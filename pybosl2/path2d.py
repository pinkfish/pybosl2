# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# LibFile: pybosl2/path2d.py
# FileSummary: 2-D path operations: area, offset, containment, corner rounding and extrusion.
# DocCategory: Paths, regions & surfaces
# FileGroup: BOSL2

"""2-D path operations: area, offset, polygon containment, round_corners, linear_extrude, and more.

The :class:`Path2D` class extends :class:`~pybosl2.paths.Path` with 2-D-specific
operations (polygon, area, offset, :meth:`~Path2D.round_corners`) while inheriting
the dimension-agnostic measurements from :class:`~pybosl2.paths.Path`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from numpy.typing import NDArray

    from pybosl2._backend import Solid
    from pybosl2.beziers import Bezier
    from pybosl2.color import Color
    from pybosl2.path3d import Path3D
    from pybosl2.regions import Region
    from pybosl2.shapes2d import Bosl2Shape2D
    from pybosl2.shapes3d import Bosl2Solid

import shapely
from shapely.geometry import LineString, Polygon

from pybosl2.bounds import Bounds2D
from pybosl2.caps import CapSpec, CapType
from pybosl2.distributors import Distributable
from pybosl2.geometry import (
    _is_point_on_segment,
    general_line_intersection,
    is_collinear,
    line_normal,
)
from pybosl2.math import EPSILON, deriv, deriv2, lerpn
from pybosl2.miscellaneous import Extrudable
from pybosl2.paths import (
    CutPoint,
    Path,
    SubdivideMethod,
)
from pybosl2.points import Point
from pybosl2.rounding import Roundable
from pybosl2.skin import Sweepable

__all__ = ["Path2D", "MinkowskiJoin", "SelfIntersection"]


# Section: Path2D object
# ---------------------------------------------------------------------------


class MinkowskiJoin(Enum):
    """Corner join style for :meth:`Path2D.minkowski_sum_circle`.

    ``ROUND``
        Circular arc joins (default). Smooth, radiused corners.
    ``MITRE``
        Sharp mitered joins, clipped at *mitre_limit*.
    ``BEVEL``
        Flat chamfered joins.
    """

    ROUND = 1
    MITRE = 2
    BEVEL = 3


@dataclass(frozen=True, slots=True)
class SelfIntersection:
    """A single self-intersection point on a path.

    Attributes:
        point: The (x, y) intersection point.
        seg1: Index of the first segment involved.
        prop1: Proportion along the first segment (0 to 1).
        seg2: Index of the second segment involved.
        prop2: Proportion along the second segment (0 to 1).

    """

    point: Point
    seg1: int
    prop1: float
    seg2: int
    prop2: float


#: How far a join that repairs a dropped offset edge may reach, as a multiple of the offset
#: distance, before it is cut straight across instead (Shapely's ``mitre_limit`` default).
_BRIDGE_MITRE_LIMIT = 5.0


def _xy(point: np.ndarray) -> list[float]:
    """One point as a plain ``[x, y]`` pair of floats."""
    return [float(point[0]), float(point[1])]


@dataclass(frozen=True, slots=True)
class _OffsetJoin:
    """Where two offset edges meet, and how to bridge them.

    Used by :meth:`Path2D._offset`. *pt_in* is where the incoming offset edge ends and *pt_out*
    where the outgoing one starts. At a corner that closes up the two run into each other and a
    :meth:`mitre` is the whole join; at one that opens up they are ``amount`` apart around
    *vertex*, and the gap is bridged by an :meth:`arc` or a :meth:`chamfer` instead.

    Attributes:
        vertex: The corner of the original outline.
        pt_in: The end of the incoming offset edge.
        pt_out: The start of the outgoing offset edge.
        u_in: Unit direction of the incoming edge.
        u_out: Unit direction of the outgoing edge.
        n_in: Offset normal of the incoming edge.
        n_out: Offset normal of the outgoing edge.
        amount: The signed offset distance.

    """

    vertex: np.ndarray
    pt_in: np.ndarray
    pt_out: np.ndarray
    u_in: np.ndarray
    u_out: np.ndarray
    n_in: np.ndarray
    n_out: np.ndarray
    amount: float

    @property
    def _cross(self) -> float:
        """The turn from the incoming to the outgoing direction."""
        return float(self.u_in[0] * self.u_out[1] - self.u_in[1] * self.u_out[0])

    def opens_gap(self, sign: float) -> bool:
        """Return True if the offset pulls the two edges apart here, leaving a gap to bridge.

        Args:
            sign: 1 for a counter-clockwise outline, -1 for a clockwise one.

        """
        return self._cross * sign * self.amount > 0

    def mitre(self, limit: float | None = None) -> list[list[float]]:
        """Return the sharp corner at the intersection of the two offset edges.

        Args:
            limit: Cap on the corner's reach, as a multiple of the offset distance. Two edges
                that nearly miss each other meet a long way off, so the joins that repair a
                dropped edge cap it and cut straight across instead. ``None`` (the join the
                caller asked for) never caps.

        Returns:
            The single corner point, or both edge ends when the edges are parallel or reach
            past *limit*.

        """
        denom = self._cross
        ends = [_xy(self.pt_in), _xy(self.pt_out)]
        if abs(denom) < EPSILON:
            return ends[:1] if np.allclose(self.pt_in, self.pt_out, rtol=0, atol=EPSILON) else ends
        gap = self.pt_out - self.pt_in
        step = float(gap[0] * self.u_out[1] - gap[1] * self.u_out[0]) / denom
        corner = self.pt_in + self.u_in * step
        if limit is not None and float(np.linalg.norm(corner - self.pt_in)) > limit * abs(self.amount):
            return ends
        return [_xy(corner)]

    def arc(self, segments: int) -> list[list[float]]:
        """Return the gap bridged by an arc of radius ``|amount|`` around the corner.

        Args:
            segments: Facet count for a full circle at this radius.

        Returns:
            The points along the arc, from *pt_in* round to *pt_out*.

        """
        start_deg = math.degrees(math.atan2(self.pt_in[1] - self.vertex[1], self.pt_in[0] - self.vertex[0]))
        end_deg = math.degrees(math.atan2(self.pt_out[1] - self.vertex[1], self.pt_out[0] - self.vertex[0]))
        sweep = (end_deg - start_deg + 180) % 360 - 180
        steps = math.ceil(segments * abs(sweep) / 360) + 1
        theta = np.radians(start_deg + sweep * np.arange(steps) / (steps - 1))
        arc = self.vertex + abs(self.amount) * np.column_stack((np.cos(theta), np.sin(theta)))
        return arc.tolist()  # type: ignore[no-any-return]

    def chamfer(self) -> list[list[float]]:
        """Return the gap bridged by a flat cut across the corner.

        Returns:
            The two points where the offset edges meet the chamfer.

        """
        bisector = self.n_in + self.n_out
        blen = float(np.linalg.norm(bisector))
        if blen < EPSILON:
            return [_xy(self.pt_in), _xy(self.pt_out)]
        bisector = bisector / blen
        cut = self.vertex + bisector * self.amount
        out: list[list[float]] = []
        for point, direction in ((self.pt_in, self.u_in), (self.pt_out, self.u_out)):
            along = float(direction @ bisector)
            if abs(along) < EPSILON:
                out.append(_xy(point))
            else:
                out.append(_xy(point + direction * (float((cut - point) @ bisector) / along)))
        return out


class Path2D(Path, Distributable, Extrudable, Sweepable, Roundable):
    """A 2-D path (formerly ``Path2D``): a list of [x, y] points, with every path operation as a method.

    Every place that already treats a path as a plain point list (indexing, iteration, ``len()``,
    equality with a plain list, and crossing the native ``polygon()``/FFI boundary) keeps working,
    so this is a drop-in for the raw lists the toolkit passes around, while giving the chained
    object form for new code::

        Path2D([[0, 0], [80, 0], [80, 60], [0, 60]]).offset(radius=-2).round_corners(radius=1).polygon()

    Every method returns a NEW Path2D (or list/array) -- nothing mutates in place, so a path can be
    reused as the base for several derived outlines.

    Args:
        points: the [x, y] points (anything array-like; numpy scalars are converted to float)
        closed: whether the path is a closed polygon -- default False, an open polyline, matching
            BOSL2, where a path is open unless a function is told otherwise. Pass
            ``closed=True`` for a polygon: it adds the segment from the last point back to the
            first to the length, the tangents, and anything derived from them. Note that
            :meth:`polygon` and :meth:`area` treat the outline as closed either way.

    Examples:
        A box outline inset by the wall thickness and with rounded corners, extruded into a plate:

        .. pythonscad-example::

            from pybosl2 import Path2D

            outline = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]])
            plate = outline.offset(radius=-3).round_corners(radius=5).polygon().linear_extrude(height=4)
            plate.show()

    """

    def __init__(self, points: Sequence[Sequence[float]] | NDArray[np.float64] = (), closed: bool = False) -> None:
        """Initialize the instance."""
        self._color: "Color | None" = None
        # A copy, not asarray: the array is frozen below and handed to every _points reader, so
        # aliasing a caller's array here would freeze theirs too.
        pts: np.ndarray = np.array(points, dtype=np.float64)
        if pts.size == 0:
            self._coords: list[tuple[float, float]] = []
            self._array = np.array([], dtype=np.float64)  # shape (0,), as an empty path always had
            self._geom = LineString()
            self.closed = closed
            return
        assert pts.ndim == 2, f"Path2D needs a list of [x, y] points, got {pts.ndim}D array"
        assert pts.shape[1] == 2, f"Path2D needs [x, y] points, got shape {pts.shape}"
        assert pts.dtype == np.float64, f"Path2D needs float64 points, got {pts.dtype}"
        self.closed = closed
        pts.flags.writeable = False  # shared by every _points reader; see the property
        self._array = pts
        self._coords = [(x, y) for x, y in pts.tolist()]
        self._geom = LineString(pts) if len(pts) >= 2 else LineString()

    def copy(self) -> "Path2D":
        """Return a shallow copy of this path."""
        c = Path2D.__new__(Path2D)
        c._points = self._points
        c.closed = self.closed
        c._color = self._color
        c._coords = self._coords
        c._array = self._array
        c._geom = self._geom
        return c

    @classmethod
    def catenary(
        cls,
        width: float,
        droop: float | None = None,
        sides: int = 100,
        angle: float | None = None,
    ) -> Path2D:
        """Return the catenary (hanging-chain) curve of the given *width*, as a :class:`~pybosl2.paths.Path2D`.

        Give exactly one of *droop* (how far the middle hangs below the endpoints) or *angle* (the
        slope in degrees at the endpoints). The curve passes through ``[-width/2, 0]`` and
        ``[width/2, 0]`` and hangs downward (negative *droop*/*angle* flips it upward). This is BOSL2's
        ``catenary()``.

        Args:
            width: horizontal distance between the endpoints (> 0)
            droop: how far the midpoint hangs below the endpoints (give this or *angle*)
            sides:     number of points along the curve (default 100)
            angle: endpoint slope in degrees, ``0 < |angle| < 90`` (give this or *droop*)

        Examples:
            A hanging arch, stroked into a 2-mm ribbon and extruded into a wall:

            .. pythonscad-example::

                from pybosl2 import Path2D

                Path2D.catenary(width=80, droop=30).stroke(width=2).linear_extrude(height=6).show()

        """
        assert (droop is None) != (angle is None), "catenary() needs exactly one of droop= or angle="
        assert width > 0, "catenary() needs width > 0."
        assert isinstance(sides, int), "catenary() needs a positive integer sides."
        assert sides > 0, "catenary() needs a positive integer sides."
        given = droop if droop is not None else angle
        assert given is not None
        sgn = int(math.copysign(1, given))
        droop_a = None if droop is None else abs(droop)
        angle_a = None if angle is None else abs(angle)
        assert angle_a is None or (0 < angle_a < 90), "catenary() angle must satisfy 0 < |angle| < 90."

        if droop_a is None:  # solve for the scale that gives the requested endpoint slope
            assert angle_a is not None

            def slope_fn(x: float) -> float:
                p1 = math.cosh(x - 0.001) - 1
                p2 = math.cosh(x + 0.001) - 1
                return math.degrees(math.atan2(p2 - p1, 0.002))

            target, f = angle_a, slope_fn
        else:  # solve for the scale that gives the requested droop

            def droop_fn(x: float) -> float:
                return (math.cosh(x) - 1) / x if x != 0 else 0.0

            target, f = droop_a / (width / 2), droop_fn

        # binary search on x for f(x) == target (f is monotonic increasing away from 0)
        x, inc = 0.0, 4.0
        while inc >= 1e-9:
            if f(x + inc) > target:
                inc /= 2
            else:
                x += inc
        scx = x
        sc = (width / 2) / scx
        droop_v = droop_a if droop_a is not None else (math.cosh(scx) - 1) * sc
        pts: list[list[float]] = []
        for xv in lerpn(-scx, scx, sides):
            xval: float = xv * sc
            yval = 0.0 if abs(abs(xv) - scx) < 1e-9 else (math.cosh(xv) - 1) * sc - droop_v
            pts.append([xval, yval])
        if sgn < 0:
            pts = [[p[0], -p[1]] for p in pts]
        return cls(pts, closed=False)

    def _closed_coords(self) -> np.ndarray:
        """Return the coordinates with the closing segment appended, whatever ``closed`` says.

        Every caller has already decided it wants the ring; gating on ``self.closed`` here only
        made ``foo(closed=True)`` on an open path quietly return the open coordinates.
        """
        coords = list(self._coords)
        if len(coords) >= 2 and coords[0] != coords[-1]:
            coords.append(coords[0])
        return np.array(coords, dtype=np.float64)

    @property
    def _points(self) -> np.ndarray:
        """The points as an (N, 2) array.

        Held rather than rebuilt per access: the path operations reach for this inside their
        loops, and rebuilding it each time made them quadratic in the point count. It is
        read-only for that reason -- a caller that needs to write takes a ``.copy()``.
        """
        return self._array

    @_points.setter
    def _points(self, value: np.ndarray) -> None:
        arr = np.array(value, dtype=np.float64)
        arr.flags.writeable = False
        self._array = arr
        self._coords = [(x, y) for x, y in arr.tolist()]
        self._geom = LineString(arr) if len(arr) >= 2 else LineString()

    @property
    def _shapely(self) -> LineString:
        """The Shapely LineString."""
        return self._geom

    def __len__(self) -> int:
        """Return the number of items."""
        return len(self._points)

    def __getitem__(self, key: int | slice | tuple[Any, ...]) -> np.ndarray | Point:
        """Return the item at index."""
        result = self._points[key]
        if isinstance(key, int):
            return Point.from_seq(result)
        return result

    def __iter__(self) -> Iterator[np.ndarray]:
        """Return an iterator."""
        return iter(self._points)

    def __array__(self, dtype: None = None, copy: bool = False) -> np.ndarray:
        """Return a numpy array representation."""
        if copy:
            return self._points.copy()
        return self._points

    @property
    def array(self) -> np.ndarray:
        """The points as an (N, 2) numpy array, for doing your own vectorised maths.

        Returns:
            An (N, 2) float64 numpy array.

        """
        return self._points

    @property
    def to_list(self) -> list[list[float]]:
        """The points as a list of ``[x, y]`` plain-Python-float pairs.

        Returns:
            A list of ``[x, y]`` pairs.

        """
        return self._points.tolist()  # type: ignore[no-any-return]

    @property
    def _shapely_polygon(self) -> Polygon:
        """Shapely Polygon from the path outline, which is a ring whether or not ``closed`` is set.

        The region operations (area, containment, offset, the booleans) are only defined on a
        region, so they read the outline as one; ``closed`` is about traversal -- the length,
        the tangents and everything derived from them -- not about whether an outline bounds
        an area.
        """
        coords = self._closed_coords()
        return Polygon(coords.tolist()) if len(coords) >= 3 else Polygon()

    @classmethod
    def from_list(cls, lst: Sequence[Any], closed: bool = False) -> "Path2D":
        """Create a Path2D from a plain list of ``[x, y]`` coordinate pairs.

        Args:
            lst: A sequence of ``[x, y]`` coordinate pairs.
            closed: Whether the path is a closed polygon.

        Returns:
            A new :class:`Path2D` instance.

        """
        return cls(lst, closed=closed)

    # -- Path delegating implementations ----------------------------------------------------

    def segment_lengths(self, closed: bool | None = None) -> NDArray[np.float64]:
        """Length of each segment of the path, as an ndarray.

        An open path of N points has N-1 segments; a closed one has N, the extra being the
        closing segment from the last point back to the first.

        The short cases follow from that rule rather than being special-cased away:

        * An EMPTY path has no segments either way -- there are no points to join.
        * A SINGLE point is where open and closed differ. Open, it has no segments. Closed,
          the closing segment joins the point to ITSELF, so the result is one segment of
          length 0 -- not zero segments::

              Path2D([[1, 2]]).segment_lengths()               # array([])
              Path2D([[1, 2]], closed=True).segment_lengths()  # array([0.])

          This keeps ``len(segment_lengths(closed=True)) == len(path)``, which
          :meth:`tangent_array` relies on when it samples the non-uniform derivative.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of segment lengths, one per segment.

        """
        if closed is None:
            closed = self.closed
        pts = self._points
        # Counted BEFORE closing the ring: an empty path's point array is 1-D, and stacking
        # the (empty) first point onto it yields a (2, 0) array that then measures one
        # spurious zero-length segment.
        if len(pts) < 2:
            return np.zeros(1 if closed and len(pts) == 1 else 0, dtype=np.float64)
        if closed:
            pts = np.vstack([pts, pts[:1]])
        lengths: NDArray[np.float64] = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        return lengths

    def length_fractions(self, closed: bool | None = None) -> NDArray[np.float64]:
        """Distance fraction of each point in the path (0 at start, 1 at end).

        Args:
            closed: Override the instance's closed flag.

        Returns:
            An ndarray of cumulative length fractions, from 0 to 1.

        """
        if closed is None:
            closed = self.closed
        coords = np.asarray(self._closed_coords() if closed else self._shapely.coords)
        segs = np.linalg.norm(np.diff(coords, axis=0), axis=1)
        cum = np.concatenate([[0.0], np.cumsum(segs)])
        total = cum[-1]
        return cum / total if total > 1e-12 else np.zeros(len(coords), dtype=np.float64)

    def closest_point(self, pt: Point | Sequence[float], closed: bool | None = None) -> Point:
        """Return the closest point on the path to *pt*.

        Uses Shapely projection for 2-D accuracy.

        Args:
            pt: The query point as :class:`~pybosl2.points.Point` or ``[x, y]``.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A :class:`~pybosl2.points.Point` of the closest point on the path.

        """
        if closed is None:
            closed = self.closed
        from shapely.geometry import Point as _Point

        q = _Point(pt.x, pt.y) if isinstance(pt, Point) else _Point(pt[0], pt[1])
        proj = self._shapely.interpolate(self._shapely.project(q))
        return Point(float(proj.x), float(proj.y))

    def tangents(self, closed: bool | None = None, uniform: bool = True) -> "list[Point]":
        """Return the normalized tangent vector at each point of the path (BOSL2 path_tangents).

        There is always exactly one tangent per path point -- not one per segment. A path of
        fewer than two points has nothing to differentiate, so each of its points gets ``+x``
        by convention; see :meth:`~pybosl2.paths.Path.tangent_array`.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            uniform: If True, estimate the derivative assuming equally spaced points. If False,
                sample it at the true segment lengths, which follows an unevenly spaced path
                much more closely.

        Returns:
            A list of unit tangent vectors, one per path point.

        Raises:
            AssertionError: If two adjacent points coincide, leaving a zero-length tangent.

        """
        return [Point(float(t[0]), float(t[1])) for t in self.tangent_array(closed=closed, uniform=uniform)]

    def normals(self, tangents: "list[Point] | None" = None, closed: bool | None = None) -> "list[Point]":
        """Perpendicular unit normal at each point (90° rotation of tangent)."""
        if tangents is None:
            tangents = self.tangents(closed=closed)
        return [Point(-t[1], t[0]) for t in tangents]

    def curvature(self, closed: bool | None = None) -> NDArray[np.float64]:
        """Numeric curvature estimate at each point of the path (BOSL2 path_curvature).

        There is one value per path point, matching :meth:`tangents`.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of curvature values, one per path point.

        """
        if closed is None:
            closed = self.closed
        pts = self._points
        if len(pts) < 3:
            return np.zeros(len(pts), dtype=np.float64)
        d1 = np.asarray(deriv(pts, closed=closed), dtype=float)
        d2 = np.asarray(deriv2(pts, closed=closed), dtype=float)
        n1 = np.linalg.norm(d1, axis=1)
        n2 = np.linalg.norm(d2, axis=1)
        dot = np.einsum("ij,ij->i", d1, d2)
        val = np.clip((n1 * n2) ** 2 - dot**2, 0.0, None)
        curv: NDArray[np.float64] = np.sqrt(val) / n1**3
        return curv

    def torsion(self, closed: bool | None = None) -> NDArray[np.float64]:
        """Numeric torsion estimate (always 0 for 2-D paths).

        Args:
            closed: Override the instance's closed flag.

        Returns:
            An ndarray of torsion values (all zeros for 2-D).

        """
        if closed is None:
            closed = self.closed
        return np.zeros(len(self._points), dtype=np.float64)

    def cut(self, cutdist: float | Sequence[float], closed: bool | None = None) -> list[Path2D]:
        """Cut path into subpaths at the given ascending list of distances (or a single distance).

        Args:
            cutdist: A single distance or a list of ascending distances from the start.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A list of :class:`Path2D` subpaths.

        """
        if closed is None:
            closed = self.closed
        from shapely.ops import substring

        ls = self._shapely
        total = ls.length
        if total < 1e-12:
            return [self.__class__([], closed=self.closed)]
        cuts = [float(cutdist)] if isinstance(cutdist, (int, float)) else [float(c) for c in cutdist]
        cuts = sorted(set(cuts))
        if not cuts:
            return [self.__class__(self._points.tolist(), closed=self.closed)]
        sub_paths: list[Path2D] = []
        prev = 0.0
        for c in cuts:
            c = max(0.0, min(total, c))
            if c > prev:
                seg = substring(ls, prev, c)
                pts = [[float(p[0]), float(p[1])] for p in seg.coords]
                sub_paths.append(self.__class__(pts, closed=False))
            prev = c
        if prev < total - 1e-12:
            seg = substring(ls, prev, total)
            pts = [[float(p[0]), float(p[1])] for p in seg.coords]
            sub_paths.append(self.__class__(pts, closed=False))
        if not sub_paths:
            sub_paths = [self.__class__(self._points.tolist(), closed=self.closed)]
        return sub_paths

    def cut_getpaths(self, cutlist: list[CutPoint], closed: bool = False) -> list[Path2D]:  # noqa: ARG002
        """Reconstruct sub-paths from the output of cut_points().

        Args:
            cutlist: Output from cut_points(), a list of :class:`CutPoint` entries.
            closed: Whether the path is closed.

        Returns:
            A list of :class:`Path2D` subpaths.

        """
        from shapely.geometry import Point as _Point
        from shapely.ops import substring

        ls = self._shapely
        num = len(cutlist)
        if num < 2:
            return [self.__class__(self._points.tolist(), closed=self.closed)]
        result: list[Path2D] = []
        for i in range(1, num):
            d1 = cutlist[i - 1].point
            d2 = cutlist[i].point
            sp1 = _Point(d1.x, d1.y)
            sp2 = _Point(d2.x, d2.y)
            p1 = ls.project(sp1)
            p2 = ls.project(sp2)
            if p2 > p1:
                seg = substring(ls, p1, p2)
                pts = [[float(p[0]), float(p[1])] for p in seg.coords]
                result.append(self.__class__(pts, closed=False))
        return result

    def cut_points(
        self,
        cutdist: float | Sequence[float],
        closed: bool | None = None,
        direction: bool = False,
    ) -> list[CutPoint]:
        """Cut path at given distance(s) from start.

        If *direction* is True, each CutPoint includes direction and normal.
        """
        if closed is None:
            closed = self.closed

        coords = self._closed_coords() if closed else np.asarray(self._shapely.coords)
        ls = LineString(coords)
        total = ls.length
        cuts = [float(cutdist)] if isinstance(cutdist, (int, float)) else [float(c) for c in cutdist]
        result: list[CutPoint] = []
        for c in cuts:
            c = max(0.0, min(total, c))
            p = ls.interpolate(c)
            if direction:
                d0 = max(0.0, c - 1e-5)
                d1 = min(total, c + 1e-5)
                p0 = ls.interpolate(d0)
                p1 = ls.interpolate(d1)
                dx = float(p1.x - p0.x)
                dy = float(p1.y - p0.y)
                n = float(np.linalg.norm([dx, dy])) or 1.0
                tx, ty = dx / n, dy / n
                result.append(
                    CutPoint(
                        Point(float(p.x), float(p.y)),
                        0,
                        direction=np.array([tx, ty, 0.0], dtype=float),
                        normal=np.array([-ty, tx, 0.0], dtype=float),
                    )
                )
            else:
                result.append(CutPoint(Point(float(p.x), float(p.y)), 0))
        return result

    def cut_points_recurse(self, dists: Sequence[float], closed: bool = False) -> list[CutPoint]:
        """Walk the path accumulating distance until each cut distance is reached.

        Args:
            dists: Ordered list of distances from the start at which to cut.
            closed: Whether the path is closed.

        Returns:
            A list of :class:`CutPoint` entries, one per cut distance.

        """
        return self.cut_points(dists, closed=closed)

    def cut_single(self, dist: float, closed: bool = False, ind: int = 0, eps: float = 1e-7) -> CutPoint:  # noqa: ARG002
        """Find the single cut point at distance dist.

        Args:
            dist: Distance along the path from the given segment index.
            closed: Whether the path is closed.
            ind: The segment index to start searching from.
            eps: Epsilon for distance comparison.

        Returns:
            A :class:`CutPoint` with the cut point and its next segment index.

        """
        ls = self._shapely
        total = ls.length
        p = ls.interpolate(max(0.0, min(total, float(dist))))
        return CutPoint(Point(float(p.x), float(p.y)), 0)

    def cuts_path_normals(self, cuts: list[CutPoint], closed: bool = False) -> "list[Point]":
        """Compute normals at each cut point from the path geometry.

        Uses the Shapely line to find the local tangent at each cut location,
        then returns the perpendicular (normal) vector.
        """
        from shapely.geometry import LineString
        from shapely.geometry import Point as _Point

        coords = self._closed_coords() if closed else np.asarray(self._shapely.coords)
        ls = LineString(coords)
        total = ls.length
        result: list[Point] = []
        for cut in cuts:
            sp = _Point(cut.point.x, cut.point.y)
            d = ls.project(sp)
            d0 = max(0.0, d - 1e-5)
            d1 = min(total, d + 1e-5)
            p0 = ls.interpolate(d0)
            p1 = ls.interpolate(d1)
            dx = float(p1.x - p0.x)
            dy = float(p1.y - p0.y)
            n = float(np.linalg.norm([dx, dy])) or 1.0
            tx, ty = dx / n, dy / n
            result.append(Point(-ty, tx))
        return result

    def plane(self, ind: int, i: int, closed: bool = False) -> "list[Point]":  # noqa: ARG002
        """Local plane at path point (always XY for 2-D).

        Args:
            ind: Index of the first point defining the plane.
            i: Index of the search start for the third non-collinear point.
            closed: Whether the path is closed.

        Returns:
            Two basis vectors defining the XY plane.

        """
        return [Point(1.0, 0.0, 0.0), Point(0.0, 1.0, 0.0)]

    def cuts_dir(self, cuts: list[CutPoint], closed: bool = False, eps: float = 1e-2) -> "list[Point]":  # noqa: ARG002
        """Compute direction vectors at each cut point.

        Args:
            cuts: List of cut entries from cut_points().
            closed: Whether the path is closed.
            eps: Epsilon for numerical comparisons.

        Returns:
            A list of :class:`Vector` direction vectors, one per cut point.

        """
        from shapely.geometry import Point as _Point

        ls = self._shapely
        dirs = []
        for cut in cuts:
            sp = _Point(cut.point.x, cut.point.y)
            d = ls.project(sp)
            # Get tangent at that point via 1e-5 offset
            d1 = max(0.0, d - 1e-5)
            d2 = min(ls.length, d + 1e-5)
            p1 = ls.interpolate(d1)
            p2 = ls.interpolate(d2)
            v = np.array([float(p2.x - p1.x), float(p2.y - p1.y)])
            nrm = float(np.linalg.norm(v)) or 1.0
            dirs.append(Point(float(v[0]) / nrm, float(v[1]) / nrm))
        return dirs

    def subdivide_path(
        self,
        points: int | None = None,
        points_per_segment: Sequence[int] | None = None,
        maxlen: float | None = None,
        exact: bool = True,
        closed: bool | None = None,
        method: SubdivideMethod = SubdivideMethod.LENGTH,
    ) -> "Path2D":
        """Subdivide the path into more points."""
        if closed is None:
            closed = self.closed
        assert points_per_segment is None or method == SubdivideMethod.SEGMENT, (
            "points_per_segment requires method=SubdivideMethod.SEGMENT"
        )
        ls = self._shapely
        total = ls.length
        if total < 1e-12:
            return self.__class__(self._points.tolist(), closed=self.closed)

        coords = list(ls.coords)
        num_segs = len(coords) - (0 if closed else 1)

        if method == SubdivideMethod.SEGMENT or points_per_segment is not None:
            from shapely.geometry import LineString

            if points_per_segment is not None:
                ppseg = list(points_per_segment)
            else:
                n = int(points or len(self._points))
                base = n // num_segs
                rem = n % num_segs
                ppseg = [base + (1 if i < rem else 0) for i in range(num_segs)]

            result: list[list[float]] = []
            for i in range(num_segs):
                a = coords[i]
                b = coords[(i + 1) % len(coords)]
                seg = LineString([a, b])
                k = ppseg[i] if i < len(ppseg) else 1
                for j in range(k):
                    p = seg.interpolate(j / k, normalized=True) if k > 1 else seg.interpolate(0.0)
                    result.append([float(p.x), float(p.y)])
                if i == num_segs - 1:
                    # add final endpoint
                    result.append([float(b[0]), float(b[1])])
            return self.__class__(result, closed=self.closed)

        # LENGTH method — uniform spacing along entire path
        n = 0
        if points is not None:
            n = int(points)
        elif maxlen is not None:
            n = max(2, int(total / maxlen) + 1)
        else:
            n = len(self._points)

        if not exact and maxlen is not None:
            n = max(2, int(total / maxlen) + 1)

        pts = []
        step = total / (n - 1) if n > 1 else total
        for i in range(n):
            d = min(i * step, total)
            p = ls.interpolate(d)
            pts.append([float(p.x), float(p.y)])
        return self.__class__(pts, closed=self.closed)

    def resample_path(
        self,
        num_copies: int | None = None,
        spacing: float | None = None,
        closed: bool | None = None,
    ) -> "Path2D":
        """Resample the path with evenly spaced points."""
        if closed is None:
            closed = self.closed
        ls = self._shapely
        total = ls.length
        if total < 1e-12:
            return self.__class__(self._points.tolist(), closed=self.closed)

        n = num_copies
        if spacing is not None and spacing > 0:
            n = max(2, int(total / spacing))
        if n is None:
            n = len(self._points)

        pts = []
        step = total / (n - 1) if n > 1 else total
        for i in range(n):
            d = min(i * step, total)
            p = ls.interpolate(d)
            pts.append([float(p.x), float(p.y)])
        return self.__class__(pts, closed=self.closed)

    def select(self, s1: int, u1: float, s2: int, u2: float, closed: bool | None = None) -> "Path2D":
        """Portion of path from the u1 fraction of segment s1 to the u2 fraction of segment s2."""
        if closed is None:
            closed = self.closed
        from shapely.ops import substring

        coords = np.asarray(self._closed_coords() if closed else self._shapely.coords)
        segs = np.linalg.norm(np.diff(coords, axis=0), axis=1)
        cum = np.concatenate([[0.0], np.cumsum(segs)])
        total = cum[-1]
        if total < 1e-12:
            return self.__class__(self._points.tolist(), closed=self.closed)

        def _dist(s: int, u: float) -> float:
            s = s % len(segs) if len(segs) > 0 else 0
            return cum[s] + u * segs[s] if s < len(segs) else total  # type: ignore[no-any-return]

        d1 = _dist(s1, u1)
        d2 = _dist(s2, u2)
        if d2 < d1:
            d1, d2 = d2, d1
        ls = self._shapely
        seg = substring(ls, max(0.0, d1), min(total, d2))
        pts = [[float(p[0]), float(p[1])] for p in seg.coords]
        return self.__class__(pts, closed=False)

    # -- measurement -----------------------------------------------------------------------

    def bounds(self) -> Bounds2D:
        """Axis-aligned bounding box with pre-computed width and length.

        Returns:
            A :class:`Bounds2D` named tuple.

        Returns a :class:`Bounds2D` named tuple with ``min_x``, ``min_y``,
        ``max_x``, ``max_y``, ``width``, and ``length`` fields.

        """
        minx, miny, maxx, maxy = self._shapely.bounds
        return Bounds2D(
            float(minx),
            float(miny),
            float(maxx),
            float(maxy),
            float(maxx - minx),
            float(maxy - miny),
        )

    def area(self, signed: bool = False) -> float:
        """Enclosed area; *signed* keeps the sign (negative == clockwise).

        Args:
            signed: If True, preserve the sign so negative indicates clockwise winding.

        Returns:
            The enclosed area as a float.

        """
        poly = self._shapely_polygon
        if signed:
            x = self._points[:, 0]
            y = self._points[:, 1]
            shoelace = np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)
            return float(poly.area if shoelace > 0 else -poly.area)
        return float(poly.area)

    def is_clockwise(self) -> bool:
        """Return True if the polygon winds clockwise (negative signed area)."""
        return self.area(signed=True) < 0

    def perimeter(self) -> float:
        """Total length along the path, including the closing segment when it is closed.

        Returns:
            The total path length as a float.

        """
        return float(np.sum(self.segment_lengths()))

    def contains(self, point: Sequence[float]) -> bool:
        """Return True if *point* is inside the closed polygon (on the boundary counts as inside).

        Containment is only meaningful for a closed polygon, so an open path (``closed=False``)
        always returns False rather than testing.

        Args:
            point: An ``[x, y]`` coordinate to test for containment.

        Returns:
            True if the point is inside or on the boundary of the polygon.

        Examples:
            .. code-block:: python

                from pybosl2 import Path2D

                rect = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]])
                result = rect.contains([40, 30])
                print("inside:", result)
                rect.stroke(width=1).linear_extrude(height=1).show()

        """
        from shapely.geometry import Point

        return bool(self._shapely_polygon.intersects(Point(point[0], point[1])))

    @property
    def is_closed(self) -> bool:
        """Return True if the first and last points of the path coincide."""
        return bool(Path2D.is_closed_path(self._points))

    def is_simple(self) -> bool:
        """Return True if the path does not self-intersect."""
        if self.closed:
            if len(self._points) < 3:
                return True
        elif len(self._points) < 2:
            return True
        return bool(self._shapely.is_simple)

    def offset(
        self,
        radius: float | None = None,
        delta: float | None = None,
        chamfer: bool = False,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
        same_length: bool = False,
    ) -> "Path2D":
        """Offset by *radius* (rounded joins) or *delta* (sharp/chamfered).

        Prefer ``.polygon().offset(...)`` (native, Manifold-side) when you only need geometry;
        this is for when the result is needed as points.

        The result is a simple (non-self-intersecting) polygon: where the offset folds back over
        the original outline -- corner arcs colliding on a detailed outline, or mitres inverting
        when a shape is shrunk past its own width -- the folded points are dropped rather than
        left in. An offset that would break the outline into separate pieces still comes back as
        one path, since a :class:`Path2D` holds a single outline; use a
        :class:`~pybosl2.regions.Region` if the pieces matter.

        Args:
            radius: Offset distance with rounded joins (positive grows, negative shrinks).
            delta: Offset distance with sharp/chamfered joins (mutually exclusive with radius).
            chamfer: If True, use chamfered rather than sharp joins when delta is given.
            fn: Number of facets for rounded sections (overrides fa/fs).
            fa: Minimum angle in degrees for circle fragments.
            fs: Minimum size for circle fragments.
            same_length: Return one point per input point (``delta`` offsets only), for callers
                like :meth:`~pybosl2.skin.Sweepable.path_sweep2d` that need the two paths to
                correspond point-for-point (BOSL2 ``offset(..., same_length=true)``). Since
                repairing a fold means dropping points, this mode skips the repair and returns
                the raw corner construction -- do not use it for outlines you intend to keep.

        Returns:
            A new offset :class:`Path2D`.

        Raises:
            AssertionError: If not exactly one of *radius*/*delta* is given, if the path is open,
                if *same_length* is combined with rounded or chamfered joins, or if the offset
                collapsed the outline entirely (shrinking a shape by more than its own
                half-width leaves nothing).

        Examples:
            .. pythonscad-example::

                from pybosl2 import Path2D

                outline = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]])
                inset = outline.offset(radius=-3)
                inset.polygon().linear_extrude(height=4).show()

        """
        result = self.__class__(
            self._offset(
                radius=radius,
                delta=delta,
                chamfer=chamfer,
                fn=fn,
                fa=fa,
                fs=fs,
                same_length=same_length,
            ),
            closed=True,
        )
        if self._color is not None:
            result._color = self._color
        return result

    def close(self) -> "Path2D":
        """Append the start point if the path is not already closed.

        Returns a new Path2D with the first point appended to the end, making
        it a closed polygon. Has no effect if the path is already closed.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Path2D

                pts = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]], closed=False)
                result = pts.close()
                result.stroke(width=2).linear_extrude(height=4).show()

        """
        return self.__class__(Path2D.close_path(self), closed=self.closed)

    def cleanup(self) -> "Path2D":
        """Drop a duplicate closing point if present.

        If the first and last points coincide this returns a new Path2D with
        the duplicate removed, turning the path into an open one.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Path2D

                pts = Path2D([[0, 0], [80, 0], [80, 60], [0, 60], [0, 0]])
                result = pts.cleanup()
                result.stroke(width=2).linear_extrude(height=4).show()

        """
        return self.__class__(Path2D.cleanup_path(self), closed=self.closed)

    def reverse(self) -> "Path2D":
        """Return the same outline wound the other way.

        Returns a new Path2D with all points in reverse order, flipping the
        winding direction (clockwise becomes counter-clockwise and vice-versa).

        Examples:
            .. pythonscad-example::

                from pybosl2 import Path2D

                rect = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]])
                result = rect.reverse()
                result.stroke(width=2).linear_extrude(height=4).show()

        """
        return self.__class__(list(reversed(self._points)), closed=self.closed)

    def deduplicated(self) -> "Path2D":
        """Drop consecutive repeated points (:meth:`_deduplicate`).

        Examples:
            .. pythonscad-example::

                from pybosl2 import Path2D

                pts = Path2D([[0, 0], [20, 0], [20, 0], [40, 0], [40, 30], [40, 30], [80, 60]])
                result = pts.deduplicated()
                result.stroke(width=2).linear_extrude(height=4).show()

        """
        return self.__class__(Path2D._deduplicate(self._points, closed=self.closed))

    def subdivide(
        self,
        num_copies: int | None = None,
        refine: float | None = None,
        maxlen: float | None = None,
        exact: bool = True,
        closed: bool | None = None,
    ) -> "Path2D":
        """Insert points along the path.

        Give exactly one of *num_copies*, *refine* or *maxlen*.

        Args:
            num_copies: Target total number of points.
            refine: Multiply the current point count by this.
            maxlen: Cap on the spacing between points.
            exact: Hit the target count exactly rather than approximately.
            closed: Override the instance's closed flag.

        Returns:
            A new :class:`Path2D` with additional interpolated points.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Path2D

                pts = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]])
                result = pts.subdivide(num_copies=24)
                result.stroke(width=1).linear_extrude(height=4).show()

        """
        points = num_copies if num_copies is not None else None
        if points is None and refine is not None:
            points = int(len(self._points) * refine)
        return self.subdivide_path(points=points, maxlen=maxlen, exact=exact, closed=closed)

    def resample(
        self,
        num_copies: int | None = None,
        spacing: float | None = None,
        closed: bool | None = None,
    ) -> "Path2D":
        """Resample to evenly spaced points.

        Give exactly one of *num_copies* or *spacing*.

        Args:
            num_copies: Target number of points.
            spacing: Approximate spacing between points.
            closed: Override the instance's closed flag.

        Returns:
            A new :class:`Path2D` with uniformly resampled points.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Path2D

                pts = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]])
                sampled = pts.resample(num_copies=20)
                sampled.stroke(width=1).linear_extrude(height=2).show()

        """
        return self.resample_path(num_copies=num_copies, spacing=spacing, closed=closed)

    def split_at_self_crossings(self, eps: float = EPSILON) -> list[Path2D]:
        """Split this 2-D path into subpaths wherever it crosses itself.

        Args:
            eps: Epsilon for numerical comparisons.

        Returns:
            A list of :class:`Path2D` subpaths split at each self-crossing.

        """
        return [
            self.__class__(sub, closed=self.closed)
            for sub in self._split_path_at_self_crossings(eps=eps, closed=self.closed)
        ]

    def polygon_parts(self, nonzero: bool = False, eps: float = EPSILON) -> list[Path2D]:
        """Split a possibly self-intersecting polygon into non-intersecting simple polygons.

        Args:
            nonzero: If True, use non-zero winding rule instead of even-odd.
            eps: Epsilon for numerical comparisons.

        Returns:
            A list of non-intersecting simple :class:`Path2D` polygon parts.

        """
        poly = Path2D.cleanup_path(self._points, eps=eps)
        temp = Path2D(poly, closed=True)
        tagged = temp._tag_self_crossing_subpaths(nonzero=nonzero, closed=True, eps=eps)
        kept = [sub[1] for sub in tagged if sub[0] == "O"]
        # Every part is a simple polygon, so each comes back closed whatever the input was.
        return [self.__class__(part, closed=True) for part in Path2D._assemble_path_fragments(kept, eps=eps)]

    # -- transforms ------------------------------------------------------------------------
    #
    # The BOSL2 transforms.scad point-list operations, as methods. All operate in 2-D and
    # return a NEW Path2D. Directions follow BOSL2: right/left are +/-X, back is +Y and
    # forward/fwd is -Y.

    def translate(self, v: Sequence[float]) -> "Path2D":
        """Translate every point by *v* (2-D; a 1-vector shifts X only).

        Args:
            v: A 2-D translation vector ``[dx, dy]``; a 1-vector shifts X only.

        Returns:
            A new translated :class:`Path2D`.

        """
        vv = np.zeros(2)
        va = np.asarray(v, dtype=float)
        vv[: min(2, len(va))] = va[: min(2, len(va))]
        return self.__class__(self._points + vv, closed=self.closed)

    move = translate

    def rot(self, a: float) -> "Path2D":
        """Rotate every point by *a* degrees about the origin (Z axis).

        Args:
            a: Rotation angle in degrees.

        Returns:
            A new rotated :class:`Path2D`.

        """
        rad = math.radians(a)
        c, s = math.cos(rad), math.sin(rad)
        rotmat = np.array([[c, -s], [s, c]])
        return self.__class__(self._points @ rotmat.T, closed=self.closed)

    rotate = rot

    def mirror(self, v: Sequence[float]) -> "Path2D":
        """Reflect every point across the line through the origin with normal *v*.

        Args:
            v: The normal vector of the reflection line through the origin.

        Returns:
            A new mirrored :class:`Path2D`.

        """
        sides = np.asarray(v, dtype=float)
        sides = sides / np.linalg.norm(sides)
        diameter = self._points @ sides
        return self.__class__(self._points - 2 * np.outer(diameter, sides), closed=self.closed)

    def yflip(self, y: float = 0.0) -> "Path2D":
        """Reflect every point across the horizontal line Y=*y* (default: the X axis).

        Args:
            y: The Y coordinate of the horizontal reflection line.

        Returns:
            A new flipped :class:`Path2D`.

        """
        pts = self._points.copy()
        pts[:, 1] = 2 * y - pts[:, 1]
        return self.__class__(pts, closed=self.closed)

    def right(self, x: float) -> "Path2D":
        """Translate by *x* along +X.

        Args:
            x: Distance to translate along +X.

        Returns:
            A new :class:`Path2D` shifted right.

        """
        return self.translate([x, 0.0])

    def left(self, x: float) -> "Path2D":
        """Translate by *x* along -X.

        Args:
            x: Distance to translate along -X.

        Returns:
            A new :class:`Path2D` shifted left.

        """
        return self.translate([-x, 0.0])

    def back(self, y: float) -> "Path2D":
        """Translate by *y* along +Y.

        Args:
            y: Distance to translate along +Y.

        Returns:
            A new :class:`Path2D` shifted back.

        """
        return self.translate([0.0, y])

    def forward(self, y: float) -> "Path2D":
        """Translate by *y* along -Y (BOSL2 fwd()).

        Args:
            y: Distance to translate along -Y.

        Returns:
            A new :class:`Path2D` shifted forward.

        """
        return self.translate([0.0, -y])

    fwd = forward

    # -- conversion ------------------------------------------------------------------------

    def to_region(self) -> "Region":
        """Convert this path into a single-outline Region.

        Returns a :class:`~pybosl2.regions.Region` containing just this
        path as its only outline. Useful as a gateway to 2-D Boolean
        operations (union, intersection, difference) on polygons.

        """
        from pybosl2.regions import Region  # local: Region imports Path2D from here

        return Region([self])

    def to_bezier(
        self,
        closed: bool = False,
        tangents: "Path2D | None" = None,
        uniform: bool = False,
        size: float | None = None,
        relsize: float | None = None,
    ) -> "Bezier":
        """Cubic bezier PATH through every point of this path (BOSL2 path_to_bezpath).

        Delegates to :func:`pybosl2.beziers.create_bezier`.

        Args:
            closed: Whether the resulting bezier path should be closed.
            tangents: Optional pre-computed tangent vectors for each point.
            uniform: If True, use uniform parameterisation; see :meth:`tangents`.
            size: Absolute size of the tangent handles.
            relsize: Relative size of the tangent handles as a fraction of segment length.

        Returns:
            A :class:`~pybosl2.beziers.Bezier` path through the given points.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Path2D

                pts = Path2D([[0, 0], [40, 30], [80, 0], [120, 30]])
                curve = pts.to_bezier(size=10).path_curve()
                curve.stroke(width=2).linear_extrude(height=3).show()

        """
        from pybosl2.beziers import create_bezier  # local: keep the import graph acyclic

        return create_bezier(self, closed=closed, tangents=tangents, uniform=uniform, size=size, relsize=relsize)

    # -- 2-D geometry (csg backend only) ---------------------------------------------------

    def _require_csg(self, feature: str) -> None:
        # Raise UnsupportedByBackendError if the active backend is not "csg".
        from pybosl2._backend import current_backend
        from pybosl2.exceptions import UnsupportedByBackendError

        backend = current_backend()
        if backend != "csg":
            raise UnsupportedByBackendError(
                feature,
                backend,
                hint="2-D geometry is a csg-backend notion; the sdf backend goes straight from "
                "path points to a 3-D field. Use .linear_extrude(...) here, or build the 2-D "
                "shape under the default (csg) backend.",
            )

    def polygon(self) -> "Bosl2Shape2D":
        """Return this path as 2-D geometry (crosses the FFI as plain floats).

        Returns:
            A :class:`~pybosl2.shapes2d.Bosl2Shape2D`, so the result chains straight into the 2-D
            operators (``.fill()``, ``.hull()``, ``.offset()``) and the extruders
            (``.linear_extrude(...)``).

        Raises:
            UnsupportedByBackendError: under ``use_backend("sdf")``.
            Use ``linear_extrude()`` instead; it works on both backends.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Path2D

                shape = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]])
                shape.polygon().linear_extrude(height=5).show()

        """
        from pythonscad import polygon as _polygon

        from pybosl2.shapes2d import Bosl2Shape2D  # local: shapes2d imports this module

        self._require_csg("polygon")
        result = Bosl2Shape2D(_polygon([[float(x), float(y)] for x, y in self]))
        if self._color is not None and hasattr(result, "color"):
            result = result.color(self._color)
        return result

    def geometry(self) -> "Bosl2Shape2D":
        """2-D geometry of this path.

        The name :class:`Region` also exposes this, so a caller that may hold either a Path2D or a
        Region can ask for geometry without checking which it got.
        """
        return self.polygon()

    def fill(self) -> "Bosl2Shape2D":
        """Return this path as 2-D geometry with every hole filled in -- only the outermost outline survives.

        (OpenSCAD ``fill()``). For a self-intersecting path this closes up the interior
        loops that ``polygon()`` would leave as holes.

        Returns:
            A :class:`~pybosl2.shapes2d.Bosl2Shape2D` (csg backend only).

        """
        return self.polygon().fill()

    def minkowski_sum(self, other: "Path2D") -> "Path2D":
        """Return the 2-D Minkowski sum of this closed path and *other*.

        Adds *other* (a closed 2‑D polygon) to every point of this path,
        producing the swept outline as a single closed :class:`Path2D`.
        Equivalent to OpenSCAD's ``minkowski()`` for 2‑D paths.

        Uses shapely to compute the convex hull of the translated copies
        of *other* centred at each vertex of this path.  For convex shapes
        the result is exact; for non‑convex shapes it is a conservative
        approximation.

        Args:
            other: A closed :class:`Path2D` to sweep along this path.

        Returns:
            The Minkowski sum as a new closed :class:`Path2D`.

        """
        from shapely.geometry import MultiPoint

        a = np.asarray(self._points)
        b = np.asarray(other._points)

        # Build the set of all a[i] + b[j] points and take the convex hull
        points = (a[:, None, :] + b[None, :, :]).reshape(-1, a.shape[1])
        hull_points = MultiPoint(points).convex_hull

        if hull_points.is_empty:
            return Path2D([], closed=True)
        pts = list(hull_points.exterior.coords)[:-1]  # drop closing repeat
        return Path2D([[float(x), float(y)] for x, y in pts], closed=True)

    def minkowski_sum_circle(
        self,
        radius: float,
        join: MinkowskiJoin = MinkowskiJoin.ROUND,
        mitre_limit: float = 5.0,
        single_sided: bool = False,
        quad_segs: int = 16,
    ) -> "Path2D":
        r"""Return the Minkowski sum of this closed path with a circle of *radius*.

        Uses shapely :meth:`~shapely.geometry.Polygon.buffer` for an
        efficient offset with configurable corner style. Positive *radius*
        dilates (outline grows); negative erodes (shrinks).

        Corner join styles:
        * :attr:`MinkowskiJoin.ROUND` — smooth radiused corners (default)
        * :attr:`MinkowskiJoin.MITRE` — sharp mitered corners (clipped at *mitre_limit*)
        * :attr:`MinkowskiJoin.BEVEL` — flat chamfered corners

        Set *single_sided* to ``True`` for a one‑sided dilation. *quad_segs*
        controls the segment count per quadrant for round joins (default 16).

        Args:
            radius: The buffer radius (positive = dilate, negative = erode).
            join: Corner join style (default :attr:`MinkowskiJoin.ROUND`).
            mitre_limit: Maximum mitre extension ratio (:attr:`MinkowskiJoin.MITRE` only).
            single_sided: If ``True``, dilate on one side of the outline only.
            quad_segs: Segments per quadrant for round joins (default 16).

        Returns:
            A new closed :class:`Path2D`.

        Examples:
            Round join (default):

            .. pythonscad-example::

                from pybosl2 import Path2D, MinkowskiJoin

                base = Path2D([[0, 0], [30, 0], [30, 20], [0, 20]])
                base.minkowski_sum_circle(radius=5, join=MinkowskiJoin.ROUND) \
                    .polygon().linear_extrude(height=3).show()

            Sharp mitered corners:

            .. pythonscad-example::

                from pybosl2 import Path2D, MinkowskiJoin

                base = Path2D([[0, 0], [30, 0], [30, 20], [0, 20]])
                base.minkowski_sum_circle(radius=5, join=MinkowskiJoin.MITRE) \
                    .polygon().linear_extrude(height=3).show()

            Flat bevel (chamfered) corners:

            .. pythonscad-example::

                from pybosl2 import Path2D, MinkowskiJoin

                base = Path2D([[0, 0], [30, 0], [30, 20], [0, 20]])
                base.minkowski_sum_circle(radius=5, join=MinkowskiJoin.BEVEL) \
                    .polygon().linear_extrude(height=3).show()

        """
        from shapely.geometry import JOIN_STYLE
        from shapely.geometry import Polygon as _Polygon

        pts = [(float(p[0]), float(p[1])) for p in self._points]
        style_map = {
            MinkowskiJoin.ROUND: JOIN_STYLE.round,
            MinkowskiJoin.MITRE: JOIN_STYLE.mitre,
            MinkowskiJoin.BEVEL: JOIN_STYLE.bevel,
        }
        poly = _Polygon(pts).buffer(
            radius, join_style=style_map[join], mitre_limit=mitre_limit, single_sided=single_sided, quad_segs=quad_segs
        )
        if poly.is_empty:
            return Path2D([], closed=True)
        coords = list(poly.exterior.coords)[:-1]
        return Path2D([[float(x), float(y)] for x, y in coords], closed=True)

    @classmethod
    def circle2d(cls, radius: float = 10, fn: int = 64) -> "Path2D":
        """Create a closed :class:`Path2D` approximating a circle of *radius*.

        Uses *fn* uniform segments around the origin.

        Args:
            radius: Circle radius.
            fn: Number of polygon segments.

        Returns:
            A closed :class:`Path2D`.

        """
        angles = np.linspace(0, 2 * np.pi, fn, endpoint=False)
        pts = [[float(radius * np.cos(a)), float(radius * np.sin(a))] for a in angles]
        return cls(pts, closed=True)

    @classmethod
    def ellipse2d(cls, rx: float = 10, ry: float = 5, fn: int = 64) -> "Path2D":
        """Create a closed :class:`Path2D` approximating an ellipse.

        Uses *fn* uniform parametric segments with semi‑axes *rx* and *ry*
        centred at the origin.

        Args:
            rx: Semi‑axis in the X direction.
            ry: Semi‑axis in the Y direction.
            fn: Number of polygon segments.

        Returns:
            A closed :class:`Path2D`.

        """
        angles = np.linspace(0, 2 * np.pi, fn, endpoint=False)
        pts = [[float(rx * np.cos(a)), float(ry * np.sin(a))] for a in angles]
        return cls(pts, closed=True)

    def hull(self, *others: "Path2D | Region") -> "Path2D":
        """Return the 2-D convex hull of this path and all the given closed paths and regions.

        Uses shapely to compute the convex hull of the union of all input
        geometries and returns the hull as a single closed :class:`Path2D`.

        Args:
            others: The closed paths or regions to hull together.

        Returns:
            A single closed :class:`Path2D` of the convex hull outline.

        """
        from pybosl2.regions import Region  # local: Region imports Path2D from here

        region = Region.hull(self, *others)
        if region.paths:
            return region.paths[0]
        return Path2D([], closed=True)

    def union(self, *others: "Path2D") -> "Path2D":
        """Return the 2-D union of this closed path with *others*.

        Converts all paths to :class:`~shapely.geometry.Polygon` objects,
        computes the Boolean union, and returns the result as a single
        closed :class:`Path2D`. Requires all paths to be closed.

        Args:
            others: One or more closed :class:`Path2D` objects to union with.

        Returns:
            A new closed :class:`Path2D` of the union outline.

        Raises:
            ValueError: If the result is not a single valid polygon.

        """
        from shapely.geometry import Polygon as _Polygon
        from shapely.ops import unary_union

        polys = [_Polygon(self._points)]
        for other in others:
            polys.append(_Polygon(other._points))
        result = unary_union(polys)
        return Path2D._polygon_to_path(result)

    def intersection(self, *others: "Path2D") -> "Path2D":
        """Return the 2-D intersection of this closed path with *others*.

        Converts all paths to :class:`~shapely.geometry.Polygon` objects,
        computes the Boolean intersection, and returns the common area as
        a single closed :class:`Path2D`.

        Args:
            others: One or more closed :class:`Path2D` objects to intersect with.

        Returns:
            A new closed :class:`Path2D` of the intersection outline, or an
            empty :class:`Path2D` if the result is empty.

        """
        from shapely.geometry import Polygon as _Polygon

        a = _Polygon(self._points)
        for other in others:
            a = a.intersection(_Polygon(other._points))
        return Path2D._polygon_to_path(a)

    def difference(self, other: "Path2D") -> "Path2D":
        """Return the 2-D difference: *self* minus *other*.

        Subtracts *other* from this path using shapely Boolean difference.
        Requires both paths to be closed.

        Args:
            other: A closed :class:`Path2D` to subtract from this one.

        Returns:
            A new closed :class:`Path2D` of the difference outline.

        Raises:
            ValueError: If the result is not a single valid polygon.

        """
        from shapely.geometry import Polygon as _Polygon

        a = _Polygon(self._points)
        b = _Polygon(other._points)
        return Path2D._polygon_to_path(a.difference(b))

    def symmetric_difference(self, other: "Path2D") -> "Path2D":
        """Return the 2-D symmetric difference (XOR) of this path and *other*.

        Returns the area in either path but not both. Requires both paths
        to be closed.

        Args:
            other: A closed :class:`Path2D` to XOR with.

        Returns:
            A new closed :class:`Path2D` of the XOR outline.

        """
        from shapely.geometry import Polygon as _Polygon

        a = _Polygon(self._points)
        b = _Polygon(other._points)
        return Path2D._polygon_to_path(a.symmetric_difference(b))

    def __or__(self, other: "Path2D") -> "Path2D":
        """Return ``a | b``  →  ``a.union(b)``."""
        return self.union(other)

    def __and__(self, other: "Path2D") -> "Path2D":
        """Return ``a & b``  →  ``a.intersection(b)``."""
        return self.intersection(other)

    def __sub__(self, other: "Path2D") -> "Path2D":
        """Return ``a - b``  →  ``a.difference(b)``."""
        return self.difference(other)

    def __xor__(self, other: "Path2D") -> "Path2D":
        """Return ``a ^ b``  →  ``a.symmetric_difference(b)``."""
        return self.symmetric_difference(other)

    @staticmethod
    def _polygon_to_path(result: Any) -> "Path2D":
        """Convert a shapely polygon result to a closed :class:`Path2D`.

        Raises:
            ValueError: If the result is empty, invalid, or a GeometryCollection.

        """
        from shapely.geometry import GeometryCollection
        from shapely.geometry import Polygon as _Polygon

        if result.is_empty:
            return Path2D([], closed=True)
        if isinstance(result, GeometryCollection) or result.geom_type not in ("Polygon", "MultiPolygon"):
            raise ValueError(f"Boolean operation produced an invalid result: {result.geom_type}")
        if isinstance(result, _Polygon):
            return Path2D(np.asarray(result.exterior.coords)[:-1], closed=True)
        # MultiPolygon: take the largest polygon
        largest = max(result.geoms, key=lambda g: g.area)
        return Path2D(np.asarray(largest.exterior.coords)[:-1], closed=True)

    # -- 2-D -> 3-D (both backends) --------------------------------------------------------

    def linear_extrude(
        self,
        height: float,
        center: bool | None = None,
        twist: float | None = None,
        scale: float | Sequence[float] | None = None,
        slices: int | None = None,
        convexity: int | None = None,
        rounding_top: float | None = None,
        rounding_bottom: float | None = None,
        res: int | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Solid":
        """Extrude this path *height* along +Z into a 3-D solid.

        The extrusion uses whichever backend is active: a
        :class:`~pybosl2.shapes3d.Bosl2Solid` under the default CSG backend, a
        :class:`~pybosl2.sdf.shapes3d.PyShape` under ``use_backend("sdf")``::

            plate = Path2D(pts).linear_extrude(height=4)          # -> Bosl2Solid
            with use_backend("sdf"):
                field = Path2D(pts).linear_extrude(height=4)      # -> PyShape

        The extra options differ by backend, since each realizes the extrusion its own way: the
        CSG backend takes the native ``center``/``twist``/``scale``/``slices``/``convexity`` (see
        :meth:`~pybosl2.shapes2d.Bosl2Shape2D.linear_extrude`); the SDF backend takes ``center``
        plus ``rounding_top``/``rounding_bottom``/``res``, and rejects the profile-shearing ones.

        Args:
            height: The extrusion height along +Z.
            center: Centre the result on z=0 rather than starting at z=0.
            twist: Degrees to rotate the top face relative to the bottom (CSG only).
            scale: Scale of the top face, a scalar or ``[x, y]`` (CSG only).
            slices: Number of intermediate layers (CSG only).
            convexity: Rendering hint for self-overlapping cross-sections (CSG only).
            rounding_top: Rim roundover at the top (SDF only).
            rounding_bottom: Rim roundover at the bottom (SDF only).
            res: Field resolution (SDF only).
            fn: Arc smoothness override (CSG only).
            fa: Arc smoothness override (CSG only).
            fs: Arc smoothness override (CSG only).

        Examples:
            .. pythonscad-example::

                from pybosl2 import Path2D

                plate = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]])
                plate.linear_extrude(height=4).show()

        """
        from pybosl2._backend import get_backend, given_arguments

        arguments = given_arguments(
            {
                "center": center,
                "twist": twist,
                "scale": scale,
                "slices": slices,
                "convexity": convexity,
                "rounding_top": rounding_top,
                "rounding_bottom": rounding_bottom,
                "res": res,
                "fn": fn,
                "fa": fa,
                "fs": fs,
            }
        )
        result = get_backend().linear_extrude([self], height, arguments)
        if self._color is not None and hasattr(result, "color"):
            result = result.color(self._color)
        return result

    def rotate_extrude(
        self,
        angle: float = 360.0,
        convexity: int | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Bosl2Solid":
        """Revolve this path about the Y axis into a 3-D solid.

        See :meth:`~pybosl2.shapes2d.Bosl2Shape2D.rotate_extrude`.

        Args:
            angle: The sweep angle in degrees (default 360 for a full revolution).
            convexity: Rendering hint for self-overlapping cross-sections.
            fn: Arc smoothness override.
            fa: Arc smoothness override.
            fs: Arc smoothness override.

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid`.

        Raises:
            pybosl2.exceptions.UnsupportedByBackendError: under ``use_backend("sdf")`` --
            the SDF backend has no revolve; sweep the profile instead via
            ``pybosl2.sdf.shapes3d.path_sweep()``.

        """
        self._require_csg("rotate_extrude")
        result = self.polygon().rotate_extrude(angle, convexity=convexity, fn=fn, fa=fa, fs=fs)
        if self._color is not None and hasattr(result, "color"):
            result = result.color(self._color)
        return result

    def debug_polygon(self, size: float = 1, vertices: bool = True) -> Any:
        """Return a debug view of this polygon.

        The filled outline (as a thin flat solid) with each vertex labelled by its index
        in red (BOSL2 debug_polygon()). Set *size* for the label size.

        Args:
            size: Label size for the vertex indices.
            vertices: If False, show only the filled outline without labels.

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid`.

        """
        import operator
        from functools import reduce

        from pybosl2.color import Color
        from pybosl2.shapes3d import text3d

        solid = self.polygon().linear_extrude(height=0.01, center=True)
        if not vertices:
            return solid
        labels = [
            text3d(str(i), size=size, height=0.02, halign="center", valign="center")
            .translate([float(x), float(y), 0.01])
            .color(Color("red"))
            for i, (x, y) in enumerate(self)
        ]
        return reduce(operator.or_, [solid, *labels]) if labels else solid

    # -- distributors (pybosl2/distributors.py) ----------------------------------------------

    def stroke(
        self,
        width: float = 1,
        closed: bool | None = None,
        endcaps: CapType | CapSpec | None = None,
        endcap1: CapType | CapSpec | None = None,
        endcap2: CapType | CapSpec | None = None,
        joints: CapType | CapSpec = CapType.ROUND,
    ) -> "Path2D":
        """Render this 2-D path as a stroked polygon outline."""
        from pybosl2._stroke2d import stroke_2d
        from pybosl2.caps import CapSpec, normalize_one

        if endcaps is None:
            endcaps = CapType.ROUND
        ec1_raw = endcap1 if endcap1 is not None else endcaps
        ec2_raw = endcap2 if endcap2 is not None else endcaps
        ec1 = ec1_raw if isinstance(ec1_raw, CapSpec) else normalize_one(ec1_raw)
        ec2 = ec2_raw if isinstance(ec2_raw, CapSpec) else normalize_one(ec2_raw)

        result = stroke_2d(
            self,
            width=width,
            closed=self.closed if closed is None else closed,
            endcap1=ec1,
            endcap2=ec2,
            joints=joints,
        )
        if self._color is not None:
            result._color = self._color
        return result

    def dashed_stroke(
        self,
        dashpat: Sequence[float] | None = None,
        closed: bool | None = None,
        fit: bool = True,
        mindash: float = 0.5,
    ) -> "Region":
        """Break this 2-D path into dashed polygon outlines.

        Returns a :class:`Region` of dash polygons.
        """
        from pybosl2._stroke2d import dashed_stroke_2d

        return dashed_stroke_2d(
            self, dashpat=dashpat, closed=self.closed if closed is None else closed, fit=fit, mindash=mindash
        )

    def _distribute(self, mats: list[np.ndarray]) -> list[Path2D]:  # type: ignore[override]
        # Apply each copier matrix, returning the list of 2-D copies (BOSL2's function form).
        # Raises if a copier lifts the 2-D path out of the XY plane; use Path3D for those.
        if not len(self):
            return [self.__class__([], closed=self.closed) for _ in mats]
        pts3 = np.hstack([self._points, np.zeros((len(self), 1))])
        out = []
        for m in mats:
            mat = np.asarray(m, dtype=float)
            homo = np.hstack([pts3, np.ones((len(pts3), 1))])
            tr = (mat @ homo.T).T
            w = tr[:, 3:4]
            res = tr[:, :3] / np.where(w == 0, 1.0, w)
            assert float(np.max(np.abs(res[:, 2]))) < 1e-7, (
                "this copier moves the 2-D path out of the XY plane; convert to Path3D first"
            )
            out.append(self.__class__(res[:, :2], closed=self.closed))
        return out

    def __repr__(self) -> str:
        """Return a string representation."""
        return f"Path2D({len(self)} pts, closed={self.closed})"

    # ======================================================================================
    # Private instance methods -- 2-D-specific path operations
    # ======================================================================================

    def self_intersections(self, closed: bool | None = None, eps: float = EPSILON) -> list[SelfIntersection]:
        """All self-intersection points of the path.

        Returns:
            A list of :class:`SelfIntersection` entries with ``.point``, ``.seg1``,
            ``.prop1``, ``.seg2``, and ``.prop2`` fields.

        """
        if closed is None:
            closed = self.closed
        p = Path2D.close_path(self._points, eps=eps) if closed else list(self._points)
        arr = np.asarray(p, dtype=float)
        result: list[SelfIntersection] = []
        for i, j in Path2D._crossing_candidates(arr, closed, eps):
            a1, a2, b1, b2 = arr[i], arr[i + 1], arr[j], arr[j + 1]
            isect = general_line_intersection(
                (Point(float(a1[0]), float(a1[1])), Point(float(a2[0]), float(a2[1]))),
                (Point(float(b1[0]), float(b1[1])), Point(float(b2[0]), float(b2[1]))),
                eps=eps,
            )
            if isect and -eps <= isect[1] <= 1 + eps and -eps <= isect[2] <= 1 + eps:
                result.append(SelfIntersection(isect[0], i, float(isect[1]), j, float(isect[2])))
        return result

    @staticmethod
    def _crossing_candidates(arr: np.ndarray, closed: bool, eps: float) -> list[tuple[int, int]]:
        """Segment pairs close enough to cross, as ``(i, j)`` with ``j >= i + 2``, in path order.

        Found through a spatial index rather than by walking every pair, which is what made
        checking a detailed path for self-intersections quadratic. Neighbouring segments (and,
        on a closed path, the pair sharing the closing point) are skipped, as they always meet.

        Args:
            arr: The path points, as an (N, 2) array, already closed if the path is.
            closed: Whether the path is closed.
            eps: How close counts as touching.

        Returns:
            The candidate segment-index pairs, ready for an exact intersection test.

        """
        plen = len(arr)
        if plen < 4:
            return []
        segments = shapely.linestrings(np.stack([arr[:-1], arr[1:]], axis=1))
        left, right = shapely.STRtree(segments).query(segments, predicate="dwithin", distance=eps)
        pairs = np.stack([left, right], axis=1)
        pairs = pairs[pairs[:, 1] >= pairs[:, 0] + 2]  # each pair once, never a neighbour
        pairs = pairs[(pairs[:, 0] <= plen - 3) & (pairs[:, 1] <= plen - 2)]
        if closed:  # the first and last segments always meet, at the closing point
            pairs = pairs[~((pairs[:, 0] == 0) & (pairs[:, 1] == plen - 2))]
        order = np.lexsort((pairs[:, 1], pairs[:, 0]))
        return [(int(i), int(j)) for i, j in pairs[order]]

    def merge_collinear(self, closed: bool | None = None, eps: float = EPSILON) -> "Path2D":
        """Remove sequential collinear points and return a new path.

        Args:
            closed: Override the instance's closed flag.
            eps: Epsilon for collinearity comparison.

        Returns:
            A new :class:`Path2D` with collinear points removed.

        """
        if closed is None:
            closed = self.closed
        if len(self._points) <= 2:
            return self.__class__(self._points.tolist(), closed=self.closed)
        indices = [0]
        end = len(self._points) - (1 if closed else 2)
        for i in range(1, end + 1):
            pa = Point(float(self._points[i - 1][0]), float(self._points[i - 1][1]))
            pb = Point(float(self._points[i][0]), float(self._points[i][1]))
            sel = Path2D._select(self._points, i + 1)
            pc = Point(float(sel[0]), float(sel[1]))
            if not is_collinear(pa, pb, pc, eps=eps):
                indices.append(i)
        if not closed:
            indices.append(len(self._points) - 1)
        pts = [self._points[i].tolist() for i in indices]
        return self.__class__(pts, closed=self.closed)

    def deduplicate(self, closed: bool | None = None, eps: float = EPSILON) -> "Path2D":
        """Remove duplicate consecutive points and return a new path.

        Args:
            closed: Override the instance's closed flag.
            eps: Epsilon for distance comparison.

        Returns:
            A new :class:`Path2D` with duplicate points removed.

        """
        if closed is None:
            closed = self.closed
        pts = Path2D._deduplicate(self._points, closed=closed, eps=eps)
        return self.__class__(pts, closed=self.closed)

    def is_path_simple(self, closed: bool | None = None, eps: float = EPSILON) -> bool:
        """Return True if the 2D path has no self-intersections (repeated points are not intersections).

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            eps: Epsilon for numerical comparisons.

        """
        if closed is None:
            closed = self.closed
        sides = len(self._points)
        end = sides - (2 if closed else 3)
        for i in range(end + 1):
            v1 = self._points[i + 1] - self._points[i]
            v2 = self._points[(i + 2) % sides] - self._points[i + 1]
            n1, n2 = float(np.hypot(*v1)), float(np.hypot(*v2))
            if n1 > 0 and n2 > 0 and math.isclose(float(v1 @ v2) / (n1 * n2), -1, rel_tol=0, abs_tol=EPSILON):
                return False
        return len(self.self_intersections(closed=closed, eps=eps)) == 0

    def _split_path_at_self_crossings(self, closed: bool | None = None, eps: float = EPSILON) -> list[Any]:
        """Split a 2D path into subpaths wherever it crosses itself.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            eps: Epsilon for numerical comparisons.

        """
        if closed is None:
            closed = self.closed
        path = Path2D.cleanup_path(self._points, eps=eps)
        temp = Path2D(path)
        raw = []
        for a in temp.self_intersections(closed=closed, eps=eps):
            raw.append([a.seg1, a.prop1])
            raw.append([a.seg2, a.prop2])
        raw.sort(key=lambda x: (x[0], x[1]))
        isects = Path2D._deduplicate([[0, 0]] + raw + [[len(path) - (1 if closed else 2), 1]], eps=eps)
        out = []
        for p0, p1 in zip(isects, isects[1:], strict=False):
            section = temp.select(p0[0], p0[1], p1[0], p1[1], closed=closed)
            outpath = Path2D._deduplicate(section, eps=eps)  # type: ignore[arg-type]
            if len(outpath) > 1:
                out.append(outpath)
        return out

    def _tag_self_crossing_subpaths(self, nonzero: bool, closed: bool | None = None, eps: float = EPSILON) -> list[Any]:
        """Tag each subpath as "I" (inside) or "O" (outside) the original polygon.

        Args:
            nonzero: If True, use non-zero winding rule instead of even-odd.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            eps: Epsilon for numerical comparisons.

        """
        if closed is None:
            closed = self.closed
        subpaths = self._split_path_at_self_crossings(closed=closed, eps=eps)
        outline = Path2D(self._points, closed=self.closed)  # built once, tested against per subpath
        out = []
        for subpath in subpaths:
            seg = Path2D._select(subpath, 0, 1)
            mp = np.asarray(seg, dtype=float).mean(axis=0)
            ln = line_normal(
                Point(float(seg[0][0]), float(seg[0][1])),
                Point(float(seg[1][0]), float(seg[1][1])),
            )
            sides = [x / 2048 for x in ln]
            p1 = [mp[0] + sides[0], mp[1] + sides[1]]
            p2 = [mp[0] - sides[0], mp[1] - sides[1]]
            p1in = Path2D.point_in_polygon(Point(float(p1[0]), float(p1[1])), outline, nonzero=nonzero) >= 0
            p2in = Path2D.point_in_polygon(Point(float(p2[0]), float(p2[1])), outline, nonzero=nonzero) >= 0
            tag = "I" if (p1in and p2in) else "O"
            out.append([tag, subpath])
        return out

    # -- Offset ----------------------------------------------------------------------------

    def _offset(
        self,
        radius: float | None = None,
        delta: float | None = None,
        chamfer: bool = False,
        closed: bool | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
        same_length: bool = False,
    ) -> list[list[float]]:
        """Offset a closed polygon by radius (rounded joins) or delta (sharp/chamfered joins).

        Pure-Python/numpy equivalent of BOSL2's offset(), returning POINTS. Positive grows the
        polygon, negative shrinks it. Prefer PS's native 2-D offset() for geometry; use this
        only when the offset outline is needed as points.

        Each edge is shifted out by the offset distance and trimmed against its neighbours;
        edges that end up folded back over the original outline are dropped and the survivors
        run on to meet each other (BOSL2 offset()'s validity check), so the returned outline is
        simple. Shapes the corner construction cannot express -- eroded down to nothing but
        corner arcs, or broken into separate pieces -- fall back to an exact buffer.

        Args:
            radius: Offset distance with rounded joins (positive grows, negative shrinks).
            delta: Offset distance with sharp/chamfered joins (mutually exclusive with radius).
            chamfer: If True, use chamfered rather than sharp joins when delta is given.
            closed: Kept for call compatibility, and it must not be False. Offsetting is a
                region operation, so the outline is always read as a closed ring -- an open
                polyline has no inside to grow or shrink.
            fn: Number of facets for rounded sections (overrides fa/fs).
            fa: Minimum angle in degrees for circle fragments.
            fs: Minimum size for circle fragments.
            same_length: Return the raw corner construction, one point per input point, skipping
                the fold repair that would drop points (``delta``, no chamfer).

        """
        assert (radius is None) != (delta is None), (
            f"offset() needs exactly one of radius= or delta=, radius={radius} delta={delta}"
        )
        assert closed is not False, "Open paths are not supported by offset()"
        closed = True
        assert not same_length or (radius is None and not chamfer), (
            "offset(same_length=True) needs a plain delta offset: rounded and chamfered joins add points."
        )
        pts = self._points.copy()
        amount = float(radius if radius is not None else delta)  # type: ignore[arg-type]
        use_round = radius is not None
        if amount == 0:
            return [_xy(p) for p in pts]

        pts = Path2D._drop_degenerate_points(pts)
        edge = np.roll(pts, -1, axis=0) - pts
        u_edge = edge / np.linalg.norm(edge, axis=1)[:, None]
        area = 0.5 * float(np.sum(pts[:, 0] * np.roll(pts[:, 1], -1) - np.roll(pts[:, 0], -1) * pts[:, 1]))
        sign = 1.0 if area > 0 else -1.0
        normal = np.column_stack((u_edge[:, 1], -u_edge[:, 0])) * sign
        start = pts + normal * amount
        end = np.roll(pts, -1, axis=0) + normal * amount

        # Each offset edge, trimmed to where it meets its neighbours, is what has to stand off
        # from the original outline -- the untrimmed ends always overhang into the next corner.
        # Only corners that close up trim an edge; where the corner opens a gap (to be bridged by
        # an arc or chamfer) the edge ends at its own end, and the mitre there is a spike.
        u_prev = np.roll(u_edge, 1, axis=0)
        turn = u_prev[:, 0] * u_edge[:, 1] - u_prev[:, 1] * u_edge[:, 0]
        opens = turn * sign * amount > 0
        corners = Path2D._offset_corner_points(start, end, u_edge)
        if same_length:
            # The caller needs the offset to line up with the input point for point, so it gets
            # the raw per-corner construction: dropping a folded edge would drop a point with it.
            return [_xy(corner) for corner in corners]
        seg_start = np.where(opens[:, None], start, corners)
        seg_end = np.where(np.roll(opens, -1)[:, None], end, np.roll(corners, -1, axis=0))
        good = Path2D._unfolded_offset_edges(seg_start, seg_end, pts, abs(amount))
        kept = np.flatnonzero(good)
        segments = Path2D._offset_segs(abs(amount), fn, fa, fs)
        if len(kept) < 3:  # eroded down to its corner arcs: nothing left for corners to join
            return Path2D._buffered_offset(pts, amount, use_round, segments)

        # A corner only opens a gap to bridge when both its edges survived; where edges were
        # dropped the two survivors are simply run on to meet each other. Corners that just close
        # up are the common case and are already worked out in `corners`, so only the ones that
        # need bridging or repairing are built one at a time.
        neighbours = np.roll(kept, 1) + 1 == kept  # each survivor's predecessor was its neighbour
        neighbours[0] = (int(kept[-1]) + 1) % len(pts) == int(kept[0])
        plain = neighbours & ~opens[kept]
        per_corner: list[list[list[float]]] = [[point] for point in corners[kept].tolist()]
        needs_work = [False] * len(kept)
        for k in np.flatnonzero(~plain):
            index = int(k)
            cur, prev = int(kept[index]), int(kept[index - 1])
            join = Path2D._offset_join(pts, u_edge, normal, start, end, prev, cur, amount)
            if (prev + 1) % len(pts) == cur:
                per_corner[index] = join.arc(segments) if use_round else join.chamfer() if chamfer else join.mitre()
                needs_work[index] = True
            else:
                per_corner[index] = join.mitre(limit=_BRIDGE_MITRE_LIMIT)
        out: list[list[float]] = [point for corner in per_corner for point in corner]
        bridged: list[bool] = [flag for corner, flag in zip(per_corner, needs_work, strict=True) for _ in corner]

        # The bridging points are not on any offset edge, so they get the standoff check of their
        # own: on a detailed outline neighbouring corner arcs run into each other.
        standing = Path2D._unfolded_offset_points(out, bridged, pts, abs(amount))
        out = [point for point, ok in zip(out, standing, strict=True) if ok]
        deduped = Path2D._drop_repeated_points(out)
        if len(deduped) < 3 or not Path2D._ring_is_simple(deduped):
            # e.g. an offset that breaks the shape in two: the survivors joined up across the gap
            return Path2D._buffered_offset(pts, amount, use_round, segments)
        return deduped

    @staticmethod
    def _drop_repeated_points(points: list[list[float]]) -> list[list[float]]:
        """Return the ring with points that repeat their neighbour removed."""
        ring = np.asarray(points, dtype=float)
        differs = np.abs(ring - np.roll(ring, -1, axis=0)).max(axis=1) > EPSILON
        return [_xy(point) for point in ring[differs]]

    @staticmethod
    def _offset_join(
        pts: np.ndarray,
        u_edge: np.ndarray,
        normal: np.ndarray,
        start: np.ndarray,
        end: np.ndarray,
        prev: int,
        cur: int,
        amount: float,
    ) -> "_OffsetJoin":
        """Where offset edge *prev* meets offset edge *cur*.

        Args:
            pts: The outline being offset, as an (N, 2) array.
            u_edge: Unit direction of each edge.
            normal: Offset normal of each edge.
            start: Start point of each offset edge.
            end: End point of each offset edge.
            prev: Index of the incoming edge.
            cur: Index of the outgoing edge.
            amount: The signed offset distance.

        Returns:
            The join between the two edges.

        """
        return _OffsetJoin(
            vertex=pts[cur],
            pt_in=end[prev],
            pt_out=start[cur],
            u_in=u_edge[prev],
            u_out=u_edge[cur],
            n_in=normal[prev],
            n_out=normal[cur],
            amount=amount,
        )

    @staticmethod
    def _drop_degenerate_points(pts: np.ndarray) -> np.ndarray:
        """Return the outline with zero-length segments removed, for offsetting.

        Args:
            pts: The outline points, as an (N, 2) array.

        Returns:
            The points that start a real segment.

        """
        keep = np.linalg.norm(np.roll(pts, -1, axis=0) - pts, axis=1) > EPSILON
        if keep.all():
            return pts
        pts = pts[keep]
        assert len(pts) >= 3, "offset() needs at least 3 distinct points"
        return pts

    @staticmethod
    def _offset_corner_points(start: np.ndarray, end: np.ndarray, u_edge: np.ndarray) -> NDArray[np.float64]:
        """Where each offset edge meets the one before it, as if every corner were mitred.

        These are the corners of the raw offset: point *i* is where offset edge ``i-1`` and
        offset edge ``i`` cross, so ``corners[i] -> corners[i+1]`` is offset edge *i* trimmed to
        its neighbours. Parallel neighbours keep the incoming edge's end.

        Args:
            start: Start point of each offset edge, as an (E, 2) array.
            end: End point of each offset edge, as an (E, 2) array.
            u_edge: Unit direction of each edge, as an (E, 2) array.

        Returns:
            One corner point per edge, as an (E, 2) array.

        """
        u_in, u_out = np.roll(u_edge, 1, axis=0), u_edge
        pt_in, pt_out = np.roll(end, 1, axis=0), start
        denom = u_in[:, 0] * u_out[:, 1] - u_in[:, 1] * u_out[:, 0]
        step = np.zeros(len(u_edge))
        np.divide(
            (pt_out[:, 0] - pt_in[:, 0]) * u_out[:, 1] - (pt_out[:, 1] - pt_in[:, 1]) * u_out[:, 0],
            denom,
            out=step,
            where=np.abs(denom) >= EPSILON,
        )
        return np.asarray(pt_in + u_in * step[:, None], dtype=float)

    @staticmethod
    def _unfolded_offset_edges(
        start: np.ndarray, end: np.ndarray, source: np.ndarray, distance: float
    ) -> NDArray[np.bool_]:
        """Which offset edges have not folded back over the outline they came from.

        Every point of a correct offset stands *distance* away from the original outline. An
        offset edge that comes closer than that has run into another part of the path -- the
        shape was shrunk past its own width there, or a corner collapsed -- and keeping it is
        what makes an offset silently self-intersect. This is BOSL2 ``offset()``'s validity
        check; the bad edges are dropped and the survivors run on to meet each other.

        Args:
            start: Start point of each offset edge, as an (E, 2) array.
            end: End point of each offset edge, as an (E, 2) array.
            source: The outline being offset, as an (N, 2) array.
            distance: The absolute offset distance every edge must stand off by.

        Returns:
            A boolean mask over the edges.

        """
        edges = shapely.linestrings(np.stack([start, end], axis=1))
        gap = Path2D._distance_from_outline(edges, source)
        return gap >= distance - max(EPSILON, distance * 1e-9)

    @staticmethod
    def _unfolded_offset_points(
        points: list[list[float]], check: list[bool], source: np.ndarray, distance: float
    ) -> NDArray[np.bool_]:
        """Which of the offset points have not folded back over the outline they came from.

        The arc and chamfer points bridging a corner are not part of any offset edge, so they
        get the standoff check one point at a time: on a detailed outline the arcs of
        neighbouring corners run into each other, and the overlap has to go. Points that are not
        flagged in *check* are corners between two edges that already passed, and are kept.

        Args:
            points: The assembled offset points.
            check: Which of them are bridging points needing the check.
            source: The outline being offset, as an (N, 2) array.
            distance: The absolute offset distance every point must stand off by.

        Returns:
            A boolean mask over *points*.

        """
        keep = np.ones(len(points), dtype=bool)
        wanted = np.asarray(check, dtype=bool)
        if not wanted.any():
            return keep
        gap = Path2D._distance_from_outline(shapely.points(np.asarray(points, dtype=float)[wanted]), source)
        keep[wanted] = gap >= distance - max(EPSILON, distance * 1e-9)
        return keep

    @staticmethod
    def _distance_from_outline(geometries: NDArray[Any], source: np.ndarray) -> NDArray[np.float64]:
        """How far each geometry stands off the closed outline through *source*.

        The outline goes into an index segment by segment rather than being measured against as
        one long LineString, so checking a detailed offset costs O(n log n) rather than a scan
        per geometry.

        Args:
            geometries: The Shapely geometries to measure (points, or the offset edges).
            source: The outline, as an (M, 2) array.

        Returns:
            The distance from each geometry to the outline.

        """
        ring = np.vstack([source, source[:1]])
        segments = shapely.linestrings(np.stack([ring[:-1], ring[1:]], axis=1))
        _, distance = shapely.STRtree(segments).query_nearest(geometries, return_distance=True, all_matches=False)
        return np.asarray(distance, dtype=float)

    @staticmethod
    def _ring_is_simple(points: list[list[float]]) -> bool:
        """Return True if the closed ring through *points* does not cross itself."""
        return bool(LineString([*points, points[0]]).is_simple)

    @staticmethod
    def _buffered_offset(source: np.ndarray, amount: float, use_round: bool, segments: int) -> list[list[float]]:
        """Return the offset as an exact buffer, for the shapes the corner construction cannot express.

        Two cases end up here: an outline eroded so far that it is all corner arcs and no edges
        survive, and one the offset breaks into separate pieces, where joining the survivors up
        crosses the gap. Both are exact for a buffer, so the outline is buffered instead. A
        :class:`Path2D` holds one outline, so the largest piece is the one that comes back.

        Args:
            source: The outline being offset, as an (N, 2) array.
            amount: The signed offset distance (negative shrinks).
            use_round: True for rounded joins, False for mitred ones.
            segments: Facet count for a full circle, used as the arc resolution.

        Returns:
            The offset outline, wound the same way as *source*.

        Raises:
            AssertionError: If the offset leaves nothing at all.

        """
        polygon = Polygon(np.vstack([source, source[:1]]).tolist())
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        grown = polygon.buffer(
            amount,
            join_style="round" if use_round else "mitre",
            quad_segs=max(segments // 4, 1),
            mitre_limit=1e9,
        )
        parts = [part for part in getattr(grown, "geoms", [grown]) if not part.is_empty]
        assert parts, f"offset() collapsed the path: offsetting by {abs(amount)} leaves nothing of this outline."
        ring = [[float(x), float(y)] for x, y in max(parts, key=lambda part: part.area).exterior.coords[:-1]]
        assert len(ring) >= 3, (
            f"offset() collapsed the path: offsetting by {abs(amount)} leaves nothing of this outline."
        )
        source_sign = Path2D.polygon_area(source, signed=True)
        return (
            ring
            if math.copysign(1, Path2D.polygon_area(ring, signed=True)) == math.copysign(1, source_sign)
            else ring[::-1]
        )

    # ======================================================================================
    # Private static kernels -- generic list/sequence helpers and polygon operations
    # ======================================================================================

    @staticmethod
    def _select(lst: Sequence[Any] | np.ndarray, start: int, end: int | None = None) -> list[Any]:
        # Circular list indexing/slicing (BOSL2 Path2D._select()). Wraps index modulo len;
        # slice form returns inclusive circular slice from start to end, wrapping past end.
        sides = len(lst)
        if sides == 0:
            return []
        if end is None:
            if isinstance(start, (list, tuple)):
                return [lst[i % sides] for i in start]
            return lst[start % sides]  # type: ignore[no-any-return]
        assert isinstance(start, int), "_path_select(): slice form needs integer start"
        s = start % sides
        e = end % sides
        if s <= e:
            return [lst[i] for i in range(s, e + 1)]
        return [lst[i] for i in range(s, sides)] + [lst[i] for i in range(e + 1)]

    @staticmethod
    def _list_head(lst: Sequence[Any] | np.ndarray, to: int = -2) -> list[Any]:
        # Elements of lst up to and including index to (BOSL2 Path2D._list_head()).
        if to < 0:
            return list(lst[: len(lst) + to + 1])
        if to < len(lst):
            return list(lst[: to + 1])
        return list(lst)

    @staticmethod
    def _list_tail(lst: Sequence[Any] | np.ndarray, frm: int = 1) -> list[Any]:
        # Elements of lst starting at index frm (may be negative; BOSL2 Path2D._list_tail()).
        if frm < 0:
            frm = frm + len(lst)
        if frm < 0:
            return list(lst)
        return list(lst[frm:])

    @staticmethod
    def _slice(lst: Sequence[Any] | np.ndarray, start: int = 0, end: int = -1) -> list[Any]:
        # lst[start..end] inclusive, negative indices from the end, clamped (BOSL2 Path2D._slice()).
        if len(lst) == 0:
            return []
        length = len(lst)
        s = max(0, min(length - 1, start + (length if start < 0 else 0)))
        e = max(0, min(length - 1, end + (length if end < 0 else 0)))
        if e < s:
            return []
        return lst[s : e + 1]  # type: ignore[return-value]

    @staticmethod
    def _repeat(val: Any, sides: int) -> list[Any]:
        """*val* repeated *sides* times."""
        return [val for _ in range(sides)]

    @staticmethod
    def _deduplicate(lst: Sequence[Any] | np.ndarray, closed: bool = False, eps: float = EPSILON) -> list[Any]:
        # Remove consecutive (approximately) duplicate entries from lst (BOSL2 deduplicate()).
        # If closed, the last entry is also compared (wrapping) against the first.
        length = len(lst)
        if length == 0:
            return []
        end = length if closed else length - 1
        out = []
        for i in range(length):
            if i == end:
                out.append(lst[i])
                continue
            nxt = lst[(i + 1) % length]
            differs = not np.array_equal(lst[i], nxt) if eps == 0 else not np.allclose(lst[i], nxt, rtol=0, atol=eps)
            if differs:
                out.append(lst[i])
        return out

    @staticmethod
    def polygon_area(poly: Sequence[Sequence[float]] | np.ndarray | "Path2D", signed: bool = False) -> float:
        """Area of a 2-D polygon (shoelace formula).

        Args:
            poly: A sequence of [x, y] points.
            signed: If True, preserve the sign so negative indicates clockwise winding.

        """
        arr = np.asarray(poly, dtype=float)
        sides = len(arr)
        if sides < 3:
            return 0.0
        p0 = arr[0]
        rest = arr[1:] - p0
        total = float(np.sum(rest[:-1, 0] * rest[1:, 1] - rest[1:, 0] * rest[:-1, 1])) / 2
        return total if signed else abs(total)

    @staticmethod
    def point_in_polygon(
        point: Point,
        poly: "Path2D",
        nonzero: bool = False,
        eps: float = EPSILON,
    ) -> int:
        """Whether point is inside 2-D polygon poly: 1 inside, -1 outside, 0 boundary.

        Args:
            point: The :class:`~pybosl2.points.Point` to test.
            poly: The :class:`Path2D` defining the polygon boundary.
            nonzero: If True, use non-zero winding rule instead of even-odd.
            eps: Epsilon for numerical comparisons.

        """
        box = poly.bounds()
        if (
            point.x < box.min_x - eps
            or point.x > box.max_x + eps
            or point.y < box.min_y - eps
            or point.y > box.max_y + eps
        ):
            return -1

        poly_arr = np.asarray(poly, dtype=float)
        sides = len(poly_arr)
        segs = [(poly_arr[i], poly_arr[(i + 1) % sides]) for i in range(sides)]

        for seg in segs:
            seg_len = float(np.linalg.norm(seg[1] - seg[0]))
            if seg_len > eps and _is_point_on_segment(point, seg, eps=eps):
                return 0

        px, py = float(point.x), float(point.y)

        if nonzero:
            winding = 0
            for seg in segs:
                p0x = seg[0][0] - px
                p0y = seg[0][1] - py
                p1x = seg[1][0] - px
                p1y = seg[1][1] - py
                if math.hypot(p1x - p0x, p1y - p0y) <= eps:
                    continue
                if p0y <= 0:
                    if p1y > 0 and (p0x * (p1y - p0y) - p0y * (p1x - p0x)) > 0:
                        winding += 1
                else:
                    if p1y <= 0 and (p0x * (p1y - p0y) - p0y * (p1x - p0x)) < 0:
                        winding -= 1
            return 1 if winding != 0 else -1

        crossings = 0
        for seg in segs:
            p0x = seg[0][0] - px
            p0y = seg[0][1] - py
            p1x = seg[1][0] - px
            p1y = seg[1][1] - py
            if ((p1y > eps and p0y <= eps) or (p1y <= eps and p0y > eps)) and (
                -eps < p0x - p0y * (p1x - p0x) / (p1y - p0y)
            ):
                crossings += 1
        return 2 * (crossings % 2) - 1

    @staticmethod
    def is_closed_path(
        path: Sequence[Sequence[float]] | np.ndarray | "Path2D" | "Path3D", eps: float = EPSILON
    ) -> bool:
        """Return True if the first and last points of path coincide.

        Args:
            path: A path to check for closure.
            eps: Epsilon for numerical comparison.

        """
        return np.allclose(path[0], path[-1], rtol=0, atol=eps)

    @staticmethod
    def close_path(
        path: Sequence[Sequence[float]] | np.ndarray | "Path2D" | "Path3D", eps: float = EPSILON
    ) -> list[Any]:
        """Append the start point to path if it isn't already closed.

        Args:
            path: A path to close.
            eps: Epsilon for numerical comparison.

        """
        return list(path) if Path2D.is_closed_path(path, eps=eps) else list(path) + [path[0]]

    @staticmethod
    def cleanup_path(
        path: Sequence[Sequence[float]] | np.ndarray | "Path2D" | "Path3D", eps: float = EPSILON
    ) -> list[Any]:
        """Drop the last point of path if it coincides with the first.

        Args:
            path: A path to clean up.
            eps: Epsilon for numerical comparison.

        """
        return list(path)[:-1] if Path2D.is_closed_path(path, eps=eps) else list(path)

    @staticmethod
    def _scad_round(x: float) -> float:
        # Round half away from zero, matching OpenSCAD's round().
        return math.floor(x + 0.5) if x >= 0 else math.ceil(x - 0.5)

    @staticmethod
    def _sum_preserving_round(data: Sequence[float]) -> list[float]:
        # Round every entry to an integer, carrying the rounding error forward so the sum is preserved.
        out = list(data)
        error = 0.0
        for i in range(len(out) - 1):
            newval = Path2D._scad_round(out[i] + error)
            error = out[i] + error - newval
            out[i] = newval
        out[-1] = Path2D._scad_round(out[-1] + error)
        return out

    @staticmethod
    def _offset_segs(
        radius: float,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> int:
        """OpenSCAD's $fn/$fa/$fs segment count for a circle of given radius (BOSL2's segs()).

        Args:
            radius: The circle radius.
            fn: Number of facets (overrides fa/fs).
            fa: Minimum angle in degrees for circle fragments.
            fs: Minimum size for circle fragments.

        """
        if fn is not None and fn >= 3:
            return int(math.floor(fn))
        fa = fa if fa else 12.0
        fs = fs if fs else 2.0
        return max(5, int(math.ceil(min(360.0 / fa, (2 * math.pi * abs(radius)) / fs))))

    @staticmethod
    def _cut_to_seg_u_form(pathcut: list[CutPoint], path: Sequence[Any], closed: bool) -> list[Any]:
        """Convert cut_points() output to [segment, u] form usable with select().

        Args:
            pathcut: Output from cut_points().
            path: The original path.
            closed: Whether the path is closed.

        """
        lastind = len(path) - (0 if closed else 1)
        out = []
        for entry in pathcut:
            if entry.next_index > lastind:
                out.append([lastind, 0])
                continue
            a, b, c = path[entry.next_index - 1], path[entry.next_index], entry.point
            diffs = [abs(b[k] - a[k]) for k in range(len(a))]
            i = diffs.index(max(diffs))
            out.append([entry.next_index - 1, (c[i] - a[i]) / (b[i] - a[i])])
        return out

    # -- Splitting self-intersecting polygons into simple polygons -------------------------

    @staticmethod
    def _modang(x: float) -> float:
        # Modulo-angle helper: wraps to [-180, 180).
        xx = x % 360
        return xx - 360 if xx > 180 else xx

    @staticmethod
    def _extreme_angle_fragment(
        seg: list[np.ndarray], fragments: list[Any], rightmost: bool = True, eps: float = EPSILON
    ) -> list[Any]:
        """Pick the fragment with the most extreme turning angle from the given segment.

        Args:
            seg: A two-point segment [p0, p1].
            fragments: List of path fragments.
            rightmost: If True, pick the most right-turning fragment.
            eps: Epsilon for numerical comparison.

        """
        if not fragments:
            return [None, []]
        delta = [seg[1][0] - seg[0][0], seg[1][1] - seg[0][1]]
        segang = math.degrees(math.atan2(delta[1], delta[0]))
        frags = []
        for fragment in fragments:
            fwdmatch = np.allclose(seg[1], fragment[0], rtol=0, atol=eps)
            bakmatch = np.allclose(seg[1], fragment[-1], rtol=0, atol=eps)
            frags.append([fwdmatch, bakmatch, list(reversed(fragment)) if bakmatch else fragment])
        angs = []
        for frag_tuple in frags:
            fwdmatch_v: bool = frag_tuple[0]  # type: ignore[assignment]
            bakmatch_v: bool = frag_tuple[1]  # type: ignore[assignment]
            frag = frag_tuple[2]
            if fwdmatch_v or bakmatch_v:
                delta2 = [frag[1][0] - frag[0][0], frag[1][1] - frag[0][1]]  # type: ignore[index]
                segang2 = math.degrees(math.atan2(delta2[1], delta2[0]))
                angs.append(Path2D._modang(segang2 - segang))
            else:
                angs.append(999 if rightmost else -999)
        fi = angs.index(min(angs)) if rightmost else angs.index(max(angs))
        if abs(angs[fi]) > 360:
            return [None, fragments]
        remainder = [fragments[i] for i in range(len(fragments)) if i != fi]
        return [frags[fi][2], remainder]

    @staticmethod
    def _assemble_a_path_from_fragments(
        fragments: list[Any],
        rightmost: bool = True,
        startfrag: int = 0,
        eps: float = EPSILON,
    ) -> list[Any]:
        """Assemble fragments into one closed polygon path; returns [path, remaining_fragments].

        Args:
            fragments: List of path fragments.
            rightmost: If True, use right-turning rule.
            startfrag: Index of the fragment to start from.
            eps: Epsilon for numerical comparison.

        """
        if len(fragments) == 0:
            return [[], []]
        if len(fragments) == 1:
            return [fragments[0], []]
        path = fragments[startfrag]
        remainder = [fragments[i] for i in range(len(fragments)) if i != startfrag]
        while True:
            if Path2D.is_closed_path(path, eps=eps):
                return [path, remainder]
            seg = Path2D._select(path, -2, -1)
            foundfrag, remainder2 = Path2D._extreme_angle_fragment(seg, remainder, rightmost=rightmost, eps=eps)
            if foundfrag is None:
                return [path, remainder2]
            if Path2D.is_closed_path(foundfrag, eps=eps):
                return [foundfrag, [path] + remainder2]
            fragend = foundfrag[-1]
            hits = [i for i in range(len(path) - 1) if np.allclose(path[i], fragend, rtol=0, atol=eps)]
            if hits:
                hitidx = hits[-1]
                newpath = Path2D._list_head(path, hitidx)
                newfrags = ([newpath] if len(newpath) > 1 else []) + remainder2
                outpath = Path2D._slice(path, hitidx, -2) + foundfrag
                return [outpath, newfrags]
            path = path + Path2D._list_tail(foundfrag)
            remainder = remainder2

    @staticmethod
    def _assemble_path_fragments(fragments: list[Any], eps: float = EPSILON) -> list[Any]:
        """Assemble fragments into complete closed polygon paths, discarding any with area < eps.

        Args:
            fragments: List of path fragments.
            eps: Epsilon for numerical comparison.

        """
        finished = []
        frags = fragments
        while len(frags) > 0:
            minxs = [min(pt[0] for pt in frag) for frag in frags]
            minxidx = minxs.index(min(minxs))
            result_l = Path2D._assemble_a_path_from_fragments(frags, startfrag=minxidx, rightmost=False, eps=eps)
            result_r = Path2D._assemble_a_path_from_fragments(frags, startfrag=minxidx, rightmost=True, eps=eps)
            l_area = abs(Path2D.polygon_area(result_l[0])) if result_l[0] else 0
            r_area = abs(Path2D.polygon_area(result_r[0])) if result_r[0] else 0
            result = result_l if l_area < r_area else result_r
            newpath = Path2D.cleanup_path(result[0])
            remainder = result[1]
            if min(l_area, r_area) >= eps:
                finished.append(newpath)
            frags = remainder
        return finished

    # -- Rounding --------------------------------------------------------------------------

    @staticmethod
    def _vector_angle3(p0: list[float], p1: list[float], p2: list[float]) -> float:
        """Interior angle at p1 of the triplet (p0, p1, p2) in degrees, any dimension.

        Args:
            p0: First point.
            p1: Center point.
            p2: Third point.

        """
        dim = len(p1)
        v1 = [p0[i] - p1[i] for i in range(dim)]
        v2 = [p2[i] - p1[i] for i in range(dim)]
        n1, n2 = math.hypot(*v1), math.hypot(*v2)
        cosang = max(-1.0, min(1.0, sum(a * b for a, b in zip(v1, v2, strict=False)) / (n1 * n2)))
        return math.degrees(math.acos(cosang))

    @staticmethod
    def _circlecorner(
        points: list[list[float]],
        diameter: float,
        radius: float,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> list[list[float]]:
        """Build the arc points for one rounded corner of a 2-D path.

        Args:
            points: Three consecutive points [p0, p1, p2] defining the corner at p1.
            diameter: Distance from p1 to the start/end of the arc.
            radius: The corner radius.
            fn: Number of facets for the arc (overrides fa/fs).
            fa: Minimum angle in degrees for circle fragments.
            fs: Minimum size for circle fragments.

        """
        from pybosl2._helpers import arc_points as _arc_points
        from pybosl2._helpers import frag_count as _frag_count

        p0, p1, p2 = points
        dim = len(p1)
        v1 = [p0[i] - p1[i] for i in range(dim)]
        v2 = [p2[i] - p1[i] for i in range(dim)]
        n1, n2 = math.hypot(*v1), math.hypot(*v2)
        prev = [x / n1 for x in v1]
        nxt = [x / n2 for x in v2]
        cosang = max(-1.0, min(1.0, sum(a * b for a, b in zip(v1, v2, strict=False)) / (n1 * n2)))
        angle = math.degrees(math.acos(cosang)) / 2
        start = [p1[i] + prev[i] * diameter for i in range(dim)]
        end = [p1[i] + nxt[i] * diameter for i in range(dim)]
        if math.isclose(angle, 90, rel_tol=0, abs_tol=EPSILON):
            return [start, end]
        bis = [prev[i] + nxt[i] for i in range(dim)]
        bislen = math.hypot(*bis)
        bis = [x / bislen for x in bis]
        center = [radius / math.sin(math.radians(angle)) * bis[i] + p1[i] for i in range(dim)]
        sides = max(3, math.ceil((90 - angle) / 180 * _frag_count(radius, fn, fa, fs)))
        a0 = math.degrees(math.atan2(start[1] - center[1], start[0] - center[0]))
        a1 = math.degrees(math.atan2(end[1] - center[1], end[0] - center[0]))
        delta = (a1 - a0 + 180) % 360 - 180
        return _arc_points(sides, radius, a0, delta, center)

    @staticmethod
    def _round_corners(
        path: list[list[float]],
        radius: float | list[float] | None = None,
        closed: bool = True,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> list[list[float]]:
        """Round every corner of a 2-D path to the given radius, inserting an arc at each vertex.

        radius can be a scalar or a per-vertex list.

        Args:
            path: A list of [x, y] points.
            radius: Corner radius (scalar or per-vertex list).
            closed: Whether the path is a closed polygon.
            fn: Number of facets for rounds (overrides fa/fs).
            fa: Minimum angle in degrees for circle fragments.
            fs: Minimum size for circle fragments.

        """
        sides = len(path)
        assert sides > 2, f"Path2D has length {sides}. Length must be 3 or more."
        size = radius if radius is not None else radius
        assert size is not None, "Must specify radius"
        if isinstance(size, (list, tuple)):
            parm = ([0] + list(size) + [0]) if len(size) < sides else list(size)
        else:
            parm = [size] * sides

        dk = []
        for i in range(sides):
            if (not closed and (i == 0 or i == sides - 1)) or parm[i] == 0:
                dk.append([0.0, 0.0])
                continue
            p0, p1, p2 = path[(i - 1) % sides], path[i], path[(i + 1) % sides]
            angle = Path2D._vector_angle3(p0, p1, p2) / 2
            assert not math.isclose(angle, 0, rel_tol=0, abs_tol=EPSILON), (
                f"Path2D turns back on itself at index {i} with nonzero rounding"
            )
            dk.append([parm[i] / math.tan(math.radians(angle)), parm[i]])

        out = []
        for i in range(sides):
            if dk[i][0] == 0:
                out.append(path[i])
                continue
            p0, p1, p2 = path[(i - 1) % sides], path[i], path[(i + 1) % sides]
            out.extend(Path2D._circlecorner([p0, p1, p2], dk[i][0], dk[i][1], fn, fa, fs))
        return Path2D._deduplicate(out, closed=closed)

    def to_bezcornerpath(
        self,
        parm: float | list[float] | None = None,
        closed: bool | None = None,
        fn: int = 0,
        fs: float = 2.0,
    ) -> "Path2D":
        """Replace straight corners with continuous-curvature beziers (BOSL2 path_to_bezcornerpath).

        Args:
            parm: Distance from corner to control point (scalar for all corners,
                ``[d, k]`` for asymmetrical, or per-corner list).  ``None`` or ``False``
                leaves a corner sharp.
            closed: Override the path's closed flag.
            fn: Number of facets per bezier corner (0 = auto from *fs*).
            fs: Maximum facet size.

        Returns:
            A new :class:`Path2D` with bezier-rounded corners.

        """
        from pybosl2.rounding import _bezcorner

        is_closed = closed if closed is not None else self.closed
        pts = self._points.tolist()
        sides = len(pts)
        if sides < 3:
            return self.__class__(pts, closed=is_closed)

        dk: list[list[float]] = []
        if parm is None or parm is False:
            return self.__class__(pts, closed=is_closed)
        if isinstance(parm, (int, float)):
            dk = [[float(parm), 1.0]] * sides
        elif isinstance(parm[0], (int, float)):
            d, k = float(parm[0]), float(parm[1]) if len(parm) > 1 else 1.0
            dk = [[d, k]] * sides
        else:
            dk = [[float(p[0]), float(p[1]) if len(p) > 1 else 1.0] for p in parm]

        out: list[list[float]] = []
        rng = range(sides) if is_closed else range(1, sides - 1)
        last_end = 0
        for i in range(sides):
            if i in rng and dk[i][0] > 0:
                p0 = pts[(i - 1) % sides]
                p1 = pts[i]
                p2 = pts[(i + 1) % sides]
                if last_end < i:
                    out.extend(pts[last_end : i + 1])
                else:
                    out.append(pts[i])
                bez_pts = _bezcorner([p0, p1, p2], dk[i], fn=fn, fs=fs)
                out.extend(bez_pts[1:])
                last_end = i + 1
            elif i == sides - 1 and last_end < sides:
                out.extend(pts[last_end:])

        return self.__class__(out, closed=is_closed)


# ---------------------------------------------------------------------------

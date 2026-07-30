# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""2-D path operations: area, offset, polygon containment, round_corners, linear_extrude, and more.

The :class:`Path2D` class extends :class:`~pybosl2.paths.Path` with 2-D-specific
operations (polygon, area, offset, :meth:`~Path2D.round_corners`) while inheriting
the dimension-agnostic measurements from :class:`~pybosl2.paths.Path`.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import NDArray

    from pybosl2._backend import Solid
    from pybosl2.beziers import Bezier
    from pybosl2.path3d import Path3D
    from pybosl2.points import Vector
    from pybosl2.regions import Region
    from pybosl2.shapes2d import Bosl2Shape2D
    from pybosl2.shapes3d import Bosl2Solid

from pybosl2.bounds import Bounds2D
from pybosl2.caps import CapSpec, CapType
from pybosl2.comparisons import approx
from pybosl2.distributors import Distributable, _apply4
from pybosl2.geometry import (
    _is_point_on_segment,
    cross,
    general_line_intersection,
    is_collinear,
    line_normal,
    pointlist_bounds,
)
from pybosl2.math import EPSILON
from pybosl2.miscellaneous import Extrudable
from pybosl2.paths import (
    CutPoint,
    Path,
    _path_curvature,
    _path_cut,
    _path_cut_getpaths,
    _path_cut_points,
    _path_cut_points_recurse,
    _path_cut_single,
    _path_cuts_dir,
    _path_cuts_normals,
    _path_length_fractions,
    _path_normals,
    _path_plane,
    _path_select,
    _path_tangents,
    _path_torsion,
    _resample_path,
    _subdivide_path,
)
from pybosl2.points import Point
from pybosl2.rounding import Roundable
from pybosl2.skin import Sweepable
from pybosl2.vectors import unit

__all__ = ["Path2D", "MinkowskiJoin"]

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
        closed: whether the path is a closed polygon (default True)

    Examples:
        A box outline inset by the wall thickness and with rounded corners, extruded into a plate:

        .. pythonscad-example::

            outline = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]])
            plate = outline.offset(radius=-3).round_corners(radius=5).polygon().linear_extrude(height=4)
            plate.show()
    """

    def __init__(self, points: Sequence[Sequence[float]] | NDArray[np.float64] = (), closed: bool = True) -> None:
        pts: np.ndarray = np.asarray(points, dtype=np.float64)
        if pts.size == 0:
            self._points: np.ndarray = np.empty((0, 2), dtype=np.float64)
        else:
            assert pts.ndim == 2, f"Path2D needs a list of [x, y] points, got {pts.ndim}D array"
            assert pts.shape[1] == 2, f"Path2D needs [x, y] points, got shape {pts.shape}"
            assert pts.dtype == np.float64, f"Path2D needs float64 points, got {pts.dtype}"
            self._points = pts
        self.closed = closed
        self._shapely_cache: object = None

    def __len__(self) -> int:
        return len(self._points)

    def __getitem__(self, key: int | slice | tuple) -> np.ndarray:
        return self._points[key]

    def __iter__(self):
        return iter(self._points)

    def __array__(self, dtype: None = None, copy: bool = False) -> np.ndarray:
        if copy:
            return self._points.copy()
        return self._points

    @property
    def array(self) -> np.ndarray:
        """The points as an (N, 2) numpy array, for doing your own vectorised maths."""
        return self._points

    @property
    def to_list(self) -> list[list[float]]:
        """The points as a list of ``[x, y]`` plain-Python-float pairs."""
        return self._points.tolist()

    @property
    def _shapely(self):
        """Cached Shapely LineString (open) or LinearRing (closed) for this path."""
        if self._shapely_cache is None:
            from shapely.geometry import LinearRing, LineString

            pts = [(float(p[0]), float(p[1])) for p in self._points]
            if self.closed and len(pts) >= 3:
                if not np.allclose(pts[0], pts[-1]):
                    pts.append(pts[0])
                self._shapely_cache = LinearRing(pts)
            else:
                self._shapely_cache = LineString(pts)
        return self._shapely_cache

    @property
    def _shapely_polygon(self):
        """Cached Shapely Polygon for area/contains operations."""
        if not self.closed or len(self._points) < 3:
            from shapely.geometry import Polygon as _Polygon

            return _Polygon()
        if not hasattr(self, "_shapely_polygon_cache"):
            pts = [(float(p[0]), float(p[1])) for p in self._points]
            from shapely.geometry import Polygon as _Polygon

            self._shapely_polygon_cache = _Polygon(pts)
        return self._shapely_polygon_cache

    @classmethod
    def from_list(cls, lst: Sequence, closed: bool = True) -> "Path2D":
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

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of segment lengths.
        """
        if closed is None:
            closed = self.closed
        coords = np.asarray(self._shapely.coords)
        return np.linalg.norm(np.diff(coords, axis=0), axis=1)

    def length_fractions(self, closed: bool | None = None) -> NDArray[np.float64]:
        """Distance fraction of each point in the path (0 at start, 1 at end).

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of cumulative length fractions, from 0 to 1.
        """
        if closed is None:
            closed = self.closed
        return _path_length_fractions(self._points, closed)

    def closest_point(self, pt: Point | Sequence[float], closed: bool | None = None) -> Point:
        """The closest point on the path to *pt*.

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

    def tangents(self, closed: bool | None = None, uniform: bool = True) -> "list[Vector]":
        """Normalized tangent vector at each point of the path, as an ndarray.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            uniform: If True, use uniform parameter spacing; if False, weight by segment lengths.

        Returns:
            An ndarray of unit tangent vectors, one per path point.
        """
        if closed is None:
            closed = self.closed
        return _path_tangents(self._points, closed, uniform=uniform)

    def normals(self, tangents: "list[Vector] | None" = None, closed: bool | None = None) -> "list[Vector]":
        """Normal vector (perpendicular to tangent, in the plane of the curve) at each point.

        For 2-D paths this is a 90-degree rotation of the tangent. For 3-D paths it is the
        principal normal estimated via the triple-product cross.

        Args:
            tangents: Optional pre-computed tangent vectors; computed automatically if None.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of unit normal vectors, one per path point.
        """
        if closed is None:
            closed = self.closed
        return _path_normals(self._points, closed, tangents=tangents)

    def curvature(self, closed: bool | None = None) -> NDArray[np.float64]:
        """Numeric curvature estimate of the path at each point, as an ndarray.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of curvature values, one per path point.
        """
        if closed is None:
            closed = self.closed
        return _path_curvature(self._points, closed)

    def torsion(self, closed: bool | None = None) -> NDArray[np.float64]:
        """Numeric torsion estimate of the path at each point, as an ndarray.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of torsion values, one per path point.
        """
        if closed is None:
            closed = self.closed
        return _path_torsion(self._points, closed)

    def cut(self, cutdist: float | Sequence[float], closed: bool | None = None) -> list["Path2D"]:
        """Cut path into subpaths at the given ascending list of distances (or a single distance).

        Args:
            cutdist: A single distance or a list of ascending distances from the start.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A list of :class:`Path2D` subpaths.
        """
        if closed is None:
            closed = self.closed
        sub_paths = _path_cut(self._points, closed, cutdist)
        return [self.__class__(pts, closed=self.closed) for pts in sub_paths]

    def cut_getpaths(self, cutlist: list[CutPoint], closed: bool) -> list["Path2D"]:
        """Reconstruct sub-paths from the output of cut_points().

        Args:
            cutlist: Output from cut_points(), a list of :class:`CutPoint` entries.
            closed: Whether the path is closed.

        Returns:
            A list of :class:`Path2D` subpaths.
        """
        sub_paths = _path_cut_getpaths(self._points, closed, cutlist)
        return [self.__class__(pts, closed=self.closed) for pts in sub_paths]

    def cut_points(
        self,
        cutdist: float | Sequence[float],
        closed: bool | None = None,
        direction: bool = False,
    ) -> list[CutPoint]:
        """Cut path at given distance(s) from start.

        Returns a list of :class:`CutPoint` entries (or :class:`` if direction is True).

        Args:
            cutdist: A single distance or a list of ascending distances from the start.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            direction: If True, also include direction and normal at each cut point.

        Returns:
            A list of :class:`CutPoint` or :class:`` entries, one per cut distance.
        """
        if closed is None:
            closed = self.closed
        return _path_cut_points(self._points, closed, cutdist, direction=direction)

    def cut_points_recurse(self, dists: Sequence[float], closed: bool = False) -> list[CutPoint]:
        """Walk the path accumulating distance until each cut distance is reached.

        Args:
            dists: Ordered list of distances from the start at which to cut.
            closed: Whether the path is closed.

        Returns:
            A list of :class:`CutPoint` entries, one per cut distance.
        """
        return _path_cut_points_recurse(self._points, closed, dists)

    def cut_single(self, dist: float, closed: bool = False, ind: int = 0, eps: float = 1e-7) -> CutPoint:
        """Find the single cut point at distance dist from segment ind.

        Args:
            dist: Distance along the path from the given segment index.
            closed: Whether the path is closed.
            ind: The segment index to start searching from.
            eps: Epsilon for distance comparison.

        Returns:
            A :class:`CutPoint` with the cut point and its next segment index.
        """
        return _path_cut_single(self._points, closed, dist, ind=ind, eps=eps)

    def cuts_path_normals(self, cuts: list[CutPoint], dirs: list, closed: bool = False) -> "list[Vector]":
        """Compute normals at each cut point (perpendicular to the direction, in local plane).

        Args:
            cuts: List of cut entries from cut_points().
            dirs: List of direction vectors at each cut.
            closed: Whether the path is closed.

        Returns:
            A list of :class:`Vector` normal vectors, one per cut point.
        """
        return _path_cuts_normals(self._points, closed, cuts, dirs)

    def plane(self, ind: int, i: int, closed: bool = False) -> "list[Vector] | None":
        """Find the local plane defined by point ind, ind-1, and the nearest non-collinear point.

        Args:
            ind: Index of the first point defining the plane.
            i: Index of the search start for the third non-collinear point.
            closed: Whether the path is closed.

        Returns:
            A 2x3 ndarray of two basis vectors defining the local plane, or None if no
            non-collinear point is found.
        """
        return _path_plane(self._points, closed, ind, i)

    def cuts_dir(self, cuts: list[CutPoint], closed: bool = False, eps: float = 1e-2) -> "list[Vector]":
        """Compute direction vectors at each cut point (blended from adjacent segments).

        Args:
            cuts: List of cut entries from cut_points().
            closed: Whether the path is closed.
            eps: Epsilon for numerical comparisons.

        Returns:
            A list of :class:`Vector` direction vectors, one per cut point.
        """
        return _path_cuts_dir(self._points, closed, cuts, eps=eps)

    def subdivide_path(
        self,
        sides: float | Sequence[int] | None = None,
        refine: int | None = None,
        maxlen: float | None = None,
        closed: bool | None = None,
        exact: bool | None = None,
        method: str | None = None,
    ) -> "Path2D":
        """Subdivide path to produce a more finely sampled path; see BOSL2 subdivide_path().

        Args:
            sides: Target number of points.
            refine: Multiplier for point count.
            maxlen: Maximum segment length.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            exact: If True, use sum-preserving rounding.
            method: "length" or "segment".

        Returns:
            A new :class:`Path2D` with the subdivided points.
        """
        if closed is None:
            closed = self.closed
        pts = _subdivide_path(
            self._points, closed, sides=sides, refine=refine, maxlen=maxlen, exact=exact, method=method
        )
        return self.__class__(pts, closed=self.closed)

    def resample_path(
        self,
        sides: int | None = None,
        spacing: float | None = None,
        closed: bool | None = None,
    ) -> "Path2D":
        """Uniformly resample path to sides points, or to a spacing near spacing.

        Args:
            sides: Target number of points.
            spacing: Approximate spacing between points.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A new :class:`Path2D` with the uniformly resampled points.
        """
        if closed is None:
            closed = self.closed
        pts = _resample_path(self._points, closed, sides=sides, spacing=spacing)
        return self.__class__(pts, closed=self.closed)

    def select(self, s1: int, u1: float, s2: int, u2: float, closed: bool | None = None) -> list:
        """Portion of path from the u1 fraction of segment s1 to the u2 fraction of segment s2.

        Args:
            s1: Starting segment index.
            u1: Fraction along segment s1 (0 to 1).
            s2: Ending segment index.
            u2: Fraction along segment s2 (0 to 1).
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A list of points representing the selected portion of the path.
        """
        if closed is None:
            closed = self.closed
        return _path_select(self._points, closed, s1, u1, s2, u2)

    # -- measurement -----------------------------------------------------------------------

    def bounds(self) -> Bounds2D:
        """Axis-aligned bounding box with pre-computed width and length.

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
            ring = self._shapely
            return float(poly.area if ring.is_ccw else -poly.area)
        return float(poly.area)

    def is_clockwise(self) -> bool:
        """True if the polygon winds clockwise (negative signed area)."""
        return self.area(signed=True) < 0

    def perimeter(self) -> float:
        """Total length around the path."""
        return float(self._shapely.length)

    @property
    def length(self) -> float:
        """Total length around the path (alias for :meth:`perimeter`)."""
        return self.perimeter()

    def contains(self, point: Sequence[float]) -> bool:
        """True if *point* is inside the closed polygon (on the boundary counts as inside).

        Containment is only meaningful for a closed polygon, so an open path (``closed=False``)
        always returns False rather than testing.

        Args:
            point: An ``[x, y]`` coordinate to test for containment.

        Returns:
            True if the point is inside or on the boundary of the polygon.

        Examples:
            .. pythonscad-example::

                rect = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]])
                result = rect.contains([40, 30])
                print("inside:", result)
        """
        if not self.closed:
            return False
        from shapely.geometry import Point

        return bool(self._shapely_polygon.intersects(Point(point[0], point[1])))

    @property
    def is_closed(self) -> bool:
        """True if the first and last points of the path coincide."""
        return bool(Path2D._is_closed_path(self._points))

    def is_simple(self) -> bool:
        """True if the path does not self-intersect."""
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
    ) -> "Path2D":
        """Offset by *radius* (rounded joins) or *delta* (sharp/chamfered).

        Prefer ``.polygon().offset(...)`` (native, Manifold-side) when you only need geometry;
        this is for when the result is needed as points.

        Args:
            radius: Offset distance with rounded joins (positive grows, negative shrinks).
            delta: Offset distance with sharp/chamfered joins (mutually exclusive with radius).
            chamfer: If True, use chamfered rather than sharp joins when delta is given.
            fn: Number of facets for rounded sections (overrides fa/fs).
            fa: Minimum angle in degrees for circle fragments.
            fs: Minimum size for circle fragments.

        Returns:
            A new offset :class:`Path2D`.

        Examples:
            .. pythonscad-example::

                outline = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]])
                inset = outline.offset(radius=-3)
                inset.polygon().linear_extrude(height=4).show()
        """
        return self.__class__(
            self._offset(
                radius=radius,
                delta=delta,
                chamfer=chamfer,
                fn=fn,
                fa=fa,
                fs=fs,
            )
        )

    def close(self) -> "Path2D":
        """Append the start point if the path is not already closed.

        Returns a new Path2D with the first point appended to the end, making
        it a closed polygon. Has no effect if the path is already closed.

        Examples:
            .. pythonscad-example::

                pts = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]], closed=False)
                result = pts.close()
                result.stroke(width=2).linear_extrude(h=4).show()
        """
        return self.__class__(Path2D._close_path(self), closed=self.closed)

    def cleanup(self) -> "Path2D":
        """Drop a duplicate closing point if present.

        If the first and last points coincide this returns a new Path2D with
        the duplicate removed, turning the path into an open one.

        Examples:
            .. pythonscad-example::

                pts = Path2D([[0, 0], [80, 0], [80, 60], [0, 60], [0, 0]])
                result = pts.cleanup()
                result.stroke(width=2).linear_extrude(h=4).show()
        """
        return self.__class__(Path2D._cleanup_path(self), closed=self.closed)

    def reverse(self) -> "Path2D":
        """The same outline wound the other way.

        Returns a new Path2D with all points in reverse order, flipping the
        winding direction (clockwise becomes counter-clockwise and vice-versa).

        Examples:
            .. pythonscad-example::

                rect = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]])
                result = rect.reverse()
                result.stroke(width=2).linear_extrude(h=4).show()
        """
        return self.__class__(list(reversed(self._points)), closed=self.closed)

    def deduplicated(self) -> "Path2D":
        """Drop consecutive repeated points (:meth:`_deduplicate`).

        Examples:
            .. pythonscad-example::

                pts = Path2D([[0, 0], [20, 0], [20, 0], [40, 0], [40, 30], [40, 30], [80, 60]])
                result = pts.deduplicated()
                result.stroke(width=2).linear_extrude(h=4).show()
        """
        return self.__class__(Path2D._deduplicate(self._points, closed=self.closed))

    def subdivide(self, **kwargs: Any) -> "Path2D":
        """Insert points along the path.

        Args:
            **kwargs: Passed through to the subdivide kernel; must include exactly one of
                *sides* (target count), *refine* (multiplier), or *maxlen* (spacing cap).

        Returns:
            A new :class:`Path2D` with additional interpolated points.

        Examples:
            .. pythonscad-example::

                pts = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]])
                result = pts.subdivide(sides=24)
                result.stroke(width=1).linear_extrude(h=4).show()
        """
        return self.subdivide_path(**kwargs)

    def resample(self, **kwargs: Any) -> "Path2D":
        """Resample to evenly spaced points.

        Accepts *sides* (target point count) or *spacing* (approximate spacing between points).

        Args:
            **kwargs: Must include exactly one of *sides* or *spacing*.

        Returns:
            A new :class:`Path2D` with uniformly resampled points.

        Examples:
            .. pythonscad-example::

                pts = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]])
                sampled = pts.resample(sides=20)
                sampled.stroke(width=1).show()
        """
        return self.resample_path(**kwargs)

    def split_at_self_crossings(self, eps: float = EPSILON) -> list["Path2D"]:
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

    def polygon_parts(self, nonzero: bool = False, eps: float = EPSILON) -> list["Path2D"]:
        """Split a possibly self-intersecting polygon into non-intersecting simple polygons.

        Args:
            nonzero: If True, use non-zero winding rule instead of even-odd.
            eps: Epsilon for numerical comparisons.

        Returns:
            A list of non-intersecting simple :class:`Path2D` polygon parts.
        """
        poly = Path2D._cleanup_path(self._points, eps=eps)
        temp = Path2D(poly, closed=True)
        tagged = temp._tag_self_crossing_subpaths(nonzero=nonzero, closed=True, eps=eps)
        kept = [sub[1] for sub in tagged if sub[0] == "O"]
        return [self.__class__(part, closed=self.closed) for part in Path2D._assemble_path_fragments(kept, eps=eps)]

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
        """This path as a single-outline Region.

        Returns a :class:`~pybosl2.regions.Region` containing just this
        path as its only outline. Useful as a gateway to 2-D Boolean
        operations (union, intersection, difference) on polygons.

        Raises:
            ValueError: If the path is not closed.
        """
        if not self.closed:
            raise ValueError("Cannot convert an open path to a Region; close the path first with .close()")
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

                pts = Path2D([[0, 0], [40, 30], [80, 0], [120, 30]])
                curve = pts.to_bezier(size=10)
                curve.stroke(width=2).linear_extrude(h=3).show()
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
        """This path as 2-D geometry (crosses the FFI as plain floats).

        Returns:
            A :class:`~pybosl2.shapes2d.Bosl2Shape2D`, so the result chains straight into the 2-D
            operators (``.fill()``, ``.hull()``, ``.offset()``) and the extruders
            (``.linear_extrude(...)``).

        Raises:
            ~pybosl2.exceptions.UnsupportedByBackendError: under ``use_backend("sdf")`` -- see the note
            above :meth:`linear_extrude`, which works on both backends.

        Examples:
            .. pythonscad-example::

                shape = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]])
                shape.polygon().linear_extrude(height=5).show()
        """
        from pythonscad import polygon as _polygon

        from pybosl2.shapes2d import Bosl2Shape2D  # local: shapes2d imports this module

        self._require_csg("polygon")
        return Bosl2Shape2D(_polygon([[float(x), float(y)] for x, y in self]))

    def geometry(self) -> "Bosl2Shape2D":
        """2-D geometry of this path.

        The name :class:`Region` also exposes this, so a caller that may hold either a Path2D or a
        Region can ask for geometry without checking which it got.
        """
        return self.polygon()

    def fill(self) -> "Bosl2Shape2D":
        """This path as 2-D geometry with every hole filled in -- only the outermost outline

        survives (OpenSCAD ``fill()``). For a self-intersecting path this closes up the interior
        loops that ``polygon()`` would leave as holes.

        Returns:
            A :class:`~pybosl2.shapes2d.Bosl2Shape2D` (csg backend only).
        """
        return self.polygon().fill()

    def minkowski_sum(self, other: "Path2D") -> "Path2D":
        """The 2-D Minkowski sum of this closed path and *other*.

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

        Raises:
            ValueError: If either path is not closed.
        """
        from shapely.geometry import MultiPoint

        if not self.closed:
            raise ValueError("minkowski_sum() requires a closed path. Close it with .close() first.")
        if not other.closed:
            raise ValueError("minkowski_sum() requires a closed path for 'other'. Close it with .close() first.")

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
        """The Minkowski sum of this closed path with a circle of *radius*.

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

        Raises:
            ValueError: If the path is not closed.

        Examples:
            Round join (default):

            .. pythonscad-example::

                base = Path2D([[0, 0], [30, 0], [30, 20], [0, 20]])
                base.minkowski_sum_circle(radius=5, join=MinkowskiJoin.ROUND) \\
                    .polygon().linear_extrude(height=3).show()

            Sharp mitered corners:

            .. pythonscad-example::

                base = Path2D([[0, 0], [30, 0], [30, 20], [0, 20]])
                base.minkowski_sum_circle(radius=5, join=MinkowskiJoin.MITRE) \\
                    .polygon().linear_extrude(height=3).show()

            Flat bevel (chamfered) corners:

            .. pythonscad-example::

                base = Path2D([[0, 0], [30, 0], [30, 20], [0, 20]])
                base.minkowski_sum_circle(radius=5, join=MinkowskiJoin.BEVEL) \\
                    .polygon().linear_extrude(height=3).show()
        """
        from shapely.geometry import JOIN_STYLE
        from shapely.geometry import Polygon as _Polygon

        if not self.closed:
            raise ValueError("minkowski_sum_circle() requires a closed path. Close it with .close() first.")

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

    @classmethod
    def hull(cls, *others: "Path2D | Region") -> "Path2D":
        """The 2-D convex hull of all the given closed paths and regions.

        Uses shapely to compute the convex hull of the union of all input
        geometries and returns the hull as a single closed :class:`Path2D`.

        Args:
            others: The closed paths or regions to hull together.

        Returns:
            A single closed :class:`Path2D` of the convex hull outline.

        Raises:
            ValueError: If any passed :class:`Path2D` is not closed.
        """
        from pybosl2.regions import Region  # local: Region imports Path2D from here

        region = Region.hull(*others)
        if region.paths:
            return region.paths[0]
        return Path2D([])

    def union(self, *others: "Path2D") -> "Path2D":
        """The 2-D union of this closed path with *others*.

        Converts all paths to :class:`~shapely.geometry.Polygon` objects,
        computes the Boolean union, and returns the result as a single
        closed :class:`Path2D`. Requires all paths to be closed.

        Args:
            others: One or more closed :class:`Path2D` objects to union with.

        Returns:
            A new closed :class:`Path2D` of the union outline.

        Raises:
            ValueError: If any path is not closed or the result is invalid.
        """
        from shapely.geometry import Polygon as _Polygon
        from shapely.ops import unary_union

        if not self.closed:
            raise ValueError("union() requires a closed path. Close it with .close() first.")
        polys = [_Polygon([(float(p[0]), float(p[1])) for p in self._points])]
        for other in others:
            if not other.closed:
                raise ValueError("union() requires all paths to be closed.")
            polys.append(_Polygon([(float(p[0]), float(p[1])) for p in other._points]))
        result = unary_union(polys)
        return Path2D._polygon_to_path(result)

    def intersection(self, *others: "Path2D") -> "Path2D":
        """The 2-D intersection of this closed path with *others*.

        Converts all paths to :class:`~shapely.geometry.Polygon` objects,
        computes the Boolean intersection, and returns the common area as
        a single closed :class:`Path2D`.

        Args:
            others: One or more closed :class:`Path2D` objects to intersect with.

        Returns:
            A new closed :class:`Path2D` of the intersection outline, or an
            empty :class:`Path2D` if the result is empty.

        Raises:
            ValueError: If any path is not closed.
        """
        from shapely.geometry import Polygon as _Polygon

        if not self.closed:
            raise ValueError("intersection() requires a closed path. Close it with .close() first.")
        a = _Polygon([(float(p[0]), float(p[1])) for p in self._points])
        for other in others:
            if not other.closed:
                raise ValueError("intersection() requires all paths to be closed.")
            a = a.intersection(_Polygon([(float(p[0]), float(p[1])) for p in other._points]))
        return Path2D._polygon_to_path(a)

    def difference(self, other: "Path2D") -> "Path2D":
        """The 2-D difference: *self* minus *other*.

        Subtracts *other* from this path using shapely Boolean difference.
        Requires both paths to be closed.

        Args:
            other: A closed :class:`Path2D` to subtract from this one.

        Returns:
            A new closed :class:`Path2D` of the difference outline.

        Raises:
            ValueError: If either path is not closed or the result is invalid.
        """
        from shapely.geometry import Polygon as _Polygon

        if not self.closed:
            raise ValueError("difference() requires a closed path. Close it with .close() first.")
        if not other.closed:
            raise ValueError("difference() requires 'other' to be closed.")
        a = _Polygon([(float(p[0]), float(p[1])) for p in self._points])
        b = _Polygon([(float(p[0]), float(p[1])) for p in other._points])
        return Path2D._polygon_to_path(a.difference(b))

    def symmetric_difference(self, other: "Path2D") -> "Path2D":
        """The 2-D symmetric difference (XOR) of this path and *other*.

        Returns the area in either path but not both. Requires both paths
        to be closed.

        Args:
            other: A closed :class:`Path2D` to XOR with.

        Returns:
            A new closed :class:`Path2D` of the XOR outline.

        Raises:
            ValueError: If either path is not closed.
        """
        from shapely.geometry import Polygon as _Polygon

        if not self.closed:
            raise ValueError("symmetric_difference() requires a closed path. Close it with .close() first.")
        if not other.closed:
            raise ValueError("symmetric_difference() requires 'other' to be closed.")
        a = _Polygon([(float(p[0]), float(p[1])) for p in self._points])
        b = _Polygon([(float(p[0]), float(p[1])) for p in other._points])
        return Path2D._polygon_to_path(a.symmetric_difference(b))

    def __or__(self, other: "Path2D") -> "Path2D":
        """``a | b``  →  ``a.union(b)``."""
        return self.union(other)

    def __and__(self, other: "Path2D") -> "Path2D":
        """``a & b``  →  ``a.intersection(b)``."""
        return self.intersection(other)

    def __sub__(self, other: "Path2D") -> "Path2D":
        """``a - b``  →  ``a.difference(b)``."""
        return self.difference(other)

    def __xor__(self, other: "Path2D") -> "Path2D":
        """``a ^ b``  →  ``a.symmetric_difference(b)``."""
        return self.symmetric_difference(other)

    @staticmethod
    def _polygon_to_path(result) -> "Path2D":
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
            coords = list(result.exterior.coords)[:-1]
            return Path2D([[float(x), float(y)] for x, y in coords], closed=True)
        # MultiPolygon: take the largest polygon
        largest = max(result.geoms, key=lambda g: g.area)
        coords = list(largest.exterior.coords)[:-1]
        return Path2D([[float(x), float(y)] for x, y in coords], closed=True)

    # -- 2-D -> 3-D (both backends) --------------------------------------------------------

    def linear_extrude(self, height: float, **kwargs: Any) -> "Solid":
        """Extrude this path *height* along +Z into a 3-D solid, **on whichever backend is

        active**: a :class:`~pybosl2.shapes3d.Bosl2Solid` under the default CSG backend, a
        :class:`~pybosl2._sdf.shapes3d.PyShape` under ``use_backend("sdf")``::

            plate = Path2D(pts).linear_extrude(height=4)          # -> Bosl2Solid
            with use_backend("sdf"):
                field = Path2D(pts).linear_extrude(height=4)      # -> PyShape

        The extra options differ by backend, since each realizes the extrusion its own way: the
        CSG backend takes the native ``center``/``twist``/``scale``/``slices``/``convexity`` (see
        :meth:`~pybosl2.shapes2d.Bosl2Shape2D.linear_extrude`); the SDF backend takes ``center``
        plus ``rounding_top``/``rounding_bottom``/``res``, and rejects the profile-shearing ones.

        Args:
            height: The extrusion height along +Z.
            **kwargs: Backend-specific extrusion options (center, twist, scale, slices, etc.).

        Examples:
            .. pythonscad-example::

                plate = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]])
                plate.linear_extrude(height=4).show()
        """
        from pybosl2._backend import get_backend

        return get_backend().linear_extrude([self], height, **kwargs)

    def rotate_extrude(self, angle: float = 360.0, **kwargs: Any) -> "Bosl2Solid":
        """Revolve this path about the Y axis into a 3-D solid; see

        :meth:`~pybosl2.shapes2d.Bosl2Shape2D.rotate_extrude`.

        Args:
            angle: The sweep angle in degrees (default 360 for a full revolution).
            **kwargs: Additional options forwarded to the backend extruder.

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid`.

        Raises:
            ~pybosl2.exceptions.UnsupportedByBackendError: under ``use_backend("sdf")`` -- the SDF
            backend has no revolve; sweep the profile instead
            (:func:`pybosl2._sdf.shapes3d.path_sweep`).
        """
        self._require_csg("rotate_extrude")
        return self.polygon().rotate_extrude(angle, **kwargs)

    def debug_polygon(self, size: float = 1, vertices: bool = True) -> Any:
        """A debug view of this polygon: the filled outline (as a thin flat solid) with each vertex

        labelled by its index in red (BOSL2 debug_polygon()). Set *size* for the label size.

        Args:
            size: Label size for the vertex indices.
            vertices: If False, show only the filled outline without labels.

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid`.
        """
        import operator
        from functools import reduce

        from pybosl2.shapes3d import text3d

        solid = self.polygon().linear_extrude(height=0.01, center=True)
        if not vertices:
            return solid
        labels = [
            text3d(str(i), size=size, height=0.02, halign="center", valign="center")
            .translate([float(x), float(y), 0.01])
            .color("red")
            for i, (x, y) in enumerate(self)
        ]
        return reduce(operator.or_, [solid, *labels]) if labels else solid

    # -- drawing (pybosl2/drawing.py) --------------------------------------------------------

    def stroke(
        self,
        width: float = 1,
        closed: bool | None = None,
        endcaps: CapType | CapSpec = CapType.ROUND,
        endcap1: CapType | CapSpec = CapType.ROUND,
        endcap2: CapType | CapSpec = CapType.ROUND,
        joints: CapType | CapSpec = CapType.ROUND,
        dots: bool = False,
        color: str | None = None,
    ) -> Any:
        """Draw this path as a solid line of the given *width*.

        Delegates to :func:`pybosl2.drawing.stroke`.

        Args:
            width: The line width.
            closed: Override the path's closed setting; uses the path's own if None.
            endcaps: Cap style for both ends (``endcap1``/``endcap2`` override).
            endcap1: Cap style for the start of the path.
            endcap2: Cap style for the end of the path.
            joints: Style for interior corners (default ``ROUND``).
            dots: If True, mark every vertex with a round dot.
            color: Optional colour applied to the whole stroke.

        Returns:
            A 2-D or 3-D geometry object from the stroke operation.

        Examples:
            .. pythonscad-example::

                square = square(50)
                square.stroke(width=2).show()
        """
        from pybosl2.drawing import stroke as _stroke

        return _stroke(
            self,
            width=width,
            closed=self.closed if closed is None else closed,
            endcaps=endcaps,
            endcap1=endcap1,
            endcap2=endcap2,
            joints=joints,
            dots=dots,
            color=color,
        )

    def dashed_stroke(
        self,
        dashpat: Sequence[float] = (3, 3),
        closed: bool | None = None,
        fit: bool = True,
        mindash: float = 0.5,
    ) -> "list[Path2D | Path3D]":
        """Break this path into dash sub-paths (see :func:`pybosl2.drawing.dashed_stroke`).

        Args:
            dashpat: Sequence of dash/gap lengths alternating.
            closed: Override the path's closed setting; uses the path's own if None.
            fit: Scale the pattern to fit a whole number of repeats.
            mindash: Drop a trailing dash shorter than this.

        Returns:
            A list of :class:`Path2D` or :class:`Path3D` sub-paths representing the dashes.

        Examples:
            .. pythonscad-example::

                pts = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]])
                result = pts.dashed_stroke(dashpat=[8, 4])
                for dash in result:
                    dash.stroke(width=1).linear_extrude(h=3).show()
        """
        from pybosl2.drawing import dashed_stroke as _dashed

        return _dashed(  # type: ignore[return-value]
            self,
            dashpat=dashpat,
            closed=self.closed if closed is None else closed,
            fit=fit,
            mindash=mindash,
        )

    # -- distributors (pybosl2/distributors.py) ----------------------------------------------

    def _distribute(self, mats: list[np.ndarray]) -> list["Path2D"]:
        # Apply each copier matrix, returning the list of 2-D copies (BOSL2's function form).
        # Raises if a copier lifts the 2-D path out of the XY plane; use Path3D for those.
        if not len(self):
            return [self.__class__([], closed=self.closed) for _ in mats]
        pts3 = np.hstack([self._points, np.zeros((len(self), 1))])
        out = []
        for m in mats:
            res = _apply4(m, pts3)
            assert float(np.max(np.abs(res[:, 2]))) < 1e-7, (
                "this copier moves the 2-D path out of the XY plane; convert to Path3D first"
            )
            out.append(self.__class__(res[:, :2], closed=self.closed))
        return out

    def __repr__(self) -> str:
        return f"Path2D({len(self)} pts, closed={self.closed})"

    # ======================================================================================
    # Private instance methods -- 2-D-specific path operations
    # ======================================================================================

    def self_intersections(self, closed: bool | None = None, eps: float = EPSILON) -> list:
        """All self-intersection points of path: list of [POINT, SEGNUM1, PROPORTION1, SEGNUM2, PROPORTION2].

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            eps: Epsilon for numerical comparisons.
        """
        if closed is None:
            closed = self.closed
        p = Path2D._close_path(self._points, eps=eps) if closed else list(self._points)
        arr = np.asarray(p, dtype=float)
        plen = len(arr)
        result = []
        for i in range(plen - 2):
            a1, a2 = arr[i], arr[i + 1]
            diameter = a2 - a1
            seg_normal = np.asarray(unit([-diameter[1], diameter[0]], [0.0, 0.0]))
            vals = arr @ seg_normal
            ref = float(a1 @ seg_normal)
            upper = plen - (2 if (i == 0 and closed) else 1)
            js = np.arange(i + 2, upper + 1)
            if len(js) == 0:
                continue
            diffs = vals[js] - ref
            signals = np.where(np.abs(diffs) < eps, 0, np.sign(diffs))
            if not (signals.max() >= 0 and signals.min() <= 0):
                continue
            upper2 = plen - (3 if (i == 0 and closed) else 2)
            for j in range(i + 2, upper2 + 1):
                if signals[j - i - 2] * signals[j - i - 1] <= 0:
                    b1, b2 = arr[j].tolist(), arr[j + 1].tolist()
                    isect = general_line_intersection([a1.tolist(), a2.tolist()], [b1, b2], eps=eps)
                    if isect and -eps <= isect[1] <= 1 + eps and -eps <= isect[2] <= 1 + eps:
                        result.append([isect[0], i, isect[1], j, isect[2]])
        return result

    def merge_collinear(self, closed: bool | None = None, eps: float = EPSILON) -> list:
        """Remove unnecessary sequential collinear points from the path.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            eps: Epsilon for numerical comparisons.
        """
        if closed is None:
            closed = self.closed
        if len(self._points) <= 2:
            return list(self._points)
        indices = [0]
        end = len(self._points) - (1 if closed else 2)
        for i in range(1, end + 1):
            if not is_collinear(self._points[i - 1], self._points[i], Path2D._select(self._points, i + 1), eps=eps):
                indices.append(i)
        if not closed:
            indices.append(len(self._points) - 1)
        return [self._points[i] for i in indices]

    def is_path_simple(self, closed: bool | None = None, eps: float = EPSILON) -> bool:
        """True if the 2D path has no self-intersections (repeated points are not intersections).

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
            if n1 > 0 and n2 > 0 and approx(float(v1 @ v2) / (n1 * n2), -1):
                return False
        return len(self.self_intersections(closed=closed, eps=eps)) == 0

    def _split_path_at_self_crossings(self, closed: bool | None = None, eps: float = EPSILON) -> list:
        """Split a 2D path into subpaths wherever it crosses itself.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            eps: Epsilon for numerical comparisons.
        """
        if closed is None:
            closed = self.closed
        path = Path2D._cleanup_path(self._points, eps=eps)
        temp = Path2D(path)
        raw = []
        for a in temp.self_intersections(closed=closed, eps=eps):
            raw.append([a[1], a[2]])
            raw.append([a[3], a[4]])
        raw.sort(key=lambda x: (x[0], x[1]))
        isects = Path2D._deduplicate([[0, 0]] + raw + [[len(path) - (1 if closed else 2), 1]], eps=eps)
        out = []
        for p0, p1 in Path2D._pair(isects):
            section = temp.select(p0[0], p0[1], p1[0], p1[1], closed=closed)
            outpath = Path2D._deduplicate(section, eps=eps)
            if len(outpath) > 1:
                out.append(outpath)
        return out

    def _tag_self_crossing_subpaths(self, nonzero: bool, closed: bool | None = None, eps: float = EPSILON) -> list:
        """Tag each subpath as "I" (inside) or "O" (outside) the original polygon.

        Args:
            nonzero: If True, use non-zero winding rule instead of even-odd.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            eps: Epsilon for numerical comparisons.
        """
        if closed is None:
            closed = self.closed
        subpaths = self._split_path_at_self_crossings(closed=closed, eps=eps)
        out = []
        for subpath in subpaths:
            seg = Path2D._select(subpath, 0, 1)
            mp = np.asarray(seg, dtype=float).mean(axis=0)
            sides = [x / 2048 for x in line_normal(seg[0], seg[1])]
            p1 = [mp[0] + sides[0], mp[1] + sides[1]]
            p2 = [mp[0] - sides[0], mp[1] - sides[1]]
            p1in = Path2D._point_in_polygon(p1, list(self._points), nonzero=nonzero) >= 0
            p2in = Path2D._point_in_polygon(p2, list(self._points), nonzero=nonzero) >= 0
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
    ) -> list[list[float]]:
        """Offset a closed polygon by radius (rounded joins) or delta (sharp/chamfered joins).

        Pure-Python/numpy equivalent of BOSL2's offset(), returning POINTS. Positive grows the
        polygon, negative shrinks it. Prefer PS's native 2-D offset() for geometry; use this
        only when the offset outline is needed as points.

        Args:
            radius: Offset distance with rounded joins (positive grows, negative shrinks).
            delta: Offset distance with sharp/chamfered joins (mutually exclusive with radius).
            chamfer: If True, use chamfered rather than sharp joins when delta is given.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            fn: Number of facets for rounded sections (overrides fa/fs).
            fa: Minimum angle in degrees for circle fragments.
            fs: Minimum size for circle fragments.
        """
        if closed is None:
            closed = self.closed
        assert (radius is None) != (delta is None), (
            f"offset() needs exactly one of radius= or delta=, radius={radius} delta={delta}"
        )
        assert closed, "Open paths are not supported by offset()"
        pts = self._points.copy()
        if radius is not None:
            amount = float(radius)
        elif delta is not None:
            amount = float(delta)
        else:
            raise AssertionError("offset() needs exactly one of radius= or delta=")
        use_round = radius is not None
        if amount == 0:
            return [[float(x), float(y)] for x, y in pts]

        incoming = pts - np.roll(pts, 1, axis=0)
        outgoing = np.roll(pts, -1, axis=0) - pts
        len_in = np.linalg.norm(incoming, axis=1)
        len_out = np.linalg.norm(outgoing, axis=1)

        keep = (len_in > EPSILON) & (len_out > EPSILON)
        if not keep.all():
            pts = pts[keep]
            assert len(pts) >= 3, "offset() needs at least 3 distinct points"
            incoming = pts - np.roll(pts, 1, axis=0)
            outgoing = np.roll(pts, -1, axis=0) - pts
            len_in = np.linalg.norm(incoming, axis=1)
            len_out = np.linalg.norm(outgoing, axis=1)

        u_in = incoming / len_in[:, None]
        u_out = outgoing / len_out[:, None]

        area = 0.5 * float(np.sum(pts[:, 0] * np.roll(pts[:, 1], -1) - np.roll(pts[:, 0], -1) * pts[:, 1]))
        sign = 1.0 if area > 0 else -1.0

        n_in = np.column_stack((u_in[:, 1], -u_in[:, 0])) * sign
        n_out = np.column_stack((u_out[:, 1], -u_out[:, 0])) * sign
        pt_in = pts + n_in * amount
        pt_out = pts + n_out * amount

        turn = (u_in[:, 0] * u_out[:, 1] - u_in[:, 1] * u_out[:, 0]) * sign
        opens_gap = turn * amount > 0

        denom = u_in[:, 0] * u_out[:, 1] - u_in[:, 1] * u_out[:, 0]
        safe = np.abs(denom) >= EPSILON
        step = np.zeros(len(pts))
        np.divide(
            (pt_out[:, 0] - pt_in[:, 0]) * u_out[:, 1] - (pt_out[:, 1] - pt_in[:, 1]) * u_out[:, 0],
            denom,
            out=step,
            where=safe,
        )
        mitre = pt_in + u_in * step[:, None]

        if not opens_gap.any():
            return mitre.tolist()

        out: list[list[float]] = []
        for i in range(len(pts)):
            if not opens_gap[i]:
                out.append([float(mitre[i, 0]), float(mitre[i, 1])])
            elif use_round:
                here, a_pt, b_pt = pts[i], pt_in[i], pt_out[i]
                start_deg = math.degrees(math.atan2(a_pt[1] - here[1], a_pt[0] - here[0]))
                end_deg = math.degrees(math.atan2(b_pt[1] - here[1], b_pt[0] - here[0]))
                sweep = (end_deg - start_deg + 180) % 360 - 180
                steps = math.ceil(Path2D._offset_segs(abs(amount), fn, fa, fs) * abs(sweep) / 360) + 1
                theta = np.radians(start_deg + sweep * np.arange(steps) / (steps - 1))
                arc_pts = here + abs(amount) * np.column_stack((np.cos(theta), np.sin(theta)))
                out.extend(arc_pts.tolist())
            elif chamfer:
                bisector = n_in[i] + n_out[i]
                blen = float(np.linalg.norm(bisector))
                if blen < EPSILON:
                    out.append([float(pt_in[i, 0]), float(pt_in[i, 1])])
                    out.append([float(pt_out[i, 0]), float(pt_out[i, 1])])
                else:
                    bisector = bisector / blen
                    cut = pts[i] + bisector * amount
                    for point, direction in (
                        (pt_in[i], u_in[i]),
                        (pt_out[i], u_out[i]),
                    ):
                        diameter = float(direction @ bisector)
                        if abs(diameter) < EPSILON:
                            out.append([float(point[0]), float(point[1])])
                        else:
                            hit = point + direction * (float((cut - point) @ bisector) / diameter)
                            out.append([float(hit[0]), float(hit[1])])
            else:
                out.append([float(mitre[i, 0]), float(mitre[i, 1])])
        return out

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
            return lst[start % sides]
        assert isinstance(start, int), "_path_select(): slice form needs integer start"
        s = start % sides
        e = end % sides
        if s <= e:
            return [lst[i] for i in range(s, e + 1)]
        return [lst[i] for i in range(s, sides)] + [lst[i] for i in range(e + 1)]

    @staticmethod
    def _pair(lst: Sequence[Any] | np.ndarray, wrap: bool = False) -> list[Any]:
        # List of consecutive (lst[i], lst[i+1]) pairs; if wrap, also (last, first).
        length = len(lst) - 1
        if length < 1:
            return []
        out = [(lst[i], lst[i + 1]) for i in range(length)]
        if wrap:
            out.append((lst[length], lst[0]))
        return out

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
    def _repeat(val: Any, sides: int) -> list:
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
            differs = (not np.array_equal(lst[i], nxt)) if eps == 0 else (not approx(lst[i], nxt, eps))
            if differs:
                out.append(lst[i])
        return out

    @staticmethod
    def _polygon_area(poly: Sequence[Sequence[float]] | np.ndarray | "Path2D", signed: bool = False) -> float:
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
    def _point_in_polygon(
        point: Sequence[float] | np.ndarray,
        poly: Sequence[Sequence[float]] | np.ndarray | "Path2D",
        nonzero: bool = False,
        eps: float = EPSILON,
    ) -> int:
        """Whether point is inside 2-D polygon poly: 1 inside, -1 outside, 0 boundary.

        Args:
            point: An [x, y] coordinate to test for containment.
            poly: A sequence of [x, y] points defining the polygon.
            nonzero: If True, use non-zero winding rule instead of even-odd.
            eps: Epsilon for numerical comparisons.
        """
        point = np.asarray(point, dtype=float)
        box = pointlist_bounds(poly)
        if (
            point[0] < box[0][0] - eps
            or point[0] > box[1][0] + eps
            or point[1] < box[0][1] - eps
            or point[1] > box[1][1] + eps
        ):
            return -1

        poly_arr = np.asarray(poly, dtype=float)
        sides = len(poly_arr)
        segs = [(poly_arr[i], poly_arr[(i + 1) % sides]) for i in range(sides)]

        for seg in segs:
            if float(np.linalg.norm(seg[1] - seg[0])) > eps and _is_point_on_segment(point, seg, eps=eps):
                return 0

        if nonzero:
            winding = 0
            for seg in segs:
                p0 = seg[0] - point
                p1 = seg[1] - point
                if float(np.linalg.norm(p1 - p0)) <= eps:
                    continue
                if p0[1] <= 0:
                    if p1[1] > 0 and cross(p0, p1 - p0) > 0:
                        winding += 1
                else:
                    if p1[1] <= 0 and cross(p0, p1 - p0) < 0:
                        winding -= 1
            return 1 if winding != 0 else -1

        crossings = 0
        for seg in segs:
            p0 = seg[0] - point
            p1 = seg[1] - point
            if ((p1[1] > eps and p0[1] <= eps) or (p1[1] <= eps and p0[1] > eps)) and (
                -eps < p0[0] - p0[1] * (p1[0] - p0[0]) / (p1[1] - p0[1])
            ):
                crossings += 1
        return 2 * (crossings % 2) - 1

    @staticmethod
    def _is_closed_path(
        path: Sequence[Sequence[float]] | np.ndarray | "Path2D" | "Path3D", eps: float = EPSILON
    ) -> bool:
        """True if the first and last points of path coincide.

        Args:
            path: A path to check for closure.
            eps: Epsilon for numerical comparison.
        """
        return approx(path[0], path[-1], eps=eps)

    @staticmethod
    def _close_path(path: Sequence[Sequence[float]] | np.ndarray | "Path2D" | "Path3D", eps: float = EPSILON) -> list:
        """Append the start point to path if it isn't already closed.

        Args:
            path: A path to close.
            eps: Epsilon for numerical comparison.
        """
        return list(path) if Path2D._is_closed_path(path, eps=eps) else list(path) + [path[0]]

    @staticmethod
    def _cleanup_path(path: Sequence[Sequence[float]] | np.ndarray | "Path2D" | "Path3D", eps: float = EPSILON) -> list:
        """Drop the last point of path if it coincides with the first.

        Args:
            path: A path to clean up.
            eps: Epsilon for numerical comparison.
        """
        return list(path)[:-1] if Path2D._is_closed_path(path, eps=eps) else list(path)

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
    def _cut_to_seg_u_form(pathcut: list[CutPoint], path: Sequence, closed: bool) -> list:
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
        seg: list[np.ndarray], fragments: list, rightmost: bool = True, eps: float = EPSILON
    ) -> list:
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
            fwdmatch = approx(seg[1], fragment[0], eps=eps)
            bakmatch = approx(seg[1], fragment[-1], eps=eps)
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
        fragments: list,
        rightmost: bool = True,
        startfrag: int = 0,
        eps: float = EPSILON,
    ) -> list:
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
            if Path2D._is_closed_path(path, eps=eps):
                return [path, remainder]
            seg = Path2D._select(path, -2, -1)
            foundfrag, remainder2 = Path2D._extreme_angle_fragment(seg, remainder, rightmost=rightmost, eps=eps)
            if foundfrag is None:
                return [path, remainder2]
            if Path2D._is_closed_path(foundfrag, eps=eps):
                return [foundfrag, [path] + remainder2]
            fragend = foundfrag[-1]
            hits = [i for i in range(len(path) - 1) if approx(path[i], fragend, eps=eps)]
            if hits:
                hitidx = hits[-1]
                newpath = Path2D._list_head(path, hitidx)
                newfrags = ([newpath] if len(newpath) > 1 else []) + remainder2
                outpath = Path2D._slice(path, hitidx, -2) + foundfrag
                return [outpath, newfrags]
            path = path + Path2D._list_tail(foundfrag)
            remainder = remainder2

    @staticmethod
    def _assemble_path_fragments(fragments: list, eps: float = EPSILON) -> list:
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
            l_area = abs(Path2D._polygon_area(result_l[0])) if result_l[0] else 0
            r_area = abs(Path2D._polygon_area(result_r[0])) if result_r[0] else 0
            result = result_l if l_area < r_area else result_r
            newpath = Path2D._cleanup_path(result[0])
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
        from pybosl2.shapes2d import _arc_points, _frag_count

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
        if approx(angle, 90):
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
            assert not approx(angle, 0), f"Path2D turns back on itself at index {i} with nonzero rounding"
            dk.append([parm[i] / math.tan(math.radians(angle)), parm[i]])

        out = []
        for i in range(sides):
            if dk[i][0] == 0:
                out.append(path[i])
                continue
            p0, p1, p2 = path[(i - 1) % sides], path[i], path[(i + 1) % sides]
            out.extend(Path2D._circlecorner([p0, p1, p2], dk[i][0], dk[i][1], fn, fa, fs))
        return Path2D._deduplicate(out, closed=closed)


# ---------------------------------------------------------------------------

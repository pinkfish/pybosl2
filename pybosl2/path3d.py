# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# DocCategory: internal

"""3-D path operations: tangents, normals, curvature, torsion, resampling, cutting, and 3-D transforms.

The :class:`Path3D` class extends :class:`~pybosl2.paths.Path` with 3-D measurements
and transforms while omitting inherently 2-D operations (polygon, area, offset).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Iterator

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import NDArray

    from pybosl2.shapes3d import Bosl2Solid


from pybosl2._helpers import frag_count as _frag_count
from pybosl2._helpers import pick_radius as _pick_radius
from pybosl2.bounds import Bounds3D
from pybosl2.caps import CapSpec, CapType
from pybosl2.distributors import Distributable
from pybosl2.geometry import is_collinear, line_closest_point
from pybosl2.math import EPSILON, deriv, deriv2, deriv3, lerp, lerpn
from pybosl2.miscellaneous import Extrudable
from pybosl2.path2d import Path2D
from pybosl2.paths import (
    CutPoint,
    Path,
    SubdivideMethod,
)
from pybosl2.points import Point
from pybosl2.rounding import Roundable
from pybosl2.skin import Sweepable
from pybosl2.vectors import unit

__all__ = ["Path3D"]


# Section: Path3D object
# ---------------------------------------------------------------------------


class Path3D(Path, Distributable, Extrudable, Sweepable, Roundable):
    """A 3-D path: a list of ``[x, y, z]`` points, with the path operations that make sense in 3-D.

    The 3-D counterpart of :class:`Path2D`. Like ``Path2D``, every method returns
    a NEW object. It carries the dimension-independent measurements (length, segment lengths,
    tangents, :meth:`normals`, curvature, :meth:`torsion`), resampling/subdividing/cutting, and the
    3-D transforms (``translate``/``move``, ``right``/``left``/``back``/``forward``/``up``/``down``,
    ``scale``, ``mirror``, ``rotate``). The inherently-2-D operations of ``Path2D`` (``polygon``,
    ``area``, ``offset``, ``round_corners``, point-in-polygon) are intentionally absent; use
    :meth:`path2d` to drop to the XY plane when you want them.

    Args:
        points: the ``[x, y, z]`` points (anything array-like; numpy scalars are converted to float)
        closed: whether the path is a closed loop -- default False, an open polyline, matching
            BOSL2, where a path is open unless a function is told otherwise. Pass
            ``closed=True`` for a loop: it adds the segment from the last point back to the
            first to the length, the tangents, and anything derived from them.

    Examples:
        A helix resampled to fewer points and swept into a coil:

        .. pythonscad-example::

            from pybosl2.path3d import Path3D

            coil = Path3D.helix(turns=3, height=60, radius=20).resample(num_copies=120)
            coil.stroke(width=4).show()

    """

    def __init__(self, points: Sequence[Sequence[float]] | NDArray[np.float64] = (), closed: bool = False) -> None:
        """Initialize the instance."""
        pts: np.ndarray = np.asarray(points, dtype=np.float64)
        if pts.size == 0:
            self._points: np.ndarray = np.empty((0, 3), dtype=np.float64)
        else:
            assert pts.ndim == 2, f"Path3D needs a list of [x, y, z] points, got {pts.ndim}D array"
            assert pts.shape[1] == 3, f"Path3D needs [x, y, z] points, got shape {pts.shape}"
            assert pts.dtype == np.float64, f"Path3D needs float64 points, got {pts.dtype}"
            self._points = pts
        self.closed = closed

    @classmethod
    def helix(
        cls,
        length: float | None = None,
        height: float | None = None,
        turns: float | None = None,
        angle: float | None = None,
        radius: float | None = None,
        radius1: float | None = None,
        radius2: float | None = None,
        diameter: float | None = None,
        diameter1: float | None = None,
        diameter2: float | None = None,
    ) -> Path3D:
        """Return a 3-D helical path on a (possibly conical) surface -- BOSL2's ``helix()``.

        Returned as a :class:`~pybosl2.paths.Path3D` (the 3-D path object), so it carries the 3-D
        transforms/measurements and feeds straight into stroke or ``path_sweep``. Give
        exactly two of *length*/*height* (length), *turns*, and *angle*; the third is derived. Positive *turns*
        is right-handed, negative left-handed. Start/end radii may differ for a conical helix (a flat
        spiral is ``height=0`` with a turn count).

        Args:
            length: Height of the helix (0 for a flat spiral).
            height: Height of the helix (0 for a flat spiral).
            turns: Number of turns (positive = right-handed).
            angle: Helix angle in degrees (measured at the base radius).
            radius: Radius for a constant-radius helix.
            radius1: Bottom radius.
            radius2: Top radius.
            diameter: Diameter for a constant-radius helix.
            diameter1: Bottom diameter.
            diameter2: Top diameter.

        Examples:
            A 2.5-turn helix drawn as a tube:

            .. pythonscad-example::

                from pybosl2 import Path3D

                Path3D.helix(turns=2.5, height=100, radius=30).stroke(width=3).show()

        """
        r1v = _pick_radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
        r2v = _pick_radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter, dflt=1)
        length = length if length is not None else height
        assert sum(v is not None for v in (length, turns, angle)) == 2, (
            "helix() needs exactly two of length/height, turns, and angle."
        )
        assert angle is None or length != 0, "helix() cannot take an angle with length 0."
        if angle is not None and length != 0:
            dz = 2 * math.pi * r1v * math.tan(math.radians(angle))
        else:
            assert length is not None
            assert turns is not None
            dz = length / abs(turns)
        if turns is not None:
            maxtheta = 360.0 * turns
        else:
            assert length is not None
            maxtheta = 360.0 * length / dz
        nseg = _frag_count(max(r1v, r2v))
        count = max(3, math.ceil(abs(maxtheta) * nseg / 360))
        out: list[list[float]] = []
        for theta in lerpn(0, maxtheta, count):
            radius = lerp(r1v, r2v, theta / maxtheta) if maxtheta != 0 else r1v  # type: ignore[assignment]
            out.append(
                [
                    radius * math.cos(math.radians(theta)),  # type: ignore[operator]
                    radius * math.sin(math.radians(theta)),  # type: ignore[operator]
                    abs(theta) / 360.0 * dz,
                ]
            )
        return cls(out, closed=False)

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
        """The points as an (N, 3) numpy array, for doing your own vectorised maths.

        Returns:
            An (N, 3) float64 numpy array.

        """
        return self._points

    @property
    def to_list(self) -> list[list[float]]:
        """The points as a list of ``[x, y, z]`` plain-Python-float triples.

        Returns:
            A list of ``[x, y, z]`` triples.

        """
        return [list(map(float, p)) for p in self._points.tolist()]

    @classmethod
    def from_list(cls, lst: Sequence[Any], closed: bool = False) -> "Path3D":
        """Create a Path3D from a plain list of ``[x, y, z]`` coordinate triples.

        Args:
            lst: A sequence of ``[x, y, z]`` coordinate triples.
            closed: Whether the path is a closed loop.

        Returns:
            A new :class:`Path3D` instance.

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

              Path3D([[1, 2, 3]]).segment_lengths()               # array([])
              Path3D([[1, 2, 3]], closed=True).segment_lengths()  # array([0.])

          This keeps ``len(segment_lengths(closed=True)) == len(path)``, which
          :meth:`~pybosl2.paths.Path.tangent_array` relies on when it samples the non-uniform
          derivative.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of segment lengths, one per segment.

        """
        if closed is None:
            closed = self.closed
        pts = self._points
        # Counted BEFORE closing the ring: indexing pts[0] to close an EMPTY path raises
        # IndexError rather than reporting no segments.
        if len(pts) < 2:
            return np.zeros(1 if closed and len(pts) == 1 else 0, dtype=np.float64)
        if closed:
            pts = np.vstack([pts, pts[:1]])
        lengths: NDArray[np.float64] = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        return lengths

    def length_fractions(self, closed: bool | None = None) -> NDArray[np.float64]:
        """Distance fraction of each point in the path (0 at start, 1 at end).

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of cumulative length fractions, from 0 to 1.

        """
        if closed is None:
            closed = self.closed
        pts = self._points if not closed else np.vstack([self._points, self._points[0]])
        if len(pts) < 2:
            return np.zeros(len(self._points), dtype=np.float64)
        segs = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        cum = np.concatenate([[0.0], np.cumsum(segs)])
        if closed:
            return cum[:-1] / cum[-1] if cum[-1] > 1e-12 else np.zeros(len(self._points), dtype=np.float64)
        return cum / cum[-1] if cum[-1] > 1e-12 else np.zeros(len(self._points), dtype=np.float64)

    def closest_point(self, pt: Point | Sequence[float], closed: bool | None = None) -> Point:
        """Return the closest point on the path to *pt*.

        Args:
            pt: The query point as :class:`~pybosl2.points.Point` or ``[x, y, z]``.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A :class:`~pybosl2.points.Point` of the closest point on the path.

        """
        if closed is None:
            closed = self.closed
        pts = self._points
        q = np.array([pt.x, pt.y, pt.z]) if isinstance(pt, Point) else np.asarray(pt, dtype=float)
        segs = [
            (
                Point(float(a[0]), float(a[1]), float(a[2])),
                Point(float(b[0]), float(b[1]), float(b[2])),
            )
            for a, b in zip(pts, pts[1:], strict=False)
        ]
        if closed:
            segs.append(
                (
                    Point(float(pts[-1][0]), float(pts[-1][1]), float(pts[-1][2])),
                    Point(float(pts[0][0]), float(pts[0][1]), float(pts[0][2])),
                )
            )
        query = Point(float(q[0]), float(q[1]), float(q[2]))
        projs = [line_closest_point(seg, query) for seg in segs]
        dists = np.linalg.norm(np.asarray(projs, dtype=float) - q, axis=1)
        r = projs[int(np.argmin(dists))]
        return Point(float(r[0]), float(r[1]), float(r[2]))

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
        return [
            Point([float(t[0]), float(t[1]), float(t[2])]) for t in self.tangent_array(closed=closed, uniform=uniform)
        ]

    def normals(self, tangents: "list[Point] | None" = None, closed: bool | None = None) -> "list[Point]":
        """Return normal vector (perpendicular to tangent, in the plane of the curve) at each point.

        For 2-D paths this is a 90-degree rotation of the tangent. For 3-D paths it is the
        principal normal estimated via the triple-product cross.

        Args:
            tangents: Optional pre-computed tangent vectors; computed automatically if None.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A list of unit normal vectors, one per path point.

        """
        if closed is None:
            closed = self.closed
        if tangents is None:
            tangents = self.tangents(closed=closed)
        sides = len(self._points)
        out: list[Point] = []
        pts = self._points
        for i in range(sides):
            if i == 0:
                idx = [-1, 0, 1] if closed else [0, 1, 2]
            elif i == sides - 1:
                idx = [i - 1, i, (i + 1) % sides] if closed else [i - 2, i - 1, i]
            else:
                idx = [i - 1, i, i + 1]
            p = pts[idx]
            ta = np.asarray(tangents[i], dtype=float)
            v = np.cross(np.cross(p[1] - p[0], p[2] - p[0]), ta)
            norm = float(np.linalg.norm(v))
            assert norm > EPSILON, "3D path contains collinear points"
            out.append(Point([float(x) for x in (v / norm)]))
        return out

    def curvature(self, closed: bool | None = None) -> NDArray[np.float64]:
        """Numeric curvature estimate of the path at each point, as an ndarray.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of curvature values, one per path point.

        """
        if closed is None:
            closed = self.closed
        if len(self._points) < 3:
            # deriv() needs two points and curvature/torsion three; without this an empty or
            # near-empty path raises IndexError out of the derivative instead of measuring 0.
            return np.zeros(len(self._points), dtype=np.float64)
        d1 = np.asarray(deriv(self._points, closed=closed), dtype=float)
        d2 = np.asarray(deriv2(self._points, closed=closed), dtype=float)
        n1 = np.linalg.norm(d1, axis=1)
        n2 = np.linalg.norm(d2, axis=1)
        dot = np.einsum("ij,ij->i", d1, d2)
        val = np.clip((n1 * n2) ** 2 - dot**2, 0.0, None)
        return np.sqrt(val) / n1**3  # type: ignore[no-any-return]

    def torsion(self, closed: bool | None = None) -> NDArray[np.float64]:
        """Numeric torsion estimate of the path at each point, as an ndarray.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of torsion values, one per path point.

        """
        if closed is None:
            closed = self.closed
        if len(self._points) < 3:
            # deriv() needs two points and curvature/torsion three; without this an empty or
            # near-empty path raises IndexError out of the derivative instead of measuring 0.
            return np.zeros(len(self._points), dtype=np.float64)
        d1 = np.asarray(deriv(self._points, closed=closed), dtype=float)
        d2 = np.asarray(deriv2(self._points, closed=closed), dtype=float)
        d3 = np.asarray(deriv3(self._points, closed=closed), dtype=float)
        crossterm = np.cross(d1, d2)
        dot = np.einsum("ij,ij->i", crossterm, d3)
        denom = np.einsum("ij,ij->i", crossterm, crossterm)
        return dot / denom  # type: ignore[no-any-return]

    def cut(self, cutdist: float | Sequence[float], closed: bool | None = None) -> list["Path3D"]:
        """Cut path into subpaths at the given ascending list of distances (or a single distance).

        Args:
            cutdist: A single distance or a list of ascending distances from the start.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A list of :class:`Path3D` subpaths.

        Raises:
            AssertionError: If the first cut distance is not positive or the last cut
                distance exceeds the path length.

        Examples:
            Splitting a path into two segments and stroking each:

            .. pythonscad-example::

                from pybosl2 import Path3D

                path3d = Path3D([[0, 0, 0], [30, 0, 0], [30, 20, 0], [0, 20, 0]])
                pieces = path3d.cut(15)
                pieces[0].stroke(width=1).show()

        """
        if closed is None:
            closed = self.closed
        cd = [float(cutdist)] if isinstance(cutdist, (int, float)) else [float(c) for c in cutdist]
        total = self.perimeter()
        assert cd[-1] < total, "Cut distances must be smaller than the path length"
        assert cd[0] > 0, "Cut distances must be strictly positive"
        cutlist: list[CutPoint] = _path_cut_points(self._points, closed, cd)
        sub_paths = _path_cut_getpaths(self._points, closed, cutlist)
        return [self.__class__(pts, closed=self.closed) for pts in sub_paths]  # type: ignore[arg-type]

    def cut_getpaths(self, cutlist: list[CutPoint], closed: bool) -> list["Path3D"]:
        """Reconstruct sub-paths from the output of cut_points().

        Args:
            cutlist: Output from cut_points(), a list of :class:`CutPoint` entries.
            closed: Whether the path is closed.

        Returns:
            A list of :class:`Path3D` subpaths.

        """
        sub_paths = _path_cut_getpaths(self._points, closed, cutlist)
        return [self.__class__(pts, closed=self.closed) for pts in sub_paths]  # type: ignore[arg-type]

    def cut_points(
        self,
        cutdist: float | Sequence[float],
        closed: bool | None = None,
        direction: bool = False,
    ) -> list[CutPoint]:
        """Cut path at given distance(s) from start.

        Returns a list of :class:`CutPoint` entries, with optional direction and normal
        data when *direction* is True.

        Args:
            cutdist: A single distance or a list of ascending distances from the start.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            direction: If True, also include direction and normal at each cut point.

        Returns:
            A list of :class:`CutPoint` entries, one per cut distance.

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

    def cuts_path_normals(self, cuts: list[CutPoint], closed: bool = False) -> "list[Point]":
        """Compute normal vectors at each cut point from the local path geometry.

        For each cut point, the normal is derived from the local plane of three consecutive
        path points. When the points are collinear or a plane cannot be determined, a
        perpendicular vector in the XY plane is used instead.

        Args:
            cuts: List of cut entries from :meth:`cut_points`.
            closed: Whether the path is closed.

        Returns:
            A list of :class:`~pybosl2.points.Vector` normal vectors, one per cut point.

        """
        from pybosl2.vectors import unit

        result: list[Point] = []
        pts = self._points
        n_pts = len(pts)
        for cut in cuts:
            idx = cut.next_index
            a = pts[idx % n_pts]
            b = pts[(idx + 1) % n_pts]
            d = np.asarray(b, float) - np.asarray(a, float)
            nd = float(np.linalg.norm(d)) or 1.0
            tx, ty, tz = d[0] / nd, d[1] / nd, d[2] / nd

            plane = None
            if n_pts >= 3 and closed:
                start = max(min(idx, n_pts - 1), 2)
                try:
                    plane = _path_plane(pts, closed, start, start - 2)
                except ValueError:
                    plane = None
            if plane is None:
                if abs(tx) < 1e-12 and abs(ty) < 1e-12:
                    result.append(Point(1.0, 0.0, 0.0))
                else:
                    n = unit([-ty, tx, 0.0])
                    result.append(Point(float(n[0]), float(n[1]), float(n[2])))
            else:
                n = unit(np.cross([tx, ty, tz], np.cross(plane[0], plane[1])))
                result.append(Point(float(n[0]), float(n[1]), float(n[2])))
        return result

    def plane(self, ind: int, i: int, closed: bool = False) -> "list[Point]":
        """Find the local plane defined by point ind, ind-1, and the nearest non-collinear point.

        Args:
            ind: Index of the first point defining the plane.
            i: Index of the search start for the third non-collinear point.
            closed: Whether the path is closed.

        Returns:
            A list of two :class:`~pybosl2.points.Vector` basis vectors defining the local plane.

        """
        return _path_plane(self._points, closed, ind, i)

    def cuts_dir(self, cuts: list[CutPoint], closed: bool = False, eps: float = 1e-2) -> "list[Point]":
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
        points: int | None = None,
        points_per_segment: Sequence[int] | None = None,
        maxlen: float | None = None,
        exact: bool = True,
        closed: bool | None = None,
        method: SubdivideMethod = SubdivideMethod.LENGTH,
    ) -> "Path3D":
        """Subdivide the path into evenly spaced points.

        Args:
            points: Target total number of points.
            points_per_segment: Number of points to add to each segment index.
            maxlen: Maximum allowed segment length.
            exact: If False, favor uniform sampling — point count may differ.
            closed: Override the instance's closed flag.
            method: ``LENGTH`` (uniform) or ``SEGMENT`` (per segment).

        Returns:
            A new :class:`Path3D` with the subdivided points.

        Raises:
            AssertionError: If more than one of *points*, *points_per_segment*, and *maxlen*
                is given, or if *points_per_segment* is given without ``SEGMENT`` method.

        Examples:
            Subdividing a helix into 200 evenly spaced points and stroking it:

            .. pythonscad-example::

                from pybosl2.path3d import Path3D

                coil = Path3D.helix(turns=3, height=60, radius=20).subdivide_path(points=200)
                coil.stroke(width=4).show()

        """
        if closed is None:
            closed = self.closed
        assert points_per_segment is None or method == SubdivideMethod.SEGMENT, (
            "points_per_segment requires method=SubdivideMethod.SEGMENT"
        )
        method_val = method.value
        pts_arr = self._points
        assert sum(x is not None for x in (points, None, maxlen)) == 1, (
            "Must give exactly one of sides, refine, and maxlen"
        )
        if points == len(pts_arr):
            return self.__class__(list(pts_arr), closed=self.closed)
        if maxlen is not None:
            out: list[Any] = []
            pairs = list(zip(pts_arr, pts_arr[1:], strict=False))
            if closed:
                pairs.append((pts_arr[-1], pts_arr[0]))
            for p0, p1 in pairs:
                steps = math.ceil(math.dist(p1, p0) / maxlen)
                out.extend(lerpn(p0, p1, steps, endpoint=False))
            if not closed:
                out.append(pts_arr[-1])
            return self.__class__(out, closed=self.closed)
        assert isinstance(points, (int, float)), "Parameter sides must be positive number"
        assert points > 0, "Parameter sides must be positive number"
        count = len(pts_arr) - (0 if closed else 1)
        if method_val == "segment":
            add_guess: Any = [(points - len(pts_arr)) / count] * count
        else:
            path_lens = np.linalg.norm(np.diff(pts_arr, axis=0), axis=1)
            if closed:
                path_lens = np.append(path_lens, np.linalg.norm(pts_arr[0] - pts_arr[-1]))
            add_density = (points - len(pts_arr)) / sum(path_lens)
            add_guess = [float(ln * add_density) for ln in path_lens]
        add_list = [float(v) for v in add_guess]
        if exact:
            add = list(add_list)
            err = 0.0
            for i in range(len(add) - 1):
                x = add[i] + err
                newval = math.floor(x + 0.5) if x >= 0 else math.ceil(x - 0.5)
                err = add[i] + err - newval
                add[i] = newval
            lx = add[-1] + err
            add[-1] = math.floor(lx + 0.5) if lx >= 0 else math.ceil(lx - 0.5)
        else:
            add = [math.floor(v + 0.5) if v >= 0 else math.ceil(v - 0.5) for v in add_list]
        out2: list[Any] = []
        for i in range(count):
            out2.extend(lerpn(pts_arr[i], pts_arr[(i + 1) % len(pts_arr)], 1 + int(add[i]), endpoint=False))
        if not closed:
            out2.append(pts_arr[-1])
        return self.__class__(out2, closed=self.closed)

    def resample_path(
        self,
        num_copies: int | None = None,
        spacing: float | None = None,
        closed: bool | None = None,
    ) -> "Path3D":
        """Uniformly resample path to num_copies points, or to a spacing near spacing.

        Args:
            num_copies: Target number of points.
            spacing: Approximate spacing between points.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A new :class:`Path3D` with the uniformly resampled points.

        Raises:
            AssertionError: If both or neither of *num_copies* and *spacing* are given.

        Examples:
            Resampling a helix to 120 evenly spaced points:

            .. pythonscad-example::

                from pybosl2.path3d import Path3D

                coil = Path3D.helix(turns=3, height=60, radius=20).resample_path(num_copies=120)
                coil.stroke(width=4).show()

        """
        if closed is None:
            closed = self.closed
        points = self._points
        assert (num_copies is None) != (spacing is None), "Must define exactly one of num_copies and spacing"
        length = self.perimeter()
        if num_copies is not None:
            n_use = num_copies - (0 if closed else 1)
        else:
            assert spacing is not None
            n_use = round(length / spacing)
        distlist = lerpn(0, length, n_use, endpoint=False)
        cuts = _path_cut_points(points, closed, distlist)  # type: ignore[arg-type]
        pts = [c.point for c in cuts]
        if not closed:
            pts.append(points[-1])
        return self.__class__(pts, closed=self.closed)

    def select(self, s1: int, u1: float, s2: int, u2: float, closed: bool | None = None) -> "Path3D":
        """Extract a portion of the path from one segment to another.

        Returns the sub-path starting at the *u1* fraction of segment *s1* and ending
        at the *u2* fraction of segment *s2*. Segments indices out of range are clamped,
        and partial endpoint fractions include the interpolated point.

        Args:
            s1: Starting segment index.
            u1: Fraction (0 to 1) along the starting segment.
            s2: Ending segment index.
            u2: Fraction (0 to 1) along the ending segment.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A new :class:`Path3D` containing the selected sub-path.

        Examples:
            Selecting the middle portion of a 3-D path:

            .. pythonscad-example::

                from pybosl2 import Path3D

                path3d = Path3D([[0, 0, 0], [30, 0, 0], [30, 20, 0], [0, 20, 0]])
                mid = path3d.select(0, 0.5, 2, 0.5)
                mid.stroke(width=1).show()

        """
        if closed is None:
            closed = self.closed
        points = self._points
        lp = len(points)
        limit = lp - (0 if closed else 1)
        u1c = 0.0 if s1 < 0 else (1.0 if s1 > limit else u1)
        u2c = 0.0 if s2 < 0 else (1.0 if s2 > limit else u2)
        s1c = max(0, min(limit, s1))
        s2c = max(0, min(limit, s2))
        out = []
        if s1c < limit and u1c < 1:
            out.append(lerp(points[s1c], points[(s1c + 1) % lp], u1c))
        out.extend(points[i] for i in range(s1c + 1, s2c + 1))
        if s2c < limit and u2c > 0:
            out.append(lerp(points[s2c], points[(s2c + 1) % lp], u2c))
        return self.__class__(out, closed=self.closed)  # type: ignore[arg-type]

    # -- measurement -----------------------------------------------------------------------

    def bounds(self) -> Bounds3D:
        """Compute the axis-aligned bounding box with pre-computed width, length, and height.

        Returns:
            A :class:`~pybosl2.bounds.Bounds3D` enclosing all path points.

        """
        pts = self._points
        min_pt = pts.min(axis=0)
        max_pt = pts.max(axis=0)
        return Bounds3D(
            float(min_pt[0]),
            float(min_pt[1]),
            float(min_pt[2]),
            float(max_pt[0]),
            float(max_pt[1]),
            float(max_pt[2]),
            float(max_pt[0] - min_pt[0]),
            float(max_pt[1] - min_pt[1]),
            float(max_pt[2] - min_pt[2]),
        )

    def perimeter(self) -> float:
        """Total length along the path.

        Returns:
            The total path length as a float.

        """
        if len(self._points) < 2:
            return 0.0
        diffs = np.diff(self._points, axis=0)
        if self.closed and len(self._points) >= 2:
            diffs = np.vstack([diffs, self._points[0] - self._points[-1]])
        return float(np.sum(np.linalg.norm(diffs, axis=1)))

    def is_closed(self) -> bool:
        """Check whether the first and last points of the path coincide.

        Returns:
            True if the path endpoints are coincident, False otherwise.

        """
        return bool(Path2D._is_closed_path(self._points))

    def close(self) -> "Path3D":
        """Append the start point if the path is not already closed.

        Returns a new Path3D with the first point appended to the end, making
        it a closed loop. Has no effect if already closed.

        Returns:
            A new :class:`Path3D` guaranteed to form a closed loop.

        Examples:
            Closing an open path into a loop:

            .. pythonscad-example::

                from pybosl2 import Path3D

                path3d = Path3D([[0, 0, 0], [30, 0, 0], [30, 20, 0]], closed=False)
                loop = path3d.close()
                loop.stroke(width=1).show()

        """
        return self.__class__(Path2D._close_path(self), closed=self.closed)

    def cleanup(self) -> "Path3D":
        """Drop a duplicate closing point if present.

        If the first and last points coincide this returns a new Path3D with
        the duplicate removed, turning the path into an open one.

        Returns:
            A new :class:`Path3D` with the duplicate end point removed.

        Examples:
            Converting a closed loop to an open path:

            .. pythonscad-example::

                from pybosl2 import Path3D

                path3d = Path3D([[0, 0, 0], [30, 0, 0], [30, 20, 0], [0, 0, 0]])
                result = path3d.cleanup()
                result.stroke(width=1).show()

        """
        return self.__class__(Path2D._cleanup_path(self), closed=self.closed)

    def reverse(self) -> "Path3D":
        """Return the same path wound in the opposite direction.

        Returns a new Path3D with all points in reverse order.

        Returns:
            A new :class:`Path3D` with reversed point order.

        Examples:
            Reversing the direction of a 3-D path:

            .. pythonscad-example::

                from pybosl2 import Path3D

                path3d = Path3D([[0, 0, 0], [30, 0, 0], [30, 20, 0], [0, 20, 0]])
                result = path3d.reverse()
                result.stroke(width=1).show()

        """
        return self.__class__(list(reversed(self._points)), closed=self.closed)

    def merge_collinear(self, closed: bool | None = None, eps: float = 1e-9) -> "Path3D":
        """Remove sequential collinear points and return a new path.

        Args:
            closed: Override the instance's closed flag.
            eps: Epsilon for collinearity comparison.

        Returns:
            A new :class:`Path3D` with collinear points removed.

        Examples:
            Removing a redundant middle point from a straight segment:

            .. pythonscad-example::

                from pybosl2 import Path3D

                path3d = Path3D([[0, 0, 0], [15, 0, 0], [30, 0, 0], [30, 20, 0], [0, 20, 0]])
                result = path3d.merge_collinear()
                result.stroke(width=1).show()

        """
        if closed is None:
            closed = self.closed
        if len(self._points) <= 2:
            return self.__class__(self._points.tolist(), closed=self.closed)
        indices = [0]
        end = len(self._points) - (1 if closed else 2)
        for i in range(1, end + 1):
            pa = Point(
                float(self._points[i - 1][0]),
                float(self._points[i - 1][1]),
                float(self._points[i - 1][2]),
            )
            pb = Point(
                float(self._points[i][0]),
                float(self._points[i][1]),
                float(self._points[i][2]),
            )
            sel = Path2D._select(self._points, i + 1)
            pc = Point(float(sel[0]), float(sel[1]), float(sel[2]))
            if not is_collinear(pa, pb, pc, eps=eps):
                indices.append(i)
        if not closed:
            indices.append(len(self._points) - 1)
        pts = [self._points[i].tolist() for i in indices]
        return self.__class__(pts, closed=self.closed)

    def deduplicate(self, closed: bool | None = None, eps: float = 1e-9) -> "Path3D":
        """Remove duplicate consecutive points and return a new path.

        Args:
            closed: Override the instance's closed flag.
            eps: Epsilon for distance comparison.

        Returns:
            A new :class:`Path3D` with duplicate points removed.

        Examples:
            Cleaning up a path with repeated consecutive points:

            .. pythonscad-example::

                from pybosl2 import Path3D

                path3d = Path3D([[0, 0, 0], [30, 0, 0], [30, 0, 0], [30, 20, 0], [0, 20, 0]])
                result = path3d.deduplicate()
                result.stroke(width=1).show()

        """
        if closed is None:
            closed = self.closed
        pts = Path2D._deduplicate(self._points, closed=closed, eps=eps)
        return self.__class__(pts, closed=self.closed)

    def deduplicated(self) -> "Path3D":
        """Drop consecutive repeated points.

        Returns:
            A new :class:`Path3D` with duplicate points removed.

        """
        return self.__class__(Path2D._deduplicate(self._points, closed=self.closed))

    def subdivide(
        self,
        num_copies: int | None = None,
        refine: float | None = None,
        maxlen: float | None = None,
        exact: bool = True,
        closed: bool | None = None,
    ) -> "Path3D":
        """Insert points along the path.

        Give exactly one of *num_copies*, *refine* or *maxlen*.

        Args:
            num_copies: Target total number of points.
            refine: Multiply the current point count by this.
            maxlen: Cap on the spacing between points.
            exact: Hit the target count exactly rather than approximately.
            closed: Override the instance's closed flag.

        Returns:
            A new :class:`Path3D` with additional interpolated points.

        Examples:
            Subdividing a 3-D path using the num_copies parameter:

            .. pythonscad-example::

                from pybosl2 import Path3D

                path3d = Path3D([[0, 0, 0], [30, 0, 0], [30, 20, 0], [0, 20, 0]])
                result = path3d.subdivide(num_copies=100)
                result.stroke(width=1).show()

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
    ) -> "Path3D":
        """Resample to evenly spaced points.

        Give exactly one of *num_copies* or *spacing*.

        Args:
            num_copies: Target number of points.
            spacing: Approximate spacing between points.
            closed: Override the instance's closed flag.

        Returns:
            A new :class:`Path3D` with uniformly resampled points.

        Examples:
            Resampling a 3-D path to 50 evenly spaced points:

            .. pythonscad-example::

                from pybosl2 import Path3D

                path3d = Path3D([[0, 0, 0], [30, 0, 0], [30, 20, 0], [0, 20, 0]])
                result = path3d.resample(num_copies=50)
                result.stroke(width=1).show()

        """
        return self.resample_path(num_copies=num_copies, spacing=spacing, closed=closed)

    def translate(self, v: Sequence[float]) -> "Path3D":
        """Translate every point by *v* (a shorter vector pads with zeros).

        Args:
            v: A 3-D translation vector ``[dx, dy, dz]``; shorter vectors pad with zeros.

        Returns:
            A new translated :class:`Path3D`.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Path3D

                path3d = Path3D([[0, 0, 0], [30, 0, 0], [30, 20, 0], [0, 20, 0]])
                result = path3d.translate([10, 5, 15])
                result.stroke(width=2).show()

        """
        vv = np.zeros(3)
        va = np.asarray(v, dtype=float)
        vv[: min(3, len(va))] = va[: min(3, len(va))]
        return self.__class__(self._points + vv, closed=self.closed)

    move = translate

    def scale(self, v: "float | Sequence[float]") -> "Path3D":
        """Scale every point by a scalar or a per-axis ``[sx, sy, sz]`` factor.

        Args:
            v: A uniform scalar or a per-axis ``[sx, sy, sz]`` scale factor.

        Returns:
            A new scaled :class:`Path3D`.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Path3D

                path3d = Path3D([[0, 0, 0], [30, 0, 0], [30, 20, 0], [0, 20, 0]])
                result = path3d.scale(2)
                result.stroke(width=2).show()

        """
        s = np.asarray([v, v, v] if isinstance(v, (int, float)) else list(v), dtype=float)
        return self.__class__(self._points * s, closed=self.closed)

    def rotate(self, a: "float | Sequence[float]", v: Sequence[float] | None = None) -> "Path3D":
        """Rotate the points.

        ``rotate(angle, axis)`` spins about *axis*; ``rotate(angle)`` about +Z;
        ``rotate([rx, ry, rz])`` applies the OpenSCAD X-then-Y-then-Z Euler rotation.

        Args:
            a: A single angle in degrees, or ``[rx, ry, rz]`` Euler angles.
            v: An optional rotation axis vector; if None and *a* is scalar, rotates about +Z.

        Returns:
            A new rotated :class:`Path3D`.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Path3D

                path3d = Path3D([[0, 0, 0], [30, 0, 0], [30, 20, 0], [0, 20, 0]])
                result = path3d.rotate(45, v=[0, 0, 1])
                result.stroke(width=2).show()

        """
        from pybosl2.transforms import axis_angle_matrix

        if v is not None:
            m = np.asarray(axis_angle_matrix(float(a), list(v)), dtype=float)  # type: ignore[type-var, arg-type]
        elif isinstance(a, (list, tuple, np.ndarray)):
            rx, ry, rz = (list(a) + [0, 0, 0])[:3]
            mx = np.asarray(axis_angle_matrix(rx, [1, 0, 0]), dtype=float)
            my = np.asarray(axis_angle_matrix(ry, [0, 1, 0]), dtype=float)
            mz = np.asarray(axis_angle_matrix(rz, [0, 0, 1]), dtype=float)
            m = mz @ my @ mx
        else:
            m = np.asarray(axis_angle_matrix(float(a), [0, 0, 1]), dtype=float)  # type: ignore[type-var, arg-type]
        return self.__class__(self._points @ m.T, closed=self.closed)

    rot = rotate

    def mirror(self, v: Sequence[float]) -> "Path3D":
        """Reflect every point across the plane through the origin with normal *v*.

        Args:
            v: The normal vector of the reflection plane through the origin.

        Returns:
            A new mirrored :class:`Path3D`.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Path3D

                path3d = Path3D([[0, 0, 0], [30, 0, 0], [30, 20, 0], [0, 20, 0]])
                result = path3d.mirror([1, 0, 0])
                result.stroke(width=2).show()

        """
        sides = np.asarray(v, dtype=float)
        sides = sides / np.linalg.norm(sides)
        return self.__class__(self._points - 2 * np.outer(self._points @ sides, sides), closed=self.closed)

    def right(self, x: float) -> "Path3D":
        """Translate by *x* along +X.

        Args:
            x: Distance to translate along +X.

        Returns:
            A new :class:`Path3D` shifted right.

        """
        return self.translate([x, 0.0, 0.0])

    def left(self, x: float) -> "Path3D":
        """Translate by *x* along -X.

        Args:
            x: Distance to translate along -X.

        Returns:
            A new :class:`Path3D` shifted left.

        """
        return self.translate([-x, 0.0, 0.0])

    def back(self, y: float) -> "Path3D":
        """Translate by *y* along +Y.

        Args:
            y: Distance to translate along +Y.

        Returns:
            A new :class:`Path3D` shifted back.

        """
        return self.translate([0.0, y, 0.0])

    def forward(self, y: float) -> "Path3D":
        """Translate by *y* along -Y (BOSL2 fwd()).

        Args:
            y: Distance to translate along -Y.

        Returns:
            A new :class:`Path3D` shifted forward.

        """
        return self.translate([0.0, -y, 0.0])

    fwd = forward

    def up(self, z: float) -> "Path3D":
        """Translate by *z* along +Z.

        Args:
            z: Distance to translate along +Z.

        Returns:
            A new :class:`Path3D` shifted up.

        """
        return self.translate([0.0, 0.0, z])

    def down(self, z: float) -> "Path3D":
        """Translate by *z* along -Z.

        Args:
            z: Distance to translate along -Z.

        Returns:
            A new :class:`Path3D` shifted down.

        """
        return self.translate([0.0, 0.0, -z])

    # -- conversion / rendering ------------------------------------------------------------

    def path2d(self) -> "Path2D":
        """Drop the Z coordinate, giving a 2-D :class:`Path2D` (the XY projection).

        Useful when a 3-D sweep path needs 2-D operations like :meth:`~Path2D.contains` or
        :meth:`~Path2D.polygon`.

        Examples:
            .. pythonscad-example::

                from pybosl2.path3d import Path3D

                sweep_path = Path3D.helix(turns=3, height=60, radius=20)
                flat = sweep_path.path2d()
                flat.stroke(width=2).linear_extrude(height=1).show()

        """
        return Path2D(self._points[:, :2].tolist(), closed=self.closed)

    # -- distributors (pybosl2/distributors.py) ----------------------------------------------

    def stroke(
        self,
        width: float = 1,
        closed: bool | None = None,
        endcaps: CapType | CapSpec = CapType.ROUND,
        endcap1: CapType | CapSpec | None = None,
        endcap2: CapType | CapSpec | None = None,
        joints: CapType | CapSpec = CapType.ROUND,  # noqa: ARG002
    ) -> "Bosl2Solid":
        """Render this 3-D path as a solid tube.

        Converts the path into a tubular 3-D solid with the given width, using
        rounded endcaps and joints by default.

        Args:
            width: Thickness of the tube.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            endcaps: Cap style for both ends (unused when explicit endcaps are given).
            endcap1: Cap style for the start of the path.
            endcap2: Cap style for the end of the path.
            joints: Joint style between segments (unused when explicit endcaps are given).

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid` representing the tubular stroke.

        Examples:
            A simple path stroked as a tube:

            .. pythonscad-example::

                from pybosl2 import Path3D

                path3d = Path3D([[0, 0, 0], [30, 0, 0], [30, 20, 10], [0, 20, 0]])
                path3d.stroke(width=2).show()

        """
        from pybosl2._backend import current_backend
        from pybosl2.caps import CapSpec, normalize_one

        ec1_raw = endcap1 if endcap1 is not None else endcaps
        ec2_raw = endcap2 if endcap2 is not None else endcaps
        ec1 = ec1_raw if isinstance(ec1_raw, CapSpec) else normalize_one(ec1_raw)
        ec2 = ec2_raw if isinstance(ec2_raw, CapSpec) else normalize_one(ec2_raw)

        backend_name = current_backend()
        if backend_name != "csg":
            from pybosl2._backend import get_backend

            return get_backend().stroke(  # type: ignore[return-value]
                self,
                width=width,
                closed=self.closed if closed is None else closed,
                endcap1=ec1,
                endcap2=ec2,
            )

        from pybosl2._stroke3d import stroke_3d

        return stroke_3d(
            self,
            width=width,
            closed=self.closed if closed is None else closed,
            endcap1=ec1,
            endcap2=ec2,
        )

    def dashed_stroke(
        self,
        dashpat: Sequence[float] | None = None,
        closed: bool | None = None,
        fit: bool = True,
        mindash: float = 0.5,
    ) -> "Bosl2Solid":
        """Render this 3-D path as dashed tube segments, unioned together.

        Breaks the path into individual solid dashes based on the given dash pattern.

        Args:
            dashpat: Alternating dash/gap lengths. Defaults to ``[3, 2]`` (3-unit dashes,
                2-unit gaps) when None.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            fit: If True, adjust the pattern so dashes fit evenly along the path.
            mindash: Minimum dash length when *fit* is True.

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid` of unioned dash segments.

        Examples:
            A dashed stroke along a 3-D path:

            .. pythonscad-example::

                from pybosl2 import Path3D

                path3d = Path3D([[0, 0, 0], [30, 0, 0], [30, 20, 10], [0, 20, 0]])
                path3d.dashed_stroke(dashpat=[5, 2]).show()

        """
        from pybosl2._stroke3d import dashed_stroke_3d

        return dashed_stroke_3d(
            self, dashpat=dashpat, closed=self.closed if closed is None else closed, fit=fit, mindash=mindash
        )

    def _distribute(self, mats: list[np.ndarray]) -> list["Path3D"]:  # type: ignore[override]
        # Apply each copier matrix, returning the list of 3-D copies (BOSL2's function form).
        if not len(self):
            return [self.__class__([], closed=self.closed) for _ in mats]
        results = []
        for m in mats:
            mat = np.asarray(m, dtype=float)
            homo = np.hstack([self._points, np.ones((len(self._points), 1))])
            tr = (mat @ homo.T).T
            w = tr[:, 3:4]
            pts = tr[:, :3] / np.where(w == 0, 1.0, w)
            results.append(self.__class__(pts, closed=self.closed))
        return results

    def __repr__(self) -> str:
        """Return a string representation."""
        return f"Path3D({len(self)} pts, closed={self.closed})"


# Section: Path helper functions
# ---------------------------------------------------------------------------


# -- Path2D Geometry ---------------------------------------------------------------------


def _path_cut_getpaths(points: np.ndarray, closed: bool, cutlist: list[CutPoint]) -> list[list[float]]:
    """Reconstruct sub-paths from the output of path_path_cut_points().

    Args:
        points: The path point array.
        cutlist: Output from path_path_cut_points(), a list of :class:`CutPoint` entries.
        closed: Whether the path is closed.

    Returns:
        A list of subpath point lists.

    """
    cuts = len(cutlist)
    result = []
    seg0 = list(points[: cutlist[0].next_index])
    if not np.allclose(cutlist[0].point, points[cutlist[0].next_index - 1], rtol=0, atol=EPSILON):
        seg0.append(cutlist[0].point)
    result.append(seg0)
    for i in range(cuts - 1):
        if (
            np.array_equal(cutlist[i].point, cutlist[i + 1].point)
            and cutlist[i].next_index == cutlist[i + 1].next_index
        ):
            result.append([])
            continue
        seg = []
        if not np.allclose(cutlist[i].point, points[(cutlist[i].next_index) % len(points)], rtol=0, atol=EPSILON):
            seg.append(cutlist[i].point)
        seg.extend(points[cutlist[i].next_index : cutlist[i + 1].next_index])
        if not np.allclose(
            cutlist[i + 1].point,
            points[(cutlist[i + 1].next_index - 1) % len(points)],
            rtol=0,
            atol=EPSILON,
        ):
            seg.append(cutlist[i + 1].point)
        result.append(seg)
    last_seg = []
    if not np.allclose(
        cutlist[cuts - 1].point,
        points[(cutlist[cuts - 1].next_index) % len(points)],
        rtol=0,
        atol=EPSILON,
    ):
        last_seg.append(cutlist[cuts - 1].point)
    n = len(points)
    a = cutlist[cuts - 1].next_index % n
    if closed:
        e = 0
        if a <= e:
            last_seg.extend([points[i] for i in range(a, e + 1)])
        else:
            last_seg.extend([points[i] for i in range(a, n)] + [points[i] for i in range(e + 1)])
    else:
        last_seg.extend(points[a:])
    result.append(last_seg)
    return result


def _path_cut_points(
    points: np.ndarray, closed: bool, cutdist: float | Sequence[float], direction: bool = False
) -> list[CutPoint]:
    """Cut path at given distance(s) from start.

    Returns a list of :class:`CutPoint` entries (or :class:`` if direction is True).

    Args:
        points: The path point array.
        cutdist: A single distance or a list of ascending distances from the start.
        closed: Override the instance's closed flag; uses ``self.closed`` by default.
        direction: If True, also include direction and normal at each cut point.

    Returns:
        A list of :class:`CutPoint` or :class:`` entries, one per cut distance.

    """
    long_enough = len(points) >= (3 if closed else 2)
    assert long_enough, (
        "Two points needed to define a path" if len(points) < 2 else "Closed path must include three points"
    )
    if isinstance(cutdist, (int, float, np.floating, np.integer)):
        return _path_cut_points(points, closed, [cutdist], direction)
    assert isinstance(cutdist, (list, tuple, np.ndarray))
    assert all(cutdist[i] < cutdist[i + 1] for i in range(len(cutdist) - 1)), "Cut distances must be an increasing list"
    cuts: list[CutPoint] = _path_cut_points_recurse(points, closed, [float(v) for v in cutdist])
    if not direction:
        return cuts
    dirs = _path_cuts_dir(points, closed, cuts)
    normals: list[Point] = []
    for i in range(len(cuts)):
        plane: list[Point] | None = None
        if len(points) >= 3:
            start = max(min(cuts[i].next_index, len(points) - 1), 2)
            try:
                plane = _path_plane(points, closed, start, start - 2)
            except ValueError:
                plane = None
        if plane is None:
            if dirs[i][0] == 0 and dirs[i][1] == 0:
                normals.append(Point([1, 0, 0]))
            else:
                n = unit([-dirs[i][1], dirs[i][0], 0])
                normals.append(Point([float(n[0]), float(n[1]), float(n[2])]))
        else:
            n = unit(np.cross(dirs[i], np.cross(plane[0], plane[1])))
            normals.append(Point([float(n[0]), float(n[1]), float(n[2])]))
    return [
        CutPoint(
            point=cuts[i].point,
            next_index=cuts[i].next_index,
            direction=np.asarray(dirs[i], dtype=float),
            normal=np.asarray(normals[i], dtype=float),
        )
        for i in range(len(cuts))
    ]


def _path_cut_points_recurse(points: np.ndarray, closed: bool, dists: Sequence[float]) -> list[CutPoint]:
    """Walk the path accumulating distance until each cut distance is reached.

    Args:
        points: The path point array.
        dists: Ordered list of distances from the start at which to cut.
        closed: Whether the path is closed.

    Returns:
        A list of :class:`CutPoint` entries, one per cut distance.

    """
    result: list[CutPoint] = []
    pind = 0
    dtotal = 0.0
    for dind in range(len(dists)):
        lastpt: Point | list[float] = [] if len(result) == 0 else result[-1].point
        dpartial = 0.0 if len(result) == 0 else math.dist(lastpt, points[(pind) % len(points)])
        if dists[dind] < dpartial + dtotal:
            t = (dists[dind] - dtotal) / dpartial
            a_arr = np.asarray(lerp(lastpt, points[pind % len(points)], t), dtype=float)
            nextpoint = CutPoint(point=Point(float(a_arr[0]), float(a_arr[1]), float(a_arr[2])), next_index=pind)
        else:
            nextpoint = _path_cut_single(points, closed, dists[dind] - dtotal - dpartial, pind)
        result.append(nextpoint)
        dtotal = dists[dind]
        pind = nextpoint.next_index
    return result


def _path_cut_single(points: np.ndarray, closed: bool, dist: float, ind: int = 0, eps: float = 1e-7) -> CutPoint:
    """Find the single cut point at distance dist from segment ind.

    Args:
        points: The path point array.
        dist: Distance along the path from the given segment index.
        closed: Whether the path is closed.
        ind: The segment index to start searching from.
        eps: Epsilon for distance comparison.

    Returns:
        A :class:`CutPoint` with the cut point and its next segment index.

    """
    while True:
        if ind == len(points) - (0 if closed else 1):
            assert dist < eps, "Path2D is too short for specified cut distance"
            pt_arr = np.asarray(points[(ind) % len(points)], dtype=float)
            return CutPoint(
                point=Point(float(pt_arr[0]), float(pt_arr[1]), float(pt_arr[2])),
                next_index=ind + 1,
            )
        diameter = math.dist(points[ind], points[(ind + 1) % len(points)])
        if diameter > dist:
            return CutPoint(
                point=Point(
                    *[
                        float(v)
                        for v in np.asarray(
                            lerp(points[ind], points[(ind + 1) % len(points)], dist / diameter), dtype=float
                        )[:3]
                    ]
                ),
                next_index=ind + 1,
            )
        dist -= diameter
        ind += 1


def _path_plane(points: np.ndarray, closed: bool, ind: int, i: int) -> list[Point]:
    """Find the local plane defined by point ind, ind-1, and the nearest non-collinear point.

    Args:
        points: The path point array.
        ind: Index of the first point defining the plane.
        i: Index of the search start for the third non-collinear point.
        closed: Whether the path is closed.

    Returns:
        A list of two :class:`Vector` basis vectors defining the local plane.

    Raises:
        ValueError: If no non-collinear point is found within the search range.

    """
    lower = -1 if closed else 0
    while i >= lower:
        pa = Point(float(points[ind][0]), float(points[ind][1]), float(points[ind][2]))
        pb = Point(float(points[ind - 1][0]), float(points[ind - 1][1]), float(points[ind - 1][2]))
        j = (i) % len(points)
        pc = Point(float(points[j][0]), float(points[j][1]), float(points[j][2]))
        if not is_collinear(pa, pb, pc):
            p_i = points[(i) % len(points)]
            return [
                Point([float(a - b) for a, b in zip(p_i, points[ind - 1], strict=False)]),
                Point([float(a - b) for a, b in zip(points[ind], points[ind - 1], strict=False)]),
            ]
        i -= 1
    raise ValueError("No non-collinear point found to define a local plane.")


def _path_cuts_dir(points: np.ndarray, closed: bool, cuts: list[CutPoint], eps: float = 1e-2) -> list[Point]:
    """Compute direction vectors at each cut point (blended from adjacent segments).

    Args:
        points: The path point array.
        cuts: List of cut entries from path_path_cut_points().
        closed: Whether the path is closed.
        eps: Epsilon for numerical comparisons.

    Returns:
        A list of :class:`Vector` direction vectors, one per cut point.

    """
    out: list[Point] = []
    zeros = [0] * points.shape[1]
    for ci in range(len(cuts)):
        nextind = cuts[ci].next_index
        nextpath = unit(
            [
                a - b
                for a, b in zip(
                    points[(nextind + 1) % len(points)],
                    points[(nextind) % len(points)],
                    strict=False,
                )
            ],
            zeros,
        )
        thispath = unit(
            [
                a - b
                for a, b in zip(
                    points[(nextind) % len(points)],
                    points[(nextind - 1) % len(points)],
                    strict=False,
                )
            ],
            zeros,
        )
        lastpath = unit(
            [
                a - b
                for a, b in zip(
                    points[(nextind - 1) % len(points)],
                    points[(nextind - 2) % len(points)],
                    strict=False,
                )
            ],
            zeros,
        )
        if nextind == len(points) and not closed:
            nextdir = lastpath
        elif (nextind <= len(points) - 2 or closed) and np.allclose(
            cuts[ci].point, points[(nextind) % len(points)], rtol=0, atol=eps
        ):
            nextdir = unit([a + b for a, b in zip(nextpath, thispath, strict=False)])
        elif (nextind > 1 or closed) and np.allclose(
            cuts[ci].point, points[(nextind - 1) % len(points)], rtol=0, atol=eps
        ):
            nextdir = unit([a + b for a, b in zip(thispath, lastpath, strict=False)])
        else:
            nextdir = thispath
        out.append(Point([float(v) for v in nextdir]))
    return out


# -- Resampling -- changing the number of points in a path -----------------------------

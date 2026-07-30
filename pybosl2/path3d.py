# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""3-D path operations: tangents, normals, curvature, torsion, resampling, cutting, and 3-D transforms.

The :class:`Path3D` class extends :class:`~pybosl2.paths.Path` with 3-D measurements
and transforms while omitting inherently 2-D operations (polygon, area, offset).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import NDArray

    from pybosl2.points import Point, Vector


from pybosl2.bounds import Bounds3D
from pybosl2.caps import CapSpec, CapType
from pybosl2.distributors import Distributable, _apply4
from pybosl2.math import lerp, lerpn
from pybosl2.miscellaneous import Extrudable
from pybosl2.path2d import Path2D
from pybosl2.paths import (
    CutPoint,
    Path,
    _path_closest_point,
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
    _path_segment_lengths,
    _path_select,
    _path_tangents,
    _path_torsion,
    _path_total_length,
    _resample_path,
    _subdivide_path,
)
from pybosl2.rounding import Roundable
from pybosl2.shapes2d import _frag_count, _pick_radius
from pybosl2.skin import Sweepable

__all__ = ["Path3D", "helix"]


def helix(
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
    """A 3-D helical path on a (possibly conical) surface -- BOSL2's ``helix()``.

    Returned as a :class:`~pybosl2.paths.Path3D` (the 3-D path object), so it carries the 3-D
    transforms/measurements and feeds straight into :func:`stroke` or ``path_sweep``. Give
    exactly two of *length*/*height* (length), *turns*, and *angle*; the third is derived. Positive *turns*
    is right-handed, negative left-handed. Start/end radii may differ for a conical helix (a flat
    spiral is ``height=0`` with a turn count).

    Args:
        length/height:     height of the helix (0 for a flat spiral)
        turns:   number of turns (positive = right-handed)
        angle:   helix angle in degrees (measured at the base radius)
        radius/diameter:     radius / diameter (constant helix)
        radius1/diameter1:   bottom radius / diameter
        radius2/diameter2:   top radius / diameter

    Examples:
        A 2.5-turn helix drawn as a tube:

        .. pythonscad-example::

            stroke(helix(turns=2.5, height=100, radius=30), width=3).show()
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
        assert length is not None and turns is not None  # else-branch only reached with both set
        dz = length / abs(turns)
    if turns is not None:
        maxtheta = 360.0 * turns
    else:
        assert length is not None
        maxtheta = 360.0 * length / dz
    nseg = _frag_count(max(r1v, r2v))
    count = max(3, math.ceil(abs(maxtheta) * nseg / 360))
    out = []
    for theta in lerpn(0, maxtheta, count):
        radius = lerp(r1v, r2v, theta / maxtheta) if maxtheta != 0 else r1v
        out.append(
            [
                radius * math.cos(math.radians(theta)),
                radius * math.sin(math.radians(theta)),
                abs(theta) / 360.0 * dz,
            ]
        )
    return Path3D(out, closed=False)


# --- turtle ----------------------------------------------------------------

_TURTLE_TWO_ARG = ("arcleft", "arcright", "arcleftto", "arcrightto")


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
        closed: whether the path is a closed loop (default True)

    Examples:
        A helix resampled to fewer points and swept into a coil:

        .. pythonscad-example::

            coil = helix(turns=3, height=60, radius=20).resample(sides=120)
            coil.stroke(width=4).show()
    """

    def __init__(self, points: Sequence[Sequence[float]] | NDArray[np.float64] = (), closed: bool = True) -> None:
        pts: np.ndarray = np.asarray(points, dtype=np.float64)
        if pts.size == 0:
            self._points: np.ndarray = np.empty((0, 3), dtype=np.float64)
        else:
            assert pts.ndim == 2, f"Path3D needs a list of [x, y, z] points, got {pts.ndim}D array"
            assert pts.shape[1] == 3, f"Path3D needs [x, y, z] points, got shape {pts.shape}"
            assert pts.dtype == np.float64, f"Path3D needs float64 points, got {pts.dtype}"
            self._points = pts
        self.closed = closed

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
        """The points as an (N, 3) numpy array, for doing your own vectorised maths."""
        return self._points

    @property
    def to_list(self) -> list[list[float]]:
        """The points as a list of ``[x, y, z]`` plain-Python-float triples."""
        return self._points.tolist()

    @classmethod
    def from_list(cls, lst: Sequence, closed: bool = True) -> "Path3D":
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

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of segment lengths.
        """
        if closed is None:
            closed = self.closed
        return _path_segment_lengths(self._points, closed)

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

        Args:
            pt: The query point as :class:`~pybosl2.points.Point` or ``[x, y, z]``.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A :class:`~pybosl2.points.Point` of the closest point on the path.
        """
        if closed is None:
            closed = self.closed
        return _path_closest_point(self._points, closed, pt)

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

    def cut(self, cutdist: float | Sequence[float], closed: bool | None = None) -> list["Path3D"]:
        """Cut path into subpaths at the given ascending list of distances (or a single distance).

        Args:
            cutdist: A single distance or a list of ascending distances from the start.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A list of :class:`Path3D` subpaths.
        """
        if closed is None:
            closed = self.closed
        sub_paths = _path_cut(self._points, closed, cutdist)
        return [self.__class__(pts, closed=self.closed) for pts in sub_paths]

    def cut_getpaths(self, cutlist: list[CutPoint], closed: bool) -> list["Path3D"]:
        """Reconstruct sub-paths from the output of cut_points().

        Args:
            cutlist: Output from cut_points(), a list of :class:`CutPoint` entries.
            closed: Whether the path is closed.

        Returns:
            A list of :class:`Path3D` subpaths.
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

    def plane(self, ind: int, i: int, closed: bool = False) -> "list[Vector]":
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
    ) -> "Path3D":
        """Subdivide path to produce a more finely sampled path; see BOSL2 subdivide_path().

        Args:
            sides: Target number of points.
            refine: Multiplier for point count.
            maxlen: Maximum segment length.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            exact: If True, use sum-preserving rounding.
            method: "length" or "segment".

        Returns:
            A new :class:`Path3D` with the subdivided points.
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
    ) -> "Path3D":
        """Uniformly resample path to sides points, or to a spacing near spacing.

        Args:
            sides: Target number of points.
            spacing: Approximate spacing between points.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A new :class:`Path3D` with the uniformly resampled points.
        """
        if closed is None:
            closed = self.closed
        pts = _resample_path(self._points, closed, sides=sides, spacing=spacing)
        return self.__class__(pts, closed=self.closed)

    def select(self, s1: int, u1: float, s2: int, u2: float, closed: bool | None = None) -> "Path3D":
        """Portion of path from the u1 fraction of segment s1 to the u2 fraction of segment s2.

        Args:
            s1: Starting segment index.
            u1: Fraction along segment s1 (0 to 1).
            s2: Ending segment index.
            u2: Fraction along segment s2 (0 to 1).
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A :class:`Path3D` representing the selected portion of the path.
        """
        if closed is None:
            closed = self.closed
        pts = _path_select(self._points, closed, s1, u1, s2, u2)
        return self.__class__(pts, closed=self.closed)

    # -- measurement -----------------------------------------------------------------------

    def bounds(self) -> Bounds3D:
        """Axis-aligned bounding box with pre-computed width, length, and height."""
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
        """Total length along the path."""
        return _path_total_length(self._points, self.closed)

    @property
    def length(self) -> float:
        """Total length around the path (alias for :meth:`perimeter`)."""
        return self.perimeter()

    def is_closed(self) -> bool:
        """True if the first and last points of the path coincide."""
        return bool(Path2D._is_closed_path(self._points))

    def close(self) -> "Path3D":
        """Append the start point if the path is not already closed.

        Returns a new Path3D with the first point appended to the end, making
        it a closed loop. Has no effect if already closed.
        """
        return self.__class__(Path2D._close_path(self), closed=self.closed)

    def cleanup(self) -> "Path3D":
        """Drop a duplicate closing point if present.

        If the first and last points coincide this returns a new Path3D with
        the duplicate removed, turning the path into an open one.
        """
        return self.__class__(Path2D._cleanup_path(self), closed=self.closed)

    def reverse(self) -> "Path3D":
        """The same path wound the other way.

        Returns a new Path3D with all points in reverse order.
        """
        return self.__class__(list(reversed(self._points)), closed=self.closed)

    def deduplicated(self) -> "Path3D":
        """Drop consecutive repeated points."""
        return self.__class__(Path2D._deduplicate(self._points, closed=self.closed))

    def subdivide(self, **kwargs: Any) -> "Path3D":
        """Insert points along the path.

        Args:
            **kwargs: Passed through to the subdivide kernel; must include exactly one of
                *sides* (target count), *refine* (multiplier), or *maxlen* (spacing cap).

        Returns:
            A new :class:`Path3D` with additional interpolated points.
        """
        return self.subdivide_path(**kwargs)

    def resample(self, **kwargs: Any) -> "Path3D":
        """Resample to evenly spaced points.

        Args:
            **kwargs: Must include exactly one of *sides* or *spacing*.

        Returns:
            A new :class:`Path3D` with uniformly resampled points.
        """
        return self.resample_path(**kwargs)

    def translate(self, v: Sequence[float]) -> "Path3D":
        """Translate every point by *v* (a shorter vector pads with zeros).

        Args:
            v: A 3-D translation vector ``[dx, dy, dz]``; shorter vectors pad with zeros.

        Returns:
            A new translated :class:`Path3D`.

        Examples:
            .. pythonscad-example::

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

                path3d = Path3D([[0, 0, 0], [30, 0, 0], [30, 20, 0], [0, 20, 0]])
                result = path3d.scale(2)
                result.stroke(width=2).show()
        """
        s = np.asarray([v, v, v] if isinstance(v, (int, float)) else list(v), dtype=float)
        return self.__class__(self._points * s, closed=self.closed)

    def rotate(self, a: "float | Sequence[float]", v: Sequence[float] | None = None) -> "Path3D":
        """Rotate the points. ``rotate(angle, axis)`` spins about *axis*; ``rotate(angle)`` about +Z;

        ``rotate([rx, ry, rz])`` applies the OpenSCAD X-then-Y-then-Z Euler rotation.

        Args:
            a: A single angle in degrees, or ``[rx, ry, rz]`` Euler angles.
            v: An optional rotation axis vector; if None and *a* is scalar, rotates about +Z.

        Returns:
            A new rotated :class:`Path3D`.

        Examples:
            .. pythonscad-example::

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

                sweep_path = helix(turns=3, height=60, radius=20)
                flat = sweep_path.path2d()
                flat.stroke(width=2).linear_extrude(h=1).show()
        """
        return Path2D(self._points[:, :2].tolist(), closed=self.closed)

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
        """Draw this 3-D path as a solid tube of the given *width*.

        Delegates to :func:`pybosl2.drawing.stroke`.

        Args:
            width: The tube diameter.
            closed: Override the path's closed setting; uses the path's own if None.
            endcaps: Cap style for both ends (``endcap1``/``endcap2`` override).
            endcap1: Cap style for the start of the path.
            endcap2: Cap style for the end of the path.
            joints: Style for interior corners (default ``ROUND``).
            dots: If True, mark every vertex with a round dot.
            color: Optional colour applied to the whole stroke.

        Returns:
            A 3-D geometry object from the stroke operation.

        Examples:
            .. pythonscad-example::

                coil = helix(turns=3, height=60, radius=20).resample(sides=120)
                coil.stroke(width=4).show()
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
        """Break this 3-D path into dash sub-paths (see :func:`pybosl2.drawing.dashed_stroke`).

        Args:
            dashpat: Sequence of dash/gap lengths alternating.
            closed: Override the path's closed setting; uses the path's own if None.
            fit: Scale the pattern to fit a whole number of repeats.
            mindash: Drop a trailing dash shorter than this.

        Returns:
            A list of :class:`Path2D` or :class:`Path3D` sub-paths representing the dashes.
        """
        from pybosl2.drawing import dashed_stroke as _dashed

        return _dashed(
            self,
            dashpat=dashpat,
            closed=self.closed if closed is None else closed,
            fit=fit,
            mindash=mindash,
        )

    # -- distributors (pybosl2/distributors.py) ----------------------------------------------

    def _distribute(self, mats: list[np.ndarray]) -> list["Path3D"]:
        # Apply each copier matrix, returning the list of 3-D copies (BOSL2's function form).
        if not len(self):
            return [self.__class__([], closed=self.closed) for _ in mats]
        return [self.__class__(_apply4(m, self._points), closed=self.closed) for m in mats]

    def __repr__(self) -> str:
        return f"Path3D({len(self)} pts, closed={self.closed})"

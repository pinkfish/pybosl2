# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Operations on 2-D and 3-D paths: length, resampling, tangents/normals/curvature/torsion, cutting and splitting.

Pure-Python port of BOSL2's paths.scad. Every path operation lives on the :class:`Path2D` class --
there are no module-level path functions. The public ergonomic API is instance methods/properties
(``Path2D(pts).offset(...)``, ``path.is_closed``); the numeric kernels and graph algorithms are
private instance methods that operate on ``self._points``.

Dimension-agnostic path-math functions (length, tangents, normals, curvature, torsion,
closest-point, cutting, resampling) live on :class:`Path`, shared by both :class:`Path2D`
and :class:`Path3D`. They use vectorised numpy operations over ``self._points``.

The :class:`Path3D` class extends these operations to 3-D paths, carrying the dimension-independent
measurements (length, tangents, normals, curvature, torsion), resampling/cutting, and 3-D transforms
while omitting inherently 2-D operations like polygon/area/offset.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:  # for the annotations only -- shapes2d/shapes3d import this module
    from collections.abc import Sequence

    from numpy.typing import NDArray


from pybosl2.comparisons import approx
from pybosl2.geometry import (
    cross,
    is_collinear,
    line_closest_point,
)
from pybosl2.math import EPSILON, deriv, deriv2, deriv3, lerp, lerpn
from pybosl2.points import Point, Vector
from pybosl2.vectors import add_scalar, unit

__all__ = ["CutPoint", "Path"]

# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# CutPoint — result of path cut operations
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CutPoint:
    """A point along a path where it was cut, with the index of the next segment.

    Returned by :meth:`~pybosl2.path2d.Path2D.cut_points` and related methods.
    When requested with ``direction=True``, the *direction* and *normal*
    attributes are populated; otherwise they are ``None``.

    Attributes:
        point: The (x, y) or (x, y, z) coordinates of the cut point.
        next_index: The 0-based index of the next point in the original path.
        direction: Unit tangent vector at the cut point, or None.
        normal: Unit normal vector at the cut point, or None.
    """

    point: Point
    next_index: int
    direction: np.ndarray | None = None
    normal: np.ndarray | None = None

    @property
    def is_directed(self) -> bool:
        """True if direction and normal vectors are present."""
        return self.direction is not None and self.normal is not None


# Section: Path helper functions
# ---------------------------------------------------------------------------


def _path_total_length(points: np.ndarray, closed: bool) -> float:
    """Total length of the path.

    Args:
        closed: Override the instance's closed flag; uses ``self.closed`` by default.

    Returns:
        The total path length as a float.
    """
    if len(points) < 2:
        return 0.0
    total = float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())
    if closed:
        total += float(np.linalg.norm(points[-1] - points[0]))
    return total


def _path_segment_lengths(points: np.ndarray, closed: bool) -> NDArray[np.float64]:
    """Length of each segment of the path, as an ndarray.

    Args:
        closed: Override the instance's closed flag; uses ``self.closed`` by default.

    Returns:
        An ndarray of segment lengths.
    """
    lens = np.linalg.norm(np.diff(points, axis=0), axis=1)
    if closed:
        lens = np.append(lens, np.linalg.norm(points[0] - points[-1]))
    return lens  # type: ignore[return-value]


def _path_length_fractions(points: np.ndarray, closed: bool) -> NDArray[np.float64]:
    """Distance fraction of each point in the path (0 at start, 1 at end).

    Args:
        closed: Override the instance's closed flag; uses ``self.closed`` by default.

    Returns:
        An ndarray of cumulative length fractions, from 0 to 1.
    """
    lengths = np.concatenate(([0.0], _path_segment_lengths(points, closed)))
    partial = np.cumsum(lengths)
    total = partial[-1]
    return partial / total


# -- Path2D Geometry ---------------------------------------------------------------------


def _path_closest_point(points: np.ndarray, closed: bool, pt: Point | Sequence[float]) -> Point:
    """The closest point on the path to *pt*.

    Args:
        pt: The query point as :class:`~pybosl2.points.Point` or ``[x, y, z]``.
        closed: Override the instance's closed flag; uses ``self.closed`` by default.

    Returns:
        A :class:`~pybosl2.points.Point` of the closest point on the path.
    """
    if isinstance(pt, Point):
        q = np.array([pt.x, pt.y]) if pt.is_2d else np.array([pt.x, pt.y, pt.z])
    else:
        q = np.asarray(pt, dtype=float)
    pts = [line_closest_point(seg, q) for seg in _pair(points, closed)]
    dists = np.linalg.norm(np.asarray(pts, dtype=float) - q, axis=1)
    min_seg = int(np.argmin(dists))
    r = pts[min_seg]
    dim = points.shape[1]
    return Point(float(r[0]), float(r[1])) if dim == 2 else Point(float(r[0]), float(r[1]), float(r[2]))


def _path_tangents(points: np.ndarray, closed: bool, uniform: bool = True) -> list[Vector]:
    """Normalized tangent vector at each point of the path.

    Args:
        closed: Override the instance's closed flag; uses ``self.closed`` by default.
        uniform: If True, use uniform parameter spacing; if False, weight by segment lengths.

    Returns:
        A list of :class:`Vector` unit tangent vectors, one per path point.
    """
    if not uniform:
        diameter = np.asarray(
            deriv(points, closed=closed, height=_path_segment_lengths(points, closed)),
            dtype=float,
        )
    else:
        diameter = np.asarray(deriv(points, closed=closed), dtype=float)
    norms = np.linalg.norm(diameter, axis=1, keepdims=True)
    assert np.all(norms.ravel() > EPSILON), "Cannot normalize a zero vector"
    result = diameter / norms
    dim = points.shape[1]
    if dim == 2:
        return [Vector([float(r[0]), float(r[1])]) for r in result]
    return [Vector([float(r[0]), float(r[1]), float(r[2])]) for r in result]


def _path_normals(points: np.ndarray, closed: bool, tangents: list[Vector] | None = None) -> list[Vector]:
    """Normal vector (perpendicular to tangent, in the plane of the curve) at each point.

    For 2-D paths this is a 90-degree rotation of the tangent. For 3-D paths it is the
    principal normal estimated via the triple-product cross.

    Args:
        tangents: Optional pre-computed tangent vectors; computed automatically if None.
        closed: Override the instance's closed flag; uses ``self.closed`` by default.

    Returns:
        An ndarray of unit normal vectors, one per path point.
    """
    if tangents is None:
        tangents = _path_tangents(points, closed)
    dim = points.shape[1]
    if dim == 2:
        return [Vector([float(t[1]), float(-t[0])]) for t in tangents]
    sides = len(points)
    out: list[Vector] = []
    for i in range(sides):
        if i == 0:
            idx = [-1, 0, 1] if closed else [0, 1, 2]
        elif i == sides - 1:
            idx = [i - 1, i, (i + 1) % sides] if closed else [i - 2, i - 1, i]
        else:
            idx = [i - 1, i, i + 1]
        pts = points[idx]
        ta = np.asarray(tangents[i], dtype=float)
        v = np.cross(np.cross(pts[1] - pts[0], pts[2] - pts[0]), ta)
        norm = float(np.linalg.norm(v))
        assert norm > EPSILON, "3D path contains collinear points"
        out.append(Vector([float(x) for x in (v / norm)]))
    return out


def _path_curvature(points: np.ndarray, closed: bool) -> NDArray[np.float64]:
    """Numeric curvature estimate of the path at each point, as an ndarray.

    Args:
        closed: Override the instance's closed flag; uses ``self.closed`` by default.

    Returns:
        An ndarray of curvature values, one per path point.
    """
    diameter1 = np.asarray(deriv(points, closed=closed), dtype=float)
    diameter2 = np.asarray(deriv2(points, closed=closed), dtype=float)
    n1 = np.linalg.norm(diameter1, axis=1)
    n2 = np.linalg.norm(diameter2, axis=1)
    dot = np.einsum("ij,ij->i", diameter1, diameter2)
    val = np.clip((n1 * n2) ** 2 - dot**2, 0.0, None)
    return np.sqrt(val) / n1**3  # type: ignore[return-value]


def _path_torsion(points: np.ndarray, closed: bool) -> NDArray[np.float64]:
    """Numeric torsion estimate of the path at each point, as an ndarray.

    Args:
        closed: Override the instance's closed flag; uses ``self.closed`` by default.

    Returns:
        An ndarray of torsion values, one per path point.
    """
    diameter1 = np.asarray(deriv(points, closed=closed), dtype=float)
    diameter2 = np.asarray(deriv2(points, closed=closed), dtype=float)
    d3 = np.asarray(deriv3(points, closed=closed), dtype=float)
    crossterm = np.cross(diameter1, diameter2)
    dot = np.einsum("ij,ij->i", crossterm, d3)
    denom = np.einsum("ij,ij->i", crossterm, crossterm)
    return dot / denom  # type: ignore[return-value]


# -- Breaking paths up into subpaths ---------------------------------------------------


def _path_cut(points: np.ndarray, closed: bool, cutdist: float | Sequence[float]) -> list:
    """Cut path into subpaths at the given ascending list of distances (or a single distance).

    Args:
        cutdist: A single distance or a list of ascending distances from the start.
        closed: Override the instance's closed flag; uses ``self.closed`` by default.

    Returns:
        A list of subpath point lists.
    """
    if isinstance(cutdist, (int, float)):
        return _path_cut(points, closed, [cutdist])
    assert isinstance(cutdist, (list, tuple, np.ndarray))
    assert cutdist[-1] < _path_total_length(points, closed), "Cut distances must be smaller than the path length"
    assert cutdist[0] > 0, "Cut distances must be strictly positive"
    cutlist: list[CutPoint] = _path_cut_points(points, closed, cutdist)  # type: ignore[assignment]
    return _path_cut_getpaths(points, closed, cutlist)


def _path_cut_getpaths(points: np.ndarray, closed: bool, cutlist: list[CutPoint]) -> list:
    """Reconstruct sub-paths from the output of path_path_cut_points().

    Args:
        cutlist: Output from path_path_cut_points(), a list of :class:`CutPoint` entries.
        closed: Whether the path is closed.

    Returns:
        A list of subpath point lists.
    """
    cuts = len(cutlist)
    result = []
    seg0 = list(_list_head(points, cutlist[0].next_index - 1))
    if not approx(cutlist[0].point, points[cutlist[0].next_index - 1]):
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
        if not approx(cutlist[i].point, _select(points, cutlist[i].next_index)):
            seg.append(cutlist[i].point)
        seg.extend(_slice(points, cutlist[i].next_index, cutlist[i + 1].next_index - 1))
        if not approx(cutlist[i + 1].point, _select(points, cutlist[i + 1].next_index - 1)):
            seg.append(cutlist[i + 1].point)
        result.append(seg)
    last_seg = []
    if not approx(cutlist[cuts - 1].point, _select(points, cutlist[cuts - 1].next_index)):
        last_seg.append(cutlist[cuts - 1].point)
    last_seg.extend(_select(points, cutlist[cuts - 1].next_index, 0 if closed else -1))
    result.append(last_seg)
    return result


def _path_cut_points(
    points: np.ndarray, closed: bool, cutdist: float | Sequence[float], direction: bool = False
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
    normals = _path_cuts_normals(points, closed, cuts, dirs)
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
        dpartial = 0.0 if len(result) == 0 else math.dist(lastpt, _select(points, pind))
        if dists[dind] < dpartial + dtotal:
            t = (dists[dind] - dtotal) / dpartial
            nextpoint = CutPoint(
                point=_to_point(lerp(lastpt, _select(points, pind), t), points.shape[1]), next_index=pind
            )
        else:
            nextpoint = _path_cut_single(points, closed, dists[dind] - dtotal - dpartial, pind)
        result.append(nextpoint)
        dtotal = dists[dind]
        pind = nextpoint.next_index
    return result


def _to_point(arr, dim: int) -> Point:
    """Convert an array-like to a :class:`Point` of the given dimension."""
    a = np.asarray(arr, dtype=float)
    if dim == 2:
        return Point(float(a[0]), float(a[1]))
    return Point(float(a[0]), float(a[1]), float(a[2]))


def _path_cut_single(points: np.ndarray, closed: bool, dist: float, ind: int = 0, eps: float = 1e-7) -> CutPoint:
    """Find the single cut point at distance dist from segment ind.

    Args:
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
            return CutPoint(point=_to_point(_select(points, ind), points.shape[1]), next_index=ind + 1)
        diameter = math.dist(points[ind], _select(points, ind + 1))
        if diameter > dist:
            return CutPoint(
                point=_to_point(lerp(points[ind], _select(points, ind + 1), dist / diameter), points.shape[1]),
                next_index=ind + 1,
            )
        dist -= diameter
        ind += 1


def _path_cuts_normals(points: np.ndarray, closed: bool, cuts: list[CutPoint], dirs: list) -> list[Vector]:
    """Compute normals at each cut point (perpendicular to the direction, in local plane).

    Args:
        cuts: List of cut entries from path_path_cut_points().
        dirs: List of direction vectors at each cut.
        closed: Whether the path is closed.

    Returns:
        A list of :class:`Vector` normal vectors, one per cut point.
    """
    out: list[Vector] = []
    dim = points.shape[1]
    for i in range(len(cuts)):
        if dim == 2:
            out.append(Vector([-dirs[i][1], dirs[i][0]]))
            continue
        plane = None
        if len(points) >= 3:
            start = max(min(cuts[i].next_index, len(points) - 1), 2)
            plane = _path_plane(points, closed, start, start - 2)
        if plane is None:
            if dirs[i][0] == 0 and dirs[i][1] == 0:
                out.append(Vector([1, 0, 0]))
            else:
                n = unit([-dirs[i][1], dirs[i][0], 0])
                out.append(Vector([float(n[0]), float(n[1]), float(n[2])]))
        else:
            n = unit(cross(dirs[i], cross(plane[0], plane[1])))
            out.append(Vector([float(n[0]), float(n[1]), float(n[2])]))
    return out


def _path_plane(points: np.ndarray, closed: bool, ind: int, i: int) -> list[Vector] | None:
    """Find the local plane defined by point ind, ind-1, and the nearest non-collinear point.

    Args:
        ind: Index of the first point defining the plane.
        i: Index of the search start for the third non-collinear point.
        closed: Whether the path is closed.

    Returns:
        A list of two :class:`Vector` basis vectors defining the local plane, or None.
    """
    lower = -1 if closed else 0
    while i >= lower:
        if not is_collinear(points[ind], points[ind - 1], _select(points, i)):
            p_i = _select(points, i)
            return [
                Vector([float(a - b) for a, b in zip(p_i, points[ind - 1], strict=False)]),
                Vector([float(a - b) for a, b in zip(points[ind], points[ind - 1], strict=False)]),
            ]
        i -= 1
    return None


def _path_cuts_dir(points: np.ndarray, closed: bool, cuts: list[CutPoint], eps: float = 1e-2) -> list[Vector]:
    """Compute direction vectors at each cut point (blended from adjacent segments).

    Args:
        cuts: List of cut entries from path_path_cut_points().
        closed: Whether the path is closed.
        eps: Epsilon for numerical comparisons.

    Returns:
        A list of :class:`Vector` direction vectors, one per cut point.
    """
    out: list[Vector] = []
    zeros = [0] * points.shape[1]
    for ci in range(len(cuts)):
        nextind = cuts[ci].next_index
        nextpath = unit(
            [
                a - b
                for a, b in zip(
                    _select(points, nextind + 1),
                    _select(points, nextind),
                    strict=False,
                )
            ],
            zeros,
        )
        thispath = unit(
            [
                a - b
                for a, b in zip(
                    _select(points, nextind),
                    _select(points, nextind - 1),
                    strict=False,
                )
            ],
            zeros,
        )
        lastpath = unit(
            [
                a - b
                for a, b in zip(
                    _select(points, nextind - 1),
                    _select(points, nextind - 2),
                    strict=False,
                )
            ],
            zeros,
        )
        if nextind == len(points) and not closed:
            nextdir = lastpath
        elif (nextind <= len(points) - 2 or closed) and approx(cuts[ci].point, _select(points, nextind), eps=eps):
            nextdir = unit([a + b for a, b in zip(nextpath, thispath, strict=False)])
        elif (nextind > 1 or closed) and approx(cuts[ci].point, _select(points, nextind - 1), eps=eps):
            nextdir = unit([a + b for a, b in zip(thispath, lastpath, strict=False)])
        else:
            nextdir = thispath
        out.append(Vector([float(v) for v in nextdir]))
    return out


# -- Resampling -- changing the number of points in a path -----------------------------


def _subdivide_path(
    points: np.ndarray,
    closed: bool,
    sides: float | Sequence[int] | None = None,
    refine: int | None = None,
    maxlen: float | None = None,
    exact: bool | None = None,
    method: str | None = None,
) -> list:
    """Subdivide path to produce a more finely sampled path; see BOSL2 subdivide_path().

    Args:
        sides: Target number of points.
        refine: Multiplier for point count.
        maxlen: Maximum segment length.
        closed: Override the instance's closed flag; uses ``self.closed`` by default.
        exact: If True, use sum-preserving rounding.
        method: "length" or "segment".

    Returns:
        A list of subdivided path points.
    """
    assert sum(x is not None for x in (sides, refine, maxlen)) == 1, (
        "Must give exactly one of sides, refine, and maxlen"
    )
    if refine == 1 or sides == len(points):
        return list(points)
    if maxlen is not None:
        assert method is None, "Cannot give method with maxlen"
        assert exact is None, "Cannot give exact with maxlen"
        out: list[Any] = []
        for p0, p1 in _pair(points, closed):
            steps = math.ceil(math.dist(p1, p0) / maxlen)
            out.extend(lerpn(p0, p1, steps, endpoint=False))
        if not closed:
            out.append(points[-1])
        return out
    exact = True if exact is None else exact
    method = "length" if method is None else method
    assert method in ("length", "segment")
    if sides is None:
        assert refine is not None, "Must give exactly one of sides, refine, and maxlen"
        sides = len(points) * refine
    assert (isinstance(sides, (int, float)) and sides > 0) or isinstance(sides, (list, tuple)), (
        "Parameter sides to subdivide_path must be positive number or vector"
    )
    count = len(points) - (0 if closed else 1)
    if method == "segment":
        if isinstance(sides, (list, tuple)):
            assert len(sides) == count, "Vector parameter sides to subdivide_path has the wrong length"
            add_guess = add_scalar(list(sides), -1)
        else:
            add_guess_r = _repeat((sides - len(points)) / count, count)
            add_guess = add_guess_r  # type: ignore[assignment]
    else:
        assert isinstance(sides, (int, float)), (
            'Parameter sides to subdivide path must be a number when method="length"'
        )
        path_lens = _path_segment_lengths(points, closed)
        add_density = (sides - len(points)) / sum(path_lens)
        add_guess = [float(ln * add_density) for ln in path_lens]  # type: ignore[assignment]
    add_list = [float(v) for v in add_guess]
    add = _sum_preserving_round(add_list) if exact else [_scad_round(v) for v in add_list]
    out2: list[Any] = []
    for i in range(count):
        out2.extend(lerpn(points[i], _select(points, i + 1), 1 + int(add[i]), endpoint=False))
    if not closed:
        out2.append(points[-1])
    return out2


def _resample_path(points: np.ndarray, closed: bool, sides: int | None = None, spacing: float | None = None) -> list:
    """Uniformly resample path to sides points, or to a spacing near spacing.

    Args:
        sides: Target number of points.
        spacing: Approximate spacing between points.
        closed: Override the instance's closed flag; uses ``self.closed`` by default.

    Returns:
        A list of uniformly resampled path points.
    """
    assert (sides is None) != (spacing is None), "Must define exactly one of sides and spacing"
    length = _path_total_length(points, closed)
    if sides is not None:
        n_use = sides - (0 if closed else 1)
    else:
        assert spacing is not None
        n_use = round(length / spacing)
    distlist = lerpn(0, length, n_use, endpoint=False)
    cuts = _path_cut_points(points, closed, distlist)  # type: ignore[arg-type]
    out = [c.point for c in cuts]
    if not closed:
        out.append(points[-1])
    return out


def _path_select(points: np.ndarray, closed: bool, s1: int, u1: float, s2: int, u2: float) -> list:
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
    return out


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Static path utility functions (moved from Path2D to avoid circular imports)
# ---------------------------------------------------------------------------


def _pair(lst: Sequence[Any] | np.ndarray, wrap: bool = False) -> list[Any]:
    # List of consecutive (lst[i], lst[i+1]) pairs; if wrap, also (last, first).
    length = len(lst) - 1
    if length < 1:
        return []
    out = [(lst[i], lst[i + 1]) for i in range(length)]
    if wrap:
        out.append((lst[length], lst[0]))
    return out


def _list_head(lst: Sequence[Any] | np.ndarray, to: int = -2) -> list[Any]:
    # Elements of lst up to and including index to (BOSL2 _list_head()).
    if to < 0:
        return list(lst[: len(lst) + to + 1])
    if to < len(lst):
        return list(lst[: to + 1])
    return list(lst)


def _slice(lst: Sequence[Any] | np.ndarray, start: int = 0, end: int = -1) -> list[Any]:
    # lst[start..end] inclusive, negative indices from the end, clamped (BOSL2 _slice()).
    if len(lst) == 0:
        return []
    length = len(lst)
    s = max(0, min(length - 1, start + (length if start < 0 else 0)))
    e = max(0, min(length - 1, end + (length if end < 0 else 0)))
    if e < s:
        return []
    return lst[s : e + 1]  # type: ignore[return-value]


def _select(lst: Sequence[Any] | np.ndarray, start: int, end: int | None = None) -> list[Any]:
    # Circular list indexing/slicing (BOSL2 _select()). Wraps index modulo len;
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


def _repeat(val: Any, sides: int) -> list:
    """*val* repeated *sides* times."""
    return [val for _ in range(sides)]


def _sum_preserving_round(data: Sequence[float]) -> list[float]:
    # Round every entry to an integer, carrying the rounding error forward so the sum is preserved.
    out = list(data)
    error = 0.0
    for i in range(len(out) - 1):
        newval = _scad_round(out[i] + error)
        error = out[i] + error - newval
        out[i] = newval
    out[-1] = _scad_round(out[-1] + error)
    return out


def _scad_round(x: float) -> float:
    # Round half away from zero, matching OpenSCAD's round().
    return math.floor(x + 0.5) if x >= 0 else math.ceil(x - 0.5)


# Section: Path -- dimension-agnostic path-math kernels shared by Path2D and Path3D
# ---------------------------------------------------------------------------


class Path(ABC):
    """Dimension-agnostic numeric path operations shared by :class:`Path2D` and :class:`Path3D`.

    Abstract base class. Subclasses must provide ``_points`` (:class:`numpy.ndarray`) and
    ``closed`` (:class:`bool`).
    """

    _points: np.ndarray
    closed: bool

    @abstractmethod
    def __init__(self, points: Sequence[Sequence[float]], closed: bool = True) -> None: ...

    def __len__(self) -> int:
        return len(self._points)

    def __getitem__(self, key: int | slice | tuple) -> np.ndarray:
        return self._points[key]

    def __iter__(self):
        return iter(self._points)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Path):
            return NotImplemented
        return bool(np.allclose(self._points, other._points)) and self.closed == other.closed

    @property
    def array(self) -> np.ndarray:
        """The points as an (N, D) numpy array."""
        return self._points

    # -- Path2D length calculation -----------------------------------------------------------

    @abstractmethod
    def segment_lengths(self, closed: bool | None = None) -> NDArray[np.float64]:
        """Length of each segment of the path, as an ndarray.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of segment lengths.
        """
        ...

    @abstractmethod
    def length_fractions(self, closed: bool | None = None) -> NDArray[np.float64]:
        """Distance fraction of each point in the path (0 at start, 1 at end).

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of cumulative length fractions, from 0 to 1.
        """
        ...

    @abstractmethod
    def closest_point(self, pt: Point | Sequence[float], closed: bool | None = None) -> Point:
        """The closest point on the path to *pt*.

        Args:
            pt: The query point as :class:`~pybosl2.points.Point` or ``[x, y, z]``.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A :class:`~pybosl2.points.Point` of the closest point on the path.
        """
        ...

    @abstractmethod
    def tangents(self, closed: bool | None = None, uniform: bool = True) -> list[Vector]:
        """Normalized tangent vector at each point of the path, as an ndarray.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            uniform: If True, use uniform parameter spacing; if False, weight by segment lengths.

        Returns:
            An ndarray of unit tangent vectors, one per path point.
        """
        ...

    @abstractmethod
    def normals(self, tangents: list[Vector] | None = None, closed: bool | None = None) -> list[Vector]:
        """Normal vector (perpendicular to tangent, in the plane of the curve) at each point.

        For 2-D paths this is a 90-degree rotation of the tangent. For 3-D paths it is the
        principal normal estimated via the triple-product cross.

        Args:
            tangents: Optional pre-computed tangent vectors; computed automatically if None.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of unit normal vectors, one per path point.
        """
        ...

    @abstractmethod
    def curvature(self, closed: bool | None = None) -> NDArray[np.float64]:
        """Numeric curvature estimate of the path at each point, as an ndarray.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of curvature values, one per path point.
        """
        ...

    @abstractmethod
    def torsion(self, closed: bool | None = None) -> NDArray[np.float64]:
        """Numeric torsion estimate of the path at each point, as an ndarray.

        Args:
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            An ndarray of torsion values, one per path point.
        """
        ...

    @abstractmethod
    def cut(self, cutdist: float | Sequence[float], closed: bool | None = None) -> list[Any]:
        """Cut path into subpaths at the given ascending list of distances (or a single distance).

        Args:
            cutdist: A single distance or a list of ascending distances from the start.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A list of subpath point lists.
        """
        ...

    @abstractmethod
    def cut_getpaths(self, cutlist: list[CutPoint], closed: bool) -> Sequence[Path]:
        """Reconstruct sub-paths from the output of cut_points().

        Args:
            cutlist: Output from cut_points(), a list of :class:`CutPoint` entries.
            closed: Whether the path is closed.

        Returns:
            A list of subpath point lists.
        """
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    def cut_points_recurse(self, dists: Sequence[float], closed: bool = False) -> list[CutPoint]:
        """Walk the path accumulating distance until each cut distance is reached.

        Args:
            dists: Ordered list of distances from the start at which to cut.
            closed: Whether the path is closed.

        Returns:
            A list of :class:`CutPoint` entries, one per cut distance.
        """
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    def cuts_path_normals(self, cuts: list[CutPoint], dirs: list[Vector], closed: bool = False) -> list[Vector]:
        """Compute normals at each cut point (perpendicular to the direction, in local plane).

        Args:
            cuts: List of cut entries from cut_points().
            dirs: List of direction vectors at each cut.
            closed: Whether the path is closed.

        Returns:
            A list of normal vectors, one per cut point.
        """
        ...

    @abstractmethod
    def plane(self, ind: int, i: int, closed: bool = False) -> list[Vector] | None:
        """Find the local plane defined by point ind, ind-1, and the nearest non-collinear point.

        Args:
            ind: Index of the first point defining the plane.
            i: Index of the search start for the third non-collinear point.
            closed: Whether the path is closed.

        Returns:
            A 2x3 ndarray of two basis vectors defining the local plane, or None if no
            non-collinear point is found.
        """
        ...

    @abstractmethod
    def cuts_dir(self, cuts: list[CutPoint], closed: bool = False, eps: float = 1e-2) -> list[Vector]:
        """Compute direction vectors at each cut point (blended from adjacent segments).

        Args:
            cuts: List of cut entries from cut_points().
            closed: Whether the path is closed.
            eps: Epsilon for numerical comparisons.

        Returns:
            A list of direction vectors, one per cut point.
        """
        ...

    @abstractmethod
    def subdivide_path(
        self,
        sides: float | Sequence[int] | None = None,
        refine: int | None = None,
        maxlen: float | None = None,
        closed: bool | None = None,
        exact: bool | None = None,
        method: str | None = None,
    ) -> Path:
        """Subdivide path to produce a more finely sampled path; see BOSL2 subdivide_path().

        Args:
            sides: Target number of points.
            refine: Multiplier for point count.
            maxlen: Maximum segment length.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.
            exact: If True, use sum-preserving rounding.
            method: "length" or "segment".

        Returns:
            A list of subdivided path points.
        """
        ...

    @abstractmethod
    def resample_path(
        self,
        sides: int | None = None,
        spacing: float | None = None,
        closed: bool | None = None,
    ) -> Path:
        """Uniformly resample path to sides points, or to a spacing near spacing.

        Args:
            sides: Target number of points.
            spacing: Approximate spacing between points.
            closed: Override the instance's closed flag; uses ``self.closed`` by default.

        Returns:
            A list of uniformly resampled path points.
        """
        ...

    @abstractmethod
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
        ...

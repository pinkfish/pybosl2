# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


# The SDF distance-field machinery the shape layers build on: the exact/decomposed polygon SDF
# (convex fast path, convex-deficiency decomposition for concave outlines, unsigned outline
# distance), the per-corner rounded/chamfered rect SDF, the 2-D convex hull, and the shared SDF
# utilities (_lv_hypot/_radius/_PENALTY). Path data is numpy throughout (see as_points()); only the
# native boundaries get plain-python lists.
#
# General-purpose path/bezier utilities (tangents, cut points, round_corners, superformula/egg
# outlines, Bezier sampling, ...) are NOT duplicated here -- pybosl2's own modules are canonical:
# pybosl2.paths.Path, pybosl2.beziers.Bezier, pybosl2.rounding.round_corners, pybosl2.shapes2d.egg/supershape
# and pybosl2.geometry. Use those directly.
#

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from pybosl2._sdf._edges import _pick_radius
from pybosl2._sdf._libfive import LVTree, lv

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import ArrayLike, NDArray


def as_path_list(paths: list[Sequence[float]] | NDArray) -> list[NDArray[np.float64]]:
    """Normalize `paths` -- one path, or a list of paths, in any array-like spelling -- to a
    list of (n, 2) float arrays (the multi-outline entry-point convention polygon2d()/
    region2d() accept)."""
    if isinstance(paths, np.ndarray):
        return [as_points(paths)] if paths.ndim == 2 else [as_points(q) for q in paths]
    first = paths[0]
    if isinstance(first, np.ndarray) or isinstance(first[0], (list, tuple, np.ndarray)):
        return [as_points(q) for q in paths]
    return [as_points(paths)]


def as_points(pts: ArrayLike) -> NDArray[np.float64]:
    """The library-wide normalization for 2-D point paths: an (n, 2) float array. Accepts
    any array-like (lists, tuples, arrays, Vec-ish rows). Per the project convention, path
    data is numpy everywhere INSIDE the libraries -- but must be `.tolist()`ed before
    crossing any native boundary (frep bounds, polygon(), translate(), the osuse FFI):
    raw ndarrays there raise SystemError/TypeError and poison the interpreter."""
    arr = np.asarray(pts, dtype=float)
    assert arr.ndim == 2, f"expected a point path, got shape {arr.shape}"
    return arr


# Penalty multiplier used to push a quadrant candidate's SDF value far above any other
# candidate's real value once outside its own quadrant (see module docstring). Dimensionless;
# the mask itself already carries the right length units, so this just needs to be
# comfortably larger than 1 -- 10000 gives a huge safety margin without risking float
# precision issues at typical (mm-scale) board-game part sizes.
_PENALTY = 10000.0
_SQRT2 = math.sqrt(2)


def _radius(
    radius1: float | None = None,
    diameter1: float | None = None,
    radius2: float | None = None,
    diameter2: float | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    dflt: float = 1,
) -> float:
    """_pick_radius(), guaranteed non-None since `dflt` is always a real number here -- unlike
    _pick_radius() itself, whose `dflt: None` default means its return type is `float | None`
    even when a caller always passes a concrete `dflt`. Not for callers that genuinely need to
    tell "not specified" apart from a real radius (see torus()/tube(), which call
    _pick_radius() directly with `dflt=None`)."""
    result = _pick_radius(
        radius1=radius1,
        diameter1=diameter1,
        radius2=radius2,
        diameter2=diameter2,
        radius=radius,
        diameter=diameter,
        dflt=dflt,
    )
    assert result is not None
    return result


def _lv_hypot(a: LVTree, b: LVTree) -> LVTree:
    return lv.sqrt(a * a + b * b)


def _rect2d(u: float, v: float, bu: float, bv: float, amount: list[float], mode: str | None) -> float:
    """2-D SDF of a `2*bu` x `2*bv` rectangle centered at the origin, with an independent
    per-corner edge treatment -- rounding radius or chamfer size, per `mode` (one string for
    all four corners, or a per-corner list) -- given by `amount[i]` at each of its 4 corners.
    `amount` is indexed the same way as pybosl2.shapes3d.EDGE_OFFSETS's per-axis rows:
    [(-,-), (+,-), (-,+), (+,+)] in (u, v) sign.
    """
    corner_modes = [mode] * 4 if isinstance(mode, str) else list(mode)
    candidates = []
    for ci, (su, sv, a) in enumerate(((-1, -1, amount[0]), (1, -1, amount[1]), (-1, 1, amount[2]), (1, 1, amount[3]))):
        cmode = corner_modes[ci]
        if cmode == "round":
            # Rounding is a Minkowski sum: shrink the rect by r, then re-offset the corner
            # outward by r via the hypot() term -- qu/qv are shifted by +r accordingly.
            qu = lv.abs(u) - bu + a
            qv = lv.abs(v) - bv + a
            base = lv.min(lv.max(qu, qv), 0) + _lv_hypot(lv.max(qu, 0), lv.max(qv, 0)) - a
        else:
            assert cmode == "chamfer"
            # Chamfer is a plane cut: intersect the two plain axis-aligned half-planes with
            # a third diagonal half-plane `a` in from the sharp corner. qu/qv are NOT shifted
            # by `a` here (unlike rounding) -- only the diagonal term is.
            qu = lv.abs(u) - bu
            qv = lv.abs(v) - bv
            base = lv.max(lv.max(qu, qv), (qu + qv + a) / _SQRT2)
        mask = lv.max(0, -su * u) + lv.max(0, -sv * v)
        candidates.append(base + _PENALTY * mask)
    return lv.min(lv.min(candidates[0], candidates[1]), lv.min(candidates[2], candidates[3]))


def _polygon_sdf_xy(x: LVTree, y: LVTree, pts: ArrayLike) -> LVTree:
    """Signed distance to an arbitrary SIMPLE polygon (convex or concave, either winding order)
    at the 2-D point (x, y) -- unlike polygon_extrude()'s max-of-half-planes (convex only),
    this handles concave outlines correctly. The zero set (the actual surface, and therefore
    the sign) is exact; the *value* is exact perpendicular distance near every face and a
    sign-correct underestimate out past vertices -- the same documented tradeoff as
    polygon_extrude() and the rest of this module.

    Convex polygons are just the max of the edges' signed half-plane distances. Concave ones
    use a convex-deficiency decomposition: the polygon = its convex hull minus the "pocket"
    polygons between the hull and the boundary, each pocket handled recursively the same way,
    so the whole thing is a pure min/max tree of half-planes. An earlier version computed the
    concave sign from the winding number (an atan2 sum per edge) -- exact in value, but its
    angle-sum branch cut lies exactly on the polygon boundary, and libfive's dual-contouring
    feature detection turned that gradient discontinuity into spike/fin mesh artifacts (badly
    on dense round_corners() outlines, and it interval-pruned terribly on top). The
    decomposition has no branch cuts anywhere and prunes like any other max() chain.
    """
    return _convex_deficiency_sdf(x, y, _ccw(as_points(pts)))


def _ccw(pts: NDArray[np.float64]) -> NDArray[np.float64]:
    """`pts` in counter-clockwise order (reversed if the signed area says clockwise)."""
    nxt = np.roll(pts, -1, axis=0)
    area2 = float(np.sum(pts[:, 0] * nxt[:, 1] - nxt[:, 0] * pts[:, 1]))
    return pts if area2 > 0 else pts[::-1]


def _halfplane_max_sdf(x: LVTree, y: LVTree, ccw_pts: NDArray[np.float64]) -> LVTree:
    """max of signed half-plane distances over a CCW convex polygon's edges (zero-length edges
    skipped, tolerating duplicate points from densified/offset path data)."""
    d = None
    n = len(ccw_pts)
    for i in range(n):
        x0, y0 = ccw_pts[i]
        x1, y1 = ccw_pts[(i + 1) % n]
        ex, ey = x1 - x0, y1 - y0
        elen = math.hypot(ex, ey)
        if elen < 1e-12:
            continue
        e = (ey / elen) * (x - x0) + (-ex / elen) * (y - y0)
        d = e if d is None else lv.max(d, e)
    assert d is not None, "polygon has no non-degenerate edges"
    return d


def _convex_deficiency_sdf(x: LVTree, y: LVTree, ccw_pts: NDArray[np.float64], _depth: int = 0) -> LVTree:
    """See _polygon_sdf_xy(): CCW polygon as (convex hull) minus (recursive pockets)."""
    assert _depth < 16, "polygon decomposition recursed implausibly deep -- is the outline self-intersecting?"
    if _is_convex(ccw_pts):
        return _halfplane_max_sdf(x, y, ccw_pts)

    hull_idx = _convex_hull_indices(ccw_pts)
    d = _halfplane_max_sdf(x, y, ccw_pts[hull_idx])

    # Each stretch of boundary between consecutive hull vertices with interior points in
    # between is a pocket: the chain plus the hull's bridge edge closing it. The chain runs
    # CCW along the polygon, which walks the pocket's own outline CW -- _ccw() renormalizes
    # before recursing. Subtracting is just max(d, -pocket).
    n = len(ccw_pts)
    for k in range(len(hull_idx)):
        i0, i1 = hull_idx[k], hull_idx[(k + 1) % len(hull_idx)]
        chain = [ccw_pts[i0]]
        j = (i0 + 1) % n
        while j != i1:
            chain.append(ccw_pts[j])
            j = (j + 1) % n
        chain.append(ccw_pts[i1])
        if len(chain) < 3:
            continue
        pocket = _convex_deficiency_sdf(x, y, _ccw(np.asarray(chain)), _depth + 1)
        d = lv.max(d, -pocket)
    return d


def _convex_hull_indices(ccw_pts: NDArray[np.float64]) -> list[int]:
    """Indices (into `ccw_pts`, in CCW boundary order) of the polygon's convex hull vertices --
    a wrap-aware pass dropping every vertex that turns clockwise (or is collinear) between its
    surviving neighbours."""
    n = len(ccw_pts)
    idx = list(range(n))
    changed = True
    while changed and len(idx) > 3:
        changed = False
        kept = []
        m = len(idx)
        for k in range(m):
            ax, ay = ccw_pts[idx[(k - 1) % m]]
            bx, by = ccw_pts[idx[k]]
            cx, cy = ccw_pts[idx[(k + 1) % m]]
            cross = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
            if cross > 1e-12:
                kept.append(idx[k])
            else:
                changed = True
        idx = kept
    return idx


def _polygon_dist2_xy(x: LVTree, y: LVTree, pts: ArrayLike) -> LVTree:
    """UNSIGNED squared distance to the polygon outline `pts` at (x, y): the min over per-edge
    point-to-segment distances (the segment clamp is just min/max -- no atan2/winding needed,
    so unlike the signed form this stays branch-cut-free everywhere)."""
    pts = as_points(pts)
    n = len(pts)
    dist2_min = None
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        elen2 = ex * ex + ey * ey
        px, py = x - ax, y - ay
        t = lv.max(0, lv.min(1, (px * ex + py * ey) / elen2))
        dx, dy = px - t * ex, py - t * ey
        diameter2 = dx * dx + dy * dy
        dist2_min = diameter2 if dist2_min is None else lv.min(dist2_min, diameter2)
    return dist2_min


def _is_convex(pts: NDArray[np.float64]) -> bool:
    """True if the simple polygon `pts` is convex: every consecutive edge pair turns the same
    way (cross products all >= 0 or all <= 0, tolerating collinear runs from densified arcs)."""
    n = len(pts)
    pos = neg = False
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        cx, cy = pts[(i + 2) % n]
        cross = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
        if cross > 1e-12:
            pos = True
        elif cross < -1e-12:
            neg = True
        if pos and neg:
            return False
    return True


# ---------------------------------------------------------------------------
# Section: Open-path calculus (ports of the BOSL2 helpers rabbit_clip() needs)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Section: Polygon-path utilities (pure-python ports of the pybosl2 helpers the
# cap-box polygon machinery needs -- byte-for-byte the same geometry, minus numpy)
# ---------------------------------------------------------------------------

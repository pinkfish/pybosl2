# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/nurbs.py
#    Pure-Python port of the NURBS *evaluation* API from BOSL2's nurbs.scad: evaluate a NURBS
#    curve (:func:`nurbs_curve`), sample a NURBS surface patch (:func:`nurbs_patch_points`), and
#    mesh a patch into a VNF (:func:`nurbs_vnf`), plus the :func:`is_nurbs_patch` /
#    :func:`nurbs_elevate_degree` helpers. All three flavours -- clamped, open and closed -- with
#    weights (rational NURBS), knot multiplicities, and explicit knot vectors are supported.
#
#    The evaluation kernel is the standard de Boor algorithm on a knot vector built exactly as
#    BOSL2 builds it; every case here is pinned point-for-point to the real BOSL2 output in
#    tests/test_bosl2_reorient.py. :func:`nurbs_curve` returns a :class:`~pybosl2.paths.Path2D` (2-D
#    control points) or :class:`~pybosl2.paths.Path3D` (3-D), and :func:`nurbs_vnf` returns a
#    :class:`~pybosl2.vnf.VNF`.
#
#    NOT ported (a large follow-up): the interpolation solvers ``nurbs_interp`` /
#    ``nurbs_interp_surface`` (constrained least-squares fitting) and the ``debug_nurbs`` display
#    modules.
#
# FileSummary: NURBS curve/surface evaluation and meshing (de Boor).
# DocCategory: Paths, regions & surfaces
# FileGroup: BOSL2

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from pybosl2.paths import Path

import math

import numpy as np

from pybosl2._helpers import is_num
from pybosl2.math import EPSILON, lerpn

__all__ = [
    "nurbs_curve",
    "nurbs_patch_points",
    "nurbs_vnf",
    "nurbs_elevate_degree",
    "is_nurbs_patch",
]


# ---------------------------------------------------------------------------
# Section: knot-vector helpers
# ---------------------------------------------------------------------------


def _is_param_list(x: object) -> bool:
    return bool(
        bool(
            isinstance(x, (list, tuple)) and len(x) and isinstance(x[0], str) and x[0] in ("closed", "open", "clamped")
        )
    )


def _calc_mult(knots):
    """Run-length multiplicities of the distinct values in *knots* (BOSL2 _calc_mult())."""
    ind = [0]
    for i in range(1, len(knots)):
        if not math.isclose(knots[i], knots[i - 1], rel_tol=0, abs_tol=EPSILON):
            ind.append(i)
    ind.append(len(knots))
    return [ind[i + 1] - ind[i] for i in range(len(ind) - 1)]


def _extend_knot_mult(mult, nxt, length):
    """
    Extend the multiplicity vector periodically to sum to *length* (BOSL2 _extend_knot_mult()).
    """
    mult = list(mult)
    while sum(mult) < length:
        mult.append(mult[nxt])
        nxt += 1
    total = sum(mult)
    if total > length:
        mult[-1] -= total - length
    return mult


def _extend_knot_vector(knots, nxt, length):
    """Extend the knot vector periodically to *length* entries (BOSL2 _extend_knot_vector())."""
    knots = list(knots)
    while len(knots) < length:
        knots.append(knots[-1] + knots[nxt + 1] - knots[nxt])
        nxt += 1
    return knots


def _expand_knots(knots, mult):
    out = []
    for i in range(len(mult)):
        out += [knots[i]] * mult[i]
    return out


def _findspan(u, p, knot, nctrl):
    """The knot span index k with ``knot[k] <= u < knot[k+1]`` (clamped at the domain ends)."""
    if u >= knot[nctrl]:
        return nctrl - 1
    if u <= knot[p]:
        return p
    lo, hi = p, nctrl
    mid = (lo + hi) // 2
    while u < knot[mid] or u >= knot[mid + 1]:
        if u < knot[mid]:
            hi = mid
        else:
            lo = mid
        mid = (lo + hi) // 2
    return mid


def _deboor(knot, ctrl, u, p, k):
    """The de Boor evaluation of the spline at parameter *u* in span *k* (== BOSL2 _nurbs_pt())."""
    diameter = [np.array(ctrl[k - p + j], dtype=float) for j in range(p + 1)]
    for r in range(1, p + 1):
        for j in range(p, r - 1, -1):
            i = k - p + j
            denom = knot[i + p - r + 1] - knot[i]
            alpha = 0.0 if abs(denom) < 1e-15 else (u - knot[i]) / denom
            diameter[j] = (1 - alpha) * diameter[j - 1] + alpha * diameter[j]
    return diameter[p]


# ---------------------------------------------------------------------------
# Section: curve evaluation
# ---------------------------------------------------------------------------


def _nurbs_curve_pts(
    control,
    degree=None,
    splinesteps=None,
    u=None,
    mult=None,
    weights=None,
    type="clamped",  # noqa: A002
    knots=None,
):
    """The list of raw points on a NURBS curve (numpy arrays); wrapped by :func:`nurbs_curve`."""
    if _is_param_list(control):
        assert len(control) >= 6, "Invalid NURBS parameter list."
        return _nurbs_curve_pts(
            control[2],
            control[1],
            splinesteps,
            u,
            mult=control[4],
            weights=control[5],
            type=control[0],
            knots=control[3],
        )
    assert splinesteps is None or u is None, "Must define exactly one of u and splinesteps."
    if splinesteps is None and u is None:
        splinesteps = 16
    if is_num(u):
        return _nurbs_curve_pts(control, degree, u=[u], mult=mult, weights=weights, knots=knots, type=type)

    if weights is not None:
        assert len(weights) == len(control), "weights must match the number of control points."
        homo = [
            list(np.asarray(control[i], dtype=float) * weights[i]) + [float(weights[i])] for i in range(len(control))
        ]
        curve = _nurbs_curve_pts(
            homo,
            degree,
            splinesteps=splinesteps,
            u=u,
            mult=mult,
            knots=knots,
            type=type,
        )
        return [np.asarray(pt[:-1], dtype=float) / pt[-1] for pt in curve]

    assert type in ("closed", "open", "clamped"), f"Unknown NURBS type: {type!r}"
    assert type == "closed" or len(control) >= degree + 1, f"{type} NURBS needs at least degree+1 control points."
    uniform = knots is None
    mult_orig = mult
    ctrl = [np.asarray(p, dtype=float) for p in control]
    if type == "closed":
        ctrl = ctrl + ctrl[:degree]
    sides = len(ctrl)  # control count (extended, for closed)

    # -- multiplicity vector ---------------------------------------------------------------
    if not uniform:
        pass
    elif type == "clamped":
        base = list(mult) if mult is not None else [1] * (sides - degree + 1)
        mult = [degree + 1] + base[1:-1] + [degree + 1]
    elif mult is None:
        mult = [1] * (sides + degree + 1)
    elif type == "open":
        pass
    else:  # closed with explicit mult
        lastmult = mult[-1] + mult[0] - 1
        mult = _extend_knot_mult(list(mult[:-1]) + [lastmult], 1, sides + degree + 1)

    # -- knot vector -----------------------------------------------------------------------
    if uniform:
        m = len(mult)
        knot = []
        for i in range(m):
            knot += [i / (m - 1)] * mult[i]
    else:
        xknots = list(knots) if mult_orig is None else _expand_knots(knots, mult)
        if type == "open":
            knot = xknots
        elif type == "clamped":
            knot = [xknots[0]] * degree + list(xknots) + [xknots[-1]] * degree
        else:  # closed
            knot = _extend_knot_vector(list(xknots), 0, sides + degree + 1)

    bound = None if type == "clamped" else [knot[degree], knot[sides]]

    # -- parameter samples -----------------------------------------------------------------
    if splinesteps is not None:
        assert isinstance(splinesteps, int) and splinesteps > 0, "splinesteps must be a positive integer."
        adjusted_u = []
        for i in range(degree, sides):
            if not math.isclose(knot[i], knot[i + 1], rel_tol=0, abs_tol=EPSILON):
                adjusted_u += [float(x) for x in lerpn(knot[i], knot[i + 1], splinesteps, endpoint=False)]
        if type != "closed":
            adjusted_u.append(knot[sides])
    else:
        uu = [float(x) for x in u]
        assert all(-1e-12 <= x <= 1 + 1e-12 for x in uu), "u must lie in [0, 1]."
        adjusted_u = uu if bound is None else [(bound[1] - bound[0]) * x + bound[0] for x in uu]

    return [_deboor(knot, ctrl, val, degree, _findspan(val, degree, knot, sides)) for val in adjusted_u]


def nurbs_curve(
    control: Path | Sequence[Sequence[float]],
    degree: int | None = None,
    splinesteps: int | None = None,
    u=None,
    mult=None,
    weights=None,
    type: str = "clamped",  # noqa: A002
    knots=None,
) -> Path | list[float]:
    """Evaluate a NURBS curve, returning its points (BOSL2 nurbs_curve()).

    Give either *splinesteps* (uniform samples between knots, with a sample at every knot) or *u*
    (parameter values in ``[0, 1]``). *weights* makes it a rational NURBS; *mult* / *knots* give
    knot multiplicities / an explicit knot vector; *type* is ``"clamped"`` (default), ``"open"`` or
    ``"closed"``. The first argument may instead be a NURBS parameter list
    ``[type, degree, control, knots, mult, weights]``.

    Returns:
        A :class:`~pybosl2.paths.Path2D` (2-D control points) or :class:`~pybosl2.paths.Path3D` (3-D). A
        single scalar *u* returns just that point as a plain list.

    Examples:
        A cubic clamped NURBS curve through five control points, swept into a tube:

        .. pythonscad-example::

            ctrl = [[0, 0, 0], [10, 20, 5], [30, -10, 10], [50, 20, 0], [60, 0, 15]]
            nurbs_curve(ctrl, 3, splinesteps=12).stroke(width=3).show()
    """
    from pybosl2.path2d import Path2D
    from pybosl2.path3d import Path3D

    scalar = is_num(u)
    pts = _nurbs_curve_pts(
        control,
        degree,
        splinesteps=splinesteps,
        u=u,
        mult=mult,
        weights=weights,
        type=type,
        knots=knots,
    )
    if scalar:
        return [float(c) for c in pts[0]]
    dim = len(pts[0])
    closed = (control[0] if _is_param_list(control) else type) == "closed"
    if dim == 2:
        return Path2D([[float(p[0]), float(p[1])] for p in pts], closed=closed)
    if dim == 3:
        return Path3D([[float(p[0]), float(p[1]), float(p[2])] for p in pts], closed=closed)
    return [[float(c) for c in p] for p in pts]  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Section: surfaces
# ---------------------------------------------------------------------------


def is_nurbs_patch(x) -> bool:
    """
    True if *x* looks like a NURBS patch: a rectangular 2-D array of points (BOSL2
    is_nurbs_patch()).
    """
    return bool(
        isinstance(x, (list, tuple))
        and len(x)
        and isinstance(x[0], (list, tuple))
        and len(x[0])
        and isinstance(x[0][0], (list, tuple, np.ndarray))
        and len(x[0]) == len(x[-1])
    )


def _valid_surface_type(surface_type) -> bool:
    if surface_type in ("closed", "clamped", "open"):
        return True
    if not isinstance(surface_type, (list, tuple)) or len(surface_type) != 2:
        return False
    return _valid_surface_type(surface_type[0]) and _valid_surface_type(surface_type[1])


def _force_list2(x):
    """A per-direction 2-list: an existing length-2 list is kept, anything else is duplicated
    (BOSL2 force_list(x, 2)). Used for degree/type/splinesteps, which are scalars or [u, v] pairs."""
    return list(x) if isinstance(x, (list, tuple)) and len(x) == 2 else [x, x]


def _column(grid, j):
    return [row[j] for row in grid]


def nurbs_patch_points(
    patch,
    degree: int | None = None,
    splinesteps: int | None = None,
    u=None,
    v=None,
    weights=None,
    type: str | tuple[str, str] = ("clamped", "clamped"),  # noqa: A002
    mult=(None, None),
    knots=(None, None),
):
    """Sample a NURBS surface *patch* on a grid of points (BOSL2 nurbs_patch_points()).

    *patch* is a rectangular array of control points (or a NURBS parameter list). *degree*,
    *splinesteps*, *type*, *mult* and *knots* are scalars applied to both directions or 2-lists
    ``[u_dir, v_dir]``. Give *splinesteps*, or *u* and *v* parameter lists. *weights* is a matrix
    the size of *patch*.

    Returns:
        A grid (list of rows) of ``[x, y, z]`` points.
    """
    if isinstance(patch, (list, tuple)) and len(patch) and _valid_surface_type(patch[0]):
        assert len(patch) >= 6, "NURBS parameter list is invalid."
        return nurbs_patch_points(
            patch[2],
            patch[1],
            splinesteps,
            u,
            v,
            patch[5],
            patch[0],
            knots=patch[3],
            mult=patch[4],
        )
    assert splinesteps is None or (u is None and v is None), "Cannot combine splinesteps with u and v."

    if weights is not None:
        wpatch = [
            [
                list(np.asarray(patch[i][j], dtype=float) * weights[i][j]) + [float(weights[i][j])]
                for j in range(len(patch[0]))
            ]
            for i in range(len(patch))
        ]
        pts = nurbs_patch_points(
            wpatch,
            degree=degree,
            splinesteps=splinesteps,
            u=u,
            v=v,
            type=type,
            mult=mult,
            knots=knots,
        )
        return [[list(np.asarray(pt[:-1], dtype=float) / pt[-1]) for pt in row] for row in pts]

    degree_list = _force_list2(degree)
    type_list = _force_list2(type)
    splinesteps_list = [None, None] if splinesteps is None else _force_list2(splinesteps)
    mult = [mult, mult] if (mult is None or is_num(mult) or (mult and is_num(mult[0]))) else list(mult)
    knots = [knots, knots] if (knots is None or (knots and is_num(knots[0]))) else list(knots)

    if is_num(u) and is_num(v):
        inner = [
            _nurbs_curve_pts(ctrl, degree_list[1], u=v, type=type_list[1], mult=mult[1], knots=knots[1])[0]
            for ctrl in patch
        ]
        return _nurbs_curve_pts(inner, degree_list[0], u=u, type=type_list[0], mult=mult[0], knots=knots[0])[0]

    # sweep each control-column as a u-curve, then each resulting row as a v-curve
    vsplines = [
        _nurbs_curve_pts(
            _column(patch, i),
            degree_list[0],
            splinesteps=splinesteps_list[0],
            u=u,
            type=type_list[0],
            mult=mult[0],
            knots=knots[0],
        )
        for i in range(len(patch[0]))
    ]
    out = []
    for i in range(len(vsplines[0])):
        row = _nurbs_curve_pts(
            _column(vsplines, i),
            degree_list[1],
            splinesteps=splinesteps_list[1],
            u=v,
            type=type_list[1],
            mult=mult[1],
            knots=knots[1],
        )
        out.append([[float(c) for c in p] for p in row])
    return out


def nurbs_vnf(
    patch,
    degree: int | None = None,
    splinesteps: int = 16,
    weights=None,
    type: str = "clamped",  # noqa: A002
    mult=None,
    knots=None,
    style: str = "default",
    reverse: bool = False,
    caps=None,
    cap1=None,
    cap2=None,
):
    """Mesh a NURBS surface *patch* into a :class:`~pybosl2.vnf.VNF` (BOSL2 nurbs_vnf()).

    Samples the patch with :func:`nurbs_patch_points` and builds the mesh with
    :meth:`~pybosl2.vnf.VNF.vertex_array`, wrapping the rows/columns for ``"closed"`` directions.

    Args:
        patch:       control-point grid or a NURBS parameter list
        degree:      scalar or ``[u, v]`` degree
        splinesteps: scalar or ``[u, v]`` samples per knot span (default 16)
        weights/type/mult/knots: as for :func:`nurbs_patch_points`
        style:       :meth:`~pybosl2.vnf.VNF.vertex_array` triangulation style
        reverse:     flip every face normal
        caps/cap1/cap2: cap a ``["clamped","closed"]`` / ``["closed","clamped"]`` surface

    Examples:
        A cubic B-spline surface patch meshed into a solid:

        .. pythonscad-example::

            patch = [
                [[-50, 50, 0], [-16, 50, 20], [16, 50, 20], [50, 50, 0]],
                [[-50, 16, 20], [-16, 16, 40], [16, 16, 40], [50, 16, 20]],
                [[-50, -16, 20], [-16, -16, 40], [16, -16, 40], [50, -16, 20]],
                [[-50, -50, 0], [-16, -50, 20], [16, -50, 20], [50, -50, 0]],
            ]
            nurbs_vnf(patch, 3).polyhedron().show()
    """
    from pybosl2.vnf import VNF

    if isinstance(patch, (list, tuple)) and len(patch) and _valid_surface_type(patch[0]):
        assert len(patch) >= 6, "NURBS parameter list is invalid."
        return nurbs_vnf(
            patch[2],
            patch[1],
            splinesteps,
            patch[5],
            patch[0],
            knots=patch[3],
            mult=patch[4],
            style=style,
            reverse=reverse,
            caps=caps,
            cap1=cap1,
            cap2=cap2,
        )
    assert is_nurbs_patch(patch), "patch must be a rectangular array of points."
    assert _valid_surface_type(type), 'type must be "closed", "clamped", "open", or a pair of those.'
    type = _force_list2(type)  # noqa: A001
    havecaps = any(c for c in (caps, cap1, cap2))
    assert not havecaps or type in (["clamped", "closed"], ["closed", "clamped"]), (
        'caps require type ["clamped","closed"] or ["closed","clamped"].'
    )
    flip = havecaps and type[0] == "closed"
    pts = nurbs_patch_points(
        patch,
        degree=degree,
        splinesteps=splinesteps,
        type=(type[0], type[1]),
        mult=mult,
        knots=knots,
        weights=weights,
    )
    if flip:
        pts = [list(row) for row in zip(*pts, strict=False)]
    return VNF.vertex_array(
        pts,
        style=style,
        row_wrap=type[1 if flip else 0] == "closed",
        col_wrap=type[0 if flip else 1] == "closed",
        reverse=reverse,
        caps=caps,
        cap1=cap1,
        cap2=cap2,
    )


# ---------------------------------------------------------------------------
# Section: degree elevation
# ---------------------------------------------------------------------------


def _nip(i, p, u, knot_vector):
    """The i-th B-spline basis function of degree *p* at *u* on knot vector *U* (BOSL2 _nip())."""
    m = len(knot_vector) - 1
    if (i == 0 and u <= knot_vector[0]) or (i == m - p - 1 and u >= knot_vector[m]):
        return 1.0
    if u < knot_vector[i] or u >= knot_vector[i + p + 1]:
        return 0.0
    bvals = [0.0] * (p + 1)
    for j in range(p + 1):
        bvals[j] = 1.0 if (knot_vector[i + j] <= u < knot_vector[i + j + 1]) else 0.0
    for k in range(1, p + 1):
        saved = 0.0 if bvals[0] == 0 else ((u - knot_vector[i]) * bvals[0]) / (knot_vector[i + k] - knot_vector[i])
        for j in range(p - k + 1):
            knot_left = knot_vector[i + j + 1]
            knot_right = knot_vector[i + j + k + 1]
            if bvals[j + 1] == 0:
                bvals[j] = saved
                saved = 0.0
            else:
                temp = bvals[j + 1] / (knot_right - knot_left)
                bvals[j] = saved + (knot_right - u) * temp
                saved = (u - knot_left) * temp
    return bvals[0]


def _greville(knot_vector, p):
    sides = len(knot_vector) - p - 2
    return [sum(knot_vector[i + 1 : i + p + 1]) / p for i in range(sides + 1)]


def _increment_knot_mults(knot_vector):
    out = []
    i = 0
    while i < len(knot_vector):
        j = i
        while j < len(knot_vector) and math.isclose(knot_vector[j], knot_vector[i], rel_tol=0, abs_tol=EPSILON):
            j += 1
        out += [knot_vector[i]] * (j - i + 1)
        i = j
    return out


def _elevate_once(ctrl, p, knot_vector):
    ctrl = [np.asarray(c, dtype=float) for c in ctrl]
    dim = len(ctrl[0])
    p_new = p + 1
    knots_new = _increment_knot_mults(knot_vector)
    n_new = len(knots_new) - p_new - 2
    n_old = len(ctrl) - 1
    grev = _greville(knots_new, p_new)
    ctrl_vals = np.array(
        [[sum(_nip(j, p, uu, knot_vector) * ctrl[j][d] for j in range(n_old + 1)) for d in range(dim)] for uu in grev]
    )
    basis_mat = np.array([[_nip(i, p_new, grev[k], knots_new) for i in range(n_new + 1)] for k in range(n_new + 1)])
    new_ctrl = np.linalg.solve(basis_mat, ctrl_vals)
    return [list(row) for row in new_ctrl], knots_new, p_new


def nurbs_elevate_degree(
    control,
    degree: int | None = None,
    knots=None,
    type: str = "clamped",  # noqa: A002
    times: int = 1,
    weights=None,
    mult=None,
):
    """Raise a NURBS/B-spline curve's degree by *times*, returning a parameter list (BOSL2 nurbs_elevate_degree()).

    Returns ``[type, new_degree, new_control, new_knots, None, new_weights]``. Only ``"clamped"``
    and ``"open"`` splines are supported (as in BOSL2). Rational curves are elevated in homogeneous
    space and de-homogenised.
    """
    if _is_param_list(control):
        assert len(control) >= 6, "Invalid NURBS parameter list."
        if times == 0:
            return list(control)
        return nurbs_elevate_degree(
            control[2],
            control[1],
            control[3],
            type=control[0],
            times=times,
            weights=control[5],
            mult=control[4],
        )
    if times == 0:
        return [type, degree, control, knots, mult, weights]

    if weights is not None:
        assert len(weights) == len(control), "weights must match the number of control points."
        homo = [
            list(np.asarray(control[i], dtype=float) * weights[i]) + [float(weights[i])] for i in range(len(control))
        ]
        radius = nurbs_elevate_degree(homo, degree, knots=knots, type=type, times=times, mult=mult)
        new_w = [pt[-1] for pt in radius[2]]
        new_ctrl = [list(np.asarray(pt[:-1], dtype=float) / pt[-1]) for pt in radius[2]]
        return [radius[0], radius[1], new_ctrl, radius[3], None, new_w]

    assert type in ("clamped", "open"), 'nurbs_elevate_degree: type must be "clamped" or "open".'
    assert is_num(times) and times >= 1, "times must be a positive integer."
    assert degree is not None, "degree must be provided."
    sides = len(control)
    if knots is None and mult is None:
        xknots = (
            [float(x) for x in lerpn(0, 1, sides - degree + 1)]
            if type == "clamped"
            else [float(x) for x in lerpn(0, 1, sides + degree + 1)]
        )
    elif mult is None:
        xknots = list(knots)
    else:
        m = len(mult)
        adj = ([degree + 1] + list(mult[1:-1]) + [degree + 1]) if (type == "clamped" and m >= 2) else list(mult)
        positions = list(knots) if knots is not None else [0 if m == 1 else i / (m - 1) for i in range(m)]
        exp = _expand_knots(positions, adj)
        xknots = exp[degree : len(exp) - degree] if type == "clamped" else exp

    u_full = ([xknots[0]] * degree + list(xknots) + [xknots[-1]] * degree) if type == "clamped" else list(xknots)
    q, u_new, p_new = _elevate_once(control, degree, u_full)
    new_knots = u_new[degree + 1 : len(u_new) - degree - 1] if type == "clamped" else u_new
    if times == 1:
        return [type, p_new, q, new_knots, None, None]
    return nurbs_elevate_degree(q, p_new, new_knots, type=type, times=times - 1)

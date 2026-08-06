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

from typing import TYPE_CHECKING, Sequence, cast

if TYPE_CHECKING:
    from pybosl2.caps import CapSpec, CapsSpec
    from pybosl2.paths import Path
    from pybosl2.vnf import VNF

import math
from enum import Enum

import numpy as np

from pybosl2._helpers import is_num
from pybosl2.math import EPSILON, lerpn

# ── type aliases ─────────────────────────────────────────────────────────

__all__ = [
    "NurbsType",
    "nurbs_curve",
    "nurbs_patch_points",
    "nurbs_patch_point",
    "nurbs_vnf",
    "nurbs_elevate_degree",
    "is_nurbs_patch",
]


# ---------------------------------------------------------------------------
# Section: NURBS type enum
# ---------------------------------------------------------------------------


class NurbsType(Enum):
    """NURBS curve/surface boundary condition.

    Determines how the knot vector is built and whether the curve/surface wraps.

    Attributes:
        CLAMPED: Clamped (end-point-interpolating) — the default.
        OPEN:     Open (non-interpolating) B-spline.
        CLOSED:   Closed (periodic) — start and end connect.
    """

    CLAMPED = "clamped"
    OPEN = "open"
    CLOSED = "closed"


# ---------------------------------------------------------------------------
# Section: knot-vector helpers
# ---------------------------------------------------------------------------


def _is_param_list(x: object) -> bool:
    return bool(isinstance(x, (list, tuple)) and len(x) >= 6 and isinstance(x[0], NurbsType))


def _calc_mult(knots: Sequence[float]) -> list[int]:
    """Run-length multiplicities of the distinct values in *knots* (BOSL2 ``_calc_mult()``)."""
    ind = [0]
    for i in range(1, len(knots)):
        if not math.isclose(knots[i], knots[i - 1], rel_tol=0, abs_tol=EPSILON):
            ind.append(i)
    ind.append(len(knots))
    return [ind[i + 1] - ind[i] for i in range(len(ind) - 1)]


def _extend_knot_mult(mult: Sequence[int], nxt: int, length: int) -> list[int]:
    """Extend a knot multiplicity vector periodically to sum to *length*.

    Args:
        mult: The multiplicity list to extend.
        nxt: The index of the next multiplicity to repeat.
        length: The target sum of the multiplicities.

    Returns:
        The extended multiplicity list.
    """
    mult = list(mult)
    n = len(mult)
    while sum(mult) < length:
        mult.append(mult[nxt % n])
        nxt += 1
    total = sum(mult)
    if total > length:
        mult[-1] -= total - length
    return mult


def _extend_knot_vector(knots: Sequence[float], nxt: int, length: int) -> list[float]:
    """Extend a knot vector periodically to *length* entries.

    Args:
        knots: The knot vector to extend.
        nxt: The index of the next knot from which to compute spacing.
        length: The target length of the knot vector.

    Returns:
        The extended knot vector.
    """
    knots = list(knots)
    while len(knots) < length:
        knots.append(knots[-1] + knots[nxt + 1] - knots[nxt])
        nxt += 1
    return knots


def _expand_knots(knots: Sequence[float], mult: Sequence[int]) -> list[float]:
    """Expand a compact knot vector by repeating each knot by its multiplicity."""
    out: list[float] = []
    for i in range(len(mult)):
        out += [knots[i]] * mult[i]
    return out


def _findspan(u: float, p: int, knot: Sequence[float], nctrl: int) -> int:
    """Find the knot span index *k* with ``knot[k] <= u < knot[k+1]``.

    Args:
        u: The parameter value.
        p: The degree of the B-spline.
        knot: The knot vector.
        nctrl: The number of control points.

    Returns:
        The knot span index (clamped at the domain ends).
    """
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


def _deboor(knot: Sequence[float], ctrl: list[np.ndarray], u: float, p: int, k: int) -> np.ndarray:
    """Evaluate the B-spline at parameter *u* in span *k* using the de Boor algorithm.

    Args:
        knot: The knot vector.
        ctrl: The list of control points (numpy arrays).
        u: The parameter value at which to evaluate.
        p: The degree of the B-spline.
        k: The knot span index (as returned by :func:`_findspan`).

    Returns:
        The evaluated point as a numpy array.
    """
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


def _nurbs_curve_pts(  # type: ignore[no-untyped-def]
    control,
    degree=None,
    splinesteps=None,
    u=None,
    mult=None,
    weights=None,
    type: NurbsType = NurbsType.CLAMPED,  # noqa: A002
    knots=None,
):
    """The list of raw points on a NURBS curve (numpy arrays); wrapped by :func:`nurbs_curve`."""
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

    assert isinstance(type, NurbsType), f"Unknown NURBS type: {type!r}"
    assert type == NurbsType.CLOSED or len(control) >= degree + 1, f"Not enough control points for {type}"
    uniform = knots is None
    mult_orig = mult
    ctrl = [np.asarray(p, dtype=float) for p in control]
    if type == NurbsType.CLOSED:
        ctrl = ctrl + ctrl[:degree]
    sides = len(ctrl)  # control count (extended, for closed)

    # -- multiplicity vector ---------------------------------------------------------------
    if not uniform:
        pass
    elif type == NurbsType.CLAMPED:
        base = list(mult) if mult is not None else [1] * (sides - degree + 1)
        mult = [degree + 1] + base[1:-1] + [degree + 1]
    elif mult is None:
        mult = [1] * (sides + degree + 1)
    elif type == NurbsType.OPEN:
        pass
    else:  # closed with explicit mult
        _m = [mult] if is_num(mult) else list(mult)
        lastmult = _m[-1] + _m[0] - 1
        mult = _extend_knot_mult(_m[:-1] + [lastmult], 1, sides + degree + 1)

    # -- knot vector -----------------------------------------------------------------------
    if uniform:
        m = len(mult)
        knot = []
        for i in range(m):
            knot += [i / (m - 1)] * mult[i]
    else:
        xknots = list(knots or []) if mult_orig is None else _expand_knots(knots, mult)
        if type == NurbsType.OPEN:
            knot = xknots
        elif type == NurbsType.CLAMPED:
            knot = [xknots[0]] * degree + list(xknots) + [xknots[-1]] * degree
        else:  # closed
            knot = _extend_knot_vector(list(xknots), 0, sides + degree + 1)

    bound = None if type == NurbsType.CLAMPED else [knot[degree], knot[sides]]

    # -- parameter samples -----------------------------------------------------------------
    if splinesteps is not None:
        assert isinstance(splinesteps, int) and splinesteps > 0, "splinesteps must be a positive integer."
        adjusted_u = []
        for i in range(degree, sides):
            if not math.isclose(knot[i], knot[i + 1], rel_tol=0, abs_tol=EPSILON):
                adjusted_u += [float(x) for x in lerpn(knot[i], knot[i + 1], splinesteps, endpoint=False)]
        if type != NurbsType.CLOSED:
            adjusted_u.append(knot[sides])
    else:
        uu = [float(x) for x in u]
        assert all(-1e-12 <= x <= 1 + 1e-12 for x in uu), "u must lie in [0, 1]."
        adjusted_u = uu if bound is None else [(bound[1] - bound[0]) * x + bound[0] for x in uu]

    return [_deboor(knot, ctrl, val, degree, _findspan(val, degree, knot, sides)) for val in adjusted_u]


def nurbs_curve(
    control: Path | list[Sequence[float]],
    degree: int | None = None,
    splinesteps: int | None = None,
    u: float | list[float] | None = None,
    mult: int | list[int] | None = None,
    weights: list[float] | None = None,
    type: NurbsType = NurbsType.CLAMPED,  # noqa: A002
    knots: list[float] | None = None,
) -> Path | list[float]:
    """Evaluate a NURBS curve, returning its points.

    This is the core curve evaluator — equivalent to BOSL2's ``nurbs_curve()``.
    Give either *splinesteps* (uniform samples between knots, with a sample at
    every knot) or *u* (parameter values in ``[0, 1]``).  *weights* makes it a
    rational NURBS; *mult* / *knots* give knot multiplicities or an explicit
    knot vector.  The first argument may also be a NURBS parameter list
    ``[type, degree, control, knots, mult, weights]``.

    Args:
        control: Control points — a sequence of ``[x,y]`` or ``[x,y,z]`` points,
                 or a NURBS parameter list.
        degree: The curve degree.  Required unless *control* is a parameter list.
        splinesteps: Number of samples per knot span.  Mutually exclusive with *u*.
        u: Explicit parameter values in ``[0, 1]``.  Mutually exclusive with
           *splinesteps*.  A scalar returns a single point.
        mult: Knot multiplicities.
        weights: Weights for rational NURBS.  Must match the number of control points.
        type: The boundary condition — :attr:`NurbsType.CLAMPED` (default),
              :attr:`NurbsType.OPEN`, or :attr:`NurbsType.CLOSED`.
        knots: Explicit knot vector.

    Returns:
        A :class:`~pybosl2.paths.Path2D` (2-D control points) or
        :class:`~pybosl2.paths.Path3D` (3-D).  A scalar *u* returns a single
        point as a plain list.

    Raises:
        AssertionError: If neither *splinesteps* nor *u* is provided, or if the
                        control points don't match the degree requirements.

    Examples:
        A cubic clamped NURBS curve through five control points, swept into a tube:

        .. pythonscad-example::

            from pybosl2 import nurbs_curve

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
    closed = (control[0] if _is_param_list(control) else type) == NurbsType.CLOSED
    if dim == 2:
        return Path2D([[float(p[0]), float(p[1])] for p in pts], closed=closed)
    if dim == 3:
        return Path3D([[float(p[0]), float(p[1]), float(p[2])] for p in pts], closed=closed)
    return [[float(c) for c in p] for p in pts]  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Section: surfaces
# ---------------------------------------------------------------------------


def is_nurbs_patch(x: object) -> bool:
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


def _valid_surface_type(surface_type: object) -> bool:
    """Return True if *surface_type* is a :class:`NurbsType` or a pair of them."""
    if isinstance(surface_type, NurbsType):
        return True
    if not isinstance(surface_type, (list, tuple)) or len(surface_type) != 2:
        return False
    return _valid_surface_type(surface_type[0]) and _valid_surface_type(surface_type[1])


def _force_list2(x: object) -> list[object]:
    """Force a value into a 2-element list.

    An existing length-2 list is kept unchanged; anything else (scalar or tuple)
    is duplicated into ``[x, x]``.  Used for degree/type/splinesteps which can
    be scalars or ``[u, v]`` pairs.

    Args:
        x: The value to convert.

    Returns:
        A list of two elements.
    """
    return list(x) if isinstance(x, (list, tuple)) and len(x) == 2 else [x, x]


def _column(grid: list[list[object]], j: int) -> list[object]:
    """Return column *j* from a 2-D grid."""
    return [row[j] for row in grid]


def nurbs_patch_points(
    patch: list[list[list[float]]],
    degree: tuple[int, int] = (3, 3),
    splinesteps: tuple[int | None, int | None] = (16, 16),
    u: list[float] | None = None,
    v: list[float] | None = None,
    weights: list[list[float]] | None = None,
    type: tuple[NurbsType, NurbsType] = (NurbsType.CLAMPED, NurbsType.CLAMPED),  # noqa: A002
    mult: tuple[int | None, int | None] = (None, None),
    knots: tuple[list[float] | None, list[float] | None] = (None, None),
) -> list[list[list[float]]]:
    """Sample a NURBS surface patch on a grid of points.

    Evaluates a NURBS surface — the equivalent of BOSL2's ``nurbs_patch_points()``.
    The patch is swept column-wise (U direction) then row-wise (V direction)
    using :func:`_nurbs_curve_pts`.  For single-point evaluation use
    :func:`nurbs_patch_point`.

    Args:
        patch: A rectangular array of control points, or a NURBS parameter list.
        degree: Per-direction degree ``(u_degree, v_degree)`` (default ``(3,3)``).
        splinesteps: Per-direction samples ``(u_steps, v_steps)`` (default ``(16,16)``).
        u: Explicit parameter values along U (overrides U component of *splinesteps*).
        v: Explicit parameter values along V (overrides V component of *splinesteps*).
        weights: A matrix the same size as *patch* for rational NURBS weighting.
        type: Per-direction boundary condition ``(u_type, v_type)``.
        mult: Per-direction knot multiplicities ``(u_mult, v_mult)``.
        knots: Per-direction knot vectors ``(u_knots, v_knots)``.

    Returns:
        A grid (list of rows) of ``[x, y, z]`` points.
    """

    if weights is not None:
        wpatch: list[list[list[float]]] = cast("list[list[list[float]]]", patch)
        wpatch = [
            [
                list(np.asarray(wpatch[i][j], dtype=float) * weights[i][j]) + [float(weights[i][j])]
                for j in range(len(wpatch[0]))
            ]
            for i in range(len(wpatch))
        ]
        pts = nurbs_patch_points(
            wpatch,
            degree,
            splinesteps,
            u,
            v,
            type=type,
            mult=mult,
            knots=knots,
        )
        return [[list(np.asarray(pt[:-1], dtype=float) / pt[-1]) for pt in row] for row in pts]

    du, dv = degree
    tu, tv = type
    mu, mv = mult
    ku, kv = knots
    su, sv = splinesteps if u is None else (None, None)

    # sweep each control-column as a u-curve, then each resulting row as a v-curve
    vsplines = [
        _nurbs_curve_pts(
            _column(cast("list[list[list[float]]]", patch), i),  # type: ignore[arg-type]
            du,
            splinesteps=su,
            u=u,
            type=tu,
            mult=mu,
            knots=ku,
        )
        for i in range(len(patch[0]))  # type: ignore[arg-type]
    ]
    out: list[list[list[float]]] = []
    for i in range(len(cast("list[list[float]]", vsplines[0]))):
        row = _nurbs_curve_pts(
            _column(vsplines, i),
            dv,
            splinesteps=sv,
            u=v,
            type=tv,
            mult=mv,
            knots=kv,
        )
        out.append([[float(c) for c in p] for p in row])
    return out


def nurbs_patch_point(
    patch: list[list[list[float]]],
    u: float,
    v: float,
    degree: tuple[int, int] = (3, 3),
    weights: list[list[float]] | None = None,
    type: tuple[NurbsType, NurbsType] = (NurbsType.CLAMPED, NurbsType.CLAMPED),  # noqa: A002
    mult: tuple[int | None, int | None] = (None, None),
    knots: tuple[list[float] | None, list[float] | None] = (None, None),
) -> list[float]:
    """Evaluate a NURBS surface patch at a single (u, v) parameter pair.

    Args:
        patch: A rectangular array of control points, or a NURBS parameter list.
        u: Parameter value along U in ``[0, 1]``.
        v: Parameter value along V in ``[0, 1]``.
        degree: Per-direction degree ``(u_degree, v_degree)`` (default ``(3,3)``).
        weights: A weight matrix for rational NURBS.
        type: Per-direction boundary condition ``(u_type, v_type)``.
        mult: Per-direction knot multiplicities ``(u_mult, v_mult)``.
        knots: Per-direction knot vectors ``(u_knots, v_knots)``.

    Returns:
        A single ``[x, y, z]`` point.
    """

    if weights is not None:
        wpatch: list[list[list[float]]] = cast("list[list[list[float]]]", patch)
        wpatch = [
            [
                list(np.asarray(wpatch[i][j], dtype=float) * weights[i][j]) + [float(weights[i][j])]
                for j in range(len(wpatch[0]))
            ]
            for i in range(len(wpatch))
        ]
        pt = nurbs_patch_point(
            wpatch,
            u,
            v,
            degree,
            type=type,
            mult=mult,
            knots=knots,
        )
        w_val = pt[-1]
        return [float(c) / w_val for c in pt[:-1]] if w_val else [float(c) for c in pt[:-1]]

    du, dv = degree
    tu, tv = type
    mu, mv = mult
    ku, kv = knots

    inner = [
        _nurbs_curve_pts(ctrl, dv, u=[v], type=tv, mult=mv, knots=kv)[0]
        for ctrl in cast("list[list[list[float]]]", patch)
    ]
    return list(_nurbs_curve_pts(inner, du, u=[u], type=tu, mult=mu, knots=ku)[0])


def nurbs_vnf(
    patch: list[list[list[float]]],
    degree: tuple[int, int] = (3, 3),
    splinesteps: tuple[int | None, int | None] = (16, 16),
    weights: list[list[float]] | None = None,
    type: tuple[NurbsType, NurbsType] = (NurbsType.CLAMPED, NurbsType.CLAMPED),  # noqa: A002
    mult: tuple[int | None, int | None] = (None, None),
    knots: tuple[list[float] | None, list[float] | None] = (None, None),
    style: str = "default",
    reverse: bool = False,
    caps: "CapsSpec | None" = None,
) -> "VNF":
    """Mesh a NURBS surface patch into a ``[vertices, faces]`` VNF.

    Samples the patch with :func:`nurbs_patch_points` and builds the mesh using
    :meth:`~pybosl2.vnf.VNF.vertex_array`.  Row/column wrapping is determined
    by the *type* parameter — ``CLOSED`` directions produce a continuous tube
    or torus.

    Args:
        patch: Control-point grid or a NURBS parameter list.
        degree: Scalar or ``[u, v]`` degree.
        splinesteps: Scalar or ``[u, v]`` samples per knot span (default 16).
        weights: A weight matrix as for :func:`nurbs_patch_points`.
        type: A :class:`NurbsType` applied to both directions, or a
              ``(u_type, v_type)`` pair.
        mult: Knot multiplicities as for :func:`nurbs_patch_points`.
        knots: Knot vectors as for :func:`nurbs_patch_points`.
        style: :meth:`~pybosl2.vnf.VNF.vertex_array` triangulation style.
        reverse: If True, flip every face normal.
        caps: A :data:`~pybosl2.caps.CapsSpec` to cap a
              ``[CLAMPED, CLOSED]`` or ``[CLOSED, CLAMPED]`` surface.
              ``None`` means no caps.

    Returns:
        A :class:`~pybosl2.vnf.VNF`.

    Raises:
        AssertionError: If *caps* are requested on a type that doesn't support
                        caps (must be paired ``CLAMPED``/``CLOSED`` or the reverse).

    Examples:
        A cubic B-spline surface patch meshed into a solid:

        .. pythonscad-example::

            from pybosl2 import nurbs_vnf

            patch = [
                [[-50, 50, 0], [-16, 50, 20], [16, 50, 20], [50, 50, 0]],
                [[-50, 16, 20], [-16, 16, 40], [16, 16, 40], [50, 16, 20]],
                [[-50, -16, 20], [-16, -16, 40], [16, -16, 40], [50, -16, 20]],
                [[-50, -50, 0], [-16, -50, 20], [16, -50, 20], [50, -50, 0]],
            ]
            nurbs_vnf(patch, 3).polyhedron().show()
    """
    from pybosl2.caps import CapType, norm_caps
    from pybosl2.vnf import VNF

    assert is_nurbs_patch(patch), "patch must be a rectangular array of points."
    assert _valid_surface_type(type), "type must be a NurbsType or a pair of NurbsTypes."
    type_list: list[NurbsType] = _force_list2(type)  # type: ignore[assignment]

    cap_specs: list["CapSpec"] = norm_caps(caps) if caps is not None else norm_caps(CapType.NONE)
    havecaps = any(cs.cap_type != CapType.NONE for cs in cap_specs)
    cap_type_pairs = ([NurbsType.CLAMPED, NurbsType.CLOSED], [NurbsType.CLOSED, NurbsType.CLAMPED])
    assert not havecaps or type_list in cap_type_pairs, "caps require [CLAMPED,CLOSED] or [CLOSED,CLAMPED]."
    flip = havecaps and type_list[0] == NurbsType.CLOSED
    pts = nurbs_patch_points(
        patch,
        degree=degree,
        splinesteps=splinesteps,
        type=type,
        mult=mult,
        knots=knots,
        weights=weights,
    )
    if flip:
        pts = [list(row) for row in zip(*pts, strict=False)]
    return VNF.vertex_array(
        pts,
        style=style,
        row_wrap=type_list[1 if flip else 0] == NurbsType.CLOSED,
        col_wrap=type_list[0 if flip else 1] == NurbsType.CLOSED,
        reverse=reverse,
        caps=cap_specs if havecaps else None,
    )


# ---------------------------------------------------------------------------
# Section: degree elevation
# ---------------------------------------------------------------------------


def _nip(i: int, p: int, u: float, knot_vector: Sequence[float]) -> float:
    """The i-th B-spline basis function of degree *p* at *u*.

    Args:
        i: The basis function index.
        p: The degree.
        u: The parameter value at which to evaluate.
        knot_vector: The knot vector.

    Returns:
        The basis function value ``N_{i,p}(u)``.
    """
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


def _greville(knot_vector: Sequence[float], p: int) -> list[float]:
    """Compute the Greville abscissae for a B-spline of degree *p*."""
    sides = len(knot_vector) - p - 2
    return [sum(knot_vector[i + 1 : i + p + 1]) / p for i in range(sides + 1)]


def _increment_knot_mults(knot_vector: Sequence[float]) -> list[float]:
    """Increment every knot multiplicity by 1 for degree elevation."""
    out: list[float] = []
    i = 0
    while i < len(knot_vector):
        j = i
        while j < len(knot_vector) and math.isclose(knot_vector[j], knot_vector[i], rel_tol=0, abs_tol=EPSILON):
            j += 1
        out += [knot_vector[i]] * (j - i + 1)
        i = j
    return out


def _elevate_once(
    ctrl: list[np.ndarray], p: int, knot_vector: Sequence[float]
) -> tuple[list[list[float]], list[float], int]:
    """Elevate the degree of a B-spline by 1.

    Args:
        ctrl: The control points.
        p: The current degree.
        knot_vector: The current knot vector.

    Returns:
        A tuple of ``(new_control_points, new_knot_vector, new_degree)``.
    """
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
    control: list[list[float]],
    degree: int | None = None,
    knots: list[float] | None = None,
    type: NurbsType = NurbsType.CLAMPED,  # noqa: A002
    times: int = 1,
    weights: list[float] | None = None,
    mult: list[int] | None = None,
) -> tuple[tuple[NurbsType, NurbsType], int, list[list[float]], list[float], None, list[float] | None]:
    """Raise a NURBS/B-spline curve's degree by *times*.

    Elevates the curve degree while preserving its shape.  Only
    :attr:`NurbsType.CLAMPED` and :attr:`NurbsType.OPEN` splines are
    supported (as in BOSL2).  Rational curves are elevated in homogeneous
    space and de-homogenised.

    Args:
        control: Control points or a NURBS parameter list.
        degree: The current degree.  Required unless *control* is a parameter list.
        knots: The current knot vector.
        type: The boundary condition — must be :attr:`NurbsType.CLAMPED` or
              :attr:`NurbsType.OPEN`.
        times: How many times to elevate (default 1).  ``times=0`` returns the
               input unchanged.
        weights: Weights for a rational NURBS curve.
        mult: Knot multiplicities.

    Returns:
        A NURBS parameter list ``[type, new_degree, control, knots, None, weights]``.

    Raises:
        AssertionError: If *type* is not ``CLAMPED`` or ``OPEN``.
    """
    if times == 0:
        return (type, degree, control, knots, mult, weights)  # type: ignore[return-value]

    if weights is not None:
        assert len(weights) == len(control), "weights must match the number of control points."
        homo = [
            list(np.asarray(control[i], dtype=float) * weights[i]) + [float(weights[i])] for i in range(len(control))
        ]
        radius = nurbs_elevate_degree(homo, degree, knots=knots, type=type, times=times, mult=mult)
        new_w: list[float] = [pt[-1] for pt in radius[2]]
        new_ctrl: list[list[float]] = [list(np.asarray(pt[:-1], dtype=float) / pt[-1]) for pt in radius[2]]
        return (radius[0], radius[1], new_ctrl, radius[3], None, new_w)

    assert type in (NurbsType.CLAMPED, NurbsType.OPEN), "nurbs_elevate_degree: type must be CLAMPED or OPEN."
    assert is_num(times) and times >= 1, "times must be a positive integer."
    assert degree is not None, "degree must be provided."
    sides = len(control)
    if knots is None and mult is None:
        xknots = (
            [float(x) for x in lerpn(0, 1, sides - degree + 1)]
            if type == NurbsType.CLAMPED
            else [float(x) for x in lerpn(0, 1, sides + degree + 1)]
        )
    elif mult is None:
        xknots = list(knots or [])
    else:
        m = len(mult)
        adj = ([degree + 1] + list(mult[1:-1]) + [degree + 1]) if (type == NurbsType.CLAMPED and m >= 2) else list(mult)
        positions = list(knots) if knots is not None else [0 if m == 1 else i / (m - 1) for i in range(m)]
        exp = _expand_knots(positions, adj)
        xknots = exp[degree : len(exp) - degree] if type == NurbsType.CLAMPED else exp

    u_full = (
        ([xknots[0]] * degree + list(xknots) + [xknots[-1]] * degree) if type == NurbsType.CLAMPED else list(xknots)
    )
    q, u_new, p_new = _elevate_once(control, degree, u_full)  # type: ignore[arg-type]
    new_knots = u_new[degree + 1 : len(u_new) - degree - 1] if type == NurbsType.CLAMPED else u_new
    if times == 1:
        return ((type, type), p_new, q, new_knots, None, None)
    return nurbs_elevate_degree(q, p_new, new_knots, type=type, times=times - 1)

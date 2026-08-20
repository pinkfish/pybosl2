# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/nurbs.py
#    Pure-Python port of the NURBS *evaluation* API from BOSL2's nurbs.scad, as two classes:
#    :class:`NurbsCurve` (evaluate a curve, sample it into a path, raise its degree) and
#    :class:`NurbsPatch` (sample a surface, mesh it into a VNF). All three flavours -- clamped,
#    open and closed -- with weights (rational NURBS), knot multiplicities, and explicit knot
#    vectors are supported.
#
#    A curve or patch carries its own definition, so operations chain off the object rather than
#    threading six arguments through free functions::
#
#        NurbsCurve(ctrl, 3).curve(splinesteps=12).stroke(width=3)
#        NurbsCurve(ctrl, 3).elevate_degree().curve()
#        NurbsPatch(patch, (3, 3)).vnf(splinesteps=(8, 8)).polyhedron()
#
#    The evaluation kernel is the standard de Boor algorithm on a knot vector built exactly as
#    BOSL2 builds it; the meshed results (including the classic rational-NURBS sphere) are rendered
#    and measured in tests/test_stl_render.py. :meth:`NurbsCurve.curve` returns a
#    :class:`~pybosl2.path2d.Path2D` (2-D control points) or :class:`~pybosl2.path3d.Path3D` (3-D),
#    and :meth:`NurbsPatch.vnf` returns a :class:`~pybosl2.vnf.VNF`.
#
#    NOT ported (a large follow-up): the interpolation solvers ``nurbs_interp`` /
#    ``nurbs_interp_surface`` (constrained least-squares fitting) and the ``debug_nurbs`` display
#    modules.
#
# FileSummary: NURBS
# DocCategory: Paths, regions & surfaces
# FileGroup: BOSL2

"""NURBS curve/surface evaluation and meshing (de Boor)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence, TypeVar

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pybosl2.caps import CapSpec, CapsSpec
    from pybosl2.paths import Path

import math
from enum import Enum

import numpy as np

from pybosl2.math import EPSILON, lerpn
from pybosl2.vnf import VNF, VnfStyle

# ── type aliases ─────────────────────────────────────────────────────────

#: A single point: any sequence of coordinates, or a numpy array of them.
PointLike = Sequence[float] | np.ndarray

_T = TypeVar("_T")

__all__ = [
    "NurbsType",
    "NurbsCurve",
    "NurbsPatch",
]


# ---------------------------------------------------------------------------
# Section: NURBS type enum
# ---------------------------------------------------------------------------


class NurbsType(Enum):
    """NURBS curve/surface boundary condition.

    Determines how the knot vector is built and whether the curve/surface wraps.
    """

    CLAMPED = "clamped"
    """Clamped (end-point-interpolating) — the default."""

    OPEN = "open"
    """Open (non-interpolating) B-spline."""

    CLOSED = "closed"
    """Closed (periodic) — start and end connect."""


# ---------------------------------------------------------------------------
# Section: knot-vector helpers
# ---------------------------------------------------------------------------


def _extend_knot_mult(mult: Sequence[int], nxt: int, length: int) -> list[int]:
    """Extend a knot multiplicity vector periodically to sum to *length*.

    Args:
        mult: The multiplicity list to extend.
        nxt: The index of the next multiplicity to repeat.
        length: The target sum of the multiplicities.

    Returns:
        The extended multiplicity list.

    """
    out = list(mult)
    n = len(out)
    while sum(out) < length:
        out.append(out[nxt % n])
        nxt += 1
    total = sum(out)
    if total > length:
        out[-1] -= total - length
    return out


def _extend_knot_vector(knots: Sequence[float], nxt: int, length: int) -> list[float]:
    """Extend a knot vector periodically to *length* entries.

    Args:
        knots: The knot vector to extend.
        nxt: The index of the next knot from which to compute spacing.
        length: The target length of the knot vector.

    Returns:
        The extended knot vector.

    """
    out = list(knots)
    while len(out) < length:
        out.append(out[-1] + out[nxt + 1] - out[nxt])
        nxt += 1
    return out


def _expand_knots(knots: Sequence[float], mult: Sequence[int]) -> list[float]:
    """Expand a compact knot vector by repeating each knot by its multiplicity."""
    out: list[float] = []
    for i, repeat in enumerate(mult):
        out += [float(knots[i])] * repeat
    return out


def _knot_multiplicities(
    nurbs_type: NurbsType,
    degree: int,
    count: int,
    mult: Sequence[int] | None,
) -> list[int]:
    """Return the knot multiplicities of a uniform knot vector.

    Args:
        nurbs_type: The boundary condition of the curve.
        degree: The curve degree.
        count: The number of control points (already extended, for closed curves).
        mult: Caller-supplied multiplicities, or ``None`` for the natural ones.

    Returns:
        One multiplicity per distinct knot value.

    """
    if nurbs_type == NurbsType.CLAMPED:
        base = list(mult) if mult is not None else [1] * (count - degree + 1)
        return [degree + 1] + base[1:-1] + [degree + 1]
    if mult is None:
        return [1] * (count + degree + 1)
    if nurbs_type == NurbsType.OPEN:
        return list(mult)
    last = mult[-1] + mult[0] - 1
    return _extend_knot_mult(list(mult[:-1]) + [last], 1, count + degree + 1)


def _knot_vector(
    nurbs_type: NurbsType,
    degree: int,
    count: int,
    mult: Sequence[int] | None,
    knots: Sequence[float] | None,
) -> list[float]:
    """Return the full (expanded) knot vector used to evaluate a curve.

    With no explicit *knots* the vector is uniform, built from the multiplicities
    of :func:`_knot_multiplicities`.  With explicit *knots* the vector is expanded
    by *mult* (when given) and then padded for the boundary condition.

    Args:
        nurbs_type: The boundary condition of the curve.
        degree: The curve degree.
        count: The number of control points (already extended, for closed curves).
        mult: Knot multiplicities, or ``None``.
        knots: An explicit knot vector, or ``None`` for a uniform one.

    Returns:
        The expanded knot vector.

    """
    if knots is None:
        mults = _knot_multiplicities(nurbs_type, degree, count, mult)
        span = len(mults) - 1
        out: list[float] = []
        for i, repeat in enumerate(mults):
            out += [i / span] * repeat
        return out

    expanded = [float(k) for k in knots] if mult is None else _expand_knots(knots, mult)
    if nurbs_type == NurbsType.OPEN:
        return expanded
    if nurbs_type == NurbsType.CLAMPED:
        return [expanded[0]] * degree + expanded + [expanded[-1]] * degree
    return _extend_knot_vector(expanded, 0, count + degree + 1)


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


def _deboor(knot: Sequence[float], ctrl: Sequence[np.ndarray], u: float, p: int, k: int) -> np.ndarray:
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
# Section: homogeneous (rational) helpers
# ---------------------------------------------------------------------------


def _homogeneous(points: Sequence[PointLike], weights: Sequence[float]) -> list[list[float]]:
    """Lift *points* into homogeneous space by scaling each with its weight."""
    if not (len(weights) == len(points)):
        raise ValueError("weights must match the number of control points.")
    return [list(np.asarray(p, dtype=float) * w) + [float(w)] for p, w in zip(points, weights, strict=True)]


def _dehomogenise(point: PointLike) -> list[float]:
    """Project a homogeneous point back by dividing through by its final coordinate."""
    w = float(point[-1])
    return [float(c) / w for c in point[:-1]] if w else [float(c) for c in point[:-1]]


def _column(grid: Sequence[Sequence[_T]], index: int) -> list[_T]:
    """Return column *index* from a 2-D grid."""
    return [row[index] for row in grid]


def _copy_pair(pair: tuple[Sequence[_T] | None, Sequence[_T] | None]) -> tuple[list[_T] | None, list[_T] | None]:
    """Copy a per-direction ``(u, v)`` pair of optional sequences, so callers cannot mutate it."""
    return (
        list(pair[0]) if pair[0] is not None else None,
        list(pair[1]) if pair[1] is not None else None,
    )


# ---------------------------------------------------------------------------
# Section: curve evaluation
# ---------------------------------------------------------------------------


def _sample_params(
    knot: Sequence[float],
    degree: int,
    count: int,
    nurbs_type: NurbsType,
    splinesteps: int | None,
    u: Sequence[float] | None,
) -> list[float]:
    """Return the parameter values at which to evaluate a curve.

    Args:
        knot: The expanded knot vector.
        degree: The curve degree.
        count: The number of control points (already extended, for closed curves).
        nurbs_type: The boundary condition of the curve.
        splinesteps: Samples per knot span, or ``None`` when *u* is given.
        u: Explicit parameters in ``[0, 1]``, or ``None`` when *splinesteps* is given.

    Returns:
        Parameter values in the curve's own knot domain.

    """
    if splinesteps is not None:
        if not (splinesteps > 0):
            raise ValueError("splinesteps must be a positive integer.")
        params: list[float] = []
        for i in range(degree, count):
            if not math.isclose(knot[i], knot[i + 1], rel_tol=0, abs_tol=EPSILON):
                params += [float(x) for x in lerpn(knot[i], knot[i + 1], splinesteps, endpoint=False)]
        if nurbs_type != NurbsType.CLOSED:
            params.append(float(knot[count]))
        return params

    if not (u is not None):
        raise ValueError("Must define exactly one of u and splinesteps.")
    values = [float(x) for x in u]
    if not (all((-1e-12 <= x <= 1 + 1e-12 for x in values))):
        raise ValueError("u must lie in [0, 1].")
    if nurbs_type == NurbsType.CLAMPED:
        return values
    lo, hi = float(knot[degree]), float(knot[count])
    return [(hi - lo) * x + lo for x in values]


def _curve_points(
    control: Sequence[PointLike],
    degree: int,
    splinesteps: int | None = None,
    u: Sequence[float] | None = None,
    mult: Sequence[int] | None = None,
    weights: Sequence[float] | None = None,
    nurbs_type: NurbsType = NurbsType.CLAMPED,
    knots: Sequence[float] | None = None,
) -> list[np.ndarray]:
    """Return the raw points on a NURBS curve as numpy arrays; the kernel behind :class:`NurbsCurve`.

    Args:
        control: The control points.
        degree: The curve degree.
        splinesteps: Samples per knot span.  Mutually exclusive with *u*; when
                     both are ``None`` this defaults to 16.
        u: Explicit parameter values in ``[0, 1]``.  Mutually exclusive with *splinesteps*.
        mult: Knot multiplicities.
        weights: Weights for a rational NURBS curve.
        nurbs_type: The boundary condition.
        knots: An explicit knot vector.

    Returns:
        The evaluated points, one numpy array per parameter value.

    """
    if not (splinesteps is None or u is None):
        raise ValueError("Must define exactly one of u and splinesteps.")
    if splinesteps is None and u is None:
        splinesteps = 16

    if weights is not None:
        rational = _curve_points(
            _homogeneous(control, weights),
            degree,
            splinesteps=splinesteps,
            u=u,
            mult=mult,
            nurbs_type=nurbs_type,
            knots=knots,
        )
        return [np.asarray(pt[:-1], dtype=float) / pt[-1] for pt in rational]

    if not (nurbs_type == NurbsType.CLOSED or len(control) >= degree + 1):
        # pragma: no cover - defensive: NurbsCurve.__init__ makes the same check before any
        # curve can reach this helper, and a CLOSED curve is exempt from it
        raise ValueError(f"Not enough control points for a degree {degree} {nurbs_type.value} curve.")
    ctrl = [np.asarray(p, dtype=float) for p in control]
    if nurbs_type == NurbsType.CLOSED:
        ctrl = ctrl + ctrl[:degree]
    count = len(ctrl)

    knot = _knot_vector(nurbs_type, degree, count, mult, knots)
    params = _sample_params(knot, degree, count, nurbs_type, splinesteps, u)
    return [_deboor(knot, ctrl, val, degree, _findspan(val, degree, knot, count)) for val in params]


# ---------------------------------------------------------------------------
# Section: surface evaluation
# ---------------------------------------------------------------------------


def _patch_grid(
    control: Sequence[Sequence[PointLike]],
    degree: tuple[int, int],
    splinesteps: tuple[int, int],
    u: Sequence[float] | None,
    v: Sequence[float] | None,
    weights: Sequence[Sequence[float]] | None,
    nurbs_type: tuple[NurbsType, NurbsType],
    mult: tuple[Sequence[int] | None, Sequence[int] | None],
    knots: tuple[Sequence[float] | None, Sequence[float] | None],
) -> list[list[list[float]]]:
    """Sample a patch of control points on a grid; the kernel behind :class:`NurbsPatch`.

    Each control column is swept as a U curve, then each resulting row is swept
    as a V curve.  A direction uses its explicit parameter list when given, and
    its *splinesteps* entry otherwise.

    Args:
        control: The rectangular grid of control points.
        degree: Per-direction degree ``(u_degree, v_degree)``.
        splinesteps: Per-direction samples per knot span.
        u: Explicit parameter values along U, or ``None``.
        v: Explicit parameter values along V, or ``None``.
        weights: A weight matrix the same size as *control*, or ``None``.
        nurbs_type: Per-direction boundary condition.
        mult: Per-direction knot multiplicities.
        knots: Per-direction knot vectors.

    Returns:
        A grid (list of rows) of points.

    """
    if weights is not None:
        grid = _patch_grid(
            [_homogeneous(row, wrow) for row, wrow in zip(control, weights, strict=True)],
            degree,
            splinesteps,
            u,
            v,
            None,
            nurbs_type,
            mult,
            knots,
        )
        return [[_dehomogenise(pt) for pt in row] for row in grid]

    u_steps = None if u is not None else splinesteps[0]
    v_steps = None if v is not None else splinesteps[1]
    columns = [
        _curve_points(
            _column(control, j),
            degree[0],
            splinesteps=u_steps,
            u=u,
            mult=mult[0],
            nurbs_type=nurbs_type[0],
            knots=knots[0],
        )
        for j in range(len(control[0]))
    ]
    out: list[list[list[float]]] = []
    for i in range(len(columns[0])):
        row = _curve_points(
            _column(columns, i),
            degree[1],
            splinesteps=v_steps,
            u=v,
            mult=mult[1],
            nurbs_type=nurbs_type[1],
            knots=knots[1],
        )
        out.append([[float(c) for c in p] for p in row])
    return out


def _patch_point(
    control: Sequence[Sequence[PointLike]],
    u: float,
    v: float,
    degree: tuple[int, int],
    weights: Sequence[Sequence[float]] | None,
    nurbs_type: tuple[NurbsType, NurbsType],
    mult: tuple[Sequence[int] | None, Sequence[int] | None],
    knots: tuple[Sequence[float] | None, Sequence[float] | None],
) -> list[float]:
    """Evaluate a patch of control points at one ``(u, v)`` pair.

    Args:
        control: The rectangular grid of control points.
        u: The parameter along U in ``[0, 1]``.
        v: The parameter along V in ``[0, 1]``.
        degree: Per-direction degree ``(u_degree, v_degree)``.
        weights: A weight matrix the same size as *control*, or ``None``.
        nurbs_type: Per-direction boundary condition.
        mult: Per-direction knot multiplicities.
        knots: Per-direction knot vectors.

    Returns:
        A single point.

    """
    if weights is not None:
        homogeneous = _patch_point(
            [_homogeneous(row, wrow) for row, wrow in zip(control, weights, strict=True)],
            u,
            v,
            degree,
            None,
            nurbs_type,
            mult,
            knots,
        )
        return _dehomogenise(homogeneous)

    # collapse each control row along V, then the resulting column along U
    inner = [
        _curve_points(row, degree[1], u=[v], mult=mult[1], nurbs_type=nurbs_type[1], knots=knots[1])[0]
        for row in control
    ]
    point = _curve_points(inner, degree[0], u=[u], mult=mult[0], nurbs_type=nurbs_type[0], knots=knots[0])[0]
    return [float(c) for c in point]


# ---------------------------------------------------------------------------
# Section: degree elevation
# ---------------------------------------------------------------------------


def _nip(i: int, p: int, u: float, knot_vector: Sequence[float]) -> float:
    """Return the i-th B-spline basis function of degree *p* at *u*.

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
    ctrl: Sequence[Sequence[float]], p: int, knot_vector: Sequence[float]
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
    return [[float(c) for c in row] for row in new_ctrl], knots_new, p_new


def _elevation_knots(
    count: int,
    degree: int,
    nurbs_type: NurbsType,
    knots: Sequence[float] | None,
    mult: Sequence[int] | None,
) -> list[float]:
    """Return the compact knot vector a curve is elevated on.

    Args:
        count: The number of control points.
        degree: The current curve degree.
        nurbs_type: The boundary condition (``CLAMPED`` or ``OPEN``).
        knots: An explicit knot vector, or ``None`` for a uniform one.
        mult: Knot multiplicities, or ``None``.

    Returns:
        The knot vector without the clamped end padding.

    """
    if knots is None and mult is None:
        span = count - degree + 1 if nurbs_type == NurbsType.CLAMPED else count + degree + 1
        return [float(x) for x in lerpn(0, 1, span)]
    if mult is None:
        return [float(k) for k in knots or []]
    m = len(mult)
    adjusted = (
        ([degree + 1] + list(mult[1:-1]) + [degree + 1]) if (nurbs_type == NurbsType.CLAMPED and m >= 2) else list(mult)
    )
    positions = [float(k) for k in knots] if knots is not None else [0.0 if m == 1 else i / (m - 1) for i in range(m)]
    expanded = _expand_knots(positions, adjusted)
    return expanded[degree : len(expanded) - degree] if nurbs_type == NurbsType.CLAMPED else expanded


def _elevate_curve(
    control: Sequence[Sequence[float]],
    degree: int,
    nurbs_type: NurbsType,
    knots: Sequence[float] | None,
    mult: Sequence[int] | None,
    weights: Sequence[float] | None,
    times: int,
) -> tuple[list[list[float]], int, list[float] | None, list[float] | None]:
    """Raise a curve's degree *times* times, preserving its shape.

    Rational curves are elevated in homogeneous space and de-homogenised, so the
    returned weights belong to the returned control points.

    Args:
        control: The control points.
        degree: The current degree.
        nurbs_type: The boundary condition (``CLAMPED`` or ``OPEN``).
        knots: The current knot vector, or ``None`` for a uniform one.
        mult: Knot multiplicities, or ``None``.
        weights: Weights for a rational curve, or ``None``.
        times: How many times to elevate; 0 returns the input unchanged.

    Returns:
        A tuple of ``(control, degree, knots, weights)``.

    """
    if nurbs_type not in (NurbsType.CLAMPED, NurbsType.OPEN):
        raise ValueError("degree elevation needs a CLAMPED or OPEN curve.")
    if not (times >= 0):
        raise ValueError("times must be zero or a positive integer.")
    points = [[float(c) for c in p] for p in control]
    if times == 0:
        return (
            points,
            degree,
            [float(k) for k in knots] if knots is not None else None,
            [float(w) for w in weights] if weights is not None else None,
        )

    if weights is not None:
        homogeneous, new_degree, new_knots, _ = _elevate_curve(
            _homogeneous(points, weights), degree, nurbs_type, knots, mult, None, times
        )
        return (
            [_dehomogenise(pt) for pt in homogeneous],
            new_degree,
            new_knots,
            [float(pt[-1]) for pt in homogeneous],
        )

    compact = _elevation_knots(len(points), degree, nurbs_type, knots, mult)
    full = ([compact[0]] * degree + compact + [compact[-1]] * degree) if nurbs_type == NurbsType.CLAMPED else compact
    new_ctrl, new_full, new_degree = _elevate_once(points, degree, full)
    new_knots = new_full[degree + 1 : len(new_full) - degree - 1] if nurbs_type == NurbsType.CLAMPED else new_full
    if times == 1:
        return new_ctrl, new_degree, new_knots, None
    return _elevate_curve(new_ctrl, new_degree, nurbs_type, new_knots, None, None, times - 1)


# ---------------------------------------------------------------------------
# Section: NURBS curve
# ---------------------------------------------------------------------------


class NurbsCurve:
    """A NURBS curve: control points plus their knot structure, with every operation as a method.

    The object owns its whole definition -- degree, boundary condition, knot vector, knot
    multiplicities and rational weights -- so operations chain off it instead of repeating six
    arguments at every call (BOSL2's ``nurbs_curve()`` / ``nurbs_elevate_degree()``)::

        NurbsCurve(ctrl, 3).curve(splinesteps=12).stroke(width=3)
        NurbsCurve(ctrl, 3).elevate_degree(2).point(0.5)

    Evaluate at chosen parameters with :meth:`point` / :meth:`points`, sample the whole curve into
    a path with :meth:`curve`, and raise the degree (keeping the shape) with :meth:`elevate_degree`.
    Indexing, iteration and ``len()`` walk the control points.

    Args:
        control: The control points -- a sequence of ``[x,y]`` or ``[x,y,z]`` points.
        degree: The curve degree.
        nurbs_type: The boundary condition -- :attr:`NurbsType.CLAMPED` (the default),
                    :attr:`NurbsType.OPEN` or :attr:`NurbsType.CLOSED`.
        knots: An explicit knot vector, or ``None`` for a uniform one.
        mult: Knot multiplicities, or ``None``.
        weights: Weights for a rational NURBS curve, or ``None``.

    Examples:
        A cubic clamped NURBS curve through five control points, swept into a tube:

        .. pythonscad-example::

            from pybosl2 import NurbsCurve

            ctrl = [[0, 0, 0], [10, 20, 5], [30, -10, 10], [50, 20, 0], [60, 0, 15]]
            NurbsCurve(ctrl, 3).curve(splinesteps=12).stroke(width=3).show()

    """

    _control: np.ndarray
    _degree: int
    _nurbs_type: NurbsType
    _knots: list[float] | None
    _mult: list[int] | None
    _weights: list[float] | None

    def __init__(
        self,
        control: Path | Sequence[Sequence[float]] | np.ndarray,
        degree: int,
        nurbs_type: NurbsType = NurbsType.CLAMPED,
        knots: Sequence[float] | None = None,
        mult: Sequence[int] | None = None,
        weights: Sequence[float] | None = None,
    ) -> None:
        """Initialize a NURBS curve from its control points and knot structure.

        Args:
            control: A sequence of 2-D or 3-D control points (lists, a Path, or a numpy array).
            degree: The curve degree.
            nurbs_type: The boundary condition.
            knots: An explicit knot vector, or ``None`` for a uniform one.
            mult: Knot multiplicities, or ``None``.
            weights: Weights for a rational NURBS curve, or ``None``.

        """
        pts = np.array([[float(c) for c in p] for p in control], dtype=float)
        if not (pts.ndim == 2):
            raise ValueError(f"control points must be a 2-D array (N points x D dims), got shape {pts.shape}")
        if pts.shape[1] not in (2, 3):
            raise ValueError(f"control points must be 2-D or 3-D, got {pts.shape[1]} components per point")
        if not (isinstance(degree, int)):
            raise ValueError(f"degree must be a positive integer, got {degree!r}")
        if not (degree >= 1):
            raise ValueError(f"degree must be a positive integer, got {degree!r}")
        if not (isinstance(nurbs_type, NurbsType)):
            raise ValueError(f"unknown NURBS type: {nurbs_type!r}")
        if not (nurbs_type == NurbsType.CLOSED or pts.shape[0] >= degree + 1):
            raise ValueError(f"a degree {degree} {nurbs_type.value} curve needs at least {degree + 1} control points")
        if not (weights is None or len(weights) == pts.shape[0]):
            raise ValueError("weights must match the number of control points.")
        pts.flags.writeable = False  # the definition is fixed once built; make a new curve to change it
        self._control = pts
        self._degree = degree
        self._nurbs_type = nurbs_type
        self._knots = [float(k) for k in knots] if knots is not None else None
        self._mult = [int(m) for m in mult] if mult is not None else None
        self._weights = [float(w) for w in weights] if weights is not None else None

    def __len__(self) -> int:
        """Return the number of items."""
        return len(self._control)

    def __getitem__(self, index: int | slice) -> np.ndarray:
        """Return the item at index."""
        return self._control[index]

    def __iter__(self) -> Iterator[np.ndarray]:
        """Return an iterator."""
        return iter(self._control)

    def __repr__(self) -> str:
        """Return a string representation."""
        return f"NurbsCurve({self._control.tolist()}, {self._degree}, {self._nurbs_type})"

    @property
    def array(self) -> np.ndarray:
        """The control points as an (N, dim) numpy array."""
        return self._control

    @property
    def to_list(self) -> list[list[float]]:
        """The control points as a plain list."""
        return self._control.tolist()  # type: ignore[no-any-return]

    @property
    def degree(self) -> int:
        """The curve degree."""
        return self._degree

    @property
    def nurbs_type(self) -> NurbsType:
        """The boundary condition of the curve."""
        return self._nurbs_type

    @property
    def knots(self) -> list[float] | None:
        """The explicit knot vector, or ``None`` when the curve uses a uniform one."""
        return list(self._knots) if self._knots is not None else None

    @property
    def weights(self) -> list[float] | None:
        """The rational weights, or ``None`` for a non-rational curve."""
        return list(self._weights) if self._weights is not None else None

    # -- evaluation ------------------------------------------------------------------------

    def points(self, u: Sequence[float]) -> np.ndarray:
        """Evaluate the curve at each parameter in *u*.

        Args:
            u: Parameter values, each in ``[0, 1]``.

        Returns:
            An ``(len(u), dim)`` ndarray of points.

        """
        return np.array(self._evaluate(u=u), dtype=float)

    def point(self, u: float) -> np.ndarray:
        """Evaluate the curve at a single parameter value.

        Args:
            u: The parameter value in ``[0, 1]``.

        Returns:
            A length-dim ndarray for the point at *u*.

        """
        return self._evaluate(u=[float(u)])[0]

    def curve(self, splinesteps: int = 16) -> Path:
        """Sample the whole curve into a path.

        Takes *splinesteps* uniform samples between every pair of knots, plus a sample at every knot, which is
        BOSL2's ``nurbs_curve(..., splinesteps=)`` behaviour.  Closed curves come back as closed
        paths.

        Args:
            splinesteps: Number of samples per knot span (default 16).

        Returns:
            A :class:`~pybosl2.path2d.Path2D` for 2-D control points, or a
            :class:`~pybosl2.path3d.Path3D` for 3-D ones.

        Examples:
            Sampling a cubic curve and sweeping it into a tube:

            .. pythonscad-example::

                from pybosl2 import NurbsCurve

                ctrl = [[0, 0, 0], [10, 20, 5], [30, -10, 10], [50, 20, 0], [60, 0, 15]]
                NurbsCurve(ctrl, 3).curve(splinesteps=12).stroke(width=3).show()

        """
        from pybosl2.path2d import Path2D
        from pybosl2.path3d import Path3D

        pts = self._evaluate(splinesteps=splinesteps)
        closed = self._nurbs_type == NurbsType.CLOSED
        if self._control.shape[1] == 2:
            return Path2D([[float(p[0]), float(p[1])] for p in pts], closed=closed)
        return Path3D([[float(p[0]), float(p[1]), float(p[2])] for p in pts], closed=closed)

    def elevate_degree(self, times: int = 1) -> NurbsCurve:
        """Raise the curve's degree, keeping its shape.

        Only :attr:`NurbsType.CLAMPED` and :attr:`NurbsType.OPEN` curves can be elevated (as in
        BOSL2).  The result carries the knot vector the elevated curve needs, so it evaluates to
        the same points as this one.

        Args:
            times: How many times to elevate (default 1); 0 returns an equivalent curve.

        Returns:
            A new :class:`NurbsCurve` of degree ``self.degree + times``.

        Raises:
            AssertionError: If the curve is :attr:`NurbsType.CLOSED`, or *times* is negative.

        """
        control, degree, knots, weights = _elevate_curve(
            self.to_list, self._degree, self._nurbs_type, self._knots, self._mult, self._weights, times
        )
        mult = self._mult if times == 0 else None
        return NurbsCurve(control, degree, self._nurbs_type, knots, mult, weights)

    def _evaluate(self, splinesteps: int | None = None, u: Sequence[float] | None = None) -> list[np.ndarray]:
        """Return the raw evaluated points for *splinesteps* samples per span, or at the parameters *u*."""
        return _curve_points(
            self.to_list,
            self._degree,
            splinesteps=splinesteps,
            u=u,
            mult=self._mult,
            weights=self._weights,
            nurbs_type=self._nurbs_type,
            knots=self._knots,
        )


# ---------------------------------------------------------------------------
# Section: NURBS surface patch
# ---------------------------------------------------------------------------


class NurbsPatch:
    """A NURBS surface patch: a rectangular grid of control points, with its knot structure.

    The surface counterpart of :class:`NurbsCurve` (BOSL2's ``nurbs_patch_points()`` /
    ``nurbs_vnf()``).  Every per-direction setting is a ``(u, v)`` pair -- degree, boundary
    condition, knot multiplicities, knot vectors and splinesteps::

        NurbsPatch(patch, (3, 3)).vnf(splinesteps=(8, 8)).polyhedron()

    Evaluate single points with :meth:`point`, a grid of chosen parameters with :meth:`points`,
    a uniformly sampled grid with :meth:`surface`, and mesh it with :meth:`vnf`.  Indexing,
    iteration and ``len()`` walk the control-point rows.

    Args:
        control: A rectangular grid (rows of ``[x,y,z]`` control points).
        degree: Per-direction degree ``(u_degree, v_degree)`` (default ``(3,3)``).
        nurbs_type: Per-direction boundary condition ``(u_type, v_type)``.
        knots: Per-direction knot vectors ``(u_knots, v_knots)``.
        mult: Per-direction knot multiplicities ``(u_mult, v_mult)``.
        weights: A weight matrix the same size as *control* for rational NURBS, or ``None``.

    Examples:
        A cubic B-spline surface patch meshed into a solid:

        .. pythonscad-example::

            from pybosl2 import NurbsPatch

            patch = [
                [[-50, 50, 0], [-16, 50, 20], [16, 50, 20], [50, 50, 0]],
                [[-50, 16, 20], [-16, 16, 40], [16, 16, 40], [50, 16, 20]],
                [[-50, -16, 20], [-16, -16, 40], [16, -16, 40], [50, -16, 20]],
                [[-50, -50, 0], [-16, -50, 20], [16, -50, 20], [50, -50, 0]],
            ]
            NurbsPatch(patch, (3, 3)).vnf().polyhedron().show()

    """

    _control: np.ndarray
    _degree: tuple[int, int]
    _nurbs_type: tuple[NurbsType, NurbsType]
    _knots: tuple[list[float] | None, list[float] | None]
    _mult: tuple[list[int] | None, list[int] | None]
    _weights: list[list[float]] | None

    def __init__(
        self,
        control: Sequence[Sequence[Sequence[float]]] | np.ndarray,
        degree: tuple[int, int] = (3, 3),
        nurbs_type: tuple[NurbsType, NurbsType] = (NurbsType.CLAMPED, NurbsType.CLAMPED),
        knots: tuple[Sequence[float] | None, Sequence[float] | None] = (None, None),
        mult: tuple[Sequence[int] | None, Sequence[int] | None] = (None, None),
        weights: Sequence[Sequence[float]] | None = None,
    ) -> None:
        """Initialize a NURBS patch from a grid of control points and its knot structure.

        Args:
            control: A rectangular grid of 3-D control points.
            degree: Per-direction degree ``(u_degree, v_degree)``.
            nurbs_type: Per-direction boundary condition ``(u_type, v_type)``.
            knots: Per-direction knot vectors ``(u_knots, v_knots)``.
            mult: Per-direction knot multiplicities ``(u_mult, v_mult)``.
            weights: A weight matrix the same size as *control*, or ``None``.

        """
        if not (NurbsPatch.is_patch(control)):
            raise ValueError("control must be a rectangular grid of points.")
        pts = np.array(control, dtype=float)
        if not (pts.ndim == 3):
            raise ValueError(f"patch must be a 3-D array (rows x cols x dim), got shape {pts.shape}")
        if not (pts.shape[2] == 3):
            raise ValueError(f"patch control points must be 3-D, got {pts.shape[2]} components")
        if not (all((isinstance(d, int) and d >= 1 for d in degree))):
            raise ValueError(f"degree must be positive integers, got {degree!r}")
        if not (all((isinstance(t, NurbsType) for t in nurbs_type))):
            raise ValueError(f"unknown NURBS type: {nurbs_type!r}")
        if not (weights is None or np.asarray(weights, dtype=float).shape == pts.shape[:2]):
            raise ValueError("weights must be the same size as the control-point grid.")
        pts.flags.writeable = False  # the definition is fixed once built; make a new patch to change it
        self._control = pts
        self._degree = (degree[0], degree[1])
        self._nurbs_type = (nurbs_type[0], nurbs_type[1])
        self._knots = _copy_pair(knots)
        self._mult = _copy_pair(mult)
        self._weights = [[float(w) for w in row] for row in weights] if weights is not None else None

    def __len__(self) -> int:
        """Return the number of items."""
        return len(self._control)

    def __getitem__(self, index: int | slice) -> np.ndarray:
        """Return the item at index."""
        return self._control[index]

    def __iter__(self) -> Iterator[np.ndarray]:
        """Return an iterator."""
        return iter(self._control)

    def __repr__(self) -> str:
        """Return a string representation."""
        rows, cols = self._control.shape[:2]
        return f"NurbsPatch(<{rows}x{cols} grid>, {self._degree}, {self._nurbs_type})"

    @staticmethod
    def is_patch(x: Any) -> bool:
        """Check if *x* looks like a NURBS patch (BOSL2 ``is_nurbs_patch()``).

        Args:
            x: The object to test.

        Returns:
            True if *x* is a rectangular 2-D array of point vectors with equal-length rows.

        """
        return bool(
            isinstance(x, (list, tuple, np.ndarray))
            and len(x)
            and isinstance(x[0], (list, tuple, np.ndarray))
            and len(x[0])
            and isinstance(x[0][0], (list, tuple, np.ndarray))
            and len(x[0]) == len(x[-1])
        )

    @property
    def array(self) -> np.ndarray:
        """The control points as a (rows, cols, 3) numpy array."""
        return self._control

    @property
    def to_list(self) -> list[list[list[float]]]:
        """The control-point grid as a plain list of rows."""
        return self._control.tolist()  # type: ignore[no-any-return]

    @property
    def degree(self) -> tuple[int, int]:
        """The per-direction degree ``(u_degree, v_degree)``."""
        return self._degree

    @property
    def nurbs_type(self) -> tuple[NurbsType, NurbsType]:
        """The per-direction boundary condition ``(u_type, v_type)``."""
        return self._nurbs_type

    @property
    def weights(self) -> list[list[float]] | None:
        """The rational weight matrix, or ``None`` for a non-rational patch."""
        return [list(row) for row in self._weights] if self._weights is not None else None

    # -- evaluation ------------------------------------------------------------------------

    def point(self, u: float, v: float) -> np.ndarray:
        """Evaluate the surface at a single ``(u, v)`` parameter pair.

        Args:
            u: The parameter along U in ``[0, 1]``.
            v: The parameter along V in ``[0, 1]``.

        Returns:
            A length-3 ndarray for the point at ``(u, v)``.

        """
        return np.array(
            _patch_point(self.to_list, u, v, self._degree, self._weights, self._nurbs_type, self._mult, self._knots),
            dtype=float,
        )

    def points(self, u: Sequence[float], v: Sequence[float]) -> np.ndarray:
        """Evaluate the surface on the grid of parameters *u* x *v*.

        Args:
            u: Parameter values along U, each in ``[0, 1]``.
            v: Parameter values along V, each in ``[0, 1]``.

        Returns:
            A ``(len(u), len(v), 3)`` ndarray of surface points.

        """
        return np.array(self._grid(u=u, v=v), dtype=float)

    def surface(self, splinesteps: tuple[int, int] = (16, 16)) -> np.ndarray:
        """Sample the whole surface on a uniform grid.

        Args:
            splinesteps: Per-direction samples per knot span (default ``(16,16)``).

        Returns:
            A ``(rows, cols, 3)`` ndarray of surface points.

        """
        return np.array(self._grid(splinesteps=splinesteps), dtype=float)

    def vnf(
        self,
        splinesteps: tuple[int, int] = (16, 16),
        style: VnfStyle = VnfStyle.DEFAULT,
        reverse: bool = False,
        caps: "CapsSpec | None" = None,
    ) -> VNF:
        """Mesh the surface into a VNF.

        Samples the patch with :meth:`surface` and builds the mesh with
        :meth:`~pybosl2.vnf.VNF.vertex_array`.  Wrapping follows the boundary condition --
        ``CLOSED`` directions produce a continuous tube or torus.

        Args:
            splinesteps: Per-direction samples per knot span (default ``(16,16)``).
            style: :meth:`~pybosl2.vnf.VNF.vertex_array` triangulation style.
            reverse: If True, flip every face normal.
            caps: A :data:`~pybosl2.caps.CapsSpec` closing the open ends of a
                  ``(CLAMPED, CLOSED)`` or ``(CLOSED, CLAMPED)`` surface; ``None`` for no caps.

        Returns:
            A :class:`~pybosl2.vnf.VNF`.

        Raises:
            AssertionError: If *caps* are requested on a patch that isn't paired
                            ``CLAMPED``/``CLOSED`` (or the reverse).

        Examples:
            Meshing a cubic B-spline patch into a solid:

            .. pythonscad-example::

                from pybosl2 import NurbsPatch

                patch = [
                    [[-50, 50, 0], [-16, 50, 20], [16, 50, 20], [50, 50, 0]],
                    [[-50, 16, 20], [-16, 16, 40], [16, 16, 40], [50, 16, 20]],
                    [[-50, -16, 20], [-16, -16, 40], [16, -16, 40], [50, -16, 20]],
                    [[-50, -50, 0], [-16, -50, 20], [16, -50, 20], [50, -50, 0]],
                ]
                NurbsPatch(patch, (3, 3)).vnf(splinesteps=(10, 10)).polyhedron().show()

        """
        from pybosl2.caps import CapType, norm_caps

        cap_specs: list["CapSpec"] = norm_caps(caps if caps is not None else CapType.NONE)
        havecaps = any(cs.cap_type != CapType.NONE for cs in cap_specs)
        cappable = ((NurbsType.CLAMPED, NurbsType.CLOSED), (NurbsType.CLOSED, NurbsType.CLAMPED))
        if not (not havecaps or self._nurbs_type in cappable):
            raise ValueError("caps require (CLAMPED,CLOSED) or (CLOSED,CLAMPED).")

        # caps close the column-wrapped ends, so a closed U direction is transposed into V
        flip = havecaps and self._nurbs_type[0] == NurbsType.CLOSED
        pts = self._grid(splinesteps=splinesteps)
        if flip:
            pts = [list(row) for row in zip(*pts, strict=False)]
        return VNF.vertex_array(
            pts,
            style=style,
            row_wrap=self._nurbs_type[1 if flip else 0] == NurbsType.CLOSED,
            col_wrap=self._nurbs_type[0 if flip else 1] == NurbsType.CLOSED,
            reverse=reverse,
            caps=cap_specs if havecaps else None,
        )

    def _grid(
        self,
        splinesteps: tuple[int, int] = (16, 16),
        u: Sequence[float] | None = None,
        v: Sequence[float] | None = None,
    ) -> list[list[list[float]]]:
        """Return the sampled grid of surface points, by splinesteps or at explicit parameters."""
        return _patch_grid(
            self.to_list,
            self._degree,
            splinesteps,
            u,
            v,
            self._weights,
            self._nurbs_type,
            self._mult,
            self._knots,
        )

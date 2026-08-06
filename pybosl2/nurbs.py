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
#    BOSL2 builds it; the meshed results (including the classic rational-NURBS sphere) are rendered
#    and measured in tests/test_stl_render.py. :func:`nurbs_curve` returns a :class:`~pybosl2.paths.Path2D` (2-D
#    control points) or :class:`~pybosl2.paths.Path3D` (3-D), and :func:`nurbs_vnf` returns a
#    :class:`~pybosl2.vnf.VNF`.
#
#    Curves are described either by plain arguments (control points, degree, knots, ...) or by a
#    :class:`NurbsCurve` value object, which is what :func:`nurbs_elevate_degree` returns. Surfaces
#    take per-direction ``(u, v)`` pairs for degree, type, splinesteps, mult and knots.
#
#    NOT ported (a large follow-up): the interpolation solvers ``nurbs_interp`` /
#    ``nurbs_interp_surface`` (constrained least-squares fitting) and the ``debug_nurbs`` display
#    modules.
#
# FileSummary: NURBS curve/surface evaluation and meshing (de Boor).
# DocCategory: Paths, regions & surfaces
# FileGroup: BOSL2

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence, TypeVar

if TYPE_CHECKING:
    from pybosl2.caps import CapSpec, CapsSpec
    from pybosl2.paths import Path

import math
from dataclasses import dataclass
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
    "nurbs_curve",
    "nurbs_curve_point",
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
    """The knot multiplicities of a uniform knot vector.

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
    """The full (expanded) knot vector used to evaluate a curve.

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
    assert len(weights) == len(points), "weights must match the number of control points."
    return [list(np.asarray(p, dtype=float) * w) + [float(w)] for p, w in zip(points, weights, strict=True)]


def _dehomogenise(point: PointLike) -> list[float]:
    """Project a homogeneous point back by dividing through by its final coordinate."""
    w = float(point[-1])
    return [float(c) / w for c in point[:-1]] if w else [float(c) for c in point[:-1]]


def _column(grid: Sequence[Sequence[_T]], index: int) -> list[_T]:
    """Return column *index* from a 2-D grid."""
    return [row[index] for row in grid]


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
    """The parameter values at which to evaluate a curve.

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
        assert splinesteps > 0, "splinesteps must be a positive integer."
        params: list[float] = []
        for i in range(degree, count):
            if not math.isclose(knot[i], knot[i + 1], rel_tol=0, abs_tol=EPSILON):
                params += [float(x) for x in lerpn(knot[i], knot[i + 1], splinesteps, endpoint=False)]
        if nurbs_type != NurbsType.CLOSED:
            params.append(float(knot[count]))
        return params

    assert u is not None, "Must define exactly one of u and splinesteps."
    values = [float(x) for x in u]
    assert all(-1e-12 <= x <= 1 + 1e-12 for x in values), "u must lie in [0, 1]."
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
    """The raw points on a NURBS curve as numpy arrays; the kernel behind :func:`nurbs_curve`.

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
    assert splinesteps is None or u is None, "Must define exactly one of u and splinesteps."
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

    assert nurbs_type == NurbsType.CLOSED or len(control) >= degree + 1, (
        f"Not enough control points for a degree {degree} {nurbs_type.value} curve."
    )
    ctrl = [np.asarray(p, dtype=float) for p in control]
    if nurbs_type == NurbsType.CLOSED:
        ctrl = ctrl + ctrl[:degree]
    count = len(ctrl)

    knot = _knot_vector(nurbs_type, degree, count, mult, knots)
    params = _sample_params(knot, degree, count, nurbs_type, splinesteps, u)
    return [_deboor(knot, ctrl, val, degree, _findspan(val, degree, knot, count)) for val in params]


def nurbs_curve(
    control: Path | Sequence[Sequence[float]],
    degree: int,
    splinesteps: int | None = None,
    u: Sequence[float] | None = None,
    mult: Sequence[int] | None = None,
    weights: Sequence[float] | None = None,
    nurbs_type: NurbsType = NurbsType.CLAMPED,
    knots: Sequence[float] | None = None,
) -> Path:
    """Evaluate a NURBS curve, returning its points as a path.

    This is the core curve evaluator — equivalent to BOSL2's ``nurbs_curve()``.
    Give either *splinesteps* (uniform samples between knots, with a sample at
    every knot) or *u* (parameter values in ``[0, 1]``).  *weights* makes it a
    rational NURBS; *mult* / *knots* give knot multiplicities or an explicit
    knot vector.  For a single point use :func:`nurbs_curve_point`.

    Args:
        control: Control points — a sequence of ``[x,y]`` or ``[x,y,z]`` points.
        degree: The curve degree.
        splinesteps: Number of samples per knot span.  Mutually exclusive with
                     *u*; when both are omitted this defaults to 16.
        u: Explicit parameter values in ``[0, 1]``.  Mutually exclusive with
           *splinesteps*.
        mult: Knot multiplicities.
        weights: Weights for rational NURBS.  Must match the number of control points.
        nurbs_type: The boundary condition — :attr:`NurbsType.CLAMPED` (default),
                    :attr:`NurbsType.OPEN`, or :attr:`NurbsType.CLOSED`.
        knots: Explicit knot vector.

    Returns:
        A :class:`~pybosl2.path2d.Path2D` (2-D control points) or
        :class:`~pybosl2.path3d.Path3D` (3-D control points).

    Raises:
        AssertionError: If both *splinesteps* and *u* are given, or if the
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

    pts = _curve_points(
        [[float(c) for c in p] for p in control],
        degree,
        splinesteps=splinesteps,
        u=u,
        mult=mult,
        weights=weights,
        nurbs_type=nurbs_type,
        knots=knots,
    )
    dim = len(pts[0])
    assert dim in (2, 3), "control points must be 2-D or 3-D."
    closed = nurbs_type == NurbsType.CLOSED
    if dim == 2:
        return Path2D([[float(p[0]), float(p[1])] for p in pts], closed=closed)
    return Path3D([[float(p[0]), float(p[1]), float(p[2])] for p in pts], closed=closed)


def nurbs_curve_point(
    control: Path | Sequence[Sequence[float]],
    u: float,
    degree: int,
    mult: Sequence[int] | None = None,
    weights: Sequence[float] | None = None,
    nurbs_type: NurbsType = NurbsType.CLAMPED,
    knots: Sequence[float] | None = None,
) -> list[float]:
    """Evaluate a NURBS curve at a single parameter value.

    The single-point counterpart of :func:`nurbs_curve`: same curve definition,
    but *u* is one parameter in ``[0, 1]`` and the result is one point.

    Args:
        control: Control points — a sequence of ``[x,y]`` or ``[x,y,z]`` points.
        u: The parameter value in ``[0, 1]``.
        degree: The curve degree.
        mult: Knot multiplicities.
        weights: Weights for rational NURBS.
        nurbs_type: The boundary condition.
        knots: Explicit knot vector.

    Returns:
        A single point as a list of coordinates.
    """
    pts = _curve_points(
        [[float(c) for c in p] for p in control],
        degree,
        u=[float(u)],
        mult=mult,
        weights=weights,
        nurbs_type=nurbs_type,
        knots=knots,
    )
    return [float(c) for c in pts[0]]


# ---------------------------------------------------------------------------
# Section: curve value object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NurbsCurve:
    """A complete NURBS curve definition: control points plus their knot structure.

    Bundles everything :func:`nurbs_curve` needs into one value, so a curve can be
    passed around, elevated, and evaluated without carrying six loose arguments.
    :func:`nurbs_elevate_degree` returns one of these.

    Args:
        control: The control points.
        degree: The curve degree.
        nurbs_type: The boundary condition (default :attr:`NurbsType.CLAMPED`).
        knots: An explicit knot vector, or ``None`` for a uniform one.
        mult: Knot multiplicities, or ``None``.
        weights: Weights for a rational NURBS curve, or ``None``.

    Examples:
        Building a curve definition and sweeping the sampled path into a tube:

        .. pythonscad-example::

            from pybosl2 import NurbsCurve

            ctrl = [[0, 0, 0], [10, 20, 5], [30, -10, 10], [50, 20, 0], [60, 0, 15]]
            NurbsCurve(ctrl, 3).points(splinesteps=12).stroke(width=3).show()
    """

    control: list[list[float]]
    degree: int
    nurbs_type: NurbsType = NurbsType.CLAMPED
    knots: list[float] | None = None
    mult: list[int] | None = None
    weights: list[float] | None = None

    def points(self, splinesteps: int = 16) -> Path:
        """Sample this curve into a path.

        Args:
            splinesteps: Number of samples per knot span (default 16).

        Returns:
            A :class:`~pybosl2.path2d.Path2D` or :class:`~pybosl2.path3d.Path3D`.

        Examples:
            .. pythonscad-example::

                from pybosl2 import NurbsCurve

                curve = NurbsCurve([[0, 0, 0], [10, 20, 5], [30, -10, 10], [50, 20, 0]], 3)
                curve.points(splinesteps=16).stroke(width=3).show()
        """
        return nurbs_curve(
            self.control,
            self.degree,
            splinesteps=splinesteps,
            mult=self.mult,
            weights=self.weights,
            nurbs_type=self.nurbs_type,
            knots=self.knots,
        )

    def point(self, u: float) -> list[float]:
        """Evaluate this curve at a single parameter value.

        Args:
            u: The parameter value in ``[0, 1]``.

        Returns:
            A single point as a list of coordinates.
        """
        return nurbs_curve_point(
            self.control,
            u,
            self.degree,
            mult=self.mult,
            weights=self.weights,
            nurbs_type=self.nurbs_type,
            knots=self.knots,
        )

    def elevate_degree(self, times: int = 1) -> NurbsCurve:
        """Raise this curve's degree, keeping its shape.

        Args:
            times: How many times to elevate the degree (default 1).

        Returns:
            A new :class:`NurbsCurve` of degree ``self.degree + times``.
        """
        return nurbs_elevate_degree(
            self.control,
            self.degree,
            knots=self.knots,
            nurbs_type=self.nurbs_type,
            times=times,
            weights=self.weights,
            mult=self.mult,
        )


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


def nurbs_patch_points(
    patch: Sequence[Sequence[Sequence[float]]],
    degree: tuple[int, int] = (3, 3),
    splinesteps: tuple[int, int] = (16, 16),
    u: Sequence[float] | None = None,
    v: Sequence[float] | None = None,
    weights: Sequence[Sequence[float]] | None = None,
    nurbs_type: tuple[NurbsType, NurbsType] = (NurbsType.CLAMPED, NurbsType.CLAMPED),
    mult: tuple[Sequence[int] | None, Sequence[int] | None] = (None, None),
    knots: tuple[Sequence[float] | None, Sequence[float] | None] = (None, None),
) -> list[list[list[float]]]:
    """Sample a NURBS surface patch on a grid of points.

    Evaluates a NURBS surface — the equivalent of BOSL2's ``nurbs_patch_points()``.
    The patch is swept column-wise (U direction) then row-wise (V direction).
    Every per-direction argument is a ``(u, v)`` pair.  For single-point
    evaluation use :func:`nurbs_patch_point`.

    Args:
        patch: A rectangular array of control points.
        degree: Per-direction degree ``(u_degree, v_degree)`` (default ``(3,3)``).
        splinesteps: Per-direction samples ``(u_steps, v_steps)`` (default ``(16,16)``).
        u: Explicit parameter values along U (replaces the U component of *splinesteps*).
        v: Explicit parameter values along V (replaces the V component of *splinesteps*).
        weights: A matrix the same size as *patch* for rational NURBS weighting.
        nurbs_type: Per-direction boundary condition ``(u_type, v_type)``.
        mult: Per-direction knot multiplicities ``(u_mult, v_mult)``.
        knots: Per-direction knot vectors ``(u_knots, v_knots)``.

    Returns:
        A grid (list of rows) of ``[x, y, z]`` points.
    """
    if weights is not None:
        grid = nurbs_patch_points(
            [_homogeneous(row, wrow) for row, wrow in zip(patch, weights, strict=True)],
            degree,
            splinesteps,
            u,
            v,
            nurbs_type=nurbs_type,
            mult=mult,
            knots=knots,
        )
        return [[_dehomogenise(pt) for pt in row] for row in grid]

    u_steps = None if u is not None else splinesteps[0]
    v_steps = None if v is not None else splinesteps[1]

    # sweep each control-column as a u-curve, then each resulting row as a v-curve
    columns = [
        _curve_points(
            _column(patch, j),
            degree[0],
            splinesteps=u_steps,
            u=u,
            mult=mult[0],
            nurbs_type=nurbs_type[0],
            knots=knots[0],
        )
        for j in range(len(patch[0]))
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


def nurbs_patch_point(
    patch: Sequence[Sequence[Sequence[float]]],
    u: float,
    v: float,
    degree: tuple[int, int] = (3, 3),
    weights: Sequence[Sequence[float]] | None = None,
    nurbs_type: tuple[NurbsType, NurbsType] = (NurbsType.CLAMPED, NurbsType.CLAMPED),
    mult: tuple[Sequence[int] | None, Sequence[int] | None] = (None, None),
    knots: tuple[Sequence[float] | None, Sequence[float] | None] = (None, None),
) -> list[float]:
    """Evaluate a NURBS surface patch at a single (u, v) parameter pair.

    Args:
        patch: A rectangular array of control points.
        u: Parameter value along U in ``[0, 1]``.
        v: Parameter value along V in ``[0, 1]``.
        degree: Per-direction degree ``(u_degree, v_degree)`` (default ``(3,3)``).
        weights: A weight matrix for rational NURBS.
        nurbs_type: Per-direction boundary condition ``(u_type, v_type)``.
        mult: Per-direction knot multiplicities ``(u_mult, v_mult)``.
        knots: Per-direction knot vectors ``(u_knots, v_knots)``.

    Returns:
        A single ``[x, y, z]`` point.
    """
    if weights is not None:
        point = nurbs_patch_point(
            [_homogeneous(row, wrow) for row, wrow in zip(patch, weights, strict=True)],
            u,
            v,
            degree,
            nurbs_type=nurbs_type,
            mult=mult,
            knots=knots,
        )
        return _dehomogenise(point)

    # collapse each control row along V, then the resulting column along U
    inner = [
        _curve_points(row, degree[1], u=[v], mult=mult[1], nurbs_type=nurbs_type[1], knots=knots[1])[0] for row in patch
    ]
    surface_point = _curve_points(inner, degree[0], u=[u], mult=mult[0], nurbs_type=nurbs_type[0], knots=knots[0])[0]
    return [float(c) for c in surface_point]


def nurbs_vnf(
    patch: Sequence[Sequence[Sequence[float]]],
    degree: tuple[int, int] = (3, 3),
    splinesteps: tuple[int, int] = (16, 16),
    weights: Sequence[Sequence[float]] | None = None,
    nurbs_type: tuple[NurbsType, NurbsType] = (NurbsType.CLAMPED, NurbsType.CLAMPED),
    mult: tuple[Sequence[int] | None, Sequence[int] | None] = (None, None),
    knots: tuple[Sequence[float] | None, Sequence[float] | None] = (None, None),
    style: VnfStyle = VnfStyle.DEFAULT,
    reverse: bool = False,
    caps: "CapsSpec | None" = None,
) -> VNF:
    """Mesh a NURBS surface patch into a ``[vertices, faces]`` VNF.

    Samples the patch with :func:`nurbs_patch_points` and builds the mesh using
    :meth:`~pybosl2.vnf.VNF.vertex_array`.  Row/column wrapping is determined
    by *nurbs_type* — ``CLOSED`` directions produce a continuous tube or torus.

    Args:
        patch: A rectangular array of control points.
        degree: Per-direction degree ``(u_degree, v_degree)``.
        splinesteps: Per-direction samples per knot span (default ``(16,16)``).
        weights: A weight matrix as for :func:`nurbs_patch_points`.
        nurbs_type: Per-direction boundary condition ``(u_type, v_type)``.
        mult: Knot multiplicities as for :func:`nurbs_patch_points`.
        knots: Knot vectors as for :func:`nurbs_patch_points`.
        style: :meth:`~pybosl2.vnf.VNF.vertex_array` triangulation style.
        reverse: If True, flip every face normal.
        caps: A :data:`~pybosl2.caps.CapsSpec` to cap a
              ``(CLAMPED, CLOSED)`` or ``(CLOSED, CLAMPED)`` surface.
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
            nurbs_vnf(patch, (3, 3)).polyhedron().show()
    """
    from pybosl2.caps import CapType, norm_caps

    assert is_nurbs_patch(patch), "patch must be a rectangular array of points."

    cap_specs: list["CapSpec"] = norm_caps(caps if caps is not None else CapType.NONE)
    havecaps = any(cs.cap_type != CapType.NONE for cs in cap_specs)
    cappable = ((NurbsType.CLAMPED, NurbsType.CLOSED), (NurbsType.CLOSED, NurbsType.CLAMPED))
    assert not havecaps or tuple(nurbs_type) in cappable, "caps require (CLAMPED,CLOSED) or (CLOSED,CLAMPED)."

    # caps close the column-wrapped ends, so a closed U direction is transposed into V
    flip = havecaps and nurbs_type[0] == NurbsType.CLOSED
    pts = nurbs_patch_points(
        patch,
        degree=degree,
        splinesteps=splinesteps,
        weights=weights,
        nurbs_type=nurbs_type,
        mult=mult,
        knots=knots,
    )
    if flip:
        pts = [list(row) for row in zip(*pts, strict=False)]
    return VNF.vertex_array(
        pts,
        style=style,
        row_wrap=nurbs_type[1 if flip else 0] == NurbsType.CLOSED,
        col_wrap=nurbs_type[0 if flip else 1] == NurbsType.CLOSED,
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
    """The compact knot vector a curve is elevated on.

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


def nurbs_elevate_degree(
    control: Sequence[Sequence[float]],
    degree: int,
    knots: Sequence[float] | None = None,
    nurbs_type: NurbsType = NurbsType.CLAMPED,
    times: int = 1,
    weights: Sequence[float] | None = None,
    mult: Sequence[int] | None = None,
) -> NurbsCurve:
    """Raise a NURBS/B-spline curve's degree by *times*.

    Elevates the curve degree while preserving its shape.  Only
    :attr:`NurbsType.CLAMPED` and :attr:`NurbsType.OPEN` splines are
    supported (as in BOSL2).  Rational curves are elevated in homogeneous
    space and de-homogenised.

    Args:
        control: The control points.
        degree: The current degree.
        knots: The current knot vector.
        nurbs_type: The boundary condition — must be :attr:`NurbsType.CLAMPED`
                    or :attr:`NurbsType.OPEN`.
        times: How many times to elevate (default 1).  ``times=0`` returns the
               input unchanged.
        weights: Weights for a rational NURBS curve.
        mult: Knot multiplicities.

    Returns:
        A :class:`NurbsCurve` holding the elevated curve.

    Raises:
        AssertionError: If *nurbs_type* is not ``CLAMPED`` or ``OPEN``, or if
                        *times* is negative.
    """
    assert nurbs_type in (NurbsType.CLAMPED, NurbsType.OPEN), (
        "nurbs_elevate_degree: nurbs_type must be CLAMPED or OPEN."
    )
    assert times >= 0, "times must be zero or a positive integer."
    points = [[float(c) for c in p] for p in control]
    if times == 0:
        return NurbsCurve(
            control=points,
            degree=degree,
            nurbs_type=nurbs_type,
            knots=[float(k) for k in knots] if knots is not None else None,
            mult=[int(m) for m in mult] if mult is not None else None,
            weights=[float(w) for w in weights] if weights is not None else None,
        )

    if weights is not None:
        elevated = nurbs_elevate_degree(
            _homogeneous(points, weights),
            degree,
            knots=knots,
            nurbs_type=nurbs_type,
            times=times,
            mult=mult,
        )
        return NurbsCurve(
            control=[_dehomogenise(pt) for pt in elevated.control],
            degree=elevated.degree,
            nurbs_type=nurbs_type,
            knots=elevated.knots,
            weights=[float(pt[-1]) for pt in elevated.control],
        )

    compact = _elevation_knots(len(points), degree, nurbs_type, knots, mult)
    full = ([compact[0]] * degree + compact + [compact[-1]] * degree) if nurbs_type == NurbsType.CLAMPED else compact
    new_ctrl, new_full, new_degree = _elevate_once(points, degree, full)
    new_knots = new_full[degree + 1 : len(new_full) - degree - 1] if nurbs_type == NurbsType.CLAMPED else new_full
    if times == 1:
        return NurbsCurve(control=new_ctrl, degree=new_degree, nurbs_type=nurbs_type, knots=new_knots)
    return nurbs_elevate_degree(new_ctrl, new_degree, new_knots, nurbs_type=nurbs_type, times=times - 1)

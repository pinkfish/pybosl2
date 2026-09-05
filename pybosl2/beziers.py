# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# DocCategory: Paths, regions & surfaces

"""Evaluate, analyze and build Bezier curves, paths, and surface patches (BOSL2 beziers.scad).

Pure-Python port of the Bezier CURVE and PATH API from BOSL2's beziers.scad.
Every operation lives on the :class:`Bezier` class -- there are no module-level
bezier functions, mirroring how pybosl2/paths.py hangs every path operation off
Path2D. No osuse()/BOSL2 runtime dependency.

A Bezier is a list of control points: a single curve, or a bezier PATH of
degree-N curves that share endpoints (a flat list of control points where
``len % N == 1``). Ported, matching beziers.scad:

- curve evaluation/analysis: points, curve, derivative, tangent,
  curvature, closest_point, length, line_intersection
- path evaluation/analysis: path_points, path_curve, path_closest_point,
  path_length, close_to_axis, path_offset, and ``Bezier.from_path()``
  (the BOSL2 ``path_to_bezpath`` equivalent)
- control-point construction: Bezier.begin/tang/joint/end (BOSL2
  bez_begin/bez_tang/bez_joint/bez_end), with the scalar-angle, direction
  -vector, and 3-D spherical-angle (``p=``) forms, and Bezier.flatten

The Bezier SURFACE subsystem is on the :class:`BezierPatch` class, built on a
VNF port (pybosl2/vnf.py) and a sweep port (pybosl2/skin.py):

- patches: points, normals, reverse, flat, is_patch, vnf, to_vnf,
  vnf_degenerate (bezier_vnf_degenerate_patch), sheet (bezier_sheet),
  and debug (debug_bezier_patches)
- sweeping a shape along a bezier/bezier-path: Bezier.sweep (bezier_sweep)
  and Bezier.sweep, plus Bezier.debug (debug_bezier)
- path_to_bezcornerpath() is ported as :meth:`~pybosl2.path2d.Path2D.to_bezcornerpath`
  via the ``_bezcorner`` helper in pybosl2/rounding.py.

``points()`` -- the hot path -- uses numpy: it builds the bezier-to-power-basis
matrix (the same "matrix representation" BOSL2 uses, generalized to any degree
N via M[i][j] = C(N,j)*C(N-j,i-j)*(-1)^(i-j) rather than BOSL2's hardcoded
per-degree table) and evaluates every sample with one matrix multiply. The
point-valued methods return numpy ndarrays.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Sequence, cast

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pybosl2._backend import Solid
    from pybosl2._edges_lang import Anchor
    from pybosl2.caps import CapsSpec, CapType
    from pybosl2.path2d import Path2D
    from pybosl2.path3d import Path3D
    from pybosl2.paths import Path, PathLike
    from pybosl2.points import Point, PointLike
    from pybosl2.shapes3d import Bosl2Solid

import numpy as np

from pybosl2._backend import backend_only
from pybosl2.caps import CapsSpec, CapType
from pybosl2.constants import UP
from pybosl2.enums import SweepMethod, VNFStyle
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.math import EPSILON, lerp, lerpn
from pybosl2.transforms import apply as _apply
from pybosl2.transforms import reorient
from pybosl2.vectors import unit as _unit
from pybosl2.vnf import VNF


class Bezier:
    """A Bezier curve or path: a list of control points, with every bezier operation as a method.

    Subclasses ``list`` (the same trick as :class:`pybosl2.paths.Path2D`), so it is a drop-in for the
    raw control-point lists the toolkit passes around, while giving the chained object form::

        Bezier([[44, 5], [48, 6], [64, -15]]).points([0.2 * i for i in range(6)])
        Bezier.flatten([Bezier.begin([0, 0], -20, 0.4), Bezier.end([1, 0], 230, 1)]).curve(20)

    A *curve* is one set of control points (degree ``len - 1``). A *path* is a flat list of
    degree-``N`` curves sharing endpoints (``len % N == 1``); the ``path_*`` methods interpret
    the Bezier that way. The point-valued methods return numpy ndarrays; the control-point
    builders (``begin``/``tang``/``joint``/``end``) are staticmethods returning raw ndarray
    groups that ``flatten`` concatenates into a new Bezier.

    Args:
        control_points: the control points (anything array-like; 2-D or 3-D points)

    Examples:
        Sweeping a circular profile along a 3-D bezier curve into a solid tube:

        .. pythonscad-example::

            import math
            import numpy as np
            from pybosl2 import Bezier

            circle = [[2 * math.cos(t), 2 * math.sin(t)] for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
            tube = Bezier([[0, 0, 5], [0, 0, 20], [25, 12, 15], [30, 4, 6]]).sweep(circle, splinesteps=24)
            tube.show()

    """

    _points: np.ndarray

    def __init__(self, control_points: PathLike = ()) -> None:
        """Initialize a Bezier with a sequence of 2-D or 3-D control points.

        Accepts any array-like: Python lists, numpy arrays, or nested sequences.
        Stored internally as a float64 numpy ndarray for efficient math operations.

        Args:
            control_points: A sequence of 2-D or 3-D control points, as nested lists or numpy arrays.

        """
        pts = np.asarray(control_points, dtype=float)
        if pts.size == 0:
            self._points = np.empty((0, 0), dtype=float)
        else:
            if not (pts.ndim == 2):
                raise Bosl2ValueError(
                    f"control points must be a 2-D array (N points x D dims), got {pts.ndim}-D shape {pts.shape}"
                )
            if not (
                pts.shape[0] >= 1
            ):  # pragma: no cover - defensive: an empty sequence is handled by the size == 0 branch above
                raise Bosl2ValueError(f"control points must have at least 1 point, got shape {pts.shape}")
            if pts.shape[1] not in (2, 3):
                raise Bosl2ValueError(f"control points must be 2-D or 3-D, got {pts.shape[1]} components per point")
            if not (pts.dtype == np.float64):  # pragma: no cover
                # defensive: np.array(..., dtype=float) either produces a float64 array or raises
                # on its own, so a surviving array never has another dtype.
                raise Bosl2ValueError(f"control points must be float64, got {pts.dtype}")
            self._points = pts

    def __len__(self) -> int:
        """Return the number of items."""
        return len(self._points)

    def __getitem__(self, index: int | slice) -> np.ndarray:
        """Return the item at index."""
        return self._points[index]

    def __iter__(self) -> Iterator[np.ndarray]:
        """Return an iterator."""
        return iter(self._points)

    def __repr__(self) -> str:
        """Return a string representation."""
        return f"Bezier({self._points.tolist()})"

    @classmethod
    def from_list(cls, points: PathLike) -> Bezier:
        """Create a Bezier from a plain list of control points.

        Args:
            points: A sequence of 2-D or 3-D control points.

        """
        return cls(points)

    @property
    def to_list(self) -> list[list[float]]:
        """The underlying control-point list."""
        return self._points.tolist()  # type: ignore[no-any-return]

    @property
    def array(self) -> np.ndarray:
        """The control points as an (N, dim) numpy array."""
        return self._points

    # -- curve evaluation ------------------------------------------------------------------

    def points(self, u: float | Sequence[float] | np.ndarray) -> np.ndarray:
        """Evaluate this curve at parameter(s) *u* (each in [0, 1]).

        Returns an ndarray of points (or a length-dim ndarray for a scalar
        *u*). Uses the bezier-to-power-basis matrix to evaluate all samples
        with a single matrix multiply for maximum performance.

        Args:
            u: A parameter value in ``[0, 1]``, or a sequence of values.

        Returns:
            An ndarray of evaluated points. For a scalar *u* the result is a
            1-D vector; for a list of *u* values the result is a 2-D array of
            row vectors.

        """
        scalar = isinstance(u, (int, float, np.floating, np.integer))
        us = [u] if scalar else list(u)  # type: ignore[arg-type]
        p = self.array
        sides = len(self) - 1
        mp = Bezier._matrix(sides) @ p
        powers = np.array([[uv**k for k in range(sides + 1)] for uv in us])  # type: ignore[operator]
        result = powers @ mp
        return result[0] if scalar else result  # type: ignore[no-any-return]

    def curve(self, splinesteps: int = 16, endpoint: bool = True) -> "Path2D | Path3D":
        """Sample *splinesteps* segments uniformly along the curve.

        Returns an ndarray of *splinesteps*+1 points (or *splinesteps* if
        *endpoint* is False) by evaluating the curve at evenly spaced
        parameter values between 0 and 1.

        Args:
            splinesteps: Number of uniform segments to sample along the curve.
            endpoint: If True, include the endpoint at u=1.

        Returns:
            An ndarray of *splinesteps*+1 points (or *splinesteps* if
            *endpoint* is False) sampled uniformly along the curve.

        Examples:
        .. pythonscad-example::

            from pybosl2 import Bezier, Path2D

            pts = Path2D(Bezier([[44, 5], [48, 6], [64, -15]]).curve(20))
            pts.stroke(width=2).linear_extrude(height=3).show()

        """
        # The sampled points *are* a path -- which is what the docstring example does with them
        # (`.stroke(...)`) -- so say so rather than handing back a bare array (PLAN T-4).
        from pybosl2.path2d import Path2D
        from pybosl2.path3d import Path3D

        sampled = np.asarray(self.points(lerpn(0, 1, splinesteps + 1, endpoint)), dtype=float)
        return Path3D(sampled) if sampled.shape[1] == 3 else Path2D(sampled)

    def derivative(self, u: float | Sequence[float] | np.ndarray, order: int = 1) -> np.ndarray:
        """Compute the *order*-th derivative of the curve at parameter(s) *u*.

        Returns an ndarray of derivative vectors. For order 0 this is
        equivalent to calling :meth:`points`. Higher orders are computed
        recursively by first reducing the control polygon via differencing.

        Args:
            u: A parameter value in ``[0, 1]``, or a sequence of values.
            order: The derivative order (0 = position, 1 = first derivative, 2 = second, etc.).

        Returns:
            An ndarray of derivative vectors. For a scalar *u* the result is
            a 1-D vector; for a list of *u* values the result is a 2-D array.

        Raises:
            ValueError: If *order* is not a non-negative integer.

        """
        if not isinstance(order, int) or order < 0:
            raise Bosl2ValueError(f"derivative(): order must be a non-negative integer, got {order!r}.")
        if order == 0:
            return self.points(u)
        sides = len(self) - 1
        dpts = sides * np.diff(self.array, axis=0)
        if order == 1:
            return Bezier(dpts).points(u)
        return Bezier(dpts).derivative(u, order - 1)

    def tangent(self, u: float | Sequence[float] | np.ndarray) -> np.ndarray:
        """Return unit tangent vector(s) at parameter(s) *u*.

        Returns an ndarray of normalized derivative vectors. For a scalar *u*
        the result is a 1-D vector; for a list of *u* values the result is
        a 2-D array of row vectors.

        Args:
            u: A parameter value in ``[0, 1]``, or a sequence of values.

        Returns:
            An ndarray of unit tangent vectors. For a scalar *u* the result is
            a 1-D vector; for a list of *u* values the result is a 2-D array.

        """
        res = np.asarray(self.derivative(u, 1), dtype=float)
        if res.ndim == 1:
            return np.asarray(_unit(res), dtype=float)
        return np.array([_unit(v) for v in res])

    def curvature(self, u: float | Sequence[float] | np.ndarray) -> np.ndarray:
        """Curvature value(s) at parameter(s) *u* (inverse tangent-circle radius).

        Computes the scalar curvature κ = ``|r' × r''|`` / ``|r'|³`` at each
        parameter value. For a scalar *u* returns a single float; for a list
        of *u* values returns a numpy array of floats.

        Args:
            u: A parameter value in ``[0, 1]``, or a sequence of values.

        Returns:
            A float (for scalar *u*) or numpy array of curvature values. The
            curvature κ = ``|r' × r''|`` / ``|r'|³`` is the inverse radius of the
            tangent circle.

        """
        scalar = isinstance(u, (int, float, np.floating, np.integer))
        us = [u] if scalar else list(u)  # type: ignore[arg-type]
        diameter1 = np.atleast_2d(np.asarray(self.derivative(us, 1), dtype=float))  # type: ignore[arg-type, type-var]
        diameter2 = np.atleast_2d(np.asarray(self.derivative(us, 2), dtype=float))  # type: ignore[arg-type, type-var]
        out = []
        for i in range(len(us)):
            n1 = float(np.linalg.norm(diameter1[i]))
            n2 = float(np.linalg.norm(diameter2[i]))
            val = math.sqrt(max((n1 * n2) ** 2 - float(diameter1[i] @ diameter2[i]) ** 2, 0.0)) / (n1**3)
            out.append(val)
        return out[0] if scalar else np.array(out)  # type: ignore[return-value]

    def closest_point(self, pt: "PointLike", max_err: float = 0.01, u: float = 0.0, end_u: float = 1.0) -> float:
        """Return the parameter *u* of the point on this curve closest to *pt*.

        Uses recursive bisection to find the curve parameter that minimizes
        distance to the target point within *max_err* tolerance. The search
        is bounded to the interval [*u*, *end_u*] and falls back to the
        nearer endpoint when no local minimum is detected.

        Args:
            pt: The target point to find the closest curve position to.
            max_err: Maximum allowed error tolerance for the bisection search.
            u: Start of the search interval along the curve.
            end_u: End of the search interval along the curve.

        Returns:
            The parameter *u* in ``[0, 1]`` of the point on this curve closest
            to the target *pt*.

        """
        pt = np.asarray(pt, dtype=float)
        steps = len(self) * 3
        uvals = [u] + [(end_u - u) * (i / steps) + u for i in range(steps + 1)] + [end_u]
        path = np.asarray(self.points(uvals), dtype=float)
        minima_ranges = []
        for i in range(1, len(uvals) - 1):
            diameter1 = np.linalg.norm(path[i - 1] - pt)
            diameter2 = np.linalg.norm(path[i] - pt)
            d3 = np.linalg.norm(path[i + 1] - pt)
            if diameter2 <= diameter1 and diameter2 <= d3:
                minima_ranges.append((uvals[i - 1], uvals[i + 1]))
        if len(minima_ranges) == 0:  # guard BOSL2 leaves implicit: fall back to the nearer end
            de = np.linalg.norm(np.asarray(self.points(end_u)) - pt)
            du = np.linalg.norm(np.asarray(self.points(u)) - pt)
            return end_u if de < du else u
        if len(minima_ranges) > 1:
            min_us = [self.closest_point(pt, max_err, a, b) for a, b in minima_ranges]
            dists = [np.linalg.norm(np.asarray(self.points(v)) - pt) for v in min_us]
            return min_us[int(np.argmin(dists))]
        a, b = minima_ranges[0]
        pp = np.asarray(self.points([a, b]), dtype=float)
        if float(np.linalg.norm(pp[1] - pp[0])) < max_err:
            return (a + b) / 2
        return self.closest_point(pt, max_err, a, b)

    def arc_length(self, start_u: float = 0.0, end_u: float = 1.0, max_deflect: float = 0.01) -> float:
        """Approximate arc length of the curve between *start_u* and *end_u*.

        Uses adaptive subdivision to compute the length: samples the curve,
        measures the maximum deviation from linear segments, and subdivides
        when the deviation exceeds *max_deflect*.

        Args:
            start_u: Start parameter along the curve (default 0).
            end_u: End parameter along the curve (default 1).
            max_deflect: Maximum deviation tolerance before subdividing further.

        Returns:
            The approximate arc length of the curve segment as a float.

        """
        from pybosl2.path2d import Path2D  # local: avoid importing the heavy path module at load time
        from pybosl2.path3d import Path3D

        segs = len(self) * 2
        uvals = lerpn(start_u, end_u, segs + 1)
        path = np.asarray(self.points(uvals), dtype=float)
        defl = max(float(np.linalg.norm(path[i + 1] - (path[i] + path[i + 2]) / 2)) for i in range(len(path) - 2))
        if defl <= max_deflect:
            # closed=False matters: the sampled polyline is an arc, not a loop, and letting the
            # path type close it back to the start would add a spurious chord to the length.
            dim = path.shape[1] if len(path) > 0 else 2
            sampled = Path3D(path, closed=False) if dim == 3 else Path2D(path, closed=False)
            return float(sampled.perimeter())
        total: float = sum(
            (
                self.arc_length(
                    lerp(start_u, end_u, i / segs),  # type: ignore[arg-type]
                    lerp(start_u, end_u, (i + 1) / segs),  # type: ignore[arg-type]
                    max_deflect,
                )
                for i in range(segs)
            ),
            start=0.0,
        )
        return total

    def line_intersection(self, line: np.ndarray) -> list[float]:
        """Return the *u* values where this 2-D curve crosses *line* (two points).

        Computes the intersection parameters in [0, 1] by finding the real
        roots of the algebraic equation that expresses the signed distance
        from the curve to the infinite line defined by two points.

        Args:
            line: A 2xdim array defining two points of the infinite line to intersect against.

        Returns:
            A list of parameter values *u* in ``[0, 1]`` where the curve
            crosses the infinite line defined by the two input points.

        """
        a = Bezier._matrix(len(self) - 1) @ self.array  # bezier algebraic coefficients
        line = np.asarray(line, dtype=float)
        sides = np.array([-line[1][1] + line[0][1], line[1][0] - line[0][0]])  # line normal
        deg = len(a) - 1
        coeffs = [float(a[i] @ sides) for i in range(deg, 0, -1)] + [float((a[0] - line[0]) @ sides)]
        return sorted(r for r in Bezier._real_roots(coeffs) if 0.0 <= r <= 1.0)

    # -- bezier path evaluation ------------------------------------------------------------

    def path_points(self, curveind: int, u: float | Sequence[float] | np.ndarray, n_degree: int = 3) -> np.ndarray:
        """Evaluate curve number *curveind* of this bezier PATH at parameter(s) *u*.

        Extracts the control points for the given segment of a degree-*N*
        bezier path and evaluates that sub-curve at the requested parameter
        values. Returns an ndarray of points.

        Args:
            curveind: Zero-based index of the curve segment within the bezier path.
            u: A parameter value in ``[0, 1]``, or a sequence of values.
            n_degree: Degree of each curve segment in the bezier path.

        Returns:
            An ndarray of evaluated points for the given curve segment.

        """
        sub = self.array[curveind * n_degree : (curveind + 1) * n_degree + 1]
        return Bezier(sub).points(u)

    def path_curve(self, splinesteps: int = 16, n_degree: int = 3, endpoint: bool = True) -> Path:
        """Sample this bezier PATH into a Path2D of points.

        Evaluates a degree-*N* bezier path (``len % N == 1``) by sampling
        each segment uniformly and concatenating the results. Returns a
        :class:`~pybosl2.paths.Path2D` for 2-D points or
        :class:`~pybosl2.paths.Path3D` for 3-D.

        Args:
            splinesteps: Number of uniform segments to sample per curve segment.
            n_degree: Degree of each curve segment in the bezier path.
            endpoint: Whether to include the final endpoint in the output.

        Returns:
            A :class:`~pybosl2.paths.Path2D` for 2-D points or
            :class:`~pybosl2.paths.Path3D` for 3-D points containing the
            sampled bezier path.

        Examples:
        .. pythonscad-example::

            from pybosl2 import Bezier

            bz = Bezier([[0, 0], [25, 30], [50, 0], [75, -30], [100, 0]])
            bz.path_curve(32, n_degree=2).stroke(width=2).linear_extrude(height=3).show()

        """
        if len(self) % n_degree != 1:
            raise Bosl2ValueError(
                f"path_curve(): a degree {n_degree} bezier path needs a multiple of {n_degree} "
                f"points plus 1, got {len(self)}."
            )
        bezpath = self.array
        segs = (len(bezpath) - 1) // n_degree
        step = 1 / splinesteps
        out = []
        for seg in range(segs):
            ctrl = Bezier(bezpath[seg * n_degree : (seg + 1) * n_degree + 1])
            us = [i * step for i in range(splinesteps)]
            out.append(ctrl.points(us))
        if endpoint:
            out.append(bezpath[-1:])
        from pybosl2.path2d import Path2D as _Path2D
        from pybosl2.path3d import Path3D as _Path3D

        result = np.concatenate(out, axis=0)
        if result.shape[1] == 3:
            return _Path3D(result)
        return _Path2D(result)

    def path_closest_point(self, pt: "PointLike", n_degree: int = 3, max_err: float = 0.01) -> tuple[int, float]:
        """Find the closest position on this bezier PATH to *pt*.

        Returns a tuple ``[segnum, u]`` where *segnum* is the 0-based curve
        segment index and *u* is the local parameter along that segment.
        Uses a two-pass search: coarse scan across segments followed by
        fine bisection within the best segment.

        Args:
            pt: The target point to find the closest position to.
            n_degree: Degree of each curve segment in the bezier path.
            max_err: Maximum allowed error tolerance for the bisection search.

        Returns:
            A tuple ``(segment_index, u)`` where *segment_index* is the
            0-based curve segment number and *u* is the local parameter along
            that segment.

        Raises:
            ValueError: If no closest point could be found.

        """
        new_pt = np.asarray(pt, dtype=float)
        if len(self) % n_degree != 1:
            raise Bosl2ValueError(
                f"path_closest_point(): a degree {n_degree} bezier path needs a multiple of {n_degree} "
                f"points plus 1, got {len(self)}."
            )
        nsegs = (len(self) - 1) // n_degree
        best = None
        for seg in range(nsegs):
            curve = Bezier(self.array[seg * n_degree : (seg + 1) * n_degree + 1])
            u = curve.closest_point(new_pt, max_err=0.05)
            dist = float(np.linalg.norm(np.asarray(curve.points(u)) - new_pt))
            if best is None or dist < best[1]:
                best = (seg, dist)
        if best is None:
            raise Bosl2ValueError("Could not find closest point.")
        seg = best[0]
        curve = Bezier(self.array[seg * n_degree : (seg + 1) * n_degree + 1])
        return (seg, curve.closest_point(new_pt, max_err=max_err))

    def path_arc_length(self, n_degree: int = 3, max_deflect: float = 0.001) -> float:
        """Approximate arc length of this bezier PATH.

        Sums the adaptive arc length of each individual degree-*N* curve
        segment. The *max_deflect* parameter controls subdivision accuracy
        within each segment's :meth:`length` call.

        Args:
            n_degree: Degree of each curve segment in the bezier path.
            max_deflect: Maximum deviation tolerance before subdividing further.

        Returns:
            The approximate total arc length of the bezier path as a float.

        """
        if len(self) % n_degree != 1:
            raise Bosl2ValueError(
                f"path_arc_length(): a degree {n_degree} bezier path needs a multiple of {n_degree} "
                f"points plus 1, got {len(self)}."
            )
        nsegs = (len(self) - 1) // n_degree
        return float(
            sum(
                Bezier(self.array[seg * n_degree : (seg + 1) * n_degree + 1]).arc_length(max_deflect=max_deflect)
                for seg in range(nsegs)
            )
        )

    def close_to_axis(self, axis: str = "X", n_degree: int = 3) -> Bezier:
        """Close this 2-D bezier PATH down to the given axis.

        Returns a new Bezier that connects the path's start and end to the
        specified axis ("X" or "Y") and closes back to form a loop, using
        linear blending segments of degree *n_degree*.

        Args:
            axis: Which axis to close down to, either ``"X"`` or ``"Y"``.
            n_degree: Degree of the linear blending segments used to close.

        Returns:
            A new :class:`Bezier` forming a closed loop that connects the
            path's start and end to the specified axis.

        Raises:
            ValueError: If *axis* is not ``"X"`` or ``"Y"``, or if the
                patch is not 2-D.

        """
        arr = self.array
        if not (arr.shape[1] == 2):
            raise Bosl2ValueError("close_to_axis() works only on 2-D bezier paths.")
        sp, ep = arr[0], arr[-1]
        head = arr[:-1]
        if axis == "X":
            foot_s, foot_e = np.array([sp[0], 0.0]), np.array([ep[0], 0.0])
        elif axis == "Y":
            foot_s, foot_e = np.array([0.0, sp[1]]), np.array([0.0, ep[1]])
        else:
            raise Bosl2ValueError(f'close_to_axis(): axis must be "X" or "Y", got {axis!r}.')
        return Bezier(
            np.concatenate(
                [
                    lerpn(foot_s, sp, n_degree, endpoint=False),
                    head,
                    lerpn(ep, foot_e, n_degree, endpoint=False),
                    lerpn(foot_e, foot_s, n_degree + 1),
                ]
            )
        )

    def path_offset(self, offset: np.ndarray, n_degree: int = 3) -> Bezier:
        """Close this 2-D bezier PATH with a reversed copy offset by *offset*.

        Returns a new Bezier that pairs the original path with an offset
        duplicate connected by linear blend segments, forming a closed loop
        suitable for extrusion.

        Args:
            offset: The 2-D offset vector to apply to the reversed copy.
            n_degree: Degree of the linear blending segments used to close.

        Returns:
            A new :class:`Bezier` forming a closed loop combining the
            original path with its offset copy.

        Raises:
            ValueError: If the bezier is not 2-D.

        """
        arr = self.array
        if not (arr.shape[1] == 2):
            raise Bosl2ValueError("path_offset() works only on 2-D bezier paths.")
        off = np.asarray(offset, dtype=float)
        backbez = (arr + off)[::-1]
        return Bezier(
            np.concatenate(
                [
                    arr[:-1],
                    lerpn(arr[-1], backbez[0], n_degree, endpoint=False),
                    backbez[:-1],
                    lerpn(backbez[-1], arr[0], n_degree + 1),
                ]
            )
        )

    @classmethod
    def from_path(
        cls,
        path: Path,
        closed: bool = False,
        tangents: Path | None = None,
        uniform: bool = False,
        size: float | None = None,
        relsize: float | None = None,
    ) -> Bezier:
        """Cubic bezier PATH through every point of *path* (BOSL2 path_to_bezpath).

        Deprecated, use the top-level :func:`create_bezier` instead.

        Args:
            path: The input path of points to fit a bezier through.
            closed: Whether the path is closed.
            tangents: Optional user-supplied tangent vectors for each point.
            uniform: If True, compute tangents assuming uniform spacing.
            size: Fixed control-point magnitude for all segments.
            relsize: Relative control-point magnitude proportional to segment length.

        Returns:
            A cubic :class:`Bezier` path interpolating every point of the
            input path.

        """
        from pybosl2.paths import require_path

        path = require_path(path, "path", "from_path")
        return create_bezier(path, closed=closed, tangents=tangents, uniform=uniform, size=size, relsize=relsize)

    # -- sweeping (BOSL2 bezier_sweep / sweep) -------------------------------------

    def sweep(
        self,
        shape: "PathLike",
        splinesteps: int = 16,
        n_degree: int | None = None,
        method: SweepMethod = SweepMethod.INCREMENTAL,
        endpoint: bool = True,
        normal: Point | None = None,
        closed: bool = False,
        twist: float = 0.0,
        twist_by_length: bool = True,
        scale: float = 1.0,
        scale_by_length: bool = True,
        symmetry: int = 1,
        last_normal: Point | None = None,
        caps: CapsSpec = CapType.BUTT,
        style: VNFStyle = VNFStyle.MIN_EDGE,
    ) -> "Solid":
        """Sweep the 2-D *shape* along this bezier curve or path into a solid.

        If *n_degree* is given and ``len(self) % n_degree == 1`` this
        treats the bezier as a degree-*N* path, sampling each segment
        separately. Otherwise the bezier is treated as a single curve.
        All other parameters are passed through to
        :func:`~pybosl2.skin._path_sweep`.

        Args:
            shape: 2-D shape as a list of points to sweep.
            splinesteps: Number of uniform segments per curve or curve-segment.
            n_degree: Curve degree for path mode; ``None`` uses curve mode.
            method: Sweep method.
            endpoint: If True, include the endpoint at u=1.
            normal: Optional normal vector for the sweep.
            closed: Whether the swept shape should be closed (a tube).
            twist: Total twist angle in degrees applied along the sweep.
            twist_by_length: If True, twist is scaled by relative arc length.
            scale: Scale factor applied along the sweep.
            scale_by_length: If True, scale is distributed by relative arc length.
            symmetry: Rotational symmetry count of the shape.
            last_normal: Last normal vector for closed sweeps.
            caps: Whether to add end caps.
            style: VNF triangulation style.

        Returns:
            The swept solid, on the active backend (SPEC S-19a). Its mesh is on ``.vnf()`` for
            anything that wants to measure or export it without a CAD runtime.

        Examples:
            Curve mode (single curve sweep):

            .. pythonscad-example::

                import math
                import numpy as np
                from pybosl2 import Bezier
                from math import cos, sin
                circle = [[2 * cos(t), 2 * sin(t)] for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
                tube = Bezier([[0, 0, 5], [0, 0, 20], [25, 12, 15], [30, 4, 6]]).sweep(circle, splinesteps=24)
                tube.show()

            Path2D mode (degree-3 bezier path sweep):

            .. pythonscad-example::

                import math
                import numpy as np
                from pybosl2 import Bezier
                from math import cos, sin
                shape = [[cos(t), sin(t)] for t in np.linspace(0, 2 * math.pi, 12, endpoint=False)]
                path = Bezier.flatten([Bezier.begin([0, 0], 0, 20), Bezier.end([50, 0], 180, 20)])
                path.sweep(shape, n_degree=3, splinesteps=24).show()

        """
        from pybosl2.path3d import Path3D
        from pybosl2.skin import path3d

        if n_degree is not None and len(self) % n_degree == 1:
            bezpath = self.array
            nsegs = (len(bezpath) - 1) // n_degree
            path = self.path_curve(splinesteps, n_degree, endpoint)
            tang: list[np.ndarray] = []
            for seg in range(nsegs):
                ctrl = Bezier(bezpath[seg * n_degree : (seg + 1) * n_degree + 1])
                tang.extend(ctrl.derivative(list(lerpn(0, 1, splinesteps + 1, endpoint))))
        else:
            path = self.curve(splinesteps, endpoint)
            tang: list[Sequence[float]] = self.derivative(  # type: ignore[no-redef]
                list(lerpn(0, 1, splinesteps + 1, endpoint))
            )
        path_3d = path3d(path)
        tang_3d = path3d(tang) if tang is not None else None
        return Path3D(np.asarray(path_3d)).path_sweep(
            shape,
            method=method,
            normal=normal,
            closed=closed,
            twist=twist,
            twist_by_length=twist_by_length,
            scale=(scale, scale),
            scale_by_length=scale_by_length,
            symmetry=symmetry,
            last_normal=last_normal,
            tangent=tang_3d,
            caps=caps,
            style=style,
        )

    def sweep_transforms(
        self,
        splinesteps: int = 16,
        n_degree: int | None = None,
        method: SweepMethod = SweepMethod.INCREMENTAL,
        endpoint: bool = True,
        normal: Point | None = None,
        closed: bool = False,
        twist: float = 0.0,
        twist_by_length: bool = True,
        scale: float = 1.0,
        scale_by_length: bool = True,
        symmetry: int = 1,
        last_normal: Point | None = None,
    ) -> list[list[list[float]]]:
        """Return the 4x4 transforms :meth:`sweep` would place its cross sections with.

        This used to be ``sweep(..., transforms=True)``. A flag that changes the return type is a
        second function (SPEC S-19b), so it is one -- and separating them is what lets ``sweep()``
        return a plain `Solid`.

        It is not the same as ``self.path_curve(...).path_sweep_transforms()``: this passes the
        curve's *analytic* tangents, which is what makes the first frame exact rather than the
        result of a rotation-minimizing walk along sampled points.

        Args:
            splinesteps: Number of uniform segments per curve or curve-segment.
            n_degree: Curve degree for path mode; ``None`` uses curve mode.
            method: Sweep method.
            endpoint: If True, include the endpoint at u=1.
            normal: Optional normal vector for the sweep.
            closed: Whether the swept shape should be closed (a tube).
            twist: Total twist angle in degrees applied along the sweep.
            twist_by_length: If True, twist is scaled by relative arc length.
            scale: Scale factor applied along the sweep.
            scale_by_length: If True, scale is distributed by relative arc length.
            symmetry: Rotational symmetry count of the shape.
            last_normal: Last normal vector for closed sweeps.

        Returns:
            One 4x4 matrix per cross section, as plain nested lists.

        Examples:
            Placing your own geometry at each station along a bezier::

                from pybosl2 import Bezier, cuboid

                curve = Bezier([[0, 0, 5], [0, 0, 10], [15, 7, 9], [17, 2, 4]])
                for matrix in curve.sweep_transforms(splinesteps=4):
                    cuboid([2, 2, 1]).multmatrix(matrix)

        """
        from pybosl2.path3d import Path3D
        from pybosl2.skin import _path_sweep, path3d

        if n_degree is not None and len(self) % n_degree == 1:
            bezpath = self.array
            nsegs = (len(bezpath) - 1) // n_degree
            path = self.path_curve(splinesteps, n_degree, endpoint)
            tang: list[Any] = []
            for seg in range(nsegs):
                ctrl = Bezier(bezpath[seg * n_degree : (seg + 1) * n_degree + 1])
                tang.extend(ctrl.derivative(list(lerpn(0, 1, splinesteps + 1, endpoint))))
        else:
            path = self.curve(splinesteps, endpoint)
            tang = list(self.derivative(list(lerpn(0, 1, splinesteps + 1, endpoint))))
        placed = _path_sweep(
            [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]],  # placeholder profile: only the frames are read
            Path3D(np.asarray(path3d(path))),
            method=method,
            normal=normal,
            closed=closed,
            twist=twist,
            twist_by_length=twist_by_length,
            scale=(scale, scale),
            scale_by_length=scale_by_length,
            symmetry=symmetry,
            last_normal=last_normal,
            tangent=path3d(tang),
            transforms=True,
        )
        return cast("list[list[list[float]]]", placed)

    # -- control-point construction (BOSL2 bez_begin/bez_tang/bez_joint/bez_end) ------------

    @staticmethod
    def begin(
        pt: "PointLike", angle: float | Sequence[float], radius: float | None = None, phi: float | None = None
    ) -> np.ndarray:
        """Return the starting endpoint and control point of a cubic bezier path.

        Returns a (2, dim) ndarray of [endpoint, control_point]. For 2-D
        points *angle* is a scalar angle; for 3-D points *angle* is a scalar angle
        in the XY plane and *phi* is the angle down from Z+.

        Args:
            pt: The starting endpoint position.
            angle: A scalar angle in the XY plane, or a direction vector. Required.
            radius: Distance from *pt* to the control point; required when *angle* is scalar.
            phi: For 3-D points: angle down from the Z+ axis.

        Returns:
            A ``(2, dim)`` ndarray of ``[endpoint, control_point]``.

        """
        pt = np.asarray(pt, dtype=float)
        if not (len(pt) == 3 or phi is None):
            raise Bosl2ValueError("phi= requires a 3-D point")
        return np.stack([pt, pt + Bezier._ctrloffset(len(pt), angle, radius, phi)])

    @staticmethod
    def tang(
        pt: "PointLike",
        angle: float | Sequence[float],
        radius1: float | None = None,
        radius2: float | None = None,
        phi: float | None = None,
    ) -> np.ndarray:
        """Smooth joint in a cubic bezier path with collinear control points.

        Returns a (3, dim) ndarray of [approaching_cp, fixed_point,
        departing_cp]. The two control points are collinear with the fixed
        point, forming a smooth (G1-continuous) bend. *angle* can be a scalar
        angle or a direction vector; *radius1* and *radius2* control the
        distances from the fixed point.

        Args:
            pt: The fixed point position.
            angle: A scalar angle or direction vector defining the tangent direction.
            radius1: Distance from *pt* to the approaching control point.
            radius2: Distance from *pt* to the departing control point; defaults to *radius1*.
            phi: For 3-D points: angle down from the Z+ axis.

        Returns:
            A ``(3, dim)`` ndarray of
            ``[approaching_cp, fixed_point, departing_cp]``.

        """
        pt = np.asarray(pt, dtype=float)
        if not (len(pt) == 3 or phi is None):
            raise Bosl2ValueError("phi= requires a 3-D point")
        unit_dir, dist = Bezier._dir_and_dist(len(pt), angle, radius1, phi)
        dist1 = dist if radius1 is None else radius1
        dist2 = dist1 if radius2 is None else radius2
        return np.stack([pt - dist1 * unit_dir, pt, pt + dist2 * unit_dir])

    @staticmethod
    def joint(
        pt: "PointLike",
        angle1: float | Sequence[float],
        angle2: float | Sequence[float],
        radius1: float | None = None,
        radius2: float | None = None,
        phi1: float | None = None,
        phi2: float | None = None,
    ) -> np.ndarray:
        """Disjoint corner joint in a cubic bezier path.

        Returns a (3, dim) ndarray of [approaching_cp, fixed_point,
        departing_cp] with the two control points in independent directions.
        *angle1* and *angle2* define the approach and departure directions as scalar
        angles or direction vectors.

        Args:
            pt: The fixed corner point position.
            angle1: Approach direction as a scalar angle or direction vector.
            angle2: Departure direction as a scalar angle or direction vector.
            radius1: Distance from *pt* to the approaching control point.
            radius2: Distance from *pt* to the departing control point.
            phi1: For 3-D points: approach angle down from Z+.
            phi2: For 3-D points: departure angle down from Z+.

        Returns:
            A ``(3, dim)`` ndarray of
            ``[approaching_cp, fixed_point, departing_cp]``, with independent
            approach and departure directions.

        """
        pt = np.asarray(pt, dtype=float)
        if not (len(pt) == 3 or (phi1 is None and phi2 is None)):
            raise Bosl2ValueError("phi1=/phi2= require a 3-D point")
        return np.stack(
            [
                pt + Bezier._ctrloffset(len(pt), angle1, radius1, phi1),
                pt,
                pt + Bezier._ctrloffset(len(pt), angle2, radius2, phi2),
            ]
        )

    @staticmethod
    def end(
        pt: "PointLike", angle: float | Sequence[float], radius: float | None = None, phi: float | None = None
    ) -> np.ndarray:
        """Approaching control point and endpoint of a cubic bezier path.

        Returns a (2, dim) ndarray of [control_point, endpoint], the mirror
        of :meth:`begin`. The control point approaches the endpoint from the
        direction specified by *angle*.

        Args:
            pt: The ending endpoint position.
            angle: A scalar angle or direction vector for the approaching control point.
            radius: Distance from the control point to *pt*; required when *angle* is scalar.
            phi: For 3-D points: angle down from the Z+ axis.

        Returns:
            A ``(2, dim)`` ndarray of ``[control_point, endpoint]``.

        """
        pt = np.asarray(pt, dtype=float)
        if not (len(pt) == 3 or phi is None):
            raise Bosl2ValueError("phi= requires a 3-D point")
        return np.stack([pt + Bezier._ctrloffset(len(pt), angle, radius, phi), pt])

    def debug(self, width: float = 1.0, n_degree: int = 3) -> Any:
        """Visualize this bezier PATH as native geometry (BOSL2 debug_bezier).

        Renders the swept curve (cyan), control net (green), and control
        points (blue for endpoints, red for interior) as solid geometry using
        tubes and spheres.

        Args:
            width: Diameter of the visualised curve tube and control net lines.
            n_degree: Degree of each curve segment in the bezier path.

        Returns:
            A native geometry solid rendering the bezier path with colored
            curve, control net, and control-point markers.

        Examples:
        .. pythonscad-example::

            from pybosl2 import Bezier

            path = Bezier.flatten([
                Bezier.begin([0, 0, 0], -20, 0.4),
                Bezier.tang([5, 8, 2], 45, 0.2),
                Bezier.end([10, 0, 5], 230, 1),
            ])
            path.debug(width=0.5)

        """
        result = _debug_tube(np.asarray(self.path_curve(n_degree=n_degree)), width / 2.0).color("cyan")
        result = result | _debug_tube(np.asarray([list(p) for p in self]), width / 2.0).color("green")
        for k, p in enumerate(self):
            marker = (
                _sphere_at(p, width * 2.25).color("blue")
                if k % n_degree == 0
                else _sphere_at(p, width * 0.75).color("red")
            )
            result = result | marker
        return result

    @staticmethod
    def flatten(groups: Sequence[np.ndarray]) -> "Bezier":
        """Concatenate control-point groups into one Bezier.

        Flattens a list of ndarray groups (from :meth:`begin`, :meth:`tang`,
        :meth:`joint`, :meth:`end`) by concatenating them along axis 0 into
        a single Bezier instance. Also supports flat lists of points directly.

        Args:
            groups: A sequence of ndarray groups from :meth:`begin`, :meth:`tang`, :meth:`joint`, or :meth:`end`.

        Returns:
            A new :class:`Bezier` with all control-point groups concatenated
            into a single flat control-point list.

        """
        if len(groups) > 0 and isinstance(groups[0], np.ndarray):
            return Bezier(np.concatenate(groups, axis=0))
        out: list[np.ndarray] = []
        for x in groups:
            out.extend(x)
        return Bezier(out)  # type: ignore[arg-type]

    # -- internals -------------------------------------------------------------------------

    @staticmethod
    def _matrix(sides: int) -> np.ndarray:
        m = np.zeros((sides + 1, sides + 1))
        for i in range(sides + 1):
            for j in range(i + 1):
                m[i][j] = math.comb(sides, j) * math.comb(sides - j, i - j) * ((-1) ** (i - j))
        return m

    @staticmethod
    def _spherical_to_xyz(radius: float, theta: float, phi: float) -> np.ndarray:
        th, ph = math.radians(theta), math.radians(phi)
        return radius * np.array([math.cos(th) * math.sin(ph), math.sin(th) * math.sin(ph), math.cos(ph)])

    @staticmethod
    def _ctrloffset(
        point_dim: int, angle: float | Sequence[float], radius: float | None, phi: float | None
    ) -> np.ndarray:
        if isinstance(angle, (list, tuple, np.ndarray)):
            direction = np.asarray(angle, dtype=float)
            return direction if radius is None else radius * np.asarray(_unit(direction), dtype=float)
        if not (radius is not None):
            raise Bosl2ValueError("radius must be given when angle is a scalar, not a direction vector")
        if point_dim == 3:
            return Bezier._spherical_to_xyz(radius, angle, 90.0 if phi is None else phi)  # type: ignore[arg-type]
        rad = math.radians(angle)  # type: ignore[arg-type]
        return radius * np.array([math.cos(rad), math.sin(rad)])

    @staticmethod
    def _dir_and_dist(
        point_dim: int, angle: float | Sequence[float], radius: float | None, phi: float | None
    ) -> "tuple[np.ndarray, float]":
        if isinstance(angle, (list, tuple, np.ndarray)):
            direction = np.asarray(angle, dtype=float)
            dist = float(np.linalg.norm(direction)) if radius is None else radius
            return np.asarray(_unit(direction), dtype=float), dist
        if not (radius is not None):
            raise Bosl2ValueError("radius must be given when angle is a scalar, not a direction vector")
        if point_dim == 3:
            return Bezier._spherical_to_xyz(1.0, angle, 90.0 if phi is None else phi), radius  # type: ignore[arg-type]
        rad = math.radians(angle)  # type: ignore[arg-type]
        return np.array([math.cos(rad), math.sin(rad)]), radius

    @staticmethod
    def _real_roots(coeffs: Sequence[float] | np.ndarray) -> list[float]:
        c = list(coeffs)
        while len(c) > 1 and abs(c[0]) < 1e-14:
            c = c[1:]
        if len(c) <= 1:
            return []
        return [float(r.real) for r in np.atleast_1d(np.roots(c)) if abs(r.imag) < 1e-9]


def create_bezier(
    path: Path,
    closed: bool = False,
    tangents: Path | None = None,
    uniform: bool = False,
    size: float | None = None,
    relsize: float | None = None,
) -> Bezier:
    """Cubic bezier PATH through every point of *path* (BOSL2 path_to_bezpath).

    Constructs a piecewise-cubic bezier that interpolates the given
    points, matching the path's tangents. *size* or *relsize* control the
    tension; omit both to use the default (relsize=0.1).

    Args:
        path: The input path of points to fit a cubic bezier through.
        closed: Whether the path is closed (last point connects to first).
        tangents: Optional user-supplied tangent vectors for each point.
        uniform: If True, compute tangents assuming uniform spacing along the path.
        size: Fixed control-point magnitude for all curve segments.
        relsize: Relative control-point magnitude proportional to each segment's length.

    Returns:
        A cubic :class:`Bezier` path whose curve passes through every point
        of the input path.

    Raises:
        ValueError: If both *size* and *relsize* are specified, or if any
            path segment has zero length.

    """
    from pybosl2.path2d import Path2D
    from pybosl2.path3d import Path3D

    if not (size is None or relsize is None):
        raise Bosl2ValueError("Can't define both size and relsize.")
    patharr = np.asarray(path, dtype=float)
    npts = len(patharr)
    lastpt = npts - (0 if closed else 1)
    curvesize = size if size is not None else (relsize if relsize is not None else 0.1)
    relative = size is None
    if isinstance(curvesize, (int, float)):
        sizevect = [float(curvesize)] * lastpt
    else:
        sizevect = [float(v) for v in curvesize]
        if not (len(sizevect) == lastpt):
            raise Bosl2ValueError(f"Size or relsize must have length {lastpt}.")
    if tangents is not None:
        tang = np.asarray(tangents, dtype=float)
        tang = np.array([t / np.linalg.norm(t) for t in tang])
    else:
        dim = patharr.shape[1] if len(patharr) > 0 else 2
        tang = np.asarray(
            (Path3D(patharr) if dim == 3 else Path2D(patharr)).tangents(closed=closed, uniform=uniform),
            dtype=float,
        )
    if not (min(sizevect) > 0):
        raise Bosl2ValueError("Size and relsize must be greater than zero.")
    out: list[np.ndarray] = []
    basis_mat = np.array([[-3, 6, -3], [7, -9, 2], [-5, 3, 0], [1, 0, 0]], dtype=float)
    for i in range(lastpt):
        first = patharr[i]
        second = patharr[(i + 1) % npts]
        seglength = float(np.linalg.norm(second - first))
        if not (seglength > 0):
            raise Bosl2ValueError(f"Path2D segment has zero length from index {i} to {i + 1}.")
        segdir = (second - first) / seglength
        tangent1 = tang[i]
        tangent2 = -tang[(i + 1) % npts]
        parallel = abs(float(tangent1 @ segdir)) + abs(float(tangent2 @ segdir))
        lmax = seglength / parallel if parallel != 0 else math.inf
        sz = sizevect[i] * seglength if relative else sizevect[i]
        normal1 = tangent1 - (tangent1 @ segdir) * segdir
        normal2 = tangent2 - (tangent2 @ segdir) * segdir
        pcoef = basis_mat @ np.array([normal1 @ normal1, normal1 @ normal2, normal2 @ normal2])
        uextreme = [] if float(np.linalg.norm(pcoef)) < EPSILON else [r for r in Bezier._real_roots(pcoef) if 0 < r < 1]
        if len(uextreme) == 0:
            scale = 0.0
        else:
            ctrl = np.array([normal1 * 0, normal1, normal2, normal2 * 0])
            dists = [float(np.linalg.norm(d)) for d in np.atleast_2d(Bezier(ctrl).points(uextreme))]
            scale = dists[0] if len(dists) == 1 else (sum(dists) - 2 * min(dists))
        ldesired = sz / scale if scale != 0 else math.inf
        length_ = min(lmax, ldesired)
        out.extend([first, first + length_ * tangent1, second + length_ * tangent2])
    out.append(patharr[lastpt % npts])
    return Bezier(np.asarray(out))


class BezierPatch:
    """A rectangular Bezier surface patch: a 2-D array (rows x cols) of 3-D control points.

    Evaluate it with :meth:`points`, get surface normals with :meth:`normals`, and mesh it into a
    :class:`~pybosl2.vnf.VNF` with :meth:`vnf` (which renders via ``polyhedron()``). Build several
    patches into one VNF with :meth:`to_vnf` (BOSL2 bezier_vnf), and make a flat patch with
    :meth:`flat` (BOSL2 bezier_patch_flat)::

        BezierPatch.flat([100, 100]).vnf(splinesteps=8).polyhedron()

    Ported from beziers.scad's Bezier SURFACE section: bezier_patch_points/_normals/_reverse/
    _flat, is_bezier_patch, and bezier_vnf. NOT ported: bezier_vnf_degenerate_patch (handles
    collapsed-edge patches), bezier_sheet (offset-shell), and bezier_sweep/sweep (need
    BOSL2's un-ported path_sweep), plus the debug_* visualization modules.

    Args:
        rows: a list of rows, each a list of [x, y, z] control points

    Examples:
        A bezier surface patch, thickened into a solid sheet:

        .. pythonscad-example::

            from pybosl2 import BezierPatch

            patch = [
                [[-50, -50, 0], [-16, -50, 20], [16, -50, -20], [50, -50, 0]],
                [[-50, -16, 20], [-16, -16, 20], [16, -16, -20], [50, -16, 20]],
                [[-50, 16, 20], [-16, 16, -20], [16, 16, 20], [50, 16, 20]],
                [[-50, 50, 0], [-16, 50, -20], [16, 50, 20], [50, 50, 0]],
            ]
            BezierPatch(patch).sheet([0, -6], splinesteps=16).polyhedron().show()

    """

    _rows: np.ndarray

    def __init__(self, rows: "Sequence[Sequence[Sequence[float]]] | np.ndarray" = ()) -> None:
        """Initialize with a 2-D grid of 3-D control points.

        Accepts a list of rows where each row is a list of [x, y, z] control
        points forming a rectangular bezier surface patch. Stored internally as
        a float64 numpy ndarray for efficient math operations.

        Args:
            rows: A list of rows, each a list of ``[x, y, z]`` control points forming a rectangular patch.

        """
        pts = np.asarray(rows, dtype=float)
        if pts.size == 0:
            self._rows = np.empty((0, 0, 0), dtype=float)
        else:
            if not (pts.ndim == 3):
                raise Bosl2ValueError(
                    f"patch rows must be a 3-D array (R rows x C cols x 3 dim), got {pts.ndim}-D shape {pts.shape}"
                )
            if not (
                pts.shape[0] >= 1
            ):  # pragma: no cover - defensive: an empty sequence is handled by the size == 0 branch above
                raise Bosl2ValueError(f"patch must have at least 1 row, got shape {pts.shape}")
            if not (
                pts.shape[1] >= 1
            ):  # pragma: no cover - defensive: a row-less array is already rejected by the ndim check
                raise Bosl2ValueError(f"patch must have at least 1 column, got shape {pts.shape}")
            if not (pts.shape[2] == 3):
                raise Bosl2ValueError(f"patch control points must be 3-D, got {pts.shape[2]} components")
            if not (pts.dtype == np.float64):  # pragma: no cover
                # defensive: np.array(..., dtype=float) either produces a float64 array or raises
                # on its own, so a surviving array never has another dtype.
                raise Bosl2ValueError(f"control points must be float64, got {pts.dtype}")
            self._rows = pts

    def __len__(self) -> int:
        """Return the number of items."""
        return len(self._rows)

    def __getitem__(self, index: int | slice) -> np.ndarray:
        """Return the item at index."""
        return self._rows[index]

    def __iter__(self) -> Iterator[np.ndarray]:
        """Return an iterator."""
        return iter(self._rows)

    @classmethod
    def from_list(cls, rows: np.ndarray) -> BezierPatch:
        """Create a BezierPatch from a plain list of control-point rows.

        Args:
            rows: A list of rows of 3-D control points.

        """
        return cls(rows)

    @property
    def to_list(self) -> list[list[list[float]]]:
        """The underlying control-point row list."""
        return self._rows.tolist()  # type: ignore[no-any-return]

    @property
    def array(self) -> np.ndarray:
        """The control points as an (rows, cols, 3) numpy array."""
        return self._rows

    @staticmethod
    def is_patch(x: Any) -> bool:
        """Check if *x* looks like a bezier patch.

        Returns True if *x* is a rectangular 2-D array of point vectors
        where the first element is a numeric vector (not a nested list of
        vectors) and all rows have equal length.

        Args:
            x: The object to test.

        Returns:
            True if *x* is a rectangular 2-D array of numeric point vectors
            with equal-length rows.

        """
        # `np.ndarray` belongs in that check: without it this returned False for the very type
        # `BezierPatch.array` hands back and its own annotation advertises, so `to_vnf(patch.array)`
        # took the sequence-of-patches branch and tried to build a patch out of one row.
        if not (isinstance(x, (list, tuple, np.ndarray)) and len(x) > 0):
            return False
        r0 = x[0]
        if not (isinstance(r0, (list, tuple, np.ndarray)) and len(r0) > 0):
            return False
        p0 = r0[0]
        if not (isinstance(p0, (list, tuple, np.ndarray)) and len(p0) >= 2):
            return False
        try:  # a point is a vector of numbers, not a list of points (which a patch-list would give)
            return all(isinstance(e, (int, float, np.integer, np.floating)) for e in p0) and len(x[0]) == len(x[-1])
        except TypeError:
            return False

    # -- evaluation ------------------------------------------------------------------------

    def points(self, u: float | Sequence[float] | np.ndarray, v: float | Sequence[float] | np.ndarray) -> np.ndarray:
        """Sample the patch at parameter(s) *u* and *v*.

        *u* is the inner/column axis and *v* is the outer/row axis. Scalar
        *u* and *v* return a single point; lists/ranges return a rectangular
        ``(len(u) x len(v))`` grid of points as an ndarray.

        Args:
            u: Parameter along the column (inner) axis in ``[0, 1]``, or a sequence of values.
            v: Parameter along the row (outer) axis in ``[0, 1]``, or a sequence of values.

        Returns:
            An ndarray of sampled surface points. Scalar *u* and *v* return a
            single point; lists/ranges return a ``(len(u) x len(v))`` grid of
            points.

        Examples:
        .. pythonscad-example::

            from pybosl2 import BezierPatch, Path3D

            patch = BezierPatch.flat([100, 100], n_degree=3)
            pts = patch.points(0, [i / 16 for i in range(17)])
            Path3D(pts).stroke(width=2).show()

        """
        patch = self.array
        nrows, ncols = patch.shape[0], patch.shape[1]
        su = isinstance(u, (int, float, np.floating, np.integer))
        sv = isinstance(v, (int, float, np.floating, np.integer))
        if not su and not sv:
            ulist, vlist = list(u), list(v)  # type: ignore[arg-type]
            vbezes = np.array([Bezier(patch[:, i, :]).points(ulist) for i in range(ncols)])  # (ncols, lenu, dim)
            return np.array(
                [Bezier(vbezes[:, i, :]).points(vlist) for i in range(vbezes.shape[1])]
            )  # (lenu, lenv, dim)
        if su and sv:
            row_pts = np.array([Bezier(patch[r]).points(v) for r in range(nrows)])  # (nrows, dim)
            return Bezier(row_pts).points(u)
        if su:
            return self.points([u], v)[0]  # type: ignore[no-any-return, list-item]
        return self.points(u, [v])[:, 0, :]  # type: ignore[list-item]

    def normals(self, u: float | Sequence[float] | np.ndarray, v: float | Sequence[float] | np.ndarray) -> np.ndarray:
        """Return unit surface normal(s) at parameter(s) *u*, *v*.

        Same shape rules as :meth:`points`: scalar inputs return a single
        normal vector, while list inputs return a grid of normals computed
        as the cross product of the *u* and *v* tangents.

        Args:
            u: Parameter along the column (inner) axis in ``[0, 1]``, or a sequence of values.
            v: Parameter along the row (outer) axis in ``[0, 1]``, or a sequence of values.

        Returns:
            An ndarray of unit normal vectors computed as the cross product of
            the *u* and *v* tangents. Scalar inputs return a single vector;
            list inputs return a grid of normals.

        """
        patch = self.array
        nrows, ncols = patch.shape[0], patch.shape[1]
        su = isinstance(u, (int, float, np.floating, np.integer))
        sv = isinstance(v, (int, float, np.floating, np.integer))
        if not su and not sv:
            ulist, vlist = list(u), list(v)  # type: ignore[arg-type]
            vbezes = np.array([Bezier(patch[:, i, :]).points(ulist) for i in range(ncols)])  # (ncols, lenu, dim)
            dvbezes = np.array([Bezier(patch[:, i, :]).derivative(ulist) for i in range(ncols)])  # (ncols, lenu, dim)
            lenu = vbezes.shape[1]
            v_tan = np.array([Bezier(vbezes[:, i, :]).derivative(vlist) for i in range(lenu)])  # (lenu, lenv, dim)
            u_tan = np.array([Bezier(dvbezes[:, i, :]).points(vlist) for i in range(lenu)])  # (lenu, lenv, dim)
            return np.array(
                [
                    [np.asarray(_unit(np.cross(u_tan[i][j], v_tan[i][j])), dtype=float) for j in range(v_tan.shape[1])]
                    for i in range(lenu)
                ]
            )
        if su and sv:
            du = Bezier(np.array([Bezier(patch[r]).points(v) for r in range(nrows)])).derivative(u)
            dv = Bezier(np.array([Bezier(patch[r]).derivative(v) for r in range(nrows)])).points(u)
            return np.asarray(_unit(np.cross(du, dv)), dtype=float)
        if su:
            return self.normals([u], v)[0]  # type: ignore[no-any-return, list-item]
        return self.normals(u, [v])[:, 0, :]  # type: ignore[list-item]

    def reverse(self) -> "BezierPatch":
        """Reverse each row of the patch, flipping the surface orientation.

        Returns a new BezierPatch with the same control points but each row
        in reversed order, which flips the face normals for VNF meshing.

        Returns:
            A new :class:`BezierPatch` with reversed row order, suitable for
            flipping the mesh orientation.

        """
        return BezierPatch([list(reversed(row)) for row in self])

    # -- meshing ---------------------------------------------------------------------------

    def vnf(self, splinesteps: int = 16, style: VNFStyle = VNFStyle.DEFAULT) -> VNF:
        """Mesh this patch into a :class:`~pybosl2.vnf.VNF`.

        Samples the patch at *splinesteps* intervals in both *u* and *v*
        directions (or per-axis if given as ``[usteps, vsteps]``) and builds
        a vertex-face mesh using :meth:`~pybosl2.vnf.VNF.vertex_array`.

        Args:
            splinesteps: Number of sampling steps per axis, or ``[usteps, vsteps]`` pair.
            style: VNF triangulation style, passed to :func:`~pybosl2.vnf.VNF.vertex_array`.

        Returns:
            A :class:`~pybosl2.vnf.VNF` vertex-face mesh of the sampled patch surface.

        Examples:
        .. pythonscad-example::

            from pybosl2 import BezierPatch

            patch = BezierPatch.flat([100, 100], n_degree=3)
            vnf = patch.vnf(splinesteps=16)
            vnf.polyhedron().show()

        """
        ss = splinesteps if isinstance(splinesteps, (list, tuple, np.ndarray)) else (splinesteps, splinesteps)
        uvals = list(lerpn(0, 1, int(ss[0]) + 1))
        vvals = list(lerpn(1, 0, int(ss[1]) + 1))
        from pybosl2.path3d import Path3D as _Path3D

        return VNF.vertex_array([_Path3D(r) for r in self.points(uvals, vvals)], style=style, reverse=False)

    @staticmethod
    def to_vnf(
        patches: "BezierPatch | np.ndarray | Sequence[BezierPatch | np.ndarray]",
        splinesteps: int = 16,
        style: VNFStyle = VNFStyle.DEFAULT,
    ) -> VNF:
        """Convert one or more patches into a single VNF (BOSL2 bezier_vnf).

        Accepts either a single patch (2-D control-point array) or a list
        of patches and returns their combined :class:`~pybosl2.vnf.VNF`
        mesh, joined via :meth:`~pybosl2.vnf.VNF.union`.

        Args:
            patches: A single patch control-point array or a sequence of patches to mesh.
            splinesteps: Number of sampling steps per axis, or ``[usteps, vsteps]`` pair.
            style: VNF triangulation style, passed to :func:`~pybosl2.vnf.VNF.vertex_array`.

        Returns:
            A combined :class:`~pybosl2.vnf.VNF` vertex-face mesh of all patches.

        Examples:
        .. pythonscad-example::

            from pybosl2 import BezierPatch

            p1 = BezierPatch.flat([50, 50], n_degree=3)
            p2 = BezierPatch.flat([50, 50], n_degree=2, trans=(60, 0, 0))
            BezierPatch.to_vnf([p1, p2], splinesteps=16).polyhedron().show()

        """

        # A caller may hand over a single patch or a sequence of them, and each may already be a
        # BezierPatch or still be the raw control-point grid (PLAN T-4). Normalise on the way in.
        def _as_patch(value: "BezierPatch | np.ndarray | Sequence[Sequence[Sequence[float]]]") -> "BezierPatch":
            return value if isinstance(value, BezierPatch) else BezierPatch(value)

        if isinstance(patches, BezierPatch) or BezierPatch.is_patch(patches):
            return _as_patch(cast("np.ndarray", patches)).vnf(splinesteps, style)
        return VNF.union([_as_patch(p).vnf(splinesteps, style) for p in patches])

    @staticmethod
    def flat(
        size: float | Sequence[float],
        n_degree: int = 1,
        spin: float = 0.0,
        orient: Anchor | Sequence[float] = UP,
        trans: Sequence[float] = (0.0, 0.0, 0.0),
    ) -> "BezierPatch":
        """Create a flat rectangular degree-*n_degree* patch.

        Generates a patch of the given *size* centered on the XY plane,
        then reorients it using *spin* and *orient*. Supports translation
        and rotation relative to the standard XY orientation.

        Args:
            size: Patch size as a scalar (square) or ``[width, height]`` pair.
            n_degree: Degree of the patch in each direction.
            spin: Rotation angle in degrees around the Z axis.
            orient: Orientation vector for the patch normal.
            trans: Translation vector ``[x, y, z]``.

        Returns:
            A new :class:`BezierPatch` of the given dimensions, centered on
            the XY plane and reoriented as specified.

        Examples:
        .. pythonscad-example::

            from pybosl2 import BezierPatch

            patch = BezierPatch.flat([100, 100], n_degree=3, spin=45)
            patch.vnf(splinesteps=16).polyhedron().show()

        """
        if n_degree <= 0:
            raise Bosl2ValueError(f"BezierPatch.flat(): n_degree must be positive, got {n_degree}.")
        sz = [float(size), float(size)] if isinstance(size, (int, float)) else [float(size[0]), float(size[1])]
        patch = [
            [[sz[0] * (x / n_degree - 0.5), sz[1] * (0.5 - y / n_degree), 0.0] for y in range(n_degree + 1)]
            for x in range(n_degree + 1)
        ]
        base = np.asarray(reorient(spin=spin, orient=list(orient)), dtype=float)
        xform = np.eye(4)
        xform[:3, 3] = np.asarray(trans, dtype=float)
        m = (xform @ base).tolist()
        return BezierPatch([_apply(m, row) for row in patch])

    def sheet(self, delta: "float | Sequence[float]", splinesteps: int = 16, style: VNFStyle = VNFStyle.DEFAULT) -> VNF:
        """Offset the patch along surface normals to form a thin sheet (BOSL2 bezier_sheet).

        Creates a solid by meshing two copies of the patch offset in opposite
        normal directions and connecting the boundary edges. *delta* is a
        2-vector ``[d0, d1]`` of the two offset distances; a scalar *d* is
        equivalent to ``[0, -d]``. The resulting VNF can be rendered directly
        with ``polyhedron()``.

        Args:
            delta: Offset distances ``[d0, d1]`` along surface normals; a scalar *d* is equivalent to ``[0, -d]``.
            splinesteps: Number of sampling steps per axis, or ``[usteps, vsteps]`` pair.
            style: VNF triangulation style, passed to :func:`~pybosl2.vnf.VNF.vertex_array`.

        Returns:
            A :class:`~pybosl2.vnf.VNF` solid mesh formed by offsetting the
            patch in opposite normal directions and connecting the boundary
            edges.

        Raises:
            ValueError: If the patch has degenerate normals.

        Examples:
        .. pythonscad-example::

            from pybosl2 import BezierPatch

            patch = BezierPatch.flat([100, 100], n_degree=3)
            patch.sheet([0, -6], splinesteps=16).polyhedron().show()

        """
        diameter = [0.0, -float(delta)] if isinstance(delta, (int, float)) else [float(delta[0]), float(delta[1])]
        ss = splinesteps if isinstance(splinesteps, (list, tuple, np.ndarray)) else (splinesteps, splinesteps)
        uvals = list(lerpn(0, 1, int(ss[0]) + 1))
        vvals = list(lerpn(1, 0, int(ss[1]) + 1))
        pts = np.asarray(self.points(uvals, vvals), dtype=float)
        normals = np.asarray(self.normals(uvals, vvals), dtype=float)
        if np.any(np.isnan(normals)):
            raise Bosl2ValueError("Bezier patch has degenerate normals.")
        offset0 = pts - diameter[0] * normals
        offset1 = pts - diameter[1] * normals
        allpoints = [np.concatenate([offset0[i], offset1[i][::-1]]) for i in range(len(offset0))]
        from pybosl2.path3d import Path3D as _Path3D

        vnf = VNF.vertex_array([_Path3D(r) for r in allpoints], caps=CapType.BUTT, col_wrap=True, style=style)
        return vnf.reverse() if diameter[0] < diameter[1] else vnf

    def vnf_degenerate(
        self, splinesteps: int = 16, reverse: bool = False, return_edges: bool = False
    ) -> VNF | tuple[VNF, list[list[list[float]]]]:
        """Mesh a degenerate patch (BOSL2 bezier_vnf_degenerate_patch).

        Handles patches where some corners or edges are collapsed, avoiding
        excess triangles by using adaptive triangulation. When *return_edges*
        is True, returns a ``[vnf, edges]`` tuple where *edges* is
        ``[left, right, top, bottom]`` point lists.

        Args:
            splinesteps: Number of sampling steps along each edge.
            reverse: If True, reverse the face orientation.
            return_edges: If True, also return edge point lists as ``[left, right, top, bottom]``.

        Returns:
            A :class:`~pybosl2.vnf.VNF` mesh, or a ``(VNF, edges)`` tuple if
            *return_edges* is True, where *edges* is ``[left, right, top,
            bottom]`` point lists.

        """
        result = BezierPatch._vnf_degenerate(self.array, splinesteps, reverse, True)
        return result if return_edges else result[0]

    @staticmethod
    def _all_equal(row: np.ndarray, eps: float = EPSILON) -> bool:
        a = np.asarray(row, dtype=float)
        return bool(np.all(np.linalg.norm(a - a[0], axis=1) <= eps))

    @staticmethod
    def _vnf_degenerate(
        patch: np.ndarray, splinesteps: int, reverse: bool, return_edges: bool
    ) -> tuple[VNF, list[list[list[float]]]]:
        from pybosl2.path3d import Path3D

        _ = return_edges
        patch = np.asarray(patch, dtype=float)
        nrows, ncols = patch.shape[0], patch.shape[1]
        row_degen = [BezierPatch._all_equal(patch[r]) for r in range(nrows)]
        col_degen = [BezierPatch._all_equal(patch[:, c]) for c in range(ncols)]
        top_degen, bot_degen = row_degen[0], row_degen[-1]
        left_degen, right_degen = col_degen[0], col_degen[-1]
        samplepts = list(lerpn(0, 1, splinesteps + 1))
        empty = VNF([], [])

        def _tolist(pts: np.ndarray) -> list[list[float]]:  # list of point rows -> list of lists
            return [list(p) for p in pts]

        if all(row_degen) and all(col_degen):
            return (empty, [[patch[0][0].tolist()] for _ in range(4)])
        if all(row_degen):
            ptl = _tolist(Bezier(patch[:, 0, :]).points(samplepts))
            return (empty, [ptl, ptl, [ptl[0]], [ptl[-1]]])
        if all(col_degen):
            ptl = _tolist(Bezier(patch[0]).points(samplepts))
            return (empty, [[ptl[0]], [ptl[-1]], ptl, ptl])
        if not top_degen and not bot_degen and not left_degen and not right_degen:
            pts = BezierPatch(patch).points(samplepts, samplepts)
            vnf = VNF.vertex_array([Path3D(r) for r in pts], reverse=not reverse)
            edges = [
                [pts[k][0] for k in range(len(pts))],
                [pts[k][-1] for k in range(len(pts))],
                list(pts[0]),
                list(pts[-1]),
            ]
            return (vnf, edges)
        if top_degen and bot_degen:
            rowcount = list(range(3, splinesteps + 1, 2))
            if splinesteps % 2 == 0:
                rowcount.append(splinesteps + 1)
            rowcount += list(reversed(list(range(3, splinesteps + 1, 2))))
            bpatch = np.asarray([Bezier(patch[:, i, :]).points(samplepts) for i in range(ncols)])
            dpts = [[bpatch[0][0]]]
            for j in range(splinesteps - 1):
                dpts.append(_tolist(Bezier(bpatch[:, j + 1, :]).points(list(lerpn(0, 1, rowcount[j])))))
            dpts.append([bpatch[0][-1]])
            vnf = VNF.tri_array([Path3D(r) for r in dpts], reverse=not reverse)
            return (
                vnf,
                [
                    [row[0] for row in dpts],
                    [row[-1] for row in dpts],
                    list(dpts[0]),
                    list(dpts[-1]),
                ],
            )
        if bot_degen:
            res = BezierPatch._vnf_degenerate(patch[::-1], splinesteps, not reverse, True)
            e = res[1]
            return (res[0], [e[0][::-1], e[1][::-1], e[3], e[2]])
        if top_degen:
            full_degen = nrows >= 4 and all(row_degen[1 : int(math.ceil(nrows / 2 - 1)) + 1])
            rowmax = (
                list(range(splinesteps + 1))
                if full_degen
                else [2 * j if j <= splinesteps / 2 else splinesteps for j in range(splinesteps + 1)]
            )
            bpatch = np.asarray([Bezier(patch[:, i, :]).points(samplepts) for i in range(ncols)])
            dpts = [[bpatch[0][0]]]
            for j in range(1, splinesteps + 1):
                dpts.append(_tolist(Bezier(bpatch[:, j, :]).points(list(lerpn(0, 1, rowmax[j] + 1)))))
            vnf = VNF.tri_array([Path3D(r) for r in dpts], reverse=not reverse)
            return (
                vnf,
                [
                    [row[0] for row in dpts],
                    [row[-1] for row in dpts],
                    list(dpts[0]),
                    list(dpts[-1]),
                ],
            )
        # left or right degeneracy: transpose and recurse
        res = BezierPatch._vnf_degenerate(np.transpose(patch, (1, 0, 2)), splinesteps, not reverse, True)
        e = res[1]
        return (res[0], [e[2], e[3], e[0], e[1]])

    # -- debugging visualization (BOSL2 debug_bezier_patches) ------------------------------

    def debug(
        self,
        splinesteps: int = 16,
        showcps: bool = True,
        showdots: bool = False,
        showpatch: bool = True,
        size: float | None = None,
        style: VNFStyle = VNFStyle.DEFAULT,
    ) -> Bosl2Solid:
        """Visualize this patch as native geometry (BOSL2 debug_bezier_patches).

        Renders the surface, control-point net lines, and control points as
        solid geometry. *showpatch* enables the surface mesh, *showcps*
        draws the control net, and *showdots* highlights the mesh vertices.

        Args:
            splinesteps: Number of sampling steps for the surface mesh.
            showcps: If True, render the control-point net.
            showdots: If True, highlight the mesh vertices.
            showpatch: If True, render the surface mesh.
            size: Optional marker diameter; auto-scaled if None.
            style: VNF triangulation style, passed to :func:`~pybosl2.vnf.VNF.vertex_array`.

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid` wrapping the rendered
            patch surface, control net, and control-point markers.

        Examples:
        .. pythonscad-example::

            from pybosl2 import BezierPatch

            patch = BezierPatch.flat([100, 100], n_degree=3)
            patch.debug(splinesteps=8, showcps=True, showpatch=True)

        """
        return debug_bezier_patches(
            [self],  # type: ignore[list-item]
            size=size,
            splinesteps=splinesteps,
            showcps=showcps,
            showdots=showdots,
            showpatch=showpatch,
            style=style,
        )


def _debug_tube(points: np.ndarray, radius: float, sides: int = 8) -> Any:
    from pybosl2.path3d import Path3D

    circ = [
        [
            radius * math.cos(2 * math.pi * k / sides),
            radius * math.sin(2 * math.pi * k / sides),
        ]
        for k in range(sides)
    ]
    pts = [list(p) for p in points]
    dedup = [pts[0]] + [
        p for i, p in enumerate(pts[1:], 1) if np.linalg.norm(np.asarray(p) - np.asarray(pts[i - 1])) > 1e-9
    ]
    # a sweep already returns a Solid (SPEC S-19a), so there is nothing to realize here
    return Path3D(dedup).path_sweep(circ)


def _sphere_at(p: np.ndarray, diameter: float) -> Any:
    """Return a marker ball at *p*, wrapped like _debug_tube()'s output so the two can be unioned.

    Returning the bare native instead meant ``sphere | tube`` failed ("invalid argument left to
    operator") while ``tube | sphere`` worked, so whether a caller's union succeeded came down to
    which kind of piece it happened to start with.
    """
    from pythonscad import sphere

    from pybosl2.shapes3d import Bosl2Solid as _Bosl2Solid

    p3 = [float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0]
    return _Bosl2Solid(sphere(d=diameter).translate(p3))  # the native takes r/d, not radius/diameter


@backend_only("csg")
def debug_bezier_patches(
    patches: np.ndarray | Sequence[np.ndarray],
    size: float | None = None,
    splinesteps: int = 16,
    showcps: bool = True,
    showdots: bool = False,
    showpatch: bool = True,
    style: VNFStyle = VNFStyle.DEFAULT,
) -> Bosl2Solid:
    """Native geometry showing bezier patches: surfaces, control points and control-net lines.

    Returns a :class:`~pybosl2.shapes3d.Bosl2Solid` wrapping the rendered patches.
    Requires the real PythonSCAD app; builds on VNF.polyhedron() and the
    ported path_sweep tube.

    **CSG-only, and it says so now.** It marks control points with native spheres and returns a
    `Bosl2Solid`, so it was never neutral -- but under `use_backend("sdf")` it got halfway through
    and failed on the *combination*: "cannot combine a 'csg'-backend solid with a 'sdf'-backend
    solid". A true sentence about the wrong thing; nothing in it says this helper is a CSG feature.
    It refuses up front under its own name now (SPEC B-9, E-5) -- the same fix `Region.debug_region`
    got in T53 and the path extrusions in T51. Three helpers that built CSG regardless of the
    active backend, each announcing it differently, and none of them saying what it was.

    Args:
        patches: A single patch or list of patches to debug-visualise.
        size: Optional marker diameter; auto-scaled if None.
        splinesteps: Number of sampling steps for the surface mesh.
        showcps: If True, render the control-point net.
        showdots: If True, highlight the mesh vertices.
        showpatch: If True, render the surface mesh.
        style: VNF triangulation style, passed to :func:`~pybosl2.vnf.VNF.vertex_array`.

    Returns:
        A :class:`~pybosl2.shapes3d.Bosl2Solid` wrapping the rendered patch
        surfaces, control nets, and control-point markers.

    """
    from pybosl2.shapes3d import Bosl2Solid as _Bosl2Solid

    # is_patch() only recognises a list/tuple, so a BezierPatch or an (R, C, 3) array -- both of
    # which the signature accepts -- used to fall through and be iterated as if each row were a
    # whole patch, failing with "patch rows must be a 3-D array".
    single = (
        isinstance(patches, BezierPatch)
        or (isinstance(patches, np.ndarray) and patches.ndim == 3)
        or BezierPatch.is_patch(patches)
    )
    plist: list[Any] = [patches] if single else patches  # type: ignore[assignment]
    result = None
    surfaces: list[Any] = []

    def _add(a: Any, b: Any) -> Any:
        return b if a is None else (a | b)

    for patch in plist:
        bp = BezierPatch(patch)
        arr = bp.array
        sz: float = (
            size
            if size is not None
            else float(np.max(arr.reshape(-1, arr.shape[-1]).max(axis=0) - arr.reshape(-1, arr.shape[-1]).min(axis=0)))
            * 0.01
        )
        if showcps:
            for row in bp:
                for p in row:
                    result = _add(result, _sphere_at(p, sz * 2).color("red"))
            nrows, ncols = arr.shape[0], arr.shape[1]
            for i in range(nrows):
                for j in range(ncols):
                    if i < nrows - 1:
                        result = _add(
                            result,
                            _debug_tube(np.asarray([arr[i][j], arr[i + 1][j]]), sz / 2).color("cyan"),
                        )
                    if j < ncols - 1:
                        result = _add(
                            result,
                            _debug_tube(np.asarray([arr[i][j], arr[i][j + 1]]), sz / 2).color("cyan"),
                        )
        if showpatch or showdots:
            vnf = bp.vnf(splinesteps=splinesteps, style=style)
            if showpatch:
                # A patch surface is open, and CSG cannot union two open meshes -- doing so lost
                # the geometry entirely for two or more patches. Collect the meshes and emit them
                # as one polyhedron instead, which is a mesh operation and does not care.
                surfaces.append(vnf)
            if showdots:
                for v in vnf.vertices:
                    result = _add(result, _sphere_at(np.asarray(v), sz).color("blue"))
    if surfaces:
        from pybosl2.vnf import VNF as _VNF

        result = _add(result, _VNF.join(surfaces).polyhedron())
    if result is None:
        raise Bosl2ValueError("debug_bezier_patches(): nothing to show -- showcps, showpatch and showdots are all off.")
    # Every piece is already a Bosl2Solid; wrapping again would bury the native and leave the
    # result with no bounding box of its own.
    return result if isinstance(result, _Bosl2Solid) else _Bosl2Solid(result)

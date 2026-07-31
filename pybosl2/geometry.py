# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/geometry.py
#    Pure-Python port of the pieces of BOSL2's geometry.scad (plus
#    pointlist_bounds() from vectors.scad) that pybosl2/paths.py depends on.
#    No osuse()/BOSL2 runtime dependency. Built on numpy: every
#    vector/point-valued function here returns a real numpy ndarray rather
#    than a plain list. Only handles 2D/3D points, and only the subset of
#    behavior (e.g. segment-bounded line_closest_point) that paths.py
#    actually needs.
#
# FileSummary: Points, lines and polygon geometry helpers (BOSL2 geometry.scad).
# DocCategory: Math & geometry
# FileGroup: BOSL2

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import numpy as np

from pybosl2.math import EPSILON
from pybosl2.points import Point, Vector
from pybosl2.vectors import unit

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import NDArray

__all__ = [
    "circle_circle_tangents",
    "general_line_intersection",
    "is_collinear",
    "line_closest_point",
    "line_normal",
    "pointlist_bounds",
]


def _cross2d(a: NDArray[np.float64], b: NDArray[np.float64]) -> float:
    """2-D cross product scalar: a_x * b_y - a_y * b_x."""
    return float(a[0] * b[1] - a[1] * b[0])


def is_collinear(
    point1: Point,
    point2: Point,
    point3: Point,
    eps: float = EPSILON,
) -> bool:
    """True if three points lie on a common line (works in 2-D or 3-D).

    Args:
        point1: First point.
        point2: Second point.
        point3: Third point.
        eps: Epsilon for collinearity tolerance.

    Returns:
        True if the three points are collinear within *eps*.
    """
    dx1 = point2.x - point1.x
    dy1 = point2.y - point1.y
    dx2 = point3.x - point1.x
    dy2 = point3.y - point1.y
    if point1.is_2d:
        n1 = math.hypot(dx1, dy1)
        n2 = math.hypot(dx2, dy2)
        if n1 <= eps or n2 <= eps:
            return True
        cross2d = dx1 * dy2 - dy1 * dx2
        return bool(abs(cross2d) <= eps * max(n1, n2))

    dz1: float = point2.z - point1.z  # type: ignore[operator]
    dz2: float = point3.z - point1.z  # type: ignore[operator]
    n1 = math.hypot(dx1, dy1, dz1)
    n2 = math.hypot(dx2, dy2, dz2)
    if n1 <= eps or n2 <= eps:
        return True
    cross_v = np.cross([dx1, dy1, dz1], [dx2, dy2, dz2])
    return float(np.linalg.norm(cross_v)) <= eps * n1 * n2


def line_normal(
    point1: Point,
    point2: Point,
) -> Vector:
    """Unit 2-D normal vector perpendicular to the line direction, pointing left.

    Returns a :class:`~pybosl2.points.Vector` of length 2, perpendicular to
    the line from *point1* to *point2*.

    Args:
        point1: First endpoint.
        point2: Second endpoint.

    Returns:
        A unit-length :class:`~pybosl2.points.Vector` normal to the line.
    """
    return Vector(unit([point1.y - point2.y, point2.x - point1.x]))


def line_closest_point(
    segment: Sequence[Sequence[float]] | tuple[NDArray[np.float64], NDArray[np.float64]],
    query_point: Point,
) -> NDArray[np.float64]:
    """Closest point on a bounded segment to a query point.

    Projects *query_point* onto the infinite line through the segment and then
    clamps the parameter to the segment's bounds using :func:`numpy.clip`.

    Args:
        segment: A ``(start, end)`` pair defining the bounded line segment.
        query_point: The point to project onto the segment.

    Returns:
        The closest point on the segment as an ndarray.
    """
    start = np.asarray(segment[0], dtype=float)
    end = np.asarray(segment[1], dtype=float)
    query = np.asarray(query_point, dtype=float)
    direction: NDArray[np.float64] = end - start
    length_sq: float = float(direction @ direction)
    if length_sq < EPSILON:
        return start.copy()
    t: float = float((query - start) @ direction) / length_sq
    t = float(np.clip(t, 0.0, 1.0))
    return start + t * direction


def pointlist_bounds(
    points: Any,
) -> NDArray[np.float64]:
    """Axis-aligned bounding box of a list of points.

    Equivalent to ``numpy.stack([arr.min(axis=0), arr.max(axis=0)])``.
    Provided for parity with BOSL2's ``pointlist_bounds()``.  Accepts any
    array-like (sequences, ndarrays, :class:`Path2D`, etc.).

    Args:
        points: An array-like of *n*-dimensional points.

    Returns:
        A ``(2, dim)`` ndarray: ``[[xmin, ymin, ...], [xmax, ymax, ...]]``.
    """
    arr = np.asarray(points, dtype=float)
    return np.stack([arr.min(axis=0), arr.max(axis=0)])


def _is_point_on_segment(
    point: Point,
    segment: Sequence[Sequence[float]] | tuple[NDArray[np.float64], NDArray[np.float64]],
    eps: float = EPSILON,
) -> bool:
    """Return True if *point* lies on the bounded *segment* within tolerance *eps*."""
    start = np.asarray(segment[0], dtype=float)
    end = np.asarray(segment[1], dtype=float)
    query = np.asarray(point, dtype=float)
    v1: NDArray[np.float64] = end - start
    v0: NDArray[np.float64] = query - start
    vv1: float = float(float(v1 @ v1))
    if vv1 < eps:
        return float(np.linalg.norm(v0)) <= eps
    t: float = float(float(v0 @ v1)) / vv1
    on_line: bool = bool(abs(_cross2d(v0, v1)) <= eps * float(np.linalg.norm(v1)))
    return on_line and (-eps <= t < 1 + eps)


def general_line_intersection(
    segment1: Sequence[Sequence[float]] | tuple[NDArray[np.float64], NDArray[np.float64]],
    segment2: Sequence[Sequence[float]] | tuple[NDArray[np.float64], NDArray[np.float64]],
    eps: float = EPSILON,
) -> list[NDArray[np.float64] | float] | None:
    """Intersection point of two infinite lines.

    Computes the intersection of the lines through *segment1* and *segment2*.
    Returns parametric positions so the caller can check segment bounds.

    Args:
        segment1: A ``(start, end)`` pair defining the first line.
        segment2: A ``(start, end)`` pair defining the second line.
        eps: Epsilon for parallel-line detection.

    Returns:
        ``[point, t, u]`` where *point* is the intersection coordinate,
        *t* and *u* are the parametric positions along *segment1* and *segment2*
        (0 at the first endpoint, 1 at the second).  Returns ``None``
        for parallel or coincident lines.
    """
    s1a = np.asarray(segment1[0], dtype=float)
    s1b = np.asarray(segment1[1], dtype=float)
    s2a = np.asarray(segment2[0], dtype=float)
    s2b = np.asarray(segment2[1], dtype=float)
    v1: NDArray[np.float64] = s1a - s1b
    v2: NDArray[np.float64] = s2a - s2b
    denominator: float = _cross2d(v1, v2)
    if abs(denominator) <= eps:
        return None
    ac: NDArray[np.float64] = s1a - s2a
    t: float = _cross2d(ac, v2) / denominator
    u: float = _cross2d(ac, v1) / denominator
    intersection_point: NDArray[np.float64] = s1a + t * (s1b - s1a)
    return [intersection_point, t, u]


def circle_circle_tangents(
    radius1: float | None = None,
    center1: Point | None = None,
    radius2: float | None = None,
    center2: Point | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
) -> list[list[list[float]]]:
    """Tangent lines between two circles.

    Computes up to four common tangent lines: two external tangents plus,
    when the circles do not overlap, two internal (crossing) tangents.

    Args:
        radius1: Radius of the first circle (mutually exclusive with *diameter1*).
        center1: Centre point of the first circle.
        radius2: Radius of the second circle (mutually exclusive with *diameter2*).
        center2: Centre point of the second circle.
        diameter1: Diameter of the first circle.
        diameter2: Diameter of the second circle.

    Returns:
        A list of tangent line pairs ``[[point_on_circle1, point_on_circle2], ...]``
        with each inner entry a list of two ``[x, y]`` coordinate lists.
        Returns up to 4 entries (2 external + 2 internal), 2 entries when
        only external tangents exist, or 0 when no tangent can be drawn.
    """
    r1v: float = radius1 if radius1 is not None else (diameter1 / 2 if diameter1 is not None else 1.0)
    r2v: float = radius2 if radius2 is not None else (diameter2 / 2 if diameter2 is not None else 1.0)
    c1_arr: NDArray[np.float64] = np.asarray(center1, dtype=float)
    c2_arr: NDArray[np.float64] = np.asarray(center2, dtype=float)
    dist: float = float(np.linalg.norm(c2_arr - c1_arr))
    if dist < EPSILON:
        return []
    r_vals: list[float] = [
        (r2v - r1v) / dist,
        (r2v - r1v) / dist,
        (-r2v - r1v) / dist,
        (-r2v - r1v) / dist,
    ]
    k_vals: list[int] = [-1, 1, -1, 1]
    ext: list[int] = [1, 1, -1, -1]
    if 1 - r_vals[2] ** 2 >= 0:
        sides: int = 4
    elif 1 - r_vals[0] ** 2 >= 0:
        sides = 2
    else:
        sides = 0
    u: NDArray[np.float64] = unit(c2_arr - c1_arr)
    result: list[list[list[float]]] = []
    for i in range(sides):
        radius: float = r_vals[i]
        sin_angle: float = math.sqrt(max(0.0, 1 - radius * radius))
        k: int = k_vals[i]
        coef: NDArray[np.float64] = np.array(
            [radius * u[0] - k * sin_angle * u[1], k * sin_angle * u[0] + radius * u[1]]
        )
        p1: NDArray[np.float64] = c1_arr - r1v * coef
        p2: NDArray[np.float64] = c2_arr - ext[i] * r2v * coef
        if not np.array_equal(p1, p2):
            result.append([p1.tolist(), p2.tolist()])
    return result

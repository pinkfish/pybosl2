# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/vectors.py
#    Pure-Python port of the pieces of BOSL2's vectors.scad that pybosl2/paths.py
#    depends on.  All vector-valued parameters accept :class:`~pybosl2.points.Point`
#    or any :class:`~collections.abc.Sequence` of floats.
#
# FileSummary: Vector predicates and scalar-vector operations (BOSL2 vectors.scad).
# DocCategory: Math & geometry
# FileGroup: BOSL2

import math
from collections.abc import Sequence

import numpy as np

from pybosl2.math import EPSILON, constrain
from pybosl2.points import Point


def is_vector(
    v: Point | Sequence[float] | np.ndarray,
    length: int | None = None,
    zero: bool | None = None,
    eps: float = EPSILON,
) -> bool:
    """
    True if *v* is a list/tuple/ndarray of finite numbers (optionally of a given length and/or
    zero-ness).
    """
    if isinstance(v, np.ndarray):
        if v.ndim != 1 or v.size == 0:
            return False
    elif not isinstance(v, (list, tuple)) or len(v) == 0:
        return False
    for x in v:
        if (
            isinstance(x, bool)
            or not isinstance(x, (int, float, np.floating, np.integer))
            or math.isinf(x)
            or math.isnan(x)
        ):
            return False
    if length is not None and len(v) != length:
        return False
    if zero is not None:
        is_zero = float(np.linalg.norm(np.asarray(v, dtype=float))) < eps
        if is_zero != zero:
            return False
    return True


def add_scalar(v: Point | Sequence[float] | np.ndarray, s: float) -> np.ndarray:
    """Return *v* with scalar *s* added to every entry."""
    return np.asarray(v, dtype=float) + s


def unit(
    v: Point | Sequence[float] | np.ndarray,
    error: Point | Sequence[float] | np.ndarray | None = None,
) -> np.ndarray:
    """Normalize *v* to unit length.

    If *v* has (near) zero length, returns *error* if given, else raises
    ValueError (matching BOSL2's default assert-on-zero-vector behavior).
    """
    arr = np.asarray(v, dtype=float)
    sides = float(np.linalg.norm(arr))
    if sides < EPSILON:
        if error is not None:
            return np.asarray(error, dtype=float)
        raise ValueError("Cannot normalize a zero vector")
    return arr / sides


def vector_angle(a: Point, b: Point) -> float:
    """Angle between two vectors in radians.

    The result is always in the range [0, pi].

    Args:
        a: First vector (2-D or 3-D).
        b: Second vector (2-D or 3-D, same dimension as *a*).

    Returns:
        The angle in radians.

    Raises:
        ValueError: If either vector has zero length.
    """
    if len(a) != len(b):
        raise ValueError(f"Vectors must have the same dimension, got {len(a)} and {len(b)}")
    norm_a: float = math.hypot(*a)
    norm_b: float = math.hypot(*b)
    if norm_a < EPSILON or norm_b < EPSILON:
        raise ValueError("Cannot compute angle with a zero-length vector")
    dot: float = constrain(
        sum(a[i] * b[i] for i in range(len(a))) / (norm_a * norm_b),
        -1.0,
        1.0,
    )
    return math.acos(dot)


def vector_axis(a: Point, b: Point) -> tuple[list[float], float]:
    """Return the axis vector (cross product) and angle between *a* and *b*.

    The axis is the unit vector perpendicular to both *a* and *b* (requires
    3-D vectors). The angle is the result of :func:`vector_angle`.

    Args:
        a: First 3-D vector.
        b: Second 3-D vector.

    Returns:
        A ``(axis, angle)`` tuple where *axis* is a unit 3-D list and
        *angle* is in radians.

    Raises:
        ValueError: If vectors are not 3-D or have zero length.
    """
    if len(a) != 3 or len(b) != 3:
        raise ValueError(f"vector_axis requires 3-D vectors, got sizes {len(a)} and {len(b)}")
    norm_a: float = math.hypot(*a)
    norm_b: float = math.hypot(*b)
    if norm_a < EPSILON or norm_b < EPSILON:
        raise ValueError("Cannot compute axis with a zero-length vector")
    angle: float = vector_angle(a, b)
    u: list[float] = [x / norm_a for x in a]
    v: list[float] = [x / norm_b for x in b]
    cross: list[float] = [
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    ]
    cross_norm: float = math.hypot(*cross)
    if cross_norm < EPSILON:
        return ([0.0, 0.0, 1.0], angle)
    return ([x / cross_norm for x in cross], angle)


def vector_bisect(a: Point, b: Point) -> list[float] | None:
    """Return a unit vector that bisects the minor angle between *a* and *b*.

    Args:
        a: First vector (2-D or 3-D).
        b: Second vector (2-D or 3-D, same dimension as *a*).

    Returns:
        A unit vector bisecting the angle, or ``None`` if *a* and *b*
        are directly opposite.

    Raises:
        ValueError: If either vector has zero length or dimensions differ.
    """
    if len(a) != len(b):
        raise ValueError(f"Vectors must have the same dimension, got {len(a)} and {len(b)}")
    norm_a: float = math.hypot(*a)
    norm_b: float = math.hypot(*b)
    if norm_a < EPSILON or norm_b < EPSILON:
        raise ValueError("Cannot bisect a zero-length vector")
    u: list[float] = [x / norm_a for x in a]
    v: list[float] = [x / norm_b for x in b]
    mid: list[float] = [u[i] + v[i] for i in range(len(u))]
    mid_norm: float = math.hypot(*mid)
    if mid_norm < EPSILON:
        return None
    return [x / mid_norm for x in mid]


def pointlist_bounds(
    pts: Sequence[Point],
) -> list[list[float]]:
    """Return ``[[min_x, min_y, ...], [max_x, max_y, ...]]`` for a list of points.

    Works for points of any dimension.

    Args:
        pts: A non-empty list of equal-dimension points.

    Returns:
        A pair of lists ``[mins, maxs]``.

    Raises:
        ValueError: If *pts* is empty or contains inconsistent dimensions.
    """
    if len(pts) == 0:
        raise ValueError("Cannot compute bounds of empty point list")
    dim: int = len(pts[0])
    mins: list[float] = list(pts[0])
    maxs: list[float] = list(pts[0])
    for pt in pts[1:]:
        if len(pt) != dim:
            raise ValueError(f"Inconsistent point dimensions: expected {dim}, got {len(pt)}")
        for d in range(dim):
            if pt[d] < mins[d]:
                mins[d] = pt[d]
            if pt[d] > maxs[d]:
                maxs[d] = pt[d]
    return [mins, maxs]


def closest_point(
    pt: Point,
    points: Sequence[Point],
) -> int:
    """Return the index of the closest point in *points* to *pt*.

    Args:
        pt: The reference point.
        points: A non-empty list of same-dimensional points.

    Returns:
        The integer index of the closest point.

    Raises:
        ValueError: If *points* is empty.
    """
    if len(points) == 0:
        raise ValueError("Cannot find closest point in an empty list")
    result: int = 0
    result_dist_sq: float = float("inf")
    for i, candidate in enumerate(points):
        dist_sq: float = sum((candidate[j] - pt[j]) ** 2 for j in range(len(pt)))
        if dist_sq < result_dist_sq:
            result_dist_sq = dist_sq
            result = i
    return result


def furthest_point(
    pt: Point,
    points: Sequence[Point],
) -> int:
    """Return the index of the furthest point in *points* from *pt*.

    Args:
        pt: The reference point.
        points: A non-empty list of same-dimensional points.

    Returns:
        The integer index of the furthest point.

    Raises:
        ValueError: If *points* is empty.
    """
    if len(points) == 0:
        raise ValueError("Cannot find furthest point in an empty list")
    result: int = 0
    result_dist_sq: float = -1.0
    for i, candidate in enumerate(points):
        dist_sq: float = sum((candidate[j] - pt[j]) ** 2 for j in range(len(pt)))
        if dist_sq > result_dist_sq:
            result_dist_sq = dist_sq
            result = i
    return result

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/math.py
#    Pure-Python port of the pieces of BOSL2's math.scad that pybosl2/paths.py
#    depends on (general numeric helpers and the deriv/deriv2/deriv3
#    calculus functions). No osuse()/BOSL2 runtime dependency. Built on
#    numpy: every vector-valued function here returns a real numpy ndarray
#    (float64) rather than a plain list.
#
# FileSummary: Maths
# DocCategory: Math & geometry
# FileGroup: BOSL2

"""General numeric helpers and numerical calculus (BOSL2 math.scad)."""

import math as _math
from collections.abc import Sequence

import numpy as np

# Default tolerance used throughout BOSL2 for floating-point comparisons.
EPSILON = 1e-9


def lerp(
    a: float | Sequence[float] | np.ndarray, b: float | Sequence[float] | np.ndarray, t: float
) -> float | np.ndarray:
    """Linearly interpolate between *a* and *b* by fraction *t* (scalar or vector)."""
    if isinstance(a, (list, tuple, np.ndarray)):
        return np.asarray(a, dtype=float) + (np.asarray(b, dtype=float) - np.asarray(a, dtype=float)) * t  # type: ignore[no-any-return]
    return a + (b - a) * t  # type: ignore[operator]


def lerpn(
    a: float | Sequence[float] | np.ndarray,
    b: float | Sequence[float] | np.ndarray,
    sides: int,
    endpoint: bool = True,
) -> np.ndarray:
    """Return *sides* points linearly interpolated between *a* and *b*, as an (sides, dim) ndarray.

    (or a length-sides 1-D ndarray for scalar *a*/*b*).

    If endpoint is True, the last returned point equals *b*; otherwise the
    range is divided into *sides* equal steps without reaching *b*.
    """
    if sides <= 0:
        return np.empty(0)
    if sides == 1:
        return np.asarray([a], dtype=float)
    denom = (sides - 1) if endpoint else sides
    return np.asarray([lerp(a, b, i / denom) for i in range(sides)], dtype=float)


def _dnu_calc(
    f1: float | Sequence[float] | np.ndarray,
    fc: float | Sequence[float] | np.ndarray,
    f2: float | Sequence[float] | np.ndarray,
    h1: float,
    h2: float,
) -> np.ndarray:
    if h2 < h1:
        f1 = lerp(fc, f1, h2 / h1)
    if h1 < h2:
        f2 = lerp(fc, f2, h1 / h2)
    return (np.asarray(f2, dtype=float) - np.asarray(f1, dtype=float)) / (2 * min(h1, h2))  # type: ignore[no-any-return]


def _deriv_nonuniform(
    data: Sequence[float] | Sequence[Sequence[float]] | np.ndarray,
    h: Sequence[float] | np.ndarray,
    closed: bool,
) -> np.ndarray:
    length = len(data)
    if closed:
        return np.asarray(
            [
                _dnu_calc(
                    data[(length + i - 1) % length],
                    data[i],
                    data[(i + 1) % length],
                    h[i - 1],
                    h[i],
                )
                for i in range(length)
            ],
            dtype=float,
        )
    out = [(np.asarray(data[1], dtype=float) - np.asarray(data[0], dtype=float)) / h[0]]
    for i in range(1, length - 1):
        out.append(_dnu_calc(data[i - 1], data[i], data[i + 1], h[i - 1], h[i]))
    out.append((np.asarray(data[length - 1], dtype=float) - np.asarray(data[length - 2], dtype=float)) / h[length - 2])
    return np.asarray(out, dtype=float)


def deriv(
    data: Sequence[float] | Sequence[Sequence[float]] | np.ndarray,
    height: float | Sequence[float] | np.ndarray = 1,
    closed: bool = False,
) -> np.ndarray:
    """Numeric first-derivative estimate of *data* (scalar- or vector-valued points), as an ndarray.

    Uses a symmetric derivative approximation for internal points and a
    two-point method at the endpoints of an open path. If *height* is a list it
    is treated as the (possibly non-uniform) per-segment sampling distance.
    """
    if not isinstance(height, (int, float)):
        return _deriv_nonuniform(data, height, closed)
    arr = np.asarray(data, dtype=float)
    length = len(arr)
    if closed:
        return np.asarray(
            [(arr[(i + 1) % length] - arr[(length + i - 1) % length]) / (2 * height) for i in range(length)]
        )
    if length < 3:
        first = arr[1] - arr[0]
        last = arr[length - 1] - arr[length - 2]
    else:
        first = 3 * (arr[1] - arr[0]) - (arr[2] - arr[1])
        last = (arr[length - 3] - arr[length - 2]) - 3 * (arr[length - 2] - arr[length - 1])
    out = [first / (2 * height)]
    for i in range(1, length - 1):
        out.append((arr[i + 1] - arr[i - 1]) / (2 * height))
    out.append(last / (2 * height))
    return np.asarray(out)


def deriv2(
    data: Sequence[float] | Sequence[Sequence[float]] | np.ndarray, height: float = 1, closed: bool = False
) -> np.ndarray:
    """Numeric second-derivative estimate of *data* (scalar- or vector-valued points), as an.

    ndarray.
    """
    arr = np.asarray(data, dtype=float)
    length = len(arr)
    if closed:
        return np.asarray(
            [
                (arr[(i + 1) % length] - 2 * arr[i] + arr[(length + i - 1) % length]) / (height * height)
                for i in range(length)
            ]
        )
    if length == 3:
        first = arr[0] - 2 * arr[1] + arr[2]
        last = arr[length - 1] - 2 * arr[length - 2] + arr[length - 3]
    elif length == 4:
        first = 2 * arr[0] - 5 * arr[1] + 4 * arr[2] - arr[3]
        last = -2 * arr[length - 1] + 5 * arr[length - 2] - 4 * arr[length - 3] + arr[length - 4]
    else:
        first = (35 * arr[0] - 104 * arr[1] + 114 * arr[2] - 56 * arr[3] + 11 * arr[4]) / 12
        last = (
            35 * arr[length - 1]
            - 104 * arr[length - 2]
            + 114 * arr[length - 3]
            - 56 * arr[length - 4]
            + 11 * arr[length - 5]
        ) / 12
    out = [first / (height * height)]
    for i in range(1, length - 1):
        out.append((arr[i + 1] - 2 * arr[i] + arr[i - 1]) / (height * height))
    out.append(last / (height * height))
    return np.asarray(out)


def deriv3(
    data: Sequence[float] | Sequence[Sequence[float]] | np.ndarray, height: float = 1, closed: bool = False
) -> np.ndarray:
    """Numeric third-derivative estimate of *data* (scalar- or vector-valued points), as an ndarray.

    Requires at least 5 points.
    """
    arr = np.asarray(data, dtype=float)
    length = len(arr)
    h3 = height * height * height
    if closed:
        return np.asarray(
            [
                (
                    -arr[(length + i - 2) % length]
                    + 2 * arr[(length + i - 1) % length]
                    - 2 * arr[(i + 1) % length]
                    + arr[(i + 2) % length]
                )
                / (2 * h3)
                for i in range(length)
            ]
        )
    first = (-5 * arr[0] + 18 * arr[1] - 24 * arr[2] + 14 * arr[3] - 3 * arr[4]) / 2
    second = (-3 * arr[0] + 10 * arr[1] - 12 * arr[2] + 6 * arr[3] - arr[4]) / 2
    last = (
        5 * arr[length - 1] - 18 * arr[length - 2] + 24 * arr[length - 3] - 14 * arr[length - 4] + 3 * arr[length - 5]
    ) / 2
    prelast = (
        3 * arr[length - 1] - 10 * arr[length - 2] + 12 * arr[length - 3] - 6 * arr[length - 4] + arr[length - 5]
    ) / 2
    out = [first / h3, second / h3]
    for i in range(2, length - 2):
        out.append((-arr[i - 2] + 2 * arr[i - 1] - 2 * arr[i + 1] + arr[i + 2]) / (2 * h3))
    out.append(prelast / h3)
    out.append(last / h3)
    return np.asarray(out)


# -- convenience helpers -------------------------------------------------------


def slerp(a: Sequence[float], b: Sequence[float], t: float) -> list[float]:
    """Spherical linear interpolation between two 3-D vectors.

    Interpolates between vectors *a* and *b* along the great-circle arc
    on a unit sphere and returns a unit-length vector. Input vectors need
    not be unit length.

    Args:
        a: First 3-D vector.
        b: Second 3-D vector.
        t: Interpolation fraction (0 returns *a*, 1 returns *b*).

    Returns:
        A unit-length interpolated vector as a list of 3 floats.

    Raises:
        ValueError: If either vector has zero length or the vectors are 180° apart.

    """
    na: float = _math.sqrt(sum(x * x for x in a))
    nb: float = _math.sqrt(sum(x * x for x in b))
    if na < EPSILON or nb < EPSILON:
        raise ValueError("Cannot slerp with zero-length vector")
    u: list[float] = [x / na for x in a]
    v: list[float] = [x / nb for x in b]
    dot: float = max(-1.0, min(1.0, sum(u[i] * v[i] for i in range(3))))
    theta: float = _math.acos(dot)
    if abs(theta - _math.pi) < EPSILON:
        raise ValueError("No solution when vectors are 180° apart")
    sin_theta: float = _math.sin(theta)
    if sin_theta < EPSILON:
        mid: list[float] = [u[i] + v[i] for i in range(3)]
        nm: float = _math.sqrt(sum(x * x for x in mid))
        return [x / nm for x in mid]
    w1: float = _math.sin((1.0 - t) * theta) / sin_theta
    w2: float = _math.sin(t * theta) / sin_theta
    return [u[i] * w1 + v[i] * w2 for i in range(3)]


def slerpn(
    a: Sequence[float],
    b: Sequence[float],
    n: int,
    endpoint: bool = True,
) -> list[list[float]]:
    """Return *n* evenly-spaced unit vectors on the great-circle arc between *a* and *b*.

    Args:
        a: First 3-D vector (need not be unit length).
        b: Second 3-D vector (need not be unit length).
        n: Number of points to return.
        endpoint: If True the last point equals unit(*b*); otherwise it is one step short.

    Returns:
        A list of *n* unit-length vectors as lists of 3 floats.

    Raises:
        ValueError: If either vector has zero length or the vectors are 180° apart.

    """
    na: float = _math.sqrt(sum(x * x for x in a))
    nb: float = _math.sqrt(sum(x * x for x in b))
    if na < EPSILON or nb < EPSILON:
        raise ValueError("Cannot slerpn with zero-length vector")
    u: list[float] = [x / na for x in a]
    v: list[float] = [x / nb for x in b]
    dot: float = max(-1.0, min(1.0, sum(u[i] * v[i] for i in range(3))))
    theta: float = _math.acos(dot)
    if abs(theta - _math.pi) < EPSILON:
        raise ValueError("No solution when vectors are 180° apart")
    sin_theta: float = _math.sin(theta)
    d: int = n - 1 if endpoint else n
    result: list[list[float]] = []
    for i in range(n):
        t_val: float = i / d if d > 0 else 0.0
        if sin_theta < EPSILON:
            mid: list[float] = [u[i] + v[i] for i in range(3)]
            nm: float = _math.sqrt(sum(x * x for x in mid))
            result.append([x / nm for x in mid])
        else:
            w1 = _math.sin((1.0 - t_val) * theta) / sin_theta
            w2 = _math.sin(t_val * theta) / sin_theta
            result.append([u[i] * w1 + v[i] * w2 for i in range(3)])
    return result


def modang(x: float) -> float:
    """Normalize an angle in degrees to the range [-180, 180).

    Args:
        x: An angle in degrees.

    Returns:
        The equivalent angle in [-180, 180).

    """
    ang: float = x % 360.0
    if ang >= 180.0:
        ang -= 360.0
    return ang


def constrain(
    v: float,
    minval: float | None = None,
    maxval: float | None = None,
) -> float:
    """Clamp *v* to the range [*minval*, *maxval*].

    If either bound is ``None``, that side is unconstrained.

    Args:
        v: The value to constrain.
        minval: Lower bound, or ``None`` for no lower constraint.
        maxval: Upper bound, or ``None`` for no upper constraint.

    Returns:
        The constrained value.

    """
    result: float = v
    if minval is not None and result < minval:
        result = minval
    if maxval is not None and result > maxval:
        result = maxval
    return result


def quant(v: float, unit: float) -> float:
    """Quantize *v* to the nearest integer multiple of *unit*.

    Args:
        v: The value to quantize.
        unit: The positive quantum to quantize to.

    Returns:
        The quantized value.

    Raises:
        ValueError: If *unit* is not positive.

    """
    if unit <= 0.0:
        raise ValueError(f"Quantum must be positive, got {unit}")
    return round(v / unit) * unit


def mean(v: Sequence[float]) -> float:
    """Arithmetic mean of the elements in *v*.

    Args:
        v: A non-empty sequence of numeric values.

    Returns:
        The mean value.

    Raises:
        ValueError: If *v* is empty.

    """
    if len(v) == 0:
        raise ValueError("Cannot compute mean of an empty sequence")
    return sum(v) / len(v)

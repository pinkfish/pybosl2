# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# LibFile: pybosl2/points.py
# FileSummary: The Point and Vector types every geometry API is expressed in.
# DocCategory: Math & geometry
# FileGroup: BOSL2

"""Lightweight 2‑D / 3‑D point and vector type shared across the pybosl2 geometry layer.

Provides :class:`Point` (mutable, ``x``/``y``/optional ``z``) with
elementwise arithmetic and numpy integration.  :class:`Vector` is a
backward-compatible alias for :class:`Point`.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import overload

import numpy as np

__all__ = ["Point", "Vector"]


# ---------------------------------------------------------------------------
# Point — mutable dataclass, 2‑D / 3‑D
# ---------------------------------------------------------------------------


@dataclass
class Point(Sequence[float]):
    """A mutable 2‑D or 3‑D point and vector.

    Inherits from :class:`~collections.abc.Sequence` for compatibility with
    functions that accept ``Sequence[float]``.

    If *z* is ``None`` the point is 2‑D (``is_2d`` returns ``True``); a
    concrete *z* makes it a 3‑D point.  Supports iteration, indexing,
    ``len()``, elementwise arithmetic (returning ``Point``), and ``np.asarray()``.

    Examples:
        .. code-block:: python

            from pybosl2 import Point

            p2 = Point(10.0, 20.0)
            assert p2.is_2d
            assert len(p2) == 2

            p3 = Point(10.0, 20.0, 5.0)
            assert not p3.is_2d
            assert len(p3) == 3

    """

    x: float
    y: float
    z: float | None = None

    def __init__(
        self,
        x: float | Sequence[float] | np.ndarray | Point = 0.0,
        y: float | None = None,
        z: float | None = None,
    ) -> None:
        """Initialize the instance."""
        if isinstance(x, Point):
            self.x, self.y, self.z = x.x, x.y, x.z
        elif isinstance(x, (int, float)):
            self.x = float(x)
            self.y = float(y) if y is not None else 0.0
            self.z = float(z) if z is not None else None
        else:
            arr = list(x)
            if len(arr) >= 3:
                self.x, self.y, self.z = float(arr[0]), float(arr[1]), float(arr[2])
            elif len(arr) == 2:
                self.x, self.y, self.z = float(arr[0]), float(arr[1]), None
            elif len(arr) == 1:
                self.x, self.y, self.z = float(arr[0]), 0.0, None
            else:
                raise ValueError(f"Expected 1-3 values, got {len(arr)}")

    @property
    def is_2d(self) -> bool:
        """``True`` when *z* is ``None`` (a 2‑D point)."""
        return self.z is None

    def __iter__(self) -> Iterator[float]:
        """Return an iterator."""
        return iter((self.x, self.y, self.z) if not self.is_2d else (self.x, self.y))  # type: ignore[arg-type]

    def __len__(self) -> int:
        """Return the number of items."""
        return 2 if self.is_2d else 3

    @overload
    def __getitem__(self, index: int) -> float: ...
    @overload
    def __getitem__(self, index: slice) -> Sequence[float]: ...

    def __getitem__(self, index: int | slice) -> float | Sequence[float]:
        """Return the item at index."""
        if isinstance(index, slice):
            return tuple(self)[index]
        if self.is_2d:
            return (self.x, self.y)[index]
        assert self.z is not None
        return (self.x, self.y, self.z)[index]

    def __repr__(self) -> str:
        """Return a string representation."""
        if self.is_2d:
            return f"Point({self.x!r}, {self.y!r})"
        return f"Point({self.x!r}, {self.y!r}, {self.z!r})"

    def __array__(self, dtype: None = None, copy: None = None) -> np.ndarray:
        """Return a numpy array representation."""
        if self.is_2d:
            arr = [self.x, self.y]
        else:
            assert self.z is not None
            arr = [self.x, self.y, self.z]
        return np.array(arr, dtype=dtype or float)

    def __add__(self, other: Sequence[float] | np.ndarray) -> Point:
        """Return self + other."""
        return Point.from_seq(np.asarray(self) + np.asarray(other, dtype=float))

    def __radd__(self, other: Sequence[float] | np.ndarray) -> Point:
        """Return other + self."""
        return Point.from_seq(np.asarray(other, dtype=float) + np.asarray(self))

    def __sub__(self, other: Sequence[float] | np.ndarray) -> Point:
        """Return self - other."""
        return Point.from_seq(np.asarray(self) - np.asarray(other, dtype=float))

    def __rsub__(self, other: Sequence[float] | np.ndarray) -> Point:
        """Return other - self."""
        return Point.from_seq(np.asarray(other, dtype=float) - np.asarray(self))

    def __neg__(self) -> Point:
        """Return -self."""
        return Point.from_seq(-np.asarray(self))

    def __eq__(self, other: object) -> bool:
        """Return whether two objects are equal."""
        if isinstance(other, Point):
            if self.is_2d != other.is_2d:
                return False
            if self.is_2d:
                return bool(self.x == other.x and self.y == other.y)
            return bool(self.x == other.x and self.y == other.y and self.z == other.z)
        if not isinstance(other, Sequence):
            return NotImplemented
        return bool(np.allclose(np.asarray(self), np.asarray(other, dtype=float)))

    def __truediv__(self, scalar: float) -> Point:
        """Return self / scalar."""
        return Point.from_seq(np.asarray(self) / scalar)

    def __rtruediv__(self, scalar: float) -> Point:
        """Return scalar / self."""
        return Point.from_seq(scalar / np.asarray(self))

    def __mul__(self, scalar: float) -> Point:
        """Return self * scalar."""
        return Point.from_seq(np.asarray(self) * scalar)

    def __rmul__(self, scalar: float) -> Point:
        """Return scalar * self."""
        return Point.from_seq(np.asarray(self) * scalar)

    def __abs__(self) -> float:
        """Return the absolute value."""
        return float(np.linalg.norm(np.asarray(self)))

    def __copy__(self) -> Point:
        """Return a shallow copy."""
        return Point(self.x, self.y, self.z)

    def copy(self) -> Point:
        """Return a copy of this point."""
        return Point(self.x, self.y, self.z)

    def dot(self, other: Sequence[float] | np.ndarray) -> float:
        """Dot product with another vector (2‑D or 3‑D)."""
        return float(np.dot(np.asarray(self), np.asarray(other, dtype=float)))

    def cross(self, other: Sequence[float] | np.ndarray) -> Point:
        """Cross product with another 3‑D vector, returning a :class:`Point`.

        Raises:
            ValueError: If this point is 2‑D (cross product requires 3‑D vectors).

        """
        if self.is_2d:
            raise ValueError("cross() requires a 3‑D point")
        return Point.from_seq(np.cross(np.asarray(self), np.asarray(other, dtype=float)))

    @classmethod
    def from_seq(cls, seq: Sequence[float] | np.ndarray) -> "Point":
        """Create a :class:`Point` from any array-like sequence of 2 or 3 values.

        Args:
            seq: A sequence, list, tuple, or ndarray of ``[x, y]`` or ``[x, y, z]``.

        Returns:
            A new :class:`Point`.

        Raises:
            ValueError: If the sequence has fewer than 2 or more than 3 elements.

        """
        arr = np.asarray(seq, dtype=float)
        if arr.shape[0] == 2:
            return cls(float(arr[0]), float(arr[1]))
        if arr.shape[0] == 3:
            return cls(float(arr[0]), float(arr[1]), float(arr[2]))
        raise ValueError(f"Expected 2 or 3 values, got {arr.shape[0]}")

    def astuple(self) -> tuple[float, float] | tuple[float, float, float]:
        """Return the point as a ``(x, y)`` or ``(x, y, z)`` tuple."""
        if self.is_2d:
            return (self.x, self.y)
        assert self.z is not None
        return (self.x, self.y, self.z)

    def tolist(self) -> list[float]:
        """Return the point as a ``[x, y]`` or ``[x, y, z]`` list."""
        if self.is_2d:
            return [self.x, self.y]
        assert self.z is not None
        return [self.x, self.y, self.z]

    @property
    def norm(self) -> float:
        """Euclidean length of the vector from origin to this point."""
        return float(np.linalg.norm(np.asarray(self)))

    def to_3d(self, z: float = 0.0) -> Point:
        """Return a 3‑D copy with the given *z*.

        For a 2‑D point this adds the Z coordinate. For a 3‑D point this
        returns a copy with *z* replaced (unless *z* equals ``self.z``).
        """
        return Point(self.x, self.y, self.z if self.z is not None and z == 0.0 else z)

    def normalized(self, error: Point | Sequence[float] | np.ndarray | None = None) -> Point:
        """Normalize this vector to unit length, returning a new Point.

        If it has (near) zero length, returns *error* if given, else raises ValueError.
        """
        from pybosl2.math import EPSILON

        arr = np.asarray(self, dtype=float)
        sides = float(np.linalg.norm(arr))
        if sides < EPSILON:
            if error is not None:
                return Point.from_seq(error)
            raise ValueError("Cannot normalize a zero vector")
        return Point.from_seq(arr / sides)

    def angle(self, other: Point) -> float:
        """Angle between this vector and *other* in radians.

        The result is always in the range [0, pi].
        """
        import math

        from pybosl2.math import EPSILON, constrain

        if len(self) != len(other):
            raise ValueError(f"Vectors must have the same dimension, got {len(self)} and {len(other)}")
        norm_a: float = math.hypot(*self)
        norm_b: float = math.hypot(*other)
        if norm_a < EPSILON or norm_b < EPSILON:
            raise ValueError("Cannot compute angle with a zero-length vector")
        dot: float = constrain(
            sum(self[i] * other[i] for i in range(len(self))) / (norm_a * norm_b),
            -1.0,
            1.0,
        )
        return math.acos(dot)

    def axis(self, other: Point) -> tuple[list[float], float]:
        """Return the axis vector (cross product) and angle between this vector and *other*.

        Requires 3-D vectors.
        """
        import math

        from pybosl2.math import EPSILON

        if len(self) != 3 or len(other) != 3:
            raise ValueError(f"axis requires 3-D vectors, got sizes {len(self)} and {len(other)}")
        norm_a: float = math.hypot(*self)
        norm_b: float = math.hypot(*other)
        if norm_a < EPSILON or norm_b < EPSILON:
            raise ValueError("Cannot compute axis with a zero-length vector")
        ang: float = self.angle(other)
        u: list[float] = [x / norm_a for x in self]
        v: list[float] = [x / norm_b for x in other]
        cross: list[float] = [
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        ]
        cross_norm: float = math.hypot(*cross)
        if cross_norm < EPSILON:
            return ([0.0, 0.0, 1.0], ang)
        return ([x / cross_norm for x in cross], ang)

    def bisect(self, other: Point) -> Point | None:
        """Return a unit vector that bisects the minor angle between this vector and *other*.

        Returns None if they are directly opposite.
        """
        import math

        from pybosl2.math import EPSILON

        if len(self) != len(other):
            raise ValueError(f"Vectors must have the same dimension, got {len(self)} and {len(other)}")
        norm_a: float = math.hypot(*self)
        norm_b: float = math.hypot(*other)
        if norm_a < EPSILON or norm_b < EPSILON:
            raise ValueError("Cannot bisect a zero-length vector")
        u: list[float] = [x / norm_a for x in self]
        v: list[float] = [x / norm_b for x in other]
        mid: list[float] = [u[i] + v[i] for i in range(len(u))]
        mid_norm: float = math.hypot(*mid)
        if mid_norm < EPSILON:
            return None
        return Point.from_seq([x / mid_norm for x in mid])

    def closest(self, points: Sequence[Point]) -> int:
        """Return the index of the closest point in *points* to this point."""
        if len(points) == 0:
            raise ValueError("Cannot find closest point in an empty list")
        result: int = 0
        result_dist_sq: float = float("inf")
        for i, candidate in enumerate(points):
            dist_sq: float = sum((candidate[j] - self[j]) ** 2 for j in range(len(self)))
            if dist_sq < result_dist_sq:
                result_dist_sq = dist_sq
                result = i
        return result

    def furthest(self, points: Sequence[Point]) -> int:
        """Return the index of the furthest point in *points* from this point."""
        if len(points) == 0:
            raise ValueError("Cannot find furthest point in an empty list")
        result: int = 0
        result_dist_sq: float = -1.0
        for i, candidate in enumerate(points):
            dist_sq: float = sum((candidate[j] - self[j]) ** 2 for j in range(len(self)))
            if dist_sq > result_dist_sq:
                result_dist_sq = dist_sq
                result = i
        return result


# ---------------------------------------------------------------------------
# Vector — backward-compatible alias for Point
# ---------------------------------------------------------------------------

Vector = Point

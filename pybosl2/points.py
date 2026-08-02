# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# DocCategory: internal

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
        .. pythonscad-example::

            from pybosl2.points import Point

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
        return iter((self.x, self.y, self.z) if not self.is_2d else (self.x, self.y))  # type: ignore[arg-type]

    def __len__(self) -> int:
        return 2 if self.is_2d else 3

    @overload
    def __getitem__(self, index: int) -> float: ...
    @overload
    def __getitem__(self, index: slice) -> Sequence[float]: ...

    def __getitem__(self, index: int | slice) -> float | Sequence[float]:
        if isinstance(index, slice):
            return tuple(self)[index]
        if self.is_2d:
            return (self.x, self.y)[index]
        assert self.z is not None
        return (self.x, self.y, self.z)[index]

    def __repr__(self) -> str:
        if self.is_2d:
            return f"Point({self.x!r}, {self.y!r})"
        return f"Point({self.x!r}, {self.y!r}, {self.z!r})"

    def __array__(self, dtype: None = None, copy: None = None) -> np.ndarray:
        if self.is_2d:
            arr = [self.x, self.y]
        else:
            assert self.z is not None
            arr = [self.x, self.y, self.z]
        return np.array(arr, dtype=dtype or float)

    def __add__(self, other: Sequence[float] | np.ndarray) -> Point:
        return Point.from_seq(np.asarray(self) + np.asarray(other, dtype=float))

    def __radd__(self, other: Sequence[float] | np.ndarray) -> Point:
        return Point.from_seq(np.asarray(other, dtype=float) + np.asarray(self))

    def __sub__(self, other: Sequence[float] | np.ndarray) -> Point:
        return Point.from_seq(np.asarray(self) - np.asarray(other, dtype=float))

    def __rsub__(self, other: Sequence[float] | np.ndarray) -> Point:
        return Point.from_seq(np.asarray(other, dtype=float) - np.asarray(self))

    def __neg__(self) -> Point:
        return Point.from_seq(-np.asarray(self))

    def __eq__(self, other: object) -> bool:
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
        return Point.from_seq(np.asarray(self) / scalar)

    def __rtruediv__(self, scalar: float) -> Point:
        return Point.from_seq(scalar / np.asarray(self))

    def __mul__(self, scalar: float) -> Point:
        return Point.from_seq(np.asarray(self) * scalar)

    def __rmul__(self, scalar: float) -> Point:
        return Point.from_seq(np.asarray(self) * scalar)

    def __abs__(self) -> float:
        return float(np.linalg.norm(np.asarray(self)))

    def __copy__(self) -> Point:
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


# ---------------------------------------------------------------------------
# Vector — backward-compatible alias for Point
# ---------------------------------------------------------------------------

Vector = Point

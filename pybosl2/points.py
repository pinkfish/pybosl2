# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# DocCategory: internal

"""Lightweight 2‑D / 3‑D point and vector types shared across the pybosl2 geometry layer.

Provides :class:`Point` (immutable, ``x``/``y``/optional ``z``) and
:class:`Vector` (mutable list subclass with elementwise arithmetic).
Both support 2‑D and 3‑D variants and integrate with numpy, shapely,
and path operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

__all__ = ["Point", "Vector"]


# ---------------------------------------------------------------------------
# Point — immutable, frozen-dataclass, 2‑D / 3‑D
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Point:
    """An immutable 2‑D or 3‑D point.

    If *z* is ``None`` the point is 2‑D (``is_2d`` returns ``True``); a
    concrete *z* makes it a 3‑D point.  Supports iteration, indexing,
    ``len()``, arithmetic, and ``np.asarray()``.

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

    @property
    def is_2d(self) -> bool:
        """``True`` when *z* is ``None`` (a 2‑D point)."""
        return self.z is None

    def __iter__(self):
        return iter((self.x, self.y) if self.is_2d else (self.x, self.y, self.z))

    def __len__(self) -> int:
        return 2 if self.is_2d else 3

    def __getitem__(self, index: int) -> float:
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

    def __add__(self, other: Sequence[float] | np.ndarray) -> np.ndarray:
        return np.asarray(self) + np.asarray(other, dtype=float)

    def __radd__(self, other: Sequence[float] | np.ndarray) -> np.ndarray:
        return np.asarray(other, dtype=float) + np.asarray(self)

    def __sub__(self, other: Sequence[float] | np.ndarray) -> np.ndarray:
        return np.asarray(self) - np.asarray(other, dtype=float)

    def __rsub__(self, other: Sequence[float] | np.ndarray) -> np.ndarray:
        return np.asarray(other, dtype=float) - np.asarray(self)

    def __neg__(self) -> np.ndarray:
        return -np.asarray(self)

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

    def __truediv__(self, scalar: float) -> np.ndarray:
        return np.asarray(self) / scalar

    def __rtruediv__(self, scalar: float) -> np.ndarray:
        return scalar / np.asarray(self)

    def __mul__(self, scalar: float) -> np.ndarray:
        return np.asarray(self) * scalar

    def __rmul__(self, scalar: float) -> np.ndarray:
        return np.asarray(self) * scalar

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

    def cross(self, other: Sequence[float] | np.ndarray) -> np.ndarray:
        """Cross product with another 3‑D vector, returning an ndarray.

        Raises:
            ValueError: If this point is 2‑D (cross product requires 3‑D vectors).
        """
        if self.is_2d:
            raise ValueError("cross() requires a 3‑D point")
        return np.cross(np.asarray(self), np.asarray(other, dtype=float))

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
# Vector — mutable list subclass with elementwise arithmetic, 2‑D / 3‑D
# ---------------------------------------------------------------------------


class Vector(list[float]):
    """A 2‑ or 3‑element list that supports elementwise arithmetic.

    Inherits from ``list[float]`` so it is a drop‑in for ``[x, y]`` or
    ``[x, y, z]`` lists.  Elementwise ``+``, ``-``, ``*`` replace the
    default list concatenation/repetition.

    ``len() == 2`` means a 2‑D vector (``is_2d`` is ``True``); ``len() == 3``
    is a 3‑D vector.  Use :meth:`to_3d` to add a Z coordinate.
    """

    def __init__(
        self, x: float | Sequence[float] | Iterable[float], y: float | None = None, z: float | None = None
    ) -> None:
        if isinstance(x, (list, tuple, np.ndarray)):
            super().__init__([float(v) for v in x])
        elif isinstance(x, (int, float)) and y is not None and z is not None:
            super().__init__([float(x), float(y), float(z)])
        elif isinstance(x, (int, float)) and y is not None:
            super().__init__([float(x), float(y)])
        elif isinstance(x, (int, float)):
            super().__init__([float(x)])
        else:
            super().__init__([float(v) for v in x])
        if len(self) not in (2, 3):
            raise ValueError(f"Vector must be 2-D or 3-D, got {len(self)} dimensions")

    @property
    def x(self) -> float:
        return self[0]

    @property
    def y(self) -> float:
        return self[1]

    @property
    def z(self) -> float | None:
        return self[2] if len(self) > 2 else None

    @property
    def is_2d(self) -> bool:
        """``True`` when this is a 2‑D vector (``len() == 2``)."""
        return len(self) == 2

    def to_3d(self, z: float = 0.0) -> "Vector":
        """Return a 3‑D copy with the given *z*.

        For a 2‑D vector this appends *z*; for a 3‑D vector this returns
        a copy with *z* replaced (unless *z* already matches).
        """
        if len(self) == 2:
            return Vector([self[0], self[1], z])
        return Vector([self[0], self[1], z])

    def dot(self, other: Sequence[float] | np.ndarray) -> float:
        """Dot product with another vector (2‑D or 3‑D)."""
        return float(np.dot(np.asarray(self), np.asarray(other, dtype=float)))

    def cross(self, other: Sequence[float] | np.ndarray) -> np.ndarray:
        """Cross product with another 3‑D vector, returning an ndarray.

        Raises:
            ValueError: If this vector is 2‑D (cross product requires 3‑D vectors).
        """
        if self.is_2d:
            raise ValueError("cross() requires a 3‑D vector")
        return np.cross(np.asarray(self), np.asarray(other, dtype=float))

    def __add__(self, other: list[float]) -> "Vector":  # type: ignore
        return Vector(a + b for a, b in zip(self, other, strict=False))

    def __radd__(self, other: list[float]) -> "Vector":
        return Vector(a + b for a, b in zip(other, self, strict=False))

    def __sub__(self, other: list[float]) -> "Vector":
        return Vector(a - b for a, b in zip(self, other, strict=False))

    def __rsub__(self, other: list[float]) -> "Vector":
        return Vector(a - b for a, b in zip(other, self, strict=False))

    def __neg__(self) -> "Vector":
        return Vector(-a for a in self)

    def __mul__(self, other: float) -> "Vector":  # type: ignore[override]
        return Vector(a * other for a in self)

    __rmul__ = __mul__  # type: ignore[assignment]

    @property
    def norm(self) -> float:
        """Euclidean length of the vector from origin."""
        return float(np.linalg.norm(np.asarray(self, dtype=float)))

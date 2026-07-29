# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Lightweight 2‑D / 3‑D point type shared across the pybosl2 geometry layer.

Provides :class:`Point`, a frozen dataclass with ``x``, ``y``, and optional
``z`` fields that works as a drop-in for ``[x, y]`` or ``[x, y, z]`` lists
and integrates with numpy, shapely, and path operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

__all__ = ["Point"]


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

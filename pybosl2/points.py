# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Lightweight 3-D point type shared across the pybosl2 geometry layer.

Provides :class:`Point3D`, a frozen dataclass with ``x``, ``y``, and ``z``
fields that works as a drop-in for ``[x, y, z]`` lists and integrates with
numpy, shapely, and path operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

__all__ = ["Point3D"]


@dataclass(frozen=True)
class Point3D:
    """An immutable 3-D point with ``x``, ``y``, and ``z`` float components.

    Usable anywhere a ``Sequence[float]`` of length 3 is expected -- it
    supports iteration, indexing, and ``len()`` so it is a drop-in for
    ``[x, y, z]`` lists and numpy arrays. Values are stored as Python
    floats, but can be passed to ``np.asarray()`` for vectorised maths.

    Examples:
        .. pythonscad-example::

            from pybosl2.points import Point3D

            p = Point3D(10.0, 20.0, 5.0)
            assert p.x == 10.0
            assert p.z == 5.0
            assert tuple(p) == (10.0, 20.0, 5.0)
            arr = np.asarray(p)  # ndarray([10., 20., 5.])
    """

    x: float
    y: float
    z: float

    def __iter__(self):
        return iter((self.x, self.y, self.z))

    def __len__(self) -> int:
        return 3

    def __getitem__(self, index: int) -> float:
        return (self.x, self.y, self.z)[index]

    def __repr__(self) -> str:
        return f"Point3D({self.x!r}, {self.y!r}, {self.z!r})"

    def __array__(self, dtype: None = None, copy: None = None) -> np.ndarray:
        return np.array([self.x, self.y, self.z], dtype=dtype or float)

    def __add__(self, other: Sequence[float] | np.ndarray) -> np.ndarray:
        a = np.asarray(self)
        b = np.asarray(other, dtype=float)
        return a + b

    def __radd__(self, other: Sequence[float] | np.ndarray) -> np.ndarray:
        return self.__add__(other)

    def __sub__(self, other: Sequence[float] | np.ndarray) -> np.ndarray:
        a = np.asarray(self)
        b = np.asarray(other, dtype=float)
        return a - b

    def __rsub__(self, other: Sequence[float] | np.ndarray) -> np.ndarray:
        a = np.asarray(other, dtype=float)
        b = np.asarray(self)
        return a - b

    def __neg__(self) -> np.ndarray:
        return np.array([-self.x, -self.y, -self.z])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Sequence):
            return NotImplemented
        a = np.asarray(self)
        b = np.asarray(other, dtype=float)
        return bool(np.allclose(a, b))

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

    def __copy__(self) -> Point3D:
        return Point3D(self.x, self.y, self.z)

    def copy(self) -> Point3D:
        """Return a copy of this point."""
        return Point3D(self.x, self.y, self.z)

    def dot(self, other: Sequence[float] | np.ndarray) -> float:
        """Dot product with another 3-D vector."""
        return float(np.dot(np.asarray(self), np.asarray(other, dtype=float)))

    def cross(self, other: Sequence[float] | np.ndarray) -> np.ndarray:
        """Cross product with another 3-D vector, returning an ndarray."""
        return np.cross(np.asarray(self), np.asarray(other, dtype=float))

    def astuple(self) -> tuple[float, float, float]:
        """Return the point as a ``(x, y, z)`` tuple."""
        return (self.x, self.y, self.z)

    def tolist(self) -> list[float]:
        """Return the point as a ``[x, y, z]`` list."""
        return [self.x, self.y, self.z]

    @property
    def norm(self) -> float:
        """Euclidean length of the vector from origin to this point."""
        return float(np.linalg.norm(np.asarray(self)))

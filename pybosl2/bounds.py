# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# DocCategory: internal

"""Axis-aligned bounding boxes for 2-D and 3-D geometry.

Provides :class:`Bounds2D` and :class:`Bounds3D` dataclasses returned
by :meth:`Path2D.bounds`, :meth:`Path3D.bounds`, and solid bounding-box
methods throughout pybosl2. Each holds the min/max corners and
pre-computed width/length (or width/length/height) so users can write
``path.bounds().width`` instead of ``path.bounds()[1][0] - path.bounds()[0][0]``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["Bounds2D", "Bounds3D"]


@dataclass(frozen=True)
class Bounds2D:
    """Axis-aligned bounding box of a 2-D path.

    Returned by :meth:`~pybosl2.paths.Path2D.bounds` with the min/max
    corners and pre-computed width and length.
    """

    min_x: float
    min_y: float
    max_x: float
    max_y: float
    width: float
    length: float

    @classmethod
    def from_points(cls, points: Any) -> "Bounds2D":
        """Create from any array-like of 2-D points."""
        import numpy as np

        arr = np.asarray(points, dtype=float)
        mn = arr.min(axis=0)
        mx = arr.max(axis=0)
        return cls(
            min_x=float(mn[0]),
            min_y=float(mn[1]),
            max_x=float(mx[0]),
            max_y=float(mx[1]),
            width=float(mx[0] - mn[0]),
            length=float(mx[1] - mn[1]),
        )


@dataclass(frozen=True)
class Bounds3D:
    """Axis-aligned bounding box of a 3-D path or solid.

    Returned by :meth:`~pybosl2.paths.Path3D.bounds` and solid bounding-box
    methods with the min/max corners and pre-computed width, length, and
    height.
    """

    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float
    width: float
    length: float
    height: float

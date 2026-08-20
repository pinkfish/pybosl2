# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# LibFile: pybosl2/bounds.py
# FileSummary: Axis-aligned bounding boxes (Bounds2D / Bounds3D).
# DocCategory: Math & geometry
# FileGroup: BOSL2

"""Axis-aligned bounding boxes for 2-D and 3-D geometry.

Provides :class:`Bounds2D` and :class:`Bounds3D` dataclasses returned
by :meth:`Path2D.bounds`, :meth:`Path3D.bounds`, and solid bounding-box
methods throughout pybosl2. Each holds the min/max corners and
pre-computed width/length (or width/length/height) so users can write
``path.bounds().width`` instead of ``path.bounds()[1][0] - path.bounds()[0][0]``.
"""

from __future__ import annotations

from dataclasses import dataclass

from pybosl2.points import Point

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

    @property
    def center(self) -> Point:
        """The (x, y) centre of the bounding box as a 2‑D :class:`Point`."""
        return Point((self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2)

    @property
    def size(self) -> tuple[float, float]:
        """The (width, length) of the bounding box."""
        return (self.width, self.length)


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

    @property
    def center(self) -> Point:
        """The (x, y, z) centre of the bounding box as a 3‑D :class:`Point`."""
        return Point(
            (self.min_x + self.max_x) / 2,
            (self.min_y + self.max_y) / 2,
            (self.min_z + self.max_z) / 2,
        )

    @property
    def size(self) -> tuple[float, float, float]:
        """The (width, length, height) of the bounding box."""
        return (self.width, self.length, self.height)

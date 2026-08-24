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

:class:`Bounds2D` and :class:`Bounds3D` are what **every** ``bounds()`` in pybosl2 returns
(SPEC S-2b) -- shapes on either backend, :class:`~pybosl2.path2d.Path2D`,
:class:`~pybosl2.path3d.Path3D`, :class:`~pybosl2.regions.Region` and :class:`~pybosl2.vnf.VNF`.
One name, one meaning: ``bounds()`` answers a box, and the box carries every spelling of itself
so no caller has to do the arithmetic and no implementation has to pick a winner::

    box = cuboid([40, 30, 20]).bounds()
    box.min, box.max        # corners, as Points
    box.center, box.size    # centre and extent
    box.width               # or .length / .height

They used to disagree -- shapes answered a bare ``(centre, size)`` pair, paths and meshes a
dataclass, regions a NumPy array -- so ``lo, hi = solid.bounds()``, the obvious reading of the
name, silently bound a *centre* to ``lo``. These types are the single answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pybosl2.points import Point

if TYPE_CHECKING:
    from collections.abc import Sequence

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

    @property
    def min(self) -> Point:
        """The lower corner as a 2-D :class:`~pybosl2.points.Point`."""
        return Point(self.min_x, self.min_y)

    @property
    def max(self) -> Point:
        """The upper corner as a 2-D :class:`~pybosl2.points.Point`."""
        return Point(self.max_x, self.max_y)

    @classmethod
    def from_min_max(cls, lo: "Sequence[float]", hi: "Sequence[float]") -> "Bounds2D":
        """Build from the two opposite corners.

        Args:
            lo: the lower corner, ``[x, y]``.
            hi: the upper corner, ``[x, y]``.

        Returns:
            The bounding box, with width and length derived.

        Examples:
            >>> Bounds2D.from_min_max([0, 0], [10, 5]).size
            (10.0, 5.0)

        """
        return cls(
            min_x=float(lo[0]),
            min_y=float(lo[1]),
            max_x=float(hi[0]),
            max_y=float(hi[1]),
            width=float(hi[0]) - float(lo[0]),
            length=float(hi[1]) - float(lo[1]),
        )

    @classmethod
    def from_center_size(cls, center: "Sequence[float]", size: "Sequence[float]") -> "Bounds2D":
        """Build from a centre point and an extent.

        This is the form the native backends report, so it is the conversion every shape's
        ``bounds()`` goes through rather than doing the halving inline.

        Args:
            center: the box centre, ``[x, y]``.
            size: the box extent, ``[width, length]``.

        Returns:
            The bounding box, with the corners derived.

        Examples:
            >>> Bounds2D.from_center_size([0, 0], [10, 5]).min_x
            -5.0

        """
        half = [float(size[0]) / 2, float(size[1]) / 2]
        return cls.from_min_max(
            [float(center[0]) - half[0], float(center[1]) - half[1]],
            [float(center[0]) + half[0], float(center[1]) + half[1]],
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

    @property
    def min(self) -> Point:
        """The lower corner as a 3-D :class:`~pybosl2.points.Point`."""
        return Point(self.min_x, self.min_y, self.min_z)

    @property
    def max(self) -> Point:
        """The upper corner as a 3-D :class:`~pybosl2.points.Point`."""
        return Point(self.max_x, self.max_y, self.max_z)

    @classmethod
    def from_min_max(cls, lo: "Sequence[float]", hi: "Sequence[float]") -> "Bounds3D":
        """Build from the two opposite corners.

        Args:
            lo: the lower corner, ``[x, y, z]``.
            hi: the upper corner, ``[x, y, z]``.

        Returns:
            The bounding box, with width, length and height derived.

        Examples:
            >>> Bounds3D.from_min_max([0, 0, 0], [10, 5, 2]).size
            (10.0, 5.0, 2.0)

        """
        return cls(
            min_x=float(lo[0]),
            min_y=float(lo[1]),
            min_z=float(lo[2]),
            max_x=float(hi[0]),
            max_y=float(hi[1]),
            max_z=float(hi[2]),
            width=float(hi[0]) - float(lo[0]),
            length=float(hi[1]) - float(lo[1]),
            height=float(hi[2]) - float(lo[2]),
        )

    @classmethod
    def from_center_size(cls, center: "Sequence[float]", size: "Sequence[float]") -> "Bounds3D":
        """Build from a centre point and an extent.

        This is the form the native backends report, so it is the conversion every solid's
        ``bounds()`` goes through rather than doing the halving inline.

        Args:
            center: the box centre, ``[x, y, z]``.
            size: the box extent, ``[width, length, height]``.

        Returns:
            The bounding box, with the corners derived.

        Examples:
            >>> Bounds3D.from_center_size([0, 0, 0], [40, 30, 20]).min_z
            -10.0

        """
        half = [float(size[i]) / 2 for i in range(3)]
        return cls.from_min_max(
            [float(center[i]) - half[i] for i in range(3)],
            [float(center[i]) + half[i] for i in range(3)],
        )

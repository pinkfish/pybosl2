# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Axis-aligned bounding boxes for 2-D and 3-D geometry.

Provides :class:`Bounds2D` and :class:`Bounds3D` dataclasses returned
by :meth:`Path.bounds`, :meth:`Path3D.bounds`, and solid bounding-box
methods throughout pybosl2. Each holds the min/max corners and
pre-computed width/length (or width/length/height) so users can write
``path.bounds().width`` instead of ``path.bounds()[1][0] - path.bounds()[0][0]``.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Bounds2D", "Bounds3D"]


@dataclass(frozen=True)
class Bounds2D:
    """Axis-aligned bounding box of a 2-D path.

    Returned by :meth:`~pybosl2.paths.Path.bounds` with the min/max
    corners and pre-computed width and length.
    """

    min_x: float
    min_y: float
    max_x: float
    max_y: float
    width: float
    length: float


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

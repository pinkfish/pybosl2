# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/shapes2d/__init__.py
# FileSummary: 2D primitives, polygons, curves, text and rounding (BOSL2 shapes2d.scad).
# DocCategory: Foundational
# FileGroup: BOSL2

"""2D primitives, polygons, curves, text and rounding (BOSL2 shapes2d.scad)."""

from __future__ import annotations

from pybosl2._helpers import AnchorType

from .base import (
    Bosl2Shape2D,
    _finish,
)
from .circle import (
    arc,
    circle,
    ellipse,
    glued_circles,
    keyhole,
    reuleaux_polygon,
    ring,
)
from .curves import (
    egg,
    jittered_poly,
    squircle,
    star,
    supershape,
    teardrop2d,
)
from .ops import (
    cross,
    fill,
    hull,
    osimport,
    round2d,
    shell2d,
    text,
)
from .square import (
    hexagon,
    octagon,
    pentagon,
    polygon,
    rect,
    rect_path,
    regular_ngon,
    right_triangle,
    square,
    trapezoid,
)

# Backward compatibility alias
CsgShape2D = Bosl2Shape2D

__all__ = [
    "AnchorType",
    "Bosl2Shape2D",
    "CsgShape2D",
    "square",
    "rect",
    "rect_path",
    "arc",
    "circle",
    "polygon",
    "regular_ngon",
    "pentagon",
    "hexagon",
    "octagon",
    "right_triangle",
    "trapezoid",
    "star",
    "jittered_poly",
    "teardrop2d",
    "egg",
    "ellipse",
    "glued_circles",
    "supershape",
    "squircle",
    "keyhole",
    "ring",
    "reuleaux_polygon",
    "text",
    "round2d",
    "shell2d",
    "cross",
    "fill",
    "osimport",
    "hull",
    "_finish",
]

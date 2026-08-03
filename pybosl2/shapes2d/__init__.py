# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/shapes2d/__init__.py
# FileSummary: 2D primitives, polygons, curves, text and rounding (BOSL2 shapes2d.scad).
# DocCategory: Foundational
# FileGroup: BOSL2

from __future__ import annotations

# Export the private native polygon callable for external module imports (e.g. cylinder/cuboid)
from pybosl2._native import native as _native

from .base import (
    AnchorType,
    Bosl2Shape2D,
    _anchor_offset_generic,
    _arc_points,
    _as_native_2d,
    _circle_from_3pts,
    _circle_pts,
    _dir2,
    _finish,
    _frag_count,
    _is_child_2d,
    _pick_radius,
    _polar_to_xy,
    _quant,
    _rotate2d,
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
    _squircle_fg_path,
    egg,
    jittered_poly,
    squircle,
    squircle_radius_fg,
    star,
    supershape,
    teardrop2d,
)
from .ops import (
    cross,
    fill,
    hull,
    round2d,
    shell2d,
    text,
)
from .square import (
    _rect_path,
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

_opolygon = _native("polygon")

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
    "hull",
    # Internal helpers re-exported for package-internal imports
    "_opolygon",
    "_frag_count",
    "_pick_radius",
    "_polar_to_xy",
    "_rotate2d",
    "_circle_pts",
    "_dir2",
    "_finish",
    "_as_native_2d",
    "_is_child_2d",
    "_anchor_offset_generic",
    "_quant",
    "_arc_points",
    "_rect_path",
    "_circle_from_3pts",
    "squircle_radius_fg",
    "_squircle_fg_path",
]

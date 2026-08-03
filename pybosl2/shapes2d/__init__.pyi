# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

from typing import Any

from .base import (
    AnchorType as AnchorType,
)
from .base import (
    Bosl2Shape2D as Bosl2Shape2D,
)
from .base import (
    _anchor_offset_generic as _anchor_offset_generic,
)
from .base import (
    _arc_points as _arc_points,
)
from .base import (
    _as_native_2d as _as_native_2d,
)
from .base import (
    _circle_from_3pts as _circle_from_3pts,
)
from .base import (
    _circle_pts as _circle_pts,
)
from .base import (
    _dir2 as _dir2,
)
from .base import (
    _finish as _finish,
)
from .base import (
    _frag_count as _frag_count,
)
from .base import (
    _is_child_2d as _is_child_2d,
)
from .base import (
    _pick_radius as _pick_radius,
)
from .base import (
    _polar_to_xy as _polar_to_xy,
)
from .base import (
    _quant as _quant,
)
from .base import (
    _rotate2d as _rotate2d,
)
from .circle import (
    arc as arc,
)
from .circle import (
    circle as circle,
)
from .circle import (
    ellipse as ellipse,
)
from .circle import (
    glued_circles as glued_circles,
)
from .circle import (
    keyhole as keyhole,
)
from .circle import (
    reuleaux_polygon as reuleaux_polygon,
)
from .circle import (
    ring as ring,
)
from .curves import (
    _squircle_fg_path as _squircle_fg_path,
)
from .curves import (
    egg as egg,
)
from .curves import (
    jittered_poly as jittered_poly,
)
from .curves import (
    squircle as squircle,
)
from .curves import (
    squircle_radius_fg as squircle_radius_fg,
)
from .curves import (
    star as star,
)
from .curves import (
    supershape as supershape,
)
from .curves import (
    teardrop2d as teardrop2d,
)
from .ops import (
    cross as cross,
)
from .ops import (
    fill as fill,
)
from .ops import (
    hull as hull,
)
from .ops import (
    round2d as round2d,
)
from .ops import (
    shell2d as shell2d,
)
from .ops import (
    text as text,
)
from .square import (
    _rect_path as _rect_path,
)
from .square import (
    hexagon as hexagon,
)
from .square import (
    octagon as octagon,
)
from .square import (
    pentagon as pentagon,
)
from .square import (
    polygon as polygon,
)
from .square import (
    rect as rect,
)
from .square import (
    rect_path as rect_path,
)
from .square import (
    regular_ngon as regular_ngon,
)
from .square import (
    right_triangle as right_triangle,
)
from .square import (
    square as square,
)
from .square import (
    trapezoid as trapezoid,
)

CsgShape2D = Bosl2Shape2D
_opolygon: Any

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# The anchor-offset helpers for each primitive family (box/cylinder/sphere/convex-hull) that the SDF
# backend's cuboid()/cyl()/sphere()/etc. need. The shared pieces are NOT duplicated here: the
# edge-selector mini-language (`_edges()`, `EDGES_ALL`, edge vectors like `TOP+LEFT`) comes from
# bosl2._edges_lang and the radius/diameter resolver (`_pick_radius`) from bosl2.shapes2d, so both
# backends share one implementation of each (see M6). This module re-exports them for convenience.
import math
from typing import TYPE_CHECKING

# ---------------------------------------------------------------------------
# cuboid() edge-set machinery -- the shared mini-language in bosl2._edges_lang (used by both
# backends), imported rather than duplicated. Re-exported so bosl2._sdf.paths and
# bosl2._sdf.shapes3d can keep importing these names from here. Importing _edges_lang (pure Python,
# no numpy/native) keeps the SDF backend from depending on the large bosl2.shapes3d CSG module.
# ---------------------------------------------------------------------------
from bosl2._edges_lang import (  # noqa: F401
    _MAJOR_AXIS_VALID,
    EDGE_OFFSETS,
    EDGES_ALL,
    EDGES_NONE,
    _edge_set,
    _edges,
    _is_edge_array,
    _is_plain_vector,
)

# The shared radius-priority resolver (radius1 > d1/2 > radius2 > d2/2 > radius > d/2 > dflt).
# Re-exported so bosl2._sdf.paths and bosl2._sdf.shapes3d can import it from here as before.
from bosl2.shapes2d import _pick_radius  # noqa: F401

if TYPE_CHECKING:
    from collections.abc import Sequence

# ---------------------------------------------------------------------------
# Anchor-offset helpers, one per primitive family (SDF-backend specific)
# ---------------------------------------------------------------------------


def _anchor_offset_box3(size: "Sequence[float]", anchor: "Sequence[float]") -> list[float]:
    a = list(anchor)
    return [-a[i] * size[i] / 2 for i in range(3)]


def _anchor_offset_hull3(points: "Sequence[Sequence[float]]", anchor: "Sequence[float]") -> list[float]:
    a = list(anchor)
    if a[0] == 0 and a[1] == 0 and a[2] == 0:
        return [0.0, 0.0, 0.0]
    best = max(points, key=lambda p: p[0] * a[0] + p[1] * a[1] + p[2] * a[2])
    return [-best[0], -best[1], -best[2]]


def _anchor_offset_cyl(
    radius1: float, radius2: float, length: float, anchor: "Sequence[float]", axis: int = 2
) -> list[float]:
    a = list(anchor)
    az = a[axis]
    r_at = radius1 if az < 0 else (radius2 if az > 0 else (radius1 + radius2) / 2)
    radial_axes = [i for i in range(3) if i != axis]
    radial = [a[i] for i in radial_axes]
    rn = math.hypot(*radial)
    if rn > 0:
        radial = [x / rn * r_at for x in radial]
    offset = [0.0, 0.0, 0.0]
    offset[axis] = az * length / 2
    for i, ax in enumerate(radial_axes):
        offset[ax] = radial[i]
    return [-x for x in offset]


def _anchor_offset_sphere(r: float, anchor: "Sequence[float]") -> list[float]:
    a = list(anchor)
    n = math.hypot(*a)
    if n == 0:
        return [0.0, 0.0, 0.0]
    return [-a[i] / n * r for i in range(3)]

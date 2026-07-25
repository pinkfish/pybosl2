# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# The cuboid() edge-selector mini-language (`_edges()`, `EDGES_ALL`, edge vectors like
# `TOP+LEFT`) and the anchor-offset helpers for each primitive family (box/cylinder/
# sphere/convex-hull), needed by the SDF backend's cuboid()/cyl()/sphere()/etc.
# A vendored subset of bosl2/shapes3d.py's edge/anchor helpers, kept identical to bosl2's
# algorithm so both backends accept the same edge selectors. The radius/diameter resolver
# (_pick_radius) is NOT copied here -- it is imported from bosl2.shapes2d so the two backends
# share a single implementation (M6: no SDF/CSG math duplication).
import math
from collections.abc import Sequence

# The shared radius-priority resolver (radius1 > d1/2 > radius2 > d2/2 > radius > d/2 > dflt).
# Re-exported so bosl2._sdf.paths and bosl2._sdf.shapes3d can import it from here as before.
from bosl2.shapes2d import _pick_radius  # noqa: F401

# ---------------------------------------------------------------------------
# cuboid() edge-set machinery -- mirrors BOSL2 attachments.scad.
# M6: this is the SAME mini-language as bosl2/shapes3d.py (verified identical over every
# selector), so it is imported from there rather than kept as a second copy. Re-exported so
# bosl2._sdf.paths and bosl2._sdf.shapes3d can keep importing these names from here.
# ---------------------------------------------------------------------------
from bosl2.shapes3d import (  # noqa: E402, F401
    _MAJOR_AXIS_VALID,
    EDGE_OFFSETS,
    EDGES_ALL,
    EDGES_NONE,
    _edge_set,
    _edges,
    _is_edge_array,
    _is_plain_vector,
)

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

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# The anchor-offset helpers for each primitive family (box/cylinder/sphere/convex-hull) that the SDF
# backend's cuboid()/cyl()/sphere()/etc. need. The shared pieces are NOT duplicated here: the
# edge-selector mini-language (`edges()`, `EDGES_ALL`, edge vectors like `TOP+LEFT`) comes from
# pybosl2._edges_lang and the radius/diameter resolver (`_pick_radius`) from pybosl2.shapes2d, so both
# backends share one implementation of each (see M6). This module re-exports them for convenience.

# ---------------------------------------------------------------------------
# cuboid() edge-set machinery -- the shared mini-language in pybosl2._edges_lang (used by both
# backends), imported rather than duplicated. Re-exported so pybosl2.sdf.paths and
# pybosl2.sdf.shapes3d can keep importing these names from here. Importing _edges_lang (pure Python,
# no numpy/native) keeps the SDF backend from depending on the large pybosl2.shapes3d CSG module.
# ---------------------------------------------------------------------------
from pybosl2._edges_lang import (
    EDGE_OFFSETS,
    EDGES_ALL,
    EDGES_NONE,
    _edge_set,
    _is_edge_array,
    _is_plain_vector,
    edges,
)

# Canonical 3-D anchor offset implementations (shared with shapes3d/base.py).
from pybosl2._helpers import (
    anchor_offset_box3 as _anchor_offset_box3,
)
from pybosl2._helpers import (
    anchor_offset_cyl as _anchor_offset_cyl,
)
from pybosl2._helpers import (
    anchor_offset_hull3 as _anchor_offset_hull3,
)
from pybosl2._helpers import (
    anchor_offset_sphere as _anchor_offset_sphere,
)

# The shared radius-priority resolver (radius1 > d1/2 > radius2 > d2/2 > radius > d/2 > dflt).
from pybosl2._helpers import pick_radius as _pick_radius

__all__ = [
    "EDGE_OFFSETS",
    "EDGES_ALL",
    "EDGES_NONE",
    "_edge_set",
    "edges",
    "_is_edge_array",
    "_is_plain_vector",
    "_pick_radius",
    "_anchor_offset_box3",
    "_anchor_offset_cyl",
    "_anchor_offset_hull3",
    "_anchor_offset_sphere",
]

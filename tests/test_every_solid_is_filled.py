# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Both backends agree about which points are *inside* each primitive (SPEC PAR-1, PAR-5).

Every cross-backend instrument this campaign built before T126 asked about a **surface**:
`bounds()` compares two analytic boxes, `tests/test_every_part_field_evaluates.py` evaluates the
field at the CSG mesh's *vertices*, and `tests/test_sdf_rim.py` evaluates it on the *profile* CSG
revolves. None of them asks whether the solid is actually filled, and that is how T126's defect
survived for as long as the SDF backend has existed: every tapered `cyl` had lost the half that
ends at its narrower rim, and a cone's mesh vertices are its apex and its two end rings -- all
corners, where the broken term read zero anyway.

T126 closed that for cylinders, inside the rim file where the fix lived. This asks the same
question of the **whole primitive family**, because the next one will not be a cylinder.

**The result is negative, and the instrument is calibrated.** No other tapered primitive has the
defect: `prismoid` (tapering either way, obliquely, and to a point), `regular_prism`, `pie_slice`,
`tube`, `rect_tube` and `cuboid` all agree exactly. A negative result from an uncalibrated
instrument is worth nothing, so the calibration was run and is recorded: against
`pybosl2/sdf/shapes3d.py` as it stood *before* T126, this file reports **5 failed, 13 passed** --

| row | points inside the mesh but outside the field | worst |
|---|---|---|
| `cyl narrowing` | 96 | +2.8650 |
| `cyl widening` | 96 | +2.8650 |
| `cyl to a point` | 52 | +3.4401 |
| `cyl rounded` | 84 | +2.3412 |
| `cyl chamfered` | 84 | +2.3412 |

-- and the other thirteen rows stay clean, `cyl plain` among them, because an untapered cylinder
never had the defect. So it fires on exactly the shapes that were broken and on nothing else.
"""

from __future__ import annotations

import math

import pytest

import pybosl2.solid as facade
from pybosl2 import use_backend, use_defaults
from pybosl2.sdf._libfive import lv

#: Points per axis. 13^3 is 2197 probes per shape, of which a few hundred land inside a typical
#: solid -- enough that a missing half, quadrant or slab cannot slip between them, and cheap
#: enough to run over the whole family. A defect thinner than the grid step is invisible here by
#: construction; `tests/test_sdf_rim.py` is where a cylinder's thin cases are pinned sharply.
GRID = 13

#: Curves are meshed with this many sides, so the facet sagitta below is small and computable.
#: Left to the ambient default the band would be 16x wider and swallow most of a small shape.
SIDES = 64

#: Floating-point slack on top of the derived band. A point exactly on a face reads zero.
FLOOR = 1e-6


def _facet_band(reach: float) -> float:
    """How far a *SIDES*-sided mesh of a curve at radius *reach* can sit from the true surface.

    The sagitta of one polygon step -- the same figure, derived the same way, as
    `tests/test_every_part_field_evaluates.py::_facet_bound`. Inside this band the two backends
    are *entitled* to disagree: a tessellation inscribes, so the mesh of a round shape is
    slightly small and the mesh of a round *hole* is slightly tight.
    """
    return (1.0 - math.cos(math.pi / SIDES)) * reach


#: The primitive family, with the tapers and degenerate ends that T126 showed are where the
#: interior goes missing. `cyl` is here as the regression guard for T126 and T127 both.
SOLIDS = [
    ("cuboid", {"size": [20, 14, 10]}),
    ("prismoid narrowing", {"size1": [20, 20], "size2": [8, 8], "height": 20}),
    ("prismoid widening", {"size1": [8, 8], "size2": [20, 20], "height": 20}),
    ("prismoid to a point", {"size1": [20, 20], "size2": [0.001, 0.001], "height": 20}),
    ("prismoid oblique", {"size1": [20, 12], "size2": [8, 16], "height": 20}),
    ("cyl plain", {"radius": 10, "height": 20}),
    ("cyl narrowing", {"radius1": 10, "radius2": 2, "height": 20}),
    ("cyl widening", {"radius1": 2, "radius2": 10, "height": 20}),
    ("cyl to a point", {"radius1": 10, "radius2": 0, "height": 20}),
    ("cyl rounded", {"radius1": 10, "radius2": 4, "height": 20, "rounding": 2}),
    ("cyl chamfered", {"radius1": 10, "radius2": 4, "height": 20, "chamfer": 2}),
    ("regular_prism narrowing", {"sides": 6, "radius1": 10, "radius2": 4, "height": 20}),
    ("regular_prism widening", {"sides": 6, "radius1": 4, "radius2": 10, "height": 20}),
    ("regular_prism plain", {"sides": 5, "radius": 10, "height": 20}),
    ("pie_slice", {"radius1": 10, "radius2": 4, "height": 20, "angle": 70}),
    ("sphere", {"radius": 9}),
    ("tube", {"height": 20, "outer_radius": 10, "wall": 2}),
    ("rect_tube", {"height": 20, "size": [20, 20], "wall": 2}),
]


def _disagreements(name: str, kwargs: dict[str, object]) -> tuple[int, float, int, float, int]:
    """Sweep one solid's bounding box, returning (missing, worst, extra, worst, sampled)."""
    builder = getattr(facade, name.split()[0])
    with use_backend("csg"), use_defaults(fn=SIDES):
        csg = builder(**kwargs)
        box = csg.bounds()
    with use_backend("sdf"), use_defaults(fn=SIDES):
        field = builder(**kwargs)
    tree = field._sdf_fn(lv.x(), lv.y(), lv.z())

    lo = (box.min_x, box.min_y, box.min_z)
    hi = (box.max_x, box.max_y, box.max_z)
    reach = max(abs(v) for v in (box.min_x, box.max_x, box.min_y, box.max_y))
    band = _facet_band(reach) + FLOOR

    missing = extra = sampled = 0
    worst_missing = worst_extra = 0.0
    for i in range(GRID):
        for j in range(GRID):
            for k in range(GRID):
                point = [lo[a] + (hi[a] - lo[a]) * ((i, j, k)[a] + 0.5) / GRID for a in range(3)]
                value = float(tree(*point))
                if abs(value) <= band:
                    continue
                sampled += 1
                if csg.inside(point):
                    if value > 0:
                        missing += 1
                        worst_missing = max(worst_missing, value)
                elif value < 0:
                    extra += 1
                    worst_extra = max(worst_extra, -value)
    return missing, worst_missing, extra, worst_extra, sampled


@pytest.mark.parametrize(("label", "kwargs"), [(label, kw) for label, kw in SOLIDS], ids=[s[0] for s in SOLIDS])
def test_both_backends_agree_about_the_inside(label: str, kwargs: dict[str, object]) -> None:
    """A point the CSG solid contains is in the SDF field, and vice versa.

    Two-sided, unlike the vertex and profile probes, which is the whole point: a solid that is too
    *small* is what nothing could see. The band it skips is derived from the mesh's own facet
    sagitta rather than chosen, because inside that band the two are entitled to differ -- a
    tessellation inscribes, so a round shape's mesh is slightly small and a round hole's mesh is
    slightly tight.
    """
    missing, worst_missing, extra, worst_extra, sampled = _disagreements(label, kwargs)
    assert sampled >= 200, f"{label}: only {sampled} points outside the facet band -- measures little"
    assert missing == 0, (
        f"{label}: {missing} points inside the CSG solid read up to {worst_missing:+.4f} in the "
        f"SDF field -- the field is missing material the mesh has (SPEC PAR-1)."
    )
    assert extra == 0, (
        f"{label}: {extra} points outside the CSG solid read down to {-worst_extra:+.4f} in the "
        f"SDF field -- the field has material the mesh does not (SPEC PAR-1)."
    )

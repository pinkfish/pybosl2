# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A part that builds on the SDF backend must produce a field that can be evaluated (PAR-1, S-46a).

`tests/test_parts_backend_coverage.py` measures "40 of the 51 parts build on either backend" by
asking whether `.shape` raises. It does not evaluate the field that comes back, and nothing else
did either, because an SDF solid meshes to nothing in this suite -- the belief that only the
analytic box could be read, which T119 measured and found false.

So three parts had been passing backend coverage with a field that raises the moment anything looks
at it. `.shape` returned an `SdfSolid`, `bounds()` answered, and a user with libfive would have got
an exception on render:

| part | on evaluating its field |
|---|---|
| `Rack` | *polygon has no non-degenerate edges* |
| `RingGear` | *polygon decomposition recursed implausibly deep* |
| `TorxMask` | *polygon decomposition recursed implausibly deep* |

Two separate defects in `pybosl2/sdf/paths.py`, both found by this file and both fixed in the same
commit. `_convex_hull_indices` was a convexity filter rather than a hull, and over-pruned one of
`TorxMask`'s pockets from eight points to two, after which the pocket extracted was the whole chain
and the recursion stood still. `Rack`'s recursion was correct and simply deeper than the flat 16
allowed -- a rack's outline peels one tooth per level, so 84 points need about 21 -- and the guard's
message blamed a self-intersecting outline for what was its own arithmetic.

All three now evaluate *and* match their CSG mesh exactly, and this file is the first thing to
compare a part's two backends on anything but a box.

It recorded six parts as building different geometry. **T122 left one, and T126 found what it
was.** `ThreadHelix` was a real defect -- its thread ridge grew inward from the diameter it was
given, which is the only direction in which a thread profile can reach the helix axis -- four were
this file's criterion applied past where it holds, and the last, `RobertsonMask` at 2.008, was a
defect in `cyl` itself: every tapered cylinder on the SDF backend had lost the half that ends at
its narrower rim, so the cone `RobertsonMask` cuts with had its whole lower half collapsed onto the
axis. `DISAGREE` is empty now. See it below, and `tests/field_probe.py` for the premise and its
limit.
"""

from __future__ import annotations

import math
from contextlib import nullcontext
from functools import lru_cache

import numpy as np
import pytest
from part_fixtures import PARTS, arguments

from pybosl2 import use_backend, use_defaults
from pybosl2.sdf._libfive import lv

#: Parts whose `.shape` is a 2-D path rather than a solid, so there is no field to evaluate and no
#: mesh to compare. Named rather than filtered by type, so a part that stops being 2-D is noticed.
TWO_DIMENSIONAL = frozenset({"Rack2d", "SpurGear2d", "TorxMask2d"})


@lru_cache(maxsize=None)
def _sdf_shape(name: str) -> object | None:
    """Build *name* on the SDF backend, or None if it refuses or is not a solid."""
    from pybosl2.exceptions import UnsupportedByBackendError

    cls = PARTS[name]
    args, kwargs = arguments(cls)
    try:
        with use_backend("sdf"):
            shape = cls(*args, **kwargs).shape
    except UnsupportedByBackendError:
        return None
    if getattr(shape, "_sdf_fn", None) is None:
        return None
    return shape


SDF_PARTS = sorted(name for name in PARTS if name not in TWO_DIMENSIONAL)


@pytest.mark.parametrize("name", SDF_PARTS)
def test_a_part_that_builds_on_sdf_has_a_field_that_evaluates(name: str) -> None:
    """Building is not the same as having a field, and only one of the two was being checked."""
    shape = _sdf_shape(name)
    if shape is None:
        pytest.skip(f"{name} does not build a field on the sdf backend")
    tree = shape._sdf_fn(lv.x(), lv.y(), lv.z())  # type: ignore[attr-defined]
    bounds = shape.bounds()  # type: ignore[attr-defined]
    centre = (
        (bounds.min_x + bounds.max_x) / 2,
        (bounds.min_y + bounds.max_y) / 2,
        (bounds.min_z + bounds.max_z) / 2,
    )
    for point in ((0.0, 0.0, 0.0), centre):
        value = float(tree(*point))
        assert value == value, f"{name}: its field reads NaN at {point}"


def test_some_parts_were_actually_examined() -> None:
    """A fixture change that made every part refuse would skip the file green."""
    examined = sum(1 for name in SDF_PARTS if _sdf_shape(name) is not None)
    assert examined >= 30, (
        f"only {examined} parts produced a field to evaluate, where the measurement found 37. "
        f"Every test above would be skipping."
    )


# ----------------------------------------------------------------------------------------
# The two backends compared on the field, not the box.
# ----------------------------------------------------------------------------------------

#: Parts whose CSG mesh departs from the SDF field by more than refining the mesh can explain.
#: **Empty**, and the six rows it used to hold are the interesting part of this file.
#:
#: `ThreadHelix` was a real defect and is fixed (T122): it grew its thread ridge *inward* from the
#: diameter it was given, which is the one direction that lets a thread profile reach the helix
#: axis, where the sweep's own angle is undefined. Its six departing vertices all sat on that
#: axis. The ridge stands on `d` and grows outward now, as BOSL2 has it, and the part agrees with
#: its field exactly at every resolution.
#:
#: The other four -- `KnuckleHinge` 0.19, `KnuckleHingePair` 0.13, `RingHook` 0.12, `SnapSocket`
#: 0.05 -- were never differences at all. They were recorded on the strength of a premise that
#: this file and `tests/field_probe.py` both stated as a general law: *faceting can only inscribe,
#: so a CSG vertex outside the field cannot be a tessellation artifact*. That holds for a
#: primitive's own mesh. **It does not survive a boolean.** A union re-triangulates, and the
#: vertices it creates lie on neither input surface: two helical ridges whose base rings are each
#: at exactly radius 6.00000 union to a mesh whose base ring reaches 5.94867 -- half a polygon
#: step inside, in empty space as far as an exact field is concerned. Every one of the four falls
#: as 1/fn^2 and reaches 0.0003 or less by fn=96, which is what a facet artifact does and what a
#: geometry difference cannot do.
#:
#: `RobertsonMask`, the last row and the only one refinement could not explain, was the real thing
#: twice over: a 2.008 departure that did not move at all with the mesh, and a defect in `cyl`
#: rather than in the part (T126). It cuts a square recess with `prismoid & cyl(diameter1=0)`, and
#: a **tapered** SDF cylinder was building each rim as a corner in the `(radial - r_ref, |axial| -
#: hb)` frame -- the end's own radius read as a vertical half-width. On an untapered cylinder that
#: line *is* the wall, so nothing noticed for as long as the backend has existed; on a taper it cut
#: the bottom half to `radius1` and the top half to `radius2`, and with `diameter1=0` that is the
#: axis. 22 of the part's 27 vertices sat outside the field because most of the cone was missing.
#: Both backends agree exactly now, and the guard that can see it is in `tests/test_sdf_rim.py`:
#: this file samples the *mesh's vertices*, and a cone's vertices are its apex and its two end
#: rings -- the corners where the broken term read zero anyway.
#:
#: So the comparison refines instead of trusting one measurement, and a row here would mean "this
#: departure survives refinement". Figures may fall, never rise; an entry that stops surviving
#: refinement should be deleted, not left as a licence nothing needs.
DISAGREE: dict[str, float] = {}

#: A departure is measured again with this many sides before it is believed. 96 is chosen so the
#: facet bound below is comfortably under every departure that has had to survive it -- 0.0012
#: against `RobertsonMask`'s 2.008 -- while the four facet artifacts clear their own bounds by 13x
#: or more.
REFINED_FN = 96

#: A departure at or below the exact-agreement floor is not examined further.
TOLERANCE = 1e-6


def _facet_bound(reach: float, sides: int) -> float:
    """How far inside a circle of radius *reach* a chord of its *sides*-sided polygon cuts.

    The whole allowance a facet artifact gets, derived from the part's own size rather than
    chosen -- the sagitta of one polygon step. A mesh vertex further outside an exact field than
    this cannot be explained by the mesh being a polygon.
    """
    return (1.0 - math.cos(math.pi / sides)) * reach


#: A mesh of up to this many vertices is sampled in full.
FULL_SAMPLE = 320

#: Above that, this many evenly strided vertices. The cost is a scalar call into the field tree per
#: point, and the deep union chains -- `Truss`, `TrussCorner`, `TrussJoiner`, `HerringboneGear`,
#: `SpurGear` -- dominate it. Measured on an idle machine: **13s with this cap, 75s without**.
#:
#: Every other timing taken while arriving at that figure was wrong, by up to 20x, because a full
#: suite was running in another process each time. A wall-clock number measured against a busy
#: machine is not a measurement, and three of them in a row looked consistent enough to act on.
#:
#: Striding is safe here in a way subsampling usually is not, and the reason is worth stating
#: because it is the thing that would stop being true: **every part agrees exactly**, so nothing
#: being watched is strided at all. The last part that did disagree had 22 departing vertices out
#: of a mesh of 27, well under FULL_SAMPLE. A part that starts disagreeing *and* has thousands of
#: vertices would be sampled thinly; that is the known blind spot, and the honest fix then is to
#: raise the cap for that part, not to widen it everywhere.
STRIDED_SAMPLE = 60


@lru_cache(maxsize=None)
def _escape(name: str, fn: int | None = None) -> tuple[float, int, int, float]:
    """Measure *name*'s CSG mesh against its SDF field, meshed with *fn* sides where it curves.

    Returns (furthest a vertex sits outside the field, how many do, how many were sampled, the
    mesh's largest distance from the Z axis). The last one is what `_facet_bound` scales.
    """
    cls = PARTS[name]
    args, kwargs = arguments(cls)
    with use_backend("csg"), use_defaults(fn=fn) if fn is not None else nullcontext():
        shape = cls(*args, **kwargs).shape
        vnf = shape.vnf() if callable(getattr(shape, "vnf", None)) else shape
    vertices = getattr(vnf, "vertices", None)
    points = np.asarray(vertices if vertices is not None else vnf.points, dtype=float)
    reach = float(np.hypot(points[:, 0], points[:, 1]).max())
    if len(points) > FULL_SAMPLE:
        points = points[:: -(-len(points) // STRIDED_SAMPLE)]
    field = _sdf_shape(name)
    assert field is not None, f"{name} has no field to compare against"
    tree = field._sdf_fn(lv.x(), lv.y(), lv.z())  # type: ignore[attr-defined]
    found = np.asarray([float(tree(float(p[0]), float(p[1]), float(p[2]))) for p in points])
    return float(found.max()), int((found > TOLERANCE).sum()), len(points), reach


COMPARABLE = sorted(name for name in SDF_PARTS if _sdf_shape(name) is not None and name not in {"Worm", "WormGear"})


@pytest.mark.parametrize("name", COMPARABLE)
def test_the_two_backends_build_the_same_part(name: str) -> None:
    """Most parts agree exactly; a part that departs is re-measured with a finer mesh.

    A departure that falls under its own facet bound when the mesh is refined is the mesh being a
    polygon. One that stays is the two backends building different geometry (SPEC PAR-1).
    """
    worst, count, total, _ = _escape(name)
    allowed = DISAGREE.get(name)
    if worst <= TOLERANCE:
        assert allowed is None, (
            f"{name} agrees with its SDF field exactly. Delete its DISAGREE entry -- a list of "
            f"known differences that includes things which agree stops being read."
        )
        return
    refined, rcount, rtotal, reach = _escape(name, REFINED_FN)
    bound = _facet_bound(reach, REFINED_FN)
    if allowed is None:
        assert refined <= bound, (
            f"{name}: {rcount} of its {rtotal} CSG vertices lie outside the SDF field at fn="
            f"{REFINED_FN}, the furthest by {refined:.5f} -- past the {bound:.5f} a polygon of "
            f"that many sides can cut inside a radius of {reach:.3f}. Refining the mesh did not "
            f"remove it, so the two backends build different geometry. If that is known and "
            f"accepted, it belongs in DISAGREE with its figure -- not unrecorded."
        )
    else:
        assert worst <= allowed, (
            f"{name}: now {worst:.4f} outside the SDF field, worse than the {allowed} recorded. "
            f"These figures only fall."
        )


def test_no_recorded_disagreement_is_really_a_facet_artifact() -> None:
    """The question four of the six recorded entries were never asked (T122).

    They were recorded because a vertex sat outside the field and the premise said faceting could
    not put it there. Refining the mesh removed all four. An entry that refinement explains is not
    a disagreement, and leaving it here would licence the next one.

    `DISAGREE` is empty (T126), so this walks nothing -- deliberately a loop rather than a
    parametrisation, which would make the empty case an unexplained skip instead of a kept rule.
    The sibling above enforces the other direction for every part: a departure refinement cannot
    explain and that is not recorded here fails.
    """
    for name in sorted(DISAGREE):
        refined, _, _, reach = _escape(name, REFINED_FN)
        bound = _facet_bound(reach, REFINED_FN)
        assert refined > bound, (
            f"{name} departs by {refined:.5f} at fn={REFINED_FN}, within the {bound:.5f} that a "
            f"polygon of that many sides explains. Delete its DISAGREE entry -- this is a mesh "
            f"artifact, not the two backends disagreeing."
        )

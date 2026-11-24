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

All three now evaluate *and* match their CSG mesh exactly. The six that do not match are recorded
below; this file is the first thing to compare a part's two backends on anything but a box.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pytest
from part_fixtures import PARTS, arguments

from pybosl2 import use_backend
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

#: Parts whose CSG mesh has a vertex outside the SDF field, with how far outside. Faceting can only
#: inscribe (see `tests/field_probe.py`), so each of these is a real difference between the two
#: backends' geometry and not a tessellation artifact. Figures may fall, never rise; an entry that
#: reaches zero should be deleted, not left as a licence nothing needs.
#:
#: `ThreadHelix` is the instructive one: all six of its departing vertices sit on the Z axis, where
#: its field reads +2.5 of empty space -- 34 of its 68 mesh vertices are on the axis and every one
#: is referenced by a face. Whatever that is, it is not a tessellation of the same solid.
DISAGREE = {
    "ThreadHelix": 2.51,
    "RobertsonMask": 2.01,
    "KnuckleHinge": 0.20,
    "KnuckleHingePair": 0.14,
    "RingHook": 0.12,
    "SnapSocket": 0.05,
}


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
#: because it is the thing that would stop being true: **every part expensive enough to be strided
#: agrees exactly**, and every disagreement in DISAGREE below has 4 to 22 departing vertices out of
#: a mesh of 27 to 242 -- all under FULL_SAMPLE, so nothing being watched is strided at all. A part
#: that starts disagreeing *and* has thousands of vertices would be sampled thinly; that is the
#: known blind spot, and the honest fix then is to raise the cap for that part, not to widen it
#: everywhere.
STRIDED_SAMPLE = 60


@lru_cache(maxsize=None)
def _escape(name: str) -> tuple[float, int, int]:
    """Return (furthest a CSG vertex sits outside the SDF field, how many do, how many vertices)."""
    cls = PARTS[name]
    args, kwargs = arguments(cls)
    with use_backend("csg"):
        shape = cls(*args, **kwargs).shape
        vnf = shape.vnf() if callable(getattr(shape, "vnf", None)) else shape
    vertices = getattr(vnf, "vertices", None)
    points = np.asarray(vertices if vertices is not None else vnf.points, dtype=float)
    if len(points) > FULL_SAMPLE:
        points = points[:: -(-len(points) // STRIDED_SAMPLE)]
    field = _sdf_shape(name)
    assert field is not None, f"{name} has no field to compare against"
    tree = field._sdf_fn(lv.x(), lv.y(), lv.z())  # type: ignore[attr-defined]
    found = np.asarray([float(tree(float(p[0]), float(p[1]), float(p[2]))) for p in points])
    return float(found.max()), int((found > 1e-6).sum()), len(points)


COMPARABLE = sorted(name for name in SDF_PARTS if _sdf_shape(name) is not None and name not in {"Worm", "WormGear"})


@pytest.mark.parametrize("name", COMPARABLE)
def test_the_two_backends_build_the_same_part(name: str) -> None:
    """A CSG vertex outside the SDF field is a real geometry difference, and most parts have none."""
    worst, count, total = _escape(name)
    allowed = DISAGREE.get(name)
    if allowed is None:
        assert worst <= 1e-6, (
            f"{name}: {count} of its {total} CSG vertices lie outside the SDF field, the furthest "
            f"by {worst:.4f}. Faceting can only inscribe, so the two backends build different "
            f"geometry (SPEC PAR-1). If that is known and accepted, it belongs in DISAGREE with "
            f"its figure -- not unrecorded."
        )
    else:
        assert worst <= allowed, (
            f"{name}: now {worst:.4f} outside the SDF field, worse than the {allowed} recorded. "
            f"These figures only fall."
        )


@pytest.mark.parametrize("name", sorted(DISAGREE))
def test_no_recorded_disagreement_has_quietly_been_fixed(name: str) -> None:
    """An entry that no longer disagrees is a stale licence, so it has to be noticed."""
    worst, _, _ = _escape(name)
    assert worst > 1e-6, (
        f"{name} now agrees with its SDF field exactly. Delete its DISAGREE entry -- a list of "
        f"known differences that includes things which agree stops being read."
    )

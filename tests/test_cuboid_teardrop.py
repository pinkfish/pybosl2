# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A teardrop-clipped cuboid must not overhang past the angle it was given, on either backend.

SPEC S-2b, PAR-1, G-8. `cuboid(teardrop=)` raised `Bosl2NotImplementedError` on the CSG side and
did not exist on the SDF one, so the two were at parity by both lacking it.

The construction is one observation. A rounded bottom edge overhangs because its surface rotates
from vertical at the wall to horizontal at the floor; clipping it at a maximum lean stops the arc
and drops straight down. Below that height **every horizontal slice is the same slice** -- a
rectangle inset by the rounding and grown back by ``rounding * cos(lean)``, its vertical edges
rounded by the same amount. So each backend builds what it is good at: CSG unions a prism of that
slice, and the SDF holds `z` at the clip plane, which extrudes the slice downward for free.

The instrument is the overhang itself, because that is the whole promise of the option. On the CSG
side that means mesh face normals -- the steepest downward-facing facet that is not the floor. On
the SDF side the field is sampled, since the analytic floor width `w/2 - r + r*cos(lean)` follows
from the same observation the construction does and would otherwise be checking itself.

**The two backends do not produce identical geometry, and the difference is the point.** A rounded
cuboid is a minkowski with a *faceted* sphere, so the CSG surface is a staircase; cutting at the
exact lean leaves the facet straddling the clip plane partly exposed, and measured, `teardrop=60`
came out at **61.88 degrees** -- over the ceiling it was asked to hold. So the CSG side snaps the
lean down to a facet boundary and can be up to one facet stricter than asked. The SDF field is
exact and needs no such thing. Both respect the ceiling, which is what the tests assert; neither
is asserted to match the other's floor width to the micron.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from pybosl2._backend import use_backend
from pybosl2._edges_lang import Anchor
from pybosl2.exceptions import Bosl2NotImplementedError

SIZE = [40.0, 30.0, 20.0]
ROUNDING = 6.0
ANGLES = [20.0, 30.0, 45.0, 60.0, 70.0]


def _requested(teardrop: float | bool) -> float:
    return 45.0 if teardrop is True else float(teardrop)


def _csg_max_lean(teardrop: float | bool) -> float:
    """The steepest downward-facing facet's lean from vertical, excluding the floor."""
    from pybosl2.shapes3d.cuboid import cuboid

    solid = cuboid(SIZE, rounding=ROUNDING, teardrop=teardrop, fn=64)
    verts, faces = solid.shape.mesh()[0], solid.shape.mesh()[1]
    tri = np.asarray(verts, dtype=float)[np.asarray(faces, dtype=int)[:, :3]]
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    keep = lengths > 1e-12
    normals = normals[keep] / lengths[keep, None]
    # 0 degrees here is a normal pointing straight down, i.e. the flat floor; 90 is a vertical
    # wall. The surface's lean from vertical is the complement.
    from_floor = np.degrees(np.arccos(np.clip(-normals[:, 2], -1.0, 1.0)))
    overhanging = from_floor[(from_floor > 1.0) & (from_floor < 90.0)]
    return float(90.0 - overhanging.min()) if len(overhanging) else 0.0


def _sdf_floor_half_width(teardrop: float | bool) -> float:
    """Where the field changes sign along +X, just above the floor."""
    import pybosl2.sdf.shapes3d as sdf

    mesh = sdf.cuboid(SIZE, rounding=ROUNDING, teardrop=teardrop, res=20).mesh()
    z = -SIZE[2] / 2 + 1e-3
    lo, hi = 0.0, SIZE[0]
    for _ in range(60):
        mid = (lo + hi) / 2
        if mesh.sample(mid, 0.0, z) < 0:
            lo = mid
        else:
            hi = mid
    return lo


@pytest.mark.parametrize("teardrop", [*ANGLES, True])
def test_the_csg_cuboid_never_overhangs_past_its_teardrop_angle(teardrop: float | bool) -> None:
    """SPEC S-2b: the angle is a ceiling, and a ceiling broken by one facet is not a ceiling."""
    lean = _csg_max_lean(teardrop)
    assert lean <= _requested(teardrop) + 1e-9, f"teardrop={teardrop} leans {lean:.2f} degrees from vertical"


@pytest.mark.parametrize("teardrop", [*ANGLES, True])
def test_the_csg_clip_is_within_one_facet_of_what_was_asked(teardrop: float | bool) -> None:
    """SPEC S-2b: snapping down must not become over-clipping -- the shape stays close to asked."""
    lean = _csg_max_lean(teardrop)
    assert lean > _requested(teardrop) - 7.0, (
        f"teardrop={teardrop} leans only {lean:.2f}; the bottom is clipped far harder than asked"
    )


@pytest.mark.parametrize("teardrop", [*ANGLES, True])
def test_the_sdf_cuboid_clips_exactly_where_it_is_asked(teardrop: float | bool) -> None:
    """SPEC PAR-1: the field is exact, so the floor lands on the analytic width, not near it."""
    predicted = SIZE[0] / 2 - ROUNDING + ROUNDING * math.cos(math.radians(_requested(teardrop)))
    assert _sdf_floor_half_width(teardrop) == pytest.approx(predicted, abs=0.01)


def test_a_teardrop_widens_the_footprint_without_moving_the_bounds() -> None:
    """SPEC S-2b: the clip fills material *inside* the box, so only the floor changes.

    Bounds are the obvious thing to assert and would have passed for a no-op, which is why the
    tests above measure the overhang instead. This one pins the other half: nothing grew.
    """
    from pybosl2.shapes3d.cuboid import cuboid

    plain = cuboid(SIZE, rounding=ROUNDING, fn=64)
    clipped = cuboid(SIZE, rounding=ROUNDING, teardrop=True, fn=64)
    assert [float(v) for v in clipped.bounds().size] == pytest.approx([float(v) for v in plain.bounds().size], abs=0.05)

    def floor_width(solid: object) -> float:
        verts = np.asarray(solid.shape.mesh()[0], dtype=float)  # type: ignore[attr-defined]
        return float(verts[verts[:, 2] < verts[:, 2].min() + 0.05][:, 0].max())

    assert floor_width(clipped) > floor_width(plain) + 1.0, "the clip added no material at the floor"


@pytest.mark.parametrize("backend", ["csg", "sdf"])
def test_both_backends_build_a_teardrop_through_the_facade(backend: str) -> None:
    """SPEC PAR-1: they were at parity by both lacking it; they must be at parity by both having it."""
    from pybosl2 import cube, cuboid

    expected = "CsgSolid" if backend == "csg" else "SdfSolid"
    with use_backend(backend):
        pairs = [
            ("cuboid", cuboid(SIZE, rounding=ROUNDING, teardrop=True), cuboid(SIZE, rounding=ROUNDING)),
            ("cube", cube(SIZE, rounding=ROUNDING, teardrop=30), cube(SIZE, rounding=ROUNDING)),
        ]
    for name, built, plain in pairs:
        assert type(built).__name__ == expected, f"{name}: {type(built).__name__} under {backend}"
        # The clip fills material inside the box, so the bounds must not grow past nominal. They
        # need not equal the plain shape's either: CSG rounds by minkowski with an *inscribed*
        # faceted sphere, so the plain floor sits a fraction of a facet above -h/2, while the fill
        # is built at -h/2 exactly. The teardrop is therefore between the two, never outside them.
        for axis, (got, was, nominal) in enumerate(zip(built.bounds().size, plain.bounds().size, SIZE, strict=True)):
            assert float(was) - 1e-6 <= float(got) <= float(nominal) + 1e-6, (
                f"{name} axis {axis}: {float(got)} is outside [{float(was)}, {float(nominal)}]"
            )


@pytest.mark.parametrize("backend", ["csg", "sdf"])
@pytest.mark.parametrize(
    ("kwargs", "because"),
    [
        ({"chamfer": 3.0, "teardrop": True}, "chamfer"),
        ({"rounding": ROUNDING, "teardrop": True, "edges": Anchor.Z}, "edge set"),
    ],
)
def test_a_combination_that_is_not_built_refuses_by_name(backend: str, kwargs: dict[str, object], because: str) -> None:
    """SPEC G-8: the combinations outside the construction refuse, rather than clipping wrongly.

    A teardrop on a restricted edge set is the dangerous one: the bottom edges need not be rounded
    at all, so the slice below the clip is no longer the cuboid's own cross-section and the fill
    would bulge outside the solid. It would still be a closed, plausible shape.
    """
    from pybosl2 import cuboid

    with use_backend(backend), pytest.raises(Bosl2NotImplementedError) as excinfo:
        cuboid(SIZE, **kwargs)  # type: ignore[arg-type]
    assert because in str(excinfo.value), f"the refusal does not say why: {excinfo.value}"


@pytest.mark.parametrize("backend", ["csg", "sdf"])
def test_a_teardrop_without_a_rounding_changes_nothing(backend: str) -> None:
    """SPEC S-2b: a sharp-edged box has vertical walls and a flat floor, so there is no overhang."""
    from pybosl2 import cuboid

    with use_backend(backend):
        plain = cuboid(SIZE)
        clipped = cuboid(SIZE, teardrop=True)
    assert [float(v) for v in clipped.bounds().size] == pytest.approx([float(v) for v in plain.bounds().size])

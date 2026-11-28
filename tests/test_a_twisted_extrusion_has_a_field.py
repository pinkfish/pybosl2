# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""`linear_extrude(twist=)` is exact on a distance field (SPEC PAR-1, PAR-4, B-9).

T14 triaged every `linear_extrude` option the SDF backend could not take and recorded this one as
settled:

> a *helical* gear still refuses, on `linear_extrude(twist=)`, which a constant-cross-section
> prism genuinely cannot express

The sentence is true and it is about the wrong thing. `polygon_prism` does extrude a constant
cross-section, and the field does not have to: a twisted prism contains ``(x, y, z)`` exactly when
the outline contains the point turned **back** by the twist accumulated at that height. So reading
the outline's own 2-D field at ``(x cos t + y sin t, -x sin t + y cos t)``, with ``t`` linear in
``z``, *is* the solid -- no slicing, no approximation, and no more expensive than the untwisted
prism by more than a sine and a cosine.

What the refusal was really describing was the backend's one extrusion function. Two others in the
module already read a station the same way -- `spiral_sweep` recovers its station from `atan2` and
`tapered_polygon_prism` recovers its station from `z` and undoes a uniform scale -- so "recover the
station, undo its transform" was the established device and a twist is its easiest case.

Measured below against the meshed extruder at its own vertices. The figure is **exactly 0.0**, not
a tolerance: the native extruder slices the twist and every vertex it emits lies on the outline at
that slice's height, which is where the field puts the surface. The opposite sign reads 1.01 to
1.66 outside, so the comparison discriminates.

T142. This is what closed `Worm`, whose refusal said a helical thread is "a non-convex mesh with no
distance-field form" -- a worm being a twisted prism of one fixed cross-section.
"""

from __future__ import annotations

import math

import pytest

from pybosl2 import use_backend
from pybosl2.exceptions import UnsupportedByBackendError
from pybosl2.path2d import Path2D
from tests.field_probe import csg_vertices, distances, worst_escape

SQUARE = Path2D([[-4.0, -4.0], [4.0, -4.0], [4.0, 4.0], [-4.0, 4.0]])

#: A ten-point star: concave, so it also checks that the twist composes with `_polygon_sdf_xy`'s
#: convex-deficiency decomposition rather than only with a convex outline's half-planes.
STAR = Path2D(
    [
        [r * math.cos(2 * math.pi * i / 10), r * math.sin(2 * math.pi * i / 10)]
        for i, r in ((i, 6.0 if i % 2 == 0 else 3.0) for i in range(10))
    ]
)

#: Long and thin, which is the shape whose *box* the twist is hardest on: at a quarter turn it
#: sweeps far wider than it ever is tall.
BLADE = Path2D([[-10.0, -1.0], [10.0, -1.0], [10.0, 1.0], [-10.0, 1.0]])

CASES = {
    "square, quarter turn": (SQUARE, 20.0, 90.0, False),
    "square, quarter turn the other way": (SQUARE, 20.0, -90.0, False),
    "square, a third of a turn": (SQUARE, 20.0, 120.0, False),
    "square, a full turn": (SQUARE, 30.0, 360.0, False),
    "square, two and a half turns": (SQUARE, 30.0, 900.0, False),
    "star, half a turn, centred": (STAR, 24.0, 180.0, True),
    "star, no turn at all": (STAR, 24.0, 0.0, False),
    "blade, quarter turn": (BLADE, 20.0, 90.0, False),
}

#: Not a faceting tolerance. A vertex of the meshed extrusion lies on the outline at its own
#: slice's height, which is exactly where the field puts the surface, so this is the arithmetic of
#: evaluating the tree and nothing else.
EXACT = 1e-6


@pytest.mark.parametrize("label", sorted(CASES))
def test_the_meshed_twist_lies_on_the_field(label: str) -> None:
    """The same twisted prism, built both ways, must be the same solid."""
    profile, height, twist, center = CASES[label]
    outside, inside, where = worst_escape(
        lambda: profile.linear_extrude(height=height, twist=twist, center=center),
        lambda: profile.linear_extrude(height=height, twist=twist, center=center),
    )
    assert outside <= EXACT, (
        f"{label}: the meshed extrusion has a vertex at {where} lying {outside:.4f} outside the "
        f"field. Faceting can only inscribe, so these are different solids (SPEC PAR-5)."
    )
    assert abs(inside) <= EXACT, (
        f"{label}: the meshed extrusion sits {inside:.4f} inside the field. Both read the same "
        f"outline at the same heights, so this has been exactly 0; a departure means one of them "
        f"has started approximating."
    )


@pytest.mark.parametrize("label", sorted(CASES))
def test_each_case_has_real_vertices_to_compare(label: str) -> None:
    """A case whose mesh came back empty would pass the test above by having nothing to check."""
    profile, height, twist, center = CASES[label]
    points = csg_vertices(lambda: profile.linear_extrude(height=height, twist=twist, center=center))
    assert len(points) >= 2 * len(profile), (
        f"{label} produced {len(points)} vertices for a {len(profile)}-point outline, which "
        f"is fewer than its two end faces -- the comparison above is not measuring the extrusion"
    )


def test_the_twist_turns_the_way_openscad_turns_it() -> None:
    """The sign, which is the one thing about this that could be silently wrong.

    A positive `twist` turns the top face *clockwise* seen from above -- OpenSCAD's convention, and
    so BOSL2's. Getting it backwards builds a mirror-image helix that has the same bounding box and
    the same volume, so only a comparison against the meshed extruder can see it. It reads 1.66
    outside here, against 0.0 for the right sign.
    """
    points = csg_vertices(lambda: SQUARE.linear_extrude(height=20.0, twist=90.0))
    right = distances(lambda: SQUARE.linear_extrude(height=20.0, twist=90.0), points)
    wrong = distances(lambda: SQUARE.linear_extrude(height=20.0, twist=-90.0), points)
    assert float(right.max()) <= EXACT, f"the matching sign now reads {right.max():.4f} outside"
    assert float(wrong.max()) > 1.0, (
        f"a twist of the opposite sign reads only {wrong.max():.4f} outside the field, so this "
        f"comparison cannot tell a mirrored helix from a right one and the agreements above "
        f"prove less than they appear to"
    )


def test_the_box_is_the_swept_outline_not_its_circumcircle() -> None:
    """The mesh domain, which `frep()`'s octree clips anything outside of.

    A twisted prism's box is the outline swept through the angles the twist actually visits, not
    the disc of its circumcircle. The blade is 20 x 2 with a circumradius of 10.05, so the disc
    claims 20.10 x 20.10 whatever the twist -- while a 30-degree turn of it reaches 20.19 x 11.82.

    A *quarter* turn is the case to be careful with, and the first version of this test used it:
    there the two agree, because the blade's own tip has by then swept through 90 degrees and the
    envelope really is square. The cheap answer looks right until a small twist is measured.
    """
    with use_backend("sdf"):
        slight = [float(v) for v in BLADE.linear_extrude(height=20.0, twist=30.0).bounds().size]
        quarter = [float(v) for v in BLADE.linear_extrude(height=20.0, twist=90.0).bounds().size]
        full = [float(v) for v in BLADE.linear_extrude(height=20.0, twist=360.0).bounds().size]
    assert slight[1] < 0.75 * slight[0], (
        f"a 30-degree turn of a 20 x 2 blade claims {slight[0]:.2f} x {slight[1]:.2f}; the swept "
        f"outline is far narrower than it is long, so this box has fallen back on the circumcircle"
    )
    for label, box in (("a quarter turn", quarter), ("a full turn", full)):
        assert box[0] == pytest.approx(box[1], rel=0.02), (
            f"{label} sweeps the tip through 90 degrees or more, so its box must be square; got "
            f"{box[0]:.2f} x {box[1]:.2f}"
        )
    for box in (slight, quarter, full):
        assert box[0] >= 20.0, f"the box is {box[0]:.2f} across a blade 20.00 long -- it clips the solid"


def test_a_full_turn_does_not_cost_more_than_a_turn_to_bound() -> None:
    """A worm turns 917 degrees, and the envelope stops growing after the first 360.

    Sampled at a quarter of a degree, 917 degrees is 3,669 angles to describe a circle the first
    1,440 of them have already closed. Capping the sampling is what keeps a long coil's box cheap.
    """
    with use_backend("sdf"):
        one = [float(v) for v in SQUARE.linear_extrude(height=30.0, twist=360.0).bounds().size]
        many = [float(v) for v in SQUARE.linear_extrude(height=30.0, twist=3600.0).bounds().size]
    assert one[:2] == pytest.approx(many[:2], rel=1e-9), (
        f"ten turns claim a different envelope ({many[:2]}) from one ({one[:2]}), so the sampling "
        f"cap has changed the answer rather than only the cost"
    )


def test_a_tapered_extrusion_still_refuses_by_name() -> None:
    """`scale=` is a different surface, not a render hint, and keeps its refusal (SPEC E-5, B-9).

    This matters because `twist` and `scale` were refused by one loop over three names. Taking
    `twist` out of it must not take `scale` with it -- a tapered prism's station transform is a
    scale, which a field *can* undo, but `linear_extrude(scale=)` can taper the two axes
    differently, and that is not a uniform scale at all.
    """
    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError) as excinfo:
        SQUARE.linear_extrude(height=20.0, scale=0.5)
    assert "linear_extrude(scale=)" in str(excinfo.value), (
        f"a tapered extrusion refused without naming the parameter: {excinfo.value}"
    )


def test_slices_is_accepted_and_ignored() -> None:
    """`slices=` is how finely the native extruder steps the twist -- tessellation, so B-9 applies.

    It was refused along with `twist` and `scale` by the same loop, which is the `convexity`
    mistake T14 found on this very constructor: a plain spur gear was being kept off the backend
    over a rendering flag.
    """
    with use_backend("sdf"):
        plain = SQUARE.linear_extrude(height=20.0, twist=90.0)
        sliced = SQUARE.linear_extrude(height=20.0, twist=90.0, slices=64)
    assert [float(v) for v in plain.bounds().size] == pytest.approx([float(v) for v in sliced.bounds().size]), (
        "slices= changed the field, which it must not: it names how the *mesh* steps the twist and "
        "the field has no steps"
    )


def test_a_twisted_rim_treatment_refuses_rather_than_lying() -> None:
    """A roundover is offset along the wall's own normal, and a twisted wall's is not the outline's.

    The SDF prism's rim treatments are its own extra, so nothing upstream asks for this combination
    -- which is exactly why it would have been easy to accept and quietly get wrong.
    """
    from pybosl2.sdf import SdfBackend

    with pytest.raises(UnsupportedByBackendError) as excinfo:
        SdfBackend().linear_extrude([SQUARE], 20.0, {"twist": 90.0, "rounding_top": 1.0})
    assert "rounding_top" in str(excinfo.value), (
        f"a twisted prism with a rounded rim refused without naming the rim: {excinfo.value}"
    )

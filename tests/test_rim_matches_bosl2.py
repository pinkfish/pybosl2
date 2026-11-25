# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The rim geometry is BOSL2's, measured against BOSL2 (SPEC B2-1, PAR-4).

`tests/test_sdf_rim.py` asks whether the field is zero on the profile the CSG backend revolves,
and that is the sharpest *cross-backend* statement available: the profile is not an approximation
of the CSG solid, it is the CSG solid. What it cannot ask is whether the profile is right.

It was not. T42 measured the fillet centre on an 8-to-4 cone, found `(6, -8)` -- 1.94029 from the
wall instead of 2 -- and wrote down that BOSL2's fillet "merely *meets* the wall"; the SDF backend
was then built to agree, and T126 and T127 refined the agreement. BOSL2 fits the fillet with
`arc(r=, corner=[inner, corner, far end])`, which is tangent to **both** legs, so its centre is
the corner's incentre at `(5.56039, -8)`. Two backends agreeing is not evidence about BOSL2, and
nothing in this repository had ever compared a rim against the `.scad` it was ported from.

So `tests/bosl2_cyl_path.py` transcribes `_cyl_path()` and this file is the comparison. The three
defects it found, all of them in both backends:

======================================  =========================================================
``rounding`` on a taper                  the centre was on the vertical line through the nominal
                                         radius, not the incentre -- 0.62mm out on 8-to-4 with a
                                         2mm rounding, 1.32mm on 10-to-2 with 3mm
``chamfer`` on a taper                   the cut's far end was on that same vertical line, where
                                         BOSL2 runs it from the corner *along the wall* -- 0.39mm
                                         at the default angle, 2.12mm at 60 degrees
``from_end=`` anywhere                   read as the cut's own hypotenuse; BOSL2 measures it
                                         along the side face -- 0.59mm out at the default 45
                                         degrees on a **plain cylinder**, 1.73mm at 30
======================================  =========================================================

Every straight-walled case at `from_end=False` was already exact, which is why none of this
surfaced: `cyl_profile`'s own tests, T42's five treated-taper cases, T126's twelve profiles and
T128's eighteen solids all measured the two backends against each other.
"""

from __future__ import annotations

import math

import pytest

from pybosl2.shapes3d.cylinder import cyl_profile
from tests.bosl2_cyl_path import cyl_path

#: Enough facets that the chord sagitta is far below the tolerance -- the vertices this compares
#: are the profile's corners and arc endpoints, which are exact at any count, but the arc's
#: *endpoints* are only where `arc_points` lands them.
FACETS = 4096

#: Both are closed form, so the only slack is floating-point arithmetic.
EXACT = 1e-9

#: BOSL2's spelling of each option this library takes, for the oracle call.
BOSL2_NAME = {
    "rounding1": "rounding1",
    "rounding2": "rounding2",
    "chamfer1": "chamfer1",
    "chamfer2": "chamfer2",
    "chamfer_angle1": "chamfang1",
    "chamfer_angle2": "chamfang2",
    "from_end1": "from_end1",
    "from_end2": "from_end2",
}

#: Every taper direction, including none -- the one the old geometry got right.
TAPERS = [(8.0, 8.0), (8.0, 4.0), (4.0, 8.0), (8.0, 6.0), (10.0, 3.0), (3.0, 10.0), (12.0, 9.0)]

#: One rim statement per row. The figures in this module's docstring come from these.
RIMS: list[tuple[str, dict[str, float | bool]]] = [
    ("rounding1", {"rounding1": 2.0}),
    ("rounding2", {"rounding2": 2.0}),
    ("rounding at both ends", {"rounding1": 2.0, "rounding2": 2.0}),
    ("a different rounding at each end", {"rounding1": 3.0, "rounding2": 1.5}),
    ("chamfer1", {"chamfer1": 2.0}),
    ("chamfer2", {"chamfer2": 2.0}),
    ("chamfer at both ends", {"chamfer1": 2.0, "chamfer2": 2.0}),
    ("a shallow chamfer angle", {"chamfer1": 2.0, "chamfer_angle1": 30.0}),
    ("a steep chamfer angle", {"chamfer2": 2.0, "chamfer_angle2": 60.0}),
    ("chamfer1 measured from the end", {"chamfer1": 2.0, "from_end1": True}),
    ("chamfer2 measured from the end", {"chamfer2": 2.0, "from_end2": True}),
    ("from the end at a shallow angle", {"chamfer1": 2.0, "chamfer_angle1": 30.0, "from_end1": True}),
    ("from the end at a steep angle", {"chamfer2": 2.0, "chamfer_angle2": 65.0, "from_end2": True}),
]


def _oracle(radius1: float, radius2: float, length: float, rim: dict[str, float | bool]) -> dict[str, object]:
    """Run the transcription on the same call.

    Args:
        radius1: Radius at the bottom end.
        radius2: Radius at the top end.
        length: The cylinder length.
        rim: The rim options, in this library's spelling.

    Returns:
        What :func:`tests.bosl2_cyl_path.cyl_path` returns.

    """
    return cyl_path(radius1, radius2, length, **{BOSL2_NAME[k]: v for k, v in rim.items()})  # type: ignore[arg-type]


def test_the_oracle_is_not_this_library_in_disguise() -> None:
    """The comparison is worthless if the transcription forwards to the code under test.

    It states the one number the whole task turns on from the other side: on an 8-to-4 cone of
    height 20 with a 2mm rounding, BOSL2's fillet centre is `(5.56039, -8)`. Written out rather
    than derived, so changing either side's formula cannot quietly move both.
    """
    bottom = _oracle(8.0, 4.0, 20.0, {"rounding1": 2.0})["bottom"]
    assert isinstance(bottom, dict)
    centre = bottom["centre"]
    assert isinstance(centre, tuple)
    assert centre[0] == pytest.approx(5.560392194562885, abs=EXACT), f"the oracle's centre moved: {centre}"
    assert centre[1] == pytest.approx(-8.0, abs=EXACT)

    # ... and it is the centre of a fillet that *rolls* in the corner, which the point this
    # library used -- `(radius - amount, -hb + amount)`, so `(6, -8)` here -- is not. The gap is
    # the whole defect, measured at this one configuration rather than described.
    def from_wall(radial: float, axial: float) -> float:
        return abs(((4.0 - 8.0) * (axial + 10.0) - 20.0 * (radial - 8.0)) / math.hypot(4.0 - 8.0, 20.0))

    assert from_wall(*centre) == pytest.approx(2.0, abs=EXACT), "BOSL2's fillet is tangent to the wall"
    assert from_wall(6.0, -8.0) == pytest.approx(1.568929, abs=1e-6), (
        "the superseded centre sat 1.568929 from the wall, so its fillet cut into the cone"
    )
    assert centre[0] == pytest.approx(6.0 - 0.439608, abs=1e-6), "the two centres are 0.439608 apart"


@pytest.mark.parametrize(("radius1", "radius2"), TAPERS)
@pytest.mark.parametrize(("label", "rim"), RIMS, ids=[row[0] for row in RIMS])
def test_the_profile_is_the_path_bosl2_builds(
    label: str, rim: dict[str, float | bool], radius1: float, radius2: float
) -> None:
    """Every rim this library can state lands on BOSL2's own two points, at every taper.

    The two compared are the ends of each treatment: the one on the end face and the one on the
    wall. They pin the whole treatment, because a chamfer *is* those two points and an arc is
    determined by its endpoints and its radius -- which the next test checks separately.
    """
    length = 20.0
    mine = cyl_profile(radius1, radius2, length, fn=FACETS, **rim)  # type: ignore[arg-type]
    theirs = _oracle(radius1, radius2, length, rim)
    for end, inner_index in (("bottom", 1), ("top", -2)):
        side = theirs[end]
        assert isinstance(side, dict)
        points = side["points"]
        assert isinstance(points, list)
        want = points[0] if end == "bottom" else points[-1]
        got = mine[inner_index]
        gap = math.dist(got, want)
        assert gap < EXACT, (
            f"{label} on a {radius1:g}-to-{radius2:g} taper: this library puts the {end} rim's "
            f"end-face point at {tuple(round(v, 6) for v in got)} and BOSL2 puts it at "
            f"{tuple(round(v, 6) for v in want)}, {gap:.6f} away (SPEC B2-1)."
        )


@pytest.mark.parametrize(("radius1", "radius2"), TAPERS)
@pytest.mark.parametrize("amount", [0.5, 1.0, 2.0, 3.0])
@pytest.mark.parametrize("top", [False, True])
def test_a_fillet_is_tangent_to_the_wall_it_rolls_against(
    radius1: float, radius2: float, amount: float, top: bool
) -> None:
    """The property the incentre has and the nominal centre does not, stated directly.

    `test_the_profile_is_the_path_bosl2_builds` compares against the transcription; this compares
    against the definition, so a shared misreading of `arc(r=, corner=)` could not satisfy both.
    A fillet of radius *a* rolling in the corner touches the end face and the wall, so its centre
    is *a* from each -- and the end-face half was never in doubt, which is exactly why the wall
    half went unchecked.
    """
    from pybosl2._helpers import rim_fillet_centre

    length = 20.0
    radial, axial = rim_fillet_centre(radius1, radius2, length, amount, top=top)
    face = length / 2 - abs(axial)
    assert face == pytest.approx(amount, abs=EXACT), f"the centre is {face} from the end face, not {amount}"
    slant = math.hypot(radius2 - radius1, length)
    wall = abs(((radius2 - radius1) * (axial + length / 2) - length * (radial - radius1)) / slant)
    assert wall == pytest.approx(amount, abs=EXACT), (
        f"a {amount}mm fillet on a {radius1:g}-to-{radius2:g} taper is centred {wall:.6f} from the "
        f"wall, so it is not tangent to it (SPEC B2-1)."
    )


@pytest.mark.parametrize(("radius1", "radius2"), TAPERS)
@pytest.mark.parametrize(("label", "rim"), RIMS, ids=[row[0] for row in RIMS])
def test_a_chamfers_far_end_is_on_the_wall(
    label: str, rim: dict[str, float | bool], radius1: float, radius2: float
) -> None:
    """A chamfer cuts the corner off the cone, so its far end lies on the cone's own wall.

    This is the statement `_wall_line_sdf` denied for two tasks. It carried two per-end insets so
    that the wall passed through the points a treated rim had *vacated*, on the reading -- written
    into its docstring -- that "a chamfered cone's wall is not the line through its two nominal
    corners". It is that line, to the last digit, and this says so without reference to BOSL2's
    source or to either backend.
    """
    if not any(k.startswith("chamfer") and not k.startswith("chamfer_angle") for k in rim):
        pytest.skip("this row states a rounding; the fillet's tangency is the test above")
    length = 20.0
    profile = cyl_profile(radius1, radius2, length, fn=FACETS, **rim)  # type: ignore[arg-type]
    slant = math.hypot(radius2 - radius1, length)
    ends = [("chamfer1", 2), ("chamfer2", -3)]
    checked = 0
    for name, index in ends:
        if not rim.get(name):
            continue
        radial, axial = profile[index]
        off = abs(((radius2 - radius1) * (axial + length / 2) - length * (radial - radius1)) / slant)
        assert off < EXACT, (
            f"{label} on a {radius1:g}-to-{radius2:g} taper: {name}'s far end is {off:.6f} off the "
            f"cone wall, so the chamfer is cutting a different cone (SPEC B2-1)."
        )
        checked += 1
    assert checked, f"{label}: no chamfer end was reached -- this asserted nothing"

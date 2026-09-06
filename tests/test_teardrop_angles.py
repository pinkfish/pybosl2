# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A teardrop angle is a promise about the steepest overhang, so measure the overhang.

SPEC S-2b, G-8. `teardrop=` exists for one reason: an FDM printer cannot bridge a surface that
leans too far from vertical, so the option caps how far the rim may lean. That makes the angle
checkable against the geometry, and nothing was checking it.

`effective_clip` returned `min(clip_angle, 90 - angle)` under a docstring that said, in the same
sentence, that a teardrop "may not overhang by more than its angle". Both cannot hold. The arc is
swept `clip` degrees from its widest point, and that sweep *is* the overhang from vertical -- so
`teardrop=30` produced a **60 degree** overhang, less printable than the 45 the bare flag gives,
which is backwards for a printability option. `teardrop2d()`, whose walls stand at exactly `angle`
from vertical, had the sense right all along; the two spellings disagreed with each other.

Three things kept it invisible:

* **45 is the fixed point of `90 - angle`.** `teardrop=True` means 45 and is the form almost every
  caller uses, so the inversion is undetectable through the flag.
* **The guard checked the arithmetic against itself.** A test asserted `effective_clip(90, 30) ==
  60`, which restates the implementation rather than measuring anything.
* **The geometric test never measured an angle.** `test_a_teardrop_rounding_clips_the_overhang`
  asserted the bounds were unchanged and the program text differed -- true of any edit at all.

So the assertions here are on the profile: walk its segments, take the steepest lean from vertical
on the underside, and require it not to exceed what was asked for. Discretisation makes the
measured angle land a degree or two under the limit, which is the right direction for a
printability guarantee and is asserted as such.
"""

from __future__ import annotations

import numpy as np
import pytest

from pybosl2._helpers import effective_clip
from pybosl2.shapes3d.cylinder import cyl_profile
from pybosl2.shapes3d.sphere import _teardrop2d_path

ANGLES = [20.0, 30.0, 45.0, 60.0, 70.0]


def _steepest_lean(points: np.ndarray, keep: np.ndarray) -> float:
    """The steepest segment lean from vertical, in degrees, over the segments *keep* selects."""
    worst = 0.0
    for (u, v), take in zip(zip(points[:-1], points[1:], strict=True), keep, strict=True):
        if not take:
            continue
        worst = max(worst, float(np.degrees(np.arctan2(abs(v[0] - u[0]), abs(v[1] - u[1])))))
    return worst


def _cyl_underside_lean(teardrop: float | bool) -> float:
    """The steepest lean of a cylinder's bottom rounding, excluding the flat bottom face itself."""
    profile = np.asarray(
        cyl_profile(
            radius1=10,
            radius2=10,
            length=20,
            rounding1=4,
            rounding2=0,
            chamfer1=0,
            chamfer2=0,
            fn=64,
            fa=12,
            fs=2,
            teardrop=teardrop,
        ),
        dtype=float,
    )
    lower = profile[:, 1] < -6.0
    on_the_floor = np.isclose(profile[:, 1], -10.0)
    keep = (lower[:-1] | lower[1:]) & ~(on_the_floor[:-1] & on_the_floor[1:])
    return _steepest_lean(profile, keep)


def _teardrop2d_wall_lean(angle: float) -> float:
    """The steepest lean of a teardrop2d's capping walls, excluding the circular part below."""
    profile = np.asarray(_teardrop2d_path(10.0, angle, None, False, False, 64), dtype=float)
    upper = profile[:, 1] >= 6.0
    return _steepest_lean(profile, upper[:-1] | upper[1:])


@pytest.mark.parametrize("angle", ANGLES)
def test_a_cylinder_rim_never_overhangs_more_than_its_teardrop_angle(angle: float) -> None:
    """SPEC S-2b: the angle is a ceiling on the lean, and a ceiling is what must be measured."""
    lean = _cyl_underside_lean(angle)
    assert lean <= angle + 1e-6, f"teardrop={angle} leans {lean:.2f} degrees from vertical"
    assert lean > angle - 3.0, f"teardrop={angle} leans only {lean:.2f}; the rim is over-clipped"


@pytest.mark.parametrize("angle", ANGLES)
def test_the_two_teardrop_spellings_agree_on_what_the_angle_means(angle: float) -> None:
    """SPEC S-2b: `cyl(teardrop=a)` and `teardrop2d(angle=a)` are one convention, or neither is.

    This is the assertion that fails on the inversion: the two leans were `90 - a` and `a`, which
    coincide only at 45 -- and 45 is exactly the value the boolean flag supplies.
    """
    assert _cyl_underside_lean(angle) == pytest.approx(_teardrop2d_wall_lean(angle), abs=3.0)


def test_the_boolean_flag_is_forty_five_degrees_of_actual_lean() -> None:
    """SPEC S-2b: `teardrop=True` is 45, measured on the rim rather than read off the formula."""
    assert _cyl_underside_lean(True) == pytest.approx(45.0, abs=3.0)
    assert _cyl_underside_lean(True) == pytest.approx(_cyl_underside_lean(45.0))
    assert _cyl_underside_lean(True) <= 45.0 + 1e-6


def test_a_smaller_teardrop_angle_is_more_printable_not_less() -> None:
    """SPEC S-2b: the option's whole purpose orders the outputs, and the inversion reversed them.

    Under `90 - angle` this sequence ran the other way, which is the plainest statement of the
    defect: asking for a gentler overhang gave a steeper one.
    """
    leans = [_cyl_underside_lean(a) for a in ANGLES]
    assert leans == sorted(leans), f"a rising teardrop angle does not raise the lean: {leans}"


def test_no_teardrop_leaves_the_rim_free_to_overhang() -> None:
    """SPEC S-2b: `teardrop=False` is not a teardrop, so the rounding runs to horizontal."""
    assert _cyl_underside_lean(False) > 80.0


def test_the_clip_angle_and_the_teardrop_are_the_same_quantity() -> None:
    """SPEC S-2b: they are both a maximum lean, so the tighter wins and neither is converted."""
    assert effective_clip(90.0, 30) == pytest.approx(30.0)
    assert effective_clip(90.0, True) == pytest.approx(45.0)
    assert effective_clip(20.0, 60) == pytest.approx(20.0), "the tighter of the two wins"
    assert effective_clip(60.0, 20) == pytest.approx(20.0), "and it wins from either side"
    assert effective_clip(90.0, False) == pytest.approx(90.0)


def test_one_definition_of_the_rule_serves_both_backends() -> None:
    """SPEC PAR-1: T45 claimed this and left a second copy of the formula in the CSG rim.

    A duplicated constant is a divergence waiting to happen, and this one waited: correcting
    `effective_clip` moved the SDF rim and left the CSG rim exactly where it was.
    """
    import pybosl2._helpers as helpers
    import pybosl2.sdf.shapes3d as sdf

    assert sdf.effective_clip is helpers.effective_clip
    source = (helpers.__file__, sdf.__file__)
    assert source[0] != source[1]

    import inspect

    body = inspect.getsource(cyl_profile)
    for spelling in ("90.0 - ", "90 - "):
        assert spelling not in body, (
            f"the CSG rim spells {spelling!r} again -- it has its own copy of the teardrop "
            f"formula, and must call effective_clip instead"
        )

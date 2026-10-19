# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""A gear is profile-shifted exactly where it would undercut, and nowhere else (SPEC S-2b).

Below a certain tooth count an involute gear's flank is cut away by the mating rack — undercut —
and the remedy is to shift the profile outward. The threshold is not a constant: it is
`2 / sin^2(pressure_angle)`, so a 14.5-degree gear needs shifting up to 32 teeth and a 25-degree one
only up to 12.

`pybosl2` gets this right, and nothing checked it. `test_low_tooth_gear_has_undercut_shift` asserts
`auto_profile_shift(8) > 0.4` — one tooth count, a loose bound, the default pressure angle — which
would also pass if the threshold were hardcoded at 17, or if every gear were shifted, or if the
shift ignored the pressure angle entirely.

Measured, the outer-to-pitch diameter ratio departs from the unshifted `1 + 2/teeth` by:

======  ========
teeth   excess
======  ========
8       0.1125
12      0.0497
16      0.0080
17      0.0007
18      **0.0000**
40      **0.0000**
======  ========

Exactly zero from 18 up at 20 degrees, where `2/sin^2(20) = 17.1`; and the first unshifted count
moves to 32 at 14.5 degrees (`31.9`) and to 12 at 25 degrees (`11.2`). This file asserts that
correspondence rather than the numbers themselves, so it keeps meaning if the facet count or the
addendum convention changes.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from pybosl2 import use_defaults
from pybosl2.parts.gears import SpurGear2d

FACETS = 32
CIRC_PITCH = 5.0

#: Pressure angles with their textbook undercut limits. Chosen to straddle the default: if the
#: threshold were hardcoded at the 20-degree value, the other two would fail.
PRESSURE_ANGLES = (14.5, 20.0, 25.0)


def _undercut_limit(pressure_angle: float) -> int:
    """The smallest tooth count that needs no shift: `ceil(2 / sin^2(pressure_angle))`."""
    return math.ceil(2.0 / math.sin(math.radians(pressure_angle)) ** 2)


def _shift_excess(teeth: int, pressure_angle: float) -> float:
    """How far the outer diameter exceeds an unshifted gear's, in pitch diameters.

    Zero for an unshifted gear, because its outer diameter is the pitch diameter plus one module of
    addendum each side -- that is `1 + 2/teeth` of the pitch diameter, whatever the module.
    """
    with use_defaults(fn=FACETS):
        outline = SpurGear2d(circ_pitch=CIRC_PITCH, teeth=teeth, pressure_angle=pressure_angle).shape
    points = np.asarray([[float(x), float(y)] for x, y in outline], dtype=float)
    pitch_diameter = CIRC_PITCH * teeth / math.pi
    outer_diameter = 2.0 * float(np.linalg.norm(points, axis=1).max())
    return outer_diameter / pitch_diameter - (1.0 + 2.0 / teeth)


@pytest.mark.parametrize("pressure_angle", PRESSURE_ANGLES)
def test_a_gear_above_the_undercut_limit_is_not_shifted(pressure_angle: float) -> None:
    """A gear that cannot undercut must not be grown: the shift is a remedy, not a default."""
    limit = _undercut_limit(pressure_angle)
    for teeth in (limit, limit + 2, limit + 8, limit + 20):
        excess = _shift_excess(teeth, pressure_angle)
        assert excess == pytest.approx(0.0, abs=5e-4), (
            f"a {teeth}-tooth gear at {pressure_angle} degrees is shifted by {excess:.5f} of its "
            f"pitch diameter, but {limit} teeth already clears the undercut limit "
            f"2/sin^2({pressure_angle}) = {2.0 / math.sin(math.radians(pressure_angle)) ** 2:.1f}"
        )


@pytest.mark.parametrize("pressure_angle", PRESSURE_ANGLES)
def test_a_gear_below_the_undercut_limit_is_shifted(pressure_angle: float) -> None:
    """And one that would undercut must be, or its flanks are cut away."""
    limit = _undercut_limit(pressure_angle)
    for teeth in (limit - 2, max(6, limit - 6)):
        excess = _shift_excess(teeth, pressure_angle)
        assert excess > 1e-3, (
            f"a {teeth}-tooth gear at {pressure_angle} degrees is not shifted (excess "
            f"{excess:.5f}), yet it is below the undercut limit of {limit} teeth"
        )


@pytest.mark.parametrize("pressure_angle", PRESSURE_ANGLES)
def test_the_threshold_follows_the_pressure_angle(pressure_angle: float) -> None:
    """The point of the file: the limit is derived, not a constant.

    Found by searching upward for the first unshifted tooth count rather than by asserting a
    number, so the test states the relationship. A threshold hardcoded at any single value fails
    two of the three angles.
    """
    first_unshifted = next((t for t in range(6, 80) if abs(_shift_excess(t, pressure_angle)) < 5e-4), None)
    assert first_unshifted == _undercut_limit(pressure_angle), (
        f"at {pressure_angle} degrees the shift stops at {first_unshifted} teeth, where "
        f"2/sin^2({pressure_angle}) = "
        f"{2.0 / math.sin(math.radians(pressure_angle)) ** 2:.2f} puts the limit at "
        f"{_undercut_limit(pressure_angle)}"
    )


def test_the_shift_grows_as_the_tooth_count_falls() -> None:
    """Monotone, because the undercut it corrects gets worse as the gear gets smaller."""
    excesses = [_shift_excess(t, 20.0) for t in (8, 10, 12, 14, 16)]
    for smaller, larger in zip(excesses, excesses[1:], strict=False):
        assert smaller > larger, f"the profile shift does not fall as teeth are added: {excesses}"


#: Helix angles with the virtual pressure angle each induces. A helical gear undercuts according to
#: `atan(tan(alpha) / cos(beta))`, not its nominal pressure angle, so the limit falls as the helix
#: steepens: 18 teeth at 0 degrees, 16 at 20, 11 at 40.
HELIX_ANGLES = (0.0, 20.0, 40.0)


@pytest.mark.parametrize("helical", HELIX_ANGLES)
def test_a_helical_gear_uses_its_virtual_pressure_angle(helical: float) -> None:
    """The same derivation one level deeper, and the free half of this file's value.

    Asserted on `auto_profile_shift` rather than on built geometry: the helix also twists the solid,
    and measuring an outer diameter would then be measuring two things at once -- the mistake T97
    made with a single fixture and T108 made with a silhouette.
    """
    from pybosl2.parts.gears import GearSpec

    virtual = math.atan(math.tan(math.radians(20.0)) / math.cos(math.radians(helical)))
    expected = math.ceil(2.0 / math.sin(virtual) ** 2)
    first_unshifted = next(t for t in range(4, 90) if GearSpec.auto_profile_shift(t, 20.0, helical) == 0.0)
    assert first_unshifted == expected, (
        f"at helix {helical} degrees the shift stops at {first_unshifted} teeth, where the virtual "
        f"pressure angle {math.degrees(virtual):.2f} puts the limit at {expected}"
    )

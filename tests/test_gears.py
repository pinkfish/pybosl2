# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.gears: the gear-dimension functions (checked numerically against BOSL2's
formulas) and the involute spur gear (2-D and 3-D)."""

import math

import pytest

from pybosl2.parts.gears import (
    BevelGear,
    GearSpec,
    GearToothProfile,
    HerringboneGear,
    Rack,
    Rack2d,
    RingGear,
    SpurGear,
    SpurGear2d,
    Worm,
    WormGear,
)
from pybosl2.shapes2d import Bosl2Shape2D
from pybosl2.shapes3d import Bosl2Solid


def _size(solid: Bosl2Solid):  # type: ignore[no-untyped-def]
    _, size = solid.bounds()
    return size


# -- dimension functions ------------------------------------------------------


def test_pitch_and_module() -> None:
    assert GearSpec.pitch_value(2) == pytest.approx(2 * math.pi)
    assert GearSpec.module_value(math.pi) == pytest.approx(1.0)
    assert GearSpec.circular_pitch(mod=2) == pytest.approx(2 * math.pi)
    assert GearSpec.diametral_pitch_func(mod=2) == pytest.approx(math.pi / (2 * math.pi))


def test_pitch_radius() -> None:
    assert GearSpec(pitch=5, teeth=11).pitch_radius == pytest.approx(5 * 11 / math.pi / 2)
    # metric: mod*teeth/2
    assert GearSpec(mod=2, teeth=20).pitch_radius == pytest.approx(20.0)


def test_outer_radius() -> None:
    # outer = pitch_radius + adendum(=module); mod 2, teeth 16 -> 16 + 2 = 18 (no profile shift)
    assert GearSpec(mod=2, teeth=16, profile_shift=0).outer_radius == pytest.approx(18.0)
    # with the default "auto" profile shift, a 16-tooth gear grows by x*module to avoid undercut
    assert GearSpec(mod=2, teeth=16).outer_radius > 18.0


def test_bevel_pitch_angle() -> None:
    # atan(sin(90)/((mate/teeth)+cos(90))) = atan(teeth/mate)
    assert GearSpec.bevel_pitch_angle(18, 30) == pytest.approx(math.degrees(math.atan(18 / 30)))


def test_worm_gear_thickness_positive() -> None:
    assert GearSpec.worm_gear_thickness(pitch=5, teeth=36, worm_diam=30) > 0


# -- tooth profile & gears ----------------------------------------------------


def test_tooth_profile_shape() -> None:
    # the rack-carved tooth is a single closed-ish path spanning one tooth, symmetric about +Y
    tp = GearToothProfile(pitch=5, teeth=20, pressure_angle=20).path()
    assert len(tp) > 10
    xs = [p[0] for p in tp]
    assert min(xs) < 0 < max(xs)  # spans both flanks
    assert abs(min(xs) + max(xs)) < 0.2  # symmetric about the y-axis


def test_low_tooth_gear_has_undercut_shift() -> None:
    # a low-tooth gear picks up an auto profile shift (undercut avoidance)
    assert GearSpec.auto_profile_shift(8) > 0.4
    assert isinstance(SpurGear2d(mod=5, teeth=8).shape, Bosl2Shape2D)


def test_spur_gear2d_builds() -> None:
    assert isinstance(SpurGear2d(pitch=5, teeth=20).shape, Bosl2Shape2D)


@pytest.mark.parametrize(
    "kw",
    [
        {"pitch": 5, "teeth": 20, "thickness": 8},
        {"pitch": 5, "teeth": 20, "thickness": 8, "shaft_diam": 5},
        {"pitch": 5, "teeth": 20, "thickness": 8, "helical": 25},
        {"mod": 2, "teeth": 16, "thickness": 6},
    ],
)
def test_spur_gear_builds(kw) -> None:  # type: ignore[no-untyped-def]
    assert isinstance(SpurGear(**kw, fn=None, fa=None, fs=None).shape, Bosl2Solid)


def test_spur_gear_envelope_matches_outer_radius() -> None:
    solid = SpurGear(pitch=5, teeth=20, thickness=8, fn=None, fa=None, fs=None).shape
    width, _, height = _size(solid)
    expect = 2 * GearSpec(pitch=5, teeth=20).outer_radius
    assert width == pytest.approx(expect, abs=0.5)
    assert height == pytest.approx(8, abs=0.01)


def test_teeth_count_scales_radius() -> None:
    assert GearSpec(pitch=5, teeth=40).pitch_radius > GearSpec(pitch=5, teeth=20).pitch_radius


# -- rack ---------------------------------------------------------------------


def test_rack2d_builds() -> None:
    assert isinstance(Rack2d(pitch=5, teeth=10, height=6).shape, Bosl2Shape2D)


def test_rack_length_and_thickness() -> None:
    radius = Rack(pitch=5, teeth=10, thickness=5, height=5, pressure_angle=20).shape
    length, thick, hgt = _size(radius)
    assert length == pytest.approx(10 * 5, abs=0.5)  # teeth * pitch
    assert thick == pytest.approx(5, abs=0.01)
    assert hgt == pytest.approx(5, abs=0.5)


def test_rack_helical_shears_length() -> None:
    straight = _size(Rack(pitch=5, teeth=10, thickness=5, height=5).shape)[0]
    sheared = _size(Rack(pitch=5, teeth=10, thickness=5, height=5, helical=30).shape)[0]
    assert sheared > straight


def test_rack_height_too_small_raises() -> None:
    with pytest.raises(ValueError, match="height must exceed adendum"):
        _ = Rack(pitch=5, teeth=10, thickness=5, height=1).shape  # < adendum + dedendum


# -- ring gear ----------------------------------------------------------------


def test_ring_gear_builds_as_annulus() -> None:
    ring = RingGear(pitch=5, teeth=20, thickness=6, backing=3, fn=None, fa=None, fs=None).shape
    assert isinstance(ring, Bosl2Solid)
    width, _, height = _size(ring)
    expect = 2 * (GearSpec(circ_pitch=5, teeth=20, internal=True).outer_radius + 3)
    assert width == pytest.approx(expect, abs=0.6)
    assert height == pytest.approx(6, abs=0.01)


# -- bevel gear ---------------------------------------------------------------


@pytest.mark.parametrize(
    "kw",
    [
        {
            "pitch": 5,
            "teeth": 20,
            "face_width": 10,
            "pitch_angle": 45,
            "cutter_radius": 0,
        },  # straight
        {"pitch": 5, "teeth": 20, "face_width": 10, "pitch_angle": 45},  # spiral
        {"pitch": 5, "teeth": 20, "face_width": 10, "pitch_angle": 45, "shaft_diam": 5},
        {"pitch": 5, "teeth": 18, "face_width": 8, "mate_teeth": 30},
        {
            "pitch": 5,
            "teeth": 20,
            "face_width": 10,
            "pitch_angle": 45,
            "left_handed": True,
        },
    ],
)
def test_bevel_gear_builds(kw) -> None:  # type: ignore[no-untyped-def]
    assert isinstance(BevelGear(**kw, fn=None, fa=None, fs=None).shape, Bosl2Solid)


def test_bevel_gear_envelope() -> None:
    # diameter is near the pitch diameter (cone tapers, teeth add a little); thickness > 0.
    solid = BevelGear(
        pitch=5, teeth=20, face_width=10, pitch_angle=45, cutter_radius=0, fn=None, fa=None, fs=None
    ).shape
    width, _, height = _size(solid)
    assert width == pytest.approx(2 * GearSpec(pitch=5, teeth=20).pitch_radius, abs=3)
    assert height > 1


def test_bevel_mate_teeth_sets_pitch_angle() -> None:
    # mate_teeth derives pitch_angle = atan(teeth/mate); a smaller ratio -> shallower cone -> thinner.
    steep = _size(BevelGear(pitch=5, teeth=20, face_width=8, mate_teeth=10, fn=None, fa=None, fs=None).shape)[2]
    shallow = _size(BevelGear(pitch=5, teeth=10, face_width=8, mate_teeth=40, fn=None, fa=None, fs=None).shape)[2]
    assert steep != pytest.approx(shallow, abs=0.1)


# -- worm & worm gear ---------------------------------------------------------


@pytest.mark.parametrize(
    "kw",
    [
        {"pitch": 8, "diameter": 30, "length": 50},
        {"pitch": 8, "diameter": 30, "length": 50, "starts": 3},
        {"pitch": 8, "diameter": 30, "length": 50, "starts": 3, "left_handed": True},
    ],
)
def test_worm_builds(kw) -> None:  # type: ignore[no-untyped-def]
    assert isinstance(Worm(**kw).shape, Bosl2Solid)


def test_worm_length() -> None:
    _, _, hgt = _size(Worm(pitch=8, diameter=30, length=50).shape)
    assert hgt == pytest.approx(50, abs=0.5)


@pytest.mark.parametrize(
    "kw",
    [
        {"pitch": 5, "teeth": 30, "worm_diam": 25},
        {"pitch": 5, "teeth": 30, "worm_diam": 25, "shaft_diam": 6},
        {"pitch": 5, "teeth": 30, "worm_diam": 25, "left_handed": True},
    ],
)
def test_worm_gear_builds(kw) -> None:  # type: ignore[no-untyped-def]
    assert isinstance(WormGear(**kw, fn=None, fa=None, fs=None).shape, Bosl2Solid)


def test_worm_gear_thickness_matches_helper() -> None:
    solid = WormGear(pitch=5, teeth=30, worm_diam=25, fn=None, fa=None, fs=None).shape
    thick = _size(solid)[2]
    assert thick == pytest.approx(GearSpec.worm_gear_thickness(pitch=5, teeth=30, worm_diam=25), abs=0.5)


def test_worm_arc_out_of_range_raises() -> None:
    with pytest.raises(ValueError, match="worm_arc must be between"):
        _ = WormGear(pitch=5, teeth=30, worm_diam=25, worm_arc=90, fn=None, fa=None, fs=None).shape


# -- herringbone --------------------------------------------------------------


@pytest.mark.parametrize(
    "kw",
    [
        {"pitch": 5, "teeth": 20, "thickness": 10, "helical": 30},
        {"pitch": 5, "teeth": 20, "thickness": 10, "helical": 30, "shaft_diam": 5},
        {"pitch": 5, "teeth": 20, "thickness": 10, "helical": 0},
        {"mod": 2, "teeth": 16, "thickness": 8, "helical": 25},
    ],
)
def test_herringbone_builds(kw) -> None:  # type: ignore[no-untyped-def]
    assert isinstance(HerringboneGear(**kw, fn=None, fa=None, fs=None).shape, Bosl2Solid)


def test_herringbone_envelope_matches_spur() -> None:
    height = HerringboneGear(
        mod=5, teeth=20, thickness=10, fn=None, fa=None, fs=None
    ).shape  # no helical -> matches the spur envelope
    width, _, hgt = _size(height)
    assert width == pytest.approx(2 * GearSpec(mod=5, teeth=20).outer_radius, abs=1.5)
    assert hgt == pytest.approx(10, abs=0.01)


# -- profile shift / undercut avoidance ---------------------------------------


def test_auto_profile_shift_formula() -> None:
    # undercut limit ~17 teeth at 20 deg -> ~0 shift there; more shift for fewer teeth; 0 above.
    assert GearSpec.auto_profile_shift(17, 20) == pytest.approx(0, abs=0.02)
    assert GearSpec.auto_profile_shift(10, 20) == pytest.approx(1 - 10 * math.sin(math.radians(20)) ** 2 / 2)
    assert GearSpec.auto_profile_shift(30, 20) == 0.0


def test_profile_shift_grows_the_tooth() -> None:
    # a positive profile shift moves the tooth outward -- the tooth profile is centred on the pitch
    # point, so the tip (its largest y) moves further out.
    tip0 = max(y for _x, y in GearToothProfile(mod=5, teeth=8, profile_shift=0).path())
    tip_shifted = max(y for _x, y in GearToothProfile(mod=5, teeth=8, profile_shift=0.5).path())
    assert tip_shifted > tip0


# -- new-API sizing (circ_pitch / mod / diam_pitch) & gear_dist ---------------


def test_pitch_inputs_agree() -> None:
    # mod=5 <-> circ_pitch=5*pi <-> diam_pitch=25.4/5
    a = GearSpec(mod=5, teeth=20).pitch_radius
    b = GearSpec(circ_pitch=5 * math.pi, teeth=20).pitch_radius
    c = GearSpec(diam_pitch=25.4 / 5, teeth=20).pitch_radius
    assert a == pytest.approx(50)
    assert b == pytest.approx(50)
    assert c == pytest.approx(50)


def test_gear_dist_no_shift_is_sum_of_pitch_radii() -> None:
    diameter = GearSpec.gear_dist(30, 15, mod=5, profile_shift1=0, profile_shift2=0)
    assert diameter == pytest.approx(GearSpec(mod=5, teeth=30).pitch_radius + GearSpec(mod=5, teeth=15).pitch_radius)


def test_gear_dist_rack_uses_pitch_radius() -> None:
    # teeth2=0 is a rack; distance is the gear's pitch radius (+ shift)
    diameter = GearSpec.gear_dist(20, 0, mod=5, profile_shift1=0, profile_shift2=0)
    assert diameter == pytest.approx(GearSpec(mod=5, teeth=20).pitch_radius)


def test_spur_gear_new_api_builds() -> None:
    assert isinstance(
        SpurGear(mod=5, teeth=18, thickness=25, helical=-29, shaft_diam=15, fn=None, fa=None, fs=None).shape,
        Bosl2Solid,
    )
    assert isinstance(
        SpurGear(mod=5, teeth=16, thickness=35, helical=-20, herringbone=True, fn=None, fa=None, fs=None).shape,
        Bosl2Solid,
    )
    assert isinstance(SpurGear2d(mod=5, teeth=30, gear_spin=45).shape, Bosl2Shape2D)


# -- coverage gaps surfaced by the QA review ----------------------------------


def test_internal_spur_gear_teeth_point_inward() -> None:
    # an internal (ring) gear's teeth point inward: the tip (root_radius) is below the pitch circle,
    # while its outer/valley radius is above it.
    pr = GearSpec(mod=5, teeth=30).pitch_radius
    r_outer = GearSpec(mod=5, teeth=30, internal=True).outer_radius
    assert GearSpec(mod=5, teeth=30, internal=True).root_radius < pr < r_outer
    assert isinstance(SpurGear2d(mod=5, teeth=30, internal=True).shape, Bosl2Shape2D)


def test_gear_dist_with_profile_shift_increases_spacing() -> None:
    # profile shift raises the working pressure angle, spreading the gears apart
    base = GearSpec.gear_dist(20, 20, mod=5, profile_shift1=0, profile_shift2=0)
    shifted = GearSpec.gear_dist(20, 20, mod=5, profile_shift1=0.5, profile_shift2=0.5)
    assert shifted > base


def test_hide_removes_teeth() -> None:
    full = SpurGear2d(mod=5, teeth=20).shape
    hidden = SpurGear2d(mod=5, teeth=20, hide=5).shape
    assert isinstance(hidden, Bosl2Shape2D)
    # hiding teeth removes area, so the hidden gear's bbox is no larger
    assert _size2d(hidden)[0] <= _size2d(full)[0] + 0.1  # type: ignore[no-untyped-call]


def test_backlash_clearance_shorten_build() -> None:
    assert isinstance(SpurGear2d(mod=5, teeth=20, backlash=0.2).shape, Bosl2Shape2D)
    assert isinstance(SpurGear2d(mod=5, teeth=20, clearance=1.0).shape, Bosl2Shape2D)
    assert isinstance(SpurGear2d(mod=5, teeth=20, shorten=0.1).shape, Bosl2Shape2D)


def _size2d(shape):  # type: ignore[no-untyped-def]
    # 2-D shapes have no z-bounds; measure via a thin extrude, which carries the tracked size
    _center, size = shape.linear_extrude(height=0.1).bounds()
    return size


@pytest.mark.parametrize("ps", [0.4, "auto"])
def test_profile_shift_gears_build(ps) -> None:  # type: ignore[no-untyped-def]
    assert isinstance(
        SpurGear(pitch=5, teeth=8, thickness=6, profile_shift=ps, fn=None, fa=None, fs=None).shape, Bosl2Solid
    )
    assert isinstance(SpurGear2d(pitch=5, teeth=8, profile_shift=ps).shape, Bosl2Shape2D)
    assert isinstance(
        HerringboneGear(pitch=5, teeth=8, thickness=6, helical=20, profile_shift=ps, fn=None, fa=None, fs=None).shape,
        Bosl2Solid,
    )

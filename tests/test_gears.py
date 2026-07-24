# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2.gears: the gear-dimension functions (checked numerically against BOSL2's
formulas) and the involute spur gear (2-D and 3-D)."""

import math

import pytest

from bosl2.gears import Gears as G
from bosl2.shapes3d import Bosl2Solid


def _size(solid):
    _center, size = solid.bounds()
    return size


# -- dimension functions ------------------------------------------------------


def test_pitch_and_module():
    assert G.pitch_value(2) == pytest.approx(2 * math.pi)
    assert G.module_value(math.pi) == pytest.approx(1.0)
    assert G.circular_pitch(mod=2) == pytest.approx(2 * math.pi)
    assert G.diametral_pitch(mod=2) == pytest.approx(math.pi / (2 * math.pi))


def test_pitch_radius():
    assert G.pitch_radius(pitch=5, teeth=11) == pytest.approx(5 * 11 / math.pi / 2)
    # metric: mod*teeth/2
    assert G.pitch_radius(mod=2, teeth=20) == pytest.approx(20.0)


def test_outer_radius():
    # outer = pitch_radius + adendum(=module); mod 2, teeth 16 -> 16 + 2 = 18 (no profile shift)
    assert G.outer_radius(mod=2, teeth=16, profile_shift=0) == pytest.approx(18.0)
    # with the default "auto" profile shift, a 16-tooth gear grows by x*module to avoid undercut
    assert G.outer_radius(mod=2, teeth=16) > 18.0


def test_bevel_pitch_angle():
    # atan(sin(90)/((mate/teeth)+cos(90))) = atan(teeth/mate)
    assert G.bevel_pitch_angle(18, 30) == pytest.approx(
        math.degrees(math.atan(18 / 30))
    )


def test_worm_gear_thickness_positive():
    assert G.worm_gear_thickness(pitch=5, teeth=36, worm_diam=30) > 0


# -- tooth profile & gears ----------------------------------------------------


def test_tooth_profile_shape():
    # the rack-carved tooth is a single closed-ish path spanning one tooth, symmetric about +Y
    tp = G.gear_tooth_profile(pitch=5, teeth=20, pressure_angle=20)
    assert len(tp) > 10
    xs = [p[0] for p in tp]
    assert min(xs) < 0 < max(xs)  # spans both flanks
    assert abs(min(xs) + max(xs)) < 0.2  # symmetric about the y-axis


def test_low_tooth_gear_has_undercut_shift():
    # a low-tooth gear picks up an auto profile shift (undercut avoidance)
    assert G.auto_profile_shift(8) > 0.4
    assert isinstance(G.spur_gear2d(mod=5, teeth=8), Bosl2Solid)


def test_spur_gear2d_builds():
    assert isinstance(G.spur_gear2d(pitch=5, teeth=20), Bosl2Solid)


@pytest.mark.parametrize(
    "kw",
    [
        {"pitch": 5, "teeth": 20, "thickness": 8},
        {"pitch": 5, "teeth": 20, "thickness": 8, "shaft_diam": 5},
        {"pitch": 5, "teeth": 20, "thickness": 8, "helical": 25},
        {"mod": 2, "teeth": 16, "thickness": 6},
    ],
)
def test_spur_gear_builds(kw):
    assert isinstance(G.spur_gear(**kw), Bosl2Solid)


def test_spur_gear_envelope_matches_outer_radius():
    g = G.spur_gear(pitch=5, teeth=20, thickness=8)
    w, l, height = _size(g)
    expect = 2 * G.outer_radius(5, 20)
    assert w == pytest.approx(expect, abs=0.5)
    assert height == pytest.approx(8, abs=0.01)


def test_teeth_count_scales_radius():
    assert G.pitch_radius(5, 40) > G.pitch_radius(5, 20)


# -- rack ---------------------------------------------------------------------


def test_rack2d_builds():
    assert isinstance(G.rack2d(pitch=5, teeth=10, height=6), Bosl2Solid)


def test_rack_length_and_thickness():
    radius = G.rack(pitch=5, teeth=10, thickness=5, height=5, pressure_angle=20)
    length, thick, hgt = _size(radius)
    assert length == pytest.approx(10 * 5, abs=0.5)  # teeth * pitch
    assert thick == pytest.approx(5, abs=0.01)
    assert hgt == pytest.approx(5, abs=0.5)


def test_rack_helical_shears_length():
    straight = _size(G.rack(pitch=5, teeth=10, thickness=5, height=5))[0]
    sheared = _size(G.rack(pitch=5, teeth=10, thickness=5, height=5, helical=30))[0]
    assert sheared > straight


def test_rack_height_too_small_raises():
    with pytest.raises(AssertionError):
        G.rack(pitch=5, teeth=10, thickness=5, height=1)  # < adendum + dedendum


# -- ring gear ----------------------------------------------------------------


def test_ring_gear_builds_as_annulus():
    ring = G.ring_gear(pitch=5, teeth=20, thickness=6, backing=3)
    assert isinstance(ring, Bosl2Solid)
    w, l, height = _size(ring)
    expect = 2 * (G.outer_radius(circ_pitch=5, teeth=20, internal=True) + 3)
    assert w == pytest.approx(expect, abs=0.6)
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
def test_bevel_gear_builds(kw):
    assert isinstance(G.bevel_gear(**kw), Bosl2Solid)


def test_bevel_gear_envelope():
    # diameter is near the pitch diameter (cone tapers, teeth add a little); thickness > 0.
    g = G.bevel_gear(pitch=5, teeth=20, face_width=10, pitch_angle=45, cutter_radius=0)
    w, l, height = _size(g)
    assert w == pytest.approx(2 * G.pitch_radius(5, 20), abs=3)
    assert height > 1


def test_bevel_mate_teeth_sets_pitch_angle():
    # mate_teeth derives pitch_angle = atan(teeth/mate); a smaller ratio -> shallower cone -> thinner.
    steep = _size(G.bevel_gear(pitch=5, teeth=20, face_width=8, mate_teeth=10))[2]
    shallow = _size(G.bevel_gear(pitch=5, teeth=10, face_width=8, mate_teeth=40))[2]
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
def test_worm_builds(kw):
    assert isinstance(G.worm(**kw), Bosl2Solid)


def test_worm_length():
    w, l, hgt = _size(G.worm(pitch=8, diameter=30, length=50))
    assert hgt == pytest.approx(50, abs=0.5)


@pytest.mark.parametrize(
    "kw",
    [
        {"pitch": 5, "teeth": 30, "worm_diam": 25},
        {"pitch": 5, "teeth": 30, "worm_diam": 25, "shaft_diam": 6},
        {"pitch": 5, "teeth": 30, "worm_diam": 25, "left_handed": True},
    ],
)
def test_worm_gear_builds(kw):
    assert isinstance(G.worm_gear(**kw), Bosl2Solid)


def test_worm_gear_thickness_matches_helper():
    g = G.worm_gear(pitch=5, teeth=30, worm_diam=25)
    thick = _size(g)[2]
    assert thick == pytest.approx(G.worm_gear_thickness(5, 30, 25), abs=0.5)


def test_worm_arc_out_of_range_raises():
    with pytest.raises(AssertionError):
        G.worm_gear(pitch=5, teeth=30, worm_diam=25, worm_arc=90)


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
def test_herringbone_builds(kw):
    assert isinstance(G.herringbone_gear(**kw), Bosl2Solid)


def test_herringbone_envelope_matches_spur():
    height = G.herringbone_gear(
        mod=5, teeth=20, thickness=10
    )  # no helical -> matches the spur envelope
    w, l, hgt = _size(height)
    assert w == pytest.approx(2 * G.outer_radius(mod=5, teeth=20), abs=1.5)
    assert hgt == pytest.approx(10, abs=0.01)


# -- profile shift / undercut avoidance ---------------------------------------


def test_auto_profile_shift_formula():
    # undercut limit ~17 teeth at 20 deg -> ~0 shift there; more shift for fewer teeth; 0 above.
    assert G.auto_profile_shift(17, 20) == pytest.approx(0, abs=0.02)
    assert G.auto_profile_shift(10, 20) == pytest.approx(
        1 - 10 * math.sin(math.radians(20)) ** 2 / 2
    )
    assert G.auto_profile_shift(30, 20) == 0.0


def test_profile_shift_grows_the_tooth():
    # a positive profile shift moves the tooth outward -- the tooth profile is centred on the pitch
    # point, so the tip (its largest y) moves further out.
    tip0 = max(y for _x, y in G.gear_tooth_profile(mod=5, teeth=8, profile_shift=0))
    tip_shifted = max(y for _x, y in G.gear_tooth_profile(mod=5, teeth=8, profile_shift=0.5))
    assert tip_shifted > tip0


# -- new-API sizing (circ_pitch / mod / diam_pitch) & gear_dist ---------------


def test_pitch_inputs_agree():
    # mod=5 <-> circ_pitch=5*pi <-> diam_pitch=25.4/5
    a = G.pitch_radius(mod=5, teeth=20)
    b = G.pitch_radius(circ_pitch=5 * math.pi, teeth=20)
    c = G.pitch_radius(diam_pitch=25.4 / 5, teeth=20)
    assert a == pytest.approx(50) and b == pytest.approx(50) and c == pytest.approx(50)


def test_gear_dist_no_shift_is_sum_of_pitch_radii():
    diameter = G.gear_dist(30, 15, mod=5, profile_shift1=0, profile_shift2=0)
    assert diameter == pytest.approx(
        G.pitch_radius(mod=5, teeth=30) + G.pitch_radius(mod=5, teeth=15)
    )


def test_gear_dist_rack_uses_pitch_radius():
    # teeth2=0 is a rack; distance is the gear's pitch radius (+ shift)
    diameter = G.gear_dist(20, 0, mod=5, profile_shift1=0, profile_shift2=0)
    assert diameter == pytest.approx(G.pitch_radius(mod=5, teeth=20))


def test_spur_gear_new_api_builds():
    assert isinstance(
        G.spur_gear(mod=5, teeth=18, thickness=25, helical=-29, shaft_diam=15),
        Bosl2Solid,
    )
    assert isinstance(
        G.spur_gear(mod=5, teeth=16, thickness=35, helical=-20, herringbone=True),
        Bosl2Solid,
    )
    assert isinstance(G.spur_gear2d(mod=5, teeth=30, gear_spin=45), Bosl2Solid)


# -- coverage gaps surfaced by the QA review ----------------------------------


def test_internal_spur_gear_teeth_point_inward():
    # an internal (ring) gear's teeth point inward: the tip (root_radius) is below the pitch circle,
    # while its outer/valley radius is above it.
    pr = G.pitch_radius(mod=5, teeth=30)
    assert (
        G.root_radius(mod=5, teeth=30, internal=True)
        < pr
        < G.outer_radius(mod=5, teeth=30, internal=True)
    )
    assert isinstance(G.spur_gear2d(mod=5, teeth=30, internal=True), Bosl2Solid)


def test_gear_dist_with_profile_shift_increases_spacing():
    # profile shift raises the working pressure angle, spreading the gears apart
    base = G.gear_dist(20, 20, mod=5, profile_shift1=0, profile_shift2=0)
    shifted = G.gear_dist(20, 20, mod=5, profile_shift1=0.5, profile_shift2=0.5)
    assert shifted > base


def test_hide_removes_teeth():
    full = G.spur_gear2d(mod=5, teeth=20)
    hidden = G.spur_gear2d(mod=5, teeth=20, hide=5)
    assert isinstance(hidden, Bosl2Solid)
    # hiding teeth removes area, so the hidden gear's bbox is no larger
    assert _size2d(hidden)[0] <= _size2d(full)[0] + 0.1


def test_backlash_clearance_shorten_build():
    assert isinstance(G.spur_gear2d(mod=5, teeth=20, backlash=0.2), Bosl2Solid)
    assert isinstance(G.spur_gear2d(mod=5, teeth=20, clearance=1.0), Bosl2Solid)
    assert isinstance(G.spur_gear2d(mod=5, teeth=20, shorten=0.1), Bosl2Solid)


def _size2d(solid):
    # 2D shapes have no z-bounds; measure via a thin extrude, re-wrapping with tracked size
    _center, size = Bosl2Solid(
        solid.shape.linear_extrude(height=0.1), size=[solid.size[0], solid.size[1], 0.1]
    ).bounds()
    return size


@pytest.mark.parametrize("ps", [0.4, "auto"])
def test_profile_shift_gears_build(ps):
    assert isinstance(
        G.spur_gear(pitch=5, teeth=8, thickness=6, profile_shift=ps), Bosl2Solid
    )
    assert isinstance(G.spur_gear2d(pitch=5, teeth=8, profile_shift=ps), Bosl2Solid)
    assert isinstance(
        G.herringbone_gear(pitch=5, teeth=8, thickness=6, helical=20, profile_shift=ps),
        Bosl2Solid,
    )

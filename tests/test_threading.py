# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/threading.py: the thread profiles (ported verbatim from BOSL2) and the
Threading rod/nut builders. Native geometry is mocked, so these check the profiles numerically and
that every builder returns a Bosl2Solid; the real geometry (watertight rods/nuts with the right
major/minor diameter and length) is verified in test_stl_render.py."""

import math
from collections.abc import Callable

import numpy as np
import pytest

from pybosl2.parts.enums import NutShape
from pybosl2.parts.threading import (
    ThreadedNut,
    ThreadedRod,
    ThreadHelix,
    _buttress_profile,
    _iso_profile,
    _trapezoidal_profile,
    acme_threaded_nut,
    acme_threaded_rod,
    buttress_threaded_nut,
    buttress_threaded_rod,
    iso_threaded_nut,
    iso_threaded_rod,
    square_threaded_nut,
    square_threaded_rod,
    trapezoidal_threaded_nut,
    trapezoidal_threaded_rod,
)
from pybosl2.shapes3d import Bosl2Solid

# -- thread profiles (in pitch units) -----------------------------------------------------


def test_iso_profile() -> None:
    depth = math.cos(math.radians(30)) * 5 / 8
    exp = [
        [-depth / math.sqrt(3) - 1 / 16, -depth],
        [-1 / 16, 0],
        [1 / 16, 0],
        [depth / math.sqrt(3) + 1 / 16, -depth],
    ]
    np.testing.assert_allclose(_iso_profile(), exp, atol=1e-12)  # type: ignore[call-overload]


def test_trapezoidal_profile_30deg() -> None:
    # thread_angle 30, depth = pitch/2 -> pa_delta = 0.5*(p/2)*tan(15)/p = tan(15)/4
    p = 2.0
    pa = math.tan(math.radians(15)) / 4
    exp = [[-(0.25 + pa), -0.5], [-(0.25 - pa), 0], [0.25 - pa, 0], [0.25 + pa, -0.5]]
    np.testing.assert_allclose(_trapezoidal_profile(p, 30), exp, atol=1e-12)  # type: ignore[call-overload]


def test_trapezoidal_depth_scales_with_pitch() -> None:
    # y (the depth fraction) is thread_depth/pitch; default depth = pitch/2 -> -0.5
    prof = _trapezoidal_profile(4, 30)
    assert math.isclose(min(p[1] for p in prof), -0.5, abs_tol=1e-12)


def test_buttress_profile_is_asymmetric() -> None:
    prof = _buttress_profile()
    assert prof[0] == [-1 / 2, -0.77]
    # asymmetric: the crest [5/16, 7/16] is offset from center, not centred on 0
    crest = [p for p in prof if p[1] == 0]
    crest_mid = (crest[0][0] + crest[-1][0]) / 2
    assert not math.isclose(crest_mid, 0.0, abs_tol=1e-6)


def test_impossible_trapezoid_raises() -> None:
    with pytest.raises(ValueError, match="trapezoidal thread geometry is"):
        _trapezoidal_profile(1, 170)  # flanks would cross


def test_thread_profile_is_structured_dataclass() -> None:
    from pybosl2.parts.threading import ThreadProfile

    iso = _iso_profile()
    assert isinstance(iso, ThreadProfile)
    assert iso.name == "ISO"
    # depth is the peak-to-valley fraction; ISO depth = cos(30)*5/8
    assert math.isclose(iso.depth, math.cos(math.radians(30)) * 5 / 8, abs_tol=1e-12)
    assert math.isclose(iso.depth_abs(2.0), iso.depth * 2.0, abs_tol=1e-12)
    # still usable as the raw point list it wraps
    assert iso.as_points() == [list(p) for p in iso]
    assert _trapezoidal_profile(2, 29).name == "trapezoidal-29deg"


# -- rod builders return solids -----------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda: iso_threaded_rod(12, 24, 1.75).shape,
        lambda: trapezoidal_threaded_rod(20, 30, 4).shape,
        lambda: acme_threaded_rod(20, 30, 4).shape,
        lambda: square_threaded_rod(20, 30, 4).shape,
        lambda: buttress_threaded_rod(20, 30, 4).shape,
        lambda: ThreadedRod(16, 24, 2, _iso_profile()).shape,
        lambda: iso_threaded_rod(16, 24, 2, starts=2).shape,
        lambda: iso_threaded_rod(12, 24, 1.75, left_handed=True).shape,
    ],
)
def test_rod_builders(call: Callable[[], Bosl2Solid]) -> None:
    """Every rod profile builds a round bar: circular in plan, and taller than it is wide."""
    rod = call()
    assert isinstance(rod, Bosl2Solid)
    _box = rod.bounds()
    _centre, size = list(_box.center), list(_box.size)
    width, depth, height = (float(v) for v in size)
    assert width == pytest.approx(depth, rel=0.02)  # round in plan, whatever the thread form
    assert height > width  # a rod, not a washer


# -- nut builders return solids -----------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda: iso_threaded_nut(18, 12, 10, 1.75, slop=0.1).shape,
        lambda: iso_threaded_nut(18, 12, 10, 1.75, shape=NutShape.SQUARE, slop=0.1).shape,
        lambda: trapezoidal_threaded_nut(24, 16, 12, 3, slop=0.1).shape,
        lambda: acme_threaded_nut(24, 16, 12, 3, slop=0.1).shape,
        lambda: square_threaded_nut(24, 16, 12, 3, slop=0.1).shape,
        lambda: buttress_threaded_nut(24, 16, 12, 3, slop=0.1).shape,
        lambda: ThreadedNut(18, 12, 10, 1.75, _iso_profile(), slop=0.1).shape,
    ],
)
def test_nut_builders(call: Callable[[], Bosl2Solid]) -> None:
    """Every nut is a squat block with a bore: wider than it is tall, and finite in every axis."""
    nut = call()
    assert isinstance(nut, Bosl2Solid)
    _box = nut.bounds()
    _centre, size = list(_box.center), list(_box.size)
    width, _depth, height = (float(v) for v in size)
    assert width > height
    assert all(math.isfinite(float(v)) and float(v) > 0 for v in size)


def test_nut_with_zero_pitch_is_plain_hole() -> None:
    """pitch 0 leaves the bore unthreaded -- the same nut body, a different hole."""
    plain = iso_threaded_nut(18, 12, 10, 0).shape
    threaded = iso_threaded_nut(18, 12, 10, 1.75).shape
    assert [float(v) for v in plain.bounds().size] == pytest.approx([float(v) for v in threaded.bounds().size])
    assert repr(plain.shape) != repr(threaded.shape)


def test_thread_helix_builds() -> None:
    """A helix is `turns` * `pitch` tall, standing on a d=20 core -- more turns, more height."""
    three = ThreadHelix(20, 4, turns=3).shape
    two = ThreadHelix(20, 4, thread_depth=1.5, flank_angle=20, turns=2).shape
    assert float(three.bounds().size[0]) == pytest.approx(20.0, abs=0.2)  # the core diameter
    assert float(three.bounds().size[2]) > float(two.bounds().size[2])


def test_invalid_rod_dims_raise() -> None:
    with pytest.raises(ValueError, match="ThreadedRod: d, l and pitch"):
        ThreadedRod(12, 24, 0, _iso_profile())  # pitch 0
    with pytest.raises(ValueError, match="ThreadedRod: d, l and pitch"):
        ThreadedRod(0, 24, 1.5, _iso_profile())  # d 0


def test_bad_nut_shape_raises() -> None:
    with pytest.raises(ValueError, match="shape must be NutShape"):
        _ = iso_threaded_nut(18, 12, 10, 1.75, shape="round").shape

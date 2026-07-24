# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2.ball_bearings: the trade-size table (as BearingSpec dataclasses) and the
ball_bearing() cartridge model."""

import pytest

from bosl2.ball_bearings import BallBearings as BB, BearingSpec
from bosl2.shapes3d import Bosl2Solid


def _size(solid):
    _min, size = solid._native_bounds()
    return size


def test_info_returns_dataclass():
    spec = BB.ball_bearing_info("608")
    assert isinstance(spec, BearingSpec)
    assert (spec.inner_diameter, spec.outer_diameter, spec.width, spec.shielded) == (
        8,
        22,
        7,
        False,
    )


def test_zz_variant_is_shielded_same_dims():
    open_ = BB.ball_bearing_info("6902")
    zz = BB.ball_bearing_info("6902ZZ")
    assert not open_.shielded and zz.shielded
    assert (zz.inner_diameter, zz.outer_diameter, zz.width) == (
        open_.inner_diameter,
        open_.outer_diameter,
        open_.width,
    )


def test_imperial_size_uses_inches():
    r8 = BB.ball_bearing_info("R8")
    assert r8.inner_diameter == pytest.approx(0.5 * 25.4)
    assert r8.outer_diameter == pytest.approx(9 / 8 * 25.4)


def test_unknown_size_raises():
    with pytest.raises(ValueError):
        BB.ball_bearing_info("nope")


@pytest.mark.parametrize(
    "kw",
    [
        {"trade_size": "608"},
        {"trade_size": "608", "shield": False},
        {"trade_size": "6902ZZ"},
        {"inner_diameter": 12, "outer_diameter": 32, "width": 10, "shield": False},
    ],
)
def test_ball_bearing_builds(kw):
    assert isinstance(BB.ball_bearing(**kw), Bosl2Solid)


def test_envelope_matches_od_and_width():
    b = BB.ball_bearing("6205")  # id 25, od 52, width 15
    w, _wy, hgt = _size(b)
    assert w == pytest.approx(52, abs=0.5)
    assert hgt == pytest.approx(15, abs=0.01)


def test_requires_size_or_dims():
    with pytest.raises(AssertionError):
        BB.ball_bearing()

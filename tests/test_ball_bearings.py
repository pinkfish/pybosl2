# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.ball_bearings: the trade-size table (as BearingSpec dataclasses) and the
ball_bearing() cartridge model."""

import pytest

from pybosl2.parts.ball_bearings import BallBearings, BearingSpec
from pybosl2.shapes3d import Bosl2Solid


def _size(solid: Bosl2Solid) -> list[float]:
    _min, size = solid._native_bounds()  # type: ignore[misc]
    return size


def test_info_returns_dataclass() -> None:
    spec = BallBearings.ball_bearing_info("608")
    assert isinstance(spec, BearingSpec)
    assert (spec.inner_diameter, spec.outer_diameter, spec.width, spec.shielded) == (
        8,
        22,
        7,
        False,
    )


def test_zz_variant_is_shielded_same_dims() -> None:
    open_ = BallBearings.ball_bearing_info("6902")
    zz = BallBearings.ball_bearing_info("6902ZZ")
    assert not open_.shielded
    assert zz.shielded
    assert (zz.inner_diameter, zz.outer_diameter, zz.width) == (
        open_.inner_diameter,
        open_.outer_diameter,
        open_.width,
    )


def test_imperial_size_uses_inches() -> None:
    r8 = BallBearings.ball_bearing_info("R8")
    assert r8.inner_diameter == pytest.approx(0.5 * 25.4)
    assert r8.outer_diameter == pytest.approx(9 / 8 * 25.4)


def test_unknown_size_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported ball bearing trade size"):
        BallBearings.ball_bearing_info("nope")


@pytest.mark.parametrize(
    ("kw", "outer_diameter", "width", "balls"),
    [
        # 608 is an open bearing, so its balls are modelled ...
        ({"trade_size": "608"}, 22, 7, 9),
        # ... and the trade size decides that, not shield=: 608ZZ is the shielded spelling.
        ({"trade_size": "608", "shield": True}, 22, 7, 9),
        ({"trade_size": "6902ZZ"}, 28, 7, 0),
        # With explicit dimensions there is no table to consult, so shield= is what decides.
        ({"inner_diameter": 12, "outer_diameter": 32, "width": 10, "shield": False}, 32, 10, 9),
        ({"inner_diameter": 12, "outer_diameter": 32, "width": 10, "shield": True}, 32, 10, 0),
    ],
)
def test_ball_bearing_envelope_and_shielding(
    kw: dict[str, object],
    outer_diameter: float,
    width: float,
    balls: int,
) -> None:
    """The envelope is the outer diameter by the width; shielding hides the balls inside it."""
    bearing = BallBearings.ball_bearing(**kw)  # type: ignore[arg-type]
    size = _size(bearing)
    assert size[0] == pytest.approx(outer_diameter, abs=0.01)
    assert size[1] == pytest.approx(outer_diameter, abs=0.2)  # faceted circle, just inside
    assert size[2] == pytest.approx(width, abs=0.01)
    # A shield covers the race, so a shielded cartridge draws no balls at all.
    assert repr(bearing).count("sphere(") == balls


def test_envelope_matches_od_and_width() -> None:
    b = BallBearings.ball_bearing("6205")  # inner_diameter 25, outer_diameter 52, width 15
    w, _wy, hgt = _size(b)
    assert w == pytest.approx(52, abs=0.5)
    assert hgt == pytest.approx(15, abs=0.01)


def test_requires_size_or_dims() -> None:
    with pytest.raises(ValueError, match="must give inner_diameter"):
        BallBearings.ball_bearing()

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.linear_bearings: LMxUU bearings, the size table, and pillow-block housings."""

import pytest

from pybosl2.parts.linear_bearings import LinearBearings, LinearBearingSpec
from pybosl2.shapes3d import Bosl2Solid


def _size(s: Bosl2Solid) -> list[float]:
    _min, size = s._native_bounds()  # type: ignore[misc]
    return size


def test_info_returns_dataclass() -> None:
    spec = LinearBearings.lmxuu_info(8)
    assert isinstance(spec, LinearBearingSpec)
    assert (spec.outer_diameter, spec.length) == (15, 24)
    assert LinearBearings.lmxuu_info(12).outer_diameter == 21


def test_unknown_size_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported lmXuu linear bearing size"):
        LinearBearings.lmxuu_info(7)


@pytest.mark.parametrize(("size", "outer_diameter", "length"), [(8, 15, 24), (12, 21, 30), (20, 32, 42)])
def test_lmxuu_bearing_envelope(size: int, outer_diameter: int, length: int) -> None:
    b = LinearBearings.lmxuu_bearing(size)
    w, _wy, height = _size(b)
    assert w == pytest.approx(outer_diameter, abs=0.5)
    assert height == pytest.approx(length, abs=0.05)


def test_generic_bearing_builds() -> None:
    assert isinstance(
        LinearBearings.linear_bearing(length=24, outer_diameter=15, inner_diameter=8, fn=None, fa=None, fs=None),
        Bosl2Solid,
    )


@pytest.mark.parametrize("kw", [{}, {"size": 12}, {"size": 20}])
def test_housing_builds(kw: dict[str, object]) -> None:
    assert isinstance(LinearBearings.lmxuu_housing(**kw), Bosl2Solid)  # type: ignore[arg-type]


def test_housing_grows_with_bearing() -> None:
    small = _size(LinearBearings.lmxuu_housing(8))[1]
    big = _size(LinearBearings.lmxuu_housing(20))[1]
    assert big > small

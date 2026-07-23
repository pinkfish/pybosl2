# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2.linear_bearings: LMxUU bearings, the size table, and pillow-block housings."""

import pytest

from bosl2.linear_bearings import LinearBearings as LB, LinearBearingSpec
from bosl2.shapes3d import Bosl2Solid


def _size(s):
    _min, size = s._native_bounds()
    return size


def test_info_returns_dataclass():
    spec = LB.lmXuu_info(8)
    assert isinstance(spec, LinearBearingSpec)
    assert (spec.od, spec.length) == (15, 24)
    assert LB.lmXuu_info(12).od == 21


def test_unknown_size_raises():
    with pytest.raises(ValueError):
        LB.lmXuu_info(7)


@pytest.mark.parametrize("size,od,length", [(8, 15, 24), (12, 21, 30), (20, 32, 42)])
def test_lmXuu_bearing_envelope(size, od, length):
    b = LB.lmXuu_bearing(size)
    w, _wy, h = _size(b)
    assert w == pytest.approx(od, abs=0.5)
    assert h == pytest.approx(length, abs=0.05)


def test_generic_bearing_builds():
    assert isinstance(LB.linear_bearing(l=24, od=15, id=8), Bosl2Solid)


@pytest.mark.parametrize("kw", [{}, {"size": 12}, {"size": 20}])
def test_housing_builds(kw):
    assert isinstance(LB.lmXuu_housing(**kw), Bosl2Solid)


def test_housing_grows_with_bearing():
    small = _size(LB.lmXuu_housing(8))[1]
    big = _size(LB.lmXuu_housing(20))[1]
    assert big > small

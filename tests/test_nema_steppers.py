# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2.nema_steppers: NEMA stepper-motor models, mount masks, and the size table."""

import pytest

from bosl2.nema_steppers import NemaSteppers as N, NemaSpec
from bosl2.shapes3d import Bosl2Solid, cuboid


def _size(s):
    _min, size = s._native_bounds()
    return size


def test_info_returns_dataclass():
    s = N.nema_motor_info(17)
    assert isinstance(s, NemaSpec)
    assert s.motor_width == 42.3 and s.screw_spacing == 31.0 and s.shaft_diam == 5.0


def test_unknown_size_raises():
    with pytest.raises(ValueError):
        N.nema_motor_info(99)


@pytest.mark.parametrize("size,width", [(8, 20.3), (17, 42.3), (23, 57.0), (42, 110.0)])
def test_motor_body_width(size, width):
    m = N.nema_stepper_motor(size)
    w, length, _h = _size(m)
    assert w == pytest.approx(width, abs=0.1)
    assert length == pytest.approx(width, abs=0.1)


def test_motor_height_is_body_plus_shaft():
    m = N.nema_stepper_motor(17, height=24, shaft_len=20)
    assert _size(m)[2] == pytest.approx(44, abs=0.2)


@pytest.mark.parametrize("kw", [{}, {"atype": "screws"}, {"length": 8}, {"slop": 0.2}])
def test_mount_mask_builds(kw):
    assert isinstance(N.nema_mount_mask(17, **kw), Bosl2Solid)


def test_mask_bad_atype_raises():
    with pytest.raises(ValueError):
        N.nema_mount_mask(17, atype="banana")


def test_mount_mask_cuts_a_plate():
    plate = cuboid([60, 60, 5]) - N.nema_mount_mask(17, depth=6)
    assert isinstance(plate, Bosl2Solid)

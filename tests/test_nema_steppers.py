# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.nema_steppers: NEMA stepper-motor models, mount masks, and the size table."""

import pytest

from pybosl2.parts.nema_steppers import NemaMotor, NemaMountMask, NemaSpec
from pybosl2.shapes3d import Bosl2Solid, cuboid


def _size(s: Bosl2Solid) -> list[float]:
    _min, size = s._native_bounds()  # type: ignore[misc]
    return size


def test_info_returns_dataclass() -> None:
    s = NemaSpec(17)
    assert isinstance(s, NemaSpec)
    assert s.motor_width == 42.3
    assert s.screw_spacing == 31.0
    assert s.shaft_diam == 5.0


def test_unknown_size_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported NEMA size"):
        NemaSpec(99)


@pytest.mark.parametrize(("size", "width"), [(8, 20.3), (17, 42.3), (23, 57.0), (42, 110.0)])
def test_motor_body_width(size: int, width: float) -> None:
    m = NemaMotor(size).shape
    w, length, _h = _size(m)
    assert w == pytest.approx(width, abs=0.1)
    assert length == pytest.approx(width, abs=0.1)


def test_motor_height_is_body_plus_shaft() -> None:
    m = NemaMotor(17, height=24, shaft_len=20).shape
    assert _size(m)[2] == pytest.approx(44, abs=0.2)


@pytest.mark.parametrize("kw", [{}, {"atype": "screws"}, {"length": 8}, {"slop": 0.2}])
def test_mount_mask_builds(kw: dict[str, object]) -> None:
    assert isinstance(NemaMountMask(17, **kw).shape, Bosl2Solid)


def test_mask_bad_atype_raises() -> None:
    with pytest.raises(ValueError, match="must be FULL or SCREWS"):
        NemaMountMask(17, atype="banana")


def test_mount_mask_cuts_a_plate() -> None:
    plate = cuboid([60, 60, 5]) - NemaMountMask(17, depth=6).shape
    assert isinstance(plate, Bosl2Solid)

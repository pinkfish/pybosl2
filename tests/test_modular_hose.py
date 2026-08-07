# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.modular_hose: Loc-Line style ball-and-socket hose segments."""

import pytest

from pybosl2.parts.modular_hose import HoseSegment, HoseType, modular_hose_radius
from pybosl2.shapes3d import Bosl2Solid


def _size(s: Bosl2Solid) -> list[float]:
    _center, size = s.bounds()
    return size


@pytest.mark.parametrize(
    ("size", "bore", "outer"),
    [(0.25, 3.268, 4.864), (0.5, 6.422, 8.096), (0.75, 9.902, 11.989)],
)
def test_radius_matches_profile(size: float, bore: float, outer: float) -> None:
    assert modular_hose_radius(size) == pytest.approx(bore, abs=0.01)
    assert modular_hose_radius(size, outer=True) == pytest.approx(outer, abs=0.01)


def test_bad_size_raises() -> None:
    with pytest.raises(ValueError, match="size must be 0.25, 0.5 or 0.75"):
        HoseSegment(0.3)


def test_bad_type_raises() -> None:
    with pytest.raises(ValueError, match="type must be one of"):
        HoseSegment(0.5, type="banana")


@pytest.mark.parametrize("size", [0.25, 0.5, 0.75])
@pytest.mark.parametrize("hosetype", [HoseType.SEGMENT, HoseType.BALL, HoseType.SOCKET])
def test_builds(size: float, hosetype: HoseType) -> None:
    assert isinstance(HoseSegment(size, hosetype).shape(), Bosl2Solid)


def test_bigger_size_bigger_hose() -> None:
    assert _size(HoseSegment(0.75, HoseType.SEGMENT).shape())[0] > _size(HoseSegment(0.25, HoseType.SEGMENT).shape())[0]


def test_clearance_widens_socket() -> None:
    tight = _size(HoseSegment(0.5, HoseType.SEGMENT, clearance=0).shape())[0]
    loose = _size(HoseSegment(0.5, HoseType.SEGMENT, clearance=0.3).shape())[0]
    assert loose > tight

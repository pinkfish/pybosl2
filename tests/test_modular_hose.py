# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2.modular_hose: Loc-Line style ball-and-socket hose segments."""

import pytest

from bosl2.modular_hose import ModularHose as MH
from bosl2.shapes3d import Bosl2Solid


def _size(s):
    _min, size = s._native_bounds()
    return size


@pytest.mark.parametrize("size,bore,outer", [(0.25, 3.268, 4.864), (0.5, 6.422, 8.096), (0.75, 9.902, 11.989)])
def test_radius_matches_profile(size, bore, outer):
    assert MH.modular_hose_radius(size) == pytest.approx(bore, abs=0.01)
    assert MH.modular_hose_radius(size, outer=True) == pytest.approx(outer, abs=0.01)


def test_bad_size_raises():
    with pytest.raises(ValueError):
        MH.modular_hose(0.3)


def test_bad_type_raises():
    with pytest.raises(ValueError):
        MH.modular_hose(0.5, "banana")


@pytest.mark.parametrize("size", [0.25, 0.5, 0.75])
@pytest.mark.parametrize("type", ["segment", "ball", "socket"])
def test_builds(size, type):
    assert isinstance(MH.modular_hose(size, type), Bosl2Solid)


def test_bigger_size_bigger_hose():
    assert _size(MH.modular_hose(0.75, "segment"))[0] > _size(MH.modular_hose(0.25, "segment"))[0]


def test_clearance_widens_socket():
    tight = _size(MH.modular_hose(0.5, "segment", clearance=0))[0]
    loose = _size(MH.modular_hose(0.5, "segment", clearance=0.3))[0]
    assert loose > tight

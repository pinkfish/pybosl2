# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.hinges: living (folding) hinges, knuckle hinges, and snap connectors."""

import pytest

from pybosl2.parts.hinges import KnuckleHinge, KnuckleHingePair, LivingHingeMask, SnapLock, SnapSocket
from pybosl2.shapes3d import Bosl2Solid, cuboid


def _size(s: Bosl2Solid) -> list[float]:
    _min, size = s._native_bounds()  # type: ignore[misc]
    return size


def test_living_hinge_mask_and_plate() -> None:
    mask = LivingHingeMask(length=100, thick=3, foldangle=60).shape()
    assert isinstance(mask, Bosl2Solid)
    assert _size(mask)[0] == pytest.approx(100, abs=0.1)  # spans the plate length
    plate = cuboid([100, 40, 3]) - mask.down(1.5)
    assert isinstance(plate, Bosl2Solid)


def test_sharper_fold_needs_wider_groove() -> None:
    # foldangle is the interior angle: a sharper fold (smaller angle) needs a wider V-groove
    sharp = _size(LivingHingeMask(length=100, thick=3, foldangle=30).shape())[1]
    shallow = _size(LivingHingeMask(length=100, thick=3, foldangle=120).shape())[1]
    assert sharp > shallow


@pytest.mark.parametrize("inner", [False, True])
def test_knuckle_leaf_builds(inner: bool) -> None:
    assert isinstance(KnuckleHinge(inner=inner).shape(), Bosl2Solid)


def test_knuckle_pair_folds_about_the_pin() -> None:
    flat = _size(KnuckleHingePair(fold=0).shape())
    folded = _size(KnuckleHingePair(fold=90).shape())
    # laid flat the leaves spread in Y and the hinge is thin; folded 90 it stands up in Z
    assert flat[1] > flat[2]
    assert folded[2] > flat[2]


def test_snap_lock_and_socket_build() -> None:
    assert isinstance(SnapLock().shape(), Bosl2Solid)
    assert isinstance(SnapSocket().shape(), Bosl2Solid)

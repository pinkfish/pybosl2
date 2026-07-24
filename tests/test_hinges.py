# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2.hinges: living (folding) hinges, knuckle hinges, and snap connectors."""

import pytest

from bosl2.hinges import Hinges as H
from bosl2.shapes3d import Bosl2Solid, cuboid


def _size(s):
    _min, size = s._native_bounds()
    return size


def test_living_hinge_mask_and_plate():
    mask = H.living_hinge_mask(length=100, thick=3, foldangle=60)
    assert isinstance(mask, Bosl2Solid)
    assert _size(mask)[0] == pytest.approx(100, abs=0.1)  # spans the plate length
    plate = cuboid([100, 40, 3]) - mask.down(1.5)
    assert isinstance(plate, Bosl2Solid)


def test_sharper_fold_needs_wider_groove():
    # foldangle is the interior angle: a sharper fold (smaller angle) needs a wider V-groove
    sharp = _size(H.living_hinge_mask(length=100, thick=3, foldangle=30))[1]
    shallow = _size(H.living_hinge_mask(length=100, thick=3, foldangle=120))[1]
    assert sharp > shallow


@pytest.mark.parametrize("inner", [False, True])
def test_knuckle_leaf_builds(inner):
    assert isinstance(H.knuckle_hinge(inner=inner), Bosl2Solid)


def test_knuckle_pair_folds_about_the_pin():
    flat = _size(H.knuckle_hinge_pair(fold=0))
    folded = _size(H.knuckle_hinge_pair(fold=90))
    # laid flat the leaves spread in Y and the hinge is thin; folded 90 it stands up in Z
    assert flat[1] > flat[2]
    assert folded[2] > flat[2]


def test_snap_lock_and_socket_build():
    assert isinstance(H.snap_lock(), Bosl2Solid)
    assert isinstance(H.snap_socket(), Bosl2Solid)

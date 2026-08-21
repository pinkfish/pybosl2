# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.hinges: living (folding) hinges, knuckle hinges, and snap connectors."""

import pytest

from pybosl2.parts.hinges import KnuckleHinge, KnuckleHingePair, LivingHingeMask, SnapLock, SnapSocket
from pybosl2.shapes3d import Bosl2Solid, cuboid


def _bounds(s: Bosl2Solid) -> tuple[list[float], list[float]]:
    return s._native_bounds()  # type: ignore[return-value]


def _size(s: Bosl2Solid) -> list[float]:
    return _bounds(s)[1]


def test_living_hinge_mask_and_plate() -> None:
    mask = LivingHingeMask(length=100, thick=3, foldangle=60).shape
    assert isinstance(mask, Bosl2Solid)
    assert _size(mask)[0] == pytest.approx(100, abs=0.1)  # spans the plate length
    plate = cuboid([100, 40, 3]) - mask.down(1.5)
    assert isinstance(plate, Bosl2Solid)


def test_sharper_fold_needs_wider_groove() -> None:
    # foldangle is the interior angle: a sharper fold (smaller angle) needs a wider V-groove
    sharp = _size(LivingHingeMask(length=100, thick=3, foldangle=30).shape)[1]
    shallow = _size(LivingHingeMask(length=100, thick=3, foldangle=120).shape)[1]
    assert sharp > shallow


@pytest.mark.parametrize(("length", "arm", "knuckle_diam"), [(40, 20, 6), (60, 30, 6), (40, 20, 10)])
def test_knuckle_leaf_measures_length_arm_and_knuckle(length: float, arm: float, knuckle_diam: float) -> None:
    """A leaf runs the hinge length in X, is as thick as the knuckle in Z, and reaches `arm` out."""
    lo, size = _bounds(KnuckleHinge(length=length, arm=arm, knuckle_diam=knuckle_diam).shape)
    assert size[0] == pytest.approx(length)
    assert size[2] == pytest.approx(knuckle_diam, abs=0.2)  # the faceted knuckle sets the thickness
    # The knuckle straddles the origin; the leaf runs out from it by `arm`.
    assert lo[1] == pytest.approx(-knuckle_diam / 2, abs=0.2)
    assert size[1] == pytest.approx(arm + knuckle_diam, abs=0.2)


def test_inner_leaf_mirrors_the_outer_one() -> None:
    """inner= swaps which side of the pin the leaf lies on; the two must interleave, not clash."""
    outer_lo, outer_size = _bounds(KnuckleHinge(inner=False).shape)
    inner_lo, inner_size = _bounds(KnuckleHinge(inner=True).shape)
    assert inner_size == pytest.approx(outer_size)
    # Mirrored in Y about the pin: the outer leaf's high edge is the inner leaf's low edge.
    assert inner_lo[1] == pytest.approx(-(outer_lo[1] + outer_size[1]))
    assert inner_lo[0] == pytest.approx(outer_lo[0])
    assert inner_lo[2] == pytest.approx(outer_lo[2])


def test_knuckle_pair_folds_about_the_pin() -> None:
    flat = _size(KnuckleHingePair(fold=0).shape)
    folded = _size(KnuckleHingePair(fold=90).shape)
    # laid flat the leaves spread in Y and the hinge is thin; folded 90 it stands up in Z
    assert flat[1] > flat[2]
    assert folded[2] > flat[2]


@pytest.mark.parametrize(("snaplen", "snapdiam"), [(5, 5), (6, 7)])
def test_snap_lock_and_socket_are_mirrored_mating_halves(snaplen: float, snapdiam: float) -> None:
    """The lock and its socket are the same envelope, mirrored in Y so they face each other."""
    lock_lo, lock_size = _bounds(SnapLock(snaplen=snaplen, snapdiam=snapdiam).shape)
    sock_lo, sock_size = _bounds(SnapSocket(snaplen=snaplen, snapdiam=snapdiam).shape)

    assert lock_size == pytest.approx(sock_size)
    assert lock_size[0] == pytest.approx(snaplen)
    assert lock_size[1] == pytest.approx(snapdiam)
    assert lock_size[2] > 0
    assert sock_lo[1] == pytest.approx(-(lock_lo[1] + lock_size[1]))
    assert lock_lo[2] == pytest.approx(0.0)  # both sit on the plate surface


def test_snap_slop_pushes_the_halves_apart() -> None:
    """slop= is clearance: it moves each half further from the fold line, never nearer."""
    tight_lo, tight_size = _bounds(SnapLock().shape)
    loose_lo, loose_size = _bounds(SnapLock(slop=0.2).shape)
    assert loose_size == pytest.approx(tight_size)
    assert loose_lo[1] > tight_lo[1]

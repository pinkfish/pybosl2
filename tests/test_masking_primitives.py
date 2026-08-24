# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

import pytest

from pybosl2._edges_lang import Anchor
from pybosl2.masking import (
    mask2d_chamfer,
    mask2d_cove,
    mask2d_groove,
    mask2d_step,
    mask2d_tear,
    mask3d_chamfer,
    mask3d_groove,
    mask3d_roundover,
)
from pybosl2.path2d import Path2D


def test_mask2d_chamfer() -> None:
    path = mask2d_chamfer(x=3.0, y=4.0)
    assert isinstance(path, Path2D)
    assert len(path) == 5


def test_mask2d_cove() -> None:
    path = mask2d_cove(radius=5.0)
    assert isinstance(path, Path2D)
    assert len(path) > 5


def test_mask2d_tear() -> None:
    path = mask2d_tear(r=4.0)
    assert isinstance(path, Path2D)
    assert len(path) > 5


def test_mask2d_step() -> None:
    path = mask2d_step(width=3.0, height=4.0)
    assert isinstance(path, Path2D)
    assert len(path) == 6


def test_mask2d_groove() -> None:
    path = mask2d_groove(width=5.0, depth=3.0)
    assert isinstance(path, Path2D)
    assert len(path) == 8


def test_mask3d_roundover_reaches_every_corner_of_the_box() -> None:
    """The cutter is one r-sided block per corner, so its envelope is the whole `size` box."""
    cutter = mask3d_roundover(r=2.0, size=(10.0, 10.0, 10.0))
    _box = cutter.bounds()
    centre, size = list(_box.center), list(_box.size)
    assert centre == pytest.approx([0.0, 0.0, 0.0])
    assert size == pytest.approx([10.0, 10.0, 10.0])


@pytest.mark.parametrize("radius", [2.0, 4.0])
def test_mask3d_roundover_corner_selection_limits_the_cutter(radius: float) -> None:
    """corners=TOP leaves the bottom four corners alone: the cutter is an r-thick top slab."""
    cutter = mask3d_roundover(r=radius, size=(10.0, 10.0, 10.0), corners=Anchor.TOP)
    _box = cutter.bounds()
    centre, size = list(_box.center), list(_box.size)
    assert centre == pytest.approx([0.0, 0.0, 5.0 - radius / 2])
    assert size == pytest.approx([10.0, 10.0, radius])


def test_mask3d_roundover_rejects_an_empty_corner_set() -> None:
    with pytest.raises(ValueError, match="selected no corners"):
        mask3d_roundover(r=2.0, size=(10.0, 10.0, 10.0), corners=Anchor.NONE)


def test_mask3d_chamfer_occupies_the_same_corners_as_the_roundover() -> None:
    chamfered = mask3d_chamfer(chamfer=2.0, size=(10.0, 10.0, 10.0))
    _box = chamfered.bounds()
    centre, size = list(_box.center), list(_box.size)
    assert centre == pytest.approx([0.0, 0.0, 0.0])
    assert size == pytest.approx([10.0, 10.0, 10.0])

    _box = mask3d_chamfer(chamfer=2.0, size=(10.0, 10.0, 10.0), corners=Anchor.TOP).bounds()
    centre, size = list(_box.center), list(_box.size)
    assert centre == pytest.approx([0.0, 0.0, 4.0])
    assert size == pytest.approx([10.0, 10.0, 2.0])


def test_mask3d_chamfer_is_not_the_roundover() -> None:
    """It cuts three flat planes, not a sphere.

    The two cutters fill the same corner blocks, so `bounds()` cannot tell them apart -- but a
    chamfer contains no sphere. This is the regression test for the factory having been routed
    through `corner_profile(children=...)`, which discards `children=` and always rounds: the two
    factories emitted byte-identical programs and every test passed.
    """
    chamfered = repr(mask3d_chamfer(chamfer=2.0, size=(10.0, 10.0, 10.0)))
    rounded = repr(mask3d_roundover(r=2.0, size=(10.0, 10.0, 10.0)))
    assert "sphere(" in rounded
    assert "sphere(" not in chamfered
    assert chamfered != rounded


def test_mask3d_chamfer_rejects_a_non_positive_chamfer() -> None:
    with pytest.raises(ValueError, match="chamfer must be positive"):
        mask3d_chamfer(chamfer=0.0, size=(10.0, 10.0, 10.0))


@pytest.mark.parametrize("width", [3.0, 6.0])
def test_mask3d_groove_measures_width_depth_and_length(width: float) -> None:
    """The groove is its 2-D profile extruded along Z: width in X, depth in Y, length in Z."""
    cutter = mask3d_groove(width=width, depth=2.0, length=10.0)
    _box = cutter.bounds()
    # mask2d_groove carries a small excess past the surface so the cut clears it.
    centre, size = list(_box.center), list(_box.size)
    assert size[0] == pytest.approx(width, abs=0.05)
    assert size[1] == pytest.approx(2.0, abs=0.05)
    assert size[2] == pytest.approx(10.0)
    # The profile hangs off the y=0 surface into the material, and the extrusion is centred on Z.
    assert centre[0] == pytest.approx(0.0)
    assert centre[1] == pytest.approx(1.0, abs=0.05)
    assert centre[2] == pytest.approx(0.0)

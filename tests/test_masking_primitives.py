# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

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
from pybosl2.shapes3d.base import Bosl2Solid


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


def test_mask3d_roundover() -> None:
    cutter = mask3d_roundover(r=2.0, size=(10.0, 10.0, 10.0))
    assert isinstance(cutter, Bosl2Solid)


def test_mask3d_chamfer() -> None:
    cutter = mask3d_chamfer(chamfer=2.0, size=(10.0, 10.0, 10.0))
    assert isinstance(cutter, Bosl2Solid)


def test_mask3d_groove() -> None:
    cutter = mask3d_groove(width=3.0, depth=2.0, length=10.0)
    assert isinstance(cutter, Bosl2Solid)

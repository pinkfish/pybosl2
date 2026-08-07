# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.walls: FDM-optimised wall shapes."""

import math

import pytest

from pybosl2.parts.walls import (
    CorrugatedWall,
    NarrowingStrut,
    SparseAxis,
    SparseCuboid,
    SparseWall,
    ThinningTriangle,
    ThinningWall,
)
from pybosl2.shapes3d import Bosl2Solid


def _size(s: Bosl2Solid) -> list[float]:
    return s.bounds()[1]


def test_narrowing_strut_builds_and_height() -> None:
    s = NarrowingStrut(w=10, length=60, wall=5, angle=30).shape()
    assert isinstance(s, Bosl2Solid)
    height = 5 + 10 / 2 / math.tan(math.radians(30))
    sz = _size(s)
    assert (sz[0], sz[1]) == pytest.approx((10.0, 60.0), abs=0.05)
    assert sz[2] == pytest.approx(height, abs=0.05)


def test_sparse_wall_outer_dims() -> None:
    sz = _size(SparseWall(height=50, length=100, thick=4).shape())
    assert sz[0] == pytest.approx(4.0, abs=0.05)  # thickness
    assert sz[2] == pytest.approx(50.0, abs=0.05)  # height
    assert sz[1] == pytest.approx(100.0, abs=1.0)  # length (struts skew slightly past the ends)


def test_sparse_wall_variants_build() -> None:
    assert isinstance(SparseWall(height=40, length=60, thick=3, strut=2).shape(), Bosl2Solid)
    assert isinstance(
        SparseWall(height=50, length=100, thick=4, maxang=45, max_bridge=30).shape(),
        Bosl2Solid,
    )


@pytest.mark.parametrize(
    ("d", "exp"),
    [(SparseAxis.X, (10, 20, 30)), (SparseAxis.Y, (10, 20, 30)), (SparseAxis.Z, (10, 20, 30))],
)
def test_sparse_cuboid_clipped_to_box(d: SparseAxis, exp: tuple[int, int, int]) -> None:
    sz = _size(SparseCuboid([10, 20, 30], dir=d, strut=1).shape())
    assert tuple(round(v) for v in sz) == exp


def test_sparse_cuboid_bad_dir() -> None:
    with pytest.raises((ValueError, TypeError)):
        SparseCuboid([10, 20, 30], dir="Q").shape()


def test_corrugated_wall_dims() -> None:
    sz = _size(CorrugatedWall(height=50, length=100, thick=5).shape())
    assert tuple(round(v) for v in sz) == (5, 100, 50)


def test_thinning_wall_dims_and_defaults() -> None:
    s = ThinningWall(height=50, length=80, thick=4).shape()  # strut/wall default from thick
    assert isinstance(s, Bosl2Solid)
    assert tuple(round(v) for v in _size(s)) == (4, 80, 50)


def test_thinning_wall_trapezoidal() -> None:
    sz = _size(ThinningWall(height=50, length=[80, 50], thick=4).shape())  # type: ignore[arg-type]
    assert sz[1] == pytest.approx(80.0, abs=0.1)  # bounding length is the wider bottom


def test_thinning_triangle_centered_and_offset() -> None:
    a = ThinningTriangle(height=50, length=80, thick=4, center=True).shape()
    b = ThinningTriangle(height=50, length=80, thick=4, center=False).shape()
    assert tuple(round(v) for v in _size(a)) == (4, 80, 50)
    lo_a = a._native_bounds()[0]  # type: ignore[index]
    lo_b = b._native_bounds()[0]  # type: ignore[index]
    assert lo_b[2] == pytest.approx(0.0, abs=0.1)  # rests on z=0 when not centered
    assert lo_a[2] == pytest.approx(-25.0, abs=0.1)


def test_thinning_triangle_diagonly_builds() -> None:
    assert isinstance(ThinningTriangle(height=50, length=80, thick=4, diagonly=True).shape(), Bosl2Solid)

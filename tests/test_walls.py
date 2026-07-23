# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2.walls: FDM-optimised wall shapes."""

import math
import pytest

from bosl2.walls import Walls as W
from bosl2.shapes3d import Bosl2Solid


def _size(s):
    return s.bounds()[1]


def test_narrowing_strut_builds_and_height():
    s = W.narrowing_strut(w=10, l=60, wall=5, ang=30)
    assert isinstance(s, Bosl2Solid)
    h = 5 + 10 / 2 / math.tan(math.radians(30))
    sz = _size(s)
    assert (sz[0], sz[1]) == pytest.approx((10.0, 60.0), abs=0.05)
    assert sz[2] == pytest.approx(h, abs=0.05)


def test_sparse_wall_outer_dims():
    sz = _size(W.sparse_wall(h=50, l=100, thick=4))
    assert sz[0] == pytest.approx(4.0, abs=0.05)  # thickness
    assert sz[2] == pytest.approx(50.0, abs=0.05)  # height
    assert sz[1] == pytest.approx(
        100.0, abs=1.0
    )  # length (struts skew slightly past the ends)


def test_sparse_wall_variants_build():
    assert isinstance(W.sparse_wall(h=40, l=60, thick=3, strut=2), Bosl2Solid)
    assert isinstance(
        W.sparse_wall(h=50, l=100, thick=4, maxang=45, max_bridge=30), Bosl2Solid
    )


@pytest.mark.parametrize(
    "d,exp", [("X", (10, 20, 30)), ("Y", (10, 20, 30)), ("Z", (10, 20, 30))]
)
def test_sparse_cuboid_clipped_to_box(d, exp):
    sz = _size(W.sparse_cuboid([10, 20, 30], dir=d, strut=1))
    assert tuple(round(v) for v in sz) == exp


def test_sparse_cuboid_bad_dir():
    with pytest.raises(ValueError):
        W.sparse_cuboid([10, 20, 30], dir="Q")


def test_corrugated_wall_dims():
    sz = _size(W.corrugated_wall(h=50, l=100, thick=5))
    assert tuple(round(v) for v in sz) == (5, 100, 50)


def test_thinning_wall_dims_and_defaults():
    s = W.thinning_wall(h=50, l=80, thick=4)  # strut/wall default from thick
    assert isinstance(s, Bosl2Solid)
    assert tuple(round(v) for v in _size(s)) == (4, 80, 50)


def test_thinning_wall_trapezoidal():
    sz = _size(W.thinning_wall(h=50, l=[80, 50], thick=4))
    assert sz[1] == pytest.approx(80.0, abs=0.1)  # bounding length is the wider bottom


def test_thinning_triangle_centered_and_offset():
    a = W.thinning_triangle(h=50, l=80, thick=4, center=True)
    b = W.thinning_triangle(h=50, l=80, thick=4, center=False)
    assert tuple(round(v) for v in _size(a)) == (4, 80, 50)
    lo_a = a._native_bounds()[0]
    lo_b = b._native_bounds()[0]
    assert lo_b[2] == pytest.approx(0.0, abs=0.1)  # rests on z=0 when not centered
    assert lo_a[2] == pytest.approx(-25.0, abs=0.1)


def test_thinning_triangle_diagonly_builds():
    assert isinstance(
        W.thinning_triangle(h=50, l=80, thick=4, diagonly=True), Bosl2Solid
    )

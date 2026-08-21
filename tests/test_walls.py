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
from pybosl2.shapes3d import Bosl2Solid, cuboid


def _size(s: Bosl2Solid) -> list[float]:
    return s.bounds()[1]


def test_narrowing_strut_builds_and_height() -> None:
    s = NarrowingStrut(w=10, length=60, wall=5, angle=30).shape
    assert isinstance(s, Bosl2Solid)
    height = 5 + 10 / 2 / math.tan(math.radians(30))
    sz = _size(s)
    assert (sz[0], sz[1]) == pytest.approx((10.0, 60.0), abs=0.05)
    assert sz[2] == pytest.approx(height, abs=0.05)


def test_sparse_wall_outer_dims() -> None:
    sz = _size(SparseWall(height=50, length=100, thick=4).shape)
    assert sz[0] == pytest.approx(4.0, abs=0.05)  # thickness
    assert sz[2] == pytest.approx(50.0, abs=0.05)  # height
    assert sz[1] == pytest.approx(100.0, abs=1.0)  # length (struts skew slightly past the ends)


def _ribs(s: Bosl2Solid) -> int:
    """How many struts the wall is built from: one extruded polygon each."""
    return repr(s).count("polygon(")


@pytest.mark.parametrize(
    ("kw", "ribs"),
    [
        ({}, 12),  # the default lattice
        ({"maxang": 20}, 16),  # a tighter overhang limit needs more, shorter struts
        ({"maxang": 45, "max_bridge": 30}, 10),  # a looser one spans further with fewer
        ({"strut": 2}, 14),  # thinner struts must be packed closer to keep the bridges short
    ],
)
def test_sparse_wall_lattice_responds_to_its_limits(kw: dict[str, object], ribs: int) -> None:
    """Every variant fills the same envelope; what changes is the strut count inside it."""
    wall = SparseWall(height=50, length=100, thick=4, **kw).shape  # type: ignore[arg-type]
    size = _size(wall)
    assert size[0] == pytest.approx(4.0, abs=0.05)  # thickness
    assert size[2] == pytest.approx(50.0, abs=0.05)  # height
    assert size[1] == pytest.approx(100.0, abs=1.5)  # length, struts skewing slightly past the ends
    assert _ribs(wall) == ribs


@pytest.mark.parametrize(
    ("d", "exp"),
    [(SparseAxis.X, (10, 20, 30)), (SparseAxis.Y, (10, 20, 30)), (SparseAxis.Z, (10, 20, 30))],
)
def test_sparse_cuboid_clipped_to_box(d: SparseAxis, exp: tuple[int, int, int]) -> None:
    sz = _size(SparseCuboid([10, 20, 30], dir=d, strut=1).shape)
    assert tuple(round(v) for v in sz) == exp


def test_sparse_cuboid_bad_dir() -> None:
    with pytest.raises((ValueError, TypeError)):
        _ = SparseCuboid([10, 20, 30], dir="Q").shape


def test_corrugated_wall_dims() -> None:
    sz = _size(CorrugatedWall(height=50, length=100, thick=5).shape)
    assert tuple(round(v) for v in sz) == (5, 100, 50)


def test_thinning_wall_dims_and_defaults() -> None:
    s = ThinningWall(height=50, length=80, thick=4).shape  # strut/wall default from thick
    assert isinstance(s, Bosl2Solid)
    assert tuple(round(v) for v in _size(s)) == (4, 80, 50)


def test_thinning_wall_trapezoidal() -> None:
    sz = _size(ThinningWall(height=50, length=[80, 50], thick=4).shape)  # type: ignore[arg-type]
    assert sz[1] == pytest.approx(80.0, abs=0.1)  # bounding length is the wider bottom


def test_thinning_triangle_centered_and_offset() -> None:
    a = ThinningTriangle(height=50, length=80, thick=4, center=True).shape
    b = ThinningTriangle(height=50, length=80, thick=4, center=False).shape
    assert tuple(round(v) for v in _size(a)) == (4, 80, 50)
    lo_a = a._native_bounds()[0]  # type: ignore[index]
    lo_b = b._native_bounds()[0]  # type: ignore[index]
    assert lo_b[2] == pytest.approx(0.0, abs=0.1)  # rests on z=0 when not centered
    assert lo_a[2] == pytest.approx(-25.0, abs=0.1)


def _thickness_at(s: Bosl2Solid, y: float, z: float) -> float | None:
    """Thickness of the wall at (y, z), or None where there is no material at all."""
    bounds = (s & cuboid([10, 0.4, 0.4]).translate([0, y, z]))._native_bounds()  # type: ignore[misc]
    return None if bounds is None else float(bounds[1][0])


def test_thinning_triangle_diagonly_keeps_only_the_diagonal_rim() -> None:
    """diagonly= drops the thickened rim from the two straight edges, leaving the hypotenuse.

    Both forms have the same triangular outline and the same 4mm bounding box, so this measures
    the wall thickness at the edges instead: full keeps 4mm all the way round, diagonly thins the
    upright and the base back to the 3mm web.
    """
    full = ThinningTriangle(height=50, length=80, thick=4).shape
    diag = ThinningTriangle(height=50, length=80, thick=4, diagonly=True).shape
    assert _size(diag) == pytest.approx(_size(full), abs=0.05)

    for y, z in ((-38.0, 0.0), (0.0, -23.0)):  # upright edge, base edge
        assert _thickness_at(full, y, z) == pytest.approx(4.0, abs=0.05)
        assert _thickness_at(diag, y, z) == pytest.approx(3.0, abs=0.05)

    # The diagonal itself is thickened in both, and the thin web between them is untouched.
    assert _thickness_at(full, -38.0, 23.0) == pytest.approx(4.0, abs=0.05)
    assert _thickness_at(diag, -38.0, 23.0) == pytest.approx(4.0, abs=0.05)
    assert _thickness_at(diag, -30.0, -10.0) == pytest.approx(3.0, abs=0.05)

    # Outside the triangle there is nothing, either way.
    assert _thickness_at(full, 35.0, 20.0) is None
    assert _thickness_at(diag, 35.0, 20.0) is None

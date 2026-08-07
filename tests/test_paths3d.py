# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.paths.Path3D: the 3-D path object -- construction, measurement, the 3-D
transforms (move / directional / scale / rotate / mirror), resampling/cutting, and the drop-to-2-D
conversion. The numeric kernels are shared with Path2D (and pinned to real BOSL2 elsewhere); these
tests focus on the 3-D object surface."""

import math

import numpy as np
import pytest

from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D

SQUARE_LOOP = [[0, 0, 0], [10, 0, 0], [10, 10, 5], [0, 10, 5]]


def test_construction_requires_3d_points() -> None:
    p = Path3D(SQUARE_LOOP, closed=True)
    assert isinstance(p, Path3D)
    assert len(p) == 4
    np.testing.assert_array_equal(p[0], [0.0, 0.0, 0.0])
    with pytest.raises(AssertionError):
        Path3D([[0, 0], [1, 1]])  # 2-D points rejected
    assert p.array.shape == (4, 3)
    assert p.closed is True
    np.testing.assert_array_equal(p[-1], [0.0, 10.0, 5.0])
    assert p.perimeter() == pytest.approx(42.3606797749979, abs=1e-9)
    np.testing.assert_allclose(p.segment_lengths(), [10.0, 11.180339887498949, 10.0, 11.180339887498949], atol=1e-9)


def test_closed_flag_and_repr() -> None:
    assert Path3D(SQUARE_LOOP).closed is False  # open by default, as in BOSL2
    assert Path3D(SQUARE_LOOP, closed=True).closed is True
    assert Path3D(SQUARE_LOOP, closed=False).closed is False
    assert "Path3D" in repr(Path3D(SQUARE_LOOP))
    assert repr(Path3D(SQUARE_LOOP, closed=True)) == "Path3D(4 pts, closed=True)"
    assert repr(Path3D(SQUARE_LOOP, closed=False)) == "Path3D(4 pts, closed=False)"
    assert len(Path3D(SQUARE_LOOP, closed=False)) == 4


def test_array_and_bounds() -> None:
    p = Path3D(SQUARE_LOOP, closed=True)
    assert p.array.shape == (4, 3)
    bounds = p.bounds()
    assert bounds.min_x == 0
    assert bounds.min_y == 0
    assert bounds.min_z == 0
    assert bounds.max_x == 10
    assert bounds.max_y == 10
    assert bounds.max_z == 5
    assert bounds.width == 10
    assert bounds.length == 10
    assert bounds.height == 5
    assert len(p) == 4
    np.testing.assert_array_equal(p[0], [0.0, 0.0, 0.0])
    np.testing.assert_array_equal(p[2], [10.0, 10.0, 5.0])
    assert p.perimeter() == pytest.approx(42.3606797749979, abs=1e-9)


def test_perimeter_open_vs_closed() -> None:
    line = Path3D([[0, 0, 0], [0, 0, 10], [0, 0, 30]], closed=False)
    assert math.isclose(line.perimeter(), 30.0, abs_tol=1e-9)
    tri = Path3D([[0, 0, 0], [3, 0, 0], [3, 4, 0]], closed=True)
    assert math.isclose(tri.perimeter(), 3 + 4 + 5, abs_tol=1e-9)  # closed adds the 5 hypotenuse
    assert len(line) == 3
    assert len(tri) == 3
    np.testing.assert_allclose(line.segment_lengths(), [10.0, 20.0], atol=1e-9)
    np.testing.assert_allclose(tri.segment_lengths(), [3.0, 4.0, 5.0], atol=1e-9)
    np.testing.assert_array_equal(line[-1], [0.0, 0.0, 30.0])


def test_segment_lengths_and_fractions() -> None:
    line = Path3D([[0, 0, 0], [0, 0, 10], [0, 0, 40]], closed=False)
    np.testing.assert_allclose(line.segment_lengths(), [10, 30], atol=1e-9)
    np.testing.assert_allclose(line.length_fractions(), [0, 0.25, 1.0], atol=1e-9)
    assert len(line) == 3
    assert line.perimeter() == pytest.approx(40.0, abs=1e-9)
    np.testing.assert_array_equal(line[0], [0.0, 0.0, 0.0])
    np.testing.assert_array_equal(line[1], [0.0, 0.0, 10.0])
    np.testing.assert_array_equal(line[2], [0.0, 0.0, 40.0])
    assert line.closed is False
    assert line.array.shape == (3, 3)


def test_translate_and_directional_moves() -> None:
    p = Path3D([[0, 0, 0]], closed=False)
    np.testing.assert_allclose(p.translate([1, 2, 3])[0], [1, 2, 3], atol=1e-9)
    np.testing.assert_allclose(p.move([1, 2, 3])[0], [1, 2, 3], atol=1e-9)
    np.testing.assert_allclose(p.right(5)[0], [5, 0, 0], atol=1e-9)
    np.testing.assert_allclose(p.left(5)[0], [-5, 0, 0], atol=1e-9)
    np.testing.assert_allclose(p.back(5)[0], [0, 5, 0], atol=1e-9)
    np.testing.assert_allclose(p.forward(5)[0], [0, -5, 0], atol=1e-9)
    np.testing.assert_allclose(p.up(5)[0], [0, 0, 5], atol=1e-9)
    np.testing.assert_allclose(p.down(5)[0], [0, 0, -5], atol=1e-9)
    assert len(p) == 1
    assert p.closed is False
    np.testing.assert_array_equal(p[0], [0.0, 0.0, 0.0])


def test_scale_scalar_and_vector() -> None:
    p = Path3D([[1, 2, 3]], closed=False)
    np.testing.assert_allclose(p.scale(2)[0], [2, 4, 6], atol=1e-9)
    np.testing.assert_allclose(p.scale([1, 0, 3])[0], [1, 0, 9], atol=1e-9)
    assert len(p) == 1
    assert p.array.shape == (1, 3)
    np.testing.assert_array_equal(p[0], [1.0, 2.0, 3.0])


def test_rotate_about_z_axis_and_euler() -> None:
    p = Path3D([[1, 0, 0]], closed=False)
    np.testing.assert_allclose(p.rotate(90)[0], [0, 1, 0], atol=1e-9)  # scalar -> Z
    np.testing.assert_allclose(p.rotate(90, [1, 0, 0])[0], [1, 0, 0], atol=1e-9)  # about its own axis
    np.testing.assert_allclose(p.rotate([0, 0, 90])[0], [0, 1, 0], atol=1e-9)  # euler Z
    z_up = Path3D([[0, 0, 1]], closed=False)
    np.testing.assert_allclose(z_up.rotate([90, 0, 0])[0], [0, -1, 0], atol=1e-9)  # euler X: +Z -> -Y
    assert len(p) == 1
    assert len(z_up) == 1
    assert p.closed is False
    np.testing.assert_array_equal(p[0], [1.0, 0.0, 0.0])
    np.testing.assert_array_equal(z_up[0], [0.0, 0.0, 1.0])


def test_mirror_across_plane() -> None:
    p = Path3D([[1, 2, 3]], closed=False)
    np.testing.assert_allclose(p.mirror([0, 0, 1])[0], [1, 2, -3], atol=1e-9)
    np.testing.assert_allclose(p.mirror([1, 0, 0])[0], [-1, 2, 3], atol=1e-9)
    assert len(p) == 1
    np.testing.assert_array_equal(p[0], [1.0, 2.0, 3.0])
    np.testing.assert_allclose(p.mirror([0, 1, 0])[0], [1, -2, 3], atol=1e-9)


def test_reverse_close_cleanup_dedup() -> None:
    p = Path3D([[0, 0, 0], [1, 0, 0], [1, 1, 1]], closed=False)
    np.testing.assert_allclose(p.reverse()[0], [1, 1, 1], atol=1e-9)
    closed = p.close()
    np.testing.assert_allclose(closed[-1], [0, 0, 0], atol=1e-9)  # start point appended
    assert len(closed.cleanup()) == 3  # duplicate closing point dropped
    dd = Path3D([[0, 0, 0], [0, 0, 0], [1, 0, 0]], closed=False).deduplicated()
    assert len(dd) == 2
    assert len(p.reverse()) == 3
    np.testing.assert_allclose(p.reverse()[-1], [0, 0, 0], atol=1e-9)
    assert len(closed) == 4
    np.testing.assert_allclose(closed[0], [0, 0, 0], atol=1e-9)
    np.testing.assert_array_equal(dd[0], [0.0, 0.0, 0.0])
    np.testing.assert_array_equal(dd[1], [1.0, 0.0, 0.0])
    np.testing.assert_allclose(dd.array, [[0, 0, 0], [1, 0, 0]], atol=1e-9)


def test_resample_and_subdivide_keep_3d() -> None:
    p = Path3D([[0, 0, 0], [0, 0, 30]], closed=False)
    radius = p.resample(num_copies=7)
    assert isinstance(radius, Path3D)
    assert len(radius) == 7
    assert radius.array.shape[1] == 3
    s = p.subdivide(num_copies=4)
    assert isinstance(s, Path3D)
    assert s.array.shape[1] == 3
    np.testing.assert_allclose(
        radius.array,
        [
            [0, 0, 0],
            [0, 0, 5],
            [0, 0, 10],
            [0, 0, 15],
            [0, 0, 20],
            [0, 0, 25],
            [0, 0, 30],
        ],
        atol=1e-9,
    )
    np.testing.assert_allclose(
        s.array,
        [
            [0, 0, 0],
            [0, 0, 10],
            [0, 0, 20],
            [0, 0, 30],
        ],
        atol=1e-9,
    )
    assert len(s) == 4
    assert radius.closed is False
    assert radius.perimeter() == pytest.approx(30.0, abs=1e-9)


def test_cut_returns_path3d_subpaths() -> None:
    line = Path3D([[0, 0, 0], [0, 0, 40]], closed=False)
    parts = line.cut([10.0])
    assert len(parts) == 2
    assert all(isinstance(pt, Path3D) for pt in parts)
    assert len(parts[0]) == 2
    assert len(parts[1]) == 2
    np.testing.assert_allclose(parts[0].array, [[0, 0, 0], [0, 0, 10]], atol=1e-9)
    np.testing.assert_allclose(parts[1].array, [[0, 0, 10], [0, 0, 40]], atol=1e-9)
    assert parts[0].closed is False
    assert parts[1].closed is False
    assert parts[0].perimeter() == pytest.approx(10.0, abs=1e-9)
    assert parts[1].perimeter() == pytest.approx(30.0, abs=1e-9)


def test_tangents_normals_curvature_torsion_shapes() -> None:
    p = Path3D(
        [[math.cos(t), math.sin(t), t / 3] for t in np.linspace(0, 2 * math.pi, 24)],
        closed=False,
    )
    assert len(p.tangents()) == 24
    assert len(p.normals()) == 24
    assert p.curvature().shape == (24,)
    assert p.torsion().shape == (24,)
    assert len(p) == 24
    c = p.curvature()
    assert float(np.min(c)) == pytest.approx(0.8679411357989224, abs=1e-9)
    assert float(np.max(c)) == pytest.approx(0.9146926996719048, abs=1e-9)
    assert float(np.mean(c)) == pytest.approx(0.9107967360158229, abs=1e-9)
    tor = p.torsion()
    assert float(np.min(tor)) == pytest.approx(0.3029990360512322, abs=1e-9)
    assert float(np.max(tor)) == pytest.approx(0.31907479844666, abs=1e-9)
    tangents = p.tangents()
    np.testing.assert_allclose(
        [float(tangents[0].x), float(tangents[0].y), float(tangents[0].z)],
        [-0.004673336467025875, 0.950898585144923, 0.30946734996708364],
        atol=1e-9,
    )
    normals = p.normals()
    np.testing.assert_allclose(
        [float(normals[0].x), float(normals[0].y), float(normals[0].z)],
        [-0.9962600657729389, -0.031128418529578327, 0.08060336783253526],
        atol=1e-9,
    )


# -- degenerate paths ---------------------------------------------------------------------
#
# The 3-D counterpart of test_paths.py's degenerate block: a path too short to have the thing
# being measured MEASURES ZERO rather than raising IndexError out of the numpy derivatives.

DEGENERATE_3D = [Path3D(), Path3D([[1.0, 2.0, 3.0]]), Path3D([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])]


@pytest.mark.parametrize("path", DEGENERATE_3D)
def test_curvature_and_torsion_need_three_points(path: Path3D) -> None:
    for measured in (path.curvature(), path.torsion()):
        assert measured.shape == (len(path),)
        assert not np.any(measured)


@pytest.mark.parametrize("path", [Path3D(), Path3D([[1.0, 2.0, 3.0]])])
def test_short_path_tangents_are_one_per_point(path: Path3D) -> None:
    assert len(path.tangents()) == len(path)
    assert path.tangent_array().shape == (len(path), 3)


def test_single_point_tangent_falls_back_to_x() -> None:
    # One point gives nothing to differentiate, so the tangent is +x by convention.
    np.testing.assert_allclose(list(Path3D([[1.0, 2.0, 3.0]]).tangents()[0]), [1.0, 0.0, 0.0])


def test_closest_point() -> None:
    from pybosl2.points import Point

    line = Path3D([[0, 0, 0], [0, 0, 10]], closed=False)
    pt = line.closest_point([1, 0, 5])
    assert isinstance(pt, Point)
    assert not pt.is_2d
    assert pt.z is not None
    np.testing.assert_allclose([pt.x, pt.y, pt.z], [0, 0, 5], atol=1e-9)
    assert len(line) == 2
    assert line.perimeter() == pytest.approx(10.0, abs=1e-9)
    pt_end = line.closest_point([0, 0, 0])
    np.testing.assert_allclose([pt_end.x, pt_end.y, pt_end.z], [0, 0, 0], atol=1e-9)
    pt_end2 = line.closest_point([0, 0, 10])
    np.testing.assert_allclose([pt_end2.x, pt_end2.y, pt_end2.z], [0, 0, 10], atol=1e-9)


def test_path2d_drops_z() -> None:
    p = Path3D([[1, 2, 9], [3, 4, 8]], closed=False)
    flat = p.path2d()
    assert isinstance(flat, Path2D)
    np.testing.assert_allclose(flat, [[1, 2], [3, 4]], atol=1e-9)
    assert flat.closed is False
    assert len(flat) == 2
    np.testing.assert_array_equal(flat[0], [1.0, 2.0])
    np.testing.assert_array_equal(flat[1], [3.0, 4.0])
    assert flat.array.shape == (2, 2)


def test_stroke_and_dashed_build() -> None:
    from pybosl2.shapes3d import Bosl2Solid

    p = Path3D([[0, 0, 0], [20, 0, 0], [20, 20, 10]], closed=False)
    assert p.stroke(width=3) is not None
    assert isinstance(p.dashed_stroke(dashpat=[5, 5]), Bosl2Solid)
    assert len(p) == 3
    assert p.perimeter() == pytest.approx(42.3606797749979, abs=1e-9)
    np.testing.assert_array_equal(p[0], [0.0, 0.0, 0.0])
    np.testing.assert_array_equal(p[-1], [20.0, 20.0, 10.0])

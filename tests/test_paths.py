# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/paths.py: the Path list-subclass and its private static kernels."""

import math

import numpy as np
import pytest

from pybosl2.paths import Path

SQUARE = [[0, 0], [80, 0], [80, 60], [0, 60]]
UNIT = [[0, 0], [10, 0], [10, 10], [0, 10]]


# -- construction / drop-in list behaviour ------------------------------------------------


def test_is_a_list_of_plain_floats():
    p = Path(np.asarray(SQUARE, dtype=float))
    assert isinstance(p, Path)
    assert p.to_list == [[float(x), float(y)] for x, y in SQUARE]


def test_rejects_non_xy_points():
    with pytest.raises(AssertionError):
        Path([[0, 0, 0], [1, 1, 1]])


def test_empty_path():
    assert len(Path()) == 0


def test_array_property():
    assert Path(SQUARE).array.shape == (4, 2)


# -- measurement --------------------------------------------------------------------------


def test_bounds_width_length():
    p = Path(SQUARE)
    bounds = p.bounds()
    assert bounds.min_x == 0
    assert bounds.min_y == 0
    assert bounds.max_x == 80
    assert bounds.max_y == 60
    assert bounds.width == 80
    assert bounds.length == 60


def test_area():
    assert Path(SQUARE).area() == 4800
    assert Path(SQUARE).area(signed=True) == 4800  # CCW is positive
    assert Path(list(reversed(SQUARE))).area(signed=True) == -4800


def test_is_clockwise():
    assert not Path(SQUARE).is_clockwise()
    assert Path(list(reversed(SQUARE))).is_clockwise()


def test_perimeter_closed_vs_open():
    assert Path(SQUARE).perimeter() == 280
    assert Path(SQUARE, closed=False).perimeter() == 220  # three segments, no closing edge


def test_segment_lengths_and_fractions():
    p = Path(SQUARE)
    np.testing.assert_allclose(p.segment_lengths(), [80, 60, 80, 60])
    fr = p.length_fractions()
    assert math.isclose(fr[0], 0.0)
    assert math.isclose(fr[-1], 1.0)


def test_is_closed_property():
    assert Path([[0, 0], [10, 0], [10, 10], [0, 0]]).is_closed is True
    assert Path(SQUARE).is_closed is False  # endpoints differ


def test_contains_only_when_closed():
    p = Path(SQUARE)
    assert p.contains([40, 30]) is True
    assert p.contains([100, 100]) is False
    assert Path(SQUARE, closed=False).contains([40, 30]) is False


def test_is_simple():
    assert Path(SQUARE).is_simple()
    figure8 = [[0, 0], [2, 2], [0, 2], [2, 0]]
    assert not Path(figure8).is_simple()


def test_closest_point():
    from pybosl2.points import Point

    pt = Path(SQUARE).closest_point([40, -5])
    assert isinstance(pt, Point)
    assert pt.is_2d
    assert pt.z is None
    np.testing.assert_allclose([pt.x, pt.y], [40, 0], atol=1e-9)


# -- tangents / normals / curvature -------------------------------------------------------


def test_tangents_are_unit():
    t = Path(SQUARE).tangents()
    np.testing.assert_allclose(np.linalg.norm(t, axis=1), np.ones(4), atol=1e-9)


def test_normals_perpendicular_to_tangents():
    p = Path(SQUARE)
    t, sides = p.tangents(), p.normals()
    for i in range(len(p)):
        assert abs(float(np.dot(t[i], sides[i]))) < 1e-9


def test_curvature_of_straightish_polygon():
    c = Path(SQUARE).curvature()
    assert c.shape == (4,)


# -- derived paths ------------------------------------------------------------------------


def test_offset_shrinks_area():
    assert math.isclose(Path(UNIT).offset(radius=-1).area(), 64.0, abs_tol=1e-6)
    assert math.isclose(Path(UNIT).offset(delta=-1).area(), 64.0, abs_tol=1e-6)


def test_offset_returns_path():
    assert isinstance(Path(UNIT).offset(radius=-1), Path)


def test_offset_needs_exactly_one_of_r_delta():
    with pytest.raises(AssertionError):
        Path(UNIT).offset()
    with pytest.raises(AssertionError):
        Path(UNIT).offset(radius=1, delta=1)


def test_round_corners_inserts_points():
    out = Path(UNIT).round_corners(radius=2)
    assert isinstance(out, Path)
    assert len(out) > len(UNIT)


def test_merge_collinear_drops_midpoints():
    p = Path([[0, 0], [5, 0], [10, 0], [10, 10], [0, 10]])
    assert len(p.merge_collinear()) == 4


def test_deduplicated():
    p = Path([[0, 0], [0, 0], [1, 0], [1, 1]])
    assert len(p.deduplicated()) == 3


def test_reverse():
    p = Path(SQUARE).reverse()
    np.testing.assert_allclose(p[0], SQUARE[-1])


def test_close_and_cleanup():
    open_sq = Path(SQUARE)
    closed = open_sq.close()
    np.testing.assert_allclose(closed[-1], closed[0])
    assert len(closed) == 5
    np.testing.assert_allclose(closed.cleanup(), open_sq)


def test_subdivide_adds_points():
    out = Path(SQUARE).subdivide(sides=8)
    assert len(out) == 8


def test_resample_to_n_points():
    out = Path(SQUARE).resample(sides=12)
    assert len(out) == 12


def test_cut_splits_into_subpaths():
    parts = Path(SQUARE).cut([100, 200])
    assert len(parts) == 3
    assert all(isinstance(p, Path) for p in parts)


def test_cut_points_along_open_path():
    pts = Path([[0, 0], [10, 0]], closed=False).cut_points([5])
    np.testing.assert_allclose(pts[0][0], [5, 0], atol=1e-9)


# -- transforms ---------------------------------------------------------------------------


def test_translate_and_move_alias():
    np.testing.assert_allclose(Path(UNIT).translate([1, 2])[0], [1, 2])
    np.testing.assert_allclose(Path(UNIT).move([1, 2])[0], [1, 2])


def test_directional_moves():
    p = Path([[1, 1]], closed=False)
    np.testing.assert_allclose(p.right(5)[0], [6, 1])
    np.testing.assert_allclose(p.left(5)[0], [-4, 1])
    np.testing.assert_allclose(p.back(5)[0], [1, 6])
    np.testing.assert_allclose(p.forward(5)[0], [1, -4])
    np.testing.assert_allclose(p.fwd(5)[0], [1, -4])


def test_rot_and_rotate_alias():
    np.testing.assert_allclose(Path([[1, 0]], closed=False).rot(90)[0], [0, 1], atol=1e-9)
    np.testing.assert_allclose(Path([[1, 0]], closed=False).rotate(90)[0], [0, 1], atol=1e-9)


def test_mirror_across_y_axis():
    np.testing.assert_allclose(Path([[3, 2]], closed=False).mirror([1, 0])[0], [-3, 2], atol=1e-9)


def test_yflip():
    np.testing.assert_allclose(Path([[3, 2]], closed=False).yflip()[0], [3, -2], atol=1e-9)


# -- conversion ---------------------------------------------------------------------------


def test_to_region():
    from pybosl2.regions import Region

    radius = Path(SQUARE).to_region()
    assert isinstance(radius, Region)
    assert len(radius) == 1


def test_polygon_and_geometry_use_mock():
    assert Path(SQUARE).polygon() is not None
    assert Path(SQUARE).geometry() is not None


# -- splitting ----------------------------------------------------------------------------


def test_polygon_parts_of_simple_square():
    parts = Path(SQUARE).polygon_parts()
    assert len(parts) == 1
    assert all(isinstance(p, Path) for p in parts)


def test_split_at_self_crossings():
    figure8 = [[0, 0], [2, 2], [0, 2], [2, 0]]
    subs = Path(figure8).split_at_self_crossings()
    assert len(subs) >= 2


# -- private static kernels ---------------------------------------------------------------


def test_select_circular_index():
    assert Path._select([10, 20, 30], 4) == 20  # 4 % 3
    assert Path._select([10, 20, 30], -1) == 30
    assert Path._select([10, 20, 30], [0, 3, -1]) == [10, 10, 30]


def test_select_circular_slice_wraps():
    assert Path._select([0, 1, 2, 3], 2, 0) == [2, 3, 0]
    assert Path._select([0, 1, 2, 3], 1, 2) == [1, 2]


def test_slice_inclusive_clamped():
    assert Path._slice([0, 1, 2, 3, 4], 1, 3) == [1, 2, 3]
    assert Path._slice([0, 1, 2, 3, 4], 0, -1) == [0, 1, 2, 3, 4]
    assert Path._slice([0, 1, 2], 2, 0) == []


def test_pair():
    assert Path._pair([1, 2, 3]) == [(1, 2), (2, 3)]
    assert Path._pair([1, 2, 3], wrap=True) == [(1, 2), (2, 3), (3, 1)]
    assert Path._pair([1]) == []


def test_list_head_and_tail():
    assert Path._list_head([0, 1, 2, 3], 1) == [0, 1]
    assert Path._list_tail([0, 1, 2, 3], 2) == [2, 3]


def test_repeat():
    assert Path._repeat(5, 3) == [5, 5, 5]


def test_deduplicate_static():
    assert Path._deduplicate([[0, 0], [0, 0], [1, 1]]) == [[0, 0], [1, 1]]


def test_polygon_area_static():
    assert Path._polygon_area(SQUARE) == 4800
    assert Path._polygon_area([[0, 0], [1, 0]]) == 0  # too few points


def test_point_in_polygon_static():
    assert Path._point_in_polygon([40, 30], SQUARE) == 1
    assert Path._point_in_polygon([100, 100], SQUARE) == -1
    assert Path._point_in_polygon([0, 30], SQUARE) == 0  # on the boundary


def test_path_length_accepts_3d():
    from pybosl2.paths import Path3D

    assert math.isclose(Path3D([[0, 0, 0], [0, 0, 3], [0, 4, 3]], closed=False).total_length(), 7.0)


def test_shapely_backed_path_methods():
    # contains
    p = Path(SQUARE)
    assert p.contains([40, 30]) is True
    assert p.contains([100, 100]) is False

    # area
    assert math.isclose(p.area(), 4800.0)
    assert math.isclose(p.area(signed=True), 4800.0)

    # clockwise vs counter-clockwise signed area
    cw_p = Path([[0, 60], [80, 60], [80, 0], [0, 0]])
    assert cw_p.is_clockwise() is True
    assert math.isclose(cw_p.area(signed=True), -4800.0)

    # is_simple
    assert p.is_simple() is True
    figure8 = Path([[0, 0], [2, 2], [0, 2], [2, 0]])
    assert figure8.is_simple() is False


# -- Minkowski sum -----------------------------------------------------------------------------


def test_minkowski_square_and_square():
    a = Path([[0, 0], [20, 0], [20, 20], [0, 20]])
    b = Path([[0, 0], [10, 0], [10, 10], [0, 10]])
    result = a.minkowski_sum(b)
    assert result.closed
    assert len(result) >= 3


def test_minkowski_square_and_circle():
    a = Path([[0, 0], [20, 0], [20, 10], [0, 10]])
    b = Path.circle2d(radius=5, fn=32)
    result = a.minkowski_sum(b)
    assert result.closed
    assert len(result) >= 3


def test_circle2d_default():
    c = Path.circle2d()
    assert c.closed
    assert len(c) == 64


def test_circle2d_radius_and_fn():
    c = Path.circle2d(radius=20, fn=8)
    assert c.closed
    assert len(c) == 8
    areas = [np.linalg.norm(np.asarray(p)) for p in c]
    np.testing.assert_allclose(areas, [20.0] * 8, atol=1e-9)


def test_ellipse2d():
    e = Path.ellipse2d(rx=20, ry=10, fn=32)
    assert e.closed
    assert len(e) == 32


def test_ellipse2d_aspect():
    e = Path.ellipse2d(rx=30, ry=10, fn=4)
    pts = np.asarray(e._points)
    assert abs(pts[0, 0]) == pytest.approx(30.0)  # first point at (30, 0)
    assert abs(pts[1, 1]) == pytest.approx(10.0)  # second point at (0, 10)


def test_minkowski_requires_closed():
    a = Path([[0, 0], [20, 0], [20, 10]], closed=False)
    b = Path([[0, 0], [5, 0], [5, 5], [0, 5]])
    with pytest.raises(ValueError, match="closed"):
        a.minkowski_sum(b)


def test_minkowski_requires_closed_other():
    a = Path([[0, 0], [20, 0], [20, 10], [0, 10]])
    b = Path([[0, 0], [5, 0], [5, 5]], closed=False)
    with pytest.raises(ValueError, match="closed"):
        a.minkowski_sum(b)


def test_minkowski_sum_circle_dilates():
    square = Path([[0, 0], [20, 0], [20, 10], [0, 10]])
    result = square.minkowski_sum_circle(radius=5)
    assert result.closed
    assert len(result) >= 3
    assert result.area() > square.area()


def test_minkowski_sum_circle_erodes():
    square = Path([[0, 0], [20, 0], [20, 10], [0, 10]])
    result = square.minkowski_sum_circle(radius=-2)
    assert result.closed
    assert result.area() < square.area()


def test_minkowski_sum_circle_requires_closed():
    open_path = Path([[0, 0], [20, 0], [20, 10]], closed=False)
    with pytest.raises(ValueError, match="closed"):
        open_path.minkowski_sum_circle(radius=5)


# -- Boolean operations on Path ----------------------------------------------------------------


def test_union_two_squares():
    a = Path([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path([[20, 0], [50, 0], [50, 30], [20, 30]])
    result = a.union(b)
    assert result.closed
    assert len(result) >= 4
    assert result.area() > 900  # larger than either square alone


def test_intersection_two_squares():
    a = Path([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path([[20, 0], [50, 0], [50, 30], [20, 30]])
    result = a.intersection(b)
    assert result.closed
    assert len(result) >= 4
    assert result.area() == pytest.approx(300.0)  # 10×30 strip


def test_difference_square_minus_square():
    a = Path([[0, 0], [40, 0], [40, 30], [0, 30]])
    b = Path([[10, 10], [30, 10], [30, 20], [10, 20]])
    result = a.difference(b)
    assert result.closed
    # Path doesn't support holes; difference returns the outer outline
    assert result.area() == pytest.approx(1200.0)


def test_symmetric_difference_two_squares():
    a = Path([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path([[20, 0], [50, 0], [50, 30], [20, 30]])
    result = a.symmetric_difference(b)
    assert result.closed


def test_union_operator():
    a = Path([[0, 0], [20, 0], [20, 20], [0, 20]])
    b = Path([[10, 0], [30, 0], [30, 20], [10, 20]])
    result = a | b
    assert result.closed
    assert len(result) >= 4


def test_intersection_operator():
    a = Path([[0, 0], [20, 0], [20, 20], [0, 20]])
    b = Path([[10, 0], [30, 0], [30, 20], [10, 20]])
    result = a & b
    assert result.closed


def test_difference_operator():
    a = Path([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path([[10, 10], [20, 10], [20, 20], [10, 20]])
    result = a - b
    assert result.closed


def test_xor_operator():
    a = Path([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path([[20, 0], [50, 0], [50, 30], [20, 30]])
    result = a ^ b
    assert result.closed


def test_union_requires_closed():
    a = Path([[0, 0], [20, 0], [20, 10], [0, 10]])
    b = Path([[10, 0], [30, 0], [30, 10]], closed=False)
    with pytest.raises(ValueError, match="closed"):
        a.union(b)


def test_difference_requires_closed():
    a = Path([[0, 0], [20, 0], [20, 10]], closed=False)
    b = Path([[5, 0], [15, 0], [15, 10], [5, 10]])
    with pytest.raises(ValueError, match="closed"):
        a.difference(b)


def test_intersection_empty_returns_empty():
    a = Path([[0, 0], [10, 0], [10, 10], [0, 10]])
    b = Path([[50, 0], [60, 0], [60, 10], [50, 10]])
    result = a.intersection(b)
    assert len(result) == 0

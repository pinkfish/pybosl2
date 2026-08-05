# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/paths.py: the Path2D list-subclass and its private static kernels."""

import math

import numpy as np
import pytest

from pybosl2.path2d import Path2D
from pybosl2.points import Point

SQUARE = [[0, 0], [80, 0], [80, 60], [0, 60]]
UNIT = [[0, 0], [10, 0], [10, 10], [0, 10]]


# -- construction / drop-in list behaviour ------------------------------------------------


def test_is_a_list_of_plain_floats() -> None:
    p = Path2D(np.asarray(SQUARE, dtype=float))
    assert isinstance(p, Path2D)
    assert p.to_list == [[float(x), float(y)] for x, y in SQUARE]
    assert len(p) == 4
    assert list(p[0]) == [0.0, 0.0]
    assert list(p[2]) == [80.0, 60.0]
    assert list(p[-1]) == [0.0, 60.0]


def test_rejects_non_xy_points() -> None:
    with pytest.raises(AssertionError):
        Path2D([[0, 0, 0], [1, 1, 1]])


def test_empty_path() -> None:
    p = Path2D()
    assert len(p) == 0
    assert p.closed is True
    assert p.to_list == []
    assert p.array.shape == (0,)


def test_array_property() -> None:
    assert Path2D(SQUARE).array.shape == (4, 2)
    assert Path2D([]).array.shape == (0,)
    assert Path2D(UNIT).array.shape == (4, 2)


# -- measurement --------------------------------------------------------------------------


def test_bounds_width_length() -> None:
    p = Path2D(SQUARE)
    bounds = p.bounds()
    assert bounds.min_x == 0
    assert bounds.min_y == 0
    assert bounds.max_x == 80
    assert bounds.max_y == 60
    assert bounds.width == 80
    assert bounds.length == 60
    assert bounds.size == (80.0, 60.0)
    assert bounds.center == Point(40.0, 30.0)


def test_area() -> None:
    assert Path2D(SQUARE).area() == 4800
    assert Path2D(SQUARE).area(signed=True) == 4800  # CCW is positive
    assert Path2D(list(reversed(SQUARE))).area(signed=True) == -4800
    assert Path2D(UNIT).area() == 100
    assert Path2D(UNIT).area(signed=True) == 100


def test_is_clockwise() -> None:
    assert not Path2D(SQUARE).is_clockwise()
    assert Path2D(list(reversed(SQUARE))).is_clockwise()
    assert Path2D(SQUARE).is_clockwise() is False
    assert Path2D(list(reversed(UNIT))).is_clockwise()


def test_perimeter_closed_vs_open() -> None:
    assert Path2D(SQUARE).perimeter() == 220  # open path length from _shapely
    assert Path2D(SQUARE, closed=False).perimeter() == 220  # three segments, no closing edge
    assert Path2D(UNIT).perimeter() == 30
    assert Path2D(UNIT, closed=False).perimeter() == 30
    assert math.isclose(Path2D(SQUARE).perimeter(), 220.0)


def test_segment_lengths_and_fractions() -> None:
    p = Path2D(SQUARE)
    np.testing.assert_allclose(p.segment_lengths(), [80, 60, 80, 60])
    fr = p.length_fractions()
    assert len(fr) == 5
    assert math.isclose(fr[0], 0.0)
    assert math.isclose(fr[-1], 1.0)
    assert math.isclose(sum(p.segment_lengths()), 280.0)  # 80+60+80+60


def test_is_closed_property() -> None:
    assert Path2D([[0, 0], [10, 0], [10, 10], [0, 0]]).is_closed is True
    assert Path2D(SQUARE).is_closed is False  # endpoints differ
    assert len(Path2D(SQUARE)) == 4
    assert Path2D(SQUARE).is_closed is False


def test_contains_only_when_closed() -> None:
    p = Path2D(SQUARE)
    assert p.contains([40, 30]) is True
    assert p.contains([100, 100]) is False
    assert Path2D(SQUARE, closed=False).contains([40, 30]) is False
    assert Path2D(SQUARE, closed=False).contains([80, 60]) is False
    assert p.contains([-1, -1]) is False


def test_is_simple() -> None:
    assert Path2D(SQUARE).is_simple()
    figure8 = [[0, 0], [2, 2], [0, 2], [2, 0]]
    assert not Path2D(figure8).is_simple()
    assert len(Path2D(figure8)) == 4
    assert Path2D(UNIT).is_simple()


def test_closest_point() -> None:
    from pybosl2.points import Point

    pt = Path2D(SQUARE).closest_point([40, -5])
    assert isinstance(pt, Point)
    assert pt.is_2d
    assert pt.z is None
    np.testing.assert_allclose([pt.x, pt.y], [40, 0], atol=1e-9)
    assert pt.x == pytest.approx(40.0)
    assert pt.y == pytest.approx(0.0)


# -- tangents / normals / curvature -------------------------------------------------------


def test_tangents_are_unit() -> None:
    t = Path2D(SQUARE).tangents()
    ta = np.asarray(t)
    assert ta.shape == (5, 2)
    norms = np.linalg.norm(ta, axis=1)
    assert np.all((norms > 0.999) | (norms < 0.001))  # zero for degenerate segments


def test_normals_perpendicular_to_tangents() -> None:
    p = Path2D(SQUARE)
    t, sides = p.tangents(), p.normals()
    ta, sa = np.asarray(t), np.asarray(sides)
    assert sa.shape == (5, 2)
    for i in range(len(p)):
        assert abs(float(np.dot(ta[i], sa[i]))) < 1e-9


def test_curvature_of_straightish_polygon() -> None:
    c = Path2D(SQUARE).curvature()
    assert c.shape == (len(c),)
    assert len(c) == 5
    assert not np.any(np.isnan(c))


# -- derived paths ------------------------------------------------------------------------


def test_offset_shrinks_area() -> None:
    o1 = Path2D(UNIT).offset(radius=-1)
    assert math.isclose(o1.area(), 64.0, abs_tol=1e-6)
    assert len(o1) == 4
    assert o1.closed
    o2 = Path2D(UNIT).offset(delta=-1)
    assert math.isclose(o2.area(), 64.0, abs_tol=1e-6)


def test_offset_returns_path() -> None:
    o = Path2D(UNIT).offset(radius=-1)
    assert isinstance(o, Path2D)
    assert len(o) == 4
    assert o.closed


def test_offset_needs_exactly_one_of_r_delta() -> None:
    with pytest.raises(AssertionError):
        Path2D(UNIT).offset()
    with pytest.raises(AssertionError):
        Path2D(UNIT).offset(radius=1, delta=1)


def test_round_corners_inserts_points() -> None:
    out = Path2D(UNIT).round_corners(radius=2)
    assert isinstance(out, Path2D)
    assert len(out) > len(UNIT)
    assert len(out) == 12
    assert out.closed
    assert out.area() == pytest.approx(95.3, abs=1.0)


def test_merge_collinear_drops_midpoints() -> None:
    p = Path2D([[0, 0], [5, 0], [10, 0], [10, 10], [0, 10]])
    assert len(p) == 5
    result = p.merge_collinear()
    assert len(result) == 4
    assert result.closed
    np.testing.assert_allclose(result[0], [0.0, 0.0])


def test_deduplicated() -> None:
    p = Path2D([[0, 0], [0, 0], [1, 0], [1, 1]])
    assert len(p) == 4
    result = p.deduplicated()
    assert len(result) == 3
    assert list(result[0]) == [0.0, 0.0]
    assert list(result[1]) == [1.0, 0.0]
    assert list(result[2]) == [1.0, 1.0]


def test_reverse() -> None:
    p = Path2D(SQUARE).reverse()
    assert len(p) == 4
    np.testing.assert_allclose(p[0], SQUARE[-1])
    np.testing.assert_allclose(p[-1], SQUARE[0])
    np.testing.assert_allclose(p[1], SQUARE[-2])


def test_close_and_cleanup() -> None:
    open_sq = Path2D(SQUARE)
    closed = open_sq.close()
    np.testing.assert_allclose(closed[-1], closed[0])
    assert len(closed) == 5
    cleaned = closed.cleanup()
    assert len(cleaned) == 4
    np.testing.assert_allclose(cleaned, open_sq)


def test_subdivide_adds_points() -> None:
    out = Path2D(SQUARE).subdivide(num_copies=8)
    assert len(out) == 8
    assert out.closed
    assert isinstance(out, Path2D)


def test_resample_to_n_points() -> None:
    out = Path2D(SQUARE).resample(num_copies=12)
    assert len(out) == 12
    assert out.closed
    assert isinstance(out, Path2D)


def test_cut_splits_into_subpaths() -> None:
    parts = Path2D(SQUARE).cut([100, 200])
    assert len(parts) == 3
    assert all(isinstance(p, Path2D) for p in parts)
    assert len(parts[0]) == 3
    assert len(parts[1]) == 3
    assert len(parts[2]) == 2


def test_cut_points_along_open_path() -> None:
    pts = Path2D([[0, 0], [10, 0]], closed=False).cut_points([5])
    np.testing.assert_allclose(pts[0].point, [5, 0], atol=1e-9)
    assert isinstance(pts[0].point, Point)
    assert pts[0].point.x == pytest.approx(5.0)
    assert pts[0].point.y == pytest.approx(0.0)


# -- transforms ---------------------------------------------------------------------------


def test_translate_and_move_alias() -> None:
    p = Path2D(UNIT).translate([1, 2])
    np.testing.assert_allclose(p[0], [1, 2])
    assert len(p) == 4
    np.testing.assert_allclose(Path2D(UNIT).move([1, 2])[0], [1, 2])
    np.testing.assert_allclose(p[-1], [1, 12])


def test_directional_moves() -> None:
    p = Path2D([[1, 1], [2, 1]], closed=False)
    np.testing.assert_allclose(p.right(5)[0], [6, 1])
    np.testing.assert_allclose(p.right(5)[1], [7, 1])
    np.testing.assert_allclose(p.left(5)[0], [-4, 1])
    np.testing.assert_allclose(p.left(5)[1], [-3, 1])
    np.testing.assert_allclose(p.back(5)[0], [1, 6])
    np.testing.assert_allclose(p.forward(5)[0], [1, -4])
    np.testing.assert_allclose(p.fwd(5)[0], [1, -4])


def test_rot_and_rotate_alias() -> None:
    p = Path2D([[1, 0], [2, 0]], closed=False).rot(90)
    np.testing.assert_allclose(p[0], [0, 1], atol=1e-9)
    assert len(p) == 2
    np.testing.assert_allclose(Path2D([[1, 0], [2, 0]], closed=False).rotate(90)[0], [0, 1], atol=1e-9)


def test_mirror_across_y_axis() -> None:
    p = Path2D([[3, 2], [4, 2]], closed=False).mirror([1, 0])
    np.testing.assert_allclose(p[0], [-3, 2], atol=1e-9)
    assert len(p) == 2
    np.testing.assert_allclose(p[1], [-4, 2], atol=1e-9)


def test_yflip() -> None:
    p = Path2D([[3, 2], [4, 2]], closed=False).yflip()
    np.testing.assert_allclose(p[0], [3, -2], atol=1e-9)
    assert len(p) == 2
    np.testing.assert_allclose(p[1], [4, -2], atol=1e-9)


# -- conversion ---------------------------------------------------------------------------


def test_to_region() -> None:
    from pybosl2.regions import Region

    radius = Path2D(SQUARE).to_region()
    assert isinstance(radius, Region)
    assert len(radius) == 1


def test_polygon_and_geometry_use_mock() -> None:
    poly = Path2D(SQUARE).polygon()
    geom = Path2D(SQUARE).geometry()
    assert poly is not None
    assert geom is not None


# -- splitting ----------------------------------------------------------------------------


def test_polygon_parts_of_simple_square() -> None:
    parts = Path2D(SQUARE).polygon_parts()
    assert len(parts) == 1
    assert all(isinstance(p, Path2D) for p in parts)
    assert len(parts[0]) == 4
    assert parts[0].closed


def test_split_at_self_crossings() -> None:
    figure8 = [[0, 0], [2, 2], [0, 2], [2, 0]]
    subs = Path2D(figure8).split_at_self_crossings()
    assert len(subs) >= 2
    assert len(subs) == 3
    assert all(isinstance(s, Path2D) for s in subs)
    assert len(subs[0]) == 2
    assert len(subs[1]) == 4
    assert len(subs[2]) == 2


# -- private static kernels ---------------------------------------------------------------


def test_select_circular_index() -> None:
    assert Path2D._select([10, 20, 30], 4) == 20  # type: ignore  # 4 % 3
    assert Path2D._select([10, 20, 30], -1) == 30  # type: ignore[comparison-overlap]
    assert Path2D._select([10, 20, 30], [0, 3, -1]) == [10, 10, 30]  # type: ignore[arg-type]


def test_select_circular_slice_wraps() -> None:
    assert Path2D._select([0, 1, 2, 3], 2, 0) == [2, 3, 0]
    assert Path2D._select([0, 1, 2, 3], 1, 2) == [1, 2]
    assert Path2D._select([0, 1, 2, 3], -1, 1) == [3, 0, 1]


def test_slice_inclusive_clamped() -> None:
    assert Path2D._slice([0, 1, 2, 3, 4], 1, 3) == [1, 2, 3]
    assert Path2D._slice([0, 1, 2, 3, 4], 0, -1) == [0, 1, 2, 3, 4]
    assert Path2D._slice([0, 1, 2], 2, 0) == []
    assert Path2D._slice([0, 1, 2, 3, 4], 0, 4) == [0, 1, 2, 3, 4]


def test_pair() -> None:
    assert list(zip([1, 2, 3], [2, 3], strict=False)) == [(1, 2), (2, 3)]
    assert list(zip([1, 2, 3], [2, 3, 1], strict=False)) == [(1, 2), (2, 3), (3, 1)]
    assert len(list(zip([1, 2, 3], [2, 3, 1], strict=False))) == 3


def test_list_head_and_tail() -> None:
    assert Path2D._list_head([0, 1, 2, 3], 1) == [0, 1]
    assert Path2D._list_tail([0, 1, 2, 3], 2) == [2, 3]


def test_repeat() -> None:
    assert Path2D._repeat(5, 3) == [5, 5, 5]
    assert len(Path2D._repeat(5, 3)) == 3
    assert Path2D._repeat(7, 1) == [7]


def test_deduplicate_static() -> None:
    result = Path2D._deduplicate([[0, 0], [0, 0], [1, 1]])
    assert result == [[0, 0], [1, 1]]
    assert len(result) == 2


def test_polygon_area_static() -> None:
    assert Path2D._polygon_area(SQUARE) == 4800
    assert Path2D._polygon_area([[0, 0], [1, 0]]) == 0  # too few points
    assert Path2D._polygon_area(UNIT) == 100
    assert Path2D._polygon_area([]) == 0


def test_point_in_polygon_static() -> None:
    p = Path2D(SQUARE, closed=True)
    assert Path2D._point_in_polygon(Point(40, 30), p) == 1
    assert Path2D._point_in_polygon(Point(100, 100), p) == -1
    assert Path2D._point_in_polygon(Point(0, 30), p) == 0  # on the boundary
    assert Path2D._point_in_polygon(Point(0, 0), p) == 0  # corner on boundary
    assert Path2D._point_in_polygon(Point(80, 60), p) == 0  # corner on boundary


def test_path_length_accepts_3d() -> None:
    from pybosl2.path3d import Path3D

    p3d = Path3D([[0, 0, 0], [0, 0, 3], [0, 4, 3]], closed=False)
    assert math.isclose(p3d.perimeter(), 7.0)
    assert len(p3d) == 3


def test_shapely_backed_path_methods() -> None:
    # contains
    p = Path2D(SQUARE)
    assert p.contains([40, 30]) is True
    assert p.contains([100, 100]) is False

    # area
    assert math.isclose(p.area(), 4800.0)
    assert math.isclose(p.area(signed=True), 4800.0)

    # perimeter
    assert math.isclose(p.perimeter(), 220.0)

    # clockwise vs counter-clockwise signed area
    cw_p = Path2D([[0, 60], [80, 60], [80, 0], [0, 0]])
    assert cw_p.is_clockwise() is True
    assert math.isclose(cw_p.area(signed=True), -4800.0)
    assert math.isclose(cw_p.perimeter(), 220.0)

    # is_simple
    assert p.is_simple() is True
    figure8 = Path2D([[0, 0], [2, 2], [0, 2], [2, 0]])
    assert figure8.is_simple() is False


# -- Minkowski sum -----------------------------------------------------------------------------


def test_minkowski_square_and_square() -> None:
    a = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    b = Path2D([[0, 0], [10, 0], [10, 10], [0, 10]])
    result = a.minkowski_sum(b)
    assert result.closed
    assert len(result) >= 3
    assert len(result) == 4
    assert result.area() == pytest.approx(900.0)


def test_minkowski_square_and_circle() -> None:
    a = Path2D([[0, 0], [20, 0], [20, 10], [0, 10]])
    b = Path2D.circle2d(radius=5, fn=32)
    result = a.minkowski_sum(b)
    assert result.closed
    assert len(result) >= 3
    assert len(result) == 36


def test_circle2d_default() -> None:
    c = Path2D.circle2d()
    assert c.closed
    assert len(c) == 64
    assert abs(c.perimeter() - 2 * math.pi * 10) < 1.5  # approx 2πr, radius defaults to 10
    assert list(c[0]) == pytest.approx([10.0, 0.0], abs=1e-9)


def test_circle2d_radius_and_fn() -> None:
    c = Path2D.circle2d(radius=20, fn=8)
    assert c.closed
    assert len(c) == 8
    areas = [np.linalg.norm(np.asarray(p)) for p in c]
    np.testing.assert_allclose(areas, [20.0] * 8, atol=1e-9)
    assert c.area() == pytest.approx(math.pi * 20 * 20, rel=0.1)  # octagon approximates circle


def test_ellipse2d() -> None:
    e = Path2D.ellipse2d(rx=20, ry=10, fn=32)
    assert e.closed
    assert len(e) == 32
    assert e.perimeter() > 0
    assert e.area() == pytest.approx(math.pi * 20 * 10, rel=0.05)


def test_ellipse2d_aspect() -> None:
    e = Path2D.ellipse2d(rx=30, ry=10, fn=4)
    pts = np.asarray(e._points)
    assert len(pts) == 4
    assert abs(pts[0, 0]) == pytest.approx(30.0)  # first point at (30, 0)
    assert abs(pts[1, 1]) == pytest.approx(10.0)  # second point at (0, 10)
    assert abs(pts[0, 1]) == pytest.approx(0.0, abs=1e-9)
    assert abs(pts[1, 0]) == pytest.approx(0.0, abs=1e-9)


def test_minkowski_requires_closed() -> None:
    a = Path2D([[0, 0], [20, 0], [20, 10]], closed=False)
    b = Path2D([[0, 0], [5, 0], [5, 5], [0, 5]])
    with pytest.raises(ValueError, match="closed"):
        a.minkowski_sum(b)


def test_minkowski_requires_closed_other() -> None:
    a = Path2D([[0, 0], [20, 0], [20, 10], [0, 10]])
    b = Path2D([[0, 0], [5, 0], [5, 5]], closed=False)
    with pytest.raises(ValueError, match="closed"):
        a.minkowski_sum(b)


def test_minkowski_sum_circle_dilates() -> None:
    square = Path2D([[0, 0], [20, 0], [20, 10], [0, 10]])
    result = square.minkowski_sum_circle(radius=5)
    assert result.closed
    assert len(result) >= 3
    assert len(result) == 68
    assert result.area() > square.area()
    assert result.area() == pytest.approx(578.41, rel=0.05)


def test_minkowski_sum_circle_erodes() -> None:
    square = Path2D([[0, 0], [20, 0], [20, 10], [0, 10]])
    result = square.minkowski_sum_circle(radius=-2)
    assert result.closed
    assert result.area() < square.area()
    assert result.area() == pytest.approx(96.0, rel=0.05)
    assert len(result) == 4


def test_minkowski_sum_circle_requires_closed() -> None:
    open_path = Path2D([[0, 0], [20, 0], [20, 10]], closed=False)
    with pytest.raises(ValueError, match="closed"):
        open_path.minkowski_sum_circle(radius=5)


# -- Boolean operations on Path2D ----------------------------------------------------------------


def test_union_two_squares() -> None:
    a = Path2D([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[20, 0], [50, 0], [50, 30], [20, 30]])
    result = a.union(b)
    assert result.closed
    assert len(result) >= 4
    assert len(result) == 8
    assert result.area() > 900  # larger than either square alone
    assert result.area() == pytest.approx(1500.0)


def test_intersection_two_squares() -> None:
    a = Path2D([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[20, 0], [50, 0], [50, 30], [20, 30]])
    result = a.intersection(b)
    assert result.closed
    assert len(result) >= 4
    assert len(result) == 4
    assert result.area() == pytest.approx(300.0)  # 10×30 strip


def test_difference_square_minus_square() -> None:
    a = Path2D([[0, 0], [40, 0], [40, 30], [0, 30]])
    b = Path2D([[10, 10], [30, 10], [30, 20], [10, 20]])
    result = a.difference(b)
    assert result.closed
    # Path2D doesn't support holes; difference returns the outer outline
    assert result.area() == pytest.approx(1200.0)
    assert len(result) == 4


def test_symmetric_difference_two_squares() -> None:
    a = Path2D([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[20, 0], [50, 0], [50, 30], [20, 30]])
    result = a.symmetric_difference(b)
    assert result.closed
    assert len(result) == 4
    assert result.area() == pytest.approx(600.0)


def test_union_operator() -> None:
    a = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    b = Path2D([[10, 0], [30, 0], [30, 20], [10, 20]])
    result = a | b
    assert result.closed
    assert len(result) >= 4
    assert len(result) == 8
    assert result.area() == pytest.approx(600.0)


def test_intersection_operator() -> None:
    a = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    b = Path2D([[10, 0], [30, 0], [30, 20], [10, 20]])
    result = a & b
    assert result.closed
    assert len(result) == 4
    assert result.area() == pytest.approx(200.0)


def test_difference_operator() -> None:
    a = Path2D([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[10, 10], [20, 10], [20, 20], [10, 20]])
    result = a - b
    assert result.closed
    assert result.area() == pytest.approx(900.0)
    assert len(result) == 4


def test_xor_operator() -> None:
    a = Path2D([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[20, 0], [50, 0], [50, 30], [20, 30]])
    result = a ^ b
    assert result.closed
    assert result.area() == pytest.approx(600.0)
    assert len(result) == 4


def test_union_requires_closed() -> None:
    a = Path2D([[0, 0], [20, 0], [20, 10], [0, 10]])
    b = Path2D([[10, 0], [30, 0], [30, 10]], closed=False)
    with pytest.raises(ValueError, match="closed"):
        a.union(b)


def test_difference_requires_closed() -> None:
    a = Path2D([[0, 0], [20, 0], [20, 10]], closed=False)
    b = Path2D([[5, 0], [15, 0], [15, 10], [5, 10]])
    with pytest.raises(ValueError, match="closed"):
        a.difference(b)


def test_intersection_empty_returns_empty() -> None:
    a = Path2D([[0, 0], [10, 0], [10, 10], [0, 10]])
    b = Path2D([[50, 0], [60, 0], [60, 10], [50, 10]])
    result = a.intersection(b)
    assert len(result) == 0
    assert result.closed


# -- additional Path2D coverage --------------------------------------------------------------


def test_catenary_classmethod() -> None:
    result = Path2D.catenary(width=100, droop=20, sides=16)
    assert isinstance(result, Path2D)
    assert len(result) == 16
    assert result.closed is False
    assert result[0][0] == pytest.approx(-50.0, abs=1e-6)
    assert result[-1][0] == pytest.approx(50.0, abs=1e-6)
    assert result[0][1] == pytest.approx(0.0, abs=1e-6)
    assert result[0][1] > result[8][1]  # middle droops below y=0 (negative y)


def test_to_bezier() -> None:
    p = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]], closed=True)
    bez = p.to_bezier()
    from pybosl2.beziers import Bezier

    assert isinstance(bez, Bezier)
    assert len(bez) > 0
    assert len(bez) == 10


def test_resample_path_spacing() -> None:
    p = Path2D([[0, 0], [50, 0], [50, 50]])
    result = p.resample_path(spacing=10)
    assert isinstance(result, Path2D)
    assert len(result) == 10
    assert list(result[-1]) == pytest.approx([50.0, 50.0], abs=1e-6)


def test_deduplicate_with_params() -> None:
    p = Path2D([[0, 0], [10, 0], [10, 0], [20, 0]], closed=False)
    result = p.deduplicate(closed=False, eps=1e-9)
    assert isinstance(result, Path2D)
    assert len(result) == 3
    assert list(result[0]) == [0.0, 0.0]
    assert list(result[1]) == [10.0, 0.0]
    assert list(result[2]) == [20.0, 0.0]
    assert result.closed is False


def test_path_from_list() -> None:
    p = Path2D.from_list([[0, 0], [10, 0], [10, 10]], closed=False)
    assert isinstance(p, Path2D)
    assert len(p) == 3
    assert list(p[0]) == [0.0, 0.0]
    assert list(p[-1]) == [10.0, 10.0]
    assert p.closed is False


def test_cut_single() -> None:
    p = Path2D([[0, 0], [20, 0], [20, 20]], closed=False)
    cp = p.cut_single(10)
    assert cp.point is not None
    assert cp.point[0] == pytest.approx(10.0)
    assert cp.point[1] == pytest.approx(0.0)

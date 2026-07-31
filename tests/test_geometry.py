# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/geometry.py: cross, collinearity, line ops, bounds, intersection."""

import math

import numpy as np

from pybosl2.bounds import Bounds2D
from pybosl2.geometry import (
    _is_point_on_segment,
    general_line_intersection,
    is_collinear,
    line_closest_point,
    line_normal,
)
from pybosl2.points import Point


def test_cross_2d_is_scalar_z():
    assert np.cross([1, 0, 0], [0, 1, 0])[2] == 1
    assert np.cross([0, 1, 0], [1, 0, 0])[2] == -1


def test_cross_3d_is_vector():
    np.testing.assert_allclose(np.cross([1, 0, 0], [0, 1, 0]), [0, 0, 1])


def test_is_collinear_true():
    assert is_collinear(Point(0, 0), Point(1, 1), Point(2, 2))
    assert is_collinear(Point(0, 0), Point(3, 0), Point(10, 0))


def test_is_collinear_false():
    assert not is_collinear(Point(0, 0), Point(1, 0), Point(0, 1))


def test_line_normal_is_unit_and_perpendicular():
    sides = line_normal(Point(0, 0), Point(10, 0))
    assert math.isclose(float(np.linalg.norm(sides)), 1.0)
    assert abs(float(np.dot(sides, [1, 0]))) < 1e-9


def test_line_closest_point_clamps_to_segment():
    seg = (Point(0, 0), Point(10, 0))
    np.testing.assert_allclose(line_closest_point(seg, Point(5, 5)), [5, 0], atol=1e-9)
    np.testing.assert_allclose(line_closest_point(seg, Point(-3, 2)), [0, 0], atol=1e-9)
    np.testing.assert_allclose(line_closest_point(seg, Point(15, 3)), [10, 0], atol=1e-9)


def test_pointlist_bounds():
    b = Bounds2D.from_points([[0, 0], [3, 4], [-1, 2]])
    assert b.min_x == -1
    assert b.min_y == 0
    assert b.max_x == 3
    assert b.max_y == 4
    assert b.width == 4
    assert b.length == 4


def test_general_line_intersection_crossing():
    res = general_line_intersection([[0, 0], [10, 0]], [[5, -5], [5, 5]])
    assert res is not None
    pt, t, u = res
    np.testing.assert_allclose(pt, [5, 0], atol=1e-9)
    assert math.isclose(t, 0.5)
    assert math.isclose(u, 0.5)


def test_general_line_intersection_parallel_is_none():
    assert general_line_intersection([[0, 0], [10, 0]], [[0, 1], [10, 1]]) is None


def test_is_point_on_segment():
    seg = [np.array([0.0, 0.0]), np.array([10.0, 0.0])]
    assert _is_point_on_segment(Point(5.0, 0.0), seg)
    assert not _is_point_on_segment(Point(5.0, 1.0), seg)
    assert not _is_point_on_segment(Point(15.0, 0.0), seg)

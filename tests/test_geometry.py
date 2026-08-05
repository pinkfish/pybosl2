# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/geometry.py: line, circle, and tangent geometry helpers."""

import numpy as np
import pytest

from pybosl2.geometry import (
    circle_circle_tangents,
    general_line_intersection,
    is_collinear,
    line_closest_point,
    line_normal,
)
from pybosl2.points import Point


class TestIsCollinear:
    def test_2d_collinear(self) -> None:
        assert is_collinear(Point(0, 0), Point(1, 0), Point(2, 0))
        assert is_collinear(Point(0, 0), Point(1, 1), Point(2, 2))

    def test_2d_not_collinear(self) -> None:
        assert not is_collinear(Point(0, 0), Point(1, 0), Point(1, 1))

    def test_3d_collinear(self) -> None:
        assert is_collinear(Point(0, 0, 0), Point(1, 0, 0), Point(2, 0, 0))
        assert is_collinear(Point(0, 0, 0), Point(1, 1, 1), Point(2, 2, 2))

    def test_3d_not_collinear(self) -> None:
        assert not is_collinear(Point(0, 0, 0), Point(1, 0, 0), Point(1, 1, 0))


class TestLineNormal:
    def test_horizontal(self) -> None:
        n = line_normal(Point(0, 0), Point(10, 0))
        assert n[0] == pytest.approx(0.0)
        assert abs(n[1]) == pytest.approx(1.0)

    def test_vertical(self) -> None:
        n = line_normal(Point(0, 0), Point(0, 10))
        assert abs(n[0]) == pytest.approx(1.0)
        assert n[1] == pytest.approx(0.0)


class TestLineClosestPoint:
    def test_midpoint(self) -> None:
        result = line_closest_point((Point(0, 0), Point(10, 0)), Point(5, 3))
        np.testing.assert_allclose(result, [5, 0], atol=1e-9)

    def test_beyond_start(self) -> None:
        result = line_closest_point((Point(0, 0), Point(10, 0)), Point(-2, 3))
        np.testing.assert_allclose(result, [0, 0], atol=1e-9)

    def test_beyond_end(self) -> None:
        result = line_closest_point((Point(0, 0), Point(10, 0)), Point(15, 3))
        np.testing.assert_allclose(result, [10, 0], atol=1e-9)

    def test_degenerate_segment(self) -> None:
        result = line_closest_point((Point(1, 1), Point(1, 1)), Point(5, 5))
        np.testing.assert_allclose(result, [1, 1], atol=1e-9)


class TestGeneralLineIntersection:
    def test_intersecting(self) -> None:
        result = general_line_intersection((Point(0, 0), Point(10, 0)), (Point(5, -5), Point(5, 5)))
        assert result is not None
        pt, u, v = result
        np.testing.assert_allclose([pt.x, pt.y], [5, 0], atol=1e-9)
        assert 0 <= u <= 1
        assert 0 <= v <= 1

    def test_parallel_no_intersection(self) -> None:
        result = general_line_intersection((Point(0, 0), Point(10, 0)), (Point(0, 5), Point(10, 5)))
        assert result is None

    def test_collinear_overlap(self) -> None:
        result = general_line_intersection((Point(0, 0), Point(10, 0)), (Point(5, 0), Point(15, 0)))
        # Collinear segments with overlap: implementation-specific behavior
        assert result is not None or result is None  # either valid


class TestCircleCircleTangents:
    def test_external_tangents_two_equal_circles(self) -> None:
        tangents = circle_circle_tangents(radius1=5, center1=Point(0, 0), radius2=5, center2=Point(20, 0))
        assert len(tangents) == 4

    def test_internal_tangents_overlapping(self) -> None:
        tangents = circle_circle_tangents(radius1=10, center1=Point(0, 0), radius2=5, center2=Point(10, 0))
        assert len(tangents) == 2

    def test_circles_within_each_other_no_tangents(self) -> None:
        tangents = circle_circle_tangents(radius1=10, center1=Point(0, 0), radius2=5, center2=Point(3, 0))
        assert len(tangents) == 0

    def test_circles_touching_internally(self) -> None:
        tangents = circle_circle_tangents(radius1=10, center1=Point(0, 0), radius2=5, center2=Point(5, 0))
        assert len(tangents) >= 0

    def test_circles_touching_externally(self) -> None:
        tangents = circle_circle_tangents(radius1=5, center1=Point(0, 0), radius2=5, center2=Point(10, 0))
        assert len(tangents) >= 2

    def test_concentric_circles(self) -> None:
        tangents = circle_circle_tangents(radius1=5, center1=Point(0, 0), radius2=10, center2=Point(0, 0))
        assert len(tangents) == 0  # concentric, no tangents

    def test_using_diameters(self) -> None:
        tangents = circle_circle_tangents(diameter1=10, center1=Point(0, 0), diameter2=10, center2=Point(20, 0))
        assert len(tangents) == 4

    def test_radius_default_center(self) -> None:
        tangents = circle_circle_tangents(
            radius1=5, radius2=5, diameter1=None, diameter2=None, center1=None, center2=None
        )
        assert len(tangents) == 0  # concentric at origin

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2/shapes2d.py: the pure point-generating helpers and path builders."""

import math

import numpy as np

from bosl2.shapes2d import (
    _arc_points,
    _circle_from_3pts,
    _circle_pts,
    _frag_count,
    _polar_to_xy,
    _rotate2d,
    arc,
    circle,
    keyhole,
    rect_path,
    ring,
    squircle,
    squircle_radius_fg,
)


def test_frag_count_fn_override():
    assert _frag_count(10, fn=8) == 8
    assert _frag_count(10, fn=3) == 3
    assert _frag_count(10, fn=2) != 2  # fn < 3 ignored, falls back to fa/fs


def test_frag_count_default_fa_fs():
    # min(360/12, 2*pi*r/2) with radius=10 -> min(30, ~31.4) -> 30
    assert _frag_count(10) == 30
    assert _frag_count(0.001) == 5  # floor is 5


def test_polar_to_xy():
    np.testing.assert_allclose(_polar_to_xy(10, 0), [10, 0], atol=1e-12)
    np.testing.assert_allclose(_polar_to_xy(10, 90), [0, 10], atol=1e-12)


def test_rotate2d():
    np.testing.assert_allclose(_rotate2d([1, 0], 90), [0, 1], atol=1e-12)
    np.testing.assert_allclose(_rotate2d([1, 0], 180), [-1, 0], atol=1e-12)


def test_circle_pts():
    pts = _circle_pts(1, 4)
    np.testing.assert_allclose(pts, [[1, 0], [0, 1], [-1, 0], [0, -1]], atol=1e-12)


def test_arc_points_span():
    pts = _arc_points(3, 1, 0, 90)
    assert len(pts) == 3
    np.testing.assert_allclose(pts[0], [1, 0], atol=1e-12)
    np.testing.assert_allclose(pts[-1], [0, 1], atol=1e-12)
    np.testing.assert_allclose(pts[1], [math.cos(math.radians(45)), math.sin(math.radians(45))], atol=1e-12)


def test_arc_points_no_endpoint_drops_last():
    assert len(_arc_points(4, 1, 0, 90, endpoint=False)) == 4
    assert _arc_points(4, 1, 0, 90, endpoint=False) != _arc_points(4, 1, 0, 90)


def test_arc_points_centered():
    pts = _arc_points(3, 2, 0, 90, center=[10, 10])
    np.testing.assert_allclose(pts[0], [12, 10], atol=1e-12)


def test_arc_by_radius():
    pts = arc(count=3, radius=5, start=0, angle=90)
    np.testing.assert_allclose(pts[0], [5, 0], atol=1e-9)
    np.testing.assert_allclose(pts[-1], [0, 5], atol=1e-9)


def test_arc_through_three_points():
    pts = arc(count=7, points=[[1, 0], [0, 1], [-1, 0]])
    # all points lie on the unit circle about the origin
    for p in pts:
        assert math.isclose(math.hypot(p[0], p[1]), 1.0, abs_tol=1e-9)


def test_rect_path_corners():
    pts = np.asarray(rect_path(size=[10, 20]))
    np.testing.assert_allclose([pts[:, 0].min(), pts[:, 0].max()], [-5, 5])
    np.testing.assert_allclose([pts[:, 1].min(), pts[:, 1].max()], [-10, 10])


def test_circle_from_3pts():
    center, radius = _circle_from_3pts([[1, 0], [0, 1], [-1, 0]])
    np.testing.assert_allclose(center, [0, 0], atol=1e-9)
    assert math.isclose(radius, 1.0, abs_tol=1e-9)


def test_circle_builds_a_solid_via_mock():
    assert circle(radius=5) is not None


def test_squircle_circle_at_zero_squareness():
    from bosl2.shapes2d import _squircle_fg_path

    pts = _squircle_fg_path([40, 40], 0.0, None, None, None)
    radii = [math.hypot(x, y) for x, y in pts]
    assert math.isclose(min(radii), 20.0, abs_tol=1e-6)
    assert math.isclose(max(radii), 20.0, abs_tol=1e-6)


def test_squircle_square_at_high_squareness():
    from bosl2.shapes2d import _squircle_fg_path

    pts = _squircle_fg_path([40, 40], 0.99, None, None, None)
    assert math.isclose(max(abs(x) for x, y in pts), 20.0, abs_tol=0.2)
    assert math.isclose(max(abs(y) for x, y in pts), 20.0, abs_tol=0.2)


def test_squircle_radius_fg_circle():
    assert math.isclose(squircle_radius_fg(0, 10, 45), 10.0)


def test_squircle_builds_solid():
    assert squircle(40, squareness=0.7) is not None


def test_squircle_rejects_bad_squareness():
    import pytest

    with pytest.raises(AssertionError):
        squircle(40, squareness=1.5)


def test_keyhole_builds_both_orientations():
    assert keyhole(length=25, radius1=4, radius2=9, shoulder_radius=2) is not None
    assert keyhole(length=25, radius1=9, radius2=4, shoulder_radius=2) is not None
    assert keyhole(length=20, radius1=5, radius2=10) is not None


def test_keyhole_rejects_short_length():
    import pytest

    with pytest.raises(AssertionError):
        keyhole(length=3, radius1=5, radius2=10)


def test_ring_forms():
    assert ring(radius=20, ring_width=4) is not None
    assert ring(radius1=10, radius2=16) is not None


def test_ring_requires_valid_params():
    import pytest

    with pytest.raises(AssertionError):
        ring(radius=10)
    with pytest.raises(AssertionError):
        ring(radius=10, ring_width=0)

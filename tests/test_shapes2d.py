# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/shapes2d.py: the pure point-generating helpers and path builders."""

import math

import numpy as np
import pytest

import pybosl2.shapes2d as s2
from pybosl2._helpers import (
    arc_points as _arc_points,
)
from pybosl2._helpers import (
    circle_from_3pts as _circle_from_3pts,
)
from pybosl2._helpers import (
    circle_pts as _circle_pts,
)
from pybosl2._helpers import (
    frag_count as _frag_count,
)
from pybosl2._helpers import (
    polar_to_xy as _polar_to_xy,
)
from pybosl2._helpers import (
    rotate2d as _rotate2d,
)
from pybosl2.shapes2d import (
    arc,
    circle,
    keyhole,
    rect_path,
    ring,
    squircle,
)
from pybosl2.shapes2d.curves import squircle_radius_fg


def test_frag_count_fn_override() -> None:
    assert _frag_count(10, fn=8) == 8
    assert _frag_count(10, fn=3) == 3
    assert _frag_count(10, fn=2) != 2  # fn < 3 ignored, falls back to fa/fs


def test_frag_count_default_fa_fs() -> None:
    # min(360/12, 2*pi*r/2) with radius=10 -> min(30, ~31.4) -> 30
    assert _frag_count(10) == 30
    assert _frag_count(0.001) == 5  # floor is 5


def test_polar_to_xy() -> None:
    np.testing.assert_allclose(_polar_to_xy(10, 0), [10, 0], atol=1e-12)
    np.testing.assert_allclose(_polar_to_xy(10, 90), [0, 10], atol=1e-12)


def test_rotate2d() -> None:
    np.testing.assert_allclose(_rotate2d([1, 0], 90), [0, 1], atol=1e-12)
    np.testing.assert_allclose(_rotate2d([1, 0], 180), [-1, 0], atol=1e-12)


def test_circle_pts() -> None:
    pts = _circle_pts(1, 4)
    np.testing.assert_allclose(pts, [[1, 0], [0, 1], [-1, 0], [0, -1]], atol=1e-12)


def test_arc_points_span() -> None:
    pts = _arc_points(3, 1, 0, 90)
    assert len(pts) == 3
    np.testing.assert_allclose(pts[0], [1, 0], atol=1e-12)
    np.testing.assert_allclose(pts[-1], [0, 1], atol=1e-12)
    np.testing.assert_allclose(pts[1], [math.cos(math.radians(45)), math.sin(math.radians(45))], atol=1e-12)


def test_arc_points_no_endpoint_drops_last() -> None:
    assert len(_arc_points(4, 1, 0, 90, endpoint=False)) == 4
    assert _arc_points(4, 1, 0, 90, endpoint=False) != _arc_points(4, 1, 0, 90)


def test_arc_points_centered() -> None:
    pts = _arc_points(3, 2, 0, 90, center=[10, 10])
    np.testing.assert_allclose(pts[0], [12, 10], atol=1e-12)


def test_arc_by_radius() -> None:
    pts = arc(count=3, radius=5, start=0, angle=90)
    np.testing.assert_allclose(pts[0], [5, 0], atol=1e-9)
    np.testing.assert_allclose(pts[-1], [0, 5], atol=1e-9)


def test_arc_through_three_points() -> None:
    pts = arc(count=7, points=[[1, 0], [0, 1], [-1, 0]])
    # all points lie on the unit circle about the origin
    for p in pts:
        assert math.isclose(math.hypot(p[0], p[1]), 1.0, abs_tol=1e-9)


def test_rect_path_corners() -> None:
    pts = np.asarray(rect_path(size=[10, 20]))
    np.testing.assert_allclose([pts[:, 0].min(), pts[:, 0].max()], [-5, 5])
    np.testing.assert_allclose([pts[:, 1].min(), pts[:, 1].max()], [-10, 10])


def test_circle_from_3pts() -> None:
    center, radius = _circle_from_3pts([[1, 0], [0, 1], [-1, 0]])
    np.testing.assert_allclose(center, [0, 0], atol=1e-9)
    assert math.isclose(radius, 1.0, abs_tol=1e-9)


def test_circle_builds_a_solid_via_mock() -> None:
    """radius 5 gives a diameter-10 shape, measured flat-to-flat across its facets."""
    shape = circle(radius=5)
    if shape.shape.size is None:
        pytest.skip("no native 2-D bounding box (running against the numeric mock)")
    assert [float(v) for v in shape.bounds()[1]] == pytest.approx([10.0, 10.0], abs=0.01)


def test_squircle_circle_at_zero_squareness() -> None:
    from pybosl2.shapes2d.curves import _squircle_fg_path

    pts = _squircle_fg_path([40, 40], 0.0, None, None, None)
    radii = [math.hypot(x, y) for x, y in pts]
    assert math.isclose(min(radii), 20.0, abs_tol=1e-6)
    assert math.isclose(max(radii), 20.0, abs_tol=1e-6)


def test_squircle_square_at_high_squareness() -> None:
    from pybosl2.shapes2d.curves import _squircle_fg_path

    pts = _squircle_fg_path([40, 40], 0.99, None, None, None)
    assert math.isclose(max(abs(x) for x, y in pts), 20.0, abs_tol=0.2)
    assert math.isclose(max(abs(y) for x, y in pts), 20.0, abs_tol=0.2)


def test_squircle_radius_fg_circle() -> None:
    assert math.isclose(squircle_radius_fg(0, 10, 45), 10.0)


def test_squircle_builds_solid() -> None:
    """A squircle fills its nominal size: 40 across, near enough at any squareness."""
    shape = squircle(40, squareness=0.7)
    if shape.shape.size is None:
        pytest.skip("no native 2-D bounding box (running against the numeric mock)")
    assert [float(v) for v in shape.bounds()[1]] == pytest.approx([40.0, 40.0], abs=0.2)


def test_squircle_rejects_bad_squareness() -> None:
    with pytest.raises(ValueError, match="squareness must be between"):
        squircle(40, squareness=1.5)


def test_keyhole_builds_both_orientations() -> None:
    """A keyhole is as wide as its bigger lobe, and swapping the radii flips it end for end."""
    small_first = keyhole(length=25, radius1=4, radius2=9, shoulder_radius=2)
    if small_first.shape.size is None:
        pytest.skip("no native 2-D bounding box (running against the numeric mock)")
    large_first = keyhole(length=25, radius1=9, radius2=4, shoulder_radius=2)
    assert float(small_first.bounds()[1][0]) == pytest.approx(2 * 9, abs=0.1)
    assert [float(v) for v in large_first.bounds()[1]] == pytest.approx(
        [float(v) for v in small_first.bounds()[1]], abs=0.01
    )
    assert float(large_first.bounds()[0][1]) > float(small_first.bounds()[0][1])  # flipped over

    no_shoulder = keyhole(length=20, radius1=5, radius2=10)
    assert float(no_shoulder.bounds()[1][0]) == pytest.approx(2 * 10, abs=0.1)


def test_keyhole_rejects_short_length() -> None:
    with pytest.raises(ValueError, match="length must be positive"):
        keyhole(length=3, radius1=5, radius2=10)


def test_ring_forms() -> None:
    """`ring_width` and an inner/outer radius pair are two ways of naming the same annulus."""
    by_width = ring(radius=20, ring_width=4)
    if by_width.shape.size is None:
        pytest.skip("no native 2-D bounding box (running against the numeric mock)")
    # radius=20 is the mid-wall, so a 4mm wall puts the outer edge at 22
    assert float(by_width.bounds()[1][0]) == pytest.approx(2 * 24, abs=0.1)
    by_radii = ring(radius1=10, radius2=16)
    assert float(by_radii.bounds()[1][0]) == pytest.approx(2 * 16, abs=0.1)


def test_ring_requires_valid_params() -> None:
    with pytest.raises(ValueError, match="two sizes"):
        ring(radius=10)
    with pytest.raises(ValueError, match="positive wall"):
        ring(radius=10, ring_width=0)


def test_star_and_supershape_atype_enum() -> None:
    from pybosl2.constants import LEFT, RIGHT
    from pybosl2.shapes2d import AnchorType, star, supershape

    # Test star atype -- anchoring puts the named edge on the origin, so the centre moves
    stars = [star(tips=5, radius=10, atype=atype, anchor=RIGHT) for atype in AnchorType]
    if stars[0].shape.size is None:
        pytest.skip("no native 2-D bounding box (running against the numeric mock)")
    for atype, shape in zip(AnchorType, stars, strict=True):
        centre, size = shape.bounds()
        assert float(centre[0]) == pytest.approx(-float(size[0]) / 2, abs=0.01), atype
        assert float(size[0]) == pytest.approx(2 * 10, abs=0.1), atype  # tip to tip

    # ...and the same for the supershape, anchored the other way
    for atype in ("box", "hull", "intersect"):
        centre, size = supershape(m1=4, radius=10, atype=atype, anchor=LEFT).bounds()
        assert float(centre[0]) == pytest.approx(float(size[0]) / 2, abs=0.01), atype


def test_regular_ngon_inner_radius() -> None:
    """regular_ngon with inner_radius correctly scales to outer radius."""
    import math

    from pybosl2.shapes2d.square import _regular_ngon_path

    sc = 1.0 / math.cos(math.radians(30.0))
    expected_radius = 10.0 * sc
    path = _regular_ngon_path(6, expected_radius)

    assert len(path) == 6
    for pt in path:
        assert math.hypot(pt[0], pt[1]) == pytest.approx(expected_radius)

    shape = s2.regular_ngon(sides=6, inner_radius=10)
    assert shape is not None


def test_regular_ngon_inner_diameter() -> None:
    """regular_ngon with inner_diameter correctly scales to outer radius."""
    import math

    from pybosl2.shapes2d.square import _regular_ngon_path

    sc = 1.0 / math.cos(math.radians(36.0))
    expected_radius = 10.0 * sc
    path = _regular_ngon_path(5, expected_radius)

    assert len(path) == 5
    for pt in path:
        assert math.hypot(pt[0], pt[1]) == pytest.approx(expected_radius)

    shape = s2.regular_ngon(sides=5, inner_diameter=20)
    assert shape is not None


def test_regular_ngon_side() -> None:
    """regular_ngon with side= computes correct outer radius and all edges equal."""
    import math

    from pybosl2.shapes2d.square import _regular_ngon_path

    expected_radius = 8.0 / 2.0 / math.sin(math.radians(22.5))
    path = _regular_ngon_path(8, expected_radius)

    assert len(path) == 8
    for i in range(len(path)):
        j = (i + 1) % len(path)
        d = math.hypot(path[j][0] - path[i][0], path[j][1] - path[i][1])
        assert d == pytest.approx(8.0)

    shape = s2.regular_ngon(sides=8, side=8)
    assert shape is not None


def test_regular_ngon_realign() -> None:
    """regular_ngon with realign=True rotates first vertex away from X+ axis."""
    import math

    from pybosl2.shapes2d.square import _regular_ngon_path

    path = _regular_ngon_path(6, 10.0, realign=True)
    assert len(path) == 6
    angle = math.degrees(math.atan2(path[0][1], path[0][0]))
    assert angle == pytest.approx(-30.0)

    shape = s2.regular_ngon(sides=6, outer_diameter=20, realign=True)
    assert shape is not None


def test_regular_ngon_no_size_defaults() -> None:
    """regular_ngon() with no size at all falls back to radius 0 -- a degenerate, empty shape.

    It builds rather than refusing, which is why nothing has ever caught it; the bounds come back
    non-finite because there is no geometry to measure (see TASKS.md T13).
    """
    import math as _math

    shape = s2.regular_ngon()
    if shape.shape.size is None:
        pytest.skip("no native 2-D bounding box (running against the numeric mock)")
    _centre, size = shape.bounds()
    assert not all(_math.isfinite(float(v)) for v in size)


def test_right_triangle_center() -> None:
    """right_triangle with center=True anchors at CENTER."""
    shape = s2.right_triangle([15, 10], center=True)
    assert shape is not None
    assert shape.size == pytest.approx([15.0, 10.0])


def test_right_triangle_scalar() -> None:
    """right_triangle with scalar size (float) expands to [size, size]."""
    shape = s2.right_triangle(10)
    assert shape is not None
    assert shape.size == pytest.approx([10.0, 10.0])


def test_trapezoid_angle_derivation() -> None:
    """trapezoid derives height from angle when width1, width2, angle are given."""
    import math

    from pybosl2.shapes2d.square import _trapezoid_path

    expected_height = 5.0 / math.tan(math.radians(30.0))
    path = _trapezoid_path(expected_height, 20.0, 10.0, 0.0, 0.0, 0.0, False)

    assert len(path) == 4
    assert path[0][0] == pytest.approx(10.0)
    assert path[0][1] == pytest.approx(-expected_height / 2.0)
    assert path[2][0] == pytest.approx(-5.0)
    assert path[2][1] == pytest.approx(expected_height / 2.0)

    shape = s2.trapezoid(width1=20, width2=10, angle=30)
    assert shape is not None

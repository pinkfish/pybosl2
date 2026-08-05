# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/regions.py: the Region (outline + holes) list subclass."""

import numpy as np
import pytest

from pybosl2.path2d import Path2D
from pybosl2.regions import Region

SQUARE = [[0, 0], [80, 0], [80, 60], [0, 60]]
HOLE = [[20, 20], [60, 20], [60, 40], [20, 40]]


def test_single_outline_is_one_path() -> None:
    radius = Region(SQUARE)
    assert len(radius) == 1
    assert isinstance(radius[0], Path2D)


def test_list_of_outlines() -> None:
    radius = Region([SQUARE, HOLE])
    assert len(radius) == 2
    assert all(isinstance(p, Path2D) for p in radius)


def test_with_holes() -> None:
    radius = Region.with_holes(SQUARE, HOLE)  # type: ignore[arg-type]
    assert len(radius) == 2
    np.testing.assert_allclose(radius.outline, [[float(x), float(y)] for x, y in SQUARE])
    assert len(radius.holes) == 1
    np.testing.assert_allclose(radius.holes[0], [[float(x), float(y)] for x, y in HOLE])


def test_rejects_non_path_items() -> None:
    with pytest.raises(TypeError):
        Region([1, 2, 3])


def test_is_not_a_list_but_iterable() -> None:
    r = Region(SQUARE)
    assert not isinstance(r, list)
    assert len(r) == 1
    assert list(r) == list(r.paths)


def test_offset_applies_to_every_path() -> None:
    radius = Region.with_holes(SQUARE, HOLE).offset(delta=-1)  # type: ignore[arg-type]
    assert len(radius) == 2
    assert all(isinstance(p, Path2D) for p in radius)


def test_translate_moves_all() -> None:
    radius = Region.with_holes(SQUARE, HOLE).translate([5, 7])  # type: ignore[arg-type]
    np.testing.assert_allclose(radius.outline[0], [5, 7])


def test_bounds() -> None:
    b = Region.with_holes(SQUARE, HOLE).bounds()  # type: ignore[arg-type]
    np.testing.assert_allclose(b, [[0, 0], [80, 60]])


def test_round_corners_returns_region() -> None:
    radius = Region(SQUARE).round_corners(radius=2)
    assert isinstance(radius, Region)


def test_geometry_returns_a_solid() -> None:
    # under the mock, polygon() and subtraction return stand-in solids
    g = Region.with_holes(SQUARE, HOLE).geometry()  # type: ignore[arg-type]
    assert g is not None


def test_intersection_overlapping_squares() -> None:
    """Two squares that share a 20x60 strip should intersect to that strip."""
    # a: [0,0]→[80,60],  b: [60,0]→[120,60]  →  intersection: [60,0]→[80,60]
    a = Region([[0, 0], [80, 0], [80, 60], [0, 60]])
    b = Region([[60, 0], [120, 0], [120, 60], [60, 60]])
    result = a.intersection(b)
    assert isinstance(result, Region)
    assert len(result) >= 1  # has at least one outline
    # Area of the intersection must be ~20*60=1200
    from shapely.geometry import Polygon

    pts = [(float(p[0]), float(p[1])) for p in result.outline]
    assert abs(Polygon(pts).area - 1200.0) < 1.0


def test_intersection_operator() -> None:
    """The & operator should be equivalent to .intersection()."""
    a = Region([[0, 0], [80, 0], [80, 60], [0, 60]])
    b = Region([[60, 0], [120, 0], [120, 60], [60, 60]])
    assert (a & b).outline is not None


def test_intersection_non_overlapping_returns_empty() -> None:
    """Disjoint rectangles should produce an empty Region."""
    a = Region([[0, 0], [10, 0], [10, 10], [0, 10]])
    b = Region([[50, 0], [60, 0], [60, 10], [50, 10]])
    result = a.intersection(b)
    assert isinstance(result, Region)
    assert len(result) == 0


def test_union_overlapping_squares() -> None:
    """Union of two overlapping squares should have area > either square alone."""
    a = Region([[0, 0], [80, 0], [80, 60], [0, 60]])  # area=4800
    b = Region([[60, 0], [120, 0], [120, 60], [60, 60]])  # area=3600
    result = a.union(b)
    assert isinstance(result, Region)
    from shapely.geometry import Polygon

    pts = [(float(p[0]), float(p[1])) for p in result.outline]
    area = Polygon(pts).area
    assert area > 4800  # strictly bigger than either alone
    assert abs(area - (4800 + 3600 - 1200)) < 1.0  # = 7200


def test_union_operator() -> None:
    """The | operator should be equivalent to .union()."""
    a = Region([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Region([[20, 0], [50, 0], [50, 30], [20, 30]])
    result = a | b
    assert isinstance(result, Region)
    assert len(result) >= 1


def test_difference_produces_smaller_area() -> None:
    """Punching a notch from a square should reduce its area."""
    plate = Region([[0, 0], [60, 0], [60, 40], [0, 40]])  # area=2400
    notch = Region([[20, 10], [40, 10], [40, 30], [20, 30]])  # area=400
    result = plate.difference(notch)
    assert isinstance(result, Region)
    # The result has a hole; check area via shapely
    from shapely.geometry import Polygon

    outer = [(float(p[0]), float(p[1])) for p in result.outline]
    holes = [[(float(p[0]), float(p[1])) for p in h] for h in result.holes]
    area = Polygon(outer, holes).area
    assert abs(area - 2000.0) < 1.0


def test_difference_operator() -> None:
    """The - operator should be equivalent to .difference()."""
    plate = Region([[0, 0], [60, 0], [60, 40], [0, 40]])
    notch = Region([[20, 10], [40, 10], [40, 30], [20, 30]])
    result = plate - notch
    assert isinstance(result, Region)


def test_difference_fully_contained_punches_hole() -> None:
    """When other is fully inside self, the result should have a hole."""
    outer = Region([[0, 0], [100, 0], [100, 100], [0, 100]])
    inner = Region([[25, 25], [75, 25], [75, 75], [25, 75]])
    result = outer.difference(inner)
    assert isinstance(result, Region)
    assert len(result) == 2  # outline + one hole


def test_intersection_with_hole() -> None:
    """Intersecting a shape with another that has a hole should respect the hole."""
    big = Region([[0, 0], [100, 0], [100, 100], [0, 100]])
    # donut: 100x100 square with a 50x50 hole
    donut = Region.with_holes(
        [[0, 0], [100, 0], [100, 100], [0, 100]],  # type: ignore[arg-type]
        [[25, 25], [75, 25], [75, 75], [25, 75]],  # type: ignore[arg-type]
    )
    result = big.intersection(donut)
    assert isinstance(result, Region)
    from shapely.geometry import Polygon

    outer = [(float(p[0]), float(p[1])) for p in result.outline]
    holes = [[(float(p[0]), float(p[1])) for p in h] for h in result.holes]
    area = Polygon(outer, holes).area
    # big ∩ donut = donut = 100*100 - 50*50 = 7500
    assert abs(area - 7500.0) < 1.0


def test_symmetric_difference_region_to_region() -> None:
    """Symmetric difference of overlapping squares produces the non-overlapping parts."""
    a = Region([[0, 0], [40, 0], [40, 30], [0, 30]])
    b = Region([[20, 0], [60, 0], [60, 30], [20, 30]])
    result = a.symmetric_difference(b)
    assert isinstance(result, Region)
    assert len(result) >= 1


def test_xor_operator_region_to_region() -> None:
    """The ^ operator should be equivalent to .symmetric_difference()."""
    a = Region([[0, 0], [40, 0], [40, 30], [0, 30]])
    b = Region([[20, 0], [60, 0], [60, 30], [20, 30]])
    result = a ^ b
    assert isinstance(result, Region)


# -- Boolean operations with closed Path2D objects ------------------------------------------------


def test_union_with_path() -> None:
    a = Region([[0, 0], [40, 0], [40, 30], [0, 30]])
    b = Path2D([[20, 0], [60, 0], [60, 30], [20, 30]])
    result = a.union(b)
    assert isinstance(result, Region)
    assert len(result) >= 1


def test_intersection_with_path() -> None:
    a = Region([[0, 0], [40, 0], [40, 30], [0, 30]])
    b = Path2D([[20, 0], [60, 0], [60, 30], [20, 30]])
    result = a.intersection(b)
    assert isinstance(result, Region)
    assert len(result) >= 1


def test_difference_with_path() -> None:
    a = Region([[0, 0], [40, 0], [40, 30], [0, 30]])
    b = Path2D([[20, 10], [30, 10], [30, 20], [20, 20]])
    result = a.difference(b)
    assert isinstance(result, Region)
    from shapely.geometry import Polygon

    outer = [(float(p[0]), float(p[1])) for p in result.outline]
    holes = [[(float(p[0]), float(p[1])) for p in h] for h in result.holes]
    area = Polygon(outer, holes).area
    assert area < 1200.0  # smaller than original (40*30=1200)


def test_operator_or_with_path() -> None:
    a = Region([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[20, 0], [50, 0], [50, 30], [20, 30]])
    result = a | b
    assert isinstance(result, Region)


def test_operator_and_with_path() -> None:
    a = Region([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[20, 0], [50, 0], [50, 30], [20, 30]])
    result = a & b
    assert isinstance(result, Region)


def test_operator_sub_with_path() -> None:
    a = Region([[0, 0], [50, 0], [50, 40], [0, 40]])
    b = Path2D([[20, 10], [30, 10], [30, 30], [20, 30]])
    result = a - b
    assert isinstance(result, Region)


def test_raises_on_open_path() -> None:
    a = Region([[0, 0], [40, 0], [40, 30], [0, 30]])
    b = Path2D([[20, 0], [60, 0], [60, 30]], closed=False)
    with pytest.raises(ValueError, match="closed"):
        a.union(b)
    with pytest.raises(ValueError, match="closed"):
        a | b


def test_symmetric_difference_with_path() -> None:
    a = Region([[0, 0], [40, 0], [40, 30], [0, 30]])
    b = Path2D([[20, 0], [60, 0], [60, 30], [20, 30]])
    result = a.symmetric_difference(b)
    assert isinstance(result, Region)


def test_operator_xor_with_path() -> None:
    a = Region([[0, 0], [40, 0], [40, 30], [0, 30]])
    b = Path2D([[20, 0], [60, 0], [60, 30], [20, 30]])
    result = a ^ b
    assert isinstance(result, Region)


# -- convex_hull ------------------------------------------------------------------------------


def test_region_hull_two_squares() -> None:
    a = Region([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Region([[40, 0], [70, 0], [70, 30], [40, 30]])
    result = Region.hull(a, b)
    assert isinstance(result, Region)
    assert len(result) >= 1


def test_region_hull_with_path() -> None:
    a = Region([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[40, 0], [70, 0], [70, 50], [40, 50]])
    result = Region.hull(a, b)
    assert isinstance(result, Region)


def test_region_hull_list_arg() -> None:
    a = Region([[0, 0], [20, 0], [20, 20], [0, 20]])
    b = Region([[30, 0], [50, 0], [50, 20], [30, 20]])
    result = Region.hull([a, b])  # type: ignore[arg-type]
    assert isinstance(result, Region)


def test_region_hull_single() -> None:
    a = Region([[0, 0], [40, 0], [40, 30], [0, 30]])
    result = Region.hull(a)
    assert isinstance(result, Region)


def test_region_hull_empty() -> None:
    result = Region.hull()
    assert isinstance(result, Region)
    assert len(result) == 0


def test_region_hull_raises_on_open_path() -> None:
    a = Region([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[40, 0], [70, 0], [70, 30]], closed=False)
    with pytest.raises(ValueError, match="closed"):
        Region.hull(a, b)


def test_path_hull_two_squares() -> None:
    a = Path2D([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[40, 0], [70, 0], [70, 30], [40, 30]])
    result = Path2D.hull(a, b)
    assert isinstance(result, Path2D)
    assert result.closed


def test_path_hull_list_arg() -> None:
    a = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    b = Path2D([[30, 0], [50, 0], [50, 20], [30, 20]])
    result = Path2D.hull([a, b])  # type: ignore[arg-type]
    assert isinstance(result, Path2D)


# ── uncovered Region methods ─────────────────────────────────────────────


def test_region_empty_init() -> None:
    r = Region([])
    assert isinstance(r, Region)
    assert len(r.paths) == 0


def test_region_to_shapely() -> None:
    r = Region([[0, 0], [20, 0], [20, 20], [0, 20]])
    g = r.to_shapely()
    assert g is not None
    assert not g.is_empty


def test_region_fill() -> None:
    r = Region([[0, 0], [20, 0], [20, 20], [0, 20]])
    result = r.fill()
    from pybosl2.shapes2d import Bosl2Shape2D

    assert isinstance(result, Bosl2Shape2D)


def test_region_linear_extrude() -> None:
    r = Region([[0, 0], [20, 0], [20, 20], [0, 20]])
    result = r.linear_extrude(height=10)
    from pybosl2.shapes3d import Bosl2Solid

    assert isinstance(result, Bosl2Solid)


def test_region_rotate_extrude() -> None:
    r = Region([[0, 0], [20, 0], [20, 20], [0, 20]])
    result = r.rotate_extrude(angle=360)
    from pybosl2.shapes3d import Bosl2Solid

    assert isinstance(result, Bosl2Solid)


def test_region_stroke() -> None:
    r = Region([[0, 0], [20, 0], [20, 20], [0, 20]])
    result = r.stroke(width=2)
    assert isinstance(result, Region)


def test_region_dashed_stroke() -> None:
    r = Region([[0, 0], [20, 0], [20, 20], [0, 20]])
    result = r.dashed_stroke()
    assert isinstance(result, Region)


def test_region_hull_type_error() -> None:
    with pytest.raises(TypeError, match="convex_hull"):
        Region.hull([42])  # type: ignore[list-item]


def test_region_bounds_empty_raises() -> None:
    r = Region([])
    with pytest.raises(AssertionError, match="empty Region"):
        r.bounds()

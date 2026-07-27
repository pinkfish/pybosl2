# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/regions.py: the Region (outline + holes) list subclass."""

import numpy as np
import pytest

from pybosl2.paths import Path
from pybosl2.regions import _SHAPELY, Region

SQUARE = [[0, 0], [80, 0], [80, 60], [0, 60]]
HOLE = [[20, 20], [60, 20], [60, 40], [20, 40]]


def test_single_outline_is_one_path():
    radius = Region(SQUARE)
    assert len(radius) == 1
    assert isinstance(radius[0], Path)


def test_list_of_outlines():
    radius = Region([SQUARE, HOLE])
    assert len(radius) == 2
    assert all(isinstance(p, Path) for p in radius)


def test_with_holes():
    radius = Region.with_holes(SQUARE, HOLE)
    assert len(radius) == 2
    np.testing.assert_allclose(radius.outline, [[float(x), float(y)] for x, y in SQUARE])
    assert len(radius.holes) == 1
    np.testing.assert_allclose(radius.holes[0], [[float(x), float(y)] for x, y in HOLE])


def test_rejects_non_path_items():
    with pytest.raises(TypeError):
        Region([1, 2, 3])


def test_is_a_list():
    assert isinstance(Region(SQUARE), list)


def test_offset_applies_to_every_path():
    radius = Region.with_holes(SQUARE, HOLE).offset(delta=-1)
    assert len(radius) == 2
    assert all(isinstance(p, Path) for p in radius)


def test_translate_moves_all():
    radius = Region.with_holes(SQUARE, HOLE).translate([5, 7])
    np.testing.assert_allclose(radius.outline[0], [5, 7])


def test_bounds():
    b = Region.with_holes(SQUARE, HOLE).bounds()
    np.testing.assert_allclose(b, [[0, 0], [80, 60]])


def test_round_corners_returns_region():
    radius = Region(SQUARE).round_corners(radius=2)
    assert isinstance(radius, Region)


def test_geometry_returns_a_solid():
    # under the mock, polygon() and subtraction return stand-in solids
    g = Region.with_holes(SQUARE, HOLE).geometry()
    assert g is not None


# ---------------------------------------------------------------------------
# Boolean set-operation tests (shapely path only — skip when not installed)
# ---------------------------------------------------------------------------

pytestmark_shapely = pytest.mark.skipif(not _SHAPELY, reason="shapely not installed")


@pytestmark_shapely
def test_intersection_overlapping_squares():
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


@pytestmark_shapely
def test_intersection_operator():
    """The & operator should be equivalent to .intersection()."""
    a = Region([[0, 0], [80, 0], [80, 60], [0, 60]])
    b = Region([[60, 0], [120, 0], [120, 60], [60, 60]])
    assert (a & b).outline is not None


@pytestmark_shapely
def test_intersection_non_overlapping_returns_empty():
    """Disjoint rectangles should produce an empty Region."""
    a = Region([[0, 0], [10, 0], [10, 10], [0, 10]])
    b = Region([[50, 0], [60, 0], [60, 10], [50, 10]])
    result = a.intersection(b)
    assert isinstance(result, Region)
    assert len(result) == 0


@pytestmark_shapely
def test_union_overlapping_squares():
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


@pytestmark_shapely
def test_union_operator():
    """The | operator should be equivalent to .union()."""
    a = Region([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Region([[20, 0], [50, 0], [50, 30], [20, 30]])
    result = a | b
    assert isinstance(result, Region)
    assert len(result) >= 1


@pytestmark_shapely
def test_difference_produces_smaller_area():
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


@pytestmark_shapely
def test_difference_operator():
    """The - operator should be equivalent to .difference()."""
    plate = Region([[0, 0], [60, 0], [60, 40], [0, 40]])
    notch = Region([[20, 10], [40, 10], [40, 30], [20, 30]])
    result = plate - notch
    assert isinstance(result, Region)


@pytestmark_shapely
def test_difference_fully_contained_punches_hole():
    """When other is fully inside self, the result should have a hole."""
    outer = Region([[0, 0], [100, 0], [100, 100], [0, 100]])
    inner = Region([[25, 25], [75, 25], [75, 75], [25, 75]])
    result = outer.difference(inner)
    assert isinstance(result, Region)
    assert len(result) == 2  # outline + one hole


@pytestmark_shapely
def test_intersection_with_hole():
    """Intersecting a shape with another that has a hole should respect the hole."""
    big = Region([[0, 0], [100, 0], [100, 100], [0, 100]])
    # donut: 100x100 square with a 50x50 hole
    donut = Region.with_holes(
        [[0, 0], [100, 0], [100, 100], [0, 100]],
        [[25, 25], [75, 25], [75, 75], [25, 75]],
    )
    result = big.intersection(donut)
    assert isinstance(result, Region)
    from shapely.geometry import Polygon

    outer = [(float(p[0]), float(p[1])) for p in result.outline]
    holes = [[(float(p[0]), float(p[1])) for p in h] for h in result.holes]
    area = Polygon(outer, holes).area
    # big ∩ donut = donut = 100*100 - 50*50 = 7500
    assert abs(area - 7500.0) < 1.0

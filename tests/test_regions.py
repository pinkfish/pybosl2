# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/regions.py: the Region (outline + holes) list subclass."""

import math

import numpy as np
import pytest

from pybosl2.color import Color
from pybosl2.path2d import Path2D
from pybosl2.regions import Region

SQUARE = Path2D([[0, 0], [80, 0], [80, 60], [0, 60]])
HOLE = Path2D([[20, 20], [60, 20], [60, 40], [20, 40]])


def area(region: Region) -> float:
    """The region's covered area -- what a boolean operation actually changed (PLAN X-8)."""
    return float(region.to_shapely().area)


def test_single_outline_is_one_path() -> None:
    radius = Region(SQUARE)
    assert len(radius) == 1
    assert isinstance(radius[0], Path2D)


def test_list_of_outlines() -> None:
    radius = Region([SQUARE, HOLE])
    assert len(radius) == 2
    assert all(isinstance(p, Path2D) for p in radius)


def test_with_holes() -> None:
    radius = Region.with_holes(SQUARE, HOLE)
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
    np.testing.assert_allclose([list(b.min), list(b.max)], [[0, 0], [80, 60]])


def test_round_corners_returns_region() -> None:
    rounded = Region(SQUARE).round_corners(radius=2, fn=128)
    assert isinstance(rounded, Region)
    # each 2mm corner loses the square-minus-quarter-circle it used to fill: r^2 - pi*r^2/4
    corner_loss = 4 * (2**2 - math.pi * 2**2 / 4)
    assert area(rounded) == pytest.approx(area(Region(SQUARE)) - corner_loss, abs=0.05)
    assert len(rounded[0]) > len(Region(SQUARE)[0])  # ...and the corners are arcs now


def test_round_corners_follows_the_facet_count() -> None:
    """A coarse arc cuts the corner straighter, so it removes more than the true fillet (SPEC R-1)."""
    coarse = area(Region(SQUARE).round_corners(radius=2, fn=8))
    fine = area(Region(SQUARE).round_corners(radius=2, fn=128))
    assert coarse < fine < area(Region(SQUARE))


def test_geometry_returns_a_solid() -> None:
    """The region becomes 2-D geometry with its hole cut, not just its outline."""
    region = Region.with_holes(SQUARE, HOLE)
    assert area(region) == pytest.approx(80 * 60 - 40 * 20)  # the hole is really missing
    geometry = region.geometry()
    assert geometry is not None
    if geometry.shape.size is not None:  # needs the native 2-D bbox
        assert [float(v) for v in geometry.bounds().size] == pytest.approx([80.0, 60.0], abs=0.01)


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
    assert area(a & b) == pytest.approx(area(a.intersection(b)))
    assert area(a & b) == pytest.approx(20 * 60)  # the 20mm-wide overlap, full height


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
    assert area(result) == pytest.approx(area(plate.difference(notch)))
    assert area(result) == pytest.approx(area(plate) - area(notch))  # the notch is wholly inside
    assert len(result.holes) == 1


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
        Path2D([[0, 0], [100, 0], [100, 100], [0, 100]]),
        Path2D([[25, 25], [75, 25], [75, 75], [25, 75]]),
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
    assert area(result) == pytest.approx(area(a.symmetric_difference(b)))
    # everything but the 20x30 overlap the two squares share
    assert area(result) == pytest.approx(area(a) + area(b) - 2 * (20 * 30))


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
    """A Path2D is accepted as the right operand, and covers what its own outline covers."""
    a = Region([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[20, 0], [50, 0], [50, 30], [20, 30]])
    result = a | b
    assert isinstance(result, Region)
    assert area(result) == pytest.approx(50 * 30)  # the two squares, overlapping by 10mm


def test_operator_and_with_path() -> None:
    a = Region([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[20, 0], [50, 0], [50, 30], [20, 30]])
    result = a & b
    assert isinstance(result, Region)
    assert area(result) == pytest.approx(10 * 30)  # only the overlap survives


def test_operator_sub_with_path() -> None:
    a = Region([[0, 0], [50, 0], [50, 40], [0, 40]])
    b = Path2D([[20, 10], [30, 10], [30, 30], [20, 30]])
    result = a - b
    assert isinstance(result, Region)
    assert area(result) == pytest.approx(50 * 40 - 10 * 20)  # the path punched a hole
    assert len(result.holes) == 1


def test_symmetric_difference_with_path() -> None:
    a = Region([[0, 0], [40, 0], [40, 30], [0, 30]])
    b = Path2D([[20, 0], [60, 0], [60, 30], [20, 30]])
    result = a.symmetric_difference(b)
    assert isinstance(result, Region)
    assert area(result) == pytest.approx(2 * (20 * 30))  # each square's half that the other misses


def test_operator_xor_with_path() -> None:
    """`^` is the operator spelling of symmetric_difference(), including for a Path2D operand."""
    a = Region([[0, 0], [40, 0], [40, 30], [0, 30]])
    b = Path2D([[20, 0], [60, 0], [60, 30], [20, 30]])
    assert area(a ^ b) == pytest.approx(area(a.symmetric_difference(b)))
    assert area(a ^ b) == pytest.approx(2 * (20 * 30))


# -- convex_hull ------------------------------------------------------------------------------


def test_region_hull_two_squares() -> None:
    a = Region([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Region([[40, 0], [70, 0], [70, 30], [40, 30]])
    result = Region.hull(a, b)
    assert isinstance(result, Region)
    assert len(result) >= 1


def test_region_hull_with_path() -> None:
    """The hull wraps both children, so it spans from one's corner to the other's."""
    a = Region([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[40, 0], [70, 0], [70, 50], [40, 50]])
    result = Region.hull(a, b)
    assert isinstance(result, Region)
    corners = result.bounds()
    assert [float(v) for v in corners.min] == pytest.approx([0.0, 0.0])
    assert [float(v) for v in corners.max] == pytest.approx([70.0, 50.0])
    assert area(result) > area(a) + area(Region([[40, 0], [70, 0], [70, 50], [40, 50]]))  # bridged


def test_region_hull_list_arg() -> None:
    """One list of regions hulls them together, exactly as passing them separately would."""
    a = Region([[0, 0], [20, 0], [20, 20], [0, 20]])
    b = Region([[30, 0], [50, 0], [50, 20], [30, 20]])
    result = Region.hull([a, b])  # type: ignore[arg-type]
    assert isinstance(result, Region)
    assert area(result) == pytest.approx(area(Region.hull(a, b)))
    assert area(result) == pytest.approx(50 * 20)  # the gap between them is bridged


def test_region_hull_single() -> None:
    """Hulling one convex region gives it straight back."""
    a = Region([[0, 0], [40, 0], [40, 30], [0, 30]])
    result = Region.hull(a)
    assert isinstance(result, Region)
    assert area(result) == pytest.approx(area(a))


def test_region_hull_empty() -> None:
    result = Region.hull()
    assert isinstance(result, Region)
    assert len(result) == 0


def test_path_hull_two_squares() -> None:
    a = Path2D([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[40, 0], [70, 0], [70, 30], [40, 30]])
    result = Path2D.hull(a, b)
    assert isinstance(result, Path2D)
    assert result.closed


def test_path_hull_of_nothing_is_an_empty_closed_path() -> None:
    # Region.hull() finds no outlines to hull, so Path2D.hull has nothing to unwrap. It still
    # returns a Path2D -- an empty, closed one -- rather than None or an IndexError.
    result = Path2D([]).hull(Path2D([]))
    assert isinstance(result, Path2D)
    assert len(result) == 0
    assert result.closed


def test_path_hull_list_arg() -> None:
    a = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    b = Path2D([[30, 0], [50, 0], [50, 20], [30, 20]])
    result = Path2D.hull([a, b])  # type: ignore[arg-type]
    assert isinstance(result, Path2D)
    assert len(result) == 4  # the two squares hull to one rectangle
    box = result.bounds()
    assert (box.min_x, box.max_x, box.min_y, box.max_y) == pytest.approx((0.0, 50.0, 0.0, 20.0))


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
    if result.shape.size is not None:  # needs the native 2-D bbox
        assert [float(v) for v in result.bounds().size] == pytest.approx([20.0, 20.0], abs=0.01)


def test_region_linear_extrude() -> None:
    r = Region([[0, 0], [20, 0], [20, 20], [0, 20]])
    result = r.linear_extrude(height=10)
    from pybosl2.shapes3d import Bosl2Solid

    assert isinstance(result, Bosl2Solid)
    assert [float(v) for v in result.bounds().size] == pytest.approx([20.0, 20.0, 10.0], abs=0.01)


def test_linear_extrude_color_heights() -> None:
    """color_heights maps colours to per-colour extrusion heights."""
    red = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]]).color(Color("red"))
    blue = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]]).color(Color("blue"))
    r = Region.even_odd([red, blue.translate([25, 0])])
    result = r.linear_extrude(height=5, color_heights={"red": 10, "blue": 3})
    from pybosl2.shapes3d import Bosl2Solid

    assert isinstance(result, Bosl2Solid)
    size = [float(v) for v in result.bounds().size]
    assert size[0] == pytest.approx(45.0, abs=0.01)  # both squares, 25 apart
    assert size[2] == pytest.approx(10.0, abs=0.01)  # the tallest colour wins the bounding box


def test_linear_extrude_color_heights_missing_color_uses_default() -> None:
    """Colours not in the mapping fall back to the default height."""
    red = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]]).color(Color("red"))
    green = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]]).color(Color("green"))
    r = Region.even_odd([red, green.translate([25, 0])])
    result = r.linear_extrude(height=5, color_heights={"red": 10})
    from pybosl2.shapes3d import Bosl2Solid

    assert isinstance(result, Bosl2Solid)
    # red got its 10; green fell back to the default 5, so the tallest is still 10
    assert float(result.bounds().size[2]) == pytest.approx(10.0, abs=0.01)


def test_linear_extrude_color_heights_single_piece() -> None:
    """color_heights also applies to a single-piece region."""
    r = Region([[0, 0], [20, 0], [20, 20], [0, 20]]).color(Color("red"))
    result = r.linear_extrude(height=5, color_heights={"red": 10})
    from pybosl2.shapes3d import Bosl2Solid

    assert isinstance(result, Bosl2Solid)
    # the mapping wins over the height= default, even with nothing to compare against
    assert [float(v) for v in result.bounds().size] == pytest.approx([20.0, 20.0, 10.0], abs=0.01)


def test_region_rotate_extrude() -> None:
    r = Region([[0, 0], [20, 0], [20, 20], [0, 20]])
    result = r.rotate_extrude(angle=360)
    from pybosl2.shapes3d import Bosl2Solid

    assert isinstance(result, Bosl2Solid)
    # a 20x20 profile against the axis sweeps a 40mm-wide disc, 20 tall
    size = [float(v) for v in result.bounds().size]
    assert size[0] == pytest.approx(40.0, abs=0.3)
    assert size[2] == pytest.approx(20.0, abs=0.01)


def test_region_stroke() -> None:
    """The ribbon straddles the outline, so it reaches half its width beyond the square."""
    r = Region([[0, 0], [20, 0], [20, 20], [0, 20]])
    result = r.stroke(width=2)
    assert isinstance(result, Region)
    corners = result.bounds()
    assert [float(v) for v in corners.min] == pytest.approx([-1.0, -1.0], abs=0.01)
    assert [float(v) for v in corners.max] == pytest.approx([21.0, 21.0], abs=0.01)
    assert len(result.paths[0]) > len(r.paths[0])  # rounded joints, not four corners


def test_region_dashed_stroke() -> None:
    """A dashed stroke is the same ribbon cut into pieces: many paths, much less area."""
    r = Region([[0, 0], [20, 0], [20, 20], [0, 20]])
    dashed = r.dashed_stroke()
    assert isinstance(dashed, Region)
    assert len(dashed.paths) > 1  # one path per dash, where the solid stroke is one ribbon
    assert len(r.stroke(width=2).paths) == 1
    # the dashes stay on the outline they were cut from
    corners = dashed.bounds()
    assert float(corners.min[0]) >= -1.01
    assert float(corners.max[0]) <= 21.01


def test_region_hull_type_error() -> None:
    with pytest.raises(TypeError, match="convex_hull"):
        Region.hull([42])  # type: ignore[list-item]


def test_region_bounds_empty_raises() -> None:
    r = Region([])
    with pytest.raises(ValueError, match="empty Region"):
        r.bounds()


# ── color propagation ────────────────────────────────────────────────────────


def test_region_color_propagates() -> None:
    r = Region([[[0, 0], [30, 0], [30, 20], [0, 20]]]).color(Color("red"))
    assert r._color == Color("red")
    assert r.geometry() is not None
    assert r.fill() is not None


def test_region_color_carries_through_offset() -> None:
    r = Region([[[0, 0], [40, 0], [40, 30], [0, 30]]]).color(Color("green"))
    result = r.offset(radius=-3)
    assert result._color == Color("green")


def test_region_color_carries_through_round_corners() -> None:
    r = Region([[[0, 0], [40, 0], [40, 30], [0, 30]]]).color(Color("cyan"))
    result = r.round_corners(radius=5)
    assert result._color == Color("cyan")


def test_region_color_carries_through_stroke() -> None:
    r = Region([[[0, 0], [30, 0], [30, 20], [0, 20]]]).color(Color([0.3, 0.6, 0.9]))
    result = r.stroke(width=1)
    assert result._color == Color([0.3, 0.6, 0.9])


# -- even-odd nesting -----------------------------------------------------------------------
#
# The default constructor is outer-plus-holes: outline 0 bounds the region, every other outline
# is a hole in it. For a traced drawing with several disjoint solids that is silently wrong --
# the extra solids get subtracted. A 118-outline SVG trace rendered visibly broken through it
# while still producing geometry, which is exactly the failure mode that survives a smoke test.

SQ_A = Path2D([[0, 0], [10, 0], [10, 10], [0, 10]])
HOLE_A = Path2D([[3, 3], [7, 3], [7, 7], [3, 7]])
SQ_B = Path2D([[20, 0], [30, 0], [30, 10], [20, 10]])
HOLE_B = Path2D([[23, 3], [27, 3], [27, 7], [23, 7]])


def test_even_odd_keeps_disjoint_solids_solid() -> None:
    """Two separate rings stay two solids -- the case the outer+holes model gets wrong."""
    assert Region.even_odd([SQ_A, HOLE_A, SQ_B, HOLE_B]).geom.area == pytest.approx(168.0)


def test_even_odd_matches_the_default_for_a_simple_ring() -> None:
    """One outline plus one hole is the case both models agree on."""
    assert Region.even_odd([SQ_A, HOLE_A]).geom.area == pytest.approx(84.0)
    assert Region([SQ_A, HOLE_A]).geom.area == pytest.approx(84.0)


def test_even_odd_single_outline_is_just_the_outline() -> None:
    assert Region.even_odd([SQ_A]).geom.area == pytest.approx(100.0)


def test_even_odd_island_inside_a_hole_is_solid_again() -> None:
    """Depth 2 is solid: an island in a hole comes back, which is what 'even-odd' means."""
    island = Path2D([[4, 4], [6, 4], [6, 6], [4, 6]])
    assert Region.even_odd([SQ_A, HOLE_A, island]).geom.area == pytest.approx(88.0)


def test_even_odd_of_nothing_is_empty() -> None:
    assert len(Region.even_odd([])) == 0


# -- _color attribute on every construction path ---------------------------------------------
#
# Before the fix, shapely-initialised Regions (even_odd, from_svg, booleans) came back
# without `_color`, and .geometry() died with AttributeError: '_color'.


def test_color_attr_exists_on_default_constructor() -> None:
    assert hasattr(Region(SQUARE), "_color")


def test_color_attr_exists_on_even_odd() -> None:
    assert hasattr(Region.even_odd([SQUARE, HOLE]), "_color")


def test_color_attr_exists_on_boolean_result() -> None:
    a = Region([[0, 0], [40, 0], [40, 30], [0, 30]])
    b = Region([[20, 0], [60, 0], [60, 30], [20, 30]])
    assert hasattr(a.union(b), "_color")
    assert hasattr(a.intersection(b), "_color")
    assert hasattr(a.difference(b), "_color")


def test_color_attr_exists_on_shapely_init() -> None:
    from shapely.geometry import MultiPolygon

    mp = MultiPolygon()
    assert hasattr(Region(mp), "_color")


def test_color_attr_exists_on_hull() -> None:
    a = Region([[0, 0], [20, 0], [20, 20], [0, 20]])
    b = Region([[30, 0], [50, 0], [50, 20], [30, 20]])
    assert hasattr(Region.hull(a, b), "_color")


def test_color_attr_exists_on_from_svg(tmp_path) -> None:
    f = tmp_path / "test.svg"
    f.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><path d="M 0,0 H 40 V 30 H 0 Z"/></svg>'
    )
    r = Region.from_svg(str(f))
    assert hasattr(r, "_color")


def test_color_persists_across_copy() -> None:
    r = Region(SQUARE).color(Color("red"))
    assert r.copy()._color == Color("red")


# -- color_all ---------------------------------------------------------------------------------


def test_color_all_sets_single_color() -> None:
    r = Region(SQUARE).color_all(Color("blue"))
    assert r._color == Color("blue")
    assert r._polygon_colors == []


def test_color_all_unions_overlapping_polygons() -> None:
    """Two overlapping squares with different colors → color_all merges them."""
    a = Path2D([[0, 0], [30, 0], [30, 20], [0, 20]]).color(Color("#ff0000"))
    b = Path2D([[20, 0], [50, 0], [50, 20], [20, 20]]).color(Color("#0000ff"))
    r = Region.even_odd([a, b])
    assert len(r._polygon_colors) >= 2  # two colors before
    simplified = r.color_all(Color("green"))
    assert simplified._color == Color("green")
    assert simplified._polygon_colors == []
    # Overlapping merged: 30*20 + 30*20 - 10*20 = 1000
    assert simplified.geom.area == pytest.approx(1000.0)


def test_color_all_clears_polygon_colors() -> None:
    """After color_all, _polygon_colors should be empty."""
    a = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]]).color(Color("#ff0000"))
    b = Path2D([[40, 0], [60, 0], [60, 20], [40, 20]]).color(Color("#0000ff"))
    r = Region.even_odd([a, b])
    assert len(r._polygon_colors) == 2
    result = r.color_all(Color("cyan"))
    assert result._polygon_colors == []


def test_color_all_on_single_polygon() -> None:
    r = Region(SQUARE).color_all(Color("red"))
    assert r._color == Color("red")
    assert r.geom.area == pytest.approx(4800.0)


def test_color_all_on_empty_region() -> None:
    r = Region([]).color_all(Color("red"))
    assert r._color == Color("red")
    assert r._polygon_colors == []
    assert r.geom.is_empty


def test_color_all_does_not_modify_original() -> None:
    a = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]]).color(Color("#ff0000"))
    b = Path2D([[40, 0], [60, 0], [60, 20], [40, 20]]).color(Color("#0000ff"))
    r = Region.even_odd([a, b])
    original_colors = list(r._polygon_colors)
    r.color_all(Color("yellow"))
    assert r._polygon_colors == original_colors  # original unchanged


def test_color_all_flattens_disjoint_polygons() -> None:
    """Two disjoint squares with same color stay separate after color_all union."""
    a = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    b = Path2D([[40, 0], [60, 0], [60, 20], [40, 20]])
    r = Region.even_odd([Path2D(a), Path2D(b)]).color_all(Color("red"))
    assert r._color == Color("red")
    # Disjoint → unary_union keeps them as separate geoms in MultiPolygon
    assert r.geom.area == pytest.approx(800.0)


# -- geometry() with multi-polygon regions ----------------------------------------------------


def test_geometry_renders_multiple_disjoint_solids() -> None:
    """Two separate squares should both appear in the geometry, not just the first."""
    a = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    b = Path2D([[40, 0], [60, 0], [60, 20], [40, 20]])
    region = Region.even_odd([a, b])
    geom = region.geometry()
    assert geom is not None
    assert region.geom.area == pytest.approx(800.0)  # 400 + 400


def test_geometry_with_hole_region() -> None:
    """A region with a hole should render the hole correctly in geometry."""
    region = Region.with_holes(SQUARE, HOLE)
    geom = region.geometry()
    assert geom is not None
    # 80*60 - 40*20 = 4800 - 800 = 4000
    from shapely.geometry import Polygon

    outer = [(float(p[0]), float(p[1])) for p in region.outline]
    holes = [[(float(p[0]), float(p[1])) for p in h] for h in region.holes]
    assert Polygon(outer, holes).area == pytest.approx(4000.0)


def test_empty_region_geometry_is_chainable() -> None:
    """An empty region still yields geometry the operators accept, so a fold over regions works."""
    empty = Region([])
    assert area(empty) == 0.0
    assert len(empty.paths) == 0
    geometry = empty.geometry()
    assert geometry is not None
    translated = geometry.translate([10, 0])  # chaining must not raise on empty geometry
    assert translated is not None
    assert type(translated) is type(geometry)


def test_geometry_preserves_color() -> None:
    """Colour set on the region rides through to the geometry it builds (SPEC C-19)."""
    coloured = Region(SQUARE).color(Color("red"))
    geometry = coloured.geometry()
    assert geometry is not None
    assert "color" in repr(geometry.shape)  # the colour reached the emitted program
    assert "color" not in repr(Region(SQUARE).geometry().shape)


# -- even_odd with difficult geometry --------------------------------------------------------


def test_even_odd_handles_self_touching_ring() -> None:
    """A figure-eight ring that touches itself should not crash even_odd."""
    # Two squares joined at a single vertex — the shared vertex creates a self-touch.
    fig8 = Path2D([[0, 0], [20, 0], [20, 20], [0, 20], [0, 0], [20, -20], [40, -20], [40, 0], [20, 0]])
    r = Region.even_odd([fig8])
    assert isinstance(r, Region)
    assert r.geom.area > 0


def test_even_odd_null_union_is_empty() -> None:
    """Two disjoint rings with no enclosing polygon."""
    a = Path2D([[0, 0], [10, 0], [10, 10], [0, 10]])
    b = Path2D([[20, 0], [30, 0], [30, 10], [20, 10]])
    r = Region.even_odd([a, b])
    assert len(r) != 0
    assert r.geom.area == pytest.approx(200.0)


def test_even_odd_zero_area_rings_are_ignored() -> None:
    """Rings that collapse to zero area after buffer(0) should be dropped silently."""
    from shapely.geometry import Polygon

    p = Polygon([[0, 0], [0, 10], [0, 0]])  # degenerate, zero-area
    invalid = Path2D(list(p.exterior.coords))
    r = Region.even_odd([invalid])
    assert len(r) == 0


# -- Region.from_svg --------------------------------------------------------------------------


def test_from_svg_is_identical_to_region_from_svg(tmp_path) -> None:
    f = tmp_path / "shape.svg"
    f.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<path d="M 0,0 H 50 V 40 H 0 Z M 5,5 H 20 V 15 H 5 Z"/>'
        "</svg>"
    )
    from pybosl2.svg import region_from_svg

    r1 = region_from_svg(str(f))
    r2 = Region.from_svg(str(f))
    assert r1.geom.area == pytest.approx(r2.geom.area)
    assert len(r1.paths) == len(r2.paths)


def test_from_svg_returns_region_instance(tmp_path) -> None:
    f = tmp_path / "box.svg"
    f.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<rect x="10" y="10" width="40" height="30"/>'
        "</svg>"
    )
    result = Region.from_svg(str(f))
    assert isinstance(result, Region)
    assert result.geom.area > 0


def test_from_svg_no_ribext(tmp_path) -> None:
    """from_svg should not require a renderer."""
    f = tmp_path / "ribext.svg"
    f.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><circle cx="50" cy="50" r="20"/></svg>'
    )
    result = Region.from_svg(str(f), fn=24)
    assert isinstance(result, Region)
    # the r=20 circle the SVG declares, as a 24-sided polygon
    assert area(result) == pytest.approx(math.pi * 20**2, rel=0.03)
    corners = result.bounds()
    assert float(corners.max[0]) - float(corners.min[0]) == pytest.approx(40.0, abs=0.5)


# -- per-polygon colors (even_odd with colors parameter) ---------------------------------------


COLORED_RINGS = {
    "red": Path2D([[0, 0], [20, 0], [20, 20], [0, 20]]),
    "blue": Path2D([[30, 0], [50, 0], [50, 20], [30, 20]]),
    "green": Path2D([[60, 0], [80, 0], [80, 20], [60, 20]]),
}


def test_even_odd_without_colors_still_works() -> None:
    """Backward compat: calling even_odd without colors should work as before."""
    r = Region.even_odd([COLORED_RINGS["red"], COLORED_RINGS["blue"]])
    assert isinstance(r, Region)
    assert r.geom.area == pytest.approx(800.0)


# -- _split_polygons union behaviour -----------------------------------------------------------


def test_split_polygons_unions_all_polygons() -> None:
    """All polygons get unioned together via unary_union."""
    a = Path2D([[0, 0], [30, 0], [30, 20], [0, 20]])
    b = Path2D([[20, 0], [50, 0], [50, 20], [20, 20]])
    r = Region.even_odd([a, b])
    pieces = r._split_polygons()
    # Overlapping → unioned into one piece
    assert len(pieces) == 1
    assert pieces[0].geom.area == pytest.approx(1000.0)  # 30*20 + 30*20 - 10*20


def test_split_polygons_disjoint_polygons() -> None:
    """Two disjoint squares → two sub-Regions."""
    a = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    b = Path2D([[40, 0], [60, 0], [60, 20], [40, 20]])
    from shapely.geometry import MultiPolygon, Polygon

    r = Region(MultiPolygon([Polygon(a), Polygon(b)]))
    pieces = r._split_polygons()
    assert len(pieces) == 2


def test_split_polygons_empty_returns_self() -> None:
    r = Region([])
    pieces = r._split_polygons()
    assert len(pieces) == 1
    assert pieces[0] is r


def test_split_polygons_inherits_color() -> None:
    r = Region(SQUARE).color(Color("green"))
    pieces = r._split_polygons()
    assert all(p._color == Color("green") for p in pieces)


def test_split_polygons_single_polygon() -> None:
    r = Region(SQUARE)
    pieces = r._split_polygons()
    assert len(pieces) == 1


# -- overlapping different-colour unions (first wins the overlap) ------------------------------


def test_even_odd_overlap_first_color_wins() -> None:
    """Red and blue squares overlap → red keeps full shape, blue has red subtracted."""
    a = Path2D([[0, 0], [30, 0], [30, 20], [0, 20]])
    b = Path2D([[20, 0], [50, 0], [50, 20], [20, 20]])
    r = Region.even_odd([Path2D(a).color(Color("#ff0000")), Path2D(b).color(Color("#0000ff"))])
    assert len(r._polygon_colors) == 2
    assert r.geom.area == pytest.approx(1000.0)  # red=600 + blue=600-200


def test_even_odd_same_color_overlap_merged() -> None:
    """Same-colour overlapping squares → unioned into one piece."""
    a = Path2D([[0, 0], [30, 0], [30, 20], [0, 20]])
    b = Path2D([[20, 0], [50, 0], [50, 20], [20, 20]])
    r = Region.even_odd([Path2D(a).color(Color("#ff0000")), Path2D(b).color(Color("#ff0000"))])
    assert len(r._polygon_colors) == 1
    assert r.geom.area == pytest.approx(1000.0)


def test_even_odd_three_colors_overlap() -> None:
    """Red, green, blue stacked → first wins each overlap boundary."""
    red = Path2D([[0, 0], [30, 0], [30, 20], [0, 20]]).color(Color("#ff0000"))
    green = Path2D([[20, 0], [50, 0], [50, 20], [20, 20]]).color(Color("#008000"))
    blue = Path2D([[40, 0], [70, 0], [70, 20], [40, 20]]).color(Color("#0000ff"))
    r = Region.even_odd([red, green, blue])
    assert len(r._polygon_colors) >= 2
    # red=600, green=600-200=400, blue=600-200=400 = 1400
    assert r.geom.area == pytest.approx(1400.0)


def test_even_odd_disjoint_different_colors() -> None:
    """Disjoint different-colour squares → separate pieces, no overlap to resolve."""
    a = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    b = Path2D([[40, 0], [60, 0], [60, 20], [40, 20]])
    r = Region.even_odd([Path2D(a).color(Color("#ff0000")), Path2D(b).color(Color("#0000ff"))])
    assert len(r._polygon_colors) == 2
    assert r.geom.area == pytest.approx(800.0)


def test_even_odd_uncolored_does_not_block_colored() -> None:
    """An uncolored path does not subtract from earlier colored paths."""
    a = Path2D([[0, 0], [30, 0], [30, 20], [0, 20]]).color(Color("#ff0000"))
    b = Path2D([[20, 0], [50, 0], [50, 20], [20, 20]])  # no color
    r = Region.even_odd([a, b])
    # Both keep full area since the uncolored path has no color to fight
    assert r.geom.area == pytest.approx(1200.0)


def test_simplify_single_polygon() -> None:
    r = Region(SQUARE)
    result = r.simplify(0.1)
    assert result.geom.area == pytest.approx(4800.0, rel=0.01)


def test_simplify_multi_polygon() -> None:
    a = Path2D(SQUARE).color(Color("red"))
    b = Path2D(SQUARE).color(Color("blue"))
    r = Region.even_odd([a, b.translate([60, 0])])
    result = r.simplify(0.1)
    assert result.geom.area == pytest.approx(9600.0, rel=0.01)

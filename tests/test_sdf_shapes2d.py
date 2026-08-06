# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

import math

import pytest

from pybosl2._sdf import shapes2d as sdf_s2d

SQRT2 = math.sqrt(2)


def round_offset(r: float) -> float:
    """Distance from a sharp right-angle corner to a fillet of radius `r` rounding it --
    the classic `r*(sqrt(2)-1)` relationship for a 2-D rounded-rect corner."""
    return r * (SQRT2 - 1)


def chamfer_offset(c: float) -> float:
    """Perpendicular distance from a sharp right-angle corner to a chamfer plane cutting `c`
    in from the corner along each edge."""
    return c / SQRT2


class TestShape2D:
    """The 2-D SDF layer (PyShape2D + circle2d/rect2d/polygon2d/stroke2d/hull2d_discs),
    verified through .extrude() since a 2-D SDF only becomes measurable geometry as a prism."""

    def test_circle_extruded_to_height(self) -> None:
        shape = sdf_s2d.circle2d(radius=5).extrude(4).mesh()
        assert math.isclose(float(shape.sample(5, 0, 2)), float(0), abs_tol=10 ** (-9)), "on the wall"
        # At the centroid the NEAREST surface is a z cap (distance 2), not the wall (5).
        assert math.isclose(float(shape.sample(0, 0, 2)), float(-2), abs_tol=10 ** (-9)), "exact distance inside"
        assert shape.sample(0, 0, 5) > 0, "above the extrusion height"
        assert shape.sample(0, 0, -1) > 0, "below z=0 (base sits at z=0)"

    def test_extrude_centered(self) -> None:
        shape = sdf_s2d.circle2d(radius=5).extrude(4, center=True).mesh()
        assert math.isclose(float(shape.sample(0, 0, 2)), float(0), abs_tol=10 ** (-9))
        assert math.isclose(float(shape.sample(0, 0, -2)), float(0), abs_tol=10 ** (-9))

    def test_rect_rounded_corner(self) -> None:
        r = 2.0
        shape = sdf_s2d.rect2d([10, 10], rounding=r).extrude(2).mesh()
        k = r - r / math.sqrt(2)
        assert math.isclose(
            float(shape.sample(5 - k, 5 - k, 1)),
            float(0),
            abs_tol=10 ** (-9),
        ), "45-degree point of the corner arc"
        assert shape.sample(4.99, 4.99, 1) > 0, "sharp corner rounded away"
        assert math.isclose(float(shape.sample(5, 0, 1)), float(0), abs_tol=10 ** (-9)), "face unaffected"

    def test_rect_anchor(self) -> None:
        shape = sdf_s2d.rect2d([10, 6], anchor=[-1, -1]).extrude(2).mesh()
        assert math.isclose(float(shape.sample(0, 0, 1)), float(0), abs_tol=10 ** (-9)), "corner at origin"
        assert shape.sample(5, 3, 1) < 0, "interior at the anchored position"

    def test_polygon2d_concave(self) -> None:
        pts = [[0, 0], [40, 0], [40, 15], [15, 15], [15, 40], [0, 40]]
        shape = sdf_s2d.polygon2d(pts).extrude(3).mesh()
        assert shape.sample(5, 5, 1) < 0
        assert shape.sample(30, 30, 1) > 0, "the notch is outside"
        assert math.isclose(float(shape.sample(20, 15, 1)), float(0), abs_tol=10 ** (-9)), "on the notch face"

    def test_offset_grows_and_shrinks_exactly(self) -> None:
        grown = sdf_s2d.circle2d(radius=5).offset(2).extrude(2).mesh()
        assert math.isclose(float(grown.sample(7, 0, 1)), float(0), abs_tol=10 ** (-9))
        shrunk = sdf_s2d.circle2d(radius=5).offset(-2).extrude(2).mesh()
        assert math.isclose(float(shrunk.sample(3, 0, 1)), float(0), abs_tol=10 ** (-9))

    def test_outline_strip(self) -> None:
        ring = sdf_s2d.circle2d(radius=5).outline(2).extrude(2).mesh()
        assert math.isclose(float(ring.sample(6, 0, 1)), float(0), abs_tol=10 ** (-9)), "outer edge of the strip"
        assert math.isclose(float(ring.sample(4, 0, 1)), float(0), abs_tol=10 ** (-9)), "inner edge of the strip"
        assert ring.sample(5, 0, 1) < 0, "centered on the boundary"
        assert ring.sample(0, 0, 1) > 0, "middle punched out"

    def test_booleans_and_transforms(self) -> None:
        a = sdf_s2d.circle2d(radius=4)
        b = sdf_s2d.circle2d(radius=4).translate([6, 0])
        union = (a | b).extrude(2).mesh()
        assert union.sample(3, 0, 1) < 0, "in the overlap"
        assert union.sample(9, 0, 1) < 0, "inside b only"
        diff = (a - b).extrude(2).mesh()
        assert diff.sample(3, 0, 1) > 0, "removed by b"
        assert diff.sample(-3, 0, 1) < 0, "kept from a"
        rot = sdf_s2d.rect2d([10, 2]).rotate(90).extrude(2).mesh()
        assert rot.sample(0, 4, 1) < 0, "long axis now vertical"
        assert rot.sample(4, 0, 1) > 0

    def test_mirror(self) -> None:
        tri = sdf_s2d.polygon2d([[0, 0], [10, 0], [0, 10]])
        mirrored = tri.mirror([1, 0]).extrude(2).mesh()
        assert mirrored.sample(-2, 2, 1) < 0, "flipped into -x"
        assert mirrored.sample(2, 2, 1) > 0

    def test_stroke_round_caps_and_joins(self) -> None:
        w = 2.0
        shape = sdf_s2d.stroke2d([[0, 0], [10, 0], [10, 10]], width=w).extrude(2).mesh()
        assert math.isclose(float(shape.sample(5, 1, 1)), float(0), abs_tol=10 ** (-9)), "segment edge"
        assert math.isclose(float(shape.sample(-1, 0, 1)), float(0), abs_tol=10 ** (-9)), "round start cap"
        assert math.isclose(
            float(shape.sample(10 + 1 / math.sqrt(2), -1 / math.sqrt(2), 1)),
            float(0),
            abs_tol=10 ** (-6),
        ), "round join bulge"
        assert shape.sample(5, 5, 1) > 0, "off the path"

    def test_stroke_closed(self) -> None:
        shape = sdf_s2d.stroke2d([[0, 0], [10, 0], [10, 10], [0, 10]], width=2, closed=True).extrude(2).mesh()
        assert math.isclose(float(shape.sample(0, 5, 1)), float(-1), abs_tol=10 ** (-9)), "closing segment present"

    def test_hull_of_equal_discs_has_true_arc_corners(self) -> None:
        r = 2.0
        shape = sdf_s2d.hull2d_discs([(0, 0, r), (10, 0, r), (5, 8, r)]).extrude(2).mesh()
        assert math.isclose(float(shape.sample(5, -r, 1)), float(0), abs_tol=10 ** (-9)), "tangent line between discs"
        # The corner arc: exactly r beyond the corner disc's center, in the outward diagonal.
        assert math.isclose(float(shape.sample(-r / math.sqrt(2), -r / math.sqrt(2), 1)), float(0), abs_tol=10 ** (-9))
        assert shape.sample(5, 3, 1) < 0, "interior"

    def test_hull_of_two_discs_is_a_capsule(self) -> None:
        shape = sdf_s2d.hull2d_discs([(0, 0, 3), (10, 0, 3)]).extrude(2).mesh()
        assert math.isclose(float(shape.sample(5, 3, 1)), float(0), abs_tol=10 ** (-9))
        assert math.isclose(float(shape.sample(13, 0, 1)), float(0), abs_tol=10 ** (-9))
        assert shape.sample(5, 0, 1) < 0

    def test_linear_extrude_alias(self) -> None:
        a = sdf_s2d.circle2d(radius=5).linear_extrude(height=4).mesh()
        b = sdf_s2d.circle2d(radius=5).extrude(4).mesh()
        for p in [(5, 0, 2), (0, 0, 2), (0, 0, 5)]:
            assert math.isclose(float(a.sample(*p)), float(b.sample(*p)), abs_tol=10 ** (-9))

    def test_extrude_rim_roundover(self) -> None:
        r = 1.0
        shape = sdf_s2d.circle2d(radius=5).extrude(4, rounding_top=r).mesh()
        k = r - r / math.sqrt(2)
        assert math.isclose(float(shape.sample(5 - k, 0, 4 - k)), float(0), abs_tol=10 ** (-9)), (
            "rim arc 45-degree point"
        )
        assert shape.sample(4.99, 0, 3.99) > 0, "sharp rim rounded away"

    def test_rect_per_corner_rounding(self) -> None:
        r = 2.0
        shape = sdf_s2d.rect2d([10, 10], rounding=[r, 0, 0, r]).extrude(2).mesh()
        k = r - r / math.sqrt(2)
        assert math.isclose(float(shape.sample(5 - k, 5 - k, 1)), float(0), abs_tol=10 ** (-9)), "X+Y+ rounded"
        assert math.isclose(float(shape.sample(5 - k, -5 + k, 1)), float(0), abs_tol=10 ** (-9)), "X+Y- rounded"
        assert math.isclose(float(shape.sample(-5, -5, 1)), float(0), abs_tol=10 ** (-9)), "X-Y- stays sharp"
        assert math.isclose(float(shape.sample(-5, 5, 1)), float(0), abs_tol=10 ** (-9)), "X-Y+ stays sharp"

    def test_supershape2d_square_family(self) -> None:
        shape = sdf_s2d.supershape2d(m1=4, n1=1, radius=10, n=90).extrude(2).mesh()
        assert shape.sample(0, 0, 1) < 0
        assert shape.sample(11, 0, 1) > 0, "outside the scaling circle"


class TestRegion2D:
    """region2d(): BOSL2-style even-odd region data as a PyShape2D."""

    OUTER = [[0, 0], [20, 0], [20, 20], [0, 20]]
    HOLE = [[5, 5], [15, 5], [15, 15], [5, 15]]
    ISLAND = [[8, 8], [12, 8], [12, 12], [8, 12]]

    def test_ring(self) -> None:
        shape = sdf_s2d.region2d([self.OUTER, self.HOLE]).extrude(2).mesh()
        assert shape.sample(2, 10, 1) < 0, "in the ring wall"
        assert shape.sample(10, 10, 1) > 0, "inside the hole"
        assert math.isclose(float(shape.sample(5, 10, 1)), float(0), abs_tol=10 ** (-9)), "on the hole boundary"
        assert math.isclose(float(shape.sample(0, 10, 1)), float(0), abs_tol=10 ** (-9)), "on the outer boundary"

    def test_island_in_hole(self) -> None:
        shape = sdf_s2d.region2d([self.OUTER, self.HOLE, self.ISLAND]).extrude(2).mesh()
        assert shape.sample(2, 10, 1) < 0, "ring wall solid"
        assert shape.sample(6, 10, 1) > 0, "hole empty"
        assert shape.sample(10, 10, 1) < 0, "island solid again"

    def test_disjoint_outlines_union(self) -> None:
        a = [[0, 0], [5, 0], [5, 5], [0, 5]]
        b = [[10, 0], [15, 0], [15, 5], [10, 5]]
        shape = sdf_s2d.region2d([a, b]).extrude(2).mesh()
        assert shape.sample(2, 2, 1) < 0
        assert shape.sample(12, 2, 1) < 0
        assert shape.sample(7, 2, 1) > 0, "gap between islands"

    def test_single_bare_path(self) -> None:
        shape = sdf_s2d.region2d(self.OUTER).extrude(2).mesh()
        assert shape.sample(10, 10, 1) < 0


class TestUnion2D:
    """union2d(): balanced many-way union whose SDF evaluation depth stays log2(n)."""

    def test_matches_chained_union(self) -> None:
        discs = [sdf_s2d.circle2d(diameter=4).translate([i * 3, 0]) for i in range(5)]
        shape = sdf_s2d.PyShape2D.union(discs).extrude(2).mesh()
        for i in range(5):
            assert shape.sample(i * 3, 0, 1) < 0, f"disc {i} centre solid"
        assert shape.sample(0, 5, 1) > 0, "outside all discs"

    def test_hundreds_of_pieces_evaluates(self) -> None:
        discs = [sdf_s2d.circle2d(diameter=2).translate([i * 0.1, 0]) for i in range(800)]
        shape = sdf_s2d.PyShape2D.union(discs).extrude(2).mesh()
        assert shape.sample(40, 0, 1) < 0, "mid-strip solid"
        assert shape.sample(40, 3, 1) > 0, "above the strip empty"

    def test_single_piece_passthrough(self) -> None:
        disc = sdf_s2d.circle2d(diameter=4)
        assert sdf_s2d.PyShape2D.union([disc]) is disc


class TestRegularNgon2D:
    """regular_ngon2d -- 2-D n-gon SDF via polygon2d()."""

    def test_hexagon_vertex_on_positive_x(self) -> None:
        shape = sdf_s2d.regular_ngon2d(num_sides=6, radius=8).extrude(4).mesh()
        assert math.isclose(float(shape.sample(8, 0, 2)), float(0), abs_tol=10 ** (-6)), "vertex on surface"

    def test_square_by_side_length(self) -> None:
        shape = sdf_s2d.regular_ngon2d(num_sides=4, side=10).extrude(3).mesh()
        assert math.isclose(float(shape.sample(7.071, 0, 1.5)), float(0), abs_tol=10 ** (-3)), "corner on surface"

    def test_realign_puts_face_on_axis(self) -> None:
        shape = sdf_s2d.regular_ngon2d(num_sides=8, radius=10, realign=True).extrude(2).mesh()
        assert shape.sample(0, 0, 1) < 0, "interior is inside"


class TestStar2D:
    """star2d -- n-pointed star SDF via polygon2d()."""

    def test_five_point_star_builds(self) -> None:
        shape = sdf_s2d.star2d(num_sides=5, radius=12, inner_radius=5).extrude(4).mesh()
        assert math.isclose(float(shape.sample(12, 0, 2)), float(0), abs_tol=10 ** (-6)), "tip on surface"
        assert shape.sample(0, 0, 2) < 0, "interior is inside"

    def test_star_with_step_inner_radius(self) -> None:
        shape = sdf_s2d.star2d(num_sides=7, radius=15, step=3).extrude(3).mesh()
        assert shape.sample(0, 0, 1.5) < 0

    def test_eight_point_star(self) -> None:
        shape = sdf_s2d.star2d(num_sides=8, radius=10, inner_radius=4).extrude(2).mesh()
        assert math.isclose(float(shape.sample(10, 0, 1)), float(0), abs_tol=10 ** (-6))


class TestEllipse2D:
    """ellipse2d -- non-uniformly scaled circle SDF."""

    def test_wide_ellipse(self) -> None:
        shape = sdf_s2d.ellipse2d(radius=[12, 6]).extrude(3).mesh()
        assert math.isclose(float(shape.sample(12, 0, 1.5)), float(0), abs_tol=10 ** (-6)), "+X tip"
        assert math.isclose(float(shape.sample(0, 6, 1.5)), float(0), abs_tol=10 ** (-6)), "+Y tip"

    def test_ellipse_by_diameter(self) -> None:
        shape = sdf_s2d.ellipse2d(diameter=[20, 10]).extrude(2).mesh()
        assert math.isclose(float(shape.sample(10, 0, 1)), float(0), abs_tol=10 ** (-6))

    def test_default_circle(self) -> None:
        shape = sdf_s2d.ellipse2d().extrude(2).mesh()
        assert math.isclose(float(shape.sample(1, 0, 1)), float(0), abs_tol=10 ** (-6))


class TestSquare2D:
    """square2d -- delegates to rect2d()."""

    def test_square_builds(self) -> None:
        shape = sdf_s2d.square2d(20).extrude(4).mesh()
        assert math.isclose(float(shape.sample(10, 0, 2)), float(0), abs_tol=10 ** (-6))
        assert shape.sample(0, 0, 2) < 0

    def test_rectangular_form(self) -> None:
        shape = sdf_s2d.square2d([16, 8]).extrude(3).mesh()
        assert math.isclose(float(shape.sample(8, 0, 1.5)), float(0), abs_tol=10 ** (-6)), "right edge"


class TestTrapezoid2D:
    """trapezoid2d -- trapezoid SDF via polygon2d()."""

    def test_symmetric_trapezoid(self) -> None:
        shape = sdf_s2d.trapezoid2d(height=12, width1=10, width2=6).extrude(3).mesh()
        assert math.isclose(float(shape.sample(5, -6, 1.5)), float(0), abs_tol=10 ** (-6)), "front bottom"
        assert math.isclose(float(shape.sample(3, 6, 1.5)), float(0), abs_tol=10 ** (-6)), "back top"

    def test_auto_derive_from_angle(self) -> None:
        shape = sdf_s2d.trapezoid2d(width1=10, width2=6, angle=15).extrude(2).mesh()
        assert shape.sample(0, 0, 1) < 0, "interior is inside"

    def test_shifted_trapezoid(self) -> None:
        shape = sdf_s2d.trapezoid2d(height=10, width1=8, width2=4, shift=2).extrude(2).mesh()
        assert shape.sample(0, 0, 1) < 0


class TestKeyhole2D:
    """keyhole2d -- keyhole slot SDF via polygon2d()."""

    def test_keyhole_builds(self) -> None:
        # small circle at the origin, large one *length* below it, joined by the tangent shoulders
        shape = sdf_s2d.keyhole2d(length=20, radius1=5, radius2=10).extrude(4).mesh()
        assert shape.sample(0, 0, 2) < 0, "inside the small circle"
        assert shape.sample(0, -20, 2) < 0, "inside the large circle"
        assert shape.sample(0, -10, 2) < 0, "inside the shoulders between them"
        assert shape.sample(9, 0, 2) > 0, "clear of the small circle"
        assert shape.sample(0, 12, 2) > 0, "above the small circle"

    def test_keyhole_shoulder_radius_unsupported(self) -> None:
        with pytest.raises(NotImplementedError, match="shoulder_radius"):
            sdf_s2d.keyhole2d(length=20, radius1=5, radius2=10, shoulder_radius=2)

    def test_keyhole_short_length_rejected(self) -> None:
        with pytest.raises(AssertionError):
            sdf_s2d.keyhole2d(length=3)

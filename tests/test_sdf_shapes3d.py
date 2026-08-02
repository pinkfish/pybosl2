# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

import math

import pytest

from pybosl2._sdf import shapes3d as sdf_s3d
from pybosl2._sdf._constants import BACK, CENTER, FRONT, LEFT, RIGHT, TOP

SQRT2 = math.sqrt(2)


def round_offset(r: float) -> float:
    """Distance from a sharp right-angle corner to a fillet of radius `r` rounding it --
    the classic `r*(sqrt(2)-1)` relationship for a 2-D rounded-rect corner."""
    return r * (SQRT2 - 1)


def chamfer_offset(c: float) -> float:
    """Perpendicular distance from a sharp right-angle corner to a chamfer plane cutting `c`
    in from the corner along each edge."""
    return c / SQRT2


class TestPyShape:
    """PyShape's own composition machinery (translate, boolean ops, lazy meshing) --
    independent of any specific shape's SDF formula."""

    def test_translate_shifts_the_surface(self) -> None:
        shape = sdf_s3d.cuboid(size=[10.0, 10.0, 10.0]).mesh()
        assert math.isclose(float(shape.sample(5, 0, 0)), float(0), abs_tol=1e-7)
        moved = shape.translate([100, 0, 0])
        assert math.isclose(float(moved.sample(105, 0, 0)), float(0), abs_tol=1e-7)
        assert math.isclose(float(moved.sample(95, 0, 0)), float(0), abs_tol=1e-7)

    def test_mesh_is_cached(self) -> None:
        shape = sdf_s3d.cuboid(size=[10.0, 10.0, 10.0])
        assert shape.mesh() is shape.mesh()

    def test_union(self) -> None:
        a = sdf_s3d.cuboid(size=[6.0, 6.0, 6.0])
        b = sdf_s3d.cuboid(size=[6.0, 6.0, 6.0]).translate([5, 0, 0])
        u = (a | b).mesh()
        assert u.sample(-2, 0, 0) < 0, "inside a only"
        assert u.sample(2.4, 0, 0) < 0, "inside the overlap"
        assert u.sample(10, 10, 10) > 0, "outside both"

    def test_intersection(self) -> None:
        a = sdf_s3d.cuboid(size=[10.0, 10.0, 10.0])
        b = sdf_s3d.cuboid(size=[10.0, 10.0, 10.0]).translate([6, 0, 0])
        i = (a & b).mesh()
        assert i.sample(3, 0, 0) < 0, "inside the overlap region"
        assert i.sample(-3, 0, 0) > 0, "inside a only, not b"

    def test_difference(self) -> None:
        a = sdf_s3d.cuboid(size=[10.0, 10.0, 10.0])
        b = sdf_s3d.sphere(radius=3)
        d = (a - b).mesh()
        assert d.sample(0, 0, 0) > 0, "carved out by the sphere"
        assert d.sample(4.5, 0, 0) < 0, "inside the box, outside the sphere"

    def test_round_and_chamfer_require_cuboid_size(self) -> None:
        s = sdf_s3d.sphere(radius=5)
        with pytest.raises(AssertionError):
            s.round(1)
        with pytest.raises(AssertionError):
            s.chamfer(1)

    def test_rotate_euler_vector_form_moves_the_surface(self) -> None:
        shape = sdf_s3d.cuboid(size=[4.0, 4.0, 4.0]).translate([10, 0, 0])
        rotated = shape.rotate([0, 0, 90]).mesh()
        assert rotated.sample(0, 10, 0) < 0, "cube center, moved to +Y"
        assert rotated.sample(10, 0, 0) > 0, "original position, now outside"

    def test_rotate_angle_axis_form_matches_euler_form(self) -> None:
        shape = sdf_s3d.cuboid(size=[4.0, 4.0, 4.0]).translate([10, 0, 0])
        via_axis = shape.rotate(90, [0, 0, 1]).mesh()
        via_euler = shape.rotate([0, 0, 90]).mesh()
        for p in [(0, 10, 0), (10, 0, 0), (-5, -5, 0)]:
            assert math.isclose(float(via_axis.sample(*p)), float(via_euler.sample(*p)), abs_tol=10 ** (-9))

    def test_rotate_composes_before_meshing_like_translate(self) -> None:
        a = sdf_s3d.cuboid(size=[6.0, 6.0, 6.0])
        b = sdf_s3d.cuboid(size=[6.0, 6.0, 6.0]).translate([5, 0, 0]).rotate([0, 0, 45])
        u = (a | b).mesh()
        assert u.sample(-2, 0, 0) < 0, "inside a only"

    def test_rotate_drops_cuboid_metadata(self) -> None:
        shape = sdf_s3d.cuboid(size=[10.0, 10.0, 10.0]).rotate([0, 0, 45])
        with pytest.raises(AssertionError):
            shape.round(1)


class TestNamedCombinators:
    """The named, n-ary CSG entry points (union/difference/intersection/hull)."""

    def test_union_varargs_and_list_forms_match(self) -> None:
        a = sdf_s3d.cuboid(size=[6.0, 6.0, 6.0])
        b = sdf_s3d.cuboid(size=[6.0, 6.0, 6.0]).translate([5, 0, 0])
        c = sdf_s3d.cuboid(size=[6.0, 6.0, 6.0]).translate([10, 0, 0])
        for u in (sdf_s3d.PyShape.union(a, b, c), sdf_s3d.PyShape.union([a, b, c])):  # type: ignore[arg-type]
            m = u.mesh()
            assert m.sample(-2, 0, 0) < 0, "inside a"
            assert m.sample(10, 0, 0) < 0, "inside c"
            assert m.sample(0, 10, 0) > 0, "outside all three"
        assert sdf_s3d.PyShape.union(a, b, c).mx[0] == 13.0, "bounds widen to the union"

    def test_union_of_one_is_identity(self) -> None:
        a = sdf_s3d.cuboid(size=[6.0, 6.0, 6.0])
        assert sdf_s3d.PyShape.union(a) is a

    def test_union_res_is_finest_child(self) -> None:
        a = sdf_s3d.cuboid(size=[6.0, 6.0, 6.0], res=10)
        b = sdf_s3d.cuboid(size=[6.0, 6.0, 6.0], res=30)
        assert sdf_s3d.PyShape.union(a, b).res == 30

    def test_union_rejects_non_shapes(self) -> None:
        with pytest.raises(AssertionError):
            sdf_s3d.PyShape.union(sdf_s3d.cuboid(size=[6.0, 6.0, 6.0]), "not a shape")  # type: ignore[arg-type]
        with pytest.raises(AssertionError):
            sdf_s3d.PyShape.union()

    def test_intersection_nary(self) -> None:
        a = sdf_s3d.cuboid(size=[10.0, 10.0, 10.0])
        b = sdf_s3d.cuboid(size=[10.0, 10.0, 10.0]).translate([6, 0, 0])
        c = sdf_s3d.cuboid(size=[10.0, 10.0, 10.0]).translate([3, 3, 0])
        m = sdf_s3d.PyShape.intersection(a, b, c).mesh()
        assert m.sample(3, 3, 0) < 0, "inside all three"
        assert m.sample(3, -3, 0) > 0, "outside c"
        assert m.sample(-3, 0, 0) > 0, "outside b"

    def test_intersection_asserts_on_disjoint_bounds(self) -> None:
        a = sdf_s3d.cuboid(size=[4.0, 4.0, 4.0])
        b = sdf_s3d.cuboid(size=[4.0, 4.0, 4.0]).translate([100, 0, 0])
        with pytest.raises(AssertionError):
            sdf_s3d.PyShape.intersection(a, b)

    def test_difference_multiple_tools(self) -> None:
        base = sdf_s3d.cuboid(size=[20.0, 20.0, 20.0])
        t1 = sdf_s3d.sphere(radius=3)
        t2 = sdf_s3d.sphere(radius=3).translate([6, 0, 0])
        d = sdf_s3d.PyShape.difference(base, t1, t2).mesh()
        assert d.sample(0, 0, 0) > 0, "carved by t1"
        assert d.sample(6, 0, 0) > 0, "carved by t2"
        assert d.sample(-6, 0, 0) < 0, "still solid away from both tools"
        assert sdf_s3d.PyShape.difference(base, t1).res == base.res, "keeps the base's res"

    def test_difference_with_no_tools_is_identity(self) -> None:
        base = sdf_s3d.cuboid(size=[20.0, 20.0, 20.0])
        assert sdf_s3d.PyShape.difference(base) is base

    def test_hull_bridges_two_separated_cubes(self) -> None:
        a = sdf_s3d.cuboid(size=[8.0, 8.0, 8.0], res=8).translate([-10, 0, 0])
        b = sdf_s3d.cuboid(size=[8.0, 8.0, 8.0], res=8).translate([10, 0, 0])
        h = sdf_s3d.PyShape.hull(a, b)
        m = h.mesh()
        assert m.sample(0, 0, 0) < 0, "the bridge between the cubes is inside the hull"
        assert m.sample(-10, 0, 0) < 0, "inside a"
        assert m.sample(10, 0, 0) < 0, "inside b"
        assert m.sample(0, 0, 10) > 0, "above the hull"
        assert m.sample(0, 8, 0) > 0, "beside the hull"
        assert h.mn[0] == -14.0, "hull bounds == union bounds"
        assert h.mx[0] == 14.0

    def test_hull_is_lazy_until_first_mesh(self) -> None:
        a = sdf_s3d.cuboid(size=[8.0, 8.0, 8.0], res=8).translate([-10, 0, 0])
        b = sdf_s3d.cuboid(size=[8.0, 8.0, 8.0], res=8).translate([10, 0, 0])
        h = sdf_s3d.PyShape.hull(a, b)
        assert a._mesh_cache is None, "constructing the hull must not mesh its children"
        assert b._mesh_cache is None
        h.mesh().sample(0, 0, 0)
        assert a._mesh_cache is not None, "sampling the hull meshes the children (once)"

    def test_hull_mixes_shapes_and_raw_points(self) -> None:
        base = sdf_s3d.cuboid(size=[16.0, 16.0, 8.0], res=8)
        h = sdf_s3d.PyShape.hull(base, [[0.0, 0.0, 18.0]]).mesh()
        assert h.sample(0, 0, 12) < 0, "on the axis of the spike, between base and apex"
        assert h.sample(0, 0, 19) > 0, "past the apex"
        assert h.sample(7, 7, 12) > 0, "outside the taper"

    def test_hull_of_raw_points_matches_convex_polyhedron(self) -> None:
        pts = [[0, 0, 0], [10, 0, 0], [0, 10, 0], [0, 0, 10]]
        h = sdf_s3d.PyShape.hull(pts).mesh()  # type: ignore[arg-type]
        ref = sdf_s3d.convex_polyhedron(pts).mesh()
        for p in [(2, 2, 2), (5, 5, 5), (-1, -1, -1), (3, 0, 0)]:
            assert math.isclose(float(h.sample(*p)), float(ref.sample(*p)), abs_tol=10 ** (-9))


class TestCuboid:
    def test_sharp_box_matches_reference_formula(self) -> None:
        size, b = [10.0, 10.0, 10.0], [5.0, 5.0, 5.0]
        shape = sdf_s3d.cuboid(size=size, edges="NONE").mesh()
        for p in [(4.9, 0, 0), (0, -4.9, 0), (0, 0, 4.9), (0, 0, 0), (2, 2, 2)]:
            assert math.isclose(float(shape.sample(*p)), float(_sharp_box_sdf(p, b)), abs_tol=10 ** (-9))  # type: ignore[arg-type]

    def test_edges_all_rounding_matches_classic_formula(self) -> None:
        size, b, r = [10.0, 10.0, 10.0], [5.0, 5.0, 5.0], 2.0
        shape = sdf_s3d.cuboid(size=size, rounding=r, edges="ALL").mesh()
        for p in [
            (5, 0, 0),
            (0, 5, 0),
            (3, 3, 0),
            (3, 0, 3),
            (4, 4, 4),
            (10, 10, 10),
            (0, 0, 0),
            (-4, -4, -4),
        ]:
            assert math.isclose(float(shape.sample(*p)), float(_round_box_sdf(p, b, r)), abs_tol=10 ** (-9))  # type: ignore[arg-type]

    def test_rounding_zero_degenerates_to_sharp_box(self) -> None:
        size, b = [8.0, 8.0, 8.0], [4.0, 4.0, 4.0]
        shape = sdf_s3d.cuboid(size=size, rounding=0, edges="ALL").mesh()
        for p in [(3, 0, 0), (0, 0, 0), (1, 1, 1)]:
            assert math.isclose(float(shape.sample(*p)), float(_sharp_box_sdf(p, b)), abs_tol=10 ** (-9))  # type: ignore[arg-type]

    def test_per_edge_rounding_only_affects_selected_edges(self) -> None:
        size, r = [10.0, 10.0, 10.0], 2.0
        shape = sdf_s3d.cuboid(size=size, rounding=r, edges=[list(TOP + LEFT), list(TOP + RIGHT)]).mesh()
        assert math.isclose(float(shape.sample(-5, 0, 5)), float(round_offset(r)), abs_tol=10 ** (-6)), (
            "TOP+LEFT selected"
        )
        assert math.isclose(float(shape.sample(5, 0, 5)), float(round_offset(r)), abs_tol=10 ** (-6)), (
            "TOP+RIGHT selected"
        )
        assert math.isclose(float(shape.sample(-5, 0, -5)), float(0), abs_tol=10 ** (-9)), "BOTTOM+LEFT unselected"
        assert math.isclose(float(shape.sample(0, -5, 5)), float(0), abs_tol=10 ** (-9)), "TOP+FRONT unselected"
        assert math.isclose(float(shape.sample(5, 5, 0)), float(0), abs_tol=10 ** (-9)), "vertical edge unselected"

    def test_edges_z_shorthand_rounds_only_vertical_edges(self) -> None:
        size, r = [10.0, 10.0, 10.0], 2.0
        shape = sdf_s3d.cuboid(size=size, rounding=r, edges="Z").mesh()
        assert math.isclose(
            float(shape.sample(5, 5, 0)),
            float(round_offset(r)),
            abs_tol=10 ** (-6),
        ), "vertical edge selected"
        assert math.isclose(
            float(shape.sample(5, 5, -3)),
            float(round_offset(r)),
            abs_tol=10 ** (-6),
        ), "vertical edge, off-center"
        assert math.isclose(float(shape.sample(-5, 0, 5)), float(0), abs_tol=10 ** (-9)), (
            "top horizontal edge unselected"
        )
        assert math.isclose(
            float(shape.sample(0, -5, -5)),
            float(0),
            abs_tol=10 ** (-9),
        ), "bottom horizontal edge unselected"

    def test_per_edge_chamfer(self) -> None:
        size, c = [10.0, 10.0, 10.0], 2.0
        shape = sdf_s3d.cuboid(size=size, chamfer=c, edges=[list(TOP + LEFT), list(TOP + RIGHT)]).mesh()
        assert math.isclose(float(shape.sample(-5, 0, 5)), float(chamfer_offset(c)), abs_tol=10 ** (-9))
        assert math.isclose(float(shape.sample(5, 0, 5)), float(chamfer_offset(c)), abs_tol=10 ** (-9))
        assert math.isclose(float(shape.sample(-5, 0, -5)), float(0), abs_tol=10 ** (-9))

    def test_rounding_and_chamfer_are_mutually_exclusive(self) -> None:
        with pytest.raises(AssertionError):
            sdf_s3d.cuboid(size=[10.0, 10.0, 10.0], rounding=1, chamfer=1)

    def test_round_then_chamfer_compose(self) -> None:
        size, r, c = [10.0, 10.0, 10.0], 2.0, 1.5
        shape = sdf_s3d.cuboid(size=size).round(r, edges="Z").chamfer(c, edges=[list(TOP + FRONT)]).mesh()
        assert math.isclose(
            float(shape.sample(5, 5, 0)),
            float(round_offset(r)),
            abs_tol=10 ** (-6),
        ), "Z-rounded vertical edge"
        assert math.isclose(
            float(shape.sample(0, -5, 5)),
            float(chamfer_offset(c)),
            abs_tol=10 ** (-9),
        ), "chamfered TOP+FRONT edge"

    def test_translate_then_chamfer_composes_correctly(self) -> None:
        size, c = [10.0, 10.0, 10.0], 2.0
        shape = sdf_s3d.cuboid(size=size).translate([100, 0, 0]).chamfer(c, edges=[list(TOP + LEFT)]).mesh()
        assert math.isclose(float(shape.sample(95, 0, 5)), float(chamfer_offset(c)), abs_tol=10 ** (-9))
        assert math.isclose(float(shape.sample(95, 0, -5)), float(0), abs_tol=10 ** (-9))

    def test_cube_is_a_plain_cuboid(self) -> None:
        shape = sdf_s3d.cube(size=10).mesh()
        assert math.isclose(float(shape.sample(5, 0, 0)), float(0), abs_tol=1e-7)
        assert shape.sample(0, 0, 0) < 0

    def test_negative_rounding_flares_selected_edge(self) -> None:
        shape = sdf_s3d.cuboid([20.0, 20.0, 10.0], rounding=-2, edges=[list(BACK + TOP)]).mesh()
        assert shape.sample(0, 10.5, 4.5) < 0, "inside the flare wing"
        assert shape.sample(0, 11.5, 3.3) > 0, "carved by the concave arc"
        assert shape.sample(0, 11, 5.2) > 0, "above the top face"
        assert shape.sample(0, 9, 0) < 0, "plain box interior intact"
        assert shape.sample(0, -10.5, 4.5) > 0, "unselected FRONT+TOP edge unflared"
        assert shape.mx[1] >= 12.0, "bounds cover the flare wing"
        assert shape.mx[1] < 12.5, "bounds not wildly padded"
        assert shape.mn[1] > -10.5, "unflared side bounds untouched (minus padding)"

    def test_negative_rounding_rejects_z_edges(self) -> None:
        with pytest.raises(AssertionError):
            sdf_s3d.cuboid([20.0, 20.0, 10.0], rounding=-2, edges="Z")


class TestOctahedron:
    def test_l1_ball_sdf(self) -> None:
        s = 10
        shape = sdf_s3d.octahedron(size=s).mesh()
        assert math.isclose(float(shape.sample(s / 2, 0, 0)), float(0), abs_tol=1e-7)
        assert math.isclose(float(shape.sample(s / 4, 0, 0)), float(-s / 4), abs_tol=1e-7)
        assert shape.sample(s, s, s) > 0


class TestWedge:
    def test_right_angle_and_hypotenuse(self) -> None:
        by, bz = 3, 4
        shape = sdf_s3d.wedge(size=[10, 6, 8], anchor=CENTER).mesh()
        assert math.isclose(float(shape.sample(0, -by, -bz)), float(0), abs_tol=1e-7), "right-angle vertex"
        assert shape.sample(0, -1, -1) < 0, "biased toward the right-angle corner"
        assert math.isclose(float(shape.sample(0, -by, bz)), float(0), abs_tol=1e-7), (
            "a real vertex on the hypotenuse edge"
        )
        assert shape.sample(0, by, bz) > 0, "the removed corner"
        assert math.isclose(float(shape.sample(0, by, -bz)), float(0), abs_tol=1e-7), "another real vertex"


class TestScale:
    def test_uniform_scale_moves_surface_and_keeps_distance_calibrated(self) -> None:
        shape = sdf_s3d.cuboid([10.0, 10.0, 10.0]).scale(2).mesh()
        assert math.isclose(float(shape.sample(10, 0, 0)), float(0), abs_tol=10 ** (-9)), "face scaled out to +-10"
        assert math.isclose(
            float(shape.sample(12, 0, 0)),
            float(2),
            abs_tol=10 ** (-9),
        ), "uniform scaling keeps exact distance"
        assert math.isclose(float(shape.sample(0, 0, 0)), float(-10), abs_tol=10 ** (-9))

    def test_per_axis_scale_zero_set(self) -> None:
        shape = sdf_s3d.cuboid([10.0, 10.0, 10.0]).scale([2, 1, 0.5]).mesh()
        assert math.isclose(float(shape.sample(10, 0, 0)), float(0), abs_tol=10 ** (-9)), "x face at +-10"
        assert math.isclose(float(shape.sample(0, 5, 0)), float(0), abs_tol=10 ** (-9)), "y face unchanged"
        assert math.isclose(float(shape.sample(0, 0, 2.5)), float(0), abs_tol=10 ** (-9)), "z face squashed to +-2.5"
        assert shape.sample(0, 0, 0) < 0
        assert shape.sample(0, 0, 3) > 0

    def test_scale_drops_cuboid_metadata(self) -> None:
        with pytest.raises(AssertionError):
            sdf_s3d.cuboid([10.0, 10.0, 10.0]).scale(2).round(1, edges="Z")

    def test_rejects_nonpositive_factors(self) -> None:
        with pytest.raises(AssertionError):
            sdf_s3d.cuboid([10.0, 10.0, 10.0]).scale([1, -1, 1])


class TestConvexPolyhedron:
    def test_tetrahedron_from_vertices(self) -> None:
        pts = [[0, 0, 0], [10, 0, 0], [0, 10, 0], [0, 0, 10]]
        shape = sdf_s3d.convex_polyhedron(pts).mesh()
        assert shape.sample(1, 1, 1) < 0, "inside near the right-angle corner"
        assert math.isclose(float(shape.sample(5, 0, 5)), float(0), abs_tol=10 ** (-9)), "on the x/z face"
        assert shape.sample(5, 5, 5) > 0, "outside the diagonal face"
        assert math.isclose(
            float(shape.sample(-3, 3, 3)),
            float(3),
            abs_tol=10 ** (-9),
        ), "exact perpendicular distance at a face"

    def test_octahedron_matches_builtin_zero_set(self) -> None:
        s = 10.0
        h = s / 2
        pts = [[h, 0, 0], [-h, 0, 0], [0, h, 0], [0, -h, 0], [0, 0, h], [0, 0, -h]]
        hulled = sdf_s3d.convex_polyhedron(pts).mesh()
        builtin = sdf_s3d.octahedron(size=s).mesh()
        face_pt = (h / 3, h / 3, h / 3)
        assert math.isclose(float(hulled.sample(*face_pt)), float(0), abs_tol=10 ** (-9))
        assert math.isclose(float(builtin.sample(*face_pt)), float(0), abs_tol=10 ** (-9))
        for p in [(1, 1, 1), (h, h, h), (0, 0, 0), (2, 0, 0), (h + 1, 0, 0)]:
            assert (hulled.sample(*p) > 0) == (builtin.sample(*p) > 0), f"sign disagreement at {p}"

    def test_interior_points_do_not_make_planes(self) -> None:
        pts = [[0, 0, 0], [10, 0, 0], [0, 10, 0], [0, 0, 10], [2, 2, 2]]
        with_interior = sdf_s3d.convex_polyhedron(pts).mesh()
        without = sdf_s3d.convex_polyhedron(pts[:4]).mesh()
        for p in [(1, 1, 1), (5, 5, 5), (-3, 3, 3), (5, 0, 5)]:
            assert math.isclose(float(with_interior.sample(*p)), float(without.sample(*p)), abs_tol=10 ** (-9))

    def test_rejects_too_few_or_coplanar_points(self) -> None:
        with pytest.raises(AssertionError):
            sdf_s3d.convex_polyhedron([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
        with pytest.raises(AssertionError):
            sdf_s3d.convex_polyhedron([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]])


class TestSphere:
    def test_sphere(self) -> None:
        shape = sdf_s3d.sphere(radius=5).mesh()
        assert math.isclose(float(shape.sample(5, 0, 0)), float(0), abs_tol=1e-7)
        assert math.isclose(float(shape.sample(0, 0, 0)), float(-5), abs_tol=1e-7)
        assert math.isclose(float(shape.sample(10, 0, 0)), float(5), abs_tol=1e-7)

    def test_spheroid_is_a_plain_sphere(self) -> None:
        shape = sdf_s3d.spheroid(radius=3).mesh()
        assert math.isclose(float(shape.sample(3, 0, 0)), float(0), abs_tol=1e-7)


class TestTorus:
    def test_torus(self) -> None:
        shape = sdf_s3d.torus(major_radius=10, minor_radius=2).mesh()
        assert math.isclose(float(shape.sample(10, 0, 0)), float(-2), abs_tol=1e-7), "center of the tube ring"
        assert math.isclose(float(shape.sample(12, 0, 0)), float(0), abs_tol=1e-7), "outer equator"
        assert math.isclose(float(shape.sample(8, 0, 0)), float(0), abs_tol=1e-7), "inner equator"
        assert math.isclose(float(shape.sample(10, 0, 2)), float(0), abs_tol=1e-7), "top of the tube"


class TestCylinders:
    def test_plain_cylinder(self) -> None:
        shape = sdf_s3d.cylinder(height=10, radius=5).mesh()
        assert math.isclose(float(shape.sample(5, 0, 0)), float(0), abs_tol=1e-7)
        assert math.isclose(float(shape.sample(0, 0, 5)), float(0), abs_tol=1e-7)
        assert shape.sample(0, 0, 0) < 0

    def test_tapered_cylinder(self) -> None:
        shape = sdf_s3d.cylinder(height=10, radius1=5, radius2=2).mesh()
        assert math.isclose(float(shape.sample(5, 0, -5)), float(0), abs_tol=10 ** (-3)), "bottom rim"
        assert math.isclose(float(shape.sample(2, 0, 5)), float(0), abs_tol=10 ** (-3)), "top rim"

    def test_cyl_uniform_rounding(self) -> None:
        r = 1.0
        shape = sdf_s3d.cyl(height=10, radius=5, rounding=r).mesh()
        assert math.isclose(float(shape.sample(5, 0, 5)), float(round_offset(r)), abs_tol=10 ** (-6)), "rim corner"
        assert math.isclose(float(shape.sample(5, 0, 0)), float(0), abs_tol=10 ** (-9)), "flat side wall"
        assert math.isclose(float(shape.sample(0, 0, 5)), float(0), abs_tol=10 ** (-9)), "flat top cap"

    def test_cyl_independent_top_bottom_chamfer(self) -> None:
        c2 = 1.5
        shape = sdf_s3d.cyl(height=10, radius=5, chamfer1=0, chamfer2=c2).mesh()
        assert math.isclose(float(shape.sample(5, 0, 5)), float(chamfer_offset(c2)), abs_tol=10 ** (-6)), (
            "chamfered top rim"
        )
        assert math.isclose(float(shape.sample(5, 0, -5)), float(0), abs_tol=10 ** (-9)), "unchamfered bottom rim"

    def test_cyl_rounding_and_chamfer_are_mutually_exclusive(self) -> None:
        with pytest.raises(AssertionError):
            sdf_s3d.cyl(height=10, radius=5, rounding=1, chamfer=1)

    def test_xcyl_ycyl_zcyl_orient_the_axis(self) -> None:
        for shape_fn, expect_axial, expect_radial in [
            (sdf_s3d.xcyl, (5, 0, 0), [(0, 5, 0), (0, 0, 5)]),
            (sdf_s3d.ycyl, (0, 5, 0), [(5, 0, 0), (0, 0, 5)]),
            (sdf_s3d.zcyl, (0, 0, 5), [(5, 0, 0), (0, 5, 0)]),
        ]:
            shape = shape_fn(height=10, radius=5).mesh()
            assert math.isclose(float(shape.sample(*expect_axial)), float(0), abs_tol=1e-7), (
                f"{shape_fn.__name__} end cap"
            )
            for p in expect_radial:
                assert math.isclose(float(shape.sample(*p)), float(0), abs_tol=1e-7), f"{shape_fn.__name__} wall"
            assert shape.sample(0, 0, 0) < 0


class TestMirror:
    def test_mirror_z_flips_a_cone(self) -> None:
        cone = sdf_s3d.cylinder(height=8, radius1=4, radius2=0.01, center=False)
        flipped = cone.mirror([0, 0, 1]).mesh()
        assert flipped.sample(3, 0, -0.5) < 0, "wide base now just below z=0"
        assert flipped.sample(3, 0, 0.5) > 0, "nothing above z=0 at r=3"
        assert flipped.sample(0, 0, -7.5) < 0, "apex now at the bottom"
        assert flipped.mx[2] <= 0.5, "bounds flipped below the plane"

    def test_mirror_diagonal_normal_swaps_axes(self) -> None:
        box = sdf_s3d.cuboid([10, 2, 2]).translate([10, 0, 0])
        swapped = box.mirror([1, -1, 0]).mesh()
        assert swapped.sample(0, 10, 0) < 0, "long axis now along y"
        assert swapped.sample(10, 0, 0) > 0, "original position empty"


class TestCylShift:
    def test_oblique_cone_top_lands_at_shift(self) -> None:
        shape = sdf_s3d.cyl(height=10, radius1=4, radius2=2, shift=[6, 0]).mesh()
        assert shape.sample(0, 0, -4.9) < 0, "bottom center solid"
        assert shape.sample(6, 0, 4.9) < 0, "top center slid to x=6"
        assert shape.sample(0, 0, 4.9) > 0, "original top center now empty"
        assert shape.sample(6, 0, 5.1) > 0, "above the top face"

    def test_shift_rejects_rounding(self) -> None:
        with pytest.raises(AssertionError):
            sdf_s3d.cyl(height=10, radius=4, shift=[2, 0], rounding=1)


class TestTubes:
    def test_tube(self) -> None:
        shape = sdf_s3d.tube(height=10, outer_radius=5, inner_radius=3).mesh()
        assert math.isclose(float(shape.sample(5, 0, 0)), float(0), abs_tol=1e-7), "outer wall"
        assert math.isclose(float(shape.sample(3, 0, 0)), float(0), abs_tol=1e-7), "inner wall"
        assert shape.sample(4, 0, 0) < 0, "inside the wall material"
        assert shape.sample(1, 0, 0) > 0, "inside the hollow bore"

    def test_tube_requires_enough_parameters(self) -> None:
        with pytest.raises(AssertionError):
            sdf_s3d.tube(height=10)

    def test_rect_tube(self) -> None:
        shape = sdf_s3d.rect_tube(height=10, size=[20, 16], isize=[16, 12], anchor=CENTER).mesh()
        assert math.isclose(float(shape.sample(10, 0, 0)), float(0), abs_tol=1e-7), "outer wall"
        assert math.isclose(float(shape.sample(8, 0, 0)), float(0), abs_tol=1e-7), "inner wall"
        assert shape.sample(9, 0, 0) < 0, "in the wall"
        assert shape.sample(0, 0, 0) > 0, "in the hollow bore"


class TestPieSlice:
    def test_acute_sector(self) -> None:
        shape = sdf_s3d.pie_slice(height=10, radius=5, angle=90).mesh()
        assert shape.sample(3, 3, 0) < 0, "inside the 90deg wedge (Q1)"
        assert shape.sample(-3, 3, 0) > 0, "Q2 excluded"
        assert shape.sample(3, -3, 0) > 0, "Q4 excluded"

    def test_reflex_sector(self) -> None:
        shape = sdf_s3d.pie_slice(height=10, radius=5, angle=270).mesh()
        assert shape.sample(3, 3, 0) < 0, "Q1 included"
        assert shape.sample(-3, 3, 0) < 0, "Q2 included"
        assert shape.sample(-3, -3, 0) < 0, "Q3 included"
        assert shape.sample(3, -3, 0) > 0, "Q4 (270-360) excluded"


class TestPrismoid:
    def test_non_tapered_matches_plain_box(self) -> None:
        shape = sdf_s3d.prismoid(size1=[10, 10], size2=[10, 10], height=10, anchor=CENTER).mesh()
        assert math.isclose(float(shape.sample(5, 0, 0)), float(0), abs_tol=1e-7)
        assert math.isclose(float(shape.sample(0, 0, 5)), float(0), abs_tol=1e-7)
        assert shape.sample(0, 0, 0) < 0

    def test_tapered(self) -> None:
        shape = sdf_s3d.prismoid(size1=[20, 20], size2=[10, 10], height=10, anchor=CENTER).mesh()
        assert math.isclose(float(shape.sample(10, 0, -5)), float(0), abs_tol=10 ** (-3)), "bottom rim (wider)"
        assert math.isclose(float(shape.sample(5, 0, 5)), float(0), abs_tol=10 ** (-3)), "top rim (narrower)"
        assert shape.sample(0, 0, 0) < 0


class TestInteriorFillet:
    def test_90_degree_fillet(self) -> None:
        shape = sdf_s3d.interior_fillet(length=10, radius=2, anchor=CENTER).mesh()
        assert shape.sample(0.5, 0, 0.5) < 0, "near-corner sliver, inside the fillet"
        assert shape.sample(2, 0, 2) > 0, "circle center, the carved-out hole"
        assert shape.sample(1.5, 0, 1.5) > 0, "past the arc, inside the removed circle"
        assert shape.sample(-1, 0, 1) > 0, "outside the wedge entirely"


class TestPositionableCutters:
    """rounding_edge_mask()/polygon_extrude(): standalone cutters."""

    def test_rounding_edge_mask(self) -> None:
        shape = sdf_s3d.rounding_edge_mask(length=10, radius=2).mesh()
        assert shape.sample(0, 0, 0) < 0, "sharp corner, inside the cutter"
        assert shape.sample(2, 2, 0) > 0, "far corner (circle center), outside the cutter"
        assert math.isclose(float(shape.sample(2, 0, 0)), float(0), abs_tol=10 ** (-9)), "tangent point on the flat"
        assert shape.sample(-1, 0.5, 0) > 0, "past the excess skirt, outside the cutter"
        assert shape.sample(0, 0, 6) > 0, "past the swept length, outside the cutter"

    def test_polygon_extrude(self) -> None:
        shape = sdf_s3d.polygon_extrude([[0, 0], [4, 0], [0, 4]], length=10).mesh()
        assert shape.sample(1, 1, 0) < 0, "inside the triangle"
        assert shape.sample(3, 3, 0) > 0, "outside the hypotenuse"
        assert shape.sample(-1, 1, 0) > 0, "outside the left edge"
        assert shape.sample(1, 1, 6) > 0, "past the swept length"

    def test_polygon_extrude_accepts_either_winding_order(self) -> None:
        pts = [[0, 0], [4, 0], [0, 4]]
        a = sdf_s3d.polygon_extrude(pts, length=10).mesh()
        b = sdf_s3d.polygon_extrude(list(reversed(pts)), length=10).mesh()
        for p in [(1, 1, 0), (3, 3, 0), (-1, 1, 0)]:
            assert math.isclose(float(a.sample(*p)), float(b.sample(*p)), abs_tol=10 ** (-9))


class TestPolygonPrism:
    """polygon_prism(): the exact winding-number polygon SDF plus offset_sweep-style rim
    treatments."""

    L_PATH = [[0, 0], [40, 0], [40, 15], [15, 15], [15, 40], [0, 40]]

    def test_concave_polygon_sign_is_exact(self) -> None:
        shape = sdf_s3d.polygon_prism(self.L_PATH, height=10).mesh()
        assert shape.sample(5, 5, 5) < 0, "inside the corner arm"
        assert shape.sample(30, 7, 5) < 0, "inside the X arm"
        assert shape.sample(7, 30, 5) < 0, "inside the Y arm"
        assert shape.sample(30, 30, 5) > 0, "in the concave notch -- outside"
        assert shape.sample(-5, 5, 5) > 0, "left of the outline"
        assert shape.sample(5, 5, 11) > 0, "above the prism"
        assert shape.sample(5, 5, -1) > 0, "below the prism"

    def test_distance_is_face_exact_and_sign_correct_past_vertices(self) -> None:
        shape = sdf_s3d.polygon_prism(self.L_PATH, height=10).mesh()
        assert math.isclose(float(shape.sample(20, 20, 5)), float(5.0), abs_tol=10 ** (-9))
        assert math.isclose(float(shape.sample(-5, 20, 5)), float(5.0), abs_tol=10 ** (-9)), "outside a hull face"
        v = shape.sample(45, -5, 5)
        assert v > 0
        assert v <= math.hypot(5, 5) + 1e-9

    def test_boundary_reads_zero(self) -> None:
        shape = sdf_s3d.polygon_prism(self.L_PATH, height=10).mesh()
        assert math.isclose(float(shape.sample(0, 20, 5)), float(0), abs_tol=10 ** (-9)), "on the left face"
        assert math.isclose(float(shape.sample(20, 15, 5)), float(0), abs_tol=10 ** (-9)), "on the notch face"
        assert math.isclose(float(shape.sample(20, 7, 10)), float(0), abs_tol=10 ** (-9)), "on the top face"

    def test_either_winding_order(self) -> None:
        a = sdf_s3d.polygon_prism(self.L_PATH, height=10).mesh()
        b = sdf_s3d.polygon_prism(list(reversed(self.L_PATH)), height=10).mesh()
        for p in [(5, 5, 5), (30, 30, 5), (45, -5, 5)]:
            assert math.isclose(float(a.sample(*p)), float(b.sample(*p)), abs_tol=10 ** (-9))

    def test_top_roundover_rim(self) -> None:
        r = 2.0
        shape = sdf_s3d.polygon_prism(self.L_PATH, height=10, rounding_top=r).mesh()
        k = r - r / math.sqrt(2)
        assert math.isclose(
            float(shape.sample(-0 + k, 20, 10 - k)),
            float(0),
            abs_tol=10 ** (-9),
        ), "45-degree point of the rim arc"
        assert shape.sample(0.01, 20, 9.99) > 0, "sharp top corner is rounded away"
        assert math.isclose(float(shape.sample(0, 20, 5)), float(0), abs_tol=10 ** (-9)), (
            "wall below the rim unaffected"
        )
        assert math.isclose(float(shape.sample(20, 7, 0)), float(0), abs_tol=10 ** (-9)), "square bottom rim unaffected"

    def test_bottom_roundover_rim(self) -> None:
        r = 2.0
        shape = sdf_s3d.polygon_prism(self.L_PATH, height=10, rounding_bottom=r).mesh()
        k = r - r / math.sqrt(2)
        assert math.isclose(float(shape.sample(k, 20, k)), float(0), abs_tol=10 ** (-9))
        assert shape.sample(0.01, 20, 0.01) > 0, "sharp bottom corner is rounded away"
        assert math.isclose(float(shape.sample(20, 7, 10)), float(0), abs_tol=10 ** (-9)), "square top rim unaffected"

    def test_top_flare_adds_material_outside_the_wall(self) -> None:
        f = 2.0
        shape = sdf_s3d.polygon_prism(self.L_PATH, height=10, rounding_top=-f).mesh()
        assert shape.sample(-1, 20, 5) > 0, "mid-wall not flared"
        assert shape.sample(-1, 20, 9.9) < 0, "inside the flare near the top"
        assert shape.sample(-1, 20, 10.1) > 0, "above the rim plane"
        u = f - f / math.sqrt(2)
        w = 10 - f + f / math.sqrt(2)
        assert math.isclose(float(shape.sample(-u, 20, w)), float(0), abs_tol=10 ** (-6))

    def test_region_of_disjoint_islands(self) -> None:
        square_a = [[0, 0], [10, 0], [10, 10], [0, 10]]
        square_b = [[20, 0], [30, 0], [30, 10], [20, 10]]
        shape = sdf_s3d.polygon_prism([square_a, square_b], height=5).mesh()
        assert shape.sample(5, 5, 2) < 0, "inside island A"
        assert shape.sample(25, 5, 2) < 0, "inside island B"
        assert shape.sample(15, 5, 2) > 0, "in the gap between islands"

    def test_rejects_bad_arguments(self) -> None:
        with pytest.raises(AssertionError):
            sdf_s3d.polygon_prism(self.L_PATH, height=0)
        with pytest.raises(AssertionError):
            sdf_s3d.polygon_prism([[0, 0], [1, 0]], height=5)
        with pytest.raises(AssertionError):
            sdf_s3d.polygon_prism(self.L_PATH, height=5, rounding_top=6)


class TestTeardropAndOnion:
    def test_teardrop(self) -> None:
        r, angle = 3, 45
        shape = sdf_s3d.teardrop(height=6, radius=r, angle=angle, anchor=CENTER).mesh()
        assert math.isclose(float(shape.sample(r, 0, 0)), float(0), abs_tol=1e-7), "equator"
        assert shape.sample(0, 0, 0) < 0, "center"
        apex = r / math.sin(math.radians(angle))
        assert math.isclose(float(shape.sample(0, 0, apex)), float(0), abs_tol=10 ** (-3)), "apex"
        assert shape.sample(0, 0, apex + 1) > 0

    def test_teardrop_roof_plane(self) -> None:
        r, angle = 3, 45
        shape = sdf_s3d.teardrop(height=6, radius=r, angle=angle, anchor=CENTER).mesh()
        apex = r / math.sin(math.radians(angle))
        v = apex * 0.7
        u = (r - v * math.cos(math.radians(angle))) / math.sin(math.radians(angle))
        assert math.isclose(float(shape.sample(u, 0, v)), float(0), abs_tol=10 ** (-3))

    def test_onion(self) -> None:
        r, angle = 3, 45
        shape = sdf_s3d.onion(radius=r, angle=angle, anchor=CENTER).mesh()
        assert math.isclose(float(shape.sample(r, 0, 0)), float(0), abs_tol=1e-7)
        assert shape.sample(0, 0, 0) < 0
        apex = r / math.sin(math.radians(angle))
        assert math.isclose(float(shape.sample(0, 0, apex)), float(0), abs_tol=10 ** (-3))


class TestHeightfield:
    def test_flat_heightfield(self) -> None:
        shape = sdf_s3d.heightfield(lambda _x, _y: 5, size=[20, 20], bottom=-5, maxz=10).mesh()
        assert math.isclose(float(shape.sample(0, 0, 5)), float(0), abs_tol=1e-7)
        assert shape.sample(0, 0, 0) < 0
        assert shape.sample(0, 0, 10) > 0

    def test_varying_heightfield(self) -> None:
        shape = sdf_s3d.heightfield(lambda x, _y: x * 0.1, size=[20, 20], bottom=-5, maxz=10).mesh()
        assert math.isclose(float(shape.sample(10, 0, 1)), float(0), abs_tol=1e-7)

    def test_rejects_non_callable_data(self) -> None:
        with pytest.raises(AssertionError):
            sdf_s3d.heightfield([[1, 2], [3, 4]], size=[20, 20])  # type: ignore[arg-type]


class TestRegularPrism:
    """regular_prism (n-gon prism) -- SDF via polygon_prism()."""

    def test_hex_prism_builds(self) -> None:
        shape = sdf_s3d.regular_prism(num_sides=6, height=10, radius=8).mesh()
        assert math.isclose(float(shape.sample(8, 0, 0)), float(0), abs_tol=10 ** (-3)), "vertex on surface"
        assert shape.sample(0, 0, 5) < 0, "interior is inside"

    def test_triangle_prism_with_side_length(self) -> None:
        shape = sdf_s3d.regular_prism(num_sides=3, height=6, side=9).mesh()
        assert math.isclose(float(shape.sample(5.196, 0, 0)), float(0), abs_tol=10 ** (-3)), "vertex on surface"
        assert shape.sample(0, 0, 3) < 0, "interior is inside"

    def test_pentagon_with_inner_radius(self) -> None:
        shape = sdf_s3d.regular_prism(num_sides=5, height=5, inner_radius=6).mesh()
        assert shape.sample(0, 0, 2.5) < 0, "interior is inside"

    def test_realign_rotates_half_a_facet(self) -> None:
        shape = sdf_s3d.regular_prism(num_sides=4, height=4, radius=10).mesh()
        assert abs(shape.sample(10, 0, 0)) < 0.01 or abs(shape.sample(0, 10, 0)) < 0.01, (
            "a square's vertex or face centre sits on an axis"
        )

    def test_size_error_when_no_size_given(self) -> None:
        with pytest.raises(ValueError, match="need one of"):
            sdf_s3d.regular_prism()


def _sharp_box_sdf(p: list[float], b: list[float]) -> float:
    q = [abs(p[i]) - b[i] for i in range(3)]
    return math.hypot(*[max(0, v) for v in q]) + min(max(q[0], q[1], q[2]), 0)


def _round_box_sdf(p: list[float], b: list[float], r: float) -> float:
    q = [abs(p[i]) - b[i] + r for i in range(3)]
    return math.hypot(*[max(0, v) for v in q]) + min(max(q[0], q[1], q[2]), 0) - r


class TestSdfDistributors:
    def test_xcopies_on_sdf(self) -> None:
        from pybosl2.solid import sphere, use_backend  # type: ignore[attr-defined]

        with use_backend("sdf"):
            s = sphere(radius=5)
            # Distribute two copies of the sphere at x=-10 and x=10
            distributed = s.xcopies(spacing=20, num_copies=2)

            # The result must be a list of PyShapes
            assert isinstance(distributed, list)
            assert len(distributed) == 2
            assert distributed[0].backend == "sdf"

            # Union the copies for combined bounding box checks
            combined = distributed[0] | distributed[1]

            # Check the bounding box: two spheres at [-10, 0, 0] and [10, 0, 0]
            # Each has radius 5, so combined x should span from -15 to 15,
            # y from -5 to 5, z from -5 to 5.
            assert math.isclose(float(combined.mn[0]), float(-15.0), abs_tol=1e-7)
            assert math.isclose(float(combined.mx[0]), float(15.0), abs_tol=1e-7)

            # Verify the shape is correctly Union-ed by sampling the points
            mesh = combined.mesh()
            assert mesh.sample(-10, 0, 0) < 0
            assert mesh.sample(10, 0, 0) < 0
            assert mesh.sample(0, 0, 0) > 0

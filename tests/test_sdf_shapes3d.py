# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

import math

import pytest

from pybosl2._edges_lang import Anchor
from pybosl2.sdf import shapes3d as sdf_s3d
from pybosl2.sdf._constants import BACK, CENTER, FRONT, LEFT, RIGHT, TOP

SQRT2 = math.sqrt(2)


def round_offset(r: float) -> float:
    """Distance from a sharp right-angle corner to a fillet of radius `r` rounding it --
    the classic `r*(sqrt(2)-1)` relationship for a 2-D rounded-rect corner."""
    return r * (SQRT2 - 1)


def _csg_operable_mesh() -> bool:
    """True if a meshed SDF solid can go into the CSG boolean operators.

    Without libfive the suite falls back to the numeric mock, whose ``to_csg()`` yields a stand-in
    the native operators reject -- so anything that meshes *and then* cuts is unverifiable here.
    These used to `except (AttributeError, ValueError, TypeError): pass`, which is a test that
    cannot fail; skipping says the same thing out loud.
    """
    try:
        meshed = sdf_s3d.cuboid([2, 2, 2]).to_csg()
        _ = meshed.shape & meshed.shape
    except Exception:
        return False
    return True


needs_csg_operable_mesh = pytest.mark.skipif(
    not _csg_operable_mesh(), reason="no libfive: a meshed SDF solid cannot enter the CSG operators"
)


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
        with pytest.raises(ValueError, match=r"round\(\) requires a"):
            s.round(1)
        with pytest.raises(ValueError, match=r"chamfer\(\) requires a"):
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
        with pytest.raises(ValueError, match=r"round\(\) requires a"):
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
        with pytest.raises(ValueError, match="every argument must be a"):
            sdf_s3d.PyShape.union(sdf_s3d.cuboid(size=[6.0, 6.0, 6.0]), "not a shape")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="need at least one"):
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
        with pytest.raises(ValueError, match="bounding boxes"):
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
        shape = sdf_s3d.cuboid(size=size, edges=Anchor.NONE).mesh()
        for p in [(4.9, 0, 0), (0, -4.9, 0), (0, 0, 4.9), (0, 0, 0), (2, 2, 2)]:
            assert math.isclose(float(shape.sample(*p)), float(_sharp_box_sdf(p, b)), abs_tol=10 ** (-9))  # type: ignore[arg-type]

    def test_edges_all_rounding_matches_classic_formula(self) -> None:
        size, b, r = [10.0, 10.0, 10.0], [5.0, 5.0, 5.0], 2.0
        shape = sdf_s3d.cuboid(size=size, rounding=r, edges=Anchor.ALL).mesh()
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
        shape = sdf_s3d.cuboid(size=size, rounding=0, edges=Anchor.ALL).mesh()
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
        shape = sdf_s3d.cuboid(size=size, rounding=r, edges=Anchor.Z).mesh()
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
        with pytest.raises(ValueError, match="Cannot specify nonzero value"):
            sdf_s3d.cuboid(size=[10.0, 10.0, 10.0], rounding=1, chamfer=1)

    def test_round_then_chamfer_compose(self) -> None:
        size, r, c = [10.0, 10.0, 10.0], 2.0, 1.5
        shape = sdf_s3d.cuboid(size=size).round(r, edges=Anchor.Z).chamfer(c, edges=[list(TOP + FRONT)]).mesh()
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
        with pytest.raises(ValueError, match="Cannot use negative rounding"):
            sdf_s3d.cuboid([20.0, 20.0, 10.0], rounding=-2, edges=Anchor.Z)


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
        with pytest.raises(ValueError, match=r"round\(\) requires a"):
            sdf_s3d.cuboid([10.0, 10.0, 10.0]).scale(2).round(1, edges=Anchor.Z)

    def test_rejects_nonpositive_factors(self) -> None:
        with pytest.raises(ValueError, match=r"scale\(\) factors must be"):
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
        with pytest.raises(ValueError, match=r"convex_polyhedron\(\) needs at"):
            sdf_s3d.convex_polyhedron([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
        with pytest.raises(ValueError, match="hull planes: points are"):
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
        center, size = sdf_s3d.spheroid(radius=3).bounds()
        assert size[0] == pytest.approx(6, abs=0.01)
        assert size[1] == pytest.approx(6, abs=0.01)
        assert size[2] == pytest.approx(6, abs=0.01)


class TestTorus:
    def test_torus(self) -> None:
        shape = sdf_s3d.torus(major_radius=10, minor_radius=2).mesh()
        assert math.isclose(float(shape.sample(10, 0, 0)), float(-2), abs_tol=1e-7), "center of the tube ring"
        assert math.isclose(float(shape.sample(12, 0, 0)), float(0), abs_tol=1e-7), "outer equator"
        assert math.isclose(float(shape.sample(8, 0, 0)), float(0), abs_tol=1e-7), "inner equator"
        assert math.isclose(float(shape.sample(10, 0, 2)), float(0), abs_tol=1e-7), "top of the tube"
        center, size = sdf_s3d.torus(major_radius=10, minor_radius=2).bounds()
        assert size[0] >= 22  # major_radius + minor_radius = 12, diameter = 24
        assert size[1] >= 22
        assert size[2] >= 3  # minor_radius * 2 = 4


class TestCylinders:
    def test_plain_cylinder(self) -> None:
        shape = sdf_s3d.cylinder(height=10, radius=5).mesh()
        assert math.isclose(float(shape.sample(5, 0, 0)), float(0), abs_tol=1e-7)
        assert math.isclose(float(shape.sample(0, 0, 5)), float(0), abs_tol=1e-7)
        assert shape.sample(0, 0, 0) < 0
        center, size = sdf_s3d.cylinder(height=10, radius=5).bounds()
        assert size[2] == pytest.approx(10, abs=0.01)
        assert size[0] == pytest.approx(10, abs=0.01)  # diameter = 2*radius

    def test_tapered_cylinder(self) -> None:
        shape = sdf_s3d.cylinder(height=10, radius1=5, radius2=2).mesh()
        assert math.isclose(float(shape.sample(5, 0, -5)), float(0), abs_tol=10 ** (-3)), "bottom rim"
        assert math.isclose(float(shape.sample(2, 0, 5)), float(0), abs_tol=10 ** (-3)), "top rim"
        center, size = sdf_s3d.cylinder(height=10, radius1=5, radius2=2).bounds()
        assert size[2] == pytest.approx(10, abs=0.01)

    def test_cyl_uniform_rounding(self) -> None:
        r = 1.0
        shape = sdf_s3d.cyl(height=10, radius=5, rounding=r).mesh()
        assert math.isclose(float(shape.sample(5, 0, 5)), float(round_offset(r)), abs_tol=10 ** (-6)), "rim corner"
        assert math.isclose(float(shape.sample(5, 0, 0)), float(0), abs_tol=10 ** (-9)), "flat side wall"
        assert math.isclose(float(shape.sample(0, 0, 5)), float(0), abs_tol=10 ** (-9)), "flat top cap"
        # rounding expands bounds outward by r
        r_bounds, r_size = sdf_s3d.cyl(height=10, radius=5, rounding=r).bounds()
        p_bounds, p_size = sdf_s3d.cyl(height=10, radius=5).bounds()
        assert r_size[0] >= p_size[0], "rounding should not shrink"

    def test_cyl_independent_top_bottom_chamfer(self) -> None:
        c2 = 1.5
        shape = sdf_s3d.cyl(height=10, radius=5, chamfer1=0, chamfer2=c2).mesh()
        assert math.isclose(float(shape.sample(5, 0, 5)), float(chamfer_offset(c2)), abs_tol=10 ** (-6)), (
            "chamfered top rim"
        )
        assert math.isclose(float(shape.sample(5, 0, -5)), float(0), abs_tol=10 ** (-9)), "unchamfered bottom rim"

    def test_cyl_rounding_and_chamfer_are_mutually_exclusive(self) -> None:
        with pytest.raises(ValueError, match="Cannot specify nonzero value"):
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
        with pytest.raises(ValueError, match="shift= cannot be combined"):
            sdf_s3d.cyl(height=10, radius=4, shift=[2, 0], rounding=1)


class TestTubes:
    def test_tube(self) -> None:
        shape = sdf_s3d.tube(height=10, outer_radius=5, inner_radius=3).mesh()
        assert math.isclose(float(shape.sample(5, 0, 0)), float(0), abs_tol=1e-7), "outer wall"
        assert math.isclose(float(shape.sample(3, 0, 0)), float(0), abs_tol=1e-7), "inner wall"
        assert shape.sample(4, 0, 0) < 0, "inside the wall material"
        assert shape.sample(1, 0, 0) > 0, "inside the hollow bore"
        center, size = sdf_s3d.tube(height=10, outer_radius=5, inner_radius=3).bounds()
        assert size[2] == pytest.approx(10, abs=0.01)
        assert size[0] >= 8, "outer diameter = 10"

    def test_tube_requires_enough_parameters(self) -> None:
        with pytest.raises(ValueError, match="two of the three sizes"):
            sdf_s3d.tube(height=10)

    def test_rect_tube(self) -> None:
        shape = sdf_s3d.rect_tube(height=10, size=[20, 16], isize=[16, 12], anchor=CENTER).mesh()
        assert math.isclose(float(shape.sample(10, 0, 0)), float(0), abs_tol=1e-7), "outer wall"
        assert math.isclose(float(shape.sample(8, 0, 0)), float(0), abs_tol=1e-7), "inner wall"
        assert shape.sample(9, 0, 0) < 0, "in the wall"
        assert shape.sample(0, 0, 0) > 0, "in the hollow bore"
        center, size = sdf_s3d.rect_tube(height=10, size=[20, 16], isize=[16, 12], anchor=CENTER).bounds()
        assert size[2] == pytest.approx(10, abs=0.01)
        assert size[0] >= 18, "outer size = 20"


class TestPieSlice:
    def test_acute_sector(self) -> None:
        shape = sdf_s3d.pie_slice(height=10, radius=5, angle=90).mesh()
        assert shape.sample(3, 3, 0) < 0, "inside the 90deg wedge (Q1)"
        assert shape.sample(-3, 3, 0) > 0, "Q2 excluded"
        assert shape.sample(3, -3, 0) > 0, "Q4 excluded"
        center, size = sdf_s3d.pie_slice(height=10, radius=5, angle=90).bounds()
        assert size[2] == pytest.approx(10, abs=0.01)
        assert size[0] >= 4, "radius = 5"

    def test_reflex_sector(self) -> None:
        shape = sdf_s3d.pie_slice(height=10, radius=5, angle=270).mesh()
        assert shape.sample(3, 3, 0) < 0, "Q1 included"
        assert shape.sample(-3, 3, 0) < 0, "Q2 included"
        assert shape.sample(-3, -3, 0) < 0, "Q3 included"
        assert shape.sample(3, -3, 0) > 0, "Q4 (270-360) excluded"
        center, size = sdf_s3d.pie_slice(height=10, radius=5, angle=270).bounds()
        assert size[2] == pytest.approx(10, abs=0.01)

    @pytest.mark.parametrize(
        ("angle", "expected_mn", "expected_mx"),
        [
            # The sector sweeps 0..angle, so its box is the apex, the two arc ends, and whichever
            # axis directions the sweep passes through -- not the whole disc's box (PAR-5).
            (30, [0.0, 0.0], [10.0, 5.0]),  # 10*sin(30) = 5
            (90, [0.0, 0.0], [10.0, 10.0]),  # +Y reached exactly
            (180, [-10.0, 0.0], [10.0, 10.0]),  # a half disc, sitting on y=0
            (200, [-10.0, -3.4202], [10.0, 10.0]),  # past -X, dipping below y=0
            (270, [-10.0, -10.0], [10.0, 10.0]),  # -Y reached: three quadrants
            (359, [-10.0, -10.0], [10.0, 10.0]),  # all four axes swept
            (360, [-10.0, -10.0], [10.0, 10.0]),  # a full disc, no sector cut at all
            (0, [-10.0, -10.0], [10.0, 10.0]),  # likewise: 0 means "no wedge", not "empty"
        ],
    )
    def test_bounds_are_the_wedge_not_the_disc(
        self,
        angle: float,
        expected_mn: list[float],
        expected_mx: list[float],
    ) -> None:
        """PAR-5: an exact backend must report the wedge's own box, tight on every side."""
        shape = sdf_s3d.pie_slice(height=10, radius=10, angle=angle)
        assert shape.mn[:2] == pytest.approx(expected_mn, abs=1e-4)
        assert shape.mx[:2] == pytest.approx(expected_mx, abs=1e-4)
        assert (shape.mn[2], shape.mx[2]) == pytest.approx((-5.0, 5.0))

        # ... and tight is only correct if nothing is left outside it: sample the field around the
        # box and check every point it calls solid really is inside.
        field = shape.mesh()
        for x, y in ((11.0, 0.0), (0.0, 11.0), (-11.0, 0.0), (0.0, -11.0), (8.0, 8.0), (-8.0, -8.0)):
            if field.sample(x, y, 0) < 0:
                assert shape.mn[0] <= x <= shape.mx[0], f"solid at x={x}, outside the reported box"
                assert shape.mn[1] <= y <= shape.mx[1], f"solid at y={y}, outside the reported box"

    def test_a_narrow_wedge_reports_a_narrow_box(self) -> None:
        """The regression in one line: a 30 degree slice claimed four times the area it occupies."""
        wedge = sdf_s3d.pie_slice(height=10, radius=10, angle=30)
        _centre, size = wedge.bounds()
        assert size[:2] == pytest.approx([10.0, 5.0])  # not the disc's [20, 20]


class TestPrismoid:
    def test_non_tapered_matches_plain_box(self) -> None:
        shape = sdf_s3d.prismoid(size1=[10, 10], size2=[10, 10], height=10, anchor=CENTER).mesh()
        assert math.isclose(float(shape.sample(5, 0, 0)), float(0), abs_tol=1e-7)
        assert math.isclose(float(shape.sample(0, 0, 5)), float(0), abs_tol=1e-7)
        assert shape.sample(0, 0, 0) < 0
        center, size = sdf_s3d.prismoid(size1=[10, 10], size2=[10, 10], height=10, anchor=CENTER).bounds()
        assert size[2] == pytest.approx(10, abs=0.01)
        assert size[0] >= 8, "size1 = 10"

    def test_tapered(self) -> None:
        shape = sdf_s3d.prismoid(size1=[20, 20], size2=[10, 10], height=10, anchor=CENTER).mesh()
        assert math.isclose(float(shape.sample(10, 0, -5)), float(0), abs_tol=10 ** (-3)), "bottom rim (wider)"
        assert math.isclose(float(shape.sample(5, 0, 5)), float(0), abs_tol=10 ** (-3)), "top rim (narrower)"
        assert shape.sample(0, 0, 0) < 0
        center, size = sdf_s3d.prismoid(size1=[20, 20], size2=[10, 10], height=10, anchor=CENTER).bounds()
        assert size[2] == pytest.approx(10, abs=0.01)


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
        with pytest.raises(ValueError, match="height must be > 0, height=0"):
            sdf_s3d.polygon_prism(self.L_PATH, height=0)
        with pytest.raises(ValueError, match="every path needs >= 3 points, got"):
            sdf_s3d.polygon_prism([[0, 0], [1, 0]], height=5)
        with pytest.raises(ValueError, match="rim treatments must be smaller"):
            sdf_s3d.polygon_prism(self.L_PATH, height=5, rounding_top=6)

    def test_polygon_prism_chamfer_top(self) -> None:
        shape = sdf_s3d.polygon_prism(self.L_PATH, height=10, chamfer_top=1).mesh()
        assert shape is not None
        # chamfered top: surface at the corner should be modified
        center, size = sdf_s3d.polygon_prism(self.L_PATH, height=10, chamfer_top=1).bounds()
        assert size[2] == pytest.approx(10, abs=0.01)
        # interior should still be solid
        assert shape.sample(20, 7.5, 5) < 0, "center is inside"

    def test_polygon_prism_chamfer_bottom(self) -> None:
        shape = sdf_s3d.polygon_prism(self.L_PATH, height=10, chamfer_bottom=1).mesh()
        assert shape is not None
        center, size = sdf_s3d.polygon_prism(self.L_PATH, height=10, chamfer_bottom=1).bounds()
        assert size[2] == pytest.approx(10, abs=0.01)
        assert shape.sample(20, 7.5, 5) < 0, "center is inside"


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
        center, size = sdf_s3d.onion(radius=r, angle=angle, anchor=CENTER).bounds()
        assert size[0] >= 5
        assert size[2] >= 3


class TestHeightfield:
    def test_flat_heightfield(self) -> None:
        shape = sdf_s3d.heightfield(lambda _x, _y: 5, size=[20, 20], bottom=-5, maxz=10).mesh()
        assert math.isclose(float(shape.sample(0, 0, 5)), float(0), abs_tol=1e-7)
        assert shape.sample(0, 0, 0) < 0
        assert shape.sample(0, 0, 10) > 0
        center, size = sdf_s3d.heightfield(lambda _x, _y: 5, size=[20, 20], bottom=-5, maxz=10).bounds()
        assert size[0] >= 18
        assert size[1] >= 18

    def test_varying_heightfield(self) -> None:
        shape = sdf_s3d.heightfield(lambda x, _y: x * 0.1, size=[20, 20], bottom=-5, maxz=10).mesh()
        assert math.isclose(float(shape.sample(10, 0, 1)), float(0), abs_tol=1e-7)
        center, size = sdf_s3d.heightfield(lambda x, _y: x * 0.1, size=[20, 20], bottom=-5, maxz=10).bounds()
        assert size[0] >= 18

    def test_rejects_non_callable_data(self) -> None:
        with pytest.raises(ValueError, match="only supports callable"):
            sdf_s3d.heightfield([[1, 2], [3, 4]], size=[20, 20])  # type: ignore[arg-type]


class TestRegularPrism:
    """regular_prism (n-gon prism) -- SDF via polygon_prism().

    The default anchor is CENTER, so these prisms straddle z=0. They used to sit on [0, height]
    instead -- polygon_prism() builds on z=0 and the anchor offset was applied to it as though it
    were already centred, putting every prism half a height too high and disagreeing with the CSG
    twin of the same call. These tests sampled at z=height/2, which was interior under the old
    placement and is the top face under the right one, so they encoded the bug.
    """

    def test_hex_prism_builds(self) -> None:
        shape = sdf_s3d.regular_prism(num_sides=6, height=10, radius=8).mesh()
        assert math.isclose(float(shape.sample(8, 0, 0)), float(0), abs_tol=10 ** (-3)), "vertex on surface"
        assert shape.sample(0, 0, 0) < 0, "interior is inside"

    def test_a_default_anchored_prism_straddles_the_origin(self) -> None:
        """The placement itself, so it cannot drift back."""
        prism = sdf_s3d.regular_prism(num_sides=6, height=10, radius=8)
        assert prism.mn[2] == pytest.approx(-5.0)
        assert prism.mx[2] == pytest.approx(5.0)
        field = prism.mesh()
        assert float(field.sample(0, 0, 0)) < 0  # solid at the centre
        assert math.isclose(float(field.sample(0, 0, 5)), 0.0, abs_tol=1e-6)  # the top face
        assert float(field.sample(0, 0, 6)) > 0  # and clear above it

    def test_triangle_prism_with_side_length(self) -> None:
        shape = sdf_s3d.regular_prism(num_sides=3, height=6, side=9).mesh()
        assert math.isclose(float(shape.sample(5.196, 0, 0)), float(0), abs_tol=10 ** (-3)), "vertex on surface"
        assert shape.sample(0, 0, 0) < 0, "interior is inside"

    def test_pentagon_with_inner_radius(self) -> None:
        shape = sdf_s3d.regular_prism(num_sides=5, height=5, inner_radius=6).mesh()
        assert shape.sample(0, 0, 0) < 0, "interior is inside"

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
            distributed = s.xcopies(spacing=20, num_copies=2)  # type: ignore[attr-defined]

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


class TestBoundingBox:
    """bounding_box() — exact AABB wrapping on SDF."""

    def test_box_returns_sdf_cuboid(self) -> None:
        s = sdf_s3d.sphere(radius=10)
        box = s.bounding_box()
        assert box is not None
        assert box.backend == "sdf"

    def test_box_with_excess(self) -> None:
        s = sdf_s3d.sphere(radius=5)
        box = s.bounding_box(excess=2)
        _center, size = box.bounds()
        assert size[0] == pytest.approx(14, abs=0.1)


class TestInside:
    """inside() — point containment on SDF."""

    def test_center_is_inside(self) -> None:
        s = sdf_s3d.sphere(radius=10)
        assert s.inside([0, 0, 0])

    def test_far_point_is_outside(self) -> None:
        s = sdf_s3d.sphere(radius=5)
        assert not s.inside([100, 0, 0])


class TestChainHull:
    """chain_hull() — sequential hull on SDF."""

    def test_three_spheres_unioned(self) -> None:
        a = sdf_s3d.sphere(radius=5).translate([0, 0, 0])
        b = sdf_s3d.sphere(radius=5).translate([20, 0, 0])
        c = sdf_s3d.sphere(radius=5).translate([40, 0, 0])
        result = a.chain_hull(b, c)
        assert result is not None
        assert result.backend == "sdf"

    def test_single_shape_returns_self(self) -> None:
        s = sdf_s3d.cuboid([4, 4, 4])
        assert s.chain_hull() is s


class TestOffset3d:
    """offset3d() / round3d() — SDF surface offset."""

    def test_expand_sphere(self) -> None:
        s = sdf_s3d.sphere(radius=5)
        bigger = s.offset3d(2)
        _center, size = bigger.bounds()
        assert size[0] == pytest.approx(14, abs=0.1)

    def test_contract_sphere(self) -> None:
        s = sdf_s3d.sphere(radius=10)
        smaller = s.offset3d(-3)
        _center, size = smaller.bounds()
        assert size[0] == pytest.approx(14, abs=0.1)

    def test_round3d_runs(self) -> None:
        s = sdf_s3d.cuboid([10, 10, 10])
        rounded = s.round3d(radius=1)
        assert rounded is not None
        assert rounded.backend == "sdf"


#: (method, the exact box the cut half of a 10mm cube should have). The cube spans -5..5, so each
#: half keeps exactly one side of the origin -- and the SDF backend's whole selling point is that
#: it knows that box exactly, without meshing (SPEC PAR-5).
SDF_HALVES = [
    ("left_half", [-5.0, -5.0, -5.0], [0.0, 5.0, 5.0]),
    ("right_half", [0.0, -5.0, -5.0], [5.0, 5.0, 5.0]),
    ("front_half", [-5.0, -5.0, -5.0], [5.0, 0.0, 5.0]),
    ("back_half", [-5.0, 0.0, -5.0], [5.0, 5.0, 5.0]),
    ("bottom_half", [-5.0, -5.0, -5.0], [5.0, 5.0, 0.0]),
    ("top_half", [-5.0, -5.0, 0.0], [5.0, 5.0, 5.0]),
]


class TestHalfOf:
    """half_of() and direction variants on SDF.

    These all used to be `assert half is not None`, and every one of them was broken: the mask was
    shifted on all three axes instead of along the cut normal, so each "half" kept an *eighth* of
    the solid -- and `right_half()` and `back_half()` kept the same eighth as each other.
    """

    @pytest.mark.parametrize(("method", "low", "high"), SDF_HALVES, ids=[row[0] for row in SDF_HALVES])
    def test_each_half_keeps_its_own_side(self, method: str, low: list[float], high: list[float]) -> None:
        half = getattr(sdf_s3d.cuboid([10, 10, 10]), method)()
        assert [float(v) for v in half.mn] == pytest.approx(low, abs=1e-6), method
        assert [float(v) for v in half.mx] == pytest.approx(high, abs=1e-6), method

    @pytest.mark.parametrize(("method", "low", "high"), SDF_HALVES, ids=[row[0] for row in SDF_HALVES])
    def test_each_half_is_half_the_volume(self, method: str, low: list[float], high: list[float]) -> None:  # noqa: ARG002 - shared table
        """...and it is a half, not an eighth: the box is 5 x 10 x 10, whichever axis was cut."""
        _centre, size = getattr(sdf_s3d.cuboid([10, 10, 10]), method)().bounds()
        assert sorted(round(float(v), 6) for v in size) == [5.0, 10.0, 10.0], method

    def test_the_cut_plane_can_be_moved_along_its_axis(self) -> None:
        half = sdf_s3d.cuboid([10, 10, 10]).left_half(x=2)
        assert [float(v) for v in half.mx] == pytest.approx([2.0, 5.0, 5.0], abs=1e-6)
        assert [float(v) for v in half.mn] == pytest.approx([-5.0, -5.0, -5.0], abs=1e-6)

    def test_half_of_takes_an_arbitrary_normal(self) -> None:
        """An off-axis cut keeps the side its normal points to; the box cannot shrink for it."""
        cube = sdf_s3d.cuboid([10, 10, 10])
        diagonal = cube.half_of([1, 1, 0])
        assert [float(v) for v in diagonal.mx] == pytest.approx([5.0, 5.0, 5.0], abs=1e-6)
        assert diagonal.backend == "sdf"


class TestProjection:
    """projection() — refused on the SDF backend, naming the explicit conversion.

    A 2-D shadow is not derivable in closed form from a distance field, and meshing to answer it
    would hand back a CSG shape from an SDF one (SPEC B-5, PAR-3). It is listed in
    CSG_ONLY_FEATURES, so the refusal fires rather than converting behind the caller's back.
    """

    def test_projection_refuses_and_names_to_csg(self) -> None:
        from pybosl2.exceptions import UnsupportedByBackendError

        s = sdf_s3d.cuboid([10, 10, 10])
        with pytest.raises(UnsupportedByBackendError, match=r"\.to_csg\(\)"):
            s.projection()

    def test_projection_cut_refuses_too(self) -> None:
        from pybosl2.exceptions import UnsupportedByBackendError

        s = sdf_s3d.sphere(radius=10)
        with pytest.raises(UnsupportedByBackendError):
            s.projection(cut=True)


class TestDistributeOnPath:
    """distribute_on_path() — path-based distribution on SDF."""

    def test_basic_distribution(self) -> None:
        from pybosl2.path3d import Path3D

        s = sdf_s3d.sphere(radius=2)
        path = Path3D([[0, 0, 0], [10, 0, 0], [20, 0, 0]])
        result = s.distribute_on_path(path, num_copies=3)
        assert result is not None
        assert result.backend == "sdf"

    def test_spaced_distribution(self) -> None:
        """Copies every 10mm along a 30mm path: the union spans from the first to the last."""
        from pybosl2.path3d import Path3D

        spread = sdf_s3d.sphere(radius=2).distribute_on_path(Path3D([[0, 0, 0], [30, 0, 0]]), spacing=10)
        assert [float(v) for v in spread.mn] == pytest.approx([-2.0, -2.0, -2.0], abs=1e-6)
        assert [float(v) for v in spread.mx] == pytest.approx([32.0, 2.0, 2.0], abs=1e-6)

    def test_dist_parameter(self) -> None:
        """`dist=` names the distances outright, so the copies sit at 0 and 10 along the path."""
        from pybosl2.path3d import Path3D

        path = Path3D([[0, 0, 0], [10, 0, 0], [20, 0, 0]])
        spread = sdf_s3d.sphere(radius=2).distribute_on_path(path, dist=[0, 10])
        assert [float(v) for v in spread.mn] == pytest.approx([-2.0, -2.0, -2.0], abs=1e-6)
        assert [float(v) for v in spread.mx] == pytest.approx([12.0, 2.0, 2.0], abs=1e-6)

    def test_start_pos_with_num_copies(self) -> None:
        """Three copies from 5mm along the 20mm path: the first at 5, the last at the end."""
        from pybosl2.path3d import Path3D

        path = Path3D([[0, 0, 0], [10, 0, 0], [20, 0, 0]])
        spread = sdf_s3d.sphere(radius=2).distribute_on_path(path, start_pos=5, num_copies=3)
        assert [float(v) for v in spread.mn] == pytest.approx([3.0, -2.0, -2.0], abs=1e-6)
        assert [float(v) for v in spread.mx] == pytest.approx([22.0, 2.0, 2.0], abs=1e-6)

    def test_start_pos_with_spacing(self) -> None:
        """From 2mm along, every 5mm: the last copy that still fits sits at 17."""
        from pybosl2.path3d import Path3D

        path = Path3D([[0, 0, 0], [10, 0, 0], [20, 0, 0]])
        spread = sdf_s3d.sphere(radius=2).distribute_on_path(path, start_pos=2, spacing=5)
        assert [float(v) for v in spread.mn] == pytest.approx([0.0, -2.0, -2.0], abs=1e-6)
        assert [float(v) for v in spread.mx] == pytest.approx([19.0, 2.0, 2.0], abs=1e-6)


class TestPassthroughMethods:
    """Native CSG passthrough methods on SDF solids."""

    def test_minkowski_sphere_on_cube(self) -> None:
        a = sdf_s3d.cuboid([4, 4, 4])
        b = sdf_s3d.sphere(radius=2)
        result = a.minkowski(b)
        assert result is not None
        assert result.backend == "sdf"

    def test_repair_delegates_to_csg(self) -> None:
        """repair() has no field form, so it meshes and hands back a CSG solid of the same size."""
        repaired = sdf_s3d.cuboid([4, 4, 4]).repair()
        assert repaired.backend == "csg"
        assert [float(v) for v in repaired.bounds()[1]] == pytest.approx([4.0, 4.0, 4.0], abs=0.1)

    def test_render_is_noop(self) -> None:
        s = sdf_s3d.sphere(radius=5)
        assert s.render() is s

    def test_resize_scales_to_target(self) -> None:
        s = sdf_s3d.cuboid([10, 10, 10])
        result = s.resize([20, 20, 20])
        _center, size = result.bounds()
        assert size[0] == pytest.approx(20, abs=0.1)

    def test_resize_zero_axis_unchanged(self) -> None:
        s = sdf_s3d.cuboid([10, 10, 10])
        result = s.resize([0, 20, 0])
        _center, size = result.bounds()
        assert size[0] == pytest.approx(10, abs=0.1)
        assert size[1] == pytest.approx(20, abs=0.1)

    def test_separate_returns_list(self) -> None:
        s = sdf_s3d.cuboid([4, 4, 4])
        parts = s.separate()
        assert isinstance(parts, list)
        assert len(parts) >= 1

    def test_wrap_delegates_to_csg(self) -> None:
        """wrap() bends the meshed solid round a cylinder, so the wrapped axis changes length."""
        flat = sdf_s3d.cuboid([4, 20, 4])
        wrapped = flat.wrap(radius=10)
        assert wrapped.backend == "csg"
        assert float(wrapped.bounds()[1][1]) != pytest.approx(float(flat.bounds()[1][1]), abs=0.2)

    def test_pull_delegates_to_csg(self) -> None:
        """pull() is a mesh deformation, so it comes back as CSG, still the same order of size."""
        pulled = sdf_s3d.cuboid([4, 4, 4]).pull([1, 0, 0], distance=2)
        assert pulled.backend == "csg"
        assert float(pulled.bounds()[1][0]) >= 4.0 - 0.1

    @needs_csg_operable_mesh
    def test_minkowski_difference_delegates(self) -> None:
        """Carving with a radius-2 sphere insets the meshed cube by 2 on every side."""
        carved = sdf_s3d.cuboid([10, 10, 10]).minkowski_difference(sdf_s3d.sphere(radius=2))
        assert [float(v) for v in carved.bounds()[1]] == pytest.approx([6.0, 6.0, 6.0], abs=0.5)

    def test_oversample_delegates_to_csg(self) -> None:
        """oversample() subdivides the meshed solid: same shape, more triangles."""
        dense = sdf_s3d.cuboid([4, 4, 4]).oversample(8)
        assert dense.backend == "csg"
        assert [float(v) for v in dense.bounds()[1]] == pytest.approx([4.0, 4.0, 4.0], abs=0.1)

    @needs_csg_operable_mesh
    def test_partition_returns_two_parts(self) -> None:
        """The two interlocking halves come back separated by the spread."""
        first, second = sdf_s3d.cuboid([20, 20, 10]).partition(spread=10, cutsize=10)
        gap = abs(float(first.bounds()[0][1]) - float(second.bounds()[0][1]))
        assert gap > 10.0  # each half's own depth, plus the 10mm spread

    def test_regular_prism_rounding_and_chamfer(self) -> None:
        s_round = sdf_s3d.regular_prism(num_sides=5, height=20, inner_radius=12, rounding=2)
        assert s_round is not None
        center, size = s_round.bounds()
        assert size[2] == pytest.approx(20, abs=0.01)
        assert size[0] > 0
        assert size[1] > 0

        s_chamfer = sdf_s3d.regular_prism(num_sides=5, height=20, inner_radius=12, chamfer=2)
        assert s_chamfer is not None
        center, size = s_chamfer.bounds()
        assert size[2] == pytest.approx(20, abs=0.01)
        assert size[0] > 0
        assert size[1] > 0

    def test_tube_rounding_and_chamfer(self) -> None:
        t_round = sdf_s3d.tube(height=20, outer_radius=15, inner_radius=10, rounding=1)
        assert t_round is not None
        center, size = t_round.bounds()
        assert size[2] == pytest.approx(20, abs=0.01)
        assert size[0] >= 28

        t_chamfer = sdf_s3d.tube(height=20, outer_radius=15, inner_radius=10, chamfer=1)
        assert t_chamfer is not None
        center, size = t_chamfer.bounds()
        assert size[2] == pytest.approx(20, abs=0.01)


class TestSpiralSweep:
    """spiral_sweep(): a helical sweep as a distance field (TASKS T14)."""

    SECTION = [[-1.2, -1.2], [1.2, -1.2], [1.2, 1.2], [-1.2, 1.2]]

    def test_the_coil_matches_the_meshed_sweep(self) -> None:
        """The zero set is exact, so a sampled point agrees with the meshed sweep.

        Sampling rather than comparing bounds: a coil and a solid tube of the same size share an
        envelope, so bounds alone cannot tell them apart. Points within a facet width of the
        surface are excluded -- a faceted mesh legitimately cuts inside the true helical surface,
        and that difference is the mesh's, not the field's.
        """
        import math
        import random

        from pybosl2.path2d import Path2D
        from pybosl2.shapes3d import cuboid as csg_cuboid

        meshed = Path2D(self.SECTION).spiral_sweep(height=40, radius=12, turns=5).polyhedron()
        field = sdf_s3d.spiral_sweep(self.SECTION, height=40, radius=12, turns=5).mesh()

        random.seed(11)
        disagreements = []
        inside = 0
        for _ in range(200):
            angle = random.uniform(-math.pi, math.pi)
            r = random.uniform(9.5, 14.5)
            z = random.uniform(-22, 22)
            x, y = r * math.cos(angle), r * math.sin(angle)
            probe = csg_cuboid([0.05, 0.05, 0.05]).translate([x, y, z])
            in_mesh = (meshed & probe)._native_bounds() is not None
            value = float(field.sample(x, y, z))
            inside += int(in_mesh)
            if in_mesh != (value < 0) and abs(value) > 0.06:
                disagreements.append((round(x, 2), round(y, 2), round(z, 2), in_mesh, round(value, 3)))

        assert not disagreements, f"the field disagrees with the mesh away from the surface: {disagreements[:5]}"
        assert 0 < inside < 200, f"the probes never straddled the coil ({inside} of 200 inside)"

    def test_the_ends_are_the_profile_not_a_flat_cut(self) -> None:
        """The sweep is clipped in parameter space, so the last cross-section is the profile.

        Clipping to a z slab instead -- the obvious way to bound the union of turns -- shears the
        end faces off flat and loses the last part of the final turn. The coil is 40 tall plus the
        profile's own half-height at each end.
        """
        coil = sdf_s3d.spiral_sweep(self.SECTION, height=40, radius=12, turns=5)
        assert coil.mn[2] == pytest.approx(-20 - 1.2)
        assert coil.mx[2] == pytest.approx(20 + 1.2)

    def test_the_seam_at_the_branch_cut_is_covered(self) -> None:
        """atan2 tears at ±pi, so a neighbouring turn has to cover it.

        The sweep carries an extra turn at each end for exactly this. Without it the coil is split
        along the -X half-plane, which is where the field would otherwise jump a whole pitch.
        """
        field = sdf_s3d.spiral_sweep(self.SECTION, height=40, radius=12, turns=5).mesh()
        # Walk across the seam at a height where the coil is solid on both sides of it.
        for dy in (-0.4, -0.2, -0.05, 0.05, 0.2, 0.4):
            assert float(field.sample(-12, dy, -20 + 8 * 2.5)) < 0, f"the coil is torn at y={dy}"

    @pytest.mark.parametrize(("bad", "match"), [({"turns": 0}, "turns"), ({"height": 0}, "height")])
    def test_a_degenerate_sweep_is_rejected(self, bad: dict, match: str) -> None:  # type: ignore[type-arg]
        kwargs = {"height": 40, "radius": 12, "turns": 5, **bad}
        with pytest.raises(ValueError, match=match):
            sdf_s3d.spiral_sweep(self.SECTION, **kwargs)

    def test_a_tapered_helix_is_refused_by_the_facade(self) -> None:
        """A helix of changing radius has no closed-form field, so it says so."""
        from pybosl2._backend import use_backend
        from pybosl2.exceptions import UnsupportedByBackendError
        from pybosl2.path2d import Path2D

        with use_backend("sdf"), pytest.raises(UnsupportedByBackendError, match="radius1"):
            Path2D(self.SECTION).spiral_sweep(height=40, radius1=12, radius2=8, turns=5)

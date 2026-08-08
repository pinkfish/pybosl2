# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for :class:`pybosl2.shapes2d.Bosl2Shape2D` -- the 2-D shape object every shapes2d
constructor now returns, its 2-D operators (fill/hull/offset) and its 2-D -> 3-D extruders.

The geometry-value assertions need a native bounding box, which only the real PythonSCAD app
provides for 2-D shapes (the numeric mock's 2-D stand-ins are bbox-less); those are marked with
``needs_native_2d_bbox``. Everything else -- the types, the plumbing, the unwrapping -- runs under
the mock too.
"""

import math

import numpy as np
import pytest

import pybosl2.shapes2d as s2
from pybosl2._helpers import unwrap
from pybosl2.path2d import Path2D
from pybosl2.regions import Region
from pybosl2.shapes2d import Bosl2Shape2D
from pybosl2.shapes3d import Bosl2Solid, cuboid

# The real app reports obj.size for 2-D geometry; the numeric mock's 2-D stand-ins report None.
needs_native_2d_bbox = pytest.mark.skipif(
    s2.square(1).shape.size is None,
    reason="no native 2-D bounding box (running against the numeric mock)",
)

SQUARE_PTS = [[0, 0], [20, 0], [20, 10], [0, 10]]


# ---------------------------------------------------------------------------
# Every constructor returns the wrapper
# ---------------------------------------------------------------------------

# One call per public shapes2d constructor, covering both the box-anchored and the
# hull-anchored `_finish()` paths as well as the constructors that bypass it (circle's
# points=/corner= forms, text, ring's composed form, round2d/shell2d).
CONSTRUCTORS = {
    "square": lambda: s2.square(10),
    "square_center_false": lambda: s2.square([10, 4], center=False),
    "square_rounded": lambda: s2.square(20, rounding=3),
    "square_chamfered": lambda: s2.square(20, chamfer=2),
    "rect": lambda: s2.rect([20, 10]),
    "rect_rounded_perim": lambda: s2.rect([20, 10], rounding=2, atype="perim"),
    "circle": lambda: s2.circle(radius=5),
    "circle_points": lambda: s2.circle(points=[[0, 0], [10, 0], [5, 8]]),
    "circle_corner": lambda: s2.circle(corner=[[0, 10], [0, 0], [10, 0]], radius=3),
    "ellipse": lambda: s2.ellipse(radius=[10, 4]),
    "regular_ngon": lambda: s2.regular_ngon(sides=7, radius=10),
    "regular_ngon_chamfered": lambda: s2.regular_ngon(sides=6, radius=15, chamfer=2),
    "pentagon_rounded": lambda: s2.pentagon(radius=12, rounding=2),
    "hexagon_chamfered": lambda: s2.hexagon(radius=12, chamfer=1.5),
    "octagon_rounded": lambda: s2.octagon(radius=12, rounding=3),
    "pentagon": lambda: s2.pentagon(radius=10),
    "hexagon": lambda: s2.hexagon(radius=10),
    "octagon": lambda: s2.octagon(radius=10),
    "right_triangle": lambda: s2.right_triangle([10, 6]),
    "right_triangle_rounded": lambda: s2.right_triangle([15, 10], rounding=2),
    "right_triangle_chamfered": lambda: s2.right_triangle([15, 10], chamfer=1.5),
    "trapezoid": lambda: s2.trapezoid(height=10, width1=20, width2=10),
    "star": lambda: s2.star(tips=5, radius=20, inner_radius=10),
    "teardrop2d": lambda: s2.teardrop2d(radius=10),
    "egg": lambda: s2.egg(length=20, radius1=4, radius2=2, arc_radius=20),
    "glued_circles": lambda: s2.glued_circles(radius=8, spread=15),
    "supershape": lambda: s2.supershape(m1=4, n1=1, radius=10),
    "squircle": lambda: s2.squircle(20),
    "keyhole": lambda: s2.keyhole(length=25, radius1=4, radius2=9),
    "ring": lambda: s2.ring(radius=20, ring_width=4),
    "reuleaux_polygon": lambda: s2.reuleaux_polygon(sides=3, radius=10),
    "text": lambda: s2.text("Ab", size=8),
    "text_spun": lambda: s2.text("Ab", size=8, spin=30),
    "round2d": lambda: s2.round2d(radius=1, children=s2.square(10)),
    "shell2d": lambda: s2.shell2d(thickness=2, children=s2.square(20)),
}


@pytest.mark.parametrize("name", sorted(CONSTRUCTORS))
def test_every_constructor_returns_the_2d_wrapper(name: str) -> None:
    shape = CONSTRUCTORS[name]()
    assert isinstance(shape, Bosl2Shape2D), f"{name}() returned {type(shape).__name__}"


@pytest.mark.parametrize("name", sorted(CONSTRUCTORS))
def test_no_constructor_double_wraps(name: str) -> None:
    # .shape must be the raw native handle, never another wrapper -- ring()/round2d()/shell2d()
    # compose already-wrapped shapes, which is where a double wrap would creep in.
    inner = CONSTRUCTORS[name]().shape
    assert not isinstance(inner, (Bosl2Shape2D, Bosl2Solid))


def test_unwrap_returns_the_native_handle() -> None:
    shape = s2.square(10)
    assert unwrap(shape) is shape.shape
    assert unwrap(shape.shape) is shape.shape  # a raw handle passes straight through


def test_repr_names_the_class() -> None:
    assert repr(s2.square(10)).startswith("CsgShape2D(")


# ---------------------------------------------------------------------------
# Transforms and CSG stay 2-D
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "op",
    [
        lambda s: s.translate([5, 2]),
        lambda s: s.move([5, 2]),
        lambda s: s.rotate(30),  # bare scalar -> Z rotation
        lambda s: s.rotate([0, 0, 30]),
        lambda s: s.rot(30),
        lambda s: s.spin(30),
        lambda s: s.mirror([1, 0]),
        lambda s: s.scale(2),
        lambda s: s.scale([2, 3]),
        lambda s: s.multmatrix(np.eye(4).tolist()),
        lambda s: s.right(5),
        lambda s: s.left(5),
        lambda s: s.back(5),
        lambda s: s.forward(5),
        lambda s: s.fwd(5),
        lambda s: s.xflip(),
        lambda s: s.yflip(3),
        lambda s: s.color("red"),
        lambda s: s.highlight(),
        lambda s: s.ghost(),
    ],
)
def test_transforms_return_the_2d_wrapper(op: object) -> None:
    assert isinstance(op(s2.square(10)), Bosl2Shape2D)  # type: ignore[operator]


@pytest.mark.parametrize("op", [lambda a, b: a | b, lambda a, b: a & b, lambda a, b: a - b])
def test_csg_between_wrappers_returns_the_2d_wrapper(op: object) -> None:
    assert isinstance(op(s2.square(20), s2.circle(radius=5)), Bosl2Shape2D)  # type: ignore[operator]


@pytest.mark.parametrize("op", [lambda a, b: a | b, lambda a, b: a & b, lambda a, b: a - b])
def test_csg_unwraps_a_raw_native_operand(op: object) -> None:
    # the wrapper must hand the native operator a raw handle, not another wrapper
    assert isinstance(op(s2.square(20), s2.circle(radius=5).shape), Bosl2Shape2D)  # type: ignore[operator]


@pytest.mark.parametrize("op", [lambda a, b: a | b, lambda a, b: a & b, lambda a, b: a - b])
def test_reflected_csg_with_a_raw_native_left_operand(op: object) -> None:
    # __ror__/__rand__/__rsub__: reached explicitly, since the native operators raise rather
    # than returning NotImplemented when handed an object they don't know.
    native, wrapper = s2.square(20).shape, s2.circle(radius=5)
    assert isinstance(op(wrapper, native), Bosl2Shape2D)  # type: ignore[operator]
    assert isinstance(wrapper.__ror__(native), Bosl2Shape2D)
    assert isinstance(wrapper.__rand__(native), Bosl2Shape2D)
    assert isinstance(wrapper.__rsub__(native), Bosl2Shape2D)


def test_unknown_native_method_falls_through_still_wrapped() -> None:
    # resize() has no explicit override; __getattr__ must re-wrap its native result as 2-D
    assert isinstance(s2.square(10).resize([20, 20, 0]), Bosl2Shape2D)  # type: ignore[operator]


def test_missing_attribute_raises_attribute_error() -> None:
    with pytest.raises(AttributeError):
        _ = s2.square(10).definitely_not_a_native_method  # type: ignore[attr-defined]


def test_sdf_only_feature_is_rejected_on_the_csg_backend() -> None:
    from pybosl2.exceptions import UnsupportedByBackendError

    with pytest.raises(UnsupportedByBackendError):
        s2.square(10).round(2)  # type: ignore[operator, attr-defined]


# ---------------------------------------------------------------------------
# fill()
# ---------------------------------------------------------------------------


def test_fill_returns_the_2d_wrapper() -> None:
    plate = s2.square(40) - s2.circle(radius=8)
    assert isinstance(plate.fill(), Bosl2Shape2D)


def test_module_level_fill_accepts_every_child_form() -> None:
    assert isinstance(s2.fill(s2.square(10)), Bosl2Shape2D)  # wrapper
    assert isinstance(s2.fill(s2.square(10).shape), Bosl2Shape2D)  # raw native
    assert isinstance(s2.fill(Path2D(SQUARE_PTS)), Bosl2Shape2D)  # Path2D
    assert isinstance(s2.fill(Region([SQUARE_PTS])), Bosl2Shape2D)  # Region
    assert isinstance(s2.fill(SQUARE_PTS), Bosl2Shape2D)  # bare point list


def _covers(shape2d: Bosl2Shape2D, point: list[float]) -> bool:
    """True if the 2-D *shape* covers ``[x, y]`` -- asked of a thin extrusion of it, since the
    native ``inside()`` test is a 3-D one."""
    return shape2d.linear_extrude(height=2, center=True).inside([point[0], point[1], 0.0])


@needs_native_2d_bbox
def test_fill_closes_the_hole_without_changing_the_outline() -> None:
    plate = s2.square(40) - s2.circle(radius=8)
    filled = plate.fill()
    # the outline is untouched...
    np.testing.assert_allclose(filled.shape.size, plate.shape.size, atol=1e-6)
    # ...but the hole in the middle is gone
    assert not _covers(plate, [0, 0])
    assert _covers(filled, [0, 0])
    assert _covers(plate, [18, 0])
    assert _covers(filled, [18, 0])  # the ring of material stays


@needs_native_2d_bbox
def test_fill_of_a_self_intersecting_path_has_no_interior_loop() -> None:
    # a bowtie: polygon() leaves the crossing loops, fill() keeps only the outer boundary
    bowtie = Path2D([[0, 0], [20, 20], [20, 0], [0, 20]])
    np.testing.assert_allclose(bowtie.fill().shape.size, [20, 20], atol=1e-6)


# ---------------------------------------------------------------------------
# hull()
# ---------------------------------------------------------------------------


def test_hull_of_self_returns_the_2d_wrapper() -> None:
    assert isinstance(s2.star(tips=5, radius=20, inner_radius=8).hull(), Bosl2Shape2D)


def test_hull_accepts_every_child_form() -> None:
    base = s2.circle(radius=5)
    assert isinstance(base.hull(s2.circle(radius=5).right(30)), Bosl2Shape2D)  # wrapper
    assert isinstance(base.hull(s2.circle(radius=5).shape), Bosl2Shape2D)  # raw native
    assert isinstance(base.hull(Path2D(SQUARE_PTS)), Bosl2Shape2D)  # Path2D
    assert isinstance(base.hull(Region([SQUARE_PTS])), Bosl2Shape2D)  # Region
    assert isinstance(base.hull(SQUARE_PTS), Bosl2Shape2D)  # bare point list


def test_module_level_hull_takes_varargs_or_one_list() -> None:
    a, b = s2.circle(radius=5), s2.circle(radius=5).right(30)
    assert isinstance(s2.hull(a, b), Bosl2Shape2D)
    assert isinstance(s2.hull([a, b]), Bosl2Shape2D)  # a single list *of* shapes
    assert isinstance(s2.hull(SQUARE_PTS), Bosl2Shape2D)  # ...not mistaken for a point list
    assert isinstance(s2.hull(Path2D(SQUARE_PTS)), Bosl2Shape2D)  # ...nor a Path2D (a list subclass)


def test_module_level_hull_rejects_no_children() -> None:
    with pytest.raises(AssertionError):
        s2.hull()


@needs_native_2d_bbox
def test_hull_spans_both_children() -> None:
    # two radius-5 circles 30 apart -> a 40 x 10 slot
    slot = s2.circle(radius=5).hull(s2.circle(radius=5).right(30))
    np.testing.assert_allclose(slot.shape.size, [40, 10], atol=0.2)


@needs_native_2d_bbox
def test_hull_of_a_concave_shape_fills_the_notches() -> None:
    star = s2.star(tips=5, radius=20, inner_radius=8)
    hull = star.hull()
    # same outer extent -- the hull touches the same tips
    np.testing.assert_allclose(hull.shape.size, star.shape.size, atol=0.5)
    # ...but it is convex: it covers everything the star does, plus at least one notch point
    ring = [[15 * math.cos(math.radians(a)), 15 * math.sin(math.radians(a))] for a in range(0, 360, 10)]
    covered = [(_covers(star, p), _covers(hull, p)) for p in ring]
    assert all(h for s, h in covered if s), "the hull must cover everything the star does"
    assert any(h and not s for s, h in covered), "the hull must also fill a notch"


# ---------------------------------------------------------------------------
# offset()
# ---------------------------------------------------------------------------


def test_offset_returns_the_2d_wrapper() -> None:
    assert isinstance(s2.square(10).offset(radius=2), Bosl2Shape2D)
    assert isinstance(s2.square(10).offset(delta=2), Bosl2Shape2D)
    assert isinstance(s2.square(10).offset(delta=2, chamfer=True), Bosl2Shape2D)
    assert isinstance(s2.square(10).offset(radius=2, fn=8), Bosl2Shape2D)


def test_offset_needs_exactly_one_of_radius_or_delta() -> None:
    with pytest.raises(AssertionError):
        s2.square(10).offset()
    with pytest.raises(AssertionError):
        s2.square(10).offset(radius=2, delta=2)


@needs_native_2d_bbox
def test_offset_grows_the_outline() -> None:
    # BOSL2 spells it radius=; the native offset() only understands r=, so this also pins the
    # keyword translation the wrapper does.
    np.testing.assert_allclose(s2.square(10).offset(delta=2).shape.size, [14, 14], atol=1e-6)
    np.testing.assert_allclose(s2.square(10).offset(radius=2).shape.size, [14, 14], atol=0.1)


@needs_native_2d_bbox
def test_round2d_and_shell2d_offset_through_the_wrapper() -> None:
    # round2d()/shell2d() chain three offset(radius=)/offset(delta=) calls; they used to pass
    # radius= straight to the native offset(), which only understands r=.
    rounded = s2.round2d(radius=2, children=s2.square(20))
    np.testing.assert_allclose(rounded.shape.size, [20, 20], atol=0.2)
    assert _covers(rounded, [0, 0])
    assert not _covers(rounded, [9.9, 9.9])  # corners rounded off
    shell = s2.shell2d(thickness=2, children=s2.square(20))
    np.testing.assert_allclose(shell.shape.size, [24, 24], atol=0.2)
    assert not _covers(shell, [0, 0])
    assert _covers(shell, [11, 0])  # hollow, 2mm wall outside


def test_round2d_and_shell2d_accept_unwrapped_children() -> None:
    assert isinstance(s2.round2d(radius=1, children=s2.square(10).shape), Bosl2Shape2D)
    assert isinstance(s2.shell2d(thickness=1, children=Path2D(SQUARE_PTS)), Bosl2Shape2D)


# ---------------------------------------------------------------------------
# 2-D -> 3-D
# ---------------------------------------------------------------------------


def test_linear_extrude_returns_a_3d_solid() -> None:
    solid = s2.square(10).linear_extrude(height=5)
    assert isinstance(solid, Bosl2Solid)
    assert not isinstance(solid.shape, (Bosl2Shape2D, Bosl2Solid))


def test_linear_extrude_carries_the_tracked_size_to_three_dimensions() -> None:
    assert s2.square([10, 4]).linear_extrude(height=5).size == [10.0, 4.0, 5.0]
    # a shape with no tracked box size stays None rather than inventing one
    assert s2.star(tips=5, radius=20, inner_radius=8).linear_extrude(height=5).size is None


def test_linear_extrude_passes_its_options_through() -> None:
    for kw in (
        {"center": True},
        {"twist": 45, "slices": 8},
        {"scale": 2},
        {"scale": [1, 2]},
        {"convexity": 4},
    ):
        assert isinstance(s2.square(10).linear_extrude(height=5, **kw), Bosl2Solid)


@needs_native_2d_bbox
def test_linear_extrude_height_is_the_z_extent() -> None:
    _center, size = s2.square([10, 4]).linear_extrude(height=5).bounds()
    np.testing.assert_allclose(size, [10, 4, 5], atol=1e-6)


def test_rotate_extrude_returns_a_3d_solid() -> None:
    profile = s2.square([4, 10]).right(20)
    assert isinstance(profile.rotate_extrude(), Bosl2Solid)
    assert isinstance(profile.rotate_extrude(angle=180), Bosl2Solid)
    assert isinstance(profile.rotate_extrude(angle=180, fn=16, convexity=4), Bosl2Solid)


def test_path_extrude_returns_a_3d_solid() -> None:
    spine = [[0, 0, 0], [0, 0, 10], [5, 0, 20]]
    assert isinstance(s2.circle(radius=2).path_extrude(spine), Bosl2Solid)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# metadata / bounds / distributors
# ---------------------------------------------------------------------------


def test_box_shapes_track_their_nominal_size() -> None:
    assert s2.square([10, 4]).size == [10.0, 4.0]
    assert s2.rect([20, 10]).size == [20.0, 10.0]
    assert s2.ring(radius=20, ring_width=4).size == [48.0, 48.0]
    # hull-anchored shapes have no genuine box size
    assert s2.star(tips=5, radius=20, inner_radius=8).size is None


def test_bounds_of_a_centred_square() -> None:
    center, size = s2.square(10).bounds()
    np.testing.assert_allclose(center, [0, 0], atol=1e-6)
    np.testing.assert_allclose(size, [10, 10], atol=1e-6)


@needs_native_2d_bbox
def test_bounds_follow_a_translate() -> None:
    center, size = s2.square(10).right(5).bounds()
    np.testing.assert_allclose(center, [5, 0], atol=1e-6)
    np.testing.assert_allclose(size, [10, 10], atol=1e-6)


def test_bounds_raises_without_a_box_or_a_native_bbox() -> None:
    # A bbox-less stand-in rather than a real shape: against the real app every native 2-D shape
    # reports a bounding box, so wrapping one could never reach bounds()' last resort.
    class BboxLessShape:
        size = None
        position = None

    shape = Bosl2Shape2D(BboxLessShape())
    shape.size = None
    with pytest.raises(ValueError, match="no native bounding box and no tracked size"):
        shape.bounds()


def test_in_plane_distributors_return_one_combined_2d_shape() -> None:
    assert isinstance(s2.circle(radius=2).xcopies(spacing=10, num_copies=3), list)
    assert isinstance(s2.circle(radius=2).ycopies(spacing=10, num_copies=3), list)
    assert isinstance(s2.circle(radius=2).grid_copies(spacing=10, num_copies=2), list)


def test_out_of_plane_distributors_are_rejected() -> None:
    with pytest.raises(AssertionError):
        s2.circle(radius=2).zcopies(spacing=10, num_copies=3)


# ---------------------------------------------------------------------------
# Path2D / Region
# ---------------------------------------------------------------------------


def test_path_geometry_is_the_2d_wrapper() -> None:
    path = Path2D(SQUARE_PTS)
    assert isinstance(path.polygon(), Bosl2Shape2D)
    assert isinstance(path.geometry(), Bosl2Shape2D)
    assert not isinstance(path.polygon().shape, Bosl2Shape2D)


def test_path_2d_operators() -> None:
    path = Path2D(SQUARE_PTS)
    assert isinstance(path.fill(), Bosl2Shape2D)
    assert isinstance(path.polygon().hull(), Bosl2Shape2D)
    assert isinstance(path.polygon().hull(s2.circle(radius=5)), Bosl2Shape2D)


def test_path_extruders() -> None:
    path = Path2D(SQUARE_PTS)
    assert isinstance(path.linear_extrude(height=4), Bosl2Solid)
    assert isinstance(path.linear_extrude(height=4, center=True, twist=20), Bosl2Solid)
    assert isinstance(path.translate([30, 0]).rotate_extrude(angle=180), Bosl2Solid)


def test_region_geometry_is_the_2d_wrapper() -> None:
    region = Region.with_holes(SQUARE_PTS, [[5, 3], [15, 3], [15, 7], [5, 7]])  # type: ignore[arg-type]
    assert isinstance(region.geometry(), Bosl2Shape2D)
    assert isinstance(region.fill(), Bosl2Shape2D)
    assert isinstance(region.geometry().hull(), Bosl2Shape2D)
    assert isinstance(region.linear_extrude(height=4), Bosl2Solid)
    assert isinstance(region.translate([30, 0]).rotate_extrude(angle=180), Bosl2Solid)


@needs_native_2d_bbox
def test_region_fill_drops_the_hole() -> None:
    region = Region.with_holes(SQUARE_PTS, [[5, 3], [15, 3], [15, 7], [5, 7]])  # type: ignore[arg-type]
    np.testing.assert_allclose(region.fill().shape.size, [20, 10], atol=1e-6)
    assert not _covers(region.geometry(), [10, 5])  # the hole
    assert _covers(region.fill(), [10, 5])


# ---------------------------------------------------------------------------
# 3-D side: Bosl2Solid.hull() / .projection()
# ---------------------------------------------------------------------------


def test_solid_hull_returns_a_3d_solid() -> None:
    from pybosl2.shapes3d import sphere

    assert isinstance(sphere(radius=8).hull(), Bosl2Solid)
    capsule = sphere(radius=8).hull(sphere(radius=8).up(30))
    assert isinstance(capsule, Bosl2Solid)
    assert not isinstance(capsule.shape, Bosl2Solid)


def test_solid_hull_accepts_a_raw_native_and_a_vnf() -> None:
    from pybosl2.shapes3d import sphere
    from pybosl2.vnf import VNF

    assert isinstance(sphere(radius=8).hull(cuboid([4, 4, 4]).shape), Bosl2Solid)
    vnf = VNF.tri_array([[[0, 0, 0], [10, 0, 0]], [[0, 10, 0], [10, 10, 5]]])
    assert isinstance(sphere(radius=8).hull(vnf), Bosl2Solid)


def test_solid_hull_spans_both_children() -> None:
    capsule = cuboid([10, 10, 10]).hull(cuboid([10, 10, 10]).up(30))
    _center, size = capsule.bounds()
    np.testing.assert_allclose(size, [10, 10, 40], atol=0.5)


def test_projection_returns_the_2d_wrapper() -> None:
    shadow = cuboid([30, 20, 10]).projection()
    assert isinstance(shadow, Bosl2Shape2D)
    assert not isinstance(shadow.shape, (Bosl2Shape2D, Bosl2Solid))
    assert isinstance(cuboid([30, 20, 10]).projection(cut=True), Bosl2Shape2D)


def test_projection_chains_back_into_the_2d_operators() -> None:
    plate = cuboid([30, 20, 10]).projection().offset(radius=2).linear_extrude(height=2)
    assert isinstance(plate, Bosl2Solid)


@needs_native_2d_bbox
def test_projection_is_the_xy_footprint() -> None:
    np.testing.assert_allclose(cuboid([30, 20, 10]).projection().shape.size, [30, 20], atol=1e-6)


# -- minkowski ------------------------------------------------------------------


def test_minkowski_returns_2d_wrapper() -> None:
    a = s2.square([10, 10], center=True)
    b = s2.circle(radius=3)
    result = a.minkowski(b)
    assert isinstance(result, Bosl2Shape2D)


def test_minkowski_accepts_native_shape() -> None:
    a = s2.square([10, 10], center=True)
    b = s2.circle(radius=2)
    result = a.minkowski(b.shape)
    assert isinstance(result, Bosl2Shape2D)


def test_minkowski_chainable() -> None:
    a = s2.square([10, 10], center=True)
    result = a.minkowski(s2.circle(radius=2)).translate([0, 5]).rotate(45)
    assert isinstance(result, Bosl2Shape2D)


def test_minkowski_union_chains() -> None:
    a = s2.square([10, 10], center=True)
    b = s2.circle(radius=4)
    c = s2.circle(radius=2)
    result = a.minkowski(b) - a.minkowski(c)
    assert isinstance(result, Bosl2Shape2D)


def test_minkowski_linear_extrude() -> None:
    a = s2.square([10, 10], center=True)
    result = a.minkowski(s2.circle(radius=3)).linear_extrude(height=5)
    assert isinstance(result, Bosl2Solid)


@needs_native_2d_bbox
def test_minkowski_grows_bounding_box() -> None:
    a = s2.square([10, 10], center=True)
    # fn=64 so the disc really is round: at the default fragment count a radius-3 circle is a
    # 10-gon measuring 6 x 5.71, and the sum would grow by the apothem, not the radius, in Y.
    result = a.minkowski(s2.circle(radius=3, fn=64))
    np.testing.assert_allclose(result.shape.size, [16, 16], atol=0.1)


# ---------------------------------------------------------------------------
# chamfer / rounding parameter tests
# ---------------------------------------------------------------------------


def test_square_rounding_returns_shape2d() -> None:
    result = s2.square(20, rounding=3)
    assert isinstance(result, Bosl2Shape2D)


def test_square_chamfer_returns_shape2d() -> None:
    result = s2.square(20, chamfer=2)
    assert isinstance(result, Bosl2Shape2D)


def test_square_rounding_and_chamfer_mutually_exclusive() -> None:
    with pytest.raises(AssertionError, match="Cannot set both"):
        s2.square(20, rounding=3, chamfer=2)


def test_regular_ngon_chamfer_returns_shape2d() -> None:
    result = s2.regular_ngon(sides=6, radius=15, chamfer=2)
    assert isinstance(result, Bosl2Shape2D)


def test_regular_ngon_rounding_and_chamfer_mutually_exclusive() -> None:
    with pytest.raises(AssertionError, match="Cannot set both"):
        s2.regular_ngon(sides=6, radius=15, rounding=2, chamfer=2)


def test_pentagon_chamfer_returns_shape2d() -> None:
    result = s2.pentagon(radius=12, chamfer=2)
    assert isinstance(result, Bosl2Shape2D)


def test_hexagon_chamfer_returns_shape2d() -> None:
    result = s2.hexagon(radius=12, chamfer=1.5)
    assert isinstance(result, Bosl2Shape2D)


def test_octagon_chamfer_returns_shape2d() -> None:
    result = s2.octagon(radius=12, chamfer=2)
    assert isinstance(result, Bosl2Shape2D)


def test_right_triangle_rounding_returns_shape2d() -> None:
    result = s2.right_triangle([15, 10], rounding=2)
    assert isinstance(result, Bosl2Shape2D)


def test_right_triangle_chamfer_returns_shape2d() -> None:
    result = s2.right_triangle([15, 10], chamfer=1.5)
    assert isinstance(result, Bosl2Shape2D)


def test_right_triangle_rounding_and_chamfer_mutually_exclusive() -> None:
    with pytest.raises(AssertionError, match="Cannot set both"):
        s2.right_triangle([15, 10], rounding=2, chamfer=1.5)


def test_rect_rounding_and_chamfer_mutually_exclusive() -> None:
    with pytest.raises(AssertionError, match="rounding and chamfer"):
        s2.rect([20, 10], rounding=3, chamfer=2)


def test_square_rounded_chainable_to_solid() -> None:
    result = s2.square(20, rounding=3).linear_extrude(height=5)
    assert isinstance(result, Bosl2Solid)


def test_square_chamfered_chainable_to_solid() -> None:
    result = s2.square(20, chamfer=2).linear_extrude(height=5)
    assert isinstance(result, Bosl2Solid)


def test_right_triangle_rounded_chainable_to_solid() -> None:
    result = s2.right_triangle([15, 10], rounding=2).linear_extrude(height=5)
    assert isinstance(result, Bosl2Solid)


# ── uncovered shapes2d methods ───────────────────────────────────────────


def test_cross_2d() -> None:
    result = s2.cross(size=30, arm_width=6)
    assert isinstance(result, Bosl2Shape2D)


def test_cross_with_center() -> None:
    result = s2.cross(size=[40, 30], arm_width=8, center=False)
    assert isinstance(result, Bosl2Shape2D)


def test_shape_rotate_keyword_a() -> None:
    sq = s2.square(20)
    result = sq.rotate(a=45)  # type: ignore[call-arg]
    assert isinstance(result, Bosl2Shape2D)


# ── chamfer / rounding validation tests ─────────────────────────────────────


def test_regular_ngon_negative_rounding_allowed() -> None:
    result = s2.regular_ngon(sides=6, radius=10, rounding=-2)
    assert isinstance(result, Bosl2Shape2D)


def test_regular_ngon_negative_chamfer_allowed() -> None:
    result = s2.regular_ngon(sides=6, radius=10, chamfer=-2)
    assert isinstance(result, Bosl2Shape2D)


def test_regular_ngon_both_rounding_and_chamfer_raises() -> None:
    with pytest.raises(AssertionError, match="Cannot set both"):
        s2.regular_ngon(sides=6, radius=10, rounding=2, chamfer=2)


def test_regular_ngon_oversized_chamfer_raises() -> None:
    with pytest.raises(AssertionError, match="too large"):
        s2.regular_ngon(sides=6, radius=10, chamfer=20)


def test_rect_oversized_rounding_raises() -> None:
    with pytest.raises(AssertionError, match="exceed the rect"):
        s2.rect(size=[10, 10], rounding=6)


def test_rect_oversized_chamfer_raises() -> None:
    with pytest.raises(AssertionError, match="exceed the rect"):
        s2.rect(size=[10, 10], chamfer=6)


# ── negative chamfer / rounding tests ────────────────────────────────────────


def test_square_negative_rounding_produces_shape() -> None:
    assert isinstance(s2.square(20, rounding=-3), Bosl2Shape2D)


def test_square_negative_chamfer_produces_shape() -> None:
    assert isinstance(s2.square(20, chamfer=-3), Bosl2Shape2D)


def test_rect_negative_rounding_produces_shape() -> None:
    assert isinstance(s2.rect([30, 20], rounding=-4), Bosl2Shape2D)


def test_cuboid_negative_chamfer_produces_shape() -> None:
    from pybosl2.shapes3d import cuboid as _cuboid

    assert isinstance(_cuboid([20, 20, 20], chamfer=-4), Bosl2Solid)


def test_cyl_negative_rounding_produces_shape() -> None:
    from pybosl2.shapes3d import cyl

    assert isinstance(cyl(height=20, radius=10, rounding=-2), Bosl2Solid)

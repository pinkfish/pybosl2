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
from pybosl2.color import Color
from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D
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
    "circle_points": lambda: s2.circle(points=Path2D([[0, 0], [10, 0], [5, 8]])),
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
    # the type IS the claim here (PLAN X-8): whatever a constructor builds, it comes back wrapped
    shape = CONSTRUCTORS[name]()
    assert isinstance(shape, Bosl2Shape2D), f"{name}() returned {type(shape).__name__}"


@needs_native_2d_bbox
@pytest.mark.parametrize("name", sorted(CONSTRUCTORS))
def test_every_constructor_builds_something_with_extent(name: str) -> None:
    """...and it is real geometry: a finite, non-empty area, not an empty union."""
    _box = CONSTRUCTORS[name]().bounds()
    centre, size = list(_box.center), list(_box.size)
    assert all(math.isfinite(float(v)) for v in centre), f"{name}(): non-finite centre {centre}"
    assert all(float(v) > 0 for v in size), f"{name}(): degenerate size {size}"


#: The constructors whose bounding box is exactly derivable from their arguments -- so the test
#: says *why* the number is what it is, and a change to the maths fails here rather than in a
#: render nobody looks at.
EXACT_SIZES = {
    "square": ([10.0, 10.0], "a 10mm square"),
    "square_center_false": ([10.0, 4.0], "size given as [x, y]"),
    "square_rounded": ([20.0, 20.0], "rounding cuts the corners in, so the box is unchanged"),
    "square_chamfered": ([20.0, 20.0], "chamfer likewise"),
    "rect": ([20.0, 10.0], "rect takes [x, y] directly"),
    "circle": ([10.0, 10.0], "radius 5 -> diameter 10 each way"),
    "ellipse": ([20.0, 7.96], "radius [10, 4], flat-to-flat across the facets"),
    "trapezoid": ([20.0, 10.0], "the wider of the two widths, by the height"),
    "hexagon": ([20.0, 17.32], "radius 10 point-to-point, 10*sqrt(3) flat-to-flat"),
    "octagon": ([20.0, 20.0], "radius 10 point-to-point both ways"),
    "right_triangle": ([10.0, 6.0], "the two legs"),
    "glued_circles": ([31.0, 15.97], "two radius-8 circles spread 15 apart"),
    "shell2d": ([24.0, 24.0], "a 20mm square walled 2mm outward on every side"),
}


@needs_native_2d_bbox
@pytest.mark.parametrize("name", sorted(EXACT_SIZES))
def test_the_derivable_constructors_have_their_exact_size(name: str) -> None:
    expected, why = EXACT_SIZES[name]
    _box = CONSTRUCTORS[name]().bounds()
    _centre, size = list(_box.center), list(_box.size)
    assert [float(v) for v in size] == pytest.approx(expected, abs=0.01), f"{name}: {why}"


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


#: (operation, expected centre, expected size) applied to a 10mm square centred on the origin.
#: A 10mm square turned 30 degrees measures 10*(cos30 + sin30) = 13.66 across its new box.
TRANSFORMS = [
    ("translate", lambda s: s.translate([5, 2]), [5.0, 2.0], [10.0, 10.0]),
    ("move", lambda s: s.translate([5, 2]), [5.0, 2.0], [10.0, 10.0]),
    ("rotate_scalar", lambda s: s.rotate(30), [0.0, 0.0], [13.66, 13.66]),  # bare scalar -> Z
    ("rotate_vector", lambda s: s.rotate([0, 0, 30]), [0.0, 0.0], [13.66, 13.66]),
    ("rot", lambda s: s.rotate(30), [0.0, 0.0], [13.66, 13.66]),
    ("spin", lambda s: s.spin(30), [0.0, 0.0], [13.66, 13.66]),
    ("mirror", lambda s: s.mirror([1, 0]), [0.0, 0.0], [10.0, 10.0]),
    ("scale_scalar", lambda s: s.scale(2), [0.0, 0.0], [20.0, 20.0]),
    ("scale_vector", lambda s: s.scale([2, 3]), [0.0, 0.0], [20.0, 30.0]),
    ("multmatrix_identity", lambda s: s.multmatrix(np.eye(4).tolist()), [0.0, 0.0], [10.0, 10.0]),
    ("right", lambda s: s.right(5), [5.0, 0.0], [10.0, 10.0]),
    ("left", lambda s: s.left(5), [-5.0, 0.0], [10.0, 10.0]),
    ("back", lambda s: s.back(5), [0.0, 5.0], [10.0, 10.0]),
    ("forward", lambda s: s.forward(5), [0.0, -5.0], [10.0, 10.0]),
    ("fwd", lambda s: s.forward(5), [0.0, -5.0], [10.0, 10.0]),
    ("xflip", lambda s: s.xflip(), [0.0, 0.0], [10.0, 10.0]),
    ("yflip_about_3", lambda s: s.yflip(3), [0.0, 6.0], [10.0, 10.0]),  # mirrored across y=3
    ("color", lambda s: s.color(Color("red")), [0.0, 0.0], [10.0, 10.0]),
    ("highlight", lambda s: s.highlight(), [0.0, 0.0], [10.0, 10.0]),
    ("ghost", lambda s: s.ghost(), [0.0, 0.0], [10.0, 10.0]),
]


@pytest.mark.parametrize(("name", "op", "centre", "size"), TRANSFORMS, ids=[row[0] for row in TRANSFORMS])
def test_transforms_return_the_2d_wrapper(name: str, op: object, centre: list[float], size: list[float]) -> None:  # noqa: ARG001 - shared table
    assert isinstance(op(s2.square(10)), Bosl2Shape2D), name  # type: ignore[operator]


@needs_native_2d_bbox
@pytest.mark.parametrize(("name", "op", "centre", "size"), TRANSFORMS, ids=[row[0] for row in TRANSFORMS])
def test_each_transform_moves_the_shape_where_it_says(
    name: str, op: object, centre: list[float], size: list[float]
) -> None:
    """A transform that returns the right *type* and the wrong geometry is still a bug."""
    _box = op(s2.square(10)).bounds()  # type: ignore[operator]
    got_centre, got_size = list(_box.center), list(_box.size)
    assert [float(v) for v in got_centre] == pytest.approx(centre, abs=0.01), name
    assert [float(v) for v in got_size] == pytest.approx(size, abs=0.01), name


#: (name, operator, the size the result should have) for a 20mm square against a radius-5 circle.
#: The circle is wholly inside the square, so union and difference keep the square's box and the
#: intersection collapses to the circle's.
CSG_OPS = [
    ("union", lambda a, b: a | b, [20.0, 20.0]),
    ("intersection", lambda a, b: a & b, [10.0, 10.0]),
    ("difference", lambda a, b: a - b, [20.0, 20.0]),
]


@pytest.mark.parametrize(("name", "op", "size"), CSG_OPS, ids=[row[0] for row in CSG_OPS])
def test_csg_between_wrappers_returns_the_2d_wrapper(name: str, op: object, size: list[float]) -> None:  # noqa: ARG001 - shared table
    assert isinstance(op(s2.square(20), s2.circle(radius=5)), Bosl2Shape2D), name  # type: ignore[operator]


@needs_native_2d_bbox
@pytest.mark.parametrize(("name", "op", "size"), CSG_OPS, ids=[row[0] for row in CSG_OPS])
def test_csg_between_wrappers_combines_the_geometry(name: str, op: object, size: list[float]) -> None:
    result = op(s2.square(20), s2.circle(radius=5))  # type: ignore[operator]
    assert [float(v) for v in result.bounds().size] == pytest.approx(size, abs=0.01), name


@needs_native_2d_bbox
def test_difference_actually_removes_material() -> None:
    """The box is unchanged by a hole, so bounds alone cannot see it -- ask what is covered."""
    plate = s2.square(20) - s2.circle(radius=5)
    assert not _covers(plate, [0, 0])  # the hole
    assert _covers(plate, [9, 9])  # the corner it was cut from


@pytest.mark.parametrize(("name", "op", "size"), CSG_OPS, ids=[row[0] for row in CSG_OPS])
def test_csg_unwraps_a_raw_native_operand(name: str, op: object, size: list[float]) -> None:  # noqa: ARG001 - shared table
    # the wrapper must hand the native operator a raw handle, not another wrapper
    result = op(s2.square(20), s2.circle(radius=5).shape)  # type: ignore[operator]
    assert isinstance(result, Bosl2Shape2D), name
    assert not isinstance(result.shape, (Bosl2Shape2D, Bosl2Solid)), name


@needs_native_2d_bbox
@pytest.mark.parametrize(("name", "op", "size"), CSG_OPS, ids=[row[0] for row in CSG_OPS])
def test_a_raw_native_operand_gives_the_same_geometry(name: str, op: object, size: list[float]) -> None:  # noqa: ARG001 - shared table
    """`square | circle.shape` must build what `square | circle` builds, not something else."""
    wrapped = op(s2.square(20), s2.circle(radius=5))  # type: ignore[operator]
    native = op(s2.square(20), s2.circle(radius=5).shape)  # type: ignore[operator]
    assert [float(v) for v in native.bounds().size] == pytest.approx([float(v) for v in wrapped.bounds().size])


@needs_native_2d_bbox
def test_reflected_csg_with_a_raw_native_left_operand() -> None:
    # __ror__/__rand__/__rsub__: reached explicitly, since the native operators raise rather
    # than returning NotImplemented when handed an object they don't know.
    native, wrapper = s2.square(20).shape, s2.circle(radius=5)
    assert [float(v) for v in wrapper.__ror__(native).bounds().size] == pytest.approx([20.0, 20.0])
    assert [float(v) for v in wrapper.__rand__(native).bounds().size] == pytest.approx([10.0, 10.0])
    assert [float(v) for v in wrapper.__rsub__(native).bounds().size] == pytest.approx([20.0, 20.0])


@pytest.mark.parametrize("op", [lambda a, b: a | b, lambda a, b: a & b, lambda a, b: a - b])
def test_reflected_csg_returns_the_2d_wrapper(op: object) -> None:
    native, wrapper = s2.square(20).shape, s2.circle(radius=5)
    assert isinstance(op(wrapper, native), Bosl2Shape2D)  # type: ignore[operator]


@needs_native_2d_bbox
def test_unknown_native_method_falls_through_still_wrapped() -> None:
    # resize() has no explicit override; __getattr__ must re-wrap its native result as 2-D
    resized = s2.square(10).resize([20, 20, 0])  # type: ignore[operator]
    assert isinstance(resized, Bosl2Shape2D)
    assert [float(v) for v in resized.bounds().size] == pytest.approx([20.0, 20.0])


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


#: (name, the child form, the size fill() should produce). A 10mm square and the 20x10 point list
#: are the two shapes under test; every accepted spelling of them must fill to the same thing.
FILL_CHILDREN = [
    ("wrapper", lambda: s2.square(10), [10.0, 10.0]),
    ("raw_native", lambda: s2.square(10).shape, [10.0, 10.0]),
    ("path2d", lambda: Path2D(SQUARE_PTS), [20.0, 10.0]),
    ("region", lambda: Region([SQUARE_PTS]), [20.0, 10.0]),
    ("point_list", lambda: SQUARE_PTS, [20.0, 10.0]),
]


@pytest.mark.parametrize(("name", "child", "size"), FILL_CHILDREN, ids=[row[0] for row in FILL_CHILDREN])
def test_module_level_fill_accepts_every_child_form(name: str, child: object, size: list[float]) -> None:  # noqa: ARG001 - shared table
    assert isinstance(s2.fill(child()), Bosl2Shape2D), name  # type: ignore[operator]


@needs_native_2d_bbox
@pytest.mark.parametrize(("name", "child", "size"), FILL_CHILDREN, ids=[row[0] for row in FILL_CHILDREN])
def test_every_fill_child_form_fills_the_same_outline(name: str, child: object, size: list[float]) -> None:
    """Accepting a form is not enough -- a Path2D and its point list must fill identically."""
    assert [float(v) for v in s2.fill(child()).bounds().size] == pytest.approx(size, abs=0.01), name  # type: ignore[operator]


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


@needs_native_2d_bbox
def test_hull_of_a_star_fills_its_points_in() -> None:
    """A star's hull keeps its extent but is solid between the tips."""
    star = s2.star(tips=5, radius=20, inner_radius=8)
    hulled = star.hull()
    assert [float(v) for v in hulled.bounds().size] == pytest.approx([float(v) for v in star.bounds().size], abs=0.01)
    notch_between_tips = [10.0, 4.0]  # inside the hull, in the star's notch
    assert not _covers(star, notch_between_tips)
    assert _covers(hulled, notch_between_tips)


#: (name, child form, the size hulling it with a radius-5 circle at the origin should give).
HULL_CHILDREN = [
    ("wrapper", lambda: s2.circle(radius=5).right(30), [40.0, 10.0]),
    ("raw_native", lambda: s2.circle(radius=5).shape, [10.0, 10.0]),
    ("path2d", lambda: Path2D(SQUARE_PTS), [25.0, 15.0]),
    ("region", lambda: Region([SQUARE_PTS]), [25.0, 15.0]),
    ("point_list", lambda: SQUARE_PTS, [25.0, 15.0]),
]


@pytest.mark.parametrize(("name", "child", "size"), HULL_CHILDREN, ids=[row[0] for row in HULL_CHILDREN])
def test_hull_accepts_every_child_form(name: str, child: object, size: list[float]) -> None:  # noqa: ARG001 - shared table
    assert isinstance(s2.circle(radius=5).hull(child()), Bosl2Shape2D), name  # type: ignore[operator]


@needs_native_2d_bbox
@pytest.mark.parametrize(("name", "child", "size"), HULL_CHILDREN, ids=[row[0] for row in HULL_CHILDREN])
def test_every_hull_child_form_spans_the_same_box(name: str, child: object, size: list[float]) -> None:
    """The hull must reach the child wherever it is -- a form that is silently ignored would not."""
    hulled = s2.circle(radius=5).hull(child())  # type: ignore[operator]
    assert [float(v) for v in hulled.bounds().size] == pytest.approx(size, abs=0.01), name


@needs_native_2d_bbox
def test_module_level_hull_takes_varargs_or_one_list() -> None:
    a, b = s2.circle(radius=5), s2.circle(radius=5).right(30)
    two_circles = [40.0, 10.0]  # from x=-5 to x=35
    assert [float(v) for v in s2.hull(a, b).bounds().size] == pytest.approx(two_circles)
    assert [float(v) for v in s2.hull([a, b]).bounds().size] == pytest.approx(two_circles)  # a list *of* shapes
    # ...and a point list is one shape's outline, not a list of shapes
    assert [float(v) for v in s2.hull(SQUARE_PTS).bounds().size] == pytest.approx([20.0, 10.0])
    assert [float(v) for v in s2.hull(Path2D(SQUARE_PTS)).bounds().size] == pytest.approx([20.0, 10.0])


def test_module_level_hull_rejects_no_children() -> None:
    with pytest.raises(ValueError, match="at least one shape"):
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


#: Every offset spelling grows a 10mm square by 2mm on each side -- they differ only in what the
#: corner looks like, which the bounding box cannot see.
OFFSETS = [
    ("radius", {"radius": 2}),
    ("delta", {"delta": 2}),
    ("delta_chamfered", {"delta": 2, "chamfer": True}),
    ("radius_coarse", {"radius": 2, "fn": 8}),
]


@pytest.mark.parametrize(("name", "kwargs"), OFFSETS, ids=[row[0] for row in OFFSETS])
def test_offset_returns_the_2d_wrapper(name: str, kwargs: dict[str, object]) -> None:
    assert isinstance(s2.square(10).offset(**kwargs), Bosl2Shape2D), name  # type: ignore[arg-type]


@needs_native_2d_bbox
@pytest.mark.parametrize(("name", "kwargs"), OFFSETS, ids=[row[0] for row in OFFSETS])
def test_every_offset_form_grows_the_shape_by_the_same_amount(name: str, kwargs: dict[str, object]) -> None:
    grown = s2.square(10).offset(**kwargs)  # type: ignore[arg-type]
    assert [float(v) for v in grown.bounds().size] == pytest.approx([14.0, 14.0], abs=0.01), name


@needs_native_2d_bbox
def test_a_negative_offset_shrinks_the_shape() -> None:
    assert [float(v) for v in s2.square(10).offset(delta=-2).bounds().size] == pytest.approx([6.0, 6.0], abs=0.01)


def test_offset_needs_exactly_one_of_radius_or_delta() -> None:
    with pytest.raises(ValueError, match="give exactly one of"):
        s2.square(10).offset()
    with pytest.raises(ValueError, match="give exactly one of"):
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


@needs_native_2d_bbox
def test_round2d_and_shell2d_accept_unwrapped_children() -> None:
    """Both take a raw native or a Path2D, and build the same geometry they would from a wrapper."""
    rounded = s2.round2d(radius=1, children=s2.square(10).shape)
    assert [float(v) for v in rounded.bounds().size] == pytest.approx([10.0, 10.0], abs=0.01)  # rounds inward
    shelled = s2.shell2d(thickness=1, children=Path2D(SQUARE_PTS))
    # a 20x10 outline walled 1mm outward on every side
    assert [float(v) for v in shelled.bounds().size] == pytest.approx([22.0, 12.0], abs=0.01)


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


#: (name, options, what the option must do to the extrusion of a 10mm square, 5 tall).
EXTRUDE_OPTIONS = [
    ("center", {"center": True}, lambda s: float(s.bounds().center[2]) == pytest.approx(0.0)),
    ("uncentered", {}, lambda s: float(s.bounds().center[2]) == pytest.approx(2.5)),
    ("twist", {"twist": 45, "slices": 8}, lambda s: float(s.bounds().size[0]) > 10.0),
    ("scale_vector", {"scale": [1, 2]}, lambda s: float(s.bounds().size[1]) == pytest.approx(20.0, abs=0.01)),
    ("scale_scalar", {"scale": 2}, lambda s: "scale = 2" in repr(s.shape)),
    ("convexity", {"convexity": 4}, lambda s: "convexity = 4" in repr(s.shape)),
]


@pytest.mark.parametrize(("name", "kwargs", "check"), EXTRUDE_OPTIONS, ids=[row[0] for row in EXTRUDE_OPTIONS])
def test_linear_extrude_passes_its_options_through(name: str, kwargs: dict[str, object], check: object) -> None:
    """Each option must reach the extrusion -- a silently dropped one builds the wrong solid.

    `scale=2` did exactly that: the native ignores a scalar scale (it honours only the vector
    form), so a uniform taper came out as a plain prism until the wrapper started normalising it.
    """
    solid = s2.square(10).linear_extrude(height=5, **kwargs)  # type: ignore[arg-type]
    assert isinstance(solid, Bosl2Solid), name
    assert check(solid), name  # type: ignore[operator]


@needs_native_2d_bbox
def test_a_scalar_scale_tapers_both_axes_like_the_vector_form() -> None:
    scalar = s2.square(10).linear_extrude(height=5, scale=2)
    vector = s2.square(10).linear_extrude(height=5, scale=[2, 2])
    assert [float(v) for v in scalar.bounds().size] == pytest.approx([float(v) for v in vector.bounds().size])
    assert repr(scalar.shape) == repr(vector.shape)


@needs_native_2d_bbox
def test_linear_extrude_height_is_the_z_extent() -> None:
    _box = s2.square([10, 4]).linear_extrude(height=5).bounds()
    _center, size = list(_box.center), list(_box.size)
    np.testing.assert_allclose(size, [10, 4, 5], atol=1e-6)


@needs_native_2d_bbox
def test_rotate_extrude_sweeps_the_profile_around_the_z_axis() -> None:
    """A 4x10 profile 20mm out from the axis sweeps a ring 44mm across and 10 tall."""
    profile = s2.square([4, 10]).right(20)
    full = profile.rotate_extrude()
    assert [float(v) for v in full.bounds().size] == pytest.approx([44.0, 43.76, 10.0], abs=0.3)


@needs_native_2d_bbox
def test_rotate_extrude_angle_sweeps_only_part_of_the_way() -> None:
    """Half a turn leaves half the ring, so it spans the full diameter in X but only half in Y."""
    profile = s2.square([4, 10]).right(20)
    half = profile.rotate_extrude(angle=180)
    assert float(half.bounds().size[0]) == pytest.approx(44.0, abs=0.3)
    assert float(half.bounds().size[1]) == pytest.approx(22.0, abs=0.3)
    assert isinstance(profile.rotate_extrude(angle=180, fn=16, convexity=4), Bosl2Solid)


@needs_native_2d_bbox
def test_path_extrude_follows_its_spine() -> None:
    """A radius-2 circle swept up 20mm and 5mm over reaches roughly that far in each axis."""
    spine = Path3D([[0, 0, 0], [0, 0, 10], [5, 0, 20]])
    tube = s2.circle(radius=2).path_extrude(spine)
    size = [float(v) for v in tube.bounds().size]
    assert size[2] == pytest.approx(20.8, abs=0.5)  # the spine's height, plus the profile's tilt
    assert 4.0 < size[0] < 12.0  # the 5mm dogleg, widened by the 4mm-diameter profile


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
    _box = s2.square(10).bounds()
    center, size = list(_box.center), list(_box.size)
    np.testing.assert_allclose(center, [0, 0], atol=1e-6)
    np.testing.assert_allclose(size, [10, 10], atol=1e-6)


@needs_native_2d_bbox
def test_bounds_follow_a_translate() -> None:
    _box = s2.square(10).right(5).bounds()
    center, size = list(_box.center), list(_box.size)
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


@needs_native_2d_bbox
def test_in_plane_distributors_lay_the_copies_out() -> None:
    """Each copier returns the copies themselves, spaced as asked and each still the same shape."""
    circle = s2.circle(radius=2)

    def gaps(copies: list[Bosl2Shape2D], axis: int) -> list[float]:
        centres = sorted(float(copy.bounds().center[axis]) for copy in copies)
        return [round(b - a, 6) for a, b in zip(centres, centres[1:], strict=False)]

    across = circle.xcopies(spacing=10, num_copies=3)
    assert len(across) == 3
    assert gaps(across, 0) == pytest.approx([10.0, 10.0])
    assert all([float(v) for v in copy.bounds().size] == pytest.approx([4.0, 4.0], abs=0.2) for copy in across)

    up = circle.ycopies(spacing=10, num_copies=3)
    assert gaps(up, 1) == pytest.approx([10.0, 10.0])
    assert gaps(up, 0) == pytest.approx([0.0, 0.0])  # ...and they stay on the Y axis

    grid = circle.grid_copies(spacing=10, num_copies=2)
    assert len(grid) == 4  # 2 x 2
    spans = [
        max(float(c.bounds().center[axis]) for c in grid) - min(float(c.bounds().center[axis]) for c in grid)
        for axis in (0, 1)
    ]
    assert spans == pytest.approx([10.0, 10.0])


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


@needs_native_2d_bbox
def test_path_2d_operators() -> None:
    """A Path2D goes into the 2-D operators directly and keeps its own 20x10 outline."""
    path = Path2D(SQUARE_PTS)
    assert [float(v) for v in path.fill().bounds().size] == pytest.approx([20.0, 10.0], abs=0.01)
    assert [float(v) for v in path.polygon().hull().bounds().size] == pytest.approx([20.0, 10.0], abs=0.01)
    # hulling it with a circle at the origin reaches out to that circle
    with_circle = path.polygon().hull(s2.circle(radius=5))
    assert [float(v) for v in with_circle.bounds().size] == pytest.approx([25.0, 15.0], abs=0.01)


@needs_native_2d_bbox
def test_path_extruders() -> None:
    path = Path2D(SQUARE_PTS)
    straight = path.linear_extrude(height=4)
    assert [float(v) for v in straight.bounds().size] == pytest.approx([20.0, 10.0, 4.0], abs=0.01)
    twisted = path.linear_extrude(height=4, center=True, twist=20)
    assert float(twisted.bounds().size[0]) > 20.0  # the twist swings the corners out
    assert float(twisted.bounds().center[2]) == pytest.approx(0.0)  # centered
    revolved = path.translate([30, 0]).rotate_extrude(angle=180)
    assert float(revolved.bounds().size[0]) == pytest.approx(100.0, abs=0.1)  # out to x=50 and back
    assert float(revolved.bounds().size[2]) == pytest.approx(10.0, abs=0.01)  # the profile's height


def test_region_geometry_is_the_2d_wrapper() -> None:
    # the type IS the claim: a Region enters the same 2-D/3-D pipeline as a shape (PLAN X-8)
    region = Region.with_holes(SQUARE_PTS, [[5, 3], [15, 3], [15, 7], [5, 7]])  # type: ignore[arg-type]
    assert isinstance(region.geometry(), Bosl2Shape2D)
    assert isinstance(region.fill(), Bosl2Shape2D)
    assert isinstance(region.geometry().hull(), Bosl2Shape2D)
    assert isinstance(region.linear_extrude(height=4), Bosl2Solid)
    assert isinstance(region.translate([30, 0]).rotate_extrude(angle=180), Bosl2Solid)


@needs_native_2d_bbox
def test_a_region_keeps_its_outline_through_the_pipeline() -> None:
    """Its outer boundary is 20x10 whatever is done to it -- the hole never changes the box."""
    region = Region.with_holes(SQUARE_PTS, [[5, 3], [15, 3], [15, 7], [5, 7]])  # type: ignore[arg-type]
    assert [float(v) for v in region.geometry().bounds().size] == pytest.approx([20.0, 10.0], abs=0.01)
    assert [float(v) for v in region.geometry().hull().bounds().size] == pytest.approx([20.0, 10.0], abs=0.01)
    assert [float(v) for v in region.linear_extrude(height=4).bounds().size] == pytest.approx(
        [20.0, 10.0, 4.0], abs=0.01
    )
    revolved = region.translate([30, 0]).rotate_extrude(angle=180)
    assert float(revolved.bounds().size[0]) == pytest.approx(100.0, abs=0.1)


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
    """A hull reaches its child whatever form it arrives in -- so the box grows to include it."""
    from pybosl2.shapes3d import sphere
    from pybosl2.vnf import VNF

    alone = [float(v) for v in sphere(radius=8).bounds().size]
    with_native = sphere(radius=8).hull(cuboid([4, 4, 4]).shape)
    assert [float(v) for v in with_native.bounds().size] == pytest.approx(alone, abs=0.5)  # cube fits inside

    vnf = VNF.tri_array([[[0, 0, 0], [10, 0, 0]], [[0, 10, 0], [10, 10, 5]]])
    with_vnf = sphere(radius=8).hull(vnf)
    assert float(with_vnf.bounds().size[0]) > alone[0]  # the mesh reaches out to x=10


def test_solid_hull_spans_both_children() -> None:
    capsule = cuboid([10, 10, 10]).hull(cuboid([10, 10, 10]).up(30))
    _box = capsule.bounds()
    _center, size = list(_box.center), list(_box.size)
    np.testing.assert_allclose(size, [10, 10, 40], atol=0.5)


def test_projection_returns_the_2d_wrapper() -> None:
    shadow = cuboid([30, 20, 10]).projection()
    assert isinstance(shadow, Bosl2Shape2D)
    assert not isinstance(shadow.shape, (Bosl2Shape2D, Bosl2Solid))
    assert isinstance(cuboid([30, 20, 10]).projection(cut=True), Bosl2Shape2D)


@needs_native_2d_bbox
def test_projection_chains_back_into_the_2d_operators() -> None:
    """3-D -> 2-D -> 3-D: the footprint grows by the offset, then extrudes to its own height."""
    plate = cuboid([30, 20, 10]).projection().offset(radius=2).linear_extrude(height=2)
    assert [float(v) for v in plate.bounds().size] == pytest.approx([34.0, 24.0, 2.0], abs=0.01)


@needs_native_2d_bbox
def test_projection_is_the_xy_footprint() -> None:
    np.testing.assert_allclose(cuboid([30, 20, 10]).projection().shape.size, [30, 20], atol=1e-6)


# -- minkowski ------------------------------------------------------------------


def test_minkowski_returns_2d_wrapper() -> None:
    a = s2.square([10, 10], center=True)
    b = s2.circle(radius=3)
    result = a.minkowski(b)
    assert isinstance(result, Bosl2Shape2D)


@needs_native_2d_bbox
def test_minkowski_accepts_native_shape() -> None:
    """A raw native operand rounds the square exactly as the wrapped one does."""
    square = s2.square([10, 10], center=True)
    circle = s2.circle(radius=2, fn=64)
    wrapped = square.minkowski(circle)
    native = square.minkowski(circle.shape)
    assert [float(v) for v in native.bounds().size] == pytest.approx([float(v) for v in wrapped.bounds().size])
    assert [float(v) for v in native.bounds().size] == pytest.approx([14.0, 14.0], abs=0.1)


@needs_native_2d_bbox
def test_minkowski_chainable() -> None:
    """The result is an ordinary 2-D shape, so the transforms keep working on it."""
    rounded = s2.square([10, 10], center=True).minkowski(s2.circle(radius=2, fn=64))
    moved = rounded.translate([0, 5]).rotate(45)
    assert float(moved.bounds().center[1]) > float(rounded.bounds().center[1])  # the translate took effect
    assert float(moved.bounds().size[0]) > float(rounded.bounds().size[0])  # ...and so did the rotate


@needs_native_2d_bbox
def test_minkowski_union_chains() -> None:
    """A ring: the same square grown by two radii, the smaller cut out of the larger."""
    square = s2.square([10, 10], center=True)
    ring = square.minkowski(s2.circle(radius=4, fn=64)) - square.minkowski(s2.circle(radius=2, fn=64))
    assert [float(v) for v in ring.bounds().size] == pytest.approx([18.0, 18.0], abs=0.1)
    assert not _covers(ring, [0, 0])  # the middle is the hole the smaller shape left
    assert _covers(ring, [8, 0])


@needs_native_2d_bbox
def test_minkowski_linear_extrude() -> None:
    solid = s2.square([10, 10], center=True).minkowski(s2.circle(radius=3, fn=64)).linear_extrude(height=5)
    assert [float(v) for v in solid.bounds().size] == pytest.approx([16.0, 16.0, 5.0], abs=0.1)


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


#: (name, the plain shape, the same shape with its corners treated, how to see the treatment).
#: "corner" -- the shape fills its bounding corner, so the treatment must remove material there.
#: "span" -- a polygon whose corners are its extreme points, so the treatment must pull them in.
#: `right_triangle(chamfer=)` used to be a no-op and `rounding=` grew the triangle instead of
#: rounding it: both went through a grow-then-shrink offset pair, which restores a sharp corner.
CORNER_TREATMENTS = [
    ("square_rounding", lambda: s2.square(20), lambda: s2.square(20, rounding=3), "corner"),
    ("square_chamfer", lambda: s2.square(20), lambda: s2.square(20, chamfer=2), "corner"),
    (
        "ngon_chamfer",
        lambda: s2.regular_ngon(sides=6, radius=15),
        lambda: s2.regular_ngon(sides=6, radius=15, chamfer=2),
        "span",
    ),
    ("pentagon_chamfer", lambda: s2.pentagon(radius=12), lambda: s2.pentagon(radius=12, chamfer=2), "span"),
    ("hexagon_chamfer", lambda: s2.hexagon(radius=12), lambda: s2.hexagon(radius=12, chamfer=1.5), "span"),
    ("octagon_chamfer", lambda: s2.octagon(radius=12), lambda: s2.octagon(radius=12, chamfer=2), "span"),
    (
        "right_triangle_rounding",
        lambda: s2.right_triangle([15, 10]),
        lambda: s2.right_triangle([15, 10], rounding=2),
        "corner",
    ),
    (
        "right_triangle_chamfer",
        lambda: s2.right_triangle([15, 10]),
        lambda: s2.right_triangle([15, 10], chamfer=1.5),
        "corner",
    ),
]


def _near_corner(shape: Bosl2Shape2D) -> list[float]:
    """A point just inside the shape's bottom-left bounding corner."""
    _box = shape.bounds()
    centre, size = list(_box.center), list(_box.size)
    return [float(centre[0]) - float(size[0]) * 0.464, float(centre[1]) - float(size[1]) * 0.464]


@pytest.mark.parametrize(
    ("name", "plain", "treated", "how"), CORNER_TREATMENTS, ids=[row[0] for row in CORNER_TREATMENTS]
)
def test_corner_treatments_return_shape2d(name: str, plain: object, treated: object, how: str) -> None:  # noqa: ARG001 - shared table
    assert isinstance(treated(), Bosl2Shape2D), name  # type: ignore[operator]


@needs_native_2d_bbox
@pytest.mark.parametrize(
    ("name", "plain", "treated", "how"), CORNER_TREATMENTS, ids=[row[0] for row in CORNER_TREATMENTS]
)
def test_a_corner_treatment_actually_cuts_the_corner(name: str, plain: object, treated: object, how: str) -> None:
    """Rounding and chamfering must remove material at the corners -- and only at the corners."""
    original, cut = plain(), treated()  # type: ignore[operator]
    before = [float(v) for v in original.bounds().size]
    after = [float(v) for v in cut.bounds().size]

    if how == "corner":
        probe = _near_corner(original)
        assert _covers(original, probe), f"{name}: bad probe -- the plain shape does not reach it"
        assert not _covers(cut, probe), f"{name}: the corner is untouched, the treatment did nothing"
    else:
        # the corners are the extreme points, so treating them pulls the whole span in
        assert all(a < b for a, b in zip(after, before, strict=True)), f"{name}: {after} vs {before}"

    # ...and either way it took a corner, not the whole shape
    assert all(a > 0.6 * b for a, b in zip(after, before, strict=True)), f"{name}: {after} vs {before}"


def test_square_rounding_and_chamfer_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="Cannot set both"):
        s2.square(20, rounding=3, chamfer=2)


def test_regular_ngon_rounding_and_chamfer_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="Cannot set both"):
        s2.regular_ngon(sides=6, radius=15, rounding=2, chamfer=2)


def test_right_triangle_rounding_and_chamfer_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="Cannot set both"):
        s2.right_triangle([15, 10], rounding=2, chamfer=1.5)


def test_rect_rounding_and_chamfer_mutually_exclusive() -> None:
    with pytest.raises(AssertionError, match="rounding and chamfer"):
        s2.rect([20, 10], rounding=3, chamfer=2)


@needs_native_2d_bbox
@pytest.mark.parametrize(
    ("name", "shape", "footprint"),
    [
        ("square_rounded", lambda: s2.square(20, rounding=3), [20.0, 20.0]),
        ("square_chamfered", lambda: s2.square(20, chamfer=2), [20.0, 20.0]),
        ("right_triangle_rounded", lambda: s2.right_triangle([15, 10], rounding=2), [10.31, 8.03]),
    ],
    ids=["square_rounded", "square_chamfered", "right_triangle_rounded"],
)
def test_a_treated_shape_extrudes_to_its_own_footprint(name: str, shape: object, footprint: list[float]) -> None:
    """The corner treatment survives into 3-D: the prism has the treated outline, 5 tall."""
    solid = shape().linear_extrude(height=5)  # type: ignore[operator]
    assert [float(v) for v in solid.bounds().size] == pytest.approx([*footprint, 5.0], abs=0.05), name


# ── uncovered shapes2d methods ───────────────────────────────────────────


@needs_native_2d_bbox
def test_cross_2d() -> None:
    """A cross spans its full size in both axes, with the arms cut away between them."""
    cross = s2.cross(size=30, arm_width=6)
    assert [float(v) for v in cross.bounds().size] == pytest.approx([30.0, 30.0], abs=0.01)
    assert _covers(cross, [0, 0])  # the middle
    assert _covers(cross, [14, 0])  # along an arm
    assert not _covers(cross, [14, 14])  # ...but not the corner between two arms


@needs_native_2d_bbox
def test_cross_with_center() -> None:
    """`size=[x, y]` gives the two arm lengths; center=False anchors it at the corner."""
    cross = s2.cross(size=[40, 30], arm_width=8, center=False)
    _box = cross.bounds()
    centre, size = list(_box.center), list(_box.size)
    assert [float(v) for v in size] == pytest.approx([40.0, 30.0], abs=0.01)
    assert float(centre[0]) > 0  # anchored off the origin rather than centred on it


@needs_native_2d_bbox
def test_shape_rotate_keyword_a() -> None:
    """`a=` is OpenSCAD's own spelling of the rotation angle, and must rotate the same way."""
    by_keyword = s2.square(20).rotate(a=45)  # type: ignore[call-arg]
    by_position = s2.square(20).rotate(45)
    assert [float(v) for v in by_keyword.bounds().size] == pytest.approx([float(v) for v in by_position.bounds().size])
    assert float(by_keyword.bounds().size[0]) == pytest.approx(20 * math.sqrt(2), abs=0.01)


# ── chamfer / rounding validation tests ─────────────────────────────────────


@needs_native_2d_bbox
@pytest.mark.parametrize("treatment", ["rounding", "chamfer"])
def test_a_negative_corner_treatment_cuts_the_other_way(treatment: str) -> None:
    """A negative radius fillets *outward*, filling the corner instead of cutting it -- so the
    shape ends up larger than the plain n-gon rather than smaller."""
    plain = s2.regular_ngon(sides=6, radius=10)
    flared = s2.regular_ngon(sides=6, radius=10, **{treatment: -2})
    before = [float(v) for v in plain.bounds().size]
    after = [float(v) for v in flared.bounds().size]
    assert all(a > b for a, b in zip(after, before, strict=True)), f"{after} vs {before}"


def test_regular_ngon_both_rounding_and_chamfer_raises() -> None:
    with pytest.raises(ValueError, match="Cannot set both"):
        s2.regular_ngon(sides=6, radius=10, rounding=2, chamfer=2)


def test_regular_ngon_oversized_chamfer_raises() -> None:
    with pytest.raises(ValueError, match="too large"):
        s2.regular_ngon(sides=6, radius=10, chamfer=20)


def test_rect_oversized_rounding_raises() -> None:
    with pytest.raises(ValueError, match="exceed the rect"):
        s2.rect(size=[10, 10], rounding=6)


def test_rect_oversized_chamfer_raises() -> None:
    with pytest.raises(ValueError, match="exceed the rect"):
        s2.rect(size=[10, 10], chamfer=6)


# ── negative chamfer / rounding tests ────────────────────────────────────────


#: (name, plain, negatively treated, the axes the flare grows). A negative rounding/chamfer
#: fillets outward -- material is *added* at the corner, so the shape gets bigger by 2x the size.
NEGATIVE_TREATMENTS = [
    ("square_rounding", lambda: s2.square(20), lambda: s2.square(20, rounding=-3), [26.0, 20.0]),
    ("square_chamfer", lambda: s2.square(20), lambda: s2.square(20, chamfer=-3), [26.0, 20.0]),
    ("rect_rounding", lambda: s2.rect([30, 20]), lambda: s2.rect([30, 20], rounding=-4), [38.0, 20.0]),
]


@needs_native_2d_bbox
@pytest.mark.parametrize(
    ("name", "plain", "flared", "size"), NEGATIVE_TREATMENTS, ids=[row[0] for row in NEGATIVE_TREATMENTS]
)
def test_a_negative_treatment_flares_the_corners_outward(
    name: str,
    plain: object,  # noqa: ARG001 - shared table
    flared: object,
    size: list[float],
) -> None:
    assert [float(v) for v in flared().bounds().size] == pytest.approx(size, abs=0.01), name  # type: ignore[operator]


def test_cuboid_negative_chamfer_flares_outward() -> None:
    from pybosl2.shapes3d import cuboid as _cuboid

    flared = _cuboid([20, 20, 20], chamfer=-4)
    # 4mm of flare on each side of X and Y; the Z faces are untouched
    assert [float(v) for v in flared.bounds().size] == pytest.approx([28.0, 28.0, 20.0], abs=0.01)


def test_cyl_negative_rounding_flares_outward() -> None:
    from pybosl2.shapes3d import cyl

    plain = cyl(height=20, radius=10)
    flared = cyl(height=20, radius=10, rounding=-2)
    before = [float(v) for v in plain.bounds().size]
    after = [float(v) for v in flared.bounds().size]
    # 2mm of flare on each side; the Y figure carries the facet error of the default cylinder
    assert all(a == pytest.approx(b + 4.0, abs=0.05) for a, b in zip(after, before, strict=True))


# ── import2d / import3d coverage ────────────────────────────────────────────


def test_osimport_2d_with_kwargs_creates_shape() -> None:
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".svg") as f:
        f.write(b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>')
        f.flush()
        result = s2.osimport(f.name, convexity=2, center=True)
        assert isinstance(result, Bosl2Shape2D)
        # measured inside the block: the import is lazy, so the file has to still be there
        if result.shape.size is not None:  # the imported 10x10 rect, as the SVG declared it
            assert [float(v) for v in result.bounds().size] == pytest.approx([10.0, 10.0], abs=0.01)


def test_osimport_3d_with_kwargs_creates_shape() -> None:
    import tempfile

    from pybosl2.shapes3d import osimport as _oi3d

    with tempfile.NamedTemporaryFile(suffix=".stl") as f:
        stl = (
            b"solid test\nfacet normal 0 0 0\nouter loop\n"
            b"vertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\n"
            b"endloop\nendfacet\nendsolid test"
        )
        f.write(stl)
        f.flush()
        result = _oi3d(f.name, convexity=2, center=True)
        assert isinstance(result, Bosl2Solid)
        # the single triangle the STL declares: 1mm on each leg, flat in Z. Measured inside the
        # block, since the import is lazy and needs the file to still exist.
        assert [float(v) for v in result.bounds().size] == pytest.approx([1.0, 1.0, 0.0], abs=0.01)

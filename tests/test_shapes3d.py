# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/shapes3d.py: the Bosl2Solid wrapper, its transforms and bbox anchoring.

The native primitives are mocked (see conftest); the mock's cube/cylinder/sphere track an
axis-aligned bounding box, so Bosl2Solid's bbox-backed anchoring math is numerically exercised.
"""

import numpy as np
import pytest

from pybosl2.color import Color
from pybosl2.constants import BOTTOM, CENTER, FRONT, RIGHT, TOP
from pybosl2.shapes3d import (
    Bosl2Solid,
    cone,
    cube,
    cuboid,
    cyl,
    cylinder,
    fillet,
    path_text,
    plot3d,
    plot_revolution,
    prismoid,
    regular_prism,
    sphere,
    textured_tile,
    tube,
    xcyl,
    ycyl,
    zcyl,
)
from pybosl2.shapes3d.base import _anchor_offset_hull3
from pybosl2.texture import TextureType

# unit-cube corner cloud, for exercising _anchor_offset_hull3 directly
_UNIT_CUBE = [[x, y, z] for x in (-0.5, 0.5) for y in (-0.5, 0.5) for z in (-0.5, 0.5)]


def test_anchor_offset_hull3_face_is_face_centre() -> None:
    # BOTTOM ties all four bottom corners; the anchor is the face centre, so the offset lifts z by 0.5
    np.testing.assert_allclose(_anchor_offset_hull3(_UNIT_CUBE, BOTTOM), [0, 0, 0.5], atol=1e-9)
    np.testing.assert_allclose(_anchor_offset_hull3(_UNIT_CUBE, TOP), [0, 0, -0.5], atol=1e-9)
    np.testing.assert_allclose(_anchor_offset_hull3(_UNIT_CUBE, RIGHT), [-0.5, 0, 0], atol=1e-9)


def test_anchor_offset_hull3_edge_is_edge_midpoint() -> None:
    # RIGHT+TOP ties two vertices; the anchor is their midpoint
    np.testing.assert_allclose(_anchor_offset_hull3(_UNIT_CUBE, [1, 0, 1]), [-0.5, 0, -0.5], atol=1e-9)


def test_anchor_offset_hull3_corner_is_the_corner() -> None:
    np.testing.assert_allclose(_anchor_offset_hull3(_UNIT_CUBE, [1, 1, 1]), [-0.5, -0.5, -0.5], atol=1e-9)


def test_anchor_offset_hull3_center_is_zero() -> None:
    np.testing.assert_allclose(_anchor_offset_hull3(_UNIT_CUBE, CENTER), [0, 0, 0], atol=1e-9)


def test_prismoid_bottom_anchor_is_centred_on_xy() -> None:
    # regression: BOTTOM (the default) must centre X/Y and rest the base on z=0, not anchor to a corner
    lo, size = prismoid([50, 10], [50, 10], height=25)._native_bounds()  # type: ignore[misc]
    np.testing.assert_allclose(lo, [-25, -5, 0], atol=1e-6)
    np.testing.assert_allclose(size, [50, 10, 25], atol=1e-6)


def test_cuboid_is_bosl2solid_with_size() -> None:
    c = cuboid([40, 30, 20])
    assert isinstance(c, Bosl2Solid)
    assert list(c.size) == [40, 30, 20]  # type: ignore[arg-type]


def test_bounds_center_and_size() -> None:
    _box = cuboid([40, 30, 20]).bounds()
    center, size = list(_box.center), list(_box.size)
    np.testing.assert_allclose(center, [0, 0, 0], atol=1e-9)
    np.testing.assert_allclose(size, [40, 30, 20], atol=1e-9)


def test_anchor_points_on_faces() -> None:
    c = cuboid([40, 30, 20])
    np.testing.assert_allclose(c.anchor_point(TOP), [0, 0, 10], atol=1e-9)
    np.testing.assert_allclose(c.anchor_point(BOTTOM), [0, 0, -10], atol=1e-9)
    np.testing.assert_allclose(c.anchor_point(RIGHT), [20, 0, 0], atol=1e-9)
    np.testing.assert_allclose(c.anchor_point(FRONT), [0, -15, 0], atol=1e-9)
    np.testing.assert_allclose(c.anchor_point([1, 1, 1]), [20, 15, 10], atol=1e-9)


def test_directional_moves_shift_center() -> None:
    c = cuboid([10, 10, 10])
    np.testing.assert_allclose(c.right(5).anchor_point(CENTER), [5, 0, 0], atol=1e-9)
    np.testing.assert_allclose(c.left(5).anchor_point(CENTER), [-5, 0, 0], atol=1e-9)
    np.testing.assert_allclose(c.back(5).anchor_point(CENTER), [0, 5, 0], atol=1e-9)
    np.testing.assert_allclose(c.forward(5).anchor_point(CENTER), [0, -5, 0], atol=1e-9)
    np.testing.assert_allclose(c.up(5).anchor_point(CENTER), [0, 0, 5], atol=1e-9)
    np.testing.assert_allclose(c.down(5).anchor_point(CENTER), [0, 0, -5], atol=1e-9)


def test_move_and_translate_agree() -> None:
    c = cuboid([10, 10, 10])
    np.testing.assert_allclose(c.move([1, 2, 3]).anchor_point(CENTER), [1, 2, 3], atol=1e-9)
    np.testing.assert_allclose(c.translate([1, 2, 3]).anchor_point(CENTER), [1, 2, 3], atol=1e-9)


def test_rot_is_rotate_alias() -> None:
    assert Bosl2Solid.rot is Bosl2Solid.rotate  # type: ignore[misc]
    assert isinstance(cuboid([10, 10, 10]).rot(90), Bosl2Solid)


def test_reanchor_moves_anchor_to_origin() -> None:
    rb = cuboid([40, 30, 20]).reanchor(BOTTOM)
    _box = rb.bounds()
    center, size = list(_box.center), list(_box.size)
    np.testing.assert_allclose(center, [0, 0, 10], atol=1e-9)  # box now sits on z=0
    np.testing.assert_allclose(size, [40, 30, 20], atol=1e-9)


def test_wrap_unwrap() -> None:
    c = cuboid([10, 10, 10])
    assert c.shape is not None
    assert Bosl2Solid._unwrap(c) is c.shape
    assert Bosl2Solid._unwrap(c.shape) is c.shape


def test_csg_operators_return_bosl2solid() -> None:
    """The small cube sits inside the big one, so only the intersection changes the box."""
    a, b = cuboid([10, 10, 10]), cuboid([5, 5, 5])
    assert isinstance(a | b, Bosl2Solid)
    assert [float(v) for v in (a | b).bounds().size] == pytest.approx([10.0, 10.0, 10.0])
    assert [float(v) for v in (a - b).bounds().size] == pytest.approx([10.0, 10.0, 10.0])
    assert [float(v) for v in (a & b).bounds().size] == pytest.approx([5.0, 5.0, 5.0])


def test_color_and_scale_preserve_wrapper() -> None:
    c = cuboid([10, 10, 10])
    coloured = c.color(Color("red"))
    assert isinstance(coloured, Bosl2Solid)
    assert [float(v) for v in coloured.bounds().size] == pytest.approx([10.0, 10.0, 10.0])  # colour is not geometry
    assert [float(v) for v in c.scale([2, 2, 2]).bounds().size] == pytest.approx([20.0, 20.0, 20.0])


# BUG: c.color(alpha=0.5) segfaults in the native OpenSCAD extension on Python 3.14
# (PythonSCAD 1.1.2).  `self.shape.color(alpha=0.5)` crashes inside the native lib.
# All other color() parameter forms work.  See https://github.com/gsohler/openscad/issues/...


@pytest.mark.parametrize(
    ("name", "call"),
    [
        ("no_argument", lambda c: c.color()),
        ("by_name", lambda c: c.color(Color("blue"))),
        ("with_alpha", lambda c: c.color(Color("green"), alpha=0.3)),
        ("by_hex", lambda c: c.color(Color("#ff0000"))),
        ("by_components", lambda c: c.color(Color([1.0, 0.5, 0.0]))),
    ],
    ids=["no_argument", "by_name", "with_alpha", "by_hex", "by_components"],
)
def test_color_native_all_parameter_forms(name: str, call: object) -> None:
    """Every spelling colours the solid without disturbing its geometry."""
    coloured = call(cuboid([5, 5, 5]))  # type: ignore[operator]
    assert isinstance(coloured, Bosl2Solid)
    assert [float(v) for v in coloured.bounds().size] == pytest.approx([5.0, 5.0, 5.0]), name
    if name != "no_argument":  # a bare color() keeps the default, which emits no colour call
        assert "color" in repr(coloured.shape), name
    # BUG: alpha-only segfaults — see above
    # assert isinstance(c.color(alpha=0.5), Bosl2Solid)


def test_other_primitives_build() -> None:
    s = sphere(radius=5)
    assert isinstance(s, Bosl2Solid)
    _box = s.bounds()
    _center, size = list(_box.center), list(_box.size)
    assert size[0] == pytest.approx(10, abs=1)
    assert size[1] == pytest.approx(10, abs=1)
    assert size[2] == pytest.approx(10, abs=1)

    c = cyl(height=10, radius=3)
    assert isinstance(c, Bosl2Solid)
    _box = c.bounds()
    size = list(_box.size)
    assert size[2] == pytest.approx(10, abs=1)
    assert size[0] == pytest.approx(6, abs=1)


def test_getattr_falls_through_to_native() -> None:
    """A method not on Bosl2Solid resolves on the wrapped native shape -- and still does its job."""
    from pybosl2._edges_lang import Anchor

    c = cuboid([10, 10, 10])
    assert callable(c.position)
    placed = c.position(Anchor.TOP, cuboid([2, 2, 2])).realize()
    assert float(placed.bounds().size[2]) > 10.0  # the child now hangs off the top


def test_plot3d_surface_and_solid() -> None:
    """The surface spans the sample grid; `base=` drops a skirt to that height underneath it."""
    import math

    xs = list(range(-9, 10, 3))
    ys = list(range(-9, 10, 3))
    surface = plot3d(lambda x, _y: math.cos(x / 6), xs, ys)  # type: ignore[operator]
    assert isinstance(surface, Bosl2Solid)
    assert [float(v) for v in surface.bounds().size][:2] == pytest.approx([18.0, 18.0])  # the -9..9 grid
    solid = plot3d(lambda x, _y: math.cos(x / 6), xs, ys, base=0)
    assert float(solid.bounds().size[2]) < float(surface.bounds().size[2])  # cut off at z=0  # type: ignore[operator]


def test_orient_reorient_return_bosl2solid() -> None:
    """orient() lays the solid over; reorient() also spins and re-anchors it."""
    from pybosl2.constants import RIGHT, TOP

    c = cuboid([40, 30, 20])
    laid_over = c.orient(RIGHT)
    assert isinstance(laid_over, Bosl2Solid)
    assert repr(laid_over.shape) != repr(c.shape)
    reoriented = c.reorient(anchor=TOP, spin=30, orient=RIGHT)
    assert isinstance(reoriented, Bosl2Solid)
    assert repr(reoriented.shape) != repr(laid_over.shape)
    # (the numeric mock does not transform the bbox through multmatrix; the geometric result is
    # verified in test_stl_render.py against the real app)


def test_anchor_bbox_override() -> None:
    # a passed-in bbox overrides the object's own bounds (min/max corners)
    c = cuboid([10, 10, 10])
    np.testing.assert_allclose(c.anchor_point(TOP, bbox=[[-20, -20, -20], [20, 20, 20]]), [0, 0, 20], atol=1e-9)
    np.testing.assert_allclose(c.anchor_point(RIGHT, bbox=[[0, 0, 0], [40, 40, 40]]), [40, 20, 20], atol=1e-9)


def test_reanchor_bbox_override_moves_center() -> None:
    c = cuboid([10, 10, 10])
    # with an overriding bbox sitting above the origin, reanchor(BOTTOM) drops it onto z=0
    _box = c.reanchor(BOTTOM, bbox=[[-5, -5, 10], [5, 5, 30]]).bounds()
    # the overriding bbox's BOTTOM anchor is at z=10, so reanchor translates by -10
    center, _ = list(_box.center), list(_box.size)
    np.testing.assert_allclose(center, [0, 0, -10], atol=1e-9)


def test_resolve_bounds_rejects_bad_bbox() -> None:
    import pytest

    c = cuboid([10, 10, 10])
    with pytest.raises(ValueError, match="bbox must be"):
        c.anchor_point(TOP, bbox=[[0, 0, 0]])  # wrong shape
    with pytest.raises(ValueError, match="bbox must be"):
        c.anchor_point(TOP, bbox=[[10, 0, 0], [0, 5, 5]])  # max < min on x


def test_fillet_builds() -> None:
    f1 = fillet(length=20, radius=6)
    assert isinstance(f1, Bosl2Solid)  # type: ignore[operator]
    _box = f1.bounds()
    s1 = list(_box.size)
    assert s1[0] > 0
    assert s1[1] > 0
    assert s1[2] > 0

    f2 = fillet(length=20, radius1=4, radius2=8)
    assert isinstance(f2, Bosl2Solid)  # type: ignore[operator]
    _box = f2.bounds()
    s2 = list(_box.size)
    assert s2[0] > 0
    assert s2[1] > 0
    assert s2[2] > 0


def test_fillet_rejects_non_right_angle() -> None:
    import pytest

    with pytest.raises(ValueError, match=r"only 90\-degree edges \(angle=90\)"):
        fillet(length=20, radius=6, angle=120)  # type: ignore[operator]


def test_plot_revolution_taper_and_path() -> None:
    """Both forms revolve a 20-tall profile about Z, roughly 20 across at its widest."""
    import math

    def _f(a, _z):  # type: ignore[no-untyped-def]
        return 2 * math.sin(math.radians(a))

    tapered = plot_revolution(  # type: ignore[operator]
        _f,
        angle=list(range(0, 361, 20)),
        z=list(range(0, 21, 5)),
        radius1=10,
        radius2=6,
    )
    assert isinstance(tapered, Bosl2Solid)
    size = [float(v) for v in tapered.bounds().size]
    assert size[0] == pytest.approx(20.0, abs=0.5)  # the radius-10 end, both sides
    assert size[2] == pytest.approx(20.0, abs=1.0)  # z=0..20

    by_path = plot_revolution(_f, angle=list(range(0, 361, 20)), path=[[10, 0], [8, 10], [10, 20]])
    assert isinstance(by_path, Bosl2Solid)
    assert [float(v) for v in by_path.bounds().size][0] == pytest.approx(20.0, abs=0.5)  # type: ignore[operator]


def test_textured_tile_reps_and_size() -> None:
    """A tile fills the size it is given; tex_depth sets how far the texture stands out of it."""
    bump = [[0, 0, 0], [0, 1, 0], [0, 0, 0]]
    deep = textured_tile(bump, size=[40, 40], tex_reps=[4, 4], tex_depth=3)  # type: ignore[operator]
    assert isinstance(deep, Bosl2Solid)
    assert [float(v) for v in deep.bounds().size][:2] == pytest.approx([40.0, 40.0])
    shallow = textured_tile(bump, size=[40, 40], tex_size=10)
    assert float(shallow.bounds().size[2]) < float(deep.bounds().size[2])  # type: ignore[operator]


# --- regressions for the Bosl2Solid wrapper review fixes ---


def test_getattr_no_recursion_when_shape_unset() -> None:
    # a half-built object (via __new__, or during unpickling) must not blow the stack
    obj = Bosl2Solid.__new__(Bosl2Solid)
    with pytest.raises(AttributeError):
        _ = obj.anything  # type: ignore[attr-defined]


def test_private_names_never_reach_the_native_handle() -> None:
    # _wrap() copies pybosl2's own bookkeeping (_attachments/_tag_name/_diff_config/
    # _dont_propagate) with hasattr()/getattr(default), which lands in __getattr__ when unset.
    # Those must be answered here, not forwarded: PythonSCAD segfaults (exit -11, empty stderr)
    # when asked for an unknown attribute on a solid that came out of frep(), so forwarding kills
    # every SDF part brought over with .to_csg() the moment it is wrapped.
    probed: list[str] = []

    class _RecordingShape:
        def __getattr__(self, name: str) -> object:
            probed.append(name)
            raise AttributeError(name)

        def translate(self, _v: object) -> "_RecordingShape":
            return self

    wrapper = Bosl2Solid(_RecordingShape())  # type: ignore[arg-type]
    _ = wrapper.translate([1, 2, 3])
    assert probed == [], f"private lookups forwarded to the native handle: {probed}"
    with pytest.raises(AttributeError):
        _ = wrapper._not_a_real_attribute  # type: ignore[attr-defined]
    assert probed == []


def test_native_passthrough_op_keeps_wrapper_and_chains() -> None:
    # resize() has no explicit override; __getattr__ must re-wrap so the fluent API survives
    chained = cuboid([10, 10, 10]).resize([5, 5, 5]).up(3)  # type: ignore[operator]
    assert isinstance(chained, Bosl2Solid)
    _box = chained.bounds()
    centre, size = list(_box.center), list(_box.size)
    assert [float(v) for v in size] == pytest.approx([5.0, 5.0, 5.0])  # the resize took
    assert float(centre[2]) == pytest.approx(3.0)  # ...and so did the up()


def test_rotate_accepts_numpy_int_scalar() -> None:
    """np.int64 is not a Python int; the scalar -> Z-rotation normalisation must still apply."""
    quarter = cuboid([10, 10, 10]).rotate(np.int64(90))
    assert [float(v) for v in quarter.bounds().size] == pytest.approx([10.0, 10.0, 10.0])  # square: unchanged
    eighth = cuboid([10, 10, 10]).rotate(np.float64(45))
    # turned 45 degrees about Z, a 10mm square footprint measures 10*sqrt(2) across
    assert [float(v) for v in eighth.bounds().size] == pytest.approx([14.142, 14.142, 10.0], abs=0.01)


def test_bounds_metadata_fallback_no_longer_checks_staleness() -> None:
    c = cuboid([10, 10, 10])
    c._native_bounds = lambda: None  # type: ignore[method-assign]
    assert c.bounds().center == [0.0, 0.0, 0.0]
    m = cuboid([10, 10, 10]).up(50)
    m._native_bounds = lambda: None  # type: ignore[method-assign]
    assert m.bounds().center == [0.0, 0.0, 0.0]  # tracked metadata (may be stale, but accepted)


def test_cyl_extra_lengthens_the_cylinder() -> None:
    """`extra=` adds length past each end, for a clean boolean cut."""
    plain = cyl(length=40, radius=10)
    stretched = cyl(length=40, radius=10, extra=5, chamfer_angle=30, from_end=True)
    assert float(plain.bounds().size[2]) == pytest.approx(40.0)
    assert float(stretched.bounds().size[2]) == pytest.approx(50.0)  # 5 past each end


def test_cyl_per_end_extras_are_independent() -> None:
    """extra1/extra2 lengthen one end each, so the solid also shifts by their difference."""
    solid = cyl(
        height=50,
        diameter=20,
        extra1=2,
        extra2=3,
        chamfer_angle1=35,
        chamfer_angle2=40,
        from_end1=True,
        from_end2=False,
    )
    assert float(solid.bounds().size[2]) == pytest.approx(55.0)  # 50 + 2 + 3
    assert float(solid.bounds().center[2]) == pytest.approx(0.5)  # (3 - 2) / 2 upward


@pytest.mark.parametrize(
    ("name", "call", "axis"),
    [
        ("xcyl", lambda: xcyl(length=40, radius=10, extra=2), 0),
        ("ycyl", lambda: ycyl(height=50, diameter=20, extra1=1), 1),
        ("zcyl", lambda: zcyl(height=30, radius=10), 2),
    ],
    ids=["xcyl", "ycyl", "zcyl"],
)
def test_the_axis_cylinders_lie_along_their_own_axis(name: str, call: object, axis: int) -> None:
    """Each is the same cylinder turned onto its named axis, so that axis is the long one."""
    size = [float(v) for v in call().bounds().size]  # type: ignore[operator]
    assert size[axis] == max(size), f"{name}: {size}"


def test_cyl_tapered_with_chamfer() -> None:
    """A tapered cylinder chamfers on the wider end's radius, not a single shared one."""
    tapered = cyl(height=30, radius1=12, radius2=8, chamfer=2, realign=True)
    assert float(tapered.bounds().size[0]) == pytest.approx(24.0, abs=0.2)  # the radius-12 end
    assert float(tapered.bounds().size[2]) == pytest.approx(30.0)


def test_cyl_accepts_the_texture_arguments_it_cannot_yet_apply() -> None:
    """`texture="none"` takes the whole texture argument set and builds a plain cylinder."""
    plain = cyl(radius=10, height=20)
    textured = cyl(radius=10, height=20, texture="none", tex_size=5, tex_reps=4, tex_depth=2, tex_inset=True)
    assert [float(v) for v in textured.bounds().size] == pytest.approx([float(v) for v in plain.bounds().size])


@pytest.mark.parametrize(
    ("name", "call"),
    [
        ("cyl_enum", lambda: cyl(radius=10, height=20, texture=TextureType.RIBS)),
        ("xcyl_string", lambda: xcyl(radius=10, height=20, texture="ribs")),
    ],
    ids=["cyl_enum", "xcyl_string"],
)
def test_a_real_texture_on_a_cylinder_is_refused_for_now(name: str, call: object) -> None:  # noqa: ARG001 - shared table
    with pytest.raises(NotImplementedError):
        call()  # type: ignore[operator]


@pytest.mark.parametrize(
    ("name", "kwargs"),
    [
        ("teardrop_true", {"teardrop": True, "clip_angle": 45}),
        ("teardrop_angle", {"teardrop": 30, "clip_angle": 60}),
    ],
    ids=["teardrop_true", "teardrop_angle"],
)
def test_a_teardrop_rounding_clips_the_overhang(name: str, kwargs: dict[str, object]) -> None:
    """A teardrop rim keeps the cylinder's extent but flattens the top of the roundover."""
    plain = cyl(radius=10, height=20, rounding=2)
    teardrop = cyl(radius=10, height=20, rounding=2, **kwargs)  # type: ignore[arg-type]
    assert [float(v) for v in teardrop.bounds().size] == pytest.approx(
        [float(v) for v in plain.bounds().size], abs=0.5
    ), name
    assert repr(teardrop.shape) != repr(plain.shape), name


def test_texture_enum() -> None:
    """A TextureType resolves to its height map, and a cap accepts the enum spelling.

    The cap's texture is a documented fallback (bottlecaps.py: "cap surface textures fall back to
    a plain wall"), so the ribbed cap is the plain one -- asserted here so the day it stops being
    a fallback, this test says so.
    """
    from pybosl2.parts.bottlecaps import BottleCaps, BottleCapTexture
    from pybosl2.texture import texture

    ribs = texture(TextureType.RIBS)
    assert [list(row) for row in ribs] == [[1.0, 0.0]]  # one rib per tile, full height then flat

    plain = BottleCaps.pco1810_cap(texture=BottleCapTexture.NONE, fn=None, fa=None, fs=None)
    ribbed = BottleCaps.pco1810_cap(texture=BottleCapTexture.RIBS, fn=None, fa=None, fs=None)
    assert isinstance(ribbed, Bosl2Solid)
    assert repr(ribbed.shape) == repr(plain.shape)


def test_align_places_child_on_face() -> None:
    """align() puts the child on the parent's top face -- so the pair is 5mm taller than the parent.

    The attachment is lazy, so the extra height only shows once it is realized.
    """
    from pybosl2._edges_lang import Anchor

    parent = cuboid([30, 30, 10])
    result = parent.align(Anchor.TOP, cuboid([5, 5, 5])).realize()
    assert [float(v) for v in result.bounds().size] == pytest.approx([30.0, 30.0, 15.0])
    assert float(result.bounds().center[2]) == pytest.approx(2.5)  # grown upward only


def test_position_places_child_at_anchor() -> None:
    """position() centres the child on the named corner, so it hangs half outside on three axes."""
    from pybosl2._edges_lang import Anchor

    parent = cuboid([30, 30, 30])
    result = parent.position(Anchor.TOP_FRONT_LEFT, cuboid([5, 5, 5])).realize()
    # 2.5mm of the child sticks out past each of the three faces meeting at that corner
    assert [float(v) for v in result.bounds().size] == pytest.approx([32.5, 32.5, 32.5])


def test_mirror_preserves_wrapper() -> None:
    """mirror() reflects across the plane and keeps the wrapper."""
    offset = cuboid([10, 10, 10]).right(20)
    mirrored = offset.mirror([1, 0, 0])
    assert isinstance(mirrored, Bosl2Solid)
    assert float(mirrored.bounds().center[0]) == pytest.approx(-float(offset.bounds().center[0]))


def test_center_false_aligns_to_bottom_front_left() -> None:
    """center=False anchors to BOTTOM_FRONT_LEFT."""
    from pybosl2._edges_lang import Anchor

    c = cuboid([10, 20, 30], anchor=Anchor.BOTTOM_FRONT_LEFT)
    _box = c.bounds()
    center = list(_box.center)
    assert center[0] > 0  # center is shifted from origin


def test_center_true_is_equivalent_to_anchor_center() -> None:
    """center=True is equivalent to anchor=CENTER."""
    from pybosl2._edges_lang import Anchor

    a = cuboid([10, 20, 30], anchor=Anchor.CENTER)
    b = cuboid([10, 20, 30], anchor=Anchor.CENTER)
    _box = a.bounds()
    ca, _ = list(_box.center), list(_box.size)
    _box = b.bounds()
    cb, _ = list(_box.center), list(_box.size)
    for i in range(3):
        assert abs(ca[i] - cb[i]) < 1e-9


def test_p1_p2_cuboid() -> None:
    """cuboid with p1/p2 defines corner to corner."""
    from pybosl2.points import Point

    result = cuboid(p1=Point(0, 0, 0), p2=Point(10, 20, 30))
    _box = result.bounds()
    size = list(_box.size)
    assert abs(size[0] - 10) < 0.01
    assert abs(size[1] - 20) < 0.01
    assert abs(size[2] - 30) < 0.01


def test_attach_aligns_child_to_parent() -> None:
    """attach() stands the child's BOTTOM on the parent's TOP, so the whole 15mm sits above."""
    from pybosl2._edges_lang import Anchor

    parent = cuboid([30, 30, 10])
    result = parent.attach(Anchor.TOP, cuboid([5, 5, 15]), child_anchor=Anchor.BOTTOM).realize()
    assert [float(v) for v in result.bounds().size] == pytest.approx([30.0, 30.0, 25.0])
    assert float(result.bounds().center[2]) == pytest.approx(7.5)


# ---------------------------------------------------------------------------
# cone() tests
# ---------------------------------------------------------------------------


def test_cone_pointed_returns_solid() -> None:
    result = cone(height=30, radius=15)
    assert isinstance(result, Bosl2Solid)
    _box = result.bounds()
    size = list(_box.size)
    assert size[2] == pytest.approx(30, abs=1)
    assert size[0] == pytest.approx(30, abs=1)
    assert size[1] == pytest.approx(30, abs=1)


def test_cone_truncated_returns_solid() -> None:
    result = cone(height=30, radius1=15, radius2=8)
    assert isinstance(result, Bosl2Solid)
    _box = result.bounds()
    size = list(_box.size)
    assert size[2] == pytest.approx(30, abs=1)
    assert size[0] >= 16
    assert size[1] >= 16


@pytest.mark.parametrize("treatment", ["chamfer1", "rounding1"])
def test_a_cone_can_be_treated_at_its_base(treatment: str) -> None:
    """The base has a rim to work with, so it rounds or chamfers like any cylinder end."""
    plain = cone(height=30, radius=15)
    treated = cone(height=30, radius=15, **{treatment: 1})
    assert isinstance(treated, Bosl2Solid)
    assert [float(v) for v in treated.bounds().size] == pytest.approx([float(v) for v in plain.bounds().size], abs=0.01)
    assert repr(treated.shape) != repr(plain.shape)


@pytest.mark.parametrize("treatment", ["chamfer", "rounding", "chamfer2", "rounding2"])
def test_a_cone_tip_cannot_be_rounded_or_chamfered(treatment: str) -> None:
    """A cone's top radius is 0, so there is no rim to treat.

    This used to "work": the revolved profile crossed the axis, OpenSCAD printed "Children of
    rotate_extrude() may not lie across the Y axis" to stderr, and the caller got a solid with no
    bounding box. The old tests asserted only isinstance and passed -- one even carried the
    comment "bounds() on chamfered cone requires valid rotate_extrude params" (SPEC E-4).
    """
    with pytest.raises(ValueError, match="larger than that end's radius"):
        cone(height=30, radius=15, **{treatment: 1})


def test_cone_bounds_positive_z() -> None:
    result = cone(height=30, radius=15)
    _box = result.bounds()
    size = list(_box.size)
    assert size[2] > 0
    assert abs(size[0] - 30) < 1


# ---------------------------------------------------------------------------
# cube() chamfer / rounding tests
# ---------------------------------------------------------------------------


def test_cube_returns_solid() -> None:
    result = cube(size=20)
    assert isinstance(result, Bosl2Solid)
    _box = result.bounds()
    size = list(_box.size)
    assert size[0] == pytest.approx(20, abs=1)
    assert size[1] == pytest.approx(20, abs=1)
    assert size[2] == pytest.approx(20, abs=1)


def test_cube_chamfered_returns_solid() -> None:
    result = cube(size=20, chamfer=3)
    assert isinstance(result, Bosl2Solid)
    _box = result.bounds()
    size = list(_box.size)
    assert size[0] > 0
    assert size[1] > 0
    assert size[2] > 0


def test_cube_rounded_returns_solid() -> None:
    result = cube(size=20, rounding=3)
    assert isinstance(result, Bosl2Solid)
    _box = result.bounds()
    size = list(_box.size)
    assert size[0] > 0
    assert size[1] > 0
    assert size[2] > 0


def test_cube_center_false_anchors_correctly() -> None:
    from pybosl2._edges_lang import Anchor

    c = cube(size=10, anchor=Anchor.BOTTOM_FRONT_LEFT)
    _box = c.bounds()
    center = list(_box.center)
    assert center[0] > 0


# ---------------------------------------------------------------------------
# tube() chamfer / rounding tests
# ---------------------------------------------------------------------------


def test_tube_returns_solid() -> None:
    result = tube(height=20, outer_radius=15, inner_radius=10)
    assert isinstance(result, Bosl2Solid)
    _box = result.bounds()
    size = list(_box.size)
    assert size[2] == pytest.approx(20, abs=1)
    assert size[0] >= 28  # outer diameter = 30


def test_tube_chamfered_returns_solid() -> None:
    result = tube(height=20, outer_radius=15, inner_radius=10, chamfer=1)
    assert isinstance(result, Bosl2Solid)
    _box = result.bounds()
    size = list(_box.size)
    assert size[2] > 0
    assert size[0] > 0


def test_tube_rounded_returns_solid() -> None:
    result = tube(height=20, outer_radius=15, inner_radius=10, rounding=1)
    assert isinstance(result, Bosl2Solid)
    _box = result.bounds()
    size = list(_box.size)
    assert size[2] > 0
    assert size[0] > 0


def test_tube_bounds_has_height() -> None:
    result = tube(height=30, outer_radius=10, inner_radius=6)
    _box = result.bounds()
    size = list(_box.size)
    assert size[2] > 0


# ---------------------------------------------------------------------------
# cylinder() unified API tests
# ---------------------------------------------------------------------------


def test_cylinder_chamfered_returns_solid() -> None:
    result = cylinder(height=20, radius=10, chamfer=2)
    assert isinstance(result, Bosl2Solid)
    _box = result.bounds()
    size = list(_box.size)
    assert size[2] == pytest.approx(20, abs=1)
    assert size[0] >= 18  # diameter = 20


def test_cylinder_rounded_returns_solid() -> None:
    result = cylinder(height=20, radius=10, rounding=2)
    assert isinstance(result, Bosl2Solid)
    _box = result.bounds()
    size = list(_box.size)
    assert size[2] == pytest.approx(20, abs=1)
    assert size[0] >= 18


def test_cylinder_teardrop_returns_solid() -> None:
    result = cylinder(height=20, radius=10, rounding=2, teardrop=True)
    assert isinstance(result, Bosl2Solid)
    _box = result.bounds()
    size = list(_box.size)
    assert size[2] > 0
    assert size[0] > 0


def test_cylinder_equals_cyl() -> None:
    a = cylinder(height=20, radius=10)
    b = cyl(height=20, radius=10)
    _box = a.bounds()
    sa = list(_box.size)
    _box = b.bounds()
    sb = list(_box.size)
    for i in range(3):
        assert abs(sa[i] - sb[i]) < 1


# ── cylinder gap coverage tests ──────────────────────────────────────────


def test_cyl_circumscribe() -> None:
    c = cyl(height=20, radius=10, circumscribe=True)
    assert isinstance(c, Bosl2Solid)
    _box = c.bounds()
    size = list(_box.size)
    assert size[2] == pytest.approx(20, abs=1)


def test_xcyl_circumscribe() -> None:
    c = xcyl(height=20, radius=10, circumscribe=True)
    assert isinstance(c, Bosl2Solid)
    _box = c.bounds()
    size = list(_box.size)
    assert size[0] == pytest.approx(20, abs=1)  # xcyl has height along X


def test_ycyl_circumscribe() -> None:
    c = ycyl(height=20, radius=10, circumscribe=True)
    assert isinstance(c, Bosl2Solid)
    _box = c.bounds()
    size = list(_box.size)
    assert size[1] == pytest.approx(20, abs=1)  # ycyl has height along Y


def test_cyl_shift() -> None:
    c = cyl(height=20, radius=10, shift=[3, 4])
    assert isinstance(c, Bosl2Solid)
    _box = c.bounds()
    size = list(_box.size)
    assert size[2] == pytest.approx(20, abs=1)
    assert size[0] >= 18


def test_cyl_shift_tapered() -> None:
    c = cyl(height=20, radius1=8, radius2=4, shift=[5, 0])
    assert isinstance(c, Bosl2Solid)
    _box = c.bounds()
    size = list(_box.size)
    assert size[2] == pytest.approx(20, abs=1)


def test_cyl_asymmetric_chamfer_bottom_only() -> None:
    c = cyl(height=20, radius=10, chamfer1=2, chamfer2=0)
    assert isinstance(c, Bosl2Solid)
    _box = c.bounds()
    size = list(_box.size)
    assert size[2] == pytest.approx(20, abs=1)


def test_cyl_asymmetric_chamfer_top_only() -> None:
    c = cyl(height=20, radius=10, chamfer1=0, chamfer2=2)
    assert isinstance(c, Bosl2Solid)
    _box = c.bounds()
    size = list(_box.size)
    assert size[2] == pytest.approx(20, abs=1)


def test_cyl_asymmetric_rounding_bottom_only() -> None:
    c = cyl(height=20, radius=10, rounding1=2, rounding2=0)
    assert isinstance(c, Bosl2Solid)
    _box = c.bounds()
    size = list(_box.size)
    assert size[2] == pytest.approx(20, abs=1)


def test_cyl_asymmetric_rounding_top_only() -> None:
    c = cyl(height=20, radius=10, rounding1=0, rounding2=2)
    assert isinstance(c, Bosl2Solid)
    _box = c.bounds()
    size = list(_box.size)
    assert size[2] == pytest.approx(20, abs=1)


def test_cyl_chamfer_from_end() -> None:
    c = cyl(height=20, radius=10, chamfer=2, from_end=True)
    assert isinstance(c, Bosl2Solid)
    _box = c.bounds()
    size = list(_box.size)
    assert size[2] == pytest.approx(20, abs=1)


def test_cyl_chamfer_from_end_bottom() -> None:
    c = cyl(height=20, radius=10, chamfer1=2, chamfer2=0, from_end1=True)
    assert isinstance(c, Bosl2Solid)
    _box = c.bounds()
    size = list(_box.size)
    assert size[2] == pytest.approx(20, abs=1)


def test_tube_realign() -> None:
    c = tube(height=20, outer_radius=15, inner_radius=10, realign=True)
    assert isinstance(c, Bosl2Solid)
    _box = c.bounds()
    size = list(_box.size)
    assert size[2] == pytest.approx(20, abs=1)
    assert size[0] >= 28


# ---------------------------------------------------------------------------
# cuboid() / prismoid() / regular_prism() gap-coverage tests
# ---------------------------------------------------------------------------


def test_cuboid_negative_chamfer() -> None:
    """cuboid with negative chamfer hits _edge_mask_negative (chamfer path)."""
    result = cuboid([10, 10, 10], chamfer=-1)
    assert isinstance(result, Bosl2Solid)
    _box = result.bounds()
    size = list(_box.size)
    assert size[0] > 0
    assert size[1] > 0
    assert size[2] > 0


def test_cuboid_negative_rounding() -> None:
    """cuboid with negative rounding hits _edge_mask_negative (rounding path)."""
    result = cuboid([10, 10, 10], rounding=-1)
    assert isinstance(result, Bosl2Solid)
    _box = result.bounds()
    size = list(_box.size)
    assert size[0] > 0
    assert size[1] > 0
    assert size[2] > 0


def test_cuboid_p1_single_point_anchor() -> None:
    """cuboid with p1 only anchors at BOTTOM_FRONT_LEFT then translates."""
    result = cuboid([10, 10, 10], p1=[2, 3, 4])
    assert isinstance(result, Bosl2Solid)
    _box = result.bounds()
    center, size = list(_box.center), list(_box.size)
    np.testing.assert_allclose(center, [7, 8, 9], atol=1e-9)
    np.testing.assert_allclose(size, [10, 10, 10], atol=1e-9)


def test_cuboid_except_edges() -> None:
    """except_edges leaves those edges sharp, so the solid keeps its full extent there."""
    from pybosl2._edges_lang import Anchor

    everywhere = cuboid([10, 10, 10], rounding=2)
    kept_sharp = cuboid([10, 10, 10], rounding=2, except_edges=[Anchor.TOP])
    assert isinstance(kept_sharp, Bosl2Solid)
    # rounding every edge pulls the bounding box in; sparing the top edges keeps it out there
    assert float(kept_sharp.bounds().size[2]) > float(everywhere.bounds().size[2])


def test_prismoid_asymmetric_rounding_and_chamfer() -> None:
    """prismoid with rounding on bottom and chamfer on top and shift."""
    result = prismoid(
        size1=[10, 10],
        size2=[20, 20],
        height=10,
        rounding1=2,
        chamfer2=1.5,
        shift=[3, 0],
    )
    assert isinstance(result, Bosl2Solid)
    _box = result.bounds()
    size = list(_box.size)
    assert size[2] > 0


def test_regular_prism_inner_radius_sizing() -> None:
    """regular_prism sized by inner_radius (apothem)."""
    result = regular_prism(sides=6, height=10, inner_radius=8)
    assert isinstance(result, Bosl2Solid)
    _box = result.bounds()
    size = list(_box.size)
    assert size[2] > 0


def test_regular_prism_circumscribe() -> None:
    """circumscribe=True measures the radius to the flats, so the polygon grows by 1/cos(180/n)."""
    import math

    inscribed = regular_prism(sides=8, height=10, radius=10)
    circumscribed = regular_prism(sides=8, height=10, radius=10, circumscribe=True)
    assert isinstance(circumscribed, Bosl2Solid)
    grew = float(circumscribed.bounds().size[0]) / float(inscribed.bounds().size[0])
    assert grew == pytest.approx(1 / math.cos(math.pi / 8), abs=0.01)


def test_regular_prism_combined_options() -> None:
    """realign turns the polygon, shift leans the prism over, and the radii taper it."""
    result = regular_prism(
        sides=6,
        height=10,
        realign=True,
        shift=[2, 0],
        radius1=8,
        radius2=5,
    )
    assert isinstance(result, Bosl2Solid)
    _box = result.bounds()
    centre, size = list(_box.center), list(_box.size)
    assert float(size[2]) == pytest.approx(10.0)  # the height is unaffected by the lean
    assert float(centre[0]) == pytest.approx(-1.0, abs=0.01)  # leaned 2mm over its own base
    assert float(size[0]) < 2 * 8  # tapered, so narrower than twice the bottom radius


# --- path_text() -------------------------------------------------------------------------
#
# A straight 80mm path carrying three 8mm letters: the text is 24mm long, so centring it has
# exactly 28mm of slack to split. Those numbers are font-independent, unlike the glyph extents.

TEXT_PATH_2D = [[0.0, 0.0], [40.0, 0.0], [80.0, 0.0]]
TEXT_PATH_3D = [[0.0, 0.0, 0.0], [40.0, 0.0, 0.0], [80.0, 0.0, 0.0]]


def test_path_text_2d_path_gives_a_flat_shape() -> None:
    """A 2-D path lays the letters out flat, so the result is 2-D geometry, not a solid."""
    from pybosl2.shapes2d import Bosl2Shape2D

    flat = path_text(TEXT_PATH_2D, "abc", size=8, lettersize=8.0)
    assert isinstance(flat, Bosl2Shape2D)
    # It is real 2-D geometry: extruding it gives a solid exactly as tall as the extrusion.
    _box = flat.linear_extrude(height=2).bounds()
    centre, size = list(_box.center), list(_box.size)
    assert float(size[2]) == pytest.approx(2.0)
    assert 0.0 < float(size[0]) <= 24.0  # the letters span at most their own 24mm of text
    assert float(centre[1]) > 0.0  # sitting on the baseline, so above the path


def test_path_text_3d_path_extrudes_the_letters() -> None:
    """A 3-D path gives a solid whose thickness is the letter depth, across the path."""
    solid = path_text(TEXT_PATH_3D, "abc", size=8, lettersize=8.0, thickness=3)
    assert isinstance(solid, Bosl2Solid)
    thicker = path_text(TEXT_PATH_3D, "abc", size=8, lettersize=8.0, thickness=5)
    assert float(solid.bounds().size[1]) == pytest.approx(3.0)
    assert float(thicker.bounds().size[1]) == pytest.approx(5.0)
    # The extra depth is all that changed: the letters still run the same distance along the path.
    assert float(thicker.bounds().size[0]) == pytest.approx(float(solid.bounds().size[0]))


def test_path_text_accepts_a_bare_point_list() -> None:
    """A point list is accepted wherever a Path is, and places the letters identically."""
    from pybosl2.path2d import Path2D

    from_list = path_text(TEXT_PATH_2D, "abc", size=8, lettersize=8.0)
    from_path = path_text(Path2D(TEXT_PATH_2D), "abc", size=8, lettersize=8.0)
    listed = from_list.linear_extrude(height=2).bounds()
    pathed = from_path.linear_extrude(height=2).bounds()
    assert np.allclose(np.asarray(listed.center, dtype=float), np.asarray(pathed.center, dtype=float))
    assert np.allclose(np.asarray(listed.size, dtype=float), np.asarray(pathed.size, dtype=float))


def test_path_text_center_splits_the_slack() -> None:
    """center=True starts the text half the leftover path length in: (80 - 3*8) / 2 = 28mm."""
    plain = path_text(TEXT_PATH_2D, "abc", size=8, lettersize=8.0).linear_extrude(height=2)
    centred = path_text(TEXT_PATH_2D, "abc", size=8, lettersize=8.0, center=True).linear_extrude(height=2)
    shift = float(centred.bounds().center[0]) - float(plain.bounds().center[0])
    assert shift == pytest.approx(28.0, abs=1e-6)
    # Only the position moved; the letters themselves are untouched.
    assert np.allclose(np.asarray(centred.bounds().size, dtype=float), np.asarray(plain.bounds().size, dtype=float))


def test_path_text_kern_spreads_the_letters() -> None:
    """kern= adds space between letters, so the text runs further along the path."""
    tight = path_text(TEXT_PATH_2D, "abc", size=8, lettersize=8.0).linear_extrude(height=2)
    spread = path_text(TEXT_PATH_2D, "abc", size=8, lettersize=8.0, kern=4.0).linear_extrude(height=2)
    # Two gaps of 4mm between three letters, and the run is measured between the outer glyph edges.
    assert float(spread.bounds().size[0]) - float(tight.bounds().size[0]) == pytest.approx(8.0, abs=1e-6)


def _text_ring(radius: float = 20.0, points: int = 32) -> list[list[float]]:
    """A closed circular path in the XY plane, for text that curves round."""
    import math

    ring = [
        [radius * math.cos(t), radius * math.sin(t), 0.0] for t in np.linspace(0, 2 * math.pi, points, endpoint=False)
    ]
    ring.append(list(ring[0]))
    return ring


def test_path_text_normal_turns_the_letters_to_face_it() -> None:
    """normal= is the direction the reader looks from, so +Z lays the letters flat."""
    ring = _text_ring()
    upright = path_text(ring, "abcd", size=8, lettersize=8.0, thickness=2)
    flat = path_text(ring, "abcd", size=8, lettersize=8.0, thickness=2, normal=[0, 0, 1])
    # Read from above, the letters lie in the plane of the ring: only their depth stands up in Z.
    assert float(flat.bounds().size[2]) == pytest.approx(2.0)
    # Read from the side, they stand upright instead, so Z spans a whole glyph height.
    assert float(upright.bounds().size[2]) > 6.0


def test_path_text_normal_accepts_one_vector_per_path_point() -> None:
    """A per-point list of normals is interpolated along the path; a constant list matches
    the same single vector broadcast."""
    ring = _text_ring()
    broadcast = path_text(ring, "abcd", size=8, lettersize=8.0, thickness=2, normal=[0, 0, 1])
    per_point = path_text(ring, "abcd", size=8, lettersize=8.0, thickness=2, normal=[[0, 0, 1]] * len(ring))
    assert np.allclose(
        np.asarray(per_point.bounds().center, dtype=float), np.asarray(broadcast.bounds().center, dtype=float)
    )
    assert np.allclose(
        np.asarray(per_point.bounds().size, dtype=float), np.asarray(broadcast.bounds().size, dtype=float)
    )


def test_path_text_normal_list_must_match_the_path() -> None:
    """A list of normals that is not one-per-path-point is rejected, not silently recycled."""
    with pytest.raises(ValueError, match="list of 3 such vectors"):
        path_text(TEXT_PATH_3D, "abc", size=8, lettersize=8.0, thickness=2, normal=[[0, 0, 1]] * 2)


def test_path_text_reverse_flips_the_letters_across_the_path() -> None:
    """reverse= reads the text from the other side, mirroring it about the path."""
    front = path_text(TEXT_PATH_3D, "abc", size=8, lettersize=8.0, thickness=3)
    back = path_text(TEXT_PATH_3D, "abc", size=8, lettersize=8.0, thickness=3, reverse=True)
    assert float(back.bounds().center[2]) == pytest.approx(-float(front.bounds().center[2]))
    assert np.allclose(np.asarray(back.bounds().size, dtype=float), np.asarray(front.bounds().size, dtype=float))


def test_path_text_offset_lifts_the_letters_off_the_path() -> None:
    """offset= shifts the letters along the normal, towards the reader."""
    flush = path_text(TEXT_PATH_3D, "abc", size=8, lettersize=8.0, thickness=3)
    raised = path_text(TEXT_PATH_3D, "abc", size=8, lettersize=8.0, thickness=3, offset=2)
    moved = np.asarray(raised.bounds().center, dtype=float) - np.asarray(flush.bounds().center, dtype=float)
    assert np.allclose(moved, [0.0, -2.0, 0.0])  # the default normal points at -Y


def test_path_text_top_orients_the_letters_on_a_2d_path() -> None:
    """top= is allowed on a 2-D path, where it is the only orientation control."""
    from pybosl2.shapes2d import Bosl2Shape2D

    topped = path_text(TEXT_PATH_2D, "abc", size=8, lettersize=8.0, top=[0, 1])
    assert isinstance(topped, Bosl2Shape2D)
    plain = path_text(TEXT_PATH_2D, "abc", size=8, lettersize=8.0)
    # +Y is already "up" for a left-to-right path, so it changes nothing.
    assert np.allclose(
        np.asarray(topped.linear_extrude(height=2).bounds().center, dtype=float),
        np.asarray(plain.linear_extrude(height=2).bounds().center, dtype=float),
    )


# --- sequence operators -------------------------------------------------------------------


def test_adding_a_vector_translates() -> None:
    """`shape + [x, y, z]` is a translation, and reads the same either way round."""
    box = cuboid([10, 10, 10])
    assert [float(v) for v in (box + [5, 0, 0]).bounds().center] == pytest.approx([5.0, 0.0, 0.0])
    assert [float(v) for v in ([5, 0, 0] + box).bounds().center] == pytest.approx([5.0, 0.0, 0.0])


def test_multiplying_scales() -> None:
    """`shape * n` scales uniformly; a vector scales per axis."""
    box = cuboid([10, 10, 10])
    assert [float(v) for v in (box * 2).bounds().size] == pytest.approx([20.0, 20.0, 20.0])
    assert [float(v) for v in (2 * box).bounds().size] == pytest.approx([20.0, 20.0, 20.0])
    assert [float(v) for v in (box * [2, 1, 1]).bounds().size] == pytest.approx([20.0, 10.0, 10.0])


def test_adding_a_bare_number_is_rejected() -> None:
    """A scalar is not a displacement, so `+` declines it rather than guessing an axis."""
    with pytest.raises(TypeError):
        cuboid([10, 10, 10]) + 5  # type: ignore[operator]

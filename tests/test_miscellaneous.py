# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/miscellaneous.py: the path extrusions (path_extrude2d / path_extrude on Path2D /
Path3D, taking a 2-D profile object rather than children), and the bounding-box / hull / minkowski
helpers. Native geometry is mocked, so these check the API surface (types, profile forms, error
cases); geometric correctness is verified in test_stl_render.py."""

import pytest

import pybosl2.shapes2d as s2
from pybosl2 import miscellaneous as m
from pybosl2.caps import CapType
from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D
from pybosl2.shapes3d import Bosl2Solid, cuboid, sphere

L_PATH = Path2D([[0, 0], [40, 0], [40, 40]], closed=False)
PATH3 = Path3D([[0, 0, 0], [20, 0, 10], [20, 20, 20]], closed=False)


# -- path_extrude2d -----------------------------------------------------------------------


def test_path_extrude2d_returns_solid() -> None:
    """The profile is swept along the path, so the solid covers the path plus half the profile."""
    swept = L_PATH.path_extrude2d(s2.square([4, 8], center=True))
    assert isinstance(swept, Bosl2Solid)
    _box = swept.bounds()
    # the 40x40 L, widened by the profile's 4mm width; the 8mm height becomes the Z extent
    centre, size = list(_box.center), list(_box.size)
    assert [float(v) for v in size] == pytest.approx([42.0, 42.0, 8.0], abs=0.01)
    assert float(centre[2]) == pytest.approx(0.0)


def test_path_extrude2d_accepts_various_profiles() -> None:
    """A shape, a Path2D, a Region and a factory are four spellings of the same 4x8 profile.

    They must sweep to the same solid -- a form that is quietly ignored would not.
    """
    from pybosl2.regions import Region

    rectangle = [[-2, -4], [2, -4], [2, 4], [-2, 4]]
    by_shape = L_PATH.path_extrude2d(s2.square([4, 8], center=True))
    expected = [float(v) for v in by_shape.bounds().size]
    for name, profile in (
        ("path2d", Path2D(rectangle)),
        ("region", Region([rectangle])),
        ("factory", lambda: s2.square([4, 8], center=True)),
    ):
        swept = L_PATH.path_extrude2d(profile)
        assert isinstance(swept, Bosl2Solid), name
        assert [float(v) for v in swept.bounds().size] == pytest.approx(expected, abs=0.01), name

    # a round profile sweeps the same path but tapers the corners, so it reaches a little further
    round_swept = L_PATH.path_extrude2d(s2.circle(radius=3))
    assert float(round_swept.bounds().size[0]) > expected[0]


def test_path_extrude2d_closed_and_caps() -> None:
    """A closed sweep is a ring around the whole loop; an open one is capped at its ends."""
    loop = Path2D([[0, 0], [40, 0], [40, 40], [0, 40]], closed=True)
    ring = loop.path_extrude2d(s2.square([4, 6], center=True), closed=True)
    assert [float(v) for v in ring.bounds().size] == pytest.approx([44.0, 44.0, 6.0], abs=0.01)

    straight = Path2D([[0, 0], [40, 0]], closed=False)
    bar = straight.path_extrude2d(s2.square([6, 8], center=True), caps=CapType.BUTT)
    assert float(bar.bounds().size[2]) == pytest.approx(8.0, abs=0.01)  # the profile's height
    assert float(bar.bounds().size[1]) == pytest.approx(6.0, abs=0.01)  # ...and its width  # type: ignore[arg-type]


def test_path_extrude2d_caps_on_closed_raises() -> None:
    loop = Path2D([[0, 0], [40, 0], [40, 40]], closed=True)
    with pytest.raises(ValueError, match="cannot cap a closed"):
        loop.path_extrude2d(s2.square([4, 8]), caps=CapType.BUTT, closed=True)  # type: ignore[arg-type]


def test_path_extrude2d_requires_2d_path() -> None:
    with pytest.raises(ValueError, match="must be 2-D"):
        PATH3.path_extrude2d(s2.circle(radius=3))


# -- path_extrude (2-D and 3-D paths) -----------------------------------------------------


def test_path_extrude_on_2d_path() -> None:
    """A 2-D spine sweeps in the XY plane, so the profile's diameter sets the Z extent."""
    tube = L_PATH.path_extrude(s2.circle(radius=3))
    assert isinstance(tube, Bosl2Solid)
    assert float(tube.bounds().size[2]) == pytest.approx(6.0, abs=0.3)  # the radius-3 profile


def test_path_extrude_on_3d_path() -> None:
    """A 3-D spine climbs, so the sweep spans the path's own extent in every axis."""
    tube = PATH3.path_extrude(s2.circle(radius=3))
    assert isinstance(tube, Bosl2Solid)
    _box = tube.bounds()
    centre, size = list(_box.center), list(_box.size)
    assert float(size[2]) > 10.0  # the spine rises from z=0 to z=20
    assert float(centre[2]) > 0.0


def test_path_extrude_factory_profile() -> None:
    """A callable profile is called once and swept exactly like the shape it returns."""
    direct = PATH3.path_extrude(s2.circle(radius=3))
    from_factory = PATH3.path_extrude(lambda: s2.circle(radius=3))
    assert isinstance(from_factory, Bosl2Solid)
    assert [float(v) for v in from_factory.bounds().size] == pytest.approx(
        [float(v) for v in direct.bounds().size], abs=0.01
    )


# -- free functions -----------------------------------------------------------------------


def test_extrude_from_to() -> None:
    """The profile is extruded between the two points, so the solid is centred on their midpoint."""
    slanted = m.extrude_from_to(s2.circle(radius=4), [0, 0, 0], [10, 20, 30])
    assert isinstance(slanted, Bosl2Solid)
    assert [float(v) for v in slanted.bounds().center] == pytest.approx([5.0, 10.0, 15.0], abs=0.1)

    tapered = m.extrude_from_to(s2.circle(radius=4), [0, 0, 0], [0, 0, 20], twist=90, scale=2)
    assert float(tapered.bounds().size[2]) == pytest.approx(20.0)  # straight up, 20 tall
    assert float(tapered.bounds().size[0]) == pytest.approx(8.0, abs=0.3)  # widened by scale=2


def test_extrude_from_to_same_point_raises() -> None:
    with pytest.raises(ValueError, match="points must differ"):
        m.extrude_from_to(s2.circle(radius=4), [1, 2, 3], [1, 2, 3])


def test_cylindrical_extrude() -> None:
    """The flat shape is wrapped round a cylinder, so its height becomes the Z extent."""
    wrapped = m.cylindrical_extrude(s2.square([20, 8]), inner_radius=25, outer_radius=30)
    assert isinstance(wrapped, Bosl2Solid)
    assert float(wrapped.bounds().size[2]) == pytest.approx(8.0, abs=0.01)  # the shape's own height

    # the diameter spelling names the same cylinder, and spin turns the wrapped patch around it
    by_diameter = m.cylindrical_extrude(s2.square([20, 8]), inner_diameter=50, outer_diameter=60, spin=45)
    assert float(by_diameter.bounds().size[2]) == pytest.approx(8.0, abs=0.01)
    assert float(by_diameter.bounds().center[0]) != pytest.approx(float(wrapped.bounds().center[0]))


def test_cylindrical_extrude_needs_radii() -> None:
    with pytest.raises(ValueError, match="positive inner and outer"):
        m.cylindrical_extrude(s2.square([20, 8]), inner_radius=25)


def test_chain_hull() -> None:
    """Consecutive pairs are hulled, so the result spans from the first child to the last."""
    bridged = m.chain_hull(cuboid([5, 5, 5]), sphere(radius=4).right(20))
    assert isinstance(bridged, Bosl2Solid)
    assert float(bridged.bounds().size[0]) == pytest.approx(26.5, abs=0.5)  # -2.5 out to 24

    stacked = m.chain_hull([cuboid([5, 5, 5]), sphere(radius=4), cuboid([3, 3, 3])])
    assert float(stacked.bounds().size[0]) == pytest.approx(8.0, abs=0.3)  # all three at the origin

    alone = m.chain_hull(cuboid([5, 5, 5]))  # a single object passes straight through
    assert [float(v) for v in alone.bounds().size] == pytest.approx([5.0, 5.0, 5.0])


def test_minkowski_difference() -> None:
    """Carving with a radius-8 sphere shrinks the cube by 8 on every side."""
    carved = m.minkowski_difference(cuboid([40, 40, 40]), sphere(radius=8))
    assert isinstance(carved, Bosl2Solid)
    assert [float(v) for v in carved.bounds().size] == pytest.approx([24.0, 24.0, 24.0], abs=0.3)


# -- Minkowski SUM (BaseShape.minkowski) ---------------------------------------------------
#
# There was no 3-D form at all: `"minkowski"` sat in _NATIVE_PASSTHROUGH, which made hasattr()
# look promising, but native minkowski() is a free FUNCTION, so the forward could never resolve
# and every call raised AttributeError. It now lives ONCE on the shared BaseShape rather than
# being duplicated in the CSG-specific 2-D and 3-D classes.


def test_minkowski_lives_on_the_shared_base_class() -> None:
    """One implementation, inherited by both dimensions -- not a copy per backend class."""
    from pybosl2._shape import BaseShape
    from pybosl2.shapes2d import Bosl2Shape2D

    assert "minkowski" in BaseShape.__dict__
    assert Bosl2Solid.minkowski is BaseShape.minkowski
    assert Bosl2Shape2D.minkowski is BaseShape.minkowski


def test_minkowski_sum_returns_a_solid() -> None:
    """Summing with a radius-2 sphere rounds the box and grows it by 2 on every side."""
    grown = cuboid([20, 30, 5]).minkowski(sphere(radius=2, fn=12))
    assert isinstance(grown, Bosl2Solid)
    assert [float(v) for v in grown.bounds().size] == pytest.approx([24.0, 34.0, 9.0], abs=0.3)


def test_minkowski_sum_keeps_2d_shapes_2d() -> None:
    """_wrap round-trips the result, so a 2-D operand does not come back as a solid."""
    from pybosl2.shapes2d import Bosl2Shape2D

    grown = s2.square([10, 10], center=True).minkowski(s2.circle(radius=3, fn=24))
    assert isinstance(grown, Bosl2Shape2D)
    if grown.shape.size is not None:  # needs the native 2-D bbox
        assert [float(v) for v in grown.bounds().size] == pytest.approx([16.0, 16.0], abs=0.1)


def test_minkowski_sum_grows_the_solid_by_the_swept_shape() -> None:
    """Sweeping a radius-r ball grows every side by ~2r -- the point of the operation."""
    grown = cuboid([20, 30, 5]).minkowski(sphere(radius=2, fn=48))
    _box = grown.bounds()
    _, size = list(_box.center), list(_box.size)
    for got, base in zip(size, (20, 30, 5), strict=True):
        assert got == pytest.approx(base + 4, abs=0.1)


def test_minkowski_sum_accepts_several_shapes() -> None:
    """Variadic, like OpenSCAD's minkowski(): each is swept in turn, so the growth accumulates."""
    once = cuboid([10, 10, 10]).minkowski(cuboid([2, 2, 2]))
    twice = cuboid([10, 10, 10]).minkowski(cuboid([2, 2, 2]), cuboid([1, 1, 1]))
    assert once.bounds().size[0] == pytest.approx(12, abs=0.01)
    assert twice.bounds().size[0] == pytest.approx(13, abs=0.01)


def test_minkowski_sum_needs_a_shape() -> None:
    with pytest.raises(ValueError, match="at least one shape"):
        cuboid([5, 5, 5]).minkowski()


def test_native_passthrough_only_claims_real_native_methods() -> None:
    """Every name in the set must exist on the native object, or the forward cannot resolve.

    Six did not (`minkowski`, `set_modifier`, `convexity`, `fn`, `fa`, `fs`); they produced a
    confusing AttributeError while making membership checks look meaningful.
    """
    from pybosl2._shape import _NATIVE_PASSTHROUGH

    assert not (_NATIVE_PASSTHROUGH & {"minkowski", "set_modifier", "convexity", "fn", "fa", "fs"})


# -- Bosl2Solid methods -------------------------------------------------------------------

BOX = cuboid([40, 30, 20])


def test_bounding_box() -> None:
    """The box is the solid's own extent; excess= grows it by that much on each side."""
    tight = BOX.bounding_box()
    assert isinstance(tight, Bosl2Solid)
    assert [float(v) for v in tight.bounds().size] == pytest.approx([float(v) for v in BOX.bounds().size])
    loose = BOX.bounding_box(excess=3)
    assert [float(v) for v in loose.bounds().size] == pytest.approx(
        [v + 6 for v in [float(x) for x in BOX.bounds().size]]
    )


def test_offset3d_zero_is_noop() -> None:
    assert BOX.offset3d(0) is BOX


def test_offset3d_and_round3d() -> None:
    """offset3d grows or shrinks in every direction; round3d rounds without changing the size much."""
    before = [float(v) for v in BOX.bounds().size]
    grown = [float(v) for v in BOX.offset3d(2).bounds().size]
    shrunk = [float(v) for v in BOX.offset3d(-2).bounds().size]
    assert all(g > b for g, b in zip(grown, before, strict=True))
    assert all(s < b for s, b in zip(shrunk, before, strict=True))
    assert grown == pytest.approx([v + 4 for v in before], abs=0.4)
    assert shrunk == pytest.approx([v - 4 for v in before], abs=0.4)

    rounded = [float(v) for v in BOX.round3d(3).bounds().size]
    assert rounded == pytest.approx(before, abs=0.4)  # the corners go, the extent stays
    assert isinstance(BOX.round3d(outer_radius=2, inner_radius=1), Bosl2Solid)


def test_chain_hull_and_minkowski_diff_methods() -> None:
    """Both are also methods on the solid, doing the same as the module-level functions."""
    bridged = BOX.chain_hull(sphere(radius=5).right(30))
    # the 40mm box reaches x=20; the sphere at x=30 reaches x=35, so the hull spans -20..35
    assert float(bridged.bounds().size[0]) == pytest.approx(55.0, abs=0.5)

    carved = BOX.minkowski_difference(sphere(radius=4))
    before = [float(v) for v in BOX.bounds().size]
    assert [float(v) for v in carved.bounds().size] == pytest.approx([v - 8 for v in before], abs=0.3)


# ── multi-diff minkowski ────────────────────────────────────────────────


def test_minkowski_difference_multiple_diffs() -> None:
    """Each tool is carved in turn, so the total inset is the sum of their radii."""
    result = m.minkowski_difference(cuboid([20, 20, 20]), sphere(radius=3), sphere(radius=4))
    assert isinstance(result, Bosl2Solid)
    assert [float(v) for v in result.bounds().size] == pytest.approx([12.0, 12.0, 12.0], abs=0.3)


def test_cylindrical_extrude_default_size() -> None:
    """With no size= the shape's own extent is wrapped, so a d=20 circle spans 20 in Z."""
    from pybosl2.miscellaneous import cylindrical_extrude

    result = cylindrical_extrude(s2.circle(10), outer_radius=50, inner_radius=40)
    assert isinstance(result, Bosl2Solid)
    assert float(result.bounds().size[2]) == pytest.approx(20.0, abs=0.2)

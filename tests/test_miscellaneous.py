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
    assert isinstance(L_PATH.path_extrude2d(s2.square([4, 8], center=True)), Bosl2Solid)


def test_path_extrude2d_accepts_various_profiles() -> None:
    # native shape, a Path2D, a Region, a Bosl2Solid, and a factory all work as the profile
    assert isinstance(L_PATH.path_extrude2d(s2.circle(radius=3)), Bosl2Solid)
    assert isinstance(L_PATH.path_extrude2d(Path2D([[-2, -4], [2, -4], [2, 4], [-2, 4]])), Bosl2Solid)
    from pybosl2.regions import Region

    assert isinstance(
        L_PATH.path_extrude2d(Region([[[-2, -4], [2, -4], [2, 4], [-2, 4]]])),
        Bosl2Solid,
    )
    assert isinstance(L_PATH.path_extrude2d(lambda: s2.square([4, 8], center=True)), Bosl2Solid)


def test_path_extrude2d_closed_and_caps() -> None:
    loop = Path2D([[0, 0], [40, 0], [40, 40], [0, 40]], closed=True)
    assert isinstance(loop.path_extrude2d(s2.square([4, 6], center=True), closed=True), Bosl2Solid)
    straight = Path2D([[0, 0], [40, 0]], closed=False)
    assert isinstance(straight.path_extrude2d(s2.square([6, 8], center=True), caps=CapType.BUTT), Bosl2Solid)  # type: ignore[arg-type]


def test_path_extrude2d_caps_on_closed_raises() -> None:
    loop = Path2D([[0, 0], [40, 0], [40, 40]], closed=True)
    with pytest.raises(AssertionError):
        loop.path_extrude2d(s2.square([4, 8]), caps=CapType.BUTT, closed=True)  # type: ignore[arg-type]


def test_path_extrude2d_requires_2d_path() -> None:
    with pytest.raises(AssertionError):
        PATH3.path_extrude2d(s2.circle(radius=3))


# -- path_extrude (2-D and 3-D paths) -----------------------------------------------------


def test_path_extrude_on_2d_path() -> None:
    assert isinstance(L_PATH.path_extrude(s2.circle(radius=3)), Bosl2Solid)


def test_path_extrude_on_3d_path() -> None:
    assert isinstance(PATH3.path_extrude(s2.circle(radius=3)), Bosl2Solid)


def test_path_extrude_factory_profile() -> None:
    assert isinstance(PATH3.path_extrude(lambda: s2.circle(radius=3)), Bosl2Solid)


# -- free functions -----------------------------------------------------------------------


def test_extrude_from_to() -> None:
    assert isinstance(m.extrude_from_to(s2.circle(radius=4), [0, 0, 0], [10, 20, 30]), Bosl2Solid)
    assert isinstance(
        m.extrude_from_to(s2.circle(radius=4), [0, 0, 0], [0, 0, 20], twist=90, scale=2),
        Bosl2Solid,
    )


def test_extrude_from_to_same_point_raises() -> None:
    with pytest.raises(AssertionError):
        m.extrude_from_to(s2.circle(radius=4), [1, 2, 3], [1, 2, 3])


def test_cylindrical_extrude() -> None:
    assert isinstance(
        m.cylindrical_extrude(s2.square([20, 8]), inner_radius=25, outer_radius=30),
        Bosl2Solid,
    )
    assert isinstance(
        m.cylindrical_extrude(s2.square([20, 8]), inner_diameter=50, outer_diameter=60, spin=45),
        Bosl2Solid,
    )


def test_cylindrical_extrude_needs_radii() -> None:
    with pytest.raises(AssertionError):
        m.cylindrical_extrude(s2.square([20, 8]), inner_radius=25)


def test_chain_hull() -> None:
    assert isinstance(m.chain_hull(cuboid([5, 5, 5]), sphere(radius=4).right(20)), Bosl2Solid)
    assert isinstance(
        m.chain_hull([cuboid([5, 5, 5]), sphere(radius=4), cuboid([3, 3, 3])]),
        Bosl2Solid,
    )
    # single object passes through
    assert isinstance(m.chain_hull(cuboid([5, 5, 5])), Bosl2Solid)


def test_minkowski_difference() -> None:
    assert isinstance(m.minkowski_difference(cuboid([40, 40, 40]), sphere(radius=8)), Bosl2Solid)


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
    assert isinstance(cuboid([20, 30, 5]).minkowski(sphere(radius=2, fn=12)), Bosl2Solid)


def test_minkowski_sum_keeps_2d_shapes_2d() -> None:
    """_wrap round-trips the result, so a 2-D operand does not come back as a solid."""
    from pybosl2.shapes2d import Bosl2Shape2D

    grown = s2.square([10, 10], center=True).minkowski(s2.circle(radius=3, fn=24))
    assert isinstance(grown, Bosl2Shape2D)


def test_minkowski_sum_grows_the_solid_by_the_swept_shape() -> None:
    """Sweeping a radius-r ball grows every side by ~2r -- the point of the operation."""
    grown = cuboid([20, 30, 5]).minkowski(sphere(radius=2, fn=48))
    _, size = grown.bounds()
    for got, base in zip(size, (20, 30, 5), strict=True):
        assert got == pytest.approx(base + 4, abs=0.1)


def test_minkowski_sum_accepts_several_shapes() -> None:
    """Variadic, like OpenSCAD's minkowski(): each is swept in turn, so the growth accumulates."""
    once = cuboid([10, 10, 10]).minkowski(cuboid([2, 2, 2]))
    twice = cuboid([10, 10, 10]).minkowski(cuboid([2, 2, 2]), cuboid([1, 1, 1]))
    assert once.bounds()[1][0] == pytest.approx(12, abs=0.01)
    assert twice.bounds()[1][0] == pytest.approx(13, abs=0.01)


def test_minkowski_sum_needs_a_shape() -> None:
    with pytest.raises(AssertionError):
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
    assert isinstance(BOX.bounding_box(), Bosl2Solid)
    assert isinstance(BOX.bounding_box(excess=3), Bosl2Solid)


def test_offset3d_zero_is_noop() -> None:
    assert BOX.offset3d(0) is BOX


def test_offset3d_and_round3d() -> None:
    assert isinstance(BOX.offset3d(2), Bosl2Solid)
    assert isinstance(BOX.offset3d(-2), Bosl2Solid)
    assert isinstance(BOX.round3d(3), Bosl2Solid)
    assert isinstance(BOX.round3d(outer_radius=2, inner_radius=1), Bosl2Solid)


def test_chain_hull_and_minkowski_diff_methods() -> None:
    assert isinstance(BOX.chain_hull(sphere(radius=5).right(30)), Bosl2Solid)
    assert isinstance(BOX.minkowski_difference(sphere(radius=4)), Bosl2Solid)


# ── multi-diff minkowski ────────────────────────────────────────────────


def test_minkowski_difference_multiple_diffs() -> None:
    result = m.minkowski_difference(cuboid([20, 20, 20]), sphere(radius=3), sphere(radius=4))
    assert isinstance(result, Bosl2Solid)


def test_cylindrical_extrude_default_size() -> None:
    from pybosl2.miscellaneous import cylindrical_extrude

    circle = s2.circle(10)
    result = cylindrical_extrude(circle, outer_radius=50, inner_radius=40)
    assert isinstance(result, Bosl2Solid)

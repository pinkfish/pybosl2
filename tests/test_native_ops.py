# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for the native-only Bosl2Solid mesh operations (repair/wrap/roof/pull/oversample/
separate/inside) that wrap PythonSCAD builtins with no BOSL2 equivalent. Native geometry is mocked,
so these check that each method re-wraps into a Bosl2Solid (preserving the fluent API) and that
separate()/inside() return the right Python types; the real geometry is verified in
test_stl_render.py."""

import pytest

import bosl2.shapes3d as s3
from bosl2.shapes3d import Bosl2Solid

# roof() maps onto a native op that the full PythonSCAD app provides but the pip
# `pythonscad` wheel does not; skip its test when the underlying op is missing.
_HAS_ROOF = hasattr(Bosl2Solid._unwrap(s3.cuboid([10, 10, 10])), "roof")


def _cube():
    return s3.cuboid([20, 20, 10])


def test_repair_returns_solid():
    assert isinstance(_cube().repair(), Bosl2Solid)


def test_wrap_returns_solid_with_and_without_fn():
    assert isinstance(_cube().wrap(20), Bosl2Solid)
    assert isinstance(_cube().wrap(20, fn=32), Bosl2Solid)


@pytest.mark.skipif(not _HAS_ROOF, reason="native roof() not provided by the pythonscad pip wheel")
def test_roof_is_2d_to_3d_constructor():
    # roof() is a 2-D -> 3-D constructor (a hip roof over a 2-D outline), not a solid method.
    import bosl2.shapes2d as s2

    assert isinstance(s3.roof(s2.square([20, 20], center=True)), Bosl2Solid)
    # accepts a Bosl2Solid-wrapped 2-D shape too
    assert isinstance(s3.roof(Bosl2Solid(s2.square([20, 20], center=True))), Bosl2Solid)


def test_pull_returns_solid():
    assert isinstance(_cube().pull([0, 0, 1], 5), Bosl2Solid)


def test_oversample_returns_solid():
    assert isinstance(_cube().oversample(2), Bosl2Solid)


def test_separate_returns_list_of_solids():
    parts = _cube().separate()
    assert isinstance(parts, list)
    assert parts and all(isinstance(p, Bosl2Solid) for p in parts)


def test_inside_returns_bool():
    c = _cube()  # centered cuboid: origin is inside, a far point is not
    r_in = c.inside([0, 0, 0])
    r_out = c.inside([100, 0, 0])
    assert isinstance(r_in, bool) and isinstance(r_out, bool)
    assert r_in is True and r_out is False


def test_methods_are_chainable():
    # each returns a Bosl2Solid, so they compose fluently with the rest of the API
    out = _cube().oversample(2).repair().up(5)
    assert isinstance(out, Bosl2Solid)


def test_pull_coerces_numpy_inputs():
    # numpy vectors must be coerced to plain floats at the native boundary (see CLAUDE.md)
    import numpy as np

    assert isinstance(_cube().pull(np.array([0.0, 0.0, 1.0]), np.float64(5)), Bosl2Solid)
    assert _cube().inside(np.array([0.0, 0.0, 0.0])) is True

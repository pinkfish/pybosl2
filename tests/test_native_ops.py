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

import pybosl2.shapes3d as s3
from pybosl2.shapes3d import Bosl2Solid


def _cube() -> Bosl2Solid:
    return s3.cuboid([20, 20, 10])


def test_repair_returns_solid() -> None:
    """repair() rebuilds the mesh without moving it."""
    repaired = _cube().repair()
    assert isinstance(repaired, Bosl2Solid)
    assert [float(v) for v in repaired.bounds().size] == pytest.approx([20.0, 20.0, 10.0])


def test_wrap_returns_solid_with_and_without_fn() -> None:
    """wrap() is the one op here that cannot be measured: the bounding box never comes back.

    The call itself returns immediately -- the native op is lazy -- but asking the wrapped solid
    for its bounds (or even its program text) re-enters the native ``wrap`` and does not return.
    So this asserts the type, and the geometry is covered against the real app in
    test_stl_render.py (PLAN X-8's stated exception).
    """
    assert isinstance(_cube().wrap(20), Bosl2Solid)
    assert isinstance(_cube().wrap(20, fn=32), Bosl2Solid)


# roof() has no test here: the op exists only in the full PythonSCAD app, never in the pip wheel
# this suite runs against, so a test here could only ever skip. It is covered for real against the
# app binary by test_stl_render.py's test_roof_makes_a_pyramid (which measures the pyramid volume)
# and test_stl_render_2d.py's test_roof_produces_3d_solid.


def test_pull_returns_solid() -> None:
    """pull() stretches the mesh, so the solid grows by the distance it was pulled."""
    pulled = _cube().pull([0, 0, 1], 5)
    assert isinstance(pulled, Bosl2Solid)
    assert [float(v) for v in pulled.bounds().size] == pytest.approx([25.0, 25.0, 15.0])


def test_oversample_returns_solid() -> None:
    """oversample() subdivides the faces: same solid, finer mesh."""
    dense = _cube().oversample(2)
    assert isinstance(dense, Bosl2Solid)
    assert [float(v) for v in dense.bounds().size] == pytest.approx([20.0, 20.0, 10.0])


def test_separate_returns_list_of_solids() -> None:
    parts = _cube().separate()
    assert isinstance(parts, list)
    assert parts
    assert all(isinstance(p, Bosl2Solid) for p in parts)


def test_inside_returns_bool() -> None:
    c = _cube()  # centered cuboid: origin is inside, a far point is not
    r_in = c.inside([0, 0, 0])
    r_out = c.inside([100, 0, 0])
    assert isinstance(r_in, bool)
    assert isinstance(r_out, bool)
    assert r_in is True
    assert r_out is False


def test_methods_are_chainable() -> None:
    # each returns a Bosl2Solid, so they compose fluently with the rest of the API
    out = _cube().oversample(2).repair().up(5)
    assert isinstance(out, Bosl2Solid)
    _box = out.bounds()
    centre, size = list(_box.center), list(_box.size)
    assert [float(v) for v in size] == pytest.approx([20.0, 20.0, 10.0])  # neither op moved it
    assert float(centre[2]) == pytest.approx(5.0)  # ...and the up() at the end did


def test_pull_coerces_numpy_inputs() -> None:
    # numpy vectors must be coerced to plain floats at the native boundary (see CLAUDE.md)
    import numpy as np

    assert isinstance(_cube().pull(np.array([0.0, 0.0, 1.0]), np.float64(5)), Bosl2Solid)
    assert _cube().inside(np.array([0.0, 0.0, 0.0])) is True

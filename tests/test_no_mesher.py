# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Nothing routine may depend on a mesher being available (SPEC A-2, PLAN T-6e).

The SDF backend needs libfive to turn a field into triangles, and plenty of machines -- CI above
all -- do not have it. That is fine as long as the things a caller does *without* asking for a mesh
keep working: measuring, transforming, combining, and above all `isinstance(shape, Solid)`.

This suite exists because that stopped being true and the whole test run still passed locally.
`Solid.vnf` was declared on the contract as a property, and on Python 3.11 `isinstance()` against a
runtime-checkable Protocol calls `hasattr()` on every member -- which *evaluates* a property. So
every type check silently meshed the field, and where no mesher existed the error escaped the
`isinstance` call itself.

Two things had to line up for that to reach CI unseen, and both are worth knowing:

* **The mesher.** The pip wheel a developer has can mesh; the runner's cannot. Nothing in the suite
  simulated the runner, so 4130 local tests passed.
* **The Python version.** 3.11 resolves a protocol `isinstance` with `hasattr`, which evaluates
  properties; 3.12 changed it to a static lookup, which does not. The project supports 3.11+
  (`requires-python`), and CI's matrix covers 3.11-3.13 -- so the failure appeared on the oldest
  supported version only, and never on a newer interpreter.

The guards below therefore probe with `hasattr` **directly** as well as through `isinstance`: the
direct probe is what makes this suite catch the defect on every interpreter rather than only on the
one where `isinstance` happens to route through it.
"""

from __future__ import annotations

from typing import Any, NoReturn

import pytest

import pybosl2.sdf  # noqa: F401  -- registers the "sdf" backend
import pybosl2.sdf.shapes3d as sdf_shapes
from pybosl2 import Anchor, cuboid, sphere, use_backend
from pybosl2._backend import Shape, Solid
from pybosl2.exceptions import Bosl2Error


@pytest.fixture
def no_mesher(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make meshing an SDF field fail, the way a machine without libfive does."""

    def unavailable(_self: Any) -> NoReturn:
        raise RuntimeError("no mesher on this machine (simulated: libfive is absent)")

    monkeypatch.setattr(sdf_shapes.SdfSolid, "mesh", unavailable)


def _sdf_solid() -> Any:
    with use_backend("sdf"):
        return cuboid([10, 10, 10])


# --- the check that broke -----------------------------------------------------------------


def test_isinstance_answers_without_meshing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A type check must not do work, and must not fail when that work would (PLAN T-6e).

    Counts the calls rather than only catching the failure: on an interpreter whose protocol
    `isinstance` resolves statically the broken form would not raise, but it would still be
    meshing -- so the assertion that matters is *zero* meshes, not "no exception".
    """
    calls: list[str] = []

    def counted(_self: Any) -> NoReturn:
        calls.append("mesh")
        raise RuntimeError("no mesher on this machine (simulated: libfive is absent)")

    monkeypatch.setattr(sdf_shapes.SdfSolid, "mesh", counted)
    shape = _sdf_solid()

    assert isinstance(shape, Solid)
    assert isinstance(shape, Shape)
    assert calls == [], f"isinstance meshed the field {len(calls)} time(s) -- it must do no work"


@pytest.mark.usefixtures("no_mesher")
def test_capability_probes_answer_without_meshing() -> None:
    """`hasattr`/`getattr` are what `isinstance` is built on, and what users write (SPEC E-6)."""
    shape = _sdf_solid()
    assert hasattr(shape, "vnf")
    assert hasattr(shape, "bounds")
    assert hasattr(shape, "no_such_operation") is False
    assert getattr(shape, "no_such_operation", "fallback") == "fallback"


# --- everything that does not need a mesh keeps working -------------------------------------


@pytest.mark.usefixtures("no_mesher")
def test_measuring_needs_no_mesher() -> None:
    """An SDF shape knows its own bounds exactly -- that is the backend's selling point."""
    assert _sdf_solid().bounds().size == pytest.approx((10.0, 10.0, 10.0))


@pytest.mark.usefixtures("no_mesher")
def test_building_and_combining_need_no_mesher() -> None:
    """Fields compose by arithmetic; nothing here has any reason to reach for triangles."""
    with use_backend("sdf"):
        combined = cuboid([10, 10, 10]) - sphere(radius=4)
        moved = combined.up(5).left(2)
    assert moved.backend == "sdf"
    assert moved.bounds().min_z == pytest.approx(0.0)


@pytest.mark.usefixtures("no_mesher")
def test_a_refusal_still_refuses_by_name() -> None:
    """The CSG-only refusals are pure message-building and must not touch the mesher."""
    shape = _sdf_solid()
    with pytest.raises(Bosl2Error, match="attachment, tagging and the edge treatments"):
        shape.attach(Anchor.TOP, None)


# --- and what genuinely needs one says so ----------------------------------------------------


@pytest.mark.usefixtures("no_mesher")
def test_asking_for_the_mesh_surfaces_the_real_error() -> None:
    """The fix must not have been to swallow the failure -- only to stop provoking it."""
    shape = _sdf_solid()
    with pytest.raises(RuntimeError, match="no mesher"):
        shape.vnf()


@pytest.mark.usefixtures("no_mesher")
def test_exporting_surfaces_the_real_error() -> None:
    """Export meshes first (SPEC S-53), so it is one of the calls that legitimately needs one."""
    shape = _sdf_solid()
    with pytest.raises(RuntimeError, match="no mesher"):
        shape.export("nowhere.stl")


# --- the CSG side is unaffected, which is what makes the fixture a fair simulation ------------


@pytest.mark.usefixtures("no_mesher")
def test_the_csg_backend_is_untouched() -> None:
    """Only the SDF mesher is stubbed; a CSG solid tessellates through its own runtime."""
    solid = cuboid([10, 10, 10])
    assert isinstance(solid, Solid)
    assert solid.vnf().volume() == pytest.approx(1000.0)

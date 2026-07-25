# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Milestone 2 of the CSG/SDF merge: the libfive/SDF backend is live behind the common wrapper.

Building an SDF shape is FFI-free (only ``.sdf()``/``.mesh()`` touch libfive), so the build/bounds/
tag tests run anywhere; the mesh-pipeline test uses the numeric mock (as pysolidfive's own tests do)."""

import importlib.util

import pytest

from bosl2._backend import Solid, current_backend, get_backend, use_backend


def test_sdf_backend_registers_and_builds_primitives():
    b = get_backend("sdf")
    assert b.name == "sdf"
    for shape in (b.sphere(radius=10), b.cube(10), b.cylinder(height=20, radius=5)):
        assert shape.backend == "sdf"
        assert isinstance(shape, Solid)


def test_sdf_sphere_bounds_match_the_requested_size():
    with use_backend("sdf"):
        _center, size = get_backend().sphere(radius=10).bounds()
    assert [round(s) for s in size] == [20, 20, 20]  # exact, cheap -- no meshing needed


def test_default_is_csg_and_context_selects_sdf():
    assert current_backend() == "csg"
    csg = get_backend().sphere(radius=10)
    with use_backend("sdf"):
        sdf = get_backend().sphere(radius=10)
    assert csg.backend == "csg" and sdf.backend == "sdf"
    assert type(csg).__name__ == "Bosl2Solid" and type(sdf).__name__ == "PyShape"
    assert isinstance(csg, Solid) and isinstance(sdf, Solid)  # one common contract


@pytest.mark.skipif(
    importlib.util.find_spec("libfive") is None,
    reason="SDF meshing needs the real libfive C extension (like CSG render tests need the app)",
)
def test_sdf_mesh_pipeline_runs():
    # Build -> symbolic SDF field -> frep() mesh, end to end (mock frep returns a marker result).
    with use_backend("sdf"):
        s = get_backend().sphere(radius=10)
        assert s.sdf() is not None  # libfive field
        assert s.mesh() is not None  # frep() realized it

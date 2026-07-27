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

from pybosl2._backend import Solid, current_backend, get_backend, use_backend


def test_sdf_backend_registers_and_builds_primitives():
    b = get_backend("sdf")
    assert b.name == "sdf"
    built = (b.construct("sphere", radius=10), b.construct("cube", 10), b.construct("cylinder", height=20, radius=5))
    for shape in built:
        assert shape.backend == "sdf"
        assert isinstance(shape, Solid)


def test_sdf_sphere_bounds_match_the_requested_size():
    with use_backend("sdf"):
        _center, size = get_backend().construct("sphere", radius=10).bounds()
    assert [round(s) for s in size] == [20, 20, 20]  # exact, cheap -- no meshing needed


def test_default_is_csg_and_context_selects_sdf():
    assert current_backend() == "csg"
    csg = get_backend().construct("sphere", radius=10)
    with use_backend("sdf"):
        sdf = get_backend().construct("sphere", radius=10)
    assert csg.backend == "csg" and sdf.backend == "sdf"
    assert type(csg).__name__ == "Bosl2Solid" and type(sdf).__name__ == "PyShape"
    assert isinstance(csg, Solid) and isinstance(sdf, Solid)  # one common contract


def _libfive_available() -> bool:
    try:
        return importlib.util.find_spec("libfive") is not None
    except (ImportError, ValueError):
        return False


@pytest.mark.skipif(
    not _libfive_available(),
    reason="SDF meshing needs the real libfive C extension (like CSG render tests need the app)",
)
def test_sdf_mesh_pipeline_runs():
    # Build -> symbolic SDF field -> frep() mesh, end to end (mock frep returns a marker result).
    with use_backend("sdf"):
        s = get_backend().construct("sphere", radius=10)
        assert s.sdf() is not None  # libfive field
        assert s.mesh() is not None  # frep() realized it


def test_sdf_backend_does_not_import_the_csg_god_module():
    # Importing the SDF backend must not drag in the large pybosl2.shapes3d CSG module: the shared
    # edge-selector language lives in pybosl2._edges_lang. Checked in a fresh interpreter since the
    # test session has already imported everything.
    import subprocess
    import sys

    code = "import pybosl2._sdf, sys; print('pybosl2.shapes3d' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False", f"pybosl2._sdf pulled in pybosl2.shapes3d:\n{out.stdout}{out.stderr}"

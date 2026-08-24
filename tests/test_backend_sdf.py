# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Milestone 2 of the CSG/SDF merge: the libfive/SDF backend is live behind the common wrapper.

Building an SDF shape is FFI-free (only ``.sdf()``/``.mesh()`` touch libfive), so the build/bounds/
tag tests run anywhere; the mesh-pipeline test uses the numeric mock (as pysolidfive's own tests do)."""

import pytest

from pybosl2._backend import Solid, current_backend, get_backend, use_backend


def test_sdf_backend_registers_and_builds_primitives() -> None:
    b = get_backend("sdf")
    assert b.name == "sdf"
    built = (
        b.construct("sphere", {"radius": 10}),
        b.construct("cube", {"size": 10}),
        b.construct("cylinder", {"height": 20, "radius": 5}),
    )
    for shape in built:
        assert shape.backend == "sdf"
        assert isinstance(shape, Solid)


def test_sdf_sphere_bounds_match_the_requested_size() -> None:
    with use_backend("sdf"):
        _box = get_backend().construct("sphere", {"radius": 10}).bounds()
        _center, size = list(_box.center), list(_box.size)
    assert [round(s) for s in size] == [20, 20, 20]  # exact, cheap -- no meshing needed


def test_default_is_csg_and_context_selects_sdf() -> None:
    assert current_backend() == "csg"
    csg = get_backend().construct("sphere", {"radius": 10})
    with use_backend("sdf"):
        sdf = get_backend().construct("sphere", {"radius": 10})
    assert csg.backend == "csg"
    assert sdf.backend == "sdf"
    assert type(csg).__name__ == "CsgSolid"
    assert type(sdf).__name__ == "SdfSolid"
    assert isinstance(csg, Solid)
    assert isinstance(sdf, Solid)  # one common contract


def test_sdf_mesh_pipeline_runs() -> None:
    """Build -> symbolic SDF field -> frep() mesh, end to end, measured at each stage.

    This runs under the numeric mock as well as real libfive, so the check is the field itself:
    a radius-10 sphere reads -10 at its centre, 0 on its surface and +10 ten past it, and the
    meshing box is the sphere's own bounds plus a small margin.
    """
    with use_backend("sdf"):
        s = get_backend().construct("sphere", {"radius": 10})
        assert s.sdf() is not None  # type: ignore[attr-defined]  # libfive field
        assert s.mn == pytest.approx([-10.0] * 3)  # type: ignore[attr-defined]
        assert s.mx == pytest.approx([10.0] * 3)  # type: ignore[attr-defined]

        mesh = s.mesh()  # type: ignore[attr-defined]  # frep() realized it
        assert mesh is s.mesh(), "the mesh is cached, not rebuilt on every call"  # type: ignore[attr-defined]
        assert mesh.sample(0, 0, 0) == pytest.approx(-10.0)  # inside, one radius from the surface
        assert mesh.sample(10, 0, 0) == pytest.approx(0.0)  # on the surface
        assert mesh.sample(0, 10, 0) == pytest.approx(0.0)  # ... in every direction
        assert mesh.sample(20, 0, 0) == pytest.approx(10.0)  # outside, and signed positive


def test_sdf_backend_does_not_import_the_csg_god_module() -> None:
    # Importing the SDF backend must not drag in the large pybosl2.shapes3d CSG module: the shared
    # edge-selector language lives in pybosl2._edges_lang. Checked in a fresh interpreter since the
    # test session has already imported everything.
    import subprocess
    import sys

    code = "import pybosl2.sdf, sys; print('pybosl2.shapes3d' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False", f"pybosl2.sdf pulled in pybosl2.shapes3d:\n{out.stdout}{out.stderr}"

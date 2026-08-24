# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The way out of the library (SPEC S-53, S-54, S-55).

§6.13 is titled "import, export and interchange" and specified only import: a user who built a
part could display it but not save it, and the only STL writing in the repo lived inside the test
harness driving the app in a subprocess. These tests pin the writers, and check them against the
same STL reader the render tests use rather than against themselves.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
import pytest

from pybosl2 import VNF, Path2D, cuboid, cyl
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.export import FORMATS, check_exportable, format_for, open_edges
from tests.render_stl import parse_stl, stl_metrics

if TYPE_CHECKING:
    from pathlib import Path

BOX = Path2D([[-5, -5], [5, -5], [5, 5], [-5, 5]], closed=True)


def _box_solid() -> object:
    return BOX.linear_sweep(height=10)


# --- the writers ---------------------------------------------------------------------------


@pytest.mark.parametrize("suffix", sorted(FORMATS))
def test_every_format_writes_a_non_empty_file(suffix: str, tmp_path: Path) -> None:
    out = _box_solid().export(tmp_path / f"box{suffix}")  # type: ignore[attr-defined]
    assert out.exists()
    assert out.stat().st_size > 100, f"{suffix} wrote {out.stat().st_size} bytes"


def test_the_stl_reads_back_as_the_solid_that_was_written(tmp_path: Path) -> None:
    """Checked with the render harness's own reader, not with our writer's assumptions."""
    out = _box_solid().export(tmp_path / "box.stl")  # type: ignore[attr-defined]
    metrics = stl_metrics(out)
    assert metrics.ntris == 12  # a box is 6 quads fanned into 12 triangles
    assert metrics.volume == pytest.approx(1000.0)
    assert list(metrics.size) == pytest.approx([10.0, 10.0, 10.0])


def test_ascii_and_binary_stl_describe_the_same_mesh(tmp_path: Path) -> None:
    binary = _box_solid().export(tmp_path / "b.stl")  # type: ignore[attr-defined]
    ascii_form = _box_solid().export(tmp_path / "a.stl", file_format="stla")  # type: ignore[attr-defined]
    assert ascii_form.read_text().startswith("solid ")
    np.testing.assert_allclose(
        np.sort(parse_stl(binary).reshape(-1, 3), axis=0),
        np.sort(parse_stl(ascii_form).reshape(-1, 3), axis=0),
        atol=1e-5,
    )


def test_obj_off_and_ply_carry_every_vertex(tmp_path: Path) -> None:
    """The text formats keep the polygons rather than triangulating, so counts match the VNF."""
    mesh = _box_solid().vnf()  # type: ignore[attr-defined]
    for suffix, vertex_token in ((".obj", "v "), (".off", None), (".ply", None)):
        out = mesh.export(tmp_path / f"box{suffix}")
        text = out.read_text()
        if vertex_token:
            assert text.count(f"\n{vertex_token}") + text.startswith(vertex_token) == len(mesh.vertices)
        assert f"{len(mesh.vertices)}" in text


def test_a_solid_and_its_mesh_export_identically(tmp_path: Path) -> None:
    solid = _box_solid()
    from_solid = solid.export(tmp_path / "a.stl")  # type: ignore[attr-defined]
    from_mesh = solid.vnf().export(tmp_path / "b.stl")  # type: ignore[attr-defined]
    assert from_solid.read_bytes() == from_mesh.read_bytes()


def test_a_solid_built_any_other_way_exports_too(tmp_path: Path) -> None:
    """Not just sweeps: an ordinary CSG solid meshes on demand (VNF.from_solid)."""
    part = cuboid([40, 30, 10], rounding=3, fn=64) - cyl(radius=4, height=20)
    metrics = stl_metrics(part.export(tmp_path / "bracket.stl"))
    assert metrics.volume == pytest.approx(part.vnf().volume(), rel=1e-6)
    # against the solid's own bounds, not the nominal size: a facetted roundover sits marginally
    # inside the box it was cut from, and that is the solid's business, not the exporter's
    assert list(metrics.size) == pytest.approx(list(part.bounds().size), abs=1e-4)


# --- S-54: pure, so it needs no CAD runtime -------------------------------------------------


def test_writing_a_mesh_touches_no_native_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A mesh built with numpy alone must be savable with numpy alone (SPEC S-54, A-2)."""
    mesh = VNF(
        [[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0], [0, 0, 5], [10, 0, 5], [10, 10, 5], [0, 10, 5]],
        [[3, 2, 1, 0], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]],
    )
    import builtins

    real_import = builtins.__import__

    def no_native(name: str, *args: object, **kwargs: object) -> object:
        if name.split(".")[0] in {"pythonscad", "openscad", "libfive"}:
            raise AssertionError(f"export reached the native runtime: {name}")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", no_native)
    out = mesh.export(tmp_path / "pure.stl")
    assert stl_metrics(out).volume == pytest.approx(500.0)


# --- S-55: refuse to write nonsense ----------------------------------------------------------


def test_an_open_surface_is_refused_and_the_escape_hatch_works(tmp_path: Path) -> None:
    open_box = VNF([[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0]], [[0, 1, 2, 3]])
    with pytest.raises(Bosl2ValueError, match="not watertight"):
        open_box.export(tmp_path / "open.stl")
    assert open_box.export(tmp_path / "open.stl", check=False).exists()


def test_an_inside_out_mesh_is_refused(tmp_path: Path) -> None:
    """An inverted mesh exports cleanly and then adds material wherever it cuts (SPEC S-55)."""
    inverted = _box_solid().vnf().reverse()  # type: ignore[attr-defined]
    assert inverted.volume() < 0
    with pytest.raises(Bosl2ValueError, match="inside out"):
        inverted.export(tmp_path / "bad.stl")


def test_an_empty_mesh_is_refused(tmp_path: Path) -> None:
    with pytest.raises(Bosl2ValueError, match="empty"):
        VNF([], []).export(tmp_path / "nothing.stl")


def test_a_closed_solid_has_no_open_edges() -> None:
    assert open_edges(_box_solid().vnf()) == []  # type: ignore[attr-defined]
    assert check_exportable(_box_solid().vnf()) is None  # type: ignore[attr-defined]


# --- format selection -------------------------------------------------------------------------


def test_the_suffix_picks_the_format() -> None:
    assert format_for("part.stl") == "stl"
    assert format_for("part.OBJ") == "obj"
    assert format_for("part.stl", explicit="stla") == "stla"


def test_a_kernel_format_is_refused_by_name() -> None:
    """Half-writing a 3MF would be worse than saying we do not write one (SPEC S-54)."""
    with pytest.raises(Bosl2ValueError, match="3MF is a CAD kernel's own format"):
        format_for("part.3mf")


def test_an_unknown_suffix_names_what_is_accepted() -> None:
    with pytest.raises(Bosl2ValueError, match=r"\.obj"):
        format_for("part.wibble")


def test_a_curved_solid_survives_the_round_trip(tmp_path: Path) -> None:
    """A facetted surface: vertex count and volume both have to come back."""
    swept = Path2D(
        [[3 * math.cos(a), 3 * math.sin(a)] for a in np.linspace(0, 2 * math.pi, 24, endpoint=False)],
        closed=True,
    ).linear_sweep(height=12)
    metrics = stl_metrics(swept.export(tmp_path / "rod.stl"))
    assert metrics.volume == pytest.approx(swept.vnf().volume(), rel=1e-5)
    assert metrics.ntris == 2 * 24 + 2 * 22  # 24 side quads fanned, plus two 24-gon caps

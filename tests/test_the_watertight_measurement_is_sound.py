# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A closed mesh must not read open because the tessellator left a sliver in it.

`stl_metrics()` is what the documentation's spec pages measure a rendered part with, and what
`tests/test_stl_render.py` asserts watertightness from. It re-identifies shared vertices by
position, because an STL is a triangle soup with no indices in it, and then requires every
undirected edge to have exactly two incident triangles.

**A degenerate triangle breaks that count.** Two of its three vertices are the same point, so its
three edges are really one edge listed twice -- and that one edge is a side the mesh's two real
faces already share. The count goes from 2 to 4 and the solid is reported open.

The app's tessellator emits them. Measured over the 93 meshes the spec pages cache:

| part | triangles | degenerate | edges miscounted | watertight, before -> after |
|---|---|---|---|---|
| `cone(radius1=10, radius2=3, chamfer=1)` | 360 | 120 | 63 | False -> **True** |
| `cylinder(radius=10, chamfer=2)` | 360 | 120 | 63 | False -> **True** |
| `ball_bearing("r8")` | 2978 | 12 | 8 | False -> **True** |
| `pco1810_neck()` | 4038 | 8 | 8 | False -> **True** |

**A chamfered cylinder had been published as not watertight for as long as this function
existed**, and so had a chamfered cone -- a third of each one's triangles are slivers, from the
fan the chamfered rim is tessellated as. The plain cylinder beside them on the same page has none,
so it is the chamfer that produces them. That is the kind of claim a reader takes at face value.

### This was half of a disagreement, and only half of it was a defect

`pco1810_neck` reported `wt: false` here while `part.vnf().is_watertight()` said `True` for the
same part, and two checks implementing the same rule disagreeing looked like one of them being
wrong. Both are right about what they are given. `VNF.is_watertight()` reads `faces`, which are
vertex **indices**, so it measures the mesh *this library built*; `stl_metrics` measures what the
renderer tessellated that mesh into. **Two meshes, not two rules** -- and the slivers exist only
in the second, which is why no amount of reading the VNF code explained it (T134).
"""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

import pytest
from render_stl import stl_metrics

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Sequence

#: A unit tetrahedron: four vertices, four faces, every edge shared by exactly two of them. The
#: smallest closed manifold there is, so anything that reads it as open is wrong about the mesh.
TETRAHEDRON: "tuple[tuple[tuple[float, float, float], ...], ...]" = (
    ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    ((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
    ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
)


def _write_binary_stl(path: "pathlib.Path", triangles: "Sequence[Sequence[Sequence[float]]]") -> None:
    """Write *triangles* as a binary STL, normals left at zero (nothing here reads them)."""
    with path.open("wb") as handle:
        handle.write(b"\0" * 80)
        handle.write(struct.pack("<I", len(triangles)))
        for triangle in triangles:
            handle.write(struct.pack("<3f", 0.0, 0.0, 0.0))
            for vertex in triangle:
                handle.write(struct.pack("<3f", *(float(v) for v in vertex)))
            handle.write(struct.pack("<H", 0))


def test_a_closed_mesh_reads_watertight(tmp_path: "pathlib.Path") -> None:
    """The premise. Without this the test below could pass by the measurement reading nothing."""
    path = tmp_path / "tetra.stl"
    _write_binary_stl(path, TETRAHEDRON)
    metrics = stl_metrics(path)
    assert metrics.ntris == 4
    assert metrics.watertight, "a tetrahedron is the smallest closed manifold and must read as one"


def test_a_degenerate_triangle_does_not_make_a_closed_mesh_read_open(tmp_path: "pathlib.Path") -> None:
    """The defect: one sliver laid on an existing edge took that edge's count from 2 to 4."""
    collapsed = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    path = tmp_path / "tetra-plus-sliver.stl"
    _write_binary_stl(path, (*TETRAHEDRON, collapsed))

    metrics = stl_metrics(path)
    assert metrics.ntris == 5, "the sliver is still counted as a triangle; only its edges are skipped"
    assert metrics.watertight, (
        "a triangle with two coincident vertices covers no area and bounds nothing, so it cannot "
        "open a closed mesh -- but its collapsed side appears twice in its own three edges, which "
        "took the tetrahedron's (0,0,0)-(1,0,0) edge from 2 incident faces to 4"
    )


def test_an_open_mesh_still_reads_open(tmp_path: "pathlib.Path") -> None:
    """The control. Skipping slivers must not turn the check into one that passes everything."""
    path = tmp_path / "open.stl"
    _write_binary_stl(path, TETRAHEDRON[:3])
    assert not stl_metrics(path).watertight, (
        "a tetrahedron with a face missing has three edges with one incident triangle each, and "
        "that is the hole this measurement exists to find"
    )


def test_a_mesh_of_nothing_but_slivers_is_not_watertight(tmp_path: "pathlib.Path") -> None:
    """And skipping every triangle must not read as a closed mesh, which `bool(edges)` decides."""
    path = tmp_path / "slivers.stl"
    _write_binary_stl(
        path,
        (
            ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
            ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 1.0, 0.0)),
        ),
    )
    assert not stl_metrics(path).watertight, "a mesh with no surface in it bounds nothing"


@pytest.mark.parametrize(
    ("name", "degenerate"),
    [("cone", 120), ("chamfered-cylinder", 120)],
)
def test_the_cached_cone_meshes_really_do_carry_slivers(name: str, degenerate: int) -> None:
    """The figures in this module's table, read off the meshes the spec pages ship.

    Kept because the claim "a plain cone was published as not watertight" is about real files, and
    a table in a docstring is prose until something reads it back.
    """
    import pathlib

    import numpy as np
    from render_stl import parse_stl

    path = (
        pathlib.Path(__file__).resolve().parent.parent / "docs" / "_extra" / "specs" / "_stl" / f"shapes3d-{name}.stl"
    )
    if not path.is_file():  # pragma: no cover - the cache is checked in, but it is a cache
        pytest.skip(f"{path.name} is not in the spec STL cache")
    triangles = parse_stl(path)
    rounded = np.round(triangles, 4)
    slivers = sum(1 for triangle in rounded if len({tuple(v) for v in triangle}) < 3)
    assert slivers == degenerate, f"shapes3d-{name}.stl has {slivers} degenerate triangles, not {degenerate}"
    assert stl_metrics(path).watertight, f"shapes3d-{name} is a closed solid and must measure as one"

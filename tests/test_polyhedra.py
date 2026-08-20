# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.polyhedra: the five Platonic solids."""

import math

import pytest

from pybosl2.parts.polyhedra import PlatonicSolid, PolyhedronInfo, RegularPolyhedron
from pybosl2.shapes3d import Bosl2Solid

_COUNTS: dict[PlatonicSolid, tuple[int, int]] = {
    PlatonicSolid.TETRAHEDRON: (4, 4),
    PlatonicSolid.CUBE: (8, 6),
    PlatonicSolid.OCTAHEDRON: (6, 8),
    PlatonicSolid.DODECAHEDRON: (20, 12),
    PlatonicSolid.ICOSAHEDRON: (12, 20),
}


def _size(s: Bosl2Solid) -> list[float]:
    _min, size = s._native_bounds()  # type: ignore[misc]
    return size


@pytest.mark.parametrize(("name", "vf"), _COUNTS.items())
def test_vertex_face_counts(name: PlatonicSolid, vf: tuple[int, int]) -> None:
    info = PolyhedronInfo(name)
    assert (info.num_vertices, info.num_faces) == vf


@pytest.mark.parametrize("name", list(_COUNTS))
def test_euler_characteristic(name: PlatonicSolid) -> None:
    info = PolyhedronInfo(name)
    edge_set: set[frozenset[int]] = set()
    for f in info.faces:
        for i in range(len(f)):
            edge_set.add(frozenset((f[i], f[(i + 1) % len(f)])))
    verts, edges, faces = info.num_vertices, len(edge_set), info.num_faces
    assert verts - edges + faces == 2  # type: ignore[operator]


@pytest.mark.parametrize("name", list(_COUNTS))
def test_builds(name: PlatonicSolid) -> None:
    assert isinstance(RegularPolyhedron(name).shape, Bosl2Solid)


def test_named_methods() -> None:
    assert isinstance(RegularPolyhedron.dodecahedron(side=10).shape, Bosl2Solid)


def test_cube_circumradius_gives_expected_side() -> None:
    assert _size(RegularPolyhedron.cube(radius=10).shape)[0] == pytest.approx(2 * 10 / math.sqrt(3), abs=0.1)


def test_octahedron_inradius() -> None:
    w = _size(RegularPolyhedron.octahedron(inner_radius=8).shape)[0]
    assert w == pytest.approx(2 * 8 * math.sqrt(3), abs=0.2)


def test_unknown_name_raises() -> None:
    with pytest.raises(KeyError):
        RegularPolyhedron("prism")

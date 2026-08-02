# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.polyhedra: the five Platonic solids."""

import math

import pytest

from pybosl2.parts.polyhedra import Polyhedra
from pybosl2.shapes3d import Bosl2Solid

_COUNTS = {
    "tetrahedron": (4, 4),
    "cube": (8, 6),
    "octahedron": (6, 8),
    "dodecahedron": (20, 12),
    "icosahedron": (12, 20),
}


def _size(s: Bosl2Solid) -> list[float]:
    _min, size = s._native_bounds()  # type: ignore[misc]
    return size


@pytest.mark.parametrize(("name", "vf"), _COUNTS.items())
def test_vertex_face_counts(name: str, vf: tuple[int, int]) -> None:
    info = Polyhedra.regular_polyhedron_info(name)
    assert (info["num_vertices"], info["num_faces"]) == vf


@pytest.mark.parametrize("name", list(_COUNTS))
def test_euler_characteristic(name: str) -> None:
    info = Polyhedra.regular_polyhedron_info(name)
    edge_set: set[frozenset[int]] = set()
    for f in info["faces"]:  # type: ignore[attr-defined]
        for i in range(len(f)):
            edge_set.add(frozenset((f[i], f[(i + 1) % len(f)])))
    verts, edges, faces = info["num_vertices"], len(edge_set), info["num_faces"]
    assert verts - edges + faces == 2  # type: ignore[operator]


@pytest.mark.parametrize("name", list(_COUNTS))
def test_builds(name: str) -> None:
    assert isinstance(Polyhedra.regular_polyhedron(name), Bosl2Solid)


def test_aliases_and_named_methods() -> None:
    assert isinstance(Polyhedra.regular_polyhedron("icosa"), Bosl2Solid)
    assert isinstance(Polyhedra.dodecahedron(side=10), Bosl2Solid)


def test_cube_circumradius_gives_expected_side() -> None:
    # cube circumradius r -> side = 2r/sqrt(3); the axis-aligned bbox equals the side
    assert _size(Polyhedra.cube(radius=10))[0] == pytest.approx(2 * 10 / math.sqrt(3), abs=0.1)


def test_octahedron_inradius() -> None:
    # octahedron vertices sit on the axes at +/- circumradius; inner_radius=8 -> R = 8*sqrt(3)
    w = _size(Polyhedra.octahedron(inner_radius=8))[0]
    assert w == pytest.approx(2 * 8 * math.sqrt(3), abs=0.2)


def test_unknown_name_raises() -> None:
    with pytest.raises(ValueError, match="unknown polyhedron"):
        Polyhedra.regular_polyhedron("prism")

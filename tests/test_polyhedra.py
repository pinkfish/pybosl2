# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2.polyhedra: the five Platonic solids."""

import math
import pytest

from bosl2.polyhedra import Polyhedra as P
from bosl2.shapes3d import Bosl2Solid

_COUNTS = {
    "tetrahedron": (4, 4),
    "cube": (8, 6),
    "octahedron": (6, 8),
    "dodecahedron": (20, 12),
    "icosahedron": (12, 20),
}


def _size(s):
    _min, size = s._native_bounds()
    return size


@pytest.mark.parametrize("name,vf", _COUNTS.items())
def test_vertex_face_counts(name, vf):
    info = P.regular_polyhedron_info(name)
    assert (info["num_vertices"], info["num_faces"]) == vf


@pytest.mark.parametrize("name", list(_COUNTS))
def test_euler_characteristic(name):
    info = P.regular_polyhedron_info(name)
    edges = set()
    for f in info["faces"]:
        for i in range(len(f)):
            edges.add(frozenset((f[i], f[(i + 1) % len(f)])))
    V, E, F = info["num_vertices"], len(edges), info["num_faces"]
    assert V - E + F == 2  # Euler's formula


@pytest.mark.parametrize("name", list(_COUNTS))
def test_builds(name):
    assert isinstance(P.regular_polyhedron(name), Bosl2Solid)


def test_aliases_and_named_methods():
    assert isinstance(P.regular_polyhedron("icosa"), Bosl2Solid)
    assert isinstance(P.dodecahedron(side=10), Bosl2Solid)


def test_cube_circumradius_gives_expected_side():
    # cube circumradius r -> side = 2r/sqrt(3); the axis-aligned bbox equals the side
    assert _size(P.cube(radius=10))[0] == pytest.approx(2 * 10 / math.sqrt(3), abs=0.1)


def test_octahedron_inradius():
    # octahedron vertices sit on the axes at +/- circumradius; inner_radius=8 -> R = 8*sqrt(3)
    w = _size(P.octahedron(inner_radius=8))[0]
    assert w == pytest.approx(2 * 8 * math.sqrt(3), abs=0.2)


def test_unknown_name_raises():
    with pytest.raises(ValueError):
        P.regular_polyhedron("prism")

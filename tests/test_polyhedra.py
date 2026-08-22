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


# Bounding box of each solid when it is circumscribed by the unit sphere. The tetrahedron and
# the cube share vertices (the tetrahedron uses four of the cube's eight), so they share a box.
_PHI = (1 + math.sqrt(5)) / 2
_UNIT_BOXES: dict[PlatonicSolid, float] = {
    PlatonicSolid.TETRAHEDRON: 2 / math.sqrt(3),
    PlatonicSolid.CUBE: 2 / math.sqrt(3),
    PlatonicSolid.OCTAHEDRON: 2.0,
    PlatonicSolid.DODECAHEDRON: 2 * _PHI / math.sqrt(3),
    PlatonicSolid.ICOSAHEDRON: 2 * _PHI / math.sqrt(1 + _PHI**2),
}

# Bounding box of each solid built with side=1, from the standard circumradius formulas.
_SIDE_BOXES: dict[PlatonicSolid, float] = {
    PlatonicSolid.TETRAHEDRON: 1 / math.sqrt(2),
    PlatonicSolid.CUBE: 1.0,
    PlatonicSolid.OCTAHEDRON: math.sqrt(2),
    PlatonicSolid.DODECAHEDRON: _PHI**2,
    PlatonicSolid.ICOSAHEDRON: _PHI,
}


@pytest.mark.parametrize("name", list(_COUNTS))
def test_default_solid_is_circumscribed_by_the_unit_sphere(name: PlatonicSolid) -> None:
    """With no size given every solid has circumradius 1, and is centred and isotropic."""
    lo, size = RegularPolyhedron(name).shape._native_bounds()  # type: ignore[misc]
    assert size == pytest.approx([_UNIT_BOXES[name]] * 3, abs=1e-9)
    assert lo == pytest.approx([-_UNIT_BOXES[name] / 2] * 3, abs=1e-9)


@pytest.mark.parametrize("name", list(_COUNTS))
def test_named_methods_match_the_enum_form(name: PlatonicSolid) -> None:
    """Each named factory is its enum call, and side= scales the box by the circumradius ratio."""
    named = getattr(RegularPolyhedron, name.value)(side=10).shape._native_bounds()  # type: ignore[misc]
    by_enum = RegularPolyhedron(name, side=10).shape._native_bounds()  # type: ignore[misc]
    assert named == by_enum
    assert named[1] == pytest.approx([10 * _SIDE_BOXES[name]] * 3, abs=1e-9)


def test_cube_circumradius_gives_expected_side() -> None:
    assert _size(RegularPolyhedron.cube(radius=10).shape)[0] == pytest.approx(2 * 10 / math.sqrt(3), abs=0.1)


def test_octahedron_inradius() -> None:
    w = _size(RegularPolyhedron.octahedron(inner_radius=8).shape)[0]
    assert w == pytest.approx(2 * 8 * math.sqrt(3), abs=0.2)


def test_unknown_name_raises() -> None:
    with pytest.raises(KeyError):
        RegularPolyhedron("prism")


@pytest.mark.parametrize("name", list(_COUNTS))
def test_a_platonic_solid_builds_on_either_backend(name: PlatonicSolid) -> None:
    """Convexity is what lets these cross over (TASKS T14).

    An SDF polyhedron is the intersection of its face half-spaces, so it can only describe a
    convex solid -- and a Platonic solid is convex by definition, which makes it one of the few
    meshes in the library that has an exact distance-field form. The nine that stay CSG-only are
    refused by the convexity check, not by a blanket guard.
    """
    import pybosl2.sdf  # noqa: F401  -- registers the sdf backend
    from pybosl2._backend import use_backend

    built = {}
    for backend in ("csg", "sdf"):
        with use_backend(backend):
            shape = RegularPolyhedron(name, side=10).shape
        assert shape.backend == backend
        built[backend] = [float(v) for v in shape.bounds()[1]]

    assert built["sdf"] == pytest.approx(built["csg"], abs=1e-6)
    assert built["csg"] == pytest.approx([10 * _SIDE_BOXES[name]] * 3, abs=1e-9)

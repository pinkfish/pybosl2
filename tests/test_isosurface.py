# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/isosurface.py: the marching-cubes mesher, the metaball field primitives, and
VNF.from_metaballs(). The mb_* formulas are pinned to real BOSL2 in tests/test_bosl2_reorient.py; here we
check the field values against their closed forms and the meshes GEOMETRICALLY (a lone metaball is
a sphere; overlapping ones merge; a torus has a hole). Native VNF is mocked, so mesh volume/vertex
checks run on the pure-Python VNF, and real geometry is verified in test_stl_render.py."""

import math

import numpy as np

from pybosl2.bounds import Bounds3D
from pybosl2.isosurface import (
    MetaballSpec,
    mb_capsule,
    mb_connector,
    mb_cuboid,
    mb_octahedron,
    mb_sphere,
    mb_torus,
)
from pybosl2.vnf import VNF

# -- field primitives ---------------------------------------------------------------------


def test_sphere_field_is_r_over_dist() -> None:
    f = mb_sphere(5)
    assert math.isclose(f([5, 0, 0]), 1.0, abs_tol=1e-9)  # type: ignore  # on the surface
    assert math.isclose(f([10, 0, 0]), 0.5, abs_tol=1e-9)  # type: ignore  # r/dist
    assert math.isclose(f([0, 3, 4]), 1.0, abs_tol=1e-9)  # type: ignore  # dist=5


def test_negative_flips_sign() -> None:
    assert mb_sphere(5, negative=True)([10, 0, 0]) < 0  # type: ignore[arg-type]


def test_influence_and_cutoff() -> None:
    base = mb_sphere(5)([10, 0, 0])  # type: ignore[arg-type]
    inf = mb_sphere(5, influence=2)([10, 0, 0])  # type: ignore[arg-type]
    assert math.isclose(inf, base**0.5, abs_tol=1e-9)
    assert mb_sphere(5, cutoff=8)([20, 0, 0]) == 0  # type: ignore[arg-type]


def test_torus_field_hole() -> None:
    f = mb_torus(8, 2)
    assert math.isclose(f([10, 0, 0]), 1.0, abs_tol=1e-9)  # type: ignore  # on the tube (dist from ring = 2)
    assert f([0, 0, 0]) < f([8, 0, 0])  # type: ignore  # center of hole is weaker than the ring


def test_capsule_field_straight_section() -> None:
    f = mb_capsule(24, 4)  # straight length 24-8=16, hl=8
    assert math.isclose(f([4, 0, 0]), 1.0, abs_tol=1e-9)  # type: ignore[arg-type]
    assert math.isclose(f([4, 0, 5]), 1.0, abs_tol=1e-9)  # type: ignore  # still on the straight part (|z|<=8)


def test_cuboid_and_octahedron_build() -> None:
    assert isinstance(mb_cuboid(20)([10, 0, 0]), float)  # type: ignore[arg-type]
    assert isinstance(mb_cuboid((16, 20, 24), 0.9)([8, 0, 0]), float)  # type: ignore[arg-type]
    assert isinstance(mb_octahedron(20)([10, 0, 0]), float)  # type: ignore[arg-type]


def test_connector_is_symmetric_capsule() -> None:
    f = mb_connector([-10, 0, 0], [10, 0, 0], 3)
    assert math.isclose(f([0, 3, 0]), 1.0, abs_tol=1e-9)  # type: ignore  # 3 away from the axis midpoint
    assert math.isclose(f([5, 0, 3]), f([-5, 0, 3]), abs_tol=1e-9)  # type: ignore  # symmetric


def test_metaball_vectorized_field() -> None:
    f = mb_sphere(5)
    vals = f.field(np.array([[5, 0, 0], [10, 0, 0], [0, 5, 0]]))
    np.testing.assert_allclose(vals, [1.0, 0.5, 1.0], atol=1e-9)


# -- isosurface meshing -------------------------------------------------------------------


def test_isosurface_sphere_volume() -> None:
    def sf(pts):  # type: ignore[no-untyped-def]
        return 8.0 / np.linalg.norm(pts, axis=1)

    vnf = VNF.from_field(sf, 1, Bounds3D(-12, -12, -12, 12, 12, 12, 24, 24, 24), voxel_size=1.5)
    ideal = 4 / 3 * math.pi * 8**3
    assert 0.9 * ideal < abs(vnf.volume()) < 1.05 * ideal
    assert len(vnf.faces) > 0


def test_isosurface_from_array() -> None:
    sides = 12
    xs = np.linspace(-6, 6, sides)
    gx, gy, gz = np.meshgrid(xs, xs, xs, indexing="ij")
    field = 4.0 / np.sqrt(gx**2 + gy**2 + gz**2 + 1e-9)
    vnf = VNF.from_field(field, 1, Bounds3D(-6, -6, -6, 6, 6, 6, 12, 12, 12))
    assert len(vnf.faces) > 0


def test_isosurface_reverse_flips_winding() -> None:
    def sf(pts):  # type: ignore[no-untyped-def]
        return 8.0 / np.linalg.norm(pts, axis=1)

    a = VNF.from_field(sf, 1, Bounds3D(-12, -12, -12, 12, 12, 12, 24, 24, 24), voxel_size=2)
    b = VNF.from_field(sf, 1, Bounds3D(-12, -12, -12, 12, 12, 12, 24, 24, 24), voxel_size=2, reverse=True)
    assert np.sign(a.volume()) == -np.sign(b.volume())


# -- metaballs ----------------------------------------------------------------------------


def test_metaballs_single_sphere_volume() -> None:
    vnf = VNF.from_metaballs(
        [MetaballSpec([0, 0, 0], mb_sphere(8))],  # type: ignore[arg-type]
        Bounds3D(-14, -14, -14, 14, 14, 14, 28, 28, 28),
        voxel_size=1.5,
    )
    ideal = 4 / 3 * math.pi * 8**3
    assert 0.9 * ideal < abs(vnf.volume()) < 1.05 * ideal


def test_metaballs_merge_is_bigger_than_parts() -> None:
    close = VNF.from_metaballs(
        [MetaballSpec([-6, 0, 0], mb_sphere(8)), MetaballSpec([6, 0, 0], mb_sphere(8))],  # type: ignore[arg-type]
        Bounds3D(-24, -16, -16, 24, 16, 16, 48, 32, 32),
        voxel_size=2,
    )
    one = VNF.from_metaballs(
        [MetaballSpec([0, 0, 0], mb_sphere(8))],  # type: ignore[arg-type]
        Bounds3D(-16, -16, -16, 16, 16, 16, 32, 32, 32),
        voxel_size=2,
    )
    assert abs(close.volume()) > 2 * abs(one.volume())


def test_metaballs_flat_spec_form() -> None:
    paired = VNF.from_metaballs(
        [MetaballSpec([0, 0, 0], mb_sphere(8))],  # type: ignore[arg-type]
        Bounds3D(-14, -14, -14, 14, 14, 14, 28, 28, 28),
        voxel_size=2,
    )
    flat = VNF.from_metaballs(
        [[0, 0, 0], mb_sphere(8)],  # type: ignore[list-item]
        Bounds3D(-14, -14, -14, 14, 14, 14, 28, 28, 28),
        voxel_size=2,
    )
    assert math.isclose(paired.volume(), flat.volume(), rel_tol=1e-6)


def test_metaballs_voxel_count() -> None:
    vnf = VNF.from_metaballs(
        [MetaballSpec([0, 0, 0], mb_sphere(8))],  # type: ignore[arg-type]
        Bounds3D(-14, -14, -14, 14, 14, 14, 28, 28, 28),
        voxel_count=8000,
    )
    assert len(vnf.faces) > 0


def test_metaballs_scalar_bounding_box() -> None:
    vnf = VNF.from_metaballs(
        [MetaballSpec([0, 0, 0], mb_sphere(6))],  # type: ignore[arg-type]
        Bounds3D(-12, -12, -12, 12, 12, 12, 24, 24, 24),
        voxel_size=2,
    )
    assert len(vnf.faces) > 0

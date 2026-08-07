# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

from pybosl2._sdf import shapes2d as sdf_s2d
from pybosl2._sdf import shapes3d as sdf_s3d
from pybosl2._sdf import skin as sdf_skin


class TestRevolveSDF:
    """revolve_sdf — revolve a 2-D SDF around the Z axis."""

    def test_full_revolution_builds(self) -> None:
        rect = sdf_s2d.rect2d([4, 10])
        shape = sdf_skin._revolve_sdf(rect).mesh()
        assert shape is not None

    def test_partial_revolution_builds(self) -> None:
        rect = sdf_s2d.rect2d([4, 10])
        shape = sdf_skin._revolve_sdf(rect, angle=90).mesh()
        assert shape is not None

    def test_circle_revolved_builds(self) -> None:
        circ = sdf_s2d.circle2d(radius=5).translate([8, 0])
        shape = sdf_skin._revolve_sdf(circ).mesh()
        assert shape is not None


class TestLinearSweepSDF:
    """linear_sweep_sdf — extrude with twist/scale/shift."""

    def test_plain_builds(self) -> None:
        shape = sdf_skin._linear_sweep_sdf(sdf_s2d.circle2d(radius=5), height=4).mesh()
        assert shape is not None


class TestSkinSDF:
    """skin_sdf — loft between stacked 2-D profiles."""

    def test_two_profile_loft(self) -> None:
        bottom = sdf_s2d.circle2d(radius=6)
        top = sdf_s2d.circle2d(radius=3)
        shape = sdf_skin.skin_sdf([bottom, top], z=[0, 10]).mesh()
        assert shape is not None

    def test_three_profile_stack(self) -> None:
        bot = sdf_s2d.square2d(12)
        mid = sdf_s2d.circle2d(radius=8)
        top = sdf_s2d.square2d(6)
        shape = sdf_skin.skin_sdf([bot, mid, top], z=[0, 6, 12]).mesh()
        assert shape is not None


class TestMeshToVNF:
    """mesh_to_vnf — extract VNF data from a meshed PyShape."""

    def test_cube_vnf_runs(self) -> None:
        # Takes the PyShape itself, not an already-meshed handle, and must come back with real
        # vertices -- it used to probe for attributes no native solid has and hand back ([], [])
        # without saying so.
        verts, faces = sdf_skin.mesh_to_vnf(sdf_s3d.cuboid([4, 4, 4]))
        assert verts, "mesh_to_vnf() returned no vertices"
        assert all(len(v) == 3 for v in verts)
        assert all(len(f) >= 3 for f in faces)

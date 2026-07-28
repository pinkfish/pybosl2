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

    def test_full_revolution_builds(self):
        rect = sdf_s2d.rect2d([4, 10])
        shape = sdf_skin.revolve_sdf(rect).mesh()
        assert shape is not None

    def test_partial_revolution_builds(self):
        rect = sdf_s2d.rect2d([4, 10])
        shape = sdf_skin.revolve_sdf(rect, angle=90).mesh()
        assert shape is not None

    def test_circle_revolved_builds(self):
        circ = sdf_s2d.circle2d(radius=5).translate([8, 0])
        shape = sdf_skin.revolve_sdf(circ).mesh()
        assert shape is not None


class TestLinearSweepSDF:
    """linear_sweep_sdf — extrude with twist/scale/shift."""

    def test_plain_builds(self):
        shape = sdf_skin.linear_sweep_sdf(sdf_s2d.circle2d(radius=5), height=4).mesh()
        assert shape is not None


class TestSkinSDF:
    """skin_sdf — loft between stacked 2-D profiles."""

    def test_two_profile_loft(self):
        bottom = sdf_s2d.circle2d(radius=6)
        top = sdf_s2d.circle2d(radius=3)
        shape = sdf_skin.skin_sdf([bottom, top], z=[0, 10]).mesh()
        assert shape is not None

    def test_three_profile_stack(self):
        bot = sdf_s2d.square2d(12)
        mid = sdf_s2d.circle2d(radius=8)
        top = sdf_s2d.square2d(6)
        shape = sdf_skin.skin_sdf([bot, mid, top], z=[0, 6, 12]).mesh()
        assert shape is not None


class TestMeshToVNF:
    """mesh_to_vnf — extract VNF data from a meshed PyShape."""

    def test_cube_vnf_runs(self):
        shape = sdf_s3d.cuboid([4, 4, 4]).mesh()
        verts, faces = sdf_skin.mesh_to_vnf(shape)
        assert verts is not None
        assert faces is not None

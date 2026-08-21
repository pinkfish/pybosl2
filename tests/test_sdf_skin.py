# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

import pytest

from pybosl2.sdf import shapes2d as sdf_s2d
from pybosl2.sdf import shapes3d as sdf_s3d
from pybosl2.sdf import skin as sdf_skin


class TestRevolveSDF:
    """revolve_sdf — revolve a 2-D SDF around the Z axis."""

    def test_full_revolution_builds(self) -> None:
        """The 4x10 profile spins about Z, so its width becomes the radius and its height the Z run."""
        revolved = sdf_skin._revolve_sdf(sdf_s2d.rect2d([4, 10]))
        assert [float(v) for v in revolved.mn] == pytest.approx([-2.0, -2.0, -5.0])
        assert [float(v) for v in revolved.mx] == pytest.approx([2.0, 2.0, 5.0])
        assert revolved.mesh() is not None  # ...and it meshes

    def test_partial_revolution_builds(self) -> None:
        """A quarter turn is the same field clipped, so its bounds cannot exceed the full sweep's."""
        full = sdf_skin._revolve_sdf(sdf_s2d.rect2d([4, 10]))
        quarter = sdf_skin._revolve_sdf(sdf_s2d.rect2d([4, 10]), angle=90)
        assert [float(v) for v in quarter.mx] == pytest.approx([float(v) for v in full.mx])
        assert quarter.mesh() is not None

    def test_circle_revolved_builds(self) -> None:
        """A radius-5 circle 8 out from the axis sweeps a torus reaching 13 from the centre."""
        torus = sdf_skin._revolve_sdf(sdf_s2d.circle2d(radius=5).translate([8, 0]))
        assert [float(v) for v in torus.mx] == pytest.approx([13.0, 13.0, 5.0])
        assert [float(v) for v in torus.mn] == pytest.approx([-13.0, -13.0, -5.0])


class TestLinearSweepSDF:
    """linear_sweep_sdf — extrude with twist/scale/shift."""

    def test_plain_builds(self) -> None:
        """A linear sweep keeps the profile's own footprint and stands `height` tall from z=0."""
        swept = sdf_skin._linear_sweep_sdf(sdf_s2d.circle2d(radius=5), height=4)
        assert [float(v) for v in swept.mn] == pytest.approx([-5.0, -5.0, 0.0])
        assert [float(v) for v in swept.mx] == pytest.approx([5.0, 5.0, 4.0])
        assert swept.mesh() is not None


class TestSkinSDF:
    """skin_sdf — loft between stacked 2-D profiles."""

    def test_two_profile_loft(self) -> None:
        """A loft spans the widest profile and runs between the two z heights it was given."""
        lofted = sdf_skin.skin_sdf([sdf_s2d.circle2d(radius=6), sdf_s2d.circle2d(radius=3)], z=[0, 10])
        assert [float(v) for v in lofted.mn] == pytest.approx([-6.0, -6.0, 0.0])
        assert [float(v) for v in lofted.mx] == pytest.approx([6.0, 6.0, 10.0])
        assert lofted.mesh() is not None

    def test_three_profile_stack(self) -> None:
        """With three profiles the widest is the radius-8 circle in the middle, not an end."""
        stacked = sdf_skin.skin_sdf(
            [sdf_s2d.square2d(12), sdf_s2d.circle2d(radius=8), sdf_s2d.square2d(6)], z=[0, 6, 12]
        )
        assert [float(v) for v in stacked.mn] == pytest.approx([-8.0, -8.0, 0.0])
        assert [float(v) for v in stacked.mx] == pytest.approx([8.0, 8.0, 12.0])
        assert stacked.mesh() is not None


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

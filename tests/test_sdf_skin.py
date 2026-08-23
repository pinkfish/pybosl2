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


def _at(shape: object, x: float, y: float, z: float) -> float:
    """Sample an SDF shape's own field directly, without meshing it."""
    d = shape._sdf_fn(x, y, z)  # type: ignore[attr-defined]
    return float(d(x, y, z)) if callable(d) else float(d)


def _inside(shape: object, x: float, y: float, z: float) -> bool:
    return _at(shape, x, y, z) <= 1e-6


class TestLinearSweepModifiers:
    """The twist / scale / shift branch of _linear_sweep_sdf, checked against the transform the
    CSG sweep applies: ``translate(u*shift) @ scale(u) @ zrot(-twist*u)``."""

    SQUARE = [10.0, 10.0]  # so the profile runs -5..5 on both axes

    def test_scale_widens_the_top_only(self) -> None:
        """scale=2 leaves the base its own size and doubles the top."""
        swept = sdf_skin._linear_sweep_sdf(sdf_s2d.rect2d(self.SQUARE), height=10, scale=2.0)
        assert _inside(swept, 4.5, 0.0, 0.1)  # base: still the 10-wide profile
        assert not _inside(swept, 5.5, 0.0, 0.1)
        assert _inside(swept, 9.5, 0.0, 9.9)  # top: twice as wide
        assert not _inside(swept, 10.5, 0.0, 9.9)

    def test_shift_moves_the_top_face_by_exactly_the_shift(self) -> None:
        """shift=(4, 0) slides the top 4mm along X, so it spans -1..9 rather than -5..5."""
        swept = sdf_skin._linear_sweep_sdf(sdf_s2d.rect2d(self.SQUARE), height=10, shift=(4.0, 0.0))
        assert _inside(swept, 8.5, 0.0, 9.9)
        assert not _inside(swept, 9.5, 0.0, 9.9)
        assert _inside(swept, -0.5, 0.0, 9.9)
        assert not _inside(swept, -1.5, 0.0, 9.9)

    def test_shift_is_not_scaled_by_the_scale(self) -> None:
        """With both, the top is scaled about the origin and *then* shifted: half-width 10
        centred on x=4, so -6..14. Shifting before scaling stretched it to -2..18."""
        swept = sdf_skin._linear_sweep_sdf(sdf_s2d.rect2d(self.SQUARE), height=10, scale=2.0, shift=(4.0, 0.0))
        assert _inside(swept, 13.9, 0.0, 9.9)
        assert not _inside(swept, 14.1, 0.0, 9.9)
        assert _inside(swept, -5.0, 0.0, 9.9)
        assert not _inside(swept, -7.0, 0.0, 9.9)

    def test_twist_turns_the_same_way_as_the_csg_sweep(self) -> None:
        """A blob 5mm out along +X, twisted a quarter turn, ends up at (0, -5) -- the direction
        the CSG sweep's zrot(-twist*u) takes it, not its mirror."""
        profile = sdf_s2d.circle2d(radius=1.5).translate([5, 0])
        swept = sdf_skin._linear_sweep_sdf(profile, height=10, twist=90.0)
        assert _inside(swept, 5.0, 0.0, 0.1)  # base: where it started
        assert _inside(swept, 0.0, -5.0, 9.9)  # top: a quarter turn clockwise
        assert not _inside(swept, 0.0, 5.0, 9.9)

    def test_twisted_bounds_reach_the_swept_corners(self) -> None:
        """A 10x10 square twisted 45 degrees swings its corners out to 5*sqrt(2); the bounds are
        the meshing domain, so claiming the untwisted +/-5 would slice those corners off."""
        import math

        swept = sdf_skin._linear_sweep_sdf(sdf_s2d.rect2d(self.SQUARE), height=10, twist=45.0)
        assert float(swept.mx[0]) == pytest.approx(5 * math.sqrt(2), abs=1e-6)
        assert float(swept.mn[0]) == pytest.approx(-5 * math.sqrt(2), abs=1e-6)
        # ...and the corner really is out there, so the bound is needed, not merely generous.
        assert _inside(swept, 0.0, 7.0, 9.9)

    def test_shift_bounds_follow_the_shifted_axis(self) -> None:
        """A shift along X widens the X bound only; Y keeps the profile's own half-width."""
        swept = sdf_skin._linear_sweep_sdf(sdf_s2d.rect2d(self.SQUARE), height=10, shift=(4.0, 0.0))
        assert float(swept.mx[0]) == pytest.approx(9.0)
        assert float(swept.mx[1]) == pytest.approx(5.0)

    def test_a_zero_shift_list_still_takes_the_exact_path(self) -> None:
        """shift defaults to a tuple, so a caller passing the equivalent list asked for nothing:
        it must still get the exact extrusion, not the swept approximation of one."""
        listed = sdf_skin._linear_sweep_sdf(sdf_s2d.circle2d(radius=5), height=4, shift=[0.0, 0.0])
        exact = sdf_s2d.circle2d(radius=5).extrude(4)
        assert [float(v) for v in listed.mn] == pytest.approx([float(v) for v in exact.mn])
        assert [float(v) for v in listed.mx] == pytest.approx([float(v) for v in exact.mx])

    def test_a_unit_scale_pair_still_takes_the_exact_path(self) -> None:
        """Likewise scale=[1, 1]: a pair that scales nothing is not a modifier."""
        paired = sdf_skin._linear_sweep_sdf(sdf_s2d.circle2d(radius=5), height=4, scale=[1.0, 1.0])
        exact = sdf_s2d.circle2d(radius=5).extrude(4)
        assert [float(v) for v in paired.mn] == pytest.approx([float(v) for v in exact.mn])
        assert [float(v) for v in paired.mx] == pytest.approx([float(v) for v in exact.mx])

    def test_center_puts_the_sweep_half_below_the_origin(self) -> None:
        """center=True runs the sweep -h/2..h/2, and the taper still starts at the bottom."""
        swept = sdf_skin._linear_sweep_sdf(sdf_s2d.rect2d(self.SQUARE), height=10, scale=2.0, center=True)
        assert float(swept.mn[2]) == pytest.approx(-5.0)
        assert float(swept.mx[2]) == pytest.approx(5.0)
        assert _inside(swept, 4.5, 0.0, -4.9)  # narrow end at the bottom
        assert not _inside(swept, 5.5, 0.0, -4.9)
        assert _inside(swept, 9.5, 0.0, 4.9)  # wide end at the top

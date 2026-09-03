# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Textures reach geometry, not just the registry (SPEC S-34, S-35).

S-34 says named textures come from one registry and the caller need not know whether a given one
is a height field or a VNF tile; S-35 says anything that can be textured accepts the texture plus
the same controls. The registry half was built and the application half was not: `cyl(texture=...)`
raised for every one of the five parameters it declared (§12.2 item 7c). T37 built the cylinder
family's half.
"""

from __future__ import annotations

import math

import pytest

from pybosl2 import Anchor, cyl, cylinder, texture, xcyl, ycyl, zcyl
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.texture import height_field, texture_grid, textured_cylinder_vnf


class TestHeightField:
    """Both kinds of texture reduce to one thing a surface can be displaced by (SPEC S-34)."""

    def test_a_height_field_texture_passes_through(self) -> None:
        assert height_field("ribs") == [[1.0, 0.0]]

    def test_a_vnf_tile_is_rasterised_to_one(self) -> None:
        """`dots` is a VNF tile, and the caller does not have to know that."""
        field = height_field("dots", sides=8)
        assert len(field) == 8
        assert all(len(row) == 8 for row in field)
        assert min(min(r) for r in field) >= 0.0
        assert max(max(r) for r in field) <= 1.0

    def test_an_unknown_texture_is_refused(self) -> None:
        with pytest.raises(Bosl2ValueError, match="neither a height field nor a VNF tile"):
            height_field(object())  # type: ignore[arg-type]

    def test_the_grid_tiles_and_wraps(self) -> None:
        grid = texture_grid(height_field("ribs"), reps_around=3, reps_along=2)
        assert len(grid) == 1 * 2 + 1, "one row per cell along, plus the closing row"
        assert len(grid[0]) == 2 * 3, "one column per cell around"
        assert grid[0] == [1.0, 0.0] * 3

    def test_a_zero_repeat_is_refused(self) -> None:
        with pytest.raises(Bosl2ValueError, match="at least 1"):
            texture_grid(height_field("ribs"), reps_around=0, reps_along=1)


class TestTexturedCylinderMesh:
    """The mesh itself, built in pure Python with no CAD runtime (SPEC A-2)."""

    def test_it_is_watertight(self) -> None:
        mesh = textured_cylinder_vnf(20, 10, 10, "ribs", tex_reps=[12, 1], tex_depth=1.5)
        assert mesh.is_watertight()
        assert mesh.volume() > 0, "and wound outwards (SPEC S-19c)"

    def test_an_undisplaced_texture_is_the_plain_cylinder(self) -> None:
        """tex_depth=0 must change nothing, which is what makes the displacement measurable."""
        mesh = textured_cylinder_vnf(20, 10, 10, "ribs", tex_reps=[64, 1], tex_depth=0)
        assert mesh.volume() == pytest.approx(math.pi * 100 * 20, rel=0.01)

    def test_depth_adds_material_and_shows_in_the_bounds(self) -> None:
        mesh = textured_cylinder_vnf(20, 10, 10, "ribs", tex_reps=[12, 1], tex_depth=1.5)
        assert mesh.bounds().size[0] == pytest.approx(2 * 11.5, abs=0.01)

    def test_inset_sinks_the_surface_before_the_texture_is_added(self) -> None:
        """With inset equal to depth the peaks sit flush with the original radius."""
        mesh = textured_cylinder_vnf(20, 10, 10, "ribs", tex_reps=[12, 1], tex_depth=1.5, tex_inset=True)
        assert mesh.bounds().size[0] == pytest.approx(20.0, abs=0.01)

    def test_a_vnf_tile_textures_too(self) -> None:
        mesh = textured_cylinder_vnf(20, 10, 10, "dots", tex_reps=[6, 3], tex_depth=1, sides=8)
        assert mesh.is_watertight()

    def test_tex_size_derives_the_repeats_from_the_cylinder(self) -> None:
        """One tile every 6 mm around a circumference of 2*pi*10 is about ten of them."""
        mesh = textured_cylinder_vnf(20, 10, 10, "ribs", tex_size=6, tex_depth=1)
        assert mesh.is_watertight()

    def test_size_and_reps_together_are_refused(self) -> None:
        with pytest.raises(Bosl2ValueError, match="not both and not neither"):
            textured_cylinder_vnf(20, 10, 10, "ribs", tex_size=5, tex_reps=[4, 1])

    def test_neither_size_nor_reps_is_refused(self) -> None:
        with pytest.raises(Bosl2ValueError, match="not both and not neither"):
            textured_cylinder_vnf(20, 10, 10, "ribs")

    def test_a_taper_is_textured_along_its_slope(self) -> None:
        mesh = textured_cylinder_vnf(20, 10, 4, "diamonds", tex_reps=[8, 2], tex_depth=1)
        assert mesh.is_watertight()
        assert mesh.bounds().size[2] == pytest.approx(20.0)


class TestTexturedCylinderSolid:
    """The parameter S-35 asks for, on the constructors that declare it."""

    def test_cyl_builds_a_textured_solid(self) -> None:
        ribbed = cyl(height=20, radius=10, texture="ribs", tex_reps=[12, 1], tex_depth=1.5)
        assert ribbed.bounds().size == pytest.approx([23.0, 23.0, 20.0], abs=0.01)
        assert ribbed.vnf().is_watertight()

    def test_it_adds_material_over_the_plain_cylinder(self) -> None:
        plain = cyl(height=20, radius=10)
        ribbed = cyl(height=20, radius=10, texture="ribs", tex_reps=[12, 1], tex_depth=1.5)
        assert ribbed.vnf().volume() > plain.vnf().volume()

    @pytest.mark.parametrize("constructor", [cyl, cylinder, zcyl])
    def test_the_upright_cylinders_all_take_it(self, constructor: object) -> None:
        shape = constructor(height=20, radius=8, texture="ribs", tex_reps=[10, 1], tex_depth=1)  # type: ignore[operator]
        assert shape.bounds().size[2] == pytest.approx(20.0)

    @pytest.mark.parametrize(("constructor", "axis"), [(xcyl, 0), (ycyl, 1)])
    def test_the_lying_cylinders_texture_along_their_own_axis(self, constructor: object, axis: int) -> None:
        shape = constructor(height=20, radius=8, texture="ribs", tex_reps=[10, 1], tex_depth=1)  # type: ignore[operator]
        assert shape.bounds().size[axis] == pytest.approx(20.0)

    def test_an_anchor_still_places_it(self) -> None:
        shape = cyl(height=20, radius=10, texture="ribs", tex_reps=[12, 1], anchor=Anchor.BOTTOM)
        assert shape.bounds().min[2] == pytest.approx(0.0)

    def test_omitting_the_repeats_matches_the_plain_facet_count(self) -> None:
        """SPEC R-1: texturing must not silently coarsen the shape."""
        plain = cyl(height=20, radius=10)
        textured = cyl(height=20, radius=10, texture="ribs", tex_depth=0.0001)
        assert textured.bounds().size[0] == pytest.approx(plain.bounds().size[0], abs=0.2)

    def test_omitting_both_repeats_and_size_still_textures(self) -> None:
        """SPEC D-4/P-1: `None` means decide, and one tile around a whole cylinder is not a texture.

        The repeats come from the geometry -- as many around as the circumference holds at the
        cylinder's own height, so one tile is roughly square in world space.
        """
        shape = cyl(height=20, radius=10, texture="ribs", tex_depth=1)
        assert shape.vnf().is_watertight()
        assert max(shape.bounds().size[:2]) > 20.0, "the texture actually displaced the surface"
        assert max(shape.bounds().size[:2]) <= 22.0, "and by no more than tex_depth"

    def test_the_registry_and_the_parameter_agree_on_names(self) -> None:
        """S-34: one registry, and the parameter takes what it returns."""
        assert texture("diamonds")
        built = cyl(height=20, radius=10, texture="diamonds", tex_reps=[8, 2], tex_depth=1)
        assert built.vnf().is_watertight()

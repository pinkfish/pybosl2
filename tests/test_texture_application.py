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


class TestText3d:
    """`text3d` is the one extrusion SPEC S-22 names that nothing tested (T39).

    It was the gap the T38 triage found behind S-22: every other extrusion the rule lists is
    exercised somewhere, and this one was not, so nothing would have noticed it breaking.
    """

    def test_it_builds_text_of_the_requested_size(self) -> None:
        from pybosl2.shapes3d.extrusions import text3d

        shape = text3d("BOSL2", size=10, height=3)
        assert shape.bounds().size[2] == pytest.approx(3.0), "the extrusion height"
        assert shape.bounds().size[0] > shape.bounds().size[1], "five characters are wider than tall"
        assert shape.vnf().volume() > 0

    def test_height_and_size_are_independent(self) -> None:
        from pybosl2.shapes3d.extrusions import text3d

        thin = text3d("X", size=10, height=1)
        thick = text3d("X", size=10, height=4)
        assert thick.bounds().size[2] == pytest.approx(4 * thin.bounds().size[2])
        assert thick.bounds().size[0] == pytest.approx(thin.bounds().size[0])

    def test_it_takes_the_anchor_language(self) -> None:
        """PLAN O-6b: it took `anchor: str = "baseline[-1,0,-1]"` until T39."""
        from pybosl2 import Anchor
        from pybosl2.shapes3d.extrusions import text3d

        centred = text3d("X", size=10, height=3, anchor=Anchor.CENTER)
        assert centred.bounds().min[2] == pytest.approx(-1.5), "centred on its own height"

    def test_valign_still_carries_the_typographic_half(self) -> None:
        """The baseline moved to `valign`, as it did for `flat.text()` in T36 -- it is not lost."""
        from pybosl2.shapes3d.extrusions import text3d

        assert text3d("X", size=10, height=3, valign="top").bounds().max[1] == pytest.approx(0.0, abs=0.01)


# ---------------------------------------------------------------------------
# SPEC S-35: anything that can be textured honours it
# ---------------------------------------------------------------------------

#: How to build each callable that declares a `texture` parameter, plain and textured. A new
#: declarer has to be added here, which is the point: `texture=` was declared on the bottle caps
#: and silently ignored for as long as they existed, and nothing could have noticed.
TEXTURABLE: dict[str, tuple[object, dict[str, object], dict[str, object]]] = {}


def _textureable_cases() -> list[tuple[str, object, dict[str, object], dict[str, object]]]:
    """Return (label, callable, plain kwargs, textured kwargs) for every texture-taking callable."""
    from pybosl2 import cyl, cylinder, xcyl, ycyl, zcyl
    from pybosl2.parts.bottlecaps import BottleCaps, BottleCapTexture
    from pybosl2.surfaces3d import textured_tile

    cylinder_args = ({"height": 20, "radius": 10}, {"texture": "ribs", "tex_reps": [12, 1], "tex_depth": 1})
    return [
        ("cyl", cyl, *cylinder_args),
        ("cylinder", cylinder, *cylinder_args),
        ("xcyl", xcyl, *cylinder_args),
        ("ycyl", ycyl, *cylinder_args),
        ("zcyl", zcyl, *cylinder_args),
        (
            "textured_tile",
            textured_tile,
            {"size": [20, 20, 3], "texture": "ribs", "tex_reps": [4, 4], "tex_depth": 0.001},
            {"size": [20, 20, 3], "texture": "ribs", "tex_reps": [4, 4], "tex_depth": 1},
        ),
        ("pco1810_cap", BottleCaps.pco1810_cap, {}, {"texture": BottleCapTexture.RIBS}),
        ("pco1881_cap", BottleCaps.pco1881_cap, {}, {"texture": BottleCapTexture.CHECKERS}),
    ]


CASES = _textureable_cases()


def test_every_texture_taking_callable_is_covered() -> None:
    """A new callable declaring `texture=` has to say how to exercise it (SPEC S-35).

    The scan is over the package rather than over this list, so adding a declarer without adding a
    case fails -- which is what would have caught the bottle caps.
    """
    import ast
    import pathlib

    package = pathlib.Path(__file__).resolve().parent.parent / "pybosl2"
    declarers: set[str] = set()
    for path in sorted(package.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            names = {a.arg for a in node.args.args + node.args.kwonlyargs}
            # `resolve_texturing` takes the parameters to resolve them, and builds nothing.
            if "texture" in names and node.name != "resolve_texturing":
                declarers.add(node.name)
    covered = {label for label, *_ in CASES}
    assert declarers <= covered, (
        f"these declare `texture=` and no case exercises it: {sorted(declarers - covered)}. "
        f"Add one to `_textureable_cases`, or the parameter is advertised and unchecked (S-35)."
    )


@pytest.mark.parametrize(
    ("label", "builder", "plain", "textured"), CASES, ids=lambda v: v if isinstance(v, str) else ""
)
def test_the_texture_reaches_the_geometry(
    label: str, builder: object, plain: dict[str, object], textured: dict[str, object]
) -> None:
    """SPEC S-35: declaring the parameter and ignoring it is the silent no-op E-5 forbids.

    The bottle caps accepted a `BottleCapTexture` and built a plain wall, with a module comment
    saying so -- which is a documented silent wrong answer rather than an excuse for one. They
    apply the named style to the cap's outer wall now, inset so the knurl is cut *into* the
    nominal diameter rather than grown outside it.
    """
    without = builder(**plain)  # type: ignore[operator]
    with_texture = builder(**textured)  # type: ignore[operator]
    assert with_texture.vnf().volume() != pytest.approx(without.vnf().volume(), rel=1e-4), (
        f"{label}: the texture changed nothing, so the parameter is decorative"
    )


def test_a_knurl_is_cut_in_rather_than_grown_on() -> None:
    """The cap keeps its nominal diameter: a grip is cut into the wall, not added outside it."""
    from pybosl2.parts.bottlecaps import BottleCaps, BottleCapTexture

    plain = BottleCaps.pco1810_cap()
    ribbed = BottleCaps.pco1810_cap(texture=BottleCapTexture.RIBS)
    assert ribbed.bounds().size[0] == pytest.approx(plain.bounds().size[0], abs=0.1)
    assert ribbed.vnf().volume() < plain.vnf().volume(), "a knurl removes material"


def test_every_cap_style_builds_something_different() -> None:
    """Three named styles, three different caps -- not two aliases and a no-op."""
    from pybosl2.parts.bottlecaps import BottleCaps, BottleCapTexture

    volumes = {style.value: BottleCaps.pco1881_cap(texture=style).vnf().volume() for style in BottleCapTexture}
    assert len({round(v, 3) for v in volumes.values()}) == len(volumes), volumes

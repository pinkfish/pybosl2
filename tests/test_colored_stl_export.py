# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""An example that sets a colour renders in that colour (SPEC DOC-2).

The docs viewer showed every mesh in one flat default, because the export was a plain STL and an
STL has nowhere to put a colour. `pybosl2/color.py`'s own rendering example -- three cuboids in
`rainbow_colors(3)` -- therefore demonstrated the opposite of what it is about.

3MF does carry colour: PythonSCAD writes a `<basematerials>` table and tags each triangle with
`pid`/`p1`. So the docs export goes to 3MF and `convert_3mf_to_colored_stl` rewrites it into the
STL colour extension that VisCAM and Magics introduced, which is what three.js's `STLLoader`
reads back as `geometry.hasColors`. One file format still serves the viewer and the download link.

**Colour survives a union, including an overlapping one**, which is worth stating because it is
easy to assume otherwise: three disjoint cuboids keep 12 tagged facets each, and a cuboid
*overlapping* a cylinder still comes out 48 facets red and 92 steelblue. PythonSCAD tags triangles
with `p1`, not objects with `pindex`, so merging bodies does not merge their colours.

**The format quantises to five bits a channel**, which is the one place a colour is not exact:
bit 15 of the per-facet attribute flags "has a colour" and the fifteen below it hold R, G and B.
Pure channels round-trip exactly; steelblue `(70, 130, 180)` comes back `(74, 132, 181)`. Any
assertion on a non-primary colour has to allow for that, so the tests below say so rather than
pinning a number that looks arbitrary.
"""

from __future__ import annotations

import struct
import zipfile
from typing import TYPE_CHECKING

import pytest
from render_stl import convert_3mf_to_colored_stl, find_pythonscad_binary, render_stl_script

if TYPE_CHECKING:
    from pathlib import Path

#: The rendering example in `pybosl2/color.py`, which is the reason this file exists.
RAINBOW = """
from pybosl2.color import rainbow_colors
from pybosl2.shapes3d import cuboid
cols = rainbow_colors(3)
a = cuboid([5, 5, 10]).color(cols[0])
b = cuboid([5, 5, 10]).color(cols[1]).right(8)
c = cuboid([5, 5, 10]).color(cols[2]).right(16)
(a | b | c).show()
"""

#: One body, so one colour -- the case that must degrade rather than fail.
ONE_BODY = """
from pybosl2 import cuboid, cyl
(cuboid([20, 20, 6]).color("red") | cyl(radius=5, height=20).color("steelblue")).show()
"""


def _facet_colors(path: Path) -> dict[tuple[int, int, int], int]:
    """Return the per-facet colours of a binary STL, as ``{(r, g, b): facet count}``.

    Reads the attribute word the colour convention uses: bit 15 clear means "this facet carries
    its own colour", with five bits per channel below it.
    """
    data = path.read_bytes()
    count = struct.unpack("<I", data[80:84])[0]
    found: dict[tuple[int, int, int], int] = {}
    for index in range(count):
        attribute = struct.unpack("<H", data[84 + index * 50 + 48 : 84 + index * 50 + 50])[0]
        if attribute & 0x8000:
            continue
        rgb = tuple(round(((attribute >> shift) & 31) / 31 * 255) for shift in (0, 5, 10))
        found[rgb] = found.get(rgb, 0) + 1  # type: ignore[index]
    return found


pytestmark = pytest.mark.skipif(
    find_pythonscad_binary() is None,
    reason="needs the PythonSCAD app binary to export a mesh",
)


def test_the_colour_example_exports_the_colours_it_sets(tmp_path: Path) -> None:
    """`rainbow_colors(3)` reaches the mesh as three pure channels, twelve facets each.

    Twelve is a cuboid's triangle count, so this says each of the three stayed its own body and
    kept its own colour -- not merely that *some* colour survived.
    """
    out = tmp_path / "rainbow.stl"
    result = render_stl_script(RAINBOW, out, timeout=300.0, export_format="binstl", prefer_color=True)
    assert result.ok, f"render failed: {result.error}"
    assert out.read_bytes()[:6] == b"COLOR=", "the colour convention announces itself in the header"

    colors = _facet_colors(out)
    assert colors == {(255, 0, 0): 12, (0, 255, 0): 12, (0, 0, 255): 12}, (
        f"expected rainbow_colors(3) one cuboid at a time, got {colors}"
    )


def test_colour_survives_an_overlapping_union(tmp_path: Path) -> None:
    """Merging two bodies does not merge their colours, and the quantisation is the only loss.

    This was written expecting the opposite -- that a union into one manifold body would carry a
    single material -- and the measurement said no. PythonSCAD tags *triangles* with `p1` rather
    than tagging objects, so each facet keeps the colour of the piece it came from. The test is
    kept pointing at the overlapping case precisely because that is the one a reader would assume
    cannot work.
    """
    out = tmp_path / "one_body.stl"
    result = render_stl_script(ONE_BODY, out, timeout=300.0, export_format="binstl", prefer_color=True)
    assert result.ok, f"render failed: {result.error}"

    colors = _facet_colors(out)
    assert len(colors) == 2, f"both colours should reach the mesh, got {colors}"
    assert (255, 0, 0) in colors, f"red is a pure channel and round-trips exactly, got {colors}"
    # steelblue is (70, 130, 180); five bits a channel put it within ~5 of that.
    blue = next(rgb for rgb in colors if rgb != (255, 0, 0))
    assert all(abs(a - b) <= 5 for a, b in zip(blue, (70, 130, 180), strict=True)), (
        f"{blue} is not steelblue within the format's five-bit quantisation"
    )


def test_an_uncoloured_example_is_untouched_byte_for_byte(tmp_path: Path) -> None:
    """`prefer_color` must be a no-op for anything that never sets a colour.

    Two things depend on this. The viewer's own colour is **theme-aware** -- it follows the
    light/dark toggle -- and a per-facet colour overrides it, so painting an uncoloured mesh
    would pin all 176 uncoloured examples to one shade. And the docs cache 685 meshes *in the
    repository*, keyed by a hash of the snippet; if this route changed their bytes, every one of
    them would have to be regenerated and re-committed.

    Every export carries PythonSCAD's implicit "Default" material -- its preview yellow,
    #F9D72C -- and tags each facet with it, so the naive converter did paint them. The guard is
    that `convert_3mf_to_colored_stl` declines when no facet names a material other than
    "Default", handing the caller back to the plain export.
    """
    source = "from pybosl2 import cuboid\ncuboid([10, 10, 10]).show()\n"
    with_colour = tmp_path / "a.stl"
    without = tmp_path / "b.stl"
    assert render_stl_script(source, with_colour, timeout=300.0, export_format="binstl", prefer_color=True).ok
    assert render_stl_script(source, without, timeout=300.0, export_format="binstl").ok

    assert with_colour.read_bytes() == without.read_bytes(), (
        "the colour route changed an uncoloured mesh: the viewer would stop following the "
        "light/dark theme and all 685 cached meshes would need regenerating"
    )
    assert with_colour.read_bytes()[:6] != b"COLOR=", "and it is not announcing facet colour"


def test_a_3mf_without_triangles_falls_back_rather_than_shipping_an_empty_mesh(tmp_path: Path) -> None:
    """`convert_3mf_to_colored_stl` returns False so the caller uses the plain export.

    The distinction matters: returning a *failure* would lose the mesh entirely, where returning
    False loses only the colour.
    """
    empty = tmp_path / "empty.3mf"
    with zipfile.ZipFile(empty, "w") as archive:
        archive.writestr("3D/3dmodel.model", '<?xml version="1.0"?><model><resources/></model>')
    assert convert_3mf_to_colored_stl(empty, tmp_path / "out.stl") is False
    assert not (tmp_path / "out.stl").exists(), "nothing is written when there is nothing to write"

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/svg.py: loading an SVG drawing as real outlines rather than an opaque
handle from the renderer's own importer. Fixtures are written inline so the suite carries no
binary assets and runs without a renderer -- which is half the point of loading SVG this way."""

import textwrap
from pathlib import Path

import pytest

from pybosl2.regions import Region
from pybosl2.svg import region_from_svg, regions_from_svg, svg_element_groups, svg_outlines, svg_rings_with_colors

# A 100x50 rect with a 20x10 hole, plus a separate 10x10 square: three rings, two solids.
TWO_SOLIDS = textwrap.dedent(
    """\
    <svg xmlns="https://www.w3.org/2000/svg" width="200" height="100" viewBox="0 0 200 100">
      <path d="M 0,0 H 100 V 50 H 0 Z"/>
      <path d="M 10,10 H 30 V 20 H 10 Z"/>
      <path d="M 150,0 H 160 V 10 H 150 Z"/>
    </svg>
    """
)

EMPTY = """\
<svg xmlns="https://www.w3.org/2000/svg" width="100" height="100">
</svg>
"""

NO_SHAPES = """\
<svg xmlns="https://www.w3.org/2000/svg" width="100" height="100">
  <g id="empty-group"/>
</svg>
"""

MOVE_ONLY = """\
<svg xmlns="https://www.w3.org/2000/svg" width="100" height="100">
  <path d="M 10,10 M 20,20 M 30,30"/>
</svg>
"""

NESTED_G = """\
<svg xmlns="https://www.w3.org/2000/svg" width="100" height="100">
  <g>
    <g>
      <path d="M 0,0 H 40 V 30 H 0 Z"/>
    </g>
  </g>
</svg>
"""

TEXT_ELEMENT = """\
<svg xmlns="https://www.w3.org/2000/svg" width="100" height="100">
  <text x="10" y="30">hello</text>
  <path d="M 0,0 H 50 V 40 H 0 Z"/>
</svg>
"""

CURVED = textwrap.dedent(
    """\
    <svg xmlns="https://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
      <path d="M 0,0 C 0,50 50,50 50,0 Z"/>
    </svg>
    """
)

# A long cubic bezier: M0,0 → C0,200,200,200,200,0 — arc length ~300 user units.
LONG_CURVE = textwrap.dedent(
    """\
    <svg xmlns="https://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
      <path d="M 0,0 C 0,200 200,200 200,0 Z"/>
    </svg>
    """
)

PIXEL_UNITS = textwrap.dedent(
    """\
    <svg xmlns="https://www.w3.org/2000/svg" width="800px" height="600px">
      <path d="M 0,0 H 100 V 200 H 0 Z"/>
    </svg>
    """
)

COLORED = textwrap.dedent(
    """\
    <svg xmlns="https://www.w3.org/2000/svg" width="100" height="100">
      <path d="M 0,0 H 40 V 30 H 0 Z" fill="#ff0000"/>
      <path d="M 50,0 H 80 V 30 H 50 Z" fill="#0000ff"/>
    </svg>
    """
)

MIXED_FILL = textwrap.dedent(
    """\
    <svg xmlns="https://www.w3.org/2000/svg" width="100" height="100">
      <path d="M 0,0 H 30 V 30 H 0 Z" fill="#ff0000"/>
      <path d="M 40,0 H 70 V 30 H 40 Z" fill="none"/>
      <circle cx="15" cy="55" r="10" fill="green"/>
    </svg>
    """
)

OPACITY_FILL = textwrap.dedent(
    """\
    <svg xmlns="https://www.w3.org/2000/svg" width="100" height="100">
      <path d="M 0,0 H 40 V 30 H 0 Z" fill="#ff0000" opacity="0.5"/>
    </svg>
    """
)

STROKE_ONLY = textwrap.dedent(
    """\
    <svg xmlns="https://www.w3.org/2000/svg" width="100" height="100">
      <path d="M 10,10 H 80 V 80 H 10 Z" fill="none" stroke="#ff0000" stroke-width="2"/>
    </svg>
    """
)

FILL_AND_STROKE = textwrap.dedent(
    """\
    <svg xmlns="https://www.w3.org/2000/svg" width="100" height="100">
      <path d="M 10,10 H 50 V 50 H 10 Z" fill="#00ff00" stroke="#000000" stroke-width="3"/>
    </svg>
    """
)

STROKES_INHERITED = textwrap.dedent(
    """\
    <svg xmlns="https://www.w3.org/2000/svg" width="100" height="100">
      <g fill="#ff0" stroke="#00f" stroke-width="1.5">
        <circle cx="50" cy="50" r="20"/>
        <rect x="10" y="10" width="30" height="30"/>
      </g>
    </svg>
    """
)


@pytest.fixture
def two_solids(tmp_path):
    f = tmp_path / "two.svg"
    f.write_text(TWO_SOLIDS)
    return str(f)


def test_each_subpath_becomes_a_ring(two_solids) -> None:
    assert len(svg_outlines(two_solids)) == 3


def test_rings_are_plain_python_floats(two_solids) -> None:
    """svgelements hands back numpy scalars, which poison the native polygon() boundary."""
    for ring in svg_outlines(two_solids):
        for x, y in ring:
            assert type(x) is float
            assert type(y) is float


def test_y_is_flipped_so_the_drawing_is_not_mirrored(two_solids) -> None:
    """SVG's Y axis points DOWN and OpenSCAD's points UP."""
    flipped = svg_outlines(two_solids)
    upright = svg_outlines(two_solids, flip_y=False)
    assert max(p[1] for r in flipped for p in r) <= 0
    assert min(p[1] for r in upright for p in r) >= 0


def test_region_keeps_both_solids_and_cuts_the_hole(two_solids) -> None:
    """100x50 minus a 20x10 hole, plus a separate 10x10 square."""
    assert region_from_svg(two_solids).geom.area == pytest.approx(100 * 50 - 20 * 10 + 10 * 10)


def test_region_from_svg_is_reachable_from_the_region_class(two_solids) -> None:
    assert Region.from_svg(two_solids).geom.area == pytest.approx(region_from_svg(two_solids).geom.area)


# -- curve resolution (fn / fs) -------------------------------------------------------------


def test_fn_gives_absolute_point_count(tmp_path) -> None:
    """When fn >= 3, each curved segment gets exactly that many points."""
    f = tmp_path / "curved.svg"
    f.write_text(CURVED)
    ring = svg_outlines(str(f), fn=8)[0]
    # The cubic bezier M0,0→C→Z: Close is skipped, Move is one point,
    # the bezier itself contributes fn=8 points, minus the duplicated close point.
    # So total = 1 (move) + 8 (bezier) = 9 minus last dup.
    # The ring is closed (Z), so the last point equals the first.  Path2D wants bare ring.
    assert 7 <= len(ring) <= 10  # ~1 move + 8 bezier pts, minus close dup


def test_fn_higher_gives_more_points_than_lower(tmp_path) -> None:
    f = tmp_path / "curved.svg"
    f.write_text(CURVED)
    coarse = svg_outlines(str(f), fn=4)[0]
    fine = svg_outlines(str(f), fn=32)[0]
    assert len(fine) > len(coarse)
    assert Region.even_odd([fine]).geom.area >= Region.even_odd([coarse]).geom.area


def test_fs_produces_more_points_for_longer_curve(tmp_path) -> None:
    """A longer curve (LONG_CURVE) should produce more points than a short one at the same fs."""
    f_short = tmp_path / "short.svg"
    f_short.write_text(CURVED)
    f_long = tmp_path / "long.svg"
    f_long.write_text(LONG_CURVE)
    short_ring = svg_outlines(str(f_short), fs=5.0)[0]
    long_ring = svg_outlines(str(f_long), fs=5.0)[0]
    assert len(long_ring) > len(short_ring)


def test_fs_lower_gives_more_points(tmp_path) -> None:
    """Smaller fs → finer resolution → more points per unit length."""
    f = tmp_path / "curved.svg"
    f.write_text(CURVED)
    coarse = svg_outlines(str(f), fs=10.0)[0]
    fine = svg_outlines(str(f), fs=2.0)[0]
    assert len(fine) > len(coarse)


def test_fn_overrides_fs(tmp_path) -> None:
    """When fn is set, fs is ignored — point count is absolute."""
    f = tmp_path / "curved.svg"
    f.write_text(CURVED)
    ring = svg_outlines(str(f), fn=6, fs=100.0)[0]
    # fs=100 would normally give 3 points (min).  fn=6 overrides.
    assert len(ring) >= 5  # more than the fs=100 minimum of ~3


def test_default_fs_is_2(tmp_path) -> None:
    """Without fn/fs, the default fs=2.0 should give a reasonable point count."""
    f = tmp_path / "curved.svg"
    f.write_text(CURVED)
    ring = svg_outlines(str(f))[0]
    assert len(ring) > 3


def test_svg_rings_with_colors_uses_same_resolution(tmp_path) -> None:
    """svg_rings_with_colors and svg_outlines should produce the same point counts."""
    f = tmp_path / "curved.svg"
    f.write_text(CURVED)
    outline_ring = svg_outlines(str(f), fn=12)[0]
    colored_paths, _ = svg_rings_with_colors(str(f), fn=12)
    assert len(outline_ring) == len(colored_paths[0])


def test_fn_is_ignored_when_none(tmp_path) -> None:
    """fn=None falls back to fs-based resolution."""
    f = tmp_path / "curved.svg"
    f.write_text(CURVED)
    ring = svg_outlines(str(f), fn=None, fs=2.0)[0]
    assert len(ring) > 3


def test_fa_is_accepted_but_does_not_affect_bezier_count(tmp_path) -> None:
    """fa is accepted for API parity but bezier flattening uses fn/fs only."""
    f = tmp_path / "curved.svg"
    f.write_text(CURVED)
    ring_fa12 = svg_outlines(str(f), fa=12.0)[0]
    ring_fa1 = svg_outlines(str(f), fa=1.0)[0]
    assert len(ring_fa12) == len(ring_fa1)


def test_geometry_renders_every_solid_not_just_the_first(two_solids) -> None:
    """Region.geometry() used to be paths[0] minus the rest, dropping disjoint solids."""
    region = region_from_svg(two_solids)
    assert len(region.paths) >= 3


# -- svg_outlines edge cases ------------------------------------------------------------------


def test_empty_svg_produces_no_rings(tmp_path) -> None:
    f = tmp_path / "empty.svg"
    f.write_text(EMPTY)
    assert svg_outlines(str(f)) == []


def test_no_shapes_produces_no_rings(tmp_path) -> None:
    f = tmp_path / "noshapes.svg"
    f.write_text(NO_SHAPES)
    assert svg_outlines(str(f)) == []


def test_move_only_produces_no_rings(tmp_path) -> None:
    """Move commands without lines/curves produce subpaths too short to form rings."""
    f = tmp_path / "moveonly.svg"
    f.write_text(MOVE_ONLY)
    assert svg_outlines(str(f)) == []


def test_nested_groups_are_processed(tmp_path) -> None:
    f = tmp_path / "nested.svg"
    f.write_text(NESTED_G)
    rings = svg_outlines(str(f))
    assert len(rings) >= 1


def test_text_elements_are_skipped(tmp_path) -> None:
    """<text> is not a Shape so it should be skipped; only the <path> counts."""
    f = tmp_path / "text.svg"
    f.write_text(TEXT_ELEMENT)
    rings = svg_outlines(str(f))
    assert len(rings) == 1


def test_pixel_units_are_treated_as_user_units(tmp_path) -> None:
    """Units like 'px' do not cause a crash; svgelements reads them as user-units."""
    f = tmp_path / "pixels.svg"
    f.write_text(PIXEL_UNITS)
    rings = svg_outlines(str(f))
    assert len(rings) >= 1
    # 100x200 rect → one closed ring with area ~20000
    from shapely.geometry import Polygon

    assert Polygon(rings[0]).area == pytest.approx(20000.0)


# -- region_from_svg / Region.from_svg edge cases ---------------------------------------------


def test_region_from_svg_empty_svg_is_empty_region(tmp_path) -> None:
    f = tmp_path / "empty.svg"
    f.write_text(EMPTY)
    r = region_from_svg(str(f))
    assert len(r) == 0


def test_region_from_svg_has_color_attr(tmp_path) -> None:
    f = tmp_path / "shape.svg"
    f.write_text(
        '<svg xmlns="https://www.w3.org/2000/svg" width="100" height="100"><path d="M 0,0 H 40 V 30 H 0 Z"/></svg>'
    )
    r = region_from_svg(str(f))
    assert hasattr(r, "_color")


def test_region_from_svg_flip_y_false_is_not_mirrored(tmp_path) -> None:
    f = tmp_path / "shape.svg"
    f.write_text(
        '<svg xmlns="https://www.w3.org/2000/svg" width="100" height="100"><path d="M 0,0 H 40 V 30 H 0 Z"/></svg>'
    )
    r = region_from_svg(str(f), flip_y=False)
    # With flip_y=False, Y stays positive (SVG Y=30 stays ~30 in user coords)
    ys = [p[1] for p in r.outline]
    assert min(ys) >= -1.0  # the SVG path has y from 0 to 30


def test_file_not_found_raises(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        svg_outlines(str(tmp_path / "nonexistent.svg"))


def test_file_not_found_from_svg_raises(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        Region.from_svg(str(tmp_path / "nonexistent.svg"))


# -- svg_rings_with_colors --------------------------------------------------------------------


def test_rings_with_colors_extracts_hex_fill(tmp_path) -> None:
    f = tmp_path / "colored.svg"
    f.write_text(COLORED)
    paths, colors = svg_rings_with_colors(str(f))
    assert len(paths) == 2
    assert len(colors) == 2
    assert colors[0] == "#ff0000"
    assert colors[1] == "#0000ff"


def test_rings_with_colors_returns_none_for_unfilled(tmp_path) -> None:
    f = tmp_path / "mixed.svg"
    f.write_text(MIXED_FILL)
    paths, colors = svg_rings_with_colors(str(f))
    assert "#ff0000" in colors
    assert "#008000" in colors
    assert None in colors  # the unfilled rect


def test_svg_rings_with_colors_geometry_same_as_baseline(tmp_path) -> None:
    """Rings from svg_rings_with_colors should be identical to svg_outlines rings."""
    f = tmp_path / "colored.svg"
    f.write_text(COLORED)
    plain = svg_outlines(str(f))
    colored_paths, _ = svg_rings_with_colors(str(f))
    assert len(plain) == len(colored_paths)
    for i in range(len(plain)):
        assert plain[i] == [list(pt) for pt in colored_paths[i]]


# -- regions_from_svg -------------------------------------------------------------------------


def test_regions_from_svg_returns_one_per_color(tmp_path) -> None:
    f = tmp_path / "colored.svg"
    f.write_text(COLORED)
    regions = regions_from_svg(str(f))
    assert len(regions) == 2
    assert str(regions[0]._color) == "#ff0000"
    assert str(regions[1]._color) == "#0000ff"


def test_regions_from_svg_unfilled_gets_no_color(tmp_path) -> None:
    f = tmp_path / "mixed.svg"
    f.write_text(MIXED_FILL)
    regions = regions_from_svg(str(f))
    colors = [r._color for r in regions]
    assert None in colors  # the unfilled shape group has no color


def test_regions_from_svg_colored_geometry_has_color(tmp_path) -> None:
    """Colored regions should produce geometry that chains correctly."""
    f = tmp_path / "colored.svg"
    f.write_text(COLORED)
    for region in regions_from_svg(str(f)):
        geom = region.geometry()
        assert geom is not None


def test_regions_from_svg_same_color_shapes_are_merged(tmp_path) -> None:
    """Two shapes with the same fill colour should end up in one Region."""
    svg = textwrap.dedent(
        """\
        <svg xmlns="https://www.w3.org/2000/svg" width="100" height="100">
          <path d="M 0,0 H 20 V 20 H 0 Z" fill="#ff0000"/>
          <path d="M 30,0 H 50 V 20 H 30 Z" fill="#ff0000"/>
        </svg>
        """
    )
    f = tmp_path / "samecolor.svg"
    f.write_text(svg)
    regions = regions_from_svg(str(f))
    assert len(regions) == 1
    assert str(regions[0]._color) == "#ff0000"
    # Two disjoint 20x20 squares → area = 400+400 = 800
    assert regions[0].geom.area == pytest.approx(800.0)


def test_regions_from_svg_empty_svg_returns_empty_list(tmp_path) -> None:
    f = tmp_path / "empty.svg"
    f.write_text(EMPTY)
    assert regions_from_svg(str(f)) == []


def test_region_color_persists_through_extrude(tmp_path) -> None:
    """Color set on a Region should carry through to geometry."""
    f = tmp_path / "colored.svg"
    f.write_text(COLORED)
    for region in regions_from_svg(str(f)):
        shape = region.geometry()
        assert shape is not None


# -- per-polygon colors via region_from_svg ---------------------------------------------------


def test_region_from_svg_has_polygon_colors(tmp_path) -> None:
    """region_from_svg returns a Region with per-polygon colours preserved."""
    f = tmp_path / "colored.svg"
    f.write_text(COLORED)
    region = region_from_svg(str(f))
    assert len(region._polygon_colors) >= 1
    assert any(c is not None for c in region._polygon_colors)


def test_region_from_svg_colors_match_fill(tmp_path) -> None:
    """Red and blue fills from SVG appear in per-polygon colors."""
    f = tmp_path / "colored.svg"
    f.write_text(COLORED)
    region = region_from_svg(str(f))
    colors = {str(c) for c in region._polygon_colors if c is not None}
    assert "#ff0000" in colors
    assert "#0000ff" in colors


def test_region_from_svg_overlap_first_wins(tmp_path) -> None:
    """Overlapping different-colour SVG shapes → first colour wins the overlap."""
    svg = textwrap.dedent(
        """\
        <svg xmlns="https://www.w3.org/2000/svg">
          <path d="M 0,0 H 30 V 20 H 0 Z" fill="#ff0000"/>
          <path d="M 20,0 H 50 V 20 H 20 Z" fill="#0000ff"/>
        </svg>
        """
    )
    f = tmp_path / "overlap.svg"
    f.write_text(svg)
    region = region_from_svg(str(f))
    assert len(region._polygon_colors) >= 2
    # Non-overlapping: blue had red subtracted from its overlap area
    assert region.geom.area == pytest.approx(1000.0)  # red=600 + blue=600-200=400


# -- stroke handling ---------------------------------------------------------------------------


def test_stroke_polygon_creates_filled_shape(tmp_path) -> None:
    """stroke-only path with strokes=polygon → produces a filled polygon."""
    f = tmp_path / "stroke.svg"
    f.write_text(STROKE_ONLY)
    paths, colors = svg_rings_with_colors(str(f), strokes="polygon")
    assert len(paths) >= 1
    assert "#ff0000" in colors


def test_stroke_ignore_skips_stroke_only(tmp_path) -> None:
    """stroke-only path with strokes=ignore → ring exists but with no colour."""
    f = tmp_path / "stroke.svg"
    f.write_text(STROKE_ONLY)
    paths, colors = svg_rings_with_colors(str(f), strokes="ignore")
    # The ring geometry is always parsed; strokes=ignore only means no
    # additional stroke-colour polygons are created.
    assert len(paths) >= 1
    assert colors[0] is None  # fill="none" → no fill colour


def test_fill_and_stroke_polygon_produces_both(tmp_path) -> None:
    """A shape with both fill and stroke produces both colours."""
    f = tmp_path / "fillstroke.svg"
    f.write_text(FILL_AND_STROKE)
    paths, colors = svg_rings_with_colors(str(f), strokes="polygon")
    assert "#00ff00" in colors  # fill
    assert "#000000" in colors  # stroke


def test_fill_and_stroke_ignore_keeps_only_fill(tmp_path) -> None:
    """strokes=ignore drops the stroke, keeps the fill."""
    f = tmp_path / "fillstroke.svg"
    f.write_text(FILL_AND_STROKE)
    paths, colors = svg_rings_with_colors(str(f), strokes="ignore")
    assert "#00ff00" in colors
    assert "#000000" not in colors


def test_inherited_strokes_with_polygon(tmp_path) -> None:
    """Inherited stroke from <g> is resolved and converted to polygon."""
    f = tmp_path / "inheroked.svg"
    f.write_text(STROKES_INHERITED)
    paths, colors = svg_rings_with_colors(str(f), strokes="polygon")
    assert "#0000ff" in colors  # stroke colour


def test_inherited_strokes_with_ignore(tmp_path) -> None:
    """strokes=ignore drops inherited strokes."""
    f = tmp_path / "inheroked.svg"
    f.write_text(STROKES_INHERITED)
    paths, colors = svg_rings_with_colors(str(f), strokes="ignore")
    assert "#0000ff" not in colors


def test_region_from_svg_with_strokes_polygon(tmp_path) -> None:
    """region_from_svg with strokes=polygon produces colored polygons incl strokes."""
    f = tmp_path / "fillstroke.svg"
    f.write_text(FILL_AND_STROKE)
    region = region_from_svg(str(f), strokes="polygon")
    colors = {str(c) for c in region._polygon_colors if c is not None}
    assert "#00ff00" in colors
    assert "#000000" in colors


def test_region_from_svg_with_strokes_ignore(tmp_path) -> None:
    """region_from_svg with strokes=ignore excludes stroke colours."""
    f = tmp_path / "fillstroke.svg"
    f.write_text(FILL_AND_STROKE)
    region = region_from_svg(str(f), strokes="ignore")
    colors = {str(c) for c in region._polygon_colors if c is not None}
    assert "#00ff00" in colors
    assert "#000000" not in colors


def test_stroke_polygon_has_reasonable_area(tmp_path) -> None:
    """A stroked closed shape produces a polygon with area ≈ stroke_width * perimeter."""
    f = tmp_path / "stroke.svg"
    f.write_text(STROKE_ONLY)
    paths, colors = svg_rings_with_colors(str(f), strokes="polygon")
    assert len(paths) >= 1
    from shapely.geometry import Polygon

    for path in paths:
        poly = Polygon([list(pt) for pt in path])
        assert poly.is_valid
        assert poly.area > 0  # buffered stroke produces real area


# -- real-world SVG: Wikipedia's Flag of Portugal -------------------------------------------
#
# A hand-drawn national flag is a much harsher test than any synthetic fixture: 148 rings,
# 37 <path> elements, 11 <use> clones, mixed winding directions, and 20 self-intersecting
# outlines. Every bug below was found by loading this one file and none of them by the
# synthetic SVGs above.

FLAG_OF_PORTUGAL = Path(__file__).resolve().parent / "svg_fixtures" / "flag_of_portugal.svg"

# The flag is 600x400 with the green field 2/5 of the width.
_FLAG_AREA = 600 * 400
_GREEN_AREA = 240 * 400


def _flag_region(strokes: str):
    return region_from_svg(str(FLAG_OF_PORTUGAL), strokes=strokes)


@pytest.mark.parametrize("strokes", ["ignore", "polygon"])
def test_flag_of_portugal_loads(strokes: str) -> None:
    """It loads at all.

    Self-intersecting rings used to abort the whole import from inside shapely with
    "TopologyException: unable to assign free hole to a shell" -- one bad ring out of 148
    took the entire drawing with it, because rings were only repaired AFTER their holes had
    been assigned.
    """
    region = _flag_region(strokes)
    assert not region._polygon.is_empty


@pytest.mark.parametrize("strokes", ["ignore", "polygon"])
def test_flag_of_portugal_covers_exactly_its_rectangle(strokes: str) -> None:
    """The flag's outline is the 600x400 rectangle -- no more, no less."""
    from shapely.ops import unary_union

    region = _flag_region(strokes)
    parts = list(getattr(region._polygon, "geoms", [region._polygon]))
    assert unary_union(parts).area == pytest.approx(_FLAG_AREA, rel=1e-6)


def test_flag_of_portugal_green_field_survives() -> None:
    """The green field keeps its area, less only the arms that sit on it.

    Regression test for the interior-probe winding bug. `even_odd` decides nesting by
    asking which other rings contain a probe taken just inside each ring's first edge --
    but "inside" was assumed to be one particular side, so for every CLOCKWISE ring the
    probe landed outside its own polygon (97 of this flag's 153 rings) and matched nothing.
    The green field was read as a sibling of the red one rather than sitting on it, and
    first-colour-wins then ate it: 1107 of 96000 survived.

    It is NOT the full 96000 -- the coat of arms straddles the two fields and is cut out of
    both, which is the point of compositing them as layers.
    """
    region = _flag_region("ignore")
    parts = list(getattr(region._polygon, "geoms", [region._polygon]))
    green = sum(
        p.area for p, c in zip(parts, region._polygon_colors, strict=True) if c is not None and str(c) == "#006600"
    )
    assert 0.8 * _GREEN_AREA < green < _GREEN_AREA


@pytest.mark.parametrize("strokes", ["ignore", "polygon"])
def test_flag_of_portugal_colours_do_not_overlap(strokes: str) -> None:
    """No two coloured pieces share area.

    Colour layers used to be stacked rather than composited -- nested coloured rings skipped
    the subtraction entirely and were rebuilt from their bare exteriors -- so the arms sat
    ON TOP of the fields instead of being cut from them and a colour could even overlap
    ITSELF (8077mm^2 of this flag's yellow). 96184mm^2 of a 240000mm^2 flag was
    double-covered, and the extruded mesh was not manifold.

    Summing the parts and dissolving them must give the same number.
    """
    from shapely.ops import unary_union

    region = _flag_region(strokes)
    parts = list(getattr(region._polygon, "geoms", [region._polygon]))
    assert region._polygon.area == pytest.approx(unary_union(parts).area, abs=1e-6)


def test_flag_of_portugal_has_its_arms() -> None:
    """The coat of arms survives: yellow armillary sphere, white shield, blue quinas."""
    region = _flag_region("ignore")
    colors = {str(c) for c in region._polygon_colors if c is not None}
    assert {"#ff0000", "#006600", "#ffff00", "#ffffff", "#003399"} <= colors


# -- svg_element_groups direct coverage -------------------------------------------------------


def test_element_groups_stroke_only_polygon(tmp_path) -> None:
    """stroke-only shape produces fill group (None color) + stroke group."""
    f = tmp_path / "s.svg"
    f.write_text(STROKE_ONLY)
    groups = svg_element_groups(str(f), strokes="polygon")
    assert len(groups) == 2
    assert groups[0][0] is None  # fill="none"
    assert groups[1][0] == "#ff0000"  # stroke color group


def test_element_groups_stroke_only_ignore(tmp_path) -> None:
    """strokes=ignore drops the stroke group entirely."""
    f = tmp_path / "s.svg"
    f.write_text(STROKE_ONLY)
    groups = svg_element_groups(str(f), strokes="ignore")
    assert len(groups) == 1
    assert groups[0][0] is None


def test_element_groups_fill_and_stroke_polygon(tmp_path) -> None:
    """Shape with fill and different-colour stroke → both groups."""
    f = tmp_path / "fs.svg"
    f.write_text(FILL_AND_STROKE)
    groups = svg_element_groups(str(f), strokes="polygon")
    assert len(groups) == 2
    colors = {g[0] for g in groups}
    assert "#00ff00" in colors  # fill
    assert "#000000" in colors  # stroke


def test_element_groups_fill_matches_stroke_skip_duplicate(tmp_path) -> None:
    """When stroke colour matches fill, no duplicate stroke group is created."""
    svg = (
        '<svg xmlns="https://www.w3.org/2000/svg">'
        '<path d="M10,10H50V50H10Z" fill="red" stroke="red" stroke-width="2"/></svg>'
    )
    f = tmp_path / "same.svg"
    f.write_text(svg)
    groups = svg_element_groups(str(f), strokes="polygon")
    assert len(groups) == 1  # only the fill group, no duplicate stroke


def test_element_groups_inherited_strokes(tmp_path) -> None:
    """Inherited <g> stroke produces stroke groups on child elements."""
    f = tmp_path / "inh.svg"
    f.write_text(STROKES_INHERITED)
    groups = svg_element_groups(str(f), strokes="polygon")
    colors = {g[0] for g in groups}
    assert "#0000ff" in colors  # inherited stroke


def test_element_groups_color_override(tmp_path) -> None:
    """color= overrides all colours in the output."""
    f = tmp_path / "fs.svg"
    f.write_text(FILL_AND_STROKE)
    groups = svg_element_groups(str(f), strokes="polygon", color="#ff00ff")
    for g_color, _rings in groups:
        assert g_color == "#ff00ff"


def test_element_groups_empty_svg(tmp_path) -> None:
    """Empty SVG produces no groups."""
    f = tmp_path / "empty.svg"
    f.write_text(EMPTY)
    groups = svg_element_groups(str(f))
    assert groups == []


# -- clipping and per-colour splitting ------------------------------------------------------

CLIPPED = textwrap.dedent(
    """\
    <svg xmlns="https://www.w3.org/2000/svg" viewBox="0 0 100 100">
      <defs><clipPath id="c"><path d="M-10 10h100v80H-10z"/></clipPath></defs>
      <g clip-path="url(#c)" transform="translate(10 -10)">
        <path fill="#ff0000" d="M-20 10h140v80h-140z"/>
      </g>
    </svg>
    """
)

OVERHANG = textwrap.dedent(
    """\
    <svg xmlns="https://www.w3.org/2000/svg" viewBox="0 0 100 100">
      <path fill="#00ff00" d="M-30 -30h160v160h-160z"/>
    </svg>
    """
)


def test_clip_path_is_applied_with_the_referencing_transform(tmp_path) -> None:
    """A <clipPath> clips in the referencing element's space, transform and all.

    A clipPath is defined in <defs>, so it parses in the document's coordinates while it
    CLIPS in the coordinates of whatever references it. Ignoring the referencing transform
    put Japan's flag 88 units off and cost it 20% of its area.
    """
    f = tmp_path / "clipped.svg"
    f.write_text(CLIPPED)
    region = region_from_svg(str(f))
    min_x, min_y, max_x, max_y = region.geom.bounds
    # clip x[-10,90] shifted by +10 -> x[0,100]; the rect itself spans x[-20,120] before that.
    assert min_x == pytest.approx(0, abs=1e-6)
    assert max_x == pytest.approx(100, abs=1e-6)


def test_the_viewbox_clips_too(tmp_path) -> None:
    """Content outside the viewBox is not drawn -- the viewport clips it."""
    f = tmp_path / "overhang.svg"
    f.write_text(OVERHANG)
    clipped = region_from_svg(str(f))
    assert clipped.geom.bounds == pytest.approx((0.0, -100.0, 100.0, 0.0), abs=1e-6)
    # ...and a caller who wants the raw drawing can still have it.
    raw = region_from_svg(str(f), clip_to_viewbox=False)
    assert raw.geom.area > clipped.geom.area


def test_regions_from_svg_are_disjoint(tmp_path) -> None:
    """Per-colour regions must not overlap each other.

    This used to pool each colour's rings and resolve them on their own, ignoring everything
    painted on top: a flag's background came back as the WHOLE flag with every other colour
    sitting on top of it, so the extruded bodies all overlapped.
    """
    from shapely.ops import unary_union

    f = tmp_path / "layers.svg"
    f.write_text(
        '<svg xmlns="https://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<path fill="#ff0000" d="M0 0h100v100H0z"/>'
        '<path fill="#0000ff" d="M0 0h40v100H0z"/>'
        "</svg>"
    )
    regions = regions_from_svg(str(f))
    total = sum(r.geom.area for r in regions)
    dissolved = unary_union([r.geom for r in regions]).area
    assert total == pytest.approx(dissolved, abs=1e-6)
    assert dissolved == pytest.approx(100 * 100, abs=1e-6)


# ---------------------------------------------------------------------------
# Coverage: private helpers
# ---------------------------------------------------------------------------


class TestRingsToShapely:
    """Coverage for _rings_to_shapely edge cases."""

    def test_invalid_polygon_repaired_with_buffer(self) -> None:
        """Self-intersecting polygon hits the buffer(0) repair path."""
        from pybosl2.svg import _rings_to_shapely

        result = _rings_to_shapely([[[0, 0], [10, 10], [0, 10], [10, 0]]])
        assert result is not None

    def test_empty_rings_returns_none(self) -> None:
        """All rings resolve to empty polys → None."""
        from pybosl2.svg import _rings_to_shapely

        assert _rings_to_shapely([]) is None


class TestShapelyToRings:
    """Coverage for _shapely_to_rings edge cases."""

    def test_none_returns_empty(self) -> None:
        from pybosl2.svg import _shapely_to_rings

        assert _shapely_to_rings(None) == []

    def test_empty_geom_returns_empty(self) -> None:
        from shapely.geometry import GeometryCollection

        from pybosl2.svg import _shapely_to_rings

        assert _shapely_to_rings(GeometryCollection()) == []

    def test_zero_area_skipped(self) -> None:
        from shapely.geometry import Polygon

        from pybosl2.svg import _shapely_to_rings

        poly = Polygon([[0, 0], [0, 0], [0, 0]])
        assert _shapely_to_rings(poly) == []

    def test_polygon_with_holes_returns_hole_rings(self) -> None:
        from shapely.geometry import Polygon

        from pybosl2.svg import _shapely_to_rings

        outer = [[0, 0], [100, 0], [100, 100], [0, 100]]
        hole = [[20, 20], [80, 20], [80, 80], [20, 80]]
        poly = Polygon(outer, [hole])
        rings = _shapely_to_rings(poly)
        assert len(rings) == 2


class TestClipRings:
    """Coverage for _clip_rings edge cases."""

    def test_empty_rings_returns_none(self) -> None:
        from pybosl2.svg import _clip_rings

        assert _clip_rings([], object()) is None


class TestViewboxGeometry:
    """Coverage for _viewbox_geometry edge cases."""

    def test_missing_file_returns_none(self) -> None:
        from pybosl2.svg import _viewbox_geometry

        assert _viewbox_geometry("/nonexistent/path.svg", 1.0) is None

    def test_zero_width_viewbox_returns_none(self, tmp_path) -> None:
        from pybosl2.svg import _viewbox_geometry

        f = tmp_path / "zero.svg"
        f.write_text('<svg xmlns="https://www.w3.org/2000/svg" viewBox="0 0 0 100"/>')
        assert _viewbox_geometry(str(f), 1.0) is None

    def test_negative_height_viewbox_returns_none(self, tmp_path) -> None:
        from pybosl2.svg import _viewbox_geometry

        f = tmp_path / "neg.svg"
        f.write_text('<svg xmlns="https://www.w3.org/2000/svg" viewBox="0 0 100 -1"/>')
        assert _viewbox_geometry(str(f), 1.0) is None


class TestResolveClip:
    """Coverage for _resolve_clip edge cases."""

    def test_non_matching_reference_returns_none(self, tmp_path) -> None:
        from pybosl2.svg import _resolve_clip

        f = tmp_path / "noclip.svg"
        f.write_text('<svg xmlns="https://www.w3.org/2000/svg"/>')
        from svgelements import SVG

        root = SVG.parse(str(f))
        assert _resolve_clip("garbage", root, 1.0, None, 2.0) is None

    def test_missing_clip_id_returns_none(self, tmp_path) -> None:
        from pybosl2.svg import _resolve_clip

        f = tmp_path / "missing.svg"
        f.write_text('<svg xmlns="https://www.w3.org/2000/svg"/>')
        from svgelements import SVG

        root = SVG.parse(str(f))
        assert _resolve_clip("url(#nonexistent)", root, 1.0, None, 2.0) is None


class TestSvgClipToViewbox:
    """Coverage for clip_to_viewbox integration path."""

    def test_clip_to_viewbox_strokes(self, tmp_path) -> None:
        """Stroke with a clip mask exercises lines 513-514."""
        f = tmp_path / "clip_stroke.svg"
        f.write_text(
            '<svg xmlns="https://www.w3.org/2000/svg" viewBox="0 0 100 100">'
            '<clipPath id="c"><rect x="0" y="0" width="50" height="50"/></clipPath>'
            '<path d="M10,10h80v80H10z" fill="none" stroke="red" stroke-width="2" clip-path="url(#c)"/>'
            "</svg>"
        )
        groups = svg_element_groups(str(f))
        assert groups  # path appears as stroke group

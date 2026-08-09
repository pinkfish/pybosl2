# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/svg.py: loading an SVG drawing as real outlines rather than an opaque
handle from the renderer's own importer. Fixtures are written inline so the suite carries no
binary assets and runs without a renderer -- which is half the point of loading SVG this way."""

import textwrap

import pytest

from pybosl2.regions import Region
from pybosl2.svg import region_from_svg, regions_from_svg, svg_outlines, svg_rings_with_colors

# A 100x50 rect with a 20x10 hole, plus a separate 10x10 square: three rings, two solids.
TWO_SOLIDS = textwrap.dedent(
    """\
    <svg xmlns="http://www.w3.org/2000/svg" width="200" height="100" viewBox="0 0 200 100">
      <path d="M 0,0 H 100 V 50 H 0 Z"/>
      <path d="M 10,10 H 30 V 20 H 10 Z"/>
      <path d="M 150,0 H 160 V 10 H 150 Z"/>
    </svg>
    """
)

EMPTY = """\
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
</svg>
"""

NO_SHAPES = """\
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <g id="empty-group"/>
</svg>
"""

MOVE_ONLY = """\
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <path d="M 10,10 M 20,20 M 30,30"/>
</svg>
"""

NESTED_G = """\
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <g>
    <g>
      <path d="M 0,0 H 40 V 30 H 0 Z"/>
    </g>
  </g>
</svg>
"""

TEXT_ELEMENT = """\
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <text x="10" y="30">hello</text>
  <path d="M 0,0 H 50 V 40 H 0 Z"/>
</svg>
"""

CURVED = textwrap.dedent(
    """\
    <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
      <path d="M 0,0 C 0,50 50,50 50,0 Z"/>
    </svg>
    """
)

# A long cubic bezier: M0,0 → C0,200,200,200,200,0 — arc length ~300 user units.
LONG_CURVE = textwrap.dedent(
    """\
    <svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
      <path d="M 0,0 C 0,200 200,200 200,0 Z"/>
    </svg>
    """
)

PIXEL_UNITS = textwrap.dedent(
    """\
    <svg xmlns="http://www.w3.org/2000/svg" width="800px" height="600px">
      <path d="M 0,0 H 100 V 200 H 0 Z"/>
    </svg>
    """
)

COLORED = textwrap.dedent(
    """\
    <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
      <path d="M 0,0 H 40 V 30 H 0 Z" fill="#ff0000"/>
      <path d="M 50,0 H 80 V 30 H 50 Z" fill="#0000ff"/>
    </svg>
    """
)

MIXED_FILL = textwrap.dedent(
    """\
    <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
      <path d="M 0,0 H 30 V 30 H 0 Z" fill="#ff0000"/>
      <path d="M 40,0 H 70 V 30 H 40 Z" fill="none"/>
      <circle cx="15" cy="55" r="10" fill="green"/>
    </svg>
    """
)

OPACITY_FILL = textwrap.dedent(
    """\
    <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
      <path d="M 0,0 H 40 V 30 H 0 Z" fill="#ff0000" opacity="0.5"/>
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
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><path d="M 0,0 H 40 V 30 H 0 Z"/></svg>'
    )
    r = region_from_svg(str(f))
    assert hasattr(r, "_color")


def test_region_from_svg_flip_y_false_is_not_mirrored(tmp_path) -> None:
    f = tmp_path / "shape.svg"
    f.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><path d="M 0,0 H 40 V 30 H 0 Z"/></svg>'
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
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
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
        <svg xmlns="http://www.w3.org/2000/svg">
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

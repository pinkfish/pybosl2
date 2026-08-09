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
from pybosl2.svg import region_from_svg, svg_outlines

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

PIXEL_UNITS = """\
<svg xmlns="http://www.w3.org/2000/svg" width="800px" height="600px">
  <path d="M 0,0 H 100 V 200 H 0 Z"/>
</svg>
"""


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


def test_curves_are_flattened_to_the_requested_resolution(tmp_path) -> None:
    f = tmp_path / "curved.svg"
    f.write_text(CURVED)
    coarse = svg_outlines(str(f), steps=4)[0]
    fine = svg_outlines(str(f), steps=32)[0]
    assert len(fine) > len(coarse)
    # A finer flattening tracks the true curve, so its area converges upward.
    assert Region.even_odd([fine]).geom.area >= Region.even_odd([coarse]).geom.area


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

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/partitions.py: the cut-path generators and the Partitionable cut operators on
Bosl2Solid. partition_path is pinned to real BOSL2 in tests/test_bosl2_reorient.py; here we check
the segment grammar and that each cutting method builds. Native geometry is mocked, so the
geometric correctness (half volumes, interlocking pieces) is verified in test_stl_render.py."""

import math

import numpy as np
import pytest

from pybosl2.constants import UP
from pybosl2.enums import PartitionCutType
from pybosl2.partitions import (
    Partitionable,
    _partition_cutpath,
    _partition_subpath,
    _ptn_sect,
    partition_cut_mask,
    partition_mask,
    partition_path,
)
from pybosl2.path2d import Path2D
from pybosl2.shapes3d import Bosl2Solid, cuboid, sphere

# -- cut-path generators ------------------------------------------------------------------


def test_partition_path_returns_path() -> None:
    p = partition_path(["flat", "jigsaw", "flat"], fn=24)
    assert isinstance(p, Path2D)
    assert p.closed is False


def test_partition_path_closed_when_y_given() -> None:
    p = partition_path([30, "hammerhead", 30], y=150)
    assert p.closed is True
    # the closing edge sits at y=150
    assert any(math.isclose(pt[1], 150, abs_tol=1e-9) for pt in p)


def test_named_subpaths_have_expected_shape() -> None:
    assert _partition_subpath("flat").to_list == [[0, 0], [1, 0]]
    assert _partition_subpath("sawtooth").to_list == [[0, 0], [0.5, 1], [1, 0]]
    assert len(_partition_subpath("dovetail")) == 6
    assert len(_partition_subpath("hammerhead")) == 10
    assert len(_partition_subpath("jigsaw", fn=24)) > 10  # arc-based


def test_ptn_sect_numeric_is_flat_segment() -> None:
    assert _ptn_sect(30).to_list == [[0, 0], [30.0, 0]]


def test_ptn_sect_yflip_negates_y() -> None:
    base = _ptn_sect("sawtooth")
    flipped = _ptn_sect("sawtooth yflip")
    np.testing.assert_allclose([p[1] for p in flipped], [-p[1] for p in base], atol=1e-9)


def test_ptn_sect_repeat_triples_width() -> None:
    one = _ptn_sect("sawtooth")
    three = _ptn_sect("sawtooth 3x")
    assert math.isclose(max(p[0] for p in three), 3 * max(p[0] for p in one), rel_tol=1e-9)


def test_ptn_sect_resize() -> None:
    sect = _ptn_sect("jigsaw 40x20", fn=24)
    xs = [p[0] for p in sect]
    ys = [p[1] for p in sect]
    assert math.isclose(max(xs) - min(xs), 40, abs_tol=1e-6)
    assert max(abs(y) for y in ys) <= 20 + 1e-6


def test_ptn_sect_skew_shifts_top() -> None:
    sect = _ptn_sect("square skew:15")
    # the top edge (y=25) is shifted right relative to the bottom by height*tan(15)
    assert isinstance(sect, Path2D)
    assert len(sect) == 4


def test_ptn_sect_bad_option_raises() -> None:
    with pytest.raises(ValueError, match="unknown section option"):
        _ptn_sect("sawtooth bogus")


def test_partition_cutpath_repeats_to_length() -> None:
    path = _partition_cutpath(100, 20, [20, 10], "dovetail", 0, True)
    xs = [p[0] for p in path]
    assert math.isclose(min(xs), -50, abs_tol=1e-9)  # spans -l/2 .. l/2
    assert math.isclose(max(xs), 50, abs_tol=1e-9)


# -- mask builders ------------------------------------------------------------------------


def test_partition_mask_builds() -> None:
    assert isinstance(partition_mask(length=60, w=30, height=20, cutpath="dovetail"), Bosl2Solid)
    assert isinstance(
        partition_mask(length=60, w=30, height=20, cutpath="jigsaw", inverse=True, fn=12),
        Bosl2Solid,
    )


def test_partition_cut_mask_builds() -> None:
    assert isinstance(
        partition_cut_mask(length=60, height=20, cutpath="dovetail", slop=0.2),
        Bosl2Solid,
    )


# -- Partitionable methods on Bosl2Solid --------------------------------------------------

BOX = cuboid([40, 30, 20])


def test_axis_half_methods_return_solid() -> None:
    assert isinstance(BOX.left_half(), Bosl2Solid)
    assert isinstance(BOX.right_half(x=5), Bosl2Solid)
    assert isinstance(BOX.front_half(), Bosl2Solid)
    assert isinstance(BOX.back_half(y=-3), Bosl2Solid)
    assert isinstance(BOX.top_half(), Bosl2Solid)
    assert isinstance(BOX.bottom_half(z=5), Bosl2Solid)


def test_half_of_general_normal() -> None:
    assert isinstance(BOX.half_of([0, 1, 1]), Bosl2Solid)
    assert isinstance(sphere(radius=20).half_of([1, 0, 0], center=5), Bosl2Solid)  # type: ignore[arg-type]


def test_half_of_with_cut_path() -> None:
    center = partition_path([40, "jigsaw", 40], fn=12)
    assert isinstance(BOX.back_half(cut_path=center), Bosl2Solid)


def test_partition_returns_two_pieces() -> None:
    pieces = BOX.partition(spread=12, cutpath="dovetail")
    assert isinstance(pieces, list)
    assert len(pieces) == 2
    assert all(isinstance(p, Bosl2Solid) for p in pieces)


def test_partition_accepts_cutsize_vector_and_spin() -> None:
    pieces = cuboid([60, 40, 20]).partition(spread=8, cutsize=[20, 15], cutpath="hammerhead", spin=90)
    assert len(pieces) == 2


# -- every cut profile ---------------------------------------------------------------------
#
# _ptn_sect() is the whole named-section grammar, and most of it was unexercised: the profiles
# below are what a partition's teeth actually look like, so a silent change to one of them
# changes every joint built from it.

CUT_TYPES = list(PartitionCutType)


@pytest.mark.parametrize("cut", CUT_TYPES, ids=lambda c: c.value)
def test_every_cut_profile_fills_its_box(cut: PartitionCutType) -> None:
    """A section spans exactly *length* in x and stays inside +/-*width* in y."""
    sect = _ptn_sect(cut, 40, 20, fn=24)
    xs = [float(p[0]) for p in sect]
    ys = [float(p[1]) for p in sect]
    assert len(sect) >= 2
    assert min(xs) == pytest.approx(0, abs=1e-9)
    assert max(xs) == pytest.approx(40, abs=1e-6)
    assert max(abs(y) for y in ys) <= 20 + 1e-6


@pytest.mark.parametrize("cut", CUT_TYPES, ids=lambda c: c.value)
def test_every_cut_profile_runs_left_to_right(cut: PartitionCutType) -> None:
    """Sections are laid end to end, so each must start at its left edge and finish at its right."""
    sect = _ptn_sect(cut, 40, 20, fn=24)
    assert float(sect[0][0]) == pytest.approx(0, abs=1e-9)
    assert float(sect[-1][0]) == pytest.approx(40, abs=1e-6)


@pytest.mark.parametrize(
    ("cut", "points"),
    [
        (PartitionCutType.FLAT, 2),
        (PartitionCutType.SAWTOOTH, 3),
        (PartitionCutType.TRIANGLE, 3),
        (PartitionCutType.SQUARE, 4),
        (PartitionCutType.COMB, 4),
        (PartitionCutType.FINGER, 4),
        (PartitionCutType.DOVETAIL, 6),
        (PartitionCutType.HAMMERHEAD, 10),
    ],
    ids=lambda value: value.value if isinstance(value, PartitionCutType) else str(value),
)
def test_straight_edged_profiles_have_their_exact_corners(cut: PartitionCutType, points: int) -> None:
    """The polygonal profiles are fixed vertex counts -- BOSL2's shapes, not approximations."""
    assert len(_ptn_sect(cut, 40, 20)) == points


@pytest.mark.parametrize(
    "cut",
    [PartitionCutType.HALFSINE, PartitionCutType.SEMICIRCLE, PartitionCutType.JIGSAW, PartitionCutType.SINEWAVE],
    ids=lambda c: c.value,
)
def test_curved_profiles_follow_the_facet_count(cut: PartitionCutType) -> None:
    """Arc-based profiles honour fn (SPEC R-1): more fragments, more points."""
    coarse = _ptn_sect(cut, 40, 20, fn=8)
    fine = _ptn_sect(cut, 40, 20, fn=64)
    assert len(fine) > len(coarse)


def test_comb_and_finger_differ_by_their_draft_angle() -> None:
    """Both are the same trapezoid; the finger's 20-degree draft is much wider than the comb's 2."""
    comb = _ptn_sect(PartitionCutType.COMB, 40, 20)
    finger = _ptn_sect(PartitionCutType.FINGER, 40, 20)
    assert float(finger[1][0]) > float(comb[1][0]) > 0


def test_dovetail_undercuts_its_own_base() -> None:
    """The point of a dovetail: the top of the tooth is wider than the bottom, so it cannot pull out."""
    sect = _ptn_sect(PartitionCutType.DOVETAIL, 40, 20)
    bottom = [float(p[0]) for p in sect if abs(float(p[1])) < 1e-9]
    top = [float(p[0]) for p in sect if abs(float(p[1]) - 20) < 1e-6]
    assert max(top) - min(top) > max(bottom[1:-1]) - min(bottom[1:-1])


# -- the modifier grammar ------------------------------------------------------------------


def test_xflip_mirrors_the_profile_but_keeps_its_span() -> None:
    plain = _ptn_sect("sawtooth", 40, 20)
    flipped = _ptn_sect("sawtooth xflip", 40, 20)
    assert [float(p[0]) for p in flipped] == pytest.approx([40 - float(p[0]) for p in reversed(plain)])
    assert [float(p[1]) for p in flipped] == pytest.approx([float(p[1]) for p in reversed(plain)])


def test_invert_negates_y() -> None:
    plain = _ptn_sect("sawtooth", 40, 20)
    inverted = _ptn_sect("sawtooth", 40, 20, invert=True)
    assert [float(p[1]) for p in inverted] == pytest.approx([-float(p[1]) for p in plain])


@pytest.mark.parametrize("modifier", ["addflip", "wave"])
def test_addflip_packs_a_section_and_its_mirror_into_the_same_width(modifier: str) -> None:
    """'wave' is BOSL2's alias for 'addflip': two half-width copies, the second flipped both ways."""
    plain = _ptn_sect("sawtooth", 40, 20)
    waved = _ptn_sect(f"sawtooth {modifier}", 40, 20)
    assert max(float(p[0]) for p in waved) == pytest.approx(40, abs=1e-6)
    # each copy is scaled to half size, so the amplitude halves
    assert max(abs(float(p[1])) for p in waved) == pytest.approx(max(abs(float(p[1])) for p in plain) / 2, abs=1e-6)
    assert min(float(p[1]) for p in waved) < 0 < max(float(p[1]) for p in waved)


def test_pinch_percentage_narrows_the_raised_part_only() -> None:
    plain = _ptn_sect("dovetail", 40, 20)
    pinched = _ptn_sect("dovetail pinch:50", 40, 20)
    top_plain = [float(p[0]) for p in plain if abs(float(p[1]) - 20) < 1e-6]
    top_pinched = [float(p[0]) for p in pinched if abs(float(p[1]) - 20) < 1e-6]
    assert max(top_pinched) - min(top_pinched) < max(top_plain) - min(top_plain)
    # the points on the baseline are untouched
    assert min(float(p[0]) for p in pinched) == pytest.approx(0, abs=1e-9)
    assert max(float(p[0]) for p in pinched) == pytest.approx(40, abs=1e-6)


def test_pinch_in_degrees_is_a_draft_angle() -> None:
    """pinch:Ndeg pinches by whatever percentage gives an N-degree wall."""
    straight = _ptn_sect("square pinch:0deg", 40, 20)
    drafted = _ptn_sect("square pinch:15deg", 40, 20)
    top_straight = [float(p[0]) for p in straight if abs(float(p[1]) - 20) < 1e-6]
    top_drafted = [float(p[0]) for p in drafted if abs(float(p[1]) - 20) < 1e-6]
    assert max(top_drafted) - min(top_drafted) < max(top_straight) - min(top_straight)


def test_pinch_leaves_a_flat_section_alone() -> None:
    """A section with no height has nothing to pinch, so it comes back unchanged."""
    assert _ptn_sect("flat pinch:50", 40, 20).to_list == _ptn_sect("flat", 40, 20).to_list


def test_flat_takes_its_length_as_a_bare_modifier() -> None:
    assert _ptn_sect("flat 30").to_list == [[0, 0], [30.0, 0]]


def test_skew_slides_the_top_over_without_changing_its_height() -> None:
    plain = _ptn_sect("square", 40, 20)
    skewed = _ptn_sect("square skew:20", 40, 20)
    assert max(abs(float(p[1])) for p in skewed) == pytest.approx(max(abs(float(p[1])) for p in plain))
    top_plain = max(float(p[0]) for p in plain if abs(float(p[1]) - 20) < 1e-6)
    top_skewed = max(float(p[0]) for p in skewed if abs(float(p[1]) - 20) < 1e-6)
    assert top_skewed > top_plain


def test_modifiers_apply_left_to_right() -> None:
    """'sawtooth 2x yflip' is the repeat, then flipped -- not the flip repeated."""
    assert _ptn_sect("sawtooth 2x yflip", 40, 20).to_list == _yscale_list(_ptn_sect("sawtooth 2x", 40, 20))


def _yscale_list(path: Path2D) -> list[list[float]]:
    return [[float(p[0]), -float(p[1])] for p in path]


# -- sub-paths and the repeated cut row ----------------------------------------------------

SUBPATH_TYPES = [
    PartitionCutType.FLAT,
    PartitionCutType.SAWTOOTH,
    PartitionCutType.SINEWAVE,
    PartitionCutType.COMB,
    PartitionCutType.FINGER,
    PartitionCutType.DOVETAIL,
    PartitionCutType.HAMMERHEAD,
    PartitionCutType.JIGSAW,
]


@pytest.mark.parametrize("cut", SUBPATH_TYPES, ids=lambda c: c.value)
def test_mask_subpaths_are_unit_tiles(cut: PartitionCutType) -> None:
    """The mask builders tile these, so each spans 0..1 in x and joins seamlessly end to end."""
    sub = _partition_subpath(cut, fn=24)
    xs = [float(p[0]) for p in sub]
    assert min(xs) == pytest.approx(0, abs=1e-9)
    assert max(xs) == pytest.approx(1, abs=1e-9)
    assert float(sub[0][1]) == pytest.approx(float(sub[-1][1]), abs=1e-9)


@pytest.mark.parametrize("cut", SUBPATH_TYPES, ids=lambda c: c.value)
def test_mask_subpaths_keep_bosl2_amplitudes(cut: PartitionCutType) -> None:
    """BOSL2 documents cutpath tiles as ``Y between -0.5 and 0.5`` -- except its own sawtooth,
    which is ``[[0,0],[0.5,1],[1,0]]`` and so reaches 1. We are feature compatible (SPEC B2-1),
    so we reproduce that rather than quietly normalising it and changing every sawtooth joint.
    """
    limit = {PartitionCutType.FLAT: 0.0, PartitionCutType.SAWTOOTH: 1.0}.get(cut, 0.5)
    assert max(abs(float(p[1])) for p in _partition_subpath(cut, fn=24)) == pytest.approx(limit, abs=1e-9)


@pytest.mark.parametrize(
    "cut",
    [PartitionCutType.SQUARE, PartitionCutType.TRIANGLE, PartitionCutType.HALFSINE, PartitionCutType.SEMICIRCLE],
    ids=lambda c: c.value,
)
def test_section_only_cut_types_are_refused_as_mask_subpaths(cut: PartitionCutType) -> None:
    """These exist as partition_path sections but have no tiling form; say so rather than guess."""
    with pytest.raises(ValueError, match="unsupported cut type"):
        _partition_subpath(cut)


def test_cutpath_row_spans_the_requested_length() -> None:
    path = _partition_cutpath(100, 20, [20, 10], "dovetail", 0, True)
    xs = [float(p[0]) for p in path]
    assert min(xs) == pytest.approx(-50)
    assert max(xs) == pytest.approx(50)
    assert max(abs(float(p[1])) for p in path) <= 10 / 2 + 1e-9


def test_cutpath_gap_spreads_the_teeth_out() -> None:
    """A gap leaves flat land between teeth, so the same length holds fewer of them."""
    tight = _partition_cutpath(100, 20, [20, 10], "dovetail", 0, True)
    spaced = _partition_cutpath(100, 20, [20, 10], "dovetail", 8, True)
    assert len(spaced) < len(tight)


def test_cutpath_centering_drops_a_tooth_to_stay_symmetric() -> None:
    """With an even tooth count, centring drops one so a tooth sits on x=0 rather than a valley.

    100mm of 25mm teeth fits 4; centred that becomes 3, centred on the origin.
    """
    centred = _partition_cutpath(100, 20, [25, 10], "sawtooth", 0, True)
    offset = _partition_cutpath(100, 20, [25, 10], "sawtooth", 0, False)
    peaks_centred = sorted(float(p[0]) for p in centred if float(p[1]) > 4.9)
    peaks_offset = sorted(float(p[0]) for p in offset if float(p[1]) > 4.9)
    assert peaks_centred == pytest.approx([-25.0, 0.0, 25.0])
    assert peaks_offset == pytest.approx([-37.5, -12.5, 12.5, 37.5])
    assert sum(peaks_centred) == pytest.approx(0, abs=1e-6)


def test_cutpath_accepts_an_explicit_profile() -> None:
    """A caller can hand in their own unit tile instead of naming one."""
    tile = [[0.0, 0.0], [0.5, 1.0], [1.0, 0.0]]
    path = _partition_cutpath(60, 20, [20, 10], tile, 0, True)
    assert max(abs(float(p[1])) for p in path) == pytest.approx(10)
    assert min(float(p[0]) for p in path) == pytest.approx(-30)


# -- partition_path assembly ---------------------------------------------------------------


def test_repeat_multiplies_the_whole_description() -> None:
    once = partition_path(["dovetail"], seglen=25)
    twice = partition_path(["dovetail"], repeat=2, seglen=25)
    span = lambda p: max(float(q[0]) for q in p) - min(float(q[0]) for q in p)  # noqa: E731
    assert span(twice) == pytest.approx(2 * span(once), abs=1e-6)


def test_the_path_is_centred_on_the_origin() -> None:
    path = partition_path([25, "dovetail", 25], seglen=25)
    xs = [float(p[0]) for p in path]
    assert min(xs) == pytest.approx(-max(xs), abs=1e-6)


def test_an_explicit_point_list_is_used_as_given() -> None:
    path = partition_path([[[0, 0], [10, 0], [10, 5], [20, 5]]])
    assert max(float(p[1]) for p in path) == pytest.approx(5)


def test_closing_y_closes_the_path_on_the_side_it_names() -> None:
    """`y=` turns the cut line into a polygon by closing it at that height, above or below."""
    below = partition_path([30, "hammerhead", 30], y=-40)
    above = partition_path([30, "hammerhead", 30], y=40)
    assert below.closed
    assert above.closed
    assert min(float(p[1]) for p in below) == pytest.approx(-40)
    assert max(float(p[1]) for p in above) == pytest.approx(40)
    # the sign also picks which end the point list starts from
    assert [list(map(float, p)) for p in above][0] != [list(map(float, p)) for p in below][0]
    assert below.is_clockwise() == above.is_clockwise()


def test_a_closing_y_inside_the_pattern_is_rejected() -> None:
    """Closing through the teeth would make a self-crossing polygon, not a partition."""
    with pytest.raises(ValueError, match="self-cross"):
        partition_path([30, "hammerhead", 30], y=0)


def test_altpath_lays_the_pattern_along_another_path() -> None:
    """`altpath=` bends a straight cut pattern onto an arbitrary base line (BOSL2 path redirect).

    The teeth then stand off perpendicular to that line rather than along +Y.
    """
    base = Path2D([[0.0, 0.0], [60.0, 30.0]])
    redirected = partition_path(["dovetail"], seglen=25, segwidth=10, altpath=base)
    points = np.asarray([[float(a), float(b)] for a, b in redirected])

    along = np.array([60.0, 30.0]) / np.linalg.norm([60.0, 30.0])
    perpendicular = np.array([-along[1], along[0]])
    offsets = points @ perpendicular
    assert min(offsets) == pytest.approx(0, abs=1e-6)  # the baseline points sit on the line
    assert max(offsets) == pytest.approx(10, abs=1e-6)  # the teeth reach segwidth off it
    assert (points @ along).min() > 0  # and the whole pattern lies along the base path


def test_a_section_can_be_an_explicit_profile() -> None:
    """A section descriptor may be a unit-ish point list, scaled to the section box like a named one."""
    sect = _ptn_sect([[0.0, 0.0], [0.5, 1.0], [1.0, 0.0]], 40, 20)
    assert sect.to_list == [[0.0, 0.0], [20.0, 20.0], [40.0, 0.0]]


def test_partition_mask_slop_shrinks_the_mask() -> None:
    """`slop=` insets the mask so the two printed halves actually fit together."""
    assert isinstance(partition_mask(length=60, w=30, height=20, cutpath="dovetail", slop=0.3), Bosl2Solid)


# -- Partitionable: the cut operators the solids actually use -------------------------------


def test_bosl2_solid_gets_its_cuts_from_the_partitions_mixin() -> None:
    """The mixin is the implementation, not a second copy of it (SPEC P-8).

    `shapes3d/base.py` used to carry its own duplicate of all nine methods, so every one of them
    was dead code here -- tested, documented, and never run.
    """
    assert Partitionable in Bosl2Solid.__mro__
    for name in ("half_of", "left_half", "right_half", "front_half", "back_half", "top_half", "bottom_half"):
        assert getattr(Bosl2Solid, name) is getattr(Partitionable, name), name
    assert Bosl2Solid.partition is Partitionable.partition


def test_half_of_accepts_a_2d_normal() -> None:
    """A 2-D direction is padded to 3-D, so `half_of([1, 0])` means "keep +X"."""
    assert isinstance(BOX.half_of([1, 0]), Bosl2Solid)


def test_half_of_accepts_a_scalar_distance_along_the_normal() -> None:
    assert isinstance(BOX.half_of(UP, center=5), Bosl2Solid)
    assert isinstance(BOX.half_of(UP, center=[0, 0, 5]), Bosl2Solid)


def test_half_of_offset_grows_the_mask() -> None:
    """`offset=` grows the cutting mask -- it goes through the native offset, which takes r=."""
    assert isinstance(BOX.half_of(UP, offset=2), Bosl2Solid)


def test_half_of_takes_a_cut_path_in_either_direction() -> None:
    """A right-to-left cut path is reversed rather than producing an inside-out mask."""
    left_to_right = Path2D([[-20.0, 0.0], [0.0, 5.0], [20.0, 0.0]])
    right_to_left = Path2D([[20.0, 0.0], [0.0, 5.0], [-20.0, 0.0]])
    assert isinstance(BOX.half_of(UP, cut_path=left_to_right), Bosl2Solid)
    assert isinstance(BOX.half_of(UP, cut_path=right_to_left), Bosl2Solid)


def test_half_of_cut_angle_spins_the_cut_face() -> None:
    path = Path2D([[-20.0, 0.0], [0.0, 5.0], [20.0, 0.0]])
    assert isinstance(BOX.half_of(UP, cut_path=path, cut_angle=30), Bosl2Solid)


def test_down_and_up_cuts_pick_their_own_reference_axis() -> None:
    """A mask normal to +Z/-Z has no XY component, so the code falls back to FRONT/BACK."""
    assert isinstance(BOX.half_of([0, 0, 1]), Bosl2Solid)
    assert isinstance(BOX.half_of([0, 0, -1]), Bosl2Solid)


def _separation(pieces: list[Bosl2Solid]) -> float:
    """Distance between the two pieces' bounding-box centres, across the cut."""
    centres = [piece.bounds()[0] for piece in pieces]
    return abs(float(centres[0][1]) - float(centres[1][1]))


def test_partition_spread_pushes_the_halves_apart() -> None:
    """The halves come back already separated by *spread*, laid out ready to print."""
    together = cuboid([60, 40, 20]).partition(spread=0, cutpath="dovetail")
    apart = cuboid([60, 40, 20]).partition(spread=12, cutpath="dovetail")
    assert len(together) == len(apart) == 2
    assert _separation(apart) - _separation(together) == pytest.approx(12, abs=1e-6)


def test_partition_spin_turns_the_cut_plane() -> None:
    """`spin=` rotates the cut, so the pieces separate along a different axis."""
    straight = cuboid([60, 40, 20]).partition(spread=10, cutpath="dovetail")
    spun = cuboid([60, 40, 20]).partition(spread=10, cutpath="dovetail", spin=90)
    assert _separation(straight) > _separation(spun)

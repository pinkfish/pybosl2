# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/masking.py: the 2-D roundover mask cross-section."""

import math

import numpy as np
import pytest

from pybosl2._edges_lang import CORNER_OFFSETS, Anchor
from pybosl2._edges_lang import edges as resolve_edges
from pybosl2.masking import _corner_set, _corners, chamfer_edge_mask, mask2d_roundover
from pybosl2.shapes3d import Bosl2Solid


@pytest.mark.parametrize(("length", "chamfer", "excess"), [(10, 2, 0.1), (30, 1, 0.1), (10, 2, 1.0)])
def test_chamfer_edge_mask_is_a_diamond_bar(length: float, chamfer: float, excess: float) -> None:
    """A diamond bar: it spans +-chamfer on X and Y, and `length` plus the excess on Z.

    This used to hand the answer to itself -- `Bosl2Solid(m, size=[4, 4, 10.1])` and then assert
    the size was [4, 4, 10.1] -- because chamfer_edge_mask() returned a bare native handle with no
    bounds() of its own to ask. It returns a wrapped solid now, so the measurement is real.
    """
    mask = chamfer_edge_mask(length=length, chamfer=chamfer, excess=excess)
    assert isinstance(mask, Bosl2Solid)
    assert mask.backend == "csg"

    centre, size = mask.bounds()
    assert size == pytest.approx([2 * chamfer, 2 * chamfer, length + excess], abs=0.01)
    assert centre == pytest.approx([0.0, 0.0, 0.0], abs=0.01)  # centred on the edge it cuts


def test_rounding_edge_mask_is_a_wrapped_solid() -> None:
    """Its sibling had the same bare-native return, and the same lack of a real measurement."""
    from pybosl2.masking import rounding_edge_mask

    mask = rounding_edge_mask(length=10, radius=2)
    assert isinstance(mask, Bosl2Solid)
    assert mask.backend == "csg"

    _centre, size = mask.bounds()
    assert size[2] == pytest.approx(10.0, abs=0.01)  # runs the length of the edge
    # The cross-section is the corner the fillet leaves behind: the radius, plus the excess that
    # carries the cut past the two faces.
    assert size[:2] == pytest.approx([2.1, 2.1], abs=0.01)
    assert rounding_edge_mask(length=10, radius=4).bounds()[1][:2] == pytest.approx([4.1, 4.1], abs=0.01)
    assert rounding_edge_mask(length=10, radius=2, excess=0.5).bounds()[1][:2] == pytest.approx([2.5, 2.5], abs=0.01)

    # A tapered mask takes its cross-section from the wide end.
    _centre, tapered_size = rounding_edge_mask(length=30, radius1=1, radius2=3).bounds()
    assert tapered_size[2] == pytest.approx(30.0, abs=0.01)
    assert tapered_size[0] == pytest.approx(3.1, abs=0.01)


def test_returns_a_point_path() -> None:
    path = mask2d_roundover(radius=3)
    from pybosl2.path2d import Path2D

    assert isinstance(path, Path2D)
    assert len(path) > 3
    assert all(len(p) == 2 for p in path)


def test_diameter_matches_radius() -> None:
    np.testing.assert_allclose(mask2d_roundover(radius=3), mask2d_roundover(diameter=6))


def test_corner_and_skirt_geometry() -> None:
    # the L-shape starts along +X and +Y with the given excess skirt past the origin
    path = mask2d_roundover(radius=4, excess=0.1)
    arr = np.asarray(path)
    assert arr[:, 0].min() == pytest.approx(-0.1)  # x skirt
    assert arr[:, 1].min() == pytest.approx(-0.1)  # y skirt


def test_quarter_circle_bite_radius() -> None:
    # the rounded far corner points all sit radius r from the rounding center [r, r]
    radius = 5.0
    path = mask2d_roundover(radius=radius, excess=0.01)
    arc_pts = np.asarray(path[3:])  # the first three points are the two flat legs
    for p in arc_pts:
        assert math.isclose(math.hypot(p[0] - radius, p[1] - radius), radius, abs_tol=1e-9)


def test_requires_r_or_d() -> None:
    with pytest.raises(ValueError, match="must give radius or"):
        mask2d_roundover()


def test_finer_fn_gives_more_points() -> None:
    coarse = mask2d_roundover(radius=5, fn=8)
    fine = mask2d_roundover(radius=5, fn=64)
    assert len(fine) > len(coarse)


# -- corner / edge SELECTORS ---------------------------------------------------------------
#
# `Anchor.TOP + Anchor.FRONT + Anchor.LEFT` is the idiomatic way to name a corner, but it
# evaluates to a Point, NOT an Anchor -- and a Point is a 3-element iterable. Everything that
# tested `isinstance(v, Anchor)` therefore fell through and iterated a single selector into
# three scalar ones (or, in a list, wrapped it twice), so every profile call spelled this way
# raised instead of selecting anything.


def test_corner_set_matches_bosl2_and_selects_exactly_one_corner() -> None:
    """A fully-specified selector names ONE corner.

    BOSL2's rule is an AND over per-axis ORs: `all(v[i] == 0 or v[i] == corner[i])`. Written
    flat, Python's precedence turns `a or b and c or d` into an OR across the axes, which
    matched any corner agreeing on a single axis -- [-1,-1,-1] selected FOUR corners.
    """
    corner_set = _corner_set([-1, -1, -1])
    assert sum(corner_set) == 1
    assert [tuple(c) for c, on in zip(CORNER_OFFSETS, corner_set, strict=True) if on] == [(-1.0, -1.0, -1.0)]


@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        ([-1, -1, -1], 1),  # a corner
        ([1, 1, 1], 1),
        ([0, -1, -1], 2),  # an edge: one free axis -> the 2 corners along it
        ([0, 0, -1], 4),  # a face: two free axes -> its 4 corners
        ([0, 0, 0], 8),  # unconstrained -> every corner
    ],
)
def test_corner_set_free_axes_widen_the_selection(selector: list[int], expected: int) -> None:
    assert sum(_corner_set(selector)) == expected


def test_combined_anchor_resolves_like_the_raw_vector() -> None:
    combined = Anchor.BOTTOM + Anchor.FRONT + Anchor.LEFT
    assert not isinstance(combined, Anchor)  # it is a Point -- the reason this needed fixing
    assert _corner_set(combined) == _corner_set([-1, -1, -1])


def test_corners_accepts_one_selector_or_a_list_of_them() -> None:
    bfl = Anchor.BOTTOM + Anchor.FRONT + Anchor.LEFT
    bfr = Anchor.BOTTOM + Anchor.FRONT + Anchor.RIGHT
    assert _corners(bfl) == _corners([bfl])  # bare and singleton agree
    assert sum(_corners(bfl)) == 1
    assert sum(_corners([bfl, bfr])) == 2  # a list of selectors is not re-wrapped
    assert _corners([[-1, -1, -1]]) == _corners([-1, -1, -1])
    assert sum(_corners(Anchor.BOTTOM)) == 4  # a bare Anchor still works


def test_corners_except_removes_from_the_selection() -> None:
    bfl = Anchor.BOTTOM + Anchor.FRONT + Anchor.LEFT
    assert sum(_corners(Anchor.ALL, [bfl])) == 7


def test_edges_accepts_a_combined_anchor() -> None:
    """`edges(v)` tested `v == []`, which on a Point runs np.allclose and raises."""
    combined = Anchor.BOTTOM + Anchor.FRONT
    assert resolve_edges(combined) == resolve_edges([combined])
    assert sum(sum(row) for row in resolve_edges(combined)) == 1
    assert resolve_edges([]) == resolve_edges(Anchor.NONE)  # the empty forms still short-circuit

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The 2-D and 3-D strokes draw the same cap on the same path, so they must reach the same place.

SPEC PAR-4, S-19a. `stroke()` in two dimensions and in three share `caps.py` -- the same
`CapSpec`, the same `endcap_polys`, the same `endcap_trim` -- and then build independently. That
makes one a check on the other: a 20mm path with an arrow on each end has one right answer, and
either implementation drifting from it shows up as the two disagreeing.

They disagreed by 50%. A 20mm arrow-capped stroke measured 20.1mm in 2-D and **30mm** in 3-D, for
two compounding reasons that had gone unnoticed because nothing compared them:

* **The 3-D stroke never trimmed.** An arrow marks the point it is given, so the body is pulled
  back to put the *tip* there rather than the base -- which is exactly what `endcap_trim`'s
  docstring says it is for, and only `_stroke2d` ever called it.
* **`trim_ends` could not have helped it.** It read `p[0]` and `p[1]` and wrote `[x, y]`, so the
  shared helper was two-dimensional. Handed a 3-D path it returned a *ragged* list -- the trimmed
  end lost its Z while the untouched points kept theirs -- and measured the trim along the XY
  shadow of a segment that might be mostly vertical.
* **And the 3-D cap profile was transposed.** `endcap_polys` documents its frame as "X is the line
  direction, Y is perpendicular"; `rotate_extrude` reads a profile the other way round, X as the
  radius and Y as the height. So each cap was revolved about its own width: an ARROW came out 10mm
  long and 7mm in radius instead of 7 long and 5 in radius.

Nothing caught any of it because a cap that is too long, too fat, or in the wrong place still
produces a closed, plausible solid -- and the two implementations were only ever tested apart.
"""

from __future__ import annotations

import pytest

from pybosl2._backend import use_backend
from pybosl2.caps import CapSpec, CapType
from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D

LENGTH = 20.0
WIDTH = 4.0

#: Every decorative cap with a 3-D form. `LINE` and `X` are flat 2-D markers the 3-D stroke refuses
#: (T59), and `CIRCLE` is unbuilt everywhere.
DECORATIVE = [
    CapType.ARROW,
    CapType.ARROW2,
    CapType.ARROW3,
    CapType.BLOCK,
    CapType.CHISEL,
    CapType.CROSS,
    CapType.DIAMOND,
    CapType.DOT,
    CapType.SQUARE,
    CapType.TAIL,
    CapType.TAIL2,
]


def _extent_2d(cap: CapType | CapSpec) -> tuple[float, float]:
    box = Path2D([[0, 0], [LENGTH, 0]], closed=False).stroke(width=WIDTH, endcap1=cap, endcap2=cap).bounds()
    return (float(box.min_x), float(box.max_x))


def _extent_3d(cap: CapType | CapSpec) -> tuple[float, float]:
    box = Path3D([[0, 0, 0], [LENGTH, 0, 0]], closed=False).stroke(width=WIDTH, endcaps=cap).bounds()
    return (float(box.min_x), float(box.max_x))


@pytest.mark.parametrize("cap", DECORATIVE, ids=lambda c: c.name)
def test_the_two_strokes_reach_the_same_place(cap: CapType) -> None:
    """SPEC PAR-4: one path, one cap, one right answer -- whichever dimension draws it."""
    with use_backend("csg"):
        flat, solid = _extent_2d(cap), _extent_3d(cap)
    # A facet of slack, and only inward: the 3-D cap is a solid of revolution built from inscribed
    # facets, so it sits a little *inside* the 2-D buffer and never outside it. The defects this
    # replaced were 2mm to 5mm, so the slack costs the guard nothing.
    assert solid == pytest.approx(flat, abs=0.4), f"{cap.name}: 2-D reaches {flat} and 3-D reaches {solid}"
    reason = f"{cap.name}: the 3-D cap reaches past the 2-D one ({solid} vs {flat})"
    assert solid[0] >= flat[0] - 1e-6, reason
    assert solid[1] <= flat[1] + 1e-6, reason


@pytest.mark.parametrize("cap", [CapType.ARROW, CapType.ARROW3], ids=lambda c: c.name)
def test_an_arrow_marks_the_point_it_was_given(cap: CapType) -> None:
    """SPEC S-19a: the tip lands on the endpoint, which is the whole reason for the trim.

    `ARROW2` is deliberately absent: `endcap_trim` pulls it back by three quarters of its length,
    not all of it, so its tip sits proudly past the point. Both dimensions agree on that -- the
    test above covers it -- and it is a shape decision rather than a placement error.

    Asserted on the geometry rather than on `endcap_trim` returning a number, because the number
    was right all along -- it was the 3-D stroke never asking for it, and `trim_ends` being unable
    to answer in three dimensions if it had.
    """
    with use_backend("csg"):
        for name, (lo, hi) in (("2-D", _extent_2d(cap)), ("3-D", _extent_3d(cap))):
            assert hi == pytest.approx(LENGTH, abs=0.5), f"{name} {cap.name}: tip at {hi}, not {LENGTH}"
            assert lo == pytest.approx(0.0, abs=0.5), f"{name} {cap.name}: tip at {lo}, not 0"


def test_the_shared_trim_works_in_the_dimension_it_is_given() -> None:
    """SPEC C-20: a helper in a shared module may not be secretly two-dimensional.

    The ragged return is the part worth pinning. A wrong *number* would have shown up the first
    time anyone looked at a 3-D stroke; a point list whose entries have different lengths passes
    through anything that only indexes `[0]` and `[1]`, and fails somewhere else entirely.
    """
    from pybosl2.caps import trim_ends

    flat = trim_ends([[0, 0], [20, 0]], 5.0, 0.0)
    assert flat[0] == pytest.approx([5.0, 0.0])

    solid = trim_ends([[0, 0, 0], [20, 0, 0]], 5.0, 0.0)
    assert solid[0] == pytest.approx([5.0, 0.0, 0.0])
    assert {len(p) for p in solid} == {3}, f"ragged output: {solid}"

    # The trim is a distance along the segment, so a mostly-vertical one is not measured by its
    # shadow: this segment is 20 long in Z and 0 long in XY.
    upright = trim_ends([[0, 0, 0], [0, 0, 20]], 5.0, 0.0)
    assert upright[0] == pytest.approx([0.0, 0.0, 5.0])


def test_a_cap_that_adds_no_length_does_not_move_the_ends() -> None:
    """SPEC PAR-4: the trim applies to arrows, so a flat cap must be left exactly where it was.

    The pairing that keeps the fix honest: trimming everything would put every cap in the right
    place by accident, and this is the half that would fail if it did.
    """
    with use_backend("csg"):
        assert _extent_3d(CapType.BUTT) == pytest.approx((0.0, LENGTH), abs=1e-6)
        assert _extent_2d(CapType.BUTT) == pytest.approx((0.0, LENGTH), abs=1e-6)


# --- the round-over family (T66) ------------------------------------------------------------


def _circle(radius_fraction: float) -> CapSpec:
    """A round-over whose fillet radius is *radius_fraction* of the stroke's half-width.

    `width=1.0` is not decoration. `CapSpec`'s own field default is `width=0.0`, and
    `endcap_polys` reads the fillet radius as `spec.length * spec.width`, so a spec built without
    it produces no cap at all -- a trap that predates this member and catches every cap type.
    """
    return CapSpec(CapType.CIRCLE, length=radius_fraction, width=1.0)


def test_a_full_round_over_is_exactly_a_round_cap() -> None:
    """SPEC S-19a: `CIRCLE` is the family `ROUND` is the extreme of, so the extreme must match.

    `_DEFAULTS` gives `CIRCLE` the same numbers as `ROUND`, which is why the table alone never
    said what distinguished them and the member went unbuilt: the only distinguishing information
    in the port was the word "round-over" in a docstring. Read as a fillet radius over the
    half-width, the shape is pinned at both ends by behaviour that already existed -- no external
    reference required, which matters because BOSL2's source is not vendored here.
    """
    with use_backend("csg"):
        assert _extent_2d(_circle(1.0)) == pytest.approx(_extent_2d(CapType.ROUND), abs=0.01)
        assert _extent_2d(CapType.CIRCLE) == pytest.approx(_extent_2d(CapType.ROUND), abs=0.01)


def test_a_round_over_of_no_radius_is_a_square_end() -> None:
    """SPEC S-19a: the other end of the family. Zero fillet is `BUTT`, and that is a result.

    An empty polygon list normally means a cap fell through to flat, which T59 exists to catch.
    Here the caller asked for no fillet, so a flat end is the answer rather than the omission --
    the one place the two look alike, and worth pinning so the distinction is deliberate.
    """
    with use_backend("csg"):
        assert _extent_2d(_circle(0.0)) == pytest.approx(_extent_2d(CapType.BUTT), abs=1e-6)
        assert _extent_3d(_circle(0.0)) == pytest.approx(_extent_3d(CapType.BUTT), abs=1e-6)


@pytest.mark.parametrize("fraction", [0.25, 0.5, 0.75])
def test_a_partial_round_over_lands_between_the_two(fraction: float) -> None:
    """SPEC S-19a: the fillet radius is a length, so the end reaches exactly that much further."""
    with use_backend("csg"):
        flat, solid = _extent_2d(_circle(fraction)), _extent_3d(_circle(fraction))
    reach = WIDTH / 2 * fraction
    assert flat[1] == pytest.approx(LENGTH + reach, abs=0.01), "the 2-D round-over is mis-sized"
    assert solid[1] == pytest.approx(LENGTH + reach, abs=0.01), "the 3-D round-over is mis-sized"


def test_the_round_over_grows_with_its_radius() -> None:
    """SPEC S-19a: monotone from `BUTT` to `ROUND`, which a mis-read of the radius would break."""
    with use_backend("csg"):
        reaches = [_extent_2d(_circle(f))[1] for f in (0.0, 0.25, 0.5, 0.75, 1.0)]
    assert reaches == sorted(reaches), f"not monotone in the fillet radius: {reaches}"
    assert reaches[0] == pytest.approx(LENGTH, abs=1e-6)
    assert reaches[-1] > reaches[0] + 1.0, "the largest round-over barely differs from a butt end"


@pytest.mark.parametrize("fraction", [0.25, 0.5, 0.75])
def test_a_round_over_keeps_a_flat_end_between_its_fillets(fraction: float) -> None:
    """SPEC S-19a: a round-over is a *flat* end with a filleted rim, which the reach cannot see.

    Every test above measures how far the cap reaches, and a negative control that centred both
    arcs on the axis -- turning the outline into a lens, with no flat at all -- passed all of them,
    because a lens of radius `p` reaches exactly as far as a round-over of radius `p`. The defining
    feature is the part that does not move: the end face stays square across `|y| <= s - p`, and
    only the rim outside that is rolled off. Asserted on the outline, where the flat is a run of
    points sharing the maximum x rather than a single apex.
    """
    from pybosl2.caps import endcap_polys

    half = WIDTH / 2
    radius = half * fraction
    outline = endcap_polys(_circle(fraction), WIDTH)[0]
    reach = max(point[0] for point in outline)
    assert reach == pytest.approx(radius, abs=1e-9)

    on_the_end = [point[1] for point in outline if point[0] == pytest.approx(reach, abs=1e-9)]
    assert len(on_the_end) >= 2, f"the end comes to a point rather than a flat: {outline}"
    assert max(on_the_end) == pytest.approx(half - radius, abs=1e-9), "the flat is the wrong height"
    assert min(on_the_end) == pytest.approx(-(half - radius), abs=1e-9), "the flat is not centred"


def test_a_full_round_over_is_the_one_that_comes_to_a_point() -> None:
    """SPEC S-19a: at `p = s` the flat vanishes and the outline is a semicircle -- which is ROUND.

    The companion to the test above: it requires a flat everywhere *except* the extreme, so the
    two together say the flat shrinks to nothing exactly once, at the value where the family ends.
    """
    from pybosl2.caps import endcap_polys

    outline = endcap_polys(_circle(1.0), WIDTH)[0]
    reach = max(point[0] for point in outline)
    on_the_end = [point[1] for point in outline if point[0] == pytest.approx(reach, abs=1e-9)]
    assert max(on_the_end) == pytest.approx(0.0, abs=1e-9), "a full round-over still has a flat"

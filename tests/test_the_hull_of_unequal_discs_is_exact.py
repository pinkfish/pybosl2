# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The convex hull of discs with *unequal* radii is exact (SPEC R-1, PAR-5).

T139 made `SdfShape2D.hull` return a hull at all, and left one case approximate. When every
operand grows by the same radius the hull is `conv(centres) + ball(r)`, so offsetting the centres'
polygon is exact. With unequal radii no single offset exists, and T139 sampled the support point
over 64 directions instead — an inscribed polygon, bounded by the direction spacing and matching
what the CSG backend builds, but not the shape.

T140 builds it exactly. The signed distance to a convex set `K` is

    f(x) = sup over unit d of ( <d, x> - h(d) )

where `h` is `K`'s support function, and for a hull of discs `h(d) = max_i(<d, c_i> + r_i)`. That
supremum is attained at a **finite** set of directions — the outward normal of one of the discs'
common outer tangent segments, or the direction from a disc's centre to `x` when that direction
lies inside the arc the disc contributes. So the exact distance is a `max` over those features,
which is what `pybosl2.sdf.paths.disc_hull_sdf_xy` assembles.

Two things in that construction were wrong when first written, and measuring is what said so:

* **The arc between two supporting lines belongs to the disc furthest along the first line's
  direction**, not to "the disc both lines touch". With two discs *both* lines touch *both* discs,
  so the second rule handed the same disc to both wedges and one disc contributed no arc at all —
  17mm of distance missing on a capsule.
* **A wedge wider than 180 degrees is a union of two half-planes, not an intersection.** With two
  discs one of the two arcs always is wider, and an `and` there silently dropped the term.

The reference below shares no code with the implementation — only the mathematics — so the two
cannot be accidentally consistent.
"""

import math

import numpy as np
import pytest

import pybosl2.sdf.shapes2d as sdf2
from pybosl2 import use_backend
from pybosl2.sdf._libfive import lv
from pybosl2.sdf.paths import disc_hull_features, drop_contained_discs

#: Direction count for the reference. The implementation is exact, so the reference is the less
#: accurate of the two and the tolerance below is *its* discretisation, not the implementation's.
REFERENCE_DIRECTIONS = 40000
TOLERANCE = 5e-3


_ANGLES = np.arange(REFERENCE_DIRECTIONS) * (2.0 * math.pi / REFERENCE_DIRECTIONS)
_DIRS = np.stack([np.cos(_ANGLES), np.sin(_ANGLES)], axis=1)


def _support_distance(x: float, y: float, discs: list[tuple[float, float, float]]) -> float:
    """`sup over unit d of (<d, x> - max_i(<d, c_i> + r_i))` -- the signed distance, by definition.

    Vectorised over the direction set, because the first version was a Python loop and the grid
    sweep below made 17 million iterations per case out of it.
    """
    arr = np.asarray(discs, dtype=float)
    offsets = _DIRS @ arr[:, :2].T + arr[:, 2]  # <d, c_i> + r_i for every direction and disc
    reach = _DIRS @ np.array([float(x), float(y)])
    return float(np.max(reach - np.max(offsets, axis=1)))


def _field(discs: list[tuple[float, float, float]]) -> object:
    with use_backend("sdf"):
        shape = sdf2._hull_of_unequal_discs(discs, res=10)
    return shape._sdf_fn(lv.x(), lv.y())


#: Every configuration the construction has a branch for.
CASES: dict[str, list[tuple[float, float, float]]] = {
    "two unequal discs": [(0.0, 0.0, 5.0), (20.0, 0.0, 2.0)],
    "three unequal discs": [(0.0, 0.0, 5.0), (20.0, 0.0, 2.0), (8.0, 15.0, 3.0)],
    "four, radii all different": [(0.0, 0.0, 3.0), (15.0, 1.0, 6.0), (7.0, 14.0, 2.0), (-4.0, 9.0, 4.0)],
    "a point and a disc": [(0.0, 0.0, 0.0), (12.0, 0.0, 5.0)],
    "a square's corners and a disc": [
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (10.0, 8.0, 0.0),
        (0.0, 8.0, 0.0),
        (22.0, 4.0, 3.0),
    ],
    "one disc inside another": [(0.0, 0.0, 6.0), (1.0, 0.0, 2.0), (20.0, 0.0, 3.0)],
    "collinear centres, unequal radii": [(0.0, 0.0, 4.0), (10.0, 0.0, 2.0), (20.0, 0.0, 6.0)],
    "nearly touching": [(0.0, 0.0, 5.0), (5.5, 0.0, 1.0)],
}

PROBES = [
    (0.0, 0.0),
    (10.0, 0.0),
    (25.0, 0.0),
    (-8.0, 0.0),
    (0.0, 10.0),
    (6.0, 6.0),
    (12.0, 7.0),
    (-3.0, -3.0),
    (30.0, 20.0),
    (3.0, 2.0),
    (5.0, -7.0),
    (-6.0, 12.0),
    (18.0, 14.0),
    (2.0, 4.0),
    (14.0, 4.0),
    (8.0, -4.0),
]


@pytest.mark.parametrize("label", sorted(CASES))
def test_the_field_matches_the_support_function(label: str) -> None:
    """Inside, outside and on the boundary, against a reference built from the definition."""
    discs = CASES[label]
    tree = _field(discs)
    kept = drop_contained_discs(discs)
    worst, where = 0.0, (0.0, 0.0)
    for px, py in PROBES:
        got = float(tree(px, py, 0.0))  # type: ignore[operator]
        want = _support_distance(px, py, kept)
        if abs(got - want) > worst:
            worst, where = abs(got - want), (px, py)
    assert worst < TOLERANCE, f"{label}: worst disagreement {worst:.3e} at {where}"


@pytest.mark.parametrize("label", sorted(CASES))
def test_the_sign_is_right_everywhere_on_a_grid(label: str) -> None:
    """A denser sweep of the sign alone, which is what decides the shape the mesher sees.

    The distance test above samples sixteen points; this one asks only "inside or outside?" over a
    grid, which is cheap enough to do densely and is the property that actually renders.
    """
    discs = CASES[label]
    kept = drop_contained_discs(discs)
    tree = _field(discs)
    low = [min(c[i] - c[2] for c in kept) - 3.0 for i in (0, 1)]
    high = [max(c[i] + c[2] for c in kept) + 3.0 for i in (0, 1)]
    disagreements = []
    steps = 17
    for ix in range(steps):
        for iy in range(steps):
            px = low[0] + (high[0] - low[0]) * ix / (steps - 1)
            py = low[1] + (high[1] - low[1]) * iy / (steps - 1)
            got = float(tree(px, py, 0.0))  # type: ignore[operator]
            want = _support_distance(px, py, kept)
            # Only a disagreement about the *side* counts, and only away from the boundary where
            # the reference's own discretisation could flip a near-zero value.
            if abs(want) > 1e-2 and (got > 0) != (want > 0):
                disagreements.append((round(px, 3), round(py, 3), round(got, 4), round(want, 4)))
    assert not disagreements, f"{label}: {len(disagreements)} points on the wrong side: {disagreements[:5]}"


def test_the_area_matches_a_hand_derivation() -> None:
    """The one case whose area can be written down, checked against the closed form.

    Agreeing with a support-function reference says the implementation matches the definition of a
    signed distance; it does not say the *shape* is the hull anyone would draw. So one case is
    derived by hand. For discs ``r1`` at the origin and ``r2`` at distance ``d``, the common outer
    tangent's unit normal has component ``(r1 - r2)/d`` along the centre line, which places the
    four tangent points; the hull is then the trapezoid between the two tangent chords plus the
    circular segment each disc contributes beyond its own chord:

        n_x = (r1 - r2)/d = 0.1,  n_y = sqrt(1 - n_x^2)
        chords at x = r1*n_x and x = d + r2*n_x, of half-heights r1*n_y and r2*n_y
        trapezoid                                    157.6060
        segment of D1, central angle 2*pi - 2*acos(n_x)   44.2616
        segment of D2, central angle 2*acos(n_x)          12.3402
        total                                        214.2077

    The CSG backend reports **210.547** for the same hull -- 1.7% low, because it hulls faceted
    circles. This is the case where the SDF side is the accurate one.
    """
    discs = [(0.0, 0.0, 5.0), (20.0, 0.0, 3.0)]
    tree = _field(discs)
    # Area by counting a fine grid, which needs no mesher.
    steps = 600
    low, high = (-6.0, -6.0), (24.0, 6.0)
    cell = ((high[0] - low[0]) / steps) * ((high[1] - low[1]) / steps)
    inside = 0
    for ix in range(steps):
        px = low[0] + (high[0] - low[0]) * (ix + 0.5) / steps
        for iy in range(steps):
            py = low[1] + (high[1] - low[1]) * (iy + 0.5) / steps
            if float(tree(px, py, 0.0)) <= 0.0:  # type: ignore[operator]
                inside += 1
    area = inside * cell
    assert abs(area - 214.2077) < 0.5, f"area {area:.4f} against a derived 214.2077"


# --- the two rules that were wrong when first written ------------------------------------


def test_each_disc_of_a_capsule_contributes_an_arc() -> None:
    """Two discs: both supporting lines touch both discs, so the arcs must be told apart by order.

    "the disc both lines touch" is the rule this looks like it should be, and with two discs it
    picks the same disc twice -- leaving one end of the capsule with no arc term and the field
    reading `|x - c| - r` for the wrong centre. Measured as 17mm of error before the fix.
    """
    discs = [(0.0, 0.0, 4.0), (18.0, 0.0, 4.0)]
    lines, arcs = disc_hull_features(discs)
    assert len(lines) == 2, f"a capsule has two supporting lines, got {len(lines)}"
    assert len(arcs) == 2
    assert {arc[2] for arc in arcs} == {0, 1}, "both discs must own an arc, not one of them twice"


def test_a_reflex_wedge_is_a_union_not_an_intersection() -> None:
    """With two discs one arc always spans more than 180 degrees, which `and` cannot express.

    The far side of a capsule's end cap is the case: an intersection of the two adjacent
    half-planes is empty there, so the disc's term was dropped and the field under-reported the
    distance. Checked on the field itself, at a point squarely in the reflex region.
    """
    discs = [(0.0, 0.0, 5.0), (20.0, 0.0, 2.0)]
    tree = _field(discs)
    # Straight out from the big disc, away from the small one: the big disc's arc spans this, and
    # that arc is the wide one.
    got = float(tree(-9.0, 0.0, 0.0))  # type: ignore[operator]
    assert abs(got - 4.0) < 1e-6, f"expected 4.0 outside the radius-5 disc, got {got}"
    got_up = float(tree(0.0, 11.0, 0.0))  # type: ignore[operator]
    assert abs(got_up - _support_distance(0.0, 11.0, discs)) < TOLERANCE


def test_a_contained_disc_is_dropped() -> None:
    """A disc inside another contributes nothing, and leaving it in loses its container's tangents.

    Two discs where one contains the other have *no* common outer tangent, so a contained disc
    left in the set would silently remove every line that pair should have produced.
    """
    discs = [(0.0, 0.0, 6.0), (1.0, 0.0, 2.0), (20.0, 0.0, 3.0)]
    kept = drop_contained_discs(discs)
    assert len(kept) == 2
    assert (1.0, 0.0, 2.0) not in kept


def test_identical_discs_keep_exactly_one() -> None:
    """Each contains the other, so a rule without a tie-break drops both and leaves nothing."""
    kept = drop_contained_discs([(0.0, 0.0, 3.0), (0.0, 0.0, 3.0), (10.0, 0.0, 1.0)])
    assert sum(1 for c in kept if c == (0.0, 0.0, 3.0)) == 1
    assert len(kept) == 2


def test_a_single_disc_is_just_that_disc() -> None:
    """Everything contained in one disc leaves no tangent lines at all, so there is nothing to max."""
    with use_backend("sdf"):
        shape = sdf2._hull_of_unequal_discs([(2.0, 1.0, 5.0), (2.5, 1.0, 1.0)], res=10)
    box = shape.bounds()
    assert [round(float(v), 6) for v in box.min] == [-3.0, -4.0]
    assert [round(float(v), 6) for v in box.max] == [7.0, 6.0]


# --- the control ---------------------------------------------------------------------------


def test_the_probes_can_fail() -> None:
    """Each of the two rules, reverted, is caught by the tests above.

    A test that agrees with a reference proves little unless getting it wrong disagrees. These are
    the two mistakes actually made, restored one at a time.
    """
    discs = [(0.0, 0.0, 5.0), (20.0, 0.0, 2.0)]
    kept = drop_contained_discs(discs)
    lines, arcs = disc_hull_features(kept)

    def field_with(gate_rule: str) -> object:
        def sdf(x: object, y: object) -> object:
            terms = [nx * x + ny * y - off for nx, ny, off in lines]
            for first, second, disc in arcs:
                nx0, ny0, _ = lines[first]
                nx1, ny1, _ = lines[second]
                centre = kept[disc]
                px, py = x - centre[0], y - centre[1]
                entering = nx0 * py - ny0 * px
                leaving = px * ny1 - py * nx1
                gate = lv.min(entering, leaving) if gate_rule == "and" else lv.max(entering, leaving)
                terms.append(lv.sqrt(px * px + py * py) - centre[2] + 10000.0 * lv.min(gate, 0))
            out = terms[0]
            for t in terms[1:]:
                out = lv.max(out, t)
            return out

        return sdf(lv.x(), lv.y())

    # The reflex rule reverted to a plain `and`: the wide arc's term is dropped.
    wrong = field_with("and")
    worst = max(
        abs(float(wrong(px, py, 0.0)) - _support_distance(px, py, kept))  # type: ignore[operator]
        for px, py in PROBES
    )
    assert worst > TOLERANCE, f"an `and` for every wedge agreed to {worst:.3e}, so the rule is untested"

    # And the arc assignment reverted to "the disc both lines touch", which picks one disc twice.
    both_touch = []
    for k, (nx, ny, off) in enumerate(lines):
        nx1, ny1, off1 = lines[(k + 1) % len(lines)]
        for i, c in enumerate(kept):
            if abs(nx * c[0] + ny * c[1] + c[2] - off) <= 1e-6 and abs(nx1 * c[0] + ny1 * c[1] + c[2] - off1) <= 1e-6:
                both_touch.append(i)
                break
    assert len(set(both_touch)) < 2, (
        "the discarded rule happened to pick both discs here, so this control does not pin it"
    )

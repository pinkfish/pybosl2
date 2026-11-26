# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A shape that claims a tighter containment than its box has to be telling the truth (SPEC S-2b).

`rotate` used to have one thing to work from: the old box's eight corners, transformed. That is
exact for a shape that fills its box and loose for one that does not, and the gap is not small --
an octagonal prism 20.48 across reported 28.97 after the half-facet turn `TrussFoot` and
`TrussJoiner` give their plugs, and a cylinder moved off its own axis and spun reported 16.39 for a
solid 12.00 wide.

T136 gave a shape somewhere to put what it knows: `Hull`, a `(points, radius)` pair claiming the
solid lies inside the convex hull of *points* grown by a ball of *radius*. A prism claims its
outline's own vertices, which are its exact extreme set in every direction; a cylinder claims its
axis segment and its radius.

**The claim is the dangerous part.** `rotate` keeps whichever of the two boxes is tighter on each
axis, so a claim that is too *generous* costs nothing -- it never wins. A claim that is too *small*
wins, and under-reports the box; `mn`/`mx` is the meshing domain, so the solid is then clipped,
silently, in the shape rather than in a number. That asymmetry is why this file exists and why it
is separate from `test_sdf_bounds_are_tight.py`: that file measures the box a shape reports, which
is the claim's *consequence* after one particular turn. This measures the claim itself.

Two questions, in the order of how much they can tell you:

* **The support function.** `conv(P) + ball(r)` contains a solid exactly when, in every direction,
  the solid reaches no further than the hull does. Sampling directions is therefore the direct
  test, and sampling the *solid* on a grid makes it a lower bound on what the solid reaches -- so
  this is a necessary condition rather than a sufficient one, and the planted control below is
  what shows it has teeth.
* **The consequence, over many turns.** Build the shape, turn it a dozen different ways, and look
  for field outside the box each turn reports. That errs the safe way: it samples *outside* the
  box, so a miss between samples makes it lenient about nothing it was asked.
"""

from __future__ import annotations

import itertools
import math

import pytest

import pybosl2.sdf.shapes2d as sdf2
import pybosl2.sdf.shapes3d as sdf
from pybosl2.path2d import Path2D
from pybosl2.sdf._libfive import lv

#: Every constructor that makes a `Hull` claim, with the call that reaches it. A shape here must
#: carry one -- `test_every_claimant_actually_claims` says so -- which is what stops the list
#: drifting from the code, in the direction where the checks below would quietly measure nothing.
CLAIMANTS = {
    "regular_prism": lambda: sdf.regular_prism(num_sides=8, height=10, radius=11.085, anchor=[0, 0, 0]),
    "regular_prism tapered": lambda: sdf.regular_prism(num_sides=7, height=12, radius1=10, radius2=4, anchor=[0, 0, 0]),
    "regular_prism rounded": lambda: sdf.regular_prism(
        num_sides=6, height=10, radius=8, rounding=1.5, anchor=[0, 0, 0]
    ),
    "polygon_prism convex": lambda: sdf.polygon_prism(Path2D([[0, 0], [12, 0], [12, 9], [0, 9]]), height=6),
    "polygon_prism concave": lambda: sdf.polygon_prism(
        Path2D([[0, 0], [20, 0], [20, 6], [6, 6], [6, 20], [0, 20]]), height=8
    ),
    "polygon_prism chamfered rim": lambda: sdf.polygon_prism(
        Path2D([[0, 0], [14, 0], [14, 10], [0, 10]]), height=8, chamfer_top=1.5
    ),
    "cyl": lambda: sdf.cyl(height=20, radius=6, anchor=[0, 0, 0]),
    "cyl tapered": lambda: sdf.cyl(height=20, radius1=8, radius2=3, anchor=[0, 0, 0]),
    "cyl sheared": lambda: sdf.cyl(height=20, radius=6, shift=[20, 0], anchor=[0, 0, 0]),
    "cyl rounded": lambda: sdf.cyl(height=20, radius=6, rounding=2, anchor=[0, 0, 0]),
    "cyl with extra": lambda: sdf.cyl(height=20, radius=6, extra1=3, extra2=5, anchor=[0, 0, 0]),
    "cyl textured": lambda: sdf.cyl(
        height=20, radius=8, texture="ribs", tex_reps=[8, 1], tex_depth=1.5, anchor=[0, 0, 0]
    ),
}

#: The 2-D twin. `regular_ngon2d`, `star2d`, `trapezoid2d` and `supershape2d` all build through
#: `polygon2d`, so claiming it there covers them; `rect2d` and `circle2d` claim their own.
CLAIMANTS_2D = {
    "polygon2d": lambda: sdf2.polygon2d(Path2D([[0, 0], [20, 0], [20, 6], [6, 6], [6, 20], [0, 20]])),
    "regular_ngon2d": lambda: sdf2.regular_ngon2d(num_sides=5, radius=5),
    "star2d": lambda: sdf2.star2d(num_sides=5, radius=10, inner_radius=4),
    "trapezoid2d": lambda: sdf2.trapezoid2d(height=10, width1=20, width2=10),
    "circle2d": lambda: sdf2.circle2d(radius=5),
    "rect2d": lambda: sdf2.rect2d(size=[20, 10]),
    "rect2d rounded": lambda: sdf2.rect2d(size=[20, 10], rounding=2),
    "rect2d chamfered": lambda: sdf2.rect2d(size=[20, 10], chamfer=2),
    "rect2d rounded unevenly": lambda: sdf2.rect2d(size=[20, 10], rounding=[3, 0, 1, 2]),
}

#: Directions to compare the solid's reach with the hull's. Enough to cover the octants and the
#: axes, plus a few that line up with nothing.
DIRECTIONS = [
    *([1.0 if i == k else 0.0 for i in range(3)] for k in range(3)),
    *([-1.0 if i == k else 0.0 for i in range(3)] for k in range(3)),
    *(list(signs) for signs in itertools.product((-1.0, 1.0), repeat=3)),
    [0.3, 0.9, 0.2],
    [-0.7, 0.4, 0.6],
    [0.5, -0.1, -0.85],
]

#: Turns to apply, as `(angle, axis)`. Half a facet is the worst case for an n-gon, so the list
#: is deliberately full of angles that are nobody's symmetry step.
TURNS = [
    (22.5, [0.0, 0.0, 1.0]),
    (30.0, [0.0, 0.0, 1.0]),
    (37.0, [0.0, 0.0, 1.0]),
    (90.0, [0.0, 0.0, 1.0]),
    (35.0, [1.0, 0.0, 0.0]),
    (61.0, [0.0, 1.0, 0.0]),
    (44.0, [1.0, 1.0, 0.0]),
    (17.0, [1.0, 2.0, 3.0]),
]


def _unit(v: "list[float]") -> "list[float]":
    length = math.sqrt(sum(c * c for c in v))
    return [c / length for c in v]


def _hull_support(shape: object, direction: "list[float]") -> float:
    """How far the shape's `Hull` claim reaches along *direction*."""
    points, radius = shape._hull  # type: ignore[attr-defined]
    return max(sum(p[i] * direction[i] for i in range(len(direction))) for p in points) + radius


def _inside_points(shape: object, samples: int) -> "list[tuple[float, ...]]":
    """Grid points over the shape's own box where the field is not positive.

    Sampled once per shape and reused for every direction: the supports below are maxima over the
    same point set, and the grid is the only thing here that costs anything.
    """
    axes = len(shape.mn)  # type: ignore[attr-defined]
    tree = shape._sdf_fn(*[lv.x(), lv.y(), lv.z()][:axes])  # type: ignore[attr-defined]
    low, high = list(shape.mn), list(shape.mx)  # type: ignore[attr-defined]
    steps = [[low[k] + (high[k] - low[k]) * i / (samples - 1) for i in range(samples)] for k in range(axes)]
    # A 2-D tree is still called with three coordinates and ignores the third.
    pad = [0.0] if axes == 2 else []
    found = [point for point in itertools.product(*steps) if float(tree(*point, *pad)) <= 0.0]
    assert found, "no sample landed inside the shape; the probe measures nothing"
    return found


def _reach(points: "list[tuple[float, ...]]", direction: "list[float]") -> float:
    """How far *points* reach along *direction*."""
    return max(sum(point[i] * direction[i] for i in range(len(direction))) for point in points)


def _solid_support(shape: object, direction: "list[float]", samples: int = 21) -> float:
    """How far the shape itself reaches along *direction*, over a grid inside its box.

    A lower bound: the extreme point can fall between samples. That makes the comparison below a
    necessary condition and not a sufficient one, which the planted control accounts for.
    """
    return _reach(_inside_points(shape, samples), direction)


@pytest.mark.parametrize("label", sorted(CLAIMANTS))
def test_every_claimant_actually_claims(label: str) -> None:
    """A constructor dropping its claim must be noticed, not silently reduce these to no-ops."""
    shape = CLAIMANTS[label]()
    assert shape._hull is not None, (
        f"{label} no longer carries a Hull, so everything this file checks about it is vacuous. "
        f"Either restore the claim or take the entry out of CLAIMANTS."
    )
    points, radius = shape._hull
    assert points, f"{label} claims an empty point set"
    assert radius >= 0.0, f"{label} claims a negative radius ({radius})"


@pytest.mark.parametrize("label", sorted(CLAIMANTS_2D))
def test_every_2d_claimant_actually_claims(label: str) -> None:
    """As above, for the 2-D shapes."""
    shape = CLAIMANTS_2D[label]()
    assert shape._hull is not None, f"{label} no longer carries a Hull2D"
    points, radius = shape._hull
    assert points, f"{label} claims an empty point set"
    assert radius >= 0.0, f"{label} claims a negative radius ({radius})"


@pytest.mark.parametrize("label", sorted(CLAIMANTS))
def test_the_solid_reaches_no_further_than_its_hull_claims(label: str) -> None:
    """The direct question: in every direction, is the hull's support at least the solid's?

    That is what containment in `conv(points) + ball(radius)` *means*, so this is the claim itself
    rather than one of its consequences.
    """
    shape = CLAIMANTS[label]()
    inside = _inside_points(shape, 21)
    for raw in DIRECTIONS:
        direction = _unit(raw)
        solid, hull = _reach(inside, direction), _hull_support(shape, direction)
        assert solid <= hull + 1e-9, (
            f"{label}: the solid reaches {solid:.4f} along {[round(c, 3) for c in direction]} and "
            f"its hull claims only {hull:.4f}. An over-claimed hull makes `rotate` report a box "
            f"the solid does not fit in, which clips it at mesh time (SPEC S-2b)."
        )


@pytest.mark.parametrize("label", sorted(CLAIMANTS_2D))
def test_the_2d_shape_reaches_no_further_than_its_hull_claims(label: str) -> None:
    """As above, in two dimensions."""
    shape = CLAIMANTS_2D[label]()
    inside = _inside_points(shape, 61)
    for raw in ([1.0, 0.0], [0.0, 1.0], [-1.0, 0.0], [0.0, -1.0], [1.0, 1.0], [-1.0, 1.0], [0.4, -0.9]):
        direction = _unit(raw)
        solid, hull = _reach(inside, direction), _hull_support(shape, direction)
        assert solid <= hull + 1e-9, (
            f"{label}: the shape reaches {solid:.4f} along {[round(c, 3) for c in direction]} and "
            f"its hull claims only {hull:.4f}"
        )


def _turn_id(turn: "tuple[float, list[float]]") -> str:
    axis = "".join("xyz"[i] for i, c in enumerate(turn[1]) if c)
    return f"{turn[0]:g}deg about {axis}"


@pytest.mark.parametrize("turn", TURNS, ids=_turn_id)
@pytest.mark.parametrize("label", sorted(CLAIMANTS))
def test_no_turn_leaves_the_solid_outside_the_box_it_reports(label: str, turn: "tuple[float, list[float]]") -> None:
    """The consequence, over eight turns -- and this one errs the safe way.

    It samples the six planes just *outside* the box, over faces extended by the same margin, so a
    corner escaping is seen as well as a face. A sample missed between grid points makes it lenient
    about nothing: there is either field out there or there is not.
    """
    angle, axis = turn
    turned = CLAIMANTS[label]().rotate(angle, axis)
    tree = turned._sdf_fn(lv.x(), lv.y(), lv.z())
    low, high = list(turned.mn), list(turned.mx)
    margin = 0.05 * max(high[i] - low[i] for i in range(3))
    for face in range(3):
        others = [k for k in range(3) if k != face]
        span = [(low[k] - margin, high[k] - low[k] + 2 * margin) for k in range(3)]
        for plane in (low[face] - margin, high[face] + margin):
            deepest = min(
                float(
                    tree(
                        *[
                            plane if k == face else span[k][0] + span[k][1] * (i if k == others[0] else j) / 16
                            for k in range(3)
                        ]
                    )
                )
                for i in range(17)
                for j in range(17)
            )
            assert deepest > 0, (
                f"{label} turned {angle} about {axis}: there is solid {-deepest:.4f} outside the "
                f"{'xyz'[face]} face of the box it reports -- meshing clips it"
            )


def test_a_shrunken_claim_is_caught() -> None:
    """The control. Both checks above have to be able to fail, or neither means anything.

    The planted defect is the realistic one: a claim that is *nearly* right. Shrinking a prism's
    outline keeps the hull the same shape, in the same place, with the right number of points --
    and makes `rotate` report a box the solid hangs out of.

    The first version shrank it by 10%, and the check read exactly equal rather than failing: at
    21 samples over this prism's box the second-highest grid line sits at 0.9 of the box's own
    half-width, so the sampled solid and the shrunken claim landed on the same number to the digit.
    A coincidence of the probe, and a reminder that a control which *just barely* fires is not
    evidence the check works -- 20% is clear of any grid.
    """
    honest = sdf.regular_prism(num_sides=8, height=10, radius=11.085, anchor=[0, 0, 0])
    points, radius = honest._hull
    assert radius == 0.0, "the fixture is meant to be a plain point-set claim"

    shrunken = sdf.regular_prism(num_sides=8, height=10, radius=11.085, anchor=[0, 0, 0])
    shrunken._hull = ([[0.8 * p[0], 0.8 * p[1], p[2]] for p in points], 0.0)

    direction = _unit([1.0, 0.0, 0.0])
    assert _solid_support(shrunken, direction) > _hull_support(shrunken, direction) + 1e-9, (
        "a hull shrunk by 10% is not seen as over-claimed, so the support check cannot fail"
    )

    turned = shrunken.rotate(22.5, [0.0, 0.0, 1.0])
    tree = turned._sdf_fn(lv.x(), lv.y(), lv.z())
    outside = min(
        float(tree(turned.mx[0] + 0.05, turned.mn[1] + (turned.mx[1] - turned.mn[1]) * i / 16, 0.0)) for i in range(17)
    )
    assert outside <= 0, "the shrunken claim does not actually under-report the turned box"


def test_the_honest_claim_passes_the_same_control() -> None:
    """The other half of the control: the planted failure must be the claim and not the probe."""
    honest = sdf.regular_prism(num_sides=8, height=10, radius=11.085, anchor=[0, 0, 0])
    direction = _unit([1.0, 0.0, 0.0])
    assert _solid_support(honest, direction) <= _hull_support(honest, direction) + 1e-9
    turned = honest.rotate(22.5, [0.0, 0.0, 1.0])
    tree = turned._sdf_fn(lv.x(), lv.y(), lv.z())
    outside = min(
        float(tree(turned.mx[0] + 0.05, turned.mn[1] + (turned.mx[1] - turned.mn[1]) * i / 16, 0.0)) for i in range(17)
    )
    assert outside > 0, "the honest claim reads as under-reporting too, so the control proves nothing"

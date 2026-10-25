# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A 2-D bound is a claim too, and nothing was measuring it (SPEC S-2b, PAR-5).

`test_sdf_bounds_are_tight.py` asks of every 3-D solid whether it reaches the box it declares and
whether any of it escapes. It was written after the same defect turned up five times in T40-T48,
and it covers **no 2-D shape at all** -- the string "2d" does not appear in it. So the whole 2-D
half of the question went unasked, and the answer was already wrong.

`SdfShape2D.rotate` builds its box from the rotated corners of the old box. That is exact at
multiples of 90 degrees, and exact for a rectangle at any angle, which is why it looked fine. It is
wrong for anything whose outline does not reach the corners of its box:

* a circle of radius 5 turned 45 degrees claimed 2.07 of empty margin, having not moved at all;
* a regular hexagon turned 60 degrees -- onto itself, vertex for vertex -- claimed 2.17;
* a five-pointed star turned 72 degrees claimed 3.45.

The fix is the 2-D form of what T49 gave the solids: each constructor records the point it turns
about and the smallest turn that leaves it identical, and `rotate` keeps the box when the angle is
a whole number of those steps. A 2-D rotation is always about the origin, so the record needs no
direction -- only the point, and `0` for a circle, which has no smallest step.

What this does **not** do is make every box tight. At an angle that is not a symmetry step the
rotated corner box is the honest conservative answer, and tightening it would mean sampling the
field rather than reasoning about it. Those cases are in `CONSERVATIVE` with the figure each
measures, and that table only shrinks.
"""

from __future__ import annotations

import pytest

import pybosl2.sdf.shapes2d as sdf2
from pybosl2.sdf._libfive import lv

#: How far the field may sit from a face of its own box before the box is called loose. The faces
#: are sampled on a line, so a contact at a single point can fall between samples; a rectangle's
#: box is exact and still measures 0.10 at this resolution. Set above that noise and far below any
#: real defect here, which has been 1.2 and up.
SLACK = 0.35

BUILDERS = {
    "circle": lambda: sdf2.circle2d(radius=5, res=10),
    "ellipse circular": lambda: sdf2.ellipse2d(radius=[5, 5], res=10),
    "ellipse": lambda: sdf2.ellipse2d(radius=[8, 4], res=10),
    "rect": lambda: sdf2.rect2d(size=[20, 10], res=10),
    "rect rounded": lambda: sdf2.rect2d(size=[20, 10], rounding=2, res=10),
    "rect chamfered": lambda: sdf2.rect2d(size=[20, 10], chamfer=2, res=10),
    "square": lambda: sdf2.square2d(size=[12, 12], res=10),
    "ngon 5": lambda: sdf2.regular_ngon2d(num_sides=5, radius=5, res=10),
    "ngon 6": lambda: sdf2.regular_ngon2d(num_sides=6, radius=5, res=10),
    "ngon 12": lambda: sdf2.regular_ngon2d(num_sides=12, radius=5, res=10),
    "ngon by apothem": lambda: sdf2.regular_ngon2d(num_sides=5, inner_radius=5, res=10),
    "ngon by side": lambda: sdf2.regular_ngon2d(num_sides=5, side=5, res=10),
    "star": lambda: sdf2.star2d(num_sides=5, radius=10, inner_radius=4, res=10),
    "trapezoid": lambda: sdf2.trapezoid2d(height=10, width1=20, width2=10, res=10),
    "trapezoid shifted": lambda: sdf2.trapezoid2d(height=10, width1=20, width2=10, shift=4, res=10),
    "circle moved": lambda: sdf2.circle2d(radius=5, res=10).translate([7, -3]),
    "rect scaled": lambda: sdf2.rect2d(size=[20, 10], res=10).scale([2, 1]),
    "circle spun": lambda: sdf2.circle2d(radius=5, res=10).rotate(30),
    "circle spun oddly": lambda: sdf2.circle2d(radius=5, res=10).rotate(17.5),
    "ellipse circular spun": lambda: sdf2.ellipse2d(radius=[5, 5], res=10).rotate(45),
    "rect spun square on": lambda: sdf2.rect2d(size=[20, 10], res=10).rotate(90),
    "rect spun over": lambda: sdf2.rect2d(size=[20, 10], res=10).rotate(180),
    "ngon 6 spun onto itself": lambda: sdf2.regular_ngon2d(num_sides=6, radius=5, res=10).rotate(60),
    "ngon 5 spun onto itself": lambda: sdf2.regular_ngon2d(num_sides=5, radius=5, res=10).rotate(72),
    "ngon 12 spun onto itself": lambda: sdf2.regular_ngon2d(num_sides=12, radius=5, res=10).rotate(30),
    "star spun onto itself": lambda: sdf2.star2d(num_sides=5, radius=10, inner_radius=4, res=10).rotate(72),
}

#: The shapes whose box is conservative on purpose, with what each measures today. A rotation that
#: is not a symmetry step cannot be tightened from the box alone, and a circle moved off the origin
#: and then turned really does sweep a wider box. Figures may fall, never rise.
CONSERVATIVE = {
    "ngon 5 spun off step": 2.25,
    "star spun off step": 4.50,
    "trapezoid spun": 4.20,
    "rect rounded spun": 0.85,
    "circle moved then spun": 1.85,
}

CONSERVATIVE_BUILDERS = {
    "ngon 5 spun off step": lambda: sdf2.regular_ngon2d(num_sides=5, radius=5, res=10).rotate(45),
    "star spun off step": lambda: sdf2.star2d(num_sides=5, radius=10, inner_radius=4, res=10).rotate(45),
    "trapezoid spun": lambda: sdf2.trapezoid2d(height=10, width1=20, width2=10, res=10).rotate(30),
    "rect rounded spun": lambda: sdf2.rect2d(size=[20, 10], rounding=2, res=10).rotate(45),
    "circle moved then spun": lambda: sdf2.circle2d(radius=5, res=10).translate([7, 0]).rotate(30),
}


def _tree(shape: object) -> object:
    return shape._sdf_fn(lv.x(), lv.y())  # type: ignore[attr-defined]


def _worst_gap(shape: object, samples: int = 121) -> tuple[float, str]:
    """Return how far the field stays from the nearest face of its own box, and which face."""
    tree = _tree(shape)
    low, high = list(shape.mn), list(shape.mx)  # type: ignore[attr-defined]
    worst, where = 0.0, "none"
    for axis in (0, 1):
        other = 1 - axis
        span = high[other] - low[other]
        for plane in (low[axis], high[axis]):
            nearest = min(
                float(
                    tree(  # type: ignore[operator]
                        *(
                            (plane, low[other] + span * i / (samples - 1), 0.0)
                            if axis == 0
                            else (low[other] + span * i / (samples - 1), plane, 0.0)
                        )
                    )
                )
                for i in range(samples)
            )
            if nearest > worst:
                worst, where = nearest, f"{'xy'[axis]}={plane:.3f}"
    return worst, where


def _worst_escape(shape: object, samples: int = 81) -> tuple[float, tuple[float, float]]:
    """Return the most negative distance found *outside* the declared box, and where."""
    tree = _tree(shape)
    low, high = list(shape.mn), list(shape.mx)  # type: ignore[attr-defined]
    pad = 0.3 * max(high[0] - low[0], high[1] - low[1]) + 1.0
    worst, at = 0.0, (0.0, 0.0)
    for i in range(samples):
        for j in range(samples):
            x = low[0] - pad + (high[0] - low[0] + 2 * pad) * i / (samples - 1)
            y = low[1] - pad + (high[1] - low[1] + 2 * pad) * j / (samples - 1)
            if low[0] - 1e-9 <= x <= high[0] + 1e-9 and low[1] - 1e-9 <= y <= high[1] + 1e-9:
                continue
            d = float(tree(x, y, 0.0))  # type: ignore[operator]
            if d < worst:
                worst, at = d, (x, y)
    return worst, at


def test_the_field_can_actually_be_sampled() -> None:
    """Every assertion below reads zero if the field evaluates to nothing, so prove it does not.

    libfive is stubbed in this suite and an SDF solid meshes to nothing, which is why so much of
    the campaign believed it could only read analytic boxes. The field is a different matter: it is
    a symbolic tree and evaluating it gives exact signed distances, which is what makes this file
    possible -- and, as T119 then measured, was never limited to two dimensions.
    """
    tree = _tree(sdf2.circle2d(radius=5, res=10))
    inside = float(tree(0.0, 0.0, 0.0))  # type: ignore[operator]
    on_edge = float(tree(5.0, 0.0, 0.0))  # type: ignore[operator]
    outside = float(tree(6.0, 0.0, 0.0))  # type: ignore[operator]
    assert inside == pytest.approx(-5.0, abs=1e-6), f"centre of a circle of radius 5 reads {inside}"
    assert on_edge == pytest.approx(0.0, abs=1e-6), f"rim of a circle of radius 5 reads {on_edge}"
    assert outside == pytest.approx(1.0, abs=1e-6), f"1 outside the rim reads {outside}"


@pytest.mark.parametrize("label", sorted(BUILDERS))
def test_the_shape_reaches_every_face_of_the_box_it_declares(label: str) -> None:
    """Loose or tight, measured against the field rather than read off the formula beside it."""
    worst, where = _worst_gap(BUILDERS[label]())
    assert worst <= SLACK, (
        f"{label} keeps {worst:.3f} clear of its own box at {where} -- the box claims room the "
        f"shape never occupies (SPEC S-2b, PAR-5)."
    )


@pytest.mark.parametrize("label", sorted(set(BUILDERS) | set(CONSERVATIVE_BUILDERS)))
def test_no_part_of_the_shape_escapes_its_box(label: str) -> None:
    """The dangerous direction: a box too small clips the mesh silently, in the shape not a number.

    This half was missing from the 3-D file's first version and two of four controls passed without
    it. It is here from the start, and over every case including the deliberately loose ones -- a
    conservative box must still be conservative in the safe direction.
    """
    build = BUILDERS.get(label) or CONSERVATIVE_BUILDERS[label]
    escape, at = _worst_escape(build())
    assert escape >= -1e-6, (
        f"{label} has field at ({at[0]:.3f}, {at[1]:.3f}), which is outside the box it declares, "
        f"reading {escape:.3f} -- meshing clips it (SPEC S-2b)."
    )


@pytest.mark.parametrize("label", sorted(CONSERVATIVE))
def test_a_conservative_box_is_no_worse_than_recorded(label: str) -> None:
    """These cannot be tightened from the box alone. The figures may fall, never rise."""
    worst, where = _worst_gap(CONSERVATIVE_BUILDERS[label]())
    assert worst <= CONSERVATIVE[label], (
        f"{label} is now {worst:.3f} loose at {where}, worse than the {CONSERVATIVE[label]} "
        f"recorded. Conservative is allowed; drifting is not."
    )


def test_no_conservative_entry_has_quietly_become_tight() -> None:
    """An entry that no longer needs to be here is a stale excuse, so it has to be noticed."""
    fixed = {
        label: round(_worst_gap(CONSERVATIVE_BUILDERS[label]())[0], 3)
        for label in sorted(CONSERVATIVE)
        if _worst_gap(CONSERVATIVE_BUILDERS[label]())[0] <= SLACK
    }
    assert not fixed, (
        f"{fixed} now measure within {SLACK} and are tight -- move them into BUILDERS and drop "
        f"them from CONSERVATIVE rather than leaving a licence nothing needs."
    )


#: Each shape and the smallest turn that must leave its box exactly as it was.
SYMMETRY_STEPS = [
    ("circle", lambda: sdf2.circle2d(radius=5, res=10), 17.5),
    ("circle", lambda: sdf2.circle2d(radius=5, res=10), 45.0),
    ("ellipse circular", lambda: sdf2.ellipse2d(radius=[5, 5], res=10), 33.0),
    ("ellipse", lambda: sdf2.ellipse2d(radius=[8, 4], res=10), 180.0),
    ("rect", lambda: sdf2.rect2d(size=[20, 10], res=10), 180.0),
    ("square", lambda: sdf2.square2d(size=[12, 12], res=10), 90.0),
    ("ngon 5", lambda: sdf2.regular_ngon2d(num_sides=5, radius=5, res=10), 72.0),
    ("ngon 6", lambda: sdf2.regular_ngon2d(num_sides=6, radius=5, res=10), 60.0),
    ("ngon 12", lambda: sdf2.regular_ngon2d(num_sides=12, radius=5, res=10), 30.0),
    ("star 5", lambda: sdf2.star2d(num_sides=5, radius=10, inner_radius=4, res=10), 72.0),
]


@pytest.mark.parametrize(("label", "build", "step"), SYMMETRY_STEPS)
def test_a_turn_onto_itself_leaves_the_box_alone(label: str, build: object, step: float) -> None:
    """A shape turned onto itself is the same shape, so it must report the same box.

    Two steps are checked, because keeping the box for one step and recomputing it for the next
    would pass a single-step test while still widening the box on the second turn.
    """
    shape = build()  # type: ignore[operator]
    before = (list(shape.mn), list(shape.mx))
    once = shape.rotate(step)
    twice = shape.rotate(2 * step)
    for turns, turned in ((1, once), (2, twice)):
        got = (list(turned.mn), list(turned.mx))
        assert got == pytest.approx(before, abs=1e-9), (
            f"{label} turned {turns * step:g} degrees -- {turns} step(s) of its own symmetry -- "
            f"reports {got} where it had {before}. The shape is unchanged; the box is not."
        )


@pytest.mark.parametrize(
    ("label", "build", "step"), [case for case in SYMMETRY_STEPS if case[2] > 0 and case[0] != "circle"]
)
def test_half_a_step_is_not_a_step(label: str, build: object, step: float) -> None:
    """Turning by half a symmetry step moves the shape, so the box may not simply be kept.

    This is the control that got away. Recording an n-gon's step as `180/n` rather than `360/n`
    leaves every genuine step a whole multiple, so every "turned onto itself" assertion still
    passed -- while a pentagon turned 36 degrees, vertices onto edge midpoints, kept a box that no
    longer bounds it and loses 0.955 off its left side. A step that is too small fails in the
    direction that clips.
    """
    turned = build().rotate(step / 2)  # type: ignore[operator]
    escape, at = _worst_escape(turned)
    assert escape >= -1e-6, (
        f"{label} turned {step / 2:g} degrees -- half of its {step:g}-degree symmetry step -- has "
        f"field at ({at[0]:.3f}, {at[1]:.3f}) outside its own box, reading {escape:.3f}. The box "
        f"was kept for a turn that moved the shape (SPEC S-2b)."
    )


def test_the_symmetry_is_about_the_shapes_own_centre_not_the_origin() -> None:
    """Move a circle off the origin and the box must widen again -- it genuinely sweeps.

    This is the 2-D form of the reason the 3-D record carries a point: a cylinder on the Z axis
    spun about Z is unmoved, and the same cylinder at x=3 is not. Without it the record would keep
    a box that a rotation really does invalidate, which is the unsafe direction.
    """
    moved = sdf2.circle2d(radius=5, res=10).translate([7, 0])
    before = (list(moved.mn), list(moved.mx))
    spun = moved.rotate(30)
    assert (list(spun.mn), list(spun.mx)) != before, (
        "a circle at x=7 spun 30 degrees kept its box, but it has swung to a new place entirely -- "
        "the symmetry point must be compared against the rotation centre, not assumed."
    )
    escape, at = _worst_escape(spun)
    assert escape >= -1e-6, f"the swung circle escapes its box at ({at[0]:.3f}, {at[1]:.3f})"


def test_cutting_a_shape_drops_its_symmetry() -> None:
    """A circle with a bite out of it is not a circle, and must not inherit a circle's licence."""
    bitten = sdf2.circle2d(radius=5, res=10) - sdf2.rect2d(size=[6, 6], res=10).translate([5, 0])
    assert bitten._symmetry is None, (
        "the difference of two shapes kept a symmetry record. Only `translate` may carry one; "
        "anything that changes the outline has to drop it, or `rotate` will keep a box that no "
        "longer bounds the shape."
    )
    escape, at = _worst_escape(bitten.rotate(30))
    assert escape >= -1e-6, f"the cut shape escapes its box after a turn at ({at[0]:.3f}, {at[1]:.3f})"

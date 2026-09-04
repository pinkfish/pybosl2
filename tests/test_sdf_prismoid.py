# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A prismoid's rounded and chamfered edges, checked against the hull CSG actually takes.

SPEC PAR-4, PAR-5. This backend refused `rounding=` and `chamfer=` on a prismoid, with a caveat in
the docstring saying that "deriving an exact SDF for a *tapered* box's independently-radiused
vertical edges was out of scope". It needed no derivation, because **the CSG backend does not
derive one either**: it builds the two end cross-sections and takes their convex hull.

The hull of two convex sets in parallel planes has cross-section `(1-t)A + tB` -- the Minkowski
combination -- at every height between them, and for these shapes that combination is the same
shape again:

* a rounded rectangle is `box + disc`, and Minkowski addition distributes, so the blend is a
  rounded rectangle with the half-size and the corner radius each linearly interpolated;
* a chamfered rectangle is an octagon whose support function is linear in the size and the
  chamfer, so its blend is a chamfered rectangle with both interpolated.

These tests do not take that on trust. They compute the cross-section **from the CSG backend's own
two input polygons** -- every `(1-t)a + tb` for `a` in one and `b` in the other, which is exactly
the hull's slice -- and ask the field about those points. No formula of the implementation's is
reused to check it.
"""

from __future__ import annotations

import math

import pytest

import pybosl2.sdf.shapes3d as sdf
from pybosl2._helpers import rect_path
from pybosl2.sdf._libfive import lv

SIZE1 = [20.0, 20.0]
SIZE2 = [10.0, 14.0]
HEIGHT = 10.0


def _hull_slice(
    t: float,
    *,
    rounding: tuple[float, float] = (0.0, 0.0),
    chamfer: tuple[float, float] = (0.0, 0.0),
    shift: tuple[float, float] = (0.0, 0.0),
) -> list[tuple[float, float]]:
    """Return the CSG hull's cross-section at height fraction *t*, from its own input polygons."""
    bottom = rect_path(SIZE1, rounding=rounding[0], chamfer=chamfer[0])
    top = rect_path(SIZE2, rounding=rounding[1], chamfer=chamfer[1])
    return [
        ((1 - t) * a[0] + t * (b[0] + shift[0]), (1 - t) * a[1] + t * (b[1] + shift[1])) for a in bottom for b in top
    ]


def _field(**kwargs: object):
    shape = sdf.prismoid(SIZE1, SIZE2, height=HEIGHT, anchor=[0, 0, 0], **kwargs)
    return shape._sdf_fn(lv.x(), lv.y(), lv.z())


CASES = [
    ("a plain taper", {}, {}),
    ("a rounding at both ends", {"rounding1": 2.0, "rounding2": 2.0}, {"rounding": (2.0, 2.0)}),
    ("a rounding that grows", {"rounding1": 1.0, "rounding2": 3.0}, {"rounding": (1.0, 3.0)}),
    ("a chamfer at both ends", {"chamfer1": 2.0, "chamfer2": 2.0}, {"chamfer": (2.0, 2.0)}),
    ("a chamfer that grows", {"chamfer1": 1.0, "chamfer2": 3.0}, {"chamfer": (1.0, 3.0)}),
    (
        "a rounding on a sheared prism",
        {"rounding1": 2.0, "rounding2": 2.0, "shift": [3.0, -2.0]},
        {"rounding": (2.0, 2.0), "shift": (3.0, -2.0)},
    ),
]


@pytest.mark.parametrize(("label", "built", "sliced"), CASES)
def test_no_part_of_the_hull_is_missing_from_the_field(
    label: str, built: dict[str, object], sliced: dict[str, object]
) -> None:
    """Every point of the hull's own cross-section is inside the field, and its boundary is touched."""
    tree = _field(**built)
    for t in (0.2, 0.5, 0.8):
        z = -HEIGHT / 2 + t * HEIGHT
        values = [float(tree(px, py, z)) for px, py in _hull_slice(t, **sliced)]  # type: ignore[arg-type]
        assert max(values) <= 1e-9, f"{label} at t={t}: a hull point sits {max(values)} outside the field"
        assert min(abs(v) for v in values) == pytest.approx(0.0, abs=1e-9), (
            f"{label} at t={t}: the field's boundary never touches the hull's"
        )


SQRT2 = math.sqrt(2.0)


@pytest.mark.parametrize(("label", "built", "sliced"), CASES)
def test_the_treated_corner_is_actually_cut_away(
    label: str, built: dict[str, object], sliced: dict[str, object]
) -> None:
    """The other half of the claim, and the half the obvious test cannot make.

    Containing the hull is easy if the field is simply too big: a plain box contains every rounded
    or chamfered version of itself, and the rounded shape *touches* the box along its flat edges,
    so "every hull point is inside, and the boundary is touched" passes with `rounding=` ignored
    altogether. Planting that is what found it -- three of five negative controls went green.

    What separates them is the **sharp corner** of the interpolated box, which the treatment cuts
    away. Its distance outside is known in closed form: `r * (sqrt(2) - 1)` for a rounding, and
    `c / sqrt(2)` for a chamfer -- both linear in the amount, so checking the value rather than
    only the sign also pins the interpolation between the two ends.
    """
    tree = _field(**built)
    r1, r2 = sliced.get("rounding", (0.0, 0.0))  # type: ignore[misc]
    c1, c2 = sliced.get("chamfer", (0.0, 0.0))  # type: ignore[misc]
    shift = sliced.get("shift", (0.0, 0.0))

    for t in (0.2, 0.5, 0.8):
        z = -HEIGHT / 2 + t * HEIGHT
        bx = (SIZE1[0] + (SIZE2[0] - SIZE1[0]) * t) / 2
        by = (SIZE1[1] + (SIZE2[1] - SIZE1[1]) * t) / 2
        corner = (bx + t * shift[0], by + t * shift[1])  # type: ignore[index]
        radius, cut = r1 + (r2 - r1) * t, c1 + (c2 - c1) * t
        expected = radius * (SQRT2 - 1) if radius else (cut / SQRT2 if cut else 0.0)
        assert float(tree(*corner, z)) == pytest.approx(expected, abs=1e-9), (
            f"{label} at t={t}: the corner is {float(tree(*corner, z))} outside, expected {expected}"
        )


def test_a_shift_does_not_inflate_the_box() -> None:
    """The bound is a declaration, and this one was over by the whole shift (SPEC S-2b).

    `shift` moves the **top** section only, so the widest point in each direction is whichever end
    reaches furthest -- not either end plus the whole shift. The bound added it to the bottom
    half-size and reported a 28-wide box for a solid 20 wide. That is the defect `cyl` carried
    until T40, in a second shape, because each shape writes its own bound beside its own field
    rather than measuring one from the other.
    """
    from pybosl2 import solid as facade
    from pybosl2 import use_backend

    for shift in ([4, 0], [0, 4], [3, -2]):
        boxes = {}
        for backend in ("csg", "sdf"):
            with use_backend(backend):
                box = facade.prismoid(size1=[20, 20], size2=[10, 10], height=10, shift=shift).bounds()
                boxes[backend] = [round(v, 2) for v in (*box.size, *box.center)]
        assert boxes["csg"] == pytest.approx(boxes["sdf"], abs=0.05), f"shift={shift}: {boxes}"


def test_a_rounding_and_a_chamfer_together_are_refused() -> None:
    """SPEC G-7: one kind, one size, and no guessing which the caller meant."""
    from pybosl2.exceptions import Bosl2ValueError

    with pytest.raises(Bosl2ValueError, match="both chamfer and rounding"):
        sdf.prismoid(SIZE1, SIZE2, height=HEIGHT, rounding=2, chamfer=2)

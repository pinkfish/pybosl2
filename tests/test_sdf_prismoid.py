# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The prismoid, and the rectangular tube that is two of them.

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

`rect_tube` is the same shape twice: an outer prismoid with an inner one taken out of it, on both
backends. Fifteen of its arguments were refused here, and every one of them was an argument of the
two prismoids it is made of -- so once the prismoid could taper, shear and treat its edges there
was nothing left to write but the subtraction. What there *was* to write was somewhere to put the
eighty lines of rule that get from its twenty-odd arguments to those two shapes, which is
`pybosl2._helpers.resolve_rect_tube`: shared, because both backends need every line of it.
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


# --- rect_tube: the same shape twice ----------------------------------------------------------

TUBES = [
    ("a wall thickness", {"size": 20, "wall": 2}),
    ("a stated bore", {"size": 20, "isize": 14}),
    ("a tapered outside", {"size1": [20, 20], "size2": [14, 14], "wall": 2}),
    ("a tapered bore", {"size": 20, "isize1": [14, 14], "isize2": [10, 10]}),
    ("a shear", {"size": 20, "wall": 2, "shift": [3, -2]}),
    ("rounded corners", {"size": 20, "wall": 2, "rounding": 3}),
    ("chamfered corners", {"size": 20, "wall": 2, "chamfer": 3}),
    ("a rounding that grows", {"size": 20, "wall": 2, "rounding1": 1, "rounding2": 4}),
    ("a bore rounded its own way", {"size": 20, "wall": 3, "rounding": 3, "inner_rounding": 1}),
    ("all of it at once", {"size1": [24, 24], "size2": [16, 16], "wall": 2, "rounding": 2, "shift": [3, 0]}),
]


@pytest.mark.parametrize(("label", "kwargs"), TUBES)
def test_a_tube_is_placed_and_sized_the_same_on_both_backends(label: str, kwargs: dict[str, object]) -> None:
    """Fifteen of `rect_tube`'s arguments were refused, and all fifteen belong to its two prismoids."""
    from pybosl2 import solid as facade
    from pybosl2 import use_backend

    boxes = {}
    for backend in ("csg", "sdf"):
        with use_backend(backend):
            box = facade.rect_tube(height=10, **kwargs).bounds()
            boxes[backend] = [round(v, 2) for v in (*box.size, *box.center)]
    assert boxes["csg"] == pytest.approx(boxes["sdf"], abs=0.05), f"{label}: {boxes}"


def test_a_sheared_solid_is_not_centred_on_the_origin() -> None:
    """The bound defect, third attempt -- and the first two were both wrong, differently.

    `shift` moves the top section only, so a sheared prismoid's box is neither the plain box nor a
    symmetric widening of it. The first version added the whole shift to the *bottom* half-size
    (28 wide for a solid 20 wide); the second got the width right and kept the box **symmetric**,
    which is only true when one end dominates in both directions -- and the T43 tests happened to
    use exactly that case, so they passed. The box is measured from the eight corners now, and the
    anchor with it.

    Both were the class of defect S-2b records: an SDF shape's `bounds()` is a claim, and one
    written by hand beside a field is a claim nothing checked.
    """
    from pybosl2 import solid as facade
    from pybosl2 import use_backend

    for shape, kwargs in (
        ("prismoid", {"size1": [20, 20], "size2": [20, 20], "shift": [3, -2]}),
        ("prismoid", {"size1": [20, 20], "size2": [16, 16], "shift": [6, 0]}),
        ("rect_tube", {"size": 20, "wall": 2, "shift": [3, -2]}),
    ):
        boxes = {}
        for backend in ("csg", "sdf"):
            with use_backend(backend):
                box = getattr(facade, shape)(height=10, **kwargs).bounds()
                boxes[backend] = [round(v, 2) for v in (*box.size, *box.center)]
        assert boxes["csg"] == pytest.approx(boxes["sdf"], abs=0.05), f"{shape} {kwargs}: {boxes}"
        assert boxes["sdf"][3] != 0 or boxes["sdf"][4] != 0, "a sheared solid is off-centre, and the box has to say so"


@pytest.mark.parametrize(("label", "kwargs"), TUBES)
def test_the_bore_goes_all_the_way_through(label: str, kwargs: dict[str, object]) -> None:
    """A tube with no hole passes every bounding-box comparison there is.

    The box is the outer prismoid's, so nothing about the subtraction shows up in it -- and the
    subtraction is the whole shape. This asks the field directly: the axis is empty at every
    height, and a point in the wall is not.
    """
    from pybosl2._helpers import resolve_rect_tube
    from pybosl2.sdf import shapes3d as sdf_shapes

    resolved = resolve_rect_tube(
        kwargs.get("size"),
        kwargs.get("isize"),
        kwargs.get("wall"),
        kwargs.get("size1"),
        kwargs.get("size2"),
        kwargs.get("isize1"),
        kwargs.get("isize2"),
        kwargs.get("rounding", 0),
        kwargs.get("rounding1"),
        kwargs.get("rounding2"),
        kwargs.get("inner_rounding", 0),
        None,
        None,
        kwargs.get("chamfer", 0),
        kwargs.get("chamfer1"),
        kwargs.get("chamfer2"),
        kwargs.get("inner_chamfer", 0),
        None,
        None,
    )
    shift = kwargs.get("shift", [0.0, 0.0])
    tree = sdf_shapes.rect_tube(height=10, anchor=[0, 0, 0], **kwargs)._sdf_fn(lv.x(), lv.y(), lv.z())

    for t in (0.1, 0.5, 0.9):
        z = -5.0 + t * 10.0
        cx, cy = t * shift[0], t * shift[1]  # type: ignore[index]
        assert float(tree(cx, cy, z)) > 0, f"{label} at t={t}: the bore is not open on the axis"
        # Near the bore's edge, on the side the shear moves it towards. The axis probe above
        # cannot see an unsheared bore -- the shifted centre is still well inside it either way --
        # so planting "build the bore without the shift" left this test green until this line.
        bore_x = resolved.isize1[0] / 2 + (resolved.isize2[0] / 2 - resolved.isize1[0] / 2) * t
        assert float(tree(cx + bore_x - 0.5, cy, z)) > 0, (
            f"{label} at t={t}: the bore does not reach its own edge -- is it sheared with the outside?"
        )
        wall_x = (resolved.size1[0] + resolved.isize1[0]) / 4 + (
            (resolved.size2[0] + resolved.isize2[0]) / 4 - (resolved.size1[0] + resolved.isize1[0]) / 4
        ) * t
        assert float(tree(cx + wall_x, cy, z)) < 0, f"{label} at t={t}: there is no wall at x={wall_x}"


def test_a_treatment_that_differs_corner_to_corner_is_refused_by_name() -> None:
    """This backend rounds all four corners alike, and says so rather than using the first one.

    BOSL2 lets `rounding=` be four numbers. The cross-section here is built from one amount, so
    four different ones have no expression to go into -- and quietly applying `values[0]` to all
    four would be the silent wrong answer B-9 exists to prevent.
    """
    from pybosl2.exceptions import Bosl2ValueError
    from pybosl2.sdf import shapes3d as sdf_shapes

    sdf_shapes.rect_tube(height=10, size=20, wall=2, rounding=[2, 2, 2, 2])  # uniform: fine
    with pytest.raises(Bosl2ValueError, match="four different"):
        sdf_shapes.rect_tube(height=10, size=20, wall=2, rounding=[1, 2, 3, 4])


def _round_rect_distance(half: tuple[float, float], radius: float, point: tuple[float, float]) -> float:
    """The 2-D distance to a rounded rectangle, in closed form -- the reference, not the field."""
    ex = abs(point[0]) - (half[0] - radius)
    ey = abs(point[1]) - (half[1] - radius)
    return min(max(ex, ey), 0.0) + math.hypot(max(ex, 0.0), max(ey, 0.0)) - radius


def test_the_bore_corner_is_the_outer_one_set_back_by_the_wall() -> None:
    """The rule that shapes the *hole*, which no bounding box and no wall probe can see.

    When the caller rounds the outside and says nothing about the bore, BOSL2 rounds the bore by
    the same amount less the wall thickness -- so the wall keeps an even thickness round the
    corner instead of thinning at it -- clamped at zero when the wall is thicker than the radius.
    Planting `wall = 0` in that derivation left every other test in this file green.

    Measured at the bore's own sharp corner, against `max(outer, -bore)` computed from the two
    closed forms. Both terms are needed: with a thin wall the *outer* surface is the nearer of the
    two there, so an assertion that named only the bore would be checking the wrong number -- and
    would have passed for the wrong reason on three of these four cases.
    """
    from pybosl2._helpers import resolve_rect_tube
    from pybosl2.sdf import shapes3d as sdf_shapes

    size, bore_binding = 20.0, 0
    for rounding, wall in ((3.0, 1.0), (3.0, 2.0), (4.0, 3.0), (1.0, 2.0)):
        resolved = resolve_rect_tube(
            size,
            None,
            wall,
            None,
            None,
            None,
            None,
            rounding,
            None,
            None,
            0,
            None,
            None,
            0,
            None,
            None,
            0,
            None,
            None,
        )
        inner_radius = resolved.inner_rounding1[0]
        assert inner_radius == pytest.approx(max(0.0, rounding - wall)), "the fixture stopped exercising the set-back"

        corner = (resolved.isize1[0] / 2, resolved.isize1[1] / 2)
        outer_d = _round_rect_distance((resolved.size1[0] / 2, resolved.size1[1] / 2), rounding, corner)
        bore_d = _round_rect_distance((corner[0], corner[1]), inner_radius, corner)
        bore_binding += -bore_d > outer_d

        tree = sdf_shapes.rect_tube(height=10, size=size, wall=wall, rounding=rounding, anchor=[0, 0, 0])._sdf_fn(
            lv.x(), lv.y(), lv.z()
        )
        assert float(tree(*corner, 0.0)) == pytest.approx(max(outer_d, -bore_d), abs=1e-9), (
            f"rounding={rounding}, wall={wall}: the bore's corner is not the outer rounding set back by the wall"
        )
    assert bore_binding >= 1, "no case here is decided by the bore -- the set-back is not being measured"

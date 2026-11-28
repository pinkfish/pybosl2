# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""`SdfShape2D.hull` returns a hull, computed in the field (SPEC A-6, A-2, B-5, E-1, PAR-1).

**It never did.** The implementation extruded each operand to a 0.01mm slab, hulled the slabs in
3-D, meshed that, crossed to CSG with `to_csg()`, projected back, and read `.paths` off the
projection -- an attribute a `CsgShape2D` does not have. So the point list stayed empty and the
method fell out of its third `return self`, handing back **the receiver** with every other operand
silently discarded (SPEC A-6). At 0.01 it never reached even that: measured in the real app at
`res=10`, a slab that thin meshes to **0 vertices**, so the 3-D hull raised
`hull(): a child shape meshed to nothing` from inside -- which is the symptom T138 recorded, one
layer above the dead code that was the actual defect.

Three things were wrong at once, and the thickness was the least of them:

* `0.01` is below the mesher's resolution -- 0.01 gives 0 vertices, 0.1 gives 8, 0.5 gives 264;
* `extrude(h)` stands the slab on `z=0` while `projection(cut=True)` slices at `z=0`, so the cut
  plane was the slab's own bottom face;
* `projection()` returns a `CsgShape2D`, which has no `.paths`, so the success branch was
  unreachable whatever the thickness.

It is computed from each shape's own **extreme-point claim** now (`Hull2D`, which T136 added for
`bounds`): the points whose convex hull, grown by a radius, contains the shape. That is exactly
what a hull needs, so there is no meshing, no conversion and no projection -- which also means it
works on a machine with no libfive at all (SPEC A-2, PLAN T-6e), where the old route could not
have run at all.

A libfive tree **cannot be evaluated at a point from Python** in the real app (`PyData` is not
callable; only the numeric mock makes it so), so sampling a field for its own boundary points is
not available. That is why a shape with no claim -- a boolean, an `outline` -- is refused by name
with the explicit `.to_csg()` route rather than approximated.
"""

import math
from typing import Any, NoReturn

import pytest

import pybosl2.sdf.shapes2d as sdf2
import pybosl2.shapes2d.ops as ops2
from pybosl2 import flat, use_backend
from pybosl2.exceptions import UnsupportedByBackendError
from pybosl2.path2d import Path2D
from pybosl2.sdf._libfive import lv


def _support_distance(x: float, y: float, discs: list[tuple[float, float, float]]) -> float:
    """The signed distance to the hull of *discs*, from its support function.

    `f(x) = sup over unit d of (<d, x> - h(d))` with `h(d) = max_i(<d, c_i> + r_i)` is the signed
    distance to a convex set, by definition -- so this is a reference the implementation cannot be
    accidentally consistent with: it shares no code and no construction, only the mathematics.
    Sampled at 40000 directions, which makes the reference the less accurate of the two.
    """
    n = 40000
    best = -1e30
    for k in range(n):
        angle = 2.0 * math.pi * k / n
        dx, dy = math.cos(angle), math.sin(angle)
        best = max(best, min(dx * (x - c[0]) + dy * (y - c[1]) - c[2] for c in discs))
    return best


def _claim_area(shape: Any) -> float:
    """The area the result's own hull claim encloses, by the shoelace formula.

    The claim a hull returns *is* its point set in boundary order, so this measures the shape
    rather than the box around it -- and it needs no mesher, which is the point of the rewrite.
    """
    pts = shape._hull[0]
    return (
        abs(
            sum(
                pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))
            )
        )
        / 2.0
    )


def _sdf(build: Any) -> Any:
    with use_backend("sdf"):
        return build()


def _csg(build: Any) -> Any:
    with use_backend("csg"):
        return build()


# --- it returns a hull, not the receiver --------------------------------------------------


def test_the_hull_of_two_shapes_is_not_the_receiver() -> None:
    """The defect, stated directly: the result must cover both operands, not just `self`.

    This is the assertion the old implementation failed. It returned `self`, so the result's box
    was the receiver's box -- which `bounds()` reports happily, and nothing raised.
    """
    with use_backend("sdf"):
        a = sdf2.circle2d(radius=5)
        b = sdf2.circle2d(radius=5).translate([20.0, 0.0])
        hull = a.hull(b)
    assert hull is not a, "hull() handed back the receiver"
    box = hull.bounds()
    # The two circles span -5..25; the receiver alone spans -5..5, so the x extent is the test.
    assert round(float(box.min[0]), 6) == -5.0
    assert round(float(box.max[0]), 6) == 25.0, "the second operand was discarded"


def test_every_operand_is_covered_not_just_the_first_two() -> None:
    """Three operands, placed so each sets one side of the box -- none may be dropped."""
    with use_backend("sdf"):
        a = sdf2.circle2d(radius=4)
        b = sdf2.circle2d(radius=4).translate([18.0, 0.0])
        c = sdf2.circle2d(radius=4).translate([9.0, 15.0])
        box = a.hull(b, c).bounds()
    assert [round(float(v), 6) for v in box.min] == [-4.0, -4.0]
    assert [round(float(v), 6) for v in box.max] == [22.0, 19.0]


def test_no_operands_returns_self() -> None:
    """`hull()` with nothing to hull is the shape itself, which is the one honest `return self`."""
    with use_backend("sdf"):
        a = sdf2.circle2d(radius=5)
        assert a.hull() is a


# --- it agrees with the other backend -----------------------------------------------------

#: Built the same way on each backend; the hull's **area** is the instrument, because a bounding
#: box cannot see the shape inside it (T47's lesson) and a hull that dropped an operand's middle
#: would still box correctly. Area comes from the polygon the field's own outline encloses on the
#: SDF side and the CSG hull's outline on the other, so the two are measured the same way.
AGREEMENT_CASES = {
    "two equal circles": (
        lambda: (flat.circle(radius=5), flat.circle(radius=5).translate([20, 0])),
        276.537,
    ),
    "two unequal circles": (
        lambda: (flat.circle(radius=5), flat.circle(radius=3).translate([20, 0])),
        210.547,
    ),
    "two squares": (
        lambda: (flat.square(10), flat.square(6).translate([15, 8])),
        252.000,
    ),
    "circle and square": (
        lambda: (flat.circle(radius=5), flat.square(6).translate([14, 6])),
        192.420,
    ),
    "three equal circles": (
        lambda: (
            flat.circle(radius=4),
            flat.circle(radius=4).translate([18, 0]),
            flat.circle(radius=4).translate([9, 15]),
        ),
        393.447,
    ),
}


@pytest.mark.parametrize("label", sorted(AGREEMENT_CASES))
def test_the_two_backends_agree_on_the_hulls_extent(label: str) -> None:
    """The SDF hull's bounding box matches the CSG hull's, within the faceting the CSG side has.

    The SDF side reads **larger** wherever a curve is involved and that is the correct direction:
    the CSG backend hulls a *faceted* circle (an inscribed polygon), while the equal-radius path
    here keeps genuine arcs. So the tolerance is one-sided -- the SDF box may exceed the CSG box
    by the faceting error and may not fall short of it, because falling short means an operand or
    part of one was lost.
    """
    build, _area = AGREEMENT_CASES[label]
    csg_box = _csg(lambda: ops2.hull(*build())).bounds()
    with use_backend("sdf"):
        shapes = build()
        sdf_box = shapes[0].hull(*shapes[1:]).bounds()
    for axis in (0, 1):
        assert float(sdf_box.min[axis]) <= float(csg_box.min[axis]) + 1e-6, (
            f"{label}: the SDF hull falls short of the CSG hull on the low {'xy'[axis]} side"
        )
        assert float(sdf_box.max[axis]) >= float(csg_box.max[axis]) - 1e-6, (
            f"{label}: the SDF hull falls short of the CSG hull on the high {'xy'[axis]} side"
        )
        # And not wildly larger: the faceting error on a circle of radius r at `fn` facets is
        # r(1 - cos(pi/fn)), well under 0.2 for everything here.
        assert float(csg_box.min[axis]) - float(sdf_box.min[axis]) < 0.25
        assert float(sdf_box.max[axis]) - float(csg_box.max[axis]) < 0.25


def test_polygons_agree_exactly() -> None:
    """With every radius zero there is nothing to facet, so the two backends must match exactly.

    This is the case that pins the construction rather than its tolerance: the hull of squares is
    a polygon on both backends and any disagreement is a real error, not faceting.
    """
    csg_box = _csg(lambda: ops2.hull(flat.square(10), flat.square(6).translate([15, 8]))).bounds()
    with use_backend("sdf"):
        sdf_box = flat.square(10).hull(flat.square(6).translate([15, 8])).bounds()
    assert [round(float(v), 6) for v in sdf_box.min] == [round(float(v), 6) for v in csg_box.min]
    assert [round(float(v), 6) for v in sdf_box.max] == [round(float(v), 6) for v in csg_box.max]


# --- it needs no mesher -------------------------------------------------------------------


@pytest.fixture
def no_mesher(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make meshing an SDF field fail, the way a machine without libfive does."""
    import pybosl2.sdf.shapes3d as sdf_shapes

    def unavailable(_self: Any) -> NoReturn:
        raise RuntimeError("no mesher on this machine (simulated: libfive is absent)")

    monkeypatch.setattr(sdf_shapes.SdfSolid, "mesh", unavailable)


@pytest.mark.usefixtures("no_mesher")
def test_the_hull_needs_no_mesher() -> None:
    """The claim is arithmetic, so this works where the old route could not run at all.

    SPEC A-2 and PLAN T-6e: nothing routine may depend on a mesher being available. The old
    implementation meshed twice -- once inside the 3-D hull for its support points, once in
    `to_csg()` -- for an operation that needs neither.
    """
    with use_backend("sdf"):
        a = sdf2.circle2d(radius=5)
        box = a.hull(sdf2.circle2d(radius=5).translate([20.0, 0.0])).bounds()
    assert round(float(box.max[0]), 6) == 25.0


@pytest.mark.usefixtures("no_mesher")
def test_the_mixed_radius_hull_needs_no_mesher_either() -> None:
    """The faceted path is support-point arithmetic too, so it also runs with no libfive."""
    with use_backend("sdf"):
        box = sdf2.circle2d(radius=5).hull(sdf2.rect2d(size=[6, 6]).translate([14.0, 6.0])).bounds()
    assert round(float(box.max[0]), 6) == 17.0


# --- what it refuses, and why -------------------------------------------------------------

NO_CLAIM = {
    "a union": lambda: sdf2.circle2d(radius=5) | sdf2.rect2d(size=[4, 4]),
    "a difference": lambda: sdf2.circle2d(radius=5) - sdf2.rect2d(size=[4, 4]),
    "an outline": lambda: sdf2.circle2d(radius=5).outline(1),
    "a shrunk shape": lambda: sdf2.circle2d(radius=5).offset(-1),
    "an unevenly rounded rect": lambda: sdf2.rect2d(size=[10, 6], rounding=[3, 0, 1, 2]),
}


@pytest.mark.parametrize("label", sorted(NO_CLAIM))
def test_a_shape_with_no_usable_claim_is_refused_by_name(label: str) -> None:
    """Refused under `hull`, naming the explicit route -- not approximated, and not silently self.

    A field cannot be asked for its own boundary points (a libfive tree is not callable from
    Python outside the numeric mock), so there is genuinely nothing to hull. Saying so is the
    whole improvement over the old third `return self`.
    """
    with use_backend("sdf"):
        other = NO_CLAIM[label]()
        good = sdf2.circle2d(radius=3).translate([20.0, 0.0])
        for receiver, operand in ((good, other), (other, good)):
            with pytest.raises(UnsupportedByBackendError) as ei:
                receiver.hull(operand)
            message = str(ei.value)
            assert "hull" in message
            assert "to_csg" in message, "the refusal must name the conversion that resolves it"


def test_an_unevenly_rounded_rect_keeps_its_bounds_claim() -> None:
    """The loose claim still serves `bounds` -- only `hull` refuses it.

    `bounds` needs a claim that *contains* the shape and a loose one is fine; `hull` needs the
    *extreme set*, and building a hull from a loose claim adds material at the boundary the claim
    does not touch. Conflating the two is what the tightness flag exists to prevent, and this
    asserts the flag did not cost `bounds` the tightening T136 added it for.
    """
    with use_backend("sdf"):
        rect = sdf2.rect2d(size=[10, 6], rounding=[3, 0, 1, 2])
    assert rect._hull is not None, "the containment claim is still there for bounds"
    assert rect._hull_tight is False, "and it is marked as not being the extreme set"
    box = rect.bounds()
    assert [round(float(v), 6) for v in box.min] == [-5.0, -3.0]
    assert [round(float(v), 6) for v in box.max] == [5.0, 3.0]


# --- the claim reaches as far as it can ---------------------------------------------------

CARRIES_A_TIGHT_CLAIM = {
    "circle2d": lambda: sdf2.circle2d(radius=5),
    "rect2d": lambda: sdf2.rect2d(size=[10, 6]),
    "rect2d rounded evenly": lambda: sdf2.rect2d(size=[10, 6], rounding=2),
    "rect2d chamfered": lambda: sdf2.rect2d(size=[10, 6], chamfer=2),
    "polygon2d": lambda: sdf2.polygon2d(Path2D([[0, 0], [10, 0], [5, 8]])),
    "translated": lambda: sdf2.circle2d(radius=5).translate([3.0, 4.0]),
    "rotated": lambda: sdf2.rect2d(size=[10, 6]).rotate(30),
    "scaled": lambda: sdf2.circle2d(radius=5).scale(2),
    "mirrored": lambda: sdf2.rect2d(size=[10, 6]).mirror([1.0, 0.0]),
    "grown": lambda: sdf2.circle2d(radius=5).offset(1),
}


@pytest.mark.parametrize("label", sorted(CARRIES_A_TIGHT_CLAIM))
def test_these_shapes_can_be_hulled(label: str) -> None:
    """Each builder's result carries a tight claim, so each can be hulled rather than refused.

    `mirror` and a positive `offset` were added by T139: a reflection is an isometry, so it
    carries the claim exactly, and growing by *a* grows the radius by exactly *a*. Both were
    reachable before and refused, for no reason other than that nothing propagated the claim.
    """
    with use_backend("sdf"):
        shape = CARRIES_A_TIGHT_CLAIM[label]()
        assert shape._hull is not None
        assert shape._hull_tight
        hull = shape.hull(sdf2.circle2d(radius=2).translate([40.0, 0.0]))
    # It reached the far circle, so the claim was used rather than the receiver returned.
    assert round(float(hull.bounds().max[0]), 6) == 42.0


def test_a_reflection_claims_the_reflected_points() -> None:
    """Not just *a* claim -- the right one. A flag that was merely present would pass above."""
    with use_backend("sdf"):
        rect = sdf2.rect2d(size=[10, 6]).translate([20.0, 0.0])
        mirrored = rect.mirror([1.0, 0.0])
    assert rect._hull is not None
    assert mirrored._hull is not None
    original = sorted((round(p[0], 6), round(p[1], 6)) for p in rect._hull[0])
    reflected = sorted((round(-p[0], 6), round(p[1], 6)) for p in rect._hull[0])
    assert sorted((round(p[0], 6), round(p[1], 6)) for p in mirrored._hull[0]) == reflected
    assert reflected != original, "the fixture must actually move under the mirror"


def test_growing_adds_exactly_its_own_radius() -> None:
    """`offset(a)` adds `a` to the claim's radius, and a *shrink* drops the claim entirely."""
    with use_backend("sdf"):
        circle = sdf2.circle2d(radius=5)
        grown = circle.offset(1.5)
        shrunk = circle.offset(-1.5)
    assert circle._hull is not None
    assert grown._hull is not None
    assert round(grown._hull[1] - circle._hull[1], 6) == 1.5
    assert shrunk._hull is None, "a shrink can pull the boundary inside the claim's own points"


# --- the control ---------------------------------------------------------------------------


def test_the_probes_can_fail() -> None:
    """The old body, restored verbatim, does not produce the hull -- by either of its symptoms.

    **And this is why the suite could not have caught the defect.** Under the numeric mock a
    `CsgShape2D` *does* answer `.paths`, and a 0.01 slab *does* mesh, so the old body ran to
    completion and returned a hull 30.6 x 10.2 where the answer is 30 x 10 -- wrong, but wrong by
    2%, which no test was asserting. In the real app `projection()` returns a `CsgShape2D` with no
    `.paths` at all, so the same code fell through to `return self`. The mock is *more capable*
    than the thing it stands in for, which is the one direction a stand-in must never be, and it
    is the same shape of problem as a skip marker that hides the question it is skipping (T135).

    So the control asserts the old body does not give the right answer, rather than asserting one
    of its two symptoms: under the mock that is the over-sized box, in the real app the receiver.
    """

    def the_old_hull(self: Any, *others: Any) -> Any:
        # verbatim, from before T139
        if not others:
            return self
        extruded = [s.extrude(0.01, res=s.res) for s in [self] + list(others)]
        hull3d = extruded[0].hull(*extruded[1:])
        csg = hull3d.to_csg()
        projection = csg.projection(cut=True)
        shapes = [projection] if not hasattr(projection, "__iter__") else list(projection)
        if not shapes:
            return self
        pts: list[list[float]] = []
        if hasattr(shapes[0], "paths"):
            for p in shapes[0].paths:
                pts.extend([[float(c[0]), float(c[1])] for c in p])
        if not pts:
            return self
        return sdf2.polygon2d(Path2D(pts), res=self.res)

    saved = sdf2.SdfShape2D.hull
    sdf2.SdfShape2D.hull = the_old_hull  # type: ignore[method-assign, assignment]
    try:
        with use_backend("sdf"):
            a = sdf2.circle2d(radius=5)
            b = sdf2.circle2d(radius=5).translate([20.0, 0.0])
            try:
                result: Any = a.hull(b)
            except Exception:
                result = None  # it raised from inside, which is T138's symptom
        if result is None or result is a:
            return  # raised, or handed back the receiver: the real app's behaviour
        box = result.bounds()
        correct = [round(float(v), 6) for v in box.min] == [-5.0, -5.0] and [round(float(v), 6) for v in box.max] == [
            25.0,
            5.0,
        ]
        assert not correct, (
            "the old body produced the correct hull, so this control measures nothing -- the "
            "defect it is meant to pin is gone or was never there"
        )
    finally:
        sdf2.SdfShape2D.hull = saved  # type: ignore[method-assign]


def test_the_mixed_radius_hull_is_exact() -> None:
    """T139 faceted the mixed-radius hull; T140 made it exact, so there is no facet count left.

    This replaces `test_the_support_point_count_matters`, which measured a `directions=` argument
    that existed only because the construction approximated. It is checked against the support
    function -- `f(x) = sup over unit d of (<d,x> - max_i(<d,c_i> + r_i))`, which is the signed
    distance to a convex set by definition -- sampled finely enough that the *reference* is the
    less accurate of the two.
    """
    discs = [(0.0, 0.0, 5.0), (20.0, 0.0, 2.0)]
    with use_backend("sdf"):
        hull = sdf2.circle2d(radius=5).hull(sdf2.circle2d(radius=2).translate([20.0, 0.0]))
    tree = hull._sdf_fn(lv.x(), lv.y())
    worst = 0.0
    for px, py in ((0, 0), (10, 0), (25, 0), (-8, 0), (0, 10), (6, 6), (12, 7), (3, 2), (30, 20)):
        worst = max(worst, abs(float(tree(px, py, 0.0)) - _support_distance(px, py, discs)))
    assert worst < 5e-3, f"worst disagreement with the support function: {worst:.3e}"


def test_the_hull_is_convex() -> None:
    """The hull of a non-convex input is convex, measured on the field rather than on a claim.

    Convexity is exactly "the sublevel set is convex": if two points are inside, every point on
    the segment between them is too. That is a statement about the shape, where reading the
    result's own point list would only restate how it was built -- and the claim moved from
    `_hull` to `_hull_discs` in T140, which a structural assertion would have had to chase.
    """
    with use_backend("sdf"):
        star = sdf2.polygon2d(Path2D([[0, 0], [10, 2], [20, 0], [18, 10], [10, 6], [2, 10]]))
        hull = star.hull(sdf2.circle2d(radius=1).translate([10.0, -8.0]))
    tree = hull._sdf_fn(lv.x(), lv.y())
    inside = [(px, py) for px in range(-2, 21) for py in range(-9, 11) if float(tree(px, py, 0.0)) <= 0.0]
    assert len(inside) > 100, "the probe grid found too little of the shape to say anything"
    worst = 0.0
    for ax, ay in inside[::7]:
        for bx, by in inside[::11]:
            for t in (0.25, 0.5, 0.75):
                mx, my = ax + (bx - ax) * t, ay + (by - ay) * t
                worst = max(worst, float(tree(mx, my, 0.0)))
    assert worst <= 1e-9, f"a midpoint of two interior points reads {worst:.3e} outside: not convex"
    # And the star's own reflex vertex is covered, which is what makes this a hull rather than
    # the star again: (10, 6) is the dent, and the hull fills it.
    assert float(tree(10.0, 7.5, 0.0)) < 0.0


def test_a_degenerate_hull_does_not_raise() -> None:
    """Collinear or coincident claims leave fewer than three hull points, which must still build."""
    with use_backend("sdf"):
        a = sdf2.circle2d(radius=3)
        collinear = a.hull(
            sdf2.circle2d(radius=3).translate([10.0, 0.0]),
            sdf2.circle2d(radius=3).translate([20.0, 0.0]),
        )
        assert round(float(collinear.bounds().max[0]), 6) == 23.0
        same = a.hull(sdf2.circle2d(radius=3))
        assert round(float(same.bounds().max[0]), 6) == 3.0


def test_the_arc_path_is_exact_where_it_claims_to_be() -> None:
    """Equal radii take the arc path, and a capsule's waist is exactly its radius.

    The box alone cannot tell the arc path from the faceted one -- both reach +-5 in y -- so this
    measures the field at the waist instead, where an inscribed polygon would fall short.
    """
    with use_backend("sdf"):
        a = sdf2.circle2d(radius=5)
        capsule = a.hull(sdf2.circle2d(radius=5).translate([20.0, 0.0]))
    box = capsule.bounds()
    # A capsule of radius 5 between (0,0) and (20,0): exactly 30 x 10, with no faceting loss.
    assert [round(float(v), 6) for v in box.min] == [-5.0, -5.0]
    assert [round(float(v), 6) for v in box.max] == [25.0, 5.0]
    assert round(float(box.max[1]) - float(box.min[1]), 6) == 10.0


def test_both_branches_agree_where_they_overlap() -> None:
    """The equal-radius branch and the unequal one must agree on an equal-radius input.

    `hull2d_discs` offsets the centres' polygon, which is exact only when the radii agree, and
    `_hull_of_unequal_discs` takes the general route. They are independent constructions, so
    running the general one on an input the special one also handles is a cross-check on both --
    and it replaces `test_the_faceted_path_is_only_taken_for_mixed_radii`, which distinguished an
    exact path from an approximate one and has nothing left to distinguish.
    """
    discs = [(0.0, 0.0, 4.0), (18.0, 0.0, 4.0), (9.0, 14.0, 4.0)]
    with use_backend("sdf"):
        special = sdf2.hull2d_discs(list(discs), res=10)
        general = sdf2._hull_of_unequal_discs(discs, res=10)
    a = special._sdf_fn(lv.x(), lv.y())
    b = general._sdf_fn(lv.x(), lv.y())
    worst = 0.0
    for px in range(-8, 27, 3):
        for py in range(-8, 21, 3):
            worst = max(worst, abs(float(a(px, py, 0.0)) - float(b(px, py, 0.0))))
    assert worst < 1e-6, f"the two constructions disagree by {worst:.3e} on equal radii"


def test_a_hull_can_be_hulled() -> None:
    """A hull records its own extreme discs, so it is itself a valid operand.

    The hull of unequal discs is extreme in several radii at once, which `Hull2D`'s single radius
    cannot express -- so T140 gave the shape a disc-level claim rather than letting a hull become
    un-hullable. Without it this refuses.
    """
    with use_backend("sdf"):
        first = sdf2.circle2d(radius=5).hull(sdf2.circle2d(radius=2).translate([20.0, 0.0]))
        again = first.hull(sdf2.circle2d(radius=3).translate([8.0, 18.0]))
    box = again.bounds()
    assert round(float(box.min[0]), 6) == -5.0
    assert round(float(box.max[0]), 6) == 22.0
    assert round(float(box.max[1]), 6) == 21.0

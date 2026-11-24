# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The cylinder rim is the same profile on both backends (SPEC PAR-4, PAR-5).

`chamfer_angle`, `from_end` and `extra` -- each in an overall/bottom/top triple -- were 45 of the
88 option gaps left after T41, and all 45 are one implementation: `cyl`, `cylinder`, `zcyl`,
`xcyl` and `ycyl` are one field with five spellings.

The CSG backend builds the rim as a **2-D profile** (`cyl_profile`) that gets rotate-extruded, so
there is an exact statement available and these tests make it: **the field is zero at every vertex
of the profile CSG revolves.** Not close, zero. The profile is the specification, and the field
either passes through it or it does not.

That is what caught the defect this file's third test records: the two backends disagreed by
0.39mm on a tapered cone with a treated rim, and had since the rim treatment was written. Nothing
noticed because a bounding box cannot see it and every earlier test used a plain cylinder, where
the two constructions coincide.
"""

from __future__ import annotations

import math

import pytest
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon

import pybosl2.sdf.shapes3d as sdf
from pybosl2.sdf._libfive import lv
from pybosl2.shapes3d.cylinder import cyl_profile

#: Local ``(x, y, z)`` to world, per axis -- the rotations `xcyl` and `ycyl` apply on the CSG side.
TO_WORLD = {
    0: lambda lx, ly, lz: (lz, ly, -lx),
    1: lambda lx, ly, lz: (lx, lz, -ly),
    2: lambda lx, ly, lz: (lx, ly, lz),
}


def _worst_on_profile(
    builder,
    axis: int,
    *,
    height: float = 20.0,
    radius1: float = 8.0,
    radius2: float = 8.0,
    **rim: object,
) -> float:
    """Return the largest |field| at the vertices of the profile the CSG backend revolves."""
    profile = cyl_profile(radius1, radius2, height, **rim)  # type: ignore[arg-type]
    shape = builder(height=height, radius1=radius1, radius2=radius2, anchor=[0, 0, 0], **rim)
    tree = shape._sdf_fn(lv.x(), lv.y(), lv.z())

    points = [(r, z) for r, z in profile if r > 1e-9]  # the two on the axis are interior
    # Midpoints of the *straight* segments too, not only the vertices. A chord of the arc would
    # sit slightly inside the true circle, which is faceting rather than a defect, so only
    # axis-aligned segments qualify -- the end faces, the wall, and the flat a clipped fillet ends
    # in. That flat is why: everything about it except its two endpoints lives in its interior, so
    # a vertex-only probe passed with the clipped fillet's depth wrong *and* with its union turned
    # into an intersection.
    for (r1, z1), (r2, z2) in zip(points, points[1:], strict=False):
        if math.isclose(r1, r2, abs_tol=1e-9) or math.isclose(z1, z2, abs_tol=1e-9):
            points.append(((r1 + r2) / 2, (z1 + z2) / 2))

    worst, sampled = 0.0, 0
    for r, z in points:
        for angle in (0.0, 1.0, 2.5):
            worst = max(worst, abs(float(tree(*TO_WORLD[axis](r * math.cos(angle), r * math.sin(angle), z)))))
            sampled += 1
    assert sampled >= 6, f"only {sampled} profile points to check -- this measures nothing"
    return worst


@pytest.mark.parametrize(
    ("label", "rim"),
    [
        ("the 45 degree default", {"chamfer1": 2, "chamfer2": 2}),
        ("a shallow angle", {"chamfer1": 2, "chamfer2": 2, "chamfer_angle1": 30, "chamfer_angle2": 30}),
        ("a steep angle", {"chamfer1": 2, "chamfer2": 2, "chamfer_angle1": 60, "chamfer_angle2": 60}),
        ("measured from the end", {"chamfer1": 2, "chamfer2": 2, "from_end1": True, "from_end2": True}),
        (
            "from the end at an angle",
            {
                "chamfer1": 2,
                "chamfer2": 2,
                "chamfer_angle1": 30,
                "chamfer_angle2": 30,
                "from_end1": True,
                "from_end2": True,
            },
        ),
        ("a different rim at each end", {"chamfer1": 2, "chamfer2": 3, "chamfer_angle1": 30, "chamfer_angle2": 60}),
        ("a rounding", {"rounding1": 2, "rounding2": 2}),
    ],
)
def test_the_chamfer_is_the_profile_csg_revolves(label: str, rim: dict[str, object]) -> None:
    """`chamfer_angle=` and `from_end=` are two ways of stating one cut, and both now cross.

    BOSL2 states a chamfer either as its radial leg with an angle (`from_end=False`, the default)
    or as the cut's own length split by that angle (`from_end=True`). This backend could express
    neither: its chamfer was the plane `(qu + qv + c) / sqrt(2)`, a symmetric 45-degree cut with
    the angle nowhere in it. The general plane through `(-dx, 0)` and `(0, -dy)` reduces to
    exactly that when `dx == dy`, which is why the default case still passes unchanged.
    """
    worst = _worst_on_profile(sdf.cyl, 2, **rim)
    assert worst == pytest.approx(0.0, abs=1e-9), f"{label}: worst |field| on the profile is {worst}"


@pytest.mark.parametrize(("name", "axis"), [("cyl", 2), ("cylinder", 2), ("zcyl", 2), ("xcyl", 0), ("ycyl", 1)])
def test_all_five_spellings_build_the_same_rim(name: str, axis: int) -> None:
    """One field, five names -- so the options reach all five or none of them.

    45 of the 88 gaps were these nine options times these five shapes. They are not five pieces of
    work: `cylinder` and `zcyl` are `cyl`, and `xcyl` and `ycyl` are the same field about another
    axis. Counting per option and per shape is what made that look like 45 things to do.
    """
    worst = _worst_on_profile(getattr(sdf, name), axis, chamfer1=2, chamfer2=3, chamfer_angle1=30, from_end2=True)
    assert worst == pytest.approx(0.0, abs=1e-9), f"{name}: worst |field| on the profile is {worst}"


@pytest.mark.parametrize(
    ("radius2", "rim"),
    [
        (4.0, {"chamfer1": 2, "chamfer2": 2}),
        (4.0, {"rounding1": 2, "rounding2": 2}),
        (4.0, {"chamfer1": 2, "chamfer2": 2, "chamfer_angle1": 30, "chamfer_angle2": 30}),
        (5.0, {"rounding1": 1.5, "rounding2": 2.5}),
        (12.0, {"chamfer1": 1, "chamfer2": 3, "chamfer_angle2": 60}),
        # Steep tapers with a rounding at the **narrow** end -- where the wall line falls inside
        # the near-vertical arc. These read 0.51 and 0.88 until the rim candidates were given
        # their own axial bands (T127); every other case here passed throughout.
        (20.0, {"rounding1": 3}),
        (20.0, {"radius1": 4.0, "rounding1": 3, "rounding2": 1}),
    ],
)
def test_a_treated_rim_moves_the_wall_of_a_cone(radius2: float, rim: dict[str, object]) -> None:
    """The defect this file was written to find, and it was there before any of this work.

    BOSL2's profile puts a chamfer's or a rounding's inner endpoint at the **nominal** end radius
    and runs the wall from there to the other end's endpoint. So a treated cone's wall is *not*
    the line through its two nominal corners -- and this backend measured against that nominal
    line, building a different cone from the same call: 0.39mm out on an 8-to-4 taper with a 2mm
    chamfer, and the same for a rounding.

    On a plain cylinder the wall is vertical and an axial inset cannot move it, so the two
    constructions coincide -- which is why every earlier test passed. A bounding box cannot see it
    either: the box is set by the widest ring, and the wall between the rims does not touch it.
    """
    worst = _worst_on_profile(sdf.cyl, 2, radius2=radius2, **rim)
    assert worst == pytest.approx(0.0, abs=1e-9), f"taper to {radius2}: worst |field| is {worst}"


#: Points per axis in the ``(r, z)`` half-plane sweep below, and the angles each is tried at.
#: 24x24 over the profile's own bounding box, which is 200-400 points inside a typical profile --
#: enough that a missing half, a missing quadrant or a missing slice cannot slip between them.
PROFILE_GRID = 24
PROFILE_ANGLES = (0.0, 2.0)

#: How much further inside the profile than its own discretisation a sample point has to be
#: before its field value means anything. A point that lands exactly *on* the slanted wall reads
#: zero, correctly, and shapely's `contains` is happy to call it interior -- with a grid this
#: round that happens, so "strictly inside" has to mean strictly.
INTERIOR_FLOOR = 1e-6


def _profile_discretisation(radius1: float, radius2: float, height: float, rim: dict[str, object]) -> float:
    """Return how far the profile CSG revolves can sit from the ideal one it approximates.

    Measured, not chosen: the same profile is built again at `fn=512` and the two are compared.
    A plain or chamfered profile is already exact and this is 0; a rounding's arc is a polyline
    and this is its chord sagitta.
    """
    fine = dict(rim)
    fine.setdefault("fn", 512)
    coarse = Polygon(cyl_profile(radius1, radius2, height, **rim))  # type: ignore[arg-type]
    exact = Polygon(cyl_profile(radius1, radius2, height, **fine))  # type: ignore[arg-type]
    return float(coarse.exterior.hausdorff_distance(exact.exterior))


def _worst_inside_profile(
    builder,
    axis: int,
    *,
    height: float = 20.0,
    radius1: float = 8.0,
    radius2: float = 8.0,
    **rim: object,
) -> tuple[float, int]:
    """Return the largest field value at a point the CSG profile puts *inside* the solid, and how many.

    The mirror of `_worst_on_profile`, and it is one-sided for the mirror-image reason. CSG
    revolves this polygon exactly, so the polygon is not an approximation of the solid in this
    plane -- it *is* it, up to the chord sagitta `_profile_discretisation` measures. A rounding's
    chords are inscribed in its arc, so they can only make the polygon smaller than the ideal
    shape; a point strictly inside the polygon is therefore inside the ideal shape too, and a
    field that reads it positive is missing material. No tolerance is needed for that direction,
    and `field > 0` is the whole assertion.
    """
    profile = cyl_profile(radius1, radius2, height, **rim)  # type: ignore[arg-type]
    polygon = Polygon(profile)
    margin = _profile_discretisation(radius1, radius2, height, rim)
    shape = builder(height=height, radius1=radius1, radius2=radius2, anchor=[0, 0, 0], **rim)
    tree = shape._sdf_fn(lv.x(), lv.y(), lv.z())

    r_lo, z_lo, r_hi, z_hi = polygon.bounds
    worst, sampled = -math.inf, 0
    for i in range(PROFILE_GRID):
        r = r_lo + (r_hi - r_lo) * (i + 0.5) / PROFILE_GRID
        for j in range(PROFILE_GRID):
            z = z_lo + (z_hi - z_lo) * (j + 0.5) / PROFILE_GRID
            point = ShapelyPoint(r, z)
            if not polygon.contains(point) or polygon.exterior.distance(point) <= margin + INTERIOR_FLOOR:
                continue
            for angle in PROFILE_ANGLES:
                world = TO_WORLD[axis](r * math.cos(angle), r * math.sin(angle), z)
                worst = max(worst, float(tree(*world)))
                sampled += 1
    return worst, sampled


@pytest.mark.parametrize(
    ("label", "shape"),
    [
        ("a plain cylinder -- the case that always worked", {}),
        ("a cone widening upward", {"radius2": 12.0}),
        ("a cone narrowing upward", {"radius2": 4.0}),
        ("a cone to a point", {"radius2": 0.0}),
        ("a cone from a point", {"radius1": 0.0, "radius2": 8.0}),
        ("a shallow taper", {"radius2": 8.5}),
        ("a tapered rim, chamfered", {"radius2": 4.0, "chamfer1": 2, "chamfer2": 2}),
        ("a tapered rim, rounded", {"radius2": 4.0, "rounding1": 2, "rounding2": 2}),
        ("a widening cone, chamfered", {"radius2": 12.0, "chamfer1": 2, "chamfer2": 2}),
        ("a widening cone, rounded", {"radius2": 12.0, "rounding1": 2, "rounding2": 2}),
        ("a rim treated at one end only", {"radius2": 4.0, "rounding1": 2}),
        ("a steep taper rounded at its narrow end", {"radius2": 20.0, "rounding1": 3}),
    ],
)
def test_the_solid_fills_the_profile_csg_revolves(label: str, shape: dict[str, float]) -> None:
    """A tapered cylinder lost the half that ends at its narrower rim, and had from the start.

    `_cyl_edge_sdf` builds each rim as a corner in the ``(radial - r_ref, |axial| - hb)`` frame --
    the end's own radius read as a vertical half-width -- and intersects the two with the wall.
    On an untapered cylinder that vertical line **is** the wall, so the rim term was redundant and
    correct. On a taper it is not: the bottom half was cut to `radius1` and the top half to
    `radius2`, so a cone was a pair of stepped cylinders with its narrow half's flare missing.
    An 8-to-2 cone read **+1.96** at a point 0.44 inside it, and `cyl(diameter1=0)` -- a plain
    cone, which is what `RobertsonMask` cuts with -- had its entire lower half collapsed onto the
    axis. The fix measures the corner from the wall line instead, which for `radius1 == radius2`
    reduces to `radial - radius1` exactly, every untapered cylinder evaluates identically -- the
    rounding branch gains a term, but `{radial <= R} & {|axial| <= hb - a}` is a *subset* of the
    rounded rectangle, so the larger region's distance is never the greater and the `min` always
    takes the rectangle.

    **Why four earlier guards missed it, all four for the same reason:** a cone's defect lives in
    the *interior* of its wall, and every one of them only ever looked at the ends.

    * `_worst_on_profile` above samples the profile's **vertices**, plus the midpoints of its
      *axis-aligned* segments. A cone's wall is the one straight segment that is not axis-aligned,
      so its midpoint was skipped -- the rule was written to keep arc chords out, and a slanted
      wall is not an arc. Every vertex it did sample is a point where `radial - r_ref == 0`, which
      reads zero whether the term means anything or not.
    * `bounds()` is analytic on both backends and agrees.
    * `tests/test_every_part_field_evaluates.py` probes the **CSG mesh's vertices** against the
      field. A cone's mesh vertices are its apex and its two end rings -- the same corners again.
    * That file's one remaining recorded disagreement, `RobertsonMask` at 2.008, *was* this bug
      seen through a boolean: intersecting the collapsed cone with a prismoid left 22 of the 27
      vertices outside the field. It was recorded as a known difference rather than chased.

    So this test asks the complementary question -- not "is every mesh vertex in the field?" but
    "is every point of the solid in the field?" -- and a missing interior is exactly what the
    one-sided vertex probes cannot express (SPEC PAR-1, PAR-5).

    **Its sensitivity is bounded by the grid, and one case here is below it.** Reverting the fix
    fails every case above but two: the plain cylinder, which is the control, and the shallow
    8-to-8.5 taper, whose missing sliver is 0.25mm against a 0.354mm grid step. A sweep cannot see
    a defect thinner than its own spacing, so the shallow taper is pinned by
    `test_the_wall_of_a_cone_is_where_both_backends_put_it` below, which samples *on* the wall and
    is sharp at any taper. It is kept here as well because the ratio is what makes it readable.
    """
    worst, sampled = _worst_inside_profile(sdf.cyl, 2, **shape)
    assert sampled >= 100, f"{label}: only {sampled} interior points -- this measures nothing"
    assert worst < 0.0, f"{label}: a point inside the profile reads {worst:+.5f} -- outside the field"


@pytest.mark.parametrize(("name", "axis"), [("cyl", 2), ("cylinder", 2), ("zcyl", 2), ("xcyl", 0), ("ycyl", 1)])
def test_all_five_spellings_fill_their_cone(name: str, axis: int) -> None:
    """One field, five names -- so the taper is whole in all five or none of them.

    `cylinder` and `zcyl` are `cyl`; `xcyl` and `ycyl` are the same field about another axis. All
    five reached `_cyl_edge_sdf`, so all five lost the same half.
    """
    worst, sampled = _worst_inside_profile(getattr(sdf, name), axis, radius1=8.0, radius2=3.0)
    assert sampled >= 100, f"{name}: only {sampled} interior points -- this measures nothing"
    assert worst < 0.0, f"{name}: a point inside the profile reads {worst:+.5f} -- outside the field"


def test_the_wall_of_a_cone_is_where_both_backends_put_it() -> None:
    """The sharp statement, on the segment the midpoint rule skipped.

    `_worst_on_profile` admits the midpoint of an *axis-aligned* profile segment because a chord
    of an arc would sit inside the true curve and that is faceting, not a defect. A cone's wall is
    straight, so every point along it is exact -- and it is the only part of a plain cone's
    profile that the vertices do not already pin.
    """
    for radius1, radius2 in ((8.0, 2.0), (2.0, 8.0), (8.0, 0.0), (0.0, 8.0), (8.0, 8.5), (8.5, 8.0)):
        shape = sdf.cyl(height=20.0, radius1=radius1, radius2=radius2, anchor=[0, 0, 0])
        tree = shape._sdf_fn(lv.x(), lv.y(), lv.z())
        worst = 0.0
        for k in range(1, 20):
            t = k / 20
            r, z = radius1 + (radius2 - radius1) * t, -10.0 + 20.0 * t
            worst = max(worst, abs(float(tree(r, 0.0, z))))
        assert worst == pytest.approx(0.0, abs=1e-9), (
            f"{radius1}-to-{radius2} cone: worst |field| along the wall is {worst}"
        )


@pytest.mark.parametrize(
    "extra",
    [{"extra": 3.0}, {"extra1": 4.0}, {"extra2": 4.0}, {"extra1": 2.0, "extra2": 5.0}],
)
def test_extra_grows_the_solid_past_its_ends_without_moving_it(extra: dict[str, float]) -> None:
    """`extra=` is for cutting: it adds a stub past an end so a difference goes clean through.

    What makes it worth a test rather than a line of code is what it must *not* change -- the
    length, and therefore the anchoring. The stub is unioned on after the shape is built and the
    anchor offset is computed from the nominal length, exactly as on the CSG side.
    """
    from pybosl2 import solid as facade
    from pybosl2 import use_backend

    boxes = {}
    for backend in ("csg", "sdf"):
        with use_backend(backend):
            box = facade.cyl(height=20, radius=8, **extra).bounds()
            boxes[backend] = [round(v, 2) for v in (box.size[2], *box.center)]
    assert boxes["csg"] == pytest.approx(boxes["sdf"], abs=0.05), f"{extra}: {boxes}"


def test_extra_is_a_stub_of_that_ends_radius_not_a_continued_taper() -> None:
    """A cone's stub is straight, at the radius of the end it grows from -- as CSG unions it.

    Continuing the taper instead would be the obvious guess and would be wrong: the point of the
    stub is to sit inside whatever the shape is being cut out of, and a taper that keeps widening
    does not stay there.
    """
    field = sdf.cyl(height=20, radius1=8, radius2=4, extra1=5, extra2=5, anchor=[0, 0, 0])
    tree = field._sdf_fn(lv.x(), lv.y(), lv.z())
    assert float(tree(7.9, 0.0, -13.0)) < 0, "the bottom stub should carry the bottom radius"
    assert float(tree(8.1, 0.0, -13.0)) > 0, "and no more than it"
    assert float(tree(3.9, 0.0, 13.0)) < 0, "the top stub should carry the top radius"
    assert float(tree(4.1, 0.0, 13.0)) > 0, "and no more than it"


@pytest.mark.parametrize(
    "corners",
    [
        {"p1": [0, 0, 0], "p2": [10, 20, 30]},
        {"p1": [5, -3, 2], "p2": [-1, 4, 8]},
        {"p1": [1, 2, 3], "size": 6},
    ],
)
def test_two_corners_place_a_cuboid_the_same_way_on_both_backends(corners: dict[str, object]) -> None:
    """`p1`/`p2` give the size and the position together, so they override the anchor rather than compose."""
    from pybosl2 import solid as facade
    from pybosl2 import use_backend

    boxes = {}
    for backend in ("csg", "sdf"):
        with use_backend(backend):
            box = facade.cuboid(**corners).bounds()
            boxes[backend] = [round(v, 2) for v in (*box.size, *box.center)]
    assert boxes["csg"] == pytest.approx(boxes["sdf"], abs=0.05), f"{corners}: {boxes}"


@pytest.mark.parametrize(
    ("label", "rim"),
    [
        ("no clip at all", {"rounding1": 2, "rounding2": 2}),
        ("clipped at 45", {"rounding1": 2, "rounding2": 2, "clip_angle": 45}),
        ("clipped at 30", {"rounding1": 2, "rounding2": 2, "clip_angle": 30}),
        ("clipped at 60", {"rounding1": 2, "rounding2": 2, "clip_angle": 60}),
        ("a teardrop", {"rounding1": 2, "rounding2": 2, "teardrop": True}),
        ("a teardrop at 30", {"rounding1": 2, "rounding2": 2, "teardrop": 30}),
        ("a different rounding at each end", {"rounding1": 1, "rounding2": 3, "clip_angle": 45}),
    ],
)
def test_a_clipped_fillet_follows_the_profile_csg_revolves(label: str, rim: dict[str, object]) -> None:
    """The last parity gap that was different in kind, and the first non-convex one.

    Everything closed on this backend before now was an intersection of convex pieces. A clipped
    fillet is not: the arc runs from the wall down to the clip angle and then goes **straight** to
    the end face, which leaves a concave vertex where the two meet. It is the full fillet
    *unioned* with the wedge between the chord and the end face -- `min` of two expressions rather
    than `max` of several.

    The profile check discriminates both ways here, which it does not always. A field that ignored
    the clip would put the flat's outer point outside itself; a field that clipped when it should
    not would put the plain fillet's start inside.
    """
    worst = _worst_on_profile(sdf.cyl, 2, **rim)
    assert worst == pytest.approx(0.0, abs=1e-9), f"{label}: worst |field| on the profile is {worst}"


@pytest.mark.parametrize("radius2", [8.0, 5.0])
@pytest.mark.parametrize("name", ["cyl", "cylinder", "zcyl", "xcyl", "ycyl"])
def test_every_cylinder_spelling_clips_its_fillet(name: str, radius2: float) -> None:
    """Ten of the twenty gaps left after T44 were this option pair on these five names."""
    worst = _worst_on_profile(
        getattr(sdf, name),
        {"cyl": 2, "cylinder": 2, "zcyl": 2, "xcyl": 0, "ycyl": 1}[name],
        radius2=radius2,
        rounding1=2,
        rounding2=2,
        clip_angle=45,
    )
    assert worst == pytest.approx(0.0, abs=1e-9), f"{name}: worst |field| on the profile is {worst}"


def test_a_boolean_teardrop_means_forty_five_degrees_not_one() -> None:
    """`bool` is a subclass of `int`, and reading the number first takes True as one degree.

    `teardrop=True` is the flag form of `teardrop=45`: clip the fillet so the overhang stays
    printable. The CSG backend tested `isinstance(teardrop, (int, float))` before ruling the flag
    out, so `True` was read as the angle itself -- a **1 degree** teardrop, which is a rounding
    with a flat too small to see, and silently not the thing the flag is for.

    Nothing caught it because the shape still builds, still looks round, and its bounding box is
    the same either way. `pybosl2.sdf.shapes3d.effective_clip` is the one place that rule lives
    now, and both backends read it.
    """
    from pybosl2.sdf.shapes3d import effective_clip
    from pybosl2.shapes3d.cylinder import cyl_profile

    # T62: this line read `== 60.0`, restating `min(clip, 90 - angle)` rather than measuring
    # anything -- and that formula inverted the angle. The lean is measured on the profile in
    # `tests/test_teardrop_angles.py` now; what is left here is the bool-before-int rule.
    assert effective_clip(90.0, True) == pytest.approx(45.0)
    assert effective_clip(90.0, 30) == pytest.approx(30.0)
    assert effective_clip(40.0, True) == pytest.approx(40.0), "the tighter of the two wins"
    assert effective_clip(90.0, False) == pytest.approx(90.0)

    flag = cyl_profile(8, 8, 20, rounding1=2, rounding2=2, teardrop=True, fn=8)[1]
    angle = cyl_profile(8, 8, 20, rounding1=2, rounding2=2, teardrop=45, fn=8)[1]
    one = cyl_profile(8, 8, 20, rounding1=2, rounding2=2, teardrop=1, fn=8)[1]
    assert flag == pytest.approx(angle), "teardrop=True is teardrop=45"
    assert flag != pytest.approx(one), "and is not teardrop=1, which is what `bool < int` made it"


TEARDROPS = [
    ("plain", {}),
    ("tapered", {"radius2": 4.0}),
    ("one cap height for both ends", {"cap_height": 6.0}),
    ("a cap on one end only", {"cap_h1": 6.0}),
    ("a different cap at each end", {"cap_h1": 6.0, "cap_h2": 7.0}),
    ("chamfered at both ends", {"chamfer": 1.5}),
    ("a different chamfer at each end", {"chamfer1": 1.0, "chamfer2": 2.0}),
    ("chamfered and capped", {"chamfer": 1.5, "cap_height": 7.0}),
    ("all of it", {"radius2": 5.0, "chamfer1": 1.0, "chamfer2": 2.0, "cap_h1": 7.0, "cap_h2": 6.0}),
]


@pytest.mark.parametrize(("label", "kwargs"), TEARDROPS)
def test_a_teardrops_cross_sections_are_the_ones_csg_hulls(label: str, kwargs: dict[str, object]) -> None:
    """The last five gaps, and the same argument as `prismoid`: a hull's slice is a linear blend.

    The CSG backend hulls a chain of cross-sections along the axis -- two for a plain teardrop,
    four when both ends are chamfered, since a chamfer is an extra section set in by its own size
    and smaller by it in both the radius and the cap. A teardrop section is convex and each of its
    three features (the disc, the roof planes, the cap) has a support function linear in the
    radius and the cap height, so the blend of two of them is another one with both interpolated.

    Checked against `_teardrop2d_path` -- the CSG backend's own outline builder -- at every
    station, so nothing of this implementation's is reused to check it.
    """
    from pybosl2._helpers import teardrop_stations
    from pybosl2.shapes3d.sphere import _teardrop2d_path

    height, angle = 20.0, 45.0
    kwargs = dict(kwargs)
    radius1 = float(kwargs.pop("radius1", 8.0))  # type: ignore[arg-type]
    radius2 = float(kwargs.pop("radius2", 8.0))  # type: ignore[arg-type]
    sin_a = math.sin(math.radians(angle))
    stations = teardrop_stations(
        height,
        radius1,
        radius2,
        kwargs.get("cap_h1", kwargs.get("cap_height")),  # type: ignore[arg-type]
        kwargs.get("cap_h2", kwargs.get("cap_height")),  # type: ignore[arg-type]
        kwargs.get("chamfer1") or kwargs.get("chamfer", 0),  # type: ignore[arg-type]
        kwargs.get("chamfer2") or kwargs.get("chamfer", 0),  # type: ignore[arg-type]
        sin_a,
    )
    tree = sdf.teardrop(
        height=height, radius1=radius1, radius2=radius2, angle=angle, anchor=[0, 0, 0], **kwargs
    )._sdf_fn(lv.x(), lv.y(), lv.z())

    worst, sampled = 0.0, 0
    for y, radius, cap in stations:
        pointy = cap >= radius / sin_a - 1e-9
        for px, pz in _teardrop2d_path(radius, angle, None if pointy else cap, False, False, 64):
            worst = max(worst, abs(float(tree(px, y, pz))))
            sampled += 1
    assert sampled >= 50, f"only {sampled} outline points -- this measures nothing"
    assert worst == pytest.approx(0.0, abs=1e-9), f"{label}: worst |field| on a cross-section is {worst}"


@pytest.mark.parametrize(("label", "kwargs"), TEARDROPS)
def test_a_teardrop_is_placed_and_sized_the_same_on_both_backends(label: str, kwargs: dict[str, object]) -> None:
    """A chamfer and a cap both move the box, so this sees what the cross-section check cannot."""
    from pybosl2 import solid as facade
    from pybosl2 import use_backend

    boxes = {}
    for backend in ("csg", "sdf"):
        with use_backend(backend):
            box = facade.teardrop(height=20, radius=8, **kwargs).bounds()
            boxes[backend] = [round(v, 1) for v in (*box.size, *box.center)]
    assert boxes["csg"] == pytest.approx(boxes["sdf"], abs=0.3), f"{label}: {boxes}"


def test_a_chamfered_end_sets_its_own_section_in_by_the_chamfer() -> None:
    """The one thing about the teardrop that **no parity check can make**, stated outright.

    `test_a_teardrops_cross_sections_are_the_ones_csg_hulls` pins the field to the stations, and
    `test_a_teardrop_is_placed_and_sized_the_same_on_both_backends` pins the box -- but the
    stations are where the rule lives, and both tests take them from `teardrop_stations` itself.
    Planting "the chamfer does not lower the cap" left every one of them green: the middle station
    still carries the full cap, so the box does not move, and the cross-section check happily
    verified the field against the wrong expectation.

    A cross-backend check cannot help either, now the two backends share the function -- a shared
    defect moves both together, which is the limit of parity testing and the reason this exists.
    So the rule is written out: a chamfered end contributes a section set **in** along the axis by
    the chamfer, and smaller by it in **both** the radius and the cap. That is what makes the end
    a bevel rather than a step.
    """
    from pybosl2._helpers import teardrop_stations

    sin_a = math.sin(math.radians(45.0))
    stations = teardrop_stations(20.0, 8.0, 6.0, 7.0, 5.0, 1.5, 2.0, sin_a)
    assert len(stations) == 4, "a chamfer at each end is four cross-sections"

    (y0, r0, c0), (y1, r1, c1), (y2, r2, c2), (y3, r3, c3) = stations
    assert (y0, y1) == pytest.approx((-10.0, -8.5)), "the front chamfer sets its section in by 1.5"
    assert (y2, y3) == pytest.approx((8.0, 10.0)), "and the back one by 2.0"
    assert (r0, r1) == pytest.approx((6.5, 8.0)), "the front section is smaller by the chamfer"
    assert (r2, r3) == pytest.approx((6.0, 4.0)), "and the back one likewise"
    assert (c0, c1) == pytest.approx((5.5, 7.0)), "the cap comes down by the chamfer too"
    assert (c2, c3) == pytest.approx((5.0, 3.0)), "and at the back, from that end's own cap"

    # No cap given is stated as a cap at the apex: the same shape, and a number to interpolate
    # towards when the other end *is* truncated.
    pointy = teardrop_stations(20.0, 8.0, 8.0, None, None, 0.0, 0.0, sin_a)
    assert all(cap == pytest.approx(8.0 / sin_a) for _, _, cap in pointy)

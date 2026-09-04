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

    worst, sampled = 0.0, 0
    for r, z in profile:
        if r <= 1e-9:  # the two points on the axis are interior, not on the surface
            continue
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

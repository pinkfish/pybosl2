# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A bound is a claim, so it gets measured against the field it describes (SPEC S-2b, PAR-5).

This is the general form of a defect that came up five times in T40-T48, in five places, each
found by accident while doing something else:

* `cyl(shift=)` widened its box by the whole shift at both ends (T40);
* `prismoid(shift=)` added the shift to the *bottom* half-size (T43);
* the fix for that kept the box **symmetric**, which a sheared solid is not (T44);
* `multmatrix` after a shear carried the old box's corners along, too wide for a treated rim (T48);
* `rotate` recomputed the box from the rotated corner box -- exact for a cuboid, 37% too wide for
  a sphere, which reported 27.3 across after a spin that could not move it (T40, fixed in T49).

Every one is the same shape of mistake: **the box is written by hand beside the field rather than
measured from it**, so it is only as good as whoever last read the formula next to it. Chasing them
one at a time found five; this asks the question directly, of everything.

Two questions, and the second is the one that matters more:

* does the solid **reach** each face of the box it declares? A box that is too large is safe, but
  it wastes the mesher's time and disagrees with the other backend about `bounds()`.
* does any of it **escape**? A box that is too small clips geometry when the field is meshed --
  silently, and in the shape rather than in a number. That is the dangerous direction, and it was
  missing from the first version of this file: two of four negative controls passed, both of them
  defects that make the box too small.

The faces are sampled on a grid, so this is a lower bound on tightness -- a contact at a single
corner can fall between samples. That is why the tolerance is generous and the *interesting*
number is not near it: a real defect here is a whole shift or a whole radius out, not a hair.
"""

from __future__ import annotations

import pytest

import pybosl2.sdf.shapes3d as sdf
from pybosl2.sdf._libfive import lv

#: How far the field may be from a face of its own box before the box is called loose. Sampling a
#: face on a grid can miss a single-point contact -- a rotated cuboid's box is exact and measures
#: 0.13 loose at this resolution, 0.015 at four times it -- so the bar is set above that noise and
#: well below anything that has ever turned out to be a real defect (2mm and up).
SLACK = 0.35

BUILDERS = {
    "cuboid": lambda: sdf.cuboid(size=[20, 14, 10], anchor=[0, 0, 0]),
    "cuboid chamfered": lambda: sdf.cuboid(size=[20, 14, 10], chamfer=2, anchor=[0, 0, 0]),
    "cuboid rounded": lambda: sdf.cuboid(size=[20, 14, 10], rounding=2, anchor=[0, 0, 0]),
    "sphere": lambda: sdf.sphere(radius=7),
    "torus": lambda: sdf.torus(outer_radius=10, inner_radius=4, anchor=[0, 0, 0]),
    "cyl": lambda: sdf.cyl(height=20, radius=6, anchor=[0, 0, 0]),
    "cyl tapered": lambda: sdf.cyl(height=20, radius1=8, radius2=3, anchor=[0, 0, 0]),
    "cyl sheared": lambda: sdf.cyl(height=20, radius1=8, radius2=3, shift=[5, -2], anchor=[0, 0, 0]),
    "cyl with extra": lambda: sdf.cyl(height=20, radius=6, extra1=3, extra2=5, anchor=[0, 0, 0]),
    "cyl textured": lambda: sdf.cyl(
        height=20, radius=8, texture="ribs", tex_reps=[8, 1], tex_depth=1.5, anchor=[0, 0, 0]
    ),
    "cyl textured inset": lambda: sdf.cyl(
        height=20, radius=8, texture="ribs", tex_reps=[8, 1], tex_depth=1.5, tex_inset=True, anchor=[0, 0, 0]
    ),
    "cyl clipped rim": lambda: sdf.cyl(height=20, radius=6, rounding=2, clip_angle=40, anchor=[0, 0, 0]),
    "tube": lambda: sdf.tube(height=20, outer_radius=8, inner_radius=4, anchor=[0, 0, 0]),
    "prismoid": lambda: sdf.prismoid([20, 20], [10, 14], height=10, anchor=[0, 0, 0]),
    "prismoid sheared": lambda: sdf.prismoid([20, 20], [10, 10], height=10, shift=[4, -3], anchor=[0, 0, 0]),
    "prismoid rounded": lambda: sdf.prismoid([20, 20], [10, 14], height=10, rounding=2, anchor=[0, 0, 0]),
    "rect_tube": lambda: sdf.rect_tube(height=10, size=20, wall=2, anchor=[0, 0, 0]),
    "rect_tube sheared": lambda: sdf.rect_tube(height=10, size=20, wall=2, shift=[3, -2], anchor=[0, 0, 0]),
    "regular_prism": lambda: sdf.regular_prism(num_sides=7, height=10, radius=5, anchor=[0, 0, 0]),
    "regular_prism sheared": lambda: sdf.regular_prism(
        num_sides=6, height=10, radius=5, shift=[4, 0], rounding=1, anchor=[0, 0, 0]
    ),
    "wedge": lambda: sdf.wedge(size=[20, 10, 8]),
    "teardrop": lambda: sdf.teardrop(height=10, radius=6, anchor=[0, 0, 0]),
    "teardrop chamfered": lambda: sdf.teardrop(height=20, radius=6, chamfer=1.5, anchor=[0, 0, 0]),
    "pie_slice": lambda: sdf.pie_slice(height=10, radius=8, angle=70, anchor=[0, 0, 0]),
    "onion": lambda: sdf.onion(radius=7),
    "sphere spun": lambda: sdf.sphere(radius=10).rotate(30, [0, 0, 1]),
    "cyl spun": lambda: sdf.cyl(height=20, radius=6, anchor=[0, 0, 0]).rotate(30, [0, 0, 1]),
    "cyl spun off its base": lambda: sdf.cyl(height=20, radius=6, anchor=[0, 0, -1]).rotate(30, [0, 0, 1]),
    "tube spun": lambda: sdf.tube(height=10, outer_radius=8, inner_radius=4, anchor=[0, 0, 0]).rotate(45, [0, 0, 1]),
    "torus spun": lambda: sdf.torus(outer_radius=10, inner_radius=4, anchor=[0, 0, 0]).rotate(30, [0, 0, 1]),
    "xcyl turned about X": lambda: sdf.xcyl(height=20, radius=6, anchor=[0, 0, 0]).rotate(30, [1, 0, 0]),
    "sphere turned about Y": lambda: sdf.sphere(radius=10).rotate(30, [0, 1, 0]),
    "sphere moved": lambda: sdf.sphere(radius=10).translate([5, -3, 2]),
    "cuboid spun": lambda: sdf.cuboid(size=[20, 10, 6]).rotate(30, [0, 0, 1]),
    # Off its own axis, so the spin really does move it: the box must grow, and a symmetry that
    # survived the move would keep the old one.
    "cyl moved then spun": lambda: sdf.cyl(height=20, radius=6, anchor=[1, 0, 0]).rotate(30, [0, 0, 1]),
    # A long shear, so the box is far from square and a spin genuinely needs a bigger one. The
    # short version of this case (shift=[5, 0]) fits inside its own unspun box either way, so a
    # wrong symmetry claim was unobservable in it -- which is why the fixture says 20.
    "sheared cyl spun": lambda: sdf.cyl(height=20, radius=6, shift=[20, 0], anchor=[0, 0, 0]).rotate(45, [0, 0, 1]),
}


def _worst_gap(shape: object, samples: int = 41) -> tuple[float, str]:
    """Return how far the field stays from the nearest face of its own box, and which face."""
    tree = shape._sdf_fn(lv.x(), lv.y(), lv.z())
    low, high = list(shape.mn), list(shape.mx)  # type: ignore[attr-defined]
    worst, where = 0.0, "none"
    for axis in range(3):
        others = [k for k in range(3) if k != axis]
        for sign, plane in ((-1, low[axis]), (1, high[axis])):
            nearest = min(
                float(
                    tree(
                        *[
                            plane
                            if k == axis
                            else low[k] + (high[k] - low[k]) * (i if k == others[0] else j) / (samples - 1)
                            for k in range(3)
                        ]
                    )
                )
                for i in range(samples)
                for j in range(samples)
            )
            if nearest > worst:
                worst, where = nearest, f"{'-+'[sign > 0]}{'xyz'[axis]} at {plane:.3f}"
    return worst, where


LOOSE_ON_PURPOSE = {"cyl moved then spun", "sheared cyl spun"}


@pytest.mark.parametrize("label", sorted(set(BUILDERS) - LOOSE_ON_PURPOSE))
def test_the_solid_reaches_every_face_of_the_box_it_declares(label: str) -> None:
    """Loose or tight, measured -- not read off the formula sitting next to the field.

    Coarse first, and refined only where the coarse pass looks loose. Every face is a grid of
    field evaluations and the field is a Python closure tree here, so a uniformly fine grid costs
    half a minute to tell us what a coarse one tells us about almost every shape; the shapes that
    *do* look loose are the ones worth paying for, and a contact missed between coarse samples
    shows up as loose rather than being skipped.
    """
    shape = BUILDERS[label]()
    worst, where = _worst_gap(shape, samples=15)
    if worst > SLACK:
        worst, where = _worst_gap(shape, samples=61)
    assert worst <= SLACK, f"{label}: the box is {worst:.3f} wider than the solid on its {where} face"


@pytest.mark.parametrize("label", sorted(BUILDERS))
def test_no_part_of_the_solid_escapes_the_box(label: str) -> None:
    """The half that matters more, and the half the first version of this file was missing.

    A box that is too large is safe. A box that is too small **clips the solid when it is meshed**
    -- not with an error, but with a shape that is quietly wrong, which is the outcome the whole
    session has been chasing. Two of four negative controls on the symmetry work passed against
    the reach-the-face check alone, and both were defects that shrink the box: a shape that keeps
    its symmetry after being moved off its own axis, and a *sheared* cylinder claiming to be
    rotationally symmetric. Both would have kept a box the spun solid no longer fits in.

    Sampled on the six planes just outside the box, over a face extended by the same margin, so a
    solid escaping through a corner is seen as well as one escaping through a face.
    """
    shape = BUILDERS[label]()
    tree = shape._sdf_fn(lv.x(), lv.y(), lv.z())
    low, high = list(shape.mn), list(shape.mx)
    margin = 0.05 * max(high[i] - low[i] for i in range(3))

    for axis in range(3):
        others = [k for k in range(3) if k != axis]
        for sign, plane in ((-1, low[axis] - margin), (1, high[axis] + margin)):
            deepest = min(
                float(
                    tree(
                        *[
                            plane
                            if k == axis
                            else (low[k] - margin) + (high[k] - low[k] + 2 * margin) * (i if k == others[0] else j) / 24
                            for k in range(3)
                        ]
                    )
                )
                for i in range(25)
                for j in range(25)
            )
            assert deepest > 0, (
                f"{label}: there is solid {-deepest:.3f} outside the "
                f"{'-+'[sign > 0]}{'xyz'[axis]} face of its own box -- meshing will clip it"
            )


def test_the_check_can_fail() -> None:
    """The tolerance is above the sampling noise and far below any defect it is meant to catch.

    Without this, `SLACK` could drift up until the test passed for anything -- the bar is the
    whole check. A sphere's box widened the way `rotate` used to widen it is 3.66 out, which is
    what these numbers have to sit either side of.
    """
    import pybosl2.sdf.shapes3d as module

    shape = sdf.sphere(radius=10)
    widened = module.PyShape(
        shape._sdf_fn,
        [v - 3.66 for v in shape.mn],
        [v + 3.66 for v in shape.mx],
        shape.res,
    )
    worst, _ = _worst_gap(widened)
    assert worst == pytest.approx(3.66, abs=1e-6), "the probe does not measure what it claims to"
    assert worst > SLACK, "and the tolerance would let that through"

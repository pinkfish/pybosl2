# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Every 2-D mask profile must enclose the area its name promises (SPEC S-28).

A mask is a cutter cross-section: whatever its polygon encloses is what gets removed. That makes
each profile's area a closed form -- a chamfer takes a triangle, a cove takes a quarter-disc -- and
a profile that computes the wrong polygon is invisible until someone looks at the solid, because
every one of them builds, exports, and cuts *something*. Two had been wrong since they were
written and no test had noticed:

* ``Mask2D.cove`` swept its arc about ``(r, r)``, which is ``Mask2D.roundover``'s arc exactly. The
  two returned the same polygon, cove differing only by two duplicated vertices, so ``cove_edges``
  rounded instead of coving.
* ``Mask2D.groove`` traced the channel's *outline* rather than the channel, closing into a frame
  one ``excess`` thick that enclosed almost nothing. It took 2.4mm^3 off a 30x30x20 box where a
  roundover of the same size took 396.

So the areas are asserted against their closed forms, and the profiles are required to differ from
one another -- the check that would have caught cove, whose area was *self-consistent*, just
somebody else's.
"""

import math

import pytest

from pybosl2 import Anchor, Mask2D, cuboid, use_defaults

R = 3.0
EXCESS = 0.01
FACETS = 256
#: cos45 == sin45, where a teardrop's arc gives way to its straight run.
_C = 1.0 / math.sqrt(2.0)
EDGES = [Anchor.TOP, Anchor.BOTTOM, Anchor.LEFT, Anchor.RIGHT, Anchor.FRONT, Anchor.BACK]

#: ``name -> (build, exact enclosed area)``. Each area is derived from the polygon the docstring
#: promises, including the ``excess`` skirt that carries the cutter clear of the surface. ``tear``
#: is absent on purpose: a teardrop profile has no elementary closed form, and its angles are
#: already pinned by ``tests/test_teardrop_angles.py``.
EXACT_AREA = {
    # The corner square, less the quarter-disc the fillet leaves behind.
    "roundover": (lambda: Mask2D.roundover(R), (R + EXCESS) ** 2 - math.pi * R**2 / 4),
    # The triangle the flat cuts off, plus the skirt on the two flanks.
    "chamfer": (lambda: Mask2D.chamfer(R), R**2 / 2 + 2 * EXCESS * R + EXCESS**2),
    # The quarter-disc itself -- a cove scoops the corner out rather than rounding it off.
    "cove": (lambda: Mask2D.cove(R), math.pi * R**2 / 4 + 2 * EXCESS * R + EXCESS**2),
    # A square step of side R.
    "step": (lambda: Mask2D.step(R), R**2 + 2 * EXCESS * R + EXCESS**2),
    # The channel: full width, and deep enough to clear the mouth. Depth defaults to half the width.
    "groove": (lambda: Mask2D.groove(R), R * (R / 2 + EXCESS)),
    # An eighth-circle off the wall, then a straight run at 45 degrees down to the face.
    # Integrating the boundary gives `1.5 * (1 - cos45)^2` for the straight part and
    # `cos45 - 1/4 - pi/8` for the arc, both in units of R^2, over the usual skirt.
    "tear": (
        lambda: Mask2D.tear(R),
        R**2 * (1.5 * (1 - _C) ** 2 + _C - 0.25 - math.pi / 8) + EXCESS * (R + 2 * R * (1 - _C) + EXCESS),
    ),
}


def _area(mask: object) -> float:
    """Return the area the closed polygon encloses, by the shoelace formula."""
    return _shoelace([(float(x), float(y)) for x, y in mask])  # type: ignore[attr-defined]


def _shoelace(pts: list[tuple[float, float]]) -> float:
    """Return the signed-area magnitude of a closed point loop."""
    twice = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1], strict=True))
    return abs(twice) / 2


@pytest.mark.parametrize("name", sorted(EXACT_AREA))
def test_a_mask_encloses_the_area_its_name_promises(name: str) -> None:
    """SPEC S-28: the cross-section is the material removed, so its area is not a free parameter."""
    build, exact = EXACT_AREA[name]
    with use_defaults(fn=FACETS):
        got = _area(build())
    # Faceting inscribes the arcs, so a curved profile lands a hair under; 1% covers it at 256.
    assert got == pytest.approx(exact, rel=0.01), (
        f"Mask2D.{name}({R}) encloses {got:.4f}, but the profile it documents encloses {exact:.4f}"
    )


def test_no_two_mask_profiles_are_the_same_polygon() -> None:
    """SPEC S-28: cove's area was self-consistent -- it was roundover's. Only comparison finds that."""
    with use_defaults(fn=FACETS):
        built = {
            name: [(round(float(x), 9), round(float(y), 9)) for x, y in build()]  # type: ignore[attr-defined]
            for name, (build, _) in EXACT_AREA.items()
        }
    for name, pts in built.items():
        for other, other_pts in built.items():
            if name < other:
                # Duplicate vertices are how cove hid: same shape, longer list.
                assert dict.fromkeys(pts) != dict.fromkeys(other_pts), (
                    f"Mask2D.{name} and Mask2D.{other} return the same polygon"
                )


@pytest.mark.parametrize(
    ("keyword", "mask"),
    [("rounding", Mask2D.roundover), ("chamfer", Mask2D.chamfer)],
    ids=["rounding", "chamfer"],
)
def test_the_constructor_and_the_mask_agree(keyword: str, mask: object) -> None:
    """SPEC S-28: `cuboid(rounding=r)` and the roundover mask must reach the same solid."""
    with use_defaults(fn=128):
        by_constructor = cuboid([30, 30, 20], **{keyword: R}).vnf().volume()
        by_mask = (
            cuboid([30, 30, 20])
            .edge_profile(edges=EDGES, mask=mask(R))  # type: ignore[operator]
            .realize()
            .vnf()
            .volume()
        )
    assert by_mask == pytest.approx(by_constructor, rel=0.01), (
        f"cuboid({keyword}={R}) is {by_constructor:.2f}mm^3 but the same cut as a mask is "
        f"{by_mask:.2f}mm^3; SPEC S-28 requires the two spellings to agree"
    )


def _fill_area(pts: list[tuple[float, float]]) -> float:
    """Return the even-odd filled area, by sampling. Equals the shoelace area iff the loop is simple."""
    lo_x, hi_x = min(p[0] for p in pts) - 0.1, max(p[0] for p in pts) + 0.1
    lo_y, hi_y = min(p[1] for p in pts) - 0.1, max(p[1] for p in pts) + 0.1
    n = 500
    step_x, step_y = (hi_x - lo_x) / n, (hi_y - lo_y) / n
    hits = 0
    for i in range(n):
        py = lo_y + (i + 0.5) * step_y
        crossings = sorted(
            x0 + (py - y0) * (x1 - x0) / (y1 - y0)
            for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1], strict=True)
            if (y0 > py) != (y1 > py)
        )
        hits += sum(round((crossings[k + 1] - crossings[k]) / step_x) for k in range(0, len(crossings) - 1, 2))
    return hits * step_x * step_y


@pytest.mark.parametrize("name", sorted(EXACT_AREA))
def test_a_mask_profile_is_a_simple_polygon(name: str) -> None:
    """SPEC S-28: a cutter that crosses itself has no interior, so "what it removes" is undefined.

    ``Mask2D.tear`` failed this and landed as a ``strict=True`` xfail carrying the measurement --
    shoelace 1.110 against an even-odd fill of 2.903 -- precisely so that fixing it could not pass
    quietly. T90 fixed it, and strict mode is what turned the entry into a failure until it was
    deleted.
    """
    build = EXACT_AREA[name][0]
    with use_defaults(fn=64):
        pts = [(float(x), float(y)) for x, y in build()]  # type: ignore[attr-defined]
    shoelace, filled = _shoelace(pts), _fill_area(pts)
    assert shoelace == pytest.approx(filled, rel=0.02), (
        f"Mask2D.{name} shoelaces to {shoelace:.3f} but fills {filled:.3f}; the loop crosses itself"
    )


#: Profiles that cut a corner, so their polygon must stay inside the corner they were given. The
#: groove is a channel across a face rather than a corner cutter, and is centred on x=0 by design.
CORNER_PROFILES = sorted(set(EXACT_AREA) - {"groove"})


@pytest.mark.parametrize("name", CORNER_PROFILES)
def test_a_corner_mask_stays_inside_the_corner(name: str) -> None:
    """SPEC S-28: a cutter reaching past its own radius removes material nobody asked for.

    `Mask2D.tear(3)` reached `x=5.12` and `y=-1.24`. Its arc ran 135 degrees past the wall instead
    of 45, which carries it back out around the far side of the centre, and its tip was placed at
    `r * (1 - sqrt 2)` -- the negative of the point it was meant to be.
    """
    with use_defaults(fn=FACETS):
        pts = [(float(x), float(y)) for x, y in EXACT_AREA[name][0]()]  # type: ignore[attr-defined]
    for axis, values in (("x", [p[0] for p in pts]), ("y", [p[1] for p in pts])):
        assert min(values) >= -EXCESS - 1e-9, (
            f"Mask2D.{name} reaches {axis}={min(values):.2f}, past the excess skirt at {-EXCESS}"
        )
        assert max(values) <= R + 1e-9, (
            f"Mask2D.{name} reaches {axis}={max(values):.2f}, outside the corner of radius {R}"
        )


def test_the_teardrop_never_leans_past_what_a_printer_can_bridge() -> None:
    """SPEC S-28: the teardrop profile exists to cap the overhang, so measure the overhang.

    This is T62's measurement -- the steepest lean from vertical, rather than the arithmetic that
    produced it -- applied to the mask spelling, which T62 did not reach. It is also the assertion
    that says the profile is the *right* simple polygon and not merely a simple one.
    """
    with use_defaults(fn=FACETS):
        pts = [(float(x), float(y)) for x, y in Mask2D.tear(R)]
    # The first three vertices are the skirt; the rest is the cut the printer has to bridge.
    steepest = max(
        math.degrees(math.atan2(abs(x1 - x0), abs(y1 - y0)))
        for (x0, y0), (x1, y1) in zip(pts[3:-1], pts[4:], strict=True)
    )
    assert steepest == pytest.approx(45.0, abs=0.5), (
        f"the teardrop cut leans {steepest:.2f} degrees from vertical; 45 is what an FDM printer "
        f"bridges without support, and is the whole reason the profile exists"
    )

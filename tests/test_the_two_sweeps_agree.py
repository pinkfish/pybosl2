# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""The SDF backend has a sweep of its own, and it is not the façade's sweep (SPEC PAR-1).

`WireBundle` is listed CSG-only under the reason

    a swept tube that follows bends is a non-convex mesh with no distance-field form

The first clause describes the CSG implementation: `Path3D.path_sweep` builds a VNF and calls
`polyhedron()`, whatever backend is active, and the SDF backend refuses a polyhedron whose faces are
not convex -- which a tube following a bend has none of. The second clause looked false, because
`pybosl2.sdf.shapes3d.path_sweep` builds exactly that shape as a field and the backend registry
already exposes it under the name `path_sweep`. Nothing asks it. That is the shape of T41's finding,
where `texture=` was called impossible by three records that had read the CSG *signature* rather
than the CSG *code*.

**It is not that finding, and only measuring says so.** Routing the façade to the native sweep makes
`WireBundle` build on both backends with agreeing *extents* -- and the two sweeps are nonetheless
different functions:

====================  ========================  ========================
route, offset         façade (mesh) centre      ``sdf.path_sweep`` centre
====================  ========================  ========================
straight, offset 0    ``[10, 0, 0]``            ``[10, 0, 0]``
straight, offset 3    ``[10, 0, +3]``           ``[10, -3, 0]``
bent, offset 0        ``[10.32, 9.68, 0]``      ``[14.6, 5.4, 0]``
====================  ========================  ========================

On a straight route the façade sends the profile's y to world **z** and the native sweep sends it to
world **-y**. On a bent route they do not even agree about where the solid is. A guard comparing
sizes would have passed both rows, because the sizes match.

So the gap stands and the delegation was reverted, but **its reason was wrong**: not that a swept
tube has no distance-field form -- it plainly has one -- but that the backend's own sweep does not
build the same solid the façade's does. Closing it means reconciling two sweeps, not routing to one.

Recorded as a `strict=True` xfail carrying the numbers, the instrument T89 used for the teardrop
mask and T90 then had to delete to go green.

**The reason given for not fixing it here was itself wrong, and T119 measured that too.** It read:
*this environment cannot check a fix: libfive is stubbed, so an SDF solid meshes to nothing and only
its analytic box can be read, and a matching box is not evidence of a matching field.* The last
clause is exactly right, and it is why the comparison below used to be a comparison of box centres.
The middle clause is false. An SDF solid does mesh to nothing, but its field evaluates to exact
signed distances and `inside()` answers correctly, so the two solids can be compared where both are
defined -- at the CSG mesh's own vertices. See `tests/field_probe.py`.

Asked that way the disagreement is sharper than a box centre could show:

* on the **straight** route it is *exactly* a -90 degree turn about X. Rotating the native sweep by
  -90 puts the field at **0.0000** at all 48 of the façade's vertices. T100's frame hypothesis was
  right, and is now measured rather than inferred from two centres.
* on the **bent** route it is not a rigid motion at all. No turn about X matches: 0 degrees leaves
  22 of 72 vertices outside the field and 22 inside, -90 and +90 both reach 19.17, and 180 reaches
  13.92. The largest departure is **+0.3162 at [-0.316, -0.949, 0.0]**, which is behind the route's
  start -- an end-cap difference, not a displacement.

So reconciling the frame fixes the straight case and leaves the bend, which is a smaller claim than
"the two sweeps are different functions" and a more useful one. It is still not fixed here, for the
one reason that survives: guessing a frame convention is how T89's two mask profiles came to be
wrong in the first place, and the bend needs more than a frame.
"""

from __future__ import annotations

import math

import pytest

import pybosl2.sdf.shapes3d as sdf_shapes
from pybosl2 import use_backend
from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D
from tests.field_probe import worst_escape

STRAIGHT = Path3D([[0.0, 0.0, 0.0], [20.0, 0.0, 0.0]], closed=False)
BENT = Path3D([[0.0, 0.0, 0.0], [20.0, 0.0, 0.0], [20.0, 20.0, 0.0]], closed=False)

#: How far the profile sits off its own origin. Hex-packing a wire bundle offsets every wire but the
#: first, so an offset profile is the normal case rather than a contrived one.
OFFSET = 3.0


def _circle(offset: float, radius: float = 1.0, sides: int = 24) -> Path2D:
    return Path2D(
        [
            [
                radius * math.cos(2 * math.pi * k / sides),
                offset + radius * math.sin(2 * math.pi * k / sides),
            ]
            for k in range(sides)
        ]
    )


def _facade_centre(route: Path3D, offset: float) -> list[float]:
    with use_backend("csg"):
        return [float(v) for v in route.path_sweep(_circle(offset)).bounds().center]


def _native_centre(route: Path3D, offset: float) -> list[float]:
    with use_backend("sdf"):
        swept = sdf_shapes.path_sweep(profile=_circle(offset), path=route)
    return [float(v) for v in swept.bounds().center]


@pytest.mark.xfail(
    strict=True,
    reason="the two sweeps are different functions; see the module docstring for the measurement",
)
@pytest.mark.parametrize("route", [STRAIGHT, BENT], ids=["straight", "bent"])
def test_the_backends_two_sweeps_build_the_same_solid(route: Path3D) -> None:
    """SPEC PAR-1: the backend's own sweep must agree with the one the façade builds.

    On the field, at the façade mesh's own vertices -- not on the box centres this used to compare.
    A vertex outside the native field cannot be faceting, which inscribes; see `field_probe`.
    """
    outside, inside, where = worst_escape(
        lambda: route.path_sweep(_circle(OFFSET)),
        lambda: sdf_shapes.path_sweep(profile=_circle(OFFSET), path=route),
    )
    assert outside <= 1e-6, (
        f"the façade's sweep has a vertex at {where} lying {outside:.4f} outside the native "
        f"sweep's field (furthest inside {inside:.4f}); the gap in `WireBundle` cannot be closed "
        f"by dispatching to it until these build the same solid"
    )


def test_the_disagreement_is_still_the_one_measured() -> None:
    """Pinned, so a partial change is not mistaken for a fix.

    Without this, moving the native sweep's frame to some *third* convention would leave the xfail
    above still xfailing -- green, and no closer.
    """
    assert _facade_centre(STRAIGHT, OFFSET) == pytest.approx([10.0, 0.0, OFFSET], abs=0.05), (
        "the façade's sweep has moved; the comparison above is no longer the one documented"
    )
    assert _native_centre(STRAIGHT, OFFSET) == pytest.approx([10.0, -OFFSET, 0.0], abs=0.05), (
        f"the native sweep no longer centres at y=-{OFFSET}. If it now matches the façade, delete "
        f"this test and the xfail above; if it has moved elsewhere, it is still not reconciled"
    )


def test_the_straight_route_differs_by_exactly_one_turn_about_x() -> None:
    """The frame hypothesis, measured on the field rather than inferred from two box centres.

    This is the half of the disagreement that *is* a rigid motion, and pinning it means a later
    change to the native sweep's frame cannot land halfway without being noticed.
    """
    outside, inside, where = worst_escape(
        lambda: STRAIGHT.path_sweep(_circle(OFFSET)),
        lambda: sdf_shapes.path_sweep(profile=_circle(OFFSET), path=STRAIGHT).rotate(-90, [1, 0, 0]),
    )
    assert max(outside, abs(inside)) <= 1e-6, (
        f"turning the native sweep -90 degrees about X used to put its field at 0.0000 on every "
        f"vertex of the façade's straight sweep; now the worst is {outside:.4f} outside and "
        f"{inside:.4f} inside, at {where}. The straight-route frame difference has moved."
    )


def test_the_bent_route_is_not_a_turn_about_x_at_all() -> None:
    """The other half, which no rotation fixes -- so the fix is not just a frame.

    Without this the xfail above could be "closed" by rotating the native sweep, which would make
    the straight route agree and leave the bend silently wrong.
    """
    best = min(
        worst_escape(
            lambda: BENT.path_sweep(_circle(OFFSET)),
            lambda angle=angle: sdf_shapes.path_sweep(profile=_circle(OFFSET), path=BENT).rotate(angle, [1, 0, 0]),
        )[0]
        for angle in (0, -90, 90, 180)
    )
    assert best > 1.0, (
        f"some turn about X now brings the bent route within {best:.4f} of agreement. If one of "
        f"them matches, the bend was a frame difference after all and this test and the xfail "
        f"above should go."
    )


def test_the_native_sweep_builds_what_the_refusal_says_it_cannot() -> None:
    """The part of the original reason that is simply false, kept as the standing correction."""
    with use_backend("sdf"):
        swept = sdf_shapes.path_sweep(profile=_circle(0.0), path=BENT)
    assert min(float(v) for v in swept.bounds().size) > 0.0, (
        "the SDF backend built a swept tube following bends, which `WireBundle`'s refusal calls "
        "a shape with no distance-field form"
    )

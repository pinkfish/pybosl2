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
mask and T90 then had to delete to go green. It is not fixed here because this environment cannot
check a fix: libfive is stubbed, so an SDF solid meshes to nothing and only its analytic box can be
read, and a matching box is not evidence of a matching field. Guessing a frame convention is how
T89's two mask profiles came to be wrong in the first place.
"""

from __future__ import annotations

import math

import pytest

import pybosl2.sdf.shapes3d as sdf_shapes
from pybosl2 import use_backend
from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D

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
    """SPEC PAR-1: the backend's own sweep must agree with the one the façade builds."""
    facade, native = _facade_centre(route, OFFSET), _native_centre(route, OFFSET)
    assert native == pytest.approx(facade, abs=0.05), (
        f"the façade sweeps to {facade} and the backend's own sweep to {native}; the gap in "
        f"`WireBundle` cannot be closed by dispatching to it until these agree"
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


def test_the_native_sweep_builds_what_the_refusal_says_it_cannot() -> None:
    """The part of the original reason that is simply false, kept as the standing correction."""
    with use_backend("sdf"):
        swept = sdf_shapes.path_sweep(profile=_circle(0.0), path=BENT)
    assert min(float(v) for v in swept.bounds().size) > 0.0, (
        "the SDF backend built a swept tube following bends, which `WireBundle`'s refusal calls "
        "a shape with no distance-field form"
    )

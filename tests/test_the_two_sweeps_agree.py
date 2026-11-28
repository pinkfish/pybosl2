# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""The SDF backend's sweep and the façade's build the same solid (SPEC PAR-1, A-1).

They did not, for as long as there were two of them, and the reason was not the one on the file.
`WireBundle` was listed CSG-only under

    a swept tube that follows bends is a non-convex mesh with no distance-field form

The second clause is plainly false -- `pybosl2.sdf.shapes3d.path_sweep` builds exactly that shape
as a field -- so T100 tried dispatching to it, found the two sweeps were *different functions*, and
reverted with the numbers:

====================  ========================  ========================
route, offset         façade (mesh) centre      ``sdf.path_sweep`` centre
====================  ========================  ========================
straight, offset 0    ``[10, 0, 0]``            ``[10, 0, 0]``
straight, offset 3    ``[10, 0, +3]``           ``[10, -3, 0]``
bent, offset 0        ``[10.32, 9.68, 0]``      ``[14.6, 5.4, 0]``
====================  ========================  ========================

T119 then measured it on the field rather than on box centres: on a straight route the difference
was *exactly* a -90 degree turn about X (0.0000 at all 48 vertices), and on a bent route it was no
rigid motion at all -- no turn about X came within 13.92. The conclusion drawn was that
reconciling the frame would fix the straight case and leave the bend, and that the bend "needs more
than a frame".

**It needed one less implementation.** Both sweeps ran Wang's double-reflection algorithm, so the
difference was never the algorithm: it was that the backend walked the path *itself* and so differed
in four places at once -- the end tangents (`path_tangents(uniform=true)` takes a one-sided
quadratic at the ends, which on a cornered path leans the start tangent backwards; the backend took
a one-sided linear), the seed normal (`BACK` above 1/sqrt2 of vertical against `[1,0,0]` above 0.9),
the closing-twist correction the backend had no equivalent of, and which in-plane axis carried
``u`` -- the last of which is a *reflection*, not a roll, which is why a single rotation could never
have reconciled the bend.

So `pybosl2.sdf.shapes3d.swept_profile` takes the **stations** rather than the path, and
`path_sweep` asks `Sweepable.path_sweep_transforms` for them. There is one frame implementation in
the library now, and the agreement below is not a measurement that happened to come out well: every
vertex of the meshed sweep *is* a point of a cross-section this field places, so it reads 0.0 by
construction. The measurement is still here because "by construction" has been wrong before.

**Why nothing noticed is the kept lesson.** Every case in `tests/test_backend_sdf_sweep.py` sweeps
along a path parallel to **Z**, and there the two frames are *both* the identity -- the façade picks
`BACK` as its seed normal above 1/sqrt2 of vertical and the backend picks `[1,0,0]` above 0.9, and
the two choices happen to produce the same frame for a vertical tangent. So the backend's own sweep
could be probed correctly in its own frame while building a differently-rolled solid from the same
arguments as the façade. Run the cases below against the commit before this one and the two
`vertical` rows are the *only* geometry comparisons that pass.

T142. `WireBundle`'s guard is gone.
"""

from __future__ import annotations

import math

import pytest

import pybosl2.sdf.shapes3d as sdf_shapes
from pybosl2 import use_backend
from pybosl2.exceptions import UnsupportedByBackendError
from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D
from tests.field_probe import csg_vertices, worst_escape

STRAIGHT = Path3D([[0.0, 0.0, 0.0], [20.0, 0.0, 0.0]], closed=False)
BENT = Path3D([[0.0, 0.0, 0.0], [20.0, 0.0, 0.0], [20.0, 20.0, 0.0]], closed=False)
VERTICAL = Path3D([[0.0, 0.0, z] for z in (0.0, 5.0, 10.0, 15.0, 20.0)], closed=False)
HELICAL = Path3D(
    [[8 * math.cos(t), 8 * math.sin(t), 2.5 * t] for t in [i * math.pi / 6 for i in range(13)]],
    closed=False,
)

#: How far the profile sits off its own origin. Hex-packing a wire bundle offsets every wire but the
#: first, so an offset profile is the normal case rather than a contrived one -- and it is what made
#: the old disagreement visible, since a centred profile hid the frame difference entirely.
OFFSET = 3.0

#: The figure every case is held to. Not a faceting tolerance: a mesh vertex sits *on* the
#: cross-section the field places, so this is the arithmetic of evaluating the tree and nothing else.
OUTSIDE = 1e-6


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


#: An L with unequal arms, so a reflected frame cannot pass as a matching one. The u/v swap the two
#: sweeps used to differ by is exactly a reflection, and a circle -- offset or not -- cannot see it.
#: Neither can an L with *equal* arms, which is symmetric about its own diagonal and so is its own
#: swap: the first spelling of the control here was 4 x 4 and read 0.0000, which is the control
#: passing its own test by being unable to fail it.
ELL = Path2D([[0.0, 0.0], [5.0, 0.0], [5.0, 1.2], [1.8, 1.2], [1.8, 3.5], [0.0, 3.5]])

#: A loop, swept closed. Worth its own case because the station list then has one *extra* entry --
#: the first station repeated at the end, carrying the closing-twist correction -- and the two slab
#: reaches have to meet there rather than cap.
RING = Path3D([[12 * math.cos(t), 12 * math.sin(t), 0.0] for t in [i * math.pi / 12 for i in range(24)]], closed=True)

ROUTES = {"straight": STRAIGHT, "bent": BENT, "vertical": VERTICAL, "helical": HELICAL}


@pytest.mark.parametrize("route", sorted(ROUTES))
@pytest.mark.parametrize("profile", ["offset circle", "asymmetric ell"])
def test_the_two_sweeps_build_the_same_solid(route: str, profile: str) -> None:
    """SPEC PAR-1: the backend's own sweep must agree with the one the façade builds.

    On the field, at the façade mesh's own vertices -- not on the box centres T100 compared. A
    vertex outside the field cannot be faceting, which inscribes; see `field_probe`.
    """
    spine = ROUTES[route]
    shape = _circle(OFFSET) if profile == "offset circle" else ELL
    outside, inside, where = worst_escape(
        lambda: spine.path_sweep(shape),
        lambda: sdf_shapes.path_sweep(profile=shape, path=spine),
    )
    assert outside <= OUTSIDE, (
        f"the façade's sweep of {profile} along the {route} route has a vertex at {where} lying "
        f"{outside:.4f} outside the native sweep's field (furthest inside {inside:.4f}). The two "
        f"read the same station list, so a departure means one of them has stopped using it."
    )
    assert abs(inside) <= OUTSIDE, (
        f"the façade's sweep of {profile} along the {route} route sits {inside:.4f} inside the "
        f"native sweep's field. Every mesh vertex is a point of a cross-section the field places, "
        f"so this has been exactly 0; a departure means the frames have diverged again."
    )


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_each_case_has_real_vertices_to_compare(route: str) -> None:
    """A case whose mesh came back empty would pass the test above by having nothing to check."""
    points = csg_vertices(lambda: ROUTES[route].path_sweep(ELL))
    assert len(points) >= 12, (
        f"the {route} route produced {len(points)} vertices; a six-point profile over two or more "
        f"stations has many more, so the comparison above is not measuring the sweep."
    )


def test_a_reflected_frame_is_caught() -> None:
    """The control: the comparison must be able to see the error the two sweeps actually had.

    Agreeing to 0.0 means nothing unless disagreement is visible, and the disagreement here was a
    *reflection* -- the backend sent the profile's `u` to the frame normal and `v` to the binormal
    where the façade sends `u` to the binormal and `v` to the normal. A circle cannot see that
    however far it is offset, which is part of why two box centres read as a frame difference.
    """
    flipped = Path2D([[y, x] for x, y in ELL])
    outside, _, _ = worst_escape(
        lambda: BENT.path_sweep(ELL),
        lambda: sdf_shapes.path_sweep(profile=flipped, path=BENT),
    )
    assert outside > 0.1, (
        f"sweeping the profile with its two axes swapped reads only {outside:.4f} outside the "
        f"unswapped field, so this comparison cannot see a reflected frame and the agreements "
        f"above prove less than they appear to."
    )


@pytest.mark.parametrize("profile", ["offset circle", "asymmetric ell"])
def test_a_closed_sweep_builds_the_same_loop(profile: str) -> None:
    """A loop joins its two ends, and the station list says so by repeating the first station.

    Separate from the open routes because the join is where the slab reaches have to meet instead of
    cap: station 0 reaches forward only and the repeated last station reaches back only, and they
    coincide, so the union closes there. Capping both would leave a gap the size of a facet.
    """
    shape = _circle(OFFSET) if profile == "offset circle" else ELL
    outside, inside, where = worst_escape(
        lambda: RING.path_sweep(shape, closed=True),
        lambda: sdf_shapes.path_sweep(profile=shape, path=RING, closed=True),
    )
    assert max(outside, abs(inside)) <= OUTSIDE, (
        f"a closed sweep of {profile} has a vertex at {where} lying {outside:.4f} outside and "
        f"{inside:.4f} inside the native sweep's field -- the two no longer close the loop alike"
    )


def test_the_facade_sweep_takes_the_exact_route_on_sdf() -> None:
    """Under `use_backend("sdf")`, `Path3D.path_sweep` must *be* the field, not a mesh of it.

    The same claim `test_the_skin_sweep_takes_the_exact_route_on_sdf` makes for `spiral_sweep`, and
    the reason the `skin -> sdf` import is architecture rather than debt: meshing is a one-way door,
    since `to_sdf` refuses on a CSG solid outright, so a sweep that went through `VNF.polyhedron()`
    would have thrown the exactness away with nothing able to recover it.
    """
    with use_backend("sdf"):
        through_facade = BENT.path_sweep(ELL)
    assert type(through_facade).__name__ == "SdfSolid", (
        f"Path3D.path_sweep under use_backend('sdf') handed back {type(through_facade).__name__}, "
        f"so it meshed the sweep instead of building the field (SPEC A-6, B-5)"
    )


@pytest.mark.parametrize(
    ("label", "kwargs", "named"),
    [
        ("a scaled sweep", {"scale": 0.5}, "path_sweep(scale=)"),
        ("an uncapped sweep", {"caps": "none"}, "path_sweep(caps=CapType.NONE)"),
        ("a domed sweep", {"caps": "round"}, "path_sweep(caps=CapType.ROUND)"),
    ],
)
def test_what_the_field_cannot_sweep_refuses_by_name(label: str, kwargs: dict[str, object], named: str) -> None:
    """Three of `path_sweep`'s arguments do not cross, and each says which one it is (SPEC E-5).

    A scaled station is not a rigid motion, so the field cannot read the profile back out of it; an
    uncapped sweep is an open surface, and a distance field describes only solids. `style=` is the
    one that *does* cross -- it chooses how a grid cell is split into triangles, and a field has no
    triangles, so it falls under B-9's tessellation carve-out and is accepted and ignored.
    """
    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError) as excinfo:
        STRAIGHT.path_sweep(ELL, **kwargs)  # type: ignore[arg-type]
    assert named in str(excinfo.value), f"{label} refused without naming {named}: {excinfo.value}"


def test_the_tessellation_argument_is_accepted_and_ignored() -> None:
    """`style=` is a triangulation choice, and B-9 says a field accepts and ignores those.

    Refusing it would turn away a perfectly buildable sweep over how the *other* backend would cut
    its quads -- the mistake `convexity` was making on `linear_extrude` until T14.
    """
    from pybosl2.enums import VNFStyle

    with use_backend("sdf"):
        plain = STRAIGHT.path_sweep(ELL)
        styled = STRAIGHT.path_sweep(ELL, style=VNFStyle.QUINCUNX)
    assert [float(v) for v in plain.bounds().size] == pytest.approx([float(v) for v in styled.bounds().size]), (
        "style= changed the field, which it must not: it names how a mesh is triangulated and the field has no mesh"
    )

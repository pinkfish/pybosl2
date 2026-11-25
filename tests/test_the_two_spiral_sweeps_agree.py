# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The two `spiral_sweep` implementations build the same solid (SPEC PAR-1, S-46a).

T103 found four parts -- `Nut`, `Screw`, `ThreadedNut`, `ThreadedRod` -- refusing the SDF backend
with a reason that was false: *a helical thread has no distance-field form*, while `ThreadHelix` in
the same file routes one through `spiral_sweep` and builds on both backends. They were reclassified
as **route** gaps, closable in principle, and closing them was then deferred with this note:

> The two `spiral_sweep` implementations agree on size *and* centre with an asymmetric profile --
> better evidence than `path_sweep` gave -- but **a box is still a size signature**, and that has
> hidden a shape difference four times this session. Named, not guessed.

The caveat was the right one and the limitation was not: T119 showed the field evaluates to exact
signed distances, so the two can be compared at the mesh's own vertices rather than through their
boxes. Asked that way, over nine configurations and 1960 vertices, the furthest any vertex sits
outside the other implementation's field is **0.0000** -- not within faceting, exactly zero. The
mesh sweep and the field sweep are the same solid.

So the "size signature" caveat is retired for this comparison, and what remains in the way of the
four parts is narrower than it was. See `test_the_thread_grid_differs_only_at_its_cut_ends` for the
part that is still a real geometry change.
"""

from __future__ import annotations

from typing import Any

import pytest

import pybosl2.sdf.shapes3d as sdf_shapes
from pybosl2.path2d import Path2D
from tests.field_probe import worst_escape

#: A right-triangle tooth, deliberately asymmetric: a symmetric profile would agree under a
#: reflection as well as under equality, so it cannot tell a mirrored sweep from a matching one.
TOOTH = Path2D([[0.0, -1.0], [1.5, 0.0], [0.0, 1.0]])

#: An asymmetric quadrilateral -- a buttress tooth, which is the shape the mirror question matters
#: most for, since a buttress thread's whole point is that its two flanks differ.
BUTTRESS = Path2D([[0.0, -1.0], [1.2, -0.6], [1.2, 0.3], [0.0, 1.0]])

SQUARE = Path2D([[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]])

CASES = {
    "tooth, 3 turns": (TOOTH, {"height": 10.0, "radius": 5.0, "turns": 3.0}),
    "tooth, 1 turn": (TOOTH, {"height": 10.0, "radius": 5.0, "turns": 1.0}),
    "tooth, 7 turns": (TOOTH, {"height": 10.0, "radius": 5.0, "turns": 7.0}),
    "tooth, fractional turns": (TOOTH, {"height": 10.0, "radius": 5.0, "turns": 2.5}),
    "tooth, not centred": (TOOTH, {"height": 10.0, "radius": 5.0, "turns": 3.0, "center": False}),
    "tooth, left-handed": (TOOTH, {"height": 10.0, "radius": 5.0, "turns": -3.0}),
    "buttress, 3 turns": (BUTTRESS, {"height": 10.0, "radius": 5.0, "turns": 3.0}),
    "square, 4 turns": (SQUARE, {"height": 12.0, "radius": 6.0, "turns": 4.0}),
    "tall and thin, 10 turns": (TOOTH, {"height": 30.0, "radius": 3.0, "turns": 10.0}),
}

#: The figure every case is held to. Not a faceting tolerance -- faceting inscribes, so it shows up
#: on the other side of zero -- only the arithmetic of evaluating the tree.
OUTSIDE = 1e-6


@pytest.mark.parametrize("label", sorted(CASES))
def test_the_mesh_sweep_lies_on_the_field_sweep(label: str) -> None:
    """The same helix, built both ways, must be the same solid."""
    profile, kwargs = CASES[label]
    outside, inside, where = worst_escape(
        lambda: profile.spiral_sweep(**kwargs),
        lambda: sdf_shapes.spiral_sweep(profile=profile, **kwargs),
    )
    assert outside <= OUTSIDE, (
        f"spiral_sweep({label}): the meshed sweep has a vertex at {where} lying {outside:.4f} "
        f"outside the field sweep. Faceting can only inscribe, so these are different solids and "
        f"the four thread parts' route gap is not a routing question after all (SPEC PAR-1)."
    )
    assert abs(inside) <= OUTSIDE, (
        f"spiral_sweep({label}): the meshed sweep sits {inside:.4f} inside the field sweep. Both "
        f"are built from the same profile points, so this comparison has been exact everywhere; "
        f"a departure means one of them has started approximating."
    )


@pytest.mark.parametrize("label", sorted(CASES))
def test_each_case_has_real_vertices_to_compare(label: str) -> None:
    """A case whose mesh came back empty would pass the test above by having nothing to check."""
    from tests.field_probe import csg_vertices

    profile, kwargs = CASES[label]
    points = csg_vertices(lambda: profile.spiral_sweep(**kwargs))
    assert len(points) >= 24, (
        f"spiral_sweep({label}) produced {len(points)} vertices; a helix of at least one turn has "
        f"many more, so the comparison above is not measuring the sweep."
    )


def test_a_mirrored_profile_is_caught() -> None:
    """The control: the asymmetric fixtures must be able to tell a flipped thread from a right one.

    Nine cases agreeing to exactly zero is only meaningful if disagreement is visible at all. A
    left-handed helix swept with a right-handed profile is the smallest realistic way to get this
    wrong, and it is the error a symmetric fixture cannot see.
    """
    mirrored = Path2D([[-x, y] for x, y in [[0.0, -1.0], [1.5, 0.0], [0.0, 1.0]]])
    kwargs = {"height": 10.0, "radius": 5.0, "turns": 3.0}
    outside, _, _ = worst_escape(
        lambda: TOOTH.spiral_sweep(**kwargs),
        lambda: sdf_shapes.spiral_sweep(profile=mirrored, **kwargs),
    )
    assert outside > 0.1, (
        f"sweeping a mirrored tooth reads only {outside:.4f} outside the unmirrored field, so the "
        f"comparison cannot distinguish a flipped profile and the agreements above prove less "
        f"than they appear to."
    )


# ----------------------------------------------------------------------------------------
# What is still in the way of the four thread parts.
# ----------------------------------------------------------------------------------------

#: Rods to compare, as (major diameter, pitch, length). The lengths are deliberately a mix of whole
#: and fractional turn counts -- 12, 12, 12, 13 and 15 turns -- because two fixtures at 12 turns is
#: what hid the phase error described below.
RODS = [
    (20.0, 2.5, 30.0),
    (16.0, 2.0, 24.0),
    (10.0, 1.5, 18.0),
    (10.0, 1.5, 19.5),
    (10.0, 1.5, 22.5),
]

#: How far in from an end plane a disagreement may sit and still count as end treatment. The
#: measured figures are 0.065 to 0.181, so this is above the measurement and far below the 9.7 that
#: the mis-phased reconstruction produced -- it cannot be satisfied by a thread that is wrong in the
#: body of the rod.
END_ZONE = 0.25

#: The most any vertex departs, per rod. Scales with pitch, which is what an end-treatment
#: difference should do. Figures may fall, never rise.
WORST_DEPARTURE = 0.60


def _swept_rod(diameter: float, pitch: float, length: float, spin: float) -> object:
    """Build the rod the sweep route would build: a helical thread over a core, trimmed to length.

    This is `ThreadHelix._build`'s own mapping of profile to section -- X is the offset outward from
    the helix radius and Y is height, scaled by pitch -- plus the core cylinder the module header
    describes, plus `_rod_solid`'s own trim.
    """
    import pybosl2.parts.threading as threading

    profile = [[float(x), float(y)] for x, y in threading._trapezoidal_profile(pitch, 60.0, pitch / 2)]
    heights = [p[1] for p in profile]
    depth = (max(heights) - min(heights)) * pitch
    section = Path2D([[(y - max(heights)) * pitch, x * pitch] for x, y in profile])
    thread = sdf_shapes.spiral_sweep(
        profile=section, height=length, radius=diameter / 2, turns=length / pitch, center=True
    )
    if spin:
        thread = thread.rotate(spin, [0, 0, 1])
    core = sdf_shapes.cyl(height=length, radius=diameter / 2 - depth, anchor=[0, 0, 0])
    trim = sdf_shapes.cyl(height=length, radius=diameter / 2 + 1, anchor=[0, 0, 0])
    return (thread | core) & trim


def _grid_against_sweep(diameter: float, pitch: float, length: float) -> "tuple[list[float], float, float]":
    """Compare `_rod_solid`'s grid with the swept rod, at the better of the two phases.

    Returns ``(how far each departing vertex sits in from an end plane, worst departure, count)``.
    """
    import numpy as np

    import pybosl2.parts.threading as threading
    from pybosl2 import use_backend
    from pybosl2.sdf._libfive import lv

    profile = threading._trapezoidal_profile(pitch, 60.0, pitch / 2)
    with use_backend("csg"):
        rod = threading._rod_solid(d=diameter, length=length, pitch=pitch, profile=profile)
    points = np.asarray(rod.vnf().vertices, dtype=float)

    best: "Any | None" = None
    for spin in (0.0, 180.0):
        with use_backend("sdf"):
            swept = _swept_rod(diameter, pitch, length, spin)
        tree = swept._sdf_fn(lv.x(), lv.y(), lv.z())  # type: ignore[attr-defined]
        found = np.asarray([float(tree(float(p[0]), float(p[1]), float(p[2]))) for p in points])
        if best is None or int((found > 1e-6).sum()) < int((best > 1e-6).sum()):
            best = found
    assert best is not None
    departing = best > 1e-6
    inset = (length / 2) - np.abs(points[departing, 2])
    return [float(v) for v in inset], float(best.max()), float(departing.sum())


@pytest.mark.parametrize(("diameter", "pitch", "length"), RODS)
def test_the_thread_grid_differs_only_at_its_cut_ends(diameter: float, pitch: float, length: float) -> None:
    """The route gap is a geometry change, and this is how much of one.

    `ThreadedRod` builds a hand-rolled vertex-array grid, and its refusal says converting it to the
    sweep route "is a geometry change, not a dispatch one". True -- and the change is confined to
    the end treatment: the body of the rod matches the swept construction exactly, and every
    departing vertex sits within a fifth of a millimetre of a cut end plane, where the grid carries
    material the sweep does not. The module header records why: BOSL2's blunt-start and lead-in
    machinery is not ported, so ends are cut flush.

    So whoever closes this gap is porting an end treatment, not a thread.
    """
    inset, worst, count = _grid_against_sweep(diameter, pitch, length)
    assert count > 0, (
        f"the grid and the swept rod now agree everywhere for M{diameter:g}x{pitch:g}. If that "
        f"holds for every rod above, the route gap is closable by dispatch after all -- drop this "
        f"test and convert the part."
    )
    assert max(inset) <= END_ZONE, (
        f"M{diameter:g}x{pitch:g} length {length:g}: a vertex departs {max(inset):.3f} in from the "
        f"end plane, past the {END_ZONE} that end treatment explains. The two constructions now "
        f"differ in the body of the rod, which is a different and larger claim."
    )
    assert worst <= WORST_DEPARTURE, (
        f"M{diameter:g}x{pitch:g}: worst departure {worst:.4f}, above the {WORST_DEPARTURE} "
        f"recorded. Conservative is fine; drifting is not."
    )


def test_the_comparison_is_sensitive_to_half_a_turn() -> None:
    """The trap this measurement fell into, kept so the next reader does not.

    The sweep's phase and the grid's agree only for one of the two half-turn offsets, and *which*
    one depends on the parity of the turn count. Measured at 12 turns the offset is zero and
    everything lines up; at 13 and 15 turns it is 180 degrees. Two fixtures at 12 turns is how
    "differs only at the ends" was nearly recorded from a reconstruction that was half a turn out,
    which reports over half the rod's vertices as departing, by 9.7mm in from the ends rather than
    0.07.

    A part converted to the sweep route without getting this right builds a thread rotated half a
    turn for odd turn counts -- which no bounding box would show.
    """
    import numpy as np

    import pybosl2.parts.threading as threading
    from pybosl2 import use_backend
    from pybosl2.sdf._libfive import lv

    diameter, pitch, length = 10.0, 1.5, 19.5  # 13 turns: odd, so the offset is not zero
    profile = threading._trapezoidal_profile(pitch, 60.0, pitch / 2)
    with use_backend("csg"):
        rod = threading._rod_solid(d=diameter, length=length, pitch=pitch, profile=profile)
    points = np.asarray(rod.vnf().vertices, dtype=float)

    departures = []
    for spin in (0.0, 180.0):
        with use_backend("sdf"):
            swept = _swept_rod(diameter, pitch, length, spin)
        tree = swept._sdf_fn(lv.x(), lv.y(), lv.z())  # type: ignore[attr-defined]
        found = np.asarray([float(tree(float(p[0]), float(p[1]), float(p[2]))) for p in points])
        departures.append(int((found > 1e-6).sum()))

    assert min(departures) < len(points) * 0.1 < max(departures), (
        f"the two half-turn phases now depart on {departures} of {len(points)} vertices. One of "
        f"them used to be a near match and the other half the rod; if they have converged, the "
        f"phase no longer matters and this test has nothing to warn about."
    )


#: A probe grid through the helix: a lattice wide enough to straddle the coil, dense enough that a
#: faceted copy of it could not agree with the exact one everywhere by luck.
def _probe_grid() -> "Any":
    import numpy as np

    axis = np.linspace(-7.0, 7.0, 9)
    vertical = np.linspace(-6.0, 6.0, 7)
    return np.array([[x, y, z] for x in axis for y in axis for z in vertical], dtype=float)


def test_the_skin_sweep_takes_the_exact_route_on_sdf() -> None:
    """What the `skin -> sdf` import buys, which is why it is architecture and not debt.

    `pybosl2.skin` is L2 and `pybosl2.sdf` is L3, so this is an upward import, and it sat in
    `known_violations` until T133 with a reason that reads like a capability and was filed as
    debt: a helical sweep has a closed-form distance field, and `skin`'s own route builds a `VNF`
    and calls `.polyhedron()` on it, which is SPEC B-5's lossy conversion. It cannot go through the
    façade either -- `pybosl2.solid` carries no `spiral_sweep`.

    So this is the `masking -> solid` case with no façade equivalent to reach, and the thing to
    check is not the import but the capability: under `use_backend("sdf")`, `Path2D.spiral_sweep`
    must be the backend's **exact** field, not a mesh of it. Measured here as equality to the last
    bit against the field built directly, with the meshed route as the control -- a lattice of 567
    points where the two agree by 0.0 and the meshed copy does not.
    """
    import numpy as np

    from tests.field_probe import distances

    profile, kwargs = CASES["buttress, 3 turns"]
    points = _probe_grid()

    through_skin = distances(lambda: profile.spiral_sweep(**kwargs), points)
    directly = distances(lambda: sdf_shapes.spiral_sweep(profile=profile, **kwargs), points)
    gap = float(np.abs(through_skin - directly).max())
    assert gap == 0.0, (
        f"Path2D.spiral_sweep under use_backend('sdf') differs from the backend's own "
        f"spiral_sweep by {gap:.6g} -- it is not taking the exact route, so the skin -> sdf edge "
        f"is no longer buying the capability it is listed for (SPEC A-1, B-5)"
    )

    # Two controls, because "equal to 0.0" needs both a reason it could have failed and a reason
    # it matters. First: the grid discriminates -- the same comparison against a helix half a turn
    # longer is not zero, so the agreement above is not a lattice of identical numbers.
    other = dict(kwargs)
    other["turns"] = float(other["turns"]) + 0.5
    apart = float(np.abs(distances(lambda: sdf_shapes.spiral_sweep(profile=profile, **other), points) - directly).max())
    assert apart > 1e-6, (
        f"the probe grid reads two different helices the same to {apart:.3g}, so it cannot tell "
        f"the exact route from any other and the agreement above pins nothing"
    )

    # Second, and this is what makes the edge architecture: there is no way back. Meshing is a
    # one-way door -- `to_sdf` refuses on a CSG solid outright, because a CSG tree has no field --
    # so if `skin` built the sweep as a VNF and handed over the polyhedron, the exactness measured
    # above would be gone with nothing able to recover it. The import is the only route to it.
    from pybosl2 import use_backend
    from pybosl2.exceptions import UnsupportedByBackendError

    with use_backend("csg"), pytest.raises(UnsupportedByBackendError) as excinfo:
        profile.spiral_sweep(**kwargs).to_sdf()
    assert "to_sdf" in str(excinfo.value), (
        "the meshed route can be turned back into a field after all, which would make the "
        "skin -> sdf import a convenience rather than the capability it is listed as"
    )

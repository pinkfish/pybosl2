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
# The four thread parts, and what was actually in the way.
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

#: The profiles every rod is built with, so the agreement is not one thread form's luck. `buttress`
#: is the awkward one: its outline spans the whole pitch, so consecutive turns abut exactly rather
#: than leaving a gap between them.
PROFILES = ("trapezoidal", "iso", "buttress")


def _profile(name: str, pitch: float) -> "Any":
    import pybosl2.parts.threading as threading

    if name == "iso":
        return threading._iso_profile()
    if name == "buttress":
        return threading._buttress_profile()
    return threading._trapezoidal_profile(pitch, 60.0, pitch / 2)


#: How far a grid vertex may sit outside the field, and only where `_on_a_cut_plane` allows it.
#: The two are a pair: a bound on its own would accept a thread that is wrong everywhere by a
#: little, and a location on its own would accept one that is wrong by a lot on the end faces.
BOOLEAN_SLIVER = 0.01


def _grid_against_field(
    diameter: float, pitch: float, length: float, profile: "Any", **kwargs: "Any"
) -> "tuple[float, float]":
    """Compare `_rod_solid`'s grid with `_rod_field`'s field at the grid's own vertices.

    Returns ``(worst departure, how far the worst departing vertex is from a cut plane)``. The
    second is what separates a boolean's own sliver from a thread that disagrees: see
    `tests/field_probe.py`'s T122 note -- an intersection re-triangulates, and the vertices it
    creates lie on *neither* input surface, so an exact field reads them a facet-width out.
    """
    import numpy as np

    import pybosl2.parts.threading as threading
    from pybosl2 import use_backend
    from pybosl2.sdf._libfive import lv

    with use_backend("csg"):
        rod = threading._rod_solid(d=diameter, length=length, pitch=pitch, profile=profile, **kwargs)
        points = np.asarray(rod.vnf().vertices, dtype=float)
    with use_backend("sdf"):
        field = threading._rod_field(
            diameter,
            length,
            pitch,
            profile,
            kwargs.get("starts", 1),
            kwargs.get("left_handed", False),
            None,
            None,
            None,
        )
        tree = field._sdf_fn(lv.x(), lv.y(), lv.z())  # type: ignore[attr-defined]
    found = np.asarray([float(tree(float(p[0]), float(p[1]), float(p[2]))) for p in points])
    if not (found > 1e-6).any():
        return 0.0, 0.0
    worst = points[int(np.argmax(found))]
    return float(found.max()), float(abs(abs(worst[2]) - length / 2))


@pytest.mark.parametrize("name", PROFILES)
@pytest.mark.parametrize(("diameter", "pitch", "length"), RODS)
def test_the_thread_grid_and_the_field_are_the_same_rod(
    name: str, pitch: float, diameter: float, length: float
) -> None:
    """The route gap is closed, and this is what closed it (SPEC PAR-1, PAR-5).

    `ThreadedRod` builds a hand-rolled vertex-array grid, and its refusal used to say that
    converting it to the sweep route "is a geometry change, not a dispatch one". T120 measured the
    change and found it confined to the end treatment -- every departing vertex within a fifth of a
    millimetre of a cut end plane, worst 0.5833 on an M20x2.5. That reading was right and the
    conclusion drawn from it was too cautious: the end treatment is not a treatment at all, it is
    **one extra turn at each end**, which `_thread_grid` has always swept (`len1 = -length/2 -
    pitch`, `turns1 = floor(len1/pitch) - 1`) and the reconstruction did not. Adding it takes the
    worst departure from 0.5833 to 0.0000 on all five rods.

    So the grid stays the CSG route -- it is the BOSL2 port, and a coaxial union of a helix with a
    core is what Manifold does badly -- and `_rod_field` is the SDF one, and they are the same solid
    rather than two approximations of a thread. PAR-5 wants exactly that: the same call, the same
    solid, whichever backend is active.
    """
    outside, from_cut = _grid_against_field(diameter, pitch, length, _profile(name, pitch))
    if outside <= OUTSIDE:
        return
    # Two of the fifteen rods -- both `buttress`, whose outline spans a whole pitch so consecutive
    # turns abut exactly -- leave two vertices 0.0020 and 0.0038 outside, and both sit *on* the trim
    # plane to the digit. The trim is an intersection, and an intersection creates vertices that lie
    # on neither surface it cut; an exact field reads one of those a sliver out. That is
    # `field_probe`'s T122 case, not a disagreement about the thread, and it is held to both a
    # bound and a location so it cannot grow into one.
    where = (
        f"{name} M{diameter:g}x{pitch:g} length {length:g}: the grid has a vertex {outside:.4f} "
        f"outside the field, {from_cut:.4f} from the nearest cut plane. Faceting inscribes, so a "
        f"departure off a cut plane is a real disagreement -- thirteen of the fifteen rods read "
        f"exactly 0.0000 and the other two only on the trim (SPEC PAR-5)."
    )
    assert from_cut <= 1e-6, where
    assert outside <= BOOLEAN_SLIVER, where


@pytest.mark.parametrize(
    "kwargs",
    [
        {"starts": 2},
        {"starts": 3},
        {"left_handed": True},
        {"starts": 2, "left_handed": True},
    ],
    ids=["2 starts", "3 starts", "left-handed", "2 starts left-handed"],
)
def test_the_two_rods_agree_on_starts_and_handedness(kwargs: "dict[str, Any]") -> None:
    """Multi-start and left-hand threads, which are where the phase arithmetic actually bites.

    A multi-start thread's *lead* is `starts * pitch`, not `pitch`, so the coil and the grid step
    by different amounts and only line up once the `starts` rotated copies are unioned. A
    single-start fixture cannot see that at all, which is why these are separate cases.
    """
    outside, _ = _grid_against_field(12.0, 1.5, 19.1, _profile("iso", 1.5), **kwargs)
    assert outside <= OUTSIDE, (
        f"a rod with {kwargs} has a grid vertex {outside:.4f} outside the field; the lead or the "
        f"handedness is no longer carried through to the coil"
    )


def test_the_comparison_is_sensitive_to_half_a_turn() -> None:
    """The trap this measurement fell into, kept so the next reader does not.

    A coil's crests sit at every `bottom + k * lead`, and the grid's at every multiple of the pitch
    from z=0. A *centred* coil of height `length + 2 * lead` puts `bottom` at `-(length/2 + lead)`,
    so the two agree only when `length / (2 * pitch)` is a whole number -- and are half a turn apart
    when it is not. Measured at 12 turns the offset is zero and everything lines up; at 13 and 15
    turns it is 180 degrees, which reports over half the rod's vertices as departing, by 9.7mm in
    from the ends rather than 0.07.

    `_rod_field` cannot be out of phase, because it sweeps the coil up from z=0 and drops it by a
    whole number of leads. This is the control that the probe would have *noticed* if it could: it
    spins the field half a turn and requires the comparison to break.
    """
    import pybosl2.parts.threading as threading

    diameter, pitch, length = 10.0, 1.5, 19.5  # 13 turns: odd, so the offset is not zero
    profile = threading._trapezoidal_profile(pitch, 60.0, pitch / 2)
    outside, _, _ = worst_escape(
        lambda: threading._rod_solid(d=diameter, length=length, pitch=pitch, profile=profile),
        lambda: threading._rod_field(diameter, length, pitch, profile, 1, False, None, None, None).rotate(
            180.0, [0, 0, 1]
        ),
    )
    # 0.51 rather than the 9.7 the mis-phased *reconstruction* produced, because this rod is
    # thread-over-core: a half-turn error moves the thread but not the core, so the departure is
    # bounded by the thread depth rather than by the rod. Five orders of magnitude above EXACT is
    # what the control needs, and 9.7 was never the figure to hold it to.
    assert outside > 0.1, (
        f"turning the field half a turn leaves the grid only {outside:.4f} outside it, so this "
        f"comparison cannot see a mis-phased thread -- which is a thread rotated half a turn for "
        f"odd turn counts, and nothing a bounding box would show"
    )


def test_the_end_turns_are_what_closed_the_gap() -> None:
    """The one measurement the old reading turned on, kept as the standing correction.

    Sweeping only `length / pitch` turns leaves the last quarter-pitch at each end unthreaded,
    because the helix then starts and stops *inside* the rod where a rod cut flush shows a partial
    thread. That is the 0.5833 T120 recorded and read as "a geometry change": it is one turn.
    """
    import numpy as np

    import pybosl2.parts.threading as threading
    from pybosl2 import use_backend
    from pybosl2.path2d import Path2D as _Path2D
    from pybosl2.sdf._libfive import lv

    diameter, pitch, length = 20.0, 2.5, 30.0
    profile = threading._trapezoidal_profile(pitch, 60.0, pitch / 2)
    with use_backend("csg"):
        points = np.asarray(
            threading._rod_solid(d=diameter, length=length, pitch=pitch, profile=profile).vnf().vertices,
            dtype=float,
        )
    prof = [[float(x), float(y)] for x, y in profile]
    section = _Path2D([[y * pitch, x * pitch] for x, y in prof])
    with use_backend("sdf"):
        # The under-swept coil: exactly `length / pitch` turns, centred -- the reconstruction T120
        # measured -- over the same core and trim the shipped form uses.
        short = sdf_shapes.spiral_sweep(
            profile=section, height=length, radius=diameter / 2, turns=length / pitch, center=True
        )
        core = sdf_shapes.cyl(height=length, radius=diameter / 2 + min(p[1] for p in prof) * pitch, anchor=[0, 0, 0])
        trim = sdf_shapes.cyl(height=length, radius=diameter / 2 + 1, anchor=[0, 0, 0])
        tree = ((short | core) & trim)._sdf_fn(lv.x(), lv.y(), lv.z())
    found = np.asarray([float(tree(float(p[0]), float(p[1]), float(p[2]))) for p in points])
    departing = found > 1e-6
    assert departing.any(), (
        "the under-swept coil now contains the whole grid, so the end turns buy nothing and "
        "`_rod_field` is carrying two turns it does not need"
    )
    inset = (length / 2) - np.abs(points[departing, 2])
    assert float(found.max()) == pytest.approx(0.5833, abs=0.01), (
        f"the under-swept coil's worst departure is {found.max():.4f}, not the 0.5833 recorded. "
        f"The figure is pitch-dependent, so this is a different rod or a different sweep."
    )
    assert float(max(inset)) <= 0.25, (
        f"a vertex departs {max(inset):.3f} in from the end plane, past the quarter-millimetre "
        f"that end treatment explains -- so what the end turns fix is no longer only the ends"
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

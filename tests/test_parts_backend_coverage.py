# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""How much of the parts library builds on the SDF backend, measured (SPEC S-46a, PAR-1).

SPEC §12.2's last open item is a *number*: how many parts build on either backend and why the rest
do not. It was written by hand and nothing checked it, which is the failure mode B2-1 names --
"a claim of parity that nothing measures is a wish". It had drifted: the spec said 38 of 53 build
and 15 refuse; the truth is 40 of 51 build and 11 refuse, because the count included an alias
(`manfrotto_rc2_plate` *is* `ManfrottoRC2Plate`) and had not been rerun since parts were ported.

The reason held up exactly, though: **all 11 refusals cite non-convexity**, which is a fact about
the mathematics rather than about effort. An SDF polyhedron is the intersection of its face
half-spaces and so is always convex; a threaded rod, a bevel gear tooth and a jigsaw rail are not.
Closing the gap would mean approximating a distance field for a non-convex mesh, which SPEC B-5
forbids.

So this file pins the number and the reason, and fails when either changes -- including when it
changes for the *better*, so a part that gains an SDF form is recorded rather than absorbed.
"""

from __future__ import annotations

import pytest
from part_fixtures import PARTS, arguments

import pybosl2.sdf  # noqa: F401  -- registers the "sdf" backend
from pybosl2 import use_backend
from pybosl2.exceptions import UnsupportedByBackendError

#: Parts that cannot build on the SDF backend, each because its geometry is a non-convex mesh.
#: **This list only shrinks.** An entry leaves it when the part gains an SDF form; nothing may be
#: added without a stated reason, and "it was easier" is not one (SPEC PAR-2).
#: Of the CSG-only parts, the ones whose gap is **their own route** rather than their shape:
#: the geometry has a distance-field form and this part does not reach it. Kept apart from the
#: genuinely-unclosable ones so a closable gap cannot hide inside an unclosable one, which is
#: what `WireBundle` did until T100 measured it.
#:
#: These four build their thread as a hand-rolled VNF grid. `ThreadHelix`, in the same module,
#: routes a helical thread through `spiral_sweep` and **builds on both backends** -- so "a
#: helical thread has no distance-field form" is false, and was the stated reason for all four
#: (T103). Closing them is a geometry change: replacing a precise thread grid with a sweep,
#: which cannot be validated where libfive is stubbed and an SDF solid meshes to nothing.
#: `WireBundle` belongs here too, by T100's measurement: the SDF backend builds a swept tube
#: along a bent route as a field, so the shape has a distance-field form. Its sweep is a
#: *different function* from the façade's -- the profile lands in another plane -- so closing
#: this one means reconciling two sweeps, which `tests/test_the_two_sweeps_agree.py` pins.
ROUTE_ONLY_PARTS = frozenset({"Nut", "Screw", "ThreadedNut", "ThreadedRod", "WireBundle"})

CSG_ONLY_PARTS = frozenset(
    {
        "BevelGear",  # spiral bevel teeth: a swept non-convex surface
        "ManfrottoRC2Plate",  # dovetail plate profile, swept
        "Nut",  # its thread is a ThreadedNut
        "Rail",  # jigsaw/dovetail rail section, swept
        "Screw",  # its thread is a ThreadedRod
        "ThinningWall",  # a tapered web between two rims
        "ThreadedNut",  # helical thread surface as a VNF grid
        "ThreadedRod",  # helical thread surface as a VNF grid
        "WireBundle",  # each wire is a swept tube along a routed path
        "Worm",  # helical worm thread
        "WormGear",  # throated teeth cut by a worm
    }
)


#: Constructor arguments for parts that need more than their defaults.
def _build_on_sdf(cls: type) -> Exception | None:
    """Return the exception a part raises on the SDF backend, or None if it builds."""
    args, kwargs = arguments(cls)
    try:
        with use_backend("sdf"):
            _ = cls(*args, **kwargs).shape
    except Exception as exc:
        return exc
    return None


def test_every_part_either_builds_on_sdf_or_is_listed() -> None:
    """No part may fail on SDF for a reason nobody wrote down (SPEC PAR-2)."""
    surprises: dict[str, str] = {}
    for name, cls in sorted(PARTS.items()):
        failure = _build_on_sdf(cls)
        if failure is not None and name not in CSG_ONLY_PARTS:
            surprises[name] = f"{type(failure).__name__}: {failure}"[:160]
    assert not surprises, (
        "these parts do not build on the SDF backend and are not in CSG_ONLY_PARTS. Either give "
        f"them an SDF form or add them with a stated reason (SPEC PAR-2): {surprises}"
    )


def test_the_csg_only_list_is_not_stale() -> None:
    """A part that has gained an SDF form comes off the list, so the gap cannot be overstated."""
    now_building = sorted(name for name in CSG_ONLY_PARTS if _build_on_sdf(PARTS[name]) is None)
    assert not now_building, (
        f"these now build on the SDF backend -- remove them from CSG_ONLY_PARTS and update SPEC §12.2: {now_building}"
    )


@pytest.mark.parametrize("name", sorted(CSG_ONLY_PARTS))
def test_each_refusal_names_a_reason_the_spec_accepts(name: str) -> None:
    """The stated reason is the whole justification for the gap, so it is checked per part.

    There are **two** reasons, and separating them is the point. SPEC B-5 forbids approximating a
    distance field, and an SDF polyhedron is the intersection of its face half-spaces -- always
    convex -- so a part whose faces are genuinely non-convex has a gap that **cannot** be closed.
    A part that merely *routes* through a meshing call has a gap that **can**, and conflating the
    two is what let `WireBundle`'s refusal stand for as long as it did: it claimed a swept tube has
    no distance-field form when the SDF backend has a `path_sweep` that builds one (T100).

    This guard used to accept only the first reason, and the better, more honest message for the
    second kind failed it. That was the right alarm and the wrong conclusion -- its own docstring
    warned that a different reason "would be a gap that *could* be closed, hiding inside one that
    cannot", which is exactly what these are. So the two are listed separately and each part has to
    say which it is.
    """
    failure = _build_on_sdf(PARTS[name])
    assert isinstance(failure, UnsupportedByBackendError), (
        f"{name} is listed CSG-only but failed with {type(failure).__name__}: {failure}"
    )
    # Matched on meaning rather than one spelling: a part that builds lazily refuses from its own
    # `shape` with its own wording rather than from a generic guard at construction, and pinning a
    # literal substring made the *better*, more specific message look like a different reason.
    shape_reasons = ("non-convex", "not convex", "no distance-field form", "has no closed-form")
    route_reasons = ("hand-rolled VNF grid", "not the same sweep", "this part's route")
    message = str(failure)
    expected = ROUTE_ONLY_PARTS if name in ROUTE_ONLY_PARTS else ()
    if expected:
        assert any(reason in message for reason in route_reasons), (
            f"{name} is listed as a *route* gap -- the shape has a distance-field form and this "
            f"part does not reach it -- but its refusal does not say so: {failure}"
        )
        return
    assert any(reason in message for reason in shape_reasons), (
        f"{name} refuses for a reason SPEC §12.2 does not accept. A gap is either the shape's "
        f"(non-convex faces, no closed form) or this part's route, and a route gap belongs in "
        f"ROUTE_ONLY_PARTS where it is visibly closable: {failure}"
    )


def test_the_measured_coverage_matches_what_the_spec_claims() -> None:
    """SPEC §12.2 states a number; this is the thing that makes it true (SPEC B2-1)."""
    from pathlib import Path

    building = sum(1 for cls in PARTS.values() if _build_on_sdf(cls) is None)
    assert building == len(PARTS) - len(CSG_ONLY_PARTS)

    spec = (Path(__file__).resolve().parent.parent / "SPEC.md").read_text()
    section = spec.split("### 12.2 Open", 1)[1].split("## 13.", 1)[0]
    assert f"{building} of the {len(PARTS)} parts" in section, (
        f"SPEC §12.2 does not state the measured figure. It is {building} of {len(PARTS)} parts "
        f"building on either backend, with {len(CSG_ONLY_PARTS)} refusing."
    )


def test_a_route_gap_is_one_the_backend_could_build() -> None:
    """The claim that makes `ROUTE_ONLY_PARTS` mean something, asserted rather than asserted-at.

    A part is in that list because its *shape* has a distance-field form and the part does not
    reach it. For the four threading entries the witness is in the same module: `ThreadHelix`
    sweeps a helical thread through `spiral_sweep` and builds on **both** backends. So "a helical
    thread has no distance-field form" -- the reason all four carried until T103 -- is false, and
    this is what falsifies it. For `WireBundle` the witness is in
    `tests/test_the_two_sweeps_agree.py`.

    Without this, the split between a closable and an unclosable gap would be two lists and a
    comment, which is the arrangement that let the false reason stand in the first place.
    """
    from pybosl2.parts.threading import ThreadHelix

    sizes = {}
    for backend in ("csg", "sdf"):
        with use_backend(backend):
            sizes[backend] = [float(v) for v in ThreadHelix(d=10.0, pitch=1.5, turns=6).shape.bounds().size]
    assert sizes["csg"] == pytest.approx(sizes["sdf"], abs=0.5), (
        f"ThreadHelix is the witness that a helical thread has a distance-field form, and the two "
        f"backends no longer agree on it: {sizes}"
    )


def test_the_route_gap_list_only_shrinks() -> None:
    """A part that gains an SDF form comes off both lists, so the gap cannot be overstated."""
    assert ROUTE_ONLY_PARTS <= CSG_ONLY_PARTS, (
        f"{sorted(ROUTE_ONLY_PARTS - CSG_ONLY_PARTS)} are listed as route gaps but are not "
        f"CSG-only, so they build on SDF and should be off both lists"
    )
    assert len(ROUTE_ONLY_PARTS) <= 5, (
        f"{sorted(ROUTE_ONLY_PARTS)} -- this list only shrinks. A new entry needs a witness that "
        f"the shape has a distance-field form, as `test_a_route_gap_is_one_the_backend_could_build` "
        f"gives for the threading four"
    )

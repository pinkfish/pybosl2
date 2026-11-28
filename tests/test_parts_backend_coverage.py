# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""How much of the parts library builds on the SDF backend, measured (SPEC S-46a, PAR-1).

SPEC §12.2's last open item is a *number*: how many parts build on either backend and why the rest
do not. It was written by hand and nothing checked it, which is the failure mode B2-1 names --
"a claim of parity that nothing measures is a wish". It had drifted: the spec said 38 of 53 build
and 15 refuse; the truth was 40 of 51 build and 11 refuse, because the count included an alias
(`manfrotto_rc2_plate` *is* `ManfrottoRC2Plate`) and had not been rerun since parts were ported.

**It is 47 of 51 now, with 4 refusing** (T142). The reason the other eleven carried did not survive
being checked, which is the fifth time that has happened to a stated reason in this campaign:

* `WireBundle` claimed the backend's own `path_sweep` built a different solid. It did, and the
  cause was that the backend walked the path and built its *own* rotation-minimizing frames rather
  than taking the stations the meshed sweep places its cross sections with. One frame
  implementation later the two agree at exactly 0.0 (`tests/test_the_two_sweeps_agree.py`).
* `Nut`, `Screw`, `ThreadedNut` and `ThreadedRod` claimed converting the thread grid to the sweep
  route was "a geometry change". The change turned out to be two lines: sweep a whole turn past
  each end -- which the grid itself already does -- and take the phase from a coil swept up from
  z=0 rather than a centred one. Fourteen rods, every vertex at exactly 0.0
  (`tests/test_the_two_spiral_sweeps_agree.py`).
* `Worm` claimed a helical thread is "a non-convex mesh with no distance-field form". A worm is a
  *twisted prism* of one fixed cross-section, which has an exact field -- and so, therefore, does
  `linear_extrude(twist=)`, which T14 recorded as the one extrusion option a field "genuinely
  cannot express" (`tests/test_a_twisted_extrusion_has_a_field.py`).
* `ManfrottoRC2Plate` claimed `linear_sweep()`. Its profile sweep *is* a plain extrusion, and
  `linear_extrude` has dispatched since T14's `walls` finding; what actually held it was its last
  three lines, which went through CSG-only anchoring machinery.

So this file pins the number and the reason, and fails when either changes -- including when it
changes for the *better*, so a part that gains an SDF form is recorded rather than absorbed.
"""

from __future__ import annotations

import pytest
from part_fixtures import PARTS, arguments

import pybosl2.sdf  # noqa: F401  -- registers the "sdf" backend
from pybosl2 import use_backend
from pybosl2.exceptions import UnsupportedByBackendError

#: Parts that cannot build on the SDF backend. **This list only shrinks.** An entry leaves it when
#: the part gains an SDF form; nothing may be added without a stated reason, and "it was easier" is
#: not one (SPEC PAR-2).
#:
#: All four are a **loft**: a stack of cross-sections, each placed by its own transform, skinned
#: into a surface. A field reads a loft pointwise, and that needs two things -- recovering which
#: station a point belongs to, and undoing that station's transform. The library has both for the
#: lofts it builds as fields: a twisted prism recovers its station from `z` and undoes a rotation
#: (T142), a helical sweep recovers its station from `atan2` and undoes a rotation and a radius
#: (T14), a tapered prism recovers its station from `z` and undoes a uniform scale (T14).
#:
#: These four have neither. `BevelGear` and `WormGear` scale their sections as well as turning
#: them, around a cone and a throat arc, so a point does not say which station it came from;
#: `Rail` and `ThinningWall` are hand-written triangle lists whose sections are not related by any
#: single transform at all. Closing them needs a convex decomposition of a 3-D mesh, or a lofted
#: prism whose cross-section is interpolated per point from tree-valued vertices -- a new
#: primitive either way, not a route. The per-part refusals carry the measurements.
CSG_ONLY_PARTS = frozenset(
    {
        "BevelGear",  # 3,440-face loft down a cone, sections scaled as well as turned
        "Rail",  # 52-face hand-written polyhedron, ends tapering into the body
        "ThinningWall",  # 44-face hand-written polyhedron, a tapered web between two rims
        "WormGear",  # 11,016-face loft around a throat arc, sections scaled, turned and moved
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

    The vocabulary this guard accepts has been narrowed twice, and both times by a reason that
    turned out to be false.

    It first accepted only *"the shape is non-convex"*. That let `WireBundle` sit behind a claim
    that a swept tube has no distance-field form while the backend had a `path_sweep` building one
    (T100), so a second category -- a **route** gap, where the shape has a form and the part does
    not reach it -- was added beside it. Every entry in that second list is now closed (T142), and
    with it the first category's wording: "a non-convex mesh has no distance-field form" was the
    reason `Worm` carried, and a worm is a twisted prism with an exact field.

    So what is accepted now is the *specific* obstacle, stated as a property of the loft: a
    station that cannot be recovered from the point, or sections not related by any one transform.
    A refusal falling back to "non-convex" alone fails here, because that sentence has been wrong
    about five parts.
    """
    failure = _build_on_sdf(PARTS[name])
    assert isinstance(failure, UnsupportedByBackendError), (
        f"{name} is listed CSG-only but failed with {type(failure).__name__}: {failure}"
    )
    # Matched on meaning rather than one spelling: a part that builds lazily refuses from its own
    # `shape` with its own wording rather than from a generic guard at construction, and pinning a
    # literal substring made the *better*, more specific message look like a different reason.
    accepted = (
        "not recoverable from the point",
        "recoverable from neither",
        "no station transform to undo",
        "not related by any",
        "given vertex by vertex",
    )
    message = str(failure)
    assert any(reason in message for reason in accepted), (
        f"{name} refuses for a reason SPEC §12.2 does not accept. The accepted reason names what "
        f"about this loft a field cannot read -- which station a point belongs to, or what "
        f"transform to undo. 'A non-convex mesh has no distance-field form' is not it: that "
        f"sentence was the stated reason for five parts that now build (T142). Got: {failure}"
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


def test_the_csg_only_list_only_shrinks() -> None:
    """The gap cannot be overstated, and cannot grow back.

    `ROUTE_ONLY_PARTS` lived here until T142 -- the five parts whose gap was their own route rather
    than their shape, kept in a separate list so a closable gap could not hide inside an unclosable
    one. All five are closed, so the list is gone rather than kept at zero: an empty frozenset with
    a test over it says nothing, and the four that remain each state their own obstacle.
    """
    assert len(CSG_ONLY_PARTS) <= 4, (
        f"{sorted(CSG_ONLY_PARTS)} -- this list only shrinks. It went 11 -> 4 in T142, and every "
        f"one of the seven that left did so because a *stated reason* turned out to be false, not "
        f"because a new engine was written. A new entry needs an obstacle nobody has falsified."
    )


def test_a_loft_a_field_can_read_still_builds() -> None:
    """The three lofts the library *does* build as fields, which is what makes the four a real gap.

    `CSG_ONLY_PARTS`'s reason is a claim about lofts in general -- that a field reads one by
    recovering its station and undoing its transform -- so it only means something while the lofts
    that *can* be read that way still are. One witness each:

    * a **helix**, whose station comes from `atan2` (`ThreadHelix`, T14),
    * a **twisted prism**, whose station comes from `z` (`Worm`, T142),
    * a **tapered prism**, whose station comes from `z` and whose transform is a uniform scale
      (`regular_prism(radius1=, radius2=)`, T14).

    Without this the reason would be a sentence with nothing behind it, which is the arrangement
    that let the false reasons stand for as long as they did.
    """
    from pybosl2.parts.gears import Worm
    from pybosl2.parts.threading import ThreadHelix
    from pybosl2.solid import regular_prism

    builders = {
        "helix": lambda: ThreadHelix(d=10.0, pitch=1.5, turns=6).shape,
        "twisted prism": lambda: Worm(mod=3, diameter=20, length=40).shape,
        "tapered prism": lambda: regular_prism(6, height=10, radius1=8, radius2=4),
    }
    for label, build in builders.items():
        sizes = {}
        for backend in ("csg", "sdf"):
            with use_backend(backend):
                sizes[backend] = [float(v) for v in build().bounds().size]
        assert sizes["csg"] == pytest.approx(sizes["sdf"], abs=0.5), (
            f"the {label} is the witness that a field can read that kind of loft, and the two "
            f"backends no longer agree on it: {sizes}"
        )

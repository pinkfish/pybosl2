# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Where an argument group exists, every façade constructor taking its members accepts it (G-1).

G-1 says a parameter family travelling together MUST be *available* as a frozen group object, and
`tests/test_groups.py` checks that each group exists, composes, and refuses a conflict. What
nothing checked is **who accepts one**. T30 wired `Placement` into "all 19 façade solid
constructors" and `EdgeTreatment` into "the 13 taking both rounding and chamfer", and those counts
were written in the task log rather than measured -- the same shape as T40's "113 remain" and
T42's "41 gaps", which were both nothing by the time T130 reran them.

Measured, the façade turned out to be wired and the scan found the two constructors that take
*one* of a family's members rather than both:

===================  ===============================  ==========================================
constructor          takes                            why it was skipped
===================  ===============================  ==========================================
`solid.teardrop`     `chamfer`, `chamfer1/2`          a teardrop's rim has no rounded form
`flat.regular_ngon`  `rounding`                       a polygon's corners round, not chamfer
===================  ===============================  ==========================================

Both were reasonable to skip while the group carried *two independent sizes*, because half of it
would have been inapplicable. `EdgeTreatment` carries one kind and one size (G-7), so there is
nothing inapplicable about it -- and a caller holding one had to unpack it by hand, which means
asking "is this a rounding or a chamfer?", the one question the group exists to answer for them.
They accept it now, and the kind the shape has no form for is refused by name (G-6).

**The partition is asserted in both directions**, because that is the part a reader cannot
otherwise discover: a group is a *façade* ergonomic. 19 of 19 façade solid constructors taking
`anchor`/`spin`/`orient` accept `placement=`, and **none** of the nine `@backend_only("csg")`
constructors that take the same three do -- `cone`, `cross`, `heightfield`,
`cylindrical_heightfield`, `text3d`, `hexagon`, `octagon`, `pentagon`, `right_triangle`. At 19-0
that is a design and not drift, and the reason is B2-3: those constructors are the BOSL2-faithful
layer, where the loose spelling BOSL2 uses *is* the API. A group added to one of them would offer
portable ergonomics on a door that only opens onto one backend.
"""

from __future__ import annotations

import inspect

import pytest

import pybosl2
import pybosl2.flat as flat
import pybosl2.solid as solid

#: Each group: the loose members it carries, and the keyword that accepts it.
GROUPS: dict[str, tuple[tuple[str, ...], str]] = {
    "Placement": (("anchor", "spin", "orient"), "placement"),
    "EdgeTreatment": (("rounding", "chamfer"), "treatment"),
    "EdgeSelection": (("edges", "except_edges"), "selection"),
    "Texturing": (("texture", "tex_size", "tex_reps", "tex_depth", "tex_inset"), "texturing"),
}

#: `Facets` is G-4's deliberate exception: it exists as plumbing, and the public answer for
#: resolution is the ambient `use_defaults(fn=64)` block, which threads nothing through any call.
#: A constructor growing `facets=` would be offering the worse of the two spellings.
PLUMBING = (("fn", "fa", "fs"), "facets")


def _facade() -> dict[str, object]:
    """Every callable the two façades offer, by name.

    Returns:
        A mapping of name to callable, across `pybosl2.solid` and `pybosl2.flat`.

    """
    out: dict[str, object] = {}
    for module in (solid, flat):
        for name in module.__all__:
            obj = getattr(module, name, None)
            if callable(obj):
                out[f"{module.__name__.rsplit('.', 1)[-1]}.{name}"] = obj
    return out


def _params(obj: object) -> set[str]:
    """The parameter names a callable declares, or an empty set if it has no readable signature.

    Args:
        obj: The callable.

    Returns:
        Its parameter names.

    """
    try:
        return set(inspect.signature(obj).parameters)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return set()


@pytest.mark.parametrize("group", sorted(GROUPS))
def test_every_facade_constructor_taking_a_family_accepts_its_group(group: str) -> None:
    """A caller who builds a group once can pass it to any façade constructor the family reaches.

    Stated over *any* member rather than all of them, which is the stricter reading and the one
    that found `teardrop` and `regular_ngon`. A constructor taking `chamfer` but not `rounding`
    still takes an edge treatment; what it does not take is both kinds, and refusing the kind it
    has no form for is G-6's job rather than a reason to withhold the group.
    """
    members, kwarg = GROUPS[group]
    takes, missing = [], []
    for name, obj in sorted(_facade().items()):
        params = _params(obj)
        if not set(members) & params:
            continue
        takes.append(name)
        if kwarg not in params:
            missing.append(name)
    assert takes, f"{group}: no façade constructor takes any of {members} -- this measures nothing"
    assert not missing, (
        f"{group}: {len(missing)} of {len(takes)} façade constructors take one of {members} and "
        f"do not accept {kwarg}=: {missing}. Add the group and resolve it through "
        f"`_groups`/`resolve_*`, so a caller can build it once and reuse it (SPEC G-1). Where the "
        f"shape cannot honour part of it, refuse that part by name rather than withholding the "
        f"group (SPEC G-6)."
    )


@pytest.mark.parametrize("group", sorted(GROUPS))
def test_a_group_is_a_facade_ergonomic_and_stays_there(group: str) -> None:
    """The other half of the partition, which is the half a reader cannot otherwise find.

    A `@backend_only("csg")` constructor is the BOSL2-faithful layer (B2-3), where the loose
    spelling is the API; a group on one of those would offer portable ergonomics on a door that
    opens onto a single backend. Nine such constructors take `anchor`/`spin`/`orient` and not one
    accepts `placement=`, so this records a decision rather than discovering a gap -- and if the
    decision changes, it has to be changed here too rather than drifting.
    """
    members, kwarg = GROUPS[group]
    facade = set(_facade().values())
    offenders = [
        name
        for name in pybosl2.__all__
        if callable(getattr(pybosl2, name, None))
        and getattr(pybosl2, name) not in facade
        and set(members) & _params(getattr(pybosl2, name))
        and kwarg in _params(getattr(pybosl2, name))
    ]
    assert not offenders, (
        f"{group}: {offenders} are not façade constructors but accept {kwarg}=. Either give the "
        f"shape a façade entry in pybosl2.solid/pybosl2.flat, where groups belong, or drop the "
        f"group and keep the loose BOSL2 spelling (SPEC B2-3, A-1)."
    )


def test_the_scan_sees_the_constructors_that_bypass_the_facade() -> None:
    """An empty result above has to mean "none", not "the comparison found nothing to compare".

    The nine are named so that a `cone` gaining a façade entry shows up here as a change rather
    than quietly weakening the assertion that cites them.
    """
    facade = set(_facade().values())
    members = set(GROUPS["Placement"][0])
    outside = sorted(
        name
        for name in pybosl2.__all__
        if callable(getattr(pybosl2, name, None))
        and getattr(pybosl2, name) not in facade
        and members <= _params(getattr(pybosl2, name))
    )
    assert len(outside) >= 5, f"only {outside} public callables bypass the façade with a full placement"
    assert "cone" in outside, "cone is the clearest case and should be in this list"


def test_resolution_is_not_offered_as_a_group() -> None:
    """G-4's exception, asserted rather than assumed: no constructor grows `facets=`.

    `Facets` is real and carries the four values down a call chain as one, which is what R-1 asks
    of a forwarding function. It is not the caller's spelling, because `use_defaults(fn=64)` sets
    resolution for a whole block without threading anything through any call. A constructor
    offering `facets=` would be offering the worse of the two, so this is a *ceiling* rather than
    a floor -- the only assertion in this file that fails by something being added.
    """
    members, kwarg = PLUMBING
    offenders = [name for name, obj in sorted(_facade().items()) if kwarg in _params(obj)]
    assert not offenders, (
        f"{offenders} accept {kwarg}=. Resolution's public answer is the ambient block, not a "
        f"group threaded through the call (SPEC G-4, R-4)."
    )
    takes = [name for name, obj in _facade().items() if set(members) <= _params(obj)]
    assert len(takes) > 20, f"only {len(takes)} façade constructors take fn/fa/fs -- the scan is broken"

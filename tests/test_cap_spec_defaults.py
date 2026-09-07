# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A dimension left out of a `CapSpec` is not supplied; it is not zero.

SPEC D-4, G-8. D-4 says `None` means "not supplied, decide for me" and never "off", and that "off"
is `0`, `False`, or an explicit enum member. `CapSpec` had it exactly backwards: every numeric
field defaulted to `0.0`, so a spec built by naming the one thing the caller cared about declared
every *other* dimension off.

That is worse than it sounds, because a cap with no dimensions is not an error. `endcap_polys`
returns a five-point polygon of zero size, which unions to nothing, so:

* `CapSpec(CapType.ARROW)` drew no arrow.
* `CapSpec(CapType.ARROW, color="red")` -- a caller who wanted a red arrow -- drew no arrow.
* `CapSpec(CapType.ARROW, length=3.5)` still drew no arrow, because `width` remained 0.0 and
  `endcap_polys` reads the size as `length * width`, so naming the obvious field did not help.

`normalize_one` was the other half. Its docstring promised a "fully-resolved" `CapSpec` and, one
sentence later, that a `CapSpec` is "returned unchanged" -- and both cannot hold for a spec that
names only some of its fields. It fills from the same table now, and `endcap_polys` calls it
rather than trusting its caller, because the failure it prevents is silent either way.

D-4 had `enforced_by = []` before this file: a rule stated in the requirements registry that
nothing checked. These assertions are as much about the rule as about `CapSpec`.
"""

from __future__ import annotations

import dataclasses

import pytest

from pybosl2.caps import _DEFAULTS, CapSpec, CapType, endcap_polys, normalize_one

#: The numeric fields D-4 governs.
DIMENSIONS = ("length", "width", "height", "extent", "angle")

#: Every member with a table entry that draws something. `NONE`/`BUTT`/`CUSTOM` draw nothing by
#: definition, so "unset resolves to something that draws" does not apply to them.
DRAWS = [c for c in _DEFAULTS if c not in (CapType.NONE, CapType.BUTT, CapType.CUSTOM)]


def _reach(spec: CapSpec | CapType) -> float:
    """How far the cap's outline extends along the line direction, at a width of 4."""
    xs = [point[0] for poly in endcap_polys(normalize_one(spec), 4.0) for point in poly]
    return max(xs) if xs else 0.0


@pytest.mark.parametrize("field", DIMENSIONS)
def test_an_unnamed_dimension_defaults_to_not_supplied(field: str) -> None:
    """SPEC D-4: the sentinel is `None`, so that "off" stays available as an explicit 0."""
    default = next(f.default for f in dataclasses.fields(CapSpec) if f.name == field)
    assert default is None, f"CapSpec.{field} defaults to {default!r}, which D-4 reserves for off"


@pytest.mark.parametrize("cap", DRAWS, ids=lambda c: c.name)
def test_a_spec_naming_nothing_draws_what_the_bare_enum_draws(cap: CapType) -> None:
    """SPEC D-4: `CapSpec(X)` and `X` are the same request, so they must produce the same cap."""
    assert _reach(CapSpec(cap)) == pytest.approx(_reach(cap)), f"CapSpec({cap.name}) differs from the bare {cap.name}"


@pytest.mark.parametrize("cap", DRAWS, ids=lambda c: c.name)
def test_naming_only_a_colour_does_not_erase_the_cap(cap: CapType) -> None:
    """SPEC D-4: the case a user actually hits -- one field named, and the shape disappears.

    Colour is the field with no geometric meaning at all, which is what makes it the sharpest
    version of the defect: nothing about setting it should change what is drawn.
    """
    assert _reach(CapSpec(cap, color="red")) == pytest.approx(_reach(cap)), (
        f"CapSpec({cap.name}, color=...) draws a different cap from {cap.name}"
    )


def test_an_explicit_zero_still_means_off() -> None:
    """SPEC D-4: the other half of the rule, and the one a `None` default could have cost.

    Filling *every* unset field from the table would put the right cap on the page and quietly
    ignore a caller who asked for none of it. `0` is off, and stays off.
    """
    assert _reach(CapSpec(CapType.ARROW, length=0.0)) == pytest.approx(0.0)
    assert _reach(CapSpec(CapType.ARROW)) > 1.0, "the pairing is vacuous if the default draws nothing"


def test_a_named_dimension_is_the_one_that_changes() -> None:
    """SPEC D-4: resolution fills the gaps and does not overwrite what the caller said."""
    plain = _reach(CapSpec(CapType.ARROW))
    assert _reach(CapSpec(CapType.ARROW, length=7.0)) == pytest.approx(plain * 2.0)


def test_resolution_is_idempotent() -> None:
    """SPEC D-4: `normalize_one` runs at the point of use, so running it twice must be harmless.

    It fills what the *table* declares, which is not every field: `_DEFAULTS` leaves `height` and
    `angle` unset for most types, and those read as 0 -- their documented neutral, not a dimension
    switched off behind the caller's back. So the assertion is that resolution reaches a fixed
    point, and that every field the table names arrives.
    """
    once = normalize_one(CapSpec(CapType.ARROW, length=7.0))
    assert normalize_one(once) == once
    table = _DEFAULTS[CapType.ARROW]
    declared = [name for name in DIMENSIONS if getattr(table, name) is not None]
    assert declared, "the ARROW row declares no dimensions; the test below is vacuous"
    assert all(getattr(once, name) is not None for name in declared), once


def test_the_polygon_builder_resolves_rather_than_trusting_its_caller() -> None:
    """SPEC G-8: an unresolved spec must not read as a cap of size zero.

    This is where the fix nearly stopped short. Moving the defaults to `None` fixed every caller
    that went through `normalize_one` and left `endcap_polys` reading `None` as zero for anyone who
    did not -- the same silent nothing, one layer down. The round-over tests walked into it.
    """
    unresolved = CapSpec(CapType.ARROW)
    assert any(getattr(unresolved, name) is None for name in DIMENSIONS), "not an unresolved spec"
    assert _reach(unresolved) > 1.0
    xs = [point[0] for poly in endcap_polys(unresolved, 4.0) for point in poly]
    assert max(xs) > 1.0, "endcap_polys read an unresolved spec as a cap of size zero"

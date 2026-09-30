# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""A part answers its dimensions as data, without building geometry (SPEC S-46).

S-46 says parts must expose their catalogue as data "so a caller can query dimensions -- and the
docs can tabulate them -- without building geometry". The spec objects existed and the parts tests
read dimensions off them, so the rule looked kept; nothing required a *new* part to do it, and
seven did not. Five cubetruss parts, `Worm` and `Rack2d` had **no public property at all**: their
arguments went into an opaque `self._args` tuple, under a comment reading "The spec above is all a
caller needs to *measure* this part", which was true of the parts it was copied from and false
where it had landed.

Two clauses, because S-46 and C-14 each own half and a part could otherwise sit in the gap:

* every part exposes at least one queryable dimension -- S-46's own clause;
* a part answers it without building, unless it is on C-14's `EAGER_PARTS` ratchet, which is the
  list of parts that build in `__init__` and is tracked separately.

The third test pins the two together: the parts that answer only after a build must be *exactly*
`EAGER_PARTS`. Without it, a part could lose its laziness and stay green here by being eager, or
gain laziness and leave the ratchet overstated -- which is the failure T92 found in that list.
"""

from __future__ import annotations

import inspect

import pytest
from part_fixtures import PARTS, arguments
from test_parts_are_lazy import _CACHES, EAGER_PARTS, _is_geometry


def _catalogue(cls: type) -> list[str]:
    """Public dimension properties, across the whole MRO.

    `vars(cls)` sees only a class's own properties, which counted `HerringboneGear` as exposing
    nothing when it inherits `SpurGear`'s entire catalogue.
    """
    return sorted(
        name
        for name, _ in inspect.getmembers(cls, lambda o: isinstance(o, property))
        if not name.startswith("_") and name != "shape"
    )


def _answers_without_building(cls: type) -> list[str]:
    """Properties that can be read without geometry appearing in a cache."""
    args, kwargs = arguments(cls)
    readable = []
    for name in _catalogue(cls):
        part = cls(*args, **kwargs)  # fresh: a cache stays set once written
        try:
            getattr(part, name)
        except Exception:
            continue
        if not any(_is_geometry(getattr(part, cache, None)) for cache in _CACHES):
            readable.append(name)
    return readable


@pytest.mark.parametrize("name", sorted(PARTS))
def test_every_part_exposes_a_dimension(name: str) -> None:
    """SPEC S-46: a part whose arguments vanish into a tuple cannot be queried or tabulated."""
    assert _catalogue(PARTS[name]), (
        f"{name} exposes no public property but `shape`, so nothing can ask it a dimension "
        f"without building it (SPEC S-46)"
    )


@pytest.mark.parametrize("name", sorted(set(PARTS) - set(EAGER_PARTS)))
def test_a_lazy_part_answers_without_building(name: str) -> None:
    """SPEC S-46: querying the catalogue must not cost a CAD run.

    *Every* property, not merely one of them. The first draft asked whether any could be read
    without building, and the control that plants a build inside one property passed it -- a part
    with four dimensions still had three clean ones. "At least one" is the assertion that survives
    the defect it is meant to catch.
    """
    cls = PARTS[name]
    builders = sorted(set(_catalogue(cls)) - set(_answers_without_building(cls)))
    assert not builders, (
        f"reading {name}.{builders[0] if builders else ''} builds geometry. {name} is not on "
        f"C-14's EAGER_PARTS ratchet, so its whole catalogue must answer without a CAD run "
        f"(SPEC S-46). Properties that build: {builders}"
    )


def test_the_two_rules_leave_no_gap_between_them() -> None:
    """The parts that answer only after a build are exactly the ones C-14 already tracks.

    Checked in both directions on purpose. A part that lost its laziness could otherwise stay green
    above by being eager, and a part that gained it would leave `EAGER_PARTS` overstating the gap
    -- which is the defect T92 found sitting in that list for two entries.
    """
    build_first = {name for name, cls in PARTS.items() if _catalogue(cls) and not _answers_without_building(cls)}
    assert build_first == set(EAGER_PARTS), (
        f"the parts answering only after a build are {sorted(build_first)}, but C-14's ratchet "
        f"says {sorted(EAGER_PARTS)}. Whichever moved, the two records must agree"
    )


def test_the_catalogue_scan_finds_something() -> None:
    """A property walk that found nothing would make every test above vacuous."""
    total = sum(len(_catalogue(cls)) for cls in PARTS.values())
    assert total > 100, f"only {total} public properties found across {len(PARTS)} parts"

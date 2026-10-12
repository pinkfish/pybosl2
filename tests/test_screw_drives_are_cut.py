# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""An accepted screw head and drive builds its own solid, or is a recorded synonym (SPEC G-8).

T104 found a scope hole in T98's enum sweep and fixed one case. T98 had reported **ten** enums as
having no public dispatch site, having looked for each in a signature; T98 itself investigated one
and T104 another, leaving eight dismissed by a probe now known to under-report. Asking the question
of those eight found this.

**`ScrewDriveType.SLOT` cut nothing.** `_build_drive_recess` has a `SLOT` branch -- it even carries
a `width = size if size else ...` fallback -- and it was unreachable: every head branch in
`_resolve_head` resolves `drive_size`/`drive_depth` only for `HEX`, so a slot arrived with both
`None`, hit the `not size or not depth` early return, and produced **no recess at all**. A slotted
screw was byte-identical to an undriven one. The builder was there the whole time, and the fallback
inside it could never have run.

Two further things the same probe measured, which are *not* fixed here:

* `SOCKET_RIBBED` builds as `SOCKET` and `ROUND` builds as `PAN`, both deliberately -- the dispatch
  groups them -- and neither said so. Documented on the enum now, the way G-8 required
  `CapType.SPHERE` be documented as a synonym of `ROUND`, and asserted below so the claim and the
  code cannot drift apart.
* `drive=HEX` is silently ignored on `HEX`, `PAN`, `ROUND` and `FLAT` heads. On a `HEX` head that is
  correct: the drive is a wrench on the head. On the other three it is a gap, and whether a
  countersunk head should carry a hex socket is a question about screw standards rather than about
  dispatch -- so it is listed with its measurement rather than guessed at.
"""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from pybosl2 import use_defaults
from pybosl2.parts.enums import ScrewDriveType, ScrewHeadType
from pybosl2.parts.screws import Screw

FACETS = 24
SPEC, LENGTH = "M6", 20

#: Head pairs that build the same solid on purpose, each with the reason. A pair here is a claim
#: that the second spelling is *unmodelled*, not that the two shapes coincide by accident.
DOCUMENTED_SYNONYMS = {
    (ScrewHeadType.SOCKET, ScrewHeadType.SOCKET_RIBBED): "the ribbing is a knurl no table describes",
    (ScrewHeadType.PAN, ScrewHeadType.ROUND): "both are the domed head the pan table gives",
}

#: Heads on which `drive=HEX` cuts nothing, with the reason. Only shrinks: giving one a socket
#: removes it. `HEX` is permanent -- a hex head is driven from outside, so a recess would be wrong.
HEX_DRIVE_NOT_CUT = {
    ScrewHeadType.HEX: "driven by a wrench on the head, so a recess would be wrong",
    ScrewHeadType.PAN: "no hex-socket dimensions in the pan table",
    ScrewHeadType.ROUND: "modelled as PAN, so it inherits the same gap",
    ScrewHeadType.FLAT: "no hex-socket dimensions in the countersunk table",
}


def _solid(head: ScrewHeadType, drive: ScrewDriveType) -> tuple[float, tuple[float, ...]]:
    with use_defaults(fn=FACETS):
        mesh = Screw(SPEC, LENGTH, head=head, drive=drive).shape.vnf()
    points = np.asarray([[float(c) for c in p] for p in mesh.vertices], dtype=float)
    return (round(float(mesh.volume()), 4), tuple(np.round(np.sort(points, axis=0).ravel(), 4)))


@pytest.mark.parametrize("head", sorted(ScrewHeadType, key=lambda h: h.name), ids=lambda h: h.name)
def test_a_slot_drive_cuts_a_slot(head: ScrewHeadType) -> None:
    """SPEC G-8: `SLOT` was accepted everywhere and cut nothing anywhere."""
    plain = _solid(head, ScrewDriveType.NONE)
    slotted = _solid(head, ScrewDriveType.SLOT)
    assert slotted != plain, (
        f"Screw(head={head.name}, drive=SLOT) is the same solid as drive=NONE. The SLOT branch in "
        f"`_build_drive_recess` is unreachable unless `_resolve_head` resolves its dimensions"
    )
    assert slotted[0] < plain[0], f"a slot removes material: {slotted[0]} against {plain[0]} for the undriven screw"


@pytest.mark.parametrize("head", sorted(ScrewHeadType, key=lambda h: h.name), ids=lambda h: h.name)
def test_a_hex_drive_cuts_a_socket_or_is_listed(head: ScrewHeadType) -> None:
    """SPEC G-8: a drive either changes the solid or is a gap someone wrote down."""
    plain = _solid(head, ScrewDriveType.NONE)
    hexed = _solid(head, ScrewDriveType.HEX)
    if head in HEX_DRIVE_NOT_CUT:
        assert hexed == plain, (
            f"Screw(head={head.name}, drive=HEX) now cuts a socket. Remove it from "
            f"HEX_DRIVE_NOT_CUT -- the gap is closed and the list overstates it"
        )
        return
    assert hexed != plain, (
        f"Screw(head={head.name}, drive=HEX) is the same solid as drive=NONE and is not listed in "
        f"HEX_DRIVE_NOT_CUT, so nothing says why"
    )
    assert hexed[0] < plain[0], f"a socket removes material: {hexed[0]} against {plain[0]}"


@pytest.mark.parametrize(
    ("first", "second"),
    sorted(itertools.combinations(sorted(ScrewHeadType, key=lambda h: h.name), 2)),
    ids=lambda h: h.name,
)
def test_two_heads_differ_unless_one_stands_in_for_the_other(first: ScrewHeadType, second: ScrewHeadType) -> None:
    """A head silently building as another is G-8's case, and two pairs do it on purpose."""
    pair = (first, second) if (first, second) in DOCUMENTED_SYNONYMS else (second, first)
    if pair in DOCUMENTED_SYNONYMS:
        assert _solid(first, ScrewDriveType.NONE) == _solid(second, ScrewDriveType.NONE), (
            f"{first.name} and {second.name} are documented as the same shape and no longer are. "
            f"If {pair[1].name} has gained its own geometry, say so on the enum and delete the row"
        )
        return
    assert _solid(first, ScrewDriveType.NONE) != _solid(second, ScrewDriveType.NONE), (
        f"Screw(head={first.name}) and Screw(head={second.name}) build the same solid, and nothing "
        f"says one stands in for the other. Either give it its own shape or add it to "
        f"DOCUMENTED_SYNONYMS with the reason (SPEC G-8)"
    )


def test_the_enum_documents_the_synonyms_it_has() -> None:
    """The reason lives on the enum, where a caller reads it, as well as in this file."""
    doc = ScrewHeadType.__doc__ or ""
    for pair in DOCUMENTED_SYNONYMS:
        for member in pair:
            assert member.name in doc, (
                f"{member.name} stands in for another head and ScrewHeadType's docstring does not "
                f"mention it, so a caller comparing two screws has no way to know"
            )

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""Every cut pattern the enum advertises builds, or refuses as the gap it is (SPEC G-8, E-1).

`PartitionCutType` offers twelve patterns and **eight tile**. The other four -- `square`,
`triangle`, `halfsine`, `semicircle` -- are *section* profiles for a `partition_path` descriptor
and have no tiling form, so they cannot be repeated along a cut.

**That refusal is correct and stays a `Bosl2ValueError`.** I first changed it to a
`Bosl2NotImplementedError` on G-8's rule about advertised members, and that was wrong: a category
difference is not unfinished work, and framing it as a gap promises a feature that is not coming.
`tests/test_partitions.py` already said so -- "these exist as partition_path sections but have no
tiling form; say so rather than guess" -- and breaking that test is what showed me the decision had
already been made deliberately. What was wrong was the *message*: "unsupported cut type ... use a
PartitionCutType member or its name", read by a caller who had passed exactly that.

The real error-contract defect was next to it. `PartitionCutType(cutpath)` raises a **bare
`ValueError`**, so `cutpath="jigwas"` came out of the enum rather than the library and
`except Bosl2Error` missed it entirely (SPEC E-1). And the enum's own docstring offered all twelve
to `partition_mask`, which is how one enum serving two vocabularies hid the distinction.

Two findings here were my own measurement errors, both of the kind this file exists to prevent:

* comparing `(vertex count, volume)` made `comb` and `finger` look identical. They differ by their
  flank angle, 2 degrees against 20, and a symmetric cut removes the same volume at either -- the
  same trap T97 recorded for `MIN_EDGE`/`MIN_AREA`. Compared on vertex positions they differ.
* an earlier probe called `partition_mask` with the wrong keyword, so all twelve raised identically
  and the pairwise check reported **every** pair as collapsed. A probe where everything fails the
  same way reports perfect agreement.
"""

from __future__ import annotations

import numpy as np
import pytest

from pybosl2.enums import PartitionCutType
from pybosl2.exceptions import Bosl2Error
from pybosl2.partitions import SECTION_ONLY_CUT_TYPES, partition_mask

LENGTH, WIDTH, HEIGHT, CUTSIZE = 60.0, 40.0, 20.0, 8.0


def _mask(pattern: PartitionCutType | str) -> object:
    return partition_mask(length=LENGTH, w=WIDTH, height=HEIGHT, cutsize=CUTSIZE, cutpath=pattern)


def _shape(pattern: PartitionCutType) -> tuple[float, ...]:
    """The vertex positions, sorted per axis -- a signature that survives face reordering.

    Deliberately not `(vertex count, volume)`: a symmetric cut removes the same volume whatever
    its flank angle, which made `comb` and `finger` look like the same pattern.
    """
    points = np.asarray([[float(c) for c in p] for p in _mask(pattern).vnf().vertices], dtype=float)  # type: ignore[attr-defined]
    return tuple(np.round(np.sort(points, axis=0).ravel(), 5))


@pytest.mark.parametrize("pattern", list(PartitionCutType), ids=lambda p: p.name)
def test_a_cut_pattern_tiles_or_says_why_it_cannot(pattern: PartitionCutType) -> None:
    """SPEC G-8, E-2: every member either tiles, or refuses naming itself and the alternatives."""
    if pattern in SECTION_ONLY_CUT_TYPES:
        with pytest.raises(Bosl2Error) as caught:
            _mask(pattern)
        message = str(caught.value)
        assert pattern.value in message, "the refusal must name the pattern that was asked for"
        assert "section" in message, "and say it is a section profile, not that it is unsupported"
        assert "jigsaw" in message, "and name a tiling pattern the caller can use instead (E-2)"
        return
    assert _shape(pattern), f"{pattern.name} built an empty mask"


@pytest.mark.parametrize(
    "pattern",
    sorted(set(PartitionCutType) - SECTION_ONLY_CUT_TYPES, key=lambda p: p.name),
    ids=lambda p: p.name,
)
def test_a_built_pattern_differs_from_every_other(pattern: PartitionCutType) -> None:
    """A pattern that fell through to another would pass that other pattern's test."""
    mine = _shape(pattern)
    for other in sorted(set(PartitionCutType) - SECTION_ONLY_CUT_TYPES, key=lambda p: p.name):
        if other is not pattern:
            assert mine != _shape(other), (
                f"{pattern.name} and {other.name} produce the same mask. `comb` and `finger` differ "
                f"only by flank angle, so compare positions -- volume cannot see it"
            )


def test_an_unknown_pattern_refuses_inside_the_library_family() -> None:
    """SPEC E-1, E-2: a misspelling is the library's error, and the message lists the choices."""
    with pytest.raises(Bosl2Error) as caught:
        _mask("jigwas")
    message = str(caught.value)
    assert "jigwas" in message, "the message must quote what arrived"
    assert "jigsaw" in message, "and name the patterns that do exist (SPEC E-2)"


def test_the_enum_documents_the_same_split_the_code_enforces() -> None:
    """The division lives in two places, so they are compared rather than trusted.

    `PartitionCutType` is one enum serving two vocabularies -- tiling patterns for a mask, section
    profiles for a `partition_path` descriptor. Its docstring said neither, and promised all twelve
    to `partition_mask`; that is what let four members look like plain members.
    """
    doc = PartitionCutType.__doc__ or ""
    for pattern in sorted(SECTION_ONLY_CUT_TYPES, key=lambda p: p.name):
        assert pattern.value in doc, (
            f"{pattern.value!r} refuses as a mask cutpath but PartitionCutType's docstring does "
            f"not say so, so a caller reading the enum still expects it to tile"
        )
    for pattern in sorted(set(PartitionCutType) - SECTION_ONLY_CUT_TYPES, key=lambda p: p.name):
        assert pattern.value not in doc, (
            f"{pattern.value!r} tiles, but the docstring lists it among the section-only profiles. "
            f"Giving a pattern a tiling form removes it from both records, in the same commit"
        )

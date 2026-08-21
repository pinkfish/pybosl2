# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""SPEC S-2a: a shape's `size` is its nominal anchor box, not its bounding box.

`anchor=` is measured against the box a shape is *designed* around -- a gear's pitch circle, a
regular polyhedron's circumsphere, the plate a snap fitting mounts on -- so the geometry may sit
inside that box or stand outside it. `bounds()` is the one that reports geometry.

Fifteen parts declare a `size` that differs from their `bounds()`. That is allowed, but it must be
deliberate: this file checks that `bounds()` never quietly answers from the nominal box, and that
every part whose two boxes disagree says at the declaration which box it is naming.
"""

from __future__ import annotations

import inspect
import re

import pytest

import pybosl2.parts as parts
from pybosl2.shapes3d import Bosl2Solid, cuboid

#: Parts whose nominal anchor box is deliberately not their bounding box, and the box it names.
NOMINAL_ANCHOR_BOX: dict[str, str] = {
    "BevelGear": "pitch circle and nominal face width",
    "HexDriveMask": "the hex key's across-flats size",
    "Rack": "nominal tooth height",
    "RegularPolyhedron": "the circumsphere",
    "SnapLock": "the plate the snap mounts on",
    "SnapPin": "the pin envelope a socket is cut for",
    "SnapPinSocket": "the matching pin's envelope plus clearance",
    "SnapSocket": "the plate the snap mounts on",
    "TorxMask": "the Torx size's outer diameter",
    "TrussClip": "the truss cell the clip grips",
    "TrussFoot": "the foot's plate",
    "TrussJoiner": "the joiner's plate",
    "Worm": "pitch diameter",
    "WormGear": "pitch circle",
    "hex_mask": "the hex key's across-flats size",
}


def test_bounds_reports_geometry_not_the_nominal_box() -> None:
    """A wrong `size` must not be able to change what `bounds()` says (SPEC S-2a)."""
    box = cuboid([10, 20, 30])
    lied_to = Bosl2Solid(box.shape, size=[1, 1, 1])

    _centre, size = lied_to.bounds()
    assert size == pytest.approx([10.0, 20.0, 30.0]), "bounds() answered from `size`, not the geometry"
    assert list(lied_to.size or []) == [1, 1, 1]  # ... while the nominal box is kept as given


@pytest.mark.parametrize("name", sorted(NOMINAL_ANCHOR_BOX))
def test_a_differing_nominal_box_is_explained_at_its_declaration(name: str) -> None:
    """SPEC S-2a: say which box you are naming, so the next reader does not 'fix' it."""
    obj = getattr(parts, name)
    source = inspect.getsource(inspect.getmodule(obj))  # type: ignore[arg-type]
    sites = [line for line in source.splitlines() if "Nominal anchor box" in line]
    assert sites, f"{name}'s module never explains its nominal anchor box"


def test_the_list_matches_the_parts_that_actually_differ() -> None:
    """The list is the record of a decision, so it must not drift from the geometry.

    A part that stops differing has either been fixed or had its anchor frame changed; either way
    the entry is stale. A part that starts differing needs the same deliberate answer.
    """
    import tests.test_part_show as part_show

    differ = set()
    for name in sorted(part_show._part_classes()):
        cls = getattr(parts, name)
        part = cls(*part_show.ARGUMENTS.get(name, ()), **part_show.KEYWORDS.get(name, {}))
        shape = part.shape
        declared = getattr(shape, "size", None)
        native_bounds = getattr(shape, "_native_bounds", None)
        if declared is None or native_bounds is None:
            continue  # 2-D shapes and anything without a native box have nothing to compare
        measured = native_bounds()
        if measured is None:
            continue
        if any(
            abs(float(d) - r) > max(0.05, 0.02 * max(abs(float(d)), abs(r)))
            for d, r in zip(declared, measured[1], strict=True)
        ):
            differ.add(name)

    listed = set(NOMINAL_ANCHOR_BOX)
    assert differ == listed, (
        "parts whose nominal anchor box differs from their geometry have changed (SPEC S-2a).\n"
        f"  newly differing: {sorted(differ - listed)}\n"
        f"  no longer differing: {sorted(listed - differ)}"
    )


def test_the_spec_and_plan_state_the_rule() -> None:
    """S-2a is the reason the mismatches above are allowed; it has to be written down."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    spec = (root / "SPEC.md").read_text()
    plan = (root / "PLAN.md").read_text()
    assert re.search(r"\*\*S-2a\*\*.*nominal anchor box", spec, re.S | re.I)
    assert "nominal anchor box" in plan

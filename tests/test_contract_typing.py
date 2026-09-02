# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A protocol member is typed, or it is on a shrinking allowlist (SPEC C-23).

C-20 made the contract cover the whole object: every public operation a shape implements is
declared on `Shape`, `Flat` or `Solid`. It did not say the declarations had to mean anything, and
48 of the 90 landed as `(*args: Any, **kwargs: Any)` -- present by name, checked not at all. A
caller following this project's own typing advice got the method *found* and every argument
accepted, including the wrong ones.

Two things kept them loose, and only one was real:

* **The distribution family** was `Any` because nobody had written the signatures out. All four
  implementations inherit one `Distributable` mixin and agree exactly, so there was nothing to
  bridge. Sixteen members, typed in T33.
* **The attachment family** was `Any` because of the *refusals*. PAR-3 requires a CSG-only feature
  to be declared and refuse on the SDF backend, and those refusals were written
  `(*_args: Any, **_kwargs: Any) -> NoReturn`, which satisfies any call -- so the shared contract
  could only declare `Any` too. The loose stub, not the operation, was the cause. The refusals now
  carry the real signature and still refuse. Seven more, typed in T33.

What is left is the genuine case PLAN T-6c describes: the two backends' concrete signatures differ
in ways a checker cannot reconcile, so the protocol declares the caller's view with `Any`. Those
are listed below and the list only shrinks.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Protocol members still declared with `*args: Any` / `**kwargs: Any`, each because the two
#: backends spell the operation differently (PLAN T-6c). Nothing may be added; typing one means
#: deleting its row.
LOOSE: frozenset[str] = frozenset(
    {
        "Flat.hull",
        "Flat.linear_extrude",
        "Flat.offset",
        "Flat.rotate_extrude",
        "Flat.xflip",
        "Flat.yflip",
        "Shape.distribute_on_path",
        "Shape.minkowski",
        "Shape.rotate",
        "Solid.chain_hull",
        "Solid.chamfer_edges",
        "Solid.corner_profile",
        "Solid.cove_edges",
        "Solid.edge_mask",
        "Solid.edge_profile",
        "Solid.edge_profile_asym",
        "Solid.face_profile",
        "Solid.hull",
        "Solid.minkowski_difference",
        "Solid.offset3d",
        "Solid.oversample",
        "Solid.partition",
        "Solid.repair",
        "Solid.round3d",
        "Solid.round_edges",
        "Solid.to_csg",
        "Solid.to_sdf",
    }
)

PROTOCOLS = {"pybosl2/_backend.py": {"Shape", "Solid"}, "pybosl2/flat.py": {"Flat"}}


def _members() -> dict[str, bool]:
    """Return every protocol member as `Protocol.name`, mapped to whether it is declared loosely.

    Keyed by protocol, not by bare member name: `rotate` is loose on `Shape` and typed on `Flat`,
    and a scan keyed by name alone lets one silently answer for the other -- the same collision
    that made the bare requirement ids ambiguous (SPEC §12.2 item 3).
    """
    found: dict[str, bool] = {}
    for path, classes in PROTOCOLS.items():
        tree = ast.parse((ROOT / path).read_text())
        for node in ast.walk(tree):
            if not (isinstance(node, ast.ClassDef) and node.name in classes):
                continue
            for member in node.body:
                if not isinstance(member, ast.FunctionDef):
                    continue
                args = member.args
                loose = any(
                    arg is not None and isinstance(arg.annotation, ast.Name) and arg.annotation.id == "Any"
                    for arg in (args.vararg, args.kwarg)
                )
                found[f"{node.name}.{member.name}"] = loose
    return found


MEMBERS = _members()


def test_the_protocols_were_found() -> None:
    """A rename that emptied this scan would make every check below vacuous."""
    assert len(MEMBERS) > 60, f"only {len(MEMBERS)} protocol members found; the scan is broken"


@pytest.mark.parametrize("name", sorted(n for n, loose in MEMBERS.items() if loose))
def test_no_new_loosely_typed_member(name: str) -> None:
    """A new `*args: Any` member on a contract is a defect, not an extra (SPEC C-23)."""
    assert name in LOOSE, (
        f"{name!r} is declared on a shape protocol as `*args: Any, **kwargs: Any`, which accepts "
        f"every call including the wrong ones. Write the real signature; if the two backends "
        f"genuinely differ, add it to LOOSE with the reason (PLAN T-6c)."
    )


def test_the_allowlist_only_shrinks() -> None:
    """Typing a member means deleting its row, so the list cannot quietly stay the same size."""
    loose_now = {name for name, loose in MEMBERS.items() if loose}
    stale = sorted(LOOSE - loose_now)
    assert not stale, (
        f"LOOSE lists members that are typed now (or gone): {stale}. Delete those rows -- the "
        f"list is the remaining debt, and a stale row overstates it."
    )


def test_the_typed_share_is_recorded() -> None:
    """One number, so the direction of travel is visible without counting rows.

    It started at 42 of 90. Each figure below is a fact about the current tree, not a target.
    """
    typed = sum(1 for loose in MEMBERS.values() if not loose)
    assert typed == len(MEMBERS) - len(LOOSE), (
        f"{typed} of {len(MEMBERS)} protocol members are typed, but LOOSE has {len(LOOSE)} rows; "
        f"the two disagree, so update LOOSE."
    )

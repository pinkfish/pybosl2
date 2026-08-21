# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The BOSL2 coverage table is evidence, so it has to stay true (SPEC B2-1).

`docs/_covgen.py` maps every upstream ``.scad`` file to the pybosl2 module that ports it. A table
nobody checks drifts into fiction -- `docs/design/sdf-csg-compatibility.md` did exactly that twice
-- so these tests check the claims that *can* be checked mechanically: the modules named exist,
the statuses are real, the notes say something, and the committed page matches the generator.

The upstream file list is pinned rather than fetched, so the docs build never needs the network;
`python3 docs/_covgen.py --refresh` re-checks it against GitHub when BOSL2 moves.
"""

from __future__ import annotations

import importlib
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from docs._covgen import BOSL2_TREE, BOSL2_VERSION, COVERAGE, STATUSES, render

PAGE = pathlib.Path(__file__).resolve().parent.parent / "docs" / "bosl2_coverage.rst"


@pytest.mark.parametrize("scad", sorted(COVERAGE))
def test_every_row_is_complete(scad: str) -> None:
    status, modules, note = COVERAGE[scad]
    assert status in STATUSES, f"{scad}: unknown status {status!r}"
    assert note.strip(), f"{scad}: a row without a note says nothing"
    assert note.rstrip().endswith("."), f"{scad}: notes are sentences"
    if status in ("ported", "partial"):
        assert modules, f"{scad}: claimed {status} but names no pybosl2 module"


@pytest.mark.parametrize("scad", sorted(COVERAGE))
def test_every_named_module_exists(scad: str) -> None:
    """A row naming a module that was renamed away is worse than no row at all."""
    for module in COVERAGE[scad][1]:
        importlib.import_module(f"pybosl2.{module}")


def test_partial_rows_say_what_is_missing() -> None:
    """'partial' is only useful with the gap spelled out, so require a note that names one."""
    for scad, (status, _modules, note) in sorted(COVERAGE.items()):
        if status == "partial":
            assert "not ported" in note or "no equivalent" in note or "absent" in note or "deprecated" in note, (
                f"{scad}: a partial row must say what is missing, got {note!r}"
            )


def test_the_committed_page_matches_the_generator() -> None:
    """The page is generated; a hand-edit (or a forgotten re-run) would publish a stale table."""
    assert PAGE.exists(), "run python3 docs/_covgen.py"
    assert PAGE.read_text() == render(), "docs/bosl2_coverage.rst is stale -- run python3 docs/_covgen.py"


def test_the_pinned_version_is_recorded() -> None:
    assert BOSL2_VERSION.startswith("v"), BOSL2_VERSION
    assert len(BOSL2_TREE) == 40, "pin the full tree sha so the check is unambiguous"


def test_the_table_has_no_silent_gaps() -> None:
    """Anything unported must be visible as a row, not missing from the table entirely."""
    counts = {key: sum(1 for value in COVERAGE.values() if value[0] == key) for key in STATUSES}
    assert sum(counts.values()) == len(COVERAGE)
    assert counts["ported"] > 0

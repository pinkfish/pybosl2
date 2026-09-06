# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""`TASKS.md` and the spec's narrative record the same tasks, or one of them is fiction.

SPEC B2-1, DOC-2. `TASKS.md` opens by calling itself "the contract between this file and the spec"
and closes with a section headed *Keeping this file honest*, naming the two ways it goes stale and
saying to fix them in the same commit as the code.

It then went stale seven tasks running. `TASKS.md` stopped at T57 while the spec narrative reached
T63, and its last entry actively contradicted the code it described -- it said the
`beziers -> shapes3d` layering edge "stays", which T58 had closed. The prose about honesty was
written *by* the process that was not following it, which is the whole problem with prose as a
guard: it is a description of an intention, and nothing reads it back.

The drift also hid a plainer error. The teardrop-inversion task was written up as **T62** in three
source comments and **T63** in the spec -- one task under two numbers, with T62 missing from the
narrative entirely. Nothing could have noticed, because nothing compared the two records.

So this compares them: the same task numbers on both sides, and no gaps in the sequence. It is
deliberately not about content. A test that tried to check whether an entry *describes* its task
would be checking prose against prose; what it can check is that neither record silently drops a
task the other has.
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
TASK = re.compile(r"\bT(\d+)\b")

#: Tasks archived out of `TASKS.md` into `docs/tasks-archive.md`, which the spec still narrates.
#: Archiving is how the file stays readable, so these are absences with a reason -- but the reason
#: has to be that the entry is *somewhere*, not that it was dropped.
ARCHIVED = ROOT / "docs" / "tasks-archive.md"


def _numbers(text: str) -> set[int]:
    return {int(n) for n in TASK.findall(text)}


def _task_log() -> set[int]:
    found = _numbers((ROOT / "TASKS.md").read_text())
    if ARCHIVED.exists():
        found |= _numbers(ARCHIVED.read_text())
    return found


def _narrative() -> set[int]:
    return _numbers((ROOT / "spec" / "spec.md.in").read_text())


def test_the_scan_finds_tasks_in_both_records() -> None:
    """A regex matching nothing would make everything below vacuous."""
    assert len(_task_log()) > 20, "no task numbers found in TASKS.md; the scan is broken"
    assert len(_narrative()) > 20, "no task numbers found in the spec frame; the scan is broken"


def test_every_task_the_spec_narrates_is_in_the_task_log() -> None:
    """SPEC DOC-2: a task the spec describes and the log does not is a task the log has dropped.

    This is the direction that actually failed: seven tasks landed with a spec paragraph each and
    no entry in `TASKS.md`, which is the file a reader is pointed at to find out what was done.
    """
    missing = sorted(_narrative() - _task_log())
    assert not missing, (
        f"the spec narrates {['T%d' % n for n in missing]} and TASKS.md does not. Add the entry in "
        f"the same commit as the code, per TASKS.md's own closing section."
    )


#: Tasks the log records and the spec narrative never names. The narrative's habit of naming the
#: task that made a change started partway through the project, so these are historical rather than
#: dropped -- the spec covers their work in prose that does not cite a number. Measured, not
#: chosen, and it only shrinks: a *new* task landing here means its spec paragraph was skipped.
UNNARRATED_BUDGET = 19


def test_no_task_lands_in_the_log_without_a_spec_paragraph() -> None:
    """SPEC B2-1: the other direction, as a ratchet rather than a rule.

    Strict equality is the wrong assertion here and measuring said so: nineteen tasks predate the
    narrative's habit of citing task numbers, and rewriting the spec's history to satisfy a test
    would be the test dictating the record rather than checking it. What the budget does catch is
    the case that matters -- a task added now whose spec paragraph was skipped.
    """
    missing = sorted(_task_log() - _narrative() - {0})
    assert len(missing) <= UNNARRATED_BUDGET, (
        f"{len(missing)} tasks in TASKS.md are not named in the spec narrative, budget "
        f"{UNNARRATED_BUDGET}: {['T%d' % n for n in missing]}. Add the spec paragraph in the same "
        f"commit, per TASKS.md's own closing section."
    )
    assert len(missing) == UNNARRATED_BUDGET, (
        f"down to {len(missing)} from {UNNARRATED_BUDGET} -- lower UNNARRATED_BUDGET to hold it."
    )


def test_the_task_numbers_have_no_gaps() -> None:
    """SPEC DOC-2: a hole is a task written up under two numbers, or one lost between records.

    This is what would have caught the T62/T63 split at the moment it was made: the spec skipped
    T62 while three source comments used it, and a contiguity check does not need to know which
    record is right to know that something is.
    """
    numbers = sorted(_task_log() | _narrative())
    gaps = [n for n in range(min(numbers), max(numbers) + 1) if n not in set(numbers)]
    assert not gaps, (
        f"no task is numbered {['T%d' % n for n in gaps]}, which usually means one task was "
        f"written up under two numbers. Renumber so the sequence is contiguous."
    )


@pytest.mark.parametrize("document", ["TASKS.md", "SPEC.md", "PLAN.md"])
def test_the_documents_a_reader_is_sent_to_exist(document: str) -> None:
    """SPEC DOC-2: TASKS.md's header links all three, and a broken link is worse than no link."""
    assert (ROOT / document).is_file(), f"{document} is linked from TASKS.md and does not exist"

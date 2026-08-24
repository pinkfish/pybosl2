# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Every docstring example type-checks under ``mypy --strict`` (SPEC DOC-5, Q-6; PLAN D-P5a).

An example is user code -- it is the code a caller copies -- so it is held to exactly what this
project asks of user code. An example the checker rejects is a **signature defect the docs found
first**, and the fix belongs in the signature, never in a ``# type: ignore``.

This is the gate that would have caught the largest share of the T16-T22 wave. ``path_sweep``'s
own documented one-liner::

    swept = helix.path_sweep(profile).polyhedron()

failed ``mypy --strict`` for as long as the signature returned
``VNF | Solid | list[list[list[float]]]`` -- the docs were telling users to write something the
project's own type checker rejected, and nothing measured it.

It type-checks rather than executing, so it needs no CAD runtime and runs in CI.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.validate_examples import _extract_py_examples, _extract_rst_examples

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Names the docs-build preamble injects, which an example may use without importing
#: (docs/_ext/pybosl2_example.py). Declared for the checker so an example reads the way a user
#: would write it rather than carrying boilerplate imports the renderer already supplies.
_PREAMBLE = """\
import math
import os
import sys
import traceback
from typing import Any

import numpy as np
"""


def _examples() -> list[tuple[str, str]]:
    """Every example in the package and the docs, labelled by where it came from."""
    found: list[tuple[str, str]] = []
    for path, line, code in _extract_py_examples():
        found.append((f"{path.relative_to(REPO_ROOT)}:{line}", code))
    for path, line, code in _extract_rst_examples():
        found.append((f"{path.relative_to(REPO_ROOT)}:{line}", code))
    return found


def _require_mypy() -> None:
    """Ensure the checker is available -- and in CI, refuse to skip without it.

    Locally a contributor may not have the dev extras yet, and skipping with a clear reason beats
    a confusing failure. In CI there is no such thing as a gate that skips: SPEC Q-6 says every
    docstring example type-checks, and a skipped check reports exactly the same green tick as a
    passing one. `mypy` is in the `test` extra precisely so every job that installs the suite has
    it, and this makes a regression in that packaging fail loudly rather than quietly stop testing.
    """
    import importlib.util
    import os

    if importlib.util.find_spec("mypy") is not None:
        return
    message = "the docstring-example gate needs mypy, which is part of the `test` extra (`pip install -e '.[test]'`)"
    if os.environ.get("CI"):
        pytest.fail(f"{message} -- and in CI this gate may not be skipped (SPEC Q-6)")
    pytest.skip(message)


@pytest.fixture(scope="module")
def mypy_report(tmp_path_factory: pytest.TempPathFactory) -> dict[str, list[str]]:
    """Type-check every example in one batched mypy run, and index the errors by example.

    One process for the whole corpus: mypy's startup dominates, and a per-example run would make
    the gate too slow to keep in the default suite.
    """
    _require_mypy()

    examples = _examples()
    work = tmp_path_factory.mktemp("examples")
    written: dict[str, str] = {}
    for index, (label, code) in enumerate(examples):
        module = work / f"example_{index:04d}.py"
        module.write_text(_PREAMBLE + "\n" + code + "\n")
        written[module.name] = label

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--strict",
            "--no-error-summary",
            "--no-incremental",
            # an example is a snippet, not a module: these two are noise, not signal
            "--allow-untyped-globals",
            "--disable-error-code=name-defined",
            str(work),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    # A gate that reports success because it never ran is worse than no gate. mypy exits 0 for
    # "no errors", 1 for "errors found", and >=2 for a usage or internal failure -- but it also
    # exits 1 with *empty stdout* when the module could not be loaded at all. Both of those look
    # exactly like "every example is clean" to the parser below, which then reports the whole
    # known-gap list as stale. Distinguish them here, before anything is parsed.
    ran = result.returncode == 0 or (result.returncode == 1 and result.stdout.strip())
    if not ran:
        raise AssertionError(
            "the docstring-example gate did not run, so its result means nothing (SPEC Q-6).\n"
            f"  mypy exited {result.returncode} with no diagnostics.\n"
            f"  stderr: {result.stderr.strip()[:500] or '(empty)'}\n"
            "Install the dev extras (`pip install -e '.[test]'`) so `python -m mypy` is importable "
            "by the interpreter running pytest."
        )

    errors: dict[str, list[str]] = {label: [] for label in written.values()}
    for line in result.stdout.splitlines():
        match = re.match(r"^.*?(example_\d+\.py):(\d+): error: (.+)$", line)
        if not match:
            continue
        filename, _lineno, message = match.groups()
        label = written.get(filename)
        if label is not None:
            errors[label].append(message)
    return errors


def test_there_are_examples_to_check() -> None:
    """A gate that checks nothing passes for the wrong reason."""
    assert len(_examples()) > 200, f"only {len(_examples())} examples found -- did extraction break?"


#: Examples that do not yet type-check, by the module that owns them. **This list only shrinks**
#: -- the same ratchet `tests/test_facets.py` uses for the facet backlog (PLAN R-P5).
#:
#: Every entry is a real signature defect the gate found on the day it landed, and almost all of
#: them are one rule: PLAN T-4, "inputs widen". A callable typed to take the exact object the
#: library hands back rejects the plain list or tuple its own docstring passes it -- `Bezier`
#: taking `ndarray` where the example writes nested lists, `path_extrude` taking `Path2D` where
#: the example writes points. The fix is per-signature and mechanical; it is queued as TASKS T23
#: step 2 rather than bundled into the wave that surfaced it.
#:
#: Counted per module rather than per line so the list survives ordinary editing: a moved example
#: must not silently free a slot.
#:
#: 8 of 314 examples, down from 54 when the gate landed.
KNOWN_UNTYPED_EXAMPLES: dict[str, int] = {
    "pybosl2/beziers.py": 3,
    "pybosl2/partitions.py": 1,
    "pybosl2/sdf/shapes2d.py": 1,
    "pybosl2/vnf.py": 3,
}


def test_no_module_grows_its_untyped_examples(mypy_report: dict[str, list[str]]) -> None:
    """The gate, as a ratchet: no module may gain an example that fails `mypy --strict`.

    A new or edited example has to type-check, and a module already carrying debt has to pay it
    down rather than add to it (SPEC DOC-5, Q-6; PLAN D-P5a, R-P5).
    """
    failing: dict[str, int] = {}
    for label, problems in mypy_report.items():
        if problems:
            module = label.rsplit(":", 1)[0]
            failing[module] = failing.get(module, 0) + 1

    grew = {
        module: (count, KNOWN_UNTYPED_EXAMPLES.get(module, 0))
        for module, count in failing.items()
        if count > KNOWN_UNTYPED_EXAMPLES.get(module, 0)
    }
    assert not grew, (
        "these modules gained a docstring example that does not pass `mypy --strict` "
        f"(module: now vs allowed): {grew}.\n"
        "An example is user code -- fix the signature it exercises, and never add a "
        "`# type: ignore` to an example (PLAN D-P5a)."
    )


def test_the_known_list_is_not_stale(mypy_report: dict[str, list[str]]) -> None:
    """A module that has been fixed comes off the list, so the debt cannot be overstated.

    Without this the ratchet rusts: an entry left behind after its examples were fixed silently
    licenses a future regression.
    """
    failing: dict[str, int] = {}
    for label, problems in mypy_report.items():
        if problems:
            module = label.rsplit(":", 1)[0]
            failing[module] = failing.get(module, 0) + 1

    stale = {
        module: (failing.get(module, 0), allowed)
        for module, allowed in KNOWN_UNTYPED_EXAMPLES.items()
        if failing.get(module, 0) < allowed
    }
    assert not stale, (
        "these modules now have fewer failing examples than the list allows -- lower the count "
        f"(module: actual vs allowed): {stale}"
    )


def test_no_example_suppresses_a_type_error() -> None:
    """`# type: ignore` in an example hides the very defect this gate exists to surface."""
    offenders = [label for label, code in _examples() if "type: ignore" in code]
    assert not offenders, (
        f"examples must not carry `# type: ignore` (PLAN D-P5a) -- if one needs it, the signature is wrong: {offenders}"
    )


def test_the_gate_refuses_to_pass_when_it_did_not_run() -> None:
    """A gate that reports success because it never executed is worse than no gate at all.

    mypy exits 1 both for "found errors" and for "could not load the module", and the second case
    comes with *empty stdout* -- which the parser reads as "every example is clean". The visible
    symptom was the opposite of the cause: every module reported as stale, with no hint that the
    checker had not run. This pins the distinction.
    """
    import subprocess
    import sys

    # the shape of a run that did not happen: exit 1, nothing on stdout, a reason on stderr
    failed_to_run = subprocess.run(
        [sys.executable, "-m", "mypy_definitely_not_installed"], capture_output=True, text=True
    )
    assert failed_to_run.returncode == 1
    assert not failed_to_run.stdout.strip()
    assert failed_to_run.stderr.strip()

    # ...and the shape of a real run that found nothing
    clean = subprocess.run([sys.executable, "-m", "mypy", "--version"], capture_output=True, text=True)
    assert clean.returncode == 0, "mypy must be importable for the gate to mean anything"

    # The fixture's own predicate, stated here so a change to it has to change this too.
    def ran(returncode: int, stdout: str) -> bool:
        return returncode == 0 or (returncode == 1 and bool(stdout.strip()))

    assert not ran(failed_to_run.returncode, failed_to_run.stdout), "a failed launch must not count as a run"
    assert ran(0, ""), "exit 0 with no output is a real run that found nothing"
    assert ran(1, "x.py:1: error: something"), "exit 1 with diagnostics is a real run"
    assert not ran(2, ""), "a usage error is not a run"

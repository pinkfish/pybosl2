# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Every CI job that runs the suite can actually run its gates (SPEC Q-6).

`tests/test_docstring_examples.py` type-checks all 300-odd docstring examples with
`mypy --strict`. If mypy is not installed in the job, that test skips -- and **a skipped gate
reports exactly the same green tick as a passing one**, which is how a check stops checking
without anyone noticing.

Two defences, and this is the second:

* `mypy` is in the `test` extra, so every job that installs the suite has it, and the gate fails
  rather than skips when `CI` is set.
* These tests read the workflows and fail if a job runs pytest without the extra that carries it.

Deliberately parsed with plain text rather than PyYAML: PyYAML is not in the `test` extra, so a
test that needed it would itself skip in exactly the environments this is meant to protect.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"

#: A job runs the suite if its steps invoke pytest, directly or under coverage.
_RUNS_TESTS = re.compile(r"\bpytest\b|coverage run")

#: What must be present in the same workflow for that suite run to be meaningful.
_INSTALLS_TEST_EXTRA = re.compile(r"pip install[^\n]*\.\[test")
_VERIFIES_MYPY = re.compile(r"mypy --version")


def _test_running_workflows() -> list[Path]:
    return sorted(p for p in WORKFLOWS.glob("*.y*ml") if _RUNS_TESTS.search(p.read_text()))


def test_the_workflows_are_where_we_think() -> None:
    """A path typo would make every check below vacuously pass."""
    assert WORKFLOWS.is_dir(), f"{WORKFLOWS} does not exist"
    found = _test_running_workflows()
    assert found, "no workflow appears to run the test suite -- has the layout changed?"


@pytest.mark.parametrize("workflow", _test_running_workflows(), ids=lambda p: p.name)
def test_a_workflow_that_runs_the_suite_installs_the_test_extra(workflow: Path) -> None:
    """`.[test]` is what carries mypy, and mypy is what makes the Q-6 gate run."""
    text = workflow.read_text()
    assert _INSTALLS_TEST_EXTRA.search(text), (
        f"{workflow.name} runs the test suite but never installs `.[test]`, so the "
        f"docstring-example gate (SPEC Q-6) would have no mypy and skip."
    )


@pytest.mark.parametrize("workflow", _test_running_workflows(), ids=lambda p: p.name)
def test_a_workflow_that_runs_the_suite_verifies_the_gate_can_run(workflow: Path) -> None:
    """An explicit `mypy --version` step fails the job early and names the cause.

    Without it the symptom is a *passing* run with one silent skip buried in the output.
    """
    text = workflow.read_text()
    assert _VERIFIES_MYPY.search(text), (
        f"{workflow.name} runs the test suite but does not verify mypy is importable. "
        f"Add a `python -m mypy --version` step after the install, so a packaging regression "
        f"fails the job instead of quietly disabling the Q-6 gate."
    )


def test_mypy_is_declared_in_the_test_extra() -> None:
    """The single place that makes every job -- present and future -- able to run the gate."""
    pyproject = (WORKFLOWS.parent.parent / "pyproject.toml").read_text()
    extra = pyproject.split("test = [", 1)[1].split("]", 1)[0]
    assert "mypy" in extra, (
        "mypy belongs in the `test` extra, not in each workflow: tests/test_docstring_examples.py "
        "runs it, so it is a test dependency (SPEC Q-6)."
    )


def test_the_gate_refuses_to_skip_under_ci() -> None:
    """Locally a missing dev tool skips; in CI it must fail (see `_require_mypy`)."""
    source = (Path(__file__).parent / "test_docstring_examples.py").read_text()
    body = source.split("def _require_mypy", 1)[1].split("\n@", 1)[0]
    assert 'os.environ.get("CI")' in body, "the gate must notice it is running in CI"
    assert "pytest.fail" in body, "in CI a missing checker must fail, not skip"
    assert "pytest.skip" in body, "locally it should still skip with a helpful reason"


# --- the lint gate's own version (T122) ---------------------------------------------------------

#: `rev: vX.Y.Z` on the ruff-pre-commit hook, which is where this repository declares the ruff it
#: lints with.
_PRECOMMIT_RUFF_REV = re.compile(r"ruff-pre-commit\n\s*rev:\s*v([0-9][^\s]*)")

#: `ruff==X.Y.Z` as a workflow installs it.
_WORKFLOW_RUFF_PIN = re.compile(r"ruff==([0-9][^\s\"']*)")


def _precommit_ruff_version() -> str:
    config = (WORKFLOWS.parent.parent / ".pre-commit-config.yaml").read_text()
    found = _PRECOMMIT_RUFF_REV.search(config)
    assert found, ".pre-commit-config.yaml no longer pins a ruff rev the way this test reads it"
    return found.group(1)


@pytest.mark.parametrize("workflow", sorted(WORKFLOWS.glob("*.y*ml")), ids=lambda p: p.name)
def test_a_workflow_installing_ruff_pins_the_declared_version(workflow: Path) -> None:
    """SPEC Q-3: a lint gate whose rule set arrives from the internet is not reproducible.

    `pip install ruff` in a workflow installs whatever released most recently. A rule that grows
    to cover one more case then turns a branch red with no commit behind it, while `ruff check .`
    stays clean on every developer's machine -- which is how an error that nobody could reproduce
    came to be reported against a file that had not changed. SIM102 reaching into `elif` bodies
    did exactly that to `docs/_rstgen.py`.

    So every workflow installs the version `.pre-commit-config.yaml` declares, and this test is
    what keeps the two from drifting. Bumping ruff means bumping the rev and running it once,
    which is the point: new rules arrive when someone is looking.
    """
    text = workflow.read_text()
    if "ruff" not in text:
        pytest.skip(f"{workflow.name} does not install ruff")
    declared = _precommit_ruff_version()
    pinned = _WORKFLOW_RUFF_PIN.findall(text)
    assert pinned, (
        f"{workflow.name} installs ruff without a version. Pin it to =={declared}, the rev "
        f".pre-commit-config.yaml declares, so the gate cannot change without a commit."
    )
    assert set(pinned) == {declared}, (
        f"{workflow.name} installs ruff {sorted(set(pinned))} while .pre-commit-config.yaml "
        f"declares {declared}. One of the two is lying about what this repository lints with."
    )

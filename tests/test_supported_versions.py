# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The supported interpreters are declared in one place and agree everywhere (PLAN L-1).

Three files say which Pythons this project runs on -- `requires-python`, the trove classifiers,
and CI's test matrix -- and nothing made them agree. A version added to the matrix but not the
classifiers is untested-in-name; a version in the classifiers but not the matrix is *claimed and
never run*, which is the one that hurts.

That matters more here than in most projects because the interpreters differ in behaviour this
library depends on: `isinstance` against a runtime-checkable Protocol uses `hasattr` on 3.11 and a
static lookup from 3.12 (PLAN T-6b, T-6e), so a green run on one says little about another.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = (ROOT / "pyproject.toml").read_text()
WORKFLOWS = ROOT / ".github" / "workflows"

#: The versions this project supports, newest last. Changing this list means changing
#: `requires-python`, the classifiers and every CI matrix in the same commit -- which is what the
#: tests below enforce.
SUPPORTED = ("3.11", "3.12", "3.13")


def _classifier_versions() -> set[str]:
    return set(re.findall(r"Programming Language :: Python :: (\d+\.\d+)", PYPROJECT))


def _matrix_versions(workflow: Path) -> set[str]:
    """Every version named in a `python-version:` matrix list in *workflow*."""
    found: set[str] = set()
    for block in re.findall(r"python-version:\s*\[([^\]]*)\]", workflow.read_text()):
        found |= set(re.findall(r"\d+\.\d+", block))
    return found


def test_requires_python_matches_the_floor() -> None:
    match = re.search(r'requires-python\s*=\s*"([^"]+)"', PYPROJECT)
    assert match, "pyproject.toml declares no requires-python"
    assert match.group(1) == f">={SUPPORTED[0]}", (
        f"requires-python is {match.group(1)!r} but the supported floor is {SUPPORTED[0]} (PLAN L-1)"
    )


def test_the_classifiers_list_every_supported_version() -> None:
    missing = sorted(set(SUPPORTED) - _classifier_versions())
    assert not missing, f"supported but not in the trove classifiers: {missing}"


def test_the_classifiers_claim_nothing_untested() -> None:
    """A classifier for a version no CI job runs is a promise nothing keeps."""
    tested: set[str] = set()
    for workflow in WORKFLOWS.glob("*.y*ml"):
        tested |= _matrix_versions(workflow)
    unrun = sorted(v for v in _classifier_versions() - tested)
    assert not unrun, (
        f"the classifiers claim support for {unrun}, which no CI matrix runs. Either test them or "
        f"stop claiming them (PLAN L-1)."
    )


def test_the_test_matrix_covers_every_supported_version() -> None:
    """The pytest job is what proves a version works; the mypy job only proves it type-checks."""
    tests_workflow = WORKFLOWS / "tests.yml"
    assert tests_workflow.exists(), "tests.yml is where the version matrix lives"
    covered = _matrix_versions(tests_workflow)
    missing = sorted(set(SUPPORTED) - covered)
    assert not missing, f"supported but absent from the tests.yml matrix: {missing}"


@pytest.mark.parametrize("version", SUPPORTED)
def test_each_supported_version_is_named_in_the_plan(version: str) -> None:
    """The list here and the one in PLAN L-1 are the same list."""
    plan = (ROOT / "PLAN.md").read_text()
    section = plan.split("## 1. Language baseline", 1)[1].split("## 2.", 1)[0]
    assert version in section, f"PLAN L-1 does not mention {version}"


def test_nothing_uses_a_typing_internal() -> None:
    """Both version bugs this project hit came from reaching into `typing`'s private surface.

    `__protocol_attrs__` does not exist before 3.12; a test built on it passed on a new interpreter
    and errored on the supported floor. There is no supported way to ask a Protocol for its
    members, so the answer is to compute it (see `tests/test_shape_contract.py::_declared`), not to
    borrow an implementation detail.
    """
    import ast

    banned = re.compile(r"__protocol_attrs__|\btyping\._\w+")
    offenders: list[str] = []
    for path in sorted((ROOT / "tests").rglob("*.py")) + sorted((ROOT / "pybosl2").rglob("*.py")):
        if path.name == "test_supported_versions.py":
            continue
        source = path.read_text()
        if not banned.search(source):
            continue
        # Scan the *code*, not the prose: a docstring saying why a name is off-limits is not a use
        # of it, and the comment explaining the ban is the most likely place to mention it.
        tree = ast.parse(source)
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and id(node) in docstrings:
                continue
            name = None
            if isinstance(node, ast.Attribute):
                name = node.attr
            elif isinstance(node, ast.Name):
                name = node.id
            if name and banned.search(name):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not offenders, (
        "these reach into typing's private surface, which differs between supported interpreters "
        f"(PLAN L-1a): {offenders}"
    )

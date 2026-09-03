# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Every public callable documents its arguments (PLAN D-P2, D-P4).

D-P2 asks for a docstring on every public callable and D-P4 for a complete `Args:`; neither has
ever been checked, and **313 public callables with 1307 parameters had no `Args:` section at all**
when it first was. T35 wrote 57 of them -- the ones blocking the ambient-resolution documentation
(SPEC G-4) -- and the rest are a per-file budget that only shrinks.

Two things this deliberately does *not* do:

**Empty since T39.** The 57 that blocked the ambient-resolution documentation went first (T35);
the remaining 256 followed, and the budget below is now the shape of a ratchet rather than a list.

Two things this deliberately does *not* do:

* It does not accept a partial `Args:`. A section listing three of a function's ten parameters
  reads as though the other seven are not parameters, which is worse than saying nothing --
  so the per-parameter check below is separate from the has-a-section check, and only the second
  is ratcheted for now.
* It does not count a docstring's absence as a pass. A callable with no docstring at all is
  D-P2's defect and is listed too.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "pybosl2"

#: Public callables that take parameters and document none of them. **Empty** since T39: every
#: public callable in the package documents its arguments. Kept as the ratchet's shape -- a new
#: undocumented callable has to add itself here, and there is nowhere to add it to.
BUDGET: dict[str, int] = {}


def _undocumented() -> dict[str, list[str]]:
    """Return, per file, the public callables that take parameters and have no `Args:` section."""
    found: dict[str, list[str]] = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE).as_posix()
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            doc = ast.get_docstring(node)
            if not doc:
                continue
            parameters = [a.arg for a in node.args.args + node.args.kwonlyargs if a.arg not in ("self", "cls")]
            if parameters and "Args:" not in doc:
                found.setdefault(relative, []).append(node.name)
    return found


UNDOCUMENTED = _undocumented()


def test_the_scan_found_the_package() -> None:
    """A scan matching nothing would make the budget vacuous."""
    assert any(PACKAGE.rglob("*.py")), "no package modules found"


def test_every_public_callable_documents_its_arguments() -> None:
    """PLAN D-P4, at zero: 313 callables taking 1307 parameters documented none of them in T35.

    The whole package is covered now, so this is a plain assertion rather than a budget. The
    per-file form below stays for the day one comes back.
    """
    undocumented = {path: sorted(names) for path, names in UNDOCUMENTED.items() if path not in BUDGET}
    assert not undocumented, (
        f"public callables with parameters and no `Args:` section (PLAN D-P4): "
        f"{ {k: v[:3] for k, v in undocumented.items()} }"
    )


@pytest.mark.parametrize("path", sorted(set(UNDOCUMENTED) | set(BUDGET)) or ["(none)"])
def test_no_file_exceeds_its_undocumented_budget(path: str) -> None:
    """A new public callable documents its arguments; an old one is written down until it does."""
    actual = len(UNDOCUMENTED.get(path, []))
    budget = BUDGET.get(path, 0)
    if actual > budget:
        names = sorted(UNDOCUMENTED.get(path, []))[:5]
        pytest.fail(
            f"{path} has {actual} public callables with parameters and no `Args:` section, "
            f"budget {budget}. First few: {names}. PLAN D-P4 asks for a complete `Args:`."
        )
    if actual < budget:
        pytest.fail(
            f"{path} is down to {actual} from a budget of {budget}. Lower its entry in BUDGET "
            f"{'or delete the row' if not actual else ''}."
        )


def test_the_budget_has_no_rows_for_files_that_are_gone() -> None:
    """A row for a deleted file makes the debt look larger than it is."""
    missing = sorted(name for name in BUDGET if not (PACKAGE / name).exists())
    assert not missing, f"BUDGET names files that no longer exist: {missing}"


def test_a_documented_section_covers_every_parameter() -> None:
    """Where a callable *has* an `Args:` section, it names every parameter it declares.

    Separate from the budget above, and not ratcheted: a partial section is a different defect
    from a missing one, and this one has always held.
    """
    import re

    incomplete: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE).as_posix()
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            doc = ast.get_docstring(node)
            if not doc or "Args:" not in doc:
                continue
            if f"{relative}::{node.name}" in PARTIAL:
                continue
            body = doc[doc.index("Args:") + 5 :]
            body = re.split(r"\n\s*(?:Returns|Raises|Yields|Examples|Note|Notes|Attributes):", body)[0]
            documented = set(re.findall(r"^\s{4,}(\w+):", body, re.M))
            # A leading underscore marks a parameter kept for signature compatibility and not
            # used, so it has nothing to say about it (`keyhole(_length=...)`).
            declared = {
                a.arg
                for a in node.args.args + node.args.kwonlyargs
                if a.arg not in ("self", "cls") and not a.arg.startswith("_")
            }
            if declared - documented:
                incomplete.append(f"{relative}::{node.name} misses {sorted(declared - documented)}")
    assert not incomplete, "incomplete Args: sections:\n  " + "\n  ".join(incomplete[:20])


#: Callables whose `Args:` is knowingly partial. Empty is the goal; a row here is debt.
PARTIAL: frozenset[str] = frozenset()

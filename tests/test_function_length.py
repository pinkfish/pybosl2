# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Functions stay short, and the backlog only shrinks (PLAN S-2).

PLAN S-2 has asked for functions under 50 lines for as long as the plan has existed, and 243
functions exceeded it -- the longest at 237 lines. A rule with 243 violations and no test does not
describe the project's standard; it teaches contributors that the document is optional.

Retiring the rule was the other option and it is the wrong one: the rule is *right*, the code has
simply never been held to it. So it becomes what every other backlog here is -- a per-file budget
that can only shrink. A file with no entry may not grow a long function at all; a file with one
may not grow another, and every split lowers its number.

Per-file rather than one total, because locality is what makes it actionable: the failure names the
file you are in, not a global counter you have no way to move.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "pybosl2"

#: The longest a function's *code* may be before it counts against its file's budget (PLAN S-2).
#: Docstrings are not counted -- see `_body_length`.
LIMIT = 50

#: How many over-long functions each file still has. Lower a number when you split one; delete the
#: row when it reaches zero. Nothing may be added.
BUDGET: dict[str, int] = {
    "_shape.py": 1,
    "_stroke3d.py": 1,
    "beziers.py": 3,
    "caps.py": 1,
    "distributors.py": 2,
    "miscellaneous.py": 2,
    "partitions.py": 2,
    "parts/ball_bearings.py": 1,
    "parts/cubetruss.py": 4,
    "parts/gears.py": 4,
    "parts/hinges.py": 1,
    "parts/hooks.py": 1,
    "parts/screws.py": 2,
    "parts/sliders.py": 1,
    "parts/tripod_mounts.py": 1,
    "parts/walls.py": 1,
    "path2d.py": 2,
    "path3d.py": 2,
    "regions.py": 2,
    "rounding.py": 2,
    "sdf/joiners.py": 1,
    "sdf/paths.py": 1,
    "sdf/shapes3d.py": 7,
    "sdf/skin.py": 1,
    "shapes2d/circle.py": 1,
    "shapes2d/square.py": 1,
    "shapes3d/base.py": 1,
    "shapes3d/cuboid.py": 3,
    "shapes3d/cylinder.py": 3,
    "shapes3d/extrusions.py": 1,
    # The five cylinder constructors, each 55 lines of which 44 is the forwarding dict -- one
    # line per parameter, which is B-3's duplication and not "this function does too much". They
    # crossed when `texturing=` was added in T37. Collapsing the three group-resolution calls into
    # one took `cube` and `cuboid` from 53 lines to 28, and these are what is left: a signature and
    # a dict listing the same 44 names. Raised deliberately rather than by redefining the metric a
    # third time -- the docstring and the signature already do not count, and a rule that keeps
    # shrinking to fit stops measuring anything. It comes back to 0 with the façade duplication.
    "solid.py": 5,
    "skin.py": 8,
    "surfaces3d.py": 6,
    "svg.py": 2,
    "texture.py": 2,
    "turtle/turtle2d.py": 2,
    "turtle/turtle3d.py": 2,
    "vnf.py": 6,
}


def _body_length(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Return the function's length in *code* lines: no signature, no docstring.

    S-2 is about a function doing too much -- "split it rather than commenting it into sections" --
    so what it should measure is the code. The other two parts of a `def` are declaration, and
    counting them puts S-2 in direct conflict with rules this project also holds:

    * **Docstrings.** DOC-2 asks for `Args:`, `Returns:`, `Raises:` and a rendering example on
      every public callable, so counting docstring lines makes S-2 penalise documentation. The
      ambient-default sweep pushed a function over its budget without touching a line of its code,
      which is what first surfaced this.
    * **Signatures.** A façade constructor declares up to forty parameters, one per line, because
      B-3 makes the façade own every shared default. `prismoid` crossed the limit on a signature
      of thirty-odd lines around a body of twenty; splitting the *body* could not have helped,
      because the body was never the problem. That duplication is real and it is B-3's, tracked as
      T31 -- but it is not "this function does too much", and one rule should not report another
      rule's debt.

    Measured together the backlog was 243 functions; docstrings alone accounted for 112 of them
    and signatures for another 63.
    """
    body = node.body
    first = body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and len(body) > 1:
        first = body[1]
    return (node.end_lineno or node.lineno) - first.lineno + 1


def _over_long() -> dict[str, list[tuple[str, int]]]:
    """Return, per file, the functions longer than the limit and how long they are."""
    found: dict[str, list[tuple[str, int]]] = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE).as_posix()
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                length = _body_length(node)
                if length > LIMIT:
                    found.setdefault(relative, []).append((node.name, length))
    return found


OVER_LONG = _over_long()


def test_the_scan_found_something() -> None:
    """A scan that matched nothing would make every check below vacuous."""
    assert OVER_LONG, "no over-long functions found at all; the scan is broken"


@pytest.mark.parametrize("path", sorted(set(OVER_LONG) | set(BUDGET)))
def test_no_file_exceeds_its_budget(path: str) -> None:
    """A file may not grow a new over-long function, and a split lowers its number."""
    functions = OVER_LONG.get(path, [])
    budget = BUDGET.get(path, 0)
    if len(functions) > budget:
        worst = sorted(functions, key=lambda f: -f[1])[:3]
        listed = ", ".join(f"{name} ({length} lines)" for name, length in worst)
        pytest.fail(
            f"{path} has {len(functions)} functions over {LIMIT} lines, budget {budget}. "
            f"Longest: {listed}. PLAN S-2: split it rather than commenting it into sections."
        )
    if len(functions) < budget:
        pytest.fail(
            f"{path} is down to {len(functions)} over-long functions from a budget of {budget}. "
            f"Lower its entry in BUDGET to {len(functions)} "
            f"({'or delete the row' if not functions else 'to hold the gain'})."
        )


def test_the_budget_has_no_rows_for_files_that_are_gone() -> None:
    """A row for a deleted file makes the debt look larger than it is."""
    missing = sorted(name for name in BUDGET if not (PACKAGE / name).exists())
    assert not missing, f"BUDGET names files that no longer exist: {missing}"


def test_the_total_is_recorded() -> None:
    """One number for the whole backlog, so its direction is visible at a glance."""
    total = sum(len(v) for v in OVER_LONG.values())
    assert total == sum(BUDGET.values()), (
        f"{total} over-long functions in the package against a budget total of "
        f"{sum(BUDGET.values())}; update BUDGET so the two agree."
    )

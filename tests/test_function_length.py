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

#: The longest a function may be before it counts against its file's budget (PLAN S-2).
LIMIT = 50

#: How many over-long functions each file still has. Lower a number when you split one; delete the
#: row when it reaches zero. Nothing may be added.
BUDGET: dict[str, int] = {
    "_backend.py": 2,
    "_helpers.py": 2,
    "_shape.py": 1,
    "_stroke2d.py": 1,
    "_stroke3d.py": 2,
    "beziers.py": 5,
    "caps.py": 1,
    "color.py": 1,
    "distributors.py": 3,
    "flat.py": 7,
    "geometry.py": 1,
    "isosurface.py": 4,
    "masking.py": 7,
    "miscellaneous.py": 3,
    "nurbs.py": 4,
    "partitions.py": 5,
    "parts/ball_bearings.py": 1,
    "parts/cubetruss.py": 4,
    "parts/gears.py": 11,
    "parts/hinges.py": 3,
    "parts/hooks.py": 1,
    "parts/joiners.py": 1,
    "parts/linear_bearings.py": 2,
    "parts/modular_hose.py": 1,
    "parts/screw_drive.py": 1,
    "parts/screws.py": 2,
    "parts/sliders.py": 1,
    "parts/tripod_mounts.py": 1,
    "parts/walls.py": 1,
    "path2d.py": 9,
    "path3d.py": 6,
    "regions.py": 3,
    "rounding.py": 4,
    "sdf/joiners.py": 2,
    "sdf/paths.py": 2,
    "sdf/shapes2d.py": 6,
    "sdf/shapes3d.py": 19,
    "sdf/skin.py": 2,
    "shapes2d/base.py": 2,
    "shapes2d/circle.py": 5,
    "shapes2d/curves.py": 5,
    "shapes2d/ops.py": 2,
    "shapes2d/square.py": 5,
    "shapes3d/base.py": 8,
    "shapes3d/cuboid.py": 7,
    "shapes3d/cylinder.py": 8,
    "shapes3d/extrusions.py": 3,
    "shapes3d/sphere.py": 2,
    "shapes3d/torus.py": 2,
    "skin.py": 14,
    "solid.py": 17,
    "surfaces3d.py": 9,
    "svg.py": 5,
    "texture.py": 2,
    "turtle/turtle2d.py": 3,
    "turtle/turtle3d.py": 2,
    "vnf.py": 10,
}


def _over_long() -> dict[str, list[tuple[str, int]]]:
    """Return, per file, the functions longer than the limit and how long they are."""
    found: dict[str, list[tuple[str, int]]] = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE).as_posix()
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                length = (node.end_lineno or node.lineno) - node.lineno
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

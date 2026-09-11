# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A call that type-checks on one backend type-checks on the other.

SPEC PAR-1, C-10; PLAN O-6b. Option parity reached zero in T63 -- every option one backend takes,
the other takes too. That was measured by *calling*, and calling is not the whole contract: a
signature is also a promise to the type checker, and the two backends can agree at runtime while
disagreeing about what they accept.

They did. Twenty-four SDF constructors declared `anchor: Sequence[float]` -- a plain vector, which
PLAN O-6b names explicitly as the thing an anchor must not be -- and the annotation was **false**.
Those functions accept an `Anchor` and always have; `sdf.cuboid([20,20,20], anchor=Anchor.TOP)`
builds exactly what the vector spelling builds. So the defect was invisible to every runtime test
in this repository and reached the user as::

    error: Argument "anchor" to "cuboid" has incompatible type "Anchor";
           expected "Sequence[float]"  [arg-type]

on code that runs. `orient` in the very same signatures was already `Anchor | Sequence[float]`,
which is what makes this an oversight rather than a decision.

This runs `mypy --strict` over calls written the way the documentation writes them, against both
spellings, so a divergence in the *type* surface fails the way a divergence in the option surface
already does. It is the same instrument `tests/test_docstring_examples.py` uses on the examples --
type-checking user code rather than reading the signature -- pointed at the backend pair.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Calls written as a user writes them, in both spellings. Each must type-check on both sides;
#: what is being compared is the *pair*, so a row that is wrong in the same way twice still fails
#: the moment either one is corrected.
PAIRS = [
    ("cuboid anchor", "cuboid([20, 20, 20], anchor=Anchor.TOP)"),
    ("cuboid orient", "cuboid([20, 20, 20], orient=Anchor.RIGHT)"),
    ("sphere anchor", "sphere(radius=10, anchor=Anchor.BOTTOM)"),
    ("cyl anchor", "cyl(length=20, radius=5, anchor=Anchor.TOP)"),
    ("tube anchor", "tube(height=20, outer_radius=10, inner_radius=5, anchor=Anchor.BOTTOM)"),
    ("prismoid anchor", "prismoid([20, 20], [10, 10], height=10, anchor=Anchor.TOP)"),
    ("torus anchor", "torus(major_radius=20, minor_radius=5, anchor=Anchor.TOP)"),
    # Both directions. `cuboid` typed `anchor: Anchor` and `orient: Anchor` on the CSG side --
    # rejecting the *vector* the SDF side accepts, the mirror image of the defect above, and alone
    # among every sibling in its own file. The vector builds at runtime on both.
    ("vector anchor still works", "cuboid([20, 20, 20], anchor=[0, 0, 1])"),
    ("vector orient still works", "cuboid([20, 20, 20], orient=[1, 0, 0])"),
]


def _typecheck(source: str) -> str:
    """Run `mypy --strict` over *source* and return its output, empty when clean."""
    scratch = REPO_ROOT / ".mypy_parity_check.py"
    scratch.write_text(source)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--strict", str(scratch)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
    finally:
        scratch.unlink(missing_ok=True)
    return "" if result.returncode == 0 else result.stdout + result.stderr


@pytest.mark.parametrize(("label", "call"), PAIRS, ids=[label for label, _ in PAIRS])
def test_the_same_call_type_checks_on_both_backends(label: str, call: str) -> None:
    """SPEC PAR-1: parity is a promise to the type checker too, not only to the interpreter."""
    source = textwrap.dedent(f"""
        from pybosl2._edges_lang import Anchor
        import pybosl2.sdf.shapes3d as sdf
        import pybosl2.shapes3d as csg

        sdf.{call}
        csg.{call}
    """)
    complaint = _typecheck(source)
    assert not complaint, f"{label}: the two backends disagree about what they accept\n{complaint}"


def test_the_checker_is_actually_running() -> None:
    """SPEC PAR-1: a harness that always reports clean would pass every row above in silence."""
    assert _typecheck("x: int = 'not an int'\n"), "mypy reported nothing for a certain error"
    assert not _typecheck("x: int = 1\n"), "mypy reported something for correct code"

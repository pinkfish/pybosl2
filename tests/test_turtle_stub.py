# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The fluent turtle methods and their stub stay in step (PLAN T-8).

`_fluent.py` binds one method per turtle command with `setattr`, from a single table, so the two
turtles cannot drift from the command language (PLAN O-1b). That is invisible to a type checker,
which made all 30 of them -- the entire fluent API -- unusable from typed code until `_fluent.pyi`
declared them. This is the parity test that keeps the two honest, the twin of
`tests/test_init_stub.py`.
"""

from __future__ import annotations

import ast
from pathlib import Path

STUB = Path(__file__).resolve().parent.parent / "pybosl2" / "turtle" / "_fluent.pyi"

#: Declared on the concrete turtles with a real signature, so the stub deliberately leaves it out.
_OVERRIDDEN = frozenset({"run"})


def _declared_in_stub() -> set[str]:
    tree = ast.parse(STUB.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "TurtleCommands":
            return {m.name for m in node.body if isinstance(m, ast.FunctionDef)}
    raise AssertionError("TurtleCommands is missing from the stub entirely")


def _generated_at_runtime() -> set[str]:
    from pybosl2.turtle._fluent import TurtleCommands

    return {name for name in vars(TurtleCommands) if not name.startswith("_")}


def test_the_stub_exists() -> None:
    assert STUB.exists(), f"{STUB.name} is what makes the generated methods visible (PLAN T-8)"


def test_every_generated_method_is_declared() -> None:
    """A command added to the table without a stub entry is invisible to every caller's checker."""
    missing = sorted(_generated_at_runtime() - _declared_in_stub() - _OVERRIDDEN)
    assert not missing, f"generated but not declared in _fluent.pyi: {missing}"


def test_the_stub_declares_nothing_that_is_not_generated() -> None:
    """A stale entry is worse than a missing one: it type-checks a call that fails at runtime."""
    extra = sorted(_declared_in_stub() - _generated_at_runtime())
    assert not extra, f"declared in _fluent.pyi but not generated: {extra}"


def test_the_fluent_methods_still_build_a_path() -> None:
    """The stub must not have been written against an API that stopped working."""
    from pybosl2.turtle import Turtle2D

    turtle = Turtle2D().set_length(40).set_arc_steps(24)
    for _ in range(4):
        turtle.move().arc_left(radius=8)
    points = turtle.points()
    assert len(points) > 50, f"the fluent chain produced only {len(points)} points"

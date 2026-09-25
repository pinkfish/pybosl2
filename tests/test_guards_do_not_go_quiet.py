# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A ratchet that reaches zero must assert that, not stop running.

SPEC B2-1. The ratchets in this suite are parametrized over the files or shapes that carry debt,
which is what makes a failure name the thing to fix. It has a failure mode at the far end: when the
debt reaches zero the parameter set is empty, pytest reports::

    SKIPPED [1] tests/test_option_parity.py:138: got empty parameter set for (shape)

and the guard stops running. That is the *success* case and the *broken scan* case reporting
identically — a scan that returned `{}` because its walk stopped reaching the package would read
exactly the same, and reads as a skip in a suite that has five of them.

Two guards were already in that state when this was written: option parity, at zero since T63, and
the domain-named `Any` measure, at zero since T73. Both had been silently skipped for every run in
between. T75 had found and fixed the same hole in the positional-tier rule without recognising it
as a class.

The fix is two parts and needs both. `or ["(none)"]` keeps the parametrization non-empty so the
guard keeps running; and a **direct assertion** states the rule over the whole measurement, which
is the part a fallback cannot do — a placeholder parameter proves the test ran, not that anything
holds.
"""

from __future__ import annotations

import importlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"

if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))


def _parametrized_with_nothing() -> list[str]:
    """Every parametrized test whose argument list collects zero cases.

    The symptom, measured, rather than a pattern that might produce it. A first version matched the
    *source* of each `parametrize` and tried to tell a ratchet from a data table by looking for a
    set operation or a filter -- which flagged eight parametrizations over ordinary data tables,
    then seven after tuning, then a different seven. That is a heuristic being fitted to the cases
    it happens to flag, which T74 named as how an exemption list turns into a dumping ground. The
    argument list either collects something or it does not, and that is answerable by reading it.
    """
    import conftest  # noqa: F401 - installs the libfive mock, as a real run does

    empty = []
    for path in sorted(TESTS.glob("test_*.py")):
        try:
            module = importlib.import_module(path.stem)
        except Exception:  # pragma: no cover - an unimportable test is another test's problem
            continue
        for name, obj in vars(module).items():
            for mark in getattr(obj, "pytestmark", []):
                if mark.name != "parametrize":
                    continue
                values = mark.args[1] if len(mark.args) > 1 else []
                if not list(values):
                    empty.append(f"{path.name}::{name}")
    return empty


def test_the_scan_reads_real_parametrizations() -> None:
    """A walk that imported nothing would make the check below vacuous."""
    seen = 0
    for path in sorted(TESTS.glob("test_*.py")):
        try:
            module = importlib.import_module(path.stem)
        except Exception:  # pragma: no cover
            continue
        seen += sum(
            1 for obj in vars(module).values() for mark in getattr(obj, "pytestmark", []) if mark.name == "parametrize"
        )
    assert seen > 40, f"only {seen} parametrizations found; the scan is broken"


def test_no_ratchet_goes_quiet_when_it_reaches_zero() -> None:
    """SPEC B2-1: a guard that stops running on success cannot be told from one that broke.

    Two were in that state when this was written -- option parity, at zero since T63, and the
    domain-named `Any` measure, at zero since T73 -- and both had been silently skipped for every
    run in between. T75 had fixed the same hole in the positional-tier rule without recognising it
    as a class.
    """
    empty = _parametrized_with_nothing()
    assert not empty, (
        'these parametrize over nothing, so they neither run nor fail -- add an `or ["(none)"]` '
        "fallback and state the rule directly:\n  " + "\n  ".join(empty)
    )


def test_the_two_guards_that_were_silent_now_assert_their_rule() -> None:
    """SPEC B2-1: the fallback keeps them running; only an assertion says the rule holds.

    Named rather than counted, because the point is not that two files changed -- it is that a
    ratchet at zero should read as "measured, and it is zero", which a placeholder parameter does
    not say.
    """
    parity = (TESTS / "test_option_parity.py").read_text()
    signatures = (TESTS / "test_signatures.py").read_text()
    assert "def test_no_shape_has_an_option_gap_at_all" in parity
    assert "def test_no_parameter_named_for_a_type_is_typed_any" in signatures


# --- shared vocabulary (T86) ---------------------------------------------------------------------


def test_no_rule_keeps_its_own_copy_of_a_shared_concept() -> None:
    """SPEC B2-1: two rules measuring one concept must not disagree about what it is.

    T85 found exactly that inside one file: the variadic rule counted `object` as untyped and the
    domain-named rule did not, twenty lines apart, so the second reported **zero** while four
    `profile: object` parameters stood on the exported surface. Widening one constant fixed the
    symptom and left two constants meaning the same thing -- the same defect one step along.

    Measuring the suite for it turned up more: *three* lists of "parameter names that mean a path",
    of twenty, eight and seven names. The widest knew `vertices`, `control_points` and `contour`;
    the narrowest, used by the C-20 rule, knew none of them. Nothing was missed by luck rather than
    design -- merging them immediately surfaced `inward_probe(poly: Any)`, which the narrow list
    could not see.

    So the check is structural: a test module may not define a set that shadows one the shared
    vocabulary already names. Sharing is the fix, and a local redefinition is how it comes undone.
    """
    import ast

    from tests import signature_vocabulary

    shared = {
        name: value
        for name, value in vars(signature_vocabulary).items()
        if not name.startswith("_") and isinstance(value, (frozenset, set, dict))
    }
    assert shared, "the shared vocabulary defines nothing; this check is vacuous"

    redefined = []
    for path in sorted(TESTS.glob("test_*.py")):
        tree = ast.parse(path.read_text())
        for node in tree.body:
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
            for target in targets:
                if target.lstrip("_") in shared and not isinstance(node.value, ast.Name):
                    redefined.append(f"{path.name}::{target}")
    assert not redefined, (
        "these shadow a name the shared vocabulary defines, with their own value -- import it "
        "instead, or the two definitions drift (SPEC B2-1):\n  " + "\n  ".join(redefined)
    )

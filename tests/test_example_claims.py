# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""An example that claims a value is checked by producing it (SPEC DOC-2, B2-1).

`tests/test_docstring_examples.py` proves every example *compiles* under `mypy --strict`. That
catches a signature defect and nothing else: an example can type-check perfectly and still tell the
reader the wrong number.

    print(bracket.bounds().size)     # (60.0, 40.0, 18.0)

That line was in the getting-started page and was false -- the bracket measures ``(60, 40, 12)``,
because `attach()` records a child rather than merging it. It was written from intuition rather
than from running the API, which is the failure SPEC B2-1 names: a claim that nothing measures is a
wish. Rendering does not catch it either, since the docs build renders the *geometry* and never
compares the printed text.

So: an example that puts a number in a trailing comment is asserting it, and this executes the
example and holds it to that. Examples without such a comment are untouched -- the point is to
check claims, not to run every example.
"""

from __future__ import annotations

import contextlib
import io
import re
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

#: `print(...)  # <value>` -- a printed expression with a claimed result. The trailing `-- prose`
#: is allowed and ignored, so a claim can be explained without escaping the check.
_CLAIM = re.compile(r"^(?P<indent>\s*)print\((?P<expr>.+)\)\s*#\s*(?P<claim>\(?-?[\d][\d.,\s-]*\)?)(?:\s*--.*)?$")


#: A `print(...)` with no claim beside it. Such a line still *evaluates* -- so a side effect or an
#: error in it is not lost -- but is rewritten to produce no output, which is what lets each claim
#: pair with its own printed line by position. Pairing across every print was wrong: one unclaimed
#: line in the middle shifted every claim after it onto the wrong value.
_PLAIN_PRINT = re.compile(r"^(?P<indent>\s*)print\((?P<expr>.+)\)\s*(?:#.*)?$")


def _claim_bearing_examples() -> list[tuple[str, str]]:
    """Every example with at least one claimed value, as (label, source)."""
    from tests.validate_examples import _extract_py_examples, _extract_rst_examples

    found: list[tuple[str, str]] = []
    for extract in (_extract_py_examples, _extract_rst_examples):
        for path, line, code in extract():
            if any(_CLAIM.match(ln) for ln in code.splitlines()):
                found.append((f"{path.relative_to(ROOT)}:{line}", code))
    return found


CLAIM_EXAMPLES = _claim_bearing_examples()


def test_there_are_claims_to_check() -> None:
    """A gate that checks nothing passes for the wrong reason."""
    assert CLAIM_EXAMPLES, "no example claims a value -- has the extraction or the pattern broken?"


@pytest.mark.parametrize(("label", "source"), CLAIM_EXAMPLES, ids=[label for label, _ in CLAIM_EXAMPLES])
def test_the_example_produces_what_it_claims(label: str, source: str) -> None:
    """Run the example and compare each printed line with the value beside it."""
    claims: list[str] = []
    lines: list[str] = []
    for raw in source.splitlines():
        match = _CLAIM.match(raw)
        if match:
            claims.append(match.group("claim").strip())
            lines.append(f"{match.group('indent')}print({match.group('expr')})")
            continue
        plain = _PLAIN_PRINT.match(raw)
        if plain:
            lines.append(f"{plain.group('indent')}{plain.group('expr')}")
            continue
        lines.append(raw)

    namespace: dict[str, Any] = {"__name__": "__example__"}
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):
            exec(compile("\n".join(lines), f"<{label}>", "exec"), namespace)
    except Exception as exc:
        pytest.fail(f"the example at {label} claims a value but does not run: {type(exc).__name__}: {exc}")

    printed = [ln for ln in captured.getvalue().splitlines() if ln.strip()]
    assert len(printed) >= len(claims), f"{label}: {len(claims)} value(s) claimed but only {len(printed)} printed"

    def _numbers(text: str) -> list[float]:
        return [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", text)]

    for claimed, actual in zip(claims, printed, strict=False):
        want, got = _numbers(claimed), _numbers(actual)
        assert len(want) == len(got), f"{label}: claimed {claimed!r} but printed {actual!r}"
        assert got == pytest.approx(want, abs=0.05), (
            f"{label} claims {claimed!r} and prints {actual!r}. Fix whichever is wrong -- but run "
            f"the example before deciding, because that is how the wrong one got written."
        )

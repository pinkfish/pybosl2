# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""A docstring that states a default states the one in the signature (SPEC B2-1, DOC-2).

`text3d` declared `language: str = "em"` while its docstring said `(default "en")`, and the two
2-D spellings -- `shapes2d.ops.text` and `flat.text` -- both use `"en"`. A one-character slip in a
default, contradicting its own documentation and its own siblings.

It is harmless *today*: the geometry is byte-identical either way, because the text engine ignores a
language code it does not know. That is what let it sit there. If the engine ever honours the field,
3-D text would shape differently from 2-D text for no documented reason, and the docstring would
still say `"en"`.

**The scan took three attempts to become worth trusting**, which is most of what this file records:

1. Matching `default` loosely anywhere in a parameter's description flagged **739 of 979** -- it was
   reading the "s" out of "use_defaults" in the sentence "the ambient ``use_defaults(fn=...)`` value
   applies".
2. Restricting to the explicit parenthesised form `(default X)` flagged **188 of 439** -- almost all
   of them the *correct* pattern, where the signature default is `None` and the docstring says what
   `None` resolves to: "``height=None`` (default 1)", "``depth=None`` (default half the width)".
   That is exactly what P-3 asks a derivable parameter to do, so it must not be flagged.
3. Restricting further to a **concrete literal** default compared against a **literal** claim gives
   249 checks and 3 hits, of which two are prose -- `cube(chamfer=0)` documented as "(default none)",
   and 0 *is* no chamfer.

So the rule this file enforces is narrow on purpose: where a signature commits to a literal and the
docstring names a literal, they must agree. `None` defaults are the business of P-3's own guards.
"""

from __future__ import annotations

import ast
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent / "pybosl2"

#: The explicit claim form: `(default X)`, `(defaults to X)`, `(default: X)`.
CLAIM = re.compile(r"\(default(?:s)?(?:\s+to)?\s*:?\s*([^)]{1,24})\)")

#: A bare token, so prose like "(default half the width)" is read as a description rather than a
#: claim about a literal.
LITERAL = re.compile(r"^[A-Za-z0-9_.\-]+$")

#: Words that describe the absence of a thing rather than naming a value. `chamfer=0` documented as
#: "(default none)" is a correct description, not a disagreement.
PROSE = frozenset({"none", "no", "off", "nothing", "zero", "unset"})

_SPELLINGS = {"none": "None", "true": "True", "false": "False"}


def _claims() -> list[tuple[str, str, str, str, str]]:
    """Every `(file:line, function, parameter, signature default, documented default)`."""
    found: list[tuple[str, str, str, str, str]] = []
    for path in sorted(ROOT.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue
            doc = ast.get_docstring(node) or ""
            if not doc:
                continue
            arguments = node.args
            named = arguments.args + arguments.kwonlyargs
            supplied = (
                [None] * (len(arguments.args) - len(arguments.defaults))
                + list(arguments.defaults)
                + list(arguments.kw_defaults)
            )
            for argument, default in zip(named, supplied, strict=False):
                # `None` means "derive this", and the docstring then legitimately describes what it
                # derives to. Only a concrete literal is a commitment the prose can contradict.
                if default is None or not isinstance(default, ast.Constant):
                    continue
                if default.value is None:
                    continue
                described = re.search(rf"^\s*{re.escape(argument.arg)}:\s*(.+?)(?=\n\s*\w+:\s|\Z)", doc, re.M | re.S)
                if not described:
                    continue
                claim = CLAIM.search(described.group(1))
                if not claim:
                    continue
                said = claim.group(1).strip().strip("`\"'").rstrip(".")
                if not LITERAL.match(said) or said.lower() in PROSE:
                    continue
                found.append(
                    (
                        f"{path.relative_to(ROOT)}:{node.lineno}",
                        node.name,
                        argument.arg,
                        str(default.value),
                        said,
                    )
                )
    return found


CLAIMS = _claims()


def test_the_scan_finds_claims_to_check() -> None:
    """A scan that matched nothing would make the check below vacuous."""
    assert len(CLAIMS) > 100, (
        f"only {len(CLAIMS)} documented literal defaults found; the claim pattern has stopped "
        f"matching the docstring style"
    )


def test_every_documented_literal_default_is_the_real_one() -> None:
    """SPEC DOC-2: the docstring and the signature are two records of one fact."""
    disagreements = []
    for where, function, parameter, actual, documented in CLAIMS:
        claimed = _SPELLINGS.get(documented.lower(), documented)
        if claimed == actual:
            continue
        try:
            if float(claimed) == float(actual):
                continue
        except (TypeError, ValueError):
            pass
        disagreements.append(f"{where}: {function}({parameter}=) is {actual!r} but the docstring says {documented!r}")
    assert not disagreements, "these docstrings state a default the signature does not have:\n  " + "\n  ".join(
        disagreements
    )


def test_the_text_constructors_agree_on_their_language_default() -> None:
    """The defect in the form that made it visible: one of three siblings differed by a letter.

    Compared across the spellings rather than against `"en"`, so the test says *agree* rather than
    pinning a particular language -- changing the default deliberately should take one edit, not
    four.
    """
    import inspect

    from pybosl2.flat import text as flat_text
    from pybosl2.shapes2d.ops import text as text2d
    from pybosl2.shapes3d.extrusions import text3d

    defaults = {
        name: inspect.signature(fn).parameters["language"].default
        for name, fn in (("flat.text", flat_text), ("text2d", text2d), ("text3d", text3d))
    }
    assert len(set(defaults.values())) == 1, f"the text constructors disagree on their language default: {defaults}"

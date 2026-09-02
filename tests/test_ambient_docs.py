# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Every facet parameter says where its default comes from (SPEC G-4, R-4).

`use_defaults(fn=64)` is how a caller sets curve resolution: once for a block, rather than
threading four numbers through every call. That only helps someone who knows it exists, and a
reader meets `fn` at a signature long before they find `pybosl2.defaults` — so the parameter's own
documentation is where the ambient mechanism has to be named.

It was named in 38 of 209 places when this was first measured. The façade had it everywhere
(T0e did that); nothing else did.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "pybosl2"

FACET_PARAMETERS = ("fn", "fa", "fs", "res")

#: `defaults.py` defines the ambient values, so pointing its own parameters at them is circular.
EXEMPT_FILES = {"defaults.py"}

#: Facet parameters still undocumented, and every one of them for the same reason: its callable
#: has **no `Args:` section at all**, which is a PLAN D-P4 defect in its own right and a bigger
#: job than this rule. Adding a partial `Args:` listing only the facet parameters would be worse
#: than nothing -- it reads as though the others are not parameters. So they are a backlog, and it
#: only shrinks: writing the `Args:` section removes its rows. 57 callables, recorded in
#: SPEC §12.2.
#: Facet parameters still undocumented. **Empty**: T35 wrote the missing `Args:` sections, and
#: the ambient clause landed with them. It stays here as a ratchet -- a new callable that takes a
#: facet control without saying where its default comes from has to add itself, and the test that
#: reads this list fails until it does.
KNOWN_GAPS: frozenset[str] = frozenset()


def _documented_facets() -> list[tuple[str, str, str, bool]]:
    """Return (file, callable, parameter, documented) for every public facet parameter."""
    out: list[tuple[str, str, str, bool]] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.name in EXEMPT_FILES:
            continue
        relative = path.relative_to(PACKAGE).as_posix()
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            doc = ast.get_docstring(node)
            if not doc:
                continue
            names = {a.arg for a in node.args.args + node.args.kwonlyargs}
            for parameter in FACET_PARAMETERS:
                if parameter not in names:
                    continue
                entry = f"{relative}::{node.name}::{parameter}"
                if entry in KNOWN_GAPS:
                    continue
                out.append((relative, node.name, parameter, "use_defaults" in doc))
    return out


FACETS = _documented_facets()


def test_the_scan_found_the_parameters() -> None:
    """A scan that matched nothing would make the check below vacuous."""
    assert len(FACETS) > 100, f"only {len(FACETS)} facet parameters found; the scan is broken"


@pytest.mark.parametrize(
    ("path", "callable_name", "parameter"),
    [(f, c, p) for f, c, p, _ in FACETS],
    ids=lambda v: str(v),
)
def test_every_facet_parameter_documents_the_ambient_default(path: str, callable_name: str, parameter: str) -> None:
    """SPEC G-4: the parameter is where a reader meets `use_defaults`."""
    documented = {(f, c, p): ok for f, c, p, ok in FACETS}
    assert documented[(path, callable_name, parameter)], (
        f"{path}::{callable_name} takes {parameter!r} without saying that omitting it inherits "
        f"the ambient default. Add the clause: "
        f'"Omitted, the ambient ``use_defaults({parameter}=...)`` value applies."'
    )


def test_the_backlog_only_shrinks() -> None:
    """Writing a missing `Args:` section removes its rows; nothing may add one."""
    live = {f"{path}::{name}::{parameter}" for path, name, parameter, documented in FACETS if not documented}
    assert not live - KNOWN_GAPS, f"new undocumented facet parameters: {sorted(live - KNOWN_GAPS)}"
    stale = sorted(KNOWN_GAPS - _all_facet_entries())
    assert not stale, f"KNOWN_GAPS names parameters that are gone or now documented: {stale}"


def _all_facet_entries() -> set[str]:
    """Every facet parameter in the package, documented or not, gaps included."""
    found: set[str] = set()
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.name in EXEMPT_FILES:
            continue
        relative = path.relative_to(PACKAGE).as_posix()
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            doc = ast.get_docstring(node)
            if not doc or "use_defaults" in doc:
                continue
            names = {a.arg for a in node.args.args + node.args.kwonlyargs}
            found |= {f"{relative}::{node.name}::{p}" for p in FACET_PARAMETERS if p in names}
    return found

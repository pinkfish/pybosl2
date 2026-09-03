# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Four rules the project has always stated and never checked (T39).

Each is clean today, which is why none of them has a budget: a violation would be a new defect
rather than old debt, and a ratchet that starts at zero is just a rule.

* **PLAN S-3** -- no `TODO` comments and no stubbed bodies. Unfinished work belongs in SPEC §12
  and TASKS.md, where it is tracked, rather than in a comment nobody greps for.
* **PLAN L-2** -- modern syntax only: `X | Y`, never `typing.Union`/`Optional`, and built-in
  generics rather than `typing.List`. Six `Union` aliases were found and converted in T39; five of
  them were the *same* alias copied into five modules, and only one of the five imported the names
  its own copy referenced.
* **PLAN T-9** -- no dynamic globals: never `globals()[name] = ...` or `setattr(module, ...)` to
  register an API. The one permitted `__getattr__` is the top-level lazy export table, which its
  stub declares statically.
* **PLAN T-6d** / **SPEC S-19b** -- no public return type is a union whose arm one of its own
  boolean parameters selects. PLAN X-4 has named a guard for this since it was written; the guard
  did not exist, which the T38 triage found.
"""

from __future__ import annotations

import ast
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "pybosl2"

#: Comment markers that mean "unfinished", whatever the spelling.
UNFINISHED = re.compile(r"#\s*(TODO|FIXME|XXX|HACK)\b")


def _union_arms(annotation: ast.expr) -> list[str]:
    """Return the top-level arms of a return annotation, or one arm if it is not a union.

    Reads the tree: a `|` nested inside a subscript belongs to a parameter of the container, not
    to the return type, and a quoted forward reference is one arm however many `|` it contains.
    """
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        try:
            annotation = ast.parse(annotation.value, mode="eval").body
        except SyntaxError:  # pragma: no cover - an annotation that is not an expression
            return [annotation.value]
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        return _union_arms(annotation.left) + _union_arms(annotation.right)
    return [ast.unparse(annotation)]


def _modules() -> list[tuple[str, str, ast.Module]]:
    """Return (name, source, tree) for every module in the package."""
    out = []
    for path in sorted(PACKAGE.rglob("*.py")):
        source = path.read_text()
        out.append((path.relative_to(PACKAGE).as_posix(), source, ast.parse(source)))
    return out


MODULES = _modules()


def test_the_scan_found_the_package() -> None:
    """A scan that matched nothing would make every check below vacuous."""
    assert len(MODULES) > 50, f"only {len(MODULES)} modules found; the scan is broken"


def test_no_unfinished_work_hides_in_a_comment() -> None:
    """PLAN S-3: unfinished work lives in the spec's conformance table, not in a comment."""
    found = [
        f"{name}:{i}: {line.strip()[:70]}"
        for name, source, _ in MODULES
        for i, line in enumerate(source.splitlines(), 1)
        if UNFINISHED.search(line)
    ]
    assert not found, "unfinished work marked in a comment (PLAN S-3):\n  " + "\n  ".join(found)


def test_no_stubbed_body_ships() -> None:
    """PLAN S-3's other half: a body that is only `pass` or `...` is unfinished work too.

    A `Protocol` member is exactly that by design, and an abstract method raising
    `NotImplementedError` is a real body, so neither counts.
    """
    found: list[str] = []
    for name, _, tree in MODULES:
        protocols = {
            n.name
            for n in ast.walk(tree)
            if isinstance(n, ast.ClassDef) and any("Protocol" in ast.unparse(b) for b in n.bases)
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if node.name in protocols:
                continue
            for member in node.body:
                if not isinstance(member, ast.FunctionDef) or member.name.startswith("_"):
                    continue
                body = [
                    s
                    for s in member.body
                    if not (
                        isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str)
                    )
                ]
                if len(body) == 1 and isinstance(body[0], ast.Pass):
                    found.append(f"{name}::{node.name}.{member.name}")
    assert not found, "stubbed bodies (PLAN S-3):\n  " + "\n  ".join(found)


def test_no_legacy_typing_spellings() -> None:
    """PLAN L-2: `X | Y` and built-in generics, never `typing.Union` or `typing.List`."""
    legacy = {"Union", "Optional", "List", "Dict", "Tuple", "Set", "FrozenSet", "Type"}
    found = [
        f"{name}: from typing import {alias.name}"
        for name, _, tree in MODULES
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "typing"
        for alias in node.names
        if alias.name in legacy
    ]
    found += [
        f"{name}: typing.{node.attr}"
        for name, _, tree in MODULES
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "typing"
        and node.attr in legacy
    ]
    assert not found, "legacy typing spellings (PLAN L-2):\n  " + "\n  ".join(found)


def test_no_api_is_registered_dynamically() -> None:
    """PLAN T-9: never `globals()[name] = ...` or `setattr(module, ...)` to bind an API.

    A name bound that way is invisible to a type checker, to an IDE and to every tool that walks
    the export list -- which is the same reason A-4 requires the lazy exports to have a stub.
    """
    # T-9's own carve-out: "the one permitted `__getattr__` is the top-level lazy re-export
    # table, which is backed by its stub" -- and caching the resolved name in `globals()` is how
    # that table avoids re-importing. It is declared statically in `__init__.pyi` (T-8), which is
    # the property that makes it safe and that `tests/test_init_stub.py` checks.
    allowed = {"__init__.py"}
    found: list[str] = []
    for name, _, tree in MODULES:
        if name in allowed:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Subscript)
                and isinstance(t.value, ast.Call)
                and getattr(t.value.func, "id", "") == "globals"
                for t in node.targets
            ):
                found.append(f"{name}: globals()[...] = ...")
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "setattr" and node.args:
                first = ast.unparse(node.args[0])
                if first in ("module", "mod", "sys.modules[__name__]"):
                    found.append(f"{name}: setattr({first}, ...)")
    assert not found, "dynamically registered API (PLAN T-9):\n  " + "\n  ".join(found)


def test_no_public_return_type_is_a_flag_selected_union() -> None:
    """PLAN T-6d and SPEC S-19b: a bool that picks which arm comes back is a second function.

    `path_sweep(..., transforms=True)` returning matrices instead of geometry is the case these
    rules exist for; it was split into `path_sweep_transforms()` in T18. PLAN X-4 has named this
    test since it was written and it did not exist until T39 -- the triage found the claim.
    """
    offenders: list[str] = []
    for name, _, tree in MODULES:
        exported: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "__all__" for t in node.targets):
                exported = {
                    e.value for e in ast.walk(node.value) if isinstance(e, ast.Constant) and isinstance(e.value, str)
                }
        if not exported:
            continue
        targets: list[tuple[str, ast.FunctionDef]] = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in exported:
                targets.append((node.name, node))
            elif isinstance(node, ast.ClassDef) and node.name in exported:
                targets += [
                    (f"{node.name}.{m.name}", m)
                    for m in node.body
                    if isinstance(m, ast.FunctionDef) and not m.name.startswith("_")
                ]
        for callable_name, node in targets:
            if node.returns is None:
                continue
            returns = ast.unparse(node.returns)
            arms = _union_arms(node.returns)
            # `X | None` is an optional result, not a flag-selected union; and a `|` inside a
            # subscript (`list[tuple[str | None, ...]]`) is not a union of the return type at all,
            # which is why this reads the tree rather than splitting the text.
            if len(arms) < 2 or (len(arms) == 2 and "None" in arms):
                continue
            booleans = [
                a.arg
                for a in node.args.args + node.args.kwonlyargs
                if a.annotation is not None and ast.unparse(a.annotation) in ("bool", "bool | None")
            ]
            if booleans:
                offenders.append(f"{name}::{callable_name} -> {returns} (bool: {booleans})")
    assert not offenders, (
        "a boolean parameter selects the return type (PLAN T-6d, SPEC S-19b). Split it into two "
        "functions, each returning one thing:\n  " + "\n  ".join(offenders)
    )

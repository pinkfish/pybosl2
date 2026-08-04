#!/usr/bin/env python3
# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Validate all ``.. pythonscad-example::`` code blocks in pybosl2.

Scans ``pybosl2/**/*.py`` docstrings (via AST for proper string unescaping) and
``docs/*.rst`` directive blocks, extracting Python snippets and statically verifying:

* Syntax validity (``compile``)
* Import resolution (``from pybosl2.xxx import ...`` and ``import ...``)
* Name references (no undefined names beyond the slimmed preamble)

The slimmed preamble (``docs/_ext/pybosl2_example.py``) provides ``sys``,
``math``, ``os``, ``traceback``, ``np`` (numpy) but NOT any pybosl2 names --
examples must supply their own imports.
"""

from __future__ import annotations

import ast
import builtins
import importlib
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Names injected by the rendering preamble
# (docs/_ext/pybosl2_example.py _PREAMBLE, lines 57–79):
#   import sys, math, site, os, traceback
#   import numpy as np
# ---------------------------------------------------------------------------
_PREAMBLE_NAMES: frozenset[str] = frozenset({"sys", "math", "site", "os", "traceback", "np"})

_BUILTIN_NAMES: frozenset[str] = frozenset(dir(builtins))

# ---------------------------------------------------------------------------
# Phase 0 – bootstrap pybosl2 so lazy-export tables are populated
# ---------------------------------------------------------------------------
_loaded_pybosl2 = False


def _ensure_pybosl2_loaded() -> None:
    global _loaded_pybosl2
    if _loaded_pybosl2:
        return
    importlib.import_module("pybosl2")
    _loaded_pybosl2 = True


# ---------------------------------------------------------------------------
# Common block extraction from plain-text strings
# ---------------------------------------------------------------------------

_BLOCK_START_RE = re.compile(r"^\.\.\s+pythonscad-example::$", re.MULTILINE)


def _extract_blocks_from_text(
    text: str,
) -> Iterator[tuple[int, str]]:
    """Yield ``(offset_line_in_text, code)`` for each block found in *text*.

    *offset_line_in_text* is the 0-based line index within *text* where the
    ``.. pythonscad-example::`` directive appears.
    """
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped != ".. pythonscad-example::":
            i += 1
            continue
        directive_indent = len(line) - len(line.lstrip())

        j = i + 1
        if j < len(lines) and lines[j].strip() == "":
            j += 1

        code_lines: list[str] = []
        min_code_indent: int | None = None
        while j < len(lines):
            nl = lines[j]
            if nl.strip() == "":
                code_lines.append(nl)
                j += 1
                continue
            nl_indent = len(nl) - len(nl.lstrip())
            if nl_indent <= directive_indent:
                break
            if min_code_indent is None or nl_indent < min_code_indent:
                min_code_indent = nl_indent
            code_lines.append(nl)
            j += 1

        if code_lines:
            if min_code_indent is not None:
                code_lines = [cl[min_code_indent:] if cl.strip() else "" for cl in code_lines]
            code = "\n".join(code_lines).strip()
            if code:
                yield (i, code)

        i = j


# ---------------------------------------------------------------------------
# Extraction from .py docstrings (via AST for proper string unescaping)
# ---------------------------------------------------------------------------


def _extract_py_examples() -> Iterator[tuple[Path, int, str]]:
    """Yield ``(file, line_number, code)`` from ``.. pythonscad-example::``
    blocks inside .py docstrings.

    Docstrings are extracted via ``ast.get_docstring()`` for proper Python
    string unescaping (e.g. ``\\\\`` → ``\\``).  Line numbers are determined
    by re-scanning the raw source to pinpoint the ``.. pythonscad-example::``
    directive line.
    """
    for py_file in sorted((REPO_ROOT / "pybosl2").rglob("*.py")):
        try:
            source = py_file.read_text()
            tree = ast.parse(source)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue

        for node in ast.walk(tree):
            if not isinstance(
                node,
                (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                continue
            docstring = ast.get_docstring(node)
            if docstring is None or ".. pythonscad-example::" not in docstring:
                continue

            # Extract code blocks from the properly-unescaped docstring
            blocks = list(_extract_blocks_from_text(docstring))
            if not blocks:
                continue

            # Re-scan raw source lines for accurate line numbers
            source_lines = source.splitlines()
            directive_lines = _find_directive_lines_in_source(source_lines, ".. pythonscad-example::")
            for offset_in_doc, code in blocks:
                # Find the best-matching directive in the source that overlaps
                # with this node's range
                best_lineno = _find_best_directive_line(source_lines, node, directive_lines, offset_in_doc)
                yield (py_file, best_lineno, code)


_DOCSTRING_NODE_TYPES = (
    ast.Module,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
)


def _find_directive_lines_in_source(source_lines: list[str], needle: str) -> list[int]:
    """Return 1-based line numbers of lines whose stripped text equals *needle*."""
    result: list[int] = []
    for idx, line in enumerate(source_lines, 1):
        if line.strip() == needle:
            result.append(idx)
    return result


def _find_best_directive_line(
    source_lines: list[str],
    node: ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    directive_lines: list[int],
    offset_in_doc: int,
) -> int:
    """Pick the directive line that falls within *node*'s range and best
    matches the expected position within the docstring.

    Falls back to ``node.lineno + offset_in_doc + 1`` if no good match is found.
    """
    node_start = node.lineno
    node_end = node.end_lineno if node.end_lineno is not None else node_start

    candidates = [dl for dl in directive_lines if node_start <= dl <= node_end]
    if len(candidates) == 1:
        return candidates[0]

    # For nodes with a known docstring start, prefer the directive line that
    # corresponds to ``doc_start + offset_in_doc``
    if hasattr(node, "body") and node.body:
        first_stmt = node.body[0]
        if (
            isinstance(first_stmt, ast.Expr)
            and isinstance(first_stmt.value, ast.Constant)
            and isinstance(first_stmt.value.value, str)
        ):
            doc_start = first_stmt.lineno
            # If """ is on its own line, docstring text starts on next line
            source_line = source_lines[doc_start - 1].strip()
            doc_text_start = doc_start + 1 if source_line in ('"""', "'''") else doc_start
            expected = doc_text_start + offset_in_doc

            if expected in candidates:
                return expected
            if candidates:
                return min(candidates, key=lambda c: abs(c - expected))

    if candidates:
        return candidates[0]
    return node.lineno + offset_in_doc + 1


# ---------------------------------------------------------------------------
# Extraction from docs/*.rst
# ---------------------------------------------------------------------------


def _extract_rst_examples() -> Iterator[tuple[Path, int, str]]:
    """Yield ``(file, line_number, code)`` from ``.. pythonscad-example::``
    blocks inside ``docs/*.rst``."""
    for rst_file in sorted((REPO_ROOT / "docs").glob("*.rst")):
        if rst_file.name.startswith("_"):
            continue
        try:
            source = rst_file.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        for offset, code in _extract_blocks_from_text(source):
            yield (rst_file, offset + 1, code)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


class _ExampleError(Exception):
    """A single validation failure for one example block."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _resolve_import_from(module_name: str, names: list[str]) -> list[str]:
    """Check that *names* can be imported from *module_name*.

    Returns a list of failure messages (empty = all ok).
    """
    failures: list[str] = []
    try:
        mod = importlib.import_module(module_name)
    except ImportError as e:
        return [f"cannot import module {module_name!r}: {e}"]
    for name in names:
        if name == "*":
            continue
        if hasattr(mod, name):
            continue
        if module_name == "pybosl2" and hasattr(mod, "_LAZY_EXPORTS") and name in mod._LAZY_EXPORTS:
            continue
        failures.append(f"name {name!r} not found in module {module_name!r}")
    return failures


def _resolve_import(module_name: str) -> list[str]:
    """Check that *module_name* can be imported."""
    try:
        importlib.import_module(module_name)
        return []
    except ImportError as e:
        return [f"cannot import module {module_name!r}: {e}"]


def _collect_scope_names(tree: ast.AST) -> tuple[set[str], set[str]]:
    """Walk *tree* and return ``(defined_names, loaded_names)``.

    *defined_names* includes import aliases, assignment targets,
    function/class definitions, function/lambda parameters, for-loop
    targets, with-item targets, and except-handler names.

    *loaded_names* are all ``Name(id=..., ctx=Load)`` nodes.
    """
    defined: set[str] = set()
    loaded: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Store):
                defined.add(node.id)
            elif isinstance(node.ctx, ast.Load):
                loaded.add(node.id)

        elif isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.asname or alias.name.split(".")[0]
                defined.add(root)

        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                defined.add(alias.asname or alias.name)

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)

        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                defined.add(node.name)

        # Function / lambda parameters (ast.arguments node)
        elif isinstance(node, ast.arguments):
            for arg in node.args + node.posonlyargs + node.kwonlyargs:
                defined.add(arg.arg)
            if node.vararg:
                defined.add(node.vararg.arg)
            if node.kwarg:
                defined.add(node.kwarg.arg)

    return defined, loaded


def _validate_code(_file_path: Path, _line_number: int, code: str) -> list[_ExampleError]:
    """Run all static checks on a single example block.

    Returns a list of :class:`_ExampleError` (empty = all good).
    """
    errors: list[_ExampleError] = []

    # 1. Syntax check -------------------------------------------------------
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        errors.append(_ExampleError(f"syntax error: {e.msg} (line {e.lineno})"))
        return errors

    # 2. Import resolution --------------------------------------------------
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            names = [alias.name for alias in node.names]
            for msg in _resolve_import_from(node.module, names):
                errors.append(_ExampleError(f"import failure: {msg}"))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for msg in _resolve_import(alias.name):
                    errors.append(_ExampleError(f"import failure: {msg}"))

    # 3. Name resolution ----------------------------------------------------
    defined, loaded = _collect_scope_names(tree)
    known = defined | _PREAMBLE_NAMES | _BUILTIN_NAMES
    for name in sorted(loaded - known):
        errors.append(_ExampleError(f"undefined name: {name!r}"))

    return errors


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_RESET = "\033[0m"


def _fmt_loc(file_path: Path, line_number: int) -> str:
    rel = file_path.relative_to(REPO_ROOT) if file_path.is_relative_to(REPO_ROOT) else file_path
    return f"{rel}:{line_number}"


def main() -> int:
    _ensure_pybosl2_loaded()

    all_errors: list[tuple[Path, int, str, list[_ExampleError]]] = []
    total_blocks = 0

    extractors: list[tuple[str, object]] = [
        ("pybosl2/**/*.py docstrings", _extract_py_examples),
        ("docs/*.rst directives", _extract_rst_examples),
    ]

    for _label, extractor_fn in extractors:
        for file_path, line_number, code in extractor_fn():  # type: ignore[operator]
            total_blocks += 1
            errors = _validate_code(file_path, line_number, code)
            if errors:
                all_errors.append((file_path, line_number, code, errors))

    # ---- Print results ----------------------------------------------------
    print(f"\nValidated {total_blocks} pythonscad-example blocks")
    print(f"  - {total_blocks - len(all_errors)} passed")
    print(f"  - {len(all_errors)} failed\n")

    if not all_errors:
        print(f"{_GREEN}All examples passed validation.{_RESET}\n")
        return 0

    for file_path, line_number, code, errors in all_errors:
        print(f"{_RED}FAIL{_RESET} {_fmt_loc(file_path, line_number)}")
        code_lines = code.splitlines()
        for cl in code_lines[:8]:
            print(f"  {_YELLOW}{cl}{_RESET}")
        if len(code_lines) > 8:
            print(f"  ... ({len(code_lines)} lines total)")
        for err in errors:
            print(f"  {_RED}->{_RESET} {err.message}")
        print()

    print(f"{_RED}{len(all_errors)} block(s) had errors.{_RESET}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())

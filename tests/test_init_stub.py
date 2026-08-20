# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The top-level stub must stay in step with the lazy export table it describes."""

from __future__ import annotations

import ast
from pathlib import Path

import pybosl2

STUB = Path(pybosl2.__file__).with_suffix(".pyi")


def _stub_names() -> set[str]:
    """Return every name the stub binds (imports, aliases, and annotated assignments)."""
    tree = ast.parse(STUB.read_text())
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def test_stub_exists() -> None:
    assert STUB.is_file(), "pybosl2/__init__.pyi is required so the lazy exports type-check (SPEC A-4)"


def test_stub_covers_every_lazy_export() -> None:
    missing = sorted(set(pybosl2._LAZY_EXPORTS) - _stub_names())
    assert not missing, f"names exported lazily but absent from __init__.pyi: {missing}"


def test_stub_declares_nothing_extra() -> None:
    declared = _stub_names() - {"Final", "__version__", "__all__"}
    extra = sorted(declared - set(pybosl2.__all__))
    assert not extra, f"names in __init__.pyi that pybosl2 does not export: {extra}"


def test_every_lazy_export_resolves() -> None:
    for name in pybosl2.__all__:
        assert getattr(pybosl2, name) is not None, name

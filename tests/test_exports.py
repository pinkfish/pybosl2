# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Every name a module advertises must resolve (SPEC A-7, PLAN M-2)."""

from __future__ import annotations

import importlib
import pkgutil

import pytest

import pybosl2

MODULES = sorted(
    name
    for _, name, _ in pkgutil.walk_packages(pybosl2.__path__, prefix="pybosl2.")
    if not any(part.startswith("_") for part in name.split("."))
)


@pytest.mark.parametrize("module_name", MODULES)
def test_every_all_entry_resolves(module_name: str) -> None:
    module = importlib.import_module(module_name)
    declared = getattr(module, "__all__", None)
    if declared is None:
        return
    missing = sorted(name for name in declared if not hasattr(module, name))
    assert not missing, f"{module_name}.__all__ advertises names that do not exist: {missing}"


def test_top_level_all_resolves() -> None:
    missing = sorted(name for name in pybosl2.__all__ if not hasattr(pybosl2, name))
    assert not missing, f"pybosl2.__all__ advertises names that do not exist: {missing}"

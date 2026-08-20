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


def test_every_part_exposes_shape_as_a_property() -> None:
    """A part's geometry is a value, not an action (SPEC C-14, PLAN O-2)."""
    import inspect

    import pybosl2.parts as parts

    offenders: list[str] = []
    for name in parts.__all__:
        cls = getattr(parts, name)
        if not inspect.isclass(cls) or not hasattr(cls, "shape"):
            continue
        if not isinstance(inspect.getattr_static(cls, "shape"), property):
            offenders.append(name)
    assert not offenders, f"parts whose `shape` is not a property: {offenders}"


def test_part_show_returns_the_shape() -> None:
    """show() closes a chain rather than swallowing the value (SPEC S-49, S-51)."""
    import inspect

    import pybosl2.parts as parts

    offenders: list[str] = []
    for name in parts.__all__:
        cls = getattr(parts, name)
        if not inspect.isclass(cls) or not hasattr(cls, "show"):
            continue
        if inspect.signature(cls.show).return_annotation in (None, "None"):
            offenders.append(name)
    assert not offenders, f"parts whose show() returns None: {offenders}"

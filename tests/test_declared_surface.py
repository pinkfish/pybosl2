# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""What the package declares about itself is true (T39).

Four of the nineteen rules the T38 triage found unchecked are claims the package makes in one
place about something that lives in another -- a dependency list, an allowlist, a set of frozen
classes. Each is cheap to check and none was checked.

* **SPEC C-6** -- every name forwarded to the native object exists on it. The allowlist was the
  half that existed; that its entries are real is the half that catches a typo.
* **PLAN L-4** -- the runtime dependencies are exactly the five the plan names. The list has grown
  twice (`shapely`, `svgelements`) and the plan was updated by hand both times.
* **PLAN O-5** -- spec objects are frozen dataclasses, so a resolved dimension cannot be reassigned.
* **SPEC A-5** -- the shadowing names are deliberate, so the package is not wildcard re-exported.
"""

from __future__ import annotations

import ast
import pathlib
import tomllib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Native operations the PythonSCAD **app** provides and the pip wheel does not. The allowlist
#: carries them because the app is a supported runtime; the wheel's absence of them is why the
#: render tests skip rather than fail (PLAN X-2).
APP_ONLY = frozenset({"roof"})

#: `ScrewSpec` is the one spec object that is not a frozen dataclass: it has an 87-line
#: constructor that parses a trade name and derives a dozen dimensions, so converting it is a
#: refactor rather than a decorator. Recorded here so nothing *else* joins it.
NOT_FROZEN = frozenset({"screws.py::ScrewSpec"})


def test_every_forwarded_name_exists_on_the_wrapped_object() -> None:
    """SPEC C-6: the passthrough allowlist names real attributes, not hopeful ones."""
    from pybosl2._shape import _NATIVE_PASSTHROUGH

    try:
        from pybosl2 import cuboid

        native = cuboid([1, 1, 1]).shape
    except Exception as exc:  # pragma: no cover - no native runtime here
        pytest.skip(f"needs a native runtime: {exc}")

    missing = sorted(n for n in _NATIVE_PASSTHROUGH if not hasattr(native, n) and n not in APP_ONLY)
    assert not missing, (
        f"forwarded names that the wrapped object does not have (SPEC C-6): {missing}. "
        f"A forwarded name that does not exist fails at the call site with an AttributeError "
        f"from inside the wrapper, which is the error C-6's allowlist exists to prevent."
    )


def test_the_runtime_dependencies_are_the_ones_the_plan_names() -> None:
    """PLAN L-4: adding one is an architectural decision, so the two lists agree or it was not made."""
    declared = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    # strip the version pins; L-4 is about which packages, not which versions
    packages = {d.split(">")[0].split("=")[0].split("[")[0].strip() for d in declared}
    named = {"numpy", "typing-extensions", "webcolors", "svgelements", "shapely"}
    assert packages == named, (
        f"pyproject declares {sorted(packages)} and PLAN L-4 names {sorted(named)}. Adding a "
        f"runtime dependency is an architectural decision (L-4): change the plan in the same "
        f"commit, or do not add it."
    )


def test_every_spec_object_is_frozen() -> None:
    """PLAN O-5: a resolved dimension is a value, and a value does not change under the caller."""
    loose: list[str] = []
    for path in sorted((ROOT / "pybosl2" / "parts").rglob("*.py")):
        relative = path.relative_to(ROOT / "pybosl2" / "parts").as_posix()
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.ClassDef) or not node.name.endswith("Spec"):
                continue
            entry = f"{relative}::{node.name}"
            frozen = any("frozen=True" in ast.unparse(d) for d in node.decorator_list)
            if not frozen and entry not in NOT_FROZEN:
                loose.append(entry)
    assert not loose, f"spec objects that are not frozen dataclasses (PLAN O-5): {loose}"


def test_the_known_exception_is_not_stale() -> None:
    """If `ScrewSpec` is converted, its row comes out rather than sitting here as a lie."""
    source = (ROOT / "pybosl2" / "parts" / "screws.py").read_text()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and node.name == "ScrewSpec":
            if any("frozen=True" in ast.unparse(d) for d in node.decorator_list):
                pytest.fail("ScrewSpec is frozen now -- remove it from NOT_FROZEN.")
            return
    pytest.fail("ScrewSpec is gone -- remove it from NOT_FROZEN.")


def test_the_package_is_not_wildcard_re_exported() -> None:
    """SPEC A-5: `square`/`circle`/`cube`/`text` shadow the OpenSCAD builtins on purpose.

    That is safe only while a caller has to ask for them by name. A `from pybosl2 import *`
    anywhere in the package would put the shadowing names into a namespace that did not choose
    them, which is the case the rule exists to prevent.
    """
    offenders = [
        f"{path.relative_to(ROOT).as_posix()}:{node.lineno}"
        for path in sorted((ROOT / "pybosl2").rglob("*.py"))
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names)
    ]
    assert not offenders, f"wildcard imports inside the package (SPEC A-5): {offenders}"


def test_the_shadowing_names_are_still_the_anchor_aware_ones() -> None:
    """A-5's premise: these names shadow the builtins deliberately, so they must be ours."""
    import pybosl2

    for name in ("square", "circle", "cube", "text"):
        value = getattr(pybosl2, name)
        assert callable(value), f"{name} is not callable"
        assert value.__module__.startswith("pybosl2"), f"{name} resolves to {value.__module__}"

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

#: Empty, and it stays empty. `ScrewSpec` was the one exception -- an 88-line constructor that
#: parses a trade name and derives eleven dimensions, which the row called "a refactor rather
#: than a decorator". Both halves were true and the conclusion did not follow: the constructor
#: takes a *specification* and the fields are what it derives, so `frozen=True, init=False` with
#: a hand-written `__init__` fits exactly, and the refactor the row was waiting for turned out to
#: be a separate gain (the parse and the table lookup split out, and the file's over-long
#: function budget went 2 -> 1).
NOT_FROZEN: frozenset[str] = frozenset()


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


def test_no_spec_object_claims_an_exception() -> None:
    """PLAN O-5: the exception list is empty, and a new row needs a reason nobody has yet."""
    assert not NOT_FROZEN, (
        f"{sorted(NOT_FROZEN)} -- every spec object is a frozen dataclass. A constructor that "
        f"cannot use the generated `__init__` is not a reason: `frozen=True, init=False` with "
        f"`object.__setattr__` is the stdlib pattern, and it is what `ScrewSpec` uses."
    )


def test_a_resolved_dimension_does_not_change_under_the_caller() -> None:
    """PLAN O-5: freezing is only worth recording if assignment actually raises.

    The `frozen=True` scan above reads decorators, so it would pass for a class that had the
    decorator and no immutability -- `init=False` plus a hand-written `__init__` is exactly the
    shape where that could go wrong, since the fields are set through `object.__setattr__` and
    a class could set them any other way without the scan noticing.
    """
    import dataclasses

    from pybosl2.parts.screws import ScrewSpec

    spec = ScrewSpec("M6")
    assert spec.diameter == 6.0
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.diameter = 99.0  # type: ignore[misc]
    assert spec.diameter == 6.0, "the assignment raised but landed anyway"


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


def test_no_exported_name_is_also_a_submodule_name() -> None:
    """One name, one thing -- and `import` decides this one, not the package (SPEC C-21).

    `pybosl2/texture.py` held the texture machinery and `texture` was also a top-level export, the
    BOSL2 function that builds a tile. Python binds a submodule onto its package as an attribute
    when the submodule is imported, and that wins over the package's own lazy export table -- so
    `from pybosl2 import texture` gave the **function** or the **module** depending on whether
    anything had imported `pybosl2.texture` first:

        >>> from pybosl2 import texture           # the function
        >>> from pybosl2.texture import TEXTURES  # ... and now `pybosl2.texture` is the module

    Order-dependent, so it survived every test that imported one way. It came out when a new test
    module imported the other way and two unrelated tests three files later started calling a
    module. The module is `pybosl2.textures` now; the function keeps BOSL2's spelling (B2-3), it
    being the half a caller reads.

    There was exactly one such name in the package, which is why this is a plain assertion rather
    than a budget.
    """
    import re

    source = (ROOT / "pybosl2" / "__init__.py").read_text()
    exported = {name for name, _ in re.findall(r'^\s*"(\w+)": \("pybosl2\.[\w.]+", "(\w+)"\),', source, re.M)}
    package = ROOT / "pybosl2"
    submodules = {p.stem for p in package.glob("*.py") if p.stem != "__init__"}
    submodules |= {p.name for p in package.iterdir() if p.is_dir() and (p / "__init__.py").exists()}

    assert exported, "the lazy export table was not found -- this check is reading the wrong thing"
    clash = sorted(exported & submodules)
    assert not clash, (
        f"these names are both a top-level export and a submodule: {clash}. Importing the "
        f"submodule rebinds the name on the package, so `from pybosl2 import {clash[0]}` returns "
        f"whichever the import order happened to leave there. Rename the module."
    )

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""Every part builds on the backend that is supposed to work, and hands back a wrapper.

SPEC C-14a, C-14. Two things had no guard, and they turn out to be the same guard.

**Nothing built every part on CSG.** `tests/test_parts_are_lazy.py` constructs each part and
checks it built *nothing* yet; `tests/test_parts_backend_coverage.py` builds each one on SDF, where
twelve are listed CSG-only and refuse. So for those twelve, the only thing ever exercised was the
refusal -- and a refusal that arrives first makes every argument behind it unfalsifiable. Both
modules passed `"trapezoidal"` as `ThreadedRod`'s *profile*, which is a list of points; `__init__`
accepted it (iterating a string gives characters), `shape` raised a raw `ValueError` from a
different method than the one called wrongly, and neither module was ever in a position to see it.

**`.shape` means two things, and only one of them is a part's.** C-14a exists because on a part
`.shape` is the finished `Solid`/`Flat`, while on a backend wrapper (`CsgSolid.shape`) it is the
raw native handle being wrapped. A part that returned its wrapper's `.shape` instead of the wrapper
would be handing back a `PyOpenSCAD`, and would *mostly work* -- which is the failure this campaign
keeps finding. The rule was recorded as a docstring obligation and enforced by nothing; asserted on
the objects instead, it costs nothing on top of building them.
"""

from __future__ import annotations

import pytest
from part_fixtures import PARTS, arguments

from pybosl2 import use_backend

#: What a part is allowed to hand back: the wrapped geometry types, never a native handle. Named by
#: module rather than imported so that a new backend type cannot satisfy this by accident.
_WRAPPER_MODULE = "pybosl2"


@pytest.mark.parametrize("name", sorted(PARTS))
def test_every_part_builds_on_the_csg_backend(name: str) -> None:
    """SPEC C-14: a part that cannot be built is a part whose arguments mean nothing.

    The extent is asserted rather than mere existence -- a part that builds an empty solid has not
    built anything, and `tests/test_assertion_quality.py` is right that "it returned something" is
    not a result. Every one of the 51 is positive on all three axes.
    """
    args, kwargs = arguments(PARTS[name])
    with use_backend("csg"):
        built = PARTS[name](*args, **kwargs).shape
    size = [float(v) for v in built.bounds().size]
    assert min(size) > 0.0, f"{name}.shape built an empty solid: its bounds measure {size}"


@pytest.mark.parametrize("name", sorted(PARTS))
def test_a_parts_shape_is_never_a_native_handle(name: str) -> None:
    """SPEC C-14a: on a part `.shape` is the finished geometry, not the handle a wrapper holds."""
    args, kwargs = arguments(PARTS[name])
    with use_backend("csg"):
        built = PARTS[name](*args, **kwargs).shape
    module = type(built).__module__
    assert module.split(".")[0] == _WRAPPER_MODULE, (
        f"{name}.shape returned a {module}.{type(built).__name__}. On a part `.shape` is the "
        f"finished Solid/Flat/Path2D; the raw native handle is what a *wrapper*'s `.shape` means "
        f"(SPEC C-14a), and handing one out here would mostly work, which is the problem"
    )


def test_the_inventory_is_not_empty() -> None:
    """A discovery walk that finds nothing would make every test above vacuous."""
    assert len(PARTS) > 40, f"only {len(PARTS)} parts discovered; the walk is broken"


def test_every_shape_declares_the_type_it_returns() -> None:
    """SPEC C-14a's prose clause, in the form that a reader and a type checker both get.

    The rule is written as a docstring obligation -- each `.shape` must say which side of the FFI
    it means. What actually reaches a reader at the call site, and the only spelling `mypy` can act
    on, is the return annotation, so that is what is required to be concrete here: 49 of the 51
    docstrings name no type at all, while all 51 annotations do. A bare or `Any` annotation is the
    case where the name `.shape` is genuinely ambiguous and nothing resolves it.
    """
    import ast
    import pathlib

    vague = []
    for path in sorted(pathlib.Path("pybosl2").rglob("*.py")):
        for cls in ast.walk(ast.parse(path.read_text())):
            if not isinstance(cls, ast.ClassDef):
                continue
            for node in cls.body:
                if not (isinstance(node, ast.FunctionDef) and node.name == "shape"):
                    continue
                declared = ast.unparse(node.returns).strip("\"'") if node.returns else ""
                if declared in ("", "Any", "object"):
                    vague.append(f"{path}:{node.lineno} {cls.name}.shape -> {declared or '(nothing)'}")
    assert not vague, (
        "these `.shape` definitions declare no concrete type, so nothing says whether they mean a "
        f"part's finished geometry or a wrapper's native handle (SPEC C-14a): {vague}"
    )

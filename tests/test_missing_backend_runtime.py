# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A backend whose engine is not installed says so, naming the engine and the remedy.

SPEC E-1, E-2, E-4; PLAN M-3. M-3 keeps both engines out of the import path -- `import pybosl2`
works with neither installed, and each is reached through a lazy handle that defers its import to
first use. That is deliberate, and it left a gap at the other end: nothing converted the eventual
failure into a library error.

So a caller without libfive could select the SDF backend, build a whole model, and meet::

    ModuleNotFoundError: No module named 'libfive'

from four frames down at render time -- naming neither pybosl2, nor which backend, nor what to
install. `use_backend("sdf")` succeeded. `cuboid([20, 20, 20])` succeeded and returned an
`SdfSolid`. Only `.vnf()` failed, and by then the caller had no reason to connect the two. The CSG
side said the same about `pythonscad`.

It was invisible to this suite because the suite installs a libfive mock (`tests/conftest.py`), so
the import always succeeds here. The tests below remove it deliberately, which is the only way to
observe what a caller without the engine observes -- and is the shape of check T81 concluded was
needed, after a probe that could not tell "unsupported" from "unmeasurable here".
"""

from __future__ import annotations

import builtins
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

import pytest

from pybosl2.exceptions import BackendRuntimeMissingError, Bosl2Error


@contextmanager
def _without(module: str) -> Iterator[None]:
    """Make *module* unimportable, as it is for a caller who has not installed it."""
    saved = {name: mod for name, mod in sys.modules.items() if name.split(".")[0] == module}
    for name in saved:
        del sys.modules[name]
    real = builtins.__import__

    def blocked(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.split(".")[0] == module:
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        return real(name, *args, **kwargs)

    builtins.__import__ = blocked
    try:
        yield
    finally:
        builtins.__import__ = real
        sys.modules.update(saved)


def test_the_sdf_backend_names_libfive_and_how_to_get_it() -> None:
    """SPEC E-2: the message is the fix, not a traceback the caller has to interpret."""
    import pybosl2.sdf._libfive as handle

    saved = handle._LazyLibfive._mod
    handle._LazyLibfive._mod = None
    try:
        with _without("libfive"), pytest.raises(BackendRuntimeMissingError) as caught:
            handle.lv.max(1, 2)
    finally:
        handle._LazyLibfive._mod = saved

    message = str(caught.value)
    assert "libfive" in message, message
    assert "sdf" in message, "the message does not say which backend needs it"
    assert "install" in message.lower(), "the message does not say how to get it"


def test_the_csg_backend_names_pythonscad_and_how_to_get_it() -> None:
    """SPEC E-2: the same gap on the other side, and the same answer."""
    import pybosl2._native as native

    saved = dict(native._cache)
    native._cache.clear()
    try:
        with _without("pythonscad"), pytest.raises(BackendRuntimeMissingError) as caught:
            native.native("cube")([1, 1, 1])
    finally:
        native._cache.clear()
        native._cache.update(saved)

    message = str(caught.value)
    assert "pythonscad" in message, message
    assert "csg" in message, "the message does not say which backend needs it"


@pytest.mark.parametrize("engine", ["libfive", "pythonscad"])
def test_it_is_both_a_library_error_and_the_import_error_it_replaces(engine: str) -> None:
    """SPEC E-1: `except Bosl2Error` catches it, and code catching the import failure still works.

    The second half is what makes this safe to add to a released signature: a caller who wrote
    `except ModuleNotFoundError` around a render is not broken by the improvement.
    """
    error = BackendRuntimeMissingError(engine, "sdf", "`pip install x`")
    assert isinstance(error, Bosl2Error)
    assert isinstance(error, ModuleNotFoundError)
    assert error.name == engine, "the `name` attribute ModuleNotFoundError callers read is set"


def test_the_import_of_pybosl2_still_needs_neither_engine() -> None:
    """PLAN M-3: the conversion must not drag either engine into the import path.

    The failure mode this guards is subtle: adding a `from pybosl2.exceptions import ...` to a lazy
    handle is fine, but doing the conversion by importing the engine *eagerly* to test for it would
    satisfy every assertion above and break M-3.
    """
    import ast
    import pathlib

    import pybosl2.sdf._libfive as handle

    tree = ast.parse(pathlib.Path(handle.__file__).read_text())
    # Read the AST rather than the text: the module docstring names ``import libfive`` too, and a
    # substring search finds that first. The check is that every real import of it is nested
    # inside a function, which is what "deferred" means.
    top_level = {
        alias.name
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in getattr(node, "names", [])
    }
    assert "libfive" not in top_level, "libfive is imported at module level (PLAN M-3)"

    deferred = [
        node
        for function in ast.walk(tree)
        if isinstance(function, ast.FunctionDef)
        for node in ast.walk(function)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "libfive"
    ]
    assert deferred, "no deferred `import libfive` found; the lazy handle is not lazy any more"

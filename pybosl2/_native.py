# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# Lazy handles to PythonSCAD's native primitives (cube/cylinder/sphere/polygon/hull/...).
#
# The pure-Python geometry layer references these at module load, but PythonSCAD's C++ FFI
# (`pythonscad`) is only needed when geometry is actually *constructed*. Wrapping each native op
# in a lazy callable lets the whole `pybosl2` package import -- and its math/algorithms be
# unit-tested, type-checked and introspected -- without the FFI present; the `import pythonscad`
# happens on the first call, not at module load. This keeps the dependency direction right: the
# algorithmic code no longer drags the native runtime in just to be imported.
#

from __future__ import annotations

from typing import Any, Callable

__all__ = ["native"]

_cache: dict[str, Callable[..., Any]] = {}


def native(name: str) -> Callable[..., Any]:
    """Return a lazy callable proxying ``pythonscad.<name>``; imports the FFI on the first call.

    ``_ocube = native("cube")`` at module level behaves like ``from pythonscad import cube as
    _ocube`` at every call site, but defers ``import pythonscad`` until geometry is first built.

    Args:
        name: Name of the native primitive to reach.

    """

    # forwards to whichever native function `name` picks out, so this one keeps a generic
    # signature: the typed parameter lists live on the pybosl2 functions that call through it
    def _call(*args: Any, **kwargs: Any) -> Any:
        fn = _cache.get(name)
        if fn is None:
            import pythonscad  # deferred: the FFI is only needed to construct geometry

            fn = _cache[name] = getattr(pythonscad, name)
        if name == "polygon":
            if args:
                points = args[0]
                sanitized = [[float(x) for x in p] for p in points]
                args = (sanitized,) + args[1:]
            elif "points" in kwargs:
                points = kwargs["points"]
                kwargs["points"] = [[float(x) for x in p] for p in points]
        return fn(*args, **kwargs)

    _call.__name__ = _call.__qualname__ = f"native:{name}"
    return _call

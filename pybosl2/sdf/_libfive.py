# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# Lazy handle to the libfive F-Rep engine, mirroring pybosl2/_native.py for pythonscad. The SDF
# backend references ``lv.<op>`` (sqrt/min/max/abs/x/y/z/...) at module load to build symbolic
# distance fields, but ``libfive`` (the C extension) is only needed once a field is meshed. This
# proxy defers ``import libfive`` to the first ``lv.<attr>`` access, so the whole pybosl2 package
# -- SDF backend included -- imports without libfive present.
#

from __future__ import annotations

from typing import Any

__all__ = ["lv", "LVTree"]

# A libfive expression tree -- what ``lv.x()`` / ``lv.max(...)`` / ... return, and what the SDF
# closures (``sdf_fn(x, y, z)``) build and return. ``Any`` because libfive is lazily imported (no
# type is available at type-check time) and because these expressions transparently accept plain
# Python floats too (via libfive's operator overloading), so callers may pass either.
LVTree = Any


class _LazyLibfive:
    """A stand-in for ``import libfive as lv`` that imports libfive on first attribute access."""

    __slots__ = ()
    _mod: Any = None

    def __getattr__(self, name: str) -> Any:
        mod = _LazyLibfive._mod
        if mod is None:
            try:
                import libfive as mod2  # deferred: only needed to build/mesh SDF fields
            except ModuleNotFoundError as missing:
                # M-3 keeps the import out of the load path; this is the other end of it. Without
                # this the failure arrives here as a bare `No module named 'libfive'`, from four
                # frames down, after the caller has built a whole model -- naming neither pybosl2,
                # nor which backend, nor what to install (SPEC E-2, E-4).
                from pybosl2.exceptions import BackendRuntimeMissingError

                raise BackendRuntimeMissingError("libfive", "sdf", "`pip install libfive`") from missing

            _LazyLibfive._mod = mod2
            mod = mod2
        return getattr(mod, name)


lv: _LazyLibfive = _LazyLibfive()

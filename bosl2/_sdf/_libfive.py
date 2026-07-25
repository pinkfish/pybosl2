# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# Lazy handle to the libfive F-Rep engine, mirroring bosl2/_native.py for pythonscad. The SDF
# backend references ``lv.<op>`` (sqrt/min/max/abs/x/y/z/...) at module load to build symbolic
# distance fields, but ``libfive`` (the C extension) is only needed once a field is meshed. This
# proxy defers ``import libfive`` to the first ``lv.<attr>`` access, so the whole bosl2 package
# -- SDF backend included -- imports without libfive present.
#

from __future__ import annotations

from typing import Any

__all__ = ["lv"]


class _LazyLibfive:
    """A stand-in for ``import libfive as lv`` that imports libfive on first attribute access."""

    __slots__ = ()
    _mod: Any = None

    def __getattr__(self, name: str) -> Any:
        mod = _LazyLibfive._mod
        if mod is None:
            import libfive as mod  # deferred: only needed to build/mesh SDF fields

            _LazyLibfive._mod = mod
        return getattr(mod, name)


lv = _LazyLibfive()

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# The exact-CSG (PythonSCAD) backend of bosl2's dual-backend solid system -- the default. Each
# primitive returns a Bosl2Solid (``backend == "csg"``); booleans are the native CSG operators.
# Importing this module registers the backend under the name ``"csg"``. It only pulls in
# bosl2.shapes3d (itself FFI-free); the native runtime is touched lazily when geometry renders.
#

from __future__ import annotations

import functools
import operator
from typing import Any

from bosl2._backend import register_backend


class CsgBackend:
    """The exact-CSG realize backend (PythonSCAD). Primitives delegate to bosl2.shapes3d."""

    name = "csg"

    def construct(self, shape: str, *args: Any, **kwargs: Any) -> Any:
        """Build the named shape via bosl2.shapes3d (the CSG constructors)."""
        import bosl2.shapes3d as _m

        fn = getattr(_m, shape, None)
        if not callable(fn):
            raise ValueError(f"the csg backend has no shape constructor {shape!r}")
        return fn(*args, **kwargs)

    def polyhedron(self, points: Any, faces: Any, **kwargs: Any) -> Any:
        from bosl2._native import native
        from bosl2.shapes3d import Bosl2Solid

        return Bosl2Solid(native("polyhedron")(points, faces, **kwargs))

    def union(self, solids: Any) -> Any:
        return functools.reduce(operator.or_, solids)

    def difference(self, solids: Any) -> Any:
        return functools.reduce(operator.sub, solids)

    def intersection(self, solids: Any) -> Any:
        return functools.reduce(operator.and_, solids)


register_backend("csg", CsgBackend())

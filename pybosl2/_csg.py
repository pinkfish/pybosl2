# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# The exact-CSG (PythonSCAD) backend of pybosl2's dual-backend solid system -- the default. Each
# primitive returns a Bosl2Solid (``backend == "csg"``); booleans are the native CSG operators.
# Importing this module registers the backend under the name ``"csg"``. It only pulls in
# pybosl2.shapes3d (itself FFI-free); the native runtime is touched lazily when geometry renders.
#

from __future__ import annotations

import functools
import operator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pybosl2.caps import CapSpec
    from pybosl2.path3d import Path3D

from pybosl2._backend import register_backend
from pybosl2._native import native

_polygon = native("polygon")


class CsgBackend:
    """The exact-CSG realize backend (PythonSCAD). Primitives delegate to pybosl2.shapes3d."""

    name = "csg"

    def construct(self, shape: str, *args: Any, **kwargs: Any) -> Any:
        """Build the named shape via pybosl2.shapes3d (the CSG constructors)."""
        import pybosl2.shapes3d as _m

        fn = getattr(_m, shape, None)
        if not callable(fn):
            raise ValueError(f"the csg backend has no shape constructor {shape!r}")
        return fn(*args, **kwargs)

    def polyhedron(self, points: Any, faces: Any, **kwargs: Any) -> Any:
        from pybosl2._native import native
        from pybosl2.shapes3d import Bosl2Solid

        return Bosl2Solid(native("polyhedron")(points, faces, **kwargs))

    def linear_extrude(self, paths: Any, height: float, **kwargs: Any) -> Any:
        """Extrude *paths* into an exact-CSG solid: the first outline with the rest cut out of it.

        as holes, through the native ``linear_extrude()``. Accepts every native option
        (``center``/``twist``/``scale``/``slices``/...).
        """
        from pybosl2.shapes2d import Bosl2Shape2D
        from pybosl2.shapes3d import Bosl2Solid

        # plain floats: the native polygon()/FFI boundary rejects numpy scalars
        outlines = [[[float(p[0]), float(p[1])] for p in path] for path in paths]
        assert outlines, "linear_extrude(): needs at least one outline."
        shape = Bosl2Shape2D(_polygon(outlines[0]))
        for hole in outlines[1:]:
            shape = shape - Bosl2Shape2D(_polygon(hole))
        solid = shape.linear_extrude(height, **kwargs)
        return solid if isinstance(solid, Bosl2Solid) else Bosl2Solid(solid)

    def union(self, solids: Any) -> Any:
        return functools.reduce(operator.or_, solids)

    def difference(self, solids: Any) -> Any:
        return functools.reduce(operator.sub, solids)

    def intersection(self, solids: Any) -> Any:
        return functools.reduce(operator.and_, solids)

    def stroke(
        self,
        path: Path3D,
        width: float = 1,
        closed: bool | None = None,
        endcap1: CapSpec | None = None,
        endcap2: CapSpec | None = None,
        **_: Any,
    ) -> Any:
        """3-D tube along *path* via the CSG stroke_3d."""
        from pybosl2._stroke3d import stroke_3d

        return stroke_3d(path, width=width, closed=closed, endcap1=endcap1, endcap2=endcap2)


register_backend("csg", CsgBackend())

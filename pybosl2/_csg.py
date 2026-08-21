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
from typing import TYPE_CHECKING, Any, Callable, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pybosl2.caps import CapSpec
    from pybosl2.path3d import Path3D

from pybosl2._backend import for_backend, refuse_unhonoured, register_backend
from pybosl2._native import native

_polygon = native("polygon")


class CsgBackend:
    """The exact-CSG realize backend (PythonSCAD). Primitives delegate to pybosl2.shapes3d."""

    name = "csg"

    def constructor(self, shape: str, /) -> Callable[..., Any]:
        """Return the pybosl2.shapes3d constructor for *shape*.

        Args:
            shape: BOSL2 shape name, e.g. ``"cuboid"``.

        Returns:
            The CSG constructor that builds it.

        Raises:
            ValueError: If pybosl2.shapes3d has no such constructor.

        """
        import pybosl2.shapes3d as _m

        fn = getattr(_m, shape, None)
        if not callable(fn):
            raise ValueError(f"the csg backend has no shape constructor {shape!r}")
        return cast("Callable[..., Any]", fn)

    def construct(self, shape: str, arguments: Mapping[str, Any]) -> Any:
        """Build the named shape via pybosl2.shapes3d (the CSG constructors).

        Takes only the arguments this constructor declares, so the façade can forward every
        default it owns without a constructor choking on an option it has no notion of (B-3).
        """
        constructor = self.constructor(shape)
        refuse_unhonoured(shape, arguments, constructor, "csg")
        return constructor(**for_backend(constructor, arguments))

    def polyhedron(self, points: Any, faces: Any = None, convexity: int | None = None) -> Any:
        from pybosl2._native import native
        from pybosl2.shapes3d import Bosl2Solid

        if convexity is None:
            return Bosl2Solid(native("polyhedron")(points, faces))
        return Bosl2Solid(native("polyhedron")(points, faces, convexity=convexity))

    def linear_extrude(self, paths: Any, height: float, arguments: Mapping[str, Any]) -> Any:
        """Extrude *paths* into an exact-CSG solid: the first outline, the rest cut out as holes.

        Goes through the native ``linear_extrude()`` and accepts every native option
        (``center``/``twist``/``scale``/``slices``/...).
        """
        from pybosl2.shapes2d import Bosl2Shape2D
        from pybosl2.shapes3d import Bosl2Solid

        # plain floats: the native polygon()/FFI boundary rejects numpy scalars
        outlines = [[[float(p[0]), float(p[1])] for p in path] for path in paths]
        if not (outlines):
            raise ValueError("linear_extrude(): needs at least one outline.")
        shape = Bosl2Shape2D(_polygon(outlines[0]))
        for hole in outlines[1:]:
            shape = shape - Bosl2Shape2D(_polygon(hole))
        solid = shape.linear_extrude(height, **arguments)
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
    ) -> Any:
        """3-D tube along *path* via the CSG stroke_3d."""
        from pybosl2._stroke3d import stroke_3d

        return stroke_3d(path, width=width, closed=closed, endcap1=endcap1, endcap2=endcap2)


register_backend("csg", CsgBackend())

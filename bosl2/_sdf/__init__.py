# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# The F-Rep / signed-distance (libfive) backend of bosl2's dual-backend solid system, vendored
# from the pysolidfive engine. Shapes are symbolic SDF trees (``PyShape``) meshed via libfive's
# frep(); booleans are min/max, and rounding/chamfer/offset are native. Importing this module is
# FFI-free (libfive is a lazy handle -- see _libfive.py); libfive is only touched when a shape is
# meshed. Importing the package registers the backend under the name ``"sdf"``.
#

from __future__ import annotations

from typing import Any

from bosl2._backend import register_backend
from bosl2._sdf import shapes3d as _s

__all__ = ["SdfBackend"]


class SdfBackend:
    """The libfive/SDF realize backend. Each primitive returns a ``PyShape`` (``backend == "sdf"``)."""

    name = "sdf"

    def construct(self, shape: str, *args: Any, **kwargs: Any) -> _s.PyShape:
        """Build the named shape via the vendored SDF constructors (bosl2._sdf.shapes3d)."""
        return getattr(_s, shape)(*args, **kwargs)

    # -- primitives (delegate to the vendored SDF constructors) --------------------------------
    def cube(self, *args: Any, **kwargs: Any) -> _s.PyShape:
        return _s.cube(*args, **kwargs)

    def cuboid(self, *args: Any, **kwargs: Any) -> _s.PyShape:
        return _s.cuboid(*args, **kwargs)

    def sphere(self, *args: Any, **kwargs: Any) -> _s.PyShape:
        return _s.sphere(*args, **kwargs)

    def cylinder(self, *args: Any, **kwargs: Any) -> _s.PyShape:
        return _s.cylinder(*args, **kwargs)

    def polyhedron(self, *args: Any, **kwargs: Any) -> _s.PyShape:
        return _s.convex_polyhedron(*args, **kwargs)

    # -- n-ary CSG (min/max on the fields) -----------------------------------------------------
    def union(self, solids: Any) -> _s.PyShape:
        return _s.union(*solids)

    def difference(self, solids: Any) -> _s.PyShape:
        return _s.difference(*solids)

    def intersection(self, solids: Any) -> _s.PyShape:
        return _s.intersection(*solids)


register_backend("sdf", SdfBackend())

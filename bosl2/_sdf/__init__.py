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
        fn = getattr(_s, shape, None)
        if not callable(fn):
            raise ValueError(f"the sdf backend has no shape constructor {shape!r}")
        return fn(*args, **kwargs)

    def polyhedron(self, points: Any, faces: Any = None, **kwargs: Any) -> _s.PyShape:
        """The convex hull of `points` as an SDF. `faces` is accepted for signature-compatibility
        with the CSG backend but ignored -- the SDF backend builds only the convex polyhedron."""
        return _s.convex_polyhedron(points, **kwargs)

    # -- n-ary CSG (min/max on the fields) -----------------------------------------------------
    def union(self, solids: Any) -> _s.PyShape:
        return _s.union(*solids)

    def difference(self, solids: Any) -> _s.PyShape:
        return _s.difference(*solids)

    def intersection(self, solids: Any) -> _s.PyShape:
        return _s.intersection(*solids)


register_backend("sdf", SdfBackend())

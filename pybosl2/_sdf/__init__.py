# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# The F-Rep / signed-distance (libfive) backend of pybosl2's dual-backend solid system, vendored
# from the pysolidfive engine. Shapes are symbolic SDF trees (``PyShape``) meshed via libfive's
# frep(); booleans are min/max, and rounding/chamfer/offset are native. Importing this module is
# FFI-free (libfive is a lazy handle -- see _libfive.py); libfive is only touched when a shape is
# meshed. Importing the package registers the backend under the name ``"sdf"``.
#

from __future__ import annotations

from typing import Any

from pybosl2._backend import register_backend
from pybosl2._sdf import joiners, shapes2d, skin
from pybosl2._sdf import shapes3d as _s

__all__ = ["SdfBackend", "shapes2d", "skin", "joiners"]


class SdfBackend:
    """The libfive/SDF realize backend. Each primitive returns a ``PyShape`` (``backend == "sdf"``)."""

    name = "sdf"

    def construct(self, shape: str, *args: Any, **kwargs: Any) -> _s.PyShape:
        """Build the named shape via the vendored SDF constructors (pybosl2._sdf.shapes3d)."""
        fn = getattr(_s, shape, None)
        if not callable(fn):
            raise ValueError(f"the sdf backend has no shape constructor {shape!r}")
        return fn(*args, **kwargs)

    def polyhedron(self, points: Any, faces: Any = None, **kwargs: Any) -> _s.PyShape:
        """The convex hull of `points` as an SDF. `faces` is accepted for signature-compatibility
        with the CSG backend but ignored -- the SDF backend builds only the convex polyhedron."""
        _ = faces
        return _s.convex_polyhedron(points, **kwargs)

    def linear_extrude(
        self,
        paths: Any,
        height: float,
        center: bool = False,
        rounding_top: float = 0,
        rounding_bottom: float = 0,
        res: int = 10,
        **kwargs: Any,
    ) -> _s.PyShape:
        """Extrude *paths* into an SDF prism via :func:`~pybosl2._sdf.shapes3d.polygon_prism`.

        *paths* is one outline or a list of DISJOINT outlines -- the SDF prism is the min (union)
        of their fields, so it cannot express holes; a region with holes has no SDF equivalent
        here. The rim treatments (*rounding_top* / *rounding_bottom*) are the SDF backend's own
        extra, the same ones ``offset_sweep`` gives on the CSG side. The native ``linear_extrude``
        options that shear the profile as it rises (``twist``/``scale``/``slices``) have no
        polygon_prism equivalent and are rejected rather than silently ignored.
        """
        from pybosl2.exceptions import UnsupportedByBackendError

        for name in ("twist", "scale", "slices", "convexity"):
            if kwargs.pop(name, None) not in (None, 0, 1, False):
                raise UnsupportedByBackendError(
                    f"linear_extrude({name}=)",
                    "sdf",
                    hint="polygon_prism() extrudes a constant cross-section; build the shape on "
                    "the csg backend for a twisted/tapered extrusion, or sweep it with "
                    "pybosl2._sdf.shapes3d.path_sweep(twist=...).",
                )
        assert not kwargs, f"linear_extrude(): the sdf backend has no {sorted(kwargs)} option(s)."
        shape = _s.polygon_prism(
            paths,
            height,
            rounding_top=rounding_top,
            rounding_bottom=rounding_bottom,
            res=res,
        )
        # polygon_prism sits on z=0; center= lowers it onto the origin like the native extruder.
        return shape.translate([0.0, 0.0, -height / 2.0]) if center else shape

    # -- n-ary CSG (min/max on the fields) -----------------------------------------------------
    def union(self, solids: Any) -> _s.PyShape:
        return _s.union(*solids)

    def difference(self, solids: Any) -> _s.PyShape:
        return _s.difference(*solids)

    def intersection(self, solids: Any) -> _s.PyShape:
        return _s.intersection(*solids)


register_backend("sdf", SdfBackend())

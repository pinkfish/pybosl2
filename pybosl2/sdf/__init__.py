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

import functools
import inspect
from typing import TYPE_CHECKING, Any, Callable, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pybosl2.caps import CapSpec
    from pybosl2.path3d import Path3D

import numpy as np

from pybosl2._backend import SolidBackend, for_backend, refuse_unhonoured, register_backend
from pybosl2.defaults import resolve_res
from pybosl2.exceptions import UnsupportedByBackendError
from pybosl2.sdf import shapes3d as _s

__all__: list[str] = []


def _describes_a_convex_solid(points: Any, faces: Any) -> bool:
    """Report whether *faces* over *points* bound a convex solid.

    The SDF backend builds a polyhedron as the max of its faces' signed half-space distances,
    which can only ever describe a convex solid. For a convex input that is exact and the `faces`
    list is redundant; for anything else the hull is a different shape, so the caller has to be
    told rather than handed the hull (SPEC B-4, B-9).

    A solid is convex exactly when every vertex lies on the inner side of every face's plane.

    Args:
        points: The vertices, as ``[x, y, z]`` triples.
        faces: Vertex indices per face.

    Returns:
        True if the faces bound a convex solid, or if the input is too malformed to judge -- in
        which case the CSG backend's own validation is the right place for the complaint.

    """
    vertices = np.asarray(points, dtype=float)
    if vertices.ndim != 2 or vertices.shape[1] != 3 or len(vertices) < 4:
        return True
    span = float(np.linalg.norm(vertices.max(axis=0) - vertices.min(axis=0))) or 1.0
    tolerance = 1e-7 * span
    centroid = vertices.mean(axis=0)

    for face in faces:
        index = [int(i) for i in face]
        if len(index) < 3 or any(i < 0 or i >= len(vertices) for i in index):
            return True  # malformed: not this backend's complaint to make
        corner = vertices[index[0]]
        normal = None
        for i in range(1, len(index) - 1):
            candidate = np.cross(vertices[index[i]] - corner, vertices[index[i + 1]] - corner)
            length = float(np.linalg.norm(candidate))
            if length > tolerance:
                normal = candidate / length
                break
        if normal is None:
            continue  # a degenerate face bounds nothing
        if float(np.dot(normal, corner - centroid)) < 0:
            normal = -normal  # face planes point outwards
        if float(np.max(vertices @ normal) - float(np.dot(normal, corner))) > tolerance:
            return False  # a vertex outside this face's plane: the solid is not convex
    return True


@functools.lru_cache(maxsize=None)
def _takes_res(constructor: Callable[..., Any]) -> bool:
    """Return True if *constructor* declares a ``res`` parameter (cached per callable)."""
    try:
        return "res" in inspect.signature(constructor).parameters
    except (TypeError, ValueError):  # builtins and other signature-less callables
        return False


class SdfBackend:
    """The libfive/SDF realize backend. Each primitive returns a ``PyShape`` (``backend == "sdf"``)."""

    name = "sdf"

    #: Parameters this backend spells differently from the BOSL2 names the facade uses.
    _OWN_NAMES = {"sides": "num_sides"}

    def constructor(self, shape: str, /) -> Callable[..., _s.PyShape]:
        """Return the pybosl2.sdf.shapes3d constructor for *shape*.

        Args:
            shape: BOSL2 shape name, e.g. ``"cuboid"``.

        Returns:
            The SDF constructor that builds it.

        Raises:
            ValueError: If pybosl2.sdf.shapes3d has no such constructor.
        """
        fn = getattr(_s, shape, None)
        if not callable(fn):
            raise ValueError(f"the sdf backend has no shape constructor {shape!r}")
        return cast("Callable[..., _s.PyShape]", fn)

    def construct(self, shape: str, arguments: Mapping[str, Any]) -> _s.PyShape:
        """Build the named shape via the vendored SDF constructors (pybosl2.sdf.shapes3d).

        A caller who said nothing about sampling resolution gets the ambient one
        (:func:`pybosl2.defaults.use_defaults`), but only for constructors that actually take a
        ``res`` -- the rest never see an argument they have no notion of.
        """
        fn = self.constructor(shape)
        refuse_unhonoured(shape, arguments, fn, "sdf", self._OWN_NAMES)
        named = {self._OWN_NAMES.get(name, name): value for name, value in arguments.items()}
        named = for_backend(fn, named)
        if "res" not in named and _takes_res(fn):
            ambient = resolve_res()
            if ambient is not None:
                named["res"] = ambient
        return fn(**named)

    def polyhedron(self, points: Any, faces: Any = None, convexity: int | None = None) -> _s.PyShape:
        """Return `points` as an SDF, built from its face half-spaces.

        This form can only describe a **convex** solid, so a `faces` list that bounds anything else
        is refused rather than quietly replaced by the hull: the hull of an L-shaped prism fills
        the notch, reports the same bounding box, and nothing downstream notices (SPEC B-4, B-9).

        Raises:
            UnsupportedByBackendError: If *faces* bound a non-convex solid.

        """
        _ = convexity  # a preview hint for the CSG renderer; it does not shape a distance field
        if faces is not None and not _describes_a_convex_solid(points, faces):
            raise UnsupportedByBackendError(
                "polyhedron(faces=)",
                "sdf",
                hint=(
                    "these faces bound a non-convex solid, and an SDF polyhedron is the "
                    "intersection of its face half-spaces, which is always convex -- building it "
                    "here would silently fill the concavities. Build it inside "
                    '`with use_backend("csg")` and bring it over with .to_csg(), or compose the '
                    "shape from SDF primitives and booleans."
                ),
            )
        return _s.convex_polyhedron(points)

    def linear_extrude(self, paths: Any, height: float, arguments: Mapping[str, Any]) -> _s.PyShape:
        """Extrude *paths* into an SDF prism via :func:`~pybosl2.sdf.shapes3d.polygon_prism`.

        *paths* is one outline or a list of DISJOINT outlines -- the SDF prism is the min (union)
        of their fields, so it cannot express holes; a region with holes has no SDF equivalent
        here. The rim treatments (*rounding_top* / *rounding_bottom*) are the SDF backend's own
        extra, the same ones ``offset_sweep`` gives on the CSG side. The native ``linear_extrude``
        options that shear the profile as it rises (``twist``/``scale``/``slices``) have no
        polygon_prism equivalent and are rejected rather than silently ignored.
        """
        from pybosl2.exceptions import UnsupportedByBackendError

        options = dict(arguments)
        center = bool(options.pop("center", False))
        rounding_top = float(options.pop("rounding_top", 0))
        rounding_bottom = float(options.pop("rounding_bottom", 0))
        res = int(options.pop("res", 10))
        for name in ("twist", "scale", "slices", "convexity", "fa", "fn", "fs"):
            if options.pop(name, None) not in (None, 0, 1, False):
                raise UnsupportedByBackendError(
                    f"linear_extrude({name}=)",
                    "sdf",
                    hint="polygon_prism() extrudes a constant cross-section; build the shape on "
                    "the csg backend for a twisted/tapered extrusion, or sweep it with "
                    "pybosl2.sdf.shapes3d.path_sweep(twist=...).",
                )
        if options:
            raise ValueError(f"linear_extrude(): the sdf backend has no {sorted(options)} option(s).")
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
        return _s.PyShape.union(*solids)

    def difference(self, solids: Any) -> _s.PyShape:
        return _s.PyShape.difference(*solids)

    def stroke(
        self,
        path: Path3D,
        width: float = 1,
        closed: bool | None = None,
        endcap1: CapSpec | None = None,
        endcap2: CapSpec | None = None,
    ) -> _s.PyShape:
        """3-D stroke via the SDF backend's own cylinder/sphere primitives."""
        return _s.stroke_3d(path, width=width, closed=closed, endcap1=endcap1, endcap2=endcap2)

    def intersection(self, solids: Any) -> _s.PyShape:
        return _s.PyShape.intersection(*solids)


register_backend("sdf", cast("SolidBackend", SdfBackend()))

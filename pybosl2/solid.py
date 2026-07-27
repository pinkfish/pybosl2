# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# The backend-neutral solid facade: unified shape constructors that build on whichever backend is
# active (``"csg"`` by default, ``"sdf"`` under ``use_backend("sdf")``). Each returns a common
# :class:`~pybosl2._backend.Solid` -- a Bosl2Solid on the CSG backend, a PyShape on the SDF backend --
# so the same code realizes exact CSG or an F-Rep/signed-distance field depending on context:
#
#     from pybosl2.solid import sphere, use_backend
#     a = sphere(radius=10)                 # CSG (default) -> Bosl2Solid
#     with use_backend("sdf"):
#         b = sphere(radius=10)             # libfive SDF   -> PyShape
#
# The shape constructors below are the 3-D primitives BOTH backends expose; each dispatches by name
# through the active backend's ``construct``. n-ary CSG (union/difference/intersection) dispatches to
# the backend's own operators. The backend-specific modules (pybosl2.shapes3d, pybosl2._sdf) remain
# directly importable for anything not yet unified here.

from __future__ import annotations

from typing import Any

from pybosl2._backend import (
    Solid,
    current_backend,
    get_backend,
    set_default_backend,
    use_backend,
)
from pybosl2.exceptions import CrossBackendError, UnsupportedByBackendError

# 3-D constructors both the CSG (pybosl2.shapes3d) and SDF (pybosl2._sdf.shapes3d) backends provide.
_SHARED_3D = (
    "cube",
    "cuboid",
    "cyl",
    "cylinder",
    "octahedron",
    "onion",
    "pie_slice",
    "prismoid",
    "rect_tube",
    "regular_prism",
    "sphere",
    "spheroid",
    "teardrop",
    "torus",
    "tube",
    "wedge",
    "xcyl",
    "ycyl",
    "zcyl",
)

__all__ = [
    *_SHARED_3D,
    "polyhedron",
    "union",
    "difference",
    "intersection",
    # backend controls, re-exported for convenience
    "use_backend",
    "set_default_backend",
    "current_backend",
    "Solid",
    "CrossBackendError",
    "UnsupportedByBackendError",
]


def _make(shape: str):
    def _ctor(*args: Any, **kwargs: Any) -> Solid:
        return get_backend().construct(shape, *args, **kwargs)

    _ctor.__name__ = _ctor.__qualname__ = shape
    _ctor.__doc__ = (
        f"A ``{shape}`` on the active backend (CSG -> Bosl2Solid, SDF -> PyShape). "
        f"See :func:`use_backend`; identical call, backend-appropriate realization."
    )
    return _ctor


for _shape in _SHARED_3D:
    globals()[_shape] = _make(_shape)
del _shape


def polyhedron(points: Any, faces: Any = None, **kwargs: Any) -> Solid:
    """A polyhedron on the active backend.

    Backends differ on what a polyhedron means (this is not part of the shared primitive surface):
    the CSG backend builds the exact mesh from *points* and *faces* (both required); the SDF backend
    ignores *faces* and builds the convex hull of *points* as a distance field.
    """
    return get_backend().polyhedron(points, faces, **kwargs)


def union(*solids: Solid) -> Solid:
    """The union of *solids* on the active backend (all operands must share the active backend)."""
    return get_backend().union(solids)


def difference(*solids: Solid) -> Solid:
    """The first solid minus the rest, on the active backend."""
    return get_backend().difference(solids)


def intersection(*solids: Solid) -> Solid:
    """The intersection of *solids* on the active backend."""
    return get_backend().intersection(solids)

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# DocCategory: Foundational
# LibFile: pybosl2/solid.py
# FileSummary: Statically typed shape constructors and backend-neutral solid facade.
# FileGroup: BOSL2

"""Statically typed shape constructors and backend-neutral solid facade."""

# The backend-neutral solid facade: unified shape constructors that build on whichever backend is
# active (``"csg"`` by default, ``"sdf"`` under ``use_backend("sdf")``). Each returns a common
# :class:`~pybosl2._backend.Solid` -- a CsgSolid on the CSG backend, an SdfSolid on the SDF backend --
# so the same code realizes exact CSG or an F-Rep/signed-distance field depending on context:
#
#     from pybosl2.solid import sphere, use_backend
#     a = sphere(radius=10)                 # CSG (default) -> CsgSolid
#     with use_backend("sdf"):
#         b = sphere(radius=10)             # libfive SDF   -> SdfSolid
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


def cube(*args: Any, **kwargs: Any) -> Solid:
    """Return a cube on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("cube", *args, **kwargs)


def cuboid(*args: Any, **kwargs: Any) -> Solid:
    """Return a cuboid on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("cuboid", *args, **kwargs)


def cyl(*args: Any, **kwargs: Any) -> Solid:
    """Return a cyl on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("cyl", *args, **kwargs)


def cylinder(*args: Any, **kwargs: Any) -> Solid:
    """Return a cylinder on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("cylinder", *args, **kwargs)


def octahedron(*args: Any, **kwargs: Any) -> Solid:
    """Return an octahedron on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("octahedron", *args, **kwargs)


def onion(*args: Any, **kwargs: Any) -> Solid:
    """Return an onion on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("onion", *args, **kwargs)


def pie_slice(*args: Any, **kwargs: Any) -> Solid:
    """Return a pie_slice on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("pie_slice", *args, **kwargs)


def prismoid(*args: Any, **kwargs: Any) -> Solid:
    """Return a prismoid on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("prismoid", *args, **kwargs)


def rect_tube(*args: Any, **kwargs: Any) -> Solid:
    """Return a rect_tube on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("rect_tube", *args, **kwargs)


def regular_prism(*args: Any, **kwargs: Any) -> Solid:
    """Return a regular_prism on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("regular_prism", *args, **kwargs)


def sphere(*args: Any, **kwargs: Any) -> Solid:
    """Return a sphere on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("sphere", *args, **kwargs)


def spheroid(*args: Any, **kwargs: Any) -> Solid:
    """Return a spheroid on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("spheroid", *args, **kwargs)


def teardrop(*args: Any, **kwargs: Any) -> Solid:
    """Return a teardrop on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("teardrop", *args, **kwargs)


def torus(*args: Any, **kwargs: Any) -> Solid:
    """Return a torus on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("torus", *args, **kwargs)


def tube(*args: Any, **kwargs: Any) -> Solid:
    """Return a tube on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("tube", *args, **kwargs)


def wedge(*args: Any, **kwargs: Any) -> Solid:
    """Return a wedge on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("wedge", *args, **kwargs)


def xcyl(*args: Any, **kwargs: Any) -> Solid:
    """Return an xcyl on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("xcyl", *args, **kwargs)


def ycyl(*args: Any, **kwargs: Any) -> Solid:
    """Return a ycyl on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("ycyl", *args, **kwargs)


def zcyl(*args: Any, **kwargs: Any) -> Solid:
    """Return a zcyl on the active backend.

    See :func:`use_backend`; identical call, backend-appropriate realization.
    """
    return get_backend().construct("zcyl", *args, **kwargs)


def polyhedron(points: Any, faces: Any = None, **kwargs: Any) -> Solid:
    """Return a polyhedron on the active backend.

    Backends differ on what a polyhedron means (this is not part of the shared primitive surface):
    the CSG backend builds the exact mesh from *points* and *faces* (both required); the SDF backend
    ignores *faces* and builds the convex hull of *points* as a distance field.
    """
    return get_backend().polyhedron(points, faces, **kwargs)


def union(*solids: Solid) -> Solid:
    """Return the union of *solids* on the active backend (all operands must share the active backend)."""
    return get_backend().union(solids)


def difference(*solids: Solid) -> Solid:
    """Return the first solid minus the rest, on the active backend."""
    return get_backend().difference(solids)


def intersection(*solids: Solid) -> Solid:
    """Return the intersection of *solids* on the active backend."""
    return get_backend().intersection(solids)

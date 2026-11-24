# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Compare a CSG solid against an SDF field, pointwise (SPEC PAR-1, B2-1).

This campaign has deferred work at least four times on one sentence: *libfive is stubbed, so an SDF
solid meshes to nothing and only its analytic box can be read.* The first clause is true. The rest
is not, and T119 measured it:

* `SdfSolid.inside()` answers **correctly**, not `False` everywhere. A sphere of radius 7 says
  `True` at (3.9, 3.9, 3.9) and `False` at (4.1, 4.1, 4.1); a drilled cube says `False` down the
  hole and `True` beside it. It reads the field, not the box.
* The field itself evaluates to **exact** signed distances. `shape._sdf_fn(lv.x(), lv.y(), lv.z())`
  is a symbolic tree, and calling it at a point gives the distance -- 2-D and 3-D alike.

So cross-backend geometry is measurable here, and it never had to be guessed. That matters because
the campaign's own notes record a bounding box hiding a shape difference four separate times, and a
box was the only thing these comparisons were using.

The comparison is one-sided on purpose. A CSG solid is a mesh and an SDF solid is a field, so the
two can only be compared where both are defined: at the mesh's vertices. A tessellation of a curved
surface **inscribes** it, so a vertex sitting *inside* the field is faceting and shrinks as the
facet count rises -- a rounded cylinder measures 0.2087 in at the default, then 0.0990, 0.0255,
0.0064 and 0.0016 as `fn` doubles from 16, which is the quadratic convergence of an inscribed
polygon. Every one of the 23 solids both backends build reads exactly 0.000000 on the outside, so
"no vertex escapes the field" is a scale-free claim needing no tolerance, and the bent `path_sweep`
breaks it by +0.3162.

**Where the one-sidedness stops holding, measured (T122).** "A vertex outside the field cannot be
faceting" is a statement about one surface's own tessellation, and it does not survive a boolean. A
union re-triangulates, and the vertices it creates lie on neither input surface: two helical ridges
whose base rings are each at exactly radius 6.00000 union to a mesh whose base ring reaches
5.94867 -- half a polygon step inside, which an exact field reads as empty space. Such a vertex is
still a facet artifact and still converges as 1/fn^2; it simply converges from the *outside*. So
for a composed part the question has to be asked by refining the mesh and seeing whether the
departure goes away (`tests/test_every_part_field_evaluates.py`), and four of the six
"disagreements" that file recorded turned out to be this. For a primitive, which is what the 23
above are, the figure is zero and the sharp claim stands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import numpy as np

from pybosl2 import use_backend
from pybosl2.sdf._libfive import lv

if TYPE_CHECKING:
    from collections.abc import Callable


def csg_vertices(build: "Callable[[], Any]") -> "np.ndarray[Any, Any]":
    """Return the vertices of the CSG solid *build* makes.

    Args:
        build: a zero-argument callable returning a CSG solid.

    Returns:
        An ``(n, 3)`` array of vertices.

    """
    with use_backend("csg"):
        solid = build()
        vnf = solid.vnf() if callable(getattr(solid, "vnf", None)) else solid
    vertices = getattr(vnf, "vertices", None)
    if vertices is None:
        vertices = vnf.points
    return np.asarray(vertices, dtype=float)


def distances(build: "Callable[[], Any]", points: "np.ndarray[Any, Any]") -> "np.ndarray[Any, Any]":
    """Return the SDF field of *build* evaluated at each of *points*.

    Negative is inside the solid, positive outside, zero on the surface.

    Args:
        build: a zero-argument callable returning an SDF solid.
        points: an ``(n, 3)`` array of points.

    Returns:
        An ``(n,)`` array of signed distances.

    """
    with use_backend("sdf"):
        field = build()
    tree = field._sdf_fn(lv.x(), lv.y(), lv.z())
    return np.asarray([float(cast("Any", tree)(float(p[0]), float(p[1]), float(p[2]))) for p in points])


def worst_escape(csg_build: "Callable[[], Any]", sdf_build: "Callable[[], Any]") -> tuple[float, float, "list[float]"]:
    """Compare the two builds at the CSG mesh's vertices.

    Args:
        csg_build: builds the CSG solid whose vertices are the sample points.
        sdf_build: builds the SDF solid whose field is sampled.

    Returns:
        ``(furthest outside, furthest inside, the worst point)``. The first is the one that matters:
        a primitive's own tessellation can only inscribe, so anything above zero is a genuine
        disagreement -- see the module docstring for the one thing that is not a primitive's own
        tessellation, and what to do about it.

    """
    points = csg_vertices(csg_build)
    found = distances(sdf_build, points)
    outside, inside = float(found.max()), float(found.min())
    worst = points[int(np.argmax(found))]
    return outside, inside, [float(v) for v in worst]

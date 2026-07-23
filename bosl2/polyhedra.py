# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/polyhedra.py
#    The five Platonic solids from BOSL2's polyhedra.scad, built as watertight polyhedra.
#    :meth:`Polyhedra.regular_polyhedron` builds any of ``"tetrahedron"``, ``"cube"``,
#    ``"octahedron"``, ``"dodecahedron"`` or ``"icosahedron"`` (there are named convenience methods
#    too), sized by circumradius, diameter, inradius, or side length.
#    :meth:`~Polyhedra.regular_polyhedron_info` returns the vertex/face data.
#
#    The Archimedean, Catalan and stellated families from the full BOSL2 module are not ported.
#
# FileSummary: The five Platonic solids as watertight polyhedra.
# FileGroup: BOSL2

from __future__ import annotations

import math

import numpy as np

from bosl2.shapes3d import Bosl2Solid
from bosl2.vnf import VNF

__all__ = ["Polyhedra"]

_PHI = (1 + math.sqrt(5)) / 2


def _normalize(verts):
    """Scale a vertex list so its circumradius (max |v|) is 1."""
    arr = np.asarray(verts, dtype=float)
    return (arr / np.linalg.norm(arr, axis=1).max()).tolist()


def _dual(verts, faces):
    """The dual polyhedron: new vertices are the (normalized) face centroids, new faces are the
    rings of faces around each original vertex. Used to derive the dodecahedron from the icosahedron."""
    V = np.asarray(verts, dtype=float)
    centroids = np.array([V[f].mean(axis=0) for f in faces])
    centroids = centroids / np.linalg.norm(centroids, axis=1)[:, None]
    newfaces = []
    for vi in range(len(V)):
        adj = [fi for fi, f in enumerate(faces) if vi in f]
        n = V[vi] / np.linalg.norm(V[vi])
        t = np.cross(n, [0, 0, 1.0])
        if np.linalg.norm(t) < 1e-6:
            t = np.cross(n, [0, 1.0, 0])
        t = t / np.linalg.norm(t)
        b = np.cross(n, t)

        def ang(fi):
            d = centroids[fi] - n * float(np.dot(centroids[fi], n))
            return math.atan2(float(np.dot(d, b)), float(np.dot(d, t)))

        newfaces.append(sorted(adj, key=ang))
    return centroids.tolist(), newfaces


# --- the five Platonic solids, unit circumradius -----------------------------

_TETRA_V = _normalize([(1, 1, 1), (-1, -1, 1), (-1, 1, -1), (1, -1, -1)])
_TETRA_F = [[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]]

_CUBE_V = _normalize(
    [
        (-1, -1, -1),
        (1, -1, -1),
        (1, 1, -1),
        (-1, 1, -1),
        (-1, -1, 1),
        (1, -1, 1),
        (1, 1, 1),
        (-1, 1, 1),
    ]
)
_CUBE_F = [
    [0, 1, 2, 3],
    [4, 7, 6, 5],
    [0, 4, 5, 1],
    [1, 5, 6, 2],
    [2, 6, 7, 3],
    [3, 7, 4, 0],
]

_OCTA_V = _normalize(
    [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
)
_OCTA_F = [
    [4, 0, 2],
    [4, 2, 1],
    [4, 1, 3],
    [4, 3, 0],
    [5, 2, 0],
    [5, 1, 2],
    [5, 3, 1],
    [5, 0, 3],
]

_ICOSA_V = _normalize(
    [
        (-1, _PHI, 0),
        (1, _PHI, 0),
        (-1, -_PHI, 0),
        (1, -_PHI, 0),
        (0, -1, _PHI),
        (0, 1, _PHI),
        (0, -1, -_PHI),
        (0, 1, -_PHI),
        (_PHI, 0, -1),
        (_PHI, 0, 1),
        (-_PHI, 0, -1),
        (-_PHI, 0, 1),
    ]
)
_ICOSA_F = [
    [0, 11, 5],
    [0, 5, 1],
    [0, 1, 7],
    [0, 7, 10],
    [0, 10, 11],
    [1, 5, 9],
    [5, 11, 4],
    [11, 10, 2],
    [10, 7, 6],
    [7, 1, 8],
    [3, 9, 4],
    [3, 4, 2],
    [3, 2, 6],
    [3, 6, 8],
    [3, 8, 9],
    [4, 9, 5],
    [2, 4, 11],
    [6, 2, 10],
    [8, 6, 7],
    [9, 8, 1],
]

_DODECA_V, _DODECA_F = _dual(_ICOSA_V, _ICOSA_F)

# name -> (unit-circumradius vertices, faces, circumradius/side ratio, aliases)
_SOLIDS = {
    "tetrahedron": (_TETRA_V, _TETRA_F, math.sqrt(6) / 4),
    "cube": (_CUBE_V, _CUBE_F, math.sqrt(3) / 2),
    "octahedron": (_OCTA_V, _OCTA_F, math.sqrt(2) / 2),
    "dodecahedron": (_DODECA_V, _DODECA_F, math.sqrt(3) / 4 * (1 + math.sqrt(5))),
    "icosahedron": (_ICOSA_V, _ICOSA_F, math.sqrt(10 + 2 * math.sqrt(5)) / 4),
}
_ALIASES = {
    "tetra": "tetrahedron",
    "hexahedron": "cube",
    "hex": "cube",
    "octa": "octahedron",
    "dodeca": "dodecahedron",
    "icosa": "icosahedron",
}


def _inradius_ratio(name):
    """Inradius / circumradius for the unit solid (min face-plane distance)."""
    verts, faces, _ = _SOLIDS[name]
    V = np.asarray(verts)
    return min(float(np.linalg.norm(V[f].mean(axis=0))) for f in faces)


class Polyhedra:
    """The five Platonic solids (BOSL2 polyhedra.scad, Platonic subset)."""

    @staticmethod
    def _resolve(name):
        key = _ALIASES.get(str(name).lower(), str(name).lower())
        if key not in _SOLIDS:
            raise ValueError(
                f"unknown polyhedron {name!r}; expected one of {sorted(_SOLIDS)}"
            )
        return key

    @staticmethod
    def regular_polyhedron_info(name: str) -> dict:
        """The named solid's vertex/face data and counts (BOSL2 regular_polyhedron_info())."""
        key = Polyhedra._resolve(name)
        verts, faces, _ratio = _SOLIDS[key]
        return {
            "name": key,
            "vertices": [list(v) for v in verts],
            "faces": [list(f) for f in faces],
            "num_vertices": len(verts),
            "num_faces": len(faces),
        }

    @staticmethod
    def regular_polyhedron(
        name: str = "cube",
        r: float | None = None,
        d: float | None = None,
        ir: float | None = None,
        side: float | None = None,
    ) -> Bosl2Solid:
        """A Platonic solid, sized by circumradius *r*, diameter *d*, inradius *ir*, or *side* (BOSL2 regular_polyhedron()).

        *name* is ``tetrahedron`` / ``cube`` / ``octahedron`` / ``dodecahedron`` / ``icosahedron``
        (short aliases accepted). Defaults to circumradius 1.

        Examples:
            A dodecahedron:

            .. pythonscad-example::

                from bosl2.polyhedra import Polyhedra
                Polyhedra.regular_polyhedron("dodecahedron", side=12).show()
        """
        key = Polyhedra._resolve(name)
        verts, faces, ratio = _SOLIDS[key]
        if side is not None:
            scale = side * ratio  # circumradius for the requested side
        elif d is not None:
            scale = d / 2
        elif ir is not None:
            scale = ir / _inradius_ratio(key)  # circumradius from the inradius
        elif r is not None:
            scale = r
        else:
            scale = 1.0
        sv = [[x * scale, y * scale, z * scale] for x, y, z in verts]
        solid = VNF(sv, faces).polyhedron()
        return Bosl2Solid(solid, size=[2 * scale, 2 * scale, 2 * scale])

    @staticmethod
    def tetrahedron(**kw) -> Bosl2Solid:
        """A regular tetrahedron (4 triangular faces)."""
        return Polyhedra.regular_polyhedron("tetrahedron", **kw)

    @staticmethod
    def cube(**kw) -> Bosl2Solid:
        """A cube / regular hexahedron (6 square faces)."""
        return Polyhedra.regular_polyhedron("cube", **kw)

    @staticmethod
    def octahedron(**kw) -> Bosl2Solid:
        """A regular octahedron (8 triangular faces)."""
        return Polyhedra.regular_polyhedron("octahedron", **kw)

    @staticmethod
    def dodecahedron(**kw) -> Bosl2Solid:
        """A regular dodecahedron (12 pentagonal faces)."""
        return Polyhedra.regular_polyhedron("dodecahedron", **kw)

    @staticmethod
    def icosahedron(**kw) -> Bosl2Solid:
        """A regular icosahedron (20 triangular faces)."""
        return Polyhedra.regular_polyhedron("icosahedron", **kw)

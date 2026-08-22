# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/parts/polyhedra.py
#    The five Platonic solids from BOSL2's polyhedra.scad, built as watertight polyhedra.
#    :class:`RegularPolyhedron` builds any :class:`PlatonicSolid`, sized by
#    circumradius, diameter, inradius, or side length (there are named convenience methods
#    too). :class:`PolyhedronInfo` returns vertex/face data.
#
#    The Archimedean, Catalan and stellated families from the full BOSL2 module are not ported.
#
# FileSummary: The five Platonic solids as watertight polyhedra.
# DocCategory: Parts library
# FileGroup: BOSL2

"""The five Platonic solids as watertight polyhedra."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import numpy as np

from pybosl2.vnf import VNF

if TYPE_CHECKING:
    from pybosl2._backend import Solid

__all__ = ["RegularPolyhedron", "PolyhedronInfo", "PlatonicSolid"]


class PlatonicSolid(StrEnum):
    """Platonic solid type."""

    TETRAHEDRON = "tetrahedron"
    CUBE = "cube"
    OCTAHEDRON = "octahedron"
    DODECAHEDRON = "dodecahedron"
    ICOSAHEDRON = "icosahedron"


_PHI = (1 + math.sqrt(5)) / 2


def _normalize(verts: list[tuple[float, float, float]]) -> list[list[float]]:
    """Scale a vertex list so its circumradius (max |v|) is 1."""
    arr = np.asarray(verts, dtype=float)
    return (arr / np.linalg.norm(arr, axis=1).max()).tolist()  # type: ignore[no-any-return]


def _dual(
    verts: list[list[float]],
    faces: list[list[int]],
) -> tuple[list[list[float]], list[list[int]]]:
    """Return the dual polyhedron: new vertices are the (normalized) face centroids, new faces are the.

    rings of faces around each original vertex. Used to derive the dodecahedron from the icosahedron.
    """
    verts_arr = np.asarray(verts, dtype=float)
    centroids = np.array([verts_arr[f].mean(axis=0) for f in faces])
    centroids = centroids / np.linalg.norm(centroids, axis=1)[:, None]
    newfaces = []
    for vi in range(len(verts_arr)):
        adj = [fi for fi, f in enumerate(faces) if vi in f]
        sides = verts_arr[vi] / np.linalg.norm(verts_arr[vi])
        t = np.cross(sides, [0, 0, 1.0])
        if np.linalg.norm(t) < 1e-6:
            t = np.cross(sides, [0, 1.0, 0])
        t = t / np.linalg.norm(t)
        b = np.cross(sides, t)

        def angle(fi: int, sides: "np.ndarray" = sides, b: "np.ndarray" = b, t: "np.ndarray" = t) -> float:
            diameter = centroids[fi] - sides * float(np.dot(centroids[fi], sides))
            return math.atan2(float(np.dot(diameter, b)), float(np.dot(diameter, t)))

        newfaces.append(sorted(adj, key=angle))
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

_OCTA_V = _normalize([(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)])
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

# PlatonicSolid -> (unit-circumradius vertices, faces, circumradius/side ratio)
_SOLIDS: dict[PlatonicSolid, tuple[list[list[float]], list[list[int]], float]] = {
    PlatonicSolid.TETRAHEDRON: (_TETRA_V, _TETRA_F, math.sqrt(6) / 4),
    PlatonicSolid.CUBE: (_CUBE_V, _CUBE_F, math.sqrt(3) / 2),
    PlatonicSolid.OCTAHEDRON: (_OCTA_V, _OCTA_F, math.sqrt(2) / 2),
    PlatonicSolid.DODECAHEDRON: (_DODECA_V, _DODECA_F, math.sqrt(3) / 4 * (1 + math.sqrt(5))),
    PlatonicSolid.ICOSAHEDRON: (_ICOSA_V, _ICOSA_F, math.sqrt(10 + 2 * math.sqrt(5)) / 4),
}


def _inradius_ratio(name: PlatonicSolid) -> float:
    """Inradius / circumradius for the unit solid (min face-plane distance)."""
    verts, faces, _ = _SOLIDS[name]
    verts_arr = np.asarray(verts)
    return min(float(np.linalg.norm(verts_arr[f].mean(axis=0))) for f in faces)


# ---------------------------------------------------------------------------
# Section: public API
# ---------------------------------------------------------------------------


@dataclass
class PolyhedronInfo:
    """Vertex and face data for a Platonic solid.

    The constructor takes a :class:`PlatonicSolid` enum and looks up the
    geometry, equivalent to the old ``Polyhedra.regular_polyhedron_info()``.
    """

    name: str
    vertices: list[list[float]]
    faces: list[list[int]]
    num_vertices: int
    num_faces: int

    def __init__(self, solid: PlatonicSolid) -> None:
        """Look up vertex/face data for the given Platonic solid.

        Args:
            solid: A :class:`PlatonicSolid` enum value identifying the polyhedron.

        Returns:
            None.

        """
        verts, faces, _ratio = _SOLIDS[solid]
        self.name = solid.value
        self.vertices = [list(v) for v in verts]
        self.faces = [list(f) for f in faces]
        self.num_vertices = len(verts)
        self.num_faces = len(faces)


class RegularPolyhedron:
    """A regular Platonic solid, sized by circumradius, diameter, inradius, or side.

    *name* is a :class:`PlatonicSolid` enum.  The convenience class methods
    :meth:`tetrahedron`, :meth:`cube`, :meth:`octahedron`, :meth:`dodecahedron`
    and :meth:`icosahedron` construct the corresponding solid without requiring
    the enum.

    Examples:
        A dodecahedron:

        .. pythonscad-example::

            from pybosl2.parts.polyhedra import RegularPolyhedron, PlatonicSolid
            RegularPolyhedron(PlatonicSolid.DODECAHEDRON, side=12).show()

    """

    def __init__(
        self,
        name: PlatonicSolid = PlatonicSolid.CUBE,
        radius: float | None = None,
        diameter: float | None = None,
        inner_radius: float | None = None,
        side: float | None = None,
    ) -> None:
        """Create a regular polyhedron, sized by one of radius/diameter/inradius/side.

        Args:
            name: A :class:`PlatonicSolid` enum value identifying the polyhedron type.
            radius: Circumscribing sphere radius.
            diameter: Circumscribing sphere diameter.
            inner_radius: Insphere radius (distance from centre to mid-face).
            side: Edge length.

        Returns:
            None.

        Raises:
            KeyError: If *name* is not a valid Platonic solid.

        """
        _ = _SOLIDS[name]  # validate early
        self._name: PlatonicSolid = name
        self._radius: float | None = radius
        self._diameter: float | None = diameter
        self._inner_radius: float | None = inner_radius
        self._side: float | None = side
        self._solid: "Solid" | None = None

    @property
    def name(self) -> PlatonicSolid:
        """The Platonic solid type."""
        return self._name

    def info(self) -> PolyhedronInfo:
        """Return vertex/face data for this solid.

        Returns:
            A :class:`PolyhedronInfo` object containing vertex and face lists.

        """
        return PolyhedronInfo(self._name)

    @property
    def shape(self) -> "Solid":
        """Build and return the polyhedron geometry (cached)."""
        if self._solid is not None:
            return self._solid
        verts, faces, ratio = _SOLIDS[self._name]
        if self._side is not None:
            scale = self._side * ratio
        elif self._diameter is not None:
            scale = self._diameter / 2
        elif self._inner_radius is not None:
            scale = self._inner_radius / _inradius_ratio(self._name)
        elif self._radius is not None:
            scale = self._radius
        else:
            scale = 1.0
        sv = [[x * scale, y * scale, z * scale] for x, y, z in verts]
        solid = VNF(sv, faces).polyhedron()
        # Nominal anchor box: the circumsphere, as BOSL2's regular_polyhedron() anchors. Every
        # Platonic solid sits strictly inside its circumsphere except at the vertices, so this is
        # larger than bounds() -- a cube of circumradius 1 measures 2/sqrt(3) across.
        self._solid = solid.with_nominal_size([2 * scale, 2 * scale, 2 * scale])
        return self._solid

    def show(self) -> Any:
        """Display the polyhedron in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self.shape.show()

    @classmethod
    def tetrahedron(
        cls,
        radius: float | None = None,
        diameter: float | None = None,
        inner_radius: float | None = None,
        side: float | None = None,
    ) -> RegularPolyhedron:
        """Return a regular tetrahedron (4 triangular faces).

        Args:
            radius: Circumscribing sphere radius.
            diameter: Circumscribing sphere diameter.
            inner_radius: Insphere radius (distance from centre to mid-face).
            side: Edge length.

        Returns:
            A :class:`RegularPolyhedron` configured as a tetrahedron.

        """
        return cls(PlatonicSolid.TETRAHEDRON, radius=radius, diameter=diameter, inner_radius=inner_radius, side=side)

    @classmethod
    def cube(
        cls,
        radius: float | None = None,
        diameter: float | None = None,
        inner_radius: float | None = None,
        side: float | None = None,
    ) -> RegularPolyhedron:
        """Return a cube / regular hexahedron (6 square faces).

        Args:
            radius: Circumscribing sphere radius.
            diameter: Circumscribing sphere diameter.
            inner_radius: Insphere radius (distance from centre to mid-face).
            side: Edge length.

        Returns:
            A :class:`RegularPolyhedron` configured as a cube.

        """
        return cls(PlatonicSolid.CUBE, radius=radius, diameter=diameter, inner_radius=inner_radius, side=side)

    @classmethod
    def octahedron(
        cls,
        radius: float | None = None,
        diameter: float | None = None,
        inner_radius: float | None = None,
        side: float | None = None,
    ) -> RegularPolyhedron:
        """Return a regular octahedron (8 triangular faces).

        Args:
            radius: Circumscribing sphere radius.
            diameter: Circumscribing sphere diameter.
            inner_radius: Insphere radius (distance from centre to mid-face).
            side: Edge length.

        Returns:
            A :class:`RegularPolyhedron` configured as an octahedron.

        """
        return cls(PlatonicSolid.OCTAHEDRON, radius=radius, diameter=diameter, inner_radius=inner_radius, side=side)

    @classmethod
    def dodecahedron(
        cls,
        radius: float | None = None,
        diameter: float | None = None,
        inner_radius: float | None = None,
        side: float | None = None,
    ) -> RegularPolyhedron:
        """Return a regular dodecahedron (12 pentagonal faces).

        Args:
            radius: Circumscribing sphere radius.
            diameter: Circumscribing sphere diameter.
            inner_radius: Insphere radius (distance from centre to mid-face).
            side: Edge length.

        Returns:
            A :class:`RegularPolyhedron` configured as a dodecahedron.

        """
        return cls(PlatonicSolid.DODECAHEDRON, radius=radius, diameter=diameter, inner_radius=inner_radius, side=side)

    @classmethod
    def icosahedron(
        cls,
        radius: float | None = None,
        diameter: float | None = None,
        inner_radius: float | None = None,
        side: float | None = None,
    ) -> RegularPolyhedron:
        """Return a regular icosahedron (20 triangular faces).

        Args:
            radius: Circumscribing sphere radius.
            diameter: Circumscribing sphere diameter.
            inner_radius: Insphere radius (distance from centre to mid-face).
            side: Edge length.

        Returns:
            A :class:`RegularPolyhedron` configured as an icosahedron.

        Examples:
            .. pythonscad-example::

                from pybosl2.parts.polyhedra import RegularPolyhedron
                RegularPolyhedron.icosahedron(side=20).show()

        """
        return cls(PlatonicSolid.ICOSAHEDRON, radius=radius, diameter=diameter, inner_radius=inner_radius, side=side)

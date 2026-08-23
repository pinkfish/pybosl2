# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/parts/walls.py
#    Pure-Python port of BOSL2's walls.scad: FDM-optimised wall shapes that use less material and
#    print without support. :class:`SparseWall` is an X-braced open wall (and
#    :class:`~SparseCuboid` its solid-box variant); :class:`~CorrugatedWall` a sinusoidal
#    corrugated panel; :class:`~ThinningWall` / :class:`~ThinningTriangle` walls whose
#    middle thins away while the edges stay thick; :class:`~NarrowingStrut` the home-plate strut
#    those triangles are built from.
#
#    The honeycomb hex_panel() is not ported.
#
# FileSummary: FDM-optimised walls: sparse, corrugated, thinning and struts.
# DocCategory: Parts library
# FileGroup: BOSL2

"""FDM-optimised walls: sparse, corrugated, thinning and struts."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import numpy as np

from pybosl2._backend import csg_part
from pybosl2._helpers import frag_count as _segs
from pybosl2._helpers import union as _union
from pybosl2._native import native
from pybosl2.path2d import Path2D
from pybosl2.solid import cuboid
from pybosl2.vnf import VNF

if TYPE_CHECKING:
    from pybosl2._backend import Solid

_opolygon = native("polygon")

__all__ = [
    "CorrugatedWall",
    "NarrowingStrut",
    "SparseCuboid",
    "SparseWall",
    "SparseAxis",
    "ThinningTriangle",
    "ThinningWall",
]


class SparseAxis(StrEnum):
    """Axis for :class:`SparseCuboid` internal bracing."""

    X = "X"
    Y = "Y"
    Z = "Z"


def _rect(x0: float, x1: float, y0: float, y1: float) -> list[list[float]]:
    """Return an axis-aligned rectangle outline from two opposite corners."""
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def _circle_2tangents(r: float, p1: list[float], p2: list[float], p3: list[float]) -> list[float]:
    """Centre of the circle of radius *r* tangent to segments p2->p1 and p2->p3 (BOSL2.

    circle_2tangents()[0]); the corner is at *p2*. Points are 3-vectors (the y component is 0 here).
    """
    p1a, p2a, p3a = (np.asarray(p, dtype=float) for p in (p1, p2, p3))
    v1 = (p1a - p2a) / np.linalg.norm(p1a - p2a)
    v2 = (p3a - p2a) / np.linalg.norm(p3a - p2a)
    bis = v1 + v2
    bis = bis / np.linalg.norm(bis)
    half = math.acos(float(np.clip(np.dot(v1, v2), -1.0, 1.0))) / 2
    return (p2a + bis * (r / math.sin(half))).tolist()  # type: ignore[no-any-return]


def _sparse_wall2d(h: float, length: float, maxang: float, strut: float, max_bridge: float) -> list[list[list[float]]]:
    """Return the 2-D cross-braced pattern as a list of outlines, in the (X=h, Y=length) plane.

    Outlines rather than a 2-D region (BOSL2 sparse_wall2d() unions them): a region is CSG-only,
    and extruding the union of overlapping outlines is the same solid as the union of their
    extrusions, so the caller extrudes each and unions in 3-D. That is what lets the wall build on
    either backend (TASKS T14).
    """
    zoff = h / 2 - strut / 2
    yoff = length / 2 - strut / 2
    maxa = math.radians(maxang)
    maxhyp = 1.5 * (max_bridge + strut) / 2 / math.sin(maxa)
    maxz = 2 * maxhyp * math.cos(maxa)
    zreps = math.ceil(2 * zoff / maxz)
    zstep = 2 * zoff / zreps
    hyp = zstep / 2 / math.cos(maxa)
    maxy = min(2 * hyp * math.sin(maxa), max_bridge + strut)
    yreps = math.ceil(2 * yoff / maxy)
    ystep = 2 * yoff / yreps
    angle = math.atan(ystep / zstep)

    parts = [
        _rect(-h / 2, -h / 2 + strut, -length / 2, length / 2),
        _rect(h / 2 - strut, h / 2, -length / 2, length / 2),
        _rect(-h / 2, h / 2, -length / 2, -length / 2 + strut),
        _rect(-h / 2, h / 2, length / 2 - strut, length / 2),
    ]
    wx = (h - strut) / zreps
    wy = strut / math.cos(angle)
    for iy in range(yreps):
        vpos = (iy - (yreps - 1) / 2) * ystep
        for jx in range(zreps):
            upos = (jx - (zreps - 1) / 2) * zstep
            for syx in (math.tan(-angle), math.tan(angle)):
                corners = [
                    (-wx / 2, -wy / 2),
                    (wx / 2, -wy / 2),
                    (wx / 2, wy / 2),
                    (-wx / 2, wy / 2),
                ]
                poly = [[upos + cx, vpos + cy + syx * cx] for cx, cy in corners]
                parts.append(poly)
    return parts


class NarrowingStrut:
    """A strut like an extruded baseball home plate: a rectangle topped by a narrowing triangle (BOSL2.

    narrowing_strut()).

    The triangular top converges at *angle* so the strut can brace an overhang without needing
    support. *w* is the width (thickness), *length* the length, *wall* the height of the rectangular
    base. It sits on the ``z = 0`` plane with the apex pointing up.

    Examples:
        .. pythonscad-example::

            from pybosl2.parts.walls import NarrowingStrut
            NarrowingStrut(w=10, length=100, wall=5, angle=30).show()

    """

    def __init__(self, w: float = 10, length: float = 100, wall: float = 5, angle: float = 30) -> None:
        """Create a narrowing strut.

        Args:
            w: Width (thickness) of the strut in mm.
            length: Length of the strut in mm.
            wall: Height of the rectangular base in mm.
            angle: Narrowing angle in degrees.

        Returns:
            None.

        """
        self._width = w
        self._length = length
        self._wall_val = wall
        self._angle = angle

        height = wall + w / 2 / math.tan(math.radians(angle))
        profile = [[-w / 2, 0], [w / 2, 0], [w / 2, wall], [0, height], [-w / 2, wall]]
        # Path2D.linear_extrude() dispatches through the backend, where the native
        # polygon().linear_extrude() pair is CSG-only (TASKS T14).
        shape = Path2D(profile).linear_extrude(height=length, center=True).rotate([90, 0, 0])
        self._solid: "Solid" = shape.with_nominal_size([w, length, height])

    @property
    def width(self) -> float:
        """Width (thickness) of the strut in mm."""
        return self._width

    @property
    def length(self) -> float:
        """Length of the strut in mm."""
        return self._length

    @property
    def wall(self) -> float:
        """Height of the rectangular base in mm."""
        return self._wall_val

    @property
    def angle(self) -> float:
        """Narrowing angle in degrees."""
        return self._angle

    @property
    def shape(self) -> "Solid":
        """Return the strut geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the strut in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()


class SparseWall:
    """An open, X-cross-braced rectangular wall that saves material.

    and prints support-free (BOSL2 sparse_wall()).

    A solid border of width *strut* frames a lattice of diagonal braces, each kept under *maxang*
    from vertical (so it needs no support) and spaced so no bridge exceeds *max_bridge*. The wall
    is *thick* in X, *length* long in Y and *height* tall in Z.

    Examples:
        .. pythonscad-example::

            from pybosl2.parts.walls import SparseWall
            SparseWall(height=50, length=100, thick=4).show()

    """

    def __init__(
        self,
        height: float = 50,
        length: float = 100,
        thick: float = 4,
        maxang: float = 30,
        strut: float = 5,
        max_bridge: float = 20,
    ) -> None:
        """Create a sparse X-braced wall.

        Args:
            height: Wall height in mm (Z axis).
            length: Wall length in mm (Y axis).
            thick: Wall thickness in mm (X axis).
            maxang: Maximum angle from vertical for the diagonal braces.
            strut: Width of the solid border in mm.
            max_bridge: Maximum unsupported bridge length in mm.

        Returns:
            None.

        """
        self._height = height
        self._length = length
        self._thick = thick

        outlines = _sparse_wall2d(height, length, maxang, strut, max_bridge)
        shape = _union(Path2D(outline).linear_extrude(height=thick, center=True) for outline in outlines).rotate(
            [0, 90, 0]
        )
        self._solid: "Solid" = shape.with_nominal_size([thick, length, height])

    @property
    def height(self) -> float:
        """Wall height in mm (Z axis)."""
        return self._height

    @property
    def length(self) -> float:
        """Wall length in mm (Y axis)."""
        return self._length

    @property
    def thick(self) -> float:
        """Wall thickness in mm (X axis)."""
        return self._thick

    @property
    def shape(self) -> "Solid":
        """Return the wall geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the wall in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()


class SparseCuboid:
    """A solid cuboid whose interior is X-cross-braced along *dir* ("X", "Y" or "Z") (BOSL2 sparse_cuboid()).

    A drop-in for :func:`~pybosl2.shapes3d.cuboid` when the part would benefit from the sparse
    lattice; *dir* is the axis the diagonal braces (and the through-gaps) run along.

    Examples:
        .. pythonscad-example::

            from pybosl2.parts.walls import SparseCuboid, SparseAxis
            SparseCuboid(size=[50, 40, 10], dir=SparseAxis.Y, strut=3).show()

    """

    def __init__(
        self,
        size: float | list[float],
        dir: SparseAxis = SparseAxis.Y,  # noqa: A002
        strut: float = 5,
        maxang: float = 30,
        max_bridge: float = 20,
    ) -> None:
        """Create a sparse-braced cuboid.

        Args:
            size: Outer dimensions, either a single float for a cube or ``[X, Y, Z]``.
            dir: Axis along which the diagonal braces run.
            strut: Width of the solid border in mm.
            maxang: Maximum angle from vertical for the diagonal braces.
            max_bridge: Maximum unsupported bridge length in mm.

        Returns:
            None.

        """
        self._size = list(size) if isinstance(size, (list, tuple)) else [size, size, size]

        sx, sy, sz = (float(v) for v in self._size)
        if dir == SparseAxis.X:
            braced = SparseWall(sz, sy, sx, maxang, strut, max_bridge).shape
        elif dir == SparseAxis.Y:
            braced = SparseWall(sz, sx, sy, maxang, strut, max_bridge).shape.rotate([0, 0, 90])
        elif dir == SparseAxis.Z:
            braced = SparseWall(sx, sy, sz, maxang, strut, max_bridge).shape.rotate([0, 90, 0])
        else:
            raise ValueError("sparse_cuboid(): dir must be a SparseAxis value.")
        self._solid: "Solid" = (braced & cuboid([sx, sy, sz])).with_nominal_size([sx, sy, sz])

    @property
    def size(self) -> list[float]:
        """Outer dimensions ``[X, Y, Z]`` in mm."""
        return self._size

    @property
    def shape(self) -> "Solid":
        """Return the cuboid geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the cuboid in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()


class CorrugatedWall:
    """A corrugated wall: a solid border framing a sinusoidal sheet.

    of thickness *wall* (BOSL2 corrugated_wall()).

    The corrugation waves back and forth across the *thick* thickness as it runs along the length,
    which stiffens a thin wall. *strut* is the width of the solid top/bottom/end border.

    Examples:
        .. pythonscad-example::

            from pybosl2.parts.walls import CorrugatedWall
            CorrugatedWall(height=50, length=100, thick=5).show()

    """

    def __init__(
        self,
        height: float = 50,
        length: float = 100,
        thick: float = 5,
        strut: float = 5,
        wall: float = 2,
    ) -> None:
        """Create a corrugated wall.

        Args:
            height: Wall height in mm (Z axis).
            length: Wall length in mm (Y axis).
            thick: Overall wall thickness in mm (X axis).
            strut: Width of the solid top/bottom/end border in mm.
            wall: Thickness of the corrugated sheet in mm.

        Returns:
            None.

        """
        self._height = height
        self._length = length
        self._thick = thick

        amplitude = (thick - wall) / 2
        period = min(15, thick * 2)
        steps = ((_segs(thick / 2) + 3) // 4) * 4
        step = period / steps
        il = length - 2 * strut + 2 * step
        ys = [-il / 2 + i * step for i in range(int(il / step) + 1)]
        pts = [[amplitude * math.sin(math.radians(y / period * 360)) - wall / 2, y] for y in ys]
        pts += [[amplitude * math.sin(math.radians(y / period * 360)) + wall / 2, y] for y in reversed(ys)]
        sheet = Path2D(pts).linear_extrude(height=height - 2 * strut + 0.1, center=True)
        frame = cuboid([thick, length, height]) - cuboid([thick + 0.5, length - 2 * strut, height - 2 * strut])
        self._solid: "Solid" = (sheet | frame).with_nominal_size([thick, length, height])

    @property
    def height(self) -> float:
        """Wall height in mm (Z axis)."""
        return self._height

    @property
    def length(self) -> float:
        """Wall length in mm (Y axis)."""
        return self._length

    @property
    def thick(self) -> float:
        """Wall thickness in mm (X axis)."""
        return self._thick

    @property
    def shape(self) -> "Solid":
        """Return the wall geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the wall in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()


class ThinningWall:
    """A rectangular wall that thins to *wall* in the middle while.

    the edges stay *thick* (BOSL2 thinning_wall()).

    Angled shoulders (kept under *angle*) join the thick border to the thin centre so nothing
    overhangs. *length* may be a single length or ``(bottom, top)`` for a trapezoidal wall. The diagonal
    ``braces`` option of the original is not ported.

    Examples:
        .. pythonscad-example::

            from pybosl2.parts.walls import ThinningWall
            ThinningWall(height=50, length=80, thick=4).show()

    """

    def __init__(
        self,
        height: float = 50,
        length: float = 100,
        thick: float = 5,
        angle: float = 30,
        strut: float | None = None,
        wall: float | None = None,
    ) -> None:
        """Create a wall that thins in the middle while edges stay thick.

        Args:
            height: Wall height in mm (Z axis).
            length: Wall length in mm, or ``(bottom, top)`` for a trapezoid.
            thick: Edge thickness in mm (X axis).
            angle: Maximum overhang angle in degrees.
            strut: Width of the thick border; auto-calculated if None.
            wall: Centre wall thickness; auto-calculated if None.

        Returns:
            None.

        """
        self._height = height
        self._length = length
        self._thick = thick

        l1 = length[0] if isinstance(length, (list, tuple)) else length
        l2 = length[1] if isinstance(length, (list, tuple)) else length
        strut_val = strut if strut is not None else min(height, l1, l2, thick) / 2
        wall_val = wall if wall is not None else thick / 2

        bevel_h = strut_val + (thick - wall_val) / 2 / math.tan(math.radians(angle))
        cp1 = _circle_2tangents(strut_val, [0, 0, height / 2], [l2 / 2, 0, height / 2], [l1 / 2, 0, -height / 2])
        cp2 = _circle_2tangents(
            bevel_h,
            [0, 0, height / 2],
            [l2 / 2, 0, height / 2],
            [l1 / 2, 0, -height / 2],
        )
        cp3 = _circle_2tangents(
            bevel_h,
            [0, 0, -height / 2],
            [l1 / 2, 0, -height / 2],
            [l2 / 2, 0, height / 2],
        )
        cp4 = _circle_2tangents(
            strut_val,
            [0, 0, -height / 2],
            [l1 / 2, 0, -height / 2],
            [l2 / 2, 0, height / 2],
        )

        z1, z2, z3 = height / 2, cp1[2], cp2[2]
        x1, x2, x3, x4, x5, x6 = l2 / 2, cp1[0], cp2[0], l1 / 2, cp4[0], cp3[0]
        y1, y2 = thick / 2, wall_val / 2

        pts = [
            [-x4, -y1, -z1],
            [x4, -y1, -z1],
            [x1, -y1, z1],
            [-x1, -y1, z1],
            [-x5, -y1, -z2],
            [x5, -y1, -z2],
            [x2, -y1, z2],
            [-x2, -y1, z2],
            [-x6, -y2, -z3],
            [x6, -y2, -z3],
            [x3, -y2, z3],
            [-x3, -y2, z3],
            [-x4, y1, -z1],
            [x4, y1, -z1],
            [x1, y1, z1],
            [-x1, y1, z1],
            [-x5, y1, -z2],
            [x5, y1, -z2],
            [x2, y1, z2],
            [-x2, y1, z2],
            [-x6, y2, -z3],
            [x6, y2, -z3],
            [x3, y2, z3],
            [-x3, y2, z3],
        ]
        faces = [
            [4, 5, 1],
            [5, 6, 2],
            [6, 7, 3],
            [7, 4, 0],
            [4, 1, 0],
            [5, 2, 1],
            [6, 3, 2],
            [7, 0, 3],
            [8, 9, 5],
            [9, 10, 6],
            [10, 11, 7],
            [11, 8, 4],
            [8, 5, 4],
            [9, 6, 5],
            [10, 7, 6],
            [11, 4, 7],
            [11, 10, 9],
            [20, 21, 22],
            [11, 9, 8],
            [20, 22, 23],
            [16, 17, 21],
            [17, 18, 22],
            [18, 19, 23],
            [19, 16, 20],
            [16, 21, 20],
            [17, 22, 21],
            [18, 23, 22],
            [19, 20, 23],
            [12, 13, 17],
            [13, 14, 18],
            [14, 15, 19],
            [15, 12, 16],
            [12, 17, 16],
            [13, 18, 17],
            [14, 19, 18],
            [15, 16, 19],
            [0, 1, 13],
            [1, 2, 14],
            [2, 3, 15],
            [3, 0, 12],
            [0, 13, 12],
            [1, 14, 13],
            [2, 15, 14],
            [3, 12, 15],
        ]
        pts = [[-y, x, z] for x, y, z in pts]
        shape = VNF(pts, faces).polyhedron()
        self._solid: "Solid" = shape.with_nominal_size([thick, l1, height])

    @property
    def height(self) -> float:
        """Wall height in mm (Z axis)."""
        return self._height

    @property
    def length(self) -> float:
        """Wall length in mm."""
        return self._length

    @property
    def thick(self) -> float:
        """Wall thickness in mm (X axis)."""
        return self._thick

    @property
    @csg_part("builds its braced sheet from a VNF handed over vertex by vertex, which has no distance-field form")
    def shape(self) -> "Solid":
        """Return the wall geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the wall in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()


class ThinningTriangle:
    """A right-triangular wall with thick edges thinning to *wall* in the middle (BOSL2 thinning_triangle()).

    The hypotenuse rises from the front-bottom to the back-top. *diagonly* keeps only the
    hypotenuse edge thick; *center* centres the shape (otherwise it rests on ``z = 0`` at the
    front). Built from :class:`NarrowingStrut` braces.

    Examples:
        .. pythonscad-example::

            from pybosl2.parts.walls import ThinningTriangle
            ThinningTriangle(height=50, length=80, thick=4, center=True).show()

    """

    def __init__(
        self,
        height: float = 50,
        length: float = 100,
        thick: float = 5,
        angle: float = 30,
        strut: float = 5,
        wall: float = 3,
        diagonly: bool = False,
        center: bool | None = None,
    ) -> None:
        """Create a right-triangular wall with thick edges thinning in the middle.

        Args:
            height: Wall height in mm (Z axis).
            length: Wall length in mm (Y axis).
            thick: Edge thickness in mm (X axis).
            angle: Maximum overhang angle in degrees for the struts.
            strut: Width of the thick border in mm.
            wall: Centre wall thickness in mm.
            diagonly: If True, keep only the hypotenuse edge thick.
            center: If True, centre the shape; if False, rest on z=0 at the front.

        Returns:
            None.

        """
        self._height = height
        self._length = length
        self._thick = thick

        dang = math.degrees(math.atan(height / length))
        dlen = height / math.sin(math.radians(dang))
        parts = []
        if not diagonly:
            ns1 = NarrowingStrut(w=thick, length=length, wall=strut, angle=angle).shape
            parts.append(ns1.down(height / 2))
            ns2 = NarrowingStrut(w=thick, length=height - 0.1, wall=strut, angle=angle).shape
            parts.append(ns2.rotate([-90, 0, 0]).forward(length / 2))
        hyp = (
            NarrowingStrut(w=thick, length=dlen * 1.2, wall=strut, angle=angle)
            .shape.rotate([0, 180, 0])
            .rotate([-dang, 0, 0])
        )
        parts.append(cuboid([thick, length, height]) & hyp)
        parts.append(cuboid([wall, length - 0.1, height - 0.1]))
        body = parts[0]
        for p in parts[1:]:
            body = body | p
        cutter = cuboid([thick + 0.1, length * 2, height]).up(height / 2).rotate([-dang, 0, 0])
        body = body - cutter
        if center is False:
            body = body.up(height / 2).back(length / 2)
        self._solid: "Solid" = body.with_nominal_size([thick, length, height])

    @property
    def height(self) -> float:
        """Wall height in mm (Z axis)."""
        return self._height

    @property
    def length(self) -> float:
        """Wall length in mm (Y axis)."""
        return self._length

    @property
    def thick(self) -> float:
        """Wall thickness in mm (X axis)."""
        return self._thick

    @property
    def shape(self) -> "Solid":
        """Return the triangle geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the triangle in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()

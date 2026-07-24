# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/walls.py
#    Pure-Python port of BOSL2's walls.scad: FDM-optimised wall shapes that use less material and
#    print without support. :meth:`Walls.sparse_wall` is an X-braced open wall (and
#    :meth:`~Walls.sparse_cuboid` its solid-box variant); :meth:`~Walls.corrugated_wall` a sinusoidal
#    corrugated panel; :meth:`~Walls.thinning_wall` / :meth:`~Walls.thinning_triangle` walls whose
#    middle thins away while the edges stay thick; :meth:`~Walls.narrowing_strut` the home-plate strut
#    those triangles are built from.
#
#    The honeycomb hex_panel() is not ported.
#
# FileSummary: FDM-optimised walls: sparse, corrugated, thinning and struts.
# FileGroup: BOSL2

from __future__ import annotations

import math

import numpy as np

from bosl2.shapes2d import _opolygon
from bosl2.shapes3d import Bosl2Solid, cuboid
from bosl2.vnf import VNF

__all__ = ["Walls"]


def _rect(x0, x1, y0, y1):
    """A native 2D axis-aligned rectangle from two opposite corners."""
    return _opolygon([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])


def _circle_2tangents(r, p1, p2, p3):
    """Centre of the circle of radius *r* tangent to segments p2->p1 and p2->p3 (BOSL2
    circle_2tangents()[0]); the corner is at *p2*. Points are 3-vectors (the y component is 0 here)."""
    p1, p2, p3 = (np.asarray(p, dtype=float) for p in (p1, p2, p3))
    v1 = (p1 - p2) / np.linalg.norm(p1 - p2)
    v2 = (p3 - p2) / np.linalg.norm(p3 - p2)
    bis = v1 + v2
    bis = bis / np.linalg.norm(bis)
    half = math.acos(float(np.clip(np.dot(v1, v2), -1.0, 1.0))) / 2
    return (p2 + bis * (r / math.sin(half))).tolist()


def _segs(r):
    """OpenSCAD segs(r) with the default $fa=12, $fs=2."""
    return max(5, math.ceil(min(360 / 12, 2 * math.pi * r / 2)))


class Walls:
    """FDM-optimised wall shapes (BOSL2 walls.scad)."""

    @staticmethod
    def narrowing_strut(w: float = 10, length: float = 100, wall: float = 5, angle: float = 30) -> Bosl2Solid:
        """A strut like an extruded baseball home plate: a rectangle topped by a narrowing triangle (BOSL2 narrowing_strut()).

        The triangular top converges at *angle* so the strut can brace an overhang without needing
        support. *w* is the width (thickness), *length* the length, *wall* the height of the rectangular
        base. It sits on the ``z = 0`` plane with the apex pointing up.

        Examples:
            .. pythonscad-example::

                from bosl2.walls import Walls
                Walls.narrowing_strut(w=10, length=100, wall=5, angle=30).show()
        """
        height = wall + w / 2 / math.tan(math.radians(angle))
        profile = [[-w / 2, 0], [w / 2, 0], [w / 2, wall], [0, height], [-w / 2, wall]]
        shape = _opolygon(profile).linear_extrude(height=length, center=True).rotate([90, 0, 0])
        return Bosl2Solid(shape, size=[w, length, height])

    @staticmethod
    def sparse_wall(
        height: float = 50,
        length: float = 100,
        thick: float = 4,
        maxang: float = 30,
        strut: float = 5,
        max_bridge: float = 20,
    ) -> Bosl2Solid:
        """An open, X-cross-braced rectangular wall that saves material and prints support-free (BOSL2 sparse_wall()).

        A solid border of width *strut* frames a lattice of diagonal braces, each kept under *maxang*
        from vertical (so it needs no support) and spaced so no bridge exceeds *max_bridge*. The wall
        is *thick* in X, *length* long in Y and *height* tall in Z.

        Examples:
            .. pythonscad-example::

                from bosl2.walls import Walls
                Walls.sparse_wall(height=50, length=100, thick=4).show()
        """
        region = Walls._sparse_wall2d(height, length, maxang, strut, max_bridge)
        shape = region.linear_extrude(height=thick, center=True).rotate([0, 90, 0])
        return Bosl2Solid(shape, size=[thick, length, height])

    @staticmethod
    def _sparse_wall2d(h, l, maxang, strut, max_bridge):
        """The 2D cross-braced pattern, in the (X=h, Y=l) plane (BOSL2 sparse_wall2d())."""
        zoff = h / 2 - strut / 2
        yoff = l / 2 - strut / 2
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

        # solid border, built as four bars so there is no polygon-with-hole
        parts = [
            _rect(-h / 2, -h / 2 + strut, -l / 2, l / 2),
            _rect(h / 2 - strut, h / 2, -l / 2, l / 2),
            _rect(-h / 2, h / 2, -l / 2, -l / 2 + strut),
            _rect(-h / 2, h / 2, l / 2 - strut, l / 2),
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
                    parts.append(_opolygon(poly))
        region = parts[0]
        for p in parts[1:]:
            region = region | p
        return region

    @staticmethod
    def sparse_cuboid(
        size,
        dir: str = "Y",
        strut: float = 5,
        maxang: float = 30,
        max_bridge: float = 20,
    ) -> Bosl2Solid:
        """A solid cuboid whose interior is X-cross-braced along *dir* ("X", "Y" or "Z") (BOSL2 sparse_cuboid()).

        A drop-in for :func:`~bosl2.shapes3d.cuboid` when the part would benefit from the sparse
        lattice; *dir* is the axis the diagonal braces (and the through-gaps) run along.
        """
        sx, sy, sz = (float(v) for v in (size if not isinstance(size, (int, float)) else (size, size, size)))
        diameter = str(dir).upper()
        if diameter == "X":
            braced = Walls.sparse_wall(sz, sy, sx, maxang, strut, max_bridge)
        elif diameter == "Y":
            braced = Walls.sparse_wall(sz, sx, sy, maxang, strut, max_bridge).rotate([0, 0, 90])
        elif diameter == "Z":
            braced = Walls.sparse_wall(sx, sy, sz, maxang, strut, max_bridge).rotate([0, 90, 0])
        else:
            raise ValueError('sparse_cuboid(): dir must be "X", "Y" or "Z".')
        return Bosl2Solid((braced & cuboid([sx, sy, sz])).shape, size=[sx, sy, sz])

    @staticmethod
    def corrugated_wall(
        height: float = 50,
        length: float = 100,
        thick: float = 5,
        strut: float = 5,
        wall: float = 2,
    ) -> Bosl2Solid:
        """A corrugated wall: a solid border framing a sinusoidal sheet of thickness *wall* (BOSL2 corrugated_wall()).

        The corrugation waves back and forth across the *thick* thickness as it runs along the length,
        which stiffens a thin wall. *strut* is the width of the solid top/bottom/end border.

        Examples:
            .. pythonscad-example::

                from bosl2.walls import Walls
                Walls.corrugated_wall(height=50, length=100, thick=5).show()
        """
        amplitude = (thick - wall) / 2
        period = min(15, thick * 2)
        steps = ((_segs(thick / 2) + 3) // 4) * 4  # quantup(segs(thick/2), 4)
        step = period / steps
        il = length - 2 * strut + 2 * step
        ys = [-il / 2 + i * step for i in range(int(il / step) + 1)]
        pts = [[amplitude * math.sin(math.radians(y / period * 360)) - wall / 2, y] for y in ys]
        pts += [[amplitude * math.sin(math.radians(y / period * 360)) + wall / 2, y] for y in reversed(ys)]
        sheet = _opolygon(pts).linear_extrude(height=height - 2 * strut + 0.1, center=True)
        frame = cuboid([thick, length, height]) - cuboid([thick + 0.5, length - 2 * strut, height - 2 * strut])
        return Bosl2Solid((Bosl2Solid(sheet) | frame).shape, size=[thick, length, height])

    @staticmethod
    def thinning_wall(
        height: float = 50,
        length: float = 100,
        thick: float = 5,
        angle: float = 30,
        strut: float | None = None,
        wall: float | None = None,
    ) -> Bosl2Solid:
        """A rectangular wall that thins to *wall* in the middle while the edges stay *thick* (BOSL2 thinning_wall()).

        Angled shoulders (kept under *angle*) join the thick border to the thin centre so nothing
        overhangs. *length* may be a single length or ``(bottom, top)`` for a trapezoidal wall. The diagonal
        ``braces`` option of the original is not ported.

        Examples:
            .. pythonscad-example::

                from bosl2.walls import Walls
                Walls.thinning_wall(height=50, length=80, thick=4).show()
        """
        l1 = length[0] if isinstance(length, (list, tuple)) else length
        l2 = length[1] if isinstance(length, (list, tuple)) else length
        strut = strut if strut is not None else min(height, l1, l2, thick) / 2
        wall = wall if wall is not None else thick / 2

        bevel_h = strut + (thick - wall) / 2 / math.tan(math.radians(angle))
        cp1 = _circle_2tangents(strut, [0, 0, height / 2], [l2 / 2, 0, height / 2], [l1 / 2, 0, -height / 2])
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
            strut,
            [0, 0, -height / 2],
            [l1 / 2, 0, -height / 2],
            [l2 / 2, 0, height / 2],
        )

        z1, z2, z3 = height / 2, cp1[2], cp2[2]
        x1, x2, x3, x4, x5, x6 = l2 / 2, cp1[0], cp2[0], l1 / 2, cp4[0], cp3[0]
        y1, y2 = thick / 2, wall / 2

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
        pts = [[-y, x, z] for x, y, z in pts]  # bake zrot(90): length runs along Y
        shape = VNF(pts, faces).polyhedron()
        return Bosl2Solid(shape, size=[thick, l1, height])

    @staticmethod
    def thinning_triangle(
        height: float = 50,
        length: float = 100,
        thick: float = 5,
        angle: float = 30,
        strut: float = 5,
        wall: float = 3,
        diagonly: bool = False,
        center: bool | None = None,
    ) -> Bosl2Solid:
        """A right-triangular wall with thick edges thinning to *wall* in the middle (BOSL2 thinning_triangle()).

        The hypotenuse rises from the front-bottom to the back-top. *diagonly* keeps only the
        hypotenuse edge thick; *center* centres the shape (otherwise it rests on ``z = 0`` at the
        front). Built from :meth:`narrowing_strut` braces.

        Examples:
            .. pythonscad-example::

                from bosl2.walls import Walls
                Walls.thinning_triangle(height=50, length=80, thick=4, center=True).show()
        """
        dang = math.degrees(math.atan(height / length))
        dlen = height / math.sin(math.radians(dang))
        ns = Walls.narrowing_strut
        parts = []
        if not diagonly:
            parts.append(ns(w=thick, length=length, wall=strut, angle=angle).down(height / 2))
            parts.append(
                ns(w=thick, length=height - 0.1, wall=strut, angle=angle).rotate([-90, 0, 0]).forward(length / 2)
            )
        hyp = ns(w=thick, length=dlen * 1.2, wall=strut, angle=angle).rotate([0, 180, 0]).rotate([-dang, 0, 0])
        parts.append(cuboid([thick, length, height]) & hyp)
        parts.append(cuboid([wall, length - 0.1, height - 0.1]))
        body = parts[0]
        for p in parts[1:]:
            body = body | p
        cutter = cuboid([thick + 0.1, length * 2, height]).up(height / 2).rotate([-dang, 0, 0])
        body = body - cutter
        if center is False:
            body = body.up(height / 2).back(length / 2)
        return Bosl2Solid(body.shape, size=[thick, length, height])

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/sliders.py
#    Pure-Python port of BOSL2's sliders.scad: simple V-groove sliders and the matching rails.
#    :meth:`Sliders.slider` builds a slider that rides in a :meth:`Sliders.rail` V-groove; both print
#    without support. *slop* on the slider tunes the printed fit.
#
# FileSummary: V-groove sliders and rails.
# FileGroup: BOSL2

from __future__ import annotations

import math

from bosl2._helpers import union
from bosl2.constants import BOTTOM, LEFT, RIGHT, FRONT, BACK
from bosl2.distributors import xflip_copy
from bosl2.shapes3d import Bosl2Solid, cuboid, prismoid
from bosl2.vnf import VNF

__all__ = ["Sliders"]


def _union(shapes):
    return union(shapes)


class Sliders:
    """V-groove sliders and rails (BOSL2 sliders.scad)."""

    @staticmethod
    def slider(
        l: float = 30,
        w: float = 10,
        h: float = 10,
        base: float = 10,
        wall: float = 5,
        ang: float = 30,
        slop: float = 0.0,
    ) -> Bosl2Solid:
        """A slider that rides in a matching :meth:`rail` V-groove (BOSL2 slider()).

        Examples:
            A slider:

            .. pythonscad-example::

                from bosl2.sliders import Sliders
                Sliders.slider(l=30, base=10, wall=4, slop=0.2).show()
        """
        full_width = w + 2 * wall
        full_height = h + base
        parts = [
            cuboid(
                [full_width, l, base - slop],
                chamfer=2,
                edges=[FRONT, BACK],
                except_edges=[BOTTOM],
                anchor=BOTTOM,
            )
        ]
        for m in xflip_copy(offset=w / 2 + slop):
            wallcube = cuboid(
                [wall, l, full_height],
                chamfer=2,
                edges=[RIGHT],
                except_edges=[BOTTOM],
                anchor=[b + le for b, le in zip(BOTTOM, LEFT)],
            )
            parts.append(wallcube.multmatrix(m.tolist()))
        bev_h = h / 2 * math.tan(math.radians(ang))
        for m in xflip_copy(offset=w / 2 + slop + 0.02):
            slid = prismoid(
                [h, l], [0, l - w], h=bev_h + 0.01, orient=LEFT, anchor=BOTTOM
            )
            parts.append(slid.up(base + h / 2).multmatrix(m.tolist()))
        result = _union(parts).down(base + h / 2).rotate([0, 0, 90])
        nb = result._native_bounds()
        size = nb[1] if nb else [l, full_width, h + 2 * base]
        return Bosl2Solid(result.shape, size=size)

    @staticmethod
    def rail(
        l: float = 30,
        w: float = 10,
        h: float = 10,
        chamfer: float = 1.0,
        ang: float = 30,
    ) -> Bosl2Solid:
        """A V-groove rail for a :meth:`slider` (BOSL2 rail()).

        Examples:
            A rail:

            .. pythonscad-example::

                from bosl2.sliders import Sliders
                Sliders.rail(l=100, w=10, h=10).show()
        """
        attack_ang, attack_len = 30, 2
        fudge = 1.177
        chamf = math.sqrt(2) * chamfer
        cosa = math.cos(math.radians(ang * fudge))
        sina = math.sin(math.radians(ang * fudge))
        saa = math.sin(math.radians(attack_ang))
        caa = math.cos(math.radians(attack_ang))

        z1 = h / 2
        z2 = z1 - chamf * cosa
        z3 = z1 - attack_len * saa
        z4 = 0.0
        x1 = w / 2
        x2 = x1 - chamf * sina
        x3 = x1 - chamf
        x4 = x1 - attack_len * saa
        x5 = x2 - attack_len * saa
        x6 = x1 - z1 * sina
        x7 = x4 - z1 * sina
        y1 = l / 2
        y2 = y1 - attack_len * caa

        pts = [
            [-x5, -y1, z3],
            [x5, -y1, z3],
            [x7, -y1, z4],
            [x4, -y1, -z1 - 0.05],
            [-x4, -y1, -z1 - 0.05],
            [-x7, -y1, z4],
            [-x3, -y2, z1],
            [x3, -y2, z1],
            [x2, -y2, z2],
            [x6, -y2, z4],
            [x1, -y2, -z1 - 0.05],
            [-x1, -y2, -z1 - 0.05],
            [-x6, -y2, z4],
            [-x2, -y2, z2],
            [x5, y1, z3],
            [-x5, y1, z3],
            [-x7, y1, z4],
            [-x4, y1, -z1 - 0.05],
            [x4, y1, -z1 - 0.05],
            [x7, y1, z4],
            [x3, y2, z1],
            [-x3, y2, z1],
            [-x2, y2, z2],
            [-x6, y2, z4],
            [-x1, y2, -z1 - 0.05],
            [x1, y2, -z1 - 0.05],
            [x6, y2, z4],
            [x2, y2, z2],
        ]
        faces = [
            [0, 1, 2],
            [0, 2, 5],
            [2, 3, 4],
            [2, 4, 5],
            [0, 13, 6],
            [0, 6, 7],
            [0, 7, 1],
            [1, 7, 8],
            [1, 8, 9],
            [1, 9, 2],
            [2, 9, 10],
            [2, 10, 3],
            [3, 10, 11],
            [3, 11, 4],
            [4, 11, 12],
            [4, 12, 5],
            [5, 12, 13],
            [5, 13, 0],
            [14, 15, 16],
            [14, 16, 19],
            [16, 17, 18],
            [16, 18, 19],
            [14, 27, 20],
            [14, 20, 21],
            [14, 21, 15],
            [15, 21, 22],
            [15, 22, 23],
            [15, 23, 16],
            [16, 23, 24],
            [16, 24, 17],
            [17, 24, 25],
            [17, 25, 18],
            [18, 25, 26],
            [18, 26, 19],
            [19, 26, 27],
            [19, 27, 14],
            [6, 21, 20],
            [6, 20, 7],
            [7, 20, 27],
            [7, 27, 8],
            [8, 27, 26],
            [8, 26, 9],
            [9, 26, 25],
            [9, 25, 10],
            [10, 25, 24],
            [10, 24, 11],
            [11, 24, 23],
            [11, 23, 12],
            [12, 23, 22],
            [12, 22, 13],
            [13, 22, 21],
            [13, 21, 6],
        ]
        return Bosl2Solid(VNF(pts, faces).polyhedron(), size=[w, l, h])

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/parts/sliders.py
#    Pure-Python port of BOSL2's sliders.scad: simple V-groove sliders and the matching rails.
#    :class:`Slider` builds a slider that rides in a :class:`Rail` V-groove; both print
#    without support. *slop* on the slider tunes the printed fit.
#
# FileSummary: V-groove sliders and rails.
# DocCategory: Parts library
# FileGroup: BOSL2

"""V-groove sliders and rails."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from pybosl2._backend import csg_part
from pybosl2._edges_lang import Anchor
from pybosl2._helpers import union
from pybosl2.constants import BOTTOM, LEFT
from pybosl2.distributors import DistributableMatrix
from pybosl2.solid import cuboid, prismoid

if TYPE_CHECKING:
    from pybosl2._backend import Solid
from pybosl2.vnf import VNF

__all__ = ["Slider", "Rail"]


_union = union


class Slider:
    """V-groove slider (BOSL2 slider()).

    The slider rides in a matching V-groove rail. Both print without support.
    *slop* tunes the printed fit.

    Examples:
        A slider:

        .. pythonscad-example::

            from pybosl2.parts.sliders import Slider
            Slider(l=30, base=10, wall=4, slop=0.2).show()

    """

    def __init__(
        self,
        l: float = 30,  # noqa: E741
        w: float = 10,
        h: float = 10,
        base: float = 10,
        wall: float = 5,
        angle: float = 30,
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a V-groove slider.

        Args:
            l: Slider length in mm.
            w: V-groove opening width in mm.
            h: V-groove height in mm.
            base: Base plate height in mm.
            wall: Wall thickness on each side of the V-groove in mm.
            angle: V-groove half-angle in degrees.
            slop: Additional clearance for tuning the printed fit.
            fn: Number of facets for $fn-based resolution.
            fa: Minimum facet angle.
            fs: Minimum facet size.

        Returns:
            None.

        """
        self._length: float = l
        self._width: float = w
        self._height: float = h
        full_width = w + 2 * wall
        full_height = h + base
        parts = [
            cuboid(
                [full_width, l, base - slop],
                chamfer=2,
                edges=[Anchor.FRONT, Anchor.BACK],
                except_edges=[Anchor.BOTTOM],
                anchor=BOTTOM,
                fn=fn,
                fa=fa,
                fs=fs,
            )
        ]
        for m in DistributableMatrix.xflip_copy(offset=w / 2 + slop):
            wallcube = cuboid(
                [wall, l, full_height],
                chamfer=2,
                edges=[Anchor.RIGHT],
                except_edges=[Anchor.BOTTOM],
                anchor=[b + le for b, le in zip(BOTTOM, LEFT, strict=False)],  # type: ignore[arg-type]
                fn=fn,
                fa=fa,
                fs=fs,
            )
            parts.append(wallcube.multmatrix(m.tolist()))
        bev_h = h / 2 * math.tan(math.radians(angle))
        for m in DistributableMatrix.xflip_copy(offset=w / 2 + slop + 0.02):
            # anchor + orient as two steps rather than construction arguments: `orient=` is a
            # CSG-only constructor argument, while reorient() is the same transform on either
            # backend (verified identical to the construction form). TASKS T14 phase 3.
            slid = prismoid(
                [h, l],
                [0, l - w],
                height=bev_h + 0.01,
                anchor=BOTTOM,
                fn=fn,
                fa=fa,
                fs=fs,
            ).reorient(anchor=BOTTOM, orient=LEFT)
            parts.append(slid.up(base + h / 2).multmatrix(m.tolist()))
        result = _union(parts).down(base + h / 2).rotate([0, 0, 90])
        size = list(result.bounds()[1])
        self._solid: "Solid" = result.with_nominal_size(size)

    @property
    def length(self) -> float:
        """Slider length in mm."""
        return self._length

    @property
    def width(self) -> float:
        """Slider width in mm."""
        return self._width

    @property
    def height(self) -> float:
        """Slider height in mm."""
        return self._height

    @property
    def shape(self) -> "Solid":
        """Return the slider geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the slider in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()


class Rail:
    """V-groove rail (BOSL2 rail()).

    A matching rail for the V-groove slider.

    Examples:
        A rail:

        .. pythonscad-example::

            from pybosl2.parts.sliders import Rail
            Rail(l=100, w=10, h=10).show()

    """

    def __init__(
        self,
        l: float = 30,  # noqa: E741
        w: float = 10,
        h: float = 10,
        chamfer: float = 1.0,
        angle: float = 30,
    ) -> None:
        """Create a V-groove rail.

        Args:
            l: Rail length in mm.
            w: V-groove opening width in mm.
            h: Rail height in mm.
            chamfer: Edge chamfer radius in mm.
            angle: V-groove half-angle in degrees.

        Returns:
            None.

        """
        self._length: float = l
        self._width: float = w
        self._height: float = h
        attack_ang, attack_len = 30, 2
        fudge = 1.177
        chamf = math.sqrt(2) * chamfer
        cosa = math.cos(math.radians(angle * fudge))
        sina = math.sin(math.radians(angle * fudge))
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
        self._solid: "Solid" = VNF(pts, faces).polyhedron().with_nominal_size([w, l, h])

    @property
    def length(self) -> float:
        """Rail length in mm."""
        return self._length

    @property
    def width(self) -> float:
        """Rail width in mm."""
        return self._width

    @property
    def height(self) -> float:
        """Rail height in mm."""
        return self._height

    @property
    @csg_part("builds from a VNF whose faces are not convex, so it has no distance-field form")
    def shape(self) -> "Solid":
        """Return the rail geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the rail in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()

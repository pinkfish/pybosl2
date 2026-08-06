# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# DocCategory: Parts library
# LibFile: pybosl2/parts/tripod_mounts.py
# FileSummary: Tripod mount plates: RC2.
# FileGroup: BOSL2

"""Tripod mount plates: RC2."""

from __future__ import annotations

import math
from typing import Sequence

from pybosl2._edges_lang import Anchor
from pybosl2.masking import chamfer_edge_mask, edge_mask
from pybosl2.path2d import Path2D
from pybosl2.points import Point
from pybosl2.shapes3d import Bosl2Solid, cuboid
from pybosl2.shapes3d.base import _finish3
from pybosl2.turtle import TurtleCommand, turtle2d
from pybosl2.turtle import TurtleCommandType as TCT  # noqa: N817

__all__ = ["TripodMounts", "manfrotto_rc2_plate"]


class TripodMounts:
    """Tripod mount plates: RC2 (BOSL2 tripod_mounts.scad).

    .. seealso::

       `Visual spec sheet <specs/tripod_mounts.html>`_ — measurements and STL previews
    """

    @staticmethod
    def manfrotto_rc2_plate(
        chamfer: str = "all",
        anchor: Anchor | Sequence[float] = Anchor.CENTER,
        spin: float = 0.0,
        orient: Anchor | Sequence[float] = Anchor.TOP,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """Create a Manfrotto RC2 tripod quick release mount plate (BOSL2 manfrotto_rc2_plate()).

        The *chamfer* argument lets you control whether the model edges are chamfered.
        By default all edges are chamfered ("all"), but you can set it to "bot" or "bottom"
        to chamfer only the bottom, or "none" for no chamfering.
        The plate is 10.5 mm thick.

        Args:
            chamfer: "none" for no chamfer, "all" for full chamfering, and "bot" or "bottom" for bottom chamfering.
            anchor: anchor point
            spin: Z-axis rotation in degrees
            orient: direction to rotate the top towards
            fn: arc smoothness
            fa: arc smoothness
            fs: arc smoothness

        Examples:
            A standard Manfrotto RC2 plate:

            .. pythonscad-example::

                from pybosl2.parts.tripod_mounts import TripodMounts
                TripodMounts.manfrotto_rc2_plate().show()

        """
        if chamfer not in ("bot", "bottom", "all", "none"):
            raise ValueError('chamfer must be "all", "bottom", "bot", or "none"')

        chsize = 0.5
        chamf_top = chamfer == "all"
        chamf_bot = chamfer in ("bot", "bottom", "all")

        length = 52.5
        innerlen = 43.0

        topwid = 37.4
        botwid = 42.4

        thickness = 10.5

        flat_height = 3.0
        angled_size = 5.0
        angled_height = thickness - flat_height * 2
        angled_width = math.sqrt(angled_size**2 - angled_height**2)

        corner_space = 25.0
        left_top = 2.0

        # Build turtle commands for pts profile:
        cmds = [
            TurtleCommand(TCT.MOVE, size=botwid),
            TurtleCommand(TCT.LEFT, angle=90.0),
            TurtleCommand(TCT.MOVE, size=flat_height),
            TurtleCommand(TCT.XYZMOVE, size=Point(-angled_width, angled_height)),
            TurtleCommand(TCT.MOVE, size=flat_height),
            TurtleCommand(TCT.LEFT, angle=90.0),
            TurtleCommand(TCT.MOVE, size=topwid),
            TurtleCommand(TCT.LEFT, angle=90.0),
            TurtleCommand(TCT.MOVE, size=left_top),
            TurtleCommand(TCT.JUMP, size=Point(0.0, flat_height)),
        ]
        pts = turtle2d(cmds).points()

        # Calculate facet points for cut2:
        p_neg3 = pts[5]
        p_neg2 = pts[6]
        p_neg1 = pts[7]

        facet = [
            [p_neg3[0], p_neg3[1] - left_top],
            [p_neg2[0], p_neg2[1] - 1.5],
            [p_neg1[0], p_neg1[1] - 1.5],
            [-10.0, p_neg1[1] - left_top],
            [p_neg3[0] - 10.0, p_neg3[1] - flat_height],
        ]

        # 1. Main body linear sweep:
        body = Bosl2Solid(pts.linear_sweep(height=length).polyhedron()).orient(Anchor.FRONT)  # type: ignore[union-attr]
        body = body.down(thickness / 2)

        # Apply centering translation to align the attachable box centered around origin:
        center_trans = [-botwid / 2 + 0.64115 / 2, length / 2, 0.0]
        body = body.translate(center_trans)

        # 2. Subtract cutouts:
        c_space_y = (length - innerlen) / 2
        cut1 = cuboid(
            [corner_space, c_space_y, thickness + 0.02],
            chamfer=-chsize,
            edges=Anchor.ALL if chamf_top else Anchor.TOP,
            anchor=Anchor.TOP_FRONT_LEFT,
            fn=fn,
            fa=fa,
            fs=fs,
        ).translate([-botwid / 2 + 0.64115 / 2 - 0.01, -length / 2 - 0.01, -thickness / 2 - 0.01])

        cut1_all = cut1 | cut1.scale([1, 1, -1])
        body = body - cut1_all

        cutout_len = 26.0
        cut2 = Bosl2Solid(Path2D(facet).linear_sweep(height=cutout_len).polyhedron()).orient(Anchor.FRONT)  # type: ignore[union-attr]
        cut2 = cut2.translate([-botwid / 2 + 0.64115 / 2, length / 2 - left_top, 0.0])
        body = body - cut2

        # 3. Add edge masks if chamfering is requested:
        if chamf_bot:
            body = edge_mask(  # type: ignore[assignment]
                body,
                [
                    Anchor.FRONT_LEFT,
                    Anchor.FRONT_RIGHT,
                    Anchor.TOP_FRONT,
                    Anchor.BOTTOM_FRONT,
                    Anchor.TOP_RIGHT,
                    Anchor.BOTTOM_RIGHT,
                ],
                size=(botwid, length, thickness),
                children=chamfer_edge_mask(length, chsize),
            )
            assert body is not None
            tl_cutter = edge_mask(
                body,
                Anchor.TOP_LEFT,
                size=(botwid, length, thickness),
                children=chamfer_edge_mask(length, chsize),
                return_cutter=True,
            )
            if tl_cutter is not None:
                c1 = tl_cutter.right(corner_space)
                c2 = tl_cutter.down((length - innerlen) / 2)
                body = body - (c1 | c1.scale([1, 1, -1]) | c2 | c2.scale([1, 1, -1]))

        if chamf_top:
            body = edge_mask(  # type: ignore[assignment]
                body,
                [
                    Anchor.BACK_LEFT,
                    Anchor.BACK_RIGHT,
                    Anchor.TOP_BACK,
                    Anchor.BOTTOM_BACK,
                ],
                size=(botwid, length, thickness),
                children=chamfer_edge_mask(length, chsize),
            )
            assert body is not None

        # Resolve anchor offset and finish using _finish3
        a = anchor.vector if isinstance(anchor, Anchor) else list(anchor)
        offset = [-a[0] * botwid / 2, -a[1] * length / 2, -a[2] * thickness / 2]

        return _finish3(
            body.shape,
            offset,
            spin,
            orient,
            size=(botwid, length, thickness),
            anchor=anchor,
        )


manfrotto_rc2_plate = TripodMounts.manfrotto_rc2_plate

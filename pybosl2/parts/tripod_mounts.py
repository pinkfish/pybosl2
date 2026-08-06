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

        # 1. Main body: sweep the dovetail profile. orient() leaves it centred on its bounding
        # box; BOSL2 anchors the dovetail as a prismoid whose top face is offset by `shift`
        # (the top face is 0.32 mm right of the bottom one), which sits the body half of that
        # offset to the left of the anchor box.
        shift = 0.64115 / 2
        body = Bosl2Solid(pts.linear_sweep(height=length).polyhedron()).orient(Anchor.FRONT)  # type: ignore[union-attr]
        body = body.left(shift / 2)
        # where the profile's own origin (its bottom-left corner) lands, so the cutouts below can
        # be placed in the same coordinates the profile was drawn in
        profile_x = -botwid / 2 - shift / 2
        profile_z = -thickness / 2

        # 2. Subtract the end relief notches: corner_space wide from the left face, cut in from
        # each end, through the full thickness. The 0.01 slop keeps the cutter faces clear of the
        # body's, which would otherwise leave coincident faces behind.
        c_space_y = (length - innerlen) / 2
        notch = cuboid(
            [corner_space, c_space_y, thickness + 0.02],
            chamfer=-chsize,
            edges=Anchor.ALL if chamf_top else Anchor.TOP,
            fn=fn,
            fa=fa,
            fs=fs,
        ).translate(
            [
                profile_x - 0.01 + corner_space / 2,
                length / 2 + 0.01 - c_space_y / 2,
                0.0,
            ]
        )
        body = body - (notch | notch.scale([1, -1, 1]))

        # 3. Subtract the facet down the left edge: the facet polygon is drawn in the profile's
        # own coordinates, so it is placed back onto them.
        cutout_len = 26.0
        facet_x = [p[0] for p in facet]
        facet_y = [p[1] for p in facet]
        cut2 = Bosl2Solid(Path2D(facet).linear_sweep(height=cutout_len).polyhedron()).orient(Anchor.FRONT)  # type: ignore[union-attr]
        cut2 = cut2.translate(
            [
                profile_x + (min(facet_x) + max(facet_x)) / 2,
                0.0,
                profile_z + (min(facet_y) + max(facet_y)) / 2,
            ]
        )
        body = body - cut2

        # 4. Chamfer the edges. The masks run along the body's own edges, so they are placed on
        # the same shifted box the body occupies. (BOSL2 also masks the notch rims here, but
        # those masks slide along their own axis and cut nothing, so they are left out.)
        mask_box = (botwid, length, thickness)
        mask_center = Point([-shift / 2, 0.0, 0.0])
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
                size=mask_box,
                center=mask_center,
                children=chamfer_edge_mask(length, chsize),
            )
            assert body is not None

        if chamf_top:
            body = edge_mask(  # type: ignore[assignment]
                body,
                [
                    Anchor.BACK_LEFT,
                    Anchor.BACK_RIGHT,
                    Anchor.TOP_BACK,
                    Anchor.BOTTOM_BACK,
                ],
                size=mask_box,
                center=mask_center,
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

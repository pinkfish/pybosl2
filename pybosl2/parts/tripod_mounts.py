# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# DocCategory: Parts library
# LibFile: pybosl2/parts/tripod_mounts.py
# FileSummary: Manfrotto RC2 tripod quick release mount plate.
# FileGroup: BOSL2

"""Tripod mount plates: RC2."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from pybosl2._backend import Solid

from pybosl2._edges_lang import Anchor
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.masking import chamfer_edge_mask, edge_mask
from pybosl2.parts._buildable import Buildable
from pybosl2.path2d import Path2D
from pybosl2.points import Point
from pybosl2.solid import cuboid
from pybosl2.turtle import TurtleCommand, turtle2d
from pybosl2.turtle import TurtleCommandType as TCT  # noqa: N817

__all__ = ["ManfrottoRC2Plate", "manfrotto_rc2_plate"]


class ManfrottoRC2Plate(Buildable):
    """A Manfrotto RC2 tripod quick release mount plate.

    The *chamfer* argument controls edge chamfering: ``"all"`` (default),
    ``"bot"`` or ``"bottom"`` for bottom-only, or ``"none"``.

    Examples:
        A standard Manfrotto RC2 plate:

        .. pythonscad-example::

            from pybosl2.parts.tripod_mounts import ManfrottoRC2Plate
            ManfrottoRC2Plate().show()

    """

    def __init__(
        self,
        chamfer: str = "all",
        anchor: Anchor | Sequence[float] = Anchor.CENTER,
        spin: float = 0.0,
        orient: Anchor | Sequence[float] = Anchor.TOP,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a Manfrotto RC2 tripod quick release mount plate.

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

        Returns:
            None.

        Raises:
            ValueError: If *chamfer* is not one of ``"all"``, ``"bottom"``, ``"bot"``, or ``"none"``.

        """
        self._chamfer = chamfer

        if chamfer not in ("bot", "bottom", "all", "none"):
            raise Bosl2ValueError('chamfer must be "all", "bottom", "bot", or "none"')

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
        body = pts.linear_extrude(height=length).orient(Anchor.FRONT)
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
        # The far-end notch is the near one mirrored, which `scale([1, -1, 1])` spells as a
        # negative factor -- a reflection written as a scale. The field backend refuses that
        # outright ("factors must be positive"), and `mirror` is what it meant; same solid on
        # either backend (the `HerringboneGear` finding, T14).
        body = body - (notch | notch.mirror([0, 1, 0]))

        # 3. Subtract the facet down the left edge: the facet polygon is drawn in the profile's
        # own coordinates, so it is placed back onto them.
        cutout_len = 26.0
        facet_x = [p[0] for p in facet]
        facet_y = [p[1] for p in facet]
        cut2 = Path2D(facet).linear_extrude(height=cutout_len).orient(Anchor.FRONT)
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
                mask=chamfer_edge_mask(length, chsize),
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
                mask=chamfer_edge_mask(length, chsize),
            )
            assert body is not None

        # Anchor, spin and orient against the plate's nominal box. This used to go through
        # `_finish3`, which unwraps to a native handle -- `.shape` -- that a field solid does not
        # have, so the part was CSG-only by its last three lines rather than by its geometry.
        # `reorient(bbox=)` is the same three moves in the same order, on the shared contract.
        half = [botwid / 2.0, length / 2.0, thickness / 2.0]
        box = [[-v for v in half], half]
        self._solid = body.reorient(anchor, spin=spin, orient=orient, bbox=box).with_nominal_size(
            [botwid, length, thickness], anchor=anchor
        )

    @property
    def chamfer(self) -> str:
        """Chamfer mode: "all", "bottom"/"bot", or "none"."""
        return self._chamfer

    @property
    def shape(self) -> "Solid":
        """Return the RC2 plate geometry.

        Builds on either backend since T142. The refusal here named `linear_sweep()`, which meshes
        the profile and hands over a non-convex polyhedron -- but the profile sweep *is* a plain
        extrusion, and `linear_extrude` has dispatched for a while (the `walls` finding, T14).
        """
        return self._solid


manfrotto_rc2_plate = ManfrottoRC2Plate  #: Alias for :class:`ManfrottoRC2Plate`.

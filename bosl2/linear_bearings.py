# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/linear_bearings.py
#    Pure-Python port of BOSL2's linear_bearings.scad: models of linear ball bearings that run along
#    a rod, and the pillow-block housings that hold them. :meth:`LinearBearings.linear_bearing` is a
#    generic bearing; :meth:`~LinearBearings.lmXuu_bearing` looks a standard LMxUU size up in
#    :meth:`~LinearBearings.lmXuu_info` (a :class:`LinearBearingSpec` table). The housings clamp a
#    bearing to a plate with a teardrop bore and a screw.
#
# FileSummary: Linear (LMxUU) ball bearings and their pillow-block housings.
# FileGroup: BOSL2

from __future__ import annotations

import math
from dataclasses import dataclass

from bosl2._helpers import union
from bosl2.shapes3d import Bosl2Solid, cuboid, teardrop, tube

__all__ = ["LinearBearings", "LinearBearingSpec"]


def _union(shapes):
    return union(shapes)


@dataclass(frozen=True)
class LinearBearingSpec:
    """Dimensions of a standard LMxUU linear bearing (BOSL2 lmXuu_info())."""

    od: float  # outer diameter
    length: float  # axial length
    # the bore (shaft) diameter equals the nominal size, which keys the table.


# nominal size (shaft Ø) -> spec, transcribed from linear_bearings.scad.
_LMXUU = {
    4: LinearBearingSpec(8, 12),
    5: LinearBearingSpec(10, 15),
    6: LinearBearingSpec(12, 19),
    8: LinearBearingSpec(15, 24),
    10: LinearBearingSpec(19, 29),
    12: LinearBearingSpec(21, 30),
    13: LinearBearingSpec(23, 32),
    16: LinearBearingSpec(28, 37),
    20: LinearBearingSpec(32, 42),
    25: LinearBearingSpec(40, 59),
    30: LinearBearingSpec(45, 64),
    35: LinearBearingSpec(52, 70),
    40: LinearBearingSpec(60, 80),
    50: LinearBearingSpec(80, 100),
    60: LinearBearingSpec(90, 110),
    80: LinearBearingSpec(120, 140),
    100: LinearBearingSpec(150, 175),
}


class LinearBearings:
    """Linear (LMxUU) ball bearings and pillow-block housings (BOSL2 linear_bearings.scad)."""

    @staticmethod
    def lmXuu_info(size: int) -> LinearBearingSpec:
        """The :class:`LinearBearingSpec` (od, length) for a standard LMxUU size (BOSL2 lmXuu_info())."""
        try:
            return _LMXUU[int(size)]
        except (KeyError, ValueError):
            raise ValueError(f"Unsupported lmXuu linear bearing size: {size!r}")

    @staticmethod
    def linear_bearing(
        length: float = 24, outer_diameter: float = 15, inner_diameter: float = 8, color: str | None = "silver"
    ) -> Bosl2Solid:
        """A generic linear ball-bearing cartridge, bore *inner_diameter* / outer *outer_diameter* / length *length* (BOSL2 linear_bearing()).

        Examples:
            An LM8UU-sized bearing:

            .. pythonscad-example::

                from bosl2.linear_bearings import LinearBearings
                LinearBearings.linear_bearing(length=24, outer_diameter=15, inner_diameter=8).show()
        """
        body = _union(
            [
                tube(inner_diameter=inner_diameter, outer_diameter=outer_diameter, height=length - 1),
                tube(inner_diameter=outer_diameter - 1, outer_diameter=outer_diameter, height=length),
                tube(inner_diameter=inner_diameter, outer_diameter=inner_diameter + 1, height=length),
                tube(inner_diameter=inner_diameter + 2, outer_diameter=outer_diameter - 2, height=length),
            ]
        )
        result = Bosl2Solid(body.shape, size=[outer_diameter, outer_diameter, length])
        return result.color(color) if color else result

    @staticmethod
    def lmXuu_bearing(size: int = 8, color: str | None = "silver") -> Bosl2Solid:
        """A standard LMxUU linear bearing for a *size* mm rod (BOSL2 lmXuu_bearing())."""
        spec = LinearBearings.lmXuu_info(size)
        return LinearBearings.linear_bearing(
            length=spec.length, inner_diameter=size, outer_diameter=spec.od, color=color
        )

    @staticmethod
    def linear_bearing_housing(
        diameter: float = 15,
        length: float = 24,
        tab: float = 8,
        gap: float = 5,
        wall: float = 3,
        tabwall: float = 5,
        screwsize: float = 3,
        _fn: int | None = None,
    ) -> Bosl2Solid:
        """A pillow-block housing that clamps a linear bearing (bore *diameter*, length *length*) to a plate (BOSL2 linear_bearing_housing()).

        The teardrop bore prints without support; the split *gap* and a *screwsize* clamp screw
        through the tabs let it grip the bearing.
        """
        outer_diameter = diameter + 2 * wall
        ogap = gap + 2 * tabwall
        tabh = tab / 2 + od / 2 * math.sqrt(2) - ogap / 2 - 1

        # teardrop bearing shell + base + clamp tabs, then the bore, split gap and screw hole removed.
        body = _union(
            [
                teardrop(diameter=od, height=length).rotate([0, 90, 0]),  # teardrop shell, axis along X
                cuboid([length, od, od / 2]).down(od / 4),  # base
                cuboid([length, ogap, od / 2 + tab / 2]).up(
                    (od / 2 + tab / 2) / 2
                ),  # clamp tabs
            ]
        )
        body = body - teardrop(diameter=diameter, height=length + 0.1).rotate([0, 90, 0])  # bearing bore
        body = body - cuboid([length + 0.1, gap, od])  # split gap
        # clamp screw across the tabs (a simple clearance hole)
        from bosl2.screws import Screws

        screw = (
            Screws.screw_hole(f"M{screwsize:g}", length=ogap + 1, _fn=_fn or 16)
            .rotate([90, 0, 0])
            .up(tabh)
        )
        body = body - screw
        return Bosl2Solid(body.shape, size=[length, od, od + tab / 2])

    @staticmethod
    def lmXuu_housing(
        size: int = 8,
        tab: float = 7,
        gap: float = 5,
        wall: float = 3,
        tabwall: float = 5,
        screwsize: float = 3,
        _fn: int | None = None,
    ) -> Bosl2Solid:
        """A pillow-block housing sized for a standard LMxUU bearing (BOSL2 lmXuu_housing())."""
        spec = LinearBearings.lmXuu_info(size)
        return LinearBearings.linear_bearing_housing(
            diameter=spec.od,
            length=spec.length,
            tab=tab,
            gap=gap,
            wall=wall,
            tabwall=tabwall,
            screwsize=screwsize,
            _fn=_fn,
        )

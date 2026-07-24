# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/ball_bearings.py
#    Pure-Python port of BOSL2's ball_bearings.scad: models of standard ball-bearing cartridges.
#    :meth:`BallBearings.ball_bearing` builds a bearing -- either a sealed/shielded cartridge (nested
#    rings plus a shield face) or an open one (inner and outer races, a ball-race groove, and the
#    balls) -- from a trade-size name (``"608"``, ``"6902ZZ"``, ``"R8"``) or explicit id/od/width.
#    :meth:`BallBearings.ball_bearing_info` returns the tabulated dimensions as a :class:`BearingSpec`.
#
#    The trade-size table is transcribed verbatim from ball_bearings.scad.
#
# FileSummary: Standard ball-bearing cartridge models.
# FileGroup: BOSL2

from __future__ import annotations

import math
import operator
from dataclasses import dataclass
from functools import reduce

from bosl2.constants import INCH
from bosl2.shapes3d import Bosl2Solid, sphere, torus, tube

__all__ = ["BallBearings", "BearingSpec"]


@dataclass(frozen=True)
class BearingSpec:
    """Dimensions of a standard ball-bearing cartridge (BOSL2 ball_bearing_info())."""

    inner_diameter: float  # inner (shaft) diameter
    outer_diameter: float  # outer diameter
    width: float  # axial width
    shielded: bool  # True for a sealed/shielded (ZZ) cartridge


_I = INCH
# trade size -> BearingSpec, transcribed from ball_bearings.scad.
_BEARINGS = {
    "R2": BearingSpec(1 / 8 * _I, 3 / 8 * _I, 5 / 32 * _I, False),
    "R3": BearingSpec(3 / 16 * _I, 1 / 2 * _I, 5 / 32 * _I, False),
    "R4": BearingSpec(1 / 4 * _I, 5 / 8 * _I, 0.196 * _I, False),
    "R6": BearingSpec(3 / 8 * _I, 7 / 8 * _I, 7 / 32 * _I, False),
    "R8": BearingSpec(1 / 2 * _I, 9 / 8 * _I, 1 / 4 * _I, False),
    "R10": BearingSpec(5 / 8 * _I, 11 / 8 * _I, 9 / 32 * _I, False),
    "R12": BearingSpec(3 / 4 * _I, 13 / 8 * _I, 5 / 16 * _I, False),
    "R14": BearingSpec(7 / 8 * _I, 15 / 8 * _I, 3 / 8 * _I, False),
    "R16": BearingSpec(8 / 8 * _I, 16 / 8 * _I, 3 / 8 * _I, False),
    "R18": BearingSpec(9 / 8 * _I, 17 / 8 * _I, 3 / 8 * _I, False),
    "R20": BearingSpec(10 / 8 * _I, 18 / 8 * _I, 3 / 8 * _I, False),
    "R22": BearingSpec(11 / 8 * _I, 20 / 8 * _I, 7 / 16 * _I, False),
    "R24": BearingSpec(12 / 8 * _I, 21 / 8 * _I, 7 / 16 * _I, False),
    "608": BearingSpec(8, 22, 7, False),
    "629": BearingSpec(9, 26, 8, False),
    "635": BearingSpec(5, 19, 6, False),
    "6000": BearingSpec(10, 26, 8, False),
    "6001": BearingSpec(12, 28, 8, False),
    "6002": BearingSpec(15, 32, 9, False),
    "6003": BearingSpec(17, 35, 10, False),
    "6007": BearingSpec(35, 62, 14, False),
    "6200": BearingSpec(10, 30, 9, False),
    "6201": BearingSpec(12, 32, 10, False),
    "6202": BearingSpec(15, 35, 11, False),
    "6203": BearingSpec(17, 40, 12, False),
    "6204": BearingSpec(20, 47, 14, False),
    "6205": BearingSpec(25, 52, 15, False),
    "6206": BearingSpec(30, 62, 16, False),
    "6207": BearingSpec(35, 72, 17, False),
    "6208": BearingSpec(40, 80, 18, False),
    "6209": BearingSpec(45, 85, 19, False),
    "6210": BearingSpec(50, 90, 20, False),
    "6211": BearingSpec(55, 100, 21, False),
    "6212": BearingSpec(60, 110, 22, False),
    "6301": BearingSpec(12, 37, 12, False),
    "6302": BearingSpec(15, 42, 13, False),
    "6303": BearingSpec(17, 47, 14, False),
    "6304": BearingSpec(20, 52, 15, False),
    "6305": BearingSpec(25, 62, 17, False),
    "6306": BearingSpec(30, 72, 19, False),
    "6307": BearingSpec(35, 80, 21, False),
    "6308": BearingSpec(40, 90, 23, False),
    "6309": BearingSpec(45, 100, 25, False),
    "6310": BearingSpec(50, 110, 27, False),
    "6311": BearingSpec(55, 120, 29, False),
    "6312": BearingSpec(60, 130, 31, False),
    "6403": BearingSpec(17, 62, 17, False),
    "6800": BearingSpec(10, 19, 5, False),
    "6801": BearingSpec(12, 21, 5, False),
    "6802": BearingSpec(15, 24, 5, False),
    "6803": BearingSpec(17, 26, 5, False),
    "6804": BearingSpec(20, 32, 7, False),
    "6805": BearingSpec(25, 37, 7, False),
    "6806": BearingSpec(30, 42, 7, False),
    "6900": BearingSpec(10, 22, 6, False),
    "6901": BearingSpec(12, 24, 6, False),
    "6902": BearingSpec(15, 28, 7, False),
    "6903": BearingSpec(17, 30, 7, False),
    "6904": BearingSpec(20, 37, 9, False),
    "6905": BearingSpec(25, 42, 9, False),
    "6906": BearingSpec(30, 47, 9, False),
    "6907": BearingSpec(35, 55, 10, False),
    "6908": BearingSpec(40, 62, 12, False),
    "16002": BearingSpec(15, 22, 8, False),
    "16004": BearingSpec(20, 42, 8, False),
    "16005": BearingSpec(25, 47, 8, False),
    "16100": BearingSpec(10, 28, 8, False),
    "16101": BearingSpec(12, 30, 8, False),
}
# The "...ZZ" shielded variants share the open variant's dimensions.
_BEARINGS.update(
    {
        name + "ZZ": BearingSpec(s.inner_diameter, s.outer_diameter, s.width, True)
        for name, s in list(_BEARINGS.items())
    }
)


class BallBearings:
    """Standard ball-bearing cartridge models (BOSL2 ball_bearings.scad)."""

    @staticmethod
    def ball_bearing_info(trade_size: str) -> BearingSpec:
        """
            The :class:`BearingSpec` for a standard trade size, e.g. ``"608"`` / ``"6902ZZ"`` /
            ``"R8"``.
        """
        try:
            return _BEARINGS[str(trade_size)]
        except KeyError:
            raise ValueError(f"Unsupported ball bearing trade size: {trade_size!r}")

    @staticmethod
    def ball_bearing(
        trade_size: str | None = None,
        inner_diameter: float | None = None,
        outer_diameter: float | None = None,
        width: float | None = None,
        shield: bool = True,
        color: str | None = "silver",
        fn=None,
        fa=None,
        fs=None,
    ) -> Bosl2Solid:
        """A ball-bearing cartridge model (BOSL2 ball_bearing()).

        Give a *trade_size* name, or explicit *inner_diameter*/*outer_diameter*/*width* (with *shield*). Returns a
        :class:`~bosl2.shapes3d.Bosl2Solid` centered on the origin.

        Examples:
            A common 608 skate bearing:

            .. pythonscad-example::

                from bosl2.ball_bearings import BallBearings
                BallBearings.ball_bearing("608").show()
        """
        if trade_size is not None:
            spec = BallBearings.ball_bearing_info(trade_size)
            inner_diameter, outer_diameter, width, shield = (
                spec.inner_diameter,
                spec.outer_diameter,
                spec.width,
                spec.shielded,
            )
        assert None not in (inner_diameter, outer_diameter, width), (
            "ball_bearing(): give a trade_size or inner_diameter/outer_diameter/width."
        )

        mid_d = (inner_diameter + outer_diameter) / 2
        wall = (outer_diameter - inner_diameter) / 2 / 3
        if shield:
            result = (
                tube(
                    inner_diameter=inner_diameter,
                    wall=wall,
                    height=width,
                    fn=fn,
                    fa=fa,
                    fs=fs,
                )
                | tube(
                    outer_diameter=outer_diameter,
                    wall=wall,
                    height=width,
                    fn=fn,
                    fa=fa,
                    fs=fs,
                )
                | tube(
                    inner_diameter=inner_diameter + 0.1,
                    outer_diameter=outer_diameter - 0.1,
                    height=(wall * 2 + width) / 2,
                    fn=fn,
                    fa=fa,
                    fs=fs,
                )
            )
        else:
            ball_cnt = int(math.floor(math.pi * mid_d * 0.95 / (wall * 2)))
            races = tube(
                inner_diameter=inner_diameter,
                wall=wall,
                height=width,
                fn=fn,
                fa=fa,
                fs=fs,
            ) | tube(
                outer_diameter=outer_diameter,
                wall=wall,
                height=width,
                fn=fn,
                fa=fa,
                fs=fs,
            )
            races = races - torus(
                major_radius=mid_d / 2, minor_radius=wall, fn=fn, fa=fa, fs=fs
            )
            balls = reduce(
                operator.or_,
                (
                    sphere(diameter=wall * 2, fn=fn, fa=fa, fs=fs)
                    .right(mid_d / 2)
                    .rotate([0, 0, i * 360 / ball_cnt])
                    for i in range(ball_cnt)
                ),
            )
            result = races | balls
        result = Bosl2Solid(result.shape, size=[outer_diameter, outer_diameter, width])
        return result.color(color) if color else result

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/ball_bearings.py
#    Pure-Python port of BOSL2's ball_bearings.scad: models of standard ball-bearing cartridges.
#    :meth:`BallBearings.ball_bearing` builds a bearing -- either a sealed/shielded cartridge (nested
#    rings plus a shield face) or an open one (inner and outer races, a ball-race groove, and the
#    balls) -- from a :class:`BearingType` trade size or explicit
#    inner_diameter/outer_diameter/width.
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
from enum import Enum, auto
from functools import reduce

from pybosl2.constants import INCH
from pybosl2.shapes3d import Bosl2Solid, sphere, torus, tube

__all__ = ["BallBearings", "BearingSpec", "BearingType"]

# string trade-name -> BearingType lookup, built from the enum names.
_BY_TRADE_NAME: dict[str, BearingType] = {}


class BearingType(Enum):
    """Trade-size identifier for standard ball-bearing cartridges.

    Each member names a standard trade size (e.g. ``BEARING_608``, ``R8``, ``R8_ZZ``)
    that :meth:`BallBearings.ball_bearing_info` and :meth:`BallBearings.ball_bearing`
    accept. Use the enum to avoid typos and get IDE autocompletion for the available
    sizes. String names (``"608"``, ``"R8ZZ"``) are also accepted via the
    :func:`BearingType.of` helper.
    """

    # R-series (inch)
    R2 = auto()
    R3 = auto()
    R4 = auto()
    R6 = auto()
    R8 = auto()
    R10 = auto()
    R12 = auto()
    R14 = auto()
    R16 = auto()
    R18 = auto()
    R20 = auto()
    R22 = auto()
    R24 = auto()
    # R-series shielded
    R2_ZZ = auto()
    R3_ZZ = auto()
    R4_ZZ = auto()
    R6_ZZ = auto()
    R8_ZZ = auto()
    R10_ZZ = auto()
    R12_ZZ = auto()
    R14_ZZ = auto()
    R16_ZZ = auto()
    R18_ZZ = auto()
    R20_ZZ = auto()
    R22_ZZ = auto()
    R24_ZZ = auto()
    # metric
    BEARING_608 = auto()
    BEARING_629 = auto()
    BEARING_635 = auto()
    BEARING_6000 = auto()
    BEARING_6001 = auto()
    BEARING_6002 = auto()
    BEARING_6003 = auto()
    BEARING_6007 = auto()
    BEARING_6200 = auto()
    BEARING_6201 = auto()
    BEARING_6202 = auto()
    BEARING_6203 = auto()
    BEARING_6204 = auto()
    BEARING_6205 = auto()
    BEARING_6206 = auto()
    BEARING_6207 = auto()
    BEARING_6208 = auto()
    BEARING_6209 = auto()
    BEARING_6210 = auto()
    BEARING_6211 = auto()
    BEARING_6212 = auto()
    BEARING_6301 = auto()
    BEARING_6302 = auto()
    BEARING_6303 = auto()
    BEARING_6304 = auto()
    BEARING_6305 = auto()
    BEARING_6306 = auto()
    BEARING_6307 = auto()
    BEARING_6308 = auto()
    BEARING_6309 = auto()
    BEARING_6310 = auto()
    BEARING_6311 = auto()
    BEARING_6312 = auto()
    BEARING_6403 = auto()
    BEARING_6800 = auto()
    BEARING_6801 = auto()
    BEARING_6802 = auto()
    BEARING_6803 = auto()
    BEARING_6804 = auto()
    BEARING_6805 = auto()
    BEARING_6806 = auto()
    BEARING_6900 = auto()
    BEARING_6901 = auto()
    BEARING_6902 = auto()
    BEARING_6903 = auto()
    BEARING_6904 = auto()
    BEARING_6905 = auto()
    BEARING_6906 = auto()
    BEARING_6907 = auto()
    BEARING_6908 = auto()
    BEARING_16002 = auto()
    BEARING_16004 = auto()
    BEARING_16005 = auto()
    BEARING_16100 = auto()
    BEARING_16101 = auto()
    # shielded metric
    BEARING_608_ZZ = auto()
    BEARING_629_ZZ = auto()
    BEARING_635_ZZ = auto()
    BEARING_6000_ZZ = auto()
    BEARING_6001_ZZ = auto()
    BEARING_6002_ZZ = auto()
    BEARING_6003_ZZ = auto()
    BEARING_6007_ZZ = auto()
    BEARING_6200_ZZ = auto()
    BEARING_6201_ZZ = auto()
    BEARING_6202_ZZ = auto()
    BEARING_6203_ZZ = auto()
    BEARING_6204_ZZ = auto()
    BEARING_6205_ZZ = auto()
    BEARING_6206_ZZ = auto()
    BEARING_6207_ZZ = auto()
    BEARING_6208_ZZ = auto()
    BEARING_6209_ZZ = auto()
    BEARING_6210_ZZ = auto()
    BEARING_6211_ZZ = auto()
    BEARING_6212_ZZ = auto()
    BEARING_6301_ZZ = auto()
    BEARING_6302_ZZ = auto()
    BEARING_6303_ZZ = auto()
    BEARING_6304_ZZ = auto()
    BEARING_6305_ZZ = auto()
    BEARING_6306_ZZ = auto()
    BEARING_6307_ZZ = auto()
    BEARING_6308_ZZ = auto()
    BEARING_6309_ZZ = auto()
    BEARING_6310_ZZ = auto()
    BEARING_6311_ZZ = auto()
    BEARING_6312_ZZ = auto()
    BEARING_6403_ZZ = auto()
    BEARING_6800_ZZ = auto()
    BEARING_6801_ZZ = auto()
    BEARING_6802_ZZ = auto()
    BEARING_6803_ZZ = auto()
    BEARING_6804_ZZ = auto()
    BEARING_6805_ZZ = auto()
    BEARING_6806_ZZ = auto()
    BEARING_6900_ZZ = auto()
    BEARING_6901_ZZ = auto()
    BEARING_6902_ZZ = auto()
    BEARING_6903_ZZ = auto()
    BEARING_6904_ZZ = auto()
    BEARING_6905_ZZ = auto()
    BEARING_6906_ZZ = auto()
    BEARING_6907_ZZ = auto()
    BEARING_6908_ZZ = auto()
    BEARING_16002_ZZ = auto()
    BEARING_16004_ZZ = auto()
    BEARING_16005_ZZ = auto()
    BEARING_16100_ZZ = auto()
    BEARING_16101_ZZ = auto()

    @classmethod
    def of(cls, trade_name: str) -> BearingType:
        """Look up a :class:`BearingType` from its trade-name string (``"608"``, ``"R8ZZ"``)."""
        bt = _BY_TRADE_NAME.get(trade_name)
        if bt is not None:
            return bt
        raise ValueError(f"Unsupported ball bearing trade size: {trade_name!r}")


# Map trade-name strings to BearingType enum members.
# Derived from the enum member names: R8 -> "R8", BEARING_608 -> "608", BEARING_608_ZZ -> "608ZZ"
_BY_TRADE_NAME = {
    "R2": BearingType.R2,
    "R3": BearingType.R3,
    "R4": BearingType.R4,
    "R6": BearingType.R6,
    "R8": BearingType.R8,
    "R10": BearingType.R10,
    "R12": BearingType.R12,
    "R14": BearingType.R14,
    "R16": BearingType.R16,
    "R18": BearingType.R18,
    "R20": BearingType.R20,
    "R22": BearingType.R22,
    "R24": BearingType.R24,
    "R2ZZ": BearingType.R2_ZZ,
    "R3ZZ": BearingType.R3_ZZ,
    "R4ZZ": BearingType.R4_ZZ,
    "R6ZZ": BearingType.R6_ZZ,
    "R8ZZ": BearingType.R8_ZZ,
    "R10ZZ": BearingType.R10_ZZ,
    "R12ZZ": BearingType.R12_ZZ,
    "R14ZZ": BearingType.R14_ZZ,
    "R16ZZ": BearingType.R16_ZZ,
    "R18ZZ": BearingType.R18_ZZ,
    "R20ZZ": BearingType.R20_ZZ,
    "R22ZZ": BearingType.R22_ZZ,
    "R24ZZ": BearingType.R24_ZZ,
    "608": BearingType.BEARING_608,
    "629": BearingType.BEARING_629,
    "635": BearingType.BEARING_635,
    "6000": BearingType.BEARING_6000,
    "6001": BearingType.BEARING_6001,
    "6002": BearingType.BEARING_6002,
    "6003": BearingType.BEARING_6003,
    "6007": BearingType.BEARING_6007,
    "6200": BearingType.BEARING_6200,
    "6201": BearingType.BEARING_6201,
    "6202": BearingType.BEARING_6202,
    "6203": BearingType.BEARING_6203,
    "6204": BearingType.BEARING_6204,
    "6205": BearingType.BEARING_6205,
    "6206": BearingType.BEARING_6206,
    "6207": BearingType.BEARING_6207,
    "6208": BearingType.BEARING_6208,
    "6209": BearingType.BEARING_6209,
    "6210": BearingType.BEARING_6210,
    "6211": BearingType.BEARING_6211,
    "6212": BearingType.BEARING_6212,
    "6301": BearingType.BEARING_6301,
    "6302": BearingType.BEARING_6302,
    "6303": BearingType.BEARING_6303,
    "6304": BearingType.BEARING_6304,
    "6305": BearingType.BEARING_6305,
    "6306": BearingType.BEARING_6306,
    "6307": BearingType.BEARING_6307,
    "6308": BearingType.BEARING_6308,
    "6309": BearingType.BEARING_6309,
    "6310": BearingType.BEARING_6310,
    "6311": BearingType.BEARING_6311,
    "6312": BearingType.BEARING_6312,
    "6403": BearingType.BEARING_6403,
    "6800": BearingType.BEARING_6800,
    "6801": BearingType.BEARING_6801,
    "6802": BearingType.BEARING_6802,
    "6803": BearingType.BEARING_6803,
    "6804": BearingType.BEARING_6804,
    "6805": BearingType.BEARING_6805,
    "6806": BearingType.BEARING_6806,
    "6900": BearingType.BEARING_6900,
    "6901": BearingType.BEARING_6901,
    "6902": BearingType.BEARING_6902,
    "6903": BearingType.BEARING_6903,
    "6904": BearingType.BEARING_6904,
    "6905": BearingType.BEARING_6905,
    "6906": BearingType.BEARING_6906,
    "6907": BearingType.BEARING_6907,
    "6908": BearingType.BEARING_6908,
    "16002": BearingType.BEARING_16002,
    "16004": BearingType.BEARING_16004,
    "16005": BearingType.BEARING_16005,
    "16100": BearingType.BEARING_16100,
    "16101": BearingType.BEARING_16101,
    "608ZZ": BearingType.BEARING_608_ZZ,
    "629ZZ": BearingType.BEARING_629_ZZ,
    "635ZZ": BearingType.BEARING_635_ZZ,
    "6000ZZ": BearingType.BEARING_6000_ZZ,
    "6001ZZ": BearingType.BEARING_6001_ZZ,
    "6002ZZ": BearingType.BEARING_6002_ZZ,
    "6003ZZ": BearingType.BEARING_6003_ZZ,
    "6007ZZ": BearingType.BEARING_6007_ZZ,
    "6200ZZ": BearingType.BEARING_6200_ZZ,
    "6201ZZ": BearingType.BEARING_6201_ZZ,
    "6202ZZ": BearingType.BEARING_6202_ZZ,
    "6203ZZ": BearingType.BEARING_6203_ZZ,
    "6204ZZ": BearingType.BEARING_6204_ZZ,
    "6205ZZ": BearingType.BEARING_6205_ZZ,
    "6206ZZ": BearingType.BEARING_6206_ZZ,
    "6207ZZ": BearingType.BEARING_6207_ZZ,
    "6208ZZ": BearingType.BEARING_6208_ZZ,
    "6209ZZ": BearingType.BEARING_6209_ZZ,
    "6210ZZ": BearingType.BEARING_6210_ZZ,
    "6211ZZ": BearingType.BEARING_6211_ZZ,
    "6212ZZ": BearingType.BEARING_6212_ZZ,
    "6301ZZ": BearingType.BEARING_6301_ZZ,
    "6302ZZ": BearingType.BEARING_6302_ZZ,
    "6303ZZ": BearingType.BEARING_6303_ZZ,
    "6304ZZ": BearingType.BEARING_6304_ZZ,
    "6305ZZ": BearingType.BEARING_6305_ZZ,
    "6306ZZ": BearingType.BEARING_6306_ZZ,
    "6307ZZ": BearingType.BEARING_6307_ZZ,
    "6308ZZ": BearingType.BEARING_6308_ZZ,
    "6309ZZ": BearingType.BEARING_6309_ZZ,
    "6310ZZ": BearingType.BEARING_6310_ZZ,
    "6311ZZ": BearingType.BEARING_6311_ZZ,
    "6312ZZ": BearingType.BEARING_6312_ZZ,
    "6403ZZ": BearingType.BEARING_6403_ZZ,
    "6800ZZ": BearingType.BEARING_6800_ZZ,
    "6801ZZ": BearingType.BEARING_6801_ZZ,
    "6802ZZ": BearingType.BEARING_6802_ZZ,
    "6803ZZ": BearingType.BEARING_6803_ZZ,
    "6804ZZ": BearingType.BEARING_6804_ZZ,
    "6805ZZ": BearingType.BEARING_6805_ZZ,
    "6806ZZ": BearingType.BEARING_6806_ZZ,
    "6900ZZ": BearingType.BEARING_6900_ZZ,
    "6901ZZ": BearingType.BEARING_6901_ZZ,
    "6902ZZ": BearingType.BEARING_6902_ZZ,
    "6903ZZ": BearingType.BEARING_6903_ZZ,
    "6904ZZ": BearingType.BEARING_6904_ZZ,
    "6905ZZ": BearingType.BEARING_6905_ZZ,
    "6906ZZ": BearingType.BEARING_6906_ZZ,
    "6907ZZ": BearingType.BEARING_6907_ZZ,
    "6908ZZ": BearingType.BEARING_6908_ZZ,
    "16002ZZ": BearingType.BEARING_16002_ZZ,
    "16004ZZ": BearingType.BEARING_16004_ZZ,
    "16005ZZ": BearingType.BEARING_16005_ZZ,
    "16100ZZ": BearingType.BEARING_16100_ZZ,
    "16101ZZ": BearingType.BEARING_16101_ZZ,
}


@dataclass(frozen=True)
class BearingSpec:
    """Tabulated dimensions of a standard ball-bearing cartridge.

    Returned by :meth:`BallBearings.ball_bearing_info` when looking up a
    :class:`BearingType` trade size.
    """

    inner_diameter: float  # inner (shaft) diameter
    outer_diameter: float  # outer diameter
    width: float  # axial width
    shielded: bool  # True for a sealed/shielded (ZZ) cartridge


_I = INCH
# BearingType -> BearingSpec, transcribed from ball_bearings.scad.
_BEARINGS: dict[BearingType, BearingSpec] = {
    BearingType.R2: BearingSpec(1 / 8 * _I, 3 / 8 * _I, 5 / 32 * _I, False),
    BearingType.R3: BearingSpec(3 / 16 * _I, 1 / 2 * _I, 5 / 32 * _I, False),
    BearingType.R4: BearingSpec(1 / 4 * _I, 5 / 8 * _I, 0.196 * _I, False),
    BearingType.R6: BearingSpec(3 / 8 * _I, 7 / 8 * _I, 7 / 32 * _I, False),
    BearingType.R8: BearingSpec(1 / 2 * _I, 9 / 8 * _I, 1 / 4 * _I, False),
    BearingType.R10: BearingSpec(5 / 8 * _I, 11 / 8 * _I, 9 / 32 * _I, False),
    BearingType.R12: BearingSpec(3 / 4 * _I, 13 / 8 * _I, 5 / 16 * _I, False),
    BearingType.R14: BearingSpec(7 / 8 * _I, 15 / 8 * _I, 3 / 8 * _I, False),
    BearingType.R16: BearingSpec(8 / 8 * _I, 16 / 8 * _I, 3 / 8 * _I, False),
    BearingType.R18: BearingSpec(9 / 8 * _I, 17 / 8 * _I, 3 / 8 * _I, False),
    BearingType.R20: BearingSpec(10 / 8 * _I, 18 / 8 * _I, 3 / 8 * _I, False),
    BearingType.R22: BearingSpec(11 / 8 * _I, 20 / 8 * _I, 7 / 16 * _I, False),
    BearingType.R24: BearingSpec(12 / 8 * _I, 21 / 8 * _I, 7 / 16 * _I, False),
    BearingType.BEARING_608: BearingSpec(8, 22, 7, False),
    BearingType.BEARING_629: BearingSpec(9, 26, 8, False),
    BearingType.BEARING_635: BearingSpec(5, 19, 6, False),
    BearingType.BEARING_6000: BearingSpec(10, 26, 8, False),
    BearingType.BEARING_6001: BearingSpec(12, 28, 8, False),
    BearingType.BEARING_6002: BearingSpec(15, 32, 9, False),
    BearingType.BEARING_6003: BearingSpec(17, 35, 10, False),
    BearingType.BEARING_6007: BearingSpec(35, 62, 14, False),
    BearingType.BEARING_6200: BearingSpec(10, 30, 9, False),
    BearingType.BEARING_6201: BearingSpec(12, 32, 10, False),
    BearingType.BEARING_6202: BearingSpec(15, 35, 11, False),
    BearingType.BEARING_6203: BearingSpec(17, 40, 12, False),
    BearingType.BEARING_6204: BearingSpec(20, 47, 14, False),
    BearingType.BEARING_6205: BearingSpec(25, 52, 15, False),
    BearingType.BEARING_6206: BearingSpec(30, 62, 16, False),
    BearingType.BEARING_6207: BearingSpec(35, 72, 17, False),
    BearingType.BEARING_6208: BearingSpec(40, 80, 18, False),
    BearingType.BEARING_6209: BearingSpec(45, 85, 19, False),
    BearingType.BEARING_6210: BearingSpec(50, 90, 20, False),
    BearingType.BEARING_6211: BearingSpec(55, 100, 21, False),
    BearingType.BEARING_6212: BearingSpec(60, 110, 22, False),
    BearingType.BEARING_6301: BearingSpec(12, 37, 12, False),
    BearingType.BEARING_6302: BearingSpec(15, 42, 13, False),
    BearingType.BEARING_6303: BearingSpec(17, 47, 14, False),
    BearingType.BEARING_6304: BearingSpec(20, 52, 15, False),
    BearingType.BEARING_6305: BearingSpec(25, 62, 17, False),
    BearingType.BEARING_6306: BearingSpec(30, 72, 19, False),
    BearingType.BEARING_6307: BearingSpec(35, 80, 21, False),
    BearingType.BEARING_6308: BearingSpec(40, 90, 23, False),
    BearingType.BEARING_6309: BearingSpec(45, 100, 25, False),
    BearingType.BEARING_6310: BearingSpec(50, 110, 27, False),
    BearingType.BEARING_6311: BearingSpec(55, 120, 29, False),
    BearingType.BEARING_6312: BearingSpec(60, 130, 31, False),
    BearingType.BEARING_6403: BearingSpec(17, 62, 17, False),
    BearingType.BEARING_6800: BearingSpec(10, 19, 5, False),
    BearingType.BEARING_6801: BearingSpec(12, 21, 5, False),
    BearingType.BEARING_6802: BearingSpec(15, 24, 5, False),
    BearingType.BEARING_6803: BearingSpec(17, 26, 5, False),
    BearingType.BEARING_6804: BearingSpec(20, 32, 7, False),
    BearingType.BEARING_6805: BearingSpec(25, 37, 7, False),
    BearingType.BEARING_6806: BearingSpec(30, 42, 7, False),
    BearingType.BEARING_6900: BearingSpec(10, 22, 6, False),
    BearingType.BEARING_6901: BearingSpec(12, 24, 6, False),
    BearingType.BEARING_6902: BearingSpec(15, 28, 7, False),
    BearingType.BEARING_6903: BearingSpec(17, 30, 7, False),
    BearingType.BEARING_6904: BearingSpec(20, 37, 9, False),
    BearingType.BEARING_6905: BearingSpec(25, 42, 9, False),
    BearingType.BEARING_6906: BearingSpec(30, 47, 9, False),
    BearingType.BEARING_6907: BearingSpec(35, 55, 10, False),
    BearingType.BEARING_6908: BearingSpec(40, 62, 12, False),
    BearingType.BEARING_16002: BearingSpec(15, 22, 8, False),
    BearingType.BEARING_16004: BearingSpec(20, 42, 8, False),
    BearingType.BEARING_16005: BearingSpec(25, 47, 8, False),
    BearingType.BEARING_16100: BearingSpec(10, 28, 8, False),
    BearingType.BEARING_16101: BearingSpec(12, 30, 8, False),
}
# Add the "...ZZ" shielded variants, sharing the open variant's dimensions.
_ZZ_BEARINGS = {
    BearingType.R2_ZZ: BearingSpec(
        _BEARINGS[BearingType.R2].inner_diameter,
        _BEARINGS[BearingType.R2].outer_diameter,
        _BEARINGS[BearingType.R2].width,
        True,
    ),
    BearingType.R3_ZZ: BearingSpec(
        _BEARINGS[BearingType.R3].inner_diameter,
        _BEARINGS[BearingType.R3].outer_diameter,
        _BEARINGS[BearingType.R3].width,
        True,
    ),
    BearingType.R4_ZZ: BearingSpec(
        _BEARINGS[BearingType.R4].inner_diameter,
        _BEARINGS[BearingType.R4].outer_diameter,
        _BEARINGS[BearingType.R4].width,
        True,
    ),
    BearingType.R6_ZZ: BearingSpec(
        _BEARINGS[BearingType.R6].inner_diameter,
        _BEARINGS[BearingType.R6].outer_diameter,
        _BEARINGS[BearingType.R6].width,
        True,
    ),
    BearingType.R8_ZZ: BearingSpec(
        _BEARINGS[BearingType.R8].inner_diameter,
        _BEARINGS[BearingType.R8].outer_diameter,
        _BEARINGS[BearingType.R8].width,
        True,
    ),
    BearingType.R10_ZZ: BearingSpec(
        _BEARINGS[BearingType.R10].inner_diameter,
        _BEARINGS[BearingType.R10].outer_diameter,
        _BEARINGS[BearingType.R10].width,
        True,
    ),
    BearingType.R12_ZZ: BearingSpec(
        _BEARINGS[BearingType.R12].inner_diameter,
        _BEARINGS[BearingType.R12].outer_diameter,
        _BEARINGS[BearingType.R12].width,
        True,
    ),
    BearingType.R14_ZZ: BearingSpec(
        _BEARINGS[BearingType.R14].inner_diameter,
        _BEARINGS[BearingType.R14].outer_diameter,
        _BEARINGS[BearingType.R14].width,
        True,
    ),
    BearingType.R16_ZZ: BearingSpec(
        _BEARINGS[BearingType.R16].inner_diameter,
        _BEARINGS[BearingType.R16].outer_diameter,
        _BEARINGS[BearingType.R16].width,
        True,
    ),
    BearingType.R18_ZZ: BearingSpec(
        _BEARINGS[BearingType.R18].inner_diameter,
        _BEARINGS[BearingType.R18].outer_diameter,
        _BEARINGS[BearingType.R18].width,
        True,
    ),
    BearingType.R20_ZZ: BearingSpec(
        _BEARINGS[BearingType.R20].inner_diameter,
        _BEARINGS[BearingType.R20].outer_diameter,
        _BEARINGS[BearingType.R20].width,
        True,
    ),
    BearingType.R22_ZZ: BearingSpec(
        _BEARINGS[BearingType.R22].inner_diameter,
        _BEARINGS[BearingType.R22].outer_diameter,
        _BEARINGS[BearingType.R22].width,
        True,
    ),
    BearingType.R24_ZZ: BearingSpec(
        _BEARINGS[BearingType.R24].inner_diameter,
        _BEARINGS[BearingType.R24].outer_diameter,
        _BEARINGS[BearingType.R24].width,
        True,
    ),
    BearingType.BEARING_608_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_608].inner_diameter,
        _BEARINGS[BearingType.BEARING_608].outer_diameter,
        _BEARINGS[BearingType.BEARING_608].width,
        True,
    ),
    BearingType.BEARING_629_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_629].inner_diameter,
        _BEARINGS[BearingType.BEARING_629].outer_diameter,
        _BEARINGS[BearingType.BEARING_629].width,
        True,
    ),
    BearingType.BEARING_635_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_635].inner_diameter,
        _BEARINGS[BearingType.BEARING_635].outer_diameter,
        _BEARINGS[BearingType.BEARING_635].width,
        True,
    ),
    BearingType.BEARING_6000_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6000].inner_diameter,
        _BEARINGS[BearingType.BEARING_6000].outer_diameter,
        _BEARINGS[BearingType.BEARING_6000].width,
        True,
    ),
    BearingType.BEARING_6001_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6001].inner_diameter,
        _BEARINGS[BearingType.BEARING_6001].outer_diameter,
        _BEARINGS[BearingType.BEARING_6001].width,
        True,
    ),
    BearingType.BEARING_6002_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6002].inner_diameter,
        _BEARINGS[BearingType.BEARING_6002].outer_diameter,
        _BEARINGS[BearingType.BEARING_6002].width,
        True,
    ),
    BearingType.BEARING_6003_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6003].inner_diameter,
        _BEARINGS[BearingType.BEARING_6003].outer_diameter,
        _BEARINGS[BearingType.BEARING_6003].width,
        True,
    ),
    BearingType.BEARING_6007_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6007].inner_diameter,
        _BEARINGS[BearingType.BEARING_6007].outer_diameter,
        _BEARINGS[BearingType.BEARING_6007].width,
        True,
    ),
    BearingType.BEARING_6200_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6200].inner_diameter,
        _BEARINGS[BearingType.BEARING_6200].outer_diameter,
        _BEARINGS[BearingType.BEARING_6200].width,
        True,
    ),
    BearingType.BEARING_6201_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6201].inner_diameter,
        _BEARINGS[BearingType.BEARING_6201].outer_diameter,
        _BEARINGS[BearingType.BEARING_6201].width,
        True,
    ),
    BearingType.BEARING_6202_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6202].inner_diameter,
        _BEARINGS[BearingType.BEARING_6202].outer_diameter,
        _BEARINGS[BearingType.BEARING_6202].width,
        True,
    ),
    BearingType.BEARING_6203_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6203].inner_diameter,
        _BEARINGS[BearingType.BEARING_6203].outer_diameter,
        _BEARINGS[BearingType.BEARING_6203].width,
        True,
    ),
    BearingType.BEARING_6204_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6204].inner_diameter,
        _BEARINGS[BearingType.BEARING_6204].outer_diameter,
        _BEARINGS[BearingType.BEARING_6204].width,
        True,
    ),
    BearingType.BEARING_6205_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6205].inner_diameter,
        _BEARINGS[BearingType.BEARING_6205].outer_diameter,
        _BEARINGS[BearingType.BEARING_6205].width,
        True,
    ),
    BearingType.BEARING_6206_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6206].inner_diameter,
        _BEARINGS[BearingType.BEARING_6206].outer_diameter,
        _BEARINGS[BearingType.BEARING_6206].width,
        True,
    ),
    BearingType.BEARING_6207_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6207].inner_diameter,
        _BEARINGS[BearingType.BEARING_6207].outer_diameter,
        _BEARINGS[BearingType.BEARING_6207].width,
        True,
    ),
    BearingType.BEARING_6208_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6208].inner_diameter,
        _BEARINGS[BearingType.BEARING_6208].outer_diameter,
        _BEARINGS[BearingType.BEARING_6208].width,
        True,
    ),
    BearingType.BEARING_6209_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6209].inner_diameter,
        _BEARINGS[BearingType.BEARING_6209].outer_diameter,
        _BEARINGS[BearingType.BEARING_6209].width,
        True,
    ),
    BearingType.BEARING_6210_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6210].inner_diameter,
        _BEARINGS[BearingType.BEARING_6210].outer_diameter,
        _BEARINGS[BearingType.BEARING_6210].width,
        True,
    ),
    BearingType.BEARING_6211_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6211].inner_diameter,
        _BEARINGS[BearingType.BEARING_6211].outer_diameter,
        _BEARINGS[BearingType.BEARING_6211].width,
        True,
    ),
    BearingType.BEARING_6212_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6212].inner_diameter,
        _BEARINGS[BearingType.BEARING_6212].outer_diameter,
        _BEARINGS[BearingType.BEARING_6212].width,
        True,
    ),
    BearingType.BEARING_6301_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6301].inner_diameter,
        _BEARINGS[BearingType.BEARING_6301].outer_diameter,
        _BEARINGS[BearingType.BEARING_6301].width,
        True,
    ),
    BearingType.BEARING_6302_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6302].inner_diameter,
        _BEARINGS[BearingType.BEARING_6302].outer_diameter,
        _BEARINGS[BearingType.BEARING_6302].width,
        True,
    ),
    BearingType.BEARING_6303_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6303].inner_diameter,
        _BEARINGS[BearingType.BEARING_6303].outer_diameter,
        _BEARINGS[BearingType.BEARING_6303].width,
        True,
    ),
    BearingType.BEARING_6304_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6304].inner_diameter,
        _BEARINGS[BearingType.BEARING_6304].outer_diameter,
        _BEARINGS[BearingType.BEARING_6304].width,
        True,
    ),
    BearingType.BEARING_6305_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6305].inner_diameter,
        _BEARINGS[BearingType.BEARING_6305].outer_diameter,
        _BEARINGS[BearingType.BEARING_6305].width,
        True,
    ),
    BearingType.BEARING_6306_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6306].inner_diameter,
        _BEARINGS[BearingType.BEARING_6306].outer_diameter,
        _BEARINGS[BearingType.BEARING_6306].width,
        True,
    ),
    BearingType.BEARING_6307_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6307].inner_diameter,
        _BEARINGS[BearingType.BEARING_6307].outer_diameter,
        _BEARINGS[BearingType.BEARING_6307].width,
        True,
    ),
    BearingType.BEARING_6308_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6308].inner_diameter,
        _BEARINGS[BearingType.BEARING_6308].outer_diameter,
        _BEARINGS[BearingType.BEARING_6308].width,
        True,
    ),
    BearingType.BEARING_6309_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6309].inner_diameter,
        _BEARINGS[BearingType.BEARING_6309].outer_diameter,
        _BEARINGS[BearingType.BEARING_6309].width,
        True,
    ),
    BearingType.BEARING_6310_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6310].inner_diameter,
        _BEARINGS[BearingType.BEARING_6310].outer_diameter,
        _BEARINGS[BearingType.BEARING_6310].width,
        True,
    ),
    BearingType.BEARING_6311_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6311].inner_diameter,
        _BEARINGS[BearingType.BEARING_6311].outer_diameter,
        _BEARINGS[BearingType.BEARING_6311].width,
        True,
    ),
    BearingType.BEARING_6312_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6312].inner_diameter,
        _BEARINGS[BearingType.BEARING_6312].outer_diameter,
        _BEARINGS[BearingType.BEARING_6312].width,
        True,
    ),
    BearingType.BEARING_6403_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6403].inner_diameter,
        _BEARINGS[BearingType.BEARING_6403].outer_diameter,
        _BEARINGS[BearingType.BEARING_6403].width,
        True,
    ),
    BearingType.BEARING_6800_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6800].inner_diameter,
        _BEARINGS[BearingType.BEARING_6800].outer_diameter,
        _BEARINGS[BearingType.BEARING_6800].width,
        True,
    ),
    BearingType.BEARING_6801_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6801].inner_diameter,
        _BEARINGS[BearingType.BEARING_6801].outer_diameter,
        _BEARINGS[BearingType.BEARING_6801].width,
        True,
    ),
    BearingType.BEARING_6802_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6802].inner_diameter,
        _BEARINGS[BearingType.BEARING_6802].outer_diameter,
        _BEARINGS[BearingType.BEARING_6802].width,
        True,
    ),
    BearingType.BEARING_6803_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6803].inner_diameter,
        _BEARINGS[BearingType.BEARING_6803].outer_diameter,
        _BEARINGS[BearingType.BEARING_6803].width,
        True,
    ),
    BearingType.BEARING_6804_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6804].inner_diameter,
        _BEARINGS[BearingType.BEARING_6804].outer_diameter,
        _BEARINGS[BearingType.BEARING_6804].width,
        True,
    ),
    BearingType.BEARING_6805_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6805].inner_diameter,
        _BEARINGS[BearingType.BEARING_6805].outer_diameter,
        _BEARINGS[BearingType.BEARING_6805].width,
        True,
    ),
    BearingType.BEARING_6806_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6806].inner_diameter,
        _BEARINGS[BearingType.BEARING_6806].outer_diameter,
        _BEARINGS[BearingType.BEARING_6806].width,
        True,
    ),
    BearingType.BEARING_6900_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6900].inner_diameter,
        _BEARINGS[BearingType.BEARING_6900].outer_diameter,
        _BEARINGS[BearingType.BEARING_6900].width,
        True,
    ),
    BearingType.BEARING_6901_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6901].inner_diameter,
        _BEARINGS[BearingType.BEARING_6901].outer_diameter,
        _BEARINGS[BearingType.BEARING_6901].width,
        True,
    ),
    BearingType.BEARING_6902_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6902].inner_diameter,
        _BEARINGS[BearingType.BEARING_6902].outer_diameter,
        _BEARINGS[BearingType.BEARING_6902].width,
        True,
    ),
    BearingType.BEARING_6903_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6903].inner_diameter,
        _BEARINGS[BearingType.BEARING_6903].outer_diameter,
        _BEARINGS[BearingType.BEARING_6903].width,
        True,
    ),
    BearingType.BEARING_6904_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6904].inner_diameter,
        _BEARINGS[BearingType.BEARING_6904].outer_diameter,
        _BEARINGS[BearingType.BEARING_6904].width,
        True,
    ),
    BearingType.BEARING_6905_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6905].inner_diameter,
        _BEARINGS[BearingType.BEARING_6905].outer_diameter,
        _BEARINGS[BearingType.BEARING_6905].width,
        True,
    ),
    BearingType.BEARING_6906_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6906].inner_diameter,
        _BEARINGS[BearingType.BEARING_6906].outer_diameter,
        _BEARINGS[BearingType.BEARING_6906].width,
        True,
    ),
    BearingType.BEARING_6907_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6907].inner_diameter,
        _BEARINGS[BearingType.BEARING_6907].outer_diameter,
        _BEARINGS[BearingType.BEARING_6907].width,
        True,
    ),
    BearingType.BEARING_6908_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_6908].inner_diameter,
        _BEARINGS[BearingType.BEARING_6908].outer_diameter,
        _BEARINGS[BearingType.BEARING_6908].width,
        True,
    ),
    BearingType.BEARING_16002_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_16002].inner_diameter,
        _BEARINGS[BearingType.BEARING_16002].outer_diameter,
        _BEARINGS[BearingType.BEARING_16002].width,
        True,
    ),
    BearingType.BEARING_16004_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_16004].inner_diameter,
        _BEARINGS[BearingType.BEARING_16004].outer_diameter,
        _BEARINGS[BearingType.BEARING_16004].width,
        True,
    ),
    BearingType.BEARING_16005_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_16005].inner_diameter,
        _BEARINGS[BearingType.BEARING_16005].outer_diameter,
        _BEARINGS[BearingType.BEARING_16005].width,
        True,
    ),
    BearingType.BEARING_16100_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_16100].inner_diameter,
        _BEARINGS[BearingType.BEARING_16100].outer_diameter,
        _BEARINGS[BearingType.BEARING_16100].width,
        True,
    ),
    BearingType.BEARING_16101_ZZ: BearingSpec(
        _BEARINGS[BearingType.BEARING_16101].inner_diameter,
        _BEARINGS[BearingType.BEARING_16101].outer_diameter,
        _BEARINGS[BearingType.BEARING_16101].width,
        True,
    ),
}
_BEARINGS.update(_ZZ_BEARINGS)


class BallBearings:
    """Models of standard ball-bearing cartridges.

    Port of BOSL2's ``ball_bearings.scad``. Builds sealed/shielded or open bearings
    from a trade size or explicit dimensions.
    """

    @staticmethod
    def ball_bearing_info(trade_size: str | BearingType) -> BearingSpec:
        """Look up the tabulated dimensions for a trade-size bearing.

        Accepts a string name (``"608"``, ``"6902ZZ"``) or a :class:`BearingType` enum value,
        and returns the corresponding :class:`BearingSpec`.
        """
        if isinstance(trade_size, str):
            trade_size = BearingType.of(trade_size)
        try:
            return _BEARINGS[trade_size]
        except KeyError:
            raise ValueError(f"Unsupported ball bearing trade size: {trade_size!r}") from None

    @staticmethod
    def ball_bearing(
        trade_size: str | BearingType | None = None,
        inner_diameter: float | None = None,
        outer_diameter: float | None = None,
        width: float | None = None,
        shield: bool = True,
        color: str | None = "silver",
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """Build a standard ball-bearing cartridge model.

        Give a *trade_size* name (or :class:`BearingType`), or explicit
        *inner_diameter*/*outer_diameter*/*width* (with *shield*). Returns a
        :class:`~pybosl2.shapes3d.Bosl2Solid` centered on the origin.

        Examples:
            A common 608 skate bearing:

            .. pythonscad-example::

                from pybosl2.ball_bearings import BearingType, BallBearings
                BallBearings.ball_bearing(BearingType.BEARING_608).show()
        """
        if trade_size is not None:
            if isinstance(trade_size, str):
                trade_size = BearingType.of(trade_size)
            spec = BallBearings.ball_bearing_info(trade_size)
            inner_diameter, outer_diameter, width, shield = (
                spec.inner_diameter,
                spec.outer_diameter,
                spec.width,
                spec.shielded,
            )
        if inner_diameter is None:
            raise ValueError("ball_bearing(): must give inner_diameter.")
        if outer_diameter is None:
            raise ValueError("ball_bearing(): must give outer_diameter.")
        if width is None:
            raise ValueError("ball_bearing(): must give width.")

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
            races = races - torus(major_radius=mid_d / 2, minor_radius=wall, fn=fn, fa=fa, fs=fs)
            balls = reduce(
                operator.or_,
                (
                    sphere(diameter=wall * 2, fn=fn, fa=fa, fs=fs).right(mid_d / 2).rotate([0, 0, i * 360 / ball_cnt])
                    for i in range(ball_cnt)
                ),
            )
            result = races | balls
        result = Bosl2Solid(result.shape, size=[outer_diameter, outer_diameter, width])
        return result.color(color) if color else result

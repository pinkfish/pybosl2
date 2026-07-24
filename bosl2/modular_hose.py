# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/modular_hose.py
#    Pure-Python port of BOSL2's modular_hose.scad: the ball-and-socket segments of a modular
#    coolant/adjustable hose (the "Loc-Line" style). :meth:`ModularHose.modular_hose` revolves a
#    ball end, a socket end, or a full segment for the 1/4", 1/2" or 3/4" sizes;
#    :meth:`~ModularHose.modular_hose_radius` gives the bore radius. The ball/socket cross-section
#    profiles are the same turtle paths BOSL2 uses.
#
# FileSummary: Modular (Loc-Line style) ball-and-socket hose segments.
# FileGroup: BOSL2

from __future__ import annotations

import math

from pythonscad import polygon as _opolygon, rotate_extrude as _orotate_extrude

from bosl2.drawing import turtle
from bosl2.shapes3d import Bosl2Solid

__all__ = ["ModularHose"]

_SQRT2 = math.sqrt(2)


def _ts(x):
    """Full turtle state starting at (x, 0) heading +X (this port's turtle needs full state)."""
    return [[[float(x), 0.0]], [1.0, 0.0], 90.0, 0.0]


def _tan(a):
    return math.tan(math.radians(a))


def _cos(a):
    return math.cos(math.radians(a))


def _sin(a):
    return math.sin(math.radians(a))


# Ball ("small") end cross-section, one per size (1/4", 1/2", 3/4"), from modular_hose.scad.
_SMALL_CMDS = [
    (
        [
            "left",
            90 - 38.5,
            "arcsteps",
            12,
            "arcleft",
            6.38493,
            62.15,
            "arcsteps",
            4,
            "arcleft",
            0.5,
            90 + 38.5 - 62.15,
            "move",
            0.76,
            "left",
            67.5,
            "move",
            0.47,
            "left",
            90 - 67.5,
            "move",
            4.165,
            "right",
            30,
            "move",
            2.1,
        ],
        4.864,
    ),
    (
        [
            "left",
            90 - 41,
            "arcsteps",
            16,
            "arcleft",
            10.7407,
            64.27,
            "arcsteps",
            4,
            "arcleft",
            0.5,
            90 + 41 - 64.27,
            "move",
            0.95 - 0.4,
            "left",
            45,
            "move",
            0.4 * _SQRT2,
            "left",
            45,
            "move",
            7.643 - 0.4,
            "right",
            30,
            "move",
            4.06,
        ],
        8.1,
    ),
    (
        [
            "left",
            90 - 30.4,
            "arcsteps",
            16,
            "arcleft",
            13.99219,
            53,
            "arcsteps",
            4,
            "arcleft",
            0.47,
            90 - 53 + 30.4,
            "move",
            0.597,
            "left",
            "move",
            9.908 - 1.905 / _tan(25) + 3.81 * _cos(30),
            "right",
            25,
            "move",
            1.905 / _sin(25),
        ],
        11.989,
    ),
]

# Socket ("big") end cross-section, one per size.
_BIG_CMDS = [
    (
        [
            "left",
            90 - 22,
            "move",
            6.5,
            "left",
            0.75,
            "arcsteps",
            8,
            "arcleft",
            6.5,
            37.3,
            "setdir",
            90,
            "move",
            0.21,
            "right",
            "move",
            1.24,
            "right",
            45,
            "move",
            0.7835,
            "right",
            19,
            "move",
            1.05,
            "setdir",
            -90,
            "move",
            1,
            "right",
            22,
            "move",
            8.76,
        ],
        3.268,
    ),
    (
        [
            "left",
            "right",
            22,
            "move",
            9,
            "arcsteps",
            8,
            "arcleft",
            11,
            36.5,
            "setdir",
            90,
            "move",
            2 - 1.366,
            "right",
            "move",
            0.91,
            "arcsteps",
            4,
            "arcright",
            1.25,
            90,
            "move",
            2.2,
            "arcsteps",
            8,
            "arcright",
            13,
            22.4,
            "move",
            8.73,
        ],
        6.42154,
    ),
    (
        [
            "left",
            90 - 22,
            "move",
            7.633,
            "arcsteps",
            16,
            "arcleft",
            13.77,
            35.27,
            "setdir",
            90,
            "move",
            1.09,
            "right",
            "move",
            1.0177,
            "right",
            45,
            "move",
            1.009,
            "right",
            77.8 - 45,
            "move",
            0.3,
            "arcright",
            15.5,
            34.2,
            "move",
            6.47,
        ],
        9.90237,
    ),
]

_WAIST = [1.7698, 1.8251, 3.95998]
_SIZES = {0.25: 0, 0.5: 1, 0.75: 2}

_SMALL = [
    [[float(x), float(y)] for x, y in turtle(cmds, state=_ts(x0))]
    for cmds, x0 in _SMALL_CMDS
]
_BIG = [
    [[float(x), float(y)] for x, y in turtle(cmds, state=_ts(x0))]
    for cmds, x0 in _BIG_CMDS
]


def _bounds(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys)), (max(xs), max(ys))


def _size_index(size):
    try:
        return _SIZES[size]
    except KeyError:
        raise ValueError(
            'modular_hose(): size must be 0.25, 0.5 or 0.75 (1/4", 1/2", 3/4").'
        )


class ModularHose:
    """Modular ball-and-socket hose segments (BOSL2 modular_hose.scad)."""

    @staticmethod
    def modular_hose(
        size: float,
        type: str = "segment",
        clearance: float | list = 0,
        waist_len: float | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """A modular-hose ball end, socket end, or full segment (BOSL2 modular_hose()).

        *size* is 0.25, 0.5 or 0.75 (the 1/4", 1/2", 3/4" hose families). *type* is ``"ball"``/
        ``"small"`` (the ball end), ``"socket"``/``"big"`` (the socket end), or ``"segment"`` (a full
        segment with a ball on one end and a socket on the other). *clearance* loosens the fit.

        Examples:
            A 1/2" hose segment:

            .. pythonscad-example::

                from bosl2.modular_hose import ModularHose
                ModularHose.modular_hose(0.5, "segment").show()
        """
        ind = _size_index(size)
        cl = (
            clearance
            if isinstance(clearance, (list, tuple))
            else [clearance, clearance]
        )
        small, big = _SMALL[ind], _BIG[ind]
        (_sx, smy), _ = _bounds(small)
        (_bx, bmy), _ = _bounds(big)
        smallend = [[x - cl[0], y - smy] for x, y in small]  # normalize base to y=0
        bigend = [[x + cl[1], y - bmy] for x, y in big]
        mid = _WAIST[ind] if waist_len is None else waist_len
        assert mid >= 0, "waist_len must be nonnegative."

        if type == "segment":
            shape = [[x, y + mid] for x, y in smallend] + [[x, -y] for x, y in bigend]
        elif type in ("small", "ball"):
            shape = [[x, y + mid] for x, y in smallend] + [
                [smallend[-1][0], 0],
                [smallend[0][0], 0],
            ]
        elif type in ("big", "socket"):
            shape = [[x, y + mid] for x, y in bigend] + [
                [bigend[-1][0], 0],
                [bigend[0][0], 0],
            ]
        else:
            raise ValueError(
                "modular_hose(): type must be one of small/big/segment/socket/ball."
            )

        (_mnx, mny), (mxx, mxy) = _bounds(shape)
        cy = (mny + mxy) / 2
        poly = [[x, y - cy] for x, y in shape]
        solid = _orotate_extrude(_opolygon(poly), fn=fn, fa=fa, fs=fs)
        return Bosl2Solid(solid, size=[2 * mxx, 2 * mxx, mxy - mny])

    @staticmethod
    def modular_hose_radius(size: float, outer: bool = False) -> float:
        """The inner (bore) or *outer* radius of a modular hose of *size* (BOSL2 modular_hose_radius())."""
        big = _BIG[_size_index(size)]
        return big[-1][0] if outer else big[0][0]

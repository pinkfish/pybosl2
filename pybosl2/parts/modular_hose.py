# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/parts/modular_hose.py
#    Pure-Python port of BOSL2's modular_hose.scad: the ball-and-socket segments of a modular
#    coolant/adjustable hose (the "Loc-Line" style). :meth:`ModularHose.modular_hose` revolves a
#    ball end, a socket end, or a full segment for the 1/4", 1/2" or 3/4" sizes;
#    :meth:`~ModularHose.modular_hose_radius` gives the bore radius. The ball/socket cross-section
#    profiles are the same turtle paths BOSL2 uses.
#
# FileSummary: Modular (Loc-Line style) ball-and-socket hose segments.
# DocCategory: Parts library
# FileGroup: BOSL2

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pybosl2._native import native
from pybosl2.shapes3d import Bosl2Solid
from pybosl2.turtle import Turtle2DState, TurtleCommand, turtle2d
from pybosl2.turtle import TurtleCommandType as TCT  # noqa: N817

if TYPE_CHECKING:  # real stub-typed imports for the checker (identical to pre-lazy)
    from pythonscad import polygon as _opolygon
    from pythonscad import rotate_extrude as _orotate_extrude
else:
    _opolygon = native("polygon")
    _orotate_extrude = native("rotate_extrude")

__all__ = ["ModularHose"]

_SQRT2 = math.sqrt(2)


def _ts(x: float) -> Turtle2DState:
    """Full turtle state starting at (x, 0) heading +X."""
    return Turtle2DState(path=[[float(x), 0.0]])


# Ball ("small") end cross-section, one per size (1/4", 1/2", 3/4"), from modular_hose.scad.
_SMALL_CMDS = [
    (
        [
            TurtleCommand(TCT.LEFT, angle=90 - 38.5),
            TurtleCommand(TCT.ARCSTEPS, size=12),
            TurtleCommand(TCT.ARCLEFT, radius=6.38493, angle=62.15),
            TurtleCommand(TCT.ARCSTEPS, size=4),
            TurtleCommand(TCT.ARCLEFT, radius=0.5, angle=90 + 38.5 - 62.15),
            TurtleCommand(TCT.MOVE, size=0.76),
            TurtleCommand(TCT.LEFT, angle=67.5),
            TurtleCommand(TCT.MOVE, size=0.47),
            TurtleCommand(TCT.LEFT, angle=90 - 67.5),
            TurtleCommand(TCT.MOVE, size=4.165),
            TurtleCommand(TCT.RIGHT, angle=30),
            TurtleCommand(TCT.MOVE, size=2.1),
        ],
        4.864,
    ),
    (
        [
            TurtleCommand(TCT.LEFT, angle=90 - 41),
            TurtleCommand(TCT.ARCSTEPS, size=16),
            TurtleCommand(TCT.ARCLEFT, radius=10.7407, angle=64.27),
            TurtleCommand(TCT.ARCSTEPS, size=4),
            TurtleCommand(TCT.ARCLEFT, radius=0.5, angle=90 + 41 - 64.27),
            TurtleCommand(TCT.MOVE, size=0.95 - 0.4),
            TurtleCommand(TCT.LEFT, angle=45),
            TurtleCommand(TCT.MOVE, size=0.4 * _SQRT2),
            TurtleCommand(TCT.LEFT, angle=45),
            TurtleCommand(TCT.MOVE, size=7.643 - 0.4),
            TurtleCommand(TCT.RIGHT, angle=30),
            TurtleCommand(TCT.MOVE, size=4.06),
        ],
        8.1,
    ),
    (
        [
            TurtleCommand(TCT.LEFT, angle=90 - 30.4),
            TurtleCommand(TCT.ARCSTEPS, size=16),
            TurtleCommand(TCT.ARCLEFT, radius=13.99219, angle=53),
            TurtleCommand(TCT.ARCSTEPS, size=4),
            TurtleCommand(TCT.ARCLEFT, radius=0.47, angle=90 - 53 + 30.4),
            TurtleCommand(TCT.MOVE, size=0.597),
            TurtleCommand(TCT.LEFT),
            TurtleCommand(
                TCT.MOVE,
                size=9.908 - 1.905 / math.tan(math.radians(25)) + 3.81 * math.cos(math.radians(30)),
            ),
            TurtleCommand(TCT.RIGHT, angle=25),
            TurtleCommand(TCT.MOVE, size=1.905 / math.sin(math.radians(25))),
        ],
        11.989,
    ),
]

# Socket ("big") end cross-section, one per size.
_BIG_CMDS = [
    (
        [
            TurtleCommand(TCT.LEFT, angle=90 - 22),
            TurtleCommand(TCT.MOVE, size=6.5),
            TurtleCommand(TCT.LEFT, angle=0.75),
            TurtleCommand(TCT.ARCSTEPS, size=8),
            TurtleCommand(TCT.ARCLEFT, radius=6.5, angle=37.3),
            TurtleCommand(TCT.SETDIR, size=90),
            TurtleCommand(TCT.MOVE, size=0.21),
            TurtleCommand(TCT.RIGHT),
            TurtleCommand(TCT.MOVE, size=1.24),
            TurtleCommand(TCT.RIGHT, angle=45),
            TurtleCommand(TCT.MOVE, size=0.7835),
            TurtleCommand(TCT.RIGHT, angle=19),
            TurtleCommand(TCT.MOVE, size=1.05),
            TurtleCommand(TCT.SETDIR, size=-90),
            TurtleCommand(TCT.MOVE, size=1),
            TurtleCommand(TCT.RIGHT, angle=22),
            TurtleCommand(TCT.MOVE, size=8.76),
        ],
        3.268,
    ),
    (
        [
            TurtleCommand(TCT.LEFT),
            TurtleCommand(TCT.RIGHT, angle=22),
            TurtleCommand(TCT.MOVE, size=9),
            TurtleCommand(TCT.ARCSTEPS, size=8),
            TurtleCommand(TCT.ARCLEFT, radius=11, angle=36.5),
            TurtleCommand(TCT.SETDIR, size=90),
            TurtleCommand(TCT.MOVE, size=2 - 1.366),
            TurtleCommand(TCT.RIGHT),
            TurtleCommand(TCT.MOVE, size=0.91),
            TurtleCommand(TCT.ARCSTEPS, size=4),
            TurtleCommand(TCT.ARCRIGHT, radius=1.25, angle=90),
            TurtleCommand(TCT.MOVE, size=2.2),
            TurtleCommand(TCT.ARCSTEPS, size=8),
            TurtleCommand(TCT.ARCRIGHT, radius=13, angle=22.4),
            TurtleCommand(TCT.MOVE, size=8.73),
        ],
        6.42154,
    ),
    (
        [
            TurtleCommand(TCT.LEFT, angle=90 - 22),
            TurtleCommand(TCT.MOVE, size=7.633),
            TurtleCommand(TCT.ARCSTEPS, size=16),
            TurtleCommand(TCT.ARCLEFT, radius=13.77, angle=35.27),
            TurtleCommand(TCT.SETDIR, size=90),
            TurtleCommand(TCT.MOVE, size=1.09),
            TurtleCommand(TCT.RIGHT),
            TurtleCommand(TCT.MOVE, size=1.0177),
            TurtleCommand(TCT.RIGHT, angle=45),
            TurtleCommand(TCT.MOVE, size=1.009),
            TurtleCommand(TCT.RIGHT, angle=77.8 - 45),
            TurtleCommand(TCT.MOVE, size=0.3),
            TurtleCommand(TCT.ARCRIGHT, radius=15.5, angle=34.2),
            TurtleCommand(TCT.MOVE, size=6.47),
        ],
        9.90237,
    ),
]

_WAIST = [1.7698, 1.8251, 3.95998]
_SIZES = {0.25: 0, 0.5: 1, 0.75: 2}
_SMALL = [[[float(x), float(y)] for x, y in turtle2d(cmds, state=_ts(x0)).points()] for cmds, x0 in _SMALL_CMDS]

_BIG = [[[float(x), float(y)] for x, y in turtle2d(cmds, state=_ts(x0)).points()] for cmds, x0 in _BIG_CMDS]


def _bounds(pts: list[list[float]]) -> tuple[tuple[float, float], tuple[float, float]]:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys)), (max(xs), max(ys))


def _size_index(size: float) -> int:
    try:
        return _SIZES[size]
    except KeyError:
        raise ValueError('modular_hose(): size must be 0.25, 0.5 or 0.75 (1/4", 1/2", 3/4").') from None


class ModularHose:
    """Modular ball-and-socket hose segments (BOSL2 modular_hose.scad).

    .. seealso::

       `Visual spec sheet <specs/modular_hose.html>`_ — measurements and STL previews
    """

    @staticmethod
    def modular_hose(
        size: float,
        type: str = "segment",  # noqa: A002
        clearance: float | list[float] = 0,
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

                from pybosl2.parts.modular_hose import ModularHose
                ModularHose.modular_hose(0.5, "segment").show()
        """
        ind = _size_index(size)
        cl = clearance if isinstance(clearance, (list, tuple)) else [clearance, clearance]
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
            raise ValueError("modular_hose(): type must be one of small/big/segment/socket/ball.")

        (_mnx, mny), (mxx, mxy) = _bounds(shape)
        cy = (mny + mxy) / 2
        poly = [[x, y - cy] for x, y in shape]
        solid = _orotate_extrude(_opolygon(poly), fn=fn, fa=fa, fs=fs)
        return Bosl2Solid(solid, size=[2 * mxx, 2 * mxx, mxy - mny])

    @staticmethod
    def modular_hose_radius(size: float, outer: bool = False) -> float:
        """
        The inner (bore) or *outer* radius of a modular hose of *size* (BOSL2
        modular_hose_radius()).
        """
        big = _BIG[_size_index(size)]
        return big[-1][0] if outer else big[0][0]

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/parts/modular_hose.py
#    Pure-Python port of BOSL2's modular_hose.scad: the ball-and-socket segments of a modular
#    coolant/adjustable hose (the "Loc-Line" style). :class:`HoseSegment` revolves a
#    ball end, a socket end, or a full segment for the 1/4", 1/2" or 3/4" sizes;
#    :func:`modular_hose_radius` gives the bore radius. The ball/socket cross-section
#    profiles are the same turtle paths BOSL2 uses.
#
# FileSummary: Modular (Loc-Line style) ball-and-socket hose segments.
# DocCategory: Parts library
# FileGroup: BOSL2

"""Modular (Loc-Line style) ball-and-socket hose segments."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import TYPE_CHECKING

from pybosl2.exceptions import Bosl2ValueError
from pybosl2.parts._buildable import Buildable
from pybosl2.path2d import Path2D
from pybosl2.turtle import Turtle2DState, TurtleCommand, turtle2d
from pybosl2.turtle import TurtleCommandType as TCT  # noqa: N817

if TYPE_CHECKING:
    from pybosl2._backend import Solid


__all__ = ["HoseSegment", "HoseType", "modular_hose_radius"]


class HoseType(StrEnum):
    """Modular hose segment type."""

    BALL = "ball"
    SMALL = "small"
    SOCKET = "socket"
    BIG = "big"
    SEGMENT = "segment"


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
        raise Bosl2ValueError('modular_hose(): size must be 0.25, 0.5 or 0.75 (1/4", 1/2", 3/4").') from None


class HoseSegment(Buildable):
    """A modular-hose ball end, socket end, or full segment.

    *size* is 0.25, 0.5 or 0.75 (the 1/4", 1/2", 3/4" hose families).  *type*
    is a :class:`HoseType` enum value.  *clearance* loosens the fit.

    Examples:
        A 1/2" hose segment:

        .. pythonscad-example::

            from pybosl2.parts.modular_hose import HoseSegment, HoseType
            HoseSegment(0.5, HoseType.SEGMENT).show()

    """

    def __init__(
        self,
        size: float,
        type: HoseType = HoseType.SEGMENT,  # noqa: A002
        clearance: float | list[float] = 0,
        waist_len: float | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a modular-hose segment, ball end or socket end.

        Args:
            size: Hose size (0.25, 0.5 or 0.75 inches).
            type: Segment type as a :class:`HoseType` enum value.
            clearance: Clearance for fit tuning; a single float or ``[ball_clearance, socket_clearance]``.
            waist_len: Length of the waist section between ball and socket; auto-derived if None.
            fn: Number of facets for $fn-based resolution.
            fa: Minimum facet angle.
            fs: Minimum facet size.

        Returns:
            None.

        Raises:
            ValueError: If *size* is not one of 0.25, 0.5, 0.75, or *type* is invalid.

        """
        ind = _size_index(size)
        cl = clearance if isinstance(clearance, (list, tuple)) else [clearance, clearance]
        small, big = _SMALL[ind], _BIG[ind]
        (_sx, smy), _ = _bounds(small)
        (_bx, bmy), _ = _bounds(big)
        smallend = [[x - cl[0], y - smy] for x, y in small]
        bigend = [[x + cl[1], y - bmy] for x, y in big]
        mid = _WAIST[ind] if waist_len is None else waist_len
        if not (mid >= 0):
            raise Bosl2ValueError("waist_len must be nonnegative.")

        if type in (HoseType.SEGMENT,):
            shape = [[x, y + mid] for x, y in smallend] + [[x, -y] for x, y in bigend]
        elif type in (HoseType.SMALL, HoseType.BALL):
            shape = [[x, y + mid] for x, y in smallend] + [
                [smallend[-1][0], 0],
                [smallend[0][0], 0],
            ]
        elif type in (HoseType.BIG, HoseType.SOCKET):
            shape = [[x, y + mid] for x, y in bigend] + [
                [bigend[-1][0], 0],
                [bigend[0][0], 0],
            ]
        else:
            raise Bosl2ValueError("modular_hose(): type must be one of BALL/SMALL/SOCKET/BIG/SEGMENT.")

        (_mnx, mny), (mxx, mxy) = _bounds(shape)
        cy = (mny + mxy) / 2
        poly = [[x, y - cy] for x, y in shape]
        # Path2D.rotate_extrude() dispatches through the backend; the native
        # polygon()/rotate_extrude() pair this used is CSG-only (TASKS T14).
        self._solid: "Solid" = (
            Path2D(poly).rotate_extrude(fn=fn, fa=fa, fs=fs).with_nominal_size([2 * mxx, 2 * mxx, mxy - mny])
        )
        self._size: float = size
        self._type: HoseType = type

    @property
    def size(self) -> float:
        """Hose size (0.25, 0.5 or 0.75 inches)."""
        return self._size

    @property
    def hose_type(self) -> HoseType:
        """Segment type."""
        return self._type

    @property
    def shape(self) -> "Solid":
        """Return the hose segment geometry."""
        return self._solid


def modular_hose_radius(size: float, outer: bool = False) -> float:
    """Return the inner (bore) or *outer* radius of a modular hose of *size*.

    Args:
        size: Hose size (0.25, 0.5 or 0.75 inches).
        outer: If True, return the outer radius instead of the inner (bore) radius.

    Returns:
        The bore or outer radius in mm for the given hose size.

    Raises:
        ValueError: If *size* is not one of 0.25, 0.5, 0.75.

    """
    big = _BIG[_size_index(size)]
    return big[-1][0] if outer else big[0][0]

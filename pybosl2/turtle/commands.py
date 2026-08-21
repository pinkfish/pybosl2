# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The turtle command language: the command names and the typed parameter bag that carries them.

Shared by the 2-D and 3-D turtles and by the method form in ``_fluent.py`` -- it lives in its own
module so all three can import it without importing each other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pybosl2.points import Point

__all__ = ["TurtleCommand", "TurtleCommandType"]


# Note: the TurtleCommandType enum has members named RIGHT, UP, etc. — the
# constants from pybosl2.constants are used only for math direction vectors.
# Use ``TurtleCommandType.RIGHT`` for the command enum, ``RIGHT`` for [1,0,0].


class TurtleCommandType(Enum):
    """Turtle movement command type."""

    MOVE = "move"
    UNTILX = "untilx"
    UNTILY = "untily"
    UNTILZ = "untilz"
    XMOVE = "xmove"
    YMOVE = "ymove"
    ZMOVE = "zmove"
    XYZMOVE = "xyzmove"
    JUMP = "jump"
    XJUMP = "xjump"
    YJUMP = "yjump"
    ZJUMP = "zjump"
    ANGLE = "angle"
    LENGTH = "length"
    SCALE = "scale"
    ADDLENGTH = "addlength"
    ARCSTEPS = "arcsteps"
    ROLL = "roll"
    RIGHT = "right"
    LEFT = "left"
    UP = "up"
    DOWN = "down"
    XROT = "xrot"
    YROT = "yrot"
    ZROT = "zrot"
    ROT = "rot"
    SETDIR = "setdir"
    ARCLEFT = "arcleft"
    ARCRIGHT = "arcright"
    ARCLEFTTO = "arcleftto"
    ARCRIGHTTO = "arcrightto"
    ARCUP = "arcup"
    ARCDOWN = "arcdown"
    ARCXROT = "arcxrot"
    ARCYROT = "arcyrot"
    ARCZROT = "arczrot"
    ARCTODIR = "arctodir"
    ARCROT = "arcrot"
    REPEAT = "repeat"
    ARC = "arc"


@dataclass
class TurtleCommand:
    """A single turtle command with its typed parameters.

    Compound ARC commands use ``angle`` to encode the rotation amount and
    ``rotation_type`` to indicate the axis.  Use :attr:`RotationType` members
    (e.g. ``TurtleCommand.RotationType.LEFT``).
    """

    class RotationType(Enum):
        """The rotation axis/direction for a compound ARC command."""

        NONE = ""
        LEFT = "left"
        RIGHT = "right"
        UP = "up"
        DOWN = "down"
        XROT = "xrot"
        YROT = "yrot"
        ZROT = "zrot"
        ROT = "rot"
        TODIR = "todir"

    cmd_type: TurtleCommandType
    size: float | Point | None = None
    angle: float | Point | None = None
    radius: float | None = None
    steps: int | None = None
    center: Point | None = None
    grow: float | Point | None = None
    shrink: float | Point | None = None
    twist: float | None = None
    roll: float | None = None
    reverse: bool = False
    rollto: Point | None = None
    rrollto: Point | None = None
    lrollto: Point | None = None
    is_compound: bool = False
    sub_commands: list[TurtleCommand] | None = None
    rotation_type: "RotationType" = field(default=RotationType.NONE)

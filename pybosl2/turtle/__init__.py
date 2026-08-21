# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Turtle-graphics path builders (2-D and 3-D).

Drive a turtle either way: as methods -- ``Turtle2D().move(40).arc_left(radius=8)``, one per
command via :class:`TurtleCommands` -- or by handing a list of :class:`TurtleCommand` objects to
:func:`turtle2d` / :func:`turtle3d`. Both run the same code; the methods build the commands.

Also exports :class:`Turtle2D`, :class:`Turtle3D`, :class:`TurtleCommandType`, and the
:class:`Turtle2DState` / :class:`Turtle3DState` value types.
"""

from ._fluent import TurtleCommands
from .commands import TurtleCommand, TurtleCommandType
from .turtle2d import Turtle2D, Turtle2DState, turtle2d
from .turtle3d import Turtle3D, Turtle3DState, turtle3d

__all__ = [
    "turtle2d",
    "turtle3d",
    "Turtle2D",
    "Turtle2DState",
    "Turtle3D",
    "Turtle3DState",
    "TurtleCommand",
    "TurtleCommandType",
    "TurtleCommands",
]

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Turtle-graphics path builders (2-D and 3-D).

Provides :func:`turtle2d` and :func:`turtle3d` convenience functions together
with the :class:`Turtle2D`, :class:`Turtle3D`, :class:`TurtleCommand`,
:class:`TurtleCommandType`, and :class:`Turtle2DState` / :class:`Turtle3DState`
types.
"""

from .turtle2d import Turtle2D, Turtle2DState, turtle2d
from .turtle3d import Turtle3D, Turtle3DState, TurtleCommand, TurtleCommandType, turtle3d

__all__ = [
    "turtle2d",
    "turtle3d",
    "Turtle2D",
    "Turtle2DState",
    "Turtle3D",
    "Turtle3DState",
    "TurtleCommand",
    "TurtleCommandType",
]

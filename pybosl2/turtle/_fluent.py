# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The turtle command language as methods, so a path reads as a sequence of moves.

``TurtleCommand(TurtleCommandType.MOVE, size=40)`` is an argument bag describing one step; SPEC
P-8 says the object should own the operation instead, and P-1 says the common case should be the
short one. :class:`TurtleCommands` gives both turtles a method per command --
``turtle.move(40).arc_left(radius=8)`` -- built from one table so the 2-D and 3-D turtles cannot
drift apart. The command objects still work, and are still what the methods build underneath.

Commands a 2-D turtle cannot honour (the z-axis moves and rotations) raise the same errors they
always did, from the same place: these methods add no validation of their own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pybosl2.exceptions import Bosl2ValueError
from pybosl2.turtle.commands import TurtleCommand, TurtleCommandType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from typing_extensions import Self

#: method name -> (command, the field its first positional argument fills, what it does).
_COMMANDS: dict[str, tuple[TurtleCommandType, str, str]] = {
    "move": (TurtleCommandType.MOVE, "size", "Move forward by *size* (default: the current step length)"),
    "x_move": (TurtleCommandType.XMOVE, "size", "Move along +X by *size*, leaving the heading alone"),
    "y_move": (TurtleCommandType.YMOVE, "size", "Move along +Y by *size*, leaving the heading alone"),
    "z_move": (TurtleCommandType.ZMOVE, "size", "Move along +Z by *size*, leaving the heading alone (3-D only)"),
    "until_x": (TurtleCommandType.UNTILX, "size", "Move along the heading until X reaches *size*"),
    "until_y": (TurtleCommandType.UNTILY, "size", "Move along the heading until Y reaches *size*"),
    "until_z": (TurtleCommandType.UNTILZ, "size", "Move along the heading until Z reaches *size* (3-D only)"),
    "jump": (TurtleCommandType.JUMP, "size", "Jump to an absolute position without drawing"),
    "x_jump": (TurtleCommandType.XJUMP, "size", "Jump to an absolute X, keeping the other coordinates"),
    "y_jump": (TurtleCommandType.YJUMP, "size", "Jump to an absolute Y, keeping the other coordinates"),
    "z_jump": (TurtleCommandType.ZJUMP, "size", "Jump to an absolute Z, keeping the other coordinates (3-D only)"),
    "left": (TurtleCommandType.LEFT, "angle", "Turn left by *angle* degrees (default: the current turn angle)"),
    "right": (TurtleCommandType.RIGHT, "angle", "Turn right by *angle* degrees (default: the current turn angle)"),
    "up": (TurtleCommandType.UP, "angle", "Pitch up by *angle* degrees (3-D only)"),
    "down": (TurtleCommandType.DOWN, "angle", "Pitch down by *angle* degrees (3-D only)"),
    "roll": (TurtleCommandType.ROLL, "angle", "Roll about the heading by *angle* degrees (3-D only)"),
    "set_direction": (TurtleCommandType.SETDIR, "size", "Point the turtle along a direction vector"),
    "set_angle": (TurtleCommandType.ANGLE, "angle", "Set the default turn angle for later turns"),
    "set_length": (TurtleCommandType.LENGTH, "size", "Set the default step length for later moves"),
    "add_length": (TurtleCommandType.ADDLENGTH, "size", "Add *size* to the default step length"),
    "scale_length": (TurtleCommandType.SCALE, "size", "Multiply the default step length by *size*"),
    "set_arc_steps": (TurtleCommandType.ARCSTEPS, "steps", "Set the segment count for later arcs (0 = automatic)"),
    "arc_left": (TurtleCommandType.ARCLEFT, "radius", "Arc left with the given *radius*"),
    "arc_right": (TurtleCommandType.ARCRIGHT, "radius", "Arc right with the given *radius*"),
    "arc_up": (TurtleCommandType.ARCUP, "radius", "Arc upward with the given *radius* (3-D only)"),
    "arc_down": (TurtleCommandType.ARCDOWN, "radius", "Arc downward with the given *radius* (3-D only)"),
    "arc_left_to": (TurtleCommandType.ARCLEFTTO, "radius", "Arc left until the heading reaches an absolute *angle*"),
    "arc_right_to": (
        TurtleCommandType.ARCRIGHTTO,
        "radius",
        "Arc right until the heading reaches an absolute *angle*",
    ),
}


class TurtleCommands:
    """A method per turtle command, each running it and returning the turtle (SPEC P-8).

    Mixed into :class:`~pybosl2.turtle.turtle2d.Turtle2D` and
    :class:`~pybosl2.turtle.turtle3d.Turtle3D`; every method builds a
    :class:`~pybosl2.turtle.commands.TurtleCommand` and hands it to that turtle's ``run()``, so
    the two spellings execute exactly the same code:

    .. code-block:: python

        Turtle2D().move(40).arc_left(radius=8)                       # methods
        turtle2d([TurtleCommand(TurtleCommandType.MOVE, size=40)])   # command objects

    Examples:
        .. pythonscad-example::

            from pybosl2.turtle import Turtle2D

            path = Turtle2D().set_length(40).set_arc_steps(24)
            for _ in range(4):
                path.move().arc_left(radius=8)
            path.points().stroke(width=3, closed=True).linear_extrude(height=4).show()

    """

    def run(self, commands: Sequence[TurtleCommand], repeat: int = 1) -> Self:
        """Execute *commands*; provided by the concrete turtle."""
        raise NotImplementedError

    def command(self, command: TurtleCommand) -> Self:
        """Run one :class:`~pybosl2.turtle.commands.TurtleCommand`.

        The escape hatch for the commands without a method of their own -- the compound arcs, and
        anything built programmatically.

        Args:
            command: The command to run.

        Returns:
            This turtle, so calls chain.

        """
        return self.run([command])


def _make(name: str, cmd_type: TurtleCommandType, field: str, summary: str) -> Any:
    def method(self: TurtleCommands, value: Any = None, **kwargs: Any) -> Any:
        if value is not None:
            if field in kwargs:
                raise Bosl2ValueError(f"{name}(): give {field} once -- positionally or by name, not both.")
            kwargs[field] = value
        return self.run([TurtleCommand(cmd_type, **kwargs)])

    method.__name__ = name
    method.__qualname__ = f"TurtleCommands.{name}"
    method.__doc__ = f"""{summary}.

        Runs ``TurtleCommandType.{cmd_type.name}``.

        Args:
            value: The command's *{field}*; ``None`` uses the turtle's current default.
            **kwargs: Any other :class:`~pybosl2.turtle.commands.TurtleCommand` field, e.g.
                ``angle=`` on an arc.

        Returns:
            This turtle, so calls chain.

        """
    return method


for _name, (_cmd, _field, _summary) in _COMMANDS.items():
    setattr(TurtleCommands, _name, _make(_name, _cmd, _field, _summary))

__all__ = ["TurtleCommands"]

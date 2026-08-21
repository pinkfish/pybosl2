# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The turtle command language as methods (SPEC P-8, PLAN O-1).

`Turtle2D().move(40)` must be exactly `TurtleCommand(TurtleCommandType.MOVE, size=40)` -- one
implementation with two spellings, not a second code path that can drift.
"""

import dataclasses

import numpy as np
import pytest

from pybosl2.turtle import Turtle2D, Turtle3D, TurtleCommand, TurtleCommandType
from pybosl2.turtle import TurtleCommandType as Tct
from pybosl2.turtle._fluent import _COMMANDS, TurtleCommands


def test_methods_and_commands_build_the_same_path() -> None:
    by_method = Turtle2D().set_length(40).move().arc_left(radius=8).move()
    by_command = Turtle2D().run(
        [
            TurtleCommand(Tct.LENGTH, size=40),
            TurtleCommand(Tct.MOVE),
            TurtleCommand(Tct.ARCLEFT, radius=8),
            TurtleCommand(Tct.MOVE),
        ]
    )
    assert np.allclose(by_method.points().array, by_command.points().array)


def test_methods_chain_and_return_the_turtle() -> None:
    turtle = Turtle2D()
    assert turtle.move(10) is turtle
    assert turtle.left(90) is turtle
    assert len(turtle.points()) == 2


def test_3d_turtle_has_the_same_methods() -> None:
    points = Turtle3D().set_length(10).move().up(90).move().points()
    assert len(points) == 3
    assert points[-1][2] > 0  # the second move went up


def test_a_value_given_twice_is_rejected() -> None:
    with pytest.raises(ValueError, match="give radius once"):
        Turtle2D().arc_left(8, radius=3)


def test_command_escape_hatch_runs_a_raw_command() -> None:
    turtle = Turtle2D().command(TurtleCommand(Tct.MOVE, size=5))
    assert len(turtle.points()) == 2


def test_a_3d_only_command_still_refuses_on_a_2d_turtle() -> None:
    """The methods add no validation of their own -- the turtle's own rules still apply."""
    with pytest.raises(ValueError, match="z-component must be 0"):
        Turtle2D().set_direction([1.0, 0.0, 1.0])


def test_every_command_method_names_a_real_command_and_field() -> None:
    """One table drives both turtles, so a typo in it would create a silently dead method."""
    fields = {f.name for f in dataclasses.fields(TurtleCommand)}
    for name, (cmd_type, field, summary) in _COMMANDS.items():
        assert hasattr(TurtleCommands, name), name
        assert isinstance(cmd_type, TurtleCommandType), name
        assert field in fields, name
        assert summary, name
        assert summary[0].isupper(), name
        assert getattr(TurtleCommands, name).__doc__, name

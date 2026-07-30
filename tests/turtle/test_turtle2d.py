# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for the 2-D turtle graphics system."""

import numpy as np
import pytest

from pybosl2.path2d import Path2D
from pybosl2.turtle import Turtle2DState, TurtleCommand, turtle2d
from pybosl2.turtle import TurtleCommandType as Tct


def test_turtle_square():
    t = turtle2d(
        [
            TurtleCommand(Tct.MOVE, size=10),
            TurtleCommand(Tct.LEFT, angle=90),
            TurtleCommand(Tct.MOVE, size=10),
            TurtleCommand(Tct.LEFT, angle=90),
            TurtleCommand(Tct.MOVE, size=10),
        ]
    )
    p = t.points()
    assert isinstance(p, Path2D)
    np.testing.assert_allclose(p, [[0, 0], [10, 0], [10, 10], [0, 10]], atol=1e-9)


def test_turtle_repeat_closes_square():
    sub = [TurtleCommand(Tct.MOVE, size=40), TurtleCommand(Tct.LEFT, angle=90)]
    p = turtle2d([TurtleCommand(Tct.REPEAT, size=4, sub_commands=sub)]).points()
    np.testing.assert_allclose(p[0], [0, 0], atol=1e-9)
    np.testing.assert_allclose(p[-1], [0, 0], atol=1e-9)


def test_turtle_full_state():
    st = turtle2d([TurtleCommand(Tct.MOVE, size=5)]).full_state()
    assert isinstance(st, Turtle2DState)
    assert len(st.path) == 2
    np.testing.assert_allclose(st.path[-1], [5, 0], atol=1e-9)
    assert st.angle == 90.0
    assert st.arcsteps == 0


def test_turtle_unknown_command_raises():
    with pytest.raises(ValueError, match="z-axis"):
        turtle2d([TurtleCommand(Tct.ZMOVE, size=5)])

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for the 2-D turtle graphics system."""

import math

import numpy as np
import pytest

from pybosl2.path2d import Path2D
from pybosl2.points import Point
from pybosl2.regions import Region
from pybosl2.turtle import Turtle2D, Turtle2DState, TurtleCommand, turtle2d
from pybosl2.turtle import TurtleCommandType as Tct

M = TurtleCommand


def test_turtle_square() -> None:
    t = turtle2d(
        [
            M(Tct.MOVE, size=10),
            M(Tct.LEFT, angle=90),
            M(Tct.MOVE, size=10),
            M(Tct.LEFT, angle=90),
            M(Tct.MOVE, size=10),
        ]
    )
    p = t.points()
    assert isinstance(p, Path2D)
    np.testing.assert_allclose(p, [[0, 0], [10, 0], [10, 10], [0, 10]], atol=1e-9)


def test_turtle_repeat_closes_square() -> None:
    sub = [M(Tct.MOVE, size=40), M(Tct.LEFT, angle=90)]
    p = turtle2d([M(Tct.REPEAT, size=4, sub_commands=sub)]).points()
    np.testing.assert_allclose(p[0], [0, 0], atol=1e-9)
    np.testing.assert_allclose(p[-1], [0, 0], atol=1e-9)


def test_turtle_full_state() -> None:
    st = turtle2d([M(Tct.MOVE, size=5)]).full_state()
    assert isinstance(st, Turtle2DState)
    assert len(st.path) == 2
    np.testing.assert_allclose(st.path[-1], [5, 0], atol=1e-9)
    assert st.angle == 90.0
    assert st.arcsteps == 0


def test_turtle_unknown_command_raises() -> None:
    with pytest.raises(ValueError, match="z-axis"):
        turtle2d([M(Tct.ZMOVE, size=5)])


# ── uncovered command types ─────────────────────────────────────────────


def test_xmove() -> None:
    p = turtle2d([M(Tct.XMOVE, size=20)]).points()
    assert len(p) == 2
    np.testing.assert_allclose(p[0], [0, 0], atol=1e-9)
    np.testing.assert_allclose(p[1], [20, 0], atol=1e-9)


def test_ymove() -> None:
    p = turtle2d([M(Tct.YMOVE, size=20)]).points()
    assert len(p) == 2
    np.testing.assert_allclose(p[0], [0, 0], atol=1e-9)
    np.testing.assert_allclose(p[1], [0, 20], atol=1e-9)


def test_xymove() -> None:
    p = turtle2d([M(Tct.XYZMOVE, size=Point(20, 30))]).points()
    assert len(p) == 2
    np.testing.assert_allclose(p[0], [0, 0], atol=1e-9)
    np.testing.assert_allclose(p[1], [20, 30], atol=1e-9)


def test_jump() -> None:
    p = turtle2d([M(Tct.JUMP, size=Point(30, 40))]).points()
    assert len(p) == 2
    np.testing.assert_allclose(p[0], [0, 0], atol=1e-9)
    np.testing.assert_allclose(p[1], [30, 40], atol=1e-9)


def test_xjump() -> None:
    p = turtle2d([M(Tct.XJUMP, size=50)]).points()
    assert len(p) == 2
    np.testing.assert_allclose(p[0], [0, 0], atol=1e-9)
    np.testing.assert_allclose(p[1], [50, 0], atol=1e-9)


def test_yjump() -> None:
    p = turtle2d([M(Tct.YJUMP, size=60)]).points()
    assert len(p) == 2
    np.testing.assert_allclose(p[0], [0, 0], atol=1e-9)
    np.testing.assert_allclose(p[1], [0, 60], atol=1e-9)


def test_right_turn() -> None:
    p = turtle2d([M(Tct.RIGHT, angle=90), M(Tct.MOVE, size=20)]).points()
    assert len(p) == 2
    np.testing.assert_allclose(p[1], [0, -20], atol=1e-9)


def test_zrot() -> None:
    p = turtle2d([M(Tct.ZROT, angle=90), M(Tct.MOVE, size=20)]).points()
    assert len(p) == 2
    np.testing.assert_allclose(p[1], [0, 20], atol=1e-9)


def test_angle_set() -> None:
    p = turtle2d([M(Tct.ANGLE, angle=180), M(Tct.MOVE, size=20)]).points()
    assert len(p) == 2
    np.testing.assert_allclose(p[1], [20, 0], atol=1e-9)


def test_setdir() -> None:
    p = turtle2d([M(Tct.SETDIR, angle=90), M(Tct.MOVE, size=20)]).points()
    assert len(p) == 2
    np.testing.assert_allclose(p[1], [20, 0], atol=1e-9)


def test_length_scale() -> None:
    p = turtle2d([M(Tct.LENGTH, size=2), M(Tct.MOVE, size=20)]).points()
    assert len(p) == 2
    np.testing.assert_allclose(p[1], [40, 0], atol=1e-9)


def test_scale_command() -> None:
    p = turtle2d([M(Tct.SCALE, size=0.5), M(Tct.MOVE, size=20)]).points()
    assert len(p) == 2
    np.testing.assert_allclose(p[1], [10, 0], atol=1e-9)


def test_addlength() -> None:
    p = turtle2d([M(Tct.ADDLENGTH, size=3), M(Tct.MOVE, size=20)]).points()
    assert len(p) == 2
    np.testing.assert_allclose(p[1], [80, 0], atol=1e-9)


def test_arcleft() -> None:
    p = turtle2d([M(Tct.ARCSTEPS, size=8), M(Tct.ARCLEFT, angle=90, radius=10)]).points()
    assert len(p) == 8
    np.testing.assert_allclose(p[-1], [10, 10], atol=1e-9)


def test_arcright() -> None:
    p = turtle2d([M(Tct.ARCSTEPS, size=8), M(Tct.ARCRIGHT, angle=90, radius=10)]).points()
    assert len(p) == 8
    np.testing.assert_allclose(p[-1], [10, -10], atol=1e-9)


def test_arcleftto_turns_to_an_absolute_heading() -> None:
    # arcleftto's angle is where to end up pointing, not how far to turn: starting along +X it is
    # a full quarter turn, but from a 45-degree heading only the remaining 45 degrees.
    p = turtle2d([M(Tct.ARCSTEPS, size=8), M(Tct.ARCLEFTTO, angle=90, radius=10)]).points()
    assert len(p) == 8
    np.testing.assert_allclose(p[-1], [10, 10], atol=1e-9)

    p = turtle2d([M(Tct.ARCSTEPS, size=8), M(Tct.LEFT, angle=45), M(Tct.ARCLEFTTO, angle=90, radius=10)]).points()
    np.testing.assert_allclose(p[-1], [10 - 5 * math.sqrt(2), 5 * math.sqrt(2)], atol=1e-9)


def test_arcrightto_turns_to_an_absolute_heading() -> None:
    p = turtle2d([M(Tct.ARCSTEPS, size=8), M(Tct.ARCRIGHTTO, angle=270, radius=10)]).points()
    assert len(p) == 8
    np.testing.assert_allclose(p[-1], [10, -10], atol=1e-9)


def test_arczrot() -> None:
    p = turtle2d([M(Tct.ARCSTEPS, size=8), M(Tct.ARCZROT, angle=90, radius=10)]).points()
    assert len(p) == 8
    np.testing.assert_allclose(p[-1], [10, 10], atol=1e-9)


def test_compound_move() -> None:
    p = turtle2d([M(Tct.MOVE, size=10, steps=3, is_compound=True)]).points()
    assert len(p) == 4
    np.testing.assert_allclose(p[0], [0, 0])
    np.testing.assert_allclose(p[-1], [10, 0])


def test_compound_reverse() -> None:
    p = turtle2d([M(Tct.MOVE, size=10, steps=3, reverse=True, is_compound=True)]).points()
    assert len(p) == 4
    assert p[-1][0] == pytest.approx(-10)


def test_compound_grow() -> None:
    p = turtle2d([M(Tct.MOVE, size=10, steps=4, is_compound=True)]).points()
    assert len(p) == 5
    np.testing.assert_allclose(p[0], [0, 0])
    np.testing.assert_allclose(p[-1], [10, 0])


def test_turtle_stroke() -> None:
    t = Turtle2D()
    t.run([M(Tct.MOVE, size=20), M(Tct.LEFT, angle=90), M(Tct.MOVE, size=20)])
    s = t.stroke(width=2)
    assert isinstance(s, Region)  # a stroke is the area the pen covers (SPEC S-23a)
    assert len(s.paths[0]) > 0
    # the L the turtle walked, grown by half a width on each side
    assert s.bounds().size == pytest.approx((22.0, 22.0), abs=0.1)

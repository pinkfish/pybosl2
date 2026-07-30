# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.turtle3d (the Turtle class) and the debug_polygon/debug_region methods."""

import numpy as np
import pytest

from pybosl2.path2d import Path2D
from pybosl2.regions import Region
from pybosl2.shapes3d import Bosl2Solid
from pybosl2.turtle3d import BaseTurtle, Turtle, TurtleCommand, turtle3d
from pybosl2.turtle3d import TurtleCommandType as Tct

M = TurtleCommand


def test_square_path_closes():
    pts = (
        Turtle()
        .run(
            [
                M(Tct.MOVE, size=10),
                M(Tct.LEFT, angle=90),
                M(Tct.MOVE, size=10),
                M(Tct.LEFT, angle=90),
                M(Tct.MOVE, size=10),
                M(Tct.LEFT, angle=90),
                M(Tct.MOVE, size=10),
            ]
        )
        .points()
    )
    corners = [[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0], [0, 0, 0]]
    np.testing.assert_allclose(pts, corners, atol=1e-9)


def test_right_and_left_are_opposite():
    right_cmds = [M(Tct.MOVE, size=5), M(Tct.RIGHT, angle=90), M(Tct.MOVE, size=5)]
    left_cmds = [M(Tct.MOVE, size=5), M(Tct.LEFT, angle=90), M(Tct.MOVE, size=5)]
    radius = Turtle().run(right_cmds).points()[-1]
    left = Turtle().run(left_cmds).points()[-1]
    assert radius[1] == pytest.approx(-left[1])
    assert radius[0] == pytest.approx(left[0])


def test_up_climbs_in_z():
    pts = Turtle().run([M(Tct.MOVE, size=5), M(Tct.UP, angle=90), M(Tct.MOVE, size=5)]).points()
    assert pts[-1][2] == pytest.approx(5)


def test_length_and_scale_commands():
    a = Turtle().run([M(Tct.LENGTH, size=4), M(Tct.MOVE, size=1)]).points()[-1]
    assert a[0] == pytest.approx(4)
    b = Turtle().run([M(Tct.LENGTH, size=4), M(Tct.SCALE, size=2), M(Tct.MOVE, size=1)]).points()[-1]
    assert b[0] == pytest.approx(8)


def test_arcleft_point_count_and_curvature():
    pts = (
        Turtle()
        .run([M(Tct.ARCSTEPS, size=8), M(Tct.MOVE, size=5), M(Tct.ARCLEFT, radius=5), M(Tct.MOVE, size=5)])
        .points()
    )
    assert len(pts) == 1 + 1 + 8 + 1
    assert pts[-1][1] > 0


def test_repeat_command():
    once = Turtle().run([M(Tct.MOVE, size=3), M(Tct.LEFT, angle=20)]).points()
    sub = [M(Tct.MOVE, size=3), M(Tct.LEFT, angle=20)]
    thrice = Turtle().run([M(Tct.REPEAT, size=3, options={"commands": sub})]).points()
    assert len(thrice) == 1 + 3 * (len(once) - 1)


def test_transforms_are_4x4():
    xform = Turtle().run([M(Tct.MOVE, size=10), M(Tct.ARCLEFT, radius=5)]).transforms()
    assert all(np.asarray(t).shape == (4, 4) for t in xform)


def test_turtle3d_function_matches_instance():
    cmds = [M(Tct.MOVE, size=10), M(Tct.LEFT, angle=90), M(Tct.MOVE, size=10)]
    np.testing.assert_allclose(turtle3d(cmds).points(), Turtle().run(cmds).points())


def test_compound_move_matches_simple_move():
    np.testing.assert_allclose(
        Turtle().run([M(Tct.MOVE, size=10, is_compound=True)]).points(),
        Turtle().run([M(Tct.MOVE, size=10)]).points(),
        atol=1e-9,
    )


def test_compound_arc_matches_simple_arc():
    simple = Turtle().run([M(Tct.ARCSTEPS, size=8), M(Tct.ARCLEFT, radius=5)]).points()
    compound = Turtle().run([M(Tct.ARC, radius=5, angle=90, steps=8, options={"left": 90}, is_compound=True)]).points()
    np.testing.assert_allclose(simple[-1], compound[-1], atol=1e-6)


def test_compound_reverse_flips_direction():
    assert Turtle().run([M(Tct.MOVE, size=5, reverse=True, is_compound=True)]).points()[-1][0] == pytest.approx(-5)


def test_compound_grow_twist_builds_transforms():
    xform = Turtle().run([M(Tct.MOVE, size=10, grow=2, twist=90, steps=6, is_compound=True)]).transforms()
    assert len(xform) == 7
    assert all(np.asarray(t).shape == (4, 4) for t in xform)


def test_compound_arc_absolute_rotation():
    rel = Turtle().run([M(Tct.ARC, radius=5, angle=90, steps=8, options={"left": 90}, is_compound=True)]).points()[-1]
    ab = Turtle().run([M(Tct.ARC, radius=5, angle=90, steps=8, options={"zrot": 90}, is_compound=True)]).points()[-1]
    np.testing.assert_allclose(rel, ab, atol=1e-6)


def test_compound_rollto_builds():
    xform = Turtle().run([M(Tct.MOVE, size=10, rollto=[0, 0, 1], steps=3, is_compound=True)]).transforms()
    assert len(xform) == 4


def test_debug_polygon_builds_with_labels():
    p = Path2D([[0, 0], [40, 0], [40, 30], [0, 30]])
    assert isinstance(p.debug_polygon(size=3), Bosl2Solid)
    assert isinstance(p.debug_polygon(vertices=False), Bosl2Solid)


def test_debug_region_builds():
    r = Region.with_holes([[0, 0], [50, 0], [50, 50], [0, 50]], [[15, 15], [35, 15], [35, 35], [15, 35]])
    assert isinstance(r.debug_region(size=3), Bosl2Solid)


def test_debug_region_single_path_defers_to_polygon():
    assert isinstance(Region([[[0, 0], [20, 0], [10, 20]]]).debug_region(), Bosl2Solid)


def test_base_turtle_inheritance():
    assert issubclass(Turtle, BaseTurtle)
    assert isinstance(Turtle(), BaseTurtle)


def test_turtle_command_class_and_enum_simple():
    cmds = [
        TurtleCommand(Tct.MOVE, size=10),
        TurtleCommand(Tct.LEFT, angle=90),
        TurtleCommand(Tct.MOVE, size=10),
        TurtleCommand(Tct.LEFT, angle=90),
        TurtleCommand(Tct.MOVE, size=10),
        TurtleCommand(Tct.LEFT, angle=90),
        TurtleCommand(Tct.MOVE, size=10),
    ]
    pts = Turtle().run(cmds).points()
    corners = [[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0], [0, 0, 0]]
    np.testing.assert_allclose(pts, corners, atol=1e-9)


def test_turtle_command_compound():
    cmd = TurtleCommand(
        Tct.MOVE,
        size=10,
        grow=2,
        twist=90,
        steps=6,
        is_compound=True,
    )
    xform = Turtle().run([cmd]).transforms()
    assert len(xform) == 7
    assert all(np.asarray(t).shape == (4, 4) for t in xform)


def test_turtle_command_repeat():
    sub_cmds = [
        TurtleCommand(Tct.MOVE, size=3),
        TurtleCommand(Tct.LEFT, angle=20),
    ]
    thrice = Turtle().run([TurtleCommand(Tct.REPEAT, size=3, options={"commands": sub_cmds})]).points()

    legacy_once = Turtle().run([M(Tct.MOVE, size=3), M(Tct.LEFT, angle=20)]).points()
    assert len(thrice) == 1 + 3 * (len(legacy_once) - 1)


def test_turtle_command_compound_with_enums():
    pts = Turtle().run([TurtleCommand(Tct.MOVE, size=10, grow=2, steps=4, is_compound=True)]).points()
    assert len(pts) == 5

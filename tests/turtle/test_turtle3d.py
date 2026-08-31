# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for "pybosl2.turtle.turtle3d" (the Turtle class) and the debug_polygon/debug_region methods."""

import numpy as np
import pytest

from pybosl2.path2d import Path2D
from pybosl2.regions import Region
from pybosl2.shapes3d import Bosl2Solid
from pybosl2.turtle import Turtle3D, TurtleCommand, turtle3d
from pybosl2.turtle import TurtleCommandType as Tct

M = TurtleCommand


def test_square_path_closes() -> None:
    pts = (
        Turtle3D()
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


def test_right_and_left_are_opposite() -> None:
    right_cmds = [M(Tct.MOVE, size=5), M(Tct.RIGHT, angle=90), M(Tct.MOVE, size=5)]
    left_cmds = [M(Tct.MOVE, size=5), M(Tct.LEFT, angle=90), M(Tct.MOVE, size=5)]
    radius = Turtle3D().run(right_cmds).points()[-1]
    left = Turtle3D().run(left_cmds).points()[-1]
    assert radius[1] == pytest.approx(-left[1])
    assert radius[0] == pytest.approx(left[0])


def test_up_climbs_in_z() -> None:
    pts = Turtle3D().run([M(Tct.MOVE, size=5), M(Tct.UP, angle=90), M(Tct.MOVE, size=5)]).points()
    assert pts[-1][2] == pytest.approx(5)


def test_length_and_scale_commands() -> None:
    a = Turtle3D().run([M(Tct.LENGTH, size=4), M(Tct.MOVE, size=1)]).points()[-1]
    assert a[0] == pytest.approx(4)
    b = Turtle3D().run([M(Tct.LENGTH, size=4), M(Tct.SCALE, size=2), M(Tct.MOVE, size=1)]).points()[-1]
    assert b[0] == pytest.approx(8)


def test_arcleft_point_count_and_curvature() -> None:
    pts = (
        Turtle3D()
        .run([M(Tct.ARCSTEPS, size=8), M(Tct.MOVE, size=5), M(Tct.ARCLEFT, radius=5), M(Tct.MOVE, size=5)])
        .points()
    )
    assert len(pts) == 1 + 1 + 8 + 1
    assert pts[-1][1] > 0


def test_repeat_command() -> None:
    once = Turtle3D().run([M(Tct.MOVE, size=3), M(Tct.LEFT, angle=20)]).points()
    sub = [M(Tct.MOVE, size=3), M(Tct.LEFT, angle=20)]
    thrice = Turtle3D().run([M(Tct.REPEAT, size=3, sub_commands=sub)]).points()
    assert len(thrice) == 1 + 3 * (len(once) - 1)


def test_transforms_are_4x4() -> None:
    xform = Turtle3D().run([M(Tct.MOVE, size=10), M(Tct.ARCLEFT, radius=5)]).transforms()
    assert all(np.asarray(t).shape == (4, 4) for t in xform)


def test_turtle3d_function_matches_instance() -> None:
    cmds = [M(Tct.MOVE, size=10), M(Tct.LEFT, angle=90), M(Tct.MOVE, size=10)]
    np.testing.assert_allclose(turtle3d(cmds).points(), Turtle3D().run(cmds).points())


def test_compound_move_matches_simple_move() -> None:
    np.testing.assert_allclose(
        Turtle3D().run([M(Tct.MOVE, size=10, is_compound=True)]).points(),
        Turtle3D().run([M(Tct.MOVE, size=10)]).points(),
        atol=1e-9,
    )


def test_compound_arc_matches_simple_arc() -> None:
    simple = Turtle3D().run([M(Tct.ARCSTEPS, size=8), M(Tct.ARCLEFT, radius=5)]).points()
    compound = (
        Turtle3D()
        .run([M(Tct.ARC, radius=5, angle=90, steps=8, rotation_type=TurtleCommand.RotationType.LEFT, is_compound=True)])
        .points()
    )
    np.testing.assert_allclose(simple[-1], compound[-1], atol=1e-6)


def test_compound_reverse_flips_direction() -> None:
    assert Turtle3D().run([M(Tct.MOVE, size=5, reverse=True, is_compound=True)]).points()[-1][0] == pytest.approx(-5)


def test_compound_grow_twist_builds_transforms() -> None:
    xform = Turtle3D().run([M(Tct.MOVE, size=10, grow=2, twist=90, steps=6, is_compound=True)]).transforms()
    assert len(xform) == 7
    assert all(np.asarray(t).shape == (4, 4) for t in xform)


def test_compound_arc_absolute_rotation() -> None:
    rel = (
        Turtle3D()
        .run([M(Tct.ARC, radius=5, angle=90, steps=8, rotation_type=TurtleCommand.RotationType.LEFT, is_compound=True)])
        .points()[-1]
    )
    ab = (
        Turtle3D()
        .run([M(Tct.ARC, radius=5, angle=90, steps=8, rotation_type=TurtleCommand.RotationType.ZROT, is_compound=True)])
        .points()[-1]
    )
    np.testing.assert_allclose(rel, ab, atol=1e-6)


def test_compound_rollto_builds() -> None:
    xform = Turtle3D().run([M(Tct.MOVE, size=10, rollto=[0, 0, 1], steps=3, is_compound=True)]).transforms()  # type: ignore[arg-type]
    assert len(xform) == 4


def test_debug_polygon_builds_with_labels() -> None:
    """The debug view is the flat polygon plus vertex markers, which stand outside its outline."""
    path = Path2D([[0, 0], [40, 0], [40, 30], [0, 30]])
    bare = path.debug_polygon(vertices=False)
    assert [float(v) for v in bare.bounds().size][:2] == pytest.approx([40.0, 30.0], abs=0.01)

    labelled = path.debug_polygon(size=3)
    assert float(labelled.bounds().size[0]) > 40.0  # the markers reach past the corners
    assert float(labelled.bounds().size[1]) > 30.0


def test_debug_region_builds() -> None:
    """A region's debug view covers its outline, with the same markers standing proud of it."""
    region = Region.with_holes(
        Path2D([[0, 0], [50, 0], [50, 50], [0, 50]]), Path2D([[15, 15], [35, 15], [35, 35], [15, 35]])
    )
    debug = region.debug_region(size=3)
    assert isinstance(debug, Bosl2Solid)
    assert float(debug.bounds().size[0]) > 50.0
    assert float(debug.bounds().size[2]) < 1.0  # it stays a flat overlay


def test_debug_region_single_path_defers_to_polygon() -> None:
    """One outline means the region view is exactly the polygon view of that outline."""
    outline = [[0, 0], [20, 0], [10, 20]]
    from_region = Region([outline]).debug_region()
    from_path = Path2D(outline).debug_polygon()
    assert repr(from_region.shape) == repr(from_path.shape)


def test_turtle3d_is_instance() -> None:
    """A fresh turtle sits at the origin facing +X, with just its starting point recorded."""
    turtle = Turtle3D()
    assert isinstance(turtle, Turtle3D)
    assert np.asarray(turtle.points()).tolist() == [[0.0, 0.0, 0.0]]
    assert np.asarray(turtle.run([M(Tct.MOVE, size=10)]).points())[-1].tolist() == [10.0, 0.0, 0.0]


# ── uncovered command types ─────────────────────────────────────────────


def test_xmove_3d() -> None:
    p = Turtle3D().run([M(Tct.XMOVE, size=20)]).points()
    assert len(p) == 2
    np.testing.assert_allclose(p[-1], [20, 0, 0], atol=1e-9)


def test_ymove_3d() -> None:
    p = Turtle3D().run([M(Tct.YMOVE, size=20)]).points()
    np.testing.assert_allclose(p[-1], [0, 20, 0], atol=1e-9)


def test_zmove_3d() -> None:
    p = Turtle3D().run([M(Tct.ZMOVE, size=20)]).points()
    np.testing.assert_allclose(p[-1], [0, 0, 20], atol=1e-9)


def test_xymove_3d() -> None:
    from pybosl2.points import Point

    p = Turtle3D().run([M(Tct.XYZMOVE, size=Point(20, 30, 40))]).points()
    np.testing.assert_allclose(p[-1], [20, 30, 40], atol=1e-9)


def test_jump_3d() -> None:
    from pybosl2.points import Point

    p = Turtle3D().run([M(Tct.JUMP, size=Point(10, 20, 30))]).points()
    np.testing.assert_allclose(p[-1], [10, 20, 30], atol=1e-9)


def test_xjump_3d() -> None:
    p = Turtle3D().run([M(Tct.XJUMP, size=50)]).points()
    np.testing.assert_allclose(p[-1], [50, 0, 0], atol=1e-9)


def test_yjump_3d() -> None:
    p = Turtle3D().run([M(Tct.YJUMP, size=60)]).points()
    np.testing.assert_allclose(p[-1], [0, 60, 0], atol=1e-9)


def test_zjump_3d() -> None:
    p = Turtle3D().run([M(Tct.ZJUMP, size=70)]).points()
    np.testing.assert_allclose(p[-1], [0, 0, 70], atol=1e-9)


def test_angle_3d() -> None:
    p = Turtle3D().run([M(Tct.ANGLE, angle=180), M(Tct.MOVE, size=20)]).points()
    n = np.linalg.norm(np.asarray(p[-1]) - np.asarray([20, 0, 0]))
    assert n < 1e-9


def test_length_3d() -> None:
    p = Turtle3D().run([M(Tct.LENGTH, size=2), M(Tct.MOVE, size=20)]).points()
    np.testing.assert_allclose(p[-1], [40, 0, 0], atol=1e-9)


def test_addlength_3d() -> None:
    p = Turtle3D().run([M(Tct.ADDLENGTH, size=3), M(Tct.MOVE, size=20)]).points()
    np.testing.assert_allclose(p[-1], [80, 0, 0], atol=1e-9)


def test_scale_3d() -> None:
    p = Turtle3D().run([M(Tct.SCALE, size=0.5), M(Tct.MOVE, size=20)]).points()
    np.testing.assert_allclose(p[-1], [10, 0, 0], atol=1e-9)


def _end_point(commands: list[M]) -> list[float]:
    """Where the turtle finishes after running *commands*."""
    return [round(float(v), 3) for v in np.asarray(Turtle3D().run(commands).points())[-1]]


def test_roll_3d() -> None:
    """Roll turns the turtle about its own heading: +X still leads, but "up" has moved."""
    assert _end_point([M(Tct.ROLL, angle=90), M(Tct.MOVE, size=10)]) == [10.0, 0.0, 0.0]
    assert _end_point([M(Tct.UP, angle=90), M(Tct.MOVE, size=10)]) == [0.0, 0.0, 10.0]
    assert _end_point([M(Tct.ROLL, angle=90), M(Tct.UP, angle=90), M(Tct.MOVE, size=10)]) == [0.0, -10.0, 0.0]


def test_xrot_3d() -> None:
    """xrot turns about the world X axis, which is where the turtle already points."""
    assert _end_point([M(Tct.XROT, angle=-90), M(Tct.MOVE, size=10)]) == [10.0, 0.0, 0.0]
    # ...so it shows up in where "up" now leads -- the opposite way round from a roll
    assert _end_point([M(Tct.XROT, angle=-90), M(Tct.UP, angle=90), M(Tct.MOVE, size=10)]) == [0.0, 10.0, 0.0]


def test_yrot_3d() -> None:
    """yrot tips the heading out of the XY plane: -90 about Y points the turtle at +Z."""
    assert _end_point([M(Tct.YROT, angle=-90), M(Tct.MOVE, size=10)]) == [0.0, 0.0, 10.0]
    assert _end_point([M(Tct.ZROT, angle=90), M(Tct.MOVE, size=10)]) == [0.0, 10.0, 0.0]


def test_arcleft_3d() -> None:
    p = Turtle3D().run([M(Tct.ARCSTEPS, size=8), M(Tct.ARCLEFT, angle=90, radius=10)]).points()
    assert len(p) >= 7


def test_arcright_3d() -> None:
    p = Turtle3D().run([M(Tct.ARCSTEPS, size=8), M(Tct.ARCRIGHT, angle=90, radius=10)]).points()
    assert len(p) >= 7


def test_arcup_3d() -> None:
    p = Turtle3D().run([M(Tct.ARCSTEPS, size=8), M(Tct.ARCUP, angle=90, radius=10)]).points()
    assert len(p) >= 7


def test_compound_todir_3d() -> None:
    from pybosl2.points import Point

    cmd = M(
        Tct.ARC,
        radius=10,
        angle=Point(0, 0, 1),
        steps=8,
        rotation_type=TurtleCommand.RotationType.TODIR,
        is_compound=True,
    )
    p = Turtle3D().run([cmd]).points()
    assert len(p) > 0


def test_turtle3d_full_state() -> None:
    st = Turtle3D().run([M(Tct.MOVE, size=10)]).full_state()
    assert st.step > 0
    assert st.arcsteps >= 0


def test_compound_rollto_3d() -> None:
    from pybosl2.points import Point
    from pybosl2.turtle import TurtleCommandType as _Tct

    cmd = M(_Tct.MOVE, size=10, steps=3, rollto=Point(0, 0, 1), is_compound=True)
    xform = Turtle3D().run([cmd]).transforms()
    assert len(xform) == 4
    assert all(np.asarray(t).shape == (4, 4) for t in xform)


def test_turtle_command_class_and_enum_simple() -> None:
    cmds = [
        TurtleCommand(Tct.MOVE, size=10),
        TurtleCommand(Tct.LEFT, angle=90),
        TurtleCommand(Tct.MOVE, size=10),
        TurtleCommand(Tct.LEFT, angle=90),
        TurtleCommand(Tct.MOVE, size=10),
        TurtleCommand(Tct.LEFT, angle=90),
        TurtleCommand(Tct.MOVE, size=10),
    ]
    pts = Turtle3D().run(cmds).points()
    corners = [[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0], [0, 0, 0]]
    np.testing.assert_allclose(pts, corners, atol=1e-9)


def test_turtle_command_compound() -> None:
    cmd = TurtleCommand(
        Tct.MOVE,
        size=10,
        grow=2,
        twist=90,
        steps=6,
        is_compound=True,
    )
    xform = Turtle3D().run([cmd]).transforms()
    assert len(xform) == 7
    assert all(np.asarray(t).shape == (4, 4) for t in xform)


def test_turtle_command_repeat() -> None:
    sub_cmds = [
        TurtleCommand(Tct.MOVE, size=3),
        TurtleCommand(Tct.LEFT, angle=20),
    ]
    thrice = Turtle3D().run([TurtleCommand(Tct.REPEAT, size=3, sub_commands=sub_cmds)]).points()

    legacy_once = Turtle3D().run([M(Tct.MOVE, size=3), M(Tct.LEFT, angle=20)]).points()
    assert len(thrice) == 1 + 3 * (len(legacy_once) - 1)


def test_turtle_command_compound_with_enums() -> None:
    pts = Turtle3D().run([TurtleCommand(Tct.MOVE, size=10, grow=2, steps=4, is_compound=True)]).points()
    assert len(pts) == 5

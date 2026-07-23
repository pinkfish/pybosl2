# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2.turtle3d (the Turtle class) and the debug_polygon/debug_region methods."""

import math

import numpy as np
import pytest

from bosl2.turtle3d import Turtle
from bosl2.paths import Path
from bosl2.regions import Region
from bosl2.shapes3d import Bosl2Solid


def test_square_path_closes():
    pts = Turtle().run(["move", 10, "left", 90, "move", 10, "left", 90,
                        "move", 10, "left", 90, "move", 10]).points()
    corners = [[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0], [0, 0, 0]]
    np.testing.assert_allclose(pts, corners, atol=1e-9)


def test_right_and_left_are_opposite():
    r = Turtle().run(["move", 5, "right", 90, "move", 5]).points()[-1]
    left = Turtle().run(["move", 5, "left", 90, "move", 5]).points()[-1]
    assert r[1] == pytest.approx(-left[1])                # mirror across the X axis
    assert r[0] == pytest.approx(left[0])


def test_up_climbs_in_z():
    pts = Turtle().run(["move", 5, "up", 90, "move", 5]).points()
    assert pts[-1][2] == pytest.approx(5)                 # turned up, then moved into +Z


def test_length_and_scale_commands():
    a = Turtle().run(["length", 4, "move", 1]).points()[-1]
    assert a[0] == pytest.approx(4)
    b = Turtle().run(["length", 4, "scale", 2, "move", 1]).points()[-1]
    assert b[0] == pytest.approx(8)


def test_arcleft_point_count_and_curvature():
    pts = Turtle().run(["arcsteps", 8, "move", 5, "arcleft", 5, "move", 5]).points()
    assert len(pts) == 1 + 1 + 8 + 1                      # start + move + 8 arc steps + move
    assert pts[-1][1] > 0                                 # curved into +Y


def test_repeat_command():
    once = Turtle().run(["move", 3, "left", 20]).points()
    thrice = Turtle().run(["repeat", 3, ["move", 3, "left", 20]]).points()
    assert len(thrice) == 1 + 3 * (len(once) - 1)


def test_transforms_are_4x4():
    T = Turtle().run(["move", 10, "arcleft", 5]).transforms()
    assert all(np.asarray(t).shape == (4, 4) for t in T)


def test_turtle3d_classmethod_matches_instance():
    cmds = ["move", 10, "left", 90, "move", 10]
    np.testing.assert_allclose(Turtle.turtle3d(cmds), Turtle().run(cmds).points())


def test_compound_move_matches_simple_move():
    np.testing.assert_allclose(Turtle().run([["move", 10]]).points(),
                               Turtle().run(["move", 10]).points(), atol=1e-9)


def test_compound_arc_matches_simple_arc():
    simple = Turtle().run(["arcsteps", 8, "arcleft", 5]).points()
    compound = Turtle().run([["arc", 5, "left", 90, "steps", 8]]).points()
    np.testing.assert_allclose(simple[-1], compound[-1], atol=1e-6)


def test_compound_reverse_flips_direction():
    assert Turtle().run([["move", 5, "reverse"]]).points()[-1][0] == pytest.approx(-5)


def test_compound_grow_twist_builds_transforms():
    T = Turtle().run([["move", 10, "grow", 2, "twist", 90, "steps", 6]]).transforms()
    assert len(T) == 7 and all(np.asarray(t).shape == (4, 4) for t in T)


def test_compound_arc_absolute_rotation():
    # an "arc" with an absolute zrot of 90 sweeps the same quarter circle as a relative left 90
    rel = Turtle().run([["arc", 5, "left", 90, "steps", 8]]).points()[-1]
    ab = Turtle().run([["arc", 5, "zrot", 90, "steps", 8]]).points()[-1]
    np.testing.assert_allclose(rel, ab, atol=1e-6)


def test_compound_rollto_builds():
    T = Turtle().run([["move", 10, "rollto", [0, 0, 1], "steps", 3]]).transforms()
    assert len(T) == 4


def test_compound_bad_head_rejected():
    with pytest.raises(AssertionError):
        Turtle().run([["left", 45, "move", 5]])


def test_debug_polygon_builds_with_labels():
    p = Path([[0, 0], [40, 0], [40, 30], [0, 30]])
    assert isinstance(p.debug_polygon(size=3), Bosl2Solid)
    assert isinstance(p.debug_polygon(vertices=False), Bosl2Solid)


def test_debug_region_builds():
    r = Region.with_holes([[0, 0], [50, 0], [50, 50], [0, 50]],
                          [[15, 15], [35, 15], [35, 35], [15, 35]])
    assert isinstance(r.debug_region(size=3), Bosl2Solid)


def test_debug_region_single_path_defers_to_polygon():
    assert isinstance(Region([[[0, 0], [20, 0], [10, 20]]]).debug_region(), Bosl2Solid)

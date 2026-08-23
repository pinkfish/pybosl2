# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/distributors.py: the copier matrix generators and the Distributable methods on
Path2D / Path3D / Bosl2Solid. The matrices themselves are pinned to real BOSL2 in
tests/test_bosl2_reorient.py; here we check the object-level behaviour (what each host returns and
how the copies are placed). Native geometry is mocked, so Bosl2Solid tests assert type/union, not
mesh geometry (that is covered in test_stl_render.py)."""

import math

import numpy as np
import pytest

from pybosl2.distributors import (
    DistributableMatrix,
    _vec3,
    line_copies,
    path_copies,
    xdistribute,
    ydistribute,
    zdistribute,
)
from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D
from pybosl2.points import Point
from pybosl2.shapes3d import Bosl2Solid, cuboid

# -- matrix generators --------------------------------------------------------------------


def test_move_and_copy_matrices() -> None:
    from pybosl2._helpers import translate4

    mats = [translate4(pos) for pos in [[0, 0, 0], [10, 0, 0], [0, 5, 0]]]
    assert len(mats) == 3
    np.testing.assert_allclose(mats[1][:3, 3], [10, 0, 0], atol=1e-9)  # translation column


def test_xcopies_centered_by_default() -> None:
    mats = DistributableMatrix.xcopies(20, num_copies=3)
    xs = sorted(m[0, 3] for m in mats)
    np.testing.assert_allclose(xs, [-20, 0, 20], atol=1e-9)  # centered on origin


def test_xcopies_explicit_positions() -> None:
    mats = DistributableMatrix.xcopies([1, 2, 3, 5, 7])  # type: ignore[arg-type]
    xs = [m[0, 3] for m in mats]
    np.testing.assert_allclose(xs, [1, 2, 3, 5, 7], atol=1e-9)


def test_grid_copies_count_and_stagger() -> None:
    assert len(DistributableMatrix.grid_copies(num_copies=[3, 4], spacing=10)) == 12
    # a staggered grid drops/offsets alternate columns per row
    assert len(DistributableMatrix.grid_copies(spacing=8, num_copies=[4, 3], stagger=True)) == 6


def test_grid_copies_inside_polygon_filters() -> None:
    # only centers inside the small square survive
    poly = [[-6, -6], [6, -6], [6, 6], [-6, 6]]
    mats = DistributableMatrix.grid_copies(spacing=5, num_copies=[9, 9], inside=poly)
    assert 0 < len(mats) < 81
    for m in mats:
        assert -6 <= m[0, 3] <= 6
        assert -6 <= m[1, 3] <= 6


def test_arc_copies_positions_on_circle() -> None:
    mats = DistributableMatrix.arc_copies(num_copies=4, radius=10, sa=0, ea=360)
    # first copy sits on +X at radius 10
    np.testing.assert_allclose(mats[0][:3, 3], [10, 0, 0], atol=1e-9)


def test_mirror_copy_is_original_plus_reflection() -> None:
    mats = DistributableMatrix.mirror_copy([1, 0, 0])
    assert len(mats) == 2
    np.testing.assert_allclose(mats[0], np.eye(4), atol=1e-9)  # the original
    np.testing.assert_allclose(mats[1][:3, :3], np.diag([-1, 1, 1]), atol=1e-9)  # X reflection


# -- Path2D (2-D) returns a list of Path2D copies ---------------------------------------------

SQUARE = Path2D([[0, 0], [10, 0], [10, 10], [0, 10]])


def test_path_xcopies_returns_paths() -> None:
    copies = SQUARE.xcopies(20, num_copies=3)  # type: ignore[var-annotated]
    assert isinstance(copies, list)
    assert len(copies) == 3
    assert all(isinstance(c, Path2D) for c in copies)
    # middle copy is the original, right copy is shifted +20 in X
    np.testing.assert_allclose(copies[2][0], [20, 0], atol=1e-9)


def test_path_grid_and_arc_stay_2d() -> None:
    assert len(SQUARE.grid_copies(num_copies=[2, 3], spacing=25)) == 6
    assert all(isinstance(c, Path2D) for c in SQUARE.arc_copies(num_copies=5, radius=40))  # type: ignore[var-annotated]


def test_path_zrot_copies_in_plane() -> None:
    copies = SQUARE.zrot_copies(num_copies=4)  # type: ignore[var-annotated]
    assert len(copies) == 4
    assert all(isinstance(c, Path2D) for c in copies)


def test_path_out_of_plane_copier_raises() -> None:
    for call in (  # type: ignore[var-annotated]
        lambda: SQUARE.zcopies(10, num_copies=3),
        lambda: SQUARE.xrot_copies(num_copies=4, radius=10),
        lambda: SQUARE.sphere_copies(num_copies=8, radius=20),
    ):
        with pytest.raises(AssertionError):
            call()


def test_path_mirror_copy_2d() -> None:
    copies = SQUARE.xflip_copy(x=20)  # type: ignore[var-annotated]
    assert len(copies) == 2
    assert all(isinstance(c, Path2D) for c in copies)


# -- Path3D returns a list of Path3D copies -----------------------------------------------

SEG3 = Path3D([[0, 0, 0], [10, 0, 0], [10, 10, 5]], closed=False)


def test_path3d__zcopies() -> None:
    copies = SEG3.zcopies(15, num_copies=3)  # type: ignore[var-annotated]
    assert len(copies) == 3
    assert all(isinstance(c, Path3D) for c in copies)
    zs = sorted(c[0][2] for c in copies)
    np.testing.assert_allclose(zs, [-15, 0, 15], atol=1e-9)  # centered along Z


def test_path3d_xrot_copies_ring() -> None:
    copies = SEG3.xrot_copies(num_copies=6, radius=20)  # type: ignore[var-annotated]
    assert len(copies) == 6
    assert all(isinstance(c, Path3D) for c in copies)


def test_path3d_sphere_copies() -> None:
    copies = SEG3.sphere_copies(num_copies=10, radius=30)  # type: ignore[var-annotated]
    assert len(copies) == 10
    assert all(isinstance(c, Path3D) for c in copies)


# -- Bosl2Solid returns a unioned solid ---------------------------------------------------


def test_solid_grid_copies_returns_solid() -> None:
    """3 x 3 copies, 20 apart, centred on the origin."""
    copies = cuboid([10, 10, 10]).grid_copies(num_copies=[3, 3], spacing=20)  # type: ignore[var-annotated]
    assert len(copies) == 9
    assert all(isinstance(c, Bosl2Solid) for c in copies)
    centres = [[round(float(v), 3) for v in c.bounds()[0]] for c in copies]
    assert sorted({c[0] for c in centres}) == pytest.approx([-20.0, 0.0, 20.0])
    assert sorted({c[1] for c in centres}) == pytest.approx([-20.0, 0.0, 20.0])


def test_solid_ring_and_flip_return_solid() -> None:
    """Each copier places its copies where it says: on a ring, mirrored, or at named points."""
    box = cuboid([10, 10, 10])

    ring = box.zrot_copies(num_copies=6, radius=30)  # type: ignore[var-annotated]
    assert len(ring) == 6
    radii = [math.hypot(float(c.bounds()[0][0]), float(c.bounds()[0][1])) for c in ring]
    assert radii == pytest.approx([30.0] * 6)  # every copy the same distance out

    mirrored = box.right(20).xflip_copy()  # type: ignore[var-annotated]
    assert sorted(round(float(c.bounds()[0][0]), 3) for c in mirrored) == pytest.approx([-20.0, 20.0])

    placed = box.move_and_copy([Point(0, 0, 0), Point(20, 0, 0), Point(0, 20, 0)])  # type: ignore[var-annotated]
    corners = sorted((round(float(c.bounds()[0][0]), 3), round(float(c.bounds()[0][1]), 3)) for c in placed)
    assert corners == [(0.0, 0.0), (0.0, 20.0), (20.0, 0.0)]


def test_solid_path_copies_returns_solid() -> None:
    """Six copies spread along a 60mm dogleg: evenly spaced, starting at the path's own start."""
    box = cuboid([4, 4, 4])
    path = Path2D([[0, 0], [30, 0], [30, 30]])
    copies = box.path_copies(path, num_copies=6)  # type: ignore[arg-type, var-annotated]
    assert len(copies) == 6
    assert all(isinstance(c, Bosl2Solid) for c in copies)
    first = [round(float(v), 3) for v in copies[0].bounds()[0]]
    assert first == pytest.approx([0.0, 0.0, 0.0])
    last = [round(float(v), 3) for v in copies[-1].bounds()[0]]
    assert last[1] > 0  # the run turns the corner and climbs the second leg


# -- distribute (list of distinct children) -----------------------------------------------


def test_distribute_returns_solid() -> None:
    """Distributing lays the children out along one axis; the others keep the widest child."""
    a, b, c = cuboid([10, 10, 10]), cuboid([20, 20, 20]), cuboid([5, 5, 5])

    spread_x = xdistribute([a, b, c], spacing=5)
    assert isinstance(spread_x, Bosl2Solid)
    size_x = [float(v) for v in spread_x.bounds()[1]]
    assert size_x[0] > 20.0  # laid out along X
    assert size_x[1:] == pytest.approx([20.0, 20.0])  # ...and only as wide as the biggest child

    spread_y = ydistribute([a, b], sizes=[10, 20])
    assert float(spread_y.bounds()[1][1]) > float(spread_y.bounds()[1][0])

    spread_z = zdistribute([a, b, c], length=100)
    assert float(spread_z.bounds()[1][2]) >= 100.0  # the run fills the length it was given


# ── _vec3 edge cases ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("inp", "fill", "expected"),
    [
        (5, 0.0, np.array([5.0, 0.0, 0.0])),
        (np.array([7]), 1.0, np.array([7.0, 1.0, 1.0])),
    ],
)
def test_vec3_scalar_and_1d(inp: object, fill: float, expected: np.ndarray) -> None:
    np.testing.assert_allclose(_vec3(inp, fill=fill), expected)  # type: ignore[arg-type]


# ── line_copies branches ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("kwargs", "expected_count", "first_x", "last_x"),
    [
        pytest.param({"length": 30, "num_copies": 4}, 4, -15.0, 15.0, id="length+nc"),
        pytest.param({"p1": [10, 0, 0], "p2": [40, 0, 0], "num_copies": 4}, 4, 10.0, 40.0, id="p1p2+nc"),
        pytest.param({"spacing": 10, "length": 30, "num_copies": 4}, 4, -15.0, 15.0, id="spacing+length+nc"),
        pytest.param({"num_copies": 1}, 1, 0.0, 0.0, id="nc=1"),
    ],
)
def test_line_copies_branches(kwargs: dict[str, object], expected_count: int, first_x: float, last_x: float) -> None:
    mats = line_copies(**kwargs)  # type: ignore[arg-type]
    assert len(mats) == expected_count
    if expected_count > 0:
        np.testing.assert_allclose(mats[0][0, 3], first_x, atol=1e-9)
        np.testing.assert_allclose(mats[-1][0, 3], last_x, atol=1e-9)


# ── _axis_copies branches ────────────────────────────────────────────────


def test_xcopies_scalar_start_pos() -> None:
    mats = DistributableMatrix.xcopies(10, num_copies=3, start_pos=5)
    xs = sorted(m[0, 3] for m in mats)
    np.testing.assert_allclose(xs, [5, 15, 25], atol=1e-9)


def test_xcopies_point_start_pos() -> None:
    mats = DistributableMatrix.xcopies(10, num_copies=3, start_pos=Point(5, 2, 0))
    xs = sorted(m[0, 3] for m in mats)
    np.testing.assert_allclose(xs, [5, 15, 25], atol=1e-9)


def test_xcopies_explicit_spacing_list() -> None:
    mats = DistributableMatrix.xcopies([1, 10, 20, 50])
    xs = [m[0, 3] for m in mats]
    np.testing.assert_allclose(xs, [1, 10, 20, 50], atol=1e-9)


def test_xcopies_with_length() -> None:
    mats = DistributableMatrix.xcopies(length=30, num_copies=4)
    xs = sorted(m[0, 3] for m in mats)
    np.testing.assert_allclose(xs, [-15, -5, 5, 15], atol=1e-9)


# ── ycopies / zcopies direct ─────────────────────────────────────────────


def test_ycopies_direct() -> None:
    mats = DistributableMatrix.ycopies(15, num_copies=3)
    ys = sorted(m[1, 3] for m in mats)
    np.testing.assert_allclose(ys, [-15, 0, 15], atol=1e-9)


def test_zcopies_direct() -> None:
    mats = DistributableMatrix.zcopies(15, num_copies=3)
    zs = sorted(m[2, 3] for m in mats)
    np.testing.assert_allclose(zs, [-15, 0, 15], atol=1e-9)


# ── grid_copies branches ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("kwargs", "expected_count"),
    [
        ({"size": 40, "spacing": 10}, 25),
        ({"spacing": [12, 8], "num_copies": [3, 5]}, 15),
        ({"size": 40, "num_copies": 5}, 25),
        ({"size": [40, 30], "num_copies": [5, 4]}, 20),
        ({"spacing": 10, "num_copies": 4}, 16),
        ({}, 4),
        ({"spacing": 8, "num_copies": [4, 3], "stagger": "alt"}, 6),
    ],
)
def test_grid_copies_branches(kwargs: dict[str, object], expected_count: int) -> None:
    mats = DistributableMatrix.grid_copies(**kwargs)  # type: ignore[arg-type]
    assert len(mats) == expected_count


# ── rot_copies branches ──────────────────────────────────────────────────


def test_rot_copies_explicit_angles() -> None:
    mats = DistributableMatrix.rot_copies(rots=[0, 90, 180, 270], num_copies=None)
    assert len(mats) == 4


def test_rot_copies_uses_rots_when_num_copies_omitted() -> None:
    # num_copies defaults to None, not 1: an explicit rots list is what BOSL2 rotates by, and a
    # default of 1 would silently swallow it and hand back a single identity copy.
    for copier in (
        DistributableMatrix.rot_copies,
        DistributableMatrix.xrot_copies,
        DistributableMatrix.yrot_copies,
        DistributableMatrix.zrot_copies,
    ):
        assert len(copier(rots=[0, 90, 180])) == 3, copier.__name__


def test_axis_copies_count_from_spacing_and_length() -> None:
    # Same regression on the line copiers: with no num_copies the count comes from length/spacing.
    assert len(DistributableMatrix.xcopies(spacing=10, length=100)) == 11
    assert len(DistributableMatrix.ycopies(spacing=10, length=100)) == 11
    assert len(DistributableMatrix.zcopies(spacing=10, length=100)) == 11
    assert len(line_copies(spacing=10, length=100)) == 11


def test_arc_copies_default_count() -> None:
    assert len(DistributableMatrix.arc_copies(radius=20)) == 6


def test_rot_copies_subrot_false() -> None:
    mats = DistributableMatrix.rot_copies(num_copies=6, delta=[20, 0, 0], subrot=False, v=[0, 0, 1])
    assert len(mats) == 6


def test_rot_copies_custom_axis_offset() -> None:
    mats = DistributableMatrix.rot_copies(num_copies=4, v=[1, 0, 0], offset=45, sa=10)
    assert len(mats) == 4


def test_rot_copies_zero_copies() -> None:
    mats = DistributableMatrix.rot_copies(num_copies=0)
    assert len(mats) == 0


# ── yrot_copies direct ───────────────────────────────────────────────────


def test_yrot_copies_direct() -> None:
    mats = DistributableMatrix.yrot_copies(num_copies=4, radius=10)
    assert len(mats) == 4
    for m in mats:
        dist = math.hypot(m[0, 3], m[1, 3], m[2, 3])
        np.testing.assert_allclose(dist, 10, atol=1e-9)


def test_yrot_copies_diameter() -> None:
    mats = DistributableMatrix.yrot_copies(num_copies=4, diameter=20)
    assert len(mats) == 4


# ── path_copies branches ─────────────────────────────────────────────────


def test_path_copies_explicit_dist() -> None:
    mats = path_copies([[0, 0], [30, 0], [30, 30]], dist=[5, 20, 50])
    assert len(mats) == 3


def test_path_copies_start_pos_with_num_copies() -> None:
    mats = path_copies([[0, 0], [30, 0], [30, 30]], start_pos=5, num_copies=4)
    assert len(mats) == 4


def test_path_copies_spacing_only() -> None:
    mats = path_copies([[0, 0], [40, 0]], spacing=10, num_copies=None)
    assert len(mats) >= 3


def test_path_copies_rotate_children_false() -> None:
    mats = path_copies([[0, 0], [30, 0], [30, 30]], num_copies=3, rotate_children=False)
    assert len(mats) == 3
    for m in mats:
        np.testing.assert_allclose(m[:3, :3], np.eye(3), atol=1e-9)


def test_path_copies_3d() -> None:
    mats = path_copies([[0, 0, 0], [100, 0, 0]], dist=[0, 50, 100])
    assert len(mats) == 3
    assert all(m.shape == (4, 4) for m in mats)


# ── flip copies direct ───────────────────────────────────────────────────


def test_yflip_copy_direct() -> None:
    mats = DistributableMatrix.yflip_copy(offset=5)
    assert len(mats) == 2


def test_zflip_copy_direct() -> None:
    mats = DistributableMatrix.zflip_copy(offset=10, z=5)
    assert len(mats) == 2


# ── Distributable instance methods ───────────────────────────────────────


def test_path_line_copies_instance() -> None:
    sq = Path2D([[0, 0], [10, 0], [10, 10], [0, 10]])
    copies = sq.line_copies(spacing=20, num_copies=3)
    assert len(copies) == 3
    assert all(isinstance(c, Path2D) for c in copies)


def test_path_ycopies_instance() -> None:
    sq = Path2D([[0, 0], [10, 0], [10, 10], [0, 10]])
    copies = sq.ycopies(15, num_copies=3)
    assert len(copies) == 3
    assert all(isinstance(c, Path2D) for c in copies)


def test_solid_rot_copies_instance() -> None:
    result = cuboid([10, 10, 10]).rot_copies(num_copies=4, v=[0, 0, 1])
    assert len(result) == 4
    assert all(isinstance(c, Bosl2Solid) for c in result)


def test_solid_yrot_copies_instance() -> None:
    result = cuboid([5, 5, 5]).yrot_copies(num_copies=6, radius=20)
    assert len(result) == 6
    assert all(isinstance(c, Bosl2Solid) for c in result)


def test_solid_mirror_copy_instance() -> None:
    result = cuboid([10, 10, 10]).mirror_copy([0, 1, 0])
    assert len(result) == 2
    assert all(isinstance(c, Bosl2Solid) for c in result)


def test_solid_yflip_copy_instance() -> None:
    result = cuboid([10, 10, 10]).yflip_copy(offset=5, y=10)
    assert len(result) == 2
    assert all(isinstance(c, Bosl2Solid) for c in result)


def test_solid_zflip_copy_instance() -> None:
    result = cuboid([10, 10, 10]).zflip_copy(offset=2, z=0)
    assert len(result) == 2
    assert all(isinstance(c, Bosl2Solid) for c in result)


# --- distribute_on_path -------------------------------------------------------------------
#
# Copies are placed at measured distances along the path and turned to face along it. A copy
# that is rotated about the world origin instead of its own still "builds", so these check
# where the copies actually land.

DIST_LINE = [[0, 0, 0], [100, 0, 0]]  # 100 long
DIST_LOOP = [[0, 0, 0], [100, 0, 0], [100, 100, 0], [0, 100, 0]]  # closed: 400 round
DIST_RAMP = [[0, 0, 0], [100, 0, 100]]  # climbs out of the XY plane


def _spread(path_pts: list[list[float]], *, closed: bool = False, **kwargs: object) -> tuple[list[float], list[float]]:
    """Distribute a 4mm cube along the path and return (centre, size) of the union."""
    from pybosl2.path3d import Path3D

    result = cuboid([4, 4, 4]).distribute_on_path(Path3D(path_pts, closed=closed), **kwargs)  # type: ignore[arg-type]
    centre, size = result.bounds()
    return [float(v) for v in centre], [float(v) for v in size]


def test_copies_along_a_closed_loop_stay_in_its_plane() -> None:
    """The loop lies flat in Z, so the copies must too: a rotation applied about the world
    origin instead of each copy's own threw them a long way out of the plane."""
    centre, size = _spread(DIST_LOOP, closed=True, num_copies=4)
    assert centre == pytest.approx([50.0, 50.0, 0.0])  # the square's own centre
    assert float(size[2]) == pytest.approx(4.0)  # just the cube's thickness, still flat


def test_copies_are_turned_to_face_along_the_path() -> None:
    """At each corner of the loop the cube is turned 45 degrees, so the union reaches out by the
    cube's diagonal rather than its side."""
    _c1, turned = _spread(DIST_LOOP, closed=True, num_copies=4)
    _c2, square_on = _spread(DIST_LOOP, closed=True, num_copies=4, rotate_children=False)
    assert float(square_on[0]) == pytest.approx(104.0)  # 100 apart + a 4mm cube
    assert float(turned[0]) == pytest.approx(100.0 + 4 * math.sqrt(2), abs=0.01)


def test_copies_follow_a_path_that_climbs() -> None:
    """A path out of the XY plane is the case a world-origin rotation gets most wrong."""
    centre, size = _spread(DIST_RAMP, num_copies=3)
    assert centre == pytest.approx([50.0, 0.0, 50.0])  # the ramp's midpoint
    assert float(size[1]) == pytest.approx(4.0)  # nothing strays sideways


@pytest.mark.parametrize(
    ("kwargs", "expected_centre", "expected_span"),
    [
        ({"num_copies": 5}, 50.0, 104.0),  # 0, 25, 50, 75, 100
        ({"spacing": 25}, 50.0, 104.0),  # the same five, spaced instead of counted
        ({"dist": [0, 50, 100]}, 50.0, 104.0),  # given explicitly
        ({"start_pos": 10, "num_copies": 3, "spacing": 20}, 30.0, 44.0),  # 10, 30, 50
        ({"start_pos": 10, "num_copies": 3}, 55.0, 94.0),  # 10, 55, 100: spread to the end
        ({"start_pos": 10, "spacing": 30}, 40.0, 64.0),  # 10, 40, 70: stepped to the end
    ],
)
def test_the_distribution_modes_place_the_copies_where_they_say(
    kwargs: dict[str, object], expected_centre: float, expected_span: float
) -> None:
    """Each way of asking for positions puts the copies at those positions along the path."""
    centre, size = _spread(DIST_LINE, **kwargs)
    assert float(centre[0]) == pytest.approx(expected_centre)
    assert float(size[0]) == pytest.approx(expected_span)


def test_distribute_on_path_needs_to_be_told_where() -> None:
    """With no count, spacing or distances there is nothing to work from."""
    from pybosl2.path3d import Path3D

    with pytest.raises(ValueError, match="provide num_copies, spacing, or dist"):
        cuboid([4, 4, 4]).distribute_on_path(Path3D(DIST_LINE))

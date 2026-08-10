# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/paths.py: the Path2D list-subclass and its private static kernels."""

import math

import numpy as np
import pytest

from pybosl2.color import Color
from pybosl2.path2d import Path2D
from pybosl2.points import Point

SQUARE = [[0, 0], [80, 0], [80, 60], [0, 60]]
UNIT = [[0, 0], [10, 0], [10, 10], [0, 10]]


# -- construction / drop-in list behaviour ------------------------------------------------


def test_is_a_list_of_plain_floats() -> None:
    p = Path2D(np.asarray(SQUARE, dtype=float))
    assert isinstance(p, Path2D)
    assert p.to_list == [[float(x), float(y)] for x, y in SQUARE]
    assert len(p) == 4
    assert list(p[0]) == [0.0, 0.0]
    assert list(p[2]) == [80.0, 60.0]
    assert list(p[-1]) == [0.0, 60.0]


def test_rejects_non_xy_points() -> None:
    with pytest.raises(AssertionError):
        Path2D([[0, 0, 0], [1, 1, 1]])


def test_empty_path() -> None:
    p = Path2D()
    assert len(p) == 0
    assert p.closed is False  # paths are open unless asked for a loop, as in BOSL2
    assert p.to_list == []
    assert p.array.shape == (0,)


def test_array_property() -> None:
    assert Path2D(SQUARE).array.shape == (4, 2)
    assert Path2D([]).array.shape == (0,)
    assert Path2D(UNIT).array.shape == (4, 2)


def test_array_is_shared_and_read_only() -> None:
    """The point array is handed out rather than rebuilt per access, so it must not be written to.

    The path operations reach for it inside their loops; rebuilding it each time made them
    quadratic in the point count. Sharing it is only safe while nobody writes through it, so it
    comes back read-only -- a caller that needs to write takes a copy.
    """
    path = Path2D(SQUARE)
    assert path.array is path.array  # the same array every time, not a fresh one
    with pytest.raises(ValueError, match="read-only"):
        path.array[0][0] = 99.0
    source = np.array(SQUARE, dtype=float)  # and the path does not alias what it was built from
    built = Path2D(source)
    source[0][0] = 99.0
    assert built.array[0][0] == 0.0


# -- measurement --------------------------------------------------------------------------


def test_bounds_width_length() -> None:
    p = Path2D(SQUARE)
    bounds = p.bounds()
    assert bounds.min_x == 0
    assert bounds.min_y == 0
    assert bounds.max_x == 80
    assert bounds.max_y == 60
    assert bounds.width == 80
    assert bounds.length == 60
    assert bounds.size == (80.0, 60.0)
    assert bounds.center == Point(40.0, 30.0)


def test_area() -> None:
    assert Path2D(SQUARE).area() == 4800
    assert Path2D(SQUARE).area(signed=True) == 4800  # CCW is positive
    assert Path2D(list(reversed(SQUARE))).area(signed=True) == -4800
    assert Path2D(UNIT).area() == 100
    assert Path2D(UNIT).area(signed=True) == 100


def test_is_clockwise() -> None:
    assert not Path2D(SQUARE).is_clockwise()
    assert Path2D(list(reversed(SQUARE))).is_clockwise()
    assert Path2D(SQUARE).is_clockwise() is False
    assert Path2D(list(reversed(UNIT))).is_clockwise()


def test_perimeter_closed_vs_open() -> None:
    assert Path2D(SQUARE, closed=True).perimeter() == 280  # four sides, incl. the closing edge
    assert Path2D(SQUARE).perimeter() == 220  # open by default
    assert Path2D(SQUARE, closed=False).perimeter() == 220  # three segments, no closing edge
    assert Path2D(UNIT, closed=True).perimeter() == 40
    assert Path2D(UNIT, closed=False).perimeter() == 30
    # perimeter() is the sum of segment_lengths(), for closed and open alike
    for path in (Path2D(SQUARE), Path2D(SQUARE, closed=True)):
        assert math.isclose(path.perimeter(), float(np.sum(path.segment_lengths())))


def test_segment_lengths_and_fractions() -> None:
    p = Path2D(SQUARE, closed=True)
    np.testing.assert_allclose(p.segment_lengths(), [80, 60, 80, 60])
    fr = p.length_fractions()
    assert len(fr) == 5
    assert math.isclose(fr[0], 0.0)
    assert math.isclose(fr[-1], 1.0)
    assert math.isclose(sum(p.segment_lengths()), 280.0)  # 80+60+80+60


def test_is_closed_property() -> None:
    assert Path2D([[0, 0], [10, 0], [10, 10], [0, 0]]).is_closed is True
    assert Path2D(SQUARE).is_closed is False  # endpoints differ
    assert len(Path2D(SQUARE)) == 4
    assert Path2D(SQUARE).is_closed is False


def test_contains_reads_the_outline_as_a_region() -> None:
    # contains() is a region query, so the outline is read as a ring either way -- `closed`
    # is about traversal (length, tangents), not about whether an outline bounds an area.
    for p in (Path2D(SQUARE), Path2D(SQUARE, closed=True)):
        assert p.contains([40, 30]) is True
        assert p.contains([100, 100]) is False
        assert p.contains([-1, -1]) is False


def test_is_simple() -> None:
    assert Path2D(SQUARE).is_simple()
    figure8 = [[0, 0], [2, 2], [0, 2], [2, 0]]
    assert not Path2D(figure8).is_simple()
    assert len(Path2D(figure8)) == 4
    assert Path2D(UNIT).is_simple()


def test_closest_point() -> None:
    from pybosl2.points import Point

    pt = Path2D(SQUARE).closest_point([40, -5])
    assert isinstance(pt, Point)
    assert pt.is_2d
    assert pt.z is None
    np.testing.assert_allclose([pt.x, pt.y], [40, 0], atol=1e-9)
    assert pt.x == pytest.approx(40.0)
    assert pt.y == pytest.approx(0.0)


# -- tangents / normals / curvature -------------------------------------------------------


def test_tangents_are_unit() -> None:
    t = Path2D(SQUARE).tangents()
    ta = np.asarray(t)
    assert ta.shape == (4, 2)  # one tangent per POINT, not per segment
    np.testing.assert_allclose(np.linalg.norm(ta, axis=1), 1.0)


def test_tangents_one_per_point_open_and_closed() -> None:
    # The uniform=True branch used to return one tangent per SEGMENT, which made an open
    # path come back one short and blew up smooth_path() with an IndexError.
    for uniform in (True, False):
        assert len(Path2D(SQUARE, closed=False).tangents(uniform=uniform)) == len(SQUARE)
        assert len(Path2D(SQUARE, closed=True).tangents(uniform=uniform)) == len(SQUARE)


def test_tangents_nonuniform_is_not_a_central_difference() -> None:
    # uniform=False must be BOSL2's deriv(path, h=segment_lengths), which accounts for
    # uneven spacing; a plain central difference normalize(p[i+1] - p[i-1]) does not.
    pts = [[0, 0], [1, 10], [40, 12], [42, 0]]
    got = np.asarray(Path2D(pts, closed=False).tangents(uniform=False))
    central = np.asarray([np.subtract(pts[2], pts[0]), np.subtract(pts[3], pts[1])], dtype=float)
    central /= np.linalg.norm(central, axis=1, keepdims=True)
    assert not np.allclose(got[1:3], central, atol=1e-4)


def test_normals_perpendicular_to_tangents() -> None:
    p = Path2D(SQUARE)
    t, sides = p.tangents(), p.normals()
    ta, sa = np.asarray(t), np.asarray(sides)
    assert sa.shape == (4, 2)
    for i in range(len(p)):
        assert abs(float(np.dot(ta[i], sa[i]))) < 1e-9


def test_curvature_of_straightish_polygon() -> None:
    c = Path2D(SQUARE).curvature()
    assert c.shape == (len(c),)
    assert len(c) == 4  # one value per point, matching tangents()
    assert not np.any(np.isnan(c))


# -- degenerate paths ---------------------------------------------------------------------
#
# A path too short to have the thing being measured MEASURES ZERO; it does not raise. These
# all route through numpy derivatives that index [1] and [2] unguarded, so without the
# length checks an empty path comes back as an IndexError from inside deriv().


@pytest.mark.parametrize(
    "path",
    [
        Path2D(),
        Path2D([], closed=True),  # nothing to join, so closing changes nothing
        Path2D([[1.0, 2.0]]),
    ],
)
def test_no_segments_measures_empty(path: Path2D) -> None:
    """Fewer than two points means no segment to measure."""
    assert path.segment_lengths().shape == (0,)
    assert path.perimeter() == 0.0


def test_closed_single_point_has_one_zero_length_segment() -> None:
    # Closing a single point joins it to ITSELF, which is a segment -- of length zero. This is
    # the one short case where closed differs from open, and it is what keeps
    # len(segment_lengths(closed=True)) == len(path) for tangent_array's non-uniform sampling.
    lengths = Path2D([[1.0, 2.0]], closed=True).segment_lengths()
    assert lengths.shape == (1,)
    assert lengths[0] == 0.0
    assert Path2D([[1.0, 2.0]]).segment_lengths().shape == (0,)


@pytest.mark.parametrize("path", [Path2D(), Path2D([[1.0, 2.0]])])
def test_short_path_tangents_are_one_per_point(path: Path2D) -> None:
    # Still one per point, the same as any other path -- an empty path just gets none.
    assert len(path.tangents()) == len(path)
    assert path.tangent_array().shape == (len(path), 2)


def test_single_point_tangent_falls_back_to_x() -> None:
    # One point gives nothing to differentiate, so the tangent is +x by convention.
    np.testing.assert_allclose(list(Path2D([[1.0, 2.0]]).tangents()[0]), [1.0, 0.0])


@pytest.mark.parametrize(
    "path",
    [Path2D(), Path2D([[1.0, 2.0]]), Path2D([[0.0, 0.0], [1.0, 0.0]])],
)
def test_curvature_needs_three_points(path: Path2D) -> None:
    """Two points can only make a straight line, so curvature is zero rather than undefined."""
    curvature = path.curvature()
    assert curvature.shape == (len(path),)
    assert not np.any(curvature)


# -- derived paths ------------------------------------------------------------------------


def test_offset_shrinks_area() -> None:
    o1 = Path2D(UNIT).offset(radius=-1)
    assert math.isclose(o1.area(), 64.0, abs_tol=1e-6)
    assert len(o1) == 4
    assert o1.closed
    o2 = Path2D(UNIT).offset(delta=-1)
    assert math.isclose(o2.area(), 64.0, abs_tol=1e-6)


def test_offset_returns_path() -> None:
    o = Path2D(UNIT).offset(radius=-1)
    assert isinstance(o, Path2D)
    assert len(o) == 4
    assert o.closed


def test_offset_needs_exactly_one_of_r_delta() -> None:
    with pytest.raises(AssertionError):
        Path2D(UNIT).offset()
    with pytest.raises(AssertionError):
        Path2D(UNIT).offset(radius=1, delta=1)


# -- offset must not fold over itself -----------------------------------------------------
#
# Every one of these produced silently broken geometry before the offset validity check:
# self-intersecting outlines from arcs/mitres that folded back over the path, and inside-out
# outlines when the path was shrunk past its own width.


def _star(points: int = 6, r_out: float = 30.0, r_in: float = 12.0) -> Path2D:
    """A spiky star: adjacent concave corners are close enough for their offsets to collide."""
    return Path2D(
        [
            [
                (r_out if i % 2 == 0 else r_in) * math.cos(math.pi * i / points),
                (r_out if i % 2 == 0 else r_in) * math.sin(math.pi * i / points),
            ]
            for i in range(points * 2)
        ]
    )


def _toothed_circle(teeth: int = 12, sides: int = 120, radius: float = 20.0, tooth: float = 2.5) -> Path2D:
    """A finely sampled outline with detail -- the shape that broke offset() in the wild."""
    step = sides // (teeth * 2)
    return Path2D(
        [
            [
                (radius + (tooth if (i // step) % 2 == 0 else 0)) * math.cos(2 * math.pi * i / sides),
                (radius + (tooth if (i // step) % 2 == 0 else 0)) * math.sin(2 * math.pi * i / sides),
            ]
            for i in range(sides)
        ]
    )


@pytest.mark.parametrize("amount", [-1.0, -2.0, -3.0, -5.0, -10.0, 1.0, 2.0, 3.0])
def test_offset_of_detailed_outline_is_simple(amount: float) -> None:
    """A detailed outline offset by anything stays a simple polygon (both join styles)."""
    outline = _toothed_circle()
    for offset in (outline.offset(radius=amount), outline.offset(delta=amount)):
        assert offset.is_path_simple(), f"offset by {amount} self-intersects"
        assert offset.is_simple()


@pytest.mark.parametrize("radius", [-2.0, -4.0, -6.0, -8.0, -10.0])
def test_offset_of_spiky_star_is_simple(radius: float) -> None:
    """Inward offsets whose corner arcs overlap each other must not leave the overlap in."""
    offset = _star().offset(radius=radius)
    assert offset.is_path_simple()
    assert offset.area() < _star().area()


def test_offset_keeps_winding_and_shrinks() -> None:
    """Shrinking must shrink: it must not turn the outline inside out."""
    outline = _toothed_circle()
    before = Path2D.polygon_area(outline, signed=True)
    for amount in (-1.0, -3.0, -6.0):
        for offset in (outline.offset(radius=amount), outline.offset(delta=amount)):
            after = Path2D.polygon_area(offset, signed=True)
            assert math.copysign(1, after) == math.copysign(1, before)  # same winding
            assert abs(after) < abs(before)  # actually smaller


def test_offset_past_half_width_raises_instead_of_inverting() -> None:
    """A 10-wide square shrunk by 8 has nothing left -- it used to come back inside out."""
    with pytest.raises(AssertionError, match="collapsed"):
        Path2D(UNIT).offset(delta=-8)
    with pytest.raises(AssertionError, match="collapsed"):
        Path2D(UNIT).offset(radius=-8)


def test_offset_collapsing_a_thin_arm_raises() -> None:
    """An L with 10-wide arms cannot be inset by 6; it used to return a bigger, folded outline."""
    ell = Path2D([[0, 0], [40, 0], [40, 10], [10, 10], [10, 40], [0, 40]])
    with pytest.raises(AssertionError, match="collapsed"):
        ell.offset(delta=-6)
    with pytest.raises(AssertionError, match="collapsed"):
        ell.offset(radius=-6)


def test_offset_just_inside_the_limit_still_works() -> None:
    """The check only rejects what really collapsed -- 4.9 of a 10-wide square is fine."""
    offset = Path2D(UNIT).offset(delta=-4.9)
    assert offset.is_path_simple()
    assert offset.area() == pytest.approx(0.04, abs=1e-6)


def test_offset_area_tracks_shapely_erosion() -> None:
    """Cross-check the offset areas against Shapely's buffer as an independent oracle.

    Dropping a folded edge takes the whole edge with it, so where an offset eats a feature (the
    teeth here) the result comes out slightly small -- never large, which is the safe direction
    for an inset.
    """
    from shapely.geometry import Polygon

    for outline in (_toothed_circle(), _star()):
        polygon = Polygon(np.vstack([outline.array, outline.array[:1]]).tolist())
        for amount in (-1.0, -2.0, -4.0, 1.0, 2.0):
            got = outline.offset(radius=amount).area()
            want = polygon.buffer(amount, join_style="round", quad_segs=64).area
            assert got == pytest.approx(want, rel=0.07), f"offset({amount}) area {got} vs shapely {want}"


def test_offset_of_a_rounded_outline_keeps_its_walls() -> None:
    """Insetting past a corner radius must square the corner off, not throw the outline away."""
    centres = ((8, -8, -90), (8, 8, 0), (-8, 8, 90), (-8, -8, 180))  # ccw, each with a radius-2 corner
    rounded = Path2D(
        [
            [cx + 2 * math.cos(math.radians(a)), cy + 2 * math.sin(math.radians(a))]
            for cx, cy, start in centres
            for a in np.linspace(start, start + 90, 6)
        ]
    )
    inset = rounded.offset(delta=-3)  # 3 > the 2 corner radius, so the corners collapse to points
    assert inset.is_path_simple()
    assert inset.area() == pytest.approx(14 * 14, rel=0.01)


def test_offset_that_splits_the_shape_stays_simple() -> None:
    """A dumbbell pinched through its neck cannot be two Path2Ds, but must still be valid."""
    dumbbell = Path2D(
        [
            [0, 0],
            [40, 0],
            [40, 20],
            [25, 20],
            [25, 25],
            [40, 25],
            [40, 45],
            [0, 45],
            [0, 25],
            [15, 25],
            [15, 20],
            [0, 20],
        ]
    )
    for amount in (-6.0, -8.0, -10.0):
        offset = dumbbell.offset(radius=amount)
        assert offset.is_path_simple(), f"offset by {amount} self-intersects"
        assert offset.area() > 0


def test_offset_same_length_keeps_one_point_per_input_point() -> None:
    """path_sweep2d() needs the offset to line up with the path point for point.

    It gets the raw construction, so it stays point-for-point; every other caller gets the
    repaired outline, which is shorter wherever a folded edge was dropped.
    """
    wavy = Path2D([[t, 8 * math.sin(t / 12)] for t in range(0, 90, 3)])
    for amount in (-2.0, 2.0):
        offset = wavy.offset(delta=amount, same_length=True)
        assert len(offset) == len(wavy)
        # each point sits out by the offset distance from its own point (a shade more at a
        # corner, where the mitre reaches), not somewhere else along the path
        displacement = np.linalg.norm(np.asarray(offset.to_list) - wavy.array, axis=1)
        assert float(displacement.min()) >= abs(amount) - 1e-9
        assert float(np.median(displacement)) < 1.5 * abs(amount)
    assert len(wavy.offset(delta=-2.0)) < len(wavy)  # without it, folded corners are dropped


def test_offset_same_length_rejects_joins_that_add_points() -> None:
    with pytest.raises(AssertionError, match="same_length"):
        Path2D(UNIT).offset(radius=-1, same_length=True)
    with pytest.raises(AssertionError, match="same_length"):
        Path2D(UNIT).offset(delta=-1, chamfer=True, same_length=True)


def test_offset_leaves_convex_outlines_untouched() -> None:
    """The validity check must not disturb offsets that never fold: a square stays a square."""
    assert Path2D(UNIT).offset(delta=-1).to_list == [[1, 1], [9, 1], [9, 9], [1, 9]]
    assert Path2D(UNIT).offset(delta=2).to_list == [[-2, -2], [12, -2], [12, 12], [-2, 12]]
    assert len(Path2D(UNIT).offset(radius=-1)) == 4


def test_round_corners_inserts_points() -> None:
    out = Path2D(UNIT, closed=True).round_corners(radius=2)
    assert isinstance(out, Path2D)
    assert len(out) > len(UNIT)
    assert len(out) == 12
    assert out.closed
    assert out.area() == pytest.approx(95.3, abs=1.0)


def test_merge_collinear_drops_midpoints() -> None:
    p = Path2D([[0, 0], [5, 0], [10, 0], [10, 10], [0, 10]], closed=True)
    assert len(p) == 5
    result = p.merge_collinear()
    assert len(result) == 4
    assert result.closed
    np.testing.assert_allclose(result[0], [0.0, 0.0])


def test_deduplicated() -> None:
    p = Path2D([[0, 0], [0, 0], [1, 0], [1, 1]])
    assert len(p) == 4
    result = p.deduplicated()
    assert len(result) == 3
    assert list(result[0]) == [0.0, 0.0]
    assert list(result[1]) == [1.0, 0.0]
    assert list(result[2]) == [1.0, 1.0]


def test_reverse() -> None:
    p = Path2D(SQUARE).reverse()
    assert len(p) == 4
    np.testing.assert_allclose(p[0], SQUARE[-1])
    np.testing.assert_allclose(p[-1], SQUARE[0])
    np.testing.assert_allclose(p[1], SQUARE[-2])


def test_close_and_cleanup() -> None:
    open_sq = Path2D(SQUARE)
    closed = open_sq.close()
    np.testing.assert_allclose(closed[-1], closed[0])
    assert len(closed) == 5
    cleaned = closed.cleanup()
    assert len(cleaned) == 4
    np.testing.assert_allclose(cleaned, open_sq)


def test_subdivide_adds_points() -> None:
    out = Path2D(SQUARE, closed=True).subdivide(num_copies=8)
    assert len(out) == 8
    assert out.closed
    assert isinstance(out, Path2D)


def test_resample_to_n_points() -> None:
    out = Path2D(SQUARE, closed=True).resample(num_copies=12)
    assert len(out) == 12
    assert out.closed
    assert isinstance(out, Path2D)


def test_cut_splits_into_subpaths() -> None:
    parts = Path2D(SQUARE).cut([100, 200])
    assert len(parts) == 3
    assert all(isinstance(p, Path2D) for p in parts)
    assert len(parts[0]) == 3
    assert len(parts[1]) == 3
    assert len(parts[2]) == 2


def test_cut_points_along_open_path() -> None:
    pts = Path2D([[0, 0], [10, 0]], closed=False).cut_points([5])
    np.testing.assert_allclose(pts[0].point, [5, 0], atol=1e-9)
    assert isinstance(pts[0].point, Point)
    assert pts[0].point.x == pytest.approx(5.0)
    assert pts[0].point.y == pytest.approx(0.0)


# -- transforms ---------------------------------------------------------------------------


def test_translate_and_move_alias() -> None:
    p = Path2D(UNIT).translate([1, 2])
    np.testing.assert_allclose(p[0], [1, 2])
    assert len(p) == 4
    np.testing.assert_allclose(Path2D(UNIT).move([1, 2])[0], [1, 2])
    np.testing.assert_allclose(p[-1], [1, 12])


def test_directional_moves() -> None:
    p = Path2D([[1, 1], [2, 1]], closed=False)
    np.testing.assert_allclose(p.right(5)[0], [6, 1])
    np.testing.assert_allclose(p.right(5)[1], [7, 1])
    np.testing.assert_allclose(p.left(5)[0], [-4, 1])
    np.testing.assert_allclose(p.left(5)[1], [-3, 1])
    np.testing.assert_allclose(p.back(5)[0], [1, 6])
    np.testing.assert_allclose(p.forward(5)[0], [1, -4])
    np.testing.assert_allclose(p.fwd(5)[0], [1, -4])


def test_rot_and_rotate_alias() -> None:
    p = Path2D([[1, 0], [2, 0]], closed=False).rot(90)
    np.testing.assert_allclose(p[0], [0, 1], atol=1e-9)
    assert len(p) == 2
    np.testing.assert_allclose(Path2D([[1, 0], [2, 0]], closed=False).rotate(90)[0], [0, 1], atol=1e-9)


def test_mirror_across_y_axis() -> None:
    p = Path2D([[3, 2], [4, 2]], closed=False).mirror([1, 0])
    np.testing.assert_allclose(p[0], [-3, 2], atol=1e-9)
    assert len(p) == 2
    np.testing.assert_allclose(p[1], [-4, 2], atol=1e-9)


def test_yflip() -> None:
    p = Path2D([[3, 2], [4, 2]], closed=False).yflip()
    np.testing.assert_allclose(p[0], [3, -2], atol=1e-9)
    assert len(p) == 2
    np.testing.assert_allclose(p[1], [4, -2], atol=1e-9)


# -- conversion ---------------------------------------------------------------------------


def test_to_region() -> None:
    from pybosl2.regions import Region

    radius = Path2D(SQUARE).to_region()
    assert isinstance(radius, Region)
    assert len(radius) == 1


def test_polygon_and_geometry_use_mock() -> None:
    poly = Path2D(SQUARE).polygon()
    geom = Path2D(SQUARE).geometry()
    assert poly is not None
    assert geom is not None


# -- splitting ----------------------------------------------------------------------------


def test_polygon_parts_of_simple_square() -> None:
    parts = Path2D(SQUARE, closed=True).polygon_parts()
    assert len(parts) == 1
    assert all(isinstance(p, Path2D) for p in parts)
    assert len(parts[0]) == 4
    assert parts[0].closed


def test_split_at_self_crossings() -> None:
    figure8 = [[0, 0], [2, 2], [0, 2], [2, 0]]
    subs = Path2D(figure8).split_at_self_crossings()
    assert len(subs) >= 2
    assert len(subs) == 3
    assert all(isinstance(s, Path2D) for s in subs)
    assert len(subs[0]) == 2
    assert len(subs[1]) == 4
    assert len(subs[2]) == 2


# -- private static kernels ---------------------------------------------------------------


def test_select_circular_index() -> None:
    assert Path2D._select([10, 20, 30], 4) == 20  # type: ignore  # 4 % 3
    assert Path2D._select([10, 20, 30], -1) == 30  # type: ignore[comparison-overlap]
    assert Path2D._select([10, 20, 30], [0, 3, -1]) == [10, 10, 30]  # type: ignore[arg-type]


def test_select_circular_slice_wraps() -> None:
    assert Path2D._select([0, 1, 2, 3], 2, 0) == [2, 3, 0]
    assert Path2D._select([0, 1, 2, 3], 1, 2) == [1, 2]
    assert Path2D._select([0, 1, 2, 3], -1, 1) == [3, 0, 1]


def test_slice_inclusive_clamped() -> None:
    assert Path2D._slice([0, 1, 2, 3, 4], 1, 3) == [1, 2, 3]
    assert Path2D._slice([0, 1, 2, 3, 4], 0, -1) == [0, 1, 2, 3, 4]
    assert Path2D._slice([0, 1, 2], 2, 0) == []
    assert Path2D._slice([0, 1, 2, 3, 4], 0, 4) == [0, 1, 2, 3, 4]


def test_pair() -> None:
    assert list(zip([1, 2, 3], [2, 3], strict=False)) == [(1, 2), (2, 3)]
    assert list(zip([1, 2, 3], [2, 3, 1], strict=False)) == [(1, 2), (2, 3), (3, 1)]
    assert len(list(zip([1, 2, 3], [2, 3, 1], strict=False))) == 3


def test_list_head_and_tail() -> None:
    assert Path2D._list_head([0, 1, 2, 3], 1) == [0, 1]
    assert Path2D._list_tail([0, 1, 2, 3], 2) == [2, 3]


def test_repeat() -> None:
    assert Path2D._repeat(5, 3) == [5, 5, 5]
    assert len(Path2D._repeat(5, 3)) == 3
    assert Path2D._repeat(7, 1) == [7]


def test_deduplicate_static() -> None:
    result = Path2D._deduplicate([[0, 0], [0, 0], [1, 1]])
    assert result == [[0, 0], [1, 1]]
    assert len(result) == 2


def test_polygon_area_static() -> None:
    assert Path2D.polygon_area(SQUARE) == 4800
    assert Path2D.polygon_area([[0, 0], [1, 0]]) == 0  # too few points
    assert Path2D.polygon_area(UNIT) == 100
    assert Path2D.polygon_area([]) == 0


def test_point_in_polygon_static() -> None:
    p = Path2D(SQUARE, closed=True)
    assert Path2D.point_in_polygon(Point(40, 30), p) == 1
    assert Path2D.point_in_polygon(Point(100, 100), p) == -1
    assert Path2D.point_in_polygon(Point(0, 30), p) == 0  # on the boundary
    assert Path2D.point_in_polygon(Point(0, 0), p) == 0  # corner on boundary
    assert Path2D.point_in_polygon(Point(80, 60), p) == 0  # corner on boundary


def test_path_length_accepts_3d() -> None:
    from pybosl2.path3d import Path3D

    p3d = Path3D([[0, 0, 0], [0, 0, 3], [0, 4, 3]], closed=False)
    assert math.isclose(p3d.perimeter(), 7.0)
    assert len(p3d) == 3


def test_shapely_backed_path_methods() -> None:
    # contains
    p = Path2D(SQUARE, closed=True)
    assert p.contains([40, 30]) is True
    assert p.contains([100, 100]) is False

    # area
    assert math.isclose(p.area(), 4800.0)
    assert math.isclose(p.area(signed=True), 4800.0)

    # perimeter
    assert math.isclose(p.perimeter(), 280.0)

    # clockwise vs counter-clockwise signed area
    cw_p = Path2D([[0, 60], [80, 60], [80, 0], [0, 0]], closed=True)
    assert cw_p.is_clockwise() is True
    assert math.isclose(cw_p.area(signed=True), -4800.0)
    assert math.isclose(cw_p.perimeter(), 280.0)

    # is_simple
    assert p.is_simple() is True
    figure8 = Path2D([[0, 0], [2, 2], [0, 2], [2, 0]])
    assert figure8.is_simple() is False


# -- Minkowski sum -----------------------------------------------------------------------------


def test_minkowski_square_and_square() -> None:
    a = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    b = Path2D([[0, 0], [10, 0], [10, 10], [0, 10]])
    result = a.minkowski_sum(b)
    assert result.closed
    assert len(result) >= 3
    assert len(result) == 4
    assert result.area() == pytest.approx(900.0)


def test_minkowski_square_and_circle() -> None:
    a = Path2D([[0, 0], [20, 0], [20, 10], [0, 10]])
    b = Path2D.circle2d(radius=5, fn=32)
    result = a.minkowski_sum(b)
    assert result.closed
    assert len(result) >= 3
    assert len(result) == 36


def test_circle2d_default() -> None:
    c = Path2D.circle2d()
    assert c.closed
    assert len(c) == 64
    assert abs(c.perimeter() - 2 * math.pi * 10) < 1.5  # approx 2πr, radius defaults to 10
    assert list(c[0]) == pytest.approx([10.0, 0.0], abs=1e-9)


def test_circle2d_radius_and_fn() -> None:
    c = Path2D.circle2d(radius=20, fn=8)
    assert c.closed
    assert len(c) == 8
    areas = [np.linalg.norm(np.asarray(p)) for p in c]
    np.testing.assert_allclose(areas, [20.0] * 8, atol=1e-9)
    assert c.area() == pytest.approx(math.pi * 20 * 20, rel=0.1)  # octagon approximates circle


def test_ellipse2d() -> None:
    e = Path2D.ellipse2d(rx=20, ry=10, fn=32)
    assert e.closed
    assert len(e) == 32
    assert e.perimeter() > 0
    assert e.area() == pytest.approx(math.pi * 20 * 10, rel=0.05)


def test_ellipse2d_aspect() -> None:
    e = Path2D.ellipse2d(rx=30, ry=10, fn=4)
    pts = np.asarray(e._points)
    assert len(pts) == 4
    assert abs(pts[0, 0]) == pytest.approx(30.0)  # first point at (30, 0)
    assert abs(pts[1, 1]) == pytest.approx(10.0)  # second point at (0, 10)
    assert abs(pts[0, 1]) == pytest.approx(0.0, abs=1e-9)
    assert abs(pts[1, 0]) == pytest.approx(0.0, abs=1e-9)


def test_minkowski_sum_circle_dilates() -> None:
    square = Path2D([[0, 0], [20, 0], [20, 10], [0, 10]])
    result = square.minkowski_sum_circle(radius=5)
    assert result.closed
    assert len(result) >= 3
    assert len(result) == 68
    assert result.area() > square.area()
    assert result.area() == pytest.approx(578.41, rel=0.05)


def test_minkowski_sum_circle_erodes() -> None:
    square = Path2D([[0, 0], [20, 0], [20, 10], [0, 10]])
    result = square.minkowski_sum_circle(radius=-2)
    assert result.closed
    assert result.area() < square.area()
    assert result.area() == pytest.approx(96.0, rel=0.05)
    assert len(result) == 4


# -- Boolean operations on Path2D ----------------------------------------------------------------


def test_union_two_squares() -> None:
    a = Path2D([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[20, 0], [50, 0], [50, 30], [20, 30]])
    result = a.union(b)
    assert result.closed
    assert len(result) >= 4
    assert len(result) == 8
    assert result.area() > 900  # larger than either square alone
    assert result.area() == pytest.approx(1500.0)


def test_intersection_two_squares() -> None:
    a = Path2D([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[20, 0], [50, 0], [50, 30], [20, 30]])
    result = a.intersection(b)
    assert result.closed
    assert len(result) >= 4
    assert len(result) == 4
    assert result.area() == pytest.approx(300.0)  # 10×30 strip


def test_difference_square_minus_square() -> None:
    a = Path2D([[0, 0], [40, 0], [40, 30], [0, 30]])
    b = Path2D([[10, 10], [30, 10], [30, 20], [10, 20]])
    result = a.difference(b)
    assert result.closed
    # Path2D doesn't support holes; difference returns the outer outline
    assert result.area() == pytest.approx(1200.0)
    assert len(result) == 4


def test_symmetric_difference_two_squares() -> None:
    a = Path2D([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[20, 0], [50, 0], [50, 30], [20, 30]])
    result = a.symmetric_difference(b)
    assert result.closed
    assert len(result) == 4
    assert result.area() == pytest.approx(600.0)


def test_union_operator() -> None:
    a = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    b = Path2D([[10, 0], [30, 0], [30, 20], [10, 20]])
    result = a | b
    assert result.closed
    assert len(result) >= 4
    assert len(result) == 8
    assert result.area() == pytest.approx(600.0)


def test_intersection_operator() -> None:
    a = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    b = Path2D([[10, 0], [30, 0], [30, 20], [10, 20]])
    result = a & b
    assert result.closed
    assert len(result) == 4
    assert result.area() == pytest.approx(200.0)


def test_difference_operator() -> None:
    a = Path2D([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[10, 10], [20, 10], [20, 20], [10, 20]])
    result = a - b
    assert result.closed
    assert result.area() == pytest.approx(900.0)
    assert len(result) == 4


def test_xor_operator() -> None:
    a = Path2D([[0, 0], [30, 0], [30, 30], [0, 30]])
    b = Path2D([[20, 0], [50, 0], [50, 30], [20, 30]])
    result = a ^ b
    assert result.closed
    assert result.area() == pytest.approx(600.0)
    assert len(result) == 4


def test_region_ops_read_an_open_outline_as_a_ring() -> None:
    # These are region operations: an outline bounds an area whether or not it is flagged
    # closed, so they no longer refuse an open path.
    open_sq = Path2D([[0, 0], [20, 0], [20, 10], [0, 10]], closed=False)
    other = Path2D([[10, 0], [30, 0], [30, 10], [10, 10]], closed=True)
    assert open_sq.union(other).area() == pytest.approx(300.0)
    assert open_sq.difference(other).area() == pytest.approx(100.0)
    assert open_sq.minkowski_sum_circle(radius=5).area() > open_sq.area()


def test_intersection_empty_returns_empty() -> None:
    a = Path2D([[0, 0], [10, 0], [10, 10], [0, 10]])
    b = Path2D([[50, 0], [60, 0], [60, 10], [50, 10]])
    result = a.intersection(b)
    assert len(result) == 0
    assert result.closed


# -- additional Path2D coverage --------------------------------------------------------------


def test_catenary_classmethod() -> None:
    result = Path2D.catenary(width=100, droop=20, sides=16)
    assert isinstance(result, Path2D)
    assert len(result) == 16
    assert result.closed is False
    assert result[0][0] == pytest.approx(-50.0, abs=1e-6)
    assert result[-1][0] == pytest.approx(50.0, abs=1e-6)
    assert result[0][1] == pytest.approx(0.0, abs=1e-6)
    assert result[0][1] > result[8][1]  # middle droops below y=0 (negative y)


def test_to_bezier() -> None:
    p = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]], closed=True)
    bez = p.to_bezier()
    from pybosl2.beziers import Bezier

    assert isinstance(bez, Bezier)
    assert len(bez) > 0
    assert len(bez) == 10


def test_resample_path_spacing() -> None:
    p = Path2D([[0, 0], [50, 0], [50, 50]])
    result = p.resample_path(spacing=10)
    assert isinstance(result, Path2D)
    assert len(result) == 10
    assert list(result[-1]) == pytest.approx([50.0, 50.0], abs=1e-6)


def test_deduplicate_with_params() -> None:
    p = Path2D([[0, 0], [10, 0], [10, 0], [20, 0]], closed=False)
    result = p.deduplicate(closed=False, eps=1e-9)
    assert isinstance(result, Path2D)
    assert len(result) == 3
    assert list(result[0]) == [0.0, 0.0]
    assert list(result[1]) == [10.0, 0.0]
    assert list(result[2]) == [20.0, 0.0]
    assert result.closed is False


def test_path_from_list() -> None:
    p = Path2D.from_list([[0, 0], [10, 0], [10, 10]], closed=False)
    assert isinstance(p, Path2D)
    assert len(p) == 3
    assert list(p[0]) == [0.0, 0.0]
    assert list(p[-1]) == [10.0, 10.0]
    assert p.closed is False


def test_cut_single() -> None:
    p = Path2D([[0, 0], [20, 0], [20, 20]], closed=False)
    cp = p.cut_single(10)
    assert cp.point is not None
    assert cp.point[0] == pytest.approx(10.0)
    assert cp.point[1] == pytest.approx(0.0)


def test_path2d_color_propagates_to_shape() -> None:
    p = Path2D([[0, 0], [10, 0], [10, 10]]).color(Color("red"))
    assert p._color == Color("red")
    shape = p.polygon()
    assert shape is not None


def test_path2d_color_propagates_to_polygon() -> None:
    p = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]])
    assert p._color is None
    cp = p.color(Color("blue"))
    assert cp._color == Color("blue")
    assert p._color is None  # original unchanged
    assert cp.polygon() is not None


def test_path2d_color_carries_through_stroke() -> None:
    p = Path2D([[0, 0], [30, 0], [30, 20]]).color(Color([0.5, 0.2, 0.8]))
    result = p.stroke(width=2)
    assert result._color == Color([0.5, 0.2, 0.8])


def test_path2d_color_carries_through_offset() -> None:
    p = Path2D([[0, 0], [40, 0], [40, 30], [0, 30]]).color(Color("green"))
    result = p.offset(radius=-3)
    assert result._color == Color("green")


def test_path2d_color_carries_through_round_corners() -> None:
    p = Path2D([[0, 0], [40, 0], [40, 30], [0, 30]]).color(Color("cyan"))
    result = p.round_corners(radius=5)
    assert result._color == Color("cyan")

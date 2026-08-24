# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/rounding.py: round_corners (circle/smooth/chamfer x radius/cut/joint/width) and
smooth_path, on Path2D / Path3D. Numeric output is pinned to real BOSL2 in
tests/test_bosl2_reorient.py; here we check the method surface, dimensions, and error handling."""

import numpy as np
import pytest

from pybosl2.enums import RoundingMethod
from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D

SQ = [[0, 0], [40, 0], [40, 30], [0, 30]]
P3 = [[0, 0, 0], [40, 0, 0], [40, 40, 20], [0, 40, 20]]


# -- round_corners ------------------------------------------------------------------------


def test_circle_inserts_points_and_returns_path() -> None:
    out = Path2D(SQ, closed=True).round_corners(radius=5)
    assert isinstance(out, Path2D)
    assert not isinstance(out, Path3D)
    assert len(out) > len(SQ)
    assert out.closed is True


@pytest.mark.parametrize(
    ("method", "kw"),
    [
        (RoundingMethod.CIRCLE, {"radius": 5}),
        (RoundingMethod.CIRCLE, {"cut": 3}),
        (RoundingMethod.CIRCLE, {"joint": 5}),
        (RoundingMethod.SMOOTH, {"joint": 8}),
        (RoundingMethod.SMOOTH, {"cut": 2}),
        (RoundingMethod.SMOOTH, {"joint": 8, "k": 0.8}),
        (RoundingMethod.CHAMFER, {"joint": 6}),
        (RoundingMethod.CHAMFER, {"cut": 4}),
        (RoundingMethod.CHAMFER, {"width": 5}),
    ],
)
def test_every_method_measure_builds(method, kw) -> None:  # type: ignore[no-untyped-def]
    out = Path2D(SQ).round_corners(method=method, **kw)
    assert isinstance(out, Path2D)
    assert len(out) >= len(SQ)


def test_chamfer_replaces_each_corner_with_two_points() -> None:
    out = Path2D(SQ, closed=True).round_corners(method=RoundingMethod.CHAMFER, joint=6)
    assert len(out) == 8  # type: ignore[arg-type]  # each of 4 corners -> 2 chamfer points
    # An OPEN path keeps its two endpoints and only works the 2 interior corners.
    assert len(Path2D(SQ).round_corners(method=RoundingMethod.CHAMFER, joint=6)) == 6


@pytest.mark.parametrize(
    ("method", "kwargs"),
    [
        (RoundingMethod.SMOOTH, {"joint": 6}),
        (RoundingMethod.CHAMFER, {"joint": 6}),
        (RoundingMethod.CIRCLE, {"radius": 5}),
    ],
    ids=["smooth", "chamfer", "circle"],
)
def test_3d_paths_return_path3d(method: RoundingMethod, kwargs: dict[str, float]) -> None:
    """Every method rounds the interior corners and leaves the two endpoints where they were."""
    original = Path3D(P3)
    rounded = original.round_corners(method=method, **kwargs)
    assert isinstance(rounded, Path3D)
    assert len(rounded) > len(original)  # the corners became several points each
    assert [float(v) for v in rounded[0]] == pytest.approx([float(v) for v in original[0]])
    assert [float(v) for v in rounded[-1]] == pytest.approx([float(v) for v in original[-1]])


def test_open_path_leaves_endpoints() -> None:
    out = Path2D([[0, 0], [40, 0], [40, 30], [0, 30]], closed=False).round_corners(radius=5)
    assert out.closed is False  # type: ignore[attr-defined]
    np.testing.assert_allclose(out[0], [0, 0], atol=1e-9)  # type: ignore  # first point unchanged
    np.testing.assert_allclose(out[-1], [0, 30], atol=1e-9)  # type: ignore  # last point unchanged


def test_radius_requires_circle_method() -> None:
    with pytest.raises(ValueError, match="radius="):
        Path2D(SQ).round_corners(method=RoundingMethod.SMOOTH, radius=5)


def test_width_requires_chamfer_method() -> None:
    with pytest.raises(ValueError, match="width="):
        Path2D(SQ).round_corners(method=RoundingMethod.CIRCLE, width=5)


def test_k_requires_smooth_method() -> None:
    with pytest.raises(ValueError, match="k is only allowed"):
        Path2D(SQ).round_corners(method=RoundingMethod.CIRCLE, cut=3, curvature=0.5)
    with pytest.raises(ValueError, match="k is only allowed"):
        Path2D(SQ).round_corners(method=RoundingMethod.CIRCLE, cut=3, k=0.5)


def test_exactly_one_size_measure() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        Path2D(SQ).round_corners(radius=5, cut=3)
    with pytest.raises(ValueError, match="exactly one"):
        Path2D(SQ).round_corners()


def test_too_short_path_raises() -> None:
    with pytest.raises(ValueError, match="3 or more"):
        Path2D([[0, 0], [10, 0]]).round_corners(radius=1)


def test_oversized_roundover_raises() -> None:
    # a radius bigger than the sides can't fit
    with pytest.raises(ValueError, match="Roundovers are too big"):
        Path2D(SQ).round_corners(method=RoundingMethod.SMOOTH, cut=10)


# -- Path2D / Path3D method form ------------------------------------------------------------


def test_path_round_corners_method_uses_own_closed() -> None:
    open_sq = Path2D(SQ, closed=False)
    out = open_sq.round_corners(radius=5)
    assert out.closed is False  # type: ignore[attr-defined]


def test_path3d_round_corners_method() -> None:
    """A bigger joint cuts further back along each leg, so it needs no more points but moves more."""
    small = Path3D(P3).round_corners(method=RoundingMethod.SMOOTH, joint=2)
    large = Path3D(P3).round_corners(method=RoundingMethod.SMOOTH, joint=6)
    assert isinstance(large, Path3D)
    corner = np.asarray(P3[1], dtype=float)
    nearest = lambda path: min(float(np.linalg.norm(np.asarray(pt, float) - corner)) for pt in path)  # noqa: E731
    assert nearest(large) > nearest(small)  # the larger joint stays further from the sharp corner


# -- smooth_path --------------------------------------------------------------------------


def test_smooth_path_returns_denser_path() -> None:
    wig = [[0, 0], [10, 30], [30, -10], [50, 20], [70, 0]]
    out = Path2D(wig, closed=False).smooth_path(relsize=0.4)
    assert isinstance(out, Path2D)
    assert len(out) > len(wig)
    # endpoints are preserved for an open smoothed path
    np.testing.assert_allclose(out[0], wig[0], atol=1e-9)
    np.testing.assert_allclose(out[-1], wig[-1], atol=1e-9)


def test_smooth_path_closed_drops_duplicate_end() -> None:
    out = Path2D(SQ, closed=True).smooth_path(relsize=0.3, closed=True)
    assert out.closed is True  # type: ignore[attr-defined]
    assert not np.allclose(out[0], out[-1])  # type: ignore  # closing duplicate removed


def test_smooth_path_3d() -> None:
    """A smoothed path is resampled into a curve through the same endpoints."""
    original = Path3D([[0, 0, 0], [10, 30, 5], [30, -10, 10], [50, 20, 0]], closed=False)
    smoothed = original.smooth_path(relsize=0.4)
    assert isinstance(smoothed, Path3D)
    assert len(smoothed) > len(original)
    assert [float(v) for v in smoothed[0]] == pytest.approx([0.0, 0.0, 0.0])
    assert [float(v) for v in smoothed[-1]] == pytest.approx([50.0, 20.0, 0.0])


def test_smooth_path_method_on_path() -> None:
    """The 2-D method does the same, and keeps the corner point off the smoothed curve."""
    path = Path2D([[0, 0], [10, 30], [30, -10]], closed=False)
    smoothed = path.smooth_path(relsize=0.4)
    assert isinstance(smoothed, Path2D)
    assert len(smoothed) > len(path)
    assert [float(v) for v in smoothed[0]] == pytest.approx([0.0, 0.0])
    assert [float(v) for v in smoothed[-1]] == pytest.approx([30.0, -10.0])
    # smooth_path interpolates: the curve runs *through* the corner (round_corners cuts it off)
    corner = np.asarray([10.0, 30.0])
    assert min(float(np.linalg.norm(np.asarray(pt, float) - corner)) for pt in smoothed) == pytest.approx(0.0)


# -- path_join ----------------------------------------------------------------------------


def test_path_join_plain_concatenation() -> None:
    p1 = [[0, 0], [10, 0]]
    p2 = [[10, 0], [20, 10]]
    res = Path2D(p1, closed=False).path_join([Path2D(p2, closed=False)], relocate=True)  # type: ignore[list-item]
    assert isinstance(res, Path2D)
    # The common point is merged, so 10,0 is not repeated twice.
    assert len(res) == 3
    np.testing.assert_allclose(res, [[0, 0], [10, 0], [20, 10]])


def test_path_join_relocate_false() -> None:
    p1 = [[0, 0], [10, 0]]
    p2 = [[10, 0], [20, 10]]
    res = Path2D(p1, closed=False).path_join([Path2D(p2, closed=False)], relocate=False)  # type: ignore[list-item]
    # Relocate=False preserves duplicate endpoints
    assert len(res) == 4  # type: ignore[arg-type]
    np.testing.assert_allclose(res, [[0, 0], [10, 0], [10, 0], [20, 10]])  # type: ignore[call-overload]


def test_path_join_with_rounding() -> None:
    # Corner at [10,0] is rounded
    p1 = [[0, 0], [10, 0]]
    p2 = [[10, 0], [10, 10]]
    res = Path2D(p1, closed=False).path_join([Path2D(p2, closed=False)], radius=2)  # type: ignore[list-item]
    assert len(res) > 3  # type: ignore[arg-type]
    # Endpoints must remain same as originals
    np.testing.assert_allclose(res[0], [0, 0], atol=1e-9)  # type: ignore[index]
    np.testing.assert_allclose(res[-1], [10, 10], atol=1e-9)  # type: ignore[index]


def test_path_join_3d() -> None:
    """Joining two paths runs them end to end, rounding the join by the given radius."""
    first = Path3D([[0, 0, 0], [10, 0, 0]], closed=False)
    second = Path3D([[10, 0, 0], [20, 10, 10]], closed=False)
    joined = first.path_join([second], radius=1)  # type: ignore[list-item]
    assert isinstance(joined, Path3D)
    assert [float(v) for v in joined[0]] == pytest.approx([0.0, 0.0, 0.0])
    assert [float(v) for v in joined[-1]] == pytest.approx([20.0, 10.0, 10.0])
    assert len(joined) > len(first) + 1  # the join itself became an arc


# -- offset_stroke ------------------------------------------------------------------------


def test_offset_stroke_returns_region_or_solid() -> None:
    p = [[0, 0], [10, 0], [10, 10]]
    res = Path2D(p).offset_stroke(width=2)
    assert res is not None
    # Depending on whether shapely is installed, it is either a Region or a Solid (CSG).
    from pybosl2.regions import Region

    assert isinstance(res, Region)
    assert len(res.outline) > 0


# -- Path2D instances method tests -----------------------------------------------------------


def test_path_methods_on_path_object() -> None:
    p = Path2D([[0, 0], [10, 0], [10, 10]], closed=False)

    # 1. offset_stroke
    res_stroke = p.offset_stroke(width=2)
    assert res_stroke is not None

    # 2. offset_sweep
    res_sweep = p.offset_sweep(height=10)
    assert res_sweep is not None
    assert res_sweep.vnf.volume() > 0  # type: ignore[attr-defined]

    # 3. convex_offset_extrude
    res_extrude = p.convex_offset_extrude(height=10)
    assert res_extrude is not None

    # 4. rounded_prism
    res_rp = p.rounded_prism(height=10)
    assert res_rp is not None

    # 5. join_prism
    res_jp = p.join_prism(height=10, fillet=2)
    assert res_jp is not None

    # 6. prism_connector
    res_pc = p.prism_connector(length=10, fillet=2)
    assert res_pc is not None

    # 7. attach_prism
    res_ap = p.attach_prism(length=10, fillet=2, rounding=2)
    assert res_ap is not None

    # 8. bent_cutout_mask
    res_bcm = p.bent_cutout_mask(radius=30, thickness=4)
    assert res_bcm is not None

    # 9. path_join method
    other = Path2D([[10, 10], [20, 20]], closed=False)
    res_pj = p.path_join([other], relocate=True)  # type: ignore[list-item]
    assert len(res_pj) == 4  # type: ignore[arg-type]


# ── uncovered rounding branches ─────────────────────────────────────────


def test_round_corners_per_corner_size() -> None:
    """A list radius rounds each corner by its own amount."""
    p = Path2D([[0, 0], [30, 0], [30, 30], [0, 30]], closed=True)
    result = p.round_corners(radius=[3, 5, 7, 10], closed=True)
    assert isinstance(result, Path2D)
    # each corner is cut back by its own radius, so this is not the same as one radius for all
    assert result.area() != p.round_corners(radius=5, closed=True).area()
    assert result.area() < p.area()


def test_smooth_path_with_tangents() -> None:
    """Given tangents, the curve leaves the first point along the one it was handed."""
    path = Path2D([[0, 0], [10, 10], [20, 0]], closed=False)
    smoothed = path.smooth_path(tangents=[[1, 0], [0, 1], [1, 0]])  # type: ignore[call-arg]
    assert isinstance(smoothed, Path2D)
    assert [float(v) for v in smoothed[0]] == pytest.approx([0.0, 0.0])
    start_direction = np.asarray(smoothed[1], float) - np.asarray(smoothed[0], float)
    assert abs(float(start_direction[0])) > abs(float(start_direction[1]))  # heading +X, as asked


def _path_length(path: Path2D) -> float:
    points = np.asarray(path.to_list, dtype=float)
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


def test_smooth_path_with_size() -> None:
    """`size=` is an absolute bulge: a bigger one bows the curve further out, so it runs longer."""
    path = Path2D([[0, 0], [10, 10], [20, 0]], closed=False)
    gentle = path.smooth_path(size=1)  # type: ignore[call-arg]
    strong = path.smooth_path(size=5)  # type: ignore[call-arg]
    assert isinstance(strong, Path2D)
    assert _path_length(strong) > _path_length(gentle) > _path_length(path)


def test_path_join_closed() -> None:
    """`closed=True` makes the joined run a loop, and relocate moves the second onto the first."""
    a = Path2D([[0, 0], [10, 10]], closed=False)
    b = Path2D([[20, 0], [30, 10]], closed=False)
    joined = a.path_join([b], closed=True, relocate=True)  # type: ignore[list-item]
    assert isinstance(joined, Path2D)
    assert joined.closed
    assert [float(v) for v in joined[0]] == pytest.approx([0.0, 0.0])

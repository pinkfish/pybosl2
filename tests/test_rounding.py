# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2/rounding.py: round_corners (circle/smooth/chamfer x radius/cut/joint/width) and
smooth_path, on Path / Path3D. Numeric output is pinned to real BOSL2 in
tests/test_bosl2_reorient.py; here we check the method surface, dimensions, and error handling."""

import numpy as np
import pytest

from bosl2.paths import Path, Path3D
from bosl2.rounding import offset_stroke, path_join, round_corners, smooth_path

SQ = [[0, 0], [40, 0], [40, 30], [0, 30]]
P3 = [[0, 0, 0], [40, 0, 0], [40, 40, 20], [0, 40, 20]]


# -- round_corners ------------------------------------------------------------------------


def test_circle_inserts_points_and_returns_path():
    out = round_corners(SQ, radius=5)
    assert isinstance(out, Path) and not isinstance(out, Path3D)
    assert len(out) > len(SQ)
    assert out.closed is True


@pytest.mark.parametrize(
    "method,kw",
    [
        ("circle", {"radius": 5}),
        ("circle", {"cut": 3}),
        ("circle", {"joint": 5}),
        ("smooth", {"joint": 8}),
        ("smooth", {"cut": 2}),
        ("smooth", {"joint": 8, "k": 0.8}),
        ("chamfer", {"joint": 6}),
        ("chamfer", {"cut": 4}),
        ("chamfer", {"width": 5}),
    ],
)
def test_every_method_measure_builds(method, kw):
    out = round_corners(SQ, method=method, **kw)
    assert isinstance(out, Path) and len(out) >= len(SQ)


def test_chamfer_replaces_each_corner_with_two_points():
    out = round_corners(SQ, method="chamfer", joint=6)
    assert len(out) == 8  # each of 4 corners -> 2 chamfer points


def test_3d_paths_return_path3d():
    assert isinstance(round_corners(P3, method="smooth", joint=6), Path3D)
    assert isinstance(round_corners(P3, method="chamfer", joint=6), Path3D)
    assert isinstance(round_corners(P3, method="circle", radius=5), Path3D)


def test_open_path_leaves_endpoints():
    out = round_corners([[0, 0], [40, 0], [40, 30], [0, 30]], radius=5, closed=False)
    assert out.closed is False
    np.testing.assert_allclose(out[0], [0, 0], atol=1e-9)  # first point unchanged
    np.testing.assert_allclose(out[-1], [0, 30], atol=1e-9)  # last point unchanged


def test_radius_requires_circle_method():
    with pytest.raises(AssertionError):
        round_corners(SQ, method="smooth", radius=5)


def test_width_requires_chamfer_method():
    with pytest.raises(AssertionError):
        round_corners(SQ, method="circle", width=5)


def test_k_requires_smooth_method():
    with pytest.raises(AssertionError):
        round_corners(SQ, method="circle", cut=3, k=0.5)


def test_exactly_one_size_measure():
    with pytest.raises(AssertionError):
        round_corners(SQ, radius=5, cut=3)
    with pytest.raises(AssertionError):
        round_corners(SQ)


def test_too_short_path_raises():
    with pytest.raises(AssertionError):
        round_corners([[0, 0], [10, 0]], radius=1)


def test_oversized_roundover_raises():
    # a radius bigger than the sides can't fit
    with pytest.raises(AssertionError):
        round_corners(SQ, method="smooth", cut=10)


# -- Path / Path3D method form ------------------------------------------------------------


def test_path_round_corners_method_uses_own_closed():
    open_sq = Path(SQ, closed=False)
    out = open_sq.round_corners(radius=5)
    assert out.closed is False


def test_path3d_round_corners_method():
    assert isinstance(Path3D(P3).round_corners(method="smooth", joint=6), Path3D)


# -- smooth_path --------------------------------------------------------------------------


def test_smooth_path_returns_denser_path():
    wig = [[0, 0], [10, 30], [30, -10], [50, 20], [70, 0]]
    out = smooth_path(wig, relsize=0.4)
    assert isinstance(out, Path) and len(out) > len(wig)
    # endpoints are preserved for an open smoothed path
    np.testing.assert_allclose(out[0], wig[0], atol=1e-9)
    np.testing.assert_allclose(out[-1], wig[-1], atol=1e-9)


def test_smooth_path_closed_drops_duplicate_end():
    out = smooth_path(SQ, relsize=0.3, closed=True)
    assert out.closed is True
    assert not np.allclose(out[0], out[-1])  # closing duplicate removed


def test_smooth_path_3d():
    out = smooth_path([[0, 0, 0], [10, 30, 5], [30, -10, 10], [50, 20, 0]], relsize=0.4)
    assert isinstance(out, Path3D)


def test_smooth_path_method_on_path():
    p = Path([[0, 0], [10, 30], [30, -10]], closed=False)
    assert isinstance(p.smooth_path(relsize=0.4), Path)


# -- path_join ----------------------------------------------------------------------------


def test_path_join_plain_concatenation():
    p1 = [[0, 0], [10, 0]]
    p2 = [[10, 0], [20, 10]]
    res = path_join([p1, p2], relocate=True)
    assert isinstance(res, Path)
    # The common point is merged, so 10,0 is not repeated twice.
    assert len(res) == 3
    np.testing.assert_allclose(res, [[0, 0], [10, 0], [20, 10]])


def test_path_join_relocate_false():
    p1 = [[0, 0], [10, 0]]
    p2 = [[10, 0], [20, 10]]
    res = path_join([p1, p2], relocate=False)
    # Relocate=False preserves duplicate endpoints
    assert len(res) == 4
    np.testing.assert_allclose(res, [[0, 0], [10, 0], [10, 0], [20, 10]])


def test_path_join_with_rounding():
    # Corner at [10,0] is rounded
    p1 = [[0, 0], [10, 0]]
    p2 = [[10, 0], [10, 10]]
    res = path_join([p1, p2], radius=2)
    assert len(res) > 3
    # Endpoints must remain same as originals
    np.testing.assert_allclose(res[0], [0, 0], atol=1e-9)
    np.testing.assert_allclose(res[-1], [10, 10], atol=1e-9)


def test_path_join_3d():
    p1 = [[0, 0, 0], [10, 0, 0]]
    p2 = [[10, 0, 0], [20, 10, 10]]
    res = path_join([p1, p2], radius=1)
    assert isinstance(res, Path3D)


# -- offset_stroke ------------------------------------------------------------------------


def test_offset_stroke_returns_region_or_solid():
    p = [[0, 0], [10, 0], [10, 10]]
    res = offset_stroke(p, width=2)
    assert res is not None
    # Depending on whether shapely is installed, it is either a Region or a Solid (CSG).
    from bosl2.regions import _SHAPELY, Region

    if _SHAPELY:
        assert isinstance(res, Region)
        # Should have outline and bounds
        assert len(res.outline) > 0
    else:
        # returns native geometry Solid
        assert hasattr(res, "color")

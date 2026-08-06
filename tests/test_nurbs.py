# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/nurbs.py: the NurbsCurve and NurbsPatch classes -- evaluation, meshing, and
degree elevation. Here we check the object surface (return types, endpoints, encapsulation, and
error handling); NurbsPatch.vnf uses the mocked VNF, so its geometry is checked for real in
test_stl_render.py."""

import numpy as np
import pytest

from pybosl2.caps import CapType
from pybosl2.nurbs import NurbsCurve, NurbsPatch, NurbsType
from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D
from pybosl2.vnf import VNF

CTRL3: list[list[float]] = [[0, 0, 0], [10, 20, 5], [30, -10, 10], [50, 20, 0], [60, 0, 15]]
CTRL2: list[list[float]] = [[0, 0], [10, 20], [30, -10], [50, 20]]
PATCH: list[list[list[float]]] = [
    [[-50, 50, 0], [-16, 50, 20], [16, 50, 20], [50, 50, 0]],
    [[-50, 16, 20], [-16, 16, 40], [16, 16, 40], [50, 16, 20]],
    [[-50, -16, 20], [-16, -16, 40], [16, -16, 40], [50, -16, 20]],
    [[-50, -50, 0], [-16, -50, 20], [16, -50, 20], [50, -50, 0]],
]


# -- NurbsCurve construction ----------------------------------------------------------------


def test_curve_wraps_its_control_points() -> None:
    curve = NurbsCurve(CTRL3, 3)
    assert len(curve) == 5
    assert curve.degree == 3
    assert curve.nurbs_type is NurbsType.CLAMPED
    np.testing.assert_allclose(curve[0], CTRL3[0])
    np.testing.assert_allclose(np.array(list(curve)), np.array(CTRL3))
    assert curve.to_list == CTRL3
    assert curve.array.shape == (5, 3)


def test_curve_state_is_encapsulated() -> None:
    """The definition is exposed read-only -- there are no public data attributes to reassign."""
    curve = NurbsCurve(CTRL2, 3, knots=[0, 0.5, 1], weights=[1, 2, 2, 1])
    assert not [name for name in vars(curve) if not name.startswith("_")]
    with pytest.raises(AttributeError):
        curve.degree = 4  # type: ignore[misc]
    # the property returns a copy, so mutating it cannot corrupt the curve
    knots = curve.knots
    assert knots is not None
    knots.append(99.0)
    assert curve.knots == [0, 0.5, 1]
    with pytest.raises(ValueError, match="read-only"):  # the control points are frozen too
        curve.array[0][0] = 99.0


def test_curve_repr_round_trips_the_definition() -> None:
    assert repr(NurbsCurve(CTRL2, 3)).startswith("NurbsCurve([[0.0, 0.0]")


def test_bad_degree_raises() -> None:
    with pytest.raises(AssertionError):
        NurbsCurve(CTRL2, 0)


def test_too_few_control_points_raises() -> None:
    with pytest.raises(AssertionError):
        NurbsCurve([[0, 0], [10, 0]], 3)  # degree 3 needs >= 4 points


def test_weights_must_match_control_points() -> None:
    with pytest.raises(AssertionError):
        NurbsCurve(CTRL2, 3, weights=[1, 2])


# -- NurbsCurve evaluation ------------------------------------------------------------------


def test_curve_returns_path3d_for_3d_control() -> None:
    path = NurbsCurve(CTRL3, 3).curve(splinesteps=8)
    assert isinstance(path, Path3D)
    assert path.closed is False


def test_curve_returns_path2d_for_2d_control() -> None:
    path = NurbsCurve(CTRL2, 3).curve(splinesteps=6)
    assert isinstance(path, Path2D)
    assert not isinstance(path, Path3D)


def test_clamped_curve_interpolates_endpoints() -> None:
    path = NurbsCurve(CTRL3, 3).curve(splinesteps=6)
    np.testing.assert_allclose(path[0], CTRL3[0], atol=1e-9)
    np.testing.assert_allclose(path[-1], CTRL3[-1], atol=1e-9)


def test_point_matches_points() -> None:
    curve = NurbsCurve(CTRL3, 3)
    point = curve.point(0.5)
    assert isinstance(point, np.ndarray)
    assert point.shape == (3,)
    np.testing.assert_allclose(point, curve.points([0.5])[0], atol=1e-12)


def test_points_returns_one_row_per_parameter() -> None:
    pts = NurbsCurve(CTRL3, 3).points([0, 0.25, 0.5, 1])
    assert pts.shape == (4, 3)


def test_u_out_of_range_raises() -> None:
    with pytest.raises(AssertionError):
        NurbsCurve(CTRL3, 3).points([0, 1.5])


def test_closed_curve_is_flagged_closed() -> None:
    path = NurbsCurve([[0, 0], [10, 0], [10, 10], [0, 10]], 2, NurbsType.CLOSED).curve(splinesteps=4)
    assert isinstance(path, Path2D)
    assert path.closed is True


def test_open_curve_type() -> None:
    """Open curves do not interpolate endpoints and return the expected point count."""
    path = NurbsCurve(CTRL3, 3, NurbsType.OPEN).curve(splinesteps=8)
    assert isinstance(path, Path3D)
    assert path.closed is False
    assert len(path) == 17
    assert not np.allclose(path[0], CTRL3[0])
    assert not np.allclose(path[-1], CTRL3[-1])


def test_closed_curve_explicit_mult() -> None:
    """A closed curve with an explicit knot multiplicity produces a closed path."""
    path = NurbsCurve([[0, 0], [10, 0], [10, 10], [0, 10]], 2, NurbsType.CLOSED, mult=[3]).curve(splinesteps=4)
    assert isinstance(path, Path2D)
    assert path.closed is True
    assert len(path) == 4


def test_curve_explicit_nonuniform_knots() -> None:
    """A clamped curve with an explicit non-uniform knot vector produces a valid path."""
    path = NurbsCurve(CTRL2, 3, knots=[0, 0.1, 0.3, 0.6, 0.8, 1.0]).curve(splinesteps=5)
    assert isinstance(path, Path2D)
    assert path.closed is False
    assert len(path) == 6


def test_weights_pull_curve_toward_heavy_point() -> None:
    # a high weight on the middle control point pulls the curve toward it
    heavy = NurbsCurve([[0, 0], [10, 0], [10, 10]], 2, weights=[1, 9, 1]).point(0.5)
    light = NurbsCurve([[0, 0], [10, 0], [10, 10]], 2, weights=[1, 1, 1]).point(0.5)
    assert heavy[0] > light[0]  # pulled toward the [10,0] control point


# -- degree elevation ------------------------------------------------------------------------


def test_elevate_raises_degree_and_count() -> None:
    elevated = NurbsCurve(CTRL2, 3).elevate_degree()
    assert isinstance(elevated, NurbsCurve)
    assert elevated.nurbs_type is NurbsType.CLAMPED
    assert elevated.degree == 4  # degree raised 3 -> 4
    assert len(elevated) == len(CTRL2) + 1  # one more control point per elevation


def test_elevate_times() -> None:
    assert NurbsCurve(CTRL2, 3).elevate_degree(times=2).degree == 5


def test_elevate_preserves_the_curve() -> None:
    # elevating degree must not change the geometry of the curve
    curve = NurbsCurve(CTRL2, 3)
    np.testing.assert_allclose(
        np.array(curve.curve(splinesteps=8)),
        np.array(curve.elevate_degree().curve(splinesteps=8)),
        atol=1e-6,
    )


def test_elevate_weighted_curve_keeps_weights() -> None:
    curve = NurbsCurve(CTRL2, 3, weights=[1, 2, 2, 1])
    elevated = curve.elevate_degree()
    assert elevated.degree == 4
    assert elevated.weights is not None
    assert len(elevated.weights) == len(elevated)
    np.testing.assert_allclose(np.array(elevated.curve(splinesteps=6)), np.array(curve.curve(splinesteps=6)), atol=1e-6)


def test_elevate_closed_curve_raises() -> None:
    with pytest.raises(AssertionError):
        NurbsCurve([[0, 0], [10, 0], [10, 10], [0, 10]], 2, NurbsType.CLOSED).elevate_degree()


def test_elevate_zero_times_is_a_noop() -> None:
    elevated = NurbsCurve(CTRL2, 3).elevate_degree(times=0)
    assert elevated.nurbs_type is NurbsType.CLAMPED
    assert elevated.degree == 3
    np.testing.assert_array_equal(np.array(elevated.to_list), np.array(CTRL2))
    assert elevated.knots is None
    assert elevated.weights is None


def test_elevate_open_curve() -> None:
    """Elevating an open B-spline preserves the type and raises the degree."""
    elevated = NurbsCurve(CTRL2, 3, NurbsType.OPEN).elevate_degree()
    assert elevated.nurbs_type is NurbsType.OPEN
    assert elevated.degree == 4
    assert len(elevated) == 11
    assert elevated.knots is not None
    assert len(elevated.knots) == 16


# -- NurbsPatch ------------------------------------------------------------------------------


def test_is_patch() -> None:
    assert NurbsPatch.is_patch(PATCH)
    assert not NurbsPatch.is_patch([[0, 0], [1, 1]])  # a path, not a patch
    assert not NurbsPatch.is_patch([1, 2, 3])


def test_patch_wraps_its_control_grid() -> None:
    patch = NurbsPatch(PATCH, (3, 3))
    assert len(patch) == 4
    assert patch.degree == (3, 3)
    assert patch.nurbs_type == (NurbsType.CLAMPED, NurbsType.CLAMPED)
    assert patch.array.shape == (4, 4, 3)
    assert patch.to_list == PATCH
    np.testing.assert_allclose(np.array(list(patch)), np.array(PATCH))


def test_patch_state_is_encapsulated() -> None:
    patch = NurbsPatch(PATCH, (3, 3))
    assert not [name for name in vars(patch) if not name.startswith("_")]
    with pytest.raises(AttributeError):
        patch.degree = (2, 2)  # type: ignore[misc]
    with pytest.raises(ValueError, match="read-only"):  # the control grid is frozen too
        patch.array[0][0][0] = 99.0


def test_patch_rejects_a_ragged_grid() -> None:
    with pytest.raises(AssertionError):
        NurbsPatch([[[0, 0, 0], [1, 0, 0]], [[0, 1, 0]]], (1, 1))


def test_patch_weights_must_match_the_grid() -> None:
    with pytest.raises(AssertionError):
        NurbsPatch(PATCH, (3, 3), weights=[[1.0, 1.0], [1.0, 1.0]])


def test_surface_grid_shape() -> None:
    grid = NurbsPatch(PATCH, (3, 3)).surface(splinesteps=(3, 3))
    assert grid.ndim == 3
    assert grid.shape[0] > 3
    assert grid.shape[1] > 3
    assert grid.shape[2] == 3


def test_points_uv_grid() -> None:
    grid = NurbsPatch(PATCH, (3, 3)).points([0, 0.5, 1], [0, 0.5, 1])
    assert grid.shape == (3, 3, 3)
    # the [0,0] corner interpolates the corner control point (clamped both ways)
    np.testing.assert_allclose(grid[0][0], PATCH[0][0], atol=1e-9)


def test_patch_mixed_degree() -> None:
    grid = NurbsPatch(PATCH, (3, 2)).surface(splinesteps=(2, 3))
    assert grid.shape[0] > 0
    assert grid.shape[1] > 0


def test_patch_point_matches_points() -> None:
    patch = NurbsPatch(PATCH, (3, 3))
    np.testing.assert_allclose(patch.point(0.25, 0.75), patch.points([0.25], [0.75])[0][0], atol=1e-9)


def test_patch_weighted_rational() -> None:
    """A weighted (rational) patch point differs from the unweighted evaluation."""
    w = [[1.0] * 4 for _ in range(4)]
    w[1][1] = 5.0
    weighted = NurbsPatch(PATCH, (3, 3), weights=w).point(0.5, 0.5)
    plain = NurbsPatch(PATCH, (3, 3)).point(0.5, 0.5)
    assert weighted.shape == (3,)
    assert not np.allclose(weighted, plain)


def test_patch_weighted_grid() -> None:
    """A weighted patch grid keeps its shape and differs from the unweighted grid."""
    w = [[1.0] * 4 for _ in range(4)]
    w[2][2] = 4.0
    weighted = NurbsPatch(PATCH, (3, 3), weights=w).surface(splinesteps=(2, 2))
    plain = NurbsPatch(PATCH, (3, 3)).surface(splinesteps=(2, 2))
    assert weighted.shape == plain.shape
    assert not np.allclose(weighted, plain)


def test_vnf_returns_vnf() -> None:
    assert isinstance(NurbsPatch(PATCH, (3, 3)).vnf(splinesteps=(4, 4)), VNF)


def test_vnf_uses_default_degree_and_splinesteps() -> None:
    assert isinstance(NurbsPatch(PATCH).vnf(), VNF)


def test_vnf_caps_require_closed_clamped() -> None:
    with pytest.raises(AssertionError):
        # both directions clamped -> no caps allowed
        NurbsPatch(PATCH, (3, 3)).vnf(caps=CapType.BUTT)


def test_vnf_with_caps() -> None:
    """A (CLAMPED, CLOSED) patch can be capped with butt caps."""
    vnf = NurbsPatch(PATCH, (3, 3), nurbs_type=(NurbsType.CLAMPED, NurbsType.CLOSED)).vnf(
        splinesteps=(4, 4), caps=CapType.BUTT
    )
    assert isinstance(vnf, VNF)
    assert len(vnf.vertices) == 80
    assert len(vnf.faces) == 130


def test_vnf_closed_caps() -> None:
    """A (CLOSED, CLAMPED) patch can be capped with butt caps (flipped internally)."""
    vnf = NurbsPatch(PATCH, (3, 3), nurbs_type=(NurbsType.CLOSED, NurbsType.CLAMPED)).vnf(
        splinesteps=(4, 4), caps=CapType.BUTT
    )
    assert isinstance(vnf, VNF)
    assert len(vnf.vertices) == 80
    assert len(vnf.faces) == 130

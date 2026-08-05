# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/nurbs.py: NURBS curve/patch evaluation, meshing, and degree elevation. The
numeric results are pinned to real BOSL2 in tests/test_bosl2_reorient.py; here we check the object
surface (return types, endpoints, the parameter-list form, and error handling). nurbs_vnf uses the
mocked VNF, so its geometry is checked for real in test_stl_render.py."""

import numpy as np
import pytest

from pybosl2.caps import CapType
from pybosl2.nurbs import (
    NurbsType,
    is_nurbs_patch,
    nurbs_curve,
    nurbs_elevate_degree,
    nurbs_patch_point,
    nurbs_patch_points,
    nurbs_vnf,
)
from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D
from pybosl2.vnf import VNF

CTRL3 = [[0, 0, 0], [10, 20, 5], [30, -10, 10], [50, 20, 0], [60, 0, 15]]
CTRL2 = [[0, 0], [10, 20], [30, -10], [50, 20]]
PATCH = [
    [[-50, 50, 0], [-16, 50, 20], [16, 50, 20], [50, 50, 0]],
    [[-50, 16, 20], [-16, 16, 40], [16, 16, 40], [50, 16, 20]],
    [[-50, -16, 20], [-16, -16, 40], [16, -16, 40], [50, -16, 20]],
    [[-50, -50, 0], [-16, -50, 20], [16, -50, 20], [50, -50, 0]],
]


# -- nurbs_curve --------------------------------------------------------------------------


def test_curve_returns_path3d_for_3d_control() -> None:
    c = nurbs_curve(CTRL3, 3, splinesteps=8)
    assert isinstance(c, Path3D)
    assert c.closed is False


def test_curve_returns_path_for_2d_control() -> None:
    c = nurbs_curve(CTRL2, 3, splinesteps=6)
    assert isinstance(c, Path2D)
    assert not isinstance(c, Path3D)


def test_clamped_curve_interpolates_endpoints() -> None:
    c = nurbs_curve(CTRL3, 3, splinesteps=6)
    np.testing.assert_allclose(c[0], CTRL3[0], atol=1e-9)
    np.testing.assert_allclose(c[-1], CTRL3[-1], atol=1e-9)


def test_scalar_u_returns_single_point() -> None:
    pt = nurbs_curve(CTRL3, 3, u=0.5)
    assert not isinstance(pt, (Path2D, Path3D))
    assert len(pt) == 3
    assert all(isinstance(x, float) for x in pt)


def test_closed_curve_is_flagged_closed() -> None:
    c = nurbs_curve([[0, 0], [10, 0], [10, 10], [0, 10]], 2, splinesteps=4, type=NurbsType.CLOSED)
    assert isinstance(c, Path2D)
    assert c.closed is True


def test_u_and_splinesteps_are_exclusive() -> None:
    with pytest.raises(AssertionError):
        nurbs_curve(CTRL3, 3, splinesteps=8, u=[0, 0.5, 1])


def test_u_out_of_range_raises() -> None:
    with pytest.raises(AssertionError):
        nurbs_curve(CTRL3, 3, u=[0, 1.5])


def test_too_few_control_points_raises() -> None:
    with pytest.raises(AssertionError):
        nurbs_curve([[0, 0], [10, 0]], 3, splinesteps=4)  # degree 3 needs >= 4 points


def test_weights_pull_curve_toward_heavy_point() -> None:
    # a high weight on the middle control point pulls the curve toward it
    heavy = nurbs_curve([[0, 0], [10, 0], [10, 10]], 2, u=[0.5], weights=[1, 9, 1])[0]
    light = nurbs_curve([[0, 0], [10, 0], [10, 10]], 2, u=[0.5], weights=[1, 1, 1])[0]
    assert heavy[0] > light[0]  # type: ignore  # pulled toward the [10,0] control point


def test_parameter_list_form() -> None:
    plist = [NurbsType.CLAMPED, 3, CTRL3, None, None, None]
    a = nurbs_curve(plist, splinesteps=5)  # type: ignore[arg-type]
    b = nurbs_curve(CTRL3, 3, splinesteps=5)
    np.testing.assert_allclose(np.array(a), np.array(b), atol=1e-9)


# -- surfaces -----------------------------------------------------------------------------


def test_is_nurbs_patch() -> None:
    assert is_nurbs_patch(PATCH)
    assert not is_nurbs_patch([[0, 0], [1, 1]])  # a path, not a patch
    assert not is_nurbs_patch([1, 2, 3])


def test_patch_points_grid_shape() -> None:
    grid = nurbs_patch_points(PATCH, 3, splinesteps=3)
    assert len(grid) > 3
    assert len(grid[0]) > 3
    assert all(len(pt) == 3 for row in grid for pt in row)


def test_patch_points_uv_form() -> None:
    grid = nurbs_patch_points(PATCH, 3, u=[0, 0.5, 1], v=[0, 0.5, 1])
    assert len(grid) == 3
    assert len(grid[0]) == 3
    # the [0,0] corner interpolates the corner control point (clamped both ways)
    np.testing.assert_allclose(grid[0][0], PATCH[0][0], atol=1e-9)


def test_patch_mixed_degree() -> None:
    grid = nurbs_patch_points(PATCH, [3, 2], splinesteps=[2, 3])  # type: ignore[arg-type]
    assert len(grid) > 0
    assert len(grid[0]) > 0


def test_nurbs_vnf_returns_vnf() -> None:
    assert isinstance(nurbs_vnf(PATCH, 3, splinesteps=4), VNF)


def test_nurbs_vnf_parameter_list() -> None:
    plist = [NurbsType.CLAMPED, 3, PATCH, None, None, None]
    assert isinstance(nurbs_vnf(plist, splinesteps=4), VNF)


def test_nurbs_vnf_caps_require_closed_clamped() -> None:
    with pytest.raises(AssertionError):
        nurbs_vnf(PATCH, 3, type=NurbsType.CLAMPED, caps=CapType.BUTT)  # both clamped -> no caps allowed


# -- degree elevation ---------------------------------------------------------------------


def test_elevate_raises_degree_and_count() -> None:
    el = nurbs_elevate_degree(CTRL2, 3)
    assert el[0] == NurbsType.CLAMPED
    assert el[1] == 4  # degree raised 3 -> 4
    assert len(el[2]) == len(CTRL2) + 1  # one more control point per elevation


def test_elevate_times() -> None:
    el = nurbs_elevate_degree(CTRL2, 3, times=2)
    assert el[1] == 5


def test_elevate_preserves_the_curve() -> None:
    # elevating degree must not change the geometry of the curve
    before = np.array(nurbs_curve(CTRL2, 3, splinesteps=8))
    el = nurbs_elevate_degree(CTRL2, 3)
    after = np.array(nurbs_curve(el[2], el[1], splinesteps=8))
    np.testing.assert_allclose(before, after, atol=1e-6)


def test_elevate_open_type_only() -> None:
    with pytest.raises(AssertionError):
        nurbs_elevate_degree(CTRL2, 3, type=NurbsType.CLOSED)


# -- additional coverage tests --------------------------------------------------------------


def test_open_curve_type() -> None:
    """Open curves do not interpolate endpoints and return the expected point count."""
    c = nurbs_curve(CTRL3, 3, splinesteps=8, type=NurbsType.OPEN)
    assert isinstance(c, Path3D)
    assert c.closed is False
    assert len(c) == 17
    assert not np.allclose(c[0], CTRL3[0])
    assert not np.allclose(c[-1], CTRL3[-1])


def test_closed_curve_explicit_mult() -> None:
    """Closed curve with explicit scalar knot multiplicity produces a closed path."""
    c = nurbs_curve([[0, 0], [10, 0], [10, 10], [0, 10]], 2, splinesteps=4, type=NurbsType.CLOSED, mult=3)
    assert isinstance(c, Path2D)
    assert c.closed is True
    assert len(c) == 4


def test_curve_explicit_nonuniform_knots() -> None:
    """A clamped curve with an explicit non-uniform knot vector produces a valid path."""
    knots = [0, 0.1, 0.3, 0.6, 0.8, 1.0]
    c = nurbs_curve(CTRL2, 3, splinesteps=5, knots=knots)
    assert isinstance(c, Path2D)
    assert c.closed is False
    assert len(c) == 6


def test_patch_points_weighted_rational() -> None:
    """A weighted (rational) patch point differs from the unweighted evaluation."""
    w = [[1.0] * 4 for _ in range(4)]
    w[1][1] = 5.0
    pt_w = nurbs_patch_point(PATCH, u=0.5, v=0.5, degree=3, weights=w)
    pt = nurbs_patch_point(PATCH, u=0.5, v=0.5, degree=3)
    assert len(pt_w) == 3
    assert all(isinstance(x, float) for x in pt_w)
    assert not np.allclose(pt_w, pt)


def test_nurbs_vnf_with_caps() -> None:
    """A ["clamped","closed"] patch can be capped with butt caps."""
    from pybosl2.caps import CapType

    vnf = nurbs_vnf(PATCH, 3, splinesteps=4, type=[NurbsType.CLAMPED, NurbsType.CLOSED], caps=CapType.BUTT)
    assert isinstance(vnf, VNF)
    assert len(vnf.vertices) == 80
    assert len(vnf.faces) == 130


def test_nurbs_vnf_closed_caps() -> None:
    """A ["closed","clamped"] patch can be capped with butt caps (flipped internally)."""
    from pybosl2.caps import CapType

    vnf = nurbs_vnf(PATCH, 3, splinesteps=4, type=[NurbsType.CLOSED, NurbsType.CLAMPED], caps=CapType.BUTT)
    assert isinstance(vnf, VNF)
    assert len(vnf.vertices) == 80
    assert len(vnf.faces) == 130


def test_elevate_degree_noop() -> None:
    """Elevating zero times returns the input unchanged."""
    el = nurbs_elevate_degree(CTRL2, 3, times=0)
    assert el[0] == NurbsType.CLAMPED
    assert el[1] == 3
    assert len(el[2]) == len(CTRL2)
    np.testing.assert_array_equal(np.array(el[2]), np.array(CTRL2))
    assert el[3] is None
    assert el[4] is None
    assert el[5] is None


def test_elevate_degree_open_type() -> None:
    """Elevating the degree of an open B-spline preserves the type and raises the degree."""
    el = nurbs_elevate_degree(CTRL2, 3, type=NurbsType.OPEN)
    assert el[0] == NurbsType.OPEN
    assert el[1] == 4
    assert len(el[2]) == 11
    assert len(el[3]) == 16

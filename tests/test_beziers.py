# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/beziers.py: the Bezier curve/path API and BezierPatch surfaces."""

import math

import numpy as np
import pytest

from pybosl2.beziers import Bezier, BezierPatch
from pybosl2.vnf import VNF

CUBIC = [[0, 0], [5, 35], [60, -25], [80, 0]]
PATCH = [
    [[-50, -50, 0], [-16, -50, 20], [16, -50, -20], [50, -50, 0]],
    [[-50, -16, 20], [-16, -16, 20], [16, -16, -20], [50, -16, 20]],
    [[-50, 16, 20], [-16, 16, -20], [16, 16, 20], [50, 16, 20]],
    [[-50, 50, 0], [-16, 50, -20], [16, 50, 20], [50, 50, 0]],
]
CIRCLE = [[math.cos(t), math.sin(t)] for t in np.linspace(0, 2 * math.pi, 12, endpoint=False)]


def _valid(vnf: object) -> bool:
    return not vnf.faces or max(i for f in vnf.faces for i in f) < len(vnf.vertices)  # type: ignore[attr-defined]


# -- curve evaluation ---------------------------------------------------------------------


def test_points_hits_endpoints_exactly() -> None:
    b = Bezier(CUBIC)
    np.testing.assert_allclose(b.points(0), [0, 0], atol=1e-12)
    np.testing.assert_allclose(b.points(1), [80, 0], atol=1e-12)


def test_points_list_returns_grid() -> None:
    got = Bezier(CUBIC).points([0.0, 0.5, 1.0])
    assert np.asarray(got).shape == (3, 2)


def test_curve_point_count() -> None:
    assert len(Bezier(CUBIC).curve(splinesteps=8)) == 9
    assert len(Bezier(CUBIC).curve(splinesteps=8, endpoint=False)) == 9


def test_derivative_of_cubic_at_zero() -> None:
    # first derivative of a cubic at u=0 is 3*(P1-P0)
    diameter = Bezier(CUBIC).derivative(0, 1)
    np.testing.assert_allclose(diameter, 3 * (np.array([5, 35]) - np.array([0, 0])), atol=1e-9)


def test_tangent_is_unit() -> None:
    t = Bezier(CUBIC).tangent(0.3)
    assert math.isclose(float(np.linalg.norm(t)), 1.0)


def test_curvature_scalar_and_list() -> None:
    assert np.isscalar(Bezier(CUBIC).curvature(0.5)) or np.ndim(Bezier(CUBIC).curvature(0.5)) == 0
    assert np.asarray(Bezier(CUBIC).curvature([0.2, 0.8])).shape == (2,)


def test_closest_point() -> None:
    u = Bezier(CUBIC).closest_point([40, 15])  # type: ignore[arg-type]
    assert 0.0 <= u <= 1.0
    # the returned u really is near the closest sample
    pt = Bezier(CUBIC).points(u)
    diameter = float(np.linalg.norm(pt - np.array([40, 15])))
    coarse = min(float(np.linalg.norm(Bezier(CUBIC).points(x) - np.array([40, 15]))) for x in np.linspace(0, 1, 50))
    assert diameter <= coarse + 1e-6


def test_length_positive_and_ge_chord() -> None:
    length_ = Bezier(CUBIC).arc_length()
    assert math.dist([0, 0], [80, 0]) < length_


def test_line_intersection_finds_endpoints_on_axis() -> None:
    us = Bezier(CUBIC).line_intersection([[-10, 0], [100, 0]])  # type: ignore[arg-type]
    assert 0.0 in [round(u, 9) for u in us]
    assert 1.0 in [round(u, 9) for u in us]


# -- bezier path --------------------------------------------------------------------------


def test_path_curve_requires_valid_length() -> None:
    with pytest.raises(AssertionError):
        Bezier([[0, 0], [1, 0], [2, 0]]).path_curve(n_degree=3)  # 3 % 3 != 1


def test_path_curve_and_points() -> None:
    bp = Bezier([[0, 0], [1, 1], [2, 0], [3, 1], [4, 0], [5, 1], [6, 0]])
    assert len(bp.path_curve(splinesteps=4, n_degree=3)) > 0
    assert np.asarray(bp.path_points(0, 0.5, n_degree=3)).shape == (2,)


def test_path_length_and_closest_point() -> None:
    bp = Bezier([[0, 0], [1, 1], [2, 0], [3, 1], [4, 0], [5, 1], [6, 0]])
    assert bp.path_arc_length(n_degree=3) > 0
    seg, u = bp.path_closest_point([3, 0], n_degree=3)  # type: ignore[arg-type]
    assert isinstance(seg, int)
    assert 0.0 <= u <= 1.0


def test_close_to_axis_and_offset_return_bezier() -> None:
    bp = Bezier([[0, 10], [3, 12], [7, 8], [10, 10]])
    assert isinstance(bp.close_to_axis(), Bezier)
    assert isinstance(bp.path_offset([0, -5]), Bezier)  # type: ignore[arg-type]


def test_from_path_returns_cubic_bezpath() -> None:
    fp = Bezier.from_path([[0, 0], [10, 10], [20, 0]], relsize=0.1)  # type: ignore[arg-type]
    assert isinstance(fp, Bezier)
    assert len(fp) % 3 == 1  # a valid cubic bezier path


# -- control-point construction -----------------------------------------------------------


def test_begin_tang_end_2d() -> None:
    b = Bezier.begin([0, 0], 0, 2)  # type: ignore[arg-type]  # along +X, distance 2
    np.testing.assert_allclose(b, [[0, 0], [2, 0]], atol=1e-9)
    e = Bezier.end([10, 0], 180, 3)  # type: ignore  # control point 3 to the left of the endpoint
    np.testing.assert_allclose(e, [[7, 0], [10, 0]], atol=1e-9)


def test_tang_collinear_control_points() -> None:
    t = Bezier.tang([1, 1], 0, 2, 4)  # type: ignore  # dir +X, radius1=2 back, radius2=4 forward
    np.testing.assert_allclose(t, [[-1, 1], [1, 1], [5, 1]], atol=1e-9)


def test_joint_independent_directions() -> None:
    j = Bezier.joint([0, 0], 90, 0, 2, 3)  # type: ignore  # approach up, depart right
    np.testing.assert_allclose(j, [[0, 2], [0, 0], [3, 0]], atol=1e-9)


def test_begin_3d_spherical() -> None:
    b = Bezier.begin([-30, 0, 0], 90, 20, phi=135)  # type: ignore[arg-type]
    np.testing.assert_allclose(
        b[1],
        [-30, 20 * math.sin(math.radians(135)), 20 * math.cos(math.radians(135))],
        atol=1e-6,
    )


def test_vector_direction_form() -> None:
    b = Bezier.begin([0, 0], [3, 4])  # type: ignore  # vector, no r -> use it directly
    np.testing.assert_allclose(b[1], [3, 4], atol=1e-9)


def test_flatten_concatenates_groups() -> None:
    flat = Bezier.flatten(
        [
            Bezier.begin([0, 0], -20, 0.4),  # type: ignore[arg-type]
            Bezier.tang([0.25, 0], 0, 0.2, 0.4),  # type: ignore[arg-type]
            Bezier.end([1, 0], 230, 1),  # type: ignore[arg-type]
        ]
    )
    assert isinstance(flat, Bezier)
    assert len(flat) == 2 + 3 + 2


# -- surfaces (BezierPatch) ---------------------------------------------------------------


def test_is_patch_distinguishes_patch_from_list() -> None:
    assert BezierPatch.is_patch(PATCH)
    assert not BezierPatch.is_patch([PATCH, PATCH])


def test_patch_points_scalar_and_grid() -> None:
    bp = BezierPatch(PATCH)  # type: ignore[arg-type]
    assert np.asarray(bp.points(0.5, 0.5)).shape == (3,)
    assert bp.points([0, 0.5, 1], [0, 0.5, 1]).shape == (3, 3, 3)


def test_patch_normals_are_unit() -> None:
    sides = BezierPatch(PATCH).normals(0.5, 0.5)  # type: ignore[arg-type]
    assert math.isclose(float(np.linalg.norm(sides)), 1.0)


def test_patch_vnf_counts_and_validity() -> None:
    v = BezierPatch(PATCH).vnf(splinesteps=8)  # type: ignore[arg-type]
    assert len(v.vertices) == 81  # 9x9 grid
    assert len(v.faces) == 128  # 8x8 cells x 2 tris
    assert _valid(v)


def test_to_vnf_joins_patch_list() -> None:
    v = BezierPatch.to_vnf([PATCH, PATCH], splinesteps=4)  # type: ignore[list-item]
    assert isinstance(v, VNF)
    assert _valid(v)


def test_flat_patch() -> None:
    fp = BezierPatch.flat([100, 100])
    assert len(fp) == 2  # degree 1 -> 2x2 control points
    assert _valid(fp.vnf(4))


def test_reverse_patch() -> None:
    assert len(BezierPatch(PATCH).reverse()) == 4  # type: ignore[arg-type]


def test_sheet_is_valid_vnf() -> None:
    v = BezierPatch(PATCH).sheet([0, -8], splinesteps=6)  # type: ignore[arg-type]
    assert isinstance(v, VNF)
    assert _valid(v)


def test_vnf_degenerate_has_fewer_faces_than_naive() -> None:
    deg = [
        [[-12.5, 12.5, 15]] * 5,
        [
            [-6.25, 11.25, 15],
            [-6.25, 8.75, 15],
            [-6.25, 6.25, 15],
            [-8.75, 6.25, 15],
            [-11.25, 6.25, 15],
        ],
        [[0, 10, 15], [0, 5, 15], [0, 0, 15], [-5, 0, 15], [-10, 0, 15]],
        [[0, 10, 8.75], [0, 5, 8.75], [0, 0, 8.75], [-5, 0, 8.75], [-10, 0, 8.75]],
        [[0, 10, 2.5], [0, 5, 2.5], [0, 0, 2.5], [-5, 0, 2.5], [-10, 0, 2.5]],
    ]
    diameter = BezierPatch(deg).vnf_degenerate(splinesteps=8)  # type: ignore[arg-type]
    naive = BezierPatch(deg).vnf(splinesteps=8)  # type: ignore[arg-type]
    assert _valid(diameter)
    assert len(diameter.faces) < len(naive.faces)  # type: ignore[union-attr]


def test_vnf_degenerate_return_edges() -> None:
    res = BezierPatch(PATCH).vnf_degenerate(splinesteps=6, return_edges=True)  # type: ignore[arg-type]
    assert isinstance(res[0], VNF)  # type: ignore[index]
    assert len(res[1]) == 4  # type: ignore  # [left, right, top, bottom]


# -- sweeps -------------------------------------------------------------------------------


def test_bezier_sweep_valid() -> None:
    v = Bezier([[0, 0, 5], [0, 0, 10], [15, 7, 9], [17, 2, 4]]).sweep(CIRCLE, splinesteps=6)  # type: ignore[arg-type]
    assert isinstance(v, VNF)
    assert _valid(v)


def test_sweep_valid() -> None:
    bp = Bezier([[0, 0, 0], [10, 0, 0], [10, 10, 0], [10, 10, 10]])
    v = bp.sweep(CIRCLE, splinesteps=6, n_degree=3)  # type: ignore[arg-type]
    assert isinstance(v, VNF)
    assert _valid(v)


def test_sweep_transforms_mode() -> None:
    tl = Bezier([[0, 0, 5], [0, 0, 10], [15, 7, 9], [17, 2, 4]]).sweep(CIRCLE, splinesteps=4, transforms=True)  # type: ignore[arg-type]
    assert len(tl) == 5  # type: ignore[arg-type]
    assert np.asarray(tl[0]).shape == (4, 4)  # type: ignore[index]

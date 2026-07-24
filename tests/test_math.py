# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2/math.py: lerp/lerpn interpolation and the deriv calculus helpers."""

import numpy as np
import pytest

from bosl2.math import EPSILON, deriv, deriv2, deriv3, lerp, lerpn


def test_epsilon_value():
    assert EPSILON == 1e-9


def test_lerp_scalar():
    assert lerp(0, 10, 0.0) == 0
    assert lerp(0, 10, 1.0) == 10
    assert lerp(0, 10, 0.5) == 5
    assert lerp(2, 4, 0.25) == 2.5


def test_lerp_vector():
    got = lerp([0, 0], [10, 20], 0.5)
    np.testing.assert_allclose(got, [5, 10])


def test_lerpn_default_hits_both_ends():
    got = lerpn(0, 1, 5)
    np.testing.assert_allclose(got, [0, 0.25, 0.5, 0.75, 1.0])


def test_lerpn_no_endpoint():
    got = lerpn(0, 1, 5, endpoint=False)
    np.testing.assert_allclose(got, [0, 0.2, 0.4, 0.6, 0.8])


def test_lerpn_vector_endpoints():
    got = lerpn([0, 0], [2, 4], 3)
    np.testing.assert_allclose(got, [[0, 0], [1, 2], [2, 4]])


def test_lerpn_degenerate_counts():
    assert lerpn(0, 1, 0).size == 0
    np.testing.assert_allclose(lerpn(5, 9, 1), [5])


def test_deriv_of_straight_line_is_constant():
    path = [[0, 0], [1, 0], [2, 0], [3, 0]]
    diameter = deriv(path)
    np.testing.assert_allclose(diameter, [[1, 0]] * 4, atol=1e-12)


def test_deriv_scales_with_h():
    path = [[0, 0], [1, 0], [2, 0], [3, 0]]
    np.testing.assert_allclose(deriv(path, height=2), [[0.5, 0]] * 4, atol=1e-12)


def test_deriv_nonuniform_h_list():
    path = [[0, 0], [1, 0], [3, 0]]
    diameter = deriv(path, height=[1.0, 2.0])
    assert diameter.shape == (3, 2)


def test_deriv2_of_parabola_is_constant():
    # y = x^2 sampled at x=0..4 -> second derivative ~ 2 everywhere (uniform spacing)
    xs = list(range(5))
    path = [[x, x * x] for x in xs]
    diameter2 = deriv2(path)
    np.testing.assert_allclose(diameter2[:, 1], [2, 2, 2, 2, 2], atol=1e-9)


def test_deriv3_requires_five_points_and_zero_for_quadratic():
    xs = list(range(6))
    path = [[x, x * x] for x in xs]  # 3rd derivative of a quadratic is 0
    d3 = deriv3(path)
    np.testing.assert_allclose(d3[:, 1], np.zeros(6), atol=1e-9)


def test_deriv_closed_wraps():
    square = [[0, 0], [1, 0], [1, 1], [0, 1]]
    diameter = deriv(square, closed=True)
    assert diameter.shape == (4, 2)


@pytest.mark.parametrize("fn", [deriv, deriv2, deriv3])
def test_deriv_returns_ndarray(fn):
    path = [[float(i), float(i * i)] for i in range(6)]
    assert isinstance(fn(path), np.ndarray)

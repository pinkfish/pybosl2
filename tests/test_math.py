# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/math.py: lerp/lerpn interpolation and the deriv calculus helpers."""

import math

import numpy as np
import pytest

from pybosl2.math import EPSILON, constrain, deriv, deriv2, deriv3, lerp, lerpn, mean, modang, quant, slerp, slerpn


def test_epsilon_value() -> None:
    assert EPSILON == 1e-9


def test_lerp_scalar() -> None:
    assert lerp(0, 10, 0.0) == 0
    assert lerp(0, 10, 1.0) == 10
    assert lerp(0, 10, 0.5) == 5
    assert lerp(2, 4, 0.25) == 2.5


def test_lerp_vector() -> None:
    got = lerp([0, 0], [10, 20], 0.5)
    np.testing.assert_allclose(got, [5, 10])


def test_lerpn_default_hits_both_ends() -> None:
    got = lerpn(0, 1, 5)
    np.testing.assert_allclose(got, [0, 0.25, 0.5, 0.75, 1.0])


def test_lerpn_no_endpoint() -> None:
    got = lerpn(0, 1, 5, endpoint=False)
    np.testing.assert_allclose(got, [0, 0.2, 0.4, 0.6, 0.8])


def test_lerpn_vector_endpoints() -> None:
    got = lerpn([0, 0], [2, 4], 3)
    np.testing.assert_allclose(got, [[0, 0], [1, 2], [2, 4]])


def test_lerpn_degenerate_counts() -> None:
    assert lerpn(0, 1, 0).size == 0
    np.testing.assert_allclose(lerpn(5, 9, 1), [5])


def test_deriv_of_straight_line_is_constant() -> None:
    path = [[0, 0], [1, 0], [2, 0], [3, 0]]
    diameter = deriv(path)
    np.testing.assert_allclose(diameter, [[1, 0]] * 4, atol=1e-12)


def test_deriv_scales_with_h() -> None:
    path = [[0, 0], [1, 0], [2, 0], [3, 0]]
    np.testing.assert_allclose(deriv(path, height=2), [[0.5, 0]] * 4, atol=1e-12)


def test_deriv_nonuniform_h_list() -> None:
    path = [[0, 0], [1, 0], [3, 0]]
    diameter = deriv(path, height=[1.0, 2.0])
    assert diameter.shape == (3, 2)


def test_deriv2_of_parabola_is_constant() -> None:
    # y = x^2 sampled at x=0..4 -> second derivative ~ 2 everywhere (uniform spacing)
    xs = list(range(5))
    path = [[x, x * x] for x in xs]
    diameter2 = deriv2(path)
    np.testing.assert_allclose(diameter2[:, 1], [2, 2, 2, 2, 2], atol=1e-9)


def test_deriv3_requires_five_points_and_zero_for_quadratic() -> None:
    xs = list(range(6))
    path = [[x, x * x] for x in xs]  # 3rd derivative of a quadratic is 0
    d3 = deriv3(path)
    np.testing.assert_allclose(d3[:, 1], np.zeros(6), atol=1e-9)


def test_deriv_closed_wraps() -> None:
    square = [[0, 0], [1, 0], [1, 1], [0, 1]]
    diameter = deriv(square, closed=True)
    assert diameter.shape == (4, 2)


@pytest.mark.parametrize("fn", [deriv, deriv2, deriv3])
def test_deriv_returns_ndarray(fn: object) -> None:
    path = [[float(i), float(i * i)] for i in range(6)]
    assert isinstance(fn(path), np.ndarray)  # type: ignore[operator]


# ── deriv edge cases ─────────────────────────────────────────────────────


def test_deriv_two_points() -> None:
    path = [[0, 0], [2, 2]]
    d = deriv(path)
    assert d.shape == (2, 2)
    np.testing.assert_allclose(d, [[1, 1], [1, 1]], atol=1e-12)


def test_deriv_nonuniform_closed() -> None:
    path = [[0, 0], [1, 0], [1, 1], [0, 1]]
    h = [1.0, 1.0, 1.0, 1.0]
    d = deriv(path, height=h, closed=True)
    assert d.shape == (4, 2)


def test_deriv2_length_three() -> None:
    path = [[0, 0], [1, 1], [2, 4]]
    d2 = deriv2(path)
    assert d2.shape == (3, 2)


def test_deriv2_length_four() -> None:
    path = [[0, 0], [1, 1], [2, 4], [3, 9]]
    d2 = deriv2(path)
    assert d2.shape == (4, 2)


def test_deriv2_closed() -> None:
    square = [[0, 0], [1, 0], [1, 1], [0, 1]]
    d2 = deriv2(square, closed=True)
    assert d2.shape == (4, 2)


def test_deriv3_closed() -> None:
    hexagon = [[0, 0], [1, 0], [2, 1], [1, 2], [0, 2], [-1, 1]]
    d3 = deriv3(hexagon, closed=True)
    assert d3.shape == (6, 2)


# ── convenience helpers ──────────────────────────────────────────────────


def test_modang_basic() -> None:
    assert modang(0) == 0.0
    assert modang(90) == 90.0
    assert modang(180) == pytest.approx(-180.0)
    assert modang(270) == pytest.approx(-90.0)
    assert modang(-90) == -90.0
    assert modang(360) == 0.0
    assert modang(450) == 90.0


def test_constrain_basic() -> None:
    assert constrain(5, minval=0, maxval=10) == 5.0
    assert constrain(-1, minval=0) == 0.0
    assert constrain(100, maxval=50, minval=0) == 50.0


def test_constrain_none_bounds() -> None:
    assert constrain(5) == 5.0
    assert constrain(-100, maxval=0) == -100.0
    assert constrain(200, minval=50) == 200.0


def test_quant_basic() -> None:
    assert quant(3.7, 1.0) == 4.0
    assert quant(3.2, 0.5) == 3.0
    assert quant(10, 3) == 9.0


def test_quant_raises_on_nonpositive() -> None:
    with pytest.raises(ValueError, match="Quantum must be positive"):
        quant(5, 0)
    with pytest.raises(ValueError, match="Quantum must be positive"):
        quant(5, -1)


def test_mean_basic() -> None:
    assert mean([1, 2, 3, 4]) == 2.5
    assert mean([5.0]) == 5.0


def test_mean_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        mean([])


# ── slerp / slerpn ───────────────────────────────────────────────────────


def test_slerp_basic() -> None:
    result = slerp([1, 0, 0], [0, 1, 0], 0.0)
    np.testing.assert_allclose(result, [1, 0, 0], atol=1e-9)

    result = slerp([1, 0, 0], [0, 1, 0], 1.0)
    np.testing.assert_allclose(result, [0, 1, 0], atol=1e-9)

    result = slerp([1, 0, 0], [0, 1, 0], 0.5)
    assert abs(math.hypot(*result) - 1.0) < 1e-9


def test_slerp_zero_vector_raises() -> None:
    with pytest.raises(ValueError, match="zero-length"):
        slerp([0, 0, 0], [1, 0, 0], 0.5)
    with pytest.raises(ValueError, match="zero-length"):
        slerp([1, 0, 0], [0, 0, 0], 0.5)


def test_slerp_opposite_vectors() -> None:
    with pytest.raises(ValueError, match="180°"):
        slerp([1, 0, 0], [-1, 0, 0], 0.5)


def test_slerpn_basic() -> None:
    result = slerpn([1, 0, 0], [0, 1, 0], 5)
    assert len(result) == 5
    for v in result:
        assert len(v) == 3
        assert abs(math.hypot(*v) - 1.0) < 1e-9


def test_slerpn_no_endpoint() -> None:
    result = slerpn([1, 0, 0], [0, 1, 0], 3, endpoint=False)
    assert len(result) == 3


def test_slerpn_zero_vector_raises() -> None:
    with pytest.raises(ValueError, match="zero-length"):
        slerpn([0, 0, 0], [1, 0, 0], 5)


def test_slerpn_opposite_vectors() -> None:
    with pytest.raises(ValueError, match="180°"):
        slerpn([1, 0, 0], [-1, 0, 0], 5)

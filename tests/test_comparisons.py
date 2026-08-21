# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for approximate-equality: math.isclose (scalars) and numpy.allclose (vectors)."""

import math

import numpy as np


def test_scalar_equal_and_close() -> None:
    assert math.isclose(1.0, 1.0, rel_tol=0, abs_tol=1e-9)
    assert math.isclose(1.0, 1.0 + 1e-12, rel_tol=0, abs_tol=1e-9)
    assert not math.isclose(1.0, 1.001, rel_tol=0, abs_tol=1e-9)


def test_scalar_eps_override() -> None:
    assert math.isclose(1.0, 1.01, rel_tol=0, abs_tol=0.1)
    assert not math.isclose(1.0, 1.01, rel_tol=0, abs_tol=1e-6)


def test_vector_component_wise() -> None:
    assert np.allclose([1, 2, 3], [1, 2, 3 + 1e-12], rtol=0, atol=1e-9)
    assert not np.allclose([1, 2, 3], [1, 2, 3.5], rtol=0, atol=1e-9)


def test_vectors_of_different_length_are_not_equal() -> None:
    assert len([1, 2]) != len([1, 2, 3])


def test_accepts_ndarrays() -> None:
    assert np.allclose(np.array([0.0, 0.0]), np.array([0.0, 1e-13]), rtol=0, atol=1e-9)
    assert not np.allclose(np.array([0.0, 0.0]), np.array([0.0, 1.0]), rtol=0, atol=1e-9)


def test_returns_plain_bool() -> None:
    """Both comparisons hand back a real `bool`, not a numpy scalar that only looks like one."""
    scalar = math.isclose(1, 2, rel_tol=0, abs_tol=1e-9)
    assert scalar is False
    assert type(scalar) is bool

    vector = bool(np.allclose([1, 2], [1, 2], rtol=0, atol=1e-9))
    assert vector is True
    assert type(vector) is bool

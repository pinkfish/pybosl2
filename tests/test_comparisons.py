# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2/comparisons.py: the approx() approximate-equality helper."""

import numpy as np

from bosl2.comparisons import approx


def test_scalar_equal_and_close():
    assert approx(1.0, 1.0)
    assert approx(1.0, 1.0 + 1e-12)
    assert not approx(1.0, 1.001)


def test_scalar_eps_override():
    assert approx(1.0, 1.01, eps=0.1)
    assert not approx(1.0, 1.01, eps=1e-6)


def test_vector_component_wise():
    assert approx([1, 2, 3], [1, 2, 3 + 1e-12])
    assert not approx([1, 2, 3], [1, 2, 3.5])


def test_vectors_of_different_length_are_not_equal():
    assert not approx([1, 2], [1, 2, 3])


def test_accepts_ndarrays():
    assert approx(np.array([0.0, 0.0]), np.array([0.0, 1e-13]))
    assert not approx(np.array([0.0, 0.0]), np.array([0.0, 1.0]))


def test_nested_vectors():
    assert approx([[0, 0], [1, 1]], [[0, 0], [1, 1 + 1e-13]])


def test_returns_plain_bool():
    assert isinstance(approx([1, 2], [1, 2]), bool)
    assert isinstance(approx(1, 2), bool)

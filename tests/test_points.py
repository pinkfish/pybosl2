# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/points.py: the Point and Vector classes."""

import numpy as np
import pytest

from pybosl2.points import Point, Vector


class TestPoint:
    def test_2d_default(self) -> None:
        p = Point(1.0, 2.0)
        assert p.is_2d
        assert p.z is None
        assert len(p) == 2
        assert list(p) == [1.0, 2.0]

    def test_3d(self) -> None:
        p = Point(1.0, 2.0, 3.0)
        assert not p.is_2d
        assert p.z == 3.0
        assert len(p) == 3
        assert list(p) == [1.0, 2.0, 3.0]

    def test_indexing_2d(self) -> None:
        p = Point(1.0, 2.0)
        assert p[0] == 1.0
        assert p[1] == 2.0
        with pytest.raises(IndexError):
            p[2]

    def test_indexing_3d(self) -> None:
        p = Point(1.0, 2.0, 3.0)
        assert p[0] == 1.0
        assert p[1] == 2.0
        assert p[2] == 3.0

    def test_numpy_array_2d(self) -> None:
        arr = np.asarray(Point(1.0, 2.0))
        assert arr.shape == (2,)
        np.testing.assert_allclose(arr, [1.0, 2.0])

    def test_numpy_array_3d(self) -> None:
        arr = np.asarray(Point(1.0, 2.0, 3.0))
        assert arr.shape == (3,)
        np.testing.assert_allclose(arr, [1.0, 2.0, 3.0])

    def test_addition(self) -> None:
        result = Point(1, 2, 3) + [4, 5, 6]
        np.testing.assert_allclose(result, [5, 7, 9])

    def test_negation(self) -> None:
        result = -Point(1, -2, 3)
        np.testing.assert_allclose(result, [-1, 2, -3])

    def test_multiplication(self) -> None:
        result = Point(1, 2, 3) * 3
        np.testing.assert_allclose(result, [3, 6, 9])

    def test_equality(self) -> None:
        assert Point(1, 2, 3) == [1, 2, 3]
        assert Point(1, 2) == [1, 2]
        assert Point(1, 2, 3) != [1, 2, 4]

    def test_dot(self) -> None:
        assert Point(1, 0, 0).dot([0, 1, 0]) == 0.0
        assert Point(1, 2, 3).dot([1, 1, 1]) == pytest.approx(6.0)

    def test_cross_3d(self) -> None:
        result = Point(1, 0, 0).cross(Point(0, 1, 0))  # type: ignore[arg-type]
        np.testing.assert_allclose(result, [0, 0, 1])

    def test_cross_2d_raises(self) -> None:
        with pytest.raises(ValueError, match="3‑D"):
            Point(1, 2).cross(Point(3, 4))  # type: ignore[arg-type]

    def test_norm(self) -> None:
        p = Point(3, 4)
        assert p.norm == pytest.approx(5.0)
        p3 = Point(1, 2, 2)
        assert p3.norm == pytest.approx(3.0)

    def test_astuple_2d(self) -> None:
        assert Point(1, 2).astuple() == (1.0, 2.0)

    def test_astuple_3d(self) -> None:
        assert Point(1, 2, 3).astuple() == (1.0, 2.0, 3.0)

    def test_tolist_2d(self) -> None:
        assert Point(1, 2).tolist() == [1.0, 2.0]

    def test_tolist_3d(self) -> None:
        assert Point(1, 2, 3).tolist() == [1.0, 2.0, 3.0]

    def test_copy(self) -> None:
        p = Point(3, 4, 5)
        c = p.copy()
        assert c == p
        assert c is not p

    def test_to_3d_from_2d(self) -> None:
        p = Point(1, 2).to_3d(5.0)
        assert not p.is_2d
        assert p.z == 5.0
        assert p == Point(1, 2, 5)

    def test_to_3d_from_3d(self) -> None:
        p = Point(1, 2, 3).to_3d(99.0)
        assert p.z == 99.0


class TestVector:
    def test_3d_arithmetic(self) -> None:
        v = Vector([1, 2, 3])
        assert v + [4, 5, 6] == [5, 7, 9]
        assert v * 3 == [3, 6, 9]
        assert -v == [-1, -2, -3]

    def test_2d_vector(self) -> None:
        v = Vector([1, 2])
        assert v.is_2d
        assert len(v) == 2
        assert v.z is None

    def test_3d_vector(self) -> None:
        v = Vector([1, 2, 3])
        assert not v.is_2d
        assert v.z == 3.0

    def test_properties(self) -> None:
        v = Vector([10, 20, 30])
        assert v.x == 10.0
        assert v.y == 20.0
        assert v.z == 30.0

    def test_to_3d_from_2d(self) -> None:
        v = Vector([1, 2]).to_3d(5.0)
        assert len(v) == 3
        assert v.z == 5.0

    def test_dot(self) -> None:
        assert Vector([1, 0, 0]).dot([0, 1, 0]) == 0.0

    def test_cross(self) -> None:
        result = Vector([1, 0, 0]).cross(Vector([0, 1, 0]))
        np.testing.assert_allclose(result, [0, 0, 1])

    def test_cross_2d_raises(self) -> None:
        with pytest.raises(ValueError, match="3‑D"):
            Vector([1, 2]).cross(Vector([3, 4]))

    def test_norm(self) -> None:
        assert Vector([3, 4]).norm == pytest.approx(5.0)

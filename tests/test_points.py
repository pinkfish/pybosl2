# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/points.py: the Point class (and Vector alias)."""

import copy
import math

import numpy as np
import pytest

from pybosl2.points import Point

Vector = Point  # backward-compat alias


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
        assert isinstance(result, Point)
        assert list(result) == [5, 7, 9]

    def test_negation(self) -> None:
        result = -Point(1, -2, 3)
        assert isinstance(result, Point)
        assert list(result) == [-1, 2, -3]

    def test_multiplication(self) -> None:
        result = Point(1, 2, 3) * 3
        assert isinstance(result, Point)
        assert list(result) == [3, 6, 9]

    def test_equality(self) -> None:
        assert Point(1, 2, 3) == [1, 2, 3]
        assert Point(1, 2) == [1, 2]
        assert Point(1, 2, 3) != [1, 2, 4]

    def test_dot(self) -> None:
        assert Point(1, 0, 0).dot([0, 1, 0]) == 0.0
        assert Point(1, 2, 3).dot([1, 1, 1]) == pytest.approx(6.0)

    def test_cross_3d(self) -> None:
        result = Point(1, 0, 0).cross(Point(0, 1, 0))
        assert isinstance(result, Point)
        assert list(result) == [0, 0, 1]

    def test_cross_2d_raises(self) -> None:
        with pytest.raises(ValueError, match="3‑D"):
            Point(1, 2).cross(Point(3, 4))

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
        assert isinstance(result, Point)
        assert list(result) == [0, 0, 1]

    def test_cross_2d_raises(self) -> None:
        with pytest.raises(ValueError, match="3‑D"):
            Vector([1, 2]).cross(Vector([3, 4]))

    def test_norm(self) -> None:
        assert Vector([3, 4]).norm == pytest.approx(5.0)


class TestPointAdvanced:
    """Tests for previously uncovered Point APIs."""

    # ── repr ──────────────────────────────────────────────────────────

    def test_repr_2d(self) -> None:
        assert repr(Point(1.5, 2.5)) == "Point(1.5, 2.5)"

    def test_repr_3d(self) -> None:
        assert repr(Point(1.5, 2.5, 3.5)) == "Point(1.5, 2.5, 3.5)"

    # ── __getitem__ slice ─────────────────────────────────────────────

    def test_getitem_slice(self) -> None:
        p = Point(1, 2, 3)
        assert p[0:2] == (1.0, 2.0)
        assert p[1:] == (2.0, 3.0)
        assert p[:2] == (1.0, 2.0)

    # ── reverse arithmetic ────────────────────────────────────────────

    def test_radd(self) -> None:
        result = [1.0, 2.0, 3.0] + Point(4, 5, 6)
        assert isinstance(result, Point)
        assert list(result) == [5, 7, 9]

    def test_subtraction(self) -> None:
        result = Point(5, 7, 9) - [1, 2, 3]
        assert isinstance(result, Point)
        assert list(result) == [4, 5, 6]

    def test_rsub(self) -> None:
        result = [5.0, 7.0, 9.0] - Point(4, 5, 6)
        assert isinstance(result, Point)
        assert list(result) == [1, 2, 3]

    def test_truediv(self) -> None:
        result = Point(4, 6, 8) / 2.0
        assert isinstance(result, Point)
        assert list(result) == [2, 3, 4]

    def test_rtruediv(self) -> None:
        result = 12.0 / Point(3, 4, 6)
        assert isinstance(result, Point)
        assert list(result) == [4, 3, 2]

    def test_rmul(self) -> None:
        result = 3.0 * Point(1, 2, 3)
        assert isinstance(result, Point)
        assert list(result) == [3, 6, 9]

    def test_abs(self) -> None:
        assert abs(Point(3, 4)) == pytest.approx(5.0)
        assert abs(Point(1, 2, 2)) == pytest.approx(3.0)

    def test_copy_dunder(self) -> None:
        p = Point(3, 4, 5)
        c = copy.copy(p)
        assert c == p
        assert c is not p

    # ── from_seq ───────────────────────────────────────────────────────

    def test_from_seq_2d(self) -> None:
        p = Point.from_seq([1.0, 2.0])
        assert p.is_2d
        assert p == Point(1, 2)

    def test_from_seq_3d(self) -> None:
        p = Point.from_seq([1.0, 2.0, 3.0])
        assert not p.is_2d
        assert p == Point(1, 2, 3)

    def test_from_seq_numpy(self) -> None:
        p = Point.from_seq(np.array([4.0, 5.0, 6.0]))
        assert p == Point(4, 5, 6)

    def test_from_seq_raises(self) -> None:
        with pytest.raises(ValueError, match="Expected 2 or 3"):
            Point.from_seq([1.0, 2.0, 3.0, 4.0])
        with pytest.raises(ValueError, match="Expected 2 or 3"):
            Point.from_seq([1.0])

    # ── __init__ edge cases ────────────────────────────────────────────

    def test_init_from_point(self) -> None:
        p = Point(1, 2, 3)
        q = Point(p)
        assert q == p
        assert q is not p

    def test_init_single_element(self) -> None:
        p = Point([5.0])
        assert p.is_2d
        assert list(p) == [5.0, 0.0]

    def test_init_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="Expected 1-3"):
            Point([])

    def test_init_from_numpy(self) -> None:
        p = Point(np.array([7.0, 8.0, 9.0]))
        assert p == Point(7, 8, 9)

    # ── normalized ─────────────────────────────────────────────────────

    def test_normalized(self) -> None:
        n = Point(3, 4).normalized()
        assert n.norm == pytest.approx(1.0)
        assert n == pytest.approx(Point(0.6, 0.8))

    def test_normalized_3d(self) -> None:
        n = Point(1, 2, 2).normalized()
        assert n.norm == pytest.approx(1.0)

    def test_normalized_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="zero vector"):
            Point(0, 0).normalized()

    def test_normalized_zero_with_error(self) -> None:
        fallback = Point(1, 0, 0)
        result = Point(0, 0).normalized(error=fallback)
        assert result == fallback

    # ── angle ──────────────────────────────────────────────────────────

    def test_angle(self) -> None:
        a = Point(1, 0).angle(Point(0, 1))
        assert a == pytest.approx(math.pi / 2)

    def test_angle_dimension_mismatch(self) -> None:
        with pytest.raises(ValueError, match="same dimension"):
            Point(1, 0).angle(Point(1, 0, 0))

    def test_angle_zero_vector(self) -> None:
        with pytest.raises(ValueError, match="zero-length"):
            Point(0, 0).angle(Point(1, 0))

    # ── axis ───────────────────────────────────────────────────────────

    def test_axis(self) -> None:
        axis_vec, ang = Point(1, 0, 0).axis(Point(0, 1, 0))
        assert ang == pytest.approx(math.pi / 2)
        assert axis_vec == pytest.approx([0, 0, 1])

    def test_axis_parallel(self) -> None:
        axis_vec, ang = Point(2, 0, 0).axis(Point(3, 0, 0))
        assert ang == pytest.approx(0.0)
        assert axis_vec == [0.0, 0.0, 1.0]

    def test_axis_dimension_error(self) -> None:
        with pytest.raises(ValueError, match="3-D vectors"):
            Point(1, 0).axis(Point(0, 1))

    def test_axis_zero_vector(self) -> None:
        with pytest.raises(ValueError, match="zero-length"):
            Point(0, 0, 0).axis(Point(1, 0, 0))

    # ── bisect ─────────────────────────────────────────────────────────

    def test_bisect(self) -> None:
        b = Point(1, 0).bisect(Point(0, 1))
        assert b is not None
        assert b.norm == pytest.approx(1.0)
        assert b == pytest.approx(Point(math.sqrt(2) / 2, math.sqrt(2) / 2))

    def test_bisect_opposite_returns_none(self) -> None:
        b = Point(1, 0).bisect(Point(-1, 0))
        assert b is None

    def test_bisect_dimension_mismatch(self) -> None:
        with pytest.raises(ValueError, match="same dimension"):
            Point(1, 0).bisect(Point(1, 0, 0))

    def test_bisect_zero_vector(self) -> None:
        with pytest.raises(ValueError, match="zero-length"):
            Point(0, 0).bisect(Point(1, 0))

    # ── closest / furthest ─────────────────────────────────────────────

    def test_closest(self) -> None:
        pts = [Point(10, 0), Point(1, 0), Point(3, 4)]
        assert Point(0, 0).closest(pts) == 1

    def test_closest_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            Point(0, 0).closest([])

    def test_furthest(self) -> None:
        pts = [Point(10, 0), Point(1, 0), Point(3, 4)]
        assert Point(0, 0).furthest(pts) == 0

    def test_furthest_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            Point(0, 0).furthest([])

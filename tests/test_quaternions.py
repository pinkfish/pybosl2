# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

import math
from copy import copy

import numpy as np
import pytest

from pybosl2.quaternions import (
    Quaternion,
    quaternion,
    quaternion_mult,
    quaternion_rot,
    quaternion_slerp,
    quaternion_to_axis,
    quaternion_to_matrix,
)


def test_quaternion_identity() -> None:
    q = quaternion()
    assert q == [0.0, 0.0, 0.0, 1.0]


def test_quaternion_from_angle_axis() -> None:
    # 90 degrees around Z axis
    q = quaternion(angle=90.0, axis=[0.0, 0.0, 1.0])
    expected = [0.0, 0.0, math.sin(math.radians(45)), math.cos(math.radians(45))]
    assert q == pytest.approx(expected)

    # Errors
    with pytest.raises(ValueError, match="must specify axis when angle is given"):
        quaternion(angle=90.0)

    with pytest.raises(ValueError, match="axis vector cannot be zero-length"):
        quaternion(angle=90.0, axis=[0.0, 0.0, 0.0])


def test_quaternion_from_rpy() -> None:
    q = quaternion(rpy=[0.0, 0.0, 90.0])
    q_expected = quaternion(angle=90.0, axis=[0.0, 0.0, 1.0])
    assert q == pytest.approx(q_expected)


def test_quaternion_from_matrix() -> None:
    # Rotation matrix for 90 degrees around Z
    m = [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    q = quaternion(matrix=m)
    q_expected = quaternion(angle=90.0, axis=[0.0, 0.0, 1.0])
    assert q == pytest.approx(q_expected)


def test_quaternion_to_matrix() -> None:
    q = quaternion(angle=90.0, axis=[0.0, 0.0, 1.0])
    m = quaternion_to_matrix(q)
    expected = [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    for i in range(3):
        assert m[i] == pytest.approx(expected[i])


def test_quaternion_to_axis() -> None:
    q = quaternion(angle=60.0, axis=[1.0, 0.0, 0.0])
    angle, axis = quaternion_to_axis(q)
    assert angle == pytest.approx(60.0)
    assert axis == pytest.approx([1.0, 0.0, 0.0])


def test_quaternion_mult() -> None:
    q1 = quaternion(angle=45.0, axis=[0.0, 0.0, 1.0])
    q2 = quaternion(angle=45.0, axis=[0.0, 0.0, 1.0])
    q3 = quaternion_mult(q1, q2)
    q_expected = quaternion(angle=90.0, axis=[0.0, 0.0, 1.0])
    assert q3 == pytest.approx(q_expected)


def test_quaternion_slerp() -> None:
    q1 = quaternion(angle=0.0, axis=[0.0, 0.0, 1.0])
    q2 = quaternion(angle=90.0, axis=[0.0, 0.0, 1.0])
    q_mid = quaternion_slerp(q1, q2, 0.5)
    q_expected = quaternion(angle=45.0, axis=[0.0, 0.0, 1.0])
    assert q_mid == pytest.approx(q_expected)


def test_quaternion_rot() -> None:
    q = quaternion(angle=90.0, axis=[0.0, 0.0, 1.0])
    v = [1.0, 0.0, 0.0]
    v_rot = quaternion_rot(q, v)
    assert v_rot == pytest.approx([0.0, 1.0, 0.0])


def test_quaternion_class_initialization() -> None:
    # Default
    q = Quaternion()
    assert q.q[0] == 1.0
    assert list(q.q[1:4]) == [0.0, 0.0, 0.0]

    # Keyword scalar/vector
    q = Quaternion.from_scalar_vector(2.0, [1.0, 2.0, 3.0])
    assert q.q[0] == 2.0
    assert list(q.q[1:4]) == [1.0, 2.0, 3.0]

    # Keyword real/imaginary
    q = Quaternion.from_real_imaginary(3.0, [4.0, 5.0, 6.0])
    assert q.scalar == 3.0
    assert list(q.imaginary) == [4.0, 5.0, 6.0]

    # Axis/degrees
    q = Quaternion.from_axis_angle([0.0, 1.0, 0.0], math.radians(90.0))
    assert q.degrees == pytest.approx(90.0)

    # Matrix
    m = np.eye(3)
    q = Quaternion.from_matrix(m)
    assert q.scalar == 1.0

    # From copy/deepcopy
    q2 = copy(q)
    assert q2 == q


def test_quaternion_class_properties_and_representation() -> None:
    q = Quaternion(1.0, 2.0, 3.0, 4.0)
    assert q.w == 1.0
    assert q.x == 2.0
    assert q.y == 3.0
    assert q.z == 4.0
    assert q.real == 1.0
    assert list(q.imaginary) == [2.0, 3.0, 4.0]

    # String format
    assert str(q).startswith("1.000")
    assert repr(q) == "Quaternion(1.0, 2.0, 3.0, 4.0)"
    assert f"{q:+.1f}" == "+1.0 +2.0i +3.0j +4.0k"


def test_quaternion_class_algebra() -> None:
    q1 = Quaternion(1.0, 2.0, 3.0, 4.0)
    q2 = Quaternion(2.0, 3.0, 4.0, 5.0)

    # Addition/Subtraction
    q_add = q1 + q2
    assert list(q_add.q) == [3.0, 5.0, 7.0, 9.0]
    q_sub = q1 - q2
    assert list(q_sub.q) == [-1.0, -1.0, -1.0, -1.0]

    # Multiplication
    assert (q1 * q2) != q1

    # In-place operators
    q_inplace = Quaternion(q1.w, q1.x, q1.y, q1.z)
    q_inplace += q2
    assert q_inplace == q1 + q2

    # Conjugate & Inverse
    assert q1.conjugate.w == q1.w
    assert list(q1.conjugate.vector) == list(-q1.vector)
    q_inv = q1.inverse
    assert (q1 * q_inv).q[0] == pytest.approx(1.0)


def test_quaternion_class_math_functions() -> None:
    q = Quaternion.from_axis_angle([1.0, 0.0, 0.0], math.pi / 2)
    # Norm / Normalised
    assert q.norm == pytest.approx(1.0)
    assert q.is_unit()
    assert q.normalised.is_unit()

    # Exp / Log
    q_exp = Quaternion.exp(q)
    q_log = Quaternion.log(q_exp)
    assert q_log.q == pytest.approx(q.q)

    # Intrinsic Distance
    assert Quaternion.distance(q, q) == pytest.approx(0.0)
    q_rot = Quaternion.from_axis_angle([1.0, 0.0, 0.0], math.pi)
    assert Quaternion.distance(q, q_rot) > 0.0

    # Random
    q_rand = Quaternion.random()
    assert q_rand.is_unit()

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

import math

import pytest

from pybosl2.quaternions import (
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

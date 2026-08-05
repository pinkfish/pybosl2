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
    # Identity quaternion norm
    assert math.hypot(*q) == pytest.approx(1.0)


def test_quaternion_from_angle_axis() -> None:
    # 90 degrees around Z axis
    q = quaternion(angle=90.0, axis=[0.0, 0.0, 1.0])
    expected = [0.0, 0.0, math.sin(math.radians(45)), math.cos(math.radians(45))]
    assert q == pytest.approx(expected)
    # Precise component checks
    assert q[0] == pytest.approx(0.0)
    assert q[1] == pytest.approx(0.0)
    assert q[2] == pytest.approx(0.7071067811865475)
    assert q[3] == pytest.approx(0.7071067811865476)
    # Must be a unit quaternion
    assert math.hypot(*q) == pytest.approx(1.0)

    # Errors
    with pytest.raises(ValueError, match="must specify axis when angle is given"):
        quaternion(angle=90.0)

    with pytest.raises(ValueError, match="axis vector cannot be zero-length"):
        quaternion(angle=90.0, axis=[0.0, 0.0, 0.0])


def test_quaternion_from_rpy() -> None:
    q = quaternion(rpy=[0.0, 0.0, 90.0])
    q_expected = quaternion(angle=90.0, axis=[0.0, 0.0, 1.0])
    assert q == pytest.approx(q_expected)
    # Component-level check: yaw=90 is same as angle=90 around Z
    assert q[2] == pytest.approx(0.7071067811865475)
    assert q[3] == pytest.approx(0.7071067811865476)
    assert q[0] == pytest.approx(0.0)
    assert q[1] == pytest.approx(0.0)
    assert math.hypot(*q) == pytest.approx(1.0)


def test_quaternion_from_matrix() -> None:
    # Rotation matrix for 90 degrees around Z
    m = [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    q = quaternion(matrix=m)
    q_expected = quaternion(angle=90.0, axis=[0.0, 0.0, 1.0])
    assert q == pytest.approx(q_expected)
    # Component checks
    assert q[0] == pytest.approx(0.0)
    assert q[1] == pytest.approx(0.0)
    assert q[2] == pytest.approx(0.7071067811865475)
    assert q[3] == pytest.approx(0.7071067811865476)
    assert math.hypot(*q) == pytest.approx(1.0)


def test_quaternion_to_matrix() -> None:
    q = quaternion(angle=90.0, axis=[0.0, 0.0, 1.0])
    m = quaternion_to_matrix(q)
    expected = [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    for i in range(3):
        assert m[i] == pytest.approx(expected[i])
    # Also check exact matrix values with abs tolerance for floating-point
    assert m[0][0] == pytest.approx(0.0, abs=1e-6)
    assert m[0][1] == pytest.approx(-1.0)
    assert m[0][2] == pytest.approx(0.0, abs=1e-6)
    assert m[1][0] == pytest.approx(1.0)
    assert m[1][1] == pytest.approx(0.0, abs=1e-6)
    assert m[1][2] == pytest.approx(0.0, abs=1e-6)
    assert m[2][0] == pytest.approx(0.0, abs=1e-6)
    assert m[2][1] == pytest.approx(0.0, abs=1e-6)
    assert m[2][2] == pytest.approx(1.0)


def test_quaternion_to_axis() -> None:
    q = quaternion(angle=60.0, axis=[1.0, 0.0, 0.0])
    angle, axis = quaternion_to_axis(q)
    assert angle == pytest.approx(60.0)
    assert axis == pytest.approx([1.0, 0.0, 0.0])
    # Axis components precisely
    assert axis[0] == pytest.approx(1.0)
    assert axis[1] == pytest.approx(0.0, abs=1e-9)
    assert axis[2] == pytest.approx(0.0, abs=1e-9)


def test_quaternion_mult() -> None:
    q1 = quaternion(angle=45.0, axis=[0.0, 0.0, 1.0])
    q2 = quaternion(angle=45.0, axis=[0.0, 0.0, 1.0])
    q3 = quaternion_mult(q1, q2)
    q_expected = quaternion(angle=90.0, axis=[0.0, 0.0, 1.0])
    assert q3 == pytest.approx(q_expected)
    # Intermediate quaternion values (45 deg Z)
    assert math.hypot(*q1) == pytest.approx(1.0)
    assert math.hypot(*q2) == pytest.approx(1.0)
    # q1 = [0, 0, sin(22.5), cos(22.5)]
    assert q1[0] == pytest.approx(0.0)
    assert q1[1] == pytest.approx(0.0)
    assert q1[2] == pytest.approx(0.3826834323650898)
    assert q1[3] == pytest.approx(0.9238795325112867)
    # q3 components = [0, 0, sin(45), cos(45)]
    assert q3[0] == pytest.approx(0.0)
    assert q3[1] == pytest.approx(0.0)
    assert q3[2] == pytest.approx(0.7071067811865476)
    assert q3[3] == pytest.approx(0.7071067811865475)
    assert math.hypot(*q3) == pytest.approx(1.0)


def test_quaternion_slerp() -> None:
    q1 = quaternion(angle=0.0, axis=[0.0, 0.0, 1.0])
    q2 = quaternion(angle=90.0, axis=[0.0, 0.0, 1.0])
    q_mid = quaternion_slerp(q1, q2, 0.5)
    q_expected = quaternion(angle=45.0, axis=[0.0, 0.0, 1.0])
    assert q_mid == pytest.approx(q_expected)
    # Slerp midpoint of 0 and 90 degrees Z produces 45 degree Z
    assert q_mid[2] == pytest.approx(0.3826834323650898)  # sin(22.5)
    assert q_mid[3] == pytest.approx(0.9238795325112867)  # cos(22.5)
    assert q_mid[0] == pytest.approx(0.0)
    assert q_mid[1] == pytest.approx(0.0)
    assert math.hypot(*q_mid) == pytest.approx(1.0)


def test_quaternion_rot() -> None:
    q = quaternion(angle=90.0, axis=[0.0, 0.0, 1.0])
    v = [1.0, 0.0, 0.0]
    v_rot = quaternion_rot(q, v)
    assert v_rot == pytest.approx([0.0, 1.0, 0.0])
    # Precise rotated coordinates
    assert v_rot[0] == pytest.approx(0.0, abs=1e-6)
    assert v_rot[1] == pytest.approx(1.0)
    assert v_rot[2] == pytest.approx(0.0, abs=1e-6)


def test_quaternion_class_initialization() -> None:
    # Default
    q = Quaternion()
    assert q.q[0] == 1.0
    assert list(q.q[1:4]) == [0.0, 0.0, 0.0]
    # Default is unit
    assert q.scalar == 1.0
    assert q.norm == pytest.approx(1.0)
    assert q.is_unit()

    # Keyword scalar/vector
    q = Quaternion.from_scalar_vector(2.0, [1.0, 2.0, 3.0])
    assert q.q[0] == 2.0
    assert list(q.q[1:4]) == [1.0, 2.0, 3.0]
    # Components
    assert q.w == 2.0
    assert q.x == 1.0
    assert q.y == 2.0
    assert q.z == 3.0
    assert q.scalar == 2.0
    assert q.norm == pytest.approx(4.242640687119285)

    # Keyword real/imaginary
    q = Quaternion.from_real_imaginary(3.0, [4.0, 5.0, 6.0])
    assert q.scalar == 3.0
    assert list(q.imaginary) == [4.0, 5.0, 6.0]
    assert q.real == 3.0

    # Axis/degrees
    q = Quaternion.from_axis_angle([0.0, 1.0, 0.0], math.radians(90.0))
    assert q.degrees == pytest.approx(90.0)
    # q is cos(45), 0, sin(45), 0
    assert q.w == pytest.approx(0.7071067811865475)
    assert q.y == pytest.approx(0.7071067811865476)
    assert q.x == pytest.approx(0.0)
    assert q.z == pytest.approx(0.0)
    assert q.is_unit()

    # Matrix
    m = np.eye(3)
    q = Quaternion.from_matrix(m)
    assert q.scalar == 1.0
    assert q.w == 1.0
    assert q.x == 0.0
    assert q.y == 0.0
    assert q.z == 0.0
    assert q.is_unit()

    # From copy/deepcopy
    q2 = copy(q)
    assert q2 == q
    assert q2.scalar == 1.0
    assert q2.is_unit()


def test_quaternion_class_properties_and_representation() -> None:
    q = Quaternion(1.0, 2.0, 3.0, 4.0)
    assert q.w == 1.0
    assert q.x == 2.0
    assert q.y == 3.0
    assert q.z == 4.0
    assert q.real == 1.0
    assert list(q.imaginary) == [2.0, 3.0, 4.0]
    # Norm: sqrt(1 + 4 + 9 + 16) = sqrt(30)
    assert q.norm == pytest.approx(5.477225575051661)

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

    # Multiplication (1+2i+3j+4k) * (2+3i+4j+5k) = -36+6i+12j+12k
    prod = q1 * q2
    assert (q1 * q2) != q1
    assert prod.w == pytest.approx(-36.0)
    assert prod.x == pytest.approx(6.0)
    assert prod.y == pytest.approx(12.0)
    assert prod.z == pytest.approx(12.0)

    # In-place operators
    q_inplace = Quaternion(q1.w, q1.x, q1.y, q1.z)
    q_inplace += q2
    assert q_inplace == q1 + q2

    # Conjugate & Inverse
    assert q1.conjugate.w == q1.w
    assert list(q1.conjugate.vector) == list(-q1.vector)
    assert q1.conjugate.x == pytest.approx(-2.0)
    assert q1.conjugate.y == pytest.approx(-3.0)
    assert q1.conjugate.z == pytest.approx(-4.0)
    q_inv = q1.inverse
    assert q_inv.w == pytest.approx(1.0 / 30.0)
    assert q_inv.x == pytest.approx(-2.0 / 30.0)
    assert q_inv.y == pytest.approx(-3.0 / 30.0)
    assert q_inv.z == pytest.approx(-4.0 / 30.0)
    identity = q1 * q_inv
    assert identity.q[0] == pytest.approx(1.0)
    assert identity.q[1] == pytest.approx(0.0, abs=1e-14)
    assert identity.q[2] == pytest.approx(0.0, abs=1e-14)
    assert identity.q[3] == pytest.approx(0.0, abs=1e-14)


def test_quaternion_class_math_functions() -> None:
    q = Quaternion.from_axis_angle([1.0, 0.0, 0.0], math.pi / 2)
    # Norm / Normalised
    assert q.norm == pytest.approx(1.0)
    assert q.w == pytest.approx(0.7071067811865476)
    assert q.x == pytest.approx(0.7071067811865475)
    assert q.y == pytest.approx(0.0)
    assert q.z == pytest.approx(0.0)
    assert q.is_unit()
    assert q.normalised.is_unit()

    # Exp / Log
    q_exp = Quaternion.exp(q)
    assert q_exp.w == pytest.approx(1.541863457045632)
    assert q_exp.x == pytest.approx(1.317538408779881)
    assert q_exp.y == pytest.approx(0.0)
    assert q_exp.z == pytest.approx(0.0)
    q_log = Quaternion.log(q_exp)
    assert q_log.q == pytest.approx(q.q)

    # Intrinsic Distance
    assert Quaternion.distance(q, q) == pytest.approx(0.0)
    q_rot = Quaternion.from_axis_angle([1.0, 0.0, 0.0], math.pi)
    assert Quaternion.distance(q, q_rot) > 0.0
    # Distance between pi/2 X rotation and pi X rotation = pi/4
    assert Quaternion.distance(q, q_rot) == pytest.approx(0.7853981633974483)

    # Random
    q_rand = Quaternion.random()
    assert q_rand.is_unit()


# ── additional quaternion coverage ──────────────────────────────────────


def test_quaternion_exp_map_variants() -> None:
    q = Quaternion.from_axis_angle([1.0, 0.0, 0.0], math.pi / 4)
    # q = [cos(pi/8), sin(pi/8), 0, 0]
    assert q.w == pytest.approx(0.9238795325112867)
    assert q.x == pytest.approx(0.3826834323650898)
    assert q.y == pytest.approx(0.0)
    assert q.z == pytest.approx(0.0)
    assert q.is_unit()

    eta = Quaternion(0, 0.1, 0, 0)
    result = Quaternion.exp_map(q, eta)
    assert isinstance(result, Quaternion)
    assert result.is_unit()
    assert result.w == pytest.approx(0.8810593889336525, rel=1e-6)
    assert result.x == pytest.approx(0.4730056635706723, rel=1e-6)
    assert result.y == pytest.approx(0.0, abs=1e-14)
    assert result.z == pytest.approx(0.0, abs=1e-14)

    sym = Quaternion.sym_exp_map(q, eta)
    assert isinstance(sym, Quaternion)
    assert sym.is_unit()
    assert sym.w == pytest.approx(0.8810593889336525, rel=1e-6)
    assert sym.x == pytest.approx(0.4730056635706723, rel=1e-6)
    assert sym.y == pytest.approx(0.0, abs=1e-14)
    assert sym.z == pytest.approx(0.0, abs=1e-14)


def test_quaternion_log_map_variants() -> None:
    q = Quaternion.from_axis_angle([0.0, 0.0, 1.0], math.pi / 3)
    p = Quaternion.from_axis_angle([0.0, 0.0, 1.0], math.pi / 2)

    # q: pi/3 around Z => [cos(pi/6), 0, 0, sin(pi/6)]
    assert q.w == pytest.approx(0.8660254037844387)
    assert q.z == pytest.approx(0.5)
    assert q.is_unit()
    # p: pi/2 around Z => [cos(pi/4), 0, 0, sin(pi/4)]
    assert p.w == pytest.approx(0.7071067811865476)
    assert p.z == pytest.approx(0.7071067811865475)
    assert p.is_unit()

    result = Quaternion.log_map(q, p)
    assert isinstance(result, Quaternion)
    # log_map of two Z-axis quaternions: pure vector Z with magnitude pi/12
    assert result.norm == pytest.approx(0.26179938779914935)
    assert result.z == pytest.approx(0.26179938779914935, abs=1e-12)
    assert result.w == pytest.approx(0.0, abs=1e-12)
    assert result.x == pytest.approx(0.0, abs=1e-12)
    assert result.y == pytest.approx(0.0, abs=1e-12)

    sym = Quaternion.sym_log_map(q, p)
    assert isinstance(sym, Quaternion)
    assert sym.norm == pytest.approx(0.26179938779914935)
    assert sym.z == pytest.approx(0.26179938779914935, abs=1e-12)


def test_quaternion_absolute_distance() -> None:
    q1 = Quaternion.from_axis_angle([1, 0, 0], 0)
    q2 = Quaternion.from_axis_angle([1, 0, 0], math.pi / 2)
    d = Quaternion.absolute_distance(q1, q2)
    assert d >= 0.0
    assert d == pytest.approx(0.7653668647301795)


def test_quaternion_sym_distance() -> None:
    q1 = Quaternion.from_axis_angle([0, 0, 1], 0)
    q2 = Quaternion.from_axis_angle([0, 0, 1], math.pi)
    d = Quaternion.sym_distance(q1, q2)
    assert d >= 0.0
    # Symmetric distance between identity and pi rotation = pi/2
    assert d == pytest.approx(1.5707963267948966)


def test_quaternion_integrate() -> None:
    q = Quaternion.from_axis_angle([0, 1, 0], 0)
    assert q.is_unit()
    assert q.w == pytest.approx(1.0)

    omega = [0.0, 1.0, 0.0]
    q.integrate(omega, 0.1)
    assert q.is_unit()
    # After 0.1 sec integration with rate [0, 1, 0], rotates by 0.1 rad around Y
    assert q.w == pytest.approx(math.cos(0.05))
    assert q.y == pytest.approx(math.sin(0.05))
    assert q.x == pytest.approx(0.0, abs=1e-14)
    assert q.z == pytest.approx(0.0, abs=1e-14)


def test_quaternion_dunders() -> None:
    q = Quaternion.from_axis_angle([1, 0, 0], math.pi / 4)
    assert q.is_unit()
    assert q.w == pytest.approx(0.9238795325112867)
    assert q.x == pytest.approx(0.3826834323650898)

    assert int(q) is not None  # type: ignore[arg-type]
    assert int(q) == 0
    assert float(q) is not None  # type: ignore[arg-type]
    assert float(q) == pytest.approx(0.9238795325112867)
    assert complex(q) is not None  # type: ignore[arg-type]
    assert complex(q) == pytest.approx(complex(0.9238795325112867, 0.3826834323650898))
    assert bool(q) is True  # type: ignore[arg-type]

    inv = q.conjugate
    assert inv.is_unit()
    assert inv.norm == pytest.approx(1.0)
    assert inv.w == pytest.approx(0.9238795325112867)
    assert inv.x == pytest.approx(-0.3826834323650898)
    assert inv.y == pytest.approx(0.0)
    assert inv.z == pytest.approx(0.0)


def test_quaternion_derivative() -> None:
    q = Quaternion.from_axis_angle([1, 0, 0], 0)
    assert q.w == pytest.approx(1.0)
    omega = [0.0, 0.0, 1.0]
    result = q.derivative(omega)
    assert isinstance(result, Quaternion)
    # 0.5 * identity * (0+1k) => [0, 0, 0, 0.5]
    assert result.w == pytest.approx(0.0)
    assert result.x == pytest.approx(0.0)
    assert result.y == pytest.approx(0.0)
    assert result.z == pytest.approx(0.5)


def test_quaternion_intermediates() -> None:
    q1 = Quaternion.from_axis_angle([1, 0, 0], 0)
    q2 = Quaternion.from_axis_angle([0, 0, 1], math.pi)
    intermediates = list(Quaternion.intermediates(q1, q2, 3))
    assert len(intermediates) == 3
    assert all(q.is_unit() for q in intermediates)

    # t=0.25: 45 deg around Z => [cos(22.5), 0, 0, sin(22.5)]
    q_0 = intermediates[0]
    assert q_0.w == pytest.approx(0.9238795325112867)
    assert q_0.z == pytest.approx(0.3826834323650898)
    assert q_0.x == pytest.approx(0.0)
    assert q_0.y == pytest.approx(0.0)

    # t=0.50: 90 deg around Z => [cos(45), 0, 0, sin(45)]
    q_1 = intermediates[1]
    assert q_1.w == pytest.approx(0.7071067811865476)
    assert q_1.z == pytest.approx(0.7071067811865475)
    assert q_1.x == pytest.approx(0.0)
    assert q_1.y == pytest.approx(0.0)

    # t=0.75: 135 deg around Z => [cos(67.5), 0, 0, sin(67.5)]
    q_2 = intermediates[2]
    assert q_2.w == pytest.approx(0.3826834323650898)
    assert q_2.z == pytest.approx(0.9238795325112867)
    assert q_2.x == pytest.approx(0.0)
    assert q_2.y == pytest.approx(0.0)


def test_quaternion_yaw_pitch_roll() -> None:
    q = Quaternion.from_axis_angle([0, 0, 1], math.pi / 4)
    assert q.is_unit()
    assert q.w == pytest.approx(0.9238795325112867)
    assert q.z == pytest.approx(0.3826834323650898)

    ypr = q.yaw_pitch_roll
    assert len(ypr) == 3
    # 45 deg around Z => yaw = pi/4, pitch = 0, roll = 0
    assert ypr[0] == pytest.approx(0.7853981633974484)  # yaw
    assert ypr[1] == pytest.approx(0.0)  # pitch
    assert ypr[2] == pytest.approx(0.0)  # roll


def test_quaternion_from_matrix_trace_branches() -> None:
    import numpy as np

    # Rotation around X by 90 degrees
    m = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=float)
    q = Quaternion.from_matrix(m)
    assert q.is_unit()
    assert q.w == pytest.approx(0.70710678, abs=1e-5)
    assert q.x == pytest.approx(0.70710678, abs=1e-5)
    assert q.y == pytest.approx(0.0, abs=1e-5)
    assert q.z == pytest.approx(0.0, abs=1e-5)

    # Rotation around Y by 180 degrees
    m2 = np.array([[-1, 0, 0], [0, 1, 0], [0, 0, -1]], dtype=float)
    q2 = Quaternion.from_matrix(m2)
    assert q2.is_unit()
    # 180 deg around Y => [cos(pi/2), 0, sin(pi/2), 0] = [0, 0, 1, 0]
    assert q2.w == pytest.approx(0.0, abs=1e-5)
    assert q2.x == pytest.approx(0.0, abs=1e-5)
    assert q2.y == pytest.approx(1.0, abs=1e-5)
    assert q2.z == pytest.approx(0.0, abs=1e-5)

    # Identity matrix
    m3 = np.eye(3)
    q3 = Quaternion.from_matrix(m3)
    assert q3.is_unit()
    assert q3.w == pytest.approx(1.0)
    assert q3.x == pytest.approx(0.0, abs=1e-5)
    assert q3.y == pytest.approx(0.0, abs=1e-5)
    assert q3.z == pytest.approx(0.0, abs=1e-5)


def test_quaternion_rotate_class_method() -> None:
    q = Quaternion.from_axis_angle([0, 0, 1], math.pi / 2)
    assert q.is_unit()
    assert q.w == pytest.approx(0.7071067811865476)
    assert q.z == pytest.approx(0.7071067811865475)

    v = [1.0, 0.0, 0.0]
    result = q.rotate(v)
    assert len(result) == 3
    # [1,0,0] rotated by 90 deg Z => [0, 1, 0]
    assert result[0] == pytest.approx(0.0, abs=1e-6)
    assert result[1] == pytest.approx(1.0, abs=1e-6)
    assert result[2] == pytest.approx(0.0, abs=1e-6)

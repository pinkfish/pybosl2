# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/quaternions.py
# FileSummary: Quaternion representations and mathematics for 3-D rotations.
# DocCategory: Math & geometry
# FileGroup: BOSL2

import math
from collections.abc import Sequence

import numpy as np


def quaternion(
    angle: float | None = None,
    axis: Sequence[float] | None = None,
    rpy: Sequence[float] | None = None,
    matrix: Sequence[Sequence[float]] | None = None,
) -> list[float]:
    """Constructs a 4-element quaternion [x, y, z, w].

    If no arguments are provided, returns the identity quaternion [0, 0, 0, 1].
    All angles are specified in degrees.

    Args:
        angle: The rotation angle in degrees. Requires `axis` to be provided.
        axis: The 3-D rotation axis vector. Requires `angle` to be provided.
        rpy: A sequence of three Euler angles [roll, pitch, yaw] in degrees.
        matrix: A 3x3 rotation matrix.

    Returns:
        A list of four floats representing the quaternion [x, y, z, w].

    Raises:
        ValueError: If arguments are mismatched or invalid.

    Example:
        >>> from pybosl2.quaternions import quaternion
        >>> q = quaternion(angle=90, axis=[0, 0, 1])
    """
    if angle is not None:
        if axis is None:
            raise ValueError("quaternion(): must specify axis when angle is given")
        axis_arr = np.asarray(axis, dtype=float)
        norm = np.linalg.norm(axis_arr)
        if norm < 1e-9:
            raise ValueError("quaternion(): axis vector cannot be zero-length")
        axis_normalized = axis_arr / norm
        rad = math.radians(angle) / 2.0
        s = math.sin(rad)
        c = math.cos(rad)
        return [float(axis_normalized[0] * s), float(axis_normalized[1] * s), float(axis_normalized[2] * s), float(c)]

    if rpy is not None:
        if len(rpy) != 3:
            raise ValueError("quaternion(): rpy must be a sequence of 3 angles")
        # Roll (X), Pitch (Y), Yaw (Z)
        r, p, y = [math.radians(a) / 2.0 for a in rpy]
        sr, cr = math.sin(r), math.cos(r)
        sp, cp = math.sin(p), math.cos(p)
        sy, cy = math.sin(y), math.cos(y)
        return [
            float(sr * cp * cy - cr * sp * sy),
            float(cr * sp * cy + sr * cp * sy),
            float(cr * cp * sy - sr * sp * cy),
            float(cr * cp * cy + sr * sp * sy),
        ]

    if matrix is not None:
        m = np.asarray(matrix, dtype=float)
        if m.shape != (3, 3):
            raise ValueError("quaternion(): matrix must be 3x3")
        trace = np.trace(m)
        if trace > 0:
            s = math.sqrt(trace + 1.0) * 2.0
            w = 0.25 * s
            x = (m[2, 1] - m[1, 2]) / s
            y = (m[0, 2] - m[2, 0]) / s
            z = (m[1, 0] - m[0, 1]) / s
        elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
            s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2.0
            w = (m[2, 1] - m[1, 2]) / s
            x = 0.25 * s
            y = (m[0, 1] + m[1, 0]) / s
            z = (m[0, 2] + m[2, 0]) / s
        elif m[1, 1] > m[2, 2]:
            s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2.0
            w = (m[0, 2] - m[2, 0]) / s
            x = (m[0, 1] + m[1, 0]) / s
            y = 0.25 * s
            z = (m[1, 2] + m[2, 1]) / s
        else:
            s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2.0
            w = (m[1, 0] - m[0, 1]) / s
            x = (m[0, 2] + m[2, 0]) / s
            y = (m[1, 2] + m[2, 1]) / s
            z = 0.25 * s
        return [float(x), float(y), float(z), float(w)]

    return [0.0, 0.0, 0.0, 1.0]


def quaternion_to_matrix(q: Sequence[float]) -> list[list[float]]:
    """Converts a quaternion to a 3x3 rotation matrix.

    Args:
        q: The quaternion [x, y, z, w].

    Returns:
        A 3x3 rotation matrix as a nested list of floats.

    Example:
        >>> from pybosl2.quaternions import quaternion_to_matrix
        >>> m = quaternion_to_matrix([0.0, 0.0, 0.70710678, 0.70710678])
    """
    x, y, z, w = q
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z

    return [
        [float(1.0 - 2.0 * (yy + zz)), float(2.0 * (xy - wz)), float(2.0 * (xz + wy))],
        [float(2.0 * (xy + wz)), float(1.0 - 2.0 * (xx + zz)), float(2.0 * (yz - wx))],
        [float(2.0 * (xz - wy)), float(2.0 * (yz + wx)), float(1.0 - 2.0 * (xx + yy))],
    ]


def quaternion_to_axis(q: Sequence[float]) -> tuple[float, list[float]]:
    """Converts a quaternion to its angle and rotation axis representation.

    All returned angles are in degrees.

    Args:
        q: The quaternion [x, y, z, w].

    Returns:
        A tuple (angle_degrees, axis_vector).
    """
    x, y, z, w = q
    # Normalize to avoid numerical instability
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm < 1e-9:
        return 0.0, [0.0, 0.0, 1.0]
    x, y, z, w = x / norm, y / norm, z / norm, w / norm

    angle = 2.0 * math.acos(max(-1.0, min(1.0, w)))
    s = math.sin(angle / 2.0)
    if abs(s) < 1e-9:
        return 0.0, [0.0, 0.0, 1.0]
    axis = [float(x / s), float(y / s), float(z / s)]
    return float(math.degrees(angle)), axis


def quaternion_mult(q1: Sequence[float], q2: Sequence[float]) -> list[float]:
    """Multiplies two quaternions (q1 * q2).

    Args:
        q1: The first quaternion [x, y, z, w].
        q2: The second quaternion [x, y, z, w].

    Returns:
        The resulting product quaternion [x, y, z, w].
    """
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2

    return [
        float(w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2),
        float(w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2),
        float(w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2),
        float(w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2),
    ]


def quaternion_slerp(q1: Sequence[float], q2: Sequence[float], t: float) -> list[float]:
    """Performs spherical linear interpolation (SLERP) between two quaternions.

    Args:
        q1: The starting quaternion [x, y, z, w].
        q2: The destination quaternion [x, y, z, w].
        t: The interpolation parameter, between 0.0 and 1.0.

    Returns:
        The interpolated quaternion [x, y, z, w].
    """
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2

    dot = x1 * x2 + y1 * y2 + z1 * z2 + w1 * w2

    # If the dot product is negative, the quaternions have opposite polarities
    # and slerp would take the long route. We invert one of them to fix this.
    if dot < 0.0:
        x2, y2, z2, w2 = -x2, -y2, -z2, -w2
        dot = -dot

    if dot > 0.9995:
        # Close enough to interpolate linearly
        x = x1 + t * (x2 - x1)
        y = y1 + t * (y2 - y1)
        z = z1 + t * (z2 - z1)
        w = w1 + t * (w2 - w1)
        norm = math.sqrt(x * x + y * y + z * z + w * w)
        return [float(x / norm), float(y / norm), float(z / norm), float(w / norm)]

    theta_0 = math.acos(dot)
    theta = theta_0 * t

    s0 = math.sin(theta_0 - theta)
    s1 = math.sin(theta)
    sin_theta_0 = math.sin(theta_0)

    x = (x1 * s0 + x2 * s1) / sin_theta_0
    y = (y1 * s0 + y2 * s1) / sin_theta_0
    z = (z1 * s0 + z2 * s1) / sin_theta_0
    w = (w1 * s0 + w2 * s1) / sin_theta_0

    return [float(x), float(y), float(z), float(w)]


def quaternion_rot(q: Sequence[float], v: Sequence[float]) -> list[float]:
    """Rotates a 3-D vector v by a quaternion q.

    Args:
        q: The quaternion [x, y, z, w].
        v: The 3-D vector to rotate [x, y, z].

    Returns:
        The rotated 3-D vector [x, y, z].
    """
    # Rotated vector: q * [v, 0] * conj(q)
    qv = [v[0], v[1], v[2], 0.0]
    q_conj = [-q[0], -q[1], -q[2], q[3]]
    res = quaternion_mult(quaternion_mult(q, qv), q_conj)
    return [float(res[0]), float(res[1]), float(res[2])]

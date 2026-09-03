# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/quaternions.py
# FileSummary: Class-based Quaternion representation and mathematics for 3-D rotations.
# DocCategory: Math & geometry
# FileGroup: BOSL2

"""Class-based Quaternion representation and mathematics for 3-D rotations."""

from __future__ import annotations

import math
import random
from copy import deepcopy
from math import acos, atan2, cos, exp, log, pi, sin, sqrt
from typing import TYPE_CHECKING, Any, Self, cast

import numpy as np

from pybosl2.exceptions import Bosl2ValueError

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence


class Quaternion:
    """Class to represent a 4-dimensional complex number or quaternion.

    Quaternion objects can be used generically as 4D numbers,
    or as unit quaternions to represent rotations in 3D space.

    Attributes:
        q: Quaternion 4-vector represented as a Numpy array

    """

    def __init__(self, w: float = 1.0, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
        """Initialise a new Quaternion object with explicit components."""
        self.q = np.array([float(w), float(x), float(y), float(z)])

    def __hash__(self) -> int:
        """Hash the quaternion components.

        Returns:
            The integer hash value.

        """
        return hash(tuple(self.q))

    @classmethod
    def from_array(cls, array: Sequence[float] | np.ndarray) -> Quaternion:
        """Create a Quaternion from a 4-element numeric sequence.

        Args:
            array: The four components as ``[x, y, z, w]``.

        """
        if len(array) != 4:
            raise Bosl2ValueError(f"from_array expects a 4-element sequence, got length {len(array)}")
        return cls(float(array[0]), float(array[1]), float(array[2]), float(array[3]))

    @classmethod
    def from_scalar_vector(cls, scalar: float, vector: Sequence[float] | np.ndarray) -> Quaternion:
        """Create a Quaternion from a scalar and a 3-element vector.

        Args:
            scalar: The scalar (real) part of the quaternion.
            vector: The vector part of the quaternion, ``[x, y, z]``.

        """
        if len(vector) != 3:
            raise Bosl2ValueError(f"from_scalar_vector expects a 3-element vector, got length {len(vector)}")
        return cls(float(scalar), float(vector[0]), float(vector[1]), float(vector[2]))

    @classmethod
    def from_real_imaginary(cls, real: float, imaginary: Sequence[float] | np.ndarray) -> Quaternion:
        """Create a Quaternion from real and 3-element imaginary parts.

        Args:
            real: The scalar part of the quaternion.
            imaginary: The vector part of the quaternion.

        """
        if len(imaginary) != 3:
            raise Bosl2ValueError(
                f"from_real_imaginary expects a 3-element imaginary vector, got length {len(imaginary)}"
            )
        return cls(float(real), float(imaginary[0]), float(imaginary[1]), float(imaginary[2]))

    @classmethod
    def from_matrix(cls, matrix: Any, rtol: float = 1e-05, atol: float = 1e-08) -> Quaternion:
        """Initialise from 3x3 or 4x4 matrix representation.

        Args:
            matrix: A 3x3 or 4x4 rotation matrix to convert from.
            rtol: Relative tolerance for the comparison.
            atol: Absolute tolerance for the comparison.

        """
        try:
            shape = matrix.shape
        except AttributeError as err:
            raise TypeError("Invalid matrix type: Input must be a 3x3 or 4x4 numpy array or matrix") from err

        if shape == (3, 3):
            r_mat = matrix
        elif shape == (4, 4):
            r_mat = matrix[:-1][:, :-1]
        else:
            raise Bosl2ValueError("Invalid matrix shape: Input must be a 3x3 or 4x4 numpy array or matrix")

        if not np.allclose(np.dot(r_mat, r_mat.conj().transpose()), np.eye(3), rtol=rtol, atol=atol):
            raise Bosl2ValueError("Matrix must be orthogonal, i.e. its transpose should be its inverse")
        if not np.isclose(np.linalg.det(r_mat), 1.0, rtol=rtol, atol=atol):
            raise Bosl2ValueError("Matrix must be special orthogonal i.e. its determinant must be +1.0")

        def trace_method(mat: Any) -> np.ndarray:
            m = mat.conj().transpose()
            if m[2, 2] < 0:
                if m[0, 0] > m[1, 1]:
                    t = 1.0 + m[0, 0] - m[1, 1] - m[2, 2]
                    q_lst = [m[1, 2] - m[2, 1], t, m[0, 1] + m[1, 0], m[2, 0] + m[0, 2]]
                else:
                    t = 1.0 - m[0, 0] + m[1, 1] - m[2, 2]
                    q_lst = [m[2, 0] - m[0, 2], m[0, 1] + m[1, 0], t, m[1, 2] + m[2, 1]]
            else:
                if m[0, 0] < -m[1, 1]:
                    t = 1.0 - m[0, 0] - m[1, 1] + m[2, 2]
                    q_lst = [m[0, 1] - m[1, 0], m[2, 0] + m[0, 2], m[1, 2] + m[2, 1], t]
                else:
                    t = 1.0 + m[0, 0] + m[1, 1] + m[2, 2]
                    q_lst = [t, m[1, 2] - m[2, 1], m[2, 0] - m[0, 2], m[0, 1] - m[1, 0]]

            q_arr = np.array(q_lst).astype("float64")
            q_arr *= 0.5 / sqrt(t)
            return q_arr

        return cls.from_array(trace_method(r_mat))

    @classmethod
    def from_axis_angle(cls, axis: Sequence[float] | np.ndarray, angle: float) -> Quaternion:
        """Create a Quaternion from rotation axis and angle (in radians).

        Args:
            axis: Axis to rotate about.
            angle: Rotation angle in degrees.

        """
        axis_arr = np.asarray(axis, dtype=float)
        mag_sq = np.dot(axis_arr, axis_arr)
        if mag_sq == 0.0:
            raise ZeroDivisionError("Provided rotation axis has no length")
        if abs(1.0 - mag_sq) > 1e-12:
            axis_arr = axis_arr / sqrt(mag_sq)
        theta = angle / 2.0
        r = cos(theta)
        i = axis_arr * sin(theta)

        return cls(r, i[0], i[1], i[2])

    @classmethod
    def random(cls) -> Quaternion:
        """Generate a random unit quaternion.

        Uniformly distributed across the rotation space.
        """
        r1 = random.uniform(0.0, 1.0)
        r2 = random.uniform(0.0, 1.0)
        r3 = random.uniform(0.0, 1.0)

        q1 = sqrt(1.0 - r1) * (sin(2 * pi * r2))
        q2 = sqrt(1.0 - r1) * (cos(2 * pi * r2))
        q3 = sqrt(r1) * (sin(2 * pi * r3))
        q4 = sqrt(r1) * (cos(2 * pi * r3))

        return cls(q1, q2, q3, q4)

    def __str__(self) -> str:
        """Informal string representation of the Quaternion object."""
        return f"{self.q[0]:.3f} {self.q[1]:+.3f}i {self.q[2]:+.3f}j {self.q[3]:+.3f}k"

    def __repr__(self) -> str:
        """Official string representation of the Quaternion object."""
        return f"Quaternion({float(self.q[0])!r}, {float(self.q[1])!r}, {float(self.q[2])!r}, {float(self.q[3])!r})"

    def __format__(self, formatstr: str) -> str:
        """Customisable string representation of the Quaternion object."""
        if formatstr.strip() == "":
            formatstr = "+.3f"

        string = "{:" + formatstr + "} " + "{:" + formatstr + "}i " + "{:" + formatstr + "}j " + "{:" + formatstr + "}k"
        return string.format(self.q[0], self.q[1], self.q[2], self.q[3])

    def __int__(self) -> int:
        """Convert to integer by considering only the scalar part."""
        return int(self.q[0])

    def __float__(self) -> float:
        """Convert to float by considering only the scalar part."""
        return float(self.q[0])

    def __complex__(self) -> complex:
        """Convert to complex by considering the scalar and first imaginary components."""
        return complex(self.q[0], self.q[1])

    def __bool__(self) -> bool:
        """Determine boolean value by comparing against zero."""
        return self != Quaternion(0.0)

    def __nonzero__(self) -> bool:
        """Determine truth value by comparing against zero."""
        return self != Quaternion(0.0)

    def __invert__(self) -> bool:
        """Invert truth value."""
        return self == Quaternion(0.0)

    def __eq__(self, other: object) -> bool:
        """Return true if each element matches within tolerance."""
        if isinstance(other, Quaternion):
            r_tol = 1.0e-13
            a_tol = 1.0e-14
            try:
                is_equal: bool = np.allclose(self.q, other.q, rtol=r_tol, atol=a_tol)
            except AttributeError as err:
                raise AttributeError(
                    "Error in internal quaternion representation means it cannot be compared like a numpy array."
                ) from err
            return is_equal
        try:
            if isinstance(other, (int, float)):
                return self.__eq__(Quaternion(float(other)))
            if isinstance(other, (list, tuple, np.ndarray)):
                return self.__eq__(Quaternion.from_array(other))
            return False
        except (TypeError, ValueError):
            return False

    def __neg__(self) -> Quaternion:
        """Negate the quaternion components."""
        return self.__class__.from_array(-self.q)

    def __abs__(self) -> float:
        """Return the norm of the quaternion."""
        return self.norm

    def _cast_other(self, other: Any) -> Quaternion:
        """Cast other types to Quaternion."""
        if isinstance(other, Quaternion):
            return other
        if isinstance(other, (int, float)):
            return Quaternion(float(other))
        return Quaternion.from_array(other)

    def __add__(self, other: Any) -> Quaternion:
        """Add another quaternion or scalar."""
        other_q = self._cast_other(other)
        return self.__class__.from_array(self.q + other_q.q)

    def __iadd__(self, other: Any) -> Self:
        """Add in-place."""
        return cast("Self", self + other)

    def __radd__(self, other: Any) -> Quaternion:
        """Right add."""
        return cast("Quaternion", self + other)

    def __sub__(self, other: Any) -> Quaternion:
        """Subtract another quaternion or scalar."""
        return self + (-self._cast_other(other))

    def __isub__(self, other: Any) -> Self:
        """Subtract in-place."""
        return cast("Self", self + (-self._cast_other(other)))

    def __rsub__(self, other: Any) -> Quaternion:
        """Right subtract."""
        return self._cast_other(other) - self

    def __mul__(self, other: Any) -> Quaternion:
        """Multiply by another quaternion or scalar."""
        other_q = self._cast_other(other)
        return self.__class__.from_array(np.dot(self._q_matrix(), other_q.q))

    def __imul__(self, other: Any) -> Self:
        """Multiply in-place."""
        return cast("Self", self * other)

    def __rmul__(self, other: Any) -> Quaternion:
        """Right multiply."""
        return self._cast_other(other) * self

    def __matmul__(self, other: Any) -> Any:
        """Compute the matrix multiplication or dot product."""
        other_q = self._cast_other(other)
        return self.q.__matmul__(other_q.q)

    def __imatmul__(self, other: Any) -> Any:
        """Compute in-place matrix multiplication."""
        return self.__matmul__(other)

    def __rmatmul__(self, other: Any) -> Any:
        """Compute right matrix multiplication."""
        return self._cast_other(other).__matmul__(self)

    def __div__(self, other: Any) -> Quaternion:
        """Divide by another quaternion or scalar."""
        other_q = self._cast_other(other)
        if other_q == self.__class__(0.0):
            raise ZeroDivisionError("Quaternion divisor must be non-zero")
        return self * other_q.inverse

    def __idiv__(self, other: Any) -> Quaternion:
        """Divide in-place."""
        return self.__div__(other)

    def __rdiv__(self, other: Any) -> Quaternion:
        """Right divide."""
        return self._cast_other(other) * self.inverse

    def __truediv__(self, other: Any) -> Quaternion:
        """Return the result of true division."""
        return self.__div__(other)

    def __itruediv__(self, other: Any) -> Self:
        """In-place true division."""
        return cast("Self", self.__idiv__(other))

    def __rtruediv__(self, other: Any) -> Quaternion:
        """Right true division."""
        return self.__rdiv__(other)

    def __pow__(self, exponent: Any) -> Quaternion:
        """Raise the quaternion to a scalar exponent."""
        exponent_val = float(exponent)
        norm_val = self.norm
        if norm_val > 0.0:
            try:
                n, theta = self.polar_decomposition
            except ZeroDivisionError:
                return Quaternion(self.scalar**exponent_val)
            return cast(
                "Quaternion",
                (self.norm**exponent_val)
                * Quaternion.from_scalar_vector(cos(exponent_val * theta), (n * sin(exponent_val * theta))),
            )
        return Quaternion.from_array(self.q)

    def __ipow__(self, other: Any) -> Self:
        """Power in-place."""
        return cast("Self", self**other)

    def __rpow__(self, other: Any) -> Quaternion:
        """Right power."""
        return cast("Quaternion", other ** float(self))

    def _vector_conjugate(self) -> np.ndarray:
        """Calculate internal vector conjugate."""
        return np.hstack((self.q[0], -self.q[1:4]))

    def _sum_of_squares(self) -> float:
        """Sum of squares of all quaternion elements."""
        val: float = np.dot(self.q, self.q)
        return val

    @property
    def conjugate(self) -> Quaternion:
        """Quaternion conjugate clone."""
        return self.__class__.from_scalar_vector(self.scalar, -self.vector)

    @property
    def inverse(self) -> Quaternion:
        """Inverse of the quaternion object."""
        ss = self._sum_of_squares()
        if ss > 0:
            return self.__class__.from_array(self._vector_conjugate() / ss)
        else:
            raise ZeroDivisionError("a zero quaternion (0 + 0i + 0j + 0k) cannot be inverted")

    @property
    def norm(self) -> float:
        """L2 norm of the quaternion 4-vector."""
        mag_squared = self._sum_of_squares()
        return sqrt(mag_squared)

    @property
    def magnitude(self) -> float:
        """Alias for norm."""
        return self.norm

    def _normalise(self) -> None:
        """In-place normalisation."""
        if not self.is_unit():
            n = self.norm
            if n > 0:
                self.q = self.q / n

    def _fast_normalise(self) -> None:
        """Fast normalisation approximation."""
        if not self.is_unit():
            mag_squared = np.dot(self.q, self.q)
            if mag_squared == 0:
                return
            mag = (1.0 + mag_squared) / 2.0 if abs(1.0 - mag_squared) < 2.107342e-08 else sqrt(mag_squared)
            self.q = self.q / mag

    @property
    def normalised(self) -> Quaternion:
        """Return a unit normalised copy."""
        q = Quaternion(self.w, self.x, self.y, self.z)
        q._normalise()
        return q

    @property
    def polar_unit_vector(self) -> np.ndarray:
        """Vector part normalised to unit length."""
        vector_length = np.linalg.norm(self.vector)
        if vector_length <= 0.0:
            raise ZeroDivisionError("Quaternion is pure real and does not have a unique unit vector")
        return cast("np.ndarray", self.vector / vector_length)

    @property
    def polar_angle(self) -> float:
        """Return polar angle of the quaternion."""
        return acos(self.scalar / self.norm)

    @property
    def polar_decomposition(self) -> tuple[np.ndarray, float]:
        """Polar decomposition of the quaternion."""
        return self.polar_unit_vector, self.polar_angle

    @property
    def unit(self) -> Quaternion:
        """Alias for normalised."""
        return self.normalised

    def is_unit(self, tolerance: float = 1e-14) -> bool:
        """Check if quaternion is of unit length.

        Args:
            tolerance: How far from unit length a quaternion may be and still count as normalised.

        """
        return abs(1.0 - self._sum_of_squares()) < tolerance

    def _q_matrix(self) -> np.ndarray:
        """Matrix representation for left multiplication."""
        return np.array(
            [
                [self.q[0], -self.q[1], -self.q[2], -self.q[3]],
                [self.q[1], self.q[0], -self.q[3], self.q[2]],
                [self.q[2], self.q[3], self.q[0], -self.q[1]],
                [self.q[3], -self.q[2], self.q[1], self.q[0]],
            ]
        )

    def _q_bar_matrix(self) -> np.ndarray:
        """Matrix representation for right multiplication."""
        return np.array(
            [
                [self.q[0], -self.q[1], -self.q[2], -self.q[3]],
                [self.q[1], self.q[0], self.q[3], -self.q[2]],
                [self.q[2], -self.q[3], self.q[0], self.q[1]],
                [self.q[3], self.q[2], -self.q[1], self.q[0]],
            ]
        )

    def _rotate_quaternion(self, q: Quaternion) -> Quaternion:
        """Rotate a quaternion vector representation."""
        unit = self.normalised  # read-only: rotating a vector does not renormalise this quaternion
        return unit * q * unit.conjugate

    def rotate(self, vector: Any) -> Any:
        """Rotate a 3D vector by the quaternion.

        Args:
            vector: The vector part of the quaternion, ``[x, y, z]``.

        """
        if isinstance(vector, Quaternion):
            return self._rotate_quaternion(vector)
        q = Quaternion.from_scalar_vector(0.0, vector)
        a = self._rotate_quaternion(q).vector
        if isinstance(vector, list):
            return list(a)
        elif isinstance(vector, tuple):
            return tuple(a)
        else:
            return a

    @classmethod
    def exp(cls, q: Quaternion) -> Quaternion:
        """Quaternion Exponential.

        Args:
            q: The quaternion to operate on.

        """
        tolerance = 1e-17
        v_norm = np.linalg.norm(q.vector)
        vec = q.vector
        if v_norm > tolerance:
            vec = vec / v_norm
        magnitude = exp(q.scalar)
        return Quaternion.from_scalar_vector(magnitude * cos(v_norm), magnitude * sin(v_norm) * vec)

    @classmethod
    def log(cls, q: Quaternion) -> Quaternion:
        """Quaternion Logarithm.

        Args:
            q: The quaternion to operate on.

        """
        v_norm = np.linalg.norm(q.vector)
        q_norm = q.norm
        tolerance = 1e-17
        if q_norm < tolerance:
            return Quaternion.from_scalar_vector(-float("inf"), float("nan") * q.vector)
        if v_norm < tolerance:
            return Quaternion.from_scalar_vector(log(q_norm), [0.0, 0.0, 0.0])
        vec = q.vector / v_norm
        return Quaternion.from_scalar_vector(log(q_norm), acos(q.scalar / q_norm) * vec)

    @classmethod
    def exp_map(cls, q: Quaternion, eta: Quaternion) -> Quaternion:
        """Quaternion exponential map.

        Args:
            q: The quaternion to operate on.
            eta: Small threshold below which two quaternions count as aligned and slerp falls back to a straight lerp.

        """
        return q * Quaternion.exp(eta)

    @classmethod
    def sym_exp_map(cls, q: Quaternion, eta: Quaternion) -> Quaternion:
        """Symmetrized exponential map.

        Args:
            q: The quaternion to operate on.
            eta: Small threshold below which two quaternions count as aligned and slerp falls back to a straight lerp.

        """
        sqrt_q = q**0.5
        return sqrt_q * Quaternion.exp(eta) * sqrt_q

    @classmethod
    def log_map(cls, q: Quaternion, p: Quaternion) -> Quaternion:
        """Quaternion logarithm map.

        Args:
            q: The quaternion to operate on.
            p: The point or vector to rotate.

        """
        return Quaternion.log(q.inverse * p)

    @classmethod
    def sym_log_map(cls, q: Quaternion, p: Quaternion) -> Quaternion:
        """Symmetrized logarithm map.

        Args:
            q: The quaternion to operate on.
            p: The point or vector to rotate.

        """
        inv_sqrt_q = q ** (-0.5)
        return Quaternion.log(inv_sqrt_q * p * inv_sqrt_q)

    @classmethod
    def absolute_distance(cls, q0: Quaternion, q1: Quaternion) -> float:
        """Quaternion absolute distance.

        Args:
            q0: The first quaternion.
            q1: The second quaternion.

        """
        q0_minus_q1 = q0 - q1
        q0_plus_q1 = q0 + q1
        d_minus = q0_minus_q1.norm
        d_plus = q0_plus_q1.norm
        return d_minus if d_minus < d_plus else d_plus

    @classmethod
    def distance(cls, q0: Quaternion, q1: Quaternion) -> float:
        """Quaternion intrinsic distance.

        Args:
            q0: The first quaternion.
            q1: The second quaternion.

        """
        q = Quaternion.log_map(q0, q1)
        return q.norm

    @classmethod
    def sym_distance(cls, q0: Quaternion, q1: Quaternion) -> float:
        """Symmetrized geodesic distance.

        Args:
            q0: The first quaternion.
            q1: The second quaternion.

        """
        q = Quaternion.sym_log_map(q0, q1)
        return q.norm

    @classmethod
    def slerp(cls, q0: Quaternion, q1: Quaternion, amount: float = 0.5) -> Quaternion:
        """Spherical Linear Interpolation between unit quaternions.

        The endpoints are normalised (and one may be negated, to take the short way round) on
        copies: interpolating between two rotations does not change either of them.

        Args:
            q0: The first quaternion.
            q1: The second quaternion.
            amount: How far to rotate, as a fraction of the full angle.

        """
        start = q0.normalised
        end = q1.normalised
        amount = np.clip(amount, 0, 1)

        dot = np.dot(start.q, end.q)

        if dot < 0.0:
            start = -start
            dot = -dot

        if dot > 0.9995:
            qr = Quaternion.from_array(start.q + amount * (end.q - start.q))
            qr._fast_normalise()
            return qr

        theta_0 = np.arccos(dot)
        sin_theta_0 = np.sin(theta_0)

        theta = theta_0 * amount
        sin_theta = np.sin(theta)

        s0 = np.cos(theta) - dot * sin_theta / sin_theta_0
        s1 = sin_theta / sin_theta_0
        qr = Quaternion.from_array((s0 * start.q) + (s1 * end.q))
        qr._fast_normalise()
        return qr

    @classmethod
    def intermediates(
        cls, q0: Quaternion, q1: Quaternion, n: int, include_endpoints: bool = False
    ) -> Iterator[Quaternion]:
        """Generate iterable sequence of intermediates.

        Args:
            q0: The first quaternion.
            q1: The second quaternion.
            n: How many intermediate quaternions to produce.
            include_endpoints: Include the two ends in the returned sequence.

        """
        step_size = 1.0 / (n + 1)
        steps = [i * step_size for i in range(n + 2)] if include_endpoints else [i * step_size for i in range(1, n + 1)]
        for step in steps:
            yield cls.slerp(q0, q1, step)

    def derivative(self, rate: Any) -> Quaternion:
        """Instantaneous quaternion derivative.

        Args:
            rate: Angular rate in degrees per unit time.

        """
        rate_arr = self._cast_other(rate).vector if isinstance(rate, Quaternion) else np.asarray(rate, dtype=float)
        return 0.5 * self * Quaternion.from_scalar_vector(0.0, rate_arr)

    def integrate(self, rate: Any, timestep: float) -> None:
        """Advance time varying quaternion in-place.

        Args:
            rate: Angular rate in degrees per unit time.
            timestep: Length of one step, in the same units as *rate*.

        """
        self._fast_normalise()
        rate_arr = self._cast_other(rate).vector if isinstance(rate, Quaternion) else np.asarray(rate, dtype=float)

        rotation_vector = rate_arr * timestep
        rotation_norm = float(np.linalg.norm(rotation_vector))
        if rotation_norm > 0:
            axis = rotation_vector / rotation_norm
            angle = rotation_norm
            q2 = Quaternion.from_axis_angle(axis, float(angle))
            self.q = (self * q2).q
            self._fast_normalise()

    @property
    def rotation_matrix(self) -> np.ndarray:
        """Get 3x3 rotation matrix representation."""
        unit = self.normalised
        product_matrix = np.dot(unit._q_matrix(), unit._q_bar_matrix().conj().transpose())
        return cast("np.ndarray", product_matrix[1:][:, 1:])

    @property
    def transformation_matrix(self) -> np.ndarray:
        """Get 4x4 homogeneous transformation matrix."""
        t = np.array([[0.0], [0.0], [0.0]])
        rt_mat = np.hstack([self.rotation_matrix, t])
        return np.vstack([rt_mat, np.array([0.0, 0.0, 0.0, 1.0])])

    @property
    def yaw_pitch_roll(self) -> tuple[float, float, float]:
        """Get Yaw, Pitch, Roll angles (in radians)."""
        q = self.normalised.q
        yaw = np.arctan2(2 * (q[0] * q[3] - q[1] * q[2]), 1 - 2 * (q[2] ** 2 + q[3] ** 2))
        pitch = np.arcsin(2 * (q[0] * q[2] + q[3] * q[1]))
        roll = np.arctan2(2 * (q[0] * q[1] - q[2] * q[3]), 1 - 2 * (q[1] ** 2 + q[2] ** 2))
        return yaw, pitch, roll

    def _wrap_angle(self, theta: float) -> float:
        """Wrap angle to [-pi, pi]."""
        result = ((theta + pi) % (2 * pi)) - pi
        if result == -pi:
            result = pi
        return result

    def get_axis(self, undefined: np.ndarray | None = None) -> np.ndarray:
        """Get the rotation axis.

        Args:
            undefined: What to return when the rotation is undefined, as it is for a zero vector.

        """
        undef = np.zeros(3) if undefined is None else undefined
        tolerance = 1e-17
        vector = self.normalised.vector
        norm = np.linalg.norm(vector)
        if norm < tolerance:
            return undef
        return cast("np.ndarray", vector / norm)

    @property
    def axis(self) -> np.ndarray:
        """Get axis of rotation."""
        return self.get_axis()

    @property
    def angle(self) -> float:
        """Get angle of rotation in radians."""
        unit = self.normalised
        norm = np.linalg.norm(unit.vector)
        return self._wrap_angle(2.0 * atan2(norm, unit.scalar))

    @property
    def degrees(self) -> float:
        """Get angle of rotation in degrees."""
        val: float | None = self.to_degrees(self.angle)
        return 0.0 if val is None else val

    @property
    def radians(self) -> float:
        """Get angle of rotation in radians."""
        return self.angle

    @property
    def scalar(self) -> float:
        """Get scalar component."""
        val: float = self.q[0]
        return val

    @property
    def vector(self) -> np.ndarray:
        """Get vector component."""
        return self.q[1:4]

    @property
    def real(self) -> float:
        """Get real component."""
        return self.scalar

    @property
    def imaginary(self) -> np.ndarray:
        """Get imaginary component."""
        return self.vector

    @property
    def w(self) -> float:
        """Get w element."""
        val: float = self.q[0]
        return val

    @property
    def x(self) -> float:
        """Get x element."""
        val: float = self.q[1]
        return val

    @property
    def y(self) -> float:
        """Get y element."""
        val: float = self.q[2]
        return val

    @property
    def z(self) -> float:
        """Get z element."""
        val: float = self.q[3]
        return val

    @property
    def elements(self) -> np.ndarray:
        """Get all elements array."""
        return self.q

    def __getitem__(self, index: int) -> float:
        """Get element by index."""
        val: float = self.q[int(index)]
        return val

    def __setitem__(self, index: int, value: float) -> None:
        """Set element by index."""
        self.q[int(index)] = float(value)

    def __copy__(self) -> Quaternion:
        """Copy instance."""
        return self.__class__.from_array(self.q)

    def __deepcopy__(self, memo: Any) -> Quaternion:
        """Deep copy instance."""
        return self.__class__.from_array(deepcopy(self.q, memo))

    @staticmethod
    def to_degrees(angle_rad: float | None) -> float | None:
        """Convert radians to degrees.

        Args:
            angle_rad: Rotation angle in radians.

        """
        if angle_rad is not None:
            return float(angle_rad) / pi * 180.0
        return None

    @staticmethod
    def to_radians(angle_deg: float | None) -> float | None:
        """Convert degrees to radians.

        Args:
            angle_deg: Rotation angle in degrees.

        """
        if angle_deg is not None:
            return float(angle_deg) / 180.0 * pi
        return None


# ---------------------------------------------------------------------------
# Compatibility Wrapper Functions for Existing pybosl2 codebase
# ---------------------------------------------------------------------------


def quaternion(
    angle: float | None = None,
    axis: Sequence[float] | None = None,
    rpy: Sequence[float] | None = None,
    matrix: Sequence[Sequence[float]] | None = None,
) -> list[float]:
    """Construct a 4-element quaternion [x, y, z, w].

    If no arguments are provided, returns the identity quaternion [0, 0, 0, 1].
    All angles are specified in degrees.

    Args:
        angle: Rotation angle in degrees.
        axis: Axis to rotate about.
        rpy: Roll, pitch and yaw in degrees.
        matrix: A 3x3 or 4x4 rotation matrix to convert from.

    """
    if angle is not None:
        if axis is None:
            raise Bosl2ValueError("quaternion(): must specify axis when angle is given")
        axis_arr = np.asarray(axis, dtype=float)
        if np.linalg.norm(axis_arr) < 1e-9:
            raise Bosl2ValueError("quaternion(): axis vector cannot be zero-length")
        # Convert degrees to radians for from_axis_angle
        rad = math.radians(angle)
        q = Quaternion.from_axis_angle(axis_arr, rad)
    elif rpy is not None:
        if len(rpy) != 3:
            raise Bosl2ValueError("quaternion(): rpy must be a sequence of 3 angles")
        r, p, y = [math.radians(a) / 2.0 for a in rpy]
        sr, cr = math.sin(r), math.cos(r)
        sp, cp = math.sin(p), math.cos(p)
        sy, cy = math.sin(y), math.cos(y)
        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y_val = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy
        return [float(x), float(y_val), float(z), float(w)]
    elif matrix is not None:
        q = Quaternion.from_matrix(np.array(matrix))
    else:
        q = Quaternion()

    return [float(q.q[1]), float(q.q[2]), float(q.q[3]), float(q.q[0])]


def quaternion_to_matrix(q: Sequence[float]) -> list[list[float]]:
    """Convert a quaternion to a 3x3 rotation matrix.

    Args:
        q: The quaternion to operate on.

    """
    quat = Quaternion.from_array([q[3], q[0], q[1], q[2]])
    return quat.rotation_matrix.tolist()  # type: ignore[no-any-return]


def quaternion_to_axis(q: Sequence[float]) -> tuple[float, list[float]]:
    """Convert a quaternion to its angle and rotation axis representation.

    Args:
        q: The quaternion to operate on.

    """
    quat = Quaternion.from_array([q[3], q[0], q[1], q[2]])
    return float(quat.degrees), quat.axis.tolist()


def quaternion_mult(q1: Sequence[float], q2: Sequence[float]) -> list[float]:
    """Multiplies two quaternions (q1 * q2).

    Args:
        q1: The first quaternion.
        q2: The second quaternion.

    """
    quat1 = Quaternion.from_array([q1[3], q1[0], q1[1], q1[2]])
    quat2 = Quaternion.from_array([q2[3], q2[0], q2[1], q2[2]])
    res = quat1 * quat2
    return [float(res.q[1]), float(res.q[2]), float(res.q[3]), float(res.q[0])]


def quaternion_slerp(q1: Sequence[float], q2: Sequence[float], t: float) -> list[float]:
    """Perform spherical linear interpolation (SLERP) between two quaternions.

    Args:
        q1: The first quaternion.
        q2: The second quaternion.
        t: Interpolation parameter from 0 (*q1*) to 1 (*q2*).

    """
    quat1 = Quaternion.from_array([q1[3], q1[0], q1[1], q1[2]])
    quat2 = Quaternion.from_array([q2[3], q2[0], q2[1], q2[2]])
    res = Quaternion.slerp(quat1, quat2, t)
    return [float(res.q[1]), float(res.q[2]), float(res.q[3]), float(res.q[0])]


def quaternion_rot(q: Sequence[float], v: Sequence[float]) -> list[float]:
    """Rotates a 3-D vector v by a quaternion q.

    Args:
        q: The quaternion to operate on.
        v: The vector part, or the point to rotate.

    """
    quat = Quaternion.from_array([q[3], q[0], q[1], q[2]])
    res: list[float] = quat.rotate(list(v))
    return res

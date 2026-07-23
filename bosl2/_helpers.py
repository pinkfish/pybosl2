# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/_helpers.py
#    Shared internal helper functions used across the bosl2 package. These are
#    consolidated from multiple files that each had their own private copy.
#    Not part of the public API.
#
# FileSummary: Internal helper functions shared across the bosl2 package.
# FileGroup: BOSL2

from functools import reduce
import operator

import numpy as np


# ---------------------------------------------------------------------------
# Scalar/number predicates
# ---------------------------------------------------------------------------


def is_num(value) -> bool:
    """True if *value* is a numeric scalar (int, float, or numpy numeric), excluding bool."""
    return isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool)


# ---------------------------------------------------------------------------
# 3-D point/vector padding
# ---------------------------------------------------------------------------


def vec3(vector):
    """Pad *vector* to a list of 3: if 2-D, set z=0; if numeric, repeat to 3.

    Unlike :func:`scalar_vec3`, a scalar becomes ``[vector, vector, vector]`` (matching ``np.asarray``
    broadcast semantics in places where all three coordinates are the same).
    """
    array = np.asarray(vector, dtype=float)
    if array.ndim == 0:
        return np.array([float(vector), float(vector), float(vector)])
    if array.shape[0] == 2:
        return np.array([array[0], array[1], 0.0])
    return np.array([float(array[0]), float(array[1]), float(array[2])])


def scalar_vec3(value, fill: float = 0.0) -> np.ndarray:
    """A scalar becomes ``[value, fill, fill]``; a vector is padded to length 3.

    BOSL2's ``scalar_vec3()`` -- used for direction vectors where a single value
    fills a single axis."""
    if is_num(value):
        return np.array([float(value), float(fill), float(fill)])
    arr = list(value)
    return np.array([float(arr[i]) if i < len(arr) else float(fill) for i in range(3)])


# ---------------------------------------------------------------------------
# Vector normalization
# ---------------------------------------------------------------------------


def unit(vector) -> np.ndarray:
    """Normalize *vector* to unit length.  Returns zero vector if zero-length (matching
    ``bosl2/transforms.py``'s ``_unit()`` convention)."""
    arr = np.asarray(vector, dtype=float)
    norm = float(np.linalg.norm(arr))
    return arr / norm if norm else arr


# ---------------------------------------------------------------------------
# 4x4 transformation matrix factories
# ---------------------------------------------------------------------------


def zrot4(angle_degrees: float) -> np.ndarray:
    """4x4 rotation matrix of *angle_degrees* degrees about the Z axis."""
    from bosl2.transforms import axis_angle_matrix
    matrix = np.eye(4)
    matrix[:3, :3] = axis_angle_matrix(angle_degrees, [0, 0, 1])
    return matrix


def rot_from_to4(source, target) -> np.ndarray:
    """4x4 rotation matrix rotating direction *source* onto direction *target*."""
    from bosl2.transforms import rot_from_to, axis_angle_matrix
    angle, axis = rot_from_to(source, target)
    matrix = np.eye(4)
    matrix[:3, :3] = axis_angle_matrix(angle, axis)
    return matrix


def translate4(offset) -> np.ndarray:
    """4x4 translation matrix. *offset* is a 3-D point (or 2-D with z=0)."""
    point = np.asarray(offset, dtype=float).ravel()
    matrix = np.eye(4)
    matrix[:3, 3] = [float(point[0]), float(point[1]), float(point[2]) if len(point) > 2 else 0.0]
    return matrix


def frame_map4_yz(y_axis, z_axis):
    """Rotation whose local +Y and +Z axes point along *y_axis* and *z_axis* (BOSL2 frame_map(y=, z=)).

    Different from ``frame_map4_xz``: this version takes Y and Z axes (used by
    :mod:`bosl2.miscellaneous`'s path_extrude2d)."""
    y_unit, z_unit = unit(np.asarray(y_axis, dtype=float)), unit(np.asarray(z_axis, dtype=float))
    x_unit = unit(np.cross(y_unit, z_unit))
    y_unit = unit(np.cross(z_unit, x_unit))
    matrix = np.eye(4)
    matrix[:3, 0], matrix[:3, 1], matrix[:3, 2] = x_unit, y_unit, z_unit
    return matrix


# ---------------------------------------------------------------------------
# CSG union helpers
# ---------------------------------------------------------------------------


def union(shapes):
    """Boolean union of an iterable of native PythonSCAD shapes (``reduce(operator.or_, shapes)``)."""
    return reduce(operator.or_, shapes)


# ---------------------------------------------------------------------------
# Bosl2Solid unwrapping
# ---------------------------------------------------------------------------


def unwrap(obj):
    """Extract the native shape from a Bosl2Solid wrapper, or return *obj* as-is."""
    from bosl2.shapes3d import Bosl2Solid
    return obj.shape if isinstance(obj, Bosl2Solid) else obj



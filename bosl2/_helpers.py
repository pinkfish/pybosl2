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


def is_num(x) -> bool:
    """True if *x* is a numeric scalar (int, float, or numpy numeric), excluding bool."""
    return isinstance(x, (int, float, np.integer, np.floating)) and not isinstance(x, bool)


# ---------------------------------------------------------------------------
# 3-D point/vector padding
# ---------------------------------------------------------------------------


def vec3(v):
    """Pad *v* to a list of 3: if 2-D, set z=0; if numeric, repeat to 3.

    Unlike :func:`scalar_vec3`, a scalar becomes ``[v, v, v]`` (matching ``np.asarray``
    broadcast semantics in places where all three coordinates are the same).
    """
    a = np.asarray(v, dtype=float)
    if a.ndim == 0:
        return np.array([float(v), float(v), float(v)])
    if a.shape[0] == 2:
        return np.array([a[0], a[1], 0.0])
    return np.array([float(a[0]), float(a[1]), float(a[2])])


def scalar_vec3(v, fill: float = 0.0) -> np.ndarray:
    """A scalar becomes ``[v, fill, fill]``; a vector is padded to length 3.

    BOSL2's ``scalar_vec3()`` -- used for direction vectors where a single value
    fills a single axis."""
    if is_num(v):
        return np.array([float(v), float(fill), float(fill)])
    arr = list(v)
    return np.array([float(arr[i]) if i < len(arr) else float(fill) for i in range(3)])


# ---------------------------------------------------------------------------
# Vector normalization
# ---------------------------------------------------------------------------


def unit(v) -> np.ndarray:
    """Normalize *v* to unit length.  Returns zero vector if zero-length (matching
    ``bosl2/transforms.py``'s ``_unit()`` convention)."""
    arr = np.asarray(v, dtype=float)
    n = float(np.linalg.norm(arr))
    return arr / n if n else arr


# ---------------------------------------------------------------------------
# 4x4 transformation matrix factories
# ---------------------------------------------------------------------------


def zrot4(deg: float) -> np.ndarray:
    """4x4 rotation matrix of *deg* degrees about the Z axis."""
    from bosl2.transforms import axis_angle_matrix
    m = np.eye(4)
    m[:3, :3] = axis_angle_matrix(deg, [0, 0, 1])
    return m


def rot_from_to4(a, b) -> np.ndarray:
    """4x4 rotation matrix rotating direction *a* onto direction *b*."""
    from bosl2.transforms import rot_from_to, axis_angle_matrix
    ang, axis = rot_from_to(a, b)
    m = np.eye(4)
    m[:3, :3] = axis_angle_matrix(ang, axis)
    return m


def translate4(v) -> np.ndarray:
    """4x4 translation matrix. *v* is a 3-D point (or 2-D with z=0)."""
    p = np.asarray(v, dtype=float).ravel()
    m = np.eye(4)
    m[:3, 3] = [float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0]
    return m


def frame_map4_yz(y, z):
    """Rotation whose local +Y and +Z axes point along *y* and *z* (BOSL2 frame_map(y=, z=)).

    Different from ``frame_map4_xz``: this version takes Y and Z axes (used by
    :mod:`bosl2.miscellaneous`'s path_extrude2d)."""
    yv, zv = unit(np.asarray(y, dtype=float)), unit(np.asarray(z, dtype=float))
    xv = unit(np.cross(yv, zv))
    yv = unit(np.cross(zv, xv))
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2] = xv, yv, zv
    return m


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


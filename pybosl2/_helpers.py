# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/_helpers.py
#    Shared internal helper functions used across the pybosl2 package. These are
#    consolidated from multiple files that each had their own private copy.
#    Not part of the public API.
#
# FileSummary: Internal helper functions shared across the pybosl2 package.
# FileGroup: BOSL2

from __future__ import annotations

import math
import operator
from enum import Enum
from functools import reduce
from typing import TYPE_CHECKING, Any

from pybosl2._edges_lang import Anchor
from pybosl2.defaults import resolve_facets

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pybosl2.shapes2d import Bosl2Shape2D
    from pybosl2.shapes3d import Bosl2Solid

import numpy as np

# ---------------------------------------------------------------------------
# Scalar/number predicates
# ---------------------------------------------------------------------------


def is_num(value: Any) -> bool:
    """Return True if *value* is a numeric scalar (int, float, or numpy numeric), excluding bool."""
    return isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool)


# ---------------------------------------------------------------------------
# 3-D point/vector padding
# ---------------------------------------------------------------------------


def vec3(vector: Any) -> np.ndarray:
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


def scalar_vec3(value: Any, fill: float = 0.0) -> np.ndarray:
    """Return ``[value, fill, fill]`` for a scalar; pad a vector to length 3.

    BOSL2's ``scalar_vec3()`` -- used for direction vectors where a single value
    fills a single axis.
    """
    if is_num(value):
        return np.array([float(value), float(fill), float(fill)])
    arr = list(value)
    return np.array([float(arr[i]) if i < len(arr) else float(fill) for i in range(3)])


# ---------------------------------------------------------------------------
# Vector normalization
# ---------------------------------------------------------------------------


def unit(vector: Any) -> np.ndarray:
    """Normalize *vector* to unit length.  Returns zero vector if zero-length (matching.

    ``pybosl2/transforms.py``'s ``_unit()`` convention).
    """
    arr = np.asarray(vector, dtype=float)
    norm = float(np.linalg.norm(arr))
    return arr / norm if norm else arr


# ---------------------------------------------------------------------------
# 4x4 transformation matrix factories
# ---------------------------------------------------------------------------


def zrot4(angle_degrees: float) -> np.ndarray:
    """4x4 rotation matrix of *angle_degrees* degrees about the Z axis."""
    from pybosl2.transforms import axis_angle_matrix

    matrix = np.eye(4)
    matrix[:3, :3] = axis_angle_matrix(angle_degrees, [0, 0, 1])
    return matrix


def xrot4(angle_degrees: float) -> np.ndarray:
    """4x4 rotation matrix of *angle_degrees* degrees about the X axis."""
    rad = math.radians(angle_degrees)
    c, s = math.cos(rad), math.sin(rad)
    m = np.eye(4)
    m[1, 1], m[1, 2], m[2, 1], m[2, 2] = c, -s, s, c
    return m


def scale4(s: Sequence[float]) -> np.ndarray:
    """4x4 scale matrix for scaling factors *s* (2-D or 3-D)."""
    m = np.eye(4)
    m[0, 0] = float(s[0])
    m[1, 1] = float(s[1])
    if len(s) > 2:
        m[2, 2] = float(s[2])
    return m


def rot_from_to4(source: Any, target: Any) -> np.ndarray:
    """4x4 rotation matrix rotating direction *source* onto direction *target*."""
    from pybosl2.transforms import axis_angle_matrix, rot_from_to

    angle, axis = rot_from_to(source, target)
    matrix = np.eye(4)
    matrix[:3, :3] = axis_angle_matrix(angle, axis)
    return matrix


def translate4(offset: Any) -> np.ndarray:
    """4x4 translation matrix. *offset* is a 3-D point (or 2-D with z=0)."""
    point = np.asarray(offset, dtype=float).ravel()
    matrix = np.eye(4)
    matrix[:3, 3] = [
        float(point[0]),
        float(point[1]),
        float(point[2]) if len(point) > 2 else 0.0,
    ]
    return matrix


def frame_map4_yz(y_axis: Any, z_axis: Any) -> np.ndarray:
    """Rotation whose local +Y and +Z axes point along *y_axis* and *z_axis* (BOSL2 frame_map(y=, z=)).

    Different from ``frame_map4_xz``: this version takes Y and Z axes (used by
    :mod:`pybosl2.miscellaneous`'s path_extrude2d).
    """
    y_unit, z_unit = (
        unit(np.asarray(y_axis, dtype=float)),
        unit(np.asarray(z_axis, dtype=float)),
    )
    x_unit = unit(np.cross(y_unit, z_unit))
    y_unit = unit(np.cross(z_unit, x_unit))
    matrix = np.eye(4)
    matrix[:3, 0], matrix[:3, 1], matrix[:3, 2] = x_unit, y_unit, z_unit
    return matrix


# ---------------------------------------------------------------------------
# CSG union helpers
# ---------------------------------------------------------------------------


def union(shapes: Any) -> Any:
    """Boolean union of an iterable of native PythonSCAD shapes (``reduce(operator.or_, shapes)``)."""
    return reduce(operator.or_, shapes)


# ---------------------------------------------------------------------------
# Bosl2Solid / Bosl2Shape2D unwrapping
# ---------------------------------------------------------------------------


def unwrap(obj: Bosl2Solid | Bosl2Shape2D | Any) -> Any:
    """Extract the native shape from a :class:`~pybosl2.shapes3d.Bosl2Solid` (3-D) or.

    :class:`~pybosl2.shapes2d.Bosl2Shape2D` (2-D) wrapper, or return *obj* as-is.

    Both are plain Python wrappers around a native handle, so anything handing an object
    *directly* to a native function (``hull()``, ``minkowski()``, ...) rather than calling a
    method on it must unwrap first.
    """
    from pybosl2.shapes2d import Bosl2Shape2D
    from pybosl2.shapes3d import Bosl2Solid

    if isinstance(obj, (Bosl2Solid, Bosl2Shape2D)):
        return obj.realize().shape
    return obj


# ---------------------------------------------------------------------------
# Consolidated Internal Geometry & Math Helpers (moved from shapes2d/base.py)
# ---------------------------------------------------------------------------


class AnchorType(Enum):
    HULL = "hull"
    BOX = "box"
    INTERSECT = "intersect"


def norm_atype(atype: str | AnchorType) -> AnchorType:
    if isinstance(atype, AnchorType):
        return atype
    try:
        return AnchorType(atype.lower())
    except (ValueError, AttributeError):
        raise ValueError(f"Invalid atype: {atype!r}. Expected one of {list(AnchorType)}") from None


def quantup(x: float, y: float) -> float:
    """Ceiling quantization, rounding x up to the next multiple of y."""
    return math.ceil(x / y - 1e-9) * y


def frag_count(
    radius: float,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> int:
    """Return the number of polygon segments to approximate a circle of radius *radius*, mirroring.

    OpenSCAD's $fn/$fa/$fs rules.  Anything the caller left as None falls back to the ambient
    defaults (:func:`pybosl2.defaults.use_defaults`) before OpenSCAD's own $fa=12 / $fs=2.
    """
    fn, fa, fs = resolve_facets(fn, fa, fs)
    if fn is not None and fn >= 3:
        return int(math.floor(fn))
    fa = fa if fa else 12.0
    fs = fs if fs else 2.0
    return max(5, int(math.ceil(min(360.0 / fa, (2 * math.pi * abs(radius)) / fs))))


def pick_radius(
    radius1: float | None = None,
    diameter1: float | None = None,
    radius2: float | None = None,
    diameter2: float | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    dflt: float | None = None,
) -> Any:
    """Resolve one radius from the radius/diameter spellings, most specific first.

    Priority is (radius1, diameter1) > (radius2, diameter2) > (radius, diameter) > *dflt*, matching
    BOSL2's get_radius(). Unlike BOSL2, giving BOTH spellings of the same dimension is an error
    rather than a silent win for the radius (SPEC.md D-5): a call that cannot mean what it says
    fails loudly (SPEC.md E-5).

    Args:
        radius1: Radius of the first end.
        diameter1: Diameter of the first end.
        radius2: Radius of the second end.
        diameter2: Diameter of the second end.
        radius: Radius applying to both ends.
        diameter: Diameter applying to both ends.
        dflt: Value to use when nothing was given.

    Returns:
        The resolved radius, or *dflt* when no spelling was supplied.

    Raises:
        ValueError: If a radius and its own diameter are both given.

    """
    for radius_value, diameter_value, radius_name, diameter_name in (
        (radius1, diameter1, "radius1", "diameter1"),
        (radius2, diameter2, "radius2", "diameter2"),
        (radius, diameter, "radius", "diameter"),
    ):
        if radius_value is not None and diameter_value is not None:
            raise ValueError(
                f"give {radius_name} or {diameter_name}, not both "
                f"({radius_name}={radius_value}, {diameter_name}={diameter_value})"
            )
    if radius1 is not None:
        return radius1
    if diameter1 is not None:
        return diameter1 / 2
    if radius2 is not None:
        return radius2
    if diameter2 is not None:
        return diameter2 / 2
    if radius is not None:
        return radius
    if diameter is not None:
        return diameter / 2
    return dflt


def polar_to_xy(radius: float, angle: float) -> list[float]:
    rad = math.radians(angle)
    return [radius * math.cos(rad), radius * math.sin(rad)]


def rotate2d(point: Sequence[float], degrees: float) -> list[float]:
    rad = math.radians(degrees)
    c, s = math.cos(rad), math.sin(rad)
    return [point[0] * c - point[1] * s, point[0] * s + point[1] * c]


def circle_pts(radius: float, count: int, start: float = 0.0) -> list[list[float]]:
    return [polar_to_xy(radius, start + 360.0 * i / count) for i in range(count)]


def dir2(anchor: Anchor | Sequence[float]) -> list[float]:
    a = (anchor.vector if isinstance(anchor, Anchor) else list(anchor)) + [0, 0, 0]
    return [a[0], a[1] + a[2]]


def anchor_offset_box(size: Sequence[float], anchor: Anchor | Sequence[float]) -> list[float]:
    d = dir2(anchor)
    return [-d[0] * size[0] / 2, -d[1] * size[1] / 2]


def anchor_offset_hull(points: Sequence[Sequence[float]], anchor: Anchor | Sequence[float]) -> list[float]:
    d = dir2(anchor)
    if d[0] == 0 and d[1] == 0:
        return [0.0, 0.0]
    best = max(points, key=lambda p: p[0] * d[0] + p[1] * d[1])
    return [-best[0], -best[1]]


def anchor_offset_generic(
    points: Sequence[Sequence[float]],
    anchor: Anchor | Sequence[float],
    atype: str | AnchorType,
) -> list[float]:
    atype_enum = norm_atype(atype)
    if atype_enum == AnchorType.BOX:
        min_x = min(p[0] for p in points)
        max_x = max(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_y = max(p[1] for p in points)
        size = [max_x - min_x, max_y - min_y]
        return anchor_offset_box(size, anchor)
    elif atype_enum == AnchorType.INTERSECT:
        d = dir2(anchor)
        if d[0] == 0 and d[1] == 0:
            return [0.0, 0.0]
        best_t = 0.0
        best_pt = [0.0, 0.0]
        n = len(points)
        for i in range(n):
            p1 = points[i]
            p2 = points[(i + 1) % n]
            x1, y1 = p1[0], p1[1]
            x2, y2 = p2[0], p2[1]
            dx, dy = d[0], d[1]

            denom = (y2 - y1) * dx - (x2 - x1) * dy
            if abs(denom) > 1e-9:
                u = (x1 * dy - y1 * dx) / denom
                if 0.0 <= u <= 1.0:
                    t = (x1 + u * (x2 - x1)) / dx if abs(dx) > 1e-9 else (y1 + u * (y2 - y1)) / dy
                    if t >= 0.0 and t > best_t:
                        best_t = t
                        best_pt = [t * dx, t * dy]
        if best_t > 0.0:
            return [-best_pt[0], -best_pt[1]]
        return anchor_offset_hull(points, anchor)
    else:
        return anchor_offset_hull(points, anchor)


def anchor_offset_box3(size: Sequence[float], anchor: Anchor | Sequence[float]) -> list[float]:
    """3-D box anchor offset: returns the translation vector for a box of *size* at *anchor*."""
    a = anchor.vector if isinstance(anchor, Anchor) else list(anchor)
    return [-a[i] * size[i] / 2 for i in range(3)]


def anchor_offset_hull3(points: Sequence[Sequence[float]], anchor: Anchor | Sequence[float]) -> list[float]:
    """3-D convex hull anchor offset with centroid tie-breaking."""
    a = anchor.vector if isinstance(anchor, Anchor) else list(anchor)
    if a[0] == 0 and a[1] == 0 and a[2] == 0:
        return [0.0, 0.0, 0.0]
    projs = [p[0] * a[0] + p[1] * a[1] + p[2] * a[2] for p in points]
    m = max(projs)
    eps = 1e-7 * (1.0 + abs(m))
    tied = [p for p, pr in zip(points, projs, strict=False) if pr >= m - eps]
    sides = len(tied)
    return [-sum(p[i] for p in tied) / sides for i in range(3)]


def anchor_offset_cyl(
    radius1: float,
    radius2: float,
    length: float,
    anchor: Anchor | Sequence[float],
    axis: int = 2,
) -> list[float]:
    """3-D cylinder anchor offset along *axis* (0=X, 1=Y, 2=Z)."""
    a = anchor.vector if isinstance(anchor, Anchor) else list(anchor)
    az = a[axis]
    r_at = radius1 if az < 0 else (radius2 if az > 0 else (radius1 + radius2) / 2)
    radial_axes = [i for i in range(3) if i != axis]
    radial = [a[i] for i in radial_axes]
    rn = math.hypot(*radial)
    if rn > 0:
        radial = [x / rn * r_at for x in radial]
    offset = [0.0, 0.0, 0.0]
    offset[axis] = az * length / 2
    for i, ax in enumerate(radial_axes):
        offset[ax] = radial[i]
    return [-x for x in offset]


def anchor_offset_sphere(r: float, anchor: Anchor | Sequence[float]) -> list[float]:
    """3-D sphere anchor offset: project *anchor* direction onto the sphere surface."""
    a = anchor.vector if isinstance(anchor, Anchor) else list(anchor)
    n = math.hypot(*a)
    if n == 0:
        return [0.0, 0.0, 0.0]
    return [-a[i] / n * r for i in range(3)]


def arc_points(
    count: int,
    radius: float,
    start: float,
    angle: float,
    center: Sequence[float] = (0.0, 0.0),
    endpoint: bool = True,
) -> list[list[float]]:
    """*count* points along an arc of radius *radius* centered at *center*, from angle *start*.

    sweeping *angle* degrees.
    """
    if not endpoint:
        return arc_points(count + 1, radius, start, angle, center, True)[:-1]
    if count <= 1:
        return [
            [
                radius * math.cos(math.radians(start)) + center[0],
                radius * math.sin(math.radians(start)) + center[1],
            ]
        ]
    pts = []
    for i in range(count):
        theta = math.radians(start + i * angle / (count - 1))
        pts.append([radius * math.cos(theta) + center[0], radius * math.sin(theta) + center[1]])
    return pts


def circle_from_3pts(points: Sequence[Sequence[float]]) -> tuple[list[float], float]:
    (x1, y1), (x2, y2), (x3, y3) = points
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / d
    uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / d
    return [ux, uy], math.hypot(x1 - ux, y1 - uy)


def rect_path(
    size: Sequence[float],
    rounding: float | Sequence[float] = 0,
    chamfer: float | Sequence[float] = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> list[list[float]]:
    sx, sy = size
    rounding_l = [float(rounding)] * 4 if isinstance(rounding, (int, float)) else [float(v) for v in rounding]
    chamfer_l = [float(chamfer)] * 4 if isinstance(chamfer, (int, float)) else [float(v) for v in chamfer]
    if all(v == 0 for v in rounding_l) and all(v == 0 for v in chamfer_l):
        return [
            [sx / 2, -sy / 2],
            [-sx / 2, -sy / 2],
            [-sx / 2, sy / 2],
            [sx / 2, sy / 2],
        ]
    quadorder = [3, 2, 1, 0]
    quadpos = [[1, 1], [-1, 1], [-1, -1], [1, -1]]
    eps = 1e-9
    insets = [
        (chamfer_l[i] if abs(chamfer_l[i]) >= eps else (rounding_l[i] if abs(rounding_l[i]) >= eps else 0))
        for i in range(4)
    ]
    insets_x = max(insets[0] + insets[1], insets[2] + insets[3])
    insets_y = max(insets[0] + insets[3], insets[1] + insets[2])
    assert insets_x <= sx, f"Requested roundings and/or chamfers ({insets_x:.3f}) exceed the rect width ({sx:.3f})"
    assert insets_y <= sy, f"Requested roundings and/or chamfers ({insets_y:.3f}) exceed the rect height ({sy:.3f})"
    path = []
    for i in range(4):
        quad = quadorder[i]
        qinset = insets[quad]
        qpos = quadpos[quad]
        qchamf = chamfer_l[quad]
        qround = rounding_l[quad]
        cverts = int(quantup(frag_count(abs(qinset), fn, fa, fs), 4) / 4) if abs(qinset) >= eps else 0
        step = 90.0 / cverts if cverts else 0.0
        center = [(sx / 2 - qinset) * qpos[0], (sy / 2 - abs(qinset)) * qpos[1]]
        if abs(qchamf) >= eps:
            qpts = [[0, abs(qinset)], [qinset, 0]]
        elif abs(qround) >= eps:
            sign = 1 if qinset >= 0 else -1
            qpts = []
            for j in range(cverts + 1):
                a = 90 - j * step
                p = polar_to_xy(abs(qinset), a)
                qpts.append([p[0] * sign, p[1]])
        else:
            qpts = [[0, 0]]
        qfpts = [[p[0] * qpos[0], p[1] * qpos[1]] for p in qpts]
        qrpts = list(reversed(qfpts)) if qpos[0] * qpos[1] < 0 else qfpts
        for p in qrpts:
            path.append([p[0] + center[0], p[1] + center[1]])
    return path


def as_native_2d(obj: Any) -> Any:
    """Return a raw native 2-D handle from *obj*: a Bosl2Shape2D/Bosl2Solid wrapper, a native shape,.

    a :class:`~pybosl2.paths.Path2D` / :class:`~pybosl2.regions.Region`, or a plain point list.
    """
    unwrapped = unwrap(obj)
    if unwrapped is not obj:  # a Bosl2Shape2D / Bosl2Solid wrapper
        return unwrapped
    geom = getattr(obj, "geometry", None)  # Path2D / Region
    if callable(geom):
        return unwrap(geom())
    if isinstance(obj, (list, tuple)):  # a bare [[x, y], ...] point list
        from pybosl2._native import native

        opolygon = native("polygon")
        return opolygon([[float(p[0]), float(p[1])] for p in obj])
    return obj


def is_child_2d(obj: Any) -> bool:
    """Return True if *obj* is a single 2-D child rather than a container of children -- a wrapper or.

    native shape, a Path2D/Region (which are ``list`` subclasses), or a ``[[x, y], ...]`` list.
    """
    if not isinstance(obj, (list, tuple)):
        return True  # a wrapper or a native handle
    if callable(getattr(obj, "geometry", None)):
        return True  # Path2D / Region
    return bool(len(obj)) and isinstance(obj[0], (list, tuple)) and len(obj[0]) == 2

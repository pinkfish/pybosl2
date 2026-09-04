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
from typing import TYPE_CHECKING, Any, NamedTuple, TypeVar

from pybosl2._edges_lang import Anchor
from pybosl2.defaults import resolve_facets

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from pybosl2.paths import PathLike
    from pybosl2.shapes2d import Bosl2Shape2D
    from pybosl2.shapes3d import Bosl2Solid

import numpy as np

from pybosl2.exceptions import Bosl2ValueError

# ---------------------------------------------------------------------------
# Scalar/number predicates
# ---------------------------------------------------------------------------


def is_num(value: Any) -> bool:
    """Return True if *value* is a numeric scalar (int, float, or numpy numeric), excluding bool.

    Args:
        value: The value to convert or check.

    """
    return isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool)


# ---------------------------------------------------------------------------
# 3-D point/vector padding
# ---------------------------------------------------------------------------


def vec3(vector: Any) -> np.ndarray:
    """Pad *vector* to a list of 3: if 2-D, set z=0; if numeric, repeat to 3.

    Unlike :func:`scalar_vec3`, a scalar becomes ``[vector, vector, vector]`` (matching ``np.asarray``
    broadcast semantics in places where all three coordinates are the same).

    Args:
        vector: The vector.

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

    Args:
        value: The value to convert or check.
        fill: Value to pad the remaining components with.

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

    Args:
        vector: The vector.

    """
    arr = np.asarray(vector, dtype=float)
    norm = float(np.linalg.norm(arr))
    return arr / norm if norm else arr


# ---------------------------------------------------------------------------
# 4x4 transformation matrix factories
# ---------------------------------------------------------------------------


def zrot4(angle_degrees: float) -> np.ndarray:
    """4x4 rotation matrix of *angle_degrees* degrees about the Z axis.

    Args:
        angle_degrees: The angle in degrees.

    """
    from pybosl2.transforms import axis_angle_matrix

    matrix = np.eye(4)
    matrix[:3, :3] = axis_angle_matrix(angle_degrees, [0, 0, 1])
    return matrix


def xrot4(angle_degrees: float) -> np.ndarray:
    """4x4 rotation matrix of *angle_degrees* degrees about the X axis.

    Args:
        angle_degrees: The angle in degrees.

    """
    rad = math.radians(angle_degrees)
    c, s = math.cos(rad), math.sin(rad)
    m = np.eye(4)
    m[1, 1], m[1, 2], m[2, 1], m[2, 2] = c, -s, s, c
    return m


def scale4(s: Sequence[float]) -> np.ndarray:
    """4x4 scale matrix for scaling factors *s* (2-D or 3-D).

    Args:
        s: The scalar.

    """
    m = np.eye(4)
    m[0, 0] = float(s[0])
    m[1, 1] = float(s[1])
    if len(s) > 2:
        m[2, 2] = float(s[2])
    return m


def rot_from_to4(source: Any, target: Any) -> np.ndarray:
    """4x4 rotation matrix rotating direction *source* onto direction *target*.

    Args:
        source: The direction to rotate from.
        target: The direction to rotate to.

    """
    from pybosl2.transforms import axis_angle_matrix, rot_from_to

    angle, axis = rot_from_to(source, target)
    matrix = np.eye(4)
    matrix[:3, :3] = axis_angle_matrix(angle, axis)
    return matrix


def translate4(offset: Any) -> np.ndarray:
    """4x4 translation matrix. *offset* is a 3-D point (or 2-D with z=0).

    Args:
        offset: The offset to apply.

    """
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

    Args:
        y_axis: The vector to use as the Y axis.
        z_axis: The vector to use as the Z axis.

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


_Unionable = TypeVar("_Unionable")


def union(shapes: "Iterable[_Unionable]") -> _Unionable:
    """Boolean union of an iterable of shapes (``reduce(operator.or_, shapes)``).

    Generic in the shape type, so unioning solids gives a solid back rather than `Any` -- which
    otherwise spreads through every part that builds by unioning a list of pieces, and hides
    exactly the mistakes the `Solid` contract exists to catch.

    Args:
        shapes: The shapes to combine.

    """
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

    Args:
        obj: The object to inspect.

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
        raise Bosl2ValueError(f"Invalid atype: {atype!r}. Expected one of {list(AnchorType)}") from None


def quantup(x: float, y: float) -> float:
    """Ceiling quantization, rounding x up to the next multiple of y.

    Args:
        x: The X coordinate.
        y: The Y coordinate.

    """
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
    An *fn* below 3 means "use fa/fs", so ``fn=0`` is how one call opts out of an ambient
    ``fn`` (SPEC R-5).

    Args:
        radius: The radius.
        fn: Fixed fragment count for curved surfaces. Omitted, the ambient ``use_defaults(fn=...)`` value applies;
            ``fn=0`` opts back out to fa/fs.
        fa: Minimum fragment angle in degrees. Omitted, the ambient ``use_defaults(fa=...)`` value applies.
        fs: Minimum fragment size in millimetres. Omitted, the ambient ``use_defaults(fs=...)`` value applies.

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
            raise Bosl2ValueError(
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


def anchor_vector(anchor: Anchor | Sequence[float]) -> list[float]:
    """Return an anchor's direction vector, rejecting the legacy string form.

    Args:
        anchor: An :class:`~pybosl2.enums.Anchor` member or a direction vector such as ``[1, 0, 0]``.

    Returns:
        The anchor's components as a list of floats.

    Raises:
        ValueError: If *anchor* is a string; pass an :class:`~pybosl2.enums.Anchor` member instead.

    """
    if isinstance(anchor, str):
        raise Bosl2ValueError(f"Legacy string anchor selection is not allowed: {anchor!r}; pass an Anchor member.")
    return [float(v) for v in anchor.vector] if isinstance(anchor, Anchor) else [float(v) for v in anchor]


def dir2(anchor: Anchor | Sequence[float]) -> list[float]:
    a = anchor_vector(anchor) + [0, 0, 0]
    return [a[0], a[1] + a[2]]


def anchor_offset_box(size: Sequence[float], anchor: Anchor | Sequence[float]) -> list[float]:
    d = dir2(anchor)
    return [-d[0] * size[0] / 2, -d[1] * size[1] / 2]


def anchor_offset_hull(points: PathLike, anchor: Anchor | Sequence[float]) -> list[float]:
    d = dir2(anchor)
    if d[0] == 0 and d[1] == 0:
        return [0.0, 0.0]
    best = max(points, key=lambda p: p[0] * d[0] + p[1] * d[1])
    return [-best[0], -best[1]]


def anchor_offset_generic(
    points: PathLike,
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
    """3-D box anchor offset: returns the translation vector for a box of *size* at *anchor*.

    Args:
        size: The size, one number or one per axis.
        anchor: Anchor point.

    """
    a = anchor_vector(anchor)
    return [-a[i] * size[i] / 2 for i in range(3)]


def anchor_offset_hull3(points: PathLike, anchor: Anchor | Sequence[float]) -> list[float]:
    """3-D convex hull anchor offset with centroid tie-breaking.

    Args:
        points: The points to operate on.
        anchor: Anchor point.

    """
    a = anchor_vector(anchor)
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
    """3-D cylinder anchor offset along *axis* (0=X, 1=Y, 2=Z).

    Args:
        radius1: The first radius.
        radius2: The second radius.
        length: The length.
        anchor: Anchor point.
        axis: The axis to rotate about.

    """
    a = anchor_vector(anchor)
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
    """3-D sphere anchor offset: project *anchor* direction onto the sphere surface.

    Args:
        r: The radius, in BOSL2's short spelling.
        anchor: Anchor point.

    """
    a = anchor_vector(anchor)
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

    Args:
        count: How many to produce.
        radius: The radius.
        start: Where to begin.
        angle: The angle in degrees.
        center: Centre the shape on the origin.
        endpoint: Include the final value in the result.

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


def circle_from_3pts(points: PathLike) -> tuple[list[float], float]:
    (x1, y1), (x2, y2), (x3, y3) = np.asarray(points, dtype=float)
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
    if not (insets_x <= sx):
        raise Bosl2ValueError(f"Requested roundings and/or chamfers ({insets_x:.3f}) exceed the rect width ({sx:.3f})")
    if not (insets_y <= sy):
        raise Bosl2ValueError(f"Requested roundings and/or chamfers ({insets_y:.3f}) exceed the rect height ({sy:.3f})")
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

    Args:
        obj: The object to inspect.

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

    Args:
        obj: The object to inspect.

    """
    if not isinstance(obj, (list, tuple)):
        return True  # a wrapper or a native handle
    if callable(getattr(obj, "geometry", None)):
        return True  # Path2D / Region
    return bool(len(obj)) and isinstance(obj[0], (list, tuple)) and len(obj[0]) == 2


def require_anchor(anchor: object, parameter: str) -> Anchor:
    """Return *anchor* as an :class:`~pybosl2.enums.Anchor`, rejecting anything else clearly.

    `attach()` and `align()` mate a *named face* against another, so unlike `anchor_vector()`
    they need a member rather than a direction vector. They previously reached straight for
    `.vector`, so a wrong argument surfaced as ``AttributeError: 'str' object has no attribute
    'vector'`` -- an internal detail naming neither the parameter at fault nor what to pass,
    while every other anchor in the library rejected the same mistake in plain terms (SPEC E-4).

    Args:
        anchor: The value passed for an anchor parameter.
        parameter: Name of the parameter, so the message points at the argument that was wrong.

    Returns:
        The anchor, unchanged, when it is an :class:`~pybosl2.enums.Anchor`.

    Raises:
        Bosl2ValueError: If *anchor* is not an :class:`~pybosl2.enums.Anchor` member.

    """
    if isinstance(anchor, Anchor):
        return anchor
    hint = ""
    if isinstance(anchor, str):
        # The likeliest mistake by far, and one the message can turn straight into the fix.
        named = anchor.upper().replace("-", "_")
        hint = f" Did you mean Anchor.{named}?" if named in Anchor.__members__ else ""
    return _reject_anchor(anchor, parameter, hint)


def _reject_anchor(anchor: object, parameter: str, hint: str) -> Anchor:
    raise Bosl2ValueError(
        f"{parameter} must be an Anchor member, not {type(anchor).__name__} ({anchor!r})."
        f"{hint} Anchors name a face to mate against -- a direction vector is accepted by "
        f"`anchor=` on the shape constructors, but not here."
    )


class RectTube(NamedTuple):
    """A `rect_tube` call resolved into the two prismoids it is built from.

    `rect_tube` is an outer prismoid with an inner one taken out of it, on both backends -- but
    getting from its twenty-odd arguments to those two shapes is eighty lines of rule: an outer
    size or a bore plus a wall, either of which derives the other; per-end sizes that fall back to
    the overall one; and inner roundings that are derived from the outer ones minus the wall
    unless the caller named them, with a chamfer on the same corner cancelling them.

    This lives here because both backends need every line of it and neither owns it. Writing it
    twice is how `center=` came to be spelled in two contradicting precedences (T40) and how
    `default_tex_reps` came to answer one undecorated call two ways (T41); this is the third time
    the same shape of duplication was about to be created, and the third time it was not
    (SPEC C-21, PAR-5).
    """

    size1: list[float]
    size2: list[float]
    isize1: list[float]
    isize2: list[float]
    rounding1: list[float]
    rounding2: list[float]
    chamfer1: list[float]
    chamfer2: list[float]
    inner_rounding1: list[float]
    inner_rounding2: list[float]
    inner_chamfer1: list[float]
    inner_chamfer2: list[float]


def _rect_tube_inner(
    factor: float,
    inner_radius: "Sequence[float | None]",
    radius: "Sequence[float | None]",
    alternative: "Sequence[float | None]",
    size: "Sequence[float]",
    isize: "Sequence[float]",
) -> list[float]:
    """Return the bore's corner treatment: the caller's, or the outer one set back by the wall.

    Args:
        factor: 1 for a rounding, 1/sqrt(2) for a chamfer -- how much of the wall it eats.
        inner_radius: What the caller asked for on the bore, per corner, or ``None``.
        radius: The outer treatment, per corner.
        alternative: The other kind on the bore; a corner that has one gets no treatment here.
        size: The outer size.
        isize: The bore size.

    Returns:
        The four corner amounts.

    """
    wall = min(size[0] - isize[0], size[1] - isize[1]) / 2 * factor
    return [
        iri
        if iri is not None
        else (max(0.0, (ri if ri is not None else 0.0) - wall) if alternative[i] is None else 0.0)
        for i, (iri, ri) in enumerate(zip(inner_radius, radius, strict=False))
    ]


#: `rect_tube` states most of its arguments three ways -- one number, one per axis, or one per
#: corner -- and the resolution below needs each of them in one shape. These three do that
#: normalising, and nothing else.
def _as2(v: "float | Sequence[float] | None") -> "list[float] | None":
    """Return *v* as ``[x, y]``, or ``None``."""
    if v is None:
        return None
    return [float(v), float(v)] if isinstance(v, (int, float)) else [float(x) for x in v]


def _force4(v: "float | Sequence[float] | None") -> "list[float | None]":
    """Return *v* as four corner values, or four ``None``s."""
    if v is None:
        return [None, None, None, None]
    return [float(v)] * 4 if isinstance(v, (int, float)) else [float(x) for x in v]


def _force4f(v: "float | Sequence[float]") -> list[float]:
    """Return *v* as four corner values."""
    return [float(v)] * 4 if isinstance(v, (int, float)) else [float(x) for x in v]


def _override_or_none(
    specific: "float | Sequence[float] | None", general: "float | Sequence[float]"
) -> "float | Sequence[float] | None":
    """Return the specific value, else the general one when it asks for anything.

    `inner_rounding`/`inner_chamfer` default to 0 rather than None in this port's signature, so a
    bare 0 means "not specified" and inherits from `rounding`/`chamfer`. Pass `inner_rounding1=`
    and friends, which do default to None, to force an explicit zero.

    Args:
        specific: The per-end value, or ``None``.
        general: The overall value.

    Returns:
        The value to use, or ``None`` for "nothing asked".

    """
    if specific is not None:
        return specific
    return general if general else None


def _rect_tube_sizes(
    size: "float | Sequence[float] | None",
    isize: "float | Sequence[float] | None",
    wall: float | None,
    size1: "float | Sequence[float] | None",
    size2: "float | Sequence[float] | None",
    isize1: "float | Sequence[float] | None",
    isize2: "float | Sequence[float] | None",
) -> "tuple[list[float], list[float], list[float], list[float]]":
    """Resolve a `rect_tube`'s outer size and bore at each end.

    Either the outer size or the bore may be given, with a wall thickness deriving the other; an
    outer size with nothing said about the bore means "just make it a tube", and a 1 mm wall is
    assumed rather than making the caller state the obvious (SPEC P-3).

    Args:
        size: Outer size for both ends.
        isize: Bore size for both ends.
        wall: Wall thickness.
        size1: Outer size at the bottom.
        size2: Outer size at the top.
        isize1: Bore size at the bottom.
        isize2: Bore size at the top.

    Returns:
        The bottom and top outer sizes, then the bottom and top bore sizes.

    Raises:
        Bosl2ValueError: if either cannot be worked out, or the bore is not smaller.

    """
    s1 = _as2(size1) if size1 is not None else _as2(size)
    s2 = _as2(size2) if size2 is not None else _as2(size)
    i1 = _as2(isize1) if isize1 is not None else _as2(isize)
    i2 = _as2(isize2) if isize2 is not None else _as2(isize)
    # An outer size with nothing said about the bore means "just make it a tube": derive the
    # hole from a 1 mm wall rather than making the caller state the obvious (SPEC.md P-3).
    if wall is None and i1 is None and i2 is None:
        wall = 1.0
    size1_v = (
        s1
        if s1 is not None
        else ([i1[0] + 2 * wall, i1[1] + 2 * wall] if (wall is not None and i1 is not None) else None)
    )
    size2_v = (
        s2
        if s2 is not None
        else ([i2[0] + 2 * wall, i2[1] + 2 * wall] if (wall is not None and i2 is not None) else None)
    )
    isize1_v = (
        i1
        if i1 is not None
        else ([s1[0] - 2 * wall, s1[1] - 2 * wall] if (wall is not None and s1 is not None) else None)
    )
    isize2_v = (
        i2
        if i2 is not None
        else ([s2[0] - 2 * wall, s2[1] - 2 * wall] if (wall is not None and s2 is not None) else None)
    )
    if size1_v is None or size2_v is None:
        raise Bosl2ValueError(
            "rect_tube(): needs an outer size -- give size (or size1/size2), or an inner size with a wall thickness."
        )
    if isize1_v is None or isize2_v is None:
        raise Bosl2ValueError(
            "rect_tube(): needs a bore -- give isize (or isize1/isize2), or a wall thickness to "
            "derive it from the outer size."
        )
    if isize1_v[0] >= size1_v[0] or isize1_v[1] >= size1_v[1]:
        raise Bosl2ValueError(
            f"rect_tube(): bore {isize1_v} is not smaller than the outer size {size1_v} at the bottom."
        )
    if isize2_v[0] >= size2_v[0] or isize2_v[1] >= size2_v[1]:
        raise Bosl2ValueError(f"rect_tube(): bore {isize2_v} is not smaller than the outer size {size2_v} at the top.")
    return size1_v, size2_v, isize1_v, isize2_v


def resolve_rect_tube(
    size: "float | Sequence[float] | None",
    isize: "float | Sequence[float] | None",
    wall: float | None,
    size1: "float | Sequence[float] | None",
    size2: "float | Sequence[float] | None",
    isize1: "float | Sequence[float] | None",
    isize2: "float | Sequence[float] | None",
    rounding: "float | Sequence[float]",
    rounding1: "float | Sequence[float] | None",
    rounding2: "float | Sequence[float] | None",
    inner_rounding: "float | Sequence[float]",
    inner_rounding1: "float | Sequence[float] | None",
    inner_rounding2: "float | Sequence[float] | None",
    chamfer: "float | Sequence[float]",
    chamfer1: "float | Sequence[float] | None",
    chamfer2: "float | Sequence[float] | None",
    inner_chamfer: "float | Sequence[float]",
    inner_chamfer1: "float | Sequence[float] | None",
    inner_chamfer2: "float | Sequence[float] | None",
) -> RectTube:
    """Resolve a `rect_tube` call into the outer and inner prismoids it is built from.

    Args:
        size: Outer size for both ends.
        isize: Bore size for both ends.
        wall: Wall thickness, deriving whichever of the two was not given.
        size1: Outer size at the bottom.
        size2: Outer size at the top.
        isize1: Bore size at the bottom.
        isize2: Bore size at the top.
        rounding: Outer corner rounding for both ends.
        rounding1: Outer corner rounding at the bottom.
        rounding2: Outer corner rounding at the top.
        inner_rounding: Bore corner rounding for both ends.
        inner_rounding1: Bore corner rounding at the bottom.
        inner_rounding2: Bore corner rounding at the top.
        chamfer: Outer corner chamfer for both ends.
        chamfer1: Outer corner chamfer at the bottom.
        chamfer2: Outer corner chamfer at the top.
        inner_chamfer: Bore corner chamfer for both ends.
        inner_chamfer1: Bore corner chamfer at the bottom.
        inner_chamfer2: Bore corner chamfer at the top.

    Returns:
        The resolved sizes and per-corner treatments.

    Raises:
        Bosl2ValueError: if the outer size or the bore cannot be worked out, or the bore is not
            smaller than the outer size.

    """
    size1_v, size2_v, isize1_v, isize2_v = _rect_tube_sizes(size, isize, wall, size1, size2, isize1, isize2)

    rounding1_v = _force4f(rounding1 if rounding1 is not None else rounding)
    rounding2_v = _force4f(rounding2 if rounding2 is not None else rounding)
    chamfer1_v = _force4f(chamfer1 if chamfer1 is not None else chamfer)
    chamfer2_v = _force4f(chamfer2 if chamfer2 is not None else chamfer)
    irounding1_t = _force4(_override_or_none(inner_rounding1, inner_rounding))
    irounding2_t = _force4(_override_or_none(inner_rounding2, inner_rounding))
    ichamfer1_t = _force4(_override_or_none(inner_chamfer1, inner_chamfer))
    ichamfer2_t = _force4(_override_or_none(inner_chamfer2, inner_chamfer))

    irounding1_v = _rect_tube_inner(1.0, irounding1_t, rounding1_v, ichamfer1_t, size1_v, isize1_v)
    irounding2_v = _rect_tube_inner(1.0, irounding2_t, rounding2_v, ichamfer2_t, size2_v, isize2_v)
    ichamfer1_v = _rect_tube_inner(1 / math.sqrt(2), ichamfer1_t, chamfer1_v, irounding1_t, size1_v, isize1_v)
    ichamfer2_v = _rect_tube_inner(1 / math.sqrt(2), ichamfer2_t, chamfer2_v, irounding2_t, size2_v, isize2_v)
    return RectTube(
        size1_v,
        size2_v,
        isize1_v,
        isize2_v,
        rounding1_v,
        rounding2_v,
        chamfer1_v,
        chamfer2_v,
        irounding1_v,
        irounding2_v,
        ichamfer1_v,
        ichamfer2_v,
    )


def teardrop_stations(
    length: float,
    rad1: float,
    rad2: float,
    cap1: float | None,
    cap2: float | None,
    chamfer1: float,
    chamfer2: float,
    sin_a: float,
) -> "list[tuple[float, float, float]]":
    """Return the cross-sections a teardrop is hulled from, as ``(y, radius, cap)`` stations.

    A chamfered end is an extra section, set in along the axis by the chamfer and smaller by it in
    both the radius and the cap -- which is what makes the end a bevel. The CSG backend hulls this
    chain; the SDF backend makes it the breakpoints of a piecewise-linear cross-section. Same
    chain, so the same shape.

    It is shared for a reason the tests found rather than the reason the previous three were
    shared for. `tests/test_sdf_rim.py` checks the field against the CSG backend's own outline
    builder *at these stations* -- so a defect in the stations themselves is invisible to it, the
    expectation being derived from the thing under test. Sharing does not fix that (a shared
    defect moves both backends together, and no parity check can see it); what it does is make the
    one explicit assertion of the rule cover both (SPEC C-21, B2-1).

    "No cap" is stated as a cap at the apex, ``radius / sin(angle)``, rather than as ``None``. It
    is the same shape, and it removes the case where one end is truncated and the other is not --
    which would otherwise have no value to interpolate towards.

    Args:
        length: Length along the axis.
        rad1: Radius at the front end.
        rad2: Radius at the back end.
        cap1: Truncation height at the front, or ``None``.
        cap2: Truncation height at the back, or ``None``.
        chamfer1: Chamfer at the front end.
        chamfer2: Chamfer at the back end.
        sin_a: Sine of the teardrop's angle.

    Returns:
        The stations, front to back.

    """

    def capped(radius: float, cap: float | None) -> float:
        return radius / sin_a if cap is None else min(cap, radius / sin_a)

    front, back = -length / 2, length / 2
    stations = []
    if chamfer1:
        inner = max(0.001, rad1 - chamfer1)
        stations.append((front, inner, capped(inner, None if cap1 is None else cap1 - chamfer1)))
        front += abs(chamfer1)
    stations.append((front, rad1, capped(rad1, cap1)))
    if chamfer2:
        back -= abs(chamfer2)
    stations.append((back, rad2, capped(rad2, cap2)))
    if chamfer2:
        inner = max(0.001, rad2 - chamfer2)
        stations.append((back + abs(chamfer2), inner, capped(inner, None if cap2 is None else cap2 - chamfer2)))
    return stations

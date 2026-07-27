# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/shapes2d.py
#    Pure-Python port of BOSL2's shapes2d.scad, laid out in the same
#    order/sections as the original .scad file so the two are easy to
#    cross-reference. No osuse()/BOSL2 runtime dependency at all -- every
#    shape's outline is computed here in plain Python and then built with
#    direct openscad primitive calls (square()/circle()/polygon()/text()/
#    hull()/.offset()), rather than delegating to BOSL2. Every shape function
#    always returns real 2-D geometry (never a raw path), wrapped in a
#    :class:`Bosl2Shape2D` -- the 2-D counterpart of
#    :class:`~pybosl2.shapes3d.Bosl2Solid`, which carries the 2-D operators
#    (fill(), hull(), offset()) and the 2-D -> 3-D extruders
#    (linear_extrude(), rotate_extrude(), path_extrude()) as chainable
#    methods. `.shape` unwraps back to the raw native handle.
#
#    Anywhere BOSL2 lets you tune arc smoothness with the special variables
#    $fn/$fa/$fs, this module exposes the same knob as an explicit `fn`/
#    `fa`/`fs` keyword argument (matching this project's existing calling
#    convention, e.g. `circle(radius=5, fn=64)`), and uses it when computing the
#    point count for any rounded/curved portion of the shape.
#
# FileSummary: 2D primitives, polygons, curves, text and rounding (BOSL2 shapes2d.scad).
# FileGroup: BOSL2

from __future__ import annotations

import math
import numbers
import random
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Union, overload

import numpy as np

from pybosl2._native import native

# Imported explicitly (rather than `from pythonscad import *`) so editors/type-checkers
# can resolve these names -- this module immediately shadows all five with its own
# BOSL2-style square()/circle()/polygon()/text()/hull() below, so the plain builtins are
# captured under private names first.

if TYPE_CHECKING:
    from openscad import PyOpenSCAD

    from pybosl2.shapes3d import Bosl2Solid
from pybosl2._backend import check_operand_backend as _check_operand_backend
from pybosl2._backend import unsupported_feature as _unsupported_feature
from pybosl2.color import Colorable
from pybosl2.distributors import Distributable
from pybosl2.geometry import is_collinear
from pybosl2.paths import Path
from pybosl2.vectors import unit

from .constants import CENTER

if TYPE_CHECKING:  # real stub-typed imports for the checker (identical to pre-lazy)
    from pythonscad import circle as _ocircle
    from pythonscad import fill as _ofill
    from pythonscad import hull as _ohull
    from pythonscad import polygon as _opolygon
    from pythonscad import square as _osquare
    from pythonscad import text as _otext
else:
    _ocircle = native("circle")
    _ofill = native("fill")
    _ohull = native("hull")
    _opolygon = native("polygon")
    _osquare = native("square")
    _otext = native("text")

# ---------------------------------------------------------------------------
# Internal helpers (not part of BOSL2's public API)
# ---------------------------------------------------------------------------


from enum import Enum


class AnchorType(Enum):
    HULL = "hull"
    BOX = "box"
    INTERSECT = "intersect"


def _norm_atype(atype: str | AnchorType) -> AnchorType:
    if isinstance(atype, AnchorType):
        return atype
    try:
        return AnchorType(atype.lower())
    except (ValueError, AttributeError):
        raise ValueError(f"Invalid atype: {atype!r}. Expected one of {list(AnchorType)}") from None


def _anchor_offset_generic(
    points: Sequence[Sequence[float]],
    anchor: Sequence[float],
    atype: str | AnchorType,
) -> list[float]:
    atype_enum = _norm_atype(atype)
    if atype_enum == AnchorType.BOX:
        min_x = min(p[0] for p in points)
        max_x = max(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_y = max(p[1] for p in points)
        size = [max_x - min_x, max_y - min_y]
        return _anchor_offset_box(size, anchor)
    elif atype_enum == AnchorType.INTERSECT:
        d = _dir2(anchor)
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
        return _anchor_offset_hull(points, anchor)
    else:
        return _anchor_offset_hull(points, anchor)


def _frag_count(
    radius: float,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> int:
    """
    Number of polygon segments to approximate a circle of radius *radius*, mirroring OpenSCAD's
    $fn/$fa/$fs rules.
    """
    if fn is not None and fn >= 3:
        return int(math.floor(fn))
    fa = fa if fa else 12.0
    fs = fs if fs else 2.0
    return max(5, int(math.ceil(min(360.0 / fa, (2 * math.pi * abs(radius)) / fs))))


def _quant(x: float, y: float) -> float:
    return math.ceil(x / y) * y


def _polar_to_xy(radius: float, angle: float) -> list[float]:
    rad = math.radians(angle)
    return [radius * math.cos(rad), radius * math.sin(rad)]


def _rotate2d(point: Sequence[float], degrees: float) -> list[float]:
    rad = math.radians(degrees)
    c, s = math.cos(rad), math.sin(rad)
    return [point[0] * c - point[1] * s, point[0] * s + point[1] * c]


def _circle_pts(radius: float, count: int, start: float = 0.0) -> list[list[float]]:
    return [_polar_to_xy(radius, start + 360.0 * i / count) for i in range(count)]


def _arc_points(
    count: int,
    radius: float,
    start: float,
    angle: float,
    center: Sequence[float] = (0.0, 0.0),
    endpoint: bool = True,
) -> list[list[float]]:
    """
    *count* points along an arc of radius *radius* centered at *center*, from angle *start*
    sweeping *angle* degrees.
    """
    if not endpoint:
        return _arc_points(count + 1, radius, start, angle, center, True)[:-1]
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


def _arc_between_points(
    center: Sequence[float],
    point_start: Sequence[float],
    point_end: Sequence[float],
    radius: float,
    endpoint: bool = True,
    fn=None,
    fa=None,
    fs=None,
) -> list[list[float]]:
    """Arc around *center* from *point_start* to *point_end*, sweeping the shorter way around."""
    a0 = math.degrees(math.atan2(point_start[1] - center[1], point_start[0] - center[0]))
    a1 = math.degrees(math.atan2(point_end[1] - center[1], point_end[0] - center[0]))
    delta = (a1 - a0 + 180) % 360 - 180
    count = max(3, math.ceil(_frag_count(radius, fn, fa, fs) * abs(delta) / 360))
    return _arc_points(count, radius, a0, delta, center, endpoint=endpoint)


def _arc_through_3(
    center: Sequence[float],
    radius: float,
    point_start: Sequence[float],
    point_mid: Sequence[float],
    point_end: Sequence[float],
    endpoint: bool = True,
    fn=None,
    fa=None,
    fs=None,
) -> list[list[float]]:
    """
    Arc around *center* from *point_start* to *point_end*, sweeping through *point_mid* (may be
    the long way around).
    """
    a0 = math.degrees(math.atan2(point_start[1] - center[1], point_start[0] - center[0]))
    am = math.degrees(math.atan2(point_mid[1] - center[1], point_mid[0] - center[0]))
    a1 = math.degrees(math.atan2(point_end[1] - center[1], point_end[0] - center[0]))
    d_mid = (am - a0) % 360
    d_end = (a1 - a0) % 360
    delta = d_end if d_mid <= d_end else d_end - 360
    count = max(3, math.ceil(_frag_count(radius, fn, fa, fs) * abs(delta) / 360))
    return _arc_points(count, radius, a0, delta, center, endpoint=endpoint)


@overload
def _pick_radius(
    radius1: float | None = None,
    diameter1: float | None = None,
    radius2: float | None = None,
    diameter2: float | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    *,
    dflt: float,
) -> float: ...
@overload
def _pick_radius(
    radius1: float | None = None,
    diameter1: float | None = None,
    radius2: float | None = None,
    diameter2: float | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    dflt: None = None,
) -> float | None: ...
@overload
def _pick_radius(
    radius1: float | None = None,
    diameter1: float | None = None,
    radius2: float | None = None,
    diameter2: float | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    *,
    dflt: float | None = None,
) -> float | None: ...
def _pick_radius(
    radius1=None,
    diameter1=None,
    radius2=None,
    diameter2=None,
    radius=None,
    diameter=None,
    dflt=None,
):
    """
    Mirror BOSL2's get_radius(): (radius1,diameter1) > (radius2,diameter2) > (radius,diameter) >
    dflt.
    """
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


def _circle_from_3pts(points: Sequence[Sequence[float]]) -> tuple[list[float], float]:
    (x1, y1), (x2, y2), (x3, y3) = points
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / d
    uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / d
    return [ux, uy], math.hypot(x1 - ux, y1 - uy)


def _circle_from_corner(corner: Sequence[Sequence[float]], radius: float) -> list[float]:
    p0, p1, p2 = corner
    v1 = unit([p0[0] - p1[0], p0[1] - p1[1]])
    v2 = unit([p2[0] - p1[0], p2[1] - p1[1]])
    bis = unit([v1[0] + v2[0], v1[1] + v2[1]])
    half_ang = math.acos(max(-1.0, min(1.0, v1[0] * bis[0] + v1[1] * bis[1])))
    dist = radius / math.sin(half_ang)
    return [p1[0] + bis[0] * dist, p1[1] + bis[1] * dist]


def _circle_circle_intersection(
    radius1: float, center1: Sequence[float], radius2: float, center2: Sequence[float]
) -> list[list[float]]:
    d = math.dist(center1, center2)
    if d == 0 or d > radius1 + radius2 or d < abs(radius1 - radius2):
        return []
    a = (radius1**2 - radius2**2 + d**2) / (2 * d)
    h_sq = radius1**2 - a**2
    if h_sq < 0:
        return []
    h = math.sqrt(h_sq)
    xm = center1[0] + a * (center2[0] - center1[0]) / d
    ym = center1[1] + a * (center2[1] - center1[1]) / d
    dx = h * (center2[1] - center1[1]) / d
    dy = h * (center2[0] - center1[0]) / d
    return [[xm + dx, ym - dy], [xm - dx, ym + dy]]


def _adjacent_angle_to_hypotenuse(adjacent: float, angle: float) -> float:
    return adjacent / math.cos(math.radians(angle))


def _adjacent_angle_to_opposite(adjacent: float, angle: float) -> float:
    return adjacent * math.tan(math.radians(angle))


def _opposite_angle_to_adjacent(opposite: float, angle: float) -> float:
    return opposite / math.tan(math.radians(angle))


def _v_theta(vec: Sequence[float]) -> float:
    return math.degrees(math.atan2(vec[1], vec[0]))


def _det2(vec_a: Sequence[float] | np.ndarray, vec_b: Sequence[float] | np.ndarray) -> float:
    """The 2-D cross product a x b -- sign gives the turn direction (z of the 3-D cross)."""
    return float(vec_a[0] * vec_b[1] - vec_a[1] * vec_b[0])


def _sign(value: float) -> int:
    value = float(value)
    return (value > 0) - (value < 0)


def _vector_angle(point_a: Sequence[float], point_b: Sequence[float], point_c: Sequence[float]) -> float:
    """The angle in degrees at vertex *b* of the corner a-b-c."""
    va = np.asarray(point_a, dtype=float) - np.asarray(point_b, dtype=float)
    vc = np.asarray(point_c, dtype=float) - np.asarray(point_b, dtype=float)
    cosv = float(np.dot(va, vc)) / (float(np.linalg.norm(va)) * float(np.linalg.norm(vc)))
    return math.degrees(math.acos(max(-1.0, min(1.0, cosv))))


def _dir2(anchor: Sequence[float]) -> list[float]:
    a = list(anchor) + [0, 0, 0]
    return [a[0], a[1] + a[2]]


def _anchor_offset_box(size: Sequence[float], anchor: Sequence[float]) -> list[float]:
    d = _dir2(anchor)
    return [-d[0] * size[0] / 2, -d[1] * size[1] / 2]


def _anchor_offset_hull(points: Sequence[Sequence[float]], anchor: Sequence[float]) -> list[float]:
    d = _dir2(anchor)
    if d[0] == 0 and d[1] == 0:
        return [0.0, 0.0]
    best = max(points, key=lambda p: p[0] * d[0] + p[1] * d[1])
    return [-best[0], -best[1]]


def _finish(
    shape: PyOpenSCAD,
    offset: Sequence[float],
    spin: float,
    size: Sequence[float] | None = None,
    anchor: Sequence[float] | None = None,
) -> "Bosl2Shape2D":
    """Anchor-translate and spin a freshly built native 2-D shape, then wrap it.

    Every shape constructor in this file funnels through here, which is what makes them all
    return a :class:`Bosl2Shape2D` rather than a bare native handle. *size*/*anchor* are the
    nominal box metadata to carry on the wrapper, for the shapes that have one. A shape that is
    already wrapped (``ring()`` composes two circles) is unwrapped first, never double-wrapped.
    """
    shape = Bosl2Shape2D._unwrap(shape)
    if offset[0] != 0 or offset[1] != 0:
        shape = shape.translate(offset)
    if spin:
        # Native 2-D rotate needs the 3-vector form; a bare scalar is rejected.
        shape = shape.rotate([0, 0, spin])
    return Bosl2Shape2D(shape, size=size, anchor=anchor)


# ---------------------------------------------------------------------------
# Section: Base class
# ---------------------------------------------------------------------------

#: Anything the 2-D operators accept as a child: a :class:`Bosl2Shape2D`, a raw native 2-D handle,
#: a :class:`~pybosl2.paths.Path` / :class:`~pybosl2.regions.Region`, or a ``[[x, y], ...]`` point list.
#: :func:`_as_native_2d` reduces any of them to a raw native handle.
Shape2DLike = Union["Bosl2Shape2D", "PyOpenSCAD", Path, Sequence[Sequence[float]]]


class Bosl2Shape2D(Distributable, Colorable):
    """Wraps a native PyOpenSCAD **2-D** shape, giving it the same fluent, chainable API that
    :class:`~pybosl2.shapes3d.Bosl2Solid` gives 3-D solids. Every shape constructor in this file
    returns one of these, as do :meth:`~pybosl2.paths.Path.polygon` and
    :meth:`~pybosl2.regions.Region.geometry`.

    The 2-D specific operations live here rather than being reached for through the raw native
    handle:

    * :meth:`fill` -- drop every hole, keeping only the outermost outline (OpenSCAD ``fill()``).
    * :meth:`hull` -- the convex hull of this shape, optionally together with more shapes/paths
      (OpenSCAD ``hull()``).
    * :meth:`offset` -- inset/outset, with BOSL2's ``radius=``/``delta=`` spelling (the native
      ``offset()`` only understands ``r=``).
    * :meth:`linear_extrude` / :meth:`rotate_extrude` -- the 2-D -> 3-D operators, which return a
      :class:`~pybosl2.shapes3d.Bosl2Solid` so the result keeps the 3-D fluent API.

    Transforms (translate/rotate/mirror/scale/multmatrix), the CSG operators (``|``, ``&``, ``-``),
    the colour operators (from :class:`~pybosl2.color.Colorable`) and the distributor copiers (from
    :class:`~pybosl2.distributors.Distributable`) all return a new ``Bosl2Shape2D``. Anything else
    falls through ``__getattr__`` to the native handle, re-wrapped as 2-D when it hands back native
    geometry.

    Like :class:`~pybosl2.shapes3d.Bosl2Solid` this is composition, not a subclass of the native
    C-extension type: passing one *directly* into a native function that wants a raw handle needs
    an explicit ``.shape`` (or :func:`pybosl2._helpers.unwrap`).
    """

    #: which realize backend produced this shape -- 2-D geometry is exact-CSG only (see
    #: pybosl2/_backend.py); the SDF backend has no 2-D surface.
    backend = "csg"

    def __init__(
        self,
        shape: PyOpenSCAD,
        size: Sequence[float] | None = None,
        anchor: "Sequence[float] | str | None" = None,
    ):
        self.shape = shape
        #: nominal [x, y] size for the shapes that have a genuine box size, else None
        self.size = None if size is None else [float(v) for v in size][:2]
        self.anchor = anchor if anchor is not None else CENTER
        # True once a positional transform has been applied, so `size`/`anchor` no longer
        # describe where the shape actually is (same flag Bosl2Solid tracks).
        self._moved = False

    @staticmethod
    def _unwrap(x: "Bosl2Shape2D | Bosl2Solid | PyOpenSCAD") -> "PyOpenSCAD":
        """The raw native handle behind *x* (a Bosl2Shape2D/Bosl2Solid), or *x* unchanged."""
        from pybosl2._helpers import unwrap

        return unwrap(x)

    def _wrap(self, new_shape: PyOpenSCAD) -> "Bosl2Shape2D":
        """Wrap a native result, carrying size/anchor metadata (and moved-ness) forward."""
        out = Bosl2Shape2D(new_shape, self.size, self.anchor)
        out._moved = self._moved
        return out

    def _wrap_moved(self, new_shape: PyOpenSCAD) -> "Bosl2Shape2D":
        """Wrap a native result of a positional transform, flagging the tracked metadata stale."""
        out = Bosl2Shape2D(new_shape, self.size, self.anchor)
        out._moved = True
        return out

    def __getattr__(self, name: str) -> Any:
        # __getattr__ only fires on a normal-lookup miss. Guard the recursion trap: never bounce
        # back through here for `shape` (or dunders) when the object is half-built, so
        # copy/pickle/hasattr raise a clean AttributeError instead of blowing the stack.
        if name == "shape" or (name.startswith("__") and name.endswith("__")):
            raise AttributeError(name)
        _unsupported = _unsupported_feature("csg", name)  # SDF-only feature on the CSG backend?
        if _unsupported is not None:
            raise _unsupported
        shape = object.__getattribute__(self, "shape")  # bypass __getattr__: no recursion
        attr = getattr(shape, name)
        if not callable(attr):
            return attr  # plain native attr (.position/.size/...)
        native_cls = type(shape)

        def _forward(*args: Any, **kwargs: Any) -> Any:
            # Re-wrap native geometry so a passed-through op keeps the fluent API instead of
            # silently leaking a raw handle. Every 2-D -> 3-D operator is defined explicitly
            # below, so whatever lands here is still 2-D.
            result = attr(*args, **kwargs)
            if isinstance(result, native_cls):
                return self._wrap_moved(result)
            if isinstance(result, (list, tuple)) and result and all(isinstance(r, native_cls) for r in result):
                return type(result)(self._wrap_moved(r) for r in result)
            return result

        _forward.__name__ = name
        return _forward

    def __repr__(self) -> str:
        return f"Bosl2Shape2D({self.shape!r}, size={self.size!r}, anchor={self.anchor!r})"

    # ---- geometry passthrough, preserving size/anchor metadata ----

    def translate(self, v: Sequence[float]) -> "Bosl2Shape2D":
        """Translate by *v* ([x, y], or [x, y, 0])."""
        return self._wrap_moved(self.shape.translate([float(c) for c in v]))

    move = translate

    def rotate(self, *a: Any, **k: Any) -> "Bosl2Shape2D":
        """Rotate about the Z axis. A bare scalar angle is accepted (BOSL2 ``rot(a)``); the native
        2-D rotate only takes the 3-vector form."""
        if len(a) == 1 and isinstance(a[0], numbers.Real) and not isinstance(a[0], bool) and "v" not in k:
            a = ([0.0, 0.0, float(a[0])],)
        return self._wrap_moved(self.shape.rotate(*a, **k))

    rot = rotate
    spin = rotate

    def mirror(self, v: Sequence[float]) -> "Bosl2Shape2D":
        """Mirror across the line through the origin normal to *v*."""
        return self._wrap_moved(self.shape.mirror([float(c) for c in v]))

    def scale(self, v: "float | Sequence[float]") -> "Bosl2Shape2D":
        """Scale by *v* (a scalar, or [x, y])."""
        return self._wrap_moved(self.shape.scale(v))

    def multmatrix(self, m: Sequence[Sequence[float]]) -> "Bosl2Shape2D":
        return self._wrap_moved(self.shape.multmatrix(m))

    # Directional translates (BOSL2 transforms.scad): right/left +/-X, back/fwd +/-Y.

    def right(self, x: float) -> "Bosl2Shape2D":
        return self.translate([x, 0.0])

    def left(self, x: float) -> "Bosl2Shape2D":
        return self.translate([-x, 0.0])

    def back(self, y: float) -> "Bosl2Shape2D":
        return self.translate([0.0, y])

    def forward(self, y: float) -> "Bosl2Shape2D":
        return self.translate([0.0, -y])

    fwd = forward

    def xflip(self, x: float = 0.0) -> "Bosl2Shape2D":
        """Mirror across the vertical line at *x* (BOSL2 xflip())."""
        return self.translate([-x, 0.0]).mirror([1, 0]).translate([x, 0.0])

    def yflip(self, y: float = 0.0) -> "Bosl2Shape2D":
        """Mirror across the horizontal line at *y* (BOSL2 yflip())."""
        return self.translate([0.0, -y]).mirror([0, 1]).translate([0.0, y])

    # ---- 2-D operators ----

    def offset(
        self,
        radius: float | None = None,
        delta: float | None = None,
        chamfer: bool = False,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Bosl2Shape2D":
        """Inset (negative) or outset (positive) the outline.

        *radius* rounds the joins it creates, *delta* keeps them sharp (or bevels them with
        ``chamfer=True``) -- BOSL2's spelling of OpenSCAD's ``r=``/``delta=``. Give exactly one.
        """
        assert (radius is None) != (delta is None), "offset(): give exactly one of radius= or delta=."
        kw: dict[str, Any] = {"r": radius} if radius is not None else {"delta": delta, "chamfer": chamfer}
        for name, value in (("fn", fn), ("fa", fa), ("fs", fs)):
            if value is not None:
                kw[name] = value
        # The offset moves the outline, so the nominal box size no longer describes it.
        return self._wrap_moved(self.shape.offset(**kw))

    def fill(self) -> "Bosl2Shape2D":
        """This shape with every hole filled in -- only the outermost outline survives
        (OpenSCAD ``fill()``).

        Useful for recovering the solid footprint of a shape you have already punched holes in,
        e.g. to build a backing plate for it, or to close up the interior loops of ``text()``.

        Examples:
            .. pythonscad-example::

                plate = s2.square(40) - s2.circle(radius=8)
                plate.fill().linear_extrude(height=2).show()
        """
        return self._wrap(_ofill(self.shape))

    def hull(self, *others: "Shape2DLike") -> "Bosl2Shape2D":
        """The convex hull of this shape (OpenSCAD ``hull()``).

        With arguments, the hull of this shape *together with* each of *others* -- any mix of
        ``Bosl2Shape2D``, native 2-D shapes, :class:`~pybosl2.paths.Path` /
        :class:`~pybosl2.regions.Region`, or plain ``[[x, y], ...]`` point lists.

        Examples:
            .. pythonscad-example::

                slot = s2.circle(radius=5).hull(s2.circle(radius=5).right(30))
                slot.linear_extrude(height=3).show()
        """
        return Bosl2Shape2D(_ohull(self.shape, *[_as_native_2d(o) for o in others]))

    # ---- 2-D -> 3-D (returns a Bosl2Solid) ----

    def linear_extrude(
        self,
        height: float,
        center: bool = False,
        twist: float = 0.0,
        scale: "float | Sequence[float]" = 1,
        slices: int | None = None,
        convexity: int | None = None,
        **kwargs: Any,
    ) -> "Bosl2Solid":
        """Extrude this 2-D shape *height* along +Z into a 3-D solid.

        Args:
            height:    extrusion height
            center:    centre the result on z=0 rather than starting at z=0 (default False)
            twist:     degrees to rotate the top face relative to the bottom (default 0)
            scale:     scale factor of the top face, a scalar or [x, y] (default 1)
            slices:    number of intermediate layers (default: from the twist)
            convexity: rendering hint for self-overlapping cross-sections
            kwargs:    any further native ``linear_extrude()`` parameter (``origin``, ``fn``, ...)

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid`.

        Examples:
            .. pythonscad-example::

                s2.star(n=5, r=30, ir=15).linear_extrude(height=6, twist=45).show()
        """
        from pybosl2.shapes3d import Bosl2Solid

        kw: dict[str, Any] = {
            "height": height,
            "center": center,
            "twist": twist,
            "scale": scale,
        }
        if slices is not None:
            kw["slices"] = slices
        if convexity is not None:
            kw["convexity"] = convexity
        kw.update(kwargs)
        size = None if self.size is None else [self.size[0], self.size[1], float(height)]
        return Bosl2Solid(self.shape.linear_extrude(**kw), size=size)

    def rotate_extrude(
        self,
        angle: float = 360.0,
        convexity: int | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
        **kwargs: Any,
    ) -> "Bosl2Solid":
        """Revolve this 2-D shape about the Y axis into a 3-D solid (OpenSCAD ``rotate_extrude()``).

        The shape must lie entirely on one side of the axis. *angle* sweeps less than a full
        revolution.

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid`.
        """
        from pybosl2.shapes3d import Bosl2Solid

        kw: dict[str, Any] = {"angle": angle}
        for name, value in (
            ("convexity", convexity),
            ("fn", fn),
            ("fa", fa),
            ("fs", fs),
        ):
            if value is not None:
                kw[name] = value
        kw.update(kwargs)
        return Bosl2Solid(self.shape.rotate_extrude(**kw))

    def path_extrude(self, path: Sequence[Sequence[float]], **kwargs: Any) -> "Bosl2Solid":
        """Sweep this 2-D shape along *path* (a :class:`~pybosl2.paths.Path3D` or point list), via
        the native ``path_extrude()``.

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid`.
        """
        from pybosl2.shapes3d import Bosl2Solid

        pts = [[float(c) for c in p] for p in path]
        return Bosl2Solid(self.shape.path_extrude(pts, **kwargs))

    # ---- colour (pybosl2/color.py) ----

    def _color_native(self, c: "str | Sequence[float] | None" = None, alpha: float | None = None) -> "Bosl2Shape2D":
        args = () if c is None else (c,)
        kw = {} if alpha is None else {"alpha": alpha}
        return self._wrap(self.shape.color(*args, **kw))

    def _highlight_native(self) -> "Bosl2Shape2D":
        return self._wrap(self.shape.highlight())

    def _ghost_native(self) -> "Bosl2Shape2D":
        return self._wrap(self.shape.background())

    # ---- CSG ----

    def __or__(self, other: "Shape2DLike") -> "Bosl2Shape2D":
        _check_operand_backend("csg", other)
        return self._wrap(self.shape | Bosl2Shape2D._unwrap(other))

    def __and__(self, other: "Shape2DLike") -> "Bosl2Shape2D":
        _check_operand_backend("csg", other)
        return self._wrap(self.shape & Bosl2Shape2D._unwrap(other))

    def __sub__(self, other: "Shape2DLike") -> "Bosl2Shape2D":
        _check_operand_backend("csg", other)
        return self._wrap(self.shape - Bosl2Shape2D._unwrap(other))

    def __ror__(self, other: "Shape2DLike") -> "Bosl2Shape2D":
        _check_operand_backend("csg", other)
        return self._wrap(Bosl2Shape2D._unwrap(other) | self.shape)

    def __rand__(self, other: "Shape2DLike") -> "Bosl2Shape2D":
        _check_operand_backend("csg", other)
        return self._wrap(Bosl2Shape2D._unwrap(other) & self.shape)

    def __rsub__(self, other: "Shape2DLike") -> "Bosl2Shape2D":
        _check_operand_backend("csg", other)
        return self._wrap(Bosl2Shape2D._unwrap(other) - self.shape)

    # ---- distributors (pybosl2/distributors.py) ----

    def _distribute(self, mats: Sequence[Sequence[Sequence[float]]]) -> "Bosl2Shape2D":
        """Union a multmatrix copy of this shape for each transform matrix (BOSL2's module form).

        The copiers that lift out of the XY plane (``zcopies``, ``xrot_copies``, ...) have no
        meaning for 2-D geometry and are rejected rather than silently flattened.
        """
        assert len(mats), "distributor produced no copies."
        out = None
        for m in mats:
            m4 = np.asarray(m, dtype=float)
            assert abs(float(m4[2, 3])) < 1e-9 and abs(float(m4[2, 2]) - 1.0) < 1e-9, (
                "this copier moves the 2-D shape out of the XY plane; extrude it to 3-D first"
            )
            copy = self.shape.multmatrix(m4.tolist())
            out = copy if out is None else out | copy
        return self._wrap_moved(out)

    # ---- bounding box ----

    def bounds(self) -> "tuple[list[float], list[float]]":
        """This shape's axis-aligned bounding box as ``(center, size)`` -- both ``[x, y]`` float
        lists in the shape's current frame (the 2-D form of
        :meth:`~pybosl2.shapes3d.Bosl2Solid.bounds`).

        Prefers the native bbox, which always reflects the current geometry; falls back to the
        tracked nominal size/anchor when the native accessors aren't available (the numeric test
        mock) and the shape hasn't been moved since construction.
        """
        try:
            pos, sz = self.shape.position, self.shape.size
        except AttributeError:
            pos = sz = None
        if pos is not None and sz is not None:
            mincorner = [float(pos[i]) for i in range(2)]
            size = [float(sz[i]) for i in range(2)]
            return [mincorner[i] + size[i] / 2 for i in range(2)], size
        if self.size is not None and not isinstance(self.anchor, str):
            if self._moved:
                raise ValueError(
                    "bounds(): no native bounding box (numeric mock) and the shape has been "
                    "transformed since construction, so its tracked metadata is stale."
                )
            size = [float(v) for v in self.size]
            return _anchor_offset_box(size, self.anchor), size
        raise ValueError("bounds(): the shape has no native bounding box and no tracked size metadata.")


def _as_native_2d(obj: "Shape2DLike") -> "PyOpenSCAD":
    """A raw native 2-D handle from *obj*: a Bosl2Shape2D/Bosl2Solid wrapper, a native shape, a
    :class:`~pybosl2.paths.Path` / :class:`~pybosl2.regions.Region`, or a plain point list.
    """
    from pybosl2._helpers import unwrap

    unwrapped = unwrap(obj)
    if unwrapped is not obj:  # a Bosl2Shape2D / Bosl2Solid wrapper
        return unwrapped
    geom = getattr(obj, "geometry", None)  # Path / Region
    if callable(geom):
        return unwrap(geom())
    if isinstance(obj, (list, tuple, np.ndarray)):  # a bare [[x, y], ...] point list
        return _opolygon([[float(p[0]), float(p[1])] for p in obj])
    return obj


def _is_child_2d(obj: "Shape2DLike | Sequence[Shape2DLike]") -> bool:
    """True if *obj* is a single 2-D child rather than a container of children -- a wrapper or
    native shape, a Path/Region (which are ``list`` subclasses), or a ``[[x, y], ...]`` list.
    """
    if not isinstance(obj, (list, tuple)):
        return True  # a wrapper or a native handle
    if callable(getattr(obj, "geometry", None)):
        return True  # Path / Region
    return bool(len(obj)) and isinstance(obj[0], (list, tuple, np.ndarray)) and len(obj[0]) == 2


def fill(children: "Shape2DLike") -> Bosl2Shape2D:
    """*children* with every hole filled in -- only the outermost outline survives
    (OpenSCAD ``fill()``, the module form of :meth:`Bosl2Shape2D.fill`).

    Args:
        children: the 2-D shape to fill (a ``Bosl2Shape2D``, a native shape, a
                  :class:`~pybosl2.paths.Path` / :class:`~pybosl2.regions.Region`, or a point list)
    """
    return Bosl2Shape2D(_ofill(_as_native_2d(children)))


def hull(*children: "Shape2DLike | Sequence[Shape2DLike]") -> Bosl2Shape2D:
    """The 2-D convex hull of *children* (OpenSCAD ``hull()``, the module form of
    :meth:`Bosl2Shape2D.hull`).

    Args:
        children: the 2-D shapes to hull -- any mix of ``Bosl2Shape2D``, native shapes,
                  :class:`~pybosl2.paths.Path` / :class:`~pybosl2.regions.Region`, or point lists.
                  A single list/tuple *of* shapes is also accepted.
    """
    items = list(children)
    if len(items) == 1 and not _is_child_2d(items[0]):
        items = list(items[0])  # a single list *of* shapes
    assert items, "hull(): needs at least one child."
    return Bosl2Shape2D(_ohull(*[_as_native_2d(c) for c in items]))


# ---------------------------------------------------------------------------
# Section: 2D Primitives
# ---------------------------------------------------------------------------


def square(
    size: float | Sequence[float] = 1,
    center: bool | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float | None = None,
) -> Bosl2Shape2D:
    """A rectangle, built with the builtin square(), with BOSL2-style anchor/spin support.

    Args:
        size:   size of the square; a scalar uses the same size for X and Y
        center: if given, overrides anchor (True -> CENTER, False -> FRONT+LEFT)
        anchor: anchor point (default CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)
    """
    sz = [float(size), float(size)] if isinstance(size, (int, float)) else [float(v) for v in size]
    use_anchor = anchor
    if center is not None:
        use_anchor = CENTER if center else [-1, -1, 0]
    shape = _osquare(sz, center=True)
    offset = _anchor_offset_box(sz, use_anchor)
    return _finish(shape, offset, spin or 0, size=sz, anchor=use_anchor)


def _rect_path(
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
    assert insets_x <= sx, "Requested roundings and/or chamfers exceed the rect width."
    assert insets_y <= sy, "Requested roundings and/or chamfers exceed the rect height."
    path = []
    for i in range(4):
        quad = quadorder[i]
        qinset = insets[quad]
        qpos = quadpos[quad]
        qchamf = chamfer_l[quad]
        qround = rounding_l[quad]
        cverts = int(_quant(_frag_count(abs(qinset), fn, fa, fs), 4) / 4) if abs(qinset) >= eps else 0
        step = 90.0 / cverts if cverts else 0.0
        center = [(sx / 2 - qinset) * qpos[0], (sy / 2 - abs(qinset)) * qpos[1]]
        if abs(qchamf) >= eps:
            qpts = [[0, abs(qinset)], [qinset, 0]]
        elif abs(qround) >= eps:
            sign = 1 if qinset >= 0 else -1
            qpts = []
            for j in range(cverts + 1):
                a = 90 - j * step
                p = _polar_to_xy(abs(qinset), a)
                qpts.append([p[0] * sign, p[1]])
        else:
            qpts = [[0, 0]]
        qfpts = [[p[0] * qpos[0], p[1] * qpos[1]] for p in qpts]
        qrpts = list(reversed(qfpts)) if qpos[0] * qpos[1] < 0 else qfpts
        for p in qrpts:
            path.append([p[0] + center[0], p[1] + center[1]])
    return path


def rect(
    size: float | Sequence[float] = 1,
    rounding: float | Sequence[float] = 0,
    atype: str = "box",
    chamfer: float | Sequence[float] = 0,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """A rectangle with optional rounded or chamfered corners.

    Note: negative rounding/chamfer (BOSL2's "external roundover spikes") is not supported here.

    Args:
        size:     size of the rectangle; a scalar uses the same size for X and Y
        rounding: corner rounding radius, or per-corner list [X+Y+,X-Y+,X-Y-,X+Y-] (default 0)
        atype:    anchor type, "box" (bounding box) or "perim" (rounded/chamfered perimeter) (default "box")
        chamfer:  corner chamfer size, or per-corner list [X+Y+,X-Y+,X-Y-,X+Y-] (default 0)
        anchor:   anchor point (default CENTER)
        spin:     Z-axis rotation in degrees after anchor (default 0)
        fn/fa/fs: arc smoothness overrides for rounded corners
    """
    sz = [float(size), float(size)] if isinstance(size, (int, float)) else list(size)
    path = _rect_path(sz, rounding=rounding, chamfer=chamfer, fn=fn, fa=fa, fs=fs)
    shape = _opolygon(path)
    complex_shape = (rounding != 0 if isinstance(rounding, (int, float)) else any(rounding)) or (
        chamfer != 0 if isinstance(chamfer, (int, float)) else any(chamfer)
    )
    if complex_shape and atype == "perim":
        offset = _anchor_offset_hull(path, anchor)
        return _finish(shape, offset, spin)
    offset = _anchor_offset_box(sz, anchor)
    return _finish(shape, offset, spin, size=sz, anchor=anchor)


def rect_path(
    size: float | Sequence[float] = 1,
    rounding: float | Sequence[float] = 0,
    chamfer: float | Sequence[float] = 0,
    anchor: Sequence[float] = CENTER,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> list[list[float]]:
    """The *points* of a (optionally rounded/chamfered) rectangle -- BOSL2's ``rect()`` in its
    function form, as opposed to :func:`rect` which returns 2-D geometry (a :class:`Bosl2Shape2D`).

    Use this when the rectangle is an input to further path math (e.g. a profile fed to
    :func:`base_bgtk.PolygonPrism`), not something to draw.

    Usage::

        rect_path([20, 4], rounding=[-3, -3, 0, 0], anchor=TOP + LEFT)

    Args:
        size:     [x, y] size (or a single number for a square)
        rounding: corner radius; a single value or per-corner list. Negative = concave.
        chamfer:  corner chamfer; a single value or per-corner list
        anchor:   BOSL2 anchor the path is translated onto (default CENTER)

    Note:
        For small radii this can emit one more point per corner than the real BOSL2 does
        (BOSL2 rounds the corner-arc segment count, this rounds up); the arc geometry is
        identical, only the sampling differs.
    """
    sz = [float(size), float(size)] if isinstance(size, (int, float)) else [float(v) for v in size]
    path = _rect_path(sz, rounding=rounding, chamfer=chamfer, fn=fn, fa=fa, fs=fs)
    offset = _anchor_offset_box(sz, anchor)
    return [[float(p[0]) + offset[0], float(p[1]) + offset[1]] for p in path]


def arc(
    count: int | None = None,
    radius: float | None = None,
    angle: float | Sequence[float] | None = None,
    diameter: float | None = None,
    center: Sequence[float] | None = None,
    points: Sequence[Sequence[float]] | None = None,
    corner: Sequence[Sequence[float]] | None = None,
    width: float | None = None,
    thickness: float | None = None,
    start: float | None = None,
    wedge: bool = False,
    long: bool = False,
    clockwise: bool = False,
    counterclockwise: bool = False,
    endpoint: bool = True,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Path:
    """A 2-D arc, returned as a :class:`~pybosl2.paths.Path` of points (BOSL2's ``arc()``).

    All of BOSL2's 2-D arc specifications are supported (3-D arcs, which project onto a plane,
    are not):

    * ``arc(radius=, angle=, [start=], [center=])`` -- radius about *center*, sweeping *angle* degrees from
      *start* (or ``angle=[start, end]`` for an explicit range).
    * ``arc(width=, thickness=)`` -- a circular segment starting and ending on the X axis.
    * ``arc(center=, points=[P0, P1])`` -- around *center* from ``P0`` toward the direction of ``P1``; the
      short way by default, or the long/``clockwise``/``counterclockwise`` way.
    * ``arc(points=[P0, P1, P2])`` -- through three points, from ``P0`` via ``P1`` to ``P2``.
    * ``arc(corner=[P0, P1, P2], radius=)`` -- the fillet arc of radius tangent to both legs of the
      corner ``P0-P1-P2``.

    Set ``wedge=True`` to prepend the centre point, giving a closed pie/sector path. When *count* is
    omitted the point count follows OpenSCAD's $fn/$fa/$fs rules, matching BOSL2.

    Args:
        count:      number of points (default: from $fn/$fa/$fs)
        radius/diameter: radius / diameter of the arc
        angle:      degrees to sweep from *start*, or ``[start, end]``
        center:     centre point (default ``[0, 0]``)
        points:     two points (with *center*) or three points the arc passes through
        corner:     three points; the arc is the radius fillet tangent to both legs
        width:      chord width for the width/thickness form
        thickness:  height of the circular segment for the width/thickness form
        start:      starting angle in degrees (default 0)
        wedge:      prepend the centre point, producing a closed sector (default False)
        long/clockwise/counterclockwise: for the two-point form, take the long way / a given handedness
        endpoint:   include the final point (default True)

    Returns:
        A :class:`~pybosl2.paths.Path` (closed when *wedge* is set).
    """
    # -- width + thickness: a circular segment through 3 points on/above the X axis ----------
    if width is not None and thickness is not None:
        assert not any(v is not None for v in (radius, center, points, angle, start)), "conflicting arc() params"
        return arc(
            count=count,
            points=[[width / 2, 0], [0, thickness], [-width / 2, 0]],
            wedge=wedge,
            endpoint=endpoint,
            fn=fn,
            fa=fa,
            fs=fs,
        )

    # -- corner: the fillet arc tangent to both legs of a 3-point corner ---------------------
    if corner is not None:
        assert len(corner) == 3, "corner= needs exactly 3 points"
        assert not is_collinear(corner[0], corner[1], corner[2]), "Collinear corner does not define an arc"
        rad = _pick_radius(radius=radius, diameter=diameter)
        assert rad is not None and rad > 0, "arc(corner=) needs radius= or diameter="
        p0, p1, p2 = (np.asarray(p, dtype=float) for p in corner)
        v1, v2 = unit(p0 - p1), unit(p2 - p1)
        half = math.acos(max(-1.0, min(1.0, float(np.dot(v1, v2))))) / 2
        d_tan = rad / math.tan(half)
        cp2 = _circle_from_corner(corner, rad)
        tp1, tp2 = p1 + v1 * d_tan, p1 + v2 * d_tan
        forward = _det2(p1 - p0, p2 - p1) > 0
        c0, c1 = (tp1, tp2) if forward else (tp2, tp1)
        ts = math.degrees(math.atan2(c0[1] - cp2[1], c0[0] - cp2[0]))
        te = math.degrees(math.atan2(c1[1] - cp2[1], c1[0] - cp2[0]))
        sweep = (te - ts) % 360
        rng = [ts, ts + sweep] if forward else [ts + sweep, ts]
        return arc(
            count=count,
            center=cp2,
            radius=rad,
            angle=rng,
            wedge=wedge,
            endpoint=endpoint,
            fn=fn,
            fa=fa,
            fs=fs,
        )

    # -- points forms ------------------------------------------------------------------------
    if points is not None:
        pts = [[float(p[0]), float(p[1])] for p in points]
        assert all(len(p) == 2 for p in points), "arc() port handles 2-D points only"
        if len(pts) == 2:
            assert center is not None, "center= is required when points has length 2"
            assert pts[0] != pts[1], "arc endpoints are equal"
            centre = [float(center[0]), float(center[1])]
            v1 = np.asarray(pts[0]) - np.asarray(centre)
            v2 = np.asarray(pts[1]) - np.asarray(centre)
            angle_val = _vector_angle(pts[0], centre, pts[1])
            prelim = _sign(_det2(v1, v2))
            if prelim != 0:
                direction = prelim
            else:
                assert clockwise or counterclockwise, "Collinear inputs don't define a unique arc"
                direction = 1
            rad = float(np.hypot(v1[0], v1[1]))
            if long or (counterclockwise and direction < 0) or (clockwise and direction > 0):
                final_angle = -direction * (360 - angle_val)
            else:
                final_angle = direction * angle_val
            sa = math.degrees(math.atan2(v1[1], v1[0]))
            return arc(
                count=count,
                center=centre,
                radius=rad,
                start=sa,
                angle=final_angle,
                wedge=wedge,
                endpoint=endpoint,
                fn=fn,
                fa=fa,
                fs=fs,
            )
        assert len(pts) == 3, f"arc(points=) needs 2 or 3 points, got {len(pts)}"
        assert not is_collinear(pts[0], pts[1], pts[2]), "Collinear inputs do not define an arc"
        centre, arc_radius = _circle_from_3pts(pts)
        a0 = math.degrees(math.atan2(pts[0][1] - centre[1], pts[0][0] - centre[0]))
        am = math.degrees(math.atan2(pts[1][1] - centre[1], pts[1][0] - centre[0]))
        a1 = math.degrees(math.atan2(pts[2][1] - centre[1], pts[2][0] - centre[0]))
        d_mid = (am - a0) % 360
        d_end = (a1 - a0) % 360
        delta = d_end if d_mid <= d_end else d_end - 360
        point_count = (
            count if count is not None else max(3, math.ceil(_frag_count(arc_radius, fn, fa, fs) * abs(delta) / 360))
        )
        out = _arc_points(point_count, arc_radius, a0, delta, centre, endpoint=endpoint)
        if wedge:
            out = [list(centre)] + out
        return Path(out, closed=wedge)

    # -- radius + angle (with optional [start, end] range) -----------------------------------
    arc_r: float | None = _pick_radius(radius=radius, diameter=diameter)
    assert arc_r is not None, "arc() needs radius=/diameter=, points=, corner=, or width=/thickness="
    if isinstance(angle, (list, tuple, np.ndarray)):
        assert start is None, "start= is not allowed with angle=[start, end]"
        calc_start = float(angle[0])
        calc_angle = float(angle[1]) - float(angle[0])
    elif isinstance(angle, (int, float)):
        calc_angle = float(angle)
        calc_start = 0.0 if start is None else float(start)
    elif angle is None:
        calc_angle = 360.0
        calc_start = 0.0 if start is None else float(start)
    else:
        raise TypeError(f"angle must be a number, a [start, end] pair, or None, got {type(angle)}")
    calc_center = (0.0, 0.0) if center is None else center
    point_count = count if count is not None else math.ceil(_frag_count(arc_r, fn, fa, fs) * abs(calc_angle) / 360) + 1
    out = _arc_points(point_count, arc_r, calc_start, calc_angle, calc_center, endpoint=endpoint)
    if wedge:
        out = [list(calc_center)] + out
    return Path(out, closed=wedge)


def circle(
    radius: float | None = None,
    diameter: float | None = None,
    points: Sequence[Sequence[float]] | None = None,
    corner: Sequence[Sequence[float]] | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """A circle, built with the builtin circle(), by radius/diameter, or fit to points.

    If `corner` is given three 2-D points, the circle is centered to be tangent to both
    segments of that path, on the inside corner. If `points` is given three 2-D points,
    the circle is centered and sized to pass through all three points. Anchor/spin are
    ignored for the `corner`/`points` forms, matching BOSL2.

    Args:
        radius:   radius of the circle
        diameter: diameter of the circle
        points:   three 2-D points the circle should pass through
        corner:   three 2-D points defining a path the circle should be tangent to
        anchor:   anchor point (default CENTER)
        spin:     Z-axis rotation in degrees after anchor (default 0)
        fn/fa/fs: arc smoothness overrides
    """
    if points is not None:
        center, rad = _circle_from_3pts(points)
        return _finish(_ocircle(r=rad, fn=fn, fa=fa, fs=fs), center, 0)
    if corner is not None:
        rad = radius if radius is not None else (diameter / 2 if diameter is not None else 1)
        center = _circle_from_corner(corner, rad)
        return _finish(_ocircle(r=rad, fn=fn, fa=fa, fs=fs), center, 0)
    rad = radius if radius is not None else (diameter / 2 if diameter is not None else 1)
    shape = _ocircle(r=rad, fn=fn, fa=fa, fs=fs)
    n = _frag_count(rad, fn, fa, fs)
    offset = _anchor_offset_hull(_circle_pts(rad, n), anchor)
    return _finish(shape, offset, spin)


def polygon(
    path: Sequence[Sequence[float]],
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
) -> Bosl2Shape2D:
    """A polygon, built with the builtin polygon(), with anchor/spin support.

    Args:
        path:   polygon path
        anchor: anchor point (default CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)
    """
    return _finish(_opolygon(path), anchor, spin)


def ellipse(
    radius: float | Sequence[float] | None = None,
    diameter: float | Sequence[float] | None = None,
    realign: bool = False,
    circumscribe: bool = False,
    uniform: bool = False,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """An ellipse (approximated as a polygon), built directly with polygon().

    Note: `uniform` (equal-length approximating segments) is not implemented; segments are
    evenly spaced by angle instead.

    Args:
        radius:   radius of the circle, or pair of semi-axes of the ellipse
        diameter: diameter of the circle, or pair giving the full X/Y axis lengths
        realign:  shift the first polygon point off the X+ axis (default False)
        circumscribe: circumscribe rather than inscribe the ideal ellipse (default False)
        anchor:   anchor point (default CENTER)
        spin:     Z-axis rotation in degrees after anchor (default 0)
        fn/fa/fs: arc smoothness overrides
    """
    _ = uniform
    if radius is not None:
        rad = [float(radius), float(radius)] if isinstance(radius, (int, float)) else [float(v) for v in radius]
    elif diameter is not None:
        dd = [float(diameter), float(diameter)] if isinstance(diameter, (int, float)) else [float(v) for v in diameter]
        rad = [dd[0] / 2, dd[1] / 2]
    else:
        rad = [1.0, 1.0]
    n = _frag_count(max(rad), fn, fa, fs)
    scale = 1.0 / math.cos(math.pi / n) if circumscribe else 1.0
    start = (360.0 / n) / 2 if realign else 0.0
    path = [
        [
            rad[0] * scale * math.cos(math.radians(start + 360.0 * i / n)),
            rad[1] * scale * math.sin(math.radians(start + 360.0 * i / n)),
        ]
        for i in range(n)
    ]
    shape = _opolygon(path)
    offset = _anchor_offset_hull(path, anchor)
    return _finish(shape, offset, spin)


# ---------------------------------------------------------------------------
# Section: Polygons
# ---------------------------------------------------------------------------


def _regular_ngon_path(
    sides: int,
    radius: float,
    rounding: float = 0,
    realign: bool = False,
    align_tip: Sequence[float] | None = None,
    align_side: Sequence[float] | None = None,
    fn=None,
    fa=None,
    fs=None,
) -> list[list[float]]:
    if not rounding:
        path = _circle_pts(radius, sides)
    else:
        inset = rounding / math.sin(math.radians((180 - 360.0 / sides) / 2))
        steps = max(1, int(_frag_count(radius, fn, fa, fs) // sides))
        path2 = []
        for i in range(sides):
            a = 360 - i * 360.0 / sides
            p = _polar_to_xy(radius - inset, a)
            path2.extend(_arc_points(steps, rounding, a + 180.0 / sides, -360.0 / sides, p))
        maxx_idx = max(range(len(path2)), key=lambda k: path2[k][0])
        path = path2[maxx_idx:] + path2[:maxx_idx]
    extra_rot = 0.0
    if align_tip is not None:
        extra_rot += math.degrees(math.atan2(align_tip[1], align_tip[0]))
    elif align_side is not None:
        extra_rot += math.degrees(math.atan2(align_side[1], align_side[0])) + 180.0 / sides
    if realign:
        extra_rot -= 180.0 / sides
    if extra_rot:
        path = [_rotate2d(p, extra_rot) for p in path]
    return path


def regular_ngon(
    sides: int = 6,
    radius: float | None = None,
    diameter: float | None = None,
    outer_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_radius: float | None = None,
    inner_diameter: float | None = None,
    side: float | None = None,
    rounding: float = 0,
    realign: bool = False,
    align_tip: Sequence[float] | None = None,
    align_side: Sequence[float] | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """A regular N-gon (equilateral, equiangular polygon), built directly with polygon().

    Note: BOSL2's outer-radius parameter is named `or`, which collides with the Python
    keyword `or`; it is exposed here as `outer_radius` instead.

    Args:
        sides:          number of sides (default 6)
        radius/outer_radius: outside radius, at the points (BOSL2 `or`)
        diameter/outer_diameter: outside diameter, at the points
        inner_radius:   inside radius, at the center of the sides
        inner_diameter: inside diameter, at the center of the sides
        side:           length of each side
        rounding:       rounding radius for the tips of the polygon (default 0)
        realign:        put the midpoint of the last edge (instead of vertex 0) on the X+ axis (default False)
        align_tip:      rotate so the first vertex points in this 2-D direction (applied before spin)
        align_side:     rotate so the normal of side 0 points in this 2-D direction (applied before spin)
        anchor:         anchor point (default CENTER)
        spin:           Z-axis rotation in degrees after anchor (default 0)
        fn/fa/fs:    arc smoothness overrides for rounded tips
    """
    assert sides >= 3
    sc = 1 / math.cos(math.radians(180.0 / sides))
    ir_s = inner_radius * sc if inner_radius is not None else None
    id_s = inner_diameter * sc if inner_diameter is not None else None
    side_s = side / 2 / math.sin(math.radians(180.0 / sides)) if side is not None else None
    dflt_val: float = side_s if side_s is not None else 0.0
    rad = _pick_radius(
        radius1=ir_s,
        diameter1=id_s,
        radius2=outer_radius,
        diameter2=outer_diameter,
        radius=radius,
        diameter=diameter,
        dflt=dflt_val,
    )
    if rad is None:
        raise ValueError(
            "regular_ngon(): need to specify one of radius, diameter, outer_radius, outer_diameter, inner_radius, inner_diameter, side."  # noqa: E501
        )
    path = _regular_ngon_path(
        sides,
        rad,
        rounding=rounding,
        realign=realign,
        align_tip=align_tip,
        align_side=align_side,
        fn=fn,
        fa=fa,
        fs=fs,
    )
    shape = _opolygon(path)
    offset = _anchor_offset_hull(path, anchor)
    return _finish(shape, offset, spin)


def pentagon(
    radius: float | None = None,
    diameter: float | None = None,
    outer_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_radius: float | None = None,
    inner_diameter: float | None = None,
    side: float | None = None,
    rounding: float = 0,
    realign: bool = False,
    align_tip: Sequence[float] | None = None,
    align_side: Sequence[float] | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """A regular pentagon. See regular_ngon() for argument details."""
    return regular_ngon(
        sides=5,
        radius=radius,
        diameter=diameter,
        outer_radius=outer_radius,
        outer_diameter=outer_diameter,
        inner_radius=inner_radius,
        inner_diameter=inner_diameter,
        side=side,
        rounding=rounding,
        realign=realign,
        align_tip=align_tip,
        align_side=align_side,
        anchor=anchor,
        spin=spin,
        fn=fn,
        fa=fa,
        fs=fs,
    )


def hexagon(
    radius: float | None = None,
    diameter: float | None = None,
    outer_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_radius: float | None = None,
    inner_diameter: float | None = None,
    side: float | None = None,
    rounding: float = 0,
    realign: bool = False,
    align_tip: Sequence[float] | None = None,
    align_side: Sequence[float] | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """A regular hexagon. See regular_ngon() for argument details."""
    return regular_ngon(
        sides=6,
        radius=radius,
        diameter=diameter,
        outer_radius=outer_radius,
        outer_diameter=outer_diameter,
        inner_radius=inner_radius,
        inner_diameter=inner_diameter,
        side=side,
        rounding=rounding,
        realign=realign,
        align_tip=align_tip,
        align_side=align_side,
        anchor=anchor,
        spin=spin,
        fn=fn,
        fa=fa,
        fs=fs,
    )


def octagon(
    radius: float | None = None,
    diameter: float | None = None,
    outer_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_radius: float | None = None,
    inner_diameter: float | None = None,
    side: float | None = None,
    rounding: float = 0,
    realign: bool = False,
    align_tip: Sequence[float] | None = None,
    align_side: Sequence[float] | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """A regular octagon. See regular_ngon() for argument details."""
    return regular_ngon(
        sides=8,
        radius=radius,
        diameter=diameter,
        outer_radius=outer_radius,
        outer_diameter=outer_diameter,
        inner_radius=inner_radius,
        inner_diameter=inner_diameter,
        side=side,
        rounding=rounding,
        realign=realign,
        align_tip=align_tip,
        align_side=align_side,
        anchor=anchor,
        spin=spin,
        fn=fn,
        fa=fa,
        fs=fs,
    )


def right_triangle(
    size: Sequence[float] = [1, 1],
    center: bool | None = None,
    anchor: Sequence[float] | None = None,
    spin: float = 0,
) -> Bosl2Shape2D:
    """A right triangle, built directly with polygon().

    Args:
        size:   [width, length] of the right triangle
        center: True forces anchor=CENTER, False forces anchor=[-1,-1] (default: use anchor=)
        anchor: anchor point (default: [-1,-1], the right-angle corner)
        spin:   Z-axis rotation in degrees after anchor (default 0)
    """
    sz = [size, size] if isinstance(size, (int, float)) else list(size)  # type: ignore[arg-type]
    if anchor is not None:
        use_anchor = anchor
    elif center:
        use_anchor = CENTER
    else:
        use_anchor = [-1, -1, 0]
    path = [[sz[0] / 2, -sz[1] / 2], [-sz[0] / 2, -sz[1] / 2], [-sz[0] / 2, sz[1] / 2]]
    shape = _opolygon(path)
    offset = _anchor_offset_box(sz, use_anchor)
    return _finish(shape, offset, spin, size=sz, anchor=use_anchor)


def _trapezoid_path(
    height: float,
    width1: float,
    width2: float,
    shift: float,
    chamfer,
    rounding,
    flip: bool,
    fn=None,
    fa=None,
    fs=None,
) -> list[list[float]]:
    chamfs = list(chamfer) if isinstance(chamfer, (list, tuple)) else [chamfer] * 4
    rounds = list(rounding) if isinstance(rounding, (list, tuple)) else [rounding] * 4
    srads = [rounds[i] if rounds[i] else chamfs[i] for i in range(4)]
    rads = [abs(s) for s in srads]
    base = [
        [width2 / 2 + shift, height / 2],
        [-width2 / 2 + shift, height / 2],
        [-width1 / 2, -height / 2],
        [width1 / 2, -height / 2],
    ]
    angle1 = _v_theta([base[0][0] - base[3][0], base[0][1] - base[3][1]]) - 90
    angle2 = _v_theta([base[1][0] - base[2][0], base[1][1] - base[2][1]]) - 90
    angles = [angle1, angle2, angle2, angle1]
    qdirs = [[1, 1], [-1, 1], [-1, -1], [1, -1]]
    angle_pairs = [
        {
            "pos": (angles[0], 90),
            "flip": (angles[0], -90),
            "neg": (180 + angles[0], 90),
        },
        {
            "pos": (90, 180 + angles[1]),
            "flip": (270, 180 + angles[1]),
            "neg": (90, angles[1]),
        },
        {
            "pos": (180 + angles[2], 270),
            "flip": (180 + angles[2], 90),
            "neg": (angles[2], -90),
        },
        {
            "pos": (-90, angles[3]),
            "flip": (90, angles[3]),
            "neg": (270, 180 + angles[3]),
        },
    ]
    cpath = []
    for i in range(4):
        if rads[i] == 0:
            cpath.append(base[i])
            continue
        hyp = _adjacent_angle_to_hypotenuse(rads[i], angles[i])
        xoff = _adjacent_angle_to_opposite(rads[i], angles[i])
        sign_a = -1 if (srads[i] < 0 and flip) else 1
        a = [xoff * qdirs[i][1] * sign_a, -rads[i] * qdirs[i][1] * sign_a]
        sign_b = 1 if (srads[i] < 0 and not flip) else -1
        b = [a[0] + hyp * qdirs[i][0] * sign_b, a[1]]
        center = [base[i][0] + b[0], base[i][1] + b[1]]
        if srads[i] > 0:
            a0, a1 = angle_pairs[i]["pos"]  # type: ignore[index]
        elif flip:
            a0, a1 = angle_pairs[i]["flip"]  # type: ignore[index]
        else:
            a0, a1 = angle_pairs[i]["neg"]  # type: ignore[index]
        point_count = max(3, math.ceil(_frag_count(rads[i], fn, fa, fs) * abs(a1 - a0) / 360)) if rounds[i] else 2
        cpath.extend(_arc_points(point_count, rads[i], a0, a1 - a0, center))
    return list(reversed(cpath))


def trapezoid(
    height: float | None = None,
    width1: float | None = None,
    width2: float | None = None,
    angle: float | None = None,
    shift: float = 0,
    chamfer: float | Sequence[float] = 0,
    rounding: float | Sequence[float] = 0,
    flip: bool = False,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """A trapezoid with parallel front and back sides, built directly with polygon().

    Args:
        height:   Y-axis height of the trapezoid
        width1:   X-axis width of the front end
        width2:   X-axis width of the back end
        angle:    if given in place of height/width1/width2, the missing value is derived from this angle
        shift:    X-axis shift of the back of the trapezoid (default 0)
        rounding: corner rounding radius, or per-corner list [X+Y+,X-Y+,X-Y-,X+Y-] (default 0)
        chamfer:  corner chamfer length, or per-corner list [X+Y+,X-Y+,X-Y-,X+Y-] (default 0)
        flip:     point negative roundings/chamfers forward/back instead of left/right (default False)
        anchor:   anchor point (default CENTER)
        spin:     Z-axis rotation in degrees after anchor (default 0)
        fn/fa/fs: arc smoothness overrides for rounded corners
    """
    defined = sum(x is not None for x in (height, width1, width2, angle))
    assert defined == 3, "Must give exactly 3 of the arguments height, width1, width2, and angle."
    if height is None:
        assert width1 is not None and width2 is not None and angle is not None
        height = _opposite_angle_to_adjacent(abs(width2 - width1) / 2, abs(angle))
    if width1 is None:
        assert width2 is not None and angle is not None
        width1 = width2 + 2 * (_adjacent_angle_to_opposite(height, angle) + shift)
    if width2 is None:
        assert width1 is not None and angle is not None
        width2 = width1 - 2 * (_adjacent_angle_to_opposite(height, angle) + shift)
    assert width1 >= 0 and width2 >= 0 and height > 0 and width1 + width2 > 0, "Degenerate trapezoid geometry."
    path = _trapezoid_path(height, width1, width2, shift, chamfer, rounding, flip, fn, fa, fs)
    shape = _opolygon(path)
    offset = _anchor_offset_hull(path, anchor)
    return _finish(shape, offset, spin)


def star(
    tips: int | None = None,
    radius: float | None = None,
    inner_radius: float | None = None,
    diameter: float | None = None,
    outer_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_diameter: float | None = None,
    step: int | None = None,
    realign: bool = False,
    align_tip: Sequence[float] | None = None,
    align_pit: Sequence[float] | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    atype: str | AnchorType = AnchorType.HULL,
) -> Bosl2Shape2D:
    """An N-pointed star polygon, built directly with polygon().

    Note: BOSL2's outer-radius parameter is named `or`, which collides with the Python
    keyword `or`; it is exposed here as `outer_radius` instead.

    Args:
        tips:           number of stellate tips
        radius/outer_radius: radius to the tips of the star (BOSL2 `or`)
        inner_radius:   radius to the inner corners of the star
        diameter/outer_diameter: diameter to the tips of the star
        inner_diameter: diameter to the inner corners of the star
        step:           compute inner radius by virtually drawing a line `step` tips around the star (2 <= step <
        tips/2)
        realign:        put the midpoint of the last edge (instead of vertex 0) on the X+ axis (default False)
        align_tip:      rotate so the first tip points in this 2-D direction (applied before spin)
        align_pit:      rotate so the first inner corner points in this 2-D direction (applied before spin)
        anchor:         anchor point (default CENTER)
        spin:           Z-axis rotation in degrees after anchor (default 0)
        atype:          anchor method (default AnchorType.HULL)
    """
    rad = _pick_radius(radius1=outer_radius, diameter1=outer_diameter, radius=radius, diameter=diameter)
    if rad is None:
        raise ValueError("star(): must specify a radius (radius, diameter, outer_radius or outer_diameter).")
    assert tips is not None, "star(): must specify tips"
    if step is not None:
        stepr = rad * math.cos(math.radians(180 * step / tips)) / math.cos(math.radians(180 * (step - 1) / tips))
    else:
        stepr = rad
    inner_rad = _pick_radius(radius=inner_radius, diameter=inner_diameter, dflt=stepr)
    path1 = []
    for i in range(2 * tips, 0, -1):
        theta = math.radians(180.0 * i / tips)
        path_radius = inner_rad if i % 2 else rad
        path1.append([path_radius * math.cos(theta), path_radius * math.sin(theta)])
    extra_rot = 0.0
    if align_tip is not None:
        extra_rot += math.degrees(math.atan2(align_tip[1], align_tip[0]))
    elif align_pit is not None:
        extra_rot += math.degrees(math.atan2(align_pit[1], align_pit[0])) + 180.0 / tips
    if realign:
        extra_rot -= 180.0 / tips
    path = [_rotate2d(p, extra_rot) for p in path1] if extra_rot else path1
    shape = _opolygon(path)
    offset = _anchor_offset_generic(path, anchor, atype)
    return _finish(shape, offset, spin)


# ---------------------------------------------------------------------------
# Section: Curved 2D Shapes
# ---------------------------------------------------------------------------


def jittered_poly(path: Sequence[Sequence[float]], dist: float = 1 / 512) -> list[list[float]]:
    """Adds tiny random jitter to a path's points.

    Used to work around rendering artifacts from exactly-overlapping coplanar faces.

    Args:
        path: the path to add jitter to
        dist: the amount to jitter points by (default 1/512)
    """
    return [[p[0] + random.uniform(-dist, dist), p[1] + random.uniform(-dist, dist)] for p in path]


def teardrop2d(
    radius: float | None = None,
    angle: float = 45,
    cap_height: float | None = None,
    diameter: float | None = None,
    circumscribe: bool = False,
    realign: bool = False,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """A 2-D teardrop shape, useful for 3D-printable horizontal holes, built directly with polygon().

    Note: `circumscribe` is approximated the same way as the inscribed case here.

    Args:
        radius:     radius of the circular part (default 1)
        angle:      angle of the hat walls from the Y axis in degrees (default 45)
        cap_height: height above center to truncate the shape (default: no truncation)
        diameter:   diameter of the circular portion (alternative to radius)
        circumscribe: produce a circumscribing teardrop (default False)
        realign:    flip whether the bottom is a point or a flat (default False)
        anchor:     anchor point (default CENTER)
        spin:       Z-axis rotation in degrees after anchor (default 0)
        fn/fa/fs: arc smoothness overrides
    """
    rad = radius if radius is not None else (diameter / 2 if diameter is not None else 1)
    if circumscribe:
        n = _frag_count(rad, fn, fa, fs)
        rad /= math.cos(math.pi / n)
    minheight = rad * math.sin(math.radians(angle))
    maxheight = rad / math.sin(math.radians(angle))
    if cap_height is not None:
        assert cap_height >= minheight, f"cap_height cannot be less than {minheight} but it is {cap_height}"
    pointy = cap_height is None or cap_height >= maxheight
    if cap_height is None or pointy:
        cap_top = [0.0, maxheight]
    else:
        cap_top = [(maxheight - cap_height) * math.tan(math.radians(angle)), cap_height]
    cap_bot = [rad * math.cos(math.radians(angle)), rad * math.sin(math.radians(angle))]
    n = _frag_count(rad, fn, fa, fs)
    start = 90.0 + (180.0 / n if realign else 0.0)
    fullcircle = _circle_pts(rad, n, start=start)
    seglen = math.dist(fullcircle[0], fullcircle[1]) if len(fullcircle) > 1 else 0.0
    skipfactor = 15 if len(fullcircle) == 6 else 3
    path = [cap_top, cap_bot]
    for p in fullcircle:
        if p[1] < cap_bot[1] - 1e-9 and math.hypot(abs(p[0]) - cap_bot[0], p[1] - cap_bot[1]) > seglen / skipfactor:
            path.append(p)
    path.append([-cap_bot[0], cap_bot[1]])
    if not pointy:
        path.append([-cap_top[0], cap_top[1]])
    shape = _opolygon(path)
    offset = _anchor_offset_hull(path, anchor)
    return _finish(shape, offset, spin)


def egg(
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    arc_radius: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    arc_diameter: float | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """An egg-shaped 2-D outline, made of two circles joined by tangent arcs, built directly with polygon().

    Args:
        length:       length of the egg
        radius1:      radius of the left-hand circle
        radius2:      radius of the right-hand circle
        arc_radius:   radius of the joining arcs
        diameter1:    diameter of the left-hand circle (alternative to radius1)
        diameter2:    diameter of the right-hand circle (alternative to radius2)
        arc_diameter: diameter of the joining arcs (alternative to arc_radius)
        anchor:       anchor point (default CENTER)
        spin:         Z-axis rotation in degrees after anchor (default 0)
        fn/fa/fs:  arc smoothness overrides
    """
    radius1 = radius1 if radius1 is not None else (diameter1 / 2 if diameter1 is not None else None)
    if radius1 is None:
        raise ValueError("egg(): must give radius1 or diameter1")
    radius2 = radius2 if radius2 is not None else (diameter2 / 2 if diameter2 is not None else None)
    if radius2 is None:
        raise ValueError("egg(): must give radius2 or diameter2")
    arc_r = arc_radius if arc_radius is not None else (arc_diameter / 2 if arc_diameter is not None else None)
    if arc_r is None:
        raise ValueError("egg(): must give arc_radius or arc_diameter")
    assert length is not None, "egg(): must give length"
    path = _egg_path(length, radius1, radius2, arc_r, fn, fa, fs)
    shape = _opolygon(path)
    offset = _anchor_offset_hull(path, anchor)
    return _finish(shape, offset, spin)


def _egg_path(
    length: float,
    radius1: float,
    radius2: float,
    arc_radius: float,
    fn=None,
    fa=None,
    fs=None,
) -> list[list[float]]:
    assert length > 0
    assert arc_radius > length / 2, "Side radius must be larger than length/2"
    assert length > radius1 + radius2, "Length must be longer than radius1+radius2"
    c1 = [-length / 2 + radius1, 0.0]
    c2 = [length / 2 - radius2, 0.0]
    m_pts = list(reversed(_circle_circle_intersection(arc_radius - radius1, c1, arc_radius - radius2, c2)))
    assert len(m_pts) == 2, "egg(): circles do not intersect for the given length/radius1/radius2/arc_radius."
    arcparms = []
    for m in m_pts:
        u1 = unit([c1[0] - m[0], c1[1] - m[1]])
        u2 = unit([c2[0] - m[0], c2[1] - m[1]])
        arcparms.append(
            [
                m,
                [c1[0] + radius1 * u1[0], c1[1] + radius1 * u1[1]],
                [c2[0] + radius2 * u2[0], c2[1] + radius2 * u2[1]],
            ]
        )
    kw = {"fn": fn, "fa": fa, "fs": fs}
    path = []
    path += _arc_between_points(c2, [length / 2, 0.0], arcparms[0][2], radius2, endpoint=False, **kw)
    path += _arc_between_points(arcparms[0][0], arcparms[0][2], arcparms[0][1], arc_radius, endpoint=False, **kw)
    path += _arc_through_3(
        c1,
        radius1,
        arcparms[0][1],
        [-length / 2, 0.0],
        arcparms[1][1],
        endpoint=False,
        **kw,
    )
    path += _arc_between_points(arcparms[1][0], arcparms[1][1], arcparms[1][2], arc_radius, endpoint=False, **kw)
    path += _arc_between_points(c2, arcparms[1][2], [length / 2, 0.0], radius2, endpoint=False, **kw)
    return path


def glued_circles(
    radius: float | None = None,
    spread: float = 10,
    tangent: float = 30,
    diameter: float | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """Two circles joined by a curved waist, like a dumbbell, built directly with polygon().

    Args:
        radius:   radius of the end circles
        spread:   distance between the centers of the end circles (default 10)
        tangent:  angle in degrees of the tangent point of the joining arcs, from the Y axis (default 30)
        diameter: diameter of the end circles (alternative to radius)
        anchor:   anchor point (default CENTER)
        spin:     Z-axis rotation in degrees after anchor (default 0)
        fn/fa/fs: arc smoothness overrides
    """
    rad = radius if radius is not None else (diameter / 2 if diameter is not None else 10)
    cp1 = [spread / 2, 0.0]
    sa1 = 90 - tangent
    ea1 = 270 + tangent
    lobearc = ea1 - sa1
    lobesegs = math.ceil(_frag_count(rad, fn, fa, fs) * lobearc / 360)
    if tangent == 0:
        # radius2/cp2 (the inner waist arc) are undefined and unused in this case: the two end
        # circles' own arcs already meet with no separate waist curve needed.
        path = _arc_points(lobesegs + 1, rad, sa1, ea1 - sa1, [-cp1[0], -cp1[1]]) + _arc_points(
            lobesegs + 1, rad, sa1 + 180, ea1 - sa1, cp1
        )
    else:
        radius2 = (spread / 2 / math.sin(math.radians(tangent))) - rad
        cp2 = [0.0, (rad + radius2) * math.cos(math.radians(tangent))]
        sa2 = 270 - tangent
        ea2 = 270 + tangent
        subarc = ea2 - sa2
        arcsegs = math.ceil(_frag_count(radius2, fn, fa, fs) * abs(subarc) / 360)
        part1 = _arc_points(lobesegs, rad, sa1, ea1 - sa1, [-cp1[0], -cp1[1]], endpoint=False)
        part2 = []
        for k in range(arcsegs):
            theta = (ea2 + 180) + k * ((ea2 - subarc + 180) - (ea2 + 180)) / arcsegs
            part2.append(
                [
                    radius2 * math.cos(math.radians(theta)) - cp2[0],
                    radius2 * math.sin(math.radians(theta)) - cp2[1],
                ]
            )
        part3 = _arc_points(lobesegs, rad, sa1 + 180, ea1 - sa1, cp1, endpoint=False)
        part4 = []
        for k in range(arcsegs):
            theta = ea2 + k * ((ea2 - subarc) - ea2) / arcsegs
            part4.append(
                [
                    radius2 * math.cos(math.radians(theta)) + cp2[0],
                    radius2 * math.sin(math.radians(theta)) + cp2[1],
                ]
            )
        path = part1 + part2 + part3 + part4
    maxx_idx = max(range(len(path)), key=lambda i: path[i][0])
    path = list(reversed(path[maxx_idx:] + path[:maxx_idx]))
    shape = _opolygon(path)
    offset = _anchor_offset_hull(path, anchor)
    return _finish(shape, offset, spin)


def _superformula(
    theta: float,
    m1: float,
    m2: float,
    n1: float,
    n2: float,
    n3: float,
    a: float,
    b: float,
) -> float:
    t1 = abs(math.cos(math.radians(m1 * theta / 4)) / a) ** n2
    t2 = abs(math.sin(math.radians(m2 * theta / 4)) / b) ** n3
    return (t1 + t2) ** (-1.0 / n1)


def supershape(
    step: float = 0.5,
    count: int | None = None,
    m1: float = 4,
    m2: float | None = None,
    n1: float | None = None,
    n2: float | None = None,
    n3: float | None = None,
    a: float = 1,
    b: float | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    atype: str | AnchorType = AnchorType.HULL,
) -> Bosl2Shape2D:
    """A 2-D shape from the superformula, built directly with polygon().

    Args:
        step:   angle step size for sampling the superformula (smaller = slower, more accurate) (default 0.5)
        count:  number of output points, an alternative to step
        m1:     superformula m1 argument (default 4)
        m2:     superformula m2 argument (default: same as m1)
        n1:     superformula n1 argument (default 1)
        n2:     superformula n2 argument (default: same as n1)
        n3:     superformula n3 argument (default: same as n2)
        a:      superformula a argument (default 1)
        b:      superformula b argument (default: same as a)
        radius:   scale the shape to fit in a circle of this radius
        diameter: scale the shape to fit in a circle of this diameter
        anchor: anchor point (default CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)
        atype:  anchor method (default AnchorType.HULL)
    """
    n_pts = count if count is not None else math.ceil(360.0 / step)
    n1v = n1 if n1 is not None else 1
    m2v = m2 if m2 is not None else m1
    n2v = n2 if n2 is not None else n1v
    n3v = n3 if n3 is not None else n2v
    bv = b if b is not None else a
    angles = [360.0 - i * 360.0 / n_pts for i in range(n_pts)]
    rvals = [_superformula(t, m1, m2v, n1v, n2v, n3v, a, bv) for t in angles]
    target_radius = radius if radius is not None else (diameter / 2 if diameter is not None else None)
    scale = (target_radius / max(rvals)) if target_radius is not None else 1.0
    path = [
        [
            scale * rvals[i] * math.cos(math.radians(angles[i])),
            scale * rvals[i] * math.sin(math.radians(angles[i])),
        ]
        for i in range(n_pts)
    ]
    shape = _opolygon(path)
    offset = _anchor_offset_generic(path, anchor, atype)
    return _finish(shape, offset, spin)


def _linearize_squareness(squareness: float) -> float:
    # Chamberlain Fong (2016), "Squircular Calculations", arXiv:1604.02174v5.
    c = 2 - 2 * math.sqrt(2)
    d = 1 - 0.5 * c * squareness
    return 2 * math.sqrt((1 + c) * squareness * squareness - c * squareness) / (d * d)


def squircle_radius_fg(squareness: float, radius: float, angle: float) -> float:
    """
    The Fong-Garcia squircle radius at *angle* degrees for squareness *squareness* and size
    *radius*.
    """
    s2a = abs(squareness * math.sin(math.radians(2 * angle)))
    return radius * math.sqrt(2) / s2a * math.sqrt(1 - math.sqrt(1 - s2a * s2a)) if s2a > 0 else radius


def _squircle_fg_path(size, squareness, fn, fa, fs) -> list:
    sq = _linearize_squareness(squareness)
    aspect = size[1] / size[0]
    r = 0.5 * size[0]
    fn = _frag_count(r, fn, fa, fs)
    astep = 90.0 / round(fn / 4) if fn >= 12 else 360.0 / 48
    pts = []
    a = 360.0
    while a > 0.01:
        theta = a + sq * math.sin(math.radians(4 * a)) * 30 / math.pi
        p = squircle_radius_fg(sq, r, theta)
        pts.append(
            [
                p * math.cos(math.radians(theta)),
                p * aspect * math.sin(math.radians(theta)),
            ]
        )
        a -= astep
    return pts


def squircle(
    size,
    squareness: float = 0.5,
    style: str = "fg",
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """A squircle -- a rounded square that morphs between a square and a circle (BOSL2 squircle()).

    *squareness* runs 0 (a circle) to 1 (a square). Only the default ``"fg"`` (Fong-Garcia) style
    is ported; the ``"superellipse"`` and ``"bezier"`` styles are not.

    Args:
        size:       scalar or [x, y] size of the bounding box
        squareness: 0 (circle) .. 1 (square); default 0.5
        style:      only "fg" is supported
        anchor/spin: standard BOSL2 2-D anchor / spin
        fn/fa/fs: smoothness overrides

    Examples:
        .. pythonscad-example::

            s2.squircle(40, squareness=0.7).linear_extrude(height=5).show()
    """
    assert 0 <= squareness <= 1, "squircle(): squareness must be between 0 and 1."
    sz = [float(size), float(size)] if isinstance(size, (int, float)) else [float(size[0]), float(size[1])]
    assert style == "fg", 'squircle(): only the default "fg" style is ported.'
    path = _squircle_fg_path(sz, squareness, fn, fa, fs)
    shape = _opolygon(path)
    offset = _anchor_offset_hull(path, anchor)
    return _finish(shape, offset, spin)


def keyhole(
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    shoulder_radius: float = 0,
    diameter1: float | None = None,
    diameter2: float | None = None,
    _length=None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """A keyhole slot -- a small circle joined to a larger one by tangent shoulders (BOSL2 keyhole()).

    Args:
        length:         overall length between the two circle centers (default 15)
        radius1/diameter1: radius/diameter of the small (bottom) circle (default 5)
        radius2/diameter2: radius/diameter of the large (top) circle (default 10)
        shoulder_radius: fillet radius where the shoulders meet the circles (default 0)
        anchor/spin: standard BOSL2 2-D anchor / spin

    Examples:
        .. pythonscad-example::

            s2.keyhole(length=25, radius1=4, radius2=9, shoulder_radius=2).linear_extrude(height=4).show()
    """
    lv = float(length if length is not None else (_length if _length is not None else 15))
    r1v = float(radius1 if radius1 is not None else (diameter1 / 2 if diameter1 is not None else 5))
    r2v = float(radius2 if radius2 is not None else (diameter2 / 2 if diameter2 is not None else 10))
    assert lv > 0 and lv >= max(r1v, r2v), "keyhole(): length must be positive and at least max(radius1, radius2)."
    shoulder_radius = float(shoulder_radius) if shoulder_radius is not None else min(r1v, r2v) / 2
    cp1, cp2 = [0.0, 0.0], [0.0, -lv]
    minr, maxr = min(r1v, r2v) + shoulder_radius, max(r1v, r2v) + shoulder_radius
    dy = math.sqrt(maxr * maxr - minr * minr)
    spt1 = [cp1[0] + minr, cp1[1] - dy] if r1v > r2v else [cp2[0] + minr, cp2[1] + dy]
    spt2 = [-spt1[0], spt1[1]]
    base = cp1 if r1v > r2v else cp2
    ds = [spt1[0] - base[0], spt1[1] - base[1]]
    angle = math.degrees(math.atan2(abs(ds[1]), abs(ds[0])))

    def _arc(**kw):
        return arc(endpoint=False, fn=fn, fa=fa, fs=fs, **kw)

    path: list[Any] = []
    if r1v > r2v:
        path += (
            [spt1]
            if shoulder_radius <= 0
            else _arc(radius=shoulder_radius, center=spt1, start=180 - angle, angle=angle)
        )
        path += _arc(radius=r2v, center=cp2, start=0, angle=-180)
        path += [spt2] if shoulder_radius <= 0 else _arc(radius=shoulder_radius, center=spt2, start=0, angle=angle)
        path += _arc(radius=r1v, center=cp1, start=180 + angle, angle=-180 - 2 * angle)
    else:
        path += [spt1] if shoulder_radius <= 0 else _arc(radius=shoulder_radius, center=spt1, start=180, angle=angle)
        path += _arc(radius=r2v, center=cp2, start=angle, angle=-180 - 2 * angle)
        path += (
            [spt2]
            if shoulder_radius <= 0
            else _arc(radius=shoulder_radius, center=spt2, start=360 - angle, angle=angle)
        )
        path += _arc(radius=r1v, center=cp1, start=180, angle=-180)
    shape = _opolygon(path)
    offset = _anchor_offset_hull(path, anchor)
    return _finish(shape, offset, spin)


def ring(
    sides: int | None = None,
    ring_width: float | None = None,
    radius: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    angle: float | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """A 2-D ring (annulus) between two concentric radii (BOSL2 ring(), full-annulus form).

    Give either both radii (*radius1*/*radius2* or *diameter1*/*diameter2*) or one radius plus
    *ring_width*. The arc / 3-point / corner / width+thickness forms of BOSL2 ``ring()`` are
    not ported.

    Args:
        radius1/radius2 (or diameter1/diameter2): the two radii/diameters
        radius/diameter + ring_width: one radius plus the wall width
        sides:    number of sides (overrides the smoothness overrides)
        anchor/spin: standard BOSL2 2-D anchor / spin

    Examples:
        .. pythonscad-example::

            s2.ring(radius=20, ring_width=4).linear_extrude(height=5).show()
    """
    assert angle is None, "ring(): only the full-annulus form is ported (no angle=)."
    r1v = radius1 if radius1 is not None else (diameter1 / 2 if diameter1 is not None else None)
    r2v = radius2 if radius2 is not None else (diameter2 / 2 if diameter2 is not None else None)
    rv = radius if radius is not None else (diameter / 2 if diameter is not None else None)
    if r1v is not None and r2v is not None:
        inner, outer = min(r1v, r2v), max(r1v, r2v)
    else:
        assert rv is not None and ring_width is not None, (
            "ring(): give (radius1 and radius2) or (radius and ring_width)."
        )
        inner, outer = min(rv, rv + ring_width), max(rv, rv + ring_width)
    assert inner != outer and outer > 0, "ring(): zero (or invalid) width."
    fnv = sides if sides is not None else fn
    shape = circle(radius=outer, fn=fnv, fa=fa, fs=fs) - circle(radius=inner, fn=fnv, fa=fa, fs=fs)
    offset = _anchor_offset_box([2 * outer, 2 * outer], anchor)
    return _finish(shape, offset, spin, size=[2 * outer, 2 * outer], anchor=anchor)


def reuleaux_polygon(
    sides: int = 3,
    radius: float | None = None,
    diameter: float | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """A Reuleaux polygon (constant-width curved-side shape), built directly with polygon().

    Args:
        sides:    number of "sides"; must be an odd positive number (default 3)
        radius:   scale the shape to fit in a circle of this radius
        diameter: scale the shape to fit in a circle of this diameter
        anchor:   anchor point (default CENTER)
        spin:     Z-axis rotation in degrees after anchor (default 0)
        fn/fa/fs: arc smoothness overrides
    """
    assert sides >= 3 and sides % 2 == 1
    rad = radius if radius is not None else (diameter / 2 if diameter is not None else 1)
    ssegs = max(3, math.ceil(_frag_count(rad, fn, fa, fs) / sides))
    slen = math.dist(_polar_to_xy(rad, 0), _polar_to_xy(rad, 180 - 180.0 / sides))
    path = []
    for i in range(sides):
        ca = 180 - (i + 0.5) * 360.0 / sides
        sa = ca + 180 + 90.0 / sides
        ea = ca + 180 - 90.0 / sides
        center = _polar_to_xy(rad, ca)
        path += _arc_points(ssegs - 1, slen, sa, ea - sa, center, endpoint=False)
    shape = _opolygon(path)
    offset = _anchor_offset_hull(path, anchor)
    return _finish(shape, offset, spin)


# ---------------------------------------------------------------------------
# Section: Text
# ---------------------------------------------------------------------------


def text(
    text: str,
    size: float = 10,
    font: str = "Liberation Sans",
    halign: str | None = None,
    valign: str | None = None,
    spacing: float = 1.0,
    direction: str = "ltr",
    language: str = "en",
    script: str = "latin",
    anchor: str = "baseline",
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """2-D text, built directly with the builtin text() (which already supports halign/valign).

    Args:
        text:      text to create
        size:      font size (default 10)
        font:      font to use (default "Liberation Sans")
        halign:    horizontal alignment: "left", "center", "right" (default "center")
        valign:    vertical alignment: "top", "center", "baseline", "bottom" (default: `anchor`)
        spacing:   relative spacing multiplier between characters (default 1.0)
        direction: text direction: "ltr", "rtl", "ttb", "btt" (default "ltr")
        language:  language the text is in (default "en")
        script:    script the text is in (default "latin")
        anchor:    vertical alignment fallback used when valign isn't given (default "baseline")
        spin:      Z-axis rotation in degrees (default 0)
    """
    h = halign if halign is not None else "center"
    v = valign if valign is not None else anchor
    shape = _otext(
        text,
        size=size,
        font=font,
        halign=h,
        valign=v,
        spacing=spacing,
        direction=direction,
        language=language,
        script=script,
        fn=fn,
        fa=fa,
        fs=fs,
    )
    return _finish(shape, [0.0, 0.0], spin)


# ---------------------------------------------------------------------------
# Section: Rounding 2D shapes
# ---------------------------------------------------------------------------


def round2d(
    radius: float | None = None,
    outer_radius: float | None = None,
    inner_radius: float | None = None,
    children: "Bosl2Shape2D | PyOpenSCAD | None" = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """Rounds the concave and/or convex corners of arbitrary 2-D children, via chained .offset() calls.

    Giving `radius` rounds all corners; `inner_radius` alone rounds only concave corners;
    `outer_radius` alone rounds only convex corners; giving both rounds each to a different
    radius.

    Note: BOSL2's outer-radius parameter is named `or`, exposed here as `outer_radius`.

    Args:
        radius:       radius to round all concave and convex corners to
        outer_radius: radius to round only convex (outside) corners to (BOSL2 `or`)
        inner_radius: radius to round only concave (inside) corners to
        children:     the 2-D solid(s) to round
        fn/fa/fs:  arc smoothness overrides
    """
    orad = outer_radius if outer_radius is not None else (radius if radius is not None else 0)
    irad = inner_radius if inner_radius is not None else (radius if radius is not None else 0)
    assert children is not None, "round2d(): must give children"
    shape = Bosl2Shape2D(_as_native_2d(children))
    shape = shape.offset(delta=irad, chamfer=True)
    shape = shape.offset(delta=-(irad + orad))
    return shape.offset(radius=orad, fn=fn, fa=fa, fs=fs)


def shell2d(
    thickness: float | Sequence[float] | None = None,
    outer_radius: float | Sequence[float] = 0,
    inner_radius: float | Sequence[float] = 0,
    children: "Bosl2Shape2D | PyOpenSCAD | None" = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """Creates a hollow shell from 2-D children, with optional rounding.

    Note: BOSL2's outer-radius parameter is named `or`, exposed here as `outer_radius`.

    Args:
        thickness:    shell thickness; positive expands outward, negative shrinks inward,
                      or a 2-element list to do both
        outer_radius: rounding radius for outside corners of the shell (BOSL2 `or`); a
                      [CONVEX,CONCAVE] pair rounds those corner types separately (default 0)
        inner_radius: rounding radius for inside corners of the shell; a [CONVEX,CONCAVE]
                      pair rounds those corner types separately (default 0)
        children:     the 2-D solid(s) to shell
        fn/fa/fs:  arc smoothness overrides
    """
    assert thickness is not None, "shell2d(): must give thickness"
    assert children is not None, "shell2d(): must give children"
    if isinstance(thickness, (int, float)):
        th = [float(thickness), 0.0] if thickness < 0 else [0.0, float(thickness)]
    else:
        tl = [float(v) for v in thickness]
        th = [tl[1], tl[0]] if tl[0] > tl[1] else tl
    orad = (
        [float(outer_radius), float(outer_radius)]
        if isinstance(outer_radius, (int, float))
        else [float(v) for v in outer_radius]
    )
    irad = (
        [float(inner_radius), float(inner_radius)]
        if isinstance(inner_radius, (int, float))
        else [float(v) for v in inner_radius]
    )
    base = Bosl2Shape2D(_as_native_2d(children))
    outer_shape = round2d(
        outer_radius=orad[0],
        inner_radius=orad[1],
        children=base.offset(delta=th[1], fn=fn, fa=fa, fs=fs),
        fn=fn,
        fa=fa,
        fs=fs,
    )
    inner_shape = round2d(
        outer_radius=irad[1],
        inner_radius=irad[0],
        children=base.offset(delta=th[0], fn=fn, fa=fa, fs=fs),
        fn=fn,
        fa=fa,
        fs=fs,
    )
    return outer_shape - inner_shape

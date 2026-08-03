# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/shapes2d/base.py
# FileSummary: Base 2D shape wrapper class and anchoring/mathematical helper functions.
# DocCategory: internal
# FileGroup: BOSL2

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import Enum
from typing import TYPE_CHECKING, Any, Union, overload

import numpy as np

from pybosl2._edges_lang import Anchor
from pybosl2._native import native
from pybosl2._shape import _BaseShape
from pybosl2.constants import CENTER
from pybosl2.vectors import unit

if TYPE_CHECKING:
    from openscad import PyOpenSCAD

    from pybosl2.path2d import Path2D
    from pybosl2.path3d import Path3D
    from pybosl2.shapes3d.base import CsgSolid as Bosl2Solid

Shape2DLike = Union["Bosl2Shape2D", "PyOpenSCAD", "Path2D", Sequence[Sequence[float]], np.ndarray]

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
    anchor: Anchor | Sequence[float],
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
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
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
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
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


def _pick_radius(  # type: ignore[no-untyped-def]
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


def _det2(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    """The 2-D cross product a x b -- sign gives the turn direction (z of the 3-D cross)."""
    return float(vec_a[0] * vec_b[1] - vec_a[1] * vec_b[0])


def _sign(value: float) -> int:
    value = float(value)
    return (value > 0) - (value < 0)


def _vector_angle(point_a: Sequence[float], point_b: Sequence[float], point_c: Sequence[float]) -> float:
    """The angle in degrees at vertex *b* of the corner a-b-c."""
    vax = float(point_a[0]) - float(point_b[0])
    vay = float(point_a[1]) - float(point_b[1])
    vcx = float(point_c[0]) - float(point_b[0])
    vcy = float(point_c[1]) - float(point_b[1])
    cosv: float = (vax * vcx + vay * vcy) / (math.hypot(vax, vay) * math.hypot(vcx, vcy))
    return math.degrees(math.acos(max(-1.0, min(1.0, cosv))))


def _dir2(anchor: Anchor | Sequence[float]) -> list[float]:
    a = (anchor.vector if isinstance(anchor, Anchor) else list(anchor)) + [0, 0, 0]
    return [a[0], a[1] + a[2]]


def _anchor_offset_box(size: Sequence[float], anchor: Anchor | Sequence[float]) -> list[float]:
    d = _dir2(anchor)
    return [-d[0] * size[0] / 2, -d[1] * size[1] / 2]


def _anchor_offset_hull(points: Sequence[Sequence[float]], anchor: Anchor | Sequence[float]) -> list[float]:
    d = _dir2(anchor)
    if d[0] == 0 and d[1] == 0:
        return [0.0, 0.0]
    best = max(points, key=lambda p: p[0] * d[0] + p[1] * d[1])
    return [-best[0], -best[1]]


def _finish(
    shape: PyOpenSCAD,
    offset: Anchor | Sequence[float],
    spin: float,
    size: Sequence[float] | None = None,
    anchor: Anchor | Sequence[float] | str | None = None,
) -> "Bosl2Shape2D":
    """Anchor-translate and spin a freshly built native 2-D shape, then wrap it.

    Every shape constructor in this file funnels through here, which is what makes them all
    return a :class:`Bosl2Shape2D` rather than a bare native handle. *size*/*anchor* are the
    nominal box metadata to carry on the wrapper, for the shapes that have one. A shape that is
    already wrapped (``ring()`` composes two circles) is unwrapped first, never double-wrapped.
    """
    shape = Bosl2Shape2D._unwrap(shape)
    off: list[float] = list(offset.vector_2d) if isinstance(offset, Anchor) else list(offset)[:2]
    if off[0] != 0 or off[1] != 0:
        shape = shape.translate(off)
    if spin:
        # Native 2-D rotate needs the 3-vector form; a bare scalar is rejected.
        shape = shape.rotate([0, 0, spin])
    return Bosl2Shape2D(shape, size=size, anchor=anchor)


class CsgShape2D(_BaseShape):
    """Wraps a native PyOpenSCAD **2-D** shape, giving it the same fluent, chainable API that
    :class:`~pybosl2.shapes3d.Bosl2Solid` gives 3-D solids. Every shape constructor in this file
    returns one of these, as do :meth:`~pybosl2.paths.Path2D.polygon` and
    :meth:`~pybosl2.regions.Region.geometry`.

    Transforms, CSG operators, colour, and distributor methods are inherited from
    :class:`~pybosl2._shape._BaseShape`.

    The 2-D specific operations live here:

    * :meth:`fill` -- drop every hole, keeping only the outermost outline (OpenSCAD ``fill()``).
    * :meth:`hull` -- the convex hull of this shape, optionally together with more shapes/paths
      (OpenSCAD ``hull()``).
    * :meth:`offset` -- inset/outset, with BOSL2's ``radius=``/``delta=`` spelling (the native
      ``offset()`` only understands ``r=``).
    * :meth:`linear_extrude` / :meth:`rotate_extrude` -- the 2-D -> 3-D operators, which return a
      :class:`~pybosl2.shapes3d.Bosl2Solid` so the result keeps the 3-D fluent API.

    Like :class:`~pybosl2.shapes3d.Bosl2Solid` this is composition, not a subclass of the native
    C-extension type: passing one *directly* into a native function that wants a raw handle needs
    an explicit ``.shape`` (or :func:`pybosl2._helpers.unwrap`).

    .. seealso::

       `Visual spec sheet <specs/shapes2d.html>`_ — measurements and STL previews
    """

    #: which realize backend produced this shape -- 2-D geometry is exact-CSG only (see
    #: pybosl2/_backend.py); the SDF backend has no 2-D surface.
    backend = "csg"

    def __init__(
        self,
        shape: PyOpenSCAD,
        size: Sequence[float] | None = None,
        anchor: "Anchor | Sequence[float] | str | None" = None,
    ):
        self.shape = shape
        #: nominal [x, y] size for the shapes that have a genuine box size, else None
        self.size = None if size is None else [float(v) for v in size][:2]
        a_val: Anchor | Sequence[float] | str | None = anchor if anchor is not None else CENTER
        self.anchor = a_val

    spin = _BaseShape.rotate

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

        Examples:
            .. pythonscad-example::

                s2.star(n=5, r=30, ir=15).offset(delta=4).linear_extrude(height=4).show()
        """
        assert (radius is None) != (delta is None), "offset(): give exactly one of radius= or delta=."
        kw: dict[str, Any] = {"r": radius} if radius is not None else {"delta": delta, "chamfer": chamfer}
        for name, value in (("fn", fn), ("fa", fa), ("fs", fs)):
            if value is not None:
                kw[name] = value
        # The offset moves the outline, so the nominal box size no longer describes it.
        return self._wrap(self.shape.offset(**kw))

    def minkowski(self, other: "Bosl2Shape2D | PyOpenSCAD") -> "Bosl2Shape2D":
        """Minkowski sum of this shape with *other*.

        Args:
            other: A second 2-D shape to sweep along the outline of this one.

        Returns:
            A new :class:`Bosl2Shape2D` whose geometry is the Minkowski sum.

        Examples:
            .. pythonscad-example::

                s2.square([10, 10], center=True).minkowski(s2.circle(radius=3)).linear_extrude(height=2).show()
        """
        from pythonscad import minkowski as _minkowski

        result = _minkowski(self.shape, Bosl2Shape2D._unwrap(other))
        return self._wrap(result)

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
        ``Bosl2Shape2D``, native 2-D shapes, :class:`~pybosl2.paths.Path2D` /
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

            .. pythonscad-example::

                s2.circle(radius=15).linear_extrude(height=20).show()
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

        Examples:
            .. pythonscad-example::

                s2.square(10).right(15).rotate_extrude().show()
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

    def path_extrude(self, path: Path3D, **kwargs: Any) -> "Bosl2Solid":
        """Sweep this 2-D shape along *path* (a :class:`~pybosl2.paths.Path3D` or point list), via
        the native ``path_extrude()``.

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid`.

        Examples:
            .. pythonscad-example::

                path = [[0, 0, 0], [20, 10, 10], [40, 0, 20], [60, 10, 30]]
                s2.circle(radius=5).path_extrude(path).show()
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

    # ---- distributors (pybosl2/distributors.py) ----

    def _distribute(self, mats: list[np.ndarray]) -> list["Bosl2Shape2D"]:  # type: ignore[override]
        """Return a list of multmatrix copies of this 2-D shape, one per matrix."""
        result = []
        for m in mats:
            m4 = np.asarray(m, dtype=float)
            assert abs(float(m4[2, 3])) < 1e-9 and abs(float(m4[2, 2]) - 1.0) < 1e-9, (
                "this copier moves the 2-D shape out of the XY plane; extrude it to 3-D first"
            )
            copy = self.shape.multmatrix(m4.tolist())
            result.append(self._wrap(copy))
        return result

    def distribute_on_path(
        self,
        path: Path2D,
        num_copies: int | None = None,
        spacing: float | None = None,
        start_pos: float | None = None,
        dist: list[float] | None = None,
        rotate_children: bool = True,
    ) -> "Bosl2Shape2D":
        """Distribute copies of this 2-D shape along *path*, oriented to the path normal.

        Args:
            path: A :class:`~pybosl2.path2d.Path2D`.
            num_copies: Number of copies.
            spacing: Distance between copies.
            start_pos: Starting position along the path.
            dist: Explicit list of distances from path start.
            rotate_children: If True, rotate each copy to align with the path normal.

        Returns:
            A :class:`Bosl2Shape2D` union of all positioned copies.
        """
        import math

        length = path.perimeter()
        is_closed = getattr(path, "closed", False)
        if dist is not None:
            distances = sorted(float(x) for x in dist)
        elif start_pos is not None:
            if num_copies is not None and spacing is not None:
                distances = [start_pos + i * spacing for i in range(num_copies)]
            elif num_copies is not None:
                step = (length - start_pos) / (num_copies - 1) if num_copies > 1 else 0.0
                distances = [start_pos + i * step for i in range(num_copies)]
            else:
                assert spacing is not None, "distribute_on_path(): provide num_copies or spacing."
                cnt = int((length - start_pos) / spacing) + 1
                distances = [start_pos + i * spacing for i in range(cnt)]
        elif num_copies is not None and spacing is None:
            if not is_closed:
                step = length / (num_copies - 1) if num_copies > 1 else 0.0
                distances = [i * step for i in range(num_copies)]
            else:
                step = length / num_copies if num_copies > 0 else 0.0
                distances = [i * step for i in range(num_copies)]
        else:
            assert spacing is not None, "distribute_on_path(): provide num_copies, spacing, or dist."
            cnt = num_copies if num_copies is not None else int(math.floor(length / spacing)) + (0 if is_closed else 1)
            ptlist = [i * spacing for i in range(cnt)]
            center = sum(ptlist) / len(ptlist)
            if is_closed:
                distances = sorted((e - center) % length for e in ptlist)
            else:
                distances = [e + length / 2 - center for e in ptlist]
        distances = [min(max(dst, 0.0), length) for dst in distances]
        cutlist = path.cut_points(distances, closed=is_closed, direction=True)
        results: list[Bosl2Shape2D] = []
        for cp in cutlist:
            copied: Bosl2Shape2D = self.translate([float(cp.point[0]), float(cp.point[1])])
            if rotate_children:
                nv = getattr(cp, "normal", [0, 1])
                ang = math.degrees(math.atan2(float(nv[1]), float(nv[0]))) - 90
                copied = copied.rotate(ang)
            results.append(copied)
        out = results[0]
        for r in results[1:]:
            out = out | r
        return out

    # ---- bounding box ----

    def bounds(self) -> "tuple[list[float], list[float]]":
        """This shape's axis-aligned bounding box as ``(center, size)`` -- both ``[x, y]`` float
        lists in the shape's current frame (the 2-D form of
        :meth:`~pybosl2.shapes3d.Bosl2Solid.bounds`).

        Prefers the native bbox, which always reflects the current geometry; falls back to the
        tracked nominal size/anchor when the native accessors aren't available (the numeric test
        mock).
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
            size = [float(v) for v in self.size]
            assert self.anchor is not None
            return _anchor_offset_box(size, self.anchor), size
        raise ValueError("bounds(): the shape has no native bounding box and no tracked size metadata.")


def _as_native_2d(obj: Any) -> "PyOpenSCAD":
    """A raw native 2-D handle from *obj*: a Bosl2Shape2D/Bosl2Solid wrapper, a native shape, a
    :class:`~pybosl2.paths.Path2D` / :class:`~pybosl2.regions.Region`, or a plain point list.
    """
    from pybosl2._helpers import unwrap

    unwrapped = unwrap(obj)
    if unwrapped is not obj:  # a Bosl2Shape2D / Bosl2Solid wrapper
        return unwrapped
    geom = getattr(obj, "geometry", None)  # Path2D / Region
    if callable(geom):
        return unwrap(geom())
    if isinstance(obj, (list, tuple)):  # a bare [[x, y], ...] point list
        return _opolygon([[float(p[0]), float(p[1])] for p in obj])
    return obj


def _is_child_2d(obj: Any) -> bool:
    """True if *obj* is a single 2-D child rather than a container of children -- a wrapper or
    native shape, a Path2D/Region (which are ``list`` subclasses), or a ``[[x, y], ...]`` list.
    """
    if not isinstance(obj, (list, tuple)):
        return True  # a wrapper or a native handle
    if callable(getattr(obj, "geometry", None)):
        return True  # Path2D / Region
    return bool(len(obj)) and isinstance(obj[0], (list, tuple)) and len(obj[0]) == 2


Bosl2Shape2D = CsgShape2D

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/shapes2d/circle.py
# FileSummary: Circles, ellipses, arcs, keyholes and rings.
# DocCategory: Foundational
# FileGroup: BOSL2

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Union

import numpy as np

from pybosl2._native import native
from pybosl2.constants import CENTER
from pybosl2.geometry import is_collinear
from pybosl2.path2d import Path2D
from pybosl2.points import Point
from pybosl2.vectors import unit

# Import base class and helper functions from shapes2d.base
from .base import (
    Bosl2Shape2D,
    _anchor_offset_box,
    _anchor_offset_hull,
    _arc_points,
    _circle_from_3pts,
    _circle_from_corner,
    _circle_pts,
    _det2,
    _finish,
    _frag_count,
    _pick_radius,
    _polar_to_xy,
    _sign,
    _vector_angle,
)

if TYPE_CHECKING:
    from openscad import PyOpenSCAD

    from pybosl2._edges_lang import Anchor


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


def circle(
    radius: float | None = None,
    diameter: float | None = None,
    points: Sequence[Sequence[float]] | None = None,
    corner: Sequence[Sequence[float]] | None = None,
    anchor: Anchor | Sequence[float] = CENTER,
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

    Examples:
        .. pythonscad-example::

            s2.circle(radius=15).linear_extrude(height=5).show()
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
) -> Path2D:
    """A 2-D arc, returned as a :class:`~pybosl2.paths.Path2D` of points (BOSL2's ``arc()``).

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
        A :class:`~pybosl2.paths.Path2D` (closed when *wedge* is set).
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
        assert not is_collinear(
            Point(corner[0][0], corner[0][1]), Point(corner[1][0], corner[1][1]), Point(corner[2][0], corner[2][1])
        ), "Collinear corner does not define an arc"
        rad = _pick_radius(radius=radius, diameter=diameter)
        assert rad is not None and rad > 0, "arc(corner=) needs radius= or diameter="
        p0, p1, p2 = corner
        v1 = unit([float(p0[0]) - float(p1[0]), float(p0[1]) - float(p1[1])])
        v2 = unit([float(p2[0]) - float(p1[0]), float(p2[1]) - float(p1[1])])
        half = math.acos(max(-1.0, min(1.0, v1[0] * v2[0] + v1[1] * v2[1]))) / 2
        d_tan = rad / math.tan(half)
        cp2 = _circle_from_corner(corner, rad)
        tp1 = [float(p1[0]) + v1[0] * d_tan, float(p1[1]) + v1[1] * d_tan]
        tp2 = [float(p1[0]) + v2[0] * d_tan, float(p1[1]) + v2[1] * d_tan]
        forward = (
            _det2(
                [float(p1[0]) - float(p0[0]), float(p1[1]) - float(p0[1])],
                [float(p2[0]) - float(p1[0]), float(p2[1]) - float(p1[1])],
            )
            > 0
        )
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
            dv1 = [float(pts[0][0]) - centre[0], float(pts[0][1]) - centre[1]]
            dv2 = [float(pts[1][0]) - centre[0], float(pts[1][1]) - centre[1]]
            angle_val = _vector_angle(pts[0], centre, pts[1])
            prelim = _sign(_det2(dv1, dv2))
            if prelim != 0:
                direction = prelim
            else:
                assert clockwise or counterclockwise, "Collinear inputs don't define a unique arc"
                direction = 1
            rad = math.hypot(dv1[0], dv1[1])
            if long or (counterclockwise and direction < 0) or (clockwise and direction > 0):
                final_angle = -direction * (360 - angle_val)
            else:
                final_angle = direction * angle_val
            sa = math.degrees(math.atan2(dv1[1], dv1[0]))
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
        assert not is_collinear(
            Point(pts[0][0], pts[0][1]), Point(pts[1][0], pts[1][1]), Point(pts[2][0], pts[2][1])
        ), "Collinear inputs do not define an arc"
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
        return Path2D(out, closed=wedge)

    # -- radius + angle (with optional [start, end] range) -----------------------------------
    arc_r: float | None = _pick_radius(radius=radius, diameter=diameter)
    assert arc_r is not None, "arc() needs radius=/diameter=, points=, corner=, or width=/thickness="
    if isinstance(angle, (list, tuple)):
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
    return Path2D(out, closed=wedge)


def ellipse(
    radius: float | Sequence[float] | None = None,
    diameter: float | Sequence[float] | None = None,
    realign: bool = False,
    circumscribe: bool = False,
    uniform: bool = False,
    anchor: Anchor | Sequence[float] = CENTER,
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

    Examples:
        .. pythonscad-example::

            s2.ellipse(diameter=[30, 20]).linear_extrude(height=5).show()
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


def keyhole(
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    shoulder_radius: float = 0,
    diameter1: float | None = None,
    diameter2: float | None = None,
    _length: float | None = None,
    anchor: Anchor | Sequence[float] = CENTER,
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

    def _arc(**kw):  # type: ignore[no-untyped-def]
        return arc(endpoint=False, fn=fn, fa=fa, fs=fs, **kw)

    path: list[Any] = []
    if r1v > r2v:
        path += (
            [spt1]
            if shoulder_radius <= 0
            else _arc(radius=shoulder_radius, center=spt1, start=180 - angle, angle=angle)  # type: ignore[no-untyped-call]
        )
        path += _arc(radius=r2v, center=cp2, start=0, angle=-180)  # type: ignore[no-untyped-call]
        path += [spt2] if shoulder_radius <= 0 else _arc(radius=shoulder_radius, center=spt2, start=0, angle=angle)  # type: ignore[no-untyped-call]
        path += _arc(radius=r1v, center=cp1, start=180 + angle, angle=-180 - 2 * angle)  # type: ignore[no-untyped-call]
    else:
        path += [spt1] if shoulder_radius <= 0 else _arc(radius=shoulder_radius, center=spt1, start=180, angle=angle)  # type: ignore[no-untyped-call]
        path += _arc(radius=r2v, center=cp2, start=angle, angle=-180 - 2 * angle)  # type: ignore[no-untyped-call]
        path += (
            [spt2]
            if shoulder_radius <= 0
            else _arc(radius=shoulder_radius, center=spt2, start=360 - angle, angle=angle)  # type: ignore[no-untyped-call]
        )
        path += _arc(radius=r1v, center=cp1, start=180, angle=-180)  # type: ignore[no-untyped-call]
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
    anchor: Anchor | Sequence[float] = CENTER,
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


def glued_circles(
    radius: float | None = None,
    spread: float = 10,
    tangent: float = 30,
    diameter: float | None = None,
    anchor: Anchor | Sequence[float] = CENTER,
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

    Examples:
        .. pythonscad-example::

            s2.glued_circles(radius=10, spread=25, tangent=30).linear_extrude(height=5).show()
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


def reuleaux_polygon(
    sides: int = 3,
    radius: float | None = None,
    diameter: float | None = None,
    anchor: Anchor | Sequence[float] = CENTER,
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

    Examples:
        .. pythonscad-example::

            s2.reuleaux_polygon(sides=3, radius=15).linear_extrude(height=5).show()
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

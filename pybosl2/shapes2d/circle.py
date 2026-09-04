# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/shapes2d/circle.py
# FileSummary: Circles, ellipses, arcs, keyholes and rings.
# DocCategory: Foundational
# FileGroup: BOSL2

"""Circles, ellipses, arcs, keyholes and rings."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, cast

from pybosl2._backend import backend_only

# Import base class and helper functions from shapes2d.base
from pybosl2._helpers import (
    anchor_offset_box as _anchor_offset_box,
)
from pybosl2._helpers import (
    anchor_offset_hull as _anchor_offset_hull,
)
from pybosl2._helpers import (
    arc_points as _arc_points,
)
from pybosl2._helpers import (
    circle_from_3pts as _circle_from_3pts,
)
from pybosl2._helpers import circle_from_corner as _circle_from_corner
from pybosl2._helpers import (
    circle_pts as _circle_pts,
)
from pybosl2._helpers import (
    frag_count as _frag_count,
)
from pybosl2._helpers import (
    pick_radius as _pick_radius,
)
from pybosl2._helpers import (
    polar_to_xy as _polar_to_xy,
)
from pybosl2._native import native
from pybosl2.constants import CENTER
from pybosl2.defaults import resolve_facets as _resolve_facets
from pybosl2.exceptions import Bosl2ValueError

# `arc` moved to `pybosl2.path2d` in T50 -- it is path geometry, not a shape -- and is re-exported
# here so BOSL2's own spelling still resolves from where a reader of `shapes2d` expects it (B2-3).
from pybosl2.path2d import Path2D
from pybosl2.path2d import arc as arc
from pybosl2.paths import require_path

from .base import Bosl2Shape2D, _finish

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pybosl2._edges_lang import Anchor


# Defined once in base.py: five identical copies is the same duplication C-21 is about, and
# only base.py imported the names its own copy referenced.

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


@backend_only("csg", neutral="pybosl2.flat.circle")
def circle(
    radius: float | None = None,
    diameter: float | None = None,
    points: "Path2D | None" = None,
    corner: Sequence[Sequence[float]] | None = None,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """Return a circle by radius/diameter, or fit to points.

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
        fn: arc smoothness overrides. Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back
            out to fa/fs.
        fa: arc smoothness overrides. Omitted, the ambient ``use_defaults(fa=...)`` value applies.
        fs: arc smoothness overrides. Omitted, the ambient ``use_defaults(fs=...)`` value applies.

    Examples:
        .. pythonscad-example::

            from pybosl2 import shapes2d as s2

            s2.circle(radius=15).linear_extrude(height=5).show()

    """
    fn, fa, fs = _resolve_facets(fn, fa, fs)
    if points is not None:
        points = cast("Path2D", require_path(points, "points", "circle", Path2D))
        center, rad = _circle_from_3pts(points)
        return _finish(_ocircle(r=rad, fn=fn, fa=fa, fs=fs), center, 0, size=[2 * rad, 2 * rad])
    if corner is not None:
        rad = _pick_radius(radius=radius, diameter=diameter, dflt=1)
        center = _circle_from_corner(corner, rad)
        return _finish(_ocircle(r=rad, fn=fn, fa=fa, fs=fs), center, 0, size=[2 * rad, 2 * rad])
    rad = _pick_radius(radius=radius, diameter=diameter, dflt=1)
    shape = _ocircle(r=rad, fn=fn, fa=fa, fs=fs)
    n = _frag_count(rad, fn, fa, fs)
    offset = _anchor_offset_hull(_circle_pts(rad, n), anchor)
    return _finish(shape, offset, spin, size=[2 * rad, 2 * rad], anchor=anchor)


@backend_only("csg")
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
    """Return an ellipse (approximated as a polygon), built directly with polygon().

    Note: `uniform` (equal-length approximating segments) is not implemented; segments are
    evenly spaced by angle instead.

    Args:
        radius:   radius of the circle, or pair of semi-axes of the ellipse
        diameter: diameter of the circle, or pair giving the full X/Y axis lengths
        realign:  shift the first polygon point off the X+ axis (default False)
        circumscribe: circumscribe rather than inscribe the ideal ellipse (default False)
        uniform:  use equal-length approximating segments (not implemented; evenly spaced by angle)
        anchor:   anchor point (default CENTER)
        spin:     Z-axis rotation in degrees after anchor (default 0)
        fn: arc smoothness overrides. Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back
            out to fa/fs.
        fa: arc smoothness overrides. Omitted, the ambient ``use_defaults(fa=...)`` value applies.
        fs: arc smoothness overrides. Omitted, the ambient ``use_defaults(fs=...)`` value applies.

    Examples:
        .. pythonscad-example::

            from pybosl2 import shapes2d as s2

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


@backend_only("csg")
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
    """Return a keyhole slot -- a small circle joined to a larger one by tangent shoulders.

    Args:
        length:         overall length between the two circle centers (default 15)
        radius1:   radius/diameter of the small (bottom) circle (default 5)
        diameter1: radius/diameter of the small (bottom) circle (default 5)
        radius2:   radius/diameter of the large (top) circle (default 10)
        diameter2: radius/diameter of the large (top) circle (default 10)
        shoulder_radius: fillet radius where the shoulders meet the circles (default 0)
        anchor: standard BOSL2 2-D anchor / spin
        spin:   standard BOSL2 2-D anchor / spin
        fn: number of fragments for circle resolution. Omitted, the ambient ``use_defaults(fn=...)`` value applies;
            ``fn=0`` opts back out to fa/fs.
        fa: minimum fragment angle for circle resolution. Omitted, the ambient ``use_defaults(fa=...)`` value applies.
        fs: minimum fragment size for circle resolution. Omitted, the ambient ``use_defaults(fs=...)`` value applies.

    Examples:
        .. pythonscad-example::

            from pybosl2 import shapes2d as s2

            s2.keyhole(length=25, radius1=4, radius2=9, shoulder_radius=2).linear_extrude(height=4).show()

    """
    lv = float(length if length is not None else (_length if _length is not None else 15))
    r1v = float(_pick_radius(radius=radius1, diameter=diameter1, dflt=5))
    r2v = float(_pick_radius(radius=radius2, diameter=diameter2, dflt=10))
    if not (lv > 0):
        raise Bosl2ValueError("keyhole(): length must be positive and at least max(radius1, radius2).")
    if not (lv >= max(r1v, r2v)):
        raise Bosl2ValueError("keyhole(): length must be positive and at least max(radius1, radius2).")
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


@backend_only("csg")
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
    """Return a 2-D ring (annulus) between two concentric radii (full-annulus form).

    Give either both radii (*radius1*/*radius2* or *diameter1*/*diameter2*) or one radius plus
    *ring_width*. The arc / 3-point / corner / width+thickness forms of BOSL2 ``ring()`` are
    not ported.

    Args:
        radius1:   the two radii/diameters
        radius2:   the two radii/diameters
        diameter1: the two radii/diameters
        diameter2: the two radii/diameters
        radius:     one radius plus the wall width
        diameter:   one radius plus the wall width
        ring_width: one radius plus the wall width
        sides:    number of sides (overrides the smoothness overrides)
        angle:    sweep angle in degrees (only the full-annulus form is ported; angle must be None)
        anchor: standard BOSL2 2-D anchor / spin
        spin:   standard BOSL2 2-D anchor / spin
        fn: number of fragments for circle resolution. Omitted, the ambient ``use_defaults(fn=...)`` value applies;
            ``fn=0`` opts back out to fa/fs.
        fa: minimum fragment angle for circle resolution. Omitted, the ambient ``use_defaults(fa=...)`` value applies.
        fs: minimum fragment size for circle resolution. Omitted, the ambient ``use_defaults(fs=...)`` value applies.

    Examples:
        .. pythonscad-example::

            from pybosl2 import shapes2d as s2

            s2.ring(radius=20, ring_width=4).linear_extrude(height=5).show()

    """
    if angle is not None:
        raise Bosl2ValueError("ring(): only the full-annulus form is ported (no angle=).")
    r1v = _pick_radius(radius=radius1, diameter=diameter1, dflt=None)
    r2v = _pick_radius(radius=radius2, diameter=diameter2, dflt=None)
    rv = _pick_radius(radius=radius, diameter=diameter, dflt=None)
    if r1v is not None and r2v is not None:
        inner, outer = min(r1v, r2v), max(r1v, r2v)
    else:
        if rv is None or ring_width is None:
            raise Bosl2ValueError("ring(): needs two sizes -- give radius1= and radius2=, or radius= with ring_width=.")
        inner, outer = min(rv, rv + ring_width), max(rv, rv + ring_width)
    if not (inner != outer):
        raise Bosl2ValueError(f"ring(): needs a positive wall between the radii; got inner={inner}, outer={outer}.")
    if outer <= 0:
        raise Bosl2ValueError(f"ring(): needs a positive outer radius; got {outer}.")
    fnv = sides if sides is not None else fn
    shape = circle(radius=outer, fn=fnv, fa=fa, fs=fs) - circle(radius=inner, fn=fnv, fa=fa, fs=fs)
    offset = _anchor_offset_box([2 * outer, 2 * outer], anchor)
    return _finish(shape, offset, spin, size=[2 * outer, 2 * outer], anchor=anchor)


@backend_only("csg")
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
        fn: arc smoothness overrides. Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back
            out to fa/fs.
        fa: arc smoothness overrides. Omitted, the ambient ``use_defaults(fa=...)`` value applies.
        fs: arc smoothness overrides. Omitted, the ambient ``use_defaults(fs=...)`` value applies.

    Examples:
        .. pythonscad-example::

            from pybosl2 import shapes2d as s2

            s2.glued_circles(radius=10, spread=25, tangent=30).linear_extrude(height=5).show()

    """
    rad = _pick_radius(radius=radius, diameter=diameter, dflt=10)
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


@backend_only("csg")
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
    """Return a Reuleaux polygon (constant-width curved-side shape), built directly with polygon().

    Args:
        sides:    number of "sides"; must be an odd positive number (default 3)
        radius:   scale the shape to fit in a circle of this radius
        diameter: scale the shape to fit in a circle of this diameter
        anchor:   anchor point (default CENTER)
        spin:     Z-axis rotation in degrees after anchor (default 0)
        fn: arc smoothness overrides. Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back
            out to fa/fs.
        fa: arc smoothness overrides. Omitted, the ambient ``use_defaults(fa=...)`` value applies.
        fs: arc smoothness overrides. Omitted, the ambient ``use_defaults(fs=...)`` value applies.

    Examples:
        .. pythonscad-example::

            from pybosl2 import shapes2d as s2

            s2.reuleaux_polygon(sides=3, radius=15).linear_extrude(height=5).show()

    """
    if sides < 3 or sides % 2 == 0:
        raise Bosl2ValueError(f"reuleaux_polygon(): sides must be an odd number of 3 or more, got {sides}.")
    rad = _pick_radius(radius=radius, diameter=diameter, dflt=1)
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

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/shapes2d/curves.py
# FileSummary: Stars, teardrops, eggs, squircles and supershapes.
# DocCategory: Foundational
# FileGroup: BOSL2

"""Stars, teardrops, eggs, squircles and supershapes."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from typing import TYPE_CHECKING, Union

import numpy as np

from pybosl2._backend import backend_only

# Import base class and helper functions from shapes2d.base
from pybosl2._helpers import (
    AnchorType,
)
from pybosl2._helpers import (
    anchor_offset_generic as _anchor_offset_generic,
)
from pybosl2._helpers import (
    anchor_offset_hull as _anchor_offset_hull,
)
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
    rotate2d as _rotate2d,
)
from pybosl2._native import native
from pybosl2.constants import CENTER
from pybosl2.vectors import unit

from .base import (
    Bosl2Shape2D,
    _arc_between_points,
    _arc_through_3,
    _circle_circle_intersection,
    _finish,
)

if TYPE_CHECKING:
    from openscad import PyOpenSCAD

    from pybosl2._edges_lang import Anchor
    from pybosl2.path2d import Path2D


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


@backend_only("csg")
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
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    atype: str | AnchorType = AnchorType.HULL,
) -> Bosl2Shape2D:
    """Return an N-pointed star polygon, built directly with polygon().

    Note: BOSL2's outer-radius parameter is named `or`, which collides with the Python
    keyword `or`; it is exposed here as `outer_radius` instead.

    Args:
        tips:           number of stellate tips
        radius:         radius to the tips of the star
        outer_radius:   radius to the tips of the star (BOSL2 `or`); alias for radius
        inner_radius:   radius to the inner corners of the star
        diameter:       diameter to the tips of the star
        outer_diameter: diameter to the tips of the star; alias for diameter
        inner_diameter: diameter to the inner corners of the star
        step:           compute inner radius by virtually drawing a line `step` tips around the star (2 <= step < tips)
        realign:        put the midpoint of the last edge (instead of vertex 0) on the X+ axis (default False)
        align_tip:      rotate so the first tip points in this 2-D direction (applied before spin)
        align_pit:      rotate so the first inner corner points in this 2-D direction (applied before spin)
        anchor:         anchor point (default CENTER)
        spin:           Z-axis rotation in degrees after anchor (default 0)
        atype:          anchor method (default AnchorType.HULL)

    Examples:
        .. pythonscad-example::

            from pybosl2 import shapes2d as s2

            s2.star(tips=5, radius=20, inner_radius=8).linear_extrude(height=5).show()

    """
    rad = _pick_radius(radius1=outer_radius, diameter1=outer_diameter, radius=radius, diameter=diameter)
    if rad is None:
        raise ValueError("star(): must specify a radius (radius, diameter, outer_radius or outer_diameter).")
    if not (tips is not None):
        raise ValueError("star(): must specify tips")
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


@backend_only("csg")
def teardrop2d(
    radius: float | None = None,
    angle: float = 45,
    cap_height: float | None = None,
    diameter: float | None = None,
    circumscribe: bool = False,
    realign: bool = False,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """Return a 2-D teardrop shape, useful for 3D-printable horizontal holes, built directly with polygon().

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
        fn: arc smoothness overrides
        fa: arc smoothness overrides
        fs: arc smoothness overrides

    Examples:
        .. pythonscad-example::

            from pybosl2 import shapes2d as s2

            s2.teardrop2d(radius=15, angle=45).linear_extrude(height=5).show()

    """
    rad = _pick_radius(radius=radius, diameter=diameter, dflt=1)
    if circumscribe:
        n = _frag_count(rad, fn, fa, fs)
        rad /= math.cos(math.pi / n)
    minheight = rad * math.sin(math.radians(angle))
    maxheight = rad / math.sin(math.radians(angle))
    if cap_height is not None and cap_height < minheight:
        raise ValueError(f"cap_height cannot be less than {minheight} but it is {cap_height}")
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


@backend_only("csg")
def egg(
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    arc_radius: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    arc_diameter: float | None = None,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """Return an egg-shaped 2-D outline, made of two circles joined by tangent arcs, built directly with polygon().

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
        fn: arc smoothness overrides
        fa: arc smoothness overrides
        fs: arc smoothness overrides

    Examples:
        .. pythonscad-example::

            from pybosl2 import shapes2d as s2

            s2.egg(length=30, radius1=10, radius2=8, arc_radius=20).linear_extrude(height=5).show()

    """
    radius1 = _pick_radius(radius=radius1, diameter=diameter1, dflt=None)
    if radius1 is None:
        raise ValueError("egg(): must give radius1 or diameter1")
    radius2 = _pick_radius(radius=radius2, diameter=diameter2, dflt=None)
    if radius2 is None:
        raise ValueError("egg(): must give radius2 or diameter2")
    arc_r = _pick_radius(radius=arc_radius, diameter=arc_diameter, dflt=None)
    if arc_r is None:
        raise ValueError("egg(): must give arc_radius or arc_diameter")
    if not (length is not None):
        raise ValueError("egg(): must give length")
    path = _egg_path(length, radius1, radius2, arc_r, fn, fa, fs)
    shape = _opolygon(path)
    offset = _anchor_offset_hull(path, anchor)
    return _finish(shape, offset, spin)


def _egg_path(
    length: float,
    radius1: float,
    radius2: float,
    arc_radius: float,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> list[list[float]]:
    assert length > 0
    if not (arc_radius > length / 2):
        raise ValueError("Side radius must be larger than length/2")
    if not (length > radius1 + radius2):
        raise ValueError("Length must be longer than radius1+radius2")
    c1 = [-length / 2 + radius1, 0.0]
    c2 = [length / 2 - radius2, 0.0]
    m_pts = list(reversed(_circle_circle_intersection(arc_radius - radius1, c1, arc_radius - radius2, c2)))
    if not (len(m_pts) == 2):
        raise ValueError("egg(): circles do not intersect for the given length/radius1/radius2/arc_radius.")
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
    path: list[list[float]] = []
    path += _arc_between_points(c2, [length / 2, 0.0], arcparms[0][2], radius2, endpoint=False, fn=fn, fa=fa, fs=fs)
    path += _arc_between_points(
        arcparms[0][0], arcparms[0][2], arcparms[0][1], arc_radius, endpoint=False, fn=fn, fa=fa, fs=fs
    )
    path += _arc_through_3(
        c1,
        radius1,
        arcparms[0][1],
        [-length / 2, 0.0],
        arcparms[1][1],
        endpoint=False,
        fn=fn,
        fa=fa,
        fs=fs,
    )
    path += _arc_between_points(
        arcparms[1][0], arcparms[1][1], arcparms[1][2], arc_radius, endpoint=False, fn=fn, fa=fa, fs=fs
    )
    path += _arc_between_points(c2, arcparms[1][2], [length / 2, 0.0], radius2, endpoint=False, fn=fn, fa=fa, fs=fs)
    return path


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
    return (t1 + t2) ** (-1.0 / n1)  # type: ignore[no-any-return]


@backend_only("csg")
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
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    atype: str | AnchorType = AnchorType.HULL,
) -> Bosl2Shape2D:
    """Return a 2-D shape from the superformula, built directly with polygon().

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

    Examples:
        .. pythonscad-example::

            from pybosl2 import shapes2d as s2

            s2.supershape(m1=3, radius=20).linear_extrude(height=5).show()

    """
    n_pts = count if count is not None else math.ceil(360.0 / step)
    n1v = n1 if n1 is not None else 1
    m2v = m2 if m2 is not None else m1
    n2v = n2 if n2 is not None else n1v
    n3v = n3 if n3 is not None else n2v
    bv = b if b is not None else a
    angles = [360.0 - i * 360.0 / n_pts for i in range(n_pts)]
    rvals = [_superformula(t, m1, m2v, n1v, n2v, n3v, a, bv) for t in angles]
    target_radius = _pick_radius(radius=radius, diameter=diameter, dflt=None)
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
    """Return the Fong-Garcia squircle radius at *angle* degrees for squareness *squareness* and size.

    *radius*.
    """
    s2a = abs(squareness * math.sin(math.radians(2 * angle)))
    return radius * math.sqrt(2) / s2a * math.sqrt(1 - math.sqrt(1 - s2a * s2a)) if s2a > 0 else radius


def _squircle_fg_path(
    size: Sequence[float],
    squareness: float,
    fn: int | None,
    fa: float | None,
    fs: float | None,
) -> list[list[float]]:
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


@backend_only("csg")
def squircle(
    size: float | Sequence[float],
    squareness: float = 0.5,
    style: str = "fg",
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """Return a squircle -- a rounded square that morphs between a square and a circle.

    *squareness* runs 0 (a circle) to 1 (a square). Only the default ``"fg"`` (Fong-Garcia) style
    is ported; the ``"superellipse"`` and ``"bezier"`` styles are not.

    Args:
        size:       scalar or [x, y] size of the bounding box
        squareness: 0 (circle) .. 1 (square); default 0.5
        style:      only "fg" is supported
        anchor:     standard BOSL2 2-D anchor
        spin:       standard BOSL2 2-D spin
        fn: smoothness overrides
        fa: smoothness overrides
        fs: smoothness overrides

    Examples:
        .. pythonscad-example::

            from pybosl2 import shapes2d as s2

            s2.squircle(40, squareness=0.7).linear_extrude(height=5).show()

    """
    if not (0 <= squareness <= 1):
        raise ValueError("squircle(): squareness must be between 0 and 1.")
    sz = [float(size), float(size)] if isinstance(size, (int, float)) else [float(size[0]), float(size[1])]
    if not (style == "fg"):
        raise ValueError('squircle(): only the default "fg" style is ported.')
    path = _squircle_fg_path(sz, squareness, fn, fa, fs)
    shape = _opolygon(path)
    offset = _anchor_offset_hull(path, anchor)
    return _finish(shape, offset, spin)


# ---------------------------------------------------------------------------
# Section: Curved 2D Shapes
# ---------------------------------------------------------------------------


@backend_only("csg")
def jittered_poly(path: Sequence[Sequence[float]], dist: float = 1 / 512) -> list[list[float]]:
    """Add tiny random jitter to a path's points.

    Used to work around rendering artifacts from exactly-overlapping coplanar faces.

    Args:
        path: the path to add jitter to
        dist: the amount to jitter points by (default 1/512)

    """
    return [[p[0] + random.uniform(-dist, dist), p[1] + random.uniform(-dist, dist)] for p in path]

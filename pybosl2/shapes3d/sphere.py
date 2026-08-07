# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/shapes3d/sphere.py
# FileSummary: Spheres, spheroids, onions and teardrops.
# DocCategory: Foundational
# FileGroup: BOSL2

"""Spheres, spheroids, onions and teardrops."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pybosl2._edges_lang import Anchor
from pybosl2._native import native

if TYPE_CHECKING:
    from collections.abc import Sequence


from pybosl2._helpers import frag_count as _frag_count
from pybosl2._helpers import pick_radius as _pick_radius

# Import base class and helper functions from shapes3d.base
from .base import (
    Bosl2Solid,
    _anchor_offset_cyl,
    _finish3,
    _osphere,
)

if TYPE_CHECKING:  # real stub-typed imports for the checker (identical to pre-lazy)
    from pythonscad import cube as _ocube
    from pythonscad import cylinder as _ocylinder_native
    from pythonscad import hull as _ohull
    from pythonscad import minkowski as _ominkowski
    from pythonscad import polyhedron as _opolyhedron
    from pythonscad import rotate_extrude as _orotate_extrude
    from pythonscad import sphere as _osphere_native
    from pythonscad import textmetrics as _otextmetrics
else:
    _ocube = native("cube")
    _ocylinder_native = native("cylinder")
    _ohull = native("hull")
    _ominkowski = native("minkowski")
    _opolyhedron = native("polyhedron")
    _orotate_extrude = native("rotate_extrude")
    _osphere_native = native("sphere")
    _otextmetrics = native("textmetrics")


def _anchor_offset_sphere(radius: float, anchor: Anchor | Sequence[float]) -> list[float]:
    a = anchor.vector if isinstance(anchor, Anchor) else list(anchor)
    sides = math.hypot(*a)
    if sides == 0:
        return [0.0, 0.0, 0.0]
    return [-a[i] / sides * radius for i in range(3)]


# ---------------------------------------------------------------------------
# Section: Other Round Objects
# ---------------------------------------------------------------------------


def sphere(
    radius: float | None = None,
    diameter: float | None = None,
    circumscribe: bool = False,
    anchor: Anchor | Sequence[float] = Anchor.CENTER,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """Return a sphere, built with the builtin sphere(), with BOSL2-style anchor/spin/orient support.

    Note: `style=` is accepted for signature compatibility but not applied; the
    builtin sphere() is used directly.

    Args:
        radius:      radius of the sphere
        diameter:      diameter of the sphere
        circumscribe:  circumscribe rather than inscribe the sphere (default False)
        anchor: anchor point (default CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)
        orient: direction to rotate the top towards, after spin (default UP)
        fn: arc smoothness overrides
        fa: arc smoothness overrides
        fs: arc smoothness overrides

    Examples:
        .. pythonscad-example::

            from pybosl2.solid import sphere

            shape = sphere(radius=15)
            shape.show()

    """
    rad = radius if radius is not None else (diameter / 2 if diameter is not None else 1)
    if circumscribe:
        sides = _frag_count(rad, fn, fa, fs)
        rad /= math.cos(math.pi / sides)
    shape = _osphere(radius=rad, fn=fn, fa=fa, fs=fs)
    offset = _anchor_offset_sphere(rad, anchor)
    return _finish3(shape, offset, spin, orient, size=None, anchor=anchor)


def spheroid(
    radius: float | None = None,
    diameter: float | None = None,
    circumscribe: bool = False,
    anchor: Anchor | Sequence[float] = Anchor.CENTER,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """Return an approximate sphere; this pure-Python port just builds a plain sphere() (style/dual are ignored).

    Args:
        radius:      radius of the spheroid
        diameter:      diameter of the spheroid
        circumscribe:  circumscribe rather than inscribe the spheroid (default False)
        anchor: anchor point (default CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)
        orient: direction to rotate the top towards, after spin (default UP)
        fn: arc smoothness overrides
        fa: arc smoothness overrides
        fs: arc smoothness overrides

    Examples:
        .. pythonscad-example::

            from pybosl2.solid import spheroid

            spheroid(radius=15).show()

    """
    return sphere(
        radius=radius,
        diameter=diameter,
        circumscribe=circumscribe,
        anchor=anchor,
        spin=spin,
        orient=orient,
        fn=fn,
        fa=fa,
        fs=fs,
    )


def _teardrop2d_path(
    radius: float,
    angle: float,
    cap_height: float | None,
    circum: bool,
    realign: bool,
    sides: int,
) -> list[list[float]]:
    """Return the 2-D (X,Y) outline of a BOSL2-style teardrop2d(): a circle of radius *radius* capped by a.

    point (or, if *cap_height* truncates it, a flat top) formed by two walls tangent to the circle at
    +-*angle* degrees from the Y axis. *sides* is the segment count for a full circle of this radius
    (as from _frag_count()); *realign* is approximated by toggling the parity of the round
    section's vertex count, since a vertex landing exactly at the bottom gives a "point" and a
    vertex straddling it gives a "flat" bottom -- the same effect BOSL2 gets from its own $fn
    discretization.
    """
    from pybosl2._helpers import arc_points as _arc_points

    rad = radius / math.cos(math.pi / sides) if circum else radius
    maxheight = rad / math.sin(math.radians(angle))
    minheight = rad * math.sin(math.radians(angle))
    assert cap_height is None or cap_height >= minheight - 1e-9, (
        "teardrop2d(): cap_height cannot be less than radius*sin(angle)."
    )
    pointy = cap_height is None or cap_height >= maxheight

    sweep = 180 + 2 * angle
    pts = max(2, round(sides * sweep / 360)) + 1
    if realign == (pts % 2 == 1):
        pts += 1
    arc = _arc_points(pts, rad, angle, -sweep, [0.0, 0.0])

    if pointy or cap_height is None:
        return [[0.0, maxheight]] + arc
    cap_x = (maxheight - cap_height) * math.tan(math.radians(angle))
    return [[cap_x, cap_height]] + arc + [[-cap_x, cap_height]]


def teardrop(
    height: float | None = None,
    radius: float | None = None,
    angle: float = 45,
    cap_height: float | None = None,
    circumscribe: bool = False,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    cap_h1: float | None = None,
    cap_h2: float | None = None,
    chamfer: float = 0,
    chamfer1: float = 0,
    chamfer2: float = 0,
    realign: bool = False,
    anchor: Anchor | Sequence[float] = Anchor.CENTER,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """BOSL2 teardrop() -- a teardrop shape, useful for 3D-printable horizontal holes.

    Args:
        height:    thickness of the teardrop (default 1)
        radius:      radius of the circular part (default 1)
        angle:    angle of the hat walls from the Z axis in degrees (default 45)
        cap_height:  height above center to truncate the shape (default: no truncation)
        circumscribe: produce a circumscribing teardrop shape (default False)
        radius1:  radius of the circular portion of the front end
        radius2:  radius of the circular portion of the back end
        diameter: diameter of the circular portion
        diameter1: diameter of the front end
        diameter2: diameter of the back end
        cap_h1: truncation height on the front side
        cap_h2: truncation height on the back side
        chamfer: chamfer size along the bottom/top faces (overall) (default 0)
        chamfer1: chamfer size along the bottom face (default 0)
        chamfer2: chamfer size along the top face (default 0)
        realign: shift face alignment, passed to teardrop2d (default False)
        anchor: anchor point (default CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)
        orient: direction to rotate the top towards, after spin (default UP)
        fn: arc smoothness overrides
        fa: arc smoothness overrides
        fs: arc smoothness overrides

    Examples:
        .. pythonscad-example::

            from pybosl2.solid import teardrop

            shape = teardrop(radius=8, angle=45, height=15)
            shape.show()

    """
    length = height if height is not None else 1.0
    rad1 = _pick_radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
    rad2 = _pick_radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter, dflt=1)
    cap_h1v = cap_h1 if cap_h1 is not None else cap_height
    cap_h2v = cap_h2 if cap_h2 is not None else cap_height
    c1 = chamfer1 if chamfer1 else chamfer
    c2 = chamfer2 if chamfer2 else chamfer
    sides = _frag_count(max(rad1, rad2), fn, fa, fs)

    def section(rad: float, cap_hv: float | None, y: float) -> list[list[float]]:
        path = _teardrop2d_path(rad, angle, cap_hv, circumscribe, realign, sides)
        return [[p[0], y, p[1]] for p in path]

    front_y, back_y = -length / 2, length / 2
    slices = []
    if c1:
        cap_hv = (cap_h1v - c1) if cap_h1v is not None else None
        slices.append(section(max(0.001, rad1 - c1), cap_hv, front_y))
        front_y += abs(c1)
    slices.append(section(rad1, cap_h1v, front_y))
    if c2:
        back_y -= abs(c2)
    slices.append(section(rad2, cap_h2v, back_y))
    if c2:
        cap_hv = (cap_h2v - c2) if cap_h2v is not None else None
        slices.append(section(max(0.001, rad2 - c2), cap_hv, back_y + abs(c2)))

    solids = [_opolyhedron(pts, [list(range(len(pts)))]) for pts in slices]
    shape = solids[0]
    for a, b in zip(solids, solids[1:], strict=False):
        piece = _ohull(a, b)
        shape = piece if shape is solids[0] else (shape | piece)
    offset = _anchor_offset_cyl(rad1, rad2, length, anchor, axis=1)
    return _finish3(shape, offset, spin, orient, size=None, anchor=anchor)


def onion(
    radius: float | None = None,
    angle: float = 45,
    cap_height: float | None = None,
    circumscribe: bool = False,
    diameter: float | None = None,
    anchor: Anchor | Sequence[float] = Anchor.CENTER,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """BOSL2 onion() -- an onion-dome shape (a sphere with a conical cap).

    Args:
        radius:      radius of the spherical portion of the bottom (default 1)
        angle:    angle of the cone from vertical in degrees (default 45)
        cap_height:  height above the sphere center to truncate the shape (default: no truncation)
        circumscribe: circumscribe rather than inscribe the given radius/diameter (default False)
        diameter:      diameter of the spherical portion of the bottom
        anchor: anchor point (default CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)
        orient: direction to rotate the top towards, after spin (default UP)
        fn: arc smoothness overrides
        fa: arc smoothness overrides
        fs: arc smoothness overrides

    Examples:
        .. pythonscad-example::

            from pybosl2.solid import onion

            onion(radius=15).show()

    """
    from pybosl2._helpers import arc_points as _arc_points
    from pybosl2._native import native

    _opolygon = native("polygon")

    rad = _pick_radius(radius=radius, diameter=diameter, dflt=1)
    sides = _frag_count(rad, fn, fa, fs)
    scaled = rad / math.cos(math.pi / sides) if circumscribe else rad
    maxheight = scaled / math.sin(math.radians(angle))
    top_z = min(cap_height, maxheight) if cap_height is not None else maxheight
    pointy = top_z >= maxheight - 1e-9

    sweep = 90 + angle
    pts = max(2, round(sides * sweep / 360)) + 1
    arc = list(reversed(_arc_points(pts, scaled, angle, -sweep, [0.0, 0.0])))
    if pointy:
        profile = arc + [[0.0, top_z]]
    else:
        cap_x = (maxheight - top_z) * math.tan(math.radians(angle))
        profile = arc + [[cap_x, top_z], [0.0, top_z]]

    shape = _orotate_extrude(_opolygon(profile), fn=fn, fa=fa, fs=fs)

    a = list(anchor)
    off_z = 0.0 if a[2] == 0 else (scaled if a[2] < 0 else -top_z)
    rn = math.hypot(a[0], a[1])
    off_xy = [-a[0] / rn * scaled, -a[1] / rn * scaled] if rn > 0 else [0.0, 0.0]
    offset = [off_xy[0], off_xy[1], off_z]
    return _finish3(shape, offset, spin, orient, size=None, anchor=anchor)

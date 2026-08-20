# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/shapes2d/square.py
# FileSummary: Rectangles, squares, polygons, ngons and trapezoid shapes.
# DocCategory: Foundational
# FileGroup: BOSL2

"""Rectangles, squares, polygons, ngons and trapezoid shapes."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, Union

import numpy as np

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
from pybosl2._helpers import (
    rect_path as _rect_path,
)
from pybosl2._helpers import (
    rotate2d as _rotate2d,
)
from pybosl2._native import native
from pybosl2.constants import CENTER
from pybosl2.vectors import v_theta as _v_theta

from .base import (
    Bosl2Shape2D,
    _adjacent_angle_to_hypotenuse,
    _adjacent_angle_to_opposite,
    _finish,
    _opposite_angle_to_adjacent,
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


# ---------------------------------------------------------------------------
# Section: 2D Primitives
# ---------------------------------------------------------------------------


@backend_only("csg", neutral="pybosl2.flat.square")
def square(
    size: float | Sequence[float] = 1,
    center: bool | None = None,
    rounding: float | Sequence[float] = 0,
    chamfer: float | Sequence[float] = 0,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """Return a rectangle, built via polygon() with BOSL2-style anchor/spin support.

    Args:
        size:     size of the square; a scalar uses the same size for X and Y
        center:   if given, overrides anchor (True -> CENTER, False -> FRONT+LEFT)
        rounding: corner rounding radius, or per-corner list [X+Y+,X-Y+,X-Y-,X+Y-] (default 0)
        chamfer:  corner chamfer size, or per-corner list [X+Y+,X-Y+,X-Y-,X+Y-] (default 0)
        anchor:   anchor point (default CENTER)
        spin:     Z-axis rotation in degrees after anchor (default 0)
        fn: arc smoothness overrides for rounded corners
        fa: arc smoothness overrides for rounded corners
        fs: arc smoothness overrides for rounded corners

    Examples:
        .. pythonscad-example::

            from pybosl2 import shapes2d as s2

            s2.square(20).linear_extrude(height=5).show()

    """
    assert not (rounding and chamfer), "Cannot set both rounding and chamfer at the same time."
    sz = [float(size), float(size)] if isinstance(size, (int, float)) else [float(v) for v in size]
    use_anchor = anchor
    if center is not None:
        use_anchor = CENTER if center else [-1, -1, 0]
    if rounding != 0 or chamfer != 0:
        path = _rect_path(sz, rounding=rounding, chamfer=chamfer, fn=fn, fa=fa, fs=fs)
        shape = _opolygon(path)
        offset = _anchor_offset_hull(path, use_anchor)
        return _finish(shape, offset, spin or 0, size=sz, anchor=use_anchor)
    shape = _osquare(sz, center=True)
    offset = _anchor_offset_box(sz, use_anchor)
    return _finish(shape, offset, spin or 0, size=sz, anchor=use_anchor)


@backend_only("csg", neutral="pybosl2.flat.rect")
def rect(
    size: float | Sequence[float] = 1,
    rounding: float | Sequence[float] = 0,
    atype: str = "box",
    chamfer: float | Sequence[float] = 0,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """Return a rectangle with optional rounded or chamfered corners.

    Note: negative rounding/chamfer (BOSL2's "external roundover spikes") is not supported here.

    Args:
        size:     size of the rectangle; a scalar uses the same size for X and Y
        rounding: corner rounding radius, or per-corner list [X+Y+,X-Y+,X-Y-,X+Y-] (default 0)
        atype:    anchor type, "box" (bounding box) or "perim" (rounded/chamfered perimeter) (default "box")
        chamfer:  corner chamfer size, or per-corner list [X+Y+,X-Y+,X-Y-,X+Y-] (default 0)
        anchor:   anchor point (default CENTER)
        spin:     Z-axis rotation in degrees after anchor (default 0)
        fn: arc smoothness overrides for rounded corners
        fa: arc smoothness overrides for rounded corners
        fs: arc smoothness overrides for rounded corners

    """
    rl = [float(rounding)] * 4 if isinstance(rounding, (int, float)) else [float(v) for v in rounding]
    cl = [float(chamfer)] * 4 if isinstance(chamfer, (int, float)) else [float(v) for v in chamfer]
    msg = "Cannot set both rounding and chamfer on the same corner."
    assert not any(a and b for a, b in zip(rl, cl, strict=False)), msg
    sz = [float(size), float(size)] if isinstance(size, (int, float)) else list(size)
    path = _rect_path(sz, rounding=rounding, chamfer=chamfer, fn=fn, fa=fa, fs=fs)
    shape = _opolygon(path)
    complex_shape = (rounding != 0 if isinstance(rounding, (int, float)) else any(rounding)) or (
        chamfer != 0 if isinstance(chamfer, (int, float)) else any(chamfer)
    )
    if complex_shape and atype == "perim":
        offset = _anchor_offset_hull(path, anchor)
        return _finish(shape, offset, spin, size=sz, anchor=anchor)
    offset = _anchor_offset_box(sz, anchor)
    return _finish(shape, offset, spin, size=sz, anchor=anchor)


@backend_only("csg")
def rect_path(
    size: float | Sequence[float] = 1,
    rounding: float | Sequence[float] = 0,
    chamfer: float | Sequence[float] = 0,
    anchor: Anchor | Sequence[float] = CENTER,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> list[list[float]]:
    """Return the *points* of a (optionally rounded/chamfered) rectangle -- BOSL2's ``rect()`` in its.

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
        fn: number of fragments for circle resolution.
        fa: minimum fragment angle for circle resolution.
        fs: minimum fragment size for circle resolution.

    Note:
        For small radii this can emit one more point per corner than the real BOSL2 does
        (BOSL2 rounds the corner-arc segment count, this rounds up); the arc geometry is
        identical, only the sampling differs.

    """
    sz = [float(size), float(size)] if isinstance(size, (int, float)) else [float(v) for v in size]
    path = _rect_path(sz, rounding=rounding, chamfer=chamfer, fn=fn, fa=fa, fs=fs)
    offset = _anchor_offset_box(sz, anchor)
    return [[float(p[0]) + offset[0], float(p[1]) + offset[1]] for p in path]


@backend_only("csg", neutral="pybosl2.flat.polygon")
def polygon(
    path: Path2D,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
) -> Bosl2Shape2D:
    """Return a polygon with anchor/spin support.

    Args:
        path:   polygon path
        anchor: anchor point (default CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)

    """
    return _finish(_opolygon(path), anchor, spin)


# ---------------------------------------------------------------------------
# Section: Polygons
# ---------------------------------------------------------------------------


def _regular_ngon_path(
    sides: int,
    radius: float,
    rounding: float = 0,
    chamfer: float = 0,
    realign: bool = False,
    align_tip: Sequence[float] | None = None,
    align_side: Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> list[list[float]]:
    if not rounding and not chamfer:
        path = _circle_pts(radius, sides)
    else:
        assert not (rounding and chamfer), "Cannot set both rounding and chamfer at the same time on an n-gon."
        half_angle = math.radians((180 - 360.0 / sides) / 2)
        inset: float = chamfer / math.sin(half_angle) if chamfer else rounding / math.sin(half_angle)
        assert inset < radius, (
            f"{'chamfer' if chamfer else 'rounding'} value {chamfer or rounding} is too large "
            f"for a {sides}-gon of radius {radius}"
        )
        assert inset < radius, (
            f"{'chamfer' if chamfer else 'rounding'} value {chamfer or rounding} is too large "
            f"for a {sides}-gon of radius {radius}"
        )
        steps = max(1, int(_frag_count(radius, fn, fa, fs) // sides))
        path2: list[list[float]] = []
        for i in range(sides):
            a = 360 - i * 360.0 / sides
            p = _polar_to_xy(radius - inset, a)
            if chamfer:
                half_angle = math.radians(180.0 / sides)
                chamf_len = chamfer / math.sin(half_angle) * math.cos(half_angle)
                c1 = [
                    p[0] + chamf_len * math.cos(math.radians(a - 90)),
                    p[1] + chamf_len * math.sin(math.radians(a - 90)),
                ]
                c2 = [
                    p[0] + chamf_len * math.cos(math.radians(a + 90)),
                    p[1] + chamf_len * math.sin(math.radians(a + 90)),
                ]
                path2.append(c1)
                path2.append(c2)
            else:
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


@backend_only("csg")
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
    chamfer: float = 0,
    realign: bool = False,
    align_tip: Sequence[float] | None = None,
    align_side: Sequence[float] | None = None,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """Return a regular N-gon (equilateral, equiangular polygon), built directly with polygon().

    Note: BOSL2's outer-radius parameter is named `or`, which collides with the Python
    keyword `or`; it is exposed here as `outer_radius` instead.

    Args:
        sides:          number of sides (default 6)
        radius:         outside radius, at the points
        outer_radius:   outside radius, at the points (BOSL2 ``or``)
        diameter:       outside diameter, at the points
        outer_diameter: outside diameter, at the points
        inner_radius:   inside radius, at the center of the sides
        inner_diameter: inside diameter, at the center of the sides
        side:           length of each side
        rounding:       rounding radius for the tips of the polygon (default 0)
        chamfer:        chamfer size for the tips of the polygon (default 0)
        realign:        put the midpoint of the last edge (instead of vertex 0) on the X+ axis (default False)
        align_tip:      rotate so the first vertex points in this 2-D direction (applied before spin)
        align_side:     rotate so the normal of side 0 points in this 2-D direction (applied before spin)
        anchor:         anchor point (default CENTER)
        spin:           Z-axis rotation in degrees after anchor (default 0)
        fn: arc smoothness overrides for rounded tips
        fa: arc smoothness overrides for rounded tips
        fs: arc smoothness overrides for rounded tips

    Examples:
        .. pythonscad-example::

            from pybosl2 import shapes2d as s2

            s2.regular_ngon(sides=6, radius=15).linear_extrude(height=5).show()

    """
    assert not (rounding and chamfer), "Cannot set both rounding and chamfer at the same time."
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
        chamfer=chamfer,
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


@backend_only("csg")
def pentagon(
    radius: float | None = None,
    diameter: float | None = None,
    outer_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_radius: float | None = None,
    inner_diameter: float | None = None,
    side: float | None = None,
    rounding: float = 0,
    chamfer: float = 0,
    realign: bool = False,
    align_tip: Sequence[float] | None = None,
    align_side: Sequence[float] | None = None,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """Return a regular pentagon. See regular_ngon() for argument details."""
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
        chamfer=chamfer,
        realign=realign,
        align_tip=align_tip,
        align_side=align_side,
        anchor=anchor,
        spin=spin,
        fn=fn,
        fa=fa,
        fs=fs,
    )


@backend_only("csg")
def hexagon(
    radius: float | None = None,
    diameter: float | None = None,
    outer_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_radius: float | None = None,
    inner_diameter: float | None = None,
    side: float | None = None,
    rounding: float = 0,
    chamfer: float = 0,
    realign: bool = False,
    align_tip: Sequence[float] | None = None,
    align_side: Sequence[float] | None = None,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """Return a regular hexagon. See regular_ngon() for argument details."""
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
        chamfer=chamfer,
        realign=realign,
        align_tip=align_tip,
        align_side=align_side,
        anchor=anchor,
        spin=spin,
        fn=fn,
        fa=fa,
        fs=fs,
    )


@backend_only("csg")
def octagon(
    radius: float | None = None,
    diameter: float | None = None,
    outer_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_radius: float | None = None,
    inner_diameter: float | None = None,
    side: float | None = None,
    rounding: float = 0,
    chamfer: float = 0,
    realign: bool = False,
    align_tip: Sequence[float] | None = None,
    align_side: Sequence[float] | None = None,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """Return a regular octagon. See regular_ngon() for argument details."""
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
        chamfer=chamfer,
        realign=realign,
        align_tip=align_tip,
        align_side=align_side,
        anchor=anchor,
        spin=spin,
        fn=fn,
        fa=fa,
        fs=fs,
    )


@backend_only("csg")
def right_triangle(
    size: Sequence[float] = (1, 1),
    center: bool | None = None,
    rounding: float = 0,
    chamfer: float = 0,
    anchor: Anchor | Sequence[float] | None = None,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """Return a right triangle, built directly with polygon().

    Args:
        size:     [width, length] of the right triangle
        center:   True forces anchor=CENTER, False forces anchor=[-1,-1] (default: use anchor=)
        rounding: corner rounding radius (default 0)
        chamfer:  corner chamfer size (default 0)
        anchor:   anchor point (default: [-1,-1], the right-angle corner)
        spin:     Z-axis rotation in degrees after anchor (default 0)
        fn: arc smoothness overrides for rounded corners
        fa: arc smoothness overrides for rounded corners
        fs: arc smoothness overrides for rounded corners

    Examples:
        .. pythonscad-example::

            from pybosl2 import shapes2d as s2

            s2.right_triangle(size=[30, 20]).linear_extrude(height=5).show()

    """
    assert not (rounding and chamfer), "Cannot set both rounding and chamfer at the same time."
    sz: Sequence[float] = [float(size), float(size)] if isinstance(size, (int, float)) else size
    if anchor is not None:
        use_anchor = anchor
    elif center:
        use_anchor = CENTER
    else:
        use_anchor = [-1, -1, 0]
    shape = _opolygon([[sz[0] / 2, -sz[1] / 2], [-sz[0] / 2, -sz[1] / 2], [-sz[0] / 2, sz[1] / 2]])
    bshape = Bosl2Shape2D(shape)
    if chamfer:
        bshape = bshape.offset(delta=chamfer, chamfer=True).offset(delta=-chamfer)
    if rounding:
        bshape = bshape.offset(radius=rounding, fn=fn, fa=fa, fs=fs)
    offset = _anchor_offset_box(sz, use_anchor)
    return _finish(bshape.__scad__(), offset, spin, size=sz, anchor=use_anchor)


def _trapezoid_path(
    height: float,
    width1: float,
    width2: float,
    shift: float,
    chamfer: float | Sequence[float],
    rounding: float | Sequence[float],
    flip: bool,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> list[list[float]]:
    chamfs: list[float] = list(chamfer) if isinstance(chamfer, (list, tuple)) else [chamfer] * 4  # type: ignore[list-item]
    rounds: list[float] = list(rounding) if isinstance(rounding, (list, tuple)) else [rounding] * 4  # type: ignore[list-item]
    srads: list[float] = [rounds[i] if rounds[i] else chamfs[i] for i in range(4)]
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


@backend_only("csg")
def trapezoid(
    height: float | None = None,
    width1: float | None = None,
    width2: float | None = None,
    angle: float | None = None,
    shift: float = 0,
    chamfer: float | Sequence[float] = 0,
    rounding: float | Sequence[float] = 0,
    flip: bool = False,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """Return a trapezoid with parallel front and back sides, built directly with polygon().

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
        fn: arc smoothness overrides for rounded corners
        fa: arc smoothness overrides for rounded corners
        fs: arc smoothness overrides for rounded corners

    Examples:
        .. pythonscad-example::

            from pybosl2 import shapes2d as s2

            s2.trapezoid(height=20, width1=30, width2=15).linear_extrude(height=5).show()

    """
    defined = sum(x is not None for x in (height, width1, width2, angle))
    assert defined == 3, "Must give exactly 3 of the arguments height, width1, width2, and angle."
    if height is None:
        assert width1 is not None
        assert width2 is not None
        assert angle is not None
        height = _opposite_angle_to_adjacent(abs(width2 - width1) / 2, abs(angle))
    if width1 is None:
        assert width2 is not None
        assert angle is not None
        width1 = width2 + 2 * (_adjacent_angle_to_opposite(height, angle) + shift)
    if width2 is None:
        assert width1 is not None
        assert angle is not None
        width2 = width1 - 2 * (_adjacent_angle_to_opposite(height, angle) + shift)
    assert width1 >= 0, "Degenerate trapezoid geometry."
    assert width2 >= 0, "Degenerate trapezoid geometry."
    assert height > 0, "Degenerate trapezoid geometry."
    assert width1 + width2 > 0, "Degenerate trapezoid geometry."
    path = _trapezoid_path(height, width1, width2, shift, chamfer, rounding, flip, fn, fa, fs)
    shape = _opolygon(path)
    offset = _anchor_offset_hull(path, anchor)
    return _finish(shape, offset, spin)

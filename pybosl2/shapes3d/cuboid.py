# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/shapes3d/cuboid.py
# FileSummary: Cubes, prismoids, wedges and general polygonal prism shapes.
# DocCategory: Foundational
# FileGroup: BOSL2

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from pybosl2._edges_lang import Anchor
from pybosl2._native import native

if TYPE_CHECKING:
    from collections.abc import Sequence

    from openscad import PyOpenSCAD

    from pybosl2.points import Point

from pybosl2.constants import BOTTOM, CENTER, FRONT, LEFT, UP
from pybosl2.shapes2d import _frag_count

# Import base class and helper functions from shapes3d.base
from .base import (
    Bosl2Solid,
    _anchor_offset_box3,
    _anchor_offset_cyl,
    _anchor_offset_hull3,
    _finish3,
    _ocylinder,
    _osphere,
    _quantup,
    _resolve_center_anchor,
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

from pybosl2._edges_lang import EDGE_OFFSETS, EDGES_ALL, _edges
from pybosl2.shapes3d.cylinder import _cyl_profile


def _corner_edges(edges: Sequence[Sequence[float]], v: Sequence[float]) -> list[int]:
    u = [(v[i] + 1) / 2 for i in range(3)]
    return [
        int(edges[0][int(u[1] + u[2] * 2)]),
        int(edges[1][int(u[0] + u[2] * 2)]),
        int(edges[2][int(u[0] + u[1] * 2)]),
    ]


def _rotate_to_axis(shape: PyOpenSCAD, axis: int) -> PyOpenSCAD:
    if axis == 0:
        return shape.rotate(90, [0, 1, 0])
    if axis == 1:
        return shape.rotate(-90, [1, 0, 0])
    return shape


def _trunc_cube(s: Sequence[float], corner: Sequence[float]) -> PyOpenSCAD:
    """A small cube with the corner facing away from *corner* trimmed off diagonally (7 vertices).

    Used to trim corner_shape() geometry down to just the correct octant of a cuboid corner.
    """
    pts = [[1, 1, 1], [1, 1, 0], [1, 0, 0], [0, 1, 1], [0, 1, 0], [1, 0, 1], [0, 0, 1]]
    faces = [
        [0, 1, 2],
        [2, 5, 0],
        [0, 5, 6],
        [0, 6, 3],
        [0, 3, 4],
        [0, 4, 1],
        [1, 4, 2],
        [3, 6, 4],
        [5, 2, 6],
        [2, 4, 6],
    ]
    scaled = [
        [
            (p[0] - 0.5) * (s[0] + 0.001),
            (p[1] - 0.5) * (s[1] + 0.001),
            (p[2] - 0.5) * (s[2] + 0.001),
        ]
        for p in pts
    ]
    shape = _opolyhedron(scaled, faces)
    if corner[0] < 0:
        shape = shape.mirror([1, 0, 0])
    if corner[1] < 0:
        shape = shape.mirror([0, 1, 0])
    if corner[2] < 0:
        shape = shape.mirror([0, 0, 1])
    return shape


def _corner_shape(
    corner: Sequence[float],
    size: Sequence[float],
    edges: Sequence[Sequence[float]],
    radius: float,
    is_chamfer: bool,
    trimcorners: bool,
    fn: int | None,
    fa: float | None,
    fs: float | None,
) -> PyOpenSCAD:
    e = _corner_edges(edges, corner)
    cnt = sum(e)
    c = [radius, radius, radius]
    m = 0.01
    c2 = [corner[i] * c[i] / 2 for i in range(3)]
    c3 = [corner[i] * (c[i] - m / 2) for i in range(3)]
    fn = 4 if is_chamfer else max(4, int(_quantup(_frag_count(radius, fn, fa, fs), 4)))
    base_t = [corner[i] * (size[i] / 2 - c[i]) for i in range(3)]

    def xtcyl(length: float, radius: float) -> "PyOpenSCAD":
        return _rotate_to_axis(_ocylinder(height=length, radius=radius, center=True, fn=fn), 0)

    def ytcyl(length: float, radius: float) -> "PyOpenSCAD":
        return _rotate_to_axis(_ocylinder(height=length, radius=radius, center=True, fn=fn), 1)

    def ztcyl(length: float, radius: float) -> "PyOpenSCAD":
        return _ocylinder(height=length, radius=radius, center=True, fn=fn)

    def tsphere(radius: float) -> "PyOpenSCAD":
        return _osphere(radius=radius, fn=fn)

    if cnt == 0 or radius == 0:
        shape = _ocube(m, center=True).translate(c3)
    elif cnt == 1:
        if e[0]:
            shape = xtcyl(c[0] * 2, radius).translate([c3[0], 0, 0])
        elif e[1]:
            shape = ytcyl(c[1] * 2, radius).translate([0, c3[1], 0])
        else:
            shape = ztcyl(c[2] * 2, radius).translate([0, 0, c3[2]])
        shape = shape & _trunc_cube(c, corner).translate(c2)
    elif cnt == 2:
        if not e[0]:
            shape = ytcyl(c[1] * 2, radius) & ztcyl(c[2] * 2, radius)
        elif not e[1]:
            shape = xtcyl(c[0] * 2, radius) & ztcyl(c[2] * 2, radius)
        else:
            shape = xtcyl(c[0] * 2, radius) & ytcyl(c[1] * 2, radius)
        shape = shape & _trunc_cube(c, corner).translate(c2)
    else:
        shape = (
            tsphere(radius)
            if trimcorners
            else (xtcyl(c[0] * 2, radius) & ytcyl(c[1] * 2, radius) & ztcyl(c[2] * 2, radius))
        )
        shape = shape & _trunc_cube(c, corner).translate(c2)
    return shape.translate(base_t)


def _edge_mask_negative(
    sz: Sequence[float],
    edge_set: Sequence[Sequence[float]],
    ard: float,
    is_chamfer: bool,
    trimcorners: bool,
    fn: int | None,
    fa: float | None,
    fs: float | None,
) -> PyOpenSCAD:
    assert edge_set == EDGES_ALL or edge_set[2] == [0, 0, 0, 0], (
        "Cannot use negative rounding/chamfer with Z aligned edges."
    )
    pieces = []
    cutters = []
    for axis in (0, 1):
        for i in range(4):
            if edge_set[axis][i] > 0:
                vec = EDGE_OFFSETS[axis][i]
                adj = [ard - 0.01, ard - 0.01, -ard]
                t = [vec[k] / 2 * (sz[k] + adj[k]) for k in range(3)]
                box = _rotate_to_axis(_ocube([ard, ard, sz[axis]], center=True), axis)
                pieces.append(box.translate(t))
                adj2 = [2 * ard, 2 * ard, -2 * ard]
                t2 = [vec[k] / 2 * (sz[k] + adj2[k]) for k in range(3)]
                if is_chamfer:
                    cutter = _ocube(
                        [ard * math.sqrt(2), ard * math.sqrt(2), sz[axis] + 2.1 * ard],
                        center=True,
                    ).rotate(45, [0, 0, 1])
                else:
                    fn = int(_quantup(_frag_count(ard, fn, fa, fs), 4))
                    cutter = _ocylinder(height=sz[axis] + 2.1 * ard, radius=ard, center=True, fn=fn)
                cutters.append(_rotate_to_axis(cutter, axis).translate(t2))
    if trimcorners:
        for za in (-1, 1):
            for ya in (-1, 1):
                for xa in (-1, 1):
                    ce = _corner_edges(edge_set, [xa, ya, za])
                    if ce[0] + ce[1] > 1:
                        adj3 = [ard - 0.01, ard - 0.01, -ard]
                        t3 = [[xa, ya, za][k] / 2 * (sz[k] + adj3[k]) for k in range(3)]
                        pieces.append(_ocube([ard + 0.01, ard + 0.01, ard], center=True).translate(t3))
    edge_union = pieces[0]
    for p in pieces[1:]:
        edge_union = edge_union | p
    for c in cutters:
        edge_union = edge_union - c
    return _ocube(sz, center=True) | edge_union


# ---------------------------------------------------------------------------
# Section: native-only 2-D -> 3-D constructor (no BOSL2 equivalent)
# ---------------------------------------------------------------------------


def roof(shape: object, method: str = "straight") -> Bosl2Solid:
    """Raise a hip roof over a 2-D *shape* via its straight skeleton (native ``roof()``).

    Like :func:`~pybosl2.skin.linear_sweep`, this turns a 2-D outline into a 3-D solid, but the top is
    a peaked roof (each edge slopes inward at 45 degrees to the skeleton) rather than a flat
    extrusion. *shape* is any 2-D object -- a native ``square``/``circle``/``polygon``, a
    :meth:`Path2D.polygon`, or a :class:`Bosl2Solid` wrapping one. *method* selects the skeleton
    algorithm. PythonSCAD-only (no BOSL2 counterpart); covered by the STL render tests.

    Examples:
        .. pythonscad-example::

            roof(s2.square([20, 10]).shape).show()
    """
    return Bosl2Solid(Bosl2Solid._unwrap(shape).roof(method=method))


# ---------------------------------------------------------------------------
# Section: Cuboids, Prismoids and Pyramids
# ---------------------------------------------------------------------------


def cube(
    size: float | Sequence[float] = 1,
    center: bool | None = None,
    anchor: Anchor | Sequence[float] = Anchor.CENTER,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
) -> Bosl2Solid:
    """A cube, built with the builtin cube(), with BOSL2-style anchor/spin/orient support.

    Args:
        size:   size of the cube, a number or length-3 vector
        center: if given, overrides anchor (True -> CENTER, False -> FRONT+LEFT+BOTTOM)
        anchor: anchor point (default Anchor.CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)
        orient: direction to rotate the top towards, after spin (default Anchor.TOP)

    Examples:
        .. pythonscad-example::

            s3.cube(size=20).show()
    """
    sz = [float(size)] * 3 if isinstance(size, (int, float)) else [float(v) for v in size]
    use_anchor = _resolve_center_anchor(center, anchor, Anchor.BOTTOM_FRONT_LEFT)
    shape = _ocube(sz, center=True)
    offset = _anchor_offset_box3(sz, use_anchor)
    return _finish3(shape, offset, spin, orient, size=sz, anchor=use_anchor)


def cuboid(
    size: float | Sequence[float] = [1, 1, 1],
    p1: Point | None = None,
    p2: Point | None = None,
    chamfer: float | None = None,
    rounding: float | None = None,
    edges: Anchor | str | list[object] = "ALL",
    except_edges: list[Any] | None = None,
    trimcorners: bool = True,
    teardrop: bool | float = False,
    anchor: Anchor = Anchor.CENTER,
    spin: float = 0,
    orient: Anchor = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """A cube/cuboid with optional chamfering or rounding of edges and corners.

    Built directly from cube()/cylinder()/sphere()/hull()/minkowski(), mirroring BOSL2's own
    cuboid() algorithm (which is itself CSG composition of primitive shapes at each corner,
    not raw polyhedron mesh math).

    You cannot mix chamfering and rounding on the same call. Negative chamfers/roundings
    create external fillets, but only apply to edges around the top or bottom face.

    Note: `teardrop=` is not supported by this pure-Python port.

    Args:
        size:         size of the cuboid, a number or length-3 vector
        p1:           align the cuboid's corner at p1, if given (forces anchor=BOTTOM_FRONT_LEFT)
        p2:           if given with p1, defines the cuboid's opposing cornerpoint
        chamfer:      chamfer size, inset from sides (default: no chamfer)
        rounding:     edge rounding radius (default: no rounding)
        edges:        edges to mask (default ``"ALL"``)
        except_edges: edges to explicitly not mask (BOSL2's `except=` synonym; `except` is a Python keyword)
        trimcorners:  round/chamfer corners where three treated edges meet (default True)
        anchor:       anchor point (default Anchor.CENTER)
        spin:         Z-axis rotation in degrees (default 0)
        orient:       direction to rotate the top towards (default Anchor.TOP)
        fn/fa/fs:  arc smoothness overrides for rounded edges/corners

    Examples:
        .. pythonscad-example::

            shape = pybosl2.shapes3d.cuboid([40, 30, 20])
            shape.show()

        .. pythonscad-example::

            shape = pybosl2.shapes3d.cuboid([40, 30, 20], rounding=5)
            shape.show()
    """
    if teardrop:
        raise NotImplementedError("cuboid(): teardrop= is not supported by this pure-Python port.")
    sz = [float(size)] * 3 if isinstance(size, (int, float)) else [float(v) for v in size]
    if p1 is not None:
        if p2 is not None:
            mn = [min(p1[i], p2[i]) for i in range(3)]
            mx = [max(p1[i], p2[i]) for i in range(3)]
            shape = cuboid(
                [mx[i] - mn[i] for i in range(3)],
                chamfer=chamfer,
                rounding=rounding,
                edges=edges,
                except_edges=except_edges,
                trimcorners=trimcorners,
                anchor=Anchor.BOTTOM_FRONT_LEFT,
                fn=fn,
                fa=fa,
                fs=fs,
            )
            return shape.translate(mn)
        shape = cuboid(
            sz,
            chamfer=chamfer,
            rounding=rounding,
            edges=edges,
            except_edges=except_edges,
            trimcorners=trimcorners,
            anchor=Anchor.BOTTOM_FRONT_LEFT,
            fn=fn,
            fa=fa,
            fs=fs,
        )
        return shape.translate([float(p1[0]), float(p1[1]), float(p1[2])])

    edge_set = _edges(edges, except_edges or [])
    chamfer_v = chamfer if chamfer else 0
    rounding_v = rounding if rounding else 0
    assert not (chamfer_v and rounding_v), "Cannot specify nonzero value for both chamfer and rounding"

    corners8 = [[xa, ya, za] for za in (-1, 1) for ya in (-1, 1) for xa in (-1, 1)]

    if chamfer_v != 0:
        radius = chamfer_v
        if edge_set == EDGES_ALL and trimcorners:
            if radius < 0:
                shape = _edge_mask_negative(sz, edge_set, abs(radius), True, trimcorners, fn, fa, fs)
            else:
                isize = [max(0.001, v - 2 * radius) for v in sz]
                shape = _ohull(
                    _ocube([sz[0], isize[1], isize[2]], center=True),
                    _ocube([isize[0], sz[1], isize[2]], center=True),
                    _ocube([isize[0], isize[1], sz[2]], center=True),
                )
        elif radius < 0:
            shape = _edge_mask_negative(sz, edge_set, abs(radius), True, trimcorners, fn, fa, fs)
        else:
            shape = _ohull(
                *[_corner_shape(c, sz, edge_set, radius, True, trimcorners, fn, fa, fs) for c in corners8]
            ) & _ocube(sz, center=True)
    elif rounding_v != 0:
        radius = rounding_v
        if edge_set == EDGES_ALL and radius > 0:
            isize = [max(0.001, v - 2 * radius) for v in sz]
            fn = int(_quantup(_frag_count(radius, fn, fa, fs), 4))
            shape = _ominkowski(_ocube(isize, center=True), _osphere(radius=radius, fn=fn))
        elif radius < 0:
            shape = _edge_mask_negative(sz, edge_set, abs(radius), False, trimcorners, fn, fa, fs)
        else:
            shape = _ohull(
                *[_corner_shape(c, sz, edge_set, radius, False, trimcorners, fn, fa, fs) for c in corners8]
            ) & _ocube(sz, center=True)
    else:
        shape = _ocube(sz, center=True)

    offset = _anchor_offset_box3(sz, anchor)
    return _finish3(shape, offset, spin, orient, size=sz, anchor=anchor)


def prismoid(
    size1: Sequence[float],
    size2: Sequence[float],
    height: float | None = None,
    shift: Sequence[float] = [0, 0],
    rounding: float | Sequence[float] = 0,
    rounding1: float | Sequence[float] | None = None,
    rounding2: float | Sequence[float] | None = None,
    chamfer: float | Sequence[float] = 0,
    chamfer1: float | Sequence[float] | None = None,
    chamfer2: float | Sequence[float] | None = None,
    length: float | None = None,
    center: bool | None = None,
    anchor: Anchor | Sequence[float] = BOTTOM,
    spin: float = 0,
    orient: Anchor | Sequence[float] = UP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """A rectangular prismoid, built as the convex hull() of two (optionally rounded/chamfered) rects.

    Args:
        size1:     [width, length] of the bottom end
        size2:     [width, length] of the top end
        height/length:       height of the prism
        shift:     [X,Y] shift of the top center relative to the bottom center
        rounding:  vertical-edge roundover radius, or per-corner list [X+Y+,X-Y+,X-Y-,X+Y-] (default 0)
        rounding1: roundover radius for the bottom of the vertical-ish edges
        rounding2: roundover radius for the top of the vertical-ish edges
        chamfer:   vertical-edge chamfer size, or per-corner list (default 0)
        chamfer1:  chamfer size for the bottom of the vertical-ish edges
        chamfer2:  chamfer size for the top of the vertical-ish edges
        center:    if given, overrides anchor
        anchor:    anchor point (default BOTTOM)
        spin:      Z-axis rotation in degrees after anchor (default 0)
        orient:    direction to rotate the top towards, after spin (default UP)
        fn/fa/fs: arc smoothness overrides for rounded corners

    Examples:
        .. pythonscad-example::

            shape = pybosl2.shapes3d.prismoid([40, 40], [20, 25], height=30)
            shape.show()
    """
    from pybosl2.shapes2d import _rect_path

    s1 = [float(size1)] * 2 if isinstance(size1, (int, float)) else [float(v) for v in size1]
    s2 = [float(size2)] * 2 if isinstance(size2, (int, float)) else [float(v) for v in size2]
    height = height if height is not None else (length if length is not None else 1)
    radius1 = rounding1 if rounding1 is not None else rounding
    radius2 = rounding2 if rounding2 is not None else rounding
    c1 = chamfer1 if chamfer1 is not None else chamfer
    c2 = chamfer2 if chamfer2 is not None else chamfer
    use_anchor = _resolve_center_anchor(center, anchor, BOTTOM)

    path1 = _rect_path(s1, rounding=radius1, chamfer=c1, fn=fn, fa=fa, fs=fs)
    path2 = _rect_path(s2, rounding=radius2, chamfer=c2, fn=fn, fa=fa, fs=fs)
    bottom_pts = [[p[0], p[1], -height / 2] for p in path1]
    top_pts = [[p[0] + shift[0], p[1] + shift[1], height / 2] for p in path2]
    bottom = _opolyhedron(bottom_pts, [list(range(len(bottom_pts)))])
    top = _opolyhedron(top_pts, [list(range(len(top_pts)))])
    shape = _ohull(bottom, top)
    offset = _anchor_offset_hull3(bottom_pts + top_pts, use_anchor)
    return _finish3(shape, offset, spin, orient, size=None, anchor=use_anchor)


def octahedron(
    size: float = 1,
    anchor: Anchor | Sequence[float] = Anchor.CENTER,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
) -> Bosl2Solid:
    """An octahedron with axis-aligned points, built directly with polyhedron().

    Args:
        size:   width of the octahedron, tip to tip
        anchor: anchor point (default CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)
        orient: direction to rotate the top towards, after spin (default UP)

    Examples:
        .. pythonscad-example::

            s3.octahedron(size=20).show()
    """
    s = size / 2
    pts = [[s, 0, 0], [-s, 0, 0], [0, s, 0], [0, -s, 0], [0, 0, s], [0, 0, -s]]
    faces = [
        [2, 0, 4],
        [1, 2, 4],
        [3, 1, 4],
        [0, 3, 4],
        [0, 2, 5],
        [2, 1, 5],
        [1, 3, 5],
        [3, 0, 5],
    ]
    shape = _opolyhedron(pts, faces)
    offset = _anchor_offset_hull3(pts, anchor)
    return _finish3(shape, offset, spin, orient, size=None, anchor=anchor)


def wedge(
    size: Sequence[float] = [1, 1, 1],
    center: bool | None = None,
    anchor: Anchor | Sequence[float] = FRONT.vector + LEFT.vector + BOTTOM.vector,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
) -> Bosl2Solid:
    """A 3-D triangular wedge with the hypotenuse in the X+Z+ quadrant, built directly with polyhedron().

    Args:
        size:   [width, thickness, height]
        center: if given, overrides anchor (True -> CENTER, False -> FRONT+LEFT+BOTTOM)
        anchor: anchor point (default FRONT+LEFT+BOTTOM)
        spin:   Z-axis rotation in degrees after anchor (default 0)
        orient: direction to rotate the top towards, after spin (default UP)

    Examples:
        .. pythonscad-example::

            s3.wedge([30, 20, 15]).show()
    """
    sz = [float(size)] * 3 if isinstance(size, (int, float)) else [float(v) for v in size]
    use_anchor = _resolve_center_anchor(center, anchor, [-1, -1, -1])
    pts: list[list[float]] = [[1, 1, -1], [1, -1, -1], [1, -1, 1], [-1, 1, -1], [-1, -1, -1], [-1, -1, 1]]
    pts = [[p[0] * sz[0] / 2, p[1] * sz[1] / 2, p[2] * sz[2] / 2] for p in pts]
    faces = [
        [0, 1, 2],
        [3, 5, 4],
        [0, 3, 1],
        [1, 3, 4],
        [1, 4, 2],
        [2, 4, 5],
        [2, 5, 3],
        [0, 2, 3],
    ]
    shape = _opolyhedron(pts, faces)
    offset = _anchor_offset_hull3(pts, use_anchor)
    return _finish3(shape, offset, spin, orient, size=None, anchor=use_anchor)


def _rect_tube_rounding(
    factor: float,
    inner_radius: Sequence[float | None],
    radius: Sequence[float | None],
    alternative: Sequence[float | None],
    size: Sequence[float],
    isize: Sequence[float],
) -> list[float]:
    wall = min(size[0] - isize[0], size[1] - isize[1]) / 2 * factor
    return [
        iri
        if iri is not None
        else (max(0.0, (ri if ri is not None else 0.0) - wall) if alternative[i] is None else 0.0)
        for i, (iri, ri) in enumerate(zip(inner_radius, radius, strict=False))
    ]


def rect_tube(
    height: float | None = None,
    size: float | Sequence[float] | None = None,
    isize: float | Sequence[float] | None = None,
    center: bool | None = None,
    shift: Sequence[float] = [0, 0],
    wall: float | None = None,
    size1: float | Sequence[float] | None = None,
    size2: float | Sequence[float] | None = None,
    isize1: float | Sequence[float] | None = None,
    isize2: float | Sequence[float] | None = None,
    rounding: float | Sequence[float] = 0,
    rounding1: float | Sequence[float] | None = None,
    rounding2: float | Sequence[float] | None = None,
    inner_rounding: float | Sequence[float] = 0,
    inner_rounding1: float | Sequence[float] | None = None,
    inner_rounding2: float | Sequence[float] | None = None,
    chamfer: float | Sequence[float] = 0,
    chamfer1: float | Sequence[float] | None = None,
    chamfer2: float | Sequence[float] | None = None,
    inner_chamfer: float | Sequence[float] = 0,
    inner_chamfer1: float | Sequence[float] | None = None,
    inner_chamfer2: float | Sequence[float] | None = None,
    anchor: Anchor | Sequence[float] = BOTTOM.vector,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
    length: float | None = None,
) -> Bosl2Solid:
    """BOSL2 rect_tube() -- a rectangular tube (a rectangle with a rectangular hole through it).

    Args:
        height/length:        height/length of the tube (default 1)
        size:       outer [X,Y] size of the tube
        isize:      inner [X,Y] size of the tube
        center:     if given, overrides anchor
        shift:      [X,Y] shift of the top center relative to the bottom center
        wall:       wall thickness
        size1/size2:   outer [X,Y] size at the bottom/top
        isize1/isize2: inner [X,Y] size at the bottom/top
        rounding/rounding1/rounding2:    outer edge rounding radius (overall/bottom/top)
        inner_rounding/inner_rounding1/inner_rounding2: inner edge rounding radius (default: same as rounding)
        chamfer/chamfer1/chamfer2:       outer edge chamfer size (overall/bottom/top)
        inner_chamfer/inner_chamfer1/inner_chamfer2:    inner edge chamfer size (default: same as chamfer)
        anchor:     anchor point (default BOTTOM)
        spin:       Z-axis rotation in degrees after anchor (default 0)
        orient:     direction to rotate the top towards, after spin (default UP)

    Examples:
        .. pythonscad-example::

            s3.rect_tube(size=30, wall=3, height=20).show()
    """
    from pybosl2.shapes2d import _rect_path

    def as2(v: float | Sequence[float] | None) -> list[float] | None:
        if v is None:
            return None
        return [float(v), float(v)] if isinstance(v, (int, float)) else [float(x) for x in v]

    def force4(v: float | Sequence[float] | None) -> list[float | None]:
        if v is None:
            return [None, None, None, None]
        return [float(v)] * 4 if isinstance(v, (int, float)) else [float(x) for x in v]

    def force4f(v: float | Sequence[float]) -> list[float]:
        return [float(v)] * 4 if isinstance(v, (int, float)) else [float(x) for x in v]

    def override_or_none(
        specific: float | Sequence[float] | None, general: float | Sequence[float]
    ) -> float | Sequence[float] | None:
        # `general` (inner_rounding/inner_chamfer) defaults to 0 rather than None in this port's
        # signature, so a bare 0 is treated as "not specified" (inherit from rounding/chamfer);
        # pass inner_rounding1=/inner_rounding2=/inner_chamfer1=/inner_chamfer2= (which do default to None) to force
        # an explicit zero.
        if specific is not None:
            return specific
        return general if general else None

    height = height if height is not None else (length if length is not None else 1)
    s1 = as2(size1) if size1 is not None else as2(size)
    s2 = as2(size2) if size2 is not None else as2(size)
    i1 = as2(isize1) if isize1 is not None else as2(isize)
    i2 = as2(isize2) if isize2 is not None else as2(isize)
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
    assert size1_v is not None and size2_v is not None, "rect_tube(): bad size/size1/size2 argument."
    assert isize1_v is not None and isize2_v is not None, "rect_tube(): bad isize/isize1/isize2 argument."
    assert isize1_v[0] < size1_v[0] and isize1_v[1] < size1_v[1], (
        "rect_tube(): inner size is larger than outer size at the bottom."
    )
    assert isize2_v[0] < size2_v[0] and isize2_v[1] < size2_v[1], (
        "rect_tube(): inner size is larger than outer size at the top."
    )

    rounding1_v = force4f(rounding1 if rounding1 is not None else rounding)
    rounding2_v = force4f(rounding2 if rounding2 is not None else rounding)
    chamfer1_v = force4f(chamfer1 if chamfer1 is not None else chamfer)
    chamfer2_v = force4f(chamfer2 if chamfer2 is not None else chamfer)
    irounding1_t = force4(override_or_none(inner_rounding1, inner_rounding))
    irounding2_t = force4(override_or_none(inner_rounding2, inner_rounding))
    ichamfer1_t = force4(override_or_none(inner_chamfer1, inner_chamfer))
    ichamfer2_t = force4(override_or_none(inner_chamfer2, inner_chamfer))

    irounding1_v = _rect_tube_rounding(1.0, irounding1_t, rounding1_v, ichamfer1_t, size1_v, isize1_v)
    irounding2_v = _rect_tube_rounding(1.0, irounding2_t, rounding2_v, ichamfer2_t, size2_v, isize2_v)
    ichamfer1_v = _rect_tube_rounding(1 / math.sqrt(2), ichamfer1_t, chamfer1_v, irounding1_t, size1_v, isize1_v)
    ichamfer2_v = _rect_tube_rounding(1 / math.sqrt(2), ichamfer2_t, chamfer2_v, irounding2_t, size2_v, isize2_v)

    use_anchor = _resolve_center_anchor(center, anchor, BOTTOM)

    outer = prismoid(
        size1_v,
        size2_v,
        height=height,
        shift=shift,
        rounding1=rounding1_v,
        rounding2=rounding2_v,
        chamfer1=chamfer1_v,
        chamfer2=chamfer2_v,
        anchor=CENTER,
    )
    inner = prismoid(
        isize1_v,
        isize2_v,
        height=height + 0.02,
        shift=shift,
        rounding1=irounding1_v,
        rounding2=irounding2_v,
        chamfer1=ichamfer1_v,
        chamfer2=ichamfer2_v,
        anchor=CENTER,
    )
    shape = outer.shape - inner.shape

    path1 = _rect_path(size1_v, rounding=rounding1_v, chamfer=chamfer1_v)
    path2 = _rect_path(size2_v, rounding=rounding2_v, chamfer=chamfer2_v)
    bottom_pts = [[p[0], p[1], -height / 2] for p in path1]
    top_pts = [[p[0] + shift[0], p[1] + shift[1], height / 2] for p in path2]
    offset = _anchor_offset_hull3(bottom_pts + top_pts, use_anchor)

    straight = size1_v == size2_v and shift[0] == 0 and shift[1] == 0
    out_size = [size1_v[0], size1_v[1], height] if straight else None
    return _finish3(shape, offset, spin, orient, size=out_size, anchor=use_anchor)


def regular_prism(
    sides: int,
    height: float | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    inner_radius: float | None = None,
    inner_diameter: float | None = None,
    side: float | None = None,
    length: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    circumscribe: bool = False,
    realign: bool = False,
    shift: Sequence[float] = [0, 0],
    center: bool | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """A regular sides-sided prism (or frustum) -- the sides-gon analogue of cyl(): a regular polygon
    cross-section extruded along Z, with optional per-end chamfer or rounding. Built the same
    way cyl() is (native cylinder with fn=sides for the plain case; a revolved half-profile with
    fn=sides for chamfered/rounded ends), so it shares cyl()'s exact rim geometry.

    Sizing gives the CIRCUMradius (vertex distance) unless noted -- exactly one of ``radius``/``diameter``
    (radius/diameter to the vertices), ``inner_radius``/``inner_diameter`` (inradius/apothem to the face centers,
    converted via ``/cos(180/sides)``), or ``side`` (edge length, converted via ``/(2 sin(180/sides))``).
    ``radius1``/``radius2`` (or the corresponding taper) set the bottom/top radius independently for a frustum.

    Note: BOSL2 regular_prism()'s texture=/teardrop= options are not ported (they need the VNF
    texturing machinery this pure-Python port doesn't implement).

    Args:
        sides:        number of sides (integer >= 3)
        height/length/height/length: prism height (default 1)
        radius/diameter/inner_radius/inner_diameter/side:    overall size (see above)
        radius1/radius2:    bottom/top circumradius for a tapered prism
        chamfer/chamfer1/chamfer2:    end chamfer size (overall/bottom/top)
        rounding/rounding1/rounding2: end rounding radius (overall/bottom/top)
        circumscribe:   circumscribe the nominal radius (scale by 1/cos(180/sides)) (default False)
        realign:  rotate by half a facet so a face, not a vertex, faces +X (default False)
        shift:    [X,Y] shift of the top center relative to the bottom center
        center:   if given, overrides anchor (True -> CENTER, False -> BOTTOM)
        anchor:   anchor point (default CENTER)
        spin:     Z-axis rotation in degrees after anchor (default 0)
        orient:   direction to rotate the top towards, after spin (default UP)
        fn/fa/fs: arc smoothness overrides

    Examples:
        .. pythonscad-example::

            shape = pybosl2.shapes3d.regular_prism(6, height=20, radius=15)
            shape.show()

        .. pythonscad-example::

            shape = pybosl2.shapes3d.regular_prism(5, height=20, inner_radius=12, rounding=2)
            shape.show()
    """
    assert isinstance(sides, int) and sides > 2, f"regular_prism(): sides must be an integer >= 3, got {sides}"
    cos_half = math.cos(math.pi / sides)

    def circumradius(spec_r: float | None) -> float:
        if spec_r is not None:
            return spec_r
        if side is not None:
            return side / (2 * math.sin(math.pi / sides))
        if inner_diameter is not None:
            return (inner_diameter / 2) / cos_half
        if inner_radius is not None:
            return inner_radius / cos_half
        if diameter is not None:
            return diameter / 2
        if radius is not None:
            return radius
        return 1.0

    rad1 = circumradius(radius1)
    rad2 = circumradius(radius2)
    if circumscribe:
        sc = 1 / cos_half
        rad1 *= sc
        rad2 *= sc
    prism_len = next((v for v in (length, height, height, length) if v is not None), 1.0)

    r1v = rounding1 if rounding1 is not None else (rounding if rounding is not None else 0)
    r2v = rounding2 if rounding2 is not None else (rounding if rounding is not None else 0)
    c1v = chamfer1 if chamfer1 is not None else (chamfer if chamfer is not None else 0)
    c2v = chamfer2 if chamfer2 is not None else (chamfer if chamfer is not None else 0)
    assert not ((r1v or r2v) and (c1v or c2v)), "Cannot specify nonzero value for both chamfer and rounding"

    use_anchor = anchor
    if use_anchor is None:
        use_anchor = CENTER if center is None or center else BOTTOM

    if not (r1v or r2v or c1v or c2v):
        shape = _ocylinder(height=prism_len, radius1=rad1, radius2=rad2, center=True, fn=sides)
    else:
        profile = _cyl_profile(rad1, rad2, prism_len, r1v, r2v, c1v, c2v, fn=fn, fa=fa, fs=fs)
        from pybosl2.shapes2d import _opolygon

        shape = _orotate_extrude(_opolygon(profile), fn=sides)

    # OpenSCAD's cylinder(fn=n) puts a vertex on +X; realign rotates half a facet so a face
    # centre faces +X instead (BOSL2's realign convention).
    if realign:
        shape = shape.rotate(180 / sides, [0, 0, 1])
    if shift[0] or shift[1]:
        shear = [
            [1, 0, shift[0] / prism_len, 0],
            [0, 1, shift[1] / prism_len, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ]
        shape = shape.multmatrix(shear)
    offset = _anchor_offset_cyl(rad1, rad2, prism_len, use_anchor)
    return _finish3(shape, offset, spin, orient, size=None, anchor=use_anchor)

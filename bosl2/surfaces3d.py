# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/surfaces3d.py
#    Advanced 3-D surface / plot / annotation builders split out of shapes3d.py to keep that module
#    focused on the core primitives: heightfield()/cylindrical_heightfield() (grid & wrapped-tube
#    surfaces), plot3d()/plot_revolution() (function plots), interior_fillet()/fillet() (concave
#    edge fillets), textured_tile() (VNF/heightfield surface texturing) and ruler() (a measurement
#    annotation). These are leaf builders -- shapes3d's core does not depend on them -- so they are
#    re-exported from shapes3d for backward-compatible `from bosl2.shapes3d import heightfield`.
#
# FileSummary: Heightfields, function plots, fillets, textured tiles and the ruler annotation.
# FileGroup: BOSL2

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Callable

import numpy as np

from bosl2._native import native
from bosl2.constants import BACK, CENTER, FRONT, INCH, LEFT, TOP, UP
from bosl2.paths import Path
from bosl2.shapes2d import _frag_count, _pick_radius
from bosl2.shapes2d import text as _text2d
from bosl2.shapes3d import (
    Bosl2Solid,
    _anchor_offset_box3,
    _anchor_offset_cyl,
    _anchor_offset_hull3,
    _finish3,
    _interior_fillet_path,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from openscad import PyOpenSCAD

if TYPE_CHECKING:  # real stub-typed imports for the checker (identical to pre-lazy)
    from pythonscad import cube as _ocube
    from pythonscad import polyhedron as _opolyhedron
else:
    _ocube = native("cube")
    _opolyhedron = native("polyhedron")

__all__ = [
    "interior_fillet",
    "heightfield",
    "cylindrical_heightfield",
    "plot3d",
    "plot_revolution",
    "fillet",
    "textured_tile",
    "ruler",
]


def _heightfield_tri_area(pts: Sequence[Sequence[float]], tri: Sequence[int]) -> float:
    ax, ay, az = pts[tri[0]]
    bx, by, bz = pts[tri[1]]
    cx, cy, cz = pts[tri[2]]
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    return math.hypot(nx, ny, nz)


def _heightfield_tris(pts: list[list[float]], i1: int, i2: int, i3: int, i4: int, style: str) -> list[list[int]]:
    """Split a quad (corners i1,i2,i3,i4 at grid positions (r,c),(r+1,c),(r+1,c+1),(r,c+1)) into
    2 or 4 triangle faces, mirroring BOSL2 vnf_vertex_array()'s "default"/"alt"/"quincunx" quad
    styles. Winding direction is left unresolved here (both a plain "i1,i3,i2 & i1,i4,i3" split and
    its mirror are geometrically valid faces) -- see _heightfield_reorient(), which fixes winding
    for the whole mesh in one pass instead of requiring every call site to work it out by hand."""
    if style == "quincunx":
        i5 = len(pts)
        pts.append([(pts[i1][k] + pts[i2][k] + pts[i3][k] + pts[i4][k]) / 4 for k in range(3)])
        tris = [[i1, i5, i2], [i2, i5, i3], [i3, i5, i4], [i4, i5, i1]]
    elif style == "alt":
        tris = [[i1, i4, i2], [i2, i4, i3]]
    else:
        tris = [[i1, i3, i2], [i1, i4, i3]]
    return [t for t in tris if _heightfield_tri_area(pts, t) > 1e-9]


def _heightfield_dedupe(
    pts: Sequence[Sequence[float]], faces: Sequence[Sequence[int]], ndigits: int = 6
) -> tuple[list[list[float]], list[list[int]]]:
    """Merge points landing on the same position (sub-micron at typical mm board-game scale).

    BOSL2's own cylindrical_heightfield() algorithm legitimately produces this: the "back of the
    tube" fill points snap to whichever end of the cylinder (z=+l/2 or z=-l/2) is nearest, so
    several consecutive rows can share literally identical positions there but at different grid
    indices. Left un-merged, that turns into a naked seam once degenerate triangles get dropped.
    """
    remap: list[int] = []
    seen: dict[tuple[float, float, float], int] = {}
    merged: list[list[float]] = []
    for p in pts:
        key = (round(p[0], ndigits), round(p[1], ndigits), round(p[2], ndigits))
        i = seen.get(key)
        if i is None:
            i = len(merged)
            seen[key] = i
            merged.append([float(v) for v in p])
        remap.append(i)
    out_faces: list[list[int]] = []
    for f in faces:
        nf = [remap[i] for i in f]
        if len(set(nf)) >= 3:
            out_faces.append(nf)
    return merged, out_faces


def _heightfield_reorient(pts: Sequence[Sequence[float]], faces: list[list[int]]) -> list[list[int]]:
    """Flood-fill the face list to one globally-consistent winding (every shared edge used in
    opposite directions by its two faces), then flip everything if needed so the winding matches
    OpenSCAD's polyhedron() convention (clockwise as seen from outside).

    This lets every face-building loop above stay simple, unflipped index math instead of having
    to derive the correct BOSL2-style reverse=true/false flag by hand for every patch (top/bottom/
    walls, or the wrapped lateral tube surface) -- which is easy to get subtly wrong per-patch.

    All-triangle manifolds take the vectorized numpy fast path in :func:`_heightfield_reorient_tris`;
    the general flood-fill below is the fallback for polygon or non-manifold face lists.
    """
    if faces and all(len(f) == 3 for f in faces):
        fast = _heightfield_reorient_tris(pts, faces)
        if fast is not None:
            return fast

    edge_faces: dict[frozenset[int], list[int]] = {}
    for fi, f in enumerate(faces):
        sides = len(f)
        for i in range(sides):
            edge_faces.setdefault(frozenset((f[i], f[(i + 1) % sides])), []).append(fi)

    visited = [False] * len(faces)
    for start in range(len(faces)):
        if visited[start]:
            continue
        visited[start] = True
        stack = [start]
        while stack:
            fi = stack.pop()
            f = faces[fi]
            sides = len(f)
            for i in range(sides):
                a, b = f[i], f[(i + 1) % sides]
                for fj in edge_faces[frozenset((a, b))]:
                    if fj == fi or visited[fj]:
                        continue
                    nf = faces[fj]
                    m = len(nf)
                    if any(nf[j] == a and nf[(j + 1) % m] == b for j in range(m)):
                        faces[fj] = list(reversed(nf))
                    visited[fj] = True
                    stack.append(fj)

    volume = 0.0
    for f in faces:
        v0 = pts[f[0]]
        for i in range(1, len(f) - 1):
            v1, v2 = pts[f[i]], pts[f[i + 1]]
            volume += (
                v0[0] * (v1[1] * v2[2] - v1[2] * v2[1])
                - v0[1] * (v1[0] * v2[2] - v1[2] * v2[0])
                + v0[2] * (v1[0] * v2[1] - v1[1] * v2[0])
            )
    return [list(reversed(f)) for f in faces] if volume > 0 else faces


def _heightfield_reorient_tris(
    pts: Sequence[Sequence[float]], faces: Sequence[Sequence[int]]
) -> list[list[int]] | None:
    """Vectorized reorientation for an all-triangle mesh: pair shared edges with numpy, resolve one
    globally-consistent winding with a path-compressed union-find over relative face parity, then a
    signed-volume flip to OpenSCAD's outward convention. Equivalent winding to the flood-fill in
    :func:`_heightfield_reorient` (verified to render identically in PythonSCAD) and faster. Returns
    None for a non-manifold mesh (an edge shared by 3+ faces), deferring to the flood-fill.
    """
    P = np.asarray(pts, dtype=float)
    F = len(faces)
    tris = np.asarray(faces, dtype=np.int64)
    src = tris[:, [0, 1, 2]].ravel()
    dst = tris[:, [1, 2, 0]].ravel()
    key = np.minimum(src, dst).astype(np.int64) * len(P) + np.maximum(src, dst)
    order = np.argsort(key, kind="stable")
    key = key[order]
    fid = np.repeat(np.arange(F), 3)[order]
    fwd = (src < dst)[order]
    _, counts = np.unique(key, return_counts=True)
    if counts.size and counts.max() > 2:
        return None  # non-manifold -> defer to the robust flood-fill

    dup = np.empty(len(key), dtype=bool)
    dup[0] = False
    dup[1:] = key[1:] == key[:-1]
    pairs = np.nonzero(dup)[0]  # each pairs faces (fid[i-1], fid[i]) sharing that edge
    fa_ = fid[pairs - 1].tolist()
    fb_ = fid[pairs].tolist()
    # two triangles sharing an edge agree iff they traverse it in OPPOSITE order; equal fwd -> flip
    need_flip = (fwd[pairs - 1] == fwd[pairs]).tolist()

    parent = list(range(F))
    parity = bytearray(F)  # parity[x] = orientation of x relative to parent[x]

    def find(x: int) -> int:
        path = []
        while parent[x] != x:
            path.append(x)
            x = parent[x]
        root = x
        acc = 0
        for node in reversed(path):
            acc ^= parity[node]
            parity[node] = acc
            parent[node] = root
        return root

    for a, b, nf in zip(fa_, fb_, need_flip, strict=False):
        ra, rb = find(a), find(b)
        if ra != rb:
            pa = parity[a] if a != ra else 0
            pb = parity[b] if b != rb else 0
            parent[ra] = rb
            parity[ra] = pa ^ pb ^ (1 if nf else 0)
    for i in range(F):
        find(i)

    flip = np.frombuffer(bytes(parity), dtype=np.uint8).astype(bool)
    out = tris.copy()
    out[flip] = out[flip][:, ::-1]
    v0, v1, v2 = P[out[:, 0]], P[out[:, 1]], P[out[:, 2]]
    if float(np.einsum("ij,ij->", v0, np.cross(v1, v2))) > 0:
        out = out[:, ::-1]
    return out.tolist()


def _heightfield_polyhedron(
    pts: Sequence[Sequence[float]], faces: Sequence[Sequence[int]]
) -> tuple[PyOpenSCAD, list[list[float]]]:
    pts, faces = _heightfield_dedupe(pts, faces)
    faces = _heightfield_reorient(pts, faces)
    return _opolyhedron(pts, faces), pts


def _heightfield_range(rng: Sequence[float]) -> list[float]:
    """Expand this port's [start, step, stop] stand-in for an OpenSCAD [start:step:stop] range
    literal into a plain list of values, inclusive of stop."""
    start, step, stop = rng
    sides = int(round((stop - start) / step))
    return [start + i * step for i in range(sides + 1)]


def _cylindrical_point(radius: float, theta_deg: float, z: float) -> list[float]:
    th = math.radians(theta_deg)
    return [radius * math.cos(th), radius * math.sin(th), z]


def interior_fillet(
    length: float = 1.0,
    radius: float | None = None,
    angle: float = 90,
    overlap: float = 0.01,
    diameter: float | None = None,
    anchor: Sequence[float] = FRONT + LEFT,
    spin: float = 0,
    orient: Sequence[float] = UP,
) -> Bosl2Solid:
    """BOSL2 interior_fillet() -- a shape to fillet an interior corner between two faces.

    Args:
        length:       length of the edge to fillet (default 1.0)
        radius:       radius of the fillet
        angle:     angle between the faces to fillet in degrees (default 90)
        overlap: overlap size for unioning with the faces (default 0.01)
        diameter:       diameter of the fillet
        anchor:  anchor point (default FRONT+LEFT)
        spin:    Z-axis rotation in degrees after anchor (default 0)
        orient:  direction to rotate the top towards, after spin (default UP)
    """
    from .shapes2d import _opolygon

    rad = _pick_radius(radius=radius, diameter=diameter, dflt=1)
    sides = _frag_count(rad)
    path = _interior_fillet_path(rad, angle, overlap, sides)
    shape = _opolygon(path).linear_extrude(height=length, center=True)
    pts3d = [[p[0], p[1], z] for z in (-length / 2, length / 2) for p in path]
    offset = _anchor_offset_hull3(pts3d, anchor)
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=None, anchor=anchor)


def heightfield(
    data: "Callable[[float, float], float | None] | Sequence[Sequence[float]]",
    size: Sequence[float] = [100, 100],
    bottom: float = -20,
    maxz: float = 99,
    xrange: Sequence[float] = [-1, 0.04, 1],
    yrange: Sequence[float] = [-1, 0.04, 1],
    style: str = "default",
    convexity: int = 10,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    orient: Sequence[float] = UP,
) -> Bosl2Solid:
    """BOSL2 heightfield() -- a 3-D surface from a 2-D array of heights or a function literal.

    Args:
        data:      2-D rectangular array of heights, or a function literal taking (x, y)
        size:      [X,Y] size of the surface (default [100,100])
        bottom:    Z coordinate for the bottom of the object (default -20)
        maxz:      maximum height to model, taller values are truncated (default 99)
        xrange:    [start, step, stop] range of X values for a function-literal surface
        yrange:    [start, step, stop] range of Y values for a function-literal surface
        style:     quad subdivision style: "default", "alt", "quincunx" (default "default")
        convexity: max number of times a line can cross the surface wall (default 10)
        anchor:    anchor point (default CENTER)
        spin:      Z-axis rotation in degrees (default 0)
        orient:    direction to rotate the top towards (default UP)
    """
    _ = convexity
    sz = [size, size] if isinstance(size, (int, float)) else list(size)
    style_key = style if style in ("alt", "quincunx") else "default"

    if callable(data):
        xvals = _heightfield_range(xrange)
        yvals = _heightfield_range(yrange)
        xcnt, ycnt = len(xvals), len(yvals)
        minx, maxx = min(xvals), max(xvals)
        miny, maxy = min(yvals), max(yvals)

        def xy_at(xi: int, yi: int) -> tuple[float, float]:
            fx = (xvals[xi] - minx) / (maxx - minx) if maxx > minx else 0.0
            fy = (yvals[yi] - miny) / (maxy - miny) if maxy > miny else 0.0
            return sz[0] * (fx - 0.5), sz[1] * (fy - 0.5)

        def height_at(xi: int, yi: int) -> float:
            z = data(xvals[xi], yvals[yi])
            return min(maxz, max(bottom + 0.1, 0.0 if z is None else z))
    else:
        ycnt, xcnt = len(data), len(data[0])

        def xy_at(xi: int, yi: int) -> tuple[float, float]:
            fx = xi / (xcnt - 1) if xcnt > 1 else 0.0
            fy = yi / (ycnt - 1) if ycnt > 1 else 0.0
            return sz[0] * (fx - 0.5), sz[1] * (fy - 0.5)

        def height_at(xi: int, yi: int) -> float:
            return min(max(data[yi][xi], bottom + 0.1), maxz)

    top = [[0.0, 0.0, 0.0] for _ in range(xcnt * ycnt)]
    for yi in range(ycnt):
        for xi in range(xcnt):
            x, y = xy_at(xi, yi)
            top[yi * xcnt + xi] = [x, y, height_at(xi, yi)]

    pts = list(top)
    bo = len(pts)
    pts += [[p[0], p[1], bottom] for p in top]

    def idx(row: int, col: int) -> int:
        return row * xcnt + col

    faces: list[list[int]] = []
    for r in range(ycnt - 1):
        for c in range(xcnt - 1):
            faces += _heightfield_tris(
                pts,
                idx(r, c),
                idx(r + 1, c),
                idx(r + 1, c + 1),
                idx(r, c + 1),
                style_key,
            )
            faces += _heightfield_tris(
                pts,
                bo + idx(r, c),
                bo + idx(r + 1, c),
                bo + idx(r + 1, c + 1),
                bo + idx(r, c + 1),
                style_key,
            )
    for c in range(xcnt - 1):
        faces += _heightfield_tris(pts, idx(0, c), bo + idx(0, c), bo + idx(0, c + 1), idx(0, c + 1), "default")
        radius = ycnt - 1
        faces += _heightfield_tris(
            pts,
            idx(radius, c),
            bo + idx(radius, c),
            bo + idx(radius, c + 1),
            idx(radius, c + 1),
            "default",
        )
    for r in range(ycnt - 1):
        faces += _heightfield_tris(pts, idx(r, 0), bo + idx(r, 0), bo + idx(r + 1, 0), idx(r + 1, 0), "default")
        c = xcnt - 1
        faces += _heightfield_tris(pts, idx(r, c), bo + idx(r, c), bo + idx(r + 1, c), idx(r + 1, c), "default")

    shape, pts = _heightfield_polyhedron(pts, faces)
    offset = _anchor_offset_hull3(pts, anchor)
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=None, anchor=anchor)


def cylindrical_heightfield(
    data: "Callable[[float, float], float | None] | Sequence[Sequence[float]]",
    length: float | None = None,
    radius: float | None = None,
    base: float = 1,
    transpose: bool = False,
    aspect: float = 1,
    style: str = "min_edge",
    convexity: int = 10,
    xrange: Sequence[float] = [-1, 0.01, 1],
    yrange: Sequence[float] = [-1, 0.01, 1],
    maxh: float = 99,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    height: float | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    orient: Sequence[float] = UP,
) -> Bosl2Solid:
    """BOSL2 cylindrical_heightfield() -- wraps a heightfield surface around a cylinder.

    Args:
        data:      2-D rectangular array of heights, or a function literal taking (x, y)
        length:         length of the cylinder to wrap around
        radius:         radius of the cylinder to wrap around
        base:      radius for the bottom of the object (default 1)
        transpose: swap the radial and length axes of the data (default False)
        aspect:    aspect ratio of the generated heightfield at the cylinder surface (default 1)
        style:     quad subdivision style: "default", "alt", "quincunx" (default "min_edge")
        convexity: max number of times a line can cross the surface wall (default 10)
        xrange:    [start, step, stop] range of X values for a function-literal surface
        yrange:    [start, step, stop] range of Y values for a function-literal surface
        maxh:      maximum height above the radius to model (default 99)
        radius1/radius2:     radius of the bottom/top of the cylinder to wrap around
        diameter/diameter1/diameter2:   diameter of the cylinder to wrap around / bottom / top
        height/height:  alternate names for length (length of the cylinder)
        anchor:    anchor point (default CENTER)
        spin:      Z-axis rotation in degrees (default 0)
        orient:    direction to rotate the top towards (default UP)
    """
    _ = convexity
    l_val = length if length is not None else (height if height is not None else height)
    assert l_val is not None and l_val > 0, "Must supply one of length= or height= as a finite positive number."
    r1v = _pick_radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter)
    r2v = _pick_radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter)
    assert r1v is not None and r1v > 0, (
        "Must supply one of radius=, radius1=, diameter=, or diameter1= as a finite positive number."
    )
    assert r2v is not None and r2v > 0, (
        "Must supply one of radius=, radius2=, diameter=, or diameter2= as a finite positive number."
    )
    assert base > 0, "base= must be a finite positive number."

    style_key = style if style in ("alt", "quincunx") else "default"

    if callable(data):
        xvals = _heightfield_range(xrange)
        yvals = _heightfield_range(yrange)
    else:
        xvals = list(range(len(data[0])))
        yvals = list(range(len(data)))
    xlen, ylen = len(xvals), len(yvals)

    stepy = l_val / (ylen - 1)
    stepx = stepy * aspect
    maxr = max(r1v, r2v)
    circ = 2 * math.pi * maxr
    astep = 360 / circ * stepx
    arc = astep * (xlen - 1)
    assert stepx * xlen <= circ, (
        f"heightfield ({xlen} x {ylen}) needs a radius of at least {maxr * stepx * xlen / circ}."
    )
    bsteps = max(1, round(_frag_count(maxr - base) * arc / 360))
    bstep = arc / bsteps

    rows: list[list[list[float]]] = []
    for yi in range(ylen):
        z = yi * stepy - l_val / 2
        t = yi / (ylen - 1) if ylen > 1 else 0.0
        rr = r1v + (r2v - r1v) * t
        row = [_cylindrical_point(rr - base, -arc / 2, z)]
        for xi in range(xlen):
            a = xi * astep
            if callable(data):
                raw = data(yvals[yi], xvals[xi]) if transpose else data(xvals[xi], yvals[yi])
            else:
                raw = data[xi][yi] if transpose else data[yi][xi]
            rad = min(maxh, max(0.01 - base, 0.0 if raw is None else raw))
            row.append(_cylindrical_point(rr + rad, a - arc / 2, z))
        row.append(_cylindrical_point(rr - base, arc / 2, z))
        for b in range(1, bsteps):
            a = arc / 2 - b * bstep
            redge = r2v if z > 0 else r1v
            row.append(_cylindrical_point(redge - base, a, l_val / 2 if z > 0 else -l_val / 2))
        rows.append(row)

    cols = len(rows[0])
    pts = [p for row in rows for p in row]

    def idx(row: int, col: int) -> int:
        return row * cols + (col % cols)

    faces: list[list[int]] = []
    for radius in range(ylen - 1):
        for c in range(cols):
            faces += _heightfield_tris(
                pts,
                idx(radius, c),
                idx(radius + 1, c),
                idx(radius + 1, c + 1),
                idx(radius, c + 1),
                style_key,
            )
    faces.append(list(range(cols)))
    faces.append(list(range((ylen - 1) * cols, ylen * cols)))

    shape, pts = _heightfield_polyhedron(pts, faces)
    offset = _anchor_offset_cyl(r1v, r2v, l_val, anchor)
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=None, anchor=anchor)


def plot3d(f, x, y, zclip=None, zspan=None, base: float = 1, style: str = "default") -> Bosl2Solid:
    """A surface plot of ``z = f(x, y)`` over a grid of *x*, *y* values (BOSL2 plot3d()).

    Args:
        f:     a callable ``f(x, y) -> z``
        x, y:  strictly increasing lists of sample coordinates
        zclip: [zmin, zmax] to clamp the surface (default no clip)
        zspan: [zmin, zmax] to rescale the surface height into (default no rescale)
        base:  thickness of solid base below the surface; 0 gives just the (open) surface (default 1)
        style: vnf_vertex_array quad-subdivision style

    Examples:
        A rippled surface plotted as a solid slab:

        .. pythonscad-example::

            s3.plot3d(lambda x, y: 6 * math.cos(math.hypot(x, y) / 6),
                      list(range(-30, 31, 3)), list(range(-30, 31, 3))).show()
    """
    from bosl2.vnf import VNF

    xs, ys = list(x), list(y)
    zlo, zhi = zclip if zclip is not None else [-math.inf, math.inf]
    data = [[[float(xi), float(yi), min(max(float(f(xi, yi)), zlo), zhi)] for yi in ys] for xi in xs]
    assert len(data) > 1 and len(data[0]) > 1, "plot3d(): x and y must each give at least 2 points."
    if zspan is not None:
        allz = [p[2] for row in data for p in row]
        minv, maxv = min(allz), max(allz)
        scale = (zspan[1] - zspan[0]) / (maxv - minv)
        data = [[[p[0], p[1], scale * (p[2] - minv) + zspan[0]] for p in row] for row in data]
    if base == 0:
        vnf = VNF.vertex_array(data, style=style)
    else:
        allz = [p[2] for row in data for p in row]
        bottom = (zspan[0] - base) if zspan is not None else (min(allz) - base)
        skirted = [[[p[0], p[1], bottom] for p in data[0]]] + data + [[[p[0], p[1], bottom] for p in data[-1]]]
        tdata = [[skirted[i][j] for i in range(len(skirted))] for j in range(len(skirted[0]))]
        vnf = VNF.vertex_array(tdata, col_wrap=True, caps=True, style=style, reverse=True)
        if vnf.volume() < 0:  # ensure outward winding for a valid manifold solid
            vnf = vnf.reverse()
    return Bosl2Solid(vnf.polyhedron())


def plot_revolution(
    f,
    angle: float,
    z=None,
    radius: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    path=None,
    rclip=None,
    rspan=None,
    horiz: bool = False,
    style: str = "min_edge",
) -> Bosl2Solid:
    """A surface of revolution whose radius is modulated by ``radius = f(angle, z)`` (BOSL2 plot_revolution()).

    The profile is either a straight taper (*z* plus *radius1*/*radius2*) or an explicit 2-D *path* of
    ``[radius, z]`` points; ``f(theta, z)`` displaces each profile point along its normal (or radially,
    with *horiz*). A full 360-degree *angle* range revolves seamlessly; a partial range is capped
    to the axis. The BOSL2 ``arclength`` form is not ported.

    Args:
        f:      a callable ``f(theta_degrees, z) -> radial displacement``
        angle:  a strictly increasing list/range of revolution angles in degrees
        z:      strictly increasing profile heights (with *radius1*/*radius2*)
        radius1/radius2/radius/diameter1/diameter2/diameter: the profile's bottom/top radius (straight taper form)
        path:   an explicit ``[[radius, z], ...]`` profile (instead of z + radii)
        rclip:  [rmin, rmax] to clamp the modulated radius
        rspan:  [rmin, rmax] to rescale the displacement into
        horiz:  displace radially (normal [1, 0]) instead of along the profile normal
        style:  vnf_vertex_array quad-subdivision style

    Examples:
        A vase whose radius ripples with height and angle:

        .. pythonscad-example::

            s3.plot_revolution(lambda a, z: 3 * math.sin(math.radians(4 * a)) * (z / 30),
                               angle=list(range(0, 361, 6)), z=list(range(0, 31, 2)),
                               radius1=12, radius2=8).show()
    """
    from bosl2.vnf import VNF

    r1v = (
        radius1
        if radius1 is not None
        else (
            radius
            if radius is not None
            else (diameter1 / 2 if diameter1 is not None else (diameter / 2 if diameter is not None else None))
        )
    )
    r2v = (
        radius2
        if radius2 is not None
        else (
            radius
            if radius is not None
            else (diameter2 / 2 if diameter2 is not None else (diameter / 2 if diameter is not None else None))
        )
    )
    theta = [float(a) for a in angle]  # type: ignore[arg-type]
    assert len(theta) > 1, "plot_revolution(): angle must have at least 2 values."
    if path is not None:
        prof = [[float(p[0]), float(p[1])] for p in path]
    else:
        zs = list(z)
        assert r1v is not None and r2v is not None and len(zs) > 1, (
            "plot_revolution(): give z with radius1 and radius2 (or a path)."
        )
        z0, z1 = zs[0], zs[-1]
        prof = [[r1v + (r2v - r1v) * (zz - z0) / (z1 - z0), zz] for zz in zs]
    normals = [[1.0, 0.0]] * len(prof) if horiz else np.asarray(Path._path_normals(prof), dtype=float).tolist()
    rlo, rhi = rclip if rclip is not None else [-math.inf, math.inf]
    rdata = [[min(max(float(f(t, pt[1])), rlo), rhi) for t in theta] for pt in prof]
    if rspan is not None:
        allv = [v for row in rdata for v in row]
        minv, maxv = min(allv), max(allv)
        sc = (rspan[1] - rspan[0]) / (maxv - minv)
        rdata = [[sc * (v - minv) + rspan[0] for v in row] for row in rdata]
    closed = (theta[-1] - theta[0]) == 360
    rmin = 0.01
    grid = []
    for i, pt in enumerate(prof):
        row = [] if closed else [[0.0, 0.0, pt[1]]]
        for j, t in enumerate(theta):
            rr = max(rmin, pt[0] + rdata[i][j] * normals[i][0])
            zz = pt[1] + rdata[i][j] * normals[i][1]
            row.append([rr * math.cos(math.radians(t)), rr * math.sin(math.radians(t)), zz])
        grid.append(row)
    vnf = VNF.vertex_array(grid, col_wrap=True, caps=True, style=style)
    if vnf.volume() < 0:
        vnf = vnf.reverse()
    return Bosl2Solid(vnf.polyhedron())


def fillet(
    length: float | None = None,
    radius: float | None = None,
    angle: float = 90,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    excess: float = 0.01,
    height: float | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """A concave edge-fillet mask of length *length* and radius *radius* (BOSL2 fillet()).

    A cutter you subtract to round a 90-degree edge (the concave complement of a rounded corner).
    Positioned manually like ``rounding_edge_mask`` -- origin at the sharp edge, +X/+Y into the
    material, centered along its own Z. Only 90-degree edges are ported (BOSL2's ``angle`` for other
    dihedral angles is not).

    Examples:
        .. pythonscad-example::

            block = s3.cuboid([30, 30, 20])
            mask = s3.fillet(length=20, radius=6).right(15).forward(15)
            (block - mask).show()
    """
    from . import masking

    assert angle == 90, "fillet(): only 90-degree edges (angle=90) are supported in this port."
    lv = (
        length
        if length is not None
        else (
            height if height is not None else (height if height is not None else (length if length is not None else 1))
        )
    )
    return Bosl2Solid(
        masking.rounding_edge_mask(
            length=lv,
            radius=radius,
            radius1=radius1,
            radius2=radius2,
            diameter=diameter,
            diameter1=diameter1,
            diameter2=diameter2,
            excess=excess,
            fn=fn,
            fa=fa,
            fs=fs,
        )
    )


def textured_tile(
    texture,
    size,
    tex_reps=None,
    tex_size=None,
    tex_depth: float = 1,
    tex_inset=False,
    style: str = "min_edge",
    sides=None,
    border=None,
    gap: float | None = None,
    roughness=None,
    fn: int | None = None,
) -> Bosl2Solid:
    """A rectangular tile carrying a repeated *texture* (BOSL2 textured_tile()).

    *texture* is either a **name** from the ported :func:`~bosl2.texture.texture` engine (e.g.
    ``"pyramids"``, ``"diamonds"``, ``"hills"``, ``"bricks"``, ``"pyramids_vnf"``), a raw **height-field**
    (a 2-D array of scalar heights in ``[0, 1]``), or a raw **VNF tile** ``(verts, faces)``. It is tiled
    *tex_reps* times (or ``tex_size`` chosen) across the *size* rectangle and raised by *tex_depth*.

    Args:
        texture:   a texture name, a 2-D height-field array, or a VNF tile ``(verts, faces)``
        size:      [x, y] size of the tile
        tex_reps:  integer or [nx, ny] tile repetitions (give this or *tex_size*)
        tex_size:  target tile size, from which the repetition count is computed
        tex_depth: how far the texture is raised (default 1); negative inverts it
        tex_inset: lower the texture into the surface by this fraction (True == full depth)
        style:     vnf_vertex_array quad-subdivision style (height-field textures only)
        sides/border/gap/roughness: parameters forwarded to :func:`~bosl2.texture.texture` for a named texture

    Examples:
        A named pyramid texture:

        .. pythonscad-example::

            s3.textured_tile("pyramids", size=[40, 40], tex_reps=[6, 6], tex_depth=3).show()

        A raw height-field:

        .. pythonscad-example::

            bump = [[0, 0, 0], [0, 1, 0], [0, 0, 0]]
            s3.textured_tile(bump, size=[40, 40], tex_reps=[4, 4], tex_depth=3).show()
    """
    from bosl2.texture import (
        TextureType,
        is_heightfield_texture,
        is_vnf_texture,
        is_watertight_topology,
        rasterize_vnf_texture,
        vnf_tile_to_solid,
    )
    from bosl2.texture import (
        texture as _texture,
    )
    from bosl2.vnf import VNF

    if isinstance(texture, (str, TextureType)):  # resolve a name through the texture engine
        texture = _texture(texture, sides=sides, border=border, gap=gap, roughness=roughness, fn=fn)

    sz = [float(size[0]), float(size[1])]
    inset = 1.0 if tex_inset is True else float(tex_inset or 0)

    def resolve_reps(cell):
        _ = cell
        if tex_reps is not None:
            return (
                [int(tex_reps[0]), int(tex_reps[1])] if hasattr(tex_reps, "__len__") else [int(tex_reps), int(tex_reps)]
            )
        assert tex_size is not None, "textured_tile(): give tex_reps or tex_size."
        ts = (
            [float(tex_size), float(tex_size)]
            if isinstance(tex_size, (int, float))
            else [float(tex_size[0]), float(tex_size[1])]
        )
        return [max(1, round(sz[0] / ts[0])), max(1, round(sz[1] / ts[1]))]

    if is_vnf_texture(texture) and not is_heightfield_texture(texture):
        verts, faces = texture
        reps = resolve_reps(1)
        v, f = vnf_tile_to_solid(verts, faces, sz, reps, tex_depth=tex_depth, inset=inset)
        if is_watertight_topology(v, f):  # sharp VNF tiling closed cleanly
            return Bosl2Solid(VNF(v, f).polyhedron(), size=[sz[0], sz[1], abs(tex_depth) + 0.1])
        texture = rasterize_vnf_texture(verts, faces)  # else fall back to a sampled height-field

    rows, cols = len(texture), len(texture[0])
    reps = resolve_reps(1)
    tiled = [
        [(float(texture[r][c]) - inset) * tex_depth for _rx in range(reps[0]) for c in range(cols)]
        for _ry in range(reps[1])
        for r in range(rows)
    ]
    flat = [v for row in tiled for v in row]
    bottom = min(flat) - 0.1
    return heightfield(tiled, size=sz, bottom=bottom, style=style)


def ruler(
    length: float = 100,
    width: float | None = None,
    thickness: float = 1,
    depth: int = 3,
    labels: bool = False,
    pipscale: float = 1 / 3,
    maxscale: float | None = None,
    colors: list[str] = None,
    alpha: float = 1.0,
    unit: float = 1,
    inch: bool = False,
    anchor: Sequence[float] = LEFT + BACK + TOP,
    spin: float = 0,
    orient: Sequence[float] = UP,
) -> Bosl2Solid:
    """BOSL2 ruler() -- a ruler for measuring objects in the viewport.

    Args:
        length:    length of the ruler (default 100)
        width:     width of the ruler (default: size of the largest unit division)
        thickness: thickness of the ruler (default 1)
        depth:     depth of the mark subdivisions (default 3)
        labels:    draw numeric labels for depths larger than 1 (default False)
        pipscale:  width scale of the pips relative to the next size up (default 1/3)
        maxscale:  log10 of the maximum width divisions to display (default: based on length)
        colors:    two colours to alternate for the ruler (default ["black","white"])
        alpha:     transparency value (default 1.0)
        unit:      unit to mark; scales the ruler marks to a different length (default 1)
        inch:      scale the ruler to inches, assuming a mm base dimension (default False)
        anchor:    anchor point (default LEFT+BACK+TOP)
        spin:      Z-axis rotation in degrees (default 0)
        orient:    direction to rotate the top towards (default UP)
    """
    from .shapes2d import _opolygon

    if colors is None:
        colors = ["black", "white"]
    assert depth <= 5, "Cannot render scales smaller than depth=5"
    assert len(colors) == 2, "'colors' must contain a list of exactly two colors."

    length_v = INCH * length if inch else length
    unit_v = INCH * unit if inch else unit
    maxscale_v = maxscale if maxscale is not None else math.floor(math.log10(length_v / unit_v - 1e-9))
    ms = int(round(maxscale_v))
    scales = [unit_v * 10**logsize for logsize in range(ms, ms - depth, -1)]
    widthfactor = (1 - pipscale) / (1 - pipscale**depth)
    width_v = width if width is not None else scales[0]
    widths = [width_v * widthfactor * pipscale ** (-logsize) for logsize in range(0, -depth, -1)]
    offsets = [0.0]
    for w in widths:
        offsets.append(offsets[-1] + w)

    pieces: list[PyOpenSCAD] = []
    for i in range(len(scales)):
        scale = scales[i]
        count = math.ceil(length_v / scale)
        log_arg = max(count * scale / unit_v, 1e-9)
        fontsize = 0.5 * min(widths[i], scale / max(1, math.ceil(math.log10(log_arg))))
        for idx in range(count):
            actlen = scale if (idx < count - 1 or abs(length_v % scale) < 1e-9) else length_v % scale
            x0 = idx * scale
            y0 = offsets[i]
            tick = _ocube([actlen, widths[i], thickness], center=True).translate(
                [x0 + actlen / 2, y0 + widths[i] / 2, 0]
            )
            pieces.append(tick.color(colors[idx % 2], alpha=alpha))

            if i == 0 and idx % 10 == 0 and idx != 0:
                mark = 0
            elif i == 0 and idx % 10 == 9 and idx != count - 1 or idx % 10 == 4:
                mark = 1
            elif idx % 10 == 5:
                mark = 0
            else:
                mark = -1
            flip = 1 - mark * 2
            if mark >= 0:
                marklength = min(widths[i] / 2, scale * 2)
                markwidth = marklength * 0.4
                tri = _opolygon([[0, 0], [flip * markwidth, -marklength], [0, -marklength * 0.9]])
                piece = (
                    tri.linear_extrude(height=thickness + scale / 100, convexity=2, center=True)
                    .translate([x0 + mark * scale, y0 + widths[i], 0])
                    .color(colors[1 - idx % 2], alpha=alpha)
                )
                pieces.append(piece)

            if labels and scale / unit_v + 1e-9 >= 1:
                lbl = _text2d(
                    str(idx * scale / unit_v),
                    size=fontsize,
                    halign="left",
                    valign="baseline",
                )
                piece = (
                    lbl.translate([0, scale * 0.02, 0])
                    .linear_extrude(height=thickness + scale / 100, convexity=2, center=True)
                    .translate([x0, y0, 0])
                    .color(colors[(idx + 1) % 2], alpha=alpha)
                )
                pieces.append(piece)

    base = pieces[0]
    for p in pieces[1:]:
        base = base | p
    shape = base.translate([-length_v / 2, -width_v / 2, 0])

    offset = _anchor_offset_box3([length_v, width_v, thickness], anchor)
    return Bosl2Solid(
        _finish3(shape, offset, spin, orient),
        size=[length_v, width_v, thickness],
        anchor=anchor,
    )

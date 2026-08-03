# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/vnf.py
#    Minimal pure-Python port of BOSL2's VNF ("Vertices and Faces") structure
#    from vnf.scad -- just the pieces the bezier surface functions
#    (pybosl2/beziers.py's BezierPatch) need to turn a grid of surface sample
#    points into a polyhedron: vnf_vertex_array() (grid -> VNF with the quad
#    subdivision styles), vnf_join() (merge VNFs), and rendering to PythonSCAD's
#    native polyhedron(). No osuse()/BOSL2 runtime dependency.
#
#    A VNF is [vertices, faces]: vertices a list of 3-D points, faces a list of
#    index lists (each a polygon into `vertices`). That maps straight onto
#    OpenSCAD's polyhedron(points=, faces=). The class carries the pair and, like
#    Path2D/Bezier, keeps every operation as a method.
#
# FileSummary: VNF (vertices+faces) surface structure and grid meshing (BOSL2 vnf.scad).
# DocCategory: Paths, regions & surfaces
# FileGroup: BOSL2

from __future__ import annotations

import math
from collections import defaultdict
from enum import Enum
from typing import TYPE_CHECKING, Any

import numpy as np

from pybosl2._mctable import CORNER_OFFSETS, EDGE_CORNERS, TRI_TABLE
from pybosl2.bounds import Bounds2D, Bounds3D

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from pybosl2.caps import CapSpec, CapType
    from pybosl2.isosurface import _MetaballSpec
    from pybosl2.path3d import Path3D

_EPS = 1e-9


def _plane_edge_t(
    pt0: list[float] | np.ndarray,
    pt1: list[float] | np.ndarray,
    a: float,
    b: float,
    c: float,
    d: float,
) -> float:
    """Return parametric t (0..1) where the edge pt0→pt1 crosses the plane A*x+B*y+C*z=D."""
    d0 = a * pt0[0] + b * pt0[1] + c * pt0[2] - d
    d1 = a * pt1[0] + b * pt1[1] + c * pt1[2] - d
    denom = d0 - d1
    if abs(denom) < _EPS:
        return 0.5
    return d0 / denom


def _interpolate(
    pt0: list[float] | np.ndarray,
    pt1: list[float] | np.ndarray,
    t: float,
) -> list[float]:
    """Linear interpolation between two 3-D points."""
    return [
        pt0[0] + t * (pt1[0] - pt0[0]),
        pt0[1] + t * (pt1[1] - pt0[1]),
        pt0[2] + t * (pt1[2] - pt0[2]),
    ]


def _triangle_area(
    a: list[float] | np.ndarray,
    b: list[float] | np.ndarray,
    c: list[float] | np.ndarray,
) -> float:
    """Signed triangle area from three 3-D points (half the cross-product magnitude)."""
    u = np.array(b, dtype=float) - np.array(a, dtype=float)
    v = np.array(c, dtype=float) - np.array(a, dtype=float)
    return float(np.linalg.norm(np.cross(u, v))) * 0.5


def _assemble_edge_paths(
    edges: list[tuple[int, int]],
) -> list[list[int]]:
    """Assemble disconnected directed edges into closed loops.

    Each edge ``(i, j)`` is treated as a directed connection i→j.
    Returns a list of vertex-index paths forming closed polygons.
    """
    if not edges:
        return []
    adj: dict[int, list[int]] = defaultdict(list)
    for a, b in edges:
        adj[a].append(b)
    visited: set[int] = set()
    paths: list[list[int]] = []

    for start in list(adj):
        if start in visited:
            continue
        path: list[int] = [start]
        visited.add(start)
        current = start
        while True:
            next_candidates = list(adj.get(current, []))
            if not next_candidates:
                break
            nxt = next_candidates[0]
            if nxt in visited:
                if nxt == path[0]:
                    paths.append(path)
                break
            path.append(nxt)
            visited.add(nxt)
            current = nxt

    # Handle any remaining edges not in a loop by assembling orphan paths
    remaining: set[tuple[int, int]] = set(edges)
    path_edges: set[tuple[int, int]] = set()
    for p in paths:
        for k1 in range(len(p)):
            k2 = (k1 + 1) % len(p)
            path_edges.add((p[k1], p[k2]))
    remaining -= path_edges

    return paths


# -- marching-squares lookup table -------------------------------------------
# In the two ambiguous cases with two opposite corners above and the other
# two below the isovalue, it is assumed the high values connect (ridge, not valley).
# This makes the contour compatible with marching cubes at pixel boundaries.
_MSQUARE_SEGMENT_TABLE: list[list[list[int]]] = [
    [[], []],
    [[0, 3], []],
    [[1, 0], []],
    [[1, 3], []],
    [[3, 2], []],
    [[0, 2], []],
    [[1, 2], [3, 0]],
    [[1, 2], []],
    [[2, 1], []],
    [[0, 1], [2, 3]],
    [[2, 0], []],
    [[2, 3], []],
    [[3, 1], []],
    [[0, 1], []],
    [[3, 0], []],
    [[], []],
]

_MSQUARE_VERTEX_INDEX_MAP: list[list[float]] = [
    [0.0, 0.0],
    [0.0, 1.0],
    [1.0, 0.0],
    [1.0, 1.0],
]


def _msquare_index(fvals: Sequence[float], isovalue: float) -> int:
    """Return 0..15 marching-square case index for 4 corner values."""
    idx = 0
    for i, v in enumerate(fvals):
        if float(v) >= isovalue:
            idx |= 1 << i
    return idx


def _assemble_partial_paths_2d(
    segments: list[list[list[float]]],
    closed: bool,
) -> list[list[list[float]]]:
    """Assemble 2-D line segments into connected paths (contour polygons).

    Each segment is ``[[x0,y0], [x1,y1]]``.  Returns a list of paths,
    each a list of ``[x, y]`` points.  If *closed* is True, only closed
    loops are kept; otherwise dangling paths are also returned open.
    """
    graph: dict[tuple[float, float], list[tuple[float, float]]] = defaultdict(list)
    for seg in segments:
        if len(seg) < 2:
            continue
        p0 = (float(seg[0][0]), float(seg[0][1]))
        p1 = (float(seg[1][0]), float(seg[1][1]))
        if abs(p0[0] - p1[0]) < _EPS and abs(p0[1] - p1[1]) < _EPS:
            continue
        graph[p0].append(p1)
        graph[p1].append(p0)

    visited: set[tuple[float, float]] = set()
    paths: list[list[list[float]]] = []

    for start in graph:
        if start in visited:
            continue
        path: list[tuple[float, float]] = [start]
        visited.add(start)
        curr = start
        prev: tuple[float, float] | None = None
        while True:
            neigh = graph.get(curr, [])
            nxt: tuple[float, float] | None = None
            if len(path) == 1:
                if neigh:
                    nxt = neigh[0]
            else:
                for n in neigh:
                    if n != prev:
                        nxt = n
                        break
            if nxt is None:
                break
            if nxt == start:
                paths.append([[float(x), float(y)] for x, y in path])
                break
            if nxt in visited:
                break
            path.append(nxt)
            visited.add(nxt)
            prev = curr
            curr = nxt

    if not closed:
        for start2 in graph:
            if start2 in visited:
                continue
            opath: list[tuple[float, float]] = [start2]
            visited.add(start2)
            cur = start2
            while True:
                neigh2 = [n for n in graph.get(cur, []) if n not in visited]
                if not neigh2:
                    break
                nx = neigh2[0]
                opath.append(nx)
                visited.add(nx)
                cur = nx
            if len(opath) >= 2:
                paths.append([[float(x), float(y)] for x, y in opath])

    return paths


def _marching_squares(
    field: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    isovalue: float,
) -> list[list[list[float]]]:
    """Run marching squares on a 2-D scalar field, returning contour paths."""
    nx, ny = field.shape
    segments: list[list[list[float]]] = []

    _edge_verts = [(0, 1), (1, 3), (2, 3), (0, 2)]
    _vert_coords = [(0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (1.0, 1.0)]

    for i in range(nx - 1):
        dx = xs[i + 1] - xs[i]
        for j in range(ny - 1):
            dy = ys[j + 1] - ys[j]
            fvals = [
                float(field[i, j]),
                float(field[i, j + 1]),
                float(field[i + 1, j]),
                float(field[i + 1, j + 1]),
            ]
            idx = _msquare_index(fvals, isovalue)
            for edge_group in _MSQUARE_SEGMENT_TABLE[idx]:
                if not edge_group:
                    continue
                seg: list[list[float]] = []
                for e in edge_group:
                    va, vb = _edge_verts[e]
                    fa, fb = fvals[va], fvals[vb]
                    denom = fb - fa
                    u = 0.5 if abs(denom) < _EPS else (isovalue - fa) / denom
                    ca = _vert_coords[va]
                    cb = _vert_coords[vb]
                    x = xs[i] + ca[0] * dx + u * (cb[0] - ca[0]) * dx
                    y = ys[j] + ca[1] * dy + u * (cb[1] - ca[1]) * dy
                    seg.append([float(x), float(y)])
                if len(seg) == 2:
                    segments.append(seg)

    paths = _assemble_partial_paths_2d(segments, closed=True)
    for p in paths:
        if p and p[0] == p[-1]:
            p.pop()
    return paths


def _to_grid(points: Any) -> np.ndarray:
    """Convert points (Path3D, list of Path3D, arrays) to a 3-D numpy grid."""
    from pybosl2.path3d import Path3D

    if isinstance(points, Path3D):
        return np.array([list(p) for p in points], dtype=float)
    if isinstance(points, list) and points and isinstance(points[0], Path3D):
        return np.array([[list(p) for p in row] for row in points], dtype=float)
    return np.asarray(points, dtype=float)


# -- marching-cubes helpers ----------------------------------------------------


def _resolve_grid(
    bb: Bounds3D,
    voxel_size: float | None,
    voxel_count: int | None,
    exact_bounds: bool,
) -> tuple[Bounds3D, float]:
    import math

    if voxel_size is None:
        w, h, d = bb.max_x - bb.min_x, bb.max_y - bb.min_y, bb.max_z - bb.min_z
        voxvol = (w * h * d) / (voxel_count if voxel_count else 22**3)
        voxel_size = voxvol ** (1 / 3)
    if exact_bounds:
        return bb, voxel_size
    vs = voxel_size
    nx = math.ceil((bb.max_x - bb.min_x) / vs)
    ny = math.ceil((bb.max_y - bb.min_y) / vs)
    nz = math.ceil((bb.max_z - bb.min_z) / vs)
    cx, cy, cz = (bb.min_x + bb.max_x) / 2, (bb.min_y + bb.max_y) / 2, (bb.min_z + bb.max_z) / 2
    hx, hy, hz = 0.5 * vs * nx, 0.5 * vs * ny, 0.5 * vs * nz
    return Bounds3D(
        min_x=cx - hx,
        min_y=cy - hy,
        min_z=cz - hz,
        max_x=cx + hx,
        max_y=cy + hy,
        max_z=cz + hz,
        width=2 * hx,
        length=2 * hy,
        height=2 * hz,
    ), voxel_size


def _grid_axes_2d(
    bb: Bounds2D,
    pixel_size: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Build uniform 2-D grid axes from a bounding box and pixel size."""
    xs = np.arange(bb.min_x, bb.max_x + pixel_size * 0.5, pixel_size)
    ys = np.arange(bb.min_y, bb.max_y + pixel_size * 0.5, pixel_size)
    return xs, ys


def _grid_axes(bb: Bounds3D, voxel_size: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    import math

    def axis(lo: float, hi: float, step: float) -> np.ndarray:
        sides: int = int(math.floor((hi - lo) / step + 0.5)) + 1
        return lo + step * np.arange(sides)

    return (
        axis(bb.min_x, bb.max_x, voxel_size),
        axis(bb.min_y, bb.max_y, voxel_size),
        axis(bb.min_z, bb.max_z, voxel_size),
    )


def _resolve_grid_2d(
    bb: Bounds2D,
    pixel_size: float | None,
    pixel_count: int | None,
    exact_bounds: bool,
) -> tuple[Bounds2D, float]:
    """Resolve 2-D grid parameters from a bounding box and optional pixel size/count."""
    if pixel_size is None:
        w, h = bb.max_x - bb.min_x, bb.max_y - bb.min_y
        pixvol = (w * h) / (pixel_count if pixel_count else 32**2)
        pixel_size = math.sqrt(pixvol)
    if exact_bounds:
        return bb, pixel_size
    vs = pixel_size
    nx = math.ceil((bb.max_x - bb.min_x) / vs)
    ny = math.ceil((bb.max_y - bb.min_y) / vs)
    cx = (bb.min_x + bb.max_x) / 2
    cy = (bb.min_y + bb.max_y) / 2
    hx = 0.5 * vs * nx
    hy = 0.5 * vs * ny
    return Bounds2D(
        min_x=cx - hx,
        min_y=cy - hy,
        max_x=cx + hx,
        max_y=cy + hy,
        width=2 * hx,
        length=2 * hy,
    ), vs


def _sample_field_2d(
    f: np.ndarray | Callable[[np.ndarray], np.ndarray],
    xs: np.ndarray,
    ys: np.ndarray,
) -> np.ndarray:
    """Sample a 2-D scalar field on a grid, returning a 2-D numpy array."""
    if isinstance(f, np.ndarray) or (isinstance(f, (list, tuple)) and not callable(f)):
        return np.asarray(f, dtype=float)
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    pts = np.stack([gx.ravel(), gy.ravel()], axis=1)
    with np.errstate(all="ignore"):
        vals = np.asarray(f(pts), dtype=float)
        if vals.shape == (len(pts),):
            return vals.reshape(gx.shape)
    raise TypeError("_sample_field_2d: callable f must accept (N,2) array and return (N,) array.")


def contour(
    f: np.ndarray | Callable[[np.ndarray], np.ndarray],
    isovalue: float,
    bounding_box: Bounds2D,
    pixel_size: float | None = None,
    pixel_count: int | None = None,
    closed: bool = True,
    exact_bounds: bool = False,
) -> list[list[list[float]]]:
    """Generate 2-D contour paths at a given isovalue from a scalar field.

    Uses marching squares on a uniform 2-D grid to trace the contour where
    ``f(x, y) == isovalue``.  Returns a list of closed (or open) polyline
    paths, each being a list of ``[x, y]`` points.

    Args:
        f: A 2-D numpy array or a callable ``(N,2)→(N,)`` or ``(x,y)→float``.
        isovalue: Scalar threshold.
        bounding_box: A :class:`~pybosl2.bounds.Bounds2D`.
        pixel_size: Isotropic pixel size.
        pixel_count: Approximate total pixel count (ignored if *pixel_size* given).
        closed: If True, return only closed contour loops.
        exact_bounds: If True, use *bounding_box* exactly.

    Returns:
        A list of contour paths, each a list of ``[x, y]`` points.

    Examples:
        .. pythonscad-example::

            import numpy as np
            from pybosl2 import contour, Bounds2D, stroke

            def field(p):
                r = np.hypot(p[:, 0], p[:, 1])
                return r
            paths = contour(field, 10, Bounds2D(-15, -15, 15, 15, 30, 30), pixel_size=0.5)
            stroke(paths, width=0.5).linear_extrude(height=2).show()
    """
    bb, ps = _resolve_grid_2d(bounding_box, pixel_size, pixel_count, exact_bounds)
    xs, ys = _grid_axes_2d(bb, ps)
    field_arr = _sample_field_2d(f, xs, ys)
    paths = _marching_squares(field_arr, xs, ys, float(isovalue))
    if not closed:
        return paths
    return [p for p in paths if len(p) >= 3 and p[0] != p[-1]]


def _sample_field(
    f: np.ndarray | Callable[[np.ndarray], np.ndarray],
    xs: np.ndarray,
    ys: np.ndarray,
    zs: np.ndarray,
) -> np.ndarray:
    if isinstance(f, np.ndarray) or (isinstance(f, (list, tuple)) and not callable(f)):
        return np.asarray(f, dtype=float)
    gx, gy, gz = np.meshgrid(xs, ys, zs, indexing="ij")
    pts = np.stack([gx.ravel(), gy.ravel(), gz.ravel()], axis=1)
    with np.errstate(all="ignore"):
        try:
            vals = np.asarray(f(pts), dtype=float)
            if vals.shape == (len(pts),):
                return vals.reshape(gx.shape)
        except (ValueError, TypeError, IndexError, np.exceptions.AxisError):
            pass
        vals = np.array([float(f(np.array([p[0], p[1], p[2]]))) for p in pts])
    return vals.reshape(gx.shape)


def _marching_cubes(
    field: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    zs: np.ndarray,
    iso: float,
    closed: bool,
) -> tuple[list[list[float]], list[list[int]]]:
    if closed:
        field = np.pad(field, 1, mode="constant", constant_values=-1e30)
        xs = np.concatenate([[xs[0] - (xs[1] - xs[0])], xs, [xs[-1] + (xs[-1] - xs[-2])]])
        ys = np.concatenate([[ys[0] - (ys[1] - ys[0])], ys, [ys[-1] + (ys[-1] - ys[-2])]])
        zs = np.concatenate([[zs[0] - (zs[1] - zs[0])], zs, [zs[-1] + (zs[-1] - zs[-2])]])
    nx, ny, nz = field.shape
    coords = (xs, ys, zs)
    verts: list[list[float]] = []
    faces: list[list[int]] = []
    cache: dict[tuple[int, int, int, int, int, int], int] = {}

    def corner_pos(ci: int, i: int, j: int, k: int) -> tuple[int, int, int]:
        di, dj, dk = CORNER_OFFSETS[ci]
        return (i + di, j + dj, k + dk)

    def edge_vertex(ca: tuple[int, int, int], cb: tuple[int, int, int]) -> int:
        ordered = (ca, cb) if ca < cb else (cb, ca)
        key = (ordered[0][0], ordered[0][1], ordered[0][2], ordered[1][0], ordered[1][1], ordered[1][2])
        idx = cache.get(key)
        if idx is not None:
            return idx
        ia, ja, ka = ca
        ib, jb, kb = cb
        va, vb = field[ia, ja, ka], field[ib, jb, kb]
        t: float = 0.5 if va == vb else (iso - va) / (vb - va)
        pa = np.array([coords[0][ia], coords[1][ja], coords[2][ka]])
        pb = np.array([coords[0][ib], coords[1][jb], coords[2][kb]])
        idx = len(verts)
        verts.append(list(pa + t * (pb - pa)))
        cache[key] = idx
        return idx

    for i in range(nx - 1):
        for j in range(ny - 1):
            for k in range(nz - 1):
                cvals = [
                    field[i + CORNER_OFFSETS[c][0], j + CORNER_OFFSETS[c][1], k + CORNER_OFFSETS[c][2]]
                    for c in range(8)
                ]
                cubeindex: int = 0
                for c in range(8):
                    if cvals[c] < iso:
                        cubeindex |= 1 << c
                tris = TRI_TABLE[cubeindex]
                if not tris:
                    continue
                for t in range(0, len(tris), 3):
                    face: list[int] = []
                    for e in tris[t : t + 3]:
                        c0, c1 = EDGE_CORNERS[e]
                        face.append(edge_vertex(corner_pos(c0, i, j, k), corner_pos(c1, i, j, k)))
                    if face[0] != face[1] and face[1] != face[2] and face[0] != face[2]:
                        faces.append(face)
    return verts, faces


def _count(sides: int, s: int = 0, reverse: bool = False) -> list[int]:
    radius = list(range(s, s + sides))
    return radius[::-1] if reverse else radius


def _lofttri(
    p1: np.ndarray,
    p2: np.ndarray,
    i1off: int,
    i2off: int,
    n1: int,
    n2: int,
    reverse: bool,
    trimax: float,
) -> list[list[int]]:
    """
    Triangulate between two rows (possibly unequal length) by shortest new edge (BOSL2
    _lofttri).
    """
    a1 = np.asarray(p1, dtype=float)
    a2 = np.asarray(p2, dtype=float)
    tris: list[Any] = []
    if n1 != n2:
        i1 = i2 = 0
        tc1 = tc2 = 0
        while True:
            t1 = i1 + 1 if i1 < n1 else n1
            t2 = i2 + 1 if i2 < n2 else n2
            d12 = 9e9 if t2 >= n2 else float(np.linalg.norm(a2[t2] - a1[i1]))
            d21 = 9e9 if t1 >= n1 else float(np.linalg.norm(a1[t1] - a2[i2]))
            userow = (2 if tc1 < trimax else 1) if d12 < d21 else (1 if tc2 < trimax else 2)
            newt = (t1 if t1 < n1 else i1) if userow == 1 else (t2 if t2 < n2 else i2)
            newofft = i2off + newt if userow == 2 else i1off + newt
            tc1n = tc1 + 1 if (d12 < d21 and tc1 < trimax) else 0
            tc2n = tc2 + 1 if (d21 < d12 and tc2 < trimax) else 0
            triangle = [i1off + i1, i2off + i2, newofft] if reverse else [i2off + i2, i1off + i1, newofft]
            if t1 >= n1 and t2 >= n2:
                break
            tris.append(triangle)
            if userow == 1:
                i1 = i1 if t1 >= n1 else t1
            else:
                i2 = i2 if t2 >= n2 else t2
            tc1, tc2 = tc1n, tc2n
    else:
        sides = n1
        i = 0
        while True:
            t = i + 1 if i < sides else sides
            if t >= sides:
                break
            d12 = float(np.linalg.norm(a2[t] - a1[i]))
            d21 = float(np.linalg.norm(a1[t] - a2[i]))
            third1 = i2off + t if d12 < d21 else i1off + t
            third2 = i1off + i if d12 < d21 else i2off + i
            if reverse:
                tris.append([i1off + i, i2off + i, third1])
                tris.append([i2off + t, i1off + t, third2])
            else:
                tris.append([i2off + i, i1off + i, third1])
                tris.append([i1off + t, i2off + t, third2])
            i = t
    return tris


class VnfStyle(str, Enum):
    """Triangulation style for :meth:`VNF.vertex_array`."""

    DEFAULT = "default"
    ALT = "alt"
    MIN_EDGE = "min_edge"
    MIN_AREA = "min_area"
    CONVEX = "convex"
    CONCAVE = "concave"
    QUINCUNX = "quincunx"
    QUAD = "quad"
    FLIP1 = "flip1"
    FLIP2 = "flip2"


class VNF:
    """A VNF surface: ``vertices`` (3-D points) plus ``faces`` (index polygons into vertices).

    Renders to PythonSCAD's native ``polyhedron`` via :meth:`polyhedron`. Build one from a
    rectangular grid of sample points with :meth:`vertex_array`, merge several with
    :meth:`union`, or mesh a scalar field with :meth:`from_field` and combine metaball
    primitives with :meth:`from_metaballs`.

    Args:
        vertices: list of [x, y, z] points
        faces:    list of index lists (each polygon into *vertices*)

    Examples:
        Meshing a bumpy grid of sample points into a surface and rendering it as a polyhedron:

        .. pythonscad-example::

            import math
            from pybosl2 import VNF

            grid = [[[x, y, 4 * math.sin(x / 6) * math.cos(y / 6)] for y in range(0, 60, 4)]
                    for x in range(0, 60, 4)]
            VNF.vertex_array(grid).polyhedron().show()
    """

    def __init__(self, vertices: list[list[float]] | None = None, faces: list[list[int]] | None = None) -> None:
        self.vertices = [[float(x) for x in v] for v in (vertices or [])]
        self.faces = [[int(i) for i in f] for f in (faces or [])]

    def __repr__(self) -> str:
        return f"VNF({len(self.vertices)} verts, {len(self.faces)} faces)"

    def __bool__(self) -> bool:
        return len(self.faces) > 0

    def bounds(self) -> Bounds3D:
        """Axis-aligned :class:`~pybosl2.bounds.Bounds3D` of the VNF."""
        arr = np.asarray(self.vertices, dtype=float)
        mn, mx = arr.min(axis=0), arr.max(axis=0)
        return Bounds3D(
            min_x=float(mn[0]),
            min_y=float(mn[1]),
            min_z=float(mn[2]),
            max_x=float(mx[0]),
            max_y=float(mx[1]),
            max_z=float(mx[2]),
            width=float(mx[0] - mn[0]),
            length=float(mx[1] - mn[1]),
            height=float(mx[2] - mn[2]),
        )

    def reverse(self) -> "VNF":
        """A copy with every face wound the other way (flips the surface normals)."""
        return VNF(self.vertices, [f[::-1] for f in self.faces])

    def volume(self) -> float:
        """Signed enclosed volume (BOSL2 vnf_volume()); negative when the faces wind inward.

        Used to detect and fix inverted meshes (a swept/skinned surface whose winding came out
        inside-out): ``vnf if vnf.volume() >= 0 else vnf.reverse()``."""
        if not self.faces:
            return 0.0
        v = np.asarray(self.vertices, dtype=float)
        total = 0.0
        for f in self.faces:  # fan-triangulate each (possibly n-gon) face
            a = v[f[0]]
            for k in range(1, len(f) - 1):
                total += float(np.dot(a, np.cross(v[f[k]], v[f[k + 1]])))
        return total / 6.0

    @staticmethod
    def union(vnfs: list["VNF"]) -> "VNF":
        """Merge a list of VNFs into one, offsetting each VNF's face indices (BOSL2 vnf_join())."""
        vnfs = list(vnfs)
        if len(vnfs) == 1:
            return vnfs[0]
        verts: list[Any] = []
        faces: list[Any] = []
        off = 0
        for v in vnfs:
            for f in v.faces:
                if len(f) >= 3:
                    faces.append([off + j for j in f])
            verts.extend(v.vertices)
            off += len(v.vertices)
        return VNF(verts, faces)

    @staticmethod
    def join(vnfs: list["VNF"]) -> "VNF":
        """Merge multiple VNFs into a single consolidated VNF with shared vertices.

        Each input VNF's vertices and faces are copied into a combined vertex array,
        with face indices offset appropriately.  No deduplication is performed.

        Args:
            vnfs: A list of :class:`VNF` objects to merge.

        Returns:
            A new :class:`VNF` containing all vertices and faces from the inputs.

        Examples:
        .. pythonscad-example::

            from pybosl2 import VNF

            a = VNF.vertex_array([[ [0,0,0],[1,0,0] ], [ [0,1,0],[1,1,0] ]])
            b = VNF.vertex_array([[ [0,0,1],[1,0,1] ], [ [0,1,1],[1,1,1] ]])
            VNF.join([a, b]).polyhedron().show()
        """
        return VNF.union(vnfs)

    @staticmethod
    def halfspace(
        vnf: "VNF",
        plane: Sequence[float],
        keep: bool = True,
        closed: bool = True,
    ) -> "VNF":
        """Clip a VNF to one side of a plane, optionally closing the cut face.

        A plane is defined as ``[A, B, C, D]`` for ``A*x + B*y + C*z = D``.
        If *keep* is True, the positive halfspace (``A*x + B*y + C*z > D``)
        is retained.  If *keep* is False, the negative halfspace is retained.

        Args:
            vnf: The input :class:`VNF`.
            plane: Plane equation ``[A, B, C, D]``.
            keep: If True, keep the positive halfspace.  Defaults to True.
            closed: If True, triangulate and close the cut face.  Defaults to True.

        Returns:
            A new :class:`VNF` containing only the requested halfspace.

        Raises:
            AssertionError: If *plane* does not have exactly 4 elements.

        Examples:
        .. pythonscad-example::

            import numpy as np
            from pybosl2 import VNF, Bounds3D

            cube_vnf = VNF.from_field(
                lambda p: 5 - np.max(np.abs(p), axis=1),
                0, Bounds3D(-10,-10,-10,10,10,10,20,20,20), voxel_size=1
            )
            cut = VNF.halfspace(cube_vnf, [0, 0, 1, 0], keep=True, closed=True)
            cut.polyhedron().show()
        """
        assert len(plane) == 4, "halfspace(): plane must be [A, B, C, D]."
        a, b, c, d = plane[0], plane[1], plane[2], plane[3]
        verts_in = np.asarray(vnf.vertices, dtype=float)
        if len(verts_in) == 0:
            return VNF([], [])

        n: np.ndarray = np.array([a, b, c], dtype=float)
        dists: np.ndarray = verts_in @ n - d

        if keep:
            inside_mask: np.ndarray = dists >= -_EPS
        else:
            inside_mask = dists <= _EPS

        inside_indices: list[int] = [i for i, m in enumerate(inside_mask) if m]
        vertex_map: dict[int, int] = {}
        for new_idx, old_idx in enumerate(inside_indices):
            vertex_map[old_idx] = new_idx

        new_verts: list[list[float]] = [list(verts_in[i]) for i in inside_indices]
        new_faces: list[list[int]] = []
        cut_edges: list[tuple[int, int]] = []

        for face in vnf.faces:
            face_inside: list[bool] = [inside_mask[i] for i in face]
            all_in = all(face_inside)
            none_in = not any(face_inside)

            if all_in:
                new_faces.append([vertex_map[i] for i in face])
            elif not none_in:
                fv = len(new_verts)
                clipped: list[int] = []
                nv = len(face)
                for idx in range(nv):
                    i0 = face[idx]
                    i1 = face[(idx + 1) % nv]
                    v0_in = inside_mask[i0]
                    v1_in = inside_mask[i1]

                    if v0_in and v1_in:
                        if not clipped or clipped[-1] != vertex_map[i0]:
                            clipped.append(vertex_map[i0])
                        clipped.append(vertex_map[i1])
                    elif v0_in and not v1_in:
                        if not clipped or clipped[-1] != vertex_map[i0]:
                            clipped.append(vertex_map[i0])
                        t = _plane_edge_t(vnf.vertices[i0], vnf.vertices[i1], a, b, c, d)
                        pt = _interpolate(vnf.vertices[i0], vnf.vertices[i1], t)
                        new_verts.append(pt)
                        clipped.append(fv)
                        cut_edges.append((fv, fv + 1))
                        fv += 1
                    elif not v0_in and v1_in:
                        t = _plane_edge_t(vnf.vertices[i0], vnf.vertices[i1], a, b, c, d)
                        pt = _interpolate(vnf.vertices[i0], vnf.vertices[i1], t)
                        new_verts.append(pt)
                        clipped.append(fv)
                        cut_edges.append((fv, fv + 1))
                        fv += 1
                        clipped.append(vertex_map[i1])

                if len(clipped) >= 3:
                    # fan-triangulate the clipped polygon
                    base = clipped[0]
                    for k in range(1, len(clipped) - 1):
                        tri = [base, clipped[k], clipped[k + 1]]
                        if _triangle_area(new_verts[tri[0]], new_verts[tri[1]], new_verts[tri[2]]) > _EPS:
                            new_faces.append(tri)

        if closed and cut_edges:
            edge_list = list(cut_edges)
            paths: list[list[int]] = _assemble_edge_paths(edge_list)
            for path in paths:
                if len(path) >= 3:
                    pbase = path[0]
                    for k in range(1, len(path) - 1):
                        tri = [pbase, path[k], path[k + 1]]
                        if _triangle_area(new_verts[tri[0]], new_verts[tri[1]], new_verts[tri[2]]) > _EPS:
                            new_faces.append(tri)

        return VNF(new_verts, new_faces)

    @staticmethod
    def slice(
        vnf: "VNF",
        plane: Sequence[float],
        closed: bool = True,
    ) -> tuple["VNF", "VNF"]:
        """Slice a VNF into two VNFs along a plane, closing both cut faces.

        Returns ``(vnf_above, vnf_below)`` where *vnf_above* is the positive
        halfspace and *vnf_below* is the negative halfspace.

        Args:
            vnf: The input :class:`VNF`.
            plane: Plane equation ``[A, B, C, D]`` for ``A*x + B*y + C*z = D``.
            closed: If True, close both cut faces.  Defaults to True.

        Returns:
            A ``(above, below)`` tuple of :class:`VNF` objects.

        Examples:
        .. pythonscad-example::

            import numpy as np
            from pybosl2 import VNF, Bounds3D

            cube_vnf = VNF.from_field(
                lambda p: 5 - np.max(np.abs(p), axis=1),
                0, Bounds3D(-10,-10,-10,10,10,10,20,20,20), voxel_size=1
            )
            above, below = VNF.slice(cube_vnf, [0, 0, 1, 0], closed=True)
            above.polyhedron().show()
        """
        above = VNF.halfspace(vnf, plane, keep=True, closed=closed)
        below = VNF.halfspace(vnf, plane, keep=False, closed=closed)
        return above, below

    @classmethod
    def vertex_array(
        cls,
        points: Path3D | list[Path3D] | list[list[list[float]]] | list[np.ndarray] | np.ndarray,
        cap1: "CapType | CapSpec | None" = None,
        cap2: "CapType | CapSpec | None" = None,
        col_wrap: bool = False,
        row_wrap: bool = False,
        reverse: bool = False,
        style: str | VnfStyle = "default",
    ) -> "VNF":
        """Build a VNF from a rectangular grid of 3-D points (BOSL2 vnf_vertex_array()).

        Each grid cell becomes triangles (or a quad) chosen by *style*: "default", "alt",
        "min_edge", "min_area", "convex", "concave", "quincunx", "quad", "flip1", "flip2".
        *col_wrap*/*row_wrap* close the grid into a tube/torus; *cap1*/*cap2* close the
        column-wrapped ends with :class:`~pybosl2.caps.CapType` styles;
        *reverse* flips face winding. Degenerate (zero-area) faces are dropped.
        """
        assert style in (
            "default",
            "alt",
            "min_edge",
            "min_area",
            "convex",
            "concave",
            "quincunx",
            "quad",
            "flip1",
            "flip2",
        ), f"unknown vertex_array style: {style!r}"
        from pybosl2.caps import CapType

        def _resolve_cap(cap: CapType | CapSpec | None) -> tuple[bool, bool]:
            if cap is None:
                return False, False
            cap_type = cap if isinstance(cap, CapType) else cap.cap_type
            if cap_type == CapType.NONE:
                return False, False
            if cap_type in (CapType.ROUND, CapType.SPHERE):
                return True, True
            return True, False

        grid = _to_grid(points)
        rows = len(grid)
        if rows == 0:
            return cls([], [])
        cols = len(grid[0])
        if rows <= 1 or cols <= 1:
            return cls([], [])

        make_cap1, cap1_round = _resolve_cap(cap1)
        make_cap2, cap2_round = _resolve_cap(cap2)
        if (make_cap1 or make_cap2) and not col_wrap:
            raise AssertionError("col_wrap must be true if caps are requested")
        if (make_cap1 or make_cap2) and row_wrap:
            raise AssertionError("cannot combine caps with row_wrap")

        pts = [p for row in grid for p in row]  # flattened, row-major
        parr = np.asarray(pts, dtype=float)
        pcnt = len(pts)
        colcnt = cols - (0 if col_wrap else 1)
        rowcnt = rows - (0 if row_wrap else 1)

        def idx(r: int, c: int) -> int:
            return (r % rows) * cols + (c % cols)

        verts = [list(p) for p in pts]
        if style == "quincunx":
            for r in range(rowcnt):
                for c in range(colcnt):
                    corners = parr[[idx(r, c), idx(r + 1, c), idx(r + 1, c + 1), idx(r, c + 1)]]
                    verts.append(corners.mean(axis=0).tolist())

        vertsarr = np.asarray(verts, dtype=float)
        faces: list[Any] = []
        if make_cap1:
            if cap1_round:
                row0 = parr[:cols]
                center: list[float] = list(row0.mean(axis=0))
                dome_radius: float = float(max(np.linalg.norm(p[:-1] - center[:-1]) for p in row0))
                apex: list[float] = center.copy()
                apex[2] -= dome_radius
                apex_idx = len(verts)
                verts.append(apex)
                for i in range(cols):
                    j = (i + 1) % cols
                    faces.append([apex_idx, idx(0, i), idx(0, j)] if reverse else [idx(0, i), apex_idx, idx(0, j)])
            else:
                faces.append(_count(cols, 0, reverse=not reverse))
        if make_cap2:
            if cap2_round:
                row_last = parr[(rows - 1) * cols : rows * cols]
                center = list(row_last.mean(axis=0))
                dome_radius = float(max(np.linalg.norm(p[:-1] - center[:-1]) for p in row_last))
                apex = center.copy()
                apex[2] += dome_radius
                apex_idx = len(verts)
                verts.append(apex)
                for i in range(cols):
                    j = (i + 1) % cols
                    faces.append(
                        [apex_idx, idx(rows - 1, i), idx(rows - 1, j)]
                        if not reverse
                        else [idx(rows - 1, i), apex_idx, idx(rows - 1, j)]
                    )
            else:
                faces.append(_count(cols, (rows - 1) * cols, reverse=reverse))

        for r in range(rowcnt):
            for c in range(colcnt):
                i1, i2, i3, i4 = (
                    idx(r, c),
                    idx(r + 1, c),
                    idx(r + 1, c + 1),
                    idx(r, c + 1),
                )
                p1, p2, p3, p4 = parr[i1], parr[i2], parr[i3], parr[i4]
                if style == "quincunx":
                    i5 = pcnt + r * colcnt + c
                    cell = [[i1, i5, i2], [i2, i5, i3], [i3, i5, i4], [i4, i5, i1]]
                elif style == "min_area":
                    area42 = np.linalg.norm(np.cross(p2 - p1, p4 - p1)) + np.linalg.norm(np.cross(p4 - p3, p2 - p3))
                    area13 = np.linalg.norm(np.cross(p1 - p4, p3 - p4)) + np.linalg.norm(np.cross(p3 - p2, p1 - p2))
                    cell = [[i1, i4, i2], [i2, i4, i3]] if area42 < area13 + _EPS else [[i1, i3, i2], [i1, i4, i3]]
                elif style == "min_edge":
                    d42 = np.linalg.norm(p4 - p2)
                    d13 = np.linalg.norm(p1 - p3)
                    cell = [[i1, i4, i2], [i2, i4, i3]] if d42 < d13 + _EPS else [[i1, i3, i2], [i1, i4, i3]]
                elif style in ("convex", "concave"):
                    sides = (-1 if reverse else 1) * np.cross(p2 - p1, p3 - p1)
                    if not np.any(sides):
                        cell = [[i1, i4, i3]]
                    else:
                        above = (sides @ p4 > sides @ p1) if style == "convex" else (sides @ p4 <= sides @ p1)
                        cell = [[i1, i4, i2], [i2, i4, i3]] if above else [[i1, i3, i2], [i1, i4, i3]]
                elif style == "quad":
                    cell = [[i1, i2, i3, i4]]
                elif (
                    style == "alt" or (style == "flip1" and (r + c) % 2 == 0) or (style == "flip2" and (r + c) % 2 == 1)
                ):
                    cell = [[i1, i4, i2], [i2, i4, i3]]
                else:  # default
                    cell = [[i1, i3, i2], [i1, i4, i3]]
                for face in cell:
                    a, b, cc = vertsarr[face[0]], vertsarr[face[1]], vertsarr[face[2]]
                    if np.linalg.norm(np.cross(b - a, cc - a)) > _EPS:  # drop degenerate faces
                        faces.append(face[::-1] if reverse else face)
        return cls(verts, faces)

    @classmethod
    def tri_array(
        cls,
        points: list[list[list[float]]],
        caps: bool = False,
        cap1: bool | None = None,
        cap2: bool | None = None,
        col_wrap: bool = False,
        row_wrap: bool = False,
        reverse: bool = False,
        limit_bunching: bool = True,
    ) -> "VNF":
        """Build a VNF from an array of rows whose lengths may differ (BOSL2 vnf_tri_array()).

        Triangulates between adjacent rows by repeatedly adding the shortest new edge, so it
        meshes triangular / irregular point arrays (what the degenerate bezier patches produce).
        """
        if (caps or cap1 or cap2) and row_wrap:
            raise AssertionError("cannot combine caps with row_wrap")
        plen = len(points)
        st = []
        for row in points:
            row = [list(p) for p in row]
            if col_wrap and not np.array_equal(row[0], row[-1]):
                row = row + [list(row[0])]
            st.append(row)
        addcol = (len(st[0]) - len(points[0])) if col_wrap else 0
        rowstarts = [len(r) for r in st]
        pcumlen = [0]
        for n in rowstarts:
            pcumlen.append(pcumlen[-1] + n)
        capfirst = cap1 if cap1 is not None else (caps if caps is not None else False)
        caplast = cap2 if cap2 is not None else (caps if caps is not None else False)

        faces: list[Any] = []
        if capfirst:
            rng = list(range(rowstarts[0] - addcol)) if reverse else list(range(rowstarts[0] - 1 - addcol, -1, -1))
            faces.append(rng)
        for i in range(plen - 1 + (1 if row_wrap else 0)):
            j = (i + 1) % plen
            trimax = max(1, abs(len(st[i]) - len(st[j]))) if limit_bunching else float("inf")
            faces.extend(
                _lofttri(
                    st[i],  # type: ignore[arg-type]
                    st[j],  # type: ignore[arg-type]
                    pcumlen[i],
                    pcumlen[j],
                    rowstarts[i],
                    rowstarts[j],
                    reverse,
                    trimax,
                )
            )
        if caplast:
            if reverse:
                rng = list(range(pcumlen[plen] - 1 - addcol, pcumlen[plen - 1] - 1, -1))
            else:
                rng = list(range(pcumlen[plen - 1], pcumlen[plen] - addcol))
            faces.append(rng)
        verts = [p for row in st for p in row]
        return cls(verts, faces)

    def polyhedron(self) -> Any:
        """Native geometry for this VNF via PythonSCAD's ``polyhedron(points=, faces=)``."""
        from pythonscad import polyhedron as _polyhedron

        pts = [[float(x) for x in v] for v in self.vertices]
        faces = [[int(i) for i in f] for f in self.faces]
        return _polyhedron(points=pts, faces=faces, convexity=10)

    def geometry(self) -> Any:
        """Alias of :meth:`polyhedron`, matching Path2D/Region's geometry() surface."""
        return self.polyhedron()

    @staticmethod
    def from_field(
        f: np.ndarray | Path3D | Callable[[np.ndarray], np.ndarray] | Callable[[Path3D], np.ndarray],
        isovalue: float,
        bounding_box: Bounds3D | float | Sequence[float] | Sequence[Sequence[float]] | None = None,
        voxel_size: float | None = None,
        voxel_count: int | None = None,
        closed: bool = True,
        reverse: bool = False,
        exact_bounds: bool = False,
    ) -> "VNF":
        """Mesh a scalar field into a :class:`VNF` via marching cubes.

        The solid is the region where ``f >= isovalue``.

        Args:
            f: A :class:`~pybosl2.path3d.Path3D`, a 3-D numpy array,
                a ``(N,3) → (N,)`` callable, or a
                ``(:class:`~pybosl2.path3d.Path3D`) → (N,)`` callable.
            isovalue: Scalar threshold.
            bounding_box: A :class:`~pybosl2.bounds.Bounds3D` or ``None``
                (auto-computed from array shape when *f* is an array).
            voxel_size: Isotropic voxel size.
            voxel_count: Approximate total voxel count (ignored if *voxel_size* given).
            closed: If True, pad field so mesh closes at bounding-box faces.
            reverse: If True, reverse inside/outside sense.
            exact_bounds: If True, use *bounding_box* exactly.

        Returns:
            A :class:`VNF`.

        Raises:
            NotImplementedError: If *isovalue* is a tuple range; only scalar thresholds are supported.

        Examples:
        .. pythonscad-example::

            import numpy as np
            from pybosl2 import VNF, Bounds3D

            def field(p):
                x, y, z = p[:, 0], p[:, 1], p[:, 2]
                return 20 / np.sqrt(x*x + y*y + z*z) + 3 * np.sin(x / 3)
            VNF.from_field(
                field, 1,
                Bounds3D(-30, -30, -30, 30, 30, 30, 60, 60, 60),
                voxel_size=2,
            ).polyhedron().show()
        """
        from pybosl2.path3d import Path3D

        bb: Bounds3D | None = None
        if bounding_box is not None:
            if isinstance(bounding_box, Bounds3D):
                bb = bounding_box
            elif isinstance(bounding_box, (int, float)):
                size = float(bounding_box)
                bb = Bounds3D(-size / 2, -size / 2, -size / 2, size / 2, size / 2, size / 2, size, size, size)
            elif isinstance(bounding_box, (list, tuple, np.ndarray)):
                val_list = list(bounding_box)
                if len(val_list) == 2 and isinstance(val_list[0], (list, tuple, np.ndarray)):
                    p1 = [float(x) for x in val_list[0]]
                    p2 = [float(x) for x in val_list[1]]
                    bb = Bounds3D(p1[0], p1[1], p1[2], p2[0], p2[1], p2[2], p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
                elif len(val_list) == 3:
                    val = [float(x) for x in val_list]
                    bb = Bounds3D(
                        -val[0] / 2,
                        -val[1] / 2,
                        -val[2] / 2,
                        val[0] / 2,
                        val[1] / 2,
                        val[2] / 2,
                        val[0],
                        val[1],
                        val[2],
                    )
                elif len(val_list) == 6:
                    val = [float(x) for x in val_list]
                    bb = Bounds3D(
                        val[0],
                        val[1],
                        val[2],
                        val[3],
                        val[4],
                        val[5],
                        val[3] - val[0],
                        val[4] - val[1],
                        val[5] - val[2],
                    )

        if isinstance(f, Path3D):
            f = np.asarray(f, dtype=float)
        elif callable(f) and not isinstance(f, np.ndarray):
            _original = f

            def _wrapped(pts: np.ndarray) -> np.ndarray:
                try:
                    return np.asarray(_original(pts), dtype=float)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    return np.asarray(_original(Path3D(pts)), dtype=float)  # type: ignore[arg-type]

            f = _wrapped

        if isinstance(isovalue, tuple):
            raise NotImplementedError(
                "from_field(): tuple (lo, hi) isovalue ranges are not yet implemented. "
                "Use a single float isovalue instead."
            )
        iso = float(isovalue)

        if isinstance(f, np.ndarray) or (isinstance(f, (list, tuple)) and not callable(f)):
            field = np.asarray(f, dtype=float)
            if bb is None:
                vs = voxel_size if voxel_size is not None else 1.0
                half = 0.5 * vs * (np.array(field.shape) - 1)
                bb = Bounds3D(
                    min_x=-half[0],
                    min_y=-half[1],
                    min_z=-half[2],
                    max_x=half[0],
                    max_y=half[1],
                    max_z=half[2],
                    width=2 * half[0],
                    length=2 * half[1],
                    height=2 * half[2],
                )
                vs_final = vs
            else:
                vs_final = (bb.max_x - bb.min_x) / (field.shape[0] - 1)
            xs, ys, zs = _grid_axes(bb, vs_final)
        else:
            assert bb is not None, "from_field(): a callable field needs a bounding_box."
            bb, vs_final = _resolve_grid(bb, voxel_size, voxel_count, exact_bounds)
            xs, ys, zs = _grid_axes(bb, vs_final)
            field = _sample_field(f, xs, ys, zs)

        verts, faces = _marching_cubes(field, xs, ys, zs, iso, closed)
        vnf = VNF(verts, faces)
        if len(faces):
            vol = vnf.volume()
            if (vol < 0) != reverse:
                vnf = vnf.reverse()
        return vnf

    @staticmethod
    def from_metaballs(
        spec: list[_MetaballSpec],
        bounding_box: Bounds3D | float | Sequence[float] | Sequence[Sequence[float]],
        voxel_size: float | None = None,
        voxel_count: int | None = None,
        isovalue: float = 1,
        closed: bool = True,
        exact_bounds: bool = False,
    ) -> "VNF":
        """Mesh transformed metaball primitives into a blobby :class:`VNF`.

        Args:
            spec: A list of :class:`_MetaballSpec` entries,
                each holding a transform (4×4 matrix or Point position) and a :class:`_Metaball`.
            bounding_box: A :class:`~pybosl2.bounds.Bounds3D`.
            voxel_size: Isotropic voxel size.
            voxel_count: Approximate total voxel count.
            isovalue: Field threshold.
            closed: Close mesh at bounding-box faces.
            exact_bounds: Use *bounding_box* exactly.

        Returns:
            A :class:`VNF`.

        Examples:
        .. pythonscad-example::

            from pybosl2.metaballs import MetaballSpec, mb_sphere
            from pybosl2 import VNF, Bounds3D

            spec = [
                MetaballSpec([-14, 0, 0], mb_sphere(12)),
                MetaballSpec([14, 0, 0], mb_sphere(12)),
            ]
            VNF.from_metaballs(
                spec,
                Bounds3D(-40, -20, -20, 40, 20, 20, 80, 40, 40),
                voxel_size=2,
            ).polyhedron().show()
        """
        assert spec, "from_metaballs(): the spec is empty."

        bb: Bounds3D
        if isinstance(bounding_box, Bounds3D):
            bb = bounding_box
        elif isinstance(bounding_box, (int, float)):
            size = float(bounding_box)
            bb = Bounds3D(-size / 2, -size / 2, -size / 2, size / 2, size / 2, size / 2, size, size, size)
        elif isinstance(bounding_box, (list, tuple, np.ndarray)):
            val_list = list(bounding_box)
            if len(val_list) == 2 and isinstance(val_list[0], (list, tuple, np.ndarray)):
                p1 = [float(x) for x in val_list[0]]
                p2 = [float(x) for x in val_list[1]]
                bb = Bounds3D(p1[0], p1[1], p1[2], p2[0], p2[1], p2[2], p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
            elif len(val_list) == 3:
                val = [float(x) for x in val_list]
                bb = Bounds3D(
                    -val[0] / 2, -val[1] / 2, -val[2] / 2, val[0] / 2, val[1] / 2, val[2] / 2, val[0], val[1], val[2]
                )
            elif len(val_list) == 6:
                val = [float(x) for x in val_list]
                bb = Bounds3D(
                    val[0], val[1], val[2], val[3], val[4], val[5], val[3] - val[0], val[4] - val[1], val[5] - val[2]
                )
            else:
                raise ValueError("bounding_box list must have length 2, 3 or 6.")
        else:
            raise TypeError("bounding_box must be Bounds3D, float, or list/tuple.")

        from pybosl2.isosurface import _MetaballSpec

        norm_spec: list[_MetaballSpec] = []
        for item in spec:
            if isinstance(item, _MetaballSpec):
                norm_spec.append(item)
            else:
                norm_spec.append(_MetaballSpec(item[0], item[1]))

        bb, vs = _resolve_grid(bb, voxel_size, voxel_count, exact_bounds)
        invs: list[np.ndarray] = [np.linalg.inv(s.transform) for s in norm_spec]

        def field(pts: np.ndarray) -> np.ndarray:
            homo: np.ndarray = np.hstack([pts, np.ones((len(pts), 1))])
            total: np.ndarray = np.zeros(len(pts))
            for s, inv in zip(norm_spec, invs, strict=False):
                local: np.ndarray = (inv @ homo.T).T[:, :3]
                total += s.metaball.field(local)
            return total

        return VNF.from_field(field, isovalue, bounding_box=bb, voxel_size=vs, closed=closed, exact_bounds=True)


def vnf_polyhedron(vnf: VNF) -> Any:
    """Render a :class:`VNF` to a PythonSCAD ``polyhedron`` (BOSL2 ``vnf_polyhedron()``).

    A module-level convenience wrapper around :meth:`VNF.polyhedron` so existing
    code using the BOSL2 OpenSCAD calling convention ``vnf_polyhedron(vnf)`` works
    without any change.

    Args:
        vnf: the :class:`VNF` to render.

    Returns:
        A PythonSCAD ``polyhedron`` solid.

    Examples:
        Build a swept VNF and render it:

        .. pythonscad-example::

            from pybosl2 import Path2D, vnf_polyhedron

            sq = [[-5, -5], [5, -5], [5, 5], [-5, 5]]
            v = Path2D(sq).linear_sweep(height=20)
            vnf_polyhedron(v).show()
    """
    return vnf.polyhedron()


__all__ = [
    "VNF",
    "VnfStyle",
    "contour",
    "vnf_polyhedron",
]

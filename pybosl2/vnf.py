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
from enum import Enum
from typing import TYPE_CHECKING, Any

import numpy as np

from pybosl2._mctable import CORNER_OFFSETS, EDGE_CORNERS, TRI_TABLE
from pybosl2.bounds import Bounds3D

if TYPE_CHECKING:
    from collections.abc import Callable

    from pybosl2.path3d import Path3D
    from pybosl2.points import Point

_EPS = 1e-9

# -- metaball field helpers ----------------------------------------------------

INF = math.inf


def _mb_cutoff(dist: np.ndarray, cutoff: float) -> np.ndarray:
    if not math.isfinite(cutoff):
        return np.ones_like(dist)
    out = np.zeros_like(dist)
    m: np.ndarray = dist < cutoff
    out[m] = 0.5 * (np.cos(np.pi * (dist[m] / cutoff) ** 4) + 1)
    return out


def _mb_field(dist: np.ndarray, base: float, influence: float, cutoff: float, neg: int) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = base / dist
        v = ratio if influence == 1 else np.power(ratio, 1.0 / influence)
    if math.isfinite(cutoff):
        v = _mb_cutoff(dist, cutoff) * v
    return neg * v


def _squircle_se_exponent(squareness: float) -> float:
    s = min(0.998, squareness)
    rho = 1 + s * (math.sqrt(2) - 1)
    x = rho / math.sqrt(2)
    return math.log(0.5) / math.log(x)


class _Metaball:
    """A metaball field primitive: ``field(pts)`` over ``(N, 3)`` points.

    Combine several with :meth:`VNF.from_metaballs`.

    Args:
        field: A vectorised ``(N, 3) → (N,)`` callable.
        neg: 1 for additive, -1 for subtractive.
    """

    def __init__(self, field: Callable[[np.ndarray], np.ndarray], neg: int = 1):
        self.field = field
        self.neg = neg

    def __call__(self, pt: np.ndarray) -> float:
        return float(self.field(np.atleast_2d(np.asarray(pt, dtype=float)))[0])


class _MetaballSpec:
    """A positioned metaball: a transform (4×4 matrix or Point translation) and a :class:`_Metaball`.

    Args:
        transform: A 4×4 matrix or a 3-element position (translation).
        metaball: The field primitive to place at that transform.
    """

    def __init__(self, transform: np.ndarray | Point, metaball: _Metaball):
        self.transform = transform
        self.metaball = metaball


# Public aliases for the metaball classes (kept for backward compat)
Metaball = _Metaball
MetaballSpec = _MetaballSpec


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

    @classmethod
    def vertex_array(
        cls,
        points: Path3D | list[Path3D] | list[list[list[float]]] | list[np.ndarray] | np.ndarray,
        caps: bool = False,
        cap1: bool | None = None,
        cap2: bool | None = None,
        col_wrap: bool = False,
        row_wrap: bool = False,
        reverse: bool = False,
        style: str | VnfStyle = "default",
    ) -> "VNF":
        """Build a VNF from a rectangular grid of 3-D points (BOSL2 vnf_vertex_array()).

        Each grid cell becomes triangles (or a quad) chosen by *style*: "default", "alt",
        "min_edge", "min_area", "convex", "concave", "quincunx", "quad", "flip1", "flip2".
        *col_wrap*/*row_wrap* close the grid into a tube/torus; *caps*/*cap1*/*cap2* close the
        column-wrapped ends; *reverse* flips face winding. Degenerate (zero-area) faces are dropped.
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
        grid = _to_grid(points)
        rows = len(grid)
        if rows == 0:
            return cls([], [])
        cols = len(grid[0])
        if rows <= 1 or cols <= 1:
            return cls([], [])

        cap1 = cap1 if cap1 is not None else (caps if caps is not None else False)
        cap2 = cap2 if cap2 is not None else (caps if caps is not None else False)
        if (cap1 or cap2) and not col_wrap:
            raise AssertionError("col_wrap must be true if caps are requested")
        if (cap1 or cap2) and row_wrap:
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
        if cap1:
            faces.append(_count(cols, 0, reverse=not reverse))
        if cap2:
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
        isovalue: float | tuple[float, float],
        bounding_box: Bounds3D | None = None,
        voxel_size: float | None = None,
        voxel_count: int | None = None,
        closed: bool = True,
        reverse: bool = False,
        exact_bounds: bool = False,
    ) -> "VNF":
        """Mesh a scalar field into a :class:`VNF` via marching cubes.

        The solid is the region where ``f >= isovalue`` (a single number) or,
        for a range ``(lo, hi)``, where ``lo <= f <= hi``.

        Args:
            f: A :class:`~pybosl2.path3d.Path3D`, a 3-D numpy array,
                a ``(N,3) → (N,)`` callable, or a
                ``(:class:`~pybosl2.path3d.Path3D`) → (N,)`` callable.
            isovalue: Threshold or ``(min, max)`` range.
            bounding_box: A :class:`~pybosl2.bounds.Bounds3D` or ``None``
                (auto-computed from array shape when *f* is an array).
            voxel_size: Isotropic voxel size.
            voxel_count: Approximate total voxel count (ignored if *voxel_size* given).
            closed: If True, pad field so mesh closes at bounding-box faces.
            reverse: If True, reverse inside/outside sense.
            exact_bounds: If True, use *bounding_box* exactly.

        Returns:
            A :class:`VNF`.

        Examples:
            .. pythonscad-example::

                def field(p):
                    x, y, z = p[:, 0], p[:, 1], p[:, 2]
                    return 20 / np.sqrt(x*x + y*y + z*z) + 3 * np.sin(x / 3)
                VNF.from_field(
                    field, 1,
                    Bounds3D(-30, -30, -30, 30, 30, 30, 60, 60, 60),
                    voxel_size=2,
                ).polyhedron().show()
        """
        import math

        from pybosl2.path3d import Path3D

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
            lo, hi = float(isovalue[0]), float(isovalue[1])
            assert lo < hi, "from_field(): isovalue range must be (min, max) with min < max."
            if math.isinf(lo):
                iso, reverse = hi, not reverse
            else:
                iso = lo
        else:
            iso = float(isovalue)

        if isinstance(f, np.ndarray) or (isinstance(f, (list, tuple)) and not callable(f)):
            field = np.asarray(f, dtype=float)
            if bounding_box is None:
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
                bb = bounding_box
                vs_final = (bb.max_x - bb.min_x) / (field.shape[0] - 1)
            xs, ys, zs = _grid_axes(bb, vs_final)
        else:
            assert bounding_box is not None, "from_field(): a callable field needs a bounding_box."
            bb, vs_final = _resolve_grid(bounding_box, voxel_size, voxel_count, exact_bounds)
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
        bounding_box: Bounds3D,
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

                spec = [
                    _MetaballSpec([-14, 0, 0], VNF.mb_sphere(12)),
                    _MetaballSpec([14, 0, 0], VNF.mb_sphere(12)),
                ]
                VNF.from_metaballs(
                    spec,
                    Bounds3D(-40, -20, -20, 40, 20, 20, 80, 40, 40),
                    voxel_size=2,
                ).polyhedron().show()
        """

        def _to_matrix(t: object) -> np.ndarray:
            a = np.asarray(t, dtype=float)
            if a.shape == (4, 4):
                return a
            m = np.eye(4)
            m[:3, 3] = a[:3]
            return m

        raw = list(spec)
        pairs: list[tuple[np.ndarray, _Metaball]] = []
        if raw and isinstance(raw[0], _Metaball):
            raise AssertionError("from_metaballs(): spec must be _MetaballSpec entries.")
        if raw and isinstance(raw[0], _MetaballSpec):
            pairs = [(_to_matrix(s.transform), s.metaball) for s in raw]
        elif raw and isinstance(raw[0], (tuple, list)) and len(raw[0]) == 2 and isinstance(raw[0][1], _Metaball):
            pairs = [(_to_matrix(t), mb) for t, mb in raw]  # type: ignore[misc,has-type]
        elif raw:
            assert len(raw) % 2 == 0, "from_metaballs(): flat spec must alternate transform and metaball."
            pairs = [(_to_matrix(raw[i]), raw[i + 1]) for i in range(0, len(raw), 2)]  # type: ignore[misc]
        assert pairs, "from_metaballs(): the spec is empty."

        bb, vs = _resolve_grid(bounding_box, voxel_size, voxel_count, exact_bounds)
        invs: list[np.ndarray] = [np.linalg.inv(t) for t, _ in pairs]

        def field(pts: np.ndarray) -> np.ndarray:
            homo: np.ndarray = np.hstack([pts, np.ones((len(pts), 1))])
            total: np.ndarray = np.zeros(len(pts))
            for (_t, ball), inv in zip(pairs, invs, strict=False):
                local: np.ndarray = (inv @ homo.T).T[:, :3]
                total += ball.field(local)
            return total

        return VNF.from_field(field, isovalue, bounding_box=bb, voxel_size=vs, closed=closed, exact_bounds=True)

    # -- metaball field primitives (static methods) ------------------------------

    @staticmethod
    def mb_sphere(
        radius: float | None = None,
        cutoff: float = math.inf,
        influence: float = 1,
        negative: bool = False,
        diameter: float | None = None,
    ) -> "_Metaball":
        """A spherical metaball field.

        Args:
            radius: Sphere radius (mutually exclusive with *diameter*).
            cutoff: Distance beyond which the field is clamped to 0. ``inf`` = no cutoff.
            influence: Blending strength (smaller = sharper).
            negative: If True, produce a subtractive metaball.
            diameter: Sphere diameter.

        Returns:
            A :class:`_Metaball` primitive.

        Raises:
            AssertionError: If no positive radius or diameter is given.
        """
        rr = radius if radius is not None else (diameter / 2 if diameter is not None else None)
        assert rr and rr > 0, "mb_sphere(): need a positive radius or diameter."
        neg = -1 if negative else 1

        def field(pts: np.ndarray) -> np.ndarray:
            dist: np.ndarray = np.linalg.norm(pts, axis=1)
            return _mb_field(dist, rr, influence, cutoff, neg)

        return _Metaball(field, neg)

    @staticmethod
    def mb_cuboid(
        size: tuple[float, float, float] | float,
        squareness: float = 0.5,
        cutoff: float = math.inf,
        influence: float = 1,
        negative: bool = False,
    ) -> "_Metaball":
        """A rounded-cuboid metaball field.

        Args:
            size: A scalar (cube edge) or ``(dx, dy, dz)`` tuple.
            squareness: 0 = fully round, 1 = sharp square edges.
            cutoff: Distance beyond which the field is clamped to 0.
            influence: Blending strength.
            negative: If True, produce a subtractive metaball.

        Returns:
            A :class:`_Metaball` primitive.

        Raises:
            AssertionError: If *squareness* is not in ``[0, 1]``.
        """
        assert 0 <= squareness <= 1, "mb_cuboid(): squareness must be in [0, 1]."
        xp = _squircle_se_exponent(squareness)
        inv = (
            np.array([2 / size] * 3, dtype=float)
            if isinstance(size, (int, float))
            else 2 / np.asarray(size, dtype=float)
        )
        neg = -1 if negative else 1

        def field(pts: np.ndarray) -> np.ndarray:
            p: np.ndarray = np.abs(pts * inv)
            dist: np.ndarray = np.max(p, axis=1) if xp >= 1100 else np.sum(p**xp, axis=1) ** (1 / xp)
            return _mb_field(dist, 1.0, influence, cutoff, neg)

        return _Metaball(field, neg)

    @staticmethod
    def mb_torus(
        major_radius: float | None = None,
        minor_radius: float | None = None,
        cutoff: float = math.inf,
        influence: float = 1,
        negative: bool = False,
        major_diameter: float | None = None,
        minor_diameter: float | None = None,
    ) -> "_Metaball":
        """A torus metaball field.

        Args:
            major_radius: Distance from the origin to the tube centre.
            minor_radius: Tube radius.
            cutoff: Distance beyond which the field is clamped to 0.
            influence: Blending strength.
            negative: If True, produce a subtractive metaball.
            major_diameter: Overrides *major_radius*.
            minor_diameter: Overrides *minor_radius*.

        Returns:
            A :class:`_Metaball` primitive.

        Raises:
            AssertionError: If either radius is missing or non-positive.
        """
        rmaj, rmin = (
            (
                major_radius
                if major_radius is not None
                else (major_diameter / 2 if major_diameter is not None else None)
            ),
            (
                minor_radius
                if minor_radius is not None
                else (minor_diameter / 2 if minor_diameter is not None else None)
            ),
        )
        assert rmaj and rmin and rmaj > 0 and rmin > 0, "mb_torus(): need positive major_radius and minor_radius."
        neg = -1 if negative else 1

        def field(pts: np.ndarray) -> np.ndarray:
            rad: np.ndarray = np.hypot(pts[:, 0], pts[:, 1]) - rmaj
            dist: np.ndarray = np.hypot(rad, pts[:, 2])
            return _mb_field(dist, rmin, influence, cutoff, neg)

        return _Metaball(field, neg)

    @staticmethod
    def mb_capsule(
        height: float | None = None,
        radius: float | None = None,
        cutoff: float = math.inf,
        influence: float = 1,
        negative: bool = False,
        diameter: float | None = None,
    ) -> "_Metaball":
        """A capsule (round-ended cylinder) metaball field.

        Args:
            height: Total length including rounded ends.
            radius: Shaft radius.
            cutoff: Distance beyond which the field is clamped to 0.
            influence: Blending strength.
            negative: If True, produce a subtractive metaball.
            diameter: Shaft diameter.

        Returns:
            A :class:`_Metaball` primitive.

        Raises:
            AssertionError: If *height* or *radius* is missing, non-positive, or shaft too short.
        """
        rr = radius if radius is not None else (diameter / 2 if diameter is not None else None)
        assert height and rr and height > 0 and rr > 0, "mb_capsule(): need positive height and radius."
        hl = (height - 2 * rr) / 2
        assert hl > 0, "mb_capsule(): total length must exceed the two rounded ends."
        neg = -1 if negative else 1

        def field(pts: np.ndarray) -> np.ndarray:
            z = pts[:, 2]
            rxy: np.ndarray = np.hypot(pts[:, 0], pts[:, 1])
            below: np.ndarray = z < -hl
            above: np.ndarray = z > hl
            dist: np.ndarray = np.where(below, np.hypot(rxy, z + hl), np.where(above, np.hypot(rxy, z - hl), rxy))
            return _mb_field(dist, rr, influence, cutoff, neg)

        return _Metaball(field, neg)

    @staticmethod
    def mb_disk(
        height: float | None = None,
        radius: float | None = None,
        cutoff: float = math.inf,
        influence: float = 1,
        negative: bool = False,
        diameter: float | None = None,
    ) -> "_Metaball":
        """A rounded-edge disk metaball field.

        Args:
            height: Disk thickness.
            radius: Outer radius.
            cutoff: Distance beyond which the field is clamped to 0.
            influence: Blending strength.
            negative: If True, produce a subtractive metaball.
            diameter: Outer diameter.

        Returns:
            A :class:`_Metaball` primitive.

        Raises:
            AssertionError: If *height* or *radius* is missing, non-positive, or too thin.
        """
        rr = radius if radius is not None else (diameter / 2 if diameter is not None else None)
        assert height and rr and height > 0 and rr > 0, "mb_disk(): need positive height and radius."
        hl = height / 2
        ri = rr - hl
        assert ri > 0, "mb_disk(): diameter must exceed the thickness."
        neg = -1 if negative else 1

        def field(pts: np.ndarray) -> np.ndarray:
            rxy: np.ndarray = np.hypot(pts[:, 0], pts[:, 1])
            z = pts[:, 2]
            dist: np.ndarray = np.where(rxy < ri, np.abs(z), np.hypot(rxy - ri, z))
            return _mb_field(dist, hl, influence, cutoff, neg)

        return _Metaball(field, neg)

    @staticmethod
    def mb_octahedron(
        size: tuple[float, float, float] | float,
        squareness: float = 0.5,
        cutoff: float = math.inf,
        influence: float = 1,
        negative: bool = False,
    ) -> "_Metaball":
        """A rounded-octahedron metaball field.

        Args:
            size: A scalar (circumscribed cube edge) or ``(dx, dy, dz)`` tuple.
            squareness: 0 = round, 1 = sharp octahedron edges.
            cutoff: Distance beyond which the field is clamped to 0.
            influence: Blending strength.
            negative: If True, produce a subtractive metaball.

        Returns:
            A :class:`_Metaball` primitive.

        Raises:
            AssertionError: If *squareness* is not in ``[0, 1]``.
        """
        assert 0 <= squareness <= 1, "mb_octahedron(): squareness must be in [0, 1]."
        xp = _squircle_se_exponent(squareness)

        def _octdist(p: np.ndarray) -> np.ndarray:
            if xp >= 1100:
                return np.abs(p[:, 0]) + np.abs(p[:, 1]) + np.abs(p[:, 2])
            a = np.abs(p[:, 0] + p[:, 1] + p[:, 2]) ** xp
            b = np.abs(-p[:, 0] - p[:, 1] + p[:, 2]) ** xp
            c = np.abs(-p[:, 0] + p[:, 1] - p[:, 2]) ** xp
            e = np.abs(p[:, 0] - p[:, 1] - p[:, 2]) ** xp
            return (a + b + c + e) ** (1 / xp)  # type: ignore[no-any-return]

        corr = 1.0 / _octdist(np.array([[1 / 3, 1 / 3, 1 / 3]]))[0]
        inv = (
            corr * np.array([2 / size] * 3, dtype=float)
            if isinstance(size, (int, float))
            else corr * 2 / np.asarray(size, dtype=float)
        )
        neg = -1 if negative else 1

        def field(pts: np.ndarray) -> np.ndarray:
            dist: np.ndarray = _octdist(pts * inv)
            return _mb_field(dist, 1.0, influence, cutoff, neg)

        return _Metaball(field, neg)

    @staticmethod
    def mb_connector(
        p1: Point,
        p2: Point,
        radius: float | None = None,
        cutoff: float = math.inf,
        influence: float = 1,
        negative: bool = False,
        diameter: float | None = None,
    ) -> "_Metaball":
        """A capsule metaball field spanning from *p1* to *p2*.

        Args:
            p1: Start :class:`~pybosl2.points.Point`.
            p2: End :class:`~pybosl2.points.Point` (must be distinct from *p1*).
            radius: Shaft radius.
            cutoff: Distance beyond which the field is clamped to 0.
            influence: Blending strength.
            negative: If True, produce a subtractive metaball.
            diameter: Shaft diameter.

        Returns:
            A :class:`_Metaball` primitive.

        Raises:
            AssertionError: If *radius* is missing, non-positive, or *p1* equals *p2*.
        """
        from pybosl2.transforms import axis_angle_matrix, rot_from_to

        rr = radius if radius is not None else (diameter / 2 if diameter is not None else None)
        a, b = np.asarray(p1, dtype=float), np.asarray(p2, dtype=float)
        assert rr and rr > 0 and not np.array_equal(a, b), "mb_connector(): need distinct points and positive radius."
        neg = -1 if negative else 1
        dc: np.ndarray = b - a
        height: float = float(np.linalg.norm(dc)) / 2
        angle, axis = rot_from_to(dc, [0, 0, 1])
        m3: np.ndarray = np.asarray(axis_angle_matrix(angle, axis), dtype=float)

        def field(pts: np.ndarray) -> np.ndarray:
            local: np.ndarray = (pts - (a + b) / 2) @ m3.T
            z = local[:, 2]
            rxy: np.ndarray = np.hypot(local[:, 0], local[:, 1])
            below: np.ndarray = z < -height
            above: np.ndarray = z > height
            dist: np.ndarray = np.where(
                below, np.hypot(rxy, z + height), np.where(above, np.hypot(rxy, z - height), rxy)
            )
            return _mb_field(dist, rr, influence, cutoff, neg)

        return _Metaball(field, neg)


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

            sq = [[-5, -5], [5, -5], [5, 5], [-5, 5]]
            v = Path2D(sq).linear_sweep(height=20)
            vnf_polyhedron(v).show()
    """
    return vnf.polyhedron()


__all__ = [
    "VNF",
    "VnfStyle",
    "vnf_polyhedron",
    "_Metaball",
    "_MetaballSpec",
    "Metaball",
    "MetaballSpec",
    "INF",
]

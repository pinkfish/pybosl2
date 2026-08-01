# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/isosurface.py
#    Pure-Python port of the 3-D core of BOSL2's isosurface.scad: :func:`isosurface` meshes the
#    level set of a scalar field over a voxel grid (marching cubes) into a :class:`~pybosl2.vnf.VNF`,
#    the ``mb_*`` functions are metaball field primitives, and :func:`metaballs` sums transformed
#    field primitives and meshes the result into a blobby surface.
#
# FileSummary: Isosurface meshing (marching cubes), metaball field primitives, and metaballs().
# DocCategory: Paths, regions & surfaces
# FileGroup: BOSL2

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from pybosl2._mctable import CORNER_OFFSETS, EDGE_CORNERS, TRI_TABLE
from pybosl2.bounds import Bounds3D

if TYPE_CHECKING:
    from collections.abc import Callable

    from pybosl2.points import Point
    from pybosl2.vnf import VNF

__all__ = [
    "Metaball",
    "isosurface",
    "metaballs",
    "mb_sphere",
    "mb_cuboid",
    "mb_torus",
    "mb_capsule",
    "mb_disk",
    "mb_octahedron",
    "mb_connector",
]

INF = math.inf


# -- private helpers (numpy for the marching-cubes hot path) --------------------


def _to_bounds3d(bb: Bounds3D | float | list | np.ndarray) -> Bounds3D:
    """Normalise a bounding-box input to a :class:`Bounds3D`."""
    if isinstance(bb, Bounds3D):
        return bb
    if isinstance(bb, (int, float)):
        hb = 0.5 * bb
        return Bounds3D(
            min_x=-hb,
            min_y=-hb,
            min_z=-hb,
            max_x=hb,
            max_y=hb,
            max_z=hb,
            width=bb,
            length=bb,
            height=bb,
        )
    arr = np.asarray(bb, dtype=float)
    x0, y0, z0 = float(arr[0][0]), float(arr[0][1]), float(arr[0][2])
    x1, y1, z1 = float(arr[1][0]), float(arr[1][1]), float(arr[1][2])
    return Bounds3D(
        min_x=x0,
        min_y=y0,
        min_z=z0,
        max_x=x1,
        max_y=y1,
        max_z=z1,
        width=x1 - x0,
        length=y1 - y0,
        height=z1 - z0,
    )


def _resolve_grid(
    bb: Bounds3D,
    voxel_size: float | None,
    voxel_count: int | None,
    exact_bounds: bool,
) -> tuple[Bounds3D, float]:
    """Resolve voxel size and (optionally) grow bounds to whole voxels."""
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


# -- marching cubes ------------------------------------------------------------


def isosurface(
    f: np.ndarray | Callable[[np.ndarray], np.ndarray],
    isovalue: float | tuple[float, float],
    bounding_box: Bounds3D | float | None = None,
    voxel_size: float | None = None,
    voxel_count: int | None = None,
    closed: bool = True,
    reverse: bool = False,
    exact_bounds: bool = False,
) -> "VNF":
    """Mesh the level set of a scalar field *f* into a :class:`~pybosl2.vnf.VNF`.

    The solid is the region where ``f >= isovalue`` (a single number) or,
    for a range ``(lo, hi)``, where ``lo <= f <= hi``.

    Args:
        f: A ``(N, 3) → (N,)`` vectorised callable, a ``point → value``
            scalar callable, or a precomputed 3-D numpy array.
        isovalue: Threshold or ``(min, max)`` range.
        bounding_box: A :class:`~pybosl2.bounds.Bounds3D`, a scalar (cube edge), or ``None``
            (auto-computed from array shape when *f* is an array).
        voxel_size: Isotropic voxel size.
        voxel_count: Approximate total voxel count (ignored if *voxel_size* given).
        closed: If True, pad field so the mesh closes at bounding-box faces.
        reverse: If True, reverse the inside/outside sense.
        exact_bounds: If True, use *bounding_box* exactly; otherwise grow to whole voxels.

    Returns:
        A :class:`~pybosl2.vnf.VNF`.

    Examples:
        .. pythonscad-example::

            def field(p):
                import numpy as np
                x, y, z = p[:, 0], p[:, 1], p[:, 2]
                return 20 / np.sqrt(x*x + y*y + z*z) + 3 * np.sin(x / 3)
            isosurface(field, 1, bounding_box=60, voxel_size=2).polyhedron().show()
    """
    from pybosl2.vnf import VNF

    if isinstance(isovalue, tuple):
        lo, hi = float(isovalue[0]), float(isovalue[1])
        assert lo < hi, "isosurface(): isovalue range must be (min, max) with min < max."
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
        else:
            bb = _to_bounds3d(bounding_box)
            vs = (bb.max_x - bb.min_x) / (field.shape[0] - 1)
        xs, ys, zs = _grid_axes(bb, vs)
    else:
        assert bounding_box is not None, "isosurface(): a callable field needs a bounding_box."
        bb, vs = _resolve_grid(_to_bounds3d(bounding_box), voxel_size, voxel_count, exact_bounds)
        xs, ys, zs = _grid_axes(bb, vs)
        field = _sample_field(f, xs, ys, zs)

    verts, faces = _marching_cubes(field, xs, ys, zs, iso, closed)
    vnf = VNF(verts, faces)
    if len(faces):
        vol = vnf.volume()
        if (vol < 0) != reverse:
            vnf = vnf.reverse()
    return vnf


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


# -- metaball field primitives --------------------------------------------------


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


class Metaball:
    """A metaball field primitive: ``field(pts)`` over ``(N, 3)`` points.

    Combine several with :func:`metaballs`.

    Args:
        field: A vectorised ``(N, 3) → (N,)`` callable.
        neg: 1 for additive, -1 for subtractive.
    """

    def __init__(self, field: Callable[[np.ndarray], np.ndarray], neg: int = 1):
        self.field = field
        self.neg = neg

    def __call__(self, pt: np.ndarray) -> float:
        return float(self.field(np.atleast_2d(np.asarray(pt, dtype=float)))[0])


def mb_sphere(
    radius: float | None = None,
    cutoff: float = INF,
    influence: float = 1,
    negative: bool = False,
    diameter: float | None = None,
) -> Metaball:
    """A spherical metaball field.

    Args:
        radius: Sphere radius (mutually exclusive with *diameter*).
        cutoff: Distance beyond which the field is clamped to 0. ``INF`` = no cutoff.
        influence: Blending strength (smaller = sharper).
        negative: If True, produce a subtractive metaball.
        diameter: Sphere diameter.

    Returns:
        A :class:`Metaball` primitive.

    Raises:
        AssertionError: If no positive radius or diameter is given.
    """
    rr = radius if radius is not None else (diameter / 2 if diameter is not None else None)
    assert rr and rr > 0, "mb_sphere(): need a positive radius or diameter."
    neg = -1 if negative else 1

    def field(pts: np.ndarray) -> np.ndarray:
        dist: np.ndarray = np.linalg.norm(pts, axis=1)
        return _mb_field(dist, rr, influence, cutoff, neg)

    return Metaball(field, neg)


def mb_cuboid(
    size: tuple[float, float, float] | float,
    squareness: float = 0.5,
    cutoff: float = INF,
    influence: float = 1,
    negative: bool = False,
) -> Metaball:
    """A rounded-cuboid metaball field.

    Args:
        size: A scalar (cube edge) or ``(dx, dy, dz)`` tuple.
        squareness: 0 = fully round, 1 = sharp square edges.
        cutoff: Distance beyond which the field is clamped to 0.
        influence: Blending strength.
        negative: If True, produce a subtractive metaball.

    Returns:
        A :class:`Metaball` primitive.

    Raises:
        AssertionError: If *squareness* is not in ``[0, 1]``.
    """
    assert 0 <= squareness <= 1, "mb_cuboid(): squareness must be in [0, 1]."
    xp = _squircle_se_exponent(squareness)
    inv: np.ndarray = np.array([2 / size] * 3) if isinstance(size, (int, float)) else 2 / np.asarray(size, dtype=float)
    neg = -1 if negative else 1

    def field(pts: np.ndarray) -> np.ndarray:
        p: np.ndarray = np.abs(pts * inv)
        dist: np.ndarray = np.max(p, axis=1) if xp >= 1100 else np.sum(p**xp, axis=1) ** (1 / xp)
        return _mb_field(dist, 1.0, influence, cutoff, neg)

    return Metaball(field, neg)


def mb_torus(
    major_radius: float | None = None,
    minor_radius: float | None = None,
    cutoff: float = INF,
    influence: float = 1,
    negative: bool = False,
    major_diameter: float | None = None,
    minor_diameter: float | None = None,
) -> Metaball:
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
        A :class:`Metaball` primitive.

    Raises:
        AssertionError: If either radius is missing or non-positive.
    """
    rmaj, rmin = (
        major_radius if major_radius is not None else (major_diameter / 2 if major_diameter is not None else None),
        minor_radius if minor_radius is not None else (minor_diameter / 2 if minor_diameter is not None else None),
    )
    assert rmaj and rmin and rmaj > 0 and rmin > 0, "mb_torus(): need positive major_radius and minor_radius."
    neg = -1 if negative else 1

    def field(pts: np.ndarray) -> np.ndarray:
        rad: np.ndarray = np.hypot(pts[:, 0], pts[:, 1]) - rmaj
        dist: np.ndarray = np.hypot(rad, pts[:, 2])
        return _mb_field(dist, rmin, influence, cutoff, neg)

    return Metaball(field, neg)


def mb_capsule(
    height: float | None = None,
    radius: float | None = None,
    cutoff: float = INF,
    influence: float = 1,
    negative: bool = False,
    diameter: float | None = None,
) -> Metaball:
    """A capsule (round-ended cylinder) metaball field.

    Args:
        height: Total length including rounded ends.
        radius: Shaft radius.
        cutoff: Distance beyond which the field is clamped to 0.
        influence: Blending strength.
        negative: If True, produce a subtractive metaball.
        diameter: Shaft diameter.

    Returns:
        A :class:`Metaball` primitive.

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

    return Metaball(field, neg)


def mb_disk(
    height: float | None = None,
    radius: float | None = None,
    cutoff: float = INF,
    influence: float = 1,
    negative: bool = False,
    diameter: float | None = None,
) -> Metaball:
    """A rounded-edge disk metaball field.

    Args:
        height: Disk thickness.
        radius: Outer radius.
        cutoff: Distance beyond which the field is clamped to 0.
        influence: Blending strength.
        negative: If True, produce a subtractive metaball.
        diameter: Outer diameter.

    Returns:
        A :class:`Metaball` primitive.

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

    return Metaball(field, neg)


def mb_octahedron(
    size: tuple[float, float, float] | float,
    squareness: float = 0.5,
    cutoff: float = INF,
    influence: float = 1,
    negative: bool = False,
) -> Metaball:
    """A rounded-octahedron metaball field.

    Args:
        size: A scalar (circumscribed cube edge) or ``(dx, dy, dz)`` tuple.
        squareness: 0 = round, 1 = sharp octahedron edges.
        cutoff: Distance beyond which the field is clamped to 0.
        influence: Blending strength.
        negative: If True, produce a subtractive metaball.

    Returns:
        A :class:`Metaball` primitive.

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
    scale = np.array([2 / size] * 3) if isinstance(size, (int, float)) else 2 / np.asarray(size, dtype=float)
    inv: np.ndarray = corr * scale
    neg = -1 if negative else 1

    def field(pts: np.ndarray) -> np.ndarray:
        dist: np.ndarray = _octdist(pts * inv)
        return _mb_field(dist, 1.0, influence, cutoff, neg)

    return Metaball(field, neg)


def mb_connector(
    p1: Point,
    p2: Point,
    radius: float | None = None,
    cutoff: float = INF,
    influence: float = 1,
    negative: bool = False,
    diameter: float | None = None,
) -> Metaball:
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
        A :class:`Metaball` primitive.

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
        dist: np.ndarray = np.where(below, np.hypot(rxy, z + height), np.where(above, np.hypot(rxy, z - height), rxy))
        return _mb_field(dist, rr, influence, cutoff, neg)

    return Metaball(field, neg)


# -- metaballs ------------------------------------------------------------------


def _to_matrix(t: np.ndarray | list[float]) -> np.ndarray:
    """A 4x4 transform from a 4x4 matrix or a 3-vector (translation)."""
    t_arr: np.ndarray = np.asarray(t, dtype=float)
    if t_arr.shape == (4, 4):
        return t_arr
    m = np.eye(4)
    m[:3, 3] = t_arr[:3]
    return m


def _parse_spec(spec: list) -> list[tuple[np.ndarray, Metaball]]:
    """Normalise a metaball spec into a list of ``(4x4 transform, Metaball)`` pairs.

    Accepts a list of ``(transform, metaball)`` tuples or the BOSL2 flat form
    ``[transform, metaball, transform, metaball, ...]``.

    Raises:
        AssertionError: If the first element is a Metaball (missing transforms)
            or the flat form has an odd number of elements.
    """
    items = list(spec)
    if items and isinstance(items[0], Metaball):
        raise AssertionError("metaballs(): spec must be (transform, metaball) pairs.")
    if items and isinstance(items[0], (tuple, list)) and len(items[0]) == 2 and isinstance(items[0][1], Metaball):
        return [(_to_matrix(t), mb) for t, mb in items]
    assert len(items) % 2 == 0, "metaballs(): flat spec must alternate transform and metaball."
    return [(_to_matrix(items[i]), items[i + 1]) for i in range(0, len(items), 2)]


def metaballs(
    spec: list,
    bounding_box: Bounds3D | float,
    voxel_size: float | None = None,
    voxel_count: int | None = None,
    isovalue: float = 1,
    closed: bool = True,
    exact_bounds: bool = False,
) -> "VNF":
    """Mesh transformed metaball primitives into a blobby surface.

    Args:
        spec: A list of ``(transform, Metaball)`` pairs (or the flat
            ``[transform, metaball, ...]`` form), where *transform* is a 4×4 matrix or
            a 3-vector position and *metaball* comes from ``mb_sphere`` / ``mb_cuboid`` /
            ``mb_torus`` / ``mb_capsule`` / ``mb_disk`` / ``mb_octahedron`` / ``mb_connector``.
        bounding_box: A :class:`~pybosl2.bounds.Bounds3D` or scalar cube edge.
        voxel_size: Isotropic voxel size.
        voxel_count: Approximate total voxel count.
        isovalue: Threshold at which the summed field surface is drawn.
        closed: If True, close mesh at bounding-box faces.
        exact_bounds: If True, use *bounding_box* exactly.

    Returns:
        A :class:`~pybosl2.vnf.VNF`.

    Examples:
        .. pythonscad-example::

            spec = [([-14, 0, 0], mb_sphere(12)), ([14, 0, 0], mb_sphere(12))]
            metaballs(spec, bounding_box=[[-40, -20, -20], [40, 20, 20]], voxel_size=2).polyhedron().show()
    """
    pairs = _parse_spec(spec)
    assert pairs, "metaballs(): the spec is empty."
    bb, vs = _resolve_grid(_to_bounds3d(bounding_box), voxel_size, voxel_count, exact_bounds)
    invs: list[np.ndarray] = [np.linalg.inv(t) for t, _ in pairs]

    def field(pts: np.ndarray) -> np.ndarray:
        homo: np.ndarray = np.hstack([pts, np.ones((len(pts), 1))])
        total: np.ndarray = np.zeros(len(pts))
        for (_t, ball), inv in zip(pairs, invs, strict=False):
            local: np.ndarray = (inv @ homo.T).T[:, :3]
            total += ball.field(local)
        return total

    return isosurface(
        field,
        isovalue,
        bounding_box=bb,
        voxel_size=vs,
        closed=closed,
        exact_bounds=True,
    )

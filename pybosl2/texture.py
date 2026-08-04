# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/texture.py
#    Port of BOSL2's texture() engine from skin.scad: the named-texture table that
#    :func:`~pybosl2.shapes3d.textured_tile` (and, in BOSL2, the textured sweeps) build from.
#    :func:`texture` resolves a texture *name* to its data -- either a height-field (a 2-D array of
#    heights in ``[0, 1]``) or a VNF tile ``(verts, faces)`` describing one unit cell of the surface.
#
#    All of BOSL2's height-field and VNF-tile textures are ported (9 height-field + 12 VNF), including
#    the ``$fn``-parametric ``cones``/``dots``/``hex_grid`` (pass *fn* for their resolution). A few VNF
#    tiles whose exact geometry can't be tiled watertight by :func:`vnf_tile_to_solid` (``bricks_vnf``,
#    ``checkers``, ``trunc_diamonds`` -- pinch points / interior holes) fall back to a sampled
#    height-field (:func:`rasterize_vnf_texture`), which flattens their vertical faces slightly. The
#    ``bricks``/``rough`` textures use this package's RNG (cosmetic difference), and ``cones`` defaults
#    to a small positive ``border`` (BOSL2 uses 0) so its tile seams watertight.
#
# FileSummary: The texture() named-texture engine.
# DocCategory: Foundational
# FileGroup: BOSL2

from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

import numpy as np

from pybosl2._helpers import quantup as _quantup_float

__all__ = ["texture", "TEXTURES", "is_heightfield_texture", "is_vnf_texture", "TextureType"]


# --- small helpers mirroring the BOSL2 list utilities texture() uses ----------


def _lerpn(a: float, b: float, sides: int, endpoint: bool = True) -> list[float]:
    """*sides* evenly spaced values from *a* to *b* (BOSL2 lerpn); *endpoint* includes *b*."""
    sides = int(sides)
    if sides <= 0:
        return []
    if endpoint:
        return list(np.linspace(a, b, sides))
    return [a + (b - a) * i / sides for i in range(sides)]


def quantup(x: float, m: int) -> int:
    """Round *x* up to the next multiple of *m* (BOSL2 quantup)."""
    return int(_quantup_float(x, m))


def _sel(lst: list[float], i: int) -> float:
    """BOSL2 select(): index with wraparound."""
    return lst[i % len(lst)]


def _rands(lo: float, hi: float, sides: int, seed: int) -> list[float]:
    """*sides* uniform randoms in ``[lo, hi]`` (BOSL2 rands; this port's RNG, so values differ)."""
    return list(np.random.default_rng(seed).uniform(lo, hi, sides))


# --- height-field textures (return a rows x cols array of heights in [0,1]) ---


def _tex_ribs(sides: int | None = None, **_: object) -> list[list[float]]:
    sides = quantup(sides if sides is not None else 2, 2)
    return [_lerpn(1, 0, sides // 2, False) + _lerpn(0, 1, sides // 2, False)]


def _tex_trunc_ribs(sides: int | None = None, **_: object) -> list[list[float]]:
    sides = quantup(sides if sides is not None else 4, 4)
    q = sides // 4
    return [[0.0] * q + _lerpn(0, 1, q, False) + [1.0] * q + _lerpn(1, 0, q, False)]


def _tex_wave_ribs(sides: int | None = None, **_: object) -> list[list[float]]:
    sides = max(6, (sides if sides is not None else 8))
    return [[(math.cos(math.radians(a)) + 1) / 2 for a in np.arange(0, 360 - 1e-9, 360 / sides)]]


def _tex_diamonds(sides: int | None = None, **_: object) -> list[list[float]]:
    sides = quantup(sides if sides is not None else 2, 2)
    path = _lerpn(0, 1, sides // 2, False) + _lerpn(1, 0, sides // 2, False)
    return [[min(_sel(path, i + j), _sel(path, i - j)) for j in range(sides)] for i in range(sides)]


def _tex_pyramids(sides: int | None = None, **_: object) -> list[list[float]]:
    sides = quantup(sides if sides is not None else 2, 2)
    return [
        [1 - (max(abs(i - sides / 2), abs(j - sides / 2)) / (sides / 2)) for j in range(sides)] for i in range(sides)
    ]


def _tex_trunc_pyramids(sides: int | None = None, **_: object) -> list[list[float]]:
    sides = quantup(sides if sides is not None else 6, 3)
    return [
        [(1 - (max(sides / 6, abs(i - sides / 2), abs(j - sides / 2)) / (sides / 2))) * 1.5 for j in range(sides)]
        for i in range(sides)
    ]


def _tex_hills(sides: int | None = None, **_: object) -> list[list[float]]:
    sides = sides if sides is not None else 12
    angs = list(np.arange(0, 359.999, 360 / sides))
    return [[(math.cos(math.radians(a)) * math.cos(math.radians(b)) + 1) / 2 for b in angs] for a in angs]


def _tex_bricks(sides: int | None = None, roughness: float | None = None, **_: object) -> list[list[float]]:
    sides = quantup(sides if sides is not None else 24, 2)
    rough = roughness if roughness is not None else 0.1
    thin = max(1, sides / 16)
    out = []
    for y in range(sides):
        rand = _rands(1 - rough, 1, sides, 12345 + y * 678)
        row = []
        for x in range(sides):
            if y % (sides // 2) <= thin:
                row.append(0.0)
            else:
                even = sides // 2 if (y // (sides // 2)) % 2 else 0
                row.append(0.0 if (x + even) % sides <= thin else rand[x])
        out.append(row)
    return out


def _tex_rough(sides: int | None = None, **_: object) -> list[list[float]]:
    sides = sides if sides is not None else 32
    return [_rands(0, 1, sides, 123456 + 29 * y) for y in range(sides)]


# --- VNF-tile textures (return (verts, faces); one unit cell over [0,1]x[0,1]) ---


def _sq(s: float, z: float = 0.0) -> list[list[float]]:
    """path3d of a square of side *s* anchored at the origin, at height *z* (BOSL2 square())."""
    return [[0.0, 0.0, z], [s, 0.0, z], [s, s, z], [0.0, s, z]]


def _rect(w: float, height: float, z: float = 0.0) -> list[list[float]]:
    """path3d of a *w* x *height* rectangle centred at the origin, at height *z* (BOSL2 rect())."""
    return [
        [-w / 2, -height / 2, z],
        [w / 2, -height / 2, z],
        [w / 2, height / 2, z],
        [-w / 2, height / 2, z],
    ]


def _mv(off: list[float], pts: list[list[float]]) -> list[list[float]]:
    o = list(off) + [0.0] * (3 - len(off))
    return [[p[0] + o[0], p[1] + o[1], p[2] + o[2]] for p in pts]


def _sqr(size: float | list[float], z: float = 0.0) -> list[list[float]]:
    """
    path3d of a square/rect anchored at the origin (BOSL2 square(), scalar or ``[w, height]``).
    """
    w, height = (size, size) if isinstance(size, (int, float)) else (size[0], size[1])
    return [[0.0, 0.0, z], [w, 0.0, z], [w, height, z], [0.0, height, z]]


def _zrot2(pts: list[list[float]], deg: float) -> list[list[float]]:
    """Rotate points about Z by *deg* degrees, preserving z (BOSL2 zrot())."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c * p[0] - s * p[1], s * p[0] + c * p[1], (p[2] if len(p) > 2 else 0.0)] for p in pts]


def _tex_diamonds_vnf(**_: object) -> tuple[list[list[float]], list[list[int]]]:
    verts: list[list[float]] = [
        [0, 1, 1],
        [0.5, 1, 0],
        [1, 1, 1],
        [0, 0.5, 0],
        [0.5, 0.5, 1],
        [1, 0.5, 0],
        [0, 0, 1],
        [0.5, 0, 0],
        [1, 0, 1],
    ]
    faces = [
        [0, 1, 3],
        [2, 5, 1],
        [8, 7, 5],
        [6, 3, 7],
        [1, 5, 4],
        [5, 7, 4],
        [7, 3, 4],
        [4, 3, 1],
    ]
    return verts, faces


def _tex_pyramids_vnf(**_: object) -> tuple[list[list[float]], list[list[int]]]:
    verts: list[list[float]] = [[0, 1, 0], [1, 1, 0], [0.5, 0.5, 1], [0, 0, 0], [1, 0, 0]]
    faces = [[2, 0, 1], [2, 1, 4], [2, 4, 3], [2, 3, 0]]
    return verts, faces


def _tex_trunc_pyramids_vnf(border: float | None = None, **_: object) -> tuple[list[list[float]], list[list[int]]]:
    b = border if border is not None else 0.1
    assert 0 < b < 0.5, "trunc_pyramids_vnf texture requires border in (0, 0.5)."
    verts = _sq(1) + _mv([0.5, 0.5, 1], _rect(1 - 2 * b, 1 - 2 * b))
    faces = [[i, (i + 1) % 4, (i + 1) % 4 + 4, i + 4] for i in range(4)] + [[4, 5, 6, 7]]
    return verts, faces


def _tex_cubes_vnf(**_: object) -> tuple[list[list[float]], list[list[int]]]:
    verts = [
        [0, 1, 0.5],
        [1, 1, 0.5],
        [0.5, 5 / 6, 1],
        [0, 4 / 6, 0],
        [1, 4 / 6, 0],
        [0.5, 3 / 6, 0.5],
        [0, 2 / 6, 1],
        [1, 2 / 6, 1],
        [0.5, 1 / 6, 0],
        [0, 0, 0.5],
        [1, 0, 0.5],
    ]
    faces = [
        [0, 1, 2],
        [0, 2, 3],
        [1, 4, 2],
        [2, 5, 3],
        [2, 4, 5],
        [6, 3, 5],
        [4, 7, 5],
        [7, 8, 5],
        [6, 5, 8],
        [10, 8, 7],
        [9, 6, 8],
        [10, 9, 8],
    ]
    return verts, faces


def _tex_trunc_ribs_vnf(
    border: float | None = None, gap: float | None = None, **_: object
) -> tuple[list[list[float]], list[list[int]]]:
    b = (border if border is not None else 0.25) * 2
    g = gap if gap is not None else 0.25
    assert b >= 0 and g >= 0, "trunc_ribs_vnf requires gap>=0 and border>=0."
    assert g + b <= 1, "trunc_ribs_vnf requires 2*border+gap <= 1."
    verts = _mv([0.5, 0.5], _rect(1 - g, 1, 0)) + _mv([0.5, 0.5], _rect(1 - g - b, 1, 1)) + _sq(1)
    faces = [[4, 7, 3, 0], [1, 2, 6, 5]]
    if g + b < 1 - 1e-9:
        faces.append([4, 5, 6, 7])
    if g > 1e-9:
        faces += [[1, 9, 10, 2], [0, 3, 11, 8]]
    return verts, faces


def _tex_bricks_vnf(
    border: float | None = None, gap: float | None = None, **_: object
) -> tuple[list[list[float]], list[list[int]]]:
    b = border if border is not None else 0.05
    g = gap if gap is not None else 0.05
    assert b >= 0 and g > 0 and g + b < 0.5, "bricks_vnf requires border>=0, gap>0, gap+border<0.5."
    verts = (
        _sqr(1)
        + _mv([g / 2, g / 2, 0], _sqr([1 - g, 0.5 - g]))
        + _mv([g / 2 + b / 2, g / 2 + b / 2, 1], _sqr([1 - g - b, 0.5 - g - b]))
        + _mv([0, 0.5 + g / 2, 0], _sqr([0.5 - g / 2, 0.5 - g]))
        + _mv([0, 0.5 + g / 2 + b / 2, 1], _sqr([0.5 - g / 2 - b / 2, 0.5 - g - b]))
        + _mv([0.5 + g / 2, 0.5 + g / 2, 0], _sqr([0.5 - g / 2, 0.5 - g]))
        + _mv(
            [0.5 + g / 2 + b / 2, 0.5 + g / 2 + b / 2, 1],
            _sqr([0.5 - g / 2 - b / 2, 0.5 - g - b]),
        )
    )
    faces = [
        [0, 4, 7, 20],
        [4, 8, 11, 7],
        [9, 8, 4, 5],
        [4, 0, 1, 5],
        [10, 9, 5, 6],
        [20, 7, 6, 13, 12, 21],
        [2, 3, 23, 22, 15, 14],
        [15, 19, 18, 14],
        [22, 23, 27, 26],
        [16, 19, 15, 12],
        [13, 6, 5, 1],
        [26, 25, 21, 22],
        [8, 9, 10, 11],
        [7, 11, 10, 6],
        [17, 16, 12, 13],
        [22, 21, 12, 15],
        [16, 17, 18, 19],
        [24, 25, 26, 27],
        [25, 24, 20, 21],
    ]
    return verts, faces


def _tex_checkers_vnf(border: float | None = None, **_: object) -> tuple[list[list[float]], list[list[int]]]:
    b = border if border is not None else 0.05
    assert 0 < b < 0.5, "checkers texture requires border in (0, 0.5)."
    verts = (
        _mv([0, 0], _sqr(0.5 - b, 1))
        + _mv([0, 0.5], _sqr(0.5 - b))
        + _mv([0.5, 0], _sqr(0.5 - b))
        + _mv([0.5, 0.5], _sqr(0.5 - b, 1))
        + [
            [0.5 - b / 2, 0.5 - b / 2, 0.5],
            [0, 1, 1],
            [0.5 - b, 1, 1],
            [0.5, 1, 0],
            [1 - b, 1, 0],
            [1, 0, 1],
            [1, 0.5 - b, 1],
            [1, 0.5, 0],
            [1, 1 - b, 0],
            [1, 1, 1],
            [0.5 - b / 2, 1 - b / 2, 0.5],
            [1 - b / 2, 1 - b / 2, 0.5],
            [1 - b / 2, 0.5 - b / 2, 0.5],
        ]
    )
    faces = [[i, i + 1, i + 2, i + 3] for i in (0, 4, 8, 12)] + [
        [10, 16, 13, 12, 28, 11],
        [9, 0, 3, 16, 10],
        [11, 28, 22, 21, 8],
        [4, 7, 26, 14, 13, 16],
        [7, 6, 17, 18, 26],
        [5, 4, 16, 3, 2],
        [19, 20, 27, 15, 14, 26],
        [20, 25, 27],
        [19, 26, 18],
        [23, 28, 12, 15, 27, 24],
        [23, 22, 28],
        [24, 27, 25],
    ]
    return verts, faces


def _tex_trunc_diamonds_vnf(border: float | None = None, **_: object) -> tuple[list[list[float]], list[list[int]]]:
    b = (border if border is not None else 0.1) / math.sqrt(2) * 2
    assert 0 < b < 0.5, "trunc_diamonds texture requires border in (0, 0.5/sqrt(2))."
    diameter1 = [[p[0], p[1], 0.0] for p in _circle_xy(1, 4)]
    diameter2 = [[p[0], p[1], 0.0] for p in _circle_xy(1 - b * 2, 4)]
    verts = _mv([0.5, 0.5, 0], diameter1) + _mv([0.5, 0.5, 1], diameter2)
    for a in (0, 90, 180, 270):
        verts += _mv([0.5, 0.5], _zrot2([[0.5, b, 1], [b, 0.5, 1], [0.5, 0.5, 1]], -a))
    faces = []
    for i in range(4):
        j = i * 3 + 8
        faces += [
            [i, (i + 1) % 4, (i + 1) % 4 + 4, i + 4],
            [j, j + 1, j + 2],
            [i, (i + 3) % 4, j + 1, j],
        ]
    faces.append([4, 5, 6, 7])
    return verts, faces


def _tex_tri_grid_vnf(border: float | None = None, **_: object) -> tuple[list[list[float]], list[list[int]]]:
    b = (border if border is not None else 0.05) * math.sqrt(3)
    assert 0 < b < math.sqrt(3) / 6, "tri_grid texture requires border in (0, 1/6)."
    adj = b / math.tan(math.radians(30))  # opp_ang_to_adj(border, 30)
    y1 = b / math.tan(math.radians(60))  # border / adj_ang_to_opp(1, 60)
    y2, y3, y4, y5, y6 = 2 * y1, 0.5 - y1, 0.5 + y1, 1 - 2 * y1, 1 - y1
    verts: list[list[float]] = [
        [0, 0, 0],
        [1, 0, 0],
        [adj, y1, 1],
        [1 - adj, y1, 1],
        [0, y2, 1],
        [1, y2, 1],
        [0.5, 0.5 - y2, 1],
        [0, y3, 1],
        [0.5 - adj, y3, 1],
        [0.5 + adj, y3, 1],
        [1, y3, 1],
        [0, 0.5, 0],
        [0.5, 0.5, 0],
        [1, 0.5, 0],
        [0, y4, 1],
        [0.5 - adj, y4, 1],
        [0.5 + adj, y4, 1],
        [1, y4, 1],
        [0.5, 0.5 + y2, 1],
        [0, y5, 1],
        [1, y5, 1],
        [adj, y6, 1],
        [1 - adj, y6, 1],
        [0, 1, 0],
        [1, 1, 0],
    ]
    faces = [
        [0, 2, 3, 1],
        [21, 23, 24, 22],
        [2, 6, 3],
        [0, 12, 6, 2],
        [1, 3, 6, 12],
        [0, 4, 8, 12],
        [4, 7, 8],
        [8, 7, 11, 12],
        [1, 12, 9, 5],
        [5, 9, 10],
        [10, 9, 12, 13],
        [11, 14, 15, 12],
        [19, 15, 14],
        [19, 23, 12, 15],
        [16, 17, 13, 12],
        [16, 20, 17],
        [12, 24, 20, 16],
        [21, 22, 18],
        [12, 23, 21, 18],
        [12, 18, 22, 24],
    ]
    return verts, faces


_TEX_FN_DEFAULT = 16  # BOSL2 _tex_fn_default()


def _circle_xy(d: float, n: int) -> list[list[float]]:
    """
    *n* points of a circle of diameter *d* centred at the origin, starting east (BOSL2
    circle()).
    """
    return [
        [
            d / 2 * math.cos(math.radians(360 * i / n)),
            d / 2 * math.sin(math.radians(360 * i / n)),
        ]
        for i in range(n)
    ]


def _square_pts(border: float) -> list[list[float]]:
    """The tile base: the unit square, subdivided to 8 points if *border*>0 else its 4 corners."""
    if border > 0:  # subdivide_path(square(1), refine=2)
        return [[0, 0], [0.5, 0], [1, 0], [1, 0.5], [1, 1], [0.5, 1], [0, 1], [0, 0.5]]
    return [[0, 0], [1, 0], [1, 1], [0, 1]]


def _sph(r: float, theta: float, phi: float) -> list[float]:
    """BOSL2 spherical_to_xyz(r, theta, phi)."""
    t, p = math.radians(theta), math.radians(phi)
    return [
        r * math.cos(t) * math.sin(p),
        r * math.sin(t) * math.sin(p),
        r * math.cos(p),
    ]


def _base_faces(n: int, base0: int, border: float) -> list[list[int]]:
    """The four faces joining a quarter of the *n*-point rim to each base-square region; *base0* is the
    index of the first base-square vertex (BOSL2's cones/dots base connection)."""
    out = []
    for i in range(4):
        arc = [j % n for j in range((i + 1) * n // 4, i * n // 4 - 1, -1)]
        if border > 0:
            out.append(
                arc
                + [
                    (2 * i + 7) % 8 + base0,
                    (2 * i) % 8 + base0,
                    (2 * i + 1) % 8 + base0,
                ]
            )
        else:
            out.append(arc + [i + base0])
    return out


def _tex_cones_vnf(
    fn: int | None = None, border: float | None = None, **_: object
) -> tuple[list[list[float]], list[list[int]]]:
    # BOSL2 defaults border=0, but a zero border leaves the tile's rim on the cell edge, which this
    # port's weld-and-close tiler can't seam watertight -- so default to a small positive border.
    b = border if border is not None else 0.05
    sides = quantup(fn, 4) if fn else _TEX_FN_DEFAULT
    assert 0 < b < 0.5, "this port's cones texture requires border in (0, 0.5)."
    rim = [[0.5 + x, 0.5 + y, 0.0] for x, y in _circle_xy(1 - 2 * b, sides)]
    verts = rim + [[0.5, 0.5, 1.0]] + [[x, y, 0.0] for x, y in _square_pts(b)]
    faces = [[i, (i + 1) % sides, sides] for i in range(sides)] + _base_faces(sides, sides + 1, b)
    return verts, faces


def _tex_dots_vnf(
    fn: int | None = None, border: float | None = None, **_: object
) -> tuple[list[list[float]], list[list[int]]]:
    b = border if border is not None else 0.05
    sides = quantup(fn, 4) if fn else _TEX_FN_DEFAULT
    assert 0 <= b < 0.5, "dots texture requires border in [0, 0.5)."
    rows = math.ceil(sides / 4)
    radius = (0.5 - b) / math.cos(math.radians(45))  # adj_ang_to_hyp(0.5-border, 45)
    cpz = -radius * math.sin(math.radians(45))
    sc = 1 / (radius - abs(cpz))
    uv = []
    for p in range(rows):
        phi = 45 - 45 * p / rows
        for ti in range(sides):
            s = _sph(radius, -360 * ti / sides, phi)
            uv.append([0.5 + s[0], 0.5 + s[1], cpz + s[2]])
    uv.append([0.5, 0.5, cpz + radius])  # dome apex
    uv += [[x, y, 0.0] for x, y in _square_pts(b)]
    verts = [[v[0], v[1], v[2] * sc] for v in uv]  # zscale(sc)
    faces = []
    for i in range(rows - 1):
        for j in range(sides):
            faces.append(
                [
                    i * sides + j,
                    i * sides + (j + 1) % sides,
                    (i + 1) * sides + (j + 1) % sides,
                    (i + 1) * sides + j,
                ]
            )
    for i in range(sides):
        faces.append([(rows - 1) * sides + i, (rows - 1) * sides + (i + 1) % sides, rows * sides])
    faces += _base_faces(sides, rows * sides + 1, b)
    return verts, faces


def _tex_hex_grid_vnf(border: float | None = None, **_: object) -> tuple[list[list[float]], list[list[int]]]:
    b = border if border is not None else 0.1
    assert 0 < b < 0.5, "hex_grid texture requires border in (0, 0.5)."
    diag = b / math.sin(math.radians(60))  # opp_ang_to_hyp(border, 60)
    hyp = 0.5 / math.cos(math.radians(30))  # adj_ang_to_hyp(0.5, 30)
    sc = 1 / 3 / hyp
    hex_ = [
        [1, 2 / 6, 0],
        [0.5, 1 / 6, 0],
        [0, 2 / 6, 0],
        [0, 4 / 6, 0],
        [0.5, 5 / 6, 0],
        [1, 4 / 6, 0],
    ]
    vertex_radius = (0.5 - b) / math.cos(math.radians(30))
    top = [
        [
            0.5 + vertex_radius * math.cos(math.radians(-30 + 60 * i)),
            0.5 + vertex_radius * math.sin(math.radians(-30 + 60 * i)) * sc,
            1.0,
        ]
        for i in range(6)
    ]

    def cyl(rad: float, angle: float) -> list[float]:  # yscale(sc, cylindrical_to_xyz(rad, angle, 1))
        return [
            rad * math.cos(math.radians(angle)),
            rad * math.sin(math.radians(angle)) * sc,
            1.0,
        ]

    def add(a: list[float], b3: list[float]) -> list[float]:
        return [a[0] + b3[0], a[1] + b3[1], a[2] + b3[2]]

    verts = (
        [list(height) for height in hex_]
        + top
        + [
            add(hex_[0], [0, -diag * sc, 1]),
            add(hex_[1], cyl(diag, 270 + 60)),
            add(hex_[1], cyl(diag, 270 - 60)),
            add(hex_[2], [0, -diag * sc, 1]),
            [0, 0, 1],
            [0.5 - b, 0, 1],
            [0.5, 0, 0],
            [0.5 + b, 0, 1],
            [1, 0, 1],
            add(hex_[3], [0, diag * sc, 1]),
            add(hex_[4], cyl(diag, 90 + 60)),
            add(hex_[4], cyl(diag, 90 - 60)),
            add(hex_[5], [0, diag * sc, 1]),
            [0, 1, 1],
            [0.5 - b, 1, 1],
            [0.5, 1, 0],
            [0.5 + b, 1, 1],
            [1, 1, 1],
        ]
    )
    faces = [[6, 7, 8, 9, 10, 11]]
    faces += [[i, (i + 1) % 6, (i + 1) % 6 + 6, i + 6] for i in range(6)]
    faces += [
        [20, 19, 13, 12],
        [17, 16, 15, 14],
        [21, 25, 26, 22],
        [23, 28, 29, 24],
        [0, 12, 13, 1],
        [1, 14, 15, 2],
        [3, 21, 22, 4],
        [4, 23, 24, 5],
        [1, 13, 19, 18],
        [1, 18, 17, 14],
        [4, 22, 26, 27],
        [4, 27, 28, 23],
    ]
    return verts, faces


# name -> (builder, kind) where kind is "heightfield" or "vnf"
TEXTURES: dict[str, tuple[Callable[..., list[list[float]] | tuple[list[list[float]], list[list[int]]]], str]] = {
    "ribs": (_tex_ribs, "heightfield"),
    "trunc_ribs": (_tex_trunc_ribs, "heightfield"),
    "wave_ribs": (_tex_wave_ribs, "heightfield"),
    "diamonds": (_tex_diamonds, "heightfield"),
    "pyramids": (_tex_pyramids, "heightfield"),
    "trunc_pyramids": (_tex_trunc_pyramids, "heightfield"),
    "hills": (_tex_hills, "heightfield"),
    "bricks": (_tex_bricks, "heightfield"),
    "rough": (_tex_rough, "heightfield"),
    "diamonds_vnf": (_tex_diamonds_vnf, "vnf"),
    "pyramids_vnf": (_tex_pyramids_vnf, "vnf"),
    "trunc_pyramids_vnf": (_tex_trunc_pyramids_vnf, "vnf"),
    "cubes": (_tex_cubes_vnf, "vnf"),
    "trunc_ribs_vnf": (_tex_trunc_ribs_vnf, "vnf"),
    "cones": (_tex_cones_vnf, "vnf"),
    "dots": (_tex_dots_vnf, "vnf"),
    "hex_grid": (_tex_hex_grid_vnf, "vnf"),
    "bricks_vnf": (_tex_bricks_vnf, "vnf"),
    "checkers": (_tex_checkers_vnf, "vnf"),
    "trunc_diamonds": (_tex_trunc_diamonds_vnf, "vnf"),
    "tri_grid": (_tex_tri_grid_vnf, "vnf"),
}


class TextureType(Enum):
    RIBS = "ribs"
    TRUNC_RIBS = "trunc_ribs"
    WAVE_RIBS = "wave_ribs"
    DIAMONDS = "diamonds"
    PYRAMIDS = "pyramids"
    TRUNC_PYRAMIDS = "trunc_pyramids"
    HILLS = "hills"
    BRICKS = "bricks"
    ROUGH = "rough"
    DIAMONDS_VNF = "diamonds_vnf"
    PYRAMIDS_VNF = "pyramids_vnf"
    TRUNC_PYRAMIDS_VNF = "trunc_pyramids_vnf"
    CUBES = "cubes"
    TRUNC_RIBS_VNF = "trunc_ribs_vnf"
    CONES = "cones"
    DOTS = "dots"
    HEX_GRID = "hex_grid"
    BRICKS_VNF = "bricks_vnf"
    CHECKERS = "checkers"
    TRUNC_DIAMONDS = "trunc_diamonds"
    TRI_GRID = "tri_grid"


def texture(
    tex: str | TextureType,
    sides: int | None = None,
    border: float | None = None,
    gap: float | None = None,
    roughness: float | None = None,
    inset: float | None = None,
    fn: int | None = None,
) -> list[list[float]] | tuple[list[list[float]], list[list[int]]]:
    """The named texture *tex* -- a height-field array or a VNF tile ``(verts, faces)`` (BOSL2 texture()).

    *sides* sets the resolution of the parametric height-field textures; *border*/*gap* shape the VNF-tile
    textures; *roughness* perturbs ``bricks``. Pass a name from :data:`TEXTURES`. See the module
    docstring for which textures are ported.

    Returns
         list[list[float]]:
            The named texture *tex* -- a height-field array or a VNF tile ``(verts, faces)`` (BOSL2 texture()).

    Raises
        ValueError: If the texture name is not found or if both 'border' and 'inset' are provided.

    See Also
        pybosl2.paths.Path2D.texture()
        pybosl2.paths.Path2D.texture_v()
        pybosl2.shapes3d.Bosl2Solid.texture()
        pybosl2.shapes3d.Bosl2Solid.texture_v()
    """
    if inset is not None and border is not None:
        raise ValueError("texture(): give 'border' or 'inset', not both.")
    if inset is not None:
        border = inset
    key = tex.value if isinstance(tex, TextureType) else tex
    if key not in TEXTURES:
        raise ValueError(f"Unrecognized (or unported) texture name: {key!r}; available: {sorted(TEXTURES)}")
    builder, _kind = TEXTURES[key]
    return builder(sides=sides, border=border, gap=gap, roughness=roughness, fn=fn)


def _weld(
    verts: list[list[float]], faces: list[list[int]], tol: float = 1e-6
) -> tuple[list[list[float]], list[list[int]]]:
    """
    Merge coincident vertices (so tiled cells stitch along shared edges); drop degenerate faces.
    """
    idx: dict[tuple[int, int, int], int] = {}
    new_verts: list[list[float]] = []
    remap: list[int] = []
    for p in verts:
        k = (round(p[0] / tol), round(p[1] / tol), round(p[2] / tol))
        if k not in idx:
            idx[k] = len(new_verts)
            new_verts.append([float(p[0]), float(p[1]), float(p[2])])
        remap.append(idx[k])
    new_faces = [[remap[i] for i in f] for f in faces]
    new_faces = [f for f in new_faces if len({*f}) >= 3]
    return new_verts, new_faces


def _close_to_base(
    verts: list[list[float]], faces: list[list[int]], bottom: float
) -> tuple[list[list[float]], list[list[int]]]:
    """Close an open (top-only) surface into a solid by dropping its boundary loops to z=*bottom*
    with side walls and a flat bottom cap."""
    verts = [list(p) for p in verts]
    faces = [list(f) for f in faces]
    halfedges = set()
    for f in faces:
        for i in range(len(f)):
            halfedges.add((f[i], f[(i + 1) % len(f)]))
    nxt = {a: b for (a, b) in halfedges if (b, a) not in halfedges}  # boundary half-edges, directed
    visited = set()
    for start in list(nxt):
        if start in visited:
            continue
        loop, a = [], start
        while a in nxt and a not in visited:
            visited.add(a)
            loop.append(a)
            a = nxt[a]
        if len(loop) < 3:
            continue
        base = {}
        for vi in loop:
            base[vi] = len(verts)
            verts.append([verts[vi][0], verts[vi][1], bottom])
        nloop = len(loop)
        for k in range(nloop):  # side walls
            a, b = loop[k], loop[(k + 1) % nloop]
            faces.append([a, b, base[b], base[a]])
        bl = [base[vi] for vi in loop]  # bottom cap (fan, faces down)
        for k in range(1, nloop - 1):
            faces.append([bl[0], bl[k + 1], bl[k]])
    return verts, faces


def is_watertight_topology(verts: list[list[float]], faces: list[list[int]]) -> bool:
    """
    True if every undirected edge of *faces* is shared by exactly two faces (a closed manifold).
    """
    _ = verts
    from collections import Counter

    e: Counter[frozenset[int]] = Counter()
    for f in faces:
        for i in range(len(f)):
            e[frozenset((f[i], f[(i + 1) % len(f)]))] += 1
    return bool(e) and all(c == 2 for c in e.values())


def rasterize_vnf_texture(verts: list[list[float]], faces: list[list[int]], sides: int = 24) -> list[list[float]]:
    """Sample a VNF texture tile's top surface to an *sides* x *sides* height-field over ``[0,1]x[0,1]``.

    A robust fallback for VNF tiles whose exact geometry can't be tiled watertight (pinch points,
    interior holes): the top (max-z) surface is captured; overhangs/undercuts are flattened.
    """
    verts_arr = np.asarray([[float(p[0]), float(p[1]), float(p[2])] for p in verts])
    tris = [[f[0], f[k], f[k + 1]] for f in faces for k in range(1, len(f) - 1)]
    tris_arr = np.asarray(tris)
    tri_a, tri_b, tri_c = verts_arr[tris_arr[:, 0]], verts_arr[tris_arr[:, 1]], verts_arr[tris_arr[:, 2]]
    ax, ay = tri_a[:, 0], tri_a[:, 1]
    bx, by = tri_b[:, 0], tri_b[:, 1]
    cx, cy = tri_c[:, 0], tri_c[:, 1]
    den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    den = np.where(np.abs(den) < 1e-12, 1e-12, den)
    heightmap = [[0.0] * sides for _ in range(sides)]
    for gy in range(sides):
        vy = (gy + 0.5) / sides
        for gx in range(sides):
            ux = (gx + 0.5) / sides
            l1 = ((by - cy) * (ux - cx) + (cx - bx) * (vy - cy)) / den
            l2 = ((cy - ay) * (ux - cx) + (ax - cx) * (vy - cy)) / den
            l3 = 1 - l1 - l2
            inside = (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
            if inside.any():
                z = l1 * tri_a[:, 2] + l2 * tri_b[:, 2] + l3 * tri_c[:, 2]
                heightmap[gy][gx] = float(z[inside].max())
    return heightmap


def vnf_tile_to_solid(
    verts: list[list[float]],
    faces: list[list[int]],
    size: Sequence[float],
    reps: Sequence[int],
    tex_depth: float = 1.0,
    inset: float = 0.0,
) -> tuple[list[list[float]], list[list[int]]]:
    """Tile a VNF texture cell over a *size* ``[x, y]`` rectangle *reps* ``[nx, ny]`` times and close
    it into a watertight solid. Returns ``(verts, faces)`` for a polyhedron."""
    sx, sy = float(size[0]), float(size[1])
    nx, ny = int(reps[0]), int(reps[1])
    v: list[list[float]] = []
    f: list[list[int]] = []
    for i in range(nx):
        for j in range(ny):
            off = len(v)
            for vx, vy, vz in verts:
                v.append([(i + vx) / nx * sx, (j + vy) / ny * sy, (vz - inset) * tex_depth])
            for face in faces:
                f.append([off + k for k in face])
    v, f = _weld(v, f)
    bottom = min(p[2] for p in v) - 0.1
    return _close_to_base(v, f, bottom)


def is_heightfield_texture(tex: list[list[float]] | tuple[list[list[float]], list[list[int]]]) -> bool:
    """True if *tex* is a height-field: a 2-D array whose entries are plain numbers."""
    try:
        row = tex[0]
        return not isinstance(row[0], (list, tuple, np.ndarray))
    except (TypeError, IndexError):
        return False


def is_vnf_texture(tex: object) -> bool:
    """True if *tex* is a VNF tile: ``(verts, faces)`` with verts a list of 3-vectors."""
    try:
        verts: Any
        faces: Any
        verts, faces = tex  # type: ignore[misc]
        return len(verts[0]) == 3 and hasattr(faces[0], "__len__")
    except (TypeError, ValueError, IndexError):
        return False

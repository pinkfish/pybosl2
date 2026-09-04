# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Textures as distance fields, built from the same tile the CSG backend meshes (SPEC PAR-4).

The CSG backend does not have a "texture" primitive either. `textured_cylinder_vnf` reduces every
texture -- a named height field, a rasterised VNF tile, or a caller's own array -- to one thing: a
2-D grid of heights in 0..1 (`pybosl2.textures.height_field`). It then places a vertex per grid
cell, pushed out radially by ``depth * h``. So the texture is *already* a sampled displacement map
before either backend sees it, and building a field from that map is not the lossy mesh-to-field
conversion SPEC B-5 forbids -- no backend is crossed, and nothing is approximated that the CSG
path does not approximate identically.

What differs is how the map is *evaluated*. A mesh reads it at vertices; a field has to answer at
every point, which means the lookup itself becomes part of the expression. Two things make that
affordable:

* **The tile is folded, not unrolled.** A texture repeating 20 times around and 4 along would be a
  480-column grid if written out. It is periodic, so the coordinate is folded back into one tile
  instead -- `atan2(-sin(n*theta), -cos(n*theta))` recovers `frac(n*theta / 2pi)` exactly, and
  `sin`/`cos` of a multiple angle come from the Chebyshev recurrence on `x/r` and `y/r`. The tree
  is then the size of the *tile*, whatever the repeat counts are.
* **Interpolation is a sum of hats.** `max(0, 1 - |t - c|)` is a triangular basis function, so
  `sum(h[c] * hat(t - c))` is plain linear interpolation with no comparison operator -- which
  matters, because libfive gives us `min`/`max`/`abs` and no `if`. Cells whose height is zero
  contribute nothing and are skipped.

The result is bilinear where the mesh is piecewise-linear over triangles, so the two agree
*exactly at the grid points* and differ only in how they fill the space between -- which is the
same kind of difference as tessellation, and the thing `tests/test_sdf_texture.py` checks.

The surface is displaced radially rather than along its own normal, so the field is not a true
Euclidean distance on a tapered cone -- the same caveat `prismoid` and the oblique cone already
carry, and for the same reason: the zero set is exact and that is what gets meshed.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pybosl2.exceptions import Bosl2ValueError
from pybosl2.sdf._libfive import LVTree, lv

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["textured_cyl_sdf", "tile_budget"]

#: How many tile cells the lookup may cost. Every cell is two multiplies and an add in the
#: expression tree, so a 33x33 tile is already a few thousand nodes; past that a field stops being
#: the cheap thing it is meant to be. The largest tile in the registry is `rough` at 32x32, so no
#: named texture reaches this -- it exists for a caller's own array (SPEC S-34 allows one).
CELL_BUDGET = 1600


def tile_budget(rows: int, columns: int) -> None:
    """Refuse a tile too large to express, naming what to do instead.

    Args:
        rows: Rows in the texture tile.
        columns: Columns in the texture tile.

    Raises:
        Bosl2ValueError: if the tile exceeds :data:`CELL_BUDGET`.

    """
    if rows * columns > CELL_BUDGET:
        raise Bosl2ValueError(
            f"texture=: a {rows}x{columns} tile is {rows * columns} cells, past the {CELL_BUDGET} "
            f"this backend can express as a field. Every cell becomes nodes in the expression, so "
            f"a tile this size stops being cheap to evaluate. Coarsen the tile, or build it "
            f'inside `with use_backend("csg")` where it is meshed rather than evaluated.'
        )


def _fold(sin_t: LVTree, cos_t: LVTree) -> LVTree:
    """Return ``frac(t)`` from ``sin(2*pi*t)`` and ``cos(2*pi*t)``.

    `atan2` is the only operator here that inverts a periodic function, and it lands in
    ``(-pi, pi]``. Negating both arguments shifts by half a turn, which puts ``t = 0`` at the end
    of the range rather than its middle -- so the result runs ``0 -> 1`` across one tile instead
    of ``0.5 -> 1, 0 -> 0.5``. ``t = 0`` comes back as ``1.0``, which is the same cell as ``0``
    because the closing row and column repeat the first.

    Args:
        sin_t: ``sin(2*pi*t)`` as an expression.
        cos_t: ``cos(2*pi*t)`` as an expression.

    Returns:
        The fractional part of *t*, in ``[0, 1]``.

    """
    return lv.atan2(-sin_t, -cos_t) / (2.0 * math.pi) + 0.5


def _multiple_angle(cos_t: LVTree, sin_t: LVTree, n: int) -> "tuple[LVTree, LVTree]":
    """Return ``(cos(n*t), sin(n*t))`` from ``cos(t)`` and ``sin(t)``, by Chebyshev recurrence.

    ``lv.cos`` cannot be used here: the angle is `atan2(y, x)`, and taking its cosine back would
    be a round trip through a function we are trying to avoid. The recurrence needs only
    multiplication, and *n* is the repeat count -- a small integer.

    Args:
        cos_t: ``cos(t)``, i.e. ``x / r``.
        sin_t: ``sin(t)``, i.e. ``y / r``.
        n: The multiple, at least 1.

    Returns:
        The pair ``(cos(n*t), sin(n*t))``.

    """
    cos_k, cos_prev = cos_t, 1.0
    sin_k, sin_prev = sin_t, 0.0
    for _ in range(n - 1):
        cos_k, cos_prev = 2.0 * cos_t * cos_k - cos_prev, cos_k
        sin_k, sin_prev = 2.0 * cos_t * sin_k - sin_prev, sin_k
    return cos_k, sin_k


def _hat(t: LVTree, i: int) -> LVTree:
    """Return the triangular basis function centred on *i*: 1 at ``t == i``, 0 a cell away.

    Args:
        t: The coordinate, in cells.
        i: Which cell this hat is centred on.

    Returns:
        ``max(0, 1 - |t - i|)``.

    """
    return lv.max(0.0, 1.0 - lv.abs(t - float(i)))


def _interpolate(field: "Sequence[Sequence[float]]", u: LVTree, v: LVTree) -> LVTree:
    """Return the tile's height at ``(u, v)``, bilinearly, as an expression.

    Both coordinates are in cells and already folded into one tile, so the closing row and column
    repeat the first -- which is what makes the interpolation wrap.

    Cells whose height is zero are skipped: they contribute nothing to the sum, and textures are
    mostly flat, so this is most of them. `ribs` goes from four products to two.

    Args:
        field: The tile, rows of heights in 0..1.
        u: The column coordinate, in ``[0, columns]``.
        v: The row coordinate, in ``[0, rows]``.

    Returns:
        The interpolated height.

    """
    rows, columns = len(field), len(field[0])
    hats_u = [_hat(u, c) for c in range(columns + 1)]
    total: LVTree = 0.0
    for r in range(rows + 1):
        row = field[r % rows]
        terms = [float(row[c % columns]) * hats_u[c] for c in range(columns + 1) if row[c % columns]]
        if terms:
            row_sum: LVTree = terms[0]
            for term in terms[1:]:
                row_sum = row_sum + term
            total = total + row_sum * _hat(v, r)
    return total


def textured_cyl_sdf(
    x: LVTree,
    y: LVTree,
    z: LVTree,
    height: float,
    radius1: float,
    radius2: float,
    field: "Sequence[Sequence[float]]",
    reps_around: int,
    reps_along: int,
    depth: float,
    inset: float,
) -> LVTree:
    """Return the field of a cylinder whose side is displaced by *field* (SPEC S-34, PAR-4).

    The surface sits at ``base(v) - inset + depth * h(u, v)``, which is the radius the CSG
    backend's `textured_cylinder_vnf` puts its vertices at, evaluated for every point rather than
    at sample points.

    Args:
        x: The x coordinate.
        y: The y coordinate.
        z: The z coordinate.
        height: Height of the cylinder, spanning ``-height/2 .. height/2``.
        radius1: Radius at the bottom.
        radius2: Radius at the top.
        field: One texture tile, rows of heights in 0..1.
        reps_around: How many times the tile repeats around the cylinder.
        reps_along: How many times it repeats along it.
        depth: How far the texture displaces the surface. Negative sinks it in.
        inset: How far the surface is sunk before the texture is added.

    Returns:
        The distance field, as an expression.

    """
    rows, columns = len(field), len(field[0])
    tile_budget(rows, columns)

    half = height / 2.0
    radial = lv.sqrt(lv.square(x) + lv.square(y))
    # `radial` is zero on the axis, where cos/sin of the angle are undefined. Nudging the divisor
    # keeps the expression finite there; the point is inside the solid by a wide margin, so the
    # texture's value at it cannot move the surface.
    safe = lv.max(radial, 1e-9)
    cos_n, sin_n = _multiple_angle(x / safe, y / safe, max(1, reps_around))
    u = _fold(sin_n, cos_n) * columns

    fraction = (z + half) / height
    angle = 2.0 * math.pi * max(1, reps_along) * fraction
    v = _fold(lv.sin(angle), lv.cos(angle)) * rows

    base = radius1 + (radius2 - radius1) * fraction
    surface = base - inset + depth * _interpolate(field, u, v)
    return lv.max(radial - surface, lv.abs(z) - half)

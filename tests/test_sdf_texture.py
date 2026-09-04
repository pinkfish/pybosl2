# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A texture is the same surface on both backends, meshed on one and evaluated on the other.

SPEC PAR-4 and PAR-5. `texture=` and its four companions were 25 of the 176 option gaps, and the
reason they looked hard is that the CSG backend builds them as a mesh. It does not, quite:
`textured_cylinder_vnf` first reduces every texture -- a named height field, a rasterised VNF
tile, or a caller's own array -- to a 2-D grid of heights, then places a vertex per cell pushed
out radially. The displacement map exists before either backend sees it, so building a field from
it crosses nothing and approximates nothing the CSG path does not approximate identically (B-5).

The claim these tests make is exact and checkable: **the SDF field is zero at every vertex the CSG
mesh is built from.** Not close, zero -- the two read the same tile with the same repeat counts and
the same radius formula. Where they differ is between the sample points, which is the same kind of
difference as tessellation and what PAR-5 already allows.
"""

from __future__ import annotations

import math

import pytest

import pybosl2.sdf.shapes3d as sdf
from pybosl2.sdf._libfive import lv
from pybosl2.textures import TEXTURES, height_field, texture_grid

#: Local ``(x, y, z)`` to world, for each axis -- the rotations `xcyl` and `ycyl` apply to a `cyl`
#: on the CSG side (90 degrees about Y, and -90 about X). The SDF backend does not rotate anything;
#: it reads `_AXIS_LEAN` backwards to put the angle in the cylinder's own frame. These two ways of
#: saying one rotation are what this file cross-checks.
TO_WORLD = {
    0: lambda lx, ly, lz: (lz, ly, -lx),
    1: lambda lx, ly, lz: (lx, lz, -ly),
    2: lambda lx, ly, lz: (lx, ly, lz),
}


def _worst_at_mesh_vertices(
    builder,
    axis: int,
    texture: str,
    *,
    height: float = 20.0,
    radius1: float = 8.0,
    radius2: float | None = None,
    reps: tuple[int, int] = (6, 2),
    depth: float = 1.2,
    inset: float = 0.4,
    budget: int = 16,
    let_it_decide: bool = False,
) -> float:
    """Return the largest |field| at the vertices the CSG mesh would be built from.

    Sampled on a stride rather than exhaustively: the field is a Python closure tree here (no
    libfive in this environment), so a 24x24 tile costs ~600 closure calls *per point* and
    checking every one of a few thousand vertices takes minutes. The stride keeps roughly *budget*
    points whatever the grid's size, so a big tile is covered as widely as a small one and no
    texture is quietly skipped. Coverage rather than exhaustiveness is enough here because the
    quantity being checked is not noisy: the two constructions either read the same tile at the
    same coordinate or they do not, and a wrong one is wrong at every vertex, not a few.
    """
    radius2 = radius1 if radius2 is None else radius2
    field = height_field(texture)
    grid = texture_grid(field, reps_around=reps[0], reps_along=reps[1])
    rows, columns = len(grid), len(grid[0])
    shape = builder(
        height=height,
        radius1=radius1,
        radius2=radius2,
        texture=texture,
        tex_depth=depth,
        tex_inset=inset,
        anchor=[0, 0, 0],
        **({} if let_it_decide else {"tex_reps": list(reps)}),
    )
    tree = shape._sdf_fn(lv.x(), lv.y(), lv.z())

    # The first and last rows sit on the rims, where the slab term is zero whatever the texture
    # does -- they would report a pass for the wrong reason, so they are skipped and the sampling
    # is required to have found something without them. An earlier version did not check that,
    # and the undecorated case (a one-row tile repeated once along, so a two-row grid and no
    # interior rows at all) sampled *nothing* and passed with the backend's default replaced.
    stride = max(1, math.isqrt(max(1, (rows * columns) // budget)))
    sampled = 0
    worst = 0.0
    for row in range(1, rows - 1, stride):
        fraction = row / (rows - 1)
        local_z = -height / 2.0 + fraction * height
        base = radius1 + (radius2 - radius1) * fraction
        for column in range(0, columns, stride):
            angle = 2.0 * math.pi * column / columns
            r = base - inset + grid[row][column] * depth
            point = TO_WORLD[axis](r * math.cos(angle), r * math.sin(angle), local_z)
            worst = max(worst, abs(float(tree(*point))))
            sampled += 1
    if sampled < 4:
        raise AssertionError(
            f"only {sampled} vertices to check on a {rows}x{columns} grid -- this measures "
            f"nothing. Give the case a texture or a repeat count with rows between the rims."
        )
    return worst


@pytest.mark.parametrize("texture", sorted(TEXTURES))
def test_the_field_is_zero_where_the_mesh_puts_a_vertex(texture: str) -> None:
    """Every texture in the registry, height fields and rasterised VNF tiles alike (SPEC S-34).

    A caller passing `texture("dots")` and one passing `texture("ribs")` get the same treatment on
    this backend for the same reason they do on the other: both are a height grid by the time the
    surface is built, and neither backend has a "VNF texture" case.
    """
    worst = _worst_at_mesh_vertices(sdf.cyl, 2, texture)
    assert worst == pytest.approx(0.0, abs=1e-9), f"{texture}: worst |field| at a mesh vertex is {worst}"


@pytest.mark.parametrize(
    ("name", "axis"),
    [("cyl", 2), ("cylinder", 2), ("zcyl", 2), ("xcyl", 0), ("ycyl", 1)],
)
def test_a_turned_cylinder_wears_the_pattern_the_same_way_round(name: str, axis: int) -> None:
    """`xcyl` is a `cyl` turned, and the texture has to turn with it (SPEC PAR-4).

    On the CSG side that is literal -- `xcyl` builds a `cyl` and rotates the result. A field has
    nothing to rotate, so the angle is put into the cylinder's own frame instead, by reading
    `_AXIS_LEAN` backwards. It is the same table `shift=` reads forwards, which is the point: one
    rotation, written down once, rather than two derivations that can disagree.
    """
    worst = _worst_at_mesh_vertices(getattr(sdf, name), axis, "trunc_ribs")
    assert worst == pytest.approx(0.0, abs=1e-9), f"{name}: worst |field| at a mesh vertex is {worst}"


def test_the_frame_map_is_what_makes_the_turned_ones_line_up() -> None:
    """A negative control: the turned cylinders pass because of the map, not by symmetry.

    `trunc_ribs` varies around the cylinder and not along it, so swapping the two local axes moves
    every rib. Without this, `xcyl` and `ycyl` would pass with the map wrong on a texture that
    happened to be symmetric -- the same trap `shift=[3, 3]` set for `_AXIS_LEAN` itself.
    """
    from pybosl2.sdf.shapes3d import _AXIS_LEAN, _axis_local_xy

    swapped = ((_AXIS_LEAN[0][1]), (_AXIS_LEAN[0][0]))
    original = _AXIS_LEAN[0]
    _AXIS_LEAN[0] = swapped
    try:
        worst = _worst_at_mesh_vertices(sdf.xcyl, 0, "trunc_ribs")
    finally:
        _AXIS_LEAN[0] = original
    assert worst > 0.1, "swapping xcyl's two local axes did not move the texture -- the test is blind"
    assert _axis_local_xy(2, [1.0, 2.0]) == (1.0, 2.0), "the z axis is the identity"


@pytest.mark.parametrize("reps", [(8, 3), (13, 2), None])
def test_the_repeat_counts_are_resolved_in_one_place(reps: tuple[int, int] | None) -> None:
    """Including the case where neither is given, which is a decision rather than an error (D-4).

    "Repeat the tile so one comes out roughly square" was written twice for one turn -- once in
    the CSG `_textured_cyl` and once in the SDF one. That is how two backends come to answer the
    same undecorated call with two different surfaces, and it is the same duplication, in the same
    shape, that `center=` had (SPEC C-21). `pybosl2.textures.default_tex_reps` is the one place now.

    `reps=None` is the undecorated call: the builder is told nothing and has to reach that shared
    default, while the grid it is checked against is built from it directly. An earlier version of
    this test passed the counts explicitly in every case, including that one -- so it went green
    with the SDF backend's default replaced by `[1, 1]`, which is the whole thing it was there to
    catch. Planting the defect is what found that; running the test was not enough.
    """
    from pybosl2.textures import default_tex_reps

    decide = reps is None
    counts = tuple(default_tex_reps(20.0, 8.0, 8.0)) if decide else reps
    assert counts is not None
    # `diamonds` rather than `ribs`: the default repeats the tile once along, so a one-row tile
    # would leave a two-row grid with nothing between the rims to check.
    worst = _worst_at_mesh_vertices(sdf.cyl, 2, "diamonds", reps=counts, let_it_decide=decide)
    assert worst == pytest.approx(0.0, abs=1e-9), f"reps {counts}: worst |field| at a vertex is {worst}"


def test_the_bound_leaves_room_for_the_peaks() -> None:
    """An SDF shape's `bounds()` is a declaration, so a texture that grows the shape has to say so.

    The texture pushes the surface out by `tex_depth` past the plain radius; a bound left at the
    plain radius would clip the peaks off when the field is meshed. `tex_inset` pulls the surface
    in first, so it is the difference that matters.
    """
    from pybosl2 import solid as facade
    from pybosl2 import use_backend

    with use_backend("sdf"):
        plain = facade.cyl(height=20, radius=8).bounds().size[0]
        proud = facade.cyl(height=20, radius=8, texture="ribs", tex_reps=[8, 1], tex_depth=1.5).bounds().size[0]
        flush = (
            facade.cyl(height=20, radius=8, texture="ribs", tex_reps=[8, 1], tex_depth=1.5, tex_inset=True)
            .bounds()
            .size[0]
        )
    assert plain == pytest.approx(16.0)
    assert proud == pytest.approx(19.0), "the peaks stand 1.5 proud of the radius, on both sides"
    assert flush == pytest.approx(16.0), "an inset texture takes material out rather than adding it"


def test_a_tile_too_large_to_express_refuses_and_says_what_to_do() -> None:
    """The honest limit, named rather than met with a slow answer (SPEC B-9, E-5).

    Every tile cell becomes nodes in the expression tree, so the cost is the tile's, not the
    cylinder's -- which is why the repeats are folded rather than unrolled. Past a few thousand
    cells a field stops being the cheap thing it is meant to be. No named texture reaches this:
    the largest in the registry is `rough` at 32x32.
    """
    from pybosl2.exceptions import Bosl2ValueError
    from pybosl2.sdf.textures import CELL_BUDGET, tile_budget

    side = int(CELL_BUDGET**0.5)
    tile_budget(side, side)
    with pytest.raises(Bosl2ValueError, match="past the"):
        tile_budget(side * 2, side * 2)

    biggest = max(len(height_field(name)) * len(height_field(name)[0]) for name in TEXTURES)
    assert biggest <= CELL_BUDGET, f"a registry texture is {biggest} cells, over the {CELL_BUDGET} budget"


def test_folding_recovers_the_tile_coordinate_exactly() -> None:
    """The one piece of arithmetic the rest of the module rests on.

    There is no `mod` and no `floor` here -- only `min`, `max`, `abs` and the trig. `atan2` of the
    negated sine and cosine is what recovers `frac(t)`, and getting the half-turn shift wrong
    would slide every texture half a tile without changing anything else about it.
    """
    from pybosl2.sdf.textures import _fold

    for t in (0.125, 0.25, 0.5, 0.75, 0.9):
        angle = 2.0 * math.pi * t
        folded = float(_fold(lv.sin(angle), lv.cos(angle))(0.0, 0.0, 0.0))
        assert folded == pytest.approx(t, abs=1e-12), f"frac({t}) came back {folded}"
    # At exactly t = 0 the answer is 0 or 1 depending on the sign of the zero `sin` returns --
    # `atan2(-0.0, -1.0)` is -pi and `atan2(+0.0, -1.0)` is +pi. Both are right: the closing row
    # and column repeat the first, so either end of the range reads the same height. The tile
    # lookup has to be indifferent to that, and it is, which is why this asserts the pair.
    assert float(_fold(lv.sin(0.0), lv.cos(0.0))(0.0, 0.0, 0.0)) in (0.0, 1.0)

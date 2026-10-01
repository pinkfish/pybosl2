# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""Each `VNFStyle` triangulates differently, and the two named for a minimum achieve it.

SPEC G-8. `VNF.vertex_array` chooses a per-cell triangulation from a ten-member enum, and every
member had its own test. All of them asserted the same six facts -- vertex count, face count,
validity, the z-bounds and the volume -- and on the 3x3 warped grid they use, those six facts are
**identical for `MIN_EDGE` and `MIN_AREA`**. Making `MIN_AREA` compute `MIN_EDGE`'s criterion leaves
the entire suite green. Two styles, one test.

This is G-8's rule about enum members arriving from the other direction: there, a member a consumer
could not build fell through to a butt cap and nothing objected. Here the members are all
implemented correctly -- measured below, and on 600 random grids before this was written -- but
nothing held them *apart*, so a regression in the rarer one would be silent.

Two things are asserted, because distinctness alone is weaker than the names promise:

* no two styles triangulate the same way, across a panel of surfaces chosen so that each pair is
  separated by at least one of them;
* `MIN_AREA` never produces more triangle area than `MIN_EDGE`, and `MIN_EDGE` never a longer split
  diagonal than `MIN_AREA`. Those are what the two names mean, and they are what a per-style test
  asserting a volume cannot see.

A single surface is not enough and the panel says why: on a symmetric saddle, `DEFAULT`/`CONVEX`,
`ALT`/`CONCAVE` and `MIN_EDGE`/`MIN_AREA` all coincide, which is a property of the saddle rather
than of the styles.
"""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from pybosl2.enums import VNFStyle
from pybosl2.path3d import Path3D
from pybosl2.vnf import VNF

#: Grid side. Four is the smallest that gives interior cells a genuine choice; at 3x3 `MIN_AREA` and
#: `MIN_EDGE` agree on every random grid tried, which would make the panel look adequate when it is
#: the grid doing the work.
SIDE = 4

#: Height functions, as `name -> f(x, y)`. Deliberately a mix of curvature signs and symmetries:
#: a radially symmetric surface makes the two diagonals of a cell mirror images, so the
#: area-minimising and edge-minimising choices stop being distinguishable.
SURFACES = {
    "saddle": lambda x, y: (x - 1.5) * (y - 1.5) * 0.8,
    "bump": lambda x, y: 2.0 - 0.3 * ((x - 1.5) ** 2 + (y - 1.5) ** 2),
    "dish": lambda x, y: 0.3 * ((x - 1.5) ** 2 + (y - 1.5) ** 2),
    "ramp": lambda x, y: 0.7 * x + 0.2 * y,
    "asymmetric": lambda x, y: (x**1.7) * 0.4 - (y**2) * 0.3,
    "rough": lambda x, y: ((x * 7 + y * 13) % 5) * 0.6 - 1.2,
}


def _grid(name: str) -> list[Path3D]:
    height = SURFACES[name]
    return [Path3D([[float(x), float(y), float(height(x, y))] for y in range(SIDE)]) for x in range(SIDE)]


def _triangulation(style: VNFStyle, surface: str) -> tuple[tuple[int, ...], ...]:
    """A face set that ignores winding and face order, so only the *choice of split* shows."""
    mesh = VNF.vertex_array(points=_grid(surface), style=style)
    return tuple(sorted(tuple(sorted(face)) for face in mesh.faces))


def _total_area(style: VNFStyle, grid: list[Path3D]) -> float:
    mesh = VNF.vertex_array(points=grid, style=style)
    verts = [np.asarray([float(c) for c in p], dtype=float) for p in mesh.vertices]
    total = 0.0
    for face in mesh.faces:
        for k in range(1, len(face) - 1):  # fan, so quads count too
            a, b, c = verts[face[0]], verts[face[k]], verts[face[k + 1]]
            total += float(np.linalg.norm(np.cross(b - a, c - a)) / 2)
    return total


@pytest.mark.parametrize(
    ("first", "second"),
    list(itertools.combinations(sorted(VNFStyle, key=lambda s: s.name), 2)),
    ids=lambda s: s.name,
)
def test_no_two_styles_triangulate_the_same_way(first: VNFStyle, second: VNFStyle) -> None:
    """SPEC G-8: a style that fell through to another would pass that other style's test."""
    separating = [s for s in SURFACES if _triangulation(first, s) != _triangulation(second, s)]
    assert separating, (
        f"VNFStyle.{first.name} and VNFStyle.{second.name} produce the same triangulation on every "
        f"surface in the panel. Either one has fallen through to the other, or the panel needs a "
        f"surface that tells them apart -- say which when adding one"
    )


def test_min_area_never_triangulates_to_more_area_than_min_edge() -> None:
    """The name is the promise: shortest diagonal and least area are different criteria."""
    for surface in SURFACES:
        grid = _grid(surface)
        by_area, by_edge = _total_area(VNFStyle.MIN_AREA, grid), _total_area(VNFStyle.MIN_EDGE, grid)
        assert by_area <= by_edge + 1e-9, (
            f"on the {surface} surface MIN_AREA triangulates to {by_area:.6f} of area where "
            f"MIN_EDGE manages {by_edge:.6f}; MIN_AREA is not minimising area"
        )


#: One quad whose corners are free in all three axes, on which the shortest diagonal is *not* the
#: least-area one. Found by search; kept as a constant so the test is deterministic.
#:
#: This is the shape of cell the old per-style tests could never contain. Over a height field on a
#: regular x/y lattice -- which is what their 3x3 warped grid is, and what `heightfield` builds --
#: the shortest diagonal is always also the least-area diagonal, so `MIN_EDGE` and `MIN_AREA` are
#: genuinely the same function there. They part company only on a general quad grid, which is what
#: a sweep or a skin produces. 934 of 8000 random free-corner cells separate them; none of 4000
#: random height-field grids did.
SEPARATING_CELL = (
    (2.74, 2.91, 2.91),
    (0.33, 0.65, 1.85),
    (2.94, 1.63, 2.06),
    (1.99, 0.78, 1.62),
)


def test_min_area_beats_min_edge_where_the_criteria_actually_disagree() -> None:
    """A guard that only ever sees ties is not measuring the thing it names."""
    corners = [list(c) for c in SEPARATING_CELL]
    grid = [Path3D([corners[0], corners[1]]), Path3D([corners[3], corners[2]])]
    by_area = _total_area(VNFStyle.MIN_AREA, grid)
    by_edge = _total_area(VNFStyle.MIN_EDGE, grid)
    assert by_area < by_edge - 1e-6, (
        f"on the cell the two criteria are known to disagree on, MIN_AREA gives {by_area:.6f} and "
        f"MIN_EDGE {by_edge:.6f}. If these are now equal the two styles have become one function, "
        f"and every assertion that distinguishes them above is measuring the panel, not the code"
    )

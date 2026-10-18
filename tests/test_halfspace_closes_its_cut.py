# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""A clipped VNF is a closed solid, and the two halves add up (SPEC S-2b, G-8).

`VNF.halfspace` documents `closed=True` as "triangulate and close the cut face", and it is the
default. **It closed nothing**, and three chained defects had to be fixed before it could:

1. `cut_edges.append((fv, fv + 1))` fired at *both* intersection sites, so each clipped face emitted
   two edges -- the second joining that face's own vertex to the **next** face's, and on the last
   face to an index one past the end. A cube clipped by a plane gave the open chain
   `(4,5), (5,6), (6,7), ... (11,12)` where the rim is four edges.
2. With that fixed the edges were right and still disjoint: `(4,5), (6,7), (8,9), (10,11)`, four
   segments sharing no endpoint, because each face made its *own* intersection points. A cut point
   lies on one original edge, and that edge belongs to two faces, so it must be one vertex with one
   index. Keyed on the original edge, the rim closes.
3. With the rim closing, the cap was wound the same way for both halves, so on `keep=False` it faced
   inwards. The dropped half of a 20-cube cut at `z = 4` measured 4533.33 against the correct 5600 --
   short by exactly twice the cap's own `area * z / 3`, which is what a sign flip on one face costs.

Each masked the next, so a fix for any one alone changed nothing measurable.

**Why it went unnoticed for so long: at `d = 0` the answer is right anyway.** `volume()` sums signed
tetrahedra from the origin, and an open face lying in a plane *through* the origin contributes
nothing -- so a plane through the centre gave the correct volume from a non-manifold mesh. Every
existing test cut through the origin. The guard below cuts off-centre on purpose, and on a plane
that is not axis-aligned.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pybosl2 import cuboid, cyl, sphere, use_defaults

if TYPE_CHECKING:
    from pybosl2.vnf import VNF

FACETS = 24

#: Planes chosen so none is the forgiving case. `d = 0` is kept as the control -- it was correct
#: before the fix, so a regression that only breaks the off-centre planes stays visible as such.
PLANES = {
    "through the origin": [0.0, 0.0, 1.0, 0.0],
    "offset in z": [0.0, 0.0, 1.0, 4.0],
    "offset in x": [1.0, 0.0, 0.0, -3.0],
    "not axis aligned": [1.0, 1.0, 1.0, 2.0],
}


def _solids() -> dict[str, VNF]:
    with use_defaults(fn=FACETS):
        return {
            "cube": cuboid([20.0, 20.0, 20.0]).vnf(),
            "cylinder": cyl(height=20.0, radius=8.0).vnf(),
            "sphere": sphere(radius=10.0).vnf(),
        }


SOLIDS = _solids()


def _open_edges(mesh: VNF) -> int:
    """How many edges are not shared by exactly two faces. Zero iff the mesh is closed."""
    counts: dict[tuple[int, int], int] = {}
    for face in mesh.faces:
        for i in range(len(face)):
            edge = (face[i], face[(i + 1) % len(face)])
            key = edge if edge[0] < edge[1] else (edge[1], edge[0])
            counts[key] = counts.get(key, 0) + 1
    return sum(1 for n in counts.values() if n != 2)


#: One combination still leaves the result open, and T110 narrowed the cause to one sentence: a mesh
#: vertex lying **exactly on the plane**. A 24-facet cylinder cut by `[1, 1, 1, 2]` has a rim vertex
#: at `(-8, 0, 10)`, and `-8 + 0 + 10 = 2` satisfies the plane exactly. Such a vertex is excluded
#: from the kept set -- its distance is 0, not greater than 0 -- while the cut simultaneously lands
#: on it from every edge that meets there, so each of those edges makes its own copy and the faces
#: either side refer to different points with the same position.
#:
#: **Correction to T110's account**: it said such a vertex is "excluded from the kept set (its
#: distance is 0, not > 0)". The masks are `dists >= -_EPS` and `dists <= _EPS` -- *closed*
#: halfspaces -- so the vertex is included on **both** sides. The duplication is therefore not about
#: which half it belongs to: the cut lands on a vertex that is already kept and already has an index
#: through `vertex_map`, and a fresh vertex is appended at the same position anyway.
#:
#: Four fixes have been tried and **none is kept**, each measured on the twelve shape-and-plane
#: combinations:
#:
#: 1. a shared fresh vertex for the on-plane corner: keep side 12 unpaired edges -> **25**, and the
#:    partition stopped balancing;
#: 2. deduplicating the clipped polygon's repeated corners: drop side 12 -> 8, but nothing could make
#:    its absence fail, because the `area > _EPS` filter discards the degenerate triangles anyway;
#: 3. reusing `vertex_map`'s index when the cut lands on a kept vertex -- which *is* the derivation
#:    the closed masks imply: drop side **8 -> 0**, keep side 12 -> **19**, partition broken;
#: 4. (3) together with (2), on the theory that the reuse puts the index into `clipped` twice:
#:    unchanged at 19, so that theory is wrong too.
#:
#: The pattern across all four is that fixing one side disturbs the other, and no account of why has
#: survived a measurement yet. Further attempts should start by explaining the **19**, which is the
#: number no hypothesis has predicted.
#:
#: One attempt at that explanation is also recorded, because it looked conclusive and was not.
#: Classifying the 19 edges' endpoints by their distance to the plane reported all 38 as *on-plane*,
#: which suggested the rim was losing the segments that coincide with existing mesh edges. Recording
#: those as rim segments changed nothing. The classification was the flaw: an interpolated cut point
#: lies on the plane **by construction**, so "on-plane" did not separate original vertices from cut
#: points and the measurement could not support the conclusion drawn from it. A fifth fix went in on
#: that reasoning and came straight back out.
#:
#: So the open question is sharper than before: of the 19 unpaired edges, how many join two *original*
#: mesh vertices, how many join two cut points, and how many are mixed? That distinction is what the
#: earlier measurement failed to make. Sharing one vertex for the on-plane corner took the
#: keep side from 12 unpaired edges to 25 and stopped the partition balancing, because the shared
#: point then disagrees with the drop side, which excludes that vertex too: reconciling the two needs
#: a decision about which half an exactly-on-plane vertex belongs to, and that is a convention rather
#: than a derivation. Deduplicating the clipped polygon's repeated corners did help the drop side,
#: 12 unpaired edges to 8 -- but no negative control could make its absence fail, because the
#: `area > _EPS` filter discards the degenerate triangles before they reach the face list either way.
#: Code that no control can break does not stay, which is the rule T109 applied to its own
#: undirected rim chainer.
#:
#: `strict=True`, so a fix cannot pass quietly. The volume and partition assertions hold for this
#: case regardless, which is why they are not xfailed with it -- the cracks do not move the
#: divergence sum measurably, and that is exactly what makes them easy to miss.
STILL_OPEN = {("cylinder", "not axis aligned")}


@pytest.mark.parametrize("plane_name", sorted(PLANES))
@pytest.mark.parametrize("solid_name", sorted(SOLIDS))
@pytest.mark.parametrize("keep", [True, False], ids=["keep", "drop"])
def test_a_clipped_solid_is_closed(
    solid_name: str, plane_name: str, keep: bool, request: pytest.FixtureRequest
) -> None:
    """SPEC S-2b: `closed=True` is the default and says it closes the cut face."""
    if (solid_name, plane_name) in STILL_OPEN:
        request.node.add_marker(pytest.mark.xfail(strict=True, reason="clipped faces lose slivers; see STILL_OPEN"))
    clipped = SOLIDS[solid_name].halfspace(plane=PLANES[plane_name], keep=keep, closed=True)
    assert _open_edges(clipped) == 0, (
        f"clipping the {solid_name} at {plane_name} left {_open_edges(clipped)} edges not shared by "
        f"two faces, so the cut face is not capped and the result is not a solid"
    )


@pytest.mark.parametrize("plane_name", sorted(PLANES))
@pytest.mark.parametrize("solid_name", sorted(SOLIDS))
def test_the_two_halves_add_up_to_the_whole(solid_name: str, plane_name: str) -> None:
    """The property that catches a mis-wound cap, which closedness alone does not.

    A cap wound inwards still gives a manifold mesh -- every edge is shared twice -- so the two
    halves must be measured. `keep` and `drop` sum to the original only if both caps face outwards.
    """
    whole = SOLIDS[solid_name]
    total = float(whole.volume())
    kept = float(whole.halfspace(plane=PLANES[plane_name], keep=True).volume())
    dropped = float(whole.halfspace(plane=PLANES[plane_name], keep=False).volume())
    assert kept + dropped == pytest.approx(total, rel=0.003), (
        f"the {solid_name} cut at {plane_name} gives {kept:.2f} + {dropped:.2f} = {kept + dropped:.2f}, not {total:.2f}"
    )


@pytest.mark.parametrize("offset", [-5.0, -2.5, 0.0, 2.5, 5.0, 7.5, 9.0])
def test_the_kept_slab_measures_what_it_should(offset: float) -> None:
    """Exact arithmetic, not a round trip: a 20-cube cut at z = offset leaves 400 * (10 - offset).

    Before the fix this was right at 0.0 and wrong everywhere else -- 2666.67 against 2000 at
    `z = 5`, and 1333.33 against 0 for a cut at the very top face, where the result is a flat square.
    """
    kept = float(SOLIDS["cube"].halfspace(plane=[0.0, 0.0, 1.0, offset], keep=True).volume())
    assert kept == pytest.approx(400.0 * (10.0 - offset), abs=0.5), (
        f"keeping z >= {offset} of a 20-cube measures {kept:.2f}, not {400.0 * (10.0 - offset):.2f}"
    )


def test_leaving_the_cut_open_is_a_different_mesh() -> None:
    """`closed=False` must mean something: it was inert, which is how the cap stayed broken.

    Checked on the open-edge count rather than the volume, because an open mesh's volume is not
    meaningful -- that is the whole point. `closed=False` is the one case where open edges are
    correct.
    """
    plane = PLANES["offset in z"]
    capped = SOLIDS["cube"].halfspace(plane=plane, keep=True, closed=True)
    uncapped = SOLIDS["cube"].halfspace(plane=plane, keep=True, closed=False)
    assert _open_edges(capped) == 0, "closed=True must close the cut"
    assert _open_edges(uncapped) > 0, (
        "closed=False produced a closed mesh, so the flag changes nothing and the capping is not "
        "actually conditional on it"
    )

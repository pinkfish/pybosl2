# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The two backends must build the same solid, measured on the field and not on the box (PAR-1).

`tests/test_option_parity.py` asks whether each backend *accepts* the same options, and
`tests/test_sdf_bounds_are_tight.py` asks whether a solid fills the box it declares. Neither asks
the question in the middle: given the same call, do the two backends build the same shape? Nothing
did, because of a sentence this campaign repeated four times -- *libfive is stubbed, so an SDF solid
meshes to nothing and only its analytic box can be read*.

Only the first clause is true. `inside()` answers correctly and the field evaluates to exact signed
distances, so the comparison was available all along; see `tests/field_probe.py` for the
measurement and for why the test is one-sided. Short version: a CSG mesh inscribes a curved surface,
so a vertex inside the field is faceting and converges away as the facet count rises, while a vertex
*outside* the field cannot be faceting and is a real disagreement.

Across every solid both backends build, the furthest-outside figure is exactly ``0.000000``. So this
file asserts something sharp and free of tolerance, and the thing it would have caught is not
hypothetical: the SDF `path_sweep` puts 22 of the façade sweep's 72 vertices outside its own field,
by up to 0.3162 (see `test_the_two_sweeps_agree.py`).
"""

from __future__ import annotations

import pytest

import pybosl2.solid as solid
from tests.field_probe import csg_vertices, distances, worst_escape

#: One call per solid, built the same way on both backends. The figure each is checked against is
#: zero, so adding a shape here cannot be made to pass by loosening anything.
SHAPES = {
    "cuboid": lambda: solid.cuboid(size=[20, 14, 10]),
    "cuboid rounded": lambda: solid.cuboid(size=[20, 14, 10], rounding=2),
    "cuboid chamfered": lambda: solid.cuboid(size=[20, 14, 10], chamfer=2),
    "cube": lambda: solid.cube(size=12),
    "sphere": lambda: solid.sphere(radius=7),
    "spheroid": lambda: solid.spheroid(radius=7),
    "cylinder": lambda: solid.cylinder(height=20, radius=6),
    "cyl": lambda: solid.cyl(height=20, radius=6),
    "cyl tapered": lambda: solid.cyl(height=20, radius1=8, radius2=3),
    "cyl rounded": lambda: solid.cyl(height=20, radius=6, rounding=2),
    "cyl chamfered": lambda: solid.cyl(height=20, radius=6, chamfer=2),
    "tube": lambda: solid.tube(height=20, outer_radius=8, inner_radius=4),
    "prismoid": lambda: solid.prismoid(size1=[20, 20], size2=[10, 14], height=10),
    "rect_tube": lambda: solid.rect_tube(height=10, size=20, wall=2),
    "regular_prism": lambda: solid.regular_prism(sides=7, height=10, radius=5),
    "wedge": lambda: solid.wedge(size=[20, 10, 8]),
    "teardrop": lambda: solid.teardrop(height=10, radius=6),
    "torus": lambda: solid.torus(outer_radius=10, inner_radius=4),
    "pie_slice": lambda: solid.pie_slice(height=10, radius=8, angle=70),
    "zcyl": lambda: solid.zcyl(height=20, radius=6),
    "xcyl": lambda: solid.xcyl(height=20, radius=6),
    "ycyl": lambda: solid.ycyl(height=20, radius=6),
    "onion": lambda: solid.onion(radius=7),
}

#: A vertex may sit this far outside the field before it counts. It is not a tolerance for faceting
#: -- faceting goes the other way -- only for the arithmetic of evaluating the tree, and every
#: shape above measures exactly 0.0 against it.
OUTSIDE = 1e-6


def test_the_probe_reads_a_real_field() -> None:
    """Every assertion below reads zero if the field evaluates to nothing, so prove it does not.

    Three points on a sphere of radius 7: the centre reads -7, the pole reads 0, and a point one
    unit beyond reads +1. A stub returning zeros would pass every other test in this file.
    """
    centre, pole, beyond = distances(
        lambda: solid.sphere(radius=7), [[0.0, 0.0, 0.0], [7.0, 0.0, 0.0], [8.0, 0.0, 0.0]]
    )
    assert centre == pytest.approx(-7.0, abs=1e-6), f"centre of a sphere of radius 7 reads {centre}"
    assert pole == pytest.approx(0.0, abs=1e-6), f"surface of a sphere of radius 7 reads {pole}"
    assert beyond == pytest.approx(1.0, abs=1e-6), f"one unit outside reads {beyond}"


def test_inside_is_not_false_everywhere() -> None:
    """The specific claim that deferred the work, kept as the standing correction.

    `inside()` reads the field, not the box: the two points either side of a sphere's surface differ
    in their answer, and a box cannot tell them apart -- both are inside the box.
    """
    from pybosl2 import use_backend

    with use_backend("sdf"):
        ball = solid.sphere(radius=7)
        near, far, corner = ball.inside([3.9, 3.9, 3.9]), ball.inside([4.1, 4.1, 4.1]), ball.inside([7.0, 7.0, 7.0])
    assert near is True, "a point 6.75 from the centre of a sphere of radius 7 is inside it"
    assert far is False, "a point 7.10 from the centre of a sphere of radius 7 is outside it"
    assert corner is False, "the corner of the bounding box is outside the sphere; box logic says inside"


@pytest.mark.parametrize("label", sorted(SHAPES))
def test_no_csg_vertex_escapes_the_sdf_field(label: str) -> None:
    """The same call on both backends must build the same solid, checked on the field itself."""
    build = SHAPES[label]
    outside, inside, where = worst_escape(build, build)
    assert outside <= OUTSIDE, (
        f"{label}: the CSG mesh has a vertex at {where} lying {outside:.4f} *outside* the SDF "
        f"field. Faceting can only inscribe, so the two backends are building different solids "
        f"(SPEC PAR-1). The furthest-inside figure is {inside:.4f}, which faceting does explain."
    )


@pytest.mark.parametrize("label", sorted(SHAPES))
def test_the_sample_points_are_real_vertices(label: str) -> None:
    """A shape whose vertex list came back empty would pass the test above by having no points."""
    points = csg_vertices(SHAPES[label])
    assert len(points) >= 6, (
        f"{label} produced {len(points)} vertices, too few to be a solid -- the test above would "
        f"then be asserting nothing."
    )


def test_faceting_inscribes_and_converges() -> None:
    """Why the test is one-sided, asserted rather than assumed.

    A rounded cylinder is the shape whose mesh departs furthest from its field, and the departure is
    entirely inward and falls by about four times per doubling of the facet count. If a tessellation
    could sit outside the field, the one-sided assertion above would be unsound.
    """
    measured = []
    for facets in (16, 32, 64):
        build_csg = lambda f=facets: solid.cyl(height=20, radius=6, rounding=2, fn=f)  # noqa: E731
        build_sdf = lambda: solid.cyl(height=20, radius=6, rounding=2)  # noqa: E731
        outside, inside, _ = worst_escape(build_csg, build_sdf)
        assert outside <= OUTSIDE, f"a tessellation at fn={facets} reached {outside:.4f} outside the field"
        measured.append(abs(inside))
    assert measured[0] > measured[1] > measured[2], (
        f"inward departure went {measured} as the facet count doubled; it must fall, or the "
        f"departure is not faceting and the one-sided comparison is unsound."
    )
    assert measured[2] < measured[0] / 4, (
        f"inward departure fell only from {measured[0]:.4f} to {measured[2]:.4f} over four times "
        f"the facets; an inscribed polygon converges quadratically."
    )

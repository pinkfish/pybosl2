# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""An SDF polyhedron is convex, and says so rather than quietly filling the concavities.

The SDF backend builds a polyhedron as the intersection of its faces' half-spaces, which can only
ever be convex. It used to accept a `faces` list and ignore it -- documented as "accepted for
signature-compatibility ... but ignored" -- so asking for an L-shaped prism handed back its convex
hull. The notch was filled, the bounding box was identical, and nothing downstream could tell
(SPEC B-4: a backend must not silently approximate what it cannot express).
"""

from __future__ import annotations

import pytest

from pybosl2._backend import get_backend, use_backend
from pybosl2.exceptions import UnsupportedByBackendError

#: An L-shaped prism: the classic non-convex solid, with a notch at the +X+Y corner.
L_POINTS = [
    [0, 0, 0], [10, 0, 0], [10, 4, 0], [4, 4, 0], [4, 10, 0], [0, 10, 0],
    [0, 0, 5], [10, 0, 5], [10, 4, 5], [4, 4, 5], [4, 10, 5], [0, 10, 5],
]  # fmt: skip
L_FACES = [
    [0, 1, 2, 3, 4, 5], [11, 10, 9, 8, 7, 6],
    [0, 6, 7, 1], [1, 7, 8, 2], [2, 8, 9, 3], [3, 9, 10, 4], [4, 10, 11, 5], [5, 11, 6, 0],
]  # fmt: skip

TETRAHEDRON = ([[0, 0, 0], [20, 0, 0], [10, 18, 0], [10, 6, 16]], [[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]])
CUBE = (
    [[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0], [0, 0, 10], [10, 0, 10], [10, 10, 10], [0, 10, 10]],
    [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]],
)


def test_a_non_convex_polyhedron_is_refused_on_sdf() -> None:
    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError, match="non-convex") as excinfo:
        get_backend().polyhedron(L_POINTS, L_FACES)
    assert ".to_csg()" in str(excinfo.value)  # the message names the way forward (SPEC E-4)


def test_the_csg_backend_builds_the_concave_solid_it_was_asked_for() -> None:
    """The other half of the claim: the shape really is buildable, just not as a field."""
    from pybosl2.shapes3d import cuboid

    with use_backend("csg"):
        solid = get_backend().polyhedron(L_POINTS, L_FACES)
    assert solid.bounds().size == pytest.approx([10.0, 10.0, 5.0])
    # The notch is open -- a probe sitting in it comes back empty.
    probe = cuboid([2, 2, 2]).translate([7, 7, 2.5])
    assert (solid & probe)._native_bounds() is None


def test_the_hull_would_have_filled_the_notch() -> None:
    """Why the refusal matters: the wrong answer was indistinguishable by bounding box.

    Building the hull anyway gives a solid whose envelope matches the real one exactly, so no
    bounds-based check anywhere could have caught the substitution.
    """
    with use_backend("sdf"):
        hull = get_backend().polyhedron(L_POINTS)  # no faces: the hull is what was asked for
        assert hull.bounds().size == pytest.approx([10.0, 10.0, 5.0])  # ... same envelope
        assert float(hull.mesh().sample(6, 6, 2.5)) < 0  # ... but solid where the notch should be


@pytest.mark.parametrize(("points", "faces"), [TETRAHEDRON, CUBE])
def test_a_convex_polyhedron_builds_on_both_backends(points: list, faces: list) -> None:  # type: ignore[type-arg]
    """For convex input the face half-spaces are exact, so both backends agree."""
    built = {}
    for backend in ("csg", "sdf"):
        with use_backend(backend):
            built[backend] = [float(v) for v in get_backend().polyhedron(points, faces).bounds().size]
    assert built["sdf"] == pytest.approx(built["csg"], abs=0.01)


def test_malformed_faces_are_left_to_the_csg_backend_to_complain_about() -> None:
    """The convexity check is not a validator: a bad index is not "non-convex"."""
    from pybosl2.sdf import _describes_a_convex_solid

    assert _describes_a_convex_solid(L_POINTS, [[0, 1, 99]])  # index out of range
    assert _describes_a_convex_solid(L_POINTS, [[0, 1]])  # too few vertices
    assert _describes_a_convex_solid(L_POINTS, [[0, 0, 0]])  # degenerate: no plane to test against

    # It is the face cutting the notch that gives the shape away -- the base does not.
    assert _describes_a_convex_solid(L_POINTS, [[0, 1, 2, 3, 4, 5]])  # the base plane: all points above it
    assert not _describes_a_convex_solid(L_POINTS, [[2, 8, 9, 3]])  # the notch wall: points on both sides


def test_the_check_sees_a_notch_however_the_faces_are_wound() -> None:
    """Winding decides which way a face normal points, so the check orients them itself."""
    from pybosl2.sdf import _describes_a_convex_solid

    assert not _describes_a_convex_solid(L_POINTS, L_FACES)
    reversed_faces = [face[::-1] for face in L_FACES]
    assert not _describes_a_convex_solid(L_POINTS, reversed_faces)
    assert _describes_a_convex_solid(*TETRAHEDRON)
    assert _describes_a_convex_solid(TETRAHEDRON[0], [face[::-1] for face in TETRAHEDRON[1]])

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Milestone 3 of the CSG/SDF merge: the backend-neutral facade (pybosl2/solid.py). The same
constructor call obeys the active backend and both backends agree on the resulting geometry."""

import pytest

from pybosl2 import solid
from pybosl2._backend import Solid, current_backend, use_backend


def test_facade_defaults_to_csg():
    s = solid.sphere(radius=10)
    assert s.backend == "csg"
    assert type(s).__name__ == "Bosl2Solid"
    assert isinstance(s, Solid)


def test_facade_obeys_use_backend_context():
    assert current_backend() == "csg"
    with use_backend("sdf"):
        s = solid.sphere(radius=10)
        assert s.backend == "sdf"
        assert type(s).__name__ == "PyShape"
    assert solid.cube(5).backend == "csg"  # restored to the default outside the block


# The full shared-shape × both-backends bounds matrix lives in tests/test_backend_matrix.py (M7).


def test_facade_union_dispatches_on_active_backend():
    u = solid.union(solid.cube(10), solid.sphere(radius=6))
    assert u.backend == "csg"
    with use_backend("sdf"):
        u2 = solid.union(solid.cube(10), solid.sphere(radius=6))
        assert u2.backend == "sdf"


def test_facade_polyhedron_dispatches_on_active_backend():
    pts = [[0, 0, 0], [10, 0, 0], [5, 10, 0], [5, 5, 10]]  # tetrahedron
    faces = [[0, 1, 2], [0, 1, 3], [1, 2, 3], [0, 2, 3]]
    c = solid.polyhedron(pts, faces)  # csg: needs faces
    assert c.backend == "csg"
    with use_backend("sdf"):
        s = solid.polyhedron(pts)  # sdf: convex hull of points, faces ignored
        assert s.backend == "sdf"
    for cv, sv in zip(c.bounds()[1], s.bounds()[1], strict=False):
        assert abs(cv - sv) < 0.7  # both agree on the tetrahedron's bounding box


def test_facade_construct_rejects_unknown_shape():
    from pybosl2._backend import get_backend

    with pytest.raises(ValueError, match="no shape constructor"):
        get_backend().construct("definitely_not_a_shape")

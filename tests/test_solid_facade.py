# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Milestone 3 of the CSG/SDF merge: the backend-neutral facade (bosl2/solid.py). The same
constructor call obeys the active backend and both backends agree on the resulting geometry."""

from bosl2 import solid
from bosl2._backend import Solid, current_backend, use_backend


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

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Milestone 3 of the CSG/SDF merge: the backend-neutral facade (bosl2/solid.py). The same
constructor call obeys the active backend and both backends agree on the resulting geometry."""

import pytest

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


@pytest.mark.parametrize(
    "name, args, kwargs, size",
    [
        ("sphere", (), {"radius": 10}, [20, 20, 20]),
        ("spheroid", (), {"radius": 10}, [20, 20, 20]),
        ("cube", (10,), {}, [10, 10, 10]),
        ("cuboid", ([12, 8, 6],), {}, [12, 8, 6]),
        ("cylinder", (), {"height": 20, "radius": 5}, [10, 10, 20]),
        ("cyl", (), {"height": 20, "radius": 5}, [10, 10, 20]),
        ("torus", (), {"major_radius": 20, "minor_radius": 5}, [50, 50, 10]),
        ("tube", (), {"height": 10, "outer_radius": 10, "inner_radius": 6}, [20, 20, 10]),
    ],
)
def test_both_backends_agree_on_bounds(name, args, kwargs, size):
    fn = getattr(solid, name)
    csg = fn(*args, **kwargs)
    with use_backend("sdf"):
        sdf = fn(*args, **kwargs)
    assert csg.backend == "csg" and sdf.backend == "sdf"
    for c, s, want in zip(csg.bounds()[1], sdf.bounds()[1], size):
        assert abs(c - want) < 0.7, f"{name}: csg size off"  # CSG faceting tolerance
        assert abs(s - want) < 0.7, f"{name}: sdf size off"
        assert abs(c - s) < 0.7, f"{name}: backends disagree"  # ... and agree with each other


def test_facade_union_dispatches_on_active_backend():
    u = solid.union(solid.cube(10), solid.sphere(radius=6))
    assert u.backend == "csg"
    with use_backend("sdf"):
        u2 = solid.union(solid.cube(10), solid.sphere(radius=6))
        assert u2.backend == "sdf"

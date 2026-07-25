# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Milestone 7 of the CSG/SDF merge: the unified backend test matrix.

Every shared 3-D constructor in the ``bosl2.solid`` facade is exercised against BOTH backends from a
single parameter table, so the shared surface is tested once rather than per backend. Construction
and ``bounds()`` are FFI-free on both backends (the SDF side reads the distance field's domain, not a
mesh), so this whole matrix runs without libfive installed -- no skips.

A coverage guard asserts the table matches ``solid._SHARED_3D`` exactly, so adding a shared
constructor without a matrix row (or vice-versa) fails loudly instead of silently going untested.
"""

import pytest

from bosl2 import solid
from bosl2._backend import Solid, use_backend

# name -> (args, kwargs, expected_size, agree)
#   expected_size: nominal [x, y, z] bounding size both backends should produce (None = don't assert)
#   agree:         whether the two backends' bounds() must match each other (False for shapes whose
#                  SDF bounds() reports a conservative construction domain rather than the tight bbox)
SHARED_SHAPES = {
    "cube": ((10,), {}, [10, 10, 10], True),
    "cuboid": (([12, 8, 6],), {}, [12, 8, 6], True),
    "cyl": ((), {"height": 20, "radius": 5}, [10, 10, 20], True),
    "cylinder": ((), {"height": 20, "radius": 5}, [10, 10, 20], True),
    "octahedron": ((10,), {}, [10, 10, 10], True),
    "onion": ((), {"radius": 10}, None, True),
    "pie_slice": ((), {"height": 10, "radius": 8, "angle": 45}, None, False),  # SDF bounds = full disc
    "prismoid": ((), {"size1": [10, 10], "size2": [6, 6], "height": 8}, [10, 10, 8], True),
    "rect_tube": ((), {"height": 10, "size": [20, 20], "wall": 2}, [20, 20, 10], True),
    "regular_prism": ((6,), {"height": 10, "radius": 8}, None, True),
    "sphere": ((), {"radius": 10}, [20, 20, 20], True),
    "spheroid": ((), {"radius": 10}, [20, 20, 20], True),
    "teardrop": ((), {"height": 10, "radius": 8}, None, True),
    "torus": ((), {"major_radius": 20, "minor_radius": 5}, [50, 50, 10], True),
    "tube": ((), {"height": 10, "outer_radius": 10, "inner_radius": 6}, [20, 20, 10], True),
    "wedge": (([10, 8, 6],), {}, [10, 8, 6], True),
    "xcyl": ((), {"length": 20, "radius": 5}, [20, 10, 10], True),
    "ycyl": ((), {"length": 20, "radius": 5}, [10, 20, 10], True),
    "zcyl": ((), {"length": 20, "radius": 5}, [10, 10, 20], True),
}

TOL = 0.8  # CSG faceting makes sizes fall slightly short of nominal


def test_matrix_covers_every_shared_constructor():
    """Guard against drift: the matrix must exercise exactly the facade's shared 3-D surface."""
    assert set(SHARED_SHAPES) == set(solid._SHARED_3D)


@pytest.mark.parametrize("backend", ["csg", "sdf"])
@pytest.mark.parametrize("name", list(SHARED_SHAPES))
def test_shared_constructor_builds_on_backend(name, backend):
    args, kwargs, expected, _ = SHARED_SHAPES[name]
    with use_backend(backend):
        s = getattr(solid, name)(*args, **kwargs)
    assert s.backend == backend
    assert isinstance(s, Solid)
    size = s.bounds()[1]
    assert len(size) == 3 and all(v > 0 for v in size), f"{name} on {backend}: degenerate bounds {size}"
    if expected is not None:
        for got, want in zip(size, expected):
            assert abs(got - want) < TOL, f"{name} on {backend}: size {size} != nominal {expected}"


@pytest.mark.parametrize("name", list(SHARED_SHAPES))
def test_both_backends_agree_on_bounds(name):
    args, kwargs, _, agree = SHARED_SHAPES[name]
    csg = getattr(solid, name)(*args, **kwargs)
    with use_backend("sdf"):
        sdf = getattr(solid, name)(*args, **kwargs)
    assert csg.backend == "csg" and sdf.backend == "sdf"
    if not agree:
        return  # bounds() legitimately differ (SDF reports a conservative construction domain)
    for c, s in zip(csg.bounds()[1], sdf.bounds()[1]):
        assert abs(c - s) < TOL, f"{name}: backends disagree on bounds ({c} vs {s})"


@pytest.mark.parametrize("backend", ["csg", "sdf"])
@pytest.mark.parametrize("op", ["union", "difference", "intersection"])
def test_boolean_ops_dispatch_on_active_backend(backend, op):
    with use_backend(backend):
        a = solid.cube(10)
        b = solid.sphere(radius=6)
        result = getattr(solid, op)(a, b)
    assert result.backend == backend
    assert isinstance(result, Solid)

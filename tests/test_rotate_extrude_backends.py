# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""`rotate_extrude()` on both backends (TASKS T14).

A revolve is the 2-D -> 3-D operation that suits a distance field best: a surface of revolution's
field at ``(x, y, z)`` is the profile's own 2-D field read at ``(hypot(x, y), z)``, because every
point's distance to it is its distance within the half-plane it lies in. So it needs no meshing and
no approximation of the revolve -- it is exact wherever the profile's 2-D field is.

It used to refuse on the SDF backend, naming `path_sweep()` as the alternative. That kept
`bottlecaps`, `modular_hose` and part of `screw_drive` CSG-only.
"""

from __future__ import annotations

import math

import pytest

import pybosl2.sdf  # noqa: F401  -- registers the sdf backend
from pybosl2._backend import use_backend
from pybosl2.path2d import Path2D

#: A 4mm-wide, 2mm-tall rectangle sitting between radius 6 and 10: revolves into a square-section
#: ring, whose every dimension is known in closed form.
RING = [[6, -1], [10, -1], [10, 1], [6, 1]]

BACKENDS = ["csg", "sdf"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_a_full_revolution_is_a_ring_of_the_stated_radius(backend: str) -> None:
    with use_backend(backend):
        ring = Path2D(RING).rotate_extrude()
    _box = ring.bounds()
    centre, size = list(_box.center), list(_box.size)
    assert size[0] == pytest.approx(20.0, abs=0.2)  # 2 * outer radius; CSG facets fall just inside
    assert size[1] == pytest.approx(20.0, abs=0.2)
    assert size[2] == pytest.approx(2.0, abs=0.01)  # the profile's own height
    assert [float(v) for v in centre] == pytest.approx([0, 0, 0], abs=0.05)


@pytest.mark.parametrize(("angle", "expected_size"), [(90, (10, 10, 2)), (180, (20, 10, 2)), (270, (20, 20, 2))])
def test_a_partial_revolution_sweeps_the_same_sector_on_both_backends(
    angle: float,
    expected_size: tuple[float, float, float],
) -> None:
    """The sector runs 0..angle from +X, so 90 degrees is the first quadrant on either backend."""
    built = {}
    for backend in BACKENDS:
        with use_backend(backend):
            built[backend] = Path2D(RING).rotate_extrude(angle).bounds()
    for axis in range(3):
        assert abs(float(built["csg"].size[axis]) - float(built["sdf"].size[axis])) < 0.2
        assert abs(float(built["csg"].center[axis]) - float(built["sdf"].center[axis])) < 0.2
        assert float(built["sdf"].size[axis]) == pytest.approx(expected_size[axis], abs=0.01)


def test_the_field_is_the_profile_read_at_the_radius() -> None:
    """What makes a revolve exact in a field: sample it and check, rather than trusting the box."""
    from pybosl2.sdf.shapes3d import rotate_extrude

    ring = rotate_extrude(RING).mesh()
    # Rotationally symmetric: the same reading at the same radius, whatever the direction.
    for angle in (0, 37, 90, 180, 300):
        x, y = 8 * math.cos(math.radians(angle)), 8 * math.sin(math.radians(angle))
        assert float(ring.sample(x, y, 0)) == pytest.approx(-1.0, abs=1e-6)
    assert float(ring.sample(4, 0, 0)) > 0  # inside the bore, so outside the solid
    assert float(ring.sample(12, 0, 0)) > 0  # past the rim
    assert float(ring.sample(8, 0, 2)) > 0  # above it


def test_a_profile_crossing_the_axis_is_rejected() -> None:
    """Revolving through the axis makes a self-intersecting solid; OpenSCAD refuses it too."""
    from pybosl2.sdf.shapes3d import rotate_extrude

    with pytest.raises(ValueError, match="crosses the Z axis"):
        rotate_extrude([[-2, -1], [10, -1], [10, 1], [-2, 1]])


@pytest.mark.parametrize("bad", [[], [[[0, 0], [1, 0]]]])
def test_a_degenerate_profile_is_rejected(bad: object) -> None:
    from pybosl2.sdf.shapes3d import rotate_extrude

    with pytest.raises(ValueError, match="rotate_extrude"):
        rotate_extrude(bad)  # type: ignore[arg-type]


def test_a_concave_profile_revolves_correctly() -> None:
    """The profile's field is `_polygon_sdf_xy`, which handles concave outlines, so this does too."""
    from pybosl2.sdf.shapes3d import rotate_extrude

    # An L-section: full width below z=0, stepped back to r=8 above it.
    profile = [[6, -2], [10, -2], [10, 0], [8, 0], [8, 2], [6, 2]]
    ring = rotate_extrude(profile).mesh()
    assert float(ring.sample(9, 0, -1)) < 0  # in the wide part, below the step
    assert float(ring.sample(7, 0, 1)) < 0  # in the narrow part, above it
    assert float(ring.sample(9.5, 0, 1.5)) > 0  # the step really is cut away
    # ... and the step is there in every direction, since a revolve is symmetric by construction
    assert float(ring.sample(0, 7, 1)) < 0
    assert float(ring.sample(0, 9.5, 1.5)) > 0

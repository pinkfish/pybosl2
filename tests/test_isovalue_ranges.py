# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""An isovalue range encloses a band, and a band of a distance field is a shell.

SPEC G-8, S-31. `VNF.from_field` took a scalar threshold and refused a `[lo, hi]` range, advising
the caller to "mesh each threshold and subtract the inner surface from the outer one". That advice
was more work than the feature: `lo <= f <= hi` is exactly `min(f - lo, hi - f) >= 0`, so a band is
one marching-cubes pass over a transformed field, not two meshes and a difference. The refusal was
the whole of the gap.

The instrument is analytic volume, not bounds. Bounds cannot tell a shell from the solid ball that
contains it -- both are 20mm across -- and the defect a band implementation actually risks is
producing the ball: getting the outer surface right and losing the cavity. `f(p) = |p|` banded to
`[5, 10]` is a spherical shell whose volume is `4/3 π (10³ - 5³)` to arithmetic, and whose every
vertex must lie on one of the two spheres and not between them.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from pybosl2.bounds import Bounds3D
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.vnf import VNF

BOX = Bounds3D(min_x=-12, min_y=-12, min_z=-12, max_x=12, max_y=12, max_z=12, width=24, length=24, height=24)


def _distance(points: np.ndarray) -> np.ndarray:
    """The distance from the origin, whose isosurfaces are spheres of known volume."""
    return np.asarray(np.linalg.norm(points, axis=1))


def _mesh(isovalue: float | tuple[float, float]) -> VNF:
    return VNF.from_field(_distance, isovalue, bounding_box=BOX, voxel_size=0.4, closed=True)


def test_a_band_of_a_distance_field_is_a_shell_of_the_right_volume() -> None:
    """SPEC G-8: `[5, 10]` encloses the shell between two spheres, not the ball inside them."""
    shell = _mesh((5.0, 10.0))
    exact = 4 / 3 * math.pi * (10**3 - 5**3)
    assert abs(shell.volume()) == pytest.approx(exact, rel=0.01), (
        f"a shell of {abs(shell.volume()):.1f} against an exact {exact:.1f}"
    )
    solid = 4 / 3 * math.pi * 10**3
    assert abs(shell.volume()) < solid * 0.95, (
        "the volume is close to the solid ball's -- the outer surface is right and the cavity is missing"
    )


def test_every_vertex_of_the_shell_is_on_one_of_the_two_spheres() -> None:
    """SPEC G-8: volume alone would accept a shell of the right size in the wrong place."""
    radii = np.linalg.norm(np.asarray(_mesh((5.0, 10.0)).vertices), axis=1)
    assert radii.min() == pytest.approx(5.0, abs=0.05), f"inner surface at {radii.min():.3f}, not 5"
    assert radii.max() == pytest.approx(10.0, abs=0.05), f"outer surface at {radii.max():.3f}, not 10"
    between = ((radii > 5.6) & (radii < 9.4)).sum()
    assert between == 0, f"{between} vertices lie inside the shell wall rather than on its surfaces"
    assert (radii < 5.6).sum() > 0, "no inner surface was meshed at all"


def test_an_open_ended_range_is_the_bare_threshold() -> None:
    """SPEC G-8: `[lo, inf]` and `lo` say the same thing, so they must mesh the same."""
    banded, bare = _mesh((10.0, math.inf)), _mesh(10.0)
    assert len(banded.vertices) == len(bare.vertices)
    assert banded.volume() == pytest.approx(bare.volume())


def test_a_range_open_at_the_bottom_is_the_region_below_the_threshold() -> None:
    """SPEC G-8: `[-inf, 10]` is `f <= 10`, the solid ball -- not `f >= -10`, which is everything.

    Negating the threshold instead of the field is the easy way to get this wrong, and it fails
    silently: the result is the whole bounding box, which is a perfectly good closed mesh.
    """
    ball = _mesh((-math.inf, 10.0))
    assert abs(ball.volume()) == pytest.approx(4 / 3 * math.pi * 10**3, rel=0.01)
    box_volume = 24.0**3
    assert abs(ball.volume()) < box_volume * 0.5, "the whole bounding box was meshed"


def test_the_band_closes_on_the_solid_as_its_top_rises() -> None:
    """SPEC G-8: a band's cavity shrinks monotonically as `hi` rises, and vanishes in the limit."""
    solid = abs(_mesh(5.0).volume())
    cavities = [solid - abs(_mesh((5.0, hi)).volume()) for hi in (6.0, 8.0, 11.0, 1e6)]
    assert cavities == sorted(cavities, reverse=True), f"the cavity does not shrink: {cavities}"
    assert cavities[-1] == pytest.approx(0.0, abs=solid * 0.001), (
        f"an effectively unbounded band still carves {cavities[-1]:.1f} out of the solid"
    )


@pytest.mark.parametrize(
    ("isovalue", "because"),
    [
        ((10.0, 5.0), "does not increase"),
        ((5.0, 5.0), "does not increase"),
        ((1.0, 2.0, 3.0), "two values"),
        ((5.0,), "two values"),
        ((-math.inf, math.inf), "every point"),
    ],
)
def test_a_range_that_encloses_nothing_says_so(isovalue: tuple[float, ...], because: str) -> None:
    """SPEC G-8, E-2: a range that cannot bound a solid is refused with the reason, not meshed."""
    with pytest.raises(Bosl2ValueError) as excinfo:
        _mesh(isovalue)  # type: ignore[arg-type]
    assert because in str(excinfo.value), f"the refusal does not say why: {excinfo.value}"


def test_metaballs_inherit_the_band() -> None:
    """SPEC G-8: `from_metaballs` forwards its isovalue, so hollowing a blob comes for free."""
    from pybosl2.isosurface import MetaballSpec, mb_sphere

    box = Bounds3D(min_x=-30, min_y=-20, min_z=-20, max_x=30, max_y=20, max_z=20, width=60, length=40, height=40)
    spec = [MetaballSpec([-10, 0, 0], mb_sphere(11)), MetaballSpec([10, 0, 0], mb_sphere(11))]
    solid = abs(VNF.from_metaballs(spec, box, voxel_size=1.5, isovalue=1.0).volume())
    hollow = abs(VNF.from_metaballs(spec, box, voxel_size=1.5, isovalue=(1.0, 1.5)).volume())
    assert 0 < hollow < solid * 0.9, f"banding the blob left {hollow:.0f} of {solid:.0f}"

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The sweep family's contract (SPEC S-19a, S-19b, S-19c).

Sweeping is the most valuable thing BOSL2 does and was the hardest thing here to use: the family
returned ``VNF | Solid | list[list[list[float]]]``, so its own documented one-liner failed
``mypy --strict``; callers appended ``.polyhedron()`` to a call that had already said "sweep this
into a solid"; and ``path_sweep`` wound its mesh opposite to ``linear_sweep``, which meant cutting
with one of them *added* material.
"""

from __future__ import annotations

import inspect
import math

import pytest

from pybosl2 import Bezier, Path2D, Path3D, cuboid
from pybosl2._backend import Solid
from pybosl2.vnf import VNF

SQUARE = Path2D([[-5, -5], [5, -5], [5, 5], [-5, 5]], closed=True)
PROFILE = Path2D([[2, 0], [6, 0], [6, 5], [2, 5]], closed=True)


def _family() -> dict[str, object]:
    """One built solid per member of the sweep family."""
    straight = Path3D([[0, 0, z] for z in range(11)])
    wavy = Path2D([[t, 4 * math.sin(t / 12)] for t in range(0, 60, 3)])
    return {
        "path_sweep": straight.path_sweep(SQUARE),
        "path_sweep2d": wavy.path_sweep2d(Path2D([[-2, -2], [2, -2], [2, 2], [-2, 2]], closed=True)),
        "linear_sweep": SQUARE.linear_sweep(height=10),
        "rotate_sweep": PROFILE.rotate_sweep(angle=360),
        "spiral_sweep": PROFILE.spiral_sweep(height=20, radius=12, turns=2),
        "sweep": SQUARE.sweep([[[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, z], [0, 0, 0, 1]] for z in (0, 5, 10)]),
        "Bezier.sweep": Bezier([[0, 0, 0], [0, 0, 10], [10, 5, 12], [14, 2, 6]]).sweep(
            [[math.cos(a), math.sin(a)] for a in [i * math.pi / 6 for i in range(12)]], splinesteps=8
        ),
    }


@pytest.mark.parametrize(("name", "swept"), list(_family().items()))
def test_every_sweep_returns_a_solid(name: str, swept: object) -> None:
    """A sweep hands back a shape, not a mesh plus an incantation (SPEC S-19a)."""
    assert isinstance(swept, Solid), f"{name} returned {type(swept).__name__}"
    assert all(extent > 0 for extent in swept.bounds().size), name  # type: ignore[attr-defined]


@pytest.mark.parametrize(("name", "swept"), list(_family().items()))
def test_every_sweep_keeps_its_mesh_reachable(name: str, swept: object) -> None:
    """Returning a Solid must not cost the caller who wanted the mesh (SPEC C-8, S-19a)."""
    mesh = swept.vnf  # type: ignore[attr-defined]
    assert isinstance(mesh, VNF), name
    assert len(mesh.vertices) > 3, name
    assert len(mesh.faces) > 3, name


@pytest.mark.parametrize(("name", "swept"), list(_family().items()))
def test_every_sweep_winds_outward(name: str, swept: object) -> None:
    """One family, one winding (SPEC S-19c).

    `path_sweep` used to hand back the mirror of what `linear_sweep` did for the same box --
    volume -1000 against +1000 -- and an inside-out mesh given to polyhedron() exports fine on its
    own and then *adds* material where it was meant to cut. The existing render-level guard
    covered `linear_sweep` alone; this covers the siblings that were actually wrong.
    """
    assert swept.vnf.volume() > 0, f"{name} is wound inside out"  # type: ignore[attr-defined]


def test_the_same_box_two_ways_agrees_on_volume() -> None:
    """The exact comparison the winding bug failed: +1000 one way, -1000 the other."""
    by_extrusion = SQUARE.linear_sweep(height=10)
    by_path = Path3D([[0, 0, z] for z in range(11)]).path_sweep(SQUARE)
    assert by_extrusion.vnf.volume() == pytest.approx(1000.0)
    assert by_path.vnf.volume() == pytest.approx(1000.0)


@pytest.mark.parametrize(("name", "swept"), list(_family().items()))
def test_a_sweep_cuts_rather_than_fills(name: str, swept: object) -> None:
    """The consequence the winding guards: subtracting a sweep must *remove* material."""
    block = cuboid([80, 80, 80])
    cut = block - swept  # type: ignore[operator]
    assert cut.vnf.volume() < block.vnf.volume(), f"cutting with {name} added material"


def test_no_sweep_signature_carries_a_union_return() -> None:
    """A return type is one type; no arm is selected by one of the call's own flags (SPEC S-19b)."""
    from pybosl2.skin import Sweepable

    offenders = []
    for name in ("path_sweep", "path_sweep2d", "linear_sweep", "rotate_sweep", "spiral_sweep", "sweep"):
        annotation = str(inspect.signature(getattr(Sweepable, name)).return_annotation)
        if "|" in annotation:
            offenders.append(f"{name} -> {annotation}")
    assert not offenders, "; ".join(offenders)


def test_the_transforms_flag_is_its_own_function() -> None:
    """`path_sweep(..., transforms=True)` is what made the union unavoidable (SPEC S-19b)."""
    path = Path3D([[0, 0, 0], [0, 0, 5], [0, 0, 10]])
    assert "transforms" not in inspect.signature(path.path_sweep).parameters

    frames = path.path_sweep_transforms()
    assert len(frames) == 3
    assert all(len(row) == 4 and all(len(cell) == 4 for cell in [row]) for row in frames[0])


def test_bezier_has_its_own_transforms_method() -> None:
    """A bezier's analytic tangents are not a path's sampled frames, so it needs its own."""
    curve = Bezier([[0, 0, 5], [0, 0, 10], [15, 7, 9], [17, 2, 4]])
    assert "transforms" not in inspect.signature(curve.sweep).parameters
    frames = curve.sweep_transforms(splinesteps=4)
    assert len(frames) == 5

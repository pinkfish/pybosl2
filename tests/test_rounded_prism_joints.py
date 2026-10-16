# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""A rounding joint removes material, and the two ends round alike (SPEC S-2b).

Two measured anomalies in `rounded_prism`, both recorded as `strict=True` xfails rather than
fixed, because the correct behaviour is a question about BOSL2's `rounded_prism` semantics and
guessing one is how T89's mask profiles and T100's reverted sweep went wrong.

**A bigger joint adds material past a point.** On a 20x20 square prism 20 high, with equal top and
bottom joints:

======  ========
joint   volume
======  ========
0.01    7984.02
3.00    4615.47
6.00    3740.64
7.00    3817.74
9.00    4233.53
======  ========

It falls to a minimum at 6 and then climbs. A rounding cannot add material: past some joint size
the surfaces must be self-intersecting, and BOSL2 validates that the joints fit rather than
building it. What the exact limit should be is not derivable from the outside -- 7 and 9 both fit
inside the height and the half-width -- so the threshold is not invented here.

**The two ends do not round alike.** Rounding only the top by 2 removes 138mm^3; rounding only the
bottom by 2 removes 2720mm^3, twenty times as much. Mirrored in z the two point sets do not match.
The docstrings say "Joint distance at the top" and "at the bottom", so nothing documents a
difference, and with the joints *equal* the solid is properly z-mirror symmetric -- so the code is
self-consistent under simultaneous mirroring and the two parameters nonetheless differ in scale.
Which of the two is right is the part that would be a guess.

What this file does assert positively: both joints are live, both aliases work, and the solid is
symmetric when the joints match. Those hold, and a regression in them is a separate failure from
the two anomalies.
"""

from __future__ import annotations

import numpy as np
import pytest

from pybosl2 import use_defaults
from pybosl2.path2d import Path2D

FACETS = 32
HEIGHT = 20.0
SIDE = 10.0

#: Small enough to be a rounding rather than a reshaping, so the side edges are out of the way.
SIDE_JOINT = 0.01

SQUARE = Path2D([[-SIDE, -SIDE], [SIDE, -SIDE], [SIDE, SIDE], [-SIDE, SIDE]], closed=True)


def _mesh(**joints: float) -> tuple[np.ndarray, float]:
    with use_defaults(fn=FACETS):
        mesh = SQUARE.rounded_prism(height=HEIGHT, joint_sides=SIDE_JOINT, **joints).vnf()
    points = np.asarray([[float(c) for c in p] for p in mesh.vertices], dtype=float)
    return points, float(mesh.volume())


def _volume(**joints: float) -> float:
    return _mesh(**joints)[1]


@pytest.mark.xfail(strict=True, reason="volume climbs again past joint=6; see the module docstring")
@pytest.mark.parametrize("joint", [7.0, 8.0, 9.0])
def test_a_bigger_joint_never_adds_material(joint: float) -> None:
    """SPEC S-2b: a rounding removes the corner, so the solid can only shrink."""
    smaller = _volume(joint_top=6.0, joint_bottom=6.0)
    bigger = _volume(joint_top=joint, joint_bottom=joint)
    assert bigger < smaller, (
        f"joint={joint} gives {bigger:.2f} where joint=6 gives {smaller:.2f}. A larger rounding "
        f"cannot add material, so the surfaces are self-intersecting and the call should refuse "
        f"(BOSL2 validates that the joints fit)"
    )


@pytest.mark.xfail(strict=True, reason="the bottom joint removes ~20x the top joint's material; see the docstring")
@pytest.mark.parametrize("joint", [2.0, 5.0, 8.0])
def test_the_two_ends_round_alike(joint: float) -> None:
    """SPEC S-2b: "joint distance at the top" and "at the bottom" document no difference."""
    top_only, _ = _mesh(joint_top=joint, joint_bottom=SIDE_JOINT)
    bottom_only, _ = _mesh(joint_top=SIDE_JOINT, joint_bottom=joint)
    mirrored = top_only.copy()
    mirrored[:, 2] = HEIGHT - mirrored[:, 2]
    left = np.array(sorted(map(tuple, np.round(mirrored, 3))))
    right = np.array(sorted(map(tuple, np.round(bottom_only, 3))))
    assert left.shape == right.shape, (
        f"the two ends mesh to different vertex counts for joint={joint}: {left.shape[0]} against {right.shape[0]}"
    )
    assert np.allclose(left, right, atol=1e-2), (
        f"rounding only the top by {joint} and only the bottom by {joint} are not mirror images: "
        f"{_volume(joint_top=joint, joint_bottom=SIDE_JOINT):.2f} against "
        f"{_volume(joint_top=SIDE_JOINT, joint_bottom=joint):.2f}"
    )


@pytest.mark.parametrize("joint", [2.0, 5.0, 8.0])
def test_equal_joints_give_a_symmetric_solid(joint: float) -> None:
    """This holds, and it is why the asymmetry above is not simply a sign error.

    The code mirrors correctly when both ends are asked for the same thing; the two parameters
    differ in scale, which is a narrower fault than "top and bottom are swapped".
    """
    points, _ = _mesh(joint_top=joint, joint_bottom=joint)
    mirrored = points.copy()
    mirrored[:, 2] = HEIGHT - mirrored[:, 2]
    left = np.array(sorted(map(tuple, np.round(points, 4))))
    right = np.array(sorted(map(tuple, np.round(mirrored, 4))))
    assert left.shape == right.shape, f"mirroring changed the vertex count at joint={joint}"
    assert np.allclose(left, right, atol=1e-3), (
        f"with joint_top = joint_bottom = {joint} the prism is not symmetric about mid-height"
    )


@pytest.mark.parametrize("joint", [1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
def test_a_joint_within_the_working_range_removes_material(joint: float) -> None:
    """Up to the point where it breaks down, the rounding behaves: monotone and shrinking."""
    plain = _volume(joint_top=SIDE_JOINT, joint_bottom=SIDE_JOINT)
    rounded = _volume(joint_top=joint, joint_bottom=joint)
    assert rounded < plain, f"joint={joint} gives {rounded:.2f}, no less than the unrounded {plain:.2f}"


def test_every_joint_parameter_and_alias_is_live() -> None:
    """None of the three joints, nor either BOSL2 alias, may be silently ignored (SPEC G-8)."""
    base = _volume(joint_top=2.0, joint_bottom=2.0)
    assert _volume(joint_top=4.0, joint_bottom=2.0) != base, "joint_top changes nothing"
    assert _volume(joint_top=2.0, joint_bottom=4.0) != base, "joint_bottom changes nothing"
    assert _volume(joint_top=2.0, joint_bot=4.0) == _volume(joint_top=2.0, joint_bottom=4.0), (
        "joint_bot is BOSL2's alias for joint_bottom and no longer matches it"
    )
    with use_defaults(fn=FACETS):
        wide = float(
            SQUARE.rounded_prism(height=HEIGHT, joint_top=2.0, joint_bottom=2.0, joint_sides=4.0).vnf().volume()
        )
    assert wide != base, "joint_sides changes nothing"

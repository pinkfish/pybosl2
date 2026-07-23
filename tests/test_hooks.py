# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2.hooks: the ring hook."""

import math
import pytest

from bosl2.hooks import Hooks, _circle_point_tangents
from bosl2.shapes3d import Bosl2Solid


def _bounds(s):
    return s._native_bounds()


def test_circle_point_tangents_lie_on_circle_and_are_tangent():
    cp = [0, 25]
    for t in _circle_point_tangents(25, cp, [25, 0]):
        assert math.dist(t, cp) == pytest.approx(25, abs=1e-6)  # on the circle
        # radius CT is perpendicular to the tangent line TP
        ct = (t[0] - cp[0], t[1] - cp[1])
        tp = (25 - t[0], 0 - t[1])
        assert ct[0] * tp[0] + ct[1] * tp[1] == pytest.approx(0, abs=1e-6)


def test_tangent_requires_external_point():
    with pytest.raises(ValueError):
        _circle_point_tangents(25, [0, 0], [10, 0])


def test_basic_ring_hook_envelope():
    lo, sz = _bounds(Hooks.ring_hook([50, 10], 25, or_=25, ir=20))
    assert tuple(round(v) for v in sz) == (50, 10, 50)  # width, depth, hole_z + or
    assert lo[2] == pytest.approx(0.0, abs=0.05)  # base rests on z=0


def test_ring_height_is_hole_z_plus_or():
    _, sz = _bounds(Hooks.ring_hook([50, 10], 40, or_=25, ir=20))
    assert sz[2] == pytest.approx(
        65.0, abs=0.5
    )  # faceted ring top sits just under hole_z + or


def test_wall_and_od_id_forms_equivalent():
    a = _bounds(Hooks.ring_hook([50, 10], 40, or_=25, wall=5))[1]
    b = _bounds(Hooks.ring_hook([50, 10], 40, od=50, id=40))[1]
    assert [round(v, 1) for v in a] == [round(v, 1) for v in b]


@pytest.mark.parametrize(
    "kw",
    [
        dict(base_size=[50, 10], hole_z=25, or_=25, ir=0),  # solid paddle
        dict(base_size=[50, 10], hole_z=25, or_=25, ir=15, hole="D"),  # D hole
        dict(base_size=[40, 10], hole_z=25, or_=25, ir=0),  # narrow base
    ],
)
def test_variants_build(kw):
    assert isinstance(Hooks.ring_hook(**kw), Bosl2Solid)


def test_custom_hole_path_builds():
    oct8 = [
        [
            10 * math.cos(math.radians(22.5 + 45 * k)),
            10 * math.sin(math.radians(22.5 + 45 * k)),
        ]
        for k in range(8)
    ]
    assert isinstance(Hooks.ring_hook([50, 20], 30, or_=25, hole=oct8), Bosl2Solid)


def test_must_define_exactly_two_of_or_ir_wall():
    with pytest.raises(ValueError):
        Hooks.ring_hook([50, 10], 25, or_=25)  # only one given


def test_base_corners_must_be_outside_cylinder():
    with pytest.raises(ValueError):
        Hooks.ring_hook(
            [10, 10], 5, or_=25, ir=0
        )  # corners inside cylinder, no tangent


def test_circle_hole_must_fit_above_base():
    with pytest.raises(ValueError):
        Hooks.ring_hook(
            [50, 10], 10, or_=25, ir=20
        )  # ir >= hole_z: hole pokes out the base


def test_custom_hole_rejects_ir_and_wall():
    with pytest.raises(ValueError):
        Hooks.ring_hook([50, 20], 30, or_=25, ir=10, hole=[[1, 0], [0, 1], [-1, 0]])


def test_fillet_not_yet_supported():
    with pytest.raises(NotImplementedError):
        Hooks.ring_hook([50, 10], 25, or_=25, ir=0, fillet=3)

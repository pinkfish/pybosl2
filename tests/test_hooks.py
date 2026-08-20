# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.hooks: the ring hook."""

import math

import pytest

from pybosl2.parts.hooks import HoleType, RingHook, _circle_point_tangents
from pybosl2.shapes3d import Bosl2Solid


def _bounds(s: Bosl2Solid) -> tuple[list[float], list[float]]:
    return s._native_bounds()  # type: ignore[return-value]


def test_circle_point_tangents_lie_on_circle_and_are_tangent() -> None:
    center = [0, 25]
    for t in _circle_point_tangents(25, center, [25, 0]):  # type: ignore[arg-type]
        assert math.dist(t, center) == pytest.approx(25, abs=1e-6)  # on the circle
        # radius CT is perpendicular to the tangent line TP
        ct = (t[0] - center[0], t[1] - center[1])
        tp = (25 - t[0], 0 - t[1])
        assert ct[0] * tp[0] + ct[1] * tp[1] == pytest.approx(0, abs=1e-6)


def test_tangent_requires_external_point() -> None:
    with pytest.raises(ValueError, match="point must be outside the circle"):
        _circle_point_tangents(25, [0, 0], [10, 0])


def test_basic_ring_hook_envelope() -> None:
    lo, sz = _bounds(RingHook([50, 10], 25, outer_radius=25, inner_radius=20).shape)
    assert tuple(round(v) for v in sz) == (
        50,
        10,
        50,
    )  # width, depth, hole_z + outer_radius
    assert lo[2] == pytest.approx(0.0, abs=0.05)  # base rests on z=0


def test_ring_height_is_hole_z_plus_or() -> None:
    _, sz = _bounds(RingHook([50, 10], 40, outer_radius=25, inner_radius=20).shape)
    assert sz[2] == pytest.approx(65.0, abs=0.5)  # faceted ring top sits just under hole_z + outer_radius


def test_wall_and_od_id_forms_equivalent() -> None:
    a = _bounds(RingHook([50, 10], 40, outer_radius=25, wall=5).shape)[1]
    b = _bounds(RingHook([50, 10], 40, outer_diameter=50, inner_diameter=40).shape)[1]
    assert [round(v, 1) for v in a] == [round(v, 1) for v in b]


@pytest.mark.parametrize(
    "kw",
    [
        {"base_size": [50, 10], "hole_z": 25, "outer_radius": 25, "inner_radius": 0},  # solid paddle
        {"base_size": [50, 10], "hole_z": 25, "outer_radius": 25, "inner_radius": 15, "hole": HoleType.D},  # D hole
        {"base_size": [40, 10], "hole_z": 25, "outer_radius": 25, "inner_radius": 0},  # narrow base
    ],
)
def test_variants_build(kw: dict[str, object]) -> None:
    assert isinstance(RingHook(**kw).shape, Bosl2Solid)  # type: ignore[arg-type]


def test_custom_hole_path_builds() -> None:
    oct8 = [
        [
            10 * math.cos(math.radians(22.5 + 45 * k)),
            10 * math.sin(math.radians(22.5 + 45 * k)),
        ]
        for k in range(8)
    ]
    assert isinstance(RingHook([50, 20], 30, outer_radius=25, hole=oct8).shape, Bosl2Solid)  # type: ignore[arg-type]


def test_must_define_exactly_two_of_or_ir_wall() -> None:
    with pytest.raises(ValueError, match="define exactly two"):
        RingHook([50, 10], 25, outer_radius=25)  # only one given


def test_base_corners_must_be_outside_cylinder() -> None:
    with pytest.raises(ValueError, match="base corners must be outside the cylinder"):
        RingHook([10, 10], 5, outer_radius=25, inner_radius=0)  # corners inside cylinder, no tangent


def test_circle_hole_must_fit_above_base() -> None:
    with pytest.raises(ValueError, match=r"inner_radius \+ hole_rounding must be less than hole_z"):
        RingHook([50, 10], 10, outer_radius=25, inner_radius=20)  # inner_radius >= hole_z: hole pokes out the base


def test_custom_hole_rejects_ir_and_wall() -> None:
    with pytest.raises(ValueError, match="cannot give inner_radius.*with a custom hole"):
        RingHook(
            [50, 20],
            30,
            outer_radius=25,
            inner_radius=10,
            hole=[[1, 0], [0, 1], [-1, 0]],  # type: ignore[arg-type]
        )


def test_fillet_not_yet_supported() -> None:
    with pytest.raises(NotImplementedError):
        RingHook([50, 10], 25, outer_radius=25, inner_radius=0, fillet=3)

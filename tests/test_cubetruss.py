# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2.cubetruss: segment/truss geometry and the cubetruss_dist length helper."""

import pytest

from bosl2.cubetruss import CubeTruss as CT
from bosl2.shapes3d import Bosl2Solid


def _size(solid):
    _min, size = solid._native_bounds()
    return size


def test_cubetruss_dist():
    assert CT.cubetruss_dist(3, 1) == 3 * 27 + 3  # 30-strut default: 3*(30-3)+1*3
    assert CT.cubetruss_dist(1, 0) == 27
    assert CT.cubetruss_dist(2, 1, size=40, strut=4) == 2 * 36 + 4


@pytest.mark.parametrize(
    "kw,expect",
    [
        ({}, 30.0),
        ({"bracing": False}, 30.0),
        ({"size": 40}, 40.0),
        ({"strut": 5}, 30.0),
    ],
)
def test_segment_is_a_cube(kw, expect):
    seg = CT.cubetruss_segment(**kw)
    assert isinstance(seg, Bosl2Solid)
    w, l, h = _size(seg)
    assert w == pytest.approx(expect, abs=0.01)
    assert l == pytest.approx(expect, abs=0.01)
    assert h == pytest.approx(expect, abs=0.01)


def test_cubetruss_length_matches_dist():
    truss = CT.cubetruss(extents=3)
    assert isinstance(truss, Bosl2Solid)
    w, l, h = _size(truss)
    assert l == pytest.approx(CT.cubetruss_dist(3, 1), abs=0.5)
    assert w == pytest.approx(30, abs=0.5)


def test_cubetruss_3d_extents():
    truss = CT.cubetruss(extents=[2, 3, 2])
    w, l, h = _size(truss)
    assert w == pytest.approx(CT.cubetruss_dist(2, 1), abs=0.5)
    assert l == pytest.approx(CT.cubetruss_dist(3, 1), abs=0.5)
    assert h == pytest.approx(CT.cubetruss_dist(2, 1), abs=0.5)


def test_bracing_adds_material():
    braced = CT.cubetruss_segment(bracing=True)
    plain = CT.cubetruss_segment(bracing=False)
    # both are the same 30mm cube envelope; bracing changes interior, not bounds
    assert _size(braced)[0] == pytest.approx(_size(plain)[0], abs=0.01)


def test_corner_symmetric_extents():
    c = CT.cubetruss_corner(extents=2)
    w, l, h = _size(c)
    expect = CT.cubetruss_dist(3, 1)  # arm 2 + central 1
    for v in (w, l, h):
        assert v == pytest.approx(expect, abs=0.5)


def test_corner_asymmetric_extents():
    # [+X, +Y, -X, -Y, +Z] arm counts
    c = CT.cubetruss_corner(extents=[2, 3, 0, 0, 1])
    w, l, h = _size(c)
    assert w == pytest.approx(CT.cubetruss_dist(2 + 1 + 0, 1), abs=0.5)
    assert l == pytest.approx(CT.cubetruss_dist(3 + 1 + 0, 1), abs=0.5)
    assert h == pytest.approx(CT.cubetruss_dist(1 + 1, 1), abs=0.5)


@pytest.mark.parametrize(
    "extents,ex,ey,ez",
    [
        (1, 1, 1, 1),
        (2, 1, 1, 2),
        (3, 1, 1, 3),
        ([2, 2, 3], 2, 2, 3),
    ],
)
def test_support_envelope(extents, ex, ey, ez):
    s = CT.cubetruss_support(extents=extents)
    assert isinstance(s, Bosl2Solid)
    w, l, h = _size(s)
    assert w == pytest.approx((30 - 3) * ex + 3, abs=0.5)  # width across the X copies
    assert h == pytest.approx(
        (30 - 3) * ez + 3, abs=0.5
    )  # full height (before the diagonal)


# -- clip accessories ---------------------------------------------------------


@pytest.mark.parametrize(
    "obj",
    [
        CT.cubetruss_clip(extents=1),
        CT.cubetruss_clip(extents=2, slop=0.1),
        CT.cubetruss_uclip(dual=True),
        CT.cubetruss_uclip(dual=False),
        CT.cubetruss_foot(w=1),
        CT.cubetruss_foot(w=3),
        CT.cubetruss_joiner(w=1, vert=True),
        CT.cubetruss_joiner(w=1, vert=False),
    ],
)
def test_accessory_builds(obj):
    assert isinstance(obj, Bosl2Solid)


def test_foot_span_scales_with_w():
    assert _size(CT.cubetruss_foot(w=3))[0] > _size(CT.cubetruss_foot(w=1))[0]


def test_uclip_dual_wider_than_single():
    assert (
        _size(CT.cubetruss_uclip(dual=True))[0]
        > _size(CT.cubetruss_uclip(dual=False))[0]
    )


def test_clips_add_material_on_the_named_face():
    from bosl2.constants import FRONT, RIGHT

    plain = _size(CT.cubetruss(extents=3))
    front = _size(CT.cubetruss(extents=3, clips=FRONT))
    right = _size(CT.cubetruss(extents=[2, 3], clips=RIGHT))
    assert front[1] > plain[1]  # FRONT clip extends +/-Y
    assert right[0] > _size(CT.cubetruss(extents=[2, 3]))[0]  # RIGHT clip extends +/-X


def test_clips_none_matches_plain():
    assert _size(CT.cubetruss(extents=3, clips=None)) == pytest.approx(
        _size(CT.cubetruss(extents=3))
    )

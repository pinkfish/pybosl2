# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.cubetruss: segment/truss geometry and the cubetruss_dist length helper."""

import pytest

from pybosl2.parts.cubetruss import CubeTruss
from pybosl2.shapes3d import Bosl2Solid


def _size(solid):  # type: ignore[no-untyped-def]
    _min, size = solid._native_bounds()
    return size


def test_cubetruss_dist() -> None:
    assert CubeTruss.cubetruss_dist(3, 1) == 3 * 27 + 3  # 30-strut default: 3*(30-3)+1*3
    assert CubeTruss.cubetruss_dist(1, 0) == 27
    assert CubeTruss.cubetruss_dist(2, 1, size=40, strut=4) == 2 * 36 + 4


@pytest.mark.parametrize(
    ("kw", "expect"),
    [
        ({}, 30.0),
        ({"bracing": False}, 30.0),
        ({"size": 40}, 40.0),
        ({"strut": 5}, 30.0),
    ],
)
def test_segment_is_a_cube(kw, expect) -> None:  # type: ignore[no-untyped-def]
    seg = CubeTruss.cubetruss_segment(**kw, fn=None, fa=None, fs=None)
    assert isinstance(seg, Bosl2Solid)
    w, length, height = _size(seg)  # type: ignore[no-untyped-call]
    assert w == pytest.approx(expect, abs=0.01)
    assert length == pytest.approx(expect, abs=0.01)
    assert height == pytest.approx(expect, abs=0.01)


def test_cubetruss_length_matches_dist() -> None:
    truss = CubeTruss.cubetruss(extents=3, fn=None, fa=None, fs=None)
    assert isinstance(truss, Bosl2Solid)
    w, length, height = _size(truss)  # type: ignore[no-untyped-call]
    assert length == pytest.approx(CubeTruss.cubetruss_dist(3, 1), abs=0.5)
    assert w == pytest.approx(30, abs=0.5)


def test_cubetruss_3d_extents() -> None:
    truss = CubeTruss.cubetruss(extents=[2, 3, 2], fn=None, fa=None, fs=None)
    w, length, height = _size(truss)  # type: ignore[no-untyped-call]
    assert w == pytest.approx(CubeTruss.cubetruss_dist(2, 1), abs=0.5)
    assert length == pytest.approx(CubeTruss.cubetruss_dist(3, 1), abs=0.5)
    assert height == pytest.approx(CubeTruss.cubetruss_dist(2, 1), abs=0.5)


def test_bracing_adds_material() -> None:
    braced = CubeTruss.cubetruss_segment(bracing=True, fn=None, fa=None, fs=None)
    plain = CubeTruss.cubetruss_segment(bracing=False, fn=None, fa=None, fs=None)
    # both are the same 30mm cube envelope; bracing changes interior, not bounds
    assert _size(braced)[0] == pytest.approx(_size(plain)[0], abs=0.01)  # type: ignore[no-untyped-call]


def test_corner_symmetric_extents() -> None:
    c = CubeTruss.cubetruss_corner(extents=2, fn=None, fa=None, fs=None)
    w, length, height = _size(c)  # type: ignore[no-untyped-call]
    expect = CubeTruss.cubetruss_dist(3, 1)  # arm 2 + central 1
    for v in (w, length, height):
        assert v == pytest.approx(expect, abs=0.5)


def test_corner_asymmetric_extents() -> None:
    # [+X, +Y, -X, -Y, +Z] arm counts
    c = CubeTruss.cubetruss_corner(extents=[2, 3, 0, 0, 1], fn=None, fa=None, fs=None)
    w, length, height = _size(c)  # type: ignore[no-untyped-call]
    assert w == pytest.approx(CubeTruss.cubetruss_dist(2 + 1 + 0, 1), abs=0.5)
    assert length == pytest.approx(CubeTruss.cubetruss_dist(3 + 1 + 0, 1), abs=0.5)
    assert height == pytest.approx(CubeTruss.cubetruss_dist(1 + 1, 1), abs=0.5)


@pytest.mark.parametrize(
    ("extents", "ex", "ez"),
    [
        (1, 1, 1),
        (2, 1, 2),
        (3, 1, 3),
        ([2, 2, 3], 2, 3),
    ],
)
def test_support_envelope(extents, ex, ez) -> None:  # type: ignore[no-untyped-def]
    s = CubeTruss.cubetruss_support(extents=extents, fn=None, fa=None, fs=None)
    assert isinstance(s, Bosl2Solid)
    w, length, height = _size(s)  # type: ignore[no-untyped-call]
    assert w == pytest.approx((30 - 3) * ex + 3, abs=0.5)  # width across the X copies
    assert height == pytest.approx((30 - 3) * ez + 3, abs=0.5)  # full height (before the diagonal)


# -- clip accessories ---------------------------------------------------------


@pytest.mark.parametrize(
    "obj",
    [
        CubeTruss.cubetruss_clip(extents=1, fn=None, fa=None, fs=None),
        CubeTruss.cubetruss_clip(extents=2, slop=0.1, fn=None, fa=None, fs=None),
        CubeTruss.cubetruss_uclip(dual=True, fn=None, fa=None, fs=None),
        CubeTruss.cubetruss_uclip(dual=False, fn=None, fa=None, fs=None),
        CubeTruss.cubetruss_foot(w=1, fn=None, fa=None, fs=None),
        CubeTruss.cubetruss_foot(w=3, fn=None, fa=None, fs=None),
        CubeTruss.cubetruss_joiner(w=1, vert=True, fn=None, fa=None, fs=None),
        CubeTruss.cubetruss_joiner(w=1, vert=False, fn=None, fa=None, fs=None),
    ],
)
def test_accessory_builds(obj) -> None:  # type: ignore[no-untyped-def]
    assert isinstance(obj, Bosl2Solid)


def test_foot_span_scales_with_w() -> None:
    assert (
        _size(CubeTruss.cubetruss_foot(w=3, fn=None, fa=None, fs=None))[0]  # type: ignore[no-untyped-call]
        > _size(CubeTruss.cubetruss_foot(w=1, fn=None, fa=None, fs=None))[0]  # type: ignore[no-untyped-call]
    )


def test_uclip_dual_wider_than_single() -> None:
    assert (
        _size(CubeTruss.cubetruss_uclip(dual=True, fn=None, fa=None, fs=None))[0]  # type: ignore[no-untyped-call]
        > _size(CubeTruss.cubetruss_uclip(dual=False, fn=None, fa=None, fs=None))[0]  # type: ignore[no-untyped-call]
    )


def test_clips_add_material_on_the_named_face() -> None:
    from pybosl2.constants import FRONT, RIGHT

    plain = _size(CubeTruss.cubetruss(extents=3, fn=None, fa=None, fs=None))  # type: ignore[no-untyped-call]
    front = _size(CubeTruss.cubetruss(extents=3, clips=FRONT, fn=None, fa=None, fs=None))  # type: ignore[arg-type, no-untyped-call]
    right = _size(CubeTruss.cubetruss(extents=[2, 3], clips=RIGHT, fn=None, fa=None, fs=None))  # type: ignore[arg-type, no-untyped-call]
    assert front[1] > plain[1]  # FRONT clip extends +/-Y
    plain_right = _size(CubeTruss.cubetruss(extents=[2, 3], fn=None, fa=None, fs=None))[0]  # type: ignore[no-untyped-call]
    assert right[0] > plain_right  # RIGHT clip extends +/-X


def test_clips_none_matches_plain() -> None:
    assert _size(CubeTruss.cubetruss(extents=3, clips=None, fn=None, fa=None, fs=None)) == pytest.approx(  # type: ignore[no-untyped-call]
        _size(CubeTruss.cubetruss(extents=3, fn=None, fa=None, fs=None))  # type: ignore[no-untyped-call]
    )

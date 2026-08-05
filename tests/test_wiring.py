# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.wiring: routed wire bundles."""

import itertools
import math

import numpy as np
import pytest

from pybosl2.parts.wiring import _WIRE_COLORS, Wiring, _hex_offset_ring, _hex_offsets, _segs
from pybosl2.shapes3d import Bosl2Solid

_PATH = [[50, 0, -50], [50, 50, -50], [0, 50, -50], [0, 0, -50], [0, 0, 0]]


def test_hex_ring_counts() -> None:
    assert _hex_offset_ring(2, 0) == [[0.0, 0.0]]
    assert len(_hex_offset_ring(2, 1)) == 6
    assert len(_hex_offset_ring(2, 2)) == 12  # 6 * lev


def test_hex_ring_spacing() -> None:
    ring = _hex_offset_ring(2.0, 1)
    for x, y in ring:
        assert math.hypot(x, y) == pytest.approx(2.0)  # ring 1 sits at radius d


def test_hex_offsets_fills_ring() -> None:
    off = _hex_offsets(13, 2.0)
    assert len(off) == 19  # 1 + 6 + 12, filled out
    assert _hex_offsets(1, 2.0) == [[0.0, 0.0]]


def test_hex_offsets_min_spacing_is_d() -> None:
    pts = np.array(_hex_offsets(19, 2.0))
    dmin = min(np.linalg.norm(a - b) for a, b in itertools.combinations(pts, 2))
    assert dmin == pytest.approx(2.0, abs=1e-6)  # nearest neighbours are exactly d apart


def test_public_hex_offsets_matches_private() -> None:
    assert Wiring.hex_offsets(7, 3.0) == _hex_offsets(7, 3.0)


@pytest.mark.parametrize("wires", [1, 7, 13, 30])
def test_wire_bundle_builds(wires: int) -> None:
    assert isinstance(Wiring.wire_bundle(_PATH, wires=wires, rounding=10), Bosl2Solid)  # type: ignore[arg-type]


def test_wire_bundle_grows_with_wire_count() -> None:
    def w(n: int) -> float:
        return Wiring.wire_bundle(_PATH, wires=n, rounding=10)._native_bounds()[1][0]  # type: ignore[arg-type, index]

    assert w(1) < w(7) < w(13)  # bundle cross-section widens


def test_wire_bundle_requires_a_wire() -> None:
    with pytest.raises(ValueError, match="needs at least one wire"):
        Wiring.wire_bundle(_PATH, wires=0)  # type: ignore[arg-type]


# ── _segs tests ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("radius", "expected"),
    [
        (0.001, 5),
        (0.5, 5),
        (1.0, 5),
        (2.0, 7),
        (5.0, 16),
        (10.0, 30),
        (20.0, 30),
    ],
)
def test_segs_values(radius: float, expected: int) -> None:
    assert _segs(radius) == expected


def test_segs_minimum() -> None:
    assert _segs(0.001) == 5  # max(5, ...) floor


# ── _hex_offset_ring additional tests ─────────────────────────────────────


@pytest.mark.parametrize("lev", [0, 1, 2, 3, 5])
def test_hex_ring_lev_counts(lev: int) -> None:
    ring = _hex_offset_ring(3.0, lev)
    if lev == 0:
        assert ring == [[0.0, 0.0]]
    else:
        assert len(ring) == 6 * lev


def test_hex_ring_lev0_always_origin() -> None:
    for d in [1.0, 2.0, 5.0, 100.0]:
        assert _hex_offset_ring(d, 0) == [[0.0, 0.0]]


def test_hex_ring_lev2_radius() -> None:
    ring = _hex_offset_ring(3.0, 2)
    # All points should be within circumradius 2*d = 6.0 of origin
    for x, y in ring:
        assert math.hypot(x, y) <= 6.0 + 1e-9


# ── _hex_offsets additional tests ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("n", "expected_len"),
    [(1, 1), (2, 7), (7, 7), (8, 19), (19, 19), (20, 37), (38, 61)],
)
def test_hex_offsets_fills_complete_rings(n: int, expected_len: int) -> None:
    assert len(_hex_offsets(n, 2.0)) == expected_len


# ── _WIRE_COLORS tests ───────────────────────────────────────────────────


def test_wire_colors_count() -> None:
    assert len(_WIRE_COLORS) == 17


def test_wire_colors_all_rgb_triples() -> None:
    for color in _WIRE_COLORS:
        assert isinstance(color, list)
        assert len(color) == 3
        assert all(0.0 <= v <= 1.0 for v in color)

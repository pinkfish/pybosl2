# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2.wiring: routed wire bundles."""

import itertools
import math

import numpy as np
import pytest

from bosl2.wiring import Wiring, _hex_offset_ring, _hex_offsets
from bosl2.shapes3d import Bosl2Solid

_PATH = [[50, 0, -50], [50, 50, -50], [0, 50, -50], [0, 0, -50], [0, 0, 0]]


def test_hex_ring_counts():
    assert _hex_offset_ring(2, 0) == [[0.0, 0.0]]
    assert len(_hex_offset_ring(2, 1)) == 6
    assert len(_hex_offset_ring(2, 2)) == 12          # 6 * lev


def test_hex_ring_spacing():
    ring = _hex_offset_ring(2.0, 1)
    for x, y in ring:
        assert math.hypot(x, y) == pytest.approx(2.0)  # ring 1 sits at radius d


def test_hex_offsets_fills_ring():
    off = _hex_offsets(13, 2.0)
    assert len(off) == 19                              # 1 + 6 + 12, filled out
    assert _hex_offsets(1, 2.0) == [[0.0, 0.0]]


def test_hex_offsets_min_spacing_is_d():
    pts = np.array(_hex_offsets(19, 2.0))
    dmin = min(np.linalg.norm(a - b) for a, b in itertools.combinations(pts, 2))
    assert dmin == pytest.approx(2.0, abs=1e-6)        # nearest neighbours are exactly d apart


def test_public_hex_offsets_matches_private():
    assert Wiring.hex_offsets(7, 3.0) == _hex_offsets(7, 3.0)


@pytest.mark.parametrize("wires", [1, 7, 13, 30])
def test_wire_bundle_builds(wires):
    assert isinstance(Wiring.wire_bundle(_PATH, wires=wires, rounding=10), Bosl2Solid)


def test_wire_bundle_grows_with_wire_count():
    def w(n):
        return Wiring.wire_bundle(_PATH, wires=n, rounding=10)._native_bounds()[1][0]
    assert w(1) < w(7) < w(13)                         # bundle cross-section widens


def test_wire_bundle_requires_a_wire():
    with pytest.raises(ValueError):
        Wiring.wire_bundle(_PATH, wires=0)

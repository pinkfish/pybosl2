# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2.bottlecaps: the PCO-1810 / PCO-1881 bottle necks and caps. Each builder is
checked for the right overall envelope (width and height) against the transcribed BOSL2 dimensions,
and that it returns a Bosl2Solid."""

import pytest

from bosl2.bottlecaps import BottleCaps as BC
from bosl2.shapes3d import Bosl2Solid


def _size(solid):
    """Overall (width_x, width_y, height_z) of a solid's real mesh."""
    _min, size = solid._native_bounds()
    return size


def test_pco1810_neck_envelope():
    neck = BC.pco1810_neck()
    assert isinstance(neck, Bosl2Solid)
    w, _wy, hgt = _size(neck)
    assert w == pytest.approx(33.0, abs=0.2)  # support ring diameter
    assert hgt == pytest.approx(21.0 + 5.0, abs=0.2)  # support_h + neck_h


def test_pco1881_neck_envelope():
    neck = BC.pco1881_neck()
    assert isinstance(neck, Bosl2Solid)
    w, _wy, hgt = _size(neck)
    assert w == pytest.approx(33.0, abs=0.2)
    assert hgt == pytest.approx(17.0 + 5.0, abs=0.2)


def test_pco1810_cap_envelope():
    cap = BC.pco1810_cap(wall=2)
    assert isinstance(cap, Bosl2Solid)
    w, _wy, hgt = _size(cap)
    assert w == pytest.approx(28.58 + 2 * 2, abs=0.3)  # cap_id + 2*wall
    assert hgt == pytest.approx(14.10 + 2, abs=0.3)  # tamper_ring_h + wall


def test_pco1881_cap_envelope():
    cap = BC.pco1881_cap(wall=2)
    assert isinstance(cap, Bosl2Solid)
    w, _wy, hgt = _size(cap)
    assert w == pytest.approx(28.58 + 2 * 2, abs=0.3)
    assert hgt == pytest.approx(11.20 + 2, abs=0.3)


def test_wall_thickness_changes_cap_size():
    thin, thick = BC.pco1881_cap(wall=1), BC.pco1881_cap(wall=3)
    assert _size(thick)[0] > _size(thin)[0]
    assert _size(thick)[2] > _size(thin)[2]


def test_texture_falls_back_to_plain():
    # Textures aren't supported by this port; the builder still succeeds (plain wall).
    for tex in ("none", "knurled", "ribbed"):
        assert isinstance(BC.pco1881_cap(texture=tex), Bosl2Solid)


def test_neck_and_cap_are_distinct_pieces():
    # Sanity: a cap is wider than tall here, a neck taller than the cap.
    assert _size(BC.pco1810_neck())[2] > _size(BC.pco1810_cap())[2]

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.bottlecaps: the PCO-1810 / PCO-1881 bottle necks and caps. Each builder is
checked for the right overall envelope (width and height) against the transcribed BOSL2 dimensions,
and that it returns a Bosl2Solid."""

import pytest

from pybosl2.parts.bottlecaps import BottleCaps
from pybosl2.shapes3d import Bosl2Solid


def _size(solid: Bosl2Solid) -> list[float]:
    """Overall (width_x, width_y, height_z) of a solid's real mesh."""
    _min, size = solid._native_bounds()  # type: ignore[misc]
    return size


def test_pco1810_neck_envelope() -> None:
    neck = BottleCaps.pco1810_neck(fn=None, fa=None, fs=None)
    assert isinstance(neck, Bosl2Solid)
    w, _wy, hgt = _size(neck)
    assert w == pytest.approx(33.0, abs=0.2)  # support ring diameter
    assert hgt == pytest.approx(21.0 + 5.0, abs=0.2)  # support_h + neck_h


def test_pco1881_neck_envelope() -> None:
    neck = BottleCaps.pco1881_neck(fn=None, fa=None, fs=None)
    assert isinstance(neck, Bosl2Solid)
    w, _wy, hgt = _size(neck)
    assert w == pytest.approx(33.0, abs=0.2)
    assert hgt == pytest.approx(17.0 + 5.0, abs=0.2)


def test_pco1810_cap_envelope() -> None:
    cap = BottleCaps.pco1810_cap(wall=2, fn=None, fa=None, fs=None)
    assert isinstance(cap, Bosl2Solid)
    w, _wy, hgt = _size(cap)
    assert w == pytest.approx(28.58 + 2 * 2, abs=0.3)  # cap_id + 2*wall
    assert hgt == pytest.approx(14.10 + 2, abs=0.3)  # tamper_ring_h + wall


def test_pco1881_cap_envelope() -> None:
    cap = BottleCaps.pco1881_cap(wall=2, fn=None, fa=None, fs=None)
    assert isinstance(cap, Bosl2Solid)
    w, _wy, hgt = _size(cap)
    assert w == pytest.approx(28.58 + 2 * 2, abs=0.3)
    assert hgt == pytest.approx(11.20 + 2, abs=0.3)


def test_wall_thickness_changes_cap_size() -> None:
    thin = BottleCaps.pco1881_cap(wall=1, fn=None, fa=None, fs=None)
    thick = BottleCaps.pco1881_cap(wall=3, fn=None, fa=None, fs=None)
    assert _size(thick)[0] > _size(thin)[0]
    assert _size(thick)[2] > _size(thin)[2]


@pytest.mark.parametrize("texture", ["knurled", "ribbed"])
def test_texture_falls_back_to_plain(texture: str) -> None:
    """Textures aren't supported by this port, so a textured cap *is* the plain one.

    Not merely "the builder still succeeds": the fallback is only honest if the model that comes
    out is identical to the untextured cap, rather than something quietly half-textured.
    """
    plain = BottleCaps.pco1881_cap(texture="none", fn=None, fa=None, fs=None)
    textured = BottleCaps.pco1881_cap(texture=texture, fn=None, fa=None, fs=None)
    assert _size(textured) == pytest.approx(_size(plain))
    assert repr(textured) == repr(plain)


def test_neck_and_cap_are_distinct_pieces() -> None:
    # Sanity: a cap is wider than tall here, a neck taller than the cap.
    neck_h = _size(BottleCaps.pco1810_neck(fn=None, fa=None, fs=None))[2]
    cap_h = _size(BottleCaps.pco1810_cap(fn=None, fa=None, fs=None))[2]
    assert neck_h > cap_h

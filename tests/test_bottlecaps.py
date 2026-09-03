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


@pytest.mark.parametrize("texture", ["ribs", "checkers"])
def test_a_named_texture_is_cut_into_the_cap(texture: str) -> None:
    """The cap's grip is real geometry now (T39, SPEC S-35).

    This test used to assert the opposite -- that a textured cap *is* the plain one, because the
    port could not apply a texture. It was right to assert it rather than merely check the builder
    succeeded, and right to say so out loud: a documented fallback is still a silent no-op at the
    call site, which is what E-5 forbids and S-35 exists to prevent.
    """
    plain = BottleCaps.pco1881_cap(texture="none", fn=None, fa=None, fs=None)
    textured = BottleCaps.pco1881_cap(texture=texture, fn=None, fa=None, fs=None)
    assert _size(textured)[0] == pytest.approx(_size(plain)[0], abs=0.1), "the knurl is cut in, not grown on"
    assert textured.vnf().volume() < plain.vnf().volume(), "and it removes material"


def test_an_unknown_texture_names_the_ones_that_exist() -> None:
    """SPEC E-4: the refusal names the accepted spellings rather than falling back silently."""
    from pybosl2.exceptions import Bosl2ValueError

    with pytest.raises(Bosl2ValueError, match="available"):
        BottleCaps.pco1881_cap(texture="knurled", fn=None, fa=None, fs=None)


def test_neck_and_cap_are_distinct_pieces() -> None:
    # Sanity: a cap is wider than tall here, a neck taller than the cap.
    neck_h = _size(BottleCaps.pco1810_neck(fn=None, fa=None, fs=None))[2]
    cap_h = _size(BottleCaps.pco1810_cap(fn=None, fa=None, fs=None))[2]
    assert neck_h > cap_h

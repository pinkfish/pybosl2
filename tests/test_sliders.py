# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.sliders: V-groove sliders and railSliders."""

import pytest

from pybosl2.parts.sliders import Rail, Slider
from pybosl2.shapes3d import Bosl2Solid


def _size(solid: Bosl2Solid) -> list[float]:
    _min, size = solid._native_bounds()  # type: ignore[misc]
    return size


@pytest.mark.parametrize(
    "kw",
    [
        {"l": 30, "base": 10, "wall": 4, "slop": 0.2},
        {"l": 40, "w": 14, "h": 12, "base": 8, "wall": 5},
    ],
)
def test_slider_builds(kw: dict[str, object]) -> None:
    assert isinstance(Slider(**kw, fn=None, fa=None, fs=None).shape, Bosl2Solid)  # type: ignore[arg-type]


def test_rail_envelope() -> None:
    radius = Rail(l=100, w=10, h=10).shape
    assert isinstance(radius, Bosl2Solid)
    w, length, height = _size(radius)
    assert w == pytest.approx(10, abs=0.1)
    assert length == pytest.approx(100, abs=0.1)
    assert height == pytest.approx(10, abs=0.2)


def test_rail_length_scales() -> None:
    assert _size(Rail(l=100, w=10, h=10).shape)[1] > _size(Rail(l=40, w=10, h=10).shape)[1]


def test_slider_slop_widens_fit() -> None:
    # more slop -> a slightly larger slider footprint
    tight = _size(Slider(l=30, slop=0.0, fn=None, fa=None, fs=None).shape)
    loose = _size(Slider(l=30, slop=0.4, fn=None, fa=None, fs=None).shape)
    assert loose[1] >= tight[1]


# ── property and show() coverage ────────────────────────────────────────────


def test_slider_properties() -> None:
    s = Slider(l=40, w=14, h=12, base=8, wall=5)
    assert s.length == 40
    assert s.width == 14
    assert s.height == 12


def test_rail_properties() -> None:
    r = Rail(l=60, w=12, h=8)
    assert r.length == 60
    assert r.width == 12
    assert r.height == 8


def test_show_methods_do_not_raise() -> None:
    Slider(l=30).show()
    Rail(l=100).show()

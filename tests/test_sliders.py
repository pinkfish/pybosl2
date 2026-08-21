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
    ("kw", "expected"),
    [
        # length, then w + a wall each side + slop each side, then h stacked on the base
        ({"l": 30, "base": 10, "wall": 4, "slop": 0.2}, (30.0, 10 + 2 * 4 + 2 * 0.2, 10 + 10)),
        ({"l": 40, "w": 14, "h": 12, "base": 8, "wall": 5}, (40.0, 14 + 2 * 5, 12 + 8)),
        ({"l": 30, "base": 10, "wall": 4}, (30.0, 10 + 2 * 4, 10 + 10)),  # no slop: nothing added
    ],
)
def test_slider_envelope(kw: dict[str, object], expected: tuple[float, float, float]) -> None:
    """A slider is `l` long, `w` wide plus its walls and slop, and `h` riding on a `base`."""
    slider = Slider(**kw, fn=None, fa=None, fs=None).shape  # type: ignore[arg-type]
    assert _size(slider) == pytest.approx(expected, abs=0.05)


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

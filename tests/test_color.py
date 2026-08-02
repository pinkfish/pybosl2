# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/color.py: the rainbow() helper and the Colorable colour operators
on Bosl2Solid. HSL and HSV conversions are handled by Python's ``colorsys`` module
via the :meth:`Colorable.hsl` and :meth:`Colorable.hsv` methods."""

import colorsys

import numpy as np

from pybosl2.color import rainbow, rainbow_colors
from pybosl2.shapes3d import Bosl2Solid, cuboid

# -- colours -------------------------------------------------------------------


def test_hsl_via_method() -> None:
    box = cuboid([10, 10, 10]).hsl(0, 1, 0.5)
    assert isinstance(box, Bosl2Solid)


def test_hsv_via_method() -> None:
    box = cuboid([10, 10, 10]).hsv(60, 1, 1)
    assert isinstance(box, Bosl2Solid)


def test_hls_to_rgb_red() -> None:
    r, g, b = colorsys.hls_to_rgb(0, 0.5, 1.0)
    np.testing.assert_allclose([r, g, b], [1, 0, 0], atol=1e-9)


def test_hls_to_rgb_green() -> None:
    r, g, b = colorsys.hls_to_rgb(1 / 3, 0.5, 1.0)
    np.testing.assert_allclose([r, g, b], [0, 1, 0], atol=1e-9)


def test_hsv_to_rgb_blue() -> None:
    r, g, b = colorsys.hsv_to_rgb(2 / 3, 1, 1)
    np.testing.assert_allclose([r, g, b], [0, 0, 1], atol=1e-9)


def test_grayscale_when_saturation_zero() -> None:
    r, g, b = colorsys.hsv_to_rgb(123 / 360, 0, 0.4)
    np.testing.assert_allclose([r, g, b], [0.4, 0.4, 0.4], atol=1e-9)


def test_ghost_for_opacity() -> None:
    box = cuboid([10, 10, 10]).hsl(200, 0.8, 0.5).ghost()
    assert isinstance(box, Bosl2Solid)


# -- rainbow ------------------------------------------------------------------


def test_rainbow_colors_count_and_spread() -> None:
    cols = rainbow_colors(6)
    assert len(cols) == 6
    assert all(len(c) == 3 for c in cols)
    assert cols[0] != cols[1]


def test_rainbow_colors_empty() -> None:
    assert rainbow_colors(0) == []


def test_rainbow_shuffle_is_seed_stable() -> None:
    a = rainbow_colors(8, shuffle=True, seed=42)
    b = rainbow_colors(8, shuffle=True, seed=42)
    assert a == b


def test_rainbow_colors_each_object() -> None:
    parts = [cuboid([5, 5, 5]) for _ in range(4)]
    out = rainbow(parts)
    assert len(out) == 4
    assert all(isinstance(o, Bosl2Solid) for o in out)


# -- Colorable operators -------------------------------------------------------


BOX = cuboid([10, 10, 10])


def test_color_forms_return_solid() -> None:
    assert isinstance(BOX.color("red"), Bosl2Solid)
    assert isinstance(BOX.color([1, 0, 0]), Bosl2Solid)
    assert isinstance(BOX.color([1, 0, 0, 0.5]), Bosl2Solid)
    assert isinstance(BOX.color("red", alpha=0.4), Bosl2Solid)


def test_color_noop_when_nothing_given() -> None:
    assert BOX.color() is BOX


def test_recolor_and_color_this() -> None:
    assert isinstance(BOX.recolor("blue"), Bosl2Solid)
    assert isinstance(BOX.color_this("green"), Bosl2Solid)
    assert BOX.recolor("default") is BOX
    assert BOX.recolor(None) is BOX
    assert BOX.color_this("default") is BOX


def test_hsl_hsv_methods_return_solid() -> None:
    assert isinstance(BOX.hsl(200, 0.8, 0.5), Bosl2Solid)
    assert isinstance(BOX.hsv(60, 1, 1), Bosl2Solid)


def test_highlight_and_ghost() -> None:
    assert isinstance(BOX.highlight(), Bosl2Solid)
    assert isinstance(BOX.ghost(), Bosl2Solid)
    assert BOX.highlight(False) is BOX
    assert BOX.ghost(False) is BOX


def test_color_chains_with_transforms() -> None:
    result = cuboid([10, 10, 10]).hsv(30).right(5).up(2)
    assert isinstance(result, Bosl2Solid)


def test_color_by_name() -> None:
    """color() accepts colour name strings."""
    assert isinstance(cuboid([10, 10, 10]).color("red"), Bosl2Solid)
    assert isinstance(cuboid([10, 10, 10]).color("blue"), Bosl2Solid)
    assert isinstance(cuboid([10, 10, 10]).color("green"), Bosl2Solid)


def test_hsl_edge_cases() -> None:
    """HSL at extremes."""
    assert cuboid([10, 10, 10]).hsl(0, 0, 0) is not None  # black
    assert cuboid([10, 10, 10]).hsl(0, 0, 1) is not None  # white
    assert cuboid([10, 10, 10]).hsl(360, 1, 0.5) is not None  # wrap-around

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/color.py: the HSL conversion, rainbow(), and the Colorable colour operators
on Bosl2Solid. HSV is handled by Python's ``colorsys`` module via the :meth:`Colorable.hsv`
method; the standalone ``hsv()`` function no longer exists."""

import colorsys

import numpy as np

from pybosl2.color import hsl, rainbow, rainbow_colors
from pybosl2.shapes3d import Bosl2Solid, cuboid

# -- HSL primaries ------------------------------------------------------------------


def test_hsl_primaries():
    np.testing.assert_allclose(hsl(0, 1, 0.5), [1, 0, 0], atol=1e-9)
    np.testing.assert_allclose(hsl(120, 1, 0.5), [0, 1, 0], atol=1e-9)
    np.testing.assert_allclose(hsl(240, 1, 0.5), [0, 0, 1], atol=1e-9)


def test_hsl_lightness_extremes():
    np.testing.assert_allclose(hsl(200, 1, 0.0), [0, 0, 0], atol=1e-9)  # black
    np.testing.assert_allclose(hsl(200, 1, 1.0), [1, 1, 1], atol=1e-9)  # white


def test_grayscale_when_saturation_zero():
    np.testing.assert_allclose(list(colorsys.hsv_to_rgb(123 / 360, 0, 0.4)), [0.4, 0.4, 0.4], atol=1e-9)
    np.testing.assert_allclose(hsl(123, 0, 0.4), [0.4, 0.4, 0.4], atol=1e-9)


def test_alpha_handling_on_hsl():
    assert len(hsl(120, 1, 0.5)) == 3
    assert hsl(120, 1, 0.5, 0.25)[-1] == 0.25
    assert len(hsl(120, 1, 0.5, 0.25)) == 4


def test_hsv_primaries_via_colorsys():
    r, g, b = colorsys.hsv_to_rgb(0 / 360, 1, 1)
    np.testing.assert_allclose([r, g, b], [1, 0, 0], atol=1e-9)

    r, g, b = colorsys.hsv_to_rgb(120 / 360, 1, 1)
    np.testing.assert_allclose([r, g, b], [0, 1, 0], atol=1e-9)

    r, g, b = colorsys.hsv_to_rgb(240 / 360, 1, 1)
    np.testing.assert_allclose([r, g, b], [0, 0, 1], atol=1e-9)


def test_hue_wraps_modulo_360_via_colorsys():
    hue_wrap = colorsys.hsv_to_rgb(360 / 360, 1, 1)
    hue_zero = colorsys.hsv_to_rgb(0 / 360, 1, 1)
    np.testing.assert_allclose(hue_wrap, hue_zero, atol=1e-9)


# -- rainbow ----------------------------------------------------------------------


def test_rainbow_colors_count_and_spread():
    cols = rainbow_colors(6)
    assert len(cols) == 6
    assert all(len(c) == 3 for c in cols)
    assert cols[0] != cols[1]  # consecutive hues differ


def test_rainbow_colors_empty():
    assert rainbow_colors(0) == []


def test_rainbow_shuffle_is_seed_stable():
    a = rainbow_colors(8, shuffle=True, seed=42)
    b = rainbow_colors(8, shuffle=True, seed=42)
    assert a == b  # deterministic for a fixed seed


def test_rainbow_colors_each_object():
    parts = [cuboid([5, 5, 5]) for _ in range(4)]
    out = rainbow(parts)
    assert len(out) == 4
    assert all(isinstance(o, Bosl2Solid) for o in out)


# -- Colorable operators on Bosl2Solid -------------------------------------------


BOX = cuboid([10, 10, 10])


def test_color_forms_return_solid():
    assert isinstance(BOX.color("red"), Bosl2Solid)
    assert isinstance(BOX.color([1, 0, 0]), Bosl2Solid)
    assert isinstance(BOX.color([1, 0, 0, 0.5]), Bosl2Solid)
    assert isinstance(BOX.color("red", alpha=0.4), Bosl2Solid)


def test_color_noop_when_nothing_given():
    assert BOX.color() is BOX


def test_recolor_and_color_this():
    assert isinstance(BOX.recolor("blue"), Bosl2Solid)
    assert isinstance(BOX.color_this("green"), Bosl2Solid)
    assert BOX.recolor("default") is BOX
    assert BOX.recolor(None) is BOX
    assert BOX.color_this("default") is BOX


def test_hsl_hsv_methods_return_solid():
    assert isinstance(BOX.hsl(200, 0.8, 0.5), Bosl2Solid)
    assert isinstance(BOX.hsv(60, 1, 1), Bosl2Solid)
    assert isinstance(BOX.hsv(60, 1, 1, 0.5), Bosl2Solid)


def test_highlight_and_ghost():
    assert isinstance(BOX.highlight(), Bosl2Solid)
    assert isinstance(BOX.ghost(), Bosl2Solid)
    assert BOX.highlight(False) is BOX  # disabling is a no-op
    assert BOX.ghost(False) is BOX


def test_color_chains_with_transforms():
    result = cuboid([10, 10, 10]).hsv(30).right(5).up(2)
    assert isinstance(result, Bosl2Solid)

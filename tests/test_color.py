# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/color.py: the rainbow() helper and the Colorable colour operators
on Bosl2Solid. HSL and HSV conversions are handled by Python's ``colorsys`` module
via the :meth:`Colorable.hsl` and :meth:`Colorable.hsv` methods."""

import colorsys
import re

import numpy as np
import pytest

from pybosl2.color import Color, rainbow, rainbow_colors
from pybosl2.shapes3d import Bosl2Solid, cuboid

# -- Color class unit tests --------------------------------------------------


def test_color_from_name() -> None:
    assert Color("red").rgb == (1.0, 0.0, 0.0)
    assert Color("blue").rgb == (0.0, 0.0, 1.0)
    assert Color("green").rgb == (0.0, 128 / 255, 0.0)


def test_color_from_hex() -> None:
    assert Color("#ff0000").rgb == (1.0, 0.0, 0.0)
    assert Color("#f00").rgb == (1.0, 0.0, 0.0)
    assert Color("#00ff0080").rgba == (0.0, 1.0, 0.0, 128 / 255)
    assert Color("#000000").rgb == (0.0, 0.0, 0.0)


def test_color_from_rgb_int() -> None:
    assert Color([255, 0, 0]).rgb == (1.0, 0.0, 0.0)
    assert Color((0, 255, 0)).rgb == (0.0, 1.0, 0.0)


def test_color_from_rgb_float() -> None:
    assert Color([1.0, 0.5, 0.0]).rgb == (1.0, 0.5, 0.0)


def test_color_from_rgba() -> None:
    c = Color([1.0, 0.5, 0.0, 0.3])
    assert c.rgba == (1.0, 0.5, 0.0, 0.3)
    assert c.alpha == 0.3


def test_color_from_none() -> None:
    assert Color(None).rgb == (0.0, 0.0, 0.0)
    assert Color(None).alpha == 1.0


def test_color_properties() -> None:
    c = Color("cornflowerblue")
    assert c.hex == "#6495ed"
    assert str(c) == "#6495ed"
    assert repr(c).startswith("Color(r=0.")


def test_color_to_native() -> None:
    assert Color("red")._to_native() == [1.0, 0.0, 0.0]
    assert Color("blue")._to_native() == [0.0, 0.0, 1.0]
    assert Color([1.0, 0.0, 0.0, 0.5])._to_native() == [1.0, 0.0, 0.0, 0.5]


def test_color_equality() -> None:
    assert Color("red") == Color("red")
    assert Color("red") == Color("#ff0000")
    assert Color("red") == Color([255, 0, 0])
    assert Color("red") != Color("blue")
    assert Color("red") == "red"
    assert Color("red") == [1.0, 0.0, 0.0]
    assert Color("red") != [1.0, 1.0, 0.0]
    assert Color("red") != 42  # type: ignore[comparison-overlap]


def test_color_hashable() -> None:
    s = {Color("red"), Color("red"), Color("blue")}
    assert len(s) == 2


def test_color_invalid_raises() -> None:
    with pytest.raises(ValueError, match="unknown colour name"):
        Color("notacolor")
    with pytest.raises(ValueError, match="invalid hex"):
        Color("#xyz")
    with pytest.raises(ValueError, match="at least 3"):
        Color([1, 2])


def test_color_hex_alpha() -> None:
    c = Color("#ff000080")
    assert c.rgb == (1.0, 0.0, 0.0)
    assert c.alpha == pytest.approx(128 / 255)


def test_color_rgba_int() -> None:
    c = Color([255, 0, 0, 128])
    assert c.rgb == (1.0, 0.0, 0.0)
    assert c.alpha == pytest.approx(128 / 255)


def test_color_to_native_without_alpha() -> None:
    assert Color("red")._to_native() == [1.0, 0.0, 0.0]


def test_color_equality_string() -> None:
    assert Color("blue") == "blue"
    assert Color("blue") != "red"


def test_color_equality_list() -> None:
    assert Color("cyan") == [0.0, 1.0, 1.0]
    assert Color("cyan") != [0.0, 0.0, 1.0]


def test_color_equality_non_color() -> None:
    assert Color("red") != 42  # type: ignore[comparison-overlap]
    assert Color("red") != object()


# -- colours -------------------------------------------------------------------


def test_hsl_via_method() -> None:
    """hue 0, full saturation, mid lightness is pure red."""
    box = cuboid([10, 10, 10]).hsl(0, 1, 0.5)
    assert isinstance(box, Bosl2Solid)
    assert applied_colour(box) == pytest.approx([1.0, 0.0, 0.0, 1.0])


def test_hsv_via_method() -> None:
    """hue 60 at full saturation and value is yellow."""
    box = cuboid([10, 10, 10]).hsv(60, 1, 1)
    assert isinstance(box, Bosl2Solid)
    assert applied_colour(box) == pytest.approx([1.0, 1.0, 0.0, 1.0])


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
    """ghost() marks the solid for see-through preview and leaves its colour alone."""
    coloured = cuboid([10, 10, 10]).hsl(200, 0.8, 0.5)
    ghosted = coloured.ghost()
    assert isinstance(ghosted, Bosl2Solid)
    assert applied_colour(ghosted) == pytest.approx(applied_colour(coloured))
    assert repr(ghosted.shape) != repr(coloured.shape)


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


def applied_colour(solid: Bosl2Solid) -> list[float]:
    """The RGBA the operator actually handed the backend, read out of the emitted program.

    Colour is not geometry, so `bounds()` cannot see it (PLAN X-8) -- but the emitted
    ``color([r, g, b, a])`` call says exactly what was applied.
    """
    found = re.search(r"color\(\[([^]]*)\]\)", repr(solid.shape))
    assert found, f"no colour applied: {repr(solid.shape)[:120]}"
    return [float(v) for v in found.group(1).split(",")]


def test_color_forms_return_solid() -> None:
    """Name, RGB list and RGBA list are three spellings of the same red; alpha= sets the fourth."""
    assert applied_colour(BOX.color("red")) == pytest.approx([1.0, 0.0, 0.0, 1.0])
    assert applied_colour(BOX.color([1, 0, 0])) == pytest.approx([1.0, 0.0, 0.0, 1.0])
    assert applied_colour(BOX.color([1, 0, 0, 0.5])) == pytest.approx([1.0, 0.0, 0.0, 0.5])
    assert applied_colour(BOX.color("red", alpha=0.4)) == pytest.approx([1.0, 0.0, 0.0, 0.4])


def test_color_noop_when_nothing_given() -> None:
    assert BOX.color() is BOX


def test_recolor_and_color_this() -> None:
    assert isinstance(BOX.recolor("blue"), Bosl2Solid)
    assert isinstance(BOX.color_this("green"), Bosl2Solid)
    assert BOX.recolor("default") is BOX
    assert BOX.recolor(None) is BOX
    assert BOX.color_this("default") is BOX


def test_hsl_hsv_methods_return_solid() -> None:
    """Both go through colorsys, so they must match it exactly."""
    assert applied_colour(BOX.hsl(200, 0.8, 0.5))[:3] == pytest.approx(colorsys.hls_to_rgb(200 / 360, 0.5, 0.8))
    assert applied_colour(BOX.hsv(60, 1, 1))[:3] == pytest.approx(colorsys.hsv_to_rgb(60 / 360, 1, 1))


def test_highlight_and_ghost() -> None:
    assert isinstance(BOX.highlight(), Bosl2Solid)
    assert isinstance(BOX.ghost(), Bosl2Solid)
    assert BOX.highlight(False) is BOX
    assert BOX.ghost(False) is BOX


def test_color_chains_with_transforms() -> None:
    """The colour survives the transforms that follow it, and the transforms still move the box."""
    result = cuboid([10, 10, 10]).hsv(30).right(5).up(2)
    assert isinstance(result, Bosl2Solid)
    assert applied_colour(result)[:3] == pytest.approx(colorsys.hsv_to_rgb(30 / 360, 1, 1))
    assert [float(v) for v in result.bounds().center] == pytest.approx([5.0, 0.0, 2.0])


@pytest.mark.parametrize(
    ("name", "rgb"),
    [("red", [1.0, 0.0, 0.0]), ("blue", [0.0, 0.0, 1.0]), ("green", [0.0, 128 / 255, 0.0])],
)
def test_color_by_name(name: str, rgb: list[float]) -> None:
    """A CSS colour name resolves to its own RGB -- "green" is the CSS half-green, not [0, 1, 0]."""
    assert applied_colour(cuboid([10, 10, 10]).color(name))[:3] == pytest.approx(rgb, abs=1e-5)


def test_hsl_edge_cases() -> None:
    """Lightness 0 and 1 are black and white whatever the hue, and 360 degrees wraps to 0."""
    assert applied_colour(cuboid([10, 10, 10]).hsl(0, 0, 0))[:3] == pytest.approx([0.0, 0.0, 0.0])
    assert applied_colour(cuboid([10, 10, 10]).hsl(0, 0, 1))[:3] == pytest.approx([1.0, 1.0, 1.0])
    assert applied_colour(cuboid([10, 10, 10]).hsl(360, 1, 0.5)) == pytest.approx(
        applied_colour(cuboid([10, 10, 10]).hsl(0, 1, 0.5))
    )  # wrap-around


# -- every colour operator must accept a Color, and must live ON the class -------------


@pytest.mark.parametrize("method", ["color", "recolor", "color_this"])
def test_colour_operators_accept_a_color_object(method: str) -> None:
    """A Color must survive the trip to the native backend.

    ``color()`` converted a Color to its [R, G, B] list before handing it over, but
    ``recolor()`` and ``color_this()`` passed the object straight through and the backend
    answered "TypeError: Unknown color representation" -- so the same argument worked or
    failed depending on which operator you reached for.
    """
    solid = cuboid([10, 10, 10])
    coloured = getattr(solid, method)(Color("green"))
    assert isinstance(coloured, Bosl2Solid)
    assert applied_colour(coloured)[:3] == pytest.approx(Color("green").rgb, abs=1e-5)


@pytest.mark.parametrize("method", ["color", "recolor", "color_this", "hsl", "hsv", "highlight", "ghost"])
def test_colour_operators_are_defined_on_the_class(method: str) -> None:
    """Colorable's operators must be attributes of the solid, not reached by fallthrough.

    ``Bosl2Solid.__getattr__`` forwards unknown names to the wrapped NATIVE handle, which
    has its own ``color``. So if these methods ever stop being class attributes -- one stray
    unindented line in color.py is enough to end the class body early -- ``.color()`` keeps
    working while silently becoming the native one, and only ``recolor``/``hsl``, which the
    native handle lacks, fail. hasattr() on the CLASS bypasses that fallthrough entirely.
    """
    assert hasattr(Bosl2Solid, method), f"Colorable.{method} is not on Bosl2Solid"

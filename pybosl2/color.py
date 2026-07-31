# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/color.py
#    Pure-Python port of BOSL2's color.scad: the HSL/HSV -> RGB colourspace
#    conversions and the rainbow() helper for colouring a list of objects.
#    Python's standard library ``colorsys`` module provides ``hls_to_rgb``
#    and ``hsv_to_rgb``, but BOSL2's ``hsl()`` uses a different formula
#    than the HLS model — the custom implementations here match OpenSCAD's
#    output exactly rather than the generic colour-science approximations.
#    The colour operators (``color``/``recolor``/``color_this``/``hsl``/
#    ``hsv``/``highlight``/``ghost``) are provided by the
#    :class:`Colorable` mixin defined here and consumed by
#    :class:`~pybosl2.shapes3d.Bosl2Solid`.
#
# FileSummary: HSL/HSV colour conversion, rainbow(), and the Colorable colour operators.
# DocCategory: Foundational
# FileGroup: BOSL2

from __future__ import annotations

import colorsys
import random
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Self

    from shapes3d import Bosl2Solid

__all__ = ["hsl", "rainbow", "rainbow_colors", "Colorable"]


def _to_3d_drop_alpha() -> Any:
    """OpenSCAD ``color([r, g, b])`` discards alpha, so BOSL2 does too."""


# ---------------------------------------------------------------------------
# Section: colourspace conversion
# ---------------------------------------------------------------------------


def hsl(height: float, s: float = 1.0, length: float = 0.5, a: float | None = None) -> list[float]:
    """Convert HSL to an ``[R, G, B]`` colour (or ``[R, G, B, A]`` if *a* is given).

    Uses the exact HSL formula from BOSL2/OpenSCAD, which differs from Python's
    ``colorsys.hls_to_rgb`` (HLS uses a double-hexcone model; HSL uses a hexagonal
    cone).  For generic colour processing prefer ``colorsys``; use this function
    only when BOSL2 parity is required.

    Args:
        height: Hue in degrees (0=red, 60=yellow, 120=green, 180=cyan, 240=blue, 300=magenta).
        s: Saturation 0..1 (0 = grey, 1 = vivid).
        length: Lightness 0..1 (0 = black, 0.5 = bright, 1 = white).
        a: Optional alpha 0..1; when given the result is ``[R, G, B, A]``.

    Returns:
        ``[R, G, B]`` (each 0..1), or ``[R, G, B, A]`` when *a* is given.
    """
    hm = height % 360
    rgb: list[float] = []
    for n in (0, 8, 4):
        k = (n + hm / 30) % 12
        rgb.append(length - s * min(length, 1 - length) * max(min(k - 3, 9 - k, 1), -1))
    return rgb + ([a] if a is not None else [])


def rainbow_colors(
    sides: int,
    stride: int = 1,
    maxhues: int | None = None,
    shuffle: bool = False,
    seed: int | None = None,
) -> list[list[float]]:
    """Generate *sides* ``[R, G, B]`` colours stepped around the hue wheel.

    Equivalent to BOSL2's ``rainbow()`` colour generation without applying the
    colours to objects.

    Args:
        sides: How many colours to generate.
        stride: Consecutive colours stride this many steps around the wheel.
        maxhues: Cap the number of distinct hues (default: *sides*).
        shuffle: Shuffle the hue order before generating colours.
        seed: Seed for the shuffle operation.

    Returns:
        A list of ``[R, G, B]`` lists, each with values 0..1.
    """
    if sides <= 0:
        return []
    mh = maxhues if maxhues is not None else sides
    huestep = 360 / mh
    hues = [(i * huestep + i * 360 / stride) % 360 for i in range(sides)]
    if shuffle:
        random.Random(seed).shuffle(hues)
    return [list(colorsys.hsv_to_rgb(hue / 360, 1.0, 1.0)) for hue in hues]


def rainbow(
    items: Sequence[Bosl2Solid],
    stride: int = 1,
    maxhues: int | None = None,
    shuffle: bool = False,
    seed: int | None = None,
) -> list[Any]:
    """Colour each object in *items* a different hue.

    Each item must support ``.color([r, g, b])`` (a :class:`~pybosl2.shapes3d.Bosl2Solid`
    or native solid).  Useful for telling apart the parts of a multi-piece model
    or debugging a list of paths.

    Args:
        items: The objects to colour.
        stride: Consecutive colours stride this many steps around the wheel.
        maxhues: Cap the number of distinct hues (default: ``len(items)``).
        shuffle: Shuffle the hue order before colouring.
        seed: Seed for the shuffle operation.

    Returns:
        A list of coloured objects, one per element of *items*.
    """
    items = list(items)
    colors = rainbow_colors(len(items), stride=stride, maxhues=maxhues, shuffle=shuffle, seed=seed)
    return [obj.color(col) for obj, col in zip(items, colors, strict=False)]


# ---------------------------------------------------------------------------
# Section: Colorable mixin
# ---------------------------------------------------------------------------


class Colorable(ABC):
    """Mixin adding the color.scad colour operators as methods.

    Inherited by :class:`~pybosl2.shapes3d.Bosl2Solid`.  Every operator resolves
    to the host's native colour primitives, which the host provides as
    ``_color_native`` (PythonSCAD ``color()``), ``_highlight_native`` (the ``#``
    modifier) and ``_ghost_native`` (the ``%`` modifier).

    Because the toolkit builds native geometry rather than a BOSL2 ``$color``
    attachment tree, :meth:`recolor` and :meth:`color_this` both apply the
    colour directly — an object's already-coloured children keep their colour,
    matching OpenSCAD's ``color()`` semantics.
    """

    @abstractmethod
    def _color_native(self, c: Any = None, alpha: float | None = None) -> Self:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    def _highlight_native(self) -> Self:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    def _ghost_native(self) -> Self:  # pragma: no cover
        raise NotImplementedError

    def color(self, c: Any = None, alpha: float | None = None) -> Self:
        """Colour this object.

        Args:
            c: A colour name (``"red"``), ``[R, G, B]`` list, or ``[R, G, B, A]`` list.
               Pass ``None`` to leave the colour unchanged.
            alpha: Optional alpha transparency 0..1.

        Returns:
            This object with the colour applied, or ``self`` unchanged when both
            *c* and *alpha* are ``None``.
        """
        if c is None and alpha is None:
            return self
        return self._color_native(c, alpha)

    def recolor(self, c: Any = "default", alpha: float | None = None) -> Self:
        """Set the colour of this object and its uncoloured descendants.

        In the native backend there is no ``$color`` attachment tree to revert
        to, so ``"default"`` / ``None`` leaves the colour unchanged.

        Args:
            c: A colour name, ``[R, G, B]`` list, or ``"default"``/``None`` to skip.
            alpha: Optional alpha transparency 0..1.

        Returns:
            This object recoloured, or ``self`` unchanged when *c* is ``"default"``
            or ``None``.
        """
        if c is None or c == "default":
            return self
        return self._color_native(c, alpha)

    def color_this(self, c: Any = "default", alpha: float | None = None) -> Self:
        """Colour just this object, without tinting its descendants.

        Equivalent to :meth:`color` in the native backend, where there is no
        ``$color`` attachment tree to preserve separately.

        Args:
            c: A colour name, ``[R, G, B]`` list, or ``"default"``/``None`` to skip.
            alpha: Optional alpha transparency 0..1.

        Returns:
            This object coloured, or ``self`` unchanged when *c* is ``"default"``
            or ``None``.
        """
        if c is None or c == "default":
            return self
        return self._color_native(c, alpha)

    def hsl(self, height: float, s: float = 1.0, length: float = 0.5, a: float | None = None) -> Self:
        """Colour this object from an HSL hue/saturation/lightness.

        Args:
            height: Hue in degrees.
            s: Saturation 0..1.
            length: Lightness 0..1.
            a: Optional alpha 0..1.

        Returns:
            This object coloured with the computed ``[R, G, B]`` value.
        """
        return self._color_native(hsl(height, s, length), a)

    def hsv(self, height: float, s: float = 1.0, v: float = 1.0, a: float | None = None) -> Self:
        """Colour this object from an HSV hue/saturation/value.

        Uses Python's :func:`colorsys.hsv_to_rgb` for the conversion.

        Args:
            height: Hue in degrees.
            s: Saturation 0..1.
            v: Value 0..1.
            a: Optional alpha 0..1.

        Returns:
            This object coloured with the computed ``[R, G, B]`` value.
        """
        rgb = list(colorsys.hsv_to_rgb(height / 360, s, v))
        return self._color_native(rgb, a)

    def highlight(self, highlight: bool = True) -> Self:
        """Apply the ``#`` debug modifier (BOSL2 highlight()).

        Args:
            highlight: If True (default), apply the highlight modifier.
                       If False, return *self* unchanged.

        Returns:
            This object with the highlight modifier applied, or *self* unchanged
            when *highlight* is ``False``.
        """
        return self._highlight_native() if highlight else self

    def ghost(self, ghost: bool = True) -> Self:
        """Apply the ``%`` (transparent, non-interacting) debug modifier.

        Args:
            ghost: If True (default), apply the ghost modifier.
                   If False, return *self* unchanged.

        Returns:
            This object with the ghost modifier applied, or *self* unchanged
            when *ghost* is ``False``.
        """
        return self._ghost_native() if ghost else self

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/color.py
#    Colour conversions and operators for the fluent object API.
#    Uses Python's standard-library ``colorsys`` for HLS and HSV → RGB
#    conversions.  The :class:`Colorable` mixin provides the fluent colour
#    operators consumed by :class:`~pybosl2.shapes3d.Bosl2Solid`.
#    Opacity is applied by chaining :meth:`~Colorable.ghost` after the
#    colour method rather than through an alpha parameter — matching how
#    OpenSCAD's ``%`` (ghost/background) modifier works.
#
# FileSummary: Colour operators (Colorable mixin) via Python's colorsys module.
# DocCategory: Foundational
# FileGroup: BOSL2

"""Colour operators (Colorable mixin) via Python's colorsys module."""

from __future__ import annotations

import colorsys
import random
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Self

    from pybosl2._shape import BaseShape as Bosl2Shape

__all__ = ["rainbow", "rainbow_colors", "Colorable"]


# ---------------------------------------------------------------------------
# rainbow
# ---------------------------------------------------------------------------


def rainbow_colors(
    sides: int,
    stride: int = 1,
    maxhues: int | None = None,
    shuffle: bool = False,
    seed: int | None = None,
) -> list[list[float]]:
    """Generate *sides* ``[R, G, B]`` colours stepped around the hue wheel.

    Equivalent to BOSL2's ``rainbow()`` colour generation without applying the
    colours to objects.  Uses :func:`colorsys.hsv_to_rgb` internally.

    Args:
        sides: How many colours to generate.
        stride: Consecutive colours stride this many steps around the wheel.
        maxhues: Cap the number of distinct hues (default: *sides*).
        shuffle: Shuffle the hue order before generating colours.
        seed: Seed for the shuffle operation.

    Returns:
        A list of ``[R, G, B]`` lists, each with values 0..1.

    Examples:
        .. pythonscad-example::

            from pybosl2.color import rainbow_colors
            from pybosl2.shapes3d import cuboid

            cols = rainbow_colors(3)
            a = cuboid([5, 5, 10]).color(cols[0])
            b = cuboid([5, 5, 10]).color(cols[1]).right(8)
            c = cuboid([5, 5, 10]).color(cols[2]).right(16)
            (a | b | c).show()

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
    items: Sequence[Bosl2Shape],
    stride: int = 1,
    maxhues: int | None = None,
    shuffle: bool = False,
    seed: int | None = None,
) -> list[Bosl2Shape]:
    """Colour each object in *items* a different hue.

    Each item must be a :class:`~pybosl2._shape.Bosl2Shape` (a
    :class:`~pybosl2.shapes2d.Bosl2Shape2D` or
    :class:`~pybosl2.shapes3d.Bosl2Solid`).  Useful for telling apart the
    parts of a multi-piece model or debugging a list of paths.

    Args:
        items: The objects to colour.
        stride: Consecutive colours stride this many steps around the wheel.
        maxhues: Cap the number of distinct hues (default: ``len(items)``).
        shuffle: Shuffle the hue order before colouring.
        seed: Seed for the shuffle operation.

    Returns:
        A list of coloured objects, one per element of *items*, each
        preserving its original 2-D or 3-D type.

    """
    items = list(items)
    colors = rainbow_colors(len(items), stride=stride, maxhues=maxhues, shuffle=shuffle, seed=seed)
    return [obj.color(col) for obj, col in zip(items, colors, strict=False)]


# ---------------------------------------------------------------------------
# Colorable mixin
# ---------------------------------------------------------------------------


class Colorable(ABC):
    """Mixin adding the color.scad colour operators as methods.

    Inherited by :class:`~pybosl2.shapes3d.Bosl2Solid`.  Every operator resolves
    to the host's native colour primitives, which the host provides as
    ``_color_native`` (PythonSCAD ``color()``), ``_highlight_native`` (the ``#``
    modifier) and ``_ghost_native`` (the ``%`` modifier).

    **Opacity** is applied by chaining :meth:`ghost` rather than through an
    ``alpha`` parameter — this matches how OpenSCAD's ``%`` background modifier
    works.  For example ``box.hsl(0, 1, 0.5).ghost()`` produces a transparent
    red box.
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

        Uses :func:`colorsys.hls_to_rgb` for the conversion.  For opacity, chain
        :meth:`ghost` after this call or pass the alpha parameter *a*.

        Args:
            height: Hue in degrees (0=red, 120=green, 240=blue).
            s: Saturation 0..1 (0 = grey, 1 = vivid).
            length: Lightness 0..1 (0 = black, 0.5 = bright, 1 = white).
            a: Optional alpha (opacity) 0..1.

        Returns:
            This object coloured with the computed ``[R, G, B]`` value.

        """
        rgb = list(colorsys.hls_to_rgb(height / 360, length, s))
        return self._color_native(rgb, a)

    def hsv(self, height: float, s: float = 1.0, v: float = 1.0, a: float | None = None) -> Self:
        """Colour this object from an HSV hue/saturation/value.

        Uses :func:`colorsys.hsv_to_rgb` for the conversion.  For opacity, chain
        :meth:`ghost` after this call or pass the alpha parameter *a*.

        Args:
            height: Hue in degrees (0=red, 120=green, 240=blue).
            s: Saturation 0..1 (0 = grey, 1 = vivid).
            v: Value 0..1 (0 = black, 1 = bright).
            a: Optional alpha (opacity) 0..1.

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

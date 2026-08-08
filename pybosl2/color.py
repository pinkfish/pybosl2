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

__all__ = ["rainbow", "rainbow_colors", "Colorable", "Color"]

# CSS3 / SVG named colour table — name → (r, g, b)  0–255 integers.
_COLOR_NAMES: dict[str, tuple[int, int, int]] = {
    "aliceblue": (240, 248, 255),
    "antiquewhite": (250, 235, 215),
    "aqua": (0, 255, 255),
    "aquamarine": (127, 255, 212),
    "azure": (240, 255, 255),
    "beige": (245, 245, 220),
    "bisque": (255, 228, 196),
    "black": (0, 0, 0),
    "blanchedalmond": (255, 235, 205),
    "blue": (0, 0, 255),
    "blueviolet": (138, 43, 226),
    "brown": (165, 42, 42),
    "burlywood": (222, 184, 135),
    "cadetblue": (95, 158, 160),
    "chartreuse": (127, 255, 0),
    "chocolate": (210, 105, 30),
    "coral": (255, 127, 80),
    "cornflowerblue": (100, 149, 237),
    "cornsilk": (255, 248, 220),
    "crimson": (220, 20, 60),
    "cyan": (0, 255, 255),
    "darkblue": (0, 0, 139),
    "darkcyan": (0, 139, 139),
    "darkgoldenrod": (184, 134, 11),
    "darkgray": (169, 169, 169),
    "darkgreen": (0, 100, 0),
    "darkgrey": (169, 169, 169),
    "darkkhaki": (189, 183, 107),
    "darkmagenta": (139, 0, 139),
    "darkolivegreen": (85, 107, 47),
    "darkorange": (255, 140, 0),
    "darkorchid": (153, 50, 204),
    "darkred": (139, 0, 0),
    "darksalmon": (233, 150, 122),
    "darkseagreen": (143, 188, 143),
    "darkslateblue": (72, 61, 139),
    "darkslategray": (47, 79, 79),
    "darkslategrey": (47, 79, 79),
    "darkturquoise": (0, 206, 209),
    "darkviolet": (148, 0, 211),
    "deeppink": (255, 20, 147),
    "deepskyblue": (0, 191, 255),
    "dimgray": (105, 105, 105),
    "dimgrey": (105, 105, 105),
    "dodgerblue": (30, 144, 255),
    "firebrick": (178, 34, 34),
    "floralwhite": (255, 250, 240),
    "forestgreen": (34, 139, 34),
    "fuchsia": (255, 0, 255),
    "gainsboro": (220, 220, 220),
    "ghostwhite": (248, 248, 255),
    "gold": (255, 215, 0),
    "goldenrod": (218, 165, 32),
    "gray": (128, 128, 128),
    "green": (0, 128, 0),
    "greenyellow": (173, 255, 47),
    "grey": (128, 128, 128),
    "honeydew": (240, 255, 240),
    "hotpink": (255, 105, 180),
    "indianred": (205, 92, 92),
    "indigo": (75, 0, 130),
    "ivory": (255, 255, 240),
    "khaki": (240, 230, 140),
    "lavender": (230, 230, 250),
    "lavenderblush": (255, 240, 245),
    "lawngreen": (124, 252, 0),
    "lemonchiffon": (255, 250, 205),
    "lightblue": (173, 216, 230),
    "lightcoral": (240, 128, 128),
    "lightcyan": (224, 255, 255),
    "lightgoldenrodyellow": (250, 250, 210),
    "lightgray": (211, 211, 211),
    "lightgreen": (144, 238, 144),
    "lightgrey": (211, 211, 211),
    "lightpink": (255, 182, 193),
    "lightsalmon": (255, 160, 122),
    "lightseagreen": (32, 178, 170),
    "lightskyblue": (135, 206, 250),
    "lightslategray": (119, 136, 153),
    "lightslategrey": (119, 136, 153),
    "lightsteelblue": (176, 196, 222),
    "lightyellow": (255, 255, 224),
    "lime": (0, 255, 0),
    "limegreen": (50, 205, 50),
    "linen": (250, 240, 230),
    "magenta": (255, 0, 255),
    "maroon": (128, 0, 0),
    "mediumaquamarine": (102, 205, 170),
    "mediumblue": (0, 0, 205),
    "mediumorchid": (186, 85, 211),
    "mediumpurple": (147, 112, 219),
    "mediumseagreen": (60, 179, 113),
    "mediumslateblue": (123, 104, 238),
    "mediumspringgreen": (0, 250, 154),
    "mediumturquoise": (72, 209, 204),
    "mediumvioletred": (199, 21, 133),
    "midnightblue": (25, 25, 112),
    "mintcream": (245, 255, 250),
    "mistyrose": (255, 228, 225),
    "moccasin": (255, 228, 181),
    "navajowhite": (255, 222, 173),
    "navy": (0, 0, 128),
    "oldlace": (253, 245, 230),
    "olive": (128, 128, 0),
    "olivedrab": (107, 142, 35),
    "orange": (255, 165, 0),
    "orangered": (255, 69, 0),
    "orchid": (218, 112, 214),
    "palegoldenrod": (238, 232, 170),
    "palegreen": (152, 251, 152),
    "paleturquoise": (175, 238, 238),
    "palevioletred": (219, 112, 147),
    "papayawhip": (255, 239, 213),
    "peachpuff": (255, 218, 185),
    "peru": (205, 133, 63),
    "pink": (255, 192, 203),
    "plum": (221, 160, 221),
    "powderblue": (176, 224, 230),
    "purple": (128, 0, 128),
    "rebeccapurple": (102, 51, 153),
    "red": (255, 0, 0),
    "rosybrown": (188, 143, 143),
    "royalblue": (65, 105, 225),
    "saddlebrown": (139, 69, 19),
    "salmon": (250, 128, 114),
    "sandybrown": (244, 164, 96),
    "seagreen": (46, 139, 87),
    "seashell": (255, 245, 238),
    "sienna": (160, 82, 45),
    "silver": (192, 192, 192),
    "skyblue": (135, 206, 235),
    "slateblue": (106, 90, 205),
    "slategray": (112, 128, 144),
    "slategrey": (112, 128, 144),
    "snow": (255, 250, 250),
    "springgreen": (0, 255, 127),
    "steelblue": (70, 130, 180),
    "tan": (210, 180, 140),
    "teal": (0, 128, 128),
    "thistle": (216, 191, 216),
    "tomato": (255, 99, 71),
    "turquoise": (64, 224, 208),
    "violet": (238, 130, 238),
    "wheat": (245, 222, 179),
    "white": (255, 255, 255),
    "whitesmoke": (245, 245, 245),
    "yellow": (255, 255, 0),
    "yellowgreen": (154, 205, 50),
}


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
    return [obj.color(col) for obj, col in zip(items, colors, strict=False)]  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Colorable mixin
# ---------------------------------------------------------------------------


class Color:
    """A normalised RGBA colour from any input format.

    Accepts a CSS colour name (``"red"``), a ``#rrggbb`` hex string, an
    ``[R, G, B]`` list or tuple (0-1 floats or 0-255 ints), or an
    ``[R, G, B, A]`` list/tuple.  All components are stored as 0-1 floats.

    ``Color("red").rgb`` → ``(1.0, 0.0, 0.0)``
    """

    __slots__ = ("_r", "_g", "_b", "_a")

    def __init__(self, spec: str | Sequence[float] | Sequence[int] | None = None) -> None:
        """Normalise a colour from any input format.

        Args:
            spec: A CSS colour name, ``#rrggbb`` hex string, ``[R,G,B]`` or
                  ``[R,G,B,A]`` sequence (0-1 floats or 0-255 ints), or ``None``.

        """
        self._a: float = 1.0
        if spec is None:
            self._r = self._g = self._b = 0.0
            return
        if isinstance(spec, str):
            s = spec.strip().lower()
            if s.startswith("#"):
                hex_val = s.lstrip("#")
                if len(hex_val) == 3:
                    hex_val = "".join(c * 2 for c in hex_val)
                if len(hex_val) not in (6, 8):
                    raise ValueError(f"invalid hex colour: {spec!r}")
                try:
                    self._r = int(hex_val[0:2], 16) / 255
                    self._g = int(hex_val[2:4], 16) / 255
                    self._b = int(hex_val[4:6], 16) / 255
                    if len(hex_val) == 8:
                        self._a = int(hex_val[6:8], 16) / 255
                except ValueError:
                    raise ValueError(f"invalid hex colour: {spec!r}") from None
                return
            if s in _COLOR_NAMES:
                r, g, b = _COLOR_NAMES[s]
                self._r, self._g, self._b = r / 255, g / 255, b / 255
                return
            raise ValueError(f"unknown colour name: {spec!r}")
        arr = list(spec)
        n = len(arr)
        if n < 3:
            raise ValueError(f"colour sequence needs at least 3 values, got {n}")
        # Detect int (0-255) vs float (0-1): if any value > 1, treat as 0-255
        scale = (
            1.0 / 255 if any(isinstance(v, int) and v > 1 or isinstance(v, float) and v > 1 for v in arr[:3]) else 1.0
        )
        self._r = float(arr[0]) * scale
        self._g = float(arr[1]) * scale
        self._b = float(arr[2]) * scale
        if n >= 4:
            self._a = float(arr[3]) * (1.0 / 255 if scale < 1 else 1.0)

    @property
    def rgb(self) -> tuple[float, float, float]:
        """The (R, G, B) components as 0-1 floats."""
        return (self._r, self._g, self._b)

    @property
    def rgba(self) -> tuple[float, float, float, float]:
        """The (R, G, B, A) components as 0-1 floats."""
        return (self._r, self._g, self._b, self._a)

    @property
    def alpha(self) -> float:
        """Alpha opacity, 0-1."""
        return self._a

    @property
    def hex(self) -> str:
        """The ``#rrggbb`` hex string."""
        return f"#{int(round(self._r * 255)):02x}{int(round(self._g * 255)):02x}{int(round(self._b * 255)):02x}"

    def _to_native(self) -> str | list[float]:
        """Return a value suitable for passing to PythonSCAD's ``color()``."""
        if self._a >= 1.0:
            return [self._r, self._g, self._b]
        return [self._r, self._g, self._b, self._a]

    def __str__(self) -> str:
        """Return the hex string."""
        return self.hex

    def __repr__(self) -> str:
        """Return a debug representation."""
        return f"Color(r={self._r:.3f}, g={self._g:.3f}, b={self._b:.3f}, a={self._a:.3f})"

    def __eq__(self, other: object) -> bool:
        """Return whether two colours are equal."""
        if isinstance(other, Color):
            return self.rgba == other.rgba
        if isinstance(other, (str, list, tuple)):
            try:
                return self == Color(other)
            except ValueError:
                return False
        return NotImplemented

    def __hash__(self) -> int:
        """Return a hash of the colour."""
        return hash(self.rgba)


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

    def color(self, c: "Color | None" = None, alpha: float | None = None) -> Self:
        """Colour this object.

        Args:
            c: A :class:`Color` object, or ``None`` to leave colour unchanged.
            alpha: Optional alpha transparency 0..1.

        Returns:
            This object with the colour applied, or ``self`` unchanged when both
            *c* and *alpha* are ``None``.

        """
        if c is None and alpha is None:
            return self
        native_c = c._to_native() if isinstance(c, Color) else (c if c is not None else None)
        return self._color_native(native_c, alpha)

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

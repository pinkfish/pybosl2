# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/shapes2d/ops.py
# FileSummary: Boolean operations, offsets, text and cross helpers.
# DocCategory: Foundational
# FileGroup: BOSL2

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Union

import numpy as np

from pybosl2._edges_lang import Anchor

# Import base class and helper functions from shapes2d.base
from pybosl2._helpers import (
    anchor_offset_box as _anchor_offset_box,
)
from pybosl2._helpers import (
    as_native_2d as _as_native_2d,
)
from pybosl2._helpers import (
    is_child_2d as _is_child_2d,
)
from pybosl2._native import native
from pybosl2.constants import CENTER

from .base import Bosl2Shape2D, _finish

if TYPE_CHECKING:
    from openscad import PyOpenSCAD

    from pybosl2.path2d import Path2D


Shape2DLike = Union["Bosl2Shape2D", "PyOpenSCAD", "Path2D", Sequence[Sequence[float]], np.ndarray]

if TYPE_CHECKING:  # real stub-typed imports for the checker (identical to pre-lazy)
    from pythonscad import circle as _ocircle
    from pythonscad import fill as _ofill
    from pythonscad import hull as _ohull
    from pythonscad import polygon as _opolygon
    from pythonscad import square as _osquare
    from pythonscad import text as _otext
else:
    _ocircle = native("circle")
    _ofill = native("fill")
    _ohull = native("hull")
    _opolygon = native("polygon")
    _osquare = native("square")
    _otext = native("text")


def fill(children: "Shape2DLike") -> Bosl2Shape2D:
    """*children* with every hole filled in -- only the outermost outline survives
    (OpenSCAD ``fill()``, the module form of :meth:`Bosl2Shape2D.fill`).

    Args:
        children: the 2-D shape to fill (a ``Bosl2Shape2D``, a native shape, a
                  :class:`~pybosl2.paths.Path2D` / :class:`~pybosl2.regions.Region`, or a point list)
    """
    return Bosl2Shape2D(_ofill(_as_native_2d(children)))


def hull(*children: "Shape2DLike | Sequence[Shape2DLike]") -> Bosl2Shape2D:
    """The 2-D convex hull of *children* (OpenSCAD ``hull()``, the module form of
    :meth:`Bosl2Shape2D.hull`).

    Args:
        children: the 2-D shapes to hull -- any mix of ``Bosl2Shape2D``, native shapes,
                  :class:`~pybosl2.paths.Path2D` / :class:`~pybosl2.regions.Region`, or point lists.
                  A single list/tuple *of* shapes is also accepted.
    """
    items = list(children)
    if len(items) == 1 and not _is_child_2d(items[0]):
        items = list(items[0])  # type: ignore[arg-type]  # a single list *of* shapes
    assert items, "hull(): needs at least one child."
    return Bosl2Shape2D(_ohull(*[_as_native_2d(c) for c in items]))


# ---------------------------------------------------------------------------
# Section: Rounding 2D shapes
# ---------------------------------------------------------------------------


def round2d(
    radius: float | None = None,
    outer_radius: float | None = None,
    inner_radius: float | None = None,
    children: "Bosl2Shape2D | PyOpenSCAD | None" = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """Rounds the concave and/or convex corners of arbitrary 2-D children, via chained .offset() calls.

    Giving `radius` rounds all corners; `inner_radius` alone rounds only concave corners;
    `outer_radius` alone rounds only convex corners; giving both rounds each to a different
    radius.

    Note: BOSL2's outer-radius parameter is named `or`, exposed here as `outer_radius`.

    Args:
        radius:       radius to round all concave and convex corners to
        outer_radius: radius to round only convex (outside) corners to (BOSL2 `or`)
        inner_radius: radius to round only concave (inside) corners to
        children:     the 2-D solid(s) to round
        fn: arc smoothness overrides
        fa: arc smoothness overrides
        fs: arc smoothness overrides
    """
    orad = outer_radius if outer_radius is not None else (radius if radius is not None else 0)
    irad = inner_radius if inner_radius is not None else (radius if radius is not None else 0)
    assert children is not None, "round2d(): must give children"
    shape = Bosl2Shape2D(_as_native_2d(children))
    shape = shape.offset(delta=irad, chamfer=True)
    shape = shape.offset(delta=-(irad + orad))
    return shape.offset(radius=orad, fn=fn, fa=fa, fs=fs)


def shell2d(
    thickness: float | Sequence[float] | None = None,
    outer_radius: float | Sequence[float] = 0,
    inner_radius: float | Sequence[float] = 0,
    children: "Bosl2Shape2D | PyOpenSCAD | None" = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """Creates a hollow shell from 2-D children, with optional rounding.

    Note: BOSL2's outer-radius parameter is named `or`, exposed here as `outer_radius`.

    Args:
        thickness:    shell thickness; positive expands outward, negative shrinks inward,
                      or a 2-element list to do both
        outer_radius: rounding radius for outside corners of the shell (BOSL2 `or`); a
                      [CONVEX,CONCAVE] pair rounds those corner types separately (default 0)
        inner_radius: rounding radius for inside corners of the shell; a [CONVEX,CONCAVE]
                      pair rounds those corner types separately (default 0)
        children:     the 2-D solid(s) to shell
        fn: arc smoothness overrides
        fa: arc smoothness overrides
        fs: arc smoothness overrides
    """
    assert thickness is not None, "shell2d(): must give thickness"
    assert children is not None, "shell2d(): must give children"
    if isinstance(thickness, (int, float)):
        th = [float(thickness), 0.0] if thickness < 0 else [0.0, float(thickness)]
    else:
        tl = [float(v) for v in thickness]
        th = [tl[1], tl[0]] if tl[0] > tl[1] else tl
    orad = (
        [float(outer_radius), float(outer_radius)]
        if isinstance(outer_radius, (int, float))
        else [float(v) for v in outer_radius]
    )
    irad = (
        [float(inner_radius), float(inner_radius)]
        if isinstance(inner_radius, (int, float))
        else [float(v) for v in inner_radius]
    )
    base = Bosl2Shape2D(_as_native_2d(children))
    outer_shape = round2d(
        outer_radius=orad[0],
        inner_radius=orad[1],
        children=base.offset(delta=th[1], fn=fn, fa=fa, fs=fs),
        fn=fn,
        fa=fa,
        fs=fs,
    )
    inner_shape = round2d(
        outer_radius=irad[1],
        inner_radius=irad[0],
        children=base.offset(delta=th[0], fn=fn, fa=fa, fs=fs),
        fn=fn,
        fa=fa,
        fs=fs,
    )
    return outer_shape - inner_shape


# -- cross / plus shape --------------------------------------------------------


def cross(
    size: float | Sequence[float] = [10, 10],
    arm_width: float | Sequence[float] | None = None,
    center: bool | None = None,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
) -> Bosl2Shape2D:
    """A 2-D cross (plus) shape: two perpendicular centred rectangles.

    Args:
        size:      overall size, a scalar square or ``[width, length]`` (default ``[10, 10]``).
        arm_width: width of each arm; a scalar or ``[horizontal, vertical]`` pair.
                   When *None* (default) the arms are one-third of the overall size.
        center:    centre alignment (default True).
        anchor:    anchor point (default CENTER).
        spin:      Z-axis rotation in degrees after anchor (default 0).

    Returns:
        A :class:`Bosl2Shape2D` wrapping the cross polygon.

    Examples:
        .. pythonscad-example::

            from pybosl2 import shapes2d as s2

            s2.cross(size=30).linear_extrude(height=5).show()
    """
    sz = [float(size)] * 2 if isinstance(size, (int, float)) else [float(size[0]), float(size[1])]
    if arm_width is None:
        aw: list[float] = [sz[0] / 3, sz[1] / 3]
    elif isinstance(arm_width, (int, float)):
        aw = [float(arm_width), float(arm_width)]
    else:
        aw = [float(arm_width[0]), float(arm_width[1])]

    hw_x, hw_y = sz[0] / 2, sz[1] / 2
    htx, hty = aw[0] / 2, aw[1] / 2

    use_anchor = anchor
    if center is not None:
        use_anchor = CENTER if center else Anchor.LEFT + Anchor.FRONT

    ha_pts = [[-hw_x, -hty], [hw_x, -hty], [hw_x, hty], [-hw_x, hty]]
    va_pts = [[-htx, -hw_y], [htx, -hw_y], [htx, hw_y], [-htx, hw_y]]
    ha_shape = Bosl2Shape2D(_opolygon(ha_pts))
    va_shape = Bosl2Shape2D(_opolygon(va_pts))
    shape = ha_shape | va_shape
    offset = _anchor_offset_box(sz, use_anchor)
    return _finish(shape, offset, spin, size=sz, anchor=use_anchor)


# ---------------------------------------------------------------------------
# Section: Text
# ---------------------------------------------------------------------------


def text(
    text: str,
    size: float = 10,
    font: str = "Liberation Sans",
    halign: str | None = None,
    valign: str | None = None,
    spacing: float = 1.0,
    direction: str = "ltr",
    language: str = "en",
    script: str = "latin",
    anchor: str = "baseline",
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Shape2D:
    """2-D text, built directly with the builtin text() (which already supports halign/valign).

    Args:
        text:      text to create
        size:      font size (default 10)
        font:      font to use (default "Liberation Sans")
        halign:    horizontal alignment: "left", "center", "right" (default "center")
        valign:    vertical alignment: "top", "center", "baseline", "bottom" (default: `anchor`)
        spacing:   relative spacing multiplier between characters (default 1.0)
        direction: text direction: "ltr", "rtl", "ttb", "btt" (default "ltr")
        language:  language the text is in (default "en")
        script:    script the text is in (default "latin")
        anchor:    vertical alignment fallback used when valign isn't given (default "baseline")
        spin:      Z-axis rotation in degrees (default 0)
    """
    h = halign if halign is not None else "center"
    v = valign if valign is not None else anchor
    shape = _otext(
        text,
        size=size,
        font=font,
        halign=h,
        valign=v,
        spacing=spacing,
        direction=direction,
        language=language,
        script=script,
        fn=fn,
        fa=fa,
        fs=fs,
    )
    return _finish(shape, [0.0, 0.0], spin)

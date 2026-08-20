# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/flat.py
# FileSummary: Statically typed 2D shape constructors and backend-neutral flat shape facade.
# DocCategory: Foundational
# FileGroup: BOSL2

"""Statically typed 2D shape constructors and backend-neutral flat shape facade."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

from pybosl2._backend import Shape, current_backend
from pybosl2._edges_lang import resolve_anchor
from pybosl2.constants import CENTER
from pybosl2.defaults import resolve_res as _resolve_res
from pybosl2.exceptions import UnsupportedByBackendError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pybosl2._backend import Solid
    from pybosl2._edges_lang import Anchor


__all__ = [
    "Flat",
    "circle",
    "ellipse",
    "regular_ngon",
    "star",
    "trapezoid",
    "polygon",
    "rect",
    "square",
    "text",
]


@runtime_checkable
class Flat(Shape, Protocol):
    """A 2-D shape: :class:`~pybosl2._backend.Shape` plus what only two dimensions can do.

    Everything shared with solids — the ``backend`` tag, the boolean operators, the transforms,
    ``bounds()`` and ``show()`` — is declared once on ``Shape`` (SPEC C-15, C-18). What is left
    here is the way up into three dimensions (SPEC C-17).
    """

    def rotate(self, a: float | Sequence[float]) -> Flat:
        """Rotate this shape *a* degrees about Z."""
        ...

    def linear_extrude(self, height: float, **kwargs: Any) -> Solid:
        """Extrude this 2-D shape into a 3-D solid."""
        ...


def circle(
    radius: float | None = None,
    diameter: float | None = None,
    *,
    points: Sequence[Sequence[float]] | None = None,
    corner: Sequence[Sequence[float]] | None = None,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Flat:
    """Return a circle on the active backend.

    Creates a 2D circle with the specified parameters.

    Args:
        radius: Radius of the circle.
        diameter: Diameter of the circle.
        points: Three 2-D points the circle should pass through.
        corner: Three 2-D points defining a path the circle should be tangent to.
        anchor: Anchor point.
        spin: Z-axis rotation in degrees after anchor.
        fn: Arc smoothness overrides (CSG backend only).
        fa: Arc smoothness overrides (CSG backend only).
        fs: Arc smoothness overrides (CSG backend only).
        res: SDF backend's resolution (SDF backend only).

    Returns:
        A 2-D flat shape representing a circle.

    Examples:
        .. pythonscad-example::

            from pybosl2.flat import circle
            circle(radius=15).linear_extrude(height=5).show()

    """
    if current_backend() == "sdf":
        from pybosl2.sdf.shapes2d import circle2d

        return cast("Flat", circle2d(radius=radius, diameter=diameter, res=_resolve_res(res) or 10))

    from pybosl2.shapes2d.circle import circle as csg_circle

    return cast(
        "Flat",
        csg_circle(
            radius=radius,
            diameter=diameter,
            points=points,
            corner=corner,
            anchor=anchor,
            spin=spin,
            fn=fn,
            fa=fa,
            fs=fs,
        ),
    )


def square(
    size: float | Sequence[float] = 1,
    *,
    center: bool | None = None,
    rounding: float | Sequence[float] = 0,
    chamfer: float | Sequence[float] = 0,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Flat:
    """Return a square on the active backend.

    Creates a 2D square with the specified size and corner treatments.

    Args:
        size: Size of the square (scalar or 2-element sequence).
        center: Whether to center the shape (CSG only).
        rounding: Corner rounding radius.
        chamfer: Corner chamfer distance.
        anchor: Anchor point.
        spin: Z-axis rotation in degrees after anchor.
        fn: Arc smoothness overrides (CSG backend only).
        fa: Arc smoothness overrides (CSG backend only).
        fs: Arc smoothness overrides (CSG backend only).
        res: SDF backend's resolution (SDF backend only).

    Returns:
        A 2-D flat shape representing a square.

    Examples:
        .. pythonscad-example::

            from pybosl2.flat import square
            square(size=20, rounding=2).linear_extrude(height=5).show()

    """
    if current_backend() == "sdf":
        from pybosl2.sdf.shapes2d import square2d

        try:
            resolved_anchor = resolve_anchor(cast("Any", anchor)).vector_2d.tolist()
        except Exception:
            resolved_anchor = list(anchor)
        return cast("Flat", square2d(size=size, anchor=resolved_anchor, res=_resolve_res(res) or 10))

    from pybosl2.shapes2d.square import square as csg_square

    return cast(
        "Flat",
        csg_square(
            size=size,
            center=center,
            rounding=rounding,
            chamfer=chamfer,
            anchor=anchor,
            spin=spin,
            fn=fn,
            fa=fa,
            fs=fs,
        ),
    )


def rect(
    size: float | Sequence[float] = 1,
    *,
    rounding: float | Sequence[float] = 0,
    chamfer: float | Sequence[float] = 0,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Flat:
    """Return a rectangle on the active backend.

    Creates a 2D rectangle with the specified dimensions and corner treatments.

    Args:
        size: Size of the rectangle (scalar or 2-element sequence).
        rounding: Corner rounding radius.
        chamfer: Corner chamfer distance.
        anchor: Anchor point.
        spin: Z-axis rotation in degrees after anchor.
        fn: Arc smoothness overrides (CSG backend only).
        fa: Arc smoothness overrides (CSG backend only).
        fs: Arc smoothness overrides (CSG backend only).
        res: SDF backend's resolution (SDF backend only).

    Returns:
        A 2-D flat shape representing a rectangle.

    Examples:
        .. pythonscad-example::

            from pybosl2.flat import rect
            rect(size=[30, 20], rounding=3).linear_extrude(height=5).show()

    """
    if current_backend() == "sdf":
        from pybosl2.sdf.shapes2d import rect2d

        try:
            resolved_anchor = resolve_anchor(cast("Any", anchor)).vector_2d.tolist()
        except Exception:
            resolved_anchor = list(anchor)
        return cast(
            "Flat",
            rect2d(
                size=size,
                rounding=rounding,
                chamfer=chamfer,
                anchor=resolved_anchor,
                res=_resolve_res(res) or 10,
            ),
        )

    from pybosl2.shapes2d.square import rect as csg_rect

    return cast(
        "Flat",
        csg_rect(
            size=size,
            rounding=rounding,
            chamfer=chamfer,
            anchor=anchor,
            spin=spin,
            fn=fn,
            fa=fa,
            fs=fs,
        ),
    )


def polygon(
    points: Sequence[Sequence[float]],
    *,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    res: int | None = None,
) -> Flat:
    """Return a polygon on the active backend.

    Creates a 2D polygon from list of points.

    Args:
        points: Sequence of 2-D points.
        anchor: Anchor point.
        spin: Z-axis rotation in degrees after anchor.
        res: SDF backend's resolution (SDF backend only).

    Returns:
        A 2-D flat shape representing a polygon.

    Examples:
        .. pythonscad-example::

            from pybosl2.flat import polygon
            polygon(points=[[0, 0], [10, 0], [5, 10]]).linear_extrude(height=5).show()

    """
    if current_backend() == "sdf":
        from pybosl2.sdf.shapes2d import polygon2d

        return cast("Flat", polygon2d(paths=points, res=_resolve_res(res) or 10))

    from pybosl2.path2d import Path2D
    from pybosl2.shapes2d.square import polygon as csg_polygon

    return cast(
        "Flat",
        csg_polygon(
            path=Path2D(points),
            anchor=anchor,
            spin=spin,
        ),
    )


def text(
    text: str,
    *,
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
) -> Flat:
    """Return a text shape on the active backend.

    Creates a 2D shape representing the given text.

    Args:
        text: The string content.
        size: Text height.
        font: Font family name.
        halign: Horizontal alignment.
        valign: Vertical alignment.
        spacing: Character spacing factor.
        direction: Text direction.
        language: Language code.
        script: Script code.
        anchor: Anchor point.
        spin: Z-axis rotation in degrees after anchor.
        fn: Arc smoothness overrides (CSG backend only).
        fa: Arc smoothness overrides (CSG backend only).
        fs: Arc smoothness overrides (CSG backend only).

    Returns:
        A 2-D flat shape representing text.

    Examples:
        .. pythonscad-example::

            from pybosl2.flat import text
            text(text="BOSL2", size=10).linear_extrude(height=3).show()

    """
    if current_backend() == "sdf":
        raise UnsupportedByBackendError(
            "text",
            "sdf",
            hint="the sdf backend has no 2-D text support; build on the default (csg) backend.",
        )

    from pybosl2.shapes2d.ops import text as csg_text

    return cast(
        "Flat",
        csg_text(
            text=text,
            size=size,
            font=font,
            halign=halign,
            valign=valign,
            spacing=spacing,
            direction=direction,
            language=language,
            script=script,
            anchor=anchor,
            spin=spin,
            fn=fn,
            fa=fa,
            fs=fs,
        ),
    )


def ellipse(
    radius: float | Sequence[float] | None = None,
    diameter: float | Sequence[float] | None = None,
    *,
    realign: bool = False,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Flat:
    """Return an ellipse on the active backend.

    Args:
        radius: Radius, or a per-axis pair.
        diameter: Diameter, or a per-axis pair.
        realign: Rotate by half a segment so a flat faces +X (CSG backend only).
        anchor: Anchor point.
        spin: Z-axis rotation in degrees after anchor (CSG backend only).
        fn: Arc smoothness override (CSG backend only).
        fa: Arc smoothness override (CSG backend only).
        fs: Arc smoothness override (CSG backend only).
        res: Sampling resolution (SDF backend only).

    Returns:
        A 2-D shape on whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2.flat import ellipse
            ellipse(radius=[20, 10]).linear_extrude(height=4).show()

    """
    if current_backend() == "sdf":
        from pybosl2.sdf.shapes2d import ellipse2d

        return cast("Flat", ellipse2d(radius=radius, diameter=diameter, res=_resolve_res(res) or 10))

    from pybosl2.shapes2d import ellipse as csg_ellipse

    return cast(
        "Flat",
        csg_ellipse(radius=radius, diameter=diameter, realign=realign, anchor=anchor, spin=spin, fn=fn, fa=fa, fs=fs),
    )


def star(
    tips: int = 5,
    radius: float | None = None,
    inner_radius: float | None = None,
    *,
    diameter: float | None = None,
    inner_diameter: float | None = None,
    step: int | None = None,
    realign: bool = False,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    res: int | None = None,
) -> Flat:
    """Return a star on the active backend.

    Args:
        tips: Number of points.
        radius: Outer radius (to the tips).
        inner_radius: Inner radius (to the valleys).
        diameter: Outer diameter, instead of *radius*.
        inner_diameter: Inner diameter, instead of *inner_radius*.
        step: Skip-count star form, instead of an inner radius (CSG backend only).
        realign: Rotate by half a point (CSG backend only).
        anchor: Anchor point.
        spin: Z-axis rotation in degrees after anchor (CSG backend only).
        res: Sampling resolution (SDF backend only).

    Returns:
        A 2-D shape on whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2.flat import star
            star(tips=6, radius=20, inner_radius=9).linear_extrude(height=4).show()

    """
    if current_backend() == "sdf":
        from pybosl2.sdf.shapes2d import star2d

        return cast(
            "Flat",
            star2d(
                num_sides=tips,
                radius=radius,
                inner_radius=inner_radius,
                diameter=diameter,
                inner_diameter=inner_diameter,
                res=_resolve_res(res) or 10,
            ),
        )

    from pybosl2.shapes2d import star as csg_star

    return cast(
        "Flat",
        csg_star(
            tips=tips,
            radius=radius,
            inner_radius=inner_radius,
            diameter=diameter,
            inner_diameter=inner_diameter,
            step=step,
            realign=realign,
            anchor=anchor,
            spin=spin,
        ),
    )


def regular_ngon(
    sides: int = 6,
    radius: float | None = None,
    *,
    diameter: float | None = None,
    outer_radius: float | None = None,
    outer_diameter: float | None = None,
    rounding: float = 0,
    realign: bool = False,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Flat:
    """Return a regular polygon on the active backend.

    Args:
        sides: Number of sides.
        radius: Radius to a vertex.
        diameter: Diameter to a vertex, instead of *radius*.
        outer_radius: Radius of the circumscribed circle.
        outer_diameter: Diameter of the circumscribed circle.
        rounding: Corner rounding radius (CSG backend only).
        realign: Rotate by half a side (CSG backend only).
        anchor: Anchor point.
        spin: Z-axis rotation in degrees after anchor (CSG backend only).
        fn: Fragment count for the rounded corners; ambient default when omitted.
        fa: Minimum fragment angle for the rounded corners.
        fs: Minimum fragment size for the rounded corners.
        res: Sampling resolution (SDF backend only).

    Returns:
        A 2-D shape on whichever backend is active.

    Raises:
        UnsupportedByBackendError: If *rounding* is asked for on the SDF backend, which has no
            rounded-corner ngon.

    Examples:
        .. pythonscad-example::

            from pybosl2.flat import regular_ngon
            regular_ngon(sides=7, radius=15).linear_extrude(height=4).show()

    """
    if current_backend() == "sdf":
        if rounding:
            raise UnsupportedByBackendError(
                "regular_ngon(rounding=)",
                "sdf",
                hint="the sdf ngon has no corner rounding; build it on the csg backend, or round "
                "the field with .round() afterwards.",
            )
        from pybosl2.sdf.shapes2d import regular_ngon2d

        return cast(
            "Flat",
            regular_ngon2d(
                num_sides=sides,
                radius=radius,
                diameter=diameter,
                outer_radius=outer_radius,
                outer_diameter=outer_diameter,
                res=_resolve_res(res) or 10,
            ),
        )

    from pybosl2.shapes2d import regular_ngon as csg_ngon

    return cast(
        "Flat",
        csg_ngon(
            sides=sides,
            radius=radius,
            diameter=diameter,
            outer_radius=outer_radius,
            outer_diameter=outer_diameter,
            rounding=rounding,
            realign=realign,
            anchor=anchor,
            spin=spin,
            fn=fn,
            fa=fa,
            fs=fs,
        ),
    )


def trapezoid(
    height: float | None = None,
    width1: float | None = None,
    width2: float | None = None,
    *,
    angle: float | None = None,
    shift: float = 0,
    anchor: Anchor | Sequence[float] = CENTER,
    spin: float = 0,
    res: int | None = None,
) -> Flat:
    """Return a trapezoid on the active backend.

    Give exactly three of *height*, *width1*, *width2* and *angle*.

    Args:
        height: Height of the trapezoid.
        width1: Width of the bottom edge.
        width2: Width of the top edge.
        angle: Base angle in degrees.
        shift: Shift of the top edge along X.
        anchor: Anchor point.
        spin: Z-axis rotation in degrees after anchor (CSG backend only).
        res: Sampling resolution (SDF backend only).

    Returns:
        A 2-D shape on whichever backend is active.

    Raises:
        ValueError: If other than three of height/width1/width2/angle are given.

    Examples:
        .. pythonscad-example::

            from pybosl2.flat import trapezoid
            trapezoid(height=10, width1=20, width2=12).linear_extrude(height=4).show()

    """
    if current_backend() == "sdf":
        from pybosl2.sdf.shapes2d import trapezoid2d

        return cast(
            "Flat",
            trapezoid2d(
                height=height, width1=width1, width2=width2, angle=angle, shift=shift, res=_resolve_res(res) or 10
            ),
        )

    from pybosl2.shapes2d import trapezoid as csg_trapezoid

    return cast(
        "Flat",
        csg_trapezoid(height=height, width1=width1, width2=width2, angle=angle, shift=shift, anchor=anchor, spin=spin),
    )

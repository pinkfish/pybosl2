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

from pybosl2._backend import current_backend
from pybosl2._edges_lang import resolve_anchor
from pybosl2.constants import CENTER
from pybosl2.exceptions import UnsupportedByBackendError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pybosl2._edges_lang import Anchor


@runtime_checkable
class Flat(Protocol):
    """The common 2-D shape contract both backend wrappers satisfy.

    A ``Flat`` carries a ``backend`` tag; booleans/transforms return a ``Flat`` on the *same*
    backend, and combining shapes from two backends raises
    :class:`~pybosl2.exceptions.CrossBackendError`.
    """

    backend: str

    def __or__(self, other: Any) -> Any:
        """Union of two 2D shapes."""
        ...

    def __and__(self, other: Any) -> Any:
        """Intersection of two 2D shapes."""
        ...

    def __sub__(self, other: Any) -> Any:
        """Difference of two 2D shapes."""
        ...

    def translate(self, v: Any) -> Any:
        """Translate this shape by vector *v*."""
        ...

    def rotate(self, a: Any) -> Any:
        """Rotate this shape by *a*."""
        ...

    def scale(self, v: Any) -> Any:
        """Scale this shape by *v*."""
        ...

    def mirror(self, v: Any) -> Any:
        """Mirror this shape across plane/axis *v*."""
        ...

    def linear_extrude(self, height: float, **kwargs: Any) -> Any:
        """Extrude this 2-D shape into a 3-D solid."""
        ...


# Backward compatibility alias
Shape2D = Flat


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

        return cast("Flat", circle2d(radius=radius, diameter=diameter, res=res or 10))

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
        return cast("Flat", square2d(size=size, anchor=resolved_anchor, res=res or 10))

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
                res=res or 10,
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

        return cast("Flat", polygon2d(paths=points, res=res or 10))

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

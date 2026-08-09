# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/svg.py
#    Load an SVG drawing as real path data -- a Region of Path2D outlines -- rather than
#    handing the file to the renderer's own importer and getting back an opaque handle.
#
# FileSummary: Load SVG drawings into a Region of outlines.
# DocCategory: Paths, regions & surfaces
# FileGroup: BOSL2

"""Load SVG drawings into a Region of outlines."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pybosl2.path2d import Path2D
    from pybosl2.regions import Region

__all__ = ["svg_outlines", "region_from_svg", "svg_rings_with_colors", "regions_from_svg"]

#: Default minimum fragment count (``fn``).  When set (``>= 3``) it overrides *fa*/*fs*
#: for curved SVG segments, giving an absolute number of points per segment.
DEFAULT_FN: int | None = None
#: Default minimum angle between fragments in degrees (``fa``).  Relevant for circular
#: arcs; passed through but not used directly for generic beziers.
DEFAULT_FA: float | None = None
#: Default minimum fragment size in the SVG's own user units (``fs``).  Curved segments
#: get ``max(3, ceil(segment_length / fs))`` points, which keeps short curves light and
#: long curves smooth.
DEFAULT_FS: float = 2.0


def _curve_point_count(segment: object, fn: int | None, fs: float) -> int:
    """Return the number of points to sample when flattening one curved SVG segment.

    Args:
        segment: An svgelements segment with a ``.length()`` method.
        fn: Absolute point count override (``>= 3``).
        fs: Minimum fragment size; used when *fn* is ``None``.

    Returns:
        The number of evenly-spaced sample points, never fewer than 3.

    """
    if fn is not None and fn >= 3:
        return fn
    length: float = segment.length()  # type: ignore[attr-defined]
    return max(3, math.ceil(length / fs))


def svg_outlines(
    file: str,
    fn: int | None = DEFAULT_FN,
    fa: float | None = DEFAULT_FA,
    fs: float = DEFAULT_FS,
    flip_y: bool = True,
) -> list[list[list[float]]]:
    """Return an SVG's outlines as plain ``[[x, y], ...]`` point rings.

    Every subpath of every shape becomes one closed ring. Curves (cubic/quadratic béziers and
    arcs) are flattened to sampled points; the number of samples is controlled by *fn*, *fa*
    and *fs* (the same ``$fn``/``$fa``/``$fs`` triplet OpenSCAD uses).  Straight segments
    keep their endpoints.

    The raw rings, with no nesting applied -- see :func:`region_from_svg` to get a
    :class:`~pybosl2.regions.Region` with holes resolved.

    Args:
        file: Path to the SVG.
        fn: Minimum fragment count per curved segment.  When set (``>= 3``) it gives an
            absolute point count; otherwise points are derived from *fs*.
        fa: Minimum angle in degrees between fragments (accepted for API parity; only
            relevant for circular arcs).
        fs: Minimum fragment size in SVG user units.  Each curved segment gets
            ``max(3, ceil(length / fs))`` points.
        flip_y: Negate Y. SVG's Y axis points DOWN and OpenSCAD's points UP, so without this
            every imported drawing comes out mirrored.

    Returns:
        One list of ``[x, y]`` points per ring, in the SVG's own USER UNITS. The renderer's
        importer instead converts px to mm at 72 dpi (a factor of 25.4/72); nothing here
        guesses at a physical size, so resize the result to whatever the part needs.

    Raises:
        ImportError: If ``svgelements`` is not installed.

    """
    try:
        from svgelements import SVG, Close, Line, Move, Path, Shape
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError("loading SVG needs the 'svgelements' package (pip install svgelements)") from exc

    _ = fa  # accepted for API parity; bezier curves use *fn*/*fs* only
    sign = -1.0 if flip_y else 1.0
    rings: list[list[list[float]]] = []
    for element in SVG.parse(file).elements():
        if not isinstance(element, Shape):
            continue
        for subpath in Path(element).as_subpaths():
            ring: list[list[float]] = []
            for segment in subpath:
                if isinstance(segment, Close):
                    continue
                if isinstance(segment, (Move, Line)):
                    # float(): svgelements hands back numpy scalars, which the native
                    # polygon()/FFI boundary rejects further downstream.
                    ring.append([float(segment.end.x), sign * float(segment.end.y)])
                    continue
                count = _curve_point_count(segment, fn, fs)
                for i in range(1, count + 1):
                    point = segment.point(i / count)
                    ring.append([float(point.x), sign * float(point.y)])
            # A closed subpath repeats its start point; Path2D/Region want the bare ring.
            if len(ring) > 1 and ring[0] == ring[-1]:
                ring.pop()
            if len(ring) >= 3:
                rings.append(ring)
    return rings


def region_from_svg(
    file: str,
    fn: int | None = DEFAULT_FN,
    fa: float | None = DEFAULT_FA,
    fs: float = DEFAULT_FS,
    flip_y: bool = True,
    color: str | None = None,
) -> "Region":
    """Load an SVG drawing as a :class:`~pybosl2.regions.Region`.

    The alternative to handing the file to the renderer's importer: that returns an opaque
    handle you can only transform, while this returns real outlines you can measure, offset,
    round, tessellate or use as a lid pattern -- and it needs no renderer, so SVG-derived
    shapes become testable without one.

    Nesting is resolved with the EVEN-ODD rule (:meth:`~pybosl2.regions.Region.even_odd`),
    which is what a traced drawing means by a hole: an outline inside one solid cuts it, an
    outline inside that hole is solid again.

    Args:
        file: Path to the SVG.
        fn: Minimum fragment count per curved segment (``>= 3`` → absolute point count).
        fa: Minimum angle in degrees (accepted for API parity; see :func:`svg_outlines`).
        fs: Minimum fragment size in SVG user units (default ``2.0``).
        flip_y: Negate Y so the drawing is not mirrored (SVG's Y axis points down).
        color: When set, overrides every shape's fill colour with this hex string
            (e.g. ``"#ff0000"``).  Pass ``None`` (the default) to use the SVG's own colours.

    Returns:
        A :class:`~pybosl2.regions.Region` of the drawing.

    Raises:
        ImportError: If ``svgelements`` is not installed.

    Examples:
        An imported drawing, inset and extruded into a plate:

        .. pythonscad-example::

            import os, tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".svg", mode="w", delete=False)
            tmp.write('<svg xmlns="http://www.w3.org/2000/svg"><path d="M10,10H90V90H10Z"/></svg>')
            tmp.close()

            from pybosl2 import Region

            result = Region.from_svg(tmp.name).offset(delta=-0.5).geometry().linear_extrude(height=2)
            os.unlink(tmp.name)
            result.show()

    """
    from pybosl2.color import Color
    from pybosl2.regions import Region

    paths, colors = svg_rings_with_colors(file, fn=fn, fa=fa, fs=fs, flip_y=flip_y, color=color)
    if not paths:
        return Region()
    colored_paths = [p.color(Color(c)) if c is not None else p for p, c in zip(paths, colors, strict=True)]
    return Region.even_odd(colored_paths)


def svg_rings_with_colors(
    file: str,
    fn: int | None = DEFAULT_FN,
    fa: float | None = DEFAULT_FA,
    fs: float = DEFAULT_FS,
    flip_y: bool = True,
    color: str | None = None,
) -> tuple[list[Path2D], list[str | None]]:
    """Return an SVG's outlines as :class:`~pybosl2.path2d.Path2D` objects and their fill colours.

    Every subpath of every shape becomes one closed :class:`~pybosl2.path2d.Path2D`; the colour
    list gives the hex fill colour of the shape each ring came from (or ``None`` for shapes
    with no fill / pattern fills).  The rings themselves are identical to those returned by
    :func:`svg_outlines` but as typed objects.

    The return value can be unpacked directly::

        paths, colors = svg_rings_with_colors("drawing.svg")

    Args:
        file: Path to the SVG.
        fn: Minimum fragment count per curved segment (``>= 3`` → absolute point count).
        fa: Minimum angle in degrees (accepted for API parity; see :func:`svg_outlines`).
        fs: Minimum fragment size in SVG user units (default ``2.0``).
        flip_y: Negate Y so the drawing is not mirrored.
        color: When set, every returned ring gets this colour instead of the SVG's
            own fill colours.  Pass ``None`` (the default) to use the colours from the SVG.

    Returns:
        A ``(paths, colors)`` tuple where *paths* is ``[Path2D, ...]`` and *colors* is a
        parallel list of ``"#rrggbb"`` hex strings or ``None`` for unfilled shapes.

    Raises:
        ImportError: If ``svgelements`` is not installed.

    """
    try:
        from svgelements import SVG, Close, Line, Move, Shape
        from svgelements import Path as _SVGPath
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError("loading SVG needs the 'svgelements' package (pip install svgelements)") from exc

    from pybosl2.path2d import Path2D

    _ = fa  # accepted for API parity; bezier curves use *fn*/*fs* only
    sign = -1.0 if flip_y else 1.0
    paths: list[Path2D] = []
    colors: list[str | None] = []
    for element in SVG.parse(file).elements():
        if not isinstance(element, Shape):
            continue
        fill_color: str | None = _shape_fill_hex(getattr(element, "fill", None))
        for subpath in _SVGPath(element).as_subpaths():
            ring: list[list[float]] = []
            for segment in subpath:
                if isinstance(segment, Close):
                    continue
                if isinstance(segment, (Move, Line)):
                    ring.append([float(segment.end.x), sign * float(segment.end.y)])
                    continue
                count = _curve_point_count(segment, fn, fs)
                for i in range(1, count + 1):
                    point = segment.point(i / count)
                    ring.append([float(point.x), sign * float(point.y)])
            if len(ring) > 1 and ring[0] == ring[-1]:
                ring.pop()
            if len(ring) >= 3:
                paths.append(Path2D(ring, closed=True))
                colors.append(fill_color)
    if color is not None:
        colors = [color] * len(colors)
    return paths, colors


def _shape_fill_hex(fill: object) -> str | None:
    """Extract a ``#rrggbb`` hex string from an svgelements fill, or ``None``.

    ``fill="none"`` (transparent) and pattern/gradient fills return ``None``.
    An absent ``fill`` attribute (SVG default = black) is treated as a real
    ``#000000`` colour.  ``fill-opacity`` is already baked into the hex string
    by svgelements (e.g. ``fill-opacity=0.5`` on ``#ff0000`` → ``#ff000080``).
    """
    if fill is None:
        return None
    if hasattr(fill, "value") and fill.value is None:
        return None
    if hasattr(fill, "hex"):
        raw = fill.hex
        if raw is None:
            return None
        if isinstance(raw, str):
            return raw
    return None


def regions_from_svg(
    file: str,
    fn: int | None = DEFAULT_FN,
    fa: float | None = DEFAULT_FA,
    fs: float = DEFAULT_FS,
    flip_y: bool = True,
    color: str | None = None,
) -> list["Region"]:
    """Load an SVG drawing as a list of :class:`~pybosl2.regions.Region` objects, coloured.

    Shapes with the same fill colour are grouped into one :class:`~pybosl2.regions.Region`;
    shapes with no fill colour (or pattern/gradient fills) are grouped into an uncoloured
    Region.  The result is a list of Regions that can each be offset, extruded or rendered
    independently, each carrying the SVG's colour through to the output.

    Args:
        file: Path to the SVG.
        fn: Minimum fragment count per curved segment (``>= 3`` → absolute point count).
        fa: Minimum angle in degrees (accepted for API parity; see :func:`svg_outlines`).
        fs: Minimum fragment size in SVG user units (default ``2.0``).
        flip_y: Negate Y so the drawing is not mirrored.
        color: When set, overrides every shape's fill colour with this hex string
            (e.g. ``"#ff0000"``).  Pass ``None`` (the default) to use the SVG's own colours.

    Returns:
        A list of :class:`~pybosl2.regions.Region` objects, one per distinct fill colour
        found in the SVG.  Each Region has its colour set via :meth:`Region.color`.

    Raises:
        ImportError: If ``svgelements`` is not installed.

    Examples:
        An imported drawing with two colours, extruded and shown side by side:

        .. pythonscad-example::

            import os, tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".svg", mode="w", delete=False)
            tmp.write('<svg xmlns="http://www.w3.org/2000/svg">'
                      '<path d="M10,10H40V40H10Z" fill="#ff0000"/>'
                      '<path d="M50,10H80V40H50Z" fill="#0000ff"/>'
                      '</svg>')
            tmp.close()

            from pybosl2.svg import regions_from_svg

            parts = regions_from_svg(tmp.name)
            os.unlink(tmp.name)
            import pythonscad as ps
            for region in parts:
                region.geometry().linear_extrude(height=3)
            ps.show()

    """
    from pybosl2.color import Color
    from pybosl2.regions import Region

    paths, colors = svg_rings_with_colors(file, fn=fn, fa=fa, fs=fs, flip_y=flip_y, color=color)

    groups: dict[str | None, list[Path2D]] = {}
    for path, color in zip(paths, colors, strict=True):
        groups.setdefault(color, []).append(path)

    results: list[Region] = []
    for color_hex, rings in groups.items():
        region = Region.even_odd(rings)
        if color_hex is not None:
            region = region.color(Color(color_hex))
        results.append(region)
    return results

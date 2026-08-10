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

__all__ = ["svg_outlines", "region_from_svg", "svg_rings_with_colors", "svg_element_groups", "regions_from_svg"]

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
    # error=: svgelements' length() defaults to an extremely tight tolerance and reaches it by
    # recursive subdivision -- 4.8 MILLION segment_length calls for the 236 curves in a 7 KB
    # drawing, 196s to load one file. The result here only picks a fragment COUNT, so a tenth
    # of a fragment is far more precision than the ceil() below can use. Same counts, ~80x
    # faster per segment.
    length: float = segment.length(error=max(fs / 10.0, 1e-3))  # type: ignore[attr-defined]
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
    strokes: str = "polygon",
) -> "Region":
    """Load an SVG drawing as a :class:`~pybosl2.regions.Region`.

    The alternative to handing the file to the renderer's importer: that returns an opaque
    handle you can only transform, while this returns real outlines you can measure, offset,
    round, tessellate or use as a lid pattern -- and it needs no renderer, so SVG-derived
    shapes become testable without one.

    Nesting is resolved with the EVEN-ODD rule (:meth:`~pybosl2.regions.Region.even_odd`)
    among shapes of the SAME colour -- what a traced drawing means by a hole: an outline
    inside one solid cuts it, an outline inside that hole is solid again. Shapes of
    DIFFERENT colours are composited in SVG paint order instead, each covering whatever was
    drawn before it, so the returned pieces never overlap.

    Args:
        file: Path to the SVG.
        fn: Minimum fragment count per curved segment (``>= 3`` → absolute point count).
        fa: Minimum angle in degrees (accepted for API parity; see :func:`svg_outlines`).
        fs: Minimum fragment size in SVG user units (default ``2.0``).
        flip_y: Negate Y so the drawing is not mirrored (SVG's Y axis points down).
        color: When set, overrides every shape's fill colour with this hex string
            (e.g. ``"#ff0000"``).  Pass ``None`` (the default) to use the SVG's own colours.
        strokes: ``"polygon"`` (default) converts stroked paths into filled polygons.
            ``"ignore"`` skips shapes that have only a stroke and no fill.

    Returns:
        A :class:`~pybosl2.regions.Region` of the drawing.

    Raises:
        ImportError: If ``svgelements`` is not installed.

    Examples:
        An imported drawing, inset and extruded into a plate::

            import os, tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".svg", mode="w", delete=False)
            tmp.write('<svg xmlns="http://www.w3.org/2000/svg"><path d="M10,10H90V90H10Z"/></svg>')
            tmp.close()

            from pybosl2 import Region

            result = Region.from_svg(tmp.name).offset(delta=-0.5).geometry().linear_extrude(height=2)
            result.show()
            os.unlink(tmp.name)

    """
    from shapely.ops import unary_union as _shapely_unary_union

    from pybosl2.color import Color
    from pybosl2.regions import Region

    groups = svg_element_groups(file, fn=fn, fa=fa, fs=fs, flip_y=flip_y, color=color, strokes=strokes)
    if not groups:
        return Region()

    # ONE COLOUR IS ONE SHAPE; DIFFERENT COLOURS ARE LAYERS IN PAINT ORDER.
    #
    # Neither rule alone works. Resolving every ring of the whole file in a single even-odd
    # pass (what this used to do) makes any nested shape a HOLE, so the Portuguese flag's
    # green field became a hole in its red one and its coat of arms became holes in the
    # field it sits on. But strict SVG paint order is just as wrong for drawings meant as
    # CAD input: a plate and its holes are usually separate <path> elements with no fill, and
    # painting one over the other would leave a solid plate with no holes at all.
    #
    # Splitting on colour serves both, because it follows what is actually visible. Shapes
    # sharing a colour are indistinguishable once painted, so reading the nested ones as
    # holes loses nothing and keeps the plate-with-holes convention. Shapes of DIFFERENT
    # colours are visible as separate things and must obey paint order.
    # CONSECUTIVE same-colour shapes only. Pooling every shape of a colour into one layer
    # instead would date that layer from the LAST time the colour appeared, so a single late
    # red detail anywhere in a drawing hoists the red BACKGROUND above everything painted
    # after it -- on the flag that erased the green field completely.
    layers: list[tuple[str | None, list[Path2D]]] = []
    for hex_color, rings in groups:
        if layers and layers[-1][0] == hex_color:
            layers[-1][1].extend(rings)
        else:
            layers.append((hex_color, list(rings)))

    # Composite back to front, so each layer is clipped by everything drawn over it: one
    # difference and one union per layer instead of re-clipping every earlier layer each
    # time. Disjoint by construction, which is what keeps each colour body manifold.
    placed: list[tuple[object, object]] = []
    covered = None
    for hex_color, layer_rings in reversed(layers):
        piece = Region.even_odd(layer_rings).geom
        if piece.is_empty:
            continue
        if covered is not None:
            piece = piece.difference(covered)
            if piece.is_empty:
                continue
            # Clipping can leave a layer as several polygons that merely TOUCH along the cut.
            # Extruded separately those share faces, so the colour's body comes out
            # non-manifold; dissolving merges them back into one polygon each.
            piece = _shapely_unary_union(piece)
        covered = piece if covered is None else covered.union(piece)
        placed.append((Color(hex_color) if hex_color is not None else None, piece))
    placed.reverse()
    return Region._from_colored_pieces(placed)


def svg_element_groups(
    file: str,
    fn: int | None = DEFAULT_FN,
    fa: float | None = DEFAULT_FA,
    fs: float = DEFAULT_FS,
    flip_y: bool = True,
    color: str | None = None,
    strokes: str = "polygon",
) -> list[tuple[str | None, list[Path2D]]]:
    """Return an SVG's shapes, IN PAINT ORDER, each with its own rings kept together.

    This grouping is the thing compositing needs and flattening destroys: a ring nested
    inside another means "hole" only when both came from the SAME element (that is what
    ``fill-rule`` decides). Two separate elements that happen to nest -- a flag's green
    field drawn on top of its red one -- are not a solid and a hole, they are two shapes,
    the later one painted over the earlier.

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
        strokes: How to handle stroked paths.  ``"polygon"`` (default) converts each
            stroked path to a filled polygon via shapely buffering so strokes appear
            as solid coloured pieces.  ``"ignore"`` skips shapes that have a stroke
            but no fill colour.

    Returns:
        ``[(colour, [Path2D, ...]), ...]`` in document (paint) order -- one entry per
        filled shape, plus one per stroked shape (a stroke paints over its own fill).

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
    groups: list[tuple[str | None, list[Path2D]]] = []
    for element in SVG.parse(file).elements():
        if not isinstance(element, Shape):
            continue
        fill_color: str | None = _shape_fill_hex(element)
        fill_rings: list[Path2D] = []
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
                fill_rings.append(Path2D(ring, closed=True))
        if fill_rings:
            groups.append((fill_color, fill_rings))
        if strokes == "polygon":
            stroke_color: str | None = _shape_stroke_hex(element)
            if stroke_color is not None and (fill_color is None or fill_color != stroke_color):
                stroke_width = float(getattr(element, "stroke_width", 1.0) or 1.0)
                stroke_rings: list[Path2D] = []
                for subpath in _SVGPath(element).as_subpaths():
                    stroke_ring_pts: list[list[float]] = []
                    for segment in subpath:
                        if isinstance(segment, Close):
                            continue
                        if isinstance(segment, (Move, Line)):
                            stroke_ring_pts.append([float(segment.end.x), sign * float(segment.end.y)])
                            continue
                        count = _curve_point_count(segment, fn, fs)
                        for i in range(1, count + 1):
                            point = segment.point(i / count)
                            stroke_ring_pts.append([float(point.x), sign * float(point.y)])
                    if len(stroke_ring_pts) < 2:
                        continue
                    stroke_ring = _stroke_to_polygon(stroke_ring_pts, stroke_width / 2)
                    if stroke_ring is not None and len(stroke_ring) >= 3:
                        stroke_rings.append(Path2D(stroke_ring, closed=True))
                # A stroke paints ON TOP of its own element's fill, so it is its own group.
                if stroke_rings:
                    groups.append((stroke_color, stroke_rings))
    if color is not None:
        groups = [(color, rings) for _c, rings in groups]
    return groups


def svg_rings_with_colors(
    file: str,
    fn: int | None = DEFAULT_FN,
    fa: float | None = DEFAULT_FA,
    fs: float = DEFAULT_FS,
    flip_y: bool = True,
    color: str | None = None,
    strokes: str = "polygon",
) -> tuple[list["Path2D"], list[str | None]]:
    """Every closed ring in an SVG, flattened, with the fill colour of each.

    The element each ring came from is NOT preserved -- use
    :func:`svg_element_groups` when that matters (it does for compositing: nesting means
    "hole" only WITHIN one element).
    """
    paths: list[Path2D] = []
    colors: list[str | None] = []
    for element_color, rings in svg_element_groups(
        file, fn=fn, fa=fa, fs=fs, flip_y=flip_y, color=color, strokes=strokes
    ):
        for ring in rings:
            paths.append(ring)
            colors.append(element_color)
    return paths, colors


def _shape_fill_hex(element: object) -> str | None:
    """Extract a ``#rrggbb`` hex string from an svgelements Shape, or ``None``.

    ``fill="none"``, pattern/gradient fills, and the SVG's implicit black
    default fill (no ``fill`` attribute, no inherited colour) all return
    ``None``.  Inherited fills from a ``<g>`` group or similar produce the
    resolved colour because svgelements propagates them to the child.
    """
    fill = getattr(element, "fill", None)
    if fill is None:
        return None
    if hasattr(fill, "value") and fill.value is None:
        return None
    # An element whose raw SVG attributes lack a ``fill`` key did not set
    # its own fill.  It may have inherited one (from a parent <g>) or it
    # may be falling back to the SVG default (black).  svgelements resolves
    # both, so we check whether the resolved colour is the default black --
    # if so and there was no explicit fill, it is not a "real" colour.
    if hasattr(element, "values"):
        raw_attrs: dict[str, object] = dict(element.values.get("attributes", {}))
        if "fill" not in raw_attrs and fill.hex == "#000000" and fill.opacity == 1.0:
            return None
    if hasattr(fill, "hex") and isinstance(fill.hex, str):
        return fill.hex
    return None


def _shape_stroke_hex(element: object) -> str | None:
    """Extract stroke colour as a ``#rrggbb`` hex from an svgelements Shape, or ``None``."""
    stroke = getattr(element, "stroke", None)
    if stroke is None:
        return None
    if hasattr(stroke, "value") and stroke.value is None:
        return None
    if hasattr(stroke, "hex") and isinstance(stroke.hex, str):
        return stroke.hex
    return None


def _stroke_to_polygon(ring: list[list[float]], radius: float) -> list[list[float]] | None:
    """Buffer a linestring by *radius* and return the resulting polygon ring.

    Returns ``None`` if the buffer produces no geometry or an empty polygon.
    """
    from shapely.geometry import LineString

    if len(ring) < 2 or radius <= 0:
        return None
    line = LineString([(float(p[0]), float(p[1])) for p in ring])
    buffered = line.buffer(radius, cap_style="round", join_style="round")
    if buffered.is_empty:
        return None
    return [[float(x), float(y)] for x, y in buffered.exterior.coords[:-1]]


def regions_from_svg(
    file: str,
    fn: int | None = DEFAULT_FN,
    fa: float | None = DEFAULT_FA,
    fs: float = DEFAULT_FS,
    flip_y: bool = True,
    color: str | None = None,
    strokes: str = "polygon",
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
        strokes: ``"polygon"`` (default) converts stroked paths into filled polygons.
            ``"ignore"`` skips shapes that have only a stroke and no fill.

    Returns:
        A list of :class:`~pybosl2.regions.Region` objects, one per distinct fill colour
        found in the SVG.  Each Region has its colour set via :meth:`Region.color`.

    Raises:
        ImportError: If ``svgelements`` is not installed.

    Examples:
        An imported drawing with two colours, extruded and shown side by side::

            import os, tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".svg", mode="w", delete=False)
            tmp.write('<svg xmlns="http://www.w3.org/2000/svg">'
                      '<path d="M10,10H40V40H10Z" fill="#ff0000"/>'
                      '<path d="M50,10H80V40H50Z" fill="#0000ff"/>'
                      '</svg>')
            tmp.close()

            from pybosl2.svg import regions_from_svg

            parts = regions_from_svg(tmp.name)
            import pythonscad as ps
            for region in parts:
                region.geometry().linear_extrude(height=3)
            ps.show()
            os.unlink(tmp.name)

    """
    from pybosl2.color import Color
    from pybosl2.regions import Region

    paths, colors = svg_rings_with_colors(file, fn=fn, fa=fa, fs=fs, flip_y=flip_y, color=color, strokes=strokes)

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

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
import pathlib
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

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
    clip_to_viewbox: bool = True,
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
        clip_to_viewbox: When True (the default), clip the drawing to the SVG's
            ``viewBox`` if one is declared, so shapes that paint outside the
            intended canvas are trimmed away.

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

    groups = svg_element_groups(
        file,
        fn=fn,
        fa=fa,
        fs=fs,
        flip_y=flip_y,
        color=color,
        strokes=strokes,
        clip_to_viewbox=clip_to_viewbox,
    )
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


def _shape_rings(element: object, sign: float, fn: "int | None", fs: float) -> list[list[list[float]]]:
    """Flatten one svgelements Shape into closed point rings."""
    from svgelements import Close, Line, Move
    from svgelements import Path as _SVGPath

    rings: list[list[list[float]]] = []
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
            rings.append(ring)
    return rings


def _rings_to_shapely(rings: "list[list[list[float]]]") -> Any:
    """Return the shapely geometry a set of rings describes, even-odd, repaired.

    Even-odd for real: a ring contained by an odd number of others is a hole in the one enclosing
    it, and the rest are shells carrying their holes. This used to union the rings as *filled*
    polygons, which is what SVG's even-odd rule says they are not -- so a donut clipped to its
    viewBox came back a solid disc, and so did every window in a plate and every gap in a ring
    icon. `Region.even_odd` ran afterwards and found nothing left to cut (TASKS T15).

    Args:
        rings: The outlines, each a closed list of ``[x, y]`` points.

    Returns:
        The shapely geometry, or None if no ring had any area.

    """
    from shapely.geometry import Polygon as _Polygon
    from shapely.ops import unary_union as _unary_union

    from pybosl2.regions import inward_probe, nesting_depths

    shells = []
    for ring in rings:
        poly = _Polygon(ring)
        if not poly.is_valid:
            poly = poly.buffer(0)
        # buffer(0) can split a self-intersecting ring into several polygons; each nests in its
        # own right.
        for part in getattr(poly, "geoms", [poly]):
            if not part.is_empty and getattr(part, "exterior", None) is not None:
                shells.append(_Polygon(part.exterior.coords))
    if not shells:
        return None

    probes = [inward_probe(shell) for shell in shells]
    depths = nesting_depths(shells, probes)
    polys = []
    for i, shell in enumerate(shells):
        if depths[i] % 2:
            continue  # odd depth: a hole, cut from the shell that encloses it just below
        holes = [
            other.exterior.coords
            for j, other in enumerate(shells)
            if j != i and depths[j] == depths[i] + 1 and shell.contains(probes[j])
        ]
        piece = _Polygon(shell.exterior.coords, holes)
        if not piece.is_valid:
            piece = piece.buffer(0)
        if not piece.is_empty:
            polys.append(piece)
    if not polys:
        return None
    return _unary_union(polys)


def _shapely_to_rings(geom: Any) -> list[list[list[float]]]:
    """Rings for every polygon in a shapely geometry (exteriors AND holes)."""
    if geom is None or geom.is_empty:
        return []
    out: list[list[list[float]]] = []
    for part in getattr(geom, "geoms", [geom]):
        if not hasattr(part, "exterior"):
            continue
        if part.area <= 0:
            continue
        out.append([[float(x), float(y)] for x, y in list(part.exterior.coords)[:-1]])
        for interior in part.interiors:
            out.append([[float(x), float(y)] for x, y in list(interior.coords)[:-1]])
    return out


def _clip_rings(rings: "list[list[list[float]]]", mask: Any) -> Any:
    """Intersect a shape's rings with a clip geometry."""
    geom = _rings_to_shapely(rings)
    if geom is None:
        return None
    return geom.intersection(mask)


def _viewbox_geometry(file: str, sign: float) -> Any:
    """Return the viewBox rectangle as shapely, in the same Y direction as the rings."""
    from shapely.geometry import box as _box

    try:
        text = pathlib.Path(file).read_text(errors="replace")
    except OSError:
        return None
    match = re.search(r'viewBox\s*=\s*"\s*([-\d.eE]+)[ ,]+([-\d.eE]+)[ ,]+([-\d.eE]+)[ ,]+([-\d.eE]+)', text)
    if match is None:
        return None
    min_x, min_y, width, height = (float(v) for v in match.groups())
    if width <= 0 or height <= 0:
        return None
    y0, y1 = sign * min_y, sign * (min_y + height)
    return _box(min_x, min(y0, y1), min_x + width, max(y0, y1))


def _walk_shapes(
    node: object, svg_root: object, sign: float, fn: "int | None", fs: float, clip: Any = None
) -> "Iterator[tuple[object, Any]]":
    """Yield ``(shape, clip_geometry_or_None)`` for every Shape, honouring ``clip-path``.

    ``<clipPath>`` is not decoration: a drawing can rely on it for its actual outline.
    Japan's flag in flag-icons paints a 720-wide white rectangle and clips it to the 640-wide
    viewport, so without this the flag came out 12% too long. The clip is INHERITED, so it is
    carried down the tree here rather than read off each shape (svgelements does not copy a
    group's clip-path onto its children).
    """
    from svgelements import Shape

    values = getattr(node, "values", None) or {}
    reference = values.get("clip-path") or values.get("clip_path")
    if reference:
        clipper = _resolve_clip(reference, svg_root, sign, fn, fs, getattr(node, "transform", None))
        if clipper is not None:
            clip = clipper if clip is None else clip.intersection(clipper)

    if isinstance(node, Shape):
        yield node, clip
        return
    for child in node if hasattr(node, "__iter__") else ():
        yield from _walk_shapes(child, svg_root, sign, fn, fs, clip)


def _resolve_clip(
    reference: str, svg_root: object, sign: float, fn: "int | None", fs: float, matrix: Any = None
) -> Any:
    """Return the shapely geometry a ``clip-path="url(#id)"`` reference names, or ``None``.

    *matrix* is the referencing element's own transform, and it MUST be applied: a
    ``<clipPath>`` lives in ``<defs>`` and so is parsed in the document's coordinates, but it
    clips in the referencing element's space. Japan's flag hangs its clip rectangle off a
    group with ``translate(88 -32)``; without that shift the clip lands 88 units left of where
    it belongs and takes 20% of the flag with it.
    """
    from svgelements import Shape

    match = re.match(r"\s*url\(\s*#([^)\s]+)\s*\)", str(reference))
    if match is None:
        return None
    target = (getattr(svg_root, "objects", None) or {}).get(match.group(1))
    if target is None:
        return None
    # Flatten UNFLIPPED, transform in the SVG's own coordinates, then flip -- the matrix is
    # expressed in SVG space, so it cannot be applied to already-flipped points.
    rings: list[list[list[float]]] = []
    for node in target if hasattr(target, "__iter__") else [target]:
        if isinstance(node, Shape):
            rings.extend(_shape_rings(node, 1.0, fn, fs))
    if matrix is not None:
        a, b, c, d, e, f = (
            float(matrix.a),
            float(matrix.b),
            float(matrix.c),
            float(matrix.d),
            float(matrix.e),
            float(matrix.f),
        )
        rings = [[[a * x + c * y + e, b * x + d * y + f] for x, y in ring] for ring in rings]
    rings = [[[x, sign * y] for x, y in ring] for ring in rings]
    return _rings_to_shapely(rings)


def svg_element_groups(
    file: str,
    fn: int | None = DEFAULT_FN,
    fa: float | None = DEFAULT_FA,
    fs: float = DEFAULT_FS,
    flip_y: bool = True,
    color: str | None = None,
    strokes: str = "polygon",
    clip_to_viewbox: bool = True,
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
        clip_to_viewbox: When True (the default), clip shapes to the SVG's ``viewBox``
            if one is declared.

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
    svg_root = SVG.parse(file)
    # The VIEWPORT clips too: an SVG's viewBox is its visible extent and content outside it is
    # not drawn (CSS `overflow: hidden` on the root). Drawings rely on that -- Scotland's
    # saltire in flag-icons is one stroke run corner to corner, whose square ends stick out
    # past the flag on every side. Honour it unless the caller asks not to.
    viewport = _viewbox_geometry(file, sign) if clip_to_viewbox else None

    groups: list[tuple[str | None, list[Path2D]]] = []
    for element, clip in _walk_shapes(svg_root, svg_root, sign, fn, fs):
        if not isinstance(element, Shape):
            continue
        mask = clip if viewport is None else (viewport if clip is None else clip.intersection(viewport))
        fill_color: str | None = _shape_fill_hex(element)
        raw_rings = _shape_rings(element, sign, fn, fs)
        if mask is not None and raw_rings:
            raw_rings = _shapely_to_rings(_clip_rings(raw_rings, mask))
        fill_rings = [Path2D(r, closed=True) for r in raw_rings]
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
                    stroke_ring = _stroke_to_polygon(
                        stroke_ring_pts, stroke_width / 2, _stroke_linecap(element), _stroke_linejoin(element)
                    )
                    if stroke_ring is not None and len(stroke_ring) >= 3:
                        if mask is not None:
                            for clipped in _shapely_to_rings(_clip_rings([stroke_ring], mask)):
                                stroke_rings.append(Path2D(clipped, closed=True))
                        else:
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
    clip_to_viewbox: bool = True,
) -> tuple[list["Path2D"], list[str | None]]:
    """Every closed ring in an SVG, flattened, with the fill colour of each.

    The element each ring came from is NOT preserved -- use
    :func:`svg_element_groups` when that matters (it does for compositing: nesting means
    "hole" only WITHIN one element).
    """
    paths: list[Path2D] = []
    colors: list[str | None] = []
    for element_color, rings in svg_element_groups(
        file,
        fn=fn,
        fa=fa,
        fs=fs,
        flip_y=flip_y,
        color=color,
        strokes=strokes,
        clip_to_viewbox=clip_to_viewbox,
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


def _stroke_linecap(element: object) -> str:
    """Return the ``stroke-linecap`` value, defaulting to ``"butt"`` (SVG's own default)."""
    values = getattr(element, "values", None) or {}
    return str(values.get("stroke-linecap", getattr(element, "stroke_linecap", None) or "butt"))


def _stroke_linejoin(element: object) -> str:
    """Return the ``stroke-linejoin`` value, defaulting to ``"miter"`` (SVG's own default)."""
    values = getattr(element, "values", None) or {}
    return str(values.get("stroke-linejoin", getattr(element, "stroke_linejoin", None) or "miter"))


#: SVG stroke-linecap -> the shapely buffer cap style. SVG's default is "butt".
_CAP_STYLES = {"butt": "flat", "round": "round", "square": "square"}
#: SVG stroke-linejoin -> the shapely buffer join style. SVG's default is "miter".
_JOIN_STYLES = {"miter": "mitre", "miter-clip": "mitre", "arcs": "mitre", "round": "round", "bevel": "bevel"}


def _stroke_to_polygon(
    ring: list[list[float]],
    radius: float,
    linecap: str = "butt",
    linejoin: str = "miter",
) -> list[list[float]] | None:
    """Buffer a linestring by *radius* and return the resulting polygon ring.

    *linecap* and *linejoin* are the SVG properties, and they DEFAULT TO SVG'S DEFAULTS.
    This used to buffer with round caps unconditionally, which silently made every stroked
    shape half a stroke-width too big in each direction: a butt cap stops dead at the
    endpoint, a round one bulges past it. On a flag drawn as strokes that is visible --
    Scotland's saltire (stroke-width .6 under a scale(128 160), so a 48-unit radius) grew 4mm
    past its own 60mm flag, and the US flag's stripes 1.7mm past theirs.

    Returns ``None`` if the buffer produces no geometry or an empty polygon.
    """
    from shapely.geometry import LineString

    if len(ring) < 2 or radius <= 0:
        return None
    line = LineString([(float(p[0]), float(p[1])) for p in ring])
    buffered = line.buffer(
        radius,
        cap_style=_CAP_STYLES.get(str(linecap).strip().lower(), "flat"),
        join_style=_JOIN_STYLES.get(str(linejoin).strip().lower(), "mitre"),
    )
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
    clip_to_viewbox: bool = True,
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
        clip_to_viewbox: When True (the default), clip shapes to the SVG's ``viewBox``
            if one is declared.

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
    from pybosl2.regions import Region

    # Split the COMPOSITED drawing, rather than resolving each colour on its own. Pooling a
    # colour's rings and running even_odd over them ignores everything painted on top, so the
    # regions came back overlapping: Australia's blue was the whole 640x480 flag with the
    # white Union Jack sitting on top of it, and every extruded body overlapped every other.
    # region_from_svg already resolves paint order into disjoint pieces; this just groups the
    # result by colour, so the two functions can no longer disagree about a drawing.
    composited = region_from_svg(
        file,
        fn=fn,
        fa=fa,
        fs=fs,
        flip_y=flip_y,
        color=color,
        strokes=strokes,
        clip_to_viewbox=clip_to_viewbox,
    )
    parts = list(getattr(composited.geom, "geoms", [composited.geom]))
    colours = composited._polygon_colors or [composited._color] * len(parts)

    grouped: dict[str | None, list[tuple[object, object]]] = {}
    order: list[str | None] = []
    for part, part_colour in zip(parts, colours, strict=False):
        key = str(part_colour) if part_colour is not None else None
        if key not in grouped:
            order.append(key)
            grouped[key] = []
        grouped[key].append((part_colour, part))

    results: list[Region] = []
    for key in order:
        pieces = grouped[key]
        region = Region._from_colored_pieces(pieces)
        if pieces[0][0] is not None:
            region = region.color(pieces[0][0])  # type: ignore[arg-type]
        results.append(region)
    return results

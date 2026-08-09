# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# DocCategory: Paths, regions & surfaces

"""Object API for 2-D paths and regions.

Path2D and Region: object wrappers over the 2-D point maths in paths.py/rounding.py/
transforms.py, so a polygon can be built once and then chained
(`Path2D(pts).offset(radius=-2).round_corners(radius=1).polygon()`) instead of threading raw
point lists through free functions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from shapely.geometry import MultiPolygon, Polygon

from pybosl2.caps import CapSpec, CapType
from pybosl2.enums import RoundingMethod
from pybosl2.path2d import Path2D
from pybosl2.shapes3d import text3d

if TYPE_CHECKING:  # for the annotations only -- importing shapes2d here would be circular
    from collections.abc import Iterator, Sequence

    from pybosl2._backend import Solid
    from pybosl2.color import Color
    from pybosl2.shapes2d import Bosl2Shape2D
    from pybosl2.shapes3d import Bosl2Solid

__all__ = ["Region"]


def _flatten_shapely_to_paths(geom: MultiPolygon) -> list[Path2D]:
    """Extract all paths from a ``Polygon`` or ``MultiPolygon``.

    Every polygon (exterior and any holes) in the geometry is flattened into
    the result list.  For a ``MultiPolygon``, all component polygons are
    included.

    Returns:
        A flat list of :class:`Path2D` objects.

    """
    if geom.is_empty:
        return []
    polys: list[Polygon] = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    paths: list[Path2D] = []
    for poly in polys:
        if not isinstance(poly, Polygon):
            continue
        # A region's outlines are rings, so they come back closed whatever built them.
        paths.append(Path2D(np.asarray(poly.exterior.coords)[:-1], closed=True))
        for interior in poly.interiors:
            paths.append(Path2D(np.asarray(interior.coords)[:-1], closed=True))
    return paths


class Region:
    """A 2-D region backed by :mod:`shapely` (not OpenSCAD/PythonSCAD).

    Stores :class:`~shapely.geometry.MultiPolygon` internally and derives
    :class:`Path2D` outlines only when requested. All Boolean operations
    (union, intersection, difference, symmetric difference) use shapely
    directly. Operator overloads (``|``, ``&``, ``-``, ``^``) are provided.

    Create a region from a single outline (no holes)::

        Region([[0, 0], [80, 0], [80, 60], [0, 60]])

    Create a region with holes (outline first, then hole paths)::

        Region([
            [[0, 0], [80, 0], [80, 60], [0, 60]],           # outer outline
            [[20, 20], [60, 20], [60, 40], [20, 40]],       # hole 1
        ])

    Or use the shorthand :meth:`with_holes` for a more readable call.

    For native-geometry output (e.g. extrusion), call :meth:`geometry()`
    which converts paths to :class:`~pybosl2.shapes2d.Bosl2Shape2D`.

    Args:
        paths: The outlines; each is coerced to a :class:`Path2D`. A single
            flat point list is treated as one outline.  A
            ``shapely.Polygon`` or ``shapely.MultiPolygon`` is also
            accepted.

    Examples:
        A rectangular plate with a rectangular hole (outline + one hole), extruded into a solid:

            .. pythonscad-example::

                from pybosl2 import Region

                region = Region([
                    [[0, 0], [80, 0], [80, 60], [0, 60]],
                    [[20, 20], [60, 20], [60, 40], [20, 40]],
                ])
                region.geometry().linear_extrude(height=5).show()

    """

    def __init__(self, paths: Any = ()) -> None:
        """Create a region from path outlines or a shapely geometry.

        Args:
            paths: The outlines; each is coerced to a :class:`Path2D`. A
                single flat point list is treated as one outline.  A
                ``shapely.Polygon`` or ``shapely.MultiPolygon`` is also
                accepted.

        """
        self._color: "Color | None" = None
        self._polygon_colors: list["Color | None"] = []
        if isinstance(paths, (Polygon, MultiPolygon)):
            if paths.is_empty:
                self._polygon = MultiPolygon()
            elif isinstance(paths, MultiPolygon):
                self._polygon = paths
            else:
                self._polygon = MultiPolygon([paths])
            return

        items = list(paths)
        if items and not isinstance(items[0], (list, tuple, np.ndarray, Path2D)):
            raise TypeError(f"Region needs paths, got {type(items[0]).__name__}")
        if items and np.asarray(items[0], dtype=float).ndim == 1:
            items = [items]
        if not items:
            self._polygon = MultiPolygon()
            return
        paths_list = [p if isinstance(p, Path2D) else Path2D(p, closed=True) for p in items]
        outer = paths_list[0]._points
        holes = [h._points for h in paths_list[1:]]
        self._polygon = MultiPolygon([Polygon(outer, holes)])

    def color(self, c: "Color") -> "Region":
        """Return a copy of this region with the given :class:`Color`."""
        copy = self.copy()
        copy._color = c
        return copy

    def copy(self) -> "Region":
        """Return a shallow copy of this region."""
        c = Region.__new__(Region)
        c._polygon = self._polygon
        c._color = self._color
        c._polygon_colors = list(self._polygon_colors)
        return c

    def __len__(self) -> int:
        """Return the number of paths in the region."""
        return len(self.paths)

    def __getitem__(self, index: int | slice) -> Path2D | list[Path2D]:
        """Access a path by index or slice."""
        return self.paths[index]

    def __iter__(self) -> Iterator[Path2D]:
        """Iterate over the paths."""
        return iter(self.paths)

    @property
    def paths(self) -> list[Path2D]:
        """The list of :class:`Path2D` objects derived from the geometry.

        Extracted on-demand from the underlying shapely
        :class:`~shapely.geometry.Polygon` or :class:`~shapely.geometry.MultiPolygon`.

        Returns:
            A list of :class:`Path2D` objects.

        """
        return _flatten_shapely_to_paths(self._polygon)

    @property
    def geom(self) -> MultiPolygon:
        """The underlying shapely geometry."""
        return self._polygon

    def to_shapely(self) -> MultiPolygon:
        """Return the shapely geometry for this region.

        Equivalent to the :attr:`geom` property; provided for explicit usage.

        Returns:
            A ``shapely.Polygon`` or ``shapely.MultiPolygon``.

        """
        return self.geom

    @classmethod
    def from_svg(
        cls,
        file: str,
        fn: int | None = None,
        fa: float | None = None,
        fs: float = 2.0,
        flip_y: bool = True,
        color: str | None = None,
    ) -> "Region":
        """Load an SVG drawing as a Region of outlines (see :func:`pybosl2.svg.region_from_svg`).

        Real path data rather than the renderer's opaque imported handle, so the drawing can be
        measured, offset, rounded or tessellated like anything else -- and needs no renderer.

        Args:
            file: Path to the SVG.
            fn: Minimum fragment count per curved segment (``>= 3`` → absolute point count).
            fa: Minimum angle in degrees (accepted for API parity).
            fs: Minimum fragment size in SVG user units (default ``2.0``).
            flip_y: Negate Y so the drawing is not mirrored (SVG's Y axis points down).
            color: When set, overrides every shape's fill colour with this hex string.
                Pass ``None`` (the default) to use the SVG's own colours.

        Returns:
            A :class:`Region` of the drawing, nested by the even-odd rule.

        """
        from pybosl2.svg import region_from_svg

        return region_from_svg(file, fn=fn, fa=fa, fs=fs, flip_y=flip_y, color=color)

    @classmethod
    def even_odd(
        cls,
        paths: "Sequence[Path2D | Sequence[Sequence[float]]]",
        colors: "Sequence[Color | str | None] | None" = None,
    ) -> "Region":
        """Create a region from outlines nested by the EVEN-ODD rule (OpenSCAD ``polygon(paths=)``).

        The default constructor is outer-plus-holes: outline 0 bounds the region and every
        other outline is a hole in it. That is right for a ring, and wrong for a traced drawing
        with several disjoint solids -- those extra solids come out subtracted instead of
        added, which still produces geometry and so fails silently.

        Even-odd instead decides each outline by how many others CONTAIN it: enclosed by an
        even number (zero included) makes it solid, by an odd number makes it a hole. That is
        the rule SVG and OpenSCAD's multi-path ``polygon()`` use, so it is the one to use for
        imported or traced outlines.

        When *colors* is provided (one per path), the fill colour of each solid ring is
        preserved through the nesting resolution: same-colour solids are unioned together,
        while different-colour solids stay as separate polygons inside the Region so
        :meth:`geometry` and :meth:`linear_extrude` can render each in its own colour.

        Args:
            paths: The outlines, each a :class:`~pybosl2.path2d.Path2D` or point sequence.
            colors: Optional per-path fill colours (a :class:`Color`, ``#rrggbb`` string or ``None``).

        Returns:
            A :class:`Region` whose solid area is the even-odd interpretation of *paths*.
            When *colors* are provided (or the *paths* are :class:`~pybosl2.path2d.Path2D`
            objects carrying their own colour), the resulting polygons each preserve their
            colour inside :attr:`_polygon_colors` so :meth:`geometry` and
            :meth:`linear_extrude` render them in the correct colours.

        Examples:
            Two disjoint squares, each with a hole -- four outlines, two solids::

                Region.even_odd([outer_a, hole_a, outer_b, hole_b])

        """
        from shapely.geometry import Point as _Point
        from shapely.geometry import Polygon as _Polygon
        from shapely.ops import unary_union as _unary_union

        from pybosl2.color import Color as _Color

        rings = [p if isinstance(p, Path2D) else Path2D(p, closed=True) for p in paths]
        polys = [_Polygon(r._points) for r in rings if len(r) >= 3]
        if not polys:
            return cls()

        resolved_colors: list[_Color | None] = []
        if colors is not None:
            color_iter = iter(colors)
            for r in rings:
                if len(r) < 3:
                    continue
                try:
                    c = next(color_iter)
                    resolved_colors.append(_Color(c) if isinstance(c, str) else c)
                except StopIteration:
                    resolved_colors.append(None)
        else:
            for r in rings:
                if len(r) < 3:
                    continue
                resolved_colors.append(r._color if r._color is not None else None)

        probes = [_Point(poly.exterior.coords[0]) for poly in polys]
        depths = [
            sum(1 for j, other in enumerate(polys) if i != j and other.contains(probes[i])) for i in range(len(polys))
        ]

        color_groups: dict[_Color | None, list[_Polygon]] = {}
        for i, poly in enumerate(polys):
            if depths[i] % 2:
                continue
            holes = [
                o.exterior.coords
                for j, o in enumerate(polys)
                if j != i and depths[j] == depths[i] + 1 and poly.contains(probes[j])
            ]
            piece = _Polygon(poly.exterior.coords, holes)
            if not piece.is_valid:
                piece = piece.buffer(0)
            if not piece.is_empty:
                color_groups.setdefault(resolved_colors[i], []).append(piece)

        if not color_groups:
            return cls()

        all_polys: list[Polygon] = []
        polygon_colors: list[_Color | None] = []
        for color, pieces in color_groups.items():
            merged = _unary_union(pieces)
            if isinstance(merged, _Polygon):
                if not merged.is_empty:
                    all_polys.append(merged)
                    polygon_colors.append(color)
            else:
                for p in merged.geoms:
                    if not p.is_empty:
                        all_polys.append(p)
                        polygon_colors.append(color)

        if not all_polys:
            return cls()
        result_geom = MultiPolygon(all_polys) if len(all_polys) > 1 else all_polys[0]
        region = cls(result_geom)
        region._polygon_colors = polygon_colors
        region._color = next((c for c in polygon_colors if c is not None), None)
        return region

    @classmethod
    def with_holes(
        cls,
        outline: Path2D,
        *holes: Path2D,
    ) -> "Region":
        r"""Create a region from an outline plus hole outlines.

        Convenience constructor. Equivalent to ``Region([outline, \\*holes])``.
        See :meth:`__init__` for the full constructor.

        Args:
            outline: The outer outline :class:`Path2D`.
            holes: Zero or more hole outline :class:`Path2D` objects.

        Returns:
            A :class:`Region` with the outline as the first path and holes as subsequent paths.

        """
        return cls([outline, *holes])

    @property
    def outline(self) -> Path2D:
        """The outer path.

        Returns:
            The first :class:`Path2D` in the region, which is the outer outline.

        """
        return self.paths[0] if self.paths else Path2D([], closed=True)

    @property
    def holes(self) -> list[Path2D]:
        """The hole paths.

        Returns:
            All :class:`Path2D` objects after the first, which are the interior holes.

        """
        return self.paths[1:]

    def offset(
        self,
        radius: float | None = None,
        delta: float | None = None,
        chamfer: bool = False,
    ) -> "Region":
        """Offset every path in the region.

        Args:
            radius: The corner-rounding radius for the offset.
            delta: The absolute offset distance.
            chamfer: Whether to chamfer corners instead of rounding them.

        Returns:
            A new :class:`Region` with every path offset by the given parameters.

        """
        result = Region([p.offset(radius=radius, delta=delta, chamfer=chamfer) for p in self.paths])
        if self._color is not None:
            result._color = self._color
        return result

    def round_corners(
        self,
        radius: float | list[float] | None = None,
        method: RoundingMethod = RoundingMethod.CIRCLE,
        cut: float | None = None,
        joint: float | None = None,
        width: float | None = None,
        curvature: float | None = None,
        closed: bool | None = None,
    ) -> "Region":
        """Round the corners of every path in the region.

        Args:
            radius: The rounding radius. A single float applies to all corners;
                a list applies per-corner radii.
            method: The rounding method (``"circle"``, ``"smooth"``, etc.).
            cut: Cut depth for chamfers.
            joint: Joint distance for rounding.
            width: Width for rounding.
            curvature: Curvature value for rounding.
            closed: Override whether paths are treated as closed.

        Returns:
            A new :class:`Region` with rounded corners on every path.

        """
        result = Region(
            [
                p.round_corners(
                    radius=radius,  # type: ignore[arg-type]
                    method=method,
                    cut=cut,
                    joint=joint,
                    width=width,
                    curvature=curvature,
                    closed=closed,
                )
                for p in self.paths
            ]
        )
        if self._color is not None:
            result._color = self._color
        return result

    def translate(self, v: Sequence[float]) -> "Region":
        """Translate every path in the region by the given vector.

        Args:
            v: A 2-D or 3-D translation vector.

        Returns:
            A new :class:`Region` with every path translated.

        """
        return Region([p.translate(v) for p in self.paths])

    def bounds(self) -> np.ndarray:
        """Return the bounding box over every path in the region.

        Returns:
            A numpy array ``[[min_x, min_y], [max_x, max_y]]``.

        """
        assert self.paths, "empty Region has no bounds"
        all_pts = np.vstack([p.array for p in self.paths])
        return np.array([all_pts.min(axis=0), all_pts.max(axis=0)])

    def geometry(self) -> "Bosl2Shape2D":
        """2-D geometry: the outline with the holes subtracted.

        When :attr:`_polygon_colors` is populated (e.g. from an SVG import with coloured
        fills), each polygon is coloured individually before being unioned into the final shape.
        Otherwise the region's single :attr:`_color` is applied to the whole result.

        Returns:
            A :class:`~pybosl2.shapes2d.Bosl2Shape2D`, so the result chains straight into the 2-D
            operators and the extruders.

        """
        polys = list(self._polygon.geoms) if isinstance(self._polygon, MultiPolygon) else [self._polygon]
        shape = None
        for i, poly in enumerate(polys):
            if poly.is_empty:
                continue
            piece = Path2D(list(poly.exterior.coords)[:-1], closed=True).polygon()
            for interior in poly.interiors:
                piece = piece - Path2D(list(interior.coords)[:-1], closed=True).polygon()
            poly_color = (
                self._polygon_colors[i]
                if i < len(self._polygon_colors) and self._polygon_colors[i] is not None
                else self._color
            )
            if poly_color is not None and hasattr(piece, "color"):
                piece = piece.color(poly_color)
            shape = piece if shape is None else (shape | piece)
        if shape is None:  # an empty region still has to produce something chainable
            from pythonscad import polygon as _polygon

            from pybosl2.shapes2d import Bosl2Shape2D

            shape = Bosl2Shape2D(_polygon([[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]))
        return shape

    def fill(self) -> "Bosl2Shape2D":
        """Return this region as 2-D geometry with its holes filled in.

        Equivalent to just the outline (OpenSCAD ``fill()``).

        Returns:
            A :class:`~pybosl2.shapes2d.Bosl2Shape2D`.

        """
        result = self.geometry().fill()
        if self._color is not None and hasattr(result, "color"):
            result = result.color(self._color)
        return result

    def _split_colored(self) -> "list[Region]":
        """Return sub-Regions, one per polygon, each carrying its own colour.

        Used internally by :meth:`linear_extrude` and :meth:`rotate_extrude` so
        per-polygon colours from an SVG import survive the extrusion.
        """
        if not self._polygon_colors:
            return [self]
        polys = list(self._polygon.geoms) if isinstance(self._polygon, MultiPolygon) else [self._polygon]
        pieces: list[Region] = []
        for i, poly in enumerate(polys):
            if poly.is_empty:
                continue
            r = Region(poly)
            c = self._polygon_colors[i] if i < len(self._polygon_colors) else None
            if c is not None:
                r._color = c
            pieces.append(r)
        return pieces if pieces else [self]

    @classmethod
    def hull(cls, *others: Region | Path2D) -> "Region":
        """Return the 2-D convex hull of all the given regions and paths.

        Uses shapely :func:`~shapely.convex_hull` on the union of all input
        geometries. Accepts a flat list or multiple arguments::

            Region.convex_hull(rect, circle)
            Region.convex_hull([rect, circle])

        Args:
            others: The regions or closed paths to hull together.

        Returns:
            A :class:`Region` representing the convex hull.

        """
        from shapely.ops import unary_union

        from pybosl2.path2d import Path2D as _Path

        items: list[Region | Path2D] = (
            list(others[0]) if len(others) == 1 and isinstance(others[0], (list, tuple)) else list(others)
        )
        geoms: list[Polygon] = []
        for item in items:
            if isinstance(item, _Path):
                item = Region([item])
            if not isinstance(item, Region):
                raise TypeError(f"convex_hull() expects Region or Path2D, got {type(item).__name__}")
            geoms.extend(item.geom.geoms)
        if not geoms:
            return Region()
        result = unary_union(geoms).convex_hull
        r = Region(_flatten_shapely_to_paths(result))
        r._polygon = MultiPolygon([result]) if isinstance(result, Polygon) else result
        return r

    def linear_extrude(
        self,
        height: float,
        center: bool = False,
        twist: float = 0.0,
        scale: float = 1.0,
        slices: int | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Solid":
        """Extrude this region along +Z into a 3-D solid with holes included.

        The result depends on the active backend: a :class:`~pybosl2.shapes3d.Bosl2Solid` under
        the default CSG backend, or a :class:`~pybosl2._sdf.shapes3d.PyShape` under
        ``use_backend("sdf")``. See :meth:`pybosl2.paths.Path2D.linear_extrude` for per-backend
        options.

        The SDF backend's prism is the union of the outlines' fields, so it can only express a
        region of DISJOINT islands; a region with holes raises
        :class:`~pybosl2.exceptions.UnsupportedByBackendError` there.

        Args:
            height: The extrusion height along +Z.
            center: Extrude symmetrically along Z if True (default False).
            twist: Twist angle in degrees over the full height (default 0).
            scale: Scale factor for the top cross-section (default 1.0).
            slices: Number of intermediate layers for twist/scale (auto if None).
            fn: Smoothness override for the angular resolution.
            fa: Smoothness override for the minimum angle.
            fs: Smoothness override for the minimum segment length.

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid` (CSG) or
            :class:`~pybosl2._sdf.shapes3d.PyShape` (SDF).

        """
        from pybosl2._backend import current_backend, get_backend
        from pybosl2.exceptions import UnsupportedByBackendError

        if self._polygon_colors:
            from functools import reduce

            pieces = self._split_colored()
            extruded = [
                p.linear_extrude(
                    height,
                    center=center,
                    twist=twist,
                    scale=scale,
                    slices=slices,
                    fn=fn,
                    fa=fa,
                    fs=fs,
                )
                for p in pieces
            ]
            return reduce(lambda a, b: a | b, extruded)

        if current_backend() != "csg" and self.holes:
            raise UnsupportedByBackendError(
                "linear_extrude (region with holes)",
                current_backend(),
                hint="the sdf prism unions its outlines' fields, so it cannot cut holes. Extrude "
                "the outline and subtract the holes' own extrusions, or build it on the csg backend.",
            )
        from pybosl2._backend import given_arguments

        result = get_backend().linear_extrude(
            list(self.paths),
            height,
            given_arguments(
                {
                    "center": center,
                    "twist": twist,
                    "scale": scale,
                    "slices": slices,
                    "fn": fn,
                    "fa": fa,
                    "fs": fs,
                }
            ),
        )
        if self._color is not None and hasattr(result, "color"):
            result = result.color(self._color)
        return result

    def rotate_extrude(
        self,
        angle: float = 360.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Bosl2Solid":
        """Revolve this region about the Y axis into a 3-D solid.

        Args:
            angle: The rotation angle in degrees.
            fn: Number of polygon segments for curved geometry.
            fa: Minimum angle for polygon segments.
            fs: Minimum size for polygon segments.

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid` (csg backend only -- the SDF backend has no
            revolve).

        """
        result = self.geometry().rotate_extrude(angle, fn=fn, fa=fa, fs=fs)
        if self._color is not None and hasattr(result, "color"):
            result = result.color(self._color)
        return result

    def stroke(
        self,
        width: float = 1,
        closed: bool | None = None,  # noqa: ARG002
        endcap1: CapType | CapSpec = CapType.ROUND,
        endcap2: CapType | CapSpec = CapType.ROUND,
        joints: CapType | CapSpec = CapType.ROUND,
    ) -> Region:
        """Stroke every path in the region (closed) and return the union as a Region.

        Args:
            width: Stroke width.
            closed: Accepted for signature parity; a region's paths are always stroked closed.
            endcap1: Cap style for the start of each path.
            endcap2: Cap style for the end of each path.
            joints: Cap style where segments meet.

        Returns:
            A :class:`Region` of the stroked outlines.

        """
        from pybosl2._stroke2d import stroke_2d

        polygons = [
            stroke_2d(p, width=width, closed=True, endcap1=endcap1, endcap2=endcap2, joints=joints) for p in self.paths
        ]
        result = Region([]) if not polygons else Region(polygons)
        if self._color is not None:
            result._color = self._color
        return result

    def dashed_stroke(
        self,
        dashpat: Any = None,
        closed: bool | None = None,  # noqa: ARG002
        fit: bool = True,
        mindash: float = 0.5,
    ) -> Region:
        """Break every path in the region into dashed polygon outlines.

        Returns a :class:`Region` of all dash polygons.
        """
        from pybosl2._stroke2d import dashed_stroke_2d

        results: list[Region] = [
            dashed_stroke_2d(p, dashpat=dashpat, closed=True, fit=fit, mindash=mindash) for p in self.paths
        ]
        if not results:
            return Region([])
        combined = results[0]
        for r in results[1:]:
            combined = combined | r
        return combined

    def debug_region(self, size: float = 1, vertices: bool = True) -> Any:
        """Visualize this region with vertex labels for debugging.

        Produces the filled region as a thin flat solid with every path's vertices labelled in
        red -- path ``a`` gets labels ``a0, a1, ...``, path ``b`` ``b0, b1, ...`` (BOSL2
        ``debug_region()``). A single-path region defers to
        :meth:`~pybosl2.paths.Path2D.debug_polygon`.

        Args:
            size: Text size for vertex labels.
            vertices: If False, omit vertex labels and return only the filled region.

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid`.

        """
        import operator
        from functools import reduce

        from pybosl2.color import Color
        from pybosl2.path2d import Path2D as _Path

        paths = [p if isinstance(p, _Path) else _Path(p) for p in self.paths]
        if len(paths) <= 1:
            return (paths[0] if paths else _Path(self.paths)).debug_polygon(size=size, vertices=vertices)  # type: ignore[arg-type]
        solid = self.geometry().linear_extrude(height=0.01, center=True)
        if not vertices:
            return solid
        labels = [
            text3d(
                f"{chr(97 + j)}{i}",
                size=size,
                height=0.02,
                halign="center",
                valign="center",
            )
            .translate([float(x), float(y), 0.01])
            .color(Color("red"))
            for j, path in enumerate(paths)
            for i, (x, y) in enumerate(path)
        ]
        return reduce(operator.or_, [solid, *labels])

    # -----------------------------------------------------------------------------------
    # 2-D boolean set operations
    # -----------------------------------------------------------------------------------

    def intersection(self, other: Region | Path2D) -> "Region":
        """Return the 2-D intersection of this region with other (the area they share).

        Uses shapely for exact polygon coordinates.

        Args:
            other: the region to intersect with.

        Returns:
            A :class:`Region` with the intersection area.

        Examples:
            Two overlapping squares share a rectangular strip:

            .. pythonscad-example::

                from pybosl2 import Region

                a = Region([[0, 0], [40, 0], [40, 30], [0, 30]])
                b = Region([[20, 0], [60, 0], [60, 30], [20, 30]])
                a.intersection(b).geometry().linear_extrude(height=3).show()

        """
        if isinstance(other, Path2D):
            other = Region([other])
        result = self.geom.intersection(other.geom)
        if result.is_empty:
            return Region([])
        r = Region(_flatten_shapely_to_paths(result))
        r._polygon = result
        return r

    def union(self, other: Region | Path2D) -> "Region":
        """Return the 2-D union of this region and other (all area covered by either).

        Uses shapely for exact polygon coordinates.

        Args:
            other: the region to union with.

        Returns:
            A :class:`Region` with the combined area.

        Examples:
            Two adjacent squares merge into an L-shape:

            .. pythonscad-example::

                from pybosl2 import Region

                a = Region([[0, 0], [30, 0], [30, 30], [0, 30]])
                b = Region([[20, 0], [50, 0], [50, 30], [20, 30]])
                a.union(b).geometry().linear_extrude(height=3).show()

        """
        if isinstance(other, Path2D):
            other = Region([other])
        result = self.geom.union(other.geom)
        if result.is_empty:
            return Region([])
        r = Region(_flatten_shapely_to_paths(result))
        r._polygon = result
        return r

    def difference(self, other: Region | Path2D) -> "Region":
        """Return the 2-D difference: self with the area of other subtracted.

        Uses shapely for exact polygon coordinates.

        Args:
            other: the region to subtract.

        Returns:
            A :class:`Region` with the subtracted area.

        Examples:
            Punch a rectangular notch out of a square:

            .. pythonscad-example::

                from pybosl2 import Region

                plate = Region([[0, 0], [60, 0], [60, 40], [0, 40]])
                notch = Region([[20, 10], [40, 10], [40, 30], [20, 30]])
                plate.difference(notch).geometry().linear_extrude(height=4).show()

        """
        if isinstance(other, Path2D):
            other = Region([other])
        result = self.geom.difference(other.geom)
        if result.is_empty:
            return Region([])
        r = Region(_flatten_shapely_to_paths(result))
        r._polygon = result
        return r

    def symmetric_difference(self, other: Region | Path2D) -> "Region":
        """Return the 2-D symmetric difference (XOR): area in either region but not both.

        Uses shapely for exact polygon coordinates.

        Args:
            other: the region to xor with.

        Returns:
            A :class:`Region` with the symmetric difference area.

        """
        if isinstance(other, Path2D):
            other = Region([other])
        result = self.geom.symmetric_difference(other.geom)
        if result.is_empty:
            return Region([])
        r = Region(_flatten_shapely_to_paths(result))
        r._polygon = result
        return r

    # Operator overloads for convenience (mirror Bosl2Shape2D's &/|/- operators).
    def __and__(self, other: Region | Path2D) -> "Region":
        """Return ``self & other``, equivalent to ``self.intersection(other)``."""
        return self.intersection(other)

    def __or__(self, other: Region | Path2D) -> "Region":
        """Return ``self | other``, equivalent to ``self.union(other)``."""
        return self.union(other)

    def __sub__(self, other: Region | Path2D) -> "Region":
        """Return ``self - other``, equivalent to ``self.difference(other)``."""
        return self.difference(other)

    def __xor__(self, other: Region | Path2D) -> "Region":
        """Return ``self ^ other``, equivalent to ``self.symmetric_difference(other)``."""
        return self.symmetric_difference(other)

    def __repr__(self) -> str:
        """Return a string representation of the region."""
        return f"Region({len(self.paths)} paths: {[len(p) for p in self.paths]})"

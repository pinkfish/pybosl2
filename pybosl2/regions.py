# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Object API for 2-D paths and regions.

Path and Region: object wrappers over the 2-D point maths in paths.py/rounding.py/
transforms.py, so a polygon can be built once and then chained
(`Path(pts).offset(radius=-2).round_corners(radius=1).polygon()`) instead of threading raw
point lists through free functions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from shapely.geometry import MultiPolygon, Polygon

from pybosl2.paths import (
    Path,
    Path3D,
)  # Path/Path3D live in paths.py; re-exported here for compatibility
from pybosl2.shapes3d import text3d

if TYPE_CHECKING:  # for the annotations only -- importing shapes2d here would be circular
    from collections.abc import Iterator, Sequence

    from pybosl2._backend import Solid
    from pybosl2.shapes2d import Bosl2Shape2D, Shape2DLike
    from pybosl2.shapes3d import Bosl2Solid

__all__ = ["Path", "Path3D", "Region"]


def _to_shapely(path: Path) -> Polygon:
    """Convert a :class:`Path` (CCW ring) to a ``shapely.Polygon``.

    Returns:
        A ``shapely.Polygon`` constructed from the path vertices.
    """
    pts = [(float(p[0]), float(p[1])) for p in path]
    return Polygon(pts)


def _from_shapely(geom: Polygon | MultiPolygon) -> list[Path]:
    """Extract paths (exterior + holes) from a shapely geometry.

    Handles ``Polygon`` and ``MultiPolygon`` by taking the largest polygon.

    Returns:
        A list of :class:`Path` objects: outer ring first, then any holes.
    """
    if geom.is_empty:
        return []
    if isinstance(geom, MultiPolygon):
        geom = max(geom.geoms, key=lambda g: g.area)
    if not isinstance(geom, Polygon):
        return []
    paths: list[Path] = []
    exterior = list(geom.exterior.coords)[:-1]  # drop the closing repeat
    paths.append(Path([[float(x), float(y)] for x, y in exterior]))
    for interior in geom.interiors:
        ring = list(interior.coords)[:-1]
        paths.append(Path([[float(x), float(y)] for x, y in ring]))
    return paths


def _flatten_shapely_to_paths(geom: Polygon | MultiPolygon) -> list[Path]:
    """Extract all paths from a ``Polygon`` or ``MultiPolygon``.

    Every polygon (exterior and any holes) in the geometry is flattened into
    the result list.  For a ``MultiPolygon``, all component polygons are
    included.

    Returns:
        A flat list of :class:`Path` objects.
    """
    if geom.is_empty:
        return []
    polys: list[Polygon] = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    paths: list[Path] = []
    for poly in polys:
        if not isinstance(poly, Polygon):
            continue
        exterior = list(poly.exterior.coords)[:-1]
        paths.append(Path([[float(x), float(y)] for x, y in exterior]))
        for interior in poly.interiors:
            ring = list(interior.coords)[:-1]
            paths.append(Path([[float(x), float(y)] for x, y in ring]))
    return paths


class Region:
    """A 2-D region: a list of :class:`Path` outlines, holes included.

    BOSL2 represents a shape-with-holes as a list of paths (outline first, then
    the holes).  ``Region`` stores these internally and provides delegation
    methods (``__len__``, ``__getitem__``, ``__iter__``) for backward
    compatibility with code that previously relied on ``Region`` being a
    ``list`` subclass.

    Args:
        paths: The outlines; each is coerced to a :class:`Path`. A single flat
            point list is accepted and treated as one outline.  A
            ``shapely.Polygon`` or ``shapely.MultiPolygon`` is also accepted.

    Examples:
        A rectangular plate with a rectangular hole (outline + one hole), extruded into a solid:

        .. pythonscad-example::

            region = Region.with_holes(
                [[0, 0], [80, 0], [80, 60], [0, 60]],
                [[20, 20], [60, 20], [60, 40], [20, 40]],
            )
            region.geometry().linear_extrude(height=5).show()
    """

    def __init__(self, paths: Any = ()) -> None:
        """Creates a region from a sequence of path outlines or a shapely geometry.

        Args:
            paths: The outlines; each is coerced to a :class:`Path`. A single
                flat point list is treated as one outline.  A
                ``shapely.Polygon`` or ``shapely.MultiPolygon`` is also
                accepted.
        """
        if isinstance(paths, (Polygon, MultiPolygon)):
            self._paths: list[Path] = _flatten_shapely_to_paths(paths)
            self._geom: Polygon | MultiPolygon | None = paths if not paths.is_empty else None
            return

        items = list(paths)
        if items and not isinstance(items[0], (list, tuple, np.ndarray, Path)):
            raise TypeError(f"Region needs paths, got {type(items[0]).__name__}")
        # a bare point list ([[x, y], ...]) is one outline, not a list of paths
        if items and np.asarray(items[0], dtype=float).ndim == 1:
            items = [items]
        self._paths = [p if isinstance(p, Path) else Path(p) for p in items]
        self._geom = None

    def __len__(self) -> int:
        """Number of paths in the region."""
        return len(self._paths)

    def __getitem__(self, index: int | slice) -> Path | list[Path]:
        """Access a path by index or slice."""
        return self._paths[index]

    def __iter__(self) -> Iterator[Path]:
        """Iterate over the paths."""
        return iter(self._paths)

    @property
    def paths(self) -> list[Path]:
        """The internal list of :class:`Path` objects.

        Returns:
            The list of paths stored in the region.
        """
        return self._paths

    @property
    def geom(self) -> Polygon | MultiPolygon:
        """The cached shapely geometry for this region.

        Built lazily from the stored paths on first access.  The first path
        is used as the exterior and all remaining paths as holes.

        Returns:
            A ``shapely.Polygon`` or ``shapely.MultiPolygon``.
        """
        if self._geom is None:
            if not self._paths:
                self._geom = Polygon()
            else:
                outer = [(float(p[0]), float(p[1])) for p in self._paths[0]]
                holes = [[(float(p[0]), float(p[1])) for p in h] for h in self._paths[1:]]
                self._geom = Polygon(outer, holes)
        return self._geom

    def to_shapely(self) -> Polygon | MultiPolygon:
        """Return the shapely geometry for this region.

        Equivalent to the :attr:`geom` property; provided for explicit usage.

        Returns:
            A ``shapely.Polygon`` or ``shapely.MultiPolygon``.
        """
        return self.geom

    @classmethod
    def with_holes(cls, outline: Sequence[float], *holes: Sequence[float]) -> "Region":
        """A region from an outline plus hole outlines.

        This is what a concentric ``DifferenceWithOffset`` produces: outline + inner hole, no
        clipping involved.

        Args:
            outline: The outer outline path.
            holes: Zero or more hole outlines inside the outer outline.

        Returns:
            A :class:`Region` with the outline as the first path and holes as subsequent paths.
        """
        return cls([outline, *holes])

    @property
    def outline(self) -> Path:
        """The outer path.

        Returns:
            The first :class:`Path` in the region, which is the outer outline.
        """
        assert self._paths, "empty Region has no outline"
        return self._paths[0]

    @property
    def holes(self) -> list[Path]:
        """The hole paths.

        Returns:
            All :class:`Path` objects after the first, which are the interior holes.
        """
        return list(self._paths[1:])

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
        return Region([p.offset(radius=radius, delta=delta, chamfer=chamfer) for p in self._paths])

    def round_corners(self, radius: float | list[float] | None = None, **kwargs: Any) -> "Region":
        """Round the corners of every path in the region.

        Args:
            radius: The rounding radius. A single float applies to all corners; a list
                applies per-corner radii.
            kwargs: Additional arguments forwarded to :meth:`Path.round_corners`.

        Returns:
            A new :class:`Region` with rounded corners on every path.
        """
        return Region([p.round_corners(radius=radius, **kwargs) for p in self._paths])  # type: ignore[arg-type]

    def translate(self, v: Sequence[float]) -> "Region":
        """Translate every path in the region by the given vector.

        Args:
            v: A 2-D or 3-D translation vector.

        Returns:
            A new :class:`Region` with every path translated.
        """
        return Region([p.translate(v) for p in self._paths])

    def bounds(self) -> np.ndarray:
        """The bounding box over every path in the region.

        Returns:
            A numpy array ``[[min_x, min_y], [max_x, max_y]]``.
        """
        assert self._paths, "empty Region has no bounds"
        all_pts = np.vstack([p.array for p in self._paths])
        return np.array([all_pts.min(axis=0), all_pts.max(axis=0)])

    def geometry(self) -> "Bosl2Shape2D":
        """2-D geometry: the outline with the holes subtracted.

        Returns:
            A :class:`~pybosl2.shapes2d.Bosl2Shape2D`, so the result chains straight into the 2-D
            operators and the extruders.
        """
        shape = self.outline.polygon()
        for hole in self.holes:
            shape = shape - hole.polygon()
        return shape

    def fill(self) -> "Bosl2Shape2D":
        """Return this region as 2-D geometry with its holes filled in.

        Equivalent to just the outline (OpenSCAD ``fill()``).

        Returns:
            A :class:`~pybosl2.shapes2d.Bosl2Shape2D`.
        """
        return self.geometry().fill()

    def hull(self, *others: "Shape2DLike") -> "Bosl2Shape2D":
        """The 2-D convex hull of this region.

        Optionally includes *others* (more regions, paths, 2-D shapes or point lists),
        equivalent to OpenSCAD ``hull()``.

        Returns:
            A :class:`~pybosl2.shapes2d.Bosl2Shape2D`.
        """
        return self.geometry().hull(*others)

    def linear_extrude(self, height: float, **kwargs: Any) -> "Solid":
        """Extrude this region along +Z into a 3-D solid with holes included.

        The result depends on the active backend: a :class:`~pybosl2.shapes3d.Bosl2Solid` under
        the default CSG backend, or a :class:`~pybosl2._sdf.shapes3d.PyShape` under
        ``use_backend("sdf")``. See :meth:`pybosl2.paths.Path.linear_extrude` for per-backend
        options.

        The SDF backend's prism is the union of the outlines' fields, so it can only express a
        region of DISJOINT islands; a region with holes raises
        :class:`~pybosl2.exceptions.UnsupportedByBackendError` there.

        Args:
            height: The extrusion height along +Z.
            kwargs: Additional arguments forwarded to the backend's linear_extrude
                implementation.

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid` (CSG) or
            :class:`~pybosl2._sdf.shapes3d.PyShape` (SDF).
        """
        from pybosl2._backend import current_backend, get_backend
        from pybosl2.exceptions import UnsupportedByBackendError

        if current_backend() != "csg" and self.holes:
            raise UnsupportedByBackendError(
                "linear_extrude (region with holes)",
                current_backend(),
                hint="the sdf prism unions its outlines' fields, so it cannot cut holes. Extrude "
                "the outline and subtract the holes' own extrusions, or build it on the csg backend.",
            )
        return get_backend().linear_extrude(list(self._paths), height, **kwargs)

    def rotate_extrude(self, angle: float = 360.0, **kwargs: Any) -> "Bosl2Solid":
        """Revolve this region about the Y axis into a 3-D solid.

        See :meth:`~pybosl2.shapes2d.Bosl2Shape2D.rotate_extrude` for details.

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid` (csg backend only -- the SDF backend has no
            revolve).
        """
        return self.geometry().rotate_extrude(angle, **kwargs)

    def debug_region(self, size: float = 1, vertices: bool = True) -> Any:
        """Visualize this region with vertex labels for debugging.

        Produces the filled region as a thin flat solid with every path's vertices labelled in
        red -- path ``a`` gets labels ``a0, a1, ...``, path ``b`` ``b0, b1, ...`` (BOSL2
        ``debug_region()``). A single-path region defers to
        :meth:`~pybosl2.paths.Path.debug_polygon`.

        Args:
            size: Text size for vertex labels.
            vertices: If False, omit vertex labels and return only the filled region.

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid`.
        """
        import operator
        from functools import reduce

        from pybosl2.paths import Path as _Path

        paths = [p if isinstance(p, _Path) else _Path(p) for p in self._paths]
        if len(paths) <= 1:
            return (paths[0] if paths else _Path(self._paths)).debug_polygon(size=size, vertices=vertices)  # type: ignore[arg-type]
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
            .color("red")
            for j, path in enumerate(paths)
            for i, (x, y) in enumerate(path)
        ]
        return reduce(operator.or_, [solid, *labels])

    def stroke(self, width: float = 1, **kwargs: Any) -> Any:
        """Draw every path in this region as a closed solid line.

        Args:
            width: The stroke width.
            kwargs: Additional arguments forwarded to :func:`pybosl2.drawing.stroke`.

        Returns:
            A 2-D or 3-D object depending on the backend.
        """
        from pybosl2.drawing import stroke as _stroke

        return _stroke(self, width=width, **kwargs)

    def dashed_stroke(self, dashpat: Sequence[float] = (3, 3), **kwargs: Any) -> "list[Path | Path3D]":
        """Break every path in this region into dash sub-paths.

        Args:
            dashpat: The dash pattern as alternating lengths ``[dash, gap, ...]``.
            kwargs: Additional arguments forwarded to :func:`pybosl2.drawing.dashed_stroke`.

        Returns:
            A list of :class:`Path` or :class:`Path3D` dash segments.
        """
        from pybosl2.drawing import dashed_stroke as _dashed

        return _dashed(self, dashpat=dashpat, **kwargs)

    # -----------------------------------------------------------------------------------
    # 2-D boolean set operations
    # -----------------------------------------------------------------------------------

    def intersection(self, other: "Region") -> "Region":
        """The 2-D intersection of this region with *other* (the area they share).

        Uses shapely for exact polygon coordinates.

        Args:
            other: the region to intersect with.

        Returns:
            A :class:`Region` with the intersection area.

        Examples:
            Two overlapping squares share a rectangular strip:

            .. pythonscad-example::

                a = Region([[0, 0], [40, 0], [40, 30], [0, 30]])
                b = Region([[20, 0], [60, 0], [60, 30], [20, 30]])
                a.intersection(b).geometry().linear_extrude(height=3).show()
        """
        result = self.geom.intersection(other.geom)
        if result.is_empty:
            return Region([])
        r = Region(_flatten_shapely_to_paths(result))
        r._geom = result
        return r

    def union(self, other: "Region") -> "Region":
        """The 2-D union of this region and *other* (all area covered by either).

        Uses shapely for exact polygon coordinates.

        Args:
            other: the region to union with.

        Returns:
            A :class:`Region` with the combined area.

        Examples:
            Two adjacent squares merge into an L-shape:

            .. pythonscad-example::

                a = Region([[0, 0], [30, 0], [30, 30], [0, 30]])
                b = Region([[20, 0], [50, 0], [50, 30], [20, 30]])
                a.union(b).geometry().linear_extrude(height=3).show()
        """
        result = self.geom.union(other.geom)
        if result.is_empty:
            return Region([])
        r = Region(_flatten_shapely_to_paths(result))
        r._geom = result
        return r

    def difference(self, other: "Region") -> "Region":
        """The 2-D difference: *self* with the area of *other* subtracted.

        Uses shapely for exact polygon coordinates.

        Args:
            other: the region to subtract.

        Returns:
            A :class:`Region` with the subtracted area.

        Examples:
            Punch a rectangular notch out of a square:

            .. pythonscad-example::

                plate = Region([[0, 0], [60, 0], [60, 40], [0, 40]])
                notch = Region([[20, 10], [40, 10], [40, 30], [20, 30]])
                plate.difference(notch).geometry().linear_extrude(height=4).show()
        """
        result = self.geom.difference(other.geom)
        if result.is_empty:
            return Region([])
        r = Region(_flatten_shapely_to_paths(result))
        r._geom = result
        return r

    def symmetric_difference(self, other: "Region") -> "Region":
        """The 2-D symmetric difference (XOR): area in either region but not both.

        Uses shapely for exact polygon coordinates.

        Args:
            other: the region to xor with.

        Returns:
            A :class:`Region` with the symmetric difference area.
        """
        result = self.geom.symmetric_difference(other.geom)
        if result.is_empty:
            return Region([])
        r = Region(_flatten_shapely_to_paths(result))
        r._geom = result
        return r

    # Operator overloads for convenience (mirror Bosl2Shape2D's &/|/- operators).
    def __and__(self, other: "Region") -> "Region":
        """``a & b``  →  ``a.intersection(b)``."""
        return self.intersection(other)

    def __or__(self, other: "Region") -> "Region":
        """``a | b``  →  ``a.union(b)``."""
        return self.union(other)

    def __sub__(self, other: "Region") -> "Region":
        """``a - b``  →  ``a.difference(b)``."""
        return self.difference(other)

    def __xor__(self, other: "Region") -> "Region":
        """``a ^ b``  →  ``a.symmetric_difference(b)``."""
        return self.symmetric_difference(other)

    def __repr__(self) -> str:
        return f"Region({len(self._paths)} paths: {[len(p) for p in self._paths]})"

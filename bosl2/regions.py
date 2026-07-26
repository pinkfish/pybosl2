# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/regions.py
#    Path and Region: object wrappers over the 2-D point maths in paths.py/rounding.py/
#    transforms.py, so a polygon can be built once and then chained
#    (`Path(pts).offset(radius=-2).round_corners(radius=1).polygon()`) instead of threading raw
#    point lists through free functions.
#
# FileSummary: Object API for 2-D paths and regions.
# FileGroup: Bosl2

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np

from bosl2.paths import (
    Path,
    Path3D,
)  # Path/Path3D live in paths.py; re-exported here for compatibility
from bosl2.shapes3d import text3d

if TYPE_CHECKING:  # for the annotations only -- importing shapes2d here would be circular
    from bosl2._backend import Solid  # noqa: F401
    from bosl2.shapes2d import Bosl2Shape2D, Shape2DLike  # noqa: F401
    from bosl2.shapes3d import Bosl2Solid  # noqa: F401

__all__ = ["Path", "Path3D", "Region"]


class Region(list):
    """A 2-D region: a list of :class:`Path` outlines, holes included.

    BOSL2 represents a shape-with-holes as a list of paths (outline first, then the holes), and
    that is what this is -- so, like :class:`Path`, it subclasses ``list`` and stays a drop-in
    for the raw region data the toolkit already passes to ``region()``/``union()``.

    Args:
        paths: the outlines; each is coerced to a :class:`Path`. A single flat point list is
               accepted and treated as one outline.

    Examples:
        A rectangular plate with a rectangular hole (outline + one hole), extruded into a solid:

        .. pythonscad-example::

            region = Region.with_holes(
                [[0, 0], [80, 0], [80, 60], [0, 60]],
                [[20, 20], [60, 20], [60, 40], [20, 40]],
            )
            region.geometry().linear_extrude(height=5).show()
    """

    def __init__(self, paths: Sequence = ()) -> None:
        items = list(paths)
        if items and not isinstance(items[0], (list, tuple, np.ndarray)):
            raise TypeError(f"Region needs paths, got {type(items[0]).__name__}")
        # a bare point list ([[x, y], ...]) is one outline, not a list of paths
        if items and np.asarray(items[0], dtype=float).ndim == 1:
            items = [items]
        super().__init__([p if isinstance(p, Path) else Path(p) for p in items])

    @classmethod
    def with_holes(cls, outline: Sequence, *holes: Sequence) -> "Region":
        """A region from an outline plus hole outlines.

        This is what a concentric ``DifferenceWithOffset`` produces: outline + inner hole, no
        clipping involved.
        """
        return cls([outline, *holes])

    @property
    def outline(self) -> Path:
        """The outer path."""
        assert len(self), "empty Region has no outline"
        return self[0]

    @property
    def holes(self) -> list[Path]:
        return list(self[1:])

    def offset(
        self,
        radius: float | None = None,
        delta: float | None = None,
        chamfer: bool = False,
    ) -> "Region":
        """Offset every path in the region."""
        return Region([p.offset(radius=radius, delta=delta, chamfer=chamfer) for p in self])

    def round_corners(self, radius: float | list[float] | None = None, **kwargs: Any) -> "Region":
        return Region([p.round_corners(radius=radius, **kwargs) for p in self])

    def translate(self, v: Sequence[float]) -> "Region":
        return Region([p.translate(v) for p in self])

    def bounds(self) -> np.ndarray:
        """[[min_x, min_y], [max_x, max_y]] over every path."""
        assert len(self), "empty Region has no bounds"
        all_pts = np.vstack([p.array for p in self])
        return np.array([all_pts.min(axis=0), all_pts.max(axis=0)])

    def geometry(self) -> "Bosl2Shape2D":
        """2-D geometry: the outline with the holes subtracted.

        Returns:
            A :class:`~bosl2.shapes2d.Bosl2Shape2D`, so the result chains straight into the 2-D
            operators and the extruders.
        """
        shape = self.outline.polygon()
        for hole in self.holes:
            shape = shape - hole.polygon()
        return shape

    def fill(self) -> "Bosl2Shape2D":
        """This region as 2-D geometry with its holes filled in -- i.e. just the outline
        (OpenSCAD ``fill()``).

        Returns:
            A :class:`~bosl2.shapes2d.Bosl2Shape2D`.
        """
        return self.geometry().fill()

    def hull(self, *others: "Shape2DLike") -> "Bosl2Shape2D":
        """The 2-D convex hull of this region, optionally together with *others* (more regions,
        paths, 2-D shapes or point lists) -- OpenSCAD ``hull()``.

        Returns:
            A :class:`~bosl2.shapes2d.Bosl2Shape2D`.
        """
        return self.geometry().hull(*others)

    def linear_extrude(self, height: float, **kwargs: Any) -> "Solid":
        """Extrude this region *height* along +Z into a 3-D solid (holes included), **on whichever
        backend is active** -- a :class:`~bosl2.shapes3d.Bosl2Solid` under the default CSG backend,
        a :class:`~bosl2._sdf.shapes3d.PyShape` under ``use_backend("sdf")``. See
        :meth:`bosl2.paths.Path.linear_extrude` for the per-backend options.

        The SDF backend's prism is the union of the outlines' fields, so it can only express a
        region of DISJOINT islands; a region with holes raises
        :class:`~bosl2.exceptions.UnsupportedByBackend` there.
        """
        from bosl2._backend import current_backend, get_backend
        from bosl2.exceptions import UnsupportedByBackend

        if current_backend() != "csg" and self.holes:
            raise UnsupportedByBackend(
                "linear_extrude (region with holes)",
                current_backend(),
                hint="the sdf prism unions its outlines' fields, so it cannot cut holes. Extrude "
                "the outline and subtract the holes' own extrusions, or build it on the csg backend.",
            )
        return get_backend().linear_extrude(list(self), height, **kwargs)

    def rotate_extrude(self, angle: float = 360.0, **kwargs: Any) -> "Bosl2Solid":
        """Revolve this region about the Y axis into a 3-D solid; see
        :meth:`~bosl2.shapes2d.Bosl2Shape2D.rotate_extrude`.

        Returns:
            A :class:`~bosl2.shapes3d.Bosl2Solid` (csg backend only -- the SDF backend has no
            revolve).
        """
        return self.geometry().rotate_extrude(angle, **kwargs)

    def debug_region(self, size: float = 1, vertices: bool = True):
        """A debug view of this region: the filled region (as a thin flat solid) with every path's
        vertices labelled in red -- path ``a`` gets labels ``a0, a1, ...``, path ``b`` ``b0, b1, ...``
        (BOSL2 debug_region()). A single-path region defers to :meth:`~bosl2.paths.Path.debug_polygon`.

        Returns:
            A :class:`~bosl2.shapes3d.Bosl2Solid`.
        """
        import operator
        from functools import reduce

        from bosl2.paths import Path

        paths = [p if isinstance(p, Path) else Path(p) for p in self]
        if len(paths) <= 1:
            return (paths[0] if paths else Path(self)).debug_polygon(size=size, vertices=vertices)
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

    def stroke(self, width: float = 1, **kwargs: Any):
        """
        Draw every path in this region as a closed solid line (see
        :func:`bosl2.drawing.stroke`).
        """
        from bosl2.drawing import stroke as _stroke

        return _stroke(self, width=width, **kwargs)

    def dashed_stroke(self, dashpat: Sequence[float] = (3, 3), **kwargs: Any) -> "list[Path | Path3D]":  # type: ignore[override]
        """
        Break every path in this region into dash sub-paths (see
        :func:`bosl2.drawing.dashed_stroke`).
        """
        from bosl2.drawing import dashed_stroke as _dashed

        return _dashed(self, dashpat=dashpat, **kwargs)  # type: ignore[return-value]

    def __repr__(self) -> str:
        return f"Region({len(self)} paths: {[len(p) for p in self]})"

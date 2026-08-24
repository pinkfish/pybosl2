# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/shapes2d/base.py
# FileSummary: Base 2D shape wrapper class and anchoring/mathematical helper functions.
# DocCategory: internal
# FileGroup: BOSL2

"""Base 2D shape wrapper class and anchoring/mathematical helper functions."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Union

import numpy as np

from pybosl2._backend import backend_only
from pybosl2._edges_lang import Anchor, resolve_anchor
from pybosl2._helpers import (
    anchor_offset_box as _anchor_offset_box,
)
from pybosl2._helpers import (
    arc_points as _arc_points,
)
from pybosl2._helpers import (
    as_native_2d as _as_native_2d,
)
from pybosl2._helpers import (
    frag_count as _frag_count,
)
from pybosl2._native import native
from pybosl2._shape import BaseShape as BaseShape
from pybosl2.bounds import Bounds2D
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.points import Point
from pybosl2.vectors import unit

if TYPE_CHECKING:
    from openscad import PyOpenSCAD

    from pybosl2.path2d import Path2D
    from pybosl2.paths import PathLike
    from pybosl2.shapes3d.base import CsgSolid as Bosl2Solid

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


def _arc_between_points(
    center: Sequence[float],
    point_start: Sequence[float],
    point_end: Sequence[float],
    radius: float,
    endpoint: bool = True,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> list[list[float]]:
    """Arc around *center* from *point_start* to *point_end*, sweeping the shorter way around."""
    a0 = math.degrees(math.atan2(point_start[1] - center[1], point_start[0] - center[0]))
    a1 = math.degrees(math.atan2(point_end[1] - center[1], point_end[0] - center[0]))
    delta = (a1 - a0 + 180) % 360 - 180
    count = max(3, math.ceil(_frag_count(radius, fn, fa, fs) * abs(delta) / 360))
    return _arc_points(count, radius, a0, delta, center, endpoint=endpoint)


def _arc_through_3(
    center: Sequence[float],
    radius: float,
    point_start: Sequence[float],
    point_mid: Sequence[float],
    point_end: Sequence[float],
    endpoint: bool = True,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> list[list[float]]:
    """Arc around *center* from *point_start* to *point_end*, sweeping through.

    *point_mid* (may be the long way around).
    """
    a0 = math.degrees(math.atan2(point_start[1] - center[1], point_start[0] - center[0]))
    am = math.degrees(math.atan2(point_mid[1] - center[1], point_mid[0] - center[0]))
    a1 = math.degrees(math.atan2(point_end[1] - center[1], point_end[0] - center[0]))
    d_mid = (am - a0) % 360
    d_end = (a1 - a0) % 360
    delta = d_end if d_mid <= d_end else d_end - 360
    count = max(3, math.ceil(_frag_count(radius, fn, fa, fs) * abs(delta) / 360))
    return _arc_points(count, radius, a0, delta, center, endpoint=endpoint)


def _circle_from_corner(corner: Sequence[Sequence[float]], radius: float) -> list[float]:
    p0, p1, p2 = corner
    v1 = unit([p0[0] - p1[0], p0[1] - p1[1]])
    v2 = unit([p2[0] - p1[0], p2[1] - p1[1]])
    bis = unit([v1[0] + v2[0], v1[1] + v2[1]])
    half_ang = math.acos(max(-1.0, min(1.0, v1[0] * bis[0] + v1[1] * bis[1])))
    dist = radius / math.sin(half_ang)
    return [p1[0] + bis[0] * dist, p1[1] + bis[1] * dist]


def _circle_circle_intersection(
    radius1: float, center1: Sequence[float], radius2: float, center2: Sequence[float]
) -> list[list[float]]:
    d = math.dist(center1, center2)
    if d == 0 or d > radius1 + radius2 or d < abs(radius1 - radius2):
        return []
    a = (radius1**2 - radius2**2 + d**2) / (2 * d)
    h_sq = radius1**2 - a**2
    if h_sq < 0:
        return []
    h = math.sqrt(h_sq)
    xm = center1[0] + a * (center2[0] - center1[0]) / d
    ym = center1[1] + a * (center2[1] - center1[1]) / d
    dx = h * (center2[1] - center1[1]) / d
    dy = h * (center2[0] - center1[0]) / d
    return [[xm + dx, ym - dy], [xm - dx, ym + dy]]


def _adjacent_angle_to_hypotenuse(adjacent: float, angle: float) -> float:
    return adjacent / math.cos(math.radians(angle))


def _adjacent_angle_to_opposite(adjacent: float, angle: float) -> float:
    return adjacent * math.tan(math.radians(angle))


def _opposite_angle_to_adjacent(opposite: float, angle: float) -> float:
    return opposite / math.tan(math.radians(angle))


def _det2(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    """Return the 2-D cross product a x b -- sign gives the turn direction (z of the 3-D cross)."""
    return float(vec_a[0] * vec_b[1] - vec_a[1] * vec_b[0])


def _sign(value: float) -> int:
    value = float(value)
    return (value > 0) - (value < 0)


@backend_only("csg")
def _finish(
    shape: PyOpenSCAD,
    offset: Anchor | Sequence[float],
    spin: float,
    size: Sequence[float] | None = None,
    anchor: Anchor | Sequence[float] | None = None,
) -> "Bosl2Shape2D":
    """Anchor-translate and spin a freshly built native 2-D shape, then wrap it.

    Every shape constructor in this file funnels through here, which is what makes them all
    return a :class:`Bosl2Shape2D` rather than a bare native handle. *size*/*anchor* are the
    nominal box metadata to carry on the wrapper, for the shapes that have one. A shape that is
    already wrapped (``ring()`` composes two circles) is unwrapped first, never double-wrapped.
    """
    shape = Bosl2Shape2D._unwrap(shape)
    off: list[float] = list(offset.vector_2d) if isinstance(offset, Anchor) else list(offset)[:2]
    if off[0] != 0 or off[1] != 0:
        shape = shape.translate(off)
    if spin:
        # Native 2-D rotate needs the 3-vector form; a bare scalar is rejected.
        shape = shape.rotate([0, 0, spin])
    return Bosl2Shape2D(shape, size=size, anchor=anchor)


class CsgShape2D(BaseShape):
    """Wraps a native PyOpenSCAD **2-D** shape, giving it the same fluent,.

    chainable API that :class:`~pybosl2.shapes3d.Bosl2Solid` gives 3-D solids.

    Every shape constructor in this file
    returns one of these, as do :meth:`~pybosl2.paths.Path2D.polygon` and
    :meth:`~pybosl2.regions.Region.geometry`.

    Transforms, CSG operators, colour, and distributor methods are inherited from
    :class:`~pybosl2._shape.BaseShape`.

    The 2-D specific operations live here:

    * :meth:`fill` -- drop every hole, keeping only the outermost outline (OpenSCAD ``fill()``).
    * :meth:`hull` -- the convex hull of this shape, optionally together with more shapes/paths
      (OpenSCAD ``hull()``).
    * :meth:`offset` -- inset/outset, with BOSL2's ``radius=``/``delta=`` spelling (the native
      ``offset()`` only understands ``r=``).
    * :meth:`linear_extrude` / :meth:`rotate_extrude` -- the 2-D -> 3-D operators, which return a
      :class:`~pybosl2.shapes3d.Bosl2Solid` so the result keeps the 3-D fluent API.

    Like :class:`~pybosl2.shapes3d.Bosl2Solid` this is composition, not a subclass of the native
    C-extension type: passing one *directly* into a native function that wants a raw handle needs
    an explicit ``.shape`` (or :func:`pybosl2._helpers.unwrap`).

    .. seealso::

       `Visual spec sheet <specs/shapes2d.html>`_ — measurements and STL previews
    """

    #: Which realize backend produced this shape (always "csg" for Bosl2Shape2D).
    #: The SDF backend uses SdfShape2D for 2-D geometry.
    backend = "csg"

    #: This shape is two-dimensional; see CsgSolid.dimensions (SPEC E-7).
    dimensions = 2

    #: The nominal anchor box (SPEC S-2a), set per instance in __init__. Declared at class level as
    #: well so it is *statically* visible: on Python 3.12+ `isinstance` against a runtime-checkable
    #: Protocol uses static lookup, and an attribute only ever assigned in __init__ makes the class
    #: fail a check it satisfies perfectly at runtime (PLAN T-6b).
    size: "list[float] | None" = None

    _bbox: tuple[list[float], list[float]] | None = None

    def __init__(
        self,
        shape: PyOpenSCAD,
        size: Sequence[float] | None = None,
        anchor: Anchor | Sequence[float] | None = None,
        _bbox: tuple[list[float], list[float]] | None = None,
    ):
        """Initialize the instance."""
        self.shape = shape
        #: nominal [x, y] size for the shapes that have a genuine box size, else None
        self.size = None if size is None else [float(v) for v in size][:2]
        a_val: Anchor | Sequence[float] | None
        if anchor is None:
            a_val = Anchor.CENTER
        elif isinstance(anchor, Anchor):
            a_val = anchor
        elif isinstance(anchor, str):  # pragma: no cover
            # defensive: anchor_vector() rejects the string form at every entry point that builds
            # a shape, so one never reaches the constructor.
            raise Bosl2ValueError(f"Legacy string anchor selection is not allowed: {anchor!r}")
        else:
            a_val = resolve_anchor(list(anchor))
        self.anchor = a_val

        # Setup manual bbox tracking for fallback bounds
        if _bbox is not None:
            self._bbox = _bbox
        elif self.size is not None:
            sz = [float(v) for v in self.size]
            center = _anchor_offset_box(sz, a_val)
            self._bbox = (
                [center[0] - sz[0] / 2, center[1] - sz[1] / 2],
                [center[0] + sz[0] / 2, center[1] + sz[1] / 2],
            )
        else:
            self._bbox = None

    def _wrap(self, new_shape: Any) -> "CsgShape2D":
        out = type(self)(new_shape, self.size, self.anchor, _bbox=self._bbox)
        if hasattr(self, "backend"):
            out.backend = self.backend
        out.attachments = list(self.attachments)
        out.tag_name = self.tag_name
        out.diff_config = self.diff_config
        if hasattr(self, "_dont_propagate"):
            out._dont_propagate = getattr(self, "_dont_propagate", None)  # type: ignore[attr-defined]
        return out

    def translate(self, v: Sequence[float]) -> "CsgShape2D":
        """Translate the shape by a vector."""
        out = super().translate(v)
        if self._bbox is not None:
            v_float = [float(x) for x in v]
            lo, hi = self._bbox
            out._bbox = (
                [lo[0] + v_float[0], lo[1] + v_float[1]],
                [hi[0] + v_float[0], hi[1] + v_float[1]],
            )
        return out

    def rotate(self, *a: object, **k: object) -> "CsgShape2D":
        """Rotate the shape."""
        out = super().rotate(*a, **k)
        if self._bbox is not None:
            angle = 0.0
            if len(a) == 1 and isinstance(a[0], (int, float)):
                angle = float(a[0])
            elif "a" in k:
                angle = float(k["a"])  # type: ignore[arg-type]
            elif len(a) == 1 and isinstance(a[0], (list, tuple)) and len(a[0]) == 3:
                angle = float(a[0][2])
            rad = math.radians(angle)
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            lo, hi = self._bbox
            corners = [
                [lo[0], lo[1]],
                [hi[0], lo[1]],
                [lo[0], hi[1]],
                [hi[0], hi[1]],
            ]
            rot_corners = [[c[0] * cos_a - c[1] * sin_a, c[0] * sin_a + c[1] * cos_a] for c in corners]
            xs = [c[0] for c in rot_corners]
            ys = [c[1] for c in rot_corners]
            out._bbox = ([min(xs), min(ys)], [max(xs), max(ys)])
        return out

    def scale(self, v: float | Sequence[float]) -> "CsgShape2D":
        """Scale the shape."""
        out = super().scale(v)
        if self._bbox is not None:
            sv = [float(v), float(v)] if isinstance(v, (int, float)) else [float(x) for x in v]
            lo, hi = self._bbox
            scaled_lo = [lo[0] * sv[0], lo[1] * sv[1]]
            scaled_hi = [hi[0] * sv[0], hi[1] * sv[1]]
            out._bbox = (
                [min(scaled_lo[0], scaled_hi[0]), min(scaled_lo[1], scaled_hi[1])],
                [max(scaled_lo[0], scaled_hi[0]), max(scaled_lo[1], scaled_hi[1])],
            )
        return out

    def _resolve_bounds(self, bbox: Sequence[Sequence[float]] | None = None) -> tuple[list[float], list[float]]:
        if bbox is None:
            return self._center_size()
        arr = np.asarray(bbox, dtype=float)
        if not (arr.shape == (2, 2)):
            raise Bosl2ValueError("bbox must be [[min_x,min_y],[max_x,max_y]].")
        lo, hi = arr[0], arr[1]
        if not (bool(np.all(hi >= lo - 1e-12))):
            raise Bosl2ValueError("bbox must be [[min...],[max...]] with max >= min.")
        return [(lo[i] + hi[i]) / 2 for i in range(2)], [hi[i] - lo[i] for i in range(2)]

    def anchor_point(
        self, anchor: Anchor | Sequence[float], bbox: Sequence[Sequence[float]] | None = None
    ) -> list[float]:
        """Return the 2D point for the given anchor."""
        center, size = self._resolve_bounds(bbox)
        a = list(anchor.vector_2d) if isinstance(anchor, Anchor) else list(anchor)
        return [center[i] + a[i] * size[i] / 2 for i in range(2)]

    def reanchor(self, anchor: Anchor | Sequence[float], bbox: Sequence[Sequence[float]] | None = None) -> "CsgShape2D":
        """Move the shape so that the given anchor is at the origin."""
        p = self.anchor_point(anchor, bbox=bbox)
        moved = self.translate([-p[0], -p[1]])
        if moved.size is not None and isinstance(anchor, Anchor):
            moved.anchor = anchor
        return moved

    def position(self, anchor: Anchor, child: object, bbox: Sequence[Sequence[float]] | None = None) -> "CsgShape2D":
        """Place *child* so its local origin lands on this shape's bounding-box *anchor* point.

        The child is NOT unioned here: the returned copy of self carries it in
        :attr:`attachments`, and the union (or the tag-driven diff/intersection, if one is
        configured) happens later, in :meth:`realize` -- which runs automatically the first
        time a native operation needs real geometry. Until then :meth:`bounds` and the anchor
        points derived from it describe the PARENT only.

        Args:
            anchor: The parent anchor point to place the child's origin on.
            child: The shape to place (a 2-D pybosl2 shape or a raw native shape).
            bbox: Optional override bounding box ``[[min_x, min_y], [max_x, max_y]]``.

        Returns:
            A copy of this shape carrying the placed child as a pending attachment.

        """
        p = self.anchor_point(anchor, bbox=bbox)
        cshape = child if isinstance(child, CsgShape2D) else CsgShape2D(child)
        placed = cshape.translate(p)
        out = self._wrap(self.shape)
        out.attachments = list(self.attachments)
        out.attachments.append(placed)
        return out

    def align(
        self,
        anchor: Anchor,
        child: object,
        align: Anchor | None = None,
        inside: bool = False,
        overlap: float = 0.0,
        bbox: Sequence[Sequence[float]] | None = None,
    ) -> "CsgShape2D":
        """Place *child* against this shape's *anchor* edge, without reorienting it.

        Like :meth:`attach` it mates a child edge to a parent edge, but the child keeps its own
        axes and is merely translated. As with :meth:`position`, the child is deferred rather
        than unioned -- see that method for what that means for :meth:`bounds`.

        Args:
            anchor: The parent edge to place the child on.
            child: The shape to place (a 2-D pybosl2 shape or a raw native shape).
            align: Corner within the edge to sit flush against (default: centered).
            inside: Place the child inside the parent instead of outside.
            overlap: Pull the child toward the parent along the edge normal by this much.
            bbox: Optional override bounding box ``[[min_x, min_y], [max_x, max_y]]``.

        Returns:
            A copy of this shape carrying the placed child as a pending attachment.

        """
        face = list(anchor.vector_2d)
        edge = list(Anchor.CENTER.vector_2d) if align is None else list(align.vector_2d)
        factor = -1.0 if inside else 1.0
        cshape = child if isinstance(child, CsgShape2D) else CsgShape2D(child)
        child_anchor = Point([edge[0] - factor * face[0], edge[1] - factor * face[1]])
        cpt = cshape.anchor_point(child_anchor)
        dest = self.anchor_point(Point([face[0] + edge[0], face[1] + edge[1]]), bbox=bbox)
        fdir = list(unit(face)) if any(face) else [0.0, 0.0]
        ov = -overlap if inside else overlap
        placed = cshape.translate([dest[i] - cpt[i] - fdir[i] * ov for i in range(2)])
        out = self._wrap(self.shape)
        out.attachments = list(self.attachments)
        out.attachments.append(placed)
        return out

    def attach(
        self,
        parent_anchor: Anchor,
        child: object,
        child_anchor: Anchor | None = None,
        overlap: float = 0.0,
        spin: float = 0.0,
        bbox: Sequence[Sequence[float]] | None = None,
    ) -> "CsgShape2D":
        """Orient and place *child* so its *child_anchor* edge mates flush against *parent_anchor*.

        The child is NOT unioned here: the returned copy of self carries it in
        :attr:`attachments`, and the union (or the tag-driven diff/intersection, if one is
        configured) happens later, in :meth:`realize` -- which runs automatically the first
        time a native operation needs real geometry. Until then :meth:`bounds` and the anchor
        points derived from it describe the PARENT only, which is what lets several attach()
        calls chain off the same parent edges.

        Args:
            parent_anchor: Which edge of self to attach to.
            child: The shape to attach (a 2-D pybosl2 shape or a raw native shape).
            child_anchor: Which edge of the child mates against it (default: the child's edge
                opposite *parent_anchor*, so the two mate naturally).
            overlap: Pull the child in by this much along the mating axis.
            spin: Spin the child about the mating point, in degrees.
            bbox: Optional override bounding box ``[[min_x, min_y], [max_x, max_y]]``.

        Returns:
            A copy of this shape carrying the placed child as a pending attachment.

        """
        pa = list(parent_anchor.vector_2d)
        ca = [-pa[0], -pa[1]] if child_anchor is None else list(child_anchor.vector_2d)
        cshape = child if isinstance(child, CsgShape2D) else CsgShape2D(child)
        cpt = cshape.anchor_point(ca)
        placed = cshape.translate([-cpt[0], -cpt[1]])
        angle_rad = math.atan2(-pa[1], -pa[0]) - math.atan2(ca[1], ca[0])
        angle_deg = math.degrees(angle_rad)
        if abs(angle_deg) > 1e-9:
            placed = placed.rotate(angle_deg)
        if spin:
            placed = placed.rotate(spin)
        ppt = self.anchor_point(parent_anchor, bbox=bbox)
        pdir = list(unit(pa)) if any(pa) else [0.0, 0.0]
        placed = placed.translate([ppt[i] - pdir[i] * overlap for i in range(2)])
        out = self._wrap(self.shape)
        out.attachments = list(self.attachments)
        out.attachments.append(placed)
        return out

    spin = BaseShape.rotate

    def xflip(self, x: float = 0.0) -> "Bosl2Shape2D":
        """Mirror across the vertical line at *x*."""
        return self.translate([-x, 0.0]).mirror([1, 0]).translate([x, 0.0])

    def yflip(self, y: float = 0.0) -> "Bosl2Shape2D":
        """Mirror across the horizontal line at *y*."""
        return self.translate([0.0, -y]).mirror([0, 1]).translate([0.0, y])

    # ---- 2-D operators ----

    def offset(
        self,
        radius: float | None = None,
        delta: float | None = None,
        chamfer: bool = False,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Bosl2Shape2D":
        """Inset (negative) or outset (positive) the outline.

        *radius* rounds the joins it creates, *delta* keeps them sharp (or bevels them with
        ``chamfer=True``) -- BOSL2's spelling of OpenSCAD's ``r=``/``delta=``. Give exactly one.

        Examples:
            .. pythonscad-example::

                from pybosl2 import shapes2d as s2

                s2.star(tips=5, radius=30, inner_radius=15).offset(delta=4).linear_extrude(height=4).show()

        """
        if not ((radius is None) != (delta is None)):
            raise Bosl2ValueError("offset(): give exactly one of radius= or delta=.")
        kw: dict[str, Any] = {"r": radius} if radius is not None else {"delta": delta, "chamfer": chamfer}
        for name, value in (("fn", fn), ("fa", fa), ("fs", fs)):
            if value is not None:
                kw[name] = value
        # The offset moves the outline, so the nominal box size no longer describes it.
        return self._wrap(self.shape.offset(**kw))

    def fill(self) -> "Bosl2Shape2D":
        """Return this shape with every hole filled in -- only the outermost outline survives (OpenSCAD ``fill()``).

        Useful for recovering the solid footprint of a shape you have already punched holes in,
        e.g. to build a backing plate for it, or to close up the interior loops of ``text()``.

        Examples:
            .. pythonscad-example::

                from pybosl2 import shapes2d as s2

                plate = s2.square(40) - s2.circle(radius=8)
                plate.fill().linear_extrude(height=2).show()

        """
        return self._wrap(_ofill(self.shape))

    def hull(self, *others: "Shape2DLike") -> "Bosl2Shape2D":
        """Return the convex hull of this shape (OpenSCAD ``hull()``).

        With arguments, the hull of this shape *together with* each of *others* -- any mix of
        ``Bosl2Shape2D``, native 2-D shapes, :class:`~pybosl2.paths.Path2D` /
        :class:`~pybosl2.regions.Region`, or plain ``[[x, y], ...]`` point lists.

        Examples:
            .. pythonscad-example::

                from pybosl2 import shapes2d as s2

                slot = s2.circle(radius=5).hull(s2.circle(radius=5).right(30))
                slot.linear_extrude(height=3).show()

        """
        return Bosl2Shape2D(_ohull(self.shape, *[_as_native_2d(o) for o in others]))

    # ---- 2-D -> 3-D (returns a Bosl2Solid) ----

    def linear_extrude(
        self,
        height: float,
        center: bool = False,
        twist: float = 0.0,
        scale: "float | Sequence[float]" = 1,
        slices: int | None = None,
        convexity: int | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Bosl2Solid":
        """Extrude this 2-D shape *height* along +Z into a 3-D solid.

        Args:
            height:    extrusion height
            center:    centre the result on z=0 rather than starting at z=0 (default False)
            twist:     degrees to rotate the top face relative to the bottom (default 0)
            scale:     scale factor of the top face, a scalar or [x, y] (default 1)
            slices:    number of intermediate layers (default: from the twist)
            convexity: rendering hint for self-overlapping cross-sections
            fn:        arc smoothness override
            fa:        arc smoothness override
            fs:        arc smoothness override

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid`.

        Examples:
            .. pythonscad-example::

                from pybosl2 import shapes2d as s2

                s2.star(tips=5, radius=30, inner_radius=15).linear_extrude(height=6, twist=45).show()

            .. pythonscad-example::

                from pybosl2 import shapes2d as s2

                s2.circle(radius=15).linear_extrude(height=20).show()

        """
        from pybosl2.shapes3d import Bosl2Solid

        kw: dict[str, Any] = {
            "height": height,
            "center": center,
            "twist": twist,
            # the native drops a *scalar* scale= silently (a vector is honoured), so a uniform
            # taper would come out as a plain prism; hand it the vector form it acts on
            "scale": [float(scale), float(scale)] if isinstance(scale, (int, float)) else list(scale),
        }
        for name, value in (("slices", slices), ("convexity", convexity), ("fn", fn), ("fa", fa), ("fs", fs)):
            if value is not None:
                kw[name] = value
        size = None if self.size is None else [self.size[0], self.size[1], float(height)]
        return Bosl2Solid(self.shape.linear_extrude(**kw), size=size)

    def rotate_extrude(
        self,
        angle: float = 360.0,
        convexity: int | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Bosl2Solid":
        """Revolve this 2-D shape about the Y axis into a 3-D solid (OpenSCAD ``rotate_extrude()``).

        The shape must lie entirely on one side of the axis. *angle* sweeps less than a full
        revolution.

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid`.

        Examples:
            .. pythonscad-example::

                from pybosl2 import shapes2d as s2

                s2.square(10).right(15).rotate_extrude().show()

        """
        from pybosl2.shapes3d import Bosl2Solid

        kw: dict[str, Any] = {"angle": angle}
        for name, value in (
            ("convexity", convexity),
            ("fn", fn),
            ("fa", fa),
            ("fs", fs),
        ):
            if value is not None:
                kw[name] = value
        return Bosl2Solid(self.shape.rotate_extrude(**kw))

    def path_extrude(self, path: "PathLike", convexity: int | None = None) -> "Bosl2Solid":
        """Sweep this 2-D shape along *path* via the native ``path_extrude()``.

        *path* is a :class:`~pybosl2.paths.Path3D` or a point list.

        Returns:
            A :class:`~pybosl2.shapes3d.Bosl2Solid`.

        Examples:
            .. pythonscad-example::

                from pybosl2 import shapes2d as s2

                path = [[0, 0, 0], [20, 10, 10], [40, 0, 20], [60, 10, 30]]
                s2.circle(radius=5).path_extrude(path).show()

        """
        from pybosl2.shapes3d import Bosl2Solid

        pts = [[float(c) for c in p] for p in path]
        if convexity is None:
            return Bosl2Solid(self.shape.path_extrude(pts))
        return Bosl2Solid(self.shape.path_extrude(pts, convexity=convexity))

    # ---- colour (pybosl2/color.py) ----

    def _color_native(self, c: "str | Sequence[float] | None" = None, alpha: float | None = None) -> "Bosl2Shape2D":
        args = () if c is None else (c,)
        kw = {} if alpha is None else {"alpha": alpha}
        return self._wrap(self.shape.color(*args, **kw))

    def _highlight_native(self) -> "Bosl2Shape2D":
        return self._wrap(self.shape.highlight())

    def _ghost_native(self) -> "Bosl2Shape2D":
        return self._wrap(self.shape.background())

    # ---- distributors (pybosl2/distributors.py) ----

    def _distribute(self, mats: list[np.ndarray]) -> list["Bosl2Shape2D"]:  # type: ignore[override]
        """Return a list of multmatrix copies of this 2-D shape, one per matrix."""
        result = []
        for m in mats:
            m4 = np.asarray(m, dtype=float)
            assert abs(float(m4[2, 3])) < 1e-9, (
                "this copier moves the 2-D shape out of the XY plane; extrude it to 3-D first"
            )
            assert abs(float(m4[2, 2]) - 1.0) < 1e-9, (
                "this copier moves the 2-D shape out of the XY plane; extrude it to 3-D first"
            )
            copy = self.shape.multmatrix(m4.tolist())
            result.append(self._wrap(copy))
        return result

    def distribute_on_path(
        self,
        path: Path2D,
        num_copies: int | None = None,
        spacing: float | None = None,
        start_pos: float | None = None,
        dist: list[float] | None = None,
        rotate_children: bool = True,
    ) -> "Bosl2Shape2D":
        """Distribute copies of this 2-D shape along *path*, oriented to the path normal.

        Args:
            path: A :class:`~pybosl2.path2d.Path2D`.
            num_copies: Number of copies.
            spacing: Distance between copies.
            start_pos: Starting position along the path.
            dist: Explicit list of distances from path start.
            rotate_children: If True, rotate each copy to align with the path normal.

        Returns:
            A :class:`Bosl2Shape2D` union of all positioned copies.

        """
        import math

        length = path.perimeter()
        is_closed = getattr(path, "closed", False)
        if dist is not None:
            distances = sorted(float(x) for x in dist)
        elif start_pos is not None:
            if num_copies is not None and spacing is not None:
                distances = [start_pos + i * spacing for i in range(num_copies)]
            elif num_copies is not None:
                step = (length - start_pos) / (num_copies - 1) if num_copies > 1 else 0.0
                distances = [start_pos + i * step for i in range(num_copies)]
            else:
                if not (spacing is not None):
                    raise Bosl2ValueError("distribute_on_path(): provide num_copies or spacing.")
                cnt = int((length - start_pos) / spacing) + 1
                distances = [start_pos + i * spacing for i in range(cnt)]
        elif num_copies is not None and spacing is None:
            if not is_closed:
                step = length / (num_copies - 1) if num_copies > 1 else 0.0
                distances = [i * step for i in range(num_copies)]
            else:
                step = length / num_copies if num_copies > 0 else 0.0
                distances = [i * step for i in range(num_copies)]
        else:
            if not (spacing is not None):
                raise Bosl2ValueError("distribute_on_path(): provide num_copies, spacing, or dist.")
            cnt = num_copies if num_copies is not None else int(math.floor(length / spacing)) + (0 if is_closed else 1)
            ptlist = [i * spacing for i in range(cnt)]
            center = sum(ptlist) / len(ptlist)
            if is_closed:
                distances = sorted((e - center) % length for e in ptlist)
            else:
                distances = [e + length / 2 - center for e in ptlist]
        distances = [min(max(dst, 0.0), length) for dst in distances]
        cutlist = path.cut_points(distances, closed=is_closed, direction=True)
        results: list[Bosl2Shape2D] = []
        for cp in cutlist:
            copied: Bosl2Shape2D = self.translate([float(cp.point[0]), float(cp.point[1])])
            if rotate_children:
                nv = getattr(cp, "normal", [0, 1])
                ang = math.degrees(math.atan2(float(nv[1]), float(nv[0]))) - 90
                copied = copied.rotate(ang)
            results.append(copied)
        out = results[0]
        for r in results[1:]:
            out = out | r
        return out

    # ---- bounding box ----

    def bounds(self) -> Bounds2D:
        """Return this shape's axis-aligned bounding box in its current frame (SPEC S-2b).

        The 2-D form of :meth:`~pybosl2.shapes3d.CsgSolid.bounds`. Prefers the native bbox, which
        always reflects the current geometry; falls back to the tracked nominal size/anchor when
        the native accessors aren't available (the numeric test mock).

        Returns:
            The :class:`~pybosl2.bounds.Bounds2D` box, carrying ``min``/``max``, ``center``,
            ``size``, ``width`` and ``length``.

        Raises:
            Bosl2ValueError: If the shape has neither a native bounding box nor tracked size
                metadata.

        Examples:
            .. pythonscad-example::

                from pybosl2 import square

                shape = square([20, 10])
                print(shape.bounds().width)     # 20.0
                shape.linear_extrude(height=4).show()

        """
        center, size = self._center_size()
        return Bounds2D.from_center_size(center, size)

    def _center_size(self) -> "tuple[list[float], list[float]]":
        """Return the bounding box as the raw ``(center, size)`` pair the native layer reports."""
        try:
            pos, sz = self.shape.position, self.shape.size
        except AttributeError:
            pos = sz = None
        if pos is not None and sz is not None:
            mincorner = [float(pos[i]) for i in range(2)]
            size = [float(sz[i]) for i in range(2)]
            return [mincorner[i] + size[i] / 2 for i in range(2)], size
        if self._bbox is not None:
            lo, hi = self._bbox
            size = [hi[0] - lo[0], hi[1] - lo[1]]
            center = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2]
            return center, size
        if self.size is not None and not isinstance(self.anchor, str):
            size = [float(v) for v in self.size]
            assert self.anchor is not None
            return _anchor_offset_box(size, self.anchor), size
        raise Bosl2ValueError("bounds(): the shape has no native bounding box and no tracked size metadata.")


Bosl2Shape2D = CsgShape2D

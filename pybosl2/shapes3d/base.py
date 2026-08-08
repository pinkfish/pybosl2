# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/shapes3d/base.py
# FileSummary: Base solid wrapper class and core anchoring math helpers.
# DocCategory: internal
# FileGroup: BOSL2

"""Base solid wrapper class and core anchoring math helpers."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import numpy as np

from pybosl2._edges_lang import Anchor, EdgeAtom, resolve_anchor
from pybosl2._native import native

if TYPE_CHECKING:
    from collections.abc import Sequence

    from openscad import PyOpenSCAD

    from pybosl2.path2d import Path2D
    from pybosl2.path3d import Path3D
    from pybosl2.shapes2d import Bosl2Shape2D
from pybosl2._helpers import frag_count as _frag_count
from pybosl2._helpers import unwrap
from pybosl2._shape import BaseShape as BaseShape
from pybosl2.constants import BACK, DOWN, FRONT, LEFT, RIGHT, UP
from pybosl2.enums import AttachTag
from pybosl2.path2d import Path2D
from pybosl2.points import Point
from pybosl2.vectors import unit

if TYPE_CHECKING:  # real stub-typed imports for the checker (identical to pre-lazy)
    from pythonscad import cube as _ocube
    from pythonscad import cylinder as _ocylinder_native
    from pythonscad import hull as _ohull
    from pythonscad import minkowski as _ominkowski
    from pythonscad import polyhedron as _opolyhedron
    from pythonscad import rotate_extrude as _orotate_extrude
    from pythonscad import sphere as _osphere_native
    from pythonscad import textmetrics as _otextmetrics
else:
    _ocube = native("cube")
    _ocylinder_native = native("cylinder")
    _ohull = native("hull")
    _ominkowski = native("minkowski")
    _opolyhedron = native("polyhedron")
    _orotate_extrude = native("rotate_extrude")
    _osphere_native = native("sphere")
    _otextmetrics = native("textmetrics")


def _ocylinder(
    height: float | None = None,
    radius: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    center: bool | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> "PyOpenSCAD":
    """Return the native cylinder, accepting this file's full-word kwargs (native wants h/r/radius1/radius2)."""
    kw = {}
    for full, nat in (
        (height, "h"),
        (radius, "r"),
        (radius1, "r1"),
        (radius2, "r2"),
        (center, "center"),
        (fn, "fn"),
        (fa, "fa"),
        (fs, "fs"),
    ):
        if full is not None:
            kw[nat] = full
    return _ocylinder_native(**kw)


def _osphere(
    radius: float | None = None,
    center: bool | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> "PyOpenSCAD":
    """Return the native sphere, accepting this file's full-word kwargs (native wants r)."""
    kw = {}
    for full, nat in (
        (radius, "r"),
        (center, "center"),
        (fn, "fn"),
        (fa, "fa"),
        (fs, "fs"),
    ):
        if full is not None:
            kw[nat] = full
    return _osphere_native(**kw)


def _as_native_3d(obj: object) -> "PyOpenSCAD":
    """Return a raw native handle from *obj*.

    Accepts a :class:`Bosl2Solid` / ``Bosl2Shape2D`` wrapper, a native shape, or anything exposing
    ``geometry()`` (a :class:`~pybosl2.vnf.VNF`, a :class:`~pybosl2.paths.Path2D`,
    a :class:`~pybosl2.regions.Region`).
    """
    from pybosl2._helpers import unwrap

    unwrapped = unwrap(obj)
    if unwrapped is not obj:  # a Bosl2Solid / Bosl2Shape2D wrapper
        return unwrapped
    geom = getattr(obj, "geometry", None)  # VNF / Path2D / Region
    if callable(geom):
        return unwrap(geom())
    return obj


# ---------------------------------------------------------------------------
# Section: Base class
# ---------------------------------------------------------------------------


class CsgSolid(BaseShape):
    """Wraps a PyOpenSCAD solid together with geometry metadata for BOSL2-style attachment.

    Tracks nominal `size` and `anchor` that BOSL2's $parent_geom attachment system would
    otherwise track, so that edge/corner/face masking (pybosl2/masking.py) work as plain chained
    methods instead of needing size=/anchor= threaded through by hand at every call site.
    Every function in this file returns an instance of this class (or a subclass).

    Transforms, CSG operators, colour, and distributor methods are inherited from
    :class:`~pybosl2._shape.BaseShape`.

    Only cuboid()-shaped objects (cube(), cuboid() -- the only ones in this file with a genuine
    axis-aligned box `size`) support the masking methods; every other shape (prismoid, wedge,
    octahedron, the cylinder family, the sphere family) carries size=None and will assert if a
    masking method is called on it, since pybosl2/masking.py's edge/corner positioning math only
    supports cuboid parents.

    CAVEAT: this is a plain Python wrapper (composition), not a subclass of the real native
    PyOpenSCAD C-extension type -- there was no way to verify from this environment whether
    that type even supports subclassing. Calling a method on a Bosl2Solid (`shape.translate(...)`,
    `shape.edge_profile(...)`) is safe. But if a Bosl2Solid is ever passed *directly* as a bare
    argument into a function that expects a native geometry object -- `hull(a, b)`,
    `minkowski(a, b)` -- rather than having a method called on it, the receiving function needs
    the raw native object: use `.shape` to unwrap explicitly.

    .. seealso::

       `Visual spec sheet <specs/shapes3d.html>`_ — measurements and STL previews
    """

    #: which realize backend produced this solid -- see pybosl2/_backend.py. Bosl2Solid is the
    #: exact-CSG (PythonSCAD) backend's Solid; the libfive/SDF backend uses its own wrapper.
    backend: str

    def __init__(
        self,
        shape: PyOpenSCAD,
        size: Sequence[float] | None = None,
        anchor: Anchor | Sequence[float] | None = None,
    ):
        """Initialize the instance."""
        self.shape = shape
        self.size = size
        a_val: Anchor | None
        if anchor is None:
            a_val = Anchor.CENTER
        elif isinstance(anchor, Anchor):
            a_val = anchor
        elif isinstance(anchor, str):
            raise ValueError(f"Legacy string anchor selection is not allowed: {anchor!r}")
        else:
            a_val = resolve_anchor(list(anchor))
        self.anchor = a_val
        from pybosl2._backend import current_backend

        self.backend = current_backend()

    # ---- 3-D directional overrides (use 3-vectors) -------------------------

    def right(self, x: float) -> "Bosl2Solid":
        """Move the solid to the right."""
        return self.translate([x, 0.0, 0.0])

    def left(self, x: float) -> "Bosl2Solid":
        """Move the solid to the left."""
        return self.translate([-x, 0.0, 0.0])

    def back(self, y: float) -> "Bosl2Solid":
        """Move the solid to the back."""
        return self.translate([0.0, y, 0.0])

    def forward(self, y: float) -> "Bosl2Solid":
        """Move the solid forward."""
        return self.translate([0.0, -y, 0.0])

    def up(self, z: float) -> "Bosl2Solid":
        """Move the solid up."""
        return self.translate([0.0, 0.0, z])

    def down(self, z: float) -> "Bosl2Solid":
        """Move the solid down."""
        return self.translate([0.0, 0.0, -z])

    # ---- native-only mesh operations (no BOSL2 equivalent) ----
    #
    # PythonSCAD provides several solid operations that BOSL2 has no counterpart for; they are
    # exposed here as first-class Bosl2Solid methods (re-wrapping the native result so anchoring
    # metadata and fluent chaining survive) rather than leaking raw native handles through
    # __getattr__. These execute only inside the real PythonSCAD app; under the numeric test mock
    # they degrade to identity/AABB stand-ins (see mock_libfive.py), so the fast suite still runs
    # and their real geometry is covered by the STL render tests.

    def repair(self) -> "Bosl2Solid":
        """Force the mesh watertight, healing gaps/non-manifold edges (native ``repair()``).

        Examples:
            .. pythonscad-example::

                from pybosl2.solid import cuboid

                cuboid([10, 20, 30]).repair().show()

        """
        return self._wrap(self.shape.repair())

    def wrap(self, radius: float, fn: int | None = None) -> "Bosl2Solid":
        """Wrap this solid around a cylinder of radius *radius*, bending +X into.

        the cylinder's circumference (native ``wrap()``). *fn* sets the
        facet count of the bend.
        """
        if fn is not None:
            return self._wrap(self.shape.wrap(r=float(radius), fn=float(fn)))
        return self._wrap(self.shape.wrap(r=float(radius)))

    def pull(self, direction: "Sequence[float] | np.ndarray", distance: float) -> "Bosl2Solid":
        """Pull the part of the solid on the +*direction* side apart by.

        *distance*, stretching the material between (native ``pull()``).
        """
        return self._wrap(self.shape.pull([float(x) for x in direction], float(distance)))

    def oversample(self, sides: int) -> "Bosl2Solid":
        """Subdivide every mesh facet *sides*-fold, e.g. before :meth:`wrap`.

        so the bend is smooth (native ``oversample()``).

        Examples:
            .. pythonscad-example::

                from pybosl2.solid import cuboid

                bar = cuboid([80, 5, 3])
                bar.oversample(sides=4).wrap(radius=20).show()

        """
        return self._wrap(self.shape.oversample(int(sides)))

    def separate(self) -> "list[Bosl2Solid]":
        """Split a solid made of disconnected lumps into a list of its connected components (native ``separate()``)."""
        return [self._wrap(part) for part in self.shape.separate()]

    def inside(self, point: "Sequence[float] | np.ndarray") -> bool:
        """Return True if *point* lies inside the solid (native ``inside()``)."""
        return bool(self.shape.inside([float(x) for x in point]))

    # ---- hull / projection ----

    def hull(self, *others: object) -> "Bosl2Solid":
        """Return the convex hull of this solid (OpenSCAD ``hull()``).

        With arguments, the hull of this solid *together with* each of *others* -- the shrink-wrap
        around them all, which is how BOSL2 builds a rounded box from spheres at its corners.
        Each of *others* may be a ``Bosl2Solid``, a raw native solid, or a
        :class:`~pybosl2.vnf.VNF`/point list, which is meshed as a polyhedron first.

        See :meth:`chain_hull` to hull consecutive *pairs*
        instead of everything at once.

        Examples:
            .. pythonscad-example::

                from pybosl2.solid import sphere

                capsule = sphere(radius=8).hull(sphere(radius=8).up(30))
                capsule.show()

        """
        return Bosl2Solid(_ohull(self.shape, *[_as_native_3d(o) for o in others]))

    def minkowski(self, *others: object) -> "Bosl2Solid":
        """Return the Minkowski SUM of this solid with *others* (OpenSCAD ``minkowski()``).

        Sweeps each of *others* over the whole of this solid, growing it by that shape. Sweeping
        a sphere grows it by a uniform margin with rounded corners, a cube with square ones --
        the usual way to turn a part into the cutter that clears it. This is the 3-D counterpart
        of :meth:`~pybosl2.shapes2d.Bosl2Shape2D.minkowski`, and the dilating opposite of
        :meth:`minkowski_difference`, which erodes.

        Each of *others* may be a ``Bosl2Solid`` or a raw native solid; several are applied in
        turn, matching OpenSCAD's variadic ``minkowski()``.

        Note this is EXPENSIVE -- cost grows with the product of the operands' complexity -- so
        keep the swept shape as simple as the result allows (a low-``fn`` sphere, or a cube).

        Args:
            others: One or more solids to sweep over this one.

        Returns:
            A new :class:`Bosl2Solid` of the Minkowski sum.

        Raises:
            AssertionError: If no shape to sweep is given.

        Examples:
            A plate grown by a rounded 2mm margin:

            .. pythonscad-example::

                from pybosl2.shapes3d import cuboid, sphere

                cuboid([20, 30, 5]).minkowski(sphere(radius=2, fn=16)).show()

        """
        from pythonscad import minkowski as _ominkowski

        assert others, "minkowski(): needs at least one shape to sweep over this solid."
        out = self.shape
        for other in others:
            out = _ominkowski(out, _as_native_3d(other))
        return Bosl2Solid(out)

    def projection(self, cut: bool = False) -> "Bosl2Shape2D":
        """Return the 2-D shadow of this solid on the XY plane (OpenSCAD ``projection()``).

        With ``cut=True`` you get the cross-section where the solid crosses the z=0 plane instead
        of the full outline -- slice the solid at the height you want first.

        Returns:
            A :class:`~pybosl2.shapes2d.Bosl2Shape2D`, so the result chains straight back into the
            2-D operators (``.offset()``, ``.fill()``, ``.hull()``) and the extruders.

        Note:
            CSG only. The SDF backend's :meth:`~pybosl2._sdf.shapes3d.PyShape.projection` raises
            :class:`~pybosl2.exceptions.UnsupportedByBackendError` -- a distance field has no
            closed-form 2-D shadow, and 2-D geometry is a CSG-backend notion.

        Examples:
            A footprint outline, grown 2mm, extruded into a base plate:

            .. pythonscad-example::

                from pybosl2.solid import cuboid

                part = cuboid([30, 20, 10], rounding=3)
                part.projection().offset(radius=2).linear_extrude(height=2).show()

        """
        from pybosl2.shapes2d import Bosl2Shape2D

        return Bosl2Shape2D(self.shape.projection(cut=cut))

    # ---- colour (pybosl2/color.py) ----
    #
    # The Colourable base class provides color/recolor/hsl/hsv/highlight/ghost;
    # these are the native primitives they resolve to.

    def _color_native(self, c: str | None = None, alpha: float | None = None) -> "Bosl2Solid":
        args = () if c is None else (c,)
        kw = {} if alpha is None else {"alpha": alpha}
        return self._wrap(self.shape.color(*args, **kw))

    def _highlight_native(self) -> "Bosl2Solid":
        return self._wrap(self.shape.highlight())

    def _ghost_native(self) -> "Bosl2Solid":
        return self._wrap(self.shape.background())

    def to_csg(self) -> "Bosl2Solid":
        """Return this solid on the CSG backend -- returns self (the converter no-op)."""
        return self

    def to_sdf(self) -> "Bosl2Solid":
        """CSG -> SDF conversion is not supported (would require lossy voxel-sampling)."""
        from pybosl2.exceptions import UnsupportedByBackendError

        raise UnsupportedByBackendError(
            "to_sdf",
            "csg",
            hint="a CSG tree has no signed-distance field; build the shape on the SDF backend "
            "instead (with use_backend('sdf')). Only SDF->CSG (PyShape.to_csg()) is supported.",
        )

    # ---- distributors (pybosl2/distributors.py) ----
    #
    # The distributors.scad copiers, inherited from Distributable via BaseShape, resolve to
    # _distribute(), which for a solid means: multmatrix a copy for each transform.

    def _distribute(self, mats: list[np.ndarray]) -> list["Bosl2Solid"]:  # type: ignore[override]
        """Return a list of multmatrix copies of this solid, one per matrix."""
        return [self._wrap(self.shape.multmatrix(np.asarray(m).tolist())) for m in mats]

    def distribute_on_path(
        self,
        path: Path3D,
        num_copies: int | None = None,
        spacing: float | None = None,
        start_pos: float | None = None,
        dist: list[float] | None = None,
        rotate_children: bool = True,
    ) -> "Bosl2Solid":
        """Distribute copies of this solid along *path*, oriented to the 3-D path direction.

        Args:
            path: A :class:`~pybosl2.path3d.Path3D`.
            num_copies: Number of copies.
            spacing: Distance between copies.
            start_pos: Starting position along the path.
            dist: Explicit list of distances from path start.
            rotate_children: If True, rotate each copy to align with the path.

        Returns:
            A :class:`Bosl2Solid` union of all positioned copies.

        """
        import math

        import numpy as np

        length = path.perimeter()
        is_closed = getattr(path, "closed", False)
        if dist is not None:
            distances = sorted(float(x) for x in dist)
        elif start_pos is not None:
            if num_copies is not None and spacing is not None:
                distances = [start_pos + i * spacing for i in range(num_copies)]
            elif num_copies is not None:
                distances = list(np.linspace(start_pos, length, num_copies))
            else:
                distances = list(np.arange(start_pos, length, spacing))
        elif num_copies is not None and spacing is None:
            distances = list(np.linspace(0, length, num_copies, endpoint=not is_closed))
        else:
            assert spacing is not None, "distribute_on_path(): provide num_copies, spacing, or dist."
            cnt = num_copies if num_copies is not None else int(math.floor(length / spacing)) + (0 if is_closed else 1)
            ptlist = [i * spacing for i in range(cnt)]
            center = sum(ptlist) / len(ptlist)
            if is_closed:
                distances = sorted((e - center) % length for e in ptlist)
            else:
                distances = [e + length / 2 - center for e in ptlist]
        distances = [min(max(dst, 0.0), length) for dst in distances]
        cutlist = path.cut_points(distances, closed=is_closed, direction=True)
        results: list[Bosl2Solid] = []
        for cp in cutlist:
            copied: Bosl2Solid = self.translate([float(v) for v in cp.point])
            if rotate_children:
                d = np.asarray(cp.direction, dtype=float)
                n = np.asarray(cp.normal, dtype=float)
                xv = d / (float(np.linalg.norm(d)) or 1)
                zv = n / (float(np.linalg.norm(n)) or 1)
                yv = np.cross(zv, xv)
                yv = yv / (float(np.linalg.norm(yv)) or 1)
                rotm = np.eye(4)
                rotm[:3, 0], rotm[:3, 1], rotm[:3, 2] = xv, yv, zv
                copied = copied.multmatrix(rotm.tolist())
            results.append(copied)
        out = results[0]
        for r in results[1:]:
            out = out | r
        return out

    # ---- bounding-box anchoring (works on ANY object, via PythonSCAD's native bbox) ----
    #
    # PythonSCAD exposes obj.position (min corner) / obj.size (extent) / obj.bbox (a solid),
    # each computed by actually meshing the object. That lets anchoring/attachment/masking
    # find where an anchor point is on ANY object without the caller passing a size -- BOSL2
    # normally threads $parent_geom through for this. Tracked cuboid size/anchor metadata,
    # when present, is used first as a no-meshing fast path.

    def _native_bounds(self) -> "tuple[list[float], list[float]] | None":
        """Return the object's axis-aligned bounding box as (mincorner, size),.

        read from the native obj.position/obj.size. Returns None when
        those accessors aren't available (the numeric test mock) or the
        geometry is empty/degenerate (native returns None).
        """
        try:
            pos = self.shape.position
            sz = self.shape.size
        except AttributeError:
            # The native handle doesn't expose position/size (the numeric test mock). A genuine
            # error from the real accessor (e.g. a broken mesh) is NOT swallowed -- it propagates.
            return None
        if pos is None or sz is None:
            return None
        try:
            mincorner = [float(pos[i]) for i in range(3)]
            size = [float(sz[i]) for i in range(3)]
        except (TypeError, IndexError, ValueError):
            return None
        return mincorner, size

    def bounds(self) -> "tuple[list[float], list[float]]":
        """Return this object's axis-aligned bounding box as (center, size) --.

        both plain [x, y, z] float lists in the object's CURRENT
        coordinate frame (after any translate/rotate/CSG).

        Prefers the native bbox, which always reflects the actual current geometry -- this is
        what lets anchoring/attachment/masking work without the caller tracking a size, and
        stays correct after the object has been moved or combined. Falls back to the tracked
        cuboid size/anchor metadata only when the native accessors aren't available (the numeric
        test mock). Raises if neither is available.
        """
        nb = self._native_bounds()
        if nb is not None:
            mincorner, size = nb
            return [mincorner[i] + size[i] / 2 for i in range(3)], size
        if self.size is not None and self.anchor is not None:
            size = [float(v) for v in self.size]
            return _anchor_offset_box3(size, self.anchor), size
        raise ValueError(
            "bounds(): object has no native bounding box and no tracked cuboid size/anchor "
            "metadata (are you calling this under the numeric mock on a non-cuboid?)"
        )

    def _resolve_bounds(self, bbox: Sequence[Sequence[float]] | None = None) -> "tuple[list[float], list[float]]":
        """Return (center, size) for anchoring: from a passed-in *bbox*.

        override if given, else the object's native bounding box
        (:meth:`bounds`). *bbox* overrides the object's own box -- useful
        when the native bbox is wrong for the purpose (a shape with an
        overhang, a mask positioned against a nominal box, or a cheap way
        to skip the meshing the native bbox needs). It is a min/max corner
        pair ``[[min_x, min_y, min_z], [max_x, max_y, max_z]]`` (the same
        shape :meth:`Path2D.bounds` and the native ``obj.bbox`` use).
        """
        if bbox is None:
            return self.bounds()
        arr = np.asarray(bbox, dtype=float)
        assert arr.shape == (2, 3), "bbox must be [[min_x,min_y,min_z],[max_x,max_y,max_z]]."
        lo, hi = arr[0], arr[1]
        assert bool(np.all(hi >= lo - 1e-12)), "bbox must be [[min...],[max...]] with max >= min."
        return [(lo[i] + hi[i]) / 2 for i in range(3)], [hi[i] - lo[i] for i in range(3)]

    def anchor_point(
        self, anchor: Anchor | Sequence[float], bbox: Sequence[Sequence[float]] | None = None
    ) -> list[float]:
        """Return the [x, y, z] point on this object's bounding box for the.

        given anchor, in the object's current coordinate frame: center +
        anchor * size / 2. Works on any object.

        Pass *bbox* to anchor against a supplied box instead of the object's own (see
        :meth:`_resolve_bounds`).

        Args:
            anchor: An :class:`Anchor` enum or a sequence of three floats.
            bbox: Optional override bounding box.

        """
        center, size = self._resolve_bounds(bbox)
        a = anchor.vector if isinstance(anchor, Anchor) else list(anchor)
        return [center[i] + a[i] * size[i] / 2 for i in range(3)]

    def reanchor(self, anchor: Anchor | Sequence[float], bbox: Sequence[Sequence[float]] | None = None) -> "Bosl2Solid":
        """Return this object translated so its bounding-box `anchor` point.

        sits at the origin. Re-anchors any object by its bbox after the
        fact (cube()/cuboid() only do this at construction, and only for
        cuboids). Pass *bbox* to use a supplied box.

        Examples:
        .. pythonscad-example::

            from pybosl2.solid import cuboid
            from pybosl2 import Anchor

            cuboid([10, 20, 30]).reanchor(Anchor.BOTTOM).show()

        """
        p = self.anchor_point(anchor, bbox=bbox)
        moved = self.translate([-p[0], -p[1], -p[2]])
        if moved.size is not None and isinstance(anchor, Anchor):
            moved.anchor = anchor
        return moved

    def position(self, anchor: Anchor, child: object, bbox: Sequence[Sequence[float]] | None = None) -> "Bosl2Solid":
        """Place `child` so its local origin lands on this object's bounding-box `anchor` point.

        The child keeps its own orientation. `child` may be a Bosl2Solid or a raw native solid.

        The child is NOT unioned here: the returned copy of self carries it in
        :attr:`attachments`, and the union (or the tag-driven diff/intersection, if one is
        configured) happens later, in :meth:`realize` -- which runs automatically the first
        time a native operation such as ``show()`` or ``mesh()`` needs real geometry. Until
        then :meth:`bounds` and the anchor points derived from it describe the PARENT only,
        so chained anchoring stays keyed to the parent rather than drifting as children are
        added. Call :meth:`realize` yourself if you need a single measurable solid sooner.

        Examples:
        .. pythonscad-example::

            from pybosl2.solid import cuboid, sphere
            from pybosl2 import Anchor

            cube = cuboid([30, 30, 10])
            knob = sphere(radius=5)
            cube.position(Anchor.TOP_FRONT_LEFT, knob).show()

        """
        p = self.anchor_point(anchor, bbox=bbox)
        csolid = child if isinstance(child, Bosl2Solid) else Bosl2Solid(child)
        placed = csolid.translate(p)
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
    ) -> "Bosl2Solid":
        """Place `child` on this object's `anchor` face, without reorienting it.

        Like :meth:`attach` it mates a child face to a parent face, but the child keeps its
        own axes and is merely translated.

        As with :meth:`position` and :meth:`attach`, the child is deferred rather than
        unioned: it goes into :attr:`attachments` on the returned copy and is combined in
        :meth:`realize`, so :meth:`bounds` still reports the parent alone until then.

        With `align` omitted the child is centered on the face, sitting OUTSIDE the parent
        (inside=False, the default) or tucked inside (inside=True). Pass `align` (an edge/corner
        direction within the face, e.g. RIGHT for the +x edge) to sit the child flush against
        that edge/corner instead -- matching BOSL2 align()'s anchor+align pair. Both anchor
        points come from the native bounding boxes, so no size needs to be passed.

        Args:
            anchor:  the parent face to place the child on (e.g. Anchor.TOP)
            child:   the solid to place (Bosl2Solid or raw native solid)
            align:   edge/corner within the face to sit flush against (default: centered)
            inside:  place the child inside the parent instead of outside (default False)
            overlap: pull the child toward the parent along the face normal by this much
            bbox: optional override bounding box ``[[min_x, min_y, min_z], [max_x, max_y, max_z]]``.

        Examples:
        .. pythonscad-example::

            from pybosl2.solid import cuboid
            from pybosl2 import Anchor

            cube = cuboid([30, 30, 10])
            label = cuboid([10, 5, 5])
            cube.align(Anchor.FRONT, label, align=Anchor.LEFT).show()

        """
        face = anchor.vector
        edge = Anchor.CENTER.vector if align is None else align.vector
        factor = -1.0 if inside else 1.0
        csolid = child if isinstance(child, Bosl2Solid) else Bosl2Solid(child)
        child_anchor = Point([edge[i] - factor * face[i] for i in range(3)])
        cpt = csolid.anchor_point(child_anchor)
        dest = self.anchor_point(Point([face[i] + edge[i] for i in range(3)]), bbox=bbox)
        fdir = list(unit(face)) if any(face) else [0.0, 0.0, 0.0]
        ov = -overlap if inside else overlap
        placed = csolid.translate([dest[i] - cpt[i] - fdir[i] * ov for i in range(3)])
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
    ) -> "Bosl2Solid":
        """Orient and place `child` so its `child_anchor` face mates flush against `parent_anchor`.

        Both anchor points come from the native bounding boxes, so neither object needs its
        size passed explicitly.

        The child is NOT unioned here: the returned copy of self carries it in
        :attr:`attachments`, and the union (or the tag-driven diff/intersection, if one is
        configured) happens later, in :meth:`realize` -- which runs automatically the first
        time a native operation such as ``show()`` or ``mesh()`` needs real geometry. Until
        then :meth:`bounds` and the anchor points derived from it describe the PARENT only,
        which is what lets several attach() calls chain off the same parent faces. Call
        :meth:`realize` yourself if you need a single measurable solid sooner.

        Args:
            parent_anchor: which face of self to attach to (e.g. Anchor.TOP)
            child:         the solid to attach (Bosl2Solid or raw native solid)
            child_anchor:  which face of the child mates against it (default: the child's
                           face OPPOSITE parent_anchor, so the two mate naturally)
            overlap:       pull the child in by this much along the mating axis (default 0)
            spin:          spin the child about the mating axis, in degrees (default 0)
            bbox: optional override bounding box ``[[min_x, min_y, min_z], [max_x, max_y, max_z]]``.

        Examples:
        .. pythonscad-example::

            from pybosl2.solid import cuboid, cylinder
            from pybosl2 import Anchor

            cube = cuboid([20, 30, 10])
            cyl = cylinder(height=15, radius=4)
            cube.attach(Anchor.UP, cyl).show()

        """
        pa = parent_anchor.vector
        ca = -pa if child_anchor is None else child_anchor.vector
        csolid = child if isinstance(child, Bosl2Solid) else Bosl2Solid(child)
        cpt = csolid.anchor_point(ca)
        placed = csolid.translate([-cpt[0], -cpt[1], -cpt[2]])
        angle, axis = _rot_from_to(
            [float(ca[0]), float(ca[1]), float(ca[2])],
            [-float(pa[0]), -float(pa[1]), -float(pa[2])],
        )
        if angle:
            placed = placed.rotate(angle, axis)
        if spin and any(pa):
            placed = placed.rotate(spin, list(unit(pa)))
        ppt = self.anchor_point(pa, bbox=bbox)
        pdir = list(unit(pa)) if any(pa) else [0.0, 0.0, 0.0]
        placed = placed.translate([ppt[i] - pdir[i] * overlap for i in range(3)])
        out = self._wrap(self.shape)
        out.attachments = list(self.attachments)
        out.attachments.append(placed)
        return out

    def reorient(
        self,
        anchor: Anchor | Sequence[float] = Anchor.CENTER,
        spin: float = 0,
        orient: Anchor | Sequence[float] = Anchor.TOP,
        bbox: Sequence[Sequence[float]] | None = None,
    ) -> "Bosl2Solid":
        """Reorient this already-built object by its bounding box.

        Moves the bounding-box *anchor* point to the origin, spins *spin* degrees about Z, then
        rotates the object's UP toward *orient*. The size comes from the native bbox, so -- unlike
        BOSL2's function form -- you never pass it. cube()/cuboid()/etc. take anchor/spin/orient at
        construction; this applies the same transform to any object after the fact. Pass *bbox* to
        reorient against a supplied box instead of the object's own.

        Examples:
        .. pythonscad-example::

            from pybosl2.solid import cuboid
            from pybosl2 import Anchor

            cuboid([10, 20, 30]).reorient(anchor=Anchor.BOTTOM, orient=Anchor.TOP).show()

        """
        from pybosl2.transforms import reorient as _reorient_matrix

        center, size = self._resolve_bounds(bbox)
        a_vec = list(anchor.vector) if isinstance(anchor, Anchor) else list(anchor)
        o_vec = list(orient.vector) if isinstance(orient, Anchor) else list(orient)
        m = _reorient_matrix(anchor=a_vec, spin=spin, orient=o_vec, size=size)
        centered = self.translate([-center[0], -center[1], -center[2]])
        return centered.multmatrix(np.asarray(m).tolist())

    def orient(
        self, direction: Anchor = Anchor.TOP, spin: float = 0, bbox: Sequence[Sequence[float]] | None = None
    ) -> "Bosl2Solid":
        """Rotate this object so its top (UP) faces *direction*; uses the bbox.

        Examples:
        .. pythonscad-example::

            from pybosl2.solid import cylinder
            from pybosl2 import Anchor

            cylinder(height=30, radius=5).orient(Anchor.TOP).show()

        """
        return self.reorient(anchor=Anchor.CENTER, spin=spin, orient=direction, bbox=bbox)

    # ---- edge/corner/face masking (pybosl2/masking.py), box-shaped objects ----
    #
    # These now work on ANY box-shaped object: the cutter size and box center come from
    # bounds() (tracked metadata when available, else the native bbox), so callers no longer
    # have to pass size= or keep the object as a freshly-built cuboid.
    def edge_mask(
        self,
        edges: EdgeAtom | list[EdgeAtom] = Anchor.ALL,
        except_edges: list[EdgeAtom] | None = None,
        children: PyOpenSCAD | None = None,
        bbox: Sequence[Sequence[float]] | None = None,
        tag: AttachTag | str | None = None,
    ) -> "Bosl2Solid":
        """Cut a pre-built 3-D edge cutter along each selected edge of this box-shaped solid.

        The cutter size and box center come from :meth:`bounds`, so you don't need to pass
        *size* or keep the object as a freshly-built cuboid.

        Args:
            edges:        edges to mask (default ``"ALL"``)
            except_edges: edges to explicitly not mask
            children:     the pre-built 3-D edge cutter
            bbox:         override bounding box (see :meth:`_resolve_bounds`)
            tag:          override tag for attachment (default: AttachTag.REMOVE)

        """
        from pybosl2 import masking

        center, size = self._resolve_bounds(bbox)
        cutter_shape = masking.edge_mask(
            self.shape,
            edges,
            except_edges,
            children,
            size=(size[0], size[1], size[2]),
            center=Point(center[0], center[1], center[2]),
            return_cutter=True,
        )
        if cutter_shape is None:
            return self._wrap(self.shape)

        t: AttachTag | str = AttachTag.REMOVE if tag is None else tag
        out = self._wrap(self.shape)
        out.attachments = list(self.attachments)
        out.attachments.append(Bosl2Solid(unwrap(cutter_shape)).tag(t))
        if t == AttachTag.REMOVE:
            out.diff_config = {"type": "diff", "remove": ["remove"], "keep": ["keep"]}
        return out

    def edge_profile(
        self,
        edges: EdgeAtom | list[EdgeAtom] = Anchor.ALL,
        except_edges: list[EdgeAtom] | None = None,
        children: Sequence[Sequence[float]] | None = None,
        convexity: int = 10,
        bbox: Sequence[Sequence[float]] | None = None,
        radius: float | None = None,
        diameter: float | None = None,
        r: float | None = None,
        d: float | None = None,
        tag: AttachTag | str | None = None,
    ) -> "Bosl2Solid":
        """Cut a 2-D mask profile along each selected edge of this box-shaped solid.

        Args:
            edges:        edges to mask (default ``"ALL"``)
            except_edges: edges to explicitly not mask
            children:     the 2-D mask cross-section path
            convexity:    accepted for compatibility; unused
            bbox:         override bounding box (see :meth:`_resolve_bounds`)
            radius:       rounding radius
            diameter:     rounding diameter
            r:            rounding radius alias
            d:            rounding diameter alias
            tag:          override tag for attachment (defaults to AttachTag.KEEP if negative, else AttachTag.REMOVE)

        """
        from pybosl2 import masking

        center, size = self._resolve_bounds(bbox)

        rad = radius if radius is not None else r
        if rad is None:
            dia = diameter if diameter is not None else d
            if dia is not None:
                rad = dia / 2

        resolved_children: Sequence[Sequence[float]] | Path2D | None = children
        if rad is not None and resolved_children is None:
            resolved_children = masking.mask2d_roundover(abs(rad))
        if resolved_children is not None and not isinstance(resolved_children, Path2D):
            resolved_children = Path2D(resolved_children, closed=False)

        cutter_shape = masking.edge_profile(
            self.shape,
            edges,
            except_edges,
            children=resolved_children,
            size=(size[0], size[1], size[2]),
            convexity=convexity,
            center=Point(center[0], center[1], center[2]) if center is not None else None,
            return_cutter=True,
        )
        if cutter_shape is None:
            return self._wrap(self.shape)

        t: AttachTag | str = (
            (AttachTag.KEEP if (rad is not None and rad < 0) else AttachTag.REMOVE) if tag is None else tag
        )

        out = self._wrap(self.shape)
        out.attachments = list(self.attachments)
        out.attachments.append(Bosl2Solid(unwrap(cutter_shape)).tag(t))
        if t == AttachTag.REMOVE:
            out.diff_config = {"type": "diff", "remove": ["remove"], "keep": ["keep"]}
        return out

    def edge_profile_asym(
        self,
        edges: EdgeAtom | list[EdgeAtom] = Anchor.ALL,
        except_edges: list[EdgeAtom] | None = None,
        children: Sequence[Sequence[float]] | None = None,
        convexity: int = 10,
        radius: float | None = None,
        diameter: float | None = None,
        r: float | None = None,
        d: float | None = None,
        tag: AttachTag | str | None = None,
    ) -> "Bosl2Solid":
        """Cut an asymmetric edge profile into the solid's edges."""
        return self.edge_profile(
            edges=edges,
            except_edges=except_edges,
            children=children,
            convexity=convexity,
            radius=radius,
            diameter=diameter,
            r=r,
            d=d,
            tag=tag,
        )

    def corner_profile(
        self,
        corners: Anchor = Anchor.ALL,
        except_corners: list[Anchor] | None = None,
        radius: float | None = None,
        diameter: float | None = None,
        children: Sequence[Sequence[float]] | None = None,
        convexity: int = 10,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
        bbox: Sequence[Sequence[float]] | None = None,
        r: float | None = None,
        d: float | None = None,
        tag: AttachTag | str | None = None,
    ) -> "Bosl2Solid":
        """Cut a 2-D mask profile along each selected corner of this box-shaped solid.

        Args:
            corners:        corners to mask (default ``"ALL"``)
            except_corners: corners to explicitly not mask
            radius:         rounding radius
            diameter:       rounding diameter
            children:       the 2-D mask cross-section path
            convexity:      accepted for compatibility; unused
            fn:       arc smoothness overrides
            fa:       arc smoothness overrides
            fs:       arc smoothness overrides
            bbox:           override bounding box (see :meth:`_resolve_bounds`)
            r:              rounding radius alias
            d:              rounding diameter alias
            tag:            override tag for attachment (defaults to AttachTag.KEEP if negative, else AttachTag.REMOVE)

        """
        from pybosl2 import masking

        center, size = self._resolve_bounds(bbox)
        rad = radius if radius is not None else r
        dia = diameter if diameter is not None else d

        clean_rad = abs(rad) if rad is not None else None
        clean_dia = abs(dia) if dia is not None else None

        cutter_shape = masking.corner_profile(
            self.shape,
            corners,
            except_corners,
            clean_rad,
            clean_dia,
            size=(size[0], size[1], size[2]),
            children=(
                None
                if children is None
                else (Path2D(children, closed=False) if not isinstance(children, Path2D) else children)
            ),
            convexity=convexity,
            center=Point(center[0], center[1], center[2]) if center is not None else None,
            fn=fn,
            fa=fa,
            fs=fs,
            return_cutter=True,
        )
        if cutter_shape is None:
            return self._wrap(self.shape)

        t: AttachTag | str
        if tag is None:
            resolved_rad = rad if rad is not None else (dia / 2 if dia is not None else None)
            t = AttachTag.KEEP if (resolved_rad is not None and resolved_rad < 0) else AttachTag.REMOVE
        else:
            t = tag

        out = self._wrap(self.shape)
        out.attachments = list(self.attachments)
        out.attachments.append(Bosl2Solid(unwrap(cutter_shape)).tag(t))
        if t == AttachTag.REMOVE:
            out.diff_config = {"type": "diff", "remove": ["remove"], "keep": ["keep"]}
        return out

    def face_profile(
        self,
        faces: Anchor | list[Anchor] = Anchor.ALL,
        radius: float | None = None,
        diameter: float | None = None,
        children: Sequence[Sequence[float]] | None = None,
        convexity: int = 10,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
        bbox: Sequence[Sequence[float]] | None = None,
        r: float | None = None,
        d: float | None = None,
        tag: AttachTag | str | None = None,
    ) -> "Bosl2Solid":
        """Cut a face profile into the solid's faces."""
        from pybosl2 import masking

        center, size = self._resolve_bounds(bbox)
        rad = radius if radius is not None else r
        dia = diameter if diameter is not None else d

        clean_rad = abs(rad) if rad is not None else None
        clean_dia = abs(dia) if dia is not None else None

        cutter_shape = masking.face_profile(
            self.shape,
            faces,
            clean_rad,
            clean_dia,
            size=(size[0], size[1], size[2]),
            children=(
                None
                if children is None
                else (Path2D(children, closed=False) if not isinstance(children, Path2D) else children)
            ),
            convexity=convexity,
            center=Point(center[0], center[1], center[2]) if center is not None else None,
            fn=fn,
            fa=fa,
            fs=fs,
            return_cutter=True,
        )
        if cutter_shape is None:
            return self._wrap(self.shape)

        t: AttachTag | str
        if tag is None:
            resolved_rad = rad if rad is not None else (dia / 2 if dia is not None else None)
            t = AttachTag.KEEP if (resolved_rad is not None and resolved_rad < 0) else AttachTag.REMOVE
        else:
            t = tag

        out = self._wrap(self.shape)
        out.attachments = list(self.attachments)
        out.attachments.append(Bosl2Solid(unwrap(cutter_shape)).tag(t))
        if t == AttachTag.REMOVE:
            out.diff_config = {"type": "diff", "remove": ["remove"], "keep": ["keep"]}
        return out

    # ---- miscellaneous operators (from pybosl2/miscellaneous.py) ----

    def bounding_box(self, excess: float = 0) -> "Bosl2Solid":
        """Return the smallest axis-aligned cuboid containing this solid, grown by *excess*.

        Uses the native bounding box, so it is exact and fast.
        """
        from pybosl2.shapes3d.cuboid import cuboid

        center, size = self.bounds()
        return cuboid([size[i] + 2 * excess for i in range(3)]).translate([float(c) for c in center])

    def offset3d(self, radius: float, size: float = 1000, convexity: int = 10) -> "Bosl2Solid":
        """Expand (or, for negative *radius*, contract) the surface of this solid by *radius*.

        Uses ``minkowski()`` with a sphere and is *very* slow; use sparingly.
        """
        _ = convexity
        from pythonscad import cube as _cube
        from pythonscad import minkowski as _mink
        from pythonscad import sphere as _sphere

        if radius == 0:
            return self
        sides = max(8, _frag_count(abs(radius)))
        sides = int(math.ceil(sides / 4) * 4)
        if radius > 0:
            return self._wrap(_mink(self.shape, _sphere(radius, fn=sides)))
        big1 = _cube([size * 1.02] * 3, center=True)
        big2 = _cube([size] * 3, center=True)
        return self._wrap(big2 - _mink(big1 - self.shape, _sphere(-radius, fn=sides)))

    def round3d(
        self,
        radius: float | None = None,
        outer_radius: float | None = None,
        inner_radius: float | None = None,
        size: float = 1000,
    ) -> "Bosl2Solid":
        """Round the corners of this solid: *radius* rounds all,.

        *outer_radius* only convex, *inner_radius* only concave. Uses
        ``offset3d`` three times and is extremely slow.
        """
        orr = outer_radius if outer_radius is not None else (radius if radius is not None else 0)
        irr = inner_radius if inner_radius is not None else (radius if radius is not None else 0)
        return self.offset3d(orr, size=size).offset3d(-irr - orr, size=size).offset3d(irr, size=size)

    def chain_hull(self, *others: object) -> "Bosl2Solid":
        """Return this solid chain-hulled with *others*, in order."""
        from pybosl2.miscellaneous import chain_hull as _chain_hull

        return _chain_hull(self, *others)

    def minkowski_difference(self, *diffs: object, size: float = 1000) -> "Bosl2Solid":
        """Carve *diffs* out of this solid's surface."""
        from pybosl2.miscellaneous import minkowski_difference as _minkowski_difference

        return _minkowski_difference(self, *diffs, size=size)

    # ---- partition / planar cut operators (from pybosl2/partitions.py) ----

    def _half_mask(
        self,
        v: Any,
        cpv: Any,
        s: float,
        cut_path: "Sequence[Sequence[float]] | Path2D | None",
        cut_angle: float,
        offset: float,
    ) -> Any:
        from pythonscad import polygon as _polygon

        from pybosl2._helpers import unit as _unit_vec
        from pybosl2.transforms import axis_angle_matrix
        from pybosl2.transforms import rot_from_to as _rot_from_to_fn

        v3 = np.asarray(v, dtype=float)
        if v3.shape[0] == 2:
            v3 = np.array([v3[0], v3[1], 0.0])
        vu = _unit_vec(v3)
        if cut_path is None:
            ppath = [[-s / 2, 0.0], [s / 2, 0.0]]
        else:
            ppath = [[float(a), float(b)] for a, b in cut_path]
            if ppath[0][0] > ppath[-1][0]:
                ppath = ppath[::-1]
        poly_pts = (
            [[min(-s / 2, ppath[0][0]), s]]
            + [[min(-s / 2, ppath[0][0]), ppath[0][1]]]
            + ppath
            + [[max(s / 2, ppath[-1][0]), ppath[-1][1]]]
            + [[max(s / 2, ppath[-1][0]), s]]
        )
        poly = _polygon([[float(x), float(y)] for x, y in poly_pts])
        if offset:
            poly = poly.offset(radius=offset)
        mask = poly.linear_extrude(height=s, center=True)
        if bool(np.allclose(vu, UP.vector)):
            xyv = np.asarray(FRONT.vector, dtype=float)
        elif bool(np.allclose(vu, DOWN.vector)):
            xyv = np.asarray(BACK.vector, dtype=float)
        else:
            xyv = np.array([v3[0], v3[1], 0.0])
        angle = math.degrees(math.atan2(xyv[1], xyv[0])) - 90
        rtf_angle, rtf_axis = _rot_from_to_fn(xyv, v3)
        m_rot = np.eye(4)
        m_rot[:3, :3] = axis_angle_matrix(rtf_angle, rtf_axis)
        cut_m = np.eye(4)
        cut_m[:3, :3] = axis_angle_matrix(cut_angle, v3)
        zrot_m = np.eye(4)
        zrot_m[:3, :3] = axis_angle_matrix(angle, [0, 0, 1])
        m = (cut_m @ m_rot @ zrot_m).tolist()
        mask = mask.multmatrix(m)
        if not np.allclose(cpv, 0):
            mask = mask.translate([float(c) for c in cpv])
        return mask

    def half_of(
        self,
        v: Any = UP,
        center: bool | list[float] | None = None,
        s: float | None = None,
        cut_path: "Path2D | None" = None,
        cut_angle: float = 0,
        offset: float = 0,
    ) -> "Bosl2Solid":
        """Keep the half of this solid on the side the normal *v* points to.

        *center* is a point on the cut plane, or a scalar distance to shift the plane along *v*. *s*
        (the mask size) defaults to twice the object's bounding-box reach, so it rarely needs
        setting. *cut_path* follows a 2-D :func:`~pybosl2.partitions.partition_path` for an
        interlocking cut face; *cut_angle* spins that face about *v*; *offset* grows the mask.

        Examples:
            Cut a cube in half along a jigsaw pattern:

        .. pythonscad-example::

            from pybosl2.solid import cuboid
            from pybosl2 import partition_path, UP

            path = partition_path(["finger", "10x15", "finger"], seglen=25)
            cuboid([60, 60, 20]).half_of(v=UP, cut_path=path).show()

        """
        v3 = np.asarray(v, dtype=float)
        if v3.shape[0] == 2:
            v3 = np.array([v3[0], v3[1], 0.0])
        vu = unit(v3)
        if center is None:
            cpv = np.zeros(3)
        elif isinstance(center, (int, float, np.integer, np.floating)) and not isinstance(center, bool):
            cpv = float(center) * vu
        else:
            cpv = np.asarray(center, dtype=float)
        if s is None:
            center_pt, size = self.bounds()
            reach = float(np.linalg.norm(size)) + float(np.linalg.norm(cpv - np.asarray(center_pt)))
            s = 2.2 * reach + 2.0
        return self._wrap(self.shape & self._half_mask(v3, cpv, s, cut_path, cut_angle, offset))

    def left_half(
        self,
        x: float = 0,
        s: float | None = None,
        cut_path: "Path2D | None" = None,
        cut_angle: float = 0,
        offset: float = 0,
    ) -> "Bosl2Solid":
        """Return the left half of the solid."""
        return self.half_of(LEFT, center=[x, 0, 0], s=s, cut_path=cut_path, cut_angle=cut_angle, offset=offset)

    def right_half(
        self,
        x: float = 0,
        s: float | None = None,
        cut_path: "Path2D | None" = None,
        cut_angle: float = 0,
        offset: float = 0,
    ) -> "Bosl2Solid":
        """Return the right half of the solid."""
        return self.half_of(RIGHT, center=[x, 0, 0], s=s, cut_path=cut_path, cut_angle=cut_angle, offset=offset)

    def front_half(
        self,
        y: float = 0,
        s: float | None = None,
        cut_path: "Path2D | None" = None,
        cut_angle: float = 0,
        offset: float = 0,
    ) -> "Bosl2Solid":
        """Return the front half of the solid."""
        return self.half_of(FRONT, center=[0, y, 0], s=s, cut_path=cut_path, cut_angle=cut_angle, offset=offset)

    def back_half(
        self,
        y: float = 0,
        s: float | None = None,
        cut_path: "Path2D | None" = None,
        cut_angle: float = 0,
        offset: float = 0,
    ) -> "Bosl2Solid":
        """Return the back half of the solid."""
        return self.half_of(BACK, center=[0, y, 0], s=s, cut_path=cut_path, cut_angle=cut_angle, offset=offset)

    def bottom_half(
        self,
        z: float = 0,
        s: float | None = None,
        cut_path: "Path2D | None" = None,
        cut_angle: float = 0,
        offset: float = 0,
    ) -> "Bosl2Solid":
        """Return the bottom half of the solid."""
        return self.half_of(DOWN, center=[0, 0, z], s=s, cut_path=cut_path, cut_angle=cut_angle, offset=offset)

    def top_half(
        self,
        z: float = 0,
        s: float | None = None,
        cut_path: "Path2D | None" = None,
        cut_angle: float = 0,
        offset: float = 0,
    ) -> "Bosl2Solid":
        """Return the top half of the solid."""
        return self.half_of(UP, center=[0, 0, z], s=s, cut_path=cut_path, cut_angle=cut_angle, offset=offset)

    def partition(
        self,
        spread: float = 10,
        cutsize: float | Sequence[float] = 10,
        cutpath: str | "Path2D" = "jigsaw",
        gap: float = 0,
        cutpath_centered: bool = True,
        spin: float = 0,
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "list[Bosl2Solid]":
        """Cut this solid into two interlocking pieces, spread apart.

        Returns ``[back_piece, front_piece]`` -- the two halves with matched joining edges, moved
        *spread* apart along the (spun) Y axis so they print separately and snap back together.
        The joint follows *cutpath* (``"jigsaw"``, ``"dovetail"``, ``"hammerhead"``, ...); *spin*
        rotates the cut direction; *slop* leaves a printer-fit clearance.

        Examples:
            Split a block into two dovetailed halves:

        .. pythonscad-example::

            from pybosl2.solid import cuboid

            halves = cuboid([60, 60, 20]).partition(spread=15, cutpath="dovetail", slop=0.15)
            halves[0].show()

        """
        from pybosl2.partitions import _partition_mask_shape

        center_pt, size = self.bounds()
        cs: list[float] = list(cutsize) if isinstance(cutsize, (list, tuple, np.ndarray)) else [cutsize * 2, cutsize]  # type: ignore[operator, list-item]
        sp = math.radians(spin)
        c, sn = math.cos(sp), math.sin(sp)
        rsx = abs(size[0] * c - size[1] * sn)
        rsy = abs(size[0] * sn + size[1] * c)
        rsz = abs(size[2])
        vec = np.array([-sn, c, 0.0]) * (spread / 2)
        pieces: list[Bosl2Solid] = []
        for idx, inverse in ((0, False), (1, True)):
            mask = _partition_mask_shape(
                rsx,
                rsy,
                rsz,
                cs,
                cutpath,
                gap,
                cutpath_centered,
                inverse,
                slop,
                fn,
                fa,
                fs,
            )
            mask = mask.rotate([0, 0, spin]).translate([float(c2) for c2 in center_pt])
            move = vec if idx == 0 else -vec
            pieces.append(self._wrap(self.shape & mask).translate([float(m) for m in move]))
        return pieces


# ---------------------------------------------------------------------------
# Internal helpers (not part of BOSL2's public API)
# ---------------------------------------------------------------------------


def _anchor_to_vector(a: Anchor | Sequence[float]) -> Point:
    """Convert an Anchor or vector-like to a :class:`Point`."""
    if isinstance(a, Anchor):
        return a.vector
    if isinstance(a, Point):
        return a
    return Point(a)


def _orient_rotate(shape: PyOpenSCAD, orient: Anchor | Sequence[float]) -> PyOpenSCAD:
    o = orient.vector if isinstance(orient, Anchor) else list(orient)
    if o == [0, 0, 1]:
        return shape
    if o == [0, 0, -1]:
        return shape.rotate(180, [1, 0, 0])
    axis = np.asarray(np.cross([0, 0, 1], o), dtype=float)
    sides = float(np.linalg.norm(axis))
    if sides < 1e-12:
        return shape
    axis = (axis / sides).tolist()
    ou = unit(o)
    cosang = max(-1.0, min(1.0, ou[2]))
    angle = math.degrees(math.acos(cosang))
    return shape.rotate(angle, axis)


def _rot_from_to(a: Sequence[float], b: Sequence[float]) -> "tuple[float, list[float]]":
    """Return (angle_degrees, axis) that rotates direction *a* onto direction *b*, for shape.rotate().

    Handles the parallel (no rotation) and antiparallel (180 deg about any perpendicular axis)
    cases. Used by Bosl2Solid.attach() to point a child's mating face at a parent face.
    """
    au, bu = unit(a), unit(b)
    diameter = max(-1.0, min(1.0, sum(au[i] * bu[i] for i in range(3))))
    if diameter > 1 - 1e-9:
        return 0.0, [0.0, 0.0, 1.0]
    if diameter < -1 + 1e-9:
        perp = np.cross(au, [1.0, 0.0, 0.0])
        if float(np.linalg.norm(np.asarray(perp, dtype=float))) < 1e-9:
            perp = np.cross(au, [0.0, 1.0, 0.0])
        perp_u = unit(perp)
        return 180.0, [float(perp_u[0]), float(perp_u[1]), float(perp_u[2])]
    axis_u = unit(np.cross(au, bu))
    axis: list[float] = [float(axis_u[0]), float(axis_u[1]), float(axis_u[2])]
    return math.degrees(math.acos(diameter)), axis


def _resolve_center_anchor(
    center: bool | None,
    anchor: "Anchor | Sequence[float]",
    default_if_false: "Anchor | Sequence[float]",
) -> "Anchor | Sequence[float]":
    """Normalize center= to an anchor value.

    Args:
        center: If True, returns CENTER; if False, returns *default_if_false*.
        anchor: The anchor to return when *center* is None.
        default_if_false: The anchor to use when center=False.

    Returns:
        The resolved anchor.

    """
    if center is not None:
        return Anchor.CENTER if center else default_if_false
    return anchor


def _finish3(
    shape: PyOpenSCAD,
    offset: Sequence[float],
    spin: float,
    orient: Anchor | Sequence[float],
    size: Sequence[float] | None = None,
    anchor: Anchor | Sequence[float] | None = None,
) -> Bosl2Solid:
    """Build, offset, spin, orient, and wrap in Bosl2Solid.

    Args:
        shape: The native geometry just built (centred at origin).
        offset: [x, y, z] anchor offset to apply.
        spin: Z-axis rotation in degrees.
        orient: Direction to rotate the top towards.
        size: Nominal [x, y, z] box size for the wrapper metadata.
        anchor: Anchor value for the wrapper metadata.

    Returns:
        A Bosl2Solid wrapping the finished geometry.

    """
    if offset[0] or offset[1] or offset[2]:
        shape = shape.translate(offset)
    if spin:
        shape = shape.rotate(spin, [0, 0, 1])
    shape = _orient_rotate(shape, orient)
    return Bosl2Solid(shape, size=size, anchor=anchor)


def _anchor_offset_box3(size: Sequence[float], anchor: Anchor | Sequence[float]) -> list[float]:
    a = anchor.vector if isinstance(anchor, Anchor) else list(anchor)
    return [-a[i] * size[i] / 2 for i in range(3)]


def _anchor_offset_hull3(points: Sequence[Sequence[float]], anchor: Anchor | Sequence[float]) -> list[float]:
    a = anchor.vector if isinstance(anchor, Anchor) else list(anchor)
    if a[0] == 0 and a[1] == 0 and a[2] == 0:
        return [0.0, 0.0, 0.0]
    # The anchor point is the support point of the hull in direction `anchor`. When several vertices
    # tie for the maximum projection (a whole face for a face anchor, two vertices for an edge
    # anchor), the anchor is their centroid -- the face/edge centre -- not an arbitrary tied corner.
    projs = [p[0] * a[0] + p[1] * a[1] + p[2] * a[2] for p in points]
    m = max(projs)
    eps = 1e-7 * (1.0 + abs(m))
    tied = [p for p, pr in zip(points, projs, strict=False) if pr >= m - eps]
    sides = len(tied)
    return [-sum(p[i] for p in tied) / sides for i in range(3)]


def _anchor_offset_cyl(
    radius1: float,
    radius2: float,
    length: float,
    anchor: Anchor | Sequence[float],
    axis: int = 2,
) -> list[float]:
    a = anchor.vector if isinstance(anchor, Anchor) else list(anchor)
    az = a[axis]
    r_at = radius1 if az < 0 else (radius2 if az > 0 else (radius1 + radius2) / 2)
    radial_axes = [i for i in range(3) if i != axis]
    radial = [a[i] for i in radial_axes]
    rn = math.hypot(*radial)
    if rn > 0:
        radial = [x / rn * r_at for x in radial]
    offset = [0.0, 0.0, 0.0]
    offset[axis] = az * length / 2
    for i, ax in enumerate(radial_axes):
        offset[ax] = radial[i]
    return [-x for x in offset]


Bosl2Solid = CsgSolid

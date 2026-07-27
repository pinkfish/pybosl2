# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/shapes3d.py
#    Every shape in this file (cube, cuboid, prismoid, octahedron, wedge, cylinder, cyl, xcyl,
#    ycyl, zcyl, sphere, spheroid, rect_tube, tube, pie_slice, torus, teardrop, onion, text3d,
#    path_text, interior_fillet, heightfield, cylindrical_heightfield, ruler) is a pure-Python
#    port with no osuse()/BOSL2 runtime dependency at all: each shape is built directly from
#    openscad primitives (cube()/cylinder()/sphere()/polyhedron()/hull()/minkowski()/
#    rotate_extrude()/linear_extrude()/text()) rather than delegating to BOSL2. cuboid()'s edge
#    rounding/chamfering mirrors BOSL2's own algorithm, which is itself CSG composition (union/
#    intersection/difference/hull of primitive shapes at each corner), not raw polyhedron mesh
#    math -- see BOSL2's shapes3d.scad module cuboid() for the reference algorithm this was
#    ported from. heightfield()/cylindrical_heightfield() build their mesh directly via
#    polyhedron() from a computed vertex/face grid (see _heightfield_polyhedron()).
#
# FileSummary: Attachable cubes, cylinders, spheres, text and rulers (BOSL2 shapes3d.scad).
# FileGroup: BOSL2

from __future__ import annotations

import math
import numbers
from typing import TYPE_CHECKING

import numpy as np

from pybosl2._native import native

if TYPE_CHECKING:
    from collections.abc import Sequence

    from openscad import PyOpenSCAD

    from pybosl2.shapes2d import Bosl2Shape2D
    from pybosl2.texture import TextureType
from pybosl2._backend import check_operand_backend as _check_operand_backend
from pybosl2._backend import unsupported_feature as _unsupported_feature
from pybosl2.color import Colorable
from pybosl2.distributors import Distributable
from pybosl2.geometry import cross
from pybosl2.miscellaneous import Miscellaneous
from pybosl2.partitions import Partitionable
from pybosl2.paths import Path
from pybosl2.vectors import is_vector, unit

from .constants import BOTTOM, CENTER, DOWN, FRONT, LEFT, UP
from .shapes2d import _frag_count, _pick_radius
from .shapes2d import text as _text2d

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
    height=None,
    radius=None,
    radius1=None,
    radius2=None,
    center=None,
    fn=None,
    fa=None,
    fs=None,
):
    """The native cylinder, accepting this file's full-word kwargs (native wants h/r/radius1/radius2)."""
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


def _osphere(radius=None, center=None, fn=None, fa=None, fs=None):
    """The native sphere, accepting this file's full-word kwargs (native wants r)."""
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


def _as_native_3d(obj) -> "PyOpenSCAD":
    """A raw native handle from *obj*: a :class:`Bosl2Solid` / ``Bosl2Shape2D`` wrapper, a native
    shape, or anything exposing ``geometry()`` (a :class:`~pybosl2.vnf.VNF`, a
    :class:`~pybosl2.paths.Path`, a :class:`~pybosl2.regions.Region`)."""
    from pybosl2._helpers import unwrap

    unwrapped = unwrap(obj)
    if unwrapped is not obj:  # a Bosl2Solid / Bosl2Shape2D wrapper
        return unwrapped
    geom = getattr(obj, "geometry", None)  # VNF / Path / Region
    if callable(geom):
        return unwrap(geom())
    return obj


# ---------------------------------------------------------------------------
# Section: Base class
# ---------------------------------------------------------------------------


class Bosl2Solid(Distributable, Colorable, Partitionable, Miscellaneous):
    """Wraps a PyOpenSCAD solid together with the geometry metadata (nominal `size` and
    `anchor`) that BOSL2's $parent_geom attachment system would otherwise track, so that
    edge/corner/face masking (pybosl2/masking.py) work as plain chained methods instead of
    needing size=/anchor= threaded through by hand at every call site. Every function in this
    file returns an instance of this class (or a subclass).

    Every geometry method (translate/rotate/mirror/multmatrix/scale/color, the union/intersection/
    difference CSG operators) delegates to the wrapped native shape and returns a new Bosl2Solid carrying the
    same size/anchor metadata forward. Any other method not explicitly listed here (e.g.
    resize(), offset()) falls through via __getattr__ to the native shape and returns its raw,
    *unwrapped* result, since we can't know whether the size/anchor metadata still applies.

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
    """

    #: which realize backend produced this solid -- see pybosl2/_backend.py. Bosl2Solid is the
    #: exact-CSG (PythonSCAD) backend's Solid; the libfive/SDF backend uses its own wrapper.
    backend = "csg"

    def __init__(
        self,
        shape: PyOpenSCAD,
        size: Sequence[float] | None = None,
        anchor: "Sequence[float] | str | None" = None,
    ):
        self.shape = shape
        self.size = size
        self.anchor = anchor if anchor is not None else CENTER
        # True once a positional transform (translate/rotate/scale/...) has been applied, so the
        # tracked cuboid size/anchor metadata no longer describes the object's current position.
        self._moved = False

    @staticmethod
    def _unwrap(x):
        from pybosl2._helpers import unwrap

        return unwrap(x)

    def _wrap(self, new_shape: PyOpenSCAD) -> "Bosl2Solid":
        """Wrap a native result, carrying size/anchor metadata (and moved-ness) forward unchanged.

        Use for ops that do NOT move/resize the geometry (colour, repair, native mesh ops)."""
        out = Bosl2Solid(new_shape, self.size, self.anchor)
        out._moved = self._moved
        return out

    def _wrap_moved(self, new_shape: PyOpenSCAD) -> "Bosl2Solid":
        """Wrap a native result of a positional transform, flagging the tracked metadata stale."""
        out = Bosl2Solid(new_shape, self.size, self.anchor)
        out._moved = True
        return out

    def __getattr__(self, name):
        # __getattr__ only fires on a normal-lookup miss. Guard the recursion trap: never bounce
        # back through here for `shape` (or dunders) when the object is half-built (unpickling,
        # __new__, or an __init__ that raised before setting .shape) -- raise a clean AttributeError
        # so copy/pickle/hasattr behave instead of blowing the stack.
        if name == "shape" or (name.startswith("__") and name.endswith("__")):
            raise AttributeError(name)
        _unsupported = _unsupported_feature("csg", name)  # SDF-only feature on the CSG backend?
        if _unsupported is not None:
            raise _unsupported
        shape = object.__getattribute__(self, "shape")  # bypass __getattr__: no recursion
        attr = getattr(shape, name)
        if not callable(attr):
            return attr  # plain native attr (.position/.size/...)
        native_cls = type(shape)

        def _forward(*args, **kwargs):
            # Re-wrap native geometry so a passed-through op (linear_extrude/offset/resize/...) keeps
            # the Bosl2Solid fluent API instead of silently leaking a raw handle. The result may be
            # in a different position, so treat it as moved. Non-geometry results pass through.
            result = attr(*args, **kwargs)
            if isinstance(result, native_cls):
                return self._wrap_moved(result)
            if isinstance(result, (list, tuple)) and result and all(isinstance(r, native_cls) for r in result):
                return type(result)(self._wrap_moved(r) for r in result)
            return result

        _forward.__name__ = name
        return _forward

    def __repr__(self) -> str:
        return f"Bosl2Solid({self.shape!r}, size={self.size!r}, anchor={self.anchor!r})"

    # ---- geometry passthrough, preserving size/anchor metadata ----

    def translate(self, v: Sequence[float]) -> "Bosl2Solid":
        return self._wrap_moved(self.shape.translate(v))

    move = translate

    def rotate(self, *a, **k) -> "Bosl2Solid":
        # BOSL2 rot(a): a bare scalar angle is a rotation about the Z axis. The native openscad
        # rotate() only accepts a vector or (angle, axis), so normalize here. Accept any real
        # scalar (incl. numpy int/float scalars) but not bool (a subclass of int).
        if len(a) == 1 and isinstance(a[0], numbers.Real) and not isinstance(a[0], bool) and "v" not in k:
            a = ([0.0, 0.0, float(a[0])],)
        return self._wrap_moved(self.shape.rotate(*a, **k))

    rot = rotate

    def mirror(self, v: Sequence[float]) -> "Bosl2Solid":
        return self._wrap_moved(self.shape.mirror(v))

    # Directional translates (BOSL2 transforms.scad): right/left +/-X, back/fwd +/-Y, up/down +/-Z.

    def right(self, x: float) -> "Bosl2Solid":
        return self.translate([x, 0.0, 0.0])

    def left(self, x: float) -> "Bosl2Solid":
        return self.translate([-x, 0.0, 0.0])

    def back(self, y: float) -> "Bosl2Solid":
        return self.translate([0.0, y, 0.0])

    def forward(self, y: float) -> "Bosl2Solid":
        return self.translate([0.0, -y, 0.0])

    fwd = forward

    def up(self, z: float) -> "Bosl2Solid":
        return self.translate([0.0, 0.0, z])

    def down(self, z: float) -> "Bosl2Solid":
        return self.translate([0.0, 0.0, -z])

    def multmatrix(self, m: Sequence[Sequence[float]]) -> "Bosl2Solid":
        return self._wrap_moved(self.shape.multmatrix(m))

    def scale(self, v) -> "Bosl2Solid":
        return self._wrap_moved(self.shape.scale(v))

    # ---- native-only mesh operations (no BOSL2 equivalent) ----
    #
    # PythonSCAD provides several solid operations that BOSL2 has no counterpart for; they are
    # exposed here as first-class Bosl2Solid methods (re-wrapping the native result so anchoring
    # metadata and fluent chaining survive) rather than leaking raw native handles through
    # __getattr__. These execute only inside the real PythonSCAD app; under the numeric test mock
    # they degrade to identity/AABB stand-ins (see mock_libfive.py), so the fast suite still runs
    # and their real geometry is covered by the STL render tests.

    def repair(self) -> "Bosl2Solid":
        """Force the mesh watertight, healing gaps/non-manifold edges (native ``repair()``)."""
        return self._wrap(self.shape.repair())

    def wrap(self, radius: float, fn: int | None = None) -> "Bosl2Solid":
        """Wrap this solid around a cylinder of radius *radius*, bending +X into the cylinder's
        circumference (native ``wrap()``). *fn* sets the facet count of the bend."""
        if fn is not None:
            return self._wrap(self.shape.wrap(r=float(radius), fn=float(fn)))
        return self._wrap(self.shape.wrap(r=float(radius)))

    def pull(self, direction: "Sequence[float] | np.ndarray", distance: float) -> "Bosl2Solid":
        """Pull the part of the solid on the +*direction* side apart by *distance*, stretching the
        material between (native ``pull()``)."""
        return self._wrap(self.shape.pull([float(x) for x in direction], float(distance)))

    def oversample(self, sides: int) -> "Bosl2Solid":
        """Subdivide every mesh facet *sides*-fold, e.g. before :meth:`wrap` so the bend is smooth
        (native ``oversample()``)."""
        return self._wrap(self.shape.oversample(int(sides)))

    def separate(self) -> "list[Bosl2Solid]":
        """Split a solid made of disconnected lumps into a list of its connected components
        (native ``separate()``)."""
        return [self._wrap(part) for part in self.shape.separate()]

    def inside(self, point: "Sequence[float] | np.ndarray") -> bool:
        """True if *point* lies inside the solid (native ``inside()``)."""
        return bool(self.shape.inside([float(x) for x in point]))

    # ---- hull / projection ----

    def hull(self, *others) -> "Bosl2Solid":
        """The convex hull of this solid (OpenSCAD ``hull()``).

        With arguments, the hull of this solid *together with* each of *others* -- the shrink-wrap
        around them all, which is how BOSL2 builds a rounded box from spheres at its corners.
        Each of *others* may be a ``Bosl2Solid``, a raw native solid, or a
        :class:`~pybosl2.vnf.VNF`/point list, which is meshed as a polyhedron first.

        See :meth:`~pybosl2.miscellaneous.Miscellaneous.chain_hull` to hull consecutive *pairs*
        instead of everything at once.

        Examples:
            .. pythonscad-example::

                capsule = s3.sphere(radius=8).hull(s3.sphere(radius=8).up(30))
                capsule.show()
        """
        return Bosl2Solid(_ohull(self.shape, *[_as_native_3d(o) for o in others]))

    def projection(self, cut: bool = False) -> "Bosl2Shape2D":
        """The 2-D shadow of this solid on the XY plane (OpenSCAD ``projection()``).

        With ``cut=True`` you get the cross-section where the solid crosses the z=0 plane instead
        of the full outline -- slice the solid at the height you want first.

        Returns:
            A :class:`~pybosl2.shapes2d.Bosl2Shape2D`, so the result chains straight back into the
            2-D operators (``.offset()``, ``.fill()``, ``.hull()``) and the extruders.

        Note:
            CSG only. The SDF backend's :meth:`~pybosl2._sdf.shapes3d.PyShape.projection` raises
            :class:`~pybosl2.exceptions.UnsupportedByBackend` -- a distance field has no
            closed-form 2-D shadow, and 2-D geometry is a CSG-backend notion.

        Examples:
            A footprint outline, grown 2mm, extruded into a base plate:

            .. pythonscad-example::

                part = s3.cuboid([30, 20, 10], rounding=3)
                part.projection().offset(radius=2).linear_extrude(height=2).show()
        """
        from pybosl2.shapes2d import Bosl2Shape2D

        return Bosl2Shape2D(self.shape.projection(cut=cut))

    # ---- colour (pybosl2/color.py) ----
    #
    # The color.scad operators (color/recolor/color_this/hsl/hsv/highlight/ghost) come from the
    # Colorable mixin, which resolves to these native primitives: PythonSCAD's color(),
    # highlight() (the # modifier) and background() (the % / ghost modifier).

    def _color_native(self, c=None, alpha=None) -> "Bosl2Solid":
        args = () if c is None else (c,)
        kw = {} if alpha is None else {"alpha": alpha}
        return self._wrap(self.shape.color(*args, **kw))

    def _highlight_native(self) -> "Bosl2Solid":
        return self._wrap(self.shape.highlight())

    def _ghost_native(self) -> "Bosl2Solid":
        return self._wrap(self.shape.background())

    def to_csg(self) -> "Bosl2Solid":
        """This solid is already on the CSG backend -- returns self (the converter no-op)."""
        return self

    def to_sdf(self) -> "Bosl2Solid":
        """CSG -> SDF conversion is not supported (would require lossy voxel-sampling)."""
        from pybosl2.exceptions import UnsupportedByBackend

        raise UnsupportedByBackend(
            "to_sdf",
            "csg",
            hint="a CSG tree has no signed-distance field; build the shape on the SDF backend "
            "instead (with use_backend('sdf')). Only SDF->CSG (PyShape.to_csg()) is supported.",
        )

    def __or__(self, other) -> "Bosl2Solid":
        _check_operand_backend("csg", other)
        return self._wrap(self.shape | Bosl2Solid._unwrap(other))

    def __and__(self, other) -> "Bosl2Solid":
        _check_operand_backend("csg", other)
        return self._wrap(self.shape & Bosl2Solid._unwrap(other))

    def __sub__(self, other) -> "Bosl2Solid":
        _check_operand_backend("csg", other)
        return self._wrap(self.shape - Bosl2Solid._unwrap(other))

    def __ror__(self, other) -> "Bosl2Solid":
        _check_operand_backend("csg", other)
        return self._wrap(Bosl2Solid._unwrap(other) | self.shape)

    def __rand__(self, other) -> "Bosl2Solid":
        _check_operand_backend("csg", other)
        return self._wrap(Bosl2Solid._unwrap(other) & self.shape)

    def __rsub__(self, other) -> "Bosl2Solid":
        _check_operand_backend("csg", other)
        return self._wrap(Bosl2Solid._unwrap(other) - self.shape)

    # ---- distributors (pybosl2/distributors.py) ----
    #
    # The distributors.scad copiers, inherited from Distributable, resolve to _distribute(), which
    # for a solid means: multmatrix a copy for each transform and union them into one new solid.
    # This reuses the wrapped native handle across the copies, which is safe for direct-CSG solids
    # (the norm here); a pysolidfive/frep-backed shape must instead be distributed via a factory to
    # avoid the frep handle-reuse segfault (see the SDF-vs-direct note in CLAUDE.md).

    def _distribute(self, mats) -> "Bosl2Solid":
        """Union a multmatrix copy of this solid for each transform matrix (BOSL2's module form)."""
        assert len(mats), "distributor produced no copies."
        out = self.shape.multmatrix(np.asarray(mats[0]).tolist())
        for m in mats[1:]:
            out = out | self.shape.multmatrix(np.asarray(m).tolist())
        return self._wrap_moved(out)

    # ---- bounding-box anchoring (works on ANY object, via PythonSCAD's native bbox) ----
    #
    # PythonSCAD exposes obj.position (min corner) / obj.size (extent) / obj.bbox (a solid),
    # each computed by actually meshing the object. That lets anchoring/attachment/masking
    # find where an anchor point is on ANY object without the caller passing a size -- BOSL2
    # normally threads $parent_geom through for this. Tracked cuboid size/anchor metadata,
    # when present, is used first as a no-meshing fast path.

    def _native_bounds(self) -> "tuple[list[float], list[float]] | None":
        """The object's axis-aligned bounding box as (mincorner, size), read from the native
        obj.position/obj.size. Returns None when those accessors aren't available (the numeric
        test mock) or the geometry is empty/degenerate (native returns None)."""
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
        """This object's axis-aligned bounding box as (center, size) -- both plain [x, y, z]
        float lists in the object's CURRENT coordinate frame (after any translate/rotate/CSG).

        Prefers the native bbox, which always reflects the actual current geometry -- this is
        what lets anchoring/attachment/masking work without the caller tracking a size, and
        stays correct after the object has been moved or combined (tracked size/anchor metadata
        would be stale there). Falls back to the tracked cuboid size/anchor metadata only when
        the native accessors aren't available (the numeric test mock), where it assumes the box
        is still at its construction position. Raises if neither is available."""
        nb = self._native_bounds()
        if nb is not None:
            mincorner, size = nb
            return [mincorner[i] + size[i] / 2 for i in range(3)], size
        if self.size is not None and not isinstance(self.anchor, str):
            # Fall back to construction-time cuboid metadata -- but only if the object hasn't been
            # moved since, because that metadata tracks size/anchor, not the current position. Fail
            # loud rather than return a silently-stale centre (this path is the numeric mock only).
            if self._moved:
                raise ValueError(
                    "bounds(): no native bounding box (numeric mock) and the object has been "
                    "transformed since construction, so its tracked cuboid metadata is stale. Run "
                    "under the real PythonSCAD app for a correct bbox, or anchor before transforming."
                )
            size = [float(v) for v in self.size]
            return _anchor_offset_box3(size, self.anchor), size
        raise ValueError(
            "bounds(): object has no native bounding box and no tracked cuboid size/anchor "
            "metadata (are you calling this under the numeric mock on a non-cuboid?)"
        )

    def _resolve_bounds(self, bbox=None) -> "tuple[list[float], list[float]]":
        """(center, size) for anchoring: from a passed-in *bbox* override if given, else the
        object's native bounding box (:meth:`bounds`).

        *bbox* overrides the object's own box -- useful when the native bbox is wrong for the
        purpose (a shape with an overhang, a mask positioned against a nominal box, or a cheap way
        to skip the meshing the native bbox needs). It is a min/max corner pair
        ``[[min_x, min_y, min_z], [max_x, max_y, max_z]]`` (the same shape :meth:`Path.bounds` and
        the native ``obj.bbox`` use)."""
        if bbox is None:
            return self.bounds()
        arr = np.asarray(bbox, dtype=float)
        assert arr.shape == (2, 3), "bbox must be [[min_x,min_y,min_z],[max_x,max_y,max_z]]."
        lo, hi = arr[0], arr[1]
        assert bool(np.all(hi >= lo - 1e-12)), "bbox must be [[min...],[max...]] with max >= min."
        return [(lo[i] + hi[i]) / 2 for i in range(3)], [hi[i] - lo[i] for i in range(3)]

    def anchor_point(self, anchor: Sequence[float], bbox=None) -> list[float]:
        """The [x, y, z] point on this object's bounding box for the given anchor vector, in the
        object's current coordinate frame: center + anchor * size / 2. Works on any object.

        Pass *bbox* to anchor against a supplied box instead of the object's own (see
        :meth:`_resolve_bounds`)."""
        center, size = self._resolve_bounds(bbox)
        a = list(anchor)
        return [center[i] + a[i] * size[i] / 2 for i in range(3)]

    def reanchor(self, anchor: Sequence[float], bbox=None) -> "Bosl2Solid":
        """Return this object translated so its bounding-box `anchor` point sits at the origin.
        Re-anchors any object by its bbox after the fact (cube()/cuboid() only do this at
        construction, and only for cuboids). Pass *bbox* to use a supplied box."""
        p = self.anchor_point(anchor, bbox=bbox)
        moved = self.translate([-p[0], -p[1], -p[2]])
        if moved.size is not None:
            moved.anchor = list(anchor)
        return moved

    def position(self, anchor: Sequence[float], child, bbox=None) -> "Bosl2Solid":
        """BOSL2 position(): place `child` so its local origin lands on this object's
        bounding-box `anchor` point, keeping the child's own orientation, and return self
        unioned with the placed child. `child` may be a Bosl2Solid or a raw native solid."""
        p = self.anchor_point(anchor, bbox=bbox)
        placed = Bosl2Solid._unwrap(child).translate(p)
        # Untracked result: bounds() on it queries the true combined bbox rather than the
        # parent box, so a chained attach/position builds on the combined shape.
        return Bosl2Solid(self.shape | placed)

    def align(
        self,
        anchor: Sequence[float],
        child,
        align: Sequence[float] | None = None,
        inside: bool = False,
        overlap: float = 0.0,
        bbox=None,
    ) -> "Bosl2Solid":
        """BOSL2 align(): place `child` on this object's `anchor` face and return self unioned
        with it. Like attach() it mates a child face to a parent face, but WITHOUT reorienting
        the child -- the child keeps its own axes and is merely translated.

        With `align` omitted the child is centered on the face, sitting OUTSIDE the parent
        (inside=False, the default) or tucked inside (inside=True). Pass `align` (an edge/corner
        direction within the face, e.g. RIGHT for the +x edge) to sit the child flush against
        that edge/corner instead -- matching BOSL2 align()'s anchor+align pair. Both anchor
        points come from the native bounding boxes, so no size needs to be passed.

        Args:
            anchor:  the parent face to place the child on (e.g. TOP)
            child:   the solid to place (Bosl2Solid or raw native solid)
            align:   edge/corner within the face to sit flush against (default: centered)
            inside:  place the child inside the parent instead of outside (default False)
            overlap: pull the child toward the parent along the face normal by this much
        """
        face = list(anchor)
        edge = [0.0, 0.0, 0.0] if align is None else list(align)
        factor = -1.0 if inside else 1.0
        csolid = child if isinstance(child, Bosl2Solid) else Bosl2Solid(child)
        # The child's own mating anchor: its face opposite the parent face (so it sits on the
        # outside), shifted to the aligned edge/corner. Matches BOSL2's thisedge - factor*thisface.
        child_anchor = [edge[i] - factor * face[i] for i in range(3)]
        cpt = csolid.anchor_point(child_anchor)
        dest = self.anchor_point([face[i] + edge[i] for i in range(3)], bbox=bbox)
        fdir = list(unit(face)) if any(face) else [0.0, 0.0, 0.0]
        ov = -overlap if inside else overlap
        placed = csolid.translate([dest[i] - cpt[i] - fdir[i] * ov for i in range(3)])
        return Bosl2Solid(self.shape | placed.shape)

    def attach(
        self,
        parent_anchor: Sequence[float],
        child,
        child_anchor: Sequence[float] | None = None,
        overlap: float = 0.0,
        spin: float = 0.0,
        bbox=None,
    ) -> "Bosl2Solid":
        """BOSL2 attach(): orient and place `child` so its `child_anchor` face mates flush
        against this object's `parent_anchor` face, then return self unioned with the placed
        child. Both anchor points come from the native bounding boxes, so neither object needs
        its size passed explicitly.

        Args:
            parent_anchor: which face of self to attach to (e.g. TOP)
            child:         the solid to attach (Bosl2Solid or raw native solid)
            child_anchor:  which face of the child mates against it (default: the child's
                           face OPPOSITE parent_anchor, so the two mate naturally)
            overlap:       pull the child in by this much along the mating axis (default 0)
            spin:          spin the child about the mating axis, in degrees (default 0)
        """
        pa = list(parent_anchor)
        ca = [-a for a in pa] if child_anchor is None else list(child_anchor)
        csolid = child if isinstance(child, Bosl2Solid) else Bosl2Solid(child)
        # 1. bring the child's mating face to the origin
        cpt = csolid.anchor_point(ca)
        placed = csolid.translate([-cpt[0], -cpt[1], -cpt[2]])
        # 2. rotate so the child's mating-face direction points opposite the parent's face
        angle, axis = _rot_from_to(ca, [-a for a in pa])
        if angle:
            placed = placed.rotate(angle, axis)
        # 3. optional spin about the mating (parent-face) axis
        if spin and any(pa):
            placed = placed.rotate(spin, list(unit(pa)))
        # 4. move onto the parent's anchor point, pulling in by `overlap`
        ppt = self.anchor_point(pa, bbox=bbox)
        pdir = list(unit(pa)) if any(pa) else [0.0, 0.0, 0.0]
        placed = placed.translate([ppt[i] - pdir[i] * overlap for i in range(3)])
        return Bosl2Solid(self.shape | placed.shape)

    def reorient(
        self,
        anchor: Sequence[float] = CENTER,
        spin: float = 0,
        orient: Sequence[float] = UP,
        bbox=None,
    ) -> "Bosl2Solid":
        """Reorient this already-built object by its bounding box (BOSL2 reorient()).

        Moves the bounding-box *anchor* point to the origin, spins *spin* degrees about Z, then
        rotates the object's UP toward *orient*. The size comes from the native bbox, so -- unlike
        BOSL2's function form -- you never pass it. cube()/cuboid()/etc. take anchor/spin/orient at
        construction; this applies the same transform to any object after the fact. Pass *bbox* to
        reorient against a supplied box instead of the object's own."""
        from pybosl2.transforms import reorient as _reorient_matrix

        center, size = self._resolve_bounds(bbox)
        m = _reorient_matrix(anchor=list(anchor), spin=spin, orient=list(orient), size=size)
        centered = self.translate([-center[0], -center[1], -center[2]])
        return centered.multmatrix(np.asarray(m).tolist())

    def orient(self, direction: Sequence[float] = UP, spin: float = 0, bbox=None) -> "Bosl2Solid":
        """Rotate this object so its top (UP) faces *direction* (BOSL2 orient()); uses the bbox."""
        return self.reorient(anchor=CENTER, spin=spin, orient=direction, bbox=bbox)

    # ---- edge/corner/face masking (pybosl2/masking.py), box-shaped objects ----
    #
    # These now work on ANY box-shaped object: the cutter size and box center come from
    # bounds() (tracked metadata when available, else the native bbox), so callers no longer
    # have to pass size= or keep the object as a freshly-built cuboid.

    def edge_mask(
        self,
        edges: str | list = "ALL",
        except_edges: list | None = None,
        children: PyOpenSCAD | None = None,
        bbox=None,
    ) -> "Bosl2Solid":
        from . import masking

        center, size = self._resolve_bounds(bbox)
        return self._wrap(masking.edge_mask(self.shape, edges, except_edges, children, size=size, center=center))

    def edge_profile(
        self,
        edges: str | list = "ALL",
        except_edges: list | None = None,
        children: Sequence[Sequence[float]] | None = None,
        convexity: int = 10,
        bbox=None,
    ) -> "Bosl2Solid":
        from . import masking

        center, size = self._resolve_bounds(bbox)
        return self._wrap(
            masking.edge_profile(
                self.shape,
                edges,
                except_edges,
                children,
                size=size,
                convexity=convexity,
                center=center,
            )
        )

    def edge_profile_asym(
        self,
        edges: str | list = "ALL",
        except_edges: list | None = None,
        children: Sequence[Sequence[float]] | None = None,
        convexity: int = 10,
    ) -> "Bosl2Solid":
        return self.edge_profile(edges, except_edges, children, convexity)

    def corner_profile(
        self,
        corners: str | list = "ALL",
        except_corners: list | None = None,
        radius: float | None = None,
        diameter: float | None = None,
        children: Sequence[Sequence[float]] | None = None,
        convexity: int = 10,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
        bbox=None,
    ) -> "Bosl2Solid":
        from . import masking

        center, size = self._resolve_bounds(bbox)
        return self._wrap(
            masking.corner_profile(
                self.shape,
                corners,
                except_corners,
                radius,
                diameter,
                size=size,
                children=children,
                convexity=convexity,
                center=center,
                fn=fn,
                fa=fa,
                fs=fs,
            )
        )

    def face_profile(
        self,
        faces: str | list = "ALL",
        radius: float | None = None,
        diameter: float | None = None,
        children: Sequence[Sequence[float]] | None = None,
        convexity: int = 10,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
        bbox=None,
    ) -> "Bosl2Solid":
        from . import masking

        center, size = self._resolve_bounds(bbox)
        return self._wrap(
            masking.face_profile(
                self.shape,
                faces,
                radius,
                diameter,
                size=size,
                children=children,
                convexity=convexity,
                center=center,
                fn=fn,
                fa=fa,
                fs=fs,
            )
        )


# ---------------------------------------------------------------------------
# Internal helpers (not part of BOSL2's public API)
# ---------------------------------------------------------------------------


def _quantup(x: float, y: float) -> float:
    return math.ceil(x / y) * y


def _orient_rotate(shape: PyOpenSCAD, orient: Sequence[float]) -> PyOpenSCAD:
    o = list(orient)
    if o == [0, 0, 1]:
        return shape
    if o == [0, 0, -1]:
        return shape.rotate(180, [1, 0, 0])
    axis = np.asarray(cross([0, 0, 1], o), dtype=float)
    sides = float(np.linalg.norm(axis))
    if sides < 1e-12:
        return shape
    axis = (axis / sides).tolist()
    ou = unit(o)
    cosang = max(-1.0, min(1.0, ou[2]))
    angle = math.degrees(math.acos(cosang))
    return shape.rotate(angle, axis)


def _rot_from_to(a: Sequence[float], b: Sequence[float]) -> "tuple[float, list[float]]":
    """(angle_degrees, axis) that rotates direction *a* onto direction *b*, for shape.rotate().
    Handles the parallel (no rotation) and antiparallel (180 deg about any perpendicular axis)
    cases. Used by Bosl2Solid.attach() to point a child's mating face at a parent face."""
    au, bu = unit(a), unit(b)
    diameter = max(-1.0, min(1.0, sum(au[i] * bu[i] for i in range(3))))
    if diameter > 1 - 1e-9:
        return 0.0, [0.0, 0.0, 1.0]
    if diameter < -1 + 1e-9:
        axis = cross(au, [1.0, 0.0, 0.0])
        if float(np.linalg.norm(np.asarray(axis, dtype=float))) < 1e-9:
            axis = cross(au, [0.0, 1.0, 0.0])
        return 180.0, list(unit(axis))
    axis = list(unit(cross(au, bu)))
    return math.degrees(math.acos(diameter)), axis


def _finish3(shape: PyOpenSCAD, offset: Sequence[float], spin: float, orient: Sequence[float]) -> PyOpenSCAD:
    if offset[0] or offset[1] or offset[2]:
        shape = shape.translate(offset)
    if spin:
        shape = shape.rotate(spin, [0, 0, 1])
    return _orient_rotate(shape, orient)


def _anchor_offset_box3(size: Sequence[float], anchor: Sequence[float]) -> list[float]:
    a = list(anchor)
    return [-a[i] * size[i] / 2 for i in range(3)]


def _anchor_offset_hull3(points: Sequence[Sequence[float]], anchor: Sequence[float]) -> list[float]:
    a = list(anchor)
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
    anchor: Sequence[float],
    axis: int = 2,
) -> list[float]:
    a = list(anchor)
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


def _anchor_offset_sphere(radius: float, anchor: Sequence[float]) -> list[float]:
    a = list(anchor)
    sides = math.hypot(*a)
    if sides == 0:
        return [0.0, 0.0, 0.0]
    return [-a[i] / sides * radius for i in range(3)]


# --- cuboid() edge-set machinery, mirroring BOSL2 attachments.scad -----------
# The edge-selector mini-language lives in pybosl2._edges_lang so BOTH backends (CSG here, SDF in
# pybosl2._sdf) share one implementation without depending on each other's shape module. Re-exported
# here for the many internal users below and for backward-compatible imports.
from pybosl2._edges_lang import (  # noqa: E402, F401
    _MAJOR_AXIS_VALID,
    EDGE_OFFSETS,
    EDGES_ALL,
    EDGES_NONE,
    _edge_set,
    _edges,
    _is_edge_array,
    _is_plain_vector,
)


def _corner_edges(edges: Sequence[Sequence[float]], v: Sequence[float]) -> list[int]:
    u = [(v[i] + 1) / 2 for i in range(3)]
    return [
        int(edges[0][int(u[1] + u[2] * 2)]),
        int(edges[1][int(u[0] + u[2] * 2)]),
        int(edges[2][int(u[0] + u[1] * 2)]),
    ]


def _rotate_to_axis(shape: PyOpenSCAD, axis: int) -> PyOpenSCAD:
    if axis == 0:
        return shape.rotate(90, [0, 1, 0])
    if axis == 1:
        return shape.rotate(-90, [1, 0, 0])
    return shape


def _trunc_cube(s: Sequence[float], corner: Sequence[float]) -> PyOpenSCAD:
    """A small cube with the corner facing away from *corner* trimmed off diagonally (7 vertices).

    Used to trim corner_shape() geometry down to just the correct octant of a cuboid corner.
    """
    pts = [[1, 1, 1], [1, 1, 0], [1, 0, 0], [0, 1, 1], [0, 1, 0], [1, 0, 1], [0, 0, 1]]
    faces = [
        [0, 1, 2],
        [2, 5, 0],
        [0, 5, 6],
        [0, 6, 3],
        [0, 3, 4],
        [0, 4, 1],
        [1, 4, 2],
        [3, 6, 4],
        [5, 2, 6],
        [2, 4, 6],
    ]
    scaled = [
        [
            (p[0] - 0.5) * (s[0] + 0.001),
            (p[1] - 0.5) * (s[1] + 0.001),
            (p[2] - 0.5) * (s[2] + 0.001),
        ]
        for p in pts
    ]
    shape = _opolyhedron(scaled, faces)
    if corner[0] < 0:
        shape = shape.mirror([1, 0, 0])
    if corner[1] < 0:
        shape = shape.mirror([0, 1, 0])
    if corner[2] < 0:
        shape = shape.mirror([0, 0, 1])
    return shape


def _corner_shape(
    corner: Sequence[float],
    size: Sequence[float],
    edges: Sequence[Sequence[float]],
    radius: float,
    is_chamfer: bool,
    trimcorners: bool,
    fn,
    fa,
    fs,
) -> PyOpenSCAD:
    e = _corner_edges(edges, corner)
    cnt = sum(e)
    c = [radius, radius, radius]
    m = 0.01
    c2 = [corner[i] * c[i] / 2 for i in range(3)]
    c3 = [corner[i] * (c[i] - m / 2) for i in range(3)]
    fn = 4 if is_chamfer else max(4, int(_quantup(_frag_count(radius, fn, fa, fs), 4)))
    base_t = [corner[i] * (size[i] / 2 - c[i]) for i in range(3)]

    def xtcyl(length: float, radius: float):
        return _rotate_to_axis(_ocylinder(height=length, radius=radius, center=True, fn=fn), 0)

    def ytcyl(length: float, radius: float):
        return _rotate_to_axis(_ocylinder(height=length, radius=radius, center=True, fn=fn), 1)

    def ztcyl(length: float, radius: float):
        return _ocylinder(height=length, radius=radius, center=True, fn=fn)

    def tsphere(radius: float):
        return _osphere(radius=radius, fn=fn)

    if cnt == 0 or radius == 0:
        shape = _ocube(m, center=True).translate(c3)
    elif cnt == 1:
        if e[0]:
            shape = xtcyl(c[0] * 2, radius).translate([c3[0], 0, 0])
        elif e[1]:
            shape = ytcyl(c[1] * 2, radius).translate([0, c3[1], 0])
        else:
            shape = ztcyl(c[2] * 2, radius).translate([0, 0, c3[2]])
        shape = shape & _trunc_cube(c, corner).translate(c2)
    elif cnt == 2:
        if not e[0]:
            shape = ytcyl(c[1] * 2, radius) & ztcyl(c[2] * 2, radius)
        elif not e[1]:
            shape = xtcyl(c[0] * 2, radius) & ztcyl(c[2] * 2, radius)
        else:
            shape = xtcyl(c[0] * 2, radius) & ytcyl(c[1] * 2, radius)
        shape = shape & _trunc_cube(c, corner).translate(c2)
    else:
        shape = (
            tsphere(radius)
            if trimcorners
            else (xtcyl(c[0] * 2, radius) & ytcyl(c[1] * 2, radius) & ztcyl(c[2] * 2, radius))
        )
        shape = shape & _trunc_cube(c, corner).translate(c2)
    return shape.translate(base_t)


def _edge_mask_negative(
    sz: Sequence[float],
    edge_set: Sequence[Sequence[float]],
    ard: float,
    is_chamfer: bool,
    trimcorners: bool,
    fn,
    fa,
    fs,
) -> PyOpenSCAD:
    assert edge_set == EDGES_ALL or edge_set[2] == [0, 0, 0, 0], (
        "Cannot use negative rounding/chamfer with Z aligned edges."
    )
    pieces = []
    cutters = []
    for axis in (0, 1):
        for i in range(4):
            if edge_set[axis][i] > 0:
                vec = EDGE_OFFSETS[axis][i]
                adj = [ard - 0.01, ard - 0.01, -ard]
                t = [vec[k] / 2 * (sz[k] + adj[k]) for k in range(3)]
                box = _rotate_to_axis(_ocube([ard, ard, sz[axis]], center=True), axis)
                pieces.append(box.translate(t))
                adj2 = [2 * ard, 2 * ard, -2 * ard]
                t2 = [vec[k] / 2 * (sz[k] + adj2[k]) for k in range(3)]
                if is_chamfer:
                    cutter = _ocube(
                        [ard * math.sqrt(2), ard * math.sqrt(2), sz[axis] + 2.1 * ard],
                        center=True,
                    ).rotate(45, [0, 0, 1])
                else:
                    fn = int(_quantup(_frag_count(ard, fn, fa, fs), 4))
                    cutter = _ocylinder(height=sz[axis] + 2.1 * ard, radius=ard, center=True, fn=fn)
                cutters.append(_rotate_to_axis(cutter, axis).translate(t2))
    if trimcorners:
        for za in (-1, 1):
            for ya in (-1, 1):
                for xa in (-1, 1):
                    ce = _corner_edges(edge_set, [xa, ya, za])
                    if ce[0] + ce[1] > 1:
                        adj3 = [ard - 0.01, ard - 0.01, -ard]
                        t3 = [[xa, ya, za][k] / 2 * (sz[k] + adj3[k]) for k in range(3)]
                        pieces.append(_ocube([ard + 0.01, ard + 0.01, ard], center=True).translate(t3))
    edge_union = pieces[0]
    for p in pieces[1:]:
        edge_union = edge_union | p
    for c in cutters:
        edge_union = edge_union - c
    return _ocube(sz, center=True) | edge_union


# ---------------------------------------------------------------------------
# Section: native-only 2-D -> 3-D constructor (no BOSL2 equivalent)
# ---------------------------------------------------------------------------


def roof(shape, method: str = "straight") -> Bosl2Solid:
    """Raise a hip roof over a 2-D *shape* via its straight skeleton (native ``roof()``).

    Like :func:`~pybosl2.skin.linear_sweep`, this turns a 2-D outline into a 3-D solid, but the top is
    a peaked roof (each edge slopes inward at 45 degrees to the skeleton) rather than a flat
    extrusion. *shape* is any 2-D object -- a native ``square``/``circle``/``polygon``, a
    :meth:`Path.polygon`, or a :class:`Bosl2Solid` wrapping one. *method* selects the skeleton
    algorithm. PythonSCAD-only (no BOSL2 counterpart); covered by the STL render tests.
    """
    return Bosl2Solid(Bosl2Solid._unwrap(shape).roof(method=method))


# ---------------------------------------------------------------------------
# Section: Cuboids, Prismoids and Pyramids
# ---------------------------------------------------------------------------


def cube(
    size: float | Sequence[float] = 1,
    center: bool | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    orient: Sequence[float] = UP,
) -> Bosl2Solid:
    """A cube, built with the builtin cube(), with BOSL2-style anchor/spin/orient support.

    Args:
        size:   size of the cube, a number or length-3 vector
        center: if given, overrides anchor (True -> CENTER, False -> FRONT+LEFT+BOTTOM)
        anchor: anchor point (default CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)
        orient: direction to rotate the top towards, after spin (default UP)
    """
    sz = [float(size)] * 3 if isinstance(size, (int, float)) else [float(v) for v in size]
    use_anchor = anchor
    if center is not None:
        use_anchor = CENTER if center else [-1, -1, -1]
    shape = _ocube(sz, center=True)
    offset = _anchor_offset_box3(sz, use_anchor)
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=sz, anchor=use_anchor)


def cuboid(
    size: float | Sequence[float] = [1, 1, 1],
    p1: Sequence[float] | None = None,
    p2: Sequence[float] | None = None,
    chamfer: float | None = None,
    rounding: float | None = None,
    edges: str | list = "ALL",
    except_edges: list | None = None,
    trimcorners: bool = True,
    teardrop: bool | float = False,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    orient: Sequence[float] = UP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """A cube/cuboid with optional chamfering or rounding of edges and corners.

    Built directly from cube()/cylinder()/sphere()/hull()/minkowski(), mirroring BOSL2's own
    cuboid() algorithm (which is itself CSG composition of primitive shapes at each corner,
    not raw polyhedron mesh math).

    You cannot mix chamfering and rounding on the same call. Negative chamfers/roundings
    create external fillets, but only apply to edges around the top or bottom face.

    Note: `teardrop=` is not supported by this pure-Python port.

    Args:
        size:         size of the cuboid, a number or length-3 vector
        p1:           align the cuboid's corner at p1, if given (forces anchor=FRONT+LEFT+BOTTOM)
        p2:           if given with p1, defines the cuboid's opposing cornerpoint
        chamfer:      chamfer size, inset from sides (default: no chamfer)
        rounding:     edge rounding radius (default: no rounding)
        edges:        edges to mask (default "ALL")
        except_edges: edges to explicitly not mask (BOSL2's `except=` synonym; `except` is a Python keyword)
        trimcorners:  round/chamfer corners where three treated edges meet (default True)
        anchor:       anchor point (default CENTER)
        spin:         Z-axis rotation in degrees (default 0)
        orient:       direction to rotate the top towards (default UP)
        fn/fa/fs:  arc smoothness overrides for rounded edges/corners

    Examples:
        .. pythonscad-example::

            shape = pybosl2.shapes3d.cuboid([40, 30, 20])
            shape.show()

        .. pythonscad-example::

            shape = pybosl2.shapes3d.cuboid([40, 30, 20], rounding=5)
            shape.show()
    """
    if teardrop:
        raise NotImplementedError("cuboid(): teardrop= is not supported by this pure-Python port.")
    sz = [float(size)] * 3 if isinstance(size, (int, float)) else [float(v) for v in size]
    if p1 is not None:
        if p2 is not None:
            mn = [min(p1[i], p2[i]) for i in range(3)]
            mx = [max(p1[i], p2[i]) for i in range(3)]
            shape = cuboid(
                [mx[i] - mn[i] for i in range(3)],
                chamfer=chamfer,
                rounding=rounding,
                edges=edges,
                except_edges=except_edges,
                trimcorners=trimcorners,
                anchor=[-1, -1, -1],
                fn=fn,
                fa=fa,
                fs=fs,
            )
            return shape.translate(mn)
        shape = cuboid(
            sz,
            chamfer=chamfer,
            rounding=rounding,
            edges=edges,
            except_edges=except_edges,
            trimcorners=trimcorners,
            anchor=[-1, -1, -1],
            fn=fn,
            fa=fa,
            fs=fs,
        )
        return shape.translate(p1)

    edge_set = _edges(edges, except_edges or [])
    chamfer_v = chamfer if chamfer else 0
    rounding_v = rounding if rounding else 0
    assert not (chamfer_v and rounding_v), "Cannot specify nonzero value for both chamfer and rounding"

    corners8 = [[xa, ya, za] for za in (-1, 1) for ya in (-1, 1) for xa in (-1, 1)]

    if chamfer_v != 0:
        radius = chamfer_v
        if edge_set == EDGES_ALL and trimcorners:
            if radius < 0:
                shape = _edge_mask_negative(sz, edge_set, abs(radius), True, trimcorners, fn, fa, fs)
            else:
                isize = [max(0.001, v - 2 * radius) for v in sz]
                shape = _ohull(
                    _ocube([sz[0], isize[1], isize[2]], center=True),
                    _ocube([isize[0], sz[1], isize[2]], center=True),
                    _ocube([isize[0], isize[1], sz[2]], center=True),
                )
        elif radius < 0:
            shape = _edge_mask_negative(sz, edge_set, abs(radius), True, trimcorners, fn, fa, fs)
        else:
            # Intersected with the plain box: _corner_shape()'s per-corner treatment (for a
            # single active edge, e.g. edges="Z") is sized around the rounding radius alone, not
            # clipped to the box's own extent along the *other* axes -- for edges="Z" specifically,
            # each corner cap spans 2*radius along Z, so if radius exceeds half the box's Z size (a thin
            # slab with a comparatively large XY corner rounding, e.g. labels.py's striped
            # backgrounds), the un-intersected hull balloons far beyond the box's actual
            # thickness instead of just rounding its corners.
            shape = _ohull(
                *[_corner_shape(c, sz, edge_set, radius, True, trimcorners, fn, fa, fs) for c in corners8]
            ) & _ocube(sz, center=True)
    elif rounding_v != 0:
        radius = rounding_v
        if edge_set == EDGES_ALL and radius > 0:
            isize = [max(0.001, v - 2 * radius) for v in sz]
            fn = int(_quantup(_frag_count(radius, fn, fa, fs), 4))
            shape = _ominkowski(_ocube(isize, center=True), _osphere(radius=radius, fn=fn))
        elif radius < 0:
            shape = _edge_mask_negative(sz, edge_set, abs(radius), False, trimcorners, fn, fa, fs)
        else:
            # See the chamfer branch above for why this needs clipping to the plain box.
            shape = _ohull(
                *[_corner_shape(c, sz, edge_set, radius, False, trimcorners, fn, fa, fs) for c in corners8]
            ) & _ocube(sz, center=True)
    else:
        shape = _ocube(sz, center=True)

    offset = _anchor_offset_box3(sz, anchor)
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=sz, anchor=anchor)


def prismoid(
    size1: Sequence[float],
    size2: Sequence[float],
    height: float | None = None,
    shift: Sequence[float] = [0, 0],
    rounding: float | Sequence[float] = 0,
    rounding1: float | Sequence[float] | None = None,
    rounding2: float | Sequence[float] | None = None,
    chamfer: float | Sequence[float] = 0,
    chamfer1: float | Sequence[float] | None = None,
    chamfer2: float | Sequence[float] | None = None,
    length: float | None = None,
    center: bool | None = None,
    anchor: Sequence[float] = BOTTOM,
    spin: float = 0,
    orient: Sequence[float] = UP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """A rectangular prismoid, built as the convex hull() of two (optionally rounded/chamfered) rects.

    Args:
        size1:     [width, length] of the bottom end
        size2:     [width, length] of the top end
        height/length:       height of the prism
        shift:     [X,Y] shift of the top center relative to the bottom center
        rounding:  vertical-edge roundover radius, or per-corner list [X+Y+,X-Y+,X-Y-,X+Y-] (default 0)
        rounding1: roundover radius for the bottom of the vertical-ish edges
        rounding2: roundover radius for the top of the vertical-ish edges
        chamfer:   vertical-edge chamfer size, or per-corner list (default 0)
        chamfer1:  chamfer size for the bottom of the vertical-ish edges
        chamfer2:  chamfer size for the top of the vertical-ish edges
        center:    if given, overrides anchor
        anchor:    anchor point (default BOTTOM)
        spin:      Z-axis rotation in degrees after anchor (default 0)
        orient:    direction to rotate the top towards, after spin (default UP)
        fn/fa/fs: arc smoothness overrides for rounded corners

    Examples:
        .. pythonscad-example::

            shape = pybosl2.shapes3d.prismoid([40, 40], [20, 25], height=30)
            shape.show()
    """
    from .shapes2d import _rect_path

    s1 = [float(size1)] * 2 if isinstance(size1, (int, float)) else [float(v) for v in size1]
    s2 = [float(size2)] * 2 if isinstance(size2, (int, float)) else [float(v) for v in size2]
    height = height if height is not None else (length if length is not None else 1)
    radius1 = rounding1 if rounding1 is not None else rounding
    radius2 = rounding2 if rounding2 is not None else rounding
    c1 = chamfer1 if chamfer1 is not None else chamfer
    c2 = chamfer2 if chamfer2 is not None else chamfer
    use_anchor = anchor
    if center is not None:
        use_anchor = CENTER if center else BOTTOM

    path1 = _rect_path(s1, rounding=radius1, chamfer=c1, fn=fn, fa=fa, fs=fs)
    path2 = _rect_path(s2, rounding=radius2, chamfer=c2, fn=fn, fa=fa, fs=fs)
    bottom_pts = [[p[0], p[1], -height / 2] for p in path1]
    top_pts = [[p[0] + shift[0], p[1] + shift[1], height / 2] for p in path2]
    bottom = _opolyhedron(bottom_pts, [list(range(len(bottom_pts)))])
    top = _opolyhedron(top_pts, [list(range(len(top_pts)))])
    shape = _ohull(bottom, top)
    offset = _anchor_offset_hull3(bottom_pts + top_pts, use_anchor)
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=None, anchor=use_anchor)


def octahedron(
    size: float = 1,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    orient: Sequence[float] = UP,
) -> Bosl2Solid:
    """An octahedron with axis-aligned points, built directly with polyhedron().

    Args:
        size:   width of the octahedron, tip to tip
        anchor: anchor point (default CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)
        orient: direction to rotate the top towards, after spin (default UP)
    """
    s = size / 2
    pts = [[s, 0, 0], [-s, 0, 0], [0, s, 0], [0, -s, 0], [0, 0, s], [0, 0, -s]]
    faces = [
        [2, 0, 4],
        [1, 2, 4],
        [3, 1, 4],
        [0, 3, 4],
        [0, 2, 5],
        [2, 1, 5],
        [1, 3, 5],
        [3, 0, 5],
    ]
    shape = _opolyhedron(pts, faces)
    offset = _anchor_offset_hull3(pts, anchor)
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=None, anchor=anchor)


def wedge(
    size: Sequence[float] = [1, 1, 1],
    center: bool | None = None,
    anchor: Sequence[float] = FRONT + LEFT + BOTTOM,
    spin: float = 0,
    orient: Sequence[float] = UP,
) -> Bosl2Solid:
    """A 3-D triangular wedge with the hypotenuse in the X+Z+ quadrant, built directly with polyhedron().

    Args:
        size:   [width, thickness, height]
        center: if given, overrides anchor (True -> CENTER, False -> FRONT+LEFT+BOTTOM)
        anchor: anchor point (default FRONT+LEFT+BOTTOM)
        spin:   Z-axis rotation in degrees after anchor (default 0)
        orient: direction to rotate the top towards, after spin (default UP)
    """
    sz = [float(size)] * 3 if isinstance(size, (int, float)) else [float(v) for v in size]
    use_anchor = anchor
    if center is not None:
        use_anchor = CENTER if center else [-1, -1, -1]
    pts: list[list[float]] = [[1, 1, -1], [1, -1, -1], [1, -1, 1], [-1, 1, -1], [-1, -1, -1], [-1, -1, 1]]
    pts = [[p[0] * sz[0] / 2, p[1] * sz[1] / 2, p[2] * sz[2] / 2] for p in pts]
    faces = [
        [0, 1, 2],
        [3, 5, 4],
        [0, 3, 1],
        [1, 3, 4],
        [1, 4, 2],
        [2, 4, 5],
        [2, 5, 3],
        [0, 2, 3],
    ]
    shape = _opolyhedron(pts, faces)
    offset = _anchor_offset_hull3(pts, use_anchor)
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=None, anchor=use_anchor)


def _rect_tube_rounding(
    factor: float,
    inner_radius: Sequence[float | None],
    radius: Sequence[float | None],
    alternative: Sequence[float | None],
    size: Sequence[float],
    isize: Sequence[float],
) -> list[float]:
    wall = min(size[0] - isize[0], size[1] - isize[1]) / 2 * factor
    return [
        iri
        if iri is not None
        else (max(0.0, (ri if ri is not None else 0.0) - wall) if alternative[i] is None else 0.0)
        for i, (iri, ri) in enumerate(zip(inner_radius, radius, strict=False))
    ]


def rect_tube(
    height: float | None = None,
    size: float | Sequence[float] | None = None,
    isize: float | Sequence[float] | None = None,
    center: bool | None = None,
    shift: Sequence[float] = [0, 0],
    wall: float | None = None,
    size1: float | Sequence[float] | None = None,
    size2: float | Sequence[float] | None = None,
    isize1: float | Sequence[float] | None = None,
    isize2: float | Sequence[float] | None = None,
    rounding: float | Sequence[float] = 0,
    rounding1: float | Sequence[float] | None = None,
    rounding2: float | Sequence[float] | None = None,
    inner_rounding: float | Sequence[float] = 0,
    inner_rounding1: float | Sequence[float] | None = None,
    inner_rounding2: float | Sequence[float] | None = None,
    chamfer: float | Sequence[float] = 0,
    chamfer1: float | Sequence[float] | None = None,
    chamfer2: float | Sequence[float] | None = None,
    inner_chamfer: float | Sequence[float] = 0,
    inner_chamfer1: float | Sequence[float] | None = None,
    inner_chamfer2: float | Sequence[float] | None = None,
    anchor: Sequence[float] = BOTTOM,
    spin: float = 0,
    orient: Sequence[float] = UP,
    length: float | None = None,
) -> Bosl2Solid:
    """BOSL2 rect_tube() -- a rectangular tube (a rectangle with a rectangular hole through it).

    Args:
        height/length:        height/length of the tube (default 1)
        size:       outer [X,Y] size of the tube
        isize:      inner [X,Y] size of the tube
        center:     if given, overrides anchor
        shift:      [X,Y] shift of the top center relative to the bottom center
        wall:       wall thickness
        size1/size2:   outer [X,Y] size at the bottom/top
        isize1/isize2: inner [X,Y] size at the bottom/top
        rounding/rounding1/rounding2:    outer edge rounding radius (overall/bottom/top)
        inner_rounding/inner_rounding1/inner_rounding2: inner edge rounding radius (default: same as rounding)
        chamfer/chamfer1/chamfer2:       outer edge chamfer size (overall/bottom/top)
        inner_chamfer/inner_chamfer1/inner_chamfer2:    inner edge chamfer size (default: same as chamfer)
        anchor:     anchor point (default BOTTOM)
        spin:       Z-axis rotation in degrees after anchor (default 0)
        orient:     direction to rotate the top towards, after spin (default UP)
    """
    from .shapes2d import _rect_path

    def as2(v: float | Sequence[float] | None) -> list[float] | None:
        if v is None:
            return None
        return [float(v), float(v)] if isinstance(v, (int, float)) else [float(x) for x in v]

    def force4(v: float | Sequence[float] | None) -> list[float | None]:
        if v is None:
            return [None, None, None, None]
        return [float(v)] * 4 if isinstance(v, (int, float)) else [float(x) for x in v]

    def force4f(v: float | Sequence[float]) -> list[float]:
        return [float(v)] * 4 if isinstance(v, (int, float)) else [float(x) for x in v]

    def override_or_none(
        specific: float | Sequence[float] | None, general: float | Sequence[float]
    ) -> float | Sequence[float] | None:
        # `general` (inner_rounding/inner_chamfer) defaults to 0 rather than None in this port's
        # signature, so a bare 0 is treated as "not specified" (inherit from rounding/chamfer);
        # pass inner_rounding1=/inner_rounding2=/inner_chamfer1=/inner_chamfer2= (which do default to None) to force
        # an explicit zero.
        if specific is not None:
            return specific
        return general if general else None

    height = height if height is not None else (length if length is not None else 1)
    s1 = as2(size1) if size1 is not None else as2(size)
    s2 = as2(size2) if size2 is not None else as2(size)
    i1 = as2(isize1) if isize1 is not None else as2(isize)
    i2 = as2(isize2) if isize2 is not None else as2(isize)
    size1_v = (
        s1
        if s1 is not None
        else ([i1[0] + 2 * wall, i1[1] + 2 * wall] if (wall is not None and i1 is not None) else None)
    )
    size2_v = (
        s2
        if s2 is not None
        else ([i2[0] + 2 * wall, i2[1] + 2 * wall] if (wall is not None and i2 is not None) else None)
    )
    isize1_v = (
        i1
        if i1 is not None
        else ([s1[0] - 2 * wall, s1[1] - 2 * wall] if (wall is not None and s1 is not None) else None)
    )
    isize2_v = (
        i2
        if i2 is not None
        else ([s2[0] - 2 * wall, s2[1] - 2 * wall] if (wall is not None and s2 is not None) else None)
    )
    assert size1_v is not None and size2_v is not None, "rect_tube(): bad size/size1/size2 argument."
    assert isize1_v is not None and isize2_v is not None, "rect_tube(): bad isize/isize1/isize2 argument."
    assert isize1_v[0] < size1_v[0] and isize1_v[1] < size1_v[1], (
        "rect_tube(): inner size is larger than outer size at the bottom."
    )
    assert isize2_v[0] < size2_v[0] and isize2_v[1] < size2_v[1], (
        "rect_tube(): inner size is larger than outer size at the top."
    )

    rounding1_v = force4f(rounding1 if rounding1 is not None else rounding)
    rounding2_v = force4f(rounding2 if rounding2 is not None else rounding)
    chamfer1_v = force4f(chamfer1 if chamfer1 is not None else chamfer)
    chamfer2_v = force4f(chamfer2 if chamfer2 is not None else chamfer)
    irounding1_t = force4(override_or_none(inner_rounding1, inner_rounding))
    irounding2_t = force4(override_or_none(inner_rounding2, inner_rounding))
    ichamfer1_t = force4(override_or_none(inner_chamfer1, inner_chamfer))
    ichamfer2_t = force4(override_or_none(inner_chamfer2, inner_chamfer))

    irounding1_v = _rect_tube_rounding(1.0, irounding1_t, rounding1_v, ichamfer1_t, size1_v, isize1_v)
    irounding2_v = _rect_tube_rounding(1.0, irounding2_t, rounding2_v, ichamfer2_t, size2_v, isize2_v)
    ichamfer1_v = _rect_tube_rounding(1 / math.sqrt(2), ichamfer1_t, chamfer1_v, irounding1_t, size1_v, isize1_v)
    ichamfer2_v = _rect_tube_rounding(1 / math.sqrt(2), ichamfer2_t, chamfer2_v, irounding2_t, size2_v, isize2_v)

    use_anchor = anchor
    if center is not None:
        use_anchor = CENTER if center else BOTTOM

    outer = prismoid(
        size1_v,
        size2_v,
        height=height,
        shift=shift,
        rounding1=rounding1_v,
        rounding2=rounding2_v,
        chamfer1=chamfer1_v,
        chamfer2=chamfer2_v,
        anchor=CENTER,
    )
    inner = prismoid(
        isize1_v,
        isize2_v,
        height=height + 0.02,
        shift=shift,
        rounding1=irounding1_v,
        rounding2=irounding2_v,
        chamfer1=ichamfer1_v,
        chamfer2=ichamfer2_v,
        anchor=CENTER,
    )
    shape = outer.shape - inner.shape

    path1 = _rect_path(size1_v, rounding=rounding1_v, chamfer=chamfer1_v)
    path2 = _rect_path(size2_v, rounding=rounding2_v, chamfer=chamfer2_v)
    bottom_pts = [[p[0], p[1], -height / 2] for p in path1]
    top_pts = [[p[0] + shift[0], p[1] + shift[1], height / 2] for p in path2]
    offset = _anchor_offset_hull3(bottom_pts + top_pts, use_anchor)

    straight = size1_v == size2_v and shift[0] == 0 and shift[1] == 0
    out_size = [size1_v[0], size1_v[1], height] if straight else None
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=out_size, anchor=use_anchor)


# ---------------------------------------------------------------------------
# Section: Cylinders
# ---------------------------------------------------------------------------


def cylinder(
    height: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    center: bool | None = None,
    length: float | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    orient: Sequence[float] = UP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """A cylinder/cone, built with the builtin cylinder(), with BOSL2-style anchor/spin/orient support.

    Args:
        length/height:    height of the cylinder
        radius1:     bottom radius (before orientation)
        radius2:     top radius (before orientation)
        center: if given, overrides anchor (True -> CENTER, False -> BOTTOM)
        diameter1:     bottom diameter (before orientation)
        diameter2:     top diameter (before orientation)
        radius:      radius of the cylinder
        diameter:      diameter of the cylinder
        anchor: anchor point (default CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)
        orient: direction to rotate the top towards, after spin (default UP)
        fn/fa/fs: arc smoothness overrides
    """
    length = length if length is not None else (height if height is not None else 1)
    rad1 = _pick_radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
    rad2 = _pick_radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter, dflt=1)
    use_anchor = anchor
    if center is not None:
        use_anchor = CENTER if center else BOTTOM
    shape = _ocylinder(
        height=length,
        radius1=rad1,
        radius2=rad2,
        center=True,
        fn=fn,
        fa=fa,
        fs=fs,
    )
    offset = _anchor_offset_cyl(rad1, rad2, length, use_anchor)
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=None, anchor=use_anchor)


def cyl(
    height: float | None = None,
    radius: float | None = None,
    center: bool | None = None,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    circumscribe: bool = False,
    realign: bool = False,
    shift: Sequence[float] = [0, 0],
    anchor: Sequence[float] | None = None,
    spin: float = 0,
    orient: Sequence[float] = UP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    # Additional missing args
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    from_end: bool = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    extra: float = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    teardrop: float | bool = False,
    clip_angle: float = 90.0,
    texture: str | TextureType | None = None,
    tex_size: float | Sequence[float] | None = None,
    tex_reps: int | Sequence[int] | None = None,
    tex_depth: float = 1.0,
    tex_inset: float | bool = False,
) -> Bosl2Solid:
    """A cylinder with optional chamfering/rounding of its end rims, built with
    cube()/cylinder()/sphere()/rotate_extrude().

    Positive rounding is built as a minkowski() of a shorter cylinder with a sphere at each
    rounded end (an inset fillet, not an outward bulge), matching BOSL2's own rounded-end
    geometry. Chamfering builds the exact half-profile (with the requested bevel at each end)
    and revolves it with rotate_extrude().

    Note: `texture=` (VNF surface texturing) is not supported by this pure-Python port.

    Args:
        length/height:  length of the cylinder along its axis (default 1)
        radius:      radius of the cylinder (default 1)
        diameter:    diameter of the cylinder
        radius1:    radius of the negative end of the cylinder
        radius2:    radius of the positive end of the cylinder
        diameter1:  diameter of the negative end of the cylinder
        diameter2:  diameter of the positive end of the cylinder
        center:   if given, overrides anchor (True -> CENTER, False -> BOTTOM)
        chamfer/chamfer1/chamfer2: chamfer size on the end rims (overall/negative/positive)
        rounding/rounding1/rounding2: rounding radius on the end rims (overall/negative/positive)
        circumscribe: circumscribe rather than inscribe the given radius (default False)
        realign:      shift point alignment (default False)
        shift:        X/Y offset for the positive end (shear) (default [0,0])
        anchor:       anchor point (default CENTER)
        spin:         Z-axis rotation in degrees after anchor (default 0)
        orient:       direction to rotate the top towards, after spin (default UP)
        fn/fa/fs:     arc smoothness overrides
        chamfer_angle/chamfer_angle1/chamfer_angle2: chamfer angle in degrees away from ends
        from_end/from_end1/from_end2: measure chamfer along conic face (default False)
        extra/extra1/extra2: add extra height at ends (invisible to anchoring)
        teardrop:     limit rounding angle from horizontal
        clip_angle:   clip rounding arc at bottom of cylinder
        texture:      named texture to apply to cylinder side surface
        tex_size:     size of texture tile
        tex_reps:     number of texture repetitions
        tex_depth:    depth of the texture
        tex_inset:    inset the texture

    Examples:
        A basic cylinder:
        .. pythonscad-example::

            shape = pybosl2.shapes3d.cyl(radius=10, height=30)
            shape.show()

        A cylinder with chamfered ends:
        .. pythonscad-example::

            shape = pybosl2.shapes3d.cyl(radius=15, height=40, chamfer=2)
            shape.show()

        A cylinder with rounded ends:
        .. pythonscad-example::

            shape = pybosl2.shapes3d.cyl(radius=12, height=35, rounding=3)
            shape.show()
    """
    if texture is not None and texture != "none":
        raise NotImplementedError("texture= (VNF surface texturing) is not supported by this pure-Python port.")
    _ = (tex_size, tex_reps, tex_depth, tex_inset)

    length_val = next((v for v in (length, height) if v is not None), 1.0)
    rad1 = _pick_radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
    rad2 = _pick_radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter, dflt=1)

    if circumscribe:
        sides = _frag_count(max(rad1, rad2), fn, fa, fs)
        sc = 1 / math.cos(math.pi / sides)
        rad1 *= sc
        rad2 *= sc
    use_anchor = anchor
    if use_anchor is None:
        use_anchor = CENTER if center is None or center else BOTTOM

    r1v = rounding1 if rounding1 is not None else (rounding if rounding is not None else 0)
    r2v = rounding2 if rounding2 is not None else (rounding if rounding is not None else 0)
    c1v = chamfer1 if chamfer1 is not None else (chamfer if chamfer is not None else 0)
    c2v = chamfer2 if chamfer2 is not None else (chamfer if chamfer is not None else 0)
    assert not ((r1v or r2v) and (c1v or c2v)), "Cannot specify nonzero value for both chamfer and rounding"

    cfang1 = chamfer_angle1 if chamfer_angle1 is not None else (chamfer_angle if chamfer_angle is not None else None)
    cfang2 = chamfer_angle2 if chamfer_angle2 is not None else (chamfer_angle if chamfer_angle is not None else None)
    fe1 = from_end1 if from_end1 is not None else from_end
    fe2 = from_end2 if from_end2 is not None else from_end

    if not (r1v or r2v or c1v or c2v):
        shape = _ocylinder(
            height=length_val,
            radius1=rad1,
            radius2=rad2,
            center=True,
            fn=fn,
            fa=fa,
            fs=fs,
        )
    elif (
        rad1 == rad2
        and r1v == r2v
        and r1v > 0
        and not c1v
        and not c2v
        and (teardrop is False or teardrop is None)
        and clip_angle == 90.0
    ):
        # Straight cylinder, uniform rounding on both ends: exact via minkowski(cylinder, sphere).
        inner_r = max(0.001, rad1 - r1v)
        inner_l = max(0.001, length_val - 2 * r1v)
        sphere_fn = int(_quantup(_frag_count(r1v, fn, fa, fs), 4))
        shape = _ominkowski(
            _ocylinder(height=inner_l, radius=inner_r, center=True, fn=fn, fa=fa, fs=fs),
            _osphere(radius=r1v, fn=sphere_fn),
        )
    else:
        profile = _cyl_profile(
            rad1,
            rad2,
            length_val,
            rounding1=r1v,
            rounding2=r2v,
            chamfer1=c1v,
            chamfer2=c2v,
            chamfer_angle1=cfang1,
            chamfer_angle2=cfang2,
            from_end1=fe1,
            from_end2=fe2,
            fn=fn,
            fa=fa,
            fs=fs,
            teardrop=teardrop,
            clip_angle=clip_angle,
        )
        from .shapes2d import _opolygon

        shape = _orotate_extrude(_opolygon(profile), fn=fn, fa=fa, fs=fs)

    if realign:
        sides = _frag_count(max(rad1, rad2), fn, fa, fs)
        shape = shape.rotate(180 / sides, [0, 0, 1])
    if shift[0] or shift[1]:
        shear = [
            [1, 0, shift[0] / length_val, 0],
            [0, 1, shift[1] / length_val, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ]
        shape = shape.multmatrix(shear)

    extra1_val = extra1 if extra1 is not None else extra
    extra2_val = extra2 if extra2 is not None else extra
    if extra1_val > 0:
        ext1 = _ocylinder(height=extra1_val, radius=rad1, center=False, fn=fn, fa=fa, fs=fs).translate(
            [0, 0, -length_val / 2 - extra1_val]
        )
        shape = shape | ext1
    if extra2_val > 0:
        ext2 = _ocylinder(height=extra2_val, radius=rad2, center=False, fn=fn, fa=fa, fs=fs).translate(
            [0, 0, length_val / 2]
        )
        shape = shape | ext2

    offset = _anchor_offset_cyl(rad1, rad2, length_val, use_anchor)
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=None, anchor=use_anchor)


def _cyl_profile(
    radius1: float,
    radius2: float,
    length: float,
    rounding1: float = 0,
    rounding2: float = 0,
    chamfer1: float = 0,
    chamfer2: float = 0,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    from_end1: bool = False,
    from_end2: bool = False,
    fn=None,
    fa=None,
    fs=None,
    teardrop: float | bool = False,
    clip_angle: float = 90.0,
) -> list[list[float]]:
    from .shapes2d import _arc_points

    eff_clip = float(clip_angle)
    if teardrop is not False and teardrop is not None:
        td_ang = teardrop if isinstance(teardrop, (int, float)) else 45.0
        eff_clip = min(eff_clip, 90.0 - td_ang)

    path = [[0.0, -length / 2]]
    if rounding1:
        sides = max(3, _frag_count(rounding1, fn, fa, fs) // 4)
        center = [radius1 - rounding1, -length / 2 + rounding1]
        pts = _arc_points(sides, rounding1, 360 - eff_clip, eff_clip, center)
        if eff_clip < 90.0:
            path.append([pts[0][0], -length / 2])
        path.extend(pts)
    elif chamfer1:
        angle1 = chamfer_angle1 if chamfer_angle1 is not None else 45.0
        if from_end1:
            dx = chamfer1 * math.cos(math.radians(angle1))
            dy = chamfer1 * math.sin(math.radians(angle1))
        else:
            dx = chamfer1
            dy = chamfer1 * math.tan(math.radians(angle1))
        path.append([radius1 - dx, -length / 2])
        path.append([radius1, -length / 2 + dy])
    else:
        path.append([radius1, -length / 2])

    if rounding2:
        sides = max(3, _frag_count(rounding2, fn, fa, fs) // 4)
        center = [radius2 - rounding2, length / 2 - rounding2]
        pts = _arc_points(sides, rounding2, 0, eff_clip, center)
        path.extend(pts)
        if eff_clip < 90.0:
            path.append([pts[-1][0], length / 2])
    elif chamfer2:
        angle2 = chamfer_angle2 if chamfer_angle2 is not None else 45.0
        if from_end2:
            dx = chamfer2 * math.cos(math.radians(angle2))
            dy = chamfer2 * math.sin(math.radians(angle2))
        else:
            dx = chamfer2
            dy = chamfer2 * math.tan(math.radians(angle2))
        path.append([radius2, length / 2 - dy])
        path.append([radius2 - dx, length / 2])
    else:
        path.append([radius2, length / 2])
    path.append([0.0, length / 2])
    return path


def regular_prism(
    sides: int,
    height: float | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    inner_radius: float | None = None,
    inner_diameter: float | None = None,
    side: float | None = None,
    length: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    circumscribe: bool = False,
    realign: bool = False,
    shift: Sequence[float] = [0, 0],
    center: bool | None = None,
    anchor: Sequence[float] | None = None,
    spin: float = 0,
    orient: Sequence[float] = UP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """A regular sides-sided prism (or frustum) -- the sides-gon analogue of cyl(): a regular polygon
    cross-section extruded along Z, with optional per-end chamfer or rounding. Built the same
    way cyl() is (native cylinder with fn=sides for the plain case; a revolved half-profile with
    fn=sides for chamfered/rounded ends), so it shares cyl()'s exact rim geometry.

    Sizing gives the CIRCUMradius (vertex distance) unless noted -- exactly one of ``radius``/``diameter``
    (radius/diameter to the vertices), ``inner_radius``/``inner_diameter`` (inradius/apothem to the face centers,
    converted via ``/cos(180/sides)``), or ``side`` (edge length, converted via ``/(2 sin(180/sides))``).
    ``radius1``/``radius2`` (or the corresponding taper) set the bottom/top radius independently for a frustum.

    Note: BOSL2 regular_prism()'s texture=/teardrop= options are not ported (they need the VNF
    texturing machinery this pure-Python port doesn't implement).

    Args:
        sides:        number of sides (integer >= 3)
        height/length/height/length: prism height (default 1)
        radius/diameter/inner_radius/inner_diameter/side:    overall size (see above)
        radius1/radius2:    bottom/top circumradius for a tapered prism
        chamfer/chamfer1/chamfer2:    end chamfer size (overall/bottom/top)
        rounding/rounding1/rounding2: end rounding radius (overall/bottom/top)
        circumscribe:   circumscribe the nominal radius (scale by 1/cos(180/sides)) (default False)
        realign:  rotate by half a facet so a face, not a vertex, faces +X (default False)
        shift:    [X,Y] shift of the top center relative to the bottom center
        center:   if given, overrides anchor (True -> CENTER, False -> BOTTOM)
        anchor:   anchor point (default CENTER)
        spin:     Z-axis rotation in degrees after anchor (default 0)
        orient:   direction to rotate the top towards, after spin (default UP)
        fn/fa/fs: arc smoothness overrides

    Examples:
        .. pythonscad-example::

            shape = pybosl2.shapes3d.regular_prism(6, height=20, radius=15)
            shape.show()

        .. pythonscad-example::

            shape = pybosl2.shapes3d.regular_prism(5, height=20, inner_radius=12, rounding=2)
            shape.show()
    """
    assert isinstance(sides, int) and sides > 2, f"regular_prism(): sides must be an integer >= 3, got {sides}"
    cos_half = math.cos(math.pi / sides)

    def circumradius(spec_r: float | None) -> float:
        if spec_r is not None:
            return spec_r
        if side is not None:
            return side / (2 * math.sin(math.pi / sides))
        if inner_diameter is not None:
            return (inner_diameter / 2) / cos_half
        if inner_radius is not None:
            return inner_radius / cos_half
        if diameter is not None:
            return diameter / 2
        if radius is not None:
            return radius
        return 1.0

    rad1 = circumradius(radius1)
    rad2 = circumradius(radius2)
    if circumscribe:
        sc = 1 / cos_half
        rad1 *= sc
        rad2 *= sc
    prism_len = next((v for v in (length, height, height, length) if v is not None), 1.0)

    r1v = rounding1 if rounding1 is not None else (rounding if rounding is not None else 0)
    r2v = rounding2 if rounding2 is not None else (rounding if rounding is not None else 0)
    c1v = chamfer1 if chamfer1 is not None else (chamfer if chamfer is not None else 0)
    c2v = chamfer2 if chamfer2 is not None else (chamfer if chamfer is not None else 0)
    assert not ((r1v or r2v) and (c1v or c2v)), "Cannot specify nonzero value for both chamfer and rounding"

    use_anchor = anchor
    if use_anchor is None:
        use_anchor = CENTER if center is None or center else BOTTOM

    if not (r1v or r2v or c1v or c2v):
        shape = _ocylinder(height=prism_len, radius1=rad1, radius2=rad2, center=True, fn=sides)
    else:
        profile = _cyl_profile(rad1, rad2, prism_len, r1v, r2v, c1v, c2v, fn, fa, fs)
        from .shapes2d import _opolygon

        shape = _orotate_extrude(_opolygon(profile), fn=sides)

    # OpenSCAD's cylinder(fn=n) puts a vertex on +X; realign rotates half a facet so a face
    # centre faces +X instead (BOSL2's realign convention).
    if realign:
        shape = shape.rotate(180 / sides, [0, 0, 1])
    if shift[0] or shift[1]:
        shear = [
            [1, 0, shift[0] / prism_len, 0],
            [0, 1, shift[1] / prism_len, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ]
        shape = shape.multmatrix(shear)
    offset = _anchor_offset_cyl(rad1, rad2, prism_len, use_anchor)
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=None, anchor=use_anchor)


def xcyl(
    height: float | None = None,
    radius: float | None = None,
    center: bool | None = None,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    circumscribe: bool = False,
    realign: bool = False,
    shift: Sequence[float] = [0, 0],
    anchor: Sequence[float] | None = None,
    spin: float = 0,
    orient: Sequence[float] = UP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    # Additional missing args
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    from_end: bool = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    extra: float = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    teardrop: float | bool = False,
    clip_angle: float = 90.0,
    texture: str | TextureType | None = None,
    tex_size: float | Sequence[float] | None = None,
    tex_reps: int | Sequence[int] | None = None,
    tex_depth: float = 1.0,
    tex_inset: float | bool = False,
) -> Bosl2Solid:
    """A cylinder oriented along the X axis. See cyl() for argument details.

    Examples:
        .. pythonscad-example::

            shape = pybosl2.shapes3d.xcyl(radius=10, height=30)
            shape.show()
    """
    length_val = next((v for v in (length, height) if v is not None), 1.0)
    rad1 = _pick_radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
    rad2 = _pick_radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter, dflt=1)

    if circumscribe:
        sides = _frag_count(max(rad1, rad2), fn, fa, fs)
        sc = 1 / math.cos(math.pi / sides)
        rad1 *= sc
        rad2 *= sc

    use_anchor = anchor
    if use_anchor is None:
        use_anchor = CENTER if center is None or center else BOTTOM

    shape = cyl(
        length=length_val,
        radius1=rad1,
        radius2=rad2,
        chamfer=chamfer,
        chamfer1=chamfer1,
        chamfer2=chamfer2,
        rounding=rounding,
        rounding1=rounding1,
        rounding2=rounding2,
        circumscribe=circumscribe,
        realign=realign,
        shift=shift,
        anchor=CENTER,
        fn=fn,
        fa=fa,
        fs=fs,
        chamfer_angle=chamfer_angle,
        chamfer_angle1=chamfer_angle1,
        chamfer_angle2=chamfer_angle2,
        from_end=from_end,
        from_end1=from_end1,
        from_end2=from_end2,
        extra=extra,
        extra1=extra1,
        extra2=extra2,
        teardrop=teardrop,
        clip_angle=clip_angle,
        texture=texture,
        tex_size=tex_size,
        tex_reps=tex_reps,
        tex_depth=tex_depth,
        tex_inset=tex_inset,
    ).shape.rotate(90, [0, 1, 0])
    offset = _anchor_offset_cyl(rad1, rad2, length_val, use_anchor, axis=0)
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=None, anchor=use_anchor)


def ycyl(
    height: float | None = None,
    radius: float | None = None,
    center: bool | None = None,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    circumscribe: bool = False,
    realign: bool = False,
    shift: Sequence[float] = [0, 0],
    anchor: Sequence[float] | None = None,
    spin: float = 0,
    orient: Sequence[float] = UP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    # Additional missing args
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    from_end: bool = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    extra: float = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    teardrop: float | bool = False,
    clip_angle: float = 90.0,
    texture: str | TextureType | None = None,
    tex_size: float | Sequence[float] | None = None,
    tex_reps: int | Sequence[int] | None = None,
    tex_depth: float = 1.0,
    tex_inset: float | bool = False,
) -> Bosl2Solid:
    """A cylinder oriented along the Y axis. See cyl() for argument details.

    Examples:
        .. pythonscad-example::

            shape = pybosl2.shapes3d.ycyl(radius=10, height=30)
            shape.show()
    """
    length_val = next((v for v in (length, height) if v is not None), 1.0)
    rad1 = _pick_radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
    rad2 = _pick_radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter, dflt=1)

    if circumscribe:
        sides = _frag_count(max(rad1, rad2), fn, fa, fs)
        sc = 1 / math.cos(math.pi / sides)
        rad1 *= sc
        rad2 *= sc

    use_anchor = anchor
    if use_anchor is None:
        use_anchor = CENTER if center is None or center else BOTTOM

    shape = cyl(
        length=length_val,
        radius1=rad1,
        radius2=rad2,
        chamfer=chamfer,
        chamfer1=chamfer1,
        chamfer2=chamfer2,
        rounding=rounding,
        rounding1=rounding1,
        rounding2=rounding2,
        circumscribe=circumscribe,
        realign=realign,
        shift=shift,
        anchor=CENTER,
        fn=fn,
        fa=fa,
        fs=fs,
        chamfer_angle=chamfer_angle,
        chamfer_angle1=chamfer_angle1,
        chamfer_angle2=chamfer_angle2,
        from_end=from_end,
        from_end1=from_end1,
        from_end2=from_end2,
        extra=extra,
        extra1=extra1,
        extra2=extra2,
        teardrop=teardrop,
        clip_angle=clip_angle,
        texture=texture,
        tex_size=tex_size,
        tex_reps=tex_reps,
        tex_depth=tex_depth,
        tex_inset=tex_inset,
    ).shape.rotate(-90, [1, 0, 0])
    offset = _anchor_offset_cyl(rad1, rad2, length_val, use_anchor, axis=1)
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=None, anchor=use_anchor)


def zcyl(
    height: float | None = None,
    radius: float | None = None,
    center: bool | None = None,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    circumscribe: bool = False,
    realign: bool = False,
    shift: Sequence[float] = [0, 0],
    anchor: Sequence[float] | None = None,
    spin: float = 0,
    orient: Sequence[float] = UP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    # Additional missing args
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    from_end: bool = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    extra: float = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    teardrop: float | bool = False,
    clip_angle: float = 90.0,
    texture: str | TextureType | None = None,
    tex_size: float | Sequence[float] | None = None,
    tex_reps: int | Sequence[int] | None = None,
    tex_depth: float = 1.0,
    tex_inset: float | bool = False,
) -> Bosl2Solid:
    """
    A cylinder oriented along the Z axis (same as cyl() with default orientation). See cyl() for
    argument details.

    Examples:
        .. pythonscad-example::

            shape = pybosl2.shapes3d.zcyl(radius=10, height=30)
            shape.show()
    """
    return cyl(
        height=height,
        radius=radius,
        center=center,
        length=length,
        radius1=radius1,
        radius2=radius2,
        diameter=diameter,
        diameter1=diameter1,
        diameter2=diameter2,
        chamfer=chamfer,
        chamfer1=chamfer1,
        chamfer2=chamfer2,
        rounding=rounding,
        rounding1=rounding1,
        rounding2=rounding2,
        circumscribe=circumscribe,
        realign=realign,
        shift=shift,
        anchor=anchor,
        spin=spin,
        orient=orient,
        fn=fn,
        fa=fa,
        fs=fs,
        chamfer_angle=chamfer_angle,
        chamfer_angle1=chamfer_angle1,
        chamfer_angle2=chamfer_angle2,
        from_end=from_end,
        from_end1=from_end1,
        from_end2=from_end2,
        extra=extra,
        extra1=extra1,
        extra2=extra2,
        teardrop=teardrop,
        clip_angle=clip_angle,
        texture=texture,
        tex_size=tex_size,
        tex_reps=tex_reps,
        tex_depth=tex_depth,
        tex_inset=tex_inset,
    )


def tube(
    height: float | None = None,
    outer_radius: float | None = None,
    inner_radius: float | None = None,
    center: bool | None = None,
    outer_diameter: float | None = None,
    inner_diameter: float | None = None,
    wall: float | None = None,
    outer_radius1: float | None = None,
    outer_radius2: float | None = None,
    outer_diameter1: float | None = None,
    outer_diameter2: float | None = None,
    inner_radius1: float | None = None,
    inner_radius2: float | None = None,
    inner_diameter1: float | None = None,
    inner_diameter2: float | None = None,
    realign: bool = False,
    length: float | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    orient: Sequence[float] = UP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """BOSL2 tube() -- a hollow cylindrical tube.

    Note: BOSL2's outer-radius parameters are named `or`/`or1`/`or2`, which collide with the
    Python keyword `or`; they are exposed here as `outer_radius`/`outer_radius1`/`outer_radius2` instead.

    Args:
        height/length:      height of the tube (default 1)
        outer_radius:  outer radius of the tube (BOSL2 `or`) (default 1)
        inner_radius:       inner radius of the tube
        center:   if given, overrides anchor (True -> CENTER, False -> DOWN)
        outer_diameter:       outer diameter of the tube
        inner_diameter:       inner diameter of the tube
        wall:     horizontal wall thickness (default 1)
        outer_radius1/outer_radius2: outer radius of the bottom/top (BOSL2 `or1`/`or2`)
        outer_diameter1/outer_diameter2:  outer diameter of the bottom/top
        inner_radius1/inner_radius2:  inner radius of the bottom/top
        inner_diameter1/inner_diameter2:  inner diameter of the bottom/top
        realign:  rotate by half the angle of one face (default False)
        anchor:   anchor point (default CENTER)
        spin:     Z-axis rotation in degrees after anchor (default 0)
        orient:   direction to rotate the top towards, after spin (default UP)
        fn/fa/fs: arc smoothness overrides

    Examples:
        .. pythonscad-example::

            shape = pybosl2.shapes3d.tube(height=20, outer_radius=15, inner_radius=10)
            shape.show()
    """
    height = height if height is not None else (length if length is not None else 1)
    orr1 = _pick_radius(
        radius1=outer_radius1,
        diameter1=outer_diameter1,
        radius=outer_radius,
        diameter=outer_diameter,
        dflt=None,
    )
    orr2 = _pick_radius(
        radius1=outer_radius2,
        diameter1=outer_diameter2,
        radius=outer_radius,
        diameter=outer_diameter,
        dflt=None,
    )
    irr1 = _pick_radius(
        radius1=inner_radius1,
        diameter1=inner_diameter1,
        radius=inner_radius,
        diameter=inner_diameter,
        dflt=None,
    )
    irr2 = _pick_radius(
        radius1=inner_radius2,
        diameter1=inner_diameter2,
        radius=inner_radius,
        diameter=inner_diameter,
        dflt=None,
    )
    wall_v = wall if wall is not None else 1
    rad1 = orr1 if orr1 is not None else (irr1 + wall_v if irr1 is not None else None)
    rad2 = orr2 if orr2 is not None else (irr2 + wall_v if irr2 is not None else None)
    irad1 = irr1 if irr1 is not None else (orr1 - wall_v if orr1 is not None else None)
    irad2 = irr2 if irr2 is not None else (orr2 - wall_v if orr2 is not None else None)
    assert rad1 is not None and rad2 is not None and irad1 is not None and irad2 is not None, (
        "tube(): must specify two of inner radius/diam, outer radius/diam, and wall width."
    )
    assert irad1 <= rad1 and irad2 <= rad2, "tube(): inner radius is larger than outer radius."

    use_anchor = anchor
    if center is not None:
        use_anchor = CENTER if center else BOTTOM

    outer = _ocylinder(
        height=height,
        radius1=rad1,
        radius2=rad2,
        center=True,
        fn=fn,
        fa=fa,
        fs=fs,
    )
    inner = _ocylinder(
        height=height + 0.02,
        radius1=irad1,
        radius2=irad2,
        center=True,
        fn=fn,
        fa=fa,
        fs=fs,
    )
    shape = outer - inner
    if realign:
        sides = _frag_count(max(rad1, rad2), fn, fa, fs)
        shape = shape.rotate(180 / sides, [0, 0, 1])
    offset = _anchor_offset_cyl(rad1, rad2, height, use_anchor)
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=None, anchor=use_anchor)


def pie_slice(
    height: float | None = None,
    radius: float | None = None,
    angle: float = 30,
    center: bool | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    length: float | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    orient: Sequence[float] = UP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """BOSL2 pie_slice() -- a pie slice, wedge of a cylinder/cone.

    Args:
        height/length:    height of the pie slice
        radius:      radius of the pie slice
        angle:    pie slice angle in degrees (default 30)
        center: if given, overrides anchor
        radius1/radius2:  bottom/top radius of the pie slice
        diameter/diameter1/diameter2: diameter of the pie slice / bottom / top
        anchor: anchor point (default CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)
        orient: direction to rotate the top towards, after spin (default UP)
        fn/fa/fs: arc smoothness overrides
    """
    from .shapes2d import _arc_points, _opolygon

    length = height if height is not None else (length if length is not None else 1)
    rad1 = _pick_radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=10)
    rad2 = _pick_radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter, dflt=10)
    use_anchor = anchor
    if center is not None:
        use_anchor = CENTER if center else BOTTOM

    base = _ocylinder(
        height=length,
        radius1=rad1,
        radius2=rad2,
        center=True,
        fn=fn,
        fa=fa,
        fs=fs,
    )
    if isinstance(angle, (list, tuple)):  # [start, end] wedge
        start, sweep = float(angle[0]), float(angle[1]) - float(angle[0])
    else:
        start, sweep = 0.0, float(angle)
    ang_v = sweep % 360 if (sweep > 360 or sweep < 0) else sweep
    if ang_v <= 0 or ang_v >= 360:
        shape = base
    else:
        maxd = max(rad1, rad2) + 0.1
        sides = max(3, math.ceil(_frag_count(maxd, fn, fa, fs) * ang_v / 360))
        arc = _arc_points(sides, maxd, start, ang_v)
        sector = _opolygon([[0.0, 0.0]] + arc).linear_extrude(height=length + 0.2, center=True)
        shape = base & sector

    offset = _anchor_offset_cyl(rad1, rad2, length, use_anchor)
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=None, anchor=use_anchor)


# ---------------------------------------------------------------------------
# Section: Other Round Objects
# ---------------------------------------------------------------------------


def sphere(
    radius: float | None = None,
    diameter: float | None = None,
    circumscribe: bool = False,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    orient: Sequence[float] = UP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """A sphere, built with the builtin sphere(), with BOSL2-style anchor/spin/orient support.

    Note: `style=` is accepted for signature compatibility but not applied; the
    builtin sphere() is used directly.

    Args:
        radius:      radius of the sphere
        diameter:      diameter of the sphere
        circumscribe:  circumscribe rather than inscribe the sphere (default False)
        anchor: anchor point (default CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)
        orient: direction to rotate the top towards, after spin (default UP)
        fn/fa/fs: arc smoothness overrides

    Examples:
        .. pythonscad-example::

            shape = pybosl2.shapes3d.sphere(radius=15)
            shape.show()
    """
    rad = radius if radius is not None else (diameter / 2 if diameter is not None else 1)
    if circumscribe:
        sides = _frag_count(rad, fn, fa, fs)
        rad /= math.cos(math.pi / sides)
    shape = _osphere(radius=rad, fn=fn, fa=fa, fs=fs)
    offset = _anchor_offset_sphere(rad, anchor)
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=None, anchor=anchor)


def spheroid(
    radius: float | None = None,
    diameter: float | None = None,
    circumscribe: bool = False,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    orient: Sequence[float] = UP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """An approximate sphere; this pure-Python port just builds a plain sphere() (style/dual are ignored).

    Args:
        radius:      radius of the spheroid
        diameter:      diameter of the spheroid
        circumscribe:  circumscribe rather than inscribe the spheroid (default False)
        anchor: anchor point (default CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)
        orient: direction to rotate the top towards, after spin (default UP)
        fn/fa/fs: arc smoothness overrides
    """
    return sphere(
        radius=radius,
        diameter=diameter,
        circumscribe=circumscribe,
        anchor=anchor,
        spin=spin,
        orient=orient,
        fn=fn,
        fa=fa,
        fs=fs,
    )


def _teardrop2d_path(
    radius: float,
    angle: float,
    cap_height: float | None,
    circum: bool,
    realign: bool,
    sides: int,
) -> list[list[float]]:
    """The 2-D (X,Y) outline of a BOSL2-style teardrop2d(): a circle of radius *radius* capped by a
    point (or, if *cap_height* truncates it, a flat top) formed by two walls tangent to the circle at
    +-*angle* degrees from the Y axis. *sides* is the segment count for a full circle of this radius
    (as from _frag_count()); *realign* is approximated by toggling the parity of the round
    section's vertex count, since a vertex landing exactly at the bottom gives a "point" and a
    vertex straddling it gives a "flat" bottom -- the same effect BOSL2 gets from its own $fn
    discretization.
    """
    from .shapes2d import _arc_points

    rad = radius / math.cos(math.pi / sides) if circum else radius
    maxheight = rad / math.sin(math.radians(angle))
    minheight = rad * math.sin(math.radians(angle))
    assert cap_height is None or cap_height >= minheight - 1e-9, (
        "teardrop2d(): cap_height cannot be less than radius*sin(angle)."
    )
    pointy = cap_height is None or cap_height >= maxheight

    sweep = 180 + 2 * angle
    pts = max(2, round(sides * sweep / 360)) + 1
    if realign == (pts % 2 == 1):
        pts += 1
    arc = _arc_points(pts, rad, angle, -sweep, [0.0, 0.0])

    if pointy or cap_height is None:
        return [[0.0, maxheight]] + arc
    cap_x = (maxheight - cap_height) * math.tan(math.radians(angle))
    return [[cap_x, cap_height]] + arc + [[-cap_x, cap_height]]


def _interior_fillet_path(radius: float, angle: float, overlap: float, sides: int) -> list[list[float]]:
    """The 2-D cross-section of an interior_fillet(): the wedge bounded by the corner point, the
    two tangent points on each wall (distance radius/tan(angle/2) from the corner), and the concave arc
    of radius *radius* joining them (center at distance radius/sin(angle/2) from the corner along the
    bisector) -- the generalization to arbitrary *angle* of the classic `cube() - cylinder()`
    quarter-round fillet at angle=90. Each straight wall edge is extended *overlap* past the ideal
    corner point so the piece unions cleanly onto both adjoining faces instead of meeting them at
    an exact, potentially non-manifold, edge.
    """
    from .shapes2d import _arc_points

    half = math.radians(angle / 2)
    tlen = radius / math.tan(half) if radius > 0 else 0.0
    p0 = [tlen, 0.0]
    p1 = [tlen * math.cos(math.radians(angle)), tlen * math.sin(math.radians(angle))]
    flap0 = [-overlap, 0.0]
    flap1 = [
        -overlap * math.cos(math.radians(angle)),
        -overlap * math.sin(math.radians(angle)),
    ]
    if radius <= 0:
        return [flap0, p0, p1, flap1]

    dist = radius / math.sin(half)
    center = [dist * math.cos(half), dist * math.sin(half)]
    start_a = math.degrees(math.atan2(p0[1] - center[1], p0[0] - center[0]))
    end_a = math.degrees(math.atan2(p1[1] - center[1], p1[0] - center[0]))
    sweep = ((end_a - start_a + 180) % 360) - 180
    arc_n = max(2, round(sides * abs(sweep) / 360)) + 1
    arc = _arc_points(arc_n, radius, start_a, sweep, center)
    return [flap0] + arc + [flap1]


def torus(
    major_radius: float | None = None,
    minor_radius: float | None = None,
    center: bool | None = None,
    major_diameter: float | None = None,
    minor_diameter: float | None = None,
    outer_radius: float | None = None,
    inner_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_diameter: float | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    orient: Sequence[float] = UP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """BOSL2 torus() -- a torus (donut) shape.

    Note: BOSL2's outer-radius parameter is named `or`, which collides with the Python
    keyword `or`; it is exposed here as `outer_radius` instead.

    Args:
        major_radius:  major radius of the torus ring (use with minor_radius or minor_diameter)
        minor_radius:  minor radius of the torus ring (use with major_radius or major_diameter)
        center: if given, overrides anchor (True -> CENTER, False -> DOWN)
        major_diameter:  major diameter of the torus ring
        minor_diameter:  minor diameter of the torus ring
        outer_radius: outer radius of the torus (BOSL2 `or`) (use with inner_radius or inner_diameter)
        inner_radius:     inside radius of the torus (use with outer_radius or outer_diameter)
        outer_diameter:     outer diameter of the torus (use with inner_radius or inner_diameter)
        inner_diameter:     inside diameter of the torus (use with outer_radius or outer_diameter)
        anchor: anchor point (default CENTER)
        orient: direction to rotate the top towards, after spin (default UP)
        fn/fa/fs: arc smoothness overrides

    Examples:
        .. pythonscad-example::

            shape = pybosl2.shapes3d.torus(major_radius=25, minor_radius=8)
            shape.show()
    """
    from .shapes2d import _arc_points, _opolygon

    _or = _pick_radius(radius=outer_radius, diameter=outer_diameter, dflt=None)
    _ir = _pick_radius(radius=inner_radius, diameter=inner_diameter, dflt=None)
    _r_maj = _pick_radius(radius=major_radius, diameter=major_diameter, dflt=None)
    _r_min = _pick_radius(radius=minor_radius, diameter=minor_diameter, dflt=None)

    if _r_maj is not None:
        maj_rad = _r_maj
    elif _ir is not None and _or is not None:
        maj_rad = (_or + _ir) / 2
    elif _ir is not None and _r_min is not None:
        maj_rad = _ir + _r_min
    elif _or is not None and _r_min is not None:
        maj_rad = _or - _r_min
    else:
        raise AssertionError("torus(): bad parameters.")

    if _r_min is not None:
        min_rad = _r_min
    elif _ir is not None:
        min_rad = maj_rad - _ir
    elif _or is not None:
        min_rad = _or - maj_rad
    else:
        raise AssertionError("torus(): bad parameters.")

    use_anchor = anchor
    if center is not None:
        use_anchor = CENTER if center else DOWN

    sides = _frag_count(min_rad, fn, fa, fs)
    profile = _arc_points(sides, min_rad, 0, 360, [maj_rad, 0.0], endpoint=False)
    shape = _orotate_extrude(_opolygon(profile), fn=fn, fa=fa, fs=fs)
    offset = _anchor_offset_cyl(maj_rad + min_rad, maj_rad + min_rad, min_rad * 2, use_anchor)
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=None, anchor=use_anchor)


def teardrop(
    height: float | None = None,
    radius: float | None = None,
    angle: float = 45,
    cap_height: float | None = None,
    circumscribe: bool = False,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    cap_h1: float | None = None,
    cap_h2: float | None = None,
    chamfer: float = 0,
    chamfer1: float = 0,
    chamfer2: float = 0,
    realign: bool = False,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    orient: Sequence[float] = UP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """BOSL2 teardrop() -- a teardrop shape, useful for 3D-printable horizontal holes.

    Args:
        height/l:    thickness of the teardrop (default 1)
        radius:      radius of the circular part (default 1)
        angle:    angle of the hat walls from the Z axis in degrees (default 45)
        cap_height:  height above center to truncate the shape (default: no truncation)
        circumscribe: produce a circumscribing teardrop shape (default False)
        radius1/radius2:  radius of the circular portion of the front/back end
        diameter/diameter1/diameter2: diameter of the circular portion / front end / back end
        cap_h1/cap_h2: truncation height on the front/back side
        chamfer/chamfer1/chamfer2: chamfer size along the bottom/top faces (overall/bottom/top) (default 0)
        realign: shift face alignment, passed to teardrop2d (default False)
        anchor: anchor point (default CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)
        orient: direction to rotate the top towards, after spin (default UP)
        fn/fa/fs: arc smoothness overrides
    """
    length = height if height is not None else 1.0
    rad1 = _pick_radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
    rad2 = _pick_radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter, dflt=1)
    cap_h1v = cap_h1 if cap_h1 is not None else cap_height
    cap_h2v = cap_h2 if cap_h2 is not None else cap_height
    c1 = chamfer1 if chamfer1 else chamfer
    c2 = chamfer2 if chamfer2 else chamfer
    sides = _frag_count(max(rad1, rad2), fn, fa, fs)

    def section(rad: float, cap_hv: float | None, y: float) -> list[list[float]]:
        path = _teardrop2d_path(rad, angle, cap_hv, circumscribe, realign, sides)
        return [[p[0], y, p[1]] for p in path]

    front_y, back_y = -length / 2, length / 2
    slices = []
    if c1:
        cap_hv = (cap_h1v - c1) if cap_h1v is not None else None
        slices.append(section(max(0.001, rad1 - c1), cap_hv, front_y))
        front_y += abs(c1)
    slices.append(section(rad1, cap_h1v, front_y))
    if c2:
        back_y -= abs(c2)
    slices.append(section(rad2, cap_h2v, back_y))
    if c2:
        cap_hv = (cap_h2v - c2) if cap_h2v is not None else None
        slices.append(section(max(0.001, rad2 - c2), cap_hv, back_y + abs(c2)))

    solids = [_opolyhedron(pts, [list(range(len(pts)))]) for pts in slices]
    shape = solids[0]
    for a, b in zip(solids, solids[1:], strict=False):
        piece = _ohull(a, b)
        shape = piece if shape is solids[0] else (shape | piece)
    offset = _anchor_offset_cyl(rad1, rad2, length, anchor, axis=1)
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=None, anchor=anchor)


def onion(
    radius: float | None = None,
    angle: float = 45,
    cap_height: float | None = None,
    circumscribe: bool = False,
    diameter: float | None = None,
    anchor: Sequence[float] = CENTER,
    spin: float = 0,
    orient: Sequence[float] = UP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """BOSL2 onion() -- an onion-dome shape (a sphere with a conical cap).

    Args:
        radius:      radius of the spherical portion of the bottom (default 1)
        angle:    angle of the cone from vertical in degrees (default 45)
        cap_height:  height above the sphere center to truncate the shape (default: no truncation)
        circumscribe: circumscribe rather than inscribe the given radius/diameter (default False)
        realign: adjust point alignment (flat vs pointy bottom) (default False)
        diameter:      diameter of the spherical portion of the bottom
        anchor: anchor point (default CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)
        orient: direction to rotate the top towards, after spin (default UP)
        fn/fa/fs: arc smoothness overrides
    """
    from .shapes2d import _arc_points, _opolygon

    rad = _pick_radius(radius=radius, diameter=diameter, dflt=1)
    sides = _frag_count(rad, fn, fa, fs)
    scaled = rad / math.cos(math.pi / sides) if circumscribe else rad
    maxheight = scaled / math.sin(math.radians(angle))
    top_z = min(cap_height, maxheight) if cap_height is not None else maxheight
    pointy = top_z >= maxheight - 1e-9

    sweep = 90 + angle
    pts = max(2, round(sides * sweep / 360)) + 1
    arc = list(reversed(_arc_points(pts, scaled, angle, -sweep, [0.0, 0.0])))
    if pointy:
        profile = arc + [[0.0, top_z]]
    else:
        cap_x = (maxheight - top_z) * math.tan(math.radians(angle))
        profile = arc + [[cap_x, top_z], [0.0, top_z]]

    shape = _orotate_extrude(_opolygon(profile), fn=fn, fa=fa, fs=fs)

    a = list(anchor)
    off_z = 0.0 if a[2] == 0 else (scaled if a[2] < 0 else -top_z)
    rn = math.hypot(a[0], a[1])
    off_xy = [-a[0] / rn * scaled, -a[1] / rn * scaled] if rn > 0 else [0.0, 0.0]
    offset = [off_xy[0], off_xy[1], off_z]
    return Bosl2Solid(_finish3(shape, offset, spin, orient), size=None, anchor=anchor)


# ---------------------------------------------------------------------------
# Section: Text
# ---------------------------------------------------------------------------


def _text3d_anchor_vec(anchor) -> list[float]:
    """Extracts a 3-vector from an `anchor` argument that may be a plain vector or (to
    accommodate this port's unusual `anchor: str = "baseline[-1,0,-1]"` default) a string
    with a bracketed `[x,y,z]` vector embedded in it. Falls back to LEFT if no vector can
    be found in a string anchor, matching BOSL2's own `default(anchor, center?CENTER:LEFT)`.
    """
    if isinstance(anchor, str):
        i = anchor.find("[")
        j = anchor.find("]")
        if i >= 0 and j > i:
            return [float(x) for x in anchor[i + 1 : j].split(",")]
        return [-1.0, 0.0, 0.0]
    return [float(x) for x in anchor]


def _frame_map(
    x: Sequence[float] | None = None,
    y: Sequence[float] | None = None,
    z: Sequence[float] | None = None,
) -> list[list[float]]:
    """Port of BOSL2's frame_map(): builds the 4x4 change-of-basis matrix whose columns are
    the (up to) two given unit axes plus the third axis completed via cross product, matching
    BOSL2's exact axis-completion rules (used by path_text() to orient each glyph).
    """
    xu = unit(x) if x is not None else None
    yu = unit(y) if y is not None else None
    zu = unit(z) if z is not None else None
    if xu is None:
        m = [cross(yu, zu), yu, zu]
    elif yu is None:
        m = [xu, cross(zu, xu), zu]
    elif zu is None:
        m = [xu, yu, cross(xu, yu)]
    else:
        m = [xu, yu, zu]
    return [
        [m[0][0], m[1][0], m[2][0], 0.0],
        [m[0][1], m[1][1], m[2][1], 0.0],
        [m[0][2], m[1][2], m[2][2], 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _point3d(v: Sequence[float]) -> list[float]:
    return list(v) if len(v) >= 3 else [v[0], v[1], 0.0]


def _cut_interp(pathcut: list, path: Sequence[Sequence[float]], data: Sequence[Sequence[float]]) -> list[list[float]]:
    """Port of BOSL2's `_cut_interp()`: linearly interpolates a per-path-vertex vector array
    `data` to the fractional position of each `path_cut_points()` cut point.
    """
    out = []
    for entry in pathcut:
        idx = entry[1]
        a = path[idx - 1]
        b = path[idx]
        c = entry[0]
        i = max(range(len(b)), key=lambda k: abs(b[k] - a[k]))
        factor = (c[i] - a[i]) / (b[i] - a[i])
        out.append([(1 - factor) * da + factor * db for da, db in zip(data[idx - 1], data[idx], strict=False)])
    return out


def _path_text_bcast_dir(v, dim: int, path: Sequence[Sequence[float]], label: str) -> list[list[float]] | None:
    """Broadcasts a `normal=`/`top=` argument (undefined, a single vector, or a per-path-point
    list of vectors) to a list of one vector per path point, mirroring BOSL2's normalok/topok
    argument checks (including the "3-vector with z==0 on a 2d path" compatibility form).
    """
    if v is None:
        return None
    if is_vector(v, dim):
        return [list(v)] * len(path)
    if dim == 2 and is_vector(v, 3) and abs(v[2]) < 1e-9:
        return [[v[0], v[1]]] * len(path)
    if isinstance(v, list) and len(v) == len(path) and all(is_vector(p, dim) for p in v):
        return [list(p) for p in v]
    raise ValueError(
        f'path_text(): "{label}" must be a length-{dim} vector or a list of {len(path)} such vectors matching the path.'
    )


def text3d(
    text: str,
    height: float = 1,
    size: float = 10,
    font: str = "Liberation Sans",
    halign: str | None = None,
    valign: str | None = None,
    spacing: float = 1.0,
    direction: str = "ltr",
    language: str = "em",
    script: str = "latin",
    anchor: str = "baseline[-1,0,-1]",
    spin: float = 0,
    orient: Sequence[float] = UP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """BOSL2 text3d() -- 3-D extruded text, with anchor/spin/orient support.

    Args:
        text:      text to create
        height:         extrusion height (default 1)
        size:      font size divided by 0.72 (default 10)
        font:      font to use (default "Liberation Sans")
        halign:    horizontal alignment: "left", "center", "right" (overrides anchor)
        valign:    vertical alignment: "top", "center", "baseline", "bottom" (overrides anchor)
        spacing:   relative spacing multiplier between characters (default 1.0)
        direction: text direction: "ltr", "rtl", "ttb", "btt" (default "ltr")
        language:  language the text is in (default "en")
        script:    script the text is in (default "latin")
        anchor:    anchor point (default "baseline")
        spin:      Z-axis rotation in degrees (default 0)
        orient:    direction to rotate the top towards (default UP)
    """
    av = _text3d_anchor_vec(anchor)
    ha = halign if halign is not None else ("left" if av[0] < 0 else "right" if av[0] > 0 else "center")
    va = valign if valign is not None else ("bottom" if av[1] < 0 else "top" if av[1] > 0 else "baseline")
    flat = _text2d(
        text,
        size=size,
        font=font,
        halign=ha,
        valign=va,
        spacing=spacing,
        direction=direction,
        language=language,
        script=script,
        fn=fn,
        fa=fa,
        fs=fs,
    )
    # .shape: _text2d() hands back a Bosl2Shape2D, but everything below works on raw natives
    # (_finish3) and the result is wrapped once, at the end.
    shape = flat.shape.linear_extrude(height=height, center=True, fn=fn, fa=fa, fs=fs)
    offset = _anchor_offset_box3([size, size, height], [0, 0, av[2]])
    shape = _finish3(shape, offset, spin, orient)
    return Bosl2Solid(shape, size=None, anchor=anchor)


def path_text(
    path: Sequence[Sequence[float]],
    text: str,
    font: str = "Liberation Sans",
    size: float = 10,
    thickness: float | None = None,
    lettersize: float | Sequence[float] | None = None,
    offset: float = 0,
    reverse: bool = False,
    normal: Sequence[float] | list[list[float]] | None = None,
    top: Sequence[float] | list[list[float]] | None = None,
    center: bool = False,
    textmetrics: bool = False,
    kern: float | Sequence[float] = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """BOSL2 path_text() -- places text characters along a path.

    Args:
        path:        path to place the text on
        text:        text to create
        font:        font to use (default "Liberation Sans")
        size:        font size divided by 0.72 (default 10)
        thickness:   thickness of the letters (not allowed for a 2-D path)
        lettersize:  scalar or array giving the size of the letters
        center:      center text on the path instead of starting at the first point (default False)
        offset:      distance to shift letters "up" towards the reader (default 0, 3-D paths only)
        normal:      direction(s) pointing towards the reader of the text (3-D paths only)
        top:         direction(s) pointing towards the top of the text
        reverse:     reverse the letters if true (default False, 3-D paths only)
        textmetrics: use the experimental textmetrics feature when lettersize is not given (default False)
        kern:        scalar or array giving per-letter size adjustments (default 0)
    """
    # Imported lazily (only path_text() needs it) so that everything else in this file stays
    # free of a numpy dependency -- pybosl2.paths uses numpy internally, and numpy isn't always
    # loadable inside the real PythonSCAD app (e.g. a hardened-runtime-signed build combined
    # with an ad-hoc-signed/unsigned numpy install fails library validation).

    assert len(text) > 0, "path_text(): text must be non-empty."
    assert size > 0, "path_text(): must give positive text size."
    assert normal is None or top is None, 'path_text(): cannot define both "normal" and "top".'
    dim = len(path[0])
    assert dim in (2, 3), "path_text(): must supply a 2d or 3d path."
    if dim == 2:
        assert thickness is None, "path_text(): cannot give a thickness with a 2d path."
        assert not reverse, "path_text(): reverse not allowed with a 2d path."
        assert offset == 0, "path_text(): cannot give offset with a 2d path."
        assert normal is None, 'path_text(): cannot define "normal" for a 2d path, only "top".'

    th = 1.0 if thickness is None else thickness
    sides = len(text)

    if lettersize is not None:
        lsize = [float(lettersize)] * sides if isinstance(lettersize, (int, float)) else [float(v) for v in lettersize]
        assert len(lsize) == sides, "path_text(): lettersize list must have one entry per character."
    elif textmetrics:
        lsize = [_otextmetrics(ch, font=font, size=size)["advance"][0] for ch in text]
    else:
        raise AssertionError("path_text(): textmetrics disabled -- must specify lettersize.")

    kern_list = [float(kern)] * (sides - 1) if isinstance(kern, (int, float)) else [float(v) for v in kern]
    assert len(kern_list) == sides - 1, "path_text(): kern must be a scalar or a list of length len(text)-1."

    centers = []
    prefix = 0.0
    kern_prefix = 0.0
    for i in range(sides):
        centers.append(prefix + kern_prefix + lsize[i] / 2.0)
        prefix += lsize[i]
        if i < sides - 1:
            kern_prefix += kern_list[i]
    textlength = prefix + kern_prefix

    plen = Path._path_length(path)
    assert textlength <= plen, "path_text(): path is too short for the text."
    start = (plen - textlength) / 2.0 if center else 0.0
    dists = [start + c for c in centers]

    pts = Path._path_cut_points(path, dists, direction=True)

    normal_pv = _path_text_bcast_dir(normal, 3, path, "normal")
    top_pv = _path_text_bcast_dir(top, dim, path, "top")

    if normal_pv is None:
        sign = 1.0 if reverse else -1.0
        normpts = [[sign * v for v in p[3]] for p in pts]
    else:
        normpts = _cut_interp(pts, path, normal_pv)
    toppts = None if top_pv is None else _cut_interp(pts, path, top_pv)

    _usetop = top_pv is not None
    usernorm = normal_pv is not None

    letters = []
    for i, ch in enumerate(text):
        tangent = pts[i][2]
        if toppts is not None:
            tt = toppts[i]
            proj = sum(a * b for a, b in zip(tangent, tt, strict=False)) / sum(v * v for v in tt)
            adjustment = [proj * v for v in tt]
        elif usernorm:
            nn = normpts[i]
            proj = sum(a * b for a, b in zip(tangent, nn, strict=False)) / sum(v * v for v in nn)
            adjustment = [proj * v for v in nn]
        else:
            adjustment = [0.0] * dim
        x_axis = [tangent[k] - adjustment[k] for k in range(dim)]

        # .shape: the letters are composed as raw natives and wrapped once, at the end.
        glyph = (
            _text2d(ch, size=size, font=font, halign="left", valign="baseline", fn=fn, fa=fa, fs=fs)
            .translate([-lsize[i] / 2.0, 0])
            .shape
        )

        if dim == 3:
            z_axis = None if toppts is not None else normpts[i]
            y_axis = toppts[i] if toppts is not None else None
            m = _frame_map(x=x_axis, y=y_axis, z=z_axis)
            letter = glyph.linear_extrude(height=th, fn=fn, fa=fa, fs=fs).translate([0.0, 0.0, offset - th / 2.0])
        else:
            y_axis = toppts[i] if toppts is not None else [-v for v in normpts[i]]
            m = _frame_map(x=_point3d(x_axis), y=_point3d(y_axis))
            letter = glyph

        letters.append(letter.multmatrix(m).translate(pts[i][0]))

    result = letters[0]
    for s in letters[1:]:
        result = result | s

    return Bosl2Solid(result, size=None, anchor=CENTER)


# ---------------------------------------------------------------------------
# Advanced surface / plot / ruler builders live in pybosl2/surfaces3d.py. They are re-exported here
# LAZILY (module __getattr__) so `from pybosl2.shapes3d import heightfield` keeps working without an
# import cycle: surfaces3d imports the core names (Bosl2Solid, _finish3, ...) from this module, so
# this module must not import surfaces3d at load time.
# ---------------------------------------------------------------------------
_SURFACE_EXPORTS = frozenset(
    {
        "interior_fillet",
        "heightfield",
        "cylindrical_heightfield",
        "plot3d",
        "plot_revolution",
        "fillet",
        "textured_tile",
        "ruler",
    }
)


def __getattr__(name):
    """Lazily resolve the surfaces3d re-exports (PEP 562), breaking the shapes3d<->surfaces3d cycle."""
    if name in _SURFACE_EXPORTS:
        import pybosl2.surfaces3d as _surfaces3d

        return getattr(_surfaces3d, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

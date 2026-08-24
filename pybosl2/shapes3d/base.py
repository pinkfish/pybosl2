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
from typing import TYPE_CHECKING, cast

import numpy as np

from pybosl2._backend import backend_only
from pybosl2._edges_lang import Anchor, EdgeAtom, resolve_anchor
from pybosl2._native import native

if TYPE_CHECKING:
    import os
    from collections.abc import Sequence
    from pathlib import Path as FilePath

    from openscad import PyOpenSCAD

    from pybosl2._backend import Solid
    from pybosl2.path2d import Path2D
    from pybosl2.path3d import Path3D
    from pybosl2.shapes2d import Bosl2Shape2D
    from pybosl2.vnf import VNF
from pybosl2._anchoring import Anchorable
from pybosl2._helpers import frag_count as _frag_count
from pybosl2._helpers import pick_radius as _pick_radius
from pybosl2._helpers import unwrap
from pybosl2._shape import BaseShape as BaseShape
from pybosl2.bounds import Bounds3D
from pybosl2.defaults import resolve_facets as _resolve_facets
from pybosl2.enums import AttachTag
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.partitions import Partitionable
from pybosl2.path2d import Path2D
from pybosl2.points import Point
from pybosl2.vectors import unit

if TYPE_CHECKING:  # real stub-typed imports for the checker (identical to pre-lazy)
    from pythonscad import cube as _ocube
    from pythonscad import cylinder as _ocylinder_native
    from pythonscad import hull as _ohull
    from pythonscad import minkowski as _ominkowski
    from pythonscad import osimport as _oosimport
    from pythonscad import polyhedron as _opolyhedron
    from pythonscad import rotate_extrude as _orotate_extrude
    from pythonscad import sphere as _osphere_native
    from pythonscad import textmetrics as _otextmetrics
else:
    _ocube = native("cube")
    _ocylinder_native = native("cylinder")
    _ohull = native("hull")
    _ominkowski = native("minkowski")
    _oosimport = native("osimport")
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
    """Return the native cylinder, accepting this file's full-word kwargs (native wants h/r/radius1/radius2).

    Whatever the caller left as None comes from the ambient defaults
    (:func:`pybosl2.defaults.use_defaults`) before the renderer's own $fa/$fs.
    """
    fn, fa, fs = _resolve_facets(fn, fa, fs)
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
    """Return the native sphere, accepting this file's full-word kwargs (native wants r).

    Whatever the caller left as None comes from the ambient defaults
    (:func:`pybosl2.defaults.use_defaults`) before the renderer's own $fa/$fs.
    """
    fn, fa, fs = _resolve_facets(fn, fa, fs)
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


@backend_only("csg")
def osimport(
    file: str,
    convexity: int | None = None,
    origin: "Sequence[float] | None" = None,
    center: bool | None = None,
) -> "Bosl2Solid":
    """Import a 3-D mesh (STL, OFF, 3MF, AMF) as a :class:`Bosl2Solid` (OpenSCAD ``import()``).

    The wrapped counterpart of the bare native ``osimport()``, so an imported mesh joins the
    fluent API instead of being a raw handle a caller has to keep unwrapping -- it can be
    anchored, transformed, coloured and cut like any other solid.

    Relative paths resolve against the PROCESS working directory, not the calling module, so
    pass an absolute path if the asset lives beside your source.

    Use :func:`pybosl2.shapes2d.osimport` for 2-D drawings (SVG/DXF).

    Args:
        file: Path to the mesh to import.
        convexity: Convexity hint for preview rendering.
        origin: For 2-D formats read as 3-D, the origin offset.
        center: Center the imported mesh on the origin.

    Returns:
        A :class:`Bosl2Solid` wrapping the imported mesh.

    Examples:
        An imported STL, cut down to its bottom half:

        .. pythonscad-example::

            from pybosl2.shapes3d import osimport, cuboid

            (osimport("part.stl") - cuboid([100, 100, 50]).up(25)).show()

    """
    kwargs: dict[str, object] = {}
    for value, name in ((convexity, "convexity"), (origin, "origin"), (center, "center")):
        if value is not None:
            kwargs[name] = value
    return Bosl2Solid(_oosimport(file, **kwargs))


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


class CsgSolid(BaseShape, Anchorable, Partitionable):
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

    #: Which backend produced this solid -- always "csg", because this class IS the exact-CSG
    #: (PythonSCAD) backend's Solid; the libfive/SDF backend uses its own wrapper. It is a class
    #: constant on purpose: reading current_backend() here would make a CSG solid built inside a
    #: use_backend("sdf") block claim to be an SDF solid, and check_operand_backend() would then
    #: wave it into an SDF boolean instead of raising CrossBackendError (SPEC C-1, PLAN O-6a).
    backend = "csg"

    #: How many dimensions this shape lives in. Paired with ``backend`` as the two facts every
    #: operand check needs: mixing backends raises CrossBackendError, mixing dimensions raises
    #: naming the extrusion or projection that crosses deliberately (SPEC C-4, C-16, E-7).
    dimensions = 3

    #: The nominal anchor box (SPEC S-2a), set per instance in __init__. Declared here as well
    #: so it is *statically* visible: since Python 3.12 `isinstance` against a runtime
    #: checkable Protocol uses static lookup, and an attribute only ever assigned in
    #: __init__ makes the class fail the check it satisfies perfectly at runtime (PLAN T-6b).
    size: "list[float] | None" = None

    def __init__(
        self,
        shape: PyOpenSCAD,
        size: Sequence[float] | None = None,
        anchor: Anchor | Sequence[float] | None = None,
    ):
        """Initialize the instance.

        Args:
            shape: The native handle this wraps.
            size: The **nominal anchor box** -- the frame ``anchor=`` is measured against, which is
                deliberately not always the bounding box. A part may anchor to the box it is
                designed around (a spur gear to its pitch circle, a regular polyhedron to its
                circumsphere) while its geometry sits inside that box, or pokes outside it. So a
                `size` that disagrees with `bounds()` is not by itself a defect; `bounds()` reports
                the geometry and prefers the native bbox, and only falls back to this when the
                native accessors are missing.
            anchor: Which point of that nominal box the shape is positioned by.

        """
        self.shape = shape
        # Normalised to a list of floats so `size` matches the Shape protocol exactly; it is
        # the one public spelling of the nominal anchor box (SPEC S-2a, C-21).
        self.size: list[float] | None = None if size is None else [float(v) for v in size]
        a_val: Anchor | None
        if anchor is None:
            a_val = Anchor.CENTER
        elif isinstance(anchor, Anchor):
            a_val = anchor
        elif isinstance(anchor, str):  # pragma: no cover
            # defensive: anchor_vector() rejects the string form at every entry point that builds
            # a solid, so one never reaches the constructor.
            raise Bosl2ValueError(f"Legacy string anchor selection is not allowed: {anchor!r}")
        else:
            a_val = resolve_anchor(list(anchor))
        self.anchor = a_val

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

    def projection(self, cut: bool = False) -> "Bosl2Shape2D":
        """Return the 2-D shadow of this solid on the XY plane (OpenSCAD ``projection()``).

        With ``cut=True`` you get the cross-section where the solid crosses the z=0 plane instead
        of the full outline -- slice the solid at the height you want first.

        Returns:
            A :class:`~pybosl2.shapes2d.Bosl2Shape2D`, so the result chains straight back into the
            2-D operators (``.offset()``, ``.fill()``, ``.hull()``) and the extruders.

        Note:
            CSG only. The SDF backend's :meth:`~pybosl2.sdf.shapes3d.PyShape.projection` raises
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
        results: list[Bosl2Solid] = []
        for cp in cutlist:
            # Turn the copy to face along the path *before* moving it into place. Translating
            # first and rotating after spun each copy about the world origin instead of its own,
            # which flung them off the path -- invisible on a path running along X, where the
            # rotation happens to fix that axis, and badly wrong on anything that turns.
            copied: Bosl2Solid = self
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
            results.append(copied.translate([float(v) for v in cp.point]))
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

    def bounds(self) -> Bounds3D:
        """Return this solid's axis-aligned bounding box in its current frame (SPEC S-2b).

        Prefers the native bbox, which always reflects the actual current geometry -- this is
        what lets anchoring/attachment/masking work without the caller tracking a size, and
        stays correct after the object has been moved or combined. Falls back to the tracked
        cuboid size/anchor metadata only when the native accessors aren't available (the numeric
        test mock).

        Returns:
            The :class:`~pybosl2.bounds.Bounds3D` box, carrying ``min``/``max``, ``center``,
            ``size`` and the per-axis extents -- so ``lo, hi = solid.bounds()`` is a ``TypeError``
            rather than the silent mis-read it used to be against the old ``(center, size)`` pair.

        Raises:
            Bosl2ValueError: If the object has neither a native bounding box nor tracked size
                metadata.

        Examples:
            .. pythonscad-example::

                from pybosl2 import cuboid

                shape = cuboid([40, 30, 20])
                print(shape.bounds().size)      # (40.0, 30.0, 20.0)
                print(shape.bounds().min_z)     # -10.0
                shape.show()

        """
        center, size = self._center_size()
        return Bounds3D.from_center_size(center, size)

    @property
    def vnf(self) -> "VNF":
        """Return this solid as a mesh (SPEC C-8, S-19a).

        For a solid a sweep built, this is the very mesh it was skinned from -- kept rather than
        discarded so that returning a `Solid` (S-19a) costs the caller nothing who wanted the mesh.
        For any other solid it is meshed on demand.

        Returns:
            The :class:`~pybosl2.vnf.VNF`, with faces wound counter-clockwise seen from outside.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Path2D

                bar = Path2D([[-5, -5], [5, -5], [5, 5], [-5, 5]], closed=True).linear_sweep(height=20)
                print(bar.vnf.volume())     # 2000.0
                bar.show()

        """
        from pybosl2.vnf import VNF

        stashed = getattr(self, "_vnf", None)
        if stashed is not None:
            return cast("VNF", stashed)
        return VNF.from_solid(self)

    def export(
        self, path: "str | os.PathLike[str]", *, file_format: str | None = None, check: bool = True
    ) -> "FilePath":
        """Write this shape to a file (SPEC S-53).

        The way out of the library: a shape you have built becomes a file you can slice, share or
        diff. The mesh formats are written by pybosl2 itself, so this works wherever
        ``import pybosl2`` does -- no CAD runtime required (S-54).

        Args:
            path: destination file. Its suffix picks the format -- ``.stl``, ``.obj``, ``.off``,
                ``.ply`` -- unless *file_format* overrides it.
            file_format: explicit format name (``"stl"``, ``"stla"`` for ASCII STL, ``"obj"``,
                ``"off"``, ``"ply"``).
            check: validate the mesh first and refuse to write one that is open or inside out
                (SPEC S-55). Pass ``False`` for a surface that is open on purpose.

        Returns:
            The path written, so the call can be chained or logged.

        Raises:
            Bosl2ValueError: If the format is unknown, or *check* is on and the mesh is not a
                closed, outward-wound solid.

        Examples:
            .. pythonscad-example::

                from pybosl2 import cuboid, cyl

                bracket = cuboid([40, 30, 10], rounding=3) - cyl(radius=4, height=20)
                bracket.export("bracket.stl")
                bracket.show()

        """
        from pathlib import Path as _FilePath

        from pybosl2.export import write_mesh

        return write_mesh(self.vnf, _FilePath(path), file_format=file_format, check=check)

    def _center_size(self) -> "tuple[list[float], list[float]]":
        """Return the bounding box as the raw ``(center, size)`` pair the native layer reports."""
        nb = self._native_bounds()
        if nb is not None:
            mincorner, size = nb
            return [mincorner[i] + size[i] / 2 for i in range(3)], size
        if self.size is not None and self.anchor is not None:
            size = [float(v) for v in self.size]
            return _anchor_offset_box3(size, self.anchor), size
        raise Bosl2ValueError(
            "bounds(): object has no native bounding box and no tracked cuboid size/anchor "
            "metadata (are you calling this under the numeric mock on a non-cuboid?)"
        )

    # _resolve_bounds / anchor_point / reanchor / reorient / orient come from Anchorable
    # (pybosl2/_anchoring.py): anchor arithmetic is bounds-and-vector maths, not CSG
    # topology, so both backends share the one implementation (TASKS T14 phase 5a).

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
            cube.attach(Anchor.TOP, cyl).show()

        """
        pa = parent_anchor.vector
        ca = -pa if child_anchor is None else child_anchor.vector
        csolid = child if isinstance(child, Bosl2Solid) else Bosl2Solid(child)
        cpt = csolid.anchor_point(ca)
        placed = csolid.translate([-cpt[0], -cpt[1], -cpt[2]])
        # CENTER has no direction, so there is no pair of faces to bring together and nothing to
        # rotate -- the child keeps its own orientation. The overlap/spin handling below already
        # allows for a directionless anchor; without this guard _rot_from_to() got there first and
        # failed on the zero vector.
        if any(ca) and any(pa):
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

    # ---- edge/corner/face masking (pybosl2/masking.py), box-shaped objects ----
    #
    # These now work on ANY box-shaped object: the cutter size and box center come from
    # bounds() (tracked metadata when available, else the native bbox), so callers no longer
    # have to pass size= or keep the object as a freshly-built cuboid.
    def edge_mask(
        self,
        edges: EdgeAtom | list[EdgeAtom] = Anchor.ALL,
        except_edges: list[EdgeAtom] | None = None,
        mask: "Solid | None" = None,
        bbox: Sequence[Sequence[float]] | None = None,
        tag: AttachTag | str | None = None,
    ) -> "Bosl2Solid":
        """Cut a pre-built 3-D edge cutter along each selected edge of this box-shaped solid.

        The cutter size and box center come from :meth:`bounds`, so you don't need to pass
        *size* or keep the object as a freshly-built cuboid.

        Args:
            edges:        edges to mask (default ``"ALL"``)
            except_edges: edges to explicitly not mask
            mask:         the 3-D edge cutter to apply, as a Solid
            bbox:         override bounding box (see :meth:`_resolve_bounds`)
            tag:          override tag for attachment (default: AttachTag.REMOVE)

        """
        from pybosl2 import masking

        center, size = self._resolve_bounds(bbox)
        cutter_shape = masking.edge_mask(
            self.shape,
            edges,
            except_edges,
            mask,
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
        mask: "Path2D | Sequence[Sequence[float]] | None" = None,
        convexity: int = 10,
        bbox: Sequence[Sequence[float]] | None = None,
        radius: float | None = None,
        diameter: float | None = None,
        r: float | None = None,
        d: float | None = None,
        tag: AttachTag | str | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Bosl2Solid":
        """Cut a 2-D mask profile along each selected edge of this box-shaped solid.

        Args:
            edges:        edges to mask (default ``"ALL"``)
            except_edges: edges to explicitly not mask
            mask:         the 2-D mask cross-section, as a Path2D or a point list
            convexity:    accepted for compatibility; unused
            bbox:         override bounding box (see :meth:`_resolve_bounds`)
            radius:       rounding radius
            diameter:     rounding diameter
            r:            rounding radius alias
            d:            rounding diameter alias
            tag:          override tag for attachment (defaults to AttachTag.KEEP if negative, else AttachTag.REMOVE)
            fn:           fixed fragment count for the default roundover mask; ambient default when omitted
            fa:           minimum fragment angle for the default roundover mask
            fs:           minimum fragment size for the default roundover mask

        """
        from pybosl2 import masking

        center, size = self._resolve_bounds(bbox)

        rad = radius if radius is not None else r
        if rad is None:
            dia = diameter if diameter is not None else d
            if dia is not None:
                rad = dia / 2

        resolved_mask: Sequence[Sequence[float]] | Path2D | None = mask
        if rad is not None and resolved_mask is None:
            resolved_mask = masking.mask2d_roundover(abs(rad), fn=fn, fa=fa, fs=fs)
        if resolved_mask is not None and not isinstance(resolved_mask, Path2D):
            resolved_mask = Path2D(resolved_mask, closed=False)

        cutter_shape = masking.edge_profile(
            self.shape,
            edges,
            except_edges,
            mask=resolved_mask,
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

    # ------------------------------------------------------------------
    # Named edge treatments (SPEC S-26a, S-26b)
    #
    # `edge_mask(edges, mask=...)` makes the caller build the cutter first, which means naming the
    # parent's own dimensions -- the solid already knows them. These name the *treatment* instead
    # and fill the rest in, which is what P-1 and P-3 ask for. `edge_mask`/`edge_profile` remain
    # for a custom mask.
    # ------------------------------------------------------------------

    def round_edges(
        self,
        edges: "EdgeAtom | list[EdgeAtom]" = Anchor.ALL,
        *,
        radius: float | None = None,
        diameter: float | None = None,
        except_edges: "list[EdgeAtom] | None" = None,
        bbox: "Sequence[Sequence[float]] | None" = None,
        tag: "AttachTag | str | None" = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Bosl2Solid":
        """Round the selected edges of this solid.

        The one-call form of the roundover: it builds the mask and takes the box from
        :meth:`bounds`, so a caller never names the parent's own dimensions (SPEC S-26a, S-26b)::

            bracket.round_edges(Anchor.TOP, radius=3)

        Args:
            edges: Which edges to round, in the anchor language (default: all of them).
            radius: Rounding radius.
            diameter: Rounding diameter (alternative to *radius*; giving both is an error).
            except_edges: Edges to leave alone.
            bbox: Override bounding box (see :meth:`_resolve_bounds`).
            tag: Override tag for attachment (default: ``AttachTag.REMOVE``).
            fn: Arc smoothness override -- fixed fragment count.
            fa: Arc smoothness override -- minimum fragment angle.
            fs: Arc smoothness override -- minimum fragment size.

        Returns:
            A new solid with the treatment attached, ready to realize.

        Raises:
            Bosl2ValueError: If neither radius nor diameter is given, or both are.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Anchor, cuboid

                cuboid([40, 30, 20]).round_edges(Anchor.Z, radius=4).show()

        """
        from pybosl2._helpers import pick_radius
        from pybosl2.masking import Mask2D

        rad = pick_radius(radius=radius, diameter=diameter)
        if rad is None:
            raise Bosl2ValueError("round_edges(): give radius= or diameter=.")
        return self.edge_profile(
            edges,
            except_edges,
            mask=Mask2D.roundover(rad, fn=fn, fa=fa, fs=fs),
            bbox=bbox,
            tag=tag,
        )

    def chamfer_edges(
        self,
        edges: "EdgeAtom | list[EdgeAtom]" = Anchor.ALL,
        *,
        chamfer: float,
        height: float | None = None,
        except_edges: "list[EdgeAtom] | None" = None,
        bbox: "Sequence[Sequence[float]] | None" = None,
        tag: "AttachTag | str | None" = None,
    ) -> "Bosl2Solid":
        """Chamfer the selected edges of this solid.

        The one-call form of the chamfer, the companion to :meth:`round_edges`.

        Args:
            edges: Which edges to chamfer, in the anchor language (default: all of them).
            chamfer: Chamfer width, measured back along the first face.
            height: Chamfer height for an asymmetric chamfer (default: *chamfer*, symmetric).
            except_edges: Edges to leave alone.
            bbox: Override bounding box (see :meth:`_resolve_bounds`).
            tag: Override tag for attachment (default: ``AttachTag.REMOVE``).

        Returns:
            A new solid with the treatment attached, ready to realize.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Anchor, cuboid

                cuboid([40, 30, 20]).chamfer_edges(Anchor.Z, chamfer=3).show()

        """
        from pybosl2.masking import Mask2D

        return self.edge_profile(
            edges,
            except_edges,
            mask=Mask2D.chamfer(chamfer, height),
            bbox=bbox,
            tag=tag,
        )

    def cove_edges(
        self,
        edges: "EdgeAtom | list[EdgeAtom]" = Anchor.ALL,
        *,
        radius: float | None = None,
        diameter: float | None = None,
        except_edges: "list[EdgeAtom] | None" = None,
        bbox: "Sequence[Sequence[float]] | None" = None,
        tag: "AttachTag | str | None" = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Bosl2Solid":
        """Cove (concave fillet) the selected edges of this solid.

        The inverse of :meth:`round_edges`: it adds a concave sweep into the corner rather than
        cutting a convex one off it.

        Args:
            edges: Which edges to cove, in the anchor language (default: all of them).
            radius: Cove radius.
            diameter: Cove diameter (alternative to *radius*; giving both is an error).
            except_edges: Edges to leave alone.
            bbox: Override bounding box (see :meth:`_resolve_bounds`).
            tag: Override tag for attachment (default: ``AttachTag.REMOVE``).
            fn: Arc smoothness override -- fixed fragment count.
            fa: Arc smoothness override -- minimum fragment angle.
            fs: Arc smoothness override -- minimum fragment size.

        Returns:
            A new solid with the treatment attached, ready to realize.

        Raises:
            Bosl2ValueError: If neither radius nor diameter is given, or both are.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Anchor, cuboid

                cuboid([40, 30, 20]).cove_edges(Anchor.Z, radius=4).show()

        """
        from pybosl2._helpers import pick_radius
        from pybosl2.masking import Mask2D

        rad = pick_radius(radius=radius, diameter=diameter)
        if rad is None:
            raise Bosl2ValueError("cove_edges(): give radius= or diameter=.")
        return self.edge_profile(
            edges,
            except_edges,
            mask=Mask2D.cove(rad, fn=fn, fa=fa, fs=fs),
            bbox=bbox,
            tag=tag,
        )

    def edge_profile_asym(
        self,
        edges: EdgeAtom | list[EdgeAtom] = Anchor.ALL,
        except_edges: list[EdgeAtom] | None = None,
        mask: "Path2D | Sequence[Sequence[float]] | None" = None,
        convexity: int = 10,
        radius: float | None = None,
        diameter: float | None = None,
        r: float | None = None,
        d: float | None = None,
        tag: AttachTag | str | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Bosl2Solid":
        """Cut an asymmetric edge profile into the solid's edges."""
        return self.edge_profile(
            edges=edges,
            except_edges=except_edges,
            mask=mask,
            convexity=convexity,
            radius=radius,
            diameter=diameter,
            r=r,
            d=d,
            tag=tag,
            fn=fn,
            fa=fa,
            fs=fs,
        )

    def corner_profile(
        self,
        corners: Anchor = Anchor.ALL,
        except_corners: list[Anchor] | None = None,
        radius: float | None = None,
        diameter: float | None = None,
        mask: "Path2D | Sequence[Sequence[float]] | None" = None,
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
            mask:           the 2-D mask cross-section, as a Path2D or a point list
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
            mask=(None if mask is None else (Path2D(mask, closed=False) if not isinstance(mask, Path2D) else mask)),
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
            resolved_rad = _pick_radius(radius=rad, diameter=dia, dflt=None)
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
        mask: "Path2D | Sequence[Sequence[float]] | None" = None,
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
            mask=(None if mask is None else (Path2D(mask, closed=False) if not isinstance(mask, Path2D) else mask)),
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
            resolved_rad = _pick_radius(radius=rad, diameter=dia, dflt=None)
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

        box = self.bounds()
        return cuboid([extent + 2 * excess for extent in box.size]).translate(list(box.center))

    def offset3d(
        self,
        radius: float,
        size: float = 1000,
        convexity: int = 10,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Bosl2Solid":
        """Expand (or, for negative *radius*, contract) the surface of this solid by *radius*.

        Uses ``minkowski()`` with a sphere and is *very* slow; use sparingly.

        Args:
            radius: Distance to expand by; negative contracts.
            size: Size of the enclosing cube used for the negative case.
            convexity: Accepted for signature compatibility; unused.
            fn: Facet count for the minkowski sphere; ambient default when omitted.
            fa: Minimum fragment angle for that sphere.
            fs: Minimum fragment size for that sphere.

        Returns:
            The offset solid.

        """
        _ = convexity
        from pythonscad import cube as _cube
        from pythonscad import minkowski as _mink
        from pythonscad import sphere as _sphere

        if radius == 0:
            return self
        sides = max(8, _frag_count(abs(radius), fn, fa, fs))
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
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> "Bosl2Solid":
        """Round the corners of this solid: *radius* rounds all,.

        *outer_radius* only convex, *inner_radius* only concave. Uses
        ``offset3d`` three times and is extremely slow.

        Args:
            radius: Rounding radius for every corner.
            outer_radius: Rounding radius for convex corners only.
            inner_radius: Rounding radius for concave corners only.
            size: Size of the enclosing cube used by :meth:`offset3d`.
            fn: Facet count for the rounding spheres; ambient default when omitted.
            fa: Minimum fragment angle for those spheres.
            fs: Minimum fragment size for those spheres.

        Returns:
            The rounded solid.

        """
        orr = outer_radius if outer_radius is not None else (radius if radius is not None else 0)
        irr = inner_radius if inner_radius is not None else (radius if radius is not None else 0)
        return (
            self.offset3d(orr, size=size, fn=fn, fa=fa, fs=fs)
            .offset3d(-irr - orr, size=size, fn=fn, fa=fa, fs=fs)
            .offset3d(irr, size=size, fn=fn, fa=fa, fs=fs)
        )

    def chain_hull(self, *others: object) -> "Bosl2Solid":
        """Return this solid chain-hulled with *others*, in order."""
        from pybosl2.miscellaneous import chain_hull as _chain_hull

        return _chain_hull(self, *others)

    def minkowski_difference(self, *diffs: object, size: float = 1000) -> "Bosl2Solid":
        """Carve *diffs* out of this solid's surface."""
        from pybosl2.miscellaneous import minkowski_difference as _minkowski_difference

        return _minkowski_difference(self, *diffs, size=size)


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
    from pybosl2._helpers import anchor_offset_box3

    return anchor_offset_box3(size, anchor)


def _anchor_offset_hull3(points: Sequence[Sequence[float]], anchor: Anchor | Sequence[float]) -> list[float]:
    from pybosl2._helpers import anchor_offset_hull3

    return anchor_offset_hull3(points, anchor)


def _anchor_offset_cyl(
    radius1: float,
    radius2: float,
    length: float,
    anchor: Anchor | Sequence[float],
    axis: int = 2,
) -> list[float]:
    from pybosl2._helpers import anchor_offset_cyl

    return anchor_offset_cyl(radius1, radius2, length, anchor, axis)


Bosl2Solid = CsgSolid

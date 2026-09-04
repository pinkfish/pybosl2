# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


# The 3-D layer: PyShape (the lazy symbolic-SDF solid) and every 3-D shape constructor --
# cuboid/cube/sphere/cyl-family/torus/tube/pie_slice/prismoid/rect_tube/wedge/octahedron/
# convex_polyhedron/teardrop/onion/heightfield, the standalone cutters
# (interior_fillet/rounding_edge_mask/polygon_extrude), and polygon_prism (the
# offset_sweep-equivalent extrusion with rim treatments). See pybosl2/sdf/__init__.py's
# module docstring for the design rationale.
#

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Callable, NoReturn, Self, cast

import numpy as np

from pybosl2._anchoring import Anchorable
from pybosl2._backend import check_operand_backend as _check_operand_backend
from pybosl2._backend import unsupported_feature as _unsupported_feature
from pybosl2._edges_lang import Anchor, resolve_anchor
from pybosl2._native import native
from pybosl2.bounds import Bounds3D
from pybosl2.color import Colorable
from pybosl2.distributors import Distributable
from pybosl2.enums import EdgeMode
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.groups import resolve_center_anchor
from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D
from pybosl2.paths import require_path
from pybosl2.sdf._constants import BOTTOM, CENTER, FRONT, LEFT, TOP
from pybosl2.sdf._libfive import LVTree, lv
from pybosl2.sdf.edges import (
    _anchor_offset_box3,
    _anchor_offset_cyl,
    _anchor_offset_hull3,
    _anchor_offset_sphere,
    _pick_radius,
)
from pybosl2.sdf.edges import (
    edges as resolve_edges,
)
from pybosl2.sdf.paths import (
    _PENALTY,
    _SQRT2,
    _ccw,
    _convex_deficiency_sdf,
    _lv_hypot,
    _polygon_dist2_xy,
    _polygon_sdf_xy,
    _radius,
    _rect2d,
    as_path_list,
    as_points,
)

if TYPE_CHECKING:
    import os
    from collections.abc import Sequence
    from pathlib import Path as FilePath

    from numpy.typing import ArrayLike, NDArray

    from pybosl2._edges_lang import EdgeAtom
    from pybosl2.caps import CapSpec
    from pybosl2.textures import TextureData, TextureType
    from pybosl2.vnf import VNF


def _place(
    shape: PyShape,
    offset: "Sequence[float]",
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
) -> PyShape:
    """Anchor, spin and orient a freshly built field, in the order the CSG backend uses.

    SPEC PAR-4 asks for the same *options* on both backends, not just the same shapes, and `spin`
    and `orient` were missing from every SDF constructor -- 38 of the 176 gaps the option-parity
    check found. They are pure placement: a rotation about Z and a rotation of +Z onto the
    requested direction, which a distance field expresses exactly. Nothing about F-Rep made them
    hard; they had simply never been written.

    The order matches `pybosl2.shapes3d.base._finish3` -- offset, then spin, then orient -- because
    PAR-5 requires an identical call to place a shape identically on either backend, and these
    three do not commute.

    Args:
        shape: The field just built, centred on the origin.
        offset: The anchor offset to translate by.
        spin: Rotation about Z in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.

    Returns:
        The placed shape.

    """
    if any(offset):
        shape = shape.translate([float(v) for v in offset])
    if spin:
        shape = shape.rotate(float(spin), [0, 0, 1])
    direction = list(orient.vector) if isinstance(orient, Anchor) else [float(v) for v in orient]
    if direction == [0.0, 0.0, 1.0]:
        return shape
    if direction == [0.0, 0.0, -1.0]:
        return shape.rotate(180.0, [1, 0, 0])
    axis = [
        0.0 * direction[2] - 1.0 * direction[1],
        1.0 * direction[0] - 0.0 * direction[2],
        0.0 * direction[1] - 0.0 * direction[0],
    ]
    scale = math.sqrt(sum(v * v for v in axis))
    if scale < 1e-12:
        return shape
    axis = [v / scale for v in axis]
    unit_z = direction[2] / math.sqrt(sum(v * v for v in direction))
    angle = math.degrees(math.acos(max(-1.0, min(1.0, unit_z))))
    return shape.rotate(angle, axis)


def _matmul3(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _axis_angle_matrix(deg: float, axis: list[float]) -> list[list[float]]:
    """Return the Rodrigues' rotation matrix for `deg` degrees around `axis` (need not be unit)."""
    angle = math.radians(deg)
    n = math.sqrt(sum(a * a for a in axis))
    ax, ay, az = (a / n for a in axis)
    c, s, t = math.cos(angle), math.sin(angle), 1 - math.cos(angle)
    return [
        [t * ax * ax + c, t * ax * ay - s * az, t * ax * az + s * ay],
        [t * ax * ay + s * az, t * ay * ay + c, t * ay * az - s * ax],
        [t * ax * az - s * ay, t * ay * az + s * ax, t * az * az + c],
    ]


def _rotation_matrix(a: float | Sequence[float], v: list[float] | None = None) -> list[list[float]]:
    """Return a 3x3 rotation matrix matching the real rotate(obj, a, v)'s two calling conventions.

    `a` a lone angle (degrees) with an explicit axis `v`; `a` a 3-vector of Euler angles [x, y, z]
    applied X-then-Y-then-Z (the composition order OpenSCAD's own rotate([x, y, z]) uses); or `a` a
    lone angle with no axis, which turns about Z exactly as OpenSCAD's rotate(a) does -- the CSG
    backend accepts that form, so this one must too (SPEC PAR-4).
    """
    if v is not None:
        return _axis_angle_matrix(cast("float", a), v)
    if isinstance(a, (int, float)):
        return _axis_angle_matrix(float(a), [0, 0, 1])
    ax, ay, az = a
    rx = _axis_angle_matrix(ax, [1, 0, 0])
    ry = _axis_angle_matrix(ay, [0, 1, 0])
    rz = _axis_angle_matrix(az, [0, 0, 1])
    return _matmul3(_matmul3(rz, ry), rx)


def _rounded_box_sdf(x: LVTree, y: LVTree, z: LVTree, size: list[float], r: float) -> LVTree:
    """Return the exact SDF for a box uniformly rounded on every edge and corner.

    The Minkowski sum of a box (shrunk by `r` on every side) with a sphere of radius `r` -- the
    same construction pybosl2.shapes3d.cuboid() itself special-cases via a real minkowski() for
    edges="ALL". Unlike _cuboid_edge_sdf()'s general per-axis-plane composition (max() of three
    independently rounded-rectangle extrusions, which only *approximates* the true corner blend and
    leaves a visible seam where the three rounded faces meet), this is a single closed-form
    expression with an exact, seamless spherical corner -- no per-axis composition, so no seam.
    """
    hx, hy, hz = [s / 2 - r for s in size]
    qx = lv.abs(x) - hx
    qy = lv.abs(y) - hy
    qz = lv.abs(z) - hz
    mqx, mqy, mqz = lv.max(qx, 0), lv.max(qy, 0), lv.max(qz, 0)
    outside = lv.sqrt(mqx * mqx + mqy * mqy + mqz * mqz)
    inside = lv.min(lv.max(lv.max(qx, qy), qz), 0)
    return outside + inside - r


def _edge_matrices(
    amount: float,
    edge_set: list[list[int]],
    mode: EdgeMode,
) -> tuple[list[list[float]], list[list[EdgeMode]]]:
    """Return the per-edge treatment state for a single (amount, edge_set, mode) selection.

    The 3x4 amounts/modes matrices _cuboid_edge_sdf() consumes (EDGE_OFFSETS row/column order).
    """
    amounts = [[amount if edge_set[a][i] else 0.0 for i in range(4)] for a in range(3)]
    modes = [[mode] * 4 for _ in range(3)]
    return amounts, modes


def _cuboid_edge_sdf(
    x: LVTree, y: LVTree, z: LVTree, size: list[float], amounts: list[list[float]], modes: list[list[EdgeMode]]
) -> LVTree:
    """Return the cuboid SDF with independent per-edge treatment.

    `amounts[axis][i]` (rounding radius or chamfer size, per `modes[axis][i]`) in EDGE_OFFSETS
    order. Everything is folded into ONE evaluation -- chaining several treatments by
    max()-ing full cuboid SDFs (the old .round()/.chamfer() composition) leaves their zero
    sets coincident along every untreated face, which libfive's mesher refines to the bitter
    end (a plain box ballooned to ~1M triangles and minutes of meshing).
    """
    if all(m == EdgeMode.ROUND for row in modes for m in row) and len({a for row in amounts for a in row}) == 1:
        # Uniform treatment (including the plain r=0 box): the exact closed-form SDF.
        return _rounded_box_sdf(x, y, z, size, amounts[0][0])

    p = [x, y, z]
    b = [s / 2 for s in size]
    # Perpendicular-axis pairs, in the same (row, column) order as EDGE_OFFSETS: axis 0 (X)
    # varies over (Y, Z), axis 1 (Y) over (X, Z), axis 2 (Z) over (X, Y).
    axes_perp = [(1, 2), (0, 2), (0, 1)]

    def axis_sdf(axis: int) -> LVTree:
        pa, pb = axes_perp[axis]
        d2d = _rect2d(p[pa], p[pb], b[pa], b[pb], amounts[axis], modes[axis])
        slab = lv.abs(p[axis]) - b[axis]
        return lv.max(d2d, slab)

    return lv.max(lv.max(axis_sdf(0), axis_sdf(1)), axis_sdf(2))


#: Native operations that genuinely need a mesh: they consume or produce mesh topology, so
#: answering them by meshing the field is inherent rather than a silent conversion (SPEC B-5).
#: Everything a caller can do to a *field* is a real method on SdfSolid; anything not in either
#: place is refused with the explicit .to_csg() route.
#:
#: Only names SdfSolid does NOT implement belong here -- an entry that is also a real method never
#: reaches the fallback and is exactly the kind of stale record that let `projection` claim to be
#: CSG-only while working (SPEC PAR-3). tests/test_backend_parity.py checks this.
_MESH_OPERATIONS = frozenset(
    {
        # "size" used to live here, forwarding to the *meshed* solid's native size query. It is a
        # real property now -- the nominal anchor box (SPEC S-2a) -- and geometry measurement is
        # bounds(), so there is nothing left to forward.
        "linear_extrude",  # 2-D -> 3-D on the meshed profile
        "rotate_extrude",
        "offset",  # native mesh offset
        "roof",
        "background",  # the % modifier applied to the meshed solid
        "textmetrics",
    }
)


class SdfSolid(Colorable, Anchorable, Distributable):
    """Wrap a libfive SDF kept as a *symbolic* function of (x, y, z).

    Rather than an already-evaluated tree or an already-meshed solid, plus the bounding box
    (`mn`/`mx`) frep() needs and (for cuboid-shaped instances) enough metadata to add more edge
    treatments after the fact.

    Extra controls beyond a bare `frep()` call:
      - Lazy, cached meshing: the real PythonSCAD/libfive C extension is only touched by
        .mesh() (or by falling through __getattr__ to a real method like .show()/.color()),
        so a chain of edits never re-meshes early.
      - translate(v): shifts the SDF itself (`f(p) -> f(p - v)`), exact and free -- no
        meshing involved -- and keeps chamfer()/round() working correctly afterwards by
        tracking where the cuboid's own local origin currently sits.
      - Boolean composition with another PyShape (`|` union, `&` intersection, `-`
        difference) via min()/max()/negate on the two SDFs directly, cheaper and more
        exact than meshing both shapes first and doing mesh-level CSG.
      - round(radius, edges=, except_edges=) / chamfer(size, edges=, except_edges=):
        add more edge treatment to an existing cuboid-shaped PyShape. Because this
        intersects (max()) the requested treatment into the *current* SDF rather than
        rebuilding from scratch, edges can be built up incrementally with different
        treatments -- e.g. `cuboid(size).round(2, edges=Anchor.Z).chamfer(1, edges=[TOP+LEFT])`
        -- which a single pybosl2.shapes3d.cuboid() call can't do (rounding/chamfer are
        mutually exclusive there, one radius for the whole call).

    CAVEAT: like pybosl2.shapes3d.Bosl2Solid, this is a plain Python wrapper (composition),
    not a subclass of the real native PyOpenSCAD type. round()/chamfer() additionally only
    make sense for cuboid-shaped instances (built by cuboid(), or by a prior round()/
    chamfer() call on one) -- they assert if `cuboid_size` isn't set, the same restriction
    Bosl2Solid places on its own edge/corner masking methods.
    """

    #: which realize backend this Solid belongs to -- the F-Rep/SDF (libfive) backend. See
    #: pybosl2/_backend.py; Bosl2Solid is the "csg" counterpart. Lets a common Solid tell them apart
    #: and reject cross-backend booleans (CrossBackendError).
    backend = "sdf"

    #: This shape is three-dimensional; see CsgSolid.dimensions (SPEC E-7).
    dimensions = 3

    def __init__(
        self,
        sdf_fn: Callable,  # type: ignore[type-arg]
        mn: Sequence[float],
        mx: Sequence[float],
        res: int = 10,
        cuboid_size: Sequence[float] | None = None,
        cuboid_center: Sequence[float] = (0.0, 0.0, 0.0),
        cuboid_edge_amounts: list[list[float]] | None = None,
        cuboid_edge_modes: list[list[EdgeMode]] | None = None,
    ) -> None:
        self._sdf_fn = sdf_fn
        self.mn = list(mn)
        self.mx = list(mx)
        self.res = res
        self.cuboid_size = list(cuboid_size) if cuboid_size is not None else None
        self.cuboid_center = tuple(cuboid_center)
        # 3x4 per-edge treatment state (EDGE_OFFSETS order) for cuboid-shaped instances --
        # round()/chamfer() MERGE into these and rebuild one single-pass SDF instead of
        # max()-wrapping treatment layers (see _cuboid_edge_sdf's docstring for why).
        self.cuboid_edge_amounts = [row[:] for row in cuboid_edge_amounts] if cuboid_edge_amounts is not None else None
        self.cuboid_edge_modes = [row[:] for row in cuboid_edge_modes] if cuboid_edge_modes is not None else None
        self._mesh_cache = None
        self._baked_cache = None
        # appearance travels with the field and is applied when it is realized (SPEC C-19)
        self._colour: tuple[Any, float | None] | None = None
        self._modifier: str | None = None
        # the nominal anchor box (SPEC S-2a), if one was attached; metadata, like colour, so it
        # survives every exact transform rather than forcing a mesh
        self._nominal_size: list[float] | None = None
        self._nominal_anchor: Any = None

    def _wrap(
        self,
        sdf_fn: Callable,  # type: ignore[type-arg]
        mn: Sequence[float],
        mx: Sequence[float],
        cuboid_size: Sequence[float] | None = None,
        cuboid_center: Sequence[float] = (0.0, 0.0, 0.0),
        cuboid_edge_amounts: list[list[float]] | None = None,
        cuboid_edge_modes: list[list[EdgeMode]] | None = None,
    ) -> PyShape:
        out = PyShape(
            sdf_fn,
            mn,
            mx,
            self.res,
            cuboid_size,
            cuboid_center,
            cuboid_edge_amounts,
            cuboid_edge_modes,
        )
        # colour is metadata, so it survives every exact transform rather than forcing a mesh
        out._colour = self._colour
        out._modifier = self._modifier
        out._nominal_size = None if self._nominal_size is None else list(self._nominal_size)
        out._nominal_anchor = self._nominal_anchor
        return out

    def with_nominal_size(self, size: Sequence[float], anchor: Any = None) -> PyShape:
        """Return this field carrying *size* as its nominal anchor box (SPEC S-2a).

        The SDF twin of :meth:`pybosl2.shapes3d.Bosl2Solid.with_nominal_size`, so a part can name
        the frame it anchors to without reaching for a native handle -- the thing that made the
        parts library CSG-only (TASKS T14). Like colour, the box rides the field as metadata and
        survives every exact transform; `bounds()` still reports the field's own exact extents.

        Args:
            size: The nominal box, as ``[x, y, z]``.
            anchor: Which point of that box the shape is positioned by; keeps the current one when
                omitted.

        Returns:
            A new shape around the same field, with the nominal box attached.

        """
        out = self._wrap(
            self._sdf_fn,
            self.mn,
            self.mx,
            self.cuboid_size,
            self.cuboid_center,
            self.cuboid_edge_amounts,
            self.cuboid_edge_modes,
        )
        out._nominal_size = [float(v) for v in size]
        if anchor is not None:
            out._nominal_anchor = anchor
        return out

    @property
    def size(self) -> "list[float] | None":
        """The nominal anchor box, or None if this shape never had one attached (SPEC S-2a)."""
        return None if self._nominal_size is None else list(self._nominal_size)

    def _record_anchor(self, anchor: Any) -> None:
        """Note that `reanchor()` moved this field onto *anchor* (see `Anchorable`)."""
        if self._nominal_size is not None:
            self._nominal_anchor = anchor

    # ---- colour: recorded on the field, applied when it is realized (SPEC C-19) -------------

    def _recoloured(self, colour: Any, modifier: str | None) -> PyShape:
        """Return a copy of this shape carrying *colour* and *modifier*."""
        out = self._wrap(
            self._sdf_fn,
            self.mn,
            self.mx,
            self.cuboid_size,
            self.cuboid_center,
            self.cuboid_edge_amounts,
            self.cuboid_edge_modes,
        )
        out._colour = colour
        out._modifier = modifier
        return out

    def _color_native(self, c: Any = None, alpha: float | None = None) -> PyShape:
        """Record the colour; it is applied to the mesh when the shape is realized."""
        return self._recoloured((c, alpha), self._modifier)

    def _highlight_native(self) -> PyShape:
        """Record the highlight (``#``) modifier."""
        return self._recoloured(self._colour, "highlight")

    def _ghost_native(self) -> PyShape:
        """Record the ghost (``%``) modifier."""
        return self._recoloured(self._colour, "ghost")

    def _apply_appearance(self, meshed: Any) -> Any:
        """Apply any recorded colour/modifier to *meshed* and return it."""
        if self._colour is not None:
            colour, alpha = self._colour
            meshed = meshed.color(colour, alpha) if alpha is not None else meshed.color(colour)
        if self._modifier == "highlight":
            meshed = meshed.highlight()
        elif self._modifier == "ghost":
            meshed = meshed.background()
        return meshed

    def sdf(self) -> LVTree:
        """Return the fully-evaluated libfive expression tree at the real coordinate trees."""
        return self._sdf_fn(lv.x(), lv.y(), lv.z())

    def bounds(self) -> Bounds3D:
        """Return this shape's axis-aligned bounding box (SPEC S-2b).

        Exact and cheap -- every SDF constructor records its tight ``mn``/``mx``, so no meshing is
        needed (unlike measuring a CSG solid). Matches :meth:`pybosl2.shapes3d.CsgSolid.bounds`.

        Returns:
            The :class:`~pybosl2.bounds.Bounds3D` box, carrying ``min``/``max``, ``center``,
            ``size`` and the per-axis extents.

        Examples:
            .. pythonscad-example::

                from pybosl2 import cuboid, use_backend

                with use_backend("sdf"):
                    shape = cuboid([40, 30, 20])
                print(shape.bounds().size)
                shape.show()

        """
        return Bounds3D.from_min_max(self.mn, self.mx)

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
                print(bar.vnf().volume())     # 2000.0
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

        return write_mesh(self.vnf(), _FilePath(path), file_format=file_format, check=check)

    # --- The CSG-only surface, refused explicitly (SPEC C-12, C-13, PAR-3) ---------------------
    # Declared as real methods rather than left to __getattr__ so that the neutral contract can
    # carry them: attachment is part of the core object model (C-12), and "the SDF backend refuses
    # it explicitly" (C-13) is better served by a method that says why than by a missing name.
    # They are real methods for a second reason too -- since Python 3.12 `isinstance` against a
    # runtime-checkable Protocol uses static lookup, so a member supplied only by __getattr__ makes
    # `isinstance(sdf_solid, Solid)` false for a perfectly good solid (PLAN T-6b).

    def _refuse(self, feature: str) -> "NoReturn":
        """Raise the standard refusal for a CSG-only feature (SPEC B-4, E-2)."""
        from pybosl2.exceptions import UnsupportedByBackendError

        raise UnsupportedByBackendError(
            feature,
            "sdf",
            hint=(
                "attachment, tagging and the edge treatments need a shape's face and edge "
                "structure, which a distance field does not retain. Build it on the default (csg) "
                "backend, or bring this field across with `.to_csg()` first."
            ),
        )

    # These take `*_args` deliberately. A refusal must fire however it is called, and
    # copying the CSG signature verbatim made `sdf_shape.attach()` raise TypeError about
    # missing arguments instead of the error that teaches (SPEC E-2). The loose form costs
    # the contract nothing: `(*args: Any, **kwargs: Any)` satisfies any protocol signature,
    # so `Shape` declares the real one and callers are checked against that (SPEC C-23).
    # These take `*_args` deliberately. A refusal must fire however it is called, and copying
    # the CSG signature verbatim made `sdf_shape.attach()` raise TypeError about missing
    # arguments instead of the error that teaches (SPEC E-2). The loose form costs the contract
    # nothing: `(*args: Any, **kwargs: Any)` satisfies any protocol signature, so `Shape`
    # declares the real one and callers are checked against that (SPEC C-23).
    def attach(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: attachment is a CSG-backend feature (SPEC C-13)."""
        self._refuse("attach")

    def position(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: attachment is a CSG-backend feature (SPEC C-13)."""
        self._refuse("position")

    def align(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: attachment is a CSG-backend feature (SPEC C-13)."""
        self._refuse("align")

    def tag(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: tagging serves attachment, which is CSG-only (SPEC C-13)."""
        self._refuse("tag")

    def tag_this(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: tagging serves attachment, which is CSG-only (SPEC C-13)."""
        self._refuse("tag_this")

    def diff(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: tag-driven boolean resolution is CSG-only (SPEC C-13). Use `-` instead."""
        self._refuse("diff")

    def intersect(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: tag-driven boolean resolution is CSG-only (SPEC C-13). Use `&` instead."""
        self._refuse("intersect")

    def realize(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: there are no attachments to resolve; attachment is CSG-only (SPEC C-13)."""
        self._refuse("realize")

    def edge_mask(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: edge treatments are CSG-only; use the `rounding=`/`chamfer=` parameters."""
        self._refuse("edge_mask")

    def edge_profile(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: edge treatments are CSG-only; use the `rounding=`/`chamfer=` parameters."""
        self._refuse("edge_profile")

    def edge_profile_asym(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: edge treatments are CSG-only; use the `rounding=`/`chamfer=` parameters."""
        self._refuse("edge_profile_asym")

    def corner_profile(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: corner treatments are CSG-only; use the `rounding=`/`chamfer=` parameters."""
        self._refuse("corner_profile")

    def face_profile(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: face treatments are CSG-only; use the `rounding=`/`chamfer=` parameters."""
        self._refuse("face_profile")

    def round_edges(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: edge treatments are CSG-only; use `cuboid(rounding=...)` instead."""
        self._refuse("round_edges")

    def chamfer_edges(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: edge treatments are CSG-only; use `cuboid(chamfer=...)` instead."""
        self._refuse("chamfer_edges")

    def cove_edges(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: edge treatments are CSG-only, and a cove has no constructor parameter."""
        self._refuse("cove_edges")

    def projection(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: a 2-D shadow of a field has no closed form (SPEC PAR-3). Use `.to_csg()`."""
        self._refuse("projection")

    def _center_size(self) -> tuple[list[float], list[float]]:
        """Return the bounding box as the raw ``(center, size)`` pair the native layer reports."""
        box = self.bounds()
        return list(box.center), list(box.size)

    def show(self) -> "SdfSolid":
        """Hand this shape to the renderer as the output of the script, and return it.

        Meshing the field is unavoidable here and is not the implicit conversion SPEC B-5
        forbids: rendering *is* meshing, and nothing meshed is handed back — the return value is
        this SDF shape, so the chain stays in SDF-land.

        Returns:
            This shape, so the call can be chained or assigned.
        """
        self._apply_appearance(self.mesh()).show()
        return self

    def mesh(self) -> Any:
        """Mesh this SDF into a real solid via frep() (cached after the first call).

        Pads `mn`/`mx` slightly beyond the shape's own tight bounding box before sampling:
        frep()'s octree evaluator needs the surface to lie strictly *inside* the sampled
        domain to see a sign change. Every constructor here sets mn/mx to the shape's exact
        bounds (e.g. cuboid()'s +-size/2), so any flat face sits exactly on the domain
        boundary -- libfive then finds no sign change there and leaves that face unmeshed
        (a hollow shell for e.g. a rounded box/cylinder, or an entirely empty mesh for a
        plain unrounded box, whose every face is flush with the domain boundary).
        """
        if self._mesh_cache is None:
            pad = [max(1e-3, (b - a) * 0.01) for a, b in zip(self.mn, self.mx, strict=False)]
            mn = [a - p for a, p in zip(self.mn, pad, strict=False)]
            mx = [b + p for b, p in zip(self.mx, pad, strict=False)]
            self._mesh_cache = native("frep")(self.sdf(), mn, mx, self.res)
        return self._mesh_cache

    def _baked(self) -> Any:
        """Return this SDF's mesh as a plain polyhedron -- an ordinary solid, not an frep handle.

        frep() hands back a handle that still carries the libfive field, and PythonSCAD only
        supports rendering that handle: reading its bounding box (``obj.position``/``obj.size``,
        what :meth:`~pybosl2.shapes3d.Bosl2Solid.bounds` and every bbox anchor need) corrupts it,
        so the next render segfaults the app -- exit -11, empty stderr, no geometry. Reading the
        vertices/faces out and rebuilding them as a polyhedron is safe and exact (the same
        triangles libfive produced), and the result behaves like any other CSG solid: measurable,
        unionable, reusable. Cached alongside :meth:`mesh`, so the field is meshed only once.

        Falls back to the frep handle itself when the mesh has no faces to rebuild from -- an
        empty field, or the numeric test mock, whose ``mesh()`` returns points only.
        """
        if self._baked_cache is None:
            handle = self.mesh()
            verts, faces = handle.mesh()
            # polyhedron() winds its faces the opposite way round from the mesh() output; handing
            # them over as-is builds the solid inside out (see VNF.polyhedron()).
            self._baked_cache = (
                native("polyhedron")(points=verts, faces=[list(f)[::-1] for f in faces], convexity=10)
                if verts and faces
                else handle
            )
        return self._baked_cache

    def __getattr__(self, name: str) -> Any:
        # A private name is this class's own bookkeeping, probed by copy/pickle/hasattr: answer
        # the miss here rather than meshing the field (libfive) -- and rather than asking the
        # frep() handle, whose attribute lookup segfaults PythonSCAD on an unknown name.
        if name.startswith("_"):
            raise AttributeError(name)
        # A CSG-only feature (attachment/anchoring) on the SDF backend raises a clear error rather
        # than meshing (libfive) just to fail with a confusing AttributeError.
        if not (name.startswith("__") and name.endswith("__")):
            _unsupported = _unsupported_feature("sdf", name)
            if _unsupported is not None:
                raise _unsupported
        # Everything a caller can do to a *field* is implemented on this class, so anything left
        # is either an operation that genuinely needs a mesh (it consumes or produces mesh
        # topology) or a mistake. Meshing for the first is honest; meshing for the second is the
        # silent, lossy conversion SPEC B-5 forbids -- so say so instead (PLAN E-P6).
        if name in _MESH_OPERATIONS:
            return getattr(self.mesh(), name)
        from pybosl2.exceptions import UnsupportedByBackendError

        raise UnsupportedByBackendError(
            name,
            "sdf",
            hint=f"the sdf backend has no {name!r}. If you want it on the meshed solid, convert "
            f"explicitly with .to_csg().{name}(...) -- that is a one-way trip out of the field.",
        )

    # ---- SDF-level composition ----

    def translate(self, v: Sequence[float]) -> PyShape:
        tx, ty, tz = (list(v) + [0.0, 0.0, 0.0])[:3]
        fn = self._sdf_fn
        new_fn = lambda x, y, z: fn(x - tx, y - ty, z - tz)  # noqa: E731
        new_mn = [self.mn[0] + tx, self.mn[1] + ty, self.mn[2] + tz]
        new_mx = [self.mx[0] + tx, self.mx[1] + ty, self.mx[2] + tz]
        new_center = (
            self.cuboid_center[0] + tx,
            self.cuboid_center[1] + ty,
            self.cuboid_center[2] + tz,
        )
        return self._wrap(
            new_fn,
            new_mn,
            new_mx,
            self.cuboid_size,
            new_center,
            self.cuboid_edge_amounts,
            self.cuboid_edge_modes,
        )

    def rotate(self, a: float | Sequence[float] | None = None, v: Sequence[float] | None = None) -> PyShape:
        """Rotate the SDF itself (`f(p) -> f(R^-1 p)`), exact and free -- no meshing involved.

        So (like translate()) a shape can still be .round()ed/.chamfer()ed/composed afterward
        without forcing an early mesh. Matches the real rotate(obj, a, v)'s two calling
        conventions: `rotate(angle, axis)`, or `rotate([x, y, z])` for Euler angles.

        Unlike translate(), this drops cuboid_size/cuboid_center metadata (so round()/chamfer()
        assert afterward) -- edges="TOP"/"LEFT"/etc. are global-frame selectors, evaluated
        before any rotation, the same order pybosl2's own anchor/edges-then-spin/orient applies
        them in, so treating edges post-rotation wouldn't mean what it looks like it means.

        Args:
            a: The shape or value to combine.
            v: The vector.

        """
        if a is None:
            raise Bosl2ValueError("rotate(): give an angle (with an axis) or a list of Euler angles.")
        m = _rotation_matrix(a, list(v) if v is not None else None)
        mt = [[m[j][i] for j in range(3)] for i in range(3)]  # transpose == inverse for a rotation
        fn = self._sdf_fn
        new_fn = lambda x, y, z: fn(  # noqa: E731
            mt[0][0] * x + mt[0][1] * y + mt[0][2] * z,
            mt[1][0] * x + mt[1][1] * y + mt[1][2] * z,
            mt[2][0] * x + mt[2][1] * y + mt[2][2] * z,
        )
        corners = [
            [
                self.mn[0] if i & 1 == 0 else self.mx[0],
                self.mn[1] if i & 2 == 0 else self.mx[1],
                self.mn[2] if i & 4 == 0 else self.mx[2],
            ]
            for i in range(8)
        ]
        rotated = [[sum(m[r][k] * c[k] for k in range(3)) for r in range(3)] for c in corners]
        new_mn = [min(c[i] for c in rotated) for i in range(3)]
        new_mx = [max(c[i] for c in rotated) for i in range(3)]
        return self._wrap(new_fn, new_mn, new_mx)

    # ---- directional moves: exact, and they keep the field (SPEC C-1, PLAN E-P6) ------------

    def right(self, x: float) -> PyShape:
        """Move this shape *x* along +X.

        Args:
            x: The X coordinate.
        """
        return self.translate([x, 0.0, 0.0])

    def left(self, x: float) -> PyShape:
        """Move this shape *x* along -X.

        Args:
            x: The X coordinate.
        """
        return self.translate([-x, 0.0, 0.0])

    def back(self, y: float) -> PyShape:
        """Move this shape *y* along +Y.

        Args:
            y: The Y coordinate.
        """
        return self.translate([0.0, y, 0.0])

    def forward(self, y: float) -> PyShape:
        """Move this shape *y* along -Y.

        Args:
            y: The Y coordinate.
        """
        return self.translate([0.0, -y, 0.0])

    def up(self, z: float) -> PyShape:
        """Move this shape *z* along +Z.

        Args:
            z: The Z coordinate.
        """
        return self.translate([0.0, 0.0, z])

    def down(self, z: float) -> PyShape:
        """Move this shape *z* along -Z.

        Args:
            z: The Z coordinate.
        """
        return self.translate([0.0, 0.0, -z])

    def scale(self, v: float | Sequence[float]) -> PyShape:
        """Scale the SDF (`f(p) -> s_min * f(p / s)`), exact zero set, no meshing involved.

        `v` a single factor or a per-axis [sx, sy, sz], matching the real scale(). The value is
        renormalized by the smallest factor so it stays a conservative (never-overestimating)
        distance under non-uniform scaling; for uniform scaling it stays exact. Drops
        cuboid_size/cuboid_center metadata (so round()/chamfer() assert afterward), same
        rationale as rotate(): edge selectors are pre-transform concepts.

        Args:
            v: The vector.

        """
        s = [float(v)] * 3 if isinstance(v, (int, float)) else [float(a) for a in v]
        if not (all((a > 0 for a in s))):
            raise Bosl2ValueError(f"scale() factors must be positive, got {s}")
        fn = self._sdf_fn
        smin = min(s)
        new_fn = lambda x, y, z: smin * fn(x / s[0], y / s[1], z / s[2])  # noqa: E731
        new_mn = [self.mn[i] * s[i] for i in range(3)]
        new_mx = [self.mx[i] * s[i] for i in range(3)]
        return self._wrap(new_fn, new_mn, new_mx)

    def mirror(self, v: Sequence[float]) -> PyShape:
        """Reflect across the plane through the origin with normal `v`, exact and free.

        `f(p) -> f(Mp)`, with M the Householder reflection, matching the real mirror(). Drops
        cuboid_size/cuboid_center metadata, same rationale as rotate(): edge selectors are
        pre-transform concepts.

        Args:
            v: The vector.

        """
        nx, ny, nz = (float(a) for a in v)
        nlen = math.sqrt(nx * nx + ny * ny + nz * nz)
        if not (nlen > 0):
            raise Bosl2ValueError("mirror() normal must be nonzero")
        nx, ny, nz = nx / nlen, ny / nlen, nz / nlen
        m = [
            [1 - 2 * nx * nx, -2 * nx * ny, -2 * nx * nz],
            [-2 * nx * ny, 1 - 2 * ny * ny, -2 * ny * nz],
            [-2 * nx * nz, -2 * ny * nz, 1 - 2 * nz * nz],
        ]
        fn = self._sdf_fn
        # A reflection is its own inverse, so the same matrix maps sample points back.
        new_fn = lambda x, y, z: fn(  # noqa: E731
            m[0][0] * x + m[0][1] * y + m[0][2] * z,
            m[1][0] * x + m[1][1] * y + m[1][2] * z,
            m[2][0] * x + m[2][1] * y + m[2][2] * z,
        )
        corners = [
            [
                self.mn[0] if i & 1 == 0 else self.mx[0],
                self.mn[1] if i & 2 == 0 else self.mx[1],
                self.mn[2] if i & 4 == 0 else self.mx[2],
            ]
            for i in range(8)
        ]
        refl = [[sum(m[r][k] * c[k] for k in range(3)) for r in range(3)] for c in corners]
        new_mn = [min(c[i] for c in refl) for i in range(3)]
        new_mx = [max(c[i] for c in refl) for i in range(3)]
        return self._wrap(new_fn, new_mn, new_mx)

    def multmatrix(self, matrix: Sequence[Sequence[float]] | np.ndarray) -> PyShape:
        """Apply a 4x4 affine transformation matrix to the SDF, exact and free.

        Args:
            matrix: The 4x4 matrix to apply.
        """
        import numpy as np

        m = np.asarray(matrix, dtype=float)
        if not (m.shape == (4, 4)):
            raise Bosl2ValueError("multmatrix requires a 4x4 matrix")
        try:
            mt = np.linalg.inv(m)
        except np.linalg.LinAlgError:
            raise Bosl2ValueError("multmatrix requires an invertible matrix") from None

        fn = self._sdf_fn

        def new_fn(x, y, z):  # type: ignore[no-untyped-def]
            return fn(
                mt[0, 0] * x + mt[0, 1] * y + mt[0, 2] * z + mt[0, 3],
                mt[1, 0] * x + mt[1, 1] * y + mt[1, 2] * z + mt[1, 3],
                mt[2, 0] * x + mt[2, 1] * y + mt[2, 2] * z + mt[2, 3],
            )

        corners = [
            [
                self.mn[0] if i & 1 == 0 else self.mx[0],
                self.mn[1] if i & 2 == 0 else self.mx[1],
                self.mn[2] if i & 4 == 0 else self.mx[2],
            ]
            for i in range(8)
        ]
        transformed = []
        for c in corners:
            cx = m[0, 0] * c[0] + m[0, 1] * c[1] + m[0, 2] * c[2] + m[0, 3]
            cy = m[1, 0] * c[0] + m[1, 1] * c[1] + m[1, 2] * c[2] + m[1, 3]
            cz = m[2, 0] * c[0] + m[2, 1] * c[1] + m[2, 2] * c[2] + m[2, 3]
            transformed.append([cx, cy, cz])

        new_mn = [min(c[i] for c in transformed) for i in range(3)]
        new_mx = [max(c[i] for c in transformed) for i in range(3)]
        # A pure translation is a translate() spelt as a matrix, so the cuboid metadata is still
        # true of the result -- and it is what tells a later difference() that this shape is a
        # plain axis-aligned box it can trim against. Any rotation or scale in the matrix turns
        # the box into something else, so the metadata is dropped as before.
        if self.cuboid_size is not None and np.allclose(m[:3, :3], np.eye(3)):
            centre = [self.cuboid_center[i] + float(m[i, 3]) for i in range(3)]
            return self._wrap(
                new_fn,
                new_mn,
                new_mx,
                self.cuboid_size,
                centre,
                self.cuboid_edge_amounts,
                self.cuboid_edge_modes,
            )
        return self._wrap(new_fn, new_mn, new_mx)

    def _distribute(self, mats: list[np.ndarray]) -> list:  # type: ignore[type-arg]
        """Return a list of multmatrix copies of this shape, one per matrix."""
        return [self.multmatrix(m) for m in mats]

    def distribute_on_path(
        self,
        path: Any,
        num_copies: int | None = None,
        spacing: float | None = None,
        start_pos: float | None = None,
        dist: list[float] | None = None,
        rotate_children: bool = True,
    ) -> PyShape:
        """Distribute copies of this solid along *path*, oriented to the 3-D path direction.

        Works identically to :meth:`~pybosl2.shapes3d.Bosl2Solid.distribute_on_path`.

        Args:
            path: A :class:`~pybosl2.path3d.Path3D`.
            num_copies: Number of copies.
            spacing: Distance between copies.
            start_pos: Starting position along the path.
            dist: Explicit list of distances from path start.
            rotate_children: If True, rotate each copy to align with the path.

        Returns:
            A :class:`PyShape` union of all positioned copies.
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
        results: list[PyShape] = []
        for cp in cutlist:
            copied = self.translate([float(v) for v in cp.point])
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

    def to_sdf(self) -> PyShape:
        """Return self since the solid is already on the SDF backend (converter no-op)."""
        return self

    def to_csg(self) -> Any:
        """Convert to the CSG backend: mesh the SDF (libfive frep) and wrap it as a Bosl2Solid.

        Exact -- the meshed surface IS the field's zero set. This is the supported bridge for mixing
        an SDF shape into CSG booleans (``csg_solid | sdf_solid.to_csg()``). Needs libfive at call
        time (like any SDF meshing).

        The mesh is rebuilt as a polyhedron on the way over so what lands in the CSG world is an
        ordinary solid: one that can be measured (bounding box, bbox anchoring), combined, and
        used more than once. Handing the frep handle straight over cannot do any of that --
        measuring it corrupts it and the render then segfaults.
        """
        from pybosl2.shapes3d import Bosl2Solid

        return Bosl2Solid(self._baked())

    def bounding_box(self, excess: float = 0) -> PyShape:
        """Return the smallest axis-aligned cuboid containing this solid, grown by *excess*.

        Uses the stored exact ``mn``/``mx`` bounds (no meshing needed).

        Args:
            excess: Extra padding added to each dimension.

        Returns:
            A new :class:`PyShape` cuboid whose bounding box encloses this solid plus
            *excess* on every side.

        Example:

            .. code-block:: python

                from pybosl2.solid import sphere, use_backend

                with use_backend("sdf"):
                    ball = sphere(radius=10)
                    box = ball.bounding_box(excess=2)
                    # box.bounds() → size=(24, 24, 24)   (20 + 2 × 2)
        """
        center = [(a + b) / 2 for a, b in zip(self.mn, self.mx, strict=False)]
        size = [b - a + 2 * excess for a, b in zip(self.mn, self.mx, strict=False)]
        return cuboid(size).translate(center)

    def inside(self, point: Sequence[float]) -> bool:
        """Return ``True`` if *point* is inside (or on) this solid's surface.

        Evaluates the signed-distance field at *point* -- exact, no meshing.

        Args:
            point: A 3-D point ``[x, y, z]``.

        Returns:
            ``True`` when the SDF at *point* is ≤ 0.
        """
        tree = self.sdf()
        d = tree(float(point[0]), float(point[1]), float(point[2]))
        return bool(float(d) <= 0)

    def chain_hull(self, *others: PyShape) -> PyShape:
        """Return the chain-hull of this shape with *others* in order.

        Hulls consecutive pairs: ``hull(self, others[0]) | hull(others[0], others[1]) | ...``.

        Args:
            *others: Additional shapes to chain-hull with.

        Returns:
            A new :class:`PyShape` that is the union of the consecutive-pair hulls.
        """
        parts = [self] + list(others)
        if len(parts) < 2:
            return self
        result: PyShape | None = None
        for i in range(len(parts) - 1):
            pair_hull = parts[i].hull(parts[i + 1])
            result = pair_hull if result is None else result | pair_hull
        return result  # type: ignore[return-value]

    def offset3d(self, radius: float) -> PyShape:
        """Expand (positive *radius*) or contract (negative *radius*) this solid's surface.

        On the SDF backend this is exact and fast -- it adds or subtracts *radius*
        from the signed-distance field.  No meshing or minkowski needed.

        Args:
            radius: Offset distance.  Positive expands outward, negative contracts inward.

        Returns:
            A new :class:`PyShape` with the offset surface.

        Example:

            .. code-block:: python

                from pybosl2.solid import cuboid, use_backend

                with use_backend("sdf"):
                    box = cuboid([10, 20, 30])
                    bigger = box.offset3d(2)   # all faces pushed out by 2 mm
                    smaller = box.offset3d(-1)  # all faces pulled in by 1 mm
        """
        fa = self._sdf_fn

        def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
            return fa(x, y, z) - float(radius)

        r = float(radius)
        return PyShape(sdf_fn, [self.mn[i] - r for i in range(3)], [self.mx[i] + r for i in range(3)], self.res)

    def round3d(
        self,
        radius: float | None = None,
        outer_radius: float | None = None,
        inner_radius: float | None = None,
    ) -> PyShape:
        """Round the corners of this solid (BOSL2 round3d()).

        *radius* rounds all edges; *outer_radius* only convex corners;
        *inner_radius* only concave corners.  Uses three offset passes on the SDF
        field -- exact and fast, no minkowski.

        Args:
            radius: Radius for all corners.
            outer_radius: Radius for convex (outer) corners only.
            inner_radius: Radius for concave (inner) corners only.

        Returns:
            A new :class:`PyShape` with rounded edges.
        """
        orr = outer_radius if outer_radius is not None else (radius if radius is not None else 0)
        irr = inner_radius if inner_radius is not None else (radius if radius is not None else 0)
        return self.offset3d(orr).offset3d(-irr - orr).offset3d(irr)

    def __or__(self, other: PyShape) -> PyShape:
        _check_operand_backend("sdf", other, 3)
        return PyShape.union(self, other)

    def __and__(self, other: PyShape) -> PyShape:
        _check_operand_backend("sdf", other, 3)
        return PyShape.intersection(self, other)

    def __sub__(self, other: PyShape) -> PyShape:
        _check_operand_backend("sdf", other, 3)
        return PyShape.difference(self, other)

    def __ror__(self, other: PyShape) -> PyShape:
        _check_operand_backend("sdf", other, 3)
        return PyShape.union(other, self)

    def __rand__(self, other: PyShape) -> PyShape:
        _check_operand_backend("sdf", other, 3)
        return PyShape.intersection(other, self)

    def __rsub__(self, other: PyShape) -> PyShape:
        _check_operand_backend("sdf", other, 3)
        return PyShape.difference(other, self)

    def __add__(self, other: Any) -> PyShape:
        try:
            len(other)
            return self.translate(other)
        except (TypeError, ValueError):
            return NotImplemented

    def __radd__(self, other: Any) -> PyShape:
        try:
            len(other)
            return self.translate(other)
        except (TypeError, ValueError):
            return NotImplemented

    def __mul__(self, other: Any) -> PyShape:
        return self.scale(other)

    def __rmul__(self, other: Any) -> PyShape:
        return self.scale(other)

    @staticmethod
    def union(*shapes: PyShape) -> PyShape:
        """Return the union of the given PyShapes (min() of their SDFs), as one PyShape.

        Accepts either varargs or a single list.
        """
        shs = _as_shape_list(shapes)
        if len(shs) == 1:
            return shs[0]
        fns = [s._sdf_fn for s in shs]

        def sdf_fn(x, y, z):  # type: ignore[no-untyped-def]
            return _balanced(lv.min, [f(x, y, z) for f in fns])

        mn = [min(s.mn[i] for s in shs) for i in range(3)]
        mx = [max(s.mx[i] for s in shs) for i in range(3)]
        return PyShape(sdf_fn, mn, mx, max(s.res for s in shs))

    @staticmethod
    def intersection(*shapes: PyShape) -> PyShape:
        """Return the intersection of the given PyShapes (max() of their SDFs), as one PyShape.

        Accepts either varargs or a single list.
        """
        shs = _as_shape_list(shapes)
        if len(shs) == 1:
            return shs[0]
        fns = [s._sdf_fn for s in shs]

        def sdf_fn(x, y, z):  # type: ignore[no-untyped-def]
            return _balanced(lv.max, [f(x, y, z) for f in fns])

        mn = [max(s.mn[i] for s in shs) for i in range(3)]
        mx = [min(s.mx[i] for s in shs) for i in range(3)]
        if not (all((mn[i] < mx[i] for i in range(3)))):
            raise Bosl2ValueError(f"intersection(): the shapes' bounding boxes don't overlap (got mn={mn}, mx={mx})")
        return PyShape(sdf_fn, mn, mx, max(s.res for s in shs))

    @staticmethod
    def difference(shape: PyShape, *tools: PyShape) -> PyShape:
        """`shape` minus the union of every `tool` (max(f, -min(tools))), as one PyShape.

        Args:
            shape: The shape to operate on.
        """
        if not (isinstance(shape, PyShape)):
            raise Bosl2ValueError(f"difference() base must be a PyShape, got {type(shape).__name__}")
        if not tools:
            return shape
        tls = _as_shape_list(tools)
        fa = shape._sdf_fn
        fns = [t._sdf_fn for t in tls]

        def sdf_fn(x, y, z):  # type: ignore[no-untyped-def]
            return lv.max(fa(x, y, z), -_balanced(lv.min, [f(x, y, z) for f in fns]))

        mn, mx = _box_after_cutting(shape, tls)
        return PyShape(sdf_fn, mn, mx, shape.res)

    # ---- cuboid-only edge treatments ----

    def _edge_treat(self, amount: float, edges: Any, except_edges: Any, mode: EdgeMode) -> PyShape:
        if not (self.cuboid_size is not None):
            raise Bosl2ValueError(f"{mode}() requires a cuboid-shaped PyShape (from pybosl2.sdf.cuboid())")
        if not (self.cuboid_edge_amounts is not None):  # pragma: no cover
            # defensive: cuboid() is the only place cuboid_size is set and it
            # always sets the amount/mode matrices with it, and every wrap carries the three
            # together, so a shape with a size but no edge state cannot exist.
            raise Bosl2ValueError(
                f"{mode}() requires the cuboid's per-edge treatment state (lost by rotate()/scale()/booleans)"
            )
        if not (self.cuboid_edge_modes is not None):  # pragma: no cover
            # defensive: cuboid() is the only place cuboid_size is set and it
            # always sets the amount/mode matrices with it, and every wrap carries the three
            # together, so a shape with a size but no edge state cannot exist.
            raise Bosl2ValueError(
                f"{mode}() requires the cuboid's per-edge treatment state (lost by rotate()/scale()/booleans)"
            )
        edge_set = resolve_edges(edges, except_edges or [])
        amounts = [row[:] for row in self.cuboid_edge_amounts]
        modes = [row[:] for row in self.cuboid_edge_modes]
        for a in range(3):
            for i in range(4):
                if edge_set[a][i]:
                    amounts[a][i] = amount
                    modes[a][i] = mode
        cx, cy, cz = self.cuboid_center
        size = self.cuboid_size
        # Rebuild ONE single-pass SDF from the merged state rather than max()-wrapping the
        # current SDF -- stacked coincident zero sets make libfive's mesher explode.
        new_fn = lambda x, y, z: _cuboid_edge_sdf(x - cx, y - cy, z - cz, size, amounts, modes)  # noqa: E731
        return self._wrap(
            new_fn,
            list(self.mn),
            list(self.mx),
            self.cuboid_size,
            self.cuboid_center,
            amounts,
            modes,
        )

    def round(
        self, radius: float, edges: EdgeAtom | list[EdgeAtom] = Anchor.ALL, except_edges: list[EdgeAtom] | None = None
    ) -> PyShape:
        """Round the selected edges by `radius`, in addition to any existing edge treatment.

        Args:
            radius: The radius.
            edges: Edges to treat.
            except_edges: Edges to spare.
        """
        return self._edge_treat(radius, edges, except_edges, EdgeMode.ROUND)

    def chamfer(
        self, size: float, edges: EdgeAtom | list[EdgeAtom] = Anchor.ALL, except_edges: list[EdgeAtom] | None = None
    ) -> PyShape:
        """Chamfer the selected edges by `size`, in addition to any existing edge treatment.

        Args:
            size: The size, one number or one per axis.
            edges: Edges to treat.
            except_edges: Edges to spare.
        """
        return self._edge_treat(size, edges, except_edges, EdgeMode.CHAMFER)

    # -- hull / projection: the counterparts of Bosl2Solid's, on the SDF side ------------------

    def hull(self, *others: Any, directions: int = 64, res: int | None = None) -> PyShape:
        """Return the convex hull of this shape, optionally together with *others*.

        See pybosl2.shapes3d.hull() for the equivalent BOSL2 hull().

        Args:
            directions: How many sample directions the hull is built from; more is smoother and slower.
            res: Sampling resolution for the SDF backend. Omitted, the ambient ``use_defaults(res=...)`` value
                applies.

        """
        args = list(self) + list(others) if isinstance(self, (list, tuple)) else [self] + list(others)

        if len(args) == 1 and isinstance(args[0], (list, tuple)) and args[0] and isinstance(args[0][0], PyShape):
            args = list(args[0])
        if not args:  # pragma: no cover - defensive: `self` is always in args, so this cannot fire
            # from the method form; kept for the day hull() also exists as a free function.
            raise Bosl2ValueError("hull() needs at least one shape or point set")

        entries: list[tuple[str, Any]] = []
        mn = [math.inf] * 3
        mx = [-math.inf] * 3
        child_res: list[Any] = []
        for a in args:
            if isinstance(a, PyShape):
                entries.append(("shape", a))
                child_res.append(a.res)
                for i in range(3):
                    mn[i] = min(mn[i], a.mn[i])
                    mx[i] = max(mx[i], a.mx[i])
            else:
                pts = np.asarray(a, dtype=float)
                if pts.ndim == 1:
                    pts = pts.reshape(1, -1)
                if not (pts.ndim == 2):
                    raise Bosl2ValueError(f"hull(): point arguments must be Nx3 array-likes, got shape {pts.shape}")
                if not (pts.shape[1] == 3):
                    raise Bosl2ValueError(f"hull(): point arguments must be Nx3 array-likes, got shape {pts.shape}")
                entries.append(("points", pts))
                for i in range(3):
                    mn[i] = min(mn[i], float(pts[:, i].min()))
                    mx[i] = max(mx[i], float(pts[:, i].max()))

        state: dict = {}  # type: ignore[type-arg]

        def planes() -> list[tuple[float, float, float, float]]:
            if "planes" not in state:
                pools = []
                for kind, v in entries:
                    if kind == "points":
                        pools.append(v)
                    else:
                        verts, _faces = v.mesh().mesh()
                        if not (verts):
                            raise Bosl2ValueError("hull(): a child shape meshed to nothing (empty geometry)")
                        pools.append(np.asarray(verts, dtype=float))
                sup = _support_points(np.concatenate(pools), directions)
                state["planes"] = _hull_planes([[float(c) for c in p] for p in sup])
            return state["planes"]  # type: ignore[no-any-return]

        def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
            terms = [nx * x + ny * y + nz * z - off for nx, ny, nz, off in planes()]
            return _balanced(lv.max, terms)

        return PyShape(
            sdf_fn,
            mn,
            mx,
            res if res is not None else (max(child_res) if child_res else 10),
        )

    def half_of(
        self,
        v: "Any" = Anchor.TOP,
        center: "bool | float | Sequence[float] | None" = None,
        s: float | None = None,
        cut_path: "Any" = None,
        cut_angle: float = 0,
        offset: float = 0,
    ) -> PyShape:
        """Keep the half of this solid on the positive side of the plane through *center* with normal *v*.

        The mask size *s* defaults to the solid's own bounding box diagonal plus margin.

        The signature matches the CSG `half_of()` exactly, defaults included (SPEC PAR-4, PAR-5):
        the two used to disagree on what a bare `half_of()` meant -- ``Anchor.TOP`` here against
        ``(1, 0, 0)`` there -- so the same code kept a different half depending on the backend,
        which is precisely what PAR-5 exists to prevent. The three profiled-cut parameters are
        CSG-only and refuse by name rather than being silently absent (SPEC B-9).

        Args:
            v: Plane normal direction (default: ``Anchor.TOP``, keeps the z >= 0 half).
            center: A point the plane passes through, or a scalar distance to shift the plane
                along *v* -- the same two forms the CSG `half_of()` takes. The scalar form used to
                raise `TypeError: 'float' object is not subscriptable` here, so a call that worked
                on one backend crashed on the other.
            s: Half of the mask's side length (auto-sized from bounds if None).
            cut_path: CSG only -- a profiled cut needs a path swept through the solid, which a
                distance field cannot express.
            cut_angle: CSG only, as *cut_path*.
            offset: CSG only, as *cut_path*.

        Returns:
            A new :class:`PyShape` representing the kept half.

        Raises:
            UnsupportedByBackendError: If a profiled-cut parameter is given.
        """
        for name, value, default in (("cut_path", cut_path, None), ("cut_angle", cut_angle, 0), ("offset", offset, 0)):
            if value != default:
                self._refuse(f"half_of({name}=)")
        v = resolve_anchor(v) if not isinstance(v, (list, tuple)) else v
        center = (0.0, 0.0, 0.0) if center is None else center
        if s is None:
            diag = [self.mx[i] - self.mn[i] for i in range(3)]
            s = 2.2 * math.sqrt(sum(d * d for d in diag)) + 2.0

        # A cube sitting entirely on the +Z side of the origin plane: rotating +Z onto *v* then
        # moving it to *center* gives the half-space that keeps the side *v* points to. (Shifting
        # it on all three axes instead, as this used to, leaves an octant -- so every half-cut
        # kept an eighth of the solid, and `right_half()` and `back_half()` kept the same one.)
        half_mask = cuboid([s] * 3).translate([0.0, 0.0, s / 2])
        # Align mask normal with the plane
        v3 = np.asarray(v, dtype=float)
        vn = float(np.linalg.norm(v3))
        if vn > 0:
            v3 = v3 / vn
            z_axis = np.array([0.0, 0.0, 1.0])
            if abs(float(np.dot(v3, z_axis))) > 0.9999:
                axis = np.array([1.0, 0.0, 0.0])
            else:
                axis = np.cross(z_axis, v3)
                axis = axis / float(np.linalg.norm(axis))
            angle = math.degrees(math.acos(float(np.dot(z_axis, v3))))
            half_mask = half_mask.rotate(angle, axis.tolist())
        # named `shift` rather than `offset`: `offset` is a parameter now (the CSG-only one), and
        # a local of the same name would shadow the value the refusal above checks
        if isinstance(center, (int, float)) and not isinstance(center, bool):
            shift = (float(center) * v3).tolist() if vn > 0 else [0.0, 0.0, 0.0]
        else:
            shift = [float(value) for value in cast("Sequence[float]", center)]
        half_mask = half_mask.translate(shift)
        return self & half_mask

    def left_half(self, x: float = 0, s: float | None = None) -> PyShape:
        """Keep the half of this solid where x ≤ *x* (negative-X half).

        Args:
            x: X-coordinate of the cutting plane.
            s: Half of the mask's side length (auto-sized from bounds if None).

        Returns:
            A new :class:`PyShape`.
        """
        return self.half_of([-1.0, 0.0, 0.0], [float(x), 0.0, 0.0], s)

    def right_half(self, x: float = 0, s: float | None = None) -> PyShape:
        """Keep the half of this solid where x ≥ *x* (positive-X half).

        Args:
            x: X-coordinate of the cutting plane.
            s: Half of the mask's side length (auto-sized from bounds if None).

        Returns:
            A new :class:`PyShape`.
        """
        return self.half_of([1.0, 0.0, 0.0], [float(x), 0.0, 0.0], s)

    def front_half(self, y: float = 0, s: float | None = None) -> PyShape:
        """Keep the half of this solid where y ≤ *y* (negative-Y half).

        Args:
            y: Y-coordinate of the cutting plane.
            s: Half of the mask's side length (auto-sized from bounds if None).

        Returns:
            A new :class:`PyShape`.
        """
        return self.half_of([0.0, -1.0, 0.0], [0.0, float(y), 0.0], s)

    def back_half(self, y: float = 0, s: float | None = None) -> PyShape:
        """Keep the half of this solid where y ≥ *y* (positive-Y half).

        Args:
            y: Y-coordinate of the cutting plane.
            s: Half of the mask's side length (auto-sized from bounds if None).

        Returns:
            A new :class:`PyShape`.
        """
        return self.half_of([0.0, 1.0, 0.0], [0.0, float(y), 0.0], s)

    def bottom_half(self, z: float = 0, s: float | None = None) -> PyShape:
        """Keep the half of this solid where z ≤ *z* (negative-Z half).

        Args:
            z: Z-coordinate of the cutting plane.
            s: Half of the mask's side length (auto-sized from bounds if None).

        Returns:
            A new :class:`PyShape`.
        """
        return self.half_of([0.0, 0.0, -1.0], [0.0, 0.0, float(z)], s)

    def top_half(self, z: float = 0, s: float | None = None) -> PyShape:
        """Keep the half of this solid where z ≥ *z* (positive-Z half).

        Args:
            z: Z-coordinate of the cutting plane.
            s: Half of the mask's side length (auto-sized from bounds if None).

        Returns:
            A new :class:`PyShape`.
        """
        return self.half_of([0.0, 0.0, 1.0], [0.0, 0.0, float(z)], s)

    # ---- native CSG passthrough methods (delegate via to_csg()) ----

    def minkowski(self, *others: PyShape) -> PyShape:
        """Minkowski sum with *others*.

        On the SDF backend this approximates the Minkowski sum as expanding
        this solid by half the diagonal of each other shape via :meth:`offset3d`.

        Args:
            *others: Additional shapes to compute the Minkowski sum with.

        Returns:
            A new :class:`PyShape`.
        """
        result = self
        for o in others:
            box = o.bounds()
            diag = math.sqrt(sum(extent**2 for extent in box.size))
            result = result.offset3d(diag / 2)
        return result

    def repair(self) -> PyShape:
        """Re-mesh this SDF solid (rebuilds the polyhedron from a fresh mesh).

        Returns:
            A new :class:`PyShape` built from a remeshed polyhedron.
        """
        return self.to_csg().repair()  # type: ignore[no-any-return]

    def render(self) -> PyShape:
        """Return self — the SDF representation is already exact (no mesh simplification needed).

        Returns:
            This :class:`PyShape` unchanged.
        """
        return self

    def resize(self, newsize: Sequence[float]) -> PyShape:
        """Scale this solid so its bounding box matches *newsize* in each axis.

        A zero component leaves that axis unchanged.

        Args:
            newsize: Target size ``[sx, sy, sz]``.  Zero entries leave the
                corresponding axis untouched.

        Returns:
            A new :class:`PyShape` scaled to the target dimensions.

        Example:

            .. code-block:: python

                from pybosl2.solid import cuboid, use_backend

                with use_backend("sdf"):
                    shape = cuboid([10, 20, 30]).resize([50, 0, 60])
                    # shape.bounds() → size=[50, 20, 60]
        """
        size = self.bounds().size
        scale_factors: list[float] = []
        for i in range(3):
            n = float(newsize[i])
            s = size[i]
            scale_factors.append(n / s if n > 0 and s > 0 else 1.0)
        return self.scale(scale_factors)

    def separate(self) -> list[PyShape]:
        """Split disconnected lumps into individual solids via CSG conversion.

        Returns:
            A list of :class:`PyShape` solids, one per connected component.
        """
        return self.to_csg().separate()  # type: ignore[no-any-return]

    def wrap(self, radius: float, fn: int | None = None) -> PyShape:
        """Bend this solid around a cylinder of *radius* via CSG conversion.

        Args:
            radius: Radius of the cylinder to wrap around.
            fn: Smoothness override for the mesh. Omitted, the ambient ``use_defaults(fn=...)`` value applies;
                ``fn=0`` opts back out to fa/fs.

        Returns:
            A new :class:`PyShape` wrapped around the cylinder.
        """
        return self.to_csg().wrap(radius, fn=fn)  # type: ignore[no-any-return]

    def pull(self, direction: Sequence[float], distance: float) -> PyShape:
        """Stretch material in *direction* by *distance* via CSG conversion.

        Args:
            direction: Direction vector ``[dx, dy, dz]`` to pull towards.
            distance: Amount to pull by.

        Returns:
            A new :class:`PyShape` with pulled geometry.
        """
        return self.to_csg().pull(direction, distance)  # type: ignore[no-any-return]

    def minkowski_difference(self, *diffs: PyShape, size: float = 1000) -> PyShape:
        """Carve *diffs* out of this solid's surface via CSG conversion.

        Args:
            *diffs: Shapes to subtract from the Minkowski-eroded surface.
            size: Bounding-box size for the CSG conversion.

        Returns:
            A new :class:`PyShape` with the difference carved out.
        """
        return self.to_csg().minkowski_difference(*diffs, size=size)  # type: ignore[no-any-return]

    def oversample(self, sides: int) -> PyShape:
        """Subdivide facets for a smoother mesh via CSG conversion.

        Args:
            sides: Number of sides to subdivide each facet to.

        Returns:
            A new :class:`PyShape` with subdivided facets.
        """
        return self.to_csg().oversample(sides)  # type: ignore[no-any-return]

    def partition(
        self,
        spread: float = 10,
        cutsize: float = 10,
        cutpath: str = "jigsaw",
        gap: float = 0,
        cutpath_centered: bool = True,
        spin: float = 0,
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> tuple[Self, Self]:
        """Split this solid into two interlocking halves via CSG conversion.

        Args:
            spread: Distance between the two halves after splitting.
            cutsize: Size of the mask beyond the part.
            cutpath: Cut pattern; ``"jigsaw"``, ``"dovetail"``, etc.
            gap: Clearance gap between the two halves.
            cutpath_centered: Whether the cut-path is centered on the split plane.
            spin: Spin angle for the cut-path.
            slop: Extra slop for 3-D printed fits.
            fn: Smoothness override. Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back
                out to fa/fs.
            fa: Minimum angle for smoothness. Omitted, the ambient ``use_defaults(fa=...)`` value applies.
            fs: Minimum segment length for smoothness. Omitted, the ambient ``use_defaults(fs=...)`` value applies.

        Returns:
            A ``(left, right)`` tuple of :class:`PyShape` solids.
        """
        parts = self.to_csg().partition(
            spread=spread,
            cutsize=cutsize,
            cutpath=cutpath,
            gap=gap,
            cutpath_centered=cutpath_centered,
            spin=spin,
            slop=slop,
            fn=fn,
            fa=fa,
            fs=fs,
        )
        return parts[0], parts[1]


# ---------------------------------------------------------------------------
# Section: Named CSG combinators (union / difference / intersection / hull)
# ---------------------------------------------------------------------------


def _as_shape_list(shapes: tuple[Any, ...]) -> list[PyShape]:
    """Return a list of PyShapes from varargs-or-single-iterable input.

    `union(a, b)` and `union([a, b])` both work, matching the two calling conventions the
    box libraries already mix (OpenSCAD-style children vs. pybosl2-style list arguments).
    """
    if len(shapes) == 1 and isinstance(shapes[0], (list, tuple)):
        shapes = tuple(shapes[0])
    out = list(shapes)
    if not (out):
        raise Bosl2ValueError("need at least one shape")
    if not all(isinstance(s, PyShape) for s in out):
        raise Bosl2ValueError(f"every argument must be a PyShape, got {[type(s).__name__ for s in out]}")
    return out


def _balanced(op: Callable[[LVTree, LVTree], LVTree], vals: list[Any]) -> LVTree:
    """Reduce `vals` with `op` as a balanced tree (depth log n) rather than a left fold.

    Depth n: same node count either way, but libfive re-evaluates the whole expression
    per sample point and shallow trees keep its interval pruning effective on wide unions.
    """
    while len(vals) > 1:
        vals = [op(vals[i], vals[i + 1]) if i + 1 < len(vals) else vals[i] for i in range(0, len(vals), 2)]
    return vals[0]


def _support_points(points: ArrayLike, n_dirs: int) -> NDArray[np.float64]:
    """Decimate a point cloud to at most `n_dirs + 6` extreme (support) points.

    For each of `n_dirs` directions spread over the sphere (a Fibonacci lattice, plus the 6
    axis directions so bounding-box extremes always survive), keep the farthest point along it.
    The hull of the survivors is an inscribed approximation of the cloud's hull: exact at
    every vertex that is the unique maximizer of some kept direction (a cuboid's 8 corners
    all are, well before n_dirs reaches double digits), with error bounded by the direction
    spacing for smooth clouds.
    """
    pts = np.asarray(points, dtype=float)
    i = np.arange(n_dirs)
    golden = math.pi * (3.0 - math.sqrt(5.0))
    zc = 1.0 - 2.0 * (i + 0.5) / n_dirs
    rad = np.sqrt(np.maximum(0.0, 1.0 - zc * zc))
    dirs = np.stack([np.cos(golden * i) * rad, np.sin(golden * i) * rad, zc], axis=1)
    axes = np.array(
        [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]],
        dtype=float,
    )
    dirs = np.concatenate([dirs, axes])
    idx = np.unique(np.argmax(pts @ dirs.T, axis=0))
    support: NDArray[np.float64] = pts[idx]
    return support


def _hull_planes(pts: list[list[float]]) -> list[tuple[float, float, float, float]]:
    """Return the supporting planes of the convex hull of `pts`.

    As (nx, ny, nz, offset) tuples with unit outward normals -- brute force over point triples
    (every non-degenerate triple whose plane has all points on one side is a hull face plane,
    deduplicated). O(n^4) in the point count, entirely fine for the tens-of-points sets
    convex_polyhedron()/hull() feed it, and it happens once in Python at construction time,
    not per SDF evaluation.
    """
    n = len(pts)
    scale = max(max(abs(v) for v in p) for p in pts) or 1.0
    eps = 1e-9 * scale

    planes: list[tuple[float, float, float, float]] = []
    seen: set = set()  # type: ignore[type-arg]
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                ax, ay, az = pts[i]
                ux, uy, uz = (pts[j][0] - ax, pts[j][1] - ay, pts[j][2] - az)
                vx, vy, vz = (pts[k][0] - ax, pts[k][1] - ay, pts[k][2] - az)
                nx, ny, nz = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
                nlen = math.sqrt(nx * nx + ny * ny + nz * nz)
                if nlen < eps * scale:
                    continue  # collinear triple
                nx, ny, nz = nx / nlen, ny / nlen, nz / nlen
                d = nx * ax + ny * ay + nz * az
                side = [nx * p[0] + ny * p[1] + nz * p[2] - d for p in pts]
                if all(abs(s) <= eps for s in side):
                    raise Bosl2ValueError("hull planes: points are coplanar -- that's a 2-D outline, not a solid")
                if all(s <= eps for s in side):
                    pass  # already outward
                elif all(s >= -eps for s in side):
                    nx, ny, nz, d = -nx, -ny, -nz, -d
                else:
                    continue  # not a supporting plane
                key = (round(nx, 7), round(ny, 7), round(nz, 7), round(d / scale, 7))
                if key in seen:
                    continue
                seen.add(key)
                planes.append((nx, ny, nz, d))
    if not (planes):
        raise Bosl2ValueError("hull planes: no supporting planes found -- are the points coplanar?")
    return planes


def _cuboid_flare_sdf(
    x: LVTree, y: LVTree, z: LVTree, size: list[float], r: float, edge_set: list[list[int]]
) -> LVTree:
    """Return the cuboid SDF with BOSL2's negative-rounding treatment on the selected edges.

    An external cove flare on the selected X/Y-axis edges: the top/bottom face extends outward
    by `r` in the horizontal direction, then a concave quarter-arc sweeps back to the side
    face -- exactly BOSL2's construction (an added edge block with a cylinder of radius `r`,
    centered `r` outward horizontally and `r` inward vertically from the edge, carved out of
    it). Z-axis edges are rejected by cuboid() itself, matching BOSL2's own assert.
    """
    p = [x, y, z]
    b = [s / 2 for s in size]
    base = lv.max(lv.max(lv.abs(x) - b[0], lv.abs(y) - b[1]), lv.abs(z) - b[2])
    d = base
    # EDGE_OFFSETS row order for axis 0 (X) and 1 (Y): the perpendicular signs run
    # [(-,-), (+,-), (-,+), (+,+)] over (horizontal-perp, z).
    for axis in (0, 1):
        hperp = 1 - axis  # the horizontal axis perpendicular to the edge direction
        for i, (sh, sz_) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
            if not edge_set[axis][i]:
                continue
            # Block: r wide just outside the side face, r tall just inside the z face.
            block = lv.max(
                lv.max(
                    lv.abs(p[axis]) - b[axis],
                    lv.abs(p[hperp] - sh * (b[hperp] + r / 2)) - r / 2,
                ),
                lv.abs(p[2] - sz_ * (b[2] - r / 2)) - r / 2,
            )
            # Concave arc: carve the cylinder centered r outward / r inward from the edge.
            du = p[hperp] - sh * (b[hperp] + r)
            dv = p[2] - sz_ * (b[2] - r)
            flare = lv.max(block, r - lv.sqrt(du * du + dv * dv))
            d = lv.min(d, flare)
    return d


def _cuboid_at_corner(
    p1: "Sequence[float]",
    p2: "Sequence[float] | None",
    size: "float | list[float] | None",
    rounding: float,
    chamfer: float,
    edges: "EdgeAtom | list[EdgeAtom]",
    except_edges: "list[EdgeAtom] | None",
    res: int,
    spin: float,
    orient: "Anchor | Sequence[float]",
) -> PyShape:
    """Build a cuboid placed by its corner rather than by an anchor -- `cuboid(p1=, p2=)`.

    Two opposing corners give the size and the position together, so *size* is ignored and the
    corner does the anchoring -- as on the CSG side, where `p1=` forces BOTTOM_FRONT_LEFT rather
    than composing with `anchor=`. With *p1* alone, *size* still says how big and *p1* only says
    where.

    Args:
        p1: One corner.
        p2: The opposing corner, or ``None``.
        size: The size as passed, used only when *p2* is ``None``.
        rounding: Rounding radius for the edges.
        chamfer: Chamfer size for the edges.
        edges: Which edges to treat.
        except_edges: Which edges to leave alone.
        res: Sampling resolution.
        spin: Z-axis rotation in degrees.
        orient: Direction to rotate the top towards.

    Returns:
        The placed cuboid.

    """
    corner = [float(v) for v in p1]
    if p2 is not None:
        low = [min(float(a), float(b)) for a, b in zip(p1, p2, strict=True)]
        high = [max(float(a), float(b)) for a, b in zip(p1, p2, strict=True)]
        size, corner = [high[i] - low[i] for i in range(3)], low
    box = cuboid(
        size=size,
        rounding=rounding,
        chamfer=chamfer,
        edges=edges,
        except_edges=except_edges,
        res=res,
        anchor=FRONT + LEFT + BOTTOM,
        spin=spin,
        orient=orient,
    )
    return box.translate(corner)


def cuboid(
    size: float | list[float] | None = None,
    p1: "Sequence[float] | None" = None,
    p2: "Sequence[float] | None" = None,
    rounding: float = 0,
    chamfer: float = 0,
    edges: EdgeAtom | list[EdgeAtom] = Anchor.ALL,
    except_edges: list[EdgeAtom] | None = None,
    res: int = 10,
    anchor: "Sequence[float]" = CENTER,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
) -> PyShape:
    """Return a cuboid with optional per-edge rounding or chamfering as a libfive SDF.

    Built as a libfive signed distance function (F-Rep) and returned as a PyShape (meshed
    lazily, via frep(), on first use) -- see pybosl2.shapes3d.cuboid() for the equivalent
    BOSL2-style mesh-CSG version (identical `edges=`/`except_edges=` semantics; both accept
    the same edge selector values, since pybosl2.sdf.edges's edge-set resolver is a
    byte-for-byte copy of pybosl2's own).

    `rounding` and `chamfer` are mutually exclusive in a single call (matching
    pybosl2.shapes3d.cuboid()); to mix both on different edges of the same cuboid, chain
    PyShape.round()/.chamfer() calls instead, e.g.
    `cuboid(size).round(2, edges=Anchor.Z).chamfer(1, edges=[TOP+LEFT])`.

    Args:
        size:         size of the cuboid, a number or length-3 vector
        p1: Place the cuboid's corner here instead of anchoring it. Forces the anchor to
            BOTTOM_FRONT_LEFT.
        p2: With *p1*, the opposing corner -- the two together give the size and the position, so
            *size* is ignored.
        rounding:     edge rounding radius applied to every selected edge (default: no rounding)
        chamfer:      edge chamfer size applied to every selected edge (default: no chamfer)
        edges:        edges to treat -- "ALL"/"NONE"/"X"/"Y"/"Z", a single edge vector (e.g.
                      TOP+LEFT), a list of edge vectors, or a raw 3x4 edge array (default "ALL")
        except_edges: edges to explicitly exclude from `edges` (BOSL2's `except=` synonym;
                      `except` is a Python keyword)
        res: libfive meshing resolution passed to frep() (default 10; higher = finer mesh). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.
        anchor:       anchor point (default CENTER)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.

    Examples:
        .. pythonscad-example::

            import pybosl2.sdf.shapes3d as sdf_s3d
            shape = sdf_s3d.cuboid([20.0, 20.0, 20.0], rounding=4)
            shape.show()

        .. pythonscad-example::

            import pybosl2.sdf.shapes3d as sdf_s3d
            shape = sdf_s3d.cuboid([20.0, 20.0, 20.0], chamfer=4)
            shape.show()

        Rounding only the 4 vertical edges (the per-axis-composition fallback path, not the
        exact-formula ``edges="ALL"`` case above):

        .. pythonscad-example::

            from pybosl2 import Anchor
            import pybosl2.sdf.shapes3d as sdf_s3d
            shape = sdf_s3d.cuboid([20.0, 20.0, 20.0], rounding=4, edges=Anchor.Z)
            shape.show()

    """
    if p1 is not None:
        return _cuboid_at_corner(p1, p2, size, rounding, chamfer, edges, except_edges, res, spin, orient)

    if size is None:
        size = [1, 1, 1]
    if rounding and chamfer:
        raise Bosl2ValueError("Cannot specify nonzero value for both rounding and chamfer")
    sz: list[float] = [float(v) for v in size] if isinstance(size, (list, tuple)) else [float(size)] * 3
    edge_set = resolve_edges(edges, except_edges or [])
    half = [s / 2 for s in sz]
    if rounding < 0:
        # BOSL2's negative rounding: an external cove flare on the selected edges (see
        # _cuboid_flare_sdf). Same restriction as BOSL2: no Z-aligned edges.
        if not (edge_set[2] == [0, 0, 0, 0]):
            raise Bosl2ValueError("Cannot use negative rounding with Z aligned edges")
        r = -rounding
        sdf_fn = lambda x, y, z: _cuboid_flare_sdf(x, y, z, sz, r, edge_set)  # noqa: E731
        # The flares stick out horizontally by r on whichever sides have a flared edge --
        # widen the meshing bounds accordingly (cuboid_size stays unset: the flared solid
        # is no longer a plain cuboid, so chained edge treatments would be wrong).
        mn = [-half[0], -half[1], -half[2]]
        mx = [half[0], half[1], half[2]]
        for axis, hperp in ((0, 1), (1, 0)):
            for i, (sh, _sz) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
                if edge_set[axis][i]:
                    if sh < 0:
                        mn[hperp] = min(mn[hperp], -half[hperp] - r)
                    else:
                        mx[hperp] = max(mx[hperp], half[hperp] + r)
        shape = PyShape(sdf_fn, mn, mx, res)
        offset = _anchor_offset_box3(sz, [int(a) for a in anchor])
        return _place(shape, offset, spin, orient)
    mode = EdgeMode.CHAMFER if chamfer else EdgeMode.ROUND
    amount = chamfer if chamfer else rounding
    amounts, modes = _edge_matrices(amount, edge_set, mode)
    sdf_fn = lambda x, y, z: _cuboid_edge_sdf(x, y, z, sz, amounts, modes)  # noqa: E731
    shape = PyShape(
        sdf_fn,
        [-half[0], -half[1], -half[2]],
        half,
        res,
        cuboid_size=sz,
        cuboid_edge_amounts=amounts,
        cuboid_edge_modes=modes,
    )
    offset = _anchor_offset_box3(sz, [int(a) for a in anchor])
    return _place(shape, offset, spin, orient)


def cube(
    size: float | list[float] = 1,
    rounding: float = 0,
    chamfer: float = 0,
    edges: "EdgeAtom | list[EdgeAtom]" = Anchor.ALL,
    except_edges: "list[EdgeAtom] | None" = None,
    center: bool | None = None,
    anchor: "Sequence[float]" = CENTER,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return a cube as a libfive SDF -- :func:`cuboid` with one size, and the same edge options.

    Args:
        size: size of the cube, a number or length-3 vector.
        rounding: Rounding radius for the edges, as :func:`cuboid` builds it.
        chamfer: Chamfer size for the edges, as :func:`cuboid` builds it.
        edges: Which edges to treat; the whole edge language :func:`cuboid` accepts.
        except_edges: Which edges to leave alone.
        center: If given, overrides ``anchor``: True centres the shape on the origin, False sits
            it on FRONT+LEFT+BOTTOM (SPEC B2-3).
        anchor: anchor point (default Anchor.CENTER)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.
    """
    anchor = resolve_center_anchor(center=center, anchor=anchor, centred=CENTER, uncentred=FRONT + LEFT + BOTTOM)
    return cuboid(
        size=size,
        rounding=rounding,
        chamfer=chamfer,
        edges=edges,
        except_edges=except_edges,
        anchor=anchor,
        spin=spin,
        orient=orient,
        res=res,
    )


# ---------------------------------------------------------------------------
# Section: Other simple solids without a BOSL2 rounding/chamfer concept
# ---------------------------------------------------------------------------


def octahedron(
    size: float = 1,
    anchor: "Sequence[float]" = CENTER,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return an octahedron with axis-aligned points (`|x|+|y|+|z| <= size/2`), as a libfive SDF.

    Args:
        size: A scalar (circumscribed cube edge) or ``(dx, dy, dz)`` tuple.
        anchor: anchor point (default CENTER)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.
    """
    s = size / 2
    sdf_fn = lambda x, y, z: lv.abs(x) + lv.abs(y) + lv.abs(z) - s  # noqa: E731
    shape = PyShape(sdf_fn, [-s, -s, -s], [s, s, s], res)
    pts = [[s, 0, 0], [-s, 0, 0], [0, s, 0], [0, -s, 0], [0, 0, s], [0, 0, -s]]
    offset = _anchor_offset_hull3(pts, anchor)
    return _place(shape, offset, spin, orient)


def _axis_aligned_box(shape: PyShape) -> "tuple[list[float], list[float]] | None":
    """Return the exact box *shape* fills, or None if it is not a plain axis-aligned box.

    `cuboid_size`/`cuboid_center` are only ever set by `cuboid()` and survive translation alone --
    rotate(), scale() and every boolean drop them -- so a shape that still carries them is
    axis-aligned. An edge treatment rounds the corners away, so a treated cuboid no longer fills
    its box and is excluded.
    """
    if shape.cuboid_size is None:
        return None
    treatments = shape.cuboid_edge_amounts
    if treatments is not None and any(any(amount for amount in row) for row in treatments):
        return None
    half = [float(s) / 2 for s in shape.cuboid_size]
    centre = [float(c) for c in shape.cuboid_center]
    return ([centre[i] - half[i] for i in range(3)], [centre[i] + half[i] for i in range(3)])


def _box_after_cutting(base: PyShape, tools: "list[PyShape]") -> "tuple[list[float], list[float]]":
    """Return the bounds of *base* minus *tools*, tightened where a cut provably trims an end.

    A difference kept the base's box verbatim, which is safe but not exact -- and exact bounds are
    the whole point of this backend (PAR-5). Trimming an *arbitrary* cut is not possible without
    the geometry, but one case is both common and provable: a cut that is a plain axis-aligned box
    spanning the base's full cross-section on two axes and overhanging one end on the third
    removes everything past that end, so the base's extent there ends at the cut's near face.

    This is what a part does to square off a moulding: `TrussClip` trimmed its ends this way and
    kept reporting the untrimmed height, 6mm taller than the CSG twin of the same code.

    Args:
        base: The solid being cut.
        tools: The solids being removed from it.

    Returns:
        The tightened ``(mn, mx)``; the base's own box where nothing could be proved.

    """
    mn, mx = list(base.mn), list(base.mx)
    span = [float(base.mx[i]) - float(base.mn[i]) for i in range(3)]
    epsilon = 1e-9 * (max(span) or 1.0)
    for tool in tools:
        box = _axis_aligned_box(tool)
        if box is None:
            continue
        cut_mn, cut_mx = box
        for axis in range(3):
            across = [i for i in range(3) if i != axis]
            covers_cross_section = all(
                cut_mn[i] <= float(base.mn[i]) + epsilon and cut_mx[i] >= float(base.mx[i]) - epsilon for i in across
            )
            if not covers_cross_section:
                continue
            reaches_low = cut_mn[axis] <= float(base.mn[axis]) + epsilon
            reaches_high = cut_mx[axis] >= float(base.mx[axis]) - epsilon
            if reaches_low and not reaches_high:
                mn[axis] = max(mn[axis], cut_mx[axis])
            elif reaches_high and not reaches_low:
                mx[axis] = min(mx[axis], cut_mn[axis])
    if any(mx[i] - mn[i] <= epsilon for i in range(3)):
        return list(base.mn), list(base.mx)  # the cuts leave nothing to measure; say nothing
    return mn, mx


def rotate_extrude(
    paths: "Path2D | Sequence[Path2D]",
    angle: float = 360.0,
    res: int = 10,
) -> PyShape:
    """Revolve a 2-D profile about the Z axis, as a libfive SDF.

    A revolve is the one 2-D -> 3-D operation that is *natural* in a distance field: the solid's
    field at ``(x, y, z)`` is the profile's own 2-D field read at ``(hypot(x, y), z)``, because
    every point's distance to a surface of revolution is its distance in the half-plane it lies
    in. So this is exact wherever `_polygon_sdf_xy` is, with no meshing and no approximation of
    the revolve itself.

    The profile is taken in the same frame OpenSCAD's ``rotate_extrude()`` uses: X is the radius
    from the Z axis, Y becomes Z. A profile crossing the axis is rejected -- the revolved solid
    would be self-intersecting, which OpenSCAD refuses too.

    Args:
        paths: The profile outline as a `Path2D`, or several disjoint ones (SPEC C-7a).
        angle: Sweep in degrees (default 360, a full revolution).
        res: libfive meshing resolution passed to frep(). Omitted, the ambient ``use_defaults(res=...)`` value
            applies.

    Returns:
        The revolved solid.

    Raises:
        ValueError: If a profile is empty, has fewer than 3 points, or crosses the Z axis.

    """
    if paths is None or len(paths) == 0:
        raise Bosl2ValueError("rotate_extrude(): needs at least one profile outline")
    path_list = as_path_list(paths, "paths", "rotate_extrude")
    if not path_list:  # pragma: no cover - as_path_list never empties a non-empty input
        raise Bosl2ValueError("rotate_extrude(): needs at least one profile outline")
    for outline in path_list:
        points = np.asarray(outline, dtype=float)
        if len(points) < 3:
            raise Bosl2ValueError(f"rotate_extrude(): a profile needs at least 3 points, got {len(points)}")
        if float(points[:, 0].min()) < -1e-9:
            raise Bosl2ValueError(
                "rotate_extrude(): the profile crosses the Z axis (a negative X), so the revolved "
                "solid would intersect itself; keep every profile point at x >= 0."
            )

    swept = angle % 360 if (angle > 360 or angle < 0) else angle
    sin_a, cos_a = math.sin(math.radians(swept)), math.cos(math.radians(swept))

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        radius = _lv_hypot(x, y)
        profile = None
        for outline in path_list:
            d = _polygon_sdf_xy(radius, z, outline)
            profile = d if profile is None else lv.min(profile, d)
        assert profile is not None, "the path list was checked non-empty above"
        if swept <= 0 or swept >= 360:
            return profile
        # The same angular sector pie_slice() cuts: two half-planes, intersected below 180
        # degrees and unioned above it.
        first = -y
        second = y * cos_a - x * sin_a
        sector = lv.max(first, second) if swept <= 180 else lv.min(first, second)
        return lv.max(profile, sector)

    corners = np.vstack([np.asarray(outline, dtype=float) for outline in path_list])
    radius = float(np.abs(corners[:, 0]).max())
    z_low, z_high = float(corners[:, 1].min()), float(corners[:, 1].max())
    xmn, ymn, xmx, ymx = _sector_xy_bounds(radius, swept)
    return PyShape(sdf_fn, [xmn, ymn, z_low], [xmx, ymx, z_high], res)


def tapered_polygon_prism(
    paths: "Path2D | Sequence[Path2D]",
    height: float,
    scale_bottom: float = 1.0,
    scale_top: float = 1.0,
    res: int = 10,
) -> PyShape:
    """Extrude a polygon whose cross-section scales linearly from bottom to top, as an SDF.

    The same construction the box `prismoid()` uses for its taper, with a polygon in place of the
    rectangle: at each height the local scale is interpolated (clamped outside the ends, so no
    per-point branch is needed) and the profile's own 2-D field is read in that scaled frame.
    Dividing the sample point by the scale and multiplying the distance back is the standard rule
    for a uniform scale, so the result is exact on the faces and carries the same documented
    underestimate past edges and vertices that `polygon_prism()` does.

    Sits on z=0, like `polygon_prism()`.

    Args:
        paths: The base outline as a `Path2D`, or several disjoint ones (SPEC C-7a).
        height: Extrusion height along +Z.
        scale_bottom: Cross-section scale at z=0.
        scale_top: Cross-section scale at z=height.
        res: libfive meshing resolution passed to frep(). Omitted, the ambient ``use_defaults(res=...)`` value
            applies.

    Returns:
        The tapered prism.

    Raises:
        ValueError: If a scale is not positive, or the height is not positive.

    """
    if height <= 0:
        raise Bosl2ValueError(f"tapered_polygon_prism(): height must be positive, got {height}")
    if scale_bottom <= 0 or scale_top <= 0:
        raise Bosl2ValueError(f"tapered_polygon_prism(): scales must be positive, got {scale_bottom} and {scale_top}")
    path_list = as_path_list(paths, "paths", "tapered_polygon_prism")
    if not path_list:
        raise Bosl2ValueError("tapered_polygon_prism(): needs at least one outline")

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        t = lv.min(lv.max(z / height, 0), 1)
        scale = scale_bottom + (scale_top - scale_bottom) * t
        profile = None
        for outline in path_list:
            d = _polygon_sdf_xy(x / scale, y / scale, outline) * scale
            profile = d if profile is None else lv.min(profile, d)
        assert profile is not None, "the path list was checked non-empty above"
        return lv.max(profile, lv.max(z - height, -z))

    widest = max(scale_bottom, scale_top)
    corners = np.vstack([np.asarray(outline, dtype=float) for outline in path_list]) * widest
    return PyShape(
        sdf_fn,
        [float(corners[:, 0].min()), float(corners[:, 1].min()), 0.0],
        [float(corners[:, 0].max()), float(corners[:, 1].max()), height],
        res,
    )


def spiral_sweep(
    profile: "Path2D",
    height: float,
    radius: float,
    turns: float = 1.0,
    center: bool = True,
    res: int = 10,
) -> PyShape:
    """Sweep a 2-D profile along a helix, as a libfive SDF -- a screw thread or a coil.

    The profile is read in the same frame the meshed `spiral_sweep()` uses: X is the offset
    outward from the helix radius, Y is height. A point at radius `r`, angle `theta` and height
    `z` lies on turn `k` of the helix when the profile contains
    ``(r - radius, z - z0 - pitch * (theta / 2pi + k))``, so the solid is the union of that test
    over every turn the coil has -- which is a plain `min()` over a handful of shifted copies of
    the profile's own 2-D field.

    Two things follow from that and are worth knowing:

    * The **zero set is exact** -- a point is on the surface exactly when the profile says so --
      but the *value* is the profile's 2-D distance, not the true 3-D distance to a helical
      surface, which is shorter as the sweep curves. That is the same trade the rest of this
      module documents.
    * `atan2` has a branch cut at ±pi, and a field built on one turn alone would tear along it.
      Sweeping one extra turn at each end covers the seam, so the neighbours agree across it.

    The ends are cut on flat z-planes rather than on the profile's own plane, which the meshed
    sweep uses. For a thread that makes no difference -- it is intersected with its rod either way
    -- but a bare coil's ends are square here.

    Args:
        profile: The cross-section as a `Path2D`: X outward from the helix, Y up (SPEC C-7a).
        height: Overall height of the coil.
        radius: Helix radius.
        turns: Number of revolutions. Negative sweeps the other way (a left-hand thread).
        center: Centre the coil on the origin, as the meshed sweep does by default.
        res: libfive meshing resolution passed to frep(). Omitted, the ambient ``use_defaults(res=...)`` value
            applies.

    Returns:
        The swept coil.

    Raises:
        ValueError: If the profile has fewer than 3 points, or turns or height is zero.

    """
    points = np.asarray(as_path_list(profile, "profile", "spiral_sweep")[0], dtype=float)
    if len(points) < 3:
        raise Bosl2ValueError(f"spiral_sweep(): the profile needs at least 3 points, got {len(points)}")
    if turns == 0:
        raise Bosl2ValueError("spiral_sweep(): turns must not be zero")
    if height == 0:
        raise Bosl2ValueError("spiral_sweep(): height must not be zero")

    outline = [[float(x), float(y)] for x, y in points]
    pitch = height / turns
    bottom = -height / 2 if center else 0.0
    # One extra turn each side so the atan2 seam is always covered by a neighbour.
    first = int(math.floor(min(0.0, turns))) - 1
    last = int(math.ceil(max(0.0, turns))) + 1

    first_turn, last_turn = min(0.0, turns), max(0.0, turns)
    scale = abs(pitch)  # turns -> millimetres, so the parameter clip is in the field's own units

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        u = _lv_hypot(x, y) - radius
        angle = lv.atan2(y, x) / (2 * math.pi)
        swept = None
        for k in range(first, last + 1):
            t_turn = angle + k
            v = z - (bottom + pitch * t_turn)
            d = _polygon_sdf_xy(u, v, outline)
            # Clip each turn to the sweep's own parameter range rather than to a z slab. A slab
            # would cut the profile's end faces off flat, which is not where the sweep ends: the
            # first and last cross-sections are the profile itself, standing on the helix.
            d = lv.max(d, (first_turn - t_turn) * scale)
            d = lv.max(d, (t_turn - last_turn) * scale)
            swept = d if swept is None else lv.min(swept, d)
        assert swept is not None, "the turn range always has at least one entry"
        return swept

    # The solid is a ring: its box reaches the profile's outermost point, at every angle.
    outer = radius + float(points[:, 0].max())
    ends = [bottom + pitch * first_turn, bottom + pitch * last_turn]
    low = min(ends) + float(points[:, 1].min())
    high = max(ends) + float(points[:, 1].max())
    return PyShape(sdf_fn, [-outer, -outer, low], [outer, outer, high], res)


def convex_polyhedron(points: "Path3D", res: int = 10) -> PyShape:
    """Return the convex hull of `points` as a libfive SDF.

    The max of the hull faces' signed half-space distances -- the 3-D analogue of
    polygon_extrude()'s half-plane form, with the same documented value tradeoff (exact
    perpendicular distance at faces, sign-correct underestimate out past edges/vertices).
    Covers the dice-style solids (tetrahedron, dodecahedron, icosahedron, trapezohedron, ...)
    that shapes3d.py builds, without needing BOSL2's polyhedra.scad or a mesh hull().

    Face planes come from a brute-force hull: every non-degenerate point triple whose plane has
    all points on one side is a supporting plane (deduplicated). That's O(n^4) in the point
    count -- entirely fine for the tens-of-vertices solids this is for, and it happens once in
    Python at construction time, not per SDF evaluation.

    Args:
        points: The points to hull. They must describe a convex solid.
        res: Sampling resolution for the SDF backend. Omitted, the ambient ``use_defaults(res=...)`` value applies.

    """
    coords = np.asarray(require_path(points, "points", "convex_polyhedron", Path3D), dtype=float)
    pts = [[float(v) for v in p] for p in coords]
    n = len(pts)
    if not (n >= 4):
        raise Bosl2ValueError(f"convex_polyhedron() needs at least 4 points, got {n}")
    planes = _hull_planes(pts)

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        d = None
        for nx, ny, nz, off in planes:
            e = nx * x + ny * y + nz * z - off
            d = e if d is None else lv.max(d, e)
        return d

    mn = [min(p[i] for p in pts) for i in range(3)]
    mx = [max(p[i] for p in pts) for i in range(3)]
    return PyShape(sdf_fn, mn, mx, res)


def wedge(
    size: list[float] | None = None,
    center: bool | None = None,
    anchor: "Sequence[float] | None" = None,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return a 3-D triangular wedge with the hypotenuse in the X+Z+ quadrant, as a libfive SDF.

    Args:
        size:   [width, thickness, height]
        center: If given, overrides ``anchor``: True centres the shape on the origin, False sits
            it on FRONT+LEFT+BOTTOM (SPEC B2-3).
        anchor: anchor point (default FRONT+LEFT+BOTTOM, matching pybosl2.shapes3d.wedge())
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: libfive meshing resolution passed to frep() (default 10). Omitted, the ambient ``use_defaults(res=...)``
            value applies.

    """
    anchor = resolve_center_anchor(center=center, anchor=anchor, centred=CENTER, uncentred=FRONT + LEFT + BOTTOM)
    if size is None:
        size = [1, 1, 1]
    if anchor is None:
        anchor = FRONT + LEFT + BOTTOM
    bx, by, bz = size[0] / 2, size[1] / 2, size[2] / 2
    # The triangular cross-section (right angle at Y-,Z-, hypotenuse from (Y+,Z-) to (Y-,Z+))
    # lies in the (Y, Z) plane; X is the uniform extrusion axis -- verified directly against
    # pybosl2.shapes3d.wedge()'s vertex list (every vertex has a fixed X, so the triangle's
    # actual shape only varies over Y/Z).
    nlen = math.hypot(by, bz)

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        box = lv.max(lv.max(lv.abs(x) - bx, lv.abs(y) - by), lv.abs(z) - bz)
        diag = (bz * y + by * z) / nlen
        return lv.max(box, diag)

    shape = PyShape(sdf_fn, [-bx, -by, -bz], [bx, by, bz], res)
    pts = [
        [bx, by, -bz],
        [bx, -by, -bz],
        [bx, -by, bz],
        [-bx, by, -bz],
        [-bx, -by, -bz],
        [-bx, -by, bz],
    ]
    offset = _anchor_offset_hull3(pts, anchor)
    return _place(shape, offset, spin, orient)


def sphere(
    radius: float | None = None,
    diameter: float | None = None,
    anchor: "Sequence[float]" = CENTER,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return a sphere, as a libfive SDF (`length(p) - r`).

    Args:
        radius: Sphere radius (mutually exclusive with *diameter*).
        diameter: Sphere diameter.
        anchor: anchor point (default CENTER)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.
    Examples:
        .. pythonscad-example::

            import pybosl2.sdf.shapes3d as sdf_s3d
            shape = sdf_s3d.sphere(radius=10)
            shape.show()

    """
    rad = _radius(radius=radius, diameter=diameter, dflt=1)
    sdf_fn = lambda x, y, z: lv.sqrt(x * x + y * y + z * z) - rad  # noqa: E731
    shape = PyShape(sdf_fn, [-rad, -rad, -rad], [rad, rad, rad], res)
    offset = _anchor_offset_sphere(rad, anchor)
    return _place(shape, offset, spin, orient)


def spheroid(
    radius: float | None = None,
    diameter: float | None = None,
    anchor: "Sequence[float]" = CENTER,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return an approximate sphere as a libfive SDF.

    This pure-libfive port just builds a plain sphere() (matching pybosl2.shapes3d.spheroid()'s
    own choice to ignore style/dual for its pure-Python port).

    Args:
        radius: radius of the spheroid.
        diameter: diameter of the spheroid.
        anchor: anchor point (default CENTER)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    """
    return sphere(radius=radius, diameter=diameter, anchor=anchor, spin=spin, orient=orient, res=res)


def torus(
    major_radius: float | None = None,
    minor_radius: float | None = None,
    major_diameter: float | None = None,
    minor_diameter: float | None = None,
    outer_radius: float | None = None,
    inner_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_diameter: float | None = None,
    center: bool | None = None,
    anchor: "Sequence[float]" = CENTER,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return a torus (donut) shape, as a libfive SDF.

    The SDF is `length(vec2(length(p.xy)-major_radius, p.z)) - minor_radius`.

    Note: BOSL2's outer-radius parameter is named `or`, which collides with the Python
    keyword `or`; it is exposed here as `outer_radius` instead. See pybosl2.shapes3d.torus() for
    the full parameter set this mirrors.

    Args:
        major_radius: Distance from the origin to the tube centre.
        minor_radius: Tube radius.
        major_diameter: Overrides *major_radius*.
        minor_diameter: Overrides *minor_radius*.
        outer_radius: outer radius of the torus (BOSL2 `or`) (use with inner_radius or inner_diameter)
        inner_radius: inside radius of the torus (use with outer_radius or outer_diameter)
        outer_diameter: outer diameter of the torus (use with inner_radius or inner_diameter)
        inner_diameter: inside diameter of the torus (use with outer_radius or outer_diameter)
        center: If given, overrides ``anchor``: True centres the shape on the origin, False sits
            it on BOTTOM (SPEC B2-3).
        anchor: anchor point (default CENTER)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.
    Examples:
        .. pythonscad-example::

            import pybosl2.sdf.shapes3d as sdf_s3d
            shape = sdf_s3d.torus(major_radius=15, minor_radius=5)
            shape.show()

    """
    anchor = resolve_center_anchor(center=center, anchor=anchor, centred=CENTER, uncentred=BOTTOM)
    _or = _pick_radius(radius=outer_radius, diameter=outer_diameter, dflt=None)
    _ir = _pick_radius(radius=inner_radius, diameter=inner_diameter, dflt=None)
    _r_maj = _pick_radius(radius=major_radius, diameter=major_diameter, dflt=None)
    _r_min = _pick_radius(radius=minor_radius, diameter=minor_diameter, dflt=None)
    if _r_maj is not None:
        maj = _r_maj
    elif _ir is not None and _or is not None:
        maj = (_or + _ir) / 2
    elif _ir is not None and _r_min is not None:
        maj = _ir + _r_min
    elif _or is not None and _r_min is not None:
        maj = _or - _r_min
    else:
        raise Bosl2ValueError(
            "torus(): needs enough radii to fix the major radius -- give major_radius/major_diameter, "
            "or any two of inner_radius/inner_diameter, outer_radius/outer_diameter and "
            "minor_radius/minor_diameter."
        )
    if _r_min is not None:
        minr = _r_min
    elif _ir is not None:
        minr = maj - _ir
    elif _or is not None:
        minr = _or - maj
    else:
        raise Bosl2ValueError(
            "torus(): needs enough radii to fix the minor radius -- give minor_radius/minor_diameter, "
            "inner_radius/inner_diameter or outer_radius/outer_diameter alongside the major radius."
        )

    sdf_fn = lambda x, y, z: _lv_hypot(_lv_hypot(x, y) - maj, z) - minr  # noqa: E731
    outer = maj + minr
    shape = PyShape(sdf_fn, [-outer, -outer, -minr], [outer, outer, minr], res)
    offset = _anchor_offset_cyl(outer, outer, minr * 2, anchor)
    return _place(shape, offset, spin, orient)


# ---------------------------------------------------------------------------
# Section: Cylinders
# ---------------------------------------------------------------------------


def _wall_line_sdf(
    rxy: LVTree,
    z: LVTree,
    radius1: float,
    radius2: float,
    hb: float,
    inset1: float = 0.0,
    inset2: float = 0.0,
) -> LVTree:
    """Return the signed distance to the infinite line for the slanted wall of a cylinder/cone.

    Goes through `(radius1, -hb + inset1)` and `(radius2, hb - inset2)` in the `(rxy, z)`
    half-plane -- exact for the wall itself; intersecting (max()) with the top/bottom slabs (see
    _cylinder_sdf()) caps it off, with the same corner-region approximation already documented for
    cuboid()'s per-axis composition.

    **The insets are where a treated rim actually leaves the wall**, and they matter only on a
    taper. BOSL2's profile puts a chamfer's or a rounding's inner endpoint at the *nominal* end
    radius and runs the wall from there to the other end's endpoint, so a chamfered cone's wall is
    not the line through its two nominal corners. This backend measured the rim against that
    nominal line until T42 and so built a different cone from the same call -- 0.39mm out on an
    8-to-4 taper with a 2mm chamfer, and the same for a rounding. On a plain cylinder the line is
    vertical and an axial inset cannot move it, which is why nothing noticed (SPEC PAR-5).

    Args:
        rxy: The radial coordinate.
        z: The axial coordinate.
        radius1: Radius at the negative end.
        radius2: Radius at the positive end.
        hb: Half the length.
        inset1: How far up from the negative end the wall starts.
        inset2: How far down from the positive end it ends.

    Returns:
        The signed distance to the wall line.

    """
    dr, dz = radius2 - radius1, 2 * hb - inset1 - inset2
    nlen = math.hypot(dr, dz)
    return ((rxy - radius1) * dz - (z + hb - inset1) * dr) / nlen


def _cylinder_sdf(
    x: LVTree, y: LVTree, z: LVTree, h: float, radius1: float, radius2: float, shift: list[float] | None = None
) -> LVTree:
    hb = h / 2
    if shift and (shift[0] or shift[1]):
        # Oblique cone (BOSL2 cyl(shift=)): `shift` is the offset of the top section's centre
        # *relative to the bottom's*, and the shear is taken about the mid-plane -- the bottom
        # slides by -shift/2 and the top by +shift/2, which is what the CSG backend's shear
        # matrix (`x' = x + shift_x * z / length`, on a cylinder spanning z = -h/2..h/2) does.
        # Measuring t from the bottom face instead put the whole solid half a shift off from the
        # CSG one for the same call: the relative offset was right and the placement was not
        # (SPEC PAR-5). Same interpolate-per-height construction, and the same
        # not-quite-Euclidean-but-zero-set-correct caveat, as prismoid().
        t = z / h
        x = x - shift[0] * t
        y = y - shift[1] * t
    rxy = _lv_hypot(x, y)
    wall = _wall_line_sdf(rxy, z, radius1, radius2, hb)
    slab = lv.abs(z) - hb
    return lv.max(wall, slab)


def chamfer_legs(amount: float, angle: float | None, from_end: bool) -> "tuple[float, float]":
    """Return a chamfer's ``(dx, dy)`` -- how far it cuts in radially and along the axis.

    BOSL2 states a chamfer two ways and both are in `cyl_profile`, which is where this comes from:
    with ``from_end=False`` the *size* is the radial leg and the angle sets the axial one
    (``dx = c``, ``dy = c * tan(angle)``); with ``from_end=True`` the size is the cut's own length
    and the angle splits it (``dx = c * cos(angle)``, ``dy = c * sin(angle)``). At the default 45
    degrees and ``from_end=False`` both legs are the size, which is the only case this backend
    could express before.

    Args:
        amount: The chamfer size.
        angle: The chamfer angle in degrees, or ``None`` for 45.
        from_end: Measure along the end face rather than up the side.

    Returns:
        The ``(dx, dy)`` pair.

    """
    degrees = 45.0 if angle is None else float(angle)
    if from_end:
        return amount * math.cos(math.radians(degrees)), amount * math.sin(math.radians(degrees))
    return amount, amount * math.tan(math.radians(degrees))


def _rim_size(amount: "float | tuple[float, float]") -> float:
    """Return how far a rim amount cuts, whether it is a radius or a chamfer's two legs.

    Args:
        amount: A rounding radius, or a chamfer's ``(dx, dy)``.

    Returns:
        The larger leg, or the radius. Zero means the rim is untreated.

    """
    return max(amount) if isinstance(amount, tuple) else amount


#: An overall/bottom/top triple as BOSL2 states one: `(chamfer, chamfer1, chamfer2)`. Passing the
#: three as a tuple rather than nine loose arguments is what keeps `cyl` and `_cyl_axis` from
#: transcribing the same twelve names twice (SPEC B-3).
_Triple = tuple[Any, Any, Any]


def _per_end(triple: _Triple, dflt: Any = 0) -> "tuple[Any, Any]":
    """Split an overall/bottom/top triple into the bottom and top values.

    The specific one wins, then the general one, then *dflt* -- the rule every one of these
    triples follows, written once.

    Args:
        triple: ``(overall, bottom, top)`` as passed.
        dflt: What to use when neither was given.

    Returns:
        The ``(bottom, top)`` pair.

    """
    overall, first, second = triple
    fallback = overall if overall is not None else dflt
    return (
        first if first is not None else fallback,
        second if second is not None else fallback,
    )


def _rim_amounts(
    rounding: _Triple,
    chamfer: _Triple,
    chamfer_angle: _Triple,
    from_end: _Triple,
) -> "tuple[EdgeMode, float | tuple[float, float], float | tuple[float, float]]":
    """Resolve the rim triples into a mode and one amount per end.

    Rounding and chamfer are mutually exclusive (SPEC G-7), and a chamfer's amount comes back as
    the ``(dx, dy)`` pair :func:`chamfer_legs` computes, which is what lets `chamfer_angle=` and
    `from_end=` cross.

    Args:
        rounding: The rounding radius triple.
        chamfer: The chamfer size triple.
        chamfer_angle: The chamfer angle triple, in degrees.
        from_end: The from-end triple.

    Returns:
        The mode and the two amounts, each a radius or a ``(dx, dy)`` chamfer pair.

    Raises:
        Bosl2ValueError: if a rounding and a chamfer are both asked for.

    """
    r1v, r2v = _per_end(rounding)
    c1v, c2v = _per_end(chamfer)
    if (r1v or r2v) and (c1v or c2v):
        raise Bosl2ValueError("Cannot specify nonzero value for both chamfer and rounding")
    if c1v or c2v:
        a1, a2 = _per_end(chamfer_angle, None)
        e1, e2 = _per_end(from_end, False)
        return EdgeMode.CHAMFER, chamfer_legs(c1v, a1, e1), chamfer_legs(c2v, a2, e2)
    return EdgeMode.ROUND, r1v, r2v


def _with_extra(
    sdf_fn: "Callable[[LVTree, LVTree, LVTree], LVTree]",
    axis: int,
    length: float,
    radius1: float,
    radius2: float,
    extra: _Triple,
    mn: list[float],
    mx: list[float],
) -> "tuple[Callable[[LVTree, LVTree, LVTree], LVTree], list[float], list[float]]":
    """Return *sdf_fn* with a plain stub of each end's radius added past that end.

    BOSL2's `extra=` grows the solid past its ends without changing its length or its anchoring,
    so a difference() cuts cleanly through instead of leaving a skin. The CSG backend unions a
    straight cylinder on; so does this, which is why the two agree exactly rather than nearly.

    Args:
        sdf_fn: The cylinder's own field.
        axis: 0, 1 or 2 -- the coordinate the cylinder runs along.
        length: Length of the cylinder.
        radius1: Radius at the negative end.
        radius2: Radius at the positive end.
        extra: The extra-length triple.
        mn: The box's low corner, widened here to hold the stubs.
        mx: The box's high corner.

    Returns:
        The field with the stubs unioned on, and the widened box.

    """
    extra1, extra2 = (float(v) for v in _per_end(extra, 0.0))
    if extra1 <= 0 and extra2 <= 0:
        return sdf_fn, mn, mx
    mn, mx = list(mn), list(mx)
    mn[axis] -= max(0.0, extra1)
    mx[axis] += max(0.0, extra2)

    def with_extra(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        coords = [x, y, z]
        axial = coords[axis]
        others = [coords[i] for i in range(3) if i != axis]
        radial = _lv_hypot(others[0], others[1])
        field = sdf_fn(x, y, z)
        for sign, radius, amount in ((-1.0, radius1, extra1), (1.0, radius2, extra2)):
            if amount <= 0:
                continue
            near, far = sign * length / 2.0, sign * (length / 2.0 + amount)
            stub = lv.max(radial - radius, lv.abs(axial - (near + far) / 2.0) - amount / 2.0)
            field = lv.min(field, stub)
        return field

    return with_extra, mn, mx


def _cyl_edge_sdf(
    axial: LVTree,
    radial: LVTree,
    h: float,
    radius1: float,
    radius2: float,
    amt1: "float | tuple[float, float]",
    amt2: "float | tuple[float, float]",
    mode: EdgeMode,
) -> LVTree:
    """Return _cylinder_sdf() plus independent rounding/chamfer treatment of the bottom and top rims.

    Uses the same per-candidate-quadrant masking technique as pybosl2.shapes3d.cuboid() (but
    only 2 candidates -- top/bottom -- since the radial coordinate has no sign ambiguity to
    select between, unlike a rectangle's 4 corners).

    A chamfer amount may be a scalar (a symmetric 45-degree cut) or the ``(dx, dy)`` pair
    :func:`chamfer_legs` returns, which is what lets `chamfer_angle=` and `from_end=` cross.
    """
    hb = h / 2
    insets = tuple(a[1] if isinstance(a, tuple) else a for a in (amt1, amt2))
    wall = _wall_line_sdf(radial, axial, radius1, radius2, hb, insets[0], insets[1])
    candidates = []
    for sz, r_ref, a in ((-1, radius1, amt1), (1, radius2, amt2)):
        if mode == EdgeMode.ROUND:
            assert not isinstance(a, tuple), "a rounding has one radius, not two legs"
            qu = radial - r_ref + a
            qv = lv.abs(axial) - hb + a
            base = lv.min(lv.max(qu, qv), 0) + _lv_hypot(lv.max(qu, 0), lv.max(qv, 0)) - a
        else:
            assert mode == EdgeMode.CHAMFER, "only rounded and chamfered rims reach this builder"
            dx, dy = a if isinstance(a, tuple) else (a, a)
            qu = radial - r_ref
            qv = lv.abs(axial) - hb
            # The cut runs from (-dx, 0) to (0, -dy) in the corner's own frame, so the plane is
            # `qu/dx + qv/dy + 1 = 0`; multiplying up and normalising gives the signed distance
            # below. With dx == dy == c it is `(qu + qv + c) / sqrt(2)`, the 45-degree form this
            # was written as before generalising it.
            leg = math.hypot(dx, dy) or 1.0
            base = lv.max(lv.max(qu, qv), (qu * dy + qv * dx + dx * dy) / leg)
        mask = lv.max(0, -sz * axial)
        candidates.append(base + _PENALTY * mask)
    rim = lv.min(candidates[0], candidates[1])
    return lv.max(wall, rim)


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
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    from_end: bool = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    extra: float = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    shift: list[float] | None = None,
    texture: "str | TextureType | TextureData | None" = None,
    tex_size: "float | Sequence[float] | None" = None,
    tex_reps: "int | Sequence[int] | None" = None,
    tex_depth: float = 1.0,
    tex_inset: float | bool = False,
    anchor: "Sequence[float] | None" = None,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return a cylinder or cone as a libfive SDF -- OpenSCAD's spelling of :func:`cyl`.

    This is an alias, exactly as it is on the CSG backend, where `cylinder()` forwards every
    argument to `cyl()` and adds nothing. It had its own field here until T40, which is why it
    silently lacked the rim treatments `cyl` has built all along: `cylinder(rounding=1)` came back
    "the sdf backend cannot do this" while `cyl(rounding=1)` built it. A second implementation of
    one shape is a second place for the two backends to drift (SPEC PAR-4, B-3).

    Args:
        height: length of the cylinder along its axis (default 1)
        radius1: radius of the negative end of the cylinder.
        radius2: radius of the positive end of the cylinder.
        center: If given, overrides ``anchor``: True centres the shape on the origin, False sits
            it on BOTTOM (SPEC B2-3).
        length: length of the cylinder along its axis (default 1)
        radius: radius of the cylinder (default 1)
        diameter: diameter of the cylinder.
        diameter1: diameter of the negative end of the cylinder.
        diameter2: diameter of the positive end of the cylinder.
        chamfer: Chamfer size on the end rims (overall/negative/positive)
        chamfer1: Chamfer size on the end rims (overall/negative/positive)
        chamfer2: Chamfer size on the end rims (overall/negative/positive)
        rounding: Rounding radius on the end rims (overall/negative/positive)
        rounding1: Rounding radius on the end rims (overall/negative/positive)
        rounding2: Rounding radius on the end rims (overall/negative/positive)
        chamfer_angle: Chamfer angle in degrees (overall/negative/positive), default 45.
        chamfer_angle1: Chamfer angle in degrees (overall/negative/positive), default 45.
        chamfer_angle2: Chamfer angle in degrees (overall/negative/positive), default 45.
        from_end: Measure the chamfer along the end face rather than up the side
            (overall/negative/positive).
        from_end1: Measure the chamfer along the end face rather than up the side
            (overall/negative/positive).
        from_end2: Measure the chamfer along the end face rather than up the side
            (overall/negative/positive).
        extra: Extra length past the end (overall/negative/positive), so a difference cuts clean
            through. It changes neither the length nor the anchoring.
        extra1: Extra length past the end (overall/negative/positive).
        extra2: Extra length past the end (overall/negative/positive).
        shift: [X,Y] offset of the top section's centre, making an oblique cone.
        texture: A texture name, a height field, or a VNF tile, displacing the side.
        tex_size: Size of one tile as ``[around, along]`` in millimetres, or one number for both.
        tex_reps: Repeat counts as ``[around, along]``, or one number for both.
        tex_depth: How far the texture displaces the surface. Negative sinks it in.
        tex_inset: How far the surface is sunk before the texture is added, so the valleys sit
            flush rather than proud. ``True`` means one full *tex_depth*.
        anchor: anchor point (default BOTTOM if center=False, otherwise CENTER)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.
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
        chamfer_angle=chamfer_angle,
        chamfer_angle1=chamfer_angle1,
        chamfer_angle2=chamfer_angle2,
        from_end=from_end,
        from_end1=from_end1,
        from_end2=from_end2,
        extra=extra,
        extra1=extra1,
        extra2=extra2,
        shift=shift,
        texture=texture,
        tex_size=tex_size,
        tex_reps=tex_reps,
        tex_depth=tex_depth,
        tex_inset=tex_inset,
        anchor=anchor,
        spin=spin,
        orient=orient,
        res=res,
    )


def _textured_cyl_sdf(
    length: float,
    rad1: float,
    rad2: float,
    tex: "str | TextureType | TextureData",
    tex_size: "float | Sequence[float] | None",
    tex_reps: "int | Sequence[int] | None",
    tex_depth: float,
    tex_inset: float | bool,
) -> "Callable[[LVTree, LVTree, LVTree], LVTree]":
    """Return the field of a textured cylinder, resolving the texture arguments as CSG does.

    The resolution is shared with the CSG backend down to the tile and the repeat counts
    (`pybosl2.textures`), so the same call describes the same surface on either backend and the two
    agree exactly at the sample points the mesh is built from (SPEC PAR-4, PAR-5).

    Args:
        length: Height of the cylinder.
        rad1: Radius at the bottom.
        rad2: Radius at the top.
        tex: The texture, by name or already built.
        tex_size: Size of one tile in millimetres.
        tex_reps: Repeat counts, instead of *tex_size*.
        tex_depth: How far the texture displaces the surface.
        tex_inset: How far the surface is sunk before the texture is added.

    Returns:
        The SDF closure.

    """
    from pybosl2.sdf.textures import textured_cyl_sdf
    from pybosl2.textures import _repeat_counts, default_tex_reps, height_field

    if tex_size is None and tex_reps is None:
        tex_reps = default_tex_reps(length, rad1, rad2)

    field = height_field(tex)
    around, along = _repeat_counts(length, max(rad1, rad2), tex_size, tex_reps)
    inset = float(tex_depth) if tex_inset is True else float(tex_inset)

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        return textured_cyl_sdf(x, y, z, length, rad1, rad2, field, around, along, float(tex_depth), inset)

    return sdf_fn


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
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    from_end: bool = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    extra: float = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    shift: list[float] | None = None,
    texture: "str | TextureType | TextureData | None" = None,
    tex_size: "float | Sequence[float] | None" = None,
    tex_reps: "int | Sequence[int] | None" = None,
    tex_depth: float = 1.0,
    tex_inset: float | bool = False,
    anchor: "Sequence[float] | None" = None,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return a cylinder/cone with optional rounding or chamfering of its end rims, as a libfive SDF.

    See pybosl2.shapes3d.cyl() for the full BOSL2-style version this mirrors (circum=/realign=
    aren't supported here; shift= is, for oblique cones, but not combined with rounding/chamfer,
    and neither is texture=).

    `rounding`/`chamfer` (and their `1`/`2` bottom/top variants) are mutually exclusive, same
    as pybosl2.shapes3d.cyl().

    Args:
        height: length of the cylinder along its axis (default 1)
        radius: radius of the cylinder (default 1)
        center: if given, overrides anchor (True -> CENTER, False -> BOTTOM)
        length: length of the cylinder along its axis (default 1)
        radius1: radius of the negative end of the cylinder.
        radius2: radius of the positive end of the cylinder.
        diameter: diameter of the cylinder.
        diameter1: diameter of the negative end of the cylinder.
        diameter2: diameter of the positive end of the cylinder.
        chamfer: chamfer size on the end rims (overall/negative/positive)
        chamfer1: chamfer size on the end rims (overall/negative/positive)
        chamfer2: chamfer size on the end rims (overall/negative/positive)
        rounding: rounding radius on the end rims (overall/negative/positive)
        rounding1: rounding radius on the end rims (overall/negative/positive)
        rounding2: rounding radius on the end rims (overall/negative/positive)
        chamfer_angle: Chamfer angle in degrees (overall/negative/positive), default 45.
        chamfer_angle1: Chamfer angle in degrees (overall/negative/positive), default 45.
        chamfer_angle2: Chamfer angle in degrees (overall/negative/positive), default 45.
        from_end: Measure the chamfer along the end face rather than up the side
            (overall/negative/positive).
        from_end1: Measure the chamfer along the end face rather than up the side
            (overall/negative/positive).
        from_end2: Measure the chamfer along the end face rather than up the side
            (overall/negative/positive).
        extra: Extra length past the end (overall/negative/positive), so a difference cuts clean
            through. It changes neither the length nor the anchoring.
        extra1: Extra length past the end (overall/negative/positive).
        extra2: Extra length past the end (overall/negative/positive).
        shift: X/Y offset for the positive end (shear) (default [0,0])
        texture: A texture name, a height field, or a VNF tile, displacing the side.
        tex_size: Size of one tile as ``[around, along]`` in millimetres, or one number for both.
        tex_reps: Repeat counts as ``[around, along]``, or one number for both.
        tex_depth: How far the texture displaces the surface. Negative sinks it in.
        tex_inset: How far the surface is sunk before the texture is added, so the valleys sit
            flush rather than proud. ``True`` means one full *tex_depth*.
        anchor: anchor point (default CENTER)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.
    Examples:
        .. pythonscad-example::

            import pybosl2.sdf.shapes3d as sdf_s3d
            shape = sdf_s3d.cyl(height=20, radius=8, rounding=2)
            shape.show()

    """
    length = length if length is not None else (height if height is not None else 1)
    rad1 = _radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
    rad2 = _radius(radius2=radius2, diameter2=diameter2, radius=radius, diameter=diameter, dflt=1)
    use_anchor = anchor
    if use_anchor is None:
        use_anchor = CENTER if center is None or center else BOTTOM

    mode, amt1, amt2 = _rim_amounts(
        (rounding, rounding1, rounding2),
        (chamfer, chamfer1, chamfer2),
        (chamfer_angle, chamfer_angle1, chamfer_angle2),
        (from_end, from_end1, from_end2),
    )

    if texture is not None and texture != "none":
        sdf_fn = _textured_cyl_sdf(length, rad1, rad2, texture, tex_size, tex_reps, tex_depth, tex_inset)
    elif shift is not None and (shift[0] or shift[1]):
        if any(_rim_size(amt) for amt in (amt1, amt2)):
            raise Bosl2ValueError("shift= cannot be combined with rounding/chamfer")
        sdf_fn = lambda x, y, z: _cylinder_sdf(x, y, z, length, rad1, rad2, shift)  # noqa: E731
    else:
        sdf_fn = lambda x, y, z: _cyl_edge_sdf(z, _lv_hypot(x, y), length, rad1, rad2, amt1, amt2, mode)  # noqa: E731
    maxr = max(rad1, rad2)
    if texture is not None and texture != "none":
        # The texture pushes the surface out by at most `tex_depth` past the plain radius (and an
        # inset pulls it in first). A bound that ignored it would clip the peaks off.
        inset = float(tex_depth) if tex_inset is True else float(tex_inset)
        maxr += max(0.0, float(tex_depth) - inset)
    mn = [-maxr, -maxr, -length / 2]
    mx = [maxr, maxr, length / 2]
    if shift is not None and (shift[0] or shift[1]):
        # The two end discs slide to -shift/2 and +shift/2, and they have their own radii: the
        # box is the union of the two, not the plain box widened by the whole shift at both ends.
        # Widening both ends by `shift` reported a 13-wide box for a solid 10 wide -- a bound, not
        # the geometry, but a bound wide enough to matter to anything that reads one.
        for i in (0, 1):
            mn[i] = min(-shift[i] / 2 - rad1, shift[i] / 2 - rad2)
            mx[i] = max(-shift[i] / 2 + rad1, shift[i] / 2 + rad2)
    field, mn, mx = _with_extra(sdf_fn, 2, length, rad1, rad2, (extra, extra1, extra2), mn, mx)
    shape = PyShape(field, mn, mx, res)
    offset = _anchor_offset_cyl(rad1, rad2, length, use_anchor)
    return _place(shape, offset, spin, orient)


#: How `shift=` maps onto the two non-axial coordinates, per axis. `shift` is stated in the
#: cylinder's *own* frame -- BOSL2's `xcyl` builds a `cyl` and turns it -- so the pair has to be
#: carried through that turn: `xcyl` is a 90-degree rotation about Y (local x,y,z -> world z,y,-x)
#: and `ycyl` is -90 about X (local x,y,z -> world x,z,-y). Each entry gives, for `others[0]` and
#: `others[1]`, which member of `shift` applies and with what sign -- the signed displacement of
#: the *far end's section centre* along that coordinate. Written down once, and checked against
#: the CSG backend with an asymmetric shift on each axis: a sign wrong here is invisible in a
#: symmetric case, and the first version had every one of them inverted.
_AXIS_LEAN: dict[int, tuple[tuple[int, float], tuple[int, float]]] = {
    0: ((1, 1.0), (0, -1.0)),
    1: ((0, 1.0), (1, -1.0)),
    2: ((0, 1.0), (1, 1.0)),
}


def _axis_local_xy(axis: int, others: "list[LVTree]") -> "tuple[LVTree, LVTree]":
    """Return the cylinder's own ``(x, y)`` from the two non-axial world coordinates.

    `_AXIS_LEAN` says which local coordinate each `others[k]` *is*, and with what sign -- that is
    what made it able to carry `shift` through the turn. Read backwards it does the other job a
    turned cylinder needs: putting a texture's angle in the cylinder's own frame, so `xcyl` and
    `cyl` wear the same pattern the same way round. One table, read forwards for `shift=` and
    backwards for `texture=`, rather than two derivations of one rotation.

    Args:
        axis: 0, 1 or 2 -- the coordinate the cylinder runs along.
        others: The two non-axial coordinates, in world order.

    Returns:
        The pair ``(local_x, local_y)``.

    """
    local: list[LVTree] = [0.0, 0.0]
    for k, (index, sign) in enumerate(_AXIS_LEAN[axis]):
        local[index] = sign * others[k]
    return local[0], local[1]


def _axis_shift(axis: int, shift: "list[float] | None") -> "list[float] | None":
    """Return `shift` resolved into the two non-axial coordinates, or None if there is no lean.

    Args:
        axis: 0, 1 or 2 -- the coordinate the cylinder runs along.
        shift: The ``[X, Y]`` offset of the far end in the cylinder's own frame, or ``None``.

    Returns:
        The displacement to apply to ``others[0]`` and ``others[1]``, or ``None`` when the
        cylinder is upright.

    """
    if shift is None or not (shift[0] or shift[1]):
        return None
    return [sign * float(shift[idx]) for idx, sign in _AXIS_LEAN[axis]]


def _cyl_axis(
    axis: int,
    height: float | None,
    radius: float | None,
    length: float | None,
    radius1: float | None,
    radius2: float | None,
    diameter: float | None,
    diameter1: float | None,
    diameter2: float | None,
    chamfer: float | None,
    chamfer1: float | None,
    chamfer2: float | None,
    rounding: float | None,
    rounding1: float | None,
    rounding2: float | None,
    anchor: "Sequence[float]",
    res: int,
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    from_end: bool = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    extra: float = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    shift: "list[float] | None" = None,
    texture: "str | TextureType | TextureData | None" = None,
    tex_size: "float | Sequence[float] | None" = None,
    tex_reps: "int | Sequence[int] | None" = None,
    tex_depth: float = 1.0,
    tex_inset: float | bool = False,
) -> PyShape:
    length = length if length is not None else (height if height is not None else 1)
    rad1 = _radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
    rad2 = _radius(radius2=radius2, diameter2=diameter2, radius=radius, diameter=diameter, dflt=1)
    mode, amt1, amt2 = _rim_amounts(
        (rounding, rounding1, rounding2),
        (chamfer, chamfer1, chamfer2),
        (chamfer_angle, chamfer_angle1, chamfer_angle2),
        (from_end, from_end1, from_end2),
    )

    lean = _axis_shift(axis, shift)
    if lean is not None and any(_rim_size(amt) for amt in (amt1, amt2)):
        raise Bosl2ValueError("shift= cannot be combined with rounding/chamfer")

    textured = None
    if texture is not None and texture != "none":
        textured = _textured_cyl_sdf(length, rad1, rad2, texture, tex_size, tex_reps, tex_depth, tex_inset)

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        coords = [x, y, z]
        axial = coords[axis]
        others = [coords[i] for i in range(3) if i != axis]
        if lean is not None:
            t = axial / length
            others = [o - m * t for o, m in zip(others, lean, strict=True)]
        if textured is not None:
            local_x, local_y = _axis_local_xy(axis, others)
            return textured(local_x, local_y, axial)
        radial = _lv_hypot(others[0], others[1])
        return _cyl_edge_sdf(axial, radial, length, rad1, rad2, amt1, amt2, mode)

    maxr = max(rad1, rad2)
    if textured is not None:
        inset = float(tex_depth) if tex_inset is True else float(tex_inset)
        maxr += max(0.0, float(tex_depth) - inset)
    mn, mx = [-maxr, -maxr, -maxr], [maxr, maxr, maxr]
    mn[axis], mx[axis] = -length / 2, length / 2
    if lean is not None:
        # Each end disc slides to its own half of the lean and carries its own radius, exactly as
        # in `cyl` -- the box is the union of the two, not the upright box widened by the whole
        # shift at both ends.
        for k, i in enumerate(i for i in range(3) if i != axis):
            mn[i] = min(-lean[k] / 2 - rad1, lean[k] / 2 - rad2)
            mx[i] = max(-lean[k] / 2 + rad1, lean[k] / 2 + rad2)
    field, mn, mx = _with_extra(sdf_fn, axis, length, rad1, rad2, (extra, extra1, extra2), mn, mx)
    shape = PyShape(field, mn, mx, res)
    offset = _anchor_offset_cyl(rad1, rad2, length, anchor, axis=axis)
    return _place(shape, offset, spin, orient)


def xcyl(
    height: float | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    length: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    from_end: bool = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    extra: float = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    shift: list[float] | None = None,
    texture: "str | TextureType | TextureData | None" = None,
    tex_size: "float | Sequence[float] | None" = None,
    tex_reps: "int | Sequence[int] | None" = None,
    tex_depth: float = 1.0,
    tex_inset: float | bool = False,
    center: bool | None = None,
    anchor: "Sequence[float]" = CENTER,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return a cylinder oriented along the X axis. See cyl() for argument details.

    Args:
        height: Length of the cylinder along its axis (default 1)
        radius: Radius of the cylinder (default 1)
        diameter: Diameter of the cylinder.
        radius1: Radius of the negative end of the cylinder.
        radius2: Radius of the positive end of the cylinder.
        diameter1: Diameter of the negative end of the cylinder.
        diameter2: Diameter of the positive end of the cylinder.
        length: Length of the cylinder along its axis (default 1)
        chamfer: Chamfer size on the end rims (overall/negative/positive)
        chamfer1: Chamfer size on the end rims (overall/negative/positive)
        chamfer2: Chamfer size on the end rims (overall/negative/positive)
        rounding: Rounding radius on the end rims (overall/negative/positive)
        rounding1: Rounding radius on the end rims (overall/negative/positive)
        rounding2: Rounding radius on the end rims (overall/negative/positive)
        chamfer_angle: Chamfer angle in degrees (overall/negative/positive), default 45.
        chamfer_angle1: Chamfer angle in degrees (overall/negative/positive), default 45.
        chamfer_angle2: Chamfer angle in degrees (overall/negative/positive), default 45.
        from_end: Measure the chamfer along the end face rather than up the side
            (overall/negative/positive).
        from_end1: Measure the chamfer along the end face rather than up the side
            (overall/negative/positive).
        from_end2: Measure the chamfer along the end face rather than up the side
            (overall/negative/positive).
        extra: Extra length past the end (overall/negative/positive), so a difference cuts clean
            through. It changes neither the length nor the anchoring.
        extra1: Extra length past the end (overall/negative/positive).
        extra2: Extra length past the end (overall/negative/positive).
        shift: [X,Y] offset of the far end's centre, in the cylinder's own frame.
        texture: A texture name, a height field, or a VNF tile, displacing the side.
        tex_size: Size of one tile as ``[around, along]`` in millimetres, or one number for both.
        tex_reps: Repeat counts as ``[around, along]``, or one number for both.
        tex_depth: How far the texture displaces the surface. Negative sinks it in.
        tex_inset: How far the surface is sunk before the texture is added, so the valleys sit
            flush rather than proud. ``True`` means one full *tex_depth*.
        center: If given, overrides ``anchor``: True centres the shape on the origin, False sits
            it on BOTTOM (SPEC B2-3).
        anchor: Anchor point (default CENTER)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.
    """
    anchor = resolve_center_anchor(center=center, anchor=anchor, centred=CENTER, uncentred=BOTTOM)
    return _cyl_axis(
        0,
        height,
        radius,
        length,
        radius1,
        radius2,
        diameter,
        diameter1,
        diameter2,
        chamfer,
        chamfer1,
        chamfer2,
        rounding,
        rounding1,
        rounding2,
        anchor,
        res,
        spin=spin,
        orient=orient,
        chamfer_angle=chamfer_angle,
        chamfer_angle1=chamfer_angle1,
        chamfer_angle2=chamfer_angle2,
        from_end=from_end,
        from_end1=from_end1,
        from_end2=from_end2,
        extra=extra,
        extra1=extra1,
        extra2=extra2,
        shift=shift,
        texture=texture,
        tex_size=tex_size,
        tex_reps=tex_reps,
        tex_depth=tex_depth,
        tex_inset=tex_inset,
    )


def ycyl(
    height: float | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    length: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    from_end: bool = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    extra: float = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    shift: list[float] | None = None,
    texture: "str | TextureType | TextureData | None" = None,
    tex_size: "float | Sequence[float] | None" = None,
    tex_reps: "int | Sequence[int] | None" = None,
    tex_depth: float = 1.0,
    tex_inset: float | bool = False,
    center: bool | None = None,
    anchor: "Sequence[float]" = CENTER,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return a cylinder oriented along the Y axis. See cyl() for argument details.

    Args:
        height: Length of the cylinder along its axis (default 1)
        radius: Radius of the cylinder (default 1)
        diameter: Diameter of the cylinder.
        radius1: Radius of the negative end of the cylinder.
        radius2: Radius of the positive end of the cylinder.
        diameter1: Diameter of the negative end of the cylinder.
        diameter2: Diameter of the positive end of the cylinder.
        length: Length of the cylinder along its axis (default 1)
        chamfer: Chamfer size on the end rims (overall/negative/positive)
        chamfer1: Chamfer size on the end rims (overall/negative/positive)
        chamfer2: Chamfer size on the end rims (overall/negative/positive)
        rounding: Rounding radius on the end rims (overall/negative/positive)
        rounding1: Rounding radius on the end rims (overall/negative/positive)
        rounding2: Rounding radius on the end rims (overall/negative/positive)
        chamfer_angle: Chamfer angle in degrees (overall/negative/positive), default 45.
        chamfer_angle1: Chamfer angle in degrees (overall/negative/positive), default 45.
        chamfer_angle2: Chamfer angle in degrees (overall/negative/positive), default 45.
        from_end: Measure the chamfer along the end face rather than up the side
            (overall/negative/positive).
        from_end1: Measure the chamfer along the end face rather than up the side
            (overall/negative/positive).
        from_end2: Measure the chamfer along the end face rather than up the side
            (overall/negative/positive).
        extra: Extra length past the end (overall/negative/positive), so a difference cuts clean
            through. It changes neither the length nor the anchoring.
        extra1: Extra length past the end (overall/negative/positive).
        extra2: Extra length past the end (overall/negative/positive).
        shift: [X,Y] offset of the far end's centre, in the cylinder's own frame.
        texture: A texture name, a height field, or a VNF tile, displacing the side.
        tex_size: Size of one tile as ``[around, along]`` in millimetres, or one number for both.
        tex_reps: Repeat counts as ``[around, along]``, or one number for both.
        tex_depth: How far the texture displaces the surface. Negative sinks it in.
        tex_inset: How far the surface is sunk before the texture is added, so the valleys sit
            flush rather than proud. ``True`` means one full *tex_depth*.
        center: If given, overrides ``anchor``: True centres the shape on the origin, False sits
            it on BOTTOM (SPEC B2-3).
        anchor: Anchor point (default CENTER)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.
    """
    anchor = resolve_center_anchor(center=center, anchor=anchor, centred=CENTER, uncentred=BOTTOM)
    return _cyl_axis(
        1,
        height,
        radius,
        length,
        radius1,
        radius2,
        diameter,
        diameter1,
        diameter2,
        chamfer,
        chamfer1,
        chamfer2,
        rounding,
        rounding1,
        rounding2,
        anchor,
        res,
        spin=spin,
        orient=orient,
        chamfer_angle=chamfer_angle,
        chamfer_angle1=chamfer_angle1,
        chamfer_angle2=chamfer_angle2,
        from_end=from_end,
        from_end1=from_end1,
        from_end2=from_end2,
        extra=extra,
        extra1=extra1,
        extra2=extra2,
        shift=shift,
        texture=texture,
        tex_size=tex_size,
        tex_reps=tex_reps,
        tex_depth=tex_depth,
        tex_inset=tex_inset,
    )


def zcyl(
    height: float | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    length: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    from_end: bool = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    extra: float = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    shift: list[float] | None = None,
    texture: "str | TextureType | TextureData | None" = None,
    tex_size: "float | Sequence[float] | None" = None,
    tex_reps: "int | Sequence[int] | None" = None,
    tex_depth: float = 1.0,
    tex_inset: float | bool = False,
    center: bool | None = None,
    anchor: "Sequence[float] | None" = None,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return a cylinder oriented along the Z axis -- an alias for :func:`cyl`, as on CSG.

    Args:
        height: Length of the cylinder along its axis (default 1)
        radius: Radius of the cylinder (default 1)
        diameter: Diameter of the cylinder.
        radius1: Radius of the negative end of the cylinder.
        radius2: Radius of the positive end of the cylinder.
        diameter1: Diameter of the negative end of the cylinder.
        diameter2: Diameter of the positive end of the cylinder.
        length: Length of the cylinder along its axis (default 1)
        chamfer: Chamfer size on the end rims (overall/negative/positive)
        chamfer1: Chamfer size on the end rims (overall/negative/positive)
        chamfer2: Chamfer size on the end rims (overall/negative/positive)
        rounding: Rounding radius on the end rims (overall/negative/positive)
        rounding1: Rounding radius on the end rims (overall/negative/positive)
        rounding2: Rounding radius on the end rims (overall/negative/positive)
        chamfer_angle: Chamfer angle in degrees (overall/negative/positive), default 45.
        chamfer_angle1: Chamfer angle in degrees (overall/negative/positive), default 45.
        chamfer_angle2: Chamfer angle in degrees (overall/negative/positive), default 45.
        from_end: Measure the chamfer along the end face rather than up the side
            (overall/negative/positive).
        from_end1: Measure the chamfer along the end face rather than up the side
            (overall/negative/positive).
        from_end2: Measure the chamfer along the end face rather than up the side
            (overall/negative/positive).
        extra: Extra length past the end (overall/negative/positive), so a difference cuts clean
            through. It changes neither the length nor the anchoring.
        extra1: Extra length past the end (overall/negative/positive).
        extra2: Extra length past the end (overall/negative/positive).
        shift: [X,Y] offset of the top section's centre, making an oblique cone.
        texture: A texture name, a height field, or a VNF tile, displacing the side.
        tex_size: Size of one tile as ``[around, along]`` in millimetres, or one number for both.
        tex_reps: Repeat counts as ``[around, along]``, or one number for both.
        tex_depth: How far the texture displaces the surface. Negative sinks it in.
        tex_inset: How far the surface is sunk before the texture is added, so the valleys sit
            flush rather than proud. ``True`` means one full *tex_depth*.
        center: If given, overrides ``anchor``: True centres the shape on the origin, False sits
            it on BOTTOM (SPEC B2-3).
        anchor: Anchor point (default CENTER)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.
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
        chamfer_angle=chamfer_angle,
        chamfer_angle1=chamfer_angle1,
        chamfer_angle2=chamfer_angle2,
        from_end=from_end,
        from_end1=from_end1,
        from_end2=from_end2,
        extra=extra,
        extra1=extra1,
        extra2=extra2,
        shift=shift,
        texture=texture,
        tex_size=tex_size,
        tex_reps=tex_reps,
        tex_depth=tex_depth,
        tex_inset=tex_inset,
        anchor=anchor,
        spin=spin,
        orient=orient,
        res=res,
    )


def tube(
    height: float | None = None,
    outer_radius: float | None = None,
    inner_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_diameter: float | None = None,
    wall: float | None = None,
    outer_r1: float | None = None,
    outer_r2: float | None = None,
    od1: float | None = None,
    od2: float | None = None,
    ir1: float | None = None,
    ir2: float | None = None,
    id1: float | None = None,
    id2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    length: float | None = None,
    center: bool | None = None,
    anchor: "Sequence[float]" = CENTER,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return a hollow cylindrical tube (outer cylinder minus inner cylinder), as a libfive SDF.

    Note: BOSL2's outer-radius parameters are named `or`/`or1`/`or2`; exposed here as
    `outer_radius`/`outer_r1`/`outer_r2` since `or` is a Python keyword.

    Args:
        height: height of the tube (default 1)
        outer_radius: outer radius of the tube (BOSL2 ``or``) (default 1)
        inner_radius: inner radius of the tube.
        outer_diameter: outer diameter of the tube.
        inner_diameter: inner diameter of the tube.
        wall: horizontal wall thickness (default 1)
        outer_r1: Outer radius at the bottom (BOSL2's ``or1``).
        outer_r2: Outer radius at the top (BOSL2's ``or2``).
        od1: Outer diameter at the bottom.
        od2: Outer diameter at the top.
        ir1: Inner radius at the bottom.
        ir2: Inner radius at the top.
        id1: Inner diameter at the bottom.
        id2: Inner diameter at the top.
        rounding: rounding radius on end rims (overall/bottom/top)
        rounding1: rounding radius on end rims (overall/bottom/top)
        rounding2: rounding radius on end rims (overall/bottom/top)
        chamfer: chamfer size on end rims (overall/bottom/top)
        chamfer1: chamfer size on end rims (overall/bottom/top)
        chamfer2: chamfer size on end rims (overall/bottom/top)
        length: height of the tube (default 1)
        center: If given, overrides ``anchor``: True centres the shape on the origin, False sits
            it on BOTTOM (SPEC B2-3).
        anchor: anchor point (default CENTER)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    """
    anchor = resolve_center_anchor(center=center, anchor=anchor, centred=CENTER, uncentred=BOTTOM)
    length = length if length is not None else (height if height is not None else 1)
    orr1 = _pick_radius(radius1=outer_r1, diameter1=od1, radius=outer_radius, diameter=outer_diameter, dflt=None)
    orr2 = _pick_radius(radius1=outer_r2, diameter1=od2, radius=outer_radius, diameter=outer_diameter, dflt=None)
    irr1 = _pick_radius(radius1=ir1, diameter1=id1, radius=inner_radius, diameter=inner_diameter, dflt=None)
    irr2 = _pick_radius(radius1=ir2, diameter1=id2, radius=inner_radius, diameter=inner_diameter, dflt=None)
    wall_v = wall if wall is not None else 1
    rad1 = orr1 if orr1 is not None else (irr1 + wall_v if irr1 is not None else None)
    rad2 = orr2 if orr2 is not None else (irr2 + wall_v if irr2 is not None else None)
    irad1 = irr1 if irr1 is not None else (orr1 - wall_v if orr1 is not None else None)
    irad2 = irr2 if irr2 is not None else (orr2 - wall_v if orr2 is not None else None)
    if rad1 is None or rad2 is None or irad1 is None or irad2 is None:
        raise Bosl2ValueError(
            "tube(): needs two of the three sizes -- an inner radius/diameter, an outer "
            "radius/diameter, and a wall thickness."
        )

    r1v = rounding1 if rounding1 is not None else (rounding if rounding is not None else 0.0)
    r2v = rounding2 if rounding2 is not None else (rounding if rounding is not None else 0.0)
    c1v = chamfer1 if chamfer1 is not None else (chamfer if chamfer is not None else 0.0)
    c2v = chamfer2 if chamfer2 is not None else (chamfer if chamfer is not None else 0.0)
    if (r1v or r2v) and (c1v or c2v):
        raise Bosl2ValueError("Cannot specify nonzero value for both chamfer and rounding")
    mode, amt1, amt2 = (EdgeMode.CHAMFER, c1v, c2v) if (c1v or c2v) else (EdgeMode.ROUND, r1v, r2v)

    def outer_sdf(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        return _cyl_edge_sdf(z, _lv_hypot(x, y), length, rad1, rad2, amt1, amt2, mode)

    def inner_sdf(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        return _cylinder_sdf(x, y, z, length, irad1, irad2)

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        return lv.max(outer_sdf(x, y, z), -inner_sdf(x, y, z))

    maxr = max(rad1, rad2)
    shape = PyShape(sdf_fn, [-maxr, -maxr, -length / 2], [maxr, maxr, length / 2], res)
    offset = _anchor_offset_cyl(rad1, rad2, length, anchor)
    return _place(shape, offset, spin, orient)


def _sector_xy_bounds(radius: float, angle: float) -> tuple[float, float, float, float]:
    """Exact ``(xmin, ymin, xmax, ymax)`` of the circular sector sweeping 0..*angle* degrees.

    The sector is the arc plus the apex at the origin, so its extremes are the origin, the two arc
    endpoints, and whichever of the four axis directions the sweep passes through. Taking the whole
    disc's box instead is what PAR-5 was about: at 30 degrees that over-reports by four times the
    area, on the backend whose selling point is exact bounds.
    """
    if angle <= 0 or angle >= 360:
        return (-radius, -radius, radius, radius)
    end_x = radius * math.cos(math.radians(angle))
    end_y = radius * math.sin(math.radians(angle))
    xs = [0.0, radius, end_x]  # 0 degrees is always swept, so +X always reaches the radius
    ys = [0.0, 0.0, end_y]
    if angle >= 90:
        ys.append(radius)
    if angle >= 180:
        xs.append(-radius)
    if angle >= 270:
        ys.append(-radius)
    return (min(xs), min(ys), max(xs), max(ys))


def pie_slice(
    height: float | None = None,
    radius: float | None = None,
    angle: float = 30,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    length: float | None = None,
    center: bool | None = None,
    anchor: "Sequence[float]" = CENTER,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return a pie slice (wedge of a cylinder/cone), as a libfive SDF.

    A cylinder intersected with an angular sector (built from 1-2 half-planes -- `angle` is a
    plain Python float fixed at construction time, so choosing intersection vs union of the two
    half-planes based on `angle <= 180` is an ordinary Python conditional, not a per-point SDF
    branch).

    Args:
        height: height of the pie slice.
        radius: radius of the pie slice.
        angle: pie slice angle in degrees (default 30)
        radius1: bottom radius of the pie slice.
        radius2: top radius of the pie slice.
        diameter: diameter of the pie slice.
        diameter1: diameter of the bottom.
        diameter2: diameter of the top.
        length: height of the pie slice.
        center: If given, overrides ``anchor``: True centres the shape on the origin, False sits
            it on BOTTOM (SPEC B2-3).
        anchor: anchor point (default CENTER)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    """
    anchor = resolve_center_anchor(center=center, anchor=anchor, centred=CENTER, uncentred=BOTTOM)
    length = length if length is not None else (height if height is not None else 1)
    rad1 = _radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=10)
    rad2 = _radius(radius2=radius2, diameter2=diameter2, radius=radius, diameter=diameter, dflt=10)
    ang_v = angle % 360 if (angle > 360 or angle < 0) else angle
    ang_rad = math.radians(ang_v)
    sin_a, cos_a = math.sin(ang_rad), math.cos(ang_rad)

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        body = _cylinder_sdf(x, y, z, length, rad1, rad2)
        if ang_v <= 0 or ang_v >= 360:
            return body
        sdf1 = -y
        sdf2 = y * cos_a - x * sin_a
        sector = lv.max(sdf1, sdf2) if ang_v <= 180 else lv.min(sdf1, sdf2)
        return lv.max(body, sector)

    # The wedge's own box, not the disc's (PAR-5). Every cross-section is the same sector scaled
    # about the apex, so the widest one -- at max(rad1, rad2) -- sets the box for the whole solid.
    xmn, ymn, xmx, ymx = _sector_xy_bounds(max(rad1, rad2), ang_v)
    shape = PyShape(sdf_fn, [xmn, ymn, -length / 2], [xmx, ymx, length / 2], res)
    # Anchoring stays on the full cylinder, as the CSG pie_slice does: `anchor` names a point on
    # the cylinder the slice was cut from, so the two backends place an anchored slice alike.
    offset = _anchor_offset_cyl(rad1, rad2, length, anchor)
    return _place(shape, offset, spin, orient)


# ---------------------------------------------------------------------------
# Section: Cuboids, Prismoids and Tubes
# ---------------------------------------------------------------------------


def prismoid(
    size1: list[float],
    size2: list[float],
    height: float | None = None,
    shift: list[float] | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    length: float | None = None,
    center: bool | None = None,
    anchor: "Sequence[float]" = BOTTOM,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return a rectangular prismoid (truncated pyramid), as a libfive SDF.

    The vertical edges take a rounding or a chamfer, which this backend refused until T43 on the
    grounds that "deriving an exact SDF for a *tapered* box's independently-radiused vertical
    edges was out of scope". It needed no derivation, because the CSG backend does not derive one
    either: it builds the two end cross-sections and takes their **convex hull**, and the hull of
    two convex sets in parallel planes has cross-section `(1-t)A + tB` -- the Minkowski
    combination -- at every height between them.

    For these shapes that combination is the same shape again. A rounded rectangle is
    `box + disc`, and Minkowski addition distributes, so the blend is a rounded rectangle whose
    half-size and whose corner radius are each linearly interpolated. A chamfered rectangle is an
    octagon whose support function is linear in the size and the chamfer, so its blend is a
    chamfered rectangle with both interpolated. **So the cross-section is exact**, and the only
    approximation left is the one this function already carried: measuring across a taper is not
    the Euclidean distance to it, though the zero set is right (SPEC B-5's line about not
    approximating what the other backend does not).

    Args:
        size1:  [width, length] of the bottom end
        size2:  [width, length] of the top end
        height:    height of the prism
        shift:  [X,Y] shift of the top center relative to the bottom center
        rounding: Rounding radius of the vertical edges (overall/bottom/top).
        rounding1: Rounding radius of the vertical edges (overall/bottom/top).
        rounding2: Rounding radius of the vertical edges (overall/bottom/top).
        chamfer: Chamfer size of the vertical edges (overall/bottom/top).
        chamfer1: Chamfer size of the vertical edges (overall/bottom/top).
        chamfer2: Chamfer size of the vertical edges (overall/bottom/top).
        length:    height of the prism
        center: If given, overrides ``anchor``: True centres the shape on the origin, False sits
            it on BOTTOM (SPEC B2-3).
        anchor: anchor point (default BOTTOM)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: libfive meshing resolution passed to frep() (default 10). Omitted, the ambient ``use_defaults(res=...)``
            value applies.

    Raises:
        Bosl2ValueError: if a rounding and a chamfer are both asked for (SPEC G-7).

    """
    anchor = resolve_center_anchor(center=center, anchor=anchor, centred=CENTER, uncentred=BOTTOM)
    if shift is None:
        shift = [0, 0]
    height = height if height is not None else (length if length is not None else 1)
    bx1, by1 = size1[0] / 2, size1[1] / 2
    bx2, by2 = size2[0] / 2, size2[1] / 2
    hb = height / 2

    r1, r2 = _per_end((rounding, rounding1, rounding2))
    c1, c2 = _per_end((chamfer, chamfer1, chamfer2))
    if (r1 or r2) and (c1 or c2):
        raise Bosl2ValueError("Cannot specify nonzero value for both chamfer and rounding")

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        t = lv.min(lv.max((z + hb) / height, 0), 1)
        bx = bx1 + (bx2 - bx1) * t
        by = by1 + (by2 - by1) * t
        qx = lv.abs(x - shift[0] * t)
        qy = lv.abs(y - shift[1] * t)
        if c1 or c2:
            cut = c1 + (c2 - c1) * t
            d2d = lv.max(lv.max(qx - bx, qy - by), (qx - bx + qy - by + cut) / _SQRT2)
        else:
            radius = r1 + (r2 - r1) * t
            ex, ey = qx - (bx - radius), qy - (by - radius)
            d2d = lv.min(lv.max(ex, ey), 0) + _lv_hypot(lv.max(ex, 0), lv.max(ey, 0)) - radius
        return lv.max(d2d, lv.abs(z) - hb)

    # The shift moves the *top* section only, so the widest point in each direction is whichever
    # end reaches furthest -- not either end plus the whole shift. Adding it to the bottom
    # reported a 28-wide box for a solid 20 wide, the same defect `cyl` carried until T40 and in
    # the same place: a bound written beside the field rather than measured from it.
    maxx = max(bx1, bx2 + abs(shift[0]))
    maxy = max(by1, by2 + abs(shift[1]))
    shape = PyShape(sdf_fn, [-maxx, -maxy, -hb], [maxx, maxy, hb], res)
    offset = _anchor_offset_box3([maxx * 2, maxy * 2, height], [int(a) for a in anchor])
    return _place(shape, offset, spin, orient)


def rect_tube(
    height: float | None = None,
    size: float | list[float] | None = None,
    isize: float | list[float] | None = None,
    wall: float | None = None,
    rounding: float = 0,
    inner_rounding: float | None = None,
    length: float | None = None,
    center: bool | None = None,
    anchor: "Sequence[float]" = BOTTOM,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return a rectangular tube (a rectangle with a rectangular hole through it), as a libfive SDF.

    (outer rounded-rect-extrusion minus inner rounded-rect-extrusion, reusing
    pybosl2.shapes3d.cuboid()'s per-edge machinery for each). Only the 4 vertical edges are
    ever rounded (`edges=Anchor.Z`, matching the "rounded rectangular tube" look BOSL2's own
    rect_tube() produces) -- there's no per-edge selection here, just one outer radius and
    one inner radius (default: same as the outer).

    Args:
        height:       height/length of the tube (default 1)
        length:       height/length of the tube (default 1)
        size:      outer [X,Y] size of the tube
        isize:     inner [X,Y] size of the tube
        wall:      wall thickness (used with `size` if `isize` isn't given, or vice versa)
        rounding:  outer vertical-edge rounding radius (default: no rounding)
        inner_rounding: inner vertical-edge rounding radius (default: same as `rounding`)
        center: If given, overrides ``anchor``: True centres the shape on the origin, False sits
            it on BOTTOM (SPEC B2-3).
        anchor:    anchor point (default BOTTOM)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: libfive meshing resolution passed to frep() (default 10). Omitted, the ambient ``use_defaults(res=...)``
            value applies.

    """
    anchor = resolve_center_anchor(center=center, anchor=anchor, centred=CENTER, uncentred=BOTTOM)
    length = height if height is not None else (length if length is not None else 1)
    if size is None:
        raise Bosl2ValueError("rect_tube(): needs an outer size -- give size=, or an inner size with a wall.")
    sz: list[float] = [float(v) for v in size] if isinstance(size, (list, tuple)) else [float(size)] * 2
    if isize is not None:
        isz: list[float] = [float(v) for v in isize] if isinstance(isize, (list, tuple)) else [float(isize)] * 2
    else:
        if not (wall is not None):
            raise Bosl2ValueError("rect_tube(): must give isize or wall.")
        isz = [sz[0] - 2 * wall, sz[1] - 2 * wall]
    irounding_v = inner_rounding if inner_rounding is not None else rounding
    edge_set_z = resolve_edges(Anchor.Z, [])
    o_amounts, o_modes = _edge_matrices(rounding, edge_set_z, EdgeMode.ROUND)
    i_amounts, i_modes = _edge_matrices(irounding_v, edge_set_z, EdgeMode.ROUND)

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        outer = _cuboid_edge_sdf(x, y, z, [sz[0], sz[1], length], o_amounts, o_modes)
        inner = _cuboid_edge_sdf(x, y, z, [isz[0], isz[1], length + 0.02], i_amounts, i_modes)
        return lv.max(outer, -inner)

    half = [sz[0] / 2, sz[1] / 2, length / 2]
    shape = PyShape(sdf_fn, [-half[0], -half[1], -half[2]], half, res)
    offset = _anchor_offset_box3([sz[0], sz[1], length], [int(a) for a in anchor])
    return _place(shape, offset, spin, orient)


# ---------------------------------------------------------------------------
# Section: Miscellaneous
# ---------------------------------------------------------------------------


def interior_fillet(
    length: float = 1.0,
    radius: float | None = None,
    angle: float = 90,
    diameter: float | None = None,
    anchor: "Sequence[float]" = CENTER,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return an interior-fillet cutter for a corner between two faces meeting at `angle` degrees.

    As a libfive SDF: the wedge between the two faces, minus a cylindrical arc of radius `radius`
    positioned so it's tangent to both. Extruded along Y for length `length`.

    CAVEAT: simplified relative to pybosl2.shapes3d.interior_fillet() -- no `overlap=` flap (an
    SDF union is already watertight without one) and no independent anchor-face alignment;
    the wedge's first face lies along the local +X/Z=0 half-plane. See
    pybosl2.shapes3d.interior_fillet() for the exact BOSL2-compatible anchor/orientation.

    Args:
        length: length of the edge to fillet (default 1.0)
        radius: radius of the fillet.
        angle: Angle in degrees between the two faces the fillet sits in.
        diameter: diameter of the fillet.
        anchor: anchor point (default FRONT+LEFT)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: Sampling resolution for the SDF backend. Omitted, the ambient ``use_defaults(res=...)`` value applies.

    """
    rad = _radius(radius=radius, diameter=diameter, dflt=1)
    half = math.radians(angle / 2)
    dist = rad / math.sin(half)
    cx, cz = dist * math.cos(half), dist * math.sin(half)
    ang_rad = math.radians(angle)
    sin_a, cos_a = math.sin(ang_rad), math.cos(ang_rad)
    hb = length / 2

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        sdf1 = -z
        sdf2 = z * cos_a - x * sin_a
        wedge_sdf = lv.max(sdf1, sdf2)
        circle = _lv_hypot(x - cx, z - cz) - rad
        fillet2d = lv.max(wedge_sdf, -circle)
        slab = lv.abs(y) - hb
        return lv.max(fillet2d, slab)

    shape = PyShape(sdf_fn, [-rad * 2, -hb, -rad * 2], [rad * 2, hb, rad * 2], res)
    offset = [-a * b for a, b in zip(anchor, [rad * 2, hb, rad * 2], strict=False)] if any(anchor) else [0.0, 0.0, 0.0]
    return _place(shape, offset, spin, orient)


def rounding_edge_mask(
    length: float | None = None,
    height: float | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    excess: float = 0.1,
    res: int = 10,
) -> PyShape:
    """Return a standalone 3-D edge-rounding CUTTER of length `length`, as a libfive SDF.

    For subtracting from another PyShape to round over a sharp 90-degree edge that isn't part of a cuboid()'s
    own edge/corner treatment -- e.g. an edge exposed by an earlier cut, or any other edge you'diameter
    otherwise position by hand. Matches pybosl2.masking.rounding_edge_mask()'s local-frame
    convention exactly (same `.rotate(...).translate(...)` call sites work unchanged): origin at
    the sharp edge, +X/+Y extending into the material (with a small `excess` skirt past 0 on
    each so the cutter fully bridges the material being cut), centered along its own Z axis over
    length `length`, with a quarter-circle bite of radius `radius` taken out of the far corner.

    Built the same way interior_fillet() builds its wedge-minus-circle cutter: a square corner
    (`box`) minus a circle tangent to both its flat sides.

    CAVEAT: simplified relative to pybosl2.masking.rounding_edge_mask() -- one radius for the
    whole length (no radius1/radius2 taper).

    Args:
        length: Length of the cutter along its axis (default 1).
        height: Length of the cutter along its axis (default 1).
        radius: Rounding radius (both ends).
        diameter: Rounding diameter (both ends).
        excess: Extra length added at each end, so the cutter reaches past the solid it trims.
        res: Sampling resolution for the SDF backend. Omitted, the ambient ``use_defaults(res=...)`` value applies.

    """
    length = length if length is not None else (height if height is not None else 1)
    rad = _radius(radius=radius, diameter=diameter, dflt=1)

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        box = lv.max(lv.max(x - rad, -x - excess), lv.max(y - rad, -y - excess))
        circle = _lv_hypot(x - rad, y - rad) - rad
        cutter2d = lv.max(box, -circle)
        slab = lv.abs(z) - length / 2
        return lv.max(cutter2d, slab)

    return PyShape(sdf_fn, [-excess, -excess, -length / 2], [rad, rad, length / 2], res)


def polygon_extrude(pts: "Path2D", length: float, res: int = 10) -> PyShape:
    """Return a linear extrusion of a CONVEX 2-D polygon as a 3-D libfive SDF.

    Extrudes `pts` along Z by `length`, centered -- for a custom edge-profile cutter with no
    pybosl2.shapes3d.Bosl2Solid.edge_profile_asym()'s `children=` path, but swept here by hand
    with an explicit rotate()/translate() rather than an automatic per-edge sweep).

    As a libfive SDF, this is the max() of each edge's signed half-plane distance -- exact at
    and near any face, but (like every other per-axis/per-plane-composed shape in this module --
    see the module docstring) underestimates the true Euclidean distance near a vertex, away
    from the surface; the sign is still correct everywhere a convex polygon's supporting
    half-planes actually bound it.

    CAVEAT: `pts` must describe a CONVEX polygon. A concave vertex's half-plane doesn't bound
    the shape there, so both the sign and the surface would come out wrong.

    Args:
        pts: The convex outline to extrude.
        length: Height to extrude to.
        res: Sampling resolution for the SDF backend. Omitted, the ambient ``use_defaults(res=...)`` value applies.

    """
    coords = as_points(require_path(pts, "pts", "polygon_extrude", Path2D))
    area2 = sum(
        coords[i][0] * coords[(i + 1) % len(coords)][1] - coords[(i + 1) % len(coords)][0] * coords[i][1]
        for i in range(len(coords))
    )
    ordered = coords if area2 > 0 else list(reversed(coords))
    n = len(ordered)
    edges = []
    for i in range(n):
        x0, y0 = ordered[i]
        x1, y1 = ordered[(i + 1) % n]
        ex, ey = x1 - x0, y1 - y0
        elen = math.hypot(ex, ey)
        edges.append((ey / elen, -ex / elen, x0, y0))

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        d = None
        for nx, ny, x0, y0 in edges:
            e = nx * (x - x0) + ny * (y - y0)
            d = e if d is None else lv.max(d, e)
        slab = lv.abs(z) - length / 2
        return lv.max(d, slab)

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return PyShape(sdf_fn, [min(xs), min(ys), -length / 2], [max(xs), max(ys), length / 2], res)


def polygon_prism(
    paths: "Path2D | Sequence[Path2D]",
    height: float,
    rounding_top: float = 0,
    rounding_bottom: float = 0,
    chamfer_top: float = 0,
    chamfer_bottom: float = 0,
    res: int = 10,
) -> PyShape:
    """Extrude an arbitrary SIMPLE polygon as a 3-D libfive SDF.

    The polygon (convex or concave) uses _polygon_sdf_xy() for exact 2-D SDF, unlike
    polygon_extrude()'s convex-only half-planes. Extrudes from z=0 up to z=height,
    with optional circular/flat treatments on each end rim -- the same job as real BOSL2's
    offset_sweep(path, height=height, bottom=os_circle(b), top=os_circle(t)), and the same sign
    convention for the radii: positive is a convex roundover eased into the rim, negative is an
    outward flare, 0 leaves that rim square. Sits on z=0 (not centered), matching offset_sweep.

    `paths` is one polygon (a list of [x, y] points) or a list of NON-OVERLAPPING polygons (a
    "region" of disjoint islands, min/union-combined). Holes aren't supported.

    Roundover rims use the same exact inset-then-offset construction as _rounded_box_sdf(), in
    (d2d, z) cross-section coordinates: q = (d2d + r, (z - height) + r) for the top rim, then
    `min(max(q), 0) + hypot(max(q, 0)) - r` -- which reduces exactly to the plain side/end
    distance away from its own rim, so both rims plus the sharp prism combine with max().
    Flares union on an extra quarter-circle ring of material outside the wall (the same
    box-minus-tangent-circle style as interior_fillet()/rounding_edge_mask(), swept here along
    the polygon via the 2-D SDF instead of along a straight edge).

    Args:
        paths:           one `Path2D` outline, or a sequence of disjoint ones (SPEC C-7a)
        height:               extrusion height (z from 0 to height)
        rounding_top:    top-rim treatment: >0 roundover radius, <0 flare, 0 square (default 0)
        rounding_bottom: bottom-rim treatment, same convention (default 0)
        chamfer_top:     top-rim chamfer size (default 0)
        chamfer_bottom:  bottom-rim chamfer size (default 0)
        res: libfive meshing resolution passed to frep() (default 10). Omitted, the ambient ``use_defaults(res=...)``
            value applies.

    """
    if not (len(paths) >= 1):
        raise Bosl2ValueError("polygon_prism(): paths must not be empty")
    path_list = as_path_list(paths, "paths", "polygon_prism")
    for p in path_list:
        if not (len(p) >= 3):
            raise Bosl2ValueError(f"polygon_prism(): every path needs >= 3 points, got {len(p)}")
    if not (height > 0):
        raise Bosl2ValueError(f"polygon_prism(): height must be > 0, height={height}")
    if not (abs(rounding_top) < height):
        raise Bosl2ValueError("polygon_prism(): rim treatments must be smaller than height")
    if not (abs(rounding_bottom) < height):
        raise Bosl2ValueError("polygon_prism(): rim treatments must be smaller than height")
    if not (chamfer_top < height):
        raise Bosl2ValueError("polygon_prism(): rim treatments must be smaller than height")
    if not (chamfer_bottom < height):
        raise Bosl2ValueError("polygon_prism(): rim treatments must be smaller than height")

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        d2d = None
        for p in path_list:
            d = _polygon_sdf_xy(x, y, p)
            d2d = d if d2d is None else lv.min(d2d, d)
        if not (d2d is not None):  # pragma: no cover
            # defensive: polygon_prism() rejects an empty path list before it
            # ever builds this callback, so the loop above always sets d2d.
            raise Bosl2ValueError("polygon_prism(): no paths")

        # Sharp prism, then max() in each roundover rim (each reduces to the sharp distance
        # away from its own rim -- see docstring).
        out = lv.max(d2d, lv.max(z - height, -z))
        if rounding_top > 0:
            rt = rounding_top
            q1, q2 = d2d + rt, (z - height) + rt
            out = lv.max(
                out,
                lv.min(lv.max(q1, q2), 0) + _lv_hypot(lv.max(q1, 0), lv.max(q2, 0)) - rt,
            )
        elif chamfer_top > 0:
            out = lv.max(out, (d2d + (z - height) + chamfer_top) / _SQRT2)

        if rounding_bottom > 0:
            rb = rounding_bottom
            q1, q2 = d2d + rb, -z + rb
            out = lv.max(
                out,
                lv.min(lv.max(q1, q2), 0) + _lv_hypot(lv.max(q1, 0), lv.max(q2, 0)) - rb,
            )
        elif chamfer_bottom > 0:
            out = lv.max(out, (d2d + (-z) + chamfer_bottom) / _SQRT2)

        # Flares union on a ring of added material curving from tangent-to-the-wall out to the
        # rim plane along a quarter circle. The ring is deliberately built on the UNSIGNED
        # outline distance (min-over-segments, no atan2), not the signed d2d: it therefore also
        # fires on the mirrored band just INSIDE the wall, which the union with the prism
        # swallows invisibly -- and in exchange it stays completely clear of the winding form's
        # atan2 branch cuts, which libfive's evaluator turned into spike/collapse artifacts
        # whenever a flared concave prism built on a dense round_corners() outline was
        # subtracted from another shape (sharp low-point-count outlines rendered fine; the
        # densified ones degenerated).
        u_d = None
        if rounding_top < 0 or rounding_bottom < 0:
            u2 = None
            for p in path_list:
                diameter2 = _polygon_dist2_xy(x, y, p)
                u2 = diameter2 if u2 is None else lv.min(u2, diameter2)
            u_d = lv.sqrt(u2)
        if rounding_top < 0:
            assert u_d is not None
            f = -rounding_top
            du = lv.min(u_d, f + 1)
            ring = lv.max(f - _lv_hypot(du - f, z - (height - f)), lv.max(z - height, (height - f) - z))
            ring = lv.max(ring, u_d - f)
            out = lv.min(out, ring)
        if rounding_bottom < 0:
            assert u_d is not None
            f = -rounding_bottom
            du = lv.min(u_d, f + 1)
            ring = lv.max(f - _lv_hypot(du - f, z - f), lv.max(-z, z - f))
            ring = lv.max(ring, u_d - f)
            out = lv.min(out, ring)
        return out

    xs = [p[0] for path in path_list for p in path]
    ys = [p[1] for path in path_list for p in path]
    flare = max(0.0, -rounding_top, -rounding_bottom)
    return PyShape(
        sdf_fn,
        [min(xs) - flare, min(ys) - flare, 0],
        [max(xs) + flare, max(ys) + flare, height],
        res,
    )


def teardrop(
    height: float | None = None,
    radius: float | None = None,
    angle: float = 45,
    cap_height: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    anchor: "Sequence[float]" = CENTER,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return a teardrop shape (useful for 3-D-printable horizontal holes), as a libfive SDF: the.

    union of a circle and a "roof" of two planes meeting at the apex, tangent to the circle,
    extruded along Y for thickness `h`.

    CAVEAT: simplified relative to pybosl2.shapes3d.teardrop() -- no `chamfer=`/`circum=`/
    `realign=` support. `cap_height` (truncation height) is supported since it's a plain top-slab
    intersection.

    Args:
        height: thickness of the teardrop (default 1)
        radius: radius of the circular part (default 1)
        angle: angle of the hat walls from the Z axis in degrees (default 45)
        cap_height: height above center to truncate the shape (default: no truncation)
        radius1: radius of the circular portion of the front end.
        radius2: radius of the circular portion of the back end.
        diameter: diameter of the circular portion.
        diameter1: diameter of the front end.
        diameter2: diameter of the back end.
        anchor: anchor point (default CENTER)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.
    Examples:
        .. pythonscad-example::

            import pybosl2.sdf.shapes3d as sdf_s3d
            shape = sdf_s3d.teardrop(height=10, radius=8)
            shape.show()

    """
    length = height if height is not None else 1
    rad1 = _radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
    rad2 = _radius(radius2=radius2, diameter2=diameter2, radius=radius, diameter=diameter, dflt=1)
    ang_rad = math.radians(angle)
    sin_a, cos_a = math.sin(ang_rad), math.cos(ang_rad)
    hb = length / 2

    def profile_sdf(u: LVTree, v: LVTree, radius: float) -> LVTree:
        circle = _lv_hypot(u, v) - radius
        right = u * sin_a + v * cos_a - radius
        left = -u * sin_a + v * cos_a - radius
        # The roof planes are only tangent to (and so only a valid boundary of) the circle
        # at v >= radius*cos_a (their tangent height); below that they cut into the disk, so
        # mask them out there and let the circle govern instead.
        v_tangent = radius * cos_a
        roof = lv.max(right, left) + _PENALTY * lv.max(0, v_tangent - v)
        d = lv.min(circle, roof)
        if cap_height is not None:
            d = lv.max(d, v - cap_height)
        return d

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        t = lv.min(lv.max((y + hb) / length, 0), 1)
        rad = rad1 + (rad2 - rad1) * t
        prof = profile_sdf(x, z, rad)
        slab = lv.abs(y) - hb
        return lv.max(prof, slab)

    maxr = max(rad1, rad2)
    maxheight = maxr / sin_a if cap_height is None else min(cap_height, maxr / sin_a)
    shape = PyShape(sdf_fn, [-maxr, -hb, -maxr], [maxr, hb, maxheight], res)
    offset = (
        [
            -anchor[0] * maxr,
            -anchor[1] * hb,
            -anchor[2] * maxheight if anchor[2] > 0 else -anchor[2] * maxr,
        ]
        if any(anchor)
        else [0.0, 0.0, 0.0]
    )
    return _place(shape, offset, spin, orient)


def onion(
    radius: float | None = None,
    angle: float = 45,
    cap_height: float | None = None,
    diameter: float | None = None,
    anchor: "Sequence[float]" = CENTER,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return an onion-dome shape (a sphere with a conical cap), as a libfive SDF: the union of a.

    sphere and a cone tangent to it, revolved around Z.

    CAVEAT: simplified relative to pybosl2.shapes3d.onion() -- no `circum=`/`realign=` support.

    Args:
        radius: radius of the spherical portion of the bottom (default 1)
        angle: angle of the cone from vertical in degrees (default 45)
        cap_height: height above the sphere center to truncate the shape (default: no truncation)
        diameter: diameter of the spherical portion of the bottom.
        anchor: anchor point (default CENTER)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    """
    rad = _radius(radius=radius, diameter=diameter, dflt=1)
    ang_rad = math.radians(angle)
    sin_a, cos_a = math.sin(ang_rad), math.cos(ang_rad)
    v_tangent = rad * cos_a

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        rxy = _lv_hypot(x, y)
        sphere_sdf = _lv_hypot(rxy, z) - rad
        roof = rxy * sin_a + z * cos_a - rad
        roof = roof + _PENALTY * lv.max(0, v_tangent - z)
        d = lv.min(sphere_sdf, roof)
        if cap_height is not None:
            d = lv.max(d, z - cap_height)
        return d

    maxheight = rad / sin_a if cap_height is None else min(cap_height, rad / sin_a)
    shape = PyShape(sdf_fn, [-rad, -rad, -rad], [rad, rad, maxheight], res)
    offset = (
        [
            -anchor[0] * rad,
            -anchor[1] * rad,
            -anchor[2] * maxheight if anchor[2] > 0 else -anchor[2] * rad,
        ]
        if any(anchor)
        else [0.0, 0.0, 0.0]
    )
    return _place(shape, offset, spin, orient)


def heightfield(
    data: Callable[[Any, Any], Any],
    size: list[float] | None = None,
    bottom: float = -20,
    maxz: float = 99,
    res: int = 10,
) -> PyShape:
    """Return a 3-D surface from a height function, as a libfive SDF.

    CAVEAT: unlike pybosl2.shapes3d.heightfield(), `data` must be a *callable* `f(x, y) -> z`
    built from ordinary arithmetic/libfive-supported math (it gets called directly with
    libfive coordinate trees, so it becomes part of the symbolic expression) -- a 2-D array of
    height samples isn't supported, since there's no closed-form way to "look up" an arbitrary
    grid of numbers inside a libfive expression (no gather/index primitive is exposed). Use
    pybosl2.shapes3d.heightfield() for array data. `xrange=`/`yrange=`/`style=` aren't
    applicable here since there's no discrete grid to sample.

    Args:
        data:   callable (x, y) -> height, evaluated symbolically
        size:   [X,Y] size of the surface (default [100,100])
        bottom: Z coordinate for the bottom of the object (default -20)
        maxz:   maximum height to model, taller values are clamped (default 99)
        res: libfive meshing resolution passed to frep() (default 10). Omitted, the ambient ``use_defaults(res=...)``
            value applies.

    """
    if size is None:
        size = [100, 100]
    if not (callable(data)):
        raise Bosl2ValueError(
            "pybosl2.sdf.shapes3d.heightfield() only supports callable data -- see the CAVEAT in its docstring."
        )
    bx, by = size[0] / 2, size[1] / 2

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        height = lv.min(lv.max(data(x, y), bottom), maxz)
        top = z - height
        slab = lv.max(lv.abs(x) - bx, lv.abs(y) - by)
        return lv.max(lv.max(top, bottom - z), slab)

    shape = PyShape(sdf_fn, [-bx, -by, bottom], [bx, by, maxz], res)
    return shape


# ---------------------------------------------------------------------------
#  regular-prism family
# ---------------------------------------------------------------------------


def regular_prism(
    num_sides: int = 6,
    height: float | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    outer_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_radius: float | None = None,
    inner_diameter: float | None = None,
    side: float | None = None,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    realign: bool = False,
    center: bool | None = None,
    anchor: "Sequence[float]" = CENTER,
    spin: float = 0,
    orient: "Anchor | Sequence[float]" = TOP,
    res: int = 10,
) -> PyShape:
    """Return a regular num_sides-gon prism (equilateral, equiangular cross-section), as a libfive SDF.

    Built on polygon_prism(). Mirrors pybosl2.shapes3d.regular_prism().

    Size is controlled by one of the radius/diameter/side parameters, in BOSL2 priority order:
    inner_radius/inner_diameter > outer_radius/outer_diameter > r/d > side.  The ``or``/``outer_radius``
    keyword collision with the Python keyword ``or`` is resolved as ``outer_radius`` here.

    Args:
        num_sides:                    number of sides (default 6)
        height:                       prism height (default 1)
        length:                       prism height (default 1)
        radius:                       radius to the vertices
        diameter:                     diameter to the vertices
        outer_radius:                 outer radius (BOSL2 ``or``)
        outer_diameter:               outer diameter
        inner_radius:                 inner radius (apothem to face centres)
        inner_diameter:               inner diameter
        side:                         length of each side
        realign:                      rotate so a face centre (not vertex) faces +X (default False)
        center: If given, overrides ``anchor``: True centres the shape on the origin, False sits
            it on BOTTOM (SPEC B2-3).
        anchor:                       anchor point (default CENTER)
        spin: Z-axis rotation in degrees, applied after anchoring.
        orient: Direction to rotate the shape's top towards, applied last.
        res: meshing resolution (default 10). Omitted, the ambient ``use_defaults(res=...)`` value applies.
        radius1: Bottom circumradius, for a tapered prism.
        radius2: Top circumradius, for a tapered prism.
        rounding: End rounding radius, applied to both ends.
        rounding1: End rounding radius at the bottom, instead of *rounding*.
        rounding2: End rounding radius at the top, instead of *rounding*.
        chamfer: End chamfer size, applied to both ends.
        chamfer1: End chamfer size at the bottom, instead of *chamfer*.
        chamfer2: End chamfer size at the top, instead of *chamfer*.

    """
    anchor = resolve_center_anchor(center=center, anchor=anchor, centred=CENTER, uncentred=BOTTOM)
    import math as _m

    length = length if length is not None else (height if height is not None else 1)
    sc = 1 / _m.cos(_m.radians(180.0 / num_sides))
    ir_s = inner_radius * sc if inner_radius is not None else None
    id_s = inner_diameter * sc if inner_diameter is not None else None
    side_s = side / 2 / _m.sin(_m.radians(180.0 / num_sides)) if side is not None else None
    rad = _pick_radius(
        radius1=ir_s,
        diameter1=id_s,
        radius2=outer_radius,
        diameter2=outer_diameter,
        radius=radius,
        diameter=diameter,
        dflt=side_s,
    )
    if rad is None and (radius1 is not None or radius2 is not None):
        # A tapered prism is sized by its ends, so the wider one stands in for the overall radius.
        rad = max(v for v in (radius1, radius2) if v is not None)
    if rad is None:
        raise Bosl2ValueError(
            "regular_prism(): need one of r, d, outer_radius, outer_diameter, inner_radius, inner_diameter, or side."
        )

    r1v = rounding1 if rounding1 is not None else (rounding if rounding is not None else 0.0)
    r2v = rounding2 if rounding2 is not None else (rounding if rounding is not None else 0.0)
    c1v = chamfer1 if chamfer1 is not None else (chamfer if chamfer is not None else 0.0)
    c2v = chamfer2 if chamfer2 is not None else (chamfer if chamfer is not None else 0.0)

    pts = [[_m.cos(2 * _m.pi * i / num_sides) * rad, _m.sin(2 * _m.pi * i / num_sides) * rad] for i in range(num_sides)]
    if realign:
        pts = [
            [
                p[0] * _m.cos(-_m.pi / num_sides) - p[1] * _m.sin(-_m.pi / num_sides),
                p[0] * _m.sin(-_m.pi / num_sides) + p[1] * _m.cos(-_m.pi / num_sides),
            ]
            for p in pts
        ]

    if radius1 is not None or radius2 is not None:
        # A tapered prism: the cross-section scales with height, the way the box prismoid tapers.
        bottom = radius1 if radius1 is not None else rad
        top = radius2 if radius2 is not None else rad
        if any(v for v in (r1v, r2v, c1v, c2v)):
            raise Bosl2ValueError(
                "regular_prism(): a tapered prism (radius1=/radius2=) cannot also take rim "
                "rounding or chamfer here; build it on the csg backend for that."
            )
        base = [[p[0] / rad * bottom, p[1] / rad * bottom] for p in pts]
        prism = tapered_polygon_prism(Path2D(base), length, 1.0, top / bottom, res=res)
    else:
        prism = polygon_prism(
            Path2D(pts),
            length,
            rounding_top=r2v,
            rounding_bottom=r1v,
            chamfer_top=c2v,
            chamfer_bottom=c1v,
            res=res,
        )
    # polygon_prism() sits on z=0, but the anchor offset below is computed from a hull centred on
    # it, so the prism has to be centred first. Without this every anchor came out half a height
    # too high -- anchor=CENTER put the prism entirely above the origin, and anchor=TOP put it
    # where CENTER belonged. The CSG twin anchors correctly, so the same call placed the shape
    # differently on the two backends (SPEC B-3).
    prism = prism.translate([0.0, 0.0, -length / 2])
    # `pts` is the cross-section at `rad`; a taper's widest end may differ, and the anchor has to
    # be measured against the box the solid actually fills.
    widest = max(radius1 if radius1 is not None else rad, radius2 if radius2 is not None else rad) / rad
    hull = [[p[0] * widest, p[1] * widest] for p in pts]
    offset = _anchor_offset_hull3(
        [[p[0], p[1], -length / 2] for p in hull] + [[p[0], p[1], length / 2] for p in hull],
        anchor,
    )
    return _place(prism, offset, spin, orient)


# ---------------------------------------------------------------------------
# Sweeping a 2-D profile along a 3-D path, as a libfive SDF
# ---------------------------------------------------------------------------


def _rmf_frames(points: ArrayLike) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Rotation-minimizing frames along a 3-D polyline (Wang et al.'s double-reflection method).

    Returns (T, N, B) arrays -- unit tangent, normal and binormal at each point. Unlike a Frenet
    frame this does not flip at inflection points, so the swept profile does not suddenly twist.
    """
    p = np.asarray(points, dtype=float)
    n = len(p)
    t = np.zeros((n, 3))
    t[1:-1] = p[2:] - p[:-2]
    t[0] = p[1] - p[0]
    t[-1] = p[-1] - p[-2]
    tl = np.linalg.norm(t, axis=1, keepdims=True)
    if not (np.all(tl > 1e-12)):
        raise Bosl2ValueError("path has a repeated point (zero-length tangent)")
    t /= tl
    nrm = np.zeros((n, 3))
    ref = np.array([0.0, 0.0, 1.0]) if abs(t[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    n0 = ref - np.dot(ref, t[0]) * t[0]
    nrm[0] = n0 / np.linalg.norm(n0)
    for i in range(n - 1):
        v1 = p[i + 1] - p[i]
        c1 = float(np.dot(v1, v1))
        if c1 < 1e-18:
            nrm[i + 1] = nrm[i]
            continue
        r_l = nrm[i] - (2.0 / c1) * np.dot(v1, nrm[i]) * v1
        t_l = t[i] - (2.0 / c1) * np.dot(v1, t[i]) * v1
        v2 = t[i + 1] - t_l
        c2 = float(np.dot(v2, v2))
        nn = r_l if c2 < 1e-18 else r_l - (2.0 / c2) * np.dot(v2, r_l) * v2
        nrm[i + 1] = nn / np.linalg.norm(nn)
    b = np.cross(t, nrm)
    return t, nrm, b


def path_sweep(profile: "Path2D", path: "Path2D | Path3D", res: int = 12, twist: float = 0.0) -> PyShape:
    """Sweep a 2-D `profile` (list of ``[u, v]`` cross-section points) along a 3-D `path`.

    (a list of ``[x, y, z]`` points -- 2-D points are lifted to ``z = 0``), as a libfive SDF.

    At each path sample the profile is placed in a rotation-minimizing frame (see
    :func:`_rmf_frames`) -- ``u`` along the frame normal, ``v`` along the binormal -- and the swept
    solid is the union (``min``) of those oriented cross-sections. Because a union of exact SDFs is
    exact, this is a true signed-distance field: it can be ``.round()``/``.chamfer()``ed, meshed at
    any resolution, or combined with other backends' solids via ``.to_csg()`` like any other
    :class:`PyShape`. Denser paths give a smoother lateral surface (the sweep converges from the
    faceted union of cross-sections). The ends are capped perpendicular to the path.

    `profile` may be any SIMPLE polygon -- convex OR concave (the cross-section is evaluated with
    :func:`_polygon_sdf_xy`'s convex-deficiency decomposition, the same one :func:`polygon_prism`
    uses over the convex-only :func:`polygon_extrude`). `twist` is a total rotation of the profile
    (in degrees) applied evenly along the path.

    Args:
        profile: The cross-section to sweep, as ``[u, v]`` points.
        path: The path to sweep it along.
        res: Sampling resolution for the SDF backend. Omitted, the ambient ``use_defaults(res=...)`` value applies.
        twist: Total twist in degrees applied along the sweep.

    """
    prof = as_points(require_path(profile, "profile", "path_sweep", Path2D))
    if not (len(prof) >= 3):
        raise Bosl2ValueError("sweep profile needs at least 3 points")
    spine = require_path(path, "path", "path_sweep")
    pts3 = [list(p) + [0.0] * (3 - len(p)) for p in np.asarray(spine, dtype=float).tolist()]
    if not (len(pts3) >= 2):
        raise Bosl2ValueError("sweep path needs at least 2 points")
    p = np.asarray(pts3, dtype=float)
    tang, norm, binorm = _rmf_frames(p)
    n = len(p)

    seg = np.linalg.norm(p[1:] - p[:-1], axis=1)
    # Each station's cross-section occupies [-ext_back, +ext_fwd] along its tangent. Interior
    # stations reach 0.6 of the way into each neighbouring segment, so consecutive slabs always
    # overlap (a gap-free union even where the path curves); the two ends cap exactly at the path
    # endpoints (ext = 0 on the outward side), so the sweep does not overshoot.
    ext_back = np.zeros(n)
    ext_fwd = np.zeros(n)
    for i in range(n):
        ext_fwd[i] = 0.0 if i == n - 1 else 0.6 * seg[i]
        ext_back[i] = 0.0 if i == 0 else 0.6 * seg[i - 1]

    tws = np.radians(twist) * (np.arange(n) / (n - 1)) if twist else np.zeros(n)

    stations = []
    for i in range(n):
        ca, sa = math.cos(tws[i]), math.sin(tws[i])
        stations.append(
            (
                tuple(p[i]),
                tuple(norm[i]),
                tuple(binorm[i]),
                tuple(tang[i]),
                float(ext_back[i]),
                float(ext_fwd[i]),
                ca,
                sa,
            )
        )

    # The concave-safe cross-section decomposition depends only on the profile, so normalise its
    # winding once here rather than re-deriving it inside _polygon_sdf_xy at every station.
    prof_ccw = _ccw(prof)

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        total = None
        for (cx, cy, cz), (nx, ny, nz), (bx, by, bz), (tx, ty, tz), eb, ef, ca, sa in stations:
            dx, dy, dz = x - cx, y - cy, z - cz
            u = nx * dx + ny * dy + nz * dz
            v = bx * dx + by * dy + bz * dz
            w = tx * dx + ty * dy + tz * dz
            if sa:  # twist: rotate the query into the profile's frame
                u, v = ca * u + sa * v, -sa * u + ca * v
            # cross-section SDF in the frame's (u, v) plane -- concave-safe decomposition
            pd = _convex_deficiency_sdf(u, v, prof_ccw)
            # signed distance to the tangent interval [-eb, ef]
            cap = lv.max((-eb) - w, w - ef)
            slab = lv.max(pd, cap)
            total = slab if total is None else lv.min(total, slab)
        return total

    # Bounds: the profile's bounding-box corners, rotated by each station's twist, placed in the
    # frame. Using the bbox corners (rather than the exact vertices) deliberately leaves a little
    # slack around a convex outline -- frep()'s octree needs the surface strictly *inside* the
    # sampled domain to see a sign change (see PyShape.mesh) -- while rotating them keeps a twisted
    # profile's true extent inside the domain (a corner reaches sqrt2x its bbox half-width).
    umin, umax = float(prof[:, 0].min()), float(prof[:, 0].max())
    vmin, vmax = float(prof[:, 1].min()), float(prof[:, 1].max())
    bbox = [(umin, vmin), (umax, vmin), (umin, vmax), (umax, vmax)]
    world = []
    for i in range(n):
        ca, sa = math.cos(tws[i]), math.sin(tws[i])
        for cu, cv in bbox:
            fu = ca * cu - sa * cv  # frame coords of the corner (inverse of the query twist)
            fv = sa * cu + ca * cv
            base = p[i] + fu * norm[i] + fv * binorm[i]
            world.append(base + ext_fwd[i] * tang[i])
            world.append(base - ext_back[i] * tang[i])
    world_arr = np.asarray(world)
    mn = world_arr.min(axis=0).tolist()
    mx = world_arr.max(axis=0).tolist()
    return PyShape(sdf_fn, mn, mx, res)


def bezier_sweep(
    profile: "Path2D",
    control_points: "Path2D | Path3D",
    splinesteps: int = 24,
    res: int = 12,
    twist: float = 0.0,
) -> PyShape:
    """Sweep a 2-D `profile` (convex or concave) along a 3-D Bezier curve, as a libfive SDF.

    `control_points` are the Bezier control points (any degree). The curve is generated with
    pybosl2's canonical :class:`pybosl2.beziers.Bezier` (``splinesteps`` segments) and swept by
    :func:`path_sweep`, so bezier generation and the signed-distance sweep compose directly::

        from pybosl2.sdf.shapes3d import bezier_sweep
        circle = [[2 * math.cos(t), 2 * math.sin(t)] for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
        tube = bezier_sweep(circle, [[0, 0, 0], [0, 0, 20], [25, 12, 15], [30, 4, 6]])

    Args:
        profile: The cross-section to sweep.
        control_points: Control points of the bezier the profile follows.
        splinesteps: How many segments the bezier is flattened into.
        res: Sampling resolution for the SDF backend. Omitted, the ambient ``use_defaults(res=...)`` value applies.
        twist: Total twist in degrees applied along the sweep.

    """
    from pybosl2.beziers import Bezier

    curve = Bezier(require_path(control_points, "control_points", "bezier_sweep")).curve(splinesteps=splinesteps)
    return path_sweep(profile, curve, res=res, twist=twist)


def stroke_3d(
    path: Any,
    width: float = 1,
    closed: bool | None = None,
    endcap1: CapSpec | None = None,
    endcap2: CapSpec | None = None,
) -> PyShape:
    """3-D stroke for the SDF backend: a tube along *path* built from native SDF cylinders and spheres.

    Unlike the CSG stroke, this does NOT use ``rotate_extrude`` — it builds each segment as a
    Z-axis cylinder oriented along the path via ``multmatrix``, with spheres at joints and
    (for round caps) at the ends.  Fancy endcaps (arrow, diamond, etc.) are rejected with
    ``UnsupportedByBackendError`` since they require ``rotate_extrude``.

    Args:
        path: A point list or Path3D object.
        width: Tube diameter.
        closed: True to close the path loop.
        endcap1: Cap Spec for the start.
        endcap2: Cap Spec for the end.

    Returns:
        A :class:`PyShape` union of the tube segments.

    """
    import numpy as np

    from pybosl2._helpers import rot_from_to4
    from pybosl2.caps import CapSpec, CapType

    pts = [list(map(float, p)) for p in path]
    if not (len(pts) >= 2):
        raise Bosl2ValueError("stroke_3d: need at least 2 points.")
    is_closed = closed if closed is not None else getattr(path, "closed", False)
    ec1 = endcap1 if endcap1 is not None else CapSpec(cap_type=CapType.ROUND)
    ec2 = endcap2 if endcap2 is not None else CapSpec(cap_type=CapType.ROUND)

    radius = width / 2
    shapes: list[PyShape] = []
    sides = len(pts)

    for i in range(sides) if is_closed else range(sides - 1):
        a = np.asarray(pts[i], dtype=float)
        b = np.asarray(pts[(i + 1) % sides], dtype=float)
        d = b - a
        seg_len = float(np.linalg.norm(d))
        if seg_len < 1e-9:
            continue
        mid = (a + b) / 2
        seg = cylinder(length=seg_len, radius=radius, center=True)
        rot = rot_from_to4([0, 0, 1], d)
        rot[:3, 3] = mid
        shapes.append(seg.multmatrix(rot))

    for i in range(sides) if is_closed else range(1, sides - 1):
        shapes.append(sphere(radius=radius).translate(pts[i]))

    if not is_closed and sides >= 2:
        caps = [(ec1, pts[0], pts[1]), (ec2, pts[-1], pts[-2])]
        for cap, end, _ref in caps:
            if cap.cap_type in (CapType.NONE, CapType.BUTT):
                continue
            if cap.cap_type == CapType.ROUND:
                shapes.append(sphere(radius=radius).translate(end))
                continue
            if cap.cap_type == CapType.DOT:
                shapes.append(sphere(radius=width).translate(end))
                continue
            import warnings

            warnings.warn(
                f"Decorative endcap {cap.cap_type!r} not supported on SDF backend; falling back to ROUND sphere",
                stacklevel=2,
            )
            shapes.append(sphere(radius=radius).translate(end))

    if not (shapes):
        raise Bosl2ValueError("stroke_3d: path has no drawable segments.")
    return SdfSolid.union(*shapes)


PyShape = SdfSolid

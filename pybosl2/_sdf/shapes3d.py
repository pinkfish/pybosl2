# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


# The 3-D layer: PyShape (the lazy symbolic-SDF solid) and every 3-D shape constructor --
# cuboid/cube/sphere/cyl-family/torus/tube/pie_slice/prismoid/rect_tube/wedge/octahedron/
# convex_polyhedron/teardrop/onion/heightfield, the standalone cutters
# (interior_fillet/rounding_edge_mask/polygon_extrude), and polygon_prism (the
# offset_sweep-equivalent extrusion with rim treatments). See pybosl2/_sdf/__init__.py's
# module docstring for the design rationale.
#

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Callable, cast

import numpy as np

from pybosl2._backend import check_operand_backend as _check_operand_backend
from pybosl2._backend import unsupported_feature as _unsupported_feature
from pybosl2._native import native
from pybosl2._sdf._constants import BOTTOM, CENTER, FRONT, LEFT
from pybosl2._sdf._edges import (
    _anchor_offset_box3,
    _anchor_offset_cyl,
    _anchor_offset_hull3,
    _anchor_offset_sphere,
    _edges,
    _pick_radius,
)
from pybosl2._sdf._libfive import LVTree, lv
from pybosl2._sdf.paths import (
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
from pybosl2.distributors import Distributable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import ArrayLike, NDArray

    from pybosl2.caps import CapSpec


def _matmul3(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _axis_angle_matrix(deg: float, axis: list[float]) -> list[list[float]]:
    """Standard Rodrigues' rotation matrix for `deg` degrees around `axis` (need not be unit)."""
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
    """3x3 rotation matrix matching the real rotate(obj, a, v)'s two calling conventions:
    `a` a lone angle (degrees) with an explicit axis `v`, or (v is None) `a` a 3-vector of Euler
    angles [x, y, z] applied X-then-Y-then-Z -- the same composition order OpenSCAD's own
    rotate([x, y, z]) uses."""
    if v is not None:
        return _axis_angle_matrix(cast("float", a), v)
    ax, ay, az = a  # type: ignore[misc]
    rx = _axis_angle_matrix(ax, [1, 0, 0])
    ry = _axis_angle_matrix(ay, [0, 1, 0])
    rz = _axis_angle_matrix(az, [0, 0, 1])
    return _matmul3(_matmul3(rz, ry), rx)


def _rounded_box_sdf(x: LVTree, y: LVTree, z: LVTree, size: list[float], r: float) -> LVTree:
    """Exact SDF for a box uniformly rounded on every edge and corner: the Minkowski sum of a
    box (shrunk by `r` on every side) with a sphere of radius `r` -- the same construction
    pybosl2.shapes3d.cuboid() itself special-cases via a real minkowski() for edges="ALL". Unlike
    _cuboid_edge_sdf()'s general per-axis-plane composition (max() of three independently
    rounded-rectangle extrusions, which only *approximates* the true corner blend and leaves a
    visible seam where the three rounded faces meet), this is a single closed-form expression
    with an exact, seamless spherical corner -- no per-axis composition, so no seam.
    """
    hx, hy, hz = [s / 2 - r for s in size]
    qx = lv.abs(x) - hx
    qy = lv.abs(y) - hy
    qz = lv.abs(z) - hz
    mqx, mqy, mqz = lv.max(qx, 0), lv.max(qy, 0), lv.max(qz, 0)
    outside = lv.sqrt(mqx * mqx + mqy * mqy + mqz * mqz)
    inside = lv.min(lv.max(lv.max(qx, qy), qz), 0)
    return outside + inside - r


def _edge_matrices(amount: float, edge_set: list[list[int]], mode: str) -> tuple[list[list[float]], list[list[str]]]:
    """The per-edge treatment state for a single (amount, edge_set, mode) selection, as the
    3x4 amounts/modes matrices _cuboid_edge_sdf() consumes (EDGE_OFFSETS row/column order)."""
    amounts = [[amount if edge_set[a][i] else 0.0 for i in range(4)] for a in range(3)]
    modes = [[mode] * 4 for _ in range(3)]
    return amounts, modes


def _cuboid_edge_sdf(
    x: LVTree, y: LVTree, z: LVTree, size: list[float], amounts: list[list[float]], modes: list[list[str]]
) -> LVTree:
    """The cuboid SDF (as an explicit function of the given x/y/z trees, so callers can pass
    shifted coordinates to compose translation) with an independent treatment per edge:
    `amounts[axis][i]` (rounding radius or chamfer size, per `modes[axis][i]`) in EDGE_OFFSETS
    order. Everything is folded into ONE evaluation -- chaining several treatments by
    max()-ing full cuboid SDFs (the old .round()/.chamfer() composition) leaves their zero
    sets coincident along every untreated face, which libfive's mesher refines to the bitter
    end (a plain box ballooned to ~1M triangles and minutes of meshing).
    """
    if all(m == "round" for row in modes for m in row) and len({a for row in amounts for a in row}) == 1:
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


class PyShape(Distributable):
    """Wraps a libfive SDF, kept as a *symbolic* function of (x, y, z) rather than an
    already-evaluated tree or an already-meshed solid, plus the bounding box (`mn`/`mx`)
    frep() needs and (for cuboid-shaped instances) enough metadata to add more edge
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
        treatments -- e.g. `cuboid(size).round(2, edges="Z").chamfer(1, edges=[TOP+LEFT])`
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

    def __init__(
        self,
        sdf_fn: Callable,
        mn: Sequence[float],
        mx: Sequence[float],
        res: int = 10,
        cuboid_size: Sequence[float] | None = None,
        cuboid_center: Sequence[float] = (0.0, 0.0, 0.0),
        cuboid_edge_amounts: list[list[float]] | None = None,
        cuboid_edge_modes: list[list[str]] | None = None,
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

    def _wrap(
        self,
        sdf_fn: Callable,
        mn: Sequence[float],
        mx: Sequence[float],
        cuboid_size: Sequence[float] | None = None,
        cuboid_center: Sequence[float] = (0.0, 0.0, 0.0),
        cuboid_edge_amounts: list[list[float]] | None = None,
        cuboid_edge_modes: list[list[str]] | None = None,
    ) -> PyShape:
        return PyShape(
            sdf_fn,
            mn,
            mx,
            self.res,
            cuboid_size,
            cuboid_center,
            cuboid_edge_amounts,
            cuboid_edge_modes,
        )

    def sdf(self) -> LVTree:
        """The fully-evaluated libfive expression tree, at the real coordinate trees."""
        return self._sdf_fn(lv.x(), lv.y(), lv.z())

    def bounds(self) -> tuple[list[float], list[float]]:
        """``(center, size)`` of this shape's axis-aligned bounding box (BOSL2/Bosl2Solid convention).

        Exact and cheap -- every SDF constructor records its tight ``mn``/``mx``, so no meshing is
        needed (unlike measuring a CSG solid). Matches :meth:`pybosl2.shapes3d.Bosl2Solid.bounds`.
        """
        center = [(a + b) / 2 for a, b in zip(self.mn, self.mx, strict=False)]
        size = [b - a for a, b in zip(self.mn, self.mx, strict=False)]
        return center, size

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

    def __getattr__(self, name: str) -> Any:
        # A CSG-only feature (attachment/anchoring) on the SDF backend raises a clear error rather
        # than meshing (libfive) just to fail with a confusing AttributeError.
        if not (name.startswith("__") and name.endswith("__")):
            _unsupported = _unsupported_feature("sdf", name)
            if _unsupported is not None:
                raise _unsupported
        # Anything else (color/show/... or any other real PyOpenSCAD method) falls through to the
        # meshed solid.
        return getattr(self.mesh(), name)

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

    def rotate(self, a: float | Sequence[float], v: list[float] | None = None) -> PyShape:
        """Rotate the SDF itself (`f(p) -> f(R^-1 p)`), exact and free -- no meshing involved,
        so (like translate()) a shape can still be .round()ed/.chamfer()ed/composed afterward
        without forcing an early mesh. Matches the real rotate(obj, a, v)'s two calling
        conventions: `rotate(angle, axis)`, or `rotate([x, y, z])` for Euler angles.

        Unlike translate(), this drops cuboid_size/cuboid_center metadata (so round()/chamfer()
        assert afterward) -- edges="TOP"/"LEFT"/etc. are global-frame selectors, evaluated
        before any rotation, the same order pybosl2's own anchor/edges-then-spin/orient applies
        them in, so treating edges post-rotation wouldn't mean what it looks like it means.
        """
        m = _rotation_matrix(a, v)
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

    def scale(self, v: float | Sequence[float]) -> PyShape:
        """Scale the SDF (`f(p) -> s_min * f(p / s)`), exact zero set, no meshing involved --
        `v` a single factor or a per-axis [sx, sy, sz], matching the real scale(). The value is
        renormalized by the smallest factor so it stays a conservative (never-overestimating)
        distance under non-uniform scaling; for uniform scaling it stays exact. Drops
        cuboid_size/cuboid_center metadata (so round()/chamfer() assert afterward), same
        rationale as rotate(): edge selectors are pre-transform concepts.
        """
        s = [float(v)] * 3 if isinstance(v, (int, float)) else [float(a) for a in v]
        assert all(a > 0 for a in s), f"scale() factors must be positive, got {s}"
        fn = self._sdf_fn
        smin = min(s)
        new_fn = lambda x, y, z: smin * fn(x / s[0], y / s[1], z / s[2])  # noqa: E731
        new_mn = [self.mn[i] * s[i] for i in range(3)]
        new_mx = [self.mx[i] * s[i] for i in range(3)]
        return self._wrap(new_fn, new_mn, new_mx)

    def mirror(self, v: list[float]) -> PyShape:
        """Reflect across the plane through the origin with normal `v` (`f(p) -> f(Mp)`, with
        M the Householder reflection), exact and free, matching the real mirror(). Drops
        cuboid_size/cuboid_center metadata, same rationale as rotate(): edge selectors are
        pre-transform concepts."""
        nx, ny, nz = (float(a) for a in v)
        nlen = math.sqrt(nx * nx + ny * ny + nz * nz)
        assert nlen > 0, "mirror() normal must be nonzero"
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
        """Apply a 4x4 affine transformation matrix to the SDF, exact and free."""
        import numpy as np

        m = np.asarray(matrix, dtype=float)
        assert m.shape == (4, 4), "multmatrix requires a 4x4 matrix"
        try:
            mt = np.linalg.inv(m)
        except np.linalg.LinAlgError:
            raise ValueError("multmatrix requires an invertible matrix") from None

        fn = self._sdf_fn

        def new_fn(x, y, z):
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
        return self._wrap(new_fn, new_mn, new_mx)

    def _distribute(self, mats: list[np.ndarray]) -> list:
        """Return a list of multmatrix copies of this shape, one per matrix."""
        return [self.multmatrix(m) for m in mats]

    def to_sdf(self) -> PyShape:
        """This solid is already on the SDF backend -- returns self (the converter no-op)."""
        return self

    def to_csg(self) -> Any:
        """Convert to the CSG backend: mesh the SDF (libfive frep) and wrap it as a Bosl2Solid.

        Exact -- the meshed surface IS the field's zero set. This is the supported bridge for mixing
        an SDF shape into CSG booleans (``csg_solid | sdf_solid.to_csg()``). Needs libfive at call
        time (like any SDF meshing)."""
        from pybosl2.shapes3d import Bosl2Solid

        return Bosl2Solid(self.mesh())

    def __or__(self, other: PyShape) -> PyShape:
        _check_operand_backend("sdf", other)
        return PyShape.union(self, other)

    def __and__(self, other: PyShape) -> PyShape:
        _check_operand_backend("sdf", other)
        return PyShape.intersection(self, other)

    def __sub__(self, other: PyShape) -> PyShape:
        _check_operand_backend("sdf", other)
        return PyShape.difference(self, other)

    def __ror__(self, other: PyShape) -> PyShape:
        _check_operand_backend("sdf", other)
        return PyShape.union(other, self)

    def __rand__(self, other: PyShape) -> PyShape:
        _check_operand_backend("sdf", other)
        return PyShape.intersection(other, self)

    def __rsub__(self, other: PyShape) -> PyShape:
        _check_operand_backend("sdf", other)
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
        """The union of the given PyShapes (min() of their SDFs), as one PyShape.

        Accepts either varargs or a single list.
        """
        shs = _as_shape_list(shapes)
        if len(shs) == 1:
            return shs[0]
        fns = [s._sdf_fn for s in shs]

        def sdf_fn(x, y, z):
            return _balanced(lv.min, [f(x, y, z) for f in fns])

        mn = [min(s.mn[i] for s in shs) for i in range(3)]
        mx = [max(s.mx[i] for s in shs) for i in range(3)]
        return PyShape(sdf_fn, mn, mx, max(s.res for s in shs))

    @staticmethod
    def intersection(*shapes: PyShape) -> PyShape:
        """The intersection of the given PyShapes (max() of their SDFs), as one PyShape.

        Accepts either varargs or a single list.
        """
        shs = _as_shape_list(shapes)
        if len(shs) == 1:
            return shs[0]
        fns = [s._sdf_fn for s in shs]

        def sdf_fn(x, y, z):
            return _balanced(lv.max, [f(x, y, z) for f in fns])

        mn = [max(s.mn[i] for s in shs) for i in range(3)]
        mx = [min(s.mx[i] for s in shs) for i in range(3)]
        assert all(mn[i] < mx[i] for i in range(3)), (
            f"intersection(): the shapes' bounding boxes don't overlap (got mn={mn}, mx={mx})"
        )
        return PyShape(sdf_fn, mn, mx, max(s.res for s in shs))

    @staticmethod
    def difference(shape: PyShape, *tools: PyShape) -> PyShape:
        """`shape` minus the union of every `tool` (max(f, -min(tools))), as one PyShape."""
        assert isinstance(shape, PyShape), f"difference() base must be a PyShape, got {type(shape).__name__}"
        if not tools:
            return shape
        tls = _as_shape_list(tools)
        fa = shape._sdf_fn
        fns = [t._sdf_fn for t in tls]

        def sdf_fn(x, y, z):
            return lv.max(fa(x, y, z), -_balanced(lv.min, [f(x, y, z) for f in fns]))

        return PyShape(sdf_fn, list(shape.mn), list(shape.mx), shape.res)

    # ---- cuboid-only edge treatments ----

    def _edge_treat(self, amount: float, edges: Any, except_edges: Any, mode: str) -> PyShape:
        assert self.cuboid_size is not None, f"{mode}() requires a cuboid-shaped PyShape (from pybosl2._sdf.cuboid())"
        assert self.cuboid_edge_amounts is not None and self.cuboid_edge_modes is not None, (
            f"{mode}() requires the cuboid's per-edge treatment state (lost by rotate()/scale()/booleans)"
        )
        edge_set = _edges(edges, except_edges or [])
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

    def round(self, radius: float, edges: str | list = "ALL", except_edges: list[Any] | None = None) -> PyShape:
        """Round the selected edges by `radius`, in addition to any existing edge treatment."""
        return self._edge_treat(radius, edges, except_edges, "round")

    def chamfer(self, size: float, edges: str | list = "ALL", except_edges: list[Any] | None = None) -> PyShape:
        """Chamfer the selected edges by `size`, in addition to any existing edge treatment."""
        return self._edge_treat(size, edges, except_edges, "chamfer")

    # -- hull / projection: the counterparts of Bosl2Solid's, on the SDF side ------------------

    def hull(self, *others: Any, directions: int = 64, res: int | None = None) -> PyShape:
        """The convex hull of this shape, optionally together with *others* (BOSL2 hull())."""
        args = list(self) + list(others) if isinstance(self, (list, tuple)) else [self] + list(others)

        if len(args) == 1 and isinstance(args[0], (list, tuple)) and args[0] and isinstance(args[0][0], PyShape):
            args = list(args[0])
        assert args, "hull() needs at least one shape or point set"

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
                assert pts.ndim == 2 and pts.shape[1] == 3, (
                    f"hull(): point arguments must be Nx3 array-likes, got shape {pts.shape}"
                )
                entries.append(("points", pts))
                for i in range(3):
                    mn[i] = min(mn[i], float(pts[:, i].min()))
                    mx[i] = max(mx[i], float(pts[:, i].max()))

        state: dict = {}

        def planes() -> list[tuple[float, float, float, float]]:
            if "planes" not in state:
                pools = []
                for kind, v in entries:
                    if kind == "points":
                        pools.append(v)
                    else:
                        verts, _faces = v.mesh().mesh()
                        assert verts, "hull(): a child shape meshed to nothing (empty geometry)"
                        pools.append(np.asarray(verts, dtype=float))
                sup = _support_points(np.concatenate(pools), directions)
                state["planes"] = _hull_planes([[float(c) for c in p] for p in sup])
            return state["planes"]

        def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
            terms = [nx * x + ny * y + nz * z - off for nx, ny, nz, off in planes()]
            return _balanced(lv.max, terms)

        return PyShape(
            sdf_fn,
            mn,
            mx,
            res if res is not None else (max(child_res) if child_res else 10),
        )

    def projection(self, cut: bool = False) -> Any:
        """Not available on the SDF backend -- an implicit field has no closed-form 2-D shadow.

        Raises:
            ~pybosl2.exceptions.UnsupportedByBackendError: always. Convert first
            (``shape.to_csg().projection()``) if a meshed projection is acceptable.
        """
        _ = cut
        from pybosl2.exceptions import UnsupportedByBackendError

        raise UnsupportedByBackendError(
            "projection",
            "sdf",
            hint="a signed-distance field has no closed-form 2-D shadow, and 2-D geometry is a "
            "csg-backend notion. Mesh it first with shape.to_csg().projection() if that is "
            "acceptable, or build the shape on the csg backend.",
        )


# ---------------------------------------------------------------------------
# Section: Named CSG combinators (union / difference / intersection / hull)
# ---------------------------------------------------------------------------


def _as_shape_list(shapes: tuple[Any, ...]) -> list[PyShape]:
    """Varargs-or-single-iterable: `union(a, b)` and `union([a, b])` both work, matching the
    two calling conventions the box libraries already mix (OpenSCAD-style children vs.
    pybosl2-style list arguments)."""
    if len(shapes) == 1 and isinstance(shapes[0], (list, tuple)):
        shapes = tuple(shapes[0])
    out = list(shapes)
    assert out, "need at least one shape"
    assert all(isinstance(s, PyShape) for s in out), (
        f"every argument must be a PyShape, got {[type(s).__name__ for s in out]}"
    )
    return out


def _balanced(op: Callable[[LVTree, LVTree], LVTree], vals: list[Any]) -> LVTree:
    """Reduce `vals` with `op` as a balanced tree (depth log n) rather than a left fold
    (depth n) -- same node count either way, but libfive re-evaluates the whole expression
    per sample point and shallow trees keep its interval pruning effective on wide unions."""
    while len(vals) > 1:
        vals = [op(vals[i], vals[i + 1]) if i + 1 < len(vals) else vals[i] for i in range(0, len(vals), 2)]
    return vals[0]


def _support_points(points: ArrayLike, n_dirs: int) -> NDArray[np.float64]:
    """Decimate a point cloud to at most `n_dirs + 6` extreme (support) points: for each of
    `n_dirs` directions spread over the sphere (a Fibonacci lattice, plus the 6 axis
    directions so bounding-box extremes always survive), keep the farthest point along it.
    The hull of the survivors is an inscribed approximation of the cloud's hull: exact at
    every vertex that is the unique maximizer of some kept direction (a cuboid's 8 corners
    all are, well before n_dirs reaches double digits), with error bounded by the direction
    spacing for smooth clouds."""
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
    return pts[idx]


def _hull_planes(pts: list[list[float]]) -> list[tuple[float, float, float, float]]:
    """The supporting planes of the convex hull of `pts`, as (nx, ny, nz, offset) tuples with
    unit outward normals -- brute force over point triples (every non-degenerate triple whose
    plane has all points on one side is a hull face plane, deduplicated). O(n^4) in the point
    count, entirely fine for the tens-of-points sets convex_polyhedron()/hull() feed it, and
    it happens once in Python at construction time, not per SDF evaluation."""
    n = len(pts)
    scale = max(max(abs(v) for v in p) for p in pts) or 1.0
    eps = 1e-9 * scale

    planes: list[tuple[float, float, float, float]] = []
    seen: set = set()
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
                assert not all(abs(s) <= eps for s in side), (
                    "hull planes: points are coplanar -- that's a 2-D outline, not a solid"
                )
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
    assert planes, "hull planes: no supporting planes found -- are the points coplanar?"
    return planes


def _cuboid_flare_sdf(
    x: LVTree, y: LVTree, z: LVTree, size: list[float], r: float, edge_set: list[list[int]]
) -> LVTree:
    """The cuboid SDF with BOSL2's negative-rounding treatment (an external cove flare) on the
    selected X/Y-axis edges: the top/bottom face extends outward by `r` in the horizontal
    direction, then a concave quarter-arc sweeps back to the side face -- exactly BOSL2's
    construction (an added edge block with a cylinder of radius `r`, centered `r` outward
    horizontally and `r` inward vertically from the edge, carved out of it). Z-axis edges are
    rejected by cuboid() itself, matching BOSL2's own assert.
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


def cuboid(
    size: float | list[float] | None = None,
    rounding: float = 0,
    chamfer: float = 0,
    edges: str | list = "ALL",
    except_edges: list[Any] | None = None,
    res: int = 10,
    anchor: "Sequence[float]" = CENTER,
) -> PyShape:
    """A cuboid with optional per-edge rounding or chamfering, built as a libfive signed
    distance function (F-Rep) and returned as a PyShape (meshed lazily, via frep(), on first
    use) -- see pybosl2.shapes3d.cuboid() for the equivalent BOSL2-style mesh-CSG version
    (identical `edges=`/`except_edges=` semantics; both accept the same edge selector values,
    since pybosl2._sdf._edges's edge-set resolver is a byte-for-byte copy of pybosl2's own).

    `rounding` and `chamfer` are mutually exclusive in a single call (matching
    pybosl2.shapes3d.cuboid()); to mix both on different edges of the same cuboid, chain
    PyShape.round()/.chamfer() calls instead, e.g.
    `cuboid(size).round(2, edges="Z").chamfer(1, edges=[TOP+LEFT])`.

    Args:
        size:         size of the cuboid, a number or length-3 vector
        rounding:     edge rounding radius applied to every selected edge (default: no rounding)
        chamfer:      edge chamfer size applied to every selected edge (default: no chamfer)
        edges:        edges to treat -- "ALL"/"NONE"/"X"/"Y"/"Z", a single edge vector (e.g.
                      TOP+LEFT), a list of edge vectors, or a raw 3x4 edge array (default "ALL")
        except_edges: edges to explicitly exclude from `edges` (BOSL2's `except=` synonym;
                      `except` is a Python keyword)
        res:          libfive meshing resolution passed to frep() (default 10; higher = finer mesh)
        anchor:       anchor point (default CENTER)

    Examples:
        .. pythonscad-example::

            import pybosl2._sdf.shapes3d as sdf_s3d
            shape = sdf_s3d.cuboid([20.0, 20.0, 20.0], rounding=4)
            shape.show()

        .. pythonscad-example::

            import pybosl2._sdf.shapes3d as sdf_s3d
            shape = sdf_s3d.cuboid([20.0, 20.0, 20.0], chamfer=4)
            shape.show()

        Rounding only the 4 vertical edges (the per-axis-composition fallback path, not the
        exact-formula ``edges="ALL"`` case above):

        .. pythonscad-example::

            import pybosl2._sdf.shapes3d as sdf_s3d
            shape = sdf_s3d.cuboid([20.0, 20.0, 20.0], rounding=4, edges="Z")
            shape.show()
    """
    if size is None:
        size = [1, 1, 1]
    assert not (rounding and chamfer), "Cannot specify nonzero value for both rounding and chamfer"
    sz: list[float] = [float(v) for v in size] if isinstance(size, (list, tuple)) else [float(size)] * 3
    edge_set = _edges(edges, except_edges or [])
    half = [s / 2 for s in sz]
    if rounding < 0:
        # BOSL2's negative rounding: an external cove flare on the selected edges (see
        # _cuboid_flare_sdf). Same restriction as BOSL2: no Z-aligned edges.
        assert edge_set[2] == [0, 0, 0, 0], "Cannot use negative rounding with Z aligned edges"
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
        if offset[0] or offset[1] or offset[2]:
            shape = shape.translate(offset)
        return shape
    mode = "chamfer" if chamfer else "round"
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
    if offset[0] or offset[1] or offset[2]:
        shape = shape.translate(offset)
    return shape


def cube(size: float | list[float] = 1, anchor: "Sequence[float]" = CENTER, res: int = 10) -> PyShape:
    """A cube, as a plain (unrounded) libfive SDF. See cuboid() for rounding/chamfering."""
    return cuboid(size=size, anchor=anchor, res=res)


# ---------------------------------------------------------------------------
# Section: Other simple solids without a BOSL2 rounding/chamfer concept
# ---------------------------------------------------------------------------


def octahedron(size: float = 1, anchor: "Sequence[float]" = CENTER, res: int = 10) -> PyShape:
    """An octahedron with axis-aligned points (`|x|+|y|+|z| <= size/2`), as a libfive SDF."""
    s = size / 2
    sdf_fn = lambda x, y, z: lv.abs(x) + lv.abs(y) + lv.abs(z) - s  # noqa: E731
    shape = PyShape(sdf_fn, [-s, -s, -s], [s, s, s], res)
    pts = [[s, 0, 0], [-s, 0, 0], [0, s, 0], [0, -s, 0], [0, 0, s], [0, 0, -s]]
    offset = _anchor_offset_hull3(pts, anchor)
    if any(offset):
        shape = shape.translate(offset)
    return shape


def convex_polyhedron(points: ArrayLike, res: int = 10) -> PyShape:
    """The convex hull of `points` as a libfive SDF: the max of the hull faces' signed
    half-space distances -- the 3-D analogue of polygon_extrude()'s half-plane form, with the
    same documented value tradeoff (exact perpendicular distance at faces, sign-correct
    underestimate out past edges/vertices). Covers the dice-style solids (tetrahedron,
    dodecahedron, icosahedron, trapezohedron, ...) that shapes3d.py builds, without needing
    BOSL2's polyhedra.scad or a mesh hull().

    Face planes come from a brute-force hull: every non-degenerate point triple whose plane has
    all points on one side is a supporting plane (deduplicated). That's O(n^4) in the point
    count -- entirely fine for the tens-of-vertices solids this is for, and it happens once in
    Python at construction time, not per SDF evaluation.
    """
    points = np.asarray(points, dtype=float)
    pts = [[float(v) for v in p] for p in points]
    n = len(pts)
    assert n >= 4, f"convex_polyhedron() needs at least 4 points, got {n}"
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
    anchor: "Sequence[float] | None" = None,
    res: int = 10,
) -> PyShape:
    """A 3-D triangular wedge with the hypotenuse in the X+Z+ quadrant, as a libfive SDF.

    Args:
        size:   [width, thickness, height]
        anchor: anchor point (default FRONT+LEFT+BOTTOM, matching pybosl2.shapes3d.wedge())
    """
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
    if any(offset):
        shape = shape.translate(offset)
    return shape


def sphere(
    radius: float | None = None,
    diameter: float | None = None,
    anchor: "Sequence[float]" = CENTER,
    res: int = 10,
) -> PyShape:
    """A sphere, as a libfive SDF (`length(p) - r`).

    Examples:
        .. pythonscad-example::

            import pybosl2._sdf.shapes3d as sdf_s3d
            shape = sdf_s3d.sphere(radius=10)
            shape.show()
    """
    rad = _radius(radius=radius, diameter=diameter, dflt=1)
    sdf_fn = lambda x, y, z: lv.sqrt(x * x + y * y + z * z) - rad  # noqa: E731
    shape = PyShape(sdf_fn, [-rad, -rad, -rad], [rad, rad, rad], res)
    offset = _anchor_offset_sphere(rad, anchor)
    if any(offset):
        shape = shape.translate(offset)
    return shape


def spheroid(
    radius: float | None = None,
    diameter: float | None = None,
    anchor: "Sequence[float]" = CENTER,
    res: int = 10,
) -> PyShape:
    """An approximate sphere; this pure-libfive port just builds a plain sphere() (matching
    pybosl2.shapes3d.spheroid()'s own choice to ignore style/dual for its pure-Python port)."""
    return sphere(radius=radius, diameter=diameter, anchor=anchor, res=res)


def torus(
    major_radius: float | None = None,
    minor_radius: float | None = None,
    major_diameter: float | None = None,
    minor_diameter: float | None = None,
    outer_radius: float | None = None,
    inner_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_diameter: float | None = None,
    anchor: "Sequence[float]" = CENTER,
    res: int = 10,
) -> PyShape:
    """A torus (donut) shape, as a libfive SDF (`length(vec2(length(p.xy)-major_radius, p.z)) - minor_radius`).

    Note: BOSL2's outer-radius parameter is named `or`, which collides with the Python
    keyword `or`; it is exposed here as `outer_radius` instead. See pybosl2.shapes3d.torus() for
    the full parameter set this mirrors.

    Examples:
        .. pythonscad-example::

            import pybosl2._sdf.shapes3d as sdf_s3d
            shape = sdf_s3d.torus(major_radius=15, minor_radius=5)
            shape.show()
    """
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
        raise AssertionError("torus(): bad parameters.")
    if _r_min is not None:
        minr = _r_min
    elif _ir is not None:
        minr = maj - _ir
    elif _or is not None:
        minr = _or - maj
    else:
        raise AssertionError("torus(): bad parameters.")

    sdf_fn = lambda x, y, z: _lv_hypot(_lv_hypot(x, y) - maj, z) - minr  # noqa: E731
    outer = maj + minr
    shape = PyShape(sdf_fn, [-outer, -outer, -minr], [outer, outer, minr], res)
    offset = _anchor_offset_cyl(outer, outer, minr * 2, anchor)
    if any(offset):
        shape = shape.translate(offset)
    return shape


# ---------------------------------------------------------------------------
# Section: Cylinders
# ---------------------------------------------------------------------------


def _wall_line_sdf(rxy: LVTree, z: LVTree, radius1: float, radius2: float, hb: float) -> LVTree:
    """Signed distance to the infinite line through `(radius1, -hb)` and `(radius2, hb)` in the
    `(rxy, z)` half-plane -- the slanted wall of a cylinder/cone, exact for the wall itself;
    intersecting (max()) with the top/bottom slabs (see _cylinder_sdf()) caps it off, with the
    same corner-region approximation already documented for cuboid()'s per-axis composition.
    """
    dr, dz = radius2 - radius1, 2 * hb
    nlen = math.hypot(dr, dz)
    return ((rxy - radius1) * dz - (z + hb) * dr) / nlen


def _cylinder_sdf(
    x: LVTree, y: LVTree, z: LVTree, h: float, radius1: float, radius2: float, shift: list[float] | None = None
) -> LVTree:
    hb = h / 2
    if shift and (shift[0] or shift[1]):
        # Oblique cone (BOSL2 cyl(shift=)): the section center slides linearly from [0, 0]
        # at the bottom to `shift` at the top -- same interpolate-per-height construction
        # (and the same not-quite-Euclidean-but-zero-set-correct caveat) as prismoid().
        t = (z + hb) / h
        x = x - shift[0] * t
        y = y - shift[1] * t
    rxy = _lv_hypot(x, y)
    wall = _wall_line_sdf(rxy, z, radius1, radius2, hb)
    slab = lv.abs(z) - hb
    return lv.max(wall, slab)


def _cyl_edge_sdf(
    axial: LVTree, radial: LVTree, h: float, radius1: float, radius2: float, amt1: float, amt2: float, mode: str
) -> LVTree:
    """_cylinder_sdf(), plus independent rounding/chamfer treatment of the bottom (amt1) and
    top (amt2) rim, using the same per-candidate-quadrant masking technique as
    pybosl2.shapes3d.cuboid() (but only 2 candidates -- top/bottom -- since the radial
    coordinate has no sign ambiguity to select between, unlike a rectangle's 4 corners)."""
    hb = h / 2
    wall = _wall_line_sdf(radial, axial, radius1, radius2, hb)
    candidates = []
    for sz, r_ref, a in ((-1, radius1, amt1), (1, radius2, amt2)):
        if mode == "round":
            qu = radial - r_ref + a
            qv = lv.abs(axial) - hb + a
            base = lv.min(lv.max(qu, qv), 0) + _lv_hypot(lv.max(qu, 0), lv.max(qv, 0)) - a
        else:
            assert mode == "chamfer"
            qu = radial - r_ref
            qv = lv.abs(axial) - hb
            base = lv.max(lv.max(qu, qv), (qu + qv + a) / _SQRT2)
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
    anchor: "Sequence[float]" = CENTER,
    res: int = 10,
) -> PyShape:
    """A cylinder/cone (no rounding) as a libfive SDF -- see cyl() for rounding/chamfering."""
    length = length if length is not None else (height if height is not None else 1)
    rad1 = _radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
    rad2 = _radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter, dflt=1)
    use_anchor = anchor
    if center is not None:
        use_anchor = CENTER if center else BOTTOM
    sdf_fn = lambda x, y, z: _cylinder_sdf(x, y, z, length, rad1, rad2)  # noqa: E731
    maxr = max(rad1, rad2)
    shape = PyShape(sdf_fn, [-maxr, -maxr, -length / 2], [maxr, maxr, length / 2], res)
    offset = _anchor_offset_cyl(rad1, rad2, length, use_anchor)
    if any(offset):
        shape = shape.translate(offset)
    return shape


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
    shift: list[float] | None = None,
    anchor: "Sequence[float] | None" = None,
    res: int = 10,
) -> PyShape:
    """A cylinder/cone with optional rounding or chamfering of its end rims, as a libfive SDF.
    See pybosl2.shapes3d.cyl() for the full BOSL2-style version this mirrors (circum=/realign=/
    texture= aren't supported here; shift= is, for oblique cones, but not combined with
    rounding/chamfer).

    `rounding`/`chamfer` (and their `1`/`2` bottom/top variants) are mutually exclusive, same
    as pybosl2.shapes3d.cyl().

    Examples:
        .. pythonscad-example::

            import pybosl2._sdf.shapes3d as sdf_s3d
            shape = sdf_s3d.cyl(height=20, radius=8, rounding=2)
            shape.show()
    """
    length = length if length is not None else (height if height is not None else 1)
    rad1 = _radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
    rad2 = _radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter, dflt=1)
    use_anchor = anchor
    if use_anchor is None:
        use_anchor = CENTER if center is None or center else BOTTOM

    r1v = rounding1 if rounding1 is not None else (rounding if rounding is not None else 0)
    r2v = rounding2 if rounding2 is not None else (rounding if rounding is not None else 0)
    c1v = chamfer1 if chamfer1 is not None else (chamfer if chamfer is not None else 0)
    c2v = chamfer2 if chamfer2 is not None else (chamfer if chamfer is not None else 0)
    assert not ((r1v or r2v) and (c1v or c2v)), "Cannot specify nonzero value for both chamfer and rounding"
    mode, amt1, amt2 = ("chamfer", c1v, c2v) if (c1v or c2v) else ("round", r1v, r2v)

    if shift is not None and (shift[0] or shift[1]):
        assert not (amt1 or amt2), "shift= cannot be combined with rounding/chamfer"
        sdf_fn = lambda x, y, z: _cylinder_sdf(x, y, z, length, rad1, rad2, shift)  # noqa: E731
    else:
        sdf_fn = lambda x, y, z: _cyl_edge_sdf(z, _lv_hypot(x, y), length, rad1, rad2, amt1, amt2, mode)  # noqa: E731
    maxr = max(rad1, rad2)
    mn = [-maxr, -maxr, -length / 2]
    mx = [maxr, maxr, length / 2]
    if shift is not None:
        # The top section slides sideways by `shift` -- widen the bounds to cover it.
        for i in (0, 1):
            mn[i] = min(mn[i], mn[i] + shift[i])
            mx[i] = max(mx[i], mx[i] + shift[i])
    shape = PyShape(sdf_fn, mn, mx, res)
    offset = _anchor_offset_cyl(rad1, rad2, length, use_anchor)
    if any(offset):
        shape = shape.translate(offset)
    return shape


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
) -> PyShape:
    length = length if length is not None else (height if height is not None else 1)
    rad1 = _radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
    rad2 = _radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter, dflt=1)
    r1v = rounding1 if rounding1 is not None else (rounding if rounding is not None else 0)
    r2v = rounding2 if rounding2 is not None else (rounding if rounding is not None else 0)
    c1v = chamfer1 if chamfer1 is not None else (chamfer if chamfer is not None else 0)
    c2v = chamfer2 if chamfer2 is not None else (chamfer if chamfer is not None else 0)
    assert not ((r1v or r2v) and (c1v or c2v)), "Cannot specify nonzero value for both chamfer and rounding"
    mode, amt1, amt2 = ("chamfer", c1v, c2v) if (c1v or c2v) else ("round", r1v, r2v)

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        coords = [x, y, z]
        axial = coords[axis]
        others = [coords[i] for i in range(3) if i != axis]
        radial = _lv_hypot(others[0], others[1])
        return _cyl_edge_sdf(axial, radial, length, rad1, rad2, amt1, amt2, mode)

    maxr = max(rad1, rad2)
    mn, mx = [-maxr, -maxr, -maxr], [maxr, maxr, maxr]
    mn[axis], mx[axis] = -length / 2, length / 2
    shape = PyShape(sdf_fn, mn, mx, res)
    offset = _anchor_offset_cyl(rad1, rad2, length, anchor, axis=axis)
    if any(offset):
        shape = shape.translate(offset)
    return shape


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
    anchor: "Sequence[float]" = CENTER,
    res: int = 10,
) -> PyShape:
    """A cylinder oriented along the X axis. See cyl() for argument details."""
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
    anchor: "Sequence[float]" = CENTER,
    res: int = 10,
) -> PyShape:
    """A cylinder oriented along the Y axis. See cyl() for argument details."""
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
    anchor: "Sequence[float]" = CENTER,
    res: int = 10,
) -> PyShape:
    """A cylinder oriented along the Z axis (same as cyl()). See cyl() for argument details."""
    return _cyl_axis(
        2,
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
    length: float | None = None,
    anchor: "Sequence[float]" = CENTER,
    res: int = 10,
) -> PyShape:
    """A hollow cylindrical tube (outer cylinder minus inner cylinder), as a libfive SDF.

    Note: BOSL2's outer-radius parameters are named `or`/`or1`/`or2`; exposed here as
    `outer_radius`/`outer_r1`/`outer_r2` since `or` is a Python keyword.
    """
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
    assert rad1 is not None and rad2 is not None and irad1 is not None and irad2 is not None, (
        "tube(): must specify two of inner radius/diam, outer radius/diam, and wall width."
    )

    sdf_fn = lambda x, y, z: lv.max(  # noqa: E731
        _cylinder_sdf(x, y, z, length, rad1, rad2),
        -_cylinder_sdf(x, y, z, length, irad1, irad2),
    )
    maxr = max(rad1, rad2)
    shape = PyShape(sdf_fn, [-maxr, -maxr, -length / 2], [maxr, maxr, length / 2], res)
    offset = _anchor_offset_cyl(rad1, rad2, length, anchor)
    if any(offset):
        shape = shape.translate(offset)
    return shape


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
    anchor: "Sequence[float]" = CENTER,
    res: int = 10,
) -> PyShape:
    """A pie slice (wedge of a cylinder/cone), as a libfive SDF: a cylinder intersected with
    an angular sector (built from 1-2 half-planes -- `angle` is a plain Python float fixed at
    construction time, so choosing intersection vs union of the two half-planes based on
    `angle <= 180` is an ordinary Python conditional, not a per-point SDF branch)."""
    length = length if length is not None else (height if height is not None else 1)
    rad1 = _radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=10)
    rad2 = _radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter, dflt=10)
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

    maxr = max(rad1, rad2)
    shape = PyShape(sdf_fn, [-maxr, -maxr, -length / 2], [maxr, maxr, length / 2], res)
    offset = _anchor_offset_cyl(rad1, rad2, length, anchor)
    if any(offset):
        shape = shape.translate(offset)
    return shape


# ---------------------------------------------------------------------------
# Section: Cuboids, Prismoids and Tubes
# ---------------------------------------------------------------------------


def prismoid(
    size1: list[float],
    size2: list[float],
    height: float | None = None,
    shift: list[float] | None = None,
    length: float | None = None,
    anchor: "Sequence[float]" = BOTTOM,
    res: int = 10,
) -> PyShape:
    """A rectangular prismoid (truncated pyramid), as a libfive SDF.

    CAVEAT: unlike pybosl2.shapes3d.prismoid(), this pure-libfive port does not support
    rounding/chamfer of the vertical edges (deriving an exact SDF for a *tapered* box's
    independently-radiused vertical edges was out of scope here -- use
    pybosl2.shapes3d.prismoid() for that, or pybosl2._sdf.shapes3d.cuboid() for the non-tapered case). The SDF
    itself is built by linearly interpolating the local half-size/shift at each height `z`
    (clamped to the `[bottom, top]` range via min()/max(), so no true per-point conditional is
    needed) and taking the 2-D box distance in that local cross-section, intersected with the
    top/bottom slab -- exact for a non-tapered box (`size1 == size2`, `shift == [0, 0]`), an
    approximation (same character as cuboid()'s documented corner caveats) for a genuine taper.

    Args:
        size1:  [width, length] of the bottom end
        size2:  [width, length] of the top end
        height/length:    height of the prism
        shift:  [X,Y] shift of the top center relative to the bottom center
        anchor: anchor point (default BOTTOM)
        res:    libfive meshing resolution passed to frep() (default 10)
    """
    if shift is None:
        shift = [0, 0]
    height = height if height is not None else (length if length is not None else 1)
    bx1, by1 = size1[0] / 2, size1[1] / 2
    bx2, by2 = size2[0] / 2, size2[1] / 2
    hb = height / 2

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        t = lv.min(lv.max((z + hb) / height, 0), 1)
        bx = bx1 + (bx2 - bx1) * t
        by = by1 + (by2 - by1) * t
        cx = shift[0] * t
        cy = shift[1] * t
        qx = lv.abs(x - cx) - bx
        qy = lv.abs(y - cy) - by
        d2d = lv.min(lv.max(qx, qy), 0) + _lv_hypot(lv.max(qx, 0), lv.max(qy, 0))
        slab = lv.abs(z) - hb
        return lv.max(d2d, slab)

    maxx = max(bx1, bx2, bx1 + abs(shift[0]), bx2 + abs(shift[0]))
    maxy = max(by1, by2, by1 + abs(shift[1]), by2 + abs(shift[1]))
    shape = PyShape(sdf_fn, [-maxx, -maxy, -hb], [maxx, maxy, hb], res)
    offset = _anchor_offset_box3([maxx * 2, maxy * 2, height], [int(a) for a in anchor])
    if any(offset):
        shape = shape.translate(offset)
    return shape


def rect_tube(
    height: float | None = None,
    size: float | list[float] | None = None,
    isize: float | list[float] | None = None,
    wall: float | None = None,
    rounding: float = 0,
    inner_rounding: float | None = None,
    length: float | None = None,
    anchor: "Sequence[float]" = BOTTOM,
    res: int = 10,
) -> PyShape:
    """A rectangular tube (a rectangle with a rectangular hole through it), as a libfive SDF
    (outer rounded-rect-extrusion minus inner rounded-rect-extrusion, reusing
    pybosl2.shapes3d.cuboid()'s per-edge machinery for each). Only the 4 vertical edges are
    ever rounded (`edges="Z"`, matching the "rounded rectangular tube" look BOSL2's own
    rect_tube() produces) -- there's no per-edge selection here, just one outer radius and
    one inner radius (default: same as the outer).

    Args:
        height/length:       height/length of the tube (default 1)
        size:      outer [X,Y] size of the tube
        isize:     inner [X,Y] size of the tube
        wall:      wall thickness (used with `size` if `isize` isn't given, or vice versa)
        rounding:  outer vertical-edge rounding radius (default: no rounding)
        inner_rounding: inner vertical-edge rounding radius (default: same as `rounding`)
        anchor:    anchor point (default BOTTOM)
        res:       libfive meshing resolution passed to frep() (default 10)
    """
    length = height if height is not None else (length if length is not None else 1)
    assert size is not None, "rect_tube(): must give size."
    sz: list[float] = [float(v) for v in size] if isinstance(size, (list, tuple)) else [float(size)] * 2
    if isize is not None:
        isz: list[float] = [float(v) for v in isize] if isinstance(isize, (list, tuple)) else [float(isize)] * 2
    else:
        assert wall is not None, "rect_tube(): must give isize or wall."
        isz = [sz[0] - 2 * wall, sz[1] - 2 * wall]
    irounding_v = inner_rounding if inner_rounding is not None else rounding
    edge_set_z = _edges("Z", [])
    o_amounts, o_modes = _edge_matrices(rounding, edge_set_z, "round")
    i_amounts, i_modes = _edge_matrices(irounding_v, edge_set_z, "round")

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        outer = _cuboid_edge_sdf(x, y, z, [sz[0], sz[1], length], o_amounts, o_modes)
        inner = _cuboid_edge_sdf(x, y, z, [isz[0], isz[1], length + 0.02], i_amounts, i_modes)
        return lv.max(outer, -inner)

    half = [sz[0] / 2, sz[1] / 2, length / 2]
    shape = PyShape(sdf_fn, [-half[0], -half[1], -half[2]], half, res)
    offset = _anchor_offset_box3([sz[0], sz[1], length], [int(a) for a in anchor])
    if any(offset):
        shape = shape.translate(offset)
    return shape


# ---------------------------------------------------------------------------
# Section: Miscellaneous
# ---------------------------------------------------------------------------


def interior_fillet(
    length: float = 1.0,
    radius: float | None = None,
    angle: float = 90,
    diameter: float | None = None,
    anchor: "Sequence[float]" = CENTER,
    res: int = 10,
) -> PyShape:
    """A shape to fillet an interior corner between two faces meeting at `angle` degrees, as a
    libfive SDF: the wedge between the two faces, minus a cylindrical arc of radius `radius`
    positioned so it's tangent to both. Extruded along Y for length `length`.

    CAVEAT: simplified relative to pybosl2.shapes3d.interior_fillet() -- no `overlap=` flap (an
    SDF union is already watertight without one) and no independent anchor-face alignment;
    the wedge's first face lies along the local +X/Z=0 half-plane. See
    pybosl2.shapes3d.interior_fillet() for the exact BOSL2-compatible anchor/orientation.
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
    if any(anchor):
        offset = [-a * b for a, b in zip(anchor, [rad * 2, hb, rad * 2], strict=False)]
        shape = shape.translate(offset)
    return shape


def rounding_edge_mask(
    length: float | None = None,
    height: float | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    excess: float = 0.1,
    res: int = 10,
) -> PyShape:
    """A standalone 3-D edge-rounding CUTTER of length `length`, as a libfive SDF, for subtracting
    from another PyShape to round over a sharp 90-degree edge that isn't part of a cuboid()'s
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


def polygon_extrude(pts: ArrayLike, length: float, res: int = 10) -> PyShape:
    """Extrude an arbitrary CONVEX 2-D polygon `pts` (either winding order) along Z by
    `length`, centered -- for a custom edge-profile cutter with no simple closed form (like
    pybosl2.shapes3d.Bosl2Solid.edge_profile_asym()'s `children=` path, but swept here by hand
    with an explicit rotate()/translate() rather than an automatic per-edge sweep).

    As a libfive SDF, this is the max() of each edge's signed half-plane distance -- exact at
    and near any face, but (like every other per-axis/per-plane-composed shape in this module --
    see the module docstring) underestimates the true Euclidean distance near a vertex, away
    from the surface; the sign is still correct everywhere a convex polygon's supporting
    half-planes actually bound it.

    CAVEAT: `pts` must describe a CONVEX polygon. A concave vertex's half-plane doesn't bound
    the shape there, so both the sign and the surface would come out wrong.
    """
    pts = as_points(pts)
    area2 = sum(
        pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))
    )
    ordered = pts if area2 > 0 else list(reversed(pts))
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
    paths: ArrayLike,
    height: float,
    rounding_top: float = 0,
    rounding_bottom: float = 0,
    res: int = 10,
) -> PyShape:
    """Extrude an arbitrary SIMPLE polygon (convex or concave -- exact 2-D SDF via
    _polygon_sdf_xy(), unlike polygon_extrude()'s convex-only half-planes) from z=0 up to z=height,
    with optional circular treatments on each end rim -- the same job as real BOSL2's
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
        paths:           one [[x, y], ...] polygon, or a list of disjoint such polygons
        height:               extrusion height (z from 0 to height)
        rounding_top:    top-rim treatment: >0 roundover radius, <0 flare, 0 square (default 0)
        rounding_bottom: bottom-rim treatment, same convention (default 0)
        res:             libfive meshing resolution passed to frep() (default 10)
    """
    if not isinstance(paths, (list, np.ndarray)):
        raise TypeError(f"polygon_prism(): paths must be a list of points or numpy array, got {type(paths).__name__}")
    assert len(paths) >= 1, "polygon_prism(): paths must not be empty"
    path_list = as_path_list(paths)
    for p in path_list:
        assert len(p) >= 3, f"polygon_prism(): every path needs >= 3 points, got {len(p)}"
    assert height > 0, f"polygon_prism(): height must be > 0, height={height}"
    assert abs(rounding_top) < height and abs(rounding_bottom) < height, (
        "polygon_prism(): rim treatments must be smaller than height"
    )

    def sdf_fn(x: LVTree, y: LVTree, z: LVTree) -> LVTree:
        d2d = None
        for p in path_list:
            d = _polygon_sdf_xy(x, y, p)
            d2d = d if d2d is None else lv.min(d2d, d)
        assert d2d is not None, "polygon_prism(): no paths"

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
        if rounding_bottom > 0:
            rb = rounding_bottom
            q1, q2 = d2d + rb, -z + rb
            out = lv.max(
                out,
                lv.min(lv.max(q1, q2), 0) + _lv_hypot(lv.max(q1, 0), lv.max(q2, 0)) - rb,
            )

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
    res: int = 10,
) -> PyShape:
    """A teardrop shape (useful for 3-D-printable horizontal holes), as a libfive SDF: the
    union of a circle and a "roof" of two planes meeting at the apex, tangent to the circle,
    extruded along Y for thickness `h`.

    CAVEAT: simplified relative to pybosl2.shapes3d.teardrop() -- no `chamfer=`/`circum=`/
    `realign=` support. `cap_height` (truncation height) is supported since it's a plain top-slab
    intersection.

    Examples:
        .. pythonscad-example::

            import pybosl2._sdf.shapes3d as sdf_s3d
            shape = sdf_s3d.teardrop(height=10, radius=8)
            shape.show()
    """
    length = height if height is not None else 1
    rad1 = _radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
    rad2 = _radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter, dflt=1)
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
    if any(anchor):
        offset = [
            -anchor[0] * maxr,
            -anchor[1] * hb,
            -anchor[2] * maxheight if anchor[2] > 0 else -anchor[2] * maxr,
        ]
        shape = shape.translate(offset)
    return shape


def onion(
    radius: float | None = None,
    angle: float = 45,
    cap_height: float | None = None,
    diameter: float | None = None,
    anchor: "Sequence[float]" = CENTER,
    res: int = 10,
) -> PyShape:
    """An onion-dome shape (a sphere with a conical cap), as a libfive SDF: the union of a
    sphere and a cone tangent to it, revolved around Z.

    CAVEAT: simplified relative to pybosl2.shapes3d.onion() -- no `circum=`/`realign=` support.
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
    if any(anchor):
        offset = [
            -anchor[0] * rad,
            -anchor[1] * rad,
            -anchor[2] * maxheight if anchor[2] > 0 else -anchor[2] * rad,
        ]
        shape = shape.translate(offset)
    return shape


def heightfield(
    data: Callable[[Any, Any], Any],
    size: list[float] | None = None,
    bottom: float = -20,
    maxz: float = 99,
    res: int = 10,
) -> PyShape:
    """A 3-D surface from a height function, as a libfive SDF.

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
        res:    libfive meshing resolution passed to frep() (default 10)
    """
    if size is None:
        size = [100, 100]
    assert callable(data), (
        "pybosl2._sdf.shapes3d.heightfield() only supports callable data -- see the CAVEAT in its docstring."
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
    realign: bool = False,
    anchor: "Sequence[float]" = CENTER,
    res: int = 10,
) -> PyShape:
    """A regular num_sides-gon prism (equilateral, equiangular cross-section), as a libfive SDF
    built on polygon_prism(). Mirrors pybosl2.shapes3d.regular_prism().

    Size is controlled by one of the radius/diameter/side parameters, in BOSL2 priority order:
    inner_radius/inner_diameter > outer_radius/outer_diameter > r/d > side.  The ``or``/``outer_radius``
    keyword collision with the Python keyword ``or`` is resolved as ``outer_radius`` here.

    Args:
        num_sides:       number of sides (default 6)
        h/l:     prism height (default 1)
        r/d:     radius/diameter to the vertices
        outer_radius/outer_diameter: outer radius/diameter (BOSL2 ``or``)
        inner_radius/inner_diameter:   inner radius/diameter (apothem to face centres)
        side:    length of each side
        realign: rotate so a face centre (not vertex) faces +X (default False)
        anchor:  anchor point (default CENTER)
        res:     meshing resolution (default 10)
    """
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
    if rad is None:
        raise ValueError(
            "regular_prism(): need one of r, d, outer_radius, outer_diameter, inner_radius, inner_diameter, or side."
        )

    pts = [[_m.cos(2 * _m.pi * i / num_sides) * rad, _m.sin(2 * _m.pi * i / num_sides) * rad] for i in range(num_sides)]
    if realign:
        pts = [
            [
                p[0] * _m.cos(-_m.pi / num_sides) - p[1] * _m.sin(-_m.pi / num_sides),
                p[0] * _m.sin(-_m.pi / num_sides) + p[1] * _m.cos(-_m.pi / num_sides),
            ]
            for p in pts
        ]

    prism = polygon_prism(pts, length, res=res)
    offset = _anchor_offset_hull3(
        [[p[0], p[1], -length / 2] for p in pts] + [[p[0], p[1], length / 2] for p in pts],
        anchor,
    )
    if any(offset):
        prism = prism.translate(offset)
    return prism


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
    assert np.all(tl > 1e-12), "path has a repeated point (zero-length tangent)"
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


def path_sweep(profile: ArrayLike, path: ArrayLike, res: int = 12, twist: float = 0.0) -> PyShape:
    """Sweep a 2-D `profile` (list of ``[u, v]`` cross-section points) along a 3-D `path`
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
    """
    prof = as_points(profile)
    assert len(prof) >= 3, "sweep profile needs at least 3 points"
    pts3 = [list(p) + [0.0] * (3 - len(p)) for p in np.asarray(path, dtype=float).tolist()]
    assert len(pts3) >= 2, "sweep path needs at least 2 points"
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
    profile: ArrayLike, control_points: ArrayLike, splinesteps: int = 24, res: int = 12, twist: float = 0.0
) -> PyShape:
    """Sweep a 2-D `profile` (convex or concave) along a 3-D Bezier curve, as a libfive SDF.

    `control_points` are the Bezier control points (any degree). The curve is generated with
    pybosl2's canonical :class:`pybosl2.beziers.Bezier` (``splinesteps`` segments) and swept by
    :func:`path_sweep`, so bezier generation and the signed-distance sweep compose directly::

        from pybosl2._sdf.shapes3d import bezier_sweep
        circle = [[2 * math.cos(t), 2 * math.sin(t)] for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
        tube = bezier_sweep(circle, [[0, 0, 0], [0, 0, 20], [25, 12, 15], [30, 4, 6]])
    """
    from pybosl2.beziers import Bezier

    path = Bezier(control_points).curve(splinesteps=splinesteps)  # type: ignore[arg-type]
    return path_sweep(profile, path, res=res, twist=twist)


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
    from pybosl2.exceptions import UnsupportedByBackendError

    pts = [list(map(float, p)) for p in path]
    assert len(pts) >= 2, "stroke_3d: need at least 2 points."
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
            raise UnsupportedByBackendError(
                f"stroke(endcap={cap.cap_type!r})",
                "sdf",
                hint="fancy endcaps need rotate_extrude; use the csg backend for those.",
            )

    assert shapes, "stroke_3d: path has no drawable segments."
    return PyShape.union(*shapes)

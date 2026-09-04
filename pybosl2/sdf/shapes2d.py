# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/sdf/shapes2d.py
#    The 2-D layer: PyShape2D (the lazy symbolic 2-D SDF, extruded to a specific height to
#    become a PyShape) and its constructors -- circle2d/rect2d/polygon2d/stroke2d/
#    hull2d_discs/supershape2d.
#

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Callable, NoReturn, cast

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence


from pybosl2._backend import check_operand_backend as _check_operand_backend
from pybosl2._edges_lang import Anchor
from pybosl2._helpers import pick_radius as _pick_radius
from pybosl2.bounds import Bounds2D
from pybosl2.color import Colorable
from pybosl2.distributors import Distributable
from pybosl2.enums import EdgeMode
from pybosl2.exceptions import Bosl2ValueError, UnsupportedByBackendError
from pybosl2.path2d import Path2D
from pybosl2.paths import require_path
from pybosl2.sdf._constants import CENTER
from pybosl2.sdf._libfive import lv
from pybosl2.sdf.paths import (
    _PENALTY,
    _collinear,
    _halfplane_max_sdf,
    _hull2d_points,
    _lv_hypot,
    _polygon_dist2_xy,
    _polygon_sdf_xy,
    _radius,
    _rect2d,
    as_path_list,
    as_points,
)
from pybosl2.sdf.paths import (
    supershape_path as _supershape_path,
)
from pybosl2.sdf.shapes3d import PyShape

# ---------------------------------------------------------------------------
# Section: 2-D shapes (PyShape2D) -- symbolic 2-D SDFs that extrude into PyShapes
# ---------------------------------------------------------------------------


class SdfShape2D(Colorable, Distributable):
    """A lazy 2-D shape: a symbolic signed-distance function of (x, y) plus bounds -- the flat.

    sibling of PyShape, for building lid-pattern shapes (shapes.py/tesselations.py) entirely in
    SDF-land. Compose with translate/rotate/scale/mirror, the boolean operators, and the two
    ops SDFs do BETTER than polygon math: offset() (a single subtraction -- exact, rounded,
    no self-intersection cleanup) and outline() (|d| - w/2, the centered outline strip).

    A 2-D SDF can't be meshed directly (frep() is 3-D only), so a PyShape2D turns into real
    geometry by extruding: extrude(height) / linear_extrude(height=...) return a PyShape (with
    the same optional rim roundover/flare treatments as polygon_prism()); anything else a
    PyShape2D doesn't define falls through __getattr__ to a thin (0.01) extrusion's mesh --
    which is almost never what you want, so extrude explicitly.
    """

    backend = "sdf"

    #: This shape is two-dimensional; see CsgSolid.dimensions (SPEC E-7).
    dimensions = 2

    def __init__(self, sdf_fn: Callable, mn: Sequence[float], mx: Sequence[float], res: int = 10):  # type: ignore[type-arg]
        self._sdf_fn = sdf_fn
        self.mn = [float(mn[0]), float(mn[1])]
        self.mx = [float(mx[0]), float(mx[1])]
        self.res = res
        #: Colour and preview modifier ride along with the field as metadata and are applied when
        #: the shape becomes geometry, which for a 2-D SDF means when it is extruded. Same scheme
        #: as SdfSolid: recording them costs nothing and keeps the chain in SDF-land (SPEC C-19).
        self._colour: tuple[Any, float | None] | None = None
        self._modifier: str | None = None
        #: The nominal anchor box (SPEC S-2a), if one was attached.
        self._size: list[float] | None = None

    @property
    def size(self) -> "list[float] | None":
        """Return the nominal anchor box, or None if this shape never had one (SPEC S-2a)."""
        return None if self._size is None else list(self._size)

    def _wrap(self, sdf_fn: Callable, mn: Sequence[float], mx: Sequence[float]) -> PyShape2D:  # type: ignore[type-arg]
        out = PyShape2D(sdf_fn, mn, mx, self.res)
        out._colour = self._colour
        out._modifier = self._modifier
        out._size = None if self._size is None else list(self._size)
        return out

    # ------------------------------------------------------------------
    # Colour, as metadata on the field (SPEC C-19, S-37)
    # ------------------------------------------------------------------

    def _recoloured(self, colour: "tuple[Any, float | None] | None", modifier: str | None) -> PyShape2D:
        out = self._wrap(self._sdf_fn, self.mn, self.mx)
        out._colour = colour
        out._modifier = modifier
        return out

    def _color_native(self, c: Any = None, alpha: float | None = None) -> PyShape2D:
        """Record the colour; it is applied when the shape is extruded into geometry."""
        return self._recoloured((c, alpha), self._modifier)

    def _highlight_native(self) -> PyShape2D:
        """Record the highlight (``#``) modifier."""
        return self._recoloured(self._colour, "highlight")

    def _ghost_native(self) -> PyShape2D:
        """Record the ghost (``%``) modifier."""
        return self._recoloured(self._colour, "ghost")

    def _apply_appearance(self, built: Any) -> Any:
        """Apply any recorded colour/modifier to *built* and return it."""
        if self._colour is not None:
            colour, alpha = self._colour
            built = built.color(colour, alpha) if alpha is not None else built.color(colour)
        if self._modifier == "highlight":
            built = built.highlight()
        elif self._modifier == "ghost":
            built = built.ghost()
        return built

    # ------------------------------------------------------------------
    # Transforms the shared contract expects of any shape (SPEC C-15, C-22)
    # ------------------------------------------------------------------

    def multmatrix(self, matrix: "Sequence[Sequence[float]] | np.ndarray") -> PyShape2D:
        """Apply an affine matrix to the field, exact and free.

        Accepts the 4x4 the rest of the library speaks -- the distributors build 4x4 matrices for
        both dimensions -- and uses its 2-D part. A matrix with a Z component that would move the
        shape out of its plane is refused rather than silently flattened.

        Args:
            matrix: a 3x3 or 4x4 affine matrix.

        Returns:
            The transformed shape.

        Raises:
            Bosl2ValueError: If the matrix is not 3x3 or 4x4, is singular, or would move a 2-D
                shape out of the Z=0 plane.

        Examples:
            .. pythonscad-example::

                from pybosl2 import square, use_backend

                with use_backend("sdf"):
                    shape = square([20, 10]).multmatrix(
                        [[1, 0, 0, 5], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
                    )
                shape.linear_extrude(height=4).show()

        """
        m = np.asarray(matrix, dtype=float)
        if m.shape == (4, 4):
            if not (np.allclose(m[2, :3], [0.0, 0.0, 1.0]) and abs(float(m[2, 3])) < 1e-12):
                raise Bosl2ValueError(
                    "multmatrix(): this matrix moves the shape out of the Z=0 plane, which a 2-D "
                    "shape cannot represent. Extrude it first with `.linear_extrude(height=...)`."
                )
            m = np.array([[m[0, 0], m[0, 1], m[0, 3]], [m[1, 0], m[1, 1], m[1, 3]], [0.0, 0.0, 1.0]])
        elif m.shape != (3, 3):
            raise Bosl2ValueError(f"multmatrix() requires a 3x3 or 4x4 matrix, got {m.shape}.")
        try:
            mt = np.linalg.inv(m)
        except np.linalg.LinAlgError:
            raise Bosl2ValueError("multmatrix() requires an invertible matrix.") from None

        fn = self._sdf_fn

        def new_fn(x, y):  # type: ignore[no-untyped-def]
            return fn(mt[0, 0] * x + mt[0, 1] * y + mt[0, 2], mt[1, 0] * x + mt[1, 1] * y + mt[1, 2])

        corners = [
            [self.mn[0], self.mn[1]],
            [self.mx[0], self.mn[1]],
            [self.mn[0], self.mx[1]],
            [self.mx[0], self.mx[1]],
        ]
        moved = [
            [m[0, 0] * c[0] + m[0, 1] * c[1] + m[0, 2], m[1, 0] * c[0] + m[1, 1] * c[1] + m[1, 2]] for c in corners
        ]
        return self._wrap(
            new_fn,
            [min(c[i] for c in moved) for i in range(2)],
            [max(c[i] for c in moved) for i in range(2)],
        )

    # ------------------------------------------------------------------
    # Anchoring (SPEC C-10, S-2a) -- box arithmetic, which an SDF shape knows exactly
    # ------------------------------------------------------------------

    def _resolve_bounds(self, bbox: "Sequence[Sequence[float]] | None" = None) -> tuple[list[float], list[float]]:
        """Return ``(centre, size)`` for anchoring, from *bbox* if given or this shape's own box."""
        if bbox is None:
            return self._center_size()
        arr = np.asarray(bbox, dtype=float)
        if arr.shape != (2, 2):
            raise Bosl2ValueError("bbox must be [[min_x, min_y], [max_x, max_y]].")
        lo, hi = arr[0], arr[1]
        if not bool(np.all(hi >= lo - 1e-12)):
            raise Bosl2ValueError("bbox must have max >= min on both axes.")
        return [float((lo[i] + hi[i]) / 2) for i in range(2)], [float(hi[i] - lo[i]) for i in range(2)]

    def anchor_point(
        self, anchor: "Anchor | Sequence[float]", bbox: "Sequence[Sequence[float]] | None" = None
    ) -> list[float]:
        """Return the 2-D point for the given anchor.

        The same arithmetic the CSG 2-D shape does, on the same anchor vocabulary (SPEC C-10) --
        it only ever needed a bounding box, and an SDF shape carries an exact one.

        Args:
            anchor: an :class:`~pybosl2._edges_lang.Anchor` or a 2-vector.
            bbox: override box, ``[[min_x, min_y], [max_x, max_y]]``.

        Returns:
            The ``[x, y]`` point.
        """
        centre, size = self._resolve_bounds(bbox)
        vec = list(anchor.vector_2d) if isinstance(anchor, Anchor) else list(anchor)
        return [centre[i] + vec[i] * size[i] / 2 for i in range(2)]

    def reanchor(
        self, anchor: "Anchor | Sequence[float]", bbox: "Sequence[Sequence[float]] | None" = None
    ) -> PyShape2D:
        """Move this shape so that *anchor* lands on the origin.

        Args:
            anchor: an :class:`~pybosl2._edges_lang.Anchor` or a 2-vector.
            bbox: override box, ``[[min_x, min_y], [max_x, max_y]]``.

        Returns:
            The moved shape.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Anchor, square, use_backend

                with use_backend("sdf"):
                    shape = square([20, 10]).reanchor(Anchor.LEFT)
                shape.linear_extrude(height=4).show()

        """
        point = self.anchor_point(anchor, bbox=bbox)
        return self.translate([-point[0], -point[1]])

    def with_nominal_size(self, size: "Sequence[float]", anchor: Any = None) -> PyShape2D:
        """Return this shape carrying *size* as its nominal anchor box (SPEC S-2a).

        Args:
            size: the nominal box, ``[width, length]``.
            anchor: accepted for signature parity; the 2-D shape tracks only the box.

        Returns:
            A copy carrying the nominal size.
        """
        _ = anchor
        out = self._wrap(self._sdf_fn, self.mn, self.mx)
        out._size = [float(v) for v in size]
        return out

    # ------------------------------------------------------------------
    # The CSG-only surface, refused explicitly (SPEC C-13, PAR-3)
    # ------------------------------------------------------------------

    def _refuse_csg_only(self, feature: str) -> "NoReturn":
        """Raise the standard refusal for a CSG-only feature (SPEC B-4, E-2)."""
        raise UnsupportedByBackendError(
            feature,
            "sdf",
            hint=(
                "attachment and tagging need a shape's edge structure, which a distance field "
                "does not retain. Build it on the default (csg) backend, or extrude this field "
                "and bring it across with `.to_csg()`."
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
        self._refuse_csg_only("attach")

    def position(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: attachment is a CSG-backend feature (SPEC C-13)."""
        self._refuse_csg_only("position")

    def align(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: attachment is a CSG-backend feature (SPEC C-13)."""
        self._refuse_csg_only("align")

    def tag(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: tagging serves attachment, which is CSG-only (SPEC C-13)."""
        self._refuse_csg_only("tag")

    def tag_this(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: tagging serves attachment, which is CSG-only (SPEC C-13)."""
        self._refuse_csg_only("tag_this")

    def diff(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: tag-driven boolean resolution is CSG-only (SPEC C-13). Use `-` instead."""
        self._refuse_csg_only("diff")

    def intersect(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: tag-driven boolean resolution is CSG-only (SPEC C-13). Use `&` instead."""
        self._refuse_csg_only("intersect")

    def realize(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: there are no attachments to resolve; attachment is CSG-only (SPEC C-13)."""
        self._refuse_csg_only("realize")

    def minkowski(self, *_args: Any, **_kwargs: Any) -> "NoReturn":
        """Refuse: a Minkowski sum of two fields has no closed form (SPEC B-4).

        `offset()` is the SDF answer for the common case -- growing a shape by a radius is a
        single subtraction on the field, exact and free.
        """
        raise UnsupportedByBackendError(
            "minkowski",
            "sdf",
            hint="a Minkowski sum has no closed-form distance field; use `.offset(r)` to grow a "
            "shape by a radius, which an SDF does exactly.",
        )

    def _distribute(self, mats: list[Any]) -> list:  # type: ignore[type-arg]
        """Return one transformed copy per matrix -- the hook `Distributable` builds on."""
        return [self.multmatrix(m) for m in mats]

    def left(self, x: float) -> PyShape2D:
        """Move this shape *x* in -X.

        Args:
            x: The X coordinate.
        """
        return self.translate([-x, 0.0])

    def right(self, x: float) -> PyShape2D:
        """Move this shape *x* in +X.

        Args:
            x: The X coordinate.
        """
        return self.translate([x, 0.0])

    def forward(self, y: float) -> PyShape2D:
        """Move this shape *y* in -Y.

        Args:
            y: The Y coordinate.
        """
        return self.translate([0.0, -y])

    def back(self, y: float) -> PyShape2D:
        """Move this shape *y* in +Y.

        Args:
            y: The Y coordinate.
        """
        return self.translate([0.0, y])

    def show(self) -> PyShape2D:
        """Refuse to render a 2-D field, naming the extrusion that would make it renderable.

        Returns:
            Never returns.

        Raises:
            UnsupportedByBackendError: Always -- a 2-D distance field has no rendering of its own.
        """
        from pybosl2.exceptions import UnsupportedByBackendError

        raise UnsupportedByBackendError(
            "show",
            "sdf",
            hint="a 2-D distance field has no rendering of its own -- extrude it first, e.g. "
            "shape.linear_extrude(height=5).show().",
        )

    # ---- transforms ----

    def translate(self, v: Sequence[float]) -> PyShape2D:
        tx, ty = float(v[0]), float(v[1])
        fn = self._sdf_fn
        new_fn = lambda x, y: fn(x - tx, y - ty)  # noqa: E731
        return self._wrap(
            new_fn,
            [self.mn[0] + tx, self.mn[1] + ty],
            [self.mx[0] + tx, self.mx[1] + ty],
        )

    def rotate(self, a: float | list[float]) -> PyShape2D:
        """Rotate by `a` degrees around the origin -- a plain scalar, or the native.

        [0, 0, a] vector spelling (only z-rotation makes sense for a 2-D shape; the x/y
        components must be 0), so migrated call sites keep working unchanged.

        Args:
            a: The shape or value to combine.

        """
        if isinstance(a, (list, tuple)):
            if not (len(a) == 3):
                raise Bosl2ValueError(f"2-D rotate only supports [0, 0, angle], got {a}")
            if a[0]:
                raise Bosl2ValueError(f"2-D rotate only supports [0, 0, angle], got {a}")
            if a[1]:
                raise Bosl2ValueError(f"2-D rotate only supports [0, 0, angle], got {a}")
            a = a[2]
        angle = math.radians(a)
        c, s = math.cos(angle), math.sin(angle)
        fn = self._sdf_fn
        new_fn = lambda x, y: fn(c * x + s * y, -s * x + c * y)  # noqa: E731
        corners = [
            [self.mn[0], self.mn[1]],
            [self.mx[0], self.mn[1]],
            [self.mn[0], self.mx[1]],
            [self.mx[0], self.mx[1]],
        ]
        rot = [[c * p[0] - s * p[1], s * p[0] + c * p[1]] for p in corners]
        return self._wrap(
            new_fn,
            [min(p[0] for p in rot), min(p[1] for p in rot)],
            [max(p[0] for p in rot), max(p[1] for p in rot)],
        )

    def scale(self, v: float | Sequence[float]) -> PyShape2D:
        s = [float(v), float(v)] if isinstance(v, (int, float)) else [float(a) for a in v]
        if not (all((a > 0 for a in s))):
            raise Bosl2ValueError(f"scale() factors must be positive, got {s}")
        fn = self._sdf_fn
        smin = min(s)
        new_fn = lambda x, y: smin * fn(x / s[0], y / s[1])  # noqa: E731
        return self._wrap(
            new_fn,
            [self.mn[0] * s[0], self.mn[1] * s[1]],
            [self.mx[0] * s[0], self.mx[1] * s[1]],
        )

    def mirror(self, v: list[float]) -> PyShape2D:
        """Mirror across the line through the origin whose NORMAL is `v` (native convention).

        Args:
            v: The vector.
        """
        nx, ny = float(v[0]), float(v[1])
        nlen = math.hypot(nx, ny)
        nx, ny = nx / nlen, ny / nlen
        fn = self._sdf_fn
        # reflect: p - 2*(p.n)n
        new_fn = lambda x, y: fn(x - 2 * (x * nx + y * ny) * nx, y - 2 * (x * nx + y * ny) * ny)  # noqa: E731
        corners = [
            [self.mn[0], self.mn[1]],
            [self.mx[0], self.mn[1]],
            [self.mn[0], self.mx[1]],
            [self.mx[0], self.mx[1]],
        ]
        ref = [
            [
                p[0] - 2 * (p[0] * nx + p[1] * ny) * nx,
                p[1] - 2 * (p[0] * nx + p[1] * ny) * ny,
            ]
            for p in corners
        ]
        return self._wrap(
            new_fn,
            [min(p[0] for p in ref), min(p[1] for p in ref)],
            [max(p[0] for p in ref), max(p[1] for p in ref)],
        )

    # ---- booleans ----

    def __or__(self, other: PyShape2D) -> PyShape2D:
        _check_operand_backend("sdf", other, 2)
        fa, fb = self._sdf_fn, other._sdf_fn

        def new_fn(x, y):  # type: ignore[no-untyped-def]
            return lv.min(fa(x, y), fb(x, y))

        return self._wrap(
            new_fn,
            [min(self.mn[i], other.mn[i]) for i in range(2)],
            [max(self.mx[i], other.mx[i]) for i in range(2)],
        )

    def __and__(self, other: PyShape2D) -> PyShape2D:
        _check_operand_backend("sdf", other, 2)
        fa, fb = self._sdf_fn, other._sdf_fn

        def new_fn(x, y):  # type: ignore[no-untyped-def]
            return lv.max(fa(x, y), fb(x, y))

        return self._wrap(
            new_fn,
            [max(self.mn[i], other.mn[i]) for i in range(2)],
            [min(self.mx[i], other.mx[i]) for i in range(2)],
        )

    def __sub__(self, other: PyShape2D) -> PyShape2D:
        _check_operand_backend("sdf", other, 2)
        fa, fb = self._sdf_fn, other._sdf_fn

        def new_fn(x, y):  # type: ignore[no-untyped-def]
            return lv.max(fa(x, y), -fb(x, y))

        return self._wrap(new_fn, list(self.mn), list(self.mx))

    def __ror__(self, other: PyShape2D) -> PyShape2D:
        _check_operand_backend("sdf", other, 2)
        fa, fb = self._sdf_fn, other._sdf_fn

        def new_fn(x, y):  # type: ignore[no-untyped-def]
            return lv.min(fb(x, y), fa(x, y))

        return self._wrap(
            new_fn,
            [min(other.mn[i], self.mn[i]) for i in range(2)],
            [max(other.mx[i], self.mx[i]) for i in range(2)],
        )

    def __rand__(self, other: PyShape2D) -> PyShape2D:
        _check_operand_backend("sdf", other, 2)
        fa, fb = self._sdf_fn, other._sdf_fn

        def new_fn(x, y):  # type: ignore[no-untyped-def]
            return lv.max(fb(x, y), fa(x, y))

        return self._wrap(
            new_fn,
            [max(other.mn[i], self.mn[i]) for i in range(2)],
            [min(other.mx[i], self.mx[i]) for i in range(2)],
        )

    def __rsub__(self, other: PyShape2D) -> PyShape2D:
        _check_operand_backend("sdf", other, 2)
        fa, fb = self._sdf_fn, other._sdf_fn

        def new_fn(x, y):  # type: ignore[no-untyped-def]
            return lv.max(fb(x, y), -fa(x, y))

        return self._wrap(new_fn, list(other.mn), list(other.mx))

    def __add__(self, other: Any) -> PyShape2D:
        try:
            len(other)
            return self.translate(other)
        except (TypeError, ValueError):
            return NotImplemented

    def __radd__(self, other: Any) -> PyShape2D:
        try:
            len(other)
            return self.translate(other)
        except (TypeError, ValueError):
            return NotImplemented

    def __mul__(self, other: Any) -> PyShape2D:
        return self.scale(other)

    def __rmul__(self, other: Any) -> PyShape2D:
        return self.scale(other)

    @staticmethod
    def union(shapes: list[PyShape2D]) -> PyShape2D:
        """Union of many shapes as a balanced pairwise tree. A linear `a | b | c | ...` chain.

        nests one lambda per piece, so composing hundreds of pieces (a dense tiling, say)
        overflows Python's recursion limit when the SDF is finally evaluated -- the tree keeps
        the evaluation depth at log2(n) instead.

        Args:
            shapes: The shapes to combine.

        """
        shapes = list(shapes)
        if not (shapes):
            raise Bosl2ValueError("union() needs at least one shape")
        while len(shapes) > 1:
            shapes = [shapes[i] | shapes[i + 1] if i + 1 < len(shapes) else shapes[i] for i in range(0, len(shapes), 2)]
        return shapes[0]

    union2d = union

    # ---- the ops SDFs are uniquely good at ----

    def offset(self, delta: float = 0, radius: float | None = None) -> PyShape2D:
        """Grow (positive) or shrink (negative) by a distance -- one subtraction on the SDF, no.

        polygon offsetting/self-intersection cleanup. Growth is round-style (matching native
        offset(radius=...)); accepts either the delta= or radius= spelling since they coincide here.

        Args:
            delta: Offset distance; negative shrinks the outline.
            radius: The radius.

        """
        amount = float(radius if radius is not None else delta)
        fn = self._sdf_fn
        new_fn = lambda x, y: fn(x, y) - amount  # noqa: E731
        g = max(amount, 0.0)
        return self._wrap(new_fn, [self.mn[0] - g, self.mn[1] - g], [self.mx[0] + g, self.mx[1] + g])

    def outline(self, width: float) -> PyShape2D:
        """Return the centered outline strip of this shape's boundary: |d| - width/2.

        Args:
            width: Width of the drawn line.
        """
        fn = self._sdf_fn
        new_fn = lambda x, y: lv.abs(fn(x, y)) - width / 2  # noqa: E731
        g = width / 2
        return self._wrap(new_fn, [self.mn[0] - g, self.mn[1] - g], [self.mx[0] + g, self.mx[1] + g])

    def fill(self) -> "NoReturn":
        """Refuse: filling an outline is a CSG-backend notion (SPEC PAR-3, B-5).

        This used to work, by extruding the field to a thin solid, meshing it, crossing to CSG,
        projecting to drop the holes, and rebuilding an SDF polygon from the outline. That is the
        silent lossy backend conversion B-5 forbids, and it made `fill` the third case PLAN B-P4
        names: a feature listed in ``CSG_ONLY_FEATURES`` that works anyway, so the refusal never
        fires. `projection` behaved the same way until T4.

        The round trip is still available, said out loud: ``shape.to_csg()`` crosses the boundary
        explicitly, and `fill` there does the same work without pretending to be a field operation.

        Raises:
            UnsupportedByBackendError: always, naming the conversion that does the job.

        """
        raise UnsupportedByBackendError(
            "fill",
            "sdf",
            hint=(
                "filling an outline needs the outline, and a distance field does not retain one. "
                "Cross the boundary explicitly with `.to_csg()` and fill there, which is the same "
                "work this used to do silently."
            ),
        )

    def xflip(self, x: float = 0.0) -> PyShape2D:
        """Mirror this shape across the vertical line x = *x*, keeping the copy left of it.

        When *x* is 0 (the default) the result is the x≤0 half mirrored to the other side:
        ``shape & mirror(VEC_X)`` where ``VEC_X = [1,0,0]``.

        Args:
            x: X-coordinate of the mirror line.

        Returns:
            A new :class:`PyShape2D` with the flipped half.
        """
        translated = self.translate([-float(x), 0.0])
        mirrored = translated.mirror([1.0, 0.0])
        return translated & mirrored

    def yflip(self, y: float = 0.0) -> PyShape2D:
        """Mirror this shape across the horizontal line y = *y*, keeping the copy below it.

        When *y* is 0 (the default) the result is the y≤0 half mirrored to the other side:
        ``shape & mirror(VEC_Y)`` where ``VEC_Y = [0,1,0]``.

        Args:
            y: Y-coordinate of the mirror line.

        Returns:
            A new :class:`PyShape2D` with the flipped half.
        """
        translated = self.translate([0.0, -float(y)])
        mirrored = translated.mirror([0.0, 1.0])
        return translated & mirrored

    def hull(self, *others: PyShape2D) -> PyShape2D:
        """Return the convex hull of this shape and *others* in 2-D.

        Uses the SDF-based hull via the 3-D hull projection: extrudes each shape
        to a thin solid, hulls the 3-D solids, then projects back to 2-D.

        Args:
            *others: Additional shapes to hull with.

        Returns:
            A new :class:`PyShape2D` representing the 2-D convex hull.
        """
        if not others:
            return self
        extruded = [s.extrude(0.01, res=s.res) for s in [self] + list(others)]
        hull3d = extruded[0].hull(*extruded[1:])
        csg = hull3d.to_csg()
        projection = csg.projection(cut=True)
        shapes = [projection] if not hasattr(projection, "__iter__") else list(projection)
        if not shapes:
            return self
        pts: list[list[float]] = []
        if hasattr(shapes[0], "paths"):
            for p in shapes[0].paths:
                pts.extend([[float(c[0]), float(c[1])] for c in p])
        if not pts:
            return self
        return polygon2d(Path2D(pts), res=self.res)

    def bounds(self) -> Bounds2D:
        """Return this shape's axis-aligned bounding box (SPEC S-2b).

        Exact and cheap: every SDF constructor records its tight ``mn``/``mx``, so nothing is
        sampled to answer this.

        Returns:
            The :class:`~pybosl2.bounds.Bounds2D` box, carrying ``min``/``max``, ``center``,
            ``size``, ``width`` and ``length``.

        Examples:
            .. pythonscad-example::

                from pybosl2 import square, use_backend

                with use_backend("sdf"):
                    shape = square([20, 10])
                print(shape.bounds().width)
                shape.linear_extrude(height=4).show()

        """
        return Bounds2D.from_min_max(self.mn, self.mx)

    def _center_size(self) -> tuple[list[float], list[float]]:
        """Return the bounding box as the raw ``(center, size)`` pair the native layer reports."""
        box = self.bounds()
        return list(box.center), list(box.size)

    # ---- to 3-D ----

    def linear_extrude(
        self,
        height: float,
        rounding_top: float = 0,
        rounding_bottom: float = 0,
        center: bool = False,
        convexity: int | None = None,  # noqa: ARG002 - a render hint; the field has no facets
        res: int | None = None,
    ) -> PyShape:
        """Extrude this 2-D shape to *height* along Z -- the `Flat` contract's spelling.

        The same operation as :meth:`extrude`, under the name the shared contract uses (SPEC C-17)
        and the CSG 2-D shape already used. Having only `extrude` here made a caller's code
        backend-specific for no reason and put a naming divergence in the API rather than in the
        one translation table PLAN B-P2 allows.

        Args:
            height: Extrusion height along Z.
            rounding_top: Rim roundover at the top face.
            rounding_bottom: Rim roundover at the bottom face.
            center: Centre the result on z=0 rather than basing it there.
            convexity: Accepted and ignored -- it is a *renderer* hint about how many times a ray
                crosses the surface, which a distance field has no use for. Its sibling
                :meth:`rotate_extrude` already took it that way, and this one did not: passing it
                raised a bare ``TypeError`` from inside the backend rather than being ignored or
                refused, which is how `Path2D.path_extrude2d` failed under `use_backend("sdf")`
                (SPEC B-9's tessellation carve-out, C-21).
            res: Sampling resolution; the ambient default applies when omitted. Omitted, the ambient
                ``use_defaults(res=...)`` value applies.

        Returns:
            The extruded :class:`PyShape`.

        Examples:
            .. pythonscad-example::

                from pybosl2 import square, use_backend

                with use_backend("sdf"):
                    shape = square([20, 10]).linear_extrude(height=6)
                shape.show()

        """
        return self.extrude(
            height,
            rounding_top=rounding_top,
            rounding_bottom=rounding_bottom,
            center=center,
            res=res,
        )

    def extrude(
        self,
        height: float,
        rounding_top: float = 0,
        rounding_bottom: float = 0,
        center: bool = False,
        res: int | None = None,
    ) -> PyShape:
        """Extrude to a specific height along Z (base at z=0, or centered), returning a PyShape.

        The optional rim treatments follow polygon_prism()'s convention (positive roundover,
        negative flare) and reuse the same construction, over this shape's own SDF.

        Args:
            height: Height to extrude to.
            rounding_top: Rounding radius applied to the top edge.
            rounding_bottom: Rounding radius applied to the bottom edge.
            center: Centre the result on z=0 rather than standing it on the plane.
            res: Sampling resolution for the SDF backend. Omitted, the ambient ``use_defaults(res=...)`` value
                applies.

        """
        if not (height > 0):
            raise Bosl2ValueError(f"extrude() needs height > 0, got {height}")
        fn = self._sdf_fn
        h = float(height)
        z0 = -h / 2 if center else 0.0

        def sdf_fn(x, y, z):  # type: ignore[no-untyped-def]
            d2d = fn(x, y)
            zz = z - z0
            out = lv.max(d2d, lv.max(zz - h, -zz))
            if rounding_top > 0:
                q1, q2 = d2d + rounding_top, (zz - h) + rounding_top
                out = lv.max(
                    out,
                    lv.min(lv.max(q1, q2), 0) + _lv_hypot(lv.max(q1, 0), lv.max(q2, 0)) - rounding_top,
                )
            if rounding_bottom > 0:
                q1, q2 = d2d + rounding_bottom, -zz + rounding_bottom
                out = lv.max(
                    out,
                    lv.min(lv.max(q1, q2), 0) + _lv_hypot(lv.max(q1, 0), lv.max(q2, 0)) - rounding_bottom,
                )
            if rounding_top < 0:
                f = -rounding_top
                du = lv.min(lv.abs(d2d), f + 1)
                ring = lv.max(f - _lv_hypot(du - f, zz - (h - f)), lv.max(zz - h, (h - f) - zz))
                ring = lv.max(ring, lv.abs(d2d) - f)
                out = lv.min(out, ring)
            if rounding_bottom < 0:
                f = -rounding_bottom
                du = lv.min(lv.abs(d2d), f + 1)
                ring = lv.max(f - _lv_hypot(du - f, zz - f), lv.max(-zz, zz - f))
                ring = lv.max(ring, lv.abs(d2d) - f)
                out = lv.min(out, ring)
            return out

        flare = max(0.0, -rounding_top, -rounding_bottom)
        extruded = PyShape(
            sdf_fn,
            [self.mn[0] - flare, self.mn[1] - flare, z0],
            [self.mx[0] + flare, self.mx[1] + flare, z0 + h],
            res if res is not None else self.res,
        )
        # A 2-D SDF becomes geometry only by extruding, so this is where a recorded colour or
        # preview modifier is handed on -- carried across as metadata, so the result stays a field
        # rather than being meshed to apply it (SPEC C-19, B-5).
        if self._colour is not None or self._modifier is not None:
            extruded._colour = self._colour
            extruded._modifier = self._modifier
        return extruded

    def revolve_sdf(self, angle: float = 360.0, res: int = 10) -> PyShape:
        """Revolve this 2-D profile around the Z axis, returning a 3-D PyShape.

        Args:
            angle: degrees to revolve (default 360 for full solid of revolution)
            res: meshing resolution (default 10). Omitted, the ambient ``use_defaults(res=...)`` value applies.
        """
        from pybosl2.sdf.skin import _revolve_sdf

        return _revolve_sdf(self, angle=angle, res=res)

    rotate_sweep = revolve_sdf

    def rotate_extrude(
        self,
        angle: float = 360.0,
        convexity: int | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
        res: int | None = None,
    ) -> PyShape:
        """Revolve this 2-D profile about the Z axis into a solid -- the contract's spelling.

        The same operation as :meth:`revolve_sdf`, under the name `Flat` declares and the CSG 2-D
        shape already used (SPEC C-17, PAR-4). Having only the backend's own name made a caller's
        code backend-specific for no reason.

        Args:
            angle: sweep angle in degrees (default: a full revolution).
            convexity: accepted for signature parity with the CSG spelling; a field has no
                facet count to hint at.
            fn: accepted and ignored -- tessellation is `res` on this backend (SPEC B-9). Omitted, the ambient
                ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back out to fa/fs.
            fa: accepted and ignored, as *fn*. Omitted, the ambient ``use_defaults(fa=...)`` value applies.
            fs: accepted and ignored, as *fn*. Omitted, the ambient ``use_defaults(fs=...)`` value applies.
            res: sampling resolution; the ambient default applies when omitted. Omitted, the ambient
                ``use_defaults(res=...)`` value applies.

        Returns:
            The revolved :class:`PyShape`.

        Examples:
            .. pythonscad-example::

                from pybosl2 import square, use_backend

                with use_backend("sdf"):
                    shape = square([6, 20]).right(14).rotate_extrude()
                shape.show()

        """
        _ = (convexity, fn, fa, fs)
        return self.revolve_sdf(angle=angle, res=res if res is not None else self.res)

    def distribute_on_path(
        self,
        path: Any,
        num_copies: int | None = None,
        spacing: float | None = None,
        start_pos: float | None = None,
        dist: list[float] | None = None,
        rotate_children: bool = True,
    ) -> PyShape2D:
        """Place copies of this shape along *path*, unioned into one shape (SPEC S-32).

        The 2-D twin of :meth:`pybosl2.sdf.shapes3d.SdfSolid.distribute_on_path`, built on the
        same `Distributable` matrices, so the placement is identical on both backends.

        Args:
            path: the route to place copies along, as a `Path2D` or a point sequence.
            num_copies: how many copies (default: one per path point).
            spacing: distance between copies along the path.
            start_pos: distance along the path to start at.
            dist: explicit distances along the path, one per copy.
            rotate_children: turn each copy to follow the path direction.

        Returns:
            The copies, unioned into one shape.

        Examples:
            .. pythonscad-example::

                from pybosl2 import Path2D, square, use_backend

                with use_backend("sdf"):
                    route = Path2D([[0, 0], [40, 0], [40, 30]])
                    trail = square([6, 4]).distribute_on_path(route, num_copies=8)
                trail.linear_extrude(height=3).show()

        """
        # Built on the inherited `path_copies`, which places the copies, rather than on a second
        # copy of the placement arithmetic: `distribute_on_path` is `path_copies` plus a union,
        # and two implementations of one placement would drift (PLAN O-1c).
        placed: list[PyShape2D] = self.path_copies(
            path,
            spacing=spacing,
            start_pos=start_pos,
            dist=dist,
            rotate_children=rotate_children,
            num_copies=num_copies,
        )
        if not placed:
            raise Bosl2ValueError("distribute_on_path(): the path produced no positions to place a copy at.")
        out = placed[0]
        for piece in placed[1:]:
            out = out | piece
        return out

    def linear_sweep_sdf(  # type: ignore[no-untyped-def]
        self,
        height: float = 1.0,
        twist: float = 0.0,
        scale=1.0,
        shift=(0.0, 0.0),
        center: bool = False,
        slices: int | None = None,
        res: int = 10,
    ) -> PyShape:
        """Extrude this 2-D SDF shape vertically with optional twist, scale, and XY shift.

        Args:
            height: extrusion height (default 1)
            twist: total degrees of twist over *height* (default 0)
            scale: final scale factor or ``[sx, sy]`` at the top (default 1)
            shift: XY displacement of the top relative to the bottom (default [0, 0])
            center: centre the extrusion on Z (default: sits on z=0..height)
            slices: ignored -- the field is continuous, so there is nothing to subdivide (accepted so the signature
                matches the CSG sweep)
            res: meshing resolution (default 10). Omitted, the ambient ``use_defaults(res=...)`` value applies.
        """
        from pybosl2.sdf.skin import _linear_sweep_sdf

        return _linear_sweep_sdf(
            self,
            height=height,
            twist=twist,
            scale=scale,
            shift=shift,
            center=center,
            slices=slices,
            res=res,
        )

    linear_sweep = linear_sweep_sdf

    def __getattr__(self, name: str) -> Any:
        # Fall through to a thin extrusion's meshed solid -- an escape hatch for native-only
        # attributes (color/show/...); extrude explicitly whenever the height matters.
        return getattr(self.extrude(0.01).mesh(), name)


def circle2d(radius: float | None = None, diameter: float | None = None, res: int = 10) -> PyShape2D:
    """Return a circle at the origin -- the exact SDF `length(p) - radius`.

    Args:
        radius: Radius of the circle.
        diameter: Diameter, instead of *radius*.
        res: Sampling resolution for the SDF backend. Omitted, the ambient ``use_defaults(res=...)`` value applies.
    """
    rad = _radius(radius=radius, diameter=diameter, dflt=1)
    return PyShape2D(lambda x, y: _lv_hypot(x, y) - rad, [-rad, -rad], [rad, rad], res)


def rect2d(  # type: ignore[no-untyped-def]
    size,
    rounding: "float | Sequence[float]" = 0,
    chamfer: "float | Sequence[float]" = 0,
    anchor: "Sequence[float]" = CENTER,
    res: int = 10,
) -> PyShape2D:
    """Return an axis-aligned rectangle with optional corner rounding or chamfering -- a single radius.

    for all four corners, or a per-corner list in BOSL2 rect() order ([X+Y+, X-Y+, X-Y-, X+Y-],
    counterclockwise from the +x+y corner), reusing the same per-corner quadrant SDF the 3-D
    cuboid edge machinery is built on. `anchor` uses the usual direction-vector convention.

    Args:
        size: Rectangle size, a scalar or ``[width, height]``.
        rounding: Corner rounding radius: one value, or one per corner.
        chamfer: Corner chamfer size: one value, or one per corner.
        anchor: Anchor as a direction vector, e.g. ``[-1, 0]`` for the left edge.
        res: Sampling resolution for the SDF backend. Omitted, the ambient ``use_defaults(res=...)`` value applies.

    """
    sz = [float(size), float(size)] if isinstance(size, (int, float)) else [float(v) for v in size]
    hx, hy = sz[0] / 2, sz[1] / 2
    has_rounding = (rounding != 0) if isinstance(rounding, (int, float)) else any(rounding)
    has_chamfer = (chamfer != 0) if isinstance(chamfer, (int, float)) else any(chamfer)
    if has_rounding and has_chamfer:
        raise Bosl2ValueError("Cannot specify nonzero rounding and chamfer together")
    mode = EdgeMode.CHAMFER if has_chamfer else EdgeMode.ROUND
    amt = chamfer if has_chamfer else rounding
    per_corner = [float(amt)] * 4 if isinstance(amt, (int, float)) else [float(v) for v in amt]
    if not (len(per_corner) == 4):
        raise Bosl2ValueError(f"per-corner treatment needs 4 values, got {per_corner}")
    if not (max(per_corner) <= min(hx, hy) + 1e-09):
        raise Bosl2ValueError(f"corner treatment {per_corner} exceeds half the rectangle {sz}")
    # BOSL2 corner order [(+,+), (-,+), (-,-), (+,-)] -> _rect2d's [(-,-), (+,-), (-,+), (+,+)].
    amount = [per_corner[2], per_corner[3], per_corner[1], per_corner[0]]

    def sdf_fn(x, y):  # type: ignore[no-untyped-def]
        return _rect2d(x, y, hx, hy, amount, mode)

    shape = PyShape2D(sdf_fn, [-hx, -hy], [hx, hy], res)
    ax, ay = (list(anchor) + [0, 0])[:2]
    if ax or ay:
        shape = shape.translate([-ax * hx, -ay * hy])
    return shape


def supershape2d(
    step: float = 0.5,
    n: int | None = None,
    m1: float = 4,
    m2: float | None = None,
    n1: float | None = None,
    n2: float | None = None,
    n3: float | None = None,
    a: float = 1,
    b: float | None = None,
    radius: float | None = None,
    diameter: float | None = None,
    res: int = 10,
) -> PyShape2D:
    """Return a superformula shape -- the outline sampled in plain Python (pysolidfive._paths, same.

    parameters and sampling as the bosl2 port's supershape()) and turned into a polygon2d().

    Args:
        step: Angular step in degrees between sampled points.
        n: Number of points to sample, instead of *step*.
        m1: Superformula rotational symmetry of the first term.
        m2: Superformula rotational symmetry of the second term; defaults to *m1*.
        n1: Superformula exponent controlling overall roundness.
        n2: Superformula exponent on the first term; defaults to *n1*.
        n3: Superformula exponent on the second term; defaults to *n1*.
        a: Superformula scale of the first term.
        b: Superformula scale of the second term; defaults to *a*.
        radius: Radius the outline is scaled to.
        diameter: Diameter, instead of *radius*.
        res: libfive meshing resolution passed to frep(). Omitted, the ambient ``use_defaults(res=...)`` value
            applies.

    """
    return polygon2d(
        Path2D(
            _supershape_path(
                step=step, n=n, m1=m1, m2=m2, n1=n1, n2=n2, n3=n3, a=a, b=b, radius=radius, diameter=diameter
            )
        ),
        res=res,
    )


def polygon2d(paths: "Path2D | Sequence[Path2D]", res: int = 10) -> PyShape2D:
    """Return an arbitrary SIMPLE polygon (or a list of disjoint ones), via the same convex-deficiency.

    decomposition polygon_prism() uses -- concave outlines welcome, holes not supported.

    Args:
        paths: one outline as a `Path2D`, or several disjoint ones (SPEC C-7a).
        res: libfive meshing resolution passed to frep(). Omitted, the ambient ``use_defaults(res=...)`` value
            applies.

    Returns:
        The polygon as a 2-D SDF shape.

    Raises:
        Bosl2ValueError: If `paths` is not a `Path2D` (or a sequence of them), or an outline has
            fewer than 3 points.

    """
    path_list = as_path_list(paths, "paths", "polygon2d")
    for p in path_list:
        if not (len(p) >= 3):
            raise Bosl2ValueError(f"polygon2d(): every path needs >= 3 points, got {len(p)}")

    def sdf_fn(x, y):  # type: ignore[no-untyped-def]
        d = None
        for p in path_list:
            dp = _polygon_sdf_xy(x, y, p)
            d = dp if d is None else lv.min(d, dp)
        return d

    xs = [p[0] for path in path_list for p in path]
    ys = [p[1] for path in path_list for p in path]
    return PyShape2D(sdf_fn, [min(xs), min(ys)], [max(xs), max(ys)], res)


def region2d(paths: "Path2D | Sequence[Path2D]", res: int = 10) -> PyShape2D:
    """BOSL2-style REGION data as a PyShape2D: a list of simple outlines with even-odd nesting.

    semantics -- an outline inside another outline is a hole, an outline inside a hole is an
    island, and so on -- exactly what the real-BOSL2 region functions (make_region/union/
    difference/offset_stroke/...) hand back and what the native `region()` helper in
    base_bgtk.py renders via polygon(paths=...). This is the SDF equivalent for code building
    on pysolidfive: nesting depths are worked out once in Python (ray-casting a vertex of each
    outline against the others), holes subtract from their direct parents, and islands rejoin
    the union.

    Args:
        paths: The outlines making up the region, nested even-odd so inner rings are holes.
        res: Sampling resolution for the SDF backend. Omitted, the ambient ``use_defaults(res=...)`` value applies.

    """
    cleaned = as_path_list(paths, "paths", "region2d")
    for p in cleaned:
        if not (len(p) >= 3):
            raise Bosl2ValueError(f"region2d(): every outline needs >= 3 points, got {len(p)}")

    def contains(poly: list[list[float]], pt: Sequence[float]) -> bool:
        # Standard even-odd ray cast (+x direction).
        x, y = pt
        inside = False
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            if (y1 > y) != (y2 > y):
                t = (y - y1) / (y2 - y1)
                if x < x1 + t * (x2 - x1):
                    inside = not inside
        return inside

    depths = []
    for i, p in enumerate(cleaned):
        depth = sum(1 for j, q in enumerate(cleaned) if j != i and contains(q, p[0]))  # type: ignore[misc,arg-type]
        depths.append(depth)

    def sdf_fn(x, y):  # type: ignore[no-untyped-def]
        d = None
        for i, p in enumerate(cleaned):
            if depths[i] % 2 != 0:
                continue  # holes are handled from their parents below
            dp = _polygon_sdf_xy(x, y, p)
            for j, q in enumerate(cleaned):
                if j != i and depths[j] == depths[i] + 1 and contains(p, q[0]):  # type: ignore[arg-type]
                    dp = lv.max(dp, -_polygon_sdf_xy(x, y, q))
            d = dp if d is None else lv.min(d, dp)
        return d

    xs = [p[0] for path in cleaned for p in path]
    ys = [p[1] for path in cleaned for p in path]
    return PyShape2D(sdf_fn, [min(xs), min(ys)], [max(xs), max(ys)], res)


def stroke2d(
    path: "Path2D",
    width: float = 1,
    closed: bool = False,
    res: int = 10,
) -> PyShape2D:
    """Return a path drawn with round caps and joins (BOSL2 stroke()'s default look) -- exactly, as.

    the min over the segments' capsule SDFs (distance-to-segment minus width/2).

    Args:
        path: The path to draw.
        width: Width of the drawn line.
        closed: Join the last point back to the first before drawing.
        res: Sampling resolution for the SDF backend. Omitted, the ambient ``use_defaults(res=...)`` value applies.

    """
    path = cast("Path2D", require_path(path, "path", "stroke2d", Path2D))
    pts = as_points(path)
    if not (len(pts) >= 2):
        raise Bosl2ValueError("stroke2d() needs at least 2 points")
    segs = pts if closed else pts[:-1]

    def sdf_fn(x, y):  # type: ignore[no-untyped-def]
        diameter2 = None
        n = len(pts)
        for i in range(len(segs)):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            ex, ey = bx - ax, by - ay
            elen2 = ex * ex + ey * ey
            if elen2 < 1e-18:
                continue
            px, py = x - ax, y - ay
            t = lv.max(0, lv.min(1, (px * ex + py * ey) / elen2))
            dx, dy = px - t * ex, py - t * ey
            seg_d2 = dx * dx + dy * dy
            diameter2 = seg_d2 if diameter2 is None else lv.min(diameter2, seg_d2)
        return lv.sqrt(diameter2) - width / 2

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    g = width / 2
    return PyShape2D(sdf_fn, [min(xs) - g, min(ys) - g], [max(xs) + g, max(ys) + g], res)


def hull2d_discs(discs: list, res: int = 10) -> PyShape2D:  # type: ignore[type-arg]
    """Return the convex hull of a set of discs [(x, y, r), ...] -- the SDF equivalent of the.

    hull(circle().translate(), circle().translate(), ...) idiom all over shapes.py. EXACT for
    equal radii (the true distance to the centers' convex hull, minus r -- computed with the
    branchless exact-convex form, so the rounded corners are genuine arcs, not the sharp
    corners a plain half-plane max would give); for mixed radii it conservatively uses the
    largest radius for the hull body unioned with each disc exactly, which matches the visual
    silhouette whenever the smaller discs sit inside the hull of the larger ones.

    Args:
        discs: The discs to hull, each ``(x, y, radius)``.
        res: Sampling resolution for the SDF backend. Omitted, the ambient ``use_defaults(res=...)`` value applies.

    """
    ds = [(float(c[0]), float(c[1]), float(c[2])) for c in discs]
    if not (ds):
        raise Bosl2ValueError("hull2d_discs() needs at least one disc")
    if len(ds) == 1:
        cx, cy, r = ds[0]
        return circle2d(radius=r, res=res).translate([cx, cy])

    centers = [[c[0], c[1]] for c in ds]
    rmax = max(c[2] for c in ds)

    def sdf_fn(x, y):  # type: ignore[no-untyped-def]
        if len(centers) == 2 or _collinear(centers):
            # Degenerate hull: distance to the segment chain between extreme centers.
            diameter2 = None
            for i in range(len(centers) - 1):
                ax, ay = centers[i]
                bx, by = centers[i + 1]
                ex, ey = bx - ax, by - ay
                elen2 = ex * ex + ey * ey
                if elen2 < 1e-18:
                    continue
                px, py = x - ax, y - ay
                t = lv.max(0, lv.min(1, (px * ex + py * ey) / elen2))
                dx, dy = px - t * ex, py - t * ey
                sd2 = dx * dx + dy * dy
                diameter2 = sd2 if diameter2 is None else lv.min(diameter2, sd2)
            body = lv.sqrt(diameter2) - rmax
        else:
            hull_pts = _hull2d_points(centers)
            halfmax = _halfplane_max_sdf(x, y, hull_pts)
            true_out = lv.sqrt(_polygon_dist2_xy(x, y, hull_pts))
            exact = lv.max(halfmax, true_out + _PENALTY * lv.min(halfmax, 0))
            body = exact - rmax
        out = body
        for cx, cy, r in ds:
            if r < rmax - 1e-12:
                out = lv.min(out, _lv_hypot(x - cx, y - cy) - r)
        return out

    xs = [c[0] - c[2] for c in ds] + [c[0] + c[2] for c in ds]
    ys = [c[1] - c[2] for c in ds] + [c[1] + c[2] for c in ds]
    return PyShape2D(sdf_fn, [min(xs), min(ys)], [max(xs), max(ys)], res)


# ---------------------------------------------------------------------------
#  additional 2-D shapes
# ---------------------------------------------------------------------------


def square2d(size: float | Sequence[float] = 10, anchor: Sequence[float] = CENTER, res: int = 10) -> PyShape2D:
    """Return a square of the given *size* (scalar or ``[w, h]``). Delegates to rect2d().

    Args:
        size: Square size, a scalar or ``[width, height]``.
        anchor: Anchor as a direction vector, e.g. ``[-1, 0]`` for the left edge.
        res: Sampling resolution for the SDF backend. Omitted, the ambient ``use_defaults(res=...)`` value applies.
    """
    sz = [float(size), float(size)] if isinstance(size, (int, float)) else list(size)
    return rect2d(sz, anchor=anchor, res=res)


def ellipse2d(
    radius: float | Sequence[float] | None = None,
    diameter: float | Sequence[float] | None = None,
    res: int = 10,
) -> PyShape2D:
    """Return an ellipse with semi-axes *radius* (``[rx, ry]``) or full diameters *diameter* (``[dx, dy]``).

    Built by non-uniformly scaling a unit circle SDF, which gives an exact algebraic distance
    whose zero-isosurface is the desired ellipse.

    Args:
        radius: Semi-axes as ``[rx, ry]``, or one value for a circle.
        diameter: Full diameters as ``[dx, dy]``, instead of *radius*.
        res: Sampling resolution for the SDF backend. Omitted, the ambient ``use_defaults(res=...)`` value applies.

    """
    if radius is not None:
        rx, ry = (
            (float(radius), float(radius)) if isinstance(radius, (int, float)) else (float(radius[0]), float(radius[1]))
        )
    elif diameter is not None:
        dx, dy = (
            (float(diameter), float(diameter))
            if isinstance(diameter, (int, float))
            else (float(diameter[0]), float(diameter[1]))
        )
        rx, ry = dx / 2, dy / 2
    else:
        rx = ry = 1.0

    def sdf_fn(x, y):  # type: ignore[no-untyped-def]
        return _lv_hypot(x / max(rx, 1e-9), y / max(ry, 1e-9)) - 1.0

    return PyShape2D(sdf_fn, [-rx, -ry], [rx, ry], res)


def regular_ngon2d(
    num_sides: int = 6,
    radius: float | None = None,
    diameter: float | None = None,
    outer_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_radius: float | None = None,
    inner_diameter: float | None = None,
    side: float | None = None,
    realign: bool = False,
    res: int = 10,
) -> PyShape2D:
    """Return a regular num_sides-gon (triangle, square, pentagon, hexagon, ...) as a signed-distance field.

    Size is controlled by one of the radius/diameter/side parameters:
    ``inner_radius``/``inner_diameter`` > ``outer_radius``/``outer_diameter`` > ``radius``/``diameter`` > ``side``.

    Args:
        num_sides:       number of sides (default 6)
        radius:     radius/diameter to the vertices
        diameter:     radius/diameter to the vertices
        outer_radius: outer radius/diameter (BOSL2 ``or``)
        outer_diameter: outer radius/diameter (BOSL2 ``or``)
        inner_radius:   inner radius/diameter (apothem to face centres)
        inner_diameter:   inner radius/diameter (apothem to face centres)
        side:    length of each side
        realign: rotate so a face centre faces +X (default: vertex at +X)
        res: meshing resolution (default 10). Omitted, the ambient ``use_defaults(res=...)`` value applies.

    """
    import math as _m

    sc = 1 / _m.cos(_m.radians(180.0 / num_sides))
    ir_s = inner_radius * sc if inner_radius is not None else None
    id_s = inner_diameter * sc if inner_diameter is not None else None
    side_s = side / 2 / _m.sin(_m.radians(180.0 / num_sides)) if side is not None else None
    rad = _radius(
        radius1=ir_s,
        diameter1=id_s,
        radius2=outer_radius,
        diameter2=outer_diameter,
        radius=radius,
        diameter=diameter,
        dflt=side_s if side_s is not None else 1,
    )
    if rad is None:  # pragma: no cover
        # defensive: _radius() falls back to dflt (the side-derived radius, or 1), so it returns
        # None only when dflt is None too -- which cannot happen here.
        raise Bosl2ValueError(
            "regular_ngon2d(): need one of radius, diameter, outer_radius, outer_diameter, inner_radius, inner_diameter, or side."  # noqa: E501
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

    return polygon2d(Path2D(pts), res=res)


def star2d(
    num_sides: int = 5,
    radius: float | None = None,
    inner_radius: float | None = None,
    diameter: float | None = None,
    outer_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_diameter: float | None = None,
    step: int | None = None,
    realign: bool = False,
    res: int = 10,
) -> PyShape2D:
    """Return a num_sides-pointed star polygon as a signed-distance field.

    Args:
        num_sides:       number of stellate tips (default 5)
        radius: radius to the tips
        outer_radius: radius to the tips (BOSL2 ``or``)
        inner_radius:      radius to the inner corners
        diameter:    diameter to the tips
        outer_diameter:    diameter to the tips
        inner_diameter:      diameter to the inner corners
        step:    compute inner radius by drawing a line ``step`` tips around
        realign: put edge midpoint on +X instead of tip (default False)
        res: meshing resolution (default 10). Omitted, the ambient ``use_defaults(res=...)`` value applies.

    """
    import math as _m

    rad = _radius(radius1=outer_radius, diameter1=outer_diameter, radius=radius, diameter=diameter, dflt=1)
    if step is not None:
        stepr = rad * _m.cos(_m.radians(180 * step / num_sides)) / _m.cos(_m.radians(180 * (step - 1) / num_sides))
    else:
        stepr = rad
    inner_r = _radius(radius=inner_radius, diameter=inner_diameter, dflt=stepr)

    pts = []
    for i in range(2 * num_sides, 0, -1):
        a = _m.radians(180.0 * i / num_sides)
        rr = inner_r if i % 2 else rad
        pts.append([rr * _m.cos(a), rr * _m.sin(a)])
    if realign:
        pts = [
            [
                p[0] * _m.cos(-_m.pi / num_sides) - p[1] * _m.sin(-_m.pi / num_sides),
                p[0] * _m.sin(-_m.pi / num_sides) + p[1] * _m.cos(-_m.pi / num_sides),
            ]
            for p in pts
        ]

    return polygon2d(Path2D(pts), res=res)


def trapezoid2d(
    height: float | None = None,
    width1: float | None = None,
    width2: float | None = None,
    angle: float | None = None,
    shift: float = 0,
    anchor: "Sequence[float]" = CENTER,
    res: int = 10,
) -> PyShape2D:
    """Return a trapezoid with parallel front and back sides, as a signed-distance field.

    Args:
        height:    Y-axis height
        width1:   X-axis width of the front end
        width2:   X-axis width of the back end
        angle:  if given in place of height/width1/width2, the missing value is derived
        shift: X-axis shift of the back (default 0)
        anchor: anchor point (default CENTER)
        res: meshing resolution (default 10). Omitted, the ambient ``use_defaults(res=...)`` value applies.

    """
    import math as _m

    _ = anchor
    defined = sum(x is not None for x in (height, width1, width2, angle))
    if defined != 3:
        raise Bosl2ValueError(
            f"trapezoid2d(): give exactly three of height=, width1=, width2= and angle= (got {defined})."
        )

    if height is None:
        height = abs(width2 - width1) / 2 / _m.tan(_m.radians(abs(angle)))  # type: ignore[operator,arg-type]
    if width1 is None:
        width1 = width2 + 2 * (height * _m.tan(_m.radians(angle)) + shift)  # type: ignore[operator,arg-type]
    if width2 is None:
        width2 = width1 - 2 * (height * _m.tan(_m.radians(angle)) + shift)  # type: ignore[operator,arg-type]
    if not (width1 >= 0):
        raise Bosl2ValueError("Degenerate trapezoid geometry.")
    if not (width2 >= 0):
        raise Bosl2ValueError("Degenerate trapezoid geometry.")
    if not (height > 0):
        raise Bosl2ValueError("Degenerate trapezoid geometry.")

    pts = [
        [width2 / 2 + shift, height / 2],
        [-width2 / 2 + shift, height / 2],
        [-width1 / 2, -height / 2],
        [width1 / 2, -height / 2],
    ]
    return polygon2d(Path2D(pts), res=res)


_KEYHOLE_EPS = 1e-9


def _sampled_arc(
    centre: tuple[float, float],
    radius: float,
    start_deg: float,
    sweep_deg: float,
    per_deg: float,
) -> list[list[float]]:
    """Sample an arc of *sweep_deg* (signed: negative sweeps clockwise) at roughly *per_deg* density."""
    n = max(3, int(abs(sweep_deg) * per_deg))
    out = []
    for i in range(n):
        a = math.radians(start_deg + sweep_deg * i / (n - 1))
        out.append([centre[0] + radius * math.cos(a), centre[1] + radius * math.sin(a)])
    return out


def _dedupe_ring(pts: list[list[float]]) -> list[list[float]]:
    """Drop consecutive duplicate points (and a repeated closing point) from a sampled ring."""
    out: list[list[float]] = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) > _KEYHOLE_EPS or abs(p[1] - out[-1][1]) > _KEYHOLE_EPS:
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < _KEYHOLE_EPS and abs(out[0][1] - out[-1][1]) < _KEYHOLE_EPS:
        out.pop()
    return out


def keyhole_outline(
    length: float = 15,
    radius1: float = 5,
    radius2: float = 10,
    shoulder_radius: float = 0,
    diameter1: float | None = None,
    diameter2: float | None = None,
    res: int = 10,
) -> list[list[float]]:
    """Return the classic keyhole outline as a counter-clockwise list of ``[x, y]`` points.

    The shape BOSL2's ``keyhole()`` builds: circle *radius1* at the origin, circle *radius2* at
    ``[0, -length]``, joined by a parallel-sided neck that runs tangent to the SMALLER of the two.
    Where the neck's walls meet the larger circle they cross at a genuine corner, and
    *shoulder_radius* rounds that corner off with a concave fillet -- so unlike the arcs and walls,
    the fillet ADDS material, filling the inside corner rather than cutting it away.

    The fillet centre sits ``shoulder_radius`` off the wall and ``radius + shoulder_radius`` from
    the large circle's centre, which is what makes it tangent to both; that construction also fixes
    how far down the neck the shoulder lands, hence the ``dy`` below.

    Args:
        length:     distance between the two circle centres (default 15)
        radius1:    radius of the circle at the origin (default 5)
        radius2:    radius of the circle at ``[0, -length]`` (default 10)
        shoulder_radius: concave fillet radius at the two shoulders; 0 leaves them sharp
        diameter1:  diameter form of *radius1*
        diameter2:  diameter form of *radius2*
        res: point density (default 10). Omitted, the ambient ``use_defaults(res=...)`` value applies.

    Returns:
        The outline points, counter-clockwise, without a repeated closing point.

    """
    r1v = _pick_radius(radius=radius1, diameter=diameter1, dflt=5)
    r2v = _pick_radius(radius=radius2, diameter=diameter2, dflt=10)
    sh = float(shoulder_radius or 0.0)
    if not (length > 0):
        raise Bosl2ValueError("keyhole_outline(): length must be positive.")
    if not (min(r1v, r2v) > 0):
        raise Bosl2ValueError("keyhole_outline(): both radii must be positive.")
    if not (sh >= 0):
        raise Bosl2ValueError("keyhole_outline(): shoulder_radius cannot be negative.")

    # Build with the smaller circle at the origin, then rotate a half turn if it was the other way
    # round: a half turn preserves the winding, so the result stays counter-clockwise either way.
    small, big = min(r1v, r2v), max(r1v, r2v)
    flipped = r1v > r2v
    per_deg = max(12, res * 4) / 90.0

    # How far down the neck the shoulder lands: the fillet centre is (small+sh) off the axis and
    # (big+sh) from the large circle's centre, so the axial offset closes the right triangle.
    dy = math.sqrt((big + sh) ** 2 - (small + sh) ** 2)
    if not (dy < length):
        raise Bosl2ValueError(
            f"keyhole_outline(): no room for a neck between the circles "
            f"(length={length}, radii={r1v}/{r2v}, shoulder_radius={sh})."
        )

    stadium = (big - small) < _KEYHOLE_EPS  # equal radii: the walls meet the far circle tangentially
    fillet = sh > _KEYHOLE_EPS and not stadium
    centre_r = (small + sh, -length + dy)  # right-hand fillet centre
    wall_r = [small, -length + dy]  # where that fillet meets the wall
    circle_r = (
        [big * (small + sh) / (big + sh), -length + big * dy / (big + sh)] if not stadium else [small, -length]
    )  # ...and where it meets the large circle

    pts = _sampled_arc((0.0, 0.0), small, 0.0, 180.0, per_deg)  # small circle, over the top
    pts.append([-wall_r[0], wall_r[1]])  # down the left wall
    if fillet:  # concave, so it is traced clockwise while the rest runs counter-clockwise
        to_circle = math.degrees(math.atan2(circle_r[1] - centre_r[1], -circle_r[0] + centre_r[0]))
        pts += _sampled_arc((-centre_r[0], centre_r[1]), sh, 0.0, to_circle % 360 - 360, per_deg)

    right = math.degrees(math.atan2(circle_r[1] + length, circle_r[0]))
    pts += _sampled_arc((0.0, -length), big, 180 - right, (right + 360) - (180 - right), per_deg)

    if fillet:
        from_circle = math.degrees(math.atan2(circle_r[1] - centre_r[1], circle_r[0] - centre_r[0]))
        pts += _sampled_arc(centre_r, sh, from_circle, (180 - from_circle) % 360 - 360, per_deg)
    else:
        pts.append(list(wall_r))  # sharp shoulder: the corner itself

    pts = _dedupe_ring(pts)
    return [[-p[0], -length - p[1]] for p in pts] if flipped else pts


def keyhole2d(
    length: float = 15,
    radius1: float = 5,
    radius2: float = 10,
    shoulder_radius: float = 0,
    diameter1: float | None = None,
    diameter2: float | None = None,
    res: int = 10,
) -> PyShape2D:
    """Return a keyhole slot -- two circles joined by a parallel-sided neck -- as an SDF polygon.

    The outline itself is :func:`keyhole_outline`; see there for the construction and for the
    meaning of *shoulder_radius*.

    Args:
        length:     distance between the two circle centres (default 15)
        radius1:    radius of the circle at the origin (default 5)
        radius2:    radius of the circle at ``[0, -length]`` (default 10)
        shoulder_radius: concave fillet radius at the two shoulders; 0 leaves them sharp
        diameter1:  diameter form of *radius1*
        diameter2:  diameter form of *radius2*
        res: meshing resolution (default 10). Omitted, the ambient ``use_defaults(res=...)`` value applies.

    """
    pts = keyhole_outline(
        length=length,
        radius1=radius1,
        radius2=radius2,
        shoulder_radius=shoulder_radius,
        diameter1=diameter1,
        diameter2=diameter2,
        res=res,
    )
    return polygon2d(Path2D(pts), res=res)


PyShape2D = SdfShape2D

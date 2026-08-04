# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Concrete base for Bosl2Shape2D and Bosl2Solid, implementing all shared
transform, CSG, colour, and distributor methods that were previously
duplicated across both subclasses.
"""

# LibFile: pybosl2/_shape.py
# FileGroup: BOSL2

from __future__ import annotations

import numbers
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from collections.abc import Sequence

from pybosl2._backend import check_operand_backend as _check_operand_backend
from pybosl2._backend import unsupported_feature as _unsupported_feature
from pybosl2.color import Colorable
from pybosl2.distributors import Distributable

__all__ = ["BaseShape"]

_NATIVE_PASSTHROUGH = frozenset(
    {
        "linear_extrude",
        "offset",
        "resize",
        "render",
        "minkowski",
        "color",
        "highlight",
        "background",
        "set_modifier",
        "projection",
        "repair",
        "wrap",
        "pull",
        "oversample",
        "separate",
        "inside",
        "convexity",
        "fn",
        "fa",
        "fs",
        "position",
        "size",
        "translate",
        "rotate",
        "mirror",
        "scale",
        "multmatrix",
        "union",
        "intersection",
        "difference",
        "rotate_extrude",
        "show",
        "roof",
    }
)


class BaseShape(Colorable, Distributable):
    """Concrete base providing transforms, directional moves, CSG operators,
    colour, and distributor methods shared by both 2-D and 3-D shapes.

    Every shared method that was duplicated across
    :class:`~pybosl2.shapes2d.Bosl2Shape2D` and
    :class:`~pybosl2.shapes3d.Bosl2Solid` lives here once.  Subclasses add
    dimension-specific operations and implement the backend hooks
    ``_color_native``, ``_highlight_native``, ``_ghost_native``, and
    ``_distribute``.
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

    # ------------------------------------------------------------------
    # Backend hooks (abstract here, concrete on each subclass)
    # ------------------------------------------------------------------

    def _color_native(self, c: Any = None, alpha: float | None = None) -> Self:
        raise NotImplementedError

    def _highlight_native(self) -> Self:
        raise NotImplementedError

    def _ghost_native(self) -> Self:
        raise NotImplementedError

    def _distribute(self, mats: list[Any]) -> list[Self]:  # type: ignore[override]
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Construction / wrapping
    # ------------------------------------------------------------------

    @staticmethod
    def _unwrap(x: object) -> Any:
        from pybosl2._helpers import unwrap

        return unwrap(x)

    def _wrap(self, new_shape: Any) -> Self:
        """Wrap a native result in the correct subclass, carrying metadata forward."""
        out = type(self)(new_shape, self.size, self.anchor)  # type: ignore[call-arg]
        if hasattr(self, "backend"):
            out.backend = self.backend  # type: ignore[attr-defined]
        return out

    _wrap_moved = _wrap

    def __scad__(self) -> Any:
        """Auto-unwrap conversion hook for the PythonSCAD C++ layer interop."""
        return self.shape

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.shape!r}, size={self.size!r}, anchor={self.anchor!r})"

    # ------------------------------------------------------------------
    # Transforms
    # ------------------------------------------------------------------

    def translate(self, v: Sequence[float]) -> Self:
        return self._wrap(self.shape.translate([float(c) for c in v]))  # type: ignore[attr-defined]

    move = translate

    def rotate(self, *a: object, **k: object) -> Self:
        if len(a) == 1 and isinstance(a[0], numbers.Real) and not isinstance(a[0], bool) and "v" not in k:
            a = ([0.0, 0.0, float(a[0])],)
        return self._wrap(self.shape.rotate(*a, **k))  # type: ignore[attr-defined]

    rot = rotate

    def mirror(self, v: Sequence[float]) -> Self:
        return self._wrap(self.shape.mirror([float(c) for c in v]))  # type: ignore[attr-defined]

    def multmatrix(self, m: Sequence[Sequence[float]]) -> Self:
        return self._wrap(self.shape.multmatrix(m))  # type: ignore[attr-defined]

    def scale(self, v: float | Sequence[float]) -> Self:
        return self._wrap(self.shape.scale(v))  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Directional moves (2-D versions; 3-D subclass adds up/down/3D vectors)
    # ------------------------------------------------------------------

    def right(self, x: float) -> Self:
        return self.translate([x, 0.0])

    def left(self, x: float) -> Self:
        return self.translate([-x, 0.0])

    def back(self, y: float) -> Self:
        return self.translate([0.0, y])

    def forward(self, y: float) -> Self:
        return self.translate([0.0, -y])

    fwd = forward

    # ------------------------------------------------------------------
    # CSG operators
    # ------------------------------------------------------------------

    def __or__(self, other: object) -> Self:
        _check_operand_backend(getattr(self, "backend", "csg"), other)
        return self._wrap(self.shape | self._unwrap(other))

    def __and__(self, other: object) -> Self:
        _check_operand_backend(getattr(self, "backend", "csg"), other)
        return self._wrap(self.shape & self._unwrap(other))

    def __sub__(self, other: object) -> Self:
        _check_operand_backend(getattr(self, "backend", "csg"), other)
        return self._wrap(self.shape - self._unwrap(other))

    def __ror__(self, other: object) -> Self:
        _check_operand_backend("csg", other)
        return self._wrap(self._unwrap(other) | self.shape)

    def __rand__(self, other: object) -> Self:
        _check_operand_backend("csg", other)
        return self._wrap(self._unwrap(other) & self.shape)

    def __rsub__(self, other: object) -> Self:
        _check_operand_backend("csg", other)
        return self._wrap(self._unwrap(other) - self.shape)

    # ------------------------------------------------------------------
    # Sequence operators (translate via +, scale via *)
    # ------------------------------------------------------------------

    def __add__(self, other: Sequence[float]) -> Self:
        try:
            len(other)
            return self.translate(other)
        except (TypeError, ValueError):
            return NotImplemented

    def __radd__(self, other: Sequence[float]) -> Self:
        try:
            len(other)
            return self.translate(other)
        except (TypeError, ValueError):
            return NotImplemented

    def __mul__(self, other: float | Sequence[float]) -> Self:
        return self.scale(other)

    def __rmul__(self, other: float | Sequence[float]) -> Self:
        return self.scale(other)

    # ------------------------------------------------------------------
    # __getattr__ passthrough with whitelist
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> object:
        if name == "shape" or (name.startswith("__") and name.endswith("__")):
            raise AttributeError(name)
        try:
            be = object.__getattribute__(self, "backend")
        except AttributeError:
            be = "csg"
        _unsupported = _unsupported_feature(be, name)
        if _unsupported is not None:
            raise _unsupported
        shape = object.__getattribute__(self, "shape")
        attr = getattr(shape, name)
        if not callable(attr):
            return attr
        if name not in _NATIVE_PASSTHROUGH:
            raise AttributeError(
                f"{type(self).__name__!r} object has no attribute {name!r} (not in the native passthrough set)"
            )
        native_cls = type(shape)

        def _forward(*args: object, **kwargs: object) -> object:
            result = attr(*args, **kwargs)
            if isinstance(result, native_cls):
                return self._wrap(result)
            if isinstance(result, (list, tuple)) and result and all(isinstance(r, native_cls) for r in result):
                return type(result)(self._wrap(r) for r in result)
            return result

        _forward.__name__ = name
        return _forward

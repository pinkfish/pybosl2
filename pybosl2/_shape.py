# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Concrete base for Bosl2Shape2D and Bosl2Solid, implementing all shared.

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
from pybosl2.enums import AttachTag

__all__ = ["BaseShape", "diff", "intersect"]


def _is_angle(value: object) -> bool:
    """Return True if *value* is a bare rotation angle (a real number, and not a bool)."""
    return isinstance(value, numbers.Real) and not isinstance(value, bool)


# Native methods forwarded verbatim to the wrapped shape. Membership is a CLAIM that the
# native object really has that method -- `minkowski`, `set_modifier`, `convexity`, `fn`,
# `fa` and `fs` were listed here and exist on neither the native object nor the wrapper, so
# they only ever produced a confusing AttributeError from the getattr below while making
# `hasattr(solid, name)` look meaningful. Verify against a real native handle before adding.
_NATIVE_PASSTHROUGH = frozenset(
    {
        "linear_extrude",
        "offset",
        "resize",
        "render",
        "color",
        "highlight",
        "background",
        "projection",
        "repair",
        "wrap",
        "pull",
        "oversample",
        "separate",
        "inside",
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
    """Concrete base providing transforms, directional moves, CSG operators,.

    colour, and distributor methods shared by both 2-D and 3-D shapes.

    Every shared method that was duplicated across
    :class:`~pybosl2.shapes2d.Bosl2Shape2D` and
    :class:`~pybosl2.shapes3d.Bosl2Solid` lives here once.  Subclasses add
    dimension-specific operations and implement the backend hooks
    ``_color_native``, ``_highlight_native``, ``_ghost_native``, and
    ``_distribute``.
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # the data model hands class-creation keywords through here; nothing of ours reads them
        super().__init_subclass__(**kwargs)

    @property
    def attachments(self) -> list[BaseShape]:
        """The list of attached sub-shapes.

        This tracks children elements attached to the current parent.
        """
        if not hasattr(self, "_attachments"):
            self._attachments: list[BaseShape] = []
        return self._attachments

    @attachments.setter
    def attachments(self, val: list[BaseShape]) -> None:
        self._attachments = val

    @property
    def tag_name(self) -> str:
        """The tag name of this shape.

        This is used to determine boolean operations during realization.
        """
        return getattr(self, "_tag_name", "")

    @tag_name.setter
    def tag_name(self, val: str) -> None:
        self._tag_name = val

    @property
    def diff_config(self) -> dict[str, Any] | None:
        """The configuration for tag-based boolean operations.

        Specifies difference or intersection configuration details.
        """
        return getattr(self, "_diff_config", None)

    @diff_config.setter
    def diff_config(self, val: dict[str, Any] | None) -> None:
        self._diff_config = val

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
        out.attachments = list(self.attachments)
        out.tag_name = self.tag_name
        out.diff_config = self.diff_config
        if hasattr(self, "_dont_propagate"):
            out._dont_propagate = self._dont_propagate
        return out

    def __scad__(self) -> Any:
        """Auto-unwrap conversion hook for the PythonSCAD C++ layer interop."""
        return self._unwrap(self)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.shape!r}, size={self.size!r}, anchor={self.anchor!r})"

    # ------------------------------------------------------------------
    # Transforms
    # ------------------------------------------------------------------

    def translate(self, v: Sequence[float]) -> Self:
        out = self._wrap(self.shape.translate([float(c) for c in v]))  # type: ignore[attr-defined]
        out.attachments = [att.translate(v) for att in self.attachments]
        return out

    move = translate

    def rotate(self, *a: object, **k: object) -> Self:
        # The native rotate() only takes a 3-vector, so a bare angle is spun about +Z. Both spellings
        # OpenSCAD accepts for it -- positional and ``a=`` -- need the same widening.
        if len(a) == 1 and _is_angle(a[0]) and "v" not in k:
            a = ([0.0, 0.0, float(a[0])],)  # type: ignore[arg-type]
        elif not a and _is_angle(k.get("a")) and "v" not in k:
            k = {**k, "a": [0.0, 0.0, float(k["a"])]}  # type: ignore[arg-type]
        out = self._wrap(self.shape.rotate(*a, **k))  # type: ignore[attr-defined]
        out.attachments = [att.rotate(*a, **k) for att in self.attachments]
        return out

    rot = rotate

    def mirror(self, v: Sequence[float]) -> Self:
        out = self._wrap(self.shape.mirror([float(c) for c in v]))  # type: ignore[attr-defined]
        out.attachments = [att.mirror(v) for att in self.attachments]
        return out

    def multmatrix(self, m: Sequence[Sequence[float]]) -> Self:
        out = self._wrap(self.shape.multmatrix(m))  # type: ignore[attr-defined]
        out.attachments = [att.multmatrix(m) for att in self.attachments]
        return out

    def scale(self, v: float | Sequence[float]) -> Self:
        out = self._wrap(self.shape.scale(v))  # type: ignore[attr-defined]
        out.attachments = [att.scale(v) for att in self.attachments]
        return out

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

    def minkowski(self, *others: object) -> Self:
        """Return the Minkowski SUM of this shape with *others* (OpenSCAD ``minkowski()``).

        Sweeps each of *others* over the whole of this shape, growing it by that shape: a
        sphere/circle grows it by a uniform margin with rounded corners, a cube/square with
        square ones -- the usual way to turn a part into the cutter that clears it. The
        dilating opposite of :meth:`~pybosl2.miscellaneous.Miscellaneous.minkowski_difference`,
        which erodes.

        Defined here rather than on the CSG solid/shape classes so ONE implementation serves
        both dimensions: the operands go through ``_unwrap`` and the result through ``_wrap``,
        so a 2-D shape returns a 2-D shape and a solid returns a solid.

        Note this is EXPENSIVE -- cost grows with the product of the operands' complexity -- so
        keep the swept shape as simple as the result allows (a low-``fn`` sphere, or a cube).

        Args:
            others: One or more shapes to sweep over this one. Several are applied in turn,
                matching OpenSCAD's variadic ``minkowski()``.

        Returns:
            A new shape of the same kind as this one, holding the Minkowski sum.

        Raises:
            AssertionError: If no shape to sweep is given.

        Examples:
            .. pythonscad-example::

                from pybosl2.shapes3d import cuboid, sphere

                cuboid([20, 30, 5]).minkowski(sphere(radius=2, fn=16)).show()

        """
        from pythonscad import minkowski as _minkowski

        assert others, "minkowski(): needs at least one shape to sweep over this one."
        backend = getattr(self, "backend", "csg")
        out = self.shape
        for other in others:
            _check_operand_backend(backend, other)
            out = _minkowski(out, self._unwrap(other))
        return self._wrap(out)

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
        # Private names never reach the native handle. `shape` guards the recursion trap on a
        # half-built wrapper (unpickling, __new__, an __init__ that raised), and every other
        # leading-underscore name -- _attachments, _tag_name, _diff_config, _dont_propagate --
        # is pybosl2's own bookkeeping, read through hasattr()/getattr(default) by _wrap() on
        # every wrapped result. A native PyOpenSCAD has no business answering those, and asking
        # one that came out of frep() (any SDF solid brought over with .to_csg()) segfaults the
        # whole app: PythonSCAD's attribute lookup evaluates the field, and the process dies with
        # exit -11 and an empty stderr, so the render just looks like it built nothing.
        if name == "shape" or name.startswith("_"):
            raise AttributeError(name)
        try:
            be = object.__getattribute__(self, "backend")
        except AttributeError:
            be = "csg"
        _unsupported = _unsupported_feature(be, name)
        if _unsupported is not None:
            raise _unsupported

        # Realize first if it has attachments and the attribute is a native passthrough method!
        realized = self
        if name in _NATIVE_PASSTHROUGH and hasattr(self, "_attachments") and self._attachments:
            realized = self.realize()

        shape = object.__getattribute__(realized, "shape")
        attr = getattr(shape, name)
        if not callable(attr):
            return attr
        if name not in _NATIVE_PASSTHROUGH:
            raise AttributeError(
                f"{type(self).__name__!r} object has no attribute {name!r} (not in the native passthrough set)"
            )
        native_cls = type(shape)

        # a passthrough to a native method this wrapper does not model, so it takes whatever the
        # native one does; anything pybosl2 gives a signature to is a real method, not this path
        def _forward(*args: object, **kwargs: object) -> object:
            result = attr(*args, **kwargs)
            if isinstance(result, native_cls):
                return self._wrap(result)
            if isinstance(result, (list, tuple)) and result and all(isinstance(r, native_cls) for r in result):
                return type(result)(self._wrap(r) for r in result)
            return result

        _forward.__name__ = name
        return _forward

    def tag(self, name: AttachTag | str) -> Self:
        """Assign an attachment tag to this shape.

        This tag is used for boolean resolution in attachments.

        Args:
            name: The tag name or AttachTag enum.

        """
        out = self._wrap(self.shape)
        out.tag_name = str(name)
        return out

    def tag_this(self, name: AttachTag | str) -> Self:
        """Assign an attachment tag to this shape but not its children.

        Args:
            name: The tag name or AttachTag enum.

        """
        out = self._wrap(self.shape)
        out.tag_name = str(name)
        out._dont_propagate = True
        return out

    def diff(
        self,
        remove: AttachTag | str | Sequence[AttachTag | str] = AttachTag.REMOVE,
        keep: AttachTag | str | Sequence[AttachTag | str] = AttachTag.KEEP,
    ) -> Self:
        """Configure difference resolution tags for attachments.

        Args:
            remove: The tag(s) to subtract.
            keep: The tag(s) to preserve.

        """
        out = self._wrap(self.shape)
        rem_list = [str(r) for r in ([remove] if isinstance(remove, (str, AttachTag)) else remove)]
        keep_list = [str(k) for k in ([keep] if isinstance(keep, (str, AttachTag)) else keep)]
        out.diff_config = {"type": "diff", "remove": rem_list, "keep": keep_list}
        return out

    def intersect(
        self,
        intersect: AttachTag | str | Sequence[AttachTag | str] = AttachTag.INTERSECT,
        keep: AttachTag | str | Sequence[AttachTag | str] = AttachTag.KEEP,
    ) -> Self:
        """Configure intersection resolution tags for attachments.

        Args:
            intersect: The tag(s) to intersect.
            keep: The tag(s) to preserve.

        """
        out = self._wrap(self.shape)
        int_list = [str(i) for i in ([intersect] if isinstance(intersect, (str, AttachTag)) else intersect)]
        keep_list = [str(k) for k in ([keep] if isinstance(keep, (str, AttachTag)) else keep)]
        out.diff_config = {"type": "intersect", "intersect": int_list, "keep": keep_list}
        return out

    def realize(self) -> Self:
        """Evaluate the shape and its attachment tree.

        Returns:
            The resolved and flattened shape wrapper.

        """
        return self._realize_node(parent_tag="")

    def _realize_node(self, parent_tag: str) -> Self:
        """Recursively resolve this shape node and all its attachments.

        Args:
            parent_tag: Tag propagated from parent.

        """
        active_tag = self.tag_name if self.tag_name else parent_tag
        dont_prop = getattr(self, "_dont_propagate", False)
        child_parent_tag = parent_tag if dont_prop else active_tag

        realized_children = [att._realize_node(child_parent_tag) for att in self.attachments]

        if not realized_children:
            out = self._wrap(self.shape)
            out.attachments = []
            out.tag_name = active_tag
            return out

        cfg = self.diff_config
        if cfg is not None:
            if cfg["type"] == "diff":
                remove_tags = set(cfg["remove"])

                keeps = [self.shape]
                removes = []

                for child in realized_children:
                    c_tag = child.tag_name
                    if c_tag in remove_tags:
                        removes.append(child.shape)
                    else:
                        keeps.append(child.shape)

                keep_geom = keeps[0]
                for k in keeps[1:]:
                    keep_geom = keep_geom | k

                if removes:
                    remove_geom = removes[0]
                    for r in removes[1:]:
                        remove_geom = remove_geom | r
                    final_geom = keep_geom - remove_geom
                else:
                    final_geom = keep_geom

                out = self._wrap(final_geom)
                out.attachments = []
                out.tag_name = active_tag
                return out

            elif cfg["type"] == "intersect":
                intersect_tags = set(cfg["intersect"])
                keep_tags = set(cfg["keep"])

                intersects = []
                keeps = []
                remainings = [self.shape]

                for child in realized_children:
                    c_tag = child.tag_name
                    if c_tag in intersect_tags:
                        intersects.append(child.shape)
                    elif c_tag in keep_tags:
                        keeps.append(child.shape)
                    else:
                        remainings.append(child.shape)

                remaining_geom = remainings[0]
                for r in remainings[1:]:
                    remaining_geom = remaining_geom | r

                if intersects:
                    intersect_geom = intersects[0]
                    for i in intersects[1:]:
                        intersect_geom = intersect_geom | i
                    final_geom = remaining_geom & intersect_geom
                else:
                    final_geom = remaining_geom - remaining_geom

                for k in keeps:
                    final_geom = final_geom | k

                out = self._wrap(final_geom)
                out.attachments = []
                out.tag_name = active_tag
                return out

        final_geom = self.shape
        for child in realized_children:
            final_geom = final_geom | child.shape

        out = self._wrap(final_geom)
        out.attachments = []
        out.tag_name = active_tag
        return out


def diff(
    shape: BaseShape,
    remove: AttachTag | str | Sequence[AttachTag | str] = AttachTag.REMOVE,
    keep: AttachTag | str | Sequence[AttachTag | str] = AttachTag.KEEP,
) -> BaseShape:
    """Configure difference resolution tags for attachments.

    Args:
        shape: The parent shape.
        remove: The tag(s) to subtract.
        keep: The tag(s) to preserve.

    """
    return shape.diff(remove, keep)


def intersect(
    shape: BaseShape,
    intersect: AttachTag | str | Sequence[AttachTag | str] = AttachTag.INTERSECT,
    keep: AttachTag | str | Sequence[AttachTag | str] = AttachTag.KEEP,
) -> BaseShape:
    """Configure intersection resolution tags for attachments.

    Args:
        shape: The parent shape.
        intersect: The tag(s) to intersect.
        keep: The tag(s) to preserve.

    """
    return shape.intersect(intersect, keep)

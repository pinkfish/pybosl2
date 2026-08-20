# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# Backend selection for the dual CSG / SDF solid system (default: "csg").
#
# pybosl2 realizes solids through one of two backends:
#   * "csg" -- exact CSG via PythonSCAD's native primitives (the default; today's Bosl2Solid).
#   * "sdf" -- F-Rep / signed-distance via libfive.
#
# The active backend is a thread/async-safe context value (a contextvars.ContextVar) so it can be
# overridden for a block with ``use_backend("sdf")`` or changed globally with
# ``set_default_backend``. Shape constructors dispatch on :func:`current_backend`; operands of a
# boolean/transform must share a backend (see :class:`~pybosl2.exceptions.CrossBackendError`), and a
# call a backend cannot express raises :class:`~pybosl2.exceptions.UnsupportedByBackendError`.
#
# This module holds only the *selection* machinery and the shared :class:`Solid` /
# :class:`SolidBackend` contracts -- it imports neither native runtime, so it stays FFI-free.
#

from __future__ import annotations

import contextlib
import contextvars
import functools
from typing import TYPE_CHECKING, Any, Callable, Iterator, Protocol, Self, TypeVar, cast, runtime_checkable

from pybosl2.exceptions import Bosl2Error, UnsupportedByBackendError

_F = TypeVar("_F", bound=Callable[..., Any])

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from pybosl2.caps import CapSpec
    from pybosl2.path3d import Path3D


def given_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Just the arguments the caller actually gave.

    The backends take different parameter sets, so only what was asked for is forwarded through
    :meth:`SolidBackend.construct` -- a backend never sees an option it has no notion of, and
    each keeps its own defaults.
    """
    return {name: value for name, value in arguments.items() if value is not None}


__all__ = [
    "BackendName",
    "given_arguments",
    "backend_only",
    "builds_with",
    "current_backend",
    "set_default_backend",
    "use_backend",
    "register_backend",
    "get_backend",
    "known_backends",
    "check_operand_backend",
    "supports",
    "unsupported_feature",
    "Shape",
    "Solid",
    "SolidBackend",
]

# Features one backend has that the other cannot faithfully express. Calling one of these on the
# wrong backend raises UnsupportedByBackendError (see the wrappers' __getattr__) instead of a
# confusing AttributeError -- or, for the SDF backend, instead of meshing just to fail.
#
# These two lists are the single source of truth for what is exclusive (SPEC PAR-3), and every
# entry carries the reason it cannot cross over. An entry that becomes implementable is REMOVED,
# not left as an excuse -- and a name listed here must genuinely be absent from the other
# backend's class, or the refusal never fires (tests/test_backend_parity.py).
CSG_ONLY_FEATURES = frozenset(
    {  # BOSL2's attachment/anchor system: anchoring needs a shape's face and edge structure,
        # which a distance field does not retain -- there is nothing to anchor TO.
        "attach",
        "anchor_point",
        "reanchor",
        "position",
        "align",
        "reorient",
        "orient",
        "edge_mask",
        "edge_profile",
        "edge_profile_asym",
        "corner_profile",
        "face_profile",
        "tag",
        "tag_this",
        # the attachment system's own state -- same reason as the operations above
        "attachments",
        "diff_config",
        "tag_name",
        "diff",
        "intersect",
        "realize",
        # Both backends build 2-D shapes (Bosl2Shape2D / PyShape2D), but these two need a 2-D
        # shadow of a 3-D solid and an outline to fill -- neither is derivable in closed form from
        # a distance field. Meshing to answer them would hand back a CSG shape from an SDF one
        # (SPEC B-5), so they refuse and name `.to_csg()` as the explicit conversion.
        "projection",
        "fill",
    }
)
SDF_ONLY_FEATURES = frozenset(
    {  # implicit-surface edge treatments -- CSG rounds via rounding=/chamfer= params, not a method
        "round",
        "chamfer",
    }
)


def backend_only(backend: str, neutral: str | None = None) -> "Callable[[_F], _F]":
    """Decorate a backend's own constructor so it refuses when another backend is active.

    A constructor in ``pybosl2.shapes3d`` builds CSG geometry whatever is selected. Called inside
    a ``use_backend("sdf")`` block it used to hand back a shape that could not combine with the
    surrounding SDF geometry; now it says so (SPEC C-1, B-4, PLAN B-P1).

    Args:
        backend: The backend this constructor belongs to.
        neutral: Dotted path of the backend-neutral equivalent, named in the error's hint.

    Returns:
        A decorator that wraps the constructor with the guard.

    """

    def decorate(fn: "_F") -> "_F":
        @functools.wraps(fn)
        def guarded(*args: Any, **kwargs: Any) -> Any:
            active = current_backend()
            if active != backend:
                hint = (
                    f"{neutral} builds this on whichever backend is active."
                    if neutral
                    else f"it is the {backend!r} backend's own constructor."
                )
                raise UnsupportedByBackendError(
                    f"{fn.__module__}.{fn.__name__}",
                    active,
                    hint=f"{hint} To build it as {backend!r} geometry anyway, "
                    f'wrap the call in `with use_backend("{backend}")`.',
                )
            return fn(*args, **kwargs)

        return cast("_F", guarded)

    return decorate


def builds_with(backend: str) -> "Callable[[_F], _F]":
    """Decorate a backend's own implementation so it runs with that backend selected.

    The counterpart to :func:`backend_only`: where that one refuses, this one *establishes* the
    context. A CSG implementation detail (the CSG stroke, a CSG mask) legitimately builds CSG
    geometry no matter what the caller selected, so it declares that rather than tripping the
    guards on the constructors it calls.

    Args:
        backend: The backend to select for the duration of the call.

    Returns:
        A decorator that runs the function inside ``use_backend(backend)``.

    """

    def decorate(fn: "_F") -> "_F":
        @functools.wraps(fn)
        def scoped(*args: Any, **kwargs: Any) -> Any:
            with use_backend(backend):
                return fn(*args, **kwargs)

        return cast("_F", scoped)

    return decorate


def supports(backend: str, feature: str) -> bool:
    """Whether *backend* can do *feature*. Backend-exclusive features are False on the other side.

    everything else (the shared surface) is assumed supported.
    """
    if feature in CSG_ONLY_FEATURES:
        return backend == "csg"
    if feature in SDF_ONLY_FEATURES:
        return backend == "sdf"
    return True


def unsupported_feature(backend: str, name: str) -> "UnsupportedByBackendError | None":
    """Return the :class:`~pybosl2.exceptions.UnsupportedByBackendError` to raise if *name* is exclusive to the.

    OTHER backend, else ``None`` (so the caller can fall through to normal attribute handling).
    """
    from pybosl2.exceptions import UnsupportedByBackendError

    if backend == "sdf" and name in CSG_ONLY_FEATURES:
        hint = "attachment/anchoring is a CSG-backend feature; build it with the default (csg) backend."
        if name in ("projection", "fill"):
            hint = (
                f"{name}() needs a 2-D shadow of a solid, which is not derivable in closed form "
                "from a distance field -- both backends build 2-D shapes otherwise. Mesh it "
                f"explicitly with .to_csg().{name}(), or build the shape on the csg backend."
            )
        return UnsupportedByBackendError(name, "sdf", hint=hint)
    if backend == "csg" and name in SDF_ONLY_FEATURES:
        return UnsupportedByBackendError(
            name,
            "csg",
            hint=f"the csg backend has no implicit {name}(); use the rounding=/chamfer= "
            "parameters on cuboid()/cyl(), or build the shape under use_backend('sdf').",
        )
    return None


def check_operand_backend(self_backend: str, other: Any) -> None:
    """Raise :class:`~pybosl2.exceptions.CrossBackendError` if *other* is a Solid on a different backend.

    Called by every boolean operator so ``csg_solid | sdf_solid`` fails loudly with conversion
    guidance instead of producing nonsense. A raw native shape (no ``backend`` attribute) is treated
    as same-backend so existing native interop keeps working.
    """
    other_backend = getattr(other, "backend", None)
    if other_backend is not None and other_backend != self_backend:
        from pybosl2.exceptions import CrossBackendError

        raise CrossBackendError(self_backend, other_backend)


BackendName = str  # "csg" | "sdf" (kept a plain str so third-party backends can register too)

_KNOWN: set[str] = {"csg", "sdf"}
_default: str = "csg"
_registry: dict[str, "SolidBackend"] = {}
# None => fall through to the module-level default (which set_default_backend can change).
_current: contextvars.ContextVar[str | None] = contextvars.ContextVar("bosl2_backend", default=None)


def _validate(name: str) -> None:
    if name not in _KNOWN:
        raise Bosl2Error(f"unknown backend {name!r}; known backends: {sorted(_KNOWN)}")


def known_backends() -> tuple[str, ...]:
    """Return the registered backend names."""
    return tuple(sorted(_KNOWN))


def current_backend() -> str:
    """Return the backend active in this context (default ``"csg"``)."""
    return _current.get() or _default


def set_default_backend(name: str) -> None:
    """Change the process-wide default backend (outside any :func:`use_backend` block)."""
    _validate(name)
    global _default
    _default = name


@contextlib.contextmanager
def use_backend(name: str) -> Iterator[None]:
    """Make *name* the active backend for the duration of the ``with`` block (nestable, thread-safe)."""
    _validate(name)
    token = _current.set(name)
    try:
        yield
    finally:
        _current.reset(token)


def register_backend(name: str, impl: "SolidBackend") -> None:
    """Register a :class:`SolidBackend` implementation under *name* (also makes it a known backend)."""
    _KNOWN.add(name)
    _registry[name] = impl


def get_backend(name: str | None = None) -> "SolidBackend":
    """Return the :class:`SolidBackend` implementation for *name* (default: the active backend).

    The two built-in backends register themselves on first use (importing them is FFI-free -- the
    native runtime is only touched when geometry is actually realized).
    """
    key = name or current_backend()
    if key not in _registry:
        if key == "csg":
            import pybosl2._csg
        elif key == "sdf":
            import pybosl2.sdf  # noqa: F401  -- registers the SDF backend on import
    try:
        return _registry[key]
    except KeyError:
        raise Bosl2Error(
            f"backend {key!r} is selected but not registered/available "
            f"(is its native dependency installed?). Registered: {sorted(_registry)}"
        ) from None


@runtime_checkable
class Shape(Protocol):
    """Everything true of every shape, in either dimension, on either backend.

    A 2-D outline and a 3-D solid are built, combined, moved and measured identically, so that
    surface is declared once here and the dimensional protocols extend it (SPEC C-15). Members
    return ``Self``, so an operation keeps the kind of shape it was given and a boolean between
    the two dimensions is a static error rather than a runtime surprise (SPEC C-16).

    A shape carries a ``backend`` tag naming the backend that *produced* it; combining shapes from
    two backends raises :class:`~pybosl2.exceptions.CrossBackendError`.
    """

    backend: str

    def __or__(self, other: Self) -> Self: ...
    def __and__(self, other: Self) -> Self: ...
    def __sub__(self, other: Self) -> Self: ...
    def translate(self, v: "Sequence[float]") -> Self: ...
    def scale(self, v: "Sequence[float]") -> Self: ...
    def mirror(self, v: "Sequence[float]") -> Self: ...
    def bounds(self) -> "tuple[list[float], list[float]]": ...
    def show(self) -> Any: ...


@runtime_checkable
class Solid(Shape, Protocol):
    """A 3-D shape: :class:`Shape` plus what only three dimensions can do.

    ``.to_csg()`` / ``.to_sdf()`` convert between the backends; ``projection()`` is the one way
    down to 2-D (SPEC C-17).
    """

    def rotate(self, a: "float | Sequence[float] | None" = None, v: "Sequence[float] | None" = None) -> "Solid": ...


class SolidBackend(Protocol):
    """The small 'realize' surface a backend implements: the primitives shape constructors build on.

    Both backends expose the same names; each realizes them in its own idiom (the CSG backend calls
    PythonSCAD's ``cube``/``cylinder``/...; the SDF backend builds the equivalent libfive fields).
    Shape functions in the shared layer call these, not the native ops directly.
    """

    name: str

    def constructor(self, shape: str, /) -> "Callable[..., Solid]":
        """Return the callable this backend would use to build *shape*.

        Exposed so the defaults a caller did not supply stay inspectable rather than silent --
        :func:`pybosl2.solid.effective_defaults` reads them straight off this signature.

        Raises:
            ValueError: If this backend has no constructor by that name.

        """
        ...

    def construct(self, shape: str, arguments: Mapping[str, Any]) -> Solid:
        """Build the named shape constructor (e.g. ``"torus"``) in this backend's idiom.

        *arguments* holds just the parameters the caller gave, so a backend never has to accept
        an option it has no notion of (see :func:`pybosl2.solid._given`).
        """
        ...

    def polyhedron(self, points: Any, faces: Any = None, convexity: int | None = None) -> Solid: ...
    def union(self, solids: Any) -> Solid: ...
    def difference(self, solids: Any) -> Solid: ...
    def intersection(self, solids: Any) -> Solid: ...

    def linear_extrude(self, paths: Any, height: float, arguments: Mapping[str, Any]) -> Solid:
        """Extrude 2-D outlines (a list of ``[[x, y], ...]`` paths) *height* along +Z.

        This is the one 2-D -> 3-D entry point both backends can express, and it takes raw point
        paths rather than a 2-D shape object deliberately: 2-D *geometry* is a CSG-only notion
        (:class:`~pybosl2.shapes2d.Bosl2Shape2D`), whereas a path is backend-neutral. It is what
        :meth:`pybosl2.paths.Path2D.linear_extrude` dispatches through, so the same call yields a
        Bosl2Solid on the CSG backend and a PyShape on the SDF one.
        """
        ...

    def stroke(
        self,
        path: Path3D,
        width: float = 1,
        closed: bool | None = None,
        endcap1: CapSpec | None = None,
        endcap2: CapSpec | None = None,
    ) -> Solid:
        """3-D tube along *path*."""
        ...

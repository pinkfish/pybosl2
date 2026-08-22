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
import inspect
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
    "for_backend",
    "refuse_unhonoured",
    "TESSELLATION_PARAMETERS",
    "backend_only",
    "builds_with",
    "csg_part",
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
    {  # BOSL2's attachment system, the half of it that holds CHILDREN: these record a placed
        # child and combine it later, which is native-tree work the SDF backend has no equivalent
        # for yet (TASKS T14 phase 5a, second half).
        #
        # The anchor arithmetic that used to be listed here -- anchor_point, reanchor, reorient,
        # orient -- is not exclusive and no longer listed. The reason recorded for it was wrong:
        # it said anchoring "needs a shape's face and edge structure, which a distance field does
        # not retain". It needs the bounding box, which an SDF shape knows exactly. Both backends
        # now share one implementation (pybosl2/_anchoring.py).
        "attach",
        "position",
        "align",
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


@functools.lru_cache(maxsize=None)
def accepted_parameters(constructor: "Callable[..., Any]") -> frozenset[str]:
    """Return the parameter names *constructor* declares (cached per callable).

    The façade owns the default for every argument both backends understand (SPEC B-3) and always
    forwards it, so each backend filters by what it actually declares rather than relying on the
    caller to have omitted the ones it does not know (PLAN F-P2).
    """
    try:
        parameters = inspect.signature(constructor).parameters
    except (TypeError, ValueError):  # pragma: no cover - signature-less callables
        return frozenset()
    if any(p.kind is p.VAR_KEYWORD for p in parameters.values()):
        return frozenset(parameters) | {"**"}
    return frozenset(parameters)


def for_backend(constructor: "Callable[..., Any]", arguments: "Mapping[str, Any]") -> dict[str, Any]:
    """Return just the *arguments* this constructor can take.

    Args:
        constructor: The backend constructor about to be called.
        arguments: Everything the façade declared, defaults included.

    Returns:
        The subset the constructor declares; a constructor taking ``**kwargs`` gets them all.

    """
    accepted = accepted_parameters(constructor)
    if "**" in accepted:
        return dict(arguments)
    return {name: value for name, value in arguments.items() if name in accepted}


#: Parameters that describe *tessellation*, not shape. A backend with no facets is not missing a
#: feature when it cannot honour these, so they are accepted and ignored rather than refused
#: (SPEC B-9); `effective_defaults()` reports what each backend actually did with them.
#:
#: `realign` is here because it rotates a shape by half a *facet*, which means nothing on a smooth
#: field -- and where it does mean something (`regular_prism`, whose sides are exact on either
#: backend) the SDF constructor declares it, so it is honoured rather than reaching this list.
#: `circumscribe` is deliberately NOT here: on `regular_prism` it decides whether the polygon
#: encloses the circle or is inscribed in it, which is real geometry, and silently ignoring it
#: would be exactly the failure B-9 exists to stop.
TESSELLATION_PARAMETERS = frozenset({"fn", "fa", "fs", "res", "realign"})


@functools.cache
def _facade_defaults(shape: str) -> "Mapping[str, Any]":
    """Return the façade constructor's own default for each parameter, or ``{}`` if it has none."""
    from pybosl2 import solid as facade

    function = getattr(facade, shape, None)
    if not callable(function):  # pragma: no cover - every shape the backends build has a façade
        return {}
    try:
        parameters = inspect.signature(function).parameters
    except (TypeError, ValueError):  # pragma: no cover - signature-less callables
        return {}
    return {name: p.default for name, p in parameters.items() if p.default is not inspect.Parameter.empty}


def refuse_unhonoured(
    shape: str,
    arguments: "Mapping[str, Any]",
    constructor: "Callable[..., Any]",
    backend: str,
    own_names: "Mapping[str, str] | None" = None,
) -> None:
    """Raise if the caller asked for something this backend's constructor cannot take (SPEC B-9).

    The façade forwards its own defaults as well as the caller's arguments, and filtering those
    down to what a backend declares is right (B-3) -- but only for the defaults. Dropping a value
    the caller actually asked for is not: ``regular_prism(radius1=8, radius2=4)`` must not quietly
    come back a straight prism on a backend with no taper.

    A value counts as asked-for when it differs from the façade's own default for that parameter,
    which is what distinguishes it from a default being forwarded on the caller's behalf.

    Args:
        shape: The façade shape name, used to find the façade's defaults.
        arguments: What the façade is forwarding, in façade spelling.
        constructor: The backend constructor about to be called.
        backend: The active backend's name, for the message.
        own_names: This backend's spelling for any façade parameter it names differently.

    Raises:
        UnsupportedByBackendError: naming every parameter the backend cannot honour.

    """
    accepted = accepted_parameters(constructor)
    if "**" in accepted:
        return
    renamed = own_names or {}
    defaults = _facade_defaults(shape)
    unhonoured = sorted(
        name
        for name, value in arguments.items()
        if renamed.get(name, name) not in accepted
        and name not in TESSELLATION_PARAMETERS
        and not _is_default(defaults, name, value)
    )
    if unhonoured:
        raise UnsupportedByBackendError(
            f"{shape}({', '.join(f'{name}=' for name in unhonoured)})",
            backend,
            hint=(
                f"the {backend} backend's {shape}() has no "
                f"{' or '.join(repr(name) for name in unhonoured)}. Build it inside "
                '`with use_backend("csg")` and bring the result over with .to_csg(), or leave the '
                "argument out."
            ),
        )


def _is_default(defaults: "Mapping[str, Any]", name: str, value: Any) -> bool:
    """Report whether *value* is the façade's own default for *name* -- i.e. nobody asked for it."""
    if name not in defaults:
        return False
    default = defaults[name]
    try:
        return bool(default == value)
    except Exception:  # pragma: no cover - defensive: exotic __eq__ on a default
        return default is value


def csg_part(getter: "_F") -> "_F":
    """Guard a part's ``shape`` property: the parts library builds exact CSG geometry.

    Every part is composed from CSG primitives, meshes and native operations, so none of them has
    an SDF form yet. Rather than letting whichever internal path happens to be unguarded hand back
    a CSG solid inside a ``use_backend("sdf")`` block -- which cannot combine with the surrounding
    SDF geometry, and only fails much later -- the part says so at the point of use (SPEC S-46a).

    Args:
        getter: The property getter to guard.

    Returns:
        The getter, wrapped so it refuses on any backend but ``"csg"``.

    """

    @functools.wraps(getter)
    def guarded(self: Any) -> Any:
        active = current_backend()
        if active != "csg":
            raise UnsupportedByBackendError(
                f"{type(self).__name__}.shape",
                active,
                hint="the parts library builds exact CSG geometry, so build the part inside "
                '`with use_backend("csg")` and bring the surrounding SDF work over with '
                ".to_csg() to combine them.",
            )
        return getter(self)

    return cast("_F", guarded)


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

    def with_nominal_size(self, size: "Sequence[float]", anchor: Any = None) -> Self:
        """Return this shape carrying *size* as its nominal anchor box (SPEC S-2a).

        Backend-neutral, so a shape can name the frame it anchors to without reaching for a native
        handle. `bounds()` keeps reporting the geometry.
        """
        ...

    @property
    def nominal_size(self) -> "list[float] | None":
        """The nominal anchor box, or None if none was attached (SPEC S-2a)."""
        ...


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

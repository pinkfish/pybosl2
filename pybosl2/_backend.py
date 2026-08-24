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
    import os
    from collections.abc import Mapping, Sequence
    from pathlib import Path as FilePath

    from pybosl2.bounds import Bounds2D, Bounds3D
    from pybosl2.caps import CapSpec
    from pybosl2.path3d import Path3D
    from pybosl2.vnf import VNF


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
        # the named treatments (SPEC S-26b) are the same masks by a friendlier name, so they are
        # exclusive for exactly the same reason
        "round_edges",
        "chamfer_edges",
        "cove_edges",
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
        and not _is_no_op(value)
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


def _is_no_op(value: Any) -> bool:
    """Report whether *value* asks for nothing, so dropping it changes no geometry.

    An explicit zero rounding or chamfer is "no rounding", not a request a backend has to honour --
    and parts pass one routinely, normalising `None` to `0` before forwarding. Refusing those was a
    false alarm: `RingHook` was turned away from the SDF backend over `prismoid(rounding=0)`.
    Matches the same no-op set the SDF `linear_extrude` has always used for `twist`/`scale`.
    """
    return value is None or value is False or (isinstance(value, (int, float)) and float(value) == 0.0)


def _is_default(defaults: "Mapping[str, Any]", name: str, value: Any) -> bool:
    """Report whether *value* is the façade's own default for *name* -- i.e. nobody asked for it."""
    if name not in defaults:
        return False
    default = defaults[name]
    try:
        return bool(default == value)
    except Exception:  # pragma: no cover - defensive: exotic __eq__ on a default
        return default is value


def csg_part(reason: str) -> "Callable[[_F], _F]":
    """Guard a part's ``shape`` property: this part needs CSG-only machinery.

    Most of the parts library is composed from primitives both backends have, and those parts are
    written against the façade and build on either (TASKS T14). The ones that keep this guard need
    something the SDF backend has no form for -- a 2-D profile extruded or revolved, a sweep along
    a path, a mesh handed over vertex by vertex. Rather than letting whichever internal path
    happens to be unguarded hand back a CSG solid inside a ``use_backend("sdf")`` block -- which
    cannot combine with the surrounding SDF geometry, and only fails much later -- the part says so
    at the point of use, and says *what* it needs (SPEC S-46a, E-4).

    Args:
        reason: What this part does that the SDF backend cannot, as a clause completing
            "<Part>.shape needs the csg backend because ...".

    Returns:
        A decorator that wraps the getter so it refuses on any backend but ``"csg"``.

    """

    def decorate(getter: "_F") -> "_F":
        @functools.wraps(getter)
        def guarded(self: Any) -> Any:
            active = current_backend()
            if active != "csg":
                raise UnsupportedByBackendError(
                    f"{type(self).__name__}.shape",
                    active,
                    hint=(
                        f"{type(self).__name__} {reason}. Build it inside "
                        '`with use_backend("csg")` and bring the surrounding SDF work over with '
                        ".to_csg() to combine them."
                    ),
                )
            return getter(self)

        return cast("_F", guarded)

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


def check_operand_backend(self_backend: str, other: Any, self_dimensions: int | None = None) -> None:
    """Raise if *other* cannot be combined with a shape on *self_backend* in *self_dimensions*.

    Called by every boolean operator, so the two ways an operand can be wrong both fail loudly with
    guidance instead of producing nonsense:

    * a different **backend** raises :class:`~pybosl2.exceptions.CrossBackendError` naming the
      conversion (SPEC E-3);
    * a different **dimension** raises :class:`~pybosl2.exceptions.Bosl2ValueError` naming the
      extrusion or projection that crosses deliberately (SPEC C-4, C-16, E-7). The static error is
      the first line of defence -- ``Flat`` and ``Solid`` are distinct protocols, so mypy rejects
      ``flat - solid`` outright -- but the native layer answers a mixed boolean with a warning on
      stdout and the unchanged left operand, which is a silent wrong answer for the many callers
      who drive a CAD app without a type checker.

    A raw native shape (no ``backend``/``dimensions`` attribute) is treated as compatible, so
    existing native interop keeps working.

    Args:
        self_backend: backend tag of the left operand.
        other: the right operand, of any type.
        self_dimensions: dimension count of the left operand; ``None`` skips the dimension check.

    Raises:
        CrossBackendError: If *other* was built by a different backend.
        Bosl2ValueError: If *other* has a different number of dimensions.

    """
    other_backend = getattr(other, "backend", None)
    if other_backend is not None and other_backend != self_backend:
        from pybosl2.exceptions import CrossBackendError

        raise CrossBackendError(self_backend, other_backend)

    other_dimensions = getattr(other, "dimensions", None)
    if self_dimensions is not None and other_dimensions is not None and other_dimensions != self_dimensions:
        from pybosl2.exceptions import Bosl2ValueError

        flat_first = self_dimensions == 2
        raise Bosl2ValueError(
            f"cannot combine a {self_dimensions}-D shape with a {other_dimensions}-D one -- a boolean "
            f"needs both operands in the same dimension. Cross deliberately first: "
            + (
                "extrude the 2-D shape with `.linear_extrude(height=...)` or `.rotate_extrude()`, "
                "or flatten the solid with `.projection()`."
                if flat_first
                else "flatten the solid with `.projection()`, or extrude the 2-D shape with "
                "`.linear_extrude(height=...)`."
            )
        )


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
    def bounds(self) -> "Bounds2D | Bounds3D":
        """Return the axis-aligned bounding box (SPEC S-2b).

        The union is fixed by which protocol the caller holds, not by an argument, so it is not
        the flag-selected union PLAN T-6d forbids: `Flat` narrows it to `Bounds2D` and `Solid` to
        `Bounds3D`.
        """
        ...

    def show(self) -> Any: ...

    # --- SPEC C-20: the contract is the whole object -----------------------------------------
    # These were reachable only by accident of the concrete class, so typed user code -- a caller
    # following this project's own advice in PLAN §2 -- could not call the library's headline
    # composition features. Parameters are `Any` where the two backends spell the same idea
    # differently; that is the bounded exception T-6c allows, not a licence to stop typing.

    # Colour and the preview modifiers ride on any shape (SPEC C-19, S-37, S-38).
    def color(self, c: Any = None, alpha: float | None = None) -> Self: ...
    def recolor(self, c: Any = None, alpha: float | None = None) -> Self: ...
    def color_this(self, c: Any = None, alpha: float | None = None) -> Self: ...
    def hsl(self, h: float, s: float = 1.0, lightness: float = 0.5, alpha: float = 1.0) -> Self: ...
    def hsv(self, h: float, s: float = 1.0, v: float = 1.0, alpha: float = 1.0) -> Self: ...
    def highlight(self) -> Self: ...
    def ghost(self) -> Self: ...

    # Attachment and tagging (SPEC C-12): part of the core object model, so part of the contract.
    # The SDF backend refuses each of these explicitly by name (C-13) rather than lacking them --
    # which is both what C-13 asks for and what keeps `isinstance(sdf_solid, Solid)` true. A caller
    # who needs to know *before* calling asks the backend, not the shape: the authority is
    # `pybosl2.sdf.CSG_ONLY_FEATURES` (PAR-3), not a structural check that would pass on the very
    # methods whose job is to refuse.
    def attach(self, *args: Any, **kwargs: Any) -> Self: ...
    def position(self, *args: Any, **kwargs: Any) -> Self: ...
    def align(self, *args: Any, **kwargs: Any) -> Self: ...
    def tag(self, *args: Any, **kwargs: Any) -> Self: ...
    def tag_this(self, *args: Any, **kwargs: Any) -> Self: ...
    def diff(self, *args: Any, **kwargs: Any) -> Self: ...
    def intersect(self, *args: Any, **kwargs: Any) -> Self: ...

    # Distribution: an operation on "any shape", not on solids specifically (SPEC C-19, S-31).
    # These return a *list* of copies, not one shape -- `xcopies(3)` is three shapes, and the
    # caller unions them or distributes them further.
    def line_copies(self, *args: Any, **kwargs: Any) -> list[Self]: ...
    def xcopies(self, *args: Any, **kwargs: Any) -> list[Self]: ...
    def ycopies(self, *args: Any, **kwargs: Any) -> list[Self]: ...
    def zcopies(self, *args: Any, **kwargs: Any) -> list[Self]: ...
    def grid_copies(self, *args: Any, **kwargs: Any) -> list[Self]: ...
    def rot_copies(self, *args: Any, **kwargs: Any) -> list[Self]: ...
    def xrot_copies(self, *args: Any, **kwargs: Any) -> list[Self]: ...
    def yrot_copies(self, *args: Any, **kwargs: Any) -> list[Self]: ...
    def zrot_copies(self, *args: Any, **kwargs: Any) -> list[Self]: ...
    def arc_copies(self, *args: Any, **kwargs: Any) -> list[Self]: ...
    def sphere_copies(self, *args: Any, **kwargs: Any) -> list[Self]: ...
    def path_copies(self, *args: Any, **kwargs: Any) -> list[Self]: ...
    def mirror_copy(self, *args: Any, **kwargs: Any) -> list[Self]: ...
    def xflip_copy(self, *args: Any, **kwargs: Any) -> list[Self]: ...
    def yflip_copy(self, *args: Any, **kwargs: Any) -> list[Self]: ...
    def zflip_copy(self, *args: Any, **kwargs: Any) -> list[Self]: ...
    # `distribute_on_path` places copies and unions them, so it is one shape, not a list.
    def distribute_on_path(self, *args: Any, **kwargs: Any) -> Self: ...

    # Transforms that both dimensions honour (SPEC C-22): a flip and a Z-rotation are not
    # three-dimensional ideas, and `spin` living only on Flat was historical.
    def multmatrix(self, m: Any) -> Self: ...
    def rotate(self, *args: Any, **kwargs: Any) -> Self: ...
    def minkowski(self, *others: Any) -> Self: ...

    # Directional moves within the plane both dimensions share.
    def left(self, x: float) -> Self: ...
    def right(self, x: float) -> Self: ...
    def forward(self, y: float) -> Self: ...
    def back(self, y: float) -> Self: ...

    # Anchoring arithmetic, which needs only a box (SPEC C-10).
    def anchor_point(self, anchor: Any, bbox: Any = None) -> list[float]: ...
    def reanchor(self, anchor: Any, bbox: Any = None) -> Self: ...

    # The nominal anchor box a shape was designed around (SPEC S-2a).
    def with_nominal_size(self, size: "Sequence[float]", anchor: Any = None) -> Self:
        """Return this shape carrying *size* as its nominal anchor box (SPEC S-2a).

        Backend-neutral, so a shape can name the frame it anchors to without reaching for a native
        handle. `bounds()` keeps reporting the geometry.
        """
        ...

    @property
    def size(self) -> "list[float] | None":
        """Return the nominal anchor box, or None if this shape never had one (SPEC S-2a).

        This is the box ``anchor=`` is measured against -- the shape the geometry is *designed*
        around -- and it is not required to equal ``bounds()``, which reports the geometry itself.
        ``nominal_size`` was a second name for exactly this and has been removed (SPEC C-21).
        """
        ...


@runtime_checkable
class Solid(Shape, Protocol):
    """A 3-D shape: :class:`Shape` plus what only three dimensions can do.

    ``.to_csg()`` / ``.to_sdf()`` convert between the backends; ``projection()`` is the one way
    down to 2-D (SPEC C-17).
    """

    def bounds(self) -> "Bounds3D":
        """Return the 3-D axis-aligned bounding box (SPEC S-2b)."""
        ...

    def vnf(self) -> "VNF":
        """Return this solid as a mesh (SPEC C-8, S-19a).

        A method rather than a property because it does real work -- meshing a field, or crossing
        the FFI for a native tessellation -- and because `isinstance` against a runtime-checkable
        Protocol calls `hasattr` on every declared member, which *evaluates* a property
        (PLAN T-6e). As a property this meshed an SDF field on every `isinstance(shape, Solid)`
        and, where no mesher was available, raised out of the check.
        """
        ...

    def export(
        self, path: "str | os.PathLike[str]", *, file_format: str | None = None, check: bool = True
    ) -> "FilePath":
        """Write this solid to a mesh file (SPEC S-53)."""
        ...

    def rotate(self, a: "float | Sequence[float] | None" = None, v: "Sequence[float] | None" = None) -> "Solid": ...

    # Directional moves. Both backends' 3-D shapes have had these all along; they were missing
    # from the contract, so code written against `Solid` -- a part being made backend-neutral,
    # above all -- could not use them without the checker objecting (TASKS T14 phase 3).
    def up(self, z: float) -> Self: ...
    def down(self, z: float) -> Self: ...
    def left(self, x: float) -> Self: ...
    def right(self, x: float) -> Self: ...
    def forward(self, y: float) -> Self: ...
    def back(self, y: float) -> Self: ...

    def multmatrix(self, m: Any) -> Self: ...
    def color(self, c: Any = None, alpha: float | None = None) -> Self: ...
    # `**kwargs` because the SDF hull takes sampling controls (`directions`, `res`) the CSG
    # one has no notion of -- the caller's view is "hull these", and the extras are backend
    # detail (PLAN T-6c).
    def hull(self, *others: Any, **kwargs: Any) -> Self: ...

    # Partitioning. Both backends implement the whole family; it was simply never declared.
    # The parameters are `Any` because the two spell their accepted forms differently (a list on
    # one, a Sequence on the other) while accepting the same values.
    # The three shared parameters only. The CSG side also takes `cut_path`/`cut_angle`/`offset`
    # for a profiled cut, which the SDF side has no notion of -- a PAR-4 divergence like
    # `partition`'s, recorded in SPEC §12.2 rather than smoothed over with `**kwargs` (which would
    # require both implementations to accept arbitrary keywords, and neither does).
    def half_of(self, v: Any = ..., center: Any = ..., s: float | None = None) -> Self: ...
    def left_half(self, x: float = 0, s: float | None = None) -> Self: ...
    def right_half(self, x: float = 0, s: float | None = None) -> Self: ...
    def front_half(self, y: float = 0, s: float | None = None) -> Self: ...
    def back_half(self, y: float = 0, s: float | None = None) -> Self: ...
    def top_half(self, z: float = 0, s: float | None = None) -> Self: ...
    def bottom_half(self, z: float = 0, s: float | None = None) -> Self: ...

    # --- SPEC C-20, the genuinely three-dimensional half ------------------------------------
    # `partition` splits, so it returns the pieces rather than one shape -- but the two backends
    # disagree on the container: the CSG one hands back `list[CsgSolid]` and the SDF one
    # `tuple[SdfSolid, SdfSolid]`. That is a PAR-4 divergence this contract work surfaced, not a
    # difference a caller should have to know about; `Any` holds the line until the two agree
    # (tracked in SPEC §12.2).
    def partition(self, *args: Any, **kwargs: Any) -> Any: ...
    # Edge, corner and face treatments (SPEC S-26, S-27) and the one way down to 2-D (C-17).
    # As above: the SDF backend refuses each by name.
    def edge_mask(self, *args: Any, **kwargs: Any) -> Self: ...
    def edge_profile(self, *args: Any, **kwargs: Any) -> Self: ...
    def edge_profile_asym(self, *args: Any, **kwargs: Any) -> Self: ...
    def corner_profile(self, *args: Any, **kwargs: Any) -> Self: ...
    def face_profile(self, *args: Any, **kwargs: Any) -> Self: ...

    # The named edge treatments (SPEC S-26b): `round_edges`/`chamfer_edges`/`cove_edges` are the
    # spellings a caller reaches for, so they belong on the contract like anything else (C-20).
    def round_edges(self, *args: Any, **kwargs: Any) -> Self: ...
    def chamfer_edges(self, *args: Any, **kwargs: Any) -> Self: ...
    def cove_edges(self, *args: Any, **kwargs: Any) -> Self: ...
    def projection(self, cut: bool = False) -> Any: ...
    def offset3d(self, *args: Any, **kwargs: Any) -> Self: ...
    def round3d(self, *args: Any, **kwargs: Any) -> Self: ...
    def wrap(self, radius: float, fn: int | None = None) -> Self: ...
    def oversample(self, *args: Any, **kwargs: Any) -> Self: ...
    def repair(self, *args: Any, **kwargs: Any) -> Self: ...
    def chain_hull(self, *args: Any, **kwargs: Any) -> Self: ...
    def minkowski_difference(self, *args: Any, **kwargs: Any) -> Self: ...
    def to_csg(self, *args: Any, **kwargs: Any) -> Any: ...
    def to_sdf(self, *args: Any, **kwargs: Any) -> Any: ...

    def anchor_point(
        self,
        anchor: Any,
        bbox: "Sequence[Sequence[float]] | None" = None,
    ) -> list[float]: ...
    def reanchor(self, anchor: Any, bbox: "Sequence[Sequence[float]] | None" = None) -> Self: ...
    def reorient(
        self,
        anchor: Any = ...,
        spin: float = 0,
        orient: Any = ...,
        bbox: "Sequence[Sequence[float]] | None" = None,
    ) -> Self: ...
    def orient(
        self,
        direction: Any = ...,
        spin: float = 0,
        bbox: "Sequence[Sequence[float]] | None" = None,
    ) -> Self: ...


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

    def rotate_extrude(self, paths: Any, angle: float, arguments: Mapping[str, Any]) -> Solid:
        """Revolve 2-D outlines about the Z axis.

        The second 2-D -> 3-D entry point both backends can express, and the one that suits a
        distance field best: a surface of revolution's field is the profile's own field read at
        ``(hypot(x, y), z)``, so the SDF backend needs no meshing and no approximation for it.
        Like :meth:`linear_extrude` it takes raw point paths rather than a 2-D shape object,
        because 2-D *geometry* is a CSG notion while a path is backend-neutral.
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

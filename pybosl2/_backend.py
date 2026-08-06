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
from typing import TYPE_CHECKING, Any, Iterator, Protocol, runtime_checkable

from pybosl2.exceptions import Bosl2Error, UnsupportedByBackendError

if TYPE_CHECKING:
    from pybosl2.caps import CapSpec
    from pybosl2.path3d import Path3D

__all__ = [
    "BackendName",
    "current_backend",
    "set_default_backend",
    "use_backend",
    "register_backend",
    "get_backend",
    "known_backends",
    "check_operand_backend",
    "supports",
    "unsupported_feature",
    "Solid",
    "SolidBackend",
]

# Features one backend has that the other cannot faithfully express. Calling one of these on the
# wrong backend raises UnsupportedByBackendError (see the wrappers' __getattr__) instead of a confusing
# AttributeError -- or, for the SDF backend, instead of meshing just to fail.
CSG_ONLY_FEATURES = frozenset(
    {  # BOSL2's attachment / anchor system -- no SDF equivalent
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
        "diff",
        "intersect",
        "realize",
        # 2-D geometry: only the CSG backend has a 2-D shape object (Bosl2Shape2D). An SDF is a
        # field over 3-space, with no 2-D shadow and no outline to fill.
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


def supports(backend: str, feature: str) -> bool:
    """Whether *backend* can do *feature*. Backend-exclusive features are False on the other side;
    everything else (the shared surface) is assumed supported.
    """
    if feature in CSG_ONLY_FEATURES:
        return backend == "csg"
    if feature in SDF_ONLY_FEATURES:
        return backend == "sdf"
    return True


def unsupported_feature(backend: str, name: str) -> "UnsupportedByBackendError | None":
    """Return the :class:`~pybosl2.exceptions.UnsupportedByBackendError` to raise if *name* is exclusive to the
    OTHER backend, else ``None`` (so the caller can fall through to normal attribute handling).
    """
    from pybosl2.exceptions import UnsupportedByBackendError

    if backend == "sdf" and name in CSG_ONLY_FEATURES:
        hint = "attachment/anchoring is a CSG-backend feature; build it with the default (csg) backend."
        if name in ("projection", "fill"):
            hint = (
                f"{name}() produces or consumes 2-D geometry, which only the csg backend has "
                "(pybosl2.shapes2d.Bosl2Shape2D). Convert first with .to_csg(), or build the shape "
                "on the default (csg) backend."
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
            import pybosl2._sdf  # noqa: F401  -- registers the SDF backend on import
    try:
        return _registry[key]
    except KeyError:
        raise Bosl2Error(
            f"backend {key!r} is selected but not registered/available "
            f"(is its native dependency installed?). Registered: {sorted(_registry)}"
        ) from None


@runtime_checkable
class Solid(Protocol):
    """The common solid contract both backend wrappers satisfy.

    A ``Solid`` carries a ``backend`` tag; booleans/transforms return a ``Solid`` on the *same*
    backend, and combining solids from two backends raises
    :class:`~pybosl2.exceptions.CrossBackendError`. ``.to_csg()`` / ``.to_sdf()`` convert between them.
    """

    backend: str

    def __or__(self, other: "Solid") -> "Solid": ...
    def __and__(self, other: "Solid") -> "Solid": ...
    def __sub__(self, other: "Solid") -> "Solid": ...
    def translate(self, v: Any) -> "Solid": ...
    def rotate(self, *args: Any, **kwargs: Any) -> "Solid": ...
    def scale(self, v: Any) -> "Solid": ...
    def mirror(self, v: Any) -> "Solid": ...
    def bounds(self) -> Any: ...


class SolidBackend(Protocol):
    """The small 'realize' surface a backend implements: the primitives shape constructors build on.

    Both backends expose the same names; each realizes them in its own idiom (the CSG backend calls
    PythonSCAD's ``cube``/``cylinder``/...; the SDF backend builds the equivalent libfive fields).
    Shape functions in the shared layer call these, not the native ops directly.
    """

    name: str

    def construct(self, shape: str, *args: Any, **kwargs: Any) -> Solid:
        """Build the named shape constructor (e.g. ``"torus"``) in this backend's idiom."""
        ...

    def polyhedron(self, *args: Any, **kwargs: Any) -> Solid: ...
    def union(self, solids: Any) -> Solid: ...
    def difference(self, solids: Any) -> Solid: ...
    def intersection(self, solids: Any) -> Solid: ...

    def linear_extrude(self, paths: Any, height: float, **kwargs: Any) -> Solid:
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
        **kwargs: Any,
    ) -> Solid:
        """3-D tube along *path*."""
        ...

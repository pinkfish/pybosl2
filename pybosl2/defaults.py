# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/defaults.py
#    Ambient resolution defaults -- the smoothness a shape gets when the caller says nothing.
#
#    Curve resolution is never a required argument in pybosl2 (SPEC.md R-2): every constructor
#    takes ``fn``/``fa``/``fs`` (CSG) or ``res`` (SDF) as ``None``, meaning "decide for me". This
#    module is what decides. Set it once for a block instead of threading the same numbers through
#    every call:
#
#        from pybosl2.defaults import use_defaults
#
#        with use_defaults(fn=64):
#            part = cyl(height=10, radius=4)   # 64-sided, without saying so
#
#    The active values live in a ``contextvars.ContextVar``, so a ``with`` block is thread- and
#    async-safe and nests, exactly like ``use_backend()``. Values are read at CONSTRUCTION time
#    (SPEC.md R-6) -- a shape's smoothness is fixed by where it was built, never re-resolved later.
#
#    Anything the caller passes explicitly always wins (SPEC.md P-6), and `fn=0` is how a single
#    call opts OUT of an ambient `fn` and back to fa/fs -- the meaning OpenSCAD's own $fn=0 has
#    (SPEC.md R-5):
#
#        with use_defaults(fn=64):
#            smooth = cyl(height=10, radius=4)            # 64 sides
#            adaptive = cyl(height=10, radius=4, fn=0)    # back to fa/fs
#
#    With nothing set anywhere, behaviour is unchanged from before this module existed:
#    OpenSCAD's own $fa=12 / $fs=2.
#
# FileSummary: Ambient curve-resolution defaults (fn/fa/fs/res) for a block or a session.
# DocCategory: Foundational
# FileGroup: BOSL2

"""Ambient curve-resolution defaults (fn/fa/fs/res) for a block or a session."""

from __future__ import annotations

import contextlib
import contextvars
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = [
    "Resolution",
    "current_defaults",
    "set_defaults",
    "reset_defaults",
    "use_defaults",
    "resolve_facets",
    "resolve_res",
]


@dataclass(frozen=True, slots=True)
class Resolution:
    """The ambient curve-resolution settings.

    Mirrors OpenSCAD's ``$fn``/``$fa``/``$fs`` special variables plus the SDF backend's ``res``.
    A field left at ``None`` means "not set" -- the renderer's own default applies.
    """

    #: Fixed number of fragments per full circle; overrides fa/fs when 3 or more, and ``0`` means
    #: "ignore any ambient fn, use fa/fs" (SPEC R-5).
    fn: int | None = None
    #: Minimum fragment angle in degrees.
    fa: float | None = None
    #: Minimum fragment size in millimetres.
    fs: float | None = None
    #: Sampling resolution for the SDF backend.
    res: int | None = None


_EMPTY = Resolution()

_current: contextvars.ContextVar[Resolution | None] = contextvars.ContextVar("bosl2_defaults", default=None)

#: Process-wide fallback, set by :func:`set_defaults`; the ContextVar shadows it inside a block.
_global: Resolution = _EMPTY


def current_defaults() -> Resolution:
    """Return the resolution settings in effect right here.

    Returns:
        The block-scoped settings if inside a :func:`use_defaults` block, otherwise the ones from
        :func:`set_defaults`, otherwise an all-``None`` :class:`Resolution`.

    """
    active = _current.get()
    return active if active is not None else _global


def set_defaults(
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> None:
    """Set the process-wide resolution defaults.

    Only the arguments given are changed; passing ``None`` leaves that setting as it was, so
    ``set_defaults(fn=64)`` does not disturb an existing ``fs``. Use :func:`reset_defaults` to
    clear. Prefer :func:`use_defaults` in library code -- a global default reaches other people's
    shapes too.

    Args:
        fn: Fixed number of fragments per full circle.
        fa: Minimum fragment angle in degrees.
        fs: Minimum fragment size in millimetres.
        res: Sampling resolution for the SDF backend.

    Returns:
        None.

    """
    global _global
    _global = _merge(_global, fn, fa, fs, res)


def reset_defaults() -> None:
    """Clear the process-wide resolution defaults, restoring the renderer's own behaviour."""
    global _global
    _global = _EMPTY


@contextlib.contextmanager
def use_defaults(
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Iterator[Resolution]:
    """Apply resolution defaults to every shape built inside the block.

    Settings nest: an inner block inherits the outer one and overrides only what it names. The
    block is thread- and async-safe (a :class:`~contextvars.ContextVar` holds the value).

    Args:
        fn: Fixed number of fragments per full circle.
        fa: Minimum fragment angle in degrees.
        fs: Minimum fragment size in millimetres.
        res: Sampling resolution for the SDF backend.

    Yields:
        The :class:`Resolution` in effect inside the block.

    Note:
        A single call opts out of an ambient ``fn`` by passing ``fn=0``, which means "use fa/fs"
        exactly as OpenSCAD's ``$fn=0`` does.

    Examples:
        .. pythonscad-example::

            from pybosl2 import cyl
            from pybosl2.defaults import use_defaults

            with use_defaults(fn=64):
                cyl(height=20, radius=8).show()

    """
    token = _current.set(_merge(current_defaults(), fn, fa, fs, res))
    try:
        yield current_defaults()
    finally:
        _current.reset(token)


def resolve_facets(
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> tuple[int | None, float | None, float | None]:
    """Fill in whichever of *fn*, *fa*, *fs* the caller left unset from the ambient defaults.

    Args:
        fn: Caller-supplied fragment count, or None.
        fa: Caller-supplied fragment angle, or None.
        fs: Caller-supplied fragment size, or None.

    Returns:
        The three values with any ``None`` replaced by the ambient setting (still ``None`` when
        nothing is set anywhere). ``fn=0`` passes through unchanged: it is the caller opting out
        of an ambient ``fn``, and :func:`~pybosl2._helpers.frag_count` reads any ``fn`` below 3 as
        "use fa/fs" (SPEC R-5).

    Note:
        The rule itself lives in :meth:`~pybosl2.groups.Facets.resolved`, which this and
        :func:`resolve_res` both call. They were two implementations of one rule (SPEC R-1).

    """
    from pybosl2.groups import Facets  # local: groups reads the ambient defaults from here

    resolved = Facets.resolved(fn=fn, fa=fa, fs=fs)
    return resolved.fn, resolved.fa, resolved.fs


def resolve_res(res: int | None = None) -> int | None:
    """Fill in the SDF sampling resolution from the ambient defaults when the caller left it unset.

    Args:
        res: Caller-supplied resolution, or None.

    Returns:
        The resolution to use, or ``None`` when nothing is set anywhere.

    """
    from pybosl2.groups import Facets  # local: groups reads the ambient defaults from here

    return Facets.resolved(res=res).res


def _merge(
    base: Resolution,
    fn: int | None,
    fa: float | None,
    fs: float | None,
    res: int | None,
) -> Resolution:
    """Return *base* with each non-None argument applied over it."""
    return Resolution(
        fn=fn if fn is not None else base.fn,
        fa=fa if fa is not None else base.fa,
        fs=fs if fs is not None else base.fs,
        res=res if res is not None else base.res,
    )

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# DocCategory: internal

"""Exceptions for the dual-backend (CSG / SDF) solid system."""

# Exceptions for the dual-backend (CSG / SDF) solid system. pybosl2 realizes solids through either
# the exact-CSG backend (PythonSCAD, the default) or the F-Rep/signed-distance backend (libfive).
# These errors make the two failure modes of a two-backend world explicit: asking a backend for a
# feature it cannot express (:class:`UnsupportedByBackendError`), and combining solids that live on
# different backends (:class:`CrossBackendError`, which tells you how to convert).
#

from __future__ import annotations

__all__ = [
    "Bosl2Error",
    "Bosl2ValueError",
    "Bosl2NotImplementedError",
    "UnsupportedByBackendError",
    "CrossBackendError",
]


class Bosl2Error(Exception):
    """Base class for pybosl2's own errors.

    Every error the library raises derives from this (SPEC E-1), including the argument-validation
    errors -- see :class:`Bosl2ValueError` for how that coexists with E-4's requirement that bad
    input raises a :class:`ValueError`.
    """


class Bosl2ValueError(Bosl2Error, ValueError):
    """Bad input to a pybosl2 call: a ``ValueError`` *and* a :class:`Bosl2Error`.

    SPEC E-4 requires argument validation to raise ``ValueError`` -- what a Python caller expects
    for a bad argument -- and SPEC E-1 requires every library error to derive from one base so the
    family can be caught with a single ``except``. Deriving from both is what makes the two
    compatible: code that already catches ``ValueError`` is unaffected, and
    ``except Bosl2Error`` starts catching the ~570 validation sites that it previously missed.

    Raised for a bad argument value; a bad argument *type* or arity is still Python's own
    ``TypeError``.

    Examples:
        Both spellings catch it::

            from pybosl2 import Bosl2Error, cyl

            try:
                cyl(height=10, radius=5, diameter=10)
            except Bosl2Error as err:
                print(err)  # give radius or diameter, not both (radius=5, diameter=10)

    """


class Bosl2NotImplementedError(Bosl2Error, NotImplementedError):
    """A capability this port advertises but does not yet build: a ``NotImplementedError`` *and* a :class:`Bosl2Error`.

    The same reasoning as :class:`Bosl2ValueError`, for the same reason. Four public callables
    raised a bare ``NotImplementedError`` -- ``cyl(texture=...)``, ``cuboid(teardrop=...)``,
    ``CapType.CIRCLE`` and ``VNF.from_field`` with a range -- so ``except Bosl2Error`` missed
    them, and none named an alternative, which SPEC E-2 asks of every refusal.

    A parameter that raises this is one the signature advertises and the port does not honour. It
    is a gap, not a design decision, and the message says what to do meanwhile.
    """


class UnsupportedByBackendError(Bosl2Error, AttributeError):
    """A feature the active backend cannot express.

    Also an :class:`AttributeError`, because a backend refuses most often from ``__getattr__`` and
    Python's attribute protocol is defined in terms of that type (SPEC E-6): ``hasattr()`` and
    ``getattr(obj, name, default)`` catch ``AttributeError`` and nothing else, so any other type
    turns a capability probe into a traceback and breaks ``copy``, ``pickle``, ``inspect`` and
    every REPL completion. The extra base is invisible to a refusal raised from a call.

    Raised, rather than silently producing different geometry, when a call needs something the chosen
    backend has no faithful equivalent for -- e.g. the BOSL2 attachment/anchor system on the ``"sdf"``
    backend, or a smooth-blend union on the ``"csg"`` backend.

    Args:
        feature: short name of the unsupported operation (e.g. ``"attach"``, ``"smooth_union"``).
        backend: the active backend that cannot do it (``"csg"`` / ``"sdf"``).
        hint:    optional guidance (an alternative call, or which backend does support it).

    """

    def __init__(self, feature: str, backend: str, hint: str | None = None) -> None:
        """Initialize the instance."""
        self.feature = feature
        self.backend = backend
        self.hint = hint
        msg = f"{feature!r} is not supported by the {backend!r} backend"
        if hint:
            msg += f". {hint}"
        super().__init__(msg)


class CrossBackendError(Bosl2Error):
    """A boolean/transform combined solids from two different backends.

    Solids must share a backend to be combined. Convert one first: meshing an SDF solid into a CSG
    polyhedron is exact (``sdf_solid.to_csg()``); voxel-sampling a CSG solid into an SDF is lossy and
    opt-in (``csg_solid.to_sdf(voxel_size=...)``).

    Args:
        left:  backend of the left operand.
        right: backend of the right operand.

    """

    def __init__(self, left: str, right: str) -> None:
        """Initialize the instance."""
        self.left = left
        self.right = right
        super().__init__(
            f"cannot combine a {left!r}-backend solid with a {right!r}-backend solid -- operands "
            f"must share a backend. Bring the SDF solid into the CSG world with `.to_csg()` (an "
            f"exact mesh->polyhedron) and combine there. (Direct CSG->SDF conversion is not supported.)"
        )

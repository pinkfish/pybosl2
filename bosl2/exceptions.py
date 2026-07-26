# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# Exceptions for the dual-backend (CSG / SDF) solid system. bosl2 realizes solids through either
# the exact-CSG backend (PythonSCAD, the default) or the F-Rep/signed-distance backend (libfive).
# These errors make the two failure modes of a two-backend world explicit: asking a backend for a
# feature it cannot express (:class:`UnsupportedByBackend`), and combining solids that live on
# different backends (:class:`CrossBackendError`, which tells you how to convert).
#

from __future__ import annotations

__all__ = ["Bosl2Error", "UnsupportedByBackend", "CrossBackendError"]


class Bosl2Error(Exception):
    """Base class for bosl2's own errors."""


class UnsupportedByBackend(Bosl2Error):
    """A feature the active backend cannot express.

    Raised, rather than silently producing different geometry, when a call needs something the chosen
    backend has no faithful equivalent for -- e.g. the BOSL2 attachment/anchor system on the ``"sdf"``
    backend, or a smooth-blend union on the ``"csg"`` backend.

    Args:
        feature: short name of the unsupported operation (e.g. ``"attach"``, ``"smooth_union"``).
        backend: the active backend that cannot do it (``"csg"`` / ``"sdf"``).
        hint:    optional guidance (an alternative call, or which backend does support it).
    """

    def __init__(self, feature: str, backend: str, hint: str | None = None) -> None:
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
        self.left = left
        self.right = right
        super().__init__(
            f"cannot combine a {left!r}-backend solid with a {right!r}-backend solid -- operands "
            f"must share a backend. Bring the SDF solid into the CSG world with `.to_csg()` (an "
            f"exact mesh->polyhedron) and combine there. (Direct CSG->SDF conversion is not supported.)"
        )

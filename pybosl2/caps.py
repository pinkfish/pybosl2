# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Sweep and skin end-cap specifications.

Provides the :data:`CapsSpec` type alias and the :func:`_norm_caps` normaliser
shared by :mod:`pybosl2.skin` and :mod:`pybosl2.beziers` for specifying
whether to add end caps when sweeping a shape along a path.

Cap types (BOSL2-style names, currently mapping to standard flat end caps):

``BUTT``, ``FLAT``
    Default flat end cap. Closes the open end with a planar face perpendicular
    to the path direction at the endpoint.

``ROUND``, ``SPHERE``
    Spherical end cap. Adds a hemispherical bulge at the end. (Planned --
    currently aliased to ``BUTT``.)

``CIRCLE``
    Round-over end cap. Bevels the end with a constant-radius profile.
    (Planned -- currently aliased to ``BUTT``.)

.. note::
    Fancy cap shapes (``ROUND``, ``SPHERE``, ``CIRCLE``) are scaffolding
    only -- they resolve to flat caps. Full BOSL2 cap profiles need the
    sweep's 3-D end-profile geometry exported into
    :class:`~pybosl2.vnf.VNF` and are not yet ported.
"""

from __future__ import annotations

from enum import Enum
from typing import Sequence, Union

import numpy as np

__all__ = ["CapsSpec", "CapType", "_caps_as_bools", "_norm_caps"]


class CapType(Enum):
    """Named end-cap style for BOSL2 ``caps=`` arguments.

    A single value caps both ends alike; wrap two values in a sequence
    for per-end control. Pass ``None`` instead of a :class:`CapType`
    to request no cap on that end.
    """

    BUTT = "butt"
    FLAT = "flat"
    ROUND = "round"
    SPHERE = "sphere"
    CIRCLE = "circle"


#: A cap specification used by every sweep/skin entry point. Can be:
#:
#: * a single :class:`CapType` enum member (same cap on both ends)
#: * a ``Sequence[CapType | None]`` pair (per-end caps, ``None`` for no cap)
#: * ``None`` to take the default (``CapType.BUTT`` on both ends)
CapsSpec = Union["CapType", "Sequence[Union['CapType', None]]", None]

#: The default cap type used when *caps* is ``None``.
DEFAULT_CAP = CapType.BUTT


def _norm_caps(caps: CapsSpec, closed: bool = False) -> list[CapType | None]:
    """Normalize a :data:`CapsSpec` to a ``[cap_type, cap_type]`` pair.

    Returns a list of two :class:`CapType` or ``None`` values for the
    start and end caps. ``None`` means no cap.

    Args:
        caps: The cap specification to normalize.
        closed: Whether the sweep is closed (no caps on either end).

    Returns:
        A ``[CapType | None, CapType | None]`` pair (or ``[]`` for closed).
    """
    if closed:
        return []

    if caps is None:
        return [None, None]
    if isinstance(caps, (list, tuple, np.ndarray)):
        return [_normalize_one(c) for c in caps[:2]]  # type: ignore[arg-type]
    return [_normalize_one(caps), _normalize_one(caps)]  # type: ignore[arg-type]


def _normalize_one(cap: CapType | None) -> CapType | None:
    """Normalize a single cap value to a :class:`CapType` or ``None``.

    ``None`` passes through as "no cap."
    """
    return cap


def _caps_as_bools(cap_types: list[CapType | None]) -> list[bool]:
    """Convert a :class:`CapType` pair to the bool pair for :func:`VNF.vertex_array`.

    ``None`` entries mean no cap; any :class:`CapType` member currently
    resolves to ``True`` (flat end cap). Always returns exactly two elements.
    """
    if not cap_types:
        return [False, False]
    if len(cap_types) == 1:
        ct = cap_types[0]
        return [ct is not None, ct is not None]
    return [ct is not None for ct in cap_types[:2]]

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

``"butt"``, ``"flat"``
    Default flat end cap. Closes the open end with a planar face perpendicular
    to the path direction at the endpoint.

``"round"``, ``"sphere"``
    Spherical end cap. Adds a hemispherical bulge at the end. (Planned --
    currently aliased to ``"butt"``.)

``"circle"``
    Round-over end cap. Bevels the end with a constant-radius profile.
    (Planned -- currently aliased to ``"butt"``.)

.. note::
    Fancy cap shapes (``"round"``, ``"sphere"``, ``"circle"``) are scaffolding
    only -- they resolve to flat caps. Full BOSL2 cap profiles (offset shells,
    spherically-sampled VNFs) need the sweep's 3-D end-profile geometry
    exported into :class:`~pybosl2.vnf.VNF` and are not yet ported.
"""

from __future__ import annotations

from enum import Enum
from typing import Sequence, Union

import numpy as np

__all__ = ["CapsSpec", "CapType", "_caps_as_bools", "_norm_caps"]


class CapType(Enum):
    """Named end-cap style for BOSL2 ``caps=`` arguments.

    Both the BOSL2 string names and enum members are accepted wherever a
    :data:`CapsSpec` value is expected. A single value caps both ends
    alike; wrap two values in a sequence for per-end control.
    """

    BUTT = "butt"
    FLAT = "flat"
    ROUND = "round"
    SPHERE = "sphere"
    CIRCLE = "circle"


#: A cap specification used by every sweep/skin entry point. Can be a single
#: ``bool`` (same cap on both ends), a :class:`CapType` enum member, a
#: ``Sequence[bool | CapType]`` (per-end caps), or ``None`` to take the
#: call's own default (which is :attr:`CapType.BUTT`).
CapsSpec = Union[bool, "CapType", "Sequence[Union[bool, 'CapType']]", None]

#: The default cap type used when *caps* is ``None``.
DEFAULT_CAP = CapType.BUTT


def _norm_caps(caps: CapsSpec, closed: bool = False, default: bool | CapType = DEFAULT_CAP) -> list[CapType | None]:
    """Normalize a :data:`CapsSpec` to a ``[cap_type, cap_type]`` pair.

    Accepts booleans, :class:`CapType` enum values, or sequences of either.
    A ``True`` boolean maps to the *default* cap type; ``False`` means no
    cap (returned as ``None`` internally via :func:`_caps_as_bools`).
    Named cap types (``ROUND``, ``SPHERE``, ``CIRCLE``) are accepted
    but currently produce flat caps in :func:`_caps_as_bools`.

    Args:
        caps: The cap specification to normalize.
        closed: Whether the sweep is closed (no caps).
        default: The default :class:`CapType` when *caps* is ``None``.

    Returns:
        A ``[CapType, CapType]`` pair.
    """
    if closed:
        return []  # closed has no caps

    ct_default: CapType = default if isinstance(default, CapType) else (DEFAULT_CAP if default else CapType.BUTT)

    if caps is None:
        return [ct_default, ct_default]
    if isinstance(caps, (list, tuple, np.ndarray)):
        return [_normalize_one(c, ct_default) for c in caps[:2]]  # type: ignore[arg-type]
    result = _normalize_one(caps, ct_default)  # type: ignore[arg-type]
    return [result, result]


def _normalize_one(cap: bool | CapType, default: CapType = DEFAULT_CAP) -> CapType | None:
    """Normalize a single cap value to a :class:`CapType`, or ``None`` for no cap."""
    if isinstance(cap, CapType):
        return cap
    if isinstance(cap, bool):
        return default if cap else None  # False = no cap
    return default


def _caps_as_bools(cap_types: list[CapType | None]) -> list[bool]:
    """Convert a :class:`CapType` pair to the bool pair expected by :func:`VNF.vertex_array`.

    ``None`` entries mean no cap; any :class:`CapType` member currently
    resolves to ``True`` (flat end cap). Always returns exactly two elements.
    """
    if not cap_types:
        return [False, False]
    if len(cap_types) == 1:
        ct = cap_types[0]
        return [ct is not None, ct is not None]
    return [ct is not None for ct in cap_types[:2]]

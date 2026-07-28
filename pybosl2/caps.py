# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""End-cap specifications shared by sweep, skin, bezier, and stroke drawing.

Provides the :class:`CapType` enum, the :class:`CapSpec` dataclass for
controlling cap appearance, and the normaliser shared by :mod:`pybosl2.skin`,
:mod:`pybosl2.beziers`, and :mod:`pybosl2.drawing`.

Cap types
    ``NONE`` -- no cap (open end)
    ``BUTT`` / ``FLAT`` -- default flat end cap
    ``ROUND`` / ``SPHERE`` -- spherical end cap (planned)
    ``CIRCLE`` -- round-over end cap (planned)
    ``ARROW`` / ``DIAMOND`` / ``DOT`` ... -- stroke endcap styles

.. note::
    Fancy sweep cap shapes (``ROUND``, ``SPHERE``, ``CIRCLE``) are
    scaffolding only -- they resolve to flat caps. Full BOSL2 cap profiles
    need the sweep's 3-D end-profile geometry exported into
    :class:`~pybosl2.vnf.VNF` and are not yet ported.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Sequence, Union

import numpy as np

__all__ = ["CapType", "CapSpec", "CapsSpec", "_caps_as_bools", "_endcap_polys", "_norm_caps"]


class CapType(Enum):
    """End-cap or stroke-endcap style.

    Sweep/skin cap types:
        ``NONE`` -- no cap (open end)
        ``BUTT`` / ``FLAT`` -- flat end cap
        ``ROUND`` / ``SPHERE`` -- spherical (planned)
        ``CIRCLE`` -- round-over (planned)

    Stroke endcap/joint types:
        ``ARROW`` / ``ARROW2`` / ``ARROW3`` -- arrow heads
        ``DIAMOND`` -- diamond shape
        ``DOT`` -- circular dot
        ``BLOCK`` / ``SQUARE`` -- rectangular block
        ``CHISEL`` -- chisel edge
        ``TAIL`` / ``TAIL2`` -- tail shapes
        ``CROSS`` / ``X`` / ``LINE`` -- line markers
    """

    NONE = "none"
    # Sweep cap types
    BUTT = "butt"
    FLAT = "flat"
    ROUND = "round"
    SPHERE = "sphere"
    CIRCLE = "circle"
    # Stroke endcap/joint types
    ARROW = "arrow"
    ARROW2 = "arrow2"
    ARROW3 = "arrow3"
    BLOCK = "block"
    CHISEL = "chisel"
    CROSS = "cross"
    DIAMOND = "diamond"
    DOT = "dot"
    LINE = "line"
    SQUARE = "square"
    TAIL = "tail"
    TAIL2 = "tail2"
    X = "x"


#: A cap specification used by sweep/skin entry points. Can be:
#:
#: * a single :class:`CapType` enum member (same cap on both ends)
#: * a :class:`CapSpec` with custom dimensions
#: * a ``Sequence[CapType | CapSpec]`` pair (per-end caps)
#:
#: Use ``CapType.NONE`` to request no cap; ``CapType.BUTT`` for a flat cap.
CapsSpec = Union["CapType", "CapSpec", "Sequence[Union['CapType', 'CapSpec']]"]

#: The default cap type used when no explicit cap is requested.
DEFAULT_CAP = CapType.BUTT


@dataclass(frozen=True)
class CapSpec:
    """Customisable end-cap specification.

    Used wherever a cap type is accepted. The *cap_type* field selects the
    shape; *length*, *width*, and *extent* control the dimensions; *angle*
    rotates the cap; *color* overrides the path colour when set.

    Args:
        cap_type: The :class:`CapType` style.
        length: Cap length multiplier (along the path direction).
        width: Cap width multiplier (perpendicular scale).
        extent: Extent multiplier for the cap shape.
        angle: Rotation angle of the cap in degrees.
        color: Override colour for the cap, or ``None`` for the path colour.
    """

    cap_type: CapType = DEFAULT_CAP
    length: float = 0.0
    width: float = 0.0
    extent: float = 0.0
    angle: float = 0.0
    color: str | None = None


# ---------------------------------------------------------------------------
# Default CapSpec for each stroke endcap/joint CapType (BOSL2 _shape_defaults).
# Used by _endcap_polys when a caller-supplied CapSpec does not provide
# all dimensions; the caller's fields override these defaults.
# ---------------------------------------------------------------------------

_DEFAULTS: dict[CapType, CapSpec] = {
    CapType.NONE: CapSpec(cap_type=CapType.NONE, length=1.0, width=0.0, extent=0.0),
    CapType.BUTT: CapSpec(cap_type=CapType.BUTT, length=1.0, width=0.0, extent=0.0),
    CapType.ROUND: CapSpec(cap_type=CapType.ROUND, length=1.0, width=1.0, extent=0.0),
    CapType.CHISEL: CapSpec(cap_type=CapType.CHISEL, length=1.0, width=1.0, extent=0.0),
    CapType.SQUARE: CapSpec(cap_type=CapType.SQUARE, length=1.0, width=1.0, extent=0.0),
    CapType.BLOCK: CapSpec(cap_type=CapType.BLOCK, length=2.0, width=1.0, extent=0.0),
    CapType.DIAMOND: CapSpec(cap_type=CapType.DIAMOND, length=2.5, width=1.0, extent=0.0),
    CapType.DOT: CapSpec(cap_type=CapType.DOT, length=2.0, width=1.0, extent=0.0),
    CapType.X: CapSpec(cap_type=CapType.X, length=2.5, width=0.4, extent=0.0, angle=45.0),
    CapType.CROSS: CapSpec(cap_type=CapType.CROSS, length=3.0, width=0.33, extent=0.0),
    CapType.LINE: CapSpec(cap_type=CapType.LINE, length=3.5, width=0.22, extent=0.0),
    CapType.ARROW: CapSpec(cap_type=CapType.ARROW, length=3.5, width=0.4, extent=0.5),
    CapType.ARROW2: CapSpec(cap_type=CapType.ARROW2, length=3.5, width=1.0, extent=0.14),
    CapType.ARROW3: CapSpec(cap_type=CapType.ARROW3, length=3.5, width=1.0, extent=0.0),
    CapType.TAIL: CapSpec(cap_type=CapType.TAIL, length=3.5, width=0.47, extent=0.5),
    CapType.TAIL2: CapSpec(cap_type=CapType.TAIL2, length=3.5, width=0.28, extent=0.5),
}


# ---------------------------------------------------------------------------
# Cap normalisation helpers
# ---------------------------------------------------------------------------


def _norm_caps(caps: CapsSpec, closed: bool = False) -> list[CapSpec]:
    """Normalize a :data:`CapsSpec` to a ``[CapSpec, CapSpec]`` pair.

    Returns a list of two fully-resolved :class:`CapSpec` objects for the
    start and end caps. ``CapSpec(cap_type=CapType.NONE)`` means no cap.

    Args:
        caps: The cap specification to normalize.
        closed: Whether the sweep is closed (no caps on either end).

    Returns:
        A ``[CapSpec, CapSpec]`` pair (or ``[]`` for closed).
    """
    if closed:
        return []

    if isinstance(caps, (list, tuple, np.ndarray)):
        return [_normalize_one(c) for c in caps[:2]]  # type: ignore[arg-type]
    result = _normalize_one(caps)  # type: ignore[arg-type]
    return [result, result]


def _normalize_one(cap: CapType | CapSpec) -> CapSpec:
    """Normalize a single cap value to a fully-resolved :class:`CapSpec`.

    If given a raw :class:`CapType`, looks up the default :class:`CapSpec`
    from :data:`_DEFAULTS`. If given a :class:`CapSpec` already, returns it
    unchanged (callers can set non-zero fields to override the defaults).
    """
    if isinstance(cap, CapSpec):
        return cap
    if isinstance(cap, CapType):
        return _DEFAULTS.get(cap, _DEFAULTS[CapType.NONE])
    return _DEFAULTS[CapType.BUTT]


def _caps_as_bools(cap_specs: list[CapSpec]) -> list[bool]:
    """Convert a :class:`CapSpec` pair to the bool pair for :func:`VNF.vertex_array`.

    ``CapType.NONE`` entries mean no cap; any other :class:`CapType` resolves
    to ``True`` (flat end cap). Always returns exactly two elements.
    """
    if not cap_specs:
        return [False, False]
    if len(cap_specs) == 1:
        ct = cap_specs[0].cap_type
        return [ct != CapType.NONE, ct != CapType.NONE]
    return [s.cap_type != CapType.NONE for s in cap_specs[:2]]


# ---------------------------------------------------------------------------
# Stroke endcap polygon generation
# ---------------------------------------------------------------------------


def _endcap_polys(spec: CapSpec, lw: float) -> list[np.ndarray]:
    """The local-frame polygon(s) for an endcap (BOSL2 ``_shape_path()``).

    Dimensions are taken directly from the :class:`CapSpec` which has
    already been resolved by :func:`_normalize_one` against
    :data:`_DEFAULTS`.

    Args:
        spec: The resolved cap specification.
        lw: The line width (stroke width) to scale the polygons.

    Returns:
        A list of (N,2) ndarray polygons in the endcap's local frame
        (X is the line direction, Y is perpendicular).
    """
    if spec.cap_type in (CapType.NONE, CapType.BUTT):
        return []

    w = spec.width
    length = spec.length * spec.width
    l2 = spec.extent * spec.width
    w2 = w - l2
    s = lw / 2
    ss = s * w2

    style = spec.cap_type
    poly: list[np.ndarray] = []
    if style == CapType.ROUND:
        th = np.linspace(0, math.pi, 16)
        poly.append(np.column_stack([-math.cos(th) * s, math.sin(th) * s]))
    elif style == CapType.CHISEL:
        poly.append(np.array([[0, -s], [s * length, 0], [0, s]]))
    elif style == CapType.SQUARE:
        poly.append(np.array([[0, -s], [s * length, -s], [s * length, s], [0, s]]))
    elif style == CapType.BLOCK:
        p = s * length
        poly.append(np.array([[0, -s], [p, -s], [p, s], [0, s]]))
    elif style == CapType.DIAMOND:
        p = s * length
        poly.append(np.array([[0, 0], [p / 2, -s], [p, 0], [p / 2, s]]))
    elif style == CapType.DOT:
        th = np.linspace(0, 2 * math.pi, 16)
        poly.append(np.column_stack([math.cos(th) * s, math.sin(th) * s]))
    elif style == CapType.X:
        p = s * length
        poly.append(np.array([[0, -ss], [p, -s]]))
        poly.append(np.array([[p, -s], [0, ss]]))
    elif style == CapType.CROSS:
        p = s * length
        poly.append(np.array([[0, -ss], [p, 0], [0, ss]]))
    elif style == CapType.LINE:
        poly.append(np.array([[0, 0], [s * length, 0]]))
    elif style == CapType.ARROW:
        p = s * length
        pp = s * (length - 0.5)
        poly.append(np.array([[0, -s], [pp, -s], [p, 0], [pp, s], [0, s]]))
    elif style == CapType.ARROW2:
        p = s * length
        pp = s * 0.75
        poly.append(np.array([[0, -ss], [p - pp, -ss], [p - pp, -s], [p, 0], [p - pp, s], [p - pp, ss], [0, ss]]))
    elif style == CapType.ARROW3:
        p = s * length
        pp = s * 0.5
        poly.append(np.array([[0, -ss], [p - pp, -ss], [p - pp, -s], [p, 0], [p - pp, s], [p - pp, ss], [0, ss]]))
    elif style == CapType.TAIL:
        p = s * length
        pp = s * (length - 0.5)
        poly.append(np.array([[0, -s], [p - pp, -s], [p, 0], [p - pp, s], [0, s]]))
    elif style == CapType.TAIL2:
        p = s * length
        pp = s * (length - 0.17)
        poly.append(np.array([[0, -ss], [p - pp, -ss], [p - pp, -s], [p, 0], [p - pp, s], [p - pp, ss], [0, ss]]))

    if spec.angle != 0.0:
        cos_a = math.cos(math.radians(spec.angle))
        sin_a = math.sin(math.radians(spec.angle))
        rot = np.array([[cos_a, -sin_a], [sin_a, cos_a]])
        poly = [(p @ rot.T).astype(float) for p in poly]  # type: ignore[attr-defined]
    return poly

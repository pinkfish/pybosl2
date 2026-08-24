# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# LibFile: pybosl2/caps.py
# FileSummary: Stroke and sweep end caps: the CapType styles and the CapSpec value.
# DocCategory: Foundational
# FileGroup: BOSL2

"""End-cap specifications shared by sweep, skin, bezier, and stroke drawing.

Provides the :class:`CapType` enum, the :class:`CapSpec` dataclass for
controlling cap appearance, and the normaliser shared by :mod:`pybosl2.skin`,
:mod:`pybosl2.beziers`, and :mod:`pybosl2.drawing`.

Cap types
    ``NONE`` -- no cap (open end)
    ``BUTT`` -- default flat end cap (``FLAT`` is a module-level backward-compatible alias)
    ``ROUND`` / ``SPHERE`` -- spherical end cap (planned)
    ``CIRCLE`` -- round-over end cap (planned)
    ``ARROW`` / ``DIAMOND`` / ``DOT`` ... -- stroke endcap styles
    ``CUSTOM`` -- user-supplied path shape (requires *path* on CapSpec)

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
from typing import TYPE_CHECKING, Any, Sequence, Union

from pybosl2.exceptions import Bosl2ValueError

if TYPE_CHECKING:
    from pybosl2._backend import Solid
    from pybosl2.paths import PathLike
    from pybosl2.vnf import VNF

__all__ = [
    "CapType",
    "CapSpec",
    "CapsSpec",
    "endcap_polys",
    "endcap_trim",
    "has_decorative_caps",
    "norm_caps",
    "vnf_with_decorative_caps",
]


class CapType(Enum):
    """End-cap or stroke-endcap style.

    Sweep/skin cap types:
        ``NONE`` -- no cap (open end)
        ``BUTT`` -- flat end cap
        ``ROUND`` / ``SPHERE`` -- spherical (planned)
        ``CIRCLE`` -- round-over (planned)
        ``CUSTOM`` -- user-supplied :attr:`CapSpec.path` shape

    Stroke endcap/joint types:
        ``ARROW`` / ``ARROW2`` / ``ARROW3`` -- arrow heads
        ``DIAMOND`` -- diamond shape
        ``DOT`` -- circular dot
        ``BLOCK`` / ``SQUARE`` -- rectangular block
        ``CHISEL`` -- chisel edge
        ``TAIL`` / ``TAIL2`` -- tail shapes
        ``CROSS`` / ``X`` / ``LINE`` -- line markers

    Examples:
        .. pythonscad-example::

            from pybosl2 import Path3D, CapType

            spine = Path3D([[0,0,0],[0,0,30],[30,0,30]], closed=False)
            spine.stroke(width=4, endcaps=CapType.ARROW).show()

    """

    NONE = "none"
    # Sweep cap types
    BUTT = "butt"
    ROUND = "round"
    SPHERE = "sphere"
    CIRCLE = "circle"
    CUSTOM = "custom"
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
CapsSpec = Union["CapType", "CapSpec", "str", "Sequence[Union['CapType', 'CapSpec', str]]"]

#: The default cap type used when no explicit cap is requested.
DEFAULT_CAP = CapType.BUTT


@dataclass(frozen=True)
class CapSpec:
    """Customisable end-cap specification.

    Used wherever a cap type is accepted. The *cap_type* field selects the
    shape; *length*, *width*, and *height* control the dimensions; *angle*
    rotates the cap; *color* overrides the path colour when set.

    When *cap_type* is :attr:`CapType.CUSTOM`, the *path* field must hold
    a custom 2-D polygon to use as the endcap shape.

    Args:
        cap_type: The :class:`CapType` style.
        length: Cap length multiplier (along the path direction).
        width: Cap width multiplier (perpendicular scale).
        height: Cap height multiplier (0 means use the computed default from width/length).
        extent: Extent multiplier for the cap shape.
        angle: Rotation angle of the cap in degrees.
        color: Override colour for the cap, or ``None`` for the path colour.
        path: Custom polygon path for :attr:`CapType.CUSTOM`; ignored otherwise.

    Examples:
        .. pythonscad-example::

            from pybosl2 import Path3D, CapSpec, CapType

            spine = Path3D([[0,0,0],[0,0,40]], closed=False)
            cap = CapSpec(CapType.ARROW, length=2, width=3)
            spine.stroke(width=4, endcaps=cap).show()

    """

    cap_type: CapType = DEFAULT_CAP
    length: float = 0.0
    width: float = 0.0
    height: float = 0.0
    extent: float = 0.0
    angle: float = 0.0
    color: str | None = None
    path: Sequence[Sequence[float]] | None = None

    def __post_init__(self) -> None:
        """Post-initialization hook."""


# ---------------------------------------------------------------------------
# Default CapSpec for each stroke endcap/joint CapType (BOSL2 _shape_defaults).
# Used by endcap_polys via normalize_one; the caller's fields override.
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
    CapType.CUSTOM: CapSpec(cap_type=CapType.CUSTOM, length=1.0, width=0.0, extent=0.0),
    CapType.SPHERE: CapSpec(cap_type=CapType.SPHERE, length=1.0, width=1.0, extent=0.0),
    CapType.CIRCLE: CapSpec(cap_type=CapType.CIRCLE, length=1.0, width=1.0, extent=0.0),
}


# ---------------------------------------------------------------------------
# Cap normalisation helpers
# ---------------------------------------------------------------------------


def norm_caps(caps: CapsSpec, closed: bool = False) -> list[CapSpec]:
    """Normalize a :data:`CapsSpec` to a ``[CapSpec, CapSpec]`` pair.

    Returns a list of two fully-resolved :class:`CapSpec` objects for the
    start and end caps. ``CapSpec(cap_type=CapType.NONE)`` means no cap.
    When *closed* is True, both caps are ``CapType.NONE``.

    Args:
        caps: The cap specification to normalize.
        closed: Whether the sweep is closed (no caps on either end).

    Returns:
        A ``[CapSpec, CapSpec]`` pair.

    """
    if closed:
        return [CapSpec(cap_type=CapType.NONE), CapSpec(cap_type=CapType.NONE)]

    if isinstance(caps, (list, tuple)):
        return [normalize_one(c) for c in caps[:2]]
    result = normalize_one(caps)  # type: ignore[arg-type]
    return [result, result]


def normalize_one(cap: CapType | CapSpec | str) -> CapSpec:
    """Normalize a single cap value to a fully-resolved :class:`CapSpec`.

    If given a raw :class:`CapType`, looks up the default :class:`CapSpec`
    from :data:`_DEFAULTS`. If given a :class:`CapSpec` already, returns it
    unchanged.
    """
    if isinstance(cap, CapSpec):
        return cap
    if isinstance(cap, str):
        try:
            cap = CapType(cap)
        except ValueError:
            return _DEFAULTS[CapType.BUTT]
    if isinstance(cap, CapType):
        return _DEFAULTS.get(cap, _DEFAULTS[CapType.NONE])
    return _DEFAULTS[CapType.BUTT]


def has_decorative_caps(cap_specs: list[CapSpec]) -> bool:
    """Return True if any endcap is a decorative (non-flat/non-dome/non-none) type."""
    _basic = frozenset({CapType.NONE, CapType.BUTT, CapType.ROUND, CapType.SPHERE})
    return any(cs.cap_type not in _basic for cs in cap_specs)


def vnf_with_decorative_caps(
    vnf: VNF,
    cap_specs: list[CapSpec],
    closed: bool,
    profile_centers: list[Sequence[float]],
    profile_outdirs: list[Sequence[float]],
    profile_radius: float,
) -> "Solid":
    """Convert VNF to CSG polyhedron, add decorative endcaps, return Bosl2Solid.

    Args:
        vnf: The body VNF (already volume-checked and corrected).
        cap_specs: Normalised cap pair.
        closed: Whether the sweep is closed (no caps expected).
        profile_centers: Centroids of the first and last profiles.
        profile_outdirs: Outward directions for the first and last caps.
        profile_radius: Bounding radius of the profile (half the *width* passed to endcap geometry).

    Returns:
        A Bosl2Solid with the body polyhedron and any decorative endcaps unioned.

    """
    from pybosl2._stroke3d import endcap_geometry_3d

    if closed or not cap_specs:
        return vnf.polyhedron()

    body = vnf.polyhedron()
    width = profile_radius * 2

    for spec, center, outdir in [
        (cap_specs[0], profile_centers[0], profile_outdirs[0]),
        (cap_specs[1], profile_centers[1], profile_outdirs[1]),
    ]:
        if spec.cap_type not in (CapType.NONE, CapType.BUTT, CapType.ROUND, CapType.SPHERE):
            ec = endcap_geometry_3d(spec, list(center), list(outdir), width)
            if ec is not None:
                body = body | ec
    return body


# ---------------------------------------------------------------------------
# Stroke endcap polygon generation (shared by drawing.py and caps.py)
# ---------------------------------------------------------------------------


def endcap_polys(spec: CapSpec, lw: float) -> list[list[list[float]]]:
    """Return the local-frame polygon(s) for an endcap (BOSL2 ``_shape_path()``).

    Dimensions are taken directly from the :class:`CapSpec` which has
    already been resolved by :func:`normalize_one` against
    :data:`_DEFAULTS`.

    Args:
        spec: The resolved cap specification.
        lw: The line width (stroke width) to scale the polygons.

    Returns:
        A list of (N,2) polygon point lists in the endcap's local frame
        (X is the line direction, Y is perpendicular).

    """
    if spec.cap_type in (CapType.NONE, CapType.BUTT):
        return []

    if spec.cap_type == CapType.CUSTOM:
        if not (spec.path is not None):
            raise Bosl2ValueError("CapType.CUSTOM requires path= on the CapSpec")
        return [[[float(c) for c in pt] for pt in spec.path]]

    if spec.cap_type == CapType.CIRCLE:
        raise NotImplementedError("CapType.CIRCLE is not yet implemented")

    w = spec.width
    length = spec.length * spec.width
    l2 = spec.extent * spec.width
    w2 = w - l2
    s = (lw / 2) / w if w else lw / 2
    ss = s * w2

    style = spec.cap_type
    poly: list[list[list[float]]] = []
    if style == CapType.ROUND:
        th = [i * math.pi / 16 for i in range(16)]
        poly.append([[-math.cos(t) * s, math.sin(t) * s] for t in th])
    elif style == CapType.CHISEL:
        poly.append([[0, -s], [s * length, 0], [0, s]])
    elif style == CapType.SQUARE:
        poly.append([[0, -s], [s * length, -s], [s * length, s], [0, s]])
    elif style == CapType.BLOCK:
        p = s * length
        poly.append([[0, -s], [p, -s], [p, s], [0, s]])
    elif style == CapType.DIAMOND:
        p = s * length
        poly.append([[-p / 2, 0], [0, -s], [p / 2, 0], [0, s]])
    elif style == CapType.DOT:
        th = [i * 2 * math.pi / 16 for i in range(16)]
        poly.append([[math.cos(t) * s, math.sin(t) * s] for t in th])
    elif style == CapType.X:
        p = s * length
        poly.append([[0, -ss], [p, -s]])
        poly.append([[p, -s], [0, ss]])
    elif style == CapType.CROSS:
        p = s * length
        poly.append([[0, -ss], [p, 0], [0, ss]])
    elif style == CapType.LINE:
        poly.append([[0, 0], [s * length, 0]])
    elif style == CapType.ARROW:
        p = s * length
        pp = s * (length - 0.5)
        poly.append([[0, -s], [pp, -s], [p, 0], [pp, s], [0, s]])
    elif style == CapType.ARROW2:
        p = s * length
        pp = s * 0.75
        poly.append([[0, -ss], [p - pp, -ss], [p - pp, -s], [p, 0], [p - pp, s], [p - pp, ss], [0, ss]])
    elif style == CapType.ARROW3:
        p = s * length
        pp = s * 0.5
        poly.append([[0, -ss], [p - pp, -ss], [p - pp, -s], [p, 0], [p - pp, s], [p - pp, ss], [0, ss]])
    elif style == CapType.TAIL:
        p = s * length
        pp = s * (length - 0.5)
        poly.append([[0, -s], [p - pp, -s], [p, 0], [p - pp, s], [0, s]])
    elif style == CapType.TAIL2:
        p = s * length
        pp = s * (length - 0.17)
        poly.append([[0, -ss], [p - pp, -ss], [p - pp, -s], [p, 0], [p - pp, s], [p - pp, ss], [0, ss]])

    if spec.angle != 0.0:
        cos_a = math.cos(math.radians(spec.angle))
        sin_a = math.sin(math.radians(spec.angle))
        poly = [[[pt[0] * cos_a - pt[1] * sin_a, pt[0] * sin_a + pt[1] * cos_a] for pt in p] for p in poly]
    return poly


def endcap_trim(spec: CapSpec, width: float) -> float:
    """How far to pull the line back under an arrow endcap so it doesn't poke through the tip.

    Args:
        spec: The resolved cap specification.
        width: The stroke line width.

    Returns:
        The trim distance in world units (0.0 for non-arrow styles).

    """
    s = (width / 2) / spec.width if spec.width else width / 2
    if spec.cap_type in (CapType.ARROW, CapType.ARROW3):
        return s * (spec.length * spec.width - 0.01)
    if spec.cap_type == CapType.ARROW2:
        return s * (spec.length * spec.width * 3 / 4)
    return 0.0


def place(poly: PathLike, theta_deg: float, at: Sequence[float]) -> list[list[float]]:
    """Rotate a local polygon by *theta_deg* and translate it to point *at*."""
    radius = math.radians(theta_deg)
    c, s = math.cos(radius), math.sin(radius)
    return [[c * p[0] - s * p[1] + at[0], s * p[0] + c * p[1] + at[1]] for p in poly]


def trim_ends(body: list[list[float]], trim1: float, trim2: float) -> list[list[float]]:
    """Shorten the open *body* path at each end by trim1/trim2 (clamped within the end segment)."""
    body = [list(map(float, p)) for p in body]
    if len(body) >= 2 and trim1 > 0:
        a0, a1 = float(body[0][0]), float(body[0][1])
        b0, b1 = float(body[1][0]), float(body[1][1])
        dx, dy = b0 - a0, b1 - a1
        seglen = math.hypot(dx, dy) or 1.0
        t = min(trim1, 0.99 * seglen) / seglen
        body[0] = [a0 + dx * t, a1 + dy * t]
    if len(body) >= 2 and trim2 > 0:
        a0, a1 = float(body[-1][0]), float(body[-1][1])
        b0, b1 = float(body[-2][0]), float(body[-2][1])
        dx, dy = b0 - a0, b1 - a1
        seglen = math.hypot(dx, dy) or 1.0
        t = min(trim2, 0.99 * seglen) / seglen
        body[-1] = [a0 + dx * t, a1 + dy * t]
    return body


def oriented_to(shape: Any, outdir: Sequence[float], at: Sequence[float]) -> Any:
    """Rotate a Z-up solid so +Z points along 3-D *outdir*, then translate it to *at*.

    Uses ``rotate(angle, axis)`` rather than a 4x4 ``multmatrix`` so it works on either backend's
    solid -- an SDF PyShape rotates its field in closed form, but has no multmatrix.
    """
    from pybosl2.transforms import rot_from_to

    angle, axis = rot_from_to([0, 0, 1], outdir)
    return shape.rotate(float(angle), [float(c) for c in axis]).translate([float(c) for c in at])

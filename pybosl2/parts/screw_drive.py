# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/parts/screw_drive.py
#    Pure-Python port of BOSL2's screw_drive.scad: masks for the driver recesses cut into a screw
#    head -- Phillips, hex (Allen), Torx and Robertson/square. Each drive type is represented by its
#    own class (e.g. :class:`PhillipsMask`, :class:`HexDriveMask`) with :meth:`shape` and :meth:`show`
#    methods, alongside the dimensional helpers BOSL2 provides: :func:`torx_info` /
#    :func:`torx_diam` / :func:`torx_depth` and :func:`phillips_depth` / :func:`phillips_diam`.
#
#    The dimension tables (Phillips ISO 4757 shaft/cutout sizes, the Torx OD/ID/depth/rounding table
#    from ISO 14583, and the Robertson square-drive inch table) are transcribed verbatim from
#    screw_drive.scad and checked in tests/test_screw_drive.py. Geometry is built with the same
#    primitives BOSL2 uses -- rotate_extrude/linear_extrude of a 2-D profile, hulls of circles, the
#    zrot_copies ring placement, cyl() and prismoid() -- via this package's native-op wrappers.
#
# FileSummary: Phillips, hex, Torx and Robertson driver-recess masks.
# DocCategory: Parts library
# FileGroup: BOSL2

"""Phillips, hex, Torx and Robertson driver-recess masks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pybosl2._helpers import frag_count as _frag_count
from pybosl2._helpers import quantup, union
from pybosl2._native import native
from pybosl2.constants import BOTTOM, INCH
from pybosl2.distributors import DistributableMatrix
from pybosl2.shapes2d import circle, hexagon
from pybosl2.shapes2d import hull as _hull2d
from pybosl2.shapes3d import cyl, prismoid
from pybosl2.shapes3d.base import Bosl2Solid

if TYPE_CHECKING:  # real stub-typed imports for the checker (identical to pre-lazy)
    from pythonscad import polygon as _opolygon
    from pythonscad import rotate_extrude as _orotate_extrude
else:
    _opolygon = native("polygon")
    _orotate_extrude = native("rotate_extrude")

__all__ = [
    "HexDriveMask",
    "PhillipsMask",
    "RobertsonMask",
    "TorxMask",
    "TorxMask2d",
    "PhillipsSpec",
    "TorxSpec",
    "RobertsonSpec",
    "hex_mask",
    "torx_info",
    "torx_diam",
    "torx_depth",
    "phillips_depth",
    "phillips_diam",
]


def _adj_ang_to_opp(adj: float, angle: float) -> float:
    """Return the opposite side of a right triangle given the adjacent side and angle (BOSL2.

    adj_ang_to_opp).
    """
    return adj * math.tan(math.radians(angle))


def _union(shapes: list[Any] | Any) -> Any:
    """Boolean union of a non-empty iterable of shapes."""
    return union(list(shapes) if not isinstance(shapes, list) else shapes)


# ---------------------------------------------------------------------------
# Section: dimension tables (transcribed from screw_drive.scad)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PhillipsSpec:
    """Phillips recess geometry for one bit size (ISO 4757). See :class:`PhillipsMask`."""

    shaft: float  # shaft/outer diameter
    b: float  # cutout wing spacing radius
    e: float  # cutout wing base width
    g: float  # tip cone diameter
    alpha: float  # cutout near-face angle
    beta: float  # cutout tilt angle


@dataclass(frozen=True)
class TorxSpec:
    """Torx driver dimensions for one size (ISO 14583). See :func:`torx_info`."""

    outer_diameter: float  # outer diameter
    inner_diameter: float  # inner diameter
    depth: float  # drive-hole depth
    tip_rounding: float  # external tip rounding radius
    inner_rounding: float  # inner rounding radius

    def as_tuple(self) -> tuple[float, float, float, float, float]:
        """``(outer_diameter, inner_diameter, depth, tip_rounding, inner_rounding)`` -- the raw BOSL2 ``torx_info``.

        list.
        """
        return (self.outer_diameter, self.inner_diameter, self.depth, self.tip_rounding, self.inner_rounding)


@dataclass(frozen=True)
class RobertsonSpec:
    """Robertson/square-drive dimensions for one size, in inches (min/max per the spec).

    ``m`` (across flats), ``t`` (depth) and ``f`` (flat-to-taper transition) return the (min+max)/2
    nominal, as BOSL2 uses.
    """

    m_min: float
    m_max: float
    t_min: float
    t_max: float
    f_min: float
    f_max: float

    @property
    def m(self) -> float:
        """Return the average m value."""
        return (self.m_min + self.m_max) / 2

    @property
    def t(self) -> float:
        """Return the average t value."""
        return (self.t_min + self.t_max) / 2

    @property
    def f(self) -> float:
        """Return the average f value."""
        return (self.f_min + self.f_max) / 2


_PH_GAMMA = 92.0
_PH_BOT_ANGLE = 28.0
_PH_SIDE_ANGLE = 26.5

# Phillips number "#0".."#4" -> its recess geometry (ISO 4757).
_PHILLIPS = {
    0: PhillipsSpec(shaft=3, b=0.61, e=0.31, g=0.81, alpha=136, beta=7.00),
    1: PhillipsSpec(shaft=4.5, b=0.97, e=0.435, g=1.27, alpha=138, beta=7.00),
    2: PhillipsSpec(shaft=6, b=1.47, e=0.815, g=2.29, alpha=140, beta=5.75),
    3: PhillipsSpec(shaft=8, b=2.41, e=2.005, g=3.81, alpha=146, beta=5.75),
    4: PhillipsSpec(shaft=10, b=3.48, e=2.415, g=5.08, alpha=153, beta=7.00),
}

# Torx size -> dimensions. Depth is from metric socket-head screws, ISO 14583
# (some depths interpolated -- see BOSL2).
_TORX = {
    1: TorxSpec(0.90, 0.65, 0.40, 0.059, 0.201),
    2: TorxSpec(1.00, 0.73, 0.44, 0.069, 0.224),
    3: TorxSpec(1.20, 0.87, 0.53, 0.081, 0.266),
    4: TorxSpec(1.35, 0.98, 0.59, 0.090, 0.308),
    5: TorxSpec(1.48, 1.08, 0.65, 0.109, 0.330),
    6: TorxSpec(1.75, 1.27, 0.775, 0.132, 0.383),
    7: TorxSpec(2.08, 1.50, 0.886, 0.161, 0.446),
    8: TorxSpec(2.40, 1.75, 1.0, 0.190, 0.510),
    9: TorxSpec(2.58, 1.87, 1.078, 0.207, 0.554),
    10: TorxSpec(2.80, 2.05, 1.142, 0.229, 0.598),
    15: TorxSpec(3.35, 2.40, 1.2, 0.267, 0.716),
    20: TorxSpec(3.95, 2.85, 1.4, 0.305, 0.859),
    25: TorxSpec(4.50, 3.25, 1.61, 0.375, 0.920),
    27: TorxSpec(5.07, 3.65, 1.84, 0.390, 1.108),
    30: TorxSpec(5.60, 4.05, 2.22, 0.451, 1.194),
    40: TorxSpec(6.75, 4.85, 2.63, 0.546, 1.428),
    45: TorxSpec(7.93, 5.64, 3.115, 0.574, 1.796),
    50: TorxSpec(8.95, 6.45, 3.82, 0.775, 1.816),
    55: TorxSpec(11.35, 8.05, 5.015, 0.867, 2.667),
    60: TorxSpec(13.45, 9.60, 5.805, 1.067, 2.883),
    70: TorxSpec(15.70, 11.20, 6.815, 1.194, 3.477),
    80: TorxSpec(17.75, 12.80, 7.75, 1.526, 3.627),
    90: TorxSpec(20.20, 14.40, 8.945, 1.530, 4.468),
    100: TorxSpec(22.40, 16.00, 10.79, 1.720, 4.925),
}

# Robertson/square size 0..4 -> dimensions, in inches.
_ROBERTSON = {
    0: RobertsonSpec(0.0696, 0.0710, 0.063, 0.073, 0.032, 0.038),
    1: RobertsonSpec(0.0900, 0.0910, 0.105, 0.113, 0.057, 0.065),
    2: RobertsonSpec(0.1110, 0.1126, 0.119, 0.140, 0.065, 0.075),
    3: RobertsonSpec(0.1315, 0.1330, 0.155, 0.165, 0.085, 0.095),
    4: RobertsonSpec(0.1895, 0.1910, 0.191, 0.201, 0.090, 0.100),
}


def _phillips_num(size: str | int) -> int:
    """Parse a Phillips size (int 0..4 or a string like ``"#2"``) into its integer number."""
    count = int(size.lstrip("#")) if isinstance(size, str) else int(size)
    if count < 0 or count > 4:
        raise ValueError(f"phillips size must be #0..#4, got {size!r}")
    return count


def torx_info(size: int) -> TorxSpec:
    """Return the :class:`TorxSpec` for a given Torx *size*.

    Maps to BOSL2 ``torx_info()``.  The spec holds outer_diameter, inner_diameter,
    depth, tip_rounding, and inner_rounding.

    Args:
        size: Torx size number (e.g. 10, 20, 30).

    Returns:
        A :class:`TorxSpec` with the dimensions for the given Torx size.

    Raises:
        ValueError: If *size* is not a supported Torx size.

    """
    try:
        return _TORX[int(size)]
    except (KeyError, ValueError):
        raise ValueError(f"Unsupported Torx size: {size!r}") from None


def torx_diam(size: int) -> float:
    """Outer diameter of a Torx *size* profile.

    Args:
        size: Torx size number (e.g. 10, 20, 30).

    Returns:
        The outer diameter in mm for the given Torx size.

    """
    return torx_info(size).outer_diameter


def torx_depth(size: int) -> float:
    """Typical drive-hole depth for a Torx *size*.

    Args:
        size: Torx size number (e.g. 10, 20, 30).

    Returns:
        The drive depth in mm for the given Torx size.

    """
    return torx_info(size).depth


def _torx_profile(size: int) -> Any:
    spec = torx_info(size)
    outer_diameter, id_, tip, rounding = (
        spec.outer_diameter,
        spec.inner_diameter,
        spec.tip_rounding,
        spec.inner_rounding,
    )
    base = outer_diameter - 2 * tip
    fn = int(quantup(_frag_count(outer_diameter / 2), 12))

    tip_circles = [
        circle(radius=tip, fn=fn // 2).translate([base / 2, 0]).multmatrix(m.tolist())
        for m in DistributableMatrix.zrot_copies(num_copies=3)
    ]
    tri = _hull2d(tip_circles)
    lobes = _union(tri.multmatrix(m.tolist()) for m in DistributableMatrix.zrot_copies(num_copies=2))
    solid = circle(diameter=base, fn=fn) | lobes

    cut = _union(
        circle(radius=rounding, fn=fn).translate([id_ / 2 + rounding, 0]).rotate([0, 0, 180 / 6]).multmatrix(m.tolist())
        for m in DistributableMatrix.zrot_copies(num_copies=6)
    )
    return solid - cut


def phillips_depth(size: str | int, diameter: float) -> float | None:
    """Recess depth needed to reach diameter *diameter* for a Phillips *size*, or ``None``.

    Args:
        size: Phillips bit size (``"#0"``..``"#4"`` or ``0``..``4``).
        diameter: Target recess diameter at the mouth.

    Returns:
        The depth in mm to achieve the given diameter, or ``None`` if the target is unreachable.

    """
    spec = _PHILLIPS[_phillips_num(size)]
    shaft, g = spec.shaft, spec.g
    h1 = _adj_ang_to_opp(g / 2, _PH_BOT_ANGLE)
    if diameter >= shaft or diameter < g:
        return None
    return (diameter - g) / 2 / math.tan(math.radians(_PH_SIDE_ANGLE)) + h1


def phillips_diam(size: str | int, depth: float) -> float | None:
    """Recess diameter at the top when cut to *depth* for a Phillips *size*, or ``None``.

    Args:
        size: Phillips bit size (``"#0"``..``"#4"`` or ``0``..``4``).
        depth: Depth to cut to in mm.

    Returns:
        The top diameter in mm at the given depth, or ``None`` if the depth is out of range.

    """
    spec = _PHILLIPS[_phillips_num(size)]
    shaft, g = spec.shaft, spec.g
    h1 = _adj_ang_to_opp(g / 2, _PH_BOT_ANGLE)
    h2 = _adj_ang_to_opp((shaft - g) / 2, 90 - _PH_SIDE_ANGLE)
    if depth < h1 or depth >= h1 + h2:
        return None
    return 2 * math.tan(math.radians(_PH_SIDE_ANGLE)) * (depth - h1) + g


class PhillipsMask:
    """Phillips driver-recess mask for a given bit size (BOSL2 phillips_mask()).

    The mask is positioned with its opening at the top and its bottom on the XY
    plane (BOSL2's ``anchor=BOTTOM``).  Pass ``center=True`` to center the mask
    vertically instead.

    Examples:
        A #2 Phillips recess cut into a tapered head:

        .. pythonscad-example::

            from pybosl2.parts.screw_drive import PhillipsMask
            from pybosl2.solid import cyl
            (cyl(diameter1=2, diameter2=8, height=4).down(2) - PhillipsMask(size="#2").shape()).show()

    """

    def __init__(
        self,
        size: str | int = "#2",
        center: bool = False,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
        l: float | None = None,  # noqa: E741
    ) -> None:
        """Create a Phillips driver-recess mask.

        Args:
            size: bit size as ``"#0"``..``"#4"`` or an integer ``0``..``4``.
            center: center the mask vertically (default: bottom on the XY plane).
            fn: facet controls for the revolved body (default: BOSL2's fixed 36 facets).
            fa: facet controls for the revolved body (default: BOSL2's fixed 36 facets).
            fs: facet controls for the revolved body (default: BOSL2's fixed 36 facets).
            l: overall length of the recess, overriding the computed length from the spec.

        Returns:
            None.

        Raises:
            ValueError: If *size* is not a valid Phillips bit size (#0..#4).

        """
        self._size: str | int = size
        self._center: bool = center
        self._fn: int | None = fn
        self._fa: float | None = fa
        self._fs: float | None = fs
        self._l: float | None = l

        _fn = fn
        if fn is None and fa is None and fs is None:
            _fn = 36
        spec = _PHILLIPS[_phillips_num(size)]
        shaft, b, e, g = spec.shaft, spec.b, spec.e, spec.g
        alpha, beta, gamma = spec.alpha, spec.beta, _PH_GAMMA

        h1 = _adj_ang_to_opp(g / 2, _PH_BOT_ANGLE)
        h2 = _adj_ang_to_opp((shaft - g) / 2, 90 - _PH_SIDE_ANGLE)
        length = h1 + h2
        h3 = _adj_ang_to_opp(b / 2, _PH_BOT_ANGLE)

        p0 = [0.0, 0.0]
        p1 = [_adj_ang_to_opp(e / 2, 90 - alpha / 2), -e / 2]
        p2 = [
            p1[0] + _adj_ang_to_opp((shaft - e) / 2, 90 - gamma / 2),
            p1[1] - (shaft - e) / 2,
        ]
        cut_path = [p0, p1, p2, [p2[0], -p2[1]], [p1[0], -p1[1]]]

        wing = _opolygon(cut_path).linear_extrude(height=length + 2)
        wing = wing.translate([0, 0, -1]).rotate([0, beta, 0]).translate([0, 0, h3])
        cutter = _union(
            wing.multmatrix(m.tolist()) for m in DistributableMatrix.zrot_copies(num_copies=4, radius=b / 2)
        )
        cutter = cutter.rotate([0, 0, 45])

        body = _orotate_extrude(
            _opolygon([[0, 0], [g / 2, h1], [shaft / 2, length], [0, length]]),
            fn=_fn,
            fa=fa,
            fs=fs,
        )
        mask = Bosl2Solid(body - cutter, size=[shaft, shaft, length])
        self._solid: Bosl2Solid = mask.down(length / 2) if center else mask
        self._shaft: float = shaft
        self._length: float = length

    @property
    def size(self) -> str | int:
        """Phillips bit size."""
        return self._size

    @property
    def center(self) -> bool:
        """Whether the mask is centered vertically."""
        return self._center

    @property
    def fn(self) -> int | None:
        """Facet count override."""
        return self._fn

    @property
    def fa(self) -> float | None:
        """Minimum facet angle."""
        return self._fa

    @property
    def fs(self) -> float | None:
        """Minimum facet size."""
        return self._fs

    @property
    def l(self) -> float | None:  # noqa: E743
        """Overall length of the recess."""
        return self._l

    @property
    def shaft(self) -> float:
        """Shaft/outer diameter."""
        return self._shaft

    @property
    def length(self) -> float:
        """Computed height of the recess."""
        return self._length

    def shape(self) -> Bosl2Solid:
        """Return the Phillips driver-recess mask geometry.

        Examples:
            Generate an STL of a #2 Phillips recess:

            .. pythonscad-example::

                from pybosl2.parts.screw_drive import PhillipsMask
                PhillipsMask(size="#2").shape().export_stl("phillips_2.stl")

        """
        return self._solid

    def show(self) -> None:
        """Display the Phillips driver-recess mask in the viewer."""
        self._solid.show()


class HexDriveMask:
    """Hex (Allen) driver-recess mask (BOSL2 hex_drive_mask()).

    The recess is slightly oversized per the ISO standard; *slop* enlarges it
    by a further ``2 * slop``.

    Examples:
        A 2.5 mm hex drive mask, 5 mm deep:

        .. pythonscad-example::

            from pybosl2.parts.screw_drive import HexDriveMask
            HexDriveMask(size=2.5, l=5).show()

    """

    def __init__(self, size: float, l: float, slop: float = 0.0, center: bool = False) -> None:  # noqa: E741
        """Create a hex (Allen) driver-recess mask.

        Args:
            size: across flats dimension of the hex key.
            l: height of the recess.
            slop: enlarge the recess by ``2 * slop``.
            center: center the mask vertically (default: bottom on the XY plane).

        Returns:
            None.

        """
        self._size: float = size
        self._l: float = l
        self._slop: float = slop
        self._center: bool = center

        realsize = 1.0072 * size + 0.0341 + 2 * slop
        solid = hexagon(inner_diameter=realsize).linear_extrude(height=l, center=center)
        self._solid: Bosl2Solid = Bosl2Solid(solid.shape, size=[realsize, realsize, l])
        self._realsize: float = realsize

    @property
    def size(self) -> float:
        """Across flats dimension."""
        return self._size

    @property
    def l(self) -> float:  # noqa: E743
        """Height of the recess."""
        return self._l

    @property
    def slop(self) -> float:
        """Slop enlargement."""
        return self._slop

    @property
    def center(self) -> bool:
        """Whether the mask is centered vertically."""
        return self._center

    @property
    def realsize(self) -> float:
        """Actual across-flats dimension after ISO oversizing."""
        return self._realsize

    def shape(self) -> Bosl2Solid:
        """Return the hex drive mask geometry."""
        return self._solid

    def show(self) -> None:
        """Display the hex drive mask in the viewer."""
        self._solid.show()


hex_mask = HexDriveMask  #: Alias for :class:`HexDriveMask`.


class TorxMask2d:
    """2-D profile of a Torx driver for a given size (BOSL2 torx_mask2d()).

    This is a 2-D shape; to generate an STL, extrude it with
    :meth:`~pybosl2.shapes2d.base.Bosl2Shape2D.linear_extrude` first.

    Examples:
        Generate an STL of a T30 Torx 2-D profile extruded 10 mm:

        .. pythonscad-example::

            from pybosl2.parts.screw_drive import TorxMask2d
            TorxMask2d(size=30).shape().linear_extrude(height=10).export_stl("torx_30.stl")

    """

    def __init__(self, size: int) -> None:
        """Create a 2-D Torx profile.

        Args:
            size: Torx size number (e.g. 10, 20, 30).

        Returns:
            None.

        """
        self._size: int = size
        self._solid: Bosl2Solid = Bosl2Solid(_torx_profile(size))

    @property
    def size(self) -> int:
        """Torx size number."""
        return self._size

    def shape(self) -> Bosl2Solid:
        """Return the 2-D Torx profile.

        Examples:
            Generate an STL of a T30 Torx 2-D profile extruded 10 mm:

            .. pythonscad-example::

                from pybosl2.parts.screw_drive import TorxMask2d
                TorxMask2d(size=30).shape().linear_extrude(height=10).export_stl("torx_30.stl")

        """
        return self._solid

    def show(self) -> None:
        """Display the 2-D Torx profile in the viewer."""
        self._solid.show()


class TorxMask:
    """Torx driver-recess mask: the 2-D profile extruded *l* tall (BOSL2 torx_mask()).

    Examples:
        A T30 Torx tip:

        .. pythonscad-example::

            from pybosl2.parts.screw_drive import TorxMask
            TorxMask(size=30, l=10).show()

    """

    def __init__(self, size: int, l: float = 5.0, center: bool = False) -> None:  # noqa: E741
        """Create a Torx driver-recess mask.

        Args:
            size: Torx size number (e.g. 10, 20, 30).
            l: height of the recess.
            center: center the mask vertically (default: bottom on the XY plane).

        Returns:
            None.

        """
        self._size: int = size
        self._l: float = l
        self._center: bool = center

        outer_diameter = torx_diam(size)
        solid = _torx_profile(size).linear_extrude(height=l, center=center)
        self._solid: Bosl2Solid = Bosl2Solid(solid.shape, size=[outer_diameter, outer_diameter, l])
        self._outer_diameter: float = outer_diameter

    @property
    def size(self) -> int:
        """Torx size number."""
        return self._size

    @property
    def l(self) -> float:  # noqa: E743
        """Height of the recess."""
        return self._l

    @property
    def center(self) -> bool:
        """Whether the mask is centered vertically."""
        return self._center

    @property
    def outer_diameter(self) -> float:
        """Outer diameter of the Torx profile."""
        return self._outer_diameter

    def shape(self) -> Bosl2Solid:
        """Return the Torx driver-recess mask geometry.

        Examples:
            Generate an STL of a T30 Torx mask:

            .. pythonscad-example::

                from pybosl2.parts.screw_drive import TorxMask
                TorxMask(size=30, l=10).shape().export_stl("torx_30_mask.stl")

        """
        return self._solid

    def show(self) -> None:
        """Display the Torx driver-recess mask in the viewer."""
        self._solid.show()


class RobertsonMask:
    """Robertson/square driver-recess mask for square-drive sizes ``0``..``4`` (BOSL2 robertson_mask()).

    Examples:
        A #2 Robertson recess:

        .. pythonscad-example::

            from pybosl2.parts.screw_drive import RobertsonMask
            RobertsonMask(size=2).show()

    """

    def __init__(self, size: str | int, l: float | None = None, angle: float = 2.5, slop: float = 0.0) -> None:  # noqa: E741
        """Create a Robertson/square driver-recess mask.

        Args:
            size: square-drive size, as ``"#2"`` / ``"2"`` or integer ``2``.
            l: length of drive mask.
            angle: taper angle of each face (default 2.5, from BOSL2's print tests).
            slop: enlarge the recess by ``2 * slop``.

        Returns:
            None.

        Raises:
            ValueError: If *size* is not a valid Robertson size (0..4).

        """
        if isinstance(size, str):
            size = int(size.replace("#", ""))
        if not (isinstance(size, int) and 0 <= size <= 4):
            raise ValueError(f"robertson size must be an int 0..4, got {size!r}")
        spec = _ROBERTSON[size]
        across_flats = spec.m * INCH
        robertson_depth = spec.t * INCH
        robertson_flat = spec.f * INCH
        extra = l - robertson_depth if l is not None else 1.0
        height = robertson_depth + extra
        m_slop = across_flats + 2 * slop
        m_top = m_slop + 2 * _adj_ang_to_opp(robertson_flat + extra, angle)
        m_bot = m_slop - 2 * _adj_ang_to_opp(robertson_depth - robertson_flat, angle)
        tapered = prismoid([m_bot, m_bot], [m_top, m_top], height=height, anchor=BOTTOM)
        cone = cyl(
            diameter1=0,
            diameter2=m_slop / (robertson_depth - robertson_flat) * math.sqrt(2) * height,
            height=height,
            anchor=BOTTOM,
        )
        self._size: int = size
        self._l: float | None = l
        self._angle: float = angle
        self._slop: float = slop
        self._solid: Bosl2Solid = (tapered & cone).down(robertson_depth)

    @property
    def size(self) -> int:
        """Robertson size number (0..4)."""
        return self._size

    @property
    def l(self) -> float | None:  # noqa: E743
        """Length of drive mask."""
        return self._l

    @property
    def angle(self) -> float:
        """Taper angle of each face."""
        return self._angle

    @property
    def slop(self) -> float:
        """Slop enlargement."""
        return self._slop

    def shape(self) -> Bosl2Solid:
        """Return the Robertson driver-recess mask geometry.

        Examples:
            Generate an STL of a #2 Robertson recess:

            .. pythonscad-example::

                from pybosl2.parts.screw_drive import RobertsonMask
                RobertsonMask(size=2).shape().export_stl("robertson_2.stl")

        """
        return self._solid

    def show(self) -> None:
        """Display the Robertson driver-recess mask in the viewer."""
        self._solid.show()

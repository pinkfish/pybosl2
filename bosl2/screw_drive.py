# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/screw_drive.py
#    Pure-Python port of BOSL2's screw_drive.scad: masks for the driver recesses cut into a screw
#    head -- Phillips, hex (Allen), Torx and Robertson/square. The :class:`ScrewDrive` class groups
#    them as static methods that return :class:`~bosl2.shapes3d.Bosl2Solid` masks (subtract one from
#    a head to make the recess), alongside the dimensional helpers BOSL2 provides:
#    :meth:`ScrewDrive.torx_info`/:meth:`~ScrewDrive.torx_diam`/:meth:`~ScrewDrive.torx_depth` and
#    :meth:`ScrewDrive.phillips_depth`/:meth:`~ScrewDrive.phillips_diam`.
#
#    The dimension tables (Phillips ISO 4757 shaft/cutout sizes, the Torx OD/ID/depth/rounding table
#    from ISO 14583, and the Robertson square-drive inch table) are transcribed verbatim from
#    screw_drive.scad and checked in tests/test_screw_drive.py. Geometry is built with the same
#    primitives BOSL2 uses -- rotate_extrude/linear_extrude of a 2-D profile, hulls of circles, the
#    zrot_copies ring placement, cyl() and prismoid() -- via this package's native-op wrappers.
#
# FileSummary: Phillips, hex, Torx and Robertson driver-recess masks.
# FileGroup: BOSL2

from __future__ import annotations

import math
from dataclasses import dataclass

from pythonscad import polygon as _opolygon, rotate_extrude as _orotate_extrude, hull as _ohull

from bosl2._helpers import union
from bosl2.constants import INCH, BOTTOM
from bosl2.distributors import zrot_copies
from bosl2.shapes2d import circle, hexagon, _frag_count
from bosl2.shapes3d import Bosl2Solid, cyl, prismoid, _quantup

__all__ = ["ScrewDrive", "PhillipsSpec", "TorxSpec", "RobertsonSpec"]


def _adj_ang_to_opp(adj: float, ang: float) -> float:
    """The opposite side of a right triangle given the adjacent side and angle (BOSL2 adj_ang_to_opp)."""
    return adj * math.tan(math.radians(ang))


def _union(shapes):
    """Boolean union of a non-empty iterable of shapes."""
    return union(shapes)


# ---------------------------------------------------------------------------
# Section: dimension tables (transcribed from screw_drive.scad)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PhillipsSpec:
    """Phillips recess geometry for one bit size (ISO 4757). See :func:`ScrewDrive.phillips_mask`."""

    shaft: float   # shaft/outer diameter
    b: float       # cutout wing spacing radius
    e: float       # cutout wing base width
    g: float       # tip cone diameter
    alpha: float   # cutout near-face angle
    beta: float    # cutout tilt angle


@dataclass(frozen=True)
class TorxSpec:
    """Torx driver dimensions for one size (ISO 14583). See :func:`ScrewDrive.torx_info`."""

    od: float              # outer diameter
    id: float              # inner diameter
    depth: float           # drive-hole depth
    tip_rounding: float    # external tip rounding radius
    inner_rounding: float  # inner rounding radius

    def as_tuple(self) -> tuple[float, float, float, float, float]:
        """``(od, id, depth, tip_rounding, inner_rounding)`` -- the raw BOSL2 ``torx_info`` list."""
        return (self.od, self.id, self.depth, self.tip_rounding, self.inner_rounding)


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
        return (self.m_min + self.m_max) / 2

    @property
    def t(self) -> float:
        return (self.t_min + self.t_max) / 2

    @property
    def f(self) -> float:
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


def _phillips_num(size) -> int:
    """Parse a Phillips size (int 0..4 or a string like ``"#2"``) into its integer number."""
    if isinstance(size, str):
        num = int(size.lstrip("#"))
    else:
        num = int(size)
    if num < 0 or num > 4:
        raise ValueError(f"phillips size must be #0..#4, got {size!r}")
    return num


class ScrewDrive:
    """Driver-recess masks and their dimensional helpers (BOSL2 screw_drive.scad).

    Every ``*_mask`` method returns a :class:`~bosl2.shapes3d.Bosl2Solid` positioned with its recess
    opening at the top and its bottom on the XY plane (BOSL2's ``anchor=BOTTOM``); subtract it from a
    screw head to cut the recess. Pass ``center=True`` to center the mask vertically instead.
    """

    # ---- Phillips --------------------------------------------------------

    @staticmethod
    def phillips_mask(size="#2", center: bool = False, _fn: int = 36) -> Bosl2Solid:
        """A Phillips driver-recess mask for the given Phillips *size* (BOSL2 phillips_mask()).

        Args:
            size: bit size as ``"#0"``..``"#4"`` or an integer ``0``..``4``.
            center: center the mask vertically (default: bottom on the XY plane).
            _fn: facet count for the revolved body.

        Examples:
            A #2 Phillips recess cut into a tapered head:

            .. pythonscad-example::

                from bosl2.screw_drive import ScrewDrive
                (s3.cyl(d1=2, d2=8, h=4).down(2) - ScrewDrive.phillips_mask(size="#2")).show()
        """
        spec = _PHILLIPS[_phillips_num(size)]
        shaft, b, e, g = spec.shaft, spec.b, spec.e, spec.g
        alpha, beta, gamma = spec.alpha, spec.beta, _PH_GAMMA

        h1 = _adj_ang_to_opp(g / 2, _PH_BOT_ANGLE)              # height of the small conical tip
        h2 = _adj_ang_to_opp((shaft - g) / 2, 90 - _PH_SIDE_ANGLE)  # height of the larger cone
        length = h1 + h2
        h3 = _adj_ang_to_opp(b / 2, _PH_BOT_ANGLE)             # height where the cutout starts

        p0 = [0.0, 0.0]
        p1 = [_adj_ang_to_opp(e / 2, 90 - alpha / 2), -e / 2]
        p2 = [p1[0] + _adj_ang_to_opp((shaft - e) / 2, 90 - gamma / 2), p1[1] - (shaft - e) / 2]
        cut_path = [p0, p1, p2, [p2[0], -p2[1]], [p1[0], -p1[1]]]

        # One cutout wing: extruded profile, dropped 1mm, tilted by beta, raised to h3.
        wing = _opolygon(cut_path).linear_extrude(height=length + 2)
        wing = wing.translate([0, 0, -1]).rotate([0, beta, 0]).translate([0, 0, h3])
        cutter = _union(wing.multmatrix(m.tolist()) for m in zrot_copies(n=4, r=b / 2))
        cutter = cutter.rotate([0, 0, 45])

        body = _orotate_extrude(_opolygon([[0, 0], [g / 2, h1], [shaft / 2, length], [0, length]]), fn=_fn)
        mask = Bosl2Solid(body - cutter, size=[shaft, shaft, length])
        return mask.down(length / 2) if center else mask

    @staticmethod
    def phillips_depth(size, d: float):
        """Recess depth needed to reach diameter *d* for a Phillips *size*, or ``None`` (BOSL2 phillips_depth())."""
        spec = _PHILLIPS[_phillips_num(size)]
        shaft, g = spec.shaft, spec.g
        h1 = _adj_ang_to_opp(g / 2, _PH_BOT_ANGLE)
        if d >= shaft or d < g:
            return None
        return (d - g) / 2 / math.tan(math.radians(_PH_SIDE_ANGLE)) + h1

    @staticmethod
    def phillips_diam(size, depth: float):
        """Recess diameter at the top when cut to *depth* for a Phillips *size*, or ``None`` (BOSL2 phillips_diam())."""
        spec = _PHILLIPS[_phillips_num(size)]
        shaft, g = spec.shaft, spec.g
        h1 = _adj_ang_to_opp(g / 2, _PH_BOT_ANGLE)
        h2 = _adj_ang_to_opp((shaft - g) / 2, 90 - _PH_SIDE_ANGLE)
        if depth < h1 or depth >= h1 + h2:
            return None
        return 2 * math.tan(math.radians(_PH_SIDE_ANGLE)) * (depth - h1) + g

    # ---- Hex (Allen) -----------------------------------------------------

    @staticmethod
    def hex_drive_mask(size: float, length: float, slop: float = 0.0,
                       center: bool = False) -> Bosl2Solid:
        """A hex (Allen) driver-recess mask, *size* across flats, *length* tall (BOSL2 hex_drive_mask()).

        The recess is slightly oversized per the ISO standard; *slop* enlarges it by a further
        ``2 * slop``.
        """
        realsize = 1.0072 * size + 0.0341 + 2 * slop   # empirical fit to the ISO standard
        solid = hexagon(id=realsize).linear_extrude(height=length, center=center)
        return Bosl2Solid(solid, size=[realsize, realsize, length])

    # ---- Torx ------------------------------------------------------------

    @staticmethod
    def torx_info(size: int) -> TorxSpec:
        """The :class:`TorxSpec` (od/id/depth/tip_rounding/inner_rounding) for a Torx *size* (BOSL2 torx_info())."""
        try:
            return _TORX[int(size)]
        except (KeyError, ValueError):
            raise ValueError(f"Unsupported Torx size: {size!r}")

    @staticmethod
    def torx_diam(size: int) -> float:
        """Outer diameter of a Torx *size* profile (BOSL2 torx_diam())."""
        return ScrewDrive.torx_info(size).od

    @staticmethod
    def torx_depth(size: int) -> float:
        """Typical drive-hole depth for a Torx *size* (BOSL2 torx_depth())."""
        return ScrewDrive.torx_info(size).depth

    @staticmethod
    def torx_mask2d(size: int) -> Bosl2Solid:
        """The 2-D profile of a Torx *size* driver (BOSL2 torx_mask2d())."""
        return Bosl2Solid(ScrewDrive._torx_profile(size))

    @staticmethod
    def _torx_profile(size: int):
        spec = ScrewDrive.torx_info(size)
        od, id_, tip, rounding = spec.od, spec.id, spec.tip_rounding, spec.inner_rounding
        base = od - 2 * tip
        fn = int(_quantup(_frag_count(od / 2), 12))

        # Six outward lobes: two rotated copies of a hull of three tip circles, plus the base circle.
        tip_circles = [circle(r=tip, _fn=fn // 2).translate([base / 2, 0]).multmatrix(m.tolist())
                       for m in zrot_copies(n=3)]
        tri = _ohull(*tip_circles)
        lobes = _union(tri.multmatrix(m.tolist()) for m in zrot_copies(n=2))
        solid = circle(d=base, _fn=fn) | lobes

        # Six inner rounding cutouts.
        cut = _union(
            circle(r=rounding, _fn=fn).translate([id_ / 2 + rounding, 0])
            .rotate([0, 0, 180 / 6]).multmatrix(m.tolist())
            for m in zrot_copies(n=6)
        )
        return solid - cut

    @staticmethod
    def torx_mask(size: int, length: float = 5.0, center: bool = False) -> Bosl2Solid:
        """A Torx driver-recess mask: the 2-D profile extruded *length* tall (BOSL2 torx_mask()).

        Examples:
            A T30 Torx tip:

            .. pythonscad-example::

                from bosl2.screw_drive import ScrewDrive
                ScrewDrive.torx_mask(size=30, length=10).show()
        """
        od = ScrewDrive.torx_diam(size)
        solid = ScrewDrive._torx_profile(size).linear_extrude(height=length, center=center)
        return Bosl2Solid(solid, size=[od, od, length])

    # ---- Robertson / square ---------------------------------------------

    @staticmethod
    def robertson_mask(size: int, extra: float = 1.0, ang: float = 2.5,
                       slop: float = 0.0) -> Bosl2Solid:
        """A Robertson/square driver-recess mask for square-drive *size* ``0``..``4`` (BOSL2 robertson_mask()).

        Args:
            size: square-drive size, an integer ``0``..``4``.
            extra: extra length of drive mask beyond the nominal depth.
            ang: taper angle of each face (default 2.5, from BOSL2's print tests).
            slop: enlarge the recess by ``2 * slop``.
        """
        if not (isinstance(size, int) and 0 <= size <= 4):
            raise ValueError(f"robertson size must be an int 0..4, got {size!r}")
        spec = _ROBERTSON[size]
        M = spec.m * INCH   # across flats
        T = spec.t * INCH   # depth
        F = spec.f * INCH   # flat-to-taper transition
        h = T + extra
        m_slop = M + 2 * slop
        m_top = m_slop + 2 * _adj_ang_to_opp(F + extra, ang)
        m_bot = m_slop - 2 * _adj_ang_to_opp(T - F, ang)
        tapered = prismoid([m_bot, m_bot], [m_top, m_top], h=h, anchor=BOTTOM)
        cone = cyl(d1=0, d2=m_slop / (T - F) * math.sqrt(2) * h, h=h, anchor=BOTTOM)
        return (tapered & cone).down(T)

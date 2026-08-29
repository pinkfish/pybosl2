# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# mypy: allow-untyped-defs

# LibFile: pybosl2/parts/gears.py
#    Pure-Python port of the core of BOSL2's (current) gears.scad. Gears are sized by circular pitch
#    (``circ_pitch``), metric ``mod``, or ``diam_pitch``; the default 20-degree pressure angle and
#    ``profile_shift=None`` (which corrects undercut on low-tooth-count gears) match BOSL2. The
#    :class:`SpurGear2d` / :class:`SpurGear` teeth are generated the way BOSL2 does it:
#    the involute working flank plus the trochoid that a meshing rack would carve, so low-tooth gears
#    get a real undercut. :class:`HerringboneGear`, the linear :class:`Rack`, the
#    internal :class:`RingGear`, the :class:`BevelGear` and the :class:`Worm` /
#    :class:`WormGear` pair are ported too, along with the dimension helpers and
#    :func:`gear_dist` (meshing-distance) / :func:`auto_profile_shift`.
#
#    Bevel/worm sweep a simpler symmetric involute tooth (no undercut modelling) -- fine for those
#    swept 3-D forms.
#
#    Note: the helical *sign* sets the twist handedness of a 3-D gear directly here; BOSL2 reaches the
#    same geometry via an internal helical inversion, so a given ``helical`` value may produce the
#    opposite hand from BOSL2. A helical gear still meshes its opposite-hand mate either way.
#
# FileSummary: Gears: spur (with undercut), helical, herringbone, rack, ring, bevel, worm.
# DocCategory: Parts library
# FileGroup: BOSL2

"""Gears: spur (with undercut), helical, herringbone, rack, ring, bevel, worm."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from pybosl2._backend import csg_part
from pybosl2._helpers import frag_count as _frag_count
from pybosl2._native import native
from pybosl2.caps import CapType
from pybosl2.constants import INCH
from pybosl2.enums import VNFStyle
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.math import lerp as _math_lerp
from pybosl2.parts._buildable import Buildable
from pybosl2.path2d import Path2D
from pybosl2.shapes3d import cylinder
from pybosl2.solid import cyl
from pybosl2.solid import cylinder as facade_cylinder
from pybosl2.vectors import v_theta as _v_theta
from pybosl2.vnf import VNF

if TYPE_CHECKING:  # real stub-typed imports for the checker (identical to pre-lazy)
    from pythonscad import polygon as _opolygon

    from pybosl2._backend import Solid
    from pybosl2.regions import Region
else:
    _opolygon = native("polygon")

__all__ = [
    "BevelGear",
    "GearSpec",
    "GearToothProfile",
    "HerringboneGear",
    "Rack",
    "Rack2d",
    "RingGear",
    "SpurGear",
    "SpurGear2d",
    "Worm",
    "WormGear",
]

PI = math.pi


# ---------------------------------------------------------------------------
# Section: pitch / module resolution and the derived radii (BOSL2 gears.scad)
# ---------------------------------------------------------------------------


def _circular_pitch(
    circ_pitch: float | None = None,
    mod: float | None = None,
    pitch: float | None = None,
    diam_pitch: float | None = None,
) -> float:
    """Resolve the circular pitch from any of the accepted pitch inputs (BOSL2 circular_pitch()).

    When none is given, defaults to a circular pitch of 5 (like BOSL2's ``mod``-ish default gear).
    """
    if pitch is not None:
        return pitch
    if circ_pitch is not None:
        return circ_pitch
    if diam_pitch is not None:
        return PI / diam_pitch * INCH
    if mod is not None:
        return mod * PI
    return 5.0


def _module_value(circ_pitch: float) -> float:
    return circ_pitch / PI


def _pitch_radius(circ_pitch: float, teeth: int, helical: float = 0) -> float:
    return circ_pitch * teeth / PI / 2 / math.cos(math.radians(helical))


def _adendum(circ_pitch: float, profile_shift: float = 0, shorten: float = 0) -> float:
    return _module_value(circ_pitch) * (1 + profile_shift - shorten)


def _dedendum(circ_pitch: float, clearance: float | None = None, profile_shift: float = 0) -> float:
    mod = _module_value(circ_pitch)
    clear = 0.25 * mod if clearance is None else clearance
    return mod * (1 - profile_shift) + clear


def _base_radius(circ_pitch: float, teeth: int, pressure_angle: float = 20, helical: float = 0) -> float:
    trans_pa = math.degrees(math.atan(math.tan(math.radians(pressure_angle)) / math.cos(math.radians(helical))))
    return _pitch_radius(circ_pitch, teeth, helical) * math.cos(math.radians(trans_pa))


def _root_radius_basic(
    circ_pitch: float,
    teeth: int,
    clearance: float | None = None,
    internal: bool = False,
    helical: float = 0,
    profile_shift: float = 0,
) -> float:
    pr = _pitch_radius(circ_pitch, teeth, helical)
    return pr - (_adendum(circ_pitch, -profile_shift) if internal else _dedendum(circ_pitch, clearance, profile_shift))


def _outer_radius_basic(
    circ_pitch: float,
    teeth: int,
    clearance: float | None = None,
    internal: bool = False,
    helical: float = 0,
    profile_shift: float = 0,
    shorten: float = 0,
) -> float:
    pr = _pitch_radius(circ_pitch, teeth, helical)
    return pr + (
        _dedendum(circ_pitch, clearance, -profile_shift) if internal else _adendum(circ_pitch, profile_shift, shorten)
    )


def _auto_profile_shift(
    teeth: int,
    pressure_angle: float = 20,
    helical: float = 0,
    profile_shift: float | None = None,
) -> float:
    """Minimum profile shift to avoid undercut, or the given value (BOSL2 auto_profile_shift())."""
    if isinstance(profile_shift, (int, float)):
        return float(profile_shift)
    if teeth == 0:
        return 0.0
    pa = math.atan(math.tan(math.radians(pressure_angle)) / math.cos(math.radians(helical)))
    min_teeth = 2 / math.sin(pa) ** 2
    if teeth > math.floor(min_teeth):
        return 0.0
    return (1 - teeth / min_teeth) / math.cos(math.radians(helical))


# ---------------------------------------------------------------------------
# Section: 2-D geometry helpers for the tooth generator
# ---------------------------------------------------------------------------


def _involute(base_r: float, a_deg: float) -> list[float]:
    b = a_deg * PI / 180
    ar = math.radians(a_deg)
    return [
        base_r * (math.cos(ar) + b * math.sin(ar)),
        base_r * (math.sin(ar) - b * math.cos(ar)),
    ]


def _xy_to_polar(xy: list[float]) -> list[float]:
    return [math.hypot(xy[0], xy[1]), math.degrees(math.atan2(xy[1], xy[0]))]


def _p2xy(r: float, angle: float) -> list[float]:
    a = math.radians(angle)
    return [r * math.cos(a), r * math.sin(a)]


def _lookup(x: float, table: list[list[float]]) -> float:
    xs = [t[0] for t in table]
    ys = [t[1] for t in table]
    if xs[0] > xs[-1]:
        xs, ys = xs[::-1], ys[::-1]
    return float(np.interp(x, xs, ys))


def _zrot_pts(pts: list[list[float]], angle: float) -> list[list[float]]:
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    return [[x * c - y * s, x * s + y * c] for x, y in pts]


def _line_isect(l1: list[list[float]], l2: list[list[float]]) -> list[float]:
    (x1, y1), (x2, y2) = l1[0], l1[1]
    (x3, y3), (x4, y4) = l2[0], l2[1]
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        return [float(l1[1][0]), float(l1[1][1])]
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / den
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / den
    return [px, py]


def _vector_angle(three: list[list[float]]) -> float:
    from pybosl2.geometry import vector_angle3

    return vector_angle3(three[0], three[1], three[2])


def _arc_corner(n: int, r: float, corner: list[list[float]]) -> list[list[float]]:
    """n-point arc of radius r rounding the corner ``[p0, p1, p2]`` (BOSL2 arc(corner=))."""
    p0, p1, p2 = (np.asarray(p, float) for p in corner)
    u0 = (p0 - p1) / np.linalg.norm(p0 - p1)
    u1 = (p2 - p1) / np.linalg.norm(p2 - p1)
    half = math.acos(np.clip(np.dot(u0, u1), -1, 1)) / 2
    if half <= 1e-9:
        return [p1.tolist()]
    center = p1 + (u0 + u1) / np.linalg.norm(u0 + u1) * (r / math.sin(half))
    t0, t1 = p1 + u0 * (r / math.tan(half)), p1 + u1 * (r / math.tan(half))
    a0 = math.atan2(t0[1] - center[1], t0[0] - center[0])
    a1 = math.atan2(t1[1] - center[1], t1[0] - center[0])
    da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    return [
        [
            center[0] + r * math.cos(a0 + da * i / n),
            center[1] + r * math.sin(a0 + da * i / n),
        ]
        for i in range(n + 1)
    ]


def _dedup(pts: list[list[float]], eps: float = 1e-9) -> list[list[float]]:
    from pybosl2.path2d import Path2D

    return [list(p) for p in Path2D._deduplicate(pts, closed=False, eps=eps)]


def _norm2(v: list[float]) -> float:
    return math.hypot(v[0], v[1])


def _strip_left(path: list[list[float]], undercut_max: float) -> list[list[float]]:
    """Remove the inward 'jaggies' the undercut can leave (BOSL2 strip_left)."""
    out = []
    i = 0
    sides = len(path)
    while i < sides:
        p = path[i]
        if _norm2(p) >= undercut_max:
            out += [list(q) for q in path[i:]]
            break
        out.append(list(p))
        angs = [
            _v_theta([path[j][0] - p[0], path[j][1] - p[1]])
            for j in range(i + 1, sides)
            if _norm2(path[j]) < undercut_max
        ]
        if not angs:
            i += 1
        else:
            i += int(np.argmin(angs)) + 1
    return out


# ---------------------------------------------------------------------------
# Section: the involute gear tooth (BOSL2 _gear_tooth_profile), with undercut
# ---------------------------------------------------------------------------


def _gear_tooth_profile(
    circ_pitch: float,
    teeth: int,
    pressure_angle: float = 20,
    clearance: float | None = None,
    backlash: float = 0.0,
    helical: float = 0,
    internal: bool = False,
    profile_shift: float = 0.0,
    shorten: float = 0,
    center: bool = False,
    steps: int = 16,
) -> list[list[float]]:
    pa = pressure_angle
    mod = _module_value(circ_pitch)
    clear = 0.25 * mod if clearance is None else clearance
    arad = _outer_radius_basic(circ_pitch, teeth, None, internal, helical, profile_shift, shorten)
    prad = _pitch_radius(circ_pitch, teeth, helical)
    brad = _base_radius(circ_pitch, teeth, pa, helical)
    rrad = _root_radius_basic(circ_pitch, teeth, clear, internal, helical, profile_shift)
    _srad = max(rrad, brad)
    tthick = circ_pitch / PI / math.cos(math.radians(helical)) * (
        PI / 2 + 2 * profile_shift * math.tan(math.radians(pa))
    ) + (backlash if internal else -backlash)
    tang = tthick / prad / 2 * 180 / PI

    involute_lup: list[list[float]] = []
    i = 0.0
    end = arad / PI / brad * 360
    while i <= end:
        pol = _xy_to_polar(_involute(brad, i))
        if pol[0] <= arad * 1.1:
            involute_lup.append([pol[0], 90 - pol[1]])
        i += 5
    involute_rlup = [[y, x] for x, y in involute_lup]

    b_ang = _lookup(brad, involute_lup)
    p_ang = _lookup(prad, involute_lup)
    soff = tang + (b_ang - p_ang)
    ma_rad = min(arad, _lookup(90 - soff + 0.05 * 360 / teeth / 2, involute_rlup))
    ma_ang = _lookup(ma_rad, involute_lup)
    cap_steps = max(1, math.ceil((ma_ang + soff - 90) / 5))
    cap_step = (ma_ang + soff - 90) / cap_steps
    ax = circ_pitch / 4 - (circ_pitch / PI) * math.tan(math.radians(pa))

    undercut = []
    a = math.degrees(math.atan2(ax, rrad))
    while a >= -90:
        bx = -a / 360 * 2 * PI * prad
        pol = _xy_to_polar([bx + ax, prad - circ_pitch / PI + profile_shift * circ_pitch / PI])
        if pol[0] < arad * 1.05:
            undercut.append([pol[0], pol[1] - a + 180 / teeth])
        a -= 1
    if undercut:
        uc_min = int(np.argmin([u[0] for u in undercut]))
        undercut_lup = undercut[uc_min:]
    else:
        undercut_lup = [[rrad, 0.0]]

    us = [k / steps / 2 for k in range(steps * 2 + 1)]

    def flank_angle(r: float) -> tuple[float, float, bool]:
        a1 = _lookup(r, involute_lup) + soff
        if internal or r < undercut_lup[0][0]:
            return a1, a1, False
        a2 = _lookup(r, undercut_lup)
        return min(a1, a2), a2, a1 > a2

    undercut_max = 0.0
    for u in us:
        radius = _lerp(rrad, ma_rad, u)
        aa, _a2, use_uc = flank_angle(radius)
        if aa < 90 + 180 / teeth and use_uc:
            undercut_max = max(undercut_max, radius)

    tooth_half_raw = []
    for u in us:
        radius = _lerp(rrad, ma_rad, u)
        aa, _a2, _uc = flank_angle(radius)
        if (internal or radius > rrad + clear) and (not internal or radius < ma_rad - clear) and aa < 90 + 180 / teeth:
            tooth_half_raw.append(_p2xy(radius, aa))
    if not internal:
        for k in range(cap_steps):
            tooth_half_raw.append(_p2xy(ma_rad, ma_ang + soff - k * (cap_step - 1)))

    if len(tooth_half_raw) < 2:
        tooth_half_raw += [_p2xy(ma_rad, 90)]

    rcircum = 2 * PI * (ma_rad if internal else rrad)
    rpart = (180 / teeth - tang) / 360
    if internal:
        line1 = tooth_half_raw[-2:]
        line2 = [[0, ma_rad], [-1, ma_rad]]
    else:
        line1 = tooth_half_raw[0:2]
        line2 = _zrot_pts([[0, rrad], [1, rrad]], 180 / teeth)
    isect_pt = _line_isect(line1, line2)
    rcorner = [tooth_half_raw[-1], isect_pt, line2[0]] if internal else [line2[0], isect_pt, line1[0]]
    maxr = _norm2([rcorner[0][0] - rcorner[1][0], rcorner[0][1] - rcorner[1][1]]) * math.tan(
        math.radians(_vector_angle(rcorner) / 2)
    )
    round_r = min(maxr, clear, rcircum * rpart)

    rounded: list[list[float]] = []
    if not internal:
        rounded += _arc_corner(8, round_r, rcorner) if round_r > 0 else [isect_pt]
    rounded += tooth_half_raw
    if internal:
        rounded += _arc_corner(8, round_r, rcorner) if round_r > 0 else [isect_pt]
    rounded = _dedup(rounded)

    tooth_half = _strip_left(rounded, undercut_max) if undercut_max else rounded

    invalid = [
        i2
        for i2 in range(len(tooth_half))
        if math.degrees(math.atan2(tooth_half[i2][1], tooth_half[i2][0])) > 90 + 180 / teeth
    ]
    if invalid:
        ind = invalid[-1]
        ipt = _line_isect([[0, 0], _p2xy(1, 90 + 180 / teeth)], tooth_half[ind : ind + 2])
        clipped = [ipt] + [list(q) for q in tooth_half[ind + 1 :]]
    else:
        clipped = tooth_half

    full = _dedup([list(q) for q in clipped] + [[-x, y] for x, y in reversed(clipped)])
    merged = Path2D(full).merge_collinear(closed=False)
    if center:
        merged = [[x, y - prad] for x, y in merged]  # type: ignore[assignment]
    return [[float(x), float(y)] for x, y in merged]


def _lerp(a: float, b: float, v: float) -> float:
    return float(_math_lerp(a, b, v))


# ---------------------------------------------------------------------------
# Section: matrix / VNF helpers for the 3-D bevel and worm gears
# ---------------------------------------------------------------------------


def _polar(r: float, t_deg: float) -> list[float]:
    a = math.radians(t_deg)
    return [r * math.sin(a), r * math.cos(a)]


def _iang(radius1: float, radius2: float) -> float:
    return math.degrees(math.sqrt((radius2 / radius1) ** 2 - 1) - math.acos(radius1 / radius2))


def _q6(b: float, s: float, t: float, d: float) -> list[float]:
    return _polar(d, s * (_iang(b, d) + t))


def _q7(f: float, r: float, b: float, radius2: float, t: float, s: float) -> list[float]:
    return _q6(b, s, t, (1 - f) * max(b, r) + f * radius2)


def _rot2d(pts: list[list[float]], ang_deg: float) -> list[list[float]]:
    a = math.radians(ang_deg)
    c, s = math.cos(a), math.sin(a)
    return [[x * c - y * s, x * s + y * c] for x, y in pts]


def _polar_xy(r: float, angle: float) -> np.ndarray[tuple[int, ...], np.dtype[np.float64]]:
    a = math.radians(angle)
    return np.array([r * math.cos(a), r * math.sin(a)])


def _law_of_cosines(a: float, b: float, c: float) -> float:
    return math.degrees(math.acos(max(-1.0, min(1.0, (a * a + b * b - c * c) / (2 * a * b)))))


def _opp_ang_to_hyp(opp: float, angle: float) -> float:
    return opp / math.sin(math.radians(angle))


def _m_up(z: float) -> np.ndarray[tuple[int, int], np.dtype[np.float64]]:
    m = np.eye(4)
    m[2, 3] = z
    return m


def _m_back(y: float) -> np.ndarray[tuple[int, int], np.dtype[np.float64]]:
    m = np.eye(4)
    m[1, 3] = y
    return m


def _m_move(v: list[float]) -> np.ndarray[tuple[int, int], np.dtype[np.float64]]:
    m = np.eye(4)
    m[0, 3], m[1, 3], m[2, 3] = v[0], v[1], v[2]
    return m


def _m_zrot(deg: float) -> np.ndarray[tuple[int, int], np.dtype[np.float64]]:
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    m[0, 0] = c
    m[0, 1] = -s
    m[1, 0] = s
    m[1, 1] = c
    return m


def _m_xrot(deg: float) -> np.ndarray[tuple[int, int], np.dtype[np.float64]]:
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    m[1, 1] = c
    m[1, 2] = -s
    m[2, 1] = s
    m[2, 2] = c
    return m


def _m_scale(u: float) -> np.ndarray[tuple[int, int], np.dtype[np.float64]]:
    return np.diag([u, u, u, 1.0])


def _m_xflip() -> np.ndarray[tuple[int, int], np.dtype[np.float64]]:
    m = np.eye(4)
    m[0, 0] = -1
    return m


def _apply(
    m: np.ndarray[tuple[int, int], np.dtype[np.float64]],
    pts: list[list[float]],
) -> list[list[float]]:
    arr = np.c_[np.asarray(pts, dtype=float), np.ones(len(pts))]
    return (arr @ m.T)[:, :3].tolist()  # type: ignore[no-any-return]


def _vnf_join(vnfs: list[VNF]) -> VNF:
    verts: list[list[float]] = []
    faces: list[list[int]] = []
    for v in vnfs:
        off = len(verts)
        verts += [list(p) for p in v.vertices]
        faces += [[i + off for i in f] for f in v.faces]
    return VNF(verts, faces)


def _vnf_xflip(vnf: VNF) -> VNF:
    return VNF([[-x, y, z] for x, y, z in vnf.vertices], [f[::-1] for f in vnf.faces])


def _simple_tooth(
    circ_pitch: float,
    teeth: int,
    pressure_angle: float,
    clearance: float | None = None,
    backlash: float = 0.0,
    interior: bool = False,
    center: bool = False,
) -> list[list[float]]:
    """Return a simple symmetric involute tooth (the older BOSL2 profile) for the swept bevel/worm forms."""
    p = _pitch_radius(circ_pitch, teeth)
    c = _outer_radius_basic(circ_pitch, teeth, clearance, interior, 0, 0, 0)
    radius = _root_radius_basic(circ_pitch, teeth, clearance, interior, 0, 0)
    b = p * math.cos(math.radians(pressure_angle))
    t = circ_pitch / 2 - backlash / 2
    k = -_iang(b, p) - math.degrees(t / 2 / p)
    isteps = 5
    pts = [_polar(radius, -k if radius >= b else 180 / teeth)]
    pts += [_q7(i / isteps, radius, b, c, k, -1) for i in range(isteps + 1)]
    pts += [_q7(i / isteps, radius, b, c, k, 1) for i in range(isteps, -1, -1)]
    pts.append(_polar(radius, k if radius >= b else -180 / teeth))
    if center:
        pts = [[x, y - p] for x, y in pts]
    return pts


# ---------------------------------------------------------------------------
# Section: gear specification dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GearSpec:
    """Resolved gear pitch and radius dimensions.

    Construct from any pitch specification: ``GearSpec(pitch=5, teeth=20)``,
    ``GearSpec(mod=2, teeth=30, helical=15)``, etc.
    """

    teeth: int
    circ_pitch: float
    pressure_angle: float = 20
    helical: float = 0
    clearance: float | None = None
    internal: bool = False
    profile_shift: float = 0.0
    shorten: float = 0

    def __init__(
        self,
        teeth: int,
        circ_pitch: float | None = None,
        mod: float | None = None,
        pitch: float | None = None,
        diam_pitch: float | None = None,
        pressure_angle: float = 20,
        clearance: float | None = None,
        internal: bool = False,
        helical: float = 0,
        profile_shift: float | None = None,
        shorten: float = 0,
    ) -> None:
        """Resolve pitch inputs and auto-correct profile shift for undercut.

        Args:
            teeth: Number of teeth on the gear.
            circ_pitch: Circular pitch in mm/tooth.
            mod: Metric module (mm/tooth).
            pitch: Circular pitch alias.
            diam_pitch: Diametral pitch (teeth per inch of pitch diameter).
            pressure_angle: Pressure angle in degrees.
            clearance: Clearance, or None for default (0.25 * module).
            internal: True for internal (ring) gears.
            helical: Helical angle in degrees.
            profile_shift: Explicit profile shift, or None for auto correction.
            shorten: Amount to shorten the teeth.

        Returns:
            None

        """
        object.__setattr__(self, "teeth", teeth)
        object.__setattr__(self, "pressure_angle", pressure_angle)
        object.__setattr__(self, "helical", helical)
        object.__setattr__(self, "clearance", clearance)
        object.__setattr__(self, "internal", internal)
        object.__setattr__(self, "shorten", shorten)
        cp = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        object.__setattr__(self, "circ_pitch", cp)
        ps = _auto_profile_shift(teeth, pressure_angle, helical, profile_shift)
        object.__setattr__(self, "profile_shift", ps)

    @property
    def module(self) -> float:
        """Metric module (mm)."""
        return _module_value(self.circ_pitch)

    @property
    def pitch_radius(self) -> float:
        """Pitch-circle radius."""
        return _pitch_radius(self.circ_pitch, self.teeth, self.helical)

    @property
    def outer_radius(self) -> float:
        """Outer (tip) radius."""
        return _outer_radius_basic(
            self.circ_pitch,
            self.teeth,
            self.clearance,
            self.internal,
            self.helical,
            self.profile_shift,
            self.shorten,
        )

    @property
    def root_radius(self) -> float:
        """Root radius."""
        return _root_radius_basic(
            self.circ_pitch,
            self.teeth,
            self.clearance,
            self.internal,
            self.helical,
            self.profile_shift,
        )

    @property
    def base_radius(self) -> float:
        """Base-circle radius of the involute."""
        return _base_radius(self.circ_pitch, self.teeth, self.pressure_angle, self.helical)

    @property
    def diametral_pitch(self) -> float:
        """Diametral pitch (teeth per inch of pitch diameter)."""
        return PI / self.circ_pitch

    @staticmethod
    def circular_pitch(
        circ_pitch: float | None = None,
        mod: float | None = None,
        pitch: float | None = None,
        diam_pitch: float | None = None,
    ) -> float:
        """Circular pitch (mm/tooth) from any pitch input.

        Args:
            circ_pitch: Circular pitch in mm/tooth.
            mod: Metric module (mm/tooth).
            pitch: Circular pitch alias.
            diam_pitch: Diametral pitch (teeth per inch of pitch diameter).

        Returns:
            Resolved circular pitch in mm/tooth.

        """
        return _circular_pitch(circ_pitch, mod, pitch, diam_pitch)

    @staticmethod
    def pitch_value(mod: float) -> float:
        """Circular pitch from the metric module.

        Args:
            mod: Metric module (mm/tooth).

        Returns:
            Circular pitch in mm/tooth.

        """
        return mod * PI

    @staticmethod
    def module_value(
        circ_pitch: float | None = None,
        mod: float | None = None,
        pitch: float | None = None,
        diam_pitch: float | None = None,
    ) -> float:
        """Metric module from any pitch input.

        Args:
            circ_pitch: Circular pitch in mm/tooth.
            mod: Metric module (mm/tooth).
            pitch: Circular pitch alias.
            diam_pitch: Diametral pitch (teeth per inch of pitch diameter).

        Returns:
            Metric module value.

        """
        return _module_value(_circular_pitch(circ_pitch, mod, pitch, diam_pitch))

    @staticmethod
    def diametral_pitch_func(
        circ_pitch: float | None = None,
        mod: float | None = None,
        pitch: float | None = None,
        diam_pitch: float | None = None,
    ) -> float:
        """Diametral pitch (teeth per inch of pitch diameter) from any pitch input.

        Args:
            circ_pitch: Circular pitch in mm/tooth.
            mod: Metric module (mm/tooth).
            pitch: Circular pitch alias.
            diam_pitch: Diametral pitch (teeth per inch of pitch diameter).

        Returns:
            Diametral pitch value.

        """
        return PI / _circular_pitch(circ_pitch, mod, pitch, diam_pitch)

    @staticmethod
    def auto_profile_shift(
        teeth: int,
        pressure_angle: float = 20,
        helical: float = 0,
        profile_shift: float | None = None,
    ) -> float:
        """Minimum profile shift (modules) to avoid undercut.

        Args:
            teeth: Number of teeth on the gear.
            pressure_angle: Pressure angle in degrees.
            helical: Helical angle in degrees.
            profile_shift: Explicit profile shift override, or None for auto.

        Returns:
            Profile shift value (modules).

        """
        return _auto_profile_shift(teeth, pressure_angle, helical, profile_shift)

    @staticmethod
    def bevel_pitch_angle(teeth: int, mate_teeth: float, drive_angle: float = 90) -> float:
        """Pitch angle (deg) for a bevel gear meshing another.

        Args:
            teeth: Number of teeth on the gear.
            mate_teeth: Number of teeth on the mating gear.
            drive_angle: Shaft angle between gears in degrees.

        Returns:
            Pitch angle in degrees.

        """
        return math.degrees(
            math.atan2(math.sin(math.radians(drive_angle)), (mate_teeth / teeth) + math.cos(math.radians(drive_angle)))
        )

    @staticmethod
    def worm_gear_thickness(
        circ_pitch: float | None = None,
        teeth: int = 30,
        worm_diam: float = 30,
        worm_arc: float = 60,
        crowning: float = 1,
        clearance: float | None = None,
        mod: float | None = None,
        pitch: float | None = None,
        diam_pitch: float | None = None,
    ) -> float:
        """Thickness of a worm gear matched to a worm.

        Args:
            circ_pitch: Circular pitch in mm/tooth.
            teeth: Number of teeth on the worm gear.
            worm_diam: Diameter of the mating worm.
            worm_arc: Arc angle the worm gear wraps around the worm.
            crowning: Crowning amount.
            clearance: Clearance, or None for default.
            mod: Metric module (mm/tooth).
            pitch: Circular pitch alias.
            diam_pitch: Diametral pitch (teeth per inch of pitch diameter).

        Returns:
            Worm gear thickness in mm.

        """
        center = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        radius = worm_diam / 2 + crowning
        pitch_thick = radius * math.sin(math.radians(worm_arc / 2)) * 2
        pr = _pitch_radius(center, teeth)
        rr = pr - _dedendum(center, clearance)
        pitchoff = (pr - rr) * math.sin(math.radians(worm_arc / 2))
        return pitch_thick + 2 * pitchoff

    @staticmethod
    def gear_dist(
        teeth1: int,
        teeth2: int,
        helical: float = 0,
        profile_shift1: float | None = None,
        profile_shift2: float | None = None,
        internal1: bool = False,
        internal2: bool = False,
        backlash: float = 0,
        pressure_angle: float = 20,
        circ_pitch: float | None = None,
        mod: float | None = None,
        diam_pitch: float | None = None,
    ) -> float:
        """Center-to-center distance for two meshing gears.

        Args:
            teeth1: Number of teeth on the first gear.
            teeth2: Number of teeth on the second gear.
            helical: Helical angle in degrees.
            profile_shift1: Profile shift for the first gear, or None for auto.
            profile_shift2: Profile shift for the second gear, or None for auto.
            internal1: True if the first gear is an internal (ring) gear.
            internal2: True if the second gear is an internal (ring) gear.
            backlash: Backlash amount in mm.
            pressure_angle: Pressure angle in degrees.
            circ_pitch: Circular pitch in mm/tooth.
            mod: Metric module (mm/tooth).
            diam_pitch: Diametral pitch (teeth per inch of pitch diameter).

        Returns:
            Center-to-center meshing distance in mm.

        """
        m_val = _module_value(_circular_pitch(circ_pitch, mod, None, diam_pitch))
        ps1 = _auto_profile_shift(teeth1, pressure_angle, helical, profile_shift1)
        ps2 = _auto_profile_shift(teeth2, pressure_angle, helical, profile_shift2)
        t1 = -teeth1 if internal2 else teeth1
        t2 = -teeth2 if internal1 else teeth2
        if internal2:
            ps1 = -ps1
        if internal1:
            ps2 = -ps2
        if teeth1 == 0 or teeth2 == 0:
            return _pitch_radius(m_val * PI, t1 + t2, helical) + (ps1 + ps2) * m_val
        pa = math.radians(pressure_angle)
        pa_transv = math.atan(math.tan(pa) / math.cos(math.radians(helical)))

        def inv(a: float) -> float:
            return math.tan(a) - a

        target = inv(pa_transv) + 2 * (ps1 + ps2) / (t1 + t2) * math.tan(pa)
        lo, hi = 1e-4, math.radians(89)
        for _ in range(60):
            mid = (lo + hi) / 2
            if inv(mid) < target:
                lo = mid
            else:
                hi = mid
        pa_eff = (lo + hi) / 2
        diameter = m_val * (t1 + t2) * math.cos(pa_transv) / math.cos(pa_eff) / math.cos(math.radians(helical)) / 2
        return diameter + (-1 if (internal1 or internal2) else 1) * backlash * math.cos(
            math.radians(helical)
        ) / math.tan(pa)


# ---------------------------------------------------------------------------
# Section: geometry classes
# ---------------------------------------------------------------------------


def _rack2d_path(
    center: float,
    teeth: int,
    height: float,
    pressure_angle: float,
    backlash: float,
    clearance: float | None,
) -> list[list[float]]:
    a = _adendum(center)
    diameter = _dedendum(center, clearance)
    if not (a + diameter < height):
        raise Bosl2ValueError("rack(): height must exceed adendum + dedendum.")
    xa = a * math.sin(math.radians(pressure_angle))
    xd = diameter * math.sin(math.radians(pressure_angle))
    left = -(teeth - 1) / 2 * center - 0.5 * center
    right = (teeth - 1) / 2 * center + 0.5 * center
    path = [[left, a - height], [left, -diameter]]
    for i in range(teeth):
        off = (i - (teeth - 1) / 2) * center
        path += [
            [off - 0.25 * center + backlash - xd, -diameter],
            [off - 0.25 * center + backlash + xa, a],
            [off + 0.25 * center - backlash - xa, a],
            [off + 0.25 * center - backlash + xd, -diameter],
        ]
    path += [[right, -diameter], [right, a - height]]
    return path


class GearToothProfile:
    """The 2-D path of one involute gear tooth, rack-carved with real undercut."""

    def __init__(
        self,
        circ_pitch: float | None = None,
        teeth: int = 11,
        pressure_angle: float = 20,
        clearance: float | None = None,
        backlash: float = 0.0,
        helical: float = 0,
        internal: bool = False,
        profile_shift: float | None = None,
        shorten: float = 0,
        center: bool = False,
        mod: float | None = None,
        pitch: float | None = None,
        diam_pitch: float | None = None,
    ) -> None:
        """Compute the involute gear tooth profile.

        Args:
            circ_pitch: Circular pitch in mm/tooth.
            teeth: Number of teeth on the gear.
            pressure_angle: Pressure angle in degrees.
            clearance: Clearance, or None for default (0.25 * module).
            backlash: Backlash amount in mm.
            helical: Helical angle in degrees.
            internal: True for internal (ring) gears.
            profile_shift: Explicit profile shift, or None for auto correction.
            shorten: Amount to shorten the teeth.
            center: If True, center the tooth vertically on the pitch circle.
            mod: Metric module (mm/tooth).
            pitch: Circular pitch alias.
            diam_pitch: Diametral pitch (teeth per inch of pitch diameter).

        Returns:
            None

        """
        circ_p: float = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        ps: float = _auto_profile_shift(teeth, pressure_angle, helical, profile_shift)
        self._path: list[list[float]] = _gear_tooth_profile(
            circ_p,
            teeth,
            pressure_angle,
            clearance,
            backlash,
            helical,
            internal,
            ps,
            shorten,
            center,
        )

    def path(self) -> list[list[float]]:
        """Return the tooth profile as a 2-D point list.

        Returns:
            List of [x, y] points defining the tooth profile.

        """
        return self._path


class SpurGear2d:
    """A 2-D involute spur gear outline.

    Examples:
        A 30-tooth metric gear:

        .. pythonscad-example::

            from pybosl2.parts.gears import SpurGear2d
            SpurGear2d(mod=5, teeth=30).shape.linear_extrude(height=3).show()

    """

    def __init__(
        self,
        circ_pitch: float | None = None,
        teeth: int = 11,
        hide: int = 0,
        pressure_angle: float = 20,
        clearance: float | None = None,
        backlash: float = 0.0,
        internal: bool = False,
        profile_shift: float | None = None,
        helical: float = 0,
        shaft_diam: float = 0,
        shorten: float = 0,
        gear_spin: float = 0,
        mod: float | None = None,
        pitch: float | None = None,
        diam_pitch: float | None = None,
    ) -> None:
        """Create a 2-D spur gear.

        Args:
            circ_pitch: Circular pitch in mm/tooth.
            teeth: Number of teeth on the gear.
            hide: Number of teeth to hide (for sector gears).
            pressure_angle: Pressure angle in degrees.
            clearance: Clearance, or None for default (0.25 * module).
            backlash: Backlash amount in mm.
            internal: True for internal (ring) gears.
            profile_shift: Explicit profile shift, or None for auto correction.
            helical: Helical angle in degrees.
            shaft_diam: Shaft bore diameter, or 0 for no bore.
            shorten: Amount to shorten the teeth.
            gear_spin: Rotation offset of the gear in degrees.
            mod: Metric module (mm/tooth).
            pitch: Circular pitch alias.
            diam_pitch: Diametral pitch (teeth per inch of pitch diameter).

        Returns:
            None

        """
        center = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        ps: float = _auto_profile_shift(teeth, pressure_angle, helical, profile_shift)
        # A bore is a hole, and one path cannot describe an outline with a hole in it. It is cut
        # where the geometry is built instead -- see `bore`, and SpurGear, which subtracts it as a
        # cylinder for exactly the same result.
        self._shaft_diam: float = shaft_diam if not hide else 0.0
        self._teeth: int = teeth
        self._mod: float | None = mod
        # The pitch and profile shift above are arithmetic on the arguments, so they still resolve
        # (and reject) at the call. Cutting the tooth profile and repeating it around the gear is
        # the expensive half, and is deferred to `shape` (SPEC C-14, PLAN O-2).
        self._args = (
            center,
            ps,
            teeth,
            hide,
            pressure_angle,
            clearance,
            backlash,
            helical,
            internal,
            shorten,
            gear_spin,
        )
        self._path: Path2D | None = None

    def _build(self) -> Path2D:
        """Build the perimeter path. Called once, on the first access to `shape`."""
        (center, ps, teeth, hide, pressure_angle, clearance, backlash, helical, internal, shorten, gear_spin) = (
            self._args
        )

        tooth = _gear_tooth_profile(center, teeth, pressure_angle, clearance, backlash, helical, internal, ps, shorten)
        perim: list[list[float]] = []
        for i in range(teeth - hide):
            perim += _zrot_pts(tooth, -i * 360 / teeth + gear_spin)
        if hide > 0:
            perim.append([0, 0])
        # The perimeter as a path, not as 2-D geometry. A path is backend-neutral -- it is what
        # `Path2D.linear_extrude()` dispatches on -- while a `Bosl2Shape2D` is a CSG notion, and
        # that was what kept every gear CSG-only (TASKS T14).
        return Path2D(_dedup(perim), closed=True)

    @property
    def teeth(self) -> int:
        """Number of teeth."""
        return self._teeth

    @property
    def shape(self) -> Path2D:
        """Return the gear's perimeter as a closed path.

        A path, not 2-D geometry: `Path2D.linear_extrude()` dispatches through the backend, so a
        gear built from this outline is not tied to CSG. It carries the teeth only -- a bore is a
        hole, which one path cannot describe; see :attr:`bore`.
        """
        if self._path is None:
            self._path = self._build()
        return self._path

    @property
    def bore(self) -> float:
        """The shaft bore diameter this gear was asked for, or 0 for none.

        The bore is not part of :attr:`shape`, which is a single closed path. Cut it where the
        geometry is built -- :class:`SpurGear` subtracts it as a cylinder, which is the same solid
        the old 2-D difference produced.
        """
        return self._shaft_diam

    def region(self) -> "Region":
        """Return the gear as a :class:`~pybosl2.regions.Region`: the perimeter, less the bore.

        The form to use when the 2-D geometry itself is wanted, hole and all. It is CSG-only, as
        every region is -- an SDF prism has no way to express a hole.
        """
        from pybosl2.regions import Region

        if self._shaft_diam <= 0:
            return Region([self.shape])
        return Region.with_holes(self.shape, Path2D.circle2d(radius=self._shaft_diam / 2))

    def show(self) -> Any:
        """Display the gear outline in the viewer, and return it.

        A path has no geometry to render on its own, so what is displayed is the region's
        geometry -- the outline with its bore, which is what the gear looks like in 2-D. Rendering
        is therefore CSG-only even though :attr:`shape` is not; 2-D geometry always is.

        Returns:
            The path, so the call can be chained or assigned (SPEC S-51).

        """
        self.region().geometry().show()
        return self.shape


class SpurGear(Buildable):
    """A 3-D involute spur gear — helical and/or herringbone, with optional shaft bore.

    Examples:
        A helical gear with a shaft bore:

        .. pythonscad-example::

            from pybosl2.parts.gears import SpurGear
            SpurGear(mod=5, teeth=18, thickness=25, helical=-29, shaft_diam=15).show()

    """

    def __init__(
        self,
        circ_pitch: float | None = None,
        teeth: int = 11,
        thickness: float = 6,
        shaft_diam: float = 0,
        hide: int = 0,
        pressure_angle: float = 20,
        clearance: float | None = None,
        backlash: float = 0.0,
        helical: float = 0,
        herringbone: bool = False,
        internal: bool = False,
        profile_shift: float | None = None,
        shorten: float = 0,
        slices: int | None = None,
        gear_spin: float = 0,
        mod: float | None = None,
        pitch: float | None = None,
        diam_pitch: float | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a 3-D spur gear.

        Args:
            circ_pitch: Circular pitch in mm/tooth.
            teeth: Number of teeth on the gear.
            thickness: Gear thickness in mm.
            shaft_diam: Shaft bore diameter, or 0 for no bore.
            hide: Number of teeth to hide (for sector gears).
            pressure_angle: Pressure angle in degrees.
            clearance: Clearance, or None for default (0.25 * module).
            backlash: Backlash amount in mm.
            helical: Helical angle in degrees.
            herringbone: If True, create a herringbone (double-helical) gear.
            internal: True for internal (ring) gears.
            profile_shift: Explicit profile shift, or None for auto correction.
            shorten: Amount to shorten the teeth.
            slices: Number of slices for linear extrusion.
            gear_spin: Rotation offset of the gear in degrees.
            mod: Metric module (mm/tooth).
            pitch: Circular pitch alias.
            diam_pitch: Diametral pitch (teeth per inch of pitch diameter).
            fn: Number of fragments (circle resolution).
            fa: Minimum fragment angle.
            fs: Minimum fragment size.

        Returns:
            None

        """
        self._teeth: int = teeth
        # The spec above is all a caller needs to *measure* this part; the geometry
        # below is deferred to `shape` (SPEC C-14, PLAN O-2).
        self._args = (
            circ_pitch,
            teeth,
            thickness,
            shaft_diam,
            hide,
            pressure_angle,
            clearance,
            backlash,
            helical,
            herringbone,
            internal,
            profile_shift,
            shorten,
            slices,
            gear_spin,
            mod,
            pitch,
            diam_pitch,
            fn,
            fa,
            fs,
        )
        self._solid: "Solid | None" = None

    def _build(self) -> "Solid":
        """Build the geometry. Called once, on the first access to `shape`."""
        (
            circ_pitch,
            teeth,
            thickness,
            shaft_diam,
            hide,
            pressure_angle,
            clearance,
            backlash,
            helical,
            herringbone,
            internal,
            profile_shift,
            shorten,
            slices,
            gear_spin,
            mod,
            pitch,
            diam_pitch,
            fn,
            fa,
            fs,
        ) = self._args

        spec = GearSpec(
            teeth=teeth,
            circ_pitch=circ_pitch,
            mod=mod,
            pitch=pitch,
            diam_pitch=diam_pitch,
            pressure_angle=pressure_angle,
            clearance=clearance,
            internal=internal,
            helical=helical,
            profile_shift=profile_shift,
            shorten=shorten,
        )
        _or = _outer_radius_basic(
            spec.circ_pitch,
            spec.teeth,
            None,
            False,
            spec.helical,
            spec.profile_shift,
            spec.shorten,
        )
        twist = math.degrees(thickness * math.tan(math.radians(spec.helical)) / spec.pitch_radius)
        shape2d = SpurGear2d(
            circ_pitch=spec.circ_pitch,
            teeth=spec.teeth,
            hide=hide,
            pressure_angle=spec.pressure_angle,
            clearance=spec.clearance,
            backlash=backlash,
            internal=spec.internal,
            profile_shift=spec.profile_shift,
            helical=spec.helical,
            shaft_diam=shaft_diam,
            shorten=spec.shorten,
            gear_spin=gear_spin,
        ).shape
        if herringbone:
            top = shape2d.linear_extrude(
                height=thickness / 2,
                twist=twist / 2,
                convexity=teeth,
                slices=slices,
                fn=fn,
                fa=fa,
                fs=fs,
            )
            bot = shape2d.linear_extrude(
                height=thickness / 2,
                twist=twist / 2,
                convexity=teeth,
                slices=slices,
                fn=fn,
                fa=fa,
                fs=fs,
            ).mirror([0, 0, 1])
            solid = top | bot
        else:
            solid = shape2d.linear_extrude(
                height=thickness,
                center=True,
                twist=twist,
                convexity=teeth,
                slices=slices,
                fn=fn,
                fa=fa,
                fs=fs,
            )
        # The bore is cut here rather than in the 2-D outline: one path cannot describe a hole,
        # and a cylinder through the blank leaves the same solid (TASKS T14).
        if shaft_diam > 0 and not hide:
            solid = solid - cyl(diameter=shaft_diam, height=thickness + 1, fn=fn, fa=fa, fs=fs)
        result = solid.with_nominal_size([2 * _or, 2 * _or, thickness])
        if gear_spin:
            result = result.rotate([0, 0, gear_spin])
        return result

    @property
    def teeth(self) -> int:
        """Number of teeth."""
        return self._teeth

    @property
    def shape(self) -> "Solid":
        """Return the spur gear geometry."""
        if self._solid is None:
            self._solid = self._build()
        return self._solid


class HerringboneGear(SpurGear):
    """A herringbone (double-helical) spur gear — :class:`SpurGear` with ``herringbone=True``.

    Examples:
        A herringbone gear with a shaft bore:

        .. pythonscad-example::

            from pybosl2.parts.gears import HerringboneGear
            HerringboneGear(mod=5, teeth=18, thickness=25, helical=30, shaft_diam=15).show()

    """

    def __init__(
        self,
        circ_pitch: float | None = None,
        teeth: int = 11,
        thickness: float = 6,
        shaft_diam: float = 0,
        hide: int = 0,
        pressure_angle: float = 20,
        clearance: float | None = None,
        backlash: float = 0.0,
        helical: float = 0,
        internal: bool = False,
        profile_shift: float | None = None,
        shorten: float = 0,
        gear_spin: float = 0,
        mod: float | None = None,
        pitch: float | None = None,
        diam_pitch: float | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a herringbone gear.

        Args:
            circ_pitch: Circular pitch in mm/tooth.
            teeth: Number of teeth on the gear.
            thickness: Gear thickness in mm.
            shaft_diam: Shaft bore diameter, or 0 for no bore.
            hide: Number of teeth to hide (for sector gears).
            pressure_angle: Pressure angle in degrees.
            clearance: Clearance, or None for default (0.25 * module).
            backlash: Backlash amount in mm.
            helical: Helical angle in degrees.
            internal: True for internal (ring) gears.
            profile_shift: Explicit profile shift, or None for auto correction.
            shorten: Amount to shorten the teeth.
            gear_spin: Rotation offset of the gear in degrees.
            mod: Metric module (mm/tooth).
            pitch: Circular pitch alias.
            diam_pitch: Diametral pitch (teeth per inch of pitch diameter).
            fn: Number of fragments (circle resolution).
            fa: Minimum fragment angle.
            fs: Minimum fragment size.

        Returns:
            None

        """
        super().__init__(
            circ_pitch=circ_pitch,
            teeth=teeth,
            thickness=thickness,
            shaft_diam=shaft_diam,
            hide=hide,
            pressure_angle=pressure_angle,
            clearance=clearance,
            backlash=backlash,
            helical=helical,
            herringbone=True,
            internal=internal,
            profile_shift=profile_shift,
            shorten=shorten,
            gear_spin=gear_spin,
            mod=mod,
            pitch=pitch,
            diam_pitch=diam_pitch,
            fn=fn,
            fa=fa,
            fs=fs,
        )


class RingGear(Buildable):
    """An internal (ring) gear: a disk with inward-facing teeth cut into its bore.

    Examples:
        .. pythonscad-example::

            from pybosl2.parts.gears import RingGear
            RingGear(teeth=30, thickness=8, pressure_angle=14.5, helical=20).show()

    """

    def __init__(
        self,
        circ_pitch: float | None = None,
        teeth: int = 11,
        thickness: float = 6,
        backing: float = 3,
        pressure_angle: float = 20,
        clearance: float | None = None,
        backlash: float = 0.0,
        helical: float = 0,
        profile_shift: float | None = None,
        mod: float | None = None,
        pitch: float | None = None,
        diam_pitch: float | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create an internal ring gear.

        Args:
            circ_pitch: Circular pitch in mm/tooth.
            teeth: Number of teeth on the gear.
            thickness: Gear thickness in mm.
            backing: Extra radial thickness behind the teeth.
            pressure_angle: Pressure angle in degrees.
            clearance: Clearance, or None for default (0.25 * module).
            backlash: Backlash amount in mm.
            helical: Helical angle in degrees.
            profile_shift: Explicit profile shift, or None for auto correction.
            mod: Metric module (mm/tooth).
            pitch: Circular pitch alias.
            diam_pitch: Diametral pitch (teeth per inch of pitch diameter).
            fn: Number of fragments (circle resolution).
            fa: Minimum fragment angle.
            fs: Minimum fragment size.

        Returns:
            None

        """
        self._teeth: int = teeth
        # The spec above is all a caller needs to *measure* this part; the geometry
        # below is deferred to `shape` (SPEC C-14, PLAN O-2).
        self._args = (
            circ_pitch,
            teeth,
            thickness,
            backing,
            pressure_angle,
            clearance,
            backlash,
            helical,
            profile_shift,
            mod,
            pitch,
            diam_pitch,
            fn,
            fa,
            fs,
        )
        self._solid: "Solid | None" = None

    def _build(self) -> "Solid":
        """Build the geometry. Called once, on the first access to `shape`."""
        (
            circ_pitch,
            teeth,
            thickness,
            backing,
            pressure_angle,
            clearance,
            backlash,
            helical,
            profile_shift,
            mod,
            pitch,
            diam_pitch,
            fn,
            fa,
            fs,
        ) = self._args

        center = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        ps: float = _auto_profile_shift(teeth, pressure_angle, helical, profile_shift)
        _or = _outer_radius_basic(center, teeth, clearance, True, helical, ps, 0) + backing
        cavity = SpurGear(
            circ_pitch=center,
            teeth=teeth,
            thickness=thickness + 1,
            pressure_angle=pressure_angle,
            clearance=clearance,
            backlash=backlash,
            helical=helical,
            internal=True,
            profile_shift=profile_shift,
        ).shape
        body = facade_cylinder(height=thickness, diameter=2 * _or, center=True, fn=fn, fa=fa, fs=fs)
        return (body - cavity).with_nominal_size([2 * _or, 2 * _or, thickness])

    @property
    def teeth(self) -> int:
        """Number of teeth."""
        return self._teeth

    @property
    def shape(self) -> "Solid":
        """Return the ring gear geometry."""
        if self._solid is None:
            self._solid = self._build()
        return self._solid


class Rack2d:
    """A 2-D involute rack outline — a straight bar of teeth.

    Examples:
        A 2-D rack extruded for STL export:

        .. pythonscad-example::

            from pybosl2.parts.gears import Rack2d
            Rack2d(mod=2, teeth=20, height=10).shape.linear_extrude(height=5).show()

    """

    def __init__(
        self,
        circ_pitch: float | None = None,
        teeth: int = 20,
        height: float = 10,
        pressure_angle: float = 20,
        backlash: float = 0.0,
        clearance: float | None = None,
        mod: float | None = None,
        pitch: float | None = None,
        diam_pitch: float | None = None,
    ) -> None:
        """Create a 2-D rack.

        Args:
            circ_pitch: Circular pitch in mm/tooth.
            teeth: Number of teeth on the rack.
            height: Total height of the rack bar.
            pressure_angle: Pressure angle in degrees.
            backlash: Backlash amount in mm.
            clearance: Clearance, or None for default (0.25 * module).
            mod: Metric module (mm/tooth).
            pitch: Circular pitch alias.
            diam_pitch: Diametral pitch (teeth per inch of pitch diameter).

        Returns:
            None

        """
        center = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        a = _adendum(center)
        path = _rack2d_path(center, teeth, height, pressure_angle, backlash, clearance)
        self._shape: Path2D = Path2D(path, closed=True)
        self._nominal = [teeth * center, 2 * abs(a - height)]

    @property
    def shape(self) -> Path2D:
        """Return the rack's tooth profile as a closed path.

        A path, not 2-D geometry: `Path2D.linear_extrude()` dispatches through the backend, so a
        rack built from this outline is not tied to CSG (see :class:`SpurGear2d`).
        """
        return self._shape

    def show(self) -> Any:
        """Display the rack in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        self._shape.polygon().show()
        return self._shape


class Rack(Buildable):
    """A 3-D rack: a linear toothed bar a gear rolls along.

    Examples:
        A rack to mesh with a spur gear:

        .. pythonscad-example::

            from pybosl2.parts.gears import Rack
            Rack(mod=5, teeth=20, thickness=10, height=12).show()

    """

    def __init__(
        self,
        circ_pitch: float | None = None,
        teeth: int = 20,
        thickness: float = 5,
        height: float = 10,
        pressure_angle: float = 20,
        backlash: float = 0.0,
        clearance: float | None = None,
        helical: float = 0,
        mod: float | None = None,
        pitch: float | None = None,
        diam_pitch: float | None = None,
    ) -> None:
        """Create a 3-D rack.

        Args:
            circ_pitch: Circular pitch in mm/tooth.
            teeth: Number of teeth on the rack.
            thickness: Rack thickness in mm.
            height: Total height of the rack bar.
            pressure_angle: Pressure angle in degrees.
            backlash: Backlash amount in mm.
            clearance: Clearance, or None for default (0.25 * module).
            helical: Helical angle in degrees.
            mod: Metric module (mm/tooth).
            pitch: Circular pitch alias.
            diam_pitch: Diametral pitch (teeth per inch of pitch diameter).

        Returns:
            None

        """
        self._teeth: int = teeth
        # The spec above is all a caller needs to *measure* this part; the geometry
        # below is deferred to `shape` (SPEC C-14, PLAN O-2).
        self._args = (
            circ_pitch,
            teeth,
            thickness,
            height,
            pressure_angle,
            backlash,
            clearance,
            helical,
            mod,
            pitch,
            diam_pitch,
        )
        self._solid: "Solid | None" = None

    def _build(self) -> "Solid":
        """Build the geometry. Called once, on the first access to `shape`."""
        (
            circ_pitch,
            teeth,
            thickness,
            height,
            pressure_angle,
            backlash,
            clearance,
            helical,
            mod,
            pitch,
            diam_pitch,
        ) = self._args

        center = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        a = _adendum(center)
        diameter = _dedendum(center, clearance)
        path = _rack2d_path(center, teeth, height, pressure_angle, backlash, clearance)
        shape = Path2D(path).linear_extrude(height=thickness, center=True, convexity=teeth * 2).rotate([90, 0, 0])
        if helical:
            sxy = math.tan(math.radians(helical))
            shape = shape.multmatrix([[1, sxy, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
            sheared_length = teeth * center + thickness * sxy
        else:
            sheared_length = teeth * center
        z_extent = height + diameter - a
        # Nominal anchor box: the rack's nominal tooth height, which the rounded tooth tips sit
        # just inside. Anchoring follows the pitch line rather than the printed profile.
        return shape.with_nominal_size([sheared_length, thickness, z_extent])

    @property
    def teeth(self) -> int:
        """Number of teeth."""
        return self._teeth

    @property
    def shape(self) -> "Solid":
        """Return the rack geometry."""
        if self._solid is None:
            self._solid = self._build()
        return self._solid


class BevelGear(Buildable):
    """A (potentially spiral) involute bevel gear.

    Examples:
        A bevel gear with a shaft bore:

        .. pythonscad-example::

            from pybosl2.parts.gears import BevelGear
            BevelGear(mod=5, teeth=30, face_width=10, pitch_angle=45, shaft_diam=15).show()

    """

    def __init__(
        self,
        circ_pitch: float | None = None,
        teeth: int = 20,
        face_width: float = 10,
        pitch_angle: float = 45,
        mate_teeth: int | None = None,
        shaft_diam: float = 0,
        hide: int = 0,
        pressure_angle: float = 20,
        clearance: float | None = None,
        backlash: float = 0.0,
        cutter_radius: float = 30,
        spiral_angle: float = 35,
        left_handed: bool = False,
        slices: int = 5,
        interior: bool = False,
        mod: float | None = None,
        pitch: float | None = None,
        diam_pitch: float | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a bevel gear.

        Args:
            circ_pitch: Circular pitch in mm/tooth.
            teeth: Number of teeth on the gear.
            face_width: Width of the tooth face along the cone.
            pitch_angle: Pitch cone angle in degrees.
            mate_teeth: Number of teeth on the mating gear (overrides pitch_angle).
            shaft_diam: Shaft bore diameter, or 0 for no bore.
            hide: Number of teeth to hide (for sector gears).
            pressure_angle: Pressure angle in degrees.
            clearance: Clearance, or None for default (0.25 * module).
            backlash: Backlash amount in mm.
            cutter_radius: Radius of the cutter for spiral bevel gears.
            spiral_angle: Spiral angle in degrees.
            left_handed: True for left-handed spiral.
            slices: Number of slices along the face width.
            interior: True for interior bevel gear.
            mod: Metric module (mm/tooth).
            pitch: Circular pitch alias.
            diam_pitch: Diametral pitch (teeth per inch of pitch diameter).
            fn: Number of fragments (circle resolution).
            fa: Minimum fragment angle.
            fs: Minimum fragment size.

        Returns:
            None

        """
        self._teeth: int = teeth
        # The spec above is all a caller needs to *measure* this part; the geometry
        # below is deferred to `shape` (SPEC C-14, PLAN O-2).
        self._args = (
            circ_pitch,
            teeth,
            face_width,
            pitch_angle,
            mate_teeth,
            shaft_diam,
            hide,
            pressure_angle,
            clearance,
            backlash,
            cutter_radius,
            spiral_angle,
            left_handed,
            slices,
            interior,
            mod,
            pitch,
            diam_pitch,
            fn,
            fa,
            fs,
        )
        self._solid: "Solid | None" = None

    def _build(self) -> "Solid":
        """Build the geometry. Called once, on the first access to `shape`."""
        (
            circ_pitch,
            teeth,
            face_width,
            pitch_angle,
            mate_teeth,
            shaft_diam,
            hide,
            pressure_angle,
            clearance,
            backlash,
            cutter_radius,
            spiral_angle,
            left_handed,
            slices,
            interior,
            mod,
            pitch,
            diam_pitch,
            fn,
            fa,
            fs,
        ) = self._args

        _ = hide
        center = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        slices_ = 1 if cutter_radius == 0 else slices
        if mate_teeth is not None:
            pitch_angle = math.degrees(math.atan(teeth / mate_teeth))
        pr = _pitch_radius(center, teeth)
        rr = _root_radius_basic(center, teeth, clearance, interior, 0, 0)
        pitchoff = (pr - rr) * math.sin(math.radians(pitch_angle))
        ocone_rad = _opp_ang_to_hyp(pr, pitch_angle)
        icone_rad = ocone_rad - face_width
        cr = 1000 if cutter_radius == 0 else cutter_radius
        midpr = (icone_rad + ocone_rad) / 2
        radcp = np.array([0.0, midpr]) + _polar_xy(cr, 180 + spiral_angle)
        ncp = float(np.linalg.norm(radcp))
        ang_c1 = _law_of_cosines(cr, ncp, ocone_rad)
        ang_c2 = _law_of_cosines(cr, ncp, icone_rad)
        radcpang = math.degrees(math.atan2(radcp[1], radcp[0]))
        sang = radcpang - (180 - ang_c1)
        eang = radcpang - (180 - ang_c2)
        profile = _simple_tooth(center, teeth, pressure_angle, clearance, backlash, interior, center=True)
        prof3 = [[x, y, 0.0] for x, y in profile]
        sin_pa = math.sin(math.radians(pitch_angle))
        verts1: list[list[list[float]]] = []
        for v in np.linspace(0, 1, slices_ + 1):
            p = radcp + _polar_xy(cr, _lerp(sang, eang, v))
            angle = math.degrees(math.atan2(p[1], p[0])) - 90
            u = float(np.linalg.norm(p)) / ocone_rad
            m = (
                _m_up((1 - u) * pr / math.tan(math.radians(pitch_angle)))
                @ _m_up(pitchoff)
                @ _m_zrot(angle / sin_pa)
                @ _m_back(u * pr)
                @ _m_xrot(pitch_angle)
                @ _m_scale(u)
            )
            ring = []
            for tooth in range(teeth):
                ring += _apply(_m_xflip() @ _m_zrot(360 * tooth / teeth) @ m, prof3)
            verts1.append(ring)
        botz, topz = verts1[0][0][2], verts1[-1][0][2]
        thickness = abs(topz - botz)
        cpz = (topz + botz) / 2
        vertices = [row[::-1] for row in verts1]
        sides = VNF.vertex_array(vertices, col_wrap=True, reverse=True)
        top_verts, bot_verts = vertices[-1], vertices[0]
        gear_pts = len(top_verts)
        face_pts = gear_pts // teeth
        top_faces: list[list[int]] = []
        for i in range(teeth):
            for j in range(face_pts // 2):
                top_faces.append([i * face_pts + j, (i + 1) * face_pts - j - 1, (i + 1) * face_pts - j - 2])
                top_faces.append([i * face_pts + j, (i + 1) * face_pts - j - 2, i * face_pts + j + 1])
        for i in range(teeth):
            top_faces.append([gear_pts, (i + 1) * face_pts - 1, i * face_pts])
            top_faces.append([gear_pts, ((i + 1) % teeth) * face_pts, (i + 1) * face_pts - 1])
        top_cap = VNF(top_verts + [[0, 0, top_verts[0][2]]], top_faces)
        bot_cap = VNF(bot_verts + [[0, 0, bot_verts[0][2]]], [f[::-1] for f in top_faces])
        vnf = _vnf_join([top_cap, bot_cap, sides])
        if not left_handed:
            vnf = _vnf_xflip(vnf)
        vnf = VNF([[x, y, z - cpz] for x, y, z in vnf.vertices], vnf.faces)
        # Nominal anchor box: the pitch circle and the nominal face width. A bevel gear's teeth
        # stand outside it and its cone runs past the face width, so this is deliberately
        # smaller than bounds() -- anchor to the gear's design circle, not to its tooth tips.
        solid = vnf.polyhedron().with_nominal_size([2 * pr, 2 * pr, thickness])
        if shaft_diam and shaft_diam > 0:
            solid = solid - cylinder(height=2 * thickness + 1, diameter=shaft_diam, center=True, fn=fn, fa=fa, fs=fs)
        return solid

    @property
    def teeth(self) -> int:
        """Number of teeth."""
        return self._teeth

    @property
    # Not "2-D geometry" -- the same copy-paste that mislabelled Worm. A bevel gear's teeth are
    # built with `VNF.vertex_array`, and a non-convex mesh has no distance-field form. Both wrong
    # reasons were invisible while the refusal fired generically at construction.
    @csg_part("builds its teeth as a VNF, and a non-convex mesh has no distance-field form")
    def shape(self) -> "Solid":
        """Return the bevel gear geometry."""
        if self._solid is None:
            self._solid = self._build()
        return self._solid


class Worm(Buildable):
    """A worm — a screw that meshes a worm gear.

    Examples:
        A worm with two starts:

        .. pythonscad-example::

            from pybosl2.parts.gears import Worm
            Worm(mod=5, diameter=30, length=80, starts=2).show()

    """

    def __init__(
        self,
        circ_pitch: float | None = None,
        diameter: float = 30,
        length: float = 100,
        starts: int = 1,
        left_handed: bool = False,
        pressure_angle: float = 20,
        backlash: float = 0.0,
        clearance: float | None = None,
        mod: float | None = None,
        pitch: float | None = None,
        diam_pitch: float | None = None,
    ) -> None:
        """Create a worm.

        Args:
            circ_pitch: Circular pitch in mm/tooth.
            diameter: Worm outer diameter in mm.
            length: Worm length in mm.
            starts: Number of thread starts.
            left_handed: True for left-handed worm.
            pressure_angle: Pressure angle in degrees.
            backlash: Backlash amount in mm.
            clearance: Clearance, or None for default (0.25 * module).
            mod: Metric module (mm/tooth).
            pitch: Circular pitch alias.
            diam_pitch: Diametral pitch (teeth per inch of pitch diameter).

        Returns:
            None

        """
        # The spec above is all a caller needs to *measure* this part; the geometry
        # below is deferred to `shape` (SPEC C-14, PLAN O-2).
        self._args = (
            circ_pitch,
            diameter,
            length,
            starts,
            left_handed,
            pressure_angle,
            backlash,
            clearance,
            mod,
            pitch,
            diam_pitch,
        )
        self._solid: "Solid | None" = None

    def _build(self) -> "Solid":
        """Build the geometry. Called once, on the first access to `shape`."""
        (
            circ_pitch,
            diameter,
            length,
            starts,
            left_handed,
            pressure_angle,
            backlash,
            clearance,
            mod,
            pitch,
            diam_pitch,
        ) = self._args

        center = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        rack = _rack2d_path(center, starts, diameter, pressure_angle, backlash, clearance)[1:-1]
        polars = [[360 * px / center / starts, py + diameter / 2] for px, py in rack]
        maxang = 360 / _frag_count(diameter / 2)
        refined: list[list[float]] = []
        for i in range(len(polars) - 1):
            delta = polars[i + 1][0] - polars[i][0]
            steps = max(1, math.ceil(delta / maxang))
            for j in range(steps):
                refined.append([polars[i][0] + j * delta / steps, _lerp(polars[i][1], polars[i + 1][1], j / steps)])
        cross = [_polar_xy(r, a).tolist() for a, r in refined]
        revs = length / center / starts
        zsteps = max(1, math.ceil(revs * 360 / maxang))
        zstep, astep = length / zsteps, revs * 360 / zsteps
        profiles = []
        for i in range(zsteps + 1):
            m = _m_zrot(i * astep - 360 * revs / 2) @ _m_up(i * zstep - length / 2)
            profiles.append(_apply(m, [[x, y, 0.0] for x, y in cross]))
        rprofiles = [prof[::-1] for prof in profiles]
        vnf = VNF.vertex_array(rprofiles, caps=CapType.BUTT, col_wrap=True, style=VNFStyle.MIN_EDGE)
        if left_handed:
            vnf = _vnf_xflip(vnf)
        # Nominal anchor box: the worm's pitch diameter. The thread crests stand proud of it, so
        # bounds() reports a wider solid -- mating parts line up on the pitch cylinder.
        return vnf.polyhedron().with_nominal_size([diameter, diameter, length])

    @property
    # Not "2-D geometry" -- that reason was copy-pasted from BevelGear. A worm is a swept helical
    # thread built with `VNF.vertex_array`, and a non-convex mesh has no distance-field form. The
    # wrong reason was invisible while the refusal fired at construction with a generic message.
    @csg_part("sweeps its helical thread as a VNF, and a non-convex mesh has no distance-field form")
    def shape(self) -> "Solid":
        """Return the worm geometry."""
        if self._solid is None:
            self._solid = self._build()
        return self._solid


class WormGear(Buildable):
    """A worm gear, hobbed to mesh a matching :class:`Worm`.

    Examples:
        A worm gear with a shaft bore:

        .. pythonscad-example::

            from pybosl2.parts.gears import WormGear
            WormGear(mod=5, teeth=36, worm_diam=30, shaft_diam=15).show()

    """

    def __init__(
        self,
        circ_pitch: float | None = None,
        teeth: int = 36,
        worm_diam: float = 30,
        worm_starts: int = 1,
        worm_arc: float = 60,
        crowning: float = 1,
        left_handed: bool = False,
        pressure_angle: float = 20,
        backlash: float = 0.0,
        slices: int = 10,
        clearance: float | None = None,
        shaft_diam: float = 0,
        mod: float | None = None,
        pitch: float | None = None,
        diam_pitch: float | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a worm gear.

        Args:
            circ_pitch: Circular pitch in mm/tooth.
            teeth: Number of teeth on the gear.
            worm_diam: Diameter of the mating worm.
            worm_starts: Number of starts on the mating worm.
            worm_arc: Arc angle the worm gear wraps around the worm (10-60 degrees).
            crowning: Crowning amount.
            left_handed: True for left-handed worm gear.
            pressure_angle: Pressure angle in degrees.
            backlash: Backlash amount in mm.
            slices: Number of slices along the width.
            clearance: Clearance, or None for default (0.25 * module).
            shaft_diam: Shaft bore diameter, or 0 for no bore.
            mod: Metric module (mm/tooth).
            pitch: Circular pitch alias.
            diam_pitch: Diametral pitch (teeth per inch of pitch diameter).
            fn: Number of fragments (circle resolution).
            fa: Minimum fragment angle.
            fs: Minimum fragment size.

        Returns:
            None

        """
        if not (10 <= worm_arc <= 60):
            raise Bosl2ValueError("worm_gear(): worm_arc must be between 10 and 60 degrees.")
        self._teeth: int = teeth
        # The spec above is all a caller needs to *measure* this part; the geometry
        # below is deferred to `shape` (SPEC C-14, PLAN O-2).
        self._args = (
            circ_pitch,
            teeth,
            worm_diam,
            worm_starts,
            worm_arc,
            crowning,
            left_handed,
            pressure_angle,
            backlash,
            slices,
            clearance,
            shaft_diam,
            mod,
            pitch,
            diam_pitch,
            fn,
            fa,
            fs,
        )
        self._solid: "Solid | None" = None

    def _build(self) -> "Solid":
        """Build the geometry. Called once, on the first access to `shape`."""
        (
            circ_pitch,
            teeth,
            worm_diam,
            worm_starts,
            worm_arc,
            crowning,
            left_handed,
            pressure_angle,
            backlash,
            slices,
            clearance,
            shaft_diam,
            mod,
            pitch,
            diam_pitch,
            fn,
            fa,
            fs,
        ) = self._args

        center = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        p = _pitch_radius(center, teeth)
        circ = 2 * PI * p
        radius1 = p + worm_diam / 2 + crowning
        radius2 = worm_diam / 2 + crowning
        thickness = GearSpec.worm_gear_thickness(
            circ_pitch=center,
            teeth=teeth,
            worm_diam=worm_diam,
            worm_arc=worm_arc,
            crowning=crowning,
            clearance=clearance,
        )
        helical = center * worm_starts * worm_arc / 360 * 360 / circ
        tooth = _simple_tooth(center, teeth, pressure_angle, clearance, backlash, False, center=True)[::-1]
        prof3 = [[x, y, 0.0] for x, y in tooth]
        profiles: list[list[list[float]]] = []
        for sl in range(slices + 1):
            u = sl / slices - 0.5
            zang = u * worm_arc
            cz = math.cos(math.radians(zang))
            tp = [0.0, radius1 - radius2 * cz, radius2 * math.sin(math.radians(zang))]
            zang2 = u * helical
            ring = []
            for i in range(teeth):
                ring += _apply(_m_zrot(zang2 - i * 360 / teeth) @ _m_move(tp) @ _m_xrot(-zang) @ _m_scale(cz), prof3)
            profiles.append(ring)
        top_verts, bot_verts = profiles[-1], profiles[0]
        face_pts = len(tooth)
        gear_pts = face_pts * teeth
        top_faces: list[list[int]] = []
        for i in range(teeth):
            for j in range(face_pts // 2 - 1):
                top_faces.append([i * face_pts + j, (i + 1) * face_pts - j - 1, (i + 1) * face_pts - j - 2])
                top_faces.append([i * face_pts + j, (i + 1) * face_pts - j - 2, i * face_pts + j + 1])
        for i in range(teeth):
            top_faces.append([gear_pts, (i + 1) * face_pts - 1, i * face_pts])
            top_faces.append([gear_pts, ((i + 1) % teeth) * face_pts, (i + 1) * face_pts - 1])
        sides = VNF.vertex_array(profiles, col_wrap=True, style=VNFStyle.MIN_EDGE)
        top_cap = VNF(top_verts + [[0, 0, top_verts[0][2]]], [f[::-1] for f in top_faces])
        bot_cap = VNF(bot_verts + [[0, 0, bot_verts[0][2]]], top_faces)
        vnf = _vnf_join([top_cap, bot_cap, sides])
        if left_handed:
            vnf = _vnf_xflip(vnf)
        # Nominal anchor box: the pitch circle, which the teeth stand outside of (see BevelGear).
        solid = vnf.polyhedron().with_nominal_size([2 * p, 2 * p, thickness])
        if shaft_diam and shaft_diam > 0:
            solid = solid - cylinder(height=worm_diam, diameter=shaft_diam, center=True, fn=fn, fa=fa, fs=fs)
        return solid

    @property
    def teeth(self) -> int:
        """Number of teeth."""
        return self._teeth

    @property
    @csg_part("cuts its throated teeth into a VNF, and a non-convex mesh has no distance-field form")
    def shape(self) -> "Solid":
        """Return the worm gear geometry."""
        if self._solid is None:
            self._solid = self._build()
        return self._solid

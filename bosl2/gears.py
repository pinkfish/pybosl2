# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/gears.py
#    Pure-Python port of the core of BOSL2's (current) gears.scad. Gears are sized by circular pitch
#    (``circ_pitch``), metric ``mod``, or ``diam_pitch``; the default 20-degree pressure angle and
#    ``profile_shift="auto"`` (which corrects undercut on low-tooth-count gears) match BOSL2. The
#    :meth:`~Gears.spur_gear2d` / :meth:`~Gears.spur_gear` teeth are generated the way BOSL2 does it:
#    the involute working flank plus the trochoid that a meshing rack would carve, so low-tooth gears
#    get a real undercut. :meth:`~Gears.herringbone_gear`, the linear :meth:`~Gears.rack`, the
#    internal :meth:`~Gears.ring_gear`, the :meth:`~Gears.bevel_gear` and the :meth:`~Gears.worm` /
#    :meth:`~Gears.worm_gear` pair are ported too, along with the dimension helpers and
#    :meth:`~Gears.gear_dist` (meshing-distance) / :meth:`~Gears.auto_profile_shift`.
#
#    Bevel/worm sweep a simpler symmetric involute tooth (no undercut modelling) -- fine for those
#    swept 3-D forms.
#
#    Note: the helical *sign* sets the twist handedness of a 3-D gear directly here; BOSL2 reaches the
#    same geometry via an internal helical inversion, so a given ``helical`` value may produce the
#    opposite hand from BOSL2. A helical gear still meshes its opposite-hand mate either way.
#
# FileSummary: Gears: spur (with undercut), helical, herringbone, rack, ring, bevel, worm.
# FileGroup: BOSL2

from __future__ import annotations

import math

import numpy as np

from pythonscad import polygon as _opolygon

from bosl2.constants import INCH
from bosl2.paths import Path
from bosl2.shapes2d import _frag_count
from bosl2.shapes3d import Bosl2Solid, cylinder
from bosl2.vnf import VNF

__all__ = ["Gears"]

PI = math.pi


# ---------------------------------------------------------------------------
# Section: pitch / module resolution and the derived radii (BOSL2 gears.scad)
# ---------------------------------------------------------------------------


def _circular_pitch(circ_pitch=None, mod=None, pitch=None, diam_pitch=None) -> float:
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


def _module_value(circ_pitch) -> float:
    return circ_pitch / PI


def _pitch_radius(circ_pitch, teeth, helical=0) -> float:
    return circ_pitch * teeth / PI / 2 / math.cos(math.radians(helical))


def _adendum(circ_pitch, profile_shift=0, shorten=0) -> float:
    return _module_value(circ_pitch) * (1 + profile_shift - shorten)


def _dedendum(circ_pitch, clearance=None, profile_shift=0) -> float:
    mod = _module_value(circ_pitch)
    clear = 0.25 * mod if clearance is None else clearance
    return mod * (1 - profile_shift) + clear


def _base_radius(circ_pitch, teeth, pressure_angle=20, helical=0) -> float:
    trans_pa = math.degrees(math.atan(math.tan(math.radians(pressure_angle)) / math.cos(math.radians(helical))))
    return _pitch_radius(circ_pitch, teeth, helical) * math.cos(math.radians(trans_pa))


def _root_radius_basic(circ_pitch, teeth, clearance=None, internal=False, helical=0, profile_shift=0) -> float:
    pr = _pitch_radius(circ_pitch, teeth, helical)
    return pr - (_adendum(circ_pitch, -profile_shift) if internal
                 else _dedendum(circ_pitch, clearance, profile_shift))


def _outer_radius_basic(circ_pitch, teeth, clearance=None, internal=False, helical=0,
                        profile_shift=0, shorten=0) -> float:
    pr = _pitch_radius(circ_pitch, teeth, helical)
    return pr + (_dedendum(circ_pitch, clearance, -profile_shift) if internal
                 else _adendum(circ_pitch, profile_shift, shorten))


def _auto_profile_shift(teeth, pressure_angle=20, helical=0, profile_shift="auto") -> float:
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


def _involute(base_r, a_deg):
    b = a_deg * PI / 180
    ar = math.radians(a_deg)
    return [base_r * (math.cos(ar) + b * math.sin(ar)), base_r * (math.sin(ar) - b * math.cos(ar))]


def _xy_to_polar(xy):
    return [math.hypot(xy[0], xy[1]), math.degrees(math.atan2(xy[1], xy[0]))]


def _p2xy(r, ang):
    a = math.radians(ang)
    return [r * math.cos(a), r * math.sin(a)]


def _lookup(x, table):
    xs = [t[0] for t in table]
    ys = [t[1] for t in table]
    if xs[0] > xs[-1]:
        xs, ys = xs[::-1], ys[::-1]
    return float(np.interp(x, xs, ys))


def _v_theta(v):
    return math.degrees(math.atan2(v[1], v[0]))


def _zrot_pts(pts, ang):
    a = math.radians(ang)
    c, s = math.cos(a), math.sin(a)
    return [[x * c - y * s, x * s + y * c] for x, y in pts]


def _line_isect(l1, l2):
    (x1, y1), (x2, y2) = l1[0], l1[1]
    (x3, y3), (x4, y4) = l2[0], l2[1]
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        return [float(l1[1][0]), float(l1[1][1])]
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / den
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / den
    return [px, py]


def _vector_angle(three):
    p0, p1, p2 = (np.asarray(p, float) for p in three)
    v0, v1 = p0 - p1, p2 - p1
    c = np.clip(np.dot(v0, v1) / (np.linalg.norm(v0) * np.linalg.norm(v1)), -1, 1)
    return math.degrees(math.acos(c))


def _arc_corner(n, r, corner):
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
    return [[center[0] + r * math.cos(a0 + da * i / n), center[1] + r * math.sin(a0 + da * i / n)]
            for i in range(n + 1)]


def _dedup(pts, eps=1e-9):
    out = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps:
            out.append([float(p[0]), float(p[1])])
    return out


def _norm2(v):
    return math.hypot(v[0], v[1])


def _strip_left(path, undercut_max):
    """Remove the inward 'jaggies' the undercut can leave (BOSL2 strip_left)."""
    out = []
    i = 0
    n = len(path)
    while i < n:
        p = path[i]
        if _norm2(p) >= undercut_max:
            out += [list(q) for q in path[i:]]
            break
        out.append(list(p))
        angs = [_v_theta([path[j][0] - p[0], path[j][1] - p[1]])
                for j in range(i + 1, n) if _norm2(path[j]) < undercut_max]
        if not angs:
            i += 1
        else:
            i += int(np.argmin(angs)) + 1
    return out


# ---------------------------------------------------------------------------
# Section: the involute gear tooth (BOSL2 _gear_tooth_profile), with undercut
# ---------------------------------------------------------------------------


def _gear_tooth_profile(circ_pitch, teeth, pressure_angle=20, clearance=None, backlash=0.0,
                        helical=0, internal=False, profile_shift=0.0, shorten=0, center=False,
                        steps=16):
    pa = pressure_angle
    mod = _module_value(circ_pitch)
    clear = 0.25 * mod if clearance is None else clearance
    arad = _outer_radius_basic(circ_pitch, teeth, None, internal, helical, profile_shift, shorten)
    prad = _pitch_radius(circ_pitch, teeth, helical)
    brad = _base_radius(circ_pitch, teeth, pa, helical)
    rrad = _root_radius_basic(circ_pitch, teeth, clear, internal, helical, profile_shift)
    srad = max(rrad, brad)
    tthick = circ_pitch / PI / math.cos(math.radians(helical)) * \
        (PI / 2 + 2 * profile_shift * math.tan(math.radians(pa))) + (backlash if internal else -backlash)
    tang = tthick / prad / 2 * 180 / PI

    involute_lup = []
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

    def flank_angle(r):
        a1 = _lookup(r, involute_lup) + soff
        if internal or r < undercut_lup[0][0]:
            return a1, a1, False
        a2 = _lookup(r, undercut_lup)
        return min(a1, a2), a2, a1 > a2

    undercut_max = 0.0
    for u in us:
        r = _lerp(rrad, ma_rad, u)
        aa, _a2, use_uc = flank_angle(r)
        if aa < 90 + 180 / teeth and use_uc:
            undercut_max = max(undercut_max, r)

    tooth_half_raw = []
    for u in us:
        r = _lerp(rrad, ma_rad, u)
        aa, _a2, _uc = flank_angle(r)
        if (internal or r > rrad + clear) and (not internal or r < ma_rad - clear) and aa < 90 + 180 / teeth:
            tooth_half_raw.append(_p2xy(r, aa))
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
    rcorner = ([tooth_half_raw[-1], isect_pt, line2[0]] if internal
               else [line2[0], isect_pt, line1[0]])
    maxr = _norm2([rcorner[0][0] - rcorner[1][0], rcorner[0][1] - rcorner[1][1]]) * \
        math.tan(math.radians(_vector_angle(rcorner) / 2))
    round_r = min(maxr, clear, rcircum * rpart)

    rounded = []
    if not internal:
        rounded += _arc_corner(8, round_r, rcorner) if round_r > 0 else [isect_pt]
    rounded += tooth_half_raw
    if internal:
        rounded += _arc_corner(8, round_r, rcorner) if round_r > 0 else [isect_pt]
    rounded = _dedup(rounded)

    tooth_half = _strip_left(rounded, undercut_max) if undercut_max else rounded

    invalid = [i2 for i2 in range(len(tooth_half))
               if math.degrees(math.atan2(tooth_half[i2][1], tooth_half[i2][0])) > 90 + 180 / teeth]
    if invalid:
        ind = invalid[-1]
        ipt = _line_isect([[0, 0], _p2xy(1, 90 + 180 / teeth)], tooth_half[ind:ind + 2])
        clipped = [ipt] + [list(q) for q in tooth_half[ind + 1:]]
    else:
        clipped = tooth_half

    full = _dedup([list(q) for q in clipped] + [[-x, y] for x, y in reversed(clipped)])
    tooth = Path._path_merge_collinear(full, closed=False)
    if center:
        tooth = [[x, y - prad] for x, y in tooth]
    return [[float(x), float(y)] for x, y in tooth]


def _lerp(a, b, v):
    return a + (b - a) * v


# ---------------------------------------------------------------------------
# Section: matrix / VNF helpers for the 3-D bevel and worm gears
# ---------------------------------------------------------------------------


def _polar(r, t_deg):
    a = math.radians(t_deg)
    return [r * math.sin(a), r * math.cos(a)]


def _iang(r1, r2):
    return math.degrees(math.sqrt((r2 / r1) ** 2 - 1) - math.acos(r1 / r2))


def _q6(b, s, t, d):
    return _polar(d, s * (_iang(b, d) + t))


def _q7(f, r, b, r2, t, s):
    return _q6(b, s, t, (1 - f) * max(b, r) + f * r2)


def _rot2d(pts, ang_deg):
    a = math.radians(ang_deg)
    c, s = math.cos(a), math.sin(a)
    return [[x * c - y * s, x * s + y * c] for x, y in pts]


def _polar_xy(r, ang):
    a = math.radians(ang)
    return np.array([r * math.cos(a), r * math.sin(a)])


def _law_of_cosines(a, b, c):
    return math.degrees(math.acos(max(-1.0, min(1.0, (a * a + b * b - c * c) / (2 * a * b)))))


def _opp_ang_to_hyp(opp, ang):
    return opp / math.sin(math.radians(ang))


def _m_up(z):
    m = np.eye(4); m[2, 3] = z; return m


def _m_back(y):
    m = np.eye(4); m[1, 3] = y; return m


def _m_move(v):
    m = np.eye(4); m[0, 3], m[1, 3], m[2, 3] = v[0], v[1], v[2]; return m


def _m_zrot(deg):
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    m = np.eye(4); m[0, 0] = c; m[0, 1] = -s; m[1, 0] = s; m[1, 1] = c; return m


def _m_xrot(deg):
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    m = np.eye(4); m[1, 1] = c; m[1, 2] = -s; m[2, 1] = s; m[2, 2] = c; return m


def _m_scale(u):
    return np.diag([u, u, u, 1.0])


def _m_xflip():
    m = np.eye(4); m[0, 0] = -1; return m


def _apply(m, pts):
    arr = np.c_[np.asarray(pts, dtype=float), np.ones(len(pts))]
    return (arr @ m.T)[:, :3].tolist()


def _vnf_join(vnfs):
    verts, faces = [], []
    for v in vnfs:
        off = len(verts)
        verts += [list(p) for p in v.vertices]
        faces += [[i + off for i in f] for f in v.faces]
    return VNF(verts, faces)


def _vnf_xflip(vnf):
    return VNF([[-x, y, z] for x, y, z in vnf.vertices], [f[::-1] for f in vnf.faces])


def _simple_tooth(circ_pitch, teeth, pressure_angle, clearance=None, backlash=0.0,
                  interior=False, center=False):
    """A simple symmetric involute tooth (the older BOSL2 profile) for the swept bevel/worm forms."""
    p = _pitch_radius(circ_pitch, teeth)
    c = _outer_radius_basic(circ_pitch, teeth, clearance, interior, 0, 0, 0)
    r = _root_radius_basic(circ_pitch, teeth, clearance, interior, 0, 0)
    b = p * math.cos(math.radians(pressure_angle))
    t = circ_pitch / 2 - backlash / 2
    k = -_iang(b, p) - math.degrees(t / 2 / p)
    isteps = 5
    pts = [_polar(r, -k if r >= b else 180 / teeth)]
    pts += [_q7(i / isteps, r, b, c, k, -1) for i in range(isteps + 1)]
    pts += [_q7(i / isteps, r, b, c, k, 1) for i in range(isteps, -1, -1)]
    pts.append(_polar(r, k if r >= b else -180 / teeth))
    if center:
        pts = [[x, y - p] for x, y in pts]
    return pts


class Gears:
    """Gears (BOSL2 gears.scad): spur (with undercut), helical, herringbone, rack, ring, bevel, worm.

    Size a gear by ``circ_pitch`` (mm of pitch circle per tooth), ``mod`` (metric module) or
    ``diam_pitch``; pass one. The 20-degree ``pressure_angle`` and ``profile_shift="auto"`` defaults
    match BOSL2. All angles are in degrees.
    """

    # -- tooth density -----------------------------------------------------

    @staticmethod
    def circular_pitch(circ_pitch=None, mod=None, pitch=None, diam_pitch=None) -> float:
        """Circular pitch (mm/tooth) from any pitch input (BOSL2 circular_pitch())."""
        return _circular_pitch(circ_pitch, mod, pitch, diam_pitch)

    @staticmethod
    def pitch_value(mod: float) -> float:
        """Circular pitch from the metric module (BOSL2 pitch_value())."""
        return mod * PI

    @staticmethod
    def module_value(circ_pitch=None, mod=None, pitch=None, diam_pitch=None) -> float:
        """Metric module from any pitch input (BOSL2 module_value())."""
        return _module_value(_circular_pitch(circ_pitch, mod, pitch, diam_pitch))

    @staticmethod
    def diametral_pitch(circ_pitch=None, mod=None, pitch=None, diam_pitch=None) -> float:
        """Diametral pitch (teeth per inch of pitch diameter) (BOSL2 diametral_pitch())."""
        return PI / _circular_pitch(circ_pitch, mod, pitch, diam_pitch)

    # -- radii -------------------------------------------------------------

    @staticmethod
    def pitch_radius(circ_pitch=None, teeth=11, helical=0, mod=None, pitch=None, diam_pitch=None) -> float:
        """Pitch radius; meshed gears sit a :meth:`gear_dist` apart (BOSL2 pitch_radius())."""
        return _pitch_radius(_circular_pitch(circ_pitch, mod, pitch, diam_pitch), teeth, helical)

    @staticmethod
    def outer_radius(circ_pitch=None, teeth=11, clearance=None, internal=False, helical=0,
                     profile_shift="auto", pressure_angle=20, shorten=0, mod=None, pitch=None,
                     diam_pitch=None) -> float:
        """Tip radius; the gear fits within this circle (BOSL2 outer_radius())."""
        cp = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        ps = _auto_profile_shift(teeth, pressure_angle, helical, profile_shift)
        return _outer_radius_basic(cp, teeth, clearance, internal, helical, ps, shorten)

    @staticmethod
    def root_radius(circ_pitch=None, teeth=11, clearance=None, internal=False, helical=0,
                    profile_shift="auto", pressure_angle=20, mod=None, pitch=None,
                    diam_pitch=None) -> float:
        """Root radius at the base of the tooth valleys (BOSL2 root_radius())."""
        cp = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        ps = _auto_profile_shift(teeth, pressure_angle, helical, profile_shift)
        return _root_radius_basic(cp, teeth, clearance, internal, helical, ps)

    @staticmethod
    def base_radius(circ_pitch=None, teeth=11, pressure_angle=20, helical=0, mod=None, pitch=None,
                    diam_pitch=None) -> float:
        """Base-circle radius of the involute (BOSL2 base_radius())."""
        return _base_radius(_circular_pitch(circ_pitch, mod, pitch, diam_pitch), teeth,
                            pressure_angle, helical)

    @staticmethod
    def auto_profile_shift(teeth, pressure_angle=20, helical=0, profile_shift="auto") -> float:
        """Minimum profile shift (modules) to avoid undercut (BOSL2 auto_profile_shift())."""
        return _auto_profile_shift(teeth, pressure_angle, helical, profile_shift)

    # -- meshing distance --------------------------------------------------

    @staticmethod
    def gear_dist(teeth1, teeth2, helical=0, profile_shift1="auto", profile_shift2="auto",
                  internal1=False, internal2=False, backlash=0, pressure_angle=20,
                  circ_pitch=None, mod=None, diam_pitch=None) -> float:
        """Center-to-center distance for two meshing gears (BOSL2 gear_dist()).

        A zero tooth count means a rack. Profile shift changes the working pressure angle and hence
        the spacing; ``"auto"`` picks the undercut-avoidance shift for each gear.
        """
        m = _module_value(_circular_pitch(circ_pitch, mod, None, diam_pitch))
        ps1 = _auto_profile_shift(teeth1, pressure_angle, helical, profile_shift1)
        ps2 = _auto_profile_shift(teeth2, pressure_angle, helical, profile_shift2)
        t1 = -teeth1 if internal2 else teeth1
        t2 = -teeth2 if internal1 else teeth2
        if internal2:
            ps1 = -ps1
        if internal1:
            ps2 = -ps2
        if teeth1 == 0 or teeth2 == 0:
            return _pitch_radius(m * PI, t1 + t2, helical) + (ps1 + ps2) * m
        pa = math.radians(pressure_angle)
        pa_transv = math.atan(math.tan(pa) / math.cos(math.radians(helical)))
        # working pressure angle from the involute equation
        inv = lambda a: math.tan(a) - a
        target = inv(pa_transv) + 2 * (ps1 + ps2) / (t1 + t2) * math.tan(pa)
        lo, hi = 1e-4, math.radians(89)
        for _ in range(60):
            mid = (lo + hi) / 2
            if inv(mid) < target:
                lo = mid
            else:
                hi = mid
        pa_eff = (lo + hi) / 2
        d = m * (t1 + t2) * math.cos(pa_transv) / math.cos(pa_eff) / math.cos(math.radians(helical)) / 2
        return d + (-1 if (internal1 or internal2) else 1) * backlash * math.cos(math.radians(helical)) / math.tan(pa)

    # -- the involute tooth & spur gears -----------------------------------

    @staticmethod
    def gear_tooth_profile(circ_pitch=None, teeth=11, pressure_angle=20, clearance=None, backlash=0.0,
                           helical=0, internal=False, profile_shift="auto", shorten=0, center=False,
                           mod=None, pitch=None, diam_pitch=None) -> list[list[float]]:
        """The 2-D path of one involute gear tooth, rack-carved with real undercut (BOSL2 _gear_tooth_profile())."""
        cp = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        ps = _auto_profile_shift(teeth, pressure_angle, helical, profile_shift)
        return _gear_tooth_profile(cp, teeth, pressure_angle, clearance, backlash, helical,
                                   internal, ps, shorten, center)

    @staticmethod
    def spur_gear2d(circ_pitch=None, teeth=11, hide=0, pressure_angle=20, clearance=None,
                    backlash=0.0, internal=False, profile_shift="auto", helical=0, shaft_diam=0,
                    shorten=0, gear_spin=0, mod=None, pitch=None, diam_pitch=None) -> Bosl2Solid:
        """A 2-D involute spur gear outline (BOSL2 spur_gear2d()).

        Examples:
            A 30-tooth metric gear:

            .. pythonscad-example::

                from bosl2.gears import Gears
                Gears.spur_gear2d(mod=5, teeth=30).linear_extrude(height=3).show()
        """
        cp = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        ps = _auto_profile_shift(teeth, pressure_angle, helical, profile_shift)
        tooth = _gear_tooth_profile(cp, teeth, pressure_angle, clearance, backlash, helical,
                                    internal, ps, shorten)
        perim = []
        for i in range(teeth - hide):
            perim += _zrot_pts(tooth, -i * 360 / teeth + gear_spin)
        if hide > 0:
            perim.append([0, 0])
        shape = _opolygon(_dedup(perim))
        result = Bosl2Solid(shape, size=[2 * _pitch_radius(cp, teeth, helical)] * 2 + [0])
        if shaft_diam > 0 and not hide:
            from bosl2.shapes2d import circle as _circle2d
            result = result - Bosl2Solid(_circle2d(d=shaft_diam))
        return result

    @staticmethod
    def spur_gear(circ_pitch=None, teeth=11, thickness=6, shaft_diam=0, hide=0, pressure_angle=20,
                  clearance=None, backlash=0.0, helical=0, herringbone=False, internal=False,
                  profile_shift="auto", shorten=0, slices=None, gear_spin=0, mod=None, pitch=None,
                  diam_pitch=None) -> Bosl2Solid:
        """A 3-D involute spur gear -- helical and/or herringbone, with an optional shaft bore (BOSL2 spur_gear()).

        Examples:
            A helical gear with a shaft bore:

            .. pythonscad-example::

                from bosl2.gears import Gears
                Gears.spur_gear(mod=5, teeth=18, thickness=25, helical=-29, shaft_diam=15).show()
        """
        cp = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        pr = _pitch_radius(cp, teeth, helical)
        twist = math.degrees(thickness * math.tan(math.radians(helical)) / pr)
        gear2d = Gears.spur_gear2d(circ_pitch=cp, teeth=teeth, hide=hide, pressure_angle=pressure_angle,
                                   clearance=clearance, backlash=backlash, internal=internal,
                                   profile_shift=profile_shift, helical=helical, shaft_diam=shaft_diam,
                                   shorten=shorten).shape
        if herringbone:
            top = gear2d.linear_extrude(height=thickness / 2, twist=twist / 2, convexity=teeth)
            bot = gear2d.linear_extrude(height=thickness / 2, twist=twist / 2,
                                        convexity=teeth).scale([1, 1, -1])
            solid = top | bot
        else:
            solid = gear2d.linear_extrude(height=thickness, center=True, twist=twist, convexity=teeth)
        result = Bosl2Solid(solid, size=[2 * pr, 2 * pr, thickness])
        return result.rotate([0, 0, gear_spin]) if gear_spin else result

    @staticmethod
    def herringbone_gear(circ_pitch=None, teeth=11, thickness=6, shaft_diam=0, hide=0,
                         pressure_angle=20, clearance=None, backlash=0.0, helical=0, internal=False,
                         profile_shift="auto", shorten=0, gear_spin=0, mod=None, pitch=None,
                         diam_pitch=None) -> Bosl2Solid:
        """A herringbone (double-helical) spur gear -- :meth:`spur_gear` with ``herringbone=True``."""
        return Gears.spur_gear(circ_pitch=circ_pitch, teeth=teeth, thickness=thickness,
                               shaft_diam=shaft_diam, hide=hide, pressure_angle=pressure_angle,
                               clearance=clearance, backlash=backlash, helical=helical,
                               herringbone=True, internal=internal, profile_shift=profile_shift,
                               shorten=shorten, gear_spin=gear_spin, mod=mod, pitch=pitch,
                               diam_pitch=diam_pitch)

    @staticmethod
    def ring_gear(circ_pitch=None, teeth=11, thickness=6, backing=3, pressure_angle=20, clearance=None,
                  backlash=0.0, helical=0, profile_shift="auto", mod=None, pitch=None,
                  diam_pitch=None) -> Bosl2Solid:
        """An internal (ring) gear: a disk with inward-facing teeth cut into its bore (BOSL2 ring_gear())."""
        cp = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        ps = _auto_profile_shift(teeth, pressure_angle, helical, profile_shift)
        or_ = _outer_radius_basic(cp, teeth, clearance, True, helical, ps, 0) + backing
        cavity = Gears.spur_gear(circ_pitch=cp, teeth=teeth, thickness=thickness + 1,
                                 pressure_angle=pressure_angle, clearance=clearance,
                                 backlash=backlash, helical=helical, internal=True,
                                 profile_shift=profile_shift)
        body = cylinder(h=thickness, d=2 * or_, center=True)
        return Bosl2Solid((body - cavity).shape, size=[2 * or_, 2 * or_, thickness])

    # -- rack --------------------------------------------------------------

    @staticmethod
    def _rack2d_path(cp, teeth, height, pressure_angle, backlash, clearance):
        a = _adendum(cp)
        d = _dedendum(cp, clearance)
        assert a + d < height, "rack(): height must exceed adendum + dedendum."
        xa = a * math.sin(math.radians(pressure_angle))
        xd = d * math.sin(math.radians(pressure_angle))
        left = -(teeth - 1) / 2 * cp - 0.5 * cp
        right = (teeth - 1) / 2 * cp + 0.5 * cp
        path = [[left, a - height], [left, -d]]
        for i in range(teeth):
            off = (i - (teeth - 1) / 2) * cp
            path += [
                [off - 0.25 * cp + backlash - xd, -d],
                [off - 0.25 * cp + backlash + xa, a],
                [off + 0.25 * cp - backlash - xa, a],
                [off + 0.25 * cp - backlash + xd, -d],
            ]
        path += [[right, -d], [right, a - height]]
        return path

    @staticmethod
    def rack2d(circ_pitch=None, teeth=20, height=10, pressure_angle=20, backlash=0.0, clearance=None,
               mod=None, pitch=None, diam_pitch=None) -> Bosl2Solid:
        """A 2-D involute rack outline -- a straight bar of teeth (BOSL2 rack2d())."""
        cp = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        a = _adendum(cp)
        path = Gears._rack2d_path(cp, teeth, height, pressure_angle, backlash, clearance)
        return Bosl2Solid(_opolygon(path), size=[teeth * cp, 2 * abs(a - height), 0])

    @staticmethod
    def rack(circ_pitch=None, teeth=20, thickness=5, height=10, pressure_angle=20, backlash=0.0,
             clearance=None, helical=0, mod=None, pitch=None, diam_pitch=None) -> Bosl2Solid:
        """A 3-D rack: a linear toothed bar a gear rolls along (BOSL2 rack())."""
        cp = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        a = _adendum(cp)
        path = Gears._rack2d_path(cp, teeth, height, pressure_angle, backlash, clearance)
        shape = _opolygon(path).linear_extrude(height=thickness, center=True,
                                               convexity=teeth * 2).rotate([90, 0, 0])
        if helical:
            sxy = math.tan(math.radians(helical))
            shape = shape.multmatrix([[1, sxy, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
        return Bosl2Solid(shape, size=[teeth * cp, thickness, 2 * abs(a - height)])

    # -- bevel / worm dimension helpers ------------------------------------

    @staticmethod
    def bevel_pitch_angle(teeth, mate_teeth, drive_angle=90) -> float:
        """Pitch angle (deg) for a bevel gear meshing another (BOSL2 bevel_pitch_angle())."""
        return math.degrees(math.atan2(math.sin(math.radians(drive_angle)),
                                       (mate_teeth / teeth) + math.cos(math.radians(drive_angle))))

    @staticmethod
    def worm_gear_thickness(circ_pitch=None, teeth=30, worm_diam=30, worm_arc=60, crowning=1,
                            clearance=None, mod=None, pitch=None, diam_pitch=None) -> float:
        """Thickness of a worm gear matched to a worm (BOSL2 worm_gear_thickness())."""
        cp = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        r = worm_diam / 2 + crowning
        pitch_thick = r * math.sin(math.radians(worm_arc / 2)) * 2
        pr = _pitch_radius(cp, teeth)
        rr = pr - _dedendum(cp, clearance)
        pitchoff = (pr - rr) * math.sin(math.radians(worm_arc / 2))
        return pitch_thick + 2 * pitchoff

    # -- bevel gear --------------------------------------------------------

    @staticmethod
    def bevel_gear(circ_pitch=None, teeth=20, face_width=10, pitch_angle=45, mate_teeth=None,
                   shaft_diam=0, hide=0, pressure_angle=20, clearance=None, backlash=0.0,
                   cutter_radius=30, spiral_angle=35, left_handed=False, slices=5, interior=False,
                   mod=None, pitch=None, diam_pitch=None) -> Bosl2Solid:
        """A (potentially spiral) involute bevel gear (BOSL2 bevel_gear())."""
        cp = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        slices = 1 if cutter_radius == 0 else slices
        if mate_teeth is not None:
            pitch_angle = math.degrees(math.atan(teeth / mate_teeth))
        pr = _pitch_radius(cp, teeth)
        rr = _root_radius_basic(cp, teeth, clearance, interior, 0, 0)
        pitchoff = (pr - rr) * math.sin(math.radians(pitch_angle))
        ocone_rad = _opp_ang_to_hyp(pr, pitch_angle)
        icone_rad = ocone_rad - face_width
        cutter_radius = 1000 if cutter_radius == 0 else cutter_radius
        midpr = (icone_rad + ocone_rad) / 2
        radcp = np.array([0.0, midpr]) + _polar_xy(cutter_radius, 180 + spiral_angle)
        ncp = float(np.linalg.norm(radcp))
        angC1 = _law_of_cosines(cutter_radius, ncp, ocone_rad)
        angC2 = _law_of_cosines(cutter_radius, ncp, icone_rad)
        radcpang = math.degrees(math.atan2(radcp[1], radcp[0]))
        sang = radcpang - (180 - angC1)
        eang = radcpang - (180 - angC2)
        profile = _simple_tooth(cp, teeth, pressure_angle, clearance, backlash, interior, center=True)
        prof3 = [[x, y, 0.0] for x, y in profile]
        tan_pa = math.tan(math.radians(pitch_angle))
        sin_pa = math.sin(math.radians(pitch_angle))
        verts1 = []
        for v in np.linspace(0, 1, slices + 1):
            p = radcp + _polar_xy(cutter_radius, _lerp(sang, eang, v))
            ang = math.degrees(math.atan2(p[1], p[0])) - 90
            u = float(np.linalg.norm(p)) / ocone_rad
            m = (_m_up((1 - u) * pr / tan_pa) @ _m_up(pitchoff) @ _m_zrot(ang / sin_pa)
                 @ _m_back(u * pr) @ _m_xrot(pitch_angle) @ _m_scale(u))
            ring = []
            for tooth in range(teeth):
                ring += _apply(_m_xflip() @ _m_zrot(360 * tooth / teeth) @ m, prof3)
            verts1.append(ring)
        botz, topz = verts1[0][0][2], verts1[-1][0][2]
        thickness = abs(topz - botz)
        cpz = (topz + botz) / 2
        vertices = [row[::-1] for row in verts1]
        sides = VNF.vertex_array(vertices, caps=False, col_wrap=True, reverse=True)
        top_verts, bot_verts = vertices[-1], vertices[0]
        gear_pts = len(top_verts)
        face_pts = gear_pts // teeth
        top_faces = []
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
        solid = Bosl2Solid(vnf.polyhedron(), size=[2 * pr, 2 * pr, thickness])
        if shaft_diam and shaft_diam > 0:
            solid = solid - cylinder(h=2 * thickness + 1, d=shaft_diam, center=True)
        return solid

    # -- worm & worm gear --------------------------------------------------

    @staticmethod
    def worm(circ_pitch=None, d=30, l=100, starts=1, left_handed=False, pressure_angle=20,
             backlash=0.0, clearance=None, mod=None, pitch=None, diam_pitch=None) -> Bosl2Solid:
        """A worm (a screw that meshes a worm gear) (BOSL2 worm())."""
        cp = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        rack = Gears._rack2d_path(cp, starts, d, pressure_angle, backlash, clearance)[1:-1]
        polars = [[360 * px / cp / starts, py + d / 2] for px, py in rack]
        maxang = 360 / _frag_count(d / 2)
        refined = []
        for i in range(len(polars) - 1):
            delta = polars[i + 1][0] - polars[i][0]
            steps = max(1, math.ceil(delta / maxang))
            for j in range(steps):
                refined.append([polars[i][0] + j * delta / steps,
                                _lerp(polars[i][1], polars[i + 1][1], j / steps)])
        cross = [_polar_xy(r, a).tolist() for a, r in refined]
        revs = l / cp / starts
        zsteps = max(1, math.ceil(revs * 360 / maxang))
        zstep, astep = l / zsteps, revs * 360 / zsteps
        profiles = []
        for i in range(zsteps + 1):
            m = _m_zrot(i * astep - 360 * revs / 2) @ _m_up(i * zstep - l / 2)
            profiles.append(_apply(m, [[x, y, 0.0] for x, y in cross]))
        rprofiles = [prof[::-1] for prof in profiles]
        vnf = VNF.vertex_array(rprofiles, caps=True, col_wrap=True, style="min_edge")
        if left_handed:
            vnf = _vnf_xflip(vnf)
        return Bosl2Solid(vnf.polyhedron(), size=[d, d, l])

    @staticmethod
    def worm_gear(circ_pitch=None, teeth=36, worm_diam=30, worm_starts=1, worm_arc=60, crowning=1,
                  left_handed=False, pressure_angle=20, backlash=0.0, slices=10, clearance=None,
                  shaft_diam=0, mod=None, pitch=None, diam_pitch=None) -> Bosl2Solid:
        """A worm gear, hobbed to mesh a matching :meth:`worm` (BOSL2 worm_gear())."""
        assert 10 <= worm_arc <= 60, "worm_gear(): worm_arc must be between 10 and 60 degrees."
        cp = _circular_pitch(circ_pitch, mod, pitch, diam_pitch)
        p = _pitch_radius(cp, teeth)
        circ = 2 * PI * p
        r1 = p + worm_diam / 2 + crowning
        r2 = worm_diam / 2 + crowning
        thickness = Gears.worm_gear_thickness(circ_pitch=cp, teeth=teeth, worm_diam=worm_diam,
                                              worm_arc=worm_arc, crowning=crowning, clearance=clearance)
        helical = cp * worm_starts * worm_arc / 360 * 360 / circ
        tooth = _simple_tooth(cp, teeth, pressure_angle, clearance, backlash, False, center=True)[::-1]
        prof3 = [[x, y, 0.0] for x, y in tooth]
        profiles = []
        for sl in range(slices + 1):
            u = sl / slices - 0.5
            zang = u * worm_arc
            cz = math.cos(math.radians(zang))
            tp = [0.0, r1 - r2 * cz, r2 * math.sin(math.radians(zang))]
            zang2 = u * helical
            ring = []
            for i in range(teeth):
                ring += _apply(_m_zrot(zang2 - i * 360 / teeth) @ _m_move(tp) @ _m_xrot(-zang) @ _m_scale(cz), prof3)
            profiles.append(ring)
        top_verts, bot_verts = profiles[-1], profiles[0]
        face_pts = len(tooth)
        gear_pts = face_pts * teeth
        top_faces = []
        for i in range(teeth):
            for j in range(face_pts // 2 - 1):
                top_faces.append([i * face_pts + j, (i + 1) * face_pts - j - 1, (i + 1) * face_pts - j - 2])
                top_faces.append([i * face_pts + j, (i + 1) * face_pts - j - 2, i * face_pts + j + 1])
        for i in range(teeth):
            top_faces.append([gear_pts, (i + 1) * face_pts - 1, i * face_pts])
            top_faces.append([gear_pts, ((i + 1) % teeth) * face_pts, (i + 1) * face_pts - 1])
        sides = VNF.vertex_array(profiles, caps=False, col_wrap=True, style="min_edge")
        top_cap = VNF(top_verts + [[0, 0, top_verts[0][2]]], [f[::-1] for f in top_faces])
        bot_cap = VNF(bot_verts + [[0, 0, bot_verts[0][2]]], top_faces)
        vnf = _vnf_join([top_cap, bot_cap, sides])
        if left_handed:
            vnf = _vnf_xflip(vnf)
        solid = Bosl2Solid(vnf.polyhedron(), size=[2 * p, 2 * p, thickness])
        if shaft_diam and shaft_diam > 0:
            solid = solid - cylinder(h=worm_diam, d=shaft_diam, center=True)
        return solid

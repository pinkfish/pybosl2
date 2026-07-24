# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/screws.py
#    Pure-Python port of the core of BOSL2's screws.scad, built on top of
#    :class:`~bosl2.threading.Threading`. The :class:`Screws` class turns a metric screw name (``"M6"``,
#    ``"M8x1"``) into ready-to-print geometry: :meth:`Screws.screw` (a threaded/plain shaft plus a
#    socket / hex / button / pan / flat / setscrew head with an optional hex or slot drive recess),
#    :meth:`Screws.nut` (a hex/square nut with a matching threaded hole), and :meth:`Screws.screw_hole`
#    (a clearance/counterbore/countersink hole cutter). :meth:`Screws.screw_info` returns the resolved
#    dimensions as a plain dict.
#
#    The dimension tables (ISO coarse/fine thread pitches, and ISO head sizes for socket cap ISO 4762,
#    hex ISO 4017, button ISO 7380, pan ISO 14583, countersunk ISO 10642/7046, setscrew, and hex/square
#    nuts ISO 4032/4035/4034) are transcribed verbatim from screws.scad and checked in
#    tests/test_screws.py. The threads themselves come from the watertight-polyhedron thread generator
#    in threading.py. Phillips/Torx (and hex/Robertson) drive-recess masks are ported separately in
#    screw_drive.py (the ScrewDrive class), though not yet wired into screw()'s drive= argument.
#    Not ported (a follow-up): UTS/imperial specs, the named-anchor system, shoulder screws, and
#    per-tolerance thread-class diameters.
#
# FileSummary: Metric screws, nuts and screw holes built on the threading port.
# FileGroup: BOSL2

from __future__ import annotations

import math
from dataclasses import dataclass

from bosl2.shapes3d import Bosl2Solid, cuboid, cyl, regular_prism

__all__ = [
    "Screws",
    "ThreadPitches",
    "HexHead",
    "SocketHead",
    "ButtonHead",
    "PanHead",
    "FlatHead",
    "NutSpec",
]


# ---------------------------------------------------------------------------
# Section: metric dimension tables (transcribed from screws.scad)
# ---------------------------------------------------------------------------

# Thread-class name -> the ThreadPitches attribute holding that pitch.
_THREAD_ALIAS = {
    "coarse": "coarse",
    "fine": "fine",
    "medium": "fine",
    "extra fine": "extra_fine",
    "extrafine": "extra_fine",
    "extra-fine": "extra_fine",
    "super fine": "super_fine",
    "superfine": "super_fine",
    "super-fine": "super_fine",
}


@dataclass(frozen=True)
class ThreadPitches:
    """
    ISO metric thread pitches (mm) for one nominal diameter; ``None`` where a class is
    undefined.
    """

    coarse: float
    fine: float | None = None
    extra_fine: float | None = None
    super_fine: float | None = None

    def pitch(self, thread: str = "coarse") -> float:
        """The pitch for a thread class (``"coarse"``/``"fine"``/``"extra-fine"``/``"super-fine"``),
        falling back to coarse if the requested class is undefined for this size."""
        return getattr(self, _THREAD_ALIAS.get(str(thread).lower(), "coarse")) or self.coarse


@dataclass(frozen=True)
class HexHead:
    """Hex cap head (ISO 4017)."""

    width: float  # across-flats
    height: float


@dataclass(frozen=True)
class SocketHead:
    """
    Socket cap head (ISO 4762). Head height == nominal diameter; hex-drive depth == diameter/2.
    """

    head_d: float
    hex_drive: float  # hex drive across-flats


@dataclass(frozen=True)
class ButtonHead:
    """Button head (ISO 7380)."""

    head_d: float
    height: float
    hex_drive: float
    hex_depth: float


@dataclass(frozen=True)
class PanHead:
    """Pan head (ISO 14583)."""

    head_d: float
    height: float


@dataclass(frozen=True)
class FlatHead:
    """Countersunk / flat head (ISO 10642 / ISO 7046), 90-degree included angle."""

    sharp_d: float  # theoretical sharp diameter
    actual_d: float  # actual (truncated) diameter


@dataclass(frozen=True)
class NutSpec:
    """Hex / square nut (ISO 4032 / 4035 / 4034); ``None`` where a thickness class is undefined."""

    width: float  # across-flats
    normal: float
    thin: float | None
    thick: float | None


# nominal diameter -> its thread pitches.
_ISO_THREAD = {
    1: ThreadPitches(0.25, 0.2),
    1.2: ThreadPitches(0.25, 0.2),
    1.4: ThreadPitches(0.3, 0.2),
    1.6: ThreadPitches(0.35, 0.2),
    1.8: ThreadPitches(0.35, 0.2),
    2: ThreadPitches(0.4, 0.25),
    2.2: ThreadPitches(0.45, 0.25),
    2.5: ThreadPitches(0.45, 0.35),
    3: ThreadPitches(0.5, 0.35),
    3.5: ThreadPitches(0.6, 0.35),
    4: ThreadPitches(0.7, 0.5),
    5: ThreadPitches(0.8, 0.5),
    6: ThreadPitches(1, 0.75),
    7: ThreadPitches(1, 0.75),
    8: ThreadPitches(1.25, 1, 0.75),
    9: ThreadPitches(1.25, 1, 0.75),
    10: ThreadPitches(1.5, 1.25, 1, 0.75),
    11: ThreadPitches(1.5, 1, 0.75),
    12: ThreadPitches(1.75, 1.5, 1.25, 1),
    14: ThreadPitches(2, 1.5, 1.25, 1),
    16: ThreadPitches(2, 1.5, 1),
    18: ThreadPitches(2.5, 2, 1.5, 1),
    20: ThreadPitches(2.5, 2, 1.5, 1),
    22: ThreadPitches(2.5, 2, 1.5, 1),
    24: ThreadPitches(3, 2, 1.5, 1),
    27: ThreadPitches(3, 2, 1.5, 1),
    30: ThreadPitches(3.5, 3, 2, 1.5),
    33: ThreadPitches(3.5, 3, 2, 1.5),
    36: ThreadPitches(4, 3, 2, 1.5),
    39: ThreadPitches(4, 3, 2, 1.5),
    42: ThreadPitches(4.5, 4, 3, 2),
    48: ThreadPitches(5, 4, 3, 2),
}

_HEX_HEAD = {
    5: HexHead(8, 3.5),
    6: HexHead(10, 4),
    8: HexHead(13, 5.3),
    10: HexHead(17, 6.4),
    12: HexHead(19, 7.5),
    14: HexHead(22, 8.8),
    16: HexHead(24, 10),
    18: HexHead(27, 11.5),
    20: HexHead(30, 12.5),
    24: HexHead(36, 15),
    30: HexHead(46, 18.7),
}

_SOCKET_HEAD = {
    1.6: SocketHead(3, 1.5),
    2: SocketHead(3.8, 1.5),
    2.5: SocketHead(4.5, 2),
    2.6: SocketHead(5, 2),
    3: SocketHead(5.5, 2.5),
    3.5: SocketHead(6.2, 2.5),
    4: SocketHead(7, 3),
    5: SocketHead(8.5, 4),
    6: SocketHead(10, 5),
    7: SocketHead(12, 6),
    8: SocketHead(13, 6),
    10: SocketHead(16, 8),
    12: SocketHead(18, 10),
    14: SocketHead(21, 12),
    16: SocketHead(24, 14),
    18: SocketHead(27, 14),
    20: SocketHead(30, 17),
    22: SocketHead(33, 17),
    24: SocketHead(36, 19),
    27: SocketHead(40, 19),
    30: SocketHead(45, 22),
    33: SocketHead(50, 24),
    36: SocketHead(54, 27),
    42: SocketHead(63, 32),
    48: SocketHead(72, 36),
}

_BUTTON_HEAD = {
    1.6: ButtonHead(2.9, 0.8, 0.9, 0.55),
    2: ButtonHead(3.5, 1.3, 1.3, 0.69),
    2.5: ButtonHead(4.6, 1.5, 1.5, 0.87),
    3: ButtonHead(5.7, 1.65, 2, 1.04),
    3.5: ButtonHead(5.7, 1.65, 2, 1.21),
    4: ButtonHead(7.6, 2.2, 2.5, 1.30),
    5: ButtonHead(9.5, 2.75, 3, 1.56),
    6: ButtonHead(10.5, 3.3, 4, 2.08),
    8: ButtonHead(14, 4.4, 5, 2.60),
    10: ButtonHead(17.5, 5.5, 6, 3.12),
    12: ButtonHead(21, 6.6, 8, 4.16),
    16: ButtonHead(28, 8.8, 10, 5.2),
}

_PAN_HEAD = {
    1.6: PanHead(3.2, 1.3),
    2: PanHead(4, 1.6),
    2.5: PanHead(5, 2),
    3: PanHead(5.6, 2.4),
    3.5: PanHead(7, 3.1),
    4: PanHead(8, 3.1),
    5: PanHead(9.5, 3.8),
    6: PanHead(12, 4.6),
    8: PanHead(16, 6),
    10: PanHead(20, 7.5),
}

_FLAT_HEAD = {
    1.6: FlatHead(3.6, 2.85),
    2: FlatHead(4.4, 3.65),
    2.5: FlatHead(5.5, 4.55),
    3: FlatHead(6.3, 5.35),
    3.5: FlatHead(8.2, 7.12),
    4: FlatHead(9.4, 8.22),
    5: FlatHead(10.4, 9.12),
    6: FlatHead(12.6, 11.085),
    8: FlatHead(17.3, 15.585),
    10: FlatHead(20, 18.04),
    12: FlatHead(24, 21.75),
    14: FlatHead(28, 25.25),
    16: FlatHead(32, 28.75),
    18: FlatHead(36, 32.2),
    20: FlatHead(40, 35.7),
}

# headless setscrew: diameter -> hex drive across-flats (depth == diameter/2)
_SETSCREW = {
    1.4: 0.7,
    1.6: 0.7,
    1.8: 0.7,
    2: 0.9,
    2.5: 1.3,
    3: 1.5,
    4: 2,
    5: 2.5,
    6: 3,
    8: 4,
    10: 5,
    12: 6,
    16: 8,
    20: 10,
}

_NUT = {
    1.6: NutSpec(3.2, 1.3, 1.0, None),
    2: NutSpec(4, 1.6, 1.2, None),
    2.5: NutSpec(5, 2, 1.6, None),
    3: NutSpec(5.5, 2.4, 1.8, None),
    4: NutSpec(7, 3.2, 2.2, None),
    5: NutSpec(8, 4.7, 2.7, 5.1),
    6: NutSpec(10, 5.2, 3.2, 5.7),
    8: NutSpec(13, 6.8, None, 7.5),
    10: NutSpec(16, 8.4, None, 9.3),
    12: NutSpec(18, 10.8, None, 12),
    16: NutSpec(24, 14.8, None, 16.4),
    20: NutSpec(30, 18, None, 20.3),
    24: NutSpec(36, 21.5, None, 23.9),
    30: NutSpec(46, 25.6, None, 28.6),
    36: NutSpec(55, 31, None, 34.7),
}

# ISO 965 clearance holes: fit name -> radial gap fraction expressed as an absolute add per size band.
# BOSL2 scales these by pitch; we approximate the common medium fit with a diameter-based add.
_CLEARANCE = {"close": 0.2, "normal": 0.5, "loose": 1.0}


def _parse_spec(spec, thread="coarse", pitch=None):
    """Resolve *spec* to ``(diameter, pitch)``.

    *spec* may be ``"M6"``, ``"M8x1"`` (explicit pitch), a bare number (treated as the metric
    nominal diameter), or a mapping already carrying ``diameter``/``pitch``.
    """
    if isinstance(spec, dict):
        diameter = float(spec["diameter"])
        sp = spec.get("pitch")
        return diameter, float(sp) if sp is not None else _lookup_pitch(diameter, thread)
    if isinstance(spec, (int, float)):
        diameter = float(spec)
        return diameter, float(pitch) if pitch is not None else _lookup_pitch(diameter, thread)
    s = str(spec).strip().upper()
    if s.startswith("M"):
        s = s[1:]
    if "X" in s:
        dpart, ppart = s.split("X", 1)
        return float(dpart), float(ppart)
    diameter = float(s)
    return diameter, float(pitch) if pitch is not None else _lookup_pitch(diameter, thread)


def _lookup_pitch(diam, thread):
    if diam not in _ISO_THREAD:
        raise ValueError(f"Unknown metric screw size M{diam:g}")
    return float(_ISO_THREAD[diam].pitch(thread))


class Screws:
    """Metric screws, nuts and screw holes (BOSL2 screws.scad), built on :class:`~bosl2.threading.Threading`.

    Every method is a class method returning a :class:`~bosl2.shapes3d.Bosl2Solid`, except
    :meth:`screw_info`, which returns a plain ``dict`` of resolved dimensions. Screws are built
    head-up: the shaft occupies ``z in [-length, 0]`` (tip at the bottom) and the head sits above
    ``z = 0``.
    """

    # -- resolved dimensions ---------------------------------------------------------------

    @staticmethod
    def screw_info(spec, head: str = "socket", thread: str = "coarse", drive: str = "none", pitch: float | None = None):
        """Resolve a screw specification to a dict of dimensions.

        Keys: ``system``, ``diameter``, ``pitch``, ``head``, ``head_size``, ``head_height``,
        ``head_angle`` (flat heads only), ``drive``, ``drive_size``, ``drive_depth``.
        """
        d, p = _parse_spec(spec, thread, pitch)
        info = {
            "system": "ISO",
            "diameter": d,
            "pitch": p,
            "head": head,
            "drive": drive,
            "drive_size": None,
            "drive_depth": None,
        }

        if head in (None, "none"):
            info["head"] = "none"
            info["head_size"] = None
            info["head_height"] = 0.0
            if drive == "hex":
                info["drive_size"] = _closest(_SETSCREW, d)
                info["drive_depth"] = d / 2
        elif head == "hex":
            spec = _closest(_HEX_HEAD, d)
            info["head_size"], info["head_height"] = spec.width, spec.height
        elif head in ("socket", "socket ribbed"):
            spec = _closest(_SOCKET_HEAD, d)
            info["head_size"], info["head_height"] = spec.head_d, d
            if drive == "hex":
                info["drive_size"], info["drive_depth"] = spec.hex_drive, d / 2
        elif head == "button":
            spec = _closest(_BUTTON_HEAD, d)
            info["head_size"], info["head_height"] = spec.head_d, spec.height
            if drive == "hex":
                info["drive_size"], info["drive_depth"] = spec.hex_drive, spec.hex_depth
        elif head in ("pan", "round"):
            spec = _closest(_PAN_HEAD, d)
            info["head_size"], info["head_height"] = spec.head_d, spec.height
        elif head == "flat":
            spec = _closest(_FLAT_HEAD, d)
            info["head_size"] = spec.actual_d
            info["head_size_sharp"] = spec.sharp_d
            info["head_angle"] = 90.0
            info["head_height"] = (spec.actual_d - d) / 2  # 90-degree cone: radius drop == height
        else:
            raise ValueError(f'Unknown head type "{head}"')
        return info

    # -- the screw -------------------------------------------------------------------------

    @staticmethod
    def screw(
        spec,
        length: float,
        head: str = "socket",
        drive: str = "none",
        thread: str = True,
        thread_len: float | None = None,
        pitch: float | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """A metric screw: a threaded (or plain) shaft plus a head, with an optional drive recess.

        *length* is the shaft length below the head (for a flat head, below the surface). Set
        ``thread=False`` for a plain unthreaded shank, or ``thread_len`` for a partly-threaded shaft.
        """

        info = Screws.screw_info(
            spec,
            head=head,
            drive=drive,
            thread="coarse" if thread in (True, False) else thread,
            pitch=pitch,
        )
        d, _p = info["diameter"], info["pitch"]
        thread_kind = thread if isinstance(thread, str) else "coarse"

        # -- shaft: top face at z=0, tip at z=-length -----------------------------------
        if thread:
            from bosl2.threading import Threading

            _, tp = _parse_spec(spec, thread_kind, pitch)
            tl = length if (thread_len is None or thread_len >= length) else thread_len
            shank_len = length - tl
            shaft = Threading.threaded_rod(d, tl, tp, fn=fn, fa=fa, fs=fs).down(shank_len + tl / 2)
            if shank_len > 1e-9:
                shank = cyl(diameter=d, height=shank_len, fn=fn, fa=fa, fs=fs).down(shank_len / 2)
                shaft = shaft | shank
        else:
            shaft = cyl(diameter=d, height=length, fn=fn, fa=fa, fs=fs).down(length / 2)

        result = shaft
        head_top = info["head_height"]  # top face of the head; 0 for a headless setscrew (recess into shaft)
        headobj = Screws._make_head(info, fn, fa, fs)
        if headobj is not None:
            result = result | headobj

        recess = Screws._make_recess(info, head_top, fn, fa, fs)
        if recess is not None:
            result = result - recess
        return result

    @staticmethod
    def _make_head(info, fn, fa, fs):

        head = info["head"]
        if head in (None, "none"):
            return None
        hh = info["head_height"]
        hs = info["head_size"]
        if head == "hex":
            return regular_prism(6, height=hh, inner_diameter=hs, fn=fn, fa=fa, fs=fs).up(hh / 2)
        if head in ("socket", "socket ribbed"):
            return cyl(diameter=hs, height=hh, chamfer2=hs / 20, fn=fn, fa=fa, fs=fs).up(hh / 2)
        if head == "button":
            rnd = min(hh * 0.9, hs / 2 * 0.9)
            return cyl(diameter=hs, height=hh, rounding2=rnd, fn=fn, fa=fa, fs=fs).up(hh / 2)
        if head in ("pan", "round"):
            return cyl(diameter=hs, height=hh, rounding2=0.2 * hs, fn=fn, fa=fa, fs=fs).up(hh / 2)
        if head == "flat":
            # 90-degree countersunk cone: shaft diameter at the bottom, head diameter at the surface.
            return cyl(
                diameter1=info["diameter"],
                diameter2=hs,
                height=hh,
                fn=fn,
                fa=fa,
                fs=fs,
            ).up(hh / 2)
        return None

    @staticmethod
    def _make_recess(info, head_top, fn, fa, fs):

        drive = info.get("drive")
        size = info.get("drive_size")
        depth = info.get("drive_depth")
        if drive in (None, "none") or not size or not depth:
            return None
        eps = 0.02
        if drive == "hex":
            rec = regular_prism(6, height=depth + eps, inner_diameter=size, fn=fn, fa=fa, fs=fs)
        elif drive == "slot":
            width = size if size else max(0.6, info["diameter"] / 6)
            length = (info["head_size"] or info["diameter"]) + 2
            rec = cuboid([length, width, depth + eps])
        else:
            return None
        # place the recess so its open mouth is flush with the top of the head (or shaft top for setscrews)
        return rec.up(head_top - (depth + eps) / 2 + eps / 2)

    # -- the nut ---------------------------------------------------------------------------

    @staticmethod
    def nut(
        spec,
        thickness: float = "normal",
        shape="hex",
        thread: str = "coarse",
        nutwidth: float | None = None,
        slop: float = 0.0,
        pitch: float | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """A hex or square nut with a threaded hole matching *spec* (BOSL2 nut()).

        *thickness* is ``"normal"``, ``"thin"``, ``"thick"`` or a number (mm). *nutwidth* overrides
        the standard across-flats width. *slop* adds radial clearance to the threaded hole.
        """
        from bosl2.threading import Threading

        d, p = _parse_spec(spec, thread, pitch)
        width, th = _nut_dims(d, thickness, nutwidth)
        return Threading.threaded_nut(width, d, th, p, shape=shape, slop=slop, fn=fn, fa=fa, fs=fs)

    # -- clearance / countersink / counterbore hole cutter ---------------------------------

    @staticmethod
    def screw_hole(
        spec,
        length: float,
        head: str = "none",
        counterbore=0.0,
        fit: str = "normal",
        thread: str = False,
        pitch: float | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """A hole cutter for a screw: clearance shaft, plus optional countersink (flat head) or
        counterbore.

        Returns a solid to *subtract* from your part. The clearance shaft occupies ``z in [-length, 0]``
        with its mouth at ``z = 0``; countersinks/counterbores open upward from there. Set
        ``thread=True`` for a tapped (threaded) hole instead of a clearance hole.
        """

        d, p = _parse_spec(spec, "coarse" if thread in (True, False) else thread, pitch)
        if thread:
            from bosl2.threading import Threading

            # a tapped hole: cut with the rod's thread tap (major + a touch of clearance)
            cutter = Threading.threaded_rod(d + 0.0, length, p, fn=fn, fa=fa, fs=fs).down(length / 2)
        else:
            gap = _CLEARANCE.get(str(fit).lower(), 0.5)
            cutter = cyl(diameter=d + 2 * gap, height=length, fn=fn, fa=fa, fs=fs).down(length / 2)

        if head == "flat":
            info = Screws.screw_info(spec, head="flat", pitch=pitch)
            hs = info["head_size"]
            csk_h = (hs - d) / 2
            csink = cyl(
                diameter1=d,
                diameter2=hs,
                height=csk_h + 0.02,
                fn=fn,
                fa=fa,
                fs=fs,
            ).up((csk_h + 0.02) / 2 - 0.01)
            cutter = cutter | csink
        elif counterbore and counterbore > 0:
            info = Screws.screw_info(spec, head=head if head not in (None, "none") else "socket", pitch=pitch)
            hd = info["head_size"] if head == "hex" else (info["head_size"] or 2 * d)
            if head == "hex":
                hd = 2 * hd / math.sqrt(3)  # across-corners for a hex head pocket
            cb = cyl(diameter=hd, height=counterbore + 0.02, fn=fn, fa=fa, fs=fs).up((counterbore + 0.02) / 2 - 0.01)
            cutter = cutter | cb
        return cutter


# ---------------------------------------------------------------------------
# Section: table helpers
# ---------------------------------------------------------------------------


def _closest(table, diam):
    """Look *diam* up in *table*, falling back to the nearest tabulated size."""
    if diam in table:
        return table[diam]
    key = min(table, key=lambda k: abs(k - diam))
    return table[key]


def _nut_dims(diam, thickness, nutwidth):
    """
    Resolve a nut's ``(across-flats width, thickness)`` for the given size and thickness class.
    """
    spec = _closest(_NUT, diam)
    width = float(nutwidth) if nutwidth is not None else spec.width
    if isinstance(thickness, (int, float)):
        return width, float(thickness)
    t = str(thickness).lower()
    if t == "thin" and spec.thin is not None:
        return width, spec.thin
    if t == "thick" and spec.thick is not None:
        return width, spec.thick
    return width, spec.normal

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/parts/screws.py
#    Pure-Python port of the core of BOSL2's screws.scad, built on top of
#    :class:`Screw` turns a metric screw name (``"M6"``,
#    ``"M8x1"``) into ready-to-print geometry: :class:`Screw` (a threaded/plain shaft plus a
#    socket / hex / button / pan / flat / setscrew head with an optional hex or slot drive recess),
#    :class:`Nut` (a hex/square nut with a matching threaded hole), and :class:`ScrewHole`
#    (a clearance/counterbore/countersink hole cutter). :class:`ScrewSpec` returns the resolved
#    dimensions.
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

"""Metric screws, nuts and screw holes built on the threading port."""
# DocCategory: Parts library
# FileGroup: BOSL2

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from pybosl2.parts.enums import NutShape, ScrewDriveType, ScrewHeadType, ThreadPitchClass
from pybosl2.shapes3d import Bosl2Solid, cuboid, cyl, regular_prism

__all__ = [
    "Nut",
    "Screw",
    "ScrewHole",
    "ScrewSpec",
    "ThreadPitches",
]


# ---------------------------------------------------------------------------
# Section: metric dimension tables (transcribed from screws.scad)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ThreadPitches:
    """ISO metric thread pitches (mm) for one nominal diameter.

    Positional args are ``coarse / fine / extra_fine / super_fine``; ``None``
    marks a pitch class that is undefined for this size.
    """

    coarse: float
    fine: float | None = None
    extra_fine: float | None = None
    super_fine: float | None = None

    def pitch(self, thread: ThreadPitchClass = ThreadPitchClass.COARSE) -> float:
        """Return the pitch for a thread class, falling back to coarse if it's undefined for this size."""
        if thread == ThreadPitchClass.NONE:
            return self.coarse
        lookup: dict[ThreadPitchClass, float | None] = {
            ThreadPitchClass.COARSE: self.coarse,
            ThreadPitchClass.FINE: self.fine,
            ThreadPitchClass.EXTRA_FINE: self.extra_fine,
            ThreadPitchClass.SUPER_FINE: self.super_fine,
        }
        return lookup.get(thread) or self.coarse


@dataclass(frozen=True)
class _HexHead:
    """Hex cap head (ISO 4017)."""

    width: float  # across-flats
    height: float


@dataclass(frozen=True)
class _SocketHead:
    """Socket cap head (ISO 4762). Head height == nominal diameter; hex-drive depth == diameter/2."""

    head_d: float
    hex_drive: float  # hex drive across-flats


@dataclass(frozen=True)
class _ButtonHead:
    """Button head (ISO 7380)."""

    head_d: float
    height: float
    hex_drive: float
    hex_depth: float


@dataclass(frozen=True)
class _PanHead:
    """Pan head (ISO 14583)."""

    head_d: float
    height: float


@dataclass(frozen=True)
class _FlatHead:
    """Countersunk / flat head (ISO 10642 / ISO 7046), 90-degree included angle."""

    sharp_d: float  # theoretical sharp diameter
    actual_d: float  # actual (truncated) diameter


@dataclass(frozen=True)
class _NutSpec:
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
    5: _HexHead(8, 3.5),
    6: _HexHead(10, 4),
    8: _HexHead(13, 5.3),
    10: _HexHead(17, 6.4),
    12: _HexHead(19, 7.5),
    14: _HexHead(22, 8.8),
    16: _HexHead(24, 10),
    18: _HexHead(27, 11.5),
    20: _HexHead(30, 12.5),
    24: _HexHead(36, 15),
    30: _HexHead(46, 18.7),
}

_SOCKET_HEAD = {
    1.6: _SocketHead(3, 1.5),
    2: _SocketHead(3.8, 1.5),
    2.5: _SocketHead(4.5, 2),
    2.6: _SocketHead(5, 2),
    3: _SocketHead(5.5, 2.5),
    3.5: _SocketHead(6.2, 2.5),
    4: _SocketHead(7, 3),
    5: _SocketHead(8.5, 4),
    6: _SocketHead(10, 5),
    7: _SocketHead(12, 6),
    8: _SocketHead(13, 6),
    10: _SocketHead(16, 8),
    12: _SocketHead(18, 10),
    14: _SocketHead(21, 12),
    16: _SocketHead(24, 14),
    18: _SocketHead(27, 14),
    20: _SocketHead(30, 17),
    22: _SocketHead(33, 17),
    24: _SocketHead(36, 19),
    27: _SocketHead(40, 19),
    30: _SocketHead(45, 22),
    33: _SocketHead(50, 24),
    36: _SocketHead(54, 27),
    42: _SocketHead(63, 32),
    48: _SocketHead(72, 36),
}

_BUTTON_HEAD = {
    1.6: _ButtonHead(2.9, 0.8, 0.9, 0.55),
    2: _ButtonHead(3.5, 1.3, 1.3, 0.69),
    2.5: _ButtonHead(4.6, 1.5, 1.5, 0.87),
    3: _ButtonHead(5.7, 1.65, 2, 1.04),
    3.5: _ButtonHead(5.7, 1.65, 2, 1.21),
    4: _ButtonHead(7.6, 2.2, 2.5, 1.30),
    5: _ButtonHead(9.5, 2.75, 3, 1.56),
    6: _ButtonHead(10.5, 3.3, 4, 2.08),
    8: _ButtonHead(14, 4.4, 5, 2.60),
    10: _ButtonHead(17.5, 5.5, 6, 3.12),
    12: _ButtonHead(21, 6.6, 8, 4.16),
    16: _ButtonHead(28, 8.8, 10, 5.2),
}

_PAN_HEAD = {
    1.6: _PanHead(3.2, 1.3),
    2: _PanHead(4, 1.6),
    2.5: _PanHead(5, 2),
    3: _PanHead(5.6, 2.4),
    3.5: _PanHead(7, 3.1),
    4: _PanHead(8, 3.1),
    5: _PanHead(9.5, 3.8),
    6: _PanHead(12, 4.6),
    8: _PanHead(16, 6),
    10: _PanHead(20, 7.5),
}

_FLAT_HEAD = {
    1.6: _FlatHead(3.6, 2.85),
    2: _FlatHead(4.4, 3.65),
    2.5: _FlatHead(5.5, 4.55),
    3: _FlatHead(6.3, 5.35),
    3.5: _FlatHead(8.2, 7.12),
    4: _FlatHead(9.4, 8.22),
    5: _FlatHead(10.4, 9.12),
    6: _FlatHead(12.6, 11.085),
    8: _FlatHead(17.3, 15.585),
    10: _FlatHead(20, 18.04),
    12: _FlatHead(24, 21.75),
    14: _FlatHead(28, 25.25),
    16: _FlatHead(32, 28.75),
    18: _FlatHead(36, 32.2),
    20: _FlatHead(40, 35.7),
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
    1.6: _NutSpec(3.2, 1.3, 1.0, None),
    2: _NutSpec(4, 1.6, 1.2, None),
    2.5: _NutSpec(5, 2, 1.6, None),
    3: _NutSpec(5.5, 2.4, 1.8, None),
    4: _NutSpec(7, 3.2, 2.2, None),
    5: _NutSpec(8, 4.7, 2.7, 5.1),
    6: _NutSpec(10, 5.2, 3.2, 5.7),
    8: _NutSpec(13, 6.8, None, 7.5),
    10: _NutSpec(16, 8.4, None, 9.3),
    12: _NutSpec(18, 10.8, None, 12),
    16: _NutSpec(24, 14.8, None, 16.4),
    20: _NutSpec(30, 18, None, 20.3),
    24: _NutSpec(36, 21.5, None, 23.9),
    30: _NutSpec(46, 25.6, None, 28.6),
    36: _NutSpec(55, 31, None, 34.7),
}

# ISO 965 clearance holes: fit name -> radial gap fraction expressed as an absolute add per size band.
# BOSL2 scales these by pitch; we approximate the common medium fit with a diameter-based add.
_CLEARANCE = {"close": 0.2, "normal": 0.5, "loose": 1.0}


class ScrewSpec:
    """Resolved dimensions for a metric screw.

    Construct directly (replaces the old ``_parse_spec`` helper):
    ``ScrewSpec("M6")``, ``ScrewSpec("M8x1", head=ScrewHeadType.HEX)``, etc.
    Construct directly (replaces the old ``_parse_spec`` helper):
    ``ScrewSpec("M6")``, ``ScrewSpec("M8x1", head=ScrewHeadType.HEX)``, etc.

    Attributes are set by the constructor and may be read freely.
    """

    system: str
    diameter: float
    pitch: float
    head: ScrewHeadType
    head_size: float | None
    head_height: float
    head_angle: float | None
    head_size_sharp: float | None
    drive: ScrewDriveType
    drive_size: float | None
    drive_depth: float | None

    def __init__(
        self,
        spec: str | dict[str, float] | float,
        head: ScrewHeadType = ScrewHeadType.NONE,
        thread: ThreadPitchClass = ThreadPitchClass.COARSE,
        drive: ScrewDriveType = ScrewDriveType.NONE,
        pitch: float | None = None,
    ) -> None:
        """Resolve a screw specification to a fully-populated :class:`ScrewSpec`.

        *spec* may be ``"M6"``, ``"M8x1"`` (explicit pitch), a bare number (treated as the
        metric nominal diameter), or a mapping already carrying ``diameter``/``pitch``.  When
        *head* is anything other than ``ScrewHeadType.NONE`` the appropriate head dimensions
        and optional drive-recess dimensions are looked up from the ISO tables.
        """
        self.system = "ISO"

        if isinstance(spec, dict):
            d = float(spec["diameter"])
            p = float(spec.get("pitch", 0)) if spec.get("pitch") is not None else _lookup_pitch(d, thread)
        elif isinstance(spec, (int, float)):
            d = float(spec)
            p = float(pitch) if pitch is not None else _lookup_pitch(d, thread)
        else:
            s = str(spec).strip().upper()
            if s.startswith("M"):
                s = s[1:]
            if "X" in s:
                dpart, ppart = s.split("X", 1)
                d, p = float(dpart), float(ppart)
            else:
                d = float(s)
                p = float(pitch) if pitch is not None else _lookup_pitch(d, thread)

        self.diameter = d
        self.pitch = p
        self.head = head
        self.drive = drive
        self.head_size = None
        self.head_height = 0.0
        self.head_angle = None
        self.head_size_sharp = None
        self.drive_size = None
        self.drive_depth = None

        if head in (None, ScrewHeadType.NONE):
            self.head = ScrewHeadType.NONE
            if drive == ScrewDriveType.HEX:
                self.drive_size = _closest(_SETSCREW, d)
                self.drive_depth = d / 2
        elif head == ScrewHeadType.HEX:
            spec_h: _HexHead = _closest(_HEX_HEAD, d)
            self.head_size, self.head_height = spec_h.width, spec_h.height
        elif head in (ScrewHeadType.SOCKET, ScrewHeadType.SOCKET_RIBBED):
            spec_s: _SocketHead = _closest(_SOCKET_HEAD, d)
            self.head_size, self.head_height = spec_s.head_d, d
            if drive == ScrewDriveType.HEX:
                self.drive_size, self.drive_depth = spec_s.hex_drive, d / 2
        elif head == ScrewHeadType.BUTTON:
            spec_b: _ButtonHead = _closest(_BUTTON_HEAD, d)
            self.head_size, self.head_height = spec_b.head_d, spec_b.height
            if drive == ScrewDriveType.HEX:
                self.drive_size, self.drive_depth = spec_b.hex_drive, spec_b.hex_depth
        elif head in (ScrewHeadType.PAN, ScrewHeadType.ROUND):
            spec_p: _PanHead = _closest(_PAN_HEAD, d)
            self.head_size, self.head_height = spec_p.head_d, spec_p.height
        elif head == ScrewHeadType.FLAT:
            spec_f: _FlatHead = _closest(_FLAT_HEAD, d)
            self.head_size = spec_f.actual_d
            self.head_size_sharp = spec_f.sharp_d
            self.head_angle = 90.0
            self.head_height = (spec_f.actual_d - d) / 2
        else:
            raise ValueError(f'Unknown head type "{head}"')


def _lookup_pitch(diam: float, thread: ThreadPitchClass) -> float:
    if diam not in _ISO_THREAD:
        raise ValueError(f"Unknown metric screw size M{diam:g}")
    return float(_ISO_THREAD[diam].pitch(thread))


def _make_head(info: ScrewSpec, fn: int | None, fa: float | None, fs: float | None) -> Bosl2Solid | None:
    """Build the screw head from resolved dimensions."""
    head = info.head
    if head in (None, ScrewHeadType.NONE):
        return None
    hh = info.head_height
    hs = info.head_size
    assert hs is not None, f"head_size not set for head type {head}"
    if head == ScrewHeadType.HEX:
        return regular_prism(6, height=hh, inner_diameter=hs, fn=fn, fa=fa, fs=fs).up(hh / 2)
    if head in (ScrewHeadType.SOCKET, ScrewHeadType.SOCKET_RIBBED):
        return cyl(diameter=hs, height=hh, chamfer2=hs / 20, fn=fn, fa=fa, fs=fs).up(hh / 2)
    if head == ScrewHeadType.BUTTON:
        rnd = min(hh * 0.9, hs / 2 * 0.9)
        return cyl(diameter=hs, height=hh, rounding2=rnd, fn=fn, fa=fa, fs=fs).up(hh / 2)
    if head in (ScrewHeadType.PAN, ScrewHeadType.ROUND):
        return cyl(diameter=hs, height=hh, rounding2=0.2 * hs, fn=fn, fa=fa, fs=fs).up(hh / 2)
    if head == ScrewHeadType.FLAT:
        return cyl(diameter1=info.diameter, diameter2=hs, height=hh, fn=fn, fa=fa, fs=fs).up(hh / 2)
    return None


def _make_recess(
    info: ScrewSpec, head_top: float, fn: int | None, fa: float | None, fs: float | None
) -> Bosl2Solid | None:
    """Build the drive recess from resolved dimensions."""
    drive = info.drive
    size = info.drive_size
    depth = info.drive_depth
    if drive in (None, ScrewDriveType.NONE) or not size or not depth:
        return None
    eps = 0.02
    if drive == ScrewDriveType.HEX:
        rec = regular_prism(6, height=depth + eps, inner_diameter=size, fn=fn, fa=fa, fs=fs)
    elif drive == ScrewDriveType.SLOT:
        width = size if size else max(0.6, info.diameter / 6)
        length = (info.head_size or info.diameter) + 2
        rec = cuboid([length, width, depth + eps], fn=fn, fa=fa, fs=fs)
    else:
        return None
    return rec.up(head_top - (depth + eps) / 2 + eps / 2)


class Screw:
    """A metric screw: threaded (or plain) shaft plus a head with an optional drive recess.

    Examples:
        An M6×20 socket-head cap screw:

        .. pythonscad-example::

            from pybosl2.parts.enums import ScrewHeadType, ScrewDriveType
            from pybosl2.parts.screws import Screw
            Screw("M6", length=20, head=ScrewHeadType.SOCKET, drive=ScrewDriveType.HEX).show()

    """

    def __init__(
        self,
        spec: str | dict[str, float] | float,
        length: float,
        head: ScrewHeadType = ScrewHeadType.SOCKET,
        drive: ScrewDriveType = ScrewDriveType.NONE,
        thread: ThreadPitchClass = ThreadPitchClass.COARSE,
        thread_len: float | None = None,
        pitch: float | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a screw from *spec* (``"M6"`` / ``"M8x1"``) and dimensions."""
        self._spec: ScrewSpec = ScrewSpec(
            spec,
            head=head,
            thread=ThreadPitchClass.COARSE if isinstance(thread, bool) else thread,
            drive=drive,
            pitch=pitch,
        )
        self._length: float = length
        self._thread: ThreadPitchClass = thread if isinstance(thread, ThreadPitchClass) else ThreadPitchClass.COARSE
        self._thread_len: float | None = thread_len
        self._fn: int | None = fn
        self._fa: float | None = fa
        self._fs: float | None = fs
        self._solid: Bosl2Solid | None = None

    @property
    def spec(self) -> ScrewSpec:
        """The resolved :class:`ScrewSpec`."""
        return self._spec

    @property
    def diameter(self) -> float:
        """Nominal screw diameter in mm."""
        return self._spec.diameter

    @property
    def pitch(self) -> float:
        """Thread pitch in mm."""
        return self._spec.pitch

    @property
    def head(self) -> ScrewHeadType:
        """Head style."""
        return self._spec.head

    @property
    def head_size(self) -> float | None:
        """Head diameter / across-flats in mm."""
        return self._spec.head_size

    @property
    def head_height(self) -> float:
        """Head height in mm (0 for headless)."""
        return self._spec.head_height

    @property
    def drive(self) -> ScrewDriveType:
        """Drive recess type."""
        return self._spec.drive

    @property
    def length(self) -> float:
        """Shaft length below the head in mm."""
        return self._length

    def shape(self) -> Bosl2Solid:
        """Build and return the screw geometry (result is cached)."""
        if self._solid is not None:
            return self._solid

        d = self._spec.diameter
        if self._thread != ThreadPitchClass.NONE:
            from pybosl2.parts.threading import iso_threaded_rod

            tp = ScrewSpec(self._spec.diameter, thread=self._thread, pitch=self._spec.pitch).pitch
            tl = self._length if (self._thread_len is None or self._thread_len >= self._length) else self._thread_len
            shank_len = self._length - tl
            shaft = iso_threaded_rod(d, tl, tp, fn=self._fn, fa=self._fa, fs=self._fs).shape().down(shank_len + tl / 2)
            if shank_len > 1e-9:
                shank = cyl(diameter=d, height=shank_len, fn=self._fn, fa=self._fa, fs=self._fs).down(shank_len / 2)
                shaft = shaft | shank
        else:
            shaft = cyl(diameter=d, height=self._length, fn=self._fn, fa=self._fa, fs=self._fs).down(self._length / 2)

        result = shaft
        head_top = self._spec.head_height
        headobj = _make_head(self._spec, self._fn, self._fa, self._fs)
        if headobj is not None:
            result = result | headobj

        recess = _make_recess(self._spec, head_top, self._fn, self._fa, self._fs)
        if recess is not None:
            result = result - recess

        self._solid = result
        return result

    def show(self) -> None:
        """Display the screw in the viewer."""
        self.shape().show()


class Nut:
    """A hex or square nut with a threaded hole.

    Examples:
        An M8 hex nut of normal thickness:

        .. pythonscad-example::

            from pybosl2.parts.screws import Nut
            Nut("M8").show()

    """

    def __init__(
        self,
        spec: str | dict[str, float] | float,
        thickness: float | str = "normal",
        shape: NutShape = NutShape.HEX,
        thread: ThreadPitchClass = ThreadPitchClass.COARSE,
        nutwidth: float | None = None,
        slop: float = 0.0,
        pitch: float | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a nut from *spec* (``"M8"``) and dimensions."""
        self._spec: ScrewSpec = ScrewSpec(spec, thread=thread, pitch=pitch)
        self._thickness: float | str = thickness
        self._shape: NutShape = shape
        self._nutwidth: float | None = nutwidth
        self._slop: float = slop
        self._fn: int | None = fn
        self._fa: float | None = fa
        self._fs: float | None = fs
        self._solid: Bosl2Solid | None = None

    @property
    def spec(self) -> ScrewSpec:
        """The resolved :class:`ScrewSpec`."""
        return self._spec

    @property
    def diameter(self) -> float:
        """Nominal diameter in mm."""
        return self._spec.diameter

    @property
    def pitch(self) -> float:
        """Thread pitch in mm."""
        return self._spec.pitch

    @property
    def shape_nut(self) -> NutShape:
        """Nut outer shape."""
        return self._shape

    def shape(self) -> Bosl2Solid:
        """Build and return the nut geometry (result is cached)."""
        if self._solid is not None:
            return self._solid

        from pybosl2.parts.threading import iso_threaded_nut

        width, th = _nut_dims(self._spec.diameter, self._thickness, self._nutwidth)
        self._solid = iso_threaded_nut(
            width,
            self._spec.diameter,
            th,
            self._spec.pitch,
            shape=self._shape,
            slop=self._slop,
            fn=self._fn,
            fa=self._fa,
            fs=self._fs,
        ).shape()
        return self._solid

    def show(self) -> None:
        """Display the nut in the viewer."""
        self.shape().show()


class ScrewHole:
    """A hole cutter for a screw: clearance shaft plus optional countersink/counterbore.

    Returns a solid to *subtract* from your part.  The clearance shaft occupies
    ``z in [-length, 0]`` with its mouth at ``z = 0``; countersinks/counterbores
    open upward from there.

    Examples:
        Drill a clearance hole for an M6 bolt through a 10 mm plate:

        .. pythonscad-example::

            from pybosl2.parts.enums import ScrewHeadType
            from pybosl2.parts.screws import ScrewHole
            from pybosl2.solid import cuboid
            (cuboid([20, 20, 10])
             - ScrewHole("M6", length=10, head=ScrewHeadType.SOCKET, fit="normal").shape()).show()

    """

    def __init__(
        self,
        spec: str | dict[str, float] | float,
        length: float,
        head: ScrewHeadType = ScrewHeadType.NONE,
        counterbore: float = 0.0,
        fit: str = "normal",
        thread: ThreadPitchClass = ThreadPitchClass.NONE,
        pitch: float | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a hole cutter from *spec* (``"M6"``) and dimensions."""
        self._spec_str: str | dict[str, float] | float = spec
        self._length: float = length
        self._head: ScrewHeadType = head
        self._counterbore: float = counterbore
        self._fit: str = fit
        self._thread: ThreadPitchClass = thread
        self._pitch: float | None = pitch
        self._fn: int | None = fn
        self._fa: float | None = fa
        self._fs: float | None = fs
        self._solid: Bosl2Solid | None = None

    @property
    def fit(self) -> str:
        """Clearance fit class (``"close"`` / ``"normal"`` / ``"loose"``)."""
        return self._fit

    @property
    def length(self) -> float:
        """Hole depth in mm."""
        return self._length

    def shape(self) -> Bosl2Solid:
        """Build and return the hole cutter geometry (result is cached)."""
        if self._solid is not None:
            return self._solid

        use_thread = self._thread != ThreadPitchClass.NONE
        sp = ScrewSpec(
            self._spec_str,
            thread=ThreadPitchClass.COARSE if not use_thread else self._thread,
            pitch=self._pitch,
        )
        d, p = sp.diameter, sp.pitch
        if use_thread:
            from pybosl2.parts.threading import iso_threaded_rod

            cutter = (
                iso_threaded_rod(d + 0.0, self._length, p, fn=self._fn, fa=self._fa, fs=self._fs)
                .shape()
                .down(self._length / 2)
            )
        else:
            gap = _CLEARANCE.get(str(self._fit).lower(), 0.5)
            cutter = cyl(diameter=d + 2 * gap, height=self._length, fn=self._fn, fa=self._fa, fs=self._fs).down(
                self._length / 2
            )

        if self._head == ScrewHeadType.FLAT:
            info = ScrewSpec(self._spec_str, head=ScrewHeadType.FLAT, pitch=self._pitch)
            hs = info.head_size
            assert hs is not None
            csk_h = (hs - d) / 2
            csink = cyl(
                diameter1=d,
                diameter2=hs,
                height=csk_h + 0.02,
                fn=self._fn,
                fa=self._fa,
                fs=self._fs,
            ).up((csk_h + 0.02) / 2 - 0.01)
            cutter = cutter | csink
        elif self._counterbore and self._counterbore > 0:
            info = ScrewSpec(
                self._spec_str,
                head=self._head if self._head not in (None, ScrewHeadType.NONE) else ScrewHeadType.SOCKET,
                pitch=self._pitch,
            )
            raw_hd = info.head_size if self._head == ScrewHeadType.HEX else (info.head_size or 2 * d)
            assert raw_hd is not None
            hd: float = raw_hd
            if self._head == ScrewHeadType.HEX:
                hd = 2 * hd / math.sqrt(3)
            cb = cyl(
                diameter=hd,
                height=self._counterbore + 0.02,
                fn=self._fn,
                fa=self._fa,
                fs=self._fs,
            ).up((self._counterbore + 0.02) / 2 - 0.01)
            cutter = cutter | cb

        self._solid = cutter
        return cutter

    def show(self) -> None:
        """Display the hole cutter in the viewer."""
        self.shape().show()


# ---------------------------------------------------------------------------
# Section: table helpers
# ---------------------------------------------------------------------------


def _closest(table: dict[Any, Any], diam: float) -> Any:
    """Look *diam* up in *table*, falling back to the nearest tabulated size."""
    if diam in table:
        return table[diam]
    key = min(table, key=lambda k: abs(k - diam))
    return table[key]


def _nut_dims(diam: float, thickness: float | str | None, nutwidth: float | None) -> tuple[float, float]:
    """Resolve a nut's ``(across-flats width, thickness)`` for the given size and thickness class."""
    spec = _closest(_NUT, diam)
    width = float(nutwidth) if nutwidth is not None else spec.width
    if thickness is None:
        return width, spec.normal
    if isinstance(thickness, (int, float)):
        return width, float(thickness)
    t = str(thickness).lower()
    if t == "thin" and spec.thin is not None:
        return width, spec.thin
    if t == "thick" and spec.thick is not None:
        return width, spec.thick
    return width, spec.normal

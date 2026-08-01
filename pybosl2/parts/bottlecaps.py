# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/parts/bottlecaps.py
#    Pure-Python port of the standard soda-bottle threadings from BOSL2's bottlecaps.scad: the
#    PCO-1810 and PCO-1881 necks and caps. The :class:`BottleCaps` class exposes them as static
#    methods returning :class:`~pybosl2.shapes3d.Bosl2Solid` geometry -- a neck to graft onto a bottle
#    body, and a matching cap.
#
#    The neck profile (inner bore, support ring, tamper-ring channel and sealing lip) is built the
#    same way BOSL2 does: a :func:`~pybosl2.drawing.turtle` outline revolved with rotate_extrude. The
#    threads use this package's :meth:`~pybosl2.threading.Threading.thread_helix`, with the two thread
#    breaks cut by the same zrot_copies-placed prismoids as BOSL2.
#
#    Approximations (this port's threading/cyl lack a few BOSL2 features): the thread lead-in
#    ``taper`` is not applied, cap threads are built without the ``internal=`` flank flip, and the
#    ``knurled``/``ribbed`` cap surface textures fall back to a plain wall (VNF texturing is not in
#    this port). The named-anchor system is not reproduced; geometry is anchored bottom-on-origin.
#    Not ported (follow-ups): generic_bottle_neck/cap, the bottle adapters, and the SPI (sp_) threads.
#
# FileSummary: PCO-1810 / PCO-1881 bottle necks and caps.
# DocCategory: Parts library
# FileGroup: BOSL2

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from pybosl2._helpers import union
from pybosl2._native import native
from pybosl2.constants import BOTTOM, RIGHT
from pybosl2.distributors import Distributable
from pybosl2.parts.threading import Threading
from pybosl2.shapes3d import Bosl2Solid, cyl, prismoid
from pybosl2.turtle import Turtle2DState, TurtleCommand, turtle2d
from pybosl2.turtle import TurtleCommandType as TCT  # noqa: N817

if TYPE_CHECKING:  # real stub-typed imports for the checker (identical to pre-lazy)
    from pythonscad import polygon as _opolygon
    from pythonscad import rotate_extrude as _orotate_extrude
else:
    _opolygon = native("polygon")
    _orotate_extrude = native("rotate_extrude")

__all__ = ["BottleCaps", "BottleThreadSpec", "BottleCapTexture"]


@dataclass(frozen=True)
class BottleThreadSpec:
    """All dimensions (mm) of one bottle threading's neck and cap, from bottlecaps.scad."""

    # -- neck profile --
    inner_d: float
    neck_d: float
    neck_h: float
    support_d: float
    support_width: float
    support_rad: float
    support_h: float
    support_ang: float
    tamper_ring_d: float
    tamper_ring_width: float
    tamper_base_d: float
    tamper_base_h: float
    threadbase_d: float
    thread_pitch: float
    flank_angle: float
    thread_od: float
    lip_d: float
    lip_h: float
    lip_leadin_r: float
    lip_recess_d: float
    lip_recess_h: float
    lip_roundover_r: float
    neck_turns: float
    # -- cap --
    cap_id: float
    cap_tamper_ring_h: float
    cap_thread_od: float
    cap_thread_pitch: float
    cap_flank_angle: float
    cap_thread_depth: float
    cap_turns: float
    # -- variant-specific (only one threading uses each) --
    tamper_ring_r: float | None = None  # PCO-1810 tamper-ring corner radius
    tamper_ring_ang: float | None = None  # PCO-1881 tamper-ring flank angle
    tamper_divot_r: float | None = None  # PCO-1881 tamper divot radius


# PCO-1810 and PCO-1881 neck/cap dimensions (mm), transcribed from bottlecaps.scad.
_PCO1810 = BottleThreadSpec(
    inner_d=21.74,
    neck_d=26.19,
    neck_h=5.00,
    support_d=33.00,
    support_width=1.45,
    support_rad=0.40,
    support_h=21.00,
    support_ang=16,
    tamper_ring_d=27.97,
    tamper_ring_width=0.50,
    tamper_base_d=25.71,
    tamper_base_h=14.10,
    threadbase_d=24.51,
    thread_pitch=3.18,
    flank_angle=20,
    thread_od=27.43,
    lip_d=25.07,
    lip_h=1.70,
    lip_leadin_r=0.20,
    lip_recess_d=24.94,
    lip_recess_h=1.00,
    lip_roundover_r=0.58,
    neck_turns=810,
    cap_id=28.58,
    cap_tamper_ring_h=14.10,
    cap_thread_od=28.58,
    cap_thread_pitch=3.18,
    cap_flank_angle=20,
    cap_thread_depth=1.6,
    cap_turns=810,
    tamper_ring_r=1.60,
)
_PCO1881 = BottleThreadSpec(
    inner_d=21.74,
    neck_d=26.19,
    neck_h=5.00,
    support_d=33.00,
    support_width=0.58,
    support_rad=0.30,
    support_h=17.00,
    support_ang=15,
    tamper_ring_d=28.00,
    tamper_ring_width=0.30,
    tamper_base_d=25.71,
    tamper_base_h=11.20,
    threadbase_d=24.20,
    thread_pitch=2.70,
    flank_angle=15,
    thread_od=27.4,
    lip_d=25.07,
    lip_h=1.70,
    lip_leadin_r=0.30,
    lip_recess_d=24.94,
    lip_recess_h=1.00,
    lip_roundover_r=0.58,
    neck_turns=650,
    cap_id=28.58,
    cap_tamper_ring_h=11.20,
    cap_thread_od=25.5,
    cap_thread_pitch=2.70,
    cap_flank_angle=15,
    cap_thread_depth=1.6,
    cap_turns=650,
    tamper_ring_ang=45,
    tamper_divot_r=1.08,
)


def _turtle_start(x, y=0.0):
    """Turtle state starting at (x, y) heading +X."""
    return Turtle2DState(path=[[float(x), float(y)]])


def _pco1810_profile(diameter: "BottleThreadSpec"):
    height = diameter.support_h + diameter.neck_h
    return turtle2d(
        [
            TurtleCommand(TCT.UNTILX, size=diameter.neck_d / 2),
            TurtleCommand(TCT.LEFT, angle=90),
            TurtleCommand(TCT.MOVE, size=diameter.neck_h - 1),
            TurtleCommand(TCT.ARCRIGHT, radius=1, angle=90),
            TurtleCommand(TCT.UNTILX, size=diameter.support_d / 2 - diameter.support_rad),
            TurtleCommand(TCT.ARCLEFT, radius=diameter.support_rad, angle=90),
            TurtleCommand(TCT.MOVE, size=diameter.support_width),
            TurtleCommand(TCT.ARCLEFT, radius=diameter.support_rad, angle=90 - diameter.support_ang),
            TurtleCommand(TCT.UNTILX, size=diameter.tamper_base_d / 2),
            TurtleCommand(TCT.RIGHT, angle=90 - diameter.support_ang),
            TurtleCommand(TCT.UNTILY, size=height - diameter.tamper_base_h),
            TurtleCommand(TCT.RIGHT, angle=90),
            TurtleCommand(TCT.UNTILX, size=diameter.tamper_ring_d / 2),
            TurtleCommand(TCT.LEFT, angle=90),
            TurtleCommand(TCT.MOVE, size=diameter.tamper_ring_width),
            TurtleCommand(TCT.ARCLEFT, radius=diameter.tamper_ring_r, angle=90),
            TurtleCommand(TCT.UNTILX, size=diameter.threadbase_d / 2),
            TurtleCommand(TCT.RIGHT, angle=90),
            TurtleCommand(TCT.UNTILY, size=height - diameter.lip_h - diameter.lip_leadin_r),
            TurtleCommand(TCT.ARCRIGHT, radius=diameter.lip_leadin_r, angle=90),
            TurtleCommand(TCT.UNTILX, size=diameter.lip_d / 2),
            TurtleCommand(TCT.LEFT, angle=90),
            TurtleCommand(TCT.UNTILY, size=height - diameter.lip_recess_h),
            TurtleCommand(TCT.LEFT, angle=90),
            TurtleCommand(TCT.UNTILX, size=diameter.lip_recess_d / 2),
            TurtleCommand(TCT.RIGHT, angle=90),
            TurtleCommand(TCT.UNTILY, size=height - diameter.lip_roundover_r),
            TurtleCommand(TCT.ARCLEFT, radius=diameter.lip_roundover_r, angle=90),
            TurtleCommand(TCT.UNTILX, size=diameter.inner_d / 2),
        ],
        state=_turtle_start(diameter.inner_d / 2),
    ).points()


def _pco1881_profile(diameter: "BottleThreadSpec"):
    height = diameter.support_h + diameter.neck_h
    return turtle2d(
        [
            TurtleCommand(TCT.UNTILX, size=diameter.neck_d / 2),
            TurtleCommand(TCT.LEFT, angle=90),
            TurtleCommand(TCT.MOVE, size=diameter.neck_h - 1),
            TurtleCommand(TCT.ARCRIGHT, radius=1, angle=90),
            TurtleCommand(TCT.UNTILX, size=diameter.support_d / 2 - diameter.support_rad),
            TurtleCommand(TCT.ARCLEFT, radius=diameter.support_rad, angle=90),
            TurtleCommand(TCT.MOVE, size=diameter.support_width),
            TurtleCommand(TCT.ARCLEFT, radius=diameter.support_rad, angle=90 - diameter.support_ang),
            TurtleCommand(TCT.UNTILX, size=diameter.tamper_base_d / 2),
            TurtleCommand(TCT.ARCRIGHT, radius=diameter.tamper_divot_r, angle=180 - diameter.support_ang * 2),
            TurtleCommand(TCT.LEFT, angle=90 - diameter.support_ang),
            TurtleCommand(TCT.UNTILY, size=height - diameter.tamper_base_h),
            TurtleCommand(TCT.RIGHT, angle=90),
            TurtleCommand(TCT.UNTILX, size=diameter.tamper_ring_d / 2),
            TurtleCommand(TCT.LEFT, angle=90),
            TurtleCommand(TCT.MOVE, size=diameter.tamper_ring_width),
            TurtleCommand(TCT.LEFT, angle=diameter.tamper_ring_ang),
            TurtleCommand(TCT.UNTILX, size=diameter.threadbase_d / 2),
            TurtleCommand(TCT.RIGHT, angle=diameter.tamper_ring_ang),
            TurtleCommand(TCT.UNTILY, size=height - diameter.lip_h - diameter.lip_leadin_r),
            TurtleCommand(TCT.ARCRIGHT, radius=diameter.lip_leadin_r, angle=90),
            TurtleCommand(TCT.UNTILX, size=diameter.lip_d / 2),
            TurtleCommand(TCT.LEFT, angle=90),
            TurtleCommand(TCT.UNTILY, size=height - diameter.lip_recess_h),
            TurtleCommand(TCT.LEFT, angle=90),
            TurtleCommand(TCT.UNTILX, size=diameter.lip_recess_d / 2),
            TurtleCommand(TCT.RIGHT, angle=90),
            TurtleCommand(TCT.UNTILY, size=height - diameter.lip_roundover_r),
            TurtleCommand(TCT.ARCLEFT, radius=diameter.lip_roundover_r, angle=90),
            TurtleCommand(TCT.UNTILX, size=diameter.inner_d / 2),
        ],
        state=_turtle_start(diameter.inner_d / 2),
    ).points()


def _neck_thread(diameter: "BottleThreadSpec", fn: int | None = None, fa: float | None = None, fs: float | None = None):
    """The neck's external thread ridge with its two thread breaks (BOSL2 thread_helix + prismoids).

    The lead-in ``taper`` BOSL2 applies is not reproduced (this port's thread_helix has no taper).
    """
    thread_h = (diameter.thread_od - diameter.threadbase_d) / 2
    turns = diameter.neck_turns / 360
    thread = Threading.thread_helix(
        d=diameter.threadbase_d - 0.1,
        pitch=diameter.thread_pitch,
        thread_depth=thread_h + 0.1,
        flank_angle=diameter.flank_angle,
        turns=turns,
    )
    thread = thread.down(turns * diameter.thread_pitch / 2)  # BOSL2 anchor=TOP: top at z=0
    top = 1.82 + 2 * math.sin(math.radians(29)) * thread_h
    cuts = []
    for m_out in Distributable.zrot_copy_mats(rots=[90, 270]):
        for m_in in Distributable.zrot_copy_mats(rots=[-28, 28], radius=diameter.threadbase_d / 2):
            block = prismoid(
                [20, 1.82],
                [20, top],
                height=thread_h + 0.1,
                anchor=BOTTOM,
                orient=RIGHT,
                fn=fn,
                fa=fa,
                fs=fs,
            )
            cuts.append(block.multmatrix((m_out @ m_in).tolist()))
    return thread - union(cuts)


def _build_neck(
    diameter: "BottleThreadSpec",
    profile,
    bottom_half: bool,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
):
    height = diameter.support_h + diameter.neck_h
    body = Bosl2Solid(
        _orotate_extrude(_opolygon([[float(x), float(y)] for x, y in profile]), fn=fn),
        size=[diameter.support_d, diameter.support_d, height],
    )
    thread = _neck_thread(diameter, fn=fn, fa=fa, fs=fs)
    if bottom_half:
        thread = thread.bottom_half()
    thread = thread.up(height - diameter.lip_h)
    return Bosl2Solid((body | thread).shape, size=[diameter.support_d, diameter.support_d, height])


class BottleCapTexture(Enum):
    NONE = "none"
    RIBS = "ribs"
    CHECKERS = "checkers"


def _build_cap(
    diameter: "BottleThreadSpec",
    wall: float,
    texture: str | BottleCapTexture,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
):
    _ = texture.value if isinstance(texture, BottleCapTexture) else texture
    w = diameter.cap_id + 2 * wall
    height = diameter.cap_tamper_ring_h + wall
    outer = cyl(diameter=w, length=height, anchor=BOTTOM, fn=fn, fa=fa, fs=fs)
    bore = cyl(diameter=diameter.cap_id, height=height, anchor=BOTTOM, fn=fn, fa=fa, fs=fs).up(wall)
    shell = outer - bore
    turns = diameter.cap_turns / 360
    thread_height = turns * diameter.cap_thread_pitch
    # internal thread (this port's thread_helix has no internal= flank flip -- approximate).
    thread = Threading.thread_helix(
        d=diameter.cap_thread_od - diameter.cap_thread_depth * 2,
        pitch=diameter.cap_thread_pitch,
        thread_depth=diameter.cap_thread_depth,
        flank_angle=diameter.cap_flank_angle,
        turns=turns,
    )
    thread = thread.up(thread_height / 2 + wall + 2)  # BOSL2 anchor=BOTTOM, then up(wall+2)
    cap = (shell | thread).rotate([0, 0, 45])
    return Bosl2Solid(cap.shape, size=[w, w, height])


class BottleCaps:
    """Standard soda-bottle necks and caps (BOSL2 bottlecaps.scad, PCO-1810 & PCO-1881).

    Each ``*_neck`` / ``*_cap`` returns a :class:`~pybosl2.shapes3d.Bosl2Solid` anchored with its
    bottom on the XY plane. See the module docstring for the geometry approximations relative to
    BOSL2 (thread taper, internal-thread flank, and cap surface textures are not reproduced).
    """

    @staticmethod
    def pco1810_neck(fn: int | None = None, fa: float | None = None, fs: float | None = None) -> Bosl2Solid:
        """A PCO-1810 threaded beverage-bottle neck (BOSL2 pco1810_neck()).

        Examples:
            A standard PCO 1810 bottle neck (28 mm):

            .. pythonscad-example::

                BottleCaps.pco1810_neck(fa=6).show()
        """
        return _build_neck(_PCO1810, _pco1810_profile(_PCO1810), bottom_half=True, fn=fn, fa=fa, fs=fs)

    @staticmethod
    def pco1810_cap(
        wall: float = 2,
        texture: str | BottleCapTexture = BottleCapTexture.NONE,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """A cap for a PCO-1810 bottle (BOSL2 pco1810_cap()). ``texture`` other than ``"none"`` falls
        back to a plain wall (surface texturing is not in this port).

        Examples:
            A plain-walled cap for a PCO 1810 neck:

            .. pythonscad-example::

                BottleCaps.pco1810_cap(fa=6).show()
        """
        return _build_cap(_PCO1810, wall, texture, fn=fn, fa=fa, fs=fs)

    @staticmethod
    def pco1881_neck(fn: int | None = None, fa: float | None = None, fs: float | None = None) -> Bosl2Solid:
        """A PCO-1881 threaded beverage-bottle neck (BOSL2 pco1881_neck()).

        Examples:
            A standard PCO 1881 bottle neck (38 mm):

            .. pythonscad-example::

                BottleCaps.pco1881_neck(fa=6).show()
        """
        return _build_neck(_PCO1881, _pco1881_profile(_PCO1881), bottom_half=False, fn=fn, fa=fa, fs=fs)

    @staticmethod
    def pco1881_cap(
        wall: float = 2,
        texture: str | BottleCapTexture = BottleCapTexture.NONE,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """A cap for a PCO-1881 bottle (BOSL2 pco1881_cap()). ``texture`` other than ``"none"`` falls
        back to a plain wall (surface texturing is not in this port)."""
        return _build_cap(_PCO1881, wall, texture, fn=fn, fa=fa, fs=fs)

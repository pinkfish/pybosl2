# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/bottlecaps.py
#    Pure-Python port of the standard soda-bottle threadings from BOSL2's bottlecaps.scad: the
#    PCO-1810 and PCO-1881 necks and caps. The :class:`BottleCaps` class exposes them as static
#    methods returning :class:`~bosl2.shapes3d.Bosl2Solid` geometry -- a neck to graft onto a bottle
#    body, and a matching cap.
#
#    The neck profile (inner bore, support ring, tamper-ring channel and sealing lip) is built the
#    same way BOSL2 does: a :func:`~bosl2.drawing.turtle` outline revolved with rotate_extrude. The
#    threads use this package's :meth:`~bosl2.threading.Threading.thread_helix`, with the two thread
#    breaks cut by the same zrot_copies-placed prismoids as BOSL2.
#
#    Approximations (this port's threading/cyl lack a few BOSL2 features): the thread lead-in
#    ``taper`` is not applied, cap threads are built without the ``internal=`` flank flip, and the
#    ``knurled``/``ribbed`` cap surface textures fall back to a plain wall (VNF texturing is not in
#    this port). The named-anchor system is not reproduced; geometry is anchored bottom-on-origin.
#    Not ported (follow-ups): generic_bottle_neck/cap, the bottle adapters, and the SPI (sp_) threads.
#
# FileSummary: PCO-1810 / PCO-1881 bottle necks and caps.
# FileGroup: BOSL2

from __future__ import annotations

import math
from dataclasses import dataclass

from pythonscad import polygon as _opolygon, rotate_extrude as _orotate_extrude

from bosl2._helpers import union
from bosl2.constants import BOTTOM, RIGHT
from bosl2.distributors import zrot_copies
from bosl2.drawing import turtle
from bosl2.shapes3d import Bosl2Solid, cyl, prismoid
from bosl2.threading import Threading

__all__ = ["BottleCaps", "BottleThreadSpec"]




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
    tamper_ring_r: float | None = None    # PCO-1810 tamper-ring corner radius
    tamper_ring_ang: float | None = None  # PCO-1881 tamper-ring flank angle
    tamper_divot_r: float | None = None   # PCO-1881 tamper divot radius


# PCO-1810 and PCO-1881 neck/cap dimensions (mm), transcribed from bottlecaps.scad.
_PCO1810 = BottleThreadSpec(
    inner_d=21.74, neck_d=26.19, neck_h=5.00, support_d=33.00, support_width=1.45,
    support_rad=0.40, support_h=21.00, support_ang=16, tamper_ring_d=27.97,
    tamper_ring_width=0.50, tamper_base_d=25.71, tamper_base_h=14.10,
    threadbase_d=24.51, thread_pitch=3.18, flank_angle=20, thread_od=27.43, lip_d=25.07,
    lip_h=1.70, lip_leadin_r=0.20, lip_recess_d=24.94, lip_recess_h=1.00, lip_roundover_r=0.58,
    neck_turns=810, cap_id=28.58, cap_tamper_ring_h=14.10, cap_thread_od=28.58,
    cap_thread_pitch=3.18, cap_flank_angle=20, cap_thread_depth=1.6, cap_turns=810,
    tamper_ring_r=1.60,
)
_PCO1881 = BottleThreadSpec(
    inner_d=21.74, neck_d=26.19, neck_h=5.00, support_d=33.00, support_width=0.58,
    support_rad=0.30, support_h=17.00, support_ang=15, tamper_ring_d=28.00,
    tamper_ring_width=0.30, tamper_base_d=25.71, tamper_base_h=11.20,
    threadbase_d=24.20, thread_pitch=2.70, flank_angle=15, thread_od=27.4,
    lip_d=25.07, lip_h=1.70, lip_leadin_r=0.30, lip_recess_d=24.94, lip_recess_h=1.00,
    lip_roundover_r=0.58, neck_turns=650, cap_id=28.58, cap_tamper_ring_h=11.20,
    cap_thread_od=25.5, cap_thread_pitch=2.70, cap_flank_angle=15, cap_thread_depth=1.6,
    cap_turns=650, tamper_ring_ang=45, tamper_divot_r=1.08,
)


def _turtle_start(x, y=0.0):
    """Full turtle state starting at (x, y) heading +X (this port's turtle needs full state)."""
    return [[[float(x), float(y)]], [1.0, 0.0], 90.0, 0.0]


def _pco1810_profile(d: "BottleThreadSpec"):
    h = d.support_h + d.neck_h
    return turtle([
        "untilx", d.neck_d / 2, "left", 90, "move", d.neck_h - 1, "arcright", 1, 90,
        "untilx", d.support_d / 2 - d.support_rad, "arcleft", d.support_rad, 90,
        "move", d.support_width, "arcleft", d.support_rad, 90 - d.support_ang,
        "untilx", d.tamper_base_d / 2, "right", 90 - d.support_ang,
        "untily", h - d.tamper_base_h, "right", 90, "untilx", d.tamper_ring_d / 2, "left", 90,
        "move", d.tamper_ring_width, "arcleft", d.tamper_ring_r, 90,
        "untilx", d.threadbase_d / 2, "right", 90, "untily", h - d.lip_h - d.lip_leadin_r,
        "arcright", d.lip_leadin_r, 90, "untilx", d.lip_d / 2, "left", 90,
        "untily", h - d.lip_recess_h, "left", 90, "untilx", d.lip_recess_d / 2, "right", 90,
        "untily", h - d.lip_roundover_r, "arcleft", d.lip_roundover_r, 90,
        "untilx", d.inner_d / 2,
    ], state=_turtle_start(d.inner_d / 2))


def _pco1881_profile(d: "BottleThreadSpec"):
    h = d.support_h + d.neck_h
    return turtle([
        "untilx", d.neck_d / 2, "left", 90, "move", d.neck_h - 1, "arcright", 1, 90,
        "untilx", d.support_d / 2 - d.support_rad, "arcleft", d.support_rad, 90,
        "move", d.support_width, "arcleft", d.support_rad, 90 - d.support_ang,
        "untilx", d.tamper_base_d / 2, "arcright", d.tamper_divot_r, 180 - d.support_ang * 2,
        "left", 90 - d.support_ang, "untily", h - d.tamper_base_h, "right", 90,
        "untilx", d.tamper_ring_d / 2, "left", 90, "move", d.tamper_ring_width,
        "left", d.tamper_ring_ang, "untilx", d.threadbase_d / 2, "right", d.tamper_ring_ang,
        "untily", h - d.lip_h - d.lip_leadin_r, "arcright", d.lip_leadin_r, 90,
        "untilx", d.lip_d / 2, "left", 90, "untily", h - d.lip_recess_h, "left", 90,
        "untilx", d.lip_recess_d / 2, "right", 90, "untily", h - d.lip_roundover_r,
        "arcleft", d.lip_roundover_r, 90, "untilx", d.inner_d / 2,
    ], state=_turtle_start(d.inner_d / 2))


def _neck_thread(d: "BottleThreadSpec"):
    """The neck's external thread ridge with its two thread breaks (BOSL2 thread_helix + prismoids).

    The lead-in ``taper`` BOSL2 applies is not reproduced (this port's thread_helix has no taper).
    """
    thread_h = (d.thread_od - d.threadbase_d) / 2
    turns = d.neck_turns / 360
    thread = Threading.thread_helix(d=d.threadbase_d - 0.1, pitch=d.thread_pitch,
                                    thread_depth=thread_h + 0.1, flank_angle=d.flank_angle,
                                    turns=turns)
    thread = thread.down(turns * d.thread_pitch / 2)   # BOSL2 anchor=TOP: top at z=0
    top = 1.82 + 2 * math.sin(math.radians(29)) * thread_h
    cuts = []
    for m_out in zrot_copies(rots=[90, 270]):
        for m_in in zrot_copies(rots=[-28, 28], r=d.threadbase_d / 2):
            block = prismoid([20, 1.82], [20, top], h=thread_h + 0.1, anchor=BOTTOM, orient=RIGHT)
            cuts.append(block.multmatrix((m_out @ m_in).tolist()))
    return thread - union(cuts)


def _build_neck(d: "BottleThreadSpec", profile, bottom_half: bool):
    h = d.support_h + d.neck_h
    body = Bosl2Solid(_orotate_extrude(_opolygon([[float(x), float(y)] for x, y in profile])),
                      size=[d.support_d, d.support_d, h])
    thread = _neck_thread(d)
    if bottom_half:
        thread = thread.bottom_half()
    thread = thread.up(h - d.lip_h)
    return Bosl2Solid((body | thread).shape, size=[d.support_d, d.support_d, h])


def _build_cap(d: "BottleThreadSpec", wall: float, texture: str):
    w = d.cap_id + 2 * wall
    h = d.cap_tamper_ring_h + wall
    outer = cyl(d=w, l=h, anchor=BOTTOM)
    bore = cyl(d=d.cap_id, h=h, anchor=BOTTOM).up(wall)
    shell = outer - bore
    turns = d.cap_turns / 360
    H = turns * d.cap_thread_pitch
    # internal thread (this port's thread_helix has no internal= flank flip -- approximate).
    thread = Threading.thread_helix(d=d.cap_thread_od - d.cap_thread_depth * 2, pitch=d.cap_thread_pitch,
                                    thread_depth=d.cap_thread_depth, flank_angle=d.cap_flank_angle,
                                    turns=turns)
    thread = thread.up(H / 2 + wall + 2)     # BOSL2 anchor=BOTTOM, then up(wall+2)
    cap = (shell | thread).rotate([0, 0, 45])
    return Bosl2Solid(cap.shape, size=[w, w, h])


class BottleCaps:
    """Standard soda-bottle necks and caps (BOSL2 bottlecaps.scad, PCO-1810 & PCO-1881).

    Each ``*_neck`` / ``*_cap`` returns a :class:`~bosl2.shapes3d.Bosl2Solid` anchored with its
    bottom on the XY plane. See the module docstring for the geometry approximations relative to
    BOSL2 (thread taper, internal-thread flank, and cap surface textures are not reproduced).
    """

    @staticmethod
    def pco1810_neck(wall: float = 2) -> Bosl2Solid:
        """A PCO-1810 threaded beverage-bottle neck (BOSL2 pco1810_neck())."""
        return _build_neck(_PCO1810, _pco1810_profile(_PCO1810), bottom_half=True)

    @staticmethod
    def pco1810_cap(wall: float = 2, texture: str = "none") -> Bosl2Solid:
        """A cap for a PCO-1810 bottle (BOSL2 pco1810_cap()). ``texture`` other than ``"none"`` falls
        back to a plain wall (surface texturing is not in this port)."""
        return _build_cap(_PCO1810, wall, texture)

    @staticmethod
    def pco1881_neck(wall: float = 2) -> Bosl2Solid:
        """A PCO-1881 threaded beverage-bottle neck (BOSL2 pco1881_neck())."""
        return _build_neck(_PCO1881, _pco1881_profile(_PCO1881), bottom_half=False)

    @staticmethod
    def pco1881_cap(wall: float = 2, texture: str = "none") -> Bosl2Solid:
        """A cap for a PCO-1881 bottle (BOSL2 pco1881_cap()). ``texture`` other than ``"none"`` falls
        back to a plain wall (surface texturing is not in this port)."""
        return _build_cap(_PCO1881, wall, texture)

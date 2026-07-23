# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/joiners.py
#    Pure-Python port of the core joiners from BOSL2's joiners.scad -- shapes for connecting two
#    separately-printed parts. :meth:`Joiners.dovetail` is the flagship: a (optionally tapered)
#    dovetail joint you attach as a male tenon or difference out as a female socket. A functional
#    :meth:`Joiners.snap_pin` and its :meth:`Joiners.snap_pin_socket` give a press-and-click pin.
#
#    The snap pin is a clean functional build (a slotted, barbed shaft); BOSL2's named-size table and
#    the hirth/rabbit-clip couplings are not ported.
#
# FileSummary: Dovetail joints and snap-pin connectors.
# FileGroup: BOSL2

from __future__ import annotations

import math

from pythonscad import hull as _ohull

from bosl2.shapes3d import Bosl2Solid, cuboid, cyl, prismoid, sphere

__all__ = ["Joiners"]


class Joiners:
    """Dovetail joints and snap-pin connectors (BOSL2 joiners.scad)."""

    @staticmethod
    def dovetail(gender: str = "male", width: float = 15, height: float = 8, slide: float = 30,
                 angle: float | None = None, slope: float = 6, taper: float = 0,
                 back_width: float | None = None, slop: float = 0.0, _fn: int | None = None) -> Bosl2Solid:
        """A dovetail joint that slides along Y and flares upward in X (BOSL2 dovetail()).

        The male form is a tenon you attach to a part; the female form is the same shape enlarged by
        *slop* for you to difference out as the mating socket. A dovetail resists pulling apart across
        the flare. *slope* is the flare (rise/run per side; ``angle`` sets it as ``1/tan(angle)``).
        Give *taper* (degrees) or *back_width* to taper it along its length so it wedges home.

        Examples:
            A male dovetail beside its female socket:

            .. pythonscad-example::

                from bosl2.joiners import Joiners
                (Joiners.dovetail("male", width=15, height=8, slide=30)
                 | Joiners.dovetail("female", width=15, height=8, slide=30).right(24)).show()
        """
        if angle is not None:
            slope = 1 / math.tan(math.radians(angle))
        hslop = slop if gender == "female" else 0.0
        w = width + 2 * hslop
        h = height + hslop
        flare = 2 * h / slope   # total added width at the top

        if taper or back_width is not None:
            if back_width is None:
                back_width = width - 2 * slide * math.tan(math.radians(taper))
            wb = back_width + 2 * hslop
            front = prismoid([w, 0.02], [w + flare, 0.02], h=h).back(slide / 2)
            back = prismoid([wb, 0.02], [wb + flare, 0.02], h=h).forward(slide / 2)
            body = Bosl2Solid(_ohull(front.shape, back.shape))
        else:
            body = prismoid([w, slide], [w + flare, slide], h=h)

        return Bosl2Solid(body.shape, size=[w + flare, slide, h])

    @staticmethod
    def snap_pin(diameter: float = 5, length: float = 12, nub_depth: float = 0.6, snap: float = 2.2,
                 clearance: float = 0.2, slot: float = 1.2, _fn: int | None = None) -> Bosl2Solid:
        """A press-and-click snap pin: a slotted shaft with a barbed head (BOSL2 snap_pin()).

        Push it head-first through a hole (or a :meth:`snap_pin_socket`); the slot lets the barb
        compress and spring back to lock. *nub_depth* is the barb overhang, *snap* its height, and
        *slot* the width of the flex gap.

        Examples:
            A snap pin:

            .. pythonscad-example::

                from bosl2.joiners import Joiners
                Joiners.snap_pin().show()
        """
        shaft = cyl(h=length, d=diameter, _fn=_fn)
        # barb: a downward-facing ratchet lip at the tip (wide at its base, tapering to the shaft).
        barb = cyl(h=snap, d1=diameter + 2 * nub_depth, d2=diameter, _fn=_fn).up(length / 2 - snap / 2)
        tip = sphere(d=diameter, _fn=_fn).up(length / 2)
        pin = shaft | barb | tip
        pin = pin - cuboid([diameter + 2 * nub_depth + 1, slot, length + snap])   # flex slot
        return Bosl2Solid(pin.shape, size=[diameter + 2 * nub_depth, diameter, length + diameter / 2])

    @staticmethod
    def snap_pin_socket(diameter: float = 5, length: float = 12, nub_depth: float = 0.6,
                        snap: float = 2.2, clearance: float = 0.2, _fn: int | None = None) -> Bosl2Solid:
        """The mating socket mask for a :meth:`snap_pin` -- difference it out of a part (BOSL2 snap_pin_socket()).

        A clearance bore with a relief groove that the pin's barb clicks into.
        """
        bore = cyl(h=length + 1, d=diameter + 2 * clearance, _fn=_fn)
        relief = cyl(h=snap + clearance, d=diameter + 2 * nub_depth + 2 * clearance, _fn=_fn).up(length / 2 - snap / 2)
        return Bosl2Solid((bore | relief).shape,
                          size=[diameter + 2 * nub_depth + 2 * clearance, diameter + 2 * clearance, length])

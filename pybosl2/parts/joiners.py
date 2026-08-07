# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/parts/joiners.py
#    Pure-Python port of the core joiners from BOSL2's joiners.scad -- shapes for connecting two
#    separately-printed parts. :class:`Dovetail` is the flagship: a (optionally tapered)
#    dovetail joint you attach as a male tenon or difference out as a female socket. A functional
#    :class:`SnapPin` and its :class:`SnapPinSocket` give a press-and-click pin.
#
#    The snap pin is a clean functional build (a slotted, barbed shaft); BOSL2's named-size table and
#    the hirth/rabbit-clip couplings are not ported.
#
# FileSummary: Dovetail joints and snap-pin connectors.
# DocCategory: Parts library
# FileGroup: BOSL2

"""Dovetail joints and snap-pin connectors."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pybosl2._native import native
from pybosl2.parts.enums import Gender
from pybosl2.shapes3d import Bosl2Solid, cuboid, cyl, prismoid, sphere

if TYPE_CHECKING:  # real stub-typed imports for the checker (identical to pre-lazy)
    from pythonscad import hull as _ohull
else:
    _ohull = native("hull")

__all__ = ["Dovetail", "SnapPin", "SnapPinSocket"]


class Dovetail:
    """A dovetail joint that slides along Y and flares upward in X.

    The male form is a tenon you attach to a part; the female form is the same
    shape enlarged by *slop* for you to difference out as the mating socket.
    *slope* is the flare (rise/run per side; ``angle`` sets it as ``1/tan(angle)``).
    Give *taper* (degrees) or *back_width* to taper it along its length.

    Examples:
        A male dovetail beside its female socket:

        .. pythonscad-example::

            from pybosl2.parts.enums import Gender
            from pybosl2.parts.joiners import Dovetail
            (Dovetail(Gender.MALE, width=15, height=8, slide=30).shape()
             | Dovetail(Gender.FEMALE, width=15, height=8, slide=30).shape().right(24)).show()

    """

    def __init__(
        self,
        gender: Gender = Gender.MALE,
        width: float = 15,
        height: float = 8,
        slide: float = 30,
        angle: float | None = None,
        slope: float = 6,
        taper: float = 0,
        back_width: float | None = None,
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a dovetail joint tenon (male) or socket (female)."""
        if angle is not None:
            slope = 1 / math.tan(math.radians(angle))
        hslop = slop if gender == Gender.FEMALE else 0.0
        w = width + 2 * hslop
        h = height + hslop
        flare = 2 * h / slope

        if taper or back_width is not None:
            if back_width is None:
                back_width = width - 2 * slide * math.tan(math.radians(taper))
            wb = back_width + 2 * hslop
            front = prismoid([w, 0.02], [w + flare, 0.02], height=h, fn=fn, fa=fa, fs=fs).back(slide / 2)
            back = prismoid([wb, 0.02], [wb + flare, 0.02], height=h, fn=fn, fa=fa, fs=fs).forward(slide / 2)
            body = Bosl2Solid(_ohull(front.shape, back.shape))
        else:
            body = prismoid([w, slide], [w + flare, slide], height=h, fn=fn, fa=fa, fs=fs)

        self._solid: Bosl2Solid = Bosl2Solid(body.shape, size=[w + flare, slide, h])
        self._gender: Gender = gender
        self._width: float = width
        self._height: float = height
        self._slide: float = slide

    @property
    def gender(self) -> Gender:
        """Male or female."""
        return self._gender

    @property
    def width(self) -> float:
        """Base width in mm."""
        return self._width

    @property
    def height(self) -> float:
        """Joint height in mm."""
        return self._height

    @property
    def slide(self) -> float:
        """Slide length in mm."""
        return self._slide

    def shape(self) -> Bosl2Solid:
        """Return the dovetail geometry."""
        return self._solid

    def show(self) -> None:
        """Display the dovetail in the viewer."""
        self._solid.show()


class SnapPin:
    """A press-and-click snap pin: a slotted shaft with a barbed head.

    Push it head-first through a hole; the slot lets the barb compress and
    spring back to lock.  *nub_depth* is the barb overhang, *snap* its height,
    and *slot* the width of the flex gap.

    Examples:
        A snap pin:

        .. pythonscad-example::

            from pybosl2.parts.joiners import SnapPin
            SnapPin().show()

    """

    def __init__(
        self,
        diameter: float = 5,
        length: float = 12,
        nub_depth: float = 0.6,
        snap: float = 2.2,
        clearance: float = 0.2,
        slot: float = 1.2,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a snap pin."""
        _ = clearance
        shaft = cyl(height=length, diameter=diameter, fn=fn, fa=fa, fs=fs)
        barb = cyl(
            height=snap,
            diameter1=diameter + 2 * nub_depth,
            diameter2=diameter,
            fn=fn,
            fa=fa,
            fs=fs,
        ).up(length / 2 - snap / 2)
        tip = sphere(diameter=diameter, fn=fn, fa=fa, fs=fs).up(length / 2)
        pin = shaft | barb | tip
        pin = pin - cuboid([diameter + 2 * nub_depth + 1, slot, length + snap], fn=fn, fa=fa, fs=fs)
        self._solid: Bosl2Solid = Bosl2Solid(
            pin.shape,
            size=[diameter + 2 * nub_depth, diameter, length + diameter / 2],
        )
        self._diameter: float = diameter
        self._length: float = length

    @property
    def diameter(self) -> float:
        """Shaft diameter in mm."""
        return self._diameter

    @property
    def length(self) -> float:
        """Shaft length in mm."""
        return self._length

    def shape(self) -> Bosl2Solid:
        """Return the snap pin geometry."""
        return self._solid

    def show(self) -> None:
        """Display the snap pin in the viewer."""
        self._solid.show()


class SnapPinSocket:
    """The mating socket mask for a :class:`SnapPin` — difference it out of a part.

    A clearance bore with a relief groove that the pin's barb clicks into.
    """

    def __init__(
        self,
        diameter: float = 5,
        length: float = 12,
        nub_depth: float = 0.6,
        snap: float = 2.2,
        clearance: float = 0.2,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a snap pin socket mask."""
        bore = cyl(height=length + 1, diameter=diameter + 2 * clearance, fn=fn, fa=fa, fs=fs)
        relief = cyl(
            height=snap + clearance,
            diameter=diameter + 2 * nub_depth + 2 * clearance,
            fn=fn,
            fa=fa,
            fs=fs,
        ).up(length / 2 - snap / 2)
        self._solid: Bosl2Solid = Bosl2Solid(
            (bore | relief).shape,
            size=[diameter + 2 * nub_depth + 2 * clearance, diameter + 2 * clearance, length],
        )
        self._diameter: float = diameter
        self._length: float = length

    @property
    def diameter(self) -> float:
        """Shaft diameter in mm."""
        return self._diameter

    @property
    def length(self) -> float:
        """Shaft length in mm."""
        return self._length

    def shape(self) -> Bosl2Solid:
        """Return the socket geometry."""
        return self._solid

    def show(self) -> None:
        """Display the socket in the viewer."""
        self._solid.show()

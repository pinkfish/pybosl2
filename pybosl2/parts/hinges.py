# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/parts/hinges.py
#    Pure-Python port of the hinges in BOSL2's hinges.scad. The classes provide
#    :class:`LivingHingeMask` (a wedge cut into a flat plate so it folds -- a print-in-place
#    "living" hinge), a functional interlocking :class:`KnuckleHinge` leaf (and
#    :class:`KnuckleHingePair`, the two mating leaves around one pin), and simple
#    :class:`SnapLock` / :class:`SnapSocket` connectors.
#
#    The knuckle hinge is a clean functional build (interlocking knuckles + a pin bore); BOSL2's
#    elaborate screw-pin / teardrop / clip / tag refinements are not reproduced.
#
# FileSummary: Living (folding) hinges, knuckle hinges, and snap connectors.
# DocCategory: Parts library
# FileGroup: BOSL2

"""Living (folding) hinges, knuckle hinges, and snap connectors."""

from __future__ import annotations

import math

from pybosl2._helpers import union
from pybosl2.constants import BOTTOM
from pybosl2.shapes3d import Bosl2Solid, cuboid, cyl, prismoid, sphere

__all__ = [
    "KnuckleHinge",
    "KnuckleHingePair",
    "LivingHingeMask",
    "SnapLock",
    "SnapSocket",
]


class LivingHingeMask:
    """A wedge mask to difference out of a plate to make a print-in-place living hinge.

    Centre it on the bottom of a plate of thickness *thick*; it leaves ``2*layerheight``
    of material as the flexible hinge, and a V-groove wide enough to fold *foldangle* degrees.

    Examples:
        A living hinge cut into a 100x40 plate:

        .. pythonscad-example::

            from pybosl2.parts.hinges import LivingHingeMask
            from pybosl2.solid import cuboid
            (cuboid([100, 40, 3]) - LivingHingeMask(length=100, thick=3, foldangle=60).shape().down(1.5)).show()

    """

    def __init__(
        self,
        length: float,
        thick: float,
        layerheight: float = 0.2,
        foldangle: float = 90,
        hingegap: float | None = None,
        slop: float = 0.0,
    ) -> None:
        """Create a living hinge mask for a plate of the given *thick*ness and *length*."""
        hg = (layerheight if hingegap is None else hingegap) + 2 * slop
        top = hg + 2 * thick / math.tan(math.radians(foldangle / 2))
        self._solid: Bosl2Solid = prismoid([length, hg], [length, top], height=thick, anchor=BOTTOM).up(layerheight * 2)
        self._length: float = length
        self._thick: float = thick

    @property
    def length(self) -> float:
        """Hinge length in mm."""
        return self._length

    @property
    def thick(self) -> float:
        """Plate thickness in mm."""
        return self._thick

    def shape(self) -> Bosl2Solid:
        """Return the hinge mask geometry."""
        return self._solid

    def show(self) -> None:
        """Display the hinge mask in the viewer."""
        self._solid.show()


class KnuckleHinge:
    """One leaf of an interlocking knuckle hinge with a pin bore.

    The hinge pin lies along X at the origin; the flat leaf extends in +Y (outer
    leaf) or -Y (inner leaf).  *segs* is the total knuckle count across both
    leaves — the outer leaf takes the ``ceil(segs/2)`` even knuckles, the inner
    leaf the ``floor(segs/2)`` odd ones.  Pair with :class:`KnuckleHingePair`.
    """

    def __init__(
        self,
        length: float = 40,
        segs: int = 5,
        knuckle_diam: float = 6,
        pin_diam: float = 2,
        arm: float = 20,
        thick: float = 3,
        gap: float = 0.4,
        inner: bool = False,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a single knuckle hinge leaf."""
        assert segs >= 2, "knuckle_hinge(): segs must be >= 2."
        seglen = (length - (segs - 1) * gap) / segs
        parts: list[Bosl2Solid] = []
        for i in range(segs):
            if (i % 2) != (1 if inner else 0):
                continue
            x = -length / 2 + seglen / 2 + i * (seglen + gap)
            parts.append(cyl(height=seglen, diameter=knuckle_diam, fn=fn, fa=fa, fs=fs).rotate([0, 90, 0]).right(x))
        ydir = -1 if inner else 1
        plate_w = arm + knuckle_diam / 2
        parts.append(cuboid([length, plate_w, thick], fn=fn, fa=fa, fs=fs).back(ydir * plate_w / 2))
        leaf = union(parts)
        leaf = leaf - cyl(height=length + 1, diameter=pin_diam, fn=fn, fa=fa, fs=fs).rotate([0, 90, 0])
        self._solid: Bosl2Solid = Bosl2Solid(leaf.shape, size=[length, plate_w + knuckle_diam / 2, knuckle_diam])
        self._length: float = length
        self._arm: float = arm
        self._inner: bool = inner

    @property
    def length(self) -> float:
        """Hinge length in mm."""
        return self._length

    @property
    def arm(self) -> float:
        """Leaf arm length in mm."""
        return self._arm

    @property
    def inner(self) -> bool:
        """True for the inner leaf, False for outer."""
        return self._inner

    def shape(self) -> Bosl2Solid:
        """Return the knuckle hinge leaf geometry."""
        return self._solid

    def show(self) -> None:
        """Display the knuckle hinge leaf in the viewer."""
        self._solid.show()


class KnuckleHingePair:
    """Both leaves of a knuckle hinge, meshed around one pin.

    Set *fold* to rotate the inner leaf about the pin axis.  With *pin*, a pin
    cylinder is included.

    Examples:
        A knuckle hinge folded 90 degrees:

        .. pythonscad-example::

            from pybosl2.parts.hinges import KnuckleHingePair
            KnuckleHingePair(fold=90).show()

    """

    def __init__(
        self,
        length: float = 40,
        segs: int = 5,
        knuckle_diam: float = 6,
        pin_diam: float = 2,
        arm: float = 20,
        thick: float = 3,
        gap: float = 0.4,
        fold: float = 0,
        pin: bool = True,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a pair of meshing knuckle hinge leaves."""
        outer = KnuckleHinge(
            length,
            segs,
            knuckle_diam,
            pin_diam,
            arm,
            thick,
            gap,
            inner=False,
            fn=fn,
            fa=fa,
            fs=fs,
        ).shape()
        inner = KnuckleHinge(
            length,
            segs,
            knuckle_diam,
            pin_diam,
            arm,
            thick,
            gap,
            inner=True,
            fn=fn,
            fa=fa,
            fs=fs,
        ).shape()
        if fold:
            inner = inner.rotate([fold, 0, 0])
        hinge = outer | inner
        if pin:
            hinge = hinge | cyl(height=length - gap, diameter=pin_diam - 0.1, fn=fn, fa=fa, fs=fs).rotate([0, 90, 0])
        self._solid: Bosl2Solid = Bosl2Solid(
            hinge.shape,
            size=[length, 2 * arm + knuckle_diam, knuckle_diam],
        )
        self._length: float = length
        self._fold: float = fold

    @property
    def length(self) -> float:
        """Hinge length in mm."""
        return self._length

    @property
    def fold(self) -> float:
        """Fold angle in degrees."""
        return self._fold

    def shape(self) -> Bosl2Solid:
        """Return the hinge pair geometry."""
        return self._solid

    def show(self) -> None:
        """Display the hinge pair in the viewer."""
        self._solid.show()


class SnapLock:
    """A snap-lock tab (a ridge on a post) that clicks into a :class:`SnapSocket`."""

    def __init__(
        self,
        thick: float = 3,
        snaplen: float = 5,
        snapdiam: float = 5,
        layerheight: float = 0.2,
        foldangle: float = 90,
        hingegap: float | None = None,
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a snap-lock tab."""
        hg = (layerheight if hingegap is None else hingegap) + 2 * slop
        snap_x = (snapdiam / 2 + (thick - 2 * layerheight)) / math.tan(math.radians(foldangle / 2)) + hg / 2
        post = cuboid([snaplen, snapdiam, snapdiam / 2 + thick], fn=fn, fa=fa, fs=fs).up((snapdiam / 2 + thick) / 2)
        ridge = cyl(height=snaplen, diameter=snapdiam, fn=fn, fa=fa, fs=fs).rotate([0, 90, 0]).up(snapdiam / 2 + thick)
        self._solid: Bosl2Solid = Bosl2Solid((post | ridge).back(snap_x).shape, size=[snaplen, snapdiam, 2 * thick])
        self._thick: float = thick

    @property
    def thick(self) -> float:
        """Plate thickness in mm."""
        return self._thick

    def shape(self) -> Bosl2Solid:
        """Return the snap-lock tab geometry."""
        return self._solid

    def show(self) -> None:
        """Display the snap-lock tab in the viewer."""
        self._solid.show()


class SnapSocket:
    """The receiving socket for a :class:`SnapLock` tab."""

    def __init__(
        self,
        thick: float = 3,
        snaplen: float = 5,
        snapdiam: float = 5,
        layerheight: float = 0.2,
        foldangle: float = 90,
        hingegap: float | None = None,
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a snap socket."""
        hg = (layerheight if hingegap is None else hingegap) + 2 * slop
        snap_x = (snapdiam / 2 + (thick - 2 * layerheight)) / math.tan(math.radians(foldangle / 2)) + hg / 2
        post = cuboid([snaplen, snapdiam, snapdiam / 2 + thick], fn=fn, fa=fa, fs=fs).up((snapdiam / 2 + thick) / 2)
        ridge = cyl(height=snaplen, diameter=snapdiam, fn=fn, fa=fa, fs=fs).rotate([0, 90, 0]).up(snapdiam / 2 + thick)
        divot = (
            sphere(diameter=snapdiam * 0.8, fn=fn, fa=fa, fs=fs)
            .scale([0.333, 1, 1])
            .left((snaplen + snapdiam / 12) / 2)
            .up(snapdiam / 2 + thick)
        )
        self._solid: Bosl2Solid = Bosl2Solid(
            ((post | ridge) - divot).forward(snap_x).shape,
            size=[snaplen, snapdiam, 2 * thick],
        )
        self._thick: float = thick

    @property
    def thick(self) -> float:
        """Plate thickness in mm."""
        return self._thick

    def shape(self) -> Bosl2Solid:
        """Return the snap socket geometry."""
        return self._solid

    def show(self) -> None:
        """Display the snap socket in the viewer."""
        self._solid.show()

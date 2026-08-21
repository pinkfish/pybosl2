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
from typing import Any

from pybosl2._backend import csg_part
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
            (cuboid([100, 40, 3]) - LivingHingeMask(length=100, thick=3, foldangle=60).shape.down(1.5)).show()

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
        """Create a living hinge mask for a plate of the given *thick*ness and *length*.

        Args:
            length: Length of the hinge in mm.
            thick: Thickness of the plate in mm.
            layerheight: Layer height in mm. Defaults to 0.2.
            foldangle: Maximum fold angle in degrees. Defaults to 90.
            hingegap: Gap at the hinge point. Defaults to layerheight.
            slop: Extra clearance.

        Returns:
            None.

        """
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

    @property
    @csg_part
    def shape(self) -> Bosl2Solid:
        """Return the hinge mask geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the hinge mask in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()


class KnuckleHinge:
    """One leaf of an interlocking knuckle hinge with a pin bore.

    The hinge pin lies along X at the origin; the flat leaf extends in +Y (outer
    leaf) or -Y (inner leaf).  *segs* is the total knuckle count across both
    leaves — the outer leaf takes the ``ceil(segs/2)`` even knuckles, the inner
    leaf the ``floor(segs/2)`` odd ones.  Pair with :class:`KnuckleHingePair`.

    Examples:
        An outer knuckle hinge leaf:

        .. pythonscad-example::

            from pybosl2.parts.hinges import KnuckleHinge
            KnuckleHinge().show()

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
        """Create a single knuckle hinge leaf.

        Args:
            length: Total hinge length in mm. Defaults to 40.
            segs: Total knuckle count across both leaves. Defaults to 5.
            knuckle_diam: Outer diameter of each knuckle. Defaults to 6.
            pin_diam: Diameter of the pin bore. Defaults to 2.
            arm: Length of the flat leaf arm. Defaults to 20.
            thick: Thickness of the flat leaf. Defaults to 3.
            gap: Gap between knuckles. Defaults to 0.4.
            inner: If True, build the inner leaf; outer otherwise. Defaults to False.
            fn: Number of fragments for rounded geometry.
            fa: Fragment angle for rounded geometry.
            fs: Fragment size for rounded geometry.

        Returns:
            None.

        """
        if not (segs >= 2):
            raise ValueError("knuckle_hinge(): segs must be >= 2.")
        seglen = (length - (segs - 1) * gap) / segs
        mine = 1 if inner else 0

        def knuckle_x(index: int) -> float:
            return -length / 2 + seglen / 2 + index * (seglen + gap)

        parts: list[Bosl2Solid] = []
        for i in range(segs):
            if (i % 2) != mine:
                continue
            parts.append(
                cyl(height=seglen, diameter=knuckle_diam, fn=fn, fa=fa, fs=fs).rotate([0, 90, 0]).right(knuckle_x(i))
            )
        ydir = -1 if inner else 1
        plate_w = arm + knuckle_diam / 2
        parts.append(cuboid([length, plate_w, thick], fn=fn, fa=fa, fs=fs).back(ydir * plate_w / 2))
        leaf = union(parts)
        leaf = leaf - cyl(height=length + 1, diameter=pin_diam, fn=fn, fa=fa, fs=fs).rotate([0, 90, 0])
        # A leaf may only occupy the space around the pin WHERE ITS OWN KNUCKLES ARE.
        #
        # The plate used to span the whole length and reach the axis, so both leaves filled
        # the pin's neighbourhood everywhere: mated leaves shared a solid running the full
        # length of the hinge, and no rotation was possible. Clearing only the other leaf's
        # knuckles is not enough either -- the leftover plate roots still sweep through each
        # other as soon as the hinge folds.
        #
        # So cut the pin's whole neighbourhood (radius + `gap`, the same clearance `gap`
        # already gives axially between neighbouring knuckles) out of the plate, and keep it
        # only across this leaf's own knuckles, which is what joins plate to knuckle. Every
        # x along the hinge then belongs to exactly one leaf, at any fold angle. This is the
        # same invariant the SDF `_sdf.joiners.knuckle_hinge` gets by extruding arm and
        # knuckle together once per segment.
        clearance = cyl(height=length + 2, diameter=knuckle_diam + 2 * gap, fn=fn, fa=fa, fs=fs).rotate([0, 90, 0])
        keep = [
            cuboid([seglen, knuckle_diam + 2 * gap + 2, knuckle_diam + 2 * gap + 2]).right(knuckle_x(i))
            for i in range(segs)
            if (i % 2) == mine
        ]
        if keep:
            clearance = clearance - union(keep)
        leaf = leaf - clearance
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

    @property
    @csg_part
    def shape(self) -> Bosl2Solid:
        """Return the knuckle hinge leaf geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the knuckle hinge leaf in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()


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
        """Create a pair of meshing knuckle hinge leaves.

        Args:
            length: Total hinge length in mm. Defaults to 40.
            segs: Total knuckle count across both leaves. Defaults to 5.
            knuckle_diam: Outer diameter of each knuckle. Defaults to 6.
            pin_diam: Diameter of the pin bore. Defaults to 2.
            arm: Length of the flat leaf arm. Defaults to 20.
            thick: Thickness of the flat leaf. Defaults to 3.
            gap: Gap between knuckles. Defaults to 0.4.
            fold: Angle to rotate the inner leaf. Defaults to 0.
            pin: If True, include a pin cylinder. Defaults to True.
            fn: Number of fragments for rounded geometry.
            fa: Fragment angle for rounded geometry.
            fs: Fragment size for rounded geometry.

        Returns:
            None.

        """
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
        ).shape
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
        ).shape
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

    @property
    @csg_part
    def shape(self) -> Bosl2Solid:
        """Return the hinge pair geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the hinge pair in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()


class SnapLock:
    """A snap-lock tab (a ridge on a post) that clicks into a :class:`SnapSocket`.

    Examples:
        A snap-lock tab:

        .. pythonscad-example::

            from pybosl2.parts.hinges import SnapLock
            SnapLock().show()

    """

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
        """Create a snap-lock tab.

        Args:
            thick: Plate thickness in mm. Defaults to 3.
            snaplen: Snap tab length in mm. Defaults to 5.
            snapdiam: Snap ridge diameter in mm. Defaults to 5.
            layerheight: Layer height in mm. Defaults to 0.2.
            foldangle: Fold angle for the living hinge section. Defaults to 90.
            hingegap: Gap at the hinge point. Defaults to layerheight.
            slop: Extra clearance.
            fn: Number of fragments for rounded geometry.
            fa: Fragment angle for rounded geometry.
            fs: Fragment size for rounded geometry.

        Returns:
            None.

        """
        hg = (layerheight if hingegap is None else hingegap) + 2 * slop
        snap_x = (snapdiam / 2 + (thick - 2 * layerheight)) / math.tan(math.radians(foldangle / 2)) + hg / 2
        post = cuboid([snaplen, snapdiam, snapdiam / 2 + thick], fn=fn, fa=fa, fs=fs).up((snapdiam / 2 + thick) / 2)
        ridge = cyl(height=snaplen, diameter=snapdiam, fn=fn, fa=fa, fs=fs).rotate([0, 90, 0]).up(snapdiam / 2 + thick)
        # Nominal anchor box: the plate the snap is mounted on, so a lock and its socket anchor to
        # the same frame. The snap head stands above it, making bounds() taller.
        self._solid: Bosl2Solid = Bosl2Solid((post | ridge).back(snap_x).shape, size=[snaplen, snapdiam, 2 * thick])
        self._thick: float = thick

    @property
    def thick(self) -> float:
        """Plate thickness in mm."""
        return self._thick

    @property
    @csg_part
    def shape(self) -> Bosl2Solid:
        """Return the snap-lock tab geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the snap-lock tab in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()


class SnapSocket:
    """The receiving socket for a :class:`SnapLock` tab.

    Examples:
        A snap socket:

        .. pythonscad-example::

            from pybosl2.parts.hinges import SnapSocket
            SnapSocket().show()

    """

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
        """Create a snap socket.

        Args:
            thick: Plate thickness in mm. Defaults to 3.
            snaplen: Snap tab length in mm. Defaults to 5.
            snapdiam: Snap ridge diameter in mm. Defaults to 5.
            layerheight: Layer height in mm. Defaults to 0.2.
            foldangle: Fold angle for the living hinge section. Defaults to 90.
            hingegap: Gap at the hinge point. Defaults to layerheight.
            slop: Extra clearance.
            fn: Number of fragments for rounded geometry.
            fa: Fragment angle for rounded geometry.
            fs: Fragment size for rounded geometry.

        Returns:
            None.

        """
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
        # Nominal anchor box: the plate, as SnapLock uses, so the two halves anchor to the same
        # frame. The socket's ridge stands above the plate, so bounds() is taller.
        self._solid: Bosl2Solid = Bosl2Solid(
            ((post | ridge) - divot).forward(snap_x).shape,
            size=[snaplen, snapdiam, 2 * thick],
        )
        self._thick: float = thick

    @property
    def thick(self) -> float:
        """Plate thickness in mm."""
        return self._thick

    @property
    @csg_part
    def shape(self) -> Bosl2Solid:
        """Return the snap socket geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the snap socket in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()

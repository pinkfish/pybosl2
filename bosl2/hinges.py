# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/hinges.py
#    Pure-Python port of the hinges in BOSL2's hinges.scad. The :class:`Hinges` class provides
#    :meth:`~Hinges.living_hinge_mask` (a wedge cut into a flat plate so it folds -- a print-in-place
#    "living" hinge), a functional interlocking :meth:`~Hinges.knuckle_hinge` leaf (and
#    :meth:`~Hinges.knuckle_hinge_pair`, the two mating leaves around one pin), and simple
#    :meth:`~Hinges.snap_lock` / :meth:`~Hinges.snap_socket` connectors.
#
#    The knuckle hinge is a clean functional build (interlocking knuckles + a pin bore); BOSL2's
#    elaborate screw-pin / teardrop / clip / tag refinements are not reproduced.
#
# FileSummary: Living (folding) hinges, knuckle hinges, and snap connectors.
# FileGroup: BOSL2

from __future__ import annotations

import math

from bosl2._helpers import union
from bosl2.constants import BOTTOM
from bosl2.shapes3d import Bosl2Solid, cuboid, cyl, prismoid, sphere

__all__ = ["Hinges"]


class Hinges:
    """Folding/knuckle hinges and snap connectors (BOSL2 hinges.scad)."""

    @staticmethod
    def living_hinge_mask(l: float, thick: float, layerheight: float = 0.2, foldangle: float = 90,
                          hingegap: float | None = None, slop: float = 0.0) -> Bosl2Solid:
        """A wedge mask to difference out of a plate to make a print-in-place living hinge (BOSL2 living_hinge_mask()).

        Centre it on the bottom of a plate of thickness *thick*; it leaves ``2*layerheight`` of
        material as the flexible hinge, and a V-groove wide enough to fold *foldangle* degrees.

        Examples:
            A living hinge cut into a 100x40 plate:

            .. pythonscad-example::

                from bosl2.hinges import Hinges
                (s3.cuboid([100, 40, 3]) - Hinges.living_hinge_mask(l=100, thick=3, foldangle=60).down(1.5)).show()
        """
        hingegap = (layerheight if hingegap is None else hingegap) + 2 * slop
        top = hingegap + 2 * thick / math.tan(math.radians(foldangle / 2))
        return prismoid([l, hingegap], [l, top], h=thick, anchor=BOTTOM).up(layerheight * 2)

    @staticmethod
    def knuckle_hinge(length: float = 40, segs: int = 5, knuckle_diam: float = 6, pin_diam: float = 2,
                      arm: float = 20, thick: float = 3, gap: float = 0.4, inner: bool = False,
                      _fn: int | None = None) -> Bosl2Solid:
        """One leaf of an interlocking knuckle (butt) hinge, with a pin bore (BOSL2 knuckle_hinge()).

        The hinge pin lies along X at the origin; the flat leaf extends in +Y (outer leaf) or -Y
        (inner leaf). *segs* is the total knuckle count across both leaves -- the outer leaf takes
        the ``ceil(segs/2)`` even knuckles, the inner leaf the ``floor(segs/2)`` odd ones, so the
        two mesh. Pair with :meth:`knuckle_hinge_pair`.
        """
        assert segs >= 2, "knuckle_hinge(): segs must be >= 2."
        seglen = (length - (segs - 1) * gap) / segs
        parts = []
        for i in range(segs):
            if (i % 2) != (1 if inner else 0):
                continue
            x = -length / 2 + seglen / 2 + i * (seglen + gap)
            parts.append(cyl(h=seglen, d=knuckle_diam, _fn=_fn).rotate([0, 90, 0]).right(x))
        # the flat leaf plate, merging into the lower part of the knuckle line
        ydir = -1 if inner else 1
        plate_w = arm + knuckle_diam / 2
        parts.append(cuboid([length, plate_w, thick]).back(ydir * plate_w / 2))
        leaf = union(parts)
        leaf = leaf - cyl(h=length + 1, d=pin_diam, _fn=_fn).rotate([0, 90, 0])   # pin bore
        return Bosl2Solid(leaf.shape, size=[length, plate_w + knuckle_diam / 2, knuckle_diam])

    @staticmethod
    def knuckle_hinge_pair(length: float = 40, segs: int = 5, knuckle_diam: float = 6,
                           pin_diam: float = 2, arm: float = 20, thick: float = 3, gap: float = 0.4,
                           fold: float = 0, pin: bool = True, _fn: int | None = None) -> Bosl2Solid:
        """Both leaves of a knuckle hinge, meshed around one pin (a full, laid-flat or *fold*-degree hinge).

        Set *fold* to rotate the inner leaf about the pin axis. With *pin*, a pin cylinder is included.

        Examples:
            A knuckle hinge folded 90 degrees:

            .. pythonscad-example::

                from bosl2.hinges import Hinges
                Hinges.knuckle_hinge_pair(fold=90).show()
        """
        outer = Hinges.knuckle_hinge(length, segs, knuckle_diam, pin_diam, arm, thick, gap,
                                     inner=False, _fn=_fn)
        inner = Hinges.knuckle_hinge(length, segs, knuckle_diam, pin_diam, arm, thick, gap,
                                     inner=True, _fn=_fn)
        if fold:
            inner = inner.rotate([fold, 0, 0])   # rotate the inner leaf about the pin (X) axis
        hinge = outer | inner
        if pin:
            hinge = hinge | cyl(h=length - gap, d=pin_diam - 0.1, _fn=_fn).rotate([0, 90, 0])
        return Bosl2Solid(hinge.shape, size=[length, 2 * arm + knuckle_diam, knuckle_diam])

    @staticmethod
    def snap_lock(thick: float = 3, snaplen: float = 5, snapdiam: float = 5, layerheight: float = 0.2,
                  foldangle: float = 90, hingegap: float | None = None, slop: float = 0.0,
                  _fn: int | None = None) -> Bosl2Solid:
        """A snap-lock tab (a ridge on a post) that clicks into a :meth:`snap_socket` (BOSL2 snap_lock())."""
        hingegap = (layerheight if hingegap is None else hingegap) + 2 * slop
        snap_x = (snapdiam / 2 + (thick - 2 * layerheight)) / math.tan(math.radians(foldangle / 2)) + hingegap / 2
        post = cuboid([snaplen, snapdiam, snapdiam / 2 + thick]).up((snapdiam / 2 + thick) / 2)
        ridge = cyl(h=snaplen, d=snapdiam, _fn=_fn).rotate([0, 90, 0]).up(snapdiam / 2 + thick)
        return Bosl2Solid((post | ridge).back(snap_x).shape, size=[snaplen, snapdiam, 2 * thick])

    @staticmethod
    def snap_socket(thick: float = 3, snaplen: float = 5, snapdiam: float = 5, layerheight: float = 0.2,
                    foldangle: float = 90, hingegap: float | None = None, slop: float = 0.0,
                    _fn: int | None = None) -> Bosl2Solid:
        """The receiving socket for a :meth:`snap_lock` tab (BOSL2 snap_socket())."""
        hingegap = (layerheight if hingegap is None else hingegap) + 2 * slop
        snap_x = (snapdiam / 2 + (thick - 2 * layerheight)) / math.tan(math.radians(foldangle / 2)) + hingegap / 2
        post = cuboid([snaplen, snapdiam, snapdiam / 2 + thick]).up((snapdiam / 2 + thick) / 2)
        ridge = cyl(h=snaplen, d=snapdiam, _fn=_fn).rotate([0, 90, 0]).up(snapdiam / 2 + thick)
        divot = sphere(d=snapdiam * 0.8, _fn=_fn).scale([0.333, 1, 1]).left((snaplen + snapdiam / 12) / 2).up(snapdiam / 2 + thick)
        return Bosl2Solid(((post | ridge) - divot).forward(snap_x).shape, size=[snaplen, snapdiam, 2 * thick])

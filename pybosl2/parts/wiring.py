# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/parts/wiring.py
#    Pure-Python port of BOSL2's wiring.scad: rendering for routed bundles of wires.
#    :class:`WireBundle` sweeps a hexagonally-packed bundle of round wires along a path whose
#    corners are rounded, colouring each wire from a 17-entry table.
#    :func:`hex_offsets` exposes the optimal hex-packing centre points it uses.
#
# FileSummary: Routed bundles of wires.
# DocCategory: Parts library
# FileGroup: BOSL2

"""Routed bundles of wires."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pybosl2._backend import Solid

import math

from pybosl2._backend import csg_part
from pybosl2._helpers import frag_count as _segs
from pybosl2.color import Color
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.parts._buildable import Buildable
from pybosl2.path3d import Path3D
from pybosl2.shapes3d import Bosl2Solid

__all__ = ["WireBundle", "hex_offsets"]

# The 17 base wire colours, in the same order as BOSL2 wiring.scad.
_WIRE_COLORS = [
    Color([0.2, 0.2, 0.2]),
    Color([1.0, 0.2, 0.2]),
    Color([0.0, 0.8, 0.0]),
    Color([1.0, 1.0, 0.2]),
    Color([0.3, 0.3, 1.0]),
    Color([1.0, 1.0, 1.0]),
    Color([0.7, 0.5, 0.0]),
    Color([0.5, 0.5, 0.5]),
    Color([0.2, 0.9, 0.9]),
    Color([0.8, 0.0, 0.8]),
    Color([0.0, 0.6, 0.6]),
    Color([1.0, 0.7, 0.7]),
    Color([1.0, 0.5, 1.0]),
    Color([0.5, 0.6, 0.0]),
    Color([1.0, 0.7, 0.0]),
    Color([0.7, 1.0, 0.5]),
    Color([0.6, 0.6, 1.0]),
]


def _hex_offset_ring(d: float, lev: int) -> list[list[float]]:
    """Return a hexagonal ring of packing centres spaced *d* apart.

    ``lev=0`` is the single centre point; ``lev>=1`` is a hexagon of ``6*lev`` points.
    """
    if lev == 0:
        return [[0.0, 0.0]]
    r = lev * d  # hexagon circumradius; side length == r
    corners = [(r * math.cos(math.radians(60 * k)), r * math.sin(math.radians(60 * k))) for k in range(6)]
    pts: list[list[float]] = []
    for k in range(6):  # subdivide each edge into lev segments
        x0, y0 = corners[k]
        x1, y1 = corners[(k + 1) % 6]
        for s in range(lev):
            t = s / lev
            pts.append([x0 + (x1 - x0) * t, y0 + (y1 - y0) * t])
    pts.reverse()
    return pts


def _hex_offsets(n: int, d: float) -> list[list[float]]:
    """Centres for the optimal hex packing of at least *n* circles of spacing *d*.

    Fills out the final ring, so the result may hold more than *n* points.
    """
    arr: list[list[float]] = []
    lev = 0
    while len(arr) < n:
        arr += _hex_offset_ring(d, lev)
        lev += 1
    return arr


def hex_offsets(sides: int, diameter: float) -> list[list[float]]:
    """Return the centre points for the optimal hexagonal packing of at least *sides* circles.

    Circles are spaced *diameter* apart.

    Args:
        sides: Minimum number of circles to pack.
        diameter: Centre-to-centre spacing between circles.

    Returns:
        A list of ``[x, y]`` centre offsets.

    """
    return _hex_offsets(sides, diameter)


class WireBundle(Buildable):
    """A bundle of round wires routed along a path with rounded corners.

    The wires are hex-packed in the bundle cross-section and each is coloured
    from the 17-entry table (re-used, offset by *wirenum*, if there are more
    than 17).  *wirediam* is each wire's diameter; *corner_steps* sets how
    finely the rounded corners are faceted.

    Examples:
        A 13-wire bundle routed around three corners:

        .. pythonscad-example::

            from pybosl2.parts.wiring import WireBundle
            WireBundle([[50, 0, -50], [50, 50, -50], [0, 50, -50],
                        [0, 0, -50], [0, 0, 0]], wires=13, rounding=10).show()

    """

    def __init__(
        self,
        path: list[list[float]],
        wires: int,
        wirediam: float = 2,
        rounding: float = 10,
        wirenum: int = 0,
        corner_steps: int = 15,
    ) -> None:
        """Create a wire bundle routed along *path*.

        Args:
            path: A list of 3-D points defining the bundle route.
            wires: Number of wires in the bundle.
            wirediam: Diameter of each wire in mm.
            rounding: Radius for rounding path corners.
            wirenum: Starting index into the colour table for offset colouring.
            corner_steps: Number of facets per rounded corner.

        Returns:
            None.

        Raises:
            ValueError: If *wires* is less than 1.

        """
        if wires < 1:
            raise Bosl2ValueError("wire_bundle() needs at least one wire.")
        self._wires: int = wires
        self._wirediam: float = wirediam
        # The spec above is all a caller needs to *measure* this part; the geometry
        # below is deferred to `shape` (SPEC C-14, PLAN O-2).
        self._args = (
            path,
            wires,
            wirediam,
            rounding,
            wirenum,
            corner_steps,
        )
        self._solid: "Bosl2Solid | None" = None

    def _build(self) -> "Bosl2Solid":
        """Build the geometry. Called once, on the first access to `shape`."""
        (
            path,
            wires,
            wirediam,
            rounding,
            wirenum,
            corner_steps,
        ) = self._args

        sides = max(_segs(wirediam / 2), 8)
        offsets = _hex_offsets(wires, wirediam)
        rounded_path = Path3D(path, closed=False).round_corners(radius=rounding, fn=(corner_steps + 1) * 4)
        radius = wirediam / 2
        profile = [
            [radius * math.cos(2 * math.pi * k / sides), radius * math.sin(2 * math.pi * k / sides)]
            for k in range(sides)
        ]

        bundle: "Solid | None" = None
        for i in range(wires):
            ox, oy = offsets[i]
            prof = [[x + ox, y + oy] for x, y in profile]
            wire = rounded_path.path_sweep(prof)
            wire = wire.color(_WIRE_COLORS[(i + wirenum) % len(_WIRE_COLORS)])
            bundle = wire if bundle is None else (bundle | wire)
        assert bundle is not None
        return Bosl2Solid(cast("Bosl2Solid", bundle).shape, size=None)

    @property
    def wires(self) -> int:
        """Number of wires in the bundle."""
        return self._wires

    @property
    def wirediam(self) -> float:
        """Wire diameter in mm."""
        return self._wirediam

    @property
    @csg_part(
        "sweeps each wire along the route with path_sweep(), and a swept tube that follows bends "
        "is a non-convex mesh with no distance-field form"
    )
    def shape(self) -> Bosl2Solid:
        """Return the wire bundle geometry."""
        if self._solid is None:
            self._solid = self._build()
        return self._solid

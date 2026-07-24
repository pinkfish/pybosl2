# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/wiring.py
#    Pure-Python port of BOSL2's wiring.scad: rendering for routed bundles of wires.
#    :meth:`Wiring.wire_bundle` sweeps a hexagonally-packed bundle of round wires along a path whose
#    corners are rounded, colouring each wire from a 17-entry table.
#    :meth:`~Wiring.hex_offsets` exposes the optimal hex-packing centre points it uses.
#
# FileSummary: Routed bundles of wires.
# FileGroup: BOSL2

from __future__ import annotations

import math

from bosl2.rounding import round_corners
from bosl2.shapes3d import Bosl2Solid
from bosl2.skin import path_sweep

__all__ = ["Wiring"]

# The 17 base wire colours, in the same order as BOSL2 wiring.scad.
_WIRE_COLORS = [
    [0.2, 0.2, 0.2],
    [1.0, 0.2, 0.2],
    [0.0, 0.8, 0.0],
    [1.0, 1.0, 0.2],
    [0.3, 0.3, 1.0],
    [1.0, 1.0, 1.0],
    [0.7, 0.5, 0.0],
    [0.5, 0.5, 0.5],
    [0.2, 0.9, 0.9],
    [0.8, 0.0, 0.8],
    [0.0, 0.6, 0.6],
    [1.0, 0.7, 0.7],
    [1.0, 0.5, 1.0],
    [0.5, 0.6, 0.0],
    [1.0, 0.7, 0.0],
    [0.7, 1.0, 0.5],
    [0.6, 0.6, 1.0],
]


def _segs(r):
    """OpenSCAD segs(r) with the default $fa=12, $fs=2."""
    return max(5, math.ceil(min(360 / 12, 2 * math.pi * r / 2)))


def _hex_offset_ring(d, lev):
    """A hexagonal ring of packing centres spaced *d* apart (BOSL2 _hex_offset_ring()).

    ``lev=0`` is the single centre point; ``lev>=1`` is a hexagon of ``6*lev`` points."""
    if lev == 0:
        return [[0.0, 0.0]]
    R = lev * d  # hexagon circumradius; side length == R
    corners = [
        (R * math.cos(math.radians(60 * k)), R * math.sin(math.radians(60 * k)))
        for k in range(6)
    ]
    pts = []
    for k in range(6):  # subdivide each edge into lev segments
        x0, y0 = corners[k]
        x1, y1 = corners[(k + 1) % 6]
        for s in range(lev):
            t = s / lev
            pts.append([x0 + (x1 - x0) * t, y0 + (y1 - y0) * t])
    pts.reverse()
    return pts


def _hex_offsets(n, d):
    """Centres for the optimal hex packing of at least *n* circles of spacing *d* (BOSL2 _hex_offsets()).

    Fills out the final ring, so the result may hold more than *n* points."""
    arr, lev = [], 0
    while len(arr) < n:
        arr += _hex_offset_ring(d, lev)
        lev += 1
    return arr


class Wiring:
    """Routed bundles of wires (BOSL2 wiring.scad)."""

    @staticmethod
    def hex_offsets(sides: int, diameter: float) -> list:
        """The centre points for the optimal hexagonal packing of at least *sides* circles spaced *diameter* apart."""
        return _hex_offsets(sides, diameter)

    @staticmethod
    def wire_bundle(
        path,
        wires: int,
        wirediam: float = 2,
        rounding: float = 10,
        wirenum: int = 0,
        corner_steps: int = 15,
    ) -> Bosl2Solid:
        """A bundle of *wires* round wires that follow *path*, its corners rounded to *rounding* (BOSL2 wire_bundle()).

        The wires are hex-packed in the bundle cross-section and each is coloured from the 17-entry
        table (re-used, offset by *wirenum*, if there are more than 17). *wirediam* is each wire's
        diameter; *corner_steps* sets how finely the rounded corners are faceted.

        Examples:
            A 13-wire bundle routed around three corners:

            .. pythonscad-example::

                from bosl2.wiring import Wiring
                Wiring.wire_bundle([[50, 0, -50], [50, 50, -50], [0, 50, -50],
                                    [0, 0, -50], [0, 0, 0]], wires=13, rounding=10).show()
        """
        if wires < 1:
            raise ValueError("wire_bundle() needs at least one wire.")
        sides = max(_segs(wirediam / 2), 8)
        offsets = _hex_offsets(wires, wirediam)
        rounded_path = round_corners(
            path, radius=rounding, closed=False, _fn=(corner_steps + 1) * 4
        )
        radius = wirediam / 2
        profile = [
            [
                radius * math.cos(2 * math.pi * k / sides),
                radius * math.sin(2 * math.pi * k / sides),
            ]
            for k in range(sides)
        ]

        bundle = None
        for i in range(wires):
            ox, oy = offsets[i]
            prof = [[x + ox, y + oy] for x, y in profile]
            wire = Bosl2Solid(path_sweep(prof, rounded_path).polyhedron())
            wire = wire.color(_WIRE_COLORS[(i + wirenum) % len(_WIRE_COLORS)])
            bundle = wire if bundle is None else (bundle | wire)
        return Bosl2Solid(bundle.shape, size=None)

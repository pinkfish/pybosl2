# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/constants.py
#    Every constant defined in BOSL2's constants.scad, laid out in the same
#    sections as the original .scad file, so the pybosl2/ package doesn't need
#    to borrow anchor/direction vectors from base_bgtk.py.
#
#    The directional vectors (LEFT, RIGHT, FRONT, BACK, BOTTOM/TOP, CENTER,
#    UP/DOWN) are :class:`Vector` instances that match the :class:`Anchor`
#    enum values.  New code should use :class:`~pybosl2._edges_lang.Anchor`
#    directly for type-safe anchor/edge/corner selection.
#
# FileSummary: Constants provided by BOSL2 (BOSL2 constants.scad).
# DocCategory: Foundational
# FileGroup: BOSL2

from pybosl2._edges_lang import Anchor
from pybosl2.points import Vector

# ---------------------------------------------------------------------------
# Section: General Constants
# ---------------------------------------------------------------------------

#: The number of millimeters in an inch.
INCH: float = 25.4

#: Identity transformation matrix for three-dimensional transforms. Equal to `ident(4)`.
IDENT: list[list[float]] = [
    [1, 0, 0, 0],
    [0, 1, 0, 0],
    [0, 0, 1, 0],
    [0, 0, 0, 1],
]

# ---------------------------------------------------------------------------
# Section: Directional Vectors
#   Vectors useful for rotate(), mirror(), and anchor arguments for
#   cuboid(), cyl(), etc.  Each is a :class:`Vector` matching the
#   corresponding :class:`Anchor` enum member.
# ---------------------------------------------------------------------------


#: Left align/anchor the object.
LEFT: Vector = Anchor.LEFT.vector

#: Right align/anchor the object.
RIGHT: Vector = Anchor.RIGHT.vector

#: Front align/anchor the object.
FRONT: Vector = Anchor.FRONT.vector

#: Forward align/anchor the object.
FORWARD: Vector = FRONT

#: Back align/anchor the object.
BACK: Vector = Anchor.BACK.vector

#: Bottom align/anchor the object.
BOTTOM: Vector = Anchor.BOTTOM.vector

#: Down align/anchor the object.
DOWN: Vector = BOTTOM

#: Top align/anchor the object.
TOP: Vector = Anchor.TOP.vector

#: Up align/anchor the object.
UP: Vector = TOP

#: Center align/anchor the object.
CENTER: Vector = Anchor.CENTER.vector

# ---------------------------------------------------------------------------
# Section: Line specifiers
#   Used by geometry functions for specifying whether two points are
#   treated as an unbounded line, a ray with one endpoint, or a segment
#   with two endpoints.
# ---------------------------------------------------------------------------

#: Treat a line as a segment.
SEGMENT: list[bool] = [True, True]

#: Treat a line as a ray, based at the first point.
RAY: list[bool] = [True, False]

#: Treat a line as an unbounded line.
LINE: list[bool] = [False, False]

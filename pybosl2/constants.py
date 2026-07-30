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
# FileSummary: Constants provided by BOSL2 (BOSL2 constants.scad).
# FileGroup: BOSL2

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
#   cuboid(), cyl(), etc.
# ---------------------------------------------------------------------------


#: Left align/anchor the object.
LEFT: Vector = Vector([-1, 0, 0])
#: Right align/anchor the object.
RIGHT: Vector = Vector([1, 0, 0])

#: Front align/anchor the object.
FRONT: Vector = Vector([0, -1, 0])
#: Forward align/anchor the object.
FORWARD: Vector = FRONT

#: Back align/anchor the object.
BACK: Vector = Vector([0, 1, 0])

#: Bottom align/anchor the object.
BOTTOM: Vector = Vector([0, 0, -1])
#: Down align/anchor the object.
DOWN: Vector = BOTTOM

#: Top align/anchor the object.
TOP: Vector = Vector([0, 0, 1])
#: Up align/anchor the object.
UP: Vector = TOP

#: Center align/anchor the object.
CENTER: Vector = Vector([0, 0, 0])

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

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/constants.py
#    Every constant defined in BOSL2's constants.scad, laid out in the same
#    sections as the original .scad file, so the bosl2/ package doesn't need
#    to borrow anchor/direction vectors from base_bgtk.py.
#
# FileSummary: Constants provided by BOSL2 (BOSL2 constants.scad).
# FileGroup: BOSL2

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


class Vec3(list):
    """A 3-element list that supports elementwise +/-/* like a vector.

    Plain Python lists use `+` for concatenation and `*` for repetition, but
    BOSL2-style code combines direction constants with idioms like
    `anchor=TOP+LEFT` expecting elementwise vector addition (`[0,0,1]+[-1,0,0]`
    -> `[-1,0,1]`), not concatenation. Subclassing `list` (rather than using a
    plain tuple or a numpy array) keeps every other list behavior -- indexing,
    iteration, equality with plain lists, and crossing the osuse()/PyOpenSCAD
    FFI boundary -- unchanged. (Duplicated from base_bgtk.py's Vec3 rather than
    imported, since this package is deliberately independent of base_bgtk.py.)
    """

    def __add__(self, other):
        return Vec3(a + b for a, b in zip(self, other))

    def __radd__(self, other):
        return Vec3(a + b for a, b in zip(other, self))

    def __sub__(self, other):
        return Vec3(a - b for a, b in zip(self, other))

    def __rsub__(self, other):
        return Vec3(a - b for a, b in zip(other, self))

    def __neg__(self):
        return Vec3(-a for a in self)

    def __mul__(self, other: float) -> "Vec3":  # type: ignore[override]
        return Vec3(a * other for a in self)

    __rmul__ = __mul__  # type: ignore[assignment]


#: Left align/anchor the object.
LEFT: Vec3 = Vec3([-1, 0, 0])
#: Right align/anchor the object.
RIGHT: Vec3 = Vec3([1, 0, 0])

#: Front align/anchor the object.
FRONT: Vec3 = Vec3([0, -1, 0])
#: Forward align/anchor the object.
FORWARD: Vec3 = FRONT

#: Back align/anchor the object.
BACK: Vec3 = Vec3([0, 1, 0])

#: Bottom align/anchor the object.
BOTTOM: Vec3 = Vec3([0, 0, -1])
#: Down align/anchor the object.
DOWN: Vec3 = BOTTOM

#: Top align/anchor the object.
TOP: Vec3 = Vec3([0, 0, 1])
#: Up align/anchor the object.
UP: Vec3 = TOP

#: Center align/anchor the object.
CENTER: Vec3 = Vec3([0, 0, 0])

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

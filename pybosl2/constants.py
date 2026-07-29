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


class Vector(list[float]):
    """A 2‑ or 3‑element list that supports elementwise arithmetic.

    Inherits from ``list[float]`` so it is a drop‑in for ``[x, y]`` or
    ``[x, y, z]`` lists.  Elementwise ``+``, ``-``, ``*`` replace the
    default list concatenation/repetition.

    ``len() == 2`` means a 2‑D vector (``is_2d`` is ``True``); ``len() == 3``
    is a 3‑D vector.  Use :meth:`to_3d` to add a Z coordinate.

    Directional constants (``UP``, ``DOWN``, ``LEFT``, ``RIGHT``, …) are
    pre‑built ``Vector`` instances.
    """

    @property
    def x(self) -> float:
        return self[0]

    @property
    def y(self) -> float:
        return self[1]

    @property
    def z(self) -> float | None:
        return self[2] if len(self) > 2 else None

    @property
    def is_2d(self) -> bool:
        """``True`` when this is a 2‑D vector (``len() == 2``)."""
        return len(self) == 2

    def to_3d(self, z: float = 0.0) -> "Vector":
        """Return a 3‑D copy with the given *z*.

        For a 2‑D vector this appends *z*; for a 3‑D vector this returns
        a copy with *z* replaced (unless *z* already matches).
        """
        if len(self) == 2:
            return Vector([self[0], self[1], z])
        return Vector([self[0], self[1], z])

    def __add__(self, other: list[float]) -> "Vector":  # type: ignore
        return Vector(a + b for a, b in zip(self, other, strict=False))

    def __radd__(self, other: list[float]) -> "Vector":
        return Vector(a + b for a, b in zip(other, self, strict=False))

    def __sub__(self, other: list[float]) -> "Vector":
        return Vector(a - b for a, b in zip(self, other, strict=False))

    def __rsub__(self, other: list[float]) -> "Vector":
        return Vector(a - b for a, b in zip(other, self, strict=False))

    def __neg__(self) -> "Vector":
        return Vector(-a for a in self)

    def __mul__(self, other: float) -> "Vector":  # type: ignore[override]
        return Vector(a * other for a in self)

    __rmul__ = __mul__  # type: ignore[assignment]


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

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# Direction-vector constants (TOP/BOTTOM/LEFT/RIGHT/FRONT/BACK/CENTER/...), needed for
# anchor=/edges= defaults throughout pysolidfive. Deliberately a vendored copy of the
# relevant subset of bosl2/constants.py rather than an import from it -- pysolidfive is meant
# to stand alone (no bosl2, and therefore no transitive numpy dependency; see the package
# docstring in pysolidfive/__init__.py), the same way base_bgtk.py and bosl2/constants.py
# each carry their own independent copy of this same Vec3/direction-vector idiom instead of
# sharing one.
#


class Vec3(list):
    """A 3-element list that supports elementwise +/-/* like a vector.

    Plain Python lists use `+` for concatenation and `*` for repetition, but this library's own
    idioms (and BOSL2-style code calling into it) combine direction constants like
    `anchor=TOP+LEFT` expecting elementwise vector addition (`[0,0,1]+[-1,0,0]` -> `[-1,0,1]`),
    not concatenation. Subclassing `list` (rather than a plain tuple or a numpy array) keeps
    every other list behavior -- indexing, iteration, equality with plain lists, and crossing
    the PyOpenSCAD FFI boundary -- unchanged.
    """

    def __add__(self, other: "Vec3 | list[float]") -> "Vec3":
        return Vec3(a + b for a, b in zip(self, other))

    def __radd__(self, other: "Vec3 | list[float]") -> "Vec3":
        return Vec3(a + b for a, b in zip(other, self))

    def __sub__(self, other: "Vec3 | list[float]") -> "Vec3":
        return Vec3(a - b for a, b in zip(self, other))

    def __rsub__(self, other: "Vec3 | list[float]") -> "Vec3":
        return Vec3(a - b for a, b in zip(other, self))

    def __neg__(self) -> "Vec3":
        return Vec3(-a for a in self)

    def __mul__(self, other: float) -> "Vec3":  # type: ignore[override]
        return Vec3(a * other for a in self)

    __rmul__ = __mul__  # type: ignore[assignment]


LEFT: Vec3 = Vec3([-1, 0, 0])
RIGHT: Vec3 = Vec3([1, 0, 0])

FRONT: Vec3 = Vec3([0, -1, 0])
FWD: Vec3 = FRONT
FORWARD: Vec3 = FRONT

BACK: Vec3 = Vec3([0, 1, 0])

BOTTOM: Vec3 = Vec3([0, 0, -1])
BOT: Vec3 = BOTTOM
DOWN: Vec3 = BOTTOM

TOP: Vec3 = Vec3([0, 0, 1])
UP: Vec3 = TOP

CENTER: Vec3 = Vec3([0, 0, 0])
CTR: Vec3 = CENTER
CENTRE: Vec3 = CENTER

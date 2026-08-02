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
#    The directional constants (LEFT, RIGHT, FRONT, BACK, BOTTOM, TOP, CENTER,
#    UP, DOWN, FORWARD) are :class:`~pybosl2._edges_lang.Anchor` enum members.
#    Code that needs the raw vector should use ``.vector`` (e.g.
#    ``TOP.vector``) or ``list(TOP)``.  New code should use
#    ``Anchor.LEFT`` directly for type-safe anchor/edge/corner selection.
#
# FileSummary: Constants provided by BOSL2 (BOSL2 constants.scad).
# DocCategory: Foundational
# FileGroup: BOSL2

from pybosl2._edges_lang import Anchor

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
#   Each constant is an :class:`~pybosl2._edges_lang.Anchor` enum member.
#   Use ``.vector`` to obtain the raw 3-D :class:`~pybosl2.points.Point`.
#   Use ``.vector_2d`` for the 2-D equivalent.
#
#   Deprecated convenience aliases: Use ``Anchor.TOP`` instead of ``TOP``
#   for type-safe anchor selection.
# ---------------------------------------------------------------------------


#: Left face/anchor selector.  Equal to ``Anchor.LEFT``.
LEFT: Anchor = Anchor.LEFT

#: Right face/anchor selector.  Equal to ``Anchor.RIGHT``.
RIGHT: Anchor = Anchor.RIGHT

#: Front face/anchor selector.  Equal to ``Anchor.FRONT``.
FRONT: Anchor = Anchor.FRONT

#: Forward anchor -- alias for ``FRONT``.
FORWARD: Anchor = Anchor.FRONT

#: Back face/anchor selector.  Equal to ``Anchor.BACK``.
BACK: Anchor = Anchor.BACK

#: Bottom face/anchor selector.  Equal to ``Anchor.BOTTOM``.
BOTTOM: Anchor = Anchor.BOTTOM

#: Down anchor -- alias for ``BOTTOM``.
DOWN: Anchor = Anchor.BOTTOM

#: Top face/anchor selector.  Equal to ``Anchor.TOP``.
TOP: Anchor = Anchor.TOP

#: Up anchor -- alias for ``TOP``.
UP: Anchor = Anchor.TOP

#: Center anchor selector.  Equal to ``Anchor.CENTER``.
CENTER: Anchor = Anchor.CENTER

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

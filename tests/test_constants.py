# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/constants.py: the direction constants and their Anchor enum values."""

from pybosl2._edges_lang import Anchor
from pybosl2.constants import (
    BACK,
    BOTTOM,
    CENTER,
    DOWN,
    FORWARD,
    FRONT,
    LEFT,
    RIGHT,
    TOP,
    UP,
)
from pybosl2.points import Point


def test_constant_are_anchors() -> None:
    assert isinstance(LEFT, Anchor)
    assert isinstance(RIGHT, Anchor)
    assert isinstance(FRONT, Anchor)
    assert isinstance(BACK, Anchor)
    assert isinstance(TOP, Anchor)
    assert isinstance(BOTTOM, Anchor)
    assert isinstance(CENTER, Anchor)
    assert LEFT is Anchor.LEFT
    assert RIGHT is Anchor.RIGHT
    assert TOP is Anchor.TOP
    assert BOTTOM is Anchor.BOTTOM
    assert CENTER is Anchor.CENTER


def test_aliases() -> None:
    assert UP is Anchor.TOP
    assert DOWN is Anchor.BOTTOM
    assert UP is TOP
    assert DOWN is BOTTOM
    assert FORWARD is FRONT


def test_vector_property() -> None:
    assert isinstance(LEFT.vector, Point)
    assert list(LEFT.vector) == [-1, 0, 0]
    assert list(RIGHT.vector) == [1, 0, 0]
    assert list(FRONT.vector) == [0, -1, 0]
    assert list(BACK.vector) == [0, 1, 0]
    assert list(TOP.vector) == [0, 0, 1]
    assert list(BOTTOM.vector) == [0, 0, -1]
    assert list(CENTER.vector) == [0, 0, 0]


def test_vector_2d_property() -> None:
    assert list(LEFT.vector_2d) == [-1, 0]
    assert list(RIGHT.vector_2d) == [1, 0]
    assert list(TOP.vector_2d) == [0, 1]
    assert list(BOTTOM.vector_2d) == [0, -1]
    assert list(FRONT.vector_2d) == [0, -1]
    assert list(BACK.vector_2d) == [0, 1]
    assert list(CENTER.vector_2d) == [0, 0]


def test_iterable() -> None:
    assert list(LEFT) == [-1, 0, 0]
    assert list(RIGHT) == [1, 0, 0]
    assert list(CENTER) == [0, 0, 0]
    assert [LEFT[0], LEFT[1], LEFT[2]] == [-1, 0, 0]
    assert len(LEFT) == 3


def test_addition_combines_directions() -> None:
    assert list(TOP + LEFT) == [-1, 0, 1]
    assert list(TOP + FRONT + RIGHT.vector) == [1, -1, 1]


def test_result_is_point() -> None:
    """Arithmetic on anchors stays in Point space, so results keep composing."""
    combined = TOP + LEFT
    assert isinstance(combined, Point)
    assert list(combined) == [-1, 0, 1]

    scaled = TOP.vector * 2
    assert isinstance(scaled, Point)
    assert list(scaled) == [0, 0, 2]
    assert list(scaled + LEFT) == [-1, 0, 2]  # ... and can be combined again


def test_vector_arithmetic() -> None:
    assert list(TOP.vector - BOTTOM.vector) == [0, 0, 2]
    assert list(-TOP.vector) == [0, 0, -1]
    assert list(TOP.vector * 5) == [0, 0, 5]
    assert list(3 * RIGHT.vector) == [3, 0, 0]
    assert TOP.vector == Point(0, 0, 1)
    assert TOP.vector != Point(1, 0, 0)


def test_inch_constant() -> None:
    """INCH equals 25.4."""
    from pybosl2.constants import INCH

    assert INCH == 25.4


def test_ident_is_4x4_identity() -> None:
    """IDENT is a 4x4 identity matrix."""
    from pybosl2.constants import IDENT

    assert len(IDENT) == 4
    for i in range(4):
        assert IDENT[i][i] == 1

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2/regions.py: the Region (outline + holes) list subclass."""

import numpy as np
import pytest

from bosl2.paths import Path
from bosl2.regions import Region

SQUARE = [[0, 0], [80, 0], [80, 60], [0, 60]]
HOLE = [[20, 20], [60, 20], [60, 40], [20, 40]]


def test_single_outline_is_one_path():
    radius = Region(SQUARE)
    assert len(radius) == 1
    assert isinstance(radius[0], Path)


def test_list_of_outlines():
    radius = Region([SQUARE, HOLE])
    assert len(radius) == 2
    assert all(isinstance(p, Path) for p in radius)


def test_with_holes():
    radius = Region.with_holes(SQUARE, HOLE)
    assert len(radius) == 2
    np.testing.assert_allclose(radius.outline, [[float(x), float(y)] for x, y in SQUARE])
    assert len(radius.holes) == 1
    np.testing.assert_allclose(radius.holes[0], [[float(x), float(y)] for x, y in HOLE])


def test_rejects_non_path_items():
    with pytest.raises(TypeError):
        Region([1, 2, 3])


def test_is_a_list():
    assert isinstance(Region(SQUARE), list)


def test_offset_applies_to_every_path():
    radius = Region.with_holes(SQUARE, HOLE).offset(delta=-1)
    assert len(radius) == 2
    assert all(isinstance(p, Path) for p in radius)


def test_translate_moves_all():
    radius = Region.with_holes(SQUARE, HOLE).translate([5, 7])
    np.testing.assert_allclose(radius.outline[0], [5, 7])


def test_bounds():
    b = Region.with_holes(SQUARE, HOLE).bounds()
    np.testing.assert_allclose(b, [[0, 0], [80, 60]])


def test_round_corners_returns_region():
    radius = Region(SQUARE).round_corners(radius=2)
    assert isinstance(radius, Region)


def test_geometry_returns_a_solid():
    # under the mock, polygon() and subtraction return stand-in solids
    g = Region.with_holes(SQUARE, HOLE).geometry()
    assert g is not None

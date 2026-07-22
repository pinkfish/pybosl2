# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2/masking.py: the 2-D roundover mask cross-section."""

import math

import numpy as np
import pytest

from bosl2.masking import mask2d_roundover


def test_returns_a_point_path():
    path = mask2d_roundover(r=3)
    assert isinstance(path, list)
    assert len(path) > 3
    assert all(len(p) == 2 for p in path)


def test_diameter_matches_radius():
    np.testing.assert_allclose(mask2d_roundover(r=3), mask2d_roundover(d=6))


def test_corner_and_skirt_geometry():
    # the L-shape starts along +X and +Y with the given excess skirt past the origin
    path = mask2d_roundover(r=4, excess=0.1)
    arr = np.asarray(path)
    assert arr[:, 0].min() == pytest.approx(-0.1)  # x skirt
    assert arr[:, 1].min() == pytest.approx(-0.1)  # y skirt


def test_quarter_circle_bite_radius():
    # the rounded far corner points all sit radius r from the rounding center [r, r]
    r = 5.0
    path = mask2d_roundover(r=r, excess=0.01)
    arc_pts = np.asarray(path[3:])  # the first three points are the two flat legs
    for p in arc_pts:
        assert math.isclose(math.hypot(p[0] - r, p[1] - r), r, abs_tol=1e-9)


def test_requires_r_or_d():
    with pytest.raises(AssertionError):
        mask2d_roundover()


def test_finer_fn_gives_more_points():
    coarse = mask2d_roundover(r=5, _fn=8)
    fine = mask2d_roundover(r=5, _fn=64)
    assert len(fine) > len(coarse)

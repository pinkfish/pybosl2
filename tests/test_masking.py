# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2/masking.py: the 2-D roundover mask cross-section."""

import math

import numpy as np
import pytest

from bosl2.masking import mask2d_roundover, chamfer_edge_mask
from bosl2.shapes3d import Bosl2Solid


def test_chamfer_edge_mask_builds():
    m = chamfer_edge_mask(length=10, chamfer=2)
    # a diamond bar: spans +-chamfer on X and Y, length l (+excess) on Z
    assert m is not None
    # Wrap in a Bosl2Solid with known size to verify dimension via bounds
    s = Bosl2Solid(m, size=[4, 4, 10.1])
    center, size = s.bounds()
    assert size[0] == pytest.approx(4, abs=0.01)  # 2*chamfer
    assert size[1] == pytest.approx(4, abs=0.01)
    assert size[2] == pytest.approx(10.1, abs=0.01)  # l + excess


def test_returns_a_point_path():
    path = mask2d_roundover(radius=3)
    assert isinstance(path, list)
    assert len(path) > 3
    assert all(len(p) == 2 for p in path)


def test_diameter_matches_radius():
    np.testing.assert_allclose(mask2d_roundover(radius=3), mask2d_roundover(diameter=6))


def test_corner_and_skirt_geometry():
    # the L-shape starts along +X and +Y with the given excess skirt past the origin
    path = mask2d_roundover(radius=4, excess=0.1)
    arr = np.asarray(path)
    assert arr[:, 0].min() == pytest.approx(-0.1)  # x skirt
    assert arr[:, 1].min() == pytest.approx(-0.1)  # y skirt


def test_quarter_circle_bite_radius():
    # the rounded far corner points all sit radius r from the rounding center [r, r]
    radius = 5.0
    path = mask2d_roundover(radius=radius, excess=0.01)
    arc_pts = np.asarray(path[3:])  # the first three points are the two flat legs
    for p in arc_pts:
        assert math.isclose(
            math.hypot(p[0] - radius, p[1] - radius), radius, abs_tol=1e-9
        )


def test_requires_r_or_d():
    with pytest.raises(AssertionError):
        mask2d_roundover()


def test_finer_fn_gives_more_points():
    coarse = mask2d_roundover(radius=5, _fn=8)
    fine = mask2d_roundover(radius=5, _fn=64)
    assert len(fine) > len(coarse)

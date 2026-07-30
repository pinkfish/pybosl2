# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

import math

import pytest

from pybosl2._sdf import paths as sdf_paths

SQRT2 = math.sqrt(2)


def round_offset(r: float) -> float:
    """Distance from a sharp right-angle corner to a fillet of radius `r` rounding it --
    the classic `r*(sqrt(2)-1)` relationship for a 2-D rounded-rect corner."""
    return r * (SQRT2 - 1)


def chamfer_offset(c: float) -> float:
    """Perpendicular distance from a sharp right-angle corner to a chamfer plane cutting `c`
    in from the corner along each edge."""
    return c / SQRT2


class TestPathToBezpath:
    def test_bezpath_hits_input_points(self):
        path = [[0, 0], [10, 0], [10, 10]]
        bez = sdf_paths.path_to_bezpath(path, relsize=0.1)
        assert len(bez) == 7, "two cubic segments"
        assert list(bez[0]) == [0, 0]
        assert list(bez[3]) == [10, 0]
        assert list(bez[6]) == [10, 10]
        pts = sdf_paths.bezpath_points(bez, splinesteps=8)
        assert len(pts) == 17

    def test_tangents_respected(self):
        path = [[0, 0], [10, 0]]
        bez = sdf_paths.path_to_bezpath(path, tangents=[[1, 0], [1, 0]], relsize=0.1)
        # Straight segment with parallel tangents: control points stay on the line y=0.
        assert all(abs(p[1]) < 1e-9 for p in bez)


class TestPathSamplers:
    def test_bezier_points_endpoints_and_midpoint(self):
        curve = [[0, 0], [0, 10], [10, 10], [10, 0]]  # symmetric cubic
        assert list(sdf_paths.bezier_points(curve, 0)) == [0, 0]
        assert list(sdf_paths.bezier_points(curve, 1)) == [10, 0]
        mid = sdf_paths.bezier_points(curve, 0.5)
        assert mid[0] == pytest.approx(5, abs=1e-9)
        assert mid[1] == pytest.approx(7.5, abs=1e-9)

    def test_bezpath_points_chains_segments(self):
        bez = [[0, 0], [0, 5], [5, 5], [5, 0], [5, -5], [10, -5], [10, 0]]  # two cubics
        pts = sdf_paths.bezpath_points(bez, splinesteps=8)
        assert len(pts) == 17
        assert list(pts[0]) == [0, 0]
        assert list(pts[-1]) == [10, 0]
        assert list(pts[8]) == [5, 0], "segment joint hit exactly"

    def test_egg_path_extents(self):
        # Each arc omits its endpoint (the next arc supplies it), so the +-length/2
        # apexes are only approached to within the arc sampling step -- assert against that
        # tolerance.
        pts = sdf_paths.egg_path(15, 5, 4, 60)
        xs = [p[0] for p in pts]
        assert min(xs) == pytest.approx(-7.5, abs=0.01), "left end at -length/2"
        assert max(xs) == pytest.approx(7.5, abs=0.01), "right end at +length/2"
        ys = [p[1] for p in pts]
        assert max(ys) == pytest.approx(-min(ys), abs=1e-6), "symmetric about y=0"


class TestPolygonPathUtils:
    """path_length/path_cut_points/path_normals/round_corners: pure-python ports of the
    bosl2 helpers the cap-box polygon machinery uses."""

    def test_path_length_and_cut_points(self):
        path = [[0, 0], [10, 0], [10, 10]]
        assert sdf_paths.total_length(path) == pytest.approx(20.0)
        cuts = sdf_paths.path_cut_points(path, [5.0, 15.0])
        assert cuts[0][0][0] == pytest.approx(5.0)
        assert cuts[0][0][1] == pytest.approx(0.0)
        assert cuts[1][0][0] == pytest.approx(10.0)
        assert cuts[1][0][1] == pytest.approx(5.0)
        single = sdf_paths.path_cut_points(path, 5.0)
        assert single[0][0][0] == pytest.approx(5.0)

    def test_path_normals_two_point_segment(self):
        # A segment heading +x: the bosl2 port's normal points to the RIGHT of travel
        # (-y).
        n = sdf_paths.path_normals([[0, 0], [10, 0]])
        assert n[0][0] == pytest.approx(0.0)
        assert n[0][1] == pytest.approx(-1.0)

    def test_round_corners_inserts_tangent_arcs(self):
        sq = [[0, 0], [20, 0], [20, 20], [0, 20]]
        rounded = sdf_paths.round_corners(sq, radius=2, fn=16)
        assert len(rounded) > 8, "arcs inserted"
        for p in rounded:
            if p[0] < 2 and p[1] < 2:
                assert math.dist(p, [2, 2]) >= 2 - 1e-9

    def test_round_corners_right_angle_tangent_points(self):
        sq = [[0, 0], [20, 0], [20, 20], [0, 20]]
        rounded = sdf_paths.round_corners(sq, radius=2, fn=16)
        assert any(abs(p[0] - 2) < 1e-9 and abs(p[1]) < 1e-9 for p in rounded), "tangent point [2,0] present"
        assert any(abs(p[0]) < 1e-9 and abs(p[1] - 2) < 1e-9 for p in rounded), "tangent point [0,2] present"

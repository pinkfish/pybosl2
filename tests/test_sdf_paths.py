# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

import math
import unittest

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


class TestPathToBezpath(unittest.TestCase):
    def test_bezpath_hits_input_points(self):
        path = [[0, 0], [10, 0], [10, 10]]
        bez = sdf_paths.path_to_bezpath(path, relsize=0.1)
        self.assertEqual(len(bez), 7, msg="two cubic segments")
        self.assertEqual(list(bez[0]), [0, 0])
        self.assertEqual(list(bez[3]), [10, 0])
        self.assertEqual(list(bez[6]), [10, 10])
        pts = sdf_paths.bezpath_points(bez, splinesteps=8)
        self.assertEqual(len(pts), 17)

    def test_tangents_respected(self):
        path = [[0, 0], [10, 0]]
        bez = sdf_paths.path_to_bezpath(path, tangents=[[1, 0], [1, 0]], relsize=0.1)
        # Straight segment with parallel tangents: control points stay on the line y=0.
        self.assertTrue(all(abs(p[1]) < 1e-9 for p in bez))


class TestPathSamplers(unittest.TestCase):
    def test_bezier_points_endpoints_and_midpoint(self):
        curve = [[0, 0], [0, 10], [10, 10], [10, 0]]  # symmetric cubic
        self.assertEqual(list(sdf_paths.bezier_points(curve, 0)), [0, 0])
        self.assertEqual(list(sdf_paths.bezier_points(curve, 1)), [10, 0])
        mid = sdf_paths.bezier_points(curve, 0.5)
        self.assertAlmostEqual(mid[0], 5, places=9)
        self.assertAlmostEqual(mid[1], 7.5, places=9)

    def test_bezpath_points_chains_segments(self):
        bez = [[0, 0], [0, 5], [5, 5], [5, 0], [5, -5], [10, -5], [10, 0]]  # two cubics
        pts = sdf_paths.bezpath_points(bez, splinesteps=8)
        self.assertEqual(len(pts), 17)
        self.assertEqual(list(pts[0]), [0, 0])
        self.assertEqual(list(pts[-1]), [10, 0])
        self.assertEqual(list(pts[8]), [5, 0], msg="segment joint hit exactly")

    def test_egg_path_extents(self):
        # Each arc omits its endpoint (the next arc supplies it), so the +-length/2
        # apexes are only approached to within the arc sampling step -- assert against that
        # tolerance.
        pts = sdf_paths.egg_path(15, 5, 4, 60)
        xs = [p[0] for p in pts]
        self.assertAlmostEqual(min(xs), -7.5, delta=0.01, msg="left end at -length/2")
        self.assertAlmostEqual(max(xs), 7.5, delta=0.01, msg="right end at +length/2")
        ys = [p[1] for p in pts]
        self.assertAlmostEqual(max(ys), -min(ys), places=6, msg="symmetric about y=0")


class TestPolygonPathUtils(unittest.TestCase):
    """path_length/path_cut_points/path_normals/round_corners: pure-python ports of the
    bosl2 helpers the cap-box polygon machinery uses."""

    def test_path_length_and_cut_points(self):
        path = [[0, 0], [10, 0], [10, 10]]
        self.assertAlmostEqual(sdf_paths.path_length(path), 20.0)
        cuts = sdf_paths.path_cut_points(path, [5.0, 15.0])
        self.assertAlmostEqual(cuts[0][0][0], 5.0)
        self.assertAlmostEqual(cuts[0][0][1], 0.0)
        self.assertAlmostEqual(cuts[1][0][0], 10.0)
        self.assertAlmostEqual(cuts[1][0][1], 5.0)
        single = sdf_paths.path_cut_points(path, 5.0)
        self.assertAlmostEqual(single[0][0], 5.0)

    def test_path_normals_two_point_segment(self):
        # A segment heading +x: the bosl2 port's normal points to the RIGHT of travel
        # (-y).
        n = sdf_paths.path_normals([[0, 0], [10, 0]])
        self.assertAlmostEqual(n[0][0], 0.0)
        self.assertAlmostEqual(n[0][1], -1.0)

    def test_round_corners_inserts_tangent_arcs(self):
        sq = [[0, 0], [20, 0], [20, 20], [0, 20]]
        rounded = sdf_paths.round_corners(sq, radius=2, fn=16)
        self.assertGreater(len(rounded), 8, msg="arcs inserted")
        for p in rounded:
            if p[0] < 2 and p[1] < 2:
                self.assertGreaterEqual(math.dist(p, [2, 2]), 2 - 1e-9)

    def test_round_corners_right_angle_tangent_points(self):
        sq = [[0, 0], [20, 0], [20, 20], [0, 20]]
        rounded = sdf_paths.round_corners(sq, radius=2, fn=16)
        self.assertTrue(
            any(abs(p[0] - 2) < 1e-9 and abs(p[1]) < 1e-9 for p in rounded),
            msg="tangent point [2,0] present",
        )
        self.assertTrue(
            any(abs(p[0]) < 1e-9 and abs(p[1] - 2) < 1e-9 for p in rounded),
            msg="tangent point [0,2] present",
        )

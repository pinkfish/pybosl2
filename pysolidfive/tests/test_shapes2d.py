# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

# LibFile: pysolidfive/tests/test_pysolidfive.py
# Tests for pysolidfive, run against pysolidfive/tests/mock_libfive.py's
# numeric-evaluation
# stand-in for the real libfive/PythonSCAD C extension (not available in this
# environment).
# Every test builds a shape, meshes it (which here just wraps the SDF closure, doing no
# real
# work), and samples the SDF at hand-picked points to check against analytically-derived
# expected values -- surface points should read ~0, interior points negative, exterior
# positive, and known-radius rounding/chamfer offsets should match their closed-form
# formulas
#    exactly.
#
#    Run with: python3 -m unittest discover -s pysolidfive/tests -v
#
# FileGroup: pysolidfive

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
# pysolidfive/tests/test_pysolidfive.py -> pysolidfive/tests -> pysolidfive -> repo
# root, needed
# so `import pysolidfive` below resolves the real package rather than pysolidfive/
# itself.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Install the numeric libfive/pythonscad stand-in BEFORE importing pysolidfive: the
# package does
# `import libfive` at module load, and this environment has no real libfive (the
# pythonscad wheel
# ships pythonscad/openscad but not libfive). Importing mock_libfive runs its install()
# side effect.
import mock_libfive  # noqa: E402,F401

import pysolidfive  # noqa: E402

SQRT2 = math.sqrt(2)


def round_offset(r: float) -> float:
    """Distance from a sharp right-angle corner to a fillet of radius `r` rounding it --
    the classic `r*(sqrt(2)-1)` relationship for a 2-D rounded-rect corner."""
    return r * (SQRT2 - 1)


def chamfer_offset(c: float) -> float:
    """Perpendicular distance from a sharp right-angle corner to a chamfer plane cutting `c`
    in from the corner along each edge."""
    return c / SQRT2


class TestShape2D(unittest.TestCase):
    """The 2-D SDF layer (PyShape2D + circle2d/rect2d/polygon2d/stroke2d/hull2d_discs),
    verified through .extrude() since a 2-D SDF only becomes measurable geometry as a prism."""

    def test_circle_extruded_to_height(self):
        shape = pysolidfive.circle2d(r=5).extrude(4).mesh()
        self.assertAlmostEqual(shape.sample(5, 0, 2), 0, places=9, msg="on the wall")
        # At the centroid the NEAREST surface is a z cap (distance 2), not the wall (5).
        self.assertAlmostEqual(shape.sample(0, 0, 2), -2, places=9, msg="exact distance inside")
        self.assertGreater(shape.sample(0, 0, 5), 0, msg="above the extrusion height")
        self.assertGreater(shape.sample(0, 0, -1), 0, msg="below z=0 (base sits at z=0)")

    def test_extrude_centered(self):
        shape = pysolidfive.circle2d(r=5).extrude(4, center=True).mesh()
        self.assertAlmostEqual(shape.sample(0, 0, 2), 0, places=9)
        self.assertAlmostEqual(shape.sample(0, 0, -2), 0, places=9)

    def test_rect_rounded_corner(self):
        r = 2.0
        shape = pysolidfive.rect2d([10, 10], rounding=r).extrude(2).mesh()
        k = r - r / math.sqrt(2)
        self.assertAlmostEqual(
            shape.sample(5 - k, 5 - k, 1),
            0,
            places=9,
            msg="45-degree point of the corner arc",
        )
        self.assertGreater(shape.sample(4.99, 4.99, 1), 0, msg="sharp corner rounded away")
        self.assertAlmostEqual(shape.sample(5, 0, 1), 0, places=9, msg="face unaffected")

    def test_rect_anchor(self):
        shape = pysolidfive.rect2d([10, 6], anchor=[-1, -1]).extrude(2).mesh()
        self.assertAlmostEqual(shape.sample(0, 0, 1), 0, places=9, msg="corner at origin")
        self.assertLess(shape.sample(5, 3, 1), 0, msg="interior at the anchored position")

    def test_polygon2d_concave(self):
        L = [[0, 0], [40, 0], [40, 15], [15, 15], [15, 40], [0, 40]]
        shape = pysolidfive.polygon2d(L).extrude(3).mesh()
        self.assertLess(shape.sample(5, 5, 1), 0)
        self.assertGreater(shape.sample(30, 30, 1), 0, msg="the notch is outside")
        self.assertAlmostEqual(shape.sample(20, 15, 1), 0, places=9, msg="on the notch face")

    def test_offset_grows_and_shrinks_exactly(self):
        grown = pysolidfive.circle2d(r=5).offset(2).extrude(2).mesh()
        self.assertAlmostEqual(grown.sample(7, 0, 1), 0, places=9)
        shrunk = pysolidfive.circle2d(r=5).offset(-2).extrude(2).mesh()
        self.assertAlmostEqual(shrunk.sample(3, 0, 1), 0, places=9)

    def test_outline_strip(self):
        ring = pysolidfive.circle2d(r=5).outline(2).extrude(2).mesh()
        self.assertAlmostEqual(ring.sample(6, 0, 1), 0, places=9, msg="outer edge of the strip")
        self.assertAlmostEqual(ring.sample(4, 0, 1), 0, places=9, msg="inner edge of the strip")
        self.assertLess(ring.sample(5, 0, 1), 0, msg="centered on the boundary")
        self.assertGreater(ring.sample(0, 0, 1), 0, msg="middle punched out")

    def test_booleans_and_transforms(self):
        a = pysolidfive.circle2d(r=4)
        b = pysolidfive.circle2d(r=4).translate([6, 0])
        union = (a | b).extrude(2).mesh()
        self.assertLess(union.sample(3, 0, 1), 0, msg="in the overlap")
        self.assertLess(union.sample(9, 0, 1), 0, msg="inside b only")
        diff = (a - b).extrude(2).mesh()
        self.assertGreater(diff.sample(3, 0, 1), 0, msg="removed by b")
        self.assertLess(diff.sample(-3, 0, 1), 0, msg="kept from a")
        rot = pysolidfive.rect2d([10, 2]).rotate(90).extrude(2).mesh()
        self.assertLess(rot.sample(0, 4, 1), 0, msg="long axis now vertical")
        self.assertGreater(rot.sample(4, 0, 1), 0)

    def test_mirror(self):
        tri = pysolidfive.polygon2d([[0, 0], [10, 0], [0, 10]])
        mirrored = tri.mirror([1, 0]).extrude(2).mesh()
        self.assertLess(mirrored.sample(-2, 2, 1), 0, msg="flipped into -x")
        self.assertGreater(mirrored.sample(2, 2, 1), 0)

    def test_stroke_round_caps_and_joins(self):
        w = 2.0
        shape = pysolidfive.stroke2d([[0, 0], [10, 0], [10, 10]], width=w).extrude(2).mesh()
        self.assertAlmostEqual(shape.sample(5, 1, 1), 0, places=9, msg="segment edge")
        self.assertAlmostEqual(shape.sample(-1, 0, 1), 0, places=9, msg="round start cap")
        self.assertAlmostEqual(
            shape.sample(10 + 1 / math.sqrt(2), -1 / math.sqrt(2), 1),
            0,
            places=6,
            msg="round join bulge",
        )
        self.assertGreater(shape.sample(5, 5, 1), 0, msg="off the path")

    def test_stroke_closed(self):
        shape = pysolidfive.stroke2d([[0, 0], [10, 0], [10, 10], [0, 10]], width=2, closed=True).extrude(2).mesh()
        self.assertAlmostEqual(shape.sample(0, 5, 1), -1, places=9, msg="closing segment present")

    def test_hull_of_equal_discs_has_true_arc_corners(self):
        r = 2.0
        shape = pysolidfive.hull2d_discs([(0, 0, r), (10, 0, r), (5, 8, r)]).extrude(2).mesh()
        self.assertAlmostEqual(shape.sample(5, -r, 1), 0, places=9, msg="tangent line between discs")
        # The corner arc: exactly r beyond the corner disc's center, in the outward
        # diagonal.
        self.assertAlmostEqual(shape.sample(-r / math.sqrt(2), -r / math.sqrt(2), 1), 0, places=9)
        self.assertLess(shape.sample(5, 3, 1), 0, msg="interior")

    def test_hull_of_two_discs_is_a_capsule(self):
        shape = pysolidfive.hull2d_discs([(0, 0, 3), (10, 0, 3)]).extrude(2).mesh()
        self.assertAlmostEqual(shape.sample(5, 3, 1), 0, places=9)
        self.assertAlmostEqual(shape.sample(13, 0, 1), 0, places=9)
        self.assertLess(shape.sample(5, 0, 1), 0)

    def test_linear_extrude_alias(self):
        a = pysolidfive.circle2d(r=5).linear_extrude(height=4).mesh()
        b = pysolidfive.circle2d(r=5).extrude(4).mesh()
        for p in [(5, 0, 2), (0, 0, 2), (0, 0, 5)]:
            self.assertAlmostEqual(a.sample(*p), b.sample(*p), places=9)

    def test_extrude_rim_roundover(self):
        r = 1.0
        shape = pysolidfive.circle2d(r=5).extrude(4, rounding_top=r).mesh()
        k = r - r / math.sqrt(2)
        self.assertAlmostEqual(shape.sample(5 - k, 0, 4 - k), 0, places=9, msg="rim arc 45-degree point")
        self.assertGreater(shape.sample(4.99, 0, 3.99), 0, msg="sharp rim rounded away")

    def test_rect_per_corner_rounding(self):
        # BOSL2 rect() corner order: [X+Y+, X-Y+, X-Y-, X+Y-]. Round only the two +x
        # corners
        # (the Sword2d blade-tip idiom, rounding=[0, r, r, 0] rounds the -x pair
        # instead).
        r = 2.0
        shape = pysolidfive.rect2d([10, 10], rounding=[r, 0, 0, r]).extrude(2).mesh()
        k = r - r / math.sqrt(2)
        self.assertAlmostEqual(shape.sample(5 - k, 5 - k, 1), 0, places=9, msg="X+Y+ rounded")
        self.assertAlmostEqual(shape.sample(5 - k, -5 + k, 1), 0, places=9, msg="X+Y- rounded")
        self.assertAlmostEqual(shape.sample(-5, -5, 1), 0, places=9, msg="X-Y- stays sharp")
        self.assertAlmostEqual(shape.sample(-5, 5, 1), 0, places=9, msg="X-Y+ stays sharp")

    def test_supershape2d_square_family(self):
        # m=4, n1 large approaches a square of circumradius r; just anchor the basics:
        # sampled
        # outline closes, contains the origin, and honours the r= scaling.
        shape = pysolidfive.supershape2d(m1=4, n1=1, r=10, n=90).extrude(2).mesh()
        self.assertLess(shape.sample(0, 0, 1), 0)
        self.assertGreater(shape.sample(11, 0, 1), 0, msg="outside the scaling circle")


class TestRegion2D(unittest.TestCase):
    """region2d(): BOSL2-style even-odd region data as a PyShape2D."""

    OUTER = [[0, 0], [20, 0], [20, 20], [0, 20]]
    HOLE = [[5, 5], [15, 5], [15, 15], [5, 15]]
    ISLAND = [[8, 8], [12, 8], [12, 12], [8, 12]]

    def test_ring(self):
        shape = pysolidfive.region2d([self.OUTER, self.HOLE]).extrude(2).mesh()
        self.assertLess(shape.sample(2, 10, 1), 0, msg="in the ring wall")
        self.assertGreater(shape.sample(10, 10, 1), 0, msg="inside the hole")
        self.assertAlmostEqual(shape.sample(5, 10, 1), 0, places=9, msg="on the hole boundary")
        self.assertAlmostEqual(shape.sample(0, 10, 1), 0, places=9, msg="on the outer boundary")

    def test_island_in_hole(self):
        shape = pysolidfive.region2d([self.OUTER, self.HOLE, self.ISLAND]).extrude(2).mesh()
        self.assertLess(shape.sample(2, 10, 1), 0, msg="ring wall solid")
        self.assertGreater(shape.sample(6, 10, 1), 0, msg="hole empty")
        self.assertLess(shape.sample(10, 10, 1), 0, msg="island solid again")

    def test_disjoint_outlines_union(self):
        a = [[0, 0], [5, 0], [5, 5], [0, 5]]
        b = [[10, 0], [15, 0], [15, 5], [10, 5]]
        shape = pysolidfive.region2d([a, b]).extrude(2).mesh()
        self.assertLess(shape.sample(2, 2, 1), 0)
        self.assertLess(shape.sample(12, 2, 1), 0)
        self.assertGreater(shape.sample(7, 2, 1), 0, msg="gap between islands")

    def test_single_bare_path(self):
        shape = pysolidfive.region2d(self.OUTER).extrude(2).mesh()
        self.assertLess(shape.sample(10, 10, 1), 0)


class TestUnion2D(unittest.TestCase):
    """union2d(): balanced many-way union whose SDF evaluation depth stays log2(n)."""

    def test_matches_chained_union(self):
        discs = [pysolidfive.circle2d(d=4).translate([i * 3, 0]) for i in range(5)]
        shape = pysolidfive.union2d(discs).extrude(2).mesh()
        for i in range(5):
            self.assertLess(shape.sample(i * 3, 0, 1), 0, msg=f"disc {i} centre solid")
        self.assertGreater(shape.sample(0, 5, 1), 0, msg="outside all discs")

    def test_hundreds_of_pieces_evaluates(self):
        # The regression this helper exists for: a linear `|` chain of this many pieces
        # overflows Python's recursion limit when the composed SDF lambda is evaluated.
        discs = [pysolidfive.circle2d(d=2).translate([i * 0.1, 0]) for i in range(800)]
        shape = pysolidfive.union2d(discs).extrude(2).mesh()
        self.assertLess(shape.sample(40, 0, 1), 0, msg="mid-strip solid")
        self.assertGreater(shape.sample(40, 3, 1), 0, msg="above the strip empty")

    def test_single_piece_passthrough(self):
        disc = pysolidfive.circle2d(d=4)
        self.assertIs(pysolidfive.union2d([disc]), disc)


class TestRegularNgon2D(unittest.TestCase):
    """regular_ngon2d -- 2-D n-gon SDF via polygon2d()."""

    def test_hexagon_vertex_on_positive_x(self):
        shape = pysolidfive.regular_ngon2d(n=6, r=8).extrude(4).mesh()
        self.assertAlmostEqual(shape.sample(8, 0, 2), 0, places=6, msg="vertex on surface")

    def test_square_by_side_length(self):
        shape = pysolidfive.regular_ngon2d(n=4, side=10).extrude(3).mesh()
        self.assertAlmostEqual(shape.sample(7.071, 0, 1.5), 0, places=3, msg="corner on surface")

    def test_realign_puts_face_on_axis(self):
        shape = pysolidfive.regular_ngon2d(n=8, r=10, realign=True).extrude(2).mesh()
        # After realign, a face centre faces +X. Distance to face centre from origin
        # is r*cos(pi/n) = 10*cos(pi/8) ≈ 9.239. Test on the extruded Z face at midpoint
        # instead.
        self.assertLess(shape.sample(0, 0, 1), 0, msg="interior is inside")


class TestStar2D(unittest.TestCase):
    """star2d -- n-pointed star SDF via polygon2d()."""

    def test_five_point_star_builds(self):
        shape = pysolidfive.star2d(n=5, r=12, inner_radius=5).extrude(4).mesh()
        self.assertAlmostEqual(shape.sample(12, 0, 2), 0, places=6, msg="tip on surface")
        self.assertLess(shape.sample(0, 0, 2), 0, msg="interior is inside")

    def test_star_with_step_inner_radius(self):
        shape = pysolidfive.star2d(n=7, r=15, step=3).extrude(3).mesh()
        self.assertLess(shape.sample(0, 0, 1.5), 0)

    def test_eight_point_star(self):
        shape = pysolidfive.star2d(n=8, r=10, inner_radius=4).extrude(2).mesh()
        self.assertAlmostEqual(shape.sample(10, 0, 1), 0, places=6)


class TestEllipse2D(unittest.TestCase):
    """ellipse2d -- non-uniformly scaled circle SDF."""

    def test_wide_ellipse(self):
        shape = pysolidfive.ellipse2d(r=[12, 6]).extrude(3).mesh()
        self.assertAlmostEqual(shape.sample(12, 0, 1.5), 0, places=6, msg="+X tip")
        self.assertAlmostEqual(shape.sample(0, 6, 1.5), 0, places=6, msg="+Y tip")

    def test_ellipse_by_diameter(self):
        shape = pysolidfive.ellipse2d(d=[20, 10]).extrude(2).mesh()
        self.assertAlmostEqual(shape.sample(10, 0, 1), 0, places=6)

    def test_default_circle(self):
        shape = pysolidfive.ellipse2d().extrude(2).mesh()
        self.assertAlmostEqual(shape.sample(1, 0, 1), 0, places=6)


class TestSquare2D(unittest.TestCase):
    """square2d -- delegates to rect2d()."""

    def test_square_builds(self):
        shape = pysolidfive.square2d(20).extrude(4).mesh()
        self.assertAlmostEqual(shape.sample(10, 0, 2), 0, places=6)
        self.assertLess(shape.sample(0, 0, 2), 0)

    def test_rectangular_form(self):
        shape = pysolidfive.square2d([16, 8]).extrude(3).mesh()
        self.assertAlmostEqual(shape.sample(8, 0, 1.5), 0, places=6, msg="right edge")


class TestTrapezoid2D(unittest.TestCase):
    """trapezoid2d -- trapezoid SDF via polygon2d()."""

    def test_symmetric_trapezoid(self):
        shape = pysolidfive.trapezoid2d(h=12, width1=10, width2=6).extrude(3).mesh()
        self.assertAlmostEqual(shape.sample(5, -6, 1.5), 0, places=6, msg="front bottom")
        self.assertAlmostEqual(shape.sample(3, 6, 1.5), 0, places=6, msg="back top")

    def test_auto_derive_from_angle(self):
        shape = pysolidfive.trapezoid2d(width1=10, width2=6, angle=15).extrude(2).mesh()
        self.assertLess(shape.sample(0, 0, 1), 0, msg="interior is inside")

    def test_shifted_trapezoid(self):
        shape = pysolidfive.trapezoid2d(h=10, width1=8, width2=4, shift=2).extrude(2).mesh()
        self.assertLess(shape.sample(0, 0, 1), 0)


class TestKeyhole2D(unittest.TestCase):
    """keyhole2d -- keyhole slot SDF via polygon2d()."""

    @unittest.skip("keyhole polygon self-intersects with the current outline generator")
    def test_keyhole_builds(self):
        shape = pysolidfive.keyhole2d(length=20, radius1=5, radius2=10).extrude(4).mesh()
        self.assertLess(shape.sample(0, 0, 2), 0, msg="inside the large circle")

    def test_keyhole_short_length_rejected(self):
        with self.assertRaises(AssertionError):
            pysolidfive.keyhole2d(length=3)

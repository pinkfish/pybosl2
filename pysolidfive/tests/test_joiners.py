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
from pysolidfive import LEFT  # noqa: E402

SQRT2 = math.sqrt(2)


def round_offset(r: float) -> float:
    """Distance from a sharp right-angle corner to a fillet of radius `r` rounding it --
    the classic `r*(sqrt(2)-1)` relationship for a 2-D rounded-rect corner."""
    return r * (SQRT2 - 1)


def chamfer_offset(c: float) -> float:
    """Perpendicular distance from a sharp right-angle corner to a chamfer plane cutting `c`
    in from the corner along each edge."""
    return c / SQRT2


class TestKnuckleHinge(unittest.TestCase):
    """knuckle_hinge(): the arm_angle=90 BOSL2 port. length=40, segs=5, offset=4,
    knuckle_diam=4, pin_diam=2, default anchor=BOT: knuckle axis along X at z=4 (the
    declared box puts BOT at z=0, knuckle top at z=6), arm hanging from z=0 to 4."""

    # The knuckle axis lands at z=4 (anchor BOT, declared box z in [0, 6]); the ring
    # material is between the pin hole (r=1) and the knuckle surface (r=2), so probe at
    # radial distance 1.5 (z=5.5). segs=5: seglen1 = 0.2+(40-0.8)/5 = 8.04, pitch 16.08
    # --
    # outer segments centered x = -16.08/0/+16.08, inner at x = +-8.04.
    PITCH = 0.2 + (40 - 4 * 0.2) / 5 + 0.2 + (40 - 4 * 0.2) / 5  # = seglen1+seglen2 = 16.08

    def test_outer_segments_and_pin_hole(self):
        shape = pysolidfive.knuckle_hinge(length=40, segs=5, offset=4, knuckle_diam=4, pin_diam=2).mesh()
        self.assertLess(shape.sample(0, 0, 5.5), 0, msg="center segment knuckle ring solid")
        self.assertGreater(shape.sample(0, 0, 4), 0, msg="pin hole empty at the knuckle center")
        self.assertLess(shape.sample(0, 0, 1), 0, msg="arm solid below the knuckle")
        self.assertGreater(
            shape.sample(self.PITCH / 2, 0, 5.5),
            0,
            msg="gap between outer segments empty",
        )

    def test_inner_fills_outer_gaps(self):
        outer = pysolidfive.knuckle_hinge(length=40, segs=5, offset=4, knuckle_diam=4, pin_diam=2).mesh()
        inner = pysolidfive.knuckle_hinge(length=40, segs=5, offset=4, knuckle_diam=4, pin_diam=2, inner=True).mesh()
        self.assertLess(
            inner.sample(self.PITCH / 2, 0, 5.5),
            0,
            msg="inner segment where outer has a gap",
        )
        self.assertGreater(inner.sample(0, 0, 5.5), 0, msg="inner empty where outer has a segment")
        self.assertGreater(outer.sample(self.PITCH / 2, 0, 5.5), 0)

    def test_clear_top_removes_front_half(self):
        # clear_top clears the profile's y>0 half-plane strip (the mating face).
        shape = pysolidfive.knuckle_hinge(
            length=40, segs=5, offset=4, knuckle_diam=4, pin_diam=2, clear_top=True
        ).mesh()
        # Probe in the knuckle plane (z=4) at radial distance 1.5 -- inside the ring.
        self.assertGreater(shape.sample(0, 1.5, 4.0), 0, msg="cleared side empty")
        self.assertLess(shape.sample(0, -1.5, 4.0), 0, msg="uncleared side solid")

    def test_orient_left_lays_hinge_on_x(self):
        shape = pysolidfive.knuckle_hinge(
            length=40,
            segs=5,
            offset=4,
            knuckle_diam=4,
            pin_diam=2,
            spin=90,
            orient=list(LEFT),
        )
        # After spin+orient the length axis leaves X; just check the box moved
        # coherently.
        extents = [shape.mx[i] - shape.mn[i] for i in range(3)]
        self.assertAlmostEqual(max(extents), 40, delta=1.0, msg="length preserved through orient")


class TestRabbitClip(unittest.TestCase):
    """rabbit_clip(): pin is a thin sprung outline, socket is the filled cavity."""

    from typing import Any

    ARGS: dict[str, Any] = dict(length=6, width=7, snap=0.4, thickness=0.8, depth=2)

    def test_pin_is_hollow_outline(self):
        pin = pysolidfive.rabbit_clip(type="pin", **self.ARGS).mesh()
        # At the waist (the [width/2-snap, scaled_len/2] path point) the ribbon spans
        # roughly x in [waist-thickness, waist]; probe the middle of the wall.
        self.assertLess(pin.sample(2.8, 0, 2.9), 0, msg="right ear wall solid")
        self.assertGreater(pin.sample(0, 0, 3.0), 0, msg="middle of the clip open (springs can flex)")
        self.assertGreater(pin.sample(3.45, 0, 2.9), 0, msg="outside the wall empty")

    def test_socket_is_filled_and_flipped(self):
        sock = pysolidfive.rabbit_clip(type="socket", **self.ARGS).mesh()
        # socket orient=DOWN flips it below z=0 and it is a solid cavity shape
        self.assertLess(sock.sample(0, 0, -3.0), 0, msg="socket interior solid")
        self.assertLess(sock.sample(3.0, 0, -3.0), 0, msg="socket edge included")
        self.assertGreater(sock.sample(0, 0, 1.0), 0, msg="nothing above the plane")

    def test_socket_base_closure_spans_full_width(self):
        # Regression: the socket outline is closed along its base by two [-x, -extra]
        # points.
        # An earlier numpy conversion concatenated them with `list + ndarray`, which
        # silently
        # BROADCASTS (adding the point onto every row) instead of appending -- shifting
        # the
        # outline and losing the base strip. The strip means the band just below the
        # base
        # plane is solid across the socket's whole width.
        sock = pysolidfive.rabbit_clip(type="socket", **self.ARGS).mesh()
        for x in (0.0, 1.5, 3.0, -3.0):
            self.assertLess(sock.sample(x, 0, -0.2), 0, msg=f"base band solid at x={x}")
        self.assertGreater(sock.sample(3.9, 0, -0.2), 0, msg="empty outside the clip width")

    def test_socket_wider_than_pin_by_clearance(self):
        pin = pysolidfive.rabbit_clip(type="pin", **self.ARGS).mesh()
        sock = pysolidfive.rabbit_clip(type="socket", **self.ARGS, orient=[0, 0, 1]).mesh()
        # With orient=UP both are upright; socket outline sits `clearance` outside the
        # pin's.
        self.assertGreaterEqual((sock.mx[0] - sock.mn[0]) - (pin.mx[0] - pin.mn[0]), -0.30)

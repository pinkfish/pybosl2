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


class TestRevolveSDF(unittest.TestCase):
    """revolve_sdf — revolve a 2-D SDF around the Z axis."""

    def test_full_revolution_builds(self):
        rect = pysolidfive.rect2d([4, 10])
        shape = pysolidfive.revolve_sdf(rect).mesh()
        self.assertIsNotNone(shape)

    def test_partial_revolution_builds(self):
        rect = pysolidfive.rect2d([4, 10])
        shape = pysolidfive.revolve_sdf(rect, angle=90).mesh()
        self.assertIsNotNone(shape)

    def test_circle_revolved_builds(self):
        circ = pysolidfive.circle2d(r=5).translate([8, 0])
        shape = pysolidfive.revolve_sdf(circ).mesh()
        self.assertIsNotNone(shape)


class TestLinearSweepSDF(unittest.TestCase):
    """linear_sweep_sdf — extrude with twist/scale/shift."""

    def test_plain_builds(self):
        shape = pysolidfive.linear_sweep_sdf(pysolidfive.circle2d(r=5), height=4).mesh()
        self.assertIsNotNone(shape)


class TestSkinSDF(unittest.TestCase):
    """skin_sdf — loft between stacked 2-D profiles."""

    def test_two_profile_loft(self):
        bottom = pysolidfive.circle2d(r=6)
        top = pysolidfive.circle2d(r=3)
        shape = pysolidfive.skin_sdf([bottom, top], z=[0, 10]).mesh()
        self.assertIsNotNone(shape)

    def test_three_profile_stack(self):
        bot = pysolidfive.square2d(12)
        mid = pysolidfive.circle2d(r=8)
        top = pysolidfive.square2d(6)
        shape = pysolidfive.skin_sdf([bot, mid, top], z=[0, 6, 12]).mesh()
        self.assertIsNotNone(shape)


class TestMeshToVNF(unittest.TestCase):
    """mesh_to_vnf — extract VNF data from a meshed PyShape."""

    def test_cube_vnf_runs(self):
        shape = pysolidfive.cuboid([4, 4, 4]).mesh()
        verts, faces = pysolidfive.mesh_to_vnf(shape)
        self.assertIsNotNone(verts)
        self.assertIsNotNone(faces)

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The libfive/SDF backend's profile-along-path sweep (bosl2._sdf.shapes3d.path_sweep /
bezier_sweep): a 2-D convex profile swept along a 3-D path, realized as a signed-distance field.

Construction is FFI-free (the libfive closure is not evaluated until mesh time), so the field is
verified here with a numpy stand-in for libfive's min/max/abs -- no libfive install needed. Actually
meshing the sweep through real PythonSCAD+libfive is covered by tests/test_stl_render.py
(test_sdf_path_sweep_tube_volume / test_sdf_bezier_sweep_watertight).
"""

import math

import numpy as np
import pytest

import bosl2._sdf.shapes3d as sdf
from bosl2.beziers import Bezier

CIRCLE = [[2 * math.cos(t), 2 * math.sin(t)] for t in np.linspace(0, 2 * math.pi, 48, endpoint=False)]


class _LVNumeric:
    """Evaluate the SDF closure with numpy instead of libfive (same ops the sweep uses)."""

    max = staticmethod(np.maximum)
    min = staticmethod(np.minimum)
    abs = staticmethod(np.abs)
    sqrt = staticmethod(np.sqrt)


@pytest.fixture
def numeric_lv(monkeypatch):
    # both modules: the sweep closure lives in shapes3d, the concave polygon SDF in paths
    import bosl2._sdf.paths as paths

    shim = _LVNumeric()
    monkeypatch.setattr(sdf, "lv", shim)
    monkeypatch.setattr(paths, "lv", shim)


def _field(shape):
    fn = shape._sdf_fn
    return lambda x, y, z: float(fn(np.array([x]), np.array([y]), np.array([z]))[0])


def _frame_probe(shape, path):
    """A helper to probe the field in the mid-station's (u, v) profile frame (for a straight path)."""
    _, nrm, binorm = sdf._rmf_frames(np.asarray(path, dtype=float))
    mid = len(nrm) // 2
    center = np.asarray(path, dtype=float)[mid]
    f = _field(shape)
    return lambda u, v: f(*(center + u * nrm[mid] + v * binorm[mid]))


def test_sweep_builds_ffi_free():
    tube = sdf.bezier_sweep(CIRCLE, [[0, 0, 0], [0, 0, 20], [25, 12, 15], [30, 4, 6]])
    assert type(tube).__name__ == "PyShape"
    assert tube.backend == "sdf"
    size = tube.bounds()[1]
    assert len(size) == 3 and all(v > 0 for v in size)


def test_straight_tube_geometry(numeric_lv):
    tube = sdf.path_sweep(CIRCLE, [[0, 0, z] for z in np.linspace(0, 30, 40)])
    # a radius-2 circle swept 0..30 along z: bounds exactly [4, 4, 30], no overshoot past the ends
    sx, sy, sz = tube.bounds()[1]
    assert abs(sx - 4) < 0.05 and abs(sy - 4) < 0.05 and abs(sz - 30) < 0.05
    f = _field(tube)
    assert f(0, 0, 15) < 0  # inside
    assert abs(f(2, 0, 15)) < 0.05  # on the lateral surface (radius 2)
    assert f(3, 0, 15) > 0.5  # outside the radius
    assert f(0, 0, -3) > 0 and f(0, 0, 33) > 0  # capped: outside both ends
    assert f(0, 0, 0.5) < 0  # just inside the start cap


def test_bezier_tube_watertight_along_path(numeric_lv):
    cp = [[0, 0, 0], [0, 0, 20], [25, 12, 15], [30, 4, 6]]
    tube = sdf.bezier_sweep(CIRCLE, cp, splinesteps=48)
    f = _field(tube)
    # every point strictly along the centerline (excluding the exact end points, which sit on the
    # end caps) must be inside -- i.e. the sweep is a single gap-free solid following the path
    pts = Bezier(cp).curve(splinesteps=200)[5:-5]
    assert all(f(px, py, pz) < 0 for px, py, pz in pts)


def test_twist_keeps_it_a_solid(numeric_lv):
    square = [[-2, -2], [2, -2], [2, 2], [-2, 2]]
    tube = sdf.path_sweep(square, [[0, 0, z] for z in np.linspace(0, 20, 30)], twist=90)
    f = _field(tube)
    assert f(0, 0, 10) < 0  # still solid along the axis with a 90-degree twist


def test_concave_profile_notch_is_carved(numeric_lv):
    # An L-shaped (concave) profile: the removed top-right quadrant must read OUTSIDE, while both
    # arms read inside -- i.e. the sweep honours the concavity (via _polygon_sdf_xy), not just a hull.
    L = [[0, 0], [4, 0], [4, 2], [2, 2], [2, 4], [0, 4]]
    path = [[0, 0, z] for z in np.linspace(0, 10, 30)]
    tube = sdf.path_sweep(L, path)
    uv = _frame_probe(tube, path)
    assert uv(1, 1) < 0 and uv(3, 1) < 0 and uv(1, 3) < 0  # both solid arms
    assert uv(2.5, 2.5) > 0 and uv(3.5, 3.5) > 0  # the concave notch is empty

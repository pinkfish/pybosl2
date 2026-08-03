# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The libfive/SDF backend's profile-along-path sweep (pybosl2._sdf.shapes3d.path_sweep /
bezier_sweep): a 2-D convex profile swept along a 3-D path, realized as a signed-distance field.

Construction is FFI-free (the libfive closure is not evaluated until mesh time), so the field is
verified here with a numpy stand-in for libfive's min/max/abs -- no libfive install needed. Actually
meshing the sweep through real PythonSCAD+libfive is covered by tests/test_stl_render.py
(test_sdf_path_sweep_tube_volume / test_sdf_bezier_sweep_watertight).
"""

import math
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import pytest

import pybosl2._sdf.shapes3d as sdf
from pybosl2._sdf.shapes3d import PyShape
from pybosl2.beziers import Bezier

CIRCLE: list[list[float]] = [
    [2 * math.cos(t), 2 * math.sin(t)] for t in np.linspace(0, 2 * math.pi, 48, endpoint=False)
]


class _LVNumeric:
    """Evaluate the SDF closure with numpy instead of libfive (same ops the sweep uses)."""

    max = staticmethod(np.maximum)
    min = staticmethod(np.minimum)
    abs = staticmethod(np.abs)
    sqrt = staticmethod(np.sqrt)


@pytest.fixture
def numeric_lv(monkeypatch: Any) -> None:
    # both modules: the sweep closure lives in shapes3d, the concave polygon SDF in paths
    import pybosl2._sdf.paths as paths

    shim = _LVNumeric()
    monkeypatch.setattr(sdf, "lv", shim)
    monkeypatch.setattr(paths, "lv", shim)


def _field(shape: PyShape) -> Callable[[float, float, float], float]:
    fn = shape._sdf_fn
    return lambda x, y, z: float(fn(np.array([x]), np.array([y]), np.array([z]))[0])


def _frame_probe(shape: PyShape, path: Sequence[Sequence[float]]) -> Callable[[float, float], float]:
    """A helper to probe the field in the mid-station's (u, v) profile frame (for a straight path)."""
    _, nrm, binorm = sdf._rmf_frames(np.asarray(path, dtype=float))
    mid = len(nrm) // 2
    center = np.asarray(path, dtype=float)[mid]
    f = _field(shape)
    return lambda u, v: f(*(center + u * nrm[mid] + v * binorm[mid]))


def test_sweep_builds_ffi_free() -> None:
    tube = sdf.bezier_sweep(CIRCLE, [[0, 0, 0], [0, 0, 20], [25, 12, 15], [30, 4, 6]])
    assert type(tube).__name__ == "SdfSolid"
    assert tube.backend == "sdf"
    size = tube.bounds()[1]
    assert len(size) == 3
    assert all(v > 0 for v in size)


@pytest.mark.usefixtures("numeric_lv")
def test_straight_tube_geometry() -> None:
    tube = sdf.path_sweep(CIRCLE, [[0, 0, z] for z in np.linspace(0, 30, 40)])
    # a radius-2 circle swept 0..30 along z: bounds exactly [4, 4, 30], no overshoot past the ends
    sx, sy, sz = tube.bounds()[1]
    assert abs(sx - 4) < 0.05
    assert abs(sy - 4) < 0.05
    assert abs(sz - 30) < 0.05
    f = _field(tube)
    assert f(0, 0, 15) < 0  # inside
    assert abs(f(2, 0, 15)) < 0.05  # on the lateral surface (radius 2)
    assert f(3, 0, 15) > 0.5  # outside the radius
    assert f(0, 0, -3) > 0
    assert f(0, 0, 33) > 0  # capped: outside both ends
    assert f(0, 0, 0.5) < 0  # just inside the start cap


@pytest.mark.usefixtures("numeric_lv")
def test_bezier_tube_watertight_along_path() -> None:
    cp = [[0, 0, 0], [0, 0, 20], [25, 12, 15], [30, 4, 6]]
    tube = sdf.bezier_sweep(CIRCLE, cp, splinesteps=48)
    f = _field(tube)
    # every point strictly along the centerline (excluding the exact end points, which sit on the
    # end caps) must be inside -- i.e. the sweep is a single gap-free solid following the path
    pts = Bezier(cp).curve(splinesteps=200)[5:-5]
    assert all(f(px, py, pz) < 0 for px, py, pz in pts)


@pytest.mark.usefixtures("numeric_lv")
def test_twist_keeps_it_a_solid() -> None:
    square = [[-2, -2], [2, -2], [2, 2], [-2, 2]]
    tube = sdf.path_sweep(square, [[0, 0, z] for z in np.linspace(0, 20, 30)], twist=90)
    f = _field(tube)
    assert f(0, 0, 10) < 0  # still solid along the axis with a 90-degree twist
    # the mid station is rotated ~45 degrees, so a corner reaches ~2*sqrt2; the mesh domain must
    # include it (regression: bounds were computed from the un-rotated profile bbox and clipped it)
    corner = 2 * math.sqrt(2)
    assert tube.mx[0] >= corner - 0.05
    assert tube.mn[0] <= -corner + 0.05
    assert f(2.7, 0, 10) < 0
    assert tube.mx[0] >= 2.7  # solid material there, and inside the domain


@pytest.mark.usefixtures("numeric_lv")
def test_concave_profile_notch_is_carved() -> None:
    # An L-shaped (concave) profile: the removed top-right quadrant must read OUTSIDE, while both
    # arms read inside -- i.e. the sweep honours the concavity (via _polygon_sdf_xy), not just a hull.
    profile = [[0, 0], [4, 0], [4, 2], [2, 2], [2, 4], [0, 4]]
    path = [[0, 0, z] for z in np.linspace(0, 10, 30)]
    tube = sdf.path_sweep(profile, path)
    uv = _frame_probe(tube, path)
    assert uv(1, 1) < 0
    assert uv(3, 1) < 0
    assert uv(1, 3) < 0  # both solid arms
    assert uv(2.5, 2.5) > 0
    assert uv(3.5, 3.5) > 0  # the concave notch is empty

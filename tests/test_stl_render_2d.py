# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# mypy: ignore_errors

"""Real-render tests for 2-D operations that require native bounding-box info.

Each 2-D shape is linear-extruded to a thin slab, exported as STL, and checked
for the correct XY extent.  Skip gracefully when no PythonSCAD binary is found.
"""

import numpy as np
import pytest
from render_stl import find_pythonscad_binary, render_object, stl_metrics

pytestmark = pytest.mark.skipif(
    find_pythonscad_binary() is None,
    reason="no PythonSCAD binary found (set PYTHONSCAD_BIN or install the app)",
)


def _render(tmp_path, expr, name="obj"):
    out = tmp_path / f"{name}.stl"
    res = render_object(expr, out)
    assert res.ok, f"render failed for {name}: {res.error}\n{res.stderr[-600:]}"
    return stl_metrics(out)


# -- fill -------------------------------------------------------------------
def test_fill_preserves_outline(tmp_path):
    m = _render(tmp_path, "(s2.square(40) - s2.circle(radius=8)).fill().linear_extrude(height=1)")
    np.testing.assert_allclose(m.size[:2], [40, 40], atol=1.0)


def test_fill_of_bowtie(tmp_path):
    m = _render(tmp_path, "Path2D([[0,0],[20,20],[20,0],[0,20]]).fill().linear_extrude(height=1)")
    np.testing.assert_allclose(m.size[:2], [20, 20], atol=1.0)


# -- hull -------------------------------------------------------------------
def test_hull_spans_both_children(tmp_path):
    m = _render(tmp_path, "s2.circle(radius=5).hull(s2.circle(radius=5).right(30)).linear_extrude(height=1)")
    np.testing.assert_allclose(m.size[:2], [40, 10], atol=1.0)


def test_hull_of_concave_shape_fills_notches(tmp_path):
    m = _render(tmp_path, "s2.star(tips=5, radius=20, inner_radius=8).hull().linear_extrude(height=1)")
    np.testing.assert_allclose(m.size[:2], [38, 38], atol=5.0)


# -- offset -----------------------------------------------------------------
def test_offset_grows_the_outline(tmp_path):
    m = _render(tmp_path, "s2.square(10).offset(delta=2).linear_extrude(height=1)")
    np.testing.assert_allclose(m.size[:2], [14, 14], atol=1.0)

    m2 = _render(tmp_path, "s2.square(10).offset(radius=2).linear_extrude(height=1)")
    np.testing.assert_allclose(m2.size[:2], [14, 14], atol=1.0)


def test_round2d_and_shell2d_through_wrapper(tmp_path):
    m = _render(tmp_path, "round2d(radius=2, children=s2.square(20)).linear_extrude(height=1)")
    np.testing.assert_allclose(m.size[:2], [20, 20], atol=1.0)

    m2 = _render(tmp_path, "shell2d(thickness=2, children=s2.square(20)).linear_extrude(height=1)")
    np.testing.assert_allclose(m2.size[:2], [24, 24], atol=1.0)


# -- linear_extrude ---------------------------------------------------------
def test_linear_extrude_height_is_z_extent(tmp_path):
    m = _render(tmp_path, "s2.square([10, 4]).linear_extrude(height=5)")
    np.testing.assert_allclose(m.size, [10, 4, 5], atol=1.0)


# -- bounds after translate -------------------------------------------------
def test_bounds_follow_a_translate(tmp_path):
    m = _render(tmp_path, "s2.square(10).right(5).linear_extrude(height=1)")
    center = (m.bbmin + m.bbmax) / 2
    np.testing.assert_allclose(center[0], 5.0, atol=1.0)
    np.testing.assert_allclose(m.size[:2], [10, 10], atol=1.0)


# -- region fill ------------------------------------------------------------
def test_region_fill_drops_the_hole(tmp_path):
    m = _render(
        tmp_path,
        "Region.with_holes([[0,0],[20,0],[20,10],[0,10]], [[5,3],[15,3],[15,7],[5,7]]).fill().linear_extrude(height=1)",
    )
    np.testing.assert_allclose(m.size[:2], [20, 10], atol=1.0)


# -- projection ------------------------------------------------------------
def test_projection_is_the_xy_footprint(tmp_path):
    m = _render(tmp_path, "s3.cuboid([30, 20, 10]).projection().linear_extrude(height=1)")
    np.testing.assert_allclose(m.size[:2], [30, 20], atol=1.0)


# -- minkowski --------------------------------------------------------------
def test_minkowski_grows_bounding_box(tmp_path):
    m = _render(tmp_path, "s2.square([10, 10], center=True).minkowski(s2.circle(radius=3)).linear_extrude(height=1)")
    np.testing.assert_allclose(m.size[:2], [16, 16], atol=1.0)


# -- roof (native op) -------------------------------------------------------
def test_roof_produces_3d_solid(tmp_path):
    m = _render(tmp_path, "roof(s2.square([20, 10]).shape)")
    assert m.ntris > 0
    assert m.volume > 0

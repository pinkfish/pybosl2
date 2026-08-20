# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# mypy: ignore_errors

"""Real-render STL tests: build pybosl2 objects in the real PythonSCAD app, export them to STL,
and verify the produced mesh's geometry (bounding box, volume, triangle count, watertightness).

These need the PythonSCAD app; they SKIP when no binary is found (set PYTHONSCAD_BIN). Run just
these with: ``PYTHONSCAD_BIN=/path/to/PythonSCAD python3 -m pytest pybosl2/tests/test_stl_render.py``.
"""

import math
import os
from pathlib import Path

import numpy as np
import pytest
from render_stl import find_pythonscad_binary, golden_ok, parse_stl, render_object, stl_metrics

from pybosl2.parts.enums import ScrewDriveType, ScrewHeadType

pytestmark = pytest.mark.skipif(
    find_pythonscad_binary() is None,
    reason="no PythonSCAD binary found (set PYTHONSCAD_BIN or install the app)",
)

GOLDEN_DIR = Path(__file__).resolve().parent / "golden_stls"

CIRCLE = "[[2*math.cos(t), 2*math.sin(t)] for t in np.linspace(0, 2*math.pi, 16, endpoint=False)]"
PATCH = (
    "[[[-50,-50,0],[-16,-50,20],[16,-50,-20],[50,-50,0]],"
    " [[-50,-16,20],[-16,-16,20],[16,-16,-20],[50,-16,20]],"
    " [[-50,16,20],[-16,16,-20],[16,16,20],[50,16,20]],"
    " [[-50,50,0],[-16,50,-20],[16,50,20],[50,50,0]]]"
)


def _render(tmp_path, expr, setup="", name="obj"):
    out = tmp_path / f"{name}.stl"
    res = render_object(expr, out, setup=setup)
    assert res.ok, f"render failed for {name}: {res.error}\n{res.stderr[-600:]}"
    return stl_metrics(out)


def _render_golden(tmp_path, expr, name, setup="", *, update=False):
    """Render *expr* to a binary STL and compare its geometry against a
    golden STL in ``tests/golden_stls/<name>.stl``.

    On the first run (or when ``UPDATE_GOLDENS=1`` is set in the
    environment) the rendered STL is written as the new golden.  On
    subsequent runs the normalized geometry hash of the fresh render is
    compared against the golden; the assertion fails when the shape has
    changed beyond floating-point tolerance.
    """
    out = tmp_path / f"{name}.stl"
    res = render_object(expr, out, setup=setup, export_format="binstl")
    assert res.ok, f"render failed for {name}: {res.error}\n{res.stderr[-600:]}"
    golden = GOLDEN_DIR / f"{name}.stl"
    _update = update or os.environ.get("UPDATE_GOLDENS") == "1"
    if _update:
        golden.write_bytes(out.read_bytes())
    metrics = stl_metrics(out)
    assert golden_ok(out, golden), (
        f"golden mismatch for {name}: {golden} differs from rendered STL "
        f"(size={metrics.size}, ntris={metrics.ntris}, vol={metrics.volume:.3f})"
    )
    return metrics


# -- primitive solids with exactly known geometry -----------------------------------------


def test_cuboid(tmp_path):
    m = _render(tmp_path, "s3.cuboid([40, 30, 20])", name="cuboid")
    np.testing.assert_allclose(m.size, [40, 30, 20], atol=1e-3)
    assert math.isclose(m.volume, 40 * 30 * 20, rel_tol=1e-4)
    assert m.ntris == 12  # a box is two triangles per face
    assert m.watertight


def test_prismoid_frustum_volume(tmp_path):
    # frustum volume = h/3 * (A1 + A2 + sqrt(A1*A2)) = 30/3*(1600+400+800) = 28000
    m = _render(tmp_path, "s3.prismoid([40, 40], [20, 20], height=30)", name="prismoid")
    np.testing.assert_allclose(m.size, [40, 40, 30], atol=1e-2)
    assert math.isclose(m.volume, 28000.0, rel_tol=1e-3)
    assert m.watertight


def test_cylinder_volume(tmp_path):
    # true volume pi*r^2*height = pi*25*20 ~= 1570.8; a 64-gon inscribes slightly under it
    true_vol = math.pi * 25 * 20
    m = _render(tmp_path, "s3.cyl(height=20, radius=5, fn=64)", name="cyl")
    assert math.isclose(m.size[2], 20.0, abs_tol=1e-3)
    np.testing.assert_allclose(m.size[:2], [10, 10], atol=0.1)
    assert 0.99 * true_vol < m.volume < true_vol
    assert m.watertight


def test_sphere_volume(tmp_path):
    true_vol = 4 / 3 * math.pi * 10**3
    m = _render(tmp_path, "s3.sphere(radius=10, fn=64)", name="sphere")
    np.testing.assert_allclose(m.size, [20, 20, 20], atol=0.4)
    assert 0.95 * true_vol < m.volume < true_vol  # faceting under-fills the true sphere
    assert m.watertight


def test_regular_prism_height_and_solid(tmp_path):
    m = _render(tmp_path, "s3.regular_prism(6, height=10, radius=10)", name="hexprism")
    assert math.isclose(m.size[2], 10.0, abs_tol=1e-3)
    assert m.volume > 0
    assert m.watertight


def test_tube_is_hollow(tmp_path):
    # a tube encloses less than the solid outer cylinder of the same radius/height
    m = _render(
        tmp_path,
        "s3.tube(height=10, outer_radius=10, inner_radius=6, fn=48)",
        name="tube",
    )
    assert math.isclose(m.size[2], 10.0, abs_tol=1e-3)
    solid_outer = math.pi * 10**2 * 10
    assert 0 < m.volume < solid_outer
    assert m.watertight


# -- VNF-based solids (surfaces, sheets, sweeps) ------------------------------------------


def test_bezier_patch_sheet(tmp_path):
    m = _render(
        tmp_path,
        f"BezierPatch({PATCH}).sheet([0, -6], splinesteps=8).polyhedron()",
        name="sheet",
    )
    assert m.ntris > 0
    assert m.volume > 0


def test_bezier_sweep_tube(tmp_path):
    setup = f"shape = {CIRCLE}\nbez = [[0,0,5],[0,0,10],[15,7,9],[17,2,4]]\n"
    m = _render(
        tmp_path,
        "Bezier(bez).sweep(shape, splinesteps=10).polyhedron()",
        setup=setup,
        name="beziersweep",
    )
    assert m.ntris > 0
    assert m.volume > 0
    assert m.watertight  # a capped tube is a closed solid


def test_sdf_path_sweep_tube_volume(tmp_path):
    # The libfive/SDF-backend sweep: a 32-gon circle (r=2) swept straight along z 0..30 meshes to a
    # watertight prism whose volume matches the exact 32-gon x height (the sign/zero-set is correct).
    setup = (
        "from pybosl2.sdf.shapes3d import path_sweep\n"
        "circle = [[2*math.cos(t), 2*math.sin(t)] for t in np.linspace(0, 2*math.pi, 32, endpoint=False)]\n"
        "pathz = [[0, 0, z] for z in np.linspace(0, 30, 60)]\n"
    )
    m = _render(tmp_path, "path_sweep(circle, pathz, res=16)", setup=setup, name="sdfsweep")
    assert m.watertight
    assert abs(m.size[0] - 4) < 0.1
    assert abs(m.size[1] - 4) < 0.1
    assert abs(m.size[2] - 30) < 0.1
    expected = 0.5 * 32 * 2**2 * math.sin(2 * math.pi / 32) * 30  # 32-gon prism
    assert abs(m.volume - expected) < 0.02 * expected


def test_sdf_concave_profile_sweep_volume(tmp_path):
    # A concave (L-shaped) profile swept straight: meshes watertight with the notch carved out, so
    # the volume equals the L's area (8x8 minus a 5x5 corner = 39) times the height.
    setup = (
        "from pybosl2.sdf.shapes3d import path_sweep\n"
        "L = [[0,0],[8,0],[8,3],[3,3],[3,8],[0,8]]\n"
        "pathz = [[0, 0, z] for z in np.linspace(0, 20, 40)]\n"
    )
    m = _render(tmp_path, "path_sweep(L, pathz, res=16)", setup=setup, name="sdfconcavesweep")
    assert m.watertight
    assert abs(m.volume - 39 * 20) < 0.02 * (39 * 20)


def test_sdf_bezier_sweep_watertight(tmp_path):
    # A profile swept along a curved 3-D Bezier as a libfive SDF meshes to a closed solid.
    setup = (
        "from pybosl2.sdf.shapes3d import bezier_sweep\n"
        "circle = [[2*math.cos(t), 2*math.sin(t)] for t in np.linspace(0, 2*math.pi, 24, endpoint=False)]\n"
    )
    m = _render(
        tmp_path,
        "bezier_sweep(circle, [[0,0,0],[0,0,20],[25,12,15],[30,4,6]], res=14)",
        setup=setup,
        name="sdfbeziersweep",
    )
    assert m.ntris > 0
    assert m.volume > 0
    assert m.watertight


def test_sweep(tmp_path):
    setup = f"shape = {CIRCLE}\nbezpath = [[0,0,0],[10,0,0],[10,10,0],[10,10,10],[10,20,10],[0,20,10],[0,20,20]]\n"
    m = _render(
        tmp_path,
        "Bezier(bezpath).sweep(shape, splinesteps=8, n_degree=3).polyhedron()",
        setup=setup,
        name="bezpathsweep",
    )
    assert m.ntris > 0
    assert m.volume > 0


def test_path_sweep_closed_torus(tmp_path):
    setup = (
        "shape = [[math.cos(t)+5, math.sin(t)] for t in np.linspace(0, 2*math.pi, 12, endpoint=False)]\n"
        "circ = [[math.cos(t)*20, math.sin(t)*20, 0] for t in np.linspace(0, 2*math.pi, 32, endpoint=False)]\n"
    )
    m = _render(
        tmp_path,
        "Path3D(circ).path_sweep(shape, closed=True).polyhedron()",
        setup=setup,
        name="torus",
    )
    assert m.ntris > 0
    assert m.volume > 0
    assert m.watertight  # a closed loop sweep has no ends


def test_two_objects_differ(tmp_path):
    # a sanity guard that the pipeline actually reflects the object: a bigger box has more volume
    small = _render(tmp_path, "s3.cuboid([10, 10, 10])", name="small")
    big = _render(tmp_path, "s3.cuboid([20, 20, 20])", name="big")
    assert big.volume > small.volume * 7  # 8x the volume


# -- the wider skin.scad surface generators -----------------------------------------------


def test_skin_lofts_two_profiles(tmp_path):
    setup = (
        "from pybosl2.enums import SkinMethod\n"
        "circle = [[6*math.cos(t), 6*math.sin(t)] for t in np.linspace(0, 2*math.pi, 24, endpoint=False)]\n"
        "square = [[-8, -8], [8, -8], [8, 8], [-8, 8]]\n"
    )
    m = _render(
        tmp_path,
        "VNF.from_skin([circle, square], slices=16, method=SkinMethod.REINDEX, z=[0, 25]).polyhedron()",
        setup=setup,
        name="skin",
    )
    assert m.ntris > 0
    assert m.volume > 0
    assert math.isclose(m.size[2], 25.0, abs_tol=1e-3)


def test_linear_sweep_twist_scale(tmp_path):
    setup = "square = [[-10, -10], [10, -10], [10, 10], [-10, 10]]\n"
    m = _render(
        tmp_path,
        "Path2D(square).linear_sweep(height=40, twist=120, scale=0.4).polyhedron()",
        setup=setup,
        name="linsweep",
    )
    assert m.volume > 0
    assert math.isclose(m.size[2], 40.0, abs_tol=1e-3)


def test_linear_sweep_plain_volume(tmp_path):
    setup = "square = [[-10, -10], [10, -10], [10, 10], [-10, 10]]\n"
    m = _render(
        tmp_path,
        "Path2D(square).linear_sweep(height=5).polyhedron()",
        setup=setup,
        name="linplain",
    )
    assert math.isclose(m.volume, 20 * 20 * 5, rel_tol=1e-3)  # 2000
    assert m.watertight


def test_rotate_sweep_full_revolution(tmp_path):
    setup = "profile = [[4, -10], [12, -10], [12, -6], [7, -2], [7, 2], [12, 6], [12, 10], [4, 10]]\n"
    m = _render(tmp_path, "Path(profile).rotate_sweep(angle=360).polyhedron()", setup=setup, name="revolve")
    assert m.volume > 0
    np.testing.assert_allclose(m.size[:2], [24, 24], atol=0.5)  # diameter ~ 2 * xmax(12)


def test_rotate_sweep_partial(tmp_path):
    setup = "profile = [[4, -10], [12, -10], [12, 10], [4, 10]]\n"
    m = _render(
        tmp_path,
        "Path2D(profile).rotate_sweep(angle=270).polyhedron()",
        setup=setup,
        name="revolve270",
    )
    assert m.volume > 0
    assert m.watertight  # a partial revolution is end-capped into a closed solid


def test_spiral_sweep_coil(tmp_path):
    setup = "section = [[-1.2, -1.2], [1.2, -1.2], [1.2, 1.2], [-1.2, 1.2]]\n"
    m = _render(
        tmp_path,
        "Path2D(section).spiral_sweep(height=40, radius=12, turns=5).polyhedron()",
        setup=setup,
        name="coil",
    )
    assert m.ntris > 0
    assert m.volume > 0
    assert math.isclose(m.size[2], 40 + 2.4, abs_tol=1.0)  # height + a section's worth of overhang


def test_path_sweep2d_wavy_bar(tmp_path):
    setup = "shape = [[-2, -2], [2, -2], [2, 2], [-2, 2]]\npath = [[t, 8*math.sin(t/12)] for t in range(0, 90, 3)]\n"
    m = _render(tmp_path, "Path(path).path_sweep2d(shape).polyhedron()", setup=setup, name="psweep2d")
    assert m.ntris > 0
    assert m.volume > 0
    assert m.watertight  # a capped open sweep is a closed solid


def test_rot_resample_then_sweep(tmp_path):
    setup = (
        "import pybosl2.skin\n"
        "sq = [[-1.5, -1.5], [1.5, -1.5], [1.5, 1.5], [-1.5, 1.5]]\n"
        "curve = [[0, 0, 0], [20, 0, 8], [20, 20, 16], [0, 20, 24]]\n"
        "tl = pybosl2.skin.rot_resample(Path3D(curve).path_sweep(Path2D(sq), transforms=True), num_copies=30)\n"
    )
    m = _render(tmp_path, "Path2D(sq).sweep(tl).polyhedron()", setup=setup, name="rotresample")
    assert m.ntris > 0
    assert m.volume > 0


# -- newly-ported shapes ------------------------------------------------------------------


def test_squircle_extruded(tmp_path):
    m = _render(
        tmp_path,
        "s2.squircle(40, squareness=0.7).linear_extrude(height=5)",
        name="squircle",
    )
    assert m.volume > 0
    np.testing.assert_allclose(m.size[:2], [40, 40], atol=0.5)
    assert math.isclose(m.size[2], 5.0, abs_tol=1e-3)


def test_keyhole_extruded(tmp_path):
    m = _render(
        tmp_path,
        "s2.keyhole(length=25, radius1=4, radius2=9, shoulder_radius=2).linear_extrude(height=4)",
        name="keyhole",
    )
    assert m.volume > 0
    assert m.watertight


def test_ring_extruded(tmp_path):
    m = _render(
        tmp_path,
        "s2.ring(radius=20, ring_width=4).linear_extrude(height=5)",
        name="ring",
    )
    assert m.volume > 0
    np.testing.assert_allclose(m.size[:2], [48, 48], atol=1.0)  # outer diameter ~ 2*(20+4)


def test_plot3d_surface_solid(tmp_path):
    setup = (
        "xs = list(range(-30, 31, 3)); ys = list(range(-30, 31, 3))\n"
        "f = lambda x, y: 6 * math.cos(math.hypot(x, y) / 6)\n"
    )
    m = _render(tmp_path, "s3.plot3d(f, xs, ys)", setup=setup, name="plot3d")
    assert m.ntris > 0
    assert m.volume > 0


def test_fillet_subtracts_a_concave_edge(tmp_path):
    # subtracting a fillet mask from a box rounds one edge inward -> less volume than the box
    box = 30 * 30 * 20
    m = _render(
        tmp_path,
        "(s3.cuboid([30, 30, 20]) - s3.fillet(length=20, radius=6).right(15).forward(15))",
        name="fillet",
    )
    np.testing.assert_allclose(m.size, [30, 30, 20], atol=1e-2)
    assert 0 < m.volume < box  # material removed at the edge
    assert m.watertight


def test_plot_revolution_makes_a_revolved_solid(tmp_path):
    setup = (
        "f = lambda a, z: 3 * math.sin(math.radians(4 * a)) * (z / 30)\n"
        "angle = list(range(0, 361, 6)); zs = list(range(0, 31, 2))\n"
    )
    m = _render(
        tmp_path,
        "s3.plot_revolution(f, angle=angle, z=zs, radius1=12, radius2=8)",
        setup=setup,
        name="plotrev",
    )
    assert m.ntris > 0
    assert m.volume > 0
    assert math.isclose(m.size[2], 30.0, abs_tol=1.0)


def test_textured_tile_heightfield(tmp_path):
    setup = "bump = [[0, 0, 0], [0, 1, 0], [0, 0, 0]]\n"
    m = _render(
        tmp_path,
        "s3.textured_tile(bump, size=[40, 40], tex_reps=[4, 4], tex_depth=3)",
        setup=setup,
        name="texttile",
    )
    assert m.volume > 0
    np.testing.assert_allclose(m.size[:2], [40, 40], atol=1e-2)
    assert m.watertight


def test_attach_with_bbox_override(tmp_path):
    # override the parent's bbox so the child attaches to a TOP that is higher than the real box
    m = _render(
        tmp_path,
        "s3.cuboid([30, 30, 20]).attach(TOP, s3.cuboid([10, 10, 10]), bbox=[[-15,-15,-10],[15,15,20]])",
        name="attachbbox",
    )
    # child bottom lands on z=20 (the overriding TOP), so the union reaches z=30 while the
    # real parent still tops out at z=10 -> a gap, but total height is 10..30 span for child + parent
    assert math.isclose(m.bbmax[2], 30.0, abs_tol=0.5)


# -- attachment methods (use the native bbox, no size passed) -----------------------------


def test_orient_rotates_up_to_direction(tmp_path):
    # UP -> RIGHT swaps the z (20) and x (40) extents
    m = _render(tmp_path, "s3.cuboid([40, 30, 20]).orient(RIGHT)", name="orient")
    np.testing.assert_allclose(m.size, [20, 30, 40], atol=1e-3)


def test_reorient_anchor_moves_face_to_origin(tmp_path):
    m = _render(tmp_path, "s3.cuboid([40, 30, 20]).reorient(anchor=TOP)", name="reorient")
    np.testing.assert_allclose(m.size, [40, 30, 20], atol=1e-3)
    assert math.isclose(m.bbmax[2], 0.0, abs_tol=1e-3)  # top face on z=0


def test_reanchor_puts_anchor_at_origin(tmp_path):
    m = _render(tmp_path, "s3.cuboid([40, 30, 20]).reanchor(BOTTOM)", name="reanchor")
    assert math.isclose(m.bbmin[2], 0.0, abs_tol=1e-3)  # bottom face on z=0


def test_attach_places_child_on_face(tmp_path):
    # a small cube attached to the TOP of a big one -> the combined bbox is taller
    m = _render(
        tmp_path,
        "s3.cuboid([30, 30, 20]).attach(TOP, s3.cuboid([10, 10, 10]))",
        name="attach",
    )
    assert m.volume > 30 * 30 * 20  # bigger than the parent alone
    assert math.isclose(m.size[2], 30.0, abs_tol=0.5)  # 20 + 10 stacked


# -- drawing.scad renderers ---------------------------------------------------------------


def test_stroke_2d_arc_ribbon(tmp_path):
    # a stroked arc extruded into a curved wall -> a real thin solid
    m = _render(
        tmp_path,
        "arc(radius=30, angle=200).stroke(width=4).linear_extrude(height=3)",
        name="stroke2d",
    )
    assert m.volume > 0
    assert math.isclose(m.size[2], 3.0, abs_tol=1e-2)
    # the ribbon spans roughly the arc's diameter but is only ~4 wide, so it is not a full disk
    assert m.volume < math.pi * 32**2 * 3


def test_stroke_2d_closed_square(tmp_path):
    setup = "sq = Path([[0, 0], [40, 0], [40, 40], [0, 40]], closed=True)\n"
    m = _render(
        tmp_path,
        "sq.stroke(width=3, joints='round').linear_extrude(height=2)",
        setup=setup,
        name="strokesq",
    )
    assert m.volume > 0
    np.testing.assert_allclose(m.size[:2], [43, 43], atol=1.0)  # 40 + width, round joints


def test_stroke_3d_helix_tube(tmp_path):
    m = _render(
        tmp_path,
        "Path3D.helix(turns=2, height=40, radius=15).stroke(width=4)",
        name="stroke3d",
    )
    assert m.ntris > 0
    assert m.volume > 0
    assert math.isclose(m.size[2], 40 + 4, abs_tol=2.0)  # helix height + tube diameter


def test_dashed_stroke_makes_multiple_solids(tmp_path):
    setup = (
        "dashes = arc(radius=30, angle=360).dashed_stroke(dashpat=[8, 5], closed=True)\n"
        "solid = dashes[0].stroke(width=2)\n"
        "for d in dashes[1:]:\n"
        "    solid = solid | d.stroke(width=2)\n"
        "obj0 = solid.linear_extrude(height=2)\n"
    )
    m = _render(tmp_path, "obj0", setup=setup, name="dashed")
    assert m.volume > 0
    # dashes leave gaps, so total volume is well under a solid ring of the same width
    assert m.volume < math.pi * (32**2 - 28**2) * 2


def test_catenary_stroke(tmp_path):
    m = _render(
        tmp_path,
        "Path2D.catenary(width=80, droop=30).stroke(width=3).linear_extrude(height=2)",
        name="catenary",
    )
    assert m.volume > 0
    np.testing.assert_allclose(m.size[0], 80, atol=3.0)  # spans the requested width


def test_turtle_stroke(tmp_path):
    setup = (
        "from pybosl2.turtle import TurtleCommand, TurtleCommandType as Tct\n"
        "path = turtle2d([TurtleCommand(Tct.MOVE, size=40), TurtleCommand(Tct.ARCLEFT, radius=8),"
        "TurtleCommand(Tct.MOVE, size=40), TurtleCommand(Tct.ARCLEFT, radius=8),"
        "TurtleCommand(Tct.MOVE, size=40), TurtleCommand(Tct.ARCLEFT, radius=8),"
        "TurtleCommand(Tct.MOVE, size=40), TurtleCommand(Tct.ARCLEFT, radius=8)]).points()\n"
    )
    m = _render(
        tmp_path,
        "path.stroke(width=3, closed=True).linear_extrude(height=2)",
        setup=setup,
        name="turtle",
    )
    assert m.volume > 0


# -- fancy endcaps generated directly -----------------------------------------------------


def test_stroke_arrow_endcap_2d(tmp_path):
    # an arrow endcap fans out wider than the 3-wide line: bbox in Y exceeds the line width
    m = _render(
        tmp_path,
        "Path2D([[0, 0], [20, 0], [40, 0]]).stroke(width=3, endcaps='arrow').linear_extrude(height=2)",
        name="arrow2d",
    )
    assert m.volume > 0
    assert m.size[1] >= 3  # stroke width fills the Y extent
    assert m.bbmin[0] < 0.5  # arrow endcap sits near the first point, stroke width may extend the bbox
    assert m.bbmax[0] > 38  # arrow endcap at far end of the path, near 40mm


def test_stroke_diamond_endcap_straddles_end(tmp_path):
    # a diamond endcap is centred on the endpoint, so it overshoots both ends
    m = _render(
        tmp_path,
        "Path2D([[0, 0], [20, 0], [40, 0]]).stroke(width=3, endcaps='diamond').linear_extrude(height=2)",
        name="diamond2d",
    )
    assert m.bbmin[0] < -1.0  # overshoots the start
    assert m.bbmax[0] > 41.0  # overshoots the end


def test_stroke_tail_and_arrow_mixed(tmp_path):
    m = _render(
        tmp_path,
        "Path2D([[0, 0], [20, 0], [40, 0]]).stroke(width=3, endcap1='tail', endcap2='arrow').linear_extrude(height=2)",
        name="tailarrow",
    )
    assert m.volume > 0
    assert m.bbmin[0] < 0  # the tail extends behind the start


def test_stroke_arrow_endcap_3d_is_a_cone(tmp_path):
    # the 3-D arrow endcap is a revolved cone: it is thicker across than the 4mm tube
    m = _render(
        tmp_path,
        "Path3D([[0, 0, 0], [20, 0, 0], [40, 0, 0]]).stroke(width=4, endcaps='arrow')",
        setup="from pybosl2._backend import set_default_backend; set_default_backend('csg')\n",
        name="arrow3d",
    )
    assert m.ntris > 0
    assert m.volume > 0
    assert m.size[1] > 3.5
    assert m.size[2] > 3.5  # 3-D stroke with cone endcap is wider than the tube cross-section


# -- Path3D transforms feed the renderers -------------------------------------------------


def test_path3d_rotated_helix_stroke(tmp_path):
    # rotating the helix about X swaps its Z-height into -Y; the tube follows
    setup = "coil = Path3D.helix(turns=2, height=40, radius=12).rotate(90, [1, 0, 0])\n"
    m = _render(tmp_path, "coil.stroke(width=3)", setup=setup, name="helixrot")
    assert m.volume > 0
    # after a 90-deg X rotation the ~40 tall extent now lies along Y (plus tube thickness)
    assert m.size[1] > 40


def test_path3d_resampled_helix_stroke(tmp_path):
    setup = "coil = Path3D.helix(turns=3, height=60, radius=20).resample(num_copies=150)\n"
    m = _render(tmp_path, "coil.stroke(width=4)", setup=setup, name="helixresample")
    assert m.ntris > 0
    assert m.volume > 0
    assert math.isclose(m.size[2], 60 + 4, abs_tol=3.0)  # helix height + tube diameter


def test_path3d_translate_moves_stroke(tmp_path):
    setup = "coil = Path3D.helix(turns=1.5, height=30, radius=10).up(100)\n"
    m = _render(tmp_path, "coil.stroke(width=3)", setup=setup, name="helixup")
    assert m.bbmin[2] > 90  # lifted 100mm up


# -- distributors: solid copies -----------------------------------------------------------


def test_grid_copies_span_and_volume(tmp_path):
    # a 3x3 grid of 10mm cubes at 30mm spacing -> outer span 2*30 + 10 = 70, 9x the volume
    m = _render(
        tmp_path,
        "s3.cuboid([10, 10, 10]).grid_copies(num_copies=[3, 3], spacing=30)",
        name="grid",
    )
    np.testing.assert_allclose(m.size[:2], [70, 70], atol=0.5)
    assert math.isclose(m.volume, 9 * 1000, rel_tol=1e-3)
    assert m.watertight


def test_line_copies_volume(tmp_path):
    m = _render(tmp_path, "s3.cuboid([6, 6, 6]).xcopies(20, num_copies=4)", name="linecopies")
    assert math.isclose(m.volume, 4 * 6**3, rel_tol=1e-3)
    np.testing.assert_allclose(m.size[0], 3 * 20 + 6, atol=0.5)  # span of 4 copies


def test_zrot_copies_ring(tmp_path):
    # 6 cubes in a ring of radius 30 -> spread across a ~60mm-diameter footprint in X and Y
    m = _render(tmp_path, "s3.cuboid([6, 6, 6]).zrot_copies(num_copies=6, radius=30)", name="ring")
    assert m.volume > 5 * 6**3  # roughly 6 cubes (minus any tiny overlap)
    assert 55 < m.size[0] < 70
    assert 55 < m.size[1] < 70
    assert math.isclose(m.size[2], 6.0, abs_tol=0.2)  # ring stays flat in Z


def test_xflip_copy_mirrors(tmp_path):
    # an off-center cube flipped across X=0 -> symmetric pair straddling the origin
    m = _render(tmp_path, "s3.cuboid([8, 8, 8]).right(20).xflip_copy()", name="xflip")
    assert math.isclose(m.volume, 2 * 8**3, rel_tol=1e-3)
    np.testing.assert_allclose(m.bbmin[0], -24, atol=0.5)
    np.testing.assert_allclose(m.bbmax[0], 24, atol=0.5)


def test_arc_copies_solid(tmp_path):
    m = _render(
        tmp_path,
        "s3.cuboid([5, 5, 5]).arc_copies(num_copies=8, radius=25, sa=0, ea=180)",
        name="arccopies",
    )
    assert m.volume > 0
    assert m.watertight


def test_distribute_list_of_children(tmp_path):
    setup = "parts = [s3.cuboid([10, 10, 10]), s3.sphere(radius=8), s3.cyl(height=14, radius=5)]\n"
    m = _render(tmp_path, "xdistribute(parts, spacing=8)", setup=setup, name="distribute")
    assert m.volume > 0
    assert m.size[0] > 30  # spread out along X


def test_path_copies_along_path(tmp_path):
    setup = "route = Path([[0, 0], [40, 0], [40, 40]], closed=False)\n"
    m = _render(
        tmp_path,
        "s3.cuboid([4, 8, 4]).path_copies(route, num_copies=6)",
        setup=setup,
        name="pathcopies",
    )
    assert m.volume > 0
    # copies span the L-shaped route: roughly 0..40 in X and 0..40 in Y
    assert m.size[0] > 35
    assert m.size[1] > 35


# -- colour operators (geometry survives; colour is a display attribute) -------------------


def test_color_name_keeps_geometry(tmp_path):
    m = _render(tmp_path, "s3.cuboid([10, 10, 10]).color(Color('red'))", name="colorname")
    assert math.isclose(m.volume, 1000, rel_tol=1e-4)
    assert m.watertight


def test_hsv_and_hsl_methods_render(tmp_path):
    a = _render(tmp_path, "s3.cuboid([10, 10, 10]).hsv(200, 0.8, 0.9)", name="hsv")
    b = _render(tmp_path, "s3.cuboid([10, 10, 10]).hsl(120, 0.6, 0.5, 0.7)", name="hsl")
    assert math.isclose(a.volume, 1000, rel_tol=1e-4)
    assert math.isclose(b.volume, 1000, rel_tol=1e-4)


def test_recolor_highlight_ghost_render(tmp_path):
    for expr, name in (
        ("s3.cuboid([10, 10, 10]).recolor(Color('green'))", "recolor"),
        ("s3.cuboid([10, 10, 10]).highlight()", "highlight"),
        ("s3.cuboid([10, 10, 10]).ghost()", "ghost"),
    ):
        m = _render(tmp_path, expr, name=name)
        assert math.isclose(m.volume, 1000, rel_tol=1e-4)


def test_rainbow_colors_a_list(tmp_path):
    # rainbow returns a list of coloured solids; union them and check the combined geometry
    setup = (
        "parts = [s3.cuboid([6, 6, 6]).right(i * 10) for i in range(4)]\n"
        "coloured = rainbow(parts)\n"
        "obj0 = coloured[0]\n"
        "for piece in coloured[1:]:\n"
        "    obj0 = obj0 | piece\n"
    )
    m = _render(tmp_path, "obj0", setup=setup, name="rainbow")
    assert math.isclose(m.volume, 4 * 6**3, rel_tol=1e-3)
    np.testing.assert_allclose(m.size[0], 3 * 10 + 6, atol=0.5)  # spread of 4 cubes


def test_recolor_child_keeps_its_own_color(tmp_path):
    # a coloured child unioned into a recoloured parent still contributes its geometry
    setup = (
        "part = s3.cuboid([20, 20, 10]).color(Color('blue')).attach(TOP, s3.cuboid([8, 8, 8]).color(Color('red')))\n"
    )
    m = _render(tmp_path, "part.recolor(Color('green'))", setup=setup, name="recolorchild")
    assert m.volume > 20 * 20 * 10  # parent + attached child
    assert math.isclose(m.size[2], 18.0, abs_tol=0.5)


# -- partitions: planar cuts and interlocking splits --------------------------------------


def test_axis_halves_keep_exactly_half(tmp_path):
    full = 40 * 30 * 20
    left = _render(tmp_path, "s3.cuboid([40, 30, 20]).left_half()", name="lefthalf")
    top = _render(tmp_path, "s3.cuboid([40, 30, 20]).top_half()", name="tophalf")
    assert math.isclose(left.volume, full / 2, rel_tol=1e-3)
    np.testing.assert_allclose([left.bbmin[0], left.bbmax[0]], [-20, 0], atol=1e-2)
    assert math.isclose(top.volume, full / 2, rel_tol=1e-3)
    np.testing.assert_allclose([top.bbmin[2], top.bbmax[2]], [0, 10], atol=1e-2)


def test_bottom_half_offset_plane(tmp_path):
    # bottom_half(z=5) keeps z in [-10, 5] -> 15/20 of the box
    m = _render(tmp_path, "s3.cuboid([40, 30, 20]).bottom_half(z=5)", name="bottomz5")
    assert math.isclose(m.volume, 40 * 30 * 15, rel_tol=1e-3)
    np.testing.assert_allclose(m.bbmax[2], 5, atol=1e-2)


def test_half_of_diagonal_plane(tmp_path):
    m = _render(tmp_path, "s3.cuboid([40, 30, 20]).half_of([0, 1, 1])", name="halfdiag")
    assert math.isclose(m.volume, 40 * 30 * 20 / 2, rel_tol=1e-2)  # a plane through the centre halves it
    assert m.watertight


def test_half_of_auto_sizes_from_bbox(tmp_path):
    # no s= given: the mask auto-sizes to the (large) object
    m = _render(tmp_path, "s3.cuboid([200, 120, 60]).right_half()", name="autosize")
    assert math.isclose(m.volume, 200 * 120 * 60 / 2, rel_tol=1e-3)
    np.testing.assert_allclose([m.bbmin[0], m.bbmax[0]], [0, 100], atol=1e-1)


def test_jigsaw_cut_path_half(tmp_path):
    setup = "center = partition_path([60, 'jigsaw', 60], fn=16)\n"
    m = _render(
        tmp_path,
        "s3.cuboid([120, 40, 20]).back_half(cut_path=center)",
        setup=setup,
        name="jigsawcut",
    )
    assert m.volume > 0
    np.testing.assert_allclose(m.size[0], 120, atol=0.5)
    assert m.watertight


def test_partition_two_pieces_conserve_volume(tmp_path):
    # the two dovetail pieces together reconstruct the whole box (spread apart)
    setup = "p = s3.cuboid([60, 40, 20]).partition(spread=12, cutpath='dovetail')\nobj0 = p[0] | p[1]\n"
    m = _render(tmp_path, "obj0", setup=setup, name="partition")
    assert math.isclose(m.volume, 60 * 40 * 20, rel_tol=1e-3)  # volume conserved
    np.testing.assert_allclose(m.size[1], 40 + 12, atol=0.5)  # spread widens Y by 12


def test_partition_single_piece_is_interlocking_half(tmp_path):
    setup = "obj0 = s3.cuboid([60, 40, 20]).partition(spread=0, cutpath='jigsaw', fn=16)[0]\n"
    m = _render(tmp_path, "obj0", setup=setup, name="partback")
    assert math.isclose(m.volume, 60 * 40 * 20 / 2, rel_tol=1e-2)  # each piece is ~half
    assert m.watertight


def test_partition_mask_renders(tmp_path):
    m = _render(
        tmp_path,
        "partition_mask(length=60, w=30, height=20, cutpath='dovetail')",
        name="partmask",
    )
    assert m.volume > 0
    assert math.isclose(m.size[2], 20, abs_tol=1e-2)


# -- miscellaneous.scad extrusions and transforms -----------------------------------------


def test_path_extrude2d_follows_the_path(tmp_path):
    # a moulding (4 wide, 8 tall profile) along an L-path spans the L footprint and stands 8 tall
    setup = "route = Path([[0, 0], [40, 0], [40, 40]], closed=False)\n"
    m = _render(
        tmp_path,
        "route.path_extrude2d(s2.square([4, 8], center=True))",
        setup=setup,
        name="pe2d",
    )
    assert m.volume > 0
    np.testing.assert_allclose(m.size[:2], [42, 42], atol=1.0)  # 40 path + profile width
    assert math.isclose(m.size[2], 8.0, abs_tol=1e-2)  # profile height
    assert m.watertight


def test_path_extrude2d_closed_loop(tmp_path):
    setup = "route = Path([[0, 0], [40, 0], [40, 40], [0, 40]], closed=True)\n"
    m = _render(
        tmp_path,
        "route.path_extrude2d(s2.square([4, 6], center=True), closed=True)",
        setup=setup,
        name="pe2dclosed",
    )
    assert m.volume > 0
    assert math.isclose(m.size[2], 6.0, abs_tol=1e-2)
    assert m.watertight


def test_path_extrude2d_takes_a_factory(tmp_path):
    # the "children" form: a factory produces a fresh profile per placement
    setup = "route = Path([[0, 0], [30, 0]], closed=False)\n"
    m = _render(
        tmp_path,
        "route.path_extrude2d(lambda: s2.circle(radius=4, fn=16))",
        setup=setup,
        name="pe2dfac",
    )
    assert m.volume > 0
    assert math.isclose(m.size[2], 8.0, abs_tol=0.3)  # circle diameter=8 stands 8 tall


def test_path_extrude_3d_path(tmp_path):
    setup = "route = Path3D([[0, 0, 0], [30, 0, 10], [30, 30, 20], [0, 30, 30]], closed=False)\n"
    m = _render(
        tmp_path,
        "route.path_extrude(s2.circle(radius=4, fn=16))",
        setup=setup,
        name="pe3d",
    )
    assert m.volume > 0
    assert m.bbmax[2] > 25  # follows the rising path up to z~30


def test_extrude_from_to_column(tmp_path):
    m = _render(
        tmp_path,
        "extrude_from_to(s2.circle(radius=4, fn=24), [0, 0, 0], [0, 0, 30])",
        name="eft",
    )
    assert math.isclose(m.size[2], 30.0, abs_tol=1e-2)
    np.testing.assert_allclose(m.size[:2], [8, 8], atol=0.2)
    assert m.watertight


def test_extrude_from_to_diagonal_with_twist(tmp_path):
    m = _render(
        tmp_path,
        "extrude_from_to(s2.square([8, 4], center=True), [0, 0, 0], [10, 20, 30], twist=180, scale=2)",
        name="eftdiag",
    )
    assert m.volume > 0
    # the far end sits at [10,20,30]
    np.testing.assert_allclose([m.bbmax[0], m.bbmax[1], m.bbmax[2]], [10, 20, 30], atol=6)


def test_bounding_box_wraps_object(tmp_path):
    m = _render(tmp_path, "s3.sphere(radius=15).bounding_box(excess=2)", name="bbox")
    np.testing.assert_allclose(m.size, [34, 34, 34], atol=0.4)  # diameter=30 + 2*2 excess
    assert m.watertight


def test_chain_hull_connects_shapes(tmp_path):
    m = _render(
        tmp_path,
        "chain_hull(s3.cuboid([5, 5, 5]), s3.sphere(radius=4).right(20))",
        name="chainhull",
    )
    assert m.volume > 0
    assert m.size[0] > 20  # spans from the cube to the sphere
    assert m.watertight


def test_offset3d_grows_solid(tmp_path):
    grown = _render(tmp_path, "s3.cuboid([20, 20, 20]).offset3d(3)", name="offset3d")
    assert grown.volume > 20**3  # bigger than the original cube
    np.testing.assert_allclose(grown.size, [26, 26, 26], atol=1.0)  # grown ~3 each side


def test_cylindrical_extrude_wraps(tmp_path):
    # a 30-wide profile wraps a ~57-degree arc of a radius=30 cylinder, standing 8 tall in Z
    m = _render(
        tmp_path,
        "cylindrical_extrude(s2.square([30, 8], center=True), inner_radius=25, outer_radius=30)",
        name="cylext",
    )
    assert m.volume > 0
    assert math.isclose(m.size[2], 8.0, abs_tol=0.5)  # profile height -> cylinder axis
    assert m.bbmax[1] <= 30.5
    assert m.size[0] > 15  # curved band out near radius=25..30


# -- nurbs.scad curve / surface evaluation ------------------------------------------------


def test_nurbs_curve_spans_control_points(tmp_path):
    # a clamped cubic curve starts/ends at the first/last control point
    setup = "ctrl = [[0, 0, 0], [10, 20, 5], [30, -10, 10], [50, 20, 0], [60, 0, 15]]\n"
    m = _render(
        tmp_path,
        "NurbsCurve(ctrl, 3).curve(splinesteps=12).stroke(width=3)",
        setup=setup,
        name="nurbscurve",
    )
    assert m.volume > 0
    np.testing.assert_allclose(m.bbmin[0], 0, atol=1.6)  # starts at x=0
    np.testing.assert_allclose(m.bbmax[0], 60, atol=1.6)  # ends at x=60


def test_nurbs_surface_patch(tmp_path):
    setup = (
        "patch = [[[-50,50,0],[-16,50,20],[16,50,20],[50,50,0]],"
        "[[-50,16,20],[-16,16,40],[16,16,40],[50,16,20]],"
        "[[-50,-16,20],[-16,-16,40],[16,-16,40],[50,-16,20]],"
        "[[-50,-50,0],[-16,-50,20],[16,-50,20],[50,-50,0]]]\n"
    )
    m = _render(
        tmp_path,
        "NurbsPatch(patch, (3, 3)).vnf(splinesteps=(8, 8)).polyhedron()",
        setup=setup,
        name="nurbspatch",
    )
    assert m.ntris > 0
    np.testing.assert_allclose(m.size[:2], [100, 100], atol=1.0)  # spans the control grid


def test_rounding_methods_extrude(tmp_path):
    # circle / smooth / chamfer rounded squares all extrude into valid solids
    sq = "[[0, 0], [40, 0], [40, 30], [0, 30]]"
    for method, kw, name in (
        ("circle", "radius=5", "roundcircle"),
        ("smooth", "joint=8", "roundsmooth"),
        ("chamfer", "joint=6", "roundchamfer"),
    ):
        m = _render(
            tmp_path,
            f"Path2D({sq}).round_corners(method='{method}', {kw}).polygon().linear_extrude(height=4)",
            name=name,
        )
        assert m.volume > 0
        assert math.isclose(m.size[2], 4.0, abs_tol=1e-2)
        np.testing.assert_allclose(m.size[:2], [40, 30], atol=0.6)  # stays within the square
        assert m.watertight


def test_smooth_path_stroke(tmp_path):
    setup = "pts = [[0, 0], [10, 30], [30, -10], [50, 20], [70, 0]]\n"
    m = _render(
        tmp_path,
        "Path2D(pts).smooth_path(relsize=0.4).stroke(width=2).linear_extrude(height=3)",
        setup=setup,
        name="smoothpath",
    )
    assert m.volume > 0
    assert m.size[0] > 65  # spans the wiggly control points


def test_round_corners_3d_path(tmp_path):
    # a 3-D path with smooth corners, swept into a tube
    setup = (
        "route = Path3D([[0,0,0],[40,0,0],[40,40,20],[0,40,20]])"
        ".round_corners(method='smooth', joint=8, closed=False)\n"
    )
    m = _render(tmp_path, "route.stroke(width=3)", setup=setup, name="round3d")
    assert m.volume > 0
    assert m.bbmax[2] > 15  # follows the path up in Z


def test_threaded_rod_iso(tmp_path):
    # an ISO M12x1.75 rod: major diameter 12, length 24, minor = 12 - 2*(cos30*5/8)*1.75
    m = _render(tmp_path, "iso_threaded_rod(12, 24, 1.75, fa=6, fs=1).shape", name="isorod")
    assert m.watertight
    np.testing.assert_allclose(m.size[:2], [12, 12], atol=0.1)  # major diameter
    assert math.isclose(m.size[2], 24.0, abs_tol=0.05)  # length
    minor = 12 - 2 * math.cos(math.radians(30)) * 5 / 8 * 1.75
    lo = math.pi * (minor / 2) ** 2 * 24  # minor-cylinder volume
    hi = math.pi * 6**2 * 24  # major-cylinder volume
    assert lo < m.volume < hi  # threaded, so between the two


@pytest.mark.parametrize(
    ("expr", "name", "dia"),
    [
        ("trapezoidal_threaded_rod(20, 30, 4, fa=6, fs=1).shape", "traprod", 20),
        ("acme_threaded_rod(20, 30, 4, fa=6, fs=1).shape", "acmerod", 20),
        ("square_threaded_rod(20, 30, 4, fa=6, fs=1).shape", "sqrod", 20),
        ("buttress_threaded_rod(20, 30, 4, fa=6, fs=1).shape", "buttrod", 20),
    ],
)
def test_threaded_rod_variants_watertight(tmp_path, expr, name, dia):
    m = _render(tmp_path, expr, name=name)
    assert m.watertight
    np.testing.assert_allclose(m.size[:2], [dia, dia], atol=0.2)
    assert math.isclose(m.size[2], 30.0, abs_tol=0.05)


def test_multistart_and_left_handed(tmp_path):
    a = _render(
        tmp_path,
        "iso_threaded_rod(16, 24, 2, starts=2, fa=6, fs=1).shape",
        name="ms2",
    )
    assert a.watertight
    assert math.isclose(a.size[2], 24.0, abs_tol=0.05)
    b = _render(
        tmp_path,
        "iso_threaded_rod(12, 24, 1.75, left_handed=True, fa=6, fs=1).shape",
        name="lh",
    )
    assert b.watertight
    np.testing.assert_allclose(b.size[:2], [12, 12], atol=0.1)


def test_threaded_hex_nut(tmp_path):
    # a hex nut for an M12 rod: flat-to-flat 18, corner-to-corner ~20.8, height 10, threaded hole
    m = _render(
        tmp_path,
        "iso_threaded_nut(18, 12, 10, 1.75, slop=0.1, fa=6, fs=1).shape",
        name="hexnut",
    )
    assert m.watertight
    assert math.isclose(min(m.size[:2]), 18.0, abs_tol=0.3)  # flat-to-flat
    assert math.isclose(m.size[2], 10.0, abs_tol=0.05)  # height
    assert m.volume < math.pi * 10.4**2 * 10  # has a hole, so less than solid


def test_threaded_square_nut(tmp_path):
    m = _render(
        tmp_path,
        "trapezoidal_threaded_nut(24, 16, 12, 3, shape='square', slop=0.1, fa=6, fs=1).shape",
        name="sqnut",
    )
    assert m.watertight
    np.testing.assert_allclose(m.size[:2], [24, 24], atol=0.3)  # square
    assert math.isclose(m.size[2], 12.0, abs_tol=0.05)


def test_thread_helix_ridge(tmp_path):
    m = _render(
        tmp_path,
        "ThreadHelix(20, 4, turns=3).shape",
        name="threadhelix",
    )
    assert m.volume > 0
    np.testing.assert_allclose(m.size[:2], [20, 20], atol=0.3)  # crest at diameter 20


# -- screws, nuts and screw holes ---------------------------------------------------------


def test_screw_socket_head(tmp_path):
    # M6 socket cap screw, 20 mm shaft: head diameter 10, head height 6 above the shaft, so the
    # whole solid is 26 tall and 10 wide at the head.
    m = _render(
        tmp_path,
        "Screw('M6', 20, head=ScrewHeadType.SOCKET, drive=ScrewDriveType.HEX, fa=6, fs=1).shape",
        name="scrsocket",
    )
    assert m.watertight
    np.testing.assert_allclose(m.size[:2], [10, 10], atol=0.3)  # socket head diameter
    assert math.isclose(m.size[2], 26.0, abs_tol=0.3)  # 20 shaft + 6 head


def test_screw_hex_head(tmp_path):
    # M8 hex head: across-flats 13 (corner-to-corner ~15), head height 5.3 above a 16 mm shaft.
    m = _render(tmp_path, "Screw('M8', 16, head=ScrewHeadType.HEX, fa=6, fs=1).shape", name="scrhex")
    assert m.watertight
    assert math.isclose(min(m.size[:2]), 13.0, abs_tol=0.4)  # flat-to-flat of the hex head
    assert math.isclose(m.size[2], 21.3, abs_tol=0.3)  # 16 shaft + 5.3 head


def test_screw_flat_head_countersunk(tmp_path):
    # M6 countersunk: the head is a 90-degree cone, so it adds only (11.085-6)/2 ~ 2.54 above the shaft.
    m = _render(tmp_path, "Screw('M6', 16, head=ScrewHeadType.FLAT, fa=6, fs=1).shape", name="scrflat")
    assert m.watertight
    np.testing.assert_allclose(m.size[:2], [11.085, 11.085], atol=0.4)  # head diameter at the surface
    assert math.isclose(m.size[2], 16 + (11.085 - 6) / 2, abs_tol=0.3)


@pytest.mark.parametrize(
    ("head", "name"),
    [(ScrewHeadType.BUTTON, "scrbtn"), (ScrewHeadType.PAN, "scrpan"), (ScrewHeadType.NONE, "scrset")],
)
def test_screw_heads_watertight(tmp_path, head, name):
    drive = ScrewDriveType.HEX if head in (ScrewHeadType.BUTTON, ScrewHeadType.NONE) else ScrewDriveType.NONE
    m = _render(
        tmp_path,
        f"Screw('M6', 16, head=ScrewHeadType.{head.name}, drive=ScrewDriveType.{drive.name}, fa=6, fs=1).shape",
        name=name,
    )
    assert m.watertight
    assert math.isclose(min(m.size[:2]), 6.0, abs_tol=0.4) or min(m.size[:2]) >= 6.0  # at least the shaft


def test_screw_recess_removes_volume(tmp_path):
    # the hex drive recess must actually cut material out of the head.
    solid = _render(
        tmp_path,
        "Screw('M8', 16, head=ScrewHeadType.SOCKET, drive=ScrewDriveType.NONE, fa=6, fs=1).shape",
        name="norec",
    )
    drilled = _render(
        tmp_path,
        "Screw('M8', 16, head=ScrewHeadType.SOCKET, drive=ScrewDriveType.HEX, fa=6, fs=1).shape",
        name="rec",
    )
    assert drilled.watertight
    assert drilled.volume < solid.volume  # the recess subtracted material


def test_nut_matches_thread(tmp_path):
    # an M6 hex nut: flat-to-flat 10, normal thickness 5.2, threaded hole.
    m = _render(tmp_path, "Nut('M6', slop=0.1, fa=6, fs=1).shape", name="scrnut")
    assert m.watertight
    assert math.isclose(min(m.size[:2]), 10.0, abs_tol=0.3)  # flat-to-flat
    assert math.isclose(m.size[2], 5.2, abs_tol=0.1)  # normal thickness
    assert m.volume < math.pi * 5.2**2 * 5.2  # has a threaded hole


def test_square_nut(tmp_path):
    m = _render(
        tmp_path,
        "Nut('M6', shape=NutShape.SQUARE, slop=0.1, fa=6, fs=1).shape",
        name="sqscrnut",
    )
    assert m.watertight
    np.testing.assert_allclose(m.size[:2], [10, 10], atol=0.3)


def test_screw_hole_clearance(tmp_path):
    # a normal-fit clearance hole for M6 is a plain cylinder of diameter 6 + 2*0.5 = 7.
    m = _render(tmp_path, "ScrewHole('M6', 20, fa=6, fs=1).shape", name="clrhole")
    assert m.watertight
    np.testing.assert_allclose(m.size[:2], [7, 7], atol=0.2)
    assert math.isclose(m.size[2], 20.0, abs_tol=0.05)


def test_screw_hole_countersink(tmp_path):
    # a flat-head clearance hole flares out to the countersink diameter at the top.
    m = _render(
        tmp_path,
        "ScrewHole('M6', 20, head=ScrewHeadType.FLAT, fa=6, fs=1).shape",
        name="cskhole",
    )
    assert m.watertight
    assert max(m.size[:2]) >= 11.0  # opens up to the head diameter
    assert m.bbmax[2] > 0
    assert m.bbmin[2] < 0  # mouth at z=0, shaft below


def test_metaball_sphere_is_watertight(tmp_path):
    # a lone mb_sphere(10) at isovalue 1 -> a watertight sphere of radius 10
    m = _render(
        tmp_path,
        "VNF.from_metaballs([([0,0,0], mb_sphere(10))], "
        "bounding_box=[[-16,-16,-16],[16,16,16]], voxel_size=1.5).polyhedron()",
        name="mbsphere",
    )
    assert m.watertight
    np.testing.assert_allclose(m.size, [20, 20, 20], atol=1.0)  # diameter ~20


def test_metaballs_merge_into_one_blob(tmp_path):
    # two spheres whose fields overlap fuse into a single watertight peanut
    setup = "spec = [([-9,0,0], mb_sphere(9)), ([9,0,0], mb_sphere(9))]\n"
    m = _render(
        tmp_path,
        "VNF.from_metaballs(spec, bounding_box=[[-28,-16,-16],[28,16,16]], voxel_size=2).polyhedron()",
        setup=setup,
        name="mbpeanut",
    )
    assert m.watertight
    assert m.size[0] > 40  # spans both balls plus the inflated bridge


def test_metaball_torus_has_a_hole(tmp_path):
    m = _render(
        tmp_path,
        "VNF.from_metaballs([([0,0,0], mb_torus(10, 3))], "
        "bounding_box=[[-16,-16,-8],[16,16,8]], voxel_size=1.5).polyhedron()",
        name="mbtorus",
    )
    assert m.watertight
    np.testing.assert_allclose(m.size[:2], [26, 26], atol=1.5)  # outer diameter ~ 2*(10+3)
    assert m.size[2] < 8  # flat torus


def test_isosurface_of_a_field_function(tmp_path):
    setup = "def sf(pts):\n    return 8.0 / (pts[:, 0]**2 + pts[:, 1]**2 + pts[:, 2]**2) ** 0.5\n"
    m = _render(
        tmp_path,
        "VNF.from_field(sf, 1, bounding_box=24, voxel_size=1.5).polyhedron()",
        setup=setup,
        name="isofield",
    )
    assert m.watertight
    np.testing.assert_allclose(m.size, [16, 16, 16], atol=1.0)  # sphere of radius 8


def test_nurbs_rational_sphere_is_watertight(tmp_path):
    # the classic rational-NURBS unit sphere (weights + repeated v-knots) meshes to a closed solid
    setup = (
        "patch = [[[0,0,1]]*7,"
        "[[2,0,1],[2,4,1],[-2,4,1],[-2,0,1],[-2,-4,1],[2,-4,1],[2,0,1]],"
        "[[2,0,-1],[2,4,-1],[-2,4,-1],[-2,0,-1],[-2,-4,-1],[2,-4,-1],[2,0,-1]],"
        "[[0,0,-1]]*7]\n"
        "weights = [[w/9 for w in row] for row in [[9,3,3,9,3,3,9],[3,1,1,3,1,1,3],[3,1,1,3,1,1,3],[9,3,3,9,3,3,9]]]\n"
        "vknots = [0, 0.5, 0.5, 0.5, 1]\n"
    )
    m = _render(
        tmp_path,
        "NurbsPatch(patch, (3, 3), weights=weights, knots=(None, vknots)).vnf(splinesteps=(12, 12)).polyhedron()",
        setup=setup,
        name="nurbssphere",
    )
    assert m.watertight
    np.testing.assert_allclose(m.size, [2, 2, 2], atol=0.1)  # unit sphere, diameter 2


# -- native-only mesh operations (repair / wrap / roof / pull / oversample / separate / inside) ----


def test_repair_keeps_watertight(tmp_path):
    m = _render(tmp_path, "s3.cuboid([20, 20, 10]).repair()", name="repair")
    assert m.watertight
    np.testing.assert_allclose(m.size, [20, 20, 10], atol=0.1)


def test_oversample_subdivides_facets(tmp_path):
    base = _render(tmp_path, "s3.cuboid([20, 20, 10])", name="ov_base")
    over = _render(tmp_path, "s3.cuboid([20, 20, 10]).oversample(3)", name="ov_3")
    assert over.watertight
    assert over.ntris > base.ntris * 4  # each facet subdivided many-fold
    np.testing.assert_allclose(over.size, [20, 20, 10], atol=0.1)  # same shape, just denser
    assert math.isclose(over.volume, base.volume, rel_tol=0.02)


def test_roof_makes_a_pyramid(tmp_path):
    # a hip roof over a 20x20 square is a pyramid: volume = base_area * height / 3.
    m = _render(tmp_path, "s3.roof(s2.square([20, 20], center=True))", name="roof")
    assert m.watertight
    np.testing.assert_allclose(m.size[:2], [20, 20], atol=0.2)
    assert m.size[2] > 5  # it rises to a ridge
    assert m.volume < 20 * 20 * m.size[2]  # a roof, not a full prism


# NOTE: wrap() is intentionally not render-tested. Meshing/exporting a wrapped solid is extremely
# slow in the Manifold backend (a single small bar exceeds several minutes), so a render test would
# only ever time out and skip. The method is covered at the mock level in test_native_ops.py; wrap
# itself is a thin pass-through to the native builtin.


def test_pull_stretches_material(tmp_path):
    solid = _render(tmp_path, "s3.cuboid([20, 20, 10])", name="pull_base")
    pulled = _render(tmp_path, "s3.cuboid([20, 20, 10]).pull([0, 0, 1], 8)", name="pull_8")
    assert pulled.watertight
    assert pulled.volume > solid.volume  # stretched apart, so bigger


def test_separate_extracts_one_lump(tmp_path):
    # two disjoint 8-cubes; separate()[0] is a single 8-cube, not the 38-wide pair.
    whole = _render(
        tmp_path,
        "(s3.cuboid([8, 8, 8]) | s3.cuboid([8, 8, 8]).right(30))",
        name="sep_whole",
    )
    part = _render(
        tmp_path,
        "(s3.cuboid([8, 8, 8]) | s3.cuboid([8, 8, 8]).right(30)).separate()[0]",
        name="sep_part",
    )
    assert part.watertight
    np.testing.assert_allclose(part.size, [8, 8, 8], atol=0.1)  # one lump
    assert whole.size[0] > 30  # the pair spanned far


# -- shapes2d extruded shapes -------------------------------------------------------------


def test_circle_extruded(tmp_path):
    m = _render(tmp_path, "s2.circle(radius=10, fn=48).linear_extrude(height=5)", name="circle")
    assert m.watertight
    np.testing.assert_allclose(m.size[:2], [20, 20], atol=0.3)
    assert math.isclose(m.size[2], 5.0, abs_tol=1e-2)
    assert m.volume > 0


def test_square_extruded(tmp_path):
    m = _render(
        tmp_path,
        "s2.square([20, 15], center=True).linear_extrude(height=5)",
        name="square",
    )
    assert m.watertight
    np.testing.assert_allclose(m.size[:2], [20, 15], atol=0.1)
    assert math.isclose(m.size[2], 5.0, abs_tol=1e-2)


def test_rect_rounded_extruded(tmp_path):
    m = _render(
        tmp_path,
        "s2.rect([30, 20], rounding=4, fn=32).linear_extrude(height=5)",
        name="rect_round",
    )
    assert m.watertight
    np.testing.assert_allclose(m.size[:2], [30, 20], atol=0.3)
    assert m.volume > 0


def test_ellipse_extruded(tmp_path):
    m = _render(
        tmp_path,
        "s2.ellipse(radius=[15, 10], fn=48).linear_extrude(height=5)",
        name="ellipse",
    )
    assert m.watertight
    np.testing.assert_allclose(m.size[:2], [30, 20], atol=0.5)
    assert math.isclose(m.size[2], 5.0, abs_tol=1e-2)


def test_regular_ngon_extruded(tmp_path):
    m = _render(tmp_path, "s2.regular_ngon(6, radius=10).linear_extrude(height=6)", name="hex2d")
    assert m.watertight
    assert math.isclose(m.size[2], 6.0, abs_tol=1e-2)


# -- the Bosl2Shape2D operators, rendered for real ---------------------------


def test_shape2d_fill_removes_the_hole(tmp_path):
    # a 40x40 plate with a radius-8 hole, then the same plate filled: same envelope, more volume
    holed = _render(
        tmp_path,
        "(s2.square(40) - s2.circle(radius=8, fn=64)).linear_extrude(height=4)",
        name="fill_holed",
    )
    filled = _render(
        tmp_path,
        "(s2.square(40) - s2.circle(radius=8, fn=64)).fill().linear_extrude(height=4)",
        name="fill_filled",
    )
    assert holed.watertight
    assert filled.watertight
    np.testing.assert_allclose(filled.size, holed.size, atol=0.1)
    # the hole was pi*8^2*4 ~= 804 mm^3 of missing material
    assert math.isclose(filled.volume - holed.volume, math.pi * 64 * 4, rel_tol=0.02)
    assert math.isclose(filled.volume, 40 * 40 * 4, rel_tol=1e-3)


def test_shape2d_hull_of_two_circles_is_a_slot(tmp_path):
    m = _render(
        tmp_path,
        "s2.circle(radius=5, fn=64).hull(s2.circle(radius=5, fn=64).right(30)).linear_extrude(height=3)",
        name="hull_slot",
    )
    assert m.watertight
    np.testing.assert_allclose(m.size, [40, 10, 3], atol=0.2)
    # a 30x10 rectangle plus a radius-5 disc, 3 tall
    assert math.isclose(m.volume, (30 * 10 + math.pi * 25) * 3, rel_tol=0.02)


def test_shape2d_hull_fills_a_star_notch(tmp_path):
    star = _render(tmp_path, "s2.star(tips=5, radius=20, inner_radius=8).linear_extrude(height=2)", name="hull_star")
    hull = _render(
        tmp_path,
        "s2.star(tips=5, radius=20, inner_radius=8).hull().linear_extrude(height=2)",
        name="hull_starhull",
    )
    assert star.watertight
    assert hull.watertight
    np.testing.assert_allclose(hull.size, star.size, atol=0.2)  # same tips
    assert hull.volume > star.volume * 1.2  # but convex, so the notches are filled


def test_shape2d_offset_uses_the_bosl2_radius_keyword(tmp_path):
    # BOSL2 spells it radius=; the native offset() only understands r=
    m = _render(tmp_path, "s2.square(20).offset(radius=3, fn=32).linear_extrude(height=2)", name="off2d_radius")
    assert m.watertight
    np.testing.assert_allclose(m.size[:2], [26, 26], atol=0.2)
    m = _render(tmp_path, "s2.square(20).offset(delta=3).linear_extrude(height=2)", name="off2d_delta")
    assert m.watertight
    np.testing.assert_allclose(m.size[:2], [26, 26], atol=1e-2)


def test_shape2d_rotate_extrude_makes_a_torus(tmp_path):
    m = _render(
        tmp_path,
        "s2.circle(radius=4, fn=48).right(20).rotate_extrude(fn=64)",
        name="rotex2d",
    )
    assert m.watertight
    np.testing.assert_allclose(m.size, [48, 48, 8], atol=0.5)


def test_path_linear_extrude_and_fill(tmp_path):
    # Path2D.linear_extrude()/fill() go through Path2D.polygon() -> Bosl2Shape2D; a simple outline
    # has no holes, so fill() leaves it exactly as it was.
    setup = "outline = Path([[0, 0], [40, 0], [40, 30], [0, 30]])\n"
    plain = _render(tmp_path, "outline.linear_extrude(height=3)", setup=setup, name="path_extrude")
    filled = _render(tmp_path, "outline.fill().linear_extrude(height=3)", setup=setup, name="path_fill")
    assert plain.watertight
    assert filled.watertight
    np.testing.assert_allclose(plain.size, [40, 30, 3], atol=0.1)
    assert math.isclose(plain.volume, 40 * 30 * 3, rel_tol=1e-3)
    assert math.isclose(filled.volume, plain.volume, rel_tol=1e-6)


def test_path_hull_wraps_a_concave_outline(tmp_path):
    # an L-shaped outline; its hull cuts the inner corner off diagonally
    setup = "ell = Path([[0, 0], [40, 0], [40, 10], [10, 10], [10, 30], [0, 30]])\n"
    plain = _render(tmp_path, "ell.linear_extrude(height=3)", setup=setup, name="path_ell")
    hull = _render(tmp_path, "ell.hull().linear_extrude(height=3)", setup=setup, name="path_ell_hull")
    assert plain.watertight
    assert hull.watertight
    np.testing.assert_allclose(hull.size, [40, 30, 3], atol=0.1)
    # the hull is the pentagon (0,0)-(40,0)-(40,10)-(10,30)-(0,30), area 900
    assert math.isclose(hull.volume, 900 * 3, rel_tol=1e-3)
    assert math.isclose(plain.volume, 600 * 3, rel_tol=1e-3)  # the L itself: 40x10 + 10x20


def test_region_fill_removes_the_hole(tmp_path):
    setup = (
        "region = Region.with_holes([[0, 0], [40, 0], [40, 30], [0, 30]], [[10, 10], [30, 10], [30, 20], [10, 20]])\n"
    )
    holed = _render(tmp_path, "region.linear_extrude(height=4)", setup=setup, name="region_holed")
    filled = _render(tmp_path, "region.fill().linear_extrude(height=4)", setup=setup, name="region_filled")
    assert holed.watertight
    assert filled.watertight
    np.testing.assert_allclose(filled.size, [40, 30, 4], atol=0.1)
    assert math.isclose(filled.volume, 40 * 30 * 4, rel_tol=1e-3)
    assert math.isclose(holed.volume, (40 * 30 - 20 * 10) * 4, rel_tol=1e-3)


def test_solid_hull_of_two_spheres_is_a_capsule(tmp_path):
    m = _render(
        tmp_path,
        "s3.sphere(radius=8, fn=48).hull(s3.sphere(radius=8, fn=48).up(30))",
        name="hull_capsule",
    )
    assert m.watertight
    np.testing.assert_allclose(m.size, [16, 16, 46], atol=0.5)
    # a 30-tall cylinder plus one full sphere
    assert math.isclose(m.volume, math.pi * 64 * 30 + 4 / 3 * math.pi * 8**3, rel_tol=0.03)


def test_solid_projection_is_the_xy_footprint(tmp_path):
    m = _render(
        tmp_path,
        "s3.cuboid([30, 20, 10], rounding=3, fn=32).projection().linear_extrude(height=2)",
        name="projection2d",
    )
    assert m.watertight
    np.testing.assert_allclose(m.size, [30, 20, 2], atol=0.2)


def test_solid_projection_offset_makes_a_base_plate(tmp_path):
    m = _render(
        tmp_path,
        "s3.cuboid([30, 20, 10]).projection().offset(radius=4, fn=32).linear_extrude(height=2)",
        name="projection_plate",
    )
    assert m.watertight
    np.testing.assert_allclose(m.size, [38, 28, 2], atol=0.3)
    assert m.volume > 0


def test_regular_ngon_rounded_extruded(tmp_path):
    m = _render_golden(
        tmp_path,
        "s2.regular_ngon(5, radius=10, rounding=3, fn=36).linear_extrude(height=6)",
        name="pent_round",
    )
    assert m.watertight
    assert m.volume > 0


def test_star_extruded(tmp_path):
    m = _render_golden(
        tmp_path,
        "s2.star(tips=5, radius=12, inner_radius=5).linear_extrude(height=5)",
        name="star",
    )
    assert m.watertight
    assert m.volume > 0


def test_teardrop2d_extruded(tmp_path):
    m = _render_golden(
        tmp_path,
        "s2.teardrop2d(radius=10, angle=45, fn=32).linear_extrude(height=5)",
        name="teardrop2d",
    )
    assert m.volume > 0


def test_egg_extruded(tmp_path):
    m = _render_golden(
        tmp_path,
        "s2.egg(length=50, radius1=10, radius2=6, arc_radius=30, fn=32).linear_extrude(height=5)",
        name="egg",
    )
    assert m.watertight
    assert m.volume > 0


def test_glued_circles_extruded(tmp_path):
    m = _render_golden(
        tmp_path,
        "s2.glued_circles(radius=10, spread=30, tangent=30, fn=32).linear_extrude(height=5)",
        name="glued",
    )
    assert m.watertight
    assert m.volume > 0


def test_reuleaux_polygon_extruded(tmp_path):
    m = _render_golden(
        tmp_path,
        "s2.reuleaux_polygon(3, radius=10, fn=48).linear_extrude(height=5)",
        name="reuleaux",
    )
    assert m.watertight
    assert m.volume > 0


# -- shapes3d rounding/chamfer variants ---------------------------------------------------


def test_cuboid_rounding_watertight(tmp_path):
    m = _render(tmp_path, "s3.cuboid([40, 30, 20], rounding=5, fn=32)", name="cuboid_round")
    assert m.watertight
    assert m.volume > 0
    np.testing.assert_allclose(m.size, [40, 30, 20], atol=0.5)


def test_cuboid_chamfer_watertight(tmp_path):
    m = _render(tmp_path, "s3.cuboid([40, 30, 20], chamfer=5)", name="cuboid_chamf")
    assert m.watertight
    assert m.volume > 0


def test_cuboid_edges_rounding(tmp_path):
    m = _render(
        tmp_path,
        "s3.cuboid([40, 30, 20], rounding=3, edges=TOP, fn=24)",
        name="cuboid_topround",
    )
    assert m.watertight
    np.testing.assert_allclose(m.size, [40, 30, 20], atol=0.5)


def test_cuboid_negative_chamfer_is_manifold(tmp_path):
    # a negative chamfer flares the edges outwards; the flare is pieced together from bars and
    # corner blocks, which used to be left standing a hair proud of each other, so the union kept
    # both surfaces and the solid came out non-manifold. Volume checked against BOSL2's own render.
    m = _render(
        tmp_path,
        "s3.cuboid([25, 4.75, 10.52], chamfer=-0.5, edges=Anchor.ALL)",
        name="cuboid_negchamf",
    )
    assert m.watertight
    assert math.isclose(m.volume, 1264.458, rel_tol=1e-4)  # BOSL2 cuboid(chamfer=-0.5, edges="ALL")
    np.testing.assert_allclose(m.size, [26, 5.75, 10.52], atol=1e-3)  # flared by the chamfer


def test_cuboid_negative_rounding_is_manifold(tmp_path):
    m = _render(
        tmp_path,
        "s3.cuboid([25, 4.75, 10.52], rounding=-0.5, edges=Anchor.ALL, fn=16)",
        name="cuboid_neground",
    )
    assert m.watertight
    assert math.isclose(m.volume, 1256.341, rel_tol=1e-4)  # BOSL2 cuboid(rounding=-0.5, edges="ALL")


def test_swept_solid_is_not_inside_out(tmp_path):
    # a VNF-built solid handed to polyhedron() as-is comes out inside out: it exports fine on its
    # own, but cutting with it then adds material instead of removing it.
    m = _render(
        tmp_path,
        "s3.cuboid([20, 20, 6]) - Path2D([[-5, -5], [5, -5], [5, 5], [-5, 5]])"
        ".linear_sweep(height=20, center=True).polyhedron()",
        name="sweep_cut",
    )
    assert m.watertight
    assert math.isclose(m.volume, 20 * 20 * 6 - 10 * 10 * 6, rel_tol=1e-6)  # the cut removed a 10x10 hole


def test_cylinder_chamfered(tmp_path):
    m = _render_golden(tmp_path, "s3.cyl(height=20, radius=5, chamfer=2, fn=64)", name="cyl_chamf")
    assert m.volume > 0


def test_cylinder_rounded(tmp_path):
    m = _render(tmp_path, "s3.cyl(height=20, radius=5, rounding=2, fn=64)", name="cyl_round")
    assert m.watertight
    assert m.volume > 0


def test_cylinder_cone(tmp_path):
    m = _render(tmp_path, "s3.cyl(height=20, radius1=8, radius2=3, fn=64)", name="cone")
    assert m.watertight
    np.testing.assert_allclose(m.size[:2], [16, 16], atol=0.2)
    assert math.isclose(m.size[2], 20.0, abs_tol=1e-3)


def test_spheroid_shape(tmp_path):
    m = _render_golden(tmp_path, "s3.spheroid(radius=15, fn=48)", name="spheroid")
    assert m.watertight
    assert m.volume > 0


def test_regular_prism_rounded(tmp_path):
    m = _render_golden(
        tmp_path,
        "s3.regular_prism(5, height=12, radius=10, rounding=2, fn=32)",
        name="pentprism_round",
    )
    assert m.volume > 0


def test_tube_chamfered(tmp_path):
    m = _render_golden(
        tmp_path,
        "s3.tube(height=12, outer_radius=10, inner_radius=6, fa=6, fs=1)",
        name="tube_chamf",
    )
    assert m.watertight
    assert m.volume > 0


def test_torus_shape(tmp_path):
    m = _render_golden(tmp_path, "s3.torus(major_radius=12, minor_radius=3, fn=48)", name="torus")
    assert m.watertight
    assert m.volume > 0


def test_xcyl_builds(tmp_path):
    m = _render(tmp_path, "s3.xcyl(height=20, radius=5)", name="xcyl")
    assert m.watertight
    assert math.isclose(m.size[0], 20.0, abs_tol=1e-2)


def test_pie_slice_builds(tmp_path):
    m = _render_golden(tmp_path, "s3.pie_slice(height=8, radius=15, angle=[30, 120])", name="pieslice")
    assert m.watertight
    assert m.volume > 0


# -- parts library shapes -----------------------------------------------------------------


def test_spur_gear_builds(tmp_path):
    m = _render_golden(
        tmp_path, "SpurGear(mod=2, teeth=15, thickness=6, fn=None, fa=None, fs=None).shape", name="spurgear"
    )
    assert m.watertight
    assert m.volume > 0


def test_hinge_knuckle_builds(tmp_path):
    m = _render_golden(
        tmp_path,
        "KnuckleHinge(length=30, knuckle_diam=6, pin_diam=2, arm=18, thick=3, fn=32).shape",
        name="knuckle_hinge",
    )
    assert m.watertight
    assert m.volume > 0


@pytest.mark.parametrize("fold", [0, 45, 90, 120])
def test_knuckle_hinge_leaves_never_share_volume(tmp_path, fold):
    """The two leaves must not intersect, or the "hinge" is one fused solid.

    This is THE property of a hinge and nothing was checking it: the leaves used to share a
    solid running the hinge's whole length, because the leaf plate spanned the full length and
    reached the pin axis, so it passed straight through the other leaf's knuckles. Building,
    being watertight, and having a plausible bounding box were all still true.

    Measured as volume additivity rather than by intersecting: |A u B| == |A| + |B| exactly
    when A and B are disjoint, and unlike an intersection it cannot be fooled by an empty
    result that merely fails to export.
    """
    leaves = (
        "_o = KnuckleHinge(length=40, segs=5, inner=False).shape\n"
        f"_i = KnuckleHinge(length=40, segs=5, inner=True).shape.rotate([{fold}, 0, 0])\n"
    )
    outer = _render(tmp_path, "_o", setup=leaves, name=f"leaf_outer_{fold}")
    inner = _render(tmp_path, "_i", setup=leaves, name=f"leaf_inner_{fold}")
    both = _render(tmp_path, "_o | _i", setup=leaves, name=f"leaf_union_{fold}")

    assert outer.volume > 0
    assert inner.volume > 0
    shared = outer.volume + inner.volume - both.volume
    assert shared == pytest.approx(0.0, abs=1e-3 * both.volume), (
        f"leaves overlap by {shared:.3f}mm^3 at fold={fold} "
        f"({100 * shared / both.volume:.2f}% of the hinge) -- they cannot rotate about the pin"
    )


def test_knuckle_hinge_leaves_bottom_out_when_closed(tmp_path):
    """...but a leaf pair DOES meet once folded far enough, and that is not a bug.

    Both plates are centred on the pin axis, so each subtends about
    +/-atan(thick/2 / (knuckle_diam/2 + gap)) about it; the leaves run out of room at roughly
    180 - 2x that. Pinning the behaviour here says the clearance above is real geometry rather
    than an over-generous cut that would leave a floppy hinge.
    """
    leaves = (
        "_o = KnuckleHinge(length=40, segs=5, inner=False).shape\n"
        "_i = KnuckleHinge(length=40, segs=5, inner=True).shape.rotate([180, 0, 0])\n"
    )
    outer = _render(tmp_path, "_o", setup=leaves, name="closed_outer")
    inner = _render(tmp_path, "_i", setup=leaves, name="closed_inner")
    both = _render(tmp_path, "_o | _i", setup=leaves, name="closed_union")
    shared = outer.volume + inner.volume - both.volume
    assert shared > 0, "folded flat back on itself the leaves should meet"


def test_worm_gear_builds(tmp_path):
    m = _render(tmp_path, "Worm(diameter=20, length=40).shape", name="worm")
    assert m.watertight
    assert m.volume > 0


def test_walls_thinning_wall_builds(tmp_path):
    m = _render(
        tmp_path,
        "ThinningWall(height=40, length=80, thick=6, angle=15).shape",
        name="thinwall",
    )
    assert m.watertight
    assert m.volume > 0


def test_polyhedra_tetrahedron(tmp_path):
    m = _render(tmp_path, "RegularPolyhedron(PlatonicSolid.TETRAHEDRON, radius=12).shape", name="tetra")
    assert m.watertight
    assert m.volume > 0


def test_polyhedra_icosahedron(tmp_path):
    m = _render(tmp_path, "RegularPolyhedron(PlatonicSolid.ICOSAHEDRON, radius=10).shape", name="icosa")
    assert m.watertight
    assert m.volume > 0


def test_screw_drive_phillips_mask(tmp_path):
    m = _render(tmp_path, "PhillipsMask('#2', fn=24).shape", name="phillips")
    assert m.volume > 0
    assert m.watertight


def test_nema_stepper_motor(tmp_path):
    m = _render(
        tmp_path,
        "NemaMountMask(size=17, depth=5, fn=24).shape",
        name="nema_mask",
    )
    assert m.volume > 0
    assert m.watertight


def test_sliders_rail_builds(tmp_path):
    m = _render(tmp_path, "Rail(l=40, w=10, h=10).shape", name="slider_rail")
    assert m.watertight
    assert m.volume > 0


def test_tripod_rc2_plate_builds(tmp_path):
    m = _render_golden(
        tmp_path,
        "ManfrottoRC2Plate(fn=None, fa=None, fs=None).shape",
        name="rc2_plate",
    )
    assert m.watertight
    assert m.volume > 0
    # the plate is a dovetail with a relief notch cut in at each end and a facet down one side --
    # pinned against BOSL2's own render of manfrotto_rc2_plate(), which is 19549 mm^3
    np.testing.assert_allclose(m.size, [42.4, 52.5, 10.5], atol=1e-3)
    np.testing.assert_allclose(m.bbmin, [-21.36, -26.25, -5.25], atol=0.01)  # centred on its anchor box
    assert math.isclose(m.volume, 19549.11, rel_tol=2e-3)


def test_sdf_backend_real_render(tmp_path):
    # Tests that shapes constructed under the "sdf" active backend
    # correctly delegate to the libfive backend and mesh/render.
    setup = (
        "from pybosl2.solid import cuboid, sphere, use_backend\n"
        "def build_shape():\n"
        "    with use_backend('sdf'):\n"
        "        a = cuboid([20, 20, 20], rounding=3, res=10)\n"
        "        b = sphere(radius=12, res=10).translate([0, 0, 10])\n"
        "        return a | b\n"
    )
    m = _render(tmp_path, "build_shape()", setup=setup, name="sdf_backend_real_render")
    assert m.watertight
    assert m.volume > 0


def test_sdf_to_csg_survives_measuring_and_reuse(tmp_path):
    # Regression: to_csg() used to hand the raw frep() handle to Bosl2Solid. Measuring that handle
    # (obj.position/obj.size, which bounds() and every bbox anchor read) corrupts it inside
    # PythonSCAD, and the render then dies with SIGSEGV and an empty stderr -- so the whole part
    # silently produced nothing. Everything below has to survive on one bridged solid: repeated
    # bounds(), anchoring, a union with a native solid, a transform, and a second .to_csg().
    setup = (
        "from pybosl2.solid import cuboid, use_backend\n"
        "from pybosl2 import shapes3d as s3\n"
        "from pybosl2 import Anchor\n"
        "def build_shape():\n"
        "    with use_backend('sdf'):\n"
        "        field = cuboid([20, 20, 20], rounding=3, res=10)\n"
        "    part = field.to_csg()\n"
        "    assert part.bounds() == part.bounds(), 'bounds() is not repeatable'\n"
        "    assert part.anchor_point(Anchor.TOP)[2] > 9\n"
        "    combined = s3.cuboid([60, 8, 8]) | part\n"
        "    assert combined.bounds()[1][0] > 59\n"
        "    return combined | field.to_csg().translate([0, 0, 30])\n"
    )
    m = _render(tmp_path, "build_shape()", setup=setup, name="sdf_to_csg_reuse")
    assert m.watertight
    assert m.volume > 0
    np.testing.assert_allclose(m.bbmin, [-30, -10, -10], atol=0.1)
    np.testing.assert_allclose(m.bbmax, [30, 10, 40], atol=0.1)


def test_sdf_to_csg_matches_the_field_it_was_meshed_from(tmp_path):
    # The bridge rebuilds libfive's mesh as a polyhedron; it must come out the same solid (same
    # bbox, same volume, right way out) as rendering the field directly -- an inside-out polyhedron
    # still looks right alone but inverts every boolean it takes part in.
    setup = (
        "from pybosl2.solid import cuboid, use_backend\n"
        "def field():\n"
        "    with use_backend('sdf'):\n"
        "        return cuboid([20, 20, 20], rounding=3, res=10)\n"
    )
    direct = _render(tmp_path, "field()", setup=setup, name="sdf_field_direct")
    bridged = _render(tmp_path, "field().to_csg()", setup=setup, name="sdf_field_bridged")
    np.testing.assert_allclose(bridged.size, direct.size, atol=1e-3)
    assert math.isclose(bridged.volume, direct.volume, rel_tol=1e-6)
    assert bridged.watertight
    setup_cut = setup + (
        "from pybosl2 import shapes3d as s3\ndef cut():\n    return s3.cuboid([30, 30, 30]) - field().to_csg()\n"
    )
    cut = _render(tmp_path, "cut()", setup=setup_cut, name="sdf_field_cut")
    assert math.isclose(cut.volume, 27000 - direct.volume, rel_tol=1e-3)


# -- SVG stroke and polygon rendering --------------------------------------------------------

PORTUGAL_FLAG_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400">'
    '<rect width="600" height="400" fill="#f00"/>'
    '<rect width="240" height="400" fill="#060"/>'
    '<g fill="#ff0" fill-rule="evenodd" stroke="#000" stroke-width="0.8">'
    '<circle cx="300" cy="200" r="80"/>'
    '<circle cx="300" cy="200" r="60"/>'
    '<path d="m200,200 h200 M300,100 v200"/>'
    "</g>"
    "<g>"
    '<path fill="#fff" stroke="#000" stroke-width="1.5" d="m260,160 h80 v80 h-80 z"/>'
    '<path fill="#00f" d="m270,170 h20 v20 h-20 z M310,170 h20 v20 h-20 z '
    'M270,210 h20 v20 h-20 z M310,210 h20 v20 h-20 z M290,190 h20 v20 h-20 z"/>'
    "</g>"
    "</svg>"
)


def _svg_setup(svg_path: Path) -> str:
    """Module-level statements for an SVG render.

    `expr` is spliced into `    obj = {expr}` INSIDE a try block, so it has to stay one
    expression on one line -- imports and assignments go here instead, where render_object
    drops them at module level.
    """
    return f"svg_path = r'{svg_path}'\nfrom pybosl2 import Region\n"


def test_portugal_flag_strokes_polygon(tmp_path):
    """Simplified Portuguese flag with strokes=polygon: coloured regions + stroke outlines."""
    svg_path = tmp_path / "portugal.svg"
    svg_path.write_text(PORTUGAL_FLAG_SVG)
    m = _render(
        tmp_path,
        'Region.from_svg(svg_path, strokes="polygon").linear_extrude(height=2)',
        setup=_svg_setup(svg_path),
        name="portugal_strokes_polygon",
    )
    assert m.ntris > 0
    assert m.watertight
    # The flag is 600x400, extruded 2mm → volume ≈ 600*400*2 = 480000, minus holes
    assert 300000 < m.volume < 500000


def test_portugal_flag_strokes_ignore(tmp_path):
    """Simplified Portuguese flag with strokes=ignore: only filled shapes, no outlines."""
    svg_path = tmp_path / "portugal.svg"
    svg_path.write_text(PORTUGAL_FLAG_SVG)
    m = _render(
        tmp_path,
        'Region.from_svg(svg_path, strokes="ignore").linear_extrude(height=2)',
        setup=_svg_setup(svg_path),
        name="portugal_strokes_ignore",
    )
    assert m.ntris > 0
    assert m.watertight
    # strokes=ignore produces fewer triangles (no stroke polygons)
    assert m.volume > 0


# -- the real thing: Wikipedia's Flag of Portugal --------------------------------------------

FLAG_OF_PORTUGAL = Path(__file__).resolve().parent / "svg_fixtures" / "flag_of_portugal.svg"


def _open_edge_count(stl_path: Path) -> int:
    """Edges used by exactly ONE triangle, i.e. a genuine hole in the surface.

    Deliberately not `StlMetrics.watertight`, which wants every edge shared by exactly two
    triangles. A multi-colour part legitimately fails that: separate colour bodies abut, and
    a cut-out that touches another leaves an edge shared by four. Neither is an opening --
    for "will this print" the question is whether the surface is CLOSED.
    """
    import collections

    tris = np.round(parse_stl(stl_path), 4)
    edges: collections.Counter = collections.Counter()
    for tri in tris:
        vs = [tuple(v) for v in tri]
        for a, b in ((0, 1), (1, 2), (2, 0)):
            edges[tuple(sorted((vs[a], vs[b])))] += 1
    return sum(1 for count in edges.values() if count == 1)


@pytest.mark.parametrize("strokes", ["ignore", "polygon"])
def test_flag_of_portugal_extrudes_to_the_whole_flag(tmp_path, strokes):
    """The real 600x400 flag, extruded 2mm, is exactly a 600x400x2 plate.

    A hand-drawn national flag exercises what synthetic fixtures do not: 148 rings across
    135 elements, 11 <use> clones, mixed winding, 20 self-intersecting outlines and a coat
    of arms straddling both fields. Loading it used to abort inside shapely; then it loaded
    with the green field 99% eaten; then with 96184mm^2 of a 240000mm^2 flag double-covered.

    Volume is the assertion that catches all three at once: any missing piece, any
    double-counted overlap, and it is no longer exactly 600*400*2.
    """
    setup = f"svg_path = r'{FLAG_OF_PORTUGAL}'\nfrom pybosl2 import Region\n"
    m = _render(
        tmp_path,
        f'Region.from_svg(svg_path, strokes="{strokes}").linear_extrude(height=2)',
        setup=setup,
        name=f"portugal_real_{strokes}",
    )
    np.testing.assert_allclose(m.size, [600, 400, 2], atol=1e-3)
    assert m.volume == pytest.approx(600 * 400 * 2, rel=1e-6)
    assert _open_edge_count(tmp_path / f"portugal_real_{strokes}.stl") == 0

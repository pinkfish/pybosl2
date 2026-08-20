# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Every rejection path names what to pass instead (SPEC E-4, PLAN E-P1).

These are the branches the assert-to-ValueError conversion created. A rejection nobody exercises
is a rejection nobody knows works — and E-4 is as much about the message as the type, so each case
asserts the wording the caller would act on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

import pybosl2.beziers as beziers
import pybosl2.miscellaneous as misc
import pybosl2.nurbs as nurbs
import pybosl2.sdf.paths as sdfp
import pybosl2.sdf.shapes2d as sdf2
import pybosl2.sdf.shapes3d as sdf3
import pybosl2.shapes2d as s2
import pybosl2.shapes3d as s3
import pybosl2.skin as skin
import pybosl2.surfaces3d as surfaces
from pybosl2.isosurface import (
    mb_capsule,
    mb_connector,
    mb_cuboid,
    mb_disk,
    mb_octahedron,
    mb_sphere,
    mb_torus,
    metaballs2d,
)
from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D
from pybosl2.shapes2d import circle, square
from pybosl2.texture import texture

#: (what the caller did wrong, the phrase the message must carry).
METABALL_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: mb_sphere(radius=0), "positive radius"),
    (lambda: mb_sphere(radius=-3), "positive radius"),
    (lambda: mb_cuboid(size=10, squareness=1.5), r"squareness must be in \[0, 1\]"),
    (lambda: mb_cuboid(size=10, squareness=-0.1), r"squareness must be in \[0, 1\]"),
    (lambda: mb_torus(major_radius=10, minor_radius=0), "positive major_radius"),
    (lambda: mb_torus(major_radius=-10, minor_radius=2), "positive major_radius"),
    (lambda: mb_torus(major_radius=10, minor_radius=-2), "positive major_radius"),
    (lambda: mb_capsule(height=10, radius=0), "positive height and radius"),
    (lambda: mb_capsule(height=0, radius=3), "positive height and radius"),
    (lambda: mb_capsule(height=-10, radius=3), "positive height and radius"),
    (lambda: mb_capsule(height=10, radius=-3), "positive height and radius"),
    (lambda: mb_capsule(height=4, radius=3), "must exceed the two rounded ends"),
    (lambda: mb_disk(height=4, radius=0), "positive height and radius"),
    (lambda: mb_disk(height=0, radius=8), "positive height and radius"),
    (lambda: mb_disk(height=-4, radius=8), "positive height and radius"),
    (lambda: mb_disk(height=4, radius=-8), "positive height and radius"),
    (lambda: mb_disk(height=20, radius=4), "must exceed the thickness"),
    (lambda: mb_octahedron(size=10, squareness=2), r"squareness must be in \[0, 1\]"),
    (lambda: mb_connector([0, 0, 0], [10, 0, 0], radius=0), "distinct points"),
    (lambda: mb_connector([0, 0, 0], [10, 0, 0], radius=-2), "distinct points"),
    (lambda: mb_connector([1, 2, 3], [1, 2, 3], radius=2), "distinct points"),
    (lambda: metaballs2d([], bounding_box=[[-10, -10], [10, 10]], pixel_size=1), "spec is empty"),
]


@pytest.mark.parametrize(("call", "expected"), METABALL_CASES)
def test_metaball_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


MISC_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: misc.cylindrical_extrude(square([10, 5])), "positive inner and outer"),
    (lambda: misc.cylindrical_extrude(square([10, 5]), inner_radius=20), "positive inner and outer"),
    (lambda: misc.cylindrical_extrude(square([10, 5]), inner_radius=0, outer_radius=20), "positive inner and outer"),
    (lambda: misc.cylindrical_extrude(square([10, 5]), inner_radius=20, outer_radius=0), "positive inner and outer"),
    (lambda: misc.minkowski_difference(circle(radius=10)), "at least one diff shape"),
    (lambda: Path2D([[0.0, 0.0]]).path_extrude2d(square([4, 4])), "at least two points"),
    (lambda: Path3D([[0.0, 0.0, 0.0]]).path_extrude(circle(radius=2)), "at least two points"),
]


@pytest.mark.parametrize(("call", "expected"), MISC_CASES)
def test_extrusion_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


def _flat(_x: float, _y: float) -> float:
    """A trivial height function for the surface plotters."""
    return 1.0


SURFACE_CASES: list[tuple[Callable[[], object], str]] = [
    # cylindrical_heightfield: the length and the two radii each have to be a positive number
    (lambda: surfaces.cylindrical_heightfield(_flat, radius=10), "length= or height="),
    (lambda: surfaces.cylindrical_heightfield(_flat, length=0, radius=10), "length= or height="),
    (lambda: surfaces.cylindrical_heightfield(_flat, length=20), "radius="),
    (lambda: surfaces.cylindrical_heightfield(_flat, length=20, radius=0), "radius="),
    (lambda: surfaces.cylindrical_heightfield(_flat, length=20, radius1=10), "radius2="),
    (lambda: surfaces.cylindrical_heightfield(_flat, length=20, radius1=10, radius2=0), "radius2="),
    (lambda: surfaces.cylindrical_heightfield(_flat, length=20, radius=10, base=0), "base= must be"),
    # plot3d: a surface needs at least two samples in each direction
    (lambda: surfaces.plot3d(_flat, [0.0], [0.0, 1.0]), "at least 2 points"),
    (lambda: surfaces.plot3d(_flat, [0.0, 1.0], [0.0]), "at least 2 points"),
    # plot_revolution: the angle sweep and the profile both need at least two values
    (lambda: surfaces.plot_revolution(_flat, [30.0], z=[0.0, 10.0], radius1=5, radius2=5), "at least 2 values"),
    (lambda: surfaces.plot_revolution(_flat, [0.0, 90.0], z=[0.0, 10.0]), "give z with radius1"),
    (lambda: surfaces.plot_revolution(_flat, [0.0, 90.0], z=[0.0], radius1=5, radius2=5), "give z with radius1"),
    # the rest
    (lambda: surfaces.textured_tile("diamonds", size=[20, 20, 2]), "tex_reps or tex_size"),
    (lambda: surfaces.ruler(length=50, depth=6), "smaller than depth"),
    (lambda: surfaces.ruler(length=50, colors=["red"]), "exactly two colors"),
]


@pytest.mark.parametrize(("call", "expected"), SURFACE_CASES)
def test_surface_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


TEXT_PATH = [[0.0, 0.0], [60.0, 0.0]]
TEXT_PATH3 = [[0.0, 0.0, 0.0], [60.0, 0.0, 0.0]]

EXTRUSION_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: s3.path_text(TEXT_PATH, "", size=5), "must be non-empty"),
    (lambda: s3.path_text(TEXT_PATH, "hi", size=0), "positive text size"),
    (lambda: s3.path_text(TEXT_PATH3, "hi", size=5, normal=[0, 0, 1], top=[0, 1, 0]), "both"),
    (lambda: s3.path_text([[0.0, 0.0, 0.0, 0.0], [1.0, 1.0, 1.0, 1.0]], "hi", size=5), "2d or 3d path"),
    (lambda: s3.path_text(TEXT_PATH, "hello", size=5, lettersize=[5.0] * 5, kern=[1.0]), "kern must be"),
    (lambda: s3.path_text(Path2D(TEXT_PATH), "a very long string", size=5, lettersize=[20.0] * 18), "too short"),
    (lambda: s3.path_text(TEXT_PATH, "hi", size=5, thickness=2), "thickness with a 2d path"),
    (lambda: s3.path_text(TEXT_PATH, "hi", size=5, reverse=True), "reverse not allowed"),
    (lambda: s3.path_text(TEXT_PATH, "hi", size=5, offset=2), "offset with a 2d path"),
    (lambda: s3.path_text(TEXT_PATH, "hi", size=5, normal=[0, 0, 1]), 'define "normal" for a 2d path'),
    (lambda: s3.path_text(TEXT_PATH, "hi", size=5, lettersize=[5.0]), "lettersize list"),
    (lambda: s3.path_text(TEXT_PATH, "hi", size=[5.0, 5.0]), "per-character widths go in lettersize"),
    (lambda: s3.path_text(TEXT_PATH, "hi", size=5), "no textmetrics"),
    (lambda: s3.cross(height=0), "positive height"),
]


@pytest.mark.parametrize(("call", "expected"), EXTRUSION_CASES)
def test_extrusion_and_text_rejections(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


ARC_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: s2.arc(width=10, thickness=3, radius=5), "conflicting arc"),
    (lambda: s2.arc(corner=[[0, 0], [10, 0]], radius=5), "exactly 3 points"),
    (lambda: s2.arc(corner=[[0, 0], [10, 0], [10, 10]]), "needs radius="),
    (lambda: s2.arc(corner=[[0, 0], [10, 0], [10, 10]], radius=0), "needs radius="),
    (lambda: s2.arc(points=[[0, 0, 0], [5, 5, 0], [10, 0, 0]]), "2-D points only"),
    (lambda: s2.arc(points=[[0, 0], [5, 5], [10, 0], [15, 5]]), "needs 2 or 3 points"),
    (lambda: s2.arc(radius=5, angle=[0, 90], start=10), "start= is not allowed"),
    (lambda: s2.arc(points=[[0, 0], [10, 0]]), "center= is required"),
    (lambda: s2.arc(points=[[5, 5], [5, 5]], center=[0, 0]), "endpoints are equal"),
    (lambda: s2.arc(points=[[0, 0], [5, 0], [10, 0]]), "collinear"),
    (lambda: s2.keyhole(length=0, radius1=3, radius2=6), "length must be positive"),
    (lambda: s2.ring(radius1=10, radius2=6, angle=90), "full-annulus"),
]


@pytest.mark.parametrize(("call", "expected"), ARC_CASES)
def test_arc_and_ring_rejections(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


SQUARE_OUTLINE = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
SPINE = [[0.0, 0.0, 0.0], [0.0, 0.0, 20.0]]
SQUARE_PATH = Path2D([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]])

BEZIER_CASES: list[tuple[Callable[[], object], str]] = [
    # create_bezier: the two size spellings are alternatives, and both must be positive
    (lambda: beziers.create_bezier(SQUARE_PATH, size=2, relsize=0.5), "both size and relsize"),
    (lambda: beziers.create_bezier(SQUARE_PATH, size=0), "greater than zero"),
    (lambda: beziers.create_bezier(SQUARE_PATH, size=[1.0, 2.0]), "must have length"),
    # Bezier: the control points have a required shape and dtype
    (lambda: beziers.Bezier([[0.0, 0.0, 0.0, 0.0]]), "must be 2-D or 3-D"),
    # the handle builders take phi only for 3-D points
    (lambda: beziers.Bezier.begin([0.0, 0.0], angle=30, radius=5, phi=45), "phi= requires a 3-D point"),
    (lambda: beziers.Bezier.tang([0.0, 0.0], angle=30, radius1=5, phi=45), "phi= requires a 3-D point"),
    (lambda: beziers.Bezier.end([0.0, 0.0], angle=30, radius=5, phi=45), "phi= requires a 3-D point"),
    (
        lambda: beziers.Bezier.joint([0.0, 0.0], angle1=30, angle2=60, radius1=5, radius2=5, phi1=45),
        "require a 3-D point",
    ),
    # a scalar angle needs a radius to turn it into a control point
    (lambda: beziers.Bezier.begin([0.0, 0.0], angle=30), "radius must be given"),
    (lambda: beziers.Bezier.joint([0.0, 0.0], angle1=30, angle2=60), "radius must be given"),
    # BezierPatch: rows, columns, 3-D points
    (lambda: beziers.BezierPatch([[[0.0, 0.0]]]), "must be 3-D"),
]


@pytest.mark.parametrize(("call", "expected"), BEZIER_CASES)
def test_bezier_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


def test_two_dimensional_only_bezier_operations_reject_3d() -> None:
    """close_to_axis and path_offset are planar operations (SPEC E-4)."""
    spatial = beziers.Bezier([[0.0, 0.0, 0.0], [5.0, 5.0, 5.0], [10.0, 0.0, 0.0]])
    with pytest.raises(ValueError, match="only on 2-D bezier paths"):
        spatial.close_to_axis()
    with pytest.raises(ValueError, match="only on 2-D bezier paths"):
        spatial.path_offset(np.array([0.0, 1.0]))


TEXTURE_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: texture("trunc_pyramids_vnf", border=0.6), "border in"),
    (lambda: texture("trunc_ribs_vnf", border=-0.1), "border>=0"),
    (lambda: texture("trunc_ribs_vnf", gap=-0.1), "gap>=0"),
    (lambda: texture("trunc_ribs_vnf", gap=0.9, border=0.4), r"2\*border\+gap"),
    (lambda: texture("bricks_vnf", border=-0.1), "border>=0"),
    (lambda: texture("bricks_vnf", gap=0), "gap>0"),
    (lambda: texture("bricks_vnf", gap=0.4, border=0.3), "gap\\+border"),
    (lambda: texture("checkers", border=0.7), "border in"),
    (lambda: texture("trunc_diamonds", border=0.7), "border in"),
    (lambda: texture("tri_grid", border=0.5), "border in"),
    (lambda: texture("cones", border=0.7), "border in"),
    (lambda: texture("dots", border=0.7), "border in"),
    (lambda: texture("hex_grid", border=0.7), "border in"),
    (lambda: texture("diamonds", border=0.2, inset=0.1), "not both"),
]


@pytest.mark.parametrize(("call", "expected"), TEXTURE_CASES)
def test_texture_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


TRIANGLE = [[0.0, 0.0], [10.0, 0.0], [5.0, 8.0]]

SKIN_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: skin.os_circle(), "radius is required"),
    (lambda: skin.os_profile([[1.0, 0.0], [1.0, 1.0]]), "First point of the profile"),
    (lambda: skin.subdivide_and_slice([TRIANGLE, TRIANGLE], slices=2, numpoints=2), "smaller than"),
    (lambda: skin.rot_resample([[0.0, 0.0, 0.0], [0.0, 0.0, 90.0]], num_copies=3, smoothlen=0), "positive odd"),
    (lambda: skin.rot_resample([[0.0, 0.0, 0.0], [0.0, 0.0, 90.0]], num_copies=1.5), "must be an integer"),
]


@pytest.mark.parametrize(("call", "expected"), SKIN_CASES)
def test_skin_helper_rejections(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


def test_sweep_and_prism_rejections() -> None:
    """The sweep family states what a usable profile and path look like (SPEC E-4)."""
    with pytest.raises(ValueError, match="at least 3 points"):
        Path2D([[0.0, 0.0], [10.0, 0.0]]).sweep([np.eye(4), np.eye(4)])
    with pytest.raises(ValueError, match="length 2 or more"):
        Path2D(TRIANGLE).sweep([np.eye(4)])
    # the receiver is the path and the argument is the profile, so a one-point path is the path
    with pytest.raises(ValueError, match="at least 2 points"):
        Path3D([[0.0, 0.0, 0.0]]).path_sweep(Path2D(TRIANGLE))
    with pytest.raises(ValueError, match="positive height"):
        Path2D(TRIANGLE).spiral_sweep(height=0, radius=10, turns=2)
    with pytest.raises(ValueError, match="nonzero turns"):
        Path2D(TRIANGLE).spiral_sweep(height=10, radius=10, turns=0)


CUBOID_FIELD = sdf3.cuboid([10.0, 10.0, 10.0])

SDF_3D_CASES: list[tuple[Callable[[], object], str]] = [
    # cylinders: shift and the rim treatments are alternatives, as are rounding and chamfer
    (lambda: sdf3.cyl(height=10, radius=4, shift=[2, 0], rounding=1), "shift="),
    (lambda: sdf3.cyl(height=10, radius=4, rounding=1, chamfer=1), "both chamfer"),
    (lambda: sdf3.tube(height=10, outer_radius=6, wall=1, rounding=1, chamfer=1), "both chamfer"),
    (lambda: sdf3.rect_tube(height=10, size=[20, 20]), "isize or wall"),
    # polygon_prism: the outline and the rim treatments both have to make sense
    (lambda: sdf3.polygon_prism([], 10), "must not be empty"),
    (lambda: sdf3.polygon_prism([SQUARE_OUTLINE], 5, rounding_bottom=9), "smaller than"),
    (lambda: sdf3.polygon_prism([SQUARE_OUTLINE], 5, chamfer_top=9), "smaller than"),
    (lambda: sdf3.polygon_prism([SQUARE_OUTLINE], 5, chamfer_bottom=9), "smaller than"),
    # sweeps
    (lambda: sdf3.path_sweep([[0.0, 0.0], [5.0, 0.0]], SPINE), "at least 3 points"),
    (lambda: sdf3.path_sweep(SQUARE_OUTLINE, [[0.0, 0.0, 0.0]]), "at least 2 points"),
    (lambda: sdf3.stroke_3d([[0.0, 0.0, 0.0]], width=2), "at least 2 points"),
    # transforms and combinators
    (lambda: CUBOID_FIELD.mirror([0, 0, 0]), "must be nonzero"),
    (lambda: CUBOID_FIELD.multmatrix([[1, 0], [0, 1]]), "4x4 matrix"),
    (lambda: CUBOID_FIELD.distribute_on_path(Path3D(SPINE)), "num_copies"),
    (lambda: sdf3.PyShape.difference("not a shape", CUBOID_FIELD), "must be a PyShape"),
    (lambda: CUBOID_FIELD.hull([[0.0, 0.0], [1.0, 1.0]]), "Nx3"),
    # round()/chamfer() need the per-edge state a plain field does not carry
    (lambda: sdf3.sphere(radius=5).round(1), "cuboid-shaped"),
]


@pytest.mark.parametrize(("call", "expected"), SDF_3D_CASES)
def test_sdf_solid_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


def test_polygon_prism_rejects_a_non_sequence_with_a_type_error() -> None:
    """A wrong *type* is a TypeError; a wrong *value* is a ValueError (PLAN E-P1)."""
    with pytest.raises(TypeError, match="must be a list of points"):
        sdf3.polygon_prism("not a path", 10)


SDF_2D_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: sdf2.rect2d([20, 10], rounding=2, chamfer=2), "rounding and chamfer"),
    (lambda: sdf2.rect2d([20, 10], rounding=[1, 2, 3]), "needs 4 values"),
    (lambda: sdf2.rect2d([20, 10], rounding=[9, 9, 9, 9]), "exceeds half"),
    (lambda: sdf2.polygon2d([[[0.0, 0.0], [10.0, 0.0]]]), "every path needs"),
    (lambda: sdf2.region2d([[[0.0, 0.0], [10.0, 0.0]]]), "every outline needs"),
    (lambda: sdf2.stroke2d([[0.0, 0.0]], width=2), "at least 2 points"),
    (lambda: sdf2.hull2d_discs([]), "at least one disc"),
    (lambda: sdf2.trapezoid2d(height=10, width1=-1, width2=5), "Degenerate"),
    (lambda: sdf2.trapezoid2d(height=10, width1=5, width2=-1), "Degenerate"),
    (lambda: sdf2.trapezoid2d(height=-1, width1=5, width2=5), "Degenerate"),
    (lambda: sdf2.circle2d(radius=5).rotate([0, 0, 0, 0]), "only supports"),
    (lambda: sdf2.circle2d(radius=5).rotate([10, 0, 0]), "only supports"),
    (lambda: sdf2.circle2d(radius=5).rotate([0, 10, 0]), "only supports"),
    (lambda: sdf2.circle2d(radius=5).scale([0, 1]), "must be positive"),
    (lambda: sdf2.PyShape2D.union([]), "at least one shape"),
    (lambda: sdf2.circle2d(radius=5).extrude(0), "needs height > 0"),
]


@pytest.mark.parametrize(("call", "expected"), SDF_2D_CASES)
def test_sdf_flat_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


SDF_PATH_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: sdfp.as_points([0.0, 1.0, 2.0]), "expected a point path"),
    (lambda: sdfp.egg_path(length=20, radius1=4, radius2=6, arc_radius=5), "must be larger"),
    (lambda: sdfp.egg_path(length=5, radius1=4, radius2=6, arc_radius=40), "longer than radius1"),
    (lambda: sdfp.path_to_bezpath(SQUARE_OUTLINE, size=2, relsize=0.5), "both size and relsize"),
    (
        lambda: sdfp.path_to_bezpath([[0.0, 0.0], [0.0, 0.0], [5.0, 5.0]], tangents=[[1.0, 0.0]] * 3, size=1),
        "zero-length path segment",
    ),
    (lambda: sdfp.path_cut_points(SQUARE_OUTLINE, [20.0, 5.0]), "increasing list"),
    (lambda: sdfp.path_cut_points(SQUARE_OUTLINE, [500.0]), "too short"),
    (lambda: sdfp.round_corners([[0.0, 0.0], [10.0, 0.0]], radius=1), "Length must be 3"),
    (lambda: sdfp.round_corners(SQUARE_OUTLINE), "Must specify radius"),
]


@pytest.mark.parametrize(("call", "expected"), SDF_PATH_CASES)
def test_sdf_path_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


NURBS_PTS = [[0.0, 0.0], [5.0, 8.0], [10.0, 0.0], [15.0, 8.0]]
NURBS_PATCH = [[[0.0, 0.0, 0.0], [5.0, 0.0, 2.0]], [[0.0, 5.0, 2.0], [5.0, 5.0, 0.0]]]

NURBS_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: nurbs.NurbsCurve(NURBS_PTS, 2, weights=[1.0, 1.0]), "weights must match"),
    (lambda: nurbs.NurbsCurve(NURBS_PTS, 9), "needs at least"),
    (lambda: nurbs.NurbsCurve(NURBS_PTS, 2).elevate_degree(-1), "zero or a positive integer"),
    (lambda: nurbs.NurbsCurve([[0.0, 0.0, 0.0, 0.0]] * 4, 2), "must be 2-D or 3-D"),
    (lambda: nurbs.NurbsCurve(NURBS_PTS, 2.5), "degree must be a positive integer"),
    (lambda: nurbs.NurbsCurve(NURBS_PTS, 2, nurbs_type="wobbly"), "unknown NURBS type"),
    (lambda: nurbs.NurbsPatch([[0.0, 0.0, 0.0]], (1, 1)), "rectangular grid"),
    (lambda: nurbs.NurbsPatch([[[0.0, 0.0]] * 2] * 2, (1, 1)), "control points must be 3-D"),
    (lambda: nurbs.NurbsPatch(NURBS_PATCH, (1.5, 1)), "degree must be positive integers"),
    (lambda: nurbs.NurbsPatch(NURBS_PATCH, (1, 1), nurbs_type=("wobbly", "clamped")), "unknown NURBS type"),
]


@pytest.mark.parametrize(("call", "expected"), NURBS_CASES)
def test_nurbs_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


OPEN_SQUARE = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]

PATH_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: Path2D([0.0, 1.0, 2.0]), r"needs a list of \[x, y\] points"),
    (lambda: Path2D(OPEN_SQUARE).catenary(width=0, droop=2), "needs width > 0"),
    (lambda: Path2D(OPEN_SQUARE).catenary(width=10, droop=2, sides=1.5), "positive integer sides"),
    (lambda: Path2D(OPEN_SQUARE).catenary(width=10, droop=2, sides=0), "positive integer sides"),
    (lambda: Path2D(OPEN_SQUARE).catenary(width=10, angle=100), r"0 < \|angle\|"),
    (lambda: Path2D(OPEN_SQUARE, closed=True).offset(delta=-500), "collapsed the path"),
    (lambda: Path3D([0.0, 1.0, 2.0]), r"needs a list of \[x, y, z\] points"),
    (lambda: Path3D.helix(radius=5, length=0, angle=30), "cannot take an angle with length 0"),
    (lambda: Path3D([[0.0, 0.0, 0.0], [5.0, 0.0, 0.0], [10.0, 0.0, 0.0]]).normals(), "collinear points"),
    (lambda: Path3D(SPINE).cut([500.0]), "smaller than the path"),
    (lambda: Path3D(SPINE).cut([0.0]), "strictly positive"),
    (lambda: Path3D(SPINE).subdivide_path(), "exactly one of"),
    (lambda: Path3D(SPINE).subdivide_path(points="many"), "must be positive number"),
    (lambda: Path3D(SPINE).subdivide_path(points=0), "must be positive number"),
    (lambda: Path3D(SPINE).resample_path(), "exactly one of num_copies"),
]


@pytest.mark.parametrize(("call", "expected"), PATH_CASES)
def test_path_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


def test_offsetting_an_open_path_is_rejected_internally() -> None:
    """The guard lives on the internal entry point.

    `Path2D.offset()` does not pass its own `closed` flag down, so an open path is offset as if it
    were closed; only `_offset(closed=False)` reaches the rejection. Exercised here because the
    rejection is real code, and the inconsistency is worth a test that says so out loud.
    """
    with pytest.raises(ValueError, match="Open paths are not supported"):
        Path2D(OPEN_SQUARE)._offset(delta=2, closed=False)

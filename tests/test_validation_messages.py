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

import pathlib
from typing import TYPE_CHECKING

import numpy as np
import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

import pybosl2.beziers as beziers
import pybosl2.distributors as dist
import pybosl2.masking as masking
import pybosl2.miscellaneous as misc
import pybosl2.nurbs as nurbs
import pybosl2.partitions as partitions
import pybosl2.parts.nema_steppers as nema
import pybosl2.parts.threading as threading
import pybosl2.paths as paths
import pybosl2.quaternions as quaternions
import pybosl2.sdf.joiners as joiners
import pybosl2.sdf.paths as sdfp
import pybosl2.sdf.shapes2d as sdf2
import pybosl2.sdf.shapes3d as sdf3
import pybosl2.sdf.skin as sdfskin
import pybosl2.shapes2d as s2
import pybosl2.shapes3d as s3
import pybosl2.skin as skin
import pybosl2.surfaces3d as surfaces
from pybosl2 import Anchor
from pybosl2.caps import CapSpec, CapType
from pybosl2.color import Color
from pybosl2.enums import ResampleMethod, RoundingMethod
from pybosl2.exceptions import Bosl2ValueError
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
from pybosl2.parts.ball_bearings import BallBearings
from pybosl2.parts.hinges import KnuckleHinge
from pybosl2.parts.hooks import RingHook
from pybosl2.parts.modular_hose import HoseSegment
from pybosl2.path2d import Path2D
from pybosl2.path3d import Path3D
from pybosl2.points import Point
from pybosl2.regions import Region
from pybosl2.rounding import _round_corners
from pybosl2.shapes2d import circle, square
from pybosl2.shapes3d import cuboid
from pybosl2.texture import texture
from pybosl2.turtle import turtle2d, turtle3d
from pybosl2.turtle.turtle3d import TurtleCommand, TurtleCommandType
from pybosl2.vnf import VNF

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
    # 3-D points are now refused by `Path2D` itself rather than by `arc()`: typing the parameter
    # moved the dimension check to construction, which is the one place that can make it once
    # (SPEC C-7a). The message names the type, not the caller's function.
    (lambda: Path2D([[0, 0, 0], [5, 5, 0], [10, 0, 0]]), "Path2D needs \\[x, y\\] points"),
    (lambda: s2.arc(points=Path2D([[0, 0], [5, 5], [10, 0], [15, 5]])), "needs 2 or 3 points"),
    (lambda: s2.arc(radius=5, angle=[0, 90], start=10), "start= is not allowed"),
    (lambda: s2.arc(points=Path2D([[0, 0], [10, 0]])), "center= is required"),
    (lambda: s2.arc(points=Path2D([[5, 5], [5, 5]]), center=[0, 0]), "endpoints are equal"),
    (lambda: s2.arc(points=Path2D([[0, 0], [5, 0], [10, 0]])), "collinear"),
    (lambda: s2.keyhole(length=0, radius1=3, radius2=6), "length must be positive"),
    (lambda: s2.ring(radius1=10, radius2=6, angle=90), "full-annulus"),
]


@pytest.mark.parametrize(("call", "expected"), ARC_CASES)
def test_arc_and_ring_rejections(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


SQUARE_OUTLINE = Path2D([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]])
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
    (lambda: skin.os_profile(Path2D([[1.0, 0.0], [1.0, 1.0]])), "First point of the profile"),
    (lambda: skin.subdivide_and_slice([Path2D(TRIANGLE), Path2D(TRIANGLE)], slices=2, numpoints=2), "smaller than"),
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
    (lambda: sdf3.path_sweep(Path2D([[0.0, 0.0], [5.0, 0.0]]), Path3D(SPINE)), "at least 3 points"),
    (lambda: sdf3.path_sweep(SQUARE_OUTLINE, Path3D([[0.0, 0.0, 0.0]])), "at least 2 points"),
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


def test_polygon_prism_names_the_wrapper_for_a_non_path() -> None:
    """A non-`Path` argument names the type to wrap it in, rather than only its own wrongness.

    This used to raise a bare `TypeError("must be a list of points or numpy array")` from a
    hand-rolled isinstance check. SPEC E-4 wants a `Bosl2ValueError` that says what to pass, and
    C-7b wants that to name the type -- which is what the shared guard produces for every converted
    parameter, so the special case went away rather than being restated.

    A string is not offered a wrapper: `Path2D("not a path")` is not the fix, so the message names
    the type it wanted and echoes what it got instead.
    """
    with pytest.raises(Bosl2ValueError, match="must be a sequence of Path2D/Path3D"):
        sdf3.polygon_prism("not a path", 10)  # type: ignore[arg-type]
    with pytest.raises(Bosl2ValueError, match=r"Path2D\("):
        sdf3.polygon_prism([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]], 10)  # type: ignore[arg-type]


SDF_2D_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: sdf2.rect2d([20, 10], rounding=2, chamfer=2), "rounding and chamfer"),
    (lambda: sdf2.rect2d([20, 10], rounding=[1, 2, 3]), "needs 4 values"),
    (lambda: sdf2.rect2d([20, 10], rounding=[9, 9, 9, 9]), "exceeds half"),
    (lambda: sdf2.polygon2d([Path2D([[0.0, 0.0], [10.0, 0.0]])]), "every path needs"),
    (lambda: sdf2.region2d([Path2D([[0.0, 0.0], [10.0, 0.0]])]), "every outline needs"),
    (lambda: sdf2.stroke2d(Path2D([[0.0, 0.0]]), width=2), "at least 2 points"),
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
        lambda: sdfp.path_to_bezpath(Path2D([[0.0, 0.0], [0.0, 0.0], [5.0, 5.0]]), tangents=[[1.0, 0.0]] * 3, size=1),
        "zero-length path segment",
    ),
    (lambda: sdfp.path_cut_points(SQUARE_OUTLINE, [20.0, 5.0]), "increasing list"),
    (lambda: sdfp.path_cut_points(SQUARE_OUTLINE, [500.0]), "too short"),
    (lambda: sdfp.round_corners(Path2D([[0.0, 0.0], [10.0, 0.0]]), radius=1), "Length must be 3"),
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


def _unit_height(_x: float, _y: float) -> float:
    """A flat height function for the cylindrical heightfield."""
    return 1.0


SHAPE_INPUT_CASES: list[tuple[Callable[[], object], str]] = [
    # array shape and dtype: the message says what shape was expected and what arrived
    (lambda: beziers.Bezier([0.0, 1.0, 2.0]), "must be a 2-D array"),
    (lambda: beziers.BezierPatch([[0.0, 1.0], [2.0, 3.0]]), "must be a 3-D array"),
    (lambda: nurbs.NurbsCurve([[0.0, 0.0], [5.0, 5.0]], 3), "needs at least 4 control points"),
    # rounding needs a path with no repeats and no reversals at the corners it is rounding
    (
        lambda: Path2D([[0.0, 0.0], [0.0, 0.0], [10.0, 0.0], [10.0, 10.0]], closed=True).round_corners(radius=1),
        "Repeated point in path",
    ),
    (
        lambda: Path2D([[0.0, 0.0], [10.0, 0.0], [0.0, 0.0], [5.0, 8.0]], closed=True).round_corners(radius=1),
        "turns back on itself",
    ),
    (
        # the previous point repeats: reachable only when the earlier corner is not being
        # rounded, so the loop does not stop there first
        lambda: Path2D([[0.0, 0.0], [10.0, 0.0], [10.0, 0.0], [5.0, 8.0]], closed=True).round_corners(
            radius=[1, 0, 1, 1]
        ),
        "Repeated point in path",
    ),
    (lambda: s2.arc(corner=[[0.0, 0.0], [5.0, 0.0], [10.0, 0.0]], radius=2), "Collinear corner"),
    # a cylindrical heightfield has to fit around its own circumference
    (lambda: surfaces.cylindrical_heightfield(_unit_height, length=20, radius=0.5), "needs a radius of at least"),
]


@pytest.mark.parametrize(("call", "expected"), SHAPE_INPUT_CASES)
def test_shape_input_rejections_say_what_arrived(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


TURTLE_CASES: list[tuple[Callable[[], object], str]] = [
    # a 2-D turtle rejects anything that would leave the plane
    (lambda: turtle2d([TurtleCommand(TurtleCommandType.SETDIR, size=Point(1.0, 0.0, 1.0))]), "z-component must be 0"),
    (
        lambda: turtle2d(
            [
                TurtleCommand(
                    TurtleCommandType.MOVE,
                    size=5.0,
                    is_compound=True,
                    rotation_type=TurtleCommand.RotationType.UP,
                    angle=30,
                )
            ]
        ),
        'z-axis sub-command "up"',
    ),
    (
        lambda: turtle2d([TurtleCommand(TurtleCommandType.MOVE, size=5.0, is_compound=True, grow=2.0)]),
        "z-axis sub-commands",
    ),
    # arcs need both a radius and an angle, and they must be numbers
    (lambda: turtle2d([TurtleCommand(TurtleCommandType.ARCLEFT, angle=90)]), "needs a numeric radius"),
    (lambda: turtle2d([TurtleCommand(TurtleCommandType.ARCZROT, angle=45)]), "needs a numeric radius"),
    (
        lambda: turtle2d(
            [
                TurtleCommand(
                    TurtleCommandType.ARC,
                    size=5.0,
                    is_compound=True,
                    rotation_type=TurtleCommand.RotationType.LEFT,
                    angle=90,
                    radius=0,
                )
            ]
        ),
        "non-zero radius",
    ),
    (
        lambda: turtle2d(
            [
                TurtleCommand(
                    TurtleCommandType.ARC,
                    size=5.0,
                    is_compound=True,
                    rotation_type=TurtleCommand.RotationType.LEFT,
                    angle=0,
                    radius=5,
                )
            ]
        ),
        "non-zero rotation angle",
    ),
    # "until" only terminates if the heading actually crosses the goal line
    (
        lambda: turtle2d(
            [TurtleCommand(TurtleCommandType.LEFT, angle=90), TurtleCommand(TurtleCommandType.UNTILX, size=50.0)]
        ),
        "never reaches the goal",
    ),
    (lambda: turtle2d([TurtleCommand(TurtleCommandType.UNTILY, size=50.0)]), "never reaches the goal"),
]


@pytest.mark.parametrize(("call", "expected"), TURTLE_CASES)
def test_turtle_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


def _box() -> object:
    """A plain 20 mm box to hang edge and corner masks on."""
    return cuboid([20, 20, 20]).shape


MASK_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: masking.edge_mask(_box(), mask=Path2D(OPEN_SQUARE)), "size="),
    (lambda: masking.edge_mask(_box(), size=(20, 20, 20)), "mask="),
    (lambda: masking.edge_profile(_box(), mask=Path2D(OPEN_SQUARE)), "size="),
    (lambda: masking.edge_profile(_box(), size=(20, 20, 20)), "mask="),
    (lambda: masking.corner_profile(_box(), corners="ALL", radius=2, size=(20, 20, 20)), "Legacy string"),
    (
        lambda: masking.corner_profile(_box(), except_corners="TOP", radius=2, size=(20, 20, 20)),
        "Legacy string",
    ),
    (lambda: masking.corner_profile(_box(), size=(20, 20, 20)), "radius or diameter"),
    (lambda: masking.face_profile(_box(), size=(20, 20, 20)), "radius or diameter"),
]


@pytest.mark.parametrize(("call", "expected"), MASK_CASES)
def test_mask_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


DISTRIBUTOR_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: dist.grid_copies(spacing=5, size=[20, 20], stagger="sometimes"), "stagger must be"),
    (lambda: dist.grid_copies(spacing=5, size=[20, 20], axes="xyz"), "invalid axes"),
    (lambda: dist.grid_copies(spacing=5, size=[20, 20], axes="xx"), "invalid axes"),
    (lambda: dist.grid_copies(spacing=5, size=[20, 20], axes="qy"), "invalid axes"),
    (lambda: dist.rot_copies(rots=3, v=[0, 0, 1], subrot=False, delta=0), "subrot can only be False"),
    (lambda: dist.path_copies(Path2D(OPEN_SQUARE), spacing=5, start_pos=-100), "don't fit on the path"),
    (lambda: dist.path_copies(Path2D(OPEN_SQUARE), spacing=5, num_copies=200), "don't fit on the path"),
    (lambda: dist.xdistribute([], spacing=5), "at least one child"),
]


@pytest.mark.parametrize(("call", "expected"), DISTRIBUTOR_CASES)
def test_distributor_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


CURVE_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: s2.star(radius=10, inner_radius=5), "must specify tips"),
    (lambda: s2.teardrop2d(radius=10, cap_height=1), "cap_height cannot be less"),
    (lambda: s2.egg(length=30, radius1=5), "must give radius2"),
    (lambda: s2.egg(length=30, radius1=5, radius2=8), "must give arc_radius"),
    (lambda: s2.egg(radius1=5, radius2=8, arc_radius=40), "must give length"),
    (lambda: s2.egg(length=30, radius1=5, radius2=8, arc_radius=10), "larger than length/2"),
    (lambda: s2.egg(length=10, radius1=6, radius2=8, arc_radius=40), "longer than radius1"),
    (lambda: s2.squircle(size=20, style="quadratic"), 'only the default "fg" style'),
]


@pytest.mark.parametrize(("call", "expected"), CURVE_CASES)
def test_curve_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


QUATERNION_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: quaternions.quaternion(rpy=[10.0, 20.0]), "must be a sequence of 3"),
    (lambda: quaternions.Quaternion.from_array([1.0, 0.0, 0.0]), "4-element sequence"),
    (lambda: quaternions.Quaternion.from_scalar_vector(1.0, [0.0, 1.0]), "3-element"),
    (lambda: quaternions.Quaternion.from_real_imaginary(1.0, [0.0, 1.0]), "3-element"),
    (lambda: quaternions.Quaternion.from_matrix(np.array([[1.0, 2.0, 3.0]] * 3)), "orthogonal"),
]


@pytest.mark.parametrize(("call", "expected"), QUATERNION_CASES)
def test_quaternion_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


def test_quaternion_division_by_zero_is_an_arithmetic_error() -> None:
    """A zero divisor is ZeroDivisionError, not ValueError -- the type Python users expect."""
    unit = quaternions.Quaternion.from_array([1.0, 0.0, 0.0, 0.0])
    with pytest.raises(ZeroDivisionError, match="must be non-zero"):
        _ = unit / quaternions.Quaternion(0.0, 0.0, 0.0, 0.0)
    with pytest.raises(ZeroDivisionError, match="no length"):
        quaternions.Quaternion.from_axis_angle([0.0, 0.0, 0.0], 45)


CUBOID_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: s3.cuboid([20, 20, 20], chamfer=2, rounding=2), "both chamfer"),
    (lambda: s3.rect_tube(height=10, size=[20, 20], isize=[30, 30]), "not smaller than"),
    (lambda: s3.regular_prism(sides=2.5, height=10, radius=8), "must be an integer"),
    (lambda: s3.regular_prism(sides=2, height=10, radius=8), "must be an integer"),
    (lambda: s3.regular_prism(sides=6, height=10, radius=8, rounding=1, chamfer=1), "both chamfer"),
]


@pytest.mark.parametrize(("call", "expected"), CUBOID_CASES)
def test_cuboid_family_rejections(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


PARTITION_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: partitions.partition_path([object()]), "each pathdesc item"),
    (lambda: partitions.partition_path([-5.0]), "length must be positive"),
    (lambda: partitions.partition_path(["comb 10"]), "unknown section option"),
    (lambda: partitions.partition_path(["comb 30x20x10"]), "LENGTHxWIDTH"),
    (lambda: partitions.partition_path(["comb skew:60"]), "between -45 and 45"),
    (lambda: partitions.partition_path(["comb 1x20"]), "too large for comb"),
    (lambda: partitions.partition_path(["finger 1x10"]), "too large for finger"),
    (lambda: partitions.partition_path(["dovetail 1x10"]), "too large for dovetail"),
    (lambda: partitions.partition_path([10.0], y=0.0), "self-cross"),
]


@pytest.mark.parametrize(("call", "expected"), PARTITION_CASES)
def test_partition_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


_SQ2D = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]

PATH2D_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: Path2D(_SQ2D).subdivide_path(points_per_segment=2), "points_per_segment requires"),
    (lambda: Path2D([[0.0, 0.0], [0.0, 0.0], [1.0, 1.0], [1.0, 1.0]], closed=True).offset(1), "3 distinct points"),
    (lambda: Path2D(_SQ2D, closed=True).offset(-50), "leaves nothing of this outline"),
    (
        lambda: Path2D(_SQ2D, closed=True).intersection(
            Path2D([[10.0, 0.0], [20.0, 0.0], [20.0, 10.0], [10.0, 10.0]], closed=True)
        ),
        "invalid result: LineString",
    ),
]


@pytest.mark.parametrize(("call", "expected"), PATH2D_CASES)
def test_path2d_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


_TRI2D = [[-4.0, -4.0], [4.0, -4.0], [0.0, 4.0]]
_SQC2D = [[-5.0, -5.0], [5.0, -5.0], [5.0, 5.0], [-5.0, 5.0]]

SKIN_MORE_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: VNF.from_skin([_SQC2D, _SQC2D], slices=2), "matching-length z"),
    (lambda: VNF.from_skin([_SQC2D, _SQC2D], slices=2, z=[0.0]), "matching-length z"),
    (lambda: skin.subdivide_and_slice([_SQC2D, _SQC2D], slices=2, numpoints="nope"), "numpoints must be int"),
    (lambda: skin.os_profile(Path2D([[1.0, 1.0], [2.0, 2.0]])), r"First point of the profile must be \[0, 0\]"),
    (
        lambda: Path2D(_SQC2D, closed=True).rounded_prism(height=2, joint_top=3, joint_bottom=3),
        "sum of the bottom and top rim heights",
    ),
    (
        lambda: Path2D(_SQC2D, closed=True).rounded_prism(top=_TRI2D, height=10),
        "same number of",
    ),
    (
        lambda: skin.rot_resample([np.eye(4), np.eye(4)], num_copies=3, method=ResampleMethod.LENGTH),
        "repeated/origin rotation",
    ),
]


@pytest.mark.parametrize(("call", "expected"), SKIN_MORE_CASES)
def test_skin_family_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


NGON_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: s2.regular_ngon(sides=6, radius=10, rounding=1, chamfer=1), "both rounding and chamfer"),
    (lambda: s2.trapezoid(height=10, width1=-1, width2=5), "Degenerate trapezoid"),
    (lambda: s2.trapezoid(height=10, width1=5, width2=-1), "Degenerate trapezoid"),
    (lambda: s2.trapezoid(height=-1, width1=5, width2=5), "Degenerate trapezoid"),
    (lambda: s2.trapezoid(height=10, width1=0, width2=0), "Degenerate trapezoid"),
]


@pytest.mark.parametrize(("call", "expected"), NGON_CASES)
def test_ngon_and_trapezoid_rejections(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


_BUTT = CapSpec(cap_type=CapType.BUTT)

SDF_SHAPES3D_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: sdf3.cyl(height=10, radius=5, shift=[2, 0], rounding=1), "shift= cannot be combined"),
    (lambda: sdf3.cyl(height=10, radius=5, shift=[2, 0], rounding2=1), "shift= cannot be combined"),
    (lambda: sdf3.cyl(height=10, radius=5, rounding=1, chamfer=1), "both chamfer and rounding"),
    (lambda: sdf3.cuboid(size=10, rounding=1, chamfer=1), "both rounding and chamfer"),
    (lambda: (sdf3.cuboid(size=10) | sdf3.sphere(radius=3)).round(1), "requires a cuboid-shaped"),
    (lambda: sdf3.cuboid(size=10).scale([2, 1, 1]).chamfer(1), "requires a cuboid-shaped"),
    (lambda: sdf3.cuboid(size=10).hull([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]]), "must be Nx3 array-likes"),
    (
        lambda: sdf3.convex_polyhedron(Path3D([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [1.0, 1.0, 0.0]])),
        "points are coplanar",
    ),
    (
        lambda: sdf3.convex_polyhedron(Path3D([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [2.0, 2.0, 2.0], [3.0, 3.0, 3.0]])),
        "no supporting planes found",
    ),
    (
        lambda: sdf3.path_sweep(
            Path2D([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]), path=Path3D([[0.0, 0.0, 0.0]] * 2 + [[0.0, 0.0, 5.0]])
        ),
        "repeated point",
    ),
    (
        lambda: sdf3.stroke_3d([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]], width=1, endcap1=_BUTT, endcap2=_BUTT),
        "no drawable segments",
    ),
]


@pytest.mark.parametrize(("call", "expected"), SDF_SHAPES3D_CASES)
def test_sdf_shapes3d_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


_BEZ_PATCH_NAN = [[[float(i), float(j), 0.0] for j in range(4)] for i in range(4)]
_BEZ_PATCH_NAN[1][1][2] = float("nan")

BEZIER_MORE_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: beziers.create_bezier([[0.0, 0.0], [0.0, 0.0], [5.0, 5.0]], tangents=[[1.0, 0.0]] * 3), "zero length"),
    (lambda: beziers.Bezier.tang([0.0, 0.0], angle=45), "radius must be given when angle is a scalar"),
    (lambda: beziers.Bezier([[0.0, 0.0], [1.0, 1.0]]).path_curve(8), "path_curve.*multiple of 3 points"),
    (lambda: beziers.Bezier([[0.0, 0.0], [1.0, 1.0]]).path_arc_length(), "path_arc_length.*multiple of 3 points"),
    (
        lambda: beziers.Bezier([[0.0, 0.0], [1.0, 1.0]]).path_closest_point(np.array([1.0, 1.0])),
        "path_closest_point.*multiple of 3 points",
    ),
    (lambda: beziers.Bezier([[0.0, 0.0]]).path_closest_point(np.array([1.0, 1.0])), "Could not find closest point"),
    (lambda: beziers.BezierPatch(_BEZ_PATCH_NAN).sheet(1, splinesteps=2), "degenerate normals"),
]


@pytest.mark.parametrize(("call", "expected"), BEZIER_MORE_CASES)
def test_more_bezier_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


NURBS_MORE_CASES: list[tuple[Callable[[], object], str]] = [
    (
        lambda: nurbs.NurbsCurve([[0.0, 0.0], [1.0, 2.0], [3.0, 2.0], [4.0, 0.0]], degree=3).curve(splinesteps=0),
        "splinesteps must be a positive integer",
    ),
]


@pytest.mark.parametrize(("call", "expected"), NURBS_MORE_CASES)
def test_more_nurbs_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


SDF_PATHS_MORE_CASES: list[tuple[Callable[[], object], str]] = [
    # the degenerate-outline guards run before any libfive tree is built, so they are reachable
    # without the SDF backend installed.
    (
        lambda: sdfp._polygon_sdf_xy(None, None, np.zeros((3, 2))),
        "no non-degenerate edges",
    ),
    (
        lambda: sdfp._convex_deficiency_sdf(None, None, np.zeros((3, 2)), _depth=16),
        "recursed implausibly deep",
    ),
    (lambda: sdfp.path_tangents(Path2D([[0.0, 0.0], [0.0, 0.0], [1.0, 1.0]]), uniform=False), "zero-length segment"),
    (lambda: sdfp.path_tangents(Path2D([[0.0, 0.0], [1.0, 1.0], [0.0, 0.0]])), "cannot normalize a zero tangent"),
    (lambda: sdfp._v_unit([0.0, 0.0, 0.0]), "cannot normalize a zero vector"),
    (lambda: sdfp.bezpath_points([[0.0, 0.0], [1.0, 1.0]]), "multiple of 3 points"),
]


@pytest.mark.parametrize(("call", "expected"), SDF_PATHS_MORE_CASES)
def test_sdf_path_helper_rejections(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


JOINER_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: joiners.knuckle_hinge(length=20, segs=3, offset=5, arm_angle=45), "arm_angle=90/arm_height=0"),
    (lambda: joiners.knuckle_hinge(length=20, segs=3, offset=5, arm_height=2), "arm_angle=90/arm_height=0"),
    (lambda: joiners.knuckle_hinge(length=20, segs=3, offset=0.1), "at least the knuckle radius"),
    (lambda: joiners.knuckle_hinge(length=20, segs=1, offset=5), "segs must be an integer of 2 or more"),
    (
        lambda: joiners.rabbit_clip(type="bogus", length=20, width=10, snap=1, thickness=2, depth=5),
        "unsupported rabbit_clip type",
    ),
    (
        lambda: joiners.rabbit_clip(type="pin", length=4, width=40, snap=3, thickness=3, depth=5),
        "too wide for its length",
    ),
]


@pytest.mark.parametrize(("call", "expected"), JOINER_CASES)
def test_sdf_joiner_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


_TURTLE3D_RT = TurtleCommand.RotationType

TURTLE3D_CASES: list[tuple[Callable[[], object], str]] = [
    (
        lambda: turtle3d(
            [
                TurtleCommand(
                    TurtleCommandType.ARC, is_compound=True, rotation_type=_TURTLE3D_RT.XROT, angle=90, radius=5
                )
            ]
        ),
        "Rotation acts as twist",
    ),
    (lambda: turtle3d([TurtleCommand(TurtleCommandType.ARC, is_compound=True, radius=5)]), "needs a rotation type"),
    (lambda: turtle3d([TurtleCommand(TurtleCommandType.UNTILZ, size=50.0)]), "never reaches the goal"),
]


@pytest.mark.parametrize(("call", "expected"), TURTLE3D_CASES)
def test_turtle3d_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


_PATH_FOR_DIST = Path2D([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]])

SHAPE_BASE_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: square(2).distribute_on_path(_PATH_FOR_DIST), "provide num_copies, spacing, or dist"),
    (lambda: square(2).distribute_on_path(_PATH_FOR_DIST, start_pos=1.0), "provide num_copies or spacing"),
    (lambda: square(2).anchor_point(Anchor.LEFT, bbox=[[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]), r"bbox must be \[\[min_x"),
    (lambda: square(2).anchor_point(Anchor.LEFT, bbox=[[5.0, 5.0], [0.0, 0.0]]), "max >= min"),
    # a string anchor is rejected wherever it enters, not only in the base constructor
    (lambda: square(2, anchor="left"), "Legacy string anchor"),
    (lambda: circle(radius=5, anchor="left"), "Legacy string anchor"),
    (lambda: cuboid([2, 2, 2], anchor="left"), "Legacy string anchor"),
    (lambda: s2.regular_ngon(sides=2, radius=5), "sides must be 3 or more"),
]


@pytest.mark.parametrize(("call", "expected"), SHAPE_BASE_CASES)
def test_shape_base_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


def test_no_cover_pragmas_are_attached_to_a_statement() -> None:
    """A `# pragma: no cover` on its own line excludes nothing -- it must sit on the statement.

    Coverage matches the pragma against a *line*; a bare comment line is not executable, so the
    guard underneath it stays reported as missing. Keeping the marker on the `if`/`else` header
    (with the reasoning in a comment below it) is what actually excludes the branch.
    """
    root = pathlib.Path(__file__).resolve().parent.parent / "pybosl2"
    stray = [
        f"{path.relative_to(root.parent)}:{lineno}"
        for path in sorted(root.rglob("*.py"))
        for lineno, line in enumerate(path.read_text().splitlines(), start=1)
        if line.strip().startswith("# pragma: no cover")
    ]
    assert not stray, "pragma comment on its own line excludes nothing; move it onto the guard: " + ", ".join(stray)


_P3 = [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 10.0, 0.0]]
_BUTT_CAP = CapSpec(cap_type=CapType.BUTT)

PATH3D_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: Path3D(_P3).cut_points([5.0, 2.0]), "increasing list"),
    (lambda: Path3D(_P3).cut_points([500.0]), "too short for specified cut distance"),
    (lambda: Path3D(_P3).subdivide_path(points_per_segment=2), "points_per_segment requires"),
    (lambda: Path3D([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [0.0, 0.0, 0.0]]).tangents(), "normalize a zero vector"),
    (lambda: Path2D([[0.0, 0.0], [1.0, 1.0], [0.0, 0.0]]).tangents(), "normalize a zero vector"),
]


@pytest.mark.parametrize(("call", "expected"), PATH3D_CASES)
def test_path3d_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


STROKE_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: Path3D([[0.0, 0.0, 0.0]]).stroke(width=1), "at least 2 points"),
    (lambda: Path3D([[0.0, 0.0, 0.0]]).dashed_stroke(dashpat=[5, 2]), "at least 2 points"),
    (
        lambda: Path3D([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]).stroke(width=1, endcap1=_BUTT_CAP, endcap2=_BUTT_CAP),
        "no drawable segments",
    ),
    (lambda: Path2D([[0.0, 0.0]]).stroke(width=1), "at least 2 points"),
    (lambda: Path2D([[0.0, 0.0]]).dashed_stroke(dashpat=[5, 2]), "at least 2 points"),
    (lambda: Path2D(_SQ2D).stroke(width=1, endcap1=CapSpec(cap_type=CapType.CUSTOM)), "CUSTOM requires path="),
]


@pytest.mark.parametrize(("call", "expected"), STROKE_CASES)
def test_stroke_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


MASKING_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: masking.corner_profile(cuboid([10, 10, 10]), radius=2, size=(10, 10, 10), corners="left"), "Legacy str"),
    (lambda: masking.corner_profile(cuboid([10, 10, 10]), radius=2), "size= .the box's size. must be given"),
    (lambda: masking.mask3d_roundover(radius=2, size=(10, 10, 10), corners=Anchor.NONE), "selected no corners"),
    (lambda: masking.mask3d_chamfer(chamfer=2, size=(10, 10, 10), corners=Anchor.NONE), "selected no corners"),
]


@pytest.mark.parametrize(("call", "expected"), MASKING_CASES)
def test_masking_corner_rejections(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


VNF_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: VNF([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], [[0, 1, 2]]).halfspace([0, 0, 1]), r"\[A, B, C"),
    (lambda: VNF.from_metaballs([], bounding_box=None), "spec is empty"),
    (lambda: VNF.from_field(lambda _p: 1.0, 0), "needs a bounding_box"),
]


@pytest.mark.parametrize(("call", "expected"), VNF_CASES)
def test_vnf_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


ROUNDING_CASES: list[tuple[Callable[[], object], str]] = [
    (
        lambda: _round_corners(_TRI2D, method=RoundingMethod.CIRCLE, radius=1, k=0.5),
        'k is only allowed with method="smooth"',
    ),
    (lambda: _round_corners(_TRI2D, method=RoundingMethod.CIRCLE, radius=-1), "radius must be nonnegative"),
    (lambda: _round_corners(_TRI2D, method=RoundingMethod.SMOOTH, joint=1, k=5), r"k must be in \[0, 1\]"),
]


@pytest.mark.parametrize(("call", "expected"), ROUNDING_CASES)
def test_rounding_parameter_rejections(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


_THREAD_PROFILE = [[-0.5, 0.0], [0.0, 0.5], [0.5, 0.0]]

PARTS_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: threading.ThreadedRod(d=10, l=0, pitch=2, profile=_THREAD_PROFILE), "must be positive"),
    (lambda: threading.ThreadHelix(d=10, pitch=0), "must be positive"),
    (lambda: threading.ThreadHelix(d=0, pitch=2), "must be positive"),
    (lambda: RingHook(base_size=[30.0, 20.0, 5.0], hole_z=10, hole=_SQ2D), "custom hole needs or/outer_diameter"),
    (lambda: RingHook(base_size=[30.0, 20.0, 5.0], hole_z=10, outer_radius=5, wall=-2), "hole doesn't fit"),
    (
        lambda: RingHook(base_size=[30.0, 20.0, 5.0], hole_z=10, outer_radius=8, wall=2, hole="square"),
        "hole must be CIRCLE, D or a 2-D path",
    ),
    (lambda: BallBearings.ball_bearing(trade_size=None, inner_diameter=5), "must give outer_diameter"),
    (lambda: BallBearings.ball_bearing(trade_size=None, inner_diameter=5, outer_diameter=10), "must give width"),
    (lambda: KnuckleHinge(length=20, segs=1), "segs must be >= 2"),
    (lambda: HoseSegment(size=0.5, waist_len=-5), "waist_len must be nonnegative"),
    (lambda: nema.NemaMountMask(size=17, atype="bogus"), "atype must be FULL or SCREWS"),
]


@pytest.mark.parametrize(("call", "expected"), PARTS_CASES)
def test_part_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


SHAPE_SIZE_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: s3.cyl(height=10, radius=5, rounding=1, chamfer=1), "both chamfer and rounding"),
    (lambda: s3.tube(height=10, outer_diameter=5, inner_diameter=10), "inner radius is larger"),
    (lambda: s3.cross(size=[10, 10], height=-5), "positive height"),
    (lambda: s2.rect(size=[10, 10], rounding=8), "exceed the rect width"),
    (lambda: s2.rect(size=[30, 4], rounding=3), "exceed the rect height"),
    (lambda: s2.arc(points=Path2D([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]])), "collinear"),
    (lambda: s2.teardrop2d(radius=5, cap_height=1), "cap_height cannot be less than"),
    (
        lambda: s3.rect_tube(height=10, size1=[20, 20], size2=[20, 20], isize2=[10, 10]),
        "needs a bore",
    ),
    (
        lambda: s3.rect_tube(height=10, size=[20, 20], isize1=[10, 10], isize2=[30, 30]),
        "is not smaller than the outer size",
    ),
    (lambda: s3.cuboid([2, 2, 2]).distribute_on_path(_PATH_FOR_DIST), "provide num_copies, spacing, or dist"),
    (lambda: s3.cuboid([2, 2, 2]).anchor_point("left"), "Legacy string anchor"),
]


@pytest.mark.parametrize(("call", "expected"), SHAPE_SIZE_CASES)
def test_shape_size_rejections_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


MISC_MODULE_CASES: list[tuple[Callable[[], object], str]] = [
    (lambda: dist.grid_copies(spacing=5, num_copies=2, axes="xq"), "invalid axes"),
    (lambda: dist.path_copies([[0.0, 0.0], [1.0, 0.0]], num_copies=3, spacing=50), "don't fit on the path"),
    (lambda: partitions.partition_path(["comb 0x"]), "repetition count must be positive"),
    (lambda: partitions.partition_path(["comb 0x20"]), "positive LENGTH and WIDTH"),
    (lambda: Color("#12345"), "invalid hex colour"),
    (lambda: quaternions.Quaternion.from_matrix(np.diag([1.0, 1.0, -1.0])), "special orthogonal"),
    (lambda: Region([Path2D(_SQ2D, closed=True)]).simplify(tolerance=0), "tolerance must be > 0"),
    (lambda: paths.Path(None), "abstract Path class"),
    (
        lambda: surfaces.plot_revolution(lambda _a, _b: 1.0, angle=[0, 90], z=[0, 10], radius1=5),
        "give z with radius1 and radius2",
    ),
    (lambda: sdfskin.skin_sdf([Path2D(_SQ2D, closed=True)], z=[0.0]), "at least 2 profiles"),
    (
        lambda: sdfskin.skin_sdf([Path2D(_SQ2D, closed=True), Path2D(_SQ2D, closed=True)], z=[0.0]),
        "same length",
    ),
    (
        lambda: sdfp.round_corners(Path2D([[0.0, 0.0], [10.0, 0.0], [10.0001, 0.0]]), radius=1),
        "turns back on itself",
    ),
    (lambda: turtle2d([TurtleCommand(TurtleCommandType.XYZMOVE, size=Point(1.0, 1.0, 1.0))]), "z-component must be 0"),
    (lambda: turtle2d([TurtleCommand(TurtleCommandType.ARCLEFTTO, radius=5)]), "needs a numeric angle"),
]


@pytest.mark.parametrize(("call", "expected"), MISC_MODULE_CASES)
def test_misc_module_rejections(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


def test_empty_region_extrude_says_what_is_missing() -> None:
    with pytest.raises(ValueError, match="at least one outline"):
        Region([]).linear_extrude(height=5)


def test_non_passthrough_native_method_is_not_silently_forwarded() -> None:
    """Native methods outside the passthrough set stay hidden, and the error says why."""
    with pytest.raises(AttributeError, match="not in the native passthrough set"):
        _ = cuboid([2, 2, 2]).explode


SIBLING_GUARD_CASES: list[tuple[Callable[[], object], str]] = [
    # each of these is the second of a pair of near-identical guards: the sibling is exercised
    # above, and these hit the other half (top vs bottom, list vs scalar, empty vs malformed).
    (lambda: skin.os_profile(Path2D([])), r"First point of the profile must be \[0, 0\]"),
    (lambda: s3.teardrop(height=10, radius=5, cap_height=1), "cap_height cannot be less than"),
    (
        lambda: s3.tube(height=10, outer_diameter1=20, outer_diameter2=5, inner_diameter=10),
        "inner radius is larger",
    ),
    (
        lambda: _round_corners(_TRI2D, method=RoundingMethod.CIRCLE, radius=1, k=[0.5, 0.5, 0.5]),
        'k is only allowed with method="smooth"',
    ),
    (lambda: dist.path_copies([[0.0, 0.0], [1.0, 0.0]], dist=[50.0]), "don't fit on the path"),
    (lambda: s2.arc(points=Path2D([[0.0, 0.0], [2.0, 0.0]]), center=[1.0, 0.0]), "define a unique arc"),
    (lambda: s2.egg(length=0, radius1=1, radius2=1, arc_radius=10), "length must be positive"),
    (
        lambda: masking.corner_profile(cuboid([10, 10, 10]), radius=2, size=(10, 10, 10), except_corners="left"),
        "Legacy string corner",
    ),
    (lambda: sdf3.xcyl(height=10, radius=5, rounding=1, chamfer=1), "both chamfer and rounding"),
    (lambda: sdf3.cuboid(size=10).hull(np.zeros((2, 2, 3))), "must be Nx3 array-likes"),
]


@pytest.mark.parametrize(("call", "expected"), SIBLING_GUARD_CASES)
def test_sibling_guards_say_what_to_pass(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


_GRID3 = [[[float(i), float(j), 0.0] for j in range(3)] for i in range(3)]
_BEZ = beziers.Bezier([[0.0, 0.0], [1.0, 1.0], [2.0, 0.0], [3.0, 1.0]])

WAS_ASSERTION_CASES: list[tuple[Callable[[], object], str]] = [
    # each of these used to raise AssertionError or a message-less assert: bad input, reported as
    # an internal invariant (and, for the bare asserts, erased entirely under `python -O`).
    (lambda: VNF.vertex_array(_GRID3, caps=True), "caps need col_wrap=True"),
    (lambda: VNF.vertex_array(_GRID3, caps=True, col_wrap=True, row_wrap=True), "cannot be combined with row_wrap"),
    (lambda: VNF.tri_array(_GRID3, caps=True, row_wrap=True), "cannot be combined with row_wrap"),
    (lambda: beziers.Bezier([[0.0, 1.0], [1.0, 2.0], [2.0, 1.0]]).close_to_axis(axis="Z"), 'axis must be "X" or "Y"'),
    (lambda: misc.extrude_from_to(Path2D(_SQ2D, closed=True), [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]), "points must differ"),
    (
        lambda: Path3D([[0.0, 0.0, 0.0], [0.0, 0.0, 10.0]]).path_sweep(Path2D(_SQ2D, closed=True), method="bogus"),
        "unknown method",
    ),
    (
        lambda: (
            threading.ThreadedNut(
                nutwidth=15, id=10, h=8, pitch=2, profile=[[-0.5, 0.0], [0.0, 0.5], [0.5, 0.0]], shape="bogus"
            ).shape
        ),
        "shape must be NutShape",
    ),
    (lambda: _BEZ.derivative(0.5, order=-1), "order must be a non-negative integer"),
    (lambda: _BEZ.derivative(0.5, order=1.5), "order must be a non-negative integer"),
    (lambda: beziers.BezierPatch.flat([100, 100], n_degree=0), "n_degree must be positive"),
    (lambda: Path3D([[0.0, 0.0, 0.0]]).cut_points(1.0), "a closed path needs three points"),
    (lambda: Path3D([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]).cut_points("x"), "a distance or a list of increasing"),
    (lambda: masking.corner_profile(cuboid([10, 10, 10]), radius=0, size=(10, 10, 10)), "must be positive"),
    (lambda: dist.path_copies([[0.0, 0.0], [10.0, 0.0]]), "to say where the copies go"),
    (lambda: sdfp.egg_path(length=0, radius1=1, radius2=1, arc_radius=10), "length must be positive"),
    (lambda: s2.reuleaux_polygon(sides=4, radius=5), "odd number of 3 or more"),
    (lambda: s2.reuleaux_polygon(sides=1, radius=5), "odd number of 3 or more"),
    (
        lambda: skin.rot_resample([np.eye(4), np.eye(4)], num_copies=2, method="length"),
        "method must be a ResampleMethod",
    ),
    (
        lambda: turtle3d([TurtleCommand(TurtleCommandType.ARCLEFT, angle=90)]),
        "needs a numeric radius",
    ),
    (
        lambda: turtle3d([TurtleCommand(TurtleCommandType.ARCXROT, angle=90)]),
        "needs a numeric radius",
    ),
    (
        lambda: turtle3d([TurtleCommand(TurtleCommandType.ARCROT, angle=90)]),
        "needs a numeric radius",
    ),
]


@pytest.mark.parametrize(("call", "expected"), WAS_ASSERTION_CASES)
def test_former_assertions_now_reject_with_value_error(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        call()


# ---------------------------------------------------------------------------
# The SDF backend's own rejections (TASKS T11)
# ---------------------------------------------------------------------------


def test_the_sdf_backend_names_a_shape_it_cannot_build() -> None:
    """An unknown shape name says which one, rather than failing on a None later."""
    import pybosl2.sdf  # noqa: F401  -- registers the sdf backend
    from pybosl2._backend import get_backend, use_backend

    with use_backend("sdf"), pytest.raises(ValueError, match="no shape constructor 'flibbertigibbet'"):
        get_backend().constructor("flibbertigibbet")


def test_the_sdf_linear_extrude_names_an_option_it_has_no_notion_of() -> None:
    """Everything it *can* honour is popped first, so whatever is left is genuinely unknown."""
    import pybosl2.sdf  # noqa: F401  -- registers the sdf backend
    from pybosl2._backend import get_backend, use_backend

    triangle = [[[0, 0], [10, 0], [10, 10]]]
    with use_backend("sdf"), pytest.raises(ValueError, match=r"no \['nonsense'\] option"):
        get_backend().linear_extrude(triangle, 5, {"nonsense": 3})


@pytest.mark.parametrize(
    ("points", "faces"),
    [
        ([[0, 0, 0], [1, 0, 0]], [[0, 1, 2]]),  # too few vertices to bound anything
        ([[0, 0], [1, 0], [1, 1], [0, 1]], [[0, 1, 2, 3]]),  # 2-D points
    ],
)
def test_the_convexity_check_declines_to_judge_a_malformed_mesh(points: list, faces: list) -> None:  # type: ignore[type-arg]
    """It is a convexity test, not a validator: "malformed" and "non-convex" are different faults.

    Answering "convex" here lets the CSG backend make its own, better complaint about the mesh.
    """
    from pybosl2.sdf import _describes_a_convex_solid

    assert _describes_a_convex_solid(points, faces)

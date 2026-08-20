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

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

import pybosl2.miscellaneous as misc
import pybosl2.shapes2d as s2
import pybosl2.shapes3d as s3
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

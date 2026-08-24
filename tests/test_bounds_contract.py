# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""One box type for every ``bounds()`` in the library (SPEC S-2b, C-21).

``bounds()`` used to answer four different things depending on what you asked: a bare
``(centre, size)`` pair from shapes, a dataclass from paths and meshes, a NumPy ``[[min], [max]]``
from regions. ``lo, hi = solid.bounds()`` -- the obvious reading of the name -- silently bound a
*centre* to ``lo``, and the shape protocols typed it ``tuple[list[float], list[float]]`` so the
checker could not help. These tests pin the single answer.
"""

from __future__ import annotations

import math

import pytest

import pybosl2.sdf  # noqa: F401  -- registers the "sdf" backend
from pybosl2 import Path2D, Path3D, Region, cuboid, square, use_backend
from pybosl2.bounds import Bounds2D, Bounds3D


def _sweep_mesh(profile: Path2D) -> object:
    """The mesh a sweep produces -- reached through `.vnf()` once T18 lands, the sweep itself today."""
    swept = profile.linear_sweep(height=10)
    return swept.vnf()


def _every_measurable() -> list[tuple[str, object, type]]:
    """One instance of every type in the library that answers ``bounds()``."""
    profile = Path2D([[-5, -5], [5, -5], [5, 5], [-5, 5]], closed=True)
    with use_backend("sdf"):
        sdf_solid = cuboid([40, 30, 20])
        sdf_flat = square([20, 10])
    return [
        ("csg solid", cuboid([40, 30, 20]), Bounds3D),
        ("csg flat", square([20, 10]), Bounds2D),
        ("sdf solid", sdf_solid, Bounds3D),
        ("sdf flat", sdf_flat, Bounds2D),
        ("Path2D", profile, Bounds2D),
        ("Path3D", Path3D([[0, 0, 0], [10, 0, 0], [10, 5, 3]]), Bounds3D),
        ("Region", Region([profile]), Bounds2D),
        ("VNF", _sweep_mesh(profile), Bounds3D),
    ]


@pytest.mark.parametrize(
    ("label", "thing", "expected"), _every_measurable(), ids=lambda v: v if isinstance(v, str) else ""
)
def test_every_bounds_is_a_bounds_object(label: str, thing: object, expected: type) -> None:
    """Every ``bounds()`` in the library answers the same two types (SPEC S-2b)."""
    box = thing.bounds()  # type: ignore[attr-defined]
    assert isinstance(box, expected), f"{label}.bounds() returned {type(box).__name__}, not {expected.__name__}"
    # ...and it is a real box, not an empty dataclass: every extent positive and the corners
    # bracketing the centre.
    assert all(extent > 0 for extent in box.size), f"{label} measured an empty box: {box.size}"
    assert all(lo < c < hi for lo, c, hi in zip(box.min, box.center, box.max, strict=True)), label


def test_unpacking_a_box_fails_loudly() -> None:
    """``lo, hi = shape.bounds()`` used to bind a centre to `lo`; now it raises (SPEC S-2b)."""
    with pytest.raises(TypeError, match="cannot unpack"):
        _lo, _hi = cuboid([40, 30, 20]).bounds()  # type: ignore[misc]


def test_a_centred_cuboid_reports_corners_not_a_centre() -> None:
    """The bug the old convention hid: a centred 40x30x20 box spans -20..20, not 0..40."""
    box = cuboid([40, 30, 20]).bounds()
    assert (box.min_x, box.min_y, box.min_z) == pytest.approx((-20.0, -15.0, -10.0))
    assert (box.max_x, box.max_y, box.max_z) == pytest.approx((20.0, 15.0, 10.0))
    assert box.size == pytest.approx((40.0, 30.0, 20.0))
    assert tuple(box.center) == pytest.approx((0.0, 0.0, 0.0))


def test_the_box_carries_every_spelling_of_itself() -> None:
    """No caller does the arithmetic and no implementation picks a winner (SPEC S-2b)."""
    box = cuboid([40, 30, 20], anchor=None).up(10).bounds()
    assert tuple(box.min) == pytest.approx((box.min_x, box.min_y, box.min_z))
    assert tuple(box.max) == pytest.approx((box.max_x, box.max_y, box.max_z))
    assert box.size == pytest.approx(tuple(hi - lo for lo, hi in zip(box.min, box.max, strict=True)))
    assert tuple(box.center) == pytest.approx(tuple((lo + hi) / 2 for lo, hi in zip(box.min, box.max, strict=True)))
    assert (box.width, box.length, box.height) == pytest.approx(box.size)


def test_bounds_tracks_the_geometry_through_a_boolean() -> None:
    """A cut narrows the box; `size` (the nominal anchor frame, S-2a) is a different question."""
    solid = cuboid([40, 30, 20]) - cuboid([100, 100, 20]).up(10)
    box = solid.bounds()
    assert box.min_z == pytest.approx(-10.0)
    assert box.max_z == pytest.approx(0.0)
    assert box.height == pytest.approx(10.0)


def test_both_constructors_agree() -> None:
    """`from_center_size` and `from_min_max` are two doors into one box."""
    assert Bounds3D.from_center_size([0, 0, 0], [40, 30, 20]) == Bounds3D.from_min_max([-20, -15, -10], [20, 15, 10])
    assert Bounds2D.from_center_size([1, 2], [10, 6]) == Bounds2D.from_min_max([-4, -1], [6, 5])


def test_a_shape_has_one_public_name_for_its_nominal_box() -> None:
    """`nominal_size` was a second spelling of `size` and is gone (SPEC C-21)."""
    solid = cuboid([40, 30, 20])
    assert solid.size == pytest.approx([40.0, 30.0, 20.0])
    assert not hasattr(solid, "nominal_size")
    with use_backend("sdf"):
        assert not hasattr(cuboid([10, 10, 10]), "nominal_size")


def test_no_bounds_is_ever_non_finite() -> None:
    """A degenerate build is a silent wrong answer; E-5 says it raises instead."""
    for thing, _cls in ((cuboid([40, 30, 20]), Bounds3D), (square([20, 10]), Bounds2D)):
        assert all(math.isfinite(v) for v in thing.bounds().size)

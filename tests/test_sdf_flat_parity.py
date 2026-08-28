# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The SDF 2-D shape honours the shared contract (SPEC C-19, C-15, PAR-1).

`SdfSolid` inherits `Colorable`, `Anchorable` and `Distributable`; `SdfShape2D` inherited from
nothing, so 43 contract members were missing from it -- the whole of colour, distribution and
anchoring, plus the in-plane moves. `isinstance(sdf_flat, Flat)` was false for a perfectly good
2-D shape.

None of that was a limit of distance fields. C-19 puts colour and distribution on *any* shape, and
anchoring only ever needed a bounding box, which an SDF carries exactly. The gap was the shared
behaviour never having been mixed in.

What genuinely cannot cross over is declared and refuses (PAR-3): attachment and tagging need the
edge structure a field does not retain, and a Minkowski sum has no closed-form distance field.

These tests check the members *work*, not merely that they exist -- a refusing stub would satisfy
`hasattr` and teach nothing.
"""

from __future__ import annotations

import pytest

import pybosl2.sdf  # noqa: F401  -- registers the "sdf" backend
from pybosl2 import Anchor, Path2D, square, use_backend
from pybosl2._backend import Shape
from pybosl2.exceptions import UnsupportedByBackendError
from pybosl2.flat import Flat
from pybosl2.sdf.shapes2d import SdfShape2D


def _flat() -> SdfShape2D:
    with use_backend("sdf"):
        return square([20, 10])


def test_the_sdf_flat_shape_satisfies_the_contract() -> None:
    """`isinstance` was false for a real 2-D SDF shape until the mixins went in.

    Checked by *using* the contract as well as by asking about it: a class can satisfy a protocol
    structurally and still be useless through it, which is the failure C-20 is about.
    """
    shape = _flat()
    assert isinstance(shape, Flat)
    assert isinstance(shape, Shape)

    # ...and a caller who holds only the contract can do the contract's work
    typed: Flat = shape
    assert typed.bounds().size == pytest.approx((20.0, 10.0))
    assert typed.translate([5, 0]).bounds().center.x == pytest.approx(5.0)
    assert typed.color("red").backend == "sdf"
    assert typed.linear_extrude(height=4).bounds().size == pytest.approx((20.0, 10.0, 4.0))


# --- colour rides the field, and survives the trip to 3-D (SPEC C-19, S-37, S-40) -------------


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("color", ("red",)),
        ("recolor", ("blue",)),
        ("color_this", ("green",)),
        ("highlight", ()),
        ("ghost", ()),
        ("hsl", (120.0,)),
        ("hsv", (200.0,)),
    ],
)
def test_a_colour_operation_keeps_the_shape_a_field(method: str, args: tuple[object, ...]) -> None:
    """Colour is metadata on the field, not a reason to mesh it early (SPEC B-5)."""
    out = getattr(_flat(), method)(*args)
    assert isinstance(out, SdfShape2D), f"{method}() left SDF-land"
    assert out.backend == "sdf"
    assert out.bounds().size == pytest.approx((20.0, 10.0)), f"{method}() changed the geometry"


def test_colour_survives_the_extrusion_into_three_dimensions() -> None:
    """SPEC S-40: colour survives the conversions between representations."""
    with use_backend("sdf"):
        solid = square([20, 10]).color("red").linear_extrude(height=5)
    assert solid._colour == ("red", None)
    assert solid.backend == "sdf"


def test_colour_does_not_leak_between_copies() -> None:
    """`_wrap` carries the metadata, so a transform keeps it and a fresh shape does not have it."""
    coloured = _flat().color("red")
    assert coloured.right(5)._colour == ("red", None)
    assert _flat()._colour is None


# --- distribution: an operation on any shape (SPEC C-19, S-31) --------------------------------


def test_copies_are_placed_where_they_are_asked_for() -> None:
    copies = _flat().xcopies(spacing=30, num_copies=3)
    assert len(copies) == 3
    assert [c.bounds().center.x for c in copies] == pytest.approx([-30.0, 0.0, 30.0])
    assert all(isinstance(c, SdfShape2D) for c in copies)


def test_a_grid_of_copies_covers_the_grid() -> None:
    copies = _flat().grid_copies(spacing=40, num_copies=[2, 2])
    assert len(copies) == 4
    centres = sorted((round(c.bounds().center.x, 3), round(c.bounds().center.y, 3)) for c in copies)
    assert centres == [(-20.0, -20.0), (-20.0, 20.0), (20.0, -20.0), (20.0, 20.0)]


def test_distribute_on_path_unions_the_copies_into_one_shape() -> None:
    with use_backend("sdf"):
        route = Path2D([[0, 0], [40, 0], [40, 30]])
        trail = square([6, 4]).distribute_on_path(route, num_copies=8)
    assert isinstance(trail, SdfShape2D)
    # one shape spanning the route, not a single copy sitting at the origin
    assert trail.bounds().width > 40
    assert trail.bounds().length > 25


# --- transforms and anchoring (SPEC C-22, C-10, S-2a) -----------------------------------------


@pytest.mark.parametrize(
    ("method", "arg", "expected"),
    [("left", 5, (-5.0, 0.0)), ("right", 5, (5.0, 0.0)), ("forward", 3, (0.0, -3.0)), ("back", 3, (0.0, 3.0))],
)
def test_each_directional_move_goes_the_right_way(method: str, arg: float, expected: tuple[float, float]) -> None:
    moved = getattr(_flat(), method)(arg)
    assert tuple(moved.bounds().center) == pytest.approx(expected)


def test_multmatrix_takes_the_matrix_the_rest_of_the_library_speaks() -> None:
    """The distributors build 4x4 matrices for both dimensions, so a 2-D shape must accept one."""
    moved = _flat().multmatrix([[1, 0, 0, 5], [0, 1, 0, -2], [0, 0, 1, 0], [0, 0, 0, 1]])
    assert tuple(moved.bounds().center) == pytest.approx((5.0, -2.0))


def test_a_matrix_that_leaves_the_plane_is_refused_not_flattened() -> None:
    """Silently dropping the Z term would move the shape somewhere the caller did not ask for."""
    with pytest.raises(Exception, match="out of the Z=0 plane"):
        _flat().multmatrix([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 7], [0, 0, 0, 1]])


def test_anchoring_puts_the_named_point_on_the_origin() -> None:
    """It only ever needed a bounding box, and an SDF shape knows its own exactly."""
    shape = _flat()
    assert shape.anchor_point(Anchor.LEFT) == pytest.approx([-10.0, 0.0])
    assert shape.anchor_point(Anchor.TOP) == pytest.approx([0.0, 5.0])
    assert tuple(shape.reanchor(Anchor.LEFT).bounds().center) == pytest.approx((10.0, 0.0))


def test_the_nominal_box_is_carried_and_is_not_the_measurement() -> None:
    """SPEC S-2a: `size` is the frame the shape is designed around; `bounds()` is the geometry."""
    shape = _flat().with_nominal_size([30.0, 30.0])
    assert shape.size == pytest.approx([30.0, 30.0])
    assert shape.bounds().size == pytest.approx((20.0, 10.0))


# --- what genuinely cannot cross over refuses by name (SPEC PAR-3, B-4) ------------------------


@pytest.mark.parametrize("feature", ["attach", "position", "align", "tag", "tag_this", "diff", "intersect", "realize"])
def test_the_attachment_family_refuses_by_name(feature: str) -> None:
    """Declared so the contract can carry it, refusing because a field has no edge structure."""
    shape = _flat()
    assert hasattr(shape, feature), "declared, so `isinstance` and the contract hold"
    with pytest.raises(UnsupportedByBackendError, match="edge structure"):
        getattr(shape, feature)()


def test_minkowski_refuses_and_names_the_thing_that_does_work() -> None:
    """A refusal earns its place by naming the alternative (SPEC E-2)."""
    with pytest.raises(UnsupportedByBackendError, match=r"\.offset\(r\)"):
        _flat().minkowski(_flat())


# --- the extrusions the contract names (SPEC C-17, PAR-4) -------------------------------------


def test_both_extrusion_spellings_exist_and_agree() -> None:
    """`linear_extrude` and `rotate_extrude` are the contract's names; the backend's are aliases."""
    with use_backend("sdf"):
        flat = square([6, 20]).right(14)
        by_contract = flat.rotate_extrude()
        by_backend = flat.revolve_sdf()
    assert by_contract.bounds().size == pytest.approx(by_backend.bounds().size)

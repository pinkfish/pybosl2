# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.screw_drive: the Phillips/hex/Torx/Robertson driver-recess masks and their
dimensional helpers. The numeric helpers are checked against the values transcribed from BOSL2's
screw_drive.scad; the mask builders are smoke-tested (they return a Bosl2Solid and compose via CSG)."""

import dataclasses
import math

import pytest

from pybosl2.parts.screw_drive import (
    HexDriveMask,
    PhillipsMask,
    PhillipsSpec,
    RobertsonMask,
    RobertsonSpec,
    TorxMask,
    TorxMask2d,
    TorxSpec,
)
from pybosl2.shapes3d import Bosl2Solid, cyl

# ---- Torx dimensional info (verbatim from screw_drive.scad) ----


def test_torx_info_values() -> None:
    t = TorxSpec(6)
    assert (t.outer_diameter, t.inner_diameter, t.depth, t.tip_rounding, t.inner_rounding) == (
        1.75,
        1.27,
        0.775,
        0.132,
        0.383,
    )
    assert TorxSpec(30).as_tuple() == (5.60, 4.05, 2.22, 0.451, 1.194)
    assert TorxSpec(100).as_tuple() == (22.40, 16.00, 10.79, 1.720, 4.925)


def test_torx_info_is_a_frozen_value() -> None:
    """TorxSpec is a frozen dataclass: two of a size are equal, and nobody can retune one."""
    assert TorxSpec(30) == TorxSpec(30)
    assert TorxSpec(30) != TorxSpec(25)
    assert dataclasses.astuple(TorxSpec(30)) == TorxSpec(30).as_tuple()
    with pytest.raises(dataclasses.FrozenInstanceError):
        TorxSpec(30).depth = 99.0  # type: ignore[misc]


def test_torx_diam_and_depth() -> None:
    assert TorxSpec(30).diam == 5.60
    assert TorxSpec(30).depth == 2.22
    assert TorxSpec(8).diam == TorxSpec(8).outer_diameter
    assert TorxSpec(8).depth == TorxSpec(8).depth


def test_torx_info_invalid() -> None:
    with pytest.raises(ValueError, match="Unsupported Torx size"):
        TorxSpec(11)
    with pytest.raises(ValueError, match="Unsupported Torx size"):
        TorxSpec("nope")  # type: ignore[arg-type]


# ---- Phillips ----


def test_phillips_size_parsing() -> None:
    # "#2" and 2 resolve identically.
    assert PhillipsSpec("#2").depth(4.0) == PhillipsSpec(2).depth(4.0)
    with pytest.raises(ValueError, match="phillips size must be"):
        _ = PhillipsMask("#9").shape
    with pytest.raises(ValueError, match="phillips size must be"):
        _ = PhillipsMask(5).shape


def test_phillips_depth_diam_roundtrip() -> None:
    # PhillipsSpec(size).diam(PhillipsSpec(size).depth(d)) == d for a valid diameter (tip g < d < shaft).
    shafts = {"#0": 3, "#1": 4.5, "#2": 6, "#3": 8, "#4": 10}
    tips = {"#0": 0.81, "#1": 1.27, "#2": 2.29, "#3": 3.81, "#4": 5.08}
    for size in ("#0", "#1", "#2", "#3", "#4"):
        diameter = (tips[size] + shafts[size]) / 2  # midpoint is always in the valid range
        depth = PhillipsSpec(size).depth(diameter)
        assert depth is not None
        assert PhillipsSpec(size).diam(depth) == pytest.approx(diameter)


def test_phillips_depth_out_of_range() -> None:
    # d beyond the shaft (#0 shaft is 3mm) or below the tip diameter g returns None.
    assert PhillipsSpec("#0").depth(5.0) is None
    assert PhillipsSpec("#0").depth(0.0) is None


def test_phillips_diam_out_of_range() -> None:
    # depth outside [h1, h1+h2) returns None.
    assert PhillipsSpec("#2").diam(0.0) is None
    assert PhillipsSpec("#2").diam(1000.0) is None


# ---- mask builders (smoke) ----


def _hex_across_flats(size: float, slop: float = 0.0) -> float:
    """The ISO-oversized recess width screw_drive.scad builds for a *size* hex key."""
    return 1.0072 * size + 0.0341 + 2 * slop


@pytest.mark.parametrize(
    ("obj", "expected_size", "expected_centre"),
    [
        # A Phillips recess spans its driver's shaft diameter and rises from z=0 ...
        (PhillipsMask("#2").shape, (6.0, 6.0, None), (0.0, 0.0, None)),
        # ... unless center=True, which straddles z=0 instead. #4's shaft is 10mm.
        (PhillipsMask(4, center=True).shape, (10.0, 10.0, None), (0.0, 0.0, 0.0)),
        # A hex recess measures the key's across-flats size (Y), oversized per ISO, and
        # 2/sqrt(3) of that across the corners (X); `l` is the depth.
        (
            HexDriveMask(5, 10).shape,
            (_hex_across_flats(5) * 2 / math.sqrt(3), _hex_across_flats(5), 10.0),
            (0.0, 0.0, 5.0),
        ),
        (
            HexDriveMask(6, 8, slop=0.05).shape,
            (
                _hex_across_flats(6, 0.05) * 2 / math.sqrt(3),
                _hex_across_flats(6, 0.05),
                8.0,
            ),
            (0.0, 0.0, 4.0),
        ),
        # A Torx recess spans the size's outer diameter, and `l` is again the depth.
        (TorxMask(30, 10).shape, (TorxSpec(30).outer_diameter, None, 10.0), (0.0, 0.0, 5.0)),
        (TorxMask(8, 5, center=True).shape, (TorxSpec(8).outer_diameter, None, 5.0), (0.0, 0.0, 0.0)),
        # A Robertson recess is a square tapered socket: as wide as it is deep.
        (RobertsonMask(2).shape, (3.0823, 3.0823, 4.2893), (0.0, 0.0, None)),
        (RobertsonMask(0, l=3.27, angle=3.0).shape, (None, None, 3.27), (0.0, 0.0, None)),
    ],
)
def test_masks_measure_their_driver_size(
    obj: Bosl2Solid,
    expected_size: tuple[float | None, float | None, float | None],
    expected_centre: tuple[float | None, float | None, float | None],
) -> None:
    _box = obj.bounds()
    centre, size = list(_box.center), list(_box.size)
    for axis in range(3):
        assert size[axis] > 0.0
        if expected_size[axis] is not None:
            assert size[axis] == pytest.approx(expected_size[axis], abs=0.01)
        if expected_centre[axis] is not None:
            assert centre[axis] == pytest.approx(expected_centre[axis], abs=0.01)


def test_hex_slop_widens_the_recess() -> None:
    """slop= is clearance: it makes the socket bigger, never smaller."""
    tight = HexDriveMask(6, 8).shape.bounds().size
    loose = HexDriveMask(6, 8, slop=0.05).shape.bounds().size
    assert loose[0] > tight[0]
    assert loose[1] > tight[1]
    assert loose[2] == pytest.approx(tight[2])  # depth is untouched


def test_torx_2d_outline_spans_the_outer_diameter() -> None:
    """The 2-D profile is the 3-D mask's cross-section, so extruding it measures the same width."""
    for size in (30, 8):
        _box = TorxMask2d(size).shape.linear_extrude(height=1).bounds()
        _, extents = list(_box.center), list(_box.size)
        assert extents[0] == pytest.approx(TorxSpec(size).outer_diameter, abs=0.01)
        assert extents[2] == pytest.approx(1.0)


def test_mask_composes_with_head() -> None:
    """A recess subtracts cleanly from a head: it cuts into it without changing its envelope."""
    head = cyl(diameter1=2, diameter2=8, height=4).down(2)
    _box = head.bounds()
    plain_centre, plain_size = list(_box.center), list(_box.size)
    for recess in (PhillipsMask("#2").shape, TorxMask(30, 4).shape):
        cut = head - recess
        _box = cut.bounds()
        centre, size = list(_box.center), list(_box.size)
        assert centre == pytest.approx(plain_centre)
        assert size == pytest.approx(plain_size)  # the recess is wholly inside the head
        assert repr(cut) != repr(head)  # ... but it really was cut


def test_robertson_size_validation() -> None:
    with pytest.raises(ValueError, match="robertson size must be"):
        RobertsonMask(5)
    with pytest.raises(ValueError, match="robertson size must be"):
        RobertsonMask("5")


# ── property and show() coverage ────────────────────────────────────────────


def test_phillips_mask_properties() -> None:
    m = PhillipsMask("#1")
    assert m.size == "#1"
    assert m.center is False
    m2 = PhillipsMask("#2", center=True)
    assert m2.center is True


def test_hex_drive_mask_properties() -> None:
    m = HexDriveMask(size=2.5, l=5)
    assert m.size == 2.5
    assert m.l == 5
    assert m.slop == 0.0
    assert m.center is False
    m2 = HexDriveMask(size=2, l=8, slop=0.1, center=True)
    assert m2.center is True
    assert m2.slop == 0.1


def test_torx_mask_properties() -> None:
    m = TorxMask(30, l=10)
    assert m.size == 30
    assert m.l == 10


def test_robertson_mask_properties() -> None:
    m = RobertsonMask(2)
    assert m.size == 2
    assert m.slop == 0.0
    m2 = RobertsonMask(2, slop=0.1, angle=3)
    assert m2.slop == 0.1


def test_show_methods_do_not_raise() -> None:
    PhillipsMask().show()
    HexDriveMask(size=2, l=5).show()
    TorxMask(30, l=10).show()
    TorxMask2d(30).show()
    RobertsonMask(2).show()


def test_phillips_spec_properties() -> None:
    spec = PhillipsSpec("#2")
    assert spec.shaft == 6
    assert spec.g == 2.29
    d = spec.depth(4.0)
    assert d is not None
    assert d > 0


def test_robertson_spec_imports() -> None:
    assert RobertsonSpec(2).m > 0

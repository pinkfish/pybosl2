# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.screw_drive: the Phillips/hex/Torx/Robertson driver-recess masks and their
dimensional helpers. The numeric helpers are checked against the values transcribed from BOSL2's
screw_drive.scad; the mask builders are smoke-tested (they return a Bosl2Solid and compose via CSG)."""

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


def test_torx_info_is_dataclass() -> None:
    assert isinstance(TorxSpec(30), TorxSpec)


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


@pytest.mark.parametrize(
    "obj",
    [
        PhillipsMask("#2").shape,
        PhillipsMask(4, center=True).shape,
        HexDriveMask(5, 10).shape,
        HexDriveMask(6, 8, slop=0.05).shape,
        TorxMask2d(30).shape,
        TorxMask(30, 10).shape,
        TorxMask(8, 5, center=True).shape,
        RobertsonMask(2).shape,
        RobertsonMask(0, l=3.27, angle=3.0).shape,
    ],
)
def test_masks_return_solid(obj: Bosl2Solid) -> None:
    assert isinstance(obj, Bosl2Solid)


def test_mask_composes_with_head() -> None:
    # A recess subtracts cleanly from a head.
    head = cyl(diameter1=2, diameter2=8, height=4).down(2)
    assert isinstance(head - PhillipsMask("#2").shape, Bosl2Solid)
    assert isinstance(head - TorxMask(30, 4).shape, Bosl2Solid)


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

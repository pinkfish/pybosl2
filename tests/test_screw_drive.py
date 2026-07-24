# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2.screw_drive: the Phillips/hex/Torx/Robertson driver-recess masks and their
dimensional helpers. The numeric helpers are checked against the values transcribed from BOSL2's
screw_drive.scad; the mask builders are smoke-tested (they return a Bosl2Solid and compose via CSG)."""


import pytest

from bosl2.screw_drive import ScrewDrive as SD
from bosl2.shapes3d import Bosl2Solid, cyl

# ---- Torx dimensional info (verbatim from screw_drive.scad) ----


def test_torx_info_values():
    t = SD.torx_info(6)
    assert (t.od, t.id, t.depth, t.tip_rounding, t.inner_rounding) == (
        1.75,
        1.27,
        0.775,
        0.132,
        0.383,
    )
    assert SD.torx_info(30).as_tuple() == (5.60, 4.05, 2.22, 0.451, 1.194)
    assert SD.torx_info(100).as_tuple() == (22.40, 16.00, 10.79, 1.720, 4.925)


def test_torx_info_is_dataclass():
    from bosl2.screw_drive import TorxSpec

    assert isinstance(SD.torx_info(30), TorxSpec)


def test_torx_diam_and_depth():
    assert SD.torx_diam(30) == 5.60
    assert SD.torx_depth(30) == 2.22
    assert SD.torx_diam(8) == SD.torx_info(8).od
    assert SD.torx_depth(8) == SD.torx_info(8).depth


def test_torx_info_invalid():
    with pytest.raises(ValueError):
        SD.torx_info(11)  # 11 is not a real Torx size
    with pytest.raises(ValueError):
        SD.torx_info("nope")


# ---- Phillips ----


def test_phillips_size_parsing():
    # "#2" and 2 resolve identically.
    assert SD.phillips_depth("#2", 4.0) == SD.phillips_depth(2, 4.0)
    with pytest.raises(ValueError):
        SD.phillips_mask("#9")
    with pytest.raises(ValueError):
        SD.phillips_mask(5)


def test_phillips_depth_diam_roundtrip():
    # phillips_diam(size, phillips_depth(size, d)) == d for a valid diameter (tip g < d < shaft).
    shafts = {"#0": 3, "#1": 4.5, "#2": 6, "#3": 8, "#4": 10}
    tips = {"#0": 0.81, "#1": 1.27, "#2": 2.29, "#3": 3.81, "#4": 5.08}
    for size in ("#0", "#1", "#2", "#3", "#4"):
        diameter = (
            tips[size] + shafts[size]
        ) / 2  # midpoint is always in the valid range
        depth = SD.phillips_depth(size, diameter)
        assert depth is not None
        assert SD.phillips_diam(size, depth) == pytest.approx(diameter)


def test_phillips_depth_out_of_range():
    # d beyond the shaft (#0 shaft is 3mm) or below the tip diameter g returns None.
    assert SD.phillips_depth("#0", 5.0) is None
    assert SD.phillips_depth("#0", 0.0) is None


def test_phillips_diam_out_of_range():
    # depth outside [h1, h1+h2) returns None.
    assert SD.phillips_diam("#2", 0.0) is None
    assert SD.phillips_diam("#2", 1000.0) is None


# ---- mask builders (smoke) ----


@pytest.mark.parametrize(
    "obj",
    [
        SD.phillips_mask("#2"),
        SD.phillips_mask(4, center=True),
        SD.hex_drive_mask(5, 10),
        SD.hex_drive_mask(6, 8, slop=0.05),
        SD.torx_mask2d(30),
        SD.torx_mask(30, 10),
        SD.torx_mask(8, 5, center=True),
        SD.robertson_mask(2),
        SD.robertson_mask(0, extra=2, angle=3.0),
    ],
)
def test_masks_return_solid(obj):
    assert isinstance(obj, Bosl2Solid)


def test_mask_composes_with_head():
    # A recess subtracts cleanly from a head.
    head = cyl(diameter1=2, diameter2=8, height=4).down(2)
    assert isinstance(head - SD.phillips_mask("#2"), Bosl2Solid)
    assert isinstance(head - SD.torx_mask(30, 4), Bosl2Solid)


def test_robertson_size_validation():
    with pytest.raises(ValueError):
        SD.robertson_mask(5)
    with pytest.raises(ValueError):
        SD.robertson_mask("2")

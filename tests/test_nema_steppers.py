# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.nema_steppers: NEMA stepper-motor models, mount masks, and the size table."""

import pytest

from pybosl2.parts.nema_steppers import NemaMotor, NemaMountMask, NemaSpec
from pybosl2.shapes3d import Bosl2Solid, cuboid


def _size(s: Bosl2Solid) -> list[float]:
    _min, size = s._native_bounds()  # type: ignore[misc]
    return size


def test_info_returns_dataclass() -> None:
    s = NemaSpec(17)
    assert isinstance(s, NemaSpec)
    assert s.motor_width == 42.3
    assert s.screw_spacing == 31.0
    assert s.shaft_diam == 5.0


def test_unknown_size_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported NEMA size"):
        NemaSpec(99)


@pytest.mark.parametrize(("size", "width"), [(8, 20.3), (17, 42.3), (23, 57.0), (42, 110.0)])
def test_motor_body_width(size: int, width: float) -> None:
    m = NemaMotor(size).shape
    w, length, _h = _size(m)
    assert w == pytest.approx(width, abs=0.1)
    assert length == pytest.approx(width, abs=0.1)


def test_motor_height_is_body_plus_shaft() -> None:
    m = NemaMotor(17, height=24, shaft_len=20).shape
    assert _size(m)[2] == pytest.approx(44, abs=0.2)


@pytest.mark.parametrize(
    ("kw", "expected"),
    [
        # X spans the screw circle plus one screw width; the slots elongate along Y by `length`.
        ({}, (34.0, 39.0, 5.0)),
        ({"atype": "screws"}, (34.0, 39.0, 5.0)),  # same slots, no central bore
        ({"length": 8}, (34.0, 42.0, 5.0)),  # longer slots
        ({"slop": 0.2}, (34.2, 39.0, 5.0)),  # slop widens every hole
        ({"depth": 6}, (34.0, 39.0, 6.0)),  # depth is how far the mask cuts
    ],
)
def test_mount_mask_matches_the_screw_pattern(
    kw: dict[str, object],
    expected: tuple[float, float, float],
) -> None:
    """The mask spans NEMA 17's 31mm screw spacing plus the 3mm screws, slotted along Y."""
    spec = NemaSpec(17)
    assert spec.screw_spacing + spec.screw_size == pytest.approx(34.0)  # where the 34 comes from
    lo, size = NemaMountMask(17, **kw).shape._native_bounds()  # type: ignore[misc]
    assert size == pytest.approx(expected, abs=0.3)  # the faceted slot ends land just inside
    assert lo[2] == pytest.approx(-size[2] / 2)  # the mask straddles the plate surface


def test_mask_bad_atype_raises() -> None:
    with pytest.raises(ValueError, match="must be FULL or SCREWS"):
        NemaMountMask(17, atype="banana")


def _survives(solid: Bosl2Solid, x: float, y: float) -> bool:
    """True if any material is left where a 2mm probe sits at (x, y): an empty solid has no bounds."""
    probe = solid & cuboid([2, 2, 10]).translate([x, y, 0])
    return probe._native_bounds() is not None  # type: ignore[misc]


@pytest.mark.parametrize(("atype", "centre_survives"), [("full", False), ("screws", True)])
def test_mount_mask_cuts_a_plate(atype: str, centre_survives: bool) -> None:
    """The mask really opens holes: probes at the four screws come back empty.

    A hole is invisible to a bounding box -- the plate keeps its 60x60x5 envelope either way --
    so this probes the plate where the holes should be. `atype` is the difference between the two
    masks: FULL also bores the central shaft clearance, SCREWS leaves it solid.
    """
    plate = cuboid([60, 60, 5]) - NemaMountMask(17, depth=6, atype=atype).shape
    assert _size(plate) == pytest.approx([60.0, 60.0, 5.0])  # the cut is entirely internal

    half = NemaSpec(17).screw_spacing / 2
    for x in (-half, half):
        for y in (-half, half):
            assert not _survives(plate, x, y), f"no screw hole at ({x}, {y})"
    assert _survives(plate, 27, 27)  # ... but the plate corners are untouched
    assert _survives(plate, 0, 0) is centre_survives

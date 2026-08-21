# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.joiners: dovetail joints and snap-pin connectors."""

import pytest

from pybosl2.parts.enums import Gender
from pybosl2.parts.joiners import Dovetail, SnapPin, SnapPinSocket
from pybosl2.shapes3d import Bosl2Solid, cuboid


def _size(s: Bosl2Solid) -> list[float]:
    _min, size = s._native_bounds()  # type: ignore[misc]
    return size


def test_dovetail_flares_to_top_width() -> None:
    # top width = base width + 2*height/slope; the dovetail is wider than its base
    dt = Dovetail(Gender.MALE, width=15, height=8, slide=30, slope=6).shape
    w, sl, height = _size(dt)
    assert w == pytest.approx(15 + 2 * 8 / 6, abs=0.1)
    assert sl == pytest.approx(30, abs=0.1)
    assert height == pytest.approx(8, abs=0.05)


def test_steeper_angle_flares_more() -> None:
    # slope = 1/tan(angle): a bigger dovetail angle -> smaller slope -> more flare
    shallow = _size(Dovetail(Gender.MALE, width=15, height=8, slide=30, angle=15).shape)[0]
    steep = _size(Dovetail(Gender.MALE, width=15, height=8, slide=30, angle=45).shape)[0]
    assert steep > shallow


def test_female_is_enlarged_by_slop() -> None:
    male = _size(Dovetail(Gender.MALE, width=15, height=8, slide=30).shape)
    female = _size(Dovetail(Gender.FEMALE, width=15, height=8, slide=30, slop=0.2).shape)
    assert female[2] > male[2]  # female taller by the slop


def _width_at(dt: Bosl2Solid, y: float) -> float:
    """Width of the dovetail in a thin slice at *y* along the slide.

    A taper only narrows one end, so the bounding box -- which is the wide end either way --
    cannot see it. Slicing can.
    """
    slab = cuboid([100, 0.2, 100]).translate([0, y, 0])
    return _size(dt & slab)[0]


@pytest.mark.parametrize(
    ("kw", "back_width", "mid_width"),
    [
        ({}, 20.0, 20.0),  # untapered: the same 18 + 2*6/6 all the way along
        ({"taper": 4}, 14.44, 17.22),  # tapered by angle
        ({"back_width": 12}, 14.03, 17.02),  # tapered to a stated back width (12 + 2*6/6)
    ],
)
def test_dovetail_taper_narrows_the_back(kw: dict[str, object], back_width: float, mid_width: float) -> None:
    dt = Dovetail(Gender.MALE, width=18, height=6, slide=40, **kw).shape  # type: ignore[arg-type]
    assert _size(dt) == pytest.approx([20.0, 40.0, 6.0], abs=0.05)  # the wide end sets the envelope
    assert _width_at(dt, 19.9) == pytest.approx(20.0, abs=0.05)  # front stays full width
    assert _width_at(dt, -19.9) == pytest.approx(back_width, abs=0.05)
    assert _width_at(dt, 0.0) == pytest.approx(mid_width, abs=0.05)  # and narrows evenly between


@pytest.mark.parametrize("length", [12, 20])
def test_snap_pin_and_socket_run_the_stated_length(length: float) -> None:
    """Both are built about z=0 and grow only along the pin axis as `length` grows."""
    pin_lo, pin_size = SnapPin(length=length).shape._native_bounds()  # type: ignore[misc]
    sock_lo, sock_size = SnapPinSocket(length=length).shape._native_bounds()  # type: ignore[misc]

    assert pin_lo[2] == pytest.approx(-length / 2)
    assert pin_size[2] == pytest.approx(length + 2.31, abs=0.01)  # plus the rounded tip
    assert sock_lo[2] == pytest.approx(-length / 2 - 0.5)
    assert sock_size[2] == pytest.approx(length + 1.0)
    # Length runs along the pin only; the cross-section is unchanged.
    assert pin_size[:2] == pytest.approx(SnapPin().shape._native_bounds()[1][:2])  # type: ignore[misc]


@pytest.mark.parametrize("diameter", [5, 8, 10])
def test_socket_bore_clears_the_pin(diameter: float) -> None:
    """The socket relief is wider than the pin's barb in both axes, so the pin fits."""
    pin = _size(SnapPin(diameter=diameter, nub_depth=0.6).shape)
    socket = _size(SnapPinSocket(diameter=diameter, nub_depth=0.6).shape)
    assert socket[0] > pin[0]
    assert socket[1] > pin[1]


def test_clearance_opens_the_socket_and_leaves_the_pin_alone() -> None:
    """clearance= is the fit allowance: it belongs to the socket, not to the pin."""
    tight_pin = _size(SnapPin(diameter=5, clearance=0.0).shape)
    loose_pin = _size(SnapPin(diameter=5, clearance=0.5).shape)
    assert loose_pin == pytest.approx(tight_pin)

    tight_socket = _size(SnapPinSocket(diameter=5, clearance=0.0).shape)
    loose_socket = _size(SnapPinSocket(diameter=5, clearance=0.5).shape)
    assert loose_socket[0] > tight_socket[0]
    assert loose_socket[1] > tight_socket[1]
    # With no clearance at all the bore is exactly the pin's own section: no room to insert it.
    assert tight_socket[1] == pytest.approx(tight_pin[1])

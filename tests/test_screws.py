# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/screws.py: the metric dimension tables (transcribed verbatim from screws.scad)
and the Screws screw/nut/screw_hole builders. Native geometry is mocked, so these check the resolved
dimensions numerically and that every builder returns a Bosl2Solid; the real assembled geometry
(watertight screws with the right head/shaft, matching nuts, hole cutters) is verified in
test_stl_render.py."""

import math

import pytest

from pybosl2.parts.enums import NutShape, ScrewDriveType, ScrewHeadType, ThreadPitchClass
from pybosl2.parts.screws import Nut, Screw, ScrewHole, ScrewSpec, _lookup_pitch, _nut_dims
from pybosl2.shapes3d import Bosl2Solid

# -- spec parsing / pitch lookup ----------------------------------------------------------


def test_parse_plain_metric_name() -> None:
    sp = ScrewSpec("M6")
    assert (sp.diameter, sp.pitch) == (6.0, 1.0)
    sp = ScrewSpec("M8")
    assert (sp.diameter, sp.pitch) == (8.0, 1.25)
    sp = ScrewSpec("M3")
    assert (sp.diameter, sp.pitch) == (3.0, 0.5)


def test_parse_explicit_pitch() -> None:
    sp = ScrewSpec("M8x1")
    assert (sp.diameter, sp.pitch) == (8.0, 1.0)
    sp = ScrewSpec("M6x0.75")
    assert (sp.diameter, sp.pitch) == (6.0, 0.75)


def test_parse_number_and_dict() -> None:
    sp = ScrewSpec(6)
    assert (sp.diameter, sp.pitch) == (6.0, 1.0)
    sp = ScrewSpec({"diameter": 10, "pitch": 1.25})
    assert (sp.diameter, sp.pitch) == (10.0, 1.25)


@pytest.mark.parametrize(
    ("thread", "expected"),
    [
        (ThreadPitchClass.COARSE, 1.5),
        (ThreadPitchClass.FINE, 1.25),
        (ThreadPitchClass.EXTRA_FINE, 1.0),
        (ThreadPitchClass.SUPER_FINE, 0.75),
    ],
)
def test_pitch_classes_m10(thread: ThreadPitchClass, expected: float) -> None:
    assert _lookup_pitch(10, thread) == expected


def test_pitch_falls_back_to_coarse_when_class_missing() -> None:
    # M6 has no super-fine pitch -> falls back to coarse (1.0)
    assert _lookup_pitch(6, ThreadPitchClass.SUPER_FINE) == 1.0


def test_unknown_size_raises() -> None:
    with pytest.raises(ValueError, match="Unknown metric screw size"):
        _lookup_pitch(6.5, ThreadPitchClass.COARSE)


# -- head dimensions (verbatim from screws.scad metric tables) ----------------------------


def test_socket_head_dims() -> None:
    info = ScrewSpec("M6", head=ScrewHeadType.SOCKET, drive=ScrewDriveType.HEX)
    assert info.head_size == 10  # ISO 4762 head diameter
    assert info.head_height == 6.0  # socket head height == nominal diameter
    assert info.drive_size == 5  # hex key across-flats
    assert info.drive_depth == 3.0  # diameter / 2


def test_hex_head_dims() -> None:
    info = ScrewSpec("M8", head=ScrewHeadType.HEX)
    assert info.head_size == 13  # across-flats
    assert info.head_height == 5.3


def test_button_head_dims() -> None:
    info = ScrewSpec("M6", head=ScrewHeadType.BUTTON, drive=ScrewDriveType.HEX)
    assert info.head_size == 10.5
    assert info.head_height == 3.3
    assert info.drive_size == 4
    assert info.drive_depth == 2.08


def test_pan_head_dims() -> None:
    info = ScrewSpec("M5", head=ScrewHeadType.PAN)
    assert info.head_size == 9.5
    assert info.head_height == 3.8


def test_flat_head_dims_and_angle() -> None:
    info = ScrewSpec("M6", head=ScrewHeadType.FLAT)
    assert info.head_size == 11.085  # actual (mean) diameter, ISO 10642/7046
    assert info.head_size_sharp == 12.6  # theoretical sharp diameter
    assert info.head_angle == 90.0
    # 90-degree countersink: cone height == radius drop == (head - shaft)/2
    assert math.isclose(info.head_height, (11.085 - 6) / 2)


def test_setscrew_drive() -> None:
    info = ScrewSpec("M6", head=ScrewHeadType.NONE, drive=ScrewDriveType.HEX)
    assert info.head == ScrewHeadType.NONE
    assert info.head_size is None
    assert info.drive_size == 3  # hex key
    assert info.drive_depth == 3.0  # diameter / 2


def test_head_table_nearest_size_fallback() -> None:
    # M7 has a thread pitch but no tabulated button head -> nearest head size (M6/M8) is used.
    info = ScrewSpec("M7", head=ScrewHeadType.BUTTON)
    assert info.head_size in (10.5, 14)  # M6 or M8 button diameter


def test_unknown_thread_size_raises() -> None:
    with pytest.raises(ValueError, match="Unknown metric screw size"):
        ScrewSpec(6.1, head=ScrewHeadType.SOCKET)


def test_unknown_head_raises() -> None:
    with pytest.raises(ValueError, match="Unknown head type"):
        ScrewSpec("M6", head="wingnut")


# -- nut dimensions (ISO 4032 / 4035 / 4034) ----------------------------------------------


def test_nut_dims_normal() -> None:
    assert _nut_dims(6, "normal", None) == (10, 5.2)
    assert _nut_dims(8, "normal", None) == (13, 6.8)


def test_nut_dims_thin_and_thick() -> None:
    assert _nut_dims(6, "thin", None) == (10, 3.2)
    assert _nut_dims(6, "thick", None) == (10, 5.7)


def test_nut_dims_numeric_thickness_and_width_override() -> None:
    assert _nut_dims(6, 4.0, None) == (10, 4.0)
    assert _nut_dims(6, "normal", 11) == (11, 5.2)


def test_nut_thin_falls_back_when_undefined() -> None:
    # M8 has no thin class -> falls back to normal thickness.
    assert _nut_dims(8, "thin", None) == (13, 6.8)


# -- builders all return solids -----------------------------------------------------------


@pytest.mark.parametrize(
    "head",
    [
        ScrewHeadType.SOCKET,
        ScrewHeadType.HEX,
        ScrewHeadType.BUTTON,
        ScrewHeadType.PAN,
        ScrewHeadType.FLAT,
        ScrewHeadType.NONE,
    ],
)
def test_screw_builds(head: ScrewHeadType) -> None:
    drive = (
        ScrewDriveType.HEX
        if head in (ScrewHeadType.SOCKET, ScrewHeadType.BUTTON, ScrewHeadType.NONE)
        else ScrewDriveType.NONE
    )
    assert isinstance(Screw("M6", 20, head=head, drive=drive, fn=8).shape(), Bosl2Solid)


def test_screw_unthreaded_and_partly_threaded() -> None:
    assert isinstance(Screw("M6", 20, thread=ThreadPitchClass.NONE, fn=8).shape(), Bosl2Solid)
    assert isinstance(Screw("M6", 20, thread_len=8, fn=8).shape(), Bosl2Solid)


@pytest.mark.parametrize("shape", [NutShape.HEX, NutShape.SQUARE])
def test_nut_builds(shape: NutShape) -> None:
    assert isinstance(Nut("M6", shape=shape, fn=8).shape(), Bosl2Solid)


def test_nut_thickness_classes_build() -> None:
    for t in ("normal", "thin", "thick", 4.0):
        assert isinstance(Nut("M6", thickness=t, fn=8).shape(), Bosl2Solid)


@pytest.mark.parametrize(
    ("head", "counterbore"),
    [
        (ScrewHeadType.NONE, 0),
        (ScrewHeadType.SOCKET, 4),
        (ScrewHeadType.FLAT, 0),
        (ScrewHeadType.HEX, 3),
    ],
)
def test_screw_hole_builds(head: ScrewHeadType, counterbore: int) -> None:
    assert isinstance(
        ScrewHole("M6", 20, head=head, counterbore=counterbore, fn=8).shape(),
        Bosl2Solid,
    )


def test_tapped_hole_builds() -> None:
    assert isinstance(ScrewHole("M6", 20, thread=ThreadPitchClass.COARSE, fn=8).shape(), Bosl2Solid)


@pytest.mark.parametrize("fit", ["close", "normal", "loose"])
def test_clearance_fits_build(fit: str) -> None:
    assert isinstance(ScrewHole("M6", 20, fit=fit, fn=8).shape(), Bosl2Solid)

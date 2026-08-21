# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.modular_hose: Loc-Line style ball-and-socket hose segments."""

import pytest

from pybosl2.parts.modular_hose import HoseSegment, HoseType, modular_hose_radius
from pybosl2.shapes3d import Bosl2Solid


def _size(s: Bosl2Solid) -> list[float]:
    _center, size = s.bounds()
    return size


def _bounds(s: Bosl2Solid) -> tuple[list[float], list[float]]:
    """The (low corner, extents) pair, so a test can say where a part sits as well as how big it is."""
    return s._native_bounds()  # type: ignore[return-value]


@pytest.mark.parametrize(
    ("size", "bore", "outer"),
    [(0.25, 3.268, 4.864), (0.5, 6.422, 8.096), (0.75, 9.902, 11.989)],
)
def test_radius_matches_profile(size: float, bore: float, outer: float) -> None:
    assert modular_hose_radius(size) == pytest.approx(bore, abs=0.01)
    assert modular_hose_radius(size, outer=True) == pytest.approx(outer, abs=0.01)


def test_bad_size_raises() -> None:
    with pytest.raises(ValueError, match="size must be 0.25, 0.5 or 0.75"):
        HoseSegment(0.3)


def test_bad_type_raises() -> None:
    with pytest.raises(ValueError, match="type must be one of"):
        HoseSegment(0.5, type="banana")


@pytest.mark.parametrize("size", [0.25, 0.5, 0.75])
def test_ball_socket_and_segment_fit_together(size: float) -> None:
    """A socket has to swallow a ball, and a segment is one of each back to back."""
    ball = _bounds(HoseSegment(size, HoseType.BALL).shape)
    socket = _bounds(HoseSegment(size, HoseType.SOCKET).shape)
    segment = _bounds(HoseSegment(size, HoseType.SEGMENT).shape)

    for lo, extents in (ball, socket, segment):
        assert extents[0] == pytest.approx(extents[1], rel=0.01)  # round in plan
        assert lo == pytest.approx([-e / 2 for e in extents], abs=0.01)  # centred on the origin

    # The socket is the receiving end, so it is bigger than the ball in every direction.
    for axis in range(3):
        assert socket[1][axis] > ball[1][axis]

    # A segment carries a ball on one end and a socket on the other: as wide as the socket, and
    # longer than either end alone.
    assert segment[1][:2] == pytest.approx(socket[1][:2])
    assert segment[1][2] > socket[1][2] + ball[1][2] * 0.5


@pytest.mark.parametrize("size", [0.25, 0.5, 0.75])
@pytest.mark.parametrize(("alias", "canonical"), [(HoseType.SMALL, HoseType.BALL), (HoseType.BIG, HoseType.SOCKET)])
def test_type_aliases_build_the_same_part(size: float, alias: HoseType, canonical: HoseType) -> None:
    """SMALL and BIG are the BOSL2 spellings of BALL and SOCKET, not separate shapes."""
    assert repr(HoseSegment(size, alias).shape) == repr(HoseSegment(size, canonical).shape)


def test_bigger_size_bigger_hose() -> None:
    assert _size(HoseSegment(0.75, HoseType.SEGMENT).shape)[0] > _size(HoseSegment(0.25, HoseType.SEGMENT).shape)[0]


def test_clearance_widens_socket() -> None:
    tight = _size(HoseSegment(0.5, HoseType.SEGMENT, clearance=0).shape)[0]
    loose = _size(HoseSegment(0.5, HoseType.SEGMENT, clearance=0.3).shape)[0]
    assert loose > tight

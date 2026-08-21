# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.linear_bearings: LMxUU bearings, the size table, and pillow-block housings."""

import pytest

from pybosl2.parts.linear_bearings import LinearBearings, LinearBearingSpec
from pybosl2.shapes3d import Bosl2Solid


def _size(s: Bosl2Solid) -> list[float]:
    _min, size = s._native_bounds()  # type: ignore[misc]
    return size


def test_info_returns_dataclass() -> None:
    spec = LinearBearings.lmxuu_info(8)
    assert isinstance(spec, LinearBearingSpec)
    assert (spec.outer_diameter, spec.length) == (15, 24)
    assert LinearBearings.lmxuu_info(12).outer_diameter == 21


def test_unknown_size_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported lmXuu linear bearing size"):
        LinearBearings.lmxuu_info(7)


@pytest.mark.parametrize(("size", "outer_diameter", "length"), [(8, 15, 24), (12, 21, 30), (20, 32, 42)])
def test_lmxuu_bearing_envelope(size: int, outer_diameter: int, length: int) -> None:
    b = LinearBearings.lmxuu_bearing(size)
    w, _wy, height = _size(b)
    assert w == pytest.approx(outer_diameter, abs=0.5)
    assert height == pytest.approx(length, abs=0.05)


@pytest.mark.parametrize(
    ("length", "outer_diameter", "inner_diameter"),
    [(24, 15, 8), (30, 21, 12)],
)
def test_generic_bearing_is_a_bored_tube(length: float, outer_diameter: float, inner_diameter: float) -> None:
    """The envelope is the outer diameter by the length, and the bore really is cut."""
    bearing = LinearBearings.linear_bearing(
        length=length,
        outer_diameter=outer_diameter,
        inner_diameter=inner_diameter,
        fn=None,
        fa=None,
        fs=None,
    )
    lo, size = bearing._native_bounds()  # type: ignore[misc]
    assert size[0] == pytest.approx(outer_diameter, abs=0.5)  # faceted circle, slightly under
    assert size[1] == pytest.approx(outer_diameter, abs=0.5)
    assert size[2] == pytest.approx(length)
    assert lo[2] == pytest.approx(-length / 2)  # centred on its own axis

    # A bore is a hole: no bounding box can see it, so check it was cut at the stated radius.
    program = repr(bearing)
    assert f"r1 = {inner_diameter / 2:g}, r2 = {inner_diameter / 2:g}" in program
    assert f"r1 = {outer_diameter / 2:g}, r2 = {outer_diameter / 2:g}" in program


@pytest.mark.parametrize("size", [8, 12, 20])
def test_housing_wraps_its_bearing(size: int) -> None:
    """A pillow block is as long as the bearing it holds, and thicker than it in the other two."""
    spec = LinearBearings.lmxuu_info(size)
    housing = _size(LinearBearings.lmxuu_housing(size))
    assert housing[1] == pytest.approx(spec.length)  # the bore runs the bearing's full length
    assert housing[0] > spec.outer_diameter  # walls and mounting flanges on either side
    assert housing[2] > spec.outer_diameter


def test_housing_grows_with_bearing() -> None:
    small = _size(LinearBearings.lmxuu_housing(8))[1]
    big = _size(LinearBearings.lmxuu_housing(20))[1]
    assert big > small

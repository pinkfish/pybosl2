# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2.sliders: V-groove sliders and rails."""

import pytest

from bosl2.sliders import Sliders as S
from bosl2.shapes3d import Bosl2Solid


def _size(solid):
    _min, size = solid._native_bounds()
    return size


@pytest.mark.parametrize(
    "kw",
    [
        {"length": 30, "base": 10, "wall": 4, "slop": 0.2},
        {"length": 40, "w": 14, "height": 12, "base": 8, "wall": 5},
    ],
)
def test_slider_builds(kw):
    assert isinstance(S.slider(**kw), Bosl2Solid)


def test_rail_envelope():
    radius = S.rail(length=100, w=10, height=10)
    assert isinstance(radius, Bosl2Solid)
    w, length, height = _size(radius)
    assert w == pytest.approx(10, abs=0.1)
    assert length == pytest.approx(100, abs=0.1)
    assert height == pytest.approx(10, abs=0.2)


def test_rail_length_scales():
    assert (
        _size(S.rail(length=100, w=10, height=10))[1]
        > _size(S.rail(length=40, w=10, height=10))[1]
    )


def test_slider_slop_widens_fit():
    # more slop -> a slightly larger slider footprint
    tight = _size(S.slider(length=30, slop=0.0))
    loose = _size(S.slider(length=30, slop=0.4))
    assert loose[1] >= tight[1]

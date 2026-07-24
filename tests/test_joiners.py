# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for bosl2.joiners: dovetail joints and snap-pin connectors."""

import math
import pytest

from bosl2.joiners import Joiners as J
from bosl2.shapes3d import Bosl2Solid


def _size(s):
    _min, size = s._native_bounds()
    return size


def test_dovetail_flares_to_top_width():
    # top width = base width + 2*height/slope; the dovetail is wider than its base
    dt = J.dovetail("male", width=15, height=8, slide=30, slope=6)
    w, sl, height = _size(dt)
    assert w == pytest.approx(15 + 2 * 8 / 6, abs=0.1)
    assert sl == pytest.approx(30, abs=0.1)
    assert height == pytest.approx(8, abs=0.05)


def test_steeper_angle_flares_more():
    # slope = 1/tan(angle): a bigger dovetail angle -> smaller slope -> more flare
    shallow = _size(J.dovetail("male", width=15, height=8, slide=30, angle=15))[0]
    steep = _size(J.dovetail("male", width=15, height=8, slide=30, angle=45))[0]
    assert steep > shallow


def test_female_is_enlarged_by_slop():
    male = _size(J.dovetail("male", width=15, height=8, slide=30))
    female = _size(J.dovetail("female", width=15, height=8, slide=30, slop=0.2))
    assert female[2] > male[2]  # female taller by the slop


@pytest.mark.parametrize("kw", [{}, {"taper": 4}, {"back_width": 12}])
def test_dovetail_taper_builds(kw):
    assert isinstance(
        J.dovetail("male", width=18, height=6, slide=40, **kw), Bosl2Solid
    )


def test_snap_pin_and_socket_build():
    assert isinstance(J.snap_pin(), Bosl2Solid)
    assert isinstance(J.snap_pin_socket(), Bosl2Solid)


def test_socket_bore_clears_the_pin():
    # the socket relief is at least as wide as the pin's barb so the pin fits
    pin_w = _size(J.snap_pin(diameter=5, nub_depth=0.6))[0]
    sock_w = _size(J.snap_pin_socket(diameter=5, nub_depth=0.6))[0]
    assert sock_w >= pin_w

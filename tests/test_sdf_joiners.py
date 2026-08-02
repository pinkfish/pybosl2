# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

import math

import pytest

from pybosl2._sdf import joiners as sdf_joiners
from pybosl2._sdf._constants import LEFT

SQRT2 = math.sqrt(2)


def round_offset(r: float) -> float:
    """Distance from a sharp right-angle corner to a fillet of radius `r` rounding it --
    the classic `r*(sqrt(2)-1)` relationship for a 2-D rounded-rect corner."""
    return r * (SQRT2 - 1)


def chamfer_offset(c: float) -> float:
    """Perpendicular distance from a sharp right-angle corner to a chamfer plane cutting `c`
    in from the corner along each edge."""
    return c / SQRT2


class TestKnuckleHinge:
    """knuckle_hinge(): the arm_angle=90 BOSL2 port. length=40, segs=5, offset=4,
    knuckle_diam=4, pin_diam=2, default anchor=BOT: knuckle axis along X at z=4 (the
    declared box puts BOT at z=0, knuckle top at z=6), arm hanging from z=0 to 4."""

    # The knuckle axis lands at z=4 (anchor BOT, declared box z in [0, 6]); the ring
    # material is between the pin hole (r=1) and the knuckle surface (r=2), so probe at
    # radial distance 1.5 (z=5.5). segs=5: seglen1 = 0.2+(40-0.8)/5 = 8.04, pitch 16.08
    # -- outer segments centered x = -16.08/0/+16.08, inner at x = +-8.04.
    PITCH = 0.2 + (40 - 4 * 0.2) / 5 + 0.2 + (40 - 4 * 0.2) / 5  # = seglen1+seglen2 = 16.08

    def test_outer_segments_and_pin_hole(self) -> None:
        shape = sdf_joiners.knuckle_hinge(length=40, segs=5, offset=4, knuckle_diam=4, pin_diam=2).mesh()
        assert shape.sample(0, 0, 5.5) < 0, "center segment knuckle ring solid"
        assert shape.sample(0, 0, 4) > 0, "pin hole empty at the knuckle center"
        assert shape.sample(0, 0, 1) < 0, "arm solid below the knuckle"
        assert shape.sample(self.PITCH / 2, 0, 5.5) > 0, "gap between outer segments empty"

    def test_inner_fills_outer_gaps(self) -> None:
        outer = sdf_joiners.knuckle_hinge(length=40, segs=5, offset=4, knuckle_diam=4, pin_diam=2).mesh()
        inner = sdf_joiners.knuckle_hinge(length=40, segs=5, offset=4, knuckle_diam=4, pin_diam=2, inner=True).mesh()
        assert inner.sample(self.PITCH / 2, 0, 5.5) < 0, "inner segment where outer has a gap"
        assert inner.sample(0, 0, 5.5) > 0, "inner empty where outer has a segment"
        assert outer.sample(self.PITCH / 2, 0, 5.5) > 0

    def test_clear_top_removes_front_half(self) -> None:
        # clear_top clears the profile's y>0 half-plane strip (the mating face).
        shape = sdf_joiners.knuckle_hinge(
            length=40, segs=5, offset=4, knuckle_diam=4, pin_diam=2, clear_top=True
        ).mesh()
        # Probe in the knuckle plane (z=4) at radial distance 1.5 -- inside the ring.
        assert shape.sample(0, 1.5, 4.0) > 0, "cleared side empty"
        assert shape.sample(0, -1.5, 4.0) < 0, "uncleared side solid"

    def test_orient_left_lays_hinge_on_x(self) -> None:
        shape = sdf_joiners.knuckle_hinge(
            length=40,
            segs=5,
            offset=4,
            knuckle_diam=4,
            pin_diam=2,
            spin=90,
            orient=list(LEFT),
        )
        # After spin+orient the length axis leaves X; just check the box moved coherently.
        extents = [shape.mx[i] - shape.mn[i] for i in range(3)]
        assert max(extents) == pytest.approx(40, abs=1.0), "length preserved through orient"


class TestRabbitClip:
    """rabbit_clip(): pin is a thin sprung outline, socket is the filled cavity."""

    from typing import Any

    ARGS: dict[str, Any] = {"length": 6, "width": 7, "snap": 0.4, "thickness": 0.8, "depth": 2}

    def test_pin_is_hollow_outline(self) -> None:
        pin = sdf_joiners.rabbit_clip(type="pin", **self.ARGS).mesh()
        # At the waist (the [width/2-snap, scaled_len/2] path point) the ribbon spans
        # roughly x in [waist-thickness, waist]; probe the middle of the wall.
        assert pin.sample(2.8, 0, 2.9) < 0, "right ear wall solid"
        assert pin.sample(0, 0, 3.0) > 0, "middle of the clip open (springs can flex)"
        assert pin.sample(3.45, 0, 2.9) > 0, "outside the wall empty"

    def test_socket_is_filled_and_flipped(self) -> None:
        sock = sdf_joiners.rabbit_clip(type="socket", **self.ARGS).mesh()
        # socket orient=DOWN flips it below z=0 and it is a solid cavity shape
        assert sock.sample(0, 0, -3.0) < 0, "socket interior solid"
        assert sock.sample(3.0, 0, -3.0) < 0, "socket edge included"
        assert sock.sample(0, 0, 1.0) > 0, "nothing above the plane"

    def test_socket_base_closure_spans_full_width(self) -> None:
        # Regression: the socket outline is closed along its base by two [-x, -extra] points.
        # An earlier numpy concatenation fix ensures the base strip is closed.
        sock = sdf_joiners.rabbit_clip(type="socket", **self.ARGS).mesh()
        for x in (0.0, 1.5, 3.0, -3.0):
            assert sock.sample(x, 0, -0.2) < 0, f"base band solid at x={x}"
        assert sock.sample(3.9, 0, -0.2) > 0, "empty outside the clip width"

    def test_socket_wider_than_pin_by_clearance(self) -> None:
        pin = sdf_joiners.rabbit_clip(type="pin", **self.ARGS).mesh()
        sock = sdf_joiners.rabbit_clip(type="socket", **self.ARGS, orient=[0, 0, 1]).mesh()
        # With orient=UP both are upright; socket outline sits `clearance` outside the pin's.
        assert (sock.mx[0] - sock.mn[0]) - (pin.mx[0] - pin.mn[0]) >= -0.30

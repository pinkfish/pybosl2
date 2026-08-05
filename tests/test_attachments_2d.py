# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

import pytest

from pybosl2 import Anchor
from pybosl2.shapes2d import circle, square


def test_2d_attach() -> None:
    parent = square([20, 20])
    child = circle(radius=5)

    # Attach circle to the right face of the square
    attached = parent.attach(Anchor.RIGHT, child)
    assert len(attached.attachments) == 1

    # Verify that the placement translated the child:
    # circle center should be placed at X = 10 (half of parent width) + 5 (child radius) = 15
    placed_child = attached.attachments[0]
    center, size = placed_child.bounds()
    assert center[0] == pytest.approx(15.0)
    assert center[1] == pytest.approx(0.0)


def test_2d_position() -> None:
    parent = square([20, 20])
    child = circle(radius=5)

    # Position child at top-left corner
    positioned = parent.position(Anchor.TOP_LEFT, child)
    assert len(positioned.attachments) == 1

    placed_child = positioned.attachments[0]
    center, size = placed_child.bounds()
    assert center[0] == pytest.approx(-10.0)
    assert center[1] == pytest.approx(10.0)


def test_2d_align() -> None:
    parent = square([20, 20])
    child = circle(radius=5)

    # Align child to top face of square
    aligned = parent.align(Anchor.TOP, child)
    assert len(aligned.attachments) == 1

    placed_child = aligned.attachments[0]
    center, size = placed_child.bounds()
    # circle's bottom anchor should touch square's top anchor
    # square top is Y = 10. Circle radius is 5.
    # circle center should be Y = 10 + 5 = 15
    assert center[0] == pytest.approx(0.0)
    assert center[1] == pytest.approx(15.0)

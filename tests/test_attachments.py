# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

import pytest

from pybosl2 import Anchor, AttachTag, diff
from pybosl2._backend import get_backend, use_backend
from pybosl2.exceptions import UnsupportedByBackendError
from pybosl2.shapes3d import cuboid, cylinder


def test_basic_attachment() -> None:
    """Verify that attachments are recorded in the shape's attachment list."""
    cube = cuboid([10, 10, 10])
    cyl = cylinder(radius=2, height=5)

    attached = cube.attach(Anchor.TOP, cyl)
    assert len(attached.attachments) == 1
    # Check that it did not union immediately in the wrapped shape
    assert attached.shape is cube.shape

    # Check bounds are computed for parent only before realization
    b_center, b_size = attached.bounds()
    assert b_center == [0.0, 0.0, 0.0]
    assert b_size == [10.0, 10.0, 10.0]

    # Realization produces the actual unioned shape
    realized = attached.realize()
    assert len(realized.attachments) == 0
    center, size = realized.bounds()
    assert pytest.approx(center) == [0.0, 0.0, 2.5]
    assert pytest.approx(size) == [10.0, 10.0, 15.0]


def test_transform_propagation() -> None:
    """Verify transforms are recursively applied to children in the tree."""
    cube = cuboid([10, 10, 10])
    cyl = cylinder(radius=2, height=5)
    attached = cube.attach(Anchor.TOP, cyl)

    # Translate parent
    moved = attached.translate([10, 0, 0])
    assert len(moved.attachments) == 1

    # The parent bounds translated
    b_center, b_size = moved.bounds()
    assert b_center == [10.0, 0.0, 0.0]
    assert b_size == [10.0, 10.0, 10.0]

    # The realized translated shape bounds
    center, size = moved.realize().bounds()
    assert pytest.approx(center) == [10.0, 0.0, 2.5]
    assert pytest.approx(size) == [10.0, 10.0, 15.0]


def test_tag_propagation_and_tag_this() -> None:
    """Verify tag inheritance and tag_this scoping."""
    cube = cuboid([10, 10, 10])
    cyl1 = cylinder(radius=2, height=5)
    cyl2 = cylinder(radius=1, height=5)

    # Propagated tag
    nested = cube.attach(Anchor.TOP, cyl1.attach(Anchor.TOP, cyl2)).tag(AttachTag.REMOVE)
    assert nested.tag_name == "remove"
    # Child shapes inherit the tag during realize
    realized = nested.realize()
    assert realized.tag_name == "remove"

    # tag_this: only the cube gets the tag
    tagged_this = cube.attach(Anchor.TOP, cyl1).tag_this(AttachTag.REMOVE)
    # Resolve children to check they inherited or not
    node = tagged_this._realize_node("")
    assert node.tag_name == "remove"
    assert node.shape is not None


def test_diff_realization() -> None:
    """Verify difference resolution tags (diff/remove)."""
    cube = cuboid([10, 10, 10])
    cyl = cylinder(radius=2, height=10).tag(AttachTag.REMOVE)

    # Without diff, it unions by default
    attached = cube.attach(Anchor.TOP, cyl)
    center, size = attached.realize().bounds()
    assert pytest.approx(center) == [0.0, 0.0, 5.0]
    assert pytest.approx(size) == [10.0, 10.0, 20.0]

    # With diff, it subtracts the remove tag
    diffed = diff(attached)
    center, size = diffed.realize().bounds()
    # Bounding box of the cube (even with a hole/subtraction) is still the original cube size
    assert pytest.approx(center) == [0.0, 0.0, 0.0]
    assert pytest.approx(size) == [10.0, 10.0, 10.0]


def test_negative_roundover_keep() -> None:
    """Verify negative rounding (fillets) adds material using KEEP tag."""
    cube = cuboid([20, 20, 20])
    # Apply positive rounding -> default remove tag
    pos_round = cube.edge_profile(edges=Anchor.Z, r=3)
    assert pos_round.attachments[0].tag_name == "remove"

    # Apply negative rounding -> keep tag
    neg_round = cube.edge_profile(edges=Anchor.Z, r=-3)
    assert neg_round.attachments[0].tag_name == "keep"

    # The fillet extends Z edges, adding material.
    center, size = neg_round.realize().bounds()
    assert size[0] > 20.0


def test_sdf_backend_error() -> None:
    """Verify that calling attachment/tagging methods on the SDF backend raises UnsupportedByBackendError."""
    with use_backend("sdf"):
        s = get_backend().construct("sphere", radius=10)
        with pytest.raises(UnsupportedByBackendError):
            s.attach(Anchor.TOP, s)
        with pytest.raises(UnsupportedByBackendError):
            s.tag(AttachTag.REMOVE)
        with pytest.raises(UnsupportedByBackendError):
            s.realize()

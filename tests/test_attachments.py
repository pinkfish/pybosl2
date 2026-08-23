# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

import pytest

from pybosl2 import Anchor, AttachTag, diff, intersect
from pybosl2._backend import get_backend, use_backend
from pybosl2.exceptions import UnsupportedByBackendError
from pybosl2.shapes3d import cuboid, cylinder, sphere


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
        s = get_backend().construct("sphere", {"radius": 10})
        with pytest.raises(UnsupportedByBackendError):
            s.attach(Anchor.TOP, s)
        with pytest.raises(UnsupportedByBackendError):
            s.tag(AttachTag.REMOVE)
        with pytest.raises(UnsupportedByBackendError):
            s.realize()


# --- intersect() resolution ---------------------------------------------------------------
#
# A CENTER attachment puts the child concentric with the parent, which is the only way to get an
# overlap to intersect: attach(TOP, ...) seats the child *on* the face, where the two merely touch.


def test_attach_at_center_places_the_child_without_turning_it() -> None:
    """CENTER has no direction, so there are no faces to bring together: the child keeps its own
    orientation and sits concentric with the parent."""
    box = cuboid([10, 10, 10])
    tall = cylinder(radius=2, height=30)
    _centre, size = box.attach(Anchor.CENTER, tall).realize().bounds()
    assert float(size[2]) == pytest.approx(30.0)  # still upright, not laid over
    assert float(size[0]) == pytest.approx(10.0)  # and centred, so the box still sets the width


def test_a_child_anchored_at_its_own_center_straddles_the_face() -> None:
    """child_anchor=CENTER mates the child's centre to the parent's face, so half of it hangs
    over the edge rather than sitting on top."""
    box = cuboid([10, 10, 10])
    ball = sphere(radius=3)
    _centre, size = box.attach(Anchor.TOP, ball, child_anchor=Anchor.CENTER).realize().bounds()
    assert float(size[2]) > 10.0  # it pokes out above ...
    assert float(size[2]) < 10.0 + 2 * 3  # ... but by less than a whole ball


def test_intersect_keeps_only_what_the_tagged_child_covers() -> None:
    """A ball smaller than the box's diagonal shaves the corners off, so the result is bounded by
    the box but is no longer the whole box."""
    box = cuboid([10, 10, 10])
    ball = sphere(radius=6).tag(AttachTag.INTERSECT)
    realized = intersect(box.attach(Anchor.CENTER, ball)).realize()
    lo, size = realized._native_bounds()
    assert [float(v) for v in size] == pytest.approx([10.0, 10.0, 10.0], abs=0.01)
    assert [float(v) for v in lo] == pytest.approx([-5.0, -5.0, -5.0], abs=0.01)


def test_intersect_with_nothing_tagged_leaves_nothing() -> None:
    """Intersecting with an empty set of shapes is empty -- an untagged child does not stand in
    for the missing intersector."""
    box = cuboid([10, 10, 10])
    realized = intersect(box.attach(Anchor.CENTER, cylinder(radius=2, height=20))).realize()
    assert realized._native_bounds() is None  # no bounding box at all: the solid is empty


def test_an_untagged_child_is_intersected_along_with_the_parent() -> None:
    """Untagged children join the geometry being cut down, so a spike through the box survives
    only as far as the tagged ball reaches -- further than the box alone, but no further."""
    box = cuboid([10, 10, 10])
    ball = sphere(radius=6).tag(AttachTag.INTERSECT)
    spike = cylinder(radius=2, height=30)
    with_spike = intersect(box.attach(Anchor.CENTER, ball).attach(Anchor.CENTER, spike)).realize()
    without = intersect(box.attach(Anchor.CENTER, ball)).realize()
    assert float(with_spike._native_bounds()[1][2]) > float(without._native_bounds()[1][2])
    assert float(with_spike._native_bounds()[1][2]) < 2 * 6 + 0.01  # never beyond the ball itself


def test_intersect_adds_kept_children_back_afterwards() -> None:
    """A keep-tagged child is unioned on after the intersection, so it is not cut down by it."""
    box = cuboid([10, 10, 10])
    ball = sphere(radius=6).tag(AttachTag.INTERSECT)
    kept = cylinder(radius=2, height=8).tag(AttachTag.KEEP)
    realized = intersect(box.attach(Anchor.CENTER, ball).attach(Anchor.TOP, kept)).realize()
    # the kept cylinder stands on the box's top face, well outside the ball
    assert float(realized._native_bounds()[1][2]) == pytest.approx(18.0, abs=0.01)


def test_several_intersect_tags_are_unioned_into_one_cutter() -> None:
    """Two tagged children keep whatever *either* covers, not only what both do: a ball plus a
    spike through it reaches the full height of the box, where the ball alone stops short."""
    box = cuboid([10, 10, 10])
    ball = sphere(radius=3).tag(AttachTag.INTERSECT)
    spike = cylinder(radius=2, height=30).tag(AttachTag.INTERSECT)
    ball_only = intersect(box.attach(Anchor.CENTER, ball)).realize()
    with_spike = intersect(box.attach(Anchor.CENTER, ball).attach(Anchor.CENTER, spike)).realize()
    assert float(ball_only._native_bounds()[1][2]) < 6.01  # bounded by the ball
    assert float(with_spike._native_bounds()[1][2]) == pytest.approx(10.0)  # the spike, box-clipped
    # the spike is narrower than the ball, so the union is no wider than the ball alone
    assert float(with_spike._native_bounds()[1][0]) == pytest.approx(float(ball_only._native_bounds()[1][0]))

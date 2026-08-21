# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/masking.py: cuboid corner, face and edge profile masking methods."""

from pybosl2._edges_lang import Anchor
from pybosl2.masking import mask2d_roundover, rounding_edge_mask
from pybosl2.shapes3d import cuboid, sphere


def test_corner_profile_rounds_all_corners() -> None:
    """The corner is taken off and nothing else is: the faces, edges and interior all survive.

    The cutter used to be inverted -- it scooped out the body and left the corner standing -- and
    `assert result is not None` could not see it (PLAN X-8).
    """
    rounded = cuboid([20, 20, 20]).corner_profile(radius=3).realize()
    assert not rounded.inside([9.5, 9.5, 9.5])  # the corner itself is gone
    assert rounded.inside([8.0, 8.0, 8.0])  # ...up to the fillet's own sphere
    assert rounded.inside([0.0, 0.0, 0.0])  # the middle is untouched
    assert rounded.inside([9.9, 9.9, 0.0])  # so is the vertical edge between two corners
    assert rounded.inside([0.0, 0.0, 9.9])  # ...and the middle of the top face


def test_corner_profile_specific_corners() -> None:
    """A corner selection treats only the corners it names, leaving the rest sharp."""
    selected = cuboid([20, 20, 20]).corner_profile(radius=3, corners=[0, 0, 1]).realize()
    assert not selected.inside([9.5, 9.5, 9.5])  # a +Z corner, selected
    assert selected.inside([9.5, 9.5, -9.5])  # the -Z corner below it, untouched


def test_face_profile_rounds_faces() -> None:
    """A face profile rounds the whole rim of that face, and leaves the opposite one sharp."""
    rounded = cuboid([20, 20, 20]).face_profile(radius=2, faces=[[0, 0, 1]]).realize()  # type: ignore[list-item]
    assert not rounded.inside([9.5, 9.5, 9.5])  # a corner of the top face
    assert not rounded.inside([9.7, 0.0, 9.7])  # ...and the middle of a top edge
    assert rounded.inside([9.5, 9.5, -9.5])  # the bottom corner below it is untouched
    assert rounded.inside([9.7, 9.7, 0.0])  # so is the vertical edge between them
    assert rounded.inside([0.0, 0.0, 9.9])  # and the face itself stays flat


def test_edge_profile_rounds_edges() -> None:
    """With no edge selection every edge is rounded -- vertical and horizontal alike."""
    rounded = cuboid([20, 20, 20]).edge_profile(children=mask2d_roundover(radius=2)).realize()  # type: ignore[arg-type]
    assert not rounded.inside([9.7, 9.7, 0.0])  # a vertical edge
    assert not rounded.inside([9.7, 0.0, 9.7])  # a top edge
    assert not rounded.inside([9.5, 9.5, 9.5])  # and the corner where they meet
    assert rounded.inside([0.0, 0.0, 9.9])  # the faces are left alone
    assert rounded.inside([9.9, 0.0, 0.0])


def test_edge_profile_specific_edges() -> None:
    """`edges=Anchor.Z` takes only the four vertical edges; the horizontal ones stay sharp."""
    rounded = cuboid([20, 20, 20]).edge_profile(edges=Anchor.Z, children=mask2d_roundover(radius=2)).realize()
    assert not rounded.inside([9.7, 9.7, 0.0])  # a vertical edge, rounded
    assert rounded.inside([9.7, 0.0, 9.7])  # a top edge, left alone
    assert rounded.inside([0.0, 0.0, 9.9])


def test_edge_profile_asymmetric() -> None:
    """A tapered edge mask cuts a shallow fillet -- 1mm here, so only the last 0.1mm goes."""
    cutter = rounding_edge_mask(length=30, radius1=1, radius2=3)
    rounded = cuboid([20, 20, 20]).edge_mask(edges=Anchor.Z, children=cutter).realize()
    assert not rounded.inside([9.9, 9.9, 0.0])  # right at the vertical edge
    assert rounded.inside([9.8, 9.8, 0.0])  # ...but the small radius leaves the rest
    assert rounded.inside([9.9, 0.0, 0.0])  # and the faces are untouched


def test_edge_mask_applies_children() -> None:
    """edge_mask subtracts the child along every edge, whatever shape the child is."""
    grooved = cuboid([20, 20, 20]).edge_mask(edges=Anchor.ALL, children=sphere(radius=3)).realize()
    assert not grooved.inside([9.7, 9.7, 0.0])  # the sphere swept along a vertical edge
    assert not grooved.inside([9.7, 0.0, 9.7])  # ...and along a horizontal one
    assert grooved.inside([0.0, 0.0, 9.9])  # the faces survive
    assert grooved.inside([0.0, 0.0, 0.0])

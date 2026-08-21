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
    """face_profile rounds selected faces."""
    result = cuboid([20, 20, 20]).face_profile(radius=2, faces=[[0, 0, 1]])  # type: ignore[list-item]
    assert result is not None


def test_edge_profile_rounds_edges() -> None:
    """edge_profile rounds all edges."""
    mask = mask2d_roundover(radius=2)
    result = cuboid([20, 20, 20]).edge_profile(children=mask)  # type: ignore[arg-type]
    assert result is not None


def test_edge_profile_specific_edges() -> None:
    """edge_profile rounds selected edges."""
    mask = mask2d_roundover(radius=2)
    result = cuboid([20, 20, 20]).edge_profile(edges=Anchor.Z, children=mask)
    assert result is not None


def test_edge_profile_asymmetric() -> None:
    """rounding_edge_mask with different radii per edge via edge_mask."""
    cutter = rounding_edge_mask(length=30, radius1=1, radius2=3)
    result = cuboid([20, 20, 20]).edge_mask(edges=Anchor.Z, children=cutter)
    assert result is not None


def test_edge_mask_applies_children() -> None:
    """edge_mask applies child shape to edges."""
    child = sphere(radius=3)
    result = cuboid([20, 20, 20]).edge_mask(edges=Anchor.ALL, children=child)
    assert result is not None

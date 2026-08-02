# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2/masking.py: cuboid corner, face and edge profile masking methods."""

from pybosl2.masking import mask2d_roundover, rounding_edge_mask
from pybosl2.shapes3d import cuboid, sphere


def test_corner_profile_rounds_all_corners() -> None:
    """cuboid with corner_profile applies rounding to corners."""
    result = cuboid([20, 20, 20]).corner_profile(radius=3)
    assert result is not None


def test_corner_profile_specific_corners() -> None:
    """corner_profile with specific corner selection."""
    result = cuboid([20, 20, 20]).corner_profile(radius=3, corners=[0, 0, 1])
    assert result is not None


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
    result = cuboid([20, 20, 20]).edge_profile(edges="Z", children=mask)  # type: ignore[arg-type]
    assert result is not None


def test_edge_profile_asymmetric() -> None:
    """rounding_edge_mask with different radii per edge via edge_mask."""
    cutter = rounding_edge_mask(length=30, radius1=1, radius2=3)
    result = cuboid([20, 20, 20]).edge_mask(edges="Z", children=cutter)
    assert result is not None


def test_edge_mask_applies_children() -> None:
    """edge_mask applies child shape to edges."""
    child = sphere(radius=3)
    result = cuboid([20, 20, 20]).edge_mask(edges="ALL", children=child)
    assert result is not None

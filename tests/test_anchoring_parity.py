# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Anchoring means the same thing on both backends (TASKS T14 phase 5a).

`anchor_point`, `reanchor`, `reorient` and `orient` used to be CSG-only, which is a large part of
why the parts library is CSG-only: the parts that are not primitives are mostly anchor chains.
None of it is CSG topology though -- it is arithmetic over bounds and an anchor vector, and the SDF
backend has exact bounds. So it moved to one shared `Anchorable` mixin (`pybosl2/_anchoring.py`)
that both backends mix in, rather than being reimplemented per backend.

These tests run the same call on both and require the same answer, so the two cannot drift.
"""

from __future__ import annotations

import numpy as np
import pytest

import pybosl2.solid as solid
from pybosl2._backend import use_backend
from pybosl2._edges_lang import Anchor

ANCHORS = [
    Anchor.TOP,
    Anchor.BOTTOM,
    Anchor.LEFT,
    Anchor.RIGHT,
    Anchor.FRONT,
    Anchor.BACK,
    Anchor.CENTER,
    Anchor.TOP_FRONT_LEFT,
    Anchor.BOTTOM_BACK_RIGHT,
]


def _on(backend: str, build: object) -> object:
    with use_backend(backend):
        return build()  # type: ignore[operator]


@pytest.mark.parametrize("anchor", ANCHORS)
def test_the_anchor_point_is_the_same_on_both_backends(anchor: Anchor) -> None:
    """centre + anchor * size / 2, and both backends measure the same box for a 10x20x30 cuboid."""
    points = {}
    for backend in ("csg", "sdf"):
        with use_backend(backend):
            points[backend] = solid.cuboid([10, 20, 30]).anchor_point(anchor)  # type: ignore[attr-defined]

    expected = [v * s / 2 for v, s in zip(anchor.vector, [10, 20, 30], strict=True)]
    np.testing.assert_allclose(points["csg"], expected, atol=1e-9)
    np.testing.assert_allclose(points["sdf"], expected, atol=1e-9)


@pytest.mark.parametrize("anchor", ANCHORS)
def test_reanchor_brings_the_same_point_to_the_origin(anchor: Anchor) -> None:
    """Whatever the backend, the named point of the box ends up at [0, 0, 0]."""
    for backend in ("csg", "sdf"):
        with use_backend(backend):
            moved = solid.cuboid([10, 20, 30]).reanchor(anchor)  # type: ignore[attr-defined]
            np.testing.assert_allclose(moved.anchor_point(anchor), [0, 0, 0], atol=1e-6)
            # ... and the shape itself is unchanged, only moved
            np.testing.assert_allclose(list(moved.bounds().size), [10, 20, 30], atol=1e-6)


@pytest.mark.parametrize(
    ("orient", "expected"),
    [
        (Anchor.TOP, [10, 20, 30]),  # already upright
        (Anchor.RIGHT, [30, 20, 10]),  # X and Z swap
        (Anchor.BACK, [10, 30, 20]),  # Y and Z swap
    ],
)
def test_reorient_turns_the_box_the_same_way_on_both_backends(orient: Anchor, expected: list[float]) -> None:
    for backend in ("csg", "sdf"):
        with use_backend(backend):
            turned = solid.cuboid([10, 20, 30]).reorient(anchor=Anchor.CENTER, orient=orient)  # type: ignore[attr-defined]
        np.testing.assert_allclose([float(v) for v in turned.bounds().size], expected, atol=1e-6)


def test_orient_is_reorient_about_the_centre() -> None:
    for backend in ("csg", "sdf"):
        with use_backend(backend):
            shape = solid.cuboid([10, 20, 30])  # type: ignore[attr-defined]
            by_orient = shape.orient(Anchor.RIGHT).bounds()
            by_reorient = shape.reorient(anchor=Anchor.CENTER, orient=Anchor.RIGHT).bounds()
        np.testing.assert_allclose([float(v) for v in by_orient.size], [float(v) for v in by_reorient.size], atol=1e-9)
        np.testing.assert_allclose(
            [float(v) for v in by_orient.center], [float(v) for v in by_reorient.center], atol=1e-9
        )


def test_a_supplied_box_overrides_the_shapes_own() -> None:
    """`bbox=` anchors against a box the caller names -- the same override on either backend."""
    for backend in ("csg", "sdf"):
        with use_backend(backend):
            point = solid.cuboid([10, 20, 30]).anchor_point(  # type: ignore[attr-defined]
                Anchor.TOP, bbox=[[0, 0, 0], [2, 2, 2]]
            )
        np.testing.assert_allclose(point, [1, 1, 2], atol=1e-9)


@pytest.mark.parametrize("bad", [[[0, 0, 0]], [[0, 0, 0], [1, 1]], [[5, 5, 5], [0, 0, 0]]])
def test_a_malformed_box_is_rejected_on_both_backends(bad: object) -> None:
    for backend in ("csg", "sdf"):
        with use_backend(backend), pytest.raises(ValueError, match="bbox must be"):
            solid.cuboid([10, 20, 30]).anchor_point(Anchor.TOP, bbox=bad)  # type: ignore[attr-defined,arg-type]


def test_reanchor_records_the_anchor_where_a_nominal_box_exists() -> None:
    """Bookkeeping for SPEC S-2a: a shape with a nominal box remembers which point it sits on.

    No test covered this before the anchoring code moved to the shared mixin, and it was silently
    dropped in the move -- the whole suite stayed green with `reanchor()` no longer recording
    anything.
    """
    with use_backend("csg"):
        moved = solid.cuboid([10, 20, 30]).reanchor(Anchor.BOTTOM)  # type: ignore[attr-defined]
    assert moved.anchor is Anchor.BOTTOM

    with use_backend("sdf"):
        named = solid.cuboid([10, 20, 30]).with_nominal_size([10, 20, 30])  # type: ignore[attr-defined]
        assert named.reanchor(Anchor.BOTTOM)._nominal_anchor is Anchor.BOTTOM

    # A raw three-vector is not an Anchor, so there is nothing to record.
    with use_backend("csg"):
        assert solid.cuboid([10, 20, 30]).reanchor([0, 0, -1]).anchor is Anchor.CENTER  # type: ignore[attr-defined]

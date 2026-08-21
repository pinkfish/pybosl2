# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""`with_nominal_size()`: naming the anchor frame without reaching for a native handle.

TASKS T14 phase 2. The parts library attaches a nominal anchor box (SPEC S-2a) by re-wrapping --
`Bosl2Solid(other.shape, size=[...])` -- which only works on the CSG backend, because only it has
a `.shape` native handle. That single idiom, used 28 times across 13 of the 15 parts modules, is
why parts cannot be written to build on either backend. This is its backend-neutral replacement.
"""

from __future__ import annotations

import pytest

import pybosl2.solid as solid
from pybosl2._backend import use_backend
from pybosl2._edges_lang import Anchor

BACKENDS = ["csg", "sdf"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_the_nominal_box_is_attached_without_touching_the_geometry(backend: str) -> None:
    """SPEC S-2a: `size` is the anchor frame; `bounds()` keeps reporting what was built."""
    with use_backend(backend):
        shape = solid.cuboid([10, 20, 30])  # type: ignore[attr-defined]
        named = shape.with_nominal_size([1, 2, 3])

    assert named.nominal_size == pytest.approx([1.0, 2.0, 3.0])
    assert named.backend == backend
    for got, want in zip(named.bounds()[1], [10, 20, 30], strict=True):
        assert abs(float(got) - want) < 0.01, "the nominal box must not change what bounds() says"


@pytest.mark.parametrize("backend", BACKENDS)
def test_it_returns_a_new_shape_and_leaves_the_original_alone(backend: str) -> None:
    with use_backend(backend):
        shape = solid.cuboid([10, 20, 30])  # type: ignore[attr-defined]
        named = shape.with_nominal_size([1, 2, 3])

    assert named is not shape
    assert named.nominal_size == pytest.approx([1.0, 2.0, 3.0])
    # The CSG constructors record their own size; the SDF ones carry none until one is attached.
    assert shape.nominal_size != pytest.approx([1.0, 2.0, 3.0]) if shape.nominal_size else True


@pytest.mark.parametrize("backend", BACKENDS)
def test_the_nominal_box_survives_a_transform(backend: str) -> None:
    """It is metadata, like colour, so an exact move does not drop it (or force a mesh)."""
    with use_backend(backend):
        moved = solid.cuboid([10, 20, 30]).with_nominal_size([1, 2, 3]).translate([5, 0, 0])  # type: ignore[attr-defined]

    assert moved.nominal_size == pytest.approx([1.0, 2.0, 3.0])
    assert moved.bounds()[0][0] == pytest.approx(5.0)  # ... and the geometry really did move


def test_a_nominal_box_can_name_the_anchor_too() -> None:
    """A part anchors to a face of the frame it is designed around, not to its bounding box."""
    shape = solid.cuboid([10, 20, 30]).with_nominal_size([1, 2, 3], anchor=Anchor.TOP)  # type: ignore[attr-defined]
    assert shape.anchor is Anchor.TOP
    assert shape.nominal_size == pytest.approx([1.0, 2.0, 3.0])


def test_it_is_the_replacement_for_the_native_rewrap() -> None:
    """The idiom it replaces, side by side, so the equivalence is on the record.

    `Bosl2Solid(other.shape, size=...)` is what 28 sites in the parts library do today. It reads
    `.shape` off the solid, which an SDF solid does not have -- asking for it raises rather than
    handing back a handle -- so a part written that way is CSG-only whatever else it does.
    """
    from pybosl2.shapes3d import Bosl2Solid

    built = solid.cuboid([10, 20, 30])  # type: ignore[attr-defined]
    by_rewrap = Bosl2Solid(built.shape, size=[1, 2, 3])
    by_method = built.with_nominal_size([1, 2, 3])

    assert by_method.nominal_size == pytest.approx(list(by_rewrap.size or []))
    assert by_method.bounds() == by_rewrap.bounds()

    from pybosl2.exceptions import UnsupportedByBackendError

    with use_backend("sdf"):
        sdf_solid = solid.cuboid([10, 20, 30])  # type: ignore[attr-defined]
        with pytest.raises(UnsupportedByBackendError, match="'shape'"):
            _ = sdf_solid.shape  # the re-wrap idiom cannot even get started here
        assert sdf_solid.with_nominal_size([1, 2, 3]).nominal_size == pytest.approx([1.0, 2.0, 3.0])

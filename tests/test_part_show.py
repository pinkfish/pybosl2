# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Every part's show() hands its shape to the renderer and returns it (SPEC S-49, S-51).

`show()` is the one call in the library with a session side effect, and the convention every
docstring example ends with -- so each part's delegation is exercised here rather than only in the
docs build, which needs the PythonSCAD app.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

import pybosl2.parts as parts
from pybosl2.parts.enums import ScrewDriveType, ScrewHeadType
from pybosl2.parts.threading import _iso_profile

#: A real ISO thread profile, as the threading tests build one.
_ISO_PROFILE = _iso_profile()

#: Constructor arguments for the parts that need them; everything else builds bare (SPEC P-1).
KEYWORDS: dict[str, dict[str, Any]] = {
    # RingHook needs exactly two of outer radius / inner radius / wall
    "RingHook": {"outer_radius": 25.0, "inner_radius": 20.0},
}

ARGUMENTS: dict[str, tuple[Any, ...]] = {
    "LivingHingeMask": (40, 3),
    "RingHook": ([50.0, 10.0], 25.0),  # plus the two radii below
    "HoseSegment": (0.5,),  # 1/2" is a real trade size
    "NemaMountMask": (17,),
    "HexDriveMask": (3, 5),
    "RobertsonMask": (2,),
    "TorxMask": (20,),
    "TorxMask2d": (20,),
    "hex_mask": (3, 5),
    "Screw": ("M6", 20),
    "ScrewHole": ("M6", 20),
    "Nut": ("M6",),
    "ThreadedNut": (18.0, 12.0, 10.0, 1.75, _ISO_PROFILE),
    "ThreadedRod": (16.0, 24.0, 2.0, _ISO_PROFILE),
    "ThreadHelix": (8.0, 1.25),
    "SparseCuboid": ([20, 20, 20],),
    "WireBundle": ([[0.0, 0.0, 0.0], [20.0, 0.0, 0.0], [20.0, 20.0, 0.0]], 3),
}


def _part_classes() -> list[str]:
    names = []
    for name in parts.__all__:
        obj = getattr(parts, name)
        if not inspect.isclass(obj) or not hasattr(obj, "show"):
            continue
        names.append(name)
    return sorted(names)


@pytest.mark.parametrize("name", _part_classes())
def test_show_returns_the_parts_shape(name: str) -> None:
    cls = getattr(parts, name)
    args = ARGUMENTS.get(name, ())
    part = cls(*args, **KEYWORDS.get(name, {}))
    shown = part.show()
    assert shown is not None, f"{name}.show() returned None (SPEC S-49)"


def test_show_is_the_shape_itself() -> None:
    """The value show() hands back is the shape, so a chain can continue from it."""
    screw = parts.Screw("M6", 20, head=ScrewHeadType.SOCKET, drive=ScrewDriveType.HEX)
    assert screw.show().bounds() == screw.shape.bounds()

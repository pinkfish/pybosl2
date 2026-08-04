# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/shapes3d/__init__.py
# FileSummary: Attachable cubes, cylinders, spheres, text and rulers (BOSL2 shapes3d.scad).
# DocCategory: Foundational
# FileGroup: BOSL2

from __future__ import annotations

from .base import Bosl2Solid
from .cuboid import (
    cube,
    cuboid,
    octahedron,
    prismoid,
    rect_tube,
    regular_prism,
    roof,
    wedge,
)
from .cylinder import (
    cone,
    cyl,
    cylinder,
    tube,
    xcyl,
    ycyl,
    zcyl,
)
from .extrusions import (
    cross,
    path_text,
    text3d,
)
from .sphere import (
    onion,
    sphere,
    spheroid,
    teardrop,
)
from .torus import (
    pie_slice,
    torus,
)

_SURFACE_EXPORTS = frozenset(
    {
        "interior_fillet",
        "heightfield",
        "cylindrical_heightfield",
        "plot3d",
        "plot_revolution",
        "fillet",
        "textured_tile",
        "ruler",
    }
)


def __getattr__(name: str) -> object:
    """Lazily resolve the surfaces3d re-exports (PEP 562), breaking the shapes3d<->surfaces3d cycle."""
    if name in _SURFACE_EXPORTS:
        import pybosl2.surfaces3d as _surfaces3d

        return getattr(_surfaces3d, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Bosl2Solid",
    "cube",
    "cuboid",
    "prismoid",
    "regular_prism",
    "octahedron",
    "wedge",
    "rect_tube",
    "roof",
    "cone",
    "cyl",
    "cylinder",
    "xcyl",
    "ycyl",
    "zcyl",
    "tube",
    "sphere",
    "spheroid",
    "teardrop",
    "onion",
    "torus",
    "pie_slice",
    "cross",
    "text3d",
    "path_text",
    # Lazily re-exported from surfaces3d
    "interior_fillet",
    "heightfield",
    "cylindrical_heightfield",
    "plot3d",
    "plot_revolution",
    "fillet",
    "textured_tile",
    "ruler",
]

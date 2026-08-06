# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/shapes3d/torus.py
# FileSummary: Toruses and pie slice shapes.
# DocCategory: Foundational
# FileGroup: BOSL2

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pybosl2._edges_lang import Anchor
from pybosl2._native import native

if TYPE_CHECKING:
    from collections.abc import Sequence


from pybosl2._helpers import frag_count as _frag_count
from pybosl2._helpers import pick_radius as _pick_radius
from pybosl2.constants import BOTTOM, DOWN

# Import base class and helper functions from shapes3d.base
from .base import (
    Bosl2Solid,
    _anchor_offset_cyl,
    _finish3,
    _ocylinder,
    _resolve_center_anchor,
)

if TYPE_CHECKING:  # real stub-typed imports for the checker (identical to pre-lazy)
    from pythonscad import cube as _ocube
    from pythonscad import cylinder as _ocylinder_native
    from pythonscad import hull as _ohull
    from pythonscad import minkowski as _ominkowski
    from pythonscad import polyhedron as _opolyhedron
    from pythonscad import rotate_extrude as _orotate_extrude
    from pythonscad import sphere as _osphere_native
    from pythonscad import textmetrics as _otextmetrics
else:
    _ocube = native("cube")
    _ocylinder_native = native("cylinder")
    _ohull = native("hull")
    _ominkowski = native("minkowski")
    _opolyhedron = native("polyhedron")
    _orotate_extrude = native("rotate_extrude")
    _osphere_native = native("sphere")
    _otextmetrics = native("textmetrics")


def pie_slice(
    height: float | None = None,
    radius: float | None = None,
    angle: float = 30,
    center: bool | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    length: float | None = None,
    anchor: Anchor | Sequence[float] = Anchor.CENTER,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """BOSL2 pie_slice() -- a pie slice, wedge of a cylinder/cone.

    Args:
        height:    height of the pie slice
        length:    height of the pie slice
        radius:      radius of the pie slice
        angle:    pie slice angle in degrees (default 30)
        center: if given, overrides anchor
        radius1:  bottom radius of the pie slice
        radius2:  top radius of the pie slice
        diameter: diameter of the pie slice
        diameter1: diameter of the bottom
        diameter2: diameter of the top
        anchor: anchor point (default CENTER)
        spin:   Z-axis rotation in degrees after anchor (default 0)
        orient: direction to rotate the top towards, after spin (default UP)
        fn: arc smoothness overrides
        fa: arc smoothness overrides
        fs: arc smoothness overrides

    Examples:
        .. pythonscad-example::

            from pybosl2 import shapes3d as s3

            s3.pie_slice(radius=20, angle=120, height=5).show()

    """
    from pybosl2._helpers import arc_points as _arc_points
    from pybosl2._native import native

    _opolygon = native("polygon")

    length = height if height is not None else (length if length is not None else 1)
    rad1 = _pick_radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=10)
    rad2 = _pick_radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter, dflt=10)
    use_anchor = _resolve_center_anchor(center, anchor, BOTTOM)

    base = _ocylinder(
        height=length,
        radius1=rad1,
        radius2=rad2,
        center=True,
        fn=fn,
        fa=fa,
        fs=fs,
    )
    if isinstance(angle, (list, tuple)):  # [start, end] wedge
        start, sweep = float(angle[0]), float(angle[1]) - float(angle[0])
    else:
        start, sweep = 0.0, float(angle)
    ang_v = sweep % 360 if (sweep > 360 or sweep < 0) else sweep
    if ang_v <= 0 or ang_v >= 360:
        shape = base
    else:
        maxd = max(rad1, rad2) + 0.1
        sides = max(3, math.ceil(_frag_count(maxd, fn, fa, fs) * ang_v / 360))
        arc = _arc_points(sides, maxd, start, ang_v)
        sector = _opolygon([[0.0, 0.0]] + arc).linear_extrude(height=length + 0.2, center=True)
        shape = base & sector

    offset = _anchor_offset_cyl(rad1, rad2, length, use_anchor)
    return _finish3(shape, offset, spin, orient, size=None, anchor=use_anchor)


def torus(
    major_radius: float | None = None,
    minor_radius: float | None = None,
    center: bool | None = None,
    major_diameter: float | None = None,
    minor_diameter: float | None = None,
    outer_radius: float | None = None,
    inner_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_diameter: float | None = None,
    anchor: Anchor | Sequence[float] = Anchor.CENTER,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """BOSL2 torus() -- a torus (donut) shape.

    Note: BOSL2's outer-radius parameter is named `or`, which collides with the Python
    keyword `or`; it is exposed here as `outer_radius` instead.

    Args:
        major_radius:  major radius of the torus ring (use with minor_radius or minor_diameter)
        minor_radius:  minor radius of the torus ring (use with major_radius or major_diameter)
        center: if given, overrides anchor (True -> CENTER, False -> DOWN)
        major_diameter:  major diameter of the torus ring
        minor_diameter:  minor diameter of the torus ring
        outer_radius: outer radius of the torus (BOSL2 `or`) (use with inner_radius or inner_diameter)
        inner_radius:     inside radius of the torus (use with outer_radius or outer_diameter)
        outer_diameter:     outer diameter of the torus (use with inner_radius or inner_diameter)
        inner_diameter:     inside diameter of the torus (use with outer_radius or outer_diameter)
        anchor: anchor point (default CENTER)
        orient: direction to rotate the top towards, after spin (default UP)
        fn: arc smoothness overrides
        fa: arc smoothness overrides
        fs: arc smoothness overrides

    Examples:
        .. pythonscad-example::

            from pybosl2 import torus

            shape = torus(major_radius=25, minor_radius=8)
            shape.show()

    """
    from pybosl2._helpers import arc_points as _arc_points
    from pybosl2._native import native

    _opolygon = native("polygon")

    _or = _pick_radius(radius=outer_radius, diameter=outer_diameter, dflt=None)
    _ir = _pick_radius(radius=inner_radius, diameter=inner_diameter, dflt=None)
    _r_maj = _pick_radius(radius=major_radius, diameter=major_diameter, dflt=None)
    _r_min = _pick_radius(radius=minor_radius, diameter=minor_diameter, dflt=None)

    if _r_maj is not None:
        maj_rad = _r_maj
    elif _ir is not None and _or is not None:
        maj_rad = (_or + _ir) / 2
    elif _ir is not None and _r_min is not None:
        maj_rad = _ir + _r_min
    elif _or is not None and _r_min is not None:
        maj_rad = _or - _r_min
    else:
        raise AssertionError("torus(): bad parameters.")

    if _r_min is not None:
        min_rad = _r_min
    elif _ir is not None:
        min_rad = maj_rad - _ir
    elif _or is not None:
        min_rad = _or - maj_rad
    else:
        raise AssertionError("torus(): bad parameters.")

    use_anchor = _resolve_center_anchor(center, anchor, DOWN)

    sides = _frag_count(min_rad, fn, fa, fs)
    profile = _arc_points(sides, min_rad, 0, 360, [maj_rad, 0.0], endpoint=False)
    shape = _orotate_extrude(_opolygon(profile), fn=fn, fa=fa, fs=fs)
    offset = _anchor_offset_cyl(maj_rad + min_rad, maj_rad + min_rad, min_rad * 2, use_anchor)
    return _finish3(shape, offset, spin, orient, size=None, anchor=use_anchor)

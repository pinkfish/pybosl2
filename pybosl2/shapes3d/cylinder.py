# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/shapes3d/cylinder.py
# FileSummary: Cylinders, cones, shear cylinders and pipe shapes.
# DocCategory: Foundational
# FileGroup: BOSL2

"""Cylinders, cones, shear cylinders and pipe shapes."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pybosl2._edges_lang import Anchor
from pybosl2._native import native

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pybosl2.texture import TextureType

from pybosl2._helpers import frag_count as _frag_count
from pybosl2._helpers import pick_radius as _pick_radius
from pybosl2._helpers import quantup
from pybosl2.constants import BOTTOM, CENTER

# Import base class and helper functions from shapes3d.base
from .base import (
    Bosl2Solid,
    _anchor_offset_cyl,
    _finish3,
    _ocylinder,
    _osphere,
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


# ---------------------------------------------------------------------------
# Section: Cylinders
# ---------------------------------------------------------------------------


def cylinder(
    height: float | None = None,
    radius: float | None = None,
    center: bool | None = None,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    circumscribe: bool = False,
    realign: bool = False,
    shift: Sequence[float] = [0, 0],
    anchor: Anchor | Sequence[float] | None = None,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    from_end: bool = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    extra: float = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    teardrop: float | bool = False,
    clip_angle: float = 90.0,
    texture: str | TextureType | None = None,
    tex_size: float | Sequence[float] | None = None,
    tex_reps: int | Sequence[int] | None = None,
    tex_depth: float = 1.0,
    tex_inset: float | bool = False,
) -> Bosl2Solid:
    """Return a cylinder with optional chamfering/rounding of its end rims, built with.

    cube()/cylinder()/sphere()/rotate_extrude().

    Positive rounding is built as a minkowski() of a shorter cylinder with a sphere at each
    rounded end (an inset fillet, not an outward bulge), matching BOSL2's own rounded-end
    geometry. Chamfering builds the exact half-profile (with the requested bevel at each end)
    and revolves it with rotate_extrude().

    Note: ``texture=`` (VNF surface texturing) is not supported by this pure-Python port.

    Args:
        length:  length of the cylinder along its axis (default 1)
        height:  length of the cylinder along its axis (default 1)
        radius:         radius of the cylinder (default 1)
        diameter:       diameter of the cylinder
        radius1:        radius of the negative end of the cylinder
        radius2:        radius of the positive end of the cylinder
        diameter1:      diameter of the negative end of the cylinder
        diameter2:      diameter of the positive end of the cylinder
        center:         if given, overrides anchor (True -> CENTER, False -> BOTTOM)
        chamfer: chamfer size on the end rims (overall/negative/positive)
        chamfer1: chamfer size on the end rims (overall/negative/positive)
        chamfer2: chamfer size on the end rims (overall/negative/positive)
        rounding: rounding radius on the end rims (overall/negative/positive)
        rounding1: rounding radius on the end rims (overall/negative/positive)
        rounding2: rounding radius on the end rims (overall/negative/positive)
        circumscribe:   circumscribe rather than inscribe the given radius (default False)
        realign:        shift point alignment (default False)
        shift:          X/Y offset for the positive end (shear) (default [0,0])
        anchor:         anchor point (default BOTTOM if center=False, otherwise CENTER)
        spin:           Z-axis rotation in degrees after anchor (default 0)
        orient:         direction to rotate the top towards, after spin (default UP)
        fn:       arc smoothness overrides
        fa:       arc smoothness overrides
        fs:       arc smoothness overrides
        chamfer_angle: chamfer angle in degrees away from ends
        chamfer_angle1: chamfer angle in degrees away from ends
        chamfer_angle2: chamfer angle in degrees away from ends
        from_end: measure chamfer along conic face (default False)
        from_end1: measure chamfer along conic face (default False)
        from_end2: measure chamfer along conic face (default False)
        extra: add extra height at ends (invisible to anchoring)
        extra1: add extra height at ends (invisible to anchoring)
        extra2: add extra height at ends (invisible to anchoring)
        teardrop:       limit rounding angle from horizontal
        clip_angle:     clip rounding arc at bottom of cylinder
        texture:        named texture to apply to cylinder side surface
        tex_size:       size of texture tile
        tex_reps:       number of texture repetitions
        tex_depth:      depth of the texture
        tex_inset:      inset the texture

    Examples:
        A basic cylinder:

        .. pythonscad-example::

            from pybosl2.solid import cylinder

            cylinder(height=30, radius=10).show()

        A cylinder with chamfered ends:

        .. pythonscad-example::

            from pybosl2.solid import cylinder

            cylinder(height=40, radius=15, chamfer=2).show()

        A cylinder with rounded ends:

        .. pythonscad-example::

            from pybosl2.solid import cylinder

            cylinder(height=30, radius=12, rounding=2).show()

    """
    return cyl(
        height=height,
        radius=radius,
        center=center,
        length=length,
        radius1=radius1,
        radius2=radius2,
        diameter=diameter,
        diameter1=diameter1,
        diameter2=diameter2,
        chamfer=chamfer,
        chamfer1=chamfer1,
        chamfer2=chamfer2,
        rounding=rounding,
        rounding1=rounding1,
        rounding2=rounding2,
        circumscribe=circumscribe,
        realign=realign,
        shift=list(shift),
        anchor=anchor,
        spin=spin,
        orient=orient,
        fn=fn,
        fa=fa,
        fs=fs,
        chamfer_angle=chamfer_angle,
        chamfer_angle1=chamfer_angle1,
        chamfer_angle2=chamfer_angle2,
        from_end=from_end,
        from_end1=from_end1,
        from_end2=from_end2,
        extra=extra,
        extra1=extra1,
        extra2=extra2,
        teardrop=teardrop,
        clip_angle=clip_angle,
        texture=texture,
        tex_size=tex_size,
        tex_reps=tex_reps,
        tex_depth=tex_depth,
        tex_inset=tex_inset,
    )


def cyl(
    height: float | None = None,
    radius: float | None = None,
    center: bool | None = None,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    circumscribe: bool = False,
    realign: bool = False,
    shift: Sequence[float] = [0, 0],
    anchor: Anchor | Sequence[float] | None = None,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    # Additional missing args
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    from_end: bool = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    extra: float = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    teardrop: float | bool = False,
    clip_angle: float = 90.0,
    texture: str | TextureType | None = None,
    tex_size: float | Sequence[float] | None = None,
    tex_reps: int | Sequence[int] | None = None,
    tex_depth: float = 1.0,
    tex_inset: float | bool = False,
) -> Bosl2Solid:
    """Return a cylinder with optional chamfering/rounding of its end rims, built with.

    cube()/cylinder()/sphere()/rotate_extrude().

    Positive rounding is built as a minkowski() of a shorter cylinder with a sphere at each
    rounded end (an inset fillet, not an outward bulge), matching BOSL2's own rounded-end
    geometry. Chamfering builds the exact half-profile (with the requested bevel at each end)
    and revolves it with rotate_extrude().

    Note: `texture=` (VNF surface texturing) is not supported by this pure-Python port.

    Args:
        length:  length of the cylinder along its axis (default 1)
        height:  length of the cylinder along its axis (default 1)
        radius:      radius of the cylinder (default 1)
        diameter:    diameter of the cylinder
        radius1:    radius of the negative end of the cylinder
        radius2:    radius of the positive end of the cylinder
        diameter1:  diameter of the negative end of the cylinder
        diameter2:  diameter of the positive end of the cylinder
        center:   if given, overrides anchor (True -> CENTER, False -> BOTTOM)
        chamfer: chamfer size on the end rims (overall/negative/positive)
        chamfer1: chamfer size on the end rims (overall/negative/positive)
        chamfer2: chamfer size on the end rims (overall/negative/positive)
        rounding: rounding radius on the end rims (overall/negative/positive)
        rounding1: rounding radius on the end rims (overall/negative/positive)
        rounding2: rounding radius on the end rims (overall/negative/positive)
        circumscribe: circumscribe rather than inscribe the given radius (default False)
        realign:      shift point alignment (default False)
        shift:        X/Y offset for the positive end (shear) (default [0,0])
        anchor:       anchor point (default CENTER)
        spin:         Z-axis rotation in degrees after anchor (default 0)
        orient:       direction to rotate the top towards, after spin (default UP)
        fn:     arc smoothness overrides
        fa:     arc smoothness overrides
        fs:     arc smoothness overrides
        chamfer_angle: chamfer angle in degrees away from ends
        chamfer_angle1: chamfer angle in degrees away from ends
        chamfer_angle2: chamfer angle in degrees away from ends
        from_end: measure chamfer along conic face (default False)
        from_end1: measure chamfer along conic face (default False)
        from_end2: measure chamfer along conic face (default False)
        extra: add extra height at ends (invisible to anchoring)
        extra1: add extra height at ends (invisible to anchoring)
        extra2: add extra height at ends (invisible to anchoring)
        teardrop:     limit rounding angle from horizontal
        clip_angle:   clip rounding arc at bottom of cylinder
        texture:      named texture to apply to cylinder side surface
        tex_size:     size of texture tile
        tex_reps:     number of texture repetitions
        tex_depth:    depth of the texture
        tex_inset:    inset the texture

    Examples:
        A basic cylinder:
        .. pythonscad-example::

            from pybosl2 import cyl

            shape = cyl(radius=10, height=30)
            shape.show()

        A cylinder with chamfered ends:
        .. pythonscad-example::

            from pybosl2 import cyl

            shape = cyl(radius=15, height=40, chamfer=2)
            shape.show()

        A cylinder with rounded ends:
        .. pythonscad-example::

            from pybosl2 import cyl

            shape = cyl(radius=12, height=35, rounding=3)
            shape.show()

    """
    if texture is not None and texture != "none":
        raise NotImplementedError("texture= (VNF surface texturing) is not supported by this pure-Python port.")
    _ = (tex_size, tex_reps, tex_depth, tex_inset)

    length_val = next((v for v in (length, height) if v is not None), 1.0)
    rad1 = _pick_radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
    rad2 = _pick_radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter, dflt=1)

    if circumscribe:
        sides = _frag_count(max(rad1, rad2), fn, fa, fs)
        sc = 1 / math.cos(math.pi / sides)
        rad1 *= sc
        rad2 *= sc
    use_anchor = anchor
    if use_anchor is None:
        use_anchor = CENTER if center is None or center else BOTTOM

    r1v = rounding1 if rounding1 is not None else (rounding if rounding is not None else 0)
    r2v = rounding2 if rounding2 is not None else (rounding if rounding is not None else 0)
    c1v = chamfer1 if chamfer1 is not None else (chamfer if chamfer is not None else 0)
    c2v = chamfer2 if chamfer2 is not None else (chamfer if chamfer is not None else 0)
    assert not ((r1v or r2v) and (c1v or c2v)), "Cannot specify nonzero value for both chamfer and rounding"

    cfang1 = chamfer_angle1 if chamfer_angle1 is not None else (chamfer_angle if chamfer_angle is not None else None)
    cfang2 = chamfer_angle2 if chamfer_angle2 is not None else (chamfer_angle if chamfer_angle is not None else None)
    fe1 = from_end1 if from_end1 is not None else from_end
    fe2 = from_end2 if from_end2 is not None else from_end

    if not (r1v or r2v or c1v or c2v):
        shape = _ocylinder(
            height=length_val,
            radius1=rad1,
            radius2=rad2,
            center=True,
            fn=fn,
            fa=fa,
            fs=fs,
        )
    elif (
        rad1 == rad2
        and r1v == r2v
        and r1v > 0
        and not c1v
        and not c2v
        and (teardrop is False or teardrop is None)
        and clip_angle == 90.0
    ):
        # Straight cylinder, uniform rounding on both ends: exact via minkowski(cylinder, sphere).
        inner_r = max(0.001, rad1 - r1v)
        inner_l = max(0.001, length_val - 2 * r1v)
        sphere_fn = int(quantup(_frag_count(r1v, fn, fa, fs), 4))
        shape = _ominkowski(
            _ocylinder(height=inner_l, radius=inner_r, center=True, fn=fn, fa=fa, fs=fs),
            _osphere(radius=r1v, fn=sphere_fn),
        )
    else:
        profile = cyl_profile(
            rad1,
            rad2,
            length_val,
            rounding1=r1v,
            rounding2=r2v,
            chamfer1=c1v,
            chamfer2=c2v,
            chamfer_angle1=cfang1,
            chamfer_angle2=cfang2,
            from_end1=fe1,
            from_end2=fe2,
            fn=fn,
            fa=fa,
            fs=fs,
            teardrop=teardrop,
            clip_angle=clip_angle,
        )
        from pybosl2._native import native

        _opolygon = native("polygon")

        shape = _orotate_extrude(_opolygon(profile), fn=fn, fa=fa, fs=fs)

    if realign:
        sides = _frag_count(max(rad1, rad2), fn, fa, fs)
        shape = shape.rotate(180 / sides, [0, 0, 1])
    if shift[0] or shift[1]:
        shear = [
            [1, 0, shift[0] / length_val, 0],
            [0, 1, shift[1] / length_val, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ]
        shape = shape.multmatrix(shear)

    extra1_val = extra1 if extra1 is not None else extra
    extra2_val = extra2 if extra2 is not None else extra
    if extra1_val > 0:
        ext1 = _ocylinder(height=extra1_val, radius=rad1, center=False, fn=fn, fa=fa, fs=fs).translate(
            [0, 0, -length_val / 2 - extra1_val]
        )
        shape = shape | ext1
    if extra2_val > 0:
        ext2 = _ocylinder(height=extra2_val, radius=rad2, center=False, fn=fn, fa=fa, fs=fs).translate(
            [0, 0, length_val / 2]
        )
        shape = shape | ext2

    offset = _anchor_offset_cyl(rad1, rad2, length_val, use_anchor)
    return _finish3(shape, offset, spin, orient, size=None, anchor=use_anchor)


def cyl_profile(
    radius1: float,
    radius2: float,
    length: float,
    rounding1: float = 0,
    rounding2: float = 0,
    chamfer1: float = 0,
    chamfer2: float = 0,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    from_end1: bool = False,
    from_end2: bool = False,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    teardrop: float | bool = False,
    clip_angle: float = 90.0,
) -> list[list[float]]:
    """Generate a 2D cylinder profile with optional rounding and chamfering."""
    from pybosl2._helpers import arc_points as _arc_points

    eff_clip = float(clip_angle)
    if teardrop is not False and teardrop is not None:
        td_ang = teardrop if isinstance(teardrop, (int, float)) else 45.0
        eff_clip = min(eff_clip, 90.0 - td_ang)

    path = [[0.0, -length / 2]]
    if rounding1:
        sides = max(3, _frag_count(rounding1, fn, fa, fs) // 4)
        center = [radius1 - rounding1, -length / 2 + rounding1]
        pts = _arc_points(sides, rounding1, 360 - eff_clip, eff_clip, center)
        if eff_clip < 90.0:
            path.append([pts[0][0], -length / 2])
        path.extend(pts)
    elif chamfer1:
        angle1 = chamfer_angle1 if chamfer_angle1 is not None else 45.0
        if from_end1:
            dx = chamfer1 * math.cos(math.radians(angle1))
            dy = chamfer1 * math.sin(math.radians(angle1))
        else:
            dx = chamfer1
            dy = chamfer1 * math.tan(math.radians(angle1))
        path.append([radius1 - dx, -length / 2])
        path.append([radius1, -length / 2 + dy])
    else:
        path.append([radius1, -length / 2])

    if rounding2:
        sides = max(3, _frag_count(rounding2, fn, fa, fs) // 4)
        center = [radius2 - rounding2, length / 2 - rounding2]
        pts = _arc_points(sides, rounding2, 0, eff_clip, center)
        path.extend(pts)
        if eff_clip < 90.0:
            path.append([pts[-1][0], length / 2])
    elif chamfer2:
        angle2 = chamfer_angle2 if chamfer_angle2 is not None else 45.0
        if from_end2:
            dx = chamfer2 * math.cos(math.radians(angle2))
            dy = chamfer2 * math.sin(math.radians(angle2))
        else:
            dx = chamfer2
            dy = chamfer2 * math.tan(math.radians(angle2))
        path.append([radius2, length / 2 - dy])
        path.append([radius2 - dx, length / 2])
    else:
        path.append([radius2, length / 2])
    path.append([0.0, length / 2])
    return path


def xcyl(
    height: float | None = None,
    radius: float | None = None,
    center: bool | None = None,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    circumscribe: bool = False,
    realign: bool = False,
    shift: Sequence[float] = [0, 0],
    anchor: Anchor | Sequence[float] | None = None,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    # Additional missing args
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    from_end: bool = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    extra: float = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    teardrop: float | bool = False,
    clip_angle: float = 90.0,
    texture: str | TextureType | None = None,
    tex_size: float | Sequence[float] | None = None,
    tex_reps: int | Sequence[int] | None = None,
    tex_depth: float = 1.0,
    tex_inset: float | bool = False,
) -> Bosl2Solid:
    """Return a cylinder oriented along the X axis. See cyl() for argument details.

    Examples:
        .. pythonscad-example::

            from pybosl2.shapes3d.cylinder import xcyl

            shape = xcyl(radius=10, height=30)
            shape.show()

    """
    length_val = next((v for v in (length, height) if v is not None), 1.0)
    rad1 = _pick_radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
    rad2 = _pick_radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter, dflt=1)

    if circumscribe:
        sides = _frag_count(max(rad1, rad2), fn, fa, fs)
        sc = 1 / math.cos(math.pi / sides)
        rad1 *= sc
        rad2 *= sc

    use_anchor = anchor
    if use_anchor is None:
        use_anchor = CENTER if center is None or center else BOTTOM

    shape = cyl(
        length=length_val,
        radius1=rad1,
        radius2=rad2,
        chamfer=chamfer,
        chamfer1=chamfer1,
        chamfer2=chamfer2,
        rounding=rounding,
        rounding1=rounding1,
        rounding2=rounding2,
        circumscribe=circumscribe,
        realign=realign,
        shift=shift,
        anchor=CENTER,
        fn=fn,
        fa=fa,
        fs=fs,
        chamfer_angle=chamfer_angle,
        chamfer_angle1=chamfer_angle1,
        chamfer_angle2=chamfer_angle2,
        from_end=from_end,
        from_end1=from_end1,
        from_end2=from_end2,
        extra=extra,
        extra1=extra1,
        extra2=extra2,
        teardrop=teardrop,
        clip_angle=clip_angle,
        texture=texture,
        tex_size=tex_size,
        tex_reps=tex_reps,
        tex_depth=tex_depth,
        tex_inset=tex_inset,
    ).shape.rotate(90, [0, 1, 0])
    offset = _anchor_offset_cyl(rad1, rad2, length_val, use_anchor, axis=0)
    return _finish3(shape, offset, spin, orient, size=None, anchor=use_anchor)


def ycyl(
    height: float | None = None,
    radius: float | None = None,
    center: bool | None = None,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    circumscribe: bool = False,
    realign: bool = False,
    shift: Sequence[float] = [0, 0],
    anchor: Anchor | Sequence[float] | None = None,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    # Additional missing args
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    from_end: bool = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    extra: float = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    teardrop: float | bool = False,
    clip_angle: float = 90.0,
    texture: str | TextureType | None = None,
    tex_size: float | Sequence[float] | None = None,
    tex_reps: int | Sequence[int] | None = None,
    tex_depth: float = 1.0,
    tex_inset: float | bool = False,
) -> Bosl2Solid:
    """Return a cylinder oriented along the Y axis. See cyl() for argument details.

    Examples:
        .. pythonscad-example::

            from pybosl2.shapes3d.cylinder import ycyl

            shape = ycyl(radius=10, height=30)
            shape.show()

    """
    length_val = next((v for v in (length, height) if v is not None), 1.0)
    rad1 = _pick_radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
    rad2 = _pick_radius(radius1=radius2, diameter1=diameter2, radius=radius, diameter=diameter, dflt=1)

    if circumscribe:
        sides = _frag_count(max(rad1, rad2), fn, fa, fs)
        sc = 1 / math.cos(math.pi / sides)
        rad1 *= sc
        rad2 *= sc

    use_anchor = anchor
    if use_anchor is None:
        use_anchor = CENTER if center is None or center else BOTTOM

    shape = cyl(
        length=length_val,
        radius1=rad1,
        radius2=rad2,
        chamfer=chamfer,
        chamfer1=chamfer1,
        chamfer2=chamfer2,
        rounding=rounding,
        rounding1=rounding1,
        rounding2=rounding2,
        circumscribe=circumscribe,
        realign=realign,
        shift=shift,
        anchor=CENTER,
        fn=fn,
        fa=fa,
        fs=fs,
        chamfer_angle=chamfer_angle,
        chamfer_angle1=chamfer_angle1,
        chamfer_angle2=chamfer_angle2,
        from_end=from_end,
        from_end1=from_end1,
        from_end2=from_end2,
        extra=extra,
        extra1=extra1,
        extra2=extra2,
        teardrop=teardrop,
        clip_angle=clip_angle,
        texture=texture,
        tex_size=tex_size,
        tex_reps=tex_reps,
        tex_depth=tex_depth,
        tex_inset=tex_inset,
    ).shape.rotate(-90, [1, 0, 0])
    offset = _anchor_offset_cyl(rad1, rad2, length_val, use_anchor, axis=1)
    return _finish3(shape, offset, spin, orient, size=None, anchor=use_anchor)


def zcyl(
    height: float | None = None,
    radius: float | None = None,
    center: bool | None = None,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    circumscribe: bool = False,
    realign: bool = False,
    shift: Sequence[float] = [0, 0],
    anchor: Anchor | Sequence[float] | None = None,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    # Additional missing args
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    from_end: bool = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    extra: float = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    teardrop: float | bool = False,
    clip_angle: float = 90.0,
    texture: str | TextureType | None = None,
    tex_size: float | Sequence[float] | None = None,
    tex_reps: int | Sequence[int] | None = None,
    tex_depth: float = 1.0,
    tex_inset: float | bool = False,
) -> Bosl2Solid:
    """Return a cylinder oriented along the Z axis (same as cyl() with default orientation). See cyl() for.

    argument details.

    Examples:
        .. pythonscad-example::

            from pybosl2.shapes3d.cylinder import zcyl

            shape = zcyl(radius=10, height=30)
            shape.show()

    """
    return cyl(
        height=height,
        radius=radius,
        center=center,
        length=length,
        radius1=radius1,
        radius2=radius2,
        diameter=diameter,
        diameter1=diameter1,
        diameter2=diameter2,
        chamfer=chamfer,
        chamfer1=chamfer1,
        chamfer2=chamfer2,
        rounding=rounding,
        rounding1=rounding1,
        rounding2=rounding2,
        circumscribe=circumscribe,
        realign=realign,
        shift=shift,
        anchor=anchor,
        spin=spin,
        orient=orient,
        fn=fn,
        fa=fa,
        fs=fs,
        chamfer_angle=chamfer_angle,
        chamfer_angle1=chamfer_angle1,
        chamfer_angle2=chamfer_angle2,
        from_end=from_end,
        from_end1=from_end1,
        from_end2=from_end2,
        extra=extra,
        extra1=extra1,
        extra2=extra2,
        teardrop=teardrop,
        clip_angle=clip_angle,
        texture=texture,
        tex_size=tex_size,
        tex_reps=tex_reps,
        tex_depth=tex_depth,
        tex_inset=tex_inset,
    )


def tube(
    height: float | None = None,
    outer_radius: float | None = None,
    inner_radius: float | None = None,
    center: bool | None = None,
    outer_diameter: float | None = None,
    inner_diameter: float | None = None,
    wall: float | None = None,
    outer_radius1: float | None = None,
    outer_radius2: float | None = None,
    outer_diameter1: float | None = None,
    outer_diameter2: float | None = None,
    inner_radius1: float | None = None,
    inner_radius2: float | None = None,
    inner_diameter1: float | None = None,
    inner_diameter2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    realign: bool = False,
    length: float | None = None,
    anchor: Anchor | Sequence[float] = Anchor.CENTER,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """BOSL2 tube() -- a hollow cylindrical tube, with optional chamfer/rounding on end rims.

    Note: BOSL2's outer-radius parameters are named ``or``/``or1``/``or2``, which collide with the
    Python keyword ``or``; they are exposed here as ``outer_radius``/``outer_radius1``/``outer_radius2`` instead.

    Args:
        height:      height of the tube (default 1)
        length:      height of the tube (default 1)
        outer_radius:       outer radius of the tube (BOSL2 ``or``) (default 1)
        inner_radius:       inner radius of the tube
        center:             if given, overrides anchor (True -> CENTER, False -> DOWN)
        outer_diameter:     outer diameter of the tube
        inner_diameter:     inner diameter of the tube
        wall:               horizontal wall thickness (default 1)
        outer_radius1: outer radius of the bottom/top
        outer_radius2: outer radius of the bottom/top
        outer_diameter1: outer diameter of the bottom/top
        outer_diameter2: outer diameter of the bottom/top
        inner_radius1:  inner radius of the bottom/top
        inner_radius2:  inner radius of the bottom/top
        inner_diameter1:  inner diameter of the bottom/top
        inner_diameter2:  inner diameter of the bottom/top
        chamfer: chamfer size on end rims (overall/bottom/top)
        chamfer1: chamfer size on end rims (overall/bottom/top)
        chamfer2: chamfer size on end rims (overall/bottom/top)
        rounding: rounding radius on end rims (overall/bottom/top)
        rounding1: rounding radius on end rims (overall/bottom/top)
        rounding2: rounding radius on end rims (overall/bottom/top)
        realign:            rotate by half the angle of one face (default False)
        anchor:             anchor point (default CENTER)
        spin:               Z-axis rotation in degrees after anchor (default 0)
        orient:             direction to rotate the top towards, after spin (default UP)
        fn:           arc smoothness overrides
        fa:           arc smoothness overrides
        fs:           arc smoothness overrides

    Examples:
        .. pythonscad-example::

            from pybosl2 import tube

            shape = tube(height=20, outer_radius=15, inner_radius=10)
            shape.show()

        A tube with chamfered end rims:

        .. pythonscad-example::

            from pybosl2 import tube

            shape = tube(height=20, outer_radius=15, inner_radius=10, chamfer=1)
            shape.show()

    """
    height = height if height is not None else (length if length is not None else 1)
    orr1 = _pick_radius(
        radius1=outer_radius1,
        diameter1=outer_diameter1,
        radius=outer_radius,
        diameter=outer_diameter,
        dflt=None,
    )
    orr2 = _pick_radius(
        radius1=outer_radius2,
        diameter1=outer_diameter2,
        radius=outer_radius,
        diameter=outer_diameter,
        dflt=None,
    )
    irr1 = _pick_radius(
        radius1=inner_radius1,
        diameter1=inner_diameter1,
        radius=inner_radius,
        diameter=inner_diameter,
        dflt=None,
    )
    irr2 = _pick_radius(
        radius1=inner_radius2,
        diameter1=inner_diameter2,
        radius=inner_radius,
        diameter=inner_diameter,
        dflt=None,
    )
    wall_v = wall if wall is not None else 1
    rad1 = orr1 if orr1 is not None else (irr1 + wall_v if irr1 is not None else None)
    rad2 = orr2 if orr2 is not None else (irr2 + wall_v if irr2 is not None else None)
    irad1 = irr1 if irr1 is not None else (orr1 - wall_v if orr1 is not None else None)
    irad2 = irr2 if irr2 is not None else (orr2 - wall_v if orr2 is not None else None)
    assert rad1 is not None, "tube(): must specify two of inner radius/diam, outer radius/diam, and wall width."
    assert rad2 is not None, "tube(): must specify two of inner radius/diam, outer radius/diam, and wall width."
    assert irad1 is not None, "tube(): must specify two of inner radius/diam, outer radius/diam, and wall width."
    assert irad2 is not None, "tube(): must specify two of inner radius/diam, outer radius/diam, and wall width."
    assert irad1 <= rad1, "tube(): inner radius is larger than outer radius."
    assert irad2 <= rad2, "tube(): inner radius is larger than outer radius."
    use_anchor = _resolve_center_anchor(center, anchor, BOTTOM)

    # Build outer and inner cylinders via cyl() for chamfer/rounding support
    outer = cyl(
        height=height,
        radius1=rad1,
        radius2=rad2,
        center=True,
        chamfer=chamfer,
        chamfer1=chamfer1,
        chamfer2=chamfer2,
        rounding=rounding,
        rounding1=rounding1,
        rounding2=rounding2,
        fn=fn,
        fa=fa,
        fs=fs,
    )
    extra_h = max(chamfer or 0, rounding or 0, chamfer1 or 0, rounding1 or 0, chamfer2 or 0, rounding2 or 0)
    inner = cyl(
        height=height + extra_h + 0.02,
        radius1=irad1,
        radius2=irad2,
        center=True,
        fn=fn,
        fa=fa,
        fs=fs,
    )
    shape = outer.shape - inner.shape
    if realign:
        sides = _frag_count(max(rad1, rad2), fn, fa, fs)
        shape = shape.rotate(180 / sides, [0, 0, 1])
    offset = _anchor_offset_cyl(rad1, rad2, height, use_anchor)
    return _finish3(shape, offset, spin, orient, size=None, anchor=use_anchor)


def cone(
    height: float | None = None,
    radius: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    center: bool | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    chamfer: float | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    length: float | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """Return a cone/truncated cone with optional chamfering or rounding of the end rims.

    Convenience wrapper around :func:`cyl` / :func:`cylinder` with ``radius2=0`` by default
    for a pointed cone, or with explicit ``radius2`` for a truncated (frustum) form.

    Args:
        height:  height of the cone (default 1)
        length:  height of the cone (default 1)
        radius:         base radius (default 1)
        radius1:        bottom radius (overrides *radius*)
        radius2:        top radius (default 0 for a pointed cone)
        center:         if given, overrides anchor
        diameter:       base diameter
        diameter1:      bottom diameter
        diameter2:      top diameter
        chamfer: chamfer size on the end rims
        chamfer1: chamfer size on the end rims
        chamfer2: chamfer size on the end rims
        rounding: rounding radius on the end rims
        rounding1: rounding radius on the end rims
        rounding2: rounding radius on the end rims
        anchor:         anchor point
        spin:           Z-axis rotation in degrees after anchor (default 0)
        orient:         direction to rotate the top towards, after spin (default UP)
        fn:       arc smoothness overrides
        fa:       arc smoothness overrides
        fs:       arc smoothness overrides

    Examples:
        A pointed cone:

        .. pythonscad-example::

            from pybosl2 import shapes3d as s3

            s3.cone(height=30, radius=15).show()

        A truncated cone (frustum):

        .. pythonscad-example::

            from pybosl2 import shapes3d as s3

            s3.cone(height=30, radius1=15, radius2=8).show()

        A cone with chamfered base:

        .. pythonscad-example::

            from pybosl2 import shapes3d as s3

            s3.cone(height=30, radius1=15, radius2=3, chamfer=2).show()

    """
    r1 = _pick_radius(radius1=radius1, diameter1=diameter1, radius=radius, diameter=diameter, dflt=1)
    r2 = _pick_radius(radius1=radius2, diameter1=diameter2, dflt=0)
    return cyl(
        height=height,
        radius1=r1,
        radius2=r2,
        center=center,
        length=length,
        chamfer=chamfer,
        chamfer1=chamfer1,
        chamfer2=chamfer2,
        rounding=rounding,
        rounding1=rounding1,
        rounding2=rounding2,
        anchor=anchor,
        spin=spin,
        orient=orient,
        fn=fn,
        fa=fa,
        fs=fs,
    )

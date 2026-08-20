# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/shapes3d/extrusions.py
# FileSummary: Text3d, path_text, cross and extrusion-related math helpers.
# DocCategory: Foundational
# FileGroup: BOSL2

"""Text3d, path_text, cross and extrusion-related math helpers."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import numpy as np

from pybosl2._edges_lang import Anchor
from pybosl2._native import native

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pybosl2.path2d import Path2D
    from pybosl2.path3d import Path3D
    from pybosl2.shapes2d import Bosl2Shape2D
from pybosl2.constants import CENTER
from pybosl2.shapes2d import text as _text2d
from pybosl2.vectors import is_vector, unit

# Import base class and helper functions from shapes3d.base
from .base import (
    Bosl2Solid,
    _anchor_offset_box3,
    _finish3,
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


def _interior_fillet_path(radius: float, angle: float, overlap: float, sides: int) -> list[list[float]]:
    """Return the 2-D cross-section of an interior_fillet(): the wedge bounded by the corner point, the.

    two tangent points on each wall (distance radius/tan(angle/2) from the corner), and the concave arc
    of radius *radius* joining them (center at distance radius/sin(angle/2) from the corner along the
    bisector) -- the generalization to arbitrary *angle* of the classic `cube() - cylinder()`
    quarter-round fillet at angle=90. Each straight wall edge is extended *overlap* past the ideal
    corner point so the piece unions cleanly onto both adjoining faces instead of meeting them at
    an exact, potentially non-manifold, edge.
    """
    from pybosl2._helpers import arc_points as _arc_points

    half = math.radians(angle / 2)
    tlen = radius / math.tan(half) if radius > 0 else 0.0
    p0 = [tlen, 0.0]
    p1 = [tlen * math.cos(math.radians(angle)), tlen * math.sin(math.radians(angle))]
    flap0 = [-overlap, 0.0]
    flap1 = [
        -overlap * math.cos(math.radians(angle)),
        -overlap * math.sin(math.radians(angle)),
    ]
    if radius <= 0:
        return [flap0, p0, p1, flap1]

    dist = radius / math.sin(half)
    center = [dist * math.cos(half), dist * math.sin(half)]
    start_a = math.degrees(math.atan2(p0[1] - center[1], p0[0] - center[0]))
    end_a = math.degrees(math.atan2(p1[1] - center[1], p1[0] - center[0]))
    sweep = ((end_a - start_a + 180) % 360) - 180
    arc_n = max(2, round(sides * abs(sweep) / 360)) + 1
    arc = _arc_points(arc_n, radius, start_a, sweep, center)
    return [flap0] + arc + [flap1]


# ---------------------------------------------------------------------------
# Section: Text
# ---------------------------------------------------------------------------


def _text3d_anchor_vec(anchor: "Anchor | Sequence[float] | str") -> list[float]:
    """Extract a 3-vector from an `anchor` argument that may be a plain vector or (to.

    accommodate this port's unusual `anchor: str = "baseline[-1,0,-1]"` default) a string
    with a bracketed `[x,y,z]` vector embedded in it. Falls back to LEFT if no vector can
    be found in a string anchor, matching BOSL2's own `default(anchor, center?CENTER:LEFT)`.
    """
    if isinstance(anchor, str):
        i = anchor.find("[")
        j = anchor.find("]")
        if i >= 0 and j > i:
            return [float(x) for x in anchor[i + 1 : j].split(",")]
        return [-1.0, 0.0, 0.0]
    if isinstance(anchor, Anchor):
        anchor = list(anchor.vector)
    return [float(x) for x in anchor]


def _frame_map(
    x: Sequence[float] | None = None,
    y: Sequence[float] | None = None,
    z: Sequence[float] | None = None,
) -> list[list[float]]:
    """Port of BOSL2's frame_map(): builds the 4x4 change-of-basis matrix whose columns are.

    the (up to) two given unit axes plus the third axis completed via cross product, matching
    BOSL2's exact axis-completion rules (used by path_text() to orient each glyph).
    """
    xu = unit(x) if x is not None else None
    yu = unit(y) if y is not None else None
    zu = unit(z) if z is not None else None
    if xu is None:
        m = [np.cross(yu, zu), yu, zu]  # type: ignore[arg-type]
    elif yu is None:
        m = [xu, np.cross(zu, xu), zu]  # type: ignore[arg-type]
    elif zu is None:
        m = [xu, yu, np.cross(xu, yu)]
    else:
        m = [xu, yu, zu]
    return [
        [m[0][0], m[1][0], m[2][0], 0.0],  # type: ignore[index]
        [m[0][1], m[1][1], m[2][1], 0.0],  # type: ignore[index]
        [m[0][2], m[1][2], m[2][2], 0.0],  # type: ignore[index]
        [0.0, 0.0, 0.0, 1.0],
    ]


def _point3d(v: Sequence[float]) -> list[float]:
    return list(v) if len(v) >= 3 else [v[0], v[1], 0.0]


def _cut_interp(
    pathcut: list[Any], path: Sequence[Sequence[float]] | Path2D | Path3D, data: Sequence[Sequence[float]]
) -> list[list[float]]:
    """Port of BOSL2's `_cut_interp()`: linearly interpolates a per-path-vertex vector array.

    `data` to the fractional position of each `cut_points()` cut point.
    """
    out = []
    for entry in pathcut:
        idx = entry.next_index
        a = path[idx - 1]
        b = path[idx]
        c = entry.point
        i = max(range(len(b)), key=lambda k: abs(b[k] - a[k]))
        factor = (c[i] - a[i]) / (b[i] - a[i])
        out.append([(1 - factor) * da + factor * db for da, db in zip(data[idx - 1], data[idx], strict=False)])
    return out


def _path_text_bcast_dir(
    v: object, dim: int, path: Sequence[Sequence[float]] | Path2D | Path3D, label: str
) -> list[list[float]] | None:
    """Broadcasts a `normal=`/`top=` argument (undefined, a single vector, or a per-path-point.

    list of vectors) to a list of one vector per path point, mirroring BOSL2's normalok/topok
    argument checks (including the "3-vector with z==0 on a 2d path" compatibility form).
    """
    if v is None:
        return None
    if is_vector(v, dim):  # type: ignore[arg-type]
        return [list(v)] * len(path)  # type: ignore[call-overload]
    if dim == 2 and is_vector(v, 3) and abs(v[2]) < 1e-9:  # type: ignore[arg-type,index]
        return [[v[0], v[1]]] * len(path)  # type: ignore[index]
    if isinstance(v, list) and len(v) == len(path) and all(is_vector(p, dim) for p in v):
        return [list(p) for p in v]
    raise ValueError(
        f'path_text(): "{label}" must be a length-{dim} vector or a list of {len(path)} such vectors matching the path.'
    )


def text3d(
    text: str,
    height: float = 1,
    size: float = 10,
    font: str = "Liberation Sans",
    halign: str | None = None,
    valign: str | None = None,
    spacing: float = 1.0,
    direction: str = "ltr",
    language: str = "em",
    script: str = "latin",
    anchor: str = "baseline[-1,0,-1]",
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """Return 3-D extruded text, with anchor/spin/orient support.

    Args:
        text:      text to create
        height:         extrusion height (default 1)
        size:      font size divided by 0.72 (default 10)
        font:      font to use (default "Liberation Sans")
        halign:    horizontal alignment: "left", "center", "right" (overrides anchor)
        valign:    vertical alignment: "top", "center", "baseline", "bottom" (overrides anchor)
        spacing:   relative spacing multiplier between characters (default 1.0)
        direction: text direction: "ltr", "rtl", "ttb", "btt" (default "ltr")
        language:  language the text is in (default "en")
        script:    script the text is in (default "latin")
        anchor:    anchor point (default "baseline")
        spin:      Z-axis rotation in degrees (default 0)
        orient:    direction to rotate the top towards (default UP)
        fn: number of fragments for circle resolution.
        fa: minimum fragment angle for circle resolution.
        fs: minimum fragment size for circle resolution.

    Examples:
        .. pythonscad-example::

            from pybosl2 import text3d

            text3d("BOSL2", size=10, height=3).show()

    """
    av = _text3d_anchor_vec(anchor)
    ha = halign if halign is not None else ("left" if av[0] < 0 else "right" if av[0] > 0 else "center")
    va = valign if valign is not None else ("bottom" if av[1] < 0 else "top" if av[1] > 0 else "baseline")
    flat = _text2d(
        text,
        size=size,
        font=font,
        halign=ha,
        valign=va,
        spacing=spacing,
        direction=direction,
        language=language,
        script=script,
        fn=fn,
        fa=fa,
        fs=fs,
    )
    # .shape: _text2d() hands back a Bosl2Shape2D, but everything below works on raw natives
    # (_finish3) and the result is wrapped once, at the end.
    shape = flat.shape.linear_extrude(height=height, center=True, fn=fn, fa=fa, fs=fs)
    offset = _anchor_offset_box3([size, size, height], [0, 0, av[2]])
    return _finish3(shape, offset, spin, orient, size=None, anchor=av)


def path_text(
    path: Path2D | Path3D,
    text: str,
    font: str = "Liberation Sans",
    size: float = 10,
    thickness: float | None = None,
    lettersize: float | Sequence[float] | None = None,
    offset: float = 0,
    reverse: bool = False,
    normal: Sequence[float] | list[list[float]] | None = None,
    top: Sequence[float] | list[list[float]] | None = None,
    center: bool = False,
    textmetrics: bool = False,
    kern: float | Sequence[float] = 0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """Place text characters along a path.

    Args:
        path:        path to place the text on
        text:        text to create
        font:        font to use (default "Liberation Sans")
        size:        font size divided by 0.72 (default 10)
        thickness:   thickness of the letters (not allowed for a 2-D path)
        lettersize:  scalar or array giving the size of the letters
        center:      center text on the path instead of starting at the first point (default False)
        offset:      distance to shift letters "up" towards the reader (default 0, 3-D paths only)
        normal:      direction(s) pointing towards the reader of the text (3-D paths only)
        top:         direction(s) pointing towards the top of the text
        reverse:     reverse the letters if true (default False, 3-D paths only)
        textmetrics: use the experimental textmetrics feature when lettersize is not given (default False)
        kern:        scalar or array giving per-letter size adjustments (default 0)
        fn: number of fragments for circle resolution.
        fa: minimum fragment angle for circle resolution.
        fs: minimum fragment size for circle resolution.

    """
    # Imported lazily (only path_text() needs it) so that everything else in this file stays
    # free of a numpy dependency -- pybosl2.paths uses numpy internally, and numpy isn't always
    # loadable inside the real PythonSCAD app (e.g. a hardened-runtime-signed build combined
    # with an ad-hoc-signed/unsigned numpy install fails library validation).

    assert len(text) > 0, "path_text(): text must be non-empty."
    assert size > 0, "path_text(): must give positive text size."
    assert normal is None or top is None, 'path_text(): cannot define both "normal" and "top".'
    dim = len(path[0])
    assert dim in (2, 3), "path_text(): must supply a 2d or 3d path."
    if dim == 2:
        assert thickness is None, "path_text(): cannot give a thickness with a 2d path."
        assert not reverse, "path_text(): reverse not allowed with a 2d path."
        assert offset == 0, "path_text(): cannot give offset with a 2d path."
        assert normal is None, 'path_text(): cannot define "normal" for a 2d path, only "top".'

    th = 1.0 if thickness is None else thickness
    sides = len(text)

    if lettersize is not None:
        lsize = [float(lettersize)] * sides if isinstance(lettersize, (int, float)) else [float(v) for v in lettersize]
        assert len(lsize) == sides, "path_text(): lettersize list must have one entry per character."
    elif textmetrics:
        lsize = [_otextmetrics(ch, font=font, size=size)["advance"][0] for ch in text]
    else:
        raise AssertionError("path_text(): textmetrics disabled -- must specify lettersize.")

    kern_list = [float(kern)] * (sides - 1) if isinstance(kern, (int, float)) else [float(v) for v in kern]
    assert len(kern_list) == sides - 1, "path_text(): kern must be a scalar or a list of length len(text)-1."

    centers = []
    prefix = 0.0
    kern_prefix = 0.0
    for i in range(sides):
        centers.append(prefix + kern_prefix + lsize[i] / 2.0)
        prefix += lsize[i]
        if i < sides - 1:
            kern_prefix += kern_list[i]
    textlength = prefix + kern_prefix

    plen = path.perimeter()
    assert textlength <= plen, "path_text(): path is too short for the text."
    start = (plen - textlength) / 2.0 if center else 0.0
    dists = [start + c for c in centers]

    pts = path.cut_points(dists, direction=True)

    normal_pv = _path_text_bcast_dir(normal, 3, path, "normal")
    top_pv = _path_text_bcast_dir(top, dim, path, "top")

    if normal_pv is None:
        sign = 1.0 if reverse else -1.0
        normpts = [[sign * v for v in p.normal] for p in pts]  # type: ignore[union-attr]
    else:
        normpts = _cut_interp(pts, path, normal_pv)
    toppts = None if top_pv is None else _cut_interp(pts, path, top_pv)

    _usetop = top_pv is not None
    usernorm = normal_pv is not None

    letters = []
    for i, ch in enumerate(text):
        tangent = pts[i].direction
        if toppts is not None:
            tt = toppts[i]
            proj = sum(a * b for a, b in zip(tangent, tt, strict=False)) / sum(v * v for v in tt)  # type: ignore[arg-type]
            adjustment = [proj * v for v in tt]
        elif usernorm:
            nn = normpts[i]
            proj = sum(a * b for a, b in zip(tangent, nn, strict=False)) / sum(v * v for v in nn)  # type: ignore[arg-type]
            adjustment = [proj * v for v in nn]
        else:
            adjustment = [0.0] * dim
        x_axis = [tangent[k] - adjustment[k] for k in range(dim)]  # type: ignore[index]

        # .shape: the letters are composed as raw natives and wrapped once, at the end.
        glyph = (
            _text2d(ch, size=size, font=font, halign="left", valign="baseline", fn=fn, fa=fa, fs=fs)
            .translate([-lsize[i] / 2.0, 0])
            .shape
        )

        if dim == 3:
            z_axis = None if toppts is not None else normpts[i]
            y_axis = toppts[i] if toppts is not None else None
            m = _frame_map(x=x_axis, y=y_axis, z=z_axis)
            letter = glyph.linear_extrude(height=th, fn=fn, fa=fa, fs=fs).translate([0.0, 0.0, offset - th / 2.0])
        else:
            y_axis = toppts[i] if toppts is not None else [-v for v in normpts[i]]
            m = _frame_map(x=_point3d(x_axis), y=_point3d(y_axis))
            letter = glyph

        letters.append(letter.multmatrix(m).translate(pts[i].point))

    result = letters[0]
    for s in letters[1:]:
        result = result | s

    return Bosl2Solid(result, size=None, anchor=CENTER)


def _s2cross(
    size: float | Sequence[float] = (10, 10),
    arm_width: float | Sequence[float] | None = None,
) -> "Bosl2Shape2D":
    """Return the 2‑D cross polygon as a Bosl2Shape2D (internal helper for the 3‑D cross)."""
    from pybosl2.shapes2d import cross as _cross2d

    return _cross2d(size=size, arm_width=arm_width)


def cross(
    size: float | Sequence[float] = (10, 10),
    height: float | None = None,
    arm_width: float | Sequence[float] | None = None,
    length: float | None = None,
    center: bool | None = None,
    anchor: Anchor | Sequence[float] = Anchor.CENTER,
    spin: float = 0,
    orient: Anchor | Sequence[float] = Anchor.TOP,
) -> Bosl2Solid:
    """Return a 3-D cross (plus) shape: two perpendicular centred rectangular prisms.

    Builds from the 2‑D :func:`~pybosl2.shapes2d.cross` polygon linear-extruded to *height*.

    Args:
        size:      overall XY size, a scalar square or ``[width, length]``
                   (default ``[10, 10]``).
        height:    Z-axis thickness (mutually exclusive with *length*).
        arm_width: width of each arm; a scalar or ``[horizontal, vertical]`` pair.
                   When *None* (default) the arms are one-third of the overall size.
        length:    alias for *height*.
        center:    centre alignment (default True).
        anchor:    anchor point (default Anchor.CENTER).
        spin:      Z-axis rotation in degrees after anchor (default 0).
        orient:    direction to rotate the top towards, after spin (default Anchor.TOP).

    Returns:
        A :class:`Bosl2Solid`.

    Examples:
        .. pythonscad-example::

            from pybosl2 import cross

            cross(size=30, height=5).show()

    """
    h = height if height is not None else length
    assert h, "cross(): need a positive height or length."
    assert h > 0, "cross(): need a positive height or length."
    use_center = center if center is not None else True
    use_anchor = anchor
    if center is not None:
        use_anchor = Anchor.CENTER if center else Anchor.BOTTOM
    sz2d = [float(size)] * 2 if isinstance(size, (int, float)) else [float(size[0]), float(size[1])]
    sz3d = [sz2d[0], sz2d[1], float(h)]
    profile = _s2cross(size=sz2d, arm_width=arm_width)
    body = profile.linear_extrude(height=float(h), center=use_center)
    offset = _anchor_offset_box3(sz3d, use_anchor)
    return _finish3(body.shape, offset, spin, orient, size=sz3d, anchor=use_anchor)

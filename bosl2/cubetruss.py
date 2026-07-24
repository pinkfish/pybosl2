# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/cubetruss.py
#    Pure-Python port of the core of BOSL2's cubetruss.scad: modular cubical truss segments and
#    the trusses assembled from them. :meth:`CubeTruss.cubetruss_segment` builds one cube segment
#    (a hollow cube lightened with octagonal tunnels through all three axes, optionally cross-braced);
#    :meth:`CubeTruss.cubetruss` tiles a grid of them; :meth:`CubeTruss.cubetruss_corner` builds an
#    L/T corner truss; :meth:`CubeTruss.cubetruss_support` builds a diagonal support brace;
#    :meth:`CubeTruss.cubetruss_dist` gives a truss's length. Sizes default to the BOSL2 conventions
#    (30 mm cube, 3 mm struts, braced).
#
#    The clip accessories are ported too: :meth:`CubeTruss.cubetruss_clip`,
#    :meth:`~CubeTruss.cubetruss_foot`, :meth:`~CubeTruss.cubetruss_joiner` and
#    :meth:`~CubeTruss.cubetruss_uclip`, and the ``clips=`` option on :meth:`cubetruss` (for the
#    FRONT/BACK/LEFT/RIGHT faces).
#
# FileSummary: Modular cubical truss segments and trusses.
# FileGroup: BOSL2

from __future__ import annotations

import math

from collections.abc import Sequence

from bosl2._helpers import union
from bosl2.constants import CENTER, BOTTOM
from bosl2.distributors import xcopies, ycopies, zcopies, xflip_copy, mirror_copy
from bosl2.masking import chamfer_edge_mask
from bosl2.shapes3d import Bosl2Solid, cuboid, prismoid, regular_prism

__all__ = ["CubeTruss"]

# BOSL2 defaults ($cubetruss_size / $cubetruss_strut_size / $cubetruss_bracing / clip thickness).
CUBETRUSS_SIZE = 30.0
CUBETRUSS_STRUT_SIZE = 3.0
CUBETRUSS_BRACING = True
CUBETRUSS_CLIP_THICKNESS = 1.6


def _union(shapes):
    return union(shapes)


def _cmask(l, chamfer, orient=None):
    """chamfer_edge_mask as a Bosl2Solid, optionally re-oriented (RIGHT -> X axis, BACK -> Y axis)."""
    m = Bosl2Solid(chamfer_edge_mask(length=l, chamfer=chamfer))
    if orient == "RIGHT":
        return m.rotate([0, 90, 0])
    if orient == "BACK":
        return m.rotate([90, 0, 0])
    return m


def _yflip_copy(offset):
    return mirror_copy(v=[0, 1, 0], offset=offset)


def _clip_placement(vec, extents):
    """For a face direction *vec*, return (z-rotation, rotated [X,Y,Z] extents) placing a clip
    (BOSL2 rot(from=FWD, to=vec)). Supports the four horizontal cardinal faces."""
    x, y = float(vec[0]), float(vec[1])
    w, l, hh = extents
    if y < 0:  # FRONT (-Y): FWD itself
        return 0, (w, l, hh)
    if y > 0:  # BACK (+Y)
        return 180, (w, l, hh)
    if x > 0:  # RIGHT (+X)
        return 90, (l, w, hh)
    if x < 0:  # LEFT (-X)
        return -90, (l, w, hh)
    raise ValueError(
        f"cubetruss(clips=): unsupported clip direction {vec!r} (use FRONT/BACK/LEFT/RIGHT)"
    )


def _octagon_tunnel(size, strut, h):
    """A long octagonal-prism cutter for the axial lightening tunnels (BOSL2 cylinder($fn=8))."""
    oct_d = (min(h, size) - 2 * strut) / math.cos(math.radians(180 / 8))
    return regular_prism(
        8, diameter=oct_d, height=max(h, size) + 1, anchor=CENTER
    ).rotate([0, 0, 180 / 8])


class CubeTruss:
    """Modular cubical trusses (BOSL2 cubetruss.scad)."""

    @staticmethod
    def cubetruss_dist(
        cubes: int = 0,
        gaps: int = 0,
        size: float | None = None,
        strut: float | None = None,
    ) -> float:
        """The length of a truss *cubes* long, plus *gaps* extra strut-widths (BOSL2 cubetruss_dist())."""
        size = CUBETRUSS_SIZE if size is None else size
        strut = CUBETRUSS_STRUT_SIZE if strut is None else strut
        return cubes * (size - strut) + gaps * strut

    @staticmethod
    def cubetruss_segment(
        size: float | None = None,
        strut: float | None = None,
        bracing: bool | None = None,
    ) -> Bosl2Solid:
        """A single cubetruss cube segment (BOSL2 cubetruss_segment()).

        Examples:
            A braced segment:

            .. pythonscad-example::

                from bosl2.cubetruss import CubeTruss
                CubeTruss.cubetruss_segment().show()
        """
        size = CUBETRUSS_SIZE if size is None else size
        strut = CUBETRUSS_STRUT_SIZE if strut is None else strut
        bracing = CUBETRUSS_BRACING if bracing is None else bracing
        height = size
        crossthick = strut / math.sqrt(2)
        voffset = 0.333

        body = cuboid([size, size, height]) - cuboid(
            [size - 2 * strut, size - 2 * strut, height - 2 * strut]
        )
        # Octagonal tunnels through the X, Y and Z axes.
        body = body - _octagon_tunnel(size, strut, height).rotate([90, 0, 0])  # along Y
        body = body - _octagon_tunnel(size, strut, height).rotate([90, 0, 0]).rotate(
            [0, 0, 90]
        )  # along X
        body = body - _octagon_tunnel(size, strut, height)  # along Z

        if bracing:
            hex_d = (min(height, size) - 2 * strut) / math.cos(
                math.radians(180 / 6)
            ) - 2 * voffset
            for i in (-1, 1):
                brace = cuboid([crossthick, (size - strut) * math.sqrt(2), height])
                hole = (
                    regular_prism(
                        6, diameter=hex_d, height=crossthick + 1, anchor=CENTER
                    )
                    .rotate([0, 0, 180 / 6])
                    .rotate([0, 90, 0])
                    .scale([1, 1.3, 1])
                    .up(i * voffset)
                )
                body = body | (brace - hole).rotate([0, 0, i * 45])
        return Bosl2Solid(body.shape, size=[size, size, size])

    @staticmethod
    def cubetruss(
        extents: int | Sequence[int] = 6,
        clips: Sequence | None = None,
        bracing: bool | None = None,
        size: float | None = None,
        strut: float | None = None,
        clipthick: float | None = None,
        slop: float = 0.0,
    ) -> Bosl2Solid:
        """A truss assembled from a grid of cube segments (BOSL2 cubetruss()).

        *extents* is the number of cubes long, or an ``[X, Y, Z]`` count. *clips* adds end clips on
        the named faces -- each a direction vector ``FRONT``/``BACK``/``LEFT``/``RIGHT`` (or a list
        of them).

        Examples:
            A 3-long truss with a front clip:

            .. pythonscad-example::

                from bosl2.cubetruss import CubeTruss
                from bosl2.constants import FRONT
                CubeTruss.cubetruss(extents=3, clips=FRONT).show()
        """
        size = CUBETRUSS_SIZE if size is None else size
        strut = CUBETRUSS_STRUT_SIZE if strut is None else strut
        clipthick = CUBETRUSS_CLIP_THICKNESS if clipthick is None else clipthick
        if isinstance(extents, (int, float)):
            w, l, hh = 1, int(extents), 1
        else:
            e = list(extents) + [1] * (3 - len(extents))
            w, l, hh = int(e[0]), int(e[1]), int(e[2])

        step = size - strut
        segs = []
        for zrow in range(hh):
            for xcol in range(w):
                for ycol in range(l):
                    seg = CubeTruss.cubetruss_segment(
                        size=size, strut=strut, bracing=bracing
                    )
                    seg = (
                        seg.up((zrow - (hh - 1) / 2) * step)
                        .right((xcol - (w - 1) / 2) * step)
                        .back((ycol - (l - 1) / 2) * step)
                    )
                    segs.append(seg)

        if clips is not None and clipthick > 0:
            vecs = clips if (clips and isinstance(clips[0], (list, tuple))) else [clips]
            for vec in vecs:
                zang, (exx, exy, exz) = _clip_placement(vec, (w, l, hh))
                for zrow in range(exz):
                    clip = CubeTruss.cubetruss_clip(
                        extents=exx,
                        size=size,
                        strut=strut,
                        clipthick=clipthick,
                        slop=slop,
                    )
                    segs.append(
                        clip.forward((exy * step + strut) / 2)
                        .up((zrow - (exz - 1) / 2) * step)
                        .rotate([0, 0, zang])
                    )

        result = _union(segs)
        s = [
            CubeTruss.cubetruss_dist(w, 1, size, strut),
            CubeTruss.cubetruss_dist(l, 1, size, strut),
            CubeTruss.cubetruss_dist(hh, 1, size, strut),
        ]
        return Bosl2Solid(result.shape, size=s)

    @staticmethod
    def cubetruss_support(
        extents: int | Sequence[int] = 1,
        size: float | None = None,
        strut: float | None = None,
    ) -> Bosl2Solid:
        """A diagonal support truss -- a block cut on the diagonal and lightened (BOSL2 cubetruss_support()).

        *extents* is the vertical segment count, or an ``[X, Y, Z]`` count.

        Examples:
            A 2-high support:

            .. pythonscad-example::

                from bosl2.cubetruss import CubeTruss
                CubeTruss.cubetruss_support(extents=2).show()
        """
        size = CUBETRUSS_SIZE if size is None else size
        strut = CUBETRUSS_STRUT_SIZE if strut is None else strut
        if isinstance(extents, (int, float)):
            ex, ey, ez = 1, 1, int(extents)
        else:
            e = [int(x) for x in (list(extents) + [1, 1, 1])[:3]]
            ex, ey, ez = e
        step = size - strut
        w, l, height = step * ex + strut, step * ey + strut, step * ez + strut
        v = [0.0, 1.0 / ey, 1.0 / ez]  # BACK/ey + UP/ez diagonal cut normal
        smax = size * (max(ex, ey, ez) + 1)
        octid = size - 2 * strut

        def octprism(length, rot):
            # cyl(diameter=octid, circum=true, realign=true, $fn=8): an octagon across-flats octid, +half facet.
            p = regular_prism(
                8, inner_diameter=octid, height=length, anchor=CENTER
            ).rotate([0, 0, 180 / 8])
            return p.rotate(rot) if rot else p

        def hollow_cell():
            return (
                octprism(size + 1, [0, 90, 0])  # X-axis tunnel
                | octprism(size + 1, None)  # Z-axis tunnel
                | cuboid([octid, octid, octid])
            )  # central cube

        pieces = []
        for mx in xcopies(step, sides=ex):
            base = cuboid([size, l, height]).half_of(v=v, s=smax)
            cells = [
                hollow_cell().multmatrix((my @ mz).tolist())
                for my in ycopies(step, sides=ey)
                for mz in zcopies(step, sides=ez)
            ]
            holes = _union(cells).half_of(v=v, center=strut, s=smax)
            ytun = _union(
                [
                    octprism(ey * size + 1, [90, 0, 0]).multmatrix(mz.tolist())
                    for mz in zcopies(step, sides=ez)
                ]
            )
            pieces.append((base - holes - ytun).multmatrix(mx.tolist()))
        return Bosl2Solid(_union(pieces).shape, size=[w, l, height])

    @staticmethod
    def cubetruss_corner(
        height: int = 1,
        extents: int | Sequence[int] = 1,
        bracing: bool | None = None,
        size: float | None = None,
        strut: float | None = None,
    ) -> Bosl2Solid:
        """A corner truss with arms jutting out in one or more directions (BOSL2 cubetruss_corner()).

        *height* is the central column height in cubes. *extents* is a scalar (equal arms in +X, +Y and
        +Z) or a length-<=5 vector giving the arm lengths in the +X, +Y, -X, -Y and +Z directions.
        End clips are not added (the clip accessory is not ported).

        Examples:
            An L-corner:

            .. pythonscad-example::

                from bosl2.cubetruss import CubeTruss
                CubeTruss.cubetruss_corner(extents=2).show()
        """
        size = CUBETRUSS_SIZE if size is None else size
        strut = CUBETRUSS_STRUT_SIZE if strut is None else strut
        height = int(height)
        if isinstance(extents, (int, float)):
            exts = [int(extents), int(extents), 0, 0, int(extents)]
        else:
            exts = [int(x) for x in (list(extents) + [0] * 5)[:5]]
        step = size - strut

        def seg():
            return CubeTruss.cubetruss_segment(size=size, strut=strut, bracing=bracing)

        segs = [seg().up(step * zcol) for zcol in range(height)]  # central column
        for d in range(4):  # +X, +Y, -X, -Y arms
            for zcol in range(height):
                for i in range(1, exts[d] + 1):
                    segs.append(
                        seg()
                        .right((step + 0.01) * i)
                        .up((step + 0.01) * zcol)
                        .rotate([0, 0, d * 90])
                    )
        for i in range(1, exts[4] + 1):  # +Z arm
            segs.append(seg().up((step + 0.01) * (i + height - 1)))

        result = _union(segs)
        s = [
            CubeTruss.cubetruss_dist(exts[0] + 1 + exts[2], 1, size, strut),
            CubeTruss.cubetruss_dist(exts[1] + 1 + exts[3], 1, size, strut),
            CubeTruss.cubetruss_dist(height + exts[4], 1, size, strut),
        ]
        return Bosl2Solid(result.shape, size=s)

    # ---- clip accessories ------------------------------------------------

    @staticmethod
    def cubetruss_clip(
        extents: int = 1,
        size: float | None = None,
        strut: float | None = None,
        clipthick: float | None = None,
        slop: float = 0.0,
    ) -> Bosl2Solid:
        """A pair of snap clips for the end of a truss (BOSL2 cubetruss_clip())."""
        size = CUBETRUSS_SIZE if size is None else size
        strut = CUBETRUSS_STRUT_SIZE if strut is None else strut
        clipthick = CUBETRUSS_CLIP_THICKNESS if clipthick is None else clipthick
        cliplen = strut * 2.6
        clipheight = min(size + strut, size / 3 + 2 * strut * 2.6)
        clipsize = 0.5

        def one_clip():
            hook = prismoid(
                [clipthick, clipheight],
                [clipthick, clipheight - cliplen * 2],
                height=cliplen,
            ).rotate([90, 0, 0])
            hook = hook - _cmask(clipheight + 0.1, clipthick).right(clipthick / 2)
            hook = hook.back(strut).right(clipthick / 2 - 0.01)
            if slop > 0:
                hook = hook - cuboid([slop, strut * 3, size]).forward(strut * 3 / 2)
            lip = (
                prismoid(
                    [clipheight - cliplen * 2, strut / 2],
                    [clipheight - cliplen * 2 - 2 * clipsize, strut / 2],
                    height=clipsize + 0.01,
                )
                .rotate([0, -90, 0])
                .forward(strut * 1.25 + slop)
                .right(slop / 2 + 0.01)
            )
            clip = hook | lip
            clip = clip - _cmask(size + 1, clipsize + clipthick / 3).scale(
                [1, 1.5, 1]
            ).left(clipsize).forward(strut * 1.6)
            for mz in zcopies(clipheight - strut, sides=2):
                clip = clip - cuboid([clipthick * 3, cliplen * 2, strut]).multmatrix(
                    mz.tolist()
                )
            for mz in zcopies(clipheight - 2 * strut, sides=2):
                clip = clip - _cmask(cliplen * 2, clipthick, orient="BACK").right(
                    clipthick
                ).multmatrix(mz.tolist())
            return clip

        pair = _union(
            [
                one_clip().multmatrix(m.tolist())
                for m in xflip_copy(offset=(extents * (size - strut) + strut) / 2)
            ]
        )
        s = [
            extents * (size - strut) + strut + 2 * clipthick,
            strut * 2,
            clipheight - 2 * strut,
        ]
        return Bosl2Solid(pair.shape, size=s)

    @staticmethod
    def cubetruss_foot(
        w: int = 1,
        size: float | None = None,
        strut: float | None = None,
        clipthick: float | None = None,
        slop: float = 0.0,
    ) -> Bosl2Solid:
        """A foot that clips onto the bottom of a truss for support (BOSL2 cubetruss_foot())."""
        size = CUBETRUSS_SIZE if size is None else size
        strut = CUBETRUSS_STRUT_SIZE if strut is None else strut
        clipthick = CUBETRUSS_CLIP_THICKNESS if clipthick is None else clipthick
        clipsize = 0.5
        wall_h = strut + clipthick * 1.5
        cyld = (size - 2 * strut) / math.cos(math.radians(180 / 8))
        span = w * (size - strut) + strut
        parts = []
        base = cuboid(
            [span + 2 * clipthick, size - 2 * strut, clipthick],
            chamfer=strut,
            edges="Z",
        ).up(clipthick / 2)
        parts.append(base)
        for mx in xcopies(span + clipthick, sides=2):
            parts.append(
                prismoid(
                    [clipthick, size - 4 * strut],
                    [clipthick, size / 3.5],
                    height=wall_h,
                    anchor=BOTTOM,
                )
                .up(clipthick - 0.01)
                .multmatrix(mx.tolist())
            )
        for mx in xcopies(span, sides=2):
            parts.append(
                prismoid(
                    [clipsize * 2, size / 3.5],
                    [0.1, size / 3.5],
                    height=clipsize * 3,
                    anchor=BOTTOM,
                )
                .up(clipthick + strut + slop * 2)
                .multmatrix(mx.tolist())
            )
        for xcol in range(w):
            plug = (
                regular_prism(
                    8,
                    radius1=(cyld - 4 * slop) / 2,
                    radius2=(cyld - 4 * slop - 1) / 2,
                    height=strut,
                    anchor=BOTTOM,
                )
                .rotate([0, 0, 180 / 8])
                .up(clipthick - 0.01)
            )
            for my in ycopies(size - 2 * strut - 4 * slop, sides=2):
                plug = plug - _cmask(size - strut, strut * 2 / 3, orient="RIGHT").up(
                    clipthick + strut
                ).multmatrix(my.tolist())
            for mz in [-45, 45]:
                plug = plug - cuboid(
                    [size * 3, strut / math.sqrt(2) + 2 * slop, size * 3]
                ).rotate([0, 0, mz])
            parts.append(plug.right((xcol - (w - 1) / 2) * (size - strut)))
        result = _union(parts).down(clipthick)
        s = [span + 2 * clipthick, size - 2 * strut, strut + clipthick]
        return Bosl2Solid(result.shape, size=s)

    @staticmethod
    def cubetruss_uclip(
        dual: bool = True,
        size: float | None = None,
        strut: float | None = None,
        clipthick: float | None = None,
        slop: float = 0.0,
    ) -> Bosl2Solid:
        """A U-shaped clip that joins two trusses face to face (BOSL2 cubetruss_uclip())."""
        size = CUBETRUSS_SIZE if size is None else size
        strut = CUBETRUSS_STRUT_SIZE if strut is None else strut
        clipthick = CUBETRUSS_CLIP_THICKNESS if clipthick is None else clipthick
        clipsize = 0.5
        nd = 2 if dual else 1
        s = [nd * strut + 2 * clipthick + slop, strut + 2 * clipthick, size / 3.5]
        body = cuboid(s) - cuboid(
            [nd * strut + slop, strut + 2 * clipthick, size + 1]
        ).back(clipthick)
        prism = (
            prismoid(
                [size / 3.5, clipthick * 1.87],
                [size / 3.5, 0.1],
                height=clipsize,
                anchor=BOTTOM,
            )
            .back_half()
            .rotate([0, -90, 0])
        )
        clips = _union(
            [
                prism.multmatrix(m.tolist())
                for m in xflip_copy(offset=(1 if dual else 0.5) * strut + slop / 2)
            ]
        ).back((strut + slop) / 2)
        return Bosl2Solid((body | clips).shape, size=s)

    @staticmethod
    def cubetruss_joiner(
        w: int = 1,
        vert: bool = True,
        size: float | None = None,
        strut: float | None = None,
        clipthick: float | None = None,
        slop: float = 0.0,
    ) -> Bosl2Solid:
        """A joiner that clips two trusses end to end (BOSL2 cubetruss_joiner())."""
        size = CUBETRUSS_SIZE if size is None else size
        strut = CUBETRUSS_STRUT_SIZE if strut is None else strut
        clipthick = CUBETRUSS_CLIP_THICKNESS if clipthick is None else clipthick
        clipsize = 0.5
        span = w * (size - strut) + strut
        parts = [cuboid([span + 2 * clipthick, size, clipthick]).up(clipthick / 2)]
        for mx in xcopies(span + clipthick, sides=2):
            parts.append(
                cuboid([clipthick, size, clipthick + strut * 3 / 4])
                .up((clipthick + strut * 3 / 4) / 2)
                .multmatrix(mx.tolist())
            )
        for my in ycopies(size, sides=2):
            parts.append(
                CubeTruss.cubetruss_foot(
                    w=w, size=size, strut=strut, clipthick=clipthick, slop=slop
                )
                .up((strut + clipthick) / 2)
                .multmatrix(my.tolist())
            )
        if vert:
            for mx in xcopies(span + clipthick, sides=2):
                parts.append(
                    prismoid(
                        [clipthick, size],
                        [clipthick, 2 * strut + 2 * clipthick],
                        height=size * 0.6,
                        anchor=BOTTOM,
                    )
                    .up(clipthick - 0.01)
                    .multmatrix(mx.tolist())
                )
            wallclip = (
                prismoid(
                    [size / 3.5, clipthick * 2],
                    [size / 3.5 - 4 * 2 * clipsize, 0.1],
                    height=2 * clipsize,
                    anchor=BOTTOM,
                )
                .back_half()
                .rotate([0, -90, 0])
            )
            for mx in xflip_copy(offset=(span + 0.02) / 2):
                for my in _yflip_copy(offset=strut + slop / 2):
                    parts.append(wallclip.multmatrix((mx @ my).tolist()).up(size / 2))
        result = _union(parts).down(clipthick)
        s = [span + 2 * clipthick, 2 * (size - strut) + strut, strut + clipthick]
        return Bosl2Solid(result.shape, size=s)

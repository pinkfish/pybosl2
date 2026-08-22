# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/parts/cubetruss.py
#    Pure-Python port of the core of BOSL2's cubetruss.scad: modular cubical truss segments and
#    the trusses assembled from them. :class:`TrussSegment` builds one cube segment
#    (a hollow cube lightened with octagonal tunnels through all three axes, optionally cross-braced);
#    :class:`Truss` tiles a grid of them; :class:`TrussCorner` builds an
#    L/T corner truss; :class:`TrussSupport` builds a diagonal support brace;
#    :func:`truss_dist` gives a truss's length. Sizes default to the BOSL2 conventions
#    (30 mm cube, 3 mm struts, braced).
#
#    The clip accessories are ported too: :class:`TrussClip`,
#    :class:`TrussFoot`, :class:`TrussJoiner` and
#    :class:`TrussUClip`, and the ``clips=`` option on :class:`Truss` (for the
#    FRONT/BACK/LEFT/RIGHT faces).
#
# FileSummary: Modular cubical truss segments and trusses.
# DocCategory: Parts library
# FileGroup: BOSL2

"""Modular cubical truss segments and trusses."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from pybosl2._backend import csg_part
from pybosl2._edges_lang import Anchor
from pybosl2._helpers import union
from pybosl2.constants import BOTTOM, CENTER
from pybosl2.distributors import DistributableMatrix
from pybosl2.masking import chamfer_edge_mask
from pybosl2.shapes3d import Bosl2Solid, cuboid, prismoid, regular_prism

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "TrussSegment",
    "Truss",
    "TrussCorner",
    "TrussSupport",
    "TrussClip",
    "TrussFoot",
    "TrussUClip",
    "TrussJoiner",
    "truss_dist",
]

# BOSL2 defaults ($cubetruss_size / $cubetruss_strut_size / $cubetruss_bracing / clip thickness).
CUBETRUSS_SIZE = 30.0
CUBETRUSS_STRUT_SIZE = 3.0
CUBETRUSS_BRACING = True
CUBETRUSS_CLIP_THICKNESS = 1.6


_union = union


def _cmask(length: float, chamfer: float, orient: str | None = None) -> Bosl2Solid:
    """chamfer_edge_mask, optionally re-oriented (RIGHT -> X axis, BACK -> Y axis)."""
    m = chamfer_edge_mask(length=length, chamfer=chamfer)
    if orient == "RIGHT":
        return m.rotate([0, 90, 0])
    if orient == "BACK":
        return m.rotate([90, 0, 0])
    return m


def _yflip_copy(offset: float) -> Any:
    return DistributableMatrix.mirror_copy(v=[0, 1, 0], offset=offset)


def _clip_placement(vec: Sequence[float], extents: Sequence[float]) -> tuple[int, tuple[float, float, float]]:
    """For a face direction *vec*, return (z-rotation, rotated [X,Y,Z] extents) placing a clip.

    (BOSL2 rot(from=FWD, to=vec)). Supports the four horizontal cardinal faces.
    """
    x, y = float(vec[0]), float(vec[1])
    w, length, hh = extents
    if y < 0:  # FRONT (-Y): FWD itself
        return 0, (w, length, hh)
    if y > 0:  # BACK (+Y)
        return 180, (w, length, hh)
    if x > 0:  # RIGHT (+X)
        return 90, (length, w, hh)
    if x < 0:  # LEFT (-X)
        return -90, (length, w, hh)
    raise ValueError(f"cubetruss(clips=): unsupported clip direction {vec!r} (use FRONT/BACK/LEFT/RIGHT)")


def _octagon_tunnel(
    size: float, strut: float, h: float, fn: int | None = None, fa: float | None = None, fs: float | None = None
) -> Bosl2Solid:
    """Return a long octagonal-prism cutter for the axial lightening tunnels (BOSL2 cylinder($fn=8))."""
    oct_d = (min(h, size) - 2 * strut) / math.cos(math.radians(180 / 8))
    return regular_prism(8, diameter=oct_d, height=max(h, size) + 1, anchor=CENTER, fn=fn, fa=fa, fs=fs).rotate(
        [0, 0, 180 / 8]
    )


def truss_dist(
    cubes: int = 0,
    gaps: int = 0,
    size: float | None = None,
    strut: float | None = None,
) -> float:
    """Return the length of a truss *cubes* long, plus *gaps* extra strut-widths.

    Args:
        cubes: Number of cubes along the truss.
        gaps: Number of extra strut-width gaps.
        size: Cube size in mm. Defaults to CUBETRUSS_SIZE (30 mm).
        strut: Strut thickness in mm. Defaults to CUBETRUSS_STRUT_SIZE (3 mm).

    Returns:
        The total length of the truss in mm.

    """
    sz = CUBETRUSS_SIZE if size is None else size
    st = CUBETRUSS_STRUT_SIZE if strut is None else strut
    return cubes * (sz - st) + gaps * st


# ---------------------------------------------------------------------------
# Section: truss classes
# ---------------------------------------------------------------------------


class TrussSegment:
    """A single cubetruss cube segment — a hollow cube lightened with octagonal tunnels.

    Examples:
        A braced segment:

        .. pythonscad-example::

            from pybosl2.parts.cubetruss import TrussSegment
            TrussSegment().show()

    """

    def __init__(
        self,
        size: float | None = None,
        strut: float | None = None,
        bracing: bool | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a cube truss segment.

        Args:
            size: Cube size in mm. Defaults to CUBETRUSS_SIZE (30 mm).
            strut: Strut thickness in mm. Defaults to CUBETRUSS_STRUT_SIZE (3 mm).
            bracing: If True, add cross bracing inside the cube. Defaults to CUBETRUSS_BRACING.
            fn: Number of fragments for rounded geometry.
            fa: Fragment angle for rounded geometry.
            fs: Fragment size for rounded geometry.

        Returns:
            None.

        """
        sz = CUBETRUSS_SIZE if size is None else size
        st = CUBETRUSS_STRUT_SIZE if strut is None else strut
        br = CUBETRUSS_BRACING if bracing is None else bracing
        height = sz
        crossthick = st / math.sqrt(2)
        voffset = 0.333

        body = cuboid([sz, sz, height], fn=fn, fa=fa, fs=fs) - cuboid(
            [sz - 2 * st, sz - 2 * st, height - 2 * st], fn=fn, fa=fa, fs=fs
        )
        body = body - _octagon_tunnel(sz, st, height, fn=fn, fa=fa, fs=fs).rotate([90, 0, 0])
        body = body - _octagon_tunnel(sz, st, height, fn=fn, fa=fa, fs=fs).rotate([90, 0, 0]).rotate([0, 0, 90])
        body = body - _octagon_tunnel(sz, st, height, fn=fn, fa=fa, fs=fs)

        if br:
            hex_d = (min(height, sz) - 2 * st) / math.cos(math.radians(180 / 6)) - 2 * voffset
            for i in (-1, 1):
                brace = cuboid([crossthick, (sz - st) * math.sqrt(2), height], fn=fn, fa=fa, fs=fs)
                hole = (
                    regular_prism(6, diameter=hex_d, height=crossthick + 1, anchor=CENTER, fn=fn, fa=fa, fs=fs)
                    .rotate([0, 0, 180 / 6])
                    .rotate([0, 90, 0])
                    .scale([1, 1.3, 1])
                    .up(i * voffset)
                )
                body = body | (brace - hole).rotate([0, 0, i * 45])
        self._solid: Bosl2Solid = Bosl2Solid(body.shape, size=[sz, sz, sz])
        self._size: float = sz
        self._strut: float = st

    @property
    def size(self) -> float:
        """Cube size in mm."""
        return self._size

    @property
    def strut(self) -> float:
        """Strut thickness in mm."""
        return self._strut

    @property
    @csg_part("chamfers with chamfer_edge_mask(), a 2-D profile extruded along each edge")
    def shape(self) -> Bosl2Solid:
        """Return the segment geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the segment in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()


class Truss:
    """A truss assembled from a grid of cube segments.

    *extents* is the number of cubes long, or an ``[X, Y, Z]`` count.  *clips*
    adds end clips on the named faces — each a direction vector ``FRONT`` /
    ``BACK`` / ``LEFT`` / ``RIGHT`` (or a list of them).

    Examples:
        A 3-long truss with a front clip:

        .. pythonscad-example::

            from pybosl2.parts.cubetruss import Truss
            from pybosl2.constants import FRONT
            Truss(extents=3, clips=FRONT).show()

    """

    def __init__(
        self,
        extents: int | Sequence[int] = 6,
        clips: Sequence[Sequence[float]] | Sequence[float] | None = None,
        bracing: bool | None = None,
        size: float | None = None,
        strut: float | None = None,
        clipthick: float | None = None,
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a truss from a grid of segments.

        Args:
            extents: Number of cubes long, or an [X, Y, Z] count. Defaults to 6.
            clips: Direction vector(s) for end clips on the named faces.
            bracing: If True, add cross bracing inside each cube.
            size: Cube size in mm. Defaults to CUBETRUSS_SIZE (30 mm).
            strut: Strut thickness in mm. Defaults to CUBETRUSS_STRUT_SIZE (3 mm).
            clipthick: Clip thickness in mm. Defaults to CUBETRUSS_CLIP_THICKNESS (1.6 mm).
            slop: Extra clearance for clips.
            fn: Number of fragments for rounded geometry.
            fa: Fragment angle for rounded geometry.
            fs: Fragment size for rounded geometry.

        Returns:
            None.

        """
        sz = CUBETRUSS_SIZE if size is None else size
        st = CUBETRUSS_STRUT_SIZE if strut is None else strut
        ct = CUBETRUSS_CLIP_THICKNESS if clipthick is None else clipthick
        if isinstance(extents, (int, float)):
            w, length, hh = 1, int(extents), 1
        else:
            e = list(extents) + [1] * (3 - len(extents))
            w, length, hh = int(e[0]), int(e[1]), int(e[2])

        step = sz - st
        segs: list[Bosl2Solid] = []
        for zrow in range(hh):
            for xcol in range(w):
                for ycol in range(length):
                    seg = TrussSegment(size=sz, strut=st, bracing=bracing, fn=fn, fa=fa, fs=fs).shape
                    seg = (
                        seg.up((zrow - (hh - 1) / 2) * step)
                        .right((xcol - (w - 1) / 2) * step)
                        .back((ycol - (length - 1) / 2) * step)
                    )
                    segs.append(seg)

        if clips is not None and ct > 0:
            raw: Any = clips
            vecs: list[Sequence[float]] = [list(v) for v in raw] if isinstance(raw[0], (list, tuple)) else [list(raw)]
            for vec in vecs:
                zang, (exx, exy, exz) = _clip_placement(vec, (w, length, hh))
                for zrow in range(int(exz)):
                    clip = TrussClip(
                        extents=int(exx),
                        size=sz,
                        strut=st,
                        clipthick=ct,
                        slop=slop,
                        fn=fn,
                        fa=fa,
                        fs=fs,
                    ).shape
                    segs.append(
                        clip.forward((exy * step + st) / 2).up((zrow - (exz - 1) / 2) * step).rotate([0, 0, zang])
                    )

        result = _union(segs)
        s = [
            truss_dist(w, 1, sz, st),
            truss_dist(length, 1, sz, st),
            truss_dist(hh, 1, sz, st),
        ]
        self._solid: Bosl2Solid = Bosl2Solid(result.shape, size=s)
        self._extents: int | tuple[int, ...] = extents if isinstance(extents, int) else tuple(extents)

    @property
    def extents(self) -> int | tuple[int, ...]:
        """Grid dimensions."""
        return self._extents

    @property
    @csg_part("chamfers with chamfer_edge_mask(), a 2-D profile extruded along each edge")
    def shape(self) -> Bosl2Solid:
        """Return the truss geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the truss in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()


class TrussSupport:
    """A diagonal support truss — a block cut on the diagonal and lightened.

    *extents* is the vertical segment count, or an ``[X, Y, Z]`` count.

    Examples:
        A 2-high support:

        .. pythonscad-example::

            from pybosl2.parts.cubetruss import TrussSupport
            TrussSupport(extents=2).show()

    """

    def __init__(
        self,
        extents: int | Sequence[int] = 1,
        size: float | None = None,
        strut: float | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a diagonal support truss.

        Args:
            extents: Vertical segment count, or an [X, Y, Z] count. Defaults to 1.
            size: Cube size in mm. Defaults to CUBETRUSS_SIZE (30 mm).
            strut: Strut thickness in mm. Defaults to CUBETRUSS_STRUT_SIZE (3 mm).
            fn: Number of fragments for rounded geometry.
            fa: Fragment angle for rounded geometry.
            fs: Fragment size for rounded geometry.

        Returns:
            None.

        """
        sz = CUBETRUSS_SIZE if size is None else size
        st = CUBETRUSS_STRUT_SIZE if strut is None else strut
        if isinstance(extents, (int, float)):
            ex, ey, ez = 1, 1, int(extents)
        else:
            e = [int(x) for x in (list(extents) + [1, 1, 1])[:3]]
            ex, ey, ez = e
        step = sz - st
        w, length, height = step * ex + st, step * ey + st, step * ez + st
        v = [0.0, 1.0 / ey, 1.0 / ez]
        smax = sz * (max(ex, ey, ez) + 1)
        octid = sz - 2 * st

        def octprism(length_: float, rot: list[float] | None) -> Bosl2Solid:
            p = regular_prism(8, inner_diameter=octid, height=length_, anchor=CENTER, fn=fn, fa=fa, fs=fs).rotate(
                [0, 0, 180 / 8]
            )
            return p.rotate(rot) if rot else p

        def hollow_cell() -> Bosl2Solid:
            return (
                octprism(sz + 1, [0, 90, 0])
                | octprism(sz + 1, None)
                | cuboid([octid, octid, octid], fn=fn, fa=fa, fs=fs)
            )

        pieces = []
        for mx in DistributableMatrix.xcopies(step, num_copies=ex):
            base = cuboid([sz, length, height], fn=fn, fa=fa, fs=fs).half_of(v=v, s=smax)
            cells = [
                hollow_cell().multmatrix((my @ mz).tolist())
                for my in DistributableMatrix.ycopies(step, num_copies=ey)
                for mz in DistributableMatrix.zcopies(step, num_copies=ez)
            ]
            holes = _union(cells).half_of(v=v, center=st, s=smax)
            ytun = _union(
                [
                    octprism(ey * sz + 1, [90, 0, 0]).multmatrix(mz.tolist())
                    for mz in DistributableMatrix.zcopies(step, num_copies=ez)
                ]
            )
            pieces.append((base - holes - ytun).multmatrix(mx.tolist()))
        self._solid: Bosl2Solid = Bosl2Solid(_union(pieces).shape, size=[w, length, height])

    @property
    @csg_part("chamfers with chamfer_edge_mask(), a 2-D profile extruded along each edge")
    def shape(self) -> Bosl2Solid:
        """Return the support truss geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the support truss in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()


class TrussCorner:
    """A corner truss with arms jutting out in one or more directions.

    *height* is the central column height in cubes.  *extents* is a scalar
    (equal arms in +X, +Y and +Z) or a length-≤5 vector.

    Examples:
        An L-corner:

        .. pythonscad-example::

            from pybosl2.parts.cubetruss import TrussCorner
            TrussCorner(extents=2).show()

    """

    def __init__(
        self,
        height: int = 1,
        extents: int | Sequence[int] = 1,
        bracing: bool | None = None,
        size: float | None = None,
        strut: float | None = None,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a corner truss.

        Args:
            height: Central column height in cubes. Defaults to 1.
            extents: Scalar (equal arms) or length-≤5 vector. Defaults to 1.
            bracing: If True, add cross bracing inside each cube.
            size: Cube size in mm. Defaults to CUBETRUSS_SIZE (30 mm).
            strut: Strut thickness in mm. Defaults to CUBETRUSS_STRUT_SIZE (3 mm).
            fn: Number of fragments for rounded geometry.
            fa: Fragment angle for rounded geometry.
            fs: Fragment size for rounded geometry.

        Returns:
            None.

        """
        sz = CUBETRUSS_SIZE if size is None else size
        st = CUBETRUSS_STRUT_SIZE if strut is None else strut
        h = int(height)
        if isinstance(extents, (int, float)):
            exts = [int(extents), int(extents), 0, 0, int(extents)]
        else:
            exts = [int(x) for x in (list(extents) + [0] * 5)[:5]]
        step = sz - st

        def seg() -> Bosl2Solid:
            return TrussSegment(size=sz, strut=st, bracing=bracing, fn=fn, fa=fa, fs=fs).shape

        segs = [seg().up(step * zcol) for zcol in range(h)]
        for d in range(4):
            for zcol in range(h):
                for i in range(1, exts[d] + 1):
                    segs.append(seg().right((step + 0.01) * i).up((step + 0.01) * zcol).rotate([0, 0, d * 90]))
        for i in range(1, exts[4] + 1):
            segs.append(seg().up((step + 0.01) * (i + h - 1)))

        result = _union(segs)
        s = [
            truss_dist(exts[0] + 1 + exts[2], 1, sz, st),
            truss_dist(exts[1] + 1 + exts[3], 1, sz, st),
            truss_dist(h + exts[4], 1, sz, st),
        ]
        self._solid: Bosl2Solid = Bosl2Solid(result.shape, size=s)
        self._height: int = h

    @property
    def height(self) -> int:
        """Central column height in cubes."""
        return self._height

    @property
    @csg_part("chamfers with chamfer_edge_mask(), a 2-D profile extruded along each edge")
    def shape(self) -> Bosl2Solid:
        """Return the corner geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the corner in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()


class TrussClip:
    """A pair of snap clips for the end of a truss.

    Examples:
        A truss clip:

        .. pythonscad-example::

            from pybosl2.parts.cubetruss import TrussClip
            TrussClip().show()

    """

    def __init__(
        self,
        extents: int = 1,
        size: float | None = None,
        strut: float | None = None,
        clipthick: float | None = None,
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a truss clip pair.

        Args:
            extents: Width in cubes. Defaults to 1.
            size: Cube size in mm. Defaults to CUBETRUSS_SIZE (30 mm).
            strut: Strut thickness in mm. Defaults to CUBETRUSS_STRUT_SIZE (3 mm).
            clipthick: Clip thickness in mm. Defaults to CUBETRUSS_CLIP_THICKNESS (1.6 mm).
            slop: Extra clearance for clips.
            fn: Number of fragments for rounded geometry.
            fa: Fragment angle for rounded geometry.
            fs: Fragment size for rounded geometry.

        Returns:
            None.

        """
        sz = CUBETRUSS_SIZE if size is None else size
        st = CUBETRUSS_STRUT_SIZE if strut is None else strut
        ct = CUBETRUSS_CLIP_THICKNESS if clipthick is None else clipthick
        cliplen = st * 2.6
        clipheight = min(sz + st, sz / 3 + 2 * st * 2.6)
        clipsize = 0.5

        def one_clip() -> Bosl2Solid:
            hook = prismoid(
                [ct, clipheight],
                [ct, clipheight - cliplen * 2],
                height=cliplen,
                fn=fn,
                fa=fa,
                fs=fs,
            ).rotate([90, 0, 0])
            hook = hook - _cmask(clipheight + 0.1, ct).right(ct / 2)
            hook = hook.back(st).right(ct / 2 - 0.01)
            if slop > 0:
                hook = hook - cuboid([slop, st * 3, sz], fn=fn, fa=fa, fs=fs).forward(st * 3 / 2)
            lip = (
                prismoid(
                    [clipheight - cliplen * 2, st / 2],
                    [clipheight - cliplen * 2 - 2 * clipsize, st / 2],
                    height=clipsize + 0.01,
                    fn=fn,
                    fa=fa,
                    fs=fs,
                )
                .rotate([0, -90, 0])
                .forward(st * 1.25 + slop)
                .right(slop / 2 + 0.01)
            )
            clip = hook | lip
            clip = clip - _cmask(sz + 1, clipsize + ct / 3).scale([1, 1.5, 1]).left(clipsize).forward(st * 1.6)
            for mz in DistributableMatrix.zcopies(clipheight - st, num_copies=2):
                clip = clip - cuboid([ct * 3, cliplen * 2, st], fn=fn, fa=fa, fs=fs).multmatrix(mz.tolist())
            for mz in DistributableMatrix.zcopies(clipheight - 2 * st, num_copies=2):
                clip = clip - _cmask(cliplen * 2, ct, orient="BACK").right(ct).multmatrix(mz.tolist())
            return clip

        pair = _union(
            [
                one_clip().multmatrix(m.tolist())
                for m in DistributableMatrix.xflip_copy(offset=(extents * (sz - st) + st) / 2)
            ]
        )
        # Nominal anchor box: the truss cell the clip mounts into, so a clip anchors to the truss
        # it grips rather than to its own hooks -- which stand outside this box in Y.
        s_arr = [
            extents * (sz - st) + st + 2 * ct,
            st * 2,
            clipheight - 2 * st,
        ]
        self._solid: Bosl2Solid = Bosl2Solid(pair.shape, size=s_arr)

    @property
    @csg_part("chamfers with chamfer_edge_mask(), a 2-D profile extruded along each edge")
    def shape(self) -> Bosl2Solid:
        """Return the clip geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the clip in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()


class TrussFoot:
    """A foot that clips onto the bottom of a truss for support.

    Examples:
        A truss foot:

        .. pythonscad-example::

            from pybosl2.parts.cubetruss import TrussFoot
            TrussFoot().show()

    """

    def __init__(
        self,
        w: int = 1,
        size: float | None = None,
        strut: float | None = None,
        clipthick: float | None = None,
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a truss foot.

        Args:
            w: Width in cubes. Defaults to 1.
            size: Cube size in mm. Defaults to CUBETRUSS_SIZE (30 mm).
            strut: Strut thickness in mm. Defaults to CUBETRUSS_STRUT_SIZE (3 mm).
            clipthick: Clip thickness in mm. Defaults to CUBETRUSS_CLIP_THICKNESS (1.6 mm).
            slop: Extra clearance for clips.
            fn: Number of fragments for rounded geometry.
            fa: Fragment angle for rounded geometry.
            fs: Fragment size for rounded geometry.

        Returns:
            None.

        """
        sz = CUBETRUSS_SIZE if size is None else size
        st = CUBETRUSS_STRUT_SIZE if strut is None else strut
        ct = CUBETRUSS_CLIP_THICKNESS if clipthick is None else clipthick
        clipsize = 0.5
        wall_h = st + ct * 1.5
        cyld = (sz - 2 * st) / math.cos(math.radians(180 / 8))
        span = w * (sz - st) + st
        parts: list[Bosl2Solid] = []
        base = cuboid(
            [span + 2 * ct, sz - 2 * st, ct],
            chamfer=st,
            edges=Anchor.Z,
            fn=fn,
            fa=fa,
            fs=fs,
        ).up(ct / 2)
        parts.append(base)
        for mx in DistributableMatrix.xcopies(span + ct, num_copies=2):
            parts.append(
                prismoid(
                    [ct, sz - 4 * st],
                    [ct, sz / 3.5],
                    height=wall_h,
                    anchor=BOTTOM,
                    fn=fn,
                    fa=fa,
                    fs=fs,
                )
                .up(ct - 0.01)
                .multmatrix(mx.tolist())
            )
        for mx in DistributableMatrix.xcopies(span, num_copies=2):
            parts.append(
                prismoid(
                    [clipsize * 2, sz / 3.5],
                    [0.1, sz / 3.5],
                    height=clipsize * 3,
                    anchor=BOTTOM,
                    fn=fn,
                    fa=fa,
                    fs=fs,
                )
                .up(ct + st + slop * 2)
                .multmatrix(mx.tolist())
            )
        for xcol in range(w):
            plug = (
                regular_prism(
                    8,
                    radius1=(cyld - 4 * slop) / 2,
                    radius2=(cyld - 4 * slop - 1) / 2,
                    height=st,
                    anchor=BOTTOM,
                    fn=fn,
                    fa=fa,
                    fs=fs,
                )
                .rotate([0, 0, 180 / 8])
                .up(ct - 0.01)
            )
            for my in DistributableMatrix.ycopies(sz - 2 * st - 4 * slop, num_copies=2):
                plug = plug - _cmask(sz - st, st * 2 / 3, orient="RIGHT").up(ct + st).multmatrix(my.tolist())
            for mz_ang in [-45, 45]:
                plug = plug - cuboid(
                    [sz * 3, st / math.sqrt(2) + 2 * slop, sz * 3],
                    fn=fn,
                    fa=fa,
                    fs=fs,
                ).rotate([0, 0, mz_ang])
            parts.append(plug.right((xcol - (w - 1) / 2) * (sz - st)))
        result = _union(parts).down(ct)
        # Nominal anchor box: the foot's plate. Its plugs stand proud of the plate in Z, so
        # bounds() is taller -- anchoring follows the surface the foot sits on.
        s_arr = [span + 2 * ct, sz - 2 * st, st + ct]
        self._solid: Bosl2Solid = Bosl2Solid(result.shape, size=s_arr)

    @property
    @csg_part("chamfers with chamfer_edge_mask(), a 2-D profile extruded along each edge")
    def shape(self) -> Bosl2Solid:
        """Return the foot geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the foot in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()


class TrussUClip:
    """A U-shaped clip that joins two trusses face to face.

    Examples:
        A U-clip:

        .. pythonscad-example::

            from pybosl2.parts.cubetruss import TrussUClip
            TrussUClip().show()

    """

    def __init__(
        self,
        dual: bool = True,
        size: float | None = None,
        strut: float | None = None,
        clipthick: float | None = None,
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a U-clip.

        Args:
            dual: If True, create clips on both sides. Defaults to True.
            size: Cube size in mm. Defaults to CUBETRUSS_SIZE (30 mm).
            strut: Strut thickness in mm. Defaults to CUBETRUSS_STRUT_SIZE (3 mm).
            clipthick: Clip thickness in mm. Defaults to CUBETRUSS_CLIP_THICKNESS (1.6 mm).
            slop: Extra clearance for clips.
            fn: Number of fragments for rounded geometry.
            fa: Fragment angle for rounded geometry.
            fs: Fragment size for rounded geometry.

        Returns:
            None.

        """
        sz = CUBETRUSS_SIZE if size is None else size
        st = CUBETRUSS_STRUT_SIZE if strut is None else strut
        ct = CUBETRUSS_CLIP_THICKNESS if clipthick is None else clipthick
        clipsize = 0.5
        nd = 2 if dual else 1
        s_arr = [nd * st + 2 * ct + slop, st + 2 * ct, sz / 3.5]
        body = cuboid(s_arr, fn=fn, fa=fa, fs=fs) - cuboid(
            [nd * st + slop, st + 2 * ct, sz + 1],
            fn=fn,
            fa=fa,
            fs=fs,
        ).back(ct)
        prism = (
            prismoid(
                [sz / 3.5, ct * 1.87],
                [sz / 3.5, 0.1],
                height=clipsize,
                anchor=BOTTOM,
                fn=fn,
                fa=fa,
                fs=fs,
            )
            .back_half()
            .rotate([0, -90, 0])
        )
        clips = _union(
            [
                prism.multmatrix(m.tolist())
                for m in DistributableMatrix.xflip_copy(offset=(1 if dual else 0.5) * st + slop / 2)
            ]
        ).back((st + slop) / 2)
        self._solid: Bosl2Solid = Bosl2Solid((body | clips).shape, size=s_arr)

    @property
    @csg_part("chamfers with chamfer_edge_mask(), a 2-D profile extruded along each edge")
    def shape(self) -> Bosl2Solid:
        """Return the U-clip geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the U-clip in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()


class TrussJoiner:
    """A joiner that clips two trusses end to end.

    Examples:
        A truss joiner:

        .. pythonscad-example::

            from pybosl2.parts.cubetruss import TrussJoiner
            TrussJoiner().show()

    """

    def __init__(
        self,
        w: int = 1,
        vert: bool = True,
        size: float | None = None,
        strut: float | None = None,
        clipthick: float | None = None,
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a truss joiner.

        Args:
            w: Width in cubes. Defaults to 1.
            vert: If True, add vertical supports. Defaults to True.
            size: Cube size in mm. Defaults to CUBETRUSS_SIZE (30 mm).
            strut: Strut thickness in mm. Defaults to CUBETRUSS_STRUT_SIZE (3 mm).
            clipthick: Clip thickness in mm. Defaults to CUBETRUSS_CLIP_THICKNESS (1.6 mm).
            slop: Extra clearance for clips.
            fn: Number of fragments for rounded geometry.
            fa: Fragment angle for rounded geometry.
            fs: Fragment size for rounded geometry.

        Returns:
            None.

        """
        sz = CUBETRUSS_SIZE if size is None else size
        st = CUBETRUSS_STRUT_SIZE if strut is None else strut
        ct = CUBETRUSS_CLIP_THICKNESS if clipthick is None else clipthick
        clipsize = 0.5
        span = w * (sz - st) + st
        parts: list[Bosl2Solid] = [cuboid([span + 2 * ct, sz, ct], fn=fn, fa=fa, fs=fs).up(ct / 2)]
        for mx in DistributableMatrix.xcopies(span + ct, num_copies=2):
            parts.append(
                cuboid([ct, sz, ct + st * 3 / 4], fn=fn, fa=fa, fs=fs).up((ct + st * 3 / 4) / 2).multmatrix(mx.tolist())
            )
        for my in DistributableMatrix.ycopies(sz, num_copies=2):
            parts.append(
                TrussFoot(w=w, size=sz, strut=st, clipthick=ct, slop=slop, fn=fn, fa=fa, fs=fs)
                .shape.up((st + ct) / 2)
                .multmatrix(my.tolist())
            )
        if vert:
            for mx in DistributableMatrix.xcopies(span + ct, num_copies=2):
                parts.append(
                    prismoid(
                        [ct, sz],
                        [ct, 2 * st + 2 * ct],
                        height=sz * 0.6,
                        anchor=BOTTOM,
                        fn=fn,
                        fa=fa,
                        fs=fs,
                    )
                    .up(ct - 0.01)
                    .multmatrix(mx.tolist())
                )
            wallclip = (
                prismoid(
                    [sz / 3.5, ct * 2],
                    [sz / 3.5 - 4 * 2 * clipsize, 0.1],
                    height=2 * clipsize,
                    anchor=BOTTOM,
                    fn=fn,
                    fa=fa,
                    fs=fs,
                )
                .back_half()
                .rotate([0, -90, 0])
            )
            for mx in DistributableMatrix.xflip_copy(offset=(span + 0.02) / 2):
                for my in _yflip_copy(offset=st + slop / 2):
                    parts.append(wallclip.multmatrix((mx @ my).tolist()).up(sz / 2))
        result = _union(parts).down(ct)
        # Nominal anchor box: the joiner's plate, as TrussFoot uses. Its wall clips stand well
        # above the plate, so bounds() is several times taller in Z.
        s_arr = [span + 2 * ct, 2 * (sz - st) + st, st + ct]
        self._solid: Bosl2Solid = Bosl2Solid(result.shape, size=s_arr)

    @property
    @csg_part("chamfers with chamfer_edge_mask(), a 2-D profile extruded along each edge")
    def shape(self) -> Bosl2Solid:
        """Return the joiner geometry."""
        return self._solid

    def show(self) -> Any:
        """Display the joiner in the viewer, and return it.

        Returns:
            The shape, so the call can be chained or assigned.

        """
        return self._solid.show()

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/parts/threading.py
#    Pure-Python port of the core of BOSL2's threading.scad: screw threads built by sweeping a 2-D
#    thread profile helically (via the toolkit's :func:`~pybosl2.skin.spiral_sweep`) and unioning a
#    core cylinder. The :class:`Threading` class exposes the thread generators as methods:
#    ``threaded_rod`` (ISO/UTS), ``trapezoidal_threaded_rod``, ``acme_threaded_rod``,
#    ``square_threaded_rod``, ``buttress_threaded_rod``, the matching ``*_nut`` builders,
#    ``generic_threaded_rod`` / ``generic_threaded_nut``, and ``thread_helix``.
#
#    The thread *profiles* are ported verbatim from BOSL2 (checked in tests/test_threading.py) and
#    the resulting geometry is verified against a real-app BOSL2 render (matching major/minor
#    diameter, length, thread pitch, and watertightness). This is a clean, geometrically-correct
#    port; the elaborate BOSL2 refinements -- blunt-start / lead-in tapers, teardrop threads, and
#    the bevel machinery -- are NOT ported (a follow-up), so ends are cut flush.
#
# FileSummary: Screw threading: threaded rods and nuts (ISO/trapezoidal/acme/square/buttress).
# DocCategory: Parts library
# FileGroup: BOSL2

"""Screw threading: threaded rods and nuts (ISO/trapezoidal/acme/square/buttress)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

from pybosl2.enums import VNFStyle
from pybosl2.parts.enums import NutShape
from pybosl2.shapes3d import Bosl2Solid, cuboid, cyl, regular_prism

__all__ = ["Threading", "ThreadProfile"]


# ---------------------------------------------------------------------------
# Section: thread profiles (in pitch units: x in [-1/2, 1/2], y the depth fraction)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ThreadProfile:
    """A 2-D thread cross-section in pitch units: x along the axis in [-1/2, 1/2], y the (negative).

    depth fraction. ``name`` labels the standard it came from; ``points`` is the profile polygon.

    Behaves like the plain list of ``[x, y]`` points it wraps -- it iterates, indexes, has a length
    and converts to a numpy array of shape ``(n, 2)`` -- so it drops straight into the thread
    builders (and anywhere a raw point list is accepted), while also carrying its name and
    :attr:`depth`.
    """

    name: str
    points: tuple[tuple[float, float], ...]

    @property
    def depth(self) -> float:
        """Peak-to-valley depth as a fraction of the pitch."""
        ys = [p[1] for p in self.points]
        return max(ys) - min(ys)

    def depth_abs(self, pitch: float) -> float:
        """Absolute peak-to-valley depth (mm) at the given *pitch*."""
        return self.depth * pitch

    def as_points(self) -> list[list[float]]:
        """Return the profile as a plain list of ``[x, y]`` float pairs."""
        return [[float(x), float(y)] for x, y in self.points]

    def __iter__(self) -> Iterator[list[float]]:
        """Return an iterator."""
        return (list(p) for p in self.points)

    def __len__(self) -> int:
        """Return the number of items."""
        return len(self.points)

    def __getitem__(self, i: int) -> list[float]:
        """Return the item at index."""
        return list(self.points[i])


def _iso_profile() -> ThreadProfile:
    depth = math.cos(math.radians(30)) * 5 / 8
    clockwise = 1 / 8
    return ThreadProfile(
        "ISO",
        (
            (-depth / math.sqrt(3) - clockwise / 2, -depth),
            (-clockwise / 2, 0),
            (clockwise / 2, 0),
            (depth / math.sqrt(3) + clockwise / 2, -depth),
        ),
    )


def _trapezoidal_profile(pitch: float, thread_angle: float = 30, thread_depth: float | None = None) -> ThreadProfile:
    depth = thread_depth if thread_depth is not None else pitch / 2
    pa_delta = 0.5 * depth * math.tan(math.radians(thread_angle / 2)) / pitch
    assert pa_delta <= 0.25, "trapezoidal thread geometry is impossible (angle/depth too large)."
    rr1 = -depth / pitch
    z1, z2 = 0.25 - pa_delta, 0.25 + pa_delta
    return ThreadProfile(f"trapezoidal-{thread_angle:g}deg", ((-z2, rr1), (-z1, 0), (z1, 0), (z2, rr1)))


def _buttress_profile() -> ThreadProfile:
    return ThreadProfile(
        "buttress",
        (
            (-1 / 2, -0.77),
            (-7 / 16, -0.75),
            (5 / 16, 0),
            (7 / 16, 0),
            (7 / 16, -0.75),
            (1 / 2, -0.77),
        ),
    )


# ---------------------------------------------------------------------------
# Section: geometry
# ---------------------------------------------------------------------------


def _thread_grid(
    profile: list[list[float]] | ThreadProfile,
    pitch: float,
    r: float,
    length: float,
    starts: int,
    left_handed: bool,
    sides: int,
) -> list[list[list[float]]]:
    """One angular sector (360/starts) of the thread surface as a column grid for vnf_vertex_array.

    Each column is a vertical stack of vertices for one angle: bottom axis point, the thread profile
    repeated up every turn, and the top axis point. Sweeping the columns around builds the whole
    rod (core + helical thread) as one closed, manifold polyhedron -- no CSG union of the thread
    with a coaxial core (which Manifold cannot do cleanly).
    """
    prof = [[float(x), float(y)] for x, y in profile]
    start_steps = sides // starts
    direction = -1 if left_handed else 1
    len1, len2 = -length / 2 - pitch, length / 2 + pitch
    turns1 = int(math.floor(len1 / pitch)) - 1
    turns2 = int(math.ceil(len2 / pitch)) + 1
    grid = []
    for step in range(start_steps + 1):
        angle = math.radians(360 * step / sides * direction)
        dz = step / start_steps
        ca, sa = math.cos(angle), math.sin(angle)
        col = [[0.0, 0.0, len1]]
        for turn in range(turns1, turns2 + 1):
            for px, py in prof:
                z = max(len1, min(len2, (px + turn + dz) * pitch))
                rad = r + py * pitch
                col.append([rad * ca, rad * sa, z])
        col.append([0.0, 0.0, len2])
        grid.append(col)
    return grid


def _rot_z(pts: list[list[float]], deg: float) -> list[list[float]]:
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [[x * c - y * s, x * s + y * c, z] for x, y, z in pts]


def _rod_solid(
    d: float,
    length: float,
    pitch: float,
    profile: list[list[float]] | ThreadProfile,
    starts: int = 1,
    left_handed: bool = False,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """Return the external threaded-rod solid, built as a direct manifold polyhedron, trimmed to length.

    Each of the *starts* thread starts is one angular sector's vertex-array surface; the sectors are
    merged at the VNF level (not by CSG union, which Manifold cannot do on coaxial helical solids)
    into one polyhedron, then trimmed to length with an intersection.
    """
    from pybosl2._helpers import frag_count, quantup
    from pybosl2.vnf import VNF

    radius = d / 2
    sides = int(quantup(frag_count(radius, fn, fa, fs), starts))
    verts: list[list[float]] = []
    faces: list[list[int]] = []
    for k in range(starts):
        grid = _thread_grid(profile, pitch, radius, length, starts, left_handed, sides)
        vnf = VNF.vertex_array(grid, col_wrap=False, style=VNFStyle.CONVEX)
        rv = _rot_z(list(vnf.vertices), k * 360 / starts) if starts > 1 else list(vnf.vertices)
        off = len(verts)
        verts += [list(v) for v in rv]
        faces += [[i + off for i in f] for f in vnf.faces]
    # the helical surface comes out wound inwards, so the merged VNF is flipped back before it
    # becomes a solid -- an inside-out thread inverts every cut it is used for
    surface = VNF(verts, faces)
    thread = Bosl2Solid((surface if surface.volume() >= 0 else surface.reverse()).polyhedron())
    return thread & cyl(height=length, radius=radius + 1, fn=fn, fa=fa, fs=fs)


def _profile_depth_abs(profile: list[list[float]] | ThreadProfile, pitch: float) -> float:
    if isinstance(profile, ThreadProfile):
        return profile.depth_abs(pitch)
    ys = [float(p[1]) for p in profile]
    return (max(ys) - min(ys)) * pitch


def _nut_solid(
    nutwidth: float,
    idia: float,
    h: float,
    pitch: float,
    profile: list[list[float]] | ThreadProfile,
    shape: NutShape = NutShape.HEX,
    starts: int = 1,
    left_handed: bool = False,
    slop: float = 0.0,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> Bosl2Solid:
    """Return a nut: a hex/square body with a threaded hole cut by a matching thread 'tap'."""
    if shape == NutShape.HEX:
        body = regular_prism(6, height=h, inner_diameter=nutwidth, fn=fn, fa=fa, fs=fs)
    elif shape == NutShape.SQUARE:
        body = cuboid([nutwidth, nutwidth, h], fn=fn, fa=fa, fs=fs)
    else:
        raise AssertionError('nut shape must be "hex" or "square".')
    if pitch == 0:
        return body - cyl(height=h + 2, radius=idia / 2 + slop, fn=fn, fa=fa, fs=fs)
    depth_abs = _profile_depth_abs(profile, pitch)
    tap = _rod_solid(
        idia + 2 * depth_abs + 2 * slop,
        h + 2 * pitch,
        pitch,
        profile,
        starts=starts,
        left_handed=left_handed,
        fn=fn,
        fa=fa,
        fs=fs,
    )
    return body - tap


# ---------------------------------------------------------------------------
# Section: Threading class
# ---------------------------------------------------------------------------


class Threading:
    """Screw-thread generators (BOSL2 threading.scad). Every method returns a.

    :class:`~pybosl2.shapes3d.Bosl2Solid`; call them on the class, e.g. ``Threading.threaded_rod(...)``.

    A *rod* is a threaded cylinder; a *nut* is a hex/square block with a matching threaded hole
    (cut by a thread 'tap', with *slop* clearance). *pitch* is the axial distance between threads,
    *starts* the number of thread starts, and *left_handed* flips the helix.

    .. seealso::

       `Visual spec sheet <specs/threading.html>`_ — measurements and STL previews
    """

    # -- generic ---------------------------------------------------------------------------

    @staticmethod
    def generic_threaded_rod(
        d: float,
        l: float,  # noqa: E741
        pitch: float,
        profile: list[list[float]] | ThreadProfile,
        starts: int = 1,
        left_handed: bool = False,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """Return a threaded rod from an explicit 2-D thread *profile* (x in [-1/2, 1/2], y the depth.

        fraction, both in pitch units) -- the core every other rod builds on (BOSL2 generic_threaded_rod()).
        """
        assert pitch > 0, "generic_threaded_rod(): d, l and pitch must be positive."
        assert l > 0, "generic_threaded_rod(): d, l and pitch must be positive."
        assert d > 0, "generic_threaded_rod(): d, l and pitch must be positive."
        return _rod_solid(d, l, pitch, profile, starts, left_handed, fn, fa, fs)

    @staticmethod
    def generic_threaded_nut(
        nutwidth: float,
        id: float,  # noqa: A002
        h: float,
        pitch: float,
        profile: list[list[float]] | ThreadProfile,
        shape: NutShape = NutShape.HEX,
        starts: int = 1,
        left_handed: bool = False,
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """Return a nut from an explicit thread *profile* (BOSL2 generic_threaded_nut())."""
        return _nut_solid(
            nutwidth,
            id,
            h,
            pitch,
            profile,
            shape,
            starts,
            left_handed,
            slop,
            fn,
            fa,
            fs,
        )

    # -- ISO / UTS -------------------------------------------------------------------------

    @staticmethod
    def threaded_rod(
        d: float,
        l: float,  # noqa: E741
        pitch: float,
        starts: int = 1,
        left_handed: bool = False,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """Return an ISO (metric) / UTS (imperial) 60-degree triangular threaded rod (BOSL2.

        threaded_rod()).

        Examples:
            An M20×2.5 threaded rod, 30 mm long:

            .. pythonscad-example::

                from pybosl2.parts.threading import Threading
                Threading.threaded_rod(d=20, l=30, pitch=2.5, fa=6, fs=1).show()

        """
        return _rod_solid(d, l, pitch, _iso_profile(), starts, left_handed, fn, fa, fs)

    @staticmethod
    def threaded_nut(
        nutwidth: float,
        id: float,  # noqa: A002
        h: float,
        pitch: float,
        shape: NutShape = NutShape.HEX,
        starts: int = 1,
        left_handed: bool = False,
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """Return a hex/square nut for an ISO/UTS threaded rod (BOSL2 threaded_nut()).

        Examples:
            An M8 nut for an M8×1.25 rod:

            .. pythonscad-example::

                from pybosl2.parts.threading import Threading
                Threading.threaded_nut(nutwidth=13, id=8, h=6.8, pitch=1.25).show()

        """
        return _nut_solid(
            nutwidth,
            id,
            h,
            pitch,
            _iso_profile(),
            shape,
            starts,
            left_handed,
            slop,
            fn,
            fa,
            fs,
        )

    # -- trapezoidal / metric trapezoidal --------------------------------------------------

    @staticmethod
    def trapezoidal_threaded_rod(
        d: float,
        l: float,  # noqa: E741
        pitch: float,
        thread_angle: float = 30,
        thread_depth: float | None = None,
        starts: int = 1,
        left_handed: bool = False,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """Return a symmetric trapezoidal threaded rod (metric trapezoidal by default) (BOSL2.

        trapezoidal_threaded_rod()).

        Examples:
            A Tr20×4 trapezoidal leadscrew, 40 mm long:

            .. pythonscad-example::

                from pybosl2.parts.threading import Threading
                Threading.trapezoidal_threaded_rod(d=20, l=40, pitch=4, fa=6, fs=1).show()

        """
        prof = _trapezoidal_profile(pitch, thread_angle, thread_depth)
        return _rod_solid(d, l, pitch, prof, starts, left_handed, fn, fa, fs)

    @staticmethod
    def trapezoidal_threaded_nut(
        nutwidth: float,
        id: float,  # noqa: A002
        h: float,
        pitch: float,
        thread_angle: float = 30,
        thread_depth: float | None = None,
        shape: NutShape = NutShape.HEX,
        starts: int = 1,
        left_handed: bool = False,
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """Return a nut for a trapezoidal threaded rod (BOSL2 trapezoidal_threaded_nut())."""
        prof = _trapezoidal_profile(pitch, thread_angle, thread_depth)
        return _nut_solid(
            nutwidth,
            id,
            h,
            pitch,
            prof,
            shape,
            starts,
            left_handed,
            slop,
            fn,
            fa,
            fs,
        )

    # -- ACME ------------------------------------------------------------------------------

    @staticmethod
    def acme_threaded_rod(
        d: float,
        l: float,  # noqa: E741
        pitch: float,
        thread_depth: float | None = None,
        starts: int = 1,
        left_handed: bool = False,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """Return a 29-degree ACME threaded rod (BOSL2 acme_threaded_rod()).

        Examples:
            An ACME ½"-10 leadscrew, 30 mm long:

            .. pythonscad-example::

                from pybosl2.parts.threading import Threading
                Threading.acme_threaded_rod(d=12.7, l=30, pitch=2.54, fa=6, fs=1).show()

        """
        prof = _trapezoidal_profile(pitch, 29, thread_depth if thread_depth is not None else pitch / 2)
        return _rod_solid(d, l, pitch, prof, starts, left_handed, fn, fa, fs)

    @staticmethod
    def acme_threaded_nut(
        nutwidth: float,
        id: float,  # noqa: A002
        h: float,
        pitch: float,
        thread_depth: float | None = None,
        shape: NutShape = NutShape.HEX,
        starts: int = 1,
        left_handed: bool = False,
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """Return a nut for an ACME threaded rod (BOSL2 acme_threaded_nut())."""
        prof = _trapezoidal_profile(pitch, 29, thread_depth if thread_depth is not None else pitch / 2)
        return _nut_solid(
            nutwidth,
            id,
            h,
            pitch,
            prof,
            shape,
            starts,
            left_handed,
            slop,
            fn,
            fa,
            fs,
        )

    # -- square ----------------------------------------------------------------------------

    @staticmethod
    def square_threaded_rod(
        d: float,
        l: float,  # noqa: E741
        pitch: float,
        starts: int = 1,
        left_handed: bool = False,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """Return a square-profile threaded rod (BOSL2 square_threaded_rod())."""
        prof = _trapezoidal_profile(pitch, 0.1)
        return _rod_solid(d, l, pitch, prof, starts, left_handed, fn, fa, fs)

    @staticmethod
    def square_threaded_nut(
        nutwidth: float,
        id: float,  # noqa: A002
        h: float,
        pitch: float,
        shape: NutShape = NutShape.HEX,
        starts: int = 1,
        left_handed: bool = False,
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """Return a nut for a square threaded rod (BOSL2 square_threaded_nut())."""
        prof = _trapezoidal_profile(pitch, 0.1)
        return _nut_solid(
            nutwidth,
            id,
            h,
            pitch,
            prof,
            shape,
            starts,
            left_handed,
            slop,
            fn,
            fa,
            fs,
        )

    # -- buttress --------------------------------------------------------------------------

    @staticmethod
    def buttress_threaded_rod(
        d: float,
        l: float,  # noqa: E741
        pitch: float,
        starts: int = 1,
        left_handed: bool = False,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """Return an asymmetric buttress threaded rod (BOSL2 buttress_threaded_rod())."""
        return _rod_solid(d, l, pitch, _buttress_profile(), starts, left_handed, fn, fa, fs)

    @staticmethod
    def buttress_threaded_nut(
        nutwidth: float,
        id: float,  # noqa: A002
        h: float,
        pitch: float,
        shape: NutShape = NutShape.HEX,
        starts: int = 1,
        left_handed: bool = False,
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """Return a nut for a buttress threaded rod (BOSL2 buttress_threaded_nut())."""
        return _nut_solid(
            nutwidth,
            id,
            h,
            pitch,
            _buttress_profile(),
            shape,
            starts,
            left_handed,
            slop,
            fn,
            fa,
            fs,
        )

    # -- single thread helix ---------------------------------------------------------------

    @staticmethod
    def thread_helix(
        d: float,
        pitch: float,
        thread_depth: float | None = None,
        flank_angle: float = 15,
        turns: float = 1,
        starts: int = 1,
        left_handed: bool = False,
        profile: list[list[float]] | ThreadProfile | None = None,
    ) -> Bosl2Solid:
        """Return a single helical thread ridge (no core), for adding threads onto your own cylinder.

        (BOSL2 thread_helix()). The thread crest is at diameter *d*; give *thread_depth* and
        *flank_angle*, or an explicit *profile*.

        .. note::
            This function does not accept ``fn``/``fa``/``fs`` — it builds its geometry
            entirely through :func:`~pybosl2.skin.spiral_sweep` (VNF / polyhedron output),
            which has no arc-based primitives and therefore no smoothing resolution to control.
        """
        from pybosl2.path2d import Path2D

        assert pitch > 0, "thread_helix(): d and pitch must be positive."
        assert d > 0, "thread_helix(): d and pitch must be positive."
        if profile is None:
            depth = thread_depth if thread_depth is not None else pitch / 2
            profile = _trapezoidal_profile(pitch, 2 * flank_angle, depth)
        prof = [[float(x), float(y)] for x, y in profile]
        ys = [p[1] for p in prof]
        pmax = max(ys)
        radius = d / 2
        section = [[(py - pmax) * pitch, px * pitch] for px, py in prof]
        lead = starts * pitch
        height = turns * lead
        thread: Bosl2Solid | None = None
        for k in range(starts):
            sec = [[x, y + k * pitch] for x, y in section]
            piece = Bosl2Solid(
                Path2D(sec)
                .spiral_sweep(
                    height=height,
                    radius=radius,
                    turns=turns * (-1 if left_handed else 1),
                    center=True,
                )
                .polyhedron()  # type: ignore[union-attr]
            )
            if starts > 1:
                piece = piece.rotate([0, 0, k * 360 / starts])
            thread = piece if thread is None else (thread | piece)
        assert thread is not None
        return thread

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

    from pybosl2._backend import Solid

from pybosl2._backend import csg_part
from pybosl2.enums import VNFStyle
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.parts._buildable import Buildable
from pybosl2.parts.enums import NutShape
from pybosl2.shapes3d import Bosl2Solid, cuboid, cyl, regular_prism
from pybosl2.vnf import VNF

__all__ = ["ThreadedRod", "ThreadedNut", "ThreadHelix", "ThreadProfile"]


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
    if not (pa_delta <= 0.25):
        raise Bosl2ValueError("trapezoidal thread geometry is impossible (angle/depth too large).")
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
) -> "Solid":
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
    thread = (surface if surface.volume() >= 0 else surface.reverse()).polyhedron()
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
        raise Bosl2ValueError(f"nut(): shape must be NutShape.HEX or NutShape.SQUARE, got {shape!r}.")
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
# Section: Threading classes
# ---------------------------------------------------------------------------


class ThreadedRod(Buildable):
    """A threaded rod built from an explicit 2-D thread profile.

    *profile* is a :class:`ThreadProfile` or a plain point list in pitch units
    (x in [-1/2, 1/2], y the depth fraction). *starts* is the number of thread
    starts and *left_handed* flips the helix.

    Examples:
        An M20×2.5 ISO threaded rod, 30 mm long:

        .. pythonscad-example::

            from pybosl2.parts.threading import ThreadedRod, iso_threaded_rod
            iso_threaded_rod(d=20, l=30, pitch=2.5, fa=6, fs=1).show()

    """

    def __init__(
        self,
        d: float,
        l: float,  # noqa: E741
        pitch: float,
        profile: list[list[float]] | ThreadProfile,
        starts: int = 1,
        left_handed: bool = False,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a threaded rod from *profile* (a :class:`ThreadProfile` or point list).

        Args:
            d: Nominal outer diameter in mm.
            l: Length in mm.
            pitch: Thread pitch in mm.
            profile: A :class:`ThreadProfile` or a plain list of [x, y] points in pitch units.
            starts: Number of thread starts.
            left_handed: True for left-handed threads.
            fn: Number of fragments (circle resolution).
            fa: Minimum fragment angle.
            fs: Minimum fragment size.

        Returns:
            None

        """
        if not (pitch > 0):
            raise Bosl2ValueError("ThreadedRod: d, l and pitch must be positive.")
        if not (l > 0):
            raise Bosl2ValueError("ThreadedRod: d, l and pitch must be positive.")
        if not (d > 0):
            raise Bosl2ValueError("ThreadedRod: d, l and pitch must be positive.")
        self._d: float = d
        self._l: float = l
        self._pitch: float = pitch
        self._profile: list[list[float]] | ThreadProfile = profile
        self._starts: int = starts
        self._left_handed: bool = left_handed
        self._fn: int | None = fn
        self._fa: float | None = fa
        self._fs: float | None = fs
        self._solid: "Solid | None" = None

    @property
    def diameter(self) -> float:
        """Nominal outer diameter in mm."""
        return self._d

    @property
    def length(self) -> float:
        """Length in mm."""
        return self._l

    @property
    def pitch(self) -> float:
        """Thread pitch in mm."""
        return self._pitch

    @property
    def starts(self) -> int:
        """Number of thread starts."""
        return self._starts

    @property
    def left_handed(self) -> bool:
        """True for left-handed threads."""
        return self._left_handed

    @property
    @csg_part("builds its thread surface as a VNF grid, and a non-convex mesh has no distance-field form")
    def shape(self) -> "Solid":
        """Build and return the threaded rod geometry (cached)."""
        if self._solid is not None:
            return self._solid
        self._solid = _rod_solid(
            self._d,
            self._l,
            self._pitch,
            self._profile,
            self._starts,
            self._left_handed,
            self._fn,
            self._fa,
            self._fs,
        )
        return self._solid


class ThreadedNut(Buildable):
    """A nut: a hex or square body with a threaded hole cut by a matching thread tap.

    Examples:
        An M8 nut for an M8×1.25 rod:

        .. pythonscad-example::

            from pybosl2.parts.threading import ThreadedNut, iso_threaded_nut
            iso_threaded_nut(nutwidth=13, id=8, h=6.8, pitch=1.25).show()

    """

    def __init__(
        self,
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
    ) -> None:
        """Create a threaded nut from *profile* (a :class:`ThreadProfile` or point list).

        Args:
            nutwidth: Across-flats width in mm.
            id: Inner (threaded) diameter in mm.
            h: Nut thickness in mm.
            pitch: Thread pitch in mm.
            profile: A :class:`ThreadProfile` or a plain list of [x, y] points in pitch units.
            shape: Nut outer shape (hex or square).
            starts: Number of thread starts.
            left_handed: True for left-handed threads.
            slop: Extra clearance added to the thread diameter.
            fn: Number of fragments (circle resolution).
            fa: Minimum fragment angle.
            fs: Minimum fragment size.

        Returns:
            None

        """
        self._nutwidth: float = nutwidth
        self._id: float = id
        self._h: float = h
        self._pitch: float = pitch
        self._profile: list[list[float]] | ThreadProfile = profile
        self._shape: NutShape = shape
        self._starts: int = starts
        self._left_handed: bool = left_handed
        self._slop: float = slop
        self._fn: int | None = fn
        self._fa: float | None = fa
        self._fs: float | None = fs
        self._solid: "Solid | None" = None

    @property
    def nutwidth(self) -> float:
        """Across-flats width in mm."""
        return self._nutwidth

    @property
    def inner_diameter(self) -> float:
        """Inner (threaded) diameter in mm."""
        return self._id

    @property
    def height(self) -> float:
        """Nut thickness in mm."""
        return self._h

    @property
    def pitch(self) -> float:
        """Thread pitch in mm."""
        return self._pitch

    @property
    def nut_shape(self) -> NutShape:
        """Nut outer shape."""
        return self._shape

    @property
    def starts(self) -> int:
        """Number of thread starts."""
        return self._starts

    @property
    def left_handed(self) -> bool:
        """True for left-handed threads."""
        return self._left_handed

    @property
    @csg_part("builds its thread surface as a VNF grid, and a non-convex mesh has no distance-field form")
    def shape(self) -> "Solid":
        """Build and return the nut geometry (cached)."""
        if self._solid is not None:
            return self._solid
        self._solid = _nut_solid(
            self._nutwidth,
            self._id,
            self._h,
            self._pitch,
            self._profile,
            self._shape,
            self._starts,
            self._left_handed,
            self._slop,
            self._fn,
            self._fa,
            self._fs,
        )
        return self._solid


class ThreadHelix(Buildable):
    """A single helical thread ridge, for adding threads onto your own cylinder.

    The thread crest is at diameter *d*; give *thread_depth* and *flank_angle*,
    or an explicit *profile*. Built entirely through spiral_sweep (VNF output),
    so it does not accept fn/fa/fs smoothing parameters.

    Examples:
        A trapezoidal thread helix around a cylinder:

        .. pythonscad-example::

            from pybosl2.shapes3d import cylinder as cyl
            from pybosl2.parts.threading import ThreadHelix
            (cyl(diameter=20, height=30) | ThreadHelix(d=20, pitch=5, turns=6).shape).show()

    """

    def __init__(
        self,
        d: float,
        pitch: float,
        thread_depth: float | None = None,
        flank_angle: float = 15,
        turns: float = 1,
        starts: int = 1,
        left_handed: bool = False,
        profile: list[list[float]] | ThreadProfile | None = None,
    ) -> None:
        """Create a single thread helix ridge for adding threads to your own cylinder.

        Args:
            d: Crest diameter in mm.
            pitch: Thread pitch in mm.
            thread_depth: Thread depth in mm, or None for pitch/2.
            flank_angle: Flank angle in degrees (half of thread angle for
                trapezoidal, ignored if *profile* is given).
            turns: Number of turns.
            starts: Number of thread starts.
            left_handed: True for left-handed threads.
            profile: Explicit :class:`ThreadProfile` or point list; if given,
                overrides *thread_depth* and *flank_angle*.

        Returns:
            None

        """
        if not (pitch > 0):
            raise Bosl2ValueError("ThreadHelix: d and pitch must be positive.")
        if not (d > 0):
            raise Bosl2ValueError("ThreadHelix: d and pitch must be positive.")
        self._d: float = d
        self._pitch: float = pitch
        self._turns: float = turns
        self._starts: int = starts
        self._left_handed: bool = left_handed
        # The five dimensions above are all a caller needs to *measure* this helix; the sweep
        # below is deferred to `shape` (SPEC C-14, PLAN O-2).
        self._args = (d, pitch, thread_depth, flank_angle, turns, starts, left_handed, profile)
        self._shape: "Solid | None" = None

    def _build(self) -> "Solid":
        """Build the geometry. Called once, on the first access to `shape`."""
        from pybosl2.path2d import Path2D

        (d, pitch, thread_depth, flank_angle, turns, starts, left_handed, profile) = self._args

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
        thread: "Solid | None" = None
        for k in range(starts):
            sec = [[x, y + k * pitch] for x, y in section]
            swept = Path2D(sec).spiral_sweep(
                height=height,
                radius=radius,
                turns=turns * (-1 if left_handed else 1),
                center=True,
            )
            # The CSG sweep hands back a VNF to be built; the SDF one is already a solid.
            piece = swept.polyhedron() if isinstance(swept, VNF) else swept
            if starts > 1:
                piece = piece.rotate([0, 0, k * 360 / starts])
            thread = piece if thread is None else (thread | piece)
        assert thread is not None
        return thread

    @property
    def diameter(self) -> float:
        """Crest diameter in mm."""
        return self._d

    @property
    def pitch(self) -> float:
        """Thread pitch in mm."""
        return self._pitch

    @property
    def turns(self) -> float:
        """Number of turns."""
        return self._turns

    @property
    def starts(self) -> int:
        """Number of thread starts."""
        return self._starts

    @property
    def left_handed(self) -> bool:
        """True for left-handed threads."""
        return self._left_handed

    @property
    def shape(self) -> "Solid":
        """Return the helix geometry."""
        if self._shape is None:
            self._shape = self._build()
        return self._shape


# -- convenience constructors for standard thread profiles --------------------


def iso_threaded_rod(
    d: float,
    l: float,  # noqa: E741
    pitch: float,
    starts: int = 1,
    left_handed: bool = False,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> ThreadedRod:
    """Return an ISO (metric) / UTS (imperial) 60-degree triangular threaded rod.

    Args:
        d: Nominal outer diameter in mm.
        l: Length in mm.
        pitch: Thread pitch in mm.
        starts: Number of thread starts.
        left_handed: True for left-handed threads.
        fn: Number of fragments (circle resolution).
        fa: Minimum fragment angle.
        fs: Minimum fragment size.

    Returns:
        A :class:`ThreadedRod` with an ISO/UTS thread profile.

    """
    return ThreadedRod(d, l, pitch, _iso_profile(), starts, left_handed, fn, fa, fs)


def iso_threaded_nut(
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
) -> ThreadedNut:
    """Return a hex/square nut for an ISO/UTS threaded rod.

    Args:
        nutwidth: Across-flats width in mm.
        id: Inner (threaded) diameter in mm.
        h: Nut thickness in mm.
        pitch: Thread pitch in mm.
        shape: Nut outer shape (hex or square).
        starts: Number of thread starts.
        left_handed: True for left-handed threads.
        slop: Extra clearance added to the thread diameter.
        fn: Number of fragments (circle resolution).
        fa: Minimum fragment angle.
        fs: Minimum fragment size.

    Returns:
        A :class:`ThreadedNut` with an ISO/UTS thread profile.

    """
    return ThreadedNut(
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
) -> ThreadedRod:
    """Return a symmetric trapezoidal (metric trapezoidal by default) threaded rod.

    Args:
        d: Nominal outer diameter in mm.
        l: Length in mm.
        pitch: Thread pitch in mm.
        thread_angle: Total thread angle in degrees.
        thread_depth: Thread depth in mm, or None for pitch/2.
        starts: Number of thread starts.
        left_handed: True for left-handed threads.
        fn: Number of fragments (circle resolution).
        fa: Minimum fragment angle.
        fs: Minimum fragment size.

    Returns:
        A :class:`ThreadedRod` with a trapezoidal thread profile.

    """
    return ThreadedRod(
        d,
        l,
        pitch,
        _trapezoidal_profile(pitch, thread_angle, thread_depth),
        starts,
        left_handed,
        fn,
        fa,
        fs,
    )


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
) -> ThreadedNut:
    """Return a nut for a trapezoidal threaded rod.

    Args:
        nutwidth: Across-flats width in mm.
        id: Inner (threaded) diameter in mm.
        h: Nut thickness in mm.
        pitch: Thread pitch in mm.
        thread_angle: Total thread angle in degrees.
        thread_depth: Thread depth in mm, or None for pitch/2.
        shape: Nut outer shape (hex or square).
        starts: Number of thread starts.
        left_handed: True for left-handed threads.
        slop: Extra clearance added to the thread diameter.
        fn: Number of fragments (circle resolution).
        fa: Minimum fragment angle.
        fs: Minimum fragment size.

    Returns:
        A :class:`ThreadedNut` with a trapezoidal thread profile.

    """
    return ThreadedNut(
        nutwidth,
        id,
        h,
        pitch,
        _trapezoidal_profile(pitch, thread_angle, thread_depth),
        shape,
        starts,
        left_handed,
        slop,
        fn,
        fa,
        fs,
    )


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
) -> ThreadedRod:
    """Return a 29-degree ACME threaded rod.

    Args:
        d: Nominal outer diameter in mm.
        l: Length in mm.
        pitch: Thread pitch in mm.
        thread_depth: Thread depth in mm, or None for pitch/2.
        starts: Number of thread starts.
        left_handed: True for left-handed threads.
        fn: Number of fragments (circle resolution).
        fa: Minimum fragment angle.
        fs: Minimum fragment size.

    Returns:
        A :class:`ThreadedRod` with a 29-degree ACME thread profile.

    """
    depth = thread_depth if thread_depth is not None else pitch / 2
    return ThreadedRod(
        d,
        l,
        pitch,
        _trapezoidal_profile(pitch, 29, depth),
        starts,
        left_handed,
        fn,
        fa,
        fs,
    )


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
) -> ThreadedNut:
    """Return a nut for an ACME threaded rod.

    Args:
        nutwidth: Across-flats width in mm.
        id: Inner (threaded) diameter in mm.
        h: Nut thickness in mm.
        pitch: Thread pitch in mm.
        thread_depth: Thread depth in mm, or None for pitch/2.
        shape: Nut outer shape (hex or square).
        starts: Number of thread starts.
        left_handed: True for left-handed threads.
        slop: Extra clearance added to the thread diameter.
        fn: Number of fragments (circle resolution).
        fa: Minimum fragment angle.
        fs: Minimum fragment size.

    Returns:
        A :class:`ThreadedNut` with an ACME thread profile.

    """
    depth = thread_depth if thread_depth is not None else pitch / 2
    return ThreadedNut(
        nutwidth,
        id,
        h,
        pitch,
        _trapezoidal_profile(pitch, 29, depth),
        shape,
        starts,
        left_handed,
        slop,
        fn,
        fa,
        fs,
    )


def square_threaded_rod(
    d: float,
    l: float,  # noqa: E741
    pitch: float,
    starts: int = 1,
    left_handed: bool = False,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> ThreadedRod:
    """Return a square-profile threaded rod.

    Args:
        d: Nominal outer diameter in mm.
        l: Length in mm.
        pitch: Thread pitch in mm.
        starts: Number of thread starts.
        left_handed: True for left-handed threads.
        fn: Number of fragments (circle resolution).
        fa: Minimum fragment angle.
        fs: Minimum fragment size.

    Returns:
        A :class:`ThreadedRod` with a square thread profile.

    """
    return ThreadedRod(d, l, pitch, _trapezoidal_profile(pitch, 0.1), starts, left_handed, fn, fa, fs)


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
) -> ThreadedNut:
    """Return a nut for a square threaded rod.

    Args:
        nutwidth: Across-flats width in mm.
        id: Inner (threaded) diameter in mm.
        h: Nut thickness in mm.
        pitch: Thread pitch in mm.
        shape: Nut outer shape (hex or square).
        starts: Number of thread starts.
        left_handed: True for left-handed threads.
        slop: Extra clearance added to the thread diameter.
        fn: Number of fragments (circle resolution).
        fa: Minimum fragment angle.
        fs: Minimum fragment size.

    Returns:
        A :class:`ThreadedNut` with a square thread profile.

    """
    return ThreadedNut(
        nutwidth,
        id,
        h,
        pitch,
        _trapezoidal_profile(pitch, 0.1),
        shape,
        starts,
        left_handed,
        slop,
        fn,
        fa,
        fs,
    )


def buttress_threaded_rod(
    d: float,
    l: float,  # noqa: E741
    pitch: float,
    starts: int = 1,
    left_handed: bool = False,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
) -> ThreadedRod:
    """Return an asymmetric buttress threaded rod.

    Args:
        d: Nominal outer diameter in mm.
        l: Length in mm.
        pitch: Thread pitch in mm.
        starts: Number of thread starts.
        left_handed: True for left-handed threads.
        fn: Number of fragments (circle resolution).
        fa: Minimum fragment angle.
        fs: Minimum fragment size.

    Returns:
        A :class:`ThreadedRod` with a buttress thread profile.

    """
    return ThreadedRod(d, l, pitch, _buttress_profile(), starts, left_handed, fn, fa, fs)


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
) -> ThreadedNut:
    """Return a nut for a buttress threaded rod.

    Args:
        nutwidth: Across-flats width in mm.
        id: Inner (threaded) diameter in mm.
        h: Nut thickness in mm.
        pitch: Thread pitch in mm.
        shape: Nut outer shape (hex or square).
        starts: Number of thread starts.
        left_handed: True for left-handed threads.
        slop: Extra clearance added to the thread diameter.
        fn: Number of fragments (circle resolution).
        fa: Minimum fragment angle.
        fs: Minimum fragment size.

    Returns:
        A :class:`ThreadedNut` with a buttress thread profile.

    """
    return ThreadedNut(
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

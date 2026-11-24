# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for pybosl2.bottlecaps: the PCO-1810 / PCO-1881 bottle necks and caps.

Each builder is checked for the right overall envelope (width and height) against the transcribed
BOSL2 dimensions, and that it returns a Bosl2Solid.

**The envelope is not the bottle.** Every test here was an envelope test, and a neck's envelope is
set by its support ring (33 mm) -- 5.6 mm wider than the thread crest it is supposed to have. So
both necks were built with **no threads at all** (T122): `ThreadHelix` grew its ridge inward from
the diameter it was given, which put the whole thread inside the neck wall, where the union with
the neck body swallowed it. The outer diameter of the PCO-1810 thread was 24.41 mm where the spec
says 27.43, both necks passed every test in this file, and the two thread breaks -- prismoid cuts
aimed at `threadbase_d/2` -- removed nothing, because the ridge they were aimed at was inside
them. The thread tests below measure the radii the mesh occupies, which is the only thing that
distinguishes a threaded neck from a smooth one.
"""

import math

import numpy as np
import pytest

from pybosl2.parts.bottlecaps import _PCO1810, _PCO1881, BottleCaps, BottleThreadSpec, _neck_thread
from pybosl2.parts.threading import ThreadHelix
from pybosl2.shapes3d import Bosl2Solid


def _size(solid: Bosl2Solid) -> list[float]:
    """Overall (width_x, width_y, height_z) of a solid's real mesh."""
    _min, size = solid._native_bounds()  # type: ignore[misc]
    return size


def test_pco1810_neck_envelope() -> None:
    neck = BottleCaps.pco1810_neck(fn=None, fa=None, fs=None)
    assert isinstance(neck, Bosl2Solid)
    w, _wy, hgt = _size(neck)
    assert w == pytest.approx(33.0, abs=0.2)  # support ring diameter
    assert hgt == pytest.approx(21.0 + 5.0, abs=0.2)  # support_h + neck_h


def test_pco1881_neck_envelope() -> None:
    neck = BottleCaps.pco1881_neck(fn=None, fa=None, fs=None)
    assert isinstance(neck, Bosl2Solid)
    w, _wy, hgt = _size(neck)
    assert w == pytest.approx(33.0, abs=0.2)
    assert hgt == pytest.approx(17.0 + 5.0, abs=0.2)


def test_pco1810_cap_envelope() -> None:
    cap = BottleCaps.pco1810_cap(wall=2, fn=None, fa=None, fs=None)
    assert isinstance(cap, Bosl2Solid)
    w, _wy, hgt = _size(cap)
    assert w == pytest.approx(28.58 + 2 * 2, abs=0.3)  # cap_id + 2*wall
    assert hgt == pytest.approx(14.10 + 2, abs=0.3)  # tamper_ring_h + wall


def test_pco1881_cap_envelope() -> None:
    cap = BottleCaps.pco1881_cap(wall=2, fn=None, fa=None, fs=None)
    assert isinstance(cap, Bosl2Solid)
    w, _wy, hgt = _size(cap)
    assert w == pytest.approx(28.58 + 2 * 2, abs=0.3)
    assert hgt == pytest.approx(11.20 + 2, abs=0.3)


def test_wall_thickness_changes_cap_size() -> None:
    thin = BottleCaps.pco1881_cap(wall=1, fn=None, fa=None, fs=None)
    thick = BottleCaps.pco1881_cap(wall=3, fn=None, fa=None, fs=None)
    assert _size(thick)[0] > _size(thin)[0]
    assert _size(thick)[2] > _size(thin)[2]


@pytest.mark.parametrize("texture", ["ribs", "checkers"])
def test_a_named_texture_is_cut_into_the_cap(texture: str) -> None:
    """The cap's grip is real geometry now (T39, SPEC S-35).

    This test used to assert the opposite -- that a textured cap *is* the plain one, because the
    port could not apply a texture. It was right to assert it rather than merely check the builder
    succeeded, and right to say so out loud: a documented fallback is still a silent no-op at the
    call site, which is what E-5 forbids and S-35 exists to prevent.
    """
    plain = BottleCaps.pco1881_cap(texture="none", fn=None, fa=None, fs=None)
    textured = BottleCaps.pco1881_cap(texture=texture, fn=None, fa=None, fs=None)
    assert _size(textured)[0] == pytest.approx(_size(plain)[0], abs=0.1), "the knurl is cut in, not grown on"
    assert textured.vnf().volume() < plain.vnf().volume(), "and it removes material"


def test_an_unknown_texture_names_the_ones_that_exist() -> None:
    """SPEC E-4: the refusal names the accepted spellings rather than falling back silently."""
    from pybosl2.exceptions import Bosl2ValueError

    with pytest.raises(Bosl2ValueError, match="available"):
        BottleCaps.pco1881_cap(texture="knurled", fn=None, fa=None, fs=None)


def test_neck_and_cap_are_distinct_pieces() -> None:
    # Sanity: a cap is wider than tall here, a neck taller than the cap.
    neck_h = _size(BottleCaps.pco1810_neck(fn=None, fa=None, fs=None))[2]
    cap_h = _size(BottleCaps.pco1810_cap(fn=None, fa=None, fs=None))[2]
    assert neck_h > cap_h


# --- where the threads are (T122) ---------------------------------------------------------------

#: The four angles the neck's two thread breaks land on: `zrot_copies(rots=[90, 270])` composed
#: with `zrot_copies(rots=[-28, 28], radius=threadbase_d/2)`.
BREAK_ANGLES = (62.0, 118.0, 242.0, 298.0)


def _radii(solid: Bosl2Solid) -> np.ndarray:
    """Distance from the Z axis of every vertex of *solid*'s mesh."""
    points = np.asarray(solid.vnf().vertices, dtype=float)
    return np.hypot(points[:, 0], points[:, 1])


@pytest.mark.parametrize(("name", "spec"), [("PCO-1810", _PCO1810), ("PCO-1881", _PCO1881)])
def test_the_neck_thread_reaches_the_diameter_the_spec_gives_it(name: str, spec: BottleThreadSpec) -> None:
    """SPEC B2-1: `thread_od` is the diameter the neck's threads reach, within BOSL2's own fudge.

    BOSL2 builds this ridge as `thread_helix(d=threadbase_d-0.1, thread_depth=thread_h+0.1)` with
    `thread_h = (thread_od - threadbase_d)/2`, so it stands on `threadbase_d - 0.1` and reaches
    `thread_od + 0.1`. Built inward instead, it reached `threadbase_d - 0.1` at its widest --
    3.02 mm short on PCO-1810 -- and vanished into the neck wall.
    """
    radius = _radii(_neck_thread(spec))
    assert float(radius.min()) == pytest.approx(spec.threadbase_d / 2 - 0.05, abs=0.01), (
        "the ridge does not stand on the thread base diameter"
    )
    assert float(radius.max()) == pytest.approx(spec.thread_od / 2 + 0.05, abs=0.01), (
        f"{name}: the threads reach {2 * float(radius.max()):.2f} mm, not thread_od = {spec.thread_od}"
    )


@pytest.mark.parametrize("angle", BREAK_ANGLES)
def test_each_thread_break_actually_breaks_the_thread(angle: float) -> None:
    """A cut aimed past the far side of the ridge is a boolean that returns a solid and does nothing.

    The uncut ridge has crest vertices at each break angle and the cut one has none. Vertex counts
    alone would not show this: the boolean *adds* 118 vertices along the faces it opens, so the
    ridge got bigger while losing the four pieces this asserts are gone.
    """
    spec = _PCO1810
    thread_h = (spec.thread_od - spec.threadbase_d) / 2
    uncut = ThreadHelix(
        d=spec.threadbase_d - 0.1,
        pitch=spec.thread_pitch,
        thread_depth=thread_h + 0.1,
        flank_angle=spec.flank_angle,
        turns=spec.neck_turns / 360,
    ).shape
    crest = spec.threadbase_d / 2 + thread_h * 0.5

    def crest_vertices_near(solid: Bosl2Solid) -> int:
        points = np.asarray(solid.vnf().vertices, dtype=float)
        radius = np.hypot(points[:, 0], points[:, 1])
        bearing = np.degrees(np.arctan2(points[:, 1], points[:, 0])) % 360.0
        close = np.abs((bearing - angle + 180.0) % 360.0 - 180.0) < 4.0
        return int(((radius > crest) & close).sum())

    assert crest_vertices_near(uncut) > 0, f"nothing to break at {angle} deg -- the fixture is wrong"
    assert crest_vertices_near(_neck_thread(spec)) == 0, f"the break at {angle} deg cut nothing"


@pytest.mark.parametrize(("name", "spec"), [("PCO-1810", _PCO1810), ("PCO-1881", _PCO1881)])
def test_the_cap_thread_meets_its_own_bore_and_its_own_neck(name: str, spec: BottleThreadSpec) -> None:
    """A cap's internal thread has two jobs, and each one is a diameter it has to reach.

    Its root has to reach the cap's bore, or the ridge is a ring floating in mid-air inside the
    cap; its crest has to come inside the neck's thread crest, or the cap screws onto nothing.
    PCO-1881 failed both: upstream passes `thread_helix(d=25.5)` directly, and this port treated
    25.5 as an outer diameter and subtracted twice the depth from it, putting that cap's thread
    3.2 mm too small -- crest at 22.3, root 1.54 mm clear of the bore.
    """
    ridge = ThreadHelix(
        d=spec.cap_thread_base_d,
        pitch=spec.cap_thread_pitch,
        thread_depth=spec.cap_thread_depth,
        flank_angle=spec.cap_flank_angle,
        turns=spec.cap_turns / 360,
    ).shape
    radius = _radii(ridge)
    assert float(radius.max()) >= spec.cap_id / 2 - 1e-9, (
        f"{name}: the thread's root is at {2 * float(radius.max()):.2f} mm and the bore is "
        f"{spec.cap_id} mm, so the ridge is not attached to the cap wall"
    )
    assert float(radius.min()) < spec.thread_od / 2, (
        f"{name}: the thread's crest clears the neck's at {spec.thread_od} mm -- the cap cannot engage"
    )
    assert float(radius.min()) == pytest.approx(spec.cap_thread_base_d / 2, abs=1e-6)


def test_the_two_variants_do_not_share_a_cap_thread_diameter() -> None:
    """The two numbers came from differently-spelled upstream lines; one field held both.

    `cap_thread_od` was 28.58 for PCO-1810 (its upstream local `thread_od`, equal to the bore) and
    25.5 for PCO-1881 (its upstream *literal* `d=`), and one conversion was applied to both. The
    field is the helix diameter now, so each variant carries what upstream passes.
    """
    assert _PCO1810.cap_thread_base_d == pytest.approx(_PCO1810.cap_id - 2 * _PCO1810.cap_thread_depth)
    assert _PCO1881.cap_thread_base_d == pytest.approx(25.5)
    assert not math.isclose(_PCO1881.cap_thread_base_d, _PCO1881.cap_id - 2 * _PCO1881.cap_thread_depth)

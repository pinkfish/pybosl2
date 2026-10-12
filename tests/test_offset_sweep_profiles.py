# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""Each `os_*` end treatment builds its own shape, and the teardrop caps its overhang.

SPEC G-8, S-2b. `offset_sweep` picks an end treatment from six `OSType` members, each with a public
`os_*` factory. T98 swept every behaviour-selecting enum for members sharing behaviour and reported
`OSType` as having **no public dispatch site** -- because it looked for the enum in a signature, and
`OSType` reaches `offset_sweep` inside an `OSProfile` descriptor. A scope hole in that sweep, found
by asking the same question of the one enum it had skipped.

The gap it was hiding: **making `os_teardrop` compute `os_circle`'s arc leaves the whole suite
green** -- 481 passed, identical volume. The existing tests check the descriptor's fields
(`d["type"] == "circle"`, `d["r"] == 3.0`) and that the swept solid has `volume() > 0` and
`volume() < plain`, all of which any treatment satisfies. Disabling the branch outright *is* caught,
because it falls through to no treatment at all and the volume stops shrinking; silently becoming a
different treatment is not.

That matters more here than it would for a tessellation choice. `os_teardrop` exists for one
reason: an FDM printer cannot bridge a surface that leans too far from vertical, so the treatment
replaces the end of the arc with a straight run at `max_angle`. A teardrop that had quietly become
a circle would leave an **87 degree** underside where 45 was asked for -- a part that does not
print, reported by nothing. The same defect class as T62's inverted `effective_clip` and T90's
`Mask2D.tear`.

Measured on the underside, because that is the end a teardrop is for: a top treatment leans the
same way whatever it is, and measuring there put teardrop and chamfer at an identical 86.19 degrees
and proved nothing.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

import pybosl2.skin as skin
from pybosl2 import use_defaults
from pybosl2.path2d import Path2D

FACETS = 64
HEIGHT = 20.0
RADIUS = 3.0

#: A square, so each z level has a single outermost x and the profile reads straight off the mesh.
SQUARE = Path2D([[-10.0, -10.0], [10.0, -10.0], [10.0, 10.0], [-10.0, 10.0]], closed=True)

#: `name -> factory`. `os_flat` takes no size: it is the "no treatment" member, and it belongs in
#: the distinctness check precisely because every other member must differ from doing nothing.
PROFILES = {
    "chamfer": lambda: skin.os_chamfer(width=RADIUS),
    "circle": lambda: skin.os_circle(radius=RADIUS),
    "flat": lambda: skin.os_flat(),
    "profile": lambda: skin.os_profile(profile=Path2D([[0.0, 0.0], [3.0, 1.5], [3.0, 3.0]])),
    "smooth": lambda: skin.os_smooth(cut=RADIUS),
    "teardrop": lambda: skin.os_teardrop(radius=RADIUS),
}


def _swept(end: str, profile: object) -> object:
    with use_defaults(fn=FACETS):
        return SQUARE.offset_sweep(height=HEIGHT, **{end: profile}).vnf()  # type: ignore[arg-type]


def _shape(name: str) -> tuple[float, tuple[float, ...]]:
    """Volume and the sorted vertex positions -- not volume alone, which hides a reshaping."""
    mesh = _swept("top", PROFILES[name]())
    points = np.asarray([[float(c) for c in p] for p in mesh.vertices], dtype=float)  # type: ignore[attr-defined]
    return (
        round(float(mesh.volume()), 4),  # type: ignore[attr-defined]
        tuple(np.round(np.sort(points, axis=0).ravel(), 4)),
    )


def _underside_lean(profile: object) -> float:
    """The steepest angle from vertical on the bottom treatment, in degrees.

    The bottom band is where an overhang is unprintable, and it is the only end that tells the
    treatments apart: read off the top, a teardrop and a chamfer both measure 86.19 degrees.
    """
    mesh = _swept("bottom", profile)
    points = np.asarray([[float(c) for c in p] for p in mesh.vertices], dtype=float)  # type: ignore[attr-defined]
    outermost: dict[float, float] = {}
    for x, _y, z in points:
        level = round(float(z), 4)
        outermost[level] = max(outermost.get(level, -1e9), float(x))
    levels = sorted(z for z in outermost if z < HEIGHT / 4)
    return max(
        math.degrees(math.atan2(abs(outermost[b] - outermost[a]), abs(b - a)))
        for a, b in zip(levels, levels[1:], strict=False)
    )


@pytest.mark.parametrize(("first", "second"), sorted(itertools.combinations(sorted(PROFILES), 2)))
def test_no_two_end_treatments_build_the_same_solid(first: str, second: str) -> None:
    """SPEC G-8: a treatment that fell through to another would pass that other's tests."""
    assert _shape(first) != _shape(second), (
        f"os_{first} and os_{second} sweep to the same solid. Every existing assertion on these is "
        f"either about the descriptor's fields or that the volume shrank, and both survive it"
    )


@pytest.mark.parametrize("max_angle", [20.0, 30.0, 45.0, 60.0])
def test_a_teardrop_caps_the_underside_overhang_at_its_angle(max_angle: float) -> None:
    """SPEC S-2b: the angle is a promise about printability, so measure the overhang.

    Several values, not just the default: 45 is `os_teardrop`'s own default *and* `os_chamfer`'s
    natural bevel, so a single reading at 45 cannot tell a working cap from a coincidence.
    """
    measured = _underside_lean(skin.os_teardrop(radius=RADIUS, max_angle=max_angle))
    assert measured == pytest.approx(max_angle, abs=0.5), (
        f"os_teardrop(max_angle={max_angle}) leaves a {measured:.2f} degree underside. The angle is "
        f"the whole reason the treatment exists -- an FDM printer cannot bridge past it"
    )


def test_a_circle_leaves_the_overhang_a_teardrop_removes() -> None:
    """The contrast that makes the test above mean something.

    Without it, a teardrop capping at 45 would be unremarkable -- it has to be capping something.
    A circular rounding of the same radius leaves 87 degrees, which is why the teardrop exists.
    """
    circular = _underside_lean(skin.os_circle(radius=RADIUS))
    teardrop = _underside_lean(skin.os_teardrop(radius=RADIUS))
    assert circular > 80.0, (
        f"a circular bottom rounding now leans only {circular:.2f} degrees from vertical, so it no "
        f"longer poses the overhang problem the teardrop solves and this comparison is moot"
    )
    assert teardrop < circular - 30.0, (
        f"the teardrop leans {teardrop:.2f} degrees and the circle {circular:.2f}; the teardrop is "
        f"not removing the overhang"
    )

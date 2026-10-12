# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""A sweep builds, or refuses by name -- it never hands back NaN (SPEC E-1, E-4).

T100 measured two gaps in `path_sweep(tangent=)` and left them named. Fixing them found a third,
and the third is the one that matters:

====================================  =============================================
input                                 before
====================================  =============================================
``tangent=`` shorter than the path    raw ``IndexError`` naming a numpy axis
``tangent=`` uniform, right length    raw ``ZeroDivisionError``
a path with a **repeated point**      **built a solid with ``[nan, nan, nan]`` bounds**
====================================  =============================================

The first two are rude. The third is silent: the sweep *returned*, so nothing raised, nothing
warned, and a caller got a solid that measures as nothing. That is the `arcxrot` failure of T94
in a different file -- which is why this guard asserts the bounds are finite as well as asking
what was raised. A test that only checks for an exception passes all three rows above.

Each cause is arithmetic on a vector that has no length:

* `% npts` makes a short `tangent=` index legal, so the error surfaced inside numpy rather than at
  the call that was wrong;
* `v2 @ v2` is zero exactly when the reflected tangent already *is* the next tangent, so the second
  reflection of the double-reflection frame is the identity -- a degenerate case of the algorithm,
  not a bad input, and uniform tangents are the obvious thing to pass (a 2-D tangent becomes one
  once padded to three components);
* `v1 @ v1` is zero when two path points coincide, and that one propagates `NaN` instead of raising
  because numpy divides a float array by zero rather than refusing.

The repeated point is **refused, not deduplicated**. `Path3D.deduplicate()` exists and the refusal
names it -- but dropping a point renumbers the path, and `tangent=` and the per-point forms of
`scale=` and `normal=` are matched against that numbering, so a silent dedup would turn a correct
call into a length mismatch or apply the wrong value at every point after the duplicate.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from pybosl2 import use_backend
from pybosl2.exceptions import Bosl2Error
from pybosl2.path3d import Path3D

PROFILE = [[math.cos(2 * math.pi * k / 12), math.sin(2 * math.pi * k / 12)] for k in range(12)]

#: Routes chosen for the arithmetic they make degenerate rather than for looking odd: collinear
#: runs, a reversal, a segment short enough to lose precision, and a climb with no x or y component.
ROUTES = {
    "straight": [[0.0, 0.0, 0.0], [20.0, 0.0, 0.0]],
    "collinear": [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [20.0, 0.0, 0.0]],
    "doubling back": [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [0.0, 0.0, 0.001]],
    "exact reversal": [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
    "near-coincident": [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0000001, 0.0, 0.0], [20.0, 0.0, 0.0]],
    # The exact duplicate belongs in the general check as well as in its own test below.
    # Without it, removing the repeated-point guard failed only the test that names the
    # refusal, while the assertion that no sweep returns NaN -- the general form, and the one
    # that would have caught this class before anyone knew to look -- stayed green.
    "repeated point": [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 0.0, 0.0], [20.0, 0.0, 0.0]],
    "right angle": [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 10.0, 0.0]],
    "vertical": [[0.0, 0.0, 0.0], [0.0, 0.0, 20.0]],
}


@pytest.mark.parametrize("name", sorted(ROUTES))
def test_a_degenerate_route_builds_finitely_or_refuses(name: str) -> None:
    """SPEC E-1: every answer is a solid that measures, or a `Bosl2Error`. Never NaN."""
    route = Path3D(ROUTES[name], closed=False)
    try:
        with use_backend("csg"):
            swept = route.path_sweep(PROFILE)
    except Bosl2Error:
        return  # refusing a degenerate route is a perfectly good answer
    size = [float(v) for v in swept.bounds().size]
    assert all(np.isfinite(size)), (
        f"the {name} route swept to a solid measuring {size}. It returned normally, so nothing "
        f"raised and nothing warned -- a test that only checks for an exception sees this as a pass"
    )
    assert min(size) > 0.0, f"the {name} route swept to an empty solid: {size}"


def test_a_repeated_path_point_refuses_and_names_the_fix() -> None:
    """SPEC E-2: the refusal says which point and what to call."""
    route = Path3D([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 0.0, 0.0], [20.0, 0.0, 0.0]], closed=False)
    with use_backend("csg"), pytest.raises(Bosl2Error) as caught:
        route.path_sweep(PROFILE)
    message = str(caught.value)
    assert "index 1" in message, "the refusal must say which point repeats"
    assert "deduplicate" in message, "and name the call that fixes it (SPEC E-2)"


def test_the_named_fix_gives_the_answer_the_clean_path_gives() -> None:
    """A refusal that names a remedy is only honest if the remedy works.

    Checked against the hand-written clean path rather than merely for "builds": `deduplicate()`
    has to leave the sweep that the duplicate was obscuring, not some other sweep.
    """
    duplicated = Path3D([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 0.0, 0.0], [20.0, 0.0, 0.0]], closed=False)
    clean = Path3D([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [20.0, 0.0, 0.0]], closed=False)
    with use_backend("csg"):
        fixed = duplicated.deduplicate().path_sweep(PROFILE).bounds()
        expected = clean.path_sweep(PROFILE).bounds()
    assert [float(v) for v in fixed.size] == pytest.approx([float(v) for v in expected.size])
    assert [float(v) for v in fixed.center] == pytest.approx([float(v) for v in expected.center])


@pytest.mark.parametrize(
    ("label", "count"),
    [("empty", 0), ("one for many", 1), ("two short", -2), ("one too many", 1)],
)
def test_a_tangent_list_of_the_wrong_length_refuses_by_name(label: str, count: int) -> None:
    """SPEC E-4: `% npts` made the bad index legal, so numpy raised instead of the library."""
    route = Path3D([[0.0, 0.0, 0.0], [20.0, 0.0, 0.0], [20.0, 20.0, 0.0]], closed=False)
    wanted = len(route) + count if label in ("two short", "one too many") else count
    tangents = [[1.0, 0.0, 0.0]] * max(0, wanted)
    with use_backend("csg"), pytest.raises(Bosl2Error, match="tangent="):
        route.path_sweep(PROFILE, tangent=tangents)


def test_uniform_tangents_sweep_rather_than_dividing_by_zero() -> None:
    """The degenerate second reflection, in the form a caller meets it.

    Forcing one direction at every point is the obvious use of `tangent=`, and it is also exactly
    the case where the double-reflection frame has nothing to rotate.
    """
    route = Path3D([[0.0, 0.0, 0.0], [20.0, 0.0, 0.0], [20.0, 20.0, 0.0]], closed=False)
    with use_backend("csg"):
        swept = route.path_sweep(PROFILE, tangent=[[1.0, 0.0, 0.0]] * len(route))
    size = [float(v) for v in swept.bounds().size]
    assert all(np.isfinite(size)), f"uniform tangents swept to {size}"
    assert min(size) > 0.0, f"uniform tangents swept to an empty solid: {size}"
    # Every frame faces +x, so the profile never turns and its own diameter is the whole z extent.
    assert size[2] == pytest.approx(2.0, abs=0.01), (
        f"the profile rotated despite every tangent pointing the same way: z extent {size[2]}"
    )


#: A bezier path whose junction is C1-continuous: ``p2``, ``p3``, ``p4`` are collinear and evenly
#: spaced, so the two cubic segments meet with the same direction. That matters -- on a path with a
#: genuine kink at the junction the curve's own tangent legitimately differs from the local chord
#: direction by half the corner angle, which would drown the misalignment this measures. The
#: obvious test path is kinked, and measuring it put the "error" at 48 degrees either way.
SMOOTH_BEZPATH = [
    [0.0, 0.0, 0.0],
    [5.0, 0.0, 0.0],
    [10.0, 0.0, 0.0],
    [15.0, 5.0, 0.0],
    [20.0, 10.0, 0.0],
    [25.0, 10.0, 0.0],
    [30.0, 10.0, 0.0],
]


def _worst_tangent_error(splinesteps: int) -> float:
    """The largest angle, in degrees, between a supplied tangent and the path's local direction."""
    import pybosl2.skin as skin
    from pybosl2.beziers import Bezier

    captured: dict[str, np.ndarray] = {}
    original = skin._path_sweep

    def spy(shape: object, path: object, **given: object) -> object:
        captured["path"] = np.asarray([[float(c) for c in p] for p in path], dtype=float)  # type: ignore[union-attr]
        tangent = given.get("tangent")
        captured["tangent"] = np.asarray(
            [[float(c) for c in v] for v in tangent],
            dtype=float,  # type: ignore[union-attr]
        )
        return original(shape, path, **given)  # type: ignore[arg-type]

    skin._path_sweep = spy  # type: ignore[assignment]
    try:
        Bezier(SMOOTH_BEZPATH).sweep(PROFILE, splinesteps=splinesteps, n_degree=3)
    finally:
        skin._path_sweep = original  # type: ignore[assignment]

    path, tangent = captured["path"], captured["tangent"]
    assert len(tangent) == len(path), f"the sweep passed {len(tangent)} tangents for {len(path)} path points"
    chords = np.diff(path, axis=0)
    chords /= np.linalg.norm(chords, axis=1, keepdims=True)
    # The local direction at an interior point is the mean of the two chords meeting there.
    local = chords[:-1] + chords[1:]
    local /= np.linalg.norm(local, axis=1, keepdims=True)
    unit = tangent / np.linalg.norm(tangent, axis=1, keepdims=True)
    cosines = np.einsum("ij,ij->i", unit[1 : len(local) + 1], local)
    return float(np.degrees(np.arccos(np.clip(cosines, -1.0, 1.0))).max())


def test_a_bezier_sweeps_tangents_line_up_with_its_path() -> None:
    """Each supplied tangent belongs to the point it is paired with (SPEC S-19a).

    `Bezier.sweep` builds its tangent list segment by segment, and consecutive segments share a
    junction that `path_curve` emits once. Both copies of the junction tangent were kept, so the
    list ran one long and every tangent after the first junction was paired with the wrong point.

    Asserted by **refinement** rather than against a fixed tolerance: a correctly paired list is
    wrong only by discretisation, so its error halves as the step count doubles, while a list
    shifted by one point stays wrong by about the turn between neighbouring points no matter how
    fine the sampling. Measured here at 3.65, 1.81 and 0.90 degrees -- a clean halving.

    Nothing could have caught it before. `tests/test_stl_render.py::test_sweep` renders this exact
    call and asserts `ntris > 0` and `volume > 0`, both of which a misaligned sweep satisfies.
    """
    errors = [_worst_tangent_error(steps) for steps in (8, 16, 32)]
    for coarse, fine in zip(errors, errors[1:], strict=False):
        assert fine < coarse * 0.7, (
            f"the tangent error does not fall with refinement: {errors}. A correctly paired list is "
            f"wrong only by discretisation and halves; one shifted by a point does not"
        )
    assert errors[-1] < 1.5, f"tangents are still {errors[-1]:.2f} degrees off at 32 steps"

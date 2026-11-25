# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause


"""The `$fn`/`$fa`/`$fs` arithmetic lives in one place, so the ambient defaults reach everything.

PLAN R-P3: *"Resolve them exactly once, at the point of use, through ... `_helpers.frag_count()`
... new leaf constructors SHOULD route through those rather than re-implementing the `$fa`/`$fs`
arithmetic."* The rule names its own failure mode and carried no enforcer.

**Three implementations existed**, and the copies had drifted in the one way that matters.
`frag_count` fills in the ambient `use_defaults(...)` block values before falling back to
OpenSCAD's `$fa=12 / $fs=2`; `Path2D._offset_segs` and `pybosl2.sdf.paths._frag_count` went
straight to the fallbacks. So a block-scoped default was silently ignored on those paths:

=========================  ===========  =========
call                       points
=========================  ===========  =========
``offset(radius=5)`` under ``use_defaults(fn=64)``  **20**
``offset(radius=5, fn=64)`` with no ambient block   **68**
=========================  ===========  =========

The same 64, one of them honoured. Both copies delegate now.

Two checks, because each catches what the other cannot:

* the arithmetic appears in exactly one function -- cheap, exact, and the form R-P3 states;
* the resolvers agree under an ambient block -- which is the behaviour the rule is *for*, and would
  survive someone writing a fourth copy that happened to delegate correctly.

**T130 found the same defect one layer further out**, where the resolved value is handed to the
renderer. The native `rotate_extrude` distinguishes "not given" from `None`, so passing `fn=None`
explicitly is not the same as leaving it out: it overrides rather than defers. Three callers --
`cyl` with a treated rim, `torus`, and `onion` -- forwarded their unresolved
arguments straight through, so an ambient `use_defaults(fn=64)` arrived as `None` and the mesh came
back at the renderer's own `$fa=12`:

=============================================  ============
``cyl(r1=10, r2=4, h=20, rounding=2)``         facets
=============================================  ============
under ``use_defaults(fn=16 / 64 / 128)``       **30 / 30 / 30**
with ``fn=16 / 64 / 128`` passed explicitly    16 / 64 / 128
=============================================  ============

`_ocylinder` and `_osphere` had always resolved first and dropped the `None`s; `rotate_extrude` had
no such wrapper, and now does (`_orevolve`). The arithmetic was never the problem here, which is
why the two checks above could not see it -- R-P3 is about where the rule lives, and this is about
whether its answer survives the last call.

**The sweeping version was measured and rejected.** Asking all 52 public callables that take `fn=`
whether their vertex count responds to `use_defaults(fn=8)` against `use_defaults(fn=64)` leaves 43
unbuildable from generic arguments and reports five false positives -- `cube`, `cuboid`,
`prismoid`, `rect_tube` and `regular_prism` are flat-faced, so `fn` legitimately changes nothing
until a `rounding=` gives them a curve. Given one, every one of them responds. A sweep that needs a
per-shape fixture to avoid false positives is not a sweep (the same verdict T99 reached about its
247-parameter form).
"""

from __future__ import annotations

import ast
import pathlib
import re
from typing import TYPE_CHECKING

import numpy as np
import pytest

from pybosl2 import use_defaults
from pybosl2._helpers import frag_count
from pybosl2.path2d import Path2D
from pybosl2.sdf.paths import _frag_count as sdf_frag_count
from pybosl2.shapes3d import cyl, onion, torus

if TYPE_CHECKING:
    from collections.abc import Callable

ROOT = pathlib.Path(__file__).resolve().parent.parent / "pybosl2"

#: The two halves of OpenSCAD's rule: dividing a full turn by the fragment *angle*, and the
#: `fa if fa else 12.0` style fallback that skips whatever the ambient block set.
_ARITHMETIC = re.compile(r"360(\.0)?\s*/\s*fa|/\s*fs\b")
_OWN_FALLBACK = re.compile(r"\bfa\s*=\s*fa\s+if\s+fa\s+else|\bfs\s*=\s*fs\s+if\s+fs\s+else")

#: The one function allowed to hold it.
CANONICAL = "_helpers.py::frag_count"


#: A profile well clear of the axis, so the revolve is an annulus and every vertex has an angle.
_REVOLVED_PROFILE = Path2D([[4.0, -5.0], [6.0, -5.0], [6.0, 5.0], [4.0, 5.0]], closed=True)


def _facet_count(shape: object) -> int:
    """Distinct angular positions among a solid's mesh vertices -- the revolve's own facet count.

    Args:
        shape: The built solid.

    Returns:
        How many angular steps the revolution was meshed with.

    """
    verts = np.asarray(shape.shape.mesh()[0], dtype=float)  # type: ignore[attr-defined]
    return len(np.unique(np.round(np.degrees(np.arctan2(verts[:, 1], verts[:, 0])), 4)))


def test_the_facet_arithmetic_lives_in_exactly_one_function() -> None:
    """PLAN R-P3: a second copy cannot read the ambient block, and nothing says it should."""
    found = []
    for path in sorted(ROOT.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = ast.unparse(node)
            if _ARITHMETIC.search(body) and _OWN_FALLBACK.search(body):
                found.append(f"{path.relative_to(ROOT)}::{node.name}")
    assert found == [CANONICAL], (
        f"the $fa/$fs arithmetic appears in {found}, and should appear only in {CANONICAL}. A copy "
        f"re-deriving it skips the ambient `use_defaults(...)` values, which is how "
        f"`offset(radius=5)` came to ignore `use_defaults(fn=64)` (PLAN R-P3)"
    )


def test_the_scan_finds_the_canonical_resolver() -> None:
    """A pattern that matched nothing would make the test above pass by accident."""
    body = ast.unparse(ast.parse((ROOT / "_helpers.py").read_text()))
    assert _ARITHMETIC.search(body), "the arithmetic pattern no longer matches frag_count"
    assert _OWN_FALLBACK.search(body), "the fallback pattern no longer matches frag_count"


#: Ambient settings and the count a radius-5 circle should get under each. `fa` is deliberately
#: absent: at radius 5 the `fs` term dominates every plausible `fa`, so an `fa`-only block cannot
#: tell a correct resolver from one ignoring the block -- it reports 16 either way.
AMBIENT = [({}, 16), ({"fn": 64}, 64), ({"fn": 8}, 8), ({"fs": 0.2}, 30)]


@pytest.mark.parametrize(("block", "expected"), AMBIENT, ids=lambda v: str(v))
def test_every_resolver_reads_the_ambient_block(block: dict[str, float], expected: int) -> None:
    """PLAN R-P3, R-4: `use_defaults` sets resolution for a block, so it has to arrive."""
    with use_defaults(**block):
        counts = {
            "frag_count": frag_count(5.0),
            "sdf.paths._frag_count": sdf_frag_count(5.0),
            "Path2D._offset_segs": Path2D._offset_segs(5.0),
        }
    assert set(counts.values()) == {expected}, (
        f"under use_defaults({block}) the resolvers disagree: {counts}. Each is a path some shape "
        f"is built through, so the same radius would get different smoothness depending on which"
    )


def test_an_ambient_default_reaches_a_rounded_offset() -> None:
    """The defect in the form a caller met it, end to end.

    `Path2D.offset(radius=)` bridges each corner with an arc, and the arc's segment count came from
    the copy that could not see the block. Asserted against the *explicit* spelling of the same
    value rather than a fixed number, so the two ways of saying "64" have to agree.
    """
    square = Path2D([[0.0, 0.0], [20.0, 0.0], [20.0, 20.0], [0.0, 20.0]], closed=True)
    explicit = len(square.offset(radius=5.0, fn=64))
    with use_defaults(fn=64):
        ambient = len(square.offset(radius=5.0))
    assert ambient == explicit, (
        f"offset(radius=5) gives {ambient} points under use_defaults(fn=64) and {explicit} with "
        f"fn=64 passed explicitly; the ambient block is not reaching the corner arcs"
    )
    with use_defaults(fn=8):
        coarse = len(square.offset(radius=5.0))
    assert coarse < ambient, f"fn=8 gave {coarse} points and fn=64 gave {ambient}"


@pytest.mark.parametrize(
    ("label", "build"),
    [
        ("a rounded rim", lambda **kw: cyl(radius1=10, radius2=4, height=20, rounding=2, **kw)),
        ("a chamfered rim", lambda **kw: cyl(radius1=10, radius2=4, height=20, chamfer=2, **kw)),
        ("a torus", lambda **kw: torus(outer_radius=10, inner_radius=4, **kw)),
        ("an onion", lambda **kw: onion(radius=8, **kw)),
        ("a revolved path", lambda **kw: _REVOLVED_PROFILE.rotate_extrude(**kw)),
        ("a plain cylinder -- the control", lambda **kw: cyl(radius=10, height=20, **kw)),
    ],
)
def test_an_ambient_default_reaches_a_revolved_surface(label: str, build: Callable[..., object]) -> None:
    """A revolved solid is as round as the ambient block says, not as round as the renderer guesses.

    Counted as *distinct angular positions among the mesh's vertices*, which is the facet count of
    the revolve itself rather than of anything the profile does. Asserted against the explicit
    spelling of the same value, as `test_an_ambient_default_reaches_a_rounded_offset` is and for the
    same reason: a fixed number would also pass if both spellings broke together.
    """
    for want in (16, 64, 128):
        explicit = _facet_count(build(fn=want))
        with use_defaults(fn=want):
            ambient = _facet_count(build())
        assert ambient == explicit, (
            f"{label}: use_defaults(fn={want}) gives {ambient} facets and fn={want} passed "
            f"explicitly gives {explicit}; the ambient block is not reaching the revolve"
        )
        assert explicit == want, f"{label}: fn={want} gave {explicit} facets"


#: The two functions allowed to reach the native ``rotate_extrude``. Everything else goes through
#: one of them, so the ambient block is applied once, in a place a reader can find.
REVOLVE_DOORS = {"pybosl2/shapes3d/base.py", "pybosl2/_csg.py"}


def test_only_the_two_wrappers_reach_the_native_revolve() -> None:
    """The structural half of the same rule, in the form that stops the next recurrence.

    Five call sites took the native ``rotate_extrude`` directly and **four of them dropped the
    ambient block**: `cyl` with a treated rim, `torus`, `onion` and `stroke_3d`'s endcaps, which
    passed no facet arguments at all. The fifth, `regular_prism`, computed its facet count itself
    and was correct. Three further modules -- `parts/bottlecaps.py`, `parts/screw_drive.py` and
    `shapes3d/extrusions.py` -- still *bound* the native function after their callers had moved to
    `Path2D.rotate_extrude`, so this scan found eight sites where a text search for the call found
    five. Each was a reasonable line to write on its own, which is why counting them beats testing
    them one at a time -- a sixth live one would be just as reasonable.

    `test_an_ambient_default_reaches_a_revolved_surface` covers the shapes that exist; this covers
    the ones that do not yet.
    """
    offenders = {}
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT.parent).as_posix()
        if rel in REVOLVE_DOORS:
            continue
        text = path.read_text()
        for pattern in ('native("rotate_extrude")', "from pythonscad import rotate_extrude"):
            if pattern in text:
                offenders.setdefault(rel, []).append(pattern)
    assert not offenders, (
        f"these modules take the native rotate_extrude directly: {offenders}. Call "
        f"`pybosl2.shapes3d.base._orevolve` instead -- it applies the ambient use_defaults block "
        f"and omits the arguments the caller left unset, which passing `fn=None` does not "
        f"(SPEC R-4, PLAN R-P3)."
    )


def test_the_revolve_doors_are_really_there() -> None:
    """A path typo in the allow-list above would make the scan vacuous rather than failing.

    Both names are asserted, not just the files: `_orevolve` is the wrapper and `resolve_facets` is
    what makes it one, so a door that stopped resolving would still satisfy a file-name check.
    """
    for rel in sorted(REVOLVE_DOORS):
        path = ROOT.parent / rel
        assert path.is_file(), f"{rel} is in REVOLVE_DOORS but does not exist"
    base = (ROOT / "shapes3d" / "base.py").read_text()
    assert "def _orevolve(" in base, "the revolve wrapper is gone from shapes3d/base.py"
    assert "_resolve_facets(fn, fa, fs)" in base, "_orevolve no longer resolves the ambient block"
    csg = (ROOT / "_csg.py").read_text()
    assert "resolve_facets(" in csg, "the csg backend's revolve no longer resolves the ambient block"

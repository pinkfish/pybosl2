# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Every value of an exported enum does what its name says (SPEC E-5, O-6b; PLAN X-3).

PLAN X-3 asks that a new public callable arrive with three tests: that it builds and is
*measurably* right, that it builds with the minimum arguments, and that its docstring example
validates. All three are enforced across the package -- X-8's no-existence-only-assertion gate,
Q-4's argument-free-constructor gate, and the docstring-example gates -- but nothing asked
whether a *particular* public name was reached by any of them. Walking `pybosl2.__all__` and
looking for each callable in the suite found **5 of 176 never named in a test**, and all five
were enums.

That is a worse place to have a gap than it sounds, because this package has a history there:
T106 found *two enums that changed nothing* when set, and T98 found one enum carrying two
different vocabularies under a single parameter name. An exported enum is the most
discoverable thing in an API -- a caller sees `StaggerMode.STANDARD` in their editor's
completions and reasonably assumes it works.

**One of the five did not.** `grid_copies(stagger=)` is annotated `bool | StaggerMode` and
validated against the literal list `(False, True, StaggerMode.ALT)`, so `StaggerMode.NONE` and
`StaggerMode.STANDARD` -- two of that enum's three values -- raised, while the annotation
promised them and mypy agreed. `"alt"` worked by accident, because `StrEnum` members compare
equal to their own string. See `tests/test_distributors.py` for the layout maths; this file is
about the values being *reachable*.
"""

from __future__ import annotations

import pathlib

import numpy as np
import pytest

from pybosl2 import (
    CutPoint,
    EdgeMode,
    EdgeTreatmentKind,
    MinkowskiJoin,
    StaggerMode,
)
from pybosl2.distributors import grid_copies
from pybosl2.path2d import Path2D


@pytest.mark.parametrize(
    ("spelling", "equivalent"),
    [
        (False, StaggerMode.NONE),
        (None, StaggerMode.NONE),
        ("none", StaggerMode.NONE),
        (True, StaggerMode.STANDARD),
        ("standard", StaggerMode.STANDARD),
        ("alt", StaggerMode.ALT),
    ],
    ids=["False", "None", "'none'", "True", "'standard'", "'alt'"],
)
def test_every_way_of_asking_for_a_stagger_lays_out_the_same_grid(spelling: object, equivalent: StaggerMode) -> None:
    """The boolean spelling and the enum spelling of one layout agree exactly.

    This is the assertion that would have failed before: `StaggerMode.NONE` and
    `StaggerMode.STANDARD` raised `Bosl2ValueError` rather than laying out anything.
    """
    by_spelling = grid_copies(spacing=5, num_copies=[3, 3], stagger=spelling)  # type: ignore[arg-type]
    by_enum = grid_copies(spacing=5, num_copies=[3, 3], stagger=equivalent)
    assert len(by_spelling) == len(by_enum)
    for left, right in zip(by_spelling, by_enum, strict=True):
        assert np.allclose(left, right), f"{spelling!r} and {equivalent} place copies differently"


def test_the_three_stagger_modes_lay_out_three_different_grids() -> None:
    """And they are not merely accepted -- each produces a layout of its own.

    A square 3x3 is nine copies; staggering drops the count because a half-step row runs off the
    same extent, and `ALT` staggers the opposite rows, so it drops one more. Accepting a value
    and acting on it are different things, which is exactly what T106 found.
    """
    counts = {mode: len(grid_copies(spacing=5, num_copies=[3, 3], stagger=mode)) for mode in StaggerMode}
    assert counts[StaggerMode.NONE] == 9, counts
    assert counts[StaggerMode.STANDARD] == 5, counts
    assert counts[StaggerMode.ALT] == 4, counts
    assert len(set(counts.values())) == 3, f"two modes lay out the same grid: {counts}"


def test_an_unknown_stagger_is_refused_by_name() -> None:
    """The refusal lists what is allowed, rather than naming only the two booleans (SPEC E-5)."""
    from pybosl2.exceptions import Bosl2ValueError

    with pytest.raises(Bosl2ValueError, match=r"'none'.*'standard'.*'alt'"):
        grid_copies(spacing=5, num_copies=[3, 3], stagger="diagonal")  # type: ignore[arg-type]


def test_each_minkowski_join_shapes_the_corner_its_name_describes() -> None:
    """ROUND, MITRE and BEVEL are three corner treatments, measured by what they leave behind.

    A square buffered by 3 keeps its extent either way -- `max_x` is 23 for all three -- so a
    bounding box cannot tell them apart. The vertex count can: a mitre is one point per corner,
    a bevel is two, and a round corner is an arc.
    """
    square = Path2D([[0, 0], [20, 0], [20, 20], [0, 20]], closed=True)
    corners = {join: np.asarray(list(square.minkowski_sum_circle(3, join=join))) for join in MinkowskiJoin}

    for join, pts in corners.items():
        assert pts[:, 0].max() == pytest.approx(23.0), f"{join} changed the extent"

    assert len(corners[MinkowskiJoin.MITRE]) == 4, "a mitre leaves one vertex per corner"
    assert len(corners[MinkowskiJoin.BEVEL]) == 8, "a bevel leaves two"
    assert len(corners[MinkowskiJoin.ROUND]) > 16, "a round corner is an arc, not a cut"


def test_the_edge_treatment_kinds_are_what_the_group_dispatches_on() -> None:
    """`EdgeTreatment` is one group because rounding and chamfering an edge are exclusive (G-7).

    So its discriminator has to round-trip: each constructor records its own kind, and the
    default records none.
    """
    from pybosl2.groups import EdgeTreatment

    assert EdgeTreatment().kind is EdgeTreatmentKind.NONE
    assert EdgeTreatment.rounding(2).kind is EdgeTreatmentKind.ROUNDING
    assert EdgeTreatment.chamfer(2).kind is EdgeTreatmentKind.CHAMFER
    assert EdgeTreatment.rounding(2).size == 2


def test_the_two_edge_modes_build_different_rims() -> None:
    """`EdgeMode` picks which rim a cylinder's end carries, and the two are not the same solid.

    A chamfer cuts a straight corner and a rounding an arc, so at equal size the chamfered end
    removes more material. Measured on the field rather than the box, because both share one.
    """
    import pybosl2.sdf.shapes3d as sdf
    from pybosl2.sdf._libfive import lv

    assert set(EdgeMode) == {EdgeMode.ROUND, EdgeMode.CHAMFER}

    fields = {
        "round": sdf.cyl(height=20, radius=8, rounding=3, anchor=[0, 0, 0]),
        "chamfer": sdf.cyl(height=20, radius=8, chamfer=3, anchor=[0, 0, 0]),
    }
    # Just inside the rim corner, where a chamfer has cut and a rounding has not yet.
    probe = (7.4, 0.0, 9.4)
    values = {k: float(v._sdf_fn(lv.x(), lv.y(), lv.z())(*probe)) for k, v in fields.items()}
    assert values["chamfer"] > values["round"], (
        f"a chamfer should have removed more at the corner than a rounding: {values}"
    )


def test_a_cut_point_reports_whether_it_carries_a_direction() -> None:
    """`CutPoint.is_directed` is the only behaviour it has, and it answers for both shapes.

    `cut_points(direction=True)` fills `direction` and `normal`; without it they stay None, and
    a caller reading them would otherwise have to guess.
    """
    path = Path2D([[0, 0], [10, 0], [10, 10]], closed=False)

    plain = path.cut_points([0.5])
    assert all(isinstance(c, CutPoint) for c in plain)
    assert not plain[0].is_directed
    assert plain[0].direction is None
    assert plain[0].normal is None

    directed = path.cut_points([0.5], direction=True)
    assert directed[0].is_directed
    assert directed[0].direction is not None
    assert np.allclose(np.linalg.norm(directed[0].direction), 1.0), "a direction is a unit vector"


def test_a_jittered_poly_moves_every_point_but_only_just() -> None:
    """`jittered_poly` exists to break exact coplanarity, so the bound is the whole contract.

    Its purpose is to stop two faces landing in exactly the same plane, which renderers show as
    z-fighting artifacts. That means two things have to hold at once and neither alone is
    enough: every point must actually move (or the overlap it was called to break survives),
    and no point may move further than `dist` (or it has reshaped the outline it was asked to
    perturb). The default is 1/512 of a millimetre.
    """
    from pybosl2.shapes2d.curves import jittered_poly

    outline = Path2D([[0, 0], [10, 0], [10, 10], [0, 10]], closed=True)
    original = np.asarray(list(outline), dtype=float)
    jittered = np.asarray(jittered_poly(outline), dtype=float)

    assert jittered.shape == original.shape
    offsets = np.abs(jittered - original)
    assert (offsets > 0).all(), "a point that did not move cannot break a coplanar overlap"
    assert (offsets <= 1 / 512).all(), f"moved further than the default dist: {offsets.max()}"

    wider = np.asarray(jittered_poly(outline, dist=0.5), dtype=float)
    assert (np.abs(wider - original) <= 0.5).all()
    assert np.abs(wider - original).max() > 1 / 512, "dist= is ignored"


def test_every_offset_sweep_profile_type_is_a_profile_the_sweep_accepts() -> None:
    """`OSType` names the rim profiles `offset_sweep` can put on an edge (SPEC S-19a).

    An exported enum whose members the builder does not accept is the `StaggerMode` defect
    above, so each one is constructed rather than merely listed.
    """
    from pybosl2.skin import OSProfile, OSType

    assert [kind.value for kind in OSType] == [
        "circle",
        "smooth",
        "teardrop",
        "chamfer",
        "flat",
        "profile",
    ]
    for kind in OSType:
        profile = OSProfile(type=kind)
        assert profile.type is kind, f"{kind} did not round-trip through OSProfile"


#: Public callables the suite is allowed not to name. **Empty, and the point is that it stays
#: empty** -- a name added here is a public thing nobody tests, which is how two enums came to
#: change nothing (T106) and how `StaggerMode` came to refuse its own values.
UNEXERCISED: frozenset[str] = frozenset()


def test_every_public_callable_is_named_somewhere_in_the_suite() -> None:
    """The scan that found this file's subject (PLAN X-3).

    X-3's three tests are each enforced across the whole package -- X-8 forbids an
    existence-only assertion, Q-4 walks the argument-free constructors, and the docstring-example
    gates read every example -- but none of them answers "is *this* name reached by any of them".
    So this walks `pybosl2.__all__` and looks for each callable in `tests/`.

    Naming a callable is a weak condition on its own: a test that merely mentions something
    proves nothing, and `tests/test_assertion_quality.py` exists because this repository had a
    pile of those. The pair is what carries weight -- **every public callable is reached, and no
    test asserts only that a result exists** -- and neither half is worth much alone.

    When it last reported a gap it was 5 of 176, every one an enum: `CutPoint`, `EdgeMode`,
    `EdgeTreatmentKind`, `MinkowskiJoin` and `StaggerMode`.
    """
    import ast
    import re

    import pybosl2

    exported = sorted(getattr(pybosl2, "__all__", []))
    assert len(exported) > 150, f"only {len(exported)} exported names -- has the surface moved?"

    callables = []
    for name in exported:
        try:
            if callable(getattr(pybosl2, name)):
                callables.append(name)
        except AttributeError:  # pragma: no cover - a broken export is test_exports.py's business
            continue

    # **Identifiers and string literals, but never docstrings.** Both of the obvious scans are
    # wrong here, in opposite directions, and each was tried:
    #
    # * Searching the files as text made this gate satisfy itself -- the docstring above names
    #   the five enums it found, so its own prose counted as coverage and would have masked them
    #   permanently.
    # * Reading only the AST's identifiers was too strict: this suite exercises real code
    #   through *source strings*, which is not a shortcut but how the render tests work
    #   (`_render(tmp_path, "roof(s2.square([20, 10]))")`) and how `test_facets.py` keeps its
    #   registry (`"isosurface.py::Metaball.sphere"`). Both were reported as uncovered when they
    #   are nothing of the kind.
    #
    # So: every identifier the AST knows about, plus the words inside string literals that are
    # not docstrings.
    used: set[str] = set()
    for path in sorted(pathlib.Path(__file__).parent.glob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:  # pragma: no cover - a test file that will not parse fails on its own
            continue
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                used.add(node.attr)
            elif isinstance(node, ast.alias):
                used.add((node.asname or node.name).split(".")[-1])
                used.add(node.name.split(".")[-1])
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                used.update(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", node.value))

    missing = sorted(n for n in callables if n not in used)
    unexpected = [n for n in missing if n not in UNEXERCISED]
    assert not unexpected, (
        f"{len(unexpected)} of {len(callables)} public callables are never used in the suite: "
        f"{unexpected}. A public name no test exercises is not covered by X-3's three tests, "
        f"whatever the package-wide gates report."
    )
    stale = sorted(UNEXERCISED - set(missing))
    assert not stale, f"these are exercised now; delete them from UNEXERCISED: {stale}"

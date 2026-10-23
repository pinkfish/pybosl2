# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The `flat` façade must honour `anchor` and `spin` on both backends (SPEC G-1, B-9).

`flat.py` dispatches each 2-D shape to one of two primitives, and the two branches were not
carrying the same load. `anchor` reached only `rect2d`; `spin` reached neither. The façade declares
both for every shape, so on the SDF backend four of six shapes accepted a placement request and
threw it away, and `spin` was discarded by all six -- the silent-no-op failure, on the parameter
callers reach for most.

SPEC B-9's existing guard could not see it. That test asks whether a declared parameter is
forwarded *anywhere* in the body, and `anchor`/`spin` are forwarded on the CSG branch, so one
branch carrying them was enough to pass. A two-branch function needs the question asked per branch.

The same split hid three live options on `regular_ngon2d` and two on `star2d`: both primitives take
`realign`, `star2d` takes `step`, and `regular_ngon2d` takes `inner_radius`/`inner_diameter`/`side`,
none of which the façade passed on.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import math
from typing import TYPE_CHECKING, Any

import pytest

import pybosl2.flat as flat
from pybosl2._backend import use_backend
from pybosl2._edges_lang import resolve_anchor
from pybosl2.constants import LEFT
from pybosl2.path2d import Path2D

if TYPE_CHECKING:
    from collections.abc import Sequence

#: One representative call per façade 2-D shape that dispatches to an SDF primitive -- taken from
#: the branch scan at the bottom of this file, not written out by hand. Writing it by hand is how
#: the first version of this guard missed `circle` and `square`, which the scan had listed and the
#: fixture had not: `circle` discarded both `anchor` and `spin` on the SDF backend and `square`
#: discarded `spin`, in the same file as the six that were being fixed. `text` is the ninth
#: two-branch façade and is absent deliberately -- it refuses on the SDF backend outright, which is
#: the honest answer and not a dropped option.
SHAPES: dict[str, dict[str, Any]] = {
    "circle": {"radius": 5},
    "square": {"size": [20, 10]},
    "rect": {"size": [20, 10]},
    "ellipse": {"radius": 5},
    "polygon": {"points": Path2D([[0, 0], [10, 0], [10, 5]])},
    "regular_ngon": {"sides": 5, "radius": 5},
    "star": {"tips": 5, "radius": 10, "inner_radius": 4},
    "trapezoid": {"height": 10, "width1": 20, "width2": 10},
}

#: The shapes a 30-degree turn visibly moves. `circle` and a circular `ellipse` are left out because
#: they are rotationally symmetric: their outline cannot witness its own spin, so asserting that
#: their box changes would pin the *looseness* of the rotated box rather than the rotation -- see
#: `test_a_turned_circle_reports_a_box_it_cannot_fill`. A regular hexagon would be the same trap at
#: 60 degrees, which is why the n-gon fixture is a pentagon.
SPUN = sorted(set(SHAPES) - {"circle", "ellipse"})


def _box(shape: Any) -> tuple[float, ...]:
    b = shape.bounds()
    return tuple(round(v, 4) for v in (b.min_x, b.min_y, b.max_x, b.max_y))


@pytest.mark.parametrize("backend", ["csg", "sdf"])
@pytest.mark.parametrize("name", sorted(SHAPES))
def test_anchor_moves_the_shape_on_both_backends(name: str, backend: str) -> None:
    """SPEC G-1: `anchor=LEFT` must move the shape, whichever backend builds it."""
    kwargs = SHAPES[name]
    with use_backend(backend):
        centred = _box(getattr(flat, name)(**kwargs))
        anchored = _box(getattr(flat, name)(**kwargs, anchor=LEFT))
    assert centred != anchored, (
        f"flat.{name}(anchor=LEFT) on the {backend} backend returns the same box as the centred "
        f"shape, {centred} -- the anchor was accepted and discarded (SPEC G-1, B-9)."
    )


@pytest.mark.parametrize("backend", ["csg", "sdf"])
@pytest.mark.parametrize("name", SPUN)
def test_spin_turns_the_shape_on_both_backends(name: str, backend: str) -> None:
    """SPEC G-1: `spin=30` must turn the shape, whichever backend builds it."""
    kwargs = SHAPES[name]
    with use_backend(backend):
        still = _box(getattr(flat, name)(**kwargs))
        spun = _box(getattr(flat, name)(**kwargs, spin=30))
    assert still != spun, (
        f"flat.{name}(spin=30) on the {backend} backend returns the same box as the unspun shape, "
        f"{still} -- the spin was accepted and discarded (SPEC G-1, B-9)."
    )


def test_anchor_runs_before_spin() -> None:
    """The two do not commute, so pin the order against the two spellings of it directly.

    Not against the CSG backend and not on a `rect`: `rect2d` takes its own `anchor`, so the
    façade hands the helper no anchor for a rect and reversing the helper cannot change a rect's
    box. A control that swapped the order passed happily while this test used one.
    """
    import pybosl2.sdf.shapes2d as sdf2d

    vector = resolve_anchor(LEFT).vector_2d.tolist()
    built = sdf2d.trapezoid2d(height=10, width1=20, width2=10, res=10)
    anchor_first = _box(built.reanchor(vector).rotate(30))
    spin_first = _box(built.rotate(30).reanchor(vector))
    assert anchor_first != spin_first, (
        "the fixture cannot tell the two orders apart, so it proves nothing -- pick a shape and "
        "anchor where anchoring and spinning do not commute."
    )
    with use_backend("sdf"):
        got = _box(flat.trapezoid(**SHAPES["trapezoid"], anchor=LEFT, spin=30))
    assert got == anchor_first, (
        f"flat.trapezoid(anchor=LEFT, spin=30) on sdf gives {got}; anchoring first gives "
        f"{anchor_first} and spinning first {spin_first}. CSG anchors first."
    )


#: What `anchor=LEFT` does on each backend, as measured. The SDF side anchors to the bounding box
#: (`reanchor`); the CSG side anchors to the geometry. Where an outline touches every side of its
#: box the two coincide; otherwise CSG lands on a feature the box knows nothing about -- a pentagon
#: differs by exactly 2.939 in y, the y of the vertex CSG chooses over the box edge midpoint.
#: "x" means the axis the anchor names agrees and the other does not. Entries may move towards
#: "both", never away: this records a gap, it does not license one.
ANCHOR_AGREEMENT = {
    "circle": "both",
    "square": "both",
    "rect": "both",
    "ellipse": "both",
    "regular_ngon": "x",
    "star": "x",
    "trapezoid": "x",
    "polygon": "neither",
}
_BETTER = {("x", "both"), ("neither", "both"), ("neither", "x")}


@pytest.mark.parametrize("name", sorted(SHAPES))
def test_anchoring_agrees_with_csg_as_far_as_it_is_known_to(name: str) -> None:
    """The backends must not drift further apart on `anchor` than they already are."""
    kwargs = SHAPES[name]
    with use_backend("csg"):
        csg = _box(getattr(flat, name)(**kwargs, anchor=LEFT))
    with use_backend("sdf"):
        sdf = _box(getattr(flat, name)(**kwargs, anchor=LEFT))
    x_agrees = (csg[0], csg[2]) == pytest.approx((sdf[0], sdf[2]), abs=1e-3)
    y_agrees = (csg[1], csg[3]) == pytest.approx((sdf[1], sdf[3]), abs=1e-3)
    expected = ANCHOR_AGREEMENT[name]
    got = "both" if x_agrees and y_agrees else "x" if x_agrees else "neither"
    assert got == expected or (expected, got) in _BETTER, (
        f"flat.{name}(anchor=LEFT): csg={csg} sdf={sdf}. The table says the backends agree on "
        f"{expected!r} and they now agree on {got!r} -- a regression unless the table is updated "
        f"to the better figure."
    )


def test_the_centred_shapes_agree_exactly() -> None:
    """Every anchor difference above is anchoring, not a different shape.

    Without this the table could be recording a shape mismatch and calling it an anchor gap.
    """
    for name, kwargs in SHAPES.items():
        with use_backend("csg"):
            csg = _box(getattr(flat, name)(**kwargs))
        with use_backend("sdf"):
            sdf = _box(getattr(flat, name)(**kwargs))
        assert csg == pytest.approx(sdf, abs=1e-3), (
            f"flat.{name}() is already a different shape on the two backends, csg={csg} "
            f"sdf={sdf} -- the anchor table above is measuring the wrong thing."
        )


#: `regular_ngon`'s three size options that are *not* spellings of `radius`, with the circumradius
#: each implies for a pentagon. A hexagon is the one polygon where `side` and `inner_radius` would
#: both come out equal to `radius` -- measuring there would have called all three aliases.
NGON_SIZES = [
    ("radius", 5.0, 5.0),
    ("inner_radius", 5.0, 5.0 / math.cos(math.pi / 5)),
    ("inner_diameter", 10.0, 5.0 / math.cos(math.pi / 5)),
    ("side", 5.0, 5.0 / (2 * math.sin(math.pi / 5))),
]


@pytest.mark.parametrize("backend", ["csg", "sdf"])
@pytest.mark.parametrize(("option", "value", "circumradius"), NGON_SIZES)
def test_every_ngon_size_option_measures_what_it_names(
    option: str, value: float, circumradius: float, backend: str
) -> None:
    """The apothem and the side length are separate measurements, and both backends have them."""
    with use_backend(backend):
        b = flat.regular_ngon(sides=5, **{option: value}).bounds()
    got = max(abs(b.min_x), abs(b.max_x), abs(b.min_y), abs(b.max_y))
    assert got == pytest.approx(circumradius, rel=1e-3), (
        f"flat.regular_ngon(sides=5, {option}={value}) on {backend} has circumradius {got:.4f}, "
        f"not the {circumradius:.4f} that option names."
    )


def test_realign_reaches_both_backends() -> None:
    """`realign` is live on both primitives; the façade used to pass it only to CSG."""
    for name, kwargs in (("regular_ngon", SHAPES["regular_ngon"]), ("star", SHAPES["star"])):
        with use_backend("sdf"):
            plain = _box(getattr(flat, name)(**kwargs))
            realigned = _box(getattr(flat, name)(**kwargs, realign=True))
        assert plain != realigned, (
            f"flat.{name}(realign=True) on sdf returns the centred box {plain} -- `realign` is a "
            f"parameter of the sdf primitive and was dropped on the way to it (SPEC B-9)."
        )


def test_star_step_reaches_the_sdf_primitive() -> None:
    """`step` picks which tips join, which a bounding box cannot see -- so watch the call instead.

    A {5/2} star has the same circumradius as a {5/1}, and with libfive absent the field cannot be
    sampled, so the honest instrument is the argument the façade passes on.
    """
    seen: dict[str, Any] = {}
    import pybosl2.sdf.shapes2d as sdf2d

    real = sdf2d.star2d

    def spy(**kwargs: Any) -> Any:
        seen.update(kwargs)
        return real(**kwargs)

    sdf2d.star2d = spy  # type: ignore[assignment]
    try:
        with use_backend("sdf"):
            flat.star(**SHAPES["star"], step=2)
    finally:
        sdf2d.star2d = real  # type: ignore[assignment]
    assert seen.get("step") == 2, (
        f"flat.star(step=2) called the sdf primitive with step={seen.get('step')!r}. The primitive "
        f"has a `step`; the façade passed it only to CSG."
    )


# ----------------------------------------------------------------------------------------
# The scan that found all of the above: per branch, not per function.
# ----------------------------------------------------------------------------------------


def _branches(fn: ast.FunctionDef) -> tuple[list[ast.stmt], list[ast.stmt]]:
    """Split a façade body into its SDF branch and everything else."""
    sdf: list[ast.stmt] = []
    rest: list[ast.stmt] = []
    for stmt in fn.body:
        dumped = ast.dump(stmt).replace('"', "'")
        if isinstance(stmt, ast.If) and "current_backend" in dumped and "'sdf'" in dumped:
            sdf.extend(stmt.body)
            rest.extend(stmt.orelse)
        else:
            rest.append(stmt)
    return sdf, rest


def _primitive_call(nodes: "Sequence[ast.stmt]", helpers: "dict[str, ast.FunctionDef]") -> tuple[set[str], Any]:
    """Return the keywords passed to the branch's *primitive*, and the primitive itself.

    Two refinements, each one a defect the earlier version of this scan could not see.

    It follows a branch that has been split into a module-private helper. Splitting
    `regular_ngon`'s SDF branch into `_regular_ngon_sdf` to stay inside the S-2 line budget put the
    primitive call one frame away, and the scan stopped at the extraction.

    And it collects keywords from the call to the primitive alone, not from every call in the
    branch. Collecting them all made the forwarding to the helper itself count as forwarding:
    `_regular_ngon_sdf(realign=realign, ...)` mentions `realign` whether or not the helper passes it
    to `regular_ngon2d`, so a control that dropped it from the primitive call went unseen.
    """
    bindings: dict[str, Any] = {}
    calls: list[ast.Call] = []
    followed: set[str] = set()
    pending = list(nodes)
    while pending:
        node = pending.pop()
        for sub in ast.walk(ast.Module(body=[node], type_ignores=[])):
            if isinstance(sub, ast.ImportFrom) and sub.module:
                for alias in sub.names:
                    try:
                        bindings[alias.asname or alias.name] = getattr(importlib.import_module(sub.module), alias.name)
                    except (ImportError, AttributeError):
                        continue
            if isinstance(sub, ast.Call):
                calls.append(sub)
                callee = sub.func.id if isinstance(sub.func, ast.Name) else None
                if callee in helpers and callee not in followed:
                    followed.add(callee)
                    pending.extend(helpers[callee].body)
    for call in calls:
        name = call.func.id if isinstance(call.func, ast.Name) else None
        if name in bindings:
            return {k.arg for k in call.keywords if k.arg}, bindings[name]
    return set(), None


def _one_branch_drops() -> list[tuple[str, str, str]]:
    """Every parameter both primitives accept that only one branch forwards."""
    found: list[tuple[str, str, str]] = []
    for module_name in ("pybosl2.flat", "pybosl2.solid"):
        module = importlib.import_module(module_name)
        tree = ast.parse(inspect.getsource(module))
        helpers = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("_")}
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            sdf_nodes, rest_nodes = _branches(node)
            if not sdf_nodes:
                continue
            sdf_kw, sdf_target = _primitive_call(sdf_nodes, helpers)
            csg_kw, csg_target = _primitive_call(rest_nodes, helpers)
            if sdf_target is None or csg_target is None:
                continue
            try:
                sdf_params = set(inspect.signature(sdf_target).parameters)
                csg_params = set(inspect.signature(csg_target).parameters)
            except (TypeError, ValueError):
                continue
            declared = {a.arg for a in node.args.args + node.args.kwonlyargs}
            for param in sorted(declared & sdf_params & csg_params):
                if (param in csg_kw) != (param in sdf_kw):
                    found.append((module_name, node.name, param))
    return found


def test_the_scan_examined_some_two_branch_facades() -> None:
    """A scan that matched nothing would pass the test below for the wrong reason."""
    examined = 0
    for module_name in ("pybosl2.flat", "pybosl2.solid"):
        module = importlib.import_module(module_name)
        for node in ast.parse(inspect.getsource(module)).body:
            is_facade = isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
            if is_facade and _branches(node)[0]:  # type: ignore[arg-type]
                examined += 1
    assert examined >= 9, (
        f"only {examined} two-branch façade functions found, where the measurement found 9 -- the "
        f'branch split stopped recognising `if current_backend() == "sdf":`, and the test below '
        f"would then pass by examining nothing."
    )


def test_no_parameter_is_forwarded_on_only_one_branch() -> None:
    """A parameter both primitives accept must reach both, or the backend decides it silently."""
    dropped = _one_branch_drops()
    assert not dropped, (
        "\n".join(
            f"{mod}::{fn} forwards {param!r} on one branch only -- the other primitive takes it too, "
            f"so on that backend the caller's value vanishes (SPEC B-9)."
            for mod, fn, param in dropped
        )
        or "(none)"
    )


@pytest.mark.xfail(
    strict=True,
    reason="SPEC §12.2 item 21, in 2-D: PyShape2D.rotate rebuilds the box from the rotated corners "
    "of the old box, so a shape a rotation cannot move still reports a wider one. Fixed for the "
    "3-D solids by recording the line each may be turned about; the 2-D shape has no such record. "
    "Remove this xfail when it gains one.",
)
def test_a_turned_circle_reports_a_box_it_cannot_fill() -> None:
    """A circle has no orientation, so spinning it must not change its bounds.

    Reachable through `flat.circle(spin=)` only because the spin is now honoured at all; calling
    `PyShape2D.rotate` directly has always done this. The figure is the same 37% item 21 measured
    on a sphere, which is the same arithmetic one dimension up.
    """
    with use_backend("sdf"):
        still = _box(flat.circle(radius=5))
        spun = _box(flat.circle(radius=5, spin=30))
    assert spun == still, (
        f"a circle of radius 5 reports {still} unspun and {spun} after spin=30 -- "
        f"{(spun[2] / still[2] - 1) * 100:.0f}% wider than a shape a rotation cannot move."
    )

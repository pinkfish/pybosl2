# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A function that builds no geometry is not backend-only, wherever it happens to live.

SPEC PAR-1, B-4. `@backend_only("csg")` says "this constructor builds CSG geometry, so calling it
under another backend hands you something that cannot combine with its surroundings". Three
functions carried it that build no geometry at all:

* `arc()` returns a `Path2D` -- 205 lines of plane trigonometry;
* `rect_path()` and `jittered_poly()` return lists of points.

All three refused under `use_backend("sdf")`, gated on which shape library happened to be active
rather than on anything they do. They live in `pybosl2.shapes2d` because that is where BOSL2 puts
them (B2-3), and the marker followed the module rather than the function.

**The false refusal was hiding a real defect.** `partition_mask` and `partition_cut_mask` call
`arc()`, so they refused too -- and looked correctly backend-isolated. They are not: they build
with `pythonscad.polygon`, `.offset(delta=)` and `.linear_extrude`, and returned a **CSG solid
inside an sdf block** the moment `arc` stopped refusing for them. They carry the marker themselves
now, which is where it belongs and what makes the reason true.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from pybosl2 import use_backend

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Return annotations that are geometry no backend owns. A function returning one of these has
#: nothing to hand back that could belong to the wrong backend.
NEUTRAL = frozenset({"Path2D", "Path3D", "Region", "VNF", "list", "float", "int", "bool", "str", "tuple", "None"})


def _backend_only_returning_neutral() -> list[tuple[str, str, str]]:
    """Return every `@backend_only` callable whose return type is backend-neutral."""
    found = []
    for path in sorted((ROOT / "pybosl2").rglob("*.py")):
        source = path.read_text()
        if "backend_only" not in source:
            continue
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.FunctionDef) or node.returns is None:
                continue
            if not any("backend_only" in ast.unparse(d) for d in node.decorator_list):
                continue
            returns = ast.unparse(node.returns).strip("'\"")
            if returns.replace("[", " ").replace("|", " ").split()[0] in NEUTRAL:
                found.append((str(path.relative_to(ROOT)), node.name, returns))
    return found


def test_nothing_backend_only_returns_backend_neutral_geometry() -> None:
    """The measurement that found the three, kept so a fourth cannot be added quietly."""
    gated = _backend_only_returning_neutral()
    assert not gated, (
        "these are marked @backend_only but return geometry no backend owns, so they refuse "
        "under the other one for no reason a caller can act on:\n  "
        + "\n  ".join(f"{path}::{name} -> {returns}" for path, name, returns in gated)
    )


@pytest.mark.parametrize(
    ("name", "kwargs"),
    [("arc", {"count": 8, "radius": 5, "angle": 90}), ("rect_path", {"size": [10, 6]})],
)
def test_the_path_builders_work_under_either_backend(name: str, kwargs: dict[str, object]) -> None:
    """And the same call gives the same answer, because there is no backend in it to differ."""
    from pybosl2 import shapes2d

    results = {}
    for backend in ("csg", "sdf"):
        with use_backend(backend):
            results[backend] = [[round(float(v), 9) for v in point] for point in getattr(shapes2d, name)(**kwargs)]
    assert results["csg"] == results["sdf"], f"{name} differs between backends: {results}"


@pytest.mark.parametrize("name", ["partition_mask", "partition_cut_mask"])
def test_the_partition_masks_refuse_for_their_own_reason(name: str) -> None:
    """The defect the false refusal was hiding, and why a wrong reason is worse than none.

    These built a CSG solid whatever backend was active, and nothing said so: they appeared to be
    isolated because `arc()`, which they call for the cut path, refused on their behalf. Fixing
    `arc` made them build -- and hand a `CsgSolid` back inside an `sdf` block, which is the A-6
    defect `backend_only` exists to prevent.

    They are genuinely CSG-only -- `pythonscad.polygon`, `.offset(delta=)` and `.linear_extrude`,
    all native mesh operations -- so the marker is right. It just has to be on *them*, where the
    reason is true, and not arriving second-hand from a helper that had no business refusing.
    """
    import pybosl2
    from pybosl2.exceptions import UnsupportedByBackendError

    with use_backend("csg"):
        assert getattr(pybosl2, name)().backend == "csg"

    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError) as excinfo:
        getattr(pybosl2, name)()
    assert name in str(excinfo.value), "the refusal names the function that cannot honour the backend"


def test_arc_is_reachable_by_every_spelling_it_had() -> None:
    """Moving a function to the layer it belongs in must not move it out from under its callers.

    `arc` is path geometry -- 205 lines of plane trigonometry returning a `Path2D` -- so it lives
    in `pybosl2.path2d` now rather than in a backend module. But BOSL2 puts it in `shapes2d`, and
    B2-3 says a caller reading BOSL2 should find it where BOSL2 says it is, so `shapes2d`
    re-exports it and the top-level name is unchanged.
    """
    import pybosl2
    import pybosl2.path2d
    import pybosl2.shapes2d

    assert pybosl2.arc is pybosl2.path2d.arc
    assert pybosl2.shapes2d.arc is pybosl2.path2d.arc
    assert pybosl2.path2d.arc.__module__ == "pybosl2.path2d", "it is defined where it lives"


def test_the_turtle_takes_its_arc_from_the_geometry_layer() -> None:
    """The layering edge this move closed, checked at the import rather than in the model file.

    `pybosl2.turtle.turtle2d` is L2 and was importing `pybosl2.shapes2d`, which is L3 -- a runtime
    upward edge, listed as debt since the model was written. The turtle needs an *arc path*, not a
    shape; once the arc lived in the geometry layer there was nothing left to reach up for.
    """
    import ast

    source = (ROOT / "pybosl2" / "turtle" / "turtle2d.py").read_text()
    reached = {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module and node.col_offset == 0
    }
    assert "pybosl2.path2d" in reached, "the turtle should take its arc from the geometry layer"
    assert not any(m.startswith("pybosl2.shapes2d") for m in reached), (
        f"turtle2d reaches a backend module at import time: {sorted(m for m in reached if 'shapes' in m)}"
    )

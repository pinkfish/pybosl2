# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""The SDF backend's own methods must not hand back a CSG solid either (SPEC A-6, B-5).

`tests/test_a_neutral_call_does_not_hand_back_csg.py` states its blind spot in the file: its
static scan skips `pybosl2/sdf/`, because reaching a native handle inside a backend module is that
module's job. That exemption was too wide. It also skipped the *dynamic* half, and six methods of
`SdfSolid` were meshing their receiver and returning the mesh:

    with use_backend("sdf"):
        block.repair()       # -> CsgSolid
        block.oversample(2)  # -> CsgSolid
        block.separate()     # -> [CsgSolid]
        block.wrap(20)       # -> CsgSolid
        block.pull(UP, 2)    # -> CsgSolid
        block.partition()    # -> (CsgSolid, CsgSolid)

Measured in the real PythonSCAD app, all six; the fast suite could not see them at all, because
`to_csg()` cannot mesh under the numeric mock and `partition` raised a `TypeError` there instead.
Each said *"via CSG conversion"* in its docstring, which is a declaration to a reader and nothing
to a caller: the returned solid would not combine with the fields around it, and the failure
surfaced as `TypeError: invalid argument left to operator` from inside PythonSCAD, naming nothing
the caller had written (SPEC E-1, E-6).

The check that would have found them needs no table of suspects, and this is it: call the methods
and look at what comes back. `to_csg()` is the one declared door across the boundary, so it is the
one exemption -- and the only way to add another is to write it down here.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import textwrap
from typing import Any

import pytest

from pybosl2 import use_backend
from pybosl2.exceptions import Bosl2Error, UnsupportedByBackendError

ROOT = pathlib.Path(__file__).resolve().parent.parent
SDF = ROOT / "pybosl2" / "sdf"

#: Methods a sweep cannot call blind, with the reason. Not exemptions from the rule -- nothing
#: here is allowed to return a CSG solid -- just calls that do something other than return
#: geometry, so calling them in a loop measures nothing.
UNSWEPT: dict[str, str] = {
    "show": "hands the solid to the viewer; its return value is not geometry",
    "realize": "the render-time hook, which the viewer calls",
    "mesh": "returns the libfive frep handle by design: it IS the boundary, and `to_csg` uses it",
    "to_csg": "the declared door across the boundary (SPEC B-5) -- returning a CSG solid is its job",
    "sdf": "returns the distance function, not a shape",
    "vnf": "returns a neutral `VNF`, which belongs to no backend",
    "bounds": "returns a `Bounds3D`",
    "position": "returns a point",
    "tag": "returns the tag string",
}

#: Arguments for the methods that need one, so the sweep reaches them too. The point of the sweep
#: is that it does not depend on anyone guessing which method is suspect, so every method that can
#: be called is called; these are the ones whose signature needs filling in.
ARGUMENTS: dict[str, tuple[tuple[Any, ...], dict[str, Any]]] = {
    "back": ((5.0,), {}),
    "chamfer": ((1.0,), {}),
    "down": ((5.0,), {}),
    "forward": ((5.0,), {}),
    "left": ((5.0,), {}),
    "mirror": (([1.0, 0.0, 0.0],), {}),
    "multmatrix": (([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],), {}),
    "offset3d": ((1.0,), {}),
    "oversample": ((2,), {}),
    "pull": (([0.0, 0.0, 1.0], 2.0), {}),
    "resize": (([20.0, 20.0, 20.0],), {}),
    "right": ((5.0,), {}),
    "round": ((1.0,), {}),
    "scale": (([2.0, 2.0, 2.0],), {}),
    "translate": (([1.0, 2.0, 3.0],), {}),
    "up": ((5.0,), {}),
    "with_nominal_size": (([10.0, 10.0, 10.0],), {}),
    "wrap": ((20.0,), {}),
}

#: `to_csg()` calls inside the SDF backend that cross the boundary and come back, with the reason.
#: The list only shrinks. An entry is a declaration that the method returns a *field* despite
#: meshing on the way, which the dynamic sweep below then holds it to.
CROSSES_AND_RETURNS: dict[str, str] = {
    "pybosl2/sdf/shapes2d.py::hull": (
        "the 2-D hull goes out through the 3-D hull's `projection` and comes back as a "
        "`polygon2d` -- an SDF shape. Lossy (B-5) and recorded as such in the method."
    ),
}


def _solid() -> Any:
    from pybosl2.solid import cuboid

    return cuboid([10.0, 10.0, 10.0])


def _swept_names() -> list[str]:
    """Every public `SdfSolid` method the sweep can call, from the class itself."""
    from pybosl2.sdf.shapes3d import SdfSolid

    names = []
    for name, raw in sorted(vars(SdfSolid).items()):
        member = raw.__func__ if isinstance(raw, staticmethod) else raw
        if name.startswith("_") or not callable(member) or name in UNSWEPT:
            continue
        try:
            signature = inspect.signature(member)
        except (TypeError, ValueError):  # pragma: no cover -- a C-level member would land here
            continue
        # `union`/`difference`/`intersection` are static, so their first parameter is a shape and
        # not the receiver. Dropping it regardless made them look callable with no arguments.
        parameters = list(signature.parameters.values())
        needed = [
            parameter.name
            for parameter in (parameters if isinstance(raw, staticmethod) else parameters[1:])
            if parameter.default is inspect.Parameter.empty
            and parameter.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        ]
        if needed and name not in ARGUMENTS:
            continue
        names.append(name)
    return names


def _foreign(value: object) -> "list[object]":
    """Return the pieces of *value* that a backend other than sdf owns."""
    pieces = list(value) if isinstance(value, (list, tuple)) else [value]
    return [piece for piece in pieces if getattr(piece, "backend", "sdf") != "sdf"]


def test_the_sweep_reaches_most_of_the_class() -> None:
    """A sweep that skipped nearly everything would pass the real check for the wrong reason."""
    from pybosl2.sdf.shapes3d import SdfSolid

    members = {n: (m.__func__ if isinstance(m, staticmethod) else m) for n, m in vars(SdfSolid).items()}
    public = [n for n, m in members.items() if not n.startswith("_") and callable(m)]
    swept = _swept_names()
    assert len(swept) > 50, f"the sweep reaches only {len(swept)} of {len(public)} methods: {sorted(swept)}"
    assert set(UNSWEPT) <= set(public), (
        f"UNSWEPT names methods SdfSolid does not have: {sorted(set(UNSWEPT) - set(public))} -- "
        f"the same stale-record failure mode as spec/layers.toml's debt rows (T50, T56)"
    )
    assert set(ARGUMENTS) <= set(public), f"ARGUMENTS is stale: {sorted(set(ARGUMENTS) - set(public))}"


@pytest.mark.parametrize("name", _swept_names())
def test_no_sdf_method_hands_back_a_solid_the_csg_backend_owns(name: str) -> None:
    """Under `sdf`: an sdf-backed result, or a refusal naming the call. Never a CSG solid.

    This is the whole check, and it needs no list of suspects -- which is the point. Six methods
    failed it before T135 and the one that was *typed* `-> tuple[Self, Self]` failed it as loudly
    as the five typed `-> PyShape`, because what a method returns is not what it says it returns.
    """
    args, kwargs = ARGUMENTS.get(name, ((), {}))
    refusal: UnsupportedByBackendError | None = None
    result: object = None
    with use_backend("sdf"):
        solid = _solid()
        try:
            result = getattr(solid, name)(*args, **kwargs)
        except UnsupportedByBackendError as raised:
            refusal = raised
        except Bosl2Error:
            return  # a library error naming its own problem is a different contract (E-1)
    if refusal is not None:
        assert name in str(refusal), (
            f"{name}() refuses the sdf backend without naming itself: {refusal}. A refusal a "
            f"caller cannot act on is the defect T51 and T53 both found (SPEC E-6)."
        )
        return
    foreign = _foreign(result)
    assert not foreign, (
        f"{name}() returned {[type(p).__name__ for p in foreign]} with backend="
        f'{[getattr(p, "backend", None) for p in foreign]} from inside `use_backend("sdf")`. A '
        f"solid the other backend owns will not combine with the fields around it, and nothing "
        f"said so (SPEC A-6). Answer in the field, or refuse under this method's own name."
    )


def test_the_sweep_can_see_a_foreign_solid() -> None:
    """The control: the assertion above has to be able to fail."""
    with use_backend("sdf"):
        from pybosl2.shapes3d import cuboid as csg_cuboid

        with use_backend("csg"):
            leaked = csg_cuboid(size=10)
        assert _foreign(leaked) == [leaked], "a csg solid is not seen as foreign; the sweep is blind"
        assert _foreign([leaked, leaked]) == [leaked, leaked], "a returned list is not unpacked"
        assert _foreign(_solid()) == [], "an sdf solid is reported foreign; the sweep cries wolf"


# ---------------------------------------------------------------------------
# The static half: who crosses the boundary at all.
# ---------------------------------------------------------------------------


def _crossings(sources: "dict[str, str]") -> "dict[str, str]":
    """Return every function in *sources* that calls `to_csg()`, keyed `path::name`."""
    found: dict[str, str] = {}
    for path, source in sources.items():
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Attribute)
                    and inner.func.attr == "to_csg"
                ):
                    found[f"{path}::{node.name}"] = ast.unparse(inner)
                    break
    return found


def _sdf_sources() -> "dict[str, str]":
    return {str(path.relative_to(ROOT)): path.read_text() for path in sorted(SDF.rglob("*.py"))}


def test_only_the_declared_crossings_mesh_inside_the_sdf_backend() -> None:
    """The ratchet. A new `to_csg()` in the SDF backend has to say why it is not the defect above.

    Cheap, and it catches the thing the sweep cannot reach: a method that needs arguments nobody
    has thought to put in `ARGUMENTS`, or a module-level function the sweep never sees.
    """
    undeclared = {k: v for k, v in _crossings(_sdf_sources()).items() if k not in CROSSES_AND_RETURNS}
    assert not undeclared, (
        "these mesh the field inside the SDF backend without declaring that what they return is "
        "still a field (SPEC A-6, B-5):\n  "
        + "\n  ".join(f"{name} -- {call}" for name, call in sorted(undeclared.items()))
        + "\nAnswer in the field, refuse under the caller's own name, or add it to "
        "CROSSES_AND_RETURNS with the reason the result comes back across."
    )


def test_the_crossing_list_has_not_gone_stale() -> None:
    """An entry for a call that no longer exists makes the residue look bigger than it is."""
    stale = sorted(set(CROSSES_AND_RETURNS) - set(_crossings(_sdf_sources())))
    assert not stale, f"CROSSES_AND_RETURNS lists calls that are gone: {stale} -- delete them"


def test_the_static_scan_sees_a_planted_crossing() -> None:
    """The control for the static half."""
    planted = textwrap.dedent(
        '''
        def looks_like_a_field_operation(self) -> "PyShape":
            """Meshes and hands the mesh back."""
            return self.to_csg().repair()
        '''
    )
    found = _crossings({"pybosl2/sdf/planted.py": planted})
    assert "pybosl2/sdf/planted.py::looks_like_a_field_operation" in found, f"the scan missed a plain crossing: {found}"
    assert _crossings({"pybosl2/sdf/clean.py": "def f(self) -> int:\n    return 1\n"}) == {}, (
        "the scan reports a function that never meshes, so it cannot tell the two apart"
    )

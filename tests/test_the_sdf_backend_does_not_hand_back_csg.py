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
and look at what comes back.

**T137 found two things this file had been reading too narrowly.** The sweep walked `SdfSolid`
only, which is the gap T34 had already found once in `tests/test_backend_parity.py` and closed
there by walking `PyShape2D` as well -- it walks both here now. And `to_csg()` was called "the one
declared door across the boundary", which it is not: `mesh()` returns the `frep()` handle, a CSG
solid in all but name, and `SdfShape2D.__getattr__` went out through it for *every* attribute miss
and handed back whatever the mesh had. The static half watches both doors now, so a function that
crosses either one has to say why what it returns is still a field.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import textwrap
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

import pytest

from pybosl2 import use_backend
from pybosl2._edges_lang import Anchor
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

#: The 2-D class's own two. `bounds`/`anchor_point` return a measurement, not geometry, so calling
#: them in a loop measures nothing -- the rest of the class is swept, refusals included.
UNSWEPT_2D: dict[str, str] = {
    "bounds": "returns a `Bounds2D`",
    "anchor_point": "returns a point",
}

#: As `ARGUMENTS`, for the 2-D class. `union`/`union2d` are left out for the reason the solid's
#: are: they take a list of shapes, which this module cannot build at import time.
ARGUMENTS_2D: dict[str, tuple[tuple[Any, ...], dict[str, Any]]] = {
    "back": ((5.0,), {}),
    "extrude": ((5.0,), {}),
    "forward": ((5.0,), {}),
    "left": ((5.0,), {}),
    "linear_extrude": ((5.0,), {}),
    "mirror": (([1.0, 0.0],), {}),
    "multmatrix": (([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],), {}),
    "outline": ((1.0,), {}),
    "reanchor": ((Anchor.LEFT,), {}),
    "right": ((5.0,), {}),
    "rotate": ((30.0,), {}),
    "scale": ((2.0,), {}),
    "translate": (([1.0, 2.0],), {}),
    "with_nominal_size": (([10.0, 10.0],), {}),
}

#: The names that cross the boundary at all. `to_csg()` returns a CSG solid outright; `mesh()`
#: returns the `frep()` handle, which is one in all but name -- and is the door the 2-D attribute
#: fallback used for every attribute miss while the ratchet below watched only the first (T137).
DOORS = ("to_csg", "mesh")

#: Calls inside the SDF backend that cross the boundary and come back, with the reason.
#: The list only shrinks. An entry is a declaration that the method returns a *field* despite
#: meshing on the way, which the dynamic sweep below then holds it to.
#: `pybosl2/sdf/shapes2d.py::hull` was the first entry here, declared as "goes out through the
#: 3-D hull's `projection` and comes back as a `polygon2d` -- lossy (B-5) and recorded as such".
#: T139 deleted it by removing the crossing: the hull is computed from each shape's own
#: extreme-point claim now, with no mesh and no conversion. **The crossing this list was
#: accepting had never produced a hull** -- `projection()` returns a `CsgShape2D`, which has no
#: `.paths`, so the method fell through to `return self`. An exemption is a claim like any other.
CROSSES_AND_RETURNS: dict[str, str] = {
    "pybosl2/sdf/shapes3d.py::show": "hands the mesh to the viewer; its return value is not geometry",
    "pybosl2/sdf/shapes3d.py::_baked": (
        "the render-time hook. Meshing is what it is for, and what it returns goes to the "
        "renderer rather than back to the caller."
    ),
    "pybosl2/sdf/shapes3d.py::__getattr__": (
        "the solid's attribute fallback forwards the names in `_MESH_OPERATIONS` -- operations "
        "that consume or produce mesh topology -- and refuses everything else (T3). The 2-D one "
        "forwarded *every* name and is not on this list, because it no longer crosses at all."
    ),
    "pybosl2/sdf/shapes3d.py::hull": (
        "the crossing is in its nested `planes` helper, declared next -- the scan walks a "
        "function's whole body, inner definitions included, so the enclosing name is listed too. "
        "`hull` itself returns a `PyShape` built from the plane coefficients."
    ),
    "pybosl2/sdf/shapes3d.py::planes": (
        "reads the vertices out of a child's mesh to build half-space coefficients. What comes "
        "back is four floats per plane, not a solid."
    ),
    "pybosl2/sdf/skin.py::mesh_to_vnf": (
        "reads vertices and faces out of the mesh and returns them as a plain pair -- neutral "
        "geometry that belongs to no backend (SPEC C-16)."
    ),
}


def _solid() -> Any:
    from pybosl2.solid import cuboid

    return cuboid([10.0, 10.0, 10.0])


def _flat() -> Any:
    from pybosl2.sdf.shapes2d import circle2d

    return circle2d(radius=5)


def _sdf_classes() -> "dict[str, tuple[type, Callable[[], Any], dict[str, str], dict[str, Any]]]":
    """The SDF shape classes the sweep walks: the solid *and* the 2-D field.

    Both, because walking only the solid is how `fill` stayed broken (T34) and how the 2-D
    attribute fallback stayed broken after that (T137). The second time it was this file's sweep
    that was looking at one class, having been written in the belief that the solid was where the
    defects were -- which was true of the six T135 found and said nothing about the other class.
    """
    from pybosl2.sdf.shapes2d import SdfShape2D
    from pybosl2.sdf.shapes3d import SdfSolid

    return {
        "SdfSolid": (SdfSolid, _solid, UNSWEPT, ARGUMENTS),
        "SdfShape2D": (SdfShape2D, _flat, UNSWEPT_2D, ARGUMENTS_2D),
    }


def _swept_names(label: str = "SdfSolid") -> list[str]:
    """Every public method of *label*'s class that the sweep can call, from the class itself."""
    cls, _build, unswept, arguments = _sdf_classes()[label]

    names = []
    for name, raw in sorted(vars(cls).items()):
        member = raw.__func__ if isinstance(raw, staticmethod) else raw
        if name.startswith("_") or not callable(member) or name in unswept:
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
        if needed and name not in arguments:
            continue
        names.append(name)
    return names


def _cases() -> list[tuple[str, str]]:
    """Every (class, method) pair the sweep calls -- parametrised so xdist spreads them."""
    return [(label, name) for label in sorted(_sdf_classes()) for name in _swept_names(label)]


def _foreign(value: object) -> "list[object]":
    """Return the pieces of *value* that a backend other than sdf owns."""
    pieces = list(value) if isinstance(value, (list, tuple)) else [value]
    return [piece for piece in pieces if getattr(piece, "backend", "sdf") != "sdf"]


#: How much of each class the sweep has to reach for the check below to mean anything.
REACH = {"SdfSolid": 50, "SdfShape2D": 25}


@pytest.mark.parametrize("label", sorted(REACH))
def test_the_sweep_reaches_most_of_the_class(label: str) -> None:
    """A sweep that skipped nearly everything would pass the real check for the wrong reason."""
    cls, _build, unswept, arguments = _sdf_classes()[label]

    members = {n: (m.__func__ if isinstance(m, staticmethod) else m) for n, m in vars(cls).items()}
    public = [n for n, m in members.items() if not n.startswith("_") and callable(m)]
    swept = _swept_names(label)
    assert len(swept) > REACH[label], (
        f"the sweep reaches only {len(swept)} of {len(public)} {label} methods: {sorted(swept)}"
    )
    assert set(unswept) <= set(public), (
        f"the unswept list names methods {label} does not have: {sorted(set(unswept) - set(public))} -- "
        f"the same stale-record failure mode as spec/layers.toml's debt rows (T50, T56)"
    )
    assert set(arguments) <= set(public), f"the argument table is stale: {sorted(set(arguments) - set(public))}"


@pytest.mark.parametrize(("label", "name"), _cases())
def test_no_sdf_method_hands_back_a_solid_the_csg_backend_owns(label: str, name: str) -> None:
    """Under `sdf`: an sdf-backed result, or a refusal naming the call. Never a CSG solid.

    This is the whole check, and it needs no list of suspects -- which is the point. Six methods
    failed it before T135 and the one that was *typed* `-> tuple[Self, Self]` failed it as loudly
    as the five typed `-> PyShape`, because what a method returns is not what it says it returns.
    """
    _cls, build, _unswept, arguments = _sdf_classes()[label]
    args, kwargs = arguments.get(name, ((), {}))
    refusal: UnsupportedByBackendError | None = None
    result: object = None
    with use_backend("sdf"):
        solid = build()
        try:
            result = getattr(solid, name)(*args, **kwargs)
        except UnsupportedByBackendError as raised:
            refusal = raised
        except Bosl2Error:
            return  # a library error naming its own problem is a different contract (E-1)
    if refusal is not None:
        assert name in str(refusal), (
            f"{label}.{name}() refuses the sdf backend without naming itself: {refusal}. A refusal "
            f"a caller cannot act on is the defect T51 and T53 both found (SPEC E-6)."
        )
        return
    foreign = _foreign(result)
    assert not foreign, (
        f"{label}.{name}() returned {[type(p).__name__ for p in foreign]} with backend="
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
    """Return every function in *sources* that goes through a door in `DOORS`, keyed `path::name`.

    A docstring is stripped before the body is scanned. Prose that *mentions* the call reads as the
    call to `ast.unparse`, which is how T133's first scan over-matched and how this one did too.
    """
    found: dict[str, str] = {}
    for path, source in sources.items():
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            statements = node.body[1:] if ast.get_docstring(node) is not None else node.body
            for statement in statements:
                crossing = next(
                    (
                        inner
                        for inner in ast.walk(statement)
                        if isinstance(inner, ast.Call)
                        and isinstance(inner.func, ast.Attribute)
                        and inner.func.attr in DOORS
                    ),
                    None,
                )
                if crossing is not None:
                    found[f"{path}::{node.name}"] = ast.unparse(crossing)
                    break
    return found


def _sdf_sources() -> "dict[str, str]":
    return {str(path.relative_to(ROOT)): path.read_text() for path in sorted(SDF.rglob("*.py"))}


def test_only_the_declared_crossings_mesh_inside_the_sdf_backend() -> None:
    """The ratchet. A new crossing in the SDF backend has to say why it is not the defect above.

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

    # The second door, which is the one the defect went out through: the pre-T137 fallback,
    # verbatim. A scan that watched `to_csg` alone reported this function as clean.
    other = textwrap.dedent(
        """
        def __getattr__(self, name: str):
            return getattr(self.extrude(0.01).mesh(), name)
        """
    )
    assert "pybosl2/sdf/planted.py::__getattr__" in _crossings({"pybosl2/sdf/planted.py": other}), (
        "the scan misses `mesh()`, so it would miss the T137 defect exactly as it did"
    )

    assert _crossings({"pybosl2/sdf/clean.py": "def f(self) -> int:\n    return 1\n"}) == {}, (
        "the scan reports a function that never meshes, so it cannot tell the two apart"
    )

    # A docstring that names a door is prose, not a crossing.
    prose = '''def f(self) -> int:\n    """Unlike to_csg(), this stays in the field."""\n    return 1\n'''
    assert _crossings({"pybosl2/sdf/prose.py": prose}) == {}, "the scan reads docstrings as code (T133)"

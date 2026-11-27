# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A shape handed to a *call* cannot come from the other backend either (SPEC A-6, E-1, E-3).

SPEC E-3 says "cross-backend mixing names both operands and the conversion that resolves it", and
it was marked `enforced` by `tests/test_backend_crossbackend.py` -- which walks the three boolean
operators. An argument is the other way to mix, and nothing walked it. T138 measured 38 ways to
hand a call a shape from the other backend, in the real PythonSCAD app with libfive present, and
**29 did not report honestly**:

* **16** raised a raw ``TypeError``/``AttributeError`` -- "Error during parsing hull. arguments
  must be solids or arrays" from the native parser, ``float() argument must be a string or a real
  number, not 'CsgSolid'`` from inside `SdfSolid.hull`'s point-set branch, ``'openscad.PyOpenSCAD'
  object has no attribute '_sdf_fn'``. None is a `Bosl2Error`, so the documented
  ``except Bosl2Error`` could not catch any of them (SPEC E-6).
* **8** raised a catchable error that named the wrong thing: an internal class (``every argument
  must be a PyShape, got ['CsgSolid']``) or an inner call (``bounds(): object has no native
  bounding box``), never the call the caller made and never the conversion (SPEC E-1).
* **3** built a wrong answer in silence. `SdfSolid.minkowski` reads only `other.bounds()`, which a
  `CsgSolid` answers, so it dilated by the foreign solid's inscribed ball and returned an
  `SdfSolid` that looked right. `SdfShape2D.union` is a `staticmethod`, so `sdf_2d.union([csg_2d])`
  returned the **CSG** shape -- a shape on a backend the receiver did not own (SPEC A-6).
* **2** returned successfully and failed later. `position` and `edge_mask` stash the child or
  cutter in `attachments` and combine at realize time, so the error surfaced as ``TypeError:
  invalid argument left to operator`` inside `_realize_node`, a frame the caller never wrote.
  Measured: the same box rendered 92 triangles with a CSG cutter and **nothing at all** with an
  SDF one.

Only 7 refused correctly; 2 more (`VNF.from_solid` in either direction) are legitimate crossings,
because a VNF is neutral geometry and meshing a field is the sanctioned SDF->CSG direction (B-5).

`require_same_backend` is the argument form of `check_operand_backend`, and this file is its
ratchet. Every case below is run **twice** -- once mixed, which must refuse under the call's own
name, and once with both shapes on the call's backend, which must still build. A guard that
refused everything would pass the first half and fail the second.
"""

import ast
import pathlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

import pytest

import pybosl2.miscellaneous as misc
import pybosl2.shapes2d.ops as ops2
from pybosl2 import flat, solid
from pybosl2._backend import use_backend
from pybosl2._edges_lang import Anchor
from pybosl2.exceptions import CrossBackendError
from pybosl2.path2d import Path2D
from pybosl2.shapes3d.cuboid import roof as _roof

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "pybosl2"


def _shape(backend: str, dim: int) -> Any:
    """Build a fresh shape on *backend* in *dim* dimensions.

    Fresh each time, and **outside** the probed call's context: building the "other" operand
    inside `use_backend(...)` is how T138's first probe accidentally measured nothing at all --
    three cases followed the active backend and were never cross-backend.
    """
    with use_backend(backend):
        return flat.circle(radius=5) if dim == 2 else solid.sphere(radius=5)


def _box(backend: str) -> Any:
    with use_backend(backend):
        return solid.cuboid([20, 20, 10])


def _cutter(backend: str) -> Any:
    with use_backend(backend):
        return solid.cyl(height=30, radius=2)


@dataclass(frozen=True)
class Case:
    """One way to hand a call a shape.

    Attributes:
        label: pytest id.
        call: the name the refusal must carry -- the call the caller made (SPEC E-1).
        backend: the backend the call builds on, which the shapes must share.
        run: performs the call; given a maker for shapes on *backend* and one for the operand
            under test, so the same lambda serves both the mixed and the same-backend run.
    """

    label: str
    call: str
    backend: str
    run: Callable[[Callable[[int], Any], Callable[[int], Any]], Any]
    refused_before: bool = False
    """True if this case already raised `CrossBackendError` before T138, by another route.

    Four do: the three free functions in `pybosl2.solid` reach the backend implementation, which
    combines through an operator and so consults `check_operand_backend`, and a multi-shape
    `SdfShape2D.union` folds pairwise through `__or__`. For those, T138's contribution is the
    *name* in the message, not the refusal -- and saying so is the difference between a control
    that measures the guard and one that credits it with work it did not do.
    """


def _other(backend: str) -> str:
    return "sdf" if backend == "csg" else "csg"


CASES: tuple[Case, ...] = (
    # --- the free-function booleans, whose docstrings have always said operands share a backend
    Case("union-free", "union", "csg", lambda own, arg: solid.union(own(3), arg(3)), refused_before=True),
    Case(
        "difference-free",
        "difference",
        "csg",
        lambda own, arg: solid.difference(own(3), arg(3)),
        refused_before=True,
    ),
    Case(
        "intersection-free",
        "intersection",
        "csg",
        lambda own, arg: solid.intersection(own(3), arg(3)),
        refused_before=True,
    ),
    Case("union-free-sdf", "union", "sdf", lambda own, arg: solid.union(own(3), arg(3))),
    # --- n-ary methods on each backend
    # All three of these fall through to the native passthrough, and none of them worked before
    # T138 -- with any argument, on any backend. The same-backend leg is what says so.
    Case("csg-union-method", "union", "csg", lambda own, arg: own(3).union(arg(3))),
    Case("csg-intersection-method", "intersection", "csg", lambda own, arg: own(3).intersection(arg(3))),
    Case("csg-difference-method", "difference", "csg", lambda own, arg: own(3).difference(arg(3))),
    Case("sdf-union-method", "union", "sdf", lambda own, arg: own(3).union([own(3), arg(3)])),
    Case("sdf-intersection", "intersection", "sdf", lambda own, arg: own(3).intersection(arg(3))),
    Case("sdf-2d-union-fold", "union", "sdf", lambda own, arg: own(2).union([own(2), arg(2)]), refused_before=True),
    # The single-element form is the one that built a wrong answer: a `staticmethod` with
    # nothing to fold returns its one shape, so this handed back the *CSG* shape from a call
    # on an SDF one. Nothing refused, and nothing was wrong enough to notice.
    Case("sdf-2d-union-single", "union", "sdf", lambda own, arg: own(2).union([arg(2)])),
    # --- hull, chain_hull, minkowski on both backends and both dimensions
    Case("csg-2d-hull", "hull", "csg", lambda own, arg: own(2).hull(arg(2))),
    Case("csg-3d-hull", "hull", "csg", lambda own, arg: own(3).hull(arg(3))),
    # `SdfShape2D.hull` builds here and not in the real app, where the 0.01 slab it extrudes
    # meshes to nothing for *any* operand -- measured identical on `main`, so pre-existing and
    # recorded under T138's "Found and not fixed" rather than asserted either way. The mixed leg
    # is the one that matters: it refuses before reaching that.
    Case("sdf-2d-hull", "hull", "sdf", lambda own, arg: own(2).hull(arg(2))),
    Case("sdf-3d-hull", "hull", "sdf", lambda own, arg: own(3).hull(arg(3))),
    Case("csg-chain-hull", "chain_hull", "csg", lambda own, arg: own(3).chain_hull(arg(3))),
    Case("sdf-chain-hull", "chain_hull", "sdf", lambda own, arg: own(3).chain_hull(arg(3))),
    Case("sdf-minkowski", "minkowski", "sdf", lambda own, arg: own(3).minkowski(arg(3))),
    Case("csg-mink-diff", "minkowski_difference", "csg", lambda own, arg: own(3).minkowski_difference(arg(3))),
    Case("sdf-mink-diff", "minkowski_difference", "sdf", lambda own, arg: own(3).minkowski_difference(arg(3))),
    Case("misc-chain-hull", "chain_hull", "csg", lambda own, arg: misc.chain_hull(own(3), arg(3))),
    Case("misc-mink-diff", "minkowski_difference", "csg", lambda own, arg: misc.minkowski_difference(own(3), arg(3))),
    # --- the 2-D ops, which coerce a child to a native handle
    Case("ops-hull", "hull", "csg", lambda own, arg: ops2.hull(own(2), arg(2))),
    Case("ops-fill", "fill", "csg", lambda _own, arg: ops2.fill(arg(2))),
    Case("ops-round2d", "round2d", "csg", lambda _own, arg: ops2.round2d(radius=1, children=arg(2))),
    Case("ops-shell2d", "shell2d", "csg", lambda _own, arg: ops2.shell2d(thickness=1, children=arg(2))),
    # --- the extrusions, which take a 2-D profile
    Case(
        "extrude-from-to",
        "extrude_from_to",
        "csg",
        lambda _own, arg: misc.extrude_from_to(arg(2), [0, 0, 0], [0, 0, 10]),
    ),
    Case(
        "cylindrical-extrude",
        "cylindrical_extrude",
        "csg",
        lambda _own, arg: misc.cylindrical_extrude(arg(2), inner_radius=10, outer_radius=12),
    ),
    Case(
        "path-extrude2d",
        "path_extrude2d",
        "csg",
        lambda _own, arg: Path2D([[0, 0], [10, 0], [10, 10]]).path_extrude2d(arg(2)),
    ),
    Case(
        "path-extrude",
        "path_extrude",
        "csg",
        lambda _own, arg: Path2D([[0, 0], [10, 0], [10, 10]]).path_extrude(arg(2)),
    ),
    # --- attachment and masking, which defer the combine to realize time
    Case("attach", "attach", "csg", lambda _own, arg: _box("csg").attach(Anchor.TOP, arg(3))),
    Case("position", "position", "csg", lambda _own, arg: _box("csg").position(Anchor.TOP, arg(3))),
    Case("align", "align", "csg", lambda _own, arg: _box("csg").align(Anchor.TOP, arg(3))),
    Case("edge-mask", "edge_mask", "csg", lambda _own, arg: _box("csg").edge_mask(Anchor.ALL, mask=_cutter_like(arg))),
)


def _cutter_like(arg: Callable[[int], Any]) -> Any:
    """A cylinder on whichever backend *arg* builds on -- a sphere makes a poor edge cutter."""
    return _cutter(_backend_of(arg))


def _maker(backend: str) -> Callable[[int], Any]:
    """A fresh-shape factory for *backend*, tagged so a case can ask which backend it makes."""

    def make(dim: int) -> Any:
        return _shape(backend, dim)

    make.backend = backend  # type: ignore[attr-defined]
    return make


def _backend_of(arg: Callable[[int], Any]) -> str:
    return cast("str", arg.backend)  # type: ignore[attr-defined]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.label)
def test_a_foreign_shape_is_refused_under_the_calls_own_name(case: Case) -> None:
    """A shape from the other backend raises CrossBackendError naming the call (SPEC E-1, E-3)."""
    own, foreign = _maker(case.backend), _maker(_other(case.backend))
    with pytest.raises(CrossBackendError) as ei, use_backend(case.backend):
        case.run(own, foreign)
    exc = ei.value
    assert exc.call == case.call, f"refused under {exc.call!r}, not the call the caller made"
    message = str(exc)
    assert f"{case.call}()" in message
    assert case.backend in message, "the message names the backend the call builds on"
    assert _other(case.backend) in message, "the message names the backend the shape came from"
    # The conversion that resolves it, and only the direction that exists: SDF->CSG is an exact
    # mesh, CSG->SDF is lossy and deliberately absent, so a message offering `to_sdf()` would be
    # pointing at a call that raises (SPEC B-5).
    assert ("to_csg" in message) if _other(case.backend) == "sdf" else ('use_backend("sdf")' in message)
    assert "to_sdf" not in message


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.label)
def test_the_same_call_builds_when_the_shapes_share_a_backend(case: Case) -> None:
    """The guard refuses a *mix*, not every argument -- without this the table proves nothing."""
    own = _maker(case.backend)
    with use_backend(case.backend):
        result = case.run(own, own)
    assert result is not None
    tag = getattr(result, "backend", case.backend)
    assert tag == case.backend, f"built on {tag!r} rather than the backend the call was given"


def test_the_probes_can_fail() -> None:
    """With the guard neutralised everywhere, every case stops reporting a CrossBackendError.

    The guard is bound in several modules at once, so patching one would leave the rest standing
    and the control would pass while measuring almost nothing. The bindings are read out of the
    source rather than listed here, so a module added later is neutralised too -- and the required
    set below names the ones the cases actually travel through, so a binding disappearing from any
    of them fails here instead of quietly blinding the control.
    """
    bindings = _modules_binding_the_guard()
    # Both halves of the library and all three layers the guard sits in, so a control that
    # neutralises "the guard" is neutralising it everywhere the cases travel.
    modules = {module for module, _ in bindings}
    for required in (
        "pybosl2._shape",
        "pybosl2.solid",
        "pybosl2.miscellaneous",
        "pybosl2.shapes2d.base",
        "pybosl2.sdf.shapes2d",
        "pybosl2.sdf.shapes3d",
    ):
        assert required in modules, f"{required} no longer binds the guard; the control is blind there"

    def noop(call: str, backend: str, *operands: Any) -> None:  # noqa: ARG001 -- a stand-in that checks nothing
        return None

    import importlib

    saved: list[tuple[Any, str, Any]] = []
    # `pybosl2._backend` itself first: three sites in `shapes3d/base.py` import the guard inside
    # the function that uses it, to keep that module off `_backend` at import time, and those
    # resolve the name at call time -- so patching the attribute there is what reaches them. Named
    # aliases are patched as well, because those resolved at import time and would not notice.
    import pybosl2._backend as backend_module

    saved.append((backend_module, "require_same_backend", backend_module.require_same_backend))
    backend_module.require_same_backend = noop  # type: ignore[assignment]
    for module_name, alias in sorted(bindings):
        module = importlib.import_module(module_name)
        saved.append((module, alias, getattr(module, alias)))
        setattr(module, alias, noop)
    try:
        unguarded: dict[str, bool] = {}
        unnamed: list[str] = []
        for case in CASES:
            own, foreign = _maker(case.backend), _maker(_other(case.backend))
            try:
                with use_backend(case.backend):
                    case.run(own, foreign)
                unguarded[case.label] = False
            except CrossBackendError as exc:
                unguarded[case.label] = True
                if exc.call is None:
                    unnamed.append(case.label)
            except Exception:  # anything else is the old, dishonest behaviour returning
                unguarded[case.label] = False

        wrongly_still_refusing = [case.label for case in CASES if not case.refused_before and unguarded[case.label]]
        assert not wrongly_still_refusing, (
            "these refused with the guard removed, so the guard is not what makes them refuse: "
            f"{wrongly_still_refusing}"
        )
        stopped_refusing = [case.label for case in CASES if case.refused_before and not unguarded[case.label]]
        assert not stopped_refusing, (
            "these are recorded as refusing by another route before T138, and now do not -- "
            f"the record is wrong or the other route is gone: {stopped_refusing}"
        )
        # And the four that did refuse before said so without naming the call, which is the part
        # T138 changed for them.
        assert sorted(unnamed) == sorted(case.label for case in CASES if case.refused_before), (
            "a case recorded as already-refusing names its call without the guard, so the guard "
            f"is not what adds the name: named={sorted(set(unguarded) - set(unnamed))}"
        )
    finally:
        for module, alias, original in saved:
            setattr(module, alias, original)


def _modules_binding_the_guard() -> set[tuple[str, str]]:
    """Return every ``(module, name)`` under `pybosl2` that imports the guard at module level.

    A deferred import inside a function body cannot be patched through the module, so those are
    reported separately by :func:`test_every_guard_binding_is_patchable`.
    """
    found: set[tuple[str, str]] = set()
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in tree.body:  # module level only
            if isinstance(node, ast.ImportFrom) and node.module == "pybosl2._backend":
                for alias in node.names:
                    if alias.name == "require_same_backend":
                        module = ".".join(("pybosl2", *path.relative_to(PACKAGE).with_suffix("").parts))
                        found.add((module, alias.asname or alias.name))
    return found


def test_every_guard_binding_is_patchable() -> None:
    """No module imports the guard inside a function, so the control reaches every call site.

    A guard imported inside the function that uses it is invisible to a control that patches the
    module, and the case it protects would pass `test_the_probes_can_fail` by never having been
    disabled. Three sites in `shapes3d/base.py` were written that way, following the local-import
    style the file uses to break cycles -- and that file already imports `pybosl2._backend` at the
    top, so there was no cycle to break and they are module-level now. This asserts the set is
    empty rather than listing exceptions: a local import has to be justified by making this fail.
    """
    local_imports: dict[str, set[str]] = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.ImportFrom)
                    and inner.module == "pybosl2._backend"
                    and any(a.name == "require_same_backend" for a in inner.names)
                ):
                    rel = str(path.relative_to(PACKAGE))
                    local_imports.setdefault(rel, set()).add(node.name)
    assert not local_imports, (
        "the guard is imported inside a function here, where patching the module cannot reach it, "
        f"so the control would silently stop measuring these call sites: {local_imports}"
    )


#: The functions that turn a caller's object into geometry a native function will accept. Every
#: one of them ends by handing back what it was given if it recognises nothing, which is the route
#: a foreign shape took into the native layer.
COERCERS = frozenset(
    {
        "as_native_2d",
        "_as_native_2d",
        "_as_native_3d",
        "_profile_factory",
        "_as_shape_list",
    }
)


def test_every_coercion_site_names_the_call_it_serves() -> None:
    """Every call to a shape coercer passes ``call=``, so a new one cannot arrive unnamed.

    The coercers are where a foreign shape used to slip through: each ends by handing back
    whatever it was given, so an un-named call site is a route straight into the native layer.
    Requiring the name here is what makes the refusal carry the caller's own name (SPEC E-1)
    rather than an inner frame's, and it fails for a *new* site without anyone updating a list.
    """
    unnamed: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in COERCERS:
                continue
            if any(kw.arg == "call" for kw in node.keywords):
                continue
            # `_as_shape_list`'s name is positional-or-keyword with a default, so a positional
            # second argument names it just as well.
            if node.func.id == "_as_shape_list" and len(node.args) >= 2:
                continue
            unnamed.append(f"{path.relative_to(PACKAGE.parent)}:{node.lineno} {node.func.id}(...)")
    assert not unnamed, (
        "these coercion sites do not name their caller, so a cross-backend shape would pass: " + "; ".join(unnamed)
    )


def test_neutral_geometry_is_not_a_cross_backend_mix() -> None:
    """A VNF, Path2D or Region carries no backend tag, and handing one over is not mixing.

    The guard would be useless if it rejected these: they are how geometry legitimately moves
    between the two backends (SPEC B-5), and `VNF.from_solid` in either direction is a sanctioned
    crossing, not a mix. Checked here because the guard looks into `list`/`tuple` operands and
    `Path2D`/`Region` are both `list` subclasses -- without the `geometry()` test it would walk a
    path's coordinates instead of recognising it.
    """
    from pybosl2.regions import Region
    from pybosl2.vnf import VNF

    path = Path2D([[0, 0], [10, 0], [10, 10]])
    with use_backend("csg"):
        # The triangle spans 0..10 and the circle -5..5, so a hull that used both is 15 across.
        assert [round(float(v), 3) for v in ops2.hull(path, flat.circle(radius=5)).bounds().size] == [15.0, 15.0]
        # The path extruded 5 tall: the 10x10 triangle's own box, with the height asked for.
        extruded = misc.extrude_from_to(path, [0, 0, 0], [0, 0, 5])
        assert [round(float(v), 3) for v in extruded.bounds().size] == [10.0, 10.0, 5.0]
        filled = ops2.fill(Region([[[0, 0], [10, 0], [10, 10]]]))
        assert [round(float(v), 3) for v in filled.bounds().size] == [10.0, 10.0]
    # A VNF carries no `backend`, so handing one to either backend is not a mix. Checked with a
    # CSG solid: `VNF.from_solid` on an *SDF* field needs a real mesher, and libfive ships only
    # inside the PythonSCAD app, so asserting it here could only ever measure the numeric mock
    # (the same reason `test_backend_crossbackend.py` leaves the SDF->CSG happy path to a render
    # test). The direction this test exists for -- that a VNF is not refused -- is below.
    with use_backend("csg"):
        mesh = VNF.from_solid(solid.cuboid([10, 10, 10]))
    assert getattr(mesh, "backend", None) is None, "a VNF must stay untagged, or the guard would refuse it"
    assert (len(mesh.vertices), len(mesh.faces)) == (8, 6), "a cube's mesh, so the VNF really carries one"
    # And it goes into an SDF n-ary call -- the same call that refuses a CSG shape -- because
    # `polyhedron()` realises the neutral mesh on whichever backend is active.
    with use_backend("sdf"):
        combined = solid.sphere(radius=5).union([solid.sphere(radius=5), mesh.polyhedron()])
    assert [round(float(v), 3) for v in combined.bounds().size] == [10.0, 10.0, 10.0]


def test_a_point_list_is_still_a_point_list() -> None:
    """A bare ``[[x, y], ...]`` and an Nx3 point set stay acceptable arguments, and still count.

    `SdfSolid.hull` takes point sets as well as shapes and the guard sits in front of the branch
    that reads them, so refusing a list outright would have been an easy way to make every mixed
    case pass. The bounds are asserted rather than mere existence, because a hull that quietly
    dropped the points would still return a shape: each box has to reach the points to prove they
    were used.
    """
    with use_backend("csg"):
        flat_hull = ops2.hull([[0, 0], [10, 0], [10, 10]], flat.circle(radius=5))
    box = flat_hull.bounds()
    # The circle spans -5..5 about the origin and the triangle 0..10, so the hull of the two
    # reaches the circle's low corner and the triangle's high one -- it used both.
    assert [round(float(v), 3) for v in box.min] == [-5.0, -5.0]
    assert [round(float(v), 3) for v in box.max] == [10.0, 10.0]

    with use_backend("sdf"):
        solid_hull = solid.sphere(radius=5).hull([[0.0, 0.0, 20.0], [1.0, 0.0, 20.0], [0.0, 1.0, 20.0]])
    box3 = solid_hull.bounds()
    # The points sit at z=20, twenty above a sphere that reaches z=5 on its own, so the top of the
    # box is the point set and the rest is the sphere.
    assert [round(float(v), 3) for v in box3.min] == [-5.0, -5.0, -5.0]
    assert [round(float(v), 3) for v in box3.max] == [5.0, 5.0, 20.0]


def test_roof_refuses_a_foreign_profile_by_its_own_name() -> None:
    """`roof` is CSG-only and already refused honestly -- recorded so the set stays complete.

    T137 gave `SdfShape2D.__getattr__` a contract, and this is one of the things that fixed: a 2-D
    field handed to `roof` reports `'roof' is not supported by the 'sdf' backend` rather than
    reaching for geometry. It is an `UnsupportedByBackendError`, not a `CrossBackendError`, because
    the operation genuinely does not exist on a field -- a different answer from the same question.
    """
    from pybosl2.exceptions import UnsupportedByBackendError

    with use_backend("sdf"):
        sdf_flat = flat.circle(radius=5)
    with pytest.raises(UnsupportedByBackendError) as ei, use_backend("csg"):
        _roof(sdf_flat)
    assert "roof" in str(ei.value)

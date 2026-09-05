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


@pytest.mark.parametrize("convexity", [None, 1, 4])
def test_convexity_is_accepted_by_every_extrude_on_both_backends(convexity: int | None) -> None:
    """`convexity` is a renderer hint, and three of the four extrude methods took it as one.

    It tells a previewer how many times a ray can cross the surface. It changes no geometry, and a
    distance field has no use for it at all -- which is why `SdfShape2D.rotate_extrude` already
    accepted and ignored it. Its sibling `linear_extrude` did not accept it, so
    `flat.square(...).linear_extrude(height=5, convexity=4)` raised a bare `TypeError` from inside
    the backend: one class, two spellings of the same shared parameter (SPEC C-17, C-21, and B-9's
    tessellation carve-out).
    """
    import inspect

    from pybosl2 import flat
    from pybosl2.sdf.shapes2d import SdfShape2D
    from pybosl2.shapes2d.base import Bosl2Shape2D

    for shape in (SdfShape2D, Bosl2Shape2D):
        for method in ("linear_extrude", "rotate_extrude"):
            assert "convexity" in inspect.signature(getattr(shape, method)).parameters, (
                f"{shape.__name__}.{method} does not take convexity, so the same call is portable "
                f"to one backend and not the other"
            )

    extra = {} if convexity is None else {"convexity": convexity}
    sizes = {}
    for backend in ("csg", "sdf"):
        with use_backend(backend):
            built = flat.square(size=[10, 6]).linear_extrude(height=5, **extra)
            sizes[backend] = [round(float(v), 2) for v in built.bounds().size]
    assert sizes["csg"] == sizes["sdf"], f"convexity={convexity} changed the geometry: {sizes}"


@pytest.mark.parametrize("method", ["path_extrude", "path_extrude2d"])
def test_the_path_extrusions_refuse_rather_than_failing_from_inside(method: str) -> None:
    """They are CSG-only in fact, and now in the contract (SPEC E-1, E-6, B-9).

    Both are built out of native primitives -- `path_extrude` clips with `pythonscad.cube`, and
    `path_extrude2d` takes its corner fillets from `_planar_half`, which cuts with
    `pythonscad.square` -- so neither follows the active backend however the profile is dispatched.

    Under `use_backend("sdf")` they used to fail *from inside*: `AttributeError: 'PyOpenSCAD'
    object has no attribute '_sdf_fn'`, and `every argument must be a PyShape, got ['PyOpenSCAD']`.
    Neither is a `Bosl2Error`, so the documented `except Bosl2Error` could not catch them, and
    neither names the call the caller made.
    """
    from pybosl2.exceptions import Bosl2Error, UnsupportedByBackendError
    from pybosl2.path2d import Path2D
    from pybosl2.path3d import Path3D

    profile = Path2D([[0, 0], [4, 0], [4, 4], [0, 4]])
    path = (
        Path2D([[0, 0], [10, 0], [10, 8]])
        if method == "path_extrude2d"
        else Path3D([[0, 0, 0], [0, 0, 10], [6, 0, 16]])
    )

    with use_backend("csg"):
        assert getattr(path, method)(profile=profile).backend == "csg"

    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError) as excinfo:
        getattr(path, method)(profile=profile)
    assert isinstance(excinfo.value, Bosl2Error), "the documented `except Bosl2Error` has to catch it"
    assert method in str(excinfo.value), "and it names the call, not an attribute inside the backend"


def test_importing_regions_does_not_drag_in_a_backend_module() -> None:
    """A debug helper's dependency should not be every caller's import cost (SPEC A-1).

    `Region.debug_region(vertices=True)` labels each vertex with `text3d`, which renders a font
    and is CSG-only. It was imported at the top of `pybosl2.regions`, so `import pybosl2.regions`
    pulled a whole backend module in for a feature most callers never touch -- and made the edge a
    *runtime* upward import rather than a deferred one.
    """
    import subprocess
    import sys

    probe = "import pybosl2.regions, sys; print('pybosl2.shapes3d' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, cwd=ROOT)
    assert out.stdout.strip() == "False", f"importing pybosl2.regions still pulls in shapes3d: {out.stdout!r}"


@pytest.mark.parametrize(
    ("label", "build"),
    [
        (
            "a one-path region",
            lambda: __import__("pybosl2.regions", fromlist=["Region"]).Region([[[0, 0], [10, 0], [10, 10], [0, 10]]]),
        ),
        (
            "a two-path region",
            lambda: __import__("pybosl2.regions", fromlist=["Region"]).Region(
                [[[0, 0], [10, 0], [10, 10], [0, 10]], [[2, 2], [4, 2], [4, 4], [2, 4]]]
            ),
        ),
        ("a path", lambda: __import__("pybosl2.path2d", fromlist=["Path2D"]).Path2D([[0, 0], [10, 0], [10, 10]])),
    ],
)
def test_the_vertex_labels_refuse_under_a_name_the_caller_can_act_on(label: str, build) -> None:
    """B-9's per-option refusal, applied to a call that is only partly backend-neutral.

    These helpers build their outline through the façade and work on either backend; only the
    `vertices=True` labels need `text3d`, which renders a font and is CSG-only. So the refusal
    belongs on the *option*, the way `cyl(teardrop=)` refuses on the option rather than the shape.

    It used to surface `'pybosl2.shapes3d.extrusions.text3d' is not supported` -- an internal path
    three frames down, and nothing a caller can act on (SPEC E-5).

    **The same feature is written twice**, in `Region.debug_region` and `Path2D.debug_polygon`, and
    a one-path region *delegates* to the second -- so fixing only the first left the commonest case
    still reporting the old message. That is why the rule is one shared function and why a one-path
    region is a case here: it names `debug_polygon`, which is where it really is.
    """
    from pybosl2.exceptions import Bosl2Error, UnsupportedByBackendError

    shape = build()
    method = "debug_polygon" if hasattr(shape, "debug_polygon") else "debug_region"

    for backend in ("csg", "sdf"):
        with use_backend(backend):
            assert getattr(shape, method)(vertices=False) is not None, "the outline works on either backend"
    with use_backend("csg"):
        assert getattr(shape, method)(vertices=True) is not None

    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError) as excinfo:
        getattr(shape, method)(vertices=True)
    message = str(excinfo.value)
    assert isinstance(excinfo.value, Bosl2Error)
    assert "debug_" in message, f"{label}: the refusal does not name the call: {message}"
    assert "text3d" not in message, f"{label}: the refusal surfaces an internal path: {message}"
    assert "vertices=False" in message, "and says what to do instead"


def test_the_path_extrusions_take_a_profile_a_sweep_cannot() -> None:
    """Why `Extrudable` cannot be rewritten to build a VNF, pinned so it cannot be lost quietly.

    T52 recorded that closing `path2d/path3d -> miscellaneous` means rewriting these two methods to
    produce a `VNF` the way `Sweepable` does -- "a geometry rewrite rather than a move". Measuring
    it (T54) says something stronger: **it is a feature removal.**

    A VNF sweep needs the cross-section as *points*. These take any native 2-D object, and that is
    the stated reason they exist -- `path_extrude`'s own docstring says "for most sweeps
    `path_sweep` is faster and cleaner; this exists for extruding an arbitrary native 2-D object
    (text, multi-part shapes) that is not a single polygon". This is that case: two disjoint
    squares, which `path_sweep` cannot take at all.

    Nor can the point-list subset be delegated to `path_sweep` and only the rest kept native: the
    two build *different geometry* for the same profile -- a mitred extrusion against a
    rotation-minimising frame -- so the same call would mean two things.
    """
    import pybosl2
    from pybosl2.path2d import Path2D
    from pybosl2.path3d import Path3D

    def two_squares() -> object:
        one = pybosl2.square(size=[3, 3], center=True)
        return one | pybosl2.square(size=[3, 3], center=True).translate([8, 0])

    with use_backend("csg"):
        # The capability: a disjoint, multi-part profile that is not a single polygon.
        assert Path3D([[0, 0, 0], [0, 0, 12], [8, 0, 18]]).path_extrude(profile=two_squares) is not None
        assert Path2D([[0, 0], [10, 0], [10, 8]]).path_extrude2d(profile=two_squares) is not None

        with pytest.raises(TypeError):
            Path3D([[0, 0, 0], [0, 0, 12]]).path_sweep(two_squares())

        # And the two are not interchangeable even where both accept the profile.
        square = Path2D([[-1.5, -1.5], [1.5, -1.5], [1.5, 1.5], [-1.5, 1.5]])
        path = Path3D([[0, 0, 0], [0, 0, 12], [8, 0, 18]])
        mitred = [round(float(v), 2) for v in path.path_extrude(profile=square).bounds().size]
        swept = [round(float(v), 2) for v in path.path_sweep(square).bounds().size]
        assert mitred != swept, (
            "path_extrude and path_sweep now agree, so the point-list case could be delegated -- "
            f"re-measure before trusting the note in spec/layers.toml ({mitred} vs {swept})"
        )


def test_the_bezier_debug_helper_refuses_under_its_own_name() -> None:
    """The third helper of this kind, and the third way of announcing the same thing badly.

    `debug_bezier_patches` marks control points with native spheres and returns a `Bosl2Solid`, so
    it was never backend-neutral. Under `use_backend("sdf")` it got *halfway through* and failed on
    the combination -- "cannot combine a 'csg'-backend solid with a 'sdf'-backend solid" -- which
    is a true sentence about the wrong thing. Nothing in it says the helper is a CSG feature.

    Three now, each announcing it differently before being fixed: the path extrusions raised a raw
    `AttributeError` from inside (T51), `Region.debug_region` surfaced `text3d`'s own name from
    three frames down (T53), and this one blamed the union. All three build CSG regardless of the
    active backend; none of them said so.
    """
    import numpy as np

    import pybosl2.beziers as beziers
    from pybosl2.exceptions import Bosl2Error, UnsupportedByBackendError

    patch = np.array(
        [
            [[0, 0, 0], [1, 0, 0], [2, 0, 0]],
            [[0, 1, 0], [1, 1, 1], [2, 1, 0]],
            [[0, 2, 0], [1, 2, 0], [2, 2, 0]],
        ],
        dtype=float,
    )

    with use_backend("csg"):
        assert beziers.debug_bezier_patches(patches=[patch]) is not None

    with use_backend("sdf"), pytest.raises(UnsupportedByBackendError) as excinfo:
        beziers.debug_bezier_patches(patches=[patch])
    message = str(excinfo.value)
    assert isinstance(excinfo.value, Bosl2Error)
    assert "debug_bezier_patches" in message, f"the refusal does not name the call: {message}"
    assert "combine" not in message, f"it still blames the union rather than the helper: {message}"

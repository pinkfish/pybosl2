# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""A public polyline parameter is a `Path2D`/`Path3D`, not a bare sequence (SPEC C-7a).

C-7 asked only that such an API *accept* a `Path`, and they all do -- through the permissive
`PathLike` alias. That is the defect rather than the compliance: the widest form became the default
one, so `PathLike` spread into public signatures as though it were the contract its own docstring
claimed ("anything an API that wants a polyline accepts").

A bare sequence carries no dimension, no open/closed flag and no winding, so every function taking
one re-derives all three, and they do not agree -- the same list is a 2-D outline to one function
and a degenerate 3-D path to the next.

The list below only ever shrinks (PLAN T-4c).
"""

import ast
import pathlib
import re

import numpy as np
import pytest

from pybosl2 import Path2D
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.path3d import Path3D
from pybosl2.paths import require_path, require_paths

# `os.PathLike` is a FILE path and unrelated to `pybosl2.paths.PathLike`; a name match sweeps it up.
# `ArrayLike`/`NDArray` belong here because C-7a names a NumPy array explicitly: they are the same
# defect spelled in numpy's vocabulary, and leaving them out under-reported the debt by 16.
_RAW = re.compile(
    r"(?<!os\.)\bPathLike\b|Sequence\[Sequence\[float\]\]|list\[list\[float\]\]|\bArrayLike\b|\bNDArray\b"
)

# Parameter names that mean an ordered set of points.
_POINTY = frozenset(
    {
        "path",
        "paths",
        "points",
        "pts",
        "polygon",
        "poly",
        "profile",
        "profiles",
        "region",
        "regions",
        "outline",
        "vertices",
        "verts",
        "curve",
        "section",
        "loop",
        "loops",
        "contour",
        "cp",
        "control_points",
    }
)

#: Normalizers, excluded by construction rather than by debt. Each one's *job* is to accept the
#: wide form -- they are the SDF layer's equivalent of the `Path2D(...)` constructor, and requiring
#: a `Path` of them would make them no-ops while forcing every internal numpy pipeline through a
#: wrapper. This is the C-7c line (a normalisation step, not a parameter), drawn explicitly so a
#: permanent entry never sits on a list that is supposed to only shrink.
EXCLUDED = frozenset(
    {
        "pybosl2/sdf/paths.py::as_points::pts",
        # A per-sample de Casteljau kernel, called once per spline step inside `bezpath_points()`.
        # Its "curve" is not always a polyline either: `path_to_bezpath()` evaluates it over a
        # control array built from *normal vectors*, which no point type describes.
        "pybosl2/sdf/paths.py::bezier_points::curve",
        # Pads each row to three floats. Half its callers hand it something that is not a polyline
        # at all -- `_path_sweep(tangent=)` and `Bezier.sweep()` both pad *direction vectors* with
        # it -- and no point type describes a list of tangents.
        "pybosl2/skin.py::path3d::path",
        # BOSL2's apply(): a matrix applied to point data, which explicitly includes a *single*
        # point (`pts.ndim == 1` returns one point back). No path type describes one point, and
        # the mapping is per-point, so order carries no meaning here.
        "pybosl2/transforms.py::apply::points",
        # The plain-list constructor, by name and contract -- the same convention as
        # `Path2D.from_list(lst)`, which escaped this scan only by not naming its parameter
        # `points`. `Bezier(path)` is the typed entry point; this is the wide one it needs.
        "pybosl2/beziers.py::from_list::points",
        # `(verts, faces)` is a *mesh*: an unordered vertex array indexed by faces, where
        # reordering `verts` without reindexing `faces` destroys the geometry. The type these
        # want is `VNF` (SPEC C-8), not a `Path` -- recorded as §12.2 item 4, not dropped.
        "pybosl2/texture.py::is_watertight_topology::verts",
        "pybosl2/texture.py::rasterize_vnf_texture::verts",
        "pybosl2/texture.py::vnf_tile_to_solid::verts",
    }
)

#: Public parameters still accepting a raw sequence. This list only shrinks (SPEC §12.2 item 3).
#: **Empty**: every public parameter that means an ordered set of points now takes a `Path`.
#: The list stays, and the scan with it, so a new signature cannot quietly re-open the debt.
STILL_RAW: frozenset[str] = frozenset()


def _public_functions(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Module-level functions and the methods of module-level classes -- and nothing else.

    `ast.walk` also reaches functions nested inside a function body, whose parameters can never be
    part of the public API; counting one of those (`region2d`'s local `contains`) overstated the
    debt by one and put an unfixable entry on the ratchet.
    """
    found: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for top in tree.body:
        if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.append(top)
        elif isinstance(top, ast.ClassDef) and not top.name.startswith("_"):
            found += [b for b in top.body if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return [f for f in found if not f.name.startswith("_")]


def _raw_polyline_parameters() -> set[str]:
    """Every public parameter meaning a polyline that still accepts a raw sequence."""
    root = pathlib.Path(__file__).resolve().parent.parent
    found: set[str] = set()
    for file in sorted((root / "pybosl2").rglob("*.py")):
        if file.name.startswith("_"):
            continue
        try:
            tree = ast.parse(file.read_text())
        except SyntaxError:  # pragma: no cover - the package must parse
            continue
        for node in _public_functions(tree):
            for arg in node.args.args + node.args.kwonlyargs:
                if arg.annotation is None or arg.arg not in _POINTY:
                    continue
                annotation = ast.unparse(arg.annotation)
                if "os.PathLike" in annotation:
                    continue
                if _RAW.search(annotation):
                    rel = file.relative_to(root).as_posix()
                    entry = f"{rel}::{node.name}::{arg.arg}"
                    if entry not in EXCLUDED:
                        found.add(entry)
    return found


def test_no_new_parameter_takes_raw_points() -> None:
    """A new or edited signature uses a Path type (SPEC C-7a)."""
    added = sorted(_raw_polyline_parameters() - STILL_RAW)
    assert not added, (
        f"these public parameters mean a sequence of points but accept a bare sequence: {added}. "
        f"Type them Path2D/Path3D and call require_path() on the first line (PLAN T-4b)."
    )


def test_the_list_is_not_stale() -> None:
    """A converted parameter comes off the list, so the debt cannot be overstated."""
    fixed = sorted(STILL_RAW - _raw_polyline_parameters())
    assert not fixed, f"these take a Path now -- remove them from STILL_RAW: {fixed}"


def test_require_path_returns_a_path_untouched() -> None:
    """The guard is a no-op for the type it wants."""
    path = Path2D([[0, 0], [1, 1]])
    assert require_path(path, "path", "stroke") is path


@pytest.mark.parametrize(
    ("points", "wrapper"),
    [([[0, 0], [1, 1]], "Path2D("), ([[0, 0, 0], [1, 1, 1]], "Path3D(")],
)
def test_the_refusal_names_the_wrapper_to_apply(points: list, wrapper: str) -> None:
    """The message is the fix: it picks the type from the width of what was passed (SPEC C-7b)."""
    with pytest.raises(Bosl2ValueError) as excinfo:
        require_path(points, "path", "stroke")
    message = str(excinfo.value)
    assert wrapper in message, f"{message!r} does not name {wrapper}"
    assert "stroke()" in message
    assert "path" in message


def test_an_unrecognisable_argument_offers_both_wrappers() -> None:
    """With nothing point-shaped to go on, guessing one type would mislead."""
    with pytest.raises(Bosl2ValueError) as excinfo:
        require_path("not points at all", "path", "stroke")
    assert "Path2D(" in str(excinfo.value)
    assert "Path3D(" in str(excinfo.value)


def test_a_path3d_is_accepted_as_a_path() -> None:
    """Both concrete path types satisfy the contract."""
    path = Path3D([[0, 0, 0], [1, 1, 1]])
    assert require_path(path, "path", "sweep") is path


def test_as_path_list_no_longer_guesses_one_path_from_many() -> None:
    """A `Path2D` says which it is, so the sniffing that used to decide is gone (C-7a).

    `as_path_list` used to inspect ``paths[0][0]`` to work out whether it held one outline or
    several. That guess is precisely the ambiguity a bare sequence creates, and it is unanswerable
    for a 2-point path: ``[[0, 0], [1, 1]]`` is either one 2-point outline or two 1-point ones.
    """
    from pybosl2.sdf.paths import as_path_list

    one = Path2D([[0, 0], [1, 0], [1, 1]])
    assert len(as_path_list(one)) == 1
    assert len(as_path_list([one, one])) == 2


@pytest.mark.parametrize(
    ("function", "argument"),
    [
        ("polygon2d", [[0, 0], [10, 0], [10, 10]]),
        ("region2d", [[[0, 0], [10, 0], [10, 10]]]),
    ],
)
def test_the_sdf_2d_entry_points_refuse_raw_points(function: str, argument: list) -> None:
    """The SDF shape entry points name the wrapper rather than meshing a guess (C-7b)."""
    import pybosl2.sdf.shapes2d as shapes2d

    with pytest.raises(Bosl2ValueError) as excinfo:
        getattr(shapes2d, function)(argument)
    assert "Path2D(" in str(excinfo.value)


@pytest.mark.parametrize(
    ("function", "arguments"),
    [
        ("rotate_extrude", ([[1, 0], [2, 0], [2, 1]],)),
        ("tapered_polygon_prism", ([[0, 0], [1, 0], [1, 1]], 5.0)),
        ("spiral_sweep", ([[0, 0], [1, 0], [1, 1]], 10.0, 5.0)),
        ("polygon_extrude", ([[0, 0], [1, 0], [1, 1]], 5.0)),
        ("convex_polyhedron", ([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]],)),
    ],
)
def test_the_sdf_3d_entry_points_refuse_raw_points(function: str, arguments: tuple) -> None:
    """Same for the 3-D entry points, each naming the type its own parameter carries."""
    import pybosl2.sdf.shapes3d as shapes3d

    with pytest.raises(Bosl2ValueError) as excinfo:
        getattr(shapes3d, function)(*arguments)
    message = str(excinfo.value)
    assert function + "()" in message
    assert "Path3D(" in message if function == "convex_polyhedron" else "Path2D(" in message


def test_path_sweep_takes_a_2d_profile_along_a_path_of_either_width() -> None:
    """`path_sweep` sweeps a 2-D cross-section along a 2-D *or* 3-D spine.

    Typing the spine `Path2D` on the strength of the module's name would reject every 3-D call --
    the mistake `path_extrude` made in an earlier tranche, which no static gate caught.
    """
    from pybosl2.sdf.shapes3d import path_sweep

    profile = Path2D([[-1, -1], [1, -1], [1, 1], [-1, 1]])
    # A 2-D spine is lifted to z=0, so it runs in the XY plane -- these two spell the same spine.
    planar = path_sweep(profile, Path2D([[0, 0], [0, 5], [2, 9]])).bounds()
    spatial = path_sweep(profile, Path3D([[0, 0, 0], [0, 5, 0], [2, 9, 0]])).bounds()
    assert planar.size == pytest.approx(spatial.size)
    assert planar.size[1] > 8, f"the spine runs 9 units along y, so the sweep should too: {planar.size}"


@pytest.mark.parametrize(
    ("function", "arguments"),
    [
        ("path_tangents", ()),
        ("path_normals", ()),
        ("total_length", ()),
        ("path_cut_points", (1.0,)),
        ("round_corners", ()),
        ("offset_polyline", (1.0,)),
        ("path_to_bezpath", ()),
    ],
)
def test_the_sdf_path_utilities_refuse_raw_points(function: str, arguments: tuple) -> None:
    """Each utility names itself and the wrapper, so the fix is in the message (C-7b)."""
    import pybosl2.sdf.paths as sdf_paths

    with pytest.raises(Bosl2ValueError) as excinfo:
        getattr(sdf_paths, function)([[0, 0], [10, 0], [10, 10]], *arguments)
    message = str(excinfo.value)
    assert function + "()" in message, message
    assert "Path2D(" in message, message


def test_path_tangents_takes_either_width_and_path_normals_does_not() -> None:
    """`Path`, not `Path2D | Path3D`, where a construction really is dimension-agnostic.

    A tangent is the same thing in 2-D and 3-D, so `path_tangents` takes either. A *normal* is not:
    rotating the tangent a quarter turn only defines one in the plane, and a 3-D path has a whole
    normal plane instead. Typing both the same way would have made one of them lie.
    """
    from pybosl2.sdf.paths import path_normals, path_tangents

    assert path_tangents(Path2D([[0, 0], [10, 0]])).shape == (2, 2)
    assert path_tangents(Path3D([[0, 0, 0], [10, 0, 0]])).shape == (2, 3)
    assert path_normals(Path2D([[0, 0], [10, 0]])).shape == (2, 2)
    with pytest.raises(Bosl2ValueError, match="Path2D"):
        path_normals(Path3D([[0, 0, 0], [10, 0, 0]]))  # type: ignore[arg-type]


def test_a_normalizer_is_excluded_rather_than_owed() -> None:
    """The two carve-outs still accept the wide form -- that is what they are for (PLAN T-4d).

    A permanent entry on a list defined to only shrink would be a lie about the debt, so these are
    listed as exclusions with their reason instead.
    """
    from pybosl2.sdf.paths import as_points, bezier_points

    assert as_points([[0, 0], [1, 1]]).shape == (2, 2)
    assert list(bezier_points([[0, 0], [10, 0]], 0.5)) == [5, 0]


def test_the_guard_checks_the_width_not_merely_that_it_is_a_path() -> None:
    """A `Path3D` must not satisfy a `Path2D` parameter (SPEC C-7a).

    `Path2D` and `Path3D` are siblings, so `isinstance(value, Path)` accepts both. Every parameter
    typed `Path2D` that only checked *that* would take a `Path3D` and run it through a formula
    indexing columns 0 and 1 -- dropping z and returning a wrong answer instead of refusing. That
    is worse than the raw sequence the migration set out to remove, because it is silent.
    """
    with pytest.raises(Bosl2ValueError) as excinfo:
        require_path(Path3D([[0, 0, 0], [1, 1, 1]]), "path", "stroke", Path2D)
    message = str(excinfo.value)
    assert "must be a Path2D" in message
    assert "got a Path3D" in message
    assert ".path2d()" in message, f"the message should say how to convert: {message}"
    # ...and the check is opt-in, so a parameter that genuinely takes either still does.
    both = Path3D([[0, 0, 0], [1, 1, 1]])
    assert require_path(both, "path", "path_tangents") is both


def test_the_width_check_reaches_into_a_sequence() -> None:
    """`require_paths` names the index *and* the width, since one bad profile is the usual case."""
    with pytest.raises(Bosl2ValueError, match=r"paths\[1\] must be a Path2D, got a Path3D"):
        require_paths([Path2D([[0, 0], [1, 1]]), Path3D([[0, 0, 0], [1, 1, 1]])], "paths", "skin", Path2D)


@pytest.mark.parametrize("function", ["is_closed_path", "close_path", "cleanup_path"])
def test_the_closure_helpers_refuse_raw_points(function: str) -> None:
    """`Path2D`'s static path helpers name the wrapper too (C-7a/b).

    These are the clearest case the requirement describes: each one re-derived closed-ness from a
    bare list, while the `Path2D` a caller almost always had already carried a `closed` flag.
    """
    with pytest.raises(Bosl2ValueError) as excinfo:
        getattr(Path2D, function)([[0, 0], [10, 0], [10, 10]])
    assert function + "()" in str(excinfo.value)
    assert "Path2D(" in str(excinfo.value)


def test_the_closure_helpers_take_either_width() -> None:
    """Whether the ends meet is the same question in 2-D and 3-D, so these take `Path`."""
    assert Path2D.is_closed_path(Path2D([[0, 0], [10, 0], [0, 0]]))
    assert Path2D.is_closed_path(Path3D([[0, 0, 0], [10, 0, 0], [0, 0, 0]]))
    assert not Path2D.is_closed_path(Path3D([[0, 0, 0], [10, 0, 0]]))
    assert len(Path2D.close_path(Path3D([[0, 0, 0], [10, 0, 0]]))) == 3
    assert len(Path2D.cleanup_path(Path3D([[0, 0, 0], [10, 0, 0], [0, 0, 0]]))) == 2


def test_polygon_area_is_planar_and_says_so() -> None:
    """The shoelace formula has no 3-D meaning, so `polygon_area` refuses a `Path3D` (C-7d)."""
    assert Path2D.polygon_area(Path2D([[0, 0], [10, 0], [10, 10], [0, 10]])) == pytest.approx(100.0)
    with pytest.raises(Bosl2ValueError, match="must be a Path2D, got a Path3D"):
        Path2D.polygon_area(Path3D([[0, 0, 0], [10, 0, 0], [10, 10, 0]]))  # type: ignore[arg-type]


def test_clockwise_polygon_returns_an_outline_not_raw_points() -> None:
    """Rewinding an outline yields an outline (PLAN T-4: outputs narrow)."""
    from pybosl2.skin import clockwise_polygon

    counterclockwise = Path2D([[0, 0], [1, 0], [1, 1], [0, 1]])
    wound = clockwise_polygon(counterclockwise)
    assert isinstance(wound, Path2D)
    assert wound == counterclockwise.reverse()
    assert Path2D.polygon_area(wound, signed=True) <= 0
    assert clockwise_polygon(wound) == wound, "already clockwise, so unchanged"


def test_the_scan_still_has_teeth_now_that_the_list_is_empty() -> None:
    """An empty ratchet must mean "nothing left", not "the scan stopped looking".

    `STILL_RAW` reaching zero is the point at which this file's other tests all pass vacuously, so
    this one checks the detector against a signature written to be caught -- a negative control for
    the whole gate.
    """
    import ast
    import textwrap

    source = textwrap.dedent("""
        def draw(path: PathLike, width: float) -> None: ...
        def fill(paths: Sequence[Sequence[float]]) -> None: ...
        def mesh(points: ArrayLike) -> None: ...
        class Thing:
            def trace(self, poly: NDArray[np.float64]) -> None: ...
        def _private(path: PathLike) -> None: ...
        def outer() -> None:
            def nested(path: PathLike) -> None: ...
    """)
    tree = ast.parse(source)
    caught = {
        f"{node.name}::{arg.arg}"
        for node in _public_functions(tree)
        for arg in node.args.args + node.args.kwonlyargs
        if arg.annotation is not None and arg.arg in _POINTY and _RAW.search(ast.unparse(arg.annotation))
    }
    assert caught == {"draw::path", "fill::paths", "mesh::points", "trace::poly"}, caught


def test_every_exclusion_names_a_real_function() -> None:
    """An exclusion that has drifted off a renamed function silently stops excluding anything."""
    root = pathlib.Path(__file__).resolve().parent.parent
    for entry in sorted(EXCLUDED):
        relative, function, parameter = entry.split("::")
        tree = ast.parse((root / relative).read_text())
        found = [f for f in _public_functions(tree) if f.name == function]
        assert found, f"{entry}: no public {function}() in {relative}"
        names = {a.arg for f in found for a in f.args.args + f.args.kwonlyargs}
        assert parameter in names, f"{entry}: {function}() has no {parameter} parameter"


@pytest.mark.parametrize(
    ("call", "wrapper"),
    [
        ("path_copies", "Path2D("),
        ("even_odd", "Path2D("),
        ("vertex_array", "Path3D("),
        ("tri_array", "Path3D("),
    ],
)
def test_the_last_tranche_refuses_raw_points(call: str, wrapper: str) -> None:
    """The final four converted entry points name the wrapper (C-7a/b)."""
    from pybosl2.distributors import path_copies
    from pybosl2.regions import Region
    from pybosl2.vnf import VNF

    square = [[0, 0], [10, 0], [10, 10], [0, 10]]
    row = [[0, 0, 0], [1, 0, 0], [2, 0, 0]]
    attempts = {
        "path_copies": lambda: path_copies(square, num_copies=3),
        "even_odd": lambda: Region.even_odd([square]),
        "vertex_array": lambda: VNF.vertex_array([row, row]),
        "tri_array": lambda: VNF.tri_array([row, row]),
    }
    with pytest.raises(Bosl2ValueError) as excinfo:
        attempts[call]()
    assert wrapper in str(excinfo.value), str(excinfo.value)


def test_path_copies_reads_closed_off_the_path_instead_of_guessing() -> None:
    """The payoff C-7a promises: the callee stops re-deriving what the type already carries.

    `path_copies` used to probe `getattr(path, "closed", False)` -- a bare sequence had no such
    flag, so an open default was assumed for anything that was not a `Path`. A closed outline now
    distributes around its full perimeter, including the closing segment, without being told.
    """
    from pybosl2.distributors import path_copies

    square = [[0, 0], [10, 0], [10, 10], [0, 10]]
    around = path_copies(Path2D(square, closed=True), num_copies=4)
    along = path_copies(Path2D(square, closed=False), num_copies=4)
    assert len(around) == len(along) == 4
    # The closed path is one segment longer, so its copies are spaced further apart.
    assert not np.allclose(np.asarray(around), np.asarray(along))


#: Path-typed parameters that reach a guard indirectly, and how. A delegating function does not
#: need its own `require_path` -- but it does need to be named here, so "no guard" never passes
#: unexamined.
GUARDED_BY_DELEGATION = {
    "pybosl2/beziers.py::create_bezier::path": "calls Bezier.from_path(), which guards",
    "pybosl2/flat.py::circle::points": "calls shapes2d.circle(), which guards",
    "pybosl2/distributors.py::path_copies::path": "the method form calls the module function, which guards",
    "pybosl2/shapes2d/base.py::distribute_on_path::path": "calls distributors.path_copies(), which guards",
    "pybosl2/shapes3d/base.py::distribute_on_path::path": "calls distributors.path_copies(), which guards",
    "pybosl2/shapes3d/extrusions.py::path_text::path": "calls Path2D/Path3D methods that guard",
    "pybosl2/vnf.py::from_skin::profiles": "calls skin.slice_profiles(), which guards",
}


def _geometry_path_names(tree: ast.Module) -> set[str]:
    """The names in this module that actually mean a pybosl2 `Path`.

    `Path` is `pathlib.Path` in `export.py` -- a *file* path -- and `PathLike` is `os.PathLike` in
    several modules. Matching on the spelling alone confuses all three, which is the mistake the
    `STILL_RAW` scan already made once with `os.PathLike`. Resolve against the module's own imports
    instead, so a name counts only when it was imported from `pybosl2.path2d`/`path3d`/`paths`.
    """
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in {
            "pybosl2.path2d",
            "pybosl2.path3d",
            "pybosl2.paths",
        }:
            names |= {a.asname or a.name for a in node.names if a.name in {"Path", "Path2D", "Path3D"}}
    return names


def _path_typed_parameters() -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Every public parameter already annotated with a pybosl2 path type."""
    root = pathlib.Path(__file__).resolve().parent.parent
    found: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for file in sorted((root / "pybosl2").rglob("*.py")):
        if file.name.startswith("_"):
            continue
        tree = ast.parse(file.read_text())
        wanted = _geometry_path_names(tree)
        if not wanted:
            continue
        for node in _public_functions(tree):
            for arg in node.args.args + node.args.kwonlyargs:
                if arg.annotation is None or arg.arg not in _POINTY:
                    continue
                entry = f"{file.relative_to(root).as_posix()}::{node.name}::{arg.arg}"
                if entry in EXCLUDED:
                    continue
                pieces = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", ast.unparse(arg.annotation)))
                if pieces & wanted:
                    found[entry] = node
    return found


def test_a_path_annotation_is_backed_by_a_guard() -> None:
    """Typing a parameter `Path2D` does not make it one -- something must check (SPEC C-7a/d).

    The `STILL_RAW` ratchet only sees *wide* annotations, so it goes quiet the moment a signature is
    retyped -- whether or not a guard was added with it. That is how `Region.even_odd`, `Bezier
    .from_path`, `Region.with_holes`, `skin.subdivide_and_slice` and `shapes2d.polygon` all kept
    accepting raw points while the ratchet read zero, and how `point_in_polygon` came to leak a bare
    `AttributeError: 'list' object has no attribute 'bounds'` instead of naming the type (E-4).
    An empty ratchet means "no wide annotations", not "the contract holds"; this is what holds it.
    """
    unguarded = []
    for entry, node in sorted(_path_typed_parameters().items()):
        if entry in GUARDED_BY_DELEGATION:
            continue
        body = ast.unparse(node)
        if "require_path" not in body and "as_path_list" not in body:
            unguarded.append(entry)
    assert not unguarded, (
        f"these parameters are typed as a path but nothing checks it: {unguarded}. "
        f"Call require_path()/require_paths() on the first line (PLAN T-4b), or record the "
        f"delegation in GUARDED_BY_DELEGATION with the callee that guards."
    )


def test_the_delegation_list_does_not_go_stale() -> None:
    """A delegation entry for a parameter that no longer exists silently excuses nothing."""
    known = _path_typed_parameters()
    missing = sorted(set(GUARDED_BY_DELEGATION) - set(known))
    assert not missing, f"these no longer name a path-typed public parameter: {missing}"

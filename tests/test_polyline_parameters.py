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

import pytest

from pybosl2 import Path2D
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.path3d import Path3D
from pybosl2.paths import require_path

# `os.PathLike` is a FILE path and unrelated to `pybosl2.paths.PathLike`; a name match sweeps it up.
_RAW = re.compile(r"(?<!os\.)\bPathLike\b|Sequence\[Sequence\[float\]\]|list\[list\[float\]\]")

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

#: Public parameters still accepting a raw sequence. This list only shrinks (SPEC §12.2 item 3).
STILL_RAW = frozenset(
    {
        "pybosl2/beziers.py::from_list::points",
        "pybosl2/caps.py::place::poly",
        "pybosl2/distributors.py::path_copies::path",
        "pybosl2/path2d.py::cleanup_path::path",
        "pybosl2/path2d.py::close_path::path",
        "pybosl2/path2d.py::is_closed_path::path",
        "pybosl2/path2d.py::polygon_area::poly",
        "pybosl2/regions.py::even_odd::paths",
        "pybosl2/sdf/paths.py::as_path_list::paths",
        "pybosl2/sdf/shapes2d.py::contains::poly",
        "pybosl2/sdf/shapes2d.py::polygon2d::paths",
        "pybosl2/sdf/shapes2d.py::region2d::paths",
        "pybosl2/sdf/shapes2d.py::stroke2d::path",
        "pybosl2/sdf/shapes3d.py::rotate_extrude::paths",
        "pybosl2/sdf/shapes3d.py::spiral_sweep::profile",
        "pybosl2/sdf/shapes3d.py::tapered_polygon_prism::paths",
        "pybosl2/shapes2d/base.py::path_extrude::path",
        "pybosl2/shapes2d/curves.py::jittered_poly::path",
        "pybosl2/skin.py::clockwise_polygon::poly",
        "pybosl2/skin.py::os_profile::profile",
        "pybosl2/skin.py::path3d::path",
        "pybosl2/skin.py::slice_profiles::profiles",
        "pybosl2/skin.py::subdivide_and_slice::profiles",
        "pybosl2/surfaces3d.py::plot_revolution::path",
        "pybosl2/texture.py::is_watertight_topology::verts",
        "pybosl2/texture.py::rasterize_vnf_texture::verts",
        "pybosl2/texture.py::vnf_tile_to_solid::verts",
        "pybosl2/transforms.py::apply::points",
        "pybosl2/vnf.py::from_skin::profiles",
        "pybosl2/vnf.py::tri_array::points",
        "pybosl2/vnf.py::vertex_array::points",
    }
)


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
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name.startswith("_"):
                continue
            for arg in node.args.args + node.args.kwonlyargs:
                if arg.annotation is None or arg.arg not in _POINTY:
                    continue
                annotation = ast.unparse(arg.annotation)
                if "os.PathLike" in annotation:
                    continue
                if _RAW.search(annotation):
                    rel = file.relative_to(root).as_posix()
                    found.add(f"{rel}::{node.name}::{arg.arg}")
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

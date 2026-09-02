# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Every facet parameter says where its default comes from (SPEC G-4, R-4).

`use_defaults(fn=64)` is how a caller sets curve resolution: once for a block, rather than
threading four numbers through every call. That only helps someone who knows it exists, and a
reader meets `fn` at a signature long before they find `pybosl2.defaults` — so the parameter's own
documentation is where the ambient mechanism has to be named.

It was named in 38 of 209 places when this was first measured. The façade had it everywhere
(T0e did that); nothing else did.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "pybosl2"

FACET_PARAMETERS = ("fn", "fa", "fs", "res")

#: `defaults.py` defines the ambient values, so pointing its own parameters at them is circular.
EXEMPT_FILES = {"defaults.py"}

#: Facet parameters still undocumented, and every one of them for the same reason: its callable
#: has **no `Args:` section at all**, which is a PLAN D-P4 defect in its own right and a bigger
#: job than this rule. Adding a partial `Args:` listing only the facet parameters would be worse
#: than nothing -- it reads as though the others are not parameters. So they are a backlog, and it
#: only shrinks: writing the `Args:` section removes its rows. 57 callables, recorded in
#: SPEC §12.2.
KNOWN_GAPS: frozenset[str] = frozenset(
    {
        "miscellaneous.py::cylindrical_extrude::fa",
        "miscellaneous.py::cylindrical_extrude::fn",
        "miscellaneous.py::cylindrical_extrude::fs",
        "partitions.py::partition::fa",
        "partitions.py::partition::fn",
        "partitions.py::partition::fs",
        "partitions.py::partition_cut_mask::fa",
        "partitions.py::partition_cut_mask::fn",
        "partitions.py::partition_cut_mask::fs",
        "parts/linear_bearings.py::linear_bearing::fa",
        "parts/linear_bearings.py::linear_bearing::fn",
        "parts/linear_bearings.py::linear_bearing::fs",
        "parts/linear_bearings.py::lmxuu_housing::fa",
        "parts/linear_bearings.py::lmxuu_housing::fn",
        "parts/linear_bearings.py::lmxuu_housing::fs",
        "rounding.py::path_join::fa",
        "rounding.py::path_join::fn",
        "rounding.py::path_join::fs",
        "rounding.py::round_corners::fa",
        "rounding.py::round_corners::fn",
        "rounding.py::round_corners::fs",
        "sdf/joiners.py::knuckle_hinge::res",
        "sdf/joiners.py::rabbit_clip::res",
        "sdf/paths.py::round_corners::fn",
        "sdf/shapes2d.py::circle2d::res",
        "sdf/shapes2d.py::ellipse2d::res",
        "sdf/shapes2d.py::extrude::res",
        "sdf/shapes2d.py::hull2d_discs::res",
        "sdf/shapes2d.py::linear_sweep_sdf::res",
        "sdf/shapes2d.py::rect2d::res",
        "sdf/shapes2d.py::region2d::res",
        "sdf/shapes2d.py::revolve_sdf::res",
        "sdf/shapes2d.py::square2d::res",
        "sdf/shapes2d.py::stroke2d::res",
        "sdf/shapes2d.py::supershape2d::res",
        "sdf/shapes3d.py::bezier_sweep::res",
        "sdf/shapes3d.py::convex_polyhedron::res",
        "sdf/shapes3d.py::cube::res",
        "sdf/shapes3d.py::cyl::res",
        "sdf/shapes3d.py::cylinder::res",
        "sdf/shapes3d.py::hull::res",
        "sdf/shapes3d.py::interior_fillet::res",
        "sdf/shapes3d.py::octahedron::res",
        "sdf/shapes3d.py::onion::res",
        "sdf/shapes3d.py::path_sweep::res",
        "sdf/shapes3d.py::pie_slice::res",
        "sdf/shapes3d.py::polygon_extrude::res",
        "sdf/shapes3d.py::rounding_edge_mask::res",
        "sdf/shapes3d.py::sphere::res",
        "sdf/shapes3d.py::spheroid::res",
        "sdf/shapes3d.py::teardrop::res",
        "sdf/shapes3d.py::torus::res",
        "sdf/shapes3d.py::tube::res",
        "sdf/shapes3d.py::xcyl::res",
        "sdf/shapes3d.py::ycyl::res",
        "sdf/shapes3d.py::zcyl::res",
        "shapes2d/base.py::offset::fa",
        "shapes2d/base.py::offset::fn",
        "shapes2d/base.py::offset::fs",
        "shapes2d/base.py::rotate_extrude::fa",
        "shapes2d/base.py::rotate_extrude::fn",
        "shapes2d/base.py::rotate_extrude::fs",
        "shapes2d/square.py::hexagon::fa",
        "shapes2d/square.py::hexagon::fn",
        "shapes2d/square.py::hexagon::fs",
        "shapes2d/square.py::octagon::fa",
        "shapes2d/square.py::octagon::fn",
        "shapes2d/square.py::octagon::fs",
        "shapes2d/square.py::pentagon::fa",
        "shapes2d/square.py::pentagon::fn",
        "shapes2d/square.py::pentagon::fs",
        "shapes3d/base.py::edge_profile_asym::fa",
        "shapes3d/base.py::edge_profile_asym::fn",
        "shapes3d/base.py::edge_profile_asym::fs",
        "shapes3d/base.py::face_profile::fa",
        "shapes3d/base.py::face_profile::fn",
        "shapes3d/base.py::face_profile::fs",
        "shapes3d/base.py::wrap::fn",
        "shapes3d/cylinder.py::cyl_profile::fa",
        "shapes3d/cylinder.py::cyl_profile::fn",
        "shapes3d/cylinder.py::cyl_profile::fs",
        "shapes3d/cylinder.py::xcyl::fa",
        "shapes3d/cylinder.py::xcyl::fn",
        "shapes3d/cylinder.py::xcyl::fs",
        "shapes3d/cylinder.py::ycyl::fa",
        "shapes3d/cylinder.py::ycyl::fn",
        "shapes3d/cylinder.py::ycyl::fs",
        "shapes3d/cylinder.py::zcyl::fa",
        "shapes3d/cylinder.py::zcyl::fn",
        "shapes3d/cylinder.py::zcyl::fs",
        "surfaces3d.py::fillet::fa",
        "surfaces3d.py::fillet::fn",
        "surfaces3d.py::fillet::fs",
        "svg.py::svg_rings_with_colors::fa",
        "svg.py::svg_rings_with_colors::fn",
        "svg.py::svg_rings_with_colors::fs",
        "texture.py::texture::fn",
    }
)


def _documented_facets() -> list[tuple[str, str, str, bool]]:
    """Return (file, callable, parameter, documented) for every public facet parameter."""
    out: list[tuple[str, str, str, bool]] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.name in EXEMPT_FILES:
            continue
        relative = path.relative_to(PACKAGE).as_posix()
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            doc = ast.get_docstring(node)
            if not doc:
                continue
            names = {a.arg for a in node.args.args + node.args.kwonlyargs}
            for parameter in FACET_PARAMETERS:
                if parameter not in names:
                    continue
                entry = f"{relative}::{node.name}::{parameter}"
                if entry in KNOWN_GAPS:
                    continue
                out.append((relative, node.name, parameter, "use_defaults" in doc))
    return out


FACETS = _documented_facets()


def test_the_scan_found_the_parameters() -> None:
    """A scan that matched nothing would make the check below vacuous."""
    assert len(FACETS) > 100, f"only {len(FACETS)} facet parameters found; the scan is broken"


@pytest.mark.parametrize(
    ("path", "callable_name", "parameter"),
    [(f, c, p) for f, c, p, _ in FACETS],
    ids=lambda v: str(v),
)
def test_every_facet_parameter_documents_the_ambient_default(path: str, callable_name: str, parameter: str) -> None:
    """SPEC G-4: the parameter is where a reader meets `use_defaults`."""
    documented = {(f, c, p): ok for f, c, p, ok in FACETS}
    assert documented[(path, callable_name, parameter)], (
        f"{path}::{callable_name} takes {parameter!r} without saying that omitting it inherits "
        f"the ambient default. Add the clause: "
        f'"Omitted, the ambient ``use_defaults({parameter}=...)`` value applies."'
    )


def test_the_backlog_only_shrinks() -> None:
    """Writing a missing `Args:` section removes its rows; nothing may add one."""
    live = {f"{path}::{name}::{parameter}" for path, name, parameter, documented in FACETS if not documented}
    assert not live - KNOWN_GAPS, f"new undocumented facet parameters: {sorted(live - KNOWN_GAPS)}"
    stale = sorted(KNOWN_GAPS - _all_facet_entries())
    assert not stale, f"KNOWN_GAPS names parameters that are gone or now documented: {stale}"


def _all_facet_entries() -> set[str]:
    """Every facet parameter in the package, documented or not, gaps included."""
    found: set[str] = set()
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.name in EXEMPT_FILES:
            continue
        relative = path.relative_to(PACKAGE).as_posix()
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            doc = ast.get_docstring(node)
            if not doc or "use_defaults" in doc:
                continue
            names = {a.arg for a in node.args.args + node.args.kwonlyargs}
            found |= {f"{relative}::{node.name}::{p}" for p in FACET_PARAMETERS if p in names}
    return found

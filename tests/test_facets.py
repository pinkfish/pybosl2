# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Curve resolution must reach every tessellated construction (SPEC.md R-1, PLAN.md R-P2).

Anything that draws a circle, arc, rounding or chamfer arc has to accept ``fn``/``fa``/``fs`` and
pass them down, so a caller can control smoothness from the outside. A backlog of callables
predates that rule; this test pins it so the list can only shrink -- a NEW public callable that
takes a radius or a rounding but no facet controls fails here.
"""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "pybosl2"

#: Parameters that mean "this callable tessellates a curve".
CURVED = {"rounding", "radius", "radius1", "diameter", "inner_rounding"}
FACETS = {"fn", "fa", "fs"}

#: Reviewed against SPEC R-1a and found to be OUT of scope: each takes a radius to place or
#: measure geometry, or samples exactly where the caller says (an explicit angle/z list, an
#: explicit xrange/yrange), so nothing it returns has a facet count for fn/fa/fs to choose. A copy distributor
#: positions whatever it is given; polar_to_xy and circle_circle_tangents return points.
PLACEMENT_ONLY: frozenset[str] = frozenset(
    {
        "distributors.py::Distributable.arc_copies",
        "distributors.py::Distributable.sphere_copies",
        "distributors.py::Distributable.xrot_copies",
        "distributors.py::Distributable.yrot_copies",
        "distributors.py::Distributable.zrot_copies",
        "distributors.py::arc_copies",
        "distributors.py::sphere_copies",
        "distributors.py::xrot_copies",
        "distributors.py::yrot_copies",
        "distributors.py::zrot_copies",
        "geometry.py::circle_circle_tangents",
        "parts/screw_drive.py::PhillipsSpec.depth",
        "parts/wiring.py::hex_offsets",
        "transforms.py::polar_to_xy",
        "surfaces3d.py::plot_revolution",
        "rounding.py::Roundable.bent_cutout_mask",
        "surfaces3d.py::cylindrical_heightfield",
        # a star's vertex count is `tips` and an ngon's is `sides`: the caller states the
        # tessellation outright, so there is no facet count for fn/fa/fs to choose
        "shapes2d/curves.py::star",
        "flat.py::star",
    }
)

#: Reviewed against SPEC R-1a and found OUT of scope for a second reason: each returns a
#: *description* rather than tessellated geometry, and whatever consumes it owns the facet count.
#: The bezier handles are control points; the metaballs are fields the isosurface mesher samples;
#: the Platonic solids are flat-faced; squircle_radius_fg returns a number; supershape takes an
#: explicit `count`; and the os_* rim profiles are consumed by offset_sweep, which resolves the
#: facet count itself.
DESCRIPTORS: frozenset[str] = frozenset(
    {
        "beziers.py::Bezier.begin",
        "beziers.py::Bezier.end",
        "beziers.py::Bezier.joint",
        "beziers.py::Bezier.tang",
        "isosurface.py::mb_sphere",
        "isosurface.py::mb_capsule",
        "isosurface.py::mb_disk",
        "isosurface.py::mb_connector",
        "parts/polyhedra.py::RegularPolyhedron.cube",
        "parts/polyhedra.py::RegularPolyhedron.dodecahedron",
        "parts/polyhedra.py::RegularPolyhedron.icosahedron",
        "parts/polyhedra.py::RegularPolyhedron.octahedron",
        "parts/polyhedra.py::RegularPolyhedron.tetrahedron",
        "shapes2d/curves.py::squircle_radius_fg",
        "shapes2d/curves.py::supershape",
        "skin.py::os_circle",
        "skin.py::os_smooth",
        "skin.py::os_teardrop",
    }
)

#: The real backlog (SPEC.md §12.2): these DO tessellate, and must grow fn/fa/fs and pass them
#: down (R-1). Nothing may be added; entries leave as they are fixed.
KNOWN_WITHOUT_FACETS: frozenset[str] = frozenset({})


def _public_callables_missing_facets() -> set[str]:
    """Return every public module-level function and public method that draws a curve without facets."""
    found: set[str] = set()

    def check(node: ast.FunctionDef | ast.AsyncFunctionDef, module: str, prefix: str = "") -> None:
        if node.name.startswith("_"):
            return
        args = node.args
        names = {a.arg for a in args.args + args.kwonlyargs + args.posonlyargs}
        if names & CURVED and not names & FACETS:
            found.add(f"{module}::{prefix}{node.name}")

    for path in sorted(PACKAGE.rglob("*.py")):
        if path.name.startswith("_") or "sdf" in path.parts:
            continue  # private helpers, and the SDF backend which uses res= instead
        module = str(path.relative_to(PACKAGE))
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                check(node, module)
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        check(member, module, f"{node.name}.")
    return found


def test_no_new_curved_api_without_facet_controls() -> None:
    new = sorted(_public_callables_missing_facets() - KNOWN_WITHOUT_FACETS - PLACEMENT_ONLY - DESCRIPTORS)
    assert not new, "these draw curves but take no fn/fa/fs (SPEC.md R-1): " + ", ".join(new)


def test_the_backlog_only_shrinks() -> None:
    fixed = sorted(KNOWN_WITHOUT_FACETS - _public_callables_missing_facets())
    assert not fixed, "fixed -- remove from KNOWN_WITHOUT_FACETS: " + ", ".join(fixed)

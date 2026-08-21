# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: docs/_covgen.py
#    Generates docs/bosl2_coverage.rst: every BOSL2 .scad file against the pybosl2 module that
#    ports it, with a status and a note. SPEC B2-1 claims feature parity with BOSL2; this is the
#    evidence for that claim, and the gap list where it does not hold yet.
#
#    Re-run after porting a module:  python3 docs/_covgen.py
#    tests/test_bosl2_coverage.py keeps the table honest (and, with network, checks the file list
#    against upstream).
#
# FileGroup: pybosl2

from __future__ import annotations

import sys
from pathlib import Path

#: The upstream file list, pinned so the docs build never needs the network. Refresh with
#: `python3 docs/_covgen.py --refresh` (which re-reads GitHub) when BOSL2 gains or loses a file.
BOSL2_VERSION = "v2.0.751"
BOSL2_TREE = "df336a2c28f31ffc6554d331d8323f48cbe7a04b"

#: status -> how to read it.
STATUSES = {
    "ported": "the module's features are available, through pybosl2's own API",
    "partial": "some of it is available; the note says what is missing",
    "unported": "nothing of it is available yet",
    "n/a": "nothing to port -- OpenSCAD plumbing that Python or NumPy already provides",
}

#: BOSL2 file -> (status, pybosl2 modules, note). Reviewed by hand: the mapping is a judgement,
#: not something to infer from names. Keep the note specific enough to act on.
COVERAGE: dict[str, tuple[str, tuple[str, ...], str]] = {
    # -- geometry and maths ------------------------------------------------------------------
    "math.scad": ("ported", ("math",), "scalar maths, interpolation, root finding, cumulative ops."),
    "vectors.scad": ("ported", ("vectors",), "vector maths and nearest-point searches."),
    "geometry.scad": ("ported", ("geometry",), "lines, planes, circles, triangles, hulls."),
    "coords.scad": ("ported", ("transforms", "points"), "coordinate conversions and point-list transforms."),
    "trigonometry.scad": ("ported", ("geometry",), "triangle solvers; the rest is Python's `math`."),
    "linalg.scad": ("n/a", ("math",), "matrix maths is NumPy's; the BOSL2 helpers have no Python analogue."),
    "affine.scad": (
        "ported",
        ("transforms", "quaternions"),
        "4x4 transform construction, decomposition and rotation maths.",
    ),
    # -- lists, strings, plumbing ------------------------------------------------------------
    "lists.scad": ("n/a", (), "list slicing/reversing/sorting is Python's."),
    "comparisons.scad": ("n/a", (), "sorting and approximate comparison are Python's and NumPy's."),
    "strings.scad": ("n/a", (), "string handling is Python's."),
    "structs.scad": ("n/a", (), "key-value structures are Python dicts and dataclasses."),
    "fnliterals.scad": ("n/a", (), "OpenSCAD needs a function-literal library; Python does not."),
    "utility.scad": ("n/a", (), "type predicates and defaults are Python's."),
    "version.scad": ("n/a", ("version",), "pybosl2 has its own version; BOSL2's version gates are moot."),
    "std.scad": ("n/a", (), "the include-everything header; `import pybosl2` is the equivalent."),
    "builtins.scad": ("n/a", (), "wrappers over OpenSCAD builtins, which PythonSCAD exposes directly."),
    "bosl1compat.scad": ("n/a", (), "BOSL v1 compatibility shims; nothing to be compatible with here."),
    # -- 2-D and 3-D shapes ------------------------------------------------------------------
    "shapes2d.scad": ("ported", ("shapes2d", "flat"), "every 2-D primitive, on both backends via the facade."),
    "shapes3d.scad": ("ported", ("shapes3d", "solid"), "every 3-D primitive, on both backends via the facade."),
    "drawing.scad": (
        "ported",
        ("shapes2d.circle", "turtle", "_stroke2d", "_stroke3d", "path3d"),
        "arc, turtle (commands and methods), stroke/dashed_stroke, helix. 3-D arcs are not ported.",
    ),
    "masks.scad": ("ported", ("masking",), "edge/corner/face profiles: `Mask2D`, `Mask3D`, and the profile cutters."),
    "attachments.scad": (
        "partial",
        ("shapes3d.base", "shapes2d.base", "_edges_lang"),
        "anchor/spin/orient, attach/align/position/reorient, the tag and diff system. The parent-child "
        "module tree BOSL2 leans on has no equivalent, so `$parent_*`-style introspection is absent.",
    ),
    "partitions.scad": ("ported", ("partitions",), "the cut-profile grammar and both mask forms."),
    "distributors.scad": ("ported", ("distributors",), "every copier, as methods on shapes and paths."),
    "color.scad": ("ported", ("color",), "`Color`, the palettes, and the colour-space conversions."),
    "transforms.scad": ("ported", ("transforms",), "the transform family, as methods and as matrices."),
    "constants.scad": ("ported", ("constants", "enums"), "directions, anchors, and the `$`-style specials."),
    # -- paths, curves, surfaces -------------------------------------------------------------
    "paths.scad": ("ported", ("paths", "path2d", "path3d"), "path maths, as `Path2D` / `Path3D` objects."),
    "regions.scad": ("ported", ("regions",), "outlines-with-holes, booleans, and offsets."),
    "beziers.scad": ("ported", ("beziers",), "bezier curves, paths and patches."),
    "nurbs.scad": ("ported", ("nurbs",), "NURBS curves and patches."),
    "rounding.scad": ("ported", ("rounding", "skin"), "corner rounding, offset sweeps, joints and prisms."),
    "skin.scad": ("ported", ("skin", "texture"), "skin, sweep, path_sweep, textures."),
    "vnf.scad": ("ported", ("vnf",), "the mesh interchange type and its operations."),
    "isosurface.scad": (
        "partial",
        ("isosurface", "vnf"),
        "3-D isosurfaces and metaballs (`Metaball`). The 2-D analogues (`contour`, `mb_circle` and "
        "friends) and `mb_cyl` are not ported.",
    ),
    "turtle3d.scad": ("ported", ("turtle",), "the 3-D turtle, sharing its command language with the 2-D one."),
    "miscellaneous.scad": ("ported", ("miscellaneous",), "the odds and ends: extrusions, hulls, projections."),
    # -- parts -------------------------------------------------------------------------------
    "ball_bearings.scad": ("ported", ("parts.ball_bearings",), "the trade-size catalogue and the cartridge."),
    "bottlecaps.scad": ("ported", ("parts.bottlecaps",), "PCO-1810/1881 and SPI threads, caps and necks."),
    "cubetruss.scad": ("ported", ("parts.cubetruss",), "the truss segments, clips and supports."),
    "gears.scad": ("ported", ("parts.gears",), "spur, bevel, worm and rack gears."),
    "hinges.scad": ("ported", ("parts.hinges", "sdf.joiners"), "knuckle and living hinges, snap locks."),
    "hooks.scad": ("ported", ("parts.hooks",), "the hook family."),
    "joiners.scad": ("ported", ("parts.joiners", "sdf.joiners"), "dovetails, snap joiners, rabbit clips."),
    "linear_bearings.scad": ("ported", ("parts.linear_bearings",), "LM__UU bearings and their housings."),
    "modular_hose.scad": ("ported", ("parts.modular_hose",), "the segment, ball and socket ends."),
    "nema_steppers.scad": ("ported", ("parts.nema_steppers",), "motor bodies, mounts and masks."),
    "polyhedra.scad": ("ported", ("parts.polyhedra",), "the Platonic, Archimedean and Catalan solids."),
    "screw_drive.scad": ("ported", ("parts.screw_drive",), "hex, torx, phillips and slot recesses."),
    "screws.scad": ("ported", ("parts.screws",), "the ISO/UTS catalogues, heads, nuts and holes."),
    "sliders.scad": ("ported", ("parts.sliders",), "the rail and slider pairs."),
    "threading.scad": ("ported", ("parts.threading",), "every thread profile, rods, nuts and helices."),
    "tripod_mounts.scad": ("ported", ("parts.tripod_mounts",), "the Manfrotto RC2 quick-release plate."),
    "walls.scad": ("ported", ("parts.walls",), "the sparse and corrugated wall panels."),
    "wiring.scad": ("ported", ("parts.wiring",), "wire bundle routing."),
    "metric_screws.scad": (
        "partial",
        ("parts.screws",),
        "the metric catalogue lives in `parts.screws`; BOSL2's own file is a thin deprecated wrapper.",
    ),
}

_HEADER = """BOSL2 coverage
==============

.. This page is generated by docs/_covgen.py -- edit that, not this file.

pybosl2 aims to be **feature** compatible with BOSL2, not API compatible (SPEC B2-1): the same
things can be built, with an API designed for Python. This table is the evidence for that claim,
and the gap list where it does not hold yet.

Checked against BOSL2 **{version}** (tree ``{tree}``); {ported} of the {total} upstream files are
ported, {partial} partial, {unported} unported, and {na} have nothing to port.

Status meanings:

{legend}

.. list-table::
   :header-rows: 1
   :widths: 22 12 26 40

   * - BOSL2 file
     - Status
     - pybosl2
     - Notes
"""


def _rows() -> str:
    out = []
    for name in sorted(COVERAGE):
        status, modules, note = COVERAGE[name]
        where = ", ".join(f"``pybosl2.{m}``" for m in modules) if modules else "--"
        out.append(f"   * - ``{name}``\n     - {status}\n     - {where}\n     - {note}\n")
    return "".join(out)


def render() -> str:
    """Return the reStructuredText for the coverage page."""
    counts = {key: sum(1 for v in COVERAGE.values() if v[0] == key) for key in STATUSES}
    legend = "\n".join(f"* **{key}** -- {why}" for key, why in STATUSES.items())
    header = _HEADER.format(
        version=BOSL2_VERSION,
        tree=BOSL2_TREE[:12],
        total=len(COVERAGE),
        ported=counts["ported"],
        partial=counts["partial"],
        unported=counts["unported"],
        na=counts["n/a"],
        legend=legend,
    )
    return header + _rows()


def main() -> int:
    """Write the page; with ``--refresh``, first re-read the file list from GitHub."""
    if "--refresh" in sys.argv:
        import json
        import subprocess

        # curl, not urllib: this interpreter has no CA bundle configured, and a maintenance
        # script is not worth carrying certifi for.
        url = "https://api.github.com/repos/BelfrySCAD/BOSL2/git/trees/master"
        raw = subprocess.run(["curl", "-fsS", "--max-time", "30", url], capture_output=True, text=True, check=True)
        tree = json.loads(raw.stdout)
        upstream = {e["path"] for e in tree["tree"] if e["path"].endswith(".scad")}
        missing = sorted(upstream - set(COVERAGE))
        stale = sorted(set(COVERAGE) - upstream)
        print(f"upstream tree {tree['sha']}: {len(upstream)} .scad files")
        if missing:
            print("  not in COVERAGE (add them):", ", ".join(missing))
        if stale:
            print("  in COVERAGE but not upstream (renamed or removed):", ", ".join(stale))
        if missing or stale:
            return 1

    target = Path(__file__).resolve().parent / "bosl2_coverage.rst"
    target.write_text(render())
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

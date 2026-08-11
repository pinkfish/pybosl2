"""Auto-generate RST documentation files from the actual Python module structure.

Hooks into ``conf.py`` via its ``setup()`` function; runs before every
``make html`` so that module moves and renames are picked up automatically.

**Category tags.**  Each source file may carry a ``# DocCategory: <section>`` tag
that maps the module to a toctree section in ``index.rst``.  When the tag is
absent the module is placed by its file path (``parts/*`` → Parts library,
``turtle/*`` → Paths, and so on).

**Sidebar labels.**  The :file:`LibFile` tag's base name (without ``.py``) is used
as the navigation link text in the main sidebar; the :file:`FileSummary` tag becomes
the tooltip / subtitle shown alongside it.

What it does:
  1. Scans ``pybosl2/`` for all public modules and reads their header tags.
  2. Generates ``index.rst`` with a dynamically-built toctree.
  3. Creates a ``.rst`` stub for any module that lacks one.
  4. Validates ``automodule``/``autoclass``/``autofunction`` directives and
     ``:class:``/``:meth:``/``:func:`` cross-references.
"""

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Any

DOCS_DIR = Path(__file__).resolve().parent
REPO_ROOT = DOCS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Toctree section order (left-to-right / top-to-bottom in the sidebar)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Metadata tag parsing
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"#\s*(FileGroup|LibFile|FileSummary|DocCategory):\s*(.*)$")


def _parse_header_tags(source: str) -> dict[str, str]:
    """Extract metadata tags from a source file's comment header block."""
    tags: dict[str, str] = {}
    for line in source.split("\n")[:30]:
        m = _TAG_RE.match(line)
        if m:
            tags[m.group(1)] = m.group(2).strip()
    return tags


def _file_id_from_libfile(libfile: str) -> str:
    """Return a bare module name from a LibFile path, e.g. ``geometry`` from ``pybosl2/geometry.py``."""
    stem = Path(libfile).stem if libfile else ""
    return stem


def _doc_category(tags: dict[str, str], module_parts: list[str]) -> str:
    """Determine the toctree section for a module.

    1. ``DocCategory: skip`` or ``DocCategory: internal`` → excluded from toctree.
    2. Any other explicit ``DocCategory`` tag wins.
    3. ``parts/*`` → Parts library.
    4. ``turtle/*`` → Paths, regions & surfaces.
    5. Support modules: bounds, caps, exceptions, points, solid, surfaces3d,
       turtle2d, version → excluded (internal only).
    6. Path-based heuristics.
    7. Everything else → Foundational.
    """
    if "DocCategory" in tags:
        cat = tags["DocCategory"]
        if cat.lower() in ("skip", "internal"):
            return "__SKIP__"
        return cat

    p0 = module_parts[0] if module_parts else ""
    if p0 == "parts":
        return "Parts library"
    if p0 == "turtle":
        if module_parts[-1] == "turtle2d":
            return "__SKIP__"  # 2-D turtle documented in drawing.rst
        return "Paths, regions & surfaces"

    last = module_parts[-1] if module_parts else ""
    if last in _INTERNAL_MODULES:
        return "__SKIP__"
    return _PATH_FALLBACK_MAP.get(last, "Foundational")


_INTERNAL_MODULES: set[str] = {
    "bounds",
    "caps",
    "exceptions",
    "path2d",
    "path3d",
    "points",
    "shapes2d",
    "shapes3d",
    "solid",
    "surfaces3d",
    "version",
}


_PATH_FALLBACK_MAP: dict[str, str] = {
    # Foundational
    "shapes3d": "Foundational",
    "shapes2d": "Foundational",
    "transforms": "Foundational",
    "distributors": "Foundational",
    "color": "Foundational",
    "masking": "Foundational",
    "partitions": "Foundational",
    "texture": "Foundational",
    "constants": "Foundational",
    "native_ops": "Foundational",
    # Paths, regions & surfaces
    "paths": "Paths, regions & surfaces",
    "path2d": "Paths, regions & surfaces",
    "path3d": "Paths, regions & surfaces",
    "regions": "Paths, regions & surfaces",
    "rounding": "Paths, regions & surfaces",
    "turtle3d": "Paths, regions & surfaces",
    "beziers": "Paths, regions & surfaces",
    "nurbs": "Paths, regions & surfaces",
    "skin": "Paths, regions & surfaces",
    "vnf": "Paths, regions & surfaces",
    "isosurface": "Paths, regions & surfaces",
    # Math & geometry
    "geometry": "Math & geometry",
    "math": "Math & geometry",
    "vectors": "Math & geometry",
    "comparisons": "Math & geometry",
    # Extras
    "miscellaneous": "Extras",
}


# ---------------------------------------------------------------------------
# Module scanning
# ---------------------------------------------------------------------------


def _build_name_index() -> dict[str, dict[str, str]]:
    """Map every public name → ``{'module': …, 'type': …}`` from the pybosl2 package tree."""
    index: dict[str, list[dict[str, str]]] = {}
    py_dir = REPO_ROOT / "pybosl2"

    for fpath in sorted(py_dir.rglob("*.py")):
        if fpath.name.startswith("_") or "/sdf/" in str(fpath):
            continue
        rel = fpath.relative_to(py_dir)
        parts = list(rel.parts)
        parts[-1] = parts[-1].replace(".py", "")
        if parts[-1] == "__init__":
            parts.pop()
        mod_name = "pybosl2." + ".".join(parts) if parts else "pybosl2"

        try:
            source = fpath.read_text()
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue

        all_list: list[str] | None = None
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                t = node.targets[0]
                if isinstance(t, ast.Name) and t.id == "__all__" and isinstance(node.value, ast.List):
                    all_list = [
                        e.value for e in node.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)
                    ]
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_") and (all_list is None or node.name in all_list):
                    index.setdefault(node.name, []).append({"module": mod_name, "type": "function"})
            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith("_") and (all_list is None or node.name in all_list):
                    index.setdefault(node.name, []).append({"module": mod_name, "type": "class"})

    # De-duplicate: prefer the entry whose module name ends with the object name
    deduped: dict[str, dict[str, str]] = {}
    for name, entries in index.items():
        if len(entries) > 1:
            direct = [e for e in entries if e["module"].split(".")[-1].lower() == name.lower()]
            deduped[name] = direct[0] if direct else entries[0]
        else:
            deduped[name] = entries[0]
    return deduped


def _scan_modules() -> dict[str, dict[str, Any]]:
    """Return {page_name: {module, parts, tags, summary, ...}} for every public module."""
    py_dir = REPO_ROOT / "pybosl2"
    modules: dict[str, dict[str, Any]] = {}

    for fpath in sorted(py_dir.rglob("*.py")):
        if fpath.name.startswith("_") or "/sdf/" in str(fpath):
            continue
        rel = fpath.relative_to(py_dir)
        parts = list(rel.parts)
        parts[-1] = parts[-1].replace(".py", "")
        if parts[-1] == "__init__":
            parts.pop()
        mod_name = "pybosl2." + ".".join(parts) if parts else "pybosl2"
        page_name = parts[-1] if parts else "pybosl2"

        try:
            source = fpath.read_text()
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue

        doc = ast.get_docstring(tree) or ""
        summary = doc.split("\n")[0].strip().rstrip(".") if doc else ""
        tags = _parse_header_tags(source)
        file_id = _file_id_from_libfile(tags.get("LibFile", "")) or page_name
        category = _doc_category(tags, parts)

        modules[page_name] = {
            "module": mod_name,
            "page": page_name,
            "file_id": file_id,
            "summary": summary,
            "tags": tags,
            "parts": parts,
            "category": category,
        }

    return modules


# ---------------------------------------------------------------------------
# Index.rst generation
# ---------------------------------------------------------------------------

_INDEX_PROLOGUE = r"""pybosl2 — a pure-Python PythonSCAD port of BOSL2
================================================

``pybosl2`` is a pure-Python / numpy port of the pieces of `BOSL2 <https://github.com/BelfrySCAD/BOSL2>`_
that this toolkit uses, with **no** ``osuse()``/BOSL2 runtime dependency. Every operation hangs off
an object — :class:`~pybosl2.path2d.Path2D` for 2-D outlines, :class:`~pybosl2.regions.Region` for
outlines-with-holes, :class:`~pybosl2.beziers.Bezier` / :class:`~pybosl2.beziers.BezierPatch` for bezier
curves and surfaces, :class:`~pybosl2.vnf.VNF` for vertex-face meshes, and the
``pybosl2.shapes3d.Bosl2Solid`` primitives — so new code reads as fluent chains::

    Path2D([[0, 0], [80, 0], [80, 60], [0, 60]]).offset(r=-2).round_corners(radius=1).polygon()

.. raw:: html

   <p style="margin:1.4em 0;padding:14px 18px;border:1px solid #38bdf0;border-radius:10px;
      background:rgba(56,189,240,0.07);font-size:1.05em;">
     &#9881;&#65039; <b><a href="specs/index.html">Visual parts catalog &amp; spec sheets &rarr;</a></b>
     &nbsp;&mdash;&nbsp; the gears, hinges, joiners, cube-truss and ball-bearing modules with
      technical schematics and metrics measured from real rendered STL.
   </p>

.. raw:: html

   <div id="version-links" style="margin:1.2em 0;padding:10px 18px;
        border:1px solid var(--md-default-fg-color--lightest,#ddd);border-radius:10px;
        font-size:0.92em;display:none">
     <b>Released versions:</b> <span id="version-list"></span>
     &ensp;<b><a id="latest-link" href="">latest &rarr;</a></b>
   </div>

   <div id="dev-notice" style="margin:1.2em 0;padding:10px 18px;
        border:1px solid var(--md-default-fg-color--lightest,#ddd);border-radius:10px;
        font-size:0.92em;display:none">
     &#9888;&#65039; <b>This is the unreleased development version.</b>
     See the <a href="../index.html">latest stable release</a> for production use.
   </div>

   <!-- version loader -->
   <script>
   (function(){
     var dev = document.getElementById('dev-notice');
     var box = document.getElementById('version-links');
     var list = document.getElementById('version-list');
     var lat = document.getElementById('latest-link');
     var path = window.location.pathname.replace(/\/$/,'');
     var inDev = /\/dev\//.test(path) || /\/dev$/.test(path);
     var isVer = /\/v\d+\.\d+\.\d+/.test(path);
      var base;
      if (inDev) { base = path.replace(/\/dev.*/, '') + '/'; }
      else if (isVer) { base = path.replace(/\/v\\d+\\.\\d+\\.\\d+.*/, '') + '/'; }
      else { base = path + '/'; }
     if (isVer) {
       lat.setAttribute('href', base + 'index.html');
       box.style.display = 'block';
       fetch(base + 'versions.json')
         .then(function(r){return r.json();})
         .then(function(vers){
           var n = Math.min(vers.length,5);
           for (var i=0; i<n; i++) {
             var v = vers[i], a = document.createElement('a');
             a.href = base + v + '/index.html';
             a.textContent = v;
             list.appendChild(a);
             if (i < n-1) list.appendChild(document.createTextNode(' \u00b7 '));
           }
         })
         .catch(function(){});
     } else {
       dev.style.display = 'block';
       lat.setAttribute('href', base + 'index.html');
       box.style.display = 'block';
       fetch(base + 'versions.json')
         .then(function(r){return r.json();})
         .then(function(vers){
           var n = Math.min(vers.length,5);
           for (var i=0; i<n; i++) {
             var v = vers[i], a = document.createElement('a');
             a.href = base + v + '/index.html';
             a.textContent = v;
             list.appendChild(a);
             if (i < n-1) list.appendChild(document.createTextNode(' \u00b7 '));
           }
         })
         .catch(function(){});
     }
   })();
   </script>

Rendered examples
-----------------

Every documented function with a rendered example shows both the exact PythonSCAD code and what the
real PythonSCAD binary builds for it, via the ``pythonscad-example`` directive (in
``docs/_ext/pybosl2_example.py``): an **interactive 3-D viewer** for the exported STL mesh (rotate,
pan and zoom — served by the ``stl_viewer`` extension's three.js viewer, a working drop-in for the
``sphinxstl`` ``.. stl::`` directive), plus a **download link** to the mesh. Two-dimensional or
open-surface examples that have no solid mesh fall back to a static preview image.

.. note::

   The interactive viewers fetch each ``.stl`` over HTTP, so view the built docs through a web
   server (for example ``python3 -m http.server`` from ``pybosl2/wiki``) rather than opening the
   HTML files directly with a ``file://`` URL, where browsers block the local mesh fetch. You can
   also embed a viewer for any STL yourself with ``.. stl:: path/to/mesh.stl``.

A cuboid primitive:

.. pythonscad-example::

   from pybosl2.solid import cuboid

   cuboid([40, 30, 20], rounding=4).show()

A bezier surface patch, meshed to a VNF and rendered as a polyhedron:

.. pythonscad-example::

   from pybosl2 import BezierPatch

   patch = [
       [[-50, -50, 0], [-16, -50, 20], [16, -50, -20], [50, -50, 0]],
       [[-50, -16, 20], [-16, -16, 20], [16, -16, -20], [50, -16, 20]],
       [[-50, 16, 20], [-16, 16, -20], [16, 16, 20], [50, 16, 20]],
       [[-50, 50, 0], [-16, 50, -20], [16, 50, 20], [50, 50, 0]],
   ]
   BezierPatch(patch).sheet([0, -6], splinesteps=16).polyhedron().show()

Sweeping a profile along a bezier curve:

.. pythonscad-example::

   import math
   import numpy as np
   from pybosl2 import Bezier

   circle = [[2 * math.cos(t), 2 * math.sin(t)] for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
   Bezier([[0, 0, 5], [0, 0, 20], [25, 12, 15], [30, 4, 6]]).sweep(circle, splinesteps=24).polyhedron().show()

API reference
-------------

The modules are grouped by role, mirroring BOSL2's own organisation. **Foundational** holds the
primitives and transforms most models start from; **Paths, regions & surfaces** the advanced
2-D/3-D modelling toolkit; **Math & geometry** the numeric helpers; and **Parts library** the
ready-made mechanical parts — each with a visual spec sheet in the catalog linked above.
"""


def _generate_index() -> None:
    """Write docs/index.rst with glob-based toctrees auto-discovering RST files."""
    toctree = """

.. toctree::
   :maxdepth: 1
   :caption: Solid backends
   :glob:

   backends/*

.. toctree::
   :maxdepth: 1
   :caption: Foundational
   :glob:

   foundational/*

.. toctree::
   :maxdepth: 1
   :caption: Paths, regions & surfaces
   :glob:

   paths/*

.. toctree::
   :maxdepth: 1
   :caption: Math & geometry
   :glob:

   math/*

.. toctree::
   :maxdepth: 1
   :caption: Parts library
   :glob:

   parts/*

.. toctree::
   :maxdepth: 1
   :caption: Extras
   :glob:

   extras/*
"""
    lines: list[str] = [_INDEX_PROLOGUE] + toctree.split("\n")

    lines.append("")
    lines.append(".. toctree::")
    lines.append("   :maxdepth: 1")
    lines.append("   :caption: Parts catalog")
    lines.append("")
    lines.append("    Visual specs &rarr; <specs/index>")
    lines.append("")

    (DOCS_DIR / "index.rst").write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Spec-sheet helpers
# ---------------------------------------------------------------------------


def _has_spec(module_name: str) -> bool:
    """True if *module_name* has a spec sheet generated by _specgen."""
    try:
        from docs._specgen import MODULES

        return module_name in MODULES
    except ImportError:
        return False


def _spec_callout_html(module_name: str) -> str:
    """Return a raw-html spec-sheet callout block for *module_name*."""
    title = module_name.replace("_", " ").title()
    return (
        f".. raw:: html\n\n"
        f'   <div class="spec-sheet-callout" style="margin:1.4em 0;padding:14px 18px;border:1px solid'
        f' #38bdf0;border-radius:10px;background:rgba(56,189,240,0.07);">\n'
        f"     &#128736;&#65039; <b>Visual spec sheet available &rarr;</b>\n"
        f'     <a href="specs/{module_name}.html">{title} &mdash; measurements and STL previews</a>\n'
        f"   </div>\n"
    )


# ---------------------------------------------------------------------------
# Module RST stubs
# ---------------------------------------------------------------------------

_STUB = """{title}
{title_underline}

{summary}

.. automodule:: {module}
   :members:
   :undoc-members:
   :show-inheritance:
"""

_PARTS_STUB = """{title}
{title_underline}

{summary}

.. autoclass:: {class_path}
   :members:
   :undoc-members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)
"""


_CATEGORY_DIRS: dict[str, str] = {
    "Foundational": "foundational",
    "Paths, regions & surfaces": "paths",
    "Math & geometry": "math",
    "Parts library": "parts",
    "Extras": "extras",
    "Solid backends": "backends",
}


def _generate_stubs(modules: dict[str, dict[str, Any]]) -> list[str]:
    """Create missing .rst files for modules. Returns list of created paths."""
    created: list[str] = []

    _3d_shapes = frozenset({"cuboid", "cylinder", "sphere", "torus", "extrusions"})
    for name, info in modules.items():
        cat = info.get("category", "Foundational")
        if cat == "__SKIP__":
            continue
        cat_dir = _CATEGORY_DIRS.get(cat)
        if cat_dir is None:
            continue
        target_dir = DOCS_DIR / cat_dir

        # Place 2-D/3-D shape stubs in subdirectories so the sidebar groups them.
        module_path = info["module"]
        is_3d = any(p == "shapes3d" for p in info["parts"])
        is_2d = any(p == "shapes2d" for p in info["parts"])
        if "shapes3d.base" not in module_path and is_3d and name in _3d_shapes:
            target_dir = target_dir / "shapes3d"
        elif is_2d and name in {"circle", "square", "curves", "ops"}:
            target_dir = target_dir / "shapes2d"

        target_dir.mkdir(parents=True, exist_ok=True)
        rst_path = target_dir / f"{name}.rst"
        if rst_path.exists():
            continue

        title = info.get("file_id", name).replace("_", " ").title()
        title_underline = "=" * len(title)
        is_parts = info["parts"] and info["parts"][0] == "parts"

        spec_callout = _spec_callout_html(name) if _has_spec(name) else ""

        if is_parts:
            mod_tail = info["module"].split(".")[-1]
            class_name = mod_tail.replace("_", " ").title().replace(" ", "")
            content = _PARTS_STUB.format(
                title=title,
                title_underline=title_underline,
                summary=info["summary"],
                class_path=f"{info['module']}.{class_name}",
            )
        else:
            content = _STUB.format(
                title=title,
                title_underline=title_underline,
                summary=info["summary"],
                module=info["module"],
            )

        if spec_callout:
            header, _, rest = content.partition("\n\n")
            content = header + "\n\n" + spec_callout + "\n" + rest

        rst_path.write_text(content)
        created.append(name)

    return created


_HANDWRITTEN_PAGES = frozenset({"index", "drawing", "native_ops", "shapes2d", "shapes3d", "backends"})


def _cleanup_stale_stubs(modules: dict[str, dict[str, Any]]) -> list[str]:
    """Remove .rst files that no longer correspond to any module. Returns list of deleted names."""
    known = frozenset(modules)
    deleted: list[str] = []
    for rst_path in sorted(DOCS_DIR.rglob("*.rst")):
        if rst_path.parent.name == "specs":
            continue
        name = rst_path.stem
        if name in _HANDWRITTEN_PAGES or name in known:
            continue
        rst_path.unlink()
        deleted.append(name)
    return deleted


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_DIRECTIVE_RE = re.compile(
    r"\.\.\s+(automodule|autoclass|autofunction)::\s+(pybosl2\.[\w.]+)",
    re.MULTILINE,
)

_ROLE_RE = re.compile(
    r":(class|meth|func|mod|attr|exc):`~?(pybosl2\.[\w.]+?)(?:\.([\w.]+))?`",
)


def _validate(rst_path: Path, name_index: dict[str, Any]) -> list[str]:
    """Check a single .rst file and return a list of warnings."""
    warnings: list[str] = []
    try:
        content = rst_path.read_text()
    except Exception:
        return warnings
    fname = rst_path.name

    for m in _DIRECTIVE_RE.finditer(content):
        directive = m.group(1)
        path = m.group(2)
        parts = path.split(".")
        found = False
        for i in range(len(parts), 0, -1):
            candidate = ".".join(parts[:i])
            py_path = REPO_ROOT / (candidate.replace(".", "/") + ".py")
            init_path = REPO_ROOT / (candidate.replace(".", "/") + "/__init__.py")
            if py_path.exists() or init_path.exists():
                found = True
                break
        if not found:
            warnings.append(f"{fname}: {directive}:: {path} — module not found")

    for m in _ROLE_RE.finditer(content):
        role = m.group(1)
        mod_path = m.group(2)
        obj_chain = m.group(3)

        if obj_chain is None:
            py_path = REPO_ROOT / (mod_path.replace(".", "/") + ".py")
            init_path = REPO_ROOT / (mod_path.replace(".", "/") + "/__init__.py")
            if py_path.exists() or init_path.exists():
                continue
            warnings.append(f"{fname}: :{role}:`~{mod_path}` — module not found")
            continue

        first_name = obj_chain.split(".")[0]
        if first_name not in name_index:
            candidate_mod = mod_path + "." + first_name
            py_path = REPO_ROOT / (candidate_mod.replace(".", "/") + ".py")
            init_path = REPO_ROOT / (candidate_mod.replace(".", "/") + "/__init__.py")
            if not py_path.exists() and not init_path.exists():
                warnings.append(f"{fname}: :{role}:`~{mod_path}.{obj_chain}` — unknown")

    return warnings


def validate_all(name_index: dict[str, Any]) -> list[str]:
    """Validate all .rst files and return a unified warning list."""
    all_warnings: list[str] = []
    for rst_path in sorted(DOCS_DIR.rglob("*.rst")):
        all_warnings.extend(_validate(rst_path, name_index))
    return all_warnings


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(verbose: bool = True) -> list[str]:
    """Run the full generation + validation cycle."""
    modules = _scan_modules()
    name_index = _build_name_index()

    created = _generate_stubs(modules)
    stale = _cleanup_stale_stubs(modules)
    _generate_index()
    warnings = validate_all(name_index)

    if verbose:
        if created:
            print(f"_rstgen: created {len(created)} stub(s): {', '.join(created)}")
        if stale:
            print(f"_rstgen: removed {len(stale)} stale stub(s): {', '.join(stale)}")
        print(f"_rstgen: {len(modules)} modules indexed")
        if warnings:
            print(f"_rstgen: {len(warnings)} broken cross-references:")
            for w in warnings:
                print(f"  {w}")
        else:
            print("_rstgen: all cross-references valid")

    return warnings


if __name__ == "__main__":
    main()

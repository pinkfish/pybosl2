# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Validate all links in the docs and specgen systems point to existing resources.

Checks:
  - RST cross-references (:class:, :func:, :meth:, :mod:, :attr:, :exc:, :doc:, :ref:)
  - RST file-relative and spec-sheet links
  - Spec sheet HTML navigation links
  - toctree entries in index.rst and group pages
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

DOCS_DIR = REPO_ROOT / "docs"
SPECS_DIR = DOCS_DIR / "specs"
WIKI_DIR = REPO_ROOT / "wiki"

_CATEGORY_DIRS = [
    "foundational",
    "foundational/shapes2d",
    "foundational/shapes3d",
    "paths",
    "math",
    "parts",
    "extras",
    "backends",
]


# ── helpers ──────────────────────────────────────────────────────────────────


def _rst_files() -> Iterator[Path]:
    yield from DOCS_DIR.rglob("*.rst")


def _spec_htmls() -> Iterator[Path]:
    if SPECS_DIR.is_dir():
        yield from SPECS_DIR.glob("*.rst")


def _resolve_module_attr(module_path: str, attr_name: str = "") -> bool:
    """Check whether *module_path* (and optionally *attr_name*) is importable."""
    try:
        mod = importlib.import_module(module_path)
        if not attr_name:
            return True
        return hasattr(mod, attr_name)
    except ImportError:
        return False


def _html_spec_exists(filename: str) -> bool:
    """Check whether *filename* exists as a spec RST source.

    Returns True even if the specs dir doesn't exist (spec not yet built
    in CI — the link is still valid, just not yet verifiable).
    """
    if not SPECS_DIR.is_dir():
        return True
    rst_name = filename.replace(".html", ".rst")
    return (SPECS_DIR / rst_name).is_file()


def _resolve_docs_href(href: str) -> bool:
    """Check whether an href points to a real resource."""
    if href.startswith(("http://", "https://", "#", "mailto:", "latest/", "v", "../")):
        return True

    # spec sheet links: specs/<name>.html
    if href.startswith("specs/"):
        return _html_spec_exists(Path(href).name)

    # doc-relative links like circle.html — search all category dirs + root
    for d in _CATEGORY_DIRS + [""]:
        target = DOCS_DIR / d / href
        if target.exists():
            return True

    # wiki-relative: e.g. _static/..., _images/... — only check if wiki is built
    if WIKI_DIR.is_dir():
        target = WIKI_DIR / href
        if target.exists():
            return True

    return False


def _resolve_spec_href(href: str) -> bool:
    """Check whether an href in a spec sheet points to a real resource."""
    if href.startswith(("http://", "https://", "#", "mailto:")):
        return True

    # spec-local resources
    if href in ("spec.css",):
        return True

    # STL files: _stl/<name>.stl — only check if specs dir has STL cache
    if href.startswith("_stl/"):
        return (SPECS_DIR / href).exists() if SPECS_DIR.is_dir() else True

    # spec-local pages
    if SPECS_DIR.is_dir():
        target = SPECS_DIR / href
        if target.exists():
            return True

    # docs-local (API pages linked from specs)
    target = DOCS_DIR / href
    if target.exists():
        return True

    # wiki output (generated HTML from RST) — only check if built
    if WIKI_DIR.is_dir():
        target = WIKI_DIR / href
        if target.exists():
            return True

    # RST source (API page exists as .rst)
    stem = Path(href).stem
    rst = DOCS_DIR / f"{stem}.rst"
    return rst.exists()


# ── regex patterns ───────────────────────────────────────────────────────────

_RST_XREF_RE = re.compile(r":(class|meth|func|mod|attr|exc|doc|ref):`~?(pybosl2\.[^`]+)`")


def _resolve_xref(role: str, target: str) -> bool:
    """Check whether an RST cross-reference resolves to a real module/class/method.

    Handles forms like:
      ``pybosl2.path2d``           — module only
      ``pybosl2.path2d.Path2D``    — class in module
      ``pybosl2.path2d.Path2D.method`` — method on class
    """
    if role in ("doc", "ref"):
        return True

    parts = target.split(".")
    if parts[0] != "pybosl2":
        return False

    # Try progressively longer module paths
    for i in range(len(parts), 1, -1):
        module = ".".join(parts[:i])
        rest = parts[i:]
        try:
            mod = importlib.import_module(module)
        except ImportError:
            continue

        if not rest:
            return True  # module-only reference
        if len(rest) == 1:
            return hasattr(mod, rest[0])
        obj = getattr(mod, rest[0], None)
        if obj is None:
            continue
        for a in rest[1:]:
            obj = getattr(obj, a, None)
            if obj is None:
                break
        if obj is not None:
            return True
    return False


_RST_HREF_RE = re.compile(r'<([^>]+\.(?:html|css|js|png|svg|stl))>|href="([^"]+)"')

_TOCTREE_RE = re.compile(r"^\s{4}(?:\w[\w\s&;]+)?\s*<(\w+)>$", re.MULTILINE)

_SPEC_HREF_RE = re.compile(r'href="([^"]+)"')


# ── pre-existing false positives (refactored APIs) ───────────────────────────

_XREF_ALLOW_LIST = frozenset(
    {
        "func:pybosl2.path3d.helix",
        "func:pybosl2.path2d.catenary",
        "func:pybosl2.skin.sweep",
        "func:pybosl2.skin.skin",
        "func:pybosl2.rounding.round_corners",
        "func:pybosl2.rounding.smooth_path",
    }
)


# ── tests ────────────────────────────────────────────────────────────────────


class TestRstCrossReferences:
    @pytest.mark.parametrize("rst_file", list(_rst_files()), ids=lambda f: f.name)
    def test_all_xrefs_resolve(self, rst_file: Path) -> None:
        text = rst_file.read_text()
        failures: list[str] = []

        for match in _RST_XREF_RE.finditer(text):
            role = match.group(1)
            target = match.group(2)

            if not _resolve_xref(role, target):
                failures.append(f"{role}:{target}")

        assert not failures, f"Broken xrefs in {rst_file.name}:\n" + "\n".join(f"  - {f}" for f in failures)


class TestRstLocalLinks:
    @pytest.mark.parametrize("rst_file", list(_rst_files()), ids=lambda f: f.name)
    def test_local_links_exist(self, rst_file: Path) -> None:
        text = rst_file.read_text()
        failures: list[str] = []

        for groups in _RST_HREF_RE.findall(text):
            href = groups[0] or groups[1]
            if not _resolve_docs_href(href):
                failures.append(href)

        assert not failures, f"Broken links in {rst_file.name}:\n" + "\n".join(f"  - {f}" for f in failures)


class TestSpecSheetLinks:
    @pytest.mark.parametrize("spec_file", list(_spec_htmls()), ids=lambda f: f.name)
    def test_nav_links_exist(self, spec_file: Path) -> None:
        if not SPECS_DIR.is_dir():
            pytest.skip("specs directory not built")
        text = spec_file.read_text()
        failures: list[str] = []

        for href in _SPEC_HREF_RE.findall(text):
            if not _resolve_spec_href(href):
                failures.append(href)

        assert not failures, f"Broken links in {spec_file.name}:\n" + "\n".join(f"  - {f}" for f in failures)


class TestIndexTocTree:
    def test_all_toctree_entries_exist(self) -> None:
        index = (DOCS_DIR / "index.rst").read_text()
        failures: list[str] = []
        for match in _TOCTREE_RE.finditer(index):
            page = match.group(1)
            found_in_dirs = any((DOCS_DIR / d / f"{page}.rst").exists() for d in _CATEGORY_DIRS)
            found_in_root = (DOCS_DIR / f"{page}.rst").exists()
            if not found_in_dirs and not found_in_root:
                failures.append(page)
        assert not failures, "Broken toctree entries:\n" + "\n".join(f"  - {f}" for f in failures)

    @pytest.mark.parametrize(
        "group_page",
        [p for p in ["shapes2d.rst", "shapes3d.rst"] if (DOCS_DIR / "foundational" / p).exists()],
    )
    def test_group_toctree_entries_exist(self, group_page: str) -> None:
        text = (DOCS_DIR / "foundational" / group_page).read_text()
        failures: list[str] = []
        for match in _TOCTREE_RE.finditer(text):
            page = match.group(1)
            found_in_dirs = any((DOCS_DIR / d / f"{page}.rst").exists() for d in _CATEGORY_DIRS)
            found_in_root = (DOCS_DIR / f"{page}.rst").exists()
            if not found_in_dirs and not found_in_root:
                failures.append(page)
        assert not failures, f"Broken {group_page} toctree:\n" + "\n".join(f"  - {f}" for f in failures)


class TestSpecSheetCoverage:
    """Every spec sheet has a corresponding API .rst page and vice-versa for parts."""

    def test_spec_sheets_have_api_pages(self) -> None:
        if not SPECS_DIR.is_dir():
            pytest.skip("specs directory not built")
        failures: list[str] = []
        for spec in _spec_htmls():
            name = spec.stem
            if name == "index":
                continue
            found = any((DOCS_DIR / d / f"{name}.rst").exists() for d in _CATEGORY_DIRS)
            found = found or (DOCS_DIR / f"{name}.rst").exists()
            if not found:
                failures.append(name)
        assert not failures, "Spec sheets without API pages:\n" + "\n".join(f"  - {f}" for f in failures)


def test_no_module_is_documented_by_two_pages() -> None:
    """Two automodule blocks for one module make Sphinx report every member as a duplicate.

    A curated page (docs/paths/paths.rst covers paths + path2d + path3d together) is the canonical
    one; _rstgen skips stub generation for anything it already documents. This catches a stub that
    slipped in anyway.
    """
    import collections
    import re

    pattern = re.compile(r"^\.\. automodule:: ([\w.]+)", re.M)
    owners: dict[str, list[str]] = collections.defaultdict(list)
    for rst in DOCS_DIR.rglob("*.rst"):
        if "_build" in rst.parts:
            continue
        text = rst.read_text()
        for module in pattern.findall(text):
            owners[module].append(str(rst.relative_to(DOCS_DIR)))

    doubled = {module: pages for module, pages in owners.items() if len(pages) > 1}
    assert not doubled, f"modules documented by more than one page: {doubled}"


def test_import_pybosl2_needs_no_optional_dependency() -> None:
    """The PythonSCAD app's Python has no webcolors; importing pybosl2 must not need it (SPEC A-4)."""
    import subprocess
    import sys

    probe = "import sys;sys.modules['webcolors'] = None;import pybosl2;assert pybosl2.cuboid is not None;print('ok')"
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_every_facade_callable_documents_its_arguments_and_shows_an_example() -> None:
    """The layer the spec recommends must document itself (SPEC DOC-2, PLAN D-P4a, D-P5)."""
    import inspect

    import pybosl2.flat as flat
    import pybosl2.solid as solid

    undocumented: list[str] = []
    unillustrated: list[str] = []
    for module in (solid, flat):
        for name in module.__all__:
            function = getattr(module, name, None)
            if not inspect.isfunction(function) or function.__module__ != module.__name__:
                continue
            doc = inspect.getdoc(function) or ""
            signature = inspect.signature(function)
            if signature.parameters and "Args:" not in doc:
                undocumented.append(f"{module.__name__}.{name}")
            # D-P5 asks for a rendering example from anything that produces geometry; an
            # introspection helper like effective_defaults has nothing to render.
            builds_geometry = str(signature.return_annotation) in {"Solid", "Flat"}
            if builds_geometry and ".. pythonscad-example::" not in doc:
                unillustrated.append(f"{module.__name__}.{name}")
    assert not undocumented, f"façade callables with no Args: section: {undocumented}"
    assert not unillustrated, f"façade callables with no rendering example: {unillustrated}"


def test_every_facade_example_runs() -> None:
    """A docstring example that does not run is worse than none (SPEC DOC-2)."""
    import inspect
    import re
    import textwrap

    import pybosl2.flat as flat
    import pybosl2.solid as solid

    ran = 0
    for module in (solid, flat):
        for name in module.__all__:
            function = getattr(module, name, None)
            if not inspect.isfunction(function) or function.__module__ != module.__name__:
                continue
            doc = inspect.getdoc(function) or ""
            for block in re.split(r"\.\. pythonscad-example::\n", doc)[1:]:
                code_lines: list[str] = []
                for line in block.splitlines():
                    if line.strip() and not line.startswith("        "):
                        break
                    code_lines.append(line)
                code = textwrap.dedent("\n".join(code_lines))
                if not code.strip():
                    continue
                ran += 1
                exec(compile(code, f"<{module.__name__}.{name}>", "exec"), {})
    assert ran > 30, f"only {ran} façade examples were exercised"

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
SPECS_DIR = DOCS_DIR / "_extra" / "specs"
WIKI_DIR = REPO_ROOT / "wiki"


# ── helpers ──────────────────────────────────────────────────────────────────


def _rst_files() -> Iterator[Path]:
    yield from DOCS_DIR.glob("*.rst")


def _spec_htmls() -> Iterator[Path]:
    if SPECS_DIR.is_dir():
        yield from SPECS_DIR.glob("*.html")


def _resolve_module_attr(module_path: str, attr_name: str = "") -> bool:
    """Check whether *module_path* (and optionally *attr_name*) is importable."""
    try:
        mod = importlib.import_module(module_path)
        if not attr_name:
            return True
        return hasattr(mod, attr_name)
    except ImportError:
        return False


def _resolve_docs_href(href: str) -> bool:
    """Check whether an href in *rst_file* points to a real resource."""
    if href.startswith(("http://", "https://", "#", "mailto:")):
        return True

    # spec sheet links: specs/<name>.html
    if href.startswith("specs/"):
        return (SPECS_DIR / Path(href).name).exists()

    # doc-relative links like circle.html
    target = DOCS_DIR / href
    if target.exists():
        return True

    # wiki-relative: e.g. _static/..., _images/...
    target = WIKI_DIR / href
    return target.exists()


def _resolve_spec_href(href: str) -> bool:
    """Check whether an href in *spec_file* points to a real resource."""
    if href.startswith(("http://", "https://", "#", "mailto:")):
        return True

    # spec-local resources
    if href in ("spec.css",):
        return True

    # STL files: _stl/<name>.stl
    if href.startswith("_stl/"):
        return (SPECS_DIR / href).exists()

    # spec-local pages
    target = SPECS_DIR / href
    if target.exists():
        return True

    # docs-local (API pages linked from specs)
    target = DOCS_DIR / href
    in_docs = target.exists()

    # wiki output (generated HTML from RST)
    target = WIKI_DIR / href
    in_wiki = target.exists()

    # RST source (API page exists as .rst)
    stem = Path(href).stem
    rst = DOCS_DIR / f"{stem}.rst"
    in_rst = rst.exists()

    return in_docs or in_wiki or in_rst


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
            if not (DOCS_DIR / f"{page}.rst").exists():
                failures.append(page)
        assert not failures, "Broken toctree entries:\n" + "\n".join(f"  - {f}" for f in failures)

    @pytest.mark.parametrize(
        "group_page",
        [p for p in ["shapes2d.rst", "shapes3d.rst"] if (DOCS_DIR / p).exists()],
    )
    def test_group_toctree_entries_exist(self, group_page: str) -> None:
        text = (DOCS_DIR / group_page).read_text()
        failures: list[str] = []
        for match in _TOCTREE_RE.finditer(text):
            page = match.group(1)
            if not (DOCS_DIR / f"{page}.rst").exists():
                failures.append(page)
        assert not failures, f"Broken {group_page} toctree:\n" + "\n".join(f"  - {f}" for f in failures)


class TestSpecSheetCoverage:
    """Every spec sheet has a corresponding API .rst page and vice-versa for parts."""

    def test_spec_sheets_have_api_pages(self) -> None:
        failures: list[str] = []
        for spec in _spec_htmls():
            name = spec.stem
            if name == "index":
                continue
            if not (DOCS_DIR / f"{name}.rst").exists():
                failures.append(name)
        assert not failures, "Spec sheets without API pages:\n" + "\n".join(f"  - {f}" for f in failures)

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/docs/conf.py
#    Sphinx configuration for the pure-Python bosl2 port's API docs. Build with:
#
#        python3 -m pip install sphinx        # once
#        make -C bosl2/docs html              # -> bosl2/wiki/ (checked in)
#
#    Set PYTHONSCAD_BIN to a real PythonSCAD binary to get rendered images and exported STL
#    meshes in the ``bosl2-example`` blocks; without it the build still succeeds and shows source
#    only (see docs/_ext/bosl2_example.py). Unchanged examples reuse their cached image/STL.
#
#    Before autodoc touches the bosl2 modules, this file must (1) put the repo root on sys.path so
#    ``import bosl2`` resolves, and (2) make the ``pythonscad``/``openscad`` native modules
#    importable, because bosl2/shapes2d.py, shapes3d.py and masking.py import ``pythonscad`` at load
#    time. The supported setup is a venv with the real ``pythonscad`` wheel installed (``pip install
#    -e .[test]``); if that is not present we fall back to pysolidfive/tests/mock_libfive.py's
#    stand-ins when they can be found beside this checkout -- the same fallback the test-suite's
#    conftest uses.
#
# FileGroup: bosl2

from __future__ import annotations

import sys
from pathlib import Path

_DOCS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _DOCS_DIR.parent

sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_DOCS_DIR / "_ext"))

# Try to import the real pythonscad wheel; if the C extension cannot load on this platform
# (e.g. missing system libraries on a headless CI runner), fall back to the numeric mock.
# ``find_spec`` alone is not enough -- the wheel may be installed but fail to dlopen.
_have_pythonscad = False
try:
    import pythonscad  # noqa: F401

    _have_pythonscad = True
except ImportError:
    pass

if not _have_pythonscad:
    _mock_dir = _REPO_ROOT / "pysolidfive" / "tests"
    if (_mock_dir / "mock_libfive.py").is_file():
        sys.path.insert(0, str(_mock_dir))
        import mock_libfive  # noqa: E402,F401  -- installs pythonscad/openscad/libfive stubs
    else:
        raise RuntimeError(
            "docs build needs the pythonscad native modules: install the wheel with "
            "`pip install -e .[test]`, or provide pysolidfive/tests/mock_libfive.py in the repo"
        )

project = "bosl2 (PythonSCAD port)"
copyright = "2026, pinkfish"
author = "pinkfish"

# Keep the docs version in sync with the code's single source of truth
# (bosl2/version.py) without importing the package.
import re as _re  # noqa: E402

_version_src = (_DOCS_DIR.parent / "bosl2" / "version.py").read_text()
release = _re.search(r'__version__ = "([^"]+)"', _version_src).group(1)
version = release

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "stl_viewer",
    "bosl2_example",
    "bosl2_navsidebar",
]

# bosl2's docstrings use Google-style Args:/Returns:/Example: sections throughout.
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_custom_sections = [("Usage", "notes")]

autodoc_member_order = "bysource"
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
autodoc_typehints = "description"

intersphinx_mapping = {"numpy": ("https://numpy.org/doc/stable/", None)}

templates_path: list[str] = []
exclude_patterns: list[str] = ["_build", "_generated", "_extra"]

# The exported STL meshes live in _extra/_stl/; listing the _extra/ parent in html_extra_path
# copies the _stl/ subdirectory verbatim to the output root (html_extra_path flattens a listed
# directory's *contents* into the root, so the extra nesting level is what preserves the _stl/
# prefix). All doc pages sit at the docs root, so a relative ``_stl/<hash>.stl`` -- what both the
# interactive viewer and the download links use -- resolves from any of them.
html_extra_path = ["_extra"]

html_theme = "alabaster"
html_static_path: list[str] = ["_static"]
html_css_files: list[str] = ["pysidebar.css"]

# A grouped, always-visible global TOC so the many modules are easy to track. Alabaster renders each
# toctree ``:caption:`` from index.rst as a section header in the sidebar's navigation block.
html_theme_options = {
    "description": "A pure-Python PythonSCAD port of BOSL2",
    "fixed_sidebar": True,
    "sidebar_collapse": False,  # keep every group's pages visible, not just the current one's
    "page_width": "1120px",
    "sidebar_width": "255px",
    "extra_nav_links": {
        "Visual parts catalog →": "specs/index.html",
    },
}
html_sidebars = {
    "**": ["about.html", "navigation.html", "relations.html", "searchbox.html"],
}

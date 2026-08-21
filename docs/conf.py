# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/docs/conf.py
#    Sphinx configuration for the pure-Python pybosl2 port's API docs. Build with:
#
#        python3 -m pip install sphinx        # once
#        make -C pybosl2/docs html              # -> pybosl2/wiki/ (checked in)
#
#    Set PYTHONSCAD_BIN to a real PythonSCAD binary to get rendered images and exported STL
#    meshes in the ``pybosl2-example`` blocks; without it the build still succeeds and shows source
#    only (see docs/_ext/pybosl2_example.py). Unchanged examples reuse their cached image/STL.
#
#    Before autodoc touches the pybosl2 modules, this file puts the repo root on sys.path so
#    ``import pybosl2`` resolves. pybosl2 itself imports FFI-free (native primitives are lazy handles
#    from pybosl2/_native.py), but autodoc *constructs* geometry when it runs the docstring examples,
#    which needs the real ``pythonscad``/``openscad`` modules. The supported setup is a venv with
#    the real ``pythonscad`` wheel installed (``pip install -e .[test]``); if that is not present we
#    fall back to pybosl2's own tests/mock_libfive.py stand-ins -- the same fallback the test-suite's
#    conftest uses (no reach into the sibling pysolidfive package).
#
# FileGroup: pybosl2

from __future__ import annotations

import sys
from pathlib import Path

_DOCS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _DOCS_DIR.parent

sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_DOCS_DIR / "_ext"))
sys.path.insert(0, str(_DOCS_DIR))  # conf.py's own dir, so `import _specgen` resolves in setup()

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
    _mock_dir = _REPO_ROOT / "tests"  # pybosl2's own native mock (not the sibling pysolidfive's)
    if (_mock_dir / "mock_libfive.py").is_file():
        sys.path.insert(0, str(_mock_dir))
        import mock_libfive  # noqa: F401  -- installs pythonscad/openscad/libfive stubs
    else:
        raise RuntimeError(
            "docs build needs the pythonscad native modules: install the wheel with "
            "`pip install -e .[test]`, or provide tests/mock_libfive.py in the repo"
        )

project = "pybosl2 (PythonSCAD port)"
copyright = "2026, pinkfish"  # noqa: A001
author = "pinkfish"

# Keep the docs version in sync with the code's single source of truth
# (pybosl2/version.py) without importing the package.
import re as _re  # noqa: E402

_version_src = (_DOCS_DIR.parent / "pybosl2" / "version.py").read_text()
release = _re.search(r'__version__ = "([^"]+)"', _version_src).group(1)
version = release

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_immaterial",
    "stl_viewer",
    "pybosl2_example",
]

# pybosl2's docstrings use Google-style Args:/Returns:/Example: sections throughout.
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

html_theme = "sphinx_immaterial"
html_static_path: list[str] = ["_static"]
html_favicon = "_static/favicon.png"
html_logo = "_static/logo.png"
html_css_files: list[str] = ["specs.css"]


html_theme_options = {
    "icon": {
        "repo": "fontawesome/brands/github",
    },
    "site_url": "https://pybosl2.org/",
    "repo_url": "https://github.com/pinkfish/pybosl2/",
    "repo_name": "pybosl2",
    "features": [
        "navigation.sections",
        "navigation.expand",
        "navigation.top",
        "navigation.footer",
        "toc.follow",
        "toc.sticky",
        "content.code.copy",
        "content.tooltips",
    ],
    "palette": [
        {
            "media": "(prefers-color-scheme)",
            "scheme": "default",
            "primary": "indigo",
            "accent": "teal",
            "toggle": {
                "icon": "material/brightness-auto",
                "name": "Switch to light mode",
            },
        },
        {
            "media": "(prefers-color-scheme: light)",
            "scheme": "default",
            "primary": "indigo",
            "accent": "teal",
            "toggle": {
                "icon": "material/lightbulb",
                "name": "Switch to dark mode",
            },
        },
        {
            "media": "(prefers-color-scheme: dark)",
            "scheme": "slate",
            "primary": "indigo",
            "accent": "teal",
            "toggle": {
                "icon": "material/lightbulb-outline",
                "name": "Switch to system preference",
            },
        },
    ],
    "font": False,
    "toc_title": "On this page",
}

object_description_options = [
    ("py:parameter", {"include_in_toc": False}),
    ("py:.*Param", {"include_in_toc": False}),
    ("py:attribute", {"include_in_toc": False}),
    ("py:attribute:pybosl2.enums.*", {"include_in_toc": True}),
    ("py:data", {"include_in_toc": False}),
    ("py:exception", {"include_in_toc": False}),
    ("py:module", {"include_in_toc": False}),
    ("py:class", {"include_in_toc": True}),
    ("py:function", {"include_in_toc": True}),
    ("py:method", {"include_in_toc": True}),
]


def setup(app):
    """Regenerate docs artifacts from the live module structure before each build.

    ``_specgen.py`` rebuilds the visual spec-sheet pages (``_extra/specs/*.html``)
    from committed STL caches. ``_covgen.py`` rebuilds the BOSL2 coverage table
    (``bosl2_coverage.rst``). ``_rstgen.py`` regenerates ``index.rst``, creates
    stub ``.rst`` files for new modules, and validates all cross-references against
    the current package layout — so module moves/renames are caught automatically.
    """
    _regenerate_specs_patched(app)
    _regenerate_coverage_patched(app)
    _regenerate_rsts_patched(app)

    _patch_typehints_self_leak(app)

    return {"parallel_read_safe": True, "parallel_write_safe": True}


def _patch_typehints_self_leak(app):
    """Strip ``self`` from recorded type annotations so it does not leak into
    autodoc field lists when methods have typed ``self`` (``self: Path3D``).

    The issue is in ``sphinx/ext/autodoc/typehints.py``: ``record_typehints``
    captures *all* parameters (including ``self`` when typed) by calling
    ``inspect.signature(obj, bound_method=False)``, while
    ``MethodDocumenter.format_args`` correctly strips ``self`` with
    ``bound_method=True``.  The mismatched parameter list causes
    ``:param self:`` to be injected into the docstring field list, which
    Napoleon then flags as unmatched.
    """

    def _strip_self(
        app: object,
        _what: str,
        name: str,
        _obj: object,
        _options: object,
        _signature: str,
        _return_annotation: str,
    ) -> None:
        annotations = app.env.temp_data.get("annotations", {})
        if name in annotations:
            annotations[name].pop("self", None)

    app.connect("autodoc-process-signature", _strip_self, priority=999)


def _regenerate_specs_patched(app):
    def _regenerate_specs(_app):
        import _specgen

        _specgen.main()

    app.connect("builder-inited", _regenerate_specs)


def _regenerate_coverage_patched(app):
    def _regenerate_coverage(_app):
        import _covgen

        _covgen.main()

    app.connect("builder-inited", _regenerate_coverage)


def _regenerate_rsts_patched(app):
    def _regenerate_rsts(_app):
        import _rstgen

        warnings = _rstgen.main(verbose=True)
        if warnings:
            print(f"_rstgen: {len(warnings)} broken cross-references detected")

    app.connect("builder-inited", _regenerate_rsts)

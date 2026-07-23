# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# pytest fixtures/setup for the bosl2 package test-suite.
#
# The bosl2 modules that touch native geometry (shapes2d/shapes3d/masking, and the
# .polygon()/.polyhedron() FFI boundaries) import `pythonscad`/`openscad` at load time. These
# modules must therefore be importable BEFORE any test module -- and therefore any bosl2 module --
# is imported.
#
# The supported setup is a venv with the real `pythonscad` wheel installed (`pip install -e
# .[test]`), which provides genuine `pythonscad` and `openscad` modules. If that wheel is not
# installed, we fall back to the shared numeric mock (pysolidfive/tests/mock_libfive.py) when it is
# present next to this checkout, so the pure-Python suite can still run without PythonSCAD at all.

import importlib.util
import os
import sys


def _pythonscad_installed() -> bool:
    """True if the real `pythonscad` wheel is importable in this interpreter."""
    try:
        return importlib.util.find_spec("pythonscad") is not None
    except (ImportError, ValueError):
        return False


def _install_mock() -> bool:
    """Install the shared numeric mock from the in-repo pysolidfive package; return success."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    mock_dir = os.path.join(repo_root, "pysolidfive", "tests")
    if not os.path.isfile(os.path.join(mock_dir, "mock_libfive.py")):
        return False
    for p in (repo_root, mock_dir):
        if p not in sys.path:
            sys.path.insert(0, p)
    import mock_libfive  # noqa: F401  -- installs pythonscad/openscad/libfive stubs on import

    return True


if not _pythonscad_installed():
    if not _install_mock():
        import pytest

        pytest.skip(
            "neither the real `pythonscad` wheel nor the numeric mock is available; "
            "run `pip install -e .[test]` in a venv to install PythonSCAD",
            allow_module_level=True,
        )

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# pytest fixtures/setup for the bosl2 package test-suite.
#
# The bosl2 package imports FFI-free (native primitives are lazy handles from bosl2/_native.py), so
# the modules load without `pythonscad`; the FFI is only needed once a test actually *constructs*
# geometry. The supported setup is a venv with the real `pythonscad` wheel installed (`pip install
# -e .[test]`), which provides genuine `pythonscad`/`openscad` modules. If that wheel is not
# installed, we fall back to bosl2's own numeric mock (tests/mock_libfive.py) so the pure-Python
# suite can still run without PythonSCAD at all. The mock is owned by this package -- no reach into
# the sibling pysolidfive package's test tree.

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
    """Install bosl2's own numeric native mock (tests/mock_libfive.py); return success."""
    mock_dir = os.path.dirname(__file__)
    if not os.path.isfile(os.path.join(mock_dir, "mock_libfive.py")):
        return False
    if mock_dir not in sys.path:
        sys.path.insert(0, mock_dir)
    import mock_libfive  # noqa: F401  -- installs pythonscad/openscad/libfive stubs on import

    return True


if not _pythonscad_installed() and not _install_mock():
    import pytest

    pytest.skip(
        "neither the real `pythonscad` wheel nor the numeric mock is available; "
        "run `pip install -e .[test]` in a venv to install PythonSCAD",
        allow_module_level=True,
    )

# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

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
    """Install the shared numeric mock if it can be found beside this checkout; return success."""
    here = os.path.dirname(__file__)
    root = os.path.abspath(os.path.join(here, "..", ".."))
    mock_dir = os.path.join(root, "pysolidfive", "tests")
    if not os.path.isfile(os.path.join(mock_dir, "mock_libfive.py")):
        return False
    for p in (root, mock_dir):
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

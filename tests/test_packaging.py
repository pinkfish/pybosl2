# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""What ships is a separate claim from what builds (SPEC Q-7).

Every other gate in this project reads the working copy. These read the packaging metadata, which
is what decides the contents of a release -- the gap that let `py.typed` be absent from every
wheel published so far while `mypy --strict` ran clean on every commit.

The full gate builds a wheel, installs it into a clean virtualenv and type-checks a consumer
snippet against it; that lives in CI (`.github/workflows/tests.yml`, the `artifact` job) because it
needs a network and a build. What is here is the cheap half: the declarations that decide what the
build collects, so a regression is caught at `pytest` speed rather than at release.
"""

from __future__ import annotations

import pathlib
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _package_data() -> list[str]:
    """Return the package-data patterns declared for `pybosl2`."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    data = pyproject["tool"]["setuptools"].get("package-data", {})
    return list(data.get("pybosl2", []))


def test_the_marker_exists() -> None:
    """PEP 561's declaration that this package's inline types are intentional."""
    marker = ROOT / "pybosl2" / "py.typed"
    assert marker.exists(), "pybosl2/py.typed is missing: PEP 561 needs it to declare the package typed"
    assert marker.stat().st_size == 0, "py.typed is a marker, not a file with contents"


def test_the_marker_is_declared_as_package_data() -> None:
    """setuptools ships `.pyi` files unasked but never `py.typed`, so it has to be asked."""
    assert "py.typed" in _package_data(), (
        "pyproject.toml does not list py.typed under [tool.setuptools.package-data]; "
        "without it the marker exists in the tree and is absent from every wheel"
    )


def test_every_stub_in_the_tree_is_declared() -> None:
    """A stub the build does not collect is a stub that only ever helps this working copy."""
    patterns = _package_data()
    assert any(p.endswith("*.pyi") for p in patterns), f"no .pyi pattern in package-data: {patterns}"
    stubs = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "pybosl2").rglob("*.pyi"))
    assert stubs, "the stub parity test (T-8) has stubs to check; this one found none"
    nested = [s for s in stubs if s.count("/") > 1]
    if nested:
        assert any("**/*.pyi" in p for p in patterns), f"nested stubs {nested} need a recursive pattern"

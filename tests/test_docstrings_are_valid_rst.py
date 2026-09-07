# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Every docstring parses as the RST the documentation build will read it as.

SPEC DOC-2. The docs are built with Sphinx and napoleon, so a docstring is not free text: it is
reStructuredText, and a malformed one becomes a warning in a build nobody runs locally. Two
arrived from CI as::

    caps.py:docstring of pybosl2.caps:12: ERROR: Unexpected indentation.
    caps.py:docstring of pybosl2.caps:13: WARNING: Block quote ends without a blank line.

from a list item whose continuation line was indented deeper than the line above it. Nothing in
the local gates reads docstrings as markup, so the only signal was a CI log.

This runs the same two stages the build does -- `napoleon` first, turning Google-style `Args:`
sections into RST, then `docutils` -- and fails on the diagnostics that mean the *structure* was
misread. Sphinx-only roles (`:class:`, `:func:`, `:mod:`) are unknown to bare docutils and are
deliberately not checked here; a missing target is a different problem with a different fix, and
including it would bury the structural faults in hundreds of false positives. That was measured:
without napoleon the same scan reports **441** diagnostics, essentially all of them `Args:` blocks
that napoleon would have rewritten. An instrument that noisy would never have been run.

**Only modules whose file lives in this repository are checked.** A stale copy of the package
installed in site-packages -- here a v0.7.8 with the pre-rename `_sdf` layout -- otherwise turns up
in the walk and reports a defect in a file no one can edit. The first version of this scan spent a
while blaming the working tree for it.
"""

from __future__ import annotations

import importlib
import inspect
import io
import pathlib
import pkgutil
import re
import warnings
from typing import Any

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Diagnostics that mean the document *structure* was misread -- the class that reaches a reader
#: as mangled output rather than a missing hyperlink.
STRUCTURAL = re.compile(
    r"(Unexpected indentation"
    r"|Block quote ends without a blank line"
    r"|Definition list ends without a blank line"
    r"|Bullet list ends without a blank line"
    r"|Enumerated list ends without a blank line"
    r"|Field list ends without a blank line"
    r"|Unexpected section title"
    r"|Inline .*? start-string without end-string"
    r"|Inline .*? end-string without a start-string"
    r"|Malformed table"
    r"|Title underline too short)"
)

docutils_core = pytest.importorskip("docutils.core", reason="docs extras not installed")
napoleon = pytest.importorskip("sphinx.ext.napoleon", reason="docs extras not installed")


def _diagnostics(text: str) -> list[str]:
    """Return the structural complaints Sphinx's own pipeline would raise for *text*."""
    rendered = str(napoleon.GoogleDocstring(inspect.cleandoc(text), napoleon.Config(napoleon_use_param=True)))
    stream = io.StringIO()
    docutils_core.publish_doctree(
        rendered,
        settings_overrides={
            "report_level": 2,
            "halt_level": 5,
            "warning_stream": stream,
            "file_insertion_enabled": False,
            "raw_enabled": False,
        },
    )
    return [line for line in stream.getvalue().splitlines() if STRUCTURAL.search(line)]


def _owned(obj: Any) -> bool:
    """Whether *obj* was defined by a file inside this repository."""
    try:
        path = inspect.getfile(obj)
    except (TypeError, OSError):
        return False
    return ROOT in pathlib.Path(path).resolve().parents


def _documented() -> list[tuple[str, str]]:
    """Every public docstring in the package, as ``(where, text)``."""
    warnings.filterwarnings("ignore")
    import pybosl2

    found: list[tuple[str, str]] = []
    for info in pkgutil.walk_packages(pybosl2.__path__, "pybosl2."):
        try:
            module = importlib.import_module(info.name)
        except Exception:  # pragma: no cover - an unimportable module is another test's problem
            continue
        if not _owned(module):
            continue
        if module.__doc__:
            found.append((info.name, module.__doc__))
        for name, obj in vars(module).items():
            if name.startswith("_") or getattr(obj, "__module__", None) != info.name:
                continue
            if inspect.isclass(obj):
                if obj.__doc__:
                    found.append((f"{info.name}.{name}", obj.__doc__))
                for attr, member in vars(obj).items():
                    if not attr.startswith("_") and inspect.isfunction(member) and member.__doc__:
                        found.append((f"{info.name}.{name}.{attr}", member.__doc__))
            elif inspect.isfunction(obj) and obj.__doc__:
                found.append((f"{info.name}.{name}", obj.__doc__))
    return found


DOCSTRINGS = _documented()


def test_the_scan_found_the_docstrings() -> None:
    """A walk that imported nothing would make the check below vacuous."""
    assert len(DOCSTRINGS) > 500, f"only {len(DOCSTRINGS)} docstrings found; the walk is broken"


def test_no_docstring_is_structurally_malformed() -> None:
    """SPEC DOC-2: a docstring is RST, and one the parser misreads reaches the reader mangled."""
    broken = [f"{where}: {line}" for where, text in DOCSTRINGS for line in _diagnostics(text)]
    assert not broken, "docstrings the documentation build will misread:\n" + "\n".join(broken)


def test_the_scan_catches_the_fault_that_prompted_it() -> None:
    """SPEC DOC-2: the check is only worth its runtime if it sees the shape CI reported.

    A list whose continuation line is indented deeper than the line above it -- exactly what
    `caps.py`'s `CIRCLE` entry became when a one-line item grew into two.
    """
    planted = "\n".join(
        [
            "Cap types",
            "    ``NONE`` -- no cap",
            "    ``CIRCLE`` -- round-over end cap: a flat end with its rim filleted. `length` sets",
            "        the fillet radius as a fraction of the half-width",
            "    ``CUSTOM`` -- user-supplied path",
        ]
    )
    assert _diagnostics(planted), "the planted over-indent was not caught"
    assert not _diagnostics(planted.replace("        the fillet", "    the fillet"))

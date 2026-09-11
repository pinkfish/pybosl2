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


# --- cross-references (T69) --------------------------------------------------------------------

#: Every Sphinx role that names a Python object. A reference to one that has moved is a dead link
#: in the published docs, and dead links are what T68's structural check deliberately left out --
#: "a different problem with a different fix". This is the fix.
ROLE = re.compile(r":(class|func|meth|mod|data|attr|obj|exc):`~?([A-Za-z0-9_.]+)`")


def _resolves(target: str) -> bool | None:
    """Whether *target* names something that exists. `None` when it is not ours to check.

    Walks the dotted name from the longest importable prefix inwards, so `pybosl2.path2d.Path2D`
    and `pybosl2.path2d.Path2D.polygon` are both answerable without knowing which parts are
    modules. Lazy re-exports resolve, because `getattr` triggers them exactly as a reader would.
    """
    if not target.startswith("pybosl2"):
        return None
    parts = target.split(".")
    for cut in range(len(parts), 0, -1):
        try:
            obj: Any = importlib.import_module(".".join(parts[:cut]))
        except Exception:
            continue
        for attr in parts[cut:]:
            obj = getattr(obj, attr, None)
            if obj is None:
                return False
        return True
    return False


def _references() -> dict[str, list[str]]:
    """Every `pybosl2` role reference in the package, mapped to the docstrings that make it."""
    found: dict[str, list[str]] = {}
    for where, text in DOCSTRINGS:
        for role, target in ROLE.findall(text):
            found.setdefault(f":{role}:`{target}`", []).append(where)
    return found


REFERENCES = _references()


def test_the_scan_found_the_references() -> None:
    """A regex matching nothing would make the check below vacuous."""
    assert len(REFERENCES) > 100, f"only {len(REFERENCES)} role references found; the scan is broken"


def test_every_cross_reference_resolves() -> None:
    """SPEC DOC-2: a role naming something that has moved is a dead link a reader clicks.

    Eighteen were broken when this was written, every one of them a name that had moved module
    while the reference stayed put -- `pybosl2.paths.Path2D` for what is now `pybosl2.path2d`,
    `pybosl2.enums.Anchor` for `pybosl2._edges_lang`, and five pointing at things deleted outright.
    Nothing had ever resolved them, because a role that fails to resolve is a Sphinx *warning* in a
    build no local gate runs, and reads perfectly well in the source.
    """
    broken = {
        ref: sorted(set(where))[:3]
        for ref, where in REFERENCES.items()
        if _resolves(ROLE.fullmatch(ref).group(2)) is False  # type: ignore[union-attr]
    }
    assert not broken, "cross-references that do not resolve:\n" + "\n".join(
        f"  {ref}  <- {where}" for ref, where in sorted(broken.items())
    )


def test_the_resolver_answers_both_ways() -> None:
    """SPEC DOC-2: a resolver that said yes to everything would pass the check above silently."""
    assert _resolves("pybosl2.path2d.Path2D") is True
    assert _resolves("pybosl2.path2d.Path2D.polygon") is True, "methods must resolve, not just types"
    assert _resolves("pybosl2.paths.Path2D") is False, "the exact stale reference this task fixed"
    assert _resolves("pybosl2.path2d.NoSuchThing") is False
    assert _resolves("numpy.ndarray") is None, "other projects are not ours to check"

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Every documented example is executed, because an example is a promise that it works.

SPEC DOC-5, Q-6. The 322 `.. pythonscad-example::` snippets are already checked three ways --
`tests/validate_examples.py` compiles them and resolves their imports and names, and
`tests/test_docstring_examples.py` runs `mypy --strict` over each one. None of the three *runs*
them, so an example that parses, imports, type-checks and then raises was invisible.

Not merely invisible: the documentation build **swallows it**. `docs/_ext/pybosl2_example.py`
renders the snippet's source, tries to build an STL, and on failure emits a warning and shows the
source anyway "rather than failing the build". So a broken example ships as documentation, minus
its viewer, and the reader who copies it is the one who finds out.

Two of the 322 failed when this was written, and only one was a defect in the example. The other
needs a runtime this environment does not have, which is the reason for the exception list below
rather than a reason to skip the whole check: an example that cannot run *here* still has to be
distinguishable from one that cannot run *anywhere*.

The failing one is worth its own note. `osimport("part.stl")` referenced a file that exists
nowhere, so it could never have worked for any reader. Making it self-contained meant writing the
mesh first -- and that turned up a second defect the example had been hiding: `osimport` does not
resolve relative paths at all, while its docstring promised they resolved "against the PROCESS
working directory". Measured, a bare name fails with the file in the process working directory
*and* with it in the directory the interpreter started in.
"""

from __future__ import annotations

import contextlib
import io
import math
import os
import sys
import tempfile
import traceback
import warnings
from pathlib import Path

import numpy as np
import pytest

from tests.validate_examples import _extract_py_examples, _extract_rst_examples

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Examples needing a runtime this environment does not provide. Each names the operation and the
#: runtime, so a row cannot quietly become "this one is broken". `roof` is the PythonSCAD *app*'s
#: own operation; the pip wheel does not carry it, which `tests/test_declared_surface.py` records
#: as `APP_ONLY` for exactly the same reason. Only shrinks.
NEEDS_A_RUNTIME_WE_LACK = {
    "roof": "the PythonSCAD app provides roof(); the pip wheel does not (APP_ONLY)",
}


def _examples() -> list[tuple[str, str]]:
    """Every documented snippet, as ``(where, source)``."""
    found = []
    for path, lineno, code in list(_extract_py_examples()) + list(_extract_rst_examples()):
        found.append((f"{Path(path).relative_to(REPO_ROOT)}:{lineno}", code))
    return found


EXAMPLES = _examples()


def _excuse(code: str) -> str | None:
    """The declared reason this example cannot run here, if it has one."""
    return next((why for name, why in NEEDS_A_RUNTIME_WE_LACK.items() if name in code), None)


def _run(code: str, where: str) -> BaseException | None:
    """Execute one example in a scratch directory, returning what it raised."""
    namespace = {
        "__name__": "__example__",
        "sys": sys,
        "math": math,
        "np": np,
        "os": os,
        "traceback": traceback,
    }
    started = Path.cwd()
    with tempfile.TemporaryDirectory() as scratch:
        # In its own directory, because an example is allowed to write a file (the `osimport` one
        # does) and must not leave it in the tree or read one another's leavings.
        os.chdir(scratch)
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                warnings.simplefilter("ignore")
                exec(compile(code, where, "exec"), namespace)
        except BaseException as exc:
            return exc
        finally:
            os.chdir(started)
    return None


def test_there_are_examples_to_run() -> None:
    """A scan matching nothing would make the check below vacuous."""
    assert len(EXAMPLES) > 250, f"only {len(EXAMPLES)} examples found; the extractor is broken"


@pytest.mark.parametrize(("where", "code"), EXAMPLES, ids=[w for w, _ in EXAMPLES])
def test_the_example_runs(where: str, code: str) -> None:
    """SPEC DOC-5: an example is the code a reader copies, so it has to be code that works."""
    excuse = _excuse(code)
    raised = _run(code, where)
    if excuse:
        pytest.skip(f"{where}: {excuse}")
    assert raised is None, f"{where} raised {type(raised).__name__}: {raised}"


def test_the_exception_list_is_not_stale() -> None:
    """SPEC DOC-5: a row for an example that runs makes the docs look worse than they are."""
    still_failing = {
        name
        for name, _ in NEEDS_A_RUNTIME_WE_LACK.items()
        for where, code in EXAMPLES
        if name in code and _run(code, where) is not None
    }
    unused = sorted(set(NEEDS_A_RUNTIME_WE_LACK) - still_failing)
    assert not unused, f"{unused} run now -- take them out of NEEDS_A_RUNTIME_WE_LACK"


def test_the_exception_list_only_shrinks() -> None:
    """SPEC DOC-5: an example may not join the list to avoid being fixed."""
    assert len(NEEDS_A_RUNTIME_WE_LACK) <= 1, (
        f"{sorted(NEEDS_A_RUNTIME_WE_LACK)} -- the list only shrinks, and each row names a "
        f"missing *runtime*, never a broken example."
    )

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Everything the façade exports is discoverable through `dir()` (SPEC DOC-5).

The top level is the front door -- the docs tell a newcomer to start at `import pybosl2`. Its
exports are resolved lazily by a module `__getattr__`, so until something asks for a name it does
not exist in `globals()`. PEP 562 pairs that hook with a module `__dir__` for exactly this reason;
without it `dir(pybosl2)` listed 3 public names out of 191, and every REPL and IDE completion
built on `dir()` showed a nearly empty module.
"""

import subprocess
import sys

import pytest

import pybosl2


def test_every_export_is_listed_by_dir() -> None:
    """`dir()` covers `__all__`, so completion offers the whole façade."""
    missing = sorted(name for name in pybosl2.__all__ if name not in dir(pybosl2))
    assert not missing, f"exported but invisible to dir(): {missing}"


def test_dir_does_not_depend_on_what_has_been_touched() -> None:
    """A fresh interpreter lists the same names as a warmed-up one.

    The regression this guards against was self-concealing: accessing a name promoted it into
    `globals()`, so `dir()` grew as a session went on and looked fine once anything had been used.
    """
    code = "import pybosl2; print(len([n for n in pybosl2.__all__ if n not in dir(pybosl2)]))"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "0", f"a cold interpreter hides exports: {out.stdout!r}"


def test_dir_is_sorted_and_has_no_duplicates() -> None:
    """What completion shows should be stable and in order."""
    listing = dir(pybosl2)
    assert listing == sorted(listing)
    assert len(listing) == len(set(listing))


def test_a_name_that_is_not_exported_still_fails() -> None:
    """Widening `dir()` must not make the module claim names it does not have."""
    assert "definitely_not_a_real_export" not in dir(pybosl2)
    name = "definitely_not_a_real_export"  # via a variable: ruff rewrites a literal getattr
    with pytest.raises(AttributeError):
        getattr(pybosl2, name)

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for the pybosl2.version module: the Version class and the package version metadata."""

import pytest

import pybosl2
from pybosl2.version import Version, __version__, version


def test_package_exposes_version_metadata() -> None:
    assert isinstance(__version__, str)
    assert pybosl2.__version__ == __version__  # type: ignore[attr-defined]
    assert isinstance(pybosl2.version, Version)  # type: ignore[attr-defined]
    assert isinstance(pybosl2.Version, type)  # type: ignore[attr-defined]


def test_default_version_parses() -> None:
    # The in-code default version is a well-formed major.minor.update string.
    assert version.string == __version__
    assert version.as_tuple() == tuple(int(p) for p in __version__.split(".")[:3])


def test_components_and_string() -> None:
    v = Version("1.2.3")
    assert (v.major, v.minor, v.update) == (1, 2, 3)
    assert v.string == "1.2.3"
    assert str(v) == "1.2.3"
    assert repr(v) == "Version('1.2.3')"


def test_leading_v_and_short_forms() -> None:
    assert Version("v2.5.7").as_tuple() == (2, 5, 7)
    assert Version("1.4").as_tuple() == (1, 4, 0)  # missing update defaults to 0
    assert Version("3").as_tuple() == (3, 0, 0)


def test_defaults_to_package_version() -> None:
    assert Version() == Version(__version__)


def test_comparisons_and_equality() -> None:
    assert Version("1.2.3") == "1.2.3"
    assert Version("1.2.3") == Version("1.2.3")
    assert Version("1.2.3") < Version("1.2.4")
    assert Version("1.2.3") < "1.3.0"
    assert Version("2.0.0") > Version("1.9.9")
    assert Version("1.0.0") <= "1.0.0"
    assert sorted([Version("1.2.0"), Version("1.10.0"), Version("1.1.0")]) == [
        Version("1.1.0"),
        Version("1.2.0"),
        Version("1.10.0"),
    ]


def test_compares_against_a_plain_string_in_both_directions() -> None:
    # >= and > used to raise TypeError against a str while < and <= worked: Python reflects
    # `Version > str` to `str.__lt__(Version)`, which declines. A minimum-version guard is the
    # natural thing for a caller to write, so it must not be the broken direction.
    assert Version("1.2.3") >= "1.2.3"
    assert Version("1.2.3") >= "1.2.0"
    assert Version("1.2.3") > "1.2.0"
    assert not Version("1.2.3") >= "1.3.0"
    assert not Version("1.2.3") > "1.2.3"
    # ...and the already-working direction still agrees with it.
    assert Version("1.2.3") <= "1.2.3"
    assert Version("1.2.3") < "1.3.0"


def test_package_version_satisfies_its_own_guard() -> None:
    """The shipped version compares as at least itself -- the check a consumer would write."""
    assert version >= __version__
    assert not version > __version__


def test_invalid_version_raises() -> None:
    with pytest.raises(ValueError, match="invalid version string"):
        Version("1.x.3")
    with pytest.raises(ValueError, match="invalid version string"):
        Version("not-a-version")

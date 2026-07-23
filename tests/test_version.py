# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for the bosl2.version module: the Version class and the package version metadata."""

import pytest

import bosl2
from bosl2.version import Version, __version__, version


def test_package_exposes_version_metadata():
    assert isinstance(__version__, str)
    assert bosl2.__version__ == __version__
    assert isinstance(bosl2.version, Version)
    assert isinstance(bosl2.Version, type)


def test_default_version_parses():
    # The in-code default version is a well-formed major.minor.update string.
    assert version.string == __version__
    assert version.as_tuple() == tuple(int(p) for p in __version__.split(".")[:3])


def test_components_and_string():
    v = Version("1.2.3")
    assert (v.major, v.minor, v.update) == (1, 2, 3)
    assert v.string == "1.2.3"
    assert str(v) == "1.2.3"
    assert repr(v) == "Version('1.2.3')"


def test_leading_v_and_short_forms():
    assert Version("v2.5.7").as_tuple() == (2, 5, 7)
    assert Version("1.4").as_tuple() == (1, 4, 0)  # missing update defaults to 0
    assert Version("3").as_tuple() == (3, 0, 0)


def test_defaults_to_package_version():
    assert Version() == Version(__version__)


def test_comparisons_and_equality():
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


def test_invalid_version_raises():
    with pytest.raises(ValueError):
        Version("1.x.3")
    with pytest.raises(ValueError):
        Version("not-a-version")

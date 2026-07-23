# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/version.py
#    Single source of truth for the package version. ``__version__`` below is the
#    DEFAULT version baked into the source; the release workflow
#    (.github/workflows/release.yml) rewrites that one string literal from the
#    published GitHub release tag. Everything else derives from it:
#      * pyproject.toml reads it via setuptools' dynamic ``attr =
#        "bosl2.version.__version__"`` (so the installed package version matches).
#      * docs/conf.py reads it for the rendered docs' version string.
#      * ``bosl2.Version`` / ``bosl2.version`` expose the parsed components.
#
# FileSummary: Package version metadata and the Version class.
# FileGroup: BOSL2

from __future__ import annotations

# The default version baked into the code. The release GitHub workflow rewrites
# the literal on the next line to match the release tag (e.g. a "v1.2.3" release
# sets this to "1.2.3"). Keep it a plain string literal so setuptools can read it
# by AST without importing the package.
__version__ = "0.5.1"


class Version:
    """A semantic ``major.minor.update`` version.

    Exposes each numeric component and a string form, so callers can branch on
    ``version.major``/``version.minor``/``version.update`` or render ``str(version)``.

    Args:
        version: A dotted version string such as ``"1.2.3"`` (an optional leading
            ``v`` is accepted). Missing trailing components default to ``0`` — e.g.
            ``"1.2"`` parses as ``1.2.0``. Defaults to the package :data:`__version__`.

    Attributes:
        major (int): The major (breaking-change) component.
        minor (int): The minor (feature) component.
        update (int): The update/patch component.
    """

    def __init__(self, version: str = __version__) -> None:
        parts = str(version).strip().lstrip("vV").split(".")
        if len(parts) < 3:
            parts = parts + ["0"] * (3 - len(parts))
        try:
            self.major, self.minor, self.update = (int(p) for p in parts[:3])
        except ValueError as exc:
            raise ValueError(f"invalid version string: {version!r}") from exc

    @property
    def string(self) -> str:
        """The ``major.minor.update`` string form (e.g. ``"1.2.3"``)."""
        return f"{self.major}.{self.minor}.{self.update}"

    def as_tuple(self) -> tuple[int, int, int]:
        """The version as a ``(major, minor, update)`` tuple, handy for comparisons."""
        return (self.major, self.minor, self.update)

    def __str__(self) -> str:
        return self.string

    def __repr__(self) -> str:
        return f"Version({self.string!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            other = Version(other)
        if isinstance(other, Version):
            return self.as_tuple() == other.as_tuple()
        return NotImplemented

    def __lt__(self, other: "Version | str") -> bool:
        other = other if isinstance(other, Version) else Version(other)
        return self.as_tuple() < other.as_tuple()

    def __le__(self, other: "Version | str") -> bool:
        return self < other or self == other

    def __hash__(self) -> int:
        return hash(self.as_tuple())


# The package version as a parsed Version instance, built from the default above.
version = Version(__version__)

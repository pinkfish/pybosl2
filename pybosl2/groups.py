# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/groups.py
#    Argument groups -- the parameter families that always travel together.
#
#    Some parameters are never really independent. A shape's placement is three of them
#    (``anchor``, ``spin``, ``orient``) and they are passed as a unit, restated at every level of
#    every call chain, and re-declared by every constructor that forwards them. A group makes the
#    unit a value:
#
#        from pybosl2 import Placement, Anchor, cuboid, cyl
#
#        upright = Placement(anchor=Anchor.BOTTOM, orient=Anchor.TOP)
#        plate = cuboid([60, 40, 8], placement=upright)
#        boss = cyl(height=10, radius=4, placement=upright)
#
#    The loose spellings still work and are still the common case (SPEC G-3) -- ``cuboid([60, 40,
#    8], anchor=Anchor.BOTTOM)`` reads better than wrapping one value in a group. What a group is
#    for is a placement used more than once, or threaded through code of your own.
#
#    Giving both a group and one of its members raises, the way a radius and its own diameter do
#    (SPEC D-5): the call cannot mean two things at once.
#
#    ``Facets`` is the same idea for curve resolution, and is mostly *internal*. Resolution has a
#    better public answer already -- ``use_defaults(fn=64)`` sets it for a block without threading
#    anything through any call (SPEC R-4) -- so the group exists to carry the four values down the
#    plumbing as one, not to be typed at a call site.
#
# FileSummary: Frozen argument groups (Placement, Facets) for parameters that travel together.
# DocCategory: Foundational
# FileGroup: BOSL2

"""Frozen argument groups (Placement, Facets) for parameters that travel together."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from pybosl2._edges_lang import Anchor
from pybosl2.exceptions import Bosl2ValueError

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["Placement", "Facets", "resolve_placement"]

#: What an unset member looks like, so "not given" is distinguishable from "given the default".
_UNSET: Any = object()


@dataclass(frozen=True, slots=True)
class Placement:
    """Where a shape sits: its anchor, its spin about Z, and the direction it faces.

    The three always travel together (SPEC G-1), so they can be one value that is built once and
    reused. Frozen, like every group: :meth:`with_` returns a new one.

    Attributes:
        anchor: The point on the shape that lands at the origin.
        spin: Rotation about Z in degrees, applied after anchoring.
        orient: The direction the shape's top is rotated towards.

    Examples:
        .. pythonscad-example::

            from pybosl2 import Anchor, Placement, cuboid

            upright = Placement(anchor=Anchor.BOTTOM)
            cuboid([40, 30, 20], placement=upright).show()

    """

    anchor: "Anchor | Sequence[float]" = Anchor.CENTER
    spin: float = 0.0
    orient: "Anchor | Sequence[float]" = Anchor.TOP

    def with_(
        self,
        *,
        anchor: "Anchor | Sequence[float] | None" = None,
        spin: float | None = None,
        orient: "Anchor | Sequence[float] | None" = None,
    ) -> "Placement":
        """Return a copy with the given members replaced.

        Args:
            anchor: New anchor, or ``None`` to keep this one's.
            spin: New spin in degrees, or ``None`` to keep this one's.
            orient: New orientation, or ``None`` to keep this one's.

        Returns:
            A new :class:`Placement`; this one is unchanged.

        Examples:
            >>> from pybosl2 import Anchor, Placement
            >>> Placement(anchor=Anchor.BOTTOM).with_(spin=45).spin
            45.0

        """
        return replace(
            self,
            anchor=self.anchor if anchor is None else anchor,
            spin=self.spin if spin is None else float(spin),
            orient=self.orient if orient is None else orient,
        )

    def as_kwargs(self) -> dict[str, Any]:
        """Return the three members as keyword arguments.

        Returns:
            A mapping with ``anchor``, ``spin`` and ``orient``.

        """
        return {"anchor": self.anchor, "spin": self.spin, "orient": self.orient}


@dataclass(frozen=True, slots=True)
class Facets:
    """The curve-resolution controls, carried as one value.

    Mostly internal. SPEC R-1 requires every construction that approximates a curve to accept
    ``fn``/``fa``/``fs`` (or ``res``) *and pass them to everything it builds*, and the rule is
    broken most often by a function that simply forgets to forward one of the four. One value is
    harder to drop than four parameters.

    Callers wanting to set resolution should reach for :func:`~pybosl2.defaults.use_defaults`
    instead, which sets it for a whole block without threading anything through any call
    (SPEC R-4). ``None`` in any member means "not given, decide for me" (SPEC D-4).

    Attributes:
        fn: Fixed fragment count for a full circle.
        fa: Minimum fragment angle in degrees.
        fs: Minimum fragment size in millimetres.
        res: Sampling resolution for the SDF backend.

    Examples:
        >>> from pybosl2.groups import Facets
        >>> Facets(fn=64).as_kwargs()
        {'fn': 64}

    """

    fn: int | None = None
    fa: float | None = None
    fs: float | None = None
    res: int | None = None

    @classmethod
    def ambient(cls) -> "Facets":
        """Return the values :func:`~pybosl2.defaults.use_defaults` currently has in force.

        Returns:
            A :class:`Facets` holding the ambient values, each ``None`` where nothing is set.

        """
        from pybosl2.defaults import current_defaults

        active = current_defaults()
        return cls(fn=active.fn, fa=active.fa, fs=active.fs, res=active.res)

    @classmethod
    def resolved(
        cls,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
        res: int | None = None,
    ) -> "Facets":
        """Return the values to actually use: what the caller passed, over the ambient defaults.

        This is the one place the rule lives (SPEC R-5: an explicit value always wins over an
        ambient one). :func:`~pybosl2.defaults.resolve_facets` and
        :func:`~pybosl2.defaults.resolve_res` both go through it, so the CSG facet controls and
        the SDF resolution cannot drift into resolving differently -- they were two
        implementations of one rule before.

        ``fn=0`` passes through unchanged: it is the caller opting *out* of an ambient ``fn``, and
        :func:`~pybosl2._helpers.frag_count` reads any ``fn`` below 3 as "use fa/fs" (SPEC R-5).

        Args:
            fn: Caller-supplied fragment count, or ``None``.
            fa: Caller-supplied fragment angle, or ``None``.
            fs: Caller-supplied fragment size, or ``None``.
            res: Caller-supplied SDF resolution, or ``None``.

        Returns:
            A :class:`Facets` with each member filled from the ambient default where the caller
            gave nothing, and still ``None`` where nothing is set anywhere.

        Examples:
            >>> from pybosl2 import use_defaults
            >>> from pybosl2.groups import Facets
            >>> with use_defaults(fn=64):
            ...     Facets.resolved(fa=6).as_kwargs()
            {'fn': 64, 'fa': 6}

        """
        return cls.ambient().merge(cls(fn=fn, fa=fa, fs=fs, res=res))

    def merge(self, other: "Facets") -> "Facets":
        """Return these values with *other*'s non-``None`` members taking precedence.

        An explicitly passed value always beats an ambient one (SPEC R-5), so the caller's
        `Facets` is the one passed as *other*.

        Args:
            other: The values that win where they are set.

        Returns:
            A new :class:`Facets`.

        """
        return Facets(
            fn=self.fn if other.fn is None else other.fn,
            fa=self.fa if other.fa is None else other.fa,
            fs=self.fs if other.fs is None else other.fs,
            res=self.res if other.res is None else other.res,
        )

    def as_kwargs(self) -> dict[str, Any]:
        """Return just the members that are set, as keyword arguments.

        Returns:
            A mapping of the non-``None`` members, so it can be splatted into a callee that
            declares only some of them.

        """
        return {
            name: value
            for name, value in (("fn", self.fn), ("fa", self.fa), ("fs", self.fs), ("res", self.res))
            if value is not None
        }


def resolve_placement(
    placement: "Placement | None",
    anchor: "Anchor | Sequence[float] | None",
    spin: float | None,
    orient: "Anchor | Sequence[float] | None",
    function: str,
    *,
    defaults: "Placement | None" = None,
) -> tuple["Anchor | Sequence[float] | None", float | None, "Anchor | Sequence[float] | None"]:
    """Resolve a placement group against the loose members, refusing a call that gives both.

    SPEC G-3: the loose spellings survive, and supplying a group *and* one of its members is an
    error rather than a silent preference -- the same rule a radius and its own diameter follow
    (SPEC D-5), for the same reason: the call cannot mean two things at once.

    Args:
        placement: The group, or ``None``.
        anchor: The loose ``anchor`` as passed.
        spin: The loose ``spin`` as passed.
        orient: The loose ``orient`` as passed.
        function: Name of the calling function, for the error message.
        defaults: What the loose members default to, so "given" can be told from "left alone".
            Defaults to :class:`Placement`'s own defaults.

    Returns:
        The three values to use.

    Raises:
        Bosl2ValueError: if *placement* is given together with any of the loose members.

    """
    if placement is None:
        return anchor, spin, orient
    baseline = Placement() if defaults is None else defaults
    given = [
        name
        for name, value, default in (
            ("anchor", anchor, baseline.anchor),
            ("spin", spin, baseline.spin),
            ("orient", orient, baseline.orient),
        )
        if value is not None and value is not default and value != default
    ]
    if given:
        raise Bosl2ValueError(
            f"{function}(): given both placement= and {', '.join(given)}=. "
            f"A placement carries anchor, spin and orient together, so passing one of them "
            f"beside it cannot mean two things -- pass placement=Placement({given[0]}=...), "
            f"or drop placement= and pass the loose arguments."
        )
    return placement.anchor, placement.spin, placement.orient

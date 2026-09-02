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

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, TypeVar, cast

from pybosl2._edges_lang import Anchor
from pybosl2.enums import EdgeTreatmentKind
from pybosl2.exceptions import Bosl2ValueError

__all__ = [
    "Placement",
    "Facets",
    "EdgeTreatment",
    "resolve_placement",
    "resolve_placement_2d",
    "resolve_edge_treatment",
]

#: What an unset member looks like, so "not given" is distinguishable from "given the default".
_UNSET: Any = object()


@dataclass(frozen=True, slots=True)
class Placement:
    """Where a shape sits: its anchor, its spin about Z, and the direction it faces.

    The three always travel together (SPEC G-1), so they can be one value that is built once and
    reused. Frozen, like every group: :meth:`with_` returns a new one.

    **A placement reads in two dimensions as well as three.** In the plane a shape has an anchor
    and a spin but nothing to orient -- there is no third axis to turn a face towards -- so a 2-D
    constructor honours those two. One placement can therefore serve a 2-D outline and the solid
    extruded from it, which is the case worth having. What it must not do is *quietly* honour two
    of the three: a placement carrying a real ``orient`` asks for something the plane cannot do, so
    passing one to a 2-D constructor raises rather than silently dropping it (SPEC E-5). The
    default ``orient`` is not "a real one" -- ``Placement()`` and ``Placement(anchor=...)`` are
    dimension-neutral and pass anywhere.

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

    def orients(self) -> bool:
        """Whether this placement asks for an orientation the plane cannot give.

        Returns:
            ``True`` when ``orient`` differs from the default, which is what makes a placement
            three-dimensional. A placement that only anchors and spins reads in either dimension.

        Examples:
            >>> from pybosl2 import Anchor, Placement
            >>> Placement(anchor=Anchor.BOTTOM).orients()
            False
            >>> Placement(orient=Anchor.RIGHT).orients()
            True

        """
        default = Placement.__dataclass_fields__["orient"].default
        return bool(self.orient is not default and self.orient != default)

    def as_kwargs(self) -> dict[str, Any]:
        """Return the three members as keyword arguments.

        Returns:
            A mapping with ``anchor``, ``spin`` and ``orient``.

        """
        return {"anchor": self.anchor, "spin": self.spin, "orient": self.orient}

    def as_plane_kwargs(self) -> dict[str, Any]:
        """Return the members a 2-D constructor can honour.

        Returns:
            A mapping with ``anchor`` and ``spin``. ``orient`` is absent because the plane has no
            third axis to turn a face towards; :meth:`orients` says whether dropping it would lose
            anything, and :func:`resolve_placement_2d` refuses rather than drop it.

        """
        return {"anchor": self.anchor, "spin": self.spin}


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


#: An edge size as the constructors spell it: one value, or one per corner. Two variables, not
#: one, because a constructor may spell its two differently -- `rect_tube` takes a per-corner
#: `rounding` and a scalar `chamfer` -- and a single variable could not bind to both.
_RoundingT = TypeVar("_RoundingT", bound="float | Sequence[float] | None")
_ChamferT = TypeVar("_ChamferT", bound="float | Sequence[float] | None")

#: The two placement members a 2-D constructor honours, typed so the resolver hands back exactly
#: what it was given: `flat.py` declares them non-optional (`anchor: Anchor | Sequence[float]`)
#: while `solid.py` declares them `| None`, and a resolver that widened would make every 2-D call
#: site fail the checker for a value it can never actually receive.
_AnchorT = TypeVar("_AnchorT", bound="Anchor | Sequence[float] | None")
_SpinT = TypeVar("_SpinT", bound="float | None")


def resolve_placement_2d(
    placement: "Placement | None",
    anchor: _AnchorT,
    spin: _SpinT,
    function: str,
    *,
    defaults: "Placement | None" = None,
) -> "tuple[_AnchorT | Anchor | Sequence[float], _SpinT | float]":
    """Resolve a placement for a 2-D constructor, which has an anchor and a spin but no orient.

    A separate function rather than a flag on :func:`resolve_placement`, because a boolean that
    selects how many values come back is a second function wearing the first one's name
    (SPEC S-19b).

    Args:
        placement: The group, or ``None``.
        anchor: The loose ``anchor`` as passed.
        spin: The loose ``spin`` as passed.
        function: Name of the calling function, for the error message.
        defaults: What the loose members default to, so "given" can be told from "left alone".

    Returns:
        The anchor and spin to use.

    Raises:
        Bosl2ValueError: if *placement* is given together with either loose member (SPEC G-3), or
            if it carries a real ``orient``, which the plane cannot honour (SPEC E-5).

    """
    if placement is None:
        return anchor, spin
    if placement.orients():
        raise Bosl2ValueError(
            f"{function}(): the placement sets orient={placement.orient!r}, which a 2-D shape "
            f"cannot honour -- there is no third axis to turn a face towards. Drop the orient "
            f"(`placement.with_(orient=Anchor.TOP)`), or apply it to the solid after extruding."
        )
    baseline = Placement() if defaults is None else defaults
    given = [
        name
        for name, value, default in (
            ("anchor", anchor, baseline.anchor),
            ("spin", spin, baseline.spin),
        )
        if value is not None and value is not default and value != default
    ]
    if given:
        raise Bosl2ValueError(
            f"{function}(): given both placement= and {', '.join(given)}=. A placement carries "
            f"anchor and spin together, so passing one of them beside it cannot mean two things "
            f"-- pass placement=Placement({given[0]}=...), or drop placement= and pass the loose "
            f"arguments."
        )
    return placement.anchor, placement.spin


@dataclass(frozen=True, slots=True)
class EdgeTreatment:
    """What happens to an edge: a rounding of some radius, a chamfer of some size, or nothing.

    Rounding and chamfer are **mutually exclusive on one edge** -- an edge is rounded or chamfered,
    never both -- and the library checked that in six places with six different wordings, none of
    which said what to do instead. As one value the conflict is not checkable, it is
    *unrepresentable*: there is one size and one kind, so there is nothing to disagree.

    Build one with :meth:`rounding` or :meth:`chamfer` rather than the constructor, so the kind and
    the size are set together.

    Attributes:
        kind: Which treatment, or :attr:`~pybosl2.enums.EdgeTreatmentKind.NONE`.
        size: The radius (rounding) or inset (chamfer). Negative rounds outward, as BOSL2's does.
            A sequence gives a size per corner, which the 2-D constructors accept.

    Examples:
        .. pythonscad-example::

            from pybosl2 import EdgeTreatment, cuboid

            cuboid([40, 30, 20], treatment=EdgeTreatment.rounding(4)).show()

    """

    kind: EdgeTreatmentKind = EdgeTreatmentKind.NONE
    size: "float | Sequence[float]" = 0.0

    @classmethod
    def rounding(cls, size: "float | Sequence[float]") -> "EdgeTreatment":
        """Return a rounding treatment of radius *size*.

        Args:
            size: The rounding radius, or one radius per corner.

        Returns:
            An :class:`EdgeTreatment`.

        Examples:
            >>> from pybosl2 import EdgeTreatment
            >>> EdgeTreatment.rounding(4).as_kwargs()
            {'rounding': 4.0}

        """
        return cls(kind=EdgeTreatmentKind.ROUNDING, size=size if isinstance(size, Sequence) else float(size))

    @classmethod
    def chamfer(cls, size: "float | Sequence[float]") -> "EdgeTreatment":
        """Return a chamfer treatment of inset *size*.

        Args:
            size: The chamfer size, inset from the sides, or one per corner.

        Returns:
            An :class:`EdgeTreatment`.

        Examples:
            >>> from pybosl2 import EdgeTreatment
            >>> EdgeTreatment.chamfer(2).as_kwargs()
            {'chamfer': 2.0}

        """
        return cls(kind=EdgeTreatmentKind.CHAMFER, size=size if isinstance(size, Sequence) else float(size))

    @classmethod
    def none(cls) -> "EdgeTreatment":
        """Return the treatment that leaves edges sharp.

        Returns:
            An :class:`EdgeTreatment` that contributes no arguments.

        """
        return cls()

    def as_kwargs(self) -> dict[str, Any]:
        """Return the treatment as the keyword argument a constructor declares.

        Returns:
            ``{"rounding": size}``, ``{"chamfer": size}``, or ``{}`` for no treatment -- so it can
            be splatted into a constructor that names the two separately.

        """
        if self.kind is EdgeTreatmentKind.ROUNDING:
            return {"rounding": self.size}
        if self.kind is EdgeTreatmentKind.CHAMFER:
            return {"chamfer": self.size}
        return {}


def refuse_rounding_and_chamfer(
    rounding: "float | Sequence[float] | None",
    chamfer: "float | Sequence[float] | None",
    function: str,
) -> None:
    """Refuse a call that asks for a rounding and a chamfer on the same edge.

    One rule, one place (SPEC G-5). It was written six times with six wordings -- "Cannot set both
    rounding and chamfer at the same time.", "Cannot specify nonzero value for both chamfer and
    rounding", and four more -- and not one of them said what to do instead, which is what E-4 asks
    of a refusal.

    Args:
        rounding: The rounding as passed, or ``None``.
        chamfer: The chamfer as passed, or ``None``.
        function: Name of the calling function, for the message.

    Raises:
        Bosl2ValueError: if both are given and neither is zero.

    """
    if rounding and chamfer:
        raise Bosl2ValueError(
            f"{function}(): given rounding={rounding} and chamfer={chamfer}. An edge is rounded "
            f"or chamfered, never both -- pass one of them, or "
            f"treatment=EdgeTreatment.rounding({rounding}) / EdgeTreatment.chamfer({chamfer}) to "
            f"say which."
        )


def resolve_edge_treatment(
    treatment: "EdgeTreatment | None",
    rounding: _RoundingT,
    chamfer: _ChamferT,
    function: str,
    *,
    per_corner: bool = True,
) -> tuple[_RoundingT, _ChamferT]:
    """Resolve an edge-treatment group against the loose ``rounding``/``chamfer``.

    Args:
        treatment: The group, or ``None``.
        rounding: The loose ``rounding`` as passed.
        chamfer: The loose ``chamfer`` as passed.
        function: Name of the calling function, for the error message.
        per_corner: Whether this constructor takes a size per corner. A 3-D primitive takes one
            size for the whole solid, so a per-corner group handed to it is refused here rather
            than left to fail as a ``TypeError`` from inside the backend (SPEC E-1, E-4).

    Returns:
        The ``rounding`` and ``chamfer`` to use, at most one of them set. Where a group decides
        the answer, the other comes back as ``0`` -- "off" -- rather than ``None``, because ``None``
        means "decide for me" and the group has just decided (SPEC D-4).

    Raises:
        Bosl2ValueError: if the group is given beside either loose member (SPEC G-3), if both
            loose members are given (the rule above), or if a per-corner group is given to a
            constructor that takes one size.

    """
    if treatment is None:
        refuse_rounding_and_chamfer(rounding, chamfer, function)
        return rounding, chamfer
    given = [name for name, value in (("rounding", rounding), ("chamfer", chamfer)) if value]
    if given:
        raise Bosl2ValueError(
            f"{function}(): given both treatment= and {', '.join(given)}=. An EdgeTreatment "
            f"already says which treatment and what size, so passing one beside it cannot mean "
            f"two things -- drop treatment=, or drop the loose argument."
        )
    if not per_corner and isinstance(treatment.size, Sequence):
        raise Bosl2ValueError(
            f"{function}(): the treatment gives a size per corner ({list(treatment.size)}), but "
            f"{function}() applies one size to the whole shape. Pass a single number -- "
            f"EdgeTreatment.{treatment.kind.value}({treatment.size[0]}) -- or use a 2-D "
            f"constructor, which does take one size per corner."
        )
    resolved = treatment.as_kwargs()
    # The group's size is whatever `EdgeTreatment.rounding()` was handed, and the caller built it
    # for the constructor it is passing it to, so it matches that constructor's own spelling of
    # the parameter. The one case the checker cannot see is a *per-corner* group given to a
    # constructor that takes a scalar; that reaches the backend and is refused there, where the
    # loose spelling would have been refused statically -- so `per_corner=False` catches it above.
    return (
        cast("_RoundingT", resolved.get("rounding", 0)),
        cast("_ChamferT", resolved.get("chamfer", 0)),
    )

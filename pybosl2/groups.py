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
    "EdgeSelection",
    "Texturing",
    "resolve_center_anchor",
    "resolve_placement",
    "resolve_placement_2d",
    "resolve_edge_treatment",
    "resolve_edge_selection",
    "resolve_texturing",
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

    Examples:
        .. pythonscad-example::

            from pybosl2 import Anchor, Placement, cuboid

            upright = Placement(anchor=Anchor.BOTTOM)
            cuboid([40, 30, 20], placement=upright).show()

    """

    #: The point on the shape that lands at the origin.
    anchor: "Anchor | Sequence[float]" = Anchor.CENTER
    #: Rotation about Z in degrees, applied after anchoring.
    spin: float = 0.0
    #: The direction the shape's top is rotated towards.
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

    Examples:
        >>> from pybosl2.groups import Facets
        >>> Facets(fn=64).as_kwargs()
        {'fn': 64}

    """

    #: Fixed fragment count for a full circle.
    fn: int | None = None
    #: Minimum fragment angle in degrees.
    fa: float | None = None
    #: Minimum fragment size in millimetres.
    fs: float | None = None
    #: Sampling resolution for the SDF backend.
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
            fn: Caller-supplied fragment count, or ``None``. Omitted, the ambient ``use_defaults(fn=...)`` value
                applies; ``fn=0`` opts back out to fa/fs.
            fa: Caller-supplied fragment angle, or ``None``. Omitted, the ambient ``use_defaults(fa=...)`` value
                applies.
            fs: Caller-supplied fragment size, or ``None``. Omitted, the ambient ``use_defaults(fs=...)`` value
                applies.
            res: Caller-supplied SDF resolution, or ``None``. Omitted, the ambient ``use_defaults(res=...)`` value
                applies.

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


#: Every anchor `resolve_center_anchor` sees, as one variable rather than three, so the resolver
#: hands back exactly the vocabulary it was given: the CSG backend passes `Anchor` members and the
#: SDF backend passes raw `Vec3` direction vectors, and a return type widened to the union of both
#: would make every SDF call site fail the checker for an `Anchor` it can never receive.
_CenterAnchorT = TypeVar("_CenterAnchorT", bound="Anchor | Sequence[float] | None")


def resolve_center_anchor(
    *,
    center: bool | None,
    anchor: _CenterAnchorT,
    centred: _CenterAnchorT,
    uncentred: _CenterAnchorT,
) -> _CenterAnchorT:
    """Fold BOSL2's ``center=`` shorthand into the anchor language (SPEC G-1, B2-3).

    ``center=`` is a placement option wearing a boolean: True means "sit on the origin", False
    means "sit on the shape's own base". BOSL2 gives it precedence over ``anchor=`` --
    ``anchor = center==true ? CENTER : center==false ? uncentred : anchor`` -- and this is the one
    place that rule is written.

    It was written in **eleven** places before T40, in three spellings and *two contradicting
    precedences*. Seven gave ``center`` precedence, which is right. The other four spelled it
    inline as ``use_anchor = anchor; if use_anchor is None: use_anchor = CENTER if center is None
    or center else BOTTOM``, which lets ``anchor`` win — while their own docstrings said "center:
    if given, overrides anchor". ``cyl(height=10, radius=5, anchor=TOP, center=False)`` sat on its
    top face, and the documentation next to it said it would sit on the bottom one. That is E-5's
    silent wrong answer, and it survived because the rule had no single home to be right in.

    Both are named at the call site rather than defaulted, because each backend anchors in its own
    vocabulary: the CSG backend passes :class:`~pybosl2.enums.Anchor` members and the SDF backend
    passes the raw direction vectors of `pybosl2/sdf/_constants.py`. One type variable spans all
    three anchors so the resolver hands back exactly what it was given.

    Args:
        center: True for a centred anchor, False for *uncentred*, ``None`` to leave *anchor* be.
        anchor: The anchor as passed, used only when *center* is ``None``.
        centred: What ``center=True`` means for this shape.
        uncentred: What ``center=False`` means -- ``BOTTOM`` for the cylinders,
            ``BOTTOM_FRONT_LEFT`` for the boxes.

    Returns:
        The anchor to place with. ``None`` propagates, so a constructor whose own default depends
        on more than this (SPEC D-4) still gets to compute it.

    """
    if center is not None:
        return centred if center else uncentred
    return anchor


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

    Examples:
        .. pythonscad-example::

            from pybosl2 import EdgeTreatment, cuboid

            cuboid([40, 30, 20], treatment=EdgeTreatment.rounding(4)).show()

    """

    #: Which treatment, or :attr:`~pybosl2.enums.EdgeTreatmentKind.NONE`.
    kind: EdgeTreatmentKind = EdgeTreatmentKind.NONE
    #: The radius (rounding) or inset (chamfer). Negative rounds outward, as BOSL2's does.
    #: A sequence gives a size per corner, which the 2-D constructors accept.
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


@dataclass(frozen=True, slots=True)
class EdgeSelection:
    """Which edges a treatment applies to, and which are spared.

    The pair travels together on 15 callables and neither member means much alone: `edges` without
    `except_edges` is the common case, and `except_edges` without `edges` reads as "all of them
    but these", which is what the default makes it. Unlike :class:`EdgeTreatment` the two are not
    exclusive -- they compose, the second narrowing the first.

    Both are expressed in the anchor language (SPEC C-10, O-6b), never as strings.

    Examples:
        .. pythonscad-example::

            from pybosl2 import Anchor, EdgeSelection, EdgeTreatment, cuboid

            top_only = EdgeSelection(edges=Anchor.TOP)
            cuboid([40, 30, 20], treatment=EdgeTreatment.rounding(4), selection=top_only).show()

    """

    #: The edges to treat. Defaults to every edge.
    edges: Any = Anchor.ALL
    #: The edges to spare, spelled ``except_edges`` at a call site because ``except`` is
    #: a Python keyword (SPEC B2-3).
    excepted: Any = None

    def as_kwargs(self) -> dict[str, Any]:
        """Return the pair as the keyword arguments a constructor declares.

        Returns:
            A mapping with ``edges`` and, when one is set, ``except_edges``.

        """
        out: dict[str, Any] = {"edges": self.edges}
        if self.excepted is not None:
            out["except_edges"] = self.excepted
        return out


def resolve_edge_selection(
    selection: "EdgeSelection | None",
    edges: Any,
    except_edges: Any,
    function: str,
) -> tuple[Any, Any]:
    """Resolve an edge-selection group against the loose ``edges``/``except_edges``.

    Args:
        selection: The group, or ``None``.
        edges: The loose ``edges`` as passed.
        except_edges: The loose ``except_edges`` as passed.
        function: Name of the calling function, for the error message.

    Returns:
        The ``edges`` and ``except_edges`` to use.

    Raises:
        Bosl2ValueError: if the group is given beside either loose member (SPEC G-3).

    """
    if selection is None:
        return edges, except_edges
    given = [
        name
        for name, value, default in (("edges", edges, Anchor.ALL), ("except_edges", except_edges, None))
        if value is not None and value is not default and value != default
    ]
    if given:
        raise Bosl2ValueError(
            f"{function}(): given both selection= and {', '.join(given)}=. An EdgeSelection "
            f"already says which edges and which are spared, so passing one beside it cannot mean "
            f"two things -- drop selection=, or drop the loose argument."
        )
    resolved = selection.as_kwargs()
    return resolved["edges"], resolved.get("except_edges")


@dataclass(frozen=True, slots=True)
class Texturing:
    """A surface texture and how it is applied: the five parameters that always travel together.

    They travel together on all 11 callables that take more than one of them, which is the
    cleanest group in the library by that measure. It could not be built until there was something
    to group -- every one of those parameters refused until T37 built the application half of the
    texture subsystem (SPEC S-34, S-35).

    *size* and *reps* are alternatives, and the group holds at most one, so the pair cannot
    disagree (SPEC G-7): give the tile's size in millimetres, or how many times it repeats.

    Examples:
        .. pythonscad-example::

            from pybosl2 import Texturing, cyl

            cyl(height=30, radius=12, texturing=Texturing("ribs", reps=[16, 1], depth=1.5)).show()

    """

    #: The texture, by name or already built.
    texture: Any = None
    #: Size of one tile as ``[around, along]`` in millimetres.
    size: "float | Sequence[float] | None" = None
    #: Repeat counts as ``[around, along]``, instead of *size*.
    reps: "int | Sequence[int] | None" = None
    #: How far the texture displaces the surface. Negative sinks it in.
    depth: float = 1.0
    #: How far the surface is sunk before the texture is added. ``True`` means one depth.
    inset: float | bool = False

    def __post_init__(self) -> None:
        """Refuse a tile that is both sized and counted (SPEC G-7).

        Raises:
            Bosl2ValueError: if *size* and *reps* are both given.

        """
        if self.size is not None and self.reps is not None:
            raise Bosl2ValueError(
                f"Texturing(): given size={self.size!r} and reps={self.reps!r}. A tile is sized "
                f"or counted, not both -- size says how big one tile is in millimetres, reps says "
                f"how many of them there are."
            )

    def as_kwargs(self) -> dict[str, Any]:
        """Return the group as the keyword arguments a constructor declares.

        Returns:
            A mapping with ``texture``, ``tex_depth`` and ``tex_inset``, plus whichever of
            ``tex_size``/``tex_reps`` is set.

        """
        out: dict[str, Any] = {
            "texture": self.texture,
            "tex_depth": self.depth,
            "tex_inset": self.inset,
        }
        if self.size is not None:
            out["tex_size"] = self.size
        if self.reps is not None:
            out["tex_reps"] = self.reps
        return out


def resolve_texturing(
    texturing: "Texturing | None",
    texture: Any,
    tex_size: "float | Sequence[float] | None",
    tex_reps: "int | Sequence[int] | None",
    tex_depth: float | None,
    tex_inset: float | bool | None,
    function: str,
) -> "tuple[Any, float | Sequence[float] | None, int | Sequence[int] | None, float | None, float | bool | None]":
    """Resolve a texturing group against the loose ``tex_*`` arguments.

    Args:
        texturing: The group, or ``None``.
        texture: The loose ``texture`` as passed.
        tex_size: The loose ``tex_size`` as passed.
        tex_reps: The loose ``tex_reps`` as passed.
        tex_depth: The loose ``tex_depth`` as passed.
        tex_inset: The loose ``tex_inset`` as passed.
        function: Name of the calling function, for the error message.

    Returns:
        The ``(texture, tex_size, tex_reps, tex_depth, tex_inset)`` to use.

    Raises:
        Bosl2ValueError: if the group is given beside any loose member (SPEC G-3).

    """
    if texturing is None:
        return texture, tex_size, tex_reps, tex_depth, tex_inset
    given = [
        name
        for name, value, default in (
            ("texture", texture, None),
            ("tex_size", tex_size, None),
            ("tex_reps", tex_reps, None),
            ("tex_depth", tex_depth, 1.0),
            ("tex_inset", tex_inset, False),
        )
        if value is not None and value != default
    ]
    if given:
        raise Bosl2ValueError(
            f"{function}(): given both texturing= and {', '.join(given)}=. A Texturing already "
            f"says which texture and how it is applied, so passing one beside it cannot mean two "
            f"things -- drop texturing=, or drop the loose argument."
        )
    return texturing.texture, texturing.size, texturing.reps, texturing.depth, texturing.inset

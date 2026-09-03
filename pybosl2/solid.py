# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# DocCategory: Foundational
# LibFile: pybosl2/solid.py
# FileSummary: Statically typed shape constructors and backend-neutral solid facade.
# FileGroup: BOSL2

"""Statically typed shape constructors and backend-neutral solid facade."""

# The backend-neutral solid facade: unified shape constructors that build on whichever backend is
# active (``"csg"`` by default, ``"sdf"`` under ``use_backend("sdf")``). Each returns a common
# :class:`~pybosl2._backend.Solid` -- a CsgSolid on the CSG backend, an SdfSolid on the SDF backend --
# so the same code realizes exact CSG or an F-Rep/signed-distance field depending on context:
#
#     from pybosl2.solid import sphere, use_backend
#     a = sphere(radius=10)                 # CSG (default) -> CsgSolid
#     with use_backend("sdf"):
#         b = sphere(radius=10)             # libfive SDF   -> SdfSolid
#
# The shape constructors below are the 3-D primitives BOTH backends expose; each dispatches by name
# through the active backend's ``construct``. n-ary CSG (union/difference/intersection) dispatches to
# the backend's own operators. The backend-specific modules (pybosl2.shapes3d, pybosl2.sdf) remain
# directly importable for anything not yet unified here.

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from pybosl2._backend import (
    Solid,
    current_backend,
    get_backend,
    set_default_backend,
    use_backend,
)
from pybosl2._edges_lang import Anchor
from pybosl2.exceptions import Bosl2ValueError, CrossBackendError, UnsupportedByBackendError
from pybosl2.groups import (
    EdgeSelection,
    EdgeTreatment,
    Placement,
    Texturing,
    resolve_edge_selection,
    resolve_edge_treatment,
    resolve_placement,
    resolve_texturing,
)

#: Resolution knobs whose default is ambient rather than per-shape (see pybosl2.defaults).
_AMBIENT = frozenset({"fn", "fa", "fs", "res"})

#: What an omitted argument resolves to, as reported by :func:`effective_defaults`: a scalar, a
#: size/shift tuple, an anchor, or ``None`` -- which means "decide for me" rather than "no value"
#: (PLAN T-9b). Every façade and backend default across the shape surface is one of these.
DefaultValue: "TypeAlias" = "bool | int | float | str | tuple[float, ...] | Anchor | Point | None"

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import TypeAlias

    from pybosl2._edges_lang import EdgeAtom
    from pybosl2.points import Point  # noqa: F401  # used by the DefaultValue alias (a string, so ruff cannot see it)

_SHARED_3D = (
    "cube",
    "cuboid",
    "cyl",
    "cylinder",
    "octahedron",
    "onion",
    "pie_slice",
    "prismoid",
    "rect_tube",
    "regular_prism",
    "sphere",
    "spheroid",
    "teardrop",
    "torus",
    "tube",
    "wedge",
    "xcyl",
    "ycyl",
    "zcyl",
)

__all__ = [
    "DefaultValue",
    "effective_defaults",
    "cube",
    "cuboid",
    "cyl",
    "cylinder",
    "octahedron",
    "onion",
    "pie_slice",
    "prismoid",
    "rect_tube",
    "regular_prism",
    "sphere",
    "spheroid",
    "teardrop",
    "torus",
    "tube",
    "wedge",
    "xcyl",
    "ycyl",
    "zcyl",
    "polyhedron",
    "union",
    "difference",
    "intersection",
    # backend controls, re-exported for convenience
    "use_backend",
    "set_default_backend",
    "current_backend",
    "Solid",
    "CrossBackendError",
    "UnsupportedByBackendError",
]


def _forward(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return what the façade sends to the backend: everything it has a value for.

    The façade owns the default for every argument both backends understand and forwards it
    whether or not the caller passed one (SPEC B-3, PLAN F-P1); the backend then takes the subset
    its own constructor declares (F-P2).

    ``None`` is not one of those values. SPEC D-4 defines it as "not supplied, decide for me", so
    an argument sitting at ``None`` is the façade declining to decide -- and forwarding the
    decline would *override* the backend's own answer with nothing. That is not a filter on top of
    F-P2; it is what D-4 means, and the two cases it covers are both real:

    * **A default the backend computes.** ``cylinder()``'s anchor depends on ``center``, so no
      constant the façade could write would be right.
    * **An ambient control with nothing set.** ``fn``/``fa``/``fs``/``res`` mean "inherit"
      (SPEC R-2), and with nothing set anywhere there is nothing to inherit, so the backend's own
      facet default is the answer (R-7).

    What this is *not* any more is the thing that decides shared arguments. It used to be: every
    façade default was ``None``, so the backend's default won every time and the two backends
    could resolve the same call differently. 67 of those are real values in the façade signature
    now (`tests/test_defaults.py::test_the_facade_owns_every_shared_default`), so they are always
    forwarded and both backends get the same answer.
    """
    return {name: value for name, value in arguments.items() if value is not None}


def _groups(
    function: str,
    arguments: dict[str, Any],
    *,
    placement: Placement | None = None,
    treatment: EdgeTreatment | None = None,
    selection: EdgeSelection | None = None,
    texturing: Texturing | None = None,
    per_corner: bool = True,
) -> dict[str, Any]:
    """Resolve every argument group *in place* in the arguments a constructor is about to forward.

    One call rather than one per group, and it works on the forwarding dict itself rather than
    beside it -- the loose members are already listed there, so resolving them in place costs a
    constructor nothing but the wrapper. Three separate calls plus their unpacking was thirteen
    lines in every constructor, which is the transcription B-3 is about.

    The groups are independent: a placement says nothing about a texture. They are resolved
    together only because they are forwarded together.

    Args:
        function: Name of the calling constructor, for the error messages.
        arguments: What the constructor is about to forward, in its own spelling.
        placement: The placement group, or ``None``.
        treatment: The edge-treatment group, or ``None``.
        selection: The edge-selection group, or ``None``.
        texturing: The texturing group, or ``None``.
        per_corner: Whether this constructor takes an edge size per corner.

    Returns:
        *arguments*, with each group's members replaced by what the group resolves to.

    """
    if {"anchor", "spin", "orient"} & set(arguments):
        arguments["anchor"], arguments["spin"], arguments["orient"] = resolve_placement(
            placement, arguments.get("anchor"), arguments.get("spin"), arguments.get("orient"), function
        )
    if {"rounding", "chamfer"} & set(arguments):
        arguments["rounding"], arguments["chamfer"] = resolve_edge_treatment(
            treatment, arguments.get("rounding"), arguments.get("chamfer"), function, per_corner=per_corner
        )
    if {"edges", "except_edges"} & set(arguments):
        arguments["edges"], arguments["except_edges"] = resolve_edge_selection(
            selection, arguments.get("edges"), arguments.get("except_edges"), function
        )
    if "texture" in arguments:
        (
            arguments["texture"],
            arguments["tex_size"],
            arguments["tex_reps"],
            arguments["tex_depth"],
            arguments["tex_inset"],
        ) = resolve_texturing(
            texturing,
            arguments.get("texture"),
            arguments.get("tex_size"),
            arguments.get("tex_reps"),
            arguments.get("tex_depth"),
            arguments.get("tex_inset"),
            function,
        )
    return arguments


def cube(
    size: float | Sequence[float] | None = 1,
    *,
    chamfer: float | None = 0,
    treatment: EdgeTreatment | None = None,
    rounding: float | None = 0,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    edges: EdgeAtom | list[EdgeAtom] | None = Anchor.ALL,
    except_edges: list[EdgeAtom] | None = None,
    selection: EdgeSelection | None = None,
    teardrop: bool | None = False,
    trimcorners: bool | None = True,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a cube on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        size: Size of the cube, a number or length-3 vector.
        chamfer: Chamfer size along all edges (default none)
        treatment: A rounding or a chamfer as one value (SPEC G-1). An edge is rounded or chamfered,
            never both, so this makes the pair unrepresentable rather than checked; giving it beside
            rounding= or chamfer= raises (SPEC G-3).
        rounding: Rounding radius along all edges (default none)
        anchor: Anchor point (default Anchor.CENTER)
        center: If given, overrides anchor (True -> CENTER, False -> FRONT+LEFT+BOTTOM)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default Anchor.TOP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        edges: edge specifier — "ALL", "NONE", "X", "Y", "Z", or list of direction vectors (CSG backend).
        except_edges: edges to exclude from chamfer/rounding (CSG backend).
        selection: Which edges to treat and which to spare, as one value (SPEC G-1). Giving it beside
            edges= or except_edges= raises (SPEC G-3).
        teardrop: limit the overhang angle for FDM printing (default False) (CSG backend).
        trimcorners: trim corners where 3+ edges meet (default True) (CSG backend).
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend). Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back out
            to fa/fs.
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fa=...)`` value applies.
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fs=...)`` value applies.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        Basic cube:

        .. pythonscad-example::

            from pybosl2 import cube

            cube(size=20).show()

        Cube with chamfered edges:

        .. pythonscad-example::

            from pybosl2 import cube

            cube(size=20, chamfer=2).show()

        Cube with rounded edges:

        .. pythonscad-example::

            from pybosl2 import cube

            cube(size=20, rounding=3).show()

    """
    return get_backend().construct(
        "cube",
        _forward(
            _groups(
                "cube",
                {
                    "size": size,
                    "center": center,
                    "teardrop": teardrop,
                    "trimcorners": trimcorners,
                    "fn": fn,
                    "fa": fa,
                    "fs": fs,
                    "res": res,
                    "rounding": rounding,
                    "anchor": anchor,
                    "spin": spin,
                    "except_edges": except_edges,
                    "orient": orient,
                    "edges": edges,
                    "chamfer": chamfer,
                },
                placement=placement,
                treatment=treatment,
                selection=selection,
                per_corner=False,
            )
        ),
    )


def cuboid(
    size: float | Sequence[float] | None = (1, 1, 1),
    *,
    chamfer: float | None = 0,
    treatment: EdgeTreatment | None = None,
    rounding: float | None = 0,
    edges: EdgeAtom | list[EdgeAtom] | None = Anchor.ALL,
    except_edges: list[EdgeAtom] | None = None,
    selection: EdgeSelection | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    p1: Sequence[float] | None = None,
    p2: Sequence[float] | None = None,
    teardrop: bool | None = False,
    trimcorners: bool | None = True,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a cuboid on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        size: Size of the cuboid, a number or length-3 vector.
        chamfer: Chamfer size, inset from sides (default: no chamfer)
        treatment: A rounding or a chamfer as one value (SPEC G-1). An edge is rounded or chamfered,
            never both, so this makes the pair unrepresentable rather than checked; giving it beside
            rounding= or chamfer= raises (SPEC G-3).
        rounding: Edge rounding radius (default: no rounding)
        edges: Edges to mask (default ``"ALL"``)
        except_edges: Edges to explicitly not mask (BOSL2's `except=` synonym; `except` is a Python keyword)
        selection: Which edges to treat and which to spare, as one value (SPEC G-1). Giving it beside
            edges= or except_edges= raises (SPEC G-3).
        anchor: Anchor point (default Anchor.CENTER)
        spin: Z-axis rotation in degrees (default 0)
        orient: Direction to rotate the top towards (default Anchor.TOP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        p1: align the cuboid's corner at p1, if given (forces anchor=BOTTOM_FRONT_LEFT) (CSG backend).
        p2: if given with p1, defines the cuboid's opposing cornerpoint (CSG backend).
        teardrop: enable teardrop rounding (not supported by this pure-Python port) (CSG backend).
        trimcorners: round/chamfer corners where three treated edges meet (default True) (CSG backend).
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend). Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back out
            to fa/fs.
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fa=...)`` value applies.
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fs=...)`` value applies.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import cuboid

            shape = cuboid([40, 30, 20])
            shape.show()

        .. pythonscad-example::

            from pybosl2 import cuboid

            shape = cuboid([40, 30, 20], rounding=5)
            shape.show()

    """
    return get_backend().construct(
        "cuboid",
        _forward(
            _groups(
                "cuboid",
                {
                    "size": size,
                    "p1": p1,
                    "p2": p2,
                    "teardrop": teardrop,
                    "trimcorners": trimcorners,
                    "fn": fn,
                    "fa": fa,
                    "fs": fs,
                    "res": res,
                    "rounding": rounding,
                    "anchor": anchor,
                    "spin": spin,
                    "except_edges": except_edges,
                    "orient": orient,
                    "edges": edges,
                    "chamfer": chamfer,
                },
                placement=placement,
                treatment=treatment,
                selection=selection,
                per_corner=False,
            )
        ),
    )


def cyl(
    height: float | None = None,
    radius: float | None = None,
    *,
    center: bool | None = None,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    chamfer: float | None = None,
    treatment: EdgeTreatment | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    shift: Sequence[float] | None = (0, 0),
    anchor: Anchor | Sequence[float] | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    circumscribe: bool | None = False,
    clip_angle: float | None = 90.0,
    extra: float | None = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    from_end: bool | None = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    realign: bool | None = False,
    teardrop: bool | float | None = False,
    tex_depth: float | None = 1.0,
    tex_inset: bool | float | None = False,
    tex_reps: int | Sequence[int] | None = None,
    tex_size: float | Sequence[float] | None = None,
    texture: Any = None,
    texturing: Texturing | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a cyl on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        height: Length of the cylinder along its axis (default 1)
        radius: Radius of the cylinder (default 1)
        center: If given, overrides anchor (True -> CENTER, False -> BOTTOM)
        length: Length of the cylinder along its axis (default 1)
        radius1: Radius of the negative end of the cylinder.
        radius2: Radius of the positive end of the cylinder.
        diameter: Diameter of the cylinder.
        diameter1: Diameter of the negative end of the cylinder.
        diameter2: Diameter of the positive end of the cylinder.
        chamfer: Chamfer size on the end rims (overall/negative/positive)
        treatment: A rounding or a chamfer as one value (SPEC G-1). An edge is rounded or chamfered,
            never both, so this makes the pair unrepresentable rather than checked; giving it beside
            rounding= or chamfer= raises (SPEC G-3).
        chamfer1: Chamfer size on the end rims (overall/negative/positive)
        chamfer2: Chamfer size on the end rims (overall/negative/positive)
        rounding: Rounding radius on the end rims (overall/negative/positive)
        rounding1: Rounding radius on the end rims (overall/negative/positive)
        rounding2: Rounding radius on the end rims (overall/negative/positive)
        shift: X/Y offset for the positive end (shear) (default [0,0])
        anchor: Anchor point (default CENTER)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        chamfer_angle: End chamfer angle in degrees away from the ends (CSG backend).
        chamfer_angle1: Chamfer angle at the bottom end (CSG backend).
        chamfer_angle2: Chamfer angle at the top end (CSG backend).
        circumscribe: Circumscribe rather than inscribe the given radius (CSG backend).
        clip_angle: Clip the rounding arc at the bottom of the cylinder (CSG backend).
        extra: Extra height at both ends, invisible to anchoring (CSG backend).
        extra1: Extra height at the bottom end (CSG backend).
        extra2: Extra height at the top end (CSG backend).
        from_end: Measure the chamfer along the conic face rather than the axis (CSG backend).
        from_end1: Measure the bottom chamfer along the conic face (CSG backend).
        from_end2: Measure the top chamfer along the conic face (CSG backend).
        realign: Shift point alignment by half a facet (CSG backend).
        teardrop: Limit the rounding angle from horizontal, for printability (CSG backend).
        tex_depth: Depth of the texture (CSG backend).
        tex_inset: Inset the texture into the surface (CSG backend).
        tex_reps: Number of texture repetitions (CSG backend).
        tex_size: Size of one texture tile (CSG backend).
        texture: Named texture for the side surface (CSG backend).
        texturing: The texture and how it is applied, as one value (SPEC G-1). Giving it beside any
            of the tex_* arguments raises (SPEC G-3).
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend). Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back out
            to fa/fs.
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fa=...)`` value applies.
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fs=...)`` value applies.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        A basic cylinder:
        .. pythonscad-example::

            from pybosl2 import cyl

            shape = cyl(radius=10, height=30)
            shape.show()

        A cylinder with chamfered ends:
        .. pythonscad-example::

            from pybosl2 import cyl

            shape = cyl(radius=15, height=40, chamfer=2)
            shape.show()

        A cylinder with rounded ends:
        .. pythonscad-example::

            from pybosl2 import cyl

            shape = cyl(radius=12, height=35, rounding=3)
            shape.show()

    """
    return get_backend().construct(
        "cyl",
        _forward(
            _groups(
                "cyl",
                {
                    "height": height,
                    "radius": radius,
                    "center": center,
                    "length": length,
                    "radius1": radius1,
                    "radius2": radius2,
                    "diameter": diameter,
                    "diameter1": diameter1,
                    "diameter2": diameter2,
                    "chamfer1": chamfer1,
                    "chamfer2": chamfer2,
                    "rounding1": rounding1,
                    "rounding2": rounding2,
                    "shift": shift,
                    "chamfer_angle": chamfer_angle,
                    "chamfer_angle1": chamfer_angle1,
                    "chamfer_angle2": chamfer_angle2,
                    "circumscribe": circumscribe,
                    "clip_angle": clip_angle,
                    "extra": extra,
                    "extra1": extra1,
                    "extra2": extra2,
                    "from_end": from_end,
                    "from_end1": from_end1,
                    "from_end2": from_end2,
                    "realign": realign,
                    "teardrop": teardrop,
                    "fn": fn,
                    "fa": fa,
                    "fs": fs,
                    "res": res,
                    "rounding": rounding,
                    "anchor": anchor,
                    "spin": spin,
                    "tex_inset": tex_inset,
                    "tex_reps": tex_reps,
                    "orient": orient,
                    "tex_size": tex_size,
                    "texture": texture,
                    "chamfer": chamfer,
                    "tex_depth": tex_depth,
                },
                placement=placement,
                treatment=treatment,
                texturing=texturing,
                per_corner=False,
            )
        ),
    )


def cylinder(
    height: float | None = None,
    radius: float | None = None,
    *,
    chamfer: float | None = None,
    treatment: EdgeTreatment | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    center: bool | None = None,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    circumscribe: bool | None = False,
    clip_angle: float | None = 90.0,
    extra: float | None = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    from_end: bool | None = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    realign: bool | None = False,
    shift: Sequence[float] | None = (0, 0),
    teardrop: bool | float | None = False,
    tex_depth: float | None = 1.0,
    tex_inset: bool | float | None = False,
    tex_reps: int | Sequence[int] | None = None,
    tex_size: float | Sequence[float] | None = None,
    texture: Any = None,
    texturing: Texturing | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a cylinder on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        height: Length of the cylinder along its axis (default 1)
        radius: Radius of the cylinder (default 1)
        chamfer: Chamfer size on the end rims (overall/negative/positive)
        treatment: A rounding or a chamfer as one value (SPEC G-1). An edge is rounded or chamfered,
            never both, so this makes the pair unrepresentable rather than checked; giving it beside
            rounding= or chamfer= raises (SPEC G-3).
        chamfer1: Chamfer size on the end rims (overall/negative/positive)
        chamfer2: Chamfer size on the end rims (overall/negative/positive)
        rounding: Rounding radius on the end rims (overall/negative/positive)
        rounding1: Rounding radius on the end rims (overall/negative/positive)
        rounding2: Rounding radius on the end rims (overall/negative/positive)
        center: If given, overrides anchor (True -> CENTER, False -> BOTTOM)
        length: Length of the cylinder along its axis (default 1)
        radius1: Radius of the negative end of the cylinder.
        radius2: Radius of the positive end of the cylinder.
        diameter: Diameter of the cylinder.
        diameter1: Diameter of the negative end of the cylinder.
        diameter2: Diameter of the positive end of the cylinder.
        anchor: Anchor point (default BOTTOM if center=False, otherwise CENTER)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        chamfer_angle: End chamfer angle in degrees away from the ends (CSG backend).
        chamfer_angle1: Chamfer angle at the bottom end (CSG backend).
        chamfer_angle2: Chamfer angle at the top end (CSG backend).
        circumscribe: Circumscribe rather than inscribe the given radius (CSG backend).
        clip_angle: Clip the rounding arc at the bottom of the cylinder (CSG backend).
        extra: Extra height at both ends, invisible to anchoring (CSG backend).
        extra1: Extra height at the bottom end (CSG backend).
        extra2: Extra height at the top end (CSG backend).
        from_end: Measure the chamfer along the conic face rather than the axis (CSG backend).
        from_end1: Measure the bottom chamfer along the conic face (CSG backend).
        from_end2: Measure the top chamfer along the conic face (CSG backend).
        realign: Shift point alignment by half a facet (CSG backend).
        shift: ``[x, y]`` offset for the positive end, shearing the solid (CSG backend).
        teardrop: Limit the rounding angle from horizontal, for printability (CSG backend).
        tex_depth: Depth of the texture (CSG backend).
        tex_inset: Inset the texture into the surface (CSG backend).
        tex_reps: Number of texture repetitions (CSG backend).
        tex_size: Size of one texture tile (CSG backend).
        texture: Named texture for the side surface (CSG backend).
        texturing: The texture and how it is applied, as one value (SPEC G-1). Giving it beside any
            of the tex_* arguments raises (SPEC G-3).
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend). Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back out
            to fa/fs.
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fa=...)`` value applies.
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fs=...)`` value applies.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        A basic cylinder:

        .. pythonscad-example::

            from pybosl2 import cylinder

            cylinder(height=30, radius=10).show()

        A cylinder with chamfered ends:

        .. pythonscad-example::

            from pybosl2 import cylinder

            cylinder(height=40, radius=15, chamfer=2).show()

        A cylinder with rounded ends:

        .. pythonscad-example::

            from pybosl2 import cylinder

            cylinder(height=30, radius=12, rounding=2).show()

    """
    return get_backend().construct(
        "cylinder",
        _forward(
            _groups(
                "cylinder",
                {
                    "height": height,
                    "radius": radius,
                    "chamfer1": chamfer1,
                    "chamfer2": chamfer2,
                    "rounding1": rounding1,
                    "rounding2": rounding2,
                    "center": center,
                    "length": length,
                    "radius1": radius1,
                    "radius2": radius2,
                    "diameter": diameter,
                    "diameter1": diameter1,
                    "diameter2": diameter2,
                    "chamfer_angle": chamfer_angle,
                    "chamfer_angle1": chamfer_angle1,
                    "chamfer_angle2": chamfer_angle2,
                    "circumscribe": circumscribe,
                    "clip_angle": clip_angle,
                    "extra": extra,
                    "extra1": extra1,
                    "extra2": extra2,
                    "from_end": from_end,
                    "from_end1": from_end1,
                    "from_end2": from_end2,
                    "realign": realign,
                    "shift": shift,
                    "teardrop": teardrop,
                    "fn": fn,
                    "fa": fa,
                    "fs": fs,
                    "res": res,
                    "rounding": rounding,
                    "anchor": anchor,
                    "spin": spin,
                    "tex_inset": tex_inset,
                    "tex_reps": tex_reps,
                    "orient": orient,
                    "tex_size": tex_size,
                    "texture": texture,
                    "chamfer": chamfer,
                    "tex_depth": tex_depth,
                },
                placement=placement,
                treatment=treatment,
                texturing=texturing,
                per_corner=False,
            )
        ),
    )


def octahedron(
    size: float | None = 1,
    *,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    res: int | None = None,
) -> Solid:
    """Return a octahedron on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        size: Width of the octahedron, tip to tip.
        anchor: Anchor point (default CENTER)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import octahedron

            octahedron(size=20).show()

    """
    return get_backend().construct(
        "octahedron",
        _forward(
            _groups(
                "octahedron",
                {
                    "size": size,
                    "anchor": anchor,
                    "spin": spin,
                    "orient": orient,
                    "res": res,
                },
                placement=placement,
            )
        ),
    )


def onion(
    radius: float | None = None,
    *,
    angle: float | None = 45,
    cap_height: float | None = None,
    diameter: float | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    circumscribe: bool | None = False,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a onion on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        radius: Radius of the spherical portion of the bottom (default 1)
        angle: Angle of the cone from vertical in degrees (default 45)
        cap_height: Height above the sphere center to truncate the shape (default: no truncation)
        diameter: Diameter of the spherical portion of the bottom.
        anchor: Anchor point (default CENTER)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        circumscribe: circumscribe rather than inscribe the given radius/diameter (default False) (CSG backend).
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend). Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back out
            to fa/fs.
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fa=...)`` value applies.
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fs=...)`` value applies.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import onion

            onion(radius=15).show()

    """
    return get_backend().construct(
        "onion",
        _forward(
            _groups(
                "onion",
                {
                    "radius": radius,
                    "angle": angle,
                    "cap_height": cap_height,
                    "diameter": diameter,
                    "circumscribe": circumscribe,
                    "fn": fn,
                    "fa": fa,
                    "fs": fs,
                    "res": res,
                    "anchor": anchor,
                    "spin": spin,
                    "orient": orient,
                },
                placement=placement,
            )
        ),
    )


def pie_slice(
    height: float | None = None,
    radius: float | None = None,
    *,
    angle: float | None = 30,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    length: float | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a pie_slice on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        height: Height of the pie slice.
        radius: Radius of the pie slice.
        angle: Pie slice angle in degrees (default 30)
        radius1: Bottom radius of the pie slice.
        radius2: Top radius of the pie slice.
        diameter: Diameter of the pie slice.
        diameter1: Diameter of the bottom.
        diameter2: Diameter of the top.
        length: Height of the pie slice.
        anchor: Anchor point (default CENTER)
        center: If given, overrides anchor.
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend). Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back out
            to fa/fs.
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fa=...)`` value applies.
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fs=...)`` value applies.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import pie_slice

            pie_slice(radius=20, angle=120, height=5).show()

    """
    return get_backend().construct(
        "pie_slice",
        _forward(
            _groups(
                "pie_slice",
                {
                    "height": height,
                    "radius": radius,
                    "angle": angle,
                    "radius1": radius1,
                    "radius2": radius2,
                    "diameter": diameter,
                    "diameter1": diameter1,
                    "diameter2": diameter2,
                    "length": length,
                    "center": center,
                    "fn": fn,
                    "fa": fa,
                    "fs": fs,
                    "res": res,
                    "anchor": anchor,
                    "spin": spin,
                    "orient": orient,
                },
                placement=placement,
            )
        ),
    )


def prismoid(
    size1: Sequence[float],
    size2: Sequence[float],
    *,
    height: float | None = None,
    shift: Sequence[float] | None = (0, 0),
    length: float | None = None,
    rounding: float | Sequence[float] | None = 0,
    rounding1: float | Sequence[float] | None = None,
    rounding2: float | Sequence[float] | None = None,
    chamfer: float | Sequence[float] | None = 0,
    treatment: EdgeTreatment | None = None,
    chamfer1: float | Sequence[float] | None = None,
    chamfer2: float | Sequence[float] | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.BOTTOM,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a prismoid on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        size1: [width, length] of the bottom end.
        size2: [width, length] of the top end.
        height: Height of the prism.
        shift: [X,Y] shift of the top center relative to the bottom center.
        length: Height of the prism.
        rounding: Radius of the vertical edge rounding, or one radius per edge (CSG backend --
            the SDF prismoid has no exact form for a tapered box's independently-radiused vertical
            edges; see :func:`pybosl2.sdf.shapes3d.prismoid`).
        rounding1: Vertical edge rounding at the bottom end (CSG backend).
        rounding2: Vertical edge rounding at the top end (CSG backend).
        chamfer: Size of the vertical edge chamfer, or one size per edge (CSG backend).
        treatment: A rounding or a chamfer as one value (SPEC G-1). An edge is rounded or chamfered,
            never both, so this makes the pair unrepresentable rather than checked; giving it beside
            rounding= or chamfer= raises (SPEC G-3).
        chamfer1: Vertical edge chamfer at the bottom end (CSG backend).
        chamfer2: Vertical edge chamfer at the top end (CSG backend).
        anchor: Anchor point (default BOTTOM)
        center: If given, overrides anchor.
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend). Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back out
            to fa/fs.
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fa=...)`` value applies.
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fs=...)`` value applies.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import prismoid

            shape = prismoid([40, 40], [20, 25], height=30)
            shape.show()

    """
    return get_backend().construct(
        "prismoid",
        _forward(
            _groups(
                "prismoid",
                {
                    "size1": size1,
                    "size2": size2,
                    "height": height,
                    "shift": shift,
                    "length": length,
                    "rounding1": rounding1,
                    "rounding2": rounding2,
                    "chamfer1": chamfer1,
                    "chamfer2": chamfer2,
                    "center": center,
                    "fn": fn,
                    "fa": fa,
                    "fs": fs,
                    "res": res,
                    "rounding": rounding,
                    "anchor": anchor,
                    "spin": spin,
                    "orient": orient,
                    "chamfer": chamfer,
                },
                placement=placement,
                treatment=treatment,
            )
        ),
    )


def rect_tube(
    height: float | None = None,
    size: float | Sequence[float] | None = None,
    *,
    isize: float | Sequence[float] | None = None,
    wall: float | None = None,
    rounding: float | Sequence[float] | None = 0,
    inner_rounding: float | Sequence[float] | None = 0,
    anchor: Anchor | Sequence[float] | None = Anchor.BOTTOM.vector,
    length: float | None = None,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    chamfer: float | None = 0,
    treatment: EdgeTreatment | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    inner_chamfer: float | None = 0,
    inner_chamfer1: float | None = None,
    inner_chamfer2: float | None = None,
    inner_rounding1: float | None = None,
    inner_rounding2: float | None = None,
    isize1: Sequence[float] | None = None,
    isize2: Sequence[float] | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    shift: Sequence[float] | None = (0, 0),
    size1: Sequence[float] | None = None,
    size2: Sequence[float] | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a rect_tube on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        height: Height of the tube (default 1)
        size: Outer [X,Y] size of the tube.
        isize: Inner [X,Y] size of the tube.
        wall: Wall thickness.
        rounding: Outer edge rounding radius (overall/bottom/top)
        inner_rounding: Inner edge rounding radius (default: same as rounding)
        anchor: Anchor point (default BOTTOM)
        length: Length of the tube (default 1)
        center: If given, overrides anchor.
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        chamfer: outer edge chamfer size (overall/bottom/top) (CSG backend).
        treatment: A rounding or a chamfer as one value (SPEC G-1). An edge is rounded or chamfered,
            never both, so this makes the pair unrepresentable rather than checked; giving it beside
            rounding= or chamfer= raises (SPEC G-3).
        chamfer1: outer edge chamfer size (overall/bottom/top) (CSG backend).
        chamfer2: outer edge chamfer size (overall/bottom/top) (CSG backend).
        inner_chamfer: inner edge chamfer size (default: same as chamfer) (CSG backend).
        inner_chamfer1: inner edge chamfer size (default: same as chamfer) (CSG backend).
        inner_chamfer2: inner edge chamfer size (default: same as chamfer) (CSG backend).
        inner_rounding1: inner edge rounding radius (default: same as rounding) (CSG backend).
        inner_rounding2: inner edge rounding radius (default: same as rounding) (CSG backend).
        isize1: inner [X,Y] size at the bottom/top (CSG backend).
        isize2: inner [X,Y] size at the bottom/top (CSG backend).
        rounding1: outer edge rounding radius (overall/bottom/top) (CSG backend).
        rounding2: outer edge rounding radius (overall/bottom/top) (CSG backend).
        shift: [X,Y] shift of the top center relative to the bottom center (CSG backend).
        size1: outer [X,Y] size at the bottom/top (CSG backend).
        size2: outer [X,Y] size at the bottom/top (CSG backend).
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend). Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back out
            to fa/fs.
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fa=...)`` value applies.
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fs=...)`` value applies.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import rect_tube

            rect_tube(size=30, wall=3, height=20).show()

    """
    return get_backend().construct(
        "rect_tube",
        _forward(
            _groups(
                "rect_tube",
                {
                    "height": height,
                    "size": size,
                    "isize": isize,
                    "wall": wall,
                    "inner_rounding": inner_rounding,
                    "length": length,
                    "center": center,
                    "chamfer1": chamfer1,
                    "chamfer2": chamfer2,
                    "inner_chamfer": inner_chamfer,
                    "inner_chamfer1": inner_chamfer1,
                    "inner_chamfer2": inner_chamfer2,
                    "inner_rounding1": inner_rounding1,
                    "inner_rounding2": inner_rounding2,
                    "isize1": isize1,
                    "isize2": isize2,
                    "rounding1": rounding1,
                    "rounding2": rounding2,
                    "shift": shift,
                    "size1": size1,
                    "size2": size2,
                    "fn": fn,
                    "fa": fa,
                    "fs": fs,
                    "res": res,
                    "rounding": rounding,
                    "anchor": anchor,
                    "spin": spin,
                    "orient": orient,
                    "chamfer": chamfer,
                },
                placement=placement,
                treatment=treatment,
            )
        ),
    )


def regular_prism(
    sides: int,
    height: float | None = None,
    radius: float | None = None,
    *,
    diameter: float | None = None,
    inner_radius: float | None = None,
    inner_diameter: float | None = None,
    side: float | None = None,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    shift: Sequence[float] | None = (0, 0),
    circumscribe: bool | None = False,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    chamfer: float | None = None,
    treatment: EdgeTreatment | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    realign: bool | None = False,
    anchor: Anchor | Sequence[float] | None = None,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a regular_prism on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        sides: Number of sides (integer >= 3)
        height: Prism height (default 1)
        radius: Overall size (see above)
        diameter: Overall size (see above)
        inner_radius: Overall size (see above)
        inner_diameter: Overall size (see above)
        side: Overall size (see above)
        length: Prism height (default 1)
        radius1: Bottom radius, for a tapered prism (CSG backend).
        radius2: Top radius, for a tapered prism (CSG backend).
        shift: ``[x, y]`` offset of the top face from the bottom (CSG backend).
        circumscribe: If True the polygon encloses the given radius instead of being inscribed in
            it (CSG backend).
        rounding: End rounding radius (overall/bottom/top)
        rounding1: End rounding radius (overall/bottom/top)
        rounding2: End rounding radius (overall/bottom/top)
        chamfer: End chamfer size (overall/bottom/top)
        treatment: A rounding or a chamfer as one value (SPEC G-1). An edge is rounded or chamfered,
            never both, so this makes the pair unrepresentable rather than checked; giving it beside
            rounding= or chamfer= raises (SPEC G-3).
        chamfer1: End chamfer size (overall/bottom/top)
        chamfer2: End chamfer size (overall/bottom/top)
        realign: Rotate by half a facet so a face, not a vertex, faces +X (default False)
        anchor: Anchor point (default CENTER)
        center: If given, overrides anchor (True -> CENTER, False -> BOTTOM)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend). Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back out
            to fa/fs.
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fa=...)`` value applies.
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fs=...)`` value applies.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import regular_prism

            shape = regular_prism(6, height=20, radius=15)
            shape.show()

        .. pythonscad-example::

            from pybosl2 import regular_prism

            shape = regular_prism(5, height=20, inner_radius=12, rounding=2)
            shape.show()

    """
    return get_backend().construct(
        "regular_prism",
        _forward(
            _groups(
                "regular_prism",
                {
                    "sides": sides,
                    "height": height,
                    "radius": radius,
                    "diameter": diameter,
                    "inner_radius": inner_radius,
                    "inner_diameter": inner_diameter,
                    "side": side,
                    "length": length,
                    "radius1": radius1,
                    "radius2": radius2,
                    "shift": shift,
                    "circumscribe": circumscribe,
                    "rounding1": rounding1,
                    "rounding2": rounding2,
                    "chamfer1": chamfer1,
                    "chamfer2": chamfer2,
                    "realign": realign,
                    "center": center,
                    "fn": fn,
                    "fa": fa,
                    "fs": fs,
                    "res": res,
                    "rounding": rounding,
                    "anchor": anchor,
                    "spin": spin,
                    "orient": orient,
                    "chamfer": chamfer,
                },
                placement=placement,
                treatment=treatment,
                per_corner=False,
            )
        ),
    )


def sphere(
    radius: float | None = None,
    *,
    diameter: float | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    circumscribe: bool | None = False,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a sphere on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        radius: Radius of the sphere.
        diameter: Diameter of the sphere.
        anchor: Anchor point (default CENTER)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        circumscribe: circumscribe rather than inscribe the sphere (default False) (CSG backend).
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend). Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back out
            to fa/fs.
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fa=...)`` value applies.
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fs=...)`` value applies.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import sphere

            shape = sphere(radius=15)
            shape.show()

    """
    return get_backend().construct(
        "sphere",
        _forward(
            _groups(
                "sphere",
                {
                    "radius": radius,
                    "diameter": diameter,
                    "circumscribe": circumscribe,
                    "fn": fn,
                    "fa": fa,
                    "fs": fs,
                    "res": res,
                    "anchor": anchor,
                    "spin": spin,
                    "orient": orient,
                },
                placement=placement,
            )
        ),
    )


def spheroid(
    radius: float | None = None,
    *,
    diameter: float | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    circumscribe: bool | None = False,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a spheroid on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        radius: Radius of the spheroid.
        diameter: Diameter of the spheroid.
        anchor: Anchor point (default CENTER)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        circumscribe: circumscribe rather than inscribe the spheroid (default False) (CSG backend).
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend). Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back out
            to fa/fs.
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fa=...)`` value applies.
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fs=...)`` value applies.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import spheroid

            spheroid(radius=15).show()

    """
    return get_backend().construct(
        "spheroid",
        _forward(
            _groups(
                "spheroid",
                {
                    "radius": radius,
                    "diameter": diameter,
                    "circumscribe": circumscribe,
                    "fn": fn,
                    "fa": fa,
                    "fs": fs,
                    "res": res,
                    "anchor": anchor,
                    "spin": spin,
                    "orient": orient,
                },
                placement=placement,
            )
        ),
    )


def teardrop(
    height: float | None = None,
    radius: float | None = None,
    *,
    angle: float | None = 45,
    cap_height: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    cap_h1: float | None = None,
    cap_h2: float | None = None,
    chamfer: float | None = 0,
    chamfer1: float | None = 0,
    chamfer2: float | None = 0,
    circumscribe: bool | None = False,
    realign: bool | None = False,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a teardrop on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        height: Thickness of the teardrop (default 1)
        radius: Radius of the circular part (default 1)
        angle: Angle of the hat walls from the Z axis in degrees (default 45)
        cap_height: Height above center to truncate the shape (default: no truncation)
        radius1: Radius of the circular portion of the front end.
        radius2: Radius of the circular portion of the back end.
        diameter: Diameter of the circular portion.
        diameter1: Diameter of the front end.
        diameter2: Diameter of the back end.
        anchor: Anchor point (default CENTER)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        cap_h1: truncation height on the front side (CSG backend).
        cap_h2: truncation height on the back side (CSG backend).
        chamfer: chamfer size along the bottom/top faces (overall) (default 0) (CSG backend).
        chamfer1: chamfer size along the bottom face (default 0) (CSG backend).
        chamfer2: chamfer size along the top face (default 0) (CSG backend).
        circumscribe: produce a circumscribing teardrop shape (default False) (CSG backend).
        realign: shift face alignment, passed to teardrop2d (default False) (CSG backend).
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend). Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back out
            to fa/fs.
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fa=...)`` value applies.
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fs=...)`` value applies.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import teardrop

            shape = teardrop(radius=8, angle=45, height=15)
            shape.show()

    """
    return get_backend().construct(
        "teardrop",
        _forward(
            _groups(
                "teardrop",
                {
                    "height": height,
                    "radius": radius,
                    "angle": angle,
                    "cap_height": cap_height,
                    "radius1": radius1,
                    "radius2": radius2,
                    "diameter": diameter,
                    "diameter1": diameter1,
                    "diameter2": diameter2,
                    "cap_h1": cap_h1,
                    "cap_h2": cap_h2,
                    "chamfer1": chamfer1,
                    "chamfer2": chamfer2,
                    "circumscribe": circumscribe,
                    "realign": realign,
                    "fn": fn,
                    "fa": fa,
                    "fs": fs,
                    "res": res,
                    "anchor": anchor,
                    "spin": spin,
                    "orient": orient,
                    "chamfer": chamfer,
                },
                placement=placement,
                per_corner=False,
            )
        ),
    )


def torus(
    major_radius: float | None = None,
    minor_radius: float | None = None,
    *,
    major_diameter: float | None = None,
    minor_diameter: float | None = None,
    outer_radius: float | None = None,
    inner_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_diameter: float | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a torus on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        major_radius: Major radius of the torus ring (use with minor_radius or minor_diameter)
        minor_radius: Minor radius of the torus ring (use with major_radius or major_diameter)
        major_diameter: Major diameter of the torus ring.
        minor_diameter: Minor diameter of the torus ring.
        outer_radius: Outer radius of the torus (BOSL2 `or`) (use with inner_radius or inner_diameter)
        inner_radius: Inside radius of the torus (use with outer_radius or outer_diameter)
        outer_diameter: Outer diameter of the torus (use with inner_radius or inner_diameter)
        inner_diameter: Inside diameter of the torus (use with outer_radius or outer_diameter)
        anchor: Anchor point (default CENTER)
        center: If given, overrides anchor (True -> CENTER, False -> DOWN)
        spin: Z-axis rotation in degrees (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend). Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back out
            to fa/fs.
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fa=...)`` value applies.
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fs=...)`` value applies.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import torus

            shape = torus(major_radius=25, minor_radius=8)
            shape.show()

    """
    return get_backend().construct(
        "torus",
        _forward(
            _groups(
                "torus",
                {
                    "major_radius": major_radius,
                    "minor_radius": minor_radius,
                    "major_diameter": major_diameter,
                    "minor_diameter": minor_diameter,
                    "outer_radius": outer_radius,
                    "inner_radius": inner_radius,
                    "outer_diameter": outer_diameter,
                    "inner_diameter": inner_diameter,
                    "center": center,
                    "fn": fn,
                    "fa": fa,
                    "fs": fs,
                    "res": res,
                    "anchor": anchor,
                    "spin": spin,
                    "orient": orient,
                },
                placement=placement,
            )
        ),
    )


def tube(
    height: float | None = None,
    outer_radius: float | None = None,
    *,
    inner_radius: float | None = None,
    outer_diameter: float | None = None,
    inner_diameter: float | None = None,
    wall: float | None = None,
    length: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    chamfer: float | None = None,
    treatment: EdgeTreatment | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    anchor: Anchor | Sequence[float] | None = Anchor.CENTER,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    inner_diameter1: float | None = None,
    inner_diameter2: float | None = None,
    inner_radius1: float | None = None,
    inner_radius2: float | None = None,
    outer_diameter1: float | None = None,
    outer_diameter2: float | None = None,
    outer_radius1: float | None = None,
    outer_radius2: float | None = None,
    realign: bool | None = False,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a tube on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        height: Height of the tube (default 1)
        outer_radius: Outer radius of the tube (BOSL2 ``or``) (default 1)
        inner_radius: Inner radius of the tube.
        outer_diameter: Outer diameter of the tube.
        inner_diameter: Inner diameter of the tube.
        wall: Horizontal wall thickness (default 1)
        length: Height of the tube (default 1)
        rounding: Rounding radius on end rims (overall/bottom/top)
        rounding1: Rounding radius on end rims (overall/bottom/top)
        rounding2: Rounding radius on end rims (overall/bottom/top)
        chamfer: Chamfer size on end rims (overall/bottom/top)
        treatment: A rounding or a chamfer as one value (SPEC G-1). An edge is rounded or chamfered,
            never both, so this makes the pair unrepresentable rather than checked; giving it beside
            rounding= or chamfer= raises (SPEC G-3).
        chamfer1: Chamfer size on end rims (overall/bottom/top)
        chamfer2: Chamfer size on end rims (overall/bottom/top)
        anchor: Anchor point (default CENTER)
        center: If given, overrides anchor (True -> CENTER, False -> DOWN)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        inner_diameter1: inner diameter of the bottom/top (CSG backend).
        inner_diameter2: inner diameter of the bottom/top (CSG backend).
        inner_radius1: inner radius of the bottom/top (CSG backend).
        inner_radius2: inner radius of the bottom/top (CSG backend).
        outer_diameter1: outer diameter of the bottom/top (CSG backend).
        outer_diameter2: outer diameter of the bottom/top (CSG backend).
        outer_radius1: outer radius of the bottom/top (CSG backend).
        outer_radius2: outer radius of the bottom/top (CSG backend).
        realign: rotate by half the angle of one face (default False) (CSG backend).
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend). Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back out
            to fa/fs.
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fa=...)`` value applies.
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fs=...)`` value applies.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import tube

            shape = tube(height=20, outer_radius=15, inner_radius=10)
            shape.show()

        A tube with chamfered end rims:

        .. pythonscad-example::

            from pybosl2 import tube

            shape = tube(height=20, outer_radius=15, inner_radius=10, chamfer=1)
            shape.show()

    """
    return get_backend().construct(
        "tube",
        _forward(
            _groups(
                "tube",
                {
                    "height": height,
                    "outer_radius": outer_radius,
                    "inner_radius": inner_radius,
                    "outer_diameter": outer_diameter,
                    "inner_diameter": inner_diameter,
                    "wall": wall,
                    "length": length,
                    "rounding1": rounding1,
                    "rounding2": rounding2,
                    "chamfer1": chamfer1,
                    "chamfer2": chamfer2,
                    "center": center,
                    "inner_diameter1": inner_diameter1,
                    "inner_diameter2": inner_diameter2,
                    "inner_radius1": inner_radius1,
                    "inner_radius2": inner_radius2,
                    "outer_diameter1": outer_diameter1,
                    "outer_diameter2": outer_diameter2,
                    "outer_radius1": outer_radius1,
                    "outer_radius2": outer_radius2,
                    "realign": realign,
                    "fn": fn,
                    "fa": fa,
                    "fs": fs,
                    "res": res,
                    "rounding": rounding,
                    "anchor": anchor,
                    "spin": spin,
                    "orient": orient,
                    "chamfer": chamfer,
                },
                placement=placement,
                treatment=treatment,
                per_corner=False,
            )
        ),
    )


def wedge(
    size: Sequence[float] | None = (1, 1, 1),
    *,
    anchor: Anchor | Sequence[float] | None = Anchor.BOTTOM_FRONT_LEFT.vector,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    res: int | None = None,
) -> Solid:
    """Return a wedge on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        size: [width, thickness, height].
        anchor: Anchor point (default FRONT+LEFT+BOTTOM)
        center: If given, overrides anchor (True -> CENTER, False -> FRONT+LEFT+BOTTOM)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import wedge

            wedge([30, 20, 15]).show()

    """
    return get_backend().construct(
        "wedge",
        _forward(
            _groups(
                "wedge",
                {
                    "size": size,
                    "anchor": anchor,
                    "center": center,
                    "spin": spin,
                    "orient": orient,
                    "res": res,
                },
                placement=placement,
            )
        ),
    )


def xcyl(
    height: float | None = None,
    radius: float | None = None,
    *,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    chamfer: float | None = None,
    treatment: EdgeTreatment | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    circumscribe: bool | None = False,
    clip_angle: float | None = 90.0,
    extra: float | None = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    from_end: bool | None = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    realign: bool | None = False,
    shift: Sequence[float] | None = (0, 0),
    teardrop: bool | float | None = False,
    tex_depth: float | None = 1.0,
    tex_inset: bool | float | None = False,
    tex_reps: int | Sequence[int] | None = None,
    tex_size: float | Sequence[float] | None = None,
    texture: Any = None,
    texturing: Texturing | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a xcyl on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        height: Length of the cylinder along its axis (default 1)
        radius: Radius of the cylinder (default 1)
        length: Length of the cylinder along its axis (default 1)
        radius1: Radius of the negative end of the cylinder.
        radius2: Radius of the positive end of the cylinder.
        diameter: Diameter of the cylinder.
        diameter1: Diameter of the negative end of the cylinder.
        diameter2: Diameter of the positive end of the cylinder.
        chamfer: Chamfer size on the end rims (overall/negative/positive)
        treatment: A rounding or a chamfer as one value (SPEC G-1). An edge is rounded or chamfered,
            never both, so this makes the pair unrepresentable rather than checked; giving it beside
            rounding= or chamfer= raises (SPEC G-3).
        chamfer1: Chamfer size on the end rims (overall/negative/positive)
        chamfer2: Chamfer size on the end rims (overall/negative/positive)
        rounding: Rounding radius on the end rims (overall/negative/positive)
        rounding1: Rounding radius on the end rims (overall/negative/positive)
        rounding2: Rounding radius on the end rims (overall/negative/positive)
        anchor: Anchor point (default CENTER)
        center: If given, overrides anchor (True -> CENTER, False -> BOTTOM)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        chamfer_angle: End chamfer angle in degrees away from the ends (CSG backend).
        chamfer_angle1: Chamfer angle at the bottom end (CSG backend).
        chamfer_angle2: Chamfer angle at the top end (CSG backend).
        circumscribe: Circumscribe rather than inscribe the given radius (CSG backend).
        clip_angle: Clip the rounding arc at the bottom of the cylinder (CSG backend).
        extra: Extra height at both ends, invisible to anchoring (CSG backend).
        extra1: Extra height at the bottom end (CSG backend).
        extra2: Extra height at the top end (CSG backend).
        from_end: Measure the chamfer along the conic face rather than the axis (CSG backend).
        from_end1: Measure the bottom chamfer along the conic face (CSG backend).
        from_end2: Measure the top chamfer along the conic face (CSG backend).
        realign: Shift point alignment by half a facet (CSG backend).
        shift: ``[x, y]`` offset for the positive end, shearing the solid (CSG backend).
        teardrop: Limit the rounding angle from horizontal, for printability (CSG backend).
        tex_depth: Depth of the texture (CSG backend).
        tex_inset: Inset the texture into the surface (CSG backend).
        tex_reps: Number of texture repetitions (CSG backend).
        tex_size: Size of one texture tile (CSG backend).
        texture: Named texture for the side surface (CSG backend).
        texturing: The texture and how it is applied, as one value (SPEC G-1). Giving it beside any
            of the tex_* arguments raises (SPEC G-3).
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend). Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back out
            to fa/fs.
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fa=...)`` value applies.
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fs=...)`` value applies.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import xcyl

            shape = xcyl(radius=10, height=30)
            shape.show()

    """
    return get_backend().construct(
        "xcyl",
        _forward(
            _groups(
                "xcyl",
                {
                    "height": height,
                    "radius": radius,
                    "length": length,
                    "radius1": radius1,
                    "radius2": radius2,
                    "diameter": diameter,
                    "diameter1": diameter1,
                    "diameter2": diameter2,
                    "chamfer1": chamfer1,
                    "chamfer2": chamfer2,
                    "rounding1": rounding1,
                    "rounding2": rounding2,
                    "center": center,
                    "chamfer_angle": chamfer_angle,
                    "chamfer_angle1": chamfer_angle1,
                    "chamfer_angle2": chamfer_angle2,
                    "circumscribe": circumscribe,
                    "clip_angle": clip_angle,
                    "extra": extra,
                    "extra1": extra1,
                    "extra2": extra2,
                    "from_end": from_end,
                    "from_end1": from_end1,
                    "from_end2": from_end2,
                    "realign": realign,
                    "shift": shift,
                    "teardrop": teardrop,
                    "fn": fn,
                    "fa": fa,
                    "fs": fs,
                    "res": res,
                    "rounding": rounding,
                    "anchor": anchor,
                    "spin": spin,
                    "tex_inset": tex_inset,
                    "tex_reps": tex_reps,
                    "orient": orient,
                    "tex_size": tex_size,
                    "texture": texture,
                    "chamfer": chamfer,
                    "tex_depth": tex_depth,
                },
                placement=placement,
                treatment=treatment,
                texturing=texturing,
                per_corner=False,
            )
        ),
    )


def ycyl(
    height: float | None = None,
    radius: float | None = None,
    *,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    chamfer: float | None = None,
    treatment: EdgeTreatment | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    circumscribe: bool | None = False,
    clip_angle: float | None = 90.0,
    extra: float | None = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    from_end: bool | None = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    realign: bool | None = False,
    shift: Sequence[float] | None = (0, 0),
    teardrop: bool | float | None = False,
    tex_depth: float | None = 1.0,
    tex_inset: bool | float | None = False,
    tex_reps: int | Sequence[int] | None = None,
    tex_size: float | Sequence[float] | None = None,
    texture: Any = None,
    texturing: Texturing | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a ycyl on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        height: Length of the cylinder along its axis (default 1)
        radius: Radius of the cylinder (default 1)
        length: Length of the cylinder along its axis (default 1)
        radius1: Radius of the negative end of the cylinder.
        radius2: Radius of the positive end of the cylinder.
        diameter: Diameter of the cylinder.
        diameter1: Diameter of the negative end of the cylinder.
        diameter2: Diameter of the positive end of the cylinder.
        chamfer: Chamfer size on the end rims (overall/negative/positive)
        treatment: A rounding or a chamfer as one value (SPEC G-1). An edge is rounded or chamfered,
            never both, so this makes the pair unrepresentable rather than checked; giving it beside
            rounding= or chamfer= raises (SPEC G-3).
        chamfer1: Chamfer size on the end rims (overall/negative/positive)
        chamfer2: Chamfer size on the end rims (overall/negative/positive)
        rounding: Rounding radius on the end rims (overall/negative/positive)
        rounding1: Rounding radius on the end rims (overall/negative/positive)
        rounding2: Rounding radius on the end rims (overall/negative/positive)
        anchor: Anchor point (default CENTER)
        center: If given, overrides anchor (True -> CENTER, False -> BOTTOM)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        chamfer_angle: End chamfer angle in degrees away from the ends (CSG backend).
        chamfer_angle1: Chamfer angle at the bottom end (CSG backend).
        chamfer_angle2: Chamfer angle at the top end (CSG backend).
        circumscribe: Circumscribe rather than inscribe the given radius (CSG backend).
        clip_angle: Clip the rounding arc at the bottom of the cylinder (CSG backend).
        extra: Extra height at both ends, invisible to anchoring (CSG backend).
        extra1: Extra height at the bottom end (CSG backend).
        extra2: Extra height at the top end (CSG backend).
        from_end: Measure the chamfer along the conic face rather than the axis (CSG backend).
        from_end1: Measure the bottom chamfer along the conic face (CSG backend).
        from_end2: Measure the top chamfer along the conic face (CSG backend).
        realign: Shift point alignment by half a facet (CSG backend).
        shift: ``[x, y]`` offset for the positive end, shearing the solid (CSG backend).
        teardrop: Limit the rounding angle from horizontal, for printability (CSG backend).
        tex_depth: Depth of the texture (CSG backend).
        tex_inset: Inset the texture into the surface (CSG backend).
        tex_reps: Number of texture repetitions (CSG backend).
        tex_size: Size of one texture tile (CSG backend).
        texture: Named texture for the side surface (CSG backend).
        texturing: The texture and how it is applied, as one value (SPEC G-1). Giving it beside any
            of the tex_* arguments raises (SPEC G-3).
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend). Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back out
            to fa/fs.
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fa=...)`` value applies.
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fs=...)`` value applies.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import ycyl

            shape = ycyl(radius=10, height=30)
            shape.show()

    """
    return get_backend().construct(
        "ycyl",
        _forward(
            _groups(
                "ycyl",
                {
                    "height": height,
                    "radius": radius,
                    "length": length,
                    "radius1": radius1,
                    "radius2": radius2,
                    "diameter": diameter,
                    "diameter1": diameter1,
                    "diameter2": diameter2,
                    "chamfer1": chamfer1,
                    "chamfer2": chamfer2,
                    "rounding1": rounding1,
                    "rounding2": rounding2,
                    "center": center,
                    "chamfer_angle": chamfer_angle,
                    "chamfer_angle1": chamfer_angle1,
                    "chamfer_angle2": chamfer_angle2,
                    "circumscribe": circumscribe,
                    "clip_angle": clip_angle,
                    "extra": extra,
                    "extra1": extra1,
                    "extra2": extra2,
                    "from_end": from_end,
                    "from_end1": from_end1,
                    "from_end2": from_end2,
                    "realign": realign,
                    "shift": shift,
                    "teardrop": teardrop,
                    "fn": fn,
                    "fa": fa,
                    "fs": fs,
                    "res": res,
                    "rounding": rounding,
                    "anchor": anchor,
                    "spin": spin,
                    "tex_inset": tex_inset,
                    "tex_reps": tex_reps,
                    "orient": orient,
                    "tex_size": tex_size,
                    "texture": texture,
                    "chamfer": chamfer,
                    "tex_depth": tex_depth,
                },
                placement=placement,
                treatment=treatment,
                texturing=texturing,
                per_corner=False,
            )
        ),
    )


def zcyl(
    height: float | None = None,
    radius: float | None = None,
    *,
    length: float | None = None,
    radius1: float | None = None,
    radius2: float | None = None,
    diameter: float | None = None,
    diameter1: float | None = None,
    diameter2: float | None = None,
    chamfer: float | None = None,
    treatment: EdgeTreatment | None = None,
    chamfer1: float | None = None,
    chamfer2: float | None = None,
    rounding: float | None = None,
    rounding1: float | None = None,
    rounding2: float | None = None,
    anchor: Anchor | Sequence[float] | None = None,
    center: bool | None = None,
    spin: float | None = 0,
    orient: Anchor | Sequence[float] | None = Anchor.TOP,
    placement: Placement | None = None,
    chamfer_angle: float | None = None,
    chamfer_angle1: float | None = None,
    chamfer_angle2: float | None = None,
    circumscribe: bool | None = False,
    clip_angle: float | None = 90.0,
    extra: float | None = 0.0,
    extra1: float | None = None,
    extra2: float | None = None,
    from_end: bool | None = False,
    from_end1: bool | None = None,
    from_end2: bool | None = None,
    realign: bool | None = False,
    shift: Sequence[float] | None = (0, 0),
    teardrop: bool | float | None = False,
    tex_depth: float | None = 1.0,
    tex_inset: bool | float | None = False,
    tex_reps: int | Sequence[int] | None = None,
    tex_size: float | Sequence[float] | None = None,
    texture: Any = None,
    texturing: Texturing | None = None,
    fn: int | None = None,
    fa: float | None = None,
    fs: float | None = None,
    res: int | None = None,
) -> Solid:
    """Return a zcyl on the active backend.

    The same call builds the same shape on either backend: the façade owns the default for every
    argument both understand and forwards it (see :func:`use_backend`, and
    :func:`effective_defaults` to see what an omitted argument resolves to). Options only one
    backend has are marked below; each backend receives only what its own constructor declares.

    Args:
        height: Length of the cylinder along its axis (default 1)
        radius: Radius of the cylinder (default 1)
        length: Length of the cylinder along its axis (default 1)
        radius1: Radius of the negative end of the cylinder.
        radius2: Radius of the positive end of the cylinder.
        diameter: Diameter of the cylinder.
        diameter1: Diameter of the negative end of the cylinder.
        diameter2: Diameter of the positive end of the cylinder.
        chamfer: Chamfer size on the end rims (overall/negative/positive)
        treatment: A rounding or a chamfer as one value (SPEC G-1). An edge is rounded or chamfered,
            never both, so this makes the pair unrepresentable rather than checked; giving it beside
            rounding= or chamfer= raises (SPEC G-3).
        chamfer1: Chamfer size on the end rims (overall/negative/positive)
        chamfer2: Chamfer size on the end rims (overall/negative/positive)
        rounding: Rounding radius on the end rims (overall/negative/positive)
        rounding1: Rounding radius on the end rims (overall/negative/positive)
        rounding2: Rounding radius on the end rims (overall/negative/positive)
        anchor: Anchor point (default CENTER)
        center: If given, overrides anchor (True -> CENTER, False -> BOTTOM)
        spin: Z-axis rotation in degrees after anchor (default 0)
        orient: Direction to rotate the top towards, after spin (default UP)
        placement: Anchor, spin and orient as one reusable value (SPEC G-1). Giving this and any
            of those three raises, since the call cannot mean both (SPEC G-3).
        chamfer_angle: End chamfer angle in degrees away from the ends (CSG backend).
        chamfer_angle1: Chamfer angle at the bottom end (CSG backend).
        chamfer_angle2: Chamfer angle at the top end (CSG backend).
        circumscribe: Circumscribe rather than inscribe the given radius (CSG backend).
        clip_angle: Clip the rounding arc at the bottom of the cylinder (CSG backend).
        extra: Extra height at both ends, invisible to anchoring (CSG backend).
        extra1: Extra height at the bottom end (CSG backend).
        extra2: Extra height at the top end (CSG backend).
        from_end: Measure the chamfer along the conic face rather than the axis (CSG backend).
        from_end1: Measure the bottom chamfer along the conic face (CSG backend).
        from_end2: Measure the top chamfer along the conic face (CSG backend).
        realign: Shift point alignment by half a facet (CSG backend).
        shift: ``[x, y]`` offset for the positive end, shearing the solid (CSG backend).
        teardrop: Limit the rounding angle from horizontal, for printability (CSG backend).
        tex_depth: Depth of the texture (CSG backend).
        tex_inset: Inset the texture into the surface (CSG backend).
        tex_reps: Number of texture repetitions (CSG backend).
        tex_size: Size of one texture tile (CSG backend).
        texture: Named texture for the side surface (CSG backend).
        texturing: The texture and how it is applied, as one value (SPEC G-1). Giving it beside any
            of the tex_* arguments raises (SPEC G-3).
        fn: Fixed fragment count for curved surfaces; the ambient default applies when omitted, and 0 means "use
            fa/fs" (CSG backend). Omitted, the ambient ``use_defaults(fn=...)`` value applies; ``fn=0`` opts back out
            to fa/fs.
        fa: Minimum fragment angle in degrees; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fa=...)`` value applies.
        fs: Minimum fragment size in millimetres; ambient default when omitted (CSG backend). Omitted, the ambient
            ``use_defaults(fs=...)`` value applies.
        res: Sampling resolution; ambient default when omitted (SDF backend). Omitted, the ambient
            ``use_defaults(res=...)`` value applies.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import zcyl

            shape = zcyl(radius=10, height=30)
            shape.show()

    """
    return get_backend().construct(
        "zcyl",
        _forward(
            _groups(
                "zcyl",
                {
                    "height": height,
                    "radius": radius,
                    "length": length,
                    "radius1": radius1,
                    "radius2": radius2,
                    "diameter": diameter,
                    "diameter1": diameter1,
                    "diameter2": diameter2,
                    "chamfer1": chamfer1,
                    "chamfer2": chamfer2,
                    "rounding1": rounding1,
                    "rounding2": rounding2,
                    "center": center,
                    "chamfer_angle": chamfer_angle,
                    "chamfer_angle1": chamfer_angle1,
                    "chamfer_angle2": chamfer_angle2,
                    "circumscribe": circumscribe,
                    "clip_angle": clip_angle,
                    "extra": extra,
                    "extra1": extra1,
                    "extra2": extra2,
                    "from_end": from_end,
                    "from_end1": from_end1,
                    "from_end2": from_end2,
                    "realign": realign,
                    "shift": shift,
                    "teardrop": teardrop,
                    "fn": fn,
                    "fa": fa,
                    "fs": fs,
                    "res": res,
                    "rounding": rounding,
                    "anchor": anchor,
                    "spin": spin,
                    "tex_inset": tex_inset,
                    "tex_reps": tex_reps,
                    "orient": orient,
                    "tex_size": tex_size,
                    "texture": texture,
                    "chamfer": chamfer,
                    "tex_depth": tex_depth,
                },
                placement=placement,
                treatment=treatment,
                texturing=texturing,
                per_corner=False,
            )
        ),
    )


def effective_defaults(shape: str, backend: str | None = None) -> dict[str, DefaultValue]:
    """Report the value each argument of *shape* takes when the caller leaves it out.

    The façade owns the default for every argument both backends understand and forwards it
    whether or not the caller passed one (SPEC B-3, PLAN F-P1); the backend then takes the subset
    its own constructor declares (F-P2). One filter, in one place. This reports what an omitted
    argument resolves to, read live off the constructor the backend would call, so it can never
    drift from the code -- and where the façade owns the default it is the façade's that is
    reported, because that is the one that decides.

    Args:
        shape: BOSL2 shape name, e.g. ``"cuboid"``.
        backend: Backend to report for; the active one by default.

    Returns:
        Each parameter mapped to the :data:`DefaultValue` a bare call resolves to: the façade's own default for
        everything both backends understand, plus the backend's own for its exclusive options.
        Parameters with no default (the caller must supply those) and the ambient resolution
        knobs are omitted -- the latter come from :func:`pybosl2.defaults.use_defaults`.

    Raises:
        ValueError: If the backend has no constructor by that name.

    Examples:
        >>> from pybosl2.solid import effective_defaults
        >>> effective_defaults("cuboid")["size"]
        (1, 1, 1)

    """
    facade = globals().get(shape)
    owned: dict[str, DefaultValue] = {}
    if inspect.isfunction(facade):
        # the façade owns the default for everything both backends understand (SPEC B-3)
        owned = {
            name: parameter.default
            for name, parameter in inspect.signature(facade).parameters.items()
            if parameter.default is not inspect.Parameter.empty and name not in _AMBIENT
        }
    constructor = get_backend(backend).constructor(shape)
    parameters = inspect.signature(constructor).parameters
    backend_own: dict[str, DefaultValue] = {
        name: parameter.default
        for name, parameter in parameters.items()
        if parameter.default is not inspect.Parameter.empty and name not in _AMBIENT and name not in owned
    }
    return {**owned, **backend_own}


def polyhedron(points: Any, faces: Any = None, convexity: int | None = None) -> Solid:
    """Return a polyhedron on the active backend.

    Backends differ on what a polyhedron means (this is not part of the shared primitive surface):
    the CSG backend builds the exact mesh from *points* and *faces* (both required); the SDF
    backend builds the intersection of the face half-spaces, which can only describe a **convex**
    solid. For convex input the two agree. For anything else the SDF backend refuses rather than
    handing back the hull -- which would fill the concavities, report the same bounding box, and
    give no sign that it was not what you asked for (SPEC B-4, B-9).

    Args:
        points: The vertices, as ``[x, y, z]`` triples.
        faces: Vertex indices per face. Required by the CSG backend; on the SDF backend they must
            bound a convex solid.
        convexity: Convexity hint for preview rendering (CSG backend).

    Raises:
        UnsupportedByBackendError: On the SDF backend, if *faces* bound a non-convex solid.

    Returns:
        The solid, built by whichever backend is active.

    Examples:
        .. pythonscad-example::

            from pybosl2 import polyhedron

            points = [[0, 0, 0], [20, 0, 0], [10, 18, 0], [10, 6, 16]]
            faces = [[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]]
            polyhedron(points, faces).show()

    """
    return get_backend().polyhedron(points, faces, convexity=convexity)


def _require_operands(operation: str, solids: tuple[Solid, ...]) -> None:
    """Reject an n-ary boolean with nothing to combine.

    Args:
        operation: Name of the calling boolean, used in the message.
        solids: The operands as given.

    Raises:
        ValueError: If *solids* is empty.

    """
    if not solids:
        raise Bosl2ValueError(f"{operation}(): needs at least one solid to combine.")


def union(*solids: Solid) -> Solid:
    """Return the union of *solids* on the active backend.

    Args:
        solids: The shapes to combine; all must share a backend (SPEC C-1).

    Returns:
        One solid covering all of them.

    Raises:
        ValueError: If no solids are given.

    Examples:
        .. pythonscad-example::

            from pybosl2 import cuboid, cyl, union

            union(cuboid([20, 20, 10]), cyl(height=20, radius=5)).show()

    """
    _require_operands("union", solids)
    return get_backend().union(solids)


def difference(*solids: Solid) -> Solid:
    """Return the first solid minus the rest, on the active backend.

    Args:
        solids: The shape to cut from, then the shapes to remove.

    Returns:
        The first solid with the others carved out of it.

    Raises:
        ValueError: If no solids are given.

    Examples:
        .. pythonscad-example::

            from pybosl2 import cuboid, cyl, difference

            difference(cuboid([20, 20, 10]), cyl(height=30, radius=5)).show()

    """
    _require_operands("difference", solids)
    return get_backend().difference(solids)


def intersection(*solids: Solid) -> Solid:
    """Return the intersection of *solids* on the active backend.

    Args:
        solids: The shapes to intersect; all must share a backend.

    Returns:
        The solid covered by every one of them.

    Raises:
        ValueError: If no solids are given.

    Examples:
        .. pythonscad-example::

            from pybosl2 import cuboid, sphere, intersection

            intersection(cuboid([20, 20, 20]), sphere(radius=13)).show()

    """
    _require_operands("intersection", solids)
    return get_backend().intersection(solids)

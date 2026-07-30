# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""2-D turtle-graphics path builder.

Implements BOSL2's ``turtle()`` command language for generating 2-D paths.
All commands operate in the XY plane; z-coordinate operations raise a
:class:`ValueError`.

Shares the :class:`TurtleCommandType` and :class:`TurtleCommand` definitions
with :mod:`pybosl2.turtle3d` so that both turtles accept the same command set.
"""

# LibFile: pybosl2/turtle2d.py
# FileSummary: 2-D turtle-graphics path builder.
# FileGroup: BOSL2

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Literal, overload

import numpy as np

from pybosl2.geometry import general_line_intersection, line_normal
from pybosl2.path2d import Path2D
from pybosl2.shapes2d import _frag_count, arc
from pybosl2.turtle3d import TurtleCommand, TurtleCommandType
from pybosl2.vectors import unit

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import ArrayLike

__all__ = ["turtle", "Turtle2D", "TurtleState", "TurtleCommand", "TurtleCommandType"]

# -- commands that involve the z-axis and are therefore illegal in 2-D -------

_Z_AXIS_COMMANDS: frozenset[TurtleCommandType] = frozenset(
    {
        TurtleCommandType.ZMOVE,
        TurtleCommandType.ZJUMP,
        TurtleCommandType.UNTILZ,
        TurtleCommandType.UP,
        TurtleCommandType.DOWN,
        TurtleCommandType.ROLL,
        TurtleCommandType.XROT,
        TurtleCommandType.YROT,
        TurtleCommandType.XYZMOVE,
        TurtleCommandType.ARCUP,
        TurtleCommandType.ARCDOWN,
        TurtleCommandType.ARCXROT,
        TurtleCommandType.ARCYROT,
        TurtleCommandType.ARCTODIR,
        TurtleCommandType.ARCROT,
        TurtleCommandType.ROT,
    }
)

# -- helpers -----------------------------------------------------------------


def _rot2(deg: float, v: Sequence[float] | np.ndarray) -> np.ndarray:
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    x, y = float(v[0]), float(v[1])
    return np.array([c * x - s * y, s * x + c * y])


# -- TurtleState -------------------------------------------------------------


@dataclass
class TurtleState:
    """Immutable snapshot of the 2-D turtle's position, heading, and settings.

    Attributes:
        path: The list of 2-D points the turtle has visited, starting with the origin.
        step: The current step vector ``[dx, dy]`` controlling direction and length.
        angle: The default turn angle in degrees used when no explicit angle is given.
        arcsteps: The number of subdivisions for arc commands (0 means auto).
    """

    path: list[list[float]] = field(default_factory=lambda: [[0.0, 0.0]])
    step: list[float] = field(default_factory=lambda: [1.0, 0.0])
    angle: float = 90.0
    arcsteps: int = 0

    def __init__(
        self,
        state: TurtleState | Sequence[Any] | None = None,
        *,
        path: list[list[float]] | None = None,
        step: list[float] | None = None,
        angle: float | None = None,
        arcsteps: int | None = None,
    ) -> None:
        """Initialize turtle state from keyword fields or a legacy list.

        ``TurtleState()`` uses defaults. ``TurtleState(path=..., step=...)``
        sets individual fields. ``TurtleState(legacy_list)`` parses a legacy
        ``[path, step_vector, angle, arcsteps]`` list. Passing an existing
        ``TurtleState`` copies its fields.
        """
        if isinstance(state, TurtleState):
            s = state
        elif isinstance(state, (list, tuple)):
            seq = list(state)
            object.__setattr__(self, "path", [[float(p[0]), float(p[1])] for p in seq[0]])
            object.__setattr__(self, "step", [float(seq[1][0]), float(seq[1][1])])
            object.__setattr__(self, "angle", float(seq[2]))
            object.__setattr__(self, "arcsteps", int(seq[3]))
            return
        elif state is not None:
            raise TypeError(f"Expected TurtleState, Sequence, or None, got {type(state).__name__}")
        else:
            s = None

        object.__setattr__(self, "path", path if path is not None else (s.path if s else [[0.0, 0.0]]))
        object.__setattr__(self, "step", step if step is not None else (s.step if s else [1.0, 0.0]))
        object.__setattr__(self, "angle", angle if angle is not None else (s.angle if s else 90.0))
        object.__setattr__(self, "arcsteps", arcsteps if arcsteps is not None else (s.arcsteps if s else 0))

    def with_point(self, pt: ArrayLike) -> TurtleState:
        """Return a new state with *pt* appended to the path."""
        arr = np.asarray(pt, dtype=float)
        return replace(self, path=self.path + [[float(arr[0]), float(arr[1])]])

    def with_step(self, v: ArrayLike) -> TurtleState:
        """Return a new state with the step vector set to *v*."""
        arr = np.asarray(v, dtype=float)
        return replace(self, step=[float(arr[0]), float(arr[1])])

    def with_angle(self, a: float) -> TurtleState:
        """Return a new state with the default angle set to *a*."""
        return replace(self, angle=float(a))

    def with_arcsteps(self, n: int) -> TurtleState:
        """Return a new state with the arc-steps count set to *n*."""
        return replace(self, arcsteps=int(n))

    @property
    def lastpt(self) -> np.ndarray:
        """The most recent point on the path as a numpy array."""
        return np.asarray(self.path[-1], dtype=float)

    @property
    def step_arr(self) -> np.ndarray:
        """The step vector as a numpy array."""
        return np.asarray(self.step, dtype=float)


# -- Turtle2D class ----------------------------------------------------------


class Turtle2D:
    """A 2-D turtle: walk it with a command list to produce a 2-D path.

    The turtle starts at the origin pointing along +X with a step length of 1.
    Commands are a flat list of :class:`TurtleCommand` objects; use
    :meth:`parse_commands` to convert raw strings or aliases into the
    canonical form.

    The turtle's internal state is a :class:`TurtleState` instance accessible
    via :meth:`full_state`.

    Examples:
        A rounded-corner square:

        .. pythonscad-example::

            from pybosl2.turtle2d import Turtle2D
            from pybosl2.turtle3d import TurtleCommand, TurtleCommandType as TCT

            cmds = [
                TurtleCommand(TCT.MOVE, size=40),
                TurtleCommand(TCT.ARCLEFT, radius=8),
                TurtleCommand(TCT.MOVE, size=40),
                TurtleCommand(TCT.ARCLEFT, radius=8),
                TurtleCommand(TCT.MOVE, size=40),
                TurtleCommand(TCT.ARCLEFT, radius=8),
                TurtleCommand(TCT.MOVE, size=40),
                TurtleCommand(TCT.ARCLEFT, radius=8),
            ]
            path = Turtle2D().run(cmds).points()
            path.stroke(width=3, closed=True).linear_extrude(height=4).show()
    """

    def __init__(self, state: TurtleState | Sequence[Any] | None = None) -> None:
        self._state = TurtleState(state)

    def run(self, commands: Sequence[TurtleCommand], repeat: int = 1) -> Turtle2D:
        """Execute *commands* (optionally *repeat* times), advancing this turtle's state.

        Returns:
            self.
        """
        self._state = _run_commands(list(commands), self._state, repeat)
        return self

    def points(self) -> Path2D:
        """Return the path the turtle has traversed as a :class:`Path2D`."""
        return Path2D(self._state.path, closed=False)

    def full_state(self) -> TurtleState:
        """Return the turtle's internal :class:`TurtleState`."""
        return self._state

    @classmethod
    def parse_commands(
        cls,
        commands: Sequence[TurtleCommand],
    ) -> list[TurtleCommand]:
        """Resolve a sequence of :class:`TurtleCommand` objects into a flat list.

        Validates that no z-axis commands are present and returns the commands
        as a plain list. For raw string/enum input use :func:`turtle` which
        converts automatically.

        Args:
            commands: Pre-constructed :class:`TurtleCommand` objects.

        Returns:
            A flat list of :class:`TurtleCommand` objects.
        """
        cmds = list(commands)
        for i, cmd in enumerate(cmds):
            if cmd.cmd_type in _Z_AXIS_COMMANDS and not (
                cmd.cmd_type == TurtleCommandType.XYZMOVE and cmd.options.get("is_2d_vector")
            ):
                raise ValueError(
                    f'Turtle command "{cmd.cmd_type.value}" involves the z-axis and is not valid in 2-D at index {i}'
                )
        return cmds

    @overload
    @classmethod
    def turtle2d(
        cls,
        commands: Sequence[TurtleCommand],
        *,
        state: TurtleState | Sequence[Any] | None = None,
        full_state: Literal[False] = False,
        repeat: int = 1,
    ) -> Path2D: ...
    @overload
    @classmethod
    def turtle2d(
        cls,
        commands: Sequence[TurtleCommand],
        *,
        state: TurtleState | Sequence[Any] | None = None,
        full_state: Literal[True],
        repeat: int = 1,
    ) -> TurtleState: ...
    @classmethod
    def turtle2d(
        cls,
        commands: Sequence[TurtleCommand],
        *,
        state: TurtleState | Sequence[Any] | None = None,
        full_state: bool = False,
        repeat: int = 1,
    ) -> Path2D | TurtleState:
        """One-shot: run *commands* from *state* and return points (default) or the *full_state*.

        Examples:
            A rounded-corner square drawn with arcs:

            .. pythonscad-example::

                path = Turtle2D.turtle2d([
                    TurtleCommand(TurtleCommandType.MOVE, size=40),
                    TurtleCommand(TurtleCommandType.ARCLEFT, radius=8),
                    TurtleCommand(TurtleCommandType.MOVE, size=40),
                    TurtleCommand(TurtleCommandType.ARCLEFT, radius=8),
                    TurtleCommand(TurtleCommandType.MOVE, size=40),
                    TurtleCommand(TurtleCommandType.ARCLEFT, radius=8),
                    TurtleCommand(TurtleCommandType.MOVE, size=40),
                    TurtleCommand(TurtleCommandType.ARCLEFT, radius=8),
                ])
                path.stroke(width=3, closed=True).linear_extrude(height=4).show()
        """
        t = cls(state).run(commands, repeat)
        if full_state:
            return t.full_state()
        return t.points()


# -- convenience function ----------------------------------------------------


@overload
def turtle(
    commands: Sequence[TurtleCommand],
    state: TurtleState | Sequence[Any] | None = None,
    *,
    full_state: Literal[False] = False,
    repeat: int = 1,
) -> Path2D: ...
@overload
def turtle(
    commands: Sequence[TurtleCommand],
    state: TurtleState | Sequence[Any] | None = None,
    *,
    full_state: Literal[True],
    repeat: int = 1,
) -> TurtleState: ...
def turtle(
    commands: Sequence[TurtleCommand],
    state: TurtleState | Sequence[Any] | None = None,
    full_state: bool = False,
    repeat: int = 1,
) -> Path2D | TurtleState:
    """Build a 2-D path from :class:`TurtleCommand` objects — BOSL2's ``turtle()``.

    *commands* is a flat list of :class:`TurtleCommand` objects. The turtle
    starts at the origin pointing along +X with a step length of 1. By default
    the computed path is returned as a :class:`~pybosl2.paths.Path2D`; set
    *full_state* to get a :class:`TurtleState` instead. *repeat* runs the whole
    command list that many times.

    Examples:
        A rounded-corner square drawn with arcs:

        .. pythonscad-example::

            from pybosl2.turtle2d import turtle
            from pybosl2.turtle3d import TurtleCommand, TurtleCommandType as TCT

            path = turtle([
                TurtleCommand(TCT.MOVE, size=40),
                TurtleCommand(TCT.ARCLEFT, radius=8),
                TurtleCommand(TCT.MOVE, size=40),
                TurtleCommand(TCT.ARCLEFT, radius=8),
                TurtleCommand(TCT.MOVE, size=40),
                TurtleCommand(TCT.ARCLEFT, radius=8),
                TurtleCommand(TCT.MOVE, size=40),
                TurtleCommand(TCT.ARCLEFT, radius=8),
            ])
            path.stroke(width=3, closed=True).linear_extrude(height=4).show()
    """
    cmds = Turtle2D.parse_commands(commands)
    if full_state:
        return Turtle2D.turtle2d(cmds, state=state, full_state=True, repeat=repeat)
    return Turtle2D.turtle2d(cmds, state=state, repeat=repeat)


# -- command execution (internal) --------------------------------------------


def _run_commands(
    commands: list[TurtleCommand],
    state: TurtleState,
    repeat: int,
) -> TurtleState:
    for _ in range(int(repeat)):
        for idx, cmd in enumerate(commands):
            state = _command(cmd, state, idx)
    return state


def _command(cmd: TurtleCommand, state: TurtleState, index: int) -> TurtleState:
    """Execute a single :class:`TurtleCommand` in 2-D space.

    Raises:
        ValueError: If *cmd* involves the z-axis or is an unknown command.
    """
    if cmd.cmd_type in _Z_AXIS_COMMANDS:
        if cmd.cmd_type == TurtleCommandType.XYZMOVE and cmd.options.get("is_2d_vector"):
            return _xymove(cmd.parm, state, index)

        raise ValueError(
            f'Turtle command "{cmd.cmd_type.value}" involves the z-axis and is not valid in 2-D at index {index}'
        )

    if cmd.cmd_type == TurtleCommandType.REPEAT:
        sub_cmds: list[TurtleCommand] = cmd.options.get("commands", [])
        return _run_commands(sub_cmds, state, int(cmd.size))

    if cmd.is_compound:
        return _compound(cmd, state, index)

    lastpt = state.lastpt
    step = state.step_arr
    parm = cmd.parm
    p = parm if isinstance(parm, (int, float)) else None

    if cmd.cmd_type == TurtleCommandType.MOVE:
        return state.with_point((p if p is not None else 1) * step + lastpt)
    if cmd.cmd_type == TurtleCommandType.XMOVE:
        return state.with_point(
            (p if p is not None else 1) * np.linalg.norm(step) * np.array([1.0, 0.0]) + lastpt,
        )
    if cmd.cmd_type == TurtleCommandType.YMOVE:
        return state.with_point(
            (p if p is not None else 1) * np.linalg.norm(step) * np.array([0.0, 1.0]) + lastpt,
        )
    if cmd.cmd_type == TurtleCommandType.JUMP:
        return state.with_point([float(parm[0]), float(parm[1])])
    if cmd.cmd_type == TurtleCommandType.XJUMP:
        return state.with_point([float(parm), float(lastpt[1])])
    if cmd.cmd_type == TurtleCommandType.YJUMP:
        return state.with_point([float(lastpt[0]), float(parm)])
    if cmd.cmd_type == TurtleCommandType.UNTILX:
        res = general_line_intersection([lastpt, lastpt + step], [[parm, 0], [parm, 1]])
        if res is None:
            raise ValueError(f'"untilx" never reaches the goal at index {index}')
        return state.with_point([float(res[0][0]), float(res[0][1])])
    if cmd.cmd_type == TurtleCommandType.UNTILY:
        res = general_line_intersection([lastpt, lastpt + step], [[0, parm], [1, parm]])
        if res is None:
            raise ValueError(f'"untily" never reaches the goal at index {index}')
        return state.with_point([float(res[0][0]), float(res[0][1])])
    if cmd.cmd_type == TurtleCommandType.LEFT:
        return state.with_step(_rot2(p if p is not None else state.angle, step))
    if cmd.cmd_type == TurtleCommandType.RIGHT:
        return state.with_step(_rot2(-(p if p is not None else state.angle), step))
    if cmd.cmd_type == TurtleCommandType.ZROT:
        ang = p if p is not None else state.angle
        norm = float(np.linalg.norm(step))
        return state.with_step(
            norm * np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))]),
        )
    if cmd.cmd_type == TurtleCommandType.ANGLE:
        return state.with_angle(float(parm))
    if cmd.cmd_type == TurtleCommandType.SETDIR:
        if isinstance(parm, (list, tuple, np.ndarray)):
            v = np.asarray(parm, dtype=float)
            if len(v) >= 3 and abs(float(v[2])) > 1e-12:
                raise ValueError(f'"setdir" z-component must be 0 for 2-D turtle at index {index}')
            return state.with_step(np.linalg.norm(step) * unit([float(v[0]), float(v[1])]))
        return state.with_step(
            np.linalg.norm(step) * np.array([math.cos(math.radians(float(parm))), math.sin(math.radians(float(parm)))]),
        )
    if cmd.cmd_type == TurtleCommandType.LENGTH:
        return state.with_step(float(parm) * unit(step))
    if cmd.cmd_type == TurtleCommandType.SCALE:
        return state.with_step(float(parm) * step)
    if cmd.cmd_type == TurtleCommandType.ADDLENGTH:
        return state.with_step(step + unit(step) * float(parm))
    if cmd.cmd_type == TurtleCommandType.ARCSTEPS:
        return state.with_arcsteps(int(parm))
    if cmd.cmd_type in (TurtleCommandType.ARCLEFT, TurtleCommandType.ARCRIGHT):
        return _arc(cmd, cmd.options.get("absolute_arc_angle", False), state, index)
    if cmd.cmd_type == TurtleCommandType.ARCZROT:
        return _arczrot(cmd, state, index)

    raise ValueError(f'Unknown turtle command "{cmd.cmd_type.value}" at index {index}')


# -- 2-D specific commands ---------------------------------------------------


def _xymove(parm: Any, state: TurtleState, index: int) -> TurtleState:
    """Handle the ``xymove`` command (2-D vector move)."""
    lastpt = state.lastpt
    v = np.atleast_1d(np.asarray(parm, dtype=float))
    if len(v) >= 3 and abs(float(v[2])) > 1e-12:
        raise ValueError(f'"xymove" z-component must be 0 for 2-D turtle at index {index}')
    return state.with_point(lastpt + np.array([float(v[0]), float(v[1])]))


# -- arc handling ------------------------------------------------------------


def _arc(
    cmd: TurtleCommand,
    absolute_angle: bool,
    state: TurtleState,
    index: int,
) -> TurtleState:
    """Execute an arc command (arcleft / arcright / arcleftto / arcrightto) in 2-D."""
    parm = cmd.parm
    parm2 = cmd.parm2
    assert isinstance(parm, (int, float)), f'"{cmd.cmd_type.value}" needs a numeric radius at index {index}'

    lastpt = state.lastpt
    step = state.step_arr
    lrsign = 1 if cmd.cmd_type == TurtleCommandType.ARCLEFT else -1
    steps = _frag_count(abs(parm)) if state.arcsteps == 0 else int(state.arcsteps)

    if not absolute_angle:
        myangle = parm2 if isinstance(parm2, (int, float)) else state.angle
        radius = parm * (1 if myangle >= 0 else -1)
        center = lastpt + lrsign * radius * line_normal([0, 0], step)
        turn = math.copysign(1, parm) * lrsign * myangle
        rot_step = _rot2(lrsign * myangle, step)
    else:
        assert isinstance(parm2, (int, float)), f'"{cmd.cmd_type.value}" needs a numeric angle at index {index}'
        radius = parm
        center = lastpt + lrsign * radius * line_normal([0, 0], step)
        start_angle = math.degrees(math.atan2(step[1], step[0])) % 360
        end_angle = float(parm2) % 360
        if lrsign * end_angle < lrsign * start_angle:
            end_angle = end_angle + lrsign * 360
        delta = -start_angle + end_angle
        turn = math.copysign(1, radius) * delta
        rot_step = _rot2(delta, step)

    if turn == 0 or radius == 0:
        arcpath: list[list[float]] = []
    else:
        p_mid = _rot2(turn / 2, lastpt - center) + center
        p_end = _rot2(turn, lastpt - center) + center
        points_2d: list[list[float]] = [
            [float(v) for v in lastpt],
            [float(v) for v in p_mid],
            [float(v) for v in p_end],
        ]
        arcpath = list(arc(steps, points=points_2d))[1:]

    new_path = state.path + [[float(p[0]), float(p[1])] for p in arcpath]
    return replace(state, path=new_path, step=[float(rot_step[0]), float(rot_step[1])])


def _arczrot(cmd: TurtleCommand, state: TurtleState, index: int) -> TurtleState:
    """Execute an ``arczrot`` command: arc with absolute Z rotation in 2-D.

    The arc is swept in the XY plane; *radius* comes from ``cmd.parm`` and
    *angle* from ``cmd.parm2`` (defaulting to the stored angle).
    """
    parm = cmd.parm
    parm2 = cmd.parm2
    assert isinstance(parm, (int, float)), f'"arczrot" needs a numeric radius at index {index}'

    lastpt = state.lastpt
    step = state.step_arr
    myangle = parm2 if isinstance(parm2, (int, float)) else state.angle
    lrsign = 1 if myangle >= 0 else -1
    radius = abs(parm)
    steps = _frag_count(radius) if state.arcsteps == 0 else int(state.arcsteps)

    center = lastpt + lrsign * radius * line_normal([0, 0], step)
    turn = lrsign * abs(myangle)
    rot_step = _rot2(turn, step)

    if turn == 0 or radius == 0:
        arcpath: list[list[float]] = []
    else:
        p_mid = _rot2(turn / 2, lastpt - center) + center
        p_end = _rot2(turn, lastpt - center) + center
        points_2d: list[list[float]] = [
            [float(v) for v in lastpt],
            [float(v) for v in p_mid],
            [float(v) for v in p_end],
        ]
        arcpath = list(arc(steps, points=points_2d))[1:]

    new_path = state.path + [[float(p[0]), float(p[1])] for p in arcpath]
    return replace(state, path=new_path, step=[float(rot_step[0]), float(rot_step[1])])


# -- compound commands -------------------------------------------------------


def _compound(cmd: TurtleCommand, state: TurtleState, index: int) -> TurtleState:
    """Execute a compound turtle command (``["move"|"arc", ...]``) in 2-D.

    Rejects z-axis sub-commands and handles 2-D-safe sub-commands
    (``steps``, ``reverse`` for ``move``; ``left``/``right``/``zrot`` for ``arc``).
    """
    legacy = cmd.to_legacy_compound()
    head = legacy[0]
    keys: dict[str, Any] = {}
    for j in range(0, len(legacy), 2):
        keys[legacy[j]] = legacy[j + 1]

    lastpt = state.lastpt
    step = state.step_arr
    movescale = float(np.linalg.norm(step))

    z_sub = {
        "up",
        "down",
        "xrot",
        "yrot",
        "roll",
        "rollto",
        "rrollto",
        "lrollto",
        "todir",
        "rot",
        "grow",
        "shrink",
        "twist",
    }
    offending = z_sub & set(keys)
    if offending:
        raise ValueError(f"Compound turtle command contains z-axis sub-commands {sorted(offending)} at index {index}")

    reverse = keys.get("reverse", False) if isinstance(keys.get("reverse"), bool) else bool(keys.get("reverse", False))
    usersteps = int(keys.get("steps", 1)) if "steps" not in z_sub else 1

    if head == "move":
        move = movescale * (keys.get("move", 0) or 0)
        flip = -1 if reverse else 1
        for n in range(1, usersteps + 1):
            frac = n / usersteps
            pt = lastpt + flip * frac * move * step
            state = state.with_point(pt)
        return state

    if head == "arc":
        radius = movescale * (keys.get("arc", 0) or 0)
        assert radius != 0, f'"arc" compound needs a non-zero radius at index {index}'

        right = keys.get("right", 0)
        left_ = keys.get("left", 0)
        zrot = keys.get("zrot", 0)

        if zrot != 0:
            myangle = float(zrot)
            assert myangle != 0, f'"arc" with zrot needs a non-zero angle at index {index}'
            lrsign = 1 if myangle >= 0 else -1
            turn = lrsign * abs(myangle)
            center = lastpt + lrsign * abs(radius) * line_normal([0, 0], step)
        elif left_ != 0 or right != 0:
            myangle = left_ - right
            assert myangle != 0, f'"arc" with left/right needs a non-zero angle at index {index}'
            lrsign = 1 if myangle >= 0 else -1
            turn = lrsign * abs(myangle)
            center = lastpt + lrsign * abs(radius) * line_normal([0, 0], step)
        else:
            raise ValueError(f'"arc" compound command needs a rotation sub-command at index {index}')

        steps_count = max(2, _frag_count(abs(radius))) if state.arcsteps == 0 else int(state.arcsteps)
        if usersteps != 1:
            steps_count = usersteps

        rot_step = _rot2(turn, step)
        for n in range(1, steps_count + 1):
            frac = n / steps_count
            if reverse:
                pt = _rot2(-frac * turn, lastpt - center) + center
            else:
                pt = _rot2(frac * turn, lastpt - center) + center
            state = state.with_point(pt)

        return replace(state, step=[float(rot_step[0]), float(rot_step[1])])

    raise ValueError(f'Unknown compound command head "{head}" at index {index}')

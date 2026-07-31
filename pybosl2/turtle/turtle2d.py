# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""2-D turtle-graphics path builder.

Implements BOSL2's ``turtle2d()`` command language for generating 2-D paths.
All commands operate in the XY plane; z-coordinate operations raise a
:class:`ValueError`.

Shares the :class:`TurtleCommandType` and :class:`TurtleCommand` definitions
with :mod:`pybosl2.turtle3d` so that both turtles accept the same command set.
"""

# LibFile: pybosl2/turtle2d.py
# FileSummary: 2-D turtle-graphics path builder.
# DocCategory: internal
# FileGroup: BOSL2

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

import numpy as np

from pybosl2.geometry import general_line_intersection, line_normal
from pybosl2.path2d import Path2D
from pybosl2.points import Point
from pybosl2.shapes2d import _frag_count, arc
from pybosl2.vectors import unit

from .turtle3d import TurtleCommand, TurtleCommandType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import ArrayLike

__all__ = ["turtle2d", "Turtle2D", "Turtle2DState", "TurtleCommand", "TurtleCommandType"]

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


# -- Turtle2DState -------------------------------------------------------------


@dataclass
class Turtle2DState:
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

    def with_point(self, pt: ArrayLike) -> Turtle2DState:
        """Return a new state with *pt* appended to the path."""
        arr = np.asarray(pt, dtype=float)
        return replace(self, path=self.path + [[float(arr[0]), float(arr[1])]])

    def with_step(self, v: ArrayLike) -> Turtle2DState:
        """Return a new state with the step vector set to *v*."""
        arr = np.asarray(v, dtype=float)
        return replace(self, step=[float(arr[0]), float(arr[1])])

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
        The turtle's internal state is a :class:`Turtle2DState` instance accessible
        via :meth:`full_state`.

        Examples:
            A rounded-corner square:

            .. pythonscad-example::

                from pybosl2.turtle2d import Turtle2D
                from pybosl2.points import Point
    from pybosl2.turtle3d import TurtleCommand, TurtleCommandType as Tct

                cmds = [
                    TurtleCommand(Tct.MOVE, size=40),
                    TurtleCommand(Tct.ARCLEFT, radius=8),
                    TurtleCommand(Tct.MOVE, size=40),
                    TurtleCommand(Tct.ARCLEFT, radius=8),
                    TurtleCommand(Tct.MOVE, size=40),
                    TurtleCommand(Tct.ARCLEFT, radius=8),
                    TurtleCommand(Tct.MOVE, size=40),
                    TurtleCommand(Tct.ARCLEFT, radius=8),
                ]
                path = Turtle2D().run(cmds).points()
                path.stroke(width=3, closed=True).linear_extrude(height=4).show()
    """

    def __init__(self, state: Turtle2DState | None = None) -> None:
        self._state = state if state is not None else Turtle2DState()

    # -- public API ----------------------------------------------------------

    def run(self, commands: Sequence[TurtleCommand], repeat: int = 1) -> Turtle2D:
        """Execute *commands* (optionally *repeat* times), advancing this turtle's state.

        Returns:
            self.
        """
        for _ in range(int(repeat)):
            for idx, cmd in enumerate(commands):
                self._command(cmd, idx)
        return self

    def points(self) -> Path2D:
        """Return the path the turtle has traversed as a :class:`Path2D`."""
        return Path2D(self._state.path, closed=False)

    def full_state(self) -> Turtle2DState:
        """Return the turtle's internal :class:`Turtle2DState`."""
        return self._state

    # -- command dispatch ----------------------------------------------------

    def _command(self, cmd: TurtleCommand, index: int) -> None:
        """Execute a single :class:`TurtleCommand`, mutating ``self._state``.

        Raises:
            ValueError: If *cmd* involves the z-axis or is an unknown command.
        """
        if cmd.cmd_type in _Z_AXIS_COMMANDS:
            if cmd.cmd_type == TurtleCommandType.XYZMOVE:
                self._xymove(cmd.size, index)
                return
            raise ValueError(
                f'Turtle command "{cmd.cmd_type.value}" involves the z-axis and is not valid in 2-D at index {index}'
            )

        if cmd.cmd_type == TurtleCommandType.REPEAT:
            sub_cmds: list[TurtleCommand] = cmd.sub_commands or []
            for _ in range(int(self._n(cmd.size))):
                for si, sc in enumerate(sub_cmds):
                    self._command(sc, si)
            return

        if cmd.is_compound:
            self._compound(cmd, index)
            return

        ct = cmd.cmd_type
        lastpt = self._state.lastpt
        step = self._state.step_arr
        size = self._n(cmd.size)
        ang = cmd.angle if isinstance(cmd.angle, (int, float)) else None

        if ct == TurtleCommandType.MOVE:
            self._state = self._state.with_point((size or 1.0) * step + lastpt)
        elif ct == TurtleCommandType.XMOVE:
            self._state = self._state.with_point(
                (size or 1.0) * np.linalg.norm(step) * np.array([1.0, 0.0]) + lastpt,
            )
        elif ct == TurtleCommandType.YMOVE:
            self._state = self._state.with_point(
                (size or 1.0) * np.linalg.norm(step) * np.array([0.0, 1.0]) + lastpt,
            )
        elif ct == TurtleCommandType.JUMP:
            px, py, _ = self._xyz(cmd.size)
            self._state = self._state.with_point([px, py])
        elif ct == TurtleCommandType.XJUMP:
            self._state = self._state.with_point([self._n(cmd.size, float(lastpt[1])), float(lastpt[1])])
        elif ct == TurtleCommandType.YJUMP:
            self._state = self._state.with_point([float(lastpt[0]), self._n(cmd.size, float(lastpt[0]))])
        elif ct == TurtleCommandType.UNTILX:
            res = general_line_intersection(
                (
                    Point(float(lastpt[0]), float(lastpt[1])),
                    Point(float(lastpt[0] + step[0]), float(lastpt[1] + step[1])),
                ),
                (Point(self._n(cmd.size), 0), Point(self._n(cmd.size), 1)),
            )
            if res is None:
                raise ValueError(f'"untilx" never reaches the goal at index {index}')
            self._state = self._state.with_point([res[0].x, res[0].y])
        elif ct == TurtleCommandType.UNTILY:
            res = general_line_intersection(
                (
                    Point(float(lastpt[0]), float(lastpt[1])),
                    Point(float(lastpt[0] + step[0]), float(lastpt[1] + step[1])),
                ),
                (Point(0, self._n(cmd.size)), Point(1, self._n(cmd.size))),
            )
            if res is None:
                raise ValueError(f'"untily" never reaches the goal at index {index}')
            self._state = self._state.with_point([res[0].x, res[0].y])
        elif ct == TurtleCommandType.LEFT:
            self._state = self._state.with_step(_rot2(ang if ang is not None else self._state.angle, step))
        elif ct == TurtleCommandType.RIGHT:
            self._state = self._state.with_step(_rot2(-(ang if ang is not None else self._state.angle), step))
        elif ct == TurtleCommandType.ZROT:
            a = ang if ang is not None else self._state.angle
            norm = float(np.linalg.norm(step))
            self._state = self._state.with_step(
                norm * np.array([math.cos(math.radians(a)), math.sin(math.radians(a))]),
            )
        elif ct == TurtleCommandType.ANGLE:
            self._state = replace(self._state, angle=self._n(cmd.size, self._state.angle))
        elif ct == TurtleCommandType.SETDIR:
            if isinstance(cmd.size, (Point, list, tuple, np.ndarray)):
                v = np.asarray(cmd.size, dtype=float)
                if len(v) >= 3 and abs(float(v[2])) > 1e-12:
                    raise ValueError(f'"setdir" z-component must be 0 for 2-D turtle at index {index}')
                self._state = self._state.with_step(np.linalg.norm(step) * unit([float(v[0]), float(v[1])]))
            else:
                self._state = self._state.with_step(
                    np.linalg.norm(step)
                    * np.array([math.cos(math.radians(self._n(cmd.size))), math.sin(math.radians(self._n(cmd.size)))]),
                )
        elif ct == TurtleCommandType.LENGTH:
            self._state = self._state.with_step(self._n(cmd.size, 1.0) * unit(step))
        elif ct == TurtleCommandType.SCALE:
            self._state = self._state.with_step(self._n(cmd.size, 1.0) * step)
        elif ct == TurtleCommandType.ADDLENGTH:
            self._state = self._state.with_step(step + unit(step) * self._n(cmd.size, 1.0))
        elif ct == TurtleCommandType.ARCSTEPS:
            self._state = replace(self._state, arcsteps=int(self._n(cmd.size)))
        elif ct in (TurtleCommandType.ARCLEFT, TurtleCommandType.ARCRIGHT):
            self._arc(cmd, False, index)
        elif ct == TurtleCommandType.ARCZROT:
            self._arczrot(cmd, index)
        else:
            raise ValueError(f'Unknown turtle command "{ct.value}" at index {index}')

    # -- 2-D specific commands -----------------------------------------------

    @staticmethod
    @staticmethod
    def _n(sz: float | Point | None, default: float = 0.0) -> float:
        if sz is None:
            return default
        if isinstance(sz, (int, float)):
            return float(sz)
        return sz.x

    @staticmethod
    def _xyz(sz: float | Point | None) -> tuple[float, float, float]:
        if sz is None:
            return (0.0, 0.0, 0.0)
        if isinstance(sz, (int, float)):
            return (float(sz), 0.0, 0.0)
        return (sz.x, sz.y, sz.z or 0.0)

    def _xymove(self, parm: Any, index: int) -> None:
        """Handle the ``xymove`` command (2-D vector move)."""
        lastpt = self._state.lastpt
        v = np.atleast_1d(np.asarray(parm, dtype=float))
        if len(v) >= 3 and abs(float(v[2])) > 1e-12:
            raise ValueError(f'"xymove" z-component must be 0 for 2-D turtle at index {index}')
        self._state = self._state.with_point(lastpt + np.array([float(v[0]), float(v[1])]))

    # -- arc handling --------------------------------------------------------

    def _arc(
        self,
        cmd: TurtleCommand,
        absolute_angle: bool,
        index: int,
    ) -> None:
        """Execute an arc command (arcleft / arcright / arcleftto / arcrightto) in 2-D."""
        radius_val = cmd.radius
        assert isinstance(radius_val, (int, float)), f'"{cmd.cmd_type.value}" needs a numeric radius at index {index}'

        lastpt = self._state.lastpt
        step = self._state.step_arr
        lrsign = 1 if cmd.cmd_type == TurtleCommandType.ARCLEFT else -1
        steps = _frag_count(abs(radius_val)) if self._state.arcsteps == 0 else int(self._state.arcsteps)

        if not absolute_angle:
            myangle = cmd.angle if isinstance(cmd.angle, (int, float)) else self._state.angle
            radius = radius_val * (1 if myangle >= 0 else -1)
            center = lastpt + lrsign * radius * line_normal(Point(0.0, 0.0), Point(float(step[0]), float(step[1])))
            turn = math.copysign(1, radius_val) * lrsign * myangle
            rot_step = _rot2(lrsign * myangle, step)
        else:
            assert isinstance(cmd.angle, (int, float)), f'"{cmd.cmd_type.value}" needs a numeric angle at index {index}'
            radius = radius_val
            center = lastpt + lrsign * radius * line_normal(Point(0.0, 0.0), Point(float(step[0]), float(step[1])))
            start_angle = math.degrees(math.atan2(step[1], step[0])) % 360
            end_angle = float(cmd.angle) % 360
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

        new_path = self._state.path + [[float(p[0]), float(p[1])] for p in arcpath]
        self._state = replace(self._state, path=new_path, step=[float(rot_step[0]), float(rot_step[1])])

    def _arczrot(self, cmd: TurtleCommand, index: int) -> None:
        """Execute an ``arczrot`` command: arc with absolute Z rotation in 2-D.

        The arc is swept in the XY plane; *radius* comes from ``cmd.radius`` and
        *angle* from ``cmd.angle`` (defaulting to the stored angle).
        """
        radius_val = cmd.radius
        assert isinstance(radius_val, (int, float)), f'"arczrot" needs a numeric radius at index {index}'

        lastpt = self._state.lastpt
        step = self._state.step_arr
        myangle = cmd.angle if isinstance(cmd.angle, (int, float)) else self._state.angle
        lrsign = 1 if myangle >= 0 else -1
        radius = abs(radius_val)
        steps = _frag_count(radius) if self._state.arcsteps == 0 else int(self._state.arcsteps)

        center = lastpt + lrsign * radius * line_normal(Point(0.0, 0.0), Point(float(step[0]), float(step[1])))
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

        new_path = self._state.path + [[float(p[0]), float(p[1])] for p in arcpath]
        self._state = replace(self._state, path=new_path, step=[float(rot_step[0]), float(rot_step[1])])

    # -- compound commands ---------------------------------------------------

    def _compound(self, cmd: TurtleCommand, index: int) -> None:
        """Execute a compound turtle command using :class:`TurtleCommand` fields directly.

        Rejects z-axis sub-commands and handles 2-D-safe sub-commands
        (``steps``, ``reverse`` for ``move``; ``left``/``right``/``zrot`` for ``arc``).
        """
        lastpt = self._state.lastpt
        step = self._state.step_arr
        movescale = float(np.linalg.norm(step))

        if cmd.rotation_type in (
            TurtleCommand.RotationType.UP,
            TurtleCommand.RotationType.DOWN,
            TurtleCommand.RotationType.XROT,
            TurtleCommand.RotationType.YROT,
        ):
            raise ValueError(
                f'Compound turtle command contains z-axis sub-command "{cmd.rotation_type.value}" at index {index}'
            )
        if (
            cmd.grow is not None
            or cmd.shrink is not None
            or cmd.twist is not None
            or cmd.roll is not None
            or cmd.rollto is not None
            or cmd.rrollto is not None
            or cmd.lrollto is not None
        ):
            raise ValueError(f"Compound turtle command contains z-axis sub-commands at index {index}")

        reverse = cmd.reverse
        usersteps = cmd.steps or 1

        if cmd.cmd_type == TurtleCommandType.MOVE:
            move = movescale * (cmd.size if isinstance(cmd.size, (int, float)) else 0)
            flip = -1 if reverse else 1
            for n in range(1, usersteps + 1):
                frac = n / usersteps
                pt = lastpt + flip * frac * move * step
                self._state = self._state.with_point(pt)

        elif cmd.cmd_type == TurtleCommandType.ARC:
            radius = movescale * (cmd.radius if isinstance(cmd.radius, (int, float)) else 0)
            assert radius != 0, f'"arc" compound needs a non-zero radius at index {index}'

            angle = cmd.angle if isinstance(cmd.angle, (int, float)) else 0
            assert angle != 0, f'"arc" compound needs a non-zero rotation angle at index {index}'

            lrsign = 1 if angle >= 0 else -1
            turn = lrsign * abs(angle)
            center = lastpt + lrsign * abs(radius) * line_normal(Point(0.0, 0.0), Point(float(step[0]), float(step[1])))

            steps_count = max(2, _frag_count(abs(radius))) if self._state.arcsteps == 0 else int(self._state.arcsteps)
            if usersteps != 1:
                steps_count = usersteps

            rot_step = _rot2(turn, step)
            for n in range(1, steps_count + 1):
                frac = n / steps_count
                if reverse:
                    pt = _rot2(-frac * turn, lastpt - center) + center
                else:
                    pt = _rot2(frac * turn, lastpt - center) + center
                self._state = self._state.with_point(pt)

            self._state = replace(self._state, step=[float(rot_step[0]), float(rot_step[1])])

        else:
            raise ValueError(f'Unknown compound command head "{cmd.cmd_type.value}" at index {index}')


# -- turtle2d function --------------------------------------------------------


def turtle2d(
    commands: Sequence[TurtleCommand],
    state: Turtle2DState | None = None,
    repeat: int = 1,
) -> Turtle2D:
    """Build a 2-D path from :class:`TurtleCommand` objects — BOSL2's ``turtle2d()``.

        Creates a :class:`Turtle2D`, runs *commands* (optionally *repeat* times),
        and returns the turtle. Access the path via :meth:`Turtle2D.points` or
        the state via :meth:`Turtle2D.full_state`.

        Args:
            commands: A flat list of :class:`TurtleCommand` objects.
            state: Optional starting :class:`Turtle2DState`.
            repeat: Number of times to repeat the command list.

        Returns:
            The :class:`Turtle2D` instance after executing all commands.

        Examples:
            A rounded-corner square drawn with arcs:

            .. pythonscad-example::

                from pybosl2.turtle2d import turtle2d
                from pybosl2.points import Point
    from pybosl2.turtle3d import TurtleCommand, TurtleCommandType as Tct

                path = turtle2d([
                    TurtleCommand(Tct.MOVE, size=40),
                    TurtleCommand(Tct.ARCLEFT, radius=8),
                    TurtleCommand(Tct.MOVE, size=40),
                    TurtleCommand(Tct.ARCLEFT, radius=8),
                    TurtleCommand(Tct.MOVE, size=40),
                    TurtleCommand(Tct.ARCLEFT, radius=8),
                    TurtleCommand(Tct.MOVE, size=40),
                    TurtleCommand(Tct.ARCLEFT, radius=8),
                ]).points()
                path.stroke(width=3, closed=True).linear_extrude(height=4).show()
    """
    return Turtle2D(state).run(commands, repeat)

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""2-D turtle-graphics path builder.

Implements BOSL2's ``turtle()`` command language for generating 2-D paths.
All commands operate in the XY plane; z-coordinate operations raise a
:class:`ValueError`.
"""

# LibFile: pybosl2/turtle2d.py
# FileSummary: 2-D turtle-graphics path builder.
# FileGroup: BOSL2

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from pybosl2.geometry import general_line_intersection, line_normal
from pybosl2.path2d import Path2D
from pybosl2.shapes2d import _frag_count, arc
from pybosl2.vectors import unit

if TYPE_CHECKING:
    from collections.abc import Sequence

_TURTLE_TWO_ARG = ("arcleft", "arcright", "arcleftto", "arcrightto")


def _rot2(deg: float, v: "Sequence[float] | np.ndarray") -> np.ndarray:
    """Rotate the 2-D vector *v* by *deg* degrees about the origin."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    x, y = float(v[0]), float(v[1])
    return np.array([c * x - s * y, s * x + c * y])


def _rot_pts(deg: float, pts):
    """Rotate a list of 2-D points by *deg* degrees about the origin."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [[c * p[0] - s * p[1], s * p[0] + c * p[1]] for p in pts]


__all__ = ["turtle"]


def turtle(
    commands: Sequence,
    state: Sequence | None = None,
    full_state: bool = False,
    repeat: int = 1,
) -> Path2D | list:
    """Build a 2-D path from [turtle-graphics](https://en.wikipedia.org/wiki/Turtle_graphics)
    *commands* -- BOSL2's ``turtle()``.

    *commands* is a flat list of command names each optionally followed by a parameter, e.g.
    ``["move", 10, "left", 90, "move", 10]``. The turtle starts at the origin pointing along +X
    with a step length of 1. By default the computed path is returned as a
    :class:`~pybosl2.paths.Path2D`; set *full_state* to get ``[path, step_vector, angle, arcsteps]``
    instead. *repeat* runs the whole command list that many times.

    Supported commands: ``move``/``xmove``/``ymove``/``xymove``, ``jump``/``xjump``/``yjump``,
    ``untilx``/``untily``, ``left``/``turn``/``right``, ``angle``, ``setdir``, ``length``/
    ``scale``/``addlength``, ``arcsteps``, ``arcleft``/``arcright``, ``arcleftto``/``arcrightto``,
    and ``repeat`` (``["repeat", count, [subcommands]]``).

    Examples:
        A rounded-corner square drawn with arcs:

        .. pythonscad-example::

            path = turtle(["move", 40, "arcleft", 8, "move", 40, "arcleft", 8,
                           "move", 40, "arcleft", 8, "move", 40, "arcleft", 8])
            path.stroke(width=3, closed=True).linear_extrude(height=4).show()
    """
    state = [[[0.0, 0.0]], [1.0, 0.0], 90.0, 0.0] if state is None else list(state)
    result = _turtle_repeat(list(commands), state, True, repeat)
    return result if full_state else Path2D(result[0], closed=False)


def _turtle_repeat(commands, state, full_state, repeat):
    for _ in range(int(repeat)):
        state = _turtle(commands, state)
    return state if full_state else state[0]


def _turtle_command_len(commands, index) -> int:
    if commands[index] == "repeat":
        return 3
    if commands[index] in _TURTLE_TWO_ARG and len(commands) > index + 2 and not isinstance(commands[index + 2], str):
        return 3
    if index + 1 < len(commands) and isinstance(commands[index + 1], str):
        return 1
    if index + 1 >= len(commands):
        return 1
    return 2


def _turtle(commands, state, index: int = 0):
    while index < len(commands):
        parm = commands[index + 1] if index + 1 < len(commands) else None
        parm2 = commands[index + 2] if index + 2 < len(commands) else None
        state = _turtle_command(commands[index], parm, parm2, state, index)
        index += _turtle_command_len(commands, index)
    return state


def _turtle_command(command, parm, parm2, state, index):
    path_idx, step_idx, ang_idx, arcs_idx = 0, 1, 2, 3
    if command == "repeat":
        assert isinstance(parm, (int, float)), f'"repeat" needs a count at index {index}'
        assert isinstance(parm2, (list, tuple)), f'"repeat" needs a command list at index {index}'
        return _turtle_repeat(list(parm2), state, True, int(parm))

    parm = None if isinstance(parm, str) else parm
    parm2 = None if isinstance(parm2, str) else parm2
    lastpt = np.asarray(state[path_idx][-1], dtype=float)
    step = np.asarray(state[step_idx], dtype=float)

    def with_point(p):
        s = list(state)
        s[path_idx] = state[path_idx] + [[float(p[0]), float(p[1])]]
        return s

    def with_step(v):
        s = list(state)
        s[step_idx] = [float(v[0]), float(v[1])]
        return s

    if command == "move":
        return with_point((parm if parm is not None else 1) * step + lastpt)
    if command == "xmove":
        return with_point((parm if parm is not None else 1) * np.linalg.norm(step) * np.array([1, 0]) + lastpt)
    if command == "ymove":
        return with_point((parm if parm is not None else 1) * np.linalg.norm(step) * np.array([0, 1]) + lastpt)
    if command == "xymove":
        return with_point(lastpt + np.asarray(parm, dtype=float))
    if command == "jump":
        return with_point(parm)
    if command == "xjump":
        return with_point([parm, lastpt[1]])
    if command == "yjump":
        return with_point([lastpt[0], parm])
    if command == "untilx":
        res = general_line_intersection([lastpt, lastpt + step], [[parm, 0], [parm, 1]])
        assert res is not None, f'"untilx" never reaches the goal at index {index}'
        return with_point(res[0])
    if command == "untily":
        res = general_line_intersection([lastpt, lastpt + step], [[0, parm], [1, parm]])
        assert res is not None, f'"untily" never reaches the goal at index {index}'
        return with_point(res[0])
    if command in ("turn", "left"):
        return with_step(_rot2(parm if parm is not None else state[ang_idx], step))
    if command == "right":
        return with_step(_rot2(-(parm if parm is not None else state[ang_idx]), step))
    if command == "angle":
        s = list(state)
        s[ang_idx] = parm
        return s
    if command == "setdir":
        if isinstance(parm, (list, tuple, np.ndarray)):
            return with_step(np.linalg.norm(step) * unit([parm[0], parm[1]]))
        return with_step(np.linalg.norm(step) * np.array([math.cos(math.radians(parm)), math.sin(math.radians(parm))]))
    if command == "length":
        return with_step(parm * unit(step))
    if command == "scale":
        return with_step(parm * step)
    if command == "addlength":
        return with_step(step + unit(step) * parm)
    if command == "arcsteps":
        s = list(state)
        s[arcs_idx] = parm
        return s
    if command in ("arcleft", "arcright", "arcleftto", "arcrightto"):
        return _turtle_arc(command, parm, parm2, state, index)
    raise AssertionError(f'Unknown turtle command "{command}" at index {index}')


def _turtle_arc(command, parm, parm2, state, index):
    path_idx, step_idx, ang_idx, arcs_idx = 0, 1, 2, 3
    assert isinstance(parm, (int, float)), f'"{command}" needs a numeric radius at index {index}'
    lastpt = np.asarray(state[path_idx][-1], dtype=float)
    step = np.asarray(state[step_idx], dtype=float)
    lrsign = 1 if command in ("arcleft", "arcleftto") else -1
    steps = _frag_count(abs(parm)) if state[arcs_idx] == 0 else int(state[arcs_idx])

    if command in ("arcleft", "arcright"):
        myangle = parm2 if parm2 is not None else state[ang_idx]
        radius = parm * (1 if myangle >= 0 else -1)
        center = lastpt + lrsign * radius * line_normal([0, 0], step)
        turn = math.copysign(1, parm) * lrsign * myangle
        rot_step = _rot2(lrsign * myangle, step)
    else:  # arcleftto / arcrightto
        assert isinstance(parm2, (int, float)), f'"{command}" needs a numeric angle at index {index}'
        radius = parm
        center = lastpt + lrsign * radius * line_normal([0, 0], step)
        start_angle = math.degrees(math.atan2(step[1], step[0])) % 360
        end_angle = parm2 % 360
        if lrsign * end_angle < lrsign * start_angle:
            end_angle = end_angle + lrsign * 360
        delta = -start_angle + end_angle
        turn = math.copysign(1, radius) * delta
        rot_step = _rot2(delta, step)

    if turn == 0 or radius == 0:
        arcpath = []
    else:
        p_mid = _rot2(turn / 2, lastpt - center) + center
        p_end = _rot2(turn, lastpt - center) + center
        arcpath = list(arc(steps, points=[lastpt, p_mid, p_end]))[1:]  # drop the shared first point
    s = list(state)
    s[path_idx] = state[path_idx] + [[float(p[0]), float(p[1])] for p in arcpath]
    s[step_idx] = [float(rot_step[0]), float(rot_step[1])]
    return s


# ---------------------------------------------------------------------------
# Section: Path2D renderers
# ---------------------------------------------------------------------------

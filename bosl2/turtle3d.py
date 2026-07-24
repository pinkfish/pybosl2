# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/turtle3d.py
#    Pure-Python port of BOSL2's turtle3d.scad: a 3-D turtle-graphics system. A :class:`Turtle` walks
#    through space carrying an orientation frame; a list of commands (``"move"``, ``"left"``, ``"up"``,
#    ``"arcright"`` ...) drives it, and the result is either the list of points it visited or a list of
#    4x4 transforms suitable for sweeping a profile (``path_sweep``/``sweep``).
#
#    The full command set is ported: the simple commands (moves, jumps, relative and absolute turns,
#    rolls, arcs, ``repeat``) and the *compound* commands -- a single ``["move", 5, "grow", 2, "twist",
#    30]`` (or ``["arc", 4, "left", 45, "up", 30]``) list applying several effects to one step, with
#    ``move``/``arc``, ``grow``/``shrink``/``twist``/``roll``/``steps``/``reverse`` and, for ``arc``,
#    relative (``left``/``right``/``up``/``down``) or absolute (``xrot``/``yrot``/``zrot``/``rot``/
#    ``todir``) rotation plus roll-to (``rollto``/``rrollto``/``lrollto``).
#
# FileSummary: 3-D turtle graphics (the Turtle class).
# FileGroup: BOSL2

from __future__ import annotations

import math

import numpy as np

from bosl2._helpers import rot_from_to4
from bosl2.transforms import rot_decode

__all__ = ["Turtle"]

RIGHT = [1.0, 0.0, 0.0]
BACK = [0.0, 1.0, 0.0]
UP = [0.0, 0.0, 1.0]
FWD = [0.0, -1.0, 0.0]

# state indices
_TR, _PRE, _STEP, _ANG, _ARCN = 0, 1, 2, 3, 4


# --- 4x4 transform helpers (OpenSCAD conventions) ---------------------------


def _trans4(v):
    m = np.eye(4)
    v = list(v) + [0.0] * (3 - len(v))
    m[:3, 3] = v[:3]
    return m


def _axis_rot4(axis, deg, center=(0.0, 0.0, 0.0)):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    x, y, z = np.asarray(axis, float) / np.linalg.norm(axis)
    R = np.array(
        [
            [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
            [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
            [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)],
        ]
    )
    m = np.eye(4)
    m[:3, :3] = R
    if any(center):
        center = np.asarray(center, float)
        m = _trans4(center) @ m @ _trans4(-center)
    return m


def _xrot4(a, center=(0, 0, 0)):
    return _axis_rot4([1, 0, 0], a, center)


def _yrot4(a, center=(0, 0, 0)):
    return _axis_rot4([0, 1, 0], a, center)


def _zrot4(a, center=(0, 0, 0)):
    return _axis_rot4([0, 0, 1], a, center)


def _apply(T, pt):
    return (T @ np.array([pt[0], pt[1], pt[2], 1.0]))[:3]


def _rotpart(T):
    m = np.eye(4)
    m[:3, :3] = T[:3, :3]
    return m


def _transpart(T):
    return T[:3, 3]


def _frame_map(x_axis, z_axis):
    """A rotation whose local X maps to *x_axis* and local Z (as best as possible) to *z_axis*."""
    x = np.asarray(x_axis, float)
    x = x / np.linalg.norm(x)
    z = np.asarray(z_axis, float)
    z = z - np.dot(z, x) * x  # orthogonalise z against x
    z = z / np.linalg.norm(z)
    y = np.cross(z, x)
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2] = x, y, z
    return m


def _ends_with(s, suffix):
    return isinstance(s, str) and s.endswith(suffix)


# --- turtle state + command processing --------------------------------------


def _init_state(state):
    """Normalise the *state* argument (a direction 3-vector, a 4x4 matrix, or a full state list)."""
    arr = np.asarray(state, dtype=object)
    if isinstance(state, np.ndarray) and state.shape == (4, 4):
        return [[np.asarray(state, float)], [_yrot4(90)], 1.0, 90.0, 0]
    if _is_vec3(state):
        s = np.asarray(state, float)
        updir = np.asarray(UP, float) - (np.dot(UP, s)) * s / np.dot(s, s)
        z = FWD if np.isclose(np.linalg.norm(updir), 0) else updir
        return [[_frame_map(s, z)], [_yrot4(90)], 1.0, 90.0, 0]
    # already a full state list
    tr, pre, step, ang, arcn = state
    return [
        [np.asarray(m, float) for m in tr],
        [np.asarray(m, float) for m in pre],
        float(step),
        float(ang),
        int(arcn),
    ]


def _is_vec3(v):
    try:
        return len(v) == 3 and all(isinstance(x, (int, float)) for x in v)
    except TypeError:
        return False


def _tupdate(state, tran, pretran):
    return [
        state[_TR] + list(tran),
        state[_PRE] + list(pretran),
        state[_STEP],
        state[_ANG],
        state[_ARCN],
    ]


def _set(state, idx, val):
    s = list(state)
    s[idx] = val
    return s


def _turtle_rotation(command, angle, center=(0, 0, 0)):
    a = (
        -1 if (_ends_with(command, "right") or _ends_with(command, "up")) else 1
    ) * angle
    if _ends_with(command, "xrot"):
        return _xrot4(a, center)
    if _ends_with(command, "yrot"):
        return _yrot4(a, center)
    if _ends_with(command, "zrot"):
        return _zrot4(a, center)
    if _ends_with(command, "right") or _ends_with(command, "left"):
        return _zrot4(a, center)
    return _yrot4(a, center)


_ONE_OR_TWO = {
    "arcleft",
    "arcright",
    "arcup",
    "arcdown",
    "arczrot",
    "arcyrot",
    "arcxrot",
}


def _command_len(commands, i):
    cmd = commands[i]
    if isinstance(cmd, (list, tuple)):  # a compound command occupies one slot
        return 1
    if cmd in ("repeat", "arctodir", "arcrot"):
        return 3
    if (
        cmd in _ONE_OR_TWO
        and len(commands) > i + 2
        and not isinstance(commands[i + 2], str)
        and not isinstance(commands[i + 2], (list, tuple))
    ):
        return 3
    nxt = commands[i + 1] if i + 1 < len(commands) else None
    if isinstance(nxt, str) or isinstance(cmd, (list, tuple)):
        return 1
    return 2


def _run(commands, state, repeat=1):
    for _ in range(repeat):
        i = 0
        while i < len(commands):
            parm = commands[i + 1] if i + 1 < len(commands) else None
            parm2 = commands[i + 2] if i + 2 < len(commands) else None
            state = _command(commands[i], parm, parm2, state, i)
            i += _command_len(commands, i)
    return state


def _num(x):
    return x if isinstance(x, (int, float)) else None


def _command(command, parm, parm2, state, index):
    if command == "repeat":
        return _run(parm2, state, int(parm))
    if isinstance(command, (list, tuple)):
        tran, pretran = _list_command(
            command, state[_ARCN], state[_STEP], state[_TR][-1], state[_PRE][-1], index
        )
        return _tupdate(state, tran, pretran)
    p = _num(parm)
    lastT = state[_TR][-1]
    lastPre = state[_PRE][-1]
    lastpt = _apply(lastT, [0, 0, 0])
    step, ang, arcn = state[_STEP], state[_ANG], state[_ARCN]

    if command == "move":
        diameter = (p if p is not None else 1) * step
        return _tupdate(state, [lastT @ _trans4([diameter, 0, 0])], [lastPre])
    if command in ("untilx", "untily", "untilz"):
        axis = {"untilx": 0, "untily": 1, "untilz": 2}[command]
        diameter = _apply(lastT, [1, 0, 0]) - lastpt  # unit step direction
        if abs(diameter[axis]) < 1e-12:
            raise ValueError(f'"{command}" never reaches the goal at index {index}')
        size = (parm - lastpt[axis]) / diameter[axis]
        return _tupdate(state, [lastT @ _trans4([size, 0, 0])], [lastPre])
    if command in ("xmove", "ymove", "zmove"):
        v = {"xmove": [1, 0, 0], "ymove": [0, 1, 0], "zmove": [0, 0, 1]}[command]
        diameter = (p if p is not None else 1) * step
        return _tupdate(
            state, [_trans4([v[0] * diameter, v[1] * diameter, v[2] * diameter]) @ lastT], [lastPre]
        )
    if command == "xyzmove":
        return _tupdate(state, [_trans4(parm) @ lastT], [lastPre])
    if command in ("jump", "xjump", "yjump", "zjump"):
        if command == "jump":
            target = np.asarray(parm, float)
        else:
            target = np.array(lastpt, float)
            target[{"xjump": 0, "yjump": 1, "zjump": 2}[command]] = parm
        return _tupdate(state, [_trans4(target - lastpt) @ lastT], [lastPre])
    if command == "angle":
        return _set(state, _ANG, parm)
    if command == "length":
        return _set(state, _STEP, parm)
    if command == "scale":
        return _set(state, _STEP, parm * step)
    if command == "addlength":
        return _set(state, _STEP, step + parm)
    if command == "arcsteps":
        return _set(state, _ARCN, int(parm))
    if command == "roll":
        return _set(
            state,
            _TR,
            state[_TR][:-1] + [lastT @ _xrot4(parm if p is not None else ang)],
        )
    if command in ("right", "left", "up", "down"):
        rot = _turtle_rotation(command, p if p is not None else ang)
        return _set(state, _TR, state[_TR][:-1] + [lastT @ rot])
    if command in ("xrot", "yrot", "zrot"):
        Trot, shift = _rotpart(lastT), _transpart(lastT)
        rot = _turtle_rotation(command, p if p is not None else ang)
        return _set(state, _TR, state[_TR][:-1] + [_trans4(shift) @ rot @ Trot])
    if command == "rot":
        Trot, shift = _rotpart(lastT), _transpart(lastT)
        return _set(
            state,
            _TR,
            state[_TR][:-1] + [_trans4(shift) @ np.asarray(parm, float) @ Trot],
        )
    if command == "setdir":
        Trot, shift = _rotpart(lastT), _transpart(lastT)
        cur = _apply(Trot, [1, 0, 0])
        return _set(
            state,
            _TR,
            state[_TR][:-1] + [_trans4(shift) @ rot_from_to4(cur, parm) @ Trot],
        )
    if command in ("arcleft", "arcright", "arcup", "arcdown"):
        radius = step * parm
        myangle = parm2 if _num(parm2) is not None else ang
        length = 2 * math.pi * radius * abs(myangle) / 360
        center = [
            0.0,
            radius
            if command == "arcleft"
            else -radius
            if command == "arcright"
            else 0.0,
            -radius if command == "arcdown" else radius if command == "arcup" else 0.0,
        ]
        steps = _segs(abs(radius)) if arcn == 0 else arcn
        tran = [
            lastT @ _turtle_rotation(command, myangle * k / steps, center)
            for k in range(1, steps + 1)
        ]
        return _tupdate(state, tran, [lastPre] * steps)
    if command in ("arcxrot", "arcyrot", "arczrot"):
        radius = step * parm
        myangle = parm2 if _num(parm2) is not None else ang
        length = 2 * math.pi * radius * abs(myangle) / 360
        steps = _segs(abs(radius)) if arcn == 0 else arcn
        Trot, shift = _rotpart(lastT), _transpart(lastT)
        v = _apply(Trot, [1, 0, 0])
        dir_ = {
            "arcxrot": np.array(RIGHT),
            "arcyrot": np.array(BACK),
            "arczrot": np.array(UP),
        }[command]
        projv = v - np.dot(dir_, v) * dir_
        center = np.sign(myangle) * radius * np.cross(dir_, projv)
        vshift = dir_ * (np.dot(dir_, v) / np.linalg.norm(projv)) * length
        tran = [
            _trans4(shift + vshift * k / steps)
            @ _turtle_rotation(command, myangle * k / steps, center)
            @ Trot
            for k in range(1, steps + 1)
        ]
        return _tupdate(state, tran, [lastPre] * steps)
    if command in ("arctodir", "arcrot"):
        Trot, shift = _rotpart(lastT), _transpart(lastT)
        v = _apply(Trot, [1, 0, 0])
        rd = rot_decode(
            rot_from_to4(v, parm2)
            if command == "arctodir"
            else np.asarray(parm2, float)
        )
        myangle, dir_ = rd[0], np.asarray(rd[1], float)
        projv = v - np.dot(dir_, v) * dir_
        radius = step * parm
        length = 2 * math.pi * radius * myangle / 360
        vshift = dir_ * (np.dot(dir_, v) / np.linalg.norm(projv)) * length
        steps = _segs(abs(radius)) if arcn == 0 else arcn
        center = radius * np.cross(dir_, projv)
        tran = [
            _trans4(shift + vshift * k / steps)
            @ _axis_rot4(dir_, k / steps * myangle, center)
            @ Trot
            for k in range(1, steps + 1)
        ]
        return _tupdate(state, tran, [lastPre] * steps)
    raise ValueError(f'Unknown turtle command "{command}" at index {index}')


def _segs(r):
    return max(5, math.ceil(min(360 / 12, 2 * math.pi * max(r, 1e-6) / 2)))


def _segs2(r, angle):
    return max(2, math.ceil(_segs(r) * abs(angle) / 360))


def _scale4(v):
    m = np.eye(4)
    m[0, 0], m[1, 1], m[2, 2] = v[0], v[1], v[2]
    return m


def _unit(v):
    v = np.asarray(v, float)
    sides = np.linalg.norm(v)
    return v / sides if sides > 1e-12 else np.zeros(3)


def _lerp3(a, b, t):
    return [a[i] + (b[i] - a[i]) * t for i in range(3)]


def _vec_angle(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return math.degrees(math.atan2(np.linalg.norm(np.cross(a, b)), np.dot(a, b)))


def _compute_spin(anchor_dir, spin_dir):
    """The roll angle that aligns the turtle's "up" with *spin_dir* (BOSL2 _compute_spin(), 2-arg)."""
    native = _rotpart(rot_from_to4(UP, anchor_dir))[:3, :3] @ np.asarray(BACK, float)
    ad, sd = np.asarray(anchor_dir, float), np.asarray(spin_dir, float)
    perp = sd - np.dot(sd, ad) * ad
    angle = _vec_angle(native, perp)
    return -angle if np.dot(np.cross(native, perp), ad) < 0 else angle


def _force_list(x, n):
    try:
        return [float(v) for v in x]
    except TypeError:
        return [float(x)] * n


def _list_command(command, arcsteps, movescale, lastT, lastPre, index):
    """A compound turtle step: ``["move"|"arc", ...]`` with sub-commands (grow/shrink/twist/roll/steps
    and, for "arc", the rotation). Returns ``(transforms, pre-transforms)`` (BOSL2 _turtle3d_list_command)."""
    command = list(command)
    reverse = "reverse" in command
    if reverse:
        ri = command.index("reverse")
        assert ri % 2 == 0, f"Malformed compound command at index {index}"
        command = command[:ri] + command[ri + 1 :]
    assert len(command) % 2 == 0, (
        f"Compound command must be [keyword, value] pairs at index {index}"
    )
    head = command[0]
    assert head in ("move", "arc"), (
        f'A compound command must begin with "move" or "arc" at index {index}'
    )
    keys = {command[i]: command[i + 1] for i in range(0, len(command), 2)}

    move = movescale * keys.get("move", 0) if head == "move" else 0.0
    radius = movescale * (keys.get("arc", 0) or 0)
    twist = keys.get("twist", 0)
    grow = _force_list(keys.get("grow", 1), 2)
    shrink = _force_list(keys.get("shrink", 1), 2)
    scaling = [grow[0] / shrink[0], grow[1] / shrink[1], 1.0]
    usersteps = int(keys.get("steps", 0))
    flip = np.diag([-1.0, 1.0, 1.0, 1.0]) if reverse else np.eye(4)

    # relative rotation ("left"/"right"/"up"/"down")
    right, left = keys.get("right", 0), keys.get("left", 0)
    up, down = keys.get("up", 0), keys.get("down", 0)
    assert head == "move" or (right == 0 or left == 0), (
        f'Cannot give both "left" and "right" at index {index}'
    )
    assert head == "move" or (up == 0 or down == 0), (
        f'Cannot give both "up" and "down" at index {index}'
    )
    newdir = _apply(_zrot4(left - right) @ _yrot4(down - up), RIGHT)
    if left - right == 0:
        relaxis = np.asarray(BACK, float)
    elif down - up == 0:
        relaxis = np.asarray(UP, float)
    else:
        relaxis = np.cross(RIGHT, newdir)
    if head == "move":
        angle = 0.0
    elif left - right == 0 or down - up == 0:
        angle = (down - up) + (left - right)
    else:
        angle = _vec_angle(RIGHT, newdir)
    if left - right == 0:
        center = -radius * np.array([0.0, 0.0, np.sign(down - up)])
    elif down - up == 0:
        center = -radius * np.array([0.0, np.sign(right - left), 0.0])
    else:
        center = -radius * _unit(np.cross(RIGHT, np.cross(RIGHT, newdir)))

    # absolute rotation ("xrot"/"yrot"/"zrot"/"rot"/"todir")
    Trot, shift = _rotpart(lastT), _transpart(lastT)
    v = _apply(Trot, RIGHT)
    xr, yr, zr = keys.get("xrot", 0), keys.get("yrot", 0), keys.get("zrot", 0)
    rotM, todir = keys.get("rot", None), keys.get("todir", None)
    absangle, absaxis = None, np.zeros(3)
    if head == "arc":
        nz = (
            len([e for e in (xr, yr, zr) if e != 0])
            + (rotM is not None)
            + (todir is not None)
        )
        assert nz <= 1, (
            f'Give only one of "xrot"/"yrot"/"zrot"/"rot"/"todir" at index {index}'
        )
        if rotM is not None:
            rd = rot_decode(np.asarray(rotM, float))
            absangle, absaxis = rd[0], np.asarray(rd[1], float)
        elif todir is not None:
            rd = rot_decode(rot_from_to4(v, todir))
            absangle, absaxis = rd[0], np.asarray(rd[1], float)
        elif xr != 0:
            absangle, absaxis = xr, np.asarray(RIGHT, float)
        elif yr != 0:
            absangle, absaxis = yr, np.asarray(BACK, float)
        elif zr != 0:
            absangle, absaxis = zr, np.asarray(UP, float)
    if absangle is None:
        abscenter = vshift = None
    else:
        projv = v - np.dot(absaxis, v) * absaxis
        assert np.linalg.norm(projv) > 1e-9, (
            f"Rotation acts as twist -- not a valid arc at index {index}"
        )
        abscenter = np.sign(absangle) * radius * np.cross(absaxis, projv)
        vshift = (
            absaxis
            * (np.dot(absaxis, v) / np.linalg.norm(projv))
            * 2
            * math.pi
            * radius
            * absangle
            / 360
        )
    assert head != "arc" or (absangle or angle), '"arc" needs a rotation type and angle'

    # roll (numeric, or roll-to-a-direction)
    def _finalT():
        if absangle is None:
            rel = np.eye(4) if angle == 0 else _axis_rot4(relaxis, angle, center)
            return lastT @ flip @ _trans4([move, 0, 0]) @ rel
        return _trans4(shift + vshift) @ _axis_rot4(absaxis, absangle, abscenter) @ Trot

    rollval = keys.get("roll", 0)
    rrollto, lrollto, rollto = (
        keys.get("rrollto", None),
        keys.get("lrollto", None),
        keys.get("rollto", None),
    )
    if rollval != 0:
        roll = rollval
    elif rrollto is None and lrollto is None and rollto is None:
        roll = 0.0
    else:
        fT = _finalT()
        finaldir = _unit(_apply(_rotpart(fT), RIGHT))
        finalup = _apply(_rotpart(fT), UP)
        desired = (
            rollto
            if rollto is not None
            else (rrollto if rrollto is not None else lrollto)
        )
        delta = (
            _compute_spin(finaldir, desired) - _compute_spin(finaldir, finalup)
        ) % 360
        if rrollto is not None or delta == 0:
            roll = delta
        elif lrollto is not None or delta > 180:
            roll = delta - 360
        else:
            roll = delta

    eff = absangle if absangle is not None else angle
    if usersteps == 0 and head == "move" and roll == 0 and twist == 0:
        steps = 1
    elif usersteps != 0:
        steps = usersteps
    elif arcsteps != 0:
        steps = arcsteps
    elif radius > 0 and eff != 0:
        steps = _segs2(radius, eff)
    else:
        steps = 5

    trans, pretran = [], []
    for n in range(1, steps + 1):
        frac = n / steps
        if absangle is None:
            rel = np.eye(4) if angle == 0 else _axis_rot4(relaxis, frac * angle, center)
            T = lastT @ flip @ _trans4([frac * move, 0, 0]) @ rel @ _xrot4(frac * roll)
        else:
            T = (
                _trans4(shift + vshift * frac)
                @ _axis_rot4(absaxis, frac * absangle, abscenter)
                @ Trot
                @ _xrot4(frac * roll)
            )
        P = lastPre @ _zrot4(frac * twist) @ _scale4(_lerp3([1, 1, 1], scaling, frac))
        trans.append(T)
        pretran.append(P)
    return trans, pretran


def _dedup(points, eps=1e-9):
    out = []
    for p in points:
        if not out or np.linalg.norm(np.asarray(p) - np.asarray(out[-1])) > eps:
            out.append([float(p[0]), float(p[1]), float(p[2])])
    return out


class Turtle:
    """A 3-D turtle: walk it with a command list to produce a path or a list of sweep transforms
    (BOSL2 turtle3d.scad).

    The turtle starts at the origin pointing in *state* (default ``RIGHT`` = +X), with "up" along +Z.
    Commands are a flat list mixing command names and their arguments, e.g.
    ``["move", 10, "left", 45, "arcright", 2]``. Turns: ``left``/``right`` (about up), ``up``/``down``
    (about the side), ``roll`` (about the heading), and absolute ``xrot``/``yrot``/``zrot``. Arcs:
    ``arcleft``/``arcright``/``arcup``/``arcdown`` (radius[, angle]). ``move``/``jump`` translate;
    ``length``/``angle``/``scale``/``arcsteps`` set defaults; ``repeat count [cmds]`` repeats. A nested
    list beginning with ``"move"`` or ``"arc"`` is a *compound* step applying several effects at once
    (``grow``/``shrink``/``twist``/``roll``/``steps``/``reverse``), e.g.
    ``["move", 40, "grow", 2, "twist", 180, "steps", 40]`` grows and twists the swept profile.

    Examples:
        A rounded square path swept into a tube:

        .. pythonscad-example::

            from bosl2.turtle3d import Turtle
            from bosl2.skin import path_sweep
            sq = [[-1, -1], [1, -1], [1, 1], [-1, 1]]
            path = Turtle().run(["move", 20, "arcleft", 3, "move", 20, "arcleft", 3,
                                 "move", 20, "arcleft", 3, "move", 20, "arcleft", 3]).points()
            path_sweep(sq, path, closed=True).polyhedron().show()
    """

    def __init__(self, state=RIGHT):
        self.state = _init_state(state)

    def run(self, commands, repeat=1) -> "Turtle":
        """Execute *commands* (optionally *repeat* times), advancing this turtle's state. Returns self."""
        self.state = _run(list(commands), self.state, repeat)
        return self

    def points(self) -> list:
        """The de-duplicated list of 3-D points the turtle has visited."""
        return _dedup([_apply(T, [0, 0, 0]) for T in self.state[_TR]])

    def transforms(self) -> list:
        """The list of 4x4 transforms (position + orientation) for sweeping a profile along the path."""
        return [
            self.state[_TR][i] @ self.state[_PRE][i]
            for i in range(len(self.state[_TR]))
        ]

    def full_state(self):
        """The raw turtle state ``[transforms, pre-transforms, move-length, angle, arc-steps]``."""
        return self.state

    @classmethod
    def turtle3d(
        cls, commands, state=RIGHT, transforms=False, full_state=False, repeat=1
    ):
        """One-shot BOSL2 ``turtle3d()``: run *commands* from *state* and return points (default),
        sweep *transforms*, or the *full_state*."""
        t = cls(state).run(commands, repeat)
        if full_state:
            return t.full_state()
        return t.transforms() if transforms else t.points()

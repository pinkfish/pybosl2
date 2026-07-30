# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/turtle3d.py
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
from enum import Enum
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from numpy.typing import ArrayLike

from pybosl2._helpers import rot_from_to4
from pybosl2.transforms import rot_decode

__all__ = ["Turtle", "BaseTurtle", "TurtleCommand", "TurtleCommandType"]


class TurtleCommandType(Enum):
    MOVE = "move"
    UNTILX = "untilx"
    UNTILY = "untily"
    UNTILZ = "untilz"
    XMOVE = "xmove"
    YMOVE = "ymove"
    ZMOVE = "zmove"
    XYZMOVE = "xyzmove"
    JUMP = "jump"
    XJUMP = "xjump"
    YJUMP = "yjump"
    ZJUMP = "zjump"
    ANGLE = "angle"
    LENGTH = "length"
    SCALE = "scale"
    ADDLENGTH = "addlength"
    ARCSTEPS = "arcsteps"
    ROLL = "roll"
    RIGHT = "right"
    LEFT = "left"
    UP = "up"
    DOWN = "down"
    XROT = "xrot"
    YROT = "yrot"
    ZROT = "zrot"
    ROT = "rot"
    SETDIR = "setdir"
    ARCLEFT = "arcleft"
    ARCRIGHT = "arcright"
    ARCUP = "arcup"
    ARCDOWN = "arcdown"
    ARCXROT = "arcxrot"
    ARCYROT = "arcyrot"
    ARCZROT = "arczrot"
    ARCTODIR = "arctodir"
    ARCROT = "arcrot"
    REPEAT = "repeat"
    ARC = "arc"


class TurtleCommand:
    _ONE_OR_TWO = {
        TurtleCommandType.ARCLEFT,
        TurtleCommandType.ARCRIGHT,
        TurtleCommandType.ARCUP,
        TurtleCommandType.ARCDOWN,
        TurtleCommandType.ARCZROT,
        TurtleCommandType.ARCYROT,
        TurtleCommandType.ARCXROT,
    }

    def __init__(
        self,
        cmd_type: TurtleCommandType,
        size: Any = None,
        angle: Any = None,
        radius: Any = None,
        steps: Any = None,
        center: Any = None,
        grow: Any = None,
        shrink: Any = None,
        twist: Any = None,
        roll: Any = None,
        reverse: bool = False,
        rollto: Any = None,
        rrollto: Any = None,
        lrollto: Any = None,
        options: dict[str, Any] | None = None,
        is_compound: bool = False,
    ) -> None:
        self.cmd_type = cmd_type
        self.size = size
        self.angle = angle
        self.radius = radius
        self.steps = steps
        self.center = center
        self.grow = grow
        self.shrink = shrink
        self.twist = twist
        self.roll = roll
        self.reverse = reverse
        self.rollto = rollto
        self.rrollto = rrollto
        self.lrollto = lrollto
        self.options = options or {}
        self._is_compound = is_compound

    @property
    def is_compound(self) -> bool:
        return self._is_compound

    @property
    def parm(self) -> Any:
        if self.cmd_type in (
            TurtleCommandType.MOVE,
            TurtleCommandType.XMOVE,
            TurtleCommandType.YMOVE,
            TurtleCommandType.ZMOVE,
            TurtleCommandType.XYZMOVE,
            TurtleCommandType.UNTILX,
            TurtleCommandType.UNTILY,
            TurtleCommandType.UNTILZ,
            TurtleCommandType.JUMP,
            TurtleCommandType.XJUMP,
            TurtleCommandType.YJUMP,
            TurtleCommandType.ZJUMP,
            TurtleCommandType.ANGLE,
            TurtleCommandType.LENGTH,
            TurtleCommandType.SCALE,
            TurtleCommandType.ADDLENGTH,
            TurtleCommandType.ARCSTEPS,
        ):
            return self.size if self.size is not None else self.angle
        if self.cmd_type in (
            TurtleCommandType.ROLL,
            TurtleCommandType.RIGHT,
            TurtleCommandType.LEFT,
            TurtleCommandType.UP,
            TurtleCommandType.DOWN,
            TurtleCommandType.XROT,
            TurtleCommandType.YROT,
            TurtleCommandType.ZROT,
        ):
            return self.angle if self.angle is not None else self.size
        if self.cmd_type in (
            TurtleCommandType.ROT,
            TurtleCommandType.SETDIR,
        ):
            return self.size if self.size is not None else self.center
        if self.cmd_type in (
            TurtleCommandType.ARCLEFT,
            TurtleCommandType.ARCRIGHT,
            TurtleCommandType.ARCUP,
            TurtleCommandType.ARCDOWN,
            TurtleCommandType.ARCXROT,
            TurtleCommandType.ARCYROT,
            TurtleCommandType.ARCZROT,
            TurtleCommandType.ARCTODIR,
            TurtleCommandType.ARCROT,
        ):
            return self.radius if self.radius is not None else self.size
        if self.cmd_type == TurtleCommandType.REPEAT:
            return self.size
        return None

    @property
    def parm2(self) -> Any:
        if self.cmd_type in (
            TurtleCommandType.ARCLEFT,
            TurtleCommandType.ARCRIGHT,
            TurtleCommandType.ARCUP,
            TurtleCommandType.ARCDOWN,
            TurtleCommandType.ARCXROT,
            TurtleCommandType.ARCYROT,
            TurtleCommandType.ARCZROT,
            TurtleCommandType.ARCTODIR,
            TurtleCommandType.ARCROT,
        ):
            return self.angle
        if self.cmd_type == TurtleCommandType.REPEAT:
            return self.options.get("commands")
        return None

    def to_legacy_compound(self) -> list[Any]:
        out: list[Any] = []
        if self.cmd_type == TurtleCommandType.MOVE:
            out.extend(["move", self.size if self.size is not None else 0])
        elif self.cmd_type == TurtleCommandType.ARC:
            out.extend(["arc", self.radius if self.radius is not None else self.size if self.size is not None else 0])

        if self.grow is not None:
            out.extend(["grow", self.grow])
        if self.shrink is not None:
            out.extend(["shrink", self.shrink])
        if self.twist is not None:
            out.extend(["twist", self.twist])
        if self.roll is not None:
            out.extend(["roll", self.roll])
        if self.steps is not None:
            out.extend(["steps", self.steps])
        if self.reverse:
            out.append("reverse")
        if self.rollto is not None:
            out.extend(["rollto", self.rollto])
        if self.rrollto is not None:
            out.extend(["rrollto", self.rrollto])
        if self.lrollto is not None:
            out.extend(["lrollto", self.lrollto])

        for k, v in self.options.items():
            if k not in (
                "commands",
                "grow",
                "shrink",
                "twist",
                "roll",
                "steps",
                "reverse",
                "rollto",
                "rrollto",
                "lrollto",
                "move",
                "arc",
            ):
                out.extend([k, v])
        return out

    @staticmethod
    def _num(x: Any) -> float | None:
        return x if isinstance(x, (int, float)) else None

    @staticmethod
    def _command_len(commands: Sequence[Any], i: int) -> int:
        cmd = commands[i]
        if isinstance(cmd, (list, tuple)):
            return 1

        resolved_cmd = None
        if isinstance(cmd, TurtleCommandType):
            resolved_cmd = cmd
        elif isinstance(cmd, str):
            resolved_cmd = next((m for m in TurtleCommandType if m.value == cmd), None)

        if resolved_cmd in (TurtleCommandType.REPEAT, TurtleCommandType.ARCTODIR, TurtleCommandType.ARCROT):
            return 3
        if (
            resolved_cmd in TurtleCommand._ONE_OR_TWO
            and len(commands) > i + 2
            and not isinstance(commands[i + 2], str)
            and not isinstance(commands[i + 2], (list, tuple))
        ):
            return 3
        nxt = commands[i + 1] if i + 1 < len(commands) else None
        if isinstance(nxt, str) or isinstance(cmd, (list, tuple)):
            return 1
        return 2

    @staticmethod
    def _to_turtle_command(cmd: Any, parm: Any = None, parm2: Any = None) -> TurtleCommand:
        if isinstance(cmd, (list, tuple)):
            cmd_list = list(cmd)
            head = cmd_list[0]
            head_val = head.value if isinstance(head, TurtleCommandType) else head
            assert head_val in ("move", "arc"), "Compound command must begin with 'move' or 'arc'"
            reverse = "reverse" in cmd_list
            if reverse:
                ri = cmd_list.index("reverse")
                cmd_list = cmd_list[:ri] + cmd_list[ri + 1 :]

            keys = {}
            for i in range(0, len(cmd_list), 2):
                k = cmd_list[i]
                k_val = k.value if isinstance(k, TurtleCommandType) else k
                keys[k_val] = cmd_list[i + 1]

            cmd_type = TurtleCommandType.MOVE if head_val == "move" else TurtleCommandType.ARC

            size = keys.get("move") if head_val == "move" else keys.get("arc")
            radius = keys.get("arc") if head_val == "arc" else None

            return TurtleCommand(
                cmd_type=cmd_type,
                size=size,
                radius=radius,
                angle=keys.get("left", 0) - keys.get("right", 0)
                or keys.get("down", 0) - keys.get("up", 0)
                or keys.get("xrot", 0)
                or keys.get("yrot", 0)
                or keys.get("zrot", 0),
                steps=keys.get("steps"),
                grow=keys.get("grow"),
                shrink=keys.get("shrink"),
                twist=keys.get("twist"),
                roll=keys.get("roll"),
                reverse=reverse,
                rollto=keys.get("rollto"),
                rrollto=keys.get("rrollto"),
                lrollto=keys.get("lrollto"),
                options=keys,
                is_compound=True,
            )

        if isinstance(cmd, TurtleCommandType):
            cmd_type = cmd
        else:
            try:
                cmd_type = TurtleCommandType(cmd)
            except ValueError:
                raise ValueError(f"Unknown command: {cmd}") from None

        size = None
        angle = None
        radius = None

        if cmd_type in (
            TurtleCommandType.MOVE,
            TurtleCommandType.XMOVE,
            TurtleCommandType.YMOVE,
            TurtleCommandType.ZMOVE,
            TurtleCommandType.XYZMOVE,
            TurtleCommandType.UNTILX,
            TurtleCommandType.UNTILY,
            TurtleCommandType.UNTILZ,
            TurtleCommandType.JUMP,
            TurtleCommandType.XJUMP,
            TurtleCommandType.YJUMP,
            TurtleCommandType.ZJUMP,
            TurtleCommandType.ANGLE,
            TurtleCommandType.LENGTH,
            TurtleCommandType.SCALE,
            TurtleCommandType.ADDLENGTH,
            TurtleCommandType.ARCSTEPS,
        ):
            size = parm
        elif cmd_type in (
            TurtleCommandType.ROLL,
            TurtleCommandType.RIGHT,
            TurtleCommandType.LEFT,
            TurtleCommandType.UP,
            TurtleCommandType.DOWN,
            TurtleCommandType.XROT,
            TurtleCommandType.YROT,
            TurtleCommandType.ZROT,
        ):
            angle = parm
        elif cmd_type in (
            TurtleCommandType.ROT,
            TurtleCommandType.SETDIR,
        ):
            size = parm
        elif cmd_type in (
            TurtleCommandType.ARCLEFT,
            TurtleCommandType.ARCRIGHT,
            TurtleCommandType.ARCUP,
            TurtleCommandType.ARCDOWN,
            TurtleCommandType.ARCXROT,
            TurtleCommandType.ARCYROT,
            TurtleCommandType.ARCZROT,
            TurtleCommandType.ARCTODIR,
            TurtleCommandType.ARCROT,
        ):
            radius = parm
            angle = parm2
        elif cmd_type == TurtleCommandType.REPEAT:
            size = parm

        return TurtleCommand(
            cmd_type=cmd_type,
            size=size,
            angle=angle,
            radius=radius,
            options={"commands": TurtleCommand._parse_commands(parm2)}
            if cmd_type == TurtleCommandType.REPEAT
            else None,
        )

    @staticmethod
    def _parse_commands(commands: Iterable[Any]) -> list[TurtleCommand]:
        cmds = list(commands)
        out = []
        i = 0
        while i < len(cmds):
            cmd = cmds[i]
            if isinstance(cmd, TurtleCommand):
                out.append(cmd)
                i += 1
                continue

            cmd_len = TurtleCommand._command_len(cmds, i)
            parm = cmds[i + 1] if i + 1 < len(cmds) else None
            parm2 = cmds[i + 2] if i + 2 < len(cmds) else None

            parsed = TurtleCommand._to_turtle_command(cmd, parm, parm2)
            out.append(parsed)
            i += cmd_len
        return out


RIGHT = [1.0, 0.0, 0.0]
BACK = [0.0, 1.0, 0.0]
UP = [0.0, 0.0, 1.0]
FWD = [0.0, -1.0, 0.0]

# state indices
_TR, _PRE, _STEP, _ANG, _ARCN = 0, 1, 2, 3, 4


class BaseTurtle:
    def __init__(self, state: Any = RIGHT) -> None:
        self.state = BaseTurtle._init_state(state)

    def run(self, commands: Iterable[Any], repeat: int = 1) -> BaseTurtle:
        """
        Execute *commands* (optionally *repeat* times), advancing this turtle's state. Returns
        self.
        """
        parsed = TurtleCommand._parse_commands(commands)
        self.state = BaseTurtle._run_commands(parsed, self.state, repeat)
        return self

    def points(self) -> list[list[float]]:
        """The de-duplicated list of 3-D points the turtle has visited."""
        return BaseTurtle._dedup([BaseTurtle._apply(T, [0, 0, 0]) for T in self.state[_TR]])

    def transforms(self) -> list[np.ndarray]:
        """
        The list of 4x4 transforms (position + orientation) for sweeping a profile along the
        path.
        """
        return [self.state[_TR][i] @ self.state[_PRE][i] for i in range(len(self.state[_TR]))]

    def full_state(self) -> list[Any]:
        """The raw turtle state ``[transforms, pre-transforms, move-length, angle, arc-steps]``."""
        return self.state

    @staticmethod
    def _trans4(v: ArrayLike) -> np.ndarray:
        m = np.eye(4)
        arr = np.atleast_1d(np.asarray(v, float))
        v_list = list(arr) + [0.0] * (3 - len(arr))
        m[:3, 3] = v_list[:3]
        return m

    @staticmethod
    def _axis_rot4(axis: ArrayLike, deg: float, center: ArrayLike = (0.0, 0.0, 0.0)) -> np.ndarray:
        a = math.radians(deg)
        c, s = math.cos(a), math.sin(a)
        x, y, z = np.asarray(axis, float) / np.linalg.norm(axis)
        rot_mat = np.array(
            [
                [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
                [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
                [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)],
            ]
        )
        m = np.eye(4)
        m[:3, :3] = rot_mat
        center_arr = np.asarray(center, float)
        if np.any(center_arr):
            m = BaseTurtle._trans4(center_arr) @ m @ BaseTurtle._trans4(-center_arr)
        return m

    @staticmethod
    def _xrot4(a: float, center: ArrayLike = (0, 0, 0)) -> np.ndarray:
        return BaseTurtle._axis_rot4([1, 0, 0], a, center)

    @staticmethod
    def _yrot4(a: float, center: ArrayLike = (0, 0, 0)) -> np.ndarray:
        return BaseTurtle._axis_rot4([0, 1, 0], a, center)

    @staticmethod
    def _zrot4(a: float, center: ArrayLike = (0, 0, 0)) -> np.ndarray:
        return BaseTurtle._axis_rot4([0, 0, 1], a, center)

    @staticmethod
    def _apply(xform: np.ndarray, pt: ArrayLike) -> np.ndarray:
        pt_arr = np.asarray(pt, float)
        return (xform @ np.array([pt_arr[0], pt_arr[1], pt_arr[2], 1.0]))[:3]

    @staticmethod
    def _rotpart(xform: np.ndarray) -> np.ndarray:
        m = np.eye(4)
        m[:3, :3] = xform[:3, :3]
        return m

    @staticmethod
    def _transpart(xform: np.ndarray) -> np.ndarray:
        return xform[:3, 3]

    @staticmethod
    def _frame_map(x_axis: ArrayLike, z_axis: ArrayLike) -> np.ndarray:
        x = np.asarray(x_axis, float)
        x = x / np.linalg.norm(x)
        z = np.asarray(z_axis, float)
        z = z - np.dot(z, x) * x
        z = z / np.linalg.norm(z)
        y = np.cross(z, x)
        m = np.eye(4)
        m[:3, 0], m[:3, 1], m[:3, 2] = x, y, z
        return m

    @staticmethod
    def _init_state(state: Any) -> list[Any]:
        _arr = np.asarray(state, dtype=object)
        if isinstance(state, np.ndarray) and state.shape == (4, 4):
            return [[np.asarray(state, float)], [BaseTurtle._yrot4(90)], 1.0, 90.0, 0]
        if BaseTurtle._is_vec3(state):
            s = np.asarray(state, float)
            updir = np.asarray(UP, float) - (np.dot(UP, s)) * s / np.dot(s, s)
            z = FWD if np.isclose(np.linalg.norm(updir), 0) else updir
            return [[BaseTurtle._frame_map(s, z)], [BaseTurtle._yrot4(90)], 1.0, 90.0, 0]
        tr, pre, step, angle, arcn = state
        return [
            [np.asarray(m, float) for m in tr],
            [np.asarray(m, float) for m in pre],
            float(step),
            float(angle),
            int(arcn),
        ]

    @staticmethod
    def _is_vec3(v: Any) -> bool:
        try:
            return len(v) == 3 and all(isinstance(x, (int, float)) for x in v)
        except TypeError:
            return False

    @staticmethod
    def _tupdate(state: list[Any], tran: Iterable[np.ndarray], pretran: Iterable[np.ndarray]) -> list[Any]:
        return [
            state[_TR] + list(tran),
            state[_PRE] + list(pretran),
            state[_STEP],
            state[_ANG],
            state[_ARCN],
        ]

    @staticmethod
    def _set(state: list[Any], idx: int, val: Any) -> list[Any]:
        s = list(state)
        s[idx] = val
        return s

    @staticmethod
    def _turtle_rotation(cmd_type: TurtleCommandType, angle: float, center: ArrayLike = (0, 0, 0)) -> np.ndarray:
        a = (
            -1
            if cmd_type
            in (
                TurtleCommandType.RIGHT,
                TurtleCommandType.ARCRIGHT,
                TurtleCommandType.UP,
                TurtleCommandType.ARCUP,
            )
            else 1
        ) * angle
        if cmd_type in (TurtleCommandType.XROT, TurtleCommandType.ARCXROT):
            return BaseTurtle._xrot4(a, center)
        if cmd_type in (TurtleCommandType.YROT, TurtleCommandType.ARCYROT):
            return BaseTurtle._yrot4(a, center)
        if cmd_type in (TurtleCommandType.ZROT, TurtleCommandType.ARCZROT):
            return BaseTurtle._zrot4(a, center)
        if cmd_type in (
            TurtleCommandType.RIGHT,
            TurtleCommandType.ARCRIGHT,
            TurtleCommandType.LEFT,
            TurtleCommandType.ARCLEFT,
        ):
            return BaseTurtle._zrot4(a, center)
        return BaseTurtle._yrot4(a, center)

    @staticmethod
    def _segs(r: float) -> int:
        return max(5, math.ceil(min(360 / 12, 2 * math.pi * max(r, 1e-6) / 2)))

    @staticmethod
    def _segs2(r: float, angle: float) -> int:
        return max(2, math.ceil(BaseTurtle._segs(r) * abs(angle) / 360))

    @staticmethod
    def _scale4(v: ArrayLike) -> np.ndarray:
        m = np.eye(4)
        v_arr = np.asarray(v, float)
        m[0, 0], m[1, 1], m[2, 2] = v_arr[0], v_arr[1], v_arr[2]
        return m

    @staticmethod
    def _unit(v: ArrayLike) -> np.ndarray:
        v = np.asarray(v, float)
        sides = np.linalg.norm(v)
        return v / sides if sides > 1e-12 else np.zeros(3)

    @staticmethod
    def _lerp3(a: Sequence[float], b: Sequence[float], t: float) -> list[float]:
        return [a[i] + (b[i] - a[i]) * t for i in range(3)]

    @staticmethod
    def _vec_angle(a: ArrayLike, b: ArrayLike) -> float:
        a, b = np.asarray(a, float), np.asarray(b, float)
        return math.degrees(math.atan2(np.linalg.norm(np.cross(a, b)), np.dot(a, b)))

    @staticmethod
    def _compute_spin(anchor_dir: ArrayLike, spin_dir: ArrayLike) -> float:
        native = BaseTurtle._rotpart(rot_from_to4(UP, anchor_dir))[:3, :3] @ np.asarray(BACK, float)
        ad, sd = np.asarray(anchor_dir, float), np.asarray(spin_dir, float)
        perp = sd - np.dot(sd, ad) * ad
        angle = BaseTurtle._vec_angle(native, perp)
        return -angle if np.dot(np.cross(native, perp), ad) < 0 else angle

    @staticmethod
    def _force_list(x: Any, n: int) -> list[float]:
        try:
            return [float(v) for v in x]
        except TypeError:
            return [float(x)] * n

    @staticmethod
    def _dedup(points: Iterable[ArrayLike], eps: float = 1e-9) -> list[list[float]]:
        out: list[list[float]] = []
        for p in points:
            p_arr = np.asarray(p, float)
            if not out or np.linalg.norm(p_arr - np.asarray(out[-1])) > eps:
                out.append([float(p_arr[0]), float(p_arr[1]), float(p_arr[2])])
        return out

    @staticmethod
    def _list_command(
        command: Iterable[Any],
        arcsteps: int,
        movescale: float,
        last_xform: np.ndarray,
        last_pre: np.ndarray,
        index: int,
    ) -> tuple[list[np.ndarray], list[np.ndarray]]:
        """A compound turtle step: ``["move"|"arc", ...]`` with sub-commands (grow/shrink/twist/roll/steps
        and, for "arc", the rotation). Returns ``(transforms, pre-transforms)`` (BOSL2 _turtle3d_list_command)."""
        cmd_list = list(command)
        reverse = "reverse" in cmd_list
        if reverse:
            ri = cmd_list.index("reverse")
            assert ri % 2 == 0, f"Malformed compound command at index {index}"
            cmd_list = cmd_list[:ri] + cmd_list[ri + 1 :]
        assert len(cmd_list) % 2 == 0, f"Compound command must be [keyword, value] pairs at index {index}"
        head = cmd_list[0]
        assert head in ("move", "arc"), f'A compound command must begin with "move" or "arc" at index {index}'
        keys = {cmd_list[i]: cmd_list[i + 1] for i in range(0, len(cmd_list), 2)}

        move = movescale * keys.get("move", 0) if head == "move" else 0.0
        radius = movescale * (keys.get("arc", 0) or 0)
        twist = keys.get("twist", 0)
        grow = BaseTurtle._force_list(keys.get("grow", 1), 2)
        shrink = BaseTurtle._force_list(keys.get("shrink", 1), 2)
        scaling = [grow[0] / shrink[0], grow[1] / shrink[1], 1.0]
        usersteps = int(keys.get("steps", 0))
        flip = np.diag([-1.0, 1.0, 1.0, 1.0]) if reverse else np.eye(4)

        # relative rotation ("left"/"right"/"up"/"down")
        right, left = keys.get("right", 0), keys.get("left", 0)
        up, down = keys.get("up", 0), keys.get("down", 0)
        assert head == "move" or (right == 0 or left == 0), f'Cannot give both "left" and "right" at index {index}'
        assert head == "move" or (up == 0 or down == 0), f'Cannot give both "up" and "down" at index {index}'
        newdir = BaseTurtle._apply(BaseTurtle._zrot4(left - right) @ BaseTurtle._yrot4(down - up), RIGHT)
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
            angle = BaseTurtle._vec_angle(RIGHT, newdir)
        if left - right == 0:
            center = -radius * np.array([0.0, 0.0, np.sign(down - up)])
        elif down - up == 0:
            center = -radius * np.array([0.0, np.sign(right - left), 0.0])
        else:
            center = -radius * BaseTurtle._unit(np.cross(RIGHT, np.cross(RIGHT, newdir)))

        # absolute rotation ("xrot"/"yrot"/"zrot"/"rot"/"todir")
        rot_part, shift = BaseTurtle._rotpart(last_xform), BaseTurtle._transpart(last_xform)
        v = BaseTurtle._apply(rot_part, RIGHT)
        xr, yr, zr = keys.get("xrot", 0), keys.get("yrot", 0), keys.get("zrot", 0)
        rot_matrix, todir = keys.get("rot"), keys.get("todir")
        absangle, absaxis = None, np.zeros(3)
        if head == "arc":
            nz = len([e for e in (xr, yr, zr) if e != 0]) + (rot_matrix is not None) + (todir is not None)
            assert nz <= 1, f'Give only one of "xrot"/"yrot"/"zrot"/"rot"/"todir" at index {index}'
            if rot_matrix is not None:
                rd = rot_decode(np.asarray(rot_matrix, float))
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
            assert np.linalg.norm(projv) > 1e-9, f"Rotation acts as twist -- not a valid arc at index {index}"
            abscenter = np.sign(absangle) * radius * np.cross(absaxis, projv)
            vshift = absaxis * (np.dot(absaxis, v) / np.linalg.norm(projv)) * 2 * math.pi * radius * absangle / 360
        assert head != "arc" or (absangle or angle), '"arc" needs a rotation type and angle'

        # roll (numeric, or roll-to-a-direction)
        def _final_xform():
            if absangle is None:
                rel = np.eye(4) if angle == 0 else BaseTurtle._axis_rot4(relaxis, angle, center)
                return last_xform @ flip @ BaseTurtle._trans4([move, 0, 0]) @ rel
            return BaseTurtle._trans4(shift + vshift) @ BaseTurtle._axis_rot4(absaxis, absangle, abscenter) @ rot_part

        rollval = keys.get("roll", 0)
        rrollto, lrollto, rollto = (
            keys.get("rrollto"),
            keys.get("lrollto"),
            keys.get("rollto"),
        )
        if rollval != 0:
            roll = rollval
        elif rrollto is None and lrollto is None and rollto is None:
            roll = 0.0
        else:
            final_xform = _final_xform()
            finaldir = BaseTurtle._unit(BaseTurtle._apply(BaseTurtle._rotpart(final_xform), RIGHT))
            finalup = BaseTurtle._apply(BaseTurtle._rotpart(final_xform), UP)
            desired = rollto if rollto is not None else (rrollto if rrollto is not None else lrollto)
            assert desired is not None
            delta = (BaseTurtle._compute_spin(finaldir, desired) - BaseTurtle._compute_spin(finaldir, finalup)) % 360
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
            steps = BaseTurtle._segs2(radius, eff)
        else:
            steps = 5

        trans, pretran = [], []
        for n in range(1, steps + 1):
            frac = n / steps
            if absangle is None:
                rel = np.eye(4) if angle == 0 else BaseTurtle._axis_rot4(relaxis, frac * angle, center)
                xform = (
                    last_xform @ flip @ BaseTurtle._trans4([frac * move, 0, 0]) @ rel @ BaseTurtle._xrot4(frac * roll)
                )
            else:
                assert abscenter is not None and vshift is not None
                xform = (
                    BaseTurtle._trans4(shift + vshift * frac)
                    @ BaseTurtle._axis_rot4(absaxis, frac * absangle, abscenter)
                    @ rot_part
                    @ BaseTurtle._xrot4(frac * roll)
                )
            pre_xform = (
                last_pre
                @ BaseTurtle._zrot4(frac * twist)
                @ BaseTurtle._scale4(BaseTurtle._lerp3([1, 1, 1], scaling, frac))
            )
            trans.append(xform)
            pretran.append(pre_xform)
        return trans, pretran

    @staticmethod
    def _num(x: Any) -> float | None:
        return x if isinstance(x, (int, float)) else None

    @staticmethod
    def _run_commands(commands: list[TurtleCommand], state: list[Any], repeat: int = 1) -> list[Any]:
        for _ in range(repeat):
            for idx, cmd in enumerate(commands):
                state = BaseTurtle._command(cmd, state, idx)
        return state

    @staticmethod
    def _command(cmd: TurtleCommand, state: list[Any], index: int) -> list[Any]:
        if cmd.cmd_type == TurtleCommandType.REPEAT:
            cmds = cmd.options.get("commands")
            assert isinstance(cmds, list)
            return BaseTurtle._run_commands(cmds, state, int(cmd.size))
        if cmd.is_compound:
            tran, pretran = BaseTurtle._list_command(
                cmd.to_legacy_compound(), state[_ARCN], state[_STEP], state[_TR][-1], state[_PRE][-1], index
            )
            return BaseTurtle._tupdate(state, tran, pretran)
        p = BaseTurtle._num(cmd.parm)
        last_xform = state[_TR][-1]
        last_pre = state[_PRE][-1]
        lastpt = BaseTurtle._apply(last_xform, [0, 0, 0])
        step, angle, arcn = state[_STEP], state[_ANG], state[_ARCN]
        cmd_type = cmd.cmd_type
        parm = cmd.parm
        parm2 = cmd.parm2

        if cmd_type == TurtleCommandType.MOVE:
            diameter = (p if p is not None else 1) * step
            return BaseTurtle._tupdate(state, [last_xform @ BaseTurtle._trans4([diameter, 0, 0])], [last_pre])
        if cmd_type in (TurtleCommandType.UNTILX, TurtleCommandType.UNTILY, TurtleCommandType.UNTILZ):
            axis = {
                TurtleCommandType.UNTILX: 0,
                TurtleCommandType.UNTILY: 1,
                TurtleCommandType.UNTILZ: 2,
            }[cmd_type]
            diameter = BaseTurtle._apply(last_xform, [1, 0, 0]) - lastpt  # unit step direction
            if abs(diameter[axis]) < 1e-12:
                raise ValueError(f'"{cmd_type.value}" never reaches the goal at index {index}')
            size = (parm - lastpt[axis]) / diameter[axis]
            return BaseTurtle._tupdate(state, [last_xform @ BaseTurtle._trans4([size, 0, 0])], [last_pre])
        if cmd_type in (TurtleCommandType.XMOVE, TurtleCommandType.YMOVE, TurtleCommandType.ZMOVE):
            v = {
                TurtleCommandType.XMOVE: [1, 0, 0],
                TurtleCommandType.YMOVE: [0, 1, 0],
                TurtleCommandType.ZMOVE: [0, 0, 1],
            }[cmd_type]
            diameter = (p if p is not None else 1) * step
            return BaseTurtle._tupdate(
                state,
                [BaseTurtle._trans4([v[0] * diameter, v[1] * diameter, v[2] * diameter]) @ last_xform],
                [last_pre],
            )
        if cmd_type == TurtleCommandType.XYZMOVE:
            return BaseTurtle._tupdate(state, [BaseTurtle._trans4(parm) @ last_xform], [last_pre])
        if cmd_type in (
            TurtleCommandType.JUMP,
            TurtleCommandType.XJUMP,
            TurtleCommandType.YJUMP,
            TurtleCommandType.ZJUMP,
        ):
            if cmd_type == TurtleCommandType.JUMP:
                target = np.asarray(parm, float)
            else:
                target = np.array(lastpt, float)
                target[
                    {
                        TurtleCommandType.XJUMP: 0,
                        TurtleCommandType.YJUMP: 1,
                        TurtleCommandType.ZJUMP: 2,
                    }[cmd_type]
                ] = parm
            return BaseTurtle._tupdate(state, [BaseTurtle._trans4(target - lastpt) @ last_xform], [last_pre])
        if cmd_type == TurtleCommandType.ANGLE:
            return BaseTurtle._set(state, _ANG, parm)
        if cmd_type == TurtleCommandType.LENGTH:
            return BaseTurtle._set(state, _STEP, parm)
        if cmd_type == TurtleCommandType.SCALE:
            return BaseTurtle._set(state, _STEP, parm * step)
        if cmd_type == TurtleCommandType.ADDLENGTH:
            return BaseTurtle._set(state, _STEP, step + parm)
        if cmd_type == TurtleCommandType.ARCSTEPS:
            return BaseTurtle._set(state, _ARCN, int(parm))
        if cmd_type == TurtleCommandType.ROLL:
            return BaseTurtle._set(
                state,
                _TR,
                state[_TR][:-1] + [last_xform @ BaseTurtle._xrot4(parm if p is not None else angle)],
            )
        if cmd_type in (TurtleCommandType.RIGHT, TurtleCommandType.LEFT, TurtleCommandType.UP, TurtleCommandType.DOWN):
            rot = BaseTurtle._turtle_rotation(cmd_type, p if p is not None else angle)
            return BaseTurtle._set(state, _TR, state[_TR][:-1] + [last_xform @ rot])
        if cmd_type in (TurtleCommandType.XROT, TurtleCommandType.YROT, TurtleCommandType.ZROT):
            rot_part, shift = BaseTurtle._rotpart(last_xform), BaseTurtle._transpart(last_xform)
            rot = BaseTurtle._turtle_rotation(cmd_type, p if p is not None else angle)
            return BaseTurtle._set(state, _TR, state[_TR][:-1] + [BaseTurtle._trans4(shift) @ rot @ rot_part])
        if cmd_type == TurtleCommandType.ROT:
            rot_part, shift = BaseTurtle._rotpart(last_xform), BaseTurtle._transpart(last_xform)
            return BaseTurtle._set(
                state,
                _TR,
                state[_TR][:-1] + [BaseTurtle._trans4(shift) @ np.asarray(parm, float) @ rot_part],
            )
        if cmd_type == TurtleCommandType.SETDIR:
            rot_part, shift = BaseTurtle._rotpart(last_xform), BaseTurtle._transpart(last_xform)
            cur = BaseTurtle._apply(rot_part, [1, 0, 0])
            return BaseTurtle._set(
                state,
                _TR,
                state[_TR][:-1] + [BaseTurtle._trans4(shift) @ rot_from_to4(cur, parm) @ rot_part],
            )
        if cmd_type in (
            TurtleCommandType.ARCLEFT,
            TurtleCommandType.ARCRIGHT,
            TurtleCommandType.ARCUP,
            TurtleCommandType.ARCDOWN,
        ):
            radius = step * parm
            myangle = parm2 if BaseTurtle._num(parm2) is not None else angle
            length = 2 * math.pi * radius * abs(myangle) / 360
            center = [
                0.0,
                radius
                if cmd_type == TurtleCommandType.ARCLEFT
                else -radius
                if cmd_type == TurtleCommandType.ARCRIGHT
                else 0.0,
                -radius
                if cmd_type == TurtleCommandType.ARCDOWN
                else radius
                if cmd_type == TurtleCommandType.ARCUP
                else 0.0,
            ]
            steps = BaseTurtle._segs(abs(radius)) if arcn == 0 else arcn
            tran = [
                last_xform @ BaseTurtle._turtle_rotation(cmd_type, myangle * k / steps, center)
                for k in range(1, steps + 1)
            ]
            return BaseTurtle._tupdate(state, tran, [last_pre] * steps)
        if cmd_type in (TurtleCommandType.ARCXROT, TurtleCommandType.ARCYROT, TurtleCommandType.ARCZROT):
            radius = step * parm
            myangle = parm2 if BaseTurtle._num(parm2) is not None else angle
            length = 2 * math.pi * radius * abs(myangle) / 360
            steps = BaseTurtle._segs(abs(radius)) if arcn == 0 else arcn
            rot_part, shift = BaseTurtle._rotpart(last_xform), BaseTurtle._transpart(last_xform)
            v_dir = BaseTurtle._apply(rot_part, [1, 0, 0])
            dir_ = {
                TurtleCommandType.ARCXROT: np.array(RIGHT),
                TurtleCommandType.ARCYROT: np.array(BACK),
                TurtleCommandType.ARCZROT: np.array(UP),
            }[cmd_type]
            projv = v_dir - np.dot(dir_, v_dir) * dir_
            center = np.sign(myangle) * radius * np.cross(dir_, projv)
            vshift = dir_ * (np.dot(dir_, v_dir) / np.linalg.norm(projv)) * length
            tran = [
                BaseTurtle._trans4(shift + vshift * k / steps)
                @ BaseTurtle._turtle_rotation(cmd_type, myangle * k / steps, center)
                @ rot_part
                for k in range(1, steps + 1)
            ]
            return BaseTurtle._tupdate(state, tran, [last_pre] * steps)
        if cmd_type in (TurtleCommandType.ARCTODIR, TurtleCommandType.ARCROT):
            rot_part, shift = BaseTurtle._rotpart(last_xform), BaseTurtle._transpart(last_xform)
            v_dir = BaseTurtle._apply(rot_part, [1, 0, 0])
            rd = rot_decode(
                rot_from_to4(v_dir, parm2) if cmd_type == TurtleCommandType.ARCTODIR else np.asarray(parm2, float)
            )
            myangle, dir_ = rd[0], np.asarray(rd[1], float)
            projv = v_dir - np.dot(dir_, v_dir) * dir_
            radius = step * parm
            length = 2 * math.pi * radius * myangle / 360
            vshift = dir_ * (np.dot(dir_, v_dir) / np.linalg.norm(projv)) * length
            steps = BaseTurtle._segs(abs(radius)) if arcn == 0 else arcn
            center = radius * np.cross(dir_, projv)
            tran = [
                BaseTurtle._trans4(shift + vshift * k / steps)
                @ BaseTurtle._axis_rot4(dir_, k / steps * myangle, center)
                @ rot_part
                for k in range(1, steps + 1)
            ]
            return BaseTurtle._tupdate(state, tran, [last_pre] * steps)
        raise ValueError(f'Unknown turtle command "{cmd_type.value}" at index {index}')


class Turtle(BaseTurtle):
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

            from pybosl2.turtle3d import Turtle
            from pybosl2.path3d import Path3D
            sq = [[-1, -1], [1, -1], [1, 1], [-1, 1]]
            path = Turtle().run(["move", 20, "arcleft", 3, "move", 20, "arcleft", 3,
                                 "move", 20, "arcleft", 3, "move", 20, "arcleft", 3]).points()
            Path3D(path).path_sweep(sq, closed=True).polyhedron().show()
    """

    def run(self, commands: Iterable[Any], repeat: int = 1) -> Turtle:
        """
        Execute *commands* (optionally *repeat* times), advancing this turtle's state. Returns
        self.
        """
        super().run(commands, repeat)
        return self

    @classmethod
    def turtle3d(
        cls,
        commands: Iterable[Any],
        state: Any = RIGHT,
        transforms: bool = False,
        full_state: bool = False,
        repeat: int = 1,
    ) -> list[list[float]] | list[np.ndarray] | list[Any]:
        """One-shot BOSL2 ``turtle3d()``: run *commands* from *state* and return points (default),
        sweep *transforms*, or the *full_state*."""
        t = cls(state).run(commands, repeat)
        if full_state:
            return t.full_state()
        return t.transforms() if transforms else t.points()

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/turtle3d.py
#    Pure-Python port of BOSL2's turtle3d.scad: a 3-D turtle-graphics system. A :class:`Turtle` walks
#    through space carrying an orientation frame; a list of :class:`TurtleCommand` objects drives it,
#    and the result is either the list of points it visited or a list of 4x4 transforms suitable for
#    sweeping a profile (``path_sweep``/``sweep``).
#
#    The full command set is supported: simple commands (moves, jumps, relative and absolute turns,
#    rolls, arcs, ``repeat``) and compound commands.
#
# FileSummary: 3-D turtle graphics (the Turtle class).
# DocCategory: Paths, regions & surfaces
# FileGroup: BOSL2

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from numpy.typing import ArrayLike

    from pybosl2.caps import CapSpec, CapType
    from pybosl2.points import Point
    from pybosl2.shapes3d import Bosl2Solid

from pybosl2._helpers import rot_from_to4
from pybosl2.constants import BACK, FRONT, RIGHT, UP
from pybosl2.transforms import rot_decode

__all__ = ["turtle3d", "Turtle3D", "Turtle3DState", "TurtleCommand", "TurtleCommandType"]

# Note: the TurtleCommandType enum has members named RIGHT, UP, etc. — the
# constants from pybosl2.constants are used only for math direction vectors.
# Use ``TurtleCommandType.RIGHT`` for the command enum, ``RIGHT`` for [1,0,0].


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


@dataclass
class TurtleCommand:
    """A single turtle command with its typed parameters.

    Compound ARC commands use ``angle`` to encode the rotation amount and
    ``rotation_type`` to indicate the axis.  Use :attr:`RotationType` members
    (e.g. ``TurtleCommand.RotationType.LEFT``).
    """

    class RotationType(Enum):
        """The rotation axis/direction for a compound ARC command."""

        NONE = ""
        LEFT = "left"
        RIGHT = "right"
        UP = "up"
        DOWN = "down"
        XROT = "xrot"
        YROT = "yrot"
        ZROT = "zrot"
        ROT = "rot"
        TODIR = "todir"

    cmd_type: TurtleCommandType
    size: float | Point | None = None
    angle: float | Point | None = None
    radius: float | None = None
    steps: int | None = None
    center: Point | None = None
    grow: float | Point | None = None
    shrink: float | Point | None = None
    twist: float | None = None
    roll: float | None = None
    reverse: bool = False
    rollto: Point | None = None
    rrollto: Point | None = None
    lrollto: Point | None = None
    is_compound: bool = False
    sub_commands: list[TurtleCommand] | None = None
    rotation_type: "RotationType" = field(default=RotationType.NONE)


# -- Turtle3DState ---------------------------------------------------------


@dataclass
class Turtle3DState:
    """Immutable snapshot of the 3-D turtle's position, orientation, and settings.

    Attributes:
        transforms: The list of 4x4 rigid-body transforms visited by the turtle.
        pre_transforms: The list of pre-sweep transforms (scale/twist) at each step.
        step: The move-length scale factor.
        angle: The default turn angle in degrees.
        arcsteps: The number of arc subdivisions (0 means auto).
    """

    transforms: list[np.ndarray] = field(default_factory=lambda: [np.eye(4)])
    pre_transforms: list[np.ndarray] = field(default_factory=lambda: [np.eye(4)])
    step: float = 1.0
    angle: float = 90.0
    arcsteps: int = 0


# -- Turtle3D -----------------------------------------------------------


class Turtle3D:
    """A 3-D turtle: walk it with a command list to produce a path or a list of sweep transforms.

    The turtle starts at the origin pointing in *state* (default ``RIGHT`` = +X), with "up" along +Z.
    Commands are a flat list of :class:`TurtleCommand` objects. Turns: ``left``/``right`` (about up),
    ``up``/``down`` (about side), ``roll`` (about heading), and absolute ``xrot``/``yrot``/``zrot``.
    Arcs: ``arcleft``/``arcright``/``arcup``/``arcdown``/``arcxrot``/``arcyrot``/``arczrot``.
    ``move``/``jump`` translate; ``length``/``angle``/``scale``/``arcsteps`` set defaults; ``repeat``
    repeats. A compound :class:`TurtleCommand` (``is_compound=True``) applies several effects at once
    (``grow``/``shrink``/``twist``/``roll``/``steps``/``reverse``).

    Examples:
        A rounded square path swept into a tube:

        .. pythonscad-example::

            from pybosl2.turtle3d import turtle3d, TurtleCommand, TurtleCommandType as Tct
            from pybosl2.path3d import Path3D

            sq = [[-1, -1], [1, -1], [1, 1], [-1, 1]]
            path = turtle3d([
                TurtleCommand(Tct.MOVE, size=20),
                TurtleCommand(Tct.ARCLEFT, radius=3),
                TurtleCommand(Tct.MOVE, size=20),
                TurtleCommand(Tct.ARCLEFT, radius=3),
                TurtleCommand(Tct.MOVE, size=20),
                TurtleCommand(Tct.ARCLEFT, radius=3),
                TurtleCommand(Tct.MOVE, size=20),
                TurtleCommand(Tct.ARCLEFT, radius=3),
            ]).points()
            Path3D(path).path_sweep(sq, closed=True).polyhedron().show()
    """

    def __init__(self, state: Any = RIGHT) -> None:
        self._state = Turtle3D._init_state(state)

    def run(self, commands: Sequence[TurtleCommand], repeat: int = 1) -> Turtle3D:
        """Execute *commands* (optionally *repeat* times), advancing this turtle's state.

        Returns:
            self.
        """
        for _ in range(int(repeat)):
            for idx, cmd in enumerate(commands):
                self._command(cmd, idx)
        return self

    def points(self) -> list[list[float]]:
        """The de-duplicated list of 3-D points the turtle has visited."""
        return Turtle3D._dedup([Turtle3D._apply(T, [0, 0, 0]) for T in self._state.transforms])

    def stroke(
        self,
        width: float = 1,
        cap: CapType | CapSpec | None = None,
        closed: bool | None = None,
    ) -> "Bosl2Solid":
        """Render the turtle's current path as a 3-D stroked tube.

        Args:
            width: Stroke line width.
            cap: Optional endcap style applied to both ends.
            closed: Override whether the path is treated as closed.

        Returns:
            A :class:`Bosl2Solid` representing the tubular stroke.
        """
        from pybosl2.path3d import Path3D

        path = Path3D(self.points(), closed=False)
        if cap is not None:
            return path.stroke(width=width, closed=closed, endcap1=cap, endcap2=cap)
        return path.stroke(width=width, closed=closed)

    def transforms(self) -> list[np.ndarray]:
        """The list of 4x4 transforms (position + orientation) for sweeping a profile along the path."""
        return [self._state.transforms[i] @ self._state.pre_transforms[i] for i in range(len(self._state.transforms))]

    def full_state(self) -> Turtle3DState:
        """Return the turtle's internal :class:`Turtle3DState`."""
        return self._state

    # -- state mutation ---------------------------------------------------

    def _tupdate(self, tran: list[np.ndarray], pretran: list[np.ndarray]) -> None:
        self._state = Turtle3DState(
            transforms=self._state.transforms + tran,
            pre_transforms=self._state.pre_transforms + pretran,
            step=self._state.step,
            angle=self._state.angle,
            arcsteps=self._state.arcsteps,
        )

    def _replace_transforms(self, val: list[np.ndarray]) -> None:
        self._state = Turtle3DState(
            transforms=val,
            pre_transforms=self._state.pre_transforms,
            step=self._state.step,
            angle=self._state.angle,
            arcsteps=self._state.arcsteps,
        )

    def _with_step(self, val: float) -> None:
        self._state = Turtle3DState(
            transforms=self._state.transforms,
            pre_transforms=self._state.pre_transforms,
            step=val,
            angle=self._state.angle,
            arcsteps=self._state.arcsteps,
        )

    def _with_angle(self, val: float) -> None:
        self._state = Turtle3DState(
            transforms=self._state.transforms,
            pre_transforms=self._state.pre_transforms,
            step=self._state.step,
            angle=val,
            arcsteps=self._state.arcsteps,
        )

    def _with_arcsteps(self, val: int) -> None:
        self._state = Turtle3DState(
            transforms=self._state.transforms,
            pre_transforms=self._state.pre_transforms,
            step=self._state.step,
            angle=self._state.angle,
            arcsteps=val,
        )

    # -- math helpers --------------------------------------------------------

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
            m = Turtle3D._trans4(center_arr) @ m @ Turtle3D._trans4(-center_arr)
        return m

    @staticmethod
    def _xrot4(a: float, center: ArrayLike = (0, 0, 0)) -> np.ndarray:
        return Turtle3D._axis_rot4([1, 0, 0], a, center)

    @staticmethod
    def _yrot4(a: float, center: ArrayLike = (0, 0, 0)) -> np.ndarray:
        return Turtle3D._axis_rot4([0, 1, 0], a, center)

    @staticmethod
    def _zrot4(a: float, center: ArrayLike = (0, 0, 0)) -> np.ndarray:
        return Turtle3D._axis_rot4([0, 0, 1], a, center)

    @staticmethod
    def _apply(xform: np.ndarray, pt: ArrayLike) -> np.ndarray:
        pt_arr = np.asarray(pt, float)
        return np.asarray((xform @ np.array([pt_arr[0], pt_arr[1], pt_arr[2], 1.0]))[:3])

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
    def _init_state(state: Any) -> Turtle3DState:
        _arr = np.asarray(state, dtype=object)
        if isinstance(state, np.ndarray) and state.shape == (4, 4):
            return Turtle3DState(transforms=[np.asarray(state, float)], pre_transforms=[Turtle3D._yrot4(90)])
        if Turtle3D._is_vec3(state):
            s = np.asarray(state, float)
            updir = np.asarray(UP.vector, float) - (np.dot(UP.vector, s)) * s / np.dot(s, s)
            z = FRONT.vector if np.isclose(np.linalg.norm(updir), 0) else updir
            return Turtle3DState(transforms=[Turtle3D._frame_map(s, z)], pre_transforms=[Turtle3D._yrot4(90)])
        return Turtle3DState(
            transforms=[np.asarray(m, float) for m in state[0]],
            pre_transforms=[np.asarray(m, float) for m in state[1]],
            step=float(state[2]) if len(state) > 2 else 1.0,
            angle=float(state[3]) if len(state) > 3 else 90.0,
            arcsteps=int(state[4]) if len(state) > 4 else 0,
        )

    @staticmethod
    def _is_vec3(v: Any) -> bool:
        try:
            return len(v) == 3 and all(isinstance(x, (int, float)) for x in v)
        except TypeError:
            return False

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
            return Turtle3D._xrot4(a, center)
        if cmd_type in (TurtleCommandType.YROT, TurtleCommandType.ARCYROT):
            return Turtle3D._yrot4(a, center)
        if cmd_type in (TurtleCommandType.ZROT, TurtleCommandType.ARCZROT):
            return Turtle3D._zrot4(a, center)
        if cmd_type in (
            TurtleCommandType.RIGHT,
            TurtleCommandType.ARCRIGHT,
            TurtleCommandType.LEFT,
            TurtleCommandType.ARCLEFT,
        ):
            return Turtle3D._zrot4(a, center)
        return Turtle3D._yrot4(a, center)

    @staticmethod
    def _segs(r: float) -> int:
        return max(5, math.ceil(min(360 / 12, 2 * math.pi * max(r, 1e-6) / 2)))

    @staticmethod
    def _segs2(r: float, angle: float) -> int:
        return max(2, math.ceil(Turtle3D._segs(r) * abs(angle) / 360))

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
        native = Turtle3D._rotpart(rot_from_to4(UP, anchor_dir))[:3, :3] @ np.asarray(BACK, float)
        ad, sd = np.asarray(anchor_dir, float), np.asarray(spin_dir, float)
        perp = sd - np.dot(sd, ad) * ad
        angle = Turtle3D._vec_angle(native, perp)
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
    def _num(x: Any) -> float | None:
        return x if isinstance(x, (int, float)) else None

    # -- compound command ----------------------------------------------------

    def _compound(self, cmd: TurtleCommand, index: int) -> tuple[list[np.ndarray], list[np.ndarray]]:
        """Execute a compound turtle step using :class:`TurtleCommand` fields directly.

        Returns ``(transforms, pre-transforms)``.
        """
        last_xform = self._state.transforms[-1]
        last_pre = self._state.pre_transforms[-1]
        movescale = self._state.step
        reverse = cmd.reverse

        flip = np.diag([-1.0, 1.0, 1.0, 1.0]) if reverse else np.eye(4)

        if cmd.cmd_type == TurtleCommandType.MOVE:
            move = movescale * self._n(cmd.size, 0.0)
            radius = 0.0
            is_arc = False
        else:
            move = 0.0
            radius = movescale * (cmd.radius if isinstance(cmd.radius, (int, float)) else 0)
            is_arc = True

        twist = cmd.twist if isinstance(cmd.twist, (int, float)) else 0
        grow = Turtle3D._force_list(cmd.grow if cmd.grow is not None else 1, 2)
        shrink = Turtle3D._force_list(cmd.shrink if cmd.shrink is not None else 1, 2)
        scaling = [grow[0] / shrink[0], grow[1] / shrink[1], 1.0]
        usersteps = int(cmd.steps) if cmd.steps is not None else 0

        angle_val = cmd.angle if isinstance(cmd.angle, (int, float)) else 0
        rtype = cmd.rotation_type

        # relative rotation
        right: float = 0.0
        left: float = 0.0
        up: float = 0.0
        down: float = 0.0
        if rtype == TurtleCommand.RotationType.LEFT:
            left = angle_val
        elif rtype == TurtleCommand.RotationType.RIGHT:
            right = angle_val
        elif rtype == TurtleCommand.RotationType.UP:
            up = angle_val
        elif rtype == TurtleCommand.RotationType.DOWN:
            down = angle_val

        assert not is_arc or (right == 0 or left == 0), f'Cannot give both "left" and "right" at index {index}'
        assert not is_arc or (up == 0 or down == 0), f'Cannot give both "up" and "down" at index {index}'

        newdir = Turtle3D._apply(Turtle3D._zrot4(left - right) @ Turtle3D._yrot4(down - up), RIGHT.vector)
        if left - right == 0:
            relaxis = np.asarray(BACK.vector, float)
        elif down - up == 0:
            relaxis = np.asarray(UP.vector, float)
        else:
            relaxis = np.cross(RIGHT.vector, newdir)
        if not is_arc:
            rel_angle = 0.0
        elif left - right == 0 or down - up == 0:
            rel_angle = (down - up) + (left - right)
        else:
            rel_angle = Turtle3D._vec_angle(RIGHT.vector, newdir)
        if left - right == 0:
            center = -radius * np.array([0.0, 0.0, np.sign(down - up)])
        elif down - up == 0:
            center = -radius * np.array([0.0, np.sign(right - left), 0.0])
        else:
            center = -radius * Turtle3D._unit(np.cross(RIGHT.vector, np.cross(RIGHT.vector, newdir)))

        # absolute rotation
        rot_part, shift = Turtle3D._rotpart(last_xform), Turtle3D._transpart(last_xform)
        v = Turtle3D._apply(rot_part, RIGHT.vector)
        absangle, absaxis = None, np.zeros(3)
        if is_arc:
            if rtype == TurtleCommand.RotationType.ROT:
                rd = rot_decode(np.asarray(cmd.angle, float))
                absangle, absaxis = rd[0], np.asarray(rd[1], float)
            elif rtype == TurtleCommand.RotationType.TODIR:
                rd = rot_decode(rot_from_to4(v, cmd.angle))
                absangle, absaxis = rd[0], np.asarray(rd[1], float)
            elif rtype == TurtleCommand.RotationType.XROT:
                absangle, absaxis = angle_val, np.asarray(RIGHT.vector, float)
            elif rtype == TurtleCommand.RotationType.YROT:
                absangle, absaxis = angle_val, np.asarray(BACK.vector, float)
            elif rtype == TurtleCommand.RotationType.ZROT:
                absangle, absaxis = angle_val, np.asarray(UP.vector, float)
        if absangle is None:
            abscenter = vshift = None
        else:
            projv = v - np.dot(absaxis, v) * absaxis
            assert np.linalg.norm(projv) > 1e-9, f"Rotation acts as twist -- not a valid arc at index {index}"
            abscenter = np.sign(absangle) * radius * np.cross(absaxis, projv)
            vshift = absaxis * (np.dot(absaxis, v) / np.linalg.norm(projv)) * 2 * math.pi * radius * absangle / 360
        assert not is_arc or (absangle or rel_angle), '"arc" needs a rotation type and angle'

        # roll
        def _final_xform() -> np.ndarray:
            if absangle is None:
                rel = np.eye(4) if rel_angle == 0 else Turtle3D._axis_rot4(relaxis, rel_angle, center)
                return last_xform @ flip @ Turtle3D._trans4([move, 0, 0]) @ rel  # type: ignore[no-any-return]
            assert absangle is not None and abscenter is not None and vshift is not None
            return Turtle3D._trans4(shift + vshift) @ Turtle3D._axis_rot4(absaxis, absangle, abscenter) @ rot_part  # type: ignore[no-any-return]

        rollval = cmd.roll if isinstance(cmd.roll, (int, float)) else 0
        rrollto = cmd.rrollto
        lrollto = cmd.lrollto
        rollto = cmd.rollto
        if rollval != 0:
            roll = rollval
        elif rrollto is None and lrollto is None and rollto is None:
            roll = 0.0
        else:
            final_xform = _final_xform()
            finaldir = Turtle3D._unit(Turtle3D._apply(Turtle3D._rotpart(final_xform), RIGHT.vector))
            finalup = Turtle3D._apply(Turtle3D._rotpart(final_xform), UP.vector)
            desired = rollto if rollto is not None else (rrollto if rrollto is not None else lrollto)
            assert desired is not None
            delta = (Turtle3D._compute_spin(finaldir, desired) - Turtle3D._compute_spin(finaldir, finalup)) % 360
            if rrollto is not None or delta == 0:
                roll = delta
            elif lrollto is not None or delta > 180:
                roll = delta - 360
            else:
                roll = delta

        eff = absangle if absangle is not None else rel_angle
        if usersteps == 0 and not is_arc and roll == 0 and twist == 0:
            steps = 1
        elif usersteps != 0:
            steps = usersteps
        elif self._state.arcsteps != 0:
            steps = self._state.arcsteps
        elif radius > 0 and eff != 0:
            steps = Turtle3D._segs2(radius, eff)
        else:
            steps = 5

        trans, pretran = [], []
        for n in range(1, steps + 1):
            frac = n / steps
            if absangle is None:
                rel = np.eye(4) if rel_angle == 0 else Turtle3D._axis_rot4(relaxis, frac * rel_angle, center)
                xform = last_xform @ flip @ Turtle3D._trans4([frac * move, 0, 0]) @ rel @ Turtle3D._xrot4(frac * roll)
            else:
                assert abscenter is not None and vshift is not None
                xform = (
                    Turtle3D._trans4(shift + vshift * frac)
                    @ Turtle3D._axis_rot4(absaxis, frac * absangle, abscenter)
                    @ rot_part
                    @ Turtle3D._xrot4(frac * roll)
                )
            pre_xform = (
                last_pre @ Turtle3D._zrot4(frac * twist) @ Turtle3D._scale4(Turtle3D._lerp3([1, 1, 1], scaling, frac))
            )
            trans.append(xform)
            pretran.append(pre_xform)
        return trans, pretran

    # -- command dispatch ----------------------------------------------------

    @staticmethod
    def _n(sz: float | Point | None, default: float = 0.0) -> float:
        """Extract scalar x-component from size (float or Point)."""
        if sz is None:
            return default
        if isinstance(sz, (int, float)):
            return float(sz)
        return sz.x

    @staticmethod
    def _xyz(sz: float | Point | None) -> tuple[float, float, float]:
        """Extract (x, y, z) from size (float→scalar, Point→position)."""
        if sz is None:
            return (0.0, 0.0, 0.0)
        if isinstance(sz, (int, float)):
            return (float(sz), 0.0, 0.0)
        return (sz.x, sz.y, sz.z or 0.0)

    def _command(self, cmd: TurtleCommand, index: int) -> None:
        """Execute a single :class:`TurtleCommand`, mutating ``self._state``."""
        if cmd.cmd_type == TurtleCommandType.REPEAT:
            sub_cmds: list[TurtleCommand] = cmd.sub_commands or []
            for _ in range(int(self._n(cmd.size, 0.0))):
                for si, sc in enumerate(sub_cmds):
                    self._command(sc, si)
            return

        if cmd.is_compound:
            tran, pretran = self._compound(cmd, index)
            self._tupdate(tran, pretran)
            return

        ct = cmd.cmd_type
        last_xform = self._state.transforms[-1]
        last_pre = self._state.pre_transforms[-1]
        lastpt = Turtle3D._apply(last_xform, [0, 0, 0])
        step = self._state.step
        angle = self._state.angle
        arcn = self._state.arcsteps
        sz = cmd.size
        ang = cmd.angle

        if ct == TurtleCommandType.MOVE:
            d = self._n(sz, 1.0) * step
            self._tupdate([last_xform @ Turtle3D._trans4([d, 0, 0])], [last_pre])
        elif ct in (TurtleCommandType.XMOVE, TurtleCommandType.YMOVE, TurtleCommandType.ZMOVE):
            axis_map = {
                TurtleCommandType.XMOVE: [1, 0, 0],
                TurtleCommandType.YMOVE: [0, 1, 0],
                TurtleCommandType.ZMOVE: [0, 0, 1],
            }
            v = axis_map[ct]
            d = self._n(sz, 1.0) * step
            self._tupdate(
                [Turtle3D._trans4([v[0] * d, v[1] * d, v[2] * d]) @ last_xform],
                [last_pre],
            )
        elif ct == TurtleCommandType.XYZMOVE:
            assert sz is not None
            px, py, pz = self._xyz(sz)
            self._tupdate([Turtle3D._trans4([px, py, pz]) @ last_xform], [last_pre])
        elif ct in (TurtleCommandType.UNTILX, TurtleCommandType.UNTILY, TurtleCommandType.UNTILZ):
            axis = {TurtleCommandType.UNTILX: 0, TurtleCommandType.UNTILY: 1, TurtleCommandType.UNTILZ: 2}[ct]
            diameter = Turtle3D._apply(last_xform, [1, 0, 0]) - lastpt
            target = list(self._xyz(sz)) if sz else [0.0, 0.0, 0.0]
            if abs(diameter[axis]) < 1e-12:
                raise ValueError(f'"{ct.value}" never reaches the goal at index {index}')
            dist = (target[axis] - lastpt[axis]) / diameter[axis]
            self._tupdate([last_xform @ Turtle3D._trans4([dist, 0, 0])], [last_pre])
        elif ct in (TurtleCommandType.JUMP, TurtleCommandType.XJUMP, TurtleCommandType.YJUMP, TurtleCommandType.ZJUMP):
            if ct == TurtleCommandType.JUMP:
                assert sz is not None
                target = np.array(self._xyz(sz), float)  # type: ignore[assignment]
            else:
                target = np.array(lastpt, float)  # type: ignore[assignment]
                jump_map = {TurtleCommandType.XJUMP: 0, TurtleCommandType.YJUMP: 1, TurtleCommandType.ZJUMP: 2}
                target[jump_map[ct]] = self._n(sz, lastpt[jump_map[ct]])
            self._tupdate([Turtle3D._trans4(target - lastpt) @ last_xform], [last_pre])
        elif ct == TurtleCommandType.ANGLE:
            self._with_angle(ang if isinstance(ang, (int, float)) else 90)
        elif ct == TurtleCommandType.LENGTH:
            self._with_step(self._n(sz, 1.0))
        elif ct == TurtleCommandType.SCALE:
            self._with_step(self._n(sz, 1.0) * step)
        elif ct == TurtleCommandType.ADDLENGTH:
            self._with_step(step + self._n(sz, 1.0))
        elif ct == TurtleCommandType.ARCSTEPS:
            self._with_arcsteps(int(self._n(sz)))
        elif ct == TurtleCommandType.ROLL:
            a = ang if ang is not None else angle
            self._replace_transforms(
                self._state.transforms[:-1] + [last_xform @ Turtle3D._xrot4(a)],  # type: ignore[arg-type]
            )
        elif ct in (TurtleCommandType.RIGHT, TurtleCommandType.LEFT, TurtleCommandType.UP, TurtleCommandType.DOWN):
            a = ang if isinstance(ang, (int, float)) else angle
            rot = Turtle3D._turtle_rotation(ct, a)
            self._replace_transforms(self._state.transforms[:-1] + [last_xform @ rot])
        elif ct in (TurtleCommandType.XROT, TurtleCommandType.YROT, TurtleCommandType.ZROT):
            a = ang if isinstance(ang, (int, float)) else angle
            rot_part, shift = Turtle3D._rotpart(last_xform), Turtle3D._transpart(last_xform)
            rot = Turtle3D._turtle_rotation(ct, a)
            self._replace_transforms(self._state.transforms[:-1] + [Turtle3D._trans4(shift) @ rot @ rot_part])
        elif ct == TurtleCommandType.ROT:
            rot_part, shift = Turtle3D._rotpart(last_xform), Turtle3D._transpart(last_xform)
            self._replace_transforms(
                self._state.transforms[:-1] + [Turtle3D._trans4(shift) @ np.asarray(ang, float) @ rot_part],
            )
        elif ct == TurtleCommandType.SETDIR:
            assert sz is not None
            rot_part, shift = Turtle3D._rotpart(last_xform), Turtle3D._transpart(last_xform)
            cur = Turtle3D._apply(rot_part, [1, 0, 0])
            self._replace_transforms(
                self._state.transforms[:-1]
                + [Turtle3D._trans4(shift) @ rot_from_to4(cur, list(self._xyz(sz))) @ rot_part],
            )
        elif ct in (
            TurtleCommandType.ARCLEFT,
            TurtleCommandType.ARCRIGHT,
            TurtleCommandType.ARCUP,
            TurtleCommandType.ARCDOWN,
        ):
            assert cmd.radius is not None
            radius = step * cmd.radius
            myangle = ang if isinstance(ang, (int, float)) else angle
            center = [
                0.0,
                radius if ct == TurtleCommandType.ARCLEFT else -radius if ct == TurtleCommandType.ARCRIGHT else 0.0,
                -radius if ct == TurtleCommandType.ARCDOWN else radius if ct == TurtleCommandType.ARCUP else 0.0,
            ]
            steps = Turtle3D._segs(abs(radius)) if arcn == 0 else arcn
            tran = [
                last_xform @ Turtle3D._turtle_rotation(ct, myangle * k / steps, center) for k in range(1, steps + 1)
            ]
            self._tupdate(tran, [last_pre] * steps)
        elif ct in (TurtleCommandType.ARCXROT, TurtleCommandType.ARCYROT, TurtleCommandType.ARCZROT):
            assert cmd.radius is not None
            radius = step * cmd.radius
            myangle = ang if isinstance(ang, (int, float)) else angle
            length = 2 * math.pi * radius * abs(myangle) / 360
            steps = Turtle3D._segs(abs(radius)) if arcn == 0 else arcn
            rot_part, shift = Turtle3D._rotpart(last_xform), Turtle3D._transpart(last_xform)
            v_dir = Turtle3D._apply(rot_part, [1, 0, 0])
            dir_ = {
                TurtleCommandType.ARCXROT: np.array(RIGHT.vector),
                TurtleCommandType.ARCYROT: np.array(BACK.vector),
                TurtleCommandType.ARCZROT: np.array(UP.vector),
            }[ct]
            projv = v_dir - np.dot(dir_, v_dir) * dir_
            center = np.sign(myangle) * radius * np.cross(dir_, projv)
            vshift = dir_ * (np.dot(dir_, v_dir) / np.linalg.norm(projv)) * length
            tran = [
                Turtle3D._trans4(shift + vshift * k / steps)
                @ Turtle3D._turtle_rotation(ct, myangle * k / steps, center)
                @ rot_part
                for k in range(1, steps + 1)
            ]
            self._tupdate(tran, [last_pre] * steps)
        elif ct in (TurtleCommandType.ARCTODIR, TurtleCommandType.ARCROT):
            assert cmd.radius is not None
            rot_part, shift = Turtle3D._rotpart(last_xform), Turtle3D._transpart(last_xform)
            v_dir = Turtle3D._apply(rot_part, [1, 0, 0])
            rd = rot_decode(rot_from_to4(v_dir, ang) if ct == TurtleCommandType.ARCTODIR else np.asarray(ang, float))
            myangle, dir_ = rd[0], np.asarray(rd[1], float)
            projv = v_dir - np.dot(dir_, v_dir) * dir_
            radius = step * cmd.radius
            length = 2 * math.pi * radius * myangle / 360
            vshift = dir_ * (np.dot(dir_, v_dir) / np.linalg.norm(projv)) * length
            steps = Turtle3D._segs(abs(radius)) if arcn == 0 else arcn
            center = radius * np.cross(dir_, projv)  # type: ignore[assignment]
            tran = [
                Turtle3D._trans4(shift + vshift * k / steps)
                @ Turtle3D._axis_rot4(dir_, k / steps * myangle, center)
                @ rot_part
                for k in range(1, steps + 1)
            ]
            self._tupdate(tran, [last_pre] * steps)
        else:
            raise ValueError(f'Unknown turtle command "{ct.value}" at index {index}')


# -- convenience function ----------------------------------------------------


def turtle3d(
    commands: Sequence[TurtleCommand],
    state: Any = RIGHT,
    repeat: int = 1,
) -> Turtle3D:
    """Build a 3-D path from :class:`TurtleCommand` objects — BOSL2's ``turtle3d()``.

    Creates a :class:`Turtle3D`, runs *commands* (optionally *repeat* times),
    and returns the turtle. Access the path via :meth:`Turtle3D.points`, the
    sweep transforms via :meth:`Turtle3D.transforms`, or the raw state via
    :meth:`Turtle3D.full_state`.

    Args:
        commands: A flat list of :class:`TurtleCommand` objects.
        state: Optional starting state (default ``RIGHT`` = +X direction).
        repeat: Number of times to repeat the command list.

    Returns:
        The :class:`Turtle3D` instance after executing all commands.

    Examples:
        A rounded square path swept into a tube:

        .. pythonscad-example::

            from pybosl2.turtle3d import turtle3d, TurtleCommand, TurtleCommandType as Tct
            from pybosl2.path3d import Path3D

            sq = [[-1, -1], [1, -1], [1, 1], [-1, 1]]
            path = turtle3d([
                TurtleCommand(Tct.MOVE, size=20),
                TurtleCommand(Tct.ARCLEFT, radius=3),
                TurtleCommand(Tct.MOVE, size=20),
                TurtleCommand(Tct.ARCLEFT, radius=3),
                TurtleCommand(Tct.MOVE, size=20),
                TurtleCommand(Tct.ARCLEFT, radius=3),
                TurtleCommand(Tct.MOVE, size=20),
                TurtleCommand(Tct.ARCLEFT, radius=3),
            ]).points()
            Path3D(path).path_sweep(sq, closed=True).polyhedron().show()
    """
    return Turtle3D(state).run(commands, repeat)

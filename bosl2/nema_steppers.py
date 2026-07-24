# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: bosl2/nema_steppers.py
#    Pure-Python port of BOSL2's nema_steppers.scad: models of NEMA-standard stepper motors and the
#    masks that cut their mounting-hole pattern into a plate. :meth:`NemaSteppers.nema_stepper_motor`
#    builds a motor (body + plinth + shaft + blind screw holes) for a NEMA size; :meth:`~NemaSteppers.
#    nema_mount_mask` is the bolt-pattern-plus-plinth cutout; :meth:`~NemaSteppers.nema_motor_info`
#    returns the standard dimensions as a :class:`NemaSpec`.
#
# FileSummary: NEMA stepper-motor models and mounting masks.
# FileGroup: BOSL2

from __future__ import annotations

from dataclasses import dataclass

from bosl2._helpers import union
from bosl2.shapes3d import Bosl2Solid, cuboid, cyl

__all__ = ["NemaSteppers", "NemaSpec"]


def _union(shapes):
    return union(shapes)


@dataclass(frozen=True)
class NemaSpec:
    """Standard dimensions of a NEMA stepper motor (BOSL2 nema_motor_info())."""

    motor_width: float  # body cross-section (square)
    plinth_height: float  # raised boss around the shaft
    plinth_diam: float
    screw_spacing: float  # centre-to-centre of the mounting holes
    screw_size: float
    screw_depth: float
    shaft_diam: float


# NEMA size -> spec, transcribed from nema_steppers.scad.
_NEMA = {
    6: NemaSpec(14.0, 1.50, 11.0, 11.50, 1.6, 2.5, 4.00),
    8: NemaSpec(20.3, 1.50, 16.0, 15.40, 2.0, 2.5, 4.00),
    11: NemaSpec(28.2, 1.50, 22.0, 23.11, 2.6, 3.0, 5.00),
    14: NemaSpec(35.2, 2.00, 22.0, 26.00, 3.0, 4.5, 5.00),
    17: NemaSpec(42.3, 2.00, 22.0, 31.00, 3.0, 4.5, 5.00),
    23: NemaSpec(57.0, 1.60, 38.1, 47.00, 5.1, 4.8, 6.35),
    34: NemaSpec(86.0, 2.00, 73.0, 69.60, 6.5, 10.0, 14.00),
    42: NemaSpec(110.0, 1.50, 55.5, 88.90, 8.5, 12.7, 19.00),
}


class NemaSteppers:
    """NEMA stepper-motor models and mounting masks (BOSL2 nema_steppers.scad)."""

    @staticmethod
    def nema_motor_info(size: int) -> NemaSpec:
        """
        The :class:`NemaSpec` for a NEMA *size* (6, 8, 11, 14, 17, 23, 34 or 42) (BOSL2
        nema_motor_info()).
        """
        try:
            return _NEMA[int(size)]
        except (KeyError, ValueError):
            raise ValueError(f"Unsupported NEMA size: {size!r}")

    @staticmethod
    def nema_stepper_motor(
        size: int = 17,
        height: float = 24,
        shaft_len: float = 20,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """A model of a NEMA *size* stepper motor (BOSL2 nema_stepper_motor()).

        The motor's mounting face is at ``z = 0`` with the body below it and the plinth and *shaft_len*
        shaft projecting up; the four mounting holes are drilled into the face.

        Examples:
            A NEMA 17 motor:

            .. pythonscad-example::

                from bosl2.nema_steppers import NemaSteppers
                NemaSteppers.nema_stepper_motor(size=17).show()
        """
        s = NemaSteppers.nema_motor_info(size)
        if size < 23:
            body = cuboid(
                [s.motor_width, s.motor_width, height],
                chamfer=2 if size >= 8 else 0.5,
                edges="Z",
            )
        else:
            body = cuboid([s.motor_width, s.motor_width, height], rounding=s.screw_size, edges="Z")
        body = body.down(height / 2)  # mounting face at z=0, body below
        for sx in (-1, 1):
            for sy in (-1, 1):  # blind mounting holes at the corners
                hole = (
                    cyl(
                        height=s.screw_depth * 2,
                        diameter=s.screw_size,
                        fn=fn,
                        fa=fa,
                        fs=fs,
                    )
                    .right(sx * s.screw_spacing / 2)
                    .back(sy * s.screw_spacing / 2)
                )
                body = body - hole
        plinth = cyl(height=s.plinth_height, diameter=s.plinth_diam, fn=fn, fa=fa, fs=fs).up(s.plinth_height / 2) - cyl(
            height=s.plinth_height * 3,
            diameter=s.shaft_diam + 0.75,
            fn=fn,
            fa=fa,
            fs=fs,
        )
        shaft = cyl(height=shaft_len, diameter=s.shaft_diam, fn=fn, fa=fa, fs=fs).up(shaft_len / 2)
        return Bosl2Solid(
            (body | plinth | shaft).shape,
            size=[s.motor_width, s.motor_width, height + shaft_len],
        )

    @staticmethod
    def nema_mount_mask(
        size: int,
        depth: float = 5,
        length: float = 5,
        atype: str = "full",
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> Bosl2Solid:
        """The mounting cutout for a NEMA *size* motor -- difference it from a plate (BOSL2 nema_mount_mask()).

        Cuts the four screw holes and (``atype="full"``) the central plinth clearance. A slot length
        *length* > 0 elongates each hole so the motor can be positioned (e.g. to tension a belt).
        """
        s = NemaSteppers.nema_motor_info(size)
        pd = s.plinth_diam + slop
        sz = s.screw_size + slop
        ss = s.screw_spacing

        def slotted(d: float, cx: float = 0.0, cy: float = 0.0):
            if length > 0:
                return [
                    cyl(height=depth, diameter=d, fn=fn, fa=fa, fs=fs).back(length / 2).right(cx).back(cy),
                    cyl(height=depth, diameter=d, fn=fn, fa=fa, fs=fs).forward(length / 2).right(cx).back(cy),
                    cuboid([d, length, depth]).right(cx).back(cy),
                ]
            return [cyl(height=depth, diameter=d, fn=fn, fa=fa, fs=fs).right(cx).back(cy)]

        parts = []
        for sx in (-1, 1):
            for sy in (-1, 1):
                parts += slotted(sz, sx * ss / 2, sy * ss / 2)
        if atype == "full":
            parts += slotted(pd)
        elif atype != "screws":
            raise ValueError('nema_mount_mask(): atype must be "full" or "screws".')
        w = ss + sz + (length if length > 0 else 0)
        return Bosl2Solid(_union(parts).shape, size=[ss + sz, w, depth])

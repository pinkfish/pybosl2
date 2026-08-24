# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/parts/nema_steppers.py
#    Pure-Python port of BOSL2's nema_steppers.scad: models of NEMA-standard stepper motors and the
#    masks that cut their mounting-hole pattern into a plate. :class:`NemaMotor`
#    builds a motor (body + plinth + shaft + blind screw holes) for a NEMA size; :class:`NemaMountMask`
#    is the bolt-pattern-plus-plinth cutout; :class:`NemaSpec`
#    returns the standard dimensions.
#
# FileSummary: NEMA stepper-motor models and mounting masks.
# DocCategory: Parts library
# FileGroup: BOSL2

"""NEMA stepper-motor models and mounting masks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from pybosl2._edges_lang import Anchor
from pybosl2._helpers import union
from pybosl2.exceptions import Bosl2ValueError
from pybosl2.parts._buildable import Buildable
from pybosl2.solid import cuboid, cyl

if TYPE_CHECKING:
    from pybosl2._backend import Solid

__all__ = ["NemaMotor", "NemaMountMask", "NemaMaskType", "NemaSpec"]


class NemaMaskType(StrEnum):
    """Mounting mask cutout type for NEMA stepper motors."""

    FULL = "full"
    SCREWS = "screws"


_union = union


@dataclass(frozen=True)
class NemaSpec:
    """Standard dimensions of a NEMA stepper motor (BOSL2 nema_motor_info()).

    Construct with the NEMA size directly: ``NemaSpec(17)``.
    """

    motor_width: float
    plinth_height: float
    plinth_diam: float
    screw_spacing: float
    screw_size: float
    screw_depth: float
    shaft_diam: float

    def __init__(self, size: int) -> None:
        """Look up the NEMA motor dimensions for the given size.

        Args:
            size: NEMA motor frame size (6, 8, 11, 14, 17, 23, 34, or 42).

        Returns:
            None

        Raises:
            ValueError: If the size is not one of the supported NEMA sizes.

        """
        try:
            spec = _NEMA[int(size)]
        except (KeyError, ValueError):
            raise Bosl2ValueError(f"Unsupported NEMA size: {size!r}") from None
        object.__setattr__(self, "motor_width", spec.motor_width)
        object.__setattr__(self, "plinth_height", spec.plinth_height)
        object.__setattr__(self, "plinth_diam", spec.plinth_diam)
        object.__setattr__(self, "screw_spacing", spec.screw_spacing)
        object.__setattr__(self, "screw_size", spec.screw_size)
        object.__setattr__(self, "screw_depth", spec.screw_depth)
        object.__setattr__(self, "shaft_diam", spec.shaft_diam)


@dataclass(frozen=True)
class _NemaSpecRaw:
    """Internal storage for NEMA dimension tables (used before NemaSpec is constructed)."""

    motor_width: float
    plinth_height: float
    plinth_diam: float
    screw_spacing: float
    screw_size: float
    screw_depth: float
    shaft_diam: float


# NEMA size -> spec, transcribed from nema_steppers.scad.
_NEMA = {
    6: _NemaSpecRaw(14.0, 1.50, 11.0, 11.50, 1.6, 2.5, 4.00),
    8: _NemaSpecRaw(20.3, 1.50, 16.0, 15.40, 2.0, 2.5, 4.00),
    11: _NemaSpecRaw(28.2, 1.50, 22.0, 23.11, 2.6, 3.0, 5.00),
    14: _NemaSpecRaw(35.2, 2.00, 22.0, 26.00, 3.0, 4.5, 5.00),
    17: _NemaSpecRaw(42.3, 2.00, 22.0, 31.00, 3.0, 4.5, 5.00),
    23: _NemaSpecRaw(57.0, 1.60, 38.1, 47.00, 5.1, 4.8, 6.35),
    34: _NemaSpecRaw(86.0, 2.00, 73.0, 69.60, 6.5, 10.0, 14.00),
    42: _NemaSpecRaw(110.0, 1.50, 55.5, 88.90, 8.5, 12.7, 19.00),
}


class NemaMotor(Buildable):
    """A model of a NEMA stepper motor.

    The motor's mounting face is at ``z = 0`` with the body below it and the
    plinth and shaft projecting up; the four mounting holes are drilled into
    the face.

    Examples:
        A NEMA 17 motor:

        .. pythonscad-example::

            from pybosl2.parts.nema_steppers import NemaMotor
            NemaMotor(size=17).show()

    """

    def __init__(
        self,
        size: int = 17,
        height: float = 24,
        shaft_len: float = 20,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a NEMA stepper motor model.

        Args:
            size: NEMA motor frame size (6, 8, 11, 14, 17, 23, 34, or 42). Defaults to 17.
            height: Motor body height in mm. Defaults to 24.
            shaft_len: Shaft projection length in mm. Defaults to 20.
            fn: Number of fragments for cylinder resolution. Passed to the geometry primitives.
            fa: Minimum fragment angle. Passed to the geometry primitives.
            fs: Minimum fragment size. Passed to the geometry primitives.

        Returns:
            None

        """
        self._spec: NemaSpec = NemaSpec(size)
        self._height: float = height
        self._shaft_len: float = shaft_len
        self._size: int = size
        self._fn: int | None = fn
        self._fa: float | None = fa
        self._fs: float | None = fs
        self._solid: "Solid" | None = None

    @property
    def spec(self) -> NemaSpec:
        """The resolved :class:`NemaSpec`."""
        return self._spec

    @property
    def size(self) -> int:
        """NEMA size (6, 8, 11, 14, 17, 23, 34 or 42)."""
        return self._size

    @property
    def height(self) -> float:
        """Motor body height in mm."""
        return self._height

    @property
    def shaft_len(self) -> float:
        """Shaft projection length in mm."""
        return self._shaft_len

    @property
    def shape(self) -> "Solid":
        """Build and return the motor geometry (cached)."""
        if self._solid is not None:
            return self._solid
        s = self._spec
        ssz = self._size
        fn, fa, fs = self._fn, self._fa, self._fs
        if ssz < 23:
            body = cuboid(
                [s.motor_width, s.motor_width, self._height],
                chamfer=2 if ssz >= 8 else 0.5,
                edges=Anchor.Z,
                fn=fn,
                fa=fa,
                fs=fs,
            )
        else:
            body = cuboid(
                [s.motor_width, s.motor_width, self._height],
                rounding=s.screw_size,
                edges=Anchor.Z,
                fn=fn,
                fa=fa,
                fs=fs,
            )
        body = body.down(self._height / 2)
        for sx in (-1, 1):
            for sy in (-1, 1):
                hole = (
                    cyl(height=s.screw_depth * 2, diameter=s.screw_size, fn=fn, fa=fa, fs=fs)
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
        shaft = cyl(height=self._shaft_len, diameter=s.shaft_diam, fn=fn, fa=fa, fs=fs).up(self._shaft_len / 2)
        self._solid = (body | plinth | shaft).with_nominal_size(
            [s.motor_width, s.motor_width, self._height + self._shaft_len]
        )
        return self._solid


class NemaMountMask(Buildable):
    """The mounting cutout for a NEMA stepper motor -- difference it from a plate.

    Cuts the four screw holes and (``atype=NemaMaskType.FULL``) the central plinth
    clearance.  A slot *length* > 0 elongates each hole so the motor can be
    positioned (e.g. to tension a belt).

    Examples:
        A NEMA 17 mount mask:

        .. pythonscad-example::

            from pybosl2.parts.nema_steppers import NemaMountMask, NemaMaskType
            NemaMountMask(size=17, atype=NemaMaskType.FULL).show()

    """

    def __init__(
        self,
        size: int,
        depth: float = 5,
        length: float = 5,
        atype: NemaMaskType = NemaMaskType.FULL,
        slop: float = 0.0,
        fn: int | None = None,
        fa: float | None = None,
        fs: float | None = None,
    ) -> None:
        """Create a NEMA mounting mask cutout.

        Args:
            size: NEMA motor frame size (6, 8, 11, 14, 17, 23, 34, or 42).
            depth: Depth of the mask cutout in mm. Defaults to 5.
            length: Slot elongation length in mm; values > 0 create slots instead of round holes. Defaults to 5.
            atype: Mask cutout type, either FULL (holes + plinth clearance) or SCREWS (holes only). Defaults to FULL.
            slop: Additional clearance added to hole diameters. Defaults to 0.0.
            fn: Number of fragments for cylinder resolution. Passed to the geometry primitives.
            fa: Minimum fragment angle. Passed to the geometry primitives.
            fs: Minimum fragment size. Passed to the geometry primitives.

        Returns:
            None

        Raises:
            ValueError: If atype is not NemaMaskType.FULL or NemaMaskType.SCREWS.

        """
        if atype not in (NemaMaskType.FULL, NemaMaskType.SCREWS):
            raise Bosl2ValueError(f"nema_mount_mask: atype must be FULL or SCREWS, got {atype!r}")
        self._spec: NemaSpec = NemaSpec(size)
        self._depth: float = depth
        self._length: float = length
        self._atype: NemaMaskType = atype
        self._slop: float = slop
        self._size: int = size
        self._fn: int | None = fn
        self._fa: float | None = fa
        self._fs: float | None = fs
        self._solid: "Solid" | None = None

    @property
    def spec(self) -> NemaSpec:
        """The resolved :class:`NemaSpec`."""
        return self._spec

    @property
    def size(self) -> int:
        """NEMA size."""
        return self._size

    @property
    def mask_type(self) -> NemaMaskType:
        """Mask cutout type."""
        return self._atype

    @property
    def shape(self) -> "Solid":
        """Build and return the mount mask geometry (cached)."""
        if self._solid is not None:
            return self._solid
        s = self._spec
        fn, fa, fs = self._fn, self._fa, self._fs
        pd = s.plinth_diam + self._slop
        sz = s.screw_size + self._slop
        ss = s.screw_spacing

        def slotted(d: float, cx: float = 0.0, cy: float = 0.0) -> list["Solid"]:
            if self._length > 0:
                return [
                    cyl(height=self._depth, diameter=d, fn=fn, fa=fa, fs=fs).back(self._length / 2).right(cx).back(cy),
                    cyl(height=self._depth, diameter=d, fn=fn, fa=fa, fs=fs)
                    .forward(self._length / 2)
                    .right(cx)
                    .back(cy),
                    cuboid([d, self._length, self._depth], fn=fn, fa=fa, fs=fs).right(cx).back(cy),
                ]
            return [cyl(height=self._depth, diameter=d, fn=fn, fa=fa, fs=fs).right(cx).back(cy)]

        parts: list["Solid"] = []
        for sx in (-1, 1):
            for sy in (-1, 1):
                parts += slotted(sz, sx * ss / 2, sy * ss / 2)
        if self._atype == NemaMaskType.FULL:
            parts += slotted(pd)
        elif self._atype != NemaMaskType.SCREWS:  # pragma: no cover
            # defensive: __init__ rejects anything that is not FULL or SCREWS, and _atype is never
            # reassigned, so by here it is always one of the two.
            raise Bosl2ValueError(f"nema_mount_mask: atype must be FULL or SCREWS, got {self._atype!r}")
        w = ss + sz + (self._length if self._length > 0 else 0)
        self._solid = _union(parts).with_nominal_size([ss + sz, w, self._depth])
        return self._solid

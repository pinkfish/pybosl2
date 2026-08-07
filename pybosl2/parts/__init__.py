# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""BOSL2 parts library."""

# pybosl2.parts — BOSL2 parts library
#
# Each module provides a class with class-method factories (e.g. Gears.spur_gear()).

from pybosl2.parts.ball_bearings import BallBearings, BearingSpec, BearingType
from pybosl2.parts.bottlecaps import BottleCaps, BottleCapTexture
from pybosl2.parts.cubetruss import CubeTruss
from pybosl2.parts.enums import Gender, NutShape, ScrewDriveType, ScrewHeadType, ThreadPitchClass
from pybosl2.parts.gears import Gears
from pybosl2.parts.hinges import Hinges
from pybosl2.parts.hooks import Hooks
from pybosl2.parts.joiners import Joiners
from pybosl2.parts.linear_bearings import LinearBearings, LinearBearingSpec
from pybosl2.parts.modular_hose import ModularHose
from pybosl2.parts.nema_steppers import NemaSpec, NemaSteppers
from pybosl2.parts.polyhedra import PlatonicSolid, PolyhedronInfo, RegularPolyhedron
from pybosl2.parts.screw_drive import ScrewDrive
from pybosl2.parts.screws import Nut, Screw, ScrewHole, ScrewSpec
from pybosl2.parts.sliders import Sliders
from pybosl2.parts.threading import ThreadedNut, ThreadedRod, ThreadHelix, ThreadProfile
from pybosl2.parts.tripod_mounts import TripodMounts, manfrotto_rc2_plate
from pybosl2.parts.walls import Walls
from pybosl2.parts.wiring import Wiring

__all__ = [
    "BallBearings",
    "BearingSpec",
    "BearingType",
    "BottleCaps",
    "BottleCapTexture",
    "CubeTruss",
    "Gender",
    "Gears",
    "Hinges",
    "Hooks",
    "Joiners",
    "LinearBearings",
    "LinearBearingSpec",
    "ModularHose",
    "NemaSteppers",
    "NemaSpec",
    "NutShape",
    "PolyhedronInfo",
    "RegularPolyhedron",
    "PlatonicSolid",
    "ScrewDrive",
    "ScrewDriveType",
    "ScrewHeadType",
    "Screw",
    "ScrewHole",
    "ScrewSpec",
    "Nut",
    "Sliders",
    "Threading",
    "ThreadedNut",
    "ThreadedRod",
    "ThreadHelix",
    "ThreadPitchClass",
    "ThreadProfile",
    "TripodMounts",
    "manfrotto_rc2_plate",
    "Walls",
    "Wiring",
]

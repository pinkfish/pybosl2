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
from pybosl2.parts.cubetruss import (
    Truss,
    TrussClip,
    TrussCorner,
    TrussFoot,
    TrussJoiner,
    TrussSegment,
    TrussSupport,
    TrussUClip,
    truss_dist,
)
from pybosl2.parts.enums import Gender, NutShape, ScrewDriveType, ScrewHeadType, ThreadPitchClass
from pybosl2.parts.gears import (
    BevelGear,
    GearSpec,
    GearToothProfile,
    HerringboneGear,
    Rack,
    Rack2d,
    RingGear,
    SpurGear,
    SpurGear2d,
    Worm,
    WormGear,
)
from pybosl2.parts.hinges import KnuckleHinge, KnuckleHingePair, LivingHingeMask, SnapLock, SnapSocket
from pybosl2.parts.hooks import HoleType, RingHook
from pybosl2.parts.joiners import Dovetail, SnapPin, SnapPinSocket
from pybosl2.parts.linear_bearings import LinearBearings, LinearBearingSpec
from pybosl2.parts.modular_hose import HoseSegment, HoseType, modular_hose_radius
from pybosl2.parts.nema_steppers import NemaMaskType, NemaMotor, NemaMountMask, NemaSpec
from pybosl2.parts.polyhedra import PlatonicSolid, PolyhedronInfo, RegularPolyhedron
from pybosl2.parts.screw_drive import (
    HexDriveMask,
    PhillipsMask,
    PhillipsSpec,
    RobertsonMask,
    RobertsonSpec,
    TorxMask,
    TorxMask2d,
    TorxSpec,
    hex_mask,
)
from pybosl2.parts.screws import Nut, Screw, ScrewHole, ScrewSpec
from pybosl2.parts.sliders import Rail, Slider
from pybosl2.parts.threading import ThreadedNut, ThreadedRod, ThreadHelix, ThreadProfile
from pybosl2.parts.tripod_mounts import ManfrottoRC2Plate, manfrotto_rc2_plate
from pybosl2.parts.walls import (
    CorrugatedWall,
    NarrowingStrut,
    SparseAxis,
    SparseCuboid,
    SparseWall,
    ThinningTriangle,
    ThinningWall,
)
from pybosl2.parts.wiring import WireBundle, hex_offsets

__all__ = [
    "BallBearings",
    "BearingSpec",
    "BearingType",
    "BottleCaps",
    "BottleCapTexture",
    "TrussSegment",
    "Truss",
    "TrussCorner",
    "TrussSupport",
    "TrussClip",
    "TrussFoot",
    "TrussUClip",
    "TrussJoiner",
    "truss_dist",
    "Gender",
    "BevelGear",
    "GearToothProfile",
    "HerringboneGear",
    "Rack",
    "Rack2d",
    "RingGear",
    "SpurGear",
    "SpurGear2d",
    "Worm",
    "WormGear",
    "GearSpec",
    "KnuckleHinge",
    "KnuckleHingePair",
    "LivingHingeMask",
    "SnapLock",
    "SnapSocket",
    "HoleType",
    "RingHook",
    "Dovetail",
    "SnapPin",
    "SnapPinSocket",
    "LinearBearings",
    "LinearBearingSpec",
    "HoseSegment",
    "HoseType",
    "modular_hose_radius",
    "NemaMaskType",
    "NemaMotor",
    "NemaMountMask",
    "NemaSpec",
    "NutShape",
    "PolyhedronInfo",
    "RegularPolyhedron",
    "PlatonicSolid",
    "HexDriveMask",
    "PhillipsMask",
    "PhillipsSpec",
    "RobertsonMask",
    "RobertsonSpec",
    "TorxMask",
    "TorxMask2d",
    "TorxSpec",
    "hex_mask",
    "ScrewDriveType",
    "ScrewHeadType",
    "Screw",
    "ScrewHole",
    "ScrewSpec",
    "Nut",
    "Slider",
    "Rail",
    "ThreadedNut",
    "ThreadedRod",
    "ThreadHelix",
    "ThreadPitchClass",
    "ThreadProfile",
    "CorrugatedWall",
    "NarrowingStrut",
    "SparseAxis",
    "SparseCuboid",
    "SparseWall",
    "ThinningTriangle",
    "ThinningWall",
    "ManfrottoRC2Plate",
    "manfrotto_rc2_plate",
    "WireBundle",
    "hex_offsets",
]

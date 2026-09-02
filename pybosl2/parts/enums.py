# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# DocCategory: Parts library
# LibFile: pybosl2/parts/enums.py
# FileSummary: Strongly-typed enums for the pybosl2 parts library.
# FileGroup: BOSL2

"""Strongly-typed enums for the pybosl2 parts library."""

from enum import StrEnum

# Gender lives in the foundations layer: the SDF backend's joiners need it, and an L3
# module may not import L5 (SPEC A-1). Re-exported here because this is where every caller
# looks for a parts vocabulary.
from pybosl2.enums import Gender as Gender


class ScrewHeadType(StrEnum):
    """Screw-head style for :func:`screw` and :func:`screw_hole`."""

    NONE = "none"
    HEX = "hex"
    SOCKET = "socket"
    SOCKET_RIBBED = "socket ribbed"
    BUTTON = "button"
    PAN = "pan"
    ROUND = "round"
    FLAT = "flat"


class ScrewDriveType(StrEnum):
    """Screw-drive recess type for :func:`screw`."""

    NONE = "none"
    HEX = "hex"
    SLOT = "slot"


class NutShape(StrEnum):
    """Nut / washer outer shape."""

    HEX = "hex"
    SQUARE = "square"


class ThreadPitchClass(StrEnum):
    """ISO metric thread pitch class for selecting coarse/fine/extra-fine/super-fine threads."""

    COARSE = "coarse"
    FINE = "fine"
    EXTRA_FINE = "extra_fine"
    SUPER_FINE = "super_fine"
    NONE = "none"

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
    """Screw-head style for :func:`screw` and :func:`screw_hole`.

    Two pairs build the **same** solid, deliberately, and say so here because nothing else did
    (T105). ``SOCKET_RIBBED`` is modelled as ``SOCKET``: the ribbing is a knurl on the cylinder
    that no dimension in the tables describes. ``ROUND`` is modelled as ``PAN``, both as the domed
    head the pan table gives. Asking for either of the two unmodelled spellings is not an error --
    the head it stands in for is the right shape to a tenth of a millimetre -- but it is not a
    distinct solid, and a caller comparing two screws should not expect one.
    """

    NONE = "none"
    HEX = "hex"
    SOCKET = "socket"
    SOCKET_RIBBED = "socket ribbed"
    BUTTON = "button"
    PAN = "pan"
    ROUND = "round"
    FLAT = "flat"


class ScrewDriveType(StrEnum):
    """Screw-drive recess type for :func:`screw`.

    ``HEX`` is cut only where a head's table carries hex-socket dimensions: on ``NONE``,
    ``SOCKET``, ``SOCKET_RIBBED`` and ``BUTTON`` heads. On ``HEX`` heads that is right -- the drive
    is a wrench on the head, not a recess -- and on ``PAN``, ``ROUND`` and ``FLAT`` it is a gap,
    measured and listed in `tests/test_screw_drives_are_cut.py` rather than guessed at, since which
    standards pair a countersunk head with a hex socket is a question about screws (T105).
    """

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

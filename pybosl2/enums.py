# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# DocCategory: Foundational
# LibFile: pybosl2/enums.py
# FileSummary: Strongly-typed enums for pybosl2.
# FileGroup: BOSL2

"""Strongly-typed enums for pybosl2."""

from enum import StrEnum


class AttachTag(StrEnum):
    """Attachment tags for boolean resolution.

    These values determine how attached shapes are combined with their parent
    shape during realization (e.g. keep/remove/intersect).
    """

    KEEP = "keep"
    REMOVE = "remove"
    INTERSECT = "intersect"


class RoundingMethod(StrEnum):
    """Corner-rounding strategy for :func:`round_corners` and :func:`smooth_path`."""

    CIRCLE = "circle"
    SMOOTH = "smooth"
    CHAMFER = "chamfer"


class VNFStyle(StrEnum):
    """Quad-subdivision style for :func:`vnf_vertex_array` and related functions."""

    DEFAULT = "default"
    ALT = "alt"
    MIN_EDGE = "min_edge"
    MIN_AREA = "min_area"
    CONVEX = "convex"
    CONCAVE = "concave"
    QUINCUNX = "quincunx"
    QUAD = "quad"
    FLIP1 = "flip1"
    FLIP2 = "flip2"


class SweepMethod(StrEnum):
    """Cross-section orientation method for :func:`path_sweep`."""

    INCREMENTAL = "incremental"
    MANUAL = "manual"
    NATURAL = "natural"


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


class SkinMethod(StrEnum):
    """Vertex-connection method for :func:`skin` / :meth:`VNF.from_skin`."""

    DIRECT = "direct"
    REINDEX = "reindex"


class PartitionCutType(StrEnum):
    """Cut profile style for :func:`partition` and :func:`partition_mask`."""

    FLAT = "flat"
    SAWTOOTH = "sawtooth"
    SINEWAVE = "sinewave"
    COMB = "comb"
    FINGER = "finger"
    DOVETAIL = "dovetail"
    HAMMERHEAD = "hammerhead"
    JIGSAW = "jigsaw"
    SQUARE = "square"
    TRIANGLE = "triangle"
    HALFSINE = "halfsine"
    SEMICIRCLE = "semicircle"


class NutShape(StrEnum):
    """Nut / washer outer shape."""

    HEX = "hex"
    SQUARE = "square"


class ScrewDriveType(StrEnum):
    """Screw-drive recess type for :func:`screw`."""

    NONE = "none"
    HEX = "hex"
    SLOT = "slot"


class Measure(StrEnum):
    """Rounding size specification for :func:`round_corners`."""

    RADIUS = "radius"
    CUT = "cut"
    JOINT = "joint"
    WIDTH = "width"


class EdgeMode(StrEnum):
    """Edge-treatment mode for SDF primitives."""

    ROUND = "round"
    CHAMFER = "chamfer"


class SamplingType(StrEnum):
    """Resampling strategy for :func:`skin` and related functions."""

    LENGTH = "length"
    SEGMENT = "segment"


class ResampleMethod(StrEnum):
    """Resampling method for :func:`rot_resample`."""

    LENGTH = "length"
    COUNT = "count"


class StaggerMode(StrEnum):
    """Stagger mode for :func:`grid_copies`."""

    NONE = "none"
    STANDARD = "standard"
    ALT = "alt"


class Gender(StrEnum):
    """Part gender for dovetail joints."""

    MALE = "male"
    FEMALE = "female"

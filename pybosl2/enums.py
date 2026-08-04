# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# DocCategory: Foundational
# LibFile: pybosl2/enums.py
# FileSummary: Strongly-typed enums for pybosl2.
# FileGroup: BOSL2

from enum import StrEnum


class AttachTag(StrEnum):
    """Attachment tags for boolean resolution.

    These values determine how attached shapes are combined with their parent
    shape during realization (e.g. keep/remove/intersect).
    """

    KEEP = "keep"
    REMOVE = "remove"
    INTERSECT = "intersect"

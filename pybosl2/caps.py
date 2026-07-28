# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Sweep and skin end-cap specifications.

Provides the :data:`CapsSpec` type alias and the :func:`_norm_caps` normaliser
shared by :mod:`pybosl2.skin` and :mod:`pybosl2.beziers` for specifying
whether to add end caps when sweeping a shape along a path.
"""

from __future__ import annotations

from typing import Sequence, Union

import numpy as np

__all__ = ["CapsSpec", "_norm_caps"]

#: A cap specification used by every sweep/skin entry point. Can be a single
#: ``bool`` (same cap on both ends), a ``Sequence[bool]`` (per-end caps), or
#: ``None`` to take the call's own default.
CapsSpec = Union[bool, "Sequence[bool]", None]


def _norm_caps(caps: CapsSpec, closed: bool = False, default: bool = True) -> list[bool]:
    """Normalize a :data:`CapsSpec` to a plain ``[cap1, cap2]`` bool pair.

    A single bool caps both ends alike, a 2-sequence caps each end
    separately, and ``None`` falls back to *default*. A *closed* sweep
    loops back on itself and so has no ends to cap -- it is always
    uncapped, whatever was asked for.

    Args:
        caps: The cap specification to normalize.
        closed: Whether the sweep is closed (no caps).
        default: The default cap state when *caps* is ``None``.

    Returns:
        A ``[cap1, cap2]`` pair of bools.
    """
    if closed:
        return [False, False]
    if caps is None:
        return [default, default]
    if isinstance(caps, (list, tuple, np.ndarray)):
        return [bool(caps[0]), bool(caps[1])]
    return [bool(caps), bool(caps)]

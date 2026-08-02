# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/isosurface.py
#    Backward-compatibility shim.  Metaball primitives have been merged into
#    :mod:`pybosl2.vnf` as :class:`VNF` static methods and the :class:`_Metaball` /
#    :class:`_MetaballSpec` classes.  This module re-exports everything under the
#    original names so existing imports keep working.
#
# FileSummary: Backward-compat shim for metaball primitives (now on VNF).
# DocCategory: Paths, regions & surfaces
# FileGroup: BOSL2

from __future__ import annotations

from typing import Any

from pybosl2.vnf import VNF as _VNF
from pybosl2.vnf import (
    _Metaball as Metaball,
)
from pybosl2.vnf import (
    _MetaballSpec as MetaballSpec,
)

__all__ = [
    "Metaball",
    "MetaballSpec",
    "mb_sphere",
    "mb_cuboid",
    "mb_torus",
    "mb_capsule",
    "mb_disk",
    "mb_octahedron",
    "mb_connector",
]


def mb_sphere(*args: Any, **kwargs: Any) -> Metaball:
    return _VNF.mb_sphere(*args, **kwargs)


def mb_cuboid(*args: Any, **kwargs: Any) -> Metaball:
    return _VNF.mb_cuboid(*args, **kwargs)


def mb_torus(*args: Any, **kwargs: Any) -> Metaball:
    return _VNF.mb_torus(*args, **kwargs)


def mb_capsule(*args: Any, **kwargs: Any) -> Metaball:
    return _VNF.mb_capsule(*args, **kwargs)


def mb_disk(*args: Any, **kwargs: Any) -> Metaball:
    return _VNF.mb_disk(*args, **kwargs)


def mb_octahedron(*args: Any, **kwargs: Any) -> Metaball:
    return _VNF.mb_octahedron(*args, **kwargs)


def mb_connector(*args: Any, **kwargs: Any) -> Metaball:
    return _VNF.mb_connector(*args, **kwargs)

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Abstract base for Bosl2Shape2D and Bosl2Solid, declaring the full common
interface: transforms, directional moves, and CSG operators.  Both subclasses
already implement every method concretely; this class exists so a single
``isinstance`` or type annotation covers both 2-D and 3-D shapes.
"""

# LibFile: pybosl2/_shape.py
# FileGroup: BOSL2

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from pybosl2.color import Colorable
from pybosl2.distributors import Distributable

__all__ = ["Bosl2Shape"]


class Bosl2Shape(Colorable, Distributable):
    """Abstract interface shared by :class:`~pybosl2.shapes2d.Bosl2Shape2D`
    and :class:`~pybosl2.shapes3d.Bosl2Solid`.

    Every method here is abstract — each subclass provides its own concrete
    implementation tuned to 2-D or 3-D geometry.
    """

    # -- transforms -----------------------------------------------------------

    @abstractmethod
    def translate(self, v: Any) -> Bosl2Shape: ...

    move = translate  # type: ignore[assignment]

    @abstractmethod
    def rotate(self, *a: Any, **k: Any) -> Bosl2Shape: ...

    rot = rotate  # type: ignore[assignment]

    @abstractmethod
    def mirror(self, v: Any) -> Bosl2Shape: ...

    @abstractmethod
    def scale(self, v: Any) -> Bosl2Shape: ...

    @abstractmethod
    def multmatrix(self, m: Any) -> Bosl2Shape: ...

    @abstractmethod
    def right(self, x: float) -> Bosl2Shape: ...

    @abstractmethod
    def left(self, x: float) -> Bosl2Shape: ...

    @abstractmethod
    def back(self, y: float) -> Bosl2Shape: ...

    @abstractmethod
    def forward(self, y: float) -> Bosl2Shape: ...

    fwd = forward  # type: ignore[assignment]

    # -- CSG operators --------------------------------------------------------

    @abstractmethod
    def __or__(self, other: Any) -> Bosl2Shape: ...

    @abstractmethod
    def __and__(self, other: Any) -> Bosl2Shape: ...

    @abstractmethod
    def __sub__(self, other: Any) -> Bosl2Shape: ...

    @abstractmethod
    def __ror__(self, other: Any) -> Bosl2Shape: ...

    @abstractmethod
    def __rand__(self, other: Any) -> Bosl2Shape: ...

    @abstractmethod
    def __rsub__(self, other: Any) -> Bosl2Shape: ...

    @abstractmethod
    def __add__(self, other: Any) -> Bosl2Shape: ...

    @abstractmethod
    def __radd__(self, other: Any) -> Bosl2Shape: ...

    @abstractmethod
    def __mul__(self, other: Any) -> Bosl2Shape: ...

    @abstractmethod
    def __rmul__(self, other: Any) -> Bosl2Shape: ...

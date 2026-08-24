# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# DocCategory: internal

"""The delegating half of the part contract: :class:`Buildable`.

Every part resolves its inputs into a frozen spec, exposes its derived dimensions as properties,
and builds geometry lazily under a ``shape`` property (SPEC C-14). What a caller then *does* with
that shape -- display it, save it, measure it -- is identical for all 53 of them, so it lives here
once rather than being written out per class (PLAN O-1c: a mixin is inherited or it is deleted).

A part only has to provide ``shape``; the rest follows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import os
    from pathlib import Path as FilePath

    from pybosl2._backend import Solid
    from pybosl2.bounds import Bounds3D


class Buildable:
    """Display, measure and save whatever a part's ``shape`` property builds.

    Mixed into every part class so a caller never has to reach inside one to do the obvious thing
    (SPEC S-51): ``Screw("M6", length=20).export("screw.stl")`` rather than
    ``Screw("M6", length=20).shape.export(...)``.
    """

    @property
    def shape(self) -> "Solid":  # pragma: no cover - every part overrides this
        """The built geometry. Each part supplies its own (SPEC C-14)."""
        raise NotImplementedError

    def show(self) -> "Solid":
        """Hand this part's shape to the renderer, and return it.

        Returns:
            The shape, so the call can be chained or assigned (SPEC S-49).

        Examples:
            .. pythonscad-example::

                from pybosl2.parts import Screw

                Screw("M6", length=20).show()

        """
        self.shape.show()
        return self.shape

    def export(
        self, path: "str | os.PathLike[str]", *, file_format: str | None = None, check: bool = True
    ) -> "FilePath":
        """Write this part to a mesh file (SPEC S-53, S-51).

        Args:
            path: destination file; its suffix picks the format (``.stl``, ``.obj``, ``.off``,
                ``.ply``).
            file_format: explicit format name, overriding the suffix.
            check: refuse to write a mesh that is open or wound inside out (SPEC S-55).

        Returns:
            The path written.

        Raises:
            Bosl2ValueError: If the format is unknown, or the mesh fails the *check*.

        Examples:
            .. pythonscad-example::

                from pybosl2.parts import Screw

                screw = Screw("M6", length=20)
                screw.export("m6x20.stl")
                screw.show()

        """
        return self.shape.export(path, file_format=file_format, check=check)

    def bounds(self) -> "Bounds3D":
        """Measure this part's shape without reaching inside it (SPEC S-2b).

        Returns:
            The :class:`~pybosl2.bounds.Bounds3D` box of the built geometry. Note that a part's
            ``size`` is its *nominal* anchor box and need not match (SPEC S-2a).

        Examples:
            .. pythonscad-example::

                from pybosl2.parts import Screw

                screw = Screw("M6", length=20)
                print(screw.bounds().height)
                screw.show()

        """
        return self.shape.bounds()

# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause
# DocCategory: Foundational
# LibFile: pybosl2/export.py
# FileSummary: Mesh writers -- STL, OBJ, OFF, PLY -- straight from a VNF, with no CAD runtime.
# FileGroup: BOSL2

"""Write a mesh to a file (SPEC S-53, S-54, S-55).

The way out of the library. :meth:`pybosl2.vnf.VNF.export` and
:meth:`~pybosl2._backend.Solid.export` are the calls a user makes; this module holds the format
writers behind them.

Every format here is **pure data**, so it is written by pybosl2 itself with no native runtime
involved (S-54, A-2): a mesh built with nothing but numpy can be saved with nothing but numpy.
Formats that are a CAD kernel's own (3MF, AMF) are the kernel's job and are refused by name rather
than half-written.

Winding follows the rest of the library: faces counter-clockwise seen from outside, so
:meth:`~pybosl2.vnf.VNF.volume` is positive for a solid. Normals are computed per face on the way
out where the format wants them.
"""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

import numpy as np

from pybosl2.exceptions import Bosl2ValueError

if TYPE_CHECKING:
    from pathlib import Path

    from pybosl2.vnf import VNF

__all__ = ["FORMATS", "format_for", "write_mesh"]

#: The mesh formats pybosl2 writes itself, mapped from the file suffixes that select them.
#: ``"stl"`` is binary; ``"stla"`` is the ASCII form, chosen with an explicit ``format=``.
FORMATS: dict[str, str] = {
    ".stl": "stl",
    ".obj": "obj",
    ".off": "off",
    ".ply": "ply",
}

#: Formats a CAD kernel owns. Named here so the refusal can say what is missing rather than
#: writing a file a slicer will reject (SPEC S-54).
_DELEGATED: dict[str, str] = {
    ".3mf": "3MF",
    ".amf": "AMF",
    ".dxf": "DXF",
    ".svg": "SVG",
}


def format_for(path: "Path | str", explicit: str | None = None) -> str:
    """Return the writer name for *path*, or the *explicit* override.

    Args:
        path: the destination file; its suffix selects the format.
        explicit: a format name that overrides the suffix (``"stl"``, ``"stla"``, ``"obj"``,
            ``"off"``, ``"ply"``).

    Returns:
        The writer name.

    Raises:
        Bosl2ValueError: If the format is unknown, or belongs to a CAD kernel this library does
            not carry.

    Examples:
        >>> format_for("bracket.stl")
        'stl'
        >>> format_for("bracket.stl", explicit="stla")
        'stla'

    """
    if explicit is not None:
        name = explicit.lower().lstrip(".")
        if name not in {*FORMATS.values(), "stla"}:
            raise Bosl2ValueError(
                f"export(): unknown format {explicit!r}; pybosl2 writes "
                f"{', '.join(sorted({*FORMATS.values(), 'stla'}))}."
            )
        return name

    suffix = str(path).lower()
    suffix = suffix[suffix.rfind(".") :] if "." in suffix else ""
    if suffix in FORMATS:
        return FORMATS[suffix]
    if suffix in _DELEGATED:
        raise Bosl2ValueError(
            f"export(): {_DELEGATED[suffix]} is a CAD kernel's own format, not one pybosl2 writes. "
            f"Export {', '.join(sorted(FORMATS))} here and convert, or drive the PythonSCAD app."
        )
    raise Bosl2ValueError(
        f"export(): cannot tell the format from {str(path)!r} -- use one of "
        f"{', '.join(sorted(FORMATS))}, or pass format= explicitly."
    )


def _triangles(mesh: "VNF") -> "np.ndarray":
    """Return every face as a triangle, fanning any polygon with more than three corners."""
    vertices = np.asarray(mesh.vertices, dtype=float)
    tris: list[list[int]] = []
    for face in mesh.faces:
        for i in range(1, len(face) - 1):
            tris.append([face[0], face[i], face[i + 1]])
    if not tris:
        raise Bosl2ValueError("export(): the mesh has no faces to write.")
    return np.asarray(vertices[np.asarray(tris, dtype=int)], dtype=float)


def _normals(tris: "np.ndarray") -> "np.ndarray":
    """Return the unit normal of each triangle, derived from its winding."""
    edge1 = tris[:, 1] - tris[:, 0]
    edge2 = tris[:, 2] - tris[:, 0]
    normals = np.cross(edge1, edge2)
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    return np.asarray(np.divide(normals, lengths, out=np.zeros_like(normals), where=lengths > 0), dtype=float)


def _write_stl_binary(mesh: "VNF", path: "Path") -> None:
    tris = _triangles(mesh)
    normals = _normals(tris)
    with path.open("wb") as handle:
        handle.write(b"pybosl2".ljust(80, b"\0"))
        handle.write(struct.pack("<I", len(tris)))
        for normal, tri in zip(normals, tris, strict=True):
            handle.write(struct.pack("<3f", *normal))
            for point in tri:
                handle.write(struct.pack("<3f", *point))
            handle.write(struct.pack("<H", 0))


def _write_stl_ascii(mesh: "VNF", path: "Path") -> None:
    tris = _triangles(mesh)
    normals = _normals(tris)
    lines = ["solid pybosl2"]
    for normal, tri in zip(normals, tris, strict=True):
        lines.append("  facet normal {:.6e} {:.6e} {:.6e}".format(*normal))
        lines.append("    outer loop")
        lines.extend("      vertex {:.6e} {:.6e} {:.6e}".format(*point) for point in tri)
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append("endsolid pybosl2\n")
    path.write_text("\n".join(lines))


def _write_obj(mesh: "VNF", path: "Path") -> None:
    lines = ["# written by pybosl2"]
    lines.extend("v {:.6f} {:.6f} {:.6f}".format(*point) for point in mesh.vertices)
    # OBJ indexes from 1
    lines.extend("f " + " ".join(str(i + 1) for i in face) for face in mesh.faces)
    path.write_text("\n".join(lines) + "\n")


def _write_off(mesh: "VNF", path: "Path") -> None:
    edges = sum(len(face) for face in mesh.faces)
    lines = ["OFF", f"{len(mesh.vertices)} {len(mesh.faces)} {edges}"]
    lines.extend("{:.6f} {:.6f} {:.6f}".format(*point) for point in mesh.vertices)
    lines.extend(f"{len(face)} " + " ".join(str(i) for i in face) for face in mesh.faces)
    path.write_text("\n".join(lines) + "\n")


def _write_ply(mesh: "VNF", path: "Path") -> None:
    lines = [
        "ply",
        "format ascii 1.0",
        "comment written by pybosl2",
        f"element vertex {len(mesh.vertices)}",
        "property float x",
        "property float y",
        "property float z",
        f"element face {len(mesh.faces)}",
        "property list uchar int vertex_index",
        "end_header",
    ]
    lines.extend("{:.6f} {:.6f} {:.6f}".format(*point) for point in mesh.vertices)
    lines.extend(f"{len(face)} " + " ".join(str(i) for i in face) for face in mesh.faces)
    path.write_text("\n".join(lines) + "\n")


_WRITERS = {
    "stl": _write_stl_binary,
    "stla": _write_stl_ascii,
    "obj": _write_obj,
    "off": _write_off,
    "ply": _write_ply,
}


def open_edges(mesh: "VNF") -> list[tuple[int, int]]:
    """Return the edges that fewer or more than two faces share.

    An empty list means the surface closes: every edge is walked once in each direction, which is
    what a slicer means by watertight.

    Args:
        mesh: the mesh to inspect.

    Returns:
        The offending vertex-index pairs, lowest-index-first, deduplicated.

    Examples:
        >>> from pybosl2 import Path2D
        >>> box = Path2D([[-5, -5], [5, -5], [5, 5], [-5, 5]], closed=True).linear_sweep(height=10)
        >>> open_edges(box.vnf)
        []

    """
    counts: dict[tuple[int, int], int] = {}
    for face in mesh.faces:
        for i, start in enumerate(face):
            end = face[(i + 1) % len(face)]
            key = (start, end) if start < end else (end, start)
            counts[key] = counts.get(key, 0) + 1
    return sorted(edge for edge, count in counts.items() if count != 2)


def _is_vnf(mesh: object) -> bool:
    """Return True if *mesh* is a VNF, importing it lazily to keep this module CAD-runtime free."""
    from pybosl2.vnf import VNF

    return isinstance(mesh, VNF)


def check_exportable(mesh: "VNF") -> None:
    """Raise if *mesh* is not a solid a slicer would accept (SPEC S-55).

    A mesh that is open or wound inside-out is a bug the caller wants to hear about here, not from
    their slicer an hour later: an inverted mesh exports cleanly on its own and then *adds*
    material wherever it is used to cut.

    Args:
        mesh: the mesh about to be written.

    Raises:
        Bosl2ValueError: If the mesh is empty, has open edges, or is wound inside out.

    """
    from pybosl2.vnf import VNF

    if not isinstance(mesh, VNF):
        # A shape is the natural thing to reach for here, because `Shape.export()` takes one.
        # Meshing it implicitly is the one thing this must not do: deciding when a field becomes
        # a mesh is the caller's call, not the exporter's (SPEC T3). So say what to call instead.
        raise Bosl2ValueError(
            f"export(): expected a VNF mesh, got {type(mesh).__name__}. Call `shape.export(path)` "
            f"to write a shape directly, or `shape.vnf()` to mesh it yourself first -- this "
            f"function will not mesh for you, because when a shape is meshed is your decision."
        )
    if not mesh.vertices or not mesh.faces:
        raise Bosl2ValueError("export(): the mesh is empty -- there is nothing to write.")
    holes = open_edges(mesh)
    if holes:
        raise Bosl2ValueError(
            f"export(): the mesh is not watertight -- {len(holes)} edge(s) are not shared by exactly "
            f"two faces, starting at {holes[0]}. Pass check=False to write it anyway (an open "
            f"surface is legal in STL, but no slicer will print it)."
        )
    if mesh.volume() < 0:
        raise Bosl2ValueError(
            "export(): the mesh is wound inside out (negative volume), so it would add material "
            "wherever it was used to cut. Fix the winding with VNF.reverse(), or pass check=False."
        )


def write_mesh(mesh: "VNF", path: "Path", *, file_format: str | None = None, check: bool = True) -> "Path":
    """Write *mesh* to *path* (SPEC S-53).

    Args:
        mesh: the mesh to write.
        path: the destination; its suffix picks the format unless *format* says otherwise.
        file_format: explicit format name, overriding the suffix. Spelled with the ``file_``
            prefix because ``format`` is a Python builtin.
        check: validate watertightness and winding first (SPEC S-55). ``False`` for a surface that
            is open on purpose.

    Returns:
        The path written, so the call can be chained or logged.

    Raises:
        Bosl2ValueError: If the format is unknown, or *check* is on and the mesh is not a solid.

    """
    name = format_for(path, file_format)
    if check:
        check_exportable(mesh)
    elif not _is_vnf(mesh):
        # `check=False` waives the *watertightness* checks, not the type -- without this the
        # wrong argument reached a writer and failed on a backend attribute instead.
        raise Bosl2ValueError(
            f"export(): expected a VNF mesh, got {type(mesh).__name__}. Call `shape.export(path)` "
            f"to write a shape directly, or `shape.vnf()` to mesh it yourself first."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    _WRITERS[name](mesh, path)
    return path

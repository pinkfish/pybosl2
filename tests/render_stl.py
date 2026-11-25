# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

"""Real-render helpers for the STL tests (pybosl2/tests/test_stl_render.py).

Unlike the mock-based unit tests, these drive the REAL PythonSCAD binary in a subprocess to build
a pybosl2 object, export it to an STL mesh, and then load that mesh back to measure it (bounding
box, triangle count, volume, surface area, watertightness). The subprocess runs the real
`pythonscad` module, so the parent-process mock (installed by conftest) is irrelevant to it.

Everything skips gracefully when no PythonSCAD binary is available (set PYTHONSCAD_BIN, or install
to /Applications) -- these tests need the app, they are not part of the pure-Python suite.
"""

from __future__ import annotations

import math
import os
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

# pybosl2/tests/render_stl.py -> pybosl2/tests -> repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent

# PythonSCAD-dev is preferred: the plain app's hardened runtime rejects the installed numpy, which
# every pybosl2 module imports (see CLAUDE.md), so nearly all pybosl2 renders fail under it.
_CANDIDATE_BINARIES = [
    "/Applications/PythonSCAD-dev.app/Contents/MacOS/PythonSCAD",
    "/Applications/PythonSCAD.app/Contents/MacOS/PythonSCAD",
    "/usr/local/bin/pythonscad",
    "squashfs-root/AppRun",
    "/opt/pythonscad/AppRun",
]


def find_pythonscad_binary() -> str | None:
    """The PythonSCAD binary to render with: $PYTHONSCAD_BIN, else a known install, else None."""
    override = os.environ.get("PYTHONSCAD_BIN")
    if override:
        return override if Path(override).is_file() else None
    for candidate in _CANDIDATE_BINARIES:
        if Path(candidate).is_file():
            return candidate
    return None


@dataclass
class StlResult:
    ok: bool
    path: Path | None
    error: str | None
    stderr: str


def _host_site_packages() -> list[str]:
    """This interpreter's site-packages, to hand to the app's embedded one.

    The app bundles its own Python, whose ``site.getsitepackages()`` returns paths INSIDE the
    bundle -- so a dependency installed for the host interpreter (pybosl2 needs ``webcolors``)
    is invisible to it and every render dies with ModuleNotFoundError before it draws anything.
    CI gets away with the ``pythonLocation`` branch below; a local checkout has no such variable.
    These are APPENDED, so the app's own numpy still wins over any host copy.
    """
    import site as _site

    found = list(_site.getsitepackages())
    user = _site.getusersitepackages()
    found.append(user) if isinstance(user, str) else found.extend(user)
    return [p for p in found if Path(p).is_dir()]


_PREAMBLE = (
    "import sys, math, site, os, traceback\n"
    f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
    f"for p in {_host_site_packages()!r}:\n"
    "    if p not in sys.path:\n"
    "        sys.path.append(p)\n"
    "for p in site.getsitepackages():\n"
    "    if p not in sys.path:\n"
    "        sys.path.append(p)\n"
    "usp = site.getusersitepackages()\n"
    "if os.path.isdir(usp) and usp not in sys.path:\n"
    "    sys.path.insert(0, usp)\n"
    "host_sp = os.environ.get('pythonLocation', '')\n"
    "if host_sp:\n"
    "    for entry in os.listdir(os.path.join(host_sp, 'lib')):\n"
    "        if entry.startswith('python3.'):\n"
    "            sp = os.path.join(host_sp, 'lib', entry, 'site-packages')\n"
    "            if os.path.isdir(sp) and sp not in sys.path:\n"
    "                sys.path.insert(0, sp)\n"
    "import numpy as np\n"
    "import pybosl2\n"
    "from pybosl2 import shapes3d as s3\n"
    "from pybosl2 import shapes2d as s2\n"
    "from pybosl2 import Path, Path2D, Path3D\n"
    "from pybosl2 import Bezier, BezierPatch\n"
    "from pybosl2 import arc, turtle2d, turtle3d\n"
    "from pybosl2 import xdistribute, ydistribute, zdistribute\n"
    "from pybosl2 import rainbow, rainbow_colors\n"
    "from pybosl2 import partition_path, partition_mask, partition_cut_mask\n"
    "from pybosl2 import extrude_from_to, cylindrical_extrude, chain_hull, minkowski_difference\n"
    "from pybosl2 import NurbsCurve, NurbsPatch, NurbsType\n"
    "from pybosl2 import VNF\n"
    "from pybosl2 import mb_sphere, mb_cuboid, mb_torus, mb_capsule, mb_disk, "
    "mb_octahedron, mb_connector\n"
    "from pybosl2.parts.threading import (\n"
    "    ThreadedRod, ThreadedNut, ThreadHelix,\n"
    "    iso_threaded_rod, iso_threaded_nut,\n"
    "    trapezoidal_threaded_rod, acme_threaded_rod,\n"
    "    square_threaded_rod, buttress_threaded_rod,\n"
    "    trapezoidal_threaded_nut,\n"
    ")\n"
    "from pybosl2.parts.screws import Screw, Nut, ScrewHole\n"
    "from pybosl2.parts.enums import ScrewHeadType, ScrewDriveType, NutShape\n"
    "from pybosl2.parts.gears import BevelGear, HerringboneGear, Rack, RingGear, SpurGear, Worm, WormGear\n"
    "from pybosl2.parts.walls import NarrowingStrut, SparseWall, SparseCuboid, "
    "CorrugatedWall, ThinningWall, ThinningTriangle\n"
    "from pybosl2.parts.hooks import HoleType, RingHook\n"
    "from pybosl2.parts.wiring import WireBundle\n"
    "from pybosl2.parts.polyhedra import PlatonicSolid, RegularPolyhedron\n"
    "from pybosl2.parts.hinges import KnuckleHinge, KnuckleHingePair, LivingHingeMask, SnapLock, SnapSocket\n"
    "from pybosl2.parts.joiners import Dovetail, SnapPin, SnapPinSocket\n"
    "from pybosl2.parts.cubetruss import (\n"
    "    TrussSegment, Truss, TrussCorner, TrussSupport,\n"
    "    TrussClip, TrussFoot, TrussUClip, TrussJoiner, truss_dist,\n"
    ")\n"
    "from pybosl2.parts.ball_bearings import BallBearings\n"
    "from pybosl2.parts.linear_bearings import LinearBearings\n"
    "from pybosl2.parts.modular_hose import HoseSegment, HoseType\n"
    "from pybosl2.parts.nema_steppers import NemaMotor, NemaMountMask, NemaSpec\n"
    "from pybosl2.parts.sliders import Slider, Rail\n"
    "from pybosl2.parts.bottlecaps import BottleCaps\n"
    "from pybosl2.parts.screw_drive import (\n"
    "    HexDriveMask, PhillipsMask, PhillipsSpec, RobertsonMask,\n"
    "    TorxMask, TorxMask2d, TorxSpec, hex_mask,\n"
    ")\n"
    "from pybosl2.parts.tripod_mounts import ManfrottoRC2Plate, manfrotto_rc2_plate\n"
    "from functools import reduce\n"
    "from pybosl2.color import Color\n"
    "from pybosl2 import Region\n"
    "from pybosl2 import *\n"
)

_EXTRA_PREAMBLE = "\ntry:\n"

_POSTAMBLE = (
    "except Exception as e:\n"
    '    print("An error occurred during model generation:")\n'
    "    # This prints the complete, standard Python error trace\n"
    "    traceback.print_exc()\n"
)


def render_object(
    expr: str,
    out_stl: Path,
    setup: str = "",
    timeout: float = 180.0,
    export_format: str | None = None,
) -> StlResult:
    """Build ``obj = <expr>`` (after any *setup* statements) in the real app and export it to STL.

    *expr* must evaluate to a native solid or a Bosl2Solid (a VNF/patch expression should end in
    ``.polyhedron()``). *export_format* is passed to PythonSCAD's ``--export-format`` (e.g. ``"binstl"``
    for a compact binary STL; the default is ASCII). Returns an StlResult; never raises for a render
    failure so callers can assert on ``.ok``. Only raises if no binary can be located at all.
    """
    body = (
        _PREAMBLE
        + setup
        + _EXTRA_PREAMBLE
        + f"    obj = {expr}\n"
        + "    if isinstance(obj, list):\n"
        + "        for o in obj: o.show()\n"
        + "    else:\n"
        + "        obj.show()\n"
        + _POSTAMBLE
    )
    return render_stl_script(body, out_stl, timeout=timeout, export_format=export_format)


def _packed_magics_color(displaycolor: str) -> int:
    """Pack a 3MF ``displaycolor`` into a Magics STL attribute word.

    The colour STL convention VisCAM and Magics introduced -- and the one three.js's
    ``STLLoader`` reads, surfacing it as ``geometry.hasColors`` -- puts five bits per channel in
    the per-facet attribute: bits 0-4 red, 5-9 green, 10-14 blue, and bit 15 clear to mean "this
    facet carries its own colour".

    Args:
        displaycolor: A 3MF colour such as ``"#FF0000FF"`` (the alpha byte is ignored; the
            format has nowhere to put it).

    Returns:
        The 16-bit attribute word.

    """
    red, green, blue = (int(displaycolor[i : i + 2], 16) for i in (1, 3, 5))
    scaled = [min(31, max(0, round(channel / 255.0 * 31))) for channel in (red, green, blue)]
    return scaled[0] | (scaled[1] << 5) | (scaled[2] << 10)


def convert_3mf_to_colored_stl(threemf_path: Path, stl_out_path: Path) -> bool:
    """Rewrite a multi-material 3MF as a binary STL carrying one colour per facet.

    **Why this exists.** An STL has no colour, so a docs example whose whole point is colour --
    `rainbow_colors`, say -- rendered in the viewer's flat default, which is the one thing that
    example is not about. 3MF does carry colour: PythonSCAD writes a `<basematerials>` table and
    tags each triangle with `pid`/`p1`. So the export goes to 3MF and is rewritten here into the
    STL colour extension, which keeps one file format for the viewer *and* the download link.

    **Colour survives a union, measured, including an overlapping one.** PythonSCAD tags
    *triangles* with `p1` rather than tagging objects with `pindex`, so merging bodies does not
    merge their colours: three disjoint `rainbow_colors(3)` cuboids come out 12 tagged facets
    each, and a cuboid overlapping a cylinder comes out 48 red and 92 steelblue. The one loss is
    resolution -- five bits a channel, so pure channels are exact and steelblue `(70, 130, 180)`
    returns as `(74, 132, 181)`.

    Args:
        threemf_path: The 3MF to read.
        stl_out_path: Where to write the binary STL.

    Returns:
        True if a colour STL was written. False when the 3MF held no triangles, or when nothing in
        it was deliberately coloured -- in both cases the caller should fall back to the plain
        export rather than ship an empty mesh or a uniformly yellow one.

    """
    with zipfile.ZipFile(threemf_path) as archive:
        root = ET.fromstring(archive.read("3D/3dmodel.model"))

    # Tags are namespaced and the namespace has changed between 3MF revisions, so match on the
    # local name rather than pinning a URI that a future PythonSCAD might bump.
    palettes: dict[str, list[int]] = {}
    # PythonSCAD always writes an implicit first entry named "Default" -- its own preview yellow,
    # #F9D72C -- and names anything a caller asked for "Color N". Tracking the names is what lets
    # a model with no colour of its own be recognised below.
    defaults: dict[str, list[bool]] = {}
    for group in root.iter():
        if not group.tag.endswith("basematerials"):
            continue
        bases = [base for base in group if base.tag.endswith("base")]
        key = group.attrib.get("id", "1")
        palettes[key] = [_packed_magics_color(base.attrib.get("displaycolor", "#CCCCCCFF")) for base in bases]
        defaults[key] = [base.attrib.get("name", "") == "Default" for base in bases]

    fallback = next(iter(palettes.values()), [])
    fallback_defaults = next(iter(defaults.values()), [])
    triangles: list[tuple[tuple[float, float, float], ...]] = []
    attributes: list[int] = []
    deliberate: list[bool] = []
    for mesh in root.iter():
        if not mesh.tag.endswith("mesh"):
            continue
        holders = {suffix: [e for e in mesh if e.tag.endswith(suffix)] for suffix in ("vertices", "triangles")}
        if not holders["vertices"] or not holders["triangles"]:
            continue
        points = [
            (float(v.attrib["x"]), float(v.attrib["y"]), float(v.attrib["z"]))
            for v in holders["vertices"][0]
            if v.tag.endswith("vertex")
        ]
        for face in holders["triangles"][0]:
            if not face.tag.endswith("triangle"):
                continue
            corners = tuple(points[int(face.attrib[key])] for key in ("v1", "v2", "v3"))
            group_id = face.attrib.get("pid", "1")
            palette = palettes.get(group_id, fallback)
            named_default = defaults.get(group_id, fallback_defaults)
            index = int(face.attrib.get("p1", 0))
            triangles.append(corners)
            attributes.append(palette[index] if index < len(palette) else 0)
            deliberate.append(not (index < len(named_default) and named_default[index]))

    if not triangles:
        return False

    # **Decline when nothing was actually coloured.** Every export carries the "Default" material,
    # so a model that never calls `.color()` still tags all of its facets -- with PythonSCAD's
    # preview yellow. Writing that as a facet colour would paint all 176 uncoloured examples
    # #F9D72C and, worse, pin them there: the viewer's own colour is theme-aware and follows the
    # light/dark toggle, and a facet colour overrides it. Returning False hands the caller back to
    # the plain export, which is byte-for-byte what it produced before this route existed.
    if not any(deliberate):
        return False

    # "COLOR=" in the first bytes is what the convention uses to announce per-facet colour; the
    # default it carries is only used for facets that do not set their own.
    header = b"COLOR=" + bytes((255, 255, 255, 255)) + b" pybosl2 colour STL"
    with stl_out_path.open("wb") as handle:
        handle.write(header.ljust(80, b"\0")[:80])
        handle.write(struct.pack("<I", len(triangles)))
        for corners, attribute in zip(triangles, attributes, strict=True):
            normal = _facet_normal(corners)
            handle.write(struct.pack("<3f", *normal))
            for corner in corners:
                handle.write(struct.pack("<3f", *corner))
            handle.write(struct.pack("<H", attribute))
    return True


def _facet_normal(corners: "tuple[tuple[float, float, float], ...]") -> tuple[float, float, float]:
    """Return the unit normal of a triangle, or zeros when it is degenerate.

    A zero normal is legal in an STL and viewers recompute from the winding, which is what
    `stl_viewer.js` does; refusing to divide by a zero length is the only thing that matters.
    """
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = corners
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    return (nx / length, ny / length, nz / length) if length else (0.0, 0.0, 0.0)


def render_stl_script(
    script_source: str,
    out_stl: Path,
    render_cmd: Sequence[str] | None = None,  # noqa: ARG001
    timeout: float = 180.0,
    cwd: str | None = None,
    export_format: str | None = None,
    prefer_color: bool = False,
) -> StlResult:
    """Run a full python-mode *script_source* (ending in ``.show()``) in the real app, exporting STL.

    The lower-level entry point behind :func:`render_object`; also used by the docs
    ``pybosl2-example`` directive to generate a downloadable STL for each example.

    With *prefer_color*, the export goes to 3MF and is rewritten as a colour STL by
    :func:`convert_3mf_to_colored_stl`, so `.color()` in an example survives into the viewer.
    It is **opt-in** rather than the default because the test suite compares meshes rather than
    looking at them, and a changed file format there would be churn with no reader. Anything that
    does not work -- the 3MF step, the rewrite, a build of PythonSCAD without 3MF -- falls back to
    the plain export, since a grey mesh is worth more than a missing one.

    Args:
        script_source: The python-mode script, ending in ``.show()``.
        out_stl: Where to write the mesh.
        render_cmd: Unused; kept for call-site compatibility.
        timeout: Seconds to allow the app.
        cwd: Working directory for the subprocess.
        export_format: Passed to ``--export-format``.
        prefer_color: Try the 3MF-to-colour-STL route first.

    Returns:
        The :class:`StlResult` for whichever route produced a mesh.

    """
    if prefer_color:
        colored = _render_colored_stl(script_source, out_stl, timeout=timeout, cwd=cwd)
        if colored is not None:
            return colored
    binary = find_pythonscad_binary()
    if binary is None:
        raise FileNotFoundError("no PythonSCAD binary found (set PYTHONSCAD_BIN or install to /Applications)")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
        f.write(script_source)
        script_path = Path(f.name)

    try:
        proc = subprocess.run(
            [
                binary,
                "--trust-python",
                "--enable",
                "python-engine",
                "-o",
                str(out_stl),
                "--backend",
                "Manifold",
                *(("--export-format", export_format) if export_format else ()),
                str(script_path),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired as exc:
        err = exc.stderr or b""
        return StlResult(
            False,
            None,
            f"render timed out after {timeout:.0f}s",
            err.decode(errors="replace") if isinstance(err, bytes) else str(err),
        )
    finally:
        script_path.unlink(missing_ok=True)

    stderr = proc.stderr or ""
    if "Traceback (most recent call last):" in stderr:
        lines = stderr.splitlines()
        cutoff = next(
            (i for i, ln in enumerate(lines) if ln.startswith("Geometries in cache")),
            len(lines),
        )
        # Capture the actual exception type and message, plus the last traceback entry
        exc_lines = [ln.strip() for ln in lines[:cutoff] if ln.strip() and not ln.startswith("  File ")]
        last_exc = exc_lines[-1] if exc_lines else "unknown error"
        return StlResult(False, None, f"script raised: {last_exc[:400]}", stderr)
    if proc.returncode != 0:
        return StlResult(
            False,
            None,
            f"PythonSCAD exited {proc.returncode}: {stderr[:200] if stderr else 'no output'}",
            stderr,
        )
    if not out_stl.is_file() or out_stl.stat().st_size == 0:
        return StlResult(
            False,
            None,
            f"no STL produced (stderr: {stderr[:200] if stderr else 'none'})",
            stderr,
        )
    return StlResult(True, out_stl, None, stderr)


def _render_colored_stl(script_source: str, out_stl: Path, timeout: float, cwd: str | None) -> "StlResult | None":
    """Export via 3MF and rewrite it as a colour STL, or None to let the caller fall back.

    Returning None rather than a failed :class:`StlResult` is the point: a build that cannot write
    3MF, or a model with no per-facet material, is not an error -- it just means the plain export
    is the right answer, and the caller carries on to it.
    """
    staging = out_stl.with_name(f".{out_stl.stem}.3mf")
    try:
        result = render_stl_script(script_source, staging, timeout=timeout, cwd=cwd, export_format="3mf")
        if not (result.ok and staging.is_file() and staging.stat().st_size):
            return None
        try:
            if not convert_3mf_to_colored_stl(staging, out_stl):
                return None
        except (zipfile.BadZipFile, KeyError, ET.ParseError, ValueError, OSError):
            # A 3MF this cannot read is a reason to fall back, not to fail the build.
            return None
        return StlResult(True, out_stl, None, result.stderr)
    finally:
        staging.unlink(missing_ok=True)


def parse_stl(path: Path) -> np.ndarray:
    """Load an STL (binary or ASCII) as an (N, 3, 3) array of triangle vertices."""
    data = Path(path).read_bytes()
    if len(data) >= 84:
        sides = struct.unpack("<I", data[80:84])[0]
        if len(data) == 84 + 50 * sides:  # exact binary-STL size => binary
            dt = np.dtype([("sides", "<f4", (3,)), ("v", "<f4", (3, 3)), ("attr", "<u2")])
            arr = np.frombuffer(data, dtype=dt, offset=84, count=sides)
            return np.array(arr["v"], dtype=float)
    verts = []
    for line in data.decode("ascii", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("vertex"):
            _, x, y, z = line.split()[:4]
            verts.append([float(x), float(y), float(z)])
    arr = np.asarray(verts, dtype=float)  # type: ignore[assignment]
    assert arr.size, "malformed ASCII STL"
    assert len(arr) % 3 == 0, "malformed ASCII STL"
    return arr.reshape(-1, 3, 3)


@dataclass
class StlMetrics:
    ntris: int
    bbmin: np.ndarray
    bbmax: np.ndarray
    size: np.ndarray
    volume: float
    area: float
    watertight: bool


def stl_metrics(path: Path) -> StlMetrics:
    """
    Measure an STL: triangle count, bounding box, enclosed volume, surface area, watertightness.
    """
    tris = parse_stl(path)
    pts = tris.reshape(-1, 3)
    bbmin, bbmax = pts.min(axis=0), pts.max(axis=0)
    v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
    volume = abs(float(np.sum(np.einsum("ij,ij->i", v0, np.cross(v1, v2))) / 6.0))
    area = float(np.sum(0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)))
    # watertight: every undirected edge shared by exactly two triangles (rounded to fuse vertices)
    edges: dict[object, int] = {}
    keys = np.round(tris, 4)
    for tri in keys:
        vs = [tuple(v) for v in tri]
        for a, b in ((0, 1), (1, 2), (2, 0)):
            e = tuple(sorted((vs[a], vs[b])))
            edges[e] = edges.get(e, 0) + 1
    watertight = bool(edges) and all(c == 2 for c in edges.values())
    return StlMetrics(len(tris), bbmin, bbmax, bbmax - bbmin, volume, area, watertight)


def stl_normalized_hash(path: Path, tolerance: float = 1e-4) -> str:
    """Return a stable SHA256 hash of the STL geometry, tolerant of vertex
    ordering differences and sub-*tolerance* floating-point drift.

    Vertices are rounded to *tolerance*, triangles are sorted by centroid,
    and the result is hashed so two STLs that represent the same shape
    (within tolerance) produce the same hash.
    """
    import hashlib

    tris = parse_stl(path)
    rounded = np.round(tris, decimals=int(-math.log10(tolerance)))
    centroids = np.round(rounded.mean(axis=1), decimals=int(-math.log10(tolerance)))
    order = np.lexsort((centroids[:, 2], centroids[:, 1], centroids[:, 0]))
    sorted_tris = rounded[order]
    flat = sorted_tris.ravel().astype(np.float32).tobytes()
    return hashlib.sha256(flat).hexdigest()[:16]


def golden_ok(rendered: Path, golden: Path, tolerance: float = 1e-4) -> bool:
    """True when the *rendered* STL matches the *golden* STL geometry within tolerance.

    Both files are loaded, vertices rounded, triangles sorted by centroid, and
    a stable hash compared.  When the golden file does not exist the first time
    (e.g. a fresh checkout), the rendered STL is copied in as the golden and
    the comparison is considered a pass.
    """
    if not golden.exists():
        golden.parent.mkdir(parents=True, exist_ok=True)
        import shutil

        shutil.copy2(rendered, golden)
        return True
    return stl_normalized_hash(rendered, tolerance) == stl_normalized_hash(golden, tolerance)

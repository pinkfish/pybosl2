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
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

# pybosl2/tests/render_stl.py -> pybosl2/tests -> pybosl2 -> repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

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


_PREAMBLE = (
    "import sys, math, site, os\n"
    f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
    # AppImage Python may not see system site-packages; add them explicitly
    "for p in site.getsitepackages():\n"
    "    if p not in sys.path:\n"
    "        sys.path.append(p)\n"
    # Also add user site-packages (where pip install --user puts numpy/shapely in CI)
    "usp = site.getusersitepackages()\n"
    "if os.path.isdir(usp) and usp not in sys.path:\n"
    "    sys.path.insert(0, usp)\n"
    # In CI (GitHub Actions), pythonLocation points to the host Python's root;
    # the AppImage Python may be a different installation and not see those packages.
    "host_sp = os.environ.get('pythonLocation', '')\n"
    "if host_sp:\n"
    "    for entry in os.listdir(os.path.join(host_sp, 'lib')):\n"
    "        if entry.startswith('python3.'):\n"
    "            sp = os.path.join(host_sp, 'lib', entry, 'site-packages')\n"
    "            if os.path.isdir(sp) and sp not in sys.path:\n"
    "                sys.path.insert(0, sp)\n"
    "import numpy as np\n"
    "import pybosl2.shapes3d as s3\n"
    "import pybosl2.shapes2d as s2\n"
    "from pybosl2 import Path, Path2D, Path3D\n"
    "from pybosl2 import Bezier, BezierPatch\n"
    "from pybosl2 import sweep, skin, rot_resample\n"
    "from pybosl2 import xdistribute, ydistribute, zdistribute\n"
    "from pybosl2 import rainbow, rainbow_colors\n"
    "from pybosl2 import partition_path, partition_mask, partition_cut_mask\n"
    "from pybosl2 import extrude_from_to, cylindrical_extrude, chain_hull, minkowski_difference\n"
    "from pybosl2 import nurbs_curve, nurbs_patch_points, nurbs_vnf, nurbs_elevate_degree, is_nurbs_patch\n"
    "from pybosl2 import VNF\n"
    "from pybosl2 import mb_sphere, mb_cuboid, mb_torus, mb_capsule, mb_disk, "
    "mb_octahedron, mb_connector\n"
    # parts library classes, so examples can be terse (Gears.spur_gear(...).show())
    "from pybosl2.parts.threading import Threading\n"
    "from pybosl2.parts.screws import Screws\n"
    "from pybosl2.parts.gears import Gears\n"
    "from pybosl2.parts.walls import Walls\n"
    "from pybosl2.parts.hooks import Hooks\n"
    "from pybosl2.parts.wiring import Wiring\n"
    "from pybosl2.parts.polyhedra import Polyhedra\n"
    "from pybosl2.parts.hinges import Hinges\n"
    "from pybosl2.parts.joiners import Joiners\n"
    "from pybosl2.parts.cubetruss import CubeTruss\n"
    "from pybosl2.parts.ball_bearings import BallBearings\n"
    "from pybosl2.parts.linear_bearings import LinearBearings\n"
    "from pybosl2.parts.modular_hose import ModularHose\n"
    "from pybosl2.parts.nema_steppers import NemaSteppers\n"
    "from pybosl2.parts.sliders import Sliders\n"
    "from pybosl2.parts.bottlecaps import BottleCaps\n"
    "from pybosl2.parts.screw_drive import ScrewDrive\n"
    "from functools import reduce\n"
    "from pybosl2 import round_corners, smooth_path\n"
    "from pybosl2 import Region\n"
    "from pybosl2 import *\n"
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
    body = _PREAMBLE + setup + f"obj = {expr}\n" + "obj.show()\n"
    return render_stl_script(body, out_stl, timeout=timeout, export_format=export_format)


def render_stl_script(
    script_source: str,
    out_stl: Path,
    render_cmd: Sequence[str] | None = None,  # noqa: ARG001
    timeout: float = 180.0,
    cwd: str | None = None,
    export_format: str | None = None,
) -> StlResult:
    """Run a full python-mode *script_source* (ending in ``.show()``) in the real app, exporting STL.

    The lower-level entry point behind :func:`render_object`; also used by the docs
    ``pybosl2-example`` directive to generate a downloadable STL for each example.
    """
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

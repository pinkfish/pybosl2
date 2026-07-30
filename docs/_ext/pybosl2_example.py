# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: pybosl2/docs/_ext/pybosl2_example.py
#    Sphinx extension providing a ``.. pybosl2-example::`` directive: the directive's content is a
#    short pybosl2-using Python snippet ending in ``<obj>.show()`` (the same convention as a real
#    PythonSCAD python-mode file). At build time it is prepended with a standard preamble (repo
#    root on sys.path, common pybosl2 imports) and rendered with the *real* PythonSCAD binary, and
#    the generated docs show, side by side: the snippet's source, an interactive 3-D STL viewer,
#    and a download link to the exported STL mesh. This is the same "show the code, show
#    what it actually builds" idea as matplotlib's ``.. plot::`` and openscad-docsgen's
#    ``Example:`` blocks that the parent repo's docs/ (for the .scad files) already use.
#
#    The STL export reuses pybosl2/tests/render_stl.py's render_stl_script() -- the same subprocess
#    /skip-gracefully plumbing the test suites rely on, not a reimplementation.
#
#    Exported STLs are cached in docs/_stl/, keyed by a hash of the snippet, so unchanged examples
#    are not re-rendered. If no PythonSCAD binary is available (or a render fails, e.g. a 2-D
#    example that cannot export to STL), the directive degrades gracefully -- it emits a build
#    warning and still shows the source, just without the STL viewer, rather than failing the
#    whole ``make html``.
#
# FileGroup: pybosl2

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx.util import logging

_DOCS_DIR = Path(__file__).resolve().parent.parent
# Exported meshes live under _extra/_stl/ so that html_extra_path=["_extra"] copies the whole
# _stl/ subdir (not just its flattened contents) to the output root, keeping the ``_stl/<hash>.stl``
# URIs the viewer and download links use valid.
_STL_DIR = _DOCS_DIR / "_extra" / "_stl"

# docs/_ext -> docs -> repo root.
_REPO_ROOT = _DOCS_DIR.parent
sys.path.insert(0, str(_REPO_ROOT / "tests"))

from render_stl import find_pythonscad_binary, render_stl_script  # noqa: E402
from stl_viewer import stl_viewer_html  # noqa: E402

_logger = logging.getLogger(__name__)

# Prepended to every snippet: put the repo root on sys.path and import the common pybosl2 names, so
# examples can be terse (`s3.cuboid(...)`, `Path2D(...)`, `Bezier(...)`) and mirror how the toolkit
# is actually used.
_PREAMBLE = (
    "import sys, math\n"
    f"sys.path.insert(0, {str(_REPO_ROOT)!r})\n"
    "import numpy as np\n"
    "import pybosl2\n"
    "import pybosl2.shapes3d\n"
    "import pybosl2.shapes2d\n"
    "import pybosl2.shapes3d as s3\n"
    "import pybosl2.shapes2d as s2\n"
    "from pybosl2.paths import Path2D, Path3D\n"
    "from pybosl2.regions import Region\n"
    "from pybosl2.beziers import Bezier, BezierPatch\n"
    "from pybosl2.vnf import VNF\n"
    "from pybosl2.skin import sweep, skin, rot_resample\n"
    "from pybosl2.drawing import arc, catenary, helix, turtle, stroke, dashed_stroke\n"
    "from pybosl2.distributors import distribute, xdistribute, ydistribute, zdistribute\n"
    "from pybosl2.color import hsl, hsv, rainbow, rainbow_colors\n"
    "from pybosl2.partitions import partition_path, partition_mask, partition_cut_mask\n"
    "from pybosl2.miscellaneous import extrude_from_to, cylindrical_extrude, chain_hull, minkowski_difference\n"
    "from pybosl2.nurbs import nurbs_curve, nurbs_patch_points, nurbs_vnf, nurbs_elevate_degree, is_nurbs_patch\n"
    "from pybosl2.isosurface import isosurface, metaballs, mb_sphere, mb_cuboid, mb_torus, mb_capsule, mb_disk, mb_octahedron, mb_connector\n"  # noqa: E501
    "from pybosl2.parts.threading import Threading\n"
    "from pybosl2.parts.screws import Screws\n"
    # parts library classes, so part examples can be terse (Gears.spur_gear(...).show())
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
    "from pybosl2.constants import *\n"
)


class Bosl2ExampleDirective(Directive):
    """``.. pythonscad-example::`` -- render a pybosl2 snippet to an interactive STL viewer. See module docstring."""

    has_content = True

    def run(self) -> list[nodes.Node]:
        code = "\n".join(self.content)
        script = _PREAMBLE + code + "\n"

        out: list[nodes.Node] = []
        code_node = nodes.literal_block(code, code)
        code_node["language"] = "python"
        out.append(code_node)

        # Show interactive 3-D STL viewer; if no STL (e.g. 2-D object), show source only.
        stl_uri = self._render_stl(script, code)
        if stl_uri is not None:
            out.append(nodes.raw("", stl_viewer_html(stl_uri), format="html"))
            para = nodes.paragraph()
            para += nodes.reference("", "⬇ Download STL mesh", refuri=stl_uri)
            out.append(para)
        return out

    def _render_stl(self, script: str, code: str) -> str | None:
        digest = hashlib.sha256(f"stl\n{code}".encode()).hexdigest()[:16]
        out_stl = _STL_DIR / f"{digest}.stl"
        if out_stl.is_file():
            return f"_stl/{out_stl.name}"
        if find_pythonscad_binary() is None:
            return None
        _STL_DIR.mkdir(exist_ok=True)
        try:
            result = render_stl_script(script, out_stl, timeout=300.0, export_format="binstl")
        except subprocess.TimeoutExpired:
            _logger.warning(f"pybosl2-example: STL export timed out for:\n{code}")
            return None
        if not result.ok:
            # 2-D examples (a Path outline, a region) legitimately have no STL -- info, not warning.
            _logger.info(f"pybosl2-example: no STL for example ({result.error})")
            return None
        return f"_stl/{out_stl.name}"


def setup(app) -> dict:
    # Registered as ``pythonscad-example`` to match the name the pybosl2 docstrings (and pysolidfive's
    # docs) already use; ``pybosl2-example`` is kept as an alias.
    app.add_directive("pythonscad-example", Bosl2ExampleDirective)
    app.add_directive("pybosl2-example", Bosl2ExampleDirective)
    return {"version": "0.1", "parallel_read_safe": True, "parallel_write_safe": True}

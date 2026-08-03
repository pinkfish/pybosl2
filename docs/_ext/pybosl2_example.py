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
    "import sys, math, site, os\n"
    f"sys.path.insert(0, {str(_REPO_ROOT)!r})\n"
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
    "import pybosl2\n"
    "from pybosl2 import Path, Path2D, Path3D\n"
    "from pybosl2 import Region\n"
    "from pybosl2 import Bezier, BezierPatch\n"
    "from pybosl2 import VNF\n"
    "from pybosl2 import sweep, skin, rot_resample\n"
    "from pybosl2 import helix\n"
    "from pybosl2 import arc\n"
    "from pybosl2 import catenary\n"
    "from pybosl2.turtle import turtle2d\n"
    "from pybosl2.turtle import turtle3d\n"
    "from pybosl2 import xdistribute, ydistribute, zdistribute\n"
    "from pybosl2 import round_corners, smooth_path\n"
    "from pybosl2 import MinkowskiJoin\n"
    "from pybosl2 import rainbow, rainbow_colors\n"
    "from pybosl2 import partition_path, partition_mask, partition_cut_mask\n"
    "from pybosl2 import extrude_from_to, cylindrical_extrude, chain_hull, minkowski_difference\n"
    "from pybosl2 import nurbs_curve, nurbs_patch_points, nurbs_vnf, nurbs_elevate_degree, is_nurbs_patch\n"
    "from pybosl2 import metaballs, mb_sphere, mb_cuboid, mb_torus, mb_capsule, mb_disk, mb_octahedron, mb_connector\n"
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
    "from pybosl2 import *\n"
    "import traceback\n"
    "\n"
    "try:\n"
)

_POSTAMBLE = (
    "except Exception as e:\n"
    '    print("An error occurred during model generation:")\n'
    "    # This prints the complete, standard Python error trace\n"
    "    traceback.print_exc()\n"
)


class Bosl2ExampleDirective(Directive):
    """``.. pythonscad-example::`` -- render a pybosl2 snippet to an interactive STL viewer. See module docstring."""

    has_content = True

    def run(self) -> list[nodes.Node]:
        code_str = "\n".join(self.content)
        lines = code_str.splitlines()
        indented_str = "\n".join(f"    {line}" if line else "" for line in lines)

        script = _PREAMBLE + indented_str + "\n" + _POSTAMBLE

        out: list[nodes.Node] = []
        code_node = nodes.literal_block(code_str, code_str)
        code_node["language"] = "python"
        out.append(code_node)

        # Show interactive 3-D STL viewer; if no STL (e.g. 2-D object), show source only.
        stl_uri = self._render_stl(script, code_str)
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
            _logger.warning("pybosl2-example: no PythonSCAD binary found, skipping STL render")
            return None
        _STL_DIR.mkdir(exist_ok=True)
        try:
            result = render_stl_script(script, out_stl, timeout=300.0, export_format="binstl")
        except subprocess.TimeoutExpired:
            _logger.warning(f"pybosl2-example: STL export timed out after 300s for:\n{code[:200]}")
            return None
        except Exception as exc:
            _logger.error(f"pybosl2-example: unexpected error rendering STL: {exc}\ncode:\n{code[:300]}")
            return None
        if not result.ok:
            stderr_tail = (result.stderr or "")[-500:]
            _logger.warning(
                f"pybosl2-example STL render FAILED: {result.error}\nstderr tail: {stderr_tail}\n{code[:300]}"
            )
            return None
        return f"_stl/{out_stl.name}"


def setup(app) -> dict:
    # Registered as ``pythonscad-example`` to match the name the pybosl2 docstrings (and pysolidfive's
    # docs) already use; ``pybosl2-example`` is kept as an alias.
    app.add_directive("pythonscad-example", Bosl2ExampleDirective)
    app.add_directive("pybosl2-example", Bosl2ExampleDirective)
    return {"version": "0.1", "parallel_read_safe": True, "parallel_write_safe": True}

pybosl2 — a pure-Python PythonSCAD port of BOSL2
================================================

``pybosl2`` is a pure-Python / numpy port of the pieces of `BOSL2 <https://github.com/BelfrySCAD/BOSL2>`_
that this toolkit uses, with **no** ``osuse()``/BOSL2 runtime dependency. Every operation hangs off
an object — :class:`~pybosl2.path2d.Path2D` for 2-D outlines, :class:`~pybosl2.regions.Region` for
outlines-with-holes, :class:`~pybosl2.beziers.Bezier` / :class:`~pybosl2.beziers.BezierPatch` for bezier
curves and surfaces, :class:`~pybosl2.vnf.VNF` for vertex-face meshes, and the
``pybosl2.shapes3d.Bosl2Solid`` primitives — so new code reads as fluent chains::

    Path2D([[0, 0], [80, 0], [80, 60], [0, 60]]).offset(r=-2).round_corners(radius=1).polygon()

.. raw:: html

   <p style="margin:1.4em 0;padding:14px 18px;border:1px solid #38bdf0;border-radius:10px;
      background:rgba(56,189,240,0.07);font-size:1.05em;">
     &#9881;&#65039; <b><a href="specs/index.html">Visual parts catalog &amp; spec sheets &rarr;</a></b>
     &nbsp;&mdash;&nbsp; the gears, hinges, joiners, cube-truss and ball-bearing modules with
     technical schematics and metrics measured from real rendered STL.
   </p>

Rendered examples
-----------------

Every documented function with a rendered example shows both the exact PythonSCAD code and what the
real PythonSCAD binary builds for it, via the ``pythonscad-example`` directive (in
``docs/_ext/pybosl2_example.py``): an **interactive 3-D viewer** for the exported STL mesh (rotate,
pan and zoom — served by the ``stl_viewer`` extension's three.js viewer, a working drop-in for the
``sphinxstl`` ``.. stl::`` directive), plus a **download link** to the mesh. Two-dimensional or
open-surface examples that have no solid mesh fall back to a static preview image.

.. note::

   The interactive viewers fetch each ``.stl`` over HTTP, so view the built docs through a web
   server (for example ``python3 -m http.server`` from ``pybosl2/wiki``) rather than opening the
   HTML files directly with a ``file://`` URL, where browsers block the local mesh fetch. You can
   also embed a viewer for any STL yourself with ``.. stl:: path/to/mesh.stl``.

A cuboid primitive:

.. pythonscad-example::

   from pybosl2 import shapes3d as s3

   s3.cuboid([40, 30, 20], rounding=4).show()

A bezier surface patch, meshed to a VNF and rendered as a polyhedron:

.. pythonscad-example::

   from pybosl2 import BezierPatch

   patch = [
       [[-50, -50, 0], [-16, -50, 20], [16, -50, -20], [50, -50, 0]],
       [[-50, -16, 20], [-16, -16, 20], [16, -16, -20], [50, -16, 20]],
       [[-50, 16, 20], [-16, 16, -20], [16, 16, 20], [50, 16, 20]],
       [[-50, 50, 0], [-16, 50, -20], [16, 50, 20], [50, 50, 0]],
   ]
   BezierPatch(patch).sheet([0, -6], splinesteps=16).polyhedron().show()

Sweeping a profile along a bezier curve:

.. pythonscad-example::

   import math
   import numpy as np
   from pybosl2 import Bezier

   circle = [[2 * math.cos(t), 2 * math.sin(t)] for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
   Bezier([[0, 0, 5], [0, 0, 20], [25, 12, 15], [30, 4, 6]]).sweep(circle, splinesteps=24).polyhedron().show()

API reference
-------------

The modules are grouped by role, mirroring BOSL2's own organisation. **Foundational** holds the
primitives and transforms most models start from; **Paths, regions & surfaces** the advanced
2-D/3-D modelling toolkit; **Math & geometry** the numeric helpers; and **Parts library** the
ready-made mechanical parts — each with a visual spec sheet in the catalog linked above.

.. toctree::
   :maxdepth: 1
   :caption: Solid backends

    CSG & SDF backends <backends>

.. toctree::
   :maxdepth: 2
   :caption: Foundational

    Color <color>
    Constants <constants>
    Distributors <distributors>
    Enums <enums>
    Masking <masking>
    Partitions <partitions>
    Solid <solid>
    Texture <texture>
    Transforms <transforms>
    Drawing <drawing>
    2-D Shapes <shapes2d>
    3-D Shapes <shapes3d>
    Native ops <native_ops>

.. toctree::
   :maxdepth: 2
   :caption: Paths, regions & surfaces

    Evaluate, analyze and build Bezier curves, paths, and surface patches (BOSL2 beziers.scad) <beziers>
    Isosurface <isosurface>
    Nurbs <nurbs>
    Abstract :class:`Path` base class for 2-D and 3-D path types <paths>
    Object API for 2-D paths and regions <regions>
    Rounding <rounding>
    Skin <skin>
    Turtle3D <turtle3d>
    Vnf <vnf>

.. toctree::
   :maxdepth: 2
   :caption: Math & geometry

    Geometry <geometry>
    Math <math>
    Vectors <vectors>

.. toctree::
   :maxdepth: 2
   :caption: Parts library

    Ball Bearings &#128736; <ball_bearings>
    Bottlecaps &#128736; <bottlecaps>
    Cubetruss &#128736; <cubetruss>
    Gears &#128736; <gears>
    Hinges &#128736; <hinges>
    Hooks &#128736; <hooks>
    Joiners &#128736; <joiners>
    Linear Bearings &#128736; <linear_bearings>
    Modular Hose &#128736; <modular_hose>
    Nema Steppers &#128736; <nema_steppers>
    Polyhedra &#128736; <polyhedra>
    Screw Drive &#128736; <screw_drive>
    Screws <screws>
    Sliders &#128736; <sliders>
    Threading &#128736; <threading>
    Walls &#128736; <walls>
    Wiring &#128736; <wiring>

.. toctree::
   :maxdepth: 2
   :caption: Extras

    Miscellaneous <miscellaneous>

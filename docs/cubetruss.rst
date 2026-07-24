Cube trusses
============

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/cubetruss.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


Pure-Python port of BOSL2's ``cubetruss.scad``: modular cubical truss segments, the trusses
assembled from them (with ``clips=`` for end clips), L/T **corner** trusses, diagonal **supports**,
and the printed clip accessories -- **clip**, **foot**, **joiner** and **u-clip**.
.. autoclass:: bosl2.cubetruss.CubeTruss
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``cubetruss.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``cubetruss``

A 3-segment truss:

.. pythonscad-example::

   CubeTruss.cubetruss(extents=3).show()

A 2x3 grid of segments:

.. pythonscad-example::

   CubeTruss.cubetruss(extents=[2,3]).show()

.. rubric:: ``cubetruss_segment``

One segment, unbraced:

.. pythonscad-example::

   CubeTruss.cubetruss_segment(bracing=False).show()

One segment, braced:

.. pythonscad-example::

   CubeTruss.cubetruss_segment(bracing=True).show()

Thicker struts:

.. pythonscad-example::

   CubeTruss.cubetruss_segment(strut=4).show()

A larger cube:

.. pythonscad-example::

   CubeTruss.cubetruss_segment(size=40).show()

.. rubric:: ``cubetruss_corner``

A corner joint:

.. pythonscad-example::

   CubeTruss.cubetruss_corner(extents=2).show()

A taller corner:

.. pythonscad-example::

   CubeTruss.cubetruss_corner(extents=2, height=2).show()

.. rubric:: ``cubetruss_support``

A diagonal support:

.. pythonscad-example::

   CubeTruss.cubetruss_support().show()

Two segments long:

.. pythonscad-example::

   CubeTruss.cubetruss_support(extents=2).show()

Thicker struts:

.. pythonscad-example::

   CubeTruss.cubetruss_support(strut=4).show()

.. rubric:: ``cubetruss_foot``

A single-wide foot:

.. pythonscad-example::

   CubeTruss.cubetruss_foot(w=1).show()

A triple-wide foot:

.. pythonscad-example::

   CubeTruss.cubetruss_foot(w=3).show()

.. rubric:: ``cubetruss_joiner``

A horizontal joiner:

.. pythonscad-example::

   CubeTruss.cubetruss_joiner(w=1, vert=False).show()

A vertical joiner:

.. pythonscad-example::

   CubeTruss.cubetruss_joiner(w=1, vert=True).show()

.. rubric:: ``cubetruss_uclip``

A single U-clip:

.. pythonscad-example::

   CubeTruss.cubetruss_uclip(dual=False).show()

A dual U-clip:

.. pythonscad-example::

   CubeTruss.cubetruss_uclip(dual=True).show()

.. rubric:: ``cubetruss_clip``

A two-segment clip:

.. pythonscad-example::

   CubeTruss.cubetruss_clip(extents=2).show()

A one-segment clip:

.. pythonscad-example::

   CubeTruss.cubetruss_clip(extents=1).show()

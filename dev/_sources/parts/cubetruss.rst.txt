Cube trusses
============

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/cubetruss.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


Pure-Python port of BOSL2's ``cubetruss.scad``: modular cubical truss segments (``TrussSegment``),
trusses assembled from them (``Truss``, with ``clips=`` for end clips), L/T **corner** trusses
(``TrussCorner``), diagonal **supports** (``TrussSupport``), and the printed clip accessories --
**clip** (``TrussClip``), **foot** (``TrussFoot``), **joiner** (``TrussJoiner``) and
**u-clip** (``TrussUClip``). The ``truss_dist`` function computes truss length from segment count.

.. autoclass:: pybosl2.parts.cubetruss.TrussSegment
   :members:

.. autoclass:: pybosl2.parts.cubetruss.Truss
   :members:

.. autoclass:: pybosl2.parts.cubetruss.TrussCorner
   :members:

.. autoclass:: pybosl2.parts.cubetruss.TrussSupport
   :members:

.. autoclass:: pybosl2.parts.cubetruss.TrussClip
   :members:

.. autoclass:: pybosl2.parts.cubetruss.TrussFoot
   :members:

.. autoclass:: pybosl2.parts.cubetruss.TrussUClip
   :members:

.. autoclass:: pybosl2.parts.cubetruss.TrussJoiner
   :members:

.. autofunction:: pybosl2.parts.cubetruss.truss_dist

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``cubetruss.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``Truss``

A 3-segment truss:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import Truss
   Truss(extents=3).shape.show()

A 2x3 grid of segments:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import Truss
   Truss(extents=[2,3]).shape.show()

.. rubric:: ``TrussSegment``

One segment, unbraced:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import TrussSegment
   TrussSegment(bracing=False).shape.show()

One segment, braced:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import TrussSegment
   TrussSegment(bracing=True).shape.show()

Thicker struts:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import TrussSegment
   TrussSegment(strut=4).shape.show()

A larger cube:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import TrussSegment
   TrussSegment(size=40).shape.show()

.. rubric:: ``TrussCorner``

A corner joint:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import TrussCorner
   TrussCorner(extents=2).shape.show()

A taller corner:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import TrussCorner
   TrussCorner(extents=2, height=2).shape.show()

.. rubric:: ``TrussSupport``

A diagonal support:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import TrussSupport
   TrussSupport().shape.show()

Two segments long:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import TrussSupport
   TrussSupport(extents=2).shape.show()

Thicker struts:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import TrussSupport
   TrussSupport(strut=4).shape.show()

.. rubric:: ``TrussFoot``

A single-wide foot:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import TrussFoot
   TrussFoot(w=1).shape.show()

A triple-wide foot:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import TrussFoot
   TrussFoot(w=3).shape.show()

.. rubric:: ``TrussJoiner``

A horizontal joiner:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import TrussJoiner
   TrussJoiner(w=1, vert=False).shape.show()

A vertical joiner:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import TrussJoiner
   TrussJoiner(w=1, vert=True).shape.show()

.. rubric:: ``TrussUClip``

A single U-clip:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import TrussUClip
   TrussUClip(dual=False).shape.show()

A dual U-clip:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import TrussUClip
   TrussUClip(dual=True).shape.show()

.. rubric:: ``TrussClip``

A two-segment clip:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import TrussClip
   TrussClip(extents=2).shape.show()

A one-segment clip:

.. pythonscad-example::

   from pybosl2.parts.cubetruss import TrussClip
   TrussClip(extents=1).shape.show()

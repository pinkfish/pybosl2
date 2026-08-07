RegularPolyhedron
=================

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/polyhedra.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


The five Platonic solids from BOSL2's ``polyhedra.scad``, built as watertight polyhedra.
:class:`~pybosl2.parts.polyhedra.RegularPolyhedron` builds ``tetrahedron`` / ``cube`` /
``octahedron`` / ``dodecahedron`` / ``icosahedron`` (with named convenience methods too), sized by
circumradius, diameter, inradius or side length. The dodecahedron is derived as the dual of the
icosahedron. The Archimedean, Catalan and stellated families are a follow-up.

.. autoclass:: pybosl2.parts.polyhedra.RegularPolyhedron
   :members:

.. autoclass:: pybosl2.parts.polyhedra.PolyhedronInfo
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``polyhedra.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``regular_polyhedron``

Tetrahedron:

.. pythonscad-example::

   from pybosl2.parts.polyhedra import RegularPolyhedron
   RegularPolyhedron("tetrahedron", radius=12).shape().show()

Cube:

.. pythonscad-example::

   from pybosl2.parts.polyhedra import RegularPolyhedron
   RegularPolyhedron("cube", radius=12).shape().show()

Octahedron:

.. pythonscad-example::

   from pybosl2.parts.polyhedra import RegularPolyhedron
   RegularPolyhedron("octahedron", radius=12).shape().show()

Dodecahedron:

.. pythonscad-example::

   from pybosl2.parts.polyhedra import RegularPolyhedron
   RegularPolyhedron("dodecahedron", radius=12).shape().show()

Icosahedron:

.. pythonscad-example::

   from pybosl2.parts.polyhedra import RegularPolyhedron
   RegularPolyhedron("icosahedron", radius=12).shape().show()

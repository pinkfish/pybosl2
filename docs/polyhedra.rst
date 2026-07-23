Polyhedra
=========

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/polyhedra.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


The five Platonic solids from BOSL2's ``polyhedra.scad``, built as watertight polyhedra.
:meth:`~bosl2.polyhedra.Polyhedra.regular_polyhedron` builds ``tetrahedron`` / ``cube`` /
``octahedron`` / ``dodecahedron`` / ``icosahedron`` (with named convenience methods too), sized by
circumradius, diameter, inradius or side length. The dodecahedron is derived as the dual of the
icosahedron. The Archimedean, Catalan and stellated families are a follow-up.

.. autoclass:: bosl2.polyhedra.Polyhedra
   :members:

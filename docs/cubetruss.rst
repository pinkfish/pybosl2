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

Walls
=====

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/walls.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


FDM-optimised wall shapes from BOSL2's ``walls.scad`` — parts that use less material and print
without support. :class:`~pybosl2.parts.walls.SparseWall` is an X-cross-braced open wall (and
:class:`~pybosl2.parts.walls.SparseCuboid` a solid-box variant braced along one axis);
:class:`~pybosl2.parts.walls.CorrugatedWall` a sinusoidal corrugated panel;
:class:`~pybosl2.parts.walls.ThinningWall` and :class:`~pybosl2.parts.walls.ThinningTriangle` walls whose
middle thins away while the edges stay thick, joined by angled shoulders that don't overhang;
:class:`~pybosl2.parts.walls.NarrowingStrut` the home-plate strut those triangles are built from. The
honeycomb ``hex_panel`` is a follow-up.

.. autoclass:: pybosl2.parts.walls.SparseWall
   :members:

.. autoclass:: pybosl2.parts.walls.SparseCuboid
   :members:

.. autoclass:: pybosl2.parts.walls.CorrugatedWall
   :members:

.. autoclass:: pybosl2.parts.walls.ThinningWall
   :members:

.. autoclass:: pybosl2.parts.walls.ThinningTriangle
   :members:

.. autoclass:: pybosl2.parts.walls.NarrowingStrut
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``walls.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``sparse_wall``

Typical shape:

.. pythonscad-example::

   from pybosl2.parts.walls import SparseWall, SparseCuboid, CorrugatedWall, ThinningWall, ThinningTriangle, NarrowingStrut
   SparseWall(height=40, length=100, thick=3).show()

Thinner strut:

.. pythonscad-example::

   from pybosl2.parts.walls import SparseWall, SparseCuboid, CorrugatedWall, ThinningWall, ThinningTriangle, NarrowingStrut
   SparseWall(height=40, length=100, thick=3, strut=2).show()

Larger maxang:

.. pythonscad-example::

   from pybosl2.parts.walls import SparseWall, SparseCuboid, CorrugatedWall, ThinningWall, ThinningTriangle, NarrowingStrut
   SparseWall(height=40, length=100, thick=3, strut=2, maxang=45).show()

Longer max_bridge:

.. pythonscad-example::

   from pybosl2.parts.walls import SparseWall, SparseCuboid, CorrugatedWall, ThinningWall, ThinningTriangle, NarrowingStrut
   SparseWall(height=40, length=100, thick=3, strut=2, maxang=45, max_bridge=30).show()

.. rubric:: ``sparse_cuboid``

A cross-braced box, braced along X:

.. pythonscad-example::

   from pybosl2.parts.walls import SparseAxis, SparseCuboid
   SparseCuboid([10, 20, 30], dir=SparseAxis.X, strut=1).show()

Braced along Y:

.. pythonscad-example::

   from pybosl2.parts.walls import SparseAxis, SparseCuboid
   SparseCuboid([10, 20, 30], dir=SparseAxis.Y, strut=1).show()

Braced along Z:

.. pythonscad-example::

   from pybosl2.parts.walls import SparseAxis, SparseCuboid
   SparseCuboid([10, 20, 30], dir=SparseAxis.Z, strut=1).show()

.. rubric:: ``corrugated_wall``

Typical shape:

.. pythonscad-example::

   from pybosl2.parts.walls import SparseWall, SparseCuboid, CorrugatedWall, ThinningWall, ThinningTriangle, NarrowingStrut
   CorrugatedWall(height=50, length=100).show()

Wider strut border:

.. pythonscad-example::

   from pybosl2.parts.walls import SparseWall, SparseCuboid, CorrugatedWall, ThinningWall, ThinningTriangle, NarrowingStrut
   CorrugatedWall(height=50, length=100, strut=8).show()

Thicker corrugation:

.. pythonscad-example::

   from pybosl2.parts.walls import SparseWall, SparseCuboid, CorrugatedWall, ThinningWall, ThinningTriangle, NarrowingStrut
   CorrugatedWall(height=50, length=100, strut=8, wall=3).show()

.. rubric:: ``thinning_wall``

Typical shape:

.. pythonscad-example::

   from pybosl2.parts.walls import SparseWall, SparseCuboid, CorrugatedWall, ThinningWall, ThinningTriangle, NarrowingStrut
   ThinningWall(height=50, length=80, thick=4).show()

Trapezoidal:

.. pythonscad-example::

   from pybosl2.parts.walls import SparseWall, SparseCuboid, CorrugatedWall, ThinningWall, ThinningTriangle, NarrowingStrut
   ThinningWall(height=50, length=[80, 50], thick=4).show()

.. rubric:: ``thinning_triangle``

Centered:

.. pythonscad-example::

   from pybosl2.parts.walls import SparseWall, SparseCuboid, CorrugatedWall, ThinningWall, ThinningTriangle, NarrowingStrut
   ThinningTriangle(height=50, length=80, thick=4, angle=30, strut=5, wall=2, center=True).show()

Resting on the ground plane:

.. pythonscad-example::

   from pybosl2.parts.walls import SparseWall, SparseCuboid, CorrugatedWall, ThinningWall, ThinningTriangle, NarrowingStrut
   ThinningTriangle(height=50, length=80, thick=4, angle=30, strut=5, wall=2, center=False).show()

Only the diagonal edge thickened:

.. pythonscad-example::

   from pybosl2.parts.walls import SparseWall, SparseCuboid, CorrugatedWall, ThinningWall, ThinningTriangle, NarrowingStrut
   ThinningTriangle(height=50, length=80, thick=4, angle=30, strut=5, wall=2, diagonly=True, center=False).show()

.. rubric:: ``narrowing_strut``

A support-free strut:

.. pythonscad-example::

   from pybosl2.parts.walls import SparseWall, SparseCuboid, CorrugatedWall, ThinningWall, ThinningTriangle, NarrowingStrut
   NarrowingStrut(w=10, length=100, wall=5, angle=30).show()

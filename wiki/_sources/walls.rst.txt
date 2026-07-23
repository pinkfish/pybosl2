Walls
=====

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/walls.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


FDM-optimised wall shapes from BOSL2's ``walls.scad`` — parts that use less material and print
without support. :meth:`~bosl2.walls.Walls.sparse_wall` is an X-cross-braced open wall (and
:meth:`~bosl2.walls.Walls.sparse_cuboid` a solid-box variant braced along one axis);
:meth:`~bosl2.walls.Walls.corrugated_wall` a sinusoidal corrugated panel;
:meth:`~bosl2.walls.Walls.thinning_wall` and :meth:`~bosl2.walls.Walls.thinning_triangle` walls whose
middle thins away while the edges stay thick, joined by angled shoulders that don't overhang;
:meth:`~bosl2.walls.Walls.narrowing_strut` the home-plate strut those triangles are built from. The
honeycomb ``hex_panel`` is a follow-up.

.. autoclass:: bosl2.walls.Walls
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``walls.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``sparse_wall``

Typical shape:

.. pythonscad-example::

   Walls.sparse_wall(h=40, l=100, thick=3).show()

Thinner strut:

.. pythonscad-example::

   Walls.sparse_wall(h=40, l=100, thick=3, strut=2).show()

Larger maxang:

.. pythonscad-example::

   Walls.sparse_wall(h=40, l=100, thick=3, strut=2, maxang=45).show()

Longer max_bridge:

.. pythonscad-example::

   Walls.sparse_wall(h=40, l=100, thick=3, strut=2, maxang=45, max_bridge=30).show()

.. rubric:: ``sparse_cuboid``

A cross-braced box, braced along X:

.. pythonscad-example::

   Walls.sparse_cuboid([10, 20, 30], dir="X", strut=1).show()

Braced along Y:

.. pythonscad-example::

   Walls.sparse_cuboid([10, 20, 30], dir="Y", strut=1).show()

Braced along Z:

.. pythonscad-example::

   Walls.sparse_cuboid([10, 20, 30], dir="Z", strut=1).show()

.. rubric:: ``corrugated_wall``

Typical shape:

.. pythonscad-example::

   Walls.corrugated_wall(h=50, l=100).show()

Wider strut border:

.. pythonscad-example::

   Walls.corrugated_wall(h=50, l=100, strut=8).show()

Thicker corrugation:

.. pythonscad-example::

   Walls.corrugated_wall(h=50, l=100, strut=8, wall=3).show()

.. rubric:: ``thinning_wall``

Typical shape:

.. pythonscad-example::

   Walls.thinning_wall(h=50, l=80, thick=4).show()

Trapezoidal:

.. pythonscad-example::

   Walls.thinning_wall(h=50, l=[80, 50], thick=4).show()

.. rubric:: ``thinning_triangle``

Centered:

.. pythonscad-example::

   Walls.thinning_triangle(h=50, l=80, thick=4, ang=30, strut=5, wall=2, center=True).show()

Resting on the ground plane:

.. pythonscad-example::

   Walls.thinning_triangle(h=50, l=80, thick=4, ang=30, strut=5, wall=2, center=False).show()

Only the diagonal edge thickened:

.. pythonscad-example::

   Walls.thinning_triangle(h=50, l=80, thick=4, ang=30, strut=5, wall=2, diagonly=True, center=False).show()

.. rubric:: ``narrowing_strut``

A support-free strut:

.. pythonscad-example::

   Walls.narrowing_strut(w=10, l=100, wall=5, ang=30).show()

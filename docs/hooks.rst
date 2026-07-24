Hooks
=====

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/hooks.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


Hooks and hook-like parts, from BOSL2's ``hooks.scad``. BOSL2 currently supplies a single part,
:meth:`~bosl2.hooks.Hooks.ring_hook`: a rectangular mounting base that flares up and joins
tangentially to a Y-axis cylinder — the "ring" — with an optional round, D-shaped or custom
through-hole. Give exactly two of ``or_/od``, ``ir/id`` and ``wall`` to size the ring wall (or a zero
inner radius for a solid paddle). The base's vertical edges and the hole mouth can be rounded; the
original's base weld ``fillet`` is a follow-up.
.. autoclass:: bosl2.hooks.Hooks
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``hooks.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``ring_hook``

Ring connector:

.. pythonscad-example::

   Hooks.ring_hook([50, 10], 25, outer_radius=25, inner_radius=20).show()

A solid paddle with no hole (inner_radius=0):

.. pythonscad-example::

   Hooks.ring_hook([70, 10], 25, outer_radius=25, inner_radius=0).show()

Narrow base — corners still outside the ring:

.. pythonscad-example::

   Hooks.ring_hook([40, 10], 25, outer_radius=25, inner_radius=0).show()

Hole sized by or/ir:

.. pythonscad-example::

   Hooks.ring_hook([50, 10], 40, outer_radius=25, inner_radius=20).show()

The same hole, sized by wall thickness:

.. pythonscad-example::

   Hooks.ring_hook([50, 10], 40, outer_radius=25, wall=5).show()

The same hole again, sized by od/id:

.. pythonscad-example::

   Hooks.ring_hook([50, 10], 40, outer_diameter=50, inner_diameter=40).show()

A semicircular D-hole:

.. pythonscad-example::

   Hooks.ring_hook([50, 10], 12, outer_radius=25, inner_radius=15, hole="D", rounding=3, hole_rounding=3).show()

Small hole_z with a D-hole:

.. pythonscad-example::

   Hooks.ring_hook([50, 10], 1, outer_radius=25, inner_radius=15, hole="D").show()

Rounded outer edges:

.. pythonscad-example::

   Hooks.ring_hook([50, 10], 40, outer_radius=25, inner_radius=15, rounding=5).show()

An arbitrary (octagonal) hole, printable without support:

.. pythonscad-example::

   Hooks.ring_hook([50, 20], 30, outer_radius=25, hole=[[13*math.cos(math.radians(22.5+45*k)), 13*math.sin(math.radians(22.5+45*k))] for k in range(8)], hole_rounding=3, rounding=4).show()

Linear bearings
===============

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/linear_bearings.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


Pure-Python port of BOSL2's ``linear_bearings.scad``: models of LMxUU linear ball bearings that run
along a rod, and the pillow-block housings that clamp them to a plate.
:meth:`~bosl2.linear_bearings.LinearBearings.lmXuu_bearing` looks a standard size up in
:meth:`~bosl2.linear_bearings.LinearBearings.lmXuu_info` (a
:class:`~bosl2.linear_bearings.LinearBearingSpec` table);
:meth:`~bosl2.linear_bearings.LinearBearings.linear_bearing` is the generic form.

.. autoclass:: bosl2.linear_bearings.LinearBearingSpec
   :members:

.. autoclass:: bosl2.linear_bearings.LinearBearings
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``linear_bearings.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``linear_bearing``

A generic cartridge:

.. pythonscad-example::

   LinearBearings.linear_bearing(length=24, outer_diameter=15, inner_diameter=8).show()

.. rubric:: ``lmXuu_bearing``

A standard LM10UU:

.. pythonscad-example::

   LinearBearings.lmXuu_bearing(size=10).show()

.. rubric:: ``linear_bearing_housing``

A pillow-block housing:

.. pythonscad-example::

   LinearBearings.linear_bearing_housing(diameter=19, length=29, wall=2, tab=8, screwsize=2.5).show()

.. rubric:: ``lmXuu_housing``

A housing sized for an LM10UU:

.. pythonscad-example::

   LinearBearings.lmXuu_housing(size=10, wall=2, tab=6, screwsize=2.5).show()

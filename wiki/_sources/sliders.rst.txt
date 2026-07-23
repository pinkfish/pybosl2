Sliders & rails
===============

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/index.html">Parts catalog &rarr;</a></b>
     &nbsp;&mdash;&nbsp; this module is featured in the visual parts catalog.
   </p>


Pure-Python port of BOSL2's ``sliders.scad``: a V-groove :meth:`~bosl2.sliders.Sliders.slider` and
the matching :meth:`~bosl2.sliders.Sliders.rail`, both designed to 3-D print without support. Tune
the printed fit with the slider's ``slop``.

.. autoclass:: bosl2.sliders.Sliders
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``sliders.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``slider``

A V-groove slider:

.. pythonscad-example::

   Sliders.slider(l=30, base=10, wall=4, slop=0.2).show()

.. rubric:: ``rail``

The mating rail:

.. pythonscad-example::

   Sliders.rail(l=100, w=10, h=10).show()

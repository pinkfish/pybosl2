Sliders & rails
===============

.. raw:: html

   <p style="margin-top:0;margin-bottom:1.2em">&#9881;&#65039; <b><a href="specs/sliders.html">Spec sheet &rarr;</a></b> &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.</p>


.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/index.html">Parts catalog &rarr;</a></b>
     &nbsp;&mdash;&nbsp; this module is featured in the visual parts catalog.
   </p>


Pure-Python port of BOSL2's ``sliders.scad``: a V-groove :class:`~pybosl2.parts.sliders.Slider` and
the matching :class:`~pybosl2.parts.sliders.Rail`, both designed to 3-D print without support. Tune
the printed fit with the slider's ``slop``.

.. autoclass:: pybosl2.parts.sliders.Slider
   :members:

.. autoclass:: pybosl2.parts.sliders.Rail
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``sliders.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``slider``

A V-groove slider:

.. pythonscad-example::

   from pybosl2.parts.sliders import Slider
   Slider(l=30, base=10, wall=4, slop=0.2).shape.show()

.. rubric:: ``rail``

The mating rail:

.. pythonscad-example::

   from pybosl2.parts.sliders import Rail
   Rail(l=100, w=10, h=10).shape.show()

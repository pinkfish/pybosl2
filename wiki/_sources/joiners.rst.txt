Joiners
=======

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/joiners.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


Pure-Python port of the core joiners from BOSL2's ``joiners.scad`` — shapes for connecting two
separately-printed parts. :meth:`~bosl2.joiners.Joiners.dovetail` is the flagship: a (optionally
tapered) dovetail joint you attach as a male tenon or difference out as a female socket. A functional
:meth:`~bosl2.joiners.Joiners.snap_pin` and its :meth:`~bosl2.joiners.Joiners.snap_pin_socket` give a
press-and-click pin.

.. autoclass:: bosl2.joiners.Joiners
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``joiners.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``dovetail``

Straight dovetail, male:

.. pythonscad-example::

   Joiners.dovetail("male", width=15, height=8, slide=30).show()

Straight dovetail, female socket:

.. pythonscad-example::

   Joiners.dovetail("female", width=15, height=8, slide=30).show()

A 6-degree taper:

.. pythonscad-example::

   Joiners.dovetail("male", width=15, height=8, slide=30, taper=6).show()

Setting the dovetail angle:

.. pythonscad-example::

   Joiners.dovetail("male", width=15, height=8, slide=10, angle=30).show()

A narrower back width:

.. pythonscad-example::

   Joiners.dovetail("male", slide=50, width=18, height=4, back_width=15).show()

Setting the flank slope:

.. pythonscad-example::

   Joiners.dovetail("male", slide=15, width=20, height=8, slope=2).show()

.. rubric:: ``snap_pin``

A snap pin:

.. pythonscad-example::

   Joiners.snap_pin().show()

.. rubric:: ``snap_pin_socket``

The matching socket:

.. pythonscad-example::

   Joiners.snap_pin_socket().show()

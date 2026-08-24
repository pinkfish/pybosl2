Modular hose
============

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/modular_hose.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


Pure-Python port of BOSL2's ``modular_hose.scad``: the ball-and-socket segments of a modular
"Loc-Line" style adjustable/coolant hose. :class:`~pybosl2.parts.modular_hose.HoseSegment`
revolves a ball end, a socket end, or a full segment for the 1/4", 1/2" and 3/4" sizes;
:func:`~pybosl2.parts.modular_hose.modular_hose_radius` gives the bore radius.

.. autoclass:: pybosl2.parts.modular_hose.HoseSegment
   :members:

.. autofunction:: pybosl2.parts.modular_hose.modular_hose_radius

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``modular_hose.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``modular_hose``

1/4" segment:

.. pythonscad-example::

   from pybosl2.parts.modular_hose import HoseSegment, HoseType
   HoseSegment(0.25, HoseType.SEGMENT).shape.show()

1/2" segment:

.. pythonscad-example::

   from pybosl2.parts.modular_hose import HoseSegment, HoseType
   HoseSegment(0.5, HoseType.SEGMENT).shape.show()

3/4" segment:

.. pythonscad-example::

   from pybosl2.parts.modular_hose import HoseSegment, HoseType
   HoseSegment(0.75, HoseType.SEGMENT).shape.show()

1/2" ball end with a longer waist:

.. pythonscad-example::

   from pybosl2.parts.modular_hose import HoseSegment, HoseType
   HoseSegment(0.5, HoseType.BALL, waist_len=15).shape.show()

3/4" socket end:

.. pythonscad-example::

   from pybosl2.parts.modular_hose import HoseSegment, HoseType
   HoseSegment(0.75, HoseType.SOCKET).shape.show()

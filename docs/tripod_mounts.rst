Tripod mounts
============

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/tripod_mounts.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


Pure-Python port of BOSL2's ``tripod_mounts.scad``: a
:meth:`~pybosl2.parts.tripod_mounts.TripodMounts.manfrotto_rc2_plate` — the
standard Manfrotto RC2 quick-release tripod mount plate.

.. autoclass:: pybosl2.parts.tripod_mounts.TripodMounts
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``tripod_mounts.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``manfrotto_rc2_plate``

A standard Manfrotto RC2 plate with full chamfering:

.. pythonscad-example::

   from pybosl2.parts.tripod_mounts import TripodMounts
   TripodMounts.manfrotto_rc2_plate().show()

A plate with bottom-only chamfering:

.. pythonscad-example::

   from pybosl2.parts.tripod_mounts import TripodMounts
   TripodMounts.manfrotto_rc2_plate(chamfer="bot").show()

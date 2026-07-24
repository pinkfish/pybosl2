Ball bearings
=============

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/ball_bearings.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


Pure-Python port of BOSL2's ``ball_bearings.scad``: models of standard ball-bearing cartridges.
:meth:`~bosl2.ball_bearings.BallBearings.ball_bearing` builds one from a trade-size name or explicit
dimensions; :meth:`~bosl2.ball_bearings.BallBearings.ball_bearing_info` returns the tabulated
dimensions as a :class:`~bosl2.ball_bearings.BearingSpec`.

.. autoclass:: bosl2.ball_bearings.BearingSpec
   :members:

.. autoclass:: bosl2.ball_bearings.BallBearings
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``ball_bearings.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``ball_bearing``

A 608 skate bearing:

.. pythonscad-example::

   BallBearings.ball_bearing("608").show()

A shielded 608ZZ:

.. pythonscad-example::

   BallBearings.ball_bearing("608ZZ").show()

An R8 imperial bearing:

.. pythonscad-example::

   BallBearings.ball_bearing("R8").show()

A custom open bearing by dimensions:

.. pythonscad-example::

   BallBearings.ball_bearing(inner_diameter=12, outer_diameter=32, width=10, shield=False).show()

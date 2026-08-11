NEMA steppers
=============

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/nema_steppers.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


Pure-Python port of BOSL2's ``nema_steppers.scad``: models of NEMA-standard stepper motors and the
masks that cut their mounting-hole pattern into a plate.
:class:`~pybosl2.parts.nema_steppers.NemaMotor` builds a motor (body, plinth, shaft and
blind screw holes) for a NEMA size; :class:`~pybosl2.parts.nema_steppers.NemaMountMask` is the
bolt-pattern-plus-plinth cutout; :class:`~pybosl2.parts.nema_steppers.NemaSpec` returns
the standard dimensions.

.. autoclass:: pybosl2.parts.nema_steppers.NemaSpec
   :members:

.. autoclass:: pybosl2.parts.nema_steppers.NemaMotor
   :members:

.. autoclass:: pybosl2.parts.nema_steppers.NemaMountMask
   :members:

.. autoclass:: pybosl2.parts.nema_steppers.NemaMaskType
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``nema_steppers.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``nema_stepper_motor``

NEMA 8:

.. pythonscad-example::

   from pybosl2.parts.nema_steppers import NemaMotor
   NemaMotor(size=8, height=24, shaft_len=15).show()

NEMA 11:

.. pythonscad-example::

   from pybosl2.parts.nema_steppers import NemaMotor
   NemaMotor(size=11, height=24, shaft_len=20).show()

NEMA 17:

.. pythonscad-example::

   from pybosl2.parts.nema_steppers import NemaMotor
   NemaMotor(size=17, height=40, shaft_len=30).show()

NEMA 23:

.. pythonscad-example::

   from pybosl2.parts.nema_steppers import NemaMotor
   NemaMotor(size=23, height=50, shaft_len=40).show()

.. rubric:: ``nema_mount_mask``

Bolt-pattern mask for a NEMA 14:

.. pythonscad-example::

   from pybosl2.parts.nema_steppers import NemaMountMask
   NemaMountMask(size=14, depth=5, length=5).show()

NEMA 17 with slotted holes:

.. pythonscad-example::

   from pybosl2.parts.nema_steppers import NemaMountMask
   NemaMountMask(size=17, depth=5, length=5).show()

NEMA 17 with round holes (length=0):

.. pythonscad-example::

   from pybosl2.parts.nema_steppers import NemaMountMask
   NemaMountMask(size=17, depth=5, length=0).show()

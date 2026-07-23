NEMA steppers
=============

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/nema_steppers.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


Pure-Python port of BOSL2's ``nema_steppers.scad``: models of NEMA-standard stepper motors and the
masks that cut their mounting-hole pattern into a plate.
:meth:`~bosl2.nema_steppers.NemaSteppers.nema_stepper_motor` builds a motor (body, plinth, shaft and
blind screw holes) for a NEMA size; :meth:`~bosl2.nema_steppers.NemaSteppers.nema_mount_mask` is the
bolt-pattern-plus-plinth cutout; :meth:`~bosl2.nema_steppers.NemaSteppers.nema_motor_info` returns
the standard dimensions as a :class:`~bosl2.nema_steppers.NemaSpec`.

.. autoclass:: bosl2.nema_steppers.NemaSpec
   :members:

.. autoclass:: bosl2.nema_steppers.NemaSteppers
   :members:

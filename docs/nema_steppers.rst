NEMA steppers
=============

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

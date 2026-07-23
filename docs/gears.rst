Gears
=====

Pure-Python port of BOSL2's current ``gears.scad``. Gears are sized by circular pitch
(``circ_pitch``), metric ``mod``, or ``diam_pitch``; the 20-degree ``pressure_angle`` and
``profile_shift="auto"`` defaults match BOSL2, so low-tooth-count gears automatically get the
profile shift that avoids undercut. The involute spur teeth are **rack-generated** -- the working
involute flank plus the trochoid a meshing rack would carve -- so low-tooth gears show a real
undercut.

Includes the involute :meth:`~bosl2.gears.Gears.spur_gear2d` / :meth:`~bosl2.gears.Gears.spur_gear`
(helical and/or ``herringbone``), the internal :meth:`~bosl2.gears.Gears.ring_gear`, the linear
:meth:`~bosl2.gears.Gears.rack`, the :meth:`~bosl2.gears.Gears.bevel_gear`, the
:meth:`~bosl2.gears.Gears.worm` / :meth:`~bosl2.gears.Gears.worm_gear` pair, the dimension helpers,
:meth:`~bosl2.gears.Gears.auto_profile_shift`, and :meth:`~bosl2.gears.Gears.gear_dist` for the
meshing centre distance.

.. autoclass:: bosl2.gears.Gears
   :members:

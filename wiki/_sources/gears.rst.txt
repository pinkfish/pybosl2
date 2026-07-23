Gears
=====

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/gears.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


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

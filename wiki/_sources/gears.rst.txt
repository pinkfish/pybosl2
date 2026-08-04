Gears
=====

.. raw:: html

   <p style="margin-top:0;margin-bottom:1.2em">&#9881;&#65039; <b><a href="specs/gears.html">Spec sheet &rarr;</a></b> &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.</p>



Pure-Python port of BOSL2's current ``gears.scad``. Gears are sized by circular pitch
(``circ_pitch``), metric ``mod``, or ``diam_pitch``; the 20-degree ``pressure_angle`` and
``profile_shift="auto"`` defaults match BOSL2, so low-tooth-count gears automatically get the
profile shift that avoids undercut. The involute spur teeth are **rack-generated** -- the working
involute flank plus the trochoid a meshing rack would carve -- so low-tooth gears show a real
undercut.

Includes the involute :meth:`~pybosl2.parts.gears.Gears.spur_gear2d` / :meth:`~pybosl2.parts.gears.Gears.spur_gear`
(helical and/or ``herringbone``), the internal :meth:`~pybosl2.parts.gears.Gears.ring_gear`, the linear
:meth:`~pybosl2.parts.gears.Gears.rack`, the :meth:`~pybosl2.parts.gears.Gears.bevel_gear`, the
:meth:`~pybosl2.parts.gears.Gears.worm` / :meth:`~pybosl2.parts.gears.Gears.worm_gear` pair, the dimension helpers,
:meth:`~pybosl2.parts.gears.Gears.auto_profile_shift`, and :meth:`~pybosl2.parts.gears.Gears.gear_dist` for the
meshing centre distance.

.. autoclass:: pybosl2.parts.gears.Gears
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``gears.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``spur_gear``

A spur gear by circular pitch:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.spur_gear(circ_pitch=5, teeth=20, thickness=8, shaft_diam=5).show()

By metric module:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.spur_gear(mod=2, teeth=20, thickness=8, shaft_diam=5).show()

A helical gear:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.spur_gear(circ_pitch=5, teeth=20, thickness=10, shaft_diam=5, helical=-30, slices=12).show()

A herringbone gear:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.spur_gear(circ_pitch=5, teeth=20, thickness=10, shaft_diam=5, helical=30, herringbone=True, slices=5).show()

.. rubric:: ``ring_gear``

An internal ring gear:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.ring_gear(circ_pitch=5, teeth=48, thickness=10).show()

Thicker backing:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.ring_gear(circ_pitch=5, teeth=48, thickness=10, backing=30).show()

A higher pressure angle:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.ring_gear(circ_pitch=5, teeth=48, thickness=10, pressure_angle=28).show()

With a profile shift:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.ring_gear(circ_pitch=5, teeth=48, thickness=10, profile_shift=0.5).show()

Helical:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.ring_gear(circ_pitch=5, teeth=48, thickness=15, helical=30).show()

.. rubric:: ``rack``

A linear rack:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.rack(pitch=5, teeth=10, thickness=5).show()

A rack at 14.5 deg pressure angle:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.rack(mod=2, teeth=10, thickness=5, pressure_angle=14.5).show()

.. rubric:: ``bevel_gear``

A 45 deg bevel gear:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.bevel_gear(circ_pitch=5, teeth=36, mate_teeth=36, shaft_diam=5).show()

By module:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.bevel_gear(mod=4, teeth=20, face_width=10, pitch_angle=45, shaft_diam=6).show()

.. rubric:: ``worm``

A single-start worm:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.worm(circ_pitch=8, diameter=30, length=50).show()

A 3-start worm:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.worm(circ_pitch=8, diameter=30, length=50, starts=3).show()

A left-handed 3-start worm:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.worm(circ_pitch=8, diameter=30, length=50, starts=3, left_handed=True).show()

.. rubric:: ``worm_gear``

A worm gear:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.worm_gear(circ_pitch=5, teeth=36, worm_diam=30, worm_starts=1).show()

Left-handed:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.worm_gear(circ_pitch=5, teeth=36, worm_diam=30, worm_starts=1, left_handed=True).show()

Meshing a 4-start worm:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.worm_gear(circ_pitch=5, teeth=36, worm_diam=30, worm_starts=4).show()

By module:

.. pythonscad-example::

   from pybosl2.parts.gears import Gears
   Gears.worm_gear(mod=2, teeth=32, worm_diam=30, worm_starts=1).show()

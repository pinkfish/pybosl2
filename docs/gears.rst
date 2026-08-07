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

Includes the involute :class:`SpurGear2d` / :class:`SpurGear`
(helical and/or ``herringbone``), the internal :class:`RingGear`, the linear
:class:`Rack`, the :class:`BevelGear`, the
:class:`Worm` / :class:`WormGear` pair, the dimension helpers,
:func:`auto_profile_shift`, and :func:`gear_dist` for the
meshing centre distance.

.. autoclass:: pybosl2.parts.gears.SpurGear
   :members:

.. autoclass:: pybosl2.parts.gears.SpurGear2d
   :members:

.. autoclass:: pybosl2.parts.gears.RingGear
   :members:

.. autoclass:: pybosl2.parts.gears.Rack
   :members:

.. autoclass:: pybosl2.parts.gears.Rack2d
   :members:

.. autoclass:: pybosl2.parts.gears.BevelGear
   :members:

.. autoclass:: pybosl2.parts.gears.Worm
   :members:

.. autoclass:: pybosl2.parts.gears.WormGear
   :members:

.. autoclass:: pybosl2.parts.gears.HerringboneGear
   :members:

.. autoclass:: pybosl2.parts.gears.GearToothProfile
   :members:

.. autofunction:: pybosl2.parts.gears.circular_pitch

.. autofunction:: pybosl2.parts.gears.diametral_pitch

.. autofunction:: pybosl2.parts.gears.module_value

.. autofunction:: pybosl2.parts.gears.pitch_value

.. autofunction:: pybosl2.parts.gears.pitch_radius

.. autofunction:: pybosl2.parts.gears.outer_radius

.. autofunction:: pybosl2.parts.gears.root_radius

.. autofunction:: pybosl2.parts.gears.base_radius

.. autofunction:: pybosl2.parts.gears.auto_profile_shift

.. autofunction:: pybosl2.parts.gears.gear_dist

.. autofunction:: pybosl2.parts.gears.worm_gear_thickness

.. autofunction:: pybosl2.parts.gears.bevel_pitch_angle

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``gears.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``spur_gear``

A spur gear by circular pitch:

.. pythonscad-example::

   from pybosl2.parts.gears import SpurGear
   SpurGear(circ_pitch=5, teeth=20, thickness=8, shaft_diam=5).shape().show()

By metric module:

.. pythonscad-example::

   from pybosl2.parts.gears import SpurGear
   SpurGear(mod=2, teeth=20, thickness=8, shaft_diam=5).shape().show()

A helical gear:

.. pythonscad-example::

   from pybosl2.parts.gears import SpurGear
   SpurGear(circ_pitch=5, teeth=20, thickness=10, shaft_diam=5, helical=-30, slices=12).shape().show()

A herringbone gear:

.. pythonscad-example::

   from pybosl2.parts.gears import SpurGear
   SpurGear(circ_pitch=5, teeth=20, thickness=10, shaft_diam=5, helical=30, herringbone=True, slices=5).shape().show()

.. rubric:: ``ring_gear``

An internal ring gear:

.. pythonscad-example::

   from pybosl2.parts.gears import RingGear
   RingGear(circ_pitch=5, teeth=48, thickness=10).shape().show()

Thicker backing:

.. pythonscad-example::

   from pybosl2.parts.gears import RingGear
   RingGear(circ_pitch=5, teeth=48, thickness=10, backing=30).shape().show()

A higher pressure angle:

.. pythonscad-example::

   from pybosl2.parts.gears import RingGear
   RingGear(circ_pitch=5, teeth=48, thickness=10, pressure_angle=28).shape().show()

With a profile shift:

.. pythonscad-example::

   from pybosl2.parts.gears import RingGear
   RingGear(circ_pitch=5, teeth=48, thickness=10, profile_shift=0.5).shape().show()

Helical:

.. pythonscad-example::

   from pybosl2.parts.gears import RingGear
   RingGear(circ_pitch=5, teeth=48, thickness=15, helical=30).shape().show()

.. rubric:: ``rack``

A linear rack:

.. pythonscad-example::

   from pybosl2.parts.gears import Rack
   Rack(pitch=5, teeth=10, thickness=5).shape().show()

A rack at 14.5 deg pressure angle:

.. pythonscad-example::

   from pybosl2.parts.gears import Rack
   Rack(mod=2, teeth=10, thickness=5, pressure_angle=14.5).shape().show()

.. rubric:: ``bevel_gear``

A 45 deg bevel gear:

.. pythonscad-example::

   from pybosl2.parts.gears import BevelGear
   BevelGear(circ_pitch=5, teeth=36, mate_teeth=36, shaft_diam=5).shape().show()

By module:

.. pythonscad-example::

   from pybosl2.parts.gears import BevelGear
   BevelGear(mod=4, teeth=20, face_width=10, pitch_angle=45, shaft_diam=6).shape().show()

.. rubric:: ``worm``

A single-start worm:

.. pythonscad-example::

   from pybosl2.parts.gears import Worm
   Worm(circ_pitch=8, diameter=30, length=50).shape().show()

A 3-start worm:

.. pythonscad-example::

   from pybosl2.parts.gears import Worm
   Worm(circ_pitch=8, diameter=30, length=50, starts=3).shape().show()

A left-handed 3-start worm:

.. pythonscad-example::

   from pybosl2.parts.gears import Worm
   Worm(circ_pitch=8, diameter=30, length=50, starts=3, left_handed=True).shape().show()

.. rubric:: ``worm_gear``

A worm gear:

.. pythonscad-example::

   from pybosl2.parts.gears import WormGear
   WormGear(circ_pitch=5, teeth=36, worm_diam=30, worm_starts=1).shape().show()

Left-handed:

.. pythonscad-example::

   from pybosl2.parts.gears import WormGear
   WormGear(circ_pitch=5, teeth=36, worm_diam=30, worm_starts=1, left_handed=True).shape().show()

Meshing a 4-start worm:

.. pythonscad-example::

   from pybosl2.parts.gears import WormGear
   WormGear(circ_pitch=5, teeth=36, worm_diam=30, worm_starts=4).shape().show()

By module:

.. pythonscad-example::

   from pybosl2.parts.gears import WormGear
   WormGear(mod=2, teeth=32, worm_diam=30, worm_starts=1).shape().show()

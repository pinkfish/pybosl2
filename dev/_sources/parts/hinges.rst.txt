Hinges
======

.. raw:: html

   <p style="margin-top:0;margin-bottom:1.2em">&#9881;&#65039; <b><a href="specs/hinges.html">Spec sheet &rarr;</a></b> &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.</p>



Pure-Python port of the hinges in BOSL2's ``hinges.scad``: a print-in-place
:class:`~pybosl2.parts.hinges.LivingHingeMask` (differenced from a plate to make a folding "live"
hinge), a functional interlocking :class:`~pybosl2.parts.hinges.KnuckleHinge` leaf (with
:class:`~pybosl2.parts.hinges.KnuckleHingePair` for both leaves meshed around one pin, at any fold
angle), and simple :class:`~pybosl2.parts.hinges.SnapLock` / :class:`~pybosl2.parts.hinges.SnapSocket`
connectors.

.. autoclass:: pybosl2.parts.hinges.KnuckleHinge
   :members:

.. autoclass:: pybosl2.parts.hinges.KnuckleHingePair
   :members:

.. autoclass:: pybosl2.parts.hinges.LivingHingeMask
   :members:

.. autoclass:: pybosl2.parts.hinges.SnapLock
   :members:

.. autoclass:: pybosl2.parts.hinges.SnapSocket
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``hinges.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``knuckle_hinge``

A 5-knuckle hinge leaf:

.. pythonscad-example::

   from pybosl2.parts.hinges import KnuckleHinge
   KnuckleHinge(length=35, segs=5).shape.show()

.. rubric:: ``knuckle_hinge_pair``

A meshed hinge pair:

.. pythonscad-example::

   from pybosl2.parts.hinges import KnuckleHingePair
   KnuckleHingePair(length=40, segs=5).shape.show()

.. rubric:: ``living_hinge_mask``

A living-hinge groove mask:

.. pythonscad-example::

   from pybosl2.parts.hinges import LivingHingeMask
   LivingHingeMask(length=100, thick=3, foldangle=60).shape.show()

.. rubric:: ``snap_lock``

A snap lock:

.. pythonscad-example::

   from pybosl2.parts.hinges import SnapLock
   SnapLock(thick=3, foldangle=60).shape.show()

.. rubric:: ``snap_socket``

A snap socket:

.. pythonscad-example::

   from pybosl2.parts.hinges import SnapSocket
   SnapSocket(thick=3, foldangle=60).shape.show()

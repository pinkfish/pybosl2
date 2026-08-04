Hinges
======


Pure-Python port of the hinges in BOSL2's ``hinges.scad``: a print-in-place
:meth:`~pybosl2.parts.hinges.Hinges.living_hinge_mask` (differenced from a plate to make a folding "live"
hinge), a functional interlocking :meth:`~pybosl2._sdf.joiners` leaf (with
:meth:`~pybosl2.parts.hinges.Hinges.knuckle_hinge_pair` for both leaves meshed around one pin, at any fold
angle), and simple :meth:`~pybosl2.parts.hinges.Hinges.snap_lock` / :meth:`~pybosl2.parts.hinges.Hinges.snap_socket`
connectors.

.. autoclass:: pybosl2.parts.hinges.Hinges
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``hinges.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``knuckle_hinge``

A 5-knuckle hinge leaf:

.. pythonscad-example::

   Hinges.knuckle_hinge(length=35, segs=5).show()

.. rubric:: ``knuckle_hinge_pair``

A meshed hinge pair:

.. pythonscad-example::

   Hinges.knuckle_hinge_pair(length=40, segs=5).show()

.. rubric:: ``living_hinge_mask``

A living-hinge groove mask:

.. pythonscad-example::

   Hinges.living_hinge_mask(length=100, thick=3, foldangle=60).show()

.. rubric:: ``snap_lock``

A snap lock:

.. pythonscad-example::

   Hinges.snap_lock(thick=3, foldangle=60).show()

.. rubric:: ``snap_socket``

A snap socket:

.. pythonscad-example::

   Hinges.snap_socket(thick=3, foldangle=60).show()

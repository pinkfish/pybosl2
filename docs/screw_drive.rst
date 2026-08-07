Screw drives: Phillips, hex, Torx & Robertson recesses
======================================================

.. raw:: html

   <p style="margin-top:0;margin-bottom:1.2em">&#9881;&#65039; <b><a href="specs/screw_drive.html">Spec sheet &rarr;</a></b> &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.</p>


.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/index.html">Parts catalog &rarr;</a></b>
     &nbsp;&mdash;&nbsp; this module is featured in the visual parts catalog.
   </p>


Pure-Python port of BOSL2's ``screw_drive.scad``: masks for the driver recess cut into a screw
head. The :mod:`pybosl2.parts.screw_drive` module provides classes and functions that each return a
:class:`~pybosl2.shapes3d` mask -- subtract one from a head to make the recess::

    head - PhillipsMask("#2").shape()     # a #2 Phillips recess
    head - HexDriveMask(5, 4).shape()     # a 5mm hex (Allen) recess, 4mm deep
    head - TorxMask(30, 4).shape()        # a T30 Torx recess
    head - RobertsonMask(2).shape()       # a #2 Robertson/square recess

Every ``*Mask`` is built bottom-on-the-XY-plane (BOSL2's ``anchor=BOTTOM``); pass ``center=True``
to center it vertically. The dimensional helpers -- :func:`~pybosl2.parts.screw_drive.torx_info`,
:func:`~pybosl2.parts.screw_drive.torx_diam`, :func:`~pybosl2.parts.screw_drive.torx_depth`,
:func:`~pybosl2.parts.screw_drive.phillips_depth` and
:func:`~pybosl2.parts.screw_drive.phillips_diam` -- return the same numbers as their BOSL2
counterparts.

The dimension tables (Phillips ISO 4757, the Torx ISO 14583 OD/ID/depth/rounding table, and the
Robertson square-drive inch table) are transcribed verbatim from ``screw_drive.scad`` and checked in
``tests/test_screw_drive.py``.

Examples
--------

A #2 Phillips recess cut into a tapered head:

.. pythonscad-example::

    from pybosl2 import shapes3d as s3
    from pybosl2.parts.screw_drive import PhillipsMask

    (s3.cyl(diameter1=2, diameter2=8, height=4).down(2) - PhillipsMask("#2").shape()).show()

A T30 Torx tip:

.. pythonscad-example::

    from pybosl2.parts.screw_drive import TorxMask
    TorxMask(size=30, l=10).shape().show()

API reference
-------------

.. autoclass:: pybosl2.parts.screw_drive.PhillipsMask
   :members:

.. autoclass:: pybosl2.parts.screw_drive.HexDriveMask
   :members:

.. autoclass:: pybosl2.parts.screw_drive.TorxMask
   :members:

.. autoclass:: pybosl2.parts.screw_drive.TorxMask2d
   :members:

.. autoclass:: pybosl2.parts.screw_drive.RobertsonMask
   :members:

.. autofunction:: pybosl2.parts.screw_drive.hex_mask

.. autofunction:: pybosl2.parts.screw_drive.torx_info

.. autofunction:: pybosl2.parts.screw_drive.torx_diam

.. autofunction:: pybosl2.parts.screw_drive.torx_depth

.. autofunction:: pybosl2.parts.screw_drive.phillips_depth

.. autofunction:: pybosl2.parts.screw_drive.phillips_diam

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``screw_drive.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``phillips_mask``

A #1 Phillips recess:

.. pythonscad-example::

   from pybosl2.parts.screw_drive import PhillipsMask

   PhillipsMask(size="#1").shape().show()

A #2 Phillips recess:

.. pythonscad-example::

   from pybosl2.parts.screw_drive import PhillipsMask

   PhillipsMask(size="#2").shape().show()

A #3 Phillips recess:

.. pythonscad-example::

   from pybosl2.parts.screw_drive import PhillipsMask

   PhillipsMask(size=3).shape().show()

.. rubric:: ``robertson_mask``

A #2 Robertson (square) recess:

.. pythonscad-example::

   from pybosl2.parts.screw_drive import RobertsonMask

   RobertsonMask(size=2).shape().show()

Screw drives: Phillips, hex, Torx & Robertson recesses
======================================================

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/index.html">Parts catalog &rarr;</a></b>
     &nbsp;&mdash;&nbsp; this module is featured in the visual parts catalog.
   </p>


Pure-Python port of BOSL2's ``screw_drive.scad``: masks for the driver recess cut into a screw
head. The :class:`~bosl2.screw_drive.ScrewDrive` class groups them as static methods that return a
:class:`~bosl2.shapes3d.Bosl2Solid` mask -- subtract one from a head to make the recess::

    head - ScrewDrive.phillips_mask("#2")     # a #2 Phillips recess
    head - ScrewDrive.hex_drive_mask(5, 4)    # a 5mm hex (Allen) recess, 4mm deep
    head - ScrewDrive.torx_mask(30, 4)        # a T30 Torx recess
    head - ScrewDrive.robertson_mask(2)       # a #2 Robertson/square recess

Every ``*_mask`` is built bottom-on-the-XY-plane (BOSL2's ``anchor=BOTTOM``); pass ``center=True``
to center it vertically. The dimensional helpers -- :meth:`~bosl2.screw_drive.ScrewDrive.torx_info`,
:meth:`~bosl2.screw_drive.ScrewDrive.torx_diam`, :meth:`~bosl2.screw_drive.ScrewDrive.torx_depth`,
:meth:`~bosl2.screw_drive.ScrewDrive.phillips_depth` and
:meth:`~bosl2.screw_drive.ScrewDrive.phillips_diam` -- return the same numbers as their BOSL2
counterparts.

The dimension tables (Phillips ISO 4757, the Torx ISO 14583 OD/ID/depth/rounding table, and the
Robertson square-drive inch table) are transcribed verbatim from ``screw_drive.scad`` and checked in
``tests/test_screw_drive.py``.

Examples
--------

A #2 Phillips recess cut into a tapered head:

.. pythonscad-example::

    from bosl2.screw_drive import ScrewDrive
    (s3.cyl(diameter1=2, diameter2=8, height=4).down(2) - ScrewDrive.phillips_mask("#2")).show()

A T30 Torx tip:

.. pythonscad-example::

    from bosl2.screw_drive import ScrewDrive
    ScrewDrive.torx_mask(size=30, length=10).show()

API reference
-------------
.. autoclass:: bosl2.screw_drive.ScrewDrive
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``screw_drive.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``phillips_mask``

A #1 Phillips recess:

.. pythonscad-example::

   ScrewDrive.phillips_mask(size="#1").show()

A #2 Phillips recess:

.. pythonscad-example::

   ScrewDrive.phillips_mask(size="#2").show()

A #3 Phillips recess:

.. pythonscad-example::

   ScrewDrive.phillips_mask(size=3).show()

.. rubric:: ``robertson_mask``

A #2 Robertson (square) recess:

.. pythonscad-example::

   ScrewDrive.robertson_mask(size=2).show()

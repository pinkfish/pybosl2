Screw drives: Phillips, hex, Torx & Robertson recesses
======================================================

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
    (s3.cyl(d1=2, d2=8, h=4).down(2) - ScrewDrive.phillips_mask("#2")).show()

A T30 Torx tip:

.. pythonscad-example::

    from bosl2.screw_drive import ScrewDrive
    ScrewDrive.torx_mask(size=30, length=10).show()

API reference
-------------

.. autoclass:: bosl2.screw_drive.ScrewDrive
   :members:

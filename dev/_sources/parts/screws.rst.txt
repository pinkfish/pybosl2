Screws
======

Pure-Python port of the core of BOSL2's ``screws.scad``, built on top of the
:class:`~pybosl2.parts.threading` thread generator. Three classes turn a
metric screw name into ready-to-print geometry::

    from pybosl2.parts.screws import Screw, Nut, ScrewHole
    Screw("M6", 20, head=ScrewHeadType.SOCKET, drive=ScrewDriveType.HEX).show()
    Nut("M6").show()
    ScrewHole("M6", 20, head=ScrewHeadType.FLAT).show()

A screw is specified by name -- ``"M6"`` (coarse pitch looked up from the ISO table), ``"M8x1"`` (an
explicit fine pitch), a bare number, or a ``{"diameter": ..., "pitch": ...}`` dict. Screws are built
*head-up*: the shaft occupies ``z in [-length, 0]`` (tip at the bottom) and the head sits above
``z = 0``, so a screw drops straight into a mating :class:`~pybosl2.parts.screws.ScrewHole` cut with
its mouth at ``z = 0``.

The dimension tables (ISO coarse/fine pitches, and the socket-cap, hex, button, pan, countersunk,
setscrew and nut head sizes) are transcribed verbatim from ``screws.scad`` and checked in
``tests/test_screws.py``; the assembled geometry is verified watertight with the right head, shaft
and thread in ``tests/test_stl_render.py``.

Coverage of BOSL2 ``screws.scad``
---------------------------------

.. list-table::
   :header-rows: 1
   :widths: 34 16 50

   * - BOSL2 feature
     - Status
     - Notes
   * - ``screw_info``
     - ported
     - replaced by :class:`~pybosl2.parts.screws.ScrewSpec`.
   * - ``screw``
     - ported
     - threaded/plain/partly-threaded shaft, plus socket / hex / button / pan / flat / setscrew heads.
   * - ``nut``
     - ported
     - hex or square nut with a matching threaded hole; ``"normal"`` / ``"thin"`` / ``"thick"`` thickness.
   * - ``screw_hole``
     - ported
     - clearance hole (close/normal/loose fit), flat-head countersink, counterbore, or tapped hole.
   * - hex / slot drive recess
     - ported
     - the two most common recesses; cut into the head (or the shaft top for a setscrew).
   * - phillips / torx drive recesses
     - ported separately
     - available as masks in :doc:`/parts/screw_drive` (:class:`~pybosl2.parts.screw_drive`); not yet
       wired into :class:`~pybosl2.parts.screws.Screw`'s ``drive=`` argument.
   * - UTS / imperial specs, shoulder screws, named anchors, per-tolerance thread classes
     - not ported
     - a follow-up; this port covers the metric fastener geometry the toolkit needs.

Examples
--------

An M8 socket cap screw with a hex drive recess:

.. pythonscad-example::

    from pybosl2.parts.enums import ScrewHeadType, ScrewDriveType
    from pybosl2.parts.screws import Screw
    Screw("M8", 24, head=ScrewHeadType.SOCKET, drive=ScrewDriveType.HEX, fa=6, fs=1).show()

A countersunk (flat-head) screw:

.. pythonscad-example::

    from pybosl2.parts.enums import ScrewHeadType
    from pybosl2.parts.screws import Screw
    Screw("M6", 20, head=ScrewHeadType.FLAT, fa=6, fs=1).show()

A screw threaded into its matching hex nut (shown side by side):

.. pythonscad-example::

    from pybosl2.parts.enums import ScrewHeadType, ScrewDriveType
    from pybosl2.parts.screws import Screw, Nut
    screw = Screw("M6", 18, head=ScrewHeadType.BUTTON, drive=ScrewDriveType.HEX, fa=6, fs=1).shape
    nut = Nut("M6", slop=0.1, fa=6, fs=1).shape.right(18)
    (screw | nut).show()

API reference
-------------

.. autoclass:: pybosl2.parts.screws.Screw
   :members:

.. autoclass:: pybosl2.parts.screws.Nut
   :members:

.. autoclass:: pybosl2.parts.screws.ScrewHole
   :members:

.. autoclass:: pybosl2.parts.screws.ScrewSpec
   :members:
   :undoc-members:

.. autoclass:: pybosl2.parts.screws.ThreadPitches
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``screws.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``screw``

An M6 screw:

.. pythonscad-example::

   from pybosl2.parts.screws import Screw
   Screw("M6", length=12).show()

A socket-head M6:

.. pythonscad-example::

   from pybosl2.parts.enums import ScrewHeadType
   from pybosl2.parts.screws import Screw
   Screw("M6", head=ScrewHeadType.SOCKET, length=12).show()

A Torx button-head M6:

.. pythonscad-example::

   from pybosl2.parts.enums import ScrewHeadType
   from pybosl2.parts.screws import Screw
   Screw("M6", head=ScrewHeadType.BUTTON, drive="torx", length=12).show()

.. rubric:: ``nut``

An M6 nut:

.. pythonscad-example::

   from pybosl2.parts.screws import Nut
   Nut("M6").show()

.. rubric:: ``screw_hole``

A threaded screw-hole mask:

.. pythonscad-example::

   from pybosl2.parts.screws import ScrewHole
   ScrewHole("M6", length=10).show()

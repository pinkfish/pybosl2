Bottle caps: PCO-1810 & PCO-1881 necks and caps
===============================================

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/index.html">Parts catalog &rarr;</a></b>
     &nbsp;&mdash;&nbsp; this module is featured in the visual parts catalog.
   </p>


Pure-Python port of the standard soda-bottle threadings from BOSL2's ``bottlecaps.scad``. The
:class:`~bosl2.bottlecaps.BottleCaps` class builds a threaded **neck** to graft onto a bottle body
and a matching **cap**, for the two common beverage-bottle standards::

    BottleCaps.pco1810_neck()      # PCO-1810 neck
    BottleCaps.pco1810_cap()       # matching PCO-1810 cap
    BottleCaps.pco1881_neck()      # PCO-1881 neck (the modern short-neck standard)
    BottleCaps.pco1881_cap()       # matching PCO-1881 cap

The neck outline (inner bore, support ring, tamper-ring channel and sealing lip) is a
:func:`~bosl2.drawing.turtle` path revolved with ``rotate_extrude``, exactly as BOSL2 builds it; the
thread is :meth:`~bosl2.threading.Threading.thread_helix` with the two thread breaks cut by the same
prismoids. Geometry is anchored with its bottom on the XY plane.

Approximations relative to BOSL2
--------------------------------

This port's threading/``cyl`` lack a few BOSL2 features, so the following are approximated:

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Feature
     - Status
     - Notes
   * - ``pco1810_neck`` / ``pco1881_neck``
     - ported
     - faithful revolved profile; threads without the lead-in ``taper``.
   * - ``pco1810_cap`` / ``pco1881_cap``
     - ported
     - bored cap with internal thread built without the ``internal=`` flank flip.
   * - ``knurled`` / ``ribbed`` cap textures
     - not ported
     - fall back to a plain wall (VNF surface texturing is not in this port).
   * - named anchors (``"support-ring"``, ``"inside-top"``, …)
     - not ported
     - geometry is anchored bottom-on-origin instead.
   * - ``generic_bottle_neck`` / ``generic_bottle_cap``, bottle adapters, SPI (``sp_``) threads
     - not ported
     - a follow-up.

Examples
--------

A PCO-1881 neck and its cap, side by side:

.. pythonscad-example::

    from bosl2.bottlecaps import BottleCaps
    (BottleCaps.pco1881_neck() | BottleCaps.pco1881_cap().right(45)).show()

API reference
-------------

.. autoclass:: bosl2.bottlecaps.BottleCaps
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``bottlecaps.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``pco1810_neck``

A PCO-1810 bottle neck:

.. pythonscad-example::

   BottleCaps.pco1810_neck().show()

.. rubric:: ``pco1810_cap``

Its matching cap:

.. pythonscad-example::

   BottleCaps.pco1810_cap().show()

.. rubric:: ``pco1881_neck``

A PCO-1881 bottle neck:

.. pythonscad-example::

   BottleCaps.pco1881_neck().show()

.. rubric:: ``pco1881_cap``

Its matching cap:

.. pythonscad-example::

   BottleCaps.pco1881_cap().show()

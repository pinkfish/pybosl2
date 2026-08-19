Threading
=========

.. raw:: html

   <p style="margin-top:0;margin-bottom:1.2em">&#9881;&#65039; <b><a href="specs/threading.html">Spec sheet &rarr;</a></b> &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.</p>


.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/index.html">Parts catalog &rarr;</a></b>
     &nbsp;&mdash;&nbsp; this module is featured in the visual parts catalog.
   </p>


Pure-Python port of the core of BOSL2's ``threading.scad``. The
:class:`~pybosl2.parts.threading.ThreadedRod` and
:class:`~pybosl2.parts.threading.ThreadedNut` classes build screw threads by generating the
whole rod (core + helical thread) as one manifold polyhedron -- an angular sweep of the thread
profile stacked over every turn -- so the result is always watertight. (Sweeping the thread and
CSG-unioning a coaxial core instead is what Manifold cannot triangulate cleanly, so this port
builds the polyhedron directly, as BOSL2 does.)

Convenience functions return pre-configured rods and nuts::

    iso_threaded_rod(12, 24, 1.75)                       # ISO M12 x 1.75
    acme_threaded_rod(20, 30, 4)                         # 29-degree ACME
    iso_threaded_nut(18, 12, 10, 1.75, slop=0.1)        # matching hex nut

A *rod* is a threaded cylinder; a *nut* is a hex/square block with a matching threaded hole (cut by
a thread "tap", with *slop* radial clearance). *pitch* is the axial distance between threads,
*starts* the number of thread starts, and *left_handed* flips the helix. The thread *profiles* are
ported verbatim from BOSL2 (checked in ``tests/test_threading.py``), and the geometry is verified
watertight with the correct major/minor diameter and length.

Coverage of BOSL2 ``threading.scad``
------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 40 16 44

   * - BOSL2 function
     - Status
     - Notes
   * - ``generic_threaded_rod`` / ``generic_threaded_nut``
     - ported
     - the profile-driven core every other builder uses.
   * - ``threaded_rod`` / ``threaded_nut``
     - ported
     - ISO (metric) / UTS 60-degree triangular threads.
   * - ``trapezoidal_threaded_rod`` / ``trapezoidal_threaded_nut``
     - ported
     - symmetric trapezoidal (metric trapezoidal by default; ``thread_angle`` / ``thread_depth``).
   * - ``acme_threaded_rod`` / ``acme_threaded_nut``
     - ported
     - 29-degree ACME threads.
   * - ``square_threaded_rod`` / ``square_threaded_nut``
     - ported
     - square-profile threads.
   * - ``buttress_threaded_rod`` / ``buttress_threaded_nut``
     - ported
     - asymmetric buttress threads.
   * - ``thread_helix``
     - ported
     - a single helical thread ridge, to add onto your own cylinder.
   * - blunt-start / lead-in tapers, ``teardrop``, bevels
     - not ported
     - the BOSL2 end-refinements; this port cuts the ends flush. A follow-up.
   * - ``ball_screw_rod`` / ``npt_threaded_rod`` / ``bspp_threaded_rod``
     - not ported
     - specialised thread forms; a follow-up.

Examples
--------

An ISO M16 x 2 rod:

.. pythonscad-example::

    from pybosl2.parts.threading import iso_threaded_rod
    iso_threaded_rod(16, 30, 2, fa=4, fs=1).show()

An ACME lead screw:

.. pythonscad-example::

    from pybosl2.parts.threading import acme_threaded_rod
    acme_threaded_rod(24, 36, 5, fa=4, fs=1).show()

A rod threaded into its matching hex nut (shown side by side):

.. pythonscad-example::

    from pybosl2.parts.threading import iso_threaded_rod, iso_threaded_nut
    rod = iso_threaded_rod(12, 30, 1.75, fa=6, fs=1).shape()
    nut = iso_threaded_nut(18, 12, 10, 1.75, slop=0.1, fa=6, fs=1).shape().right(22)
    (rod | nut).show()

API reference
-------------
.. autoclass:: pybosl2.parts.threading.ThreadedRod
   :members:

.. autoclass:: pybosl2.parts.threading.ThreadedNut
   :members:

.. autoclass:: pybosl2.parts.threading.ThreadHelix
   :members:

.. GENERATED-EXAMPLES (regenerate via scratchpad/gen_examples.py -- do not edit below)

Examples
--------

These mirror the examples in BOSL2's ``threading.scad``, rendered live through PythonSCAD.
Examples that rely on BOSL2's attachment/anchor system, or on features not in this port, are omitted.

.. rubric:: ``threaded_rod``

An ISO/UTS threaded rod:

.. pythonscad-example::

   from pybosl2.parts.threading import iso_threaded_rod
   iso_threaded_rod(d=25, l=20, pitch=2).show()

Left-handed:

.. pythonscad-example::

   from pybosl2.parts.threading import iso_threaded_rod
   iso_threaded_rod(d=10, l=20, pitch=1.25, left_handed=True).show()

.. rubric:: ``threaded_nut``

A hex nut:

.. pythonscad-example::

   from pybosl2.parts.threading import iso_threaded_nut
   iso_threaded_nut(nutwidth=16, id=8, h=8, pitch=1.25).show()

.. rubric:: ``trapezoidal_threaded_rod``

A trapezoidal-thread rod:

.. pythonscad-example::

   from pybosl2.parts.threading import trapezoidal_threaded_rod
   trapezoidal_threaded_rod(d=10, l=40, pitch=2).show()

.. rubric:: ``trapezoidal_threaded_nut``

Its nut:

.. pythonscad-example::

   from pybosl2.parts.threading import trapezoidal_threaded_nut
   trapezoidal_threaded_nut(nutwidth=16, id=8, h=8, pitch=2).show()

.. rubric:: ``acme_threaded_rod``

An Acme lead screw:

.. pythonscad-example::

   from pybosl2.parts.threading import acme_threaded_rod
   acme_threaded_rod(d=10, l=30, pitch=2, starts=3).show()

.. rubric:: ``acme_threaded_nut``

An Acme nut:

.. pythonscad-example::

   from pybosl2.parts.threading import acme_threaded_nut
   acme_threaded_nut(nutwidth=16, id=10, h=10, pitch=2).show()

.. rubric:: ``buttress_threaded_rod``

A buttress-thread rod:

.. pythonscad-example::

   from pybosl2.parts.threading import buttress_threaded_rod
   buttress_threaded_rod(d=10, l=20, pitch=1.25).show()

.. rubric:: ``buttress_threaded_nut``

Its nut:

.. pythonscad-example::

   from pybosl2.parts.threading import buttress_threaded_nut
   buttress_threaded_nut(nutwidth=16, id=8, h=8, pitch=1.25).show()

.. rubric:: ``square_threaded_rod``

A square-thread rod:

.. pythonscad-example::

   from pybosl2.parts.threading import square_threaded_rod
   square_threaded_rod(d=10, l=20, pitch=2, starts=2).show()

.. rubric:: ``square_threaded_nut``

Its nut:

.. pythonscad-example::

   from pybosl2.parts.threading import square_threaded_nut
   square_threaded_nut(nutwidth=16, id=10, h=10, pitch=2, starts=2).show()

.. rubric:: ``thread_helix``

A single thread ridge, swept as a helix:

.. pythonscad-example::

   from pybosl2.parts.threading import ThreadHelix
   ThreadHelix(d=10, pitch=2, thread_depth=0.75, flank_angle=15, turns=2.5).show()

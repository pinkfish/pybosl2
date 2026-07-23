Joiners
=======

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/joiners.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


Pure-Python port of the core joiners from BOSL2's ``joiners.scad`` — shapes for connecting two
separately-printed parts. :meth:`~bosl2.joiners.Joiners.dovetail` is the flagship: a (optionally
tapered) dovetail joint you attach as a male tenon or difference out as a female socket. A functional
:meth:`~bosl2.joiners.Joiners.snap_pin` and its :meth:`~bosl2.joiners.Joiners.snap_pin_socket` give a
press-and-click pin.

.. autoclass:: bosl2.joiners.Joiners
   :members:

Wiring
======

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/wiring.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


Rendering for routed wire bundles, from BOSL2's ``wiring.scad``.
:meth:`~bosl2.wiring.Wiring.wire_bundle` hex-packs a set of round wires into a bundle and sweeps them
along a path whose corners are rounded to a given radius, colouring each wire from a 17-entry table
(re-used if there are more than 17 wires). Each wire is an independently watertight swept tube;
:meth:`~bosl2.wiring.Wiring.hex_offsets` exposes the optimal hexagonal packing centres it uses.
.. autoclass:: bosl2.wiring.Wiring
   :members:

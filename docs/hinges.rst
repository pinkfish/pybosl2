Hinges
======

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/hinges.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


Pure-Python port of the hinges in BOSL2's ``hinges.scad``: a print-in-place
:meth:`~bosl2.hinges.Hinges.living_hinge_mask` (differenced from a plate to make a folding "live"
hinge), a functional interlocking :meth:`~bosl2.hinges.Hinges.knuckle_hinge` leaf (with
:meth:`~bosl2.hinges.Hinges.knuckle_hinge_pair` for both leaves meshed around one pin, at any fold
angle), and simple :meth:`~bosl2.hinges.Hinges.snap_lock` / :meth:`~bosl2.hinges.Hinges.snap_socket`
connectors.

.. autoclass:: bosl2.hinges.Hinges
   :members:

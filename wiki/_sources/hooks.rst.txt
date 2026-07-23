Hooks
=====

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/hooks.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


Hooks and hook-like parts, from BOSL2's ``hooks.scad``. BOSL2 currently supplies a single part,
:meth:`~bosl2.hooks.Hooks.ring_hook`: a rectangular mounting base that flares up and joins
tangentially to a Y-axis cylinder — the "ring" — with an optional round, D-shaped or custom
through-hole. Give exactly two of ``or_/od``, ``ir/id`` and ``wall`` to size the ring wall (or a zero
inner radius for a solid paddle). The base's vertical edges and the hole mouth can be rounded; the
original's base weld ``fillet`` is a follow-up.

.. autoclass:: bosl2.hooks.Hooks
   :members:

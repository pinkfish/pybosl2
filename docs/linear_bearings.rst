Linear bearings
===============

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/linear_bearings.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; visual schematic and metrics measured from a real rendered STL.
   </p>


Pure-Python port of BOSL2's ``linear_bearings.scad``: models of LMxUU linear ball bearings that run
along a rod, and the pillow-block housings that clamp them to a plate.
:meth:`~bosl2.linear_bearings.LinearBearings.lmXuu_bearing` looks a standard size up in
:meth:`~bosl2.linear_bearings.LinearBearings.lmXuu_info` (a
:class:`~bosl2.linear_bearings.LinearBearingSpec` table);
:meth:`~bosl2.linear_bearings.LinearBearings.linear_bearing` is the generic form.

.. autoclass:: bosl2.linear_bearings.LinearBearingSpec
   :members:

.. autoclass:: bosl2.linear_bearings.LinearBearings
   :members:

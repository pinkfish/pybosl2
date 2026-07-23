Linear bearings
===============

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

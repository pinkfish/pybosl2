Wiring
======

Rendering for routed wire bundles, from BOSL2's ``wiring.scad``.
:meth:`~bosl2.wiring.Wiring.wire_bundle` hex-packs a set of round wires into a bundle and sweeps them
along a path whose corners are rounded to a given radius, colouring each wire from a 17-entry table
(re-used if there are more than 17 wires). Each wire is an independently watertight swept tube;
:meth:`~bosl2.wiring.Wiring.hex_offsets` exposes the optimal hexagonal packing centres it uses.

.. autoclass:: bosl2.wiring.Wiring
   :members:

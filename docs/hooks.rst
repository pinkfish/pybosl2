Hooks
=====

Hooks and hook-like parts, from BOSL2's ``hooks.scad``. BOSL2 currently supplies a single part,
:meth:`~bosl2.hooks.Hooks.ring_hook`: a rectangular mounting base that flares up and joins
tangentially to a Y-axis cylinder — the "ring" — with an optional round, D-shaped or custom
through-hole. Give exactly two of ``or_/od``, ``ir/id`` and ``wall`` to size the ring wall (or a zero
inner radius for a solid paddle). The base's vertical edges and the hole mouth can be rounded; the
original's base weld ``fillet`` is a follow-up.

.. autoclass:: bosl2.hooks.Hooks
   :members:

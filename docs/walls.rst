Walls
=====

FDM-optimised wall shapes from BOSL2's ``walls.scad`` — parts that use less material and print
without support. :meth:`~bosl2.walls.Walls.sparse_wall` is an X-cross-braced open wall (and
:meth:`~bosl2.walls.Walls.sparse_cuboid` a solid-box variant braced along one axis);
:meth:`~bosl2.walls.Walls.corrugated_wall` a sinusoidal corrugated panel;
:meth:`~bosl2.walls.Walls.thinning_wall` and :meth:`~bosl2.walls.Walls.thinning_triangle` walls whose
middle thins away while the edges stay thick, joined by angled shoulders that don't overhang;
:meth:`~bosl2.walls.Walls.narrowing_strut` the home-plate strut those triangles are built from. The
honeycomb ``hex_panel`` is a follow-up.

.. autoclass:: bosl2.walls.Walls
   :members:

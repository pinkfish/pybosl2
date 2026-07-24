Textures
========

Port of BOSL2's ``texture()`` engine (from ``skin.scad``): the named-texture table that
:func:`~bosl2.shapes3d.textured_tile` builds from. :func:`~bosl2.texture.texture` resolves a texture
**name** to its data — either a **height-field** (a 2-D array of heights in ``[0, 1]``) or a **VNF
tile** ``(verts, faces)`` describing one unit cell of the surface.

All of BOSL2's textures are ported (9 height-field + 12 VNF). Height-field textures: ``ribs``,
``trunc_ribs``, ``wave_ribs``, ``diamonds``, ``pyramids``, ``trunc_pyramids``, ``hills``, ``bricks``,
``rough``. VNF-tile textures: ``diamonds_vnf``, ``pyramids_vnf``, ``trunc_pyramids_vnf``, ``cubes``,
``trunc_ribs_vnf``, ``bricks_vnf``, ``checkers``, ``trunc_diamonds``, ``tri_grid``, and the
``$fn``-parametric ``cones``, ``dots`` and ``hex_grid`` (pass *fn* for their resolution). A few VNF
tiles that can't be tiled watertight directly (``bricks_vnf``, ``checkers``, ``trunc_diamonds``) fall
back to a sampled height-field, which slightly flattens their vertical faces.
.. autofunction:: bosl2.texture.texture

.. autofunction:: bosl2.texture.vnf_tile_to_solid

3-D shapes and Bosl2Solid
=========================

.. raw:: html

   <p class="specref" id="spec-sheet-callout" style="margin:0 0 1.5em;padding:11px 16px;border:1px solid #38bdf0;border-radius:8px;background:rgba(56,189,240,0.07);font-size:0.98em;">
     &#9881;&#65039; <b><a href="specs/shapes3d.html">Spec sheet &rarr;</a></b>
     &nbsp;&mdash;&nbsp; interactive 3-D viewer, metrics, and variants catalog.
   </p>

Pure-Python port of the 3-D shape generators from BOSL2's ``shapes3d.scad``. Each returns a
:class:`~pybosl2.Bosl2Solid` wrapping native geometry, with BOSL2-style anchor/spin/orient
support and bbox-backed attachment methods.

**Live preview — try it:**

.. pythonscad-example::

   s3.cuboid([40, 30, 20], rounding=4).show()

.. pythonscad-example::

   s3.sphere(r=15).show()

.. pythonscad-example::

   s3.cylinder(h=30, r=10).show()

Coverage of BOSL2 ``shapes3d.scad``
-----------------------------------

.. list-table::
   :header-rows: 1
   :widths: 40 15 45

   * - BOSL2 shape
     - Status
     - Notes
   * - ``cube`` / ``cuboid``
     - ported
     - with chamfer / rounding / edge selection
   * - ``prismoid``
     - ported
     -
   * - ``regular_prism``
     - ported
     -
   * - ``octahedron`` / ``wedge``
     - ported
     -
   * - ``cylinder`` / ``cyl`` / ``xcyl`` / ``ycyl`` / ``zcyl``
     - ported
     -
   * - ``tube`` / ``rect_tube`` / ``pie_slice``
     - ported
     -
   * - ``sphere`` / ``spheroid``
     - ported
     -
   * - ``torus`` / ``teardrop`` / ``onion``
     - ported
     -
   * - ``text3d`` / ``path_text``
     - ported
     -
   * - ``interior_fillet``
     - ported
     -
   * - ``heightfield`` / ``cylindrical_heightfield``
     - ported
     -
   * - ``ruler``
     - ported
     -
   * - ``plot3d``
     - ported
     - :func:`~pybosl2.surfaces3d` — a ``z = f(x, y)`` surface plot, with an optional solid base
   * - ``fillet``
     - ported
     - :func:`~pybosl2.surfaces3d` — the concave edge-fillet mask (90-degree edges only; other
       dihedral ``ang`` not ported)
   * - ``plot_revolution``
     - ported
     - :func:`~pybosl2.surfaces3d` — a surface of revolution modulated by
       ``radius=f(angle, z)`` (the ``arclength`` form is not ported)
   * - ``textured_tile``
     - ported (height-field form)
     - :func:`~pybosl2.surfaces3d` — a tiled scalar height-field texture; VNF-tile and
       named-texture forms need the BOSL2 texture engine (not ported)

Bosl2Solid & attachment
-----------------------

Every 3-D shape is a :class:`~pybosl2.Bosl2Solid`, which carries the transform methods
(``translate``/``move``, ``rotate``/``rot``, ``right``/``left``/``back``/``forward``/``up``/``down``,
``mirror``, ``scale``, ``color``) and the BOSL2 attachment methods —
``bounds``, ``anchor_point``, ``reanchor``, ``reorient``, ``orient``, ``position``, ``attach``,
``align``, plus the edge/corner/face masking (``edge_mask``, ``edge_profile``, ``corner_profile``,
``face_profile``). All of these read the object's **native bounding box**, so a size never needs to
be threaded through the calls — e.g. ``cuboid([40,30,20]).attach(TOP, sphere(radius=6))`` or
``cyl(height=20, radius=5).orient(RIGHT)`` just work on the built object.

The BOSL2 attachment *framework* internals (``attachable``, ``attach_geom``, named anchors, the
``tag``/``diff``/``intersect`` tagged-CSG operations, and the ``show_anchors``/description helpers)
are not ported — the methods above cover positioning/masking directly on the object.

API reference
-------------
.. automodule:: pybosl2.shapes3d
   :members:
   :undoc-members:
   :show-inheritance:

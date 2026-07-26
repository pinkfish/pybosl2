2-D shapes
==========

Pure-Python port of the 2-D shape generators from BOSL2's ``shapes2d.scad`` (plus ``arc()``).
Each returns a :class:`~bosl2.shapes2d.Bosl2Shape2D` -- the 2-D counterpart of
:class:`~bosl2.shapes3d.Bosl2Solid` -- so the geometry chains straight on::

    square(20).offset(radius=2).fill().linear_extrude(height=4).show()

The 2-D object
--------------

:class:`~bosl2.shapes2d.Bosl2Shape2D` wraps a native 2-D handle (reachable as ``.shape``) and
carries, as chained methods:

* the 2-D operators -- :meth:`~bosl2.shapes2d.Bosl2Shape2D.fill` (drop every hole),
  :meth:`~bosl2.shapes2d.Bosl2Shape2D.hull` (convex hull, optionally with more shapes/paths) and
  :meth:`~bosl2.shapes2d.Bosl2Shape2D.offset` (BOSL2's ``radius=``/``delta=`` spelling);
* the 2-D → 3-D extruders -- :meth:`~bosl2.shapes2d.Bosl2Shape2D.linear_extrude`,
  :meth:`~bosl2.shapes2d.Bosl2Shape2D.rotate_extrude` and
  :meth:`~bosl2.shapes2d.Bosl2Shape2D.path_extrude`, each returning a
  :class:`~bosl2.shapes3d.Bosl2Solid`;
* the transforms, the CSG operators (``|``, ``&``, ``-``), the ``color.scad`` operators and the
  ``distributors.scad`` copiers, all returning a new ``Bosl2Shape2D``.

:func:`~bosl2.shapes2d.fill` and :func:`~bosl2.shapes2d.hull` are also available as free
functions (the OpenSCAD module form), and accept a ``Bosl2Shape2D``, a raw native shape, a
:class:`~bosl2.paths.Path` / :class:`~bosl2.regions.Region`, or a plain point list.

The same operators live on :class:`~bosl2.paths.Path` and :class:`~bosl2.regions.Region`
(``path.fill()``, ``path.hull()``, ``path.linear_extrude(height=...)``), and
:meth:`Bosl2Solid.projection() <bosl2.shapes3d.Bosl2Solid.projection>` comes back the other way,
from a 3-D solid to a ``Bosl2Shape2D`` footprint.

Coverage of BOSL2 ``shapes2d.scad``
-----------------------------------

.. list-table::
   :header-rows: 1
   :widths: 40 15 45

   * - BOSL2 shape
     - Status
     - Notes
   * - ``square`` / ``rect``
     - ported
     - plus ``rect_path`` for the point-list form
   * - ``circle`` / ``ellipse``
     - ported
     -
   * - ``regular_ngon`` / ``pentagon`` / ``hexagon`` / ``octagon``
     - ported
     -
   * - ``right_triangle`` / ``trapezoid``
     - ported
     -
   * - ``star``, ``teardrop2d``, ``egg``, ``glued_circles``, ``supershape``, ``reuleaux_polygon``
     - ported
     -
   * - ``squircle``
     - ported
     - :func:`~bosl2.shapes2d.squircle` — the default ``"fg"`` (Fong-Garcia) style; the
       ``"superellipse"`` / ``"bezier"`` styles are not ported
   * - ``jittered_poly``, ``round2d``, ``shell2d``
     - ported
     - ``round2d`` / ``shell2d`` are rounding / shelling operators
   * - ``arc``
     - ported
     - lives here but is documented on the :doc:`drawing` page (returns a
       :class:`~bosl2.paths.Path`)
   * - ``text``
     - ported
     - :func:`~bosl2.shapes2d.text`
   * - ``keyhole``
     - ported
     - :func:`~bosl2.shapes2d.keyhole`
   * - ``ring``
     - ported
     - :func:`~bosl2.shapes2d.ring` — the full-annulus form (``radius1``/``radius2`` or ``radius`` + ``ring_width``);
       the arc / 3-point / corner / width+thickness forms are not ported

API reference
-------------
.. automodule:: bosl2.shapes2d
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: arc

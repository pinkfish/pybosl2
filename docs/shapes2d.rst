2-D shapes
==========

Pure-Python port of the 2-D shape generators from BOSL2's ``shapes2d.scad`` (plus ``arc()``).
Each returns a :class:`~pybosl2.Bosl2Solid2D` -- the 2-D counterpart of
:class:`~pybosl2.Bosl2Solid` -- so the geometry chains straight on::

    square(20).offset(radius=2).fill().linear_extrude(height=4).show()

The 2-D object
--------------

:class:`~pybosl2.Bosl2Solid2D` wraps a native 2-D handle (reachable as ``.shape``) and
carries, as chained methods:

* the 2-D operators -- :meth:`~pybosl2.shapes2d` (drop every hole),
  :meth:`~pybosl2` (convex hull, optionally with more shapes/paths) and
  :meth:`~pybosl2.Bosl2Shape2D.offset` (BOSL2's ``radius=``/``delta=`` spelling);
* the 2-D → 3-D extruders -- :meth:`~pybosl2.shapes2d.Bosl2Shape2D.linear_extrude`,
  :meth:`~pybosl2.Bosl2Shape2D.rotate_extrude` and
  :meth:`~pybosl2.Bosl2Shape2D.path_extrude`, each returning a
  :class:`~pybosl2.Bosl2Solid`;
* the transforms, the CSG operators (``|``, ``&``, ``-``), the ``color.scad`` operators and the
  ``distributors.scad`` copiers, all returning a new ``Bosl2Shape2D``.

:mod:`~pybosl2.shapes2d` and :mod:`~pybosl2.shapes2d` are also available as free
functions (the OpenSCAD module form), and accept a ``Bosl2Shape2D``, a raw native shape, a
:class:`~pybosl2.paths` / :mod:`~pybosl2.regions`, or a plain point list.

The same operators live on :class:`~mod.paths` and :class:`~mod.regions`
(``path.fill()``, ``path.hull()``, ``path.linear_extrude(height=...)``), and
:meth:`Bosl2Solid.projection() <pybosl2.Bosl2Solid.projection>` comes back the other way,
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
     - :mod:`~pybosl2.shapes2d` — the default ``"fg"`` (Fong-Garcia) style; the
       ``"superellipse"`` / ``"bezier"`` styles are not ported
   * - ``jittered_poly``, ``round2d``, ``shell2d``
     - ported
     - ``round2d`` / ``shell2d`` are rounding / shelling operators
   * - ``arc``
     - ported
     - lives here but is documented on the :doc:`drawing` page (returns a
       :mod:`~pybosl2.paths`)
   * - ``text``
     - ported
     - :mod:`~pybosl2.shapes2d`
   * - ``keyhole``
     - ported
     - :mod:`~pybosl2.shapes2d`
   * - ``ring``
     - ported
     - :mod:`~pybosl2.shapes2d` — the full-annulus form (``radius1``/``radius2`` or ``radius`` + ``ring_width``);
       the arc / 3-point / corner / width+thickness forms are not ported

API reference
-------------
.. automodule:: pybosl2.shapes2d
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: arc

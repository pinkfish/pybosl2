NURBS
=====

Pure-Python port of the NURBS **evaluation** API from BOSL2's ``nurbs.scad``, as two classes:
:class:`~pybosl2.nurbs.NurbsCurve` (evaluate a curve, sample it into a path, raise its degree) and
:class:`~pybosl2.nurbs.NurbsPatch` (sample a surface, mesh it into a VNF). All three flavours --
``CLAMPED``, ``OPEN`` and ``CLOSED`` -- are supported, with weights (rational NURBS), knot
multiplicities, and explicit knot vectors.

Each object owns its whole definition, so operations chain off it instead of threading six
arguments through free functions::

    NurbsCurve(ctrl, 3).curve(splinesteps=12).stroke(width=3)
    NurbsCurve(ctrl, 3).elevate_degree().point(0.5)
    NurbsPatch(patch, (3, 3)).vnf(splinesteps=(8, 8)).polyhedron()

``NurbsCurve.curve()`` returns a :class:`~pybosl2.path2d.Path2D` (2-D control points) or a
:class:`~pybosl2.path3d.Path3D` (3-D), so the result carries the full path/extrude/stroke API, and
``NurbsPatch.vnf()`` returns a :class:`~pybosl2.vnf.VNF`. The classic rational-NURBS sphere is
rendered and checked for real in ``tests/test_stl_render.py``.

Every per-direction setting on a patch is a ``(u, v)`` pair: ``degree=(3, 3)``,
``splinesteps=(16, 16)``, ``knots=(u_knots, v_knots)``, and so on. The curve/patch definition is
read-only once constructed -- build a new object to change it.

Coverage of BOSL2 ``nurbs.scad``
--------------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - BOSL2 function
     - Status
     - Notes
   * - ``nurbs_curve``
     - ported
     - :class:`~pybosl2.nurbs.NurbsCurve` -- clamped/open/closed, weights, mult, explicit knots.
       ``curve(splinesteps)`` samples the whole curve into a path; ``point(u)`` / ``points(u)``
       evaluate chosen parameters.
   * - ``nurbs_patch_points``
     - ported
     - :class:`~pybosl2.nurbs.NurbsPatch` -- ``surface(splinesteps)`` samples a uniform grid,
       ``points(u, v)`` a chosen one, ``point(u, v)`` a single point; per-direction
       degree/type/mult/knots.
   * - ``nurbs_vnf``
     - ported
     - ``NurbsPatch.vnf()`` -- mesh a patch (built on ``vnf_vertex_array``), with
       ``style`` / ``reverse`` / ``caps``.
   * - ``nurbs_elevate_degree``
     - ported
     - ``NurbsCurve.elevate_degree()`` -- raise a clamped/open curve's degree (collocation
       at Greville points); returns a new :class:`~pybosl2.nurbs.NurbsCurve`.
   * - ``is_nurbs_patch``
     - ported
     - ``NurbsPatch.is_patch()``.
   * - ``nurbs_interp`` / ``nurbs_interp_surface``
     - not ported
     - the constrained least-squares *interpolation* solvers (fit a NURBS through given points with
       derivative/curvature/corner constraints) -- thousands of lines of custom linear algebra; a
       large follow-up.
   * - ``debug_nurbs`` / ``debug_nurbs_interp``
     - not ported
     - preview/annotation display modules.

Examples
--------

A cubic clamped NURBS curve, swept into a tube:

.. pythonscad-example::

    from pybosl2 import NurbsCurve

    ctrl = [[0, 0, 0], [10, 20, 5], [30, -10, 10], [50, 20, 0], [60, 0, 15]]
    NurbsCurve(ctrl, 3).curve(splinesteps=12).stroke(width=3).show()

A cubic B-spline surface patch meshed into a sheet:

.. pythonscad-example::

    from pybosl2 import NurbsPatch

    patch = [
        [[-50, 50, 0], [-16, 50, 20], [16, 50, 20], [50, 50, 0]],
        [[-50, 16, 20], [-16, 16, 40], [16, 16, 40], [50, 16, 20]],
        [[-50, -16, 20], [-16, -16, 40], [16, -16, 40], [50, -16, 20]],
        [[-50, -50, 0], [-16, -50, 20], [16, -50, 20], [50, -50, 0]],
    ]
    NurbsPatch(patch, (3, 3)).vnf(splinesteps=(10, 10)).polyhedron().show()

A sphere as a rational NURBS surface (weights + repeated knots):

.. pythonscad-example::

    from pybosl2 import NurbsPatch

    patch = [[[0, 0, 1]] * 7,
             [[2, 0, 1], [2, 4, 1], [-2, 4, 1], [-2, 0, 1], [-2, -4, 1], [2, -4, 1], [2, 0, 1]],
             [[2, 0, -1], [2, 4, -1], [-2, 4, -1], [-2, 0, -1], [-2, -4, -1], [2, -4, -1], [2, 0, -1]],
             [[0, 0, -1]] * 7]
    weights = [[w / 9 for w in row] for row in
               [[9, 3, 3, 9, 3, 3, 9], [3, 1, 1, 3, 1, 1, 3], [3, 1, 1, 3, 1, 1, 3], [9, 3, 3, 9, 3, 3, 9]]]
    NurbsPatch(patch, (3, 3), weights=weights,
               knots=(None, [0, 0.5, 0.5, 0.5, 1])).vnf(splinesteps=(12, 12)).polyhedron().show()

API reference
-------------
.. automodule:: pybosl2.nurbs
   :members:
   :undoc-members:

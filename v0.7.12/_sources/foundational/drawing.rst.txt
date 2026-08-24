Drawing
=======

The drawing functions are distributed across the modules where they naturally live.
*Path generators* return points; *path renderers* turn points into geometry.

Arc & catenary
----------------

.. autofunction:: pybosl2.shapes2d.arc

.. automethod:: pybosl2.path2d.Path2D.catenary

Helix
-----

:meth:`pybosl2.path3d.Path3D.helix` — see the :doc:`/paths/paths` reference for full documentation.

2-D Turtle
----------

Drive the turtle with methods -- one per command, each returning the turtle so calls chain --
and take the path when you are done:

.. pythonscad-example::

    from pybosl2.turtle import Turtle2D

    path = Turtle2D().set_length(40).set_arc_steps(24)
    for _ in range(4):
        path.move().arc_left(radius=8)
    path.points().stroke(width=3, closed=True).linear_extrude(height=4).show()

The command objects still work, and are what the methods build underneath; hand a list of them to
:func:`~pybosl2.turtle.turtle2d` when you are generating a program rather than writing one.

.. autoclass:: pybosl2.turtle.TurtleCommands
   :members:

.. autofunction:: pybosl2.turtle.turtle2d

3-D Turtle
----------

The 3-D turtle takes the same commands and the same methods; it is documented in
:doc:`/paths/turtle3d`.

Stroke & dashed stroke
-----------------------

Both 2-D and 3-D paths carry ``stroke`` and ``dashed_stroke`` as methods:

* :meth:`pybosl2.path2d.Path2D.stroke` / :meth:`pybosl2.path2d.Path2D.dashed_stroke`
* :meth:`pybosl2.path3d.Path3D.stroke` / :meth:`pybosl2.path3d.Path3D.dashed_stroke`

Coverage of BOSL2 ``drawing.scad``
----------------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - BOSL2 function
     - Status
     - Notes
   * - ``arc``
     - ported
     - :func:`~pybosl2.shapes2d.arc` returns a :class:`~pybosl2.path2d.Path2D`; all 2-D forms
       (radius/angle, ``angle=[start, end]``, ``width``/``thickness``, two-point with
       ``long``/``cw``/``ccw``, three-point, ``corner=``, and ``wedge=``). 3-D arcs are not ported.
   * - ``catenary``
     - ported
     - :meth:`~pybosl2.path2d.Path2D.catenary` — by ``droop=`` or endpoint ``angle=``.
   * - ``helix``
     - ported
     - :meth:`~pybosl2.path3d.Path3D.helix` — returns a :class:`~pybosl2.path3d.Path3D` (conical/flat spirals
       included).
   * - ``turtle``
     - ported
     - :class:`~pybosl2.turtle.Turtle2D` (methods) or :func:`~pybosl2.turtle.turtle2d` (command
       objects) — the full command set, including ``repeat`` and the
       ``arcleft``/``arcright``/``arcleftto``/``arcrightto`` arcs.
   * - ``stroke``
     - ported
     - :meth:`~pybosl2.path2d.Path2D.stroke` / :meth:`~pybosl2.path3d.Path3D.stroke` — 2-D
       (segment rects + joints & endcaps) and 3-D (cylinder tube + spherical joints + revolved
       endcaps). **Every** BOSL2 endcap/joint style is generated directly: ``round``, ``square``,
       ``butt``, ``dot``, ``block``, ``diamond``, ``chisel``, ``line``, ``x``, ``cross``,
       ``arrow``, ``arrow2``, ``arrow3``, ``tail``, ``tail2`` (arrow caps trim the line back).
       Per-vertex ``width`` lists and the ``*_angle``/``*_color`` knobs are not ported.
   * - ``dashed_stroke``
     - ported
     - :meth:`~pybosl2.path2d.Path2D.dashed_stroke` / :meth:`~pybosl2.path3d.Path3D.dashed_stroke`
       — the method forms that build unioned dash solids directly.
   * - ``turtle3d``
     - ported
     - :doc:`/paths/turtle3d` — the 3-D turtle as a :class:`~pybosl2.turtle.turtle3d.Turtle3D` class with
       the full simple and compound command sets.
   * - ``debug_polygon`` / ``debug_region``
     - not ported
     - annotated debugging modules (vertex/edge labels); no geometry payload.

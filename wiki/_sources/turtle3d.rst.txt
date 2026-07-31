Turtle (3-D)
============

Pure-Python port of BOSL2's ``turtle3d.scad`` as a :class:`~pybosl2.turtle.turtle3d.Turtle3D` class. A turtle
walks through 3-D space carrying an orientation frame; a flat list of commands drives it, and the
result is either the list of points it visited (:meth:`~pybosl2.turtle.turtle3d.Turtle3D.points`) or a list of
4x4 transforms (:meth:`~pybosl2.turtle.turtle3d.Turtle3D.transforms`) ready to sweep a profile with
:func:`~pybosl2.skin.path_sweep` / :func:`~pybosl2.skin.sweep`.

The full simple command set is ported — moves (``move``/``jump``/``xmove`` …), relative turns
(``left``/``right``/``up``/``down``/``roll``), absolute turns (``xrot``/``yrot``/``zrot``/``rot``/
``setdir``), arcs (``arcleft``/``arcright``/``arcup``/``arcdown``/``arcxrot`` …/``arctodir``/
``arcrot``), the ``length``/``angle``/``scale``/``arcsteps`` settings, and ``repeat``. *Compound*
commands are also supported — a single nested list starting with ``"move"`` or ``"arc"`` that applies
several effects at once (``["move", 40, "grow", 2, "twist", 180, "steps", 40]``), with
``grow``/``shrink`` scaling the swept profile, ``twist`` rotating it, ``roll``/``rollto`` rolling the
frame, and, for ``arc``, relative or absolute rotation.

.. autoclass:: pybosl2.turtle.turtle3d.Turtle3D
   :members:
   :undoc-members:

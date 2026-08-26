Getting started
===============

This page builds one real part from nothing — a rounded bracket with a bore, a boss and a
chamfer — and saves it to a file you can slice. Every step is a working example; copy them in
order and you will have an STL at the end.

If you have not installed pybosl2 yet:

.. code-block:: bash

   pip install pybosl2          # the library
   pip install pythonscad       # the geometry kernel it drives

Everything on this page except the final render works in plain CPython.

1. A solid
----------

Shapes are functions; they return an object you keep working on. Only the size is required —
everything else has a sensible default, so the shortest useful call is one argument.

.. pythonscad-example::

   from pybosl2 import cuboid

   body = cuboid([60, 40, 12])
   body.show()

``.show()`` hands the shape to the renderer and gives it back, so it closes a chain without
swallowing the value.

2. Round its edges
------------------

Shaping options are keyword arguments on the constructor, and ``edges=`` says which edges to treat
using the anchor language — the same vocabulary used everywhere a face, edge or corner is named.

.. pythonscad-example::

   from pybosl2 import Anchor, cuboid

   body = cuboid([60, 40, 12], rounding=4, edges=Anchor.Z)
   body.show()

The same treatment is available on a shape you have already built, which is what you want when the
rounding is not part of how the shape was made:

.. pythonscad-example::

   from pybosl2 import Anchor, cuboid

   body = cuboid([60, 40, 12]).round_edges(Anchor.Z, radius=4)
   body.show()

``chamfer_edges()`` and ``cove_edges()`` are its siblings. Each takes the *treatment* and works out
the rest from the shape it is applied to — you never restate the part's own dimensions.

3. Cut a hole
-------------

Booleans are operators: ``-`` difference, ``|`` union, ``&`` intersection. Each returns a new
shape, so nothing you built is modified.

.. pythonscad-example::

   from pybosl2 import Anchor, cuboid, cyl

   body = cuboid([60, 40, 12], rounding=4, edges=Anchor.Z)
   bore = cyl(diameter=10, height=20)
   bracket = body - bore
   bracket.show()

A hole is just a solid you subtract. ``cyl`` takes ``radius`` or ``diameter`` — both spellings are
accepted and neither is required, but giving both is an error rather than a silent preference.

4. Put something somewhere
--------------------------

Directional moves read as English, and ``attach`` places a child by the anchor of its parent, so
you rarely have to compute a position.

.. pythonscad-example::

   from pybosl2 import Anchor, cuboid, cyl

   body = cuboid([60, 40, 12], rounding=4, edges=Anchor.Z)
   boss = cyl(diameter=16, height=6)
   bracket = body.attach(Anchor.TOP, boss) - cyl(diameter=10, height=40)
   bracket.show()

5. Measure it
-------------

``bounds()`` answers a box, without rendering anything. It carries every spelling of itself, so
you never do the arithmetic.

.. pythonscad-example::

   from pybosl2 import Anchor, cuboid, cyl

   body = cuboid([60, 40, 12], rounding=4, edges=Anchor.Z)
   bracket = body.attach(Anchor.TOP, cyl(diameter=16, height=6))

   box = bracket.bounds()
   print(box.size)        # (60.0, 40.0, 18.0)
   print(box.max_z)       # 9.0 -- the top of the boss
   print(box.center)      # where the middle of it sits
   bracket.show()

6. Save it
----------

.. pythonscad-example::

   from pybosl2 import Anchor, cuboid, cyl

   body = cuboid([60, 40, 12], rounding=4, edges=Anchor.Z)
   bracket = body.attach(Anchor.TOP, cyl(diameter=16, height=6)) - cyl(diameter=10, height=40)

   bracket.export("bracket.stl")
   bracket.show()

The suffix picks the format — ``.stl``, ``.obj``, ``.off``, ``.ply``. Before writing, pybosl2
checks that the mesh is closed and wound the right way out, so a part that would fail in your
slicer fails here instead, with a message saying what is wrong.

Where to go next
----------------

**Curves and paths.** A :class:`~pybosl2.path2d.Path2D` or
:class:`~pybosl2.path3d.Path3D` is an ordered point list that owns its own measurement, sampling
and cleanup — and it becomes geometry by extruding or sweeping:

.. pythonscad-example::

   from pybosl2 import Path2D

   profile = Path2D([[0, 0], [30, 0], [30, 8], [8, 8], [8, 24], [0, 24]], closed=True)
   rail = profile.round_corners(radius=2).linear_sweep(height=40, twist=45)
   rail.show()

A sweep returns a solid, so it composes with ``-``/``|``/``&`` like anything else; its mesh is on
``.vnf`` if you want to measure or export that directly.

**Ready-made parts.** The parts library is driven by trade-size names rather than measurements,
and every part exposes its derived dimensions as properties, so you can measure one without
building it::

   from pybosl2.parts import Screw

   screw = Screw("M6", length=20)
   print(screw.pitch)          # 1.0 -- derived from the "M6" spec
   screw.export("m6x20.stl")

**Smoothness.** Anything that draws a curve takes ``fn``/``fa``/``fs``, and you can set them once
for a block instead of threading them through every call::

   from pybosl2 import cuboid, use_defaults

   with use_defaults(fn=64):
       smooth = cuboid([20, 20, 20], rounding=4)

**The other backend.** The same code builds on an exact-CSG kernel or on signed-distance fields::

   from pybosl2 import cuboid, use_backend

   with use_backend("sdf"):
       field = cuboid([20, 20, 20], rounding=4)

Anything one backend cannot express raises and says so, rather than quietly building something
else.

From here, the API reference below is organised by role: **Foundational** for the primitives and
transforms most models start from, **Paths, regions & surfaces** for the modelling toolkit,
**Math & geometry** for the numeric helpers, and **Parts library** for the mechanical catalogue.

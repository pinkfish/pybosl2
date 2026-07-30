Solid backends: CSG and SDF
===========================

``pybosl2`` can realize a solid two different ways, and the choice is a switchable *backend*:

* **CSG** (the default) — exact constructive solid geometry via PythonSCAD's native
  primitives. Booleans are exact, the attachment/anchoring system is available, and shapes
  carry their BOSL2 metadata. This is today's :class:`~pybosl2.shapes3d.Bosl2Solid`.
* **SDF** — an F-Rep / signed-distance-field engine built on `libfive
  <https://libfive.com>`_ (the merged ``pysolidfive`` code). Shapes are implicit surfaces, so
  they round and blend smoothly and mesh at any resolution, at the cost of the CSG-only
  attachment features. Its solids are :class:`PyShape` objects.

Both backends expose the *same* shared constructors, so the same code builds either one.

The ``pybosl2.solid`` facade
--------------------------

:mod:`pybosl2.solid` is the backend-neutral entry point. Each constructor dispatches to whichever
backend is active and returns a common :class:`~pybosl2._backend.Solid` — a ``Bosl2Solid`` on CSG,
a ``PyShape`` on SDF::

    from pybosl2.solid import sphere, use_backend

    a = sphere(radius=10)          # CSG (default)  -> Bosl2Solid
    with use_backend("sdf"):
        b = sphere(radius=10)      # libfive SDF     -> PyShape

The shared 3-D surface both backends provide:

.. hlist::
   :columns: 3

   * ``cube``
   * ``cuboid``
   * ``cyl``
   * ``cylinder``
   * ``octahedron``
   * ``onion``
   * ``pie_slice``
   * ``prismoid``
   * ``rect_tube``
   * ``regular_prism``
   * ``sphere``
   * ``spheroid``
   * ``teardrop``
   * ``torus``
   * ``tube``
   * ``wedge``
   * ``xcyl``
   * ``ycyl``
   * ``zcyl``

plus the n-ary booleans ``union``, ``difference`` and ``intersection``. The backend-specific
modules (:mod:`pybosl2.shapes3d`, ``pybosl2._sdf``) stay directly importable for anything not yet
unified in the facade.

Selecting a backend
-------------------

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Call
     - Effect
   * - ``current_backend()``
     - The backend active in this context (``"csg"`` by default).
   * - ``use_backend("sdf")``
     - A context manager making its argument the active backend for the ``with`` block. Nestable
       and thread/async-safe (it is a :class:`contextvars.ContextVar`).
   * - ``set_default_backend("sdf")``
     - Change the process-wide default (outside any ``use_backend`` block).

All three are re-exported from :mod:`pybosl2.solid` for convenience.

Combining and converting between backends
-----------------------------------------

A boolean or transform requires its operands to share the active backend. Combining solids from
two different backends raises :class:`~pybosl2.exceptions.CrossBackendError` rather than producing
nonsense::

    from pybosl2.solid import cube, sphere, use_backend

    c = cube(10)                       # csg
    with use_backend("sdf"):
        s = sphere(radius=6)           # sdf
    c | s                              # raises CrossBackendError

Convert first with the bridge methods:

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Method
     - Result
   * - ``pyshape.to_csg()``
     - Mesh the SDF field and wrap it as a ``Bosl2Solid`` — the supported SDF → CSG bridge.
   * - ``pyshape.to_sdf()`` / ``bosl2solid.to_csg()``
     - Identity (already on that backend).
   * - ``bosl2solid.to_sdf()``
     - Raises :class:`~pybosl2.exceptions.UnsupportedByBackend` — an exact CSG solid has no faithful
       distance field. Rebuild it under ``use_backend("sdf")`` instead.

So the CSG → SDF direction is deliberately *not* automatic: build with the SDF backend from the
start when you want an implicit surface.

Capability map: what each backend can do
----------------------------------------

Most of the surface is shared, but a few features belong to one backend only. Calling one on the
wrong backend raises :class:`~pybosl2.exceptions.UnsupportedByBackend` (with a hint) instead of a
confusing ``AttributeError`` — and, on the SDF side, instead of meshing via libfive just to fail:

.. list-table::
   :header-rows: 1
   :widths: 18 40 42

   * - Backend
     - Exclusive features
     - Why
   * - **CSG only**
     - ``attach``, ``anchor_point``, ``reanchor``, ``position``, ``align``, ``reorient``,
       ``orient``, ``edge_mask``, ``edge_profile``, ``edge_profile_asym``, ``corner_profile``,
       ``face_profile``
     - BOSL2's attachment / anchoring system has no signed-distance equivalent.
   * - **CSG only**
     - ``projection``, ``fill``, and all 2-D geometry
       (:class:`~pybosl2.shapes2d.Bosl2Shape2D`, :meth:`Path2D.polygon() <pybosl2.paths.Path2D.polygon>`,
       :meth:`Path2D.hull() <pybosl2.paths.Path2D.hull>`, ``rotate_extrude``, a 2-D ``stroke()``)
     - Only the CSG backend has a 2-D shape object; an SDF is a field over 3-space, with no 2-D
       shadow to project and no outline to fill. See below.
   * - **SDF only**
     - ``round``, ``chamfer`` (as solid methods)
     - Implicit-surface edge treatments. On CSG use the ``rounding=`` / ``chamfer=`` parameters of
       ``cuboid()`` / ``cyl()`` instead.

Query support directly with ``supports(backend, feature)``::

    from pybosl2._backend import supports

    supports("csg", "attach")   # True
    supports("sdf", "attach")   # False
    supports("sdf", "round")    # True
    supports("csg", "sphere")   # True  -- shared surface

2-D on the two backends
-----------------------

2-D *geometry* is a CSG-only notion: :class:`~pybosl2.shapes2d.Bosl2Shape2D` and every
``pybosl2.shapes2d`` constructor build exact 2-D shapes, and stay on the CSG backend even inside a
``use_backend("sdf")`` block (they do not silently change meaning). A **path**, on the other hand,
is just points and so is backend-neutral — and the operations that take a path *to a 3-D solid*
dispatch on the active backend:

.. list-table::
   :header-rows: 1
   :widths: 34 33 33

   * - Call
     - CSG
     - SDF
   * - :meth:`Path.linear_extrude() <pybosl2.paths.Path.linear_extrude>`,
       :meth:`Region.linear_extrude() <pybosl2.regions.Region.linear_extrude>`
     - native ``linear_extrude`` → :class:`~pybosl2.shapes3d.Bosl2Solid`; takes
       ``center``/``twist``/``scale``/``slices``
     - ``polygon_prism`` → :class:`PyShape`; takes ``center`` plus
       ``rounding_top``/``rounding_bottom``/``res``, and rejects the profile-shearing options
   * - :meth:`Bosl2Solid.hull() <pybosl2.shapes3d.Bosl2Solid.hull>` /
       :meth:`PyShape.hull() <pybosl2._sdf.shapes3d.PyShape.hull>`
     - exact native ``hull()``
     - polyhedral hull of the children's support points
   * - :func:`stroke() <pybosl2.drawing.stroke>` of a **3-D** path
     - a tube of Bosl2Solid cylinders/spheres
     - the same tube as one distance field
   * - :meth:`Bosl2Solid.projection() <pybosl2.shapes3d.Bosl2Solid.projection>`,
       ``Path.polygon()``/``.fill()``/``.hull()``/``.rotate_extrude()``, 2-D ``stroke()``
     - → :class:`~pybosl2.shapes2d.Bosl2Shape2D` / :class:`~pybosl2.shapes3d.Bosl2Solid`
     - :class:`~pybosl2.exceptions.UnsupportedByBackend`

So the same source builds on either backend as long as it goes path → solid::

    outline = Path([[0, 0], [40, 0], [40, 25], [0, 25]]).round_corners(radius=5)
    plate = outline.linear_extrude(height=4)              # -> Bosl2Solid
    with use_backend("sdf"):
        field = outline.linear_extrude(height=4)          # -> PyShape

Sweeping a profile along a path (SDF)
-------------------------------------

The SDF backend can sweep a 2-D profile (**convex or concave**) along a 3-D path directly as a
distance field (``pybosl2._sdf.shapes3d.path_sweep`` / ``bezier_sweep``). The profile is placed in a
rotation-minimizing frame at each path sample and unioned; the cross-section itself is evaluated with
the convex-deficiency decomposition (the same one ``polygon_prism`` uses over the convex-only
``polygon_extrude``), so concave outlines are handled correctly. The result is a true SDF — it can be
``.round()``/``.chamfer()``ed, meshed at any resolution, or bridged to CSG with ``.to_csg()``. Bezier
generation stays pybosl2's canonical :class:`~pybosl2.beziers.Bezier`; the sweep just consumes the
sampled curve::

    import math, numpy as np
    from pybosl2._sdf.shapes3d import bezier_sweep

    circle = [[2 * math.cos(t), 2 * math.sin(t)] for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
    tube = bezier_sweep(circle, [[0, 0, 0], [0, 0, 20], [25, 12, 15], [30, 4, 6]])

This is distinct from the CSG sweeps (:meth:`pybosl2.beziers.Bezier.sweep`, ``skin``, ``offset_sweep``),
which build a VNF/polyhedron mesh rather than a distance field. Denser paths give a smoother lateral
surface; the ends cap perpendicular to the path.

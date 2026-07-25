Solid backends: CSG and SDF
===========================

``bosl2`` can realize a solid two different ways, and the choice is a switchable *backend*:

* **CSG** (the default) — exact constructive solid geometry via PythonSCAD's native
  primitives. Booleans are exact, the attachment/anchoring system is available, and shapes
  carry their BOSL2 metadata. This is today's :class:`~bosl2.shapes3d.Bosl2Solid`.
* **SDF** — an F-Rep / signed-distance-field engine built on `libfive
  <https://libfive.com>`_ (the merged ``pysolidfive`` code). Shapes are implicit surfaces, so
  they round and blend smoothly and mesh at any resolution, at the cost of the CSG-only
  attachment features. Its solids are :class:`PyShape` objects.

Both backends expose the *same* shared constructors, so the same code builds either one.

The ``bosl2.solid`` facade
--------------------------

:mod:`bosl2.solid` is the backend-neutral entry point. Each constructor dispatches to whichever
backend is active and returns a common :class:`~bosl2._backend.Solid` — a ``Bosl2Solid`` on CSG,
a ``PyShape`` on SDF::

    from bosl2.solid import sphere, use_backend

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
modules (:mod:`bosl2.shapes3d`, ``bosl2._sdf``) stay directly importable for anything not yet
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

All three are re-exported from :mod:`bosl2.solid` for convenience.

Combining and converting between backends
-----------------------------------------

A boolean or transform requires its operands to share the active backend. Combining solids from
two different backends raises :class:`~bosl2.exceptions.CrossBackendError` rather than producing
nonsense::

    from bosl2.solid import cube, sphere, use_backend

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
     - Raises :class:`~bosl2.exceptions.UnsupportedByBackend` — an exact CSG solid has no faithful
       distance field. Rebuild it under ``use_backend("sdf")`` instead.

So the CSG → SDF direction is deliberately *not* automatic: build with the SDF backend from the
start when you want an implicit surface.

Capability map: what each backend can do
----------------------------------------

Most of the surface is shared, but a few features belong to one backend only. Calling one on the
wrong backend raises :class:`~bosl2.exceptions.UnsupportedByBackend` (with a hint) instead of a
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
   * - **SDF only**
     - ``round``, ``chamfer`` (as solid methods)
     - Implicit-surface edge treatments. On CSG use the ``rounding=`` / ``chamfer=`` parameters of
       ``cuboid()`` / ``cyl()`` instead.

Query support directly with ``supports(backend, feature)``::

    from bosl2._backend import supports

    supports("csg", "attach")   # True
    supports("sdf", "attach")   # False
    supports("sdf", "round")    # True
    supports("csg", "sphere")   # True  -- shared surface

Backends
========

``pybosl2`` can realize a solid two different ways, and the choice is a switchable *backend*:

* **CSG** (the default) — exact constructive solid geometry via PythonSCAD's native
  primitives. Booleans are exact, the attachment/anchoring system is available, and shapes
  carry their BOSL2 metadata. This is today's ``pybosl2.shapes3d.Bosl2Solid``.
* **SDF** — an F-Rep / signed-distance-field engine built on `libfive
  <https://libfive.com>`_ (the merged ``pysolidfive`` code). Shapes are implicit surfaces, so
  they round and blend smoothly and mesh at any resolution, at the cost of the CSG-only
  attachment features. Its solids are :class:`PyShape` objects.

Both backends expose the *same* shared constructors, so the same code builds either one.

The ``pybosl2.solid`` facade
----------------------------

:mod:`pybosl2.solid` is the backend-neutral entry point. Each constructor dispatches to whichever
backend is active and returns a common ``Solid`` — a ``Bosl2Solid`` on CSG,
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
modules (:mod:`pybosl2.shapes3d`, ``pybosl2.sdf``) stay directly importable for anything not yet
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
two different backends raises :class:`~pybosl2.exceptions` rather than producing
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
     - Raises :class:`~pybosl2.exceptions.UnsupportedByBackendError` — an exact CSG solid has no faithful
       distance field. Rebuild it under ``use_backend("sdf")`` instead.

So the CSG → SDF direction is deliberately *not* automatic: build with the SDF backend from the
start when you want an implicit surface.

Capability map: what each backend can do
----------------------------------------

Most of the surface is shared, but a few features belong to one backend only. Calling one on the
wrong backend raises :class:`~pybosl2.exceptions.UnsupportedByBackendError` (with a hint) instead of a
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
       (:class:`~pybosl2.shapes2d`, :meth:`Path2D.polygon() <pybosl2.paths.Path2D.polygon>`,
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

2-D *geometry* is a CSG-only notion: :class:`~pybosl2.shapes2d` and every
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
     - native ``linear_extrude`` → ``pybosl2.shapes3d.Bosl2Solid``; takes
        ``center``/``twist``/``scale``/``slices``
     - ``polygon_prism`` → :class:`PyShape`; takes ``center`` plus
       ``rounding_top``/``rounding_bottom``/``res``, and rejects the profile-shearing options
   * - ``Bosl2Solid.hull()`` /
        ``PyShape.hull()``
     - exact native ``hull()``
     - polyhedral hull of the children's support points
   * - :func:`stroke() <pybosl2.path2d.Path2D.stroke>` of a **3-D** path
     - a tube of Bosl2Solid cylinders/spheres
     - the same tube as one distance field
   * - ``Bosl2Solid.projection()``,
        ``Path.polygon()``/``.fill()``/``.hull()``/``.rotate_extrude()``, 2-D ``stroke()``
     - → :class:`~pybosl2.shapes2d` / ``pybosl2.shapes3d.Bosl2Solid``
     - :class:`~pybosl2.exceptions.UnsupportedByBackendError`

So the same source builds on either backend as long as it goes path → solid::

    outline = Path([[0, 0], [40, 0], [40, 25], [0, 25]]).round_corners(radius=5)
    plate = outline.linear_extrude(height=4)              # -> Bosl2Solid
    with use_backend("sdf"):
        field = outline.linear_extrude(height=4)          # -> PyShape

Sweeping a profile along a path (SDF)
-------------------------------------

The SDF backend can sweep a 2-D profile (**convex or concave**) along a 3-D path directly as a
distance field (``pybosl2.sdf.shapes3d.path_sweep`` / ``bezier_sweep``). The profile is placed in a
rotation-minimizing frame at each path sample and unioned; the cross-section itself is evaluated with
the convex-deficiency decomposition (the same one ``polygon_prism`` uses over the convex-only
``polygon_extrude``), so concave outlines are handled correctly. The result is a true SDF — it can be
``.round()``/``.chamfer()``ed, meshed at any resolution, or bridged to CSG with ``.to_csg()``. Bezier
generation stays pybosl2's canonical :class:`~pybosl2.beziers`; the sweep just consumes the
sampled curve::

    import math, numpy as np
    from pybosl2.sdf.shapes3d import bezier_sweep

    circle = [[2 * math.cos(t), 2 * math.sin(t)] for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
    tube = bezier_sweep(circle, [[0, 0, 0], [0, 0, 20], [25, 12, 15], [30, 4, 6]])

This is distinct from the CSG sweeps (:meth:`~pybosl2.skin.Sweepable.sweep`, ``skin``, ``offset_sweep``),
which build a VNF/polyhedron mesh rather than a distance field. Denser paths give a smoother lateral
surface; the ends cap perpendicular to the path.

Rendering the docs examples with PythonSCAD
--------------------------------------------

Every docstring example in this reference is built and mesh-exported by the **real** PythonSCAD
binary (the ``pythonscad-example`` Sphinx directive in ``docs/_ext/pybosl2_example.py``).  This
means the PythonSCAD process must be able to import ``numpy`` and ``shapely`` — pybosl2's core
dependencies.  Without them every rendered example silently falls back to a source-only listing.

The PythonSCAD AppImage bundles its own isolated Python interpreter; ``pip install`` on your host
machine does **not** put packages where that interpreter can find them.  You need to install
numpy and shapely *into the AppImage's own Python*.

**macOS** (``PythonSCAD-dev.app`` or ``PythonSCAD.app``):

.. code-block:: bash

   # The bundled Python lives inside the .app bundle:
   /Applications/PythonSCAD-dev.app/Contents/Frameworks/Python.framework/Versions/*/bin/python3 \
       -m pip install --user numpy shapely

If the ``python3`` binary inside the framework has a broken library path, install to the
per-user site‑packages that the AppImage Python already has on ``sys.path``:

.. code-block:: bash

   python3 -m pip install --target ~/Library/Python/3.*/lib/python/site-packages numpy shapely

**Linux** (AppImage extracted):

.. code-block:: bash

   # Extract the AppImage first, then find its Python:
   PYBASE=$(find /opt/pythonscad -path '*/bin/python3*' -not -path '*/__pycache__/*' | head -1)
   $PYBASE -m pip install --user numpy shapely

**Check**: Run a minimal script through the binary to confirm both libraries import:

.. code-block:: bash

   BIN=/path/to/PythonSCAD
   cat > /tmp/check.py << 'PYEOF'
   import sys, site, os
   usp = site.getusersitepackages()
   if os.path.isdir(usp) and usp not in sys.path:
       sys.path.insert(0, usp)
   import numpy as np
   import shapely
   print(f"numpy {np.__version__}  shapely {shapely.__version__}", file=sys.stderr, flush=True)
   from pythonscad import cube
   cube([1,1,1]).show()
   PYEOF
   "$BIN" --trust-python --enable python-engine -o /tmp/test.stl --backend Manifold /tmp/check.py
   ls -la /tmp/test.stl   # should be a non-zero STL file

.. seealso::

   `PythonSCAD documentation — getting started <https://pythonscad.org/>`_
     Official install and usage docs.

   `PythonSCAD — Python libraries <https://github.com/pythonscad/pythonscad/tree/main/docs>`_
     How to install third‑party packages into PythonSCAD's bundled Python.

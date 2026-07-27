Paths
=====

The object form of BOSL2's path maths. :class:`~pybosl2.paths.Path` is a 2-D outline (a list of
``[x, y]`` points) carrying every ``paths.scad`` operation as a chained method;
:class:`~pybosl2.paths.Path3D` is its 3-D sibling (a list of ``[x, y, z]`` points), used by the 3-D
generators like :func:`~pybosl2.drawing.helix`. ``Path3D`` reuses the same numeric kernels and
carries only the operations that make sense in 3-D -- measurement (length, tangents,
:meth:`~pybosl2.paths.Path3D.normals`, curvature, :meth:`~pybosl2.paths.Path3D.torsion`), resampling
and cutting, and the 3-D transforms (``translate``/``move``, the six directional moves including
``up``/``down``, ``scale``, ``rotate``, ``mirror``) -- with :meth:`~pybosl2.paths.Path3D.path2d` to
drop to the XY plane when you need the inherently-2-D operations (``polygon``, ``offset``, ``area``).
.. automodule:: pybosl2.paths
   :members:
   :undoc-members:
   :show-inheritance:

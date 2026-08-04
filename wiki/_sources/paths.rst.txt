Paths
=====

The object form of BOSL2's path maths. :class:`~pybosl2.path2d.Path2D` is a 2-D outline (a list of
``[x, y]`` points) carrying every ``paths.scad`` operation as a chained method;
:class:`~pybosl2.path3d.Path3D` is its 3-D sibling (a list of ``[x, y, z]`` points), used by the 3-D
generators like :meth:`~pybosl2.path3d.Path3D.helix`. ``Path3D`` reuses the same numeric kernels and
carries only the operations that make sense in 3-D -- measurement (length, tangents,
:meth:`~pybosl2.path3d.Path3D.normals`, curvature, :meth:`~pybosl2.path3d.Path3D.torsion`), resampling
and cutting, and the 3-D transforms (``translate``/``move``, the six directional moves including
``up``/``down``, ``scale``, ``rotate``, ``mirror``) -- with :meth:`~pybosl2.path3d.Path3D.path2d` to
drop to the XY plane when you need the inherently-2-D operations (``polygon``, ``offset``, ``area``).

.. automodule:: pybosl2.paths
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: pybosl2.path2d
   :members:
   :exclude-members: Path, CutPoint, CutPoint.point, CutPoint.next_index, CutPoint.direction, CutPoint.normal, SubdivideMethod, catenary, SelfIntersection
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: pybosl2.path3d
   :members:
   :exclude-members: Path, CutPoint, SubdivideMethod
   :undoc-members:
   :show-inheritance:
   :no-index:

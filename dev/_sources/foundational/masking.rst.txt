Masking
=======

Cut a rounded, chamfered or grooved profile into an edge, a corner or a face of a solid
(BOSL2 ``masks2d.scad`` / ``masks3d.scad``).

Two shapes of tool:

* :class:`~pybosl2.masking.Mask2D` builds the 2-D cutter cross-section you sweep along an edge --
  pass one as the *children* of :meth:`~pybosl2.shapes3d.base.Bosl2Solid.edge_profile` or
  :meth:`~pybosl2.shapes3d.base.Bosl2Solid.corner_profile`.
* :class:`~pybosl2.masking.Mask3D` builds a finished 3-D cutter solid: subtract it to treat every
  selected edge or corner in one go.

The BOSL2 spellings (``mask2d_roundover``, ``mask3d_chamfer``, …) remain as aliases of the
factories, so existing code keeps working.

.. pythonscad-example::

    from pybosl2 import Anchor, Mask2D, cuboid

    cuboid([30, 30, 20]).edge_profile(edges=[Anchor.TOP], children=Mask2D.roundover(4)).show()

.. pythonscad-example::

    from pybosl2 import Mask3D, cuboid

    (cuboid([30, 30, 30]) - Mask3D.roundover(4, size=(30, 30, 30))).show()

API reference
-------------

.. automodule:: pybosl2.masking
   :members:
   :undoc-members:
   :show-inheritance:

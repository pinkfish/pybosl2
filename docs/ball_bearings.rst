Ball bearings
=============

Pure-Python port of BOSL2's ``ball_bearings.scad``: models of standard ball-bearing cartridges.
:meth:`~bosl2.ball_bearings.BallBearings.ball_bearing` builds one from a trade-size name or explicit
dimensions; :meth:`~bosl2.ball_bearings.BallBearings.ball_bearing_info` returns the tabulated
dimensions as a :class:`~bosl2.ball_bearings.BearingSpec`.

.. autoclass:: bosl2.ball_bearings.BearingSpec
   :members:

.. autoclass:: bosl2.ball_bearings.BallBearings
   :members:

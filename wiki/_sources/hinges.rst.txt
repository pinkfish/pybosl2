Hinges
======

Pure-Python port of the hinges in BOSL2's ``hinges.scad``: a print-in-place
:meth:`~bosl2.hinges.Hinges.living_hinge_mask` (differenced from a plate to make a folding "live"
hinge), a functional interlocking :meth:`~bosl2.hinges.Hinges.knuckle_hinge` leaf (with
:meth:`~bosl2.hinges.Hinges.knuckle_hinge_pair` for both leaves meshed around one pin, at any fold
angle), and simple :meth:`~bosl2.hinges.Hinges.snap_lock` / :meth:`~bosl2.hinges.Hinges.snap_socket`
connectors.

.. autoclass:: bosl2.hinges.Hinges
   :members:

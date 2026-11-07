"""Foreign-rig importers.

Each module here converts ONE foreign format into a `retarget.skeleton.Rig` and
`Clip` already expressed in werk convention (right handed, +Y up, -Z forward,
quaternions wxyz, metres). Downstream code never asks which format a rig came
from, and every axis/handedness/unit conversion is therefore in exactly one
named, testable place per format.
"""

"""Reusable node-group builders. Import order is dependency order: a module may only build groups from modules
listed before it (checked by `nodes_tools.py check`)."""

MODULE_ORDER = [
    "curve",       # curve frames, bending flat layouts onto a path, samples and parcels along a path
    "shapes",      # small parametric meshes: rounded/chamfered boxes, rods, rings, leaves, blossoms, foliage
    "scatter",     # distributing instances on surfaces and along curves
    "motion",      # analytic animation: springs, gait steps, wind gusts, pendulums, time remaps
    "materials",   # shader node groups: attribute tints, stucco, wood, stone, felt, terracotta, stripes, glow
    "post",        # compositor groups: haze over sky, glow
]

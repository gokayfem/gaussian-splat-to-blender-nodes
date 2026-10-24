"""Part registry. Each module exposes ``build() -> GeometryNodeTree`` (a modifier group named "Garden ...")
and may expose ``materials() -> None`` (called first) and ``CONTROLS`` (doc only).

Ownership (one agent per module group; never edit another owner's module):
  ground      paving, joints, lawn, soil, paths, ground transitions
  table       radial table top, centre disc, legs, cross foot
  vase        vase vessel + dried arrangement
  tree        main tree trunk/branches/canopy near the hero view
  shrubs      shrubs, herbaceous plants, ground plants in the near/mid garden
  boundary    hedges, climbers, boundary walls, fences, shed, far vegetation
  structures  raised beds, pots, stakes/obelisks, steps, pallet, watering can, pond grates, ornaments, statue
"""
PARTS = ["ground", "table", "vase", "tree", "shrubs", "boundary", "structures"]

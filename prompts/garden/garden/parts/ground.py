"""Garden part 'ground': hexagonal paving around the table, the continuous ground surface (joint bed, lawn soil,
bed terrace), the patchy lawn and the path strips beyond it.

Sub-groups (all "Garden Ground ..."): Paving Boundary, Lawn Outline, Height, Hex Slab, Paving, Surface, Lawn, Paths.
Fitted numbers: data/params/ground.json (scripts/analyze_ground.py, scripts/analyze_ground_ortho.py).
"""
from nodekit.graph import Graph

from garden.parts import ground_materials
from garden.parts.ground_lawn import ground_surface, lawn, paths
from garden.parts.ground_paving import paving

CONTROLS = ["Seed", "Joint Width", "Slab Bevel", "Slab Jitter", "Joint Litter", "Lawn Density", "Lawn Height",
            "Lawn Patchiness", "Lawn Edge Creep", "Show Lawn"]


def materials():
    ground_materials.build_all()


def build():
    g = Graph("Garden Ground", kind="GEOMETRY", modifier=True,
              description="Garden ground: fitted hex paving with joint litter, the ground surface, patchy instanced "
                          "lawn and the concrete path strips")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed for slabs, litter and grass")
    joint = g.input("Joint Width", "FLOAT", 0.006, min=0.0, max=0.08, subtype="DISTANCE", panel="Paving",
                    desc="Gap between neighbouring paving slabs")
    bevel = g.input("Slab Bevel", "FLOAT", 0.006, min=0.0, max=0.04, subtype="DISTANCE", panel="Paving",
                    desc="Rounded top edge of each slab")
    jitter = g.input("Slab Jitter", "FLOAT", 1.0, min=0.0, max=4.0, panel="Paving",
                     desc="Scale of per-slab settling, tilt and shift (1 = fitted)")
    litter = g.input("Joint Litter", "FLOAT", 1.0, min=0.0, max=3.0, panel="Paving",
                     desc="Needles, moss and weeds in the joints (1 = fitted)")
    dens = g.input("Lawn Density", "FLOAT", 3000.0, min=0.0, max=20000.0, panel="Lawn",
                   desc="Grass tufts per square metre at full cover")
    height = g.input("Lawn Height", "FLOAT", 0.07, min=0.005, max=0.6, subtype="DISTANCE", panel="Lawn",
                     desc="Tallest grass blade")
    patchy = g.input("Lawn Patchiness", "FLOAT", 0.3, min=0.0, max=1.0, subtype="FACTOR", panel="Lawn",
                     desc="How strongly noise patches thin the lawn")
    creep = g.input("Lawn Edge Creep", "FLOAT", 0.45, min=-0.5, max=1.0, subtype="DISTANCE", panel="Lawn",
                    desc="How far grass grows in over the outer slabs")
    show = g.input("Show Lawn", "BOOL", True, panel="Lawn", desc="Generate the grass instances (off for fast previews)")
    with g.frame("Paving: fitted hex slabs, joint litter, ground lights"):
        pv = g.group(paving(), Seed=seed, **{"Joint Width": joint}, Bevel=bevel,
                     **{"Height Jitter": g.math("MULTIPLY", jitter, 0.004)},
                     **{"Tilt Jitter": g.math("MULTIPLY", jitter, 0.012)},
                     **{"Placement Jitter": g.math("MULTIPLY", jitter, 0.006)}, **{"Joint Litter": litter})
    with g.frame("Ground surface and lawn"):
        surf = g.group(ground_surface())["Mesh"]
        grass = g.group(lawn(), Ground=surf, Seed=seed, Density=dens, Height=height, Patchiness=patchy,
                        **{"Edge Creep": creep})["Instances"]
        grass = g.node("GeometryNodeSwitch", props={"input_type": "GEOMETRY"}, Switch=show, **{"True": grass})
    with g.frame("Paths and stepping stones"):
        pth = g.group(paths())["Mesh"]
    with g.frame("Join everything"):
        out = g.node("GeometryNodeJoinGeometry")
        for geo in (pv["Geometry"], surf, grass["Output"], pth):
            g.connect(geo, out.i("Geometry"))
    g.output("Geometry", "GEOMETRY", out, desc="Ground geometry (slabs, litter and grass stay instances)")
    return g.finish()

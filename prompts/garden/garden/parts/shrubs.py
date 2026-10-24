"""Garden part 'shrubs': near/mid-garden shrubs and herbaceous plants as Geometry Nodes + Shader Nodes.

Fitted data: data/params/shrubs.json (scripts/analyze_shrubs.py measures pieces from the splat cloud; its
"tuning" block holds the hand-fitted build controls and survives re-measurement).

Top group 'Garden Shrubs' = 'Garden Shrubs Data' (one point per measured piece) -> 'Garden Shrubs Envelope'
(union of piece ellipsoids, lumpy) -> 'Garden Shrubs Clusters' (instanced leaves + dark under-layer) and
'Garden Shrubs Herbaceous' (iris-like strap clumps, fringe blades, low rosettes, white blossoms).
"""
import bpy

from nodekit.graph import Graph

from garden.parts import shrubs_branches as sb
from garden.parts import shrubs_groups as sg
from garden.parts import shrubs_materials as sm
from garden.parts.shrubs_nodes import join
from garden.util import load_params

CONTROLS = ["Seed", "Leaf Density", "Leaf Scale", "Inflate", "Lumpiness", "Color Gain", "Color Variation",
            "Clump Density", "Flower Density"]

TUNING = dict(inflate=1.15, pad=0.04, height_scale=1.0, voxel=0.05, lumpiness=0.26, lump_scale=1.1, density=90.0,
              leaf_scale=1.0, depth=0.35, lift=0.45, color_gain=2.2, herb_gain=1.5, color_var=0.7, clump_density=5.0,
              fringe_density=22.0, strap_height=0.95, rosette_density=40.0, flower_density=200.0,
              size_broadleaf=0.05, size_bright=0.05, size_sparse=0.07, sparse_density=0.5, sparse_inflate=0.9, branch_density=16.0, branch_leaf=0.16, branch_length=0.6, bright_height=1.5, under_layer=False)


def _params():
    p = load_params("shrubs")
    pieces = list(p.get("shrubs", [])) + list(p.get("weeds", []))
    tune = {**TUNING, **p.get("tuning", {})}
    return pieces, tune


def density_object(points):
    """Sparse measured control data: one vertex per foliage density voxel with a float attribute sh_density.
    It is read by the graph through Object Info; it never renders (vertices only, kept in the QA collection)."""
    name = "GARDEN_shrubs_density"
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    me.clear_geometry()
    me.vertices.add(len(points))
    me.vertices.foreach_set("co", [c for p in points for c in p[:3]])
    a = me.attributes.get("sh_density") or me.attributes.new("sh_density", "FLOAT", "POINT")
    a.data.foreach_set("value", [p[3] for p in points])
    me.update()
    ob = bpy.data.objects.get(name) or bpy.data.objects.new(name, me)
    coll = bpy.data.collections.get("QA") or bpy.context.scene.collection
    if ob.name not in coll.objects:
        coll.objects.link(ob)
    ob.hide_render = True
    return ob


def materials():
    sm.leaf_material()
    sm.blossom_material()


def build():
    pieces, t = _params()
    data = sg.build_data(pieces)
    dens_ob = density_object(load_params("shrubs").get("density_field", {}).get("points", []))
    g = Graph("Garden Shrubs", kind="GEOMETRY", modifier=True,
              description="Near/mid-garden shrubs and herbaceous plants fitted to the Garden splat: measured "
              "piece envelopes unioned into lumpy mounds, clothed in instanced leaves, with iris-like strap "
              "clumps, low rosettes and white blossoms")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed for every scatter")
    dens = g.input("Leaf Density", "FLOAT", t["density"], min=0.0, max=5000.0,
                   desc="Leaves per square metre of envelope")
    lscale = g.input("Leaf Scale", "FLOAT", t["leaf_scale"], min=0.2, max=4.0, desc="Multiplier on fitted leaf sizes")
    infl = g.input("Inflate", "FLOAT", t["inflate"], min=0.5, max=4.0, desc="Envelope radius multiplier")
    lump = g.input("Lumpiness", "FLOAT", t["lumpiness"], min=0.0, max=1.0, subtype="DISTANCE",
                   desc="Envelope surface noise amplitude")
    gain = g.input("Color Gain", "FLOAT", t["color_gain"], min=0.2, max=4.0, desc="Scan colour to albedo gain")
    var = g.input("Color Variation", "FLOAT", t["color_var"], min=0.0, max=1.0, subtype="FACTOR",
                  desc="Per-leaf brightness and hue spread")
    clump = g.input("Clump Density", "FLOAT", t["clump_density"], min=0.0, max=100.0,
                    desc="Iris-like strap clumps per m^2 on strap pieces")
    flw = g.input("Flower Density", "FLOAT", t["flower_density"], min=0.0, max=2000.0,
                  desc="White blossoms per m^2 at full measured flower share")
    leaf_m = bpy.data.materials["Garden Shrubs Leaf"]
    blos_m = bpy.data.materials["Garden Shrubs Blossom"]
    with g.frame("Measured pieces -> union envelope"):
        pts = g.group(data)["Points"]
        field = g.node("GeometryNodeObjectInfo", props={"transform_space": "RELATIVE"}, Object=dens_ob)["Geometry"]
        env = g.group(sg.build_envelope(), Pieces=pts, **{"Density Field": field}, Inflate=infl, Pad=t["pad"], Lumpiness=lump, Seed=seed,
                      **{"Height Scale": t["height_scale"], "Sparse Inflate": t["sparse_inflate"], "Bright Height": t["bright_height"], "Voxel Size": t["voxel"],
                         "Lump Scale": t["lump_scale"]})["Envelope"]
    with g.frame("Leaves and under-layer; herbaceous plants and blossoms"):
        cl = g.group(sg.build_clusters(), Envelope=env, Seed=seed, Depth=t["depth"],
                     **{"Leaf Density": dens, "Leaf Scale": lscale, "Leaf Lift": t["lift"], "Color Gain": gain,
                        "Color Variation": var, "Size Broadleaf": t["size_broadleaf"],
                        "Size Bright": t["size_bright"], "Size Sparse": t["size_sparse"],
                        "Sparse Density": t["sparse_density"], "Under Layer": t["under_layer"],
                        "Leaf Material": leaf_m})["Geometry"]
        hb = g.group(sg.build_herbaceous(), Envelope=env, Seed=seed,
                     **{"Clump Density": clump, "Fringe Density": t["fringe_density"],
                        "Strap Height": t["strap_height"], "Rosette Density": t["rosette_density"],
                        "Flower Density": flw, "Color Gain": g.math("MULTIPLY", gain, t["herb_gain"] / t["color_gain"]), "Leaf Material": leaf_m,
                        "Blossom Material": blos_m})["Geometry"]
        br = g.group(sb.build_branches(), Envelope=env, Seed=seed, **{
            "Branch Density": t["branch_density"], "Branch Length": t["branch_length"],
            "Leaf Length": t["branch_leaf"], "Color Gain": gain,
            "Leaf Material": leaf_m})["Geometry"]
    g.output("Geometry", "GEOMETRY", join(g, cl, hb, br), desc="Shrubs and herbaceous plants")
    return g.finish()

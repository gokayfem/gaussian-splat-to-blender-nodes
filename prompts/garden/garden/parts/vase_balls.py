"""Back-layer seed balls of the vase arrangement: smooth wooden balls and scaly cone-balls, instanced.

"Garden Vase Seed Balls": one point per fitted ball (data/params/vase.json arrangement.balls: centre in the plane
frame, radius, sRGB colour, kind 0 smooth / 1 scaly), each carrying nk_color and its radius; a smooth sphere or a
pointed Voronoi-scaled cone is instanced on it (Pick Instance by kind) with a short stem toward the vessel mouth.
"""
from nodekit.graph import Graph, once

from garden.parts import vase_nodes as vn
from garden.util import load_params

AP = load_params("vase").get("arrangement", {})


def _ball_point(g, b, k, seed):
    pt = g.node("GeometryNodePoints", Count=1, Position=tuple(b["centre"]), Radius=b["radius"])["Points"]
    pt = vn.store(g, pt, "nk_color", vn.colour(b["color"]), dtype="FLOAT_COLOR")
    pt = vn.store(g, pt, "vase_kind", float(b.get("kind", 0)))
    return vn.store(g, pt, "nk_rand", vn.rand(g, 0.0, 1.0, seed, 40 + k))


@once
def seed_balls():
    balls = AP.get("balls", [])
    g = Graph("Garden Vase Seed Balls",
              description="Fitted back-layer seed balls: smooth wooden balls and scaly cone-balls instanced on one "
                          "point per ball (radius, colour, kind from the fit), each on a thin stem from the mouth")
    size = g.input("Ball Scale", "FLOAT", 1.0, min=0.3, max=2.5, desc="Multiplier on every ball's fitted radius")
    scales = g.input("Scale Relief", "FLOAT", 1.0, min=0.0, max=3.0, desc="Depth of the scaly balls' scales")
    seed = g.input("Seed", "INT", 0, min=0, max=10000, desc="Random seed")
    with g.frame("One point per fitted ball with its colour, kind and radius"):
        pts = vn.join(g, *[_ball_point(g, b, k, seed) for k, b in enumerate(balls)])
        kind = vn.named(g, "vase_kind")
        rad = g.node("GeometryNodeInputRadius")["Radius"]
    with g.frame("Two unit balls: smooth, and scaly (Voronoi cells pushed out, rims marked for the shader)"):
        smooth = vn.smooth(g, g.node("GeometryNodeMeshUVSphere", Segments=24, Rings=12, Radius=1.0)["Mesh"])
        sc = g.node("GeometryNodeMeshIcoSphere", Subdivisions=4, Radius=1.0)["Mesh"]
        vor = g.node("ShaderNodeTexVoronoi", props={"feature": "F1"}, Scale=4.5)["Distance"]
        off = g.vmath("SCALE", g.node("GeometryNodeInputNormal")["Normal"],
                      scale=g.math("MULTIPLY", g.math("SUBTRACT", 0.25, vor), g.math("MULTIPLY", scales, 0.35)))
        sc = vn.store(g, sc, "vase_mottle", g.map_range(vor, 0.05, 0.4, 0.0, 1.0).out)
        sc = vn.smooth(g, g.node("GeometryNodeSetPosition", Geometry=sc, Offset=off.out)["Geometry"])
        # pointed cone: stretch along Z and taper the upper half to a tip
        cq = g.separate(g.node("GeometryNodeInputPosition"))
        ct = g.math("MAXIMUM", cq["Z"], 0.0)
        cs = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", g.math("POWER", ct, 1.5), 0.75))
        sc = g.node("GeometryNodeSetPosition", Geometry=sc, Position=g.combine(
            g.math("MULTIPLY", cq["X"], cs), g.math("MULTIPLY", cq["Y"], cs),
            g.math("MULTIPLY", cq["Z"], g.math("ADD", 1.25, g.math("MULTIPLY", ct, 0.35)))))["Geometry"]
        lib = g.node("GeometryNodeGeometryToInstance")
        for geo in (sc, smooth):  # multi-input stacks newest first: index 0 smooth, 1 scaly
            g.connect(geo, lib.i("Geometry"))
    with g.frame("Instance the picked ball at each point, scaled by its radius"):
        inst = g.node("GeometryNodeInstanceOnPoints", Points=pts, Instance=lib["Instances"],
                      **{"Pick Instance": True, "Instance Index": kind,
                         "Scale": g.math("MULTIPLY", rad, size)})["Instances"]
    with g.frame("Stems from the mouth to each ball"):
        stems = [vn.tube(g, g.node("GeometryNodeCurvePrimitiveLine", Start=(0.004 * k, 0.0, 1.02),
                                   End=tuple(b["centre"]))["Curve"], 0.002, 5) for k, b in enumerate(balls)]
        stems = vn.store(g, vn.join(g, *stems), "nk_color", vn.colour(AP.get("stem_color", (95, 65, 40))),
                         dtype="FLOAT_COLOR")
    g.output("Geometry", "GEOMETRY", vn.join(g, inst, stems), desc="Balls (instances) and stems")
    return g.finish()

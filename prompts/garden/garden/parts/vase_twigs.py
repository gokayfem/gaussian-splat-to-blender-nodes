"""Fine dried twigs and fibres of the vase arrangement.

"Garden Vase Twigs": Count thin curved twigs rising from a small disc in the vessel mouth. One unit twig (a
sagging quadratic Bezier along +X) is instanced per root point, aimed into the arrangement's fitted spread (mostly
within the arrangement plane, fanning from Angle Min to Angle Max, a little out of plane), scaled to a random
length, then realized and swept as a thin tube. Colour nk_color dark stem brown with nk_rand jitter.
"""
import math

from nodekit.graph import Graph, once

from garden.parts import vase_nodes as vn
from garden.util import load_params

TP = load_params("vase").get("arrangement", {}).get("twigs", {})


@once
def twigs():
    g = Graph("Garden Vase Twigs",
              description="Thin curved dried twigs rising from the vessel mouth into the arrangement's spread "
                          "(instanced unit Bezier twigs, realized and swept as fine tubes)")
    count = g.input("Count", "INT", TP.get("count", 30), min=0, max=300, desc="Number of twigs")
    lmin = g.input("Length Min", "FLOAT", TP.get("length_min", 0.1), min=0.01, max=0.5, subtype="DISTANCE",
                   desc="Shortest twig")
    lmax = g.input("Length Max", "FLOAT", TP.get("length_max", 0.24), min=0.01, max=0.6, subtype="DISTANCE",
                   desc="Longest twig")
    amin = g.input("Angle Min", "FLOAT", math.radians(TP.get("angle_min_deg", 10)), min=-math.pi, max=math.pi,
                   subtype="ANGLE", desc="Lowest twig direction in the arrangement plane (0 = +X, 90 = up)")
    amax = g.input("Angle Max", "FLOAT", math.radians(TP.get("angle_max_deg", 170)), min=-math.pi, max=math.pi,
                   subtype="ANGLE", desc="Highest twig direction in the arrangement plane")
    out = g.input("Out Of Plane", "FLOAT", TP.get("out_of_plane", 0.35), min=0.0, max=1.5,
                  desc="How far twigs lean toward +-Y out of the arrangement plane")
    sag = g.input("Curvature", "FLOAT", TP.get("curvature", 0.12), min=-0.5, max=0.5,
                  desc="Bend of each twig as a share of its length (random sign per twig)")
    rad = g.input("Radius", "FLOAT", TP.get("radius", 0.0011), min=0.0002, max=0.01, subtype="DISTANCE",
                  desc="Twig radius")
    seed = g.input("Seed", "INT", 0, min=0, max=10000, desc="Random seed")
    with g.frame("Unit twig along +X with a sideways and downward sag"):
        unit = g.node("GeometryNodeCurveQuadraticBezier", Resolution=10, Start=(0, 0, 0), End=(1, 0, 0),
                      Middle=g.combine(0.5, g.math("MULTIPLY", sag, 0.6), sag))["Curve"]
    with g.frame("Root points in the mouth; direction fanned in the plane, leaning out of it"):
        pts = g.node("GeometryNodePoints", Count=count, Position=g.combine(
            vn.rand(g, -0.03, 0.03, seed, 1), vn.rand(g, -0.012, 0.012, seed, 2), TP.get("root_z", 1.02)))["Points"]
        th = vn.rand(g, amin, amax, seed, 3)
        d = g.combine(g.math("COSINE", th), vn.rand(g, g.math("MULTIPLY", out, -1.0), out, seed, 4),
                      g.math("SINE", th))
        rot = vn.orient(g, d, g.combine(vn.rand(g, -1.0, 1.0, seed, 5), vn.rand(g, -1.0, 1.0, seed, 6), 1.0))
        ln = vn.rand(g, lmin, lmax, seed, 7)
        inst = g.node("GeometryNodeInstanceOnPoints", Points=pts, Instance=unit, Rotation=rot, Scale=ln)["Instances"]
        inst = vn.store(g, inst, "nk_rand", vn.rand(g, 0.0, 1.0, seed, 8), domain="INSTANCE")
    with g.frame("Realize and sweep as fine tubes, tinted stem brown"):
        crv = g.node("GeometryNodeRealizeInstances", Geometry=inst)["Geometry"]
        mesh = vn.tube(g, crv, rad, 4)
        mesh = vn.store(g, mesh, "nk_color", vn.colour(TP.get("color", (110, 78, 50))), dtype="FLOAT_COLOR")
    g.output("Geometry", "GEOMETRY", mesh, desc="Twig tubes")
    return g.finish()

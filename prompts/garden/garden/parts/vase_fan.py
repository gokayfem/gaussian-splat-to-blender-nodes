"""The dried palm fan of the vase arrangement.

"Garden Vase Fan Spear": one broad straw spear (length 1 along +X, face +Z) -- a gently tapering blade with a
V notch splitting its tip into two points, a central fold, two shallow secondary pleats, edges curling up and a
slight twist; stores vase_uv (u root->tip, v across).
"Garden Vase Fan Palm": three spear variants (different fold/curl/notch) picked at random per spear; spears
radiate unevenly from the hub over the fitted spread (angle, length, tilt and roll jitter), rooted in a small
irregularly pleated base, on a petiole from the vessel mouth. Fitted numbers: data/params/vase.json
arrangement.fan.
"""
import math

from nodekit.graph import Graph, once

from garden.parts import vase_nodes as vn
from garden.util import load_params

AP = load_params("vase").get("arrangement", {})
FP = AP.get("fan", {})


def _ramp(g, v, lo, hi):
    return g.map_range(v, lo, hi, 0.0, 1.0, interp="SMOOTHSTEP").out


@once
def spear():
    g = Graph("Garden Vase Fan Spear",
              description="One dried palm spear along +X (length 1), face +Z: tapering blade, V-notched split "
                          "tip, central fold, two shallow secondary pleats, up-curled edges and a slight twist")
    wd = g.input("Width", "FLOAT", 0.26, min=0.05, max=0.8, subtype="FACTOR", desc="Widest width / length")
    fold = g.input("Fold", "FLOAT", 0.35, min=0.0, max=2.0, desc="Central V fold (rise per unit half-width)")
    curl = g.input("Curl", "FLOAT", 0.4, min=-2.0, max=2.0, desc="Edge curl (rise of the edges per width)")
    notch = g.input("Notch", "FLOAT", 0.18, min=0.0, max=0.5, subtype="FACTOR",
                    desc="Depth of the split at the tip as a share of length")
    twist = g.input("Twist", "FLOAT", 0.25, min=-1.5, max=1.5, subtype="ANGLE", desc="Twist from root to tip")
    with g.frame("Grid: u along 0..1, v across -1..1"):
        grid = g.node("GeometryNodeMeshGrid", **{"Size X": 1.0, "Size Y": 2.0, "Vertices X": 32,
                                                 "Vertices Y": 25})["Mesh"]
        p = g.separate(g.node("GeometryNodeInputPosition"))
        u, v = g.math("ADD", p["X"], 0.5), p["Y"]
        av = g.math("ABSOLUTE", v)
    with g.frame("Outline: narrow root, broad body, two-pointed split tip"):
        root = g.math("MULTIPLY_ADD", _ramp(g, u, 0.0, 0.18), 0.75, 0.25)
        body = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", g.math("POWER", u, 1.6), 0.72))
        hw = g.math("MULTIPLY", g.math("MULTIPLY", g.math("MULTIPLY", wd, 0.5), root), body)
        y = g.math("MULTIPLY", v, hw)
        tipcut = g.math("MULTIPLY", g.math("MULTIPLY", notch, g.math("SUBTRACT", 1.0, av)), _ramp(g, u, 0.7, 1.0))
        point = g.math("MULTIPLY", g.math("MULTIPLY", av, 0.12), _ramp(g, u, 0.85, 1.0))
        x = g.math("SUBTRACT", g.math("ADD", u, point), tipcut)
    with g.frame("Relief: central fold, secondary pleats, curled edges; then twist about X"):
        ay = g.math("ABSOLUTE", y)
        pleats = g.math("MULTIPLY", g.math("MULTIPLY", hw, 0.08),
                        g.math("ABSOLUTE", g.math("SINE", g.math("MULTIPLY", v, 2.0 * math.pi))))
        z = g.math("ADD", g.math("MULTIPLY", ay, fold), pleats)
        z = g.math("ADD", z, g.math("MULTIPLY", g.math("MULTIPLY", curl, wd),
                                    g.math("MULTIPLY", g.math("POWER", av, 3.0), _ramp(g, u, 0.1, 0.6))))
        ang = g.math("MULTIPLY", twist, u)
        ca, sa = g.math("COSINE", ang), g.math("SINE", ang)
        pos = g.combine(x, g.math("SUBTRACT", g.math("MULTIPLY", y, ca), g.math("MULTIPLY", z, sa)),
                        g.math("ADD", g.math("MULTIPLY", y, sa), g.math("MULTIPLY", z, ca)))
        mesh = vn.store(g, grid, "vase_uv", g.combine(u, v, 0.0), dtype="FLOAT_VECTOR")
        mesh = vn.store(g, mesh, "vase_root", g.math("MULTIPLY", g.math("POWER", g.math("SUBTRACT", 1.0, u), 3.0), 0.3))
        mesh = g.node("GeometryNodeSetPosition", Geometry=mesh, Position=pos)["Geometry"]
    g.output("Mesh", "GEOMETRY", vn.smooth(g, mesh), desc="The spear")
    return g.finish()


def _variant(g, sp, width, k):
    v = FP.get("variants", [[0.35, 0.5, 0.2, 0.3], [0.2, 0.9, 0.12, -0.2], [0.5, 0.2, 0.26, 0.45]])[k]
    return g.group(sp, Width=width, Fold=v[0], Curl=v[1], Notch=v[2], Twist=v[3])["Mesh"]


@once
def fan_palm():
    sp = spear()
    g = Graph("Garden Vase Fan Palm",
              description="Dried palm fan: broad straw spears (three random variants) radiating unevenly in the XZ "
                          "plane from a small pleated base at the hub, on a petiole from the vessel mouth")
    hub = g.input("Hub", "VECTOR", tuple(FP.get("hub", (0, 0.04, 1.15))), subtype="TRANSLATION",
                  desc="Fan centre (arrangement frame)")
    base = g.input("Stem Base", "VECTOR", tuple(FP.get("stem_base", (0, 0, 1.0))), subtype="TRANSLATION",
                   desc="Where the petiole leaves the vessel mouth")
    n = g.input("Blades", "INT", FP.get("blades", 16), min=3, max=60, desc="Number of spears")
    amin = g.input("Angle Min", "FLOAT", math.radians(FP.get("angle_min_deg", -30)), min=-math.pi,
                   max=2 * math.pi, subtype="ANGLE", desc="Direction of the first spear in the XZ plane (90 = up)")
    amax = g.input("Angle Max", "FLOAT", math.radians(FP.get("angle_max_deg", 196)), min=-math.pi,
                   max=2 * math.pi, subtype="ANGLE", desc="Direction of the last spear")
    ln = g.input("Length", "FLOAT", FP.get("length", 0.2), min=0.02, max=0.5, subtype="DISTANCE",
                 desc="Hub-to-tip length in the middle of the fan")
    lj = g.input("Length Jitter", "FLOAT", FP.get("length_jitter", 0.22), min=0.0, max=0.6, subtype="FACTOR",
                 desc="Random length variation per spear")
    wd = g.input("Blade Width", "FLOAT", FP.get("blade_width", 0.26), min=0.05, max=0.8, subtype="FACTOR",
                 desc="Spear width as a share of its length")
    aj = g.input("Angle Jitter", "FLOAT", FP.get("angle_jitter", 0.35), min=0.0, max=1.0, subtype="FACTOR",
                 desc="Uneven spacing: random angle offset as a share of the even spacing")
    cup = g.input("Cup", "FLOAT", FP.get("cup", 0.1), min=-1.0, max=1.0, desc="Tilt of the spears toward +Y")
    seed = g.input("Seed", "INT", 0, min=0, max=10000, desc="Random seed")
    with g.frame("Three spear variants to pick from"):
        lib = g.node("GeometryNodeGeometryToInstance")
        for k in (2, 1, 0):
            g.connect(_variant(g, sp, wd, k), lib.i("Geometry"))
    with g.frame("Spear roots near the hub: uneven angles, lengths, tilt and roll"):
        pts = g.node("GeometryNodePoints", Count=n, Position=hub)["Points"]
        idx = g.node("GeometryNodeInputIndex")["Index"]
        f = g.math("DIVIDE", idx, g.math("MAXIMUM", g.math("SUBTRACT", n, 1.0), 1.0))
        step = g.math("DIVIDE", g.math("SUBTRACT", amax, amin), g.math("MAXIMUM", n, 1.0))
        jit = g.math("MULTIPLY", step, vn.rand(g, g.math("MULTIPLY", aj, -1.0), aj, seed, 1))
        th = g.math("ADD", g.math("MULTIPLY_ADD", f, g.math("SUBTRACT", amax, amin), amin), jit)
        tilt = g.math("ADD", cup, vn.rand(g, -0.06, 0.06, seed, 2))
        lean = FP.get("lean_back", 0.18)  # upper spears lean back (-Y) so the fan face tips toward the sky
        d = g.combine(g.math("COSINE", th), g.math("SUBTRACT", tilt, g.math("MULTIPLY", g.math("SINE", th), lean)),
                      g.math("SINE", th))
        roll = g.combine(vn.rand(g, -0.12, 0.12, seed, 5), 1.0, vn.rand(g, -0.12, 0.12, seed, 6))
        rot = vn.orient(g, d, roll)
        edge = g.math("POWER", g.math("ABSOLUTE", g.math("MULTIPLY_ADD", f, 2.0, -1.0)), 2.0)
        size = g.math("MULTIPLY", g.math("MULTIPLY", ln, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", edge, 0.3))),
                      g.math("ADD", 1.0, vn.rand(g, g.math("MULTIPLY", lj, -1.0), lj, seed, 3)))
        off = g.vmath("SCALE", g.vmath("NORMALIZE", d), scale=g.math("MULTIPLY", size, FP.get("spear_start", 0.3)))
        pts = g.node("GeometryNodeSetPosition", Geometry=pts, Offset=off.out)["Geometry"]
        pick = g.node("FunctionNodeRandomValue", props={"data_type": "INT"}, Min=0, Max=2,
                      Seed=g.math("ADD", seed, 9.0))["Value"]
        inst = g.node("GeometryNodeInstanceOnPoints", Points=pts, Instance=lib["Instances"], Rotation=rot,
                      Scale=g.math("MULTIPLY", size, 1.0 - FP.get("spear_start", 0.3)), **{"Pick Instance": True, "Instance Index": pick})
        inst = vn.store(g, inst["Instances"], "nk_color", vn.colour(FP.get("color", (240, 210, 150))),
                        dtype="FLOAT_COLOR", domain="INSTANCE")
        inst = vn.store(g, inst, "nk_rand", vn.rand(g, 0.0, 1.0, seed, 4), domain="INSTANCE")
        inst = vn.store(g, inst, "vase_trans", FP.get("translucency", 0.25), domain="INSTANCE")
    with g.frame("Pleated base: small polar grid with irregular zig-zag pleats"):
        web = g.node("GeometryNodeMeshGrid", **{"Size X": 1.0, "Size Y": 1.0, "Vertices Y": 6,
                                                "Vertices X": g.math("MULTIPLY_ADD", n, 4.0, 1.0)})["Mesh"]
        wp = g.separate(g.node("GeometryNodeInputPosition"))
        wu, wv = g.math("ADD", wp["X"], 0.5), g.math("ADD", wp["Y"], 0.5)
        wth = g.math("MULTIPLY_ADD", wu, g.math("SUBTRACT", amax, amin), amin)
        wr = g.math("MULTIPLY", g.math("MULTIPLY_ADD", wv, FP.get("web_radius", 0.45), 0.01), ln)
        par = g.math("FLOORED_MODULO", g.math("ROUND", g.math("MULTIPLY", wu, g.math("MULTIPLY", n, 4.0))), 2.0)
        amp = g.node("ShaderNodeTexNoise", Vector=g.combine(wu, 0.0, 0.0), Scale=6.0, Detail=1.0)["Fac"]
        pleat = g.math("MULTIPLY", g.math("MULTIPLY_ADD", par, 2.0, -1.0),
                       g.math("MULTIPLY", wr, g.math("MULTIPLY", amp, 0.16)))
        wpos = g.vmath("ADD", hub, g.combine(g.math("MULTIPLY", wr, g.math("COSINE", wth)),
                                             g.math("MULTIPLY_ADD", wr, cup, pleat),
                                             g.math("MULTIPLY", wr, g.math("SINE", wth))))
        web = vn.store(g, web, "vase_uv", g.combine(g.math("MULTIPLY", wv, 0.2), 0.0, 0.0), dtype="FLOAT_VECTOR")
        web = vn.store(g, web, "vase_root", g.math("MULTIPLY", g.math("SUBTRACT", 1.0, wv), 0.35))
        web = vn.store(g, web, "vase_trans", FP.get("translucency", 0.25))
        web = vn.store(g, web, "nk_color", vn.colour(FP.get("color", (240, 210, 150))), dtype="FLOAT_COLOR")
        web = g.node("GeometryNodeSetPosition", Geometry=web, Position=wpos.out)["Geometry"]
    with g.frame("Petiole from the mouth to the hub"):
        line = g.node("GeometryNodeCurvePrimitiveLine", Start=base, End=hub)["Curve"]
        stem = vn.tube(g, line, 0.0035)
        stem = vn.store(g, stem, "nk_color", vn.colour(FP.get("stem_color", (170, 140, 95))), dtype="FLOAT_COLOR")
    g.output("Geometry", "GEOMETRY", vn.join(g, inst, web, stem), desc="Spears (instances), pleated base, petiole")
    return g.finish()

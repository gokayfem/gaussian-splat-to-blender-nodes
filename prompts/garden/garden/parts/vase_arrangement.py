"""The dried arrangement in the vase, built in its own plane frame.

Frame (data/params/vase.json "arrangement"): X = s along the arrangement plane, Y = n toward the hero camera,
Z = world height. Groups: "Garden Vase Fan Palm" (pleated blades radiating from a hub on a petiole),
"Garden Vase Pod Frond" (a curved stem with alternating pointed orange leaves), "Garden Vase Seed Heads" (ball,
grey bloom, spiral shell cone, two scaly cones and their stems) and "Garden Vase Dried Arrangement" joining them.
Leaves carry vase_uv (u root->tip, v across) and vase_root; every piece carries nk_color and nk_rand.
"""
import math

from library.shapes import leaf
from nodekit.graph import Graph, once

from garden.parts import vase_balls, vase_materials, vase_twigs
from garden.parts.vase_fan import fan_palm
from garden.parts import vase_nodes as vn
from garden.util import load_params

AP = load_params("vase").get("arrangement", {})


def _leaf_uv(g, mesh, length, root_amount=1.0):
    """Store vase_uv (u = 0 root .. 1 tip, v across) and vase_root = amount * (1 - u)^2 on a leaf along +X."""
    p = g.separate(g.node("GeometryNodeInputPosition"))
    u = g.math("DIVIDE", p["X"], length)
    mesh = vn.store(g, mesh, "vase_uv", g.combine(u, g.math("DIVIDE", p["Y"], length), 0.0), dtype="FLOAT_VECTOR")
    root = g.math("MULTIPLY", g.math("POWER", g.math("SUBTRACT", 1.0, u, clamp=True), 2.0), root_amount)
    return vn.store(g, mesh, "vase_root", root)


@once
def pod_frond():
    pl = AP.get("pod_leaf", {})
    g = Graph("Garden Vase Pod Frond",
              description="A curved dried stem (quadratic Bezier) with alternating pointed leaves angled toward its "
                          "tip, shrinking toward the tip; leaves are instances tinted root to tip")
    start = g.input("Start", "VECTOR", (0, 0, 1.02), subtype="TRANSLATION", desc="Stem base")
    mid = g.input("Middle", "VECTOR", (0.1, 0, 1.08), subtype="TRANSLATION", desc="Bezier control point")
    end = g.input("End", "VECTOR", (0.2, 0, 1.1), subtype="TRANSLATION", desc="Stem tip")
    count = g.input("Leaves", "INT", 12, min=0, max=80, desc="Leaves along the stem")
    tint = g.input("Color", "COLOR", vn.colour(pl.get("color", (205, 140, 90))), desc="Leaf tint (linear)")
    ln = g.input("Leaf Length", "FLOAT", pl.get("length", 0.085), min=0.01, max=0.3, subtype="DISTANCE",
                 desc="Length of the lowest leaves")
    wd = g.input("Leaf Width", "FLOAT", pl.get("width", 0.24), min=0.05, max=0.8, subtype="FACTOR",
                 desc="Leaf width as a share of its length")
    spread = g.input("Spread", "FLOAT", math.radians(pl.get("spread_deg", 38)), min=0.0, max=1.5,
                     subtype="ANGLE", desc="Angle between a leaf and the stem")
    seed = g.input("Seed", "INT", 0, min=0, max=10000, desc="Random seed")
    with g.frame("Stem curve and its leaf points (start of stem kept bare)"):
        crv = g.node("GeometryNodeCurveQuadraticBezier", Resolution=24, Start=start, Middle=mid, End=end)["Curve"]
        stem = vn.tube(g, crv, 0.0026, 6)
        stem = vn.store(g, stem, "nk_color", vn.colour(AP.get("stem_color", (95, 65, 40))), dtype="FLOAT_COLOR")
        trim = g.node("GeometryNodeTrimCurve", props={"mode": "FACTOR"}, Curve=crv, Start=0.3, End=1.0)["Curve"]
        res = g.node("GeometryNodeResampleCurve", Curve=trim, Mode="Count", Count=count)["Curve"]
        pts = g.node("GeometryNodeCurveToPoints", props={"mode": "EVALUATED"}, Curve=res)
    with g.frame("Leaf directions: tangent turned by Spread to alternate sides in the plane, a little out of it"):
        idx = g.node("GeometryNodeInputIndex")["Index"]
        f = g.math("DIVIDE", idx, g.math("MAXIMUM", g.math("SUBTRACT", count, 1.0), 1.0))
        side = g.math("MULTIPLY_ADD", g.math("FLOORED_MODULO", idx, 2.0), 2.0, -1.0)
        tan = pts["Tangent"]
        perp = g.vmath("NORMALIZE", g.vmath("CROSS_PRODUCT", (0.0, 1.0, 0.0), tan)).out
        ang = g.math("ADD", spread, vn.rand(g, -0.15, 0.15, seed, 11))
        d = g.vmath("ADD", g.vmath("SCALE", tan, scale=g.math("COSINE", ang)),
                    g.vmath("SCALE", perp, scale=g.math("MULTIPLY", side, g.math("SINE", ang))))
        d = g.vmath("ADD", d, g.combine(0.0, vn.rand(g, -0.35, 0.35, seed, 12), 0.0))
        nrm = g.combine(vn.rand(g, -0.3, 0.3, seed, 13), 1.0, 0.0)
        rot = vn.orient(g, d.out, nrm)
        size = g.math("MULTIPLY", ln, g.math("MULTIPLY", g.math("SUBTRACT", 1.0, g.math("MULTIPLY", f, 0.45)),
                                             vn.rand(g, 0.85, 1.15, seed, 14)))
    with g.frame("Pointed leaf instances, tinted orange with nk_rand"):
        lf = g.group(leaf(), Length=1.0, Width=wd, **{"Widest At": 0.42, "Fold": pl.get("fold", 0.4), "Curl": pl.get("curl", 0.25),
                                                      "Resolution": 8})["Mesh"]
        lf = _leaf_uv(g, lf, 1.0)
        inst = g.node("GeometryNodeInstanceOnPoints", Points=pts["Points"], Instance=lf, Rotation=rot,
                      Scale=g.combine(size, g.math("MULTIPLY", size, vn.rand(g, 0.6, 1.25, seed, 16)),
                                      g.math("MULTIPLY", size, vn.rand(g, 0.7, 1.6, seed, 17))).out)["Instances"]
        inst = vn.store(g, inst, "nk_color", tint, dtype="FLOAT_COLOR",
                        domain="INSTANCE")
        inst = vn.store(g, inst, "nk_rand", vn.rand(g, 0.0, 1.0, seed, 15), domain="INSTANCE")
    g.output("Geometry", "GEOMETRY", vn.join(g, inst, stem), desc="Leaves (instances) and stem")
    return g.finish()


def _place(g, mesh, base, tip):
    """Move a mesh built along +Z from the origin so it runs from ``base`` toward ``tip``."""
    d = [t - b for t, b in zip(tip, base)]
    rot = g.node("FunctionNodeAlignRotationToVector", props={"axis": "Z", "pivot_axis": "AUTO"}, Vector=d)
    return g.node("GeometryNodeTransform", Geometry=mesh, Translation=base, Rotation=rot["Rotation"])["Geometry"]


def _tint(g, mesh, rgb, seed, k):
    mesh = vn.store(g, mesh, "nk_color", vn.colour(rgb), dtype="FLOAT_COLOR")
    return vn.store(g, mesh, "nk_rand", vn.rand(g, 0.0, 1.0, seed, k, ident=0))


def _stem(g, a, b):
    line = g.node("GeometryNodeCurveQuadraticBezier", Resolution=8, Start=a,
                  Middle=[(x + y) / 2 + (0.01 if i == 1 else 0) for i, (x, y) in enumerate(zip(a, b))], End=b)
    return vn.tube(g, line["Curve"], 0.0022, 5)


@once
def seed_heads():
    g = Graph("Garden Vase Seed Heads",
              description="Seed heads of the arrangement at fitted positions: tan ball, grey-white rough bloom, "
                          "cream spiral shell cone, two dark scaly cones, each on a thin stem from the mouth")
    hs = g.input("Head Scale", "FLOAT", 1.0, min=0.3, max=2.5, desc="Multiplier on every head's size")
    rough = g.input("Roughness Detail", "FLOAT", 1.6, min=0.0, max=3.0,
                    desc="Strength of the bloom's lumps and the cones' scales")
    seed = g.input("Seed", "INT", 0, min=0, max=10000, desc="Random seed")
    mouth = (0.0, 0.0, 1.02)
    with g.frame("Ball: smooth tan sphere"):
        bp = AP.get("ball", {})
        ball = g.node("GeometryNodeMeshUVSphere", Segments=32, Rings=16,
                      Radius=g.math("MULTIPLY", hs, bp.get("radius", 0.033)))["Mesh"]
        ball = vn.xf(g, vn.smooth(g, ball), t=tuple(bp.get("centre", (0.23, 0.04, 1.18))))
        ball = _tint(g, ball, bp.get("color", (215, 165, 120)), seed, 21)
    with g.frame("Bloom: icosphere pushed out by fine noise (a rough dried flower head)"):
        blp = AP.get("bloom", {})
        bl = g.node("GeometryNodeMeshIcoSphere", Subdivisions=4,
                    Radius=g.math("MULTIPLY", hs, blp.get("radius", 0.03)))["Mesh"]
        nz = g.node("ShaderNodeTexNoise", Scale=90.0, Detail=3.0)["Fac"]
        off = g.vmath("SCALE", g.node("GeometryNodeInputNormal")["Normal"],
                      scale=g.math("MULTIPLY", g.math("SUBTRACT", nz, 0.45), g.math("MULTIPLY", rough, 0.012)))
        bl = vn.store(g, bl, "vase_mottle", g.map_range(nz, 0.6, 0.35, 0.0, 0.7).out)
        bl = g.node("GeometryNodeSetPosition", Geometry=bl, Offset=off.out)["Geometry"]
        bl = vn.xf(g, vn.smooth(g, bl), t=tuple(blp.get("centre", (0.066, 0.011, 1.241))))
        bl = _tint(g, bl, blp.get("color", (205, 200, 190)), seed, 22)
    with g.frame("Shell: cone whose radius steps along a spiral (fract of angle + turns along height)"):
        sp = AP.get("shell", {})
        sb, st = sp.get("base", (0.012, 0, 1.225)), sp.get("tip", (0.02, 0.006, 1.298))
        slen = math.dist(sb, st)
        cone = g.node("GeometryNodeMeshCone", Vertices=48, **{"Side Segments": 32, "Radius Top": 0.0,
                                                               "Radius Bottom": 1.0, "Depth": 1.0})["Mesh"]
        p = g.separate(g.node("GeometryNodeInputPosition"))
        t = g.math("ADD", p["Z"], 0.5)
        ang = g.math("DIVIDE", g.math("ARCTAN2", p["Y"], p["X"]), vn.TAU)
        ridge = g.math("FRACT", g.math("MULTIPLY_ADD", t, sp.get("turns", 4.0), ang))
        rr = g.math("MULTIPLY", g.math("MULTIPLY", hs, sp.get("radius", 0.014)),
                    g.math("MULTIPLY_ADD", g.math("POWER", ridge, 0.6), 0.35, 0.7))
        rr = g.math("MULTIPLY", rr, g.math("POWER", g.math("SUBTRACT", 1.0, t), 0.6))
        cone = vn.store(g, cone, "vase_root", g.math("MULTIPLY", g.math("POWER", g.math("SUBTRACT", 1.0, ridge), 4.0), 0.6))
        sh = g.node("GeometryNodeSetPosition", Geometry=cone, Position=g.combine(
            g.math("MULTIPLY", p["X"], rr), g.math("MULTIPLY", p["Y"], rr),
            g.math("MULTIPLY", t, g.math("MULTIPLY", hs, slen))))["Geometry"]
        sh = _place(g, vn.smooth(g, sh), sb, st)
        sh = _tint(g, sh, sp.get("color", (222, 196, 152)), seed, 23)
    with g.frame("Striped pods: flattened pointed ovoids with chevron stripes (vase_stripe) and fine scales"):
        cones = []
        for i, cp in enumerate(AP.get("cones", [])):
            clen = math.dist(cp["base"], cp["tip"])
            sph = g.node("GeometryNodeMeshUVSphere", Segments=32, Rings=24, Radius=1.0)["Mesh"]
            q = g.separate(g.node("GeometryNodeInputPosition"))
            t = g.math("MULTIPLY", g.math("ADD", q["Z"], 1.0), 0.5)
            taper = g.math("MULTIPLY", g.math("POWER", g.math("SUBTRACT", 1.0, t, clamp=True), 0.55), 1.35)
            stripe = g.math("GREATER_THAN", g.math("FRACT", g.math("MULTIPLY_ADD", t, 9.0, g.math(
                "MULTIPLY", g.math("ABSOLUTE", q["X"]), 0.9))), 0.55)
            sph = vn.store(g, sph, "vase_stripe", stripe)
            sph = g.node("GeometryNodeSetPosition", Geometry=sph, Position=g.combine(
                g.math("MULTIPLY", q["X"], taper), g.math("MULTIPLY", g.math("MULTIPLY", q["Y"], taper), 0.55),
                g.math("ADD", q["Z"], 1.0)))["Geometry"]
            sph = vn.xf(g, sph, s=g.combine(g.math("MULTIPLY", hs, cp["radius"]), g.math("MULTIPLY", hs, cp["radius"]),
                                            g.math("MULTIPLY", hs, clen / 2)))
            vor = g.node("ShaderNodeTexVoronoi", props={"feature": "F1"}, Scale=220.0)["Distance"]
            off = g.vmath("SCALE", g.node("GeometryNodeInputNormal")["Normal"],
                          scale=g.math("MULTIPLY", g.math("SUBTRACT", 0.3, vor), g.math("MULTIPLY", rough, 0.003)))
            sph = g.node("GeometryNodeSetPosition", Geometry=sph, Offset=off.out)["Geometry"]
            sph = _place(g, vn.smooth(g, sph), cp["base"], cp["tip"])
            cones.append(_tint(g, sph, AP.get("cone_color", (105, 78, 52)), seed, 24 + i))
    with g.frame("Stems from the mouth to each head"):
        tips = [AP.get("ball", {}).get("centre", (0.23, 0.04, 1.18)), sb] + [c["base"] for c in AP.get("cones", [])]
        tips.append(AP.get("bloom", {}).get("centre", (0.066, 0.011, 1.241)))
        stems = vn.join(g, *[_stem(g, (mouth[0] + 0.01 * k, mouth[1], mouth[2]), tuple(tp))
                             for k, tp in enumerate(tips)])
        stems = _tint(g, stems, AP.get("stem_color", (95, 65, 40)), seed, 30)
    g.output("Geometry", "GEOMETRY", vn.join(g, ball, bl, sh, *cones, stems), desc="All seed heads and stems")
    return g.finish()


@once
def arrangement():
    g = Graph("Garden Vase Dried Arrangement",
              description="The dried arrangement in its plane frame (X along the plane, Y toward the hero view, Z "
                          "world height): palm fan in front, pod fronds, seed heads; material set to dry plant")
    seed = g.input("Seed", "INT", 0, min=0, max=10000, desc="Random seed")
    blades = g.input("Fan Blades", "INT", AP.get("fan", {}).get("blades", 24), min=3, max=60,
                     desc="Number of palm fan blades")
    density = g.input("Pod Density", "FLOAT", 1.0, min=0.2, max=3.0, desc="Multiplier on leaves per frond")
    with g.frame("Palm fan"):
        fan = g.group(fan_palm(), Blades=blades, Seed=seed)["Geometry"]
    with g.frame("Pod fronds from the fitted stem curves"):
        fronds = []
        for i, fr in enumerate(AP.get("fronds", [])):
            cnt = g.math("ROUND", g.math("MULTIPLY", density, float(fr.get("leaves", 10))))
            col = vn.colour(fr.get("color", AP.get("pod_leaf", {}).get("color", (205, 140, 90))))
            fronds.append(g.group(pod_frond(), Start=tuple(fr["start"]), Middle=tuple(fr["mid"]),
                                  End=tuple(fr["end"]), Leaves=cnt, Color=col,
                                  Seed=g.math("ADD", seed, 101.0 * (i + 1)))["Geometry"])
    with g.frame("Seed heads; join everything and set the dry plant material"):
        heads = g.group(seed_heads(), Seed=seed)["Geometry"]
        balls = g.group(vase_balls.seed_balls(), Seed=seed)["Geometry"]
        twig = g.group(vase_twigs.twigs(), Seed=seed)["Geometry"]
        geo = vn.join(g, fan, *fronds, heads, balls, twig)
        geo = g.node("GeometryNodeSetMaterial", Geometry=geo, Material=vase_materials.plant_material())["Geometry"]
    g.output("Geometry", "GEOMETRY", geo, desc="The arrangement (plane frame)")
    return g.finish()

"""Garden tree shaders: bark (fissured plates, silvery patches, lichen) and leaf (midrib, veins, translucency).

Both are SHADER node groups built with nodekit (described inputs, frames) and wrapped in a material that only
holds the group and the output. Colours are sRGB splat measurements from data/params/tree.json (bark_srgb,
crown.median_srgb) and include overcast lighting, so they are starting points tuned by render comparison.

Attributes written by Geometry Nodes and read here:
  nk_fissure  (point, 0..1)  1 in a bark fissure, 0 on a plate; same Voronoi field that displaced the mesh
  nk_bark     (point, vec)   bark-space coordinate (around, around, along/stretch) in metres
  nk_lichen   (point, 0..1)  Weathering control of the tree
  nk_leafuv   (point, vec)   leaf space: x 0..1 base->tip, y -1..1 across the blade
  nk_rand     (instance)     per-leaf random 0..1
"""
from nodekit.graph import Graph, once

from garden.util import load_params, srgb_to_linear


def _attr(g, name, kind="GEOMETRY"):
    return g.node("ShaderNodeAttribute", props={"attribute_type": kind, "attribute_name": name})


@once
def bark_shader():
    p = load_params("tree").get("bark_srgb", {})
    g = Graph("Garden Tree Bark Shader", kind="SHADER",
              description="Grey-brown bark: dark vertical fissures (nk_fissure from GN), fine vertical streaks and "
                          "silvery-grey strips stretched along the stem, very sparse neutral-grey lichen "
                          "(nk_lichen), base dirt/algae streaks, grime-filled fissures, pale peeling flakes (nk_flake) and dark scars (nk_scar), sharp fine bump")
    dark = g.input("Fissure Color", "COLOR", srgb_to_linear(p.get("p10", [31, 25, 12])),
                   desc="Colour deep in the fissures (measured p10 bark splat colour)")
    base = g.input("Plate Color", "COLOR", srgb_to_linear([c * k for c, k in zip(p.get("p50", [68, 59, 45]),
                                                                                   (0.84, 0.68, 0.34))]),
                   desc="Main dark brown of the bark (measured median bark splat colour x0.84 R / x0.68 G / x0.34 B, "
                        "fitted on close_trunk: d3 trunk median (62,54,43) vs reference (57,46,29))")
    pale = g.input("Weathered Color", "COLOR", srgb_to_linear([98, 88, 70]),
                   desc="Pale grey-brown peeling strips (between measured p90 and p97, warmed; no blue)")
    lichen_c = g.input("Lichen Color", "COLOR", srgb_to_linear([100, 98, 90]), desc="Neutral grey lichen tint")
    pale_amt = g.input("Weathered Amount", "FLOAT", 0.35, min=0.0, max=1.0, subtype="FACTOR",
                       desc="Share of the bark covered by silvery strips")
    grime = g.input("Grime Color", "COLOR", srgb_to_linear([24, 19, 12]),
                    desc="Dirt-filled fissure colour (darker than the p10 splat colour)")
    algae = g.input("Algae Color", "COLOR", srgb_to_linear([34, 36, 22]),
                    desc="Green-black algae and soil splash near the base")
    dirt_amt = g.input("Dirt", "FLOAT", 0.7, min=0.0, max=1.0, subtype="FACTOR",
                       desc="Strength of base dirt and algae streaks")
    bump_s = g.input("Bump", "FLOAT", 0.8, min=0.0, max=2.0, desc="Strength of the fine bark bump")
    with g.frame("Bark-space coordinates (z = along/stretch) and vertically stretched streak fields"):
        fis = _attr(g, "nk_fissure")["Fac"]
        bv = _attr(g, "nk_bark")["Vector"]
        lich = _attr(g, "nk_lichen")["Fac"]
        sv = g.vmath("MULTIPLY", bv, (1.0, 1.0, 0.3))["Vector"]
        streak = g.node("ShaderNodeTexNoise", Vector=sv, Scale=70.0, Detail=4.0, Roughness=0.6)["Fac"]
        strip = g.node("ShaderNodeTexNoise", Vector=sv, Scale=16.0, Detail=3.0, Roughness=0.5)["Fac"]
        flake = g.node("ShaderNodeTexVoronoi", props={"feature": "DISTANCE_TO_EDGE"},
                       Vector=g.vmath("MULTIPLY", bv, (1.0, 1.0, 0.5))["Vector"], Scale=45.0)["Distance"]
        micro = g.math("SUBTRACT", 1.0, g.map_range(flake, 0.0, 0.12, 0.0, 1.0, interp="SMOOTHSTEP"),
                       label="soft flaky plate edges")
        breakup = g.node("ShaderNodeTexNoise", Vector=bv, Scale=60.0, Detail=2.0)["Fac"]
        zpos = g.separate(g.node("ShaderNodeNewGeometry")["Position"])["Z"]
        algae_n = g.node("ShaderNodeTexNoise", Vector=g.vmath("MULTIPLY", bv, (1.0, 1.0, 0.12))["Vector"],
                         Scale=22.0, Detail=3.0)["Fac"]
    with g.frame("Colour: grey-brown with fine vertical streaks, silvery strips, rare lichen, dark fissures"):
        pale_m = g.map_range(strip, g.math("SUBTRACT", 0.64, g.math("MULTIPLY", pale_amt, 0.2)), 0.7, 0.0, 1.0,
                             interp="SMOOTHSTEP", label="silvery strip mask")
        pale_m = g.math("MULTIPLY", pale_m, g.map_range(breakup, 0.45, 0.6, 0.0, 1.0), label="broken into flakes")
        plate = g.mix(g.math("MULTIPLY", pale_m, 0.8), base, pale, data_type="RGBA")["Result"]
        fib = g.node("ShaderNodeTexNoise", Vector=g.vmath("MULTIPLY", bv, (1.0, 1.0, 0.08))["Vector"], Scale=160.0,
                     Detail=2.0, label="hair-fine fibres")["Fac"]
        sdark = g.math("ADD", g.map_range(streak, 0.35, 0.65, 0.0, 0.45),
                       g.map_range(fib, 0.5, 0.7, 0.0, 0.3), label="streak + fibre darkening")
        plate = g.mix(sdark, plate, dark, data_type="RGBA")["Result"]
        lnoise = g.node("ShaderNodeTexNoise", Vector=bv, Scale=14.0, Detail=3.0)["Fac"]
        lmask = g.math("MULTIPLY", g.map_range(lnoise, 0.7, 0.74, 0.0, 1.0, interp="SMOOTHSTEP"), lich)
        plate = g.mix(lmask, plate, lichen_c, data_type="RGBA")["Result"]
        darkness = g.math("MAXIMUM", fis, g.math("MULTIPLY", micro, 0.2), label="fissure or flake edge")
        col = g.mix(darkness, plate, grime, data_type="RGBA")["Result"]
    with g.frame("Dirt: soil splash and green-black algae streaks rising from the base, grime in fissures"):
        base_m = g.map_range(zpos, 0.15, 0.95, 1.0, 0.0, interp="SMOOTHSTEP", label="near the soil")
        streaks = g.map_range(algae_n, 0.4, 0.65, 0.0, 1.0, label="vertical algae streaks")
        dirt = g.math("MULTIPLY", g.math("MULTIPLY", base_m, g.math("ADD", 0.35, g.math("MULTIPLY", streaks, 0.65))),
                      dirt_amt)
        col = g.mix(dirt, col, algae, data_type="RGBA")["Result"]
    with g.frame("Peeling flakes (nk_flake instances) pale on some, scars/knots (nk_scar) dark"):
        flk = _attr(g, "nk_flake", "INSTANCER")["Fac"]
        frnd = _attr(g, "nk_rand", "INSTANCER")["Fac"]
        fpale = g.math("MULTIPLY", flk, g.map_range(frnd, 0.5, 0.95, 0.0, 0.45), label="flake paleness")
        col = g.mix(fpale, col, pale, data_type="RGBA")["Result"]
        scar = _attr(g, "nk_scar")["Fac"]
        col = g.mix(g.math("MULTIPLY", scar, 1.0), col, g.mix(0.4, dark, (0.006, 0.004, 0.002, 1.0),
                                                                data_type="RGBA")["Result"], data_type="RGBA")["Result"]
    with g.frame("Roughness, bump and BSDF"):
        rough = g.map_range(fis, 0.0, 1.0, 0.8, 0.97)
        h = g.math("SUBTRACT", g.math("MULTIPLY", streak, 0.5), g.math("ADD", fis, g.math("MULTIPLY", micro, 0.25)))
        bump = g.node("ShaderNodeBump", Strength=bump_s, Distance=0.003, Height=h)["Normal"]
        bsdf = g.node("ShaderNodeBsdfPrincipled", **{"Base Color": col, "Roughness": rough, "Normal": bump})
    g.output("Shader", "SHADER", bsdf["BSDF"], desc="Bark BSDF")
    return g.finish()


@once
def leaf_shader():
    crown = load_params("tree").get("crown", {})
    g = Graph("Garden Tree Leaf Shader", kind="SHADER",
              description="Leaf: per-leaf hue/value variation (nk_rand), paler midrib and side veins from "
                          "nk_leafuv, yellower tip, roughness variation, mixed with translucency")
    leaf_c = g.input("Leaf Color", "COLOR", srgb_to_linear([min(255, v * 1.3) for v in crown.get("median_srgb", [53, 72, 29])]),
                     desc="Mean leaf colour (measured median crown foliage splat colour x1.3: the splat colour is mostly the shaded crown underside)")
    var = g.input("Color Variation", "FLOAT", 0.25, min=0.0, max=1.0, subtype="FACTOR",
                  desc="Per-leaf value/hue variation")
    trans = g.input("Translucency", "FLOAT", 0.3, min=0.0, max=1.0, subtype="FACTOR",
                    desc="Share of light transmitted through the blade")
    with g.frame("Leaf space: midrib, veins and tip"):
        uv = g.separate(_attr(g, "nk_leafuv")["Vector"])
        rnd = _attr(g, "nk_rand", "INSTANCER")["Fac"]
        av = g.math("ABSOLUTE", uv["Y"])
        midrib = g.math("SUBTRACT", 1.0, g.map_range(av, 0.0, 0.07, 0.0, 1.0, interp="SMOOTHSTEP"))
        vein_p = g.math("SINE", g.math("MULTIPLY", g.math("SUBTRACT", uv["X"], g.math("MULTIPLY", av, 0.6)), 40.0))
        veins = g.math("MULTIPLY", g.map_range(vein_p, 0.75, 1.0, 0.0, 1.0), g.math("SUBTRACT", 1.0, av))
        tip = g.map_range(uv["X"], 0.6, 1.0, 0.0, 1.0, interp="SMOOTHSTEP")
    with g.frame("Colour per leaf, veins paler, tips yellower"):
        hsv = g.node("ShaderNodeHueSaturation", Hue=g.math("ADD", 0.5, g.math("MULTIPLY", g.math(
            "SUBTRACT", rnd, 0.5), g.math("MULTIPLY", var, 0.12))), Saturation=1.0,
                     Value=g.math("ADD", 1.0, g.math("MULTIPLY", g.math("SUBTRACT", rnd, 0.5), var)), Color=leaf_c)
        c = g.mix(g.math("MULTIPLY", g.math("MAXIMUM", midrib, g.math("MULTIPLY", veins, 0.5)), 0.45), hsv["Color"],
                  (0.32, 0.36, 0.12, 1.0), data_type="RGBA")["Result"]
        c = g.mix(g.math("MULTIPLY", tip, 0.25), c, (0.16, 0.16, 0.03, 1.0), data_type="RGBA")["Result"]
    with g.frame("Waxy-to-matt roughness, translucent mix"):
        rough = g.map_range(rnd, 0.0, 1.0, 0.6, 0.72, label="matt: limits white sky specular")
        bsdf = g.node("ShaderNodeBsdfPrincipled", **{"Base Color": c, "Roughness": rough,
                                                     "Specular IOR Level": 0.25, "Specular Tint": c})
        tr = g.node("ShaderNodeBsdfTranslucent", Color=g.mix(0.5, c, (0.25, 0.3, 0.02, 1.0),
                                                              data_type="RGBA")["Result"])
        sh = g.node("ShaderNodeMixShader", Fac=trans)
        g.connect(bsdf["BSDF"], sh.b.inputs[1])
        g.connect(tr["BSDF"], sh.b.inputs[2])
    g.output("Shader", "SHADER", sh["Shader"], desc="Leaf shader")
    return g.finish()


def _wrap(name, group):
    import bpy
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    gn = nt.nodes.new("ShaderNodeGroup")
    gn.node_tree = group
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (300, 0)
    nt.links.new(gn.outputs[0], out.inputs["Surface"])
    return m


def materials():
    _wrap("Garden Tree Bark", bark_shader())
    leaf = _wrap("Garden Tree Leaf", leaf_shader())
    leaf.use_backface_culling = False

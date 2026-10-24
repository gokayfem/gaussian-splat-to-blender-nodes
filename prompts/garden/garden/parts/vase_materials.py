"""Procedural shaders for the vase: rough mottled gourd/ceramic vessel and matte dried plant material.

Vessel reads vase_local (cos phi, sin phi, height fraction) and vase_wear from Geometry Nodes. Dry plant reads
nk_color (per piece tint), nk_rand, vase_uv (leaf u root->tip, v across) and vase_root ((1-u)^2, 0 on non-leaves).
Colours are sRGB picks from the reference renders (they include overcast light), converted to linear.
"""
import bpy

from garden.util import new_material, srgb_to_linear

VESSEL = "Garden Vase Vessel"
PLANT = "Garden Vase Dry Plant"


class _N:
    """Tiny helper over a material node tree: new(type, **inputs), link, attr, math, mix, ramp."""

    def __init__(self, nodes, links):
        self.nodes, self.links = nodes, links

    def _set(self, sock, v):
        if hasattr(v, "is_output"):
            self.links.new(v, sock)
        else:
            sock.default_value = v

    def new(self, idname, props=None, **inputs):
        node = self.nodes.new(idname)
        for k, v in (props or {}).items():
            setattr(node, k, v)
        for k, v in inputs.items():
            self._set(node.inputs[k], v)
        return node

    def link(self, a, b):
        self.links.new(a, b)

    def attr(self, name, out="Fac"):
        a = self.new("ShaderNodeAttribute", props={"attribute_type": "GEOMETRY", "attribute_name": name})
        return a.outputs[out]

    def math(self, op, a, b=0.0, clamp=False):
        m = self.new("ShaderNodeMath", props={"operation": op, "use_clamp": clamp})
        self._set(m.inputs[0], a)
        self._set(m.inputs[1], b)
        return m.outputs[0]

    def mix(self, fac, a, b, blend="MIX"):
        m = self.new("ShaderNodeMix", props={"data_type": "RGBA", "blend_type": blend, "clamp_result": True})
        for key, v in (("Factor", fac), ("A", a), ("B", b)):
            self._set(next(s for s in m.inputs if s.name == key and s.enabled), v)
        return next(s for s in m.outputs if s.name == "Result" and s.enabled)

    def ramp(self, fac, lo, hi):
        """Linear 0..1 ramp of fac between lo and hi (clamped; lo > hi inverts)."""
        mr = self.new("ShaderNodeMapRange", props={"clamp": True}, Value=fac, **{"From Min": lo, "From Max": hi})
        return mr.outputs["Result"]


def vessel_material():
    return bpy.data.materials[VESSEL]


def plant_material():
    return bpy.data.materials[PLANT]


def _bsdf(n, out, color, rough, normal=None):
    b = n.new("ShaderNodeBsdfPrincipled", Roughness=rough)
    n.link(color, b.inputs["Base Color"])
    if normal is not None:
        n.link(normal, b.inputs["Normal"])
    b.inputs["Specular IOR Level"].default_value = 0.3
    n.link(b.outputs["BSDF"], out.inputs["Surface"])
    return b


def _vessel(p):
    c = p.get("colors", {})
    m, nodes, links, out = new_material(VESSEL)
    n = _N(nodes, links)
    loc = n.attr("vase_local", "Vector")
    wear = n.attr("vase_wear")
    co = n.new("ShaderNodeVectorMath", props={"operation": "MULTIPLY"}, Vector=loc)
    co.inputs[1].default_value = (0.15, 0.15, 0.29)  # back to metres-ish so noise scales are physical
    big = n.new("ShaderNodeTexNoise", Vector=co.outputs[0], Scale=5.0, Detail=3.0, Roughness=0.5)
    fine = n.new("ShaderNodeTexNoise", Vector=co.outputs[0], Scale=60.0, Detail=6.0, Roughness=0.65)
    # dark weathered patches: big noise above a threshold that drops with wear
    thr = n.math("SUBTRACT", 0.62, n.math("MULTIPLY", wear, 0.12))
    patch = n.ramp(n.math("SUBTRACT", big.outputs["Fac"], thr), -0.02, 0.14)
    base = n.mix(n.ramp(fine.outputs["Fac"], 0.3, 0.75), srgb_to_linear(c.get("vessel_dark", (98, 72, 48))),
                 srgb_to_linear(c.get("vessel_light", (150, 118, 84))))
    col = n.mix(patch, base, srgb_to_linear(c.get("vessel_patch", (62, 44, 30))))
    # slightly darker toward the base (soil/stain), lighter chalky specks
    low = n.ramp(n.new("ShaderNodeSeparateXYZ", Vector=loc).outputs["Z"], 0.2, 0.0)
    col = n.mix(n.math("MULTIPLY", low, 0.15), col, srgb_to_linear((70, 52, 36)))
    speck = n.ramp(fine.outputs["Fac"], 0.7, 0.78)
    col = n.mix(n.math("MULTIPLY", speck, 0.25), col, srgb_to_linear((178, 150, 115)))
    # the large dark stain on the +v flank (fitted: centre phi, height fraction, size in radians/height)
    dp = p.get("colors", {}).get("dark_patch", [110.0, 0.35, 0.55, 0.22])
    import math as _m
    xyz = n.new("ShaderNodeSeparateXYZ", Vector=loc)
    cdot = n.math("ADD", n.math("MULTIPLY", xyz.outputs["X"], _m.cos(_m.radians(dp[0]))),
                  n.math("MULTIPLY", xyz.outputs["Y"], _m.sin(_m.radians(dp[0]))))
    dang = n.math("DIVIDE", n.math("ARCCOSINE", n.math("MINIMUM", cdot, 1.0)), dp[2])
    dz = n.math("DIVIDE", n.math("SUBTRACT", xyz.outputs["Z"], dp[1]), dp[3])
    dd = n.math("ADD", n.math("ADD", n.math("MULTIPLY", dang, dang), n.math("MULTIPLY", dz, dz)),
                n.math("MULTIPLY", n.math("SUBTRACT", big.outputs["Fac"], 0.5), 1.2))
    stain = n.math("MULTIPLY", n.ramp(dd, 1.1, 0.3), n.math("MINIMUM", n.math("MULTIPLY", wear, 1.6), 1.0))
    col = n.mix(stain, col, srgb_to_linear(c.get("vessel_stain", (70, 50, 36))))
    # coconut-husk fibres: short pale hair-like strands -- thin ridges of a distorted noise, cut into short
    # segments by a second noise mask (so they read as scattered hairs, not long contour lines)
    fn = n.new("ShaderNodeTexNoise", Vector=co.outputs[0], Scale=55.0, Detail=3.0, Distortion=7.0)
    ridge = n.math("ABSOLUTE", n.math("SUBTRACT", fn.outputs["Fac"], 0.5))
    fibre = n.ramp(ridge, 0.016, 0.0)
    seg = n.new("ShaderNodeTexNoise", Vector=co.outputs[0], Scale=140.0, Detail=1.0)
    fibre = n.math("MULTIPLY", fibre, n.ramp(seg.outputs["Fac"], 0.5, 0.62))
    col = n.mix(n.math("MULTIPLY", fibre, p.get("colors", {}).get("fibre_amount", 0.35)), col,
                srgb_to_linear((205, 178, 140)))
    # mid-scale worn tone variation (irregular, not blotchy): redder vs greyer areas
    mid = n.new("ShaderNodeTexNoise", Vector=co.outputs[0], Scale=14.0, Detail=4.0, Roughness=0.6)
    col = n.mix(n.math("MULTIPLY", n.ramp(mid.outputs["Fac"], 0.35, 0.7), 0.6), col,
                n.mix(1.0, col, (0.8, 0.85, 0.9, 1.0), blend="MULTIPLY"))
    # dark fibrous grime: patches (mid noise) filled with dark distorted strands -- dirt held in the fibres
    gpatch = n.ramp(big.outputs["Fac"], 0.45, 0.6)
    gstr = n.new("ShaderNodeTexNoise", Vector=co.outputs[0], Scale=70.0, Detail=4.0, Distortion=1.5)
    grime = n.math("MULTIPLY", gpatch, n.ramp(gstr.outputs["Fac"], 0.42, 0.62))
    grime = n.math("MULTIPLY", grime, p.get("colors", {}).get("grime_amount", 0.7))
    col = n.mix(grime, col, srgb_to_linear(c.get("vessel_grime", (48, 34, 24))))
    # inside the side-hole tunnels: darker, as the wall section is shadowed
    col = n.mix(n.ramp(n.attr("vase_inset"), 0.0, 0.35), col, srgb_to_linear((52, 38, 27)))
    # relief at two scales: shallow dents/undulation and fine grain, plus raised fibres
    hgt = n.math("ADD", n.math("MULTIPLY", mid.outputs["Fac"], 3.0), n.math("ADD", fine.outputs["Fac"],
                                                                         n.math("MULTIPLY", fibre, 0.4)))
    bump = n.new("ShaderNodeBump", Strength=0.45, Distance=0.002, Height=hgt)
    # glossier rough husk: roughness varies 0.45-0.8 with the mid-scale tone, a little more specular
    # raised/clean areas polished (0.3), grimy patches and fibres rough (up to 0.75)
    rough = n.math("ADD", 0.28, n.math("MULTIPLY", n.ramp(mid.outputs["Fac"], 0.4, 0.65), 0.3))
    rough = n.math("ADD", rough, n.math("MULTIPLY", n.math("ADD", grime, fibre), 0.25))
    b = _bsdf(n, out, col, 0.6, bump.outputs["Normal"])
    n.link(rough, b.inputs["Roughness"])
    b.inputs["Specular IOR Level"].default_value = 0.6
    return m


def _plant(p):
    m, nodes, links, out = new_material(PLANT)
    n = _N(nodes, links)
    tint = n.attr("nk_color", "Color")
    rnd = n.attr("nk_rand")
    root = n.attr("vase_root")
    uv = n.attr("vase_uv", "Vector")
    sep = n.new("ShaderNodeSeparateXYZ", Vector=uv)
    # fibres: noise stretched along the leaf (u), fine across (v)
    fco = n.new("ShaderNodeCombineXYZ", X=n.math("MULTIPLY", sep.outputs["X"], 4.0),
                Y=n.math("MULTIPLY", sep.outputs["Y"], 90.0))
    fib = n.new("ShaderNodeTexNoise", Vector=fco.outputs[0], Scale=1.0, Detail=3.0)
    obj = n.new("ShaderNodeTexNoise", Scale=140.0, Detail=4.0)  # fine mottling on heads (object coords)
    v = n.math("ADD", n.math("MULTIPLY", n.math("SUBTRACT", fib.outputs["Fac"], 0.5), 0.45),
               n.math("MULTIPLY", n.math("SUBTRACT", obj.outputs["Fac"], 0.5), 0.25))
    v = n.math("ADD", 1.0, n.math("ADD", v, n.math("MULTIPLY", n.math("SUBTRACT", rnd, 0.5), 0.22)))
    lines = n.math("ABSOLUTE", n.math("SINE", n.math("MULTIPLY", sep.outputs["Y"], 60.0)))
    v = n.math("SUBTRACT", v, n.math("MULTIPLY", n.ramp(lines, 0.2, 0.0), 0.07))
    col = n.mix(1.0, tint, v, blend="MULTIPLY")
    dark = n.mix(1.0, tint, (0.30, 0.20, 0.13, 1.0), blend="MULTIPLY")
    col = n.mix(n.math("MULTIPLY", root, 0.85), col, dark)
    # vase_mottle (cone scales, bloom crevices): 0 = no effect, 1 = lighter scale rim
    stripe = n.attr("vase_stripe")
    col = n.mix(n.math("MULTIPLY", stripe, 0.75), col, srgb_to_linear((214, 192, 156)))
    mot = n.attr("vase_mottle")
    col = n.mix(n.math("MULTIPLY", mot, 0.35), col, srgb_to_linear((205, 175, 135)))
    # backs of the blades read darker and redder in the splat (seen from the opposite side)
    back = n.new("ShaderNodeNewGeometry").outputs["Backfacing"]
    col = n.mix(back, col, n.mix(1.0, col, (0.5, 0.34, 0.24, 1.0), blend="MULTIPLY"))
    b = _bsdf(n, out, col, 0.78)
    # very weak translucency: thin dried blades glow slightly when back-lit
    tr = n.new("ShaderNodeBsdfTranslucent")
    n.link(n.mix(1.0, col, (1.0, 0.9, 0.7, 1.0), blend="MULTIPLY"), tr.inputs["Color"])
    base_tr = p.get("arrangement", {}).get("translucency", 0.08)
    mx = n.new("ShaderNodeMixShader", Fac=n.math("ADD", base_tr, n.attr("vase_trans")))
    n.link(b.outputs["BSDF"], mx.inputs[1])
    n.link(tr.outputs["BSDF"], mx.inputs[2])
    n.link(mx.outputs["Shader"], out.inputs["Surface"])
    m.use_backface_culling = False
    return m


def build(p):
    _vessel(p)
    _plant(p)

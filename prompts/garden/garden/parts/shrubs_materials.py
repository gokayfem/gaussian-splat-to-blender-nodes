"""Procedural Shader Node materials of the shrubs part.

Garden Shrubs Leaf     per-leaf colour from nk_color (Geometry Nodes), lighter yellow-green midrib (|sh_v| small),
                       paler root / darker tip along sh_u, roughness broken up by nk_rand and noise, and a thin-leaf
                       translucency (Translucent BSDF mixed in) so back-lit leaves glow slightly.
Garden Shrubs Blossom  cream-white petals with a yellow-green centre (nk_part from NK Blossom; nk_part 2 = dark green
                       stalks of a spray), soft translucency.
"""
from garden.util import new_material


class _M:
    """Tiny helper over a material node tree: n(type, **inputs) creates and links."""

    def __init__(self, name):
        self.m, self.nodes, self.links, self.out = new_material(name)

    def n(self, bl_idname, props=None, **inputs):
        node = self.nodes.new(bl_idname)
        for k, v in (props or {}).items():
            setattr(node, k, v)
        for k, v in inputs.items():
            sock = node.inputs[k.replace("_", " ")] if not isinstance(k, int) else node.inputs[k]
            self.set(sock, v)
        return node

    def set(self, sock, v):
        if hasattr(v, "is_output") or hasattr(v, "links"):
            self.links.new(v, sock)
        else:
            sock.default_value = v

    def attr(self, name, out="Fac"):
        """Attribute from the realized mesh or, when absent there, from the instance (GN instance domain):
        a missing attribute reads as 0, so the sum of the GEOMETRY and INSTANCER lookups is whichever exists."""
        a = self.nodes.new("ShaderNodeAttribute")
        a.attribute_type, a.attribute_name = "GEOMETRY", name
        b = self.nodes.new("ShaderNodeAttribute")
        b.attribute_type, b.attribute_name = "INSTANCER", name
        if out == "Color":
            return self.mix_rgb(1.0, a.outputs[out], b.outputs[out], blend="ADD")
        return self.math("MAXIMUM", a.outputs[out], b.outputs[out])

    def math(self, op, a, b=0.0, c=0.0, clamp=False):
        node = self.nodes.new("ShaderNodeMath")
        node.operation, node.use_clamp = op, clamp
        for i, v in enumerate((a, b, c)):
            self.set(node.inputs[i], v)
        return node.outputs[0]

    def mix_rgb(self, fac, a, b, blend="MIX"):
        node = self.nodes.new("ShaderNodeMix")
        node.data_type, node.blend_type = "RGBA", blend
        self.set(node.inputs["Factor"], fac)
        self.set(node.inputs[6], a)
        self.set(node.inputs[7], b)
        return node.outputs[2]


def leaf_material(name="Garden Shrubs Leaf"):
    M = _M(name)
    col = M.attr("nk_color", "Color")
    rnd = M.attr("nk_rand")
    u, v = M.attr("sh_u"), M.attr("sh_v")
    # midrib: 1 on the rib, 0 a little away from it
    rib = M.math("SUBTRACT", 1.0, M.math("MINIMUM", M.math("DIVIDE", M.math("ABSOLUTE", v), 0.09), 1.0))
    rib = M.math("MULTIPLY", rib, M.math("SUBTRACT", 1.0, M.math("MULTIPLY", u, 0.8)))
    # paler, yellower root; slightly darker tip. All tints are relative to nk_color (multiplies), so the
    # fitted per-piece colour fully drives the leaf (constant tints had been washing it out).
    root_tint = M.mix_rgb(1.0, col, (1.3, 1.35, 0.8, 1.0), blend="MULTIPLY")
    base = M.mix_rgb(M.math("POWER", M.math("SUBTRACT", 1.0, u), 3.0), col, root_tint)
    base = M.mix_rgb(M.math("MULTIPLY", M.math("POWER", u, 2.0), 0.25), base, (0.0, 0.0, 0.0, 1.0))
    ribc = M.mix_rgb(1.0, col, (1.5, 1.6, 1.0, 1.0), blend="MULTIPLY")
    base = M.mix_rgb(M.math("MULTIPLY", rib, 0.55), base, ribc)
    # fine vein mottling from object-space noise
    tc = M.n("ShaderNodeTexCoord")
    nz = M.n("ShaderNodeTexNoise", Vector=tc.outputs["Object"], Scale=60.0, Detail=2.0)
    mott = M.math("MULTIPLY_ADD", nz.outputs["Fac"], 0.25, 0.88)
    base = M.mix_rgb(1.0, base, M.n("ShaderNodeCombineColor", Red=mott, Green=mott, Blue=mott).outputs[0],
                     blend="MULTIPLY")
    rough = M.math("MULTIPLY_ADD", rnd, 0.15, M.math("MULTIPLY_ADD", nz.outputs["Fac"], 0.1, 0.55))  # matte leaf: 0.55..0.8
    # per-leaf value (sh_lv, branch leaves only): bright / mid / shaded leaves; 1 where absent
    lv = M.attr("sh_lv")
    lv = M.math("ADD", lv, M.math("LESS_THAN", lv, 0.01))
    base = M.mix_rgb(1.0, base, M.n("ShaderNodeCombineColor", Red=lv, Green=lv, Blue=lv).outputs[0],
                     blend="MULTIPLY")
    bsdf = M.n("ShaderNodeBsdfPrincipled", Base_Color=base, Roughness=rough)
    # Specular: low and tinted fully to the leaf colour (white specular reflecting the bright sky greyed the
    # foliage); sunlit front-spray leaves (sh_lv > 1, branch tips) keep a little waxy, glossier highlight.
    wax = M.math("MINIMUM", M.math("MAXIMUM", M.math("MULTIPLY", M.math("SUBTRACT", lv, 1.0), 2.0), 0.0), 1.0)
    M.links.new(M.math("MULTIPLY_ADD", wax, 0.25, 0.2), bsdf.inputs["Specular IOR Level"])
    M.links.new(M.math("SUBTRACT", rough, M.math("MULTIPLY", wax, 0.3)), bsdf.inputs["Roughness"])
    M.links.new(M.mix_rgb(1.0, base, (2.5, 2.5, 2.5, 1.0), blend="MULTIPLY"), bsdf.inputs["Specular Tint"])
    trans_col = M.mix_rgb(1.0, base, (1.1, 1.4, 0.5, 1.0), blend="MULTIPLY")
    tr = M.n("ShaderNodeBsdfTranslucent", Color=trans_col)
    mix = M.n("ShaderNodeMixShader", Fac=0.18)
    M.links.new(bsdf.outputs[0], mix.inputs[1])
    M.links.new(tr.outputs[0], mix.inputs[2])
    M.links.new(mix.outputs[0], M.out.inputs["Surface"])
    return M.m


def blossom_material(name="Garden Shrubs Blossom"):
    M = _M(name)
    part = M.attr("nk_part")
    rnd = M.attr("nk_rand")
    petal = M.mix_rgb(rnd, (0.78, 0.78, 0.72, 1.0), (0.85, 0.82, 0.74, 1.0))
    base = M.mix_rgb(M.math("MINIMUM", part, 1.0), petal, (0.55, 0.5, 0.12, 1.0))
    # nk_part 2 = the thin stalks of a spray: dark green
    base = M.mix_rgb(M.math("GREATER_THAN", part, 1.5), base, (0.03, 0.07, 0.015, 1.0))
    bsdf = M.n("ShaderNodeBsdfPrincipled", Base_Color=base, Roughness=0.55)
    tr = M.n("ShaderNodeBsdfTranslucent", Color=petal)
    mix = M.n("ShaderNodeMixShader", Fac=0.2)
    M.links.new(bsdf.outputs[0], mix.inputs[1])
    M.links.new(tr.outputs[0], mix.inputs[2])
    M.links.new(mix.outputs[0], M.out.inputs["Surface"])
    return M.m

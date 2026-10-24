"""Procedural shader materials for the ground: paver concrete, earth (joint bed / lawn soil / terrace soil), grass,
needle litter, moss, path concrete and the ground-light steel and lens.

Colours are calibrated against the hero/overview reference renders (sRGB, overcast light), not scan albedo.
"""
import math

from garden.util import load_params, srgb_to_linear

LOOK = {
    "paver": (198, 188, 176), "paver_dark": (78, 68, 54), "paver_stain": (120, 96, 66),
    "paver_algae": (118, 122, 88), "paver_grain": (118, 110, 100), "paver_pale": (238, 234, 228),
    "paver_grey": (148, 140, 130), "stain_warm": (150, 126, 98), "stain_cool": (138, 138, 134), "wet_edge": (112, 98, 80), "paver_south": (110, 98, 82),
    "joint_soil": (92, 78, 60), "joint_moss": (86, 96, 42), "joint_litter": (120, 82, 50),
    "lawn_soil": (92, 94, 46), "terrace_soil": (52, 40, 30),
    "grass_root": (118, 140, 34), "grass_tip": (196, 214, 86), "grass_dry": (200, 190, 100),
    "litter": (126, 94, 66), "twig": (132, 104, 76), "leaf_litter": (96, 80, 64), "weed_leaf": (72, 104, 34), "mat_dark": (88, 66, 46), "paver_warm": (214, 196, 178), "paver_cool": (190, 190, 186), "moss": (66, 78, 32), "path": (104, 94, 80), "steel": (190, 190, 186),
}
LOOK.update(load_params("ground").get("look", {}))


def lin(key):
    return srgb_to_linear(LOOK[key])


class Shader:
    """Tiny helper over a material node tree: n(type, **inputs), with sockets/values linked or set by name."""

    def __init__(self, name):
        from garden.util import new_material
        self.m, self.nodes, self.links, self.out = new_material(name)

    def n(self, idname, props=None, **inputs):
        node = self.nodes.new(idname)
        for k, v in (props or {}).items():
            setattr(node, k, v)
        for k, v in inputs.items():
            self.set(node.inputs[k.replace("_", " ")], v)
        return node

    def set(self, sock, v):
        if hasattr(v, "is_output") or hasattr(v, "links"):
            self.links.new(v, sock)
        elif hasattr(v, "outputs"):
            self.links.new(v.outputs[0], sock)
        else:
            sock.default_value = v

    def math(self, op, a, b=0.0, c=None):
        node = self.n("ShaderNodeMath", {"operation": op})
        self.set(node.inputs[0], a)
        self.set(node.inputs[1], b)
        if c is not None:
            self.set(node.inputs[2], c)
        return node.outputs[0]

    def mixc(self, fac, a, b, blend="MIX"):
        node = self.n("ShaderNodeMix", {"data_type": "RGBA", "blend_type": blend, "clamp_factor": True})
        self.set(node.inputs["Factor"], fac)
        self.set(node.inputs[6], a)
        self.set(node.inputs[7], b)
        return node.outputs[2]

    def ramp(self, v, a, b):
        node = self.n("ShaderNodeMapRange", {"interpolation_type": "SMOOTHSTEP"})
        self.set(node.inputs["Value"], v)
        self.set(node.inputs["From Min"], a)
        self.set(node.inputs["From Max"], b)
        return node.outputs[0]

    def attr(self, name, kind="GEOMETRY"):
        return self.n("ShaderNodeAttribute", {"attribute_name": name, "attribute_type": kind}).outputs["Fac"]

    def noise(self, vec, scale, detail=4.0, rough=0.55):
        return self.n("ShaderNodeTexNoise", Vector=vec, Scale=scale, Detail=detail, Roughness=rough).outputs["Fac"]

    def bsdf(self, color, rough, normal=None, **extra):
        b = self.n("ShaderNodeBsdfPrincipled", Base_Color=color, Roughness=rough, **extra)
        if normal is not None:
            self.set(b.inputs["Normal"], normal)
        self.links.new(b.outputs[0], self.out.inputs["Surface"])
        return b

    def bump(self, h, strength, dist=0.01):
        return self.n("ShaderNodeBump", Strength=strength, Distance=dist, Height=h).outputs["Normal"]

    def tone(self, col, k):
        return self.mixc(1.0, col, (k, k, k, 1.0), "MULTIPLY") if isinstance(k, float) else \
            self.mixc(1.0, col, self.n("ShaderNodeCombineColor", Red=k, Green=k, Blue=k).outputs[0], "MULTIPLY")


def _hex_edge_distance(s, obj):
    """Distance to the slab's own hex outline in object space (cylinder vertex 0 on +X: flat normals at 30/90/150
    degrees); 0.215 m across flats / 2 minus the max projection."""
    sep = s.n("ShaderNodeSeparateXYZ", Vector=obj)
    projs = []
    for deg in (30.0, 90.0, 150.0):
        c, sn = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        projs.append(s.math("ABSOLUTE", s.math("MULTIPLY_ADD", sep.outputs[0], c,
                                               s.math("MULTIPLY", sep.outputs[1], sn))))
    hx = s.math("MAXIMUM", projs[0], s.math("MAXIMUM", projs[1], projs[2]))
    return s.math("SUBTRACT", 0.2155, hx)


def paver():
    """Concrete paver at three scales: per-stone warm/cool weathering; stains, grime blotches, pits and selective edge
    dirt; fine bright/dark aggregate grain. Damp patches are smoother so they pick up sky sheen."""
    s = Shader("Garden Ground Paver")
    obj = s.n("ShaderNodeTexCoord").outputs["Object"]
    world = s.n("ShaderNodeNewGeometry").outputs["Position"]
    rnd = s.attr("nk_rand", "INSTANCER")
    edge_w = s.attr("gr_edge", "INSTANCER")
    ed = _hex_edge_distance(s, obj)
    shifted = s.n("ShaderNodeMapping", Vector=world, Location=(7.3, 1.1, 0.0)).outputs[0]
    # scale 1: per-stone warm/cool weathering (small spread so no slab reads as a different material)
    wc = s.math("FRACT", s.math("MULTIPLY", rnd, 7.31))
    col = s.mixc(s.ramp(wc, 0.45, 1.0), lin("paver"), lin("paver_warm"))
    col = s.mixc(s.math("MULTIPLY", s.ramp(wc, 0.55, 0.0), 0.9), col, lin("paver_cool"))
    col = s.tone(col, s.math("MULTIPLY_ADD", rnd, 0.22, 0.88))
    # regional variation across neighbouring slabs (a slow field, sampled per slab via its object centre)
    reg = s.noise(s.n("ShaderNodeObjectInfo").outputs["Location"], 1.1, 2.0, 0.5)
    col = s.tone(col, s.math("MULTIPLY_ADD", reg, 0.3, 0.8))
    # scale 2a: grime blotches and grey/brown stains lying on the faces
    broad = s.ramp(s.noise(world, 2.2, 8.0, 0.7), 0.38, 0.6)
    col = s.mixc(s.math("MULTIPLY", broad, 0.85), col, lin("paver_grey"))
    big_w = s.ramp(s.noise(shifted, 0.8, 5.0, 0.6), 0.5, 0.72)
    col = s.mixc(s.math("MULTIPLY", big_w, 0.55), col, lin("stain_warm"))
    big_c = s.ramp(s.noise(world, 1.3, 5.0, 0.6), 0.52, 0.74)
    col = s.mixc(s.math("MULTIPLY", big_c, 0.5), col, lin("stain_cool"))
    stain = s.ramp(s.noise(shifted, 7.0, 6.0, 0.72), 0.55, 0.7)
    col = s.mixc(s.math("MULTIPLY", stain, 0.65), col, lin("paver_stain"))
    blot = s.ramp(s.noise(world, 14.0, 4.0, 0.7), 0.6, 0.72)
    col = s.mixc(s.math("MULTIPLY", blot, 0.5), col, lin("paver_dark"))
    # the -y half and the area under the table are dirtier and browner (lighting agent's measurement)
    wy = s.n("ShaderNodeSeparateXYZ", Vector=world).outputs[1]
    # measured: -y half (opposite/low_side foreground) is mid-dark grey-brown, about half the +y brightness
    south = s.math("MULTIPLY", s.ramp(wy, 0.2, -0.8), s.math("MULTIPLY_ADD", s.noise(world, 2.0, 4.0, 0.6), 0.4, 0.7))
    col = s.mixc(s.math("MINIMUM", s.math("MULTIPLY", south, 0.95), 0.92), col, lin("paver_south"))
    rho = s.n("ShaderNodeVectorMath", {"operation": "LENGTH"},
              Vector=s.n("ShaderNodeMapping", Vector=world, Scale=(1.0, 1.0, 0.0))).outputs["Value"]
    under = s.math("MULTIPLY", s.ramp(rho, 0.8, 0.3), s.ramp(s.noise(world, 3.5, 4.0, 0.6), 0.35, 0.6))
    col = s.mixc(s.math("MULTIPLY", under, 0.45), col, lin("paver_south"))
    # scale 2b: selective edge dirt (some joint stretches only) and a faint algae film on outer slabs
    sel = s.ramp(s.noise(world, 4.0, 4.0, 0.6), 0.45, 0.66)
    rim = s.math("MULTIPLY", s.ramp(ed, s.math("MULTIPLY_ADD", sel, 0.025, 0.004), 0.0015), sel)
    rim = s.math("MULTIPLY", rim, s.ramp(s.noise(world, 18.0, 3.0), 0.3, 0.6))
    col = s.mixc(s.math("MULTIPLY", rim, 0.75), col, lin("wet_edge"))
    algae = s.math("MULTIPLY", edge_w, s.ramp(s.noise(shifted, 2.5, 4.0, 0.6), 0.45, 0.68))
    col = s.mixc(s.math("MULTIPLY", algae, 0.4), col, lin("paver_algae"))
    pits = s.ramp(s.n("ShaderNodeTexVoronoi", Vector=world, Scale=140.0).outputs["Distance"], 0.16, 0.08)
    pits = s.math("MULTIPLY", pits, s.ramp(s.noise(shifted, 9.0), 0.4, 0.6))
    col = s.mixc(s.math("MULTIPLY", pits, 0.5), col, lin("paver_dark"))
    # scale 3: aggregate grain, pale and dark specks a few mm across (high contrast like the close-up)
    g1 = s.noise(world, 520.0, 1.0, 0.5)
    g2 = s.noise(shifted, 380.0, 1.0, 0.5)
    col = s.mixc(s.math("MULTIPLY", s.ramp(g1, 0.58, 0.68), 0.28), col, lin("paver_grain"))
    col = s.mixc(s.math("MULTIPLY", s.ramp(g2, 0.58, 0.68), 0.14), col, lin("paver_pale"))
    # roughness: damp/worn patches smoother -> sky sheen; grain adds micro variation
    damp = s.ramp(s.noise(shifted, 1.6, 4.0, 0.6), 0.5, 0.68)
    rough = s.math("MULTIPLY_ADD", damp, -0.25, s.math("MULTIPLY_ADD", g1, 0.12, 0.8))
    # worn edge band (bevel, last ~1 cm): dusty and fully rough so grazing sky light cannot paint white rims
    band = s.ramp(ed, 0.006, 0.0015)
    band_n = s.ramp(s.noise(world, 22.0, 3.0, 0.6), 0.4, 0.65)
    col = s.mixc(s.math("MULTIPLY", s.math("MULTIPLY", band, band_n), 0.3), col, lin("wet_edge"))
    rough = s.math("MAXIMUM", rough, s.math("MULTIPLY", band, 0.97))
    h = s.math("ADD", s.math("MULTIPLY", g1, 0.5), s.math("MULTIPLY", s.noise(world, 60.0, 3.0), 0.5))
    b = s.bsdf(col, rough, s.bump(h, 0.3, 0.002))
    b.inputs["Specular IOR Level"].default_value = 0.4
    return s.m


def earth():
    s = Shader("Garden Ground Earth")
    world = s.n("ShaderNodeNewGeometry").outputs["Position"]
    pave, lawn, terr = s.attr("gr_pave"), s.attr("gr_lawn"), s.attr("gr_terrace")
    n1 = s.noise(world, 18.0, 4.0, 0.6)
    n2 = s.noise(world, 3.0, 3.0, 0.5)
    joint = s.mixc(s.math("MULTIPLY", s.ramp(n2, 0.5, 0.65), 0.6), lin("joint_soil"), lin("joint_moss"))
    joint = s.mixc(s.math("MULTIPLY", s.ramp(n1, 0.5, 0.7), 0.7), joint, lin("joint_litter"))
    soil = s.mixc(s.ramp(n1, 0.35, 0.7), lin("terrace_soil"), s.tone(lin("terrace_soil"), 1.35))
    lawn_c = s.mixc(s.ramp(n2, 0.4, 0.65), lin("lawn_soil"), s.tone(lin("lawn_soil"), 1.25))
    col = s.mixc(lawn, soil, lawn_c)
    col = s.mixc(terr, col, soil)
    col = s.mixc(pave, col, joint)
    # rear yard (y < -8, unseen ground under the bin / wheelbarrow): dark soil with grey gravel
    yard = s.attr("gr_yard")
    grav = s.ramp(s.n("ShaderNodeTexVoronoi", Vector=world, Scale=60.0).outputs["Distance"], 0.25, 0.12)
    ycol = s.mixc(s.math("MULTIPLY", grav, 0.7), lin("terrace_soil"), lin("path"))
    col = s.mixc(yard, col, ycol)
    s.bsdf(col, 0.95, s.bump(n1, 0.5, 0.01))
    return s.m


def grass():
    s = Shader("Garden Ground Grass")
    tip = s.attr("nk_tip")
    rnd = s.attr("nk_rand", "INSTANCER")
    blade_r = s.attr("nk_rand")
    dry = s.attr("gr_dry", "INSTANCER")
    t = s.math("POWER", tip, 1.3)
    col = s.mixc(t, lin("grass_root"), lin("grass_tip"))
    col = s.mixc(s.math("MULTIPLY", dry, s.math("MULTIPLY_ADD", t, 0.6, 0.4)), col, lin("grass_dry"))
    tone = s.attr("gr_tone", "INSTANCER")
    # +y lawn (seen from opposite/left) reads lighter and less saturated in the reference
    iy = s.n("ShaderNodeSeparateXYZ", Vector=s.n("ShaderNodeObjectInfo").outputs["Location"]).outputs[1]
    north = s.ramp(iy, 0.5, 2.5)
    col = s.mixc(s.math("MULTIPLY", north, 0.35), col, lin("grass_dry"))
    v = s.math("SUBTRACT", 1.18, s.math("ADD", s.math("MULTIPLY", rnd, 0.12), s.math("MULTIPLY", blade_r, 0.42)))
    v = s.math("MULTIPLY", v, s.math("MULTIPLY_ADD", north, 0.25, s.math("MAXIMUM", tone, 0.6)))
    col = s.n("ShaderNodeHueSaturation", Hue=s.math("MULTIPLY_ADD", blade_r, 0.04, 0.48), Saturation=1.0,
              Value=v, Fac=1.0, Color=col).outputs[0]
    b = s.bsdf(col, 0.6, None)
    b.inputs["Subsurface Weight"].default_value = 0.0
    tr = s.n("ShaderNodeBsdfTranslucent", Color=col)
    mix = s.n("ShaderNodeMixShader", Fac=0.45)
    s.links.new(b.outputs[0], mix.inputs[1])
    s.links.new(tr.outputs[0], mix.inputs[2])
    s.links.new(mix.outputs[0], s.out.inputs["Surface"])
    return s.m


def simple(name, key, rough, var=0.25, scale=60.0, metal=0.0):
    s = Shader(name)
    world = s.n("ShaderNodeNewGeometry").outputs["Position"]
    n = s.noise(world, scale, 3.0)
    rnd = s.attr("nk_rand", "INSTANCER")
    col = s.tone(lin(key), s.math("MULTIPLY_ADD", s.math("ADD", n, rnd), var, 1.0 - var))
    s.bsdf(col, rough, s.bump(n, 0.2, 0.003), Metallic=metal)
    return s.m


def lens():
    s = Shader("Garden Ground Lens")
    s.bsdf((0.18, 0.19, 0.2, 1.0), 0.25)
    return s.m


def water():
    s = Shader("Garden Ground Water")
    world = s.n("ShaderNodeNewGeometry").outputs["Position"]
    s.bsdf((0.01, 0.012, 0.009, 1.0), 0.6, s.bump(s.noise(world, 6.0, 2.0), 0.05, 0.002))
    return s.m


def litter_mat():
    """Felted needle clump: reddish-brown fibres (stretched noise streaks in two directions) over dark gaps."""
    s = Shader("Garden Ground Litter Mat")
    obj = s.n("ShaderNodeTexCoord").outputs["Object"]
    rnd = s.attr("nk_rand", "INSTANCER")
    f1 = s.noise(s.n("ShaderNodeMapping", Vector=obj, Scale=(900.0, 60.0, 60.0)).outputs[0], 1.0, 2.0, 0.5)
    f2 = s.noise(s.n("ShaderNodeMapping", Vector=obj, Rotation=(0.0, 0.0, 1.1),
                     Scale=(900.0, 60.0, 60.0)).outputs[0], 1.0, 2.0, 0.5)
    fib = s.math("MAXIMUM", s.ramp(f1, 0.5, 0.62), s.ramp(f2, 0.52, 0.64))
    col = s.mixc(fib, lin("mat_dark"), s.tone(lin("litter"), s.math("MULTIPLY_ADD", rnd, 0.3, 0.85)))
    s.bsdf(col, 0.85, s.bump(fib, 0.5, 0.002))
    return s.m


def build_all():
    water()
    simple("Garden Ground Twig", "twig", 0.85, 0.25, 30.0)
    simple("Garden Ground Weed Leaf", "weed_leaf", 0.55, 0.3, 40.0)
    simple("Garden Ground Leaf Litter", "leaf_litter", 0.75, 0.3, 50.0)
    litter_mat()
    paver()
    earth()
    grass()
    simple("Garden Ground Litter", "litter", 0.8, 0.3, 80.0)
    simple("Garden Ground Moss", "moss", 0.9, 0.3, 40.0)
    simple("Garden Ground Path", "path", 0.9, 0.2, 6.0)
    simple("Garden Ground Steel", "steel", 0.35, 0.1, 30.0, metal=0.8)
    lens()

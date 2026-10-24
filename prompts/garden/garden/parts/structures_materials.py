"""Procedural Shader Node materials for the garden structures ("Garden Structures <Thing>").

Base colours start from the scan's median sRGB colour of each object (data/params/structures.json notes), which the
lighting module calibrates so an open top-lit surface renders at about its base colour. Per-piece variation comes
from Geometry Nodes attributes: nk_rand (0..1 per board/piece), nk_color (piece tint), st_relief (pot lattice
ridge 0..1), st_h (0 at a pot's foot, 1 at its rim), st_weather (timber weathering control).
"""
from garden.util import new_material, srgb_to_linear

P = "Garden Structures "


class Sh:
    """Tiny shader-graph helper over a material's node tree."""

    def __init__(self, name):
        self.m, self.nodes, self.links, self.out = new_material(P + name)
        self.bsdf = self.n("ShaderNodeBsdfPrincipled")
        self.link(self.bsdf.outputs["BSDF"], self.out.inputs["Surface"])

    def n(self, idname, **props):
        node = self.nodes.new(idname)
        for k, v in props.items():
            setattr(node, k, v)
        return node

    def link(self, a, b):
        self.links.new(a, b)

    def set(self, sock, v):
        if isinstance(v, (int, float, tuple, list)):
            sock.default_value = v
        else:
            self.link(v, sock)

    def attr(self, name, kind="GEOMETRY"):
        return self.n("ShaderNodeAttribute", attribute_name=name, attribute_type=kind)

    def coord(self):
        return self.n("ShaderNodeTexCoord").outputs["Object"]

    def noise(self, scale, detail=4.0, rough=0.55, vec=None, dims="3D"):
        t = self.n("ShaderNodeTexNoise", noise_dimensions=dims)
        t.inputs["Scale"].default_value = scale
        t.inputs["Detail"].default_value = detail
        t.inputs["Roughness"].default_value = rough
        self.link(vec if vec is not None else self.coord(), t.inputs["Vector"])
        return t.outputs["Fac"]

    def math(self, op, a, b=0.0, clamp=False):
        m = self.n("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.set(m.inputs[0], a)
        self.set(m.inputs[1], b)
        return m.outputs[0]

    def mrange(self, v, a0, a1, b0=0.0, b1=1.0):
        m = self.n("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
        self.set(m.inputs["Value"], v)
        for k, val in (("From Min", a0), ("From Max", a1), ("To Min", b0), ("To Max", b1)):
            self.set(m.inputs[k], val)
        return m.outputs["Result"]

    def mixc(self, fac, a, b):
        m = self.n("ShaderNodeMix", data_type="RGBA", clamp_factor=True)
        self.set(m.inputs["Factor"], fac)
        self.set(m.inputs[6], a if not isinstance(a, tuple) else a)
        self.set(m.inputs[7], b if not isinstance(b, tuple) else b)
        return m.outputs[2]

    def bump(self, height, strength, distance=0.01):
        b = self.n("ShaderNodeBump")
        b.inputs["Strength"].default_value = strength
        b.inputs["Distance"].default_value = distance
        self.set(b.inputs["Height"], height)
        self.link(b.outputs["Normal"], self.bsdf.inputs["Normal"])
        return b

    def principled(self, color, rough, metal=0.0):
        self.set(self.bsdf.inputs["Base Color"], color)
        self.set(self.bsdf.inputs["Roughness"], rough)
        self.set(self.bsdf.inputs["Metallic"], metal)


def L(rgb):
    return srgb_to_linear(rgb)


def _lattice_ribs(s, rib_w=0.0013):
    """Per-pixel thin lattice ribs from the pot-local position (st_local) and lattice parameters
    st_latp = (count around, vertical pitch, second-family strength): rib = 1 within ~rib_w metres of either
    helical line family, slightly warped by noise; st_band masks the rim/foot and breaks the ribs up."""
    loc = s.n("ShaderNodeSeparateXYZ")
    s.link(s.attr("st_local").outputs["Vector"], loc.inputs[0])
    prm = s.n("ShaderNodeSeparateXYZ")
    s.link(s.attr("st_latp").outputs["Vector"], prm.inputs[0])
    band = s.attr("st_band").outputs["Fac"]
    x, y, z = loc.outputs["X"], loc.outputs["Y"], loc.outputs["Z"]
    cnt, pitch, fam2 = prm.outputs["X"], prm.outputs["Y"], prm.outputs["Z"]
    warp = s.math("MULTIPLY", s.math("SUBTRACT", s.noise(7.0, 2.0, 0.5, vec=s.attr("st_local").outputs["Vector"]),
                                     0.5), 0.12)
    u = s.math("ADD", s.math("MULTIPLY", s.math("DIVIDE", s.math("ARCTAN2", y, x), 6.283185), cnt), warp)
    v = s.math("DIVIDE", z, s.math("MAXIMUM", pitch, 0.001))
    rad = s.math("SQRT", s.math("ADD", s.math("MULTIPLY", x, x), s.math("MULTIPLY", y, y)))
    cell_u = s.math("DIVIDE", s.math("MULTIPLY", rad, 6.283185), s.math("MAXIMUM", cnt, 1.0))
    cell = s.math("DIVIDE", s.math("MULTIPLY", cell_u, pitch),
                  s.math("SQRT", s.math("ADD", s.math("MULTIPLY", cell_u, cell_u), s.math("MULTIPLY", pitch, pitch))))
    ribs = []
    for op, wgt in (("ADD", 1.0), ("SUBTRACT", fam2)):
        f = s.math("FRACT", s.math(op, u, v))
        dm = s.math("MULTIPLY", s.math("MINIMUM", f, s.math("SUBTRACT", 1.0, f)), cell)
        ribs.append(s.math("MULTIPLY", s.mrange(dm, rib_w, rib_w * 0.35), wgt))
    return s.math("MULTIPLY", s.math("MAXIMUM", ribs[0], ribs[1]), band)


def ceramic():
    """Pale peach-cream planter clay at three scales: broad warm/cool mottling and chalky bloom; vertical rain
    streaks under the rim and green-grey algae / soil splash at the foot (st_h); fine pores. The lattice is thin
    crisp ribs (about 2.5 mm) computed per pixel (_lattice_ribs) and expressed as a sharp bump plus a faint
    highlight on the rib and dirt along its foot."""
    s = Sh("Ceramic")
    rib = _lattice_ribs(s)
    h = s.attr("st_h").outputs["Fac"]
    mott = s.noise(6.0, 5.0, 0.6)
    base = s.mixc(s.mrange(mott, 0.35, 0.7), L((228, 196, 176)), L((206, 170, 148)))
    bloom = s.mrange(s.noise(2.5, 4.0, 0.6), 0.55, 0.75, 0.0, 0.35)
    base = s.mixc(bloom, base, L((236, 226, 212)))
    base = s.mixc(s.math("MULTIPLY", rib, 0.35), base, L((242, 228, 214)))
    mp = s.n("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (14.0, 14.0, 1.2)
    s.link(s.coord(), mp.inputs["Vector"])
    streak = s.mrange(s.noise(3.0, 3.0, 0.6, vec=mp.outputs["Vector"]), 0.55, 0.75, 0.0, 1.0)
    streak = s.math("MULTIPLY", streak, s.mrange(h, 0.55, 0.92, 0.0, 0.35))
    col = s.mixc(streak, base, L((150, 130, 108)))
    algae = s.math("MULTIPLY", s.mrange(h, 0.0, 0.4, 1.0, 0.0), s.mrange(s.noise(8.0, 4.0, 0.6), 0.3, 0.55))
    col = s.mixc(s.math("MULTIPLY", algae, 0.85), col, L((96, 100, 66)))
    splash = s.math("MULTIPLY", s.mrange(h, 0.0, 0.16, 1.0, 0.0), s.mrange(s.noise(25.0, 4.0, 0.7), 0.3, 0.55))
    col = s.mixc(splash, col, L((70, 56, 40)))
    s.principled(col, s.math("ADD", s.math("MULTIPLY", mott, 0.1), 0.84))
    s.bump(s.math("ADD", rib, s.math("MULTIPLY", s.noise(160.0, 2.0, 0.5), 0.15)), 0.9, 0.0025)


def timber():
    """Weathered pale timber boards: fibre streaks along the board, per-board tone (nk_rand), grey weathering."""
    s = Sh("Timber")
    rnd = s.attr("nk_rand").outputs["Fac"]
    weather = s.attr("st_weather").outputs["Fac"]
    mp = s.n("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, 1.0, 1.0)
    s.link(s.coord(), mp.inputs["Vector"])
    fib = s.noise(60.0, 6.0, 0.7, vec=mp.outputs["Vector"])
    broad = s.noise(4.0, 3.0, 0.5)
    tone = s.mixc(s.math("MULTIPLY", rnd, 0.8), L((176, 150, 112)), L((135, 108, 76)))
    tone = s.mixc(s.mrange(fib, 0.3, 0.75, 0.0, 0.45), tone, L((110, 88, 62)))
    tone = s.mixc(s.math("MULTIPLY", weather, s.mrange(broad, 0.3, 0.7, 0.3, 0.9)), tone, L((150, 145, 132)))
    s.principled(tone, 0.88)
    s.bump(fib, 0.25, 0.004)


def pallet_wood():
    """Red-brown pallet timber, paler on worn top faces, per-board tone."""
    s = Sh("Pallet Wood")
    rnd = s.attr("nk_rand").outputs["Fac"]
    nrm = s.n("ShaderNodeNewGeometry").outputs["Normal"]
    up = s.n("ShaderNodeSeparateXYZ")
    s.link(nrm, up.inputs[0])
    tone = s.mixc(rnd, L((150, 88, 74)), L((118, 66, 56)))
    tone = s.mixc(s.mrange(up.outputs["Z"], 0.6, 0.95, 0.0, 0.55), tone, L((190, 160, 145)))
    tone = s.mixc(s.mrange(s.noise(30.0, 6.0, 0.7), 0.4, 0.8, 0.0, 0.4), tone, L((90, 60, 50)))
    grime = s.mrange(s.noise(3.0, 4.0, 0.6), 0.4, 0.65, 0.0, 0.7)
    tone = s.mixc(grime, tone, L((62, 52, 38)))
    s.principled(tone, s.math("SUBTRACT", 0.88, s.math("MULTIPLY", grime, 0.2)))
    s.bump(s.noise(80.0, 4.0, 0.6), 0.2, 0.004)


def concrete():
    """Weathered, dirty concrete treads and kerbs at three scales: broad warm/cool tone; dark damp patches
    (glossier) and soil stains; moss concentrated along tread edges and corners on upward faces; fine grit."""
    s = Sh("Concrete")
    n1 = s.noise(4.0, 5.0, 0.6)
    n2 = s.noise(30.0, 3.0, 0.5)
    n3 = s.noise(220.0, 2.0, 0.5)
    col = s.mixc(s.mrange(n1, 0.35, 0.7), L((92, 86, 72)), L((66, 62, 50)))
    damp = s.mrange(s.noise(1.8, 5.0, 0.7), 0.42, 0.6)
    col = s.mixc(s.math("MULTIPLY", damp, 0.9), col, L((40, 36, 28)))
    col = s.mixc(s.mrange(n2, 0.5, 0.8, 0.0, 0.6), col, L((58, 50, 36)))
    up = s.n("ShaderNodeSeparateXYZ")
    s.link(s.n("ShaderNodeNewGeometry").outputs["Normal"], up.inputs[0])
    edge = s.mrange(s.n("ShaderNodeAmbientOcclusion").outputs["AO"], 0.95, 0.6)
    patch = s.mrange(s.noise(1.6, 3.0, 0.6), 0.52, 0.64)
    moss = s.math("MULTIPLY", s.mrange(up.outputs["Z"], 0.6, 0.95),
                  s.math("MULTIPLY", s.mrange(s.noise(9.0, 5.0, 0.65), 0.4, 0.6),
                         s.math("MULTIPLY", patch, s.math("ADD", s.math("MULTIPLY", edge, 0.8), 0.1))))
    col = s.mixc(s.math("MULTIPLY", moss, 0.6), col, L((58, 68, 32)))
    col = s.mixc(s.mrange(n3, 0.6, 0.8, 0.0, 0.25), col, L((128, 122, 104)))
    s.principled(col, s.math("SUBTRACT", 0.92, s.math("MULTIPLY", damp, 0.35)))
    s.bump(s.math("ADD", n3, s.math("MULTIPLY", n2, 0.5)), 0.35, 0.004)


def pink_slab():
    """Salmon-pink precast paving slab (top landing): mottled, dirty, with a sawn joint every 0.45 m along X."""
    s = Sh("Pink Slab")
    n1 = s.noise(5.0, 5.0, 0.6)
    col = s.mixc(s.mrange(n1, 0.35, 0.7), L((176, 132, 116)), L((140, 104, 90)))
    col = s.mixc(s.mrange(s.noise(25.0, 3.0, 0.5), 0.55, 0.8, 0.0, 0.5), col, L((90, 80, 60)))
    sep = s.n("ShaderNodeSeparateXYZ")
    s.link(s.attr("st_local").outputs["Vector"], sep.inputs[0])
    joint = s.mrange(s.math("ABSOLUTE", s.math("SUBTRACT", s.math("FRACT", s.math("DIVIDE", sep.outputs["X"], 0.45)),
                                                    0.5)), 0.47, 0.5)
    col = s.mixc(joint, col, L((40, 36, 28)))
    s.principled(col, 0.9)
    s.bump(s.math("SUBTRACT", s.noise(80.0, 3.0, 0.5), joint), 0.4, 0.005)


def litter():
    """Dry leaf litter and twigs: brown to grey-buff per piece (nk_rand)."""
    s = Sh("Litter")
    rnd = s.attr("nk_rand").outputs["Fac"]
    s.principled(s.mixc(rnd, L((120, 82, 50)), L((150, 130, 100))), 0.8)
    s.set(s.bsdf.inputs["Subsurface Weight"], 0.05)


def brick():
    """Red-brown brick riser with recessed pale mortar (Brick texture)."""
    s = Sh("Brick")
    b = s.n("ShaderNodeTexBrick")
    s.link(s.coord(), b.inputs["Vector"])
    b.inputs["Color1"].default_value = L((140, 98, 74))
    b.inputs["Color2"].default_value = L((118, 82, 62))
    b.inputs["Mortar"].default_value = L((150, 140, 120))
    b.inputs["Scale"].default_value = 4.5
    b.inputs["Mortar Size"].default_value = 0.012
    b.inputs["Brick Width"].default_value = 0.5
    b.inputs["Row Height"].default_value = 0.25
    col = s.mixc(s.mrange(s.noise(20.0), 0.4, 0.8, 0.0, 0.35), b.outputs["Color"], L((80, 70, 50)))
    s.principled(col, 0.9)
    s.bump(s.math("SUBTRACT", 1.0, b.outputs["Fac"]), 0.4, 0.006)


def soil():
    """Dark crumbly soil: clods from noise, a few paler dry patches."""
    s = Sh("Soil")
    n1 = s.noise(25.0, 6.0, 0.7)
    n2 = s.noise(3.0, 3.0, 0.5)
    col = s.mixc(s.mrange(n1, 0.3, 0.7), L((78, 68, 46)), L((46, 40, 28)))
    col = s.mixc(s.mrange(n2, 0.55, 0.75, 0.0, 0.5), col, L((112, 100, 76)))
    s.principled(col, 0.97)
    s.bump(n1, 0.6, 0.01)


def stone():
    """Grey weathered stone / rock with lichen-buff mottling."""
    s = Sh("Stone")
    n1 = s.noise(5.0, 6.0, 0.65)
    n2 = s.noise(40.0, 3.0, 0.5)
    col = s.mixc(s.mrange(n1, 0.35, 0.7), L((132, 126, 110)), L((92, 88, 74)))
    col = s.mixc(s.mrange(n2, 0.6, 0.8, 0.0, 0.4), col, L((95, 95, 72)))
    s.principled(col, 0.9)
    s.bump(s.math("ADD", n1, s.math("MULTIPLY", n2, 0.3)), 0.5, 0.01)


def dark_stone():
    """Dark grey cast stone (statue, lantern)."""
    s = Sh("Dark Stone")
    n1 = s.noise(12.0, 5.0, 0.6)
    s.principled(s.mixc(s.mrange(n1, 0.3, 0.7), L((58, 60, 56)), L((34, 36, 34))), 0.8)
    s.bump(n1, 0.3, 0.005)


def metal_simple(name, rgb, rough, metal, rough_var=0.15, tone_var=0.4):
    """Metal or plain surface: one colour with noise tone and roughness breakup."""
    s = Sh(name)
    n1 = s.noise(15.0, 4.0, 0.6)
    s.principled(s.mixc(s.mrange(n1, 0.4, 0.75, 0.0, tone_var), L(rgb), L(tuple(int(c * 0.7) for c in rgb))),
                 s.math("ADD", s.math("MULTIPLY", n1, rough_var), rough), metal)
    return s


def galvanised():
    """Weathered galvanised steel: dull blue-grey zinc with spangle mottling, patchy white oxide bloom and
    darker grime; rough, only partly metallic."""
    s = Sh("Galvanised")
    n1 = s.noise(18.0, 4.0, 0.6)
    ox = s.mrange(s.noise(4.0, 5.0, 0.65), 0.5, 0.68)
    grime = s.mrange(s.noise(2.5, 4.0, 0.6), 0.55, 0.75, 0.0, 0.6)
    col = s.mixc(s.mrange(n1, 0.35, 0.7), L((122, 130, 138)), L((96, 104, 112)))
    col = s.mixc(ox, col, L((190, 192, 186)))
    col = s.mixc(grime, col, L((80, 82, 74)))
    s.principled(col, s.math("ADD", 0.68, s.math("MULTIPLY", ox, 0.25)), s.math("SUBTRACT", 0.35, s.math("MULTIPLY", ox, 0.3)))
    s.bump(s.noise(90.0, 3.0, 0.5), 0.2, 0.002)


def dark_metal():
    """Black painted steel: satin paint, chipped and rust-brown near the ground (world Z below ~0.35 m)."""
    s = Sh("Dark Metal")
    n1 = s.noise(15.0, 4.0, 0.6)
    sep = s.n("ShaderNodeSeparateXYZ")
    s.link(s.coord(), sep.inputs[0])
    low = s.mrange(sep.outputs["Z"], 0.4, 0.12)
    rust = s.math("MULTIPLY", low, s.mrange(s.noise(30.0, 5.0, 0.7), 0.35, 0.6))
    col = s.mixc(s.mrange(n1, 0.4, 0.75, 0.0, 0.4), L((30, 30, 28)), L((22, 22, 20)))
    col = s.mixc(rust, col, L((92, 58, 34)))
    s.principled(col, s.math("ADD", 0.38, s.math("MULTIPLY", rust, 0.5)), s.math("SUBTRACT", 0.6, rust))
    s.bump(s.noise(120.0, 2.0, 0.5), 0.15, 0.002)


def colour_attr(name, rough, fallback):
    """Plastic/paint/glaze whose colour comes from the nk_color attribute (fallback where absent)."""
    s = Sh(name)
    a = s.attr("nk_color")
    has = s.math("GREATER_THAN", s.math("ADD", a.outputs["Fac"], 0.0), 0.0001)
    col = s.mixc(has, L(fallback), a.outputs["Color"])
    n1 = s.noise(10.0, 4.0, 0.6)
    col = s.mixc(s.mrange(n1, 0.45, 0.8, 0.0, 0.3), col, L((60, 58, 45)))
    s.principled(col, rough)
    return s


def plant():
    """Small green seedlings/grass in pots and beds (root-to-tip gradient from nk_tip)."""
    s = Sh("Plant")
    tip = s.attr("nk_tip").outputs["Fac"]
    rnd = s.attr("nk_rand").outputs["Fac"]
    col = s.mixc(tip, L((52, 70, 26)), L((104, 128, 50)))
    col = s.mixc(s.math("MULTIPLY", rnd, 0.5), col, L((130, 130, 60)))
    s.principled(col, 0.6)
    s.set(s.bsdf.inputs["Subsurface Weight"], 0.1)


def weed_leaf():
    """Broadleaf weed leaves and stems: per-leaf green tone (nk_rand), paler underside-ish veining noise,
    some translucency."""
    s = Sh("Weed Leaf")
    rnd = s.attr("nk_rand").outputs["Fac"]
    col = s.mixc(rnd, L((38, 62, 20)), L((82, 112, 42)))
    col = s.mixc(s.mrange(s.noise(60.0, 3.0, 0.5), 0.55, 0.8, 0.0, 0.3), col, L((40, 60, 22)))
    s.principled(col, 0.5)
    s.set(s.bsdf.inputs["Subsurface Weight"], 0.15)


def moss():
    """Moss cushions in corners: dark olive with brighter tips."""
    s = Sh("Moss")
    n1 = s.noise(80.0, 3.0, 0.6)
    s.principled(s.mixc(s.mrange(n1, 0.4, 0.7), L((44, 58, 20)), L((86, 104, 36))), 0.9)
    s.bump(n1, 0.5, 0.003)


def reed():
    """Variegated strap leaves of the pond plants: yellow-green with pale lengthwise stripes, darker roots."""
    s = Sh("Reed")
    tip = s.attr("nk_tip").outputs["Fac"]
    mp = s.n("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (60.0, 60.0, 0.5)
    s.link(s.coord(), mp.inputs["Vector"])
    stripe = s.mrange(s.noise(1.0, 1.0, 0.5, vec=mp.outputs["Vector"]), 0.5, 0.62)
    col = s.mixc(s.mrange(tip, 0.0, 0.5), L((70, 92, 34)), L((150, 165, 70)))
    col = s.mixc(s.math("MULTIPLY", stripe, 0.6), col, L((205, 205, 140)))
    s.principled(col, 0.55)
    s.set(s.bsdf.inputs["Subsurface Weight"], 0.1)


def ball():
    """Dark green football with black patches (Voronoi cells on object coordinates)."""
    s = Sh("Ball")
    v = s.n("ShaderNodeTexVoronoi")
    v.inputs["Scale"].default_value = 18.0
    s.link(s.coord(), v.inputs["Vector"])
    patch = s.math("GREATER_THAN", s.noise(3.0, 0.0, 0.5, vec=v.outputs["Color"]), 0.58)
    s.principled(s.mixc(patch, L((30, 96, 74)), L((20, 22, 20))), 0.45)


def water():
    """Dark still pond water under the grates."""
    s = Sh("Water")
    s.principled(L((22, 26, 18)), 0.05)


def build_all():
    ceramic()
    timber()
    pallet_wood()
    concrete()
    pink_slab()
    litter()
    brick()
    soil()
    stone()
    dark_stone()
    dark_metal()
    galvanised()
    metal_simple("Steel", (120, 106, 94), 0.03, 1.0, rough_var=0.03, tone_var=0.05)
    metal_simple("Cane", (170, 140, 92), 0.7, 0.0)
    colour_attr("Painted", 0.6, (120, 120, 110))
    colour_attr("Glazed", 0.3, (52, 50, 40))
    plant()
    reed()
    weed_leaf()
    moss()
    ball()
    water()

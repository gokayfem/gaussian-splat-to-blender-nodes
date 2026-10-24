"""Procedural Shader Node materials for the garden boundary (walls, shed, fences, hedges, far vegetation).

Every colour default comes from data/params/boundary.json ``palette`` (sRGB 0-255 picked from the reference
renders, converted to linear here). Wall materials read the GN attribute ``bnd_s`` (arc length along the wall)
and object Z (the boundary object has an identity transform, so object Z is world height) as a wall-local
texture space, so bricks run along every wall regardless of its direction. Foliage reads ``nk_color`` /
``nk_rand`` from the leaf instances (INSTANCER) or realized geometry (GEOMETRY), whichever is present.
"""
import bpy

from garden.util import load_params, new_material, srgb_to_linear

PREFIX = "Garden Boundary "


class _Tree:
    """Tiny helper over a material node tree: node creation with inputs, links and properties in one call."""

    def __init__(self, nodes, links):
        self.nodes, self.links = nodes, links

    def n(self, idname, props=None, **inputs):
        node = self.nodes.new(idname)
        for k, v in (props or {}).items():
            setattr(node, k, v)
        for k, v in inputs.items():
            sock = next(s for s in node.inputs if s.name == k and s.enabled)
            if hasattr(v, "is_output"):
                self.links.new(v, sock)
            else:
                sock.default_value = v
        return node

    def link(self, out, node, name):
        self.links.new(out, next(s for s in node.inputs if s.name == name and s.enabled))

    def math(self, op, a, b=0.0, clamp=False):
        m = self.n("ShaderNodeMath", props={"operation": op, "use_clamp": clamp})
        for i, v in enumerate((a, b)):
            if hasattr(v, "is_output"):
                self.links.new(v, m.inputs[i])
            else:
                m.inputs[i].default_value = v
        return m.outputs[0]

    def mulc(self, col, scalar):
        """Colour times a scalar (value scaling through a Multiply-blend Mix with a grey from the scalar)."""
        gray = self.n("ShaderNodeCombineColor")
        for k in range(3):
            self.links.new(scalar, gray.inputs[k])
        m = self.n("ShaderNodeMix", props={"data_type": "RGBA", "blend_type": "MULTIPLY"})
        fac, a, b = [s for s in m.inputs if s.enabled]
        fac.default_value = 1.0
        if hasattr(col, "is_output"):
            self.links.new(col, a)
        else:
            a.default_value = col
        self.links.new(gray.outputs[0], b)
        return next(s for s in m.outputs if s.enabled)

    def mixc(self, fac, a, b):
        m = self.n("ShaderNodeMix", props={"data_type": "RGBA"})
        sockets = [s for s in m.inputs if s.enabled]
        for sock, v in zip(sockets, (fac, a, b)):
            if hasattr(v, "is_output"):
                self.links.new(v, sock)
            else:
                sock.default_value = v
        return next(s for s in m.outputs if s.enabled)


def _pal(name, default):
    return srgb_to_linear(load_params("boundary").get("palette", {}).get(name, default))


def _wall_coords(t):
    """(bnd_s, z, 0): metres along the wall and height, the texture space of every boundary wall."""
    s = t.n("ShaderNodeAttribute", props={"attribute_type": "GEOMETRY", "attribute_name": "bnd_s"})
    tc = t.n("ShaderNodeTexCoord")
    sep = t.n("ShaderNodeSeparateXYZ", Vector=tc.outputs["Object"])
    return t.n("ShaderNodeCombineXYZ", X=s.outputs["Fac"], Y=sep.outputs["Z"]).outputs[0], tc.outputs["Object"]


def _brick(name, c1, c2, mortar, band=None, band_rows=None, stains=0.0, base_dark=0.0, base_height=0.9):
    """Brick wall: Brick Texture in wall space, per-brick tone, soot/grime noise, mortar recess bump.

    ``band`` (colour) with ``band_rows`` [[z0, z1, period, duty], ...] paints rows of contrasting bricks
    (red window heads/bands on the yellow stock-brick house) over spans that repeat along the wall."""
    m, nodes, links, out = new_material(PREFIX + name)
    t = _Tree(nodes, links)
    uv, obj = _wall_coords(t)
    brick = t.n("ShaderNodeTexBrick", Vector=uv, Color1=_pal(c1[0], c1[1]), Color2=_pal(c2[0], c2[1]),
                Mortar=_pal(mortar[0], mortar[1]), Scale=1.0, **{"Mortar Size": 0.011, "Mortar Smooth": 0.3,
                                                                 "Bias": 0.0, "Brick Width": 0.225,
                                                                 "Row Height": 0.075})
    brick.offset = 0.5
    col = brick.outputs["Color"]
    if band is not None:
        sep = t.n("ShaderNodeSeparateXYZ", Vector=uv)
        mask = None
        for row in band_rows:
            z0, z1, period, duty = row[:4]
            arch = row[4] if len(row) > 4 else 0.0
            u = t.math("FRACT", t.math("DIVIDE", sep.outputs["X"], period))
            # arch: the band rises by `arch` at the middle of each span (sin of the span coordinate)
            lift = t.math("MULTIPLY", t.math("SINE", t.math("MULTIPLY", t.math("DIVIDE", u, duty), 3.14159)), arch)
            zz = t.math("SUBTRACT", sep.outputs["Y"], lift)
            inz = t.math("MULTIPLY", t.math("GREATER_THAN", zz, z0), t.math("LESS_THAN", zz, z1))
            span = t.math("LESS_THAN", u, duty)
            term = t.math("MULTIPLY", inz, span)
            mask = term if mask is None else t.math("MAXIMUM", mask, term)
        notmortar = t.math("SUBTRACT", 1.0, brick.outputs["Fac"])
        col = t.mixc(t.math("MULTIPLY", mask, notmortar), col, _pal(band[0], band[1]))
    grime = t.n("ShaderNodeTexNoise", Vector=obj, Scale=0.9, Detail=4.0, Roughness=0.6)
    dark = t.n("ShaderNodeMapRange", Value=grime.outputs["Fac"], **{"From Min": 0.35, "From Max": 0.75,
                                                                     "To Min": 0.75, "To Max": 1.08})
    col = t.mulc(col, dark.outputs[0])
    if stains > 0.0:
        # vertical run-off stains: noise stretched along Z in wall space, darkening in streaks
        sep2 = t.n("ShaderNodeSeparateXYZ", Vector=uv)
        sv = t.n("ShaderNodeCombineXYZ", X=t.math("MULTIPLY", sep2.outputs["X"], 2.5),
                 Y=t.math("MULTIPLY", sep2.outputs["Y"], 0.25))
        st = t.n("ShaderNodeTexNoise", Vector=sv.outputs[0], Scale=1.0, Detail=5.0, Roughness=0.65)
        sk = t.n("ShaderNodeMapRange", Value=st.outputs["Fac"], **{"From Min": 0.45, "From Max": 0.7,
                                                                    "To Min": 1.0, "To Max": 1.0 - stains})
        col = t.mulc(col, sk.outputs[0])
        low = t.n("ShaderNodeMapRange", Value=sep2.outputs["Y"], **{"From Min": 0.0, "From Max": base_height,
                                                                     "To Min": 1.0 - base_dark, "To Max": 1.0})
        col = t.mulc(col, low.outputs[0])
    bump = t.n("ShaderNodeBump", Strength=0.35, Distance=0.01, Height=brick.outputs["Fac"])
    rough = t.n("ShaderNodeMapRange", Value=grime.outputs["Fac"], **{"To Min": 0.82, "To Max": 0.95})
    bsdf = t.n("ShaderNodeBsdfPrincipled", Roughness=rough.outputs[0], Normal=bump.outputs[0])
    links.new(col, bsdf.inputs["Base Color"])
    links.new(bsdf.outputs[0], out.inputs["Surface"])
    return m


def _wood(name, base, dark, grain_scale=(40.0, 40.0, 1.5)):
    """Weathered stained timber: vertical grain streaks (noise stretched along Z), per-board tone from nk_rand."""
    m, nodes, links, out = new_material(PREFIX + name)
    t = _Tree(nodes, links)
    tc = t.n("ShaderNodeTexCoord")
    stretch = t.n("ShaderNodeVectorMath", props={"operation": "MULTIPLY"}, Vector=tc.outputs["Object"])
    stretch.inputs[1].default_value = grain_scale
    grain = t.n("ShaderNodeTexNoise", Vector=stretch.outputs[0], Scale=1.0, Detail=6.0, Roughness=0.6,
                Distortion=0.4)
    rnd = t.n("ShaderNodeAttribute", props={"attribute_type": "INSTANCER", "attribute_name": "nk_rand"})
    fac = t.math("ADD", t.math("MULTIPLY", grain.outputs["Fac"], 1.4), t.math("MULTIPLY", rnd.outputs["Fac"], 0.6))
    col = t.mixc(t.math("SUBTRACT", fac, 0.6, clamp=True), _pal(base[0], base[1]), _pal(dark[0], dark[1]))
    bump = t.n("ShaderNodeBump", Strength=0.2, Distance=0.005, Height=grain.outputs["Fac"])
    bsdf = t.n("ShaderNodeBsdfPrincipled", Roughness=0.85, Normal=bump.outputs[0])
    links.new(col, bsdf.inputs["Base Color"])
    links.new(bsdf.outputs[0], out.inputs["Surface"])
    return m


def _plain(name, colour, rough, noise_scale=3.0, noise_amt=0.15, metallic=0.0):
    """Paint, felt or render: base colour with low-frequency value mottling and a fine bump."""
    m, nodes, links, out = new_material(PREFIX + name)
    t = _Tree(nodes, links)
    tc = t.n("ShaderNodeTexCoord")
    nz = t.n("ShaderNodeTexNoise", Vector=tc.outputs["Object"], Scale=noise_scale, Detail=5.0, Roughness=0.6)
    val = t.n("ShaderNodeMapRange", Value=nz.outputs["Fac"], **{"To Min": 1.0 - noise_amt, "To Max": 1.0 + noise_amt})
    col = t.mulc(_pal(colour[0], colour[1]), val.outputs[0])
    bump = t.n("ShaderNodeBump", Strength=0.15, Distance=0.004, Height=nz.outputs["Fac"])
    bsdf = t.n("ShaderNodeBsdfPrincipled", Roughness=rough, Metallic=metallic, Normal=bump.outputs[0])
    links.new(col, bsdf.inputs["Base Color"])
    links.new(bsdf.outputs[0], out.inputs["Surface"])
    return m


def _wire(name, yaw_deg):
    """Hutch wire mesh: light grey wire grid (Brick texture with square cells, mortar = wire) over a dark interior,
    in a coordinate (s along the hutch front, z)."""
    import math
    m, nodes, links, out = new_material(PREFIX + name)
    t = _Tree(nodes, links)
    tc = t.n("ShaderNodeTexCoord")
    sep = t.n("ShaderNodeSeparateXYZ", Vector=tc.outputs["Object"])
    c, s_ = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    sc = t.math("ADD", t.math("MULTIPLY", sep.outputs["X"], c), t.math("MULTIPLY", sep.outputs["Y"], s_))
    v = t.n("ShaderNodeCombineXYZ", X=sc, Y=sep.outputs["Z"])
    grid = t.n("ShaderNodeTexBrick", Vector=v.outputs[0], Color1=(0.012, 0.012, 0.01, 1), Color2=(0.02, 0.018, 0.015, 1),
               Mortar=_pal("wire", [150, 150, 146]), Scale=1.0, **{"Mortar Size": 0.004, "Bias": 0.0,
                                                                    "Brick Width": 0.025, "Row Height": 0.025})
    grid.offset = 0.0
    bsdf = t.n("ShaderNodeBsdfPrincipled", Roughness=0.6)
    links.new(grid.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bsdf.outputs[0], out.inputs["Surface"])
    return m


def _foliage(name):
    """Leaves/mound/blossoms: colour from nk_color (instance or geometry), a little translucency and sheen-free
    rough-waxy response; nk_rand varies roughness."""
    m, nodes, links, out = new_material(PREFIX + name)
    t = _Tree(nodes, links)
    a_inst = t.n("ShaderNodeAttribute", props={"attribute_type": "INSTANCER", "attribute_name": "nk_color"})
    a_geo = t.n("ShaderNodeAttribute", props={"attribute_type": "GEOMETRY", "attribute_name": "nk_color"})
    r_inst = t.n("ShaderNodeAttribute", props={"attribute_type": "INSTANCER", "attribute_name": "nk_rand"})
    col = t.n("ShaderNodeVectorMath", props={"operation": "MAXIMUM"})
    links.new(a_inst.outputs["Vector"], col.inputs[0])
    links.new(a_geo.outputs["Vector"], col.inputs[1])
    rough = t.n("ShaderNodeMapRange", Value=r_inst.outputs["Fac"], **{"To Min": 0.62, "To Max": 0.75})
    bsdf = t.n("ShaderNodeBsdfPrincipled", Roughness=rough.outputs[0])
    bsdf.inputs["Specular IOR Level"].default_value = 0.25   # matte leaves: no grey grazing sheen at distance
    links.new(col.outputs[0], bsdf.inputs["Base Color"])
    links.new(col.outputs[0], bsdf.inputs["Specular Tint"])  # sky reflection tinted by the leaf, not white
    trans = t.n("ShaderNodeBsdfTranslucent")
    links.new(col.outputs[0], trans.inputs["Color"])
    mix = t.n("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.12
    links.new(bsdf.outputs[0], mix.inputs[1])
    links.new(trans.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])
    m.use_backface_culling = False
    return m


def materials():
    p = load_params("boundary")
    bands = p.get("house_band_rows", [[0.95, 1.3, 2.6, 0.45]])
    _brick("Brick Red", ("brick_red_a", [150, 84, 62]), ("brick_red_b", [118, 66, 52]),
           ("mortar_red", [150, 138, 120]))
    _brick("Brick Stock", ("stock_a", [165, 145, 108]), ("stock_b", [138, 118, 88]),
           ("mortar_stock", [172, 162, 142]), band=("stock_band", [150, 78, 58]), band_rows=bands,
           stains=p.get("house_stains", 0.45), base_dark=p.get("house_base_dark", 0.45), base_height=1.0)
    _wire("Hutch Wire", p.get("hutch_yaw", -72.0))
    _brick("Brick Dark", ("dark_a", [96, 82, 60]), ("dark_b", [66, 56, 42]), ("mortar_dark", [112, 104, 88]),
           band=None, stains=0.75, base_dark=0.4, base_height=1.2)
    _plain("Render", ("render", [170, 166, 150]), 0.9, noise_scale=1.5, noise_amt=0.12)
    _plain("Roof Felt", ("roof", [72, 72, 74]), 0.8, noise_scale=6.0, noise_amt=0.1)
    _plain("Door Paint", ("door", [22, 22, 24]), 0.65, noise_scale=8.0, noise_amt=0.25)
    _plain("Mirror", ("mirror", [70, 80, 75]), 0.08, noise_scale=10.0, noise_amt=0.05, metallic=1.0)
    _plain("Terracotta Ring", ("plaque", [150, 80, 50]), 0.7)
    _wood("Fence Wood", ("fence_a", [86, 64, 48]), ("fence_b", [52, 38, 30]))
    _wood("Hutch Wood", ("hutch_a", [100, 66, 42]), ("hutch_b", [58, 38, 26]))
    _wood("Fence Edge", ("fence_edge_a", [150, 122, 92]), ("fence_edge_b", [110, 86, 62]))
    _wood("Deck Wood", ("deck_a", [104, 88, 68]), ("deck_b", [58, 48, 38]))
    _wood("Gate Wood", ("gate_a", [128, 116, 84]), ("gate_b", [88, 78, 56]))
    _foliage("Foliage")
    _plain("Bark", ("bark", [150, 136, 116]), 0.85, noise_scale=12.0, noise_amt=0.25)
    return {n: bpy.data.materials[PREFIX + n] for n in ("Brick Red", "Brick Stock", "Render", "Roof Felt",
                                                        "Door Paint", "Fence Wood", "Gate Wood", "Foliage",
                                                        "Mirror", "Terracotta Ring", "Bark", "Hutch Wood", "Hutch Wire", "Fence Edge", "Deck Wood", "Brick Dark")}

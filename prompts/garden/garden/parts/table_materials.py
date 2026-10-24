"""Procedural shaders for the garden table: weathered teak with directional fibres, and a thin honed slate disc.

Wood reads attributes stored by Geometry Nodes: nk_local (X = along the grain), nk_rand (per piece), nk_part
(0 plank, 1 frame timber), nk_end (end-grain faces), nk_edge (0 plank centre .. 1 long edge) and nk_wear
(Weathering control). Three scales: per-plank tone/roughness and broad silver weathering; in-plank patches, worn
edges, stains and cracks; fine fibres and bump. Colours are sRGB albedo picks calibrated against the references.
"""
import math

from garden.util import new_material, srgb_to_linear


class _N:
    """Tiny helper over a material node tree: n.new(type, **inputs), n.link(out, in)."""

    def __init__(self, nodes, links):
        self.nodes, self.links = nodes, links

    def new(self, idname, props=None, **inputs):
        node = self.nodes.new(idname)
        for k, v in (props or {}).items():
            setattr(node, k, v)
        for k, v in inputs.items():
            sock = node.inputs[k]
            if hasattr(v, "is_output"):
                self.links.new(v, sock)
            else:
                sock.default_value = v
        return node

    def attr(self, name, out="Fac"):
        a = self.new("ShaderNodeAttribute", props={"attribute_type": "GEOMETRY", "attribute_name": name})
        return a.outputs[out]

    def math(self, op, a, b=0.0, clamp=False):
        m = self.nodes.new("ShaderNodeMath")
        m.operation, m.use_clamp = op, clamp
        for i, v in enumerate((a, b)):
            if hasattr(v, "is_output"):
                self.links.new(v, m.inputs[i])
            else:
                m.inputs[i].default_value = v
        return m.outputs[0]

    def mix(self, fac, a, b, blend="MIX"):
        m = self.new("ShaderNodeMix", props={"data_type": "RGBA", "blend_type": blend, "clamp_result": True})
        for key, v in (("Factor", fac), ("A", a), ("B", b)):
            sock = next(s for s in m.inputs if s.name == key and s.enabled)
            if hasattr(v, "is_output"):
                self.links.new(v, sock)
            else:
                sock.default_value = v
        return next(s for s in m.outputs if s.name == "Result" and s.enabled)

    def ramp(self, fac, lo, hi):
        mr = self.new("ShaderNodeMapRange", props={"clamp": True}, Value=fac, **{"From Min": lo, "From Max": hi})
        return mr.outputs["Result"]


def _stretched(n, v, scale, **tex):
    """Noise on the grain-space vector, stretched by `scale` (X along the grain)."""
    vm = n.new("ShaderNodeVectorMath", props={"operation": "MULTIPLY"}, Vector=v)
    vm.inputs[1].default_value = scale
    return n.new("ShaderNodeTexNoise", Vector=vm.outputs[0], Scale=1.0, **tex).outputs["Fac"]


def _line(n, fac, width):
    """1 on a thin band where noise crosses 0.5 (crack / scratch lines), 0 elsewhere."""
    d = n.math("ABSOLUTE", n.math("SUBTRACT", fac, 0.5))
    return n.math("SUBTRACT", 1.0, n.ramp(d, 0.0, width))


def _wood_colour(n, p, v, rand, part, wear):
    """Base colour: fibres + in-plank patches, per-plank tone, silver weathering, uneven stain."""
    # per-board fibre frequency and phase so neighbouring planks never share a pattern
    r2 = n.math("FRACT", n.math("MULTIPLY", rand, 7.31))
    vp = n.new("ShaderNodeVectorMath", props={"operation": "SCALE"}, Vector=v)
    n.links.new(n.math("ADD", n.math("MULTIPLY", r2, 0.7), 0.75), vp.inputs["Scale"])
    vp = vp.outputs[0]
    fib = _stretched(n, vp, (1.0, 380.0, 380.0), Detail=6.0, Roughness=0.6, Distortion=0.15)
    fine = _stretched(n, v, (3.0, 900.0, 900.0), Detail=3.0)
    patch = _stretched(n, v, (7.0, 20.0, 20.0), Detail=4.0, Roughness=0.7, Distortion=0.8)
    patch2 = _stretched(n, v, (9.0, 40.0, 40.0), Detail=3.0, Roughness=0.6)
    streak = n.ramp(fib, 0.4, 0.62)
    pf = n.ramp(n.math("ADD", n.math("MULTIPLY", patch, 0.7), n.math("MULTIPLY", patch2, 0.3)), 0.4, 0.6)
    # board-scale blotches (near-isotropic, 5-10 cm) break the long radial banding
    blotch = n.ramp(_stretched(n, v, (12.0, 16.0, 16.0), Detail=5.0, Roughness=0.7, Distortion=1.2), 0.35, 0.65)
    tone = n.math("ADD", n.math("ADD", n.math("MULTIPLY", pf, 0.25), n.math("MULTIPLY", streak, 0.1)),
                  n.math("ADD", n.math("MULTIPLY", n.ramp(fine, 0.3, 0.7), 0.15), n.math("MULTIPLY", blotch, 0.5)))
    wood = p.get("wood_rgb_srgb", [206, 166, 122])
    col = n.mix(tone, srgb_to_linear([int(c * 0.72) for c in wood]), srgb_to_linear(wood))
    hsv = n.new("ShaderNodeHueSaturation", Hue=0.5, Color=col)
    n.links.new(n.math("ADD", n.math("MULTIPLY", rand, 0.5), 0.68), hsv.inputs["Value"])
    n.links.new(n.math("ADD", n.math("MULTIPLY", rand, -0.22), 1.06), hsv.inputs["Saturation"])
    col = hsv.outputs[0]
    col = n.mix(n.math("MULTIPLY", part, 0.85), col, srgb_to_linear(p.get("wood_structure_rgb_srgb", [92, 68, 48])))
    # silver weathering: irregular patches that grow with Weathering, fibres still showing through
    geo = n.new("ShaderNodeNewGeometry").outputs["Position"]
    broad = n.new("ShaderNodeTexNoise", Vector=geo, Scale=5.0, Detail=5.0, Roughness=0.7, Distortion=0.5).outputs["Fac"]
    smask = n.math("ADD", n.math("MULTIPLY", broad, 0.7), n.math("MULTIPLY", patch, 0.3))
    lo = n.math("SUBTRACT", 0.72, n.math("MULTIPLY", wear, 0.42))
    silver = n.math("MULTIPLY", n.ramp(n.math("SUBTRACT", smask, lo), 0.0, 0.12), n.math("ADD", n.math("MULTIPLY", wear, 0.6), 0.2))
    silver = n.math("MULTIPLY", n.math("MULTIPLY", silver, 0.75), n.math("SUBTRACT", 1.0, n.math("MULTIPLY", part, 0.8)))
    silver_col = n.mix(streak, srgb_to_linear([128, 124, 118]), srgb_to_linear([178, 172, 164]))
    col = n.mix(silver, col, silver_col)
    # uneven stain: broad value variation in world space
    stain = n.new("ShaderNodeTexNoise", Vector=geo, Scale=1.4, Detail=2.0).outputs["Fac"]
    col = n.mix(n.math("MULTIPLY", n.ramp(stain, 0.3, 0.6), 0.25), col, srgb_to_linear([68, 60, 52]), blend="MULTIPLY")
    blot = n.math("MULTIPLY", n.ramp(n.math("ADD", n.math("MULTIPLY", patch, 0.6), n.math("MULTIPLY", stain, 0.4)), 0.56, 0.66),
                  n.math("ADD", n.math("MULTIPLY", wear, 0.4), 0.4))
    col = n.mix(n.math("MULTIPLY", blot, 0.4), col, srgb_to_linear([68, 60, 52]), blend="MULTIPLY")
    # overall weathered grey cast, scaled by Weathering (keeps chroma near the reference's)
    col = n.mix(n.math("MULTIPLY", wear, 0.15), col, srgb_to_linear([120, 110, 100]))
    # fine sharp fibre lines along the grain, broken irregularly (not smooth streaks)
    r2 = n.math("FRACT", n.math("MULTIPLY", rand, 7.31))
    r3 = n.math("FRACT", n.math("MULTIPLY", rand, 3.77))
    vp = n.new("ShaderNodeVectorMath", props={"operation": "SCALE"}, Vector=v)
    n.links.new(n.math("ADD", n.math("MULTIPLY", r2, 0.7), 0.75), vp.inputs["Scale"])
    lines = _line(n, _stretched(n, vp.outputs[0], (0.3, 900.0, 900.0), Detail=1.0), 0.02)
    breaks = n.ramp(_stretched(n, v, (7.0, 25.0, 25.0), Detail=3.0), 0.45, 0.6)
    strength = n.math("ADD", n.math("MULTIPLY", r3, 0.3), 0.12)
    fibre_lines = n.math("MULTIPLY", n.math("MULTIPLY", lines, breaks), strength)
    col = n.mix(fibre_lines, col, srgb_to_linear([66, 50, 36]), blend="MULTIPLY")
    return col, pf, silver, fib, fine


def _wood_wear(n, p, col, v, local, part, wear, end, edge):
    """Edge/joint/end darkening, pale worn edges, cracks, sparse pale marks, end grain, centre hole, soil contact."""
    plank = n.math("SUBTRACT", 1.0, part)
    pos = n.new("ShaderNodeSeparateXYZ", Vector=local).outputs
    jag = _stretched(n, v, (12.0, 12.0, 12.0), Detail=3.0)
    rim = n.ramp(n.math("ADD", pos[0], n.math("MULTIPLY", jag, 0.06)), 0.72, 0.8)
    inner = n.math("SUBTRACT", 1.0, n.ramp(n.math("SUBTRACT", pos[0], n.math("MULTIPLY", jag, 0.06)), 0.28, 0.37))
    rand = n.attr("nk_rand")
    seam_w = n.math("ADD", edge, n.math("ADD", n.math("MULTIPLY", jag, 0.012), n.math("MULTIPLY", rand, 0.012)))
    along = _stretched(n, v, (9.0, 2.0, 2.0), Detail=2.0)
    seam = n.math("MULTIPLY", n.ramp(seam_w, 0.988, 1.005), n.ramp(along, 0.25, 0.6))
    patchy = n.ramp(_stretched(n, v, (14.0, 18.0, 18.0), Detail=4.0, Distortion=1.0), 0.3, 0.7)
    ends = n.math("MULTIPLY", n.math("MAXIMUM", rim, n.math("MULTIPLY", inner, 0.8)), patchy)
    dark = n.math("MULTIPLY", n.math("MAXIMUM", ends, seam), plank)
    col = n.mix(n.math("MULTIPLY", dark, 0.55), col, srgb_to_linear([52, 40, 30]), blend="MULTIPLY")
    # pale worn bevel along the long edges, broken up by noise, stronger with Weathering
    worn = n.math("MULTIPLY", n.math("MULTIPLY", n.ramp(edge, 0.86, 0.97), n.math("SUBTRACT", 1.0, seam)),
                  n.ramp(jag, 0.45, 0.65))
    worn = n.math("MULTIPLY", n.math("MULTIPLY", worn, plank), n.math("ADD", n.math("MULTIPLY", wear, 0.6), 0.1))
    col = n.mix(worn, col, srgb_to_linear([182, 168, 150]))
    # cracks: sparse thin dark lines along the grain, more of them with Weathering
    crk = _line(n, _stretched(n, v, (1.0, 220.0, 220.0), Detail=1.0), 0.01)
    cmask = n.ramp(_stretched(n, v, (5.0, 6.0, 6.0), Detail=2.0), n.math("SUBTRACT", 0.75, n.math("MULTIPLY", wear, 0.2)), 0.8)
    crack = n.math("MULTIPLY", n.math("MULTIPLY", crk, cmask), n.math("ADD", n.math("MULTIPLY", wear, 0.35), 0.05))
    col = n.mix(crack, col, srgb_to_linear([40, 30, 22]))
    # sparse irregular pale marks along the grain
    geo = n.new("ShaderNodeNewGeometry").outputs["Position"]
    gate = n.new("ShaderNodeTexNoise", Vector=geo, Scale=3.0, Detail=3.0).outputs["Fac"]
    marks = _stretched(n, v, (6.0, 60.0, 60.0), Detail=4.0, Roughness=0.7, Distortion=1.5)
    pale = n.math("MULTIPLY", n.math("MULTIPLY", n.ramp(marks, 0.62, 0.7), n.ramp(gate, 0.45, 0.55)), wear)
    col = n.mix(n.math("MULTIPLY", pale, 0.85), col, srgb_to_linear([196, 186, 170]))
    # end grain: dark, rough, with faint rings
    rings = n.new("ShaderNodeTexWave", props={"wave_type": "RINGS", "rings_direction": "X"}, Vector=v, Scale=40.0,
                  Distortion=4.0).outputs["Fac"]
    endc = n.mix(n.math("MULTIPLY", rings, 0.4), srgb_to_linear([34, 26, 19]), srgb_to_linear([66, 52, 38]))
    col = n.mix(end, col, endc)
    gz = n.new("ShaderNodeSeparateXYZ", Vector=geo).outputs
    # umbrella hole through the centre of the X foot (close_legs reference)
    rad = n.new("ShaderNodeVectorMath", props={"operation": "LENGTH"},
                Vector=n.new("ShaderNodeCombineXYZ", X=gz[0], Y=gz[1]).outputs[0]).outputs["Value"]
    hole = n.math("MULTIPLY", n.math("SUBTRACT", 1.0, n.ramp(rad, 0.019, 0.023)), n.math("GREATER_THAN", gz[2], 0.06))
    col = n.mix(n.math("MULTIPLY", hole, part), col, srgb_to_linear([12, 10, 8]))
    # soil contact: dirty, darker bottom few centimetres of the foot
    soil = n.math("MULTIPLY", n.math("SUBTRACT", 1.0, n.ramp(n.math("ADD", gz[2], n.math("MULTIPLY", jag, 0.03)), 0.0, 0.05)), part)
    col = n.mix(n.math("MULTIPLY", soil, 0.8), col, srgb_to_linear([46, 38, 30]))
    return col, crack, worn, pale, hole


def _wood(p):
    m, nodes, links, out = new_material("Garden Table Wood")
    n = _N(nodes, links)
    local = n.attr("nk_local", "Vector")
    rand, part, wear = n.attr("nk_rand"), n.attr("nk_part"), n.attr("nk_wear")
    end, edge = n.attr("nk_end"), n.attr("nk_edge")
    shift = n.new("ShaderNodeCombineXYZ", X=n.math("MULTIPLY", rand, 17.3), Y=n.math("MULTIPLY", rand, 5.1),
                  Z=n.math("MULTIPLY", rand, 3.7)).outputs[0]
    v = n.new("ShaderNodeVectorMath", props={"operation": "ADD"}, Vector=local).outputs[0]
    links.new(shift, v.node.inputs[1])
    col, pf, silver, fib, fine = _wood_colour(n, p, v, rand, part, wear)
    col, crack, worn, pale, hole = _wood_wear(n, p, col, v, local, part, wear, end, edge)
    # weathered fibres scatter light: paler neutral grey at grazing angles
    facing = n.new("ShaderNodeLayerWeight", Blend=0.5).outputs["Facing"]
    graze = n.math("MULTIPLY", n.ramp(facing, 0.6, 0.95), n.math("ADD", n.math("MULTIPLY", wear, 0.3), 0.1))
    graze = n.math("MULTIPLY", graze, n.math("SUBTRACT", 1.0, part))
    col = n.mix(graze, col, srgb_to_linear([196, 188, 178]))
    bsdf = n.new("ShaderNodeBsdfPrincipled")
    links.new(col, bsdf.inputs["Base Color"])
    # per-plank roughness, smoother patches, rougher silver/worn/end grain
    rough = n.math("ADD", n.math("MULTIPLY", rand, 0.14), 0.62)
    rough = n.math("ADD", rough, n.math("MULTIPLY", n.ramp(pf, 0.5, 0.9), -0.16))
    rough = n.math("ADD", rough, n.math("MULTIPLY", part, 0.3))
    rough = n.math("ADD", rough, n.math("MULTIPLY", n.math("MAXIMUM", n.math("MAXIMUM", silver, worn), pale), 0.14))
    rough = n.math("MAXIMUM", rough, n.math("MULTIPLY", end, 0.85))
    links.new(rough, bsdf.inputs["Roughness"])
    height = n.math("ADD", n.math("ADD", fib, n.math("MULTIPLY", fine, 0.5)), n.math("MULTIPLY", crack, -0.8))
    bump = n.new("ShaderNodeBump", Strength=0.35, Distance=0.002, Height=n.math("SUBTRACT", height, n.math("MULTIPLY", hole, 3.0)))
    links.new(bump.outputs[0], bsdf.inputs["Normal"])
    bsdf.inputs["Specular IOR Level"].default_value = 0.28
    links.new(n.math("MULTIPLY", n.math("SUBTRACT", 1.0, part), 0.2), bsdf.inputs["Sheen Weight"])
    bsdf.inputs["Sheen Roughness"].default_value = 0.3
    bsdf.inputs["Sheen Tint"].default_value = srgb_to_linear([235, 232, 226])
    links.new(bsdf.outputs[0], out.inputs["Surface"])
    return m


def _slate(p):
    """Thin honed slate: soft mottled tone, scratch- and pit-driven roughness, worn paler rim."""
    m, nodes, links, out = new_material("Garden Table Slate")
    n = _N(nodes, links)
    geo = n.new("ShaderNodeNewGeometry").outputs["Position"]
    wear = n.attr("nk_wear")
    mottle = n.new("ShaderNodeTexNoise", Vector=geo, Scale=12.0, Detail=6.0, Roughness=0.65, Distortion=0.6).outputs["Fac"]
    cloud = n.new("ShaderNodeTexNoise", Vector=geo, Scale=18.0, Detail=4.0, Roughness=0.6).outputs["Fac"]
    base_c = p.get("slate_rgb_srgb", [92, 91, 82])
    m_t = n.ramp(n.math("ADD", n.math("MULTIPLY", mottle, 0.7), n.math("MULTIPLY", cloud, 0.3)), 0.32, 0.68)
    col = n.mix(m_t, srgb_to_linear([int(c * 0.45) for c in base_c]), srgb_to_linear([int(c * 1.25) for c in base_c]))
    col = n.mix(n.math("MULTIPLY", n.ramp(n.math("ADD", mottle, n.math("MULTIPLY", cloud, 0.3)), 0.75, 0.95), 0.7), col,
                srgb_to_linear([int(c * 1.35) + 4 for c in base_c]))
    # scratches: two families of long thin lines in different directions, gated sparsely
    scr = None
    for k, (sx, sy) in enumerate(((1.0, 0.35), (-0.45, 1.0))):
        d = n.new("ShaderNodeVectorMath", props={"operation": "DOT_PRODUCT"}, Vector=geo)
        d.inputs[1].default_value = (sx, sy, 0.0)
        dv = n.new("ShaderNodeCombineXYZ", X=n.math("MULTIPLY", d.outputs["Value"], 1.0), Y=float(k) * 3.1).outputs[0]
        lines = _line(n, n.new("ShaderNodeTexNoise", Vector=dv, Scale=55.0, Detail=1.0).outputs["Fac"], 0.002)
        gate = n.ramp(n.new("ShaderNodeTexNoise", Vector=geo, Scale=11.0 + 4 * k, Detail=2.0).outputs["Fac"], 0.55, 0.65)
        s = n.math("MULTIPLY", lines, gate)
        scr = s if scr is None else n.math("MAXIMUM", scr, s)
    scr = n.math("MULTIPLY", scr, n.math("ADD", n.math("MULTIPLY", wear, 0.4), 0.1))
    vor = n.new("ShaderNodeTexVoronoi", Vector=geo, Scale=140.0).outputs["Distance"]
    pits = n.math("MULTIPLY", n.math("SUBTRACT", 1.0, n.ramp(vor, 0.05, 0.11)),
                  n.ramp(n.new("ShaderNodeTexNoise", Vector=geo, Scale=25.0).outputs["Fac"], 0.55, 0.62))
    col = n.mix(n.math("MULTIPLY", scr, 0.04), col, srgb_to_linear([120, 118, 112]))
    col = n.mix(n.math("MULTIPLY", pits, 0.6), col, srgb_to_linear([138, 134, 126]))
    # worn paler, rougher rim
    xy = n.new("ShaderNodeVectorMath", props={"operation": "MULTIPLY"}, Vector=geo)
    xy.inputs[1].default_value = (1.0, 1.0, 0.0)
    rad = n.new("ShaderNodeVectorMath", props={"operation": "LENGTH"}, Vector=xy.outputs[0]).outputs["Value"]
    disc_r = p.get("disc_radius", 0.286)
    rim = n.ramp(rad, disc_r - 0.007, disc_r - 0.002)
    col = n.mix(n.math("MULTIPLY", rim, 0.18), col, srgb_to_linear([150, 148, 140]))
    bsdf = n.new("ShaderNodeBsdfPrincipled")
    links.new(col, bsdf.inputs["Base Color"])
    rough = n.math("ADD", n.math("MULTIPLY", m_t, 0.18), 0.4)
    rough = n.math("ADD", rough, n.math("MULTIPLY", n.math("MAXIMUM", n.math("MAXIMUM", scr, pits), rim), 0.2))
    links.new(rough, bsdf.inputs["Roughness"])
    fine = n.new("ShaderNodeTexNoise", Vector=geo, Scale=60.0, Detail=2.0).outputs["Fac"]
    bump = n.new("ShaderNodeBump", Strength=0.12, Distance=0.001,
                 Height=n.math("SUBTRACT", fine, n.math("ADD", n.math("MULTIPLY", scr, 0.5), pits)))
    links.new(bump.outputs[0], bsdf.inputs["Normal"])
    links.new(bsdf.outputs[0], out.inputs["Surface"])
    return m


def build(p):
    """Create/rebuild both table materials (get-or-create, nodes rebuilt each call)."""
    return _wood(p), _slate(p)

"""Garden part 'vase': the rough flattened gourd-like vessel on the table's centre disc and its dried arrangement.

Top group "Garden Vase" = "Garden Vase Vessel" (an elliptical lathe: one unrolled profile -- outer wall, rolled lip
and inner wall -- read through Float Curves, low-frequency lumps and two modelled side holes) + "Garden Vase Dried
Arrangement" (garden/parts/vase_arrangement.py: palm fan, orange pod fronds, seed heads, stems). Fitted numbers come
from data/params/vase.json (scripts/analyze_vase.py). Shaders are in garden/parts/vase_materials.py.
"""
import math

from nodekit.graph import Graph, once

from garden.parts import vase_arrangement, vase_materials
from garden.parts import vase_nodes as vn
from garden.util import load_params

P = load_params("vase")
VP = P.get("vessel", {})


def materials():
    vase_materials.build(P)


def _wrap(g, a):
    """Angle difference wrapped to (-pi, pi]."""
    return g.math("ARCTAN2", g.math("SINE", a), g.math("COSINE", a))


def _w_at(zh):
    """Profile parameter w where the outer wall reaches height fraction zh (inverse of the fitted profile)."""
    pts = VP.get("profile_outer", [[0, 0, 0], [1, 1, 1]])
    for (w0, _, z0), (w1, _, z1) in zip(pts, pts[1:]):
        if z0 <= zh <= z1:
            return w0 + (w1 - w0) * (zh - z0) / max(z1 - z0, 1e-6)
    return pts[-1][0]


def _ramp(g, v, lo, hi):
    return g.map_range(v, lo, hi, 0.0, 1.0, interp="SMOOTHSTEP").out


def _hole_warp(g, phi, w, zf, a, b, height, hole, size):
    """One round hole: inside its radius, (phi, w) are pushed out onto the circle (so the rim is a true circle)
    and an inset 0..1 says how deep into the wall the vertex goes. Returns (dphi, dw, inset)."""
    ph, zh, rh = math.radians(hole[0]), hole[1], hole[2]
    wh = _w_at(zh)
    rad = g.math("MAXIMUM", g.math("MULTIPLY", size, rh), 1e-4)
    dphi = _wrap(g, g.math("SUBTRACT", phi, ph))
    metric = g.vmath("LENGTH", g.combine(g.math("MULTIPLY", a, g.math("SINE", phi)),
                                         g.math("MULTIPLY", b, g.math("COSINE", phi))))["Value"]
    dist = g.math("MAXIMUM", g.vmath("LENGTH", g.combine(
        g.math("MULTIPLY", dphi, metric), g.math("MULTIPLY", g.math("SUBTRACT", zf, zh), height)))["Value"], 1e-5)
    inside = g.math("LESS_THAN", dist, rad)
    grow = g.math("MULTIPLY", inside, g.math("SUBTRACT", g.math("DIVIDE", rad, dist), 1.0))
    inset = g.math("MULTIPLY", inside, g.math("SUBTRACT", 1.0, g.math("DIVIDE", dist, rad)))
    return (g.math("MULTIPLY", dphi, grow), g.math("MULTIPLY", g.math("SUBTRACT", w, wh), grow), inset)


@once
def vessel():
    g = Graph("Garden Vase Vessel",
              description="Flattened gourd vessel: an elliptical lathe of one unrolled profile (outer wall, lip, "
                          "inner wall), asymmetric shoulder/lip and bulge, low-frequency lumps and two round side "
                          "holes tunnelled through the wall; base at the origin, major axis along +X")
    height = g.input("Height", "FLOAT", VP.get("height", 0.288), min=0.05, max=1.0, subtype="DISTANCE",
                     desc="Base to rim height")
    semi = g.input("Semi Major", "FLOAT", VP.get("semi_major", 0.153), min=0.02, max=0.5, subtype="DISTANCE",
                   desc="Largest half-width along the major axis (X)")
    flat = g.input("Flatten", "FLOAT", 1.0, min=0.3, max=2.2, desc="Multiplier on the fitted minor/major ratio "
                   "(1 = measured flattened ellipse, about 2.2 = round)")
    asym = g.input("Asymmetry", "FLOAT", 1.0, min=0.0, max=3.0, desc="Multiplier on the fitted shoulder shift, "
                   "uneven lip and low bulge (0 = symmetric lathe)")
    lump = g.input("Lumpiness", "FLOAT", VP.get("lumpiness", 0.05), min=0.0, max=0.3, subtype="FACTOR",
                   desc="Radial low-frequency irregularity as a share of the radius")
    hole = g.input("Hole Size", "FLOAT", 1.0, min=0.0, max=3.0, desc="Multiplier on the measured hole radii "
                   "(0 closes the holes)")
    wear = g.input("Weathering", "FLOAT", 0.6, min=0.0, max=1.0, subtype="FACTOR",
                   desc="Amount of dark weathered patches (stored as vase_wear for the shader)")
    seed = g.input("Seed", "INT", 0, min=0, max=10000, desc="Noise seed for the lumps")
    seg = g.input("Segments", "INT", 360, min=12, max=512, desc="Vertices around")
    rings = g.input("Rings", "INT", 260, min=8, max=512, desc="Rings along the unrolled profile")
    prof = VP.get("profile_outer", []) + VP.get("profile_lip", [])
    asy = VP.get("asymmetry", {})

    with g.frame("Unit cylinder: w = z + 0.5 runs along the unrolled profile, phi around"):
        cyl = g.node("GeometryNodeMeshCylinder", props={"fill_type": "NONE"}, Vertices=seg,
                     **{"Side Segments": rings, "Radius": 1.0, "Depth": 1.0})["Mesh"]
        p = g.separate(g.node("GeometryNodeInputPosition"))
        w0 = g.math("ADD", p["Z"], 0.5)
        phi0 = g.math("ARCTAN2", p["Y"], p["X"])
    with g.frame("Holes: measure surface distance to each hole on the unshaped profile; warp onto circles"):
        zf0 = vn.float_curve(g, w0, [(q[0], q[2]) for q in prof], "height (hole distance)")
        a0 = g.math("MULTIPLY", vn.float_curve(g, w0, [(q[0], q[1]) for q in prof], "radius (hole distance)"), semi)
        b0 = g.math("MULTIPLY", a0, 0.47)
        outer_end = VP.get("profile_outer", [[0.74]])[-1][0]
        on_outer = g.math("LESS_THAN", w0, outer_end)
        dphi, dw, inset = 0.0, 0.0, 0.0
        for h in VP.get("holes", []):
            hp, hw, hi = _hole_warp(g, phi0, w0, zf0, a0, b0, height, h, hole)
            dphi, dw, inset = g.math("ADD", dphi, hp), g.math("ADD", dw, hw), g.math("MAXIMUM", inset, hi)
        inset = g.math("MULTIPLY", inset, on_outer)
        phi = g.math("ADD", phi0, g.math("MULTIPLY", dphi, on_outer))
        w = g.math("ADD", w0, g.math("MULTIPLY", dw, on_outer))
    with g.frame("Fitted profile: radius and height along w, minor/major ratio along height"):
        r = vn.float_curve(g, w, [(q[0], q[1]) for q in prof], "radius / semi major")
        zf = vn.float_curve(g, w, [(q[0], q[2]) for q in prof], "height / Height")
        k = vn.float_curve(g, zf, [tuple(q) for q in VP.get("minor_ratio", [[0, 0.5], [1, 0.5]])], "minor / major")
        k = g.math("MINIMUM", g.math("MULTIPLY", k, flat), 1.0)
    with g.frame("Low-frequency lumps (seamless around phi) and the low +X bulge scale the radius"):
        nz = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "4D"},
                    Vector=g.combine(g.math("COSINE", phi), g.math("SINE", phi), g.math("MULTIPLY", zf, 1.3)),
                    W=g.math("MULTIPLY", seed, 7.31), Scale=1.1, Detail=2.0, Roughness=0.5)["Fac"]
        bump = g.math("MULTIPLY_ADD", g.math("SUBTRACT", nz, 0.5), g.math("MULTIPLY", lump, 2.0), 1.0)
        # egg lean: +X flank fuller low, -X flank fuller high (an S-shaped, tilted-egg profile)
        tilt = g.math("SUBTRACT", g.math("MULTIPLY", _ramp(g, zf, 0.65, 0.15), asy.get("low_bulge", 0.05)),
                      g.math("MULTIPLY", _ramp(g, zf, 0.4, 0.85), asy.get("high_bulge", 0.0)))
        bulge = g.math("MULTIPLY", g.math("MULTIPLY", asym, tilt), g.math("COSINE", phi))
        a = g.math("MULTIPLY", g.math("MULTIPLY", r, semi), g.math("ADD", bump, bulge))
        b = g.math("MULTIPLY", a, k)
    with g.frame("Shape: ellipse, shoulder shifted toward -X, lip height varying around; holes tunnel inward"):
        top = _ramp(g, w, 0.45, outer_end)
        shift = g.math("MULTIPLY", g.math("MULTIPLY", asym, asy.get("shoulder_shift", -0.012)), top)
        lip = g.math("MULTIPLY", g.math("MULTIPLY", asym, asy.get("lip_amplitude", 0.012)),
                     g.math("MULTIPLY", _ramp(g, w, outer_end - 0.12, outer_end),
                            g.math("SINE", g.math("ADD", phi, math.radians(asy.get("lip_phase_deg", -90.0))))))
        nrm = g.vmath("NORMALIZE", g.combine(g.math("MULTIPLY", b, g.math("COSINE", phi)),
                                             g.math("MULTIPLY", a, g.math("SINE", phi)), 0.0))
        tunnel = g.vmath("SCALE", nrm, scale=g.math("MULTIPLY", inset, -VP.get("hole_depth", 0.04)))
        hgt = g.math("MULTIPLY", zf, height)
        lean_u = g.math("MULTIPLY", g.math("MULTIPLY", asym, asy.get("lean_du_dz", 0.0)), hgt)
        lean_v = g.math("MULTIPLY", g.math("MULTIPLY", asym, asy.get("lean_dv_dz", 0.0)), hgt)
        pos = g.vmath("ADD", g.combine(g.math("ADD", g.math("MULTIPLY_ADD", a, g.math("COSINE", phi), shift), lean_u),
                                       g.math("MULTIPLY_ADD", b, g.math("SINE", phi), lean_v),
                                       g.math("MULTIPLY_ADD", zf, height, lip)), tunnel)
        local = g.combine(g.math("COSINE", phi), g.math("SINE", phi), zf)
        geo = vn.store(g, cyl, "vase_local", local, dtype="FLOAT_VECTOR")
        geo = vn.store(g, geo, "vase_wear", wear)
        geo = vn.store(g, geo, "vase_inset", inset)
        geo = g.node("GeometryNodeSetPosition", Geometry=geo, Position=pos.out)["Geometry"]
    with g.frame("Open the far end of each tunnel (a real opening; the tunnel wall stays visible)"):
        deep = g.math("GREATER_THAN", vn.named(g, "vase_inset"), 0.7)
        geo = g.node("GeometryNodeDeleteGeometry", props={"domain": "FACE"}, Geometry=geo,
                     Selection=deep)["Geometry"]
        geo = vn.smooth(g, geo)
    g.output("Mesh", "GEOMETRY", geo, desc="The vessel mesh (local frame)")
    return g.finish()


def build():
    vp, ap = VP, P.get("arrangement", {})
    g = Graph("Garden Vase", kind="GEOMETRY", modifier=True,
              description="The dried-flower vessel on the table centre: fitted flattened gourd vessel plus its "
                          "dried arrangement (palm fan, orange pod fronds, seed heads), realized with materials")
    seed = g.input("Seed", "INT", 0, min=0, max=10000, desc="Random seed for lumps and per-leaf variation")
    vscale = g.input("Vessel Scale", "FLOAT", 1.0, min=0.5, max=2.0, desc="Uniform scale of the vessel about its base")
    lump = g.input("Lumpiness", "FLOAT", vp.get("lumpiness", 0.05), min=0.0, max=0.3, subtype="FACTOR",
                   desc="Vessel low-frequency irregularity")
    hole = g.input("Hole Size", "FLOAT", 1.0, min=0.0, max=3.0, desc="Multiplier on the measured side-hole radii")
    asym = g.input("Asymmetry", "FLOAT", 1.0, min=0.0, max=3.0,
                   desc="Vessel shoulder shift, uneven lip and low bulge (0 = symmetric lathe)")
    wear = g.input("Weathering", "FLOAT", 0.6, min=0.0, max=1.0, subtype="FACTOR",
                   desc="Dark weathered patches on the vessel")
    ascale = g.input("Arrangement Scale", "FLOAT", 1.0, min=0.3, max=2.5,
                     desc="Uniform scale of the dried arrangement about the vessel mouth")
    blades = g.input("Fan Blades", "INT", ap.get("fan", {}).get("blades", 24), min=3, max=60,
                     desc="Number of blades in the palm fan")
    density = g.input("Pod Density", "FLOAT", 1.0, min=0.2, max=3.0, desc="Multiplier on leaves per pod frond")
    with g.frame("Vessel in its own frame, rotated to the fitted major axis and set on the disc"):
        v = g.group(vessel(), **{"Lumpiness": lump, "Hole Size": hole, "Asymmetry": asym, "Weathering": wear, "Seed": seed})["Mesh"]
        v = g.node("GeometryNodeSetMaterial", Geometry=v, Material=vase_materials.vessel_material())["Geometry"]
        lean = [math.radians(x) for x in vp.get("lean_deg", [0.0, 0.0])]
        v = vn.xf(g, v, r=(lean[0], lean[1], math.radians(vp.get("major_axis_deg", 46.0))),
                  s=g.combine(vscale, vscale, vscale))
        c = vp.get("centre", [-0.04, 0.015])
        v = vn.xf(g, v, t=(c[0], c[1], vp.get("base_z", 0.752)))
    with g.frame("Dried arrangement in its plane frame, moved to the vessel mouth"):
        rim = vp.get("base_z", 0.752) + vp.get("height", 0.288)
        arr = g.group(vase_arrangement.arrangement(), **{"Seed": seed, "Fan Blades": blades,
                                                         "Pod Density": density})["Geometry"]
        mouth = g.math("MULTIPLY_ADD", vscale, vp.get("height", 0.288), vp.get("base_z", 0.752))
        o = ap.get("origin", [-0.04, 0.015])
        arr = vn.xf(g, arr, t=(0.0, 0.0, -rim))
        arr = vn.xf(g, arr, r=(0.0, 0.0, math.radians(ap.get("plane_deg", 55.0))),
                    s=g.combine(ascale, ascale, ascale))
        arr = vn.xf(g, arr, t=g.combine(o[0], o[1], mouth))
    with g.frame("Join and realize once (shaders read point attributes)"):
        out = g.node("GeometryNodeRealizeInstances", Geometry=vn.join(g, v, arr))["Geometry"]
    g.output("Geometry", "GEOMETRY", out, desc="Vessel and arrangement, world space")
    return g.finish()

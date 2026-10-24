"""Ground surface (soil / joint bed / terrace) and the patchy lawn of instanced grass tufts, plus the concrete path
strips and stepping stones beyond the lawn."""
import math

import bpy
from nodekit.graph import Graph, once
from library.shapes import grass_tuft, leaf

from garden.parts.ground_fields import P, ground_height, lawn_outline, lawn_tone, paving_boundary, polyline, smooth01
from garden.parts.ground_slab import hex_slab


def mat(name):
    return bpy.data.materials[name]


def _rand(g, idx, lo, hi, seed, k):
    return g.node("FunctionNodeRandomValue", props={"data_type": "FLOAT"}, Min=lo, Max=hi, ID=idx,
                  Seed=g.math("ADD", seed, float(k)))["Value"]


def _store(g, geo, name, value, dtype="FLOAT", domain="POINT"):
    return g.node("GeometryNodeStoreNamedAttribute", props={"data_type": dtype, "domain": domain}, Geometry=geo,
                  Name=name, Value=value)["Geometry"]


@once
def ground_surface():
    g = Graph("Garden Ground Surface", description="The continuous ground: a 10 cm grid lifted to the fitted height "
                                                   "field, with masks for the paving joint bed, lawn soil and terrace "
                                                   "stored for the earth shader")
    sx = g.input("Size X", "FLOAT", 20.0, min=1.0, max=60.0, subtype="DISTANCE", desc="Ground extent along X")
    sy = g.input("Size Y", "FLOAT", 20.2, min=1.0, max=60.0, subtype="DISTANCE", desc="Ground extent along Y")
    res = g.input("Resolution", "FLOAT", 0.1, min=0.02, max=1.0, subtype="DISTANCE", desc="Grid spacing")
    with g.frame("Grid centred on the lawn, spacing = Resolution"):
        nx = g.math("ADD", g.math("CEIL", g.math("DIVIDE", sx, res)), 1.0)
        ny = g.math("ADD", g.math("CEIL", g.math("DIVIDE", sy, res)), 1.0)
        grid = g.node("GeometryNodeMeshGrid", **{"Size X": sx, "Size Y": sy, "Vertices X": nx, "Vertices Y": ny})
        grid = g.node("GeometryNodeTransform", Geometry=grid["Mesh"], Translation=(-1.0, -0.6, 0.0))
    with g.frame("Lift to the fitted height (joint bed sits 12 mm under the slab tops)"):
        pos = g.node("GeometryNodeInputPosition")
        h = g.group(ground_height(), Position=pos)
        pave = smooth01(g, h["Paving Margin"], -0.3, -0.24)
        z = g.math("SUBTRACT", h["Height"], g.math("MULTIPLY", pave, 0.009))
        xyz = g.separate(pos)
        geo = g.node("GeometryNodeSetPosition", Geometry=grid, Position=g.combine(xyz["X"], xyz["Y"], z))["Geometry"]
    with g.frame("Masks for the earth shader: gr_pave, gr_lawn, gr_terrace"):
        geo = _store(g, geo, "gr_pave", pave)
        lawn = smooth01(g, g.group(lawn_outline(), Position=pos)["Margin"], -0.45, -0.1)
        geo = _store(g, geo, "gr_lawn", lawn)
        geo = _store(g, geo, "gr_terrace", h["Terrace"])
        geo = _store(g, geo, "gr_yard", smooth01(g, xyz["Y"], -7.9, -8.4))
        geo = g.node("GeometryNodeSetShadeSmooth", Geometry=geo)
        geo = g.node("GeometryNodeSetMaterial", Geometry=geo, Material=mat("Garden Ground Earth"))
    pd = P["terrace"]["pond"]
    th = math.radians(P["terrace"]["frame_deg"])
    with g.frame("Pond water: a plane over the pond hole at the measured water level"):
        ca, cb = 0.5 * (pd["a"][0] + pd["a"][1]), 0.5 * (pd["b"][0] + pd["b"][1])
        cx, cy = ca * math.cos(th) - cb * math.sin(th), ca * math.sin(th) + cb * math.cos(th)
        water = g.node("GeometryNodeMeshGrid", **{"Size X": pd["a"][1] - pd["a"][0], "Size Y": pd["b"][1] - pd["b"][0],
                                                  "Vertices X": 2, "Vertices Y": 2})
        water = g.node("GeometryNodeTransform", Geometry=water["Mesh"], Translation=(cx, cy, pd["water_z"]),
                       Rotation=g.node("FunctionNodeEulerToRotation", Euler=(0.0, 0.0, th)))
        water = g.node("GeometryNodeSetMaterial", Geometry=water, Material=mat("Garden Ground Water"))
        both = g.node("GeometryNodeJoinGeometry")
        g.connect(water, both.i("Geometry"))
        g.connect(geo, both.i("Geometry"))
    g.output("Mesh", "GEOMETRY", both, desc="Ground mesh (gr_pave / gr_lawn / gr_terrace attributes) and pond water")
    return g.finish()


@once
def lawn():
    g = Graph("Garden Ground Lawn", description="Patchy lawn: grass tufts scattered on the ground inside the fitted "
                                               "lawn outline and outside the paving, thinned and yellowed by "
                                               "patch noise, creeping over the outer slabs")
    ground = g.input("Ground", "GEOMETRY", desc="Ground surface mesh (Garden Ground Surface)")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    dens = g.input("Density", "FLOAT", 3000.0, min=0.0, max=20000.0, desc="Grass tufts per square metre at full "
                                                                          "cover")
    height = g.input("Height", "FLOAT", 0.07, min=0.005, max=0.6, subtype="DISTANCE", desc="Tallest blade length")
    patchy = g.input("Patchiness", "FLOAT", 0.3, min=0.0, max=1.0, subtype="FACTOR",
                     desc="How strongly noise patches thin the lawn")
    terrace_cov = g.input("Terrace Cover", "FLOAT", 0.5, min=0.0, max=1.0, subtype="FACTOR",
                          desc="Peak grass/weed cover on the raised bed terrace soil")
    weeds = g.input("Weeds", "FLOAT", 6.0, min=0.0, max=100.0, desc="Broadleaf weed rosettes per square metre")
    creep = g.input("Edge Creep", "FLOAT", 0.35, min=-0.5, max=1.0, subtype="DISTANCE",
                    desc="How far grass grows in over the outer slabs")
    with g.frame("Cover field: inside lawn outline, outside the paving (minus creep), noise patches"):
        pos = g.node("GeometryNodeInputPosition")
        lawn_m = smooth01(g, g.group(lawn_outline(), Position=pos)["Margin"], -0.45, -0.1)
        pav_m = g.group(paving_boundary(), Position=pos)["Margin"]
        cn = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "2D"}, Vector=pos, Scale=3.0, Detail=3.0)
        ragged = g.math("MULTIPLY_ADD", g.math("SUBTRACT", cn["Fac"], 0.5), 0.9, creep)
        out_pave = smooth01(g, pav_m, ragged, g.math("SUBTRACT", ragged, 0.18))
        n1 = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "2D"}, Vector=pos, Scale=2.6, Detail=4.0,
                    Roughness=0.6)
        thin = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", smooth01(g, n1["Fac"], 0.54, 0.34), patchy))
        hh = g.group(ground_height(), Position=pos)
        terr = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, hh["Terrace"]), g.math("SUBTRACT", 1.0, hh["Pond"]))
        cover = g.math("MULTIPLY", g.math("MULTIPLY", lawn_m, out_pave), g.math("MULTIPLY", thin, terr))
        # bed terrace (close_trunk / hero rear): patchy grass and weeds over soil, about half covered
        tn = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "2D"}, Vector=pos, Scale=3.2, Detail=5.0,
                    Roughness=0.65)
        yard = smooth01(g, g.separate(pos)["Y"], -7.9, -8.4)
        t_cov = g.math("MULTIPLY", g.math("MULTIPLY", hh["Terrace"], g.math("SUBTRACT", 1.0, hh["Pond"])),
                       g.math("MULTIPLY", smooth01(g, tn["Fac"], 0.46, 0.6), terrace_cov))
        t_cov = g.math("MULTIPLY", t_cov, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", yard, 0.8)))
        cover = g.math("MAXIMUM", cover, t_cov)
    with g.frame("Scatter tuft points by cover x Density"):
        pts = g.node("GeometryNodeDistributePointsOnFaces", Mesh=ground, Density=dens, Seed=seed,
                     Selection=g.math("GREATER_THAN", cover, 0.02))
        pts = g.node("GeometryNodeDeleteGeometry", props={"domain": "POINT"}, Geometry=pts["Points"],
                     Selection=g.math("LESS_THAN", _rand(g, g.node("GeometryNodeInputIndex"), 0.0, 1.0, seed, 3),
                                      g.math("SUBTRACT", 1.0, cover)))["Geometry"]
    with g.frame("Per-tuft attributes: nk_rand, gr_dry (yellow patches), size from cover"):
        idx = g.node("GeometryNodeInputIndex")
        pos2 = g.node("GeometryNodeInputPosition")
        pts = _store(g, pts, "nk_rand", _rand(g, idx, 0.0, 1.0, seed, 4))
        dry = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "2D"}, Vector=pos2, Scale=0.55, Detail=3.0)
        edge = smooth01(g, g.group(paving_boundary(), Position=pos2)["Margin"], -0.5, 0.1)
        lt = g.group(lawn_tone(), Position=pos2)
        dryv = g.math("MAXIMUM", g.math("MULTIPLY", smooth01(g, dry["Fac"], 0.55, 0.72), 0.2),
                      g.math("MAXIMUM", g.math("MULTIPLY", edge, 0.35),
                             g.math("MULTIPLY", smooth01(g, lt["Dry"], 0.04, 0.25), 0.3)))
        pts = _store(g, pts, "gr_dry", dryv)
        lush = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "2D"}, Vector=pos2, Scale=1.3, Detail=5.0,
                      Roughness=0.65)
        tone = g.math("MULTIPLY", lt["Tone"], g.map_range(lush["Fac"], 0.3, 0.7, 0.88, 1.08)["Result"])
        pts = _store(g, pts, "gr_tone", tone)
        tall = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "2D"}, Vector=pos2, Scale=2.6, Detail=4.0)
        size = g.math("MULTIPLY", _rand(g, idx, 0.6, 1.2, seed, 5),
                      g.math("MULTIPLY", g.map_range(cover, 0.0, 1.0, 0.5, 1.0)["Result"],
                             g.map_range(tall["Fac"], 0.35, 0.65, 0.55, 1.2)["Result"]))
    with g.frame("Four tuft variants (NK Grass Tuft), picked at random"):
        lib = g.node("GeometryNodeJoinGeometry")
        for k, (blades, spread) in enumerate(((9, 0.45), (12, 0.6), (7, 0.35), (14, 0.75))):
            tuft = g.group(grass_tuft(), Blades=blades, Height=1.0, **{"Height Min": 0.45}, Radius=0.16,
                           Spread=spread, **{"Blade Width": 0.05}, Curl=0.35, Fold=0.5, Resolution=4, Seed=31 + k)
            g.connect(g.node("GeometryNodeGeometryToInstance", Geometry=tuft["Mesh"]), lib.i("Geometry"))
        lib = g.node("GeometryNodeSetMaterial", Geometry=lib, Material=mat("Garden Ground Grass"))
    with g.frame("Instance tufts: random yaw, scaled by Height x size"):
        rot = g.node("FunctionNodeEulerToRotation", Euler=g.combine(
            _rand(g, idx, -0.12, 0.12, seed, 6), _rand(g, idx, -0.12, 0.12, seed, 7),
            _rand(g, idx, 0.0, 6.283, seed, 8)))
        sc = g.math("MULTIPLY", height, size)
        inst = g.node("GeometryNodeInstanceOnPoints", Points=pts, Instance=lib, **{"Pick Instance": True},
                      **{"Instance Index": g.node("FunctionNodeRandomValue", props={"data_type": "INT"}, Min=0,
                                                  Max=3, ID=idx, Seed=g.math("ADD", seed, 9.0))["Value"]},
                      Rotation=rot, Scale=sc)
    with g.frame("Broadleaf weeds (plantain / clover-like rosettes) sprinkled through the turf"):
        wp = g.node("GeometryNodeDistributePointsOnFaces", Mesh=ground, Density=g.math("MULTIPLY", weeds, g.math("MULTIPLY_ADD", t_cov, 4.0, 1.0)),
                    Seed=g.math("ADD", seed, 77.0), Selection=g.math("GREATER_THAN", g.math("ADD", cover, g.math("MULTIPLY", t_cov, 3.0)), 0.3))["Points"]
        widx = g.node("GeometryNodeInputIndex")
        wp = _store(g, wp, "nk_rand", _rand(g, widx, 0.0, 1.0, seed, 78))
        wrot = g.node("FunctionNodeEulerToRotation", Euler=g.combine(0.0, 0.0, _rand(g, widx, 0.0, 6.283, seed, 79)))
        ros = g.node("GeometryNodeInstanceOnPoints", Points=wp, Instance=g.group(rosette())["Mesh"], Rotation=wrot,
                     Scale=_rand(g, widx, 0.6, 1.4, seed, 80))["Instances"]
        both = g.node("GeometryNodeJoinGeometry")
        g.connect(ros, both.i("Geometry"))
        g.connect(inst, both.i("Geometry"))
    g.output("Instances", "GEOMETRY", both, desc="Grass tufts (nk_rand, gr_dry, gr_tone) and weed rosettes")
    return g.finish()


@once
def rosette():
    g = Graph("Garden Ground Rosette", description="A small broadleaf lawn weed: 6 oval leaves (NK Leaf) radiating "
                                                   "from a point, lying low and slightly raised at the tips")
    size = g.input("Size", "FLOAT", 0.045, min=0.005, max=0.5, subtype="DISTANCE", desc="Leaf length")
    with g.frame("Six leaves round the centre, tilted up 15-25 degrees"):
        lf = g.group(leaf(), Length=size, Width=0.5, **{"Widest At": 0.55}, Fold=0.25, Curl=0.1, Resolution=6)
        pts = g.node("GeometryNodeMeshCircle", Vertices=6, Radius=0.002)
        idx = g.node("GeometryNodeInputIndex")
        ang = g.math("MULTIPLY", idx, math.tau / 6.0)
        rot = g.node("FunctionNodeEulerToRotation", Euler=g.combine(0.0, g.math("MULTIPLY_ADD", g.math(
            "FRACT", g.math("MULTIPLY", idx, 0.37)), -0.18, -0.26), ang))
        ins = g.node("GeometryNodeInstanceOnPoints", Points=pts["Mesh"], Instance=lf["Mesh"], Rotation=rot,
                     Scale=g.math("MULTIPLY_ADD", g.math("FRACT", g.math("MULTIPLY", idx, 0.61)), 0.4, 0.75))
        out = g.node("GeometryNodeRealizeInstances", Geometry=ins)
        out = g.node("GeometryNodeSetMaterial", Geometry=out, Material=mat("Garden Ground Weed Leaf"))
    g.output("Mesh", "GEOMETRY", out, desc="Rosette mesh")
    return g.finish()


@once
def paths():
    pp = P["paths"]
    g = Graph("Garden Ground Paths", description="Concrete path / edging strips beyond the lawn (fitted polylines) "
                                                 "and stepping stones, following the ground height")
    wscale = g.input("Width Scale", "FLOAT", 1.0, min=0.1, max=3.0, desc="Multiply every strip width")
    out = g.node("GeometryNodeJoinGeometry")
    for key in ("hero_path", "far_path", "left_path"):
        spec = pp[key]
        curve = polyline(g, spec["points"], key.replace("_", " "))
        with g.frame(f"{key.replace('_', ' ')}: resample, drape on the ground, sweep a slab profile"):
            curve = g.node("GeometryNodeResampleCurve", Curve=curve, Mode="Length", Length=0.15)
            pos = g.node("GeometryNodeInputPosition")
            hz = g.group(ground_height(), Position=pos)["Height"]
            xyz = g.separate(pos)
            curve = g.node("GeometryNodeSetPosition", Geometry=curve, Position=g.combine(
                xyz["X"], xyz["Y"], g.math("ADD", hz, spec["z"] - spec["thickness"] * 0.5 + 0.012)))
            prof = g.node("GeometryNodeCurvePrimitiveQuadrilateral", Width=g.math("MULTIPLY", spec["width"], wscale),
                          Height=spec["thickness"])
            mesh = g.node("GeometryNodeCurveToMesh", Curve=curve, **{"Profile Curve": prof}, **{"Fill Caps": True})
            g.connect(mesh, out.i("Geometry"))
    with g.frame("Stepping stones: hex slabs at the measured spots"):
        slab = g.group(hex_slab(), **{"Across Flats": 0.42}, Thickness=0.05, Bevel=0.008)["Mesh"]
        for x, y, rz in pp["stepping_stones"]:
            hz = 0.03
            t = g.node("GeometryNodeTransform", Geometry=slab, Translation=(x, y, hz), Rotation=g.node(
                "FunctionNodeEulerToRotation", Euler=(0.0, 0.0, rz)))
            g.connect(t, out.i("Geometry"))
    with g.frame("Concrete material"):
        res = g.node("GeometryNodeSetMaterial", Geometry=out, Material=mat("Garden Ground Path"))
    g.output("Mesh", "GEOMETRY", res, desc="Path strips and stepping stones")
    return g.finish()

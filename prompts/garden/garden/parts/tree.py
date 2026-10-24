"""Garden part 'tree': the leaning, forking tree behind the table (hero view, top centre).

Measured by scripts/analyze_tree.py -> data/params/tree.json. Geometry Nodes build everything:
  Garden Tree Skeleton   fitted control points (x, y, z, radius) of trunk + three stems -> Catmull-Rom curves,
                         plus procedural buttress roots from the trunk base
  Garden Tree Bark Mesh  curve -> tube mesh, Voronoi fissure field stretched along the stem displaces the
                         surface and is stored as nk_fissure for the bark shader
  Garden Tree Crown      (tree_canopy.py) branches, twigs and instanced NK Leaf leaves above the scan ceiling
Top group: "Garden Tree".
"""
import math

import bpy
from nodekit.graph import Graph, once

from garden.parts import tree_bark, tree_canopy, tree_materials
from garden.util import load_params

STEM_ORDER = ("trunk", "left", "right")   # trunk includes the main stem


def _index_switch(g, data_type, values, index):
    n = g.node("GeometryNodeIndexSwitch", props={"data_type": data_type})
    for _ in range(len(values) - 2):
        n.b.index_switch_items.new()
    n.set(Index=index)
    for k, v in enumerate(values):
        g.connect(v, n.i(str(k)))
    return n


def _rand(g, lo, hi, seed, ident=None, dtype="FLOAT"):
    n = g.node("FunctionNodeRandomValue", props={"data_type": dtype}, Min=lo, Max=hi, Seed=seed)
    if ident is not None:
        g.connect(ident, n.i("ID"))
    return n


@once
def skeleton():
    prm = load_params("tree")
    stems = prm["stems"]
    gz = float(prm.get("ground_z", 0.1))
    pts = [(p, sid) for sid, name in enumerate(STEM_ORDER) for p in stems[name]]
    base = stems["trunk"][1]
    g = Graph("Garden Tree Skeleton", description="Stem curves through the fitted control points of "
              "data/params/tree.json (trunk continuing into the main stem, left and right stems; x, y, z, radius) as Catmull-Rom splines "
              "with nk_r radius, plus buttress roots spreading from the trunk base into the soil")
    seed = g.input("Seed", "INT", 7, min=0, max=10000, desc="Random seed for the root layout")
    nroots = g.input("Root Count", "INT", 6, min=0, max=16, desc="Number of buttress roots at the trunk base")
    rlen = g.input("Root Length", "FLOAT", 0.32, min=0.0, max=2.0, subtype="DISTANCE",
                   desc="Horizontal reach of a root from the trunk axis")
    step = g.input("Resample Length", "FLOAT", 0.01, min=0.004, max=0.2, subtype="DISTANCE",
                   desc="Spacing of curve points (sets the bark mesh density along the stems)")
    with g.frame(f"{len(pts)} fitted control points (scripts/analyze_tree.py): position, radius, stem id"):
        idx = g.node("GeometryNodeInputIndex")["Index"]
        pos = _index_switch(g, "VECTOR", [tuple(p[:3]) for p, _ in pts], idx)
        rad = _index_switch(g, "FLOAT", [p[3] for p, _ in pts], idx)
        sid = _index_switch(g, "INT", [s for _, s in pts], idx)
        cp = g.node("GeometryNodePoints", Count=len(pts), Position=pos["Output"], Radius=0.01)["Points"]
        cp = g.node("GeometryNodeStoreNamedAttribute", props={"data_type": "FLOAT", "domain": "POINT"},
                    Geometry=cp, Name="nk_r", Value=rad["Output"])["Geometry"]
    with g.frame("Points to one curve per stem, ordered by index"):
        st = g.node("GeometryNodePointsToCurves", Points=cp, **{"Curve Group ID": sid["Output"], "Weight": idx})
    with g.frame("Roots: 4 points each, from inside the trunk (z 0.42) down and out below the soil"):
        rp = g.node("GeometryNodePoints", Count=g.math("MULTIPLY", nroots, 4.0), Radius=0.01)["Points"]
        ri = g.node("GeometryNodeInputIndex")["Index"]
        root = g.math("FLOOR", g.math("DIVIDE", ri, 4.0))
        t = g.math("DIVIDE", g.math("FLOORED_MODULO", ri, 4.0), 3.0, label="t along the root")
        ang = g.math("ADD", g.math("MULTIPLY", g.math("DIVIDE", root, nroots), math.tau),
                     _rand(g, -0.45, 0.45, seed, root)["Value"])
        reach = g.math("MULTIPLY", g.math("MULTIPLY", t, rlen), _rand(g, 0.6, 1.3, g.math("ADD", seed, 1), root)[
            "Value"])
        z = g.mix(g.math("POWER", t, 0.45), base[2] + 0.2, gz - 0.09)["Result"]
        rpos = g.combine(g.math("ADD", base[0], g.math("MULTIPLY", g.math("COSINE", ang), reach)),
                         g.math("ADD", base[1], g.math("MULTIPLY", g.math("SINE", ang), reach)), z)
        rp = g.node("GeometryNodeSetPosition", Geometry=rp, Position=rpos)["Geometry"]
        rr = g.mix(g.math("POWER", t, 0.8), base[3] * 0.6, 0.035)["Result"]
        rp = g.node("GeometryNodeStoreNamedAttribute", props={"data_type": "FLOAT", "domain": "POINT"},
                    Geometry=rp, Name="nk_r", Value=rr)["Geometry"]
        roots = g.node("GeometryNodePointsToCurves", Points=rp, **{"Curve Group ID": root, "Weight": ri})["Curves"]
        roots = g.node("GeometryNodeStoreNamedAttribute", props={"data_type": "BOOLEAN", "domain": "CURVE"},
                       Geometry=roots, Name="nk_root", Value=True)["Geometry"]
    with g.frame("Smooth Catmull-Rom splines, resampled; arc length stored as nk_along"):
        cur = g.node("GeometryNodeJoinGeometry", Geometry=st["Curves"])
        g.connect(roots, cur.i("Geometry"))
        cur = g.node("GeometryNodeCurveSplineType", props={"spline_type": "CATMULL_ROM"}, Curve=cur)["Curve"]
        cur = g.node("GeometryNodeResampleCurve", Curve=cur, Mode="Length", Length=step)["Curve"]
        cur = g.node("GeometryNodeSetCurveRadius", Curve=cur, Radius=1.0)["Curve"]
        sp = g.node("GeometryNodeSplineParameter")
        cur = g.node("GeometryNodeStoreNamedAttribute", props={"data_type": "FLOAT", "domain": "POINT"},
                     Geometry=cur, Name="nk_along", Value=sp["Length"])["Geometry"]
    g.output("Curves", "GEOMETRY", cur, desc="Stem and root curves with nk_r, nk_along, nk_root")
    return g.finish()


def _scars(g, rr):
    """0..1 mask of the measured bark scars/knots (data/params/tree.json "scars": x, y, z, radius)."""
    out = g.value(0.0, label="no scar")
    pos = g.node("GeometryNodeInputPosition")["Position"]
    for x, y, z, rad in load_params("tree").get("scars", []):
        d = g.vmath("DISTANCE", pos, (x, y, z))["Value"]
        m = g.math("SUBTRACT", 1.0, g.map_range(d, rad * 0.4, rad, 0.0, 1.0, interp="SMOOTHSTEP"))
        out = g.math("MAXIMUM", out, m)
    return g.math("MULTIPLY", out, g.math("MINIMUM", g.math("DIVIDE", rr, 0.08), 1.0), label="scar on thick stems")


@once
def bark_mesh():
    g = Graph("Garden Tree Bark Mesh", description="Tube mesh around curves (radius from nk_r) whose surface is "
              "pushed in along a Voronoi fissure network stretched along the stem (bark plates and vertical "
              "fissures), stored as nk_fissure / nk_bark for the bark shader")
    curves = g.input("Curves", "GEOMETRY", desc="Curves carrying nk_r (radius) and nk_along (arc length)")
    rscale = g.input("Radius Scale", "FLOAT", 1.0, min=0.3, max=3.0, desc="Multiplier on the fitted radii")
    res = g.input("Resolution", "INT", 112, min=4, max=256, desc="Profile segments around a stem")
    depth = g.input("Fissure Depth", "FLOAT", 0.012, min=0.0, max=0.06, subtype="DISTANCE",
                    desc="Depth of the bark fissures on a 0.15 m radius stem (scales with radius)")
    fscale = g.input("Fissure Scale", "FLOAT", 30.0, min=1.0, max=60.0,
                     desc="Bark plates per metre around the stem")
    stretch = g.input("Fissure Stretch", "FLOAT", 7.0, min=1.0, max=10.0,
                      desc="How much longer the plates are along the stem than across")
    width = g.input("Fissure Width", "FLOAT", 0.08, min=0.01, max=0.5, subtype="FACTOR",
                    desc="Fissure width as a share of a plate")
    lichen = g.input("Weathering", "FLOAT", 0.5, min=0.0, max=1.0, subtype="FACTOR",
                     desc="Lichen and weathering amount passed to the bark shader")
    mat = g.input("Material", "MATERIAL", desc="Bark material")
    with g.frame("Profile circle with its angle stored as nk_ang; tube scaled by nk_r"):
        prof = g.node("GeometryNodeCurvePrimitiveCircle", Resolution=res, Radius=1.0)["Curve"]
        prof = g.node("GeometryNodeStoreNamedAttribute", props={"data_type": "FLOAT", "domain": "POINT"},
                      Geometry=prof, Name="nk_ang", Value=g.node("GeometryNodeSplineParameter")["Factor"])
        r = g.node("GeometryNodeInputNamedAttribute", props={"data_type": "FLOAT"}, Name="nk_r")["Attribute"]
        curves = g.node("GeometryNodeStoreNamedAttribute", props={"data_type": "FLOAT_VECTOR", "domain": "POINT"},
                        Geometry=curves, Name="nk_axis", Value=g.node("GeometryNodeInputTangent")["Tangent"])
        mesh = g.node("GeometryNodeCurveToMesh", Curve=curves["Geometry"], **{"Profile Curve": prof["Geometry"],
                                                                   "Scale": g.math("MULTIPLY", r, rscale),
                                                                   "Fill Caps": True})["Mesh"]
    with g.frame("Bark space: (r cos a, r sin a, along / stretch) in metres"):
        a = g.math("MULTIPLY", g.node("GeometryNodeInputNamedAttribute", props={"data_type": "FLOAT"},
                                      Name="nk_ang")["Attribute"], math.tau)
        rr = g.math("MULTIPLY", g.node("GeometryNodeInputNamedAttribute", props={"data_type": "FLOAT"},
                                       Name="nk_r")["Attribute"], rscale)
        along = g.node("GeometryNodeInputNamedAttribute", props={"data_type": "FLOAT"}, Name="nk_along")["Attribute"]
        bv = g.combine(g.math("MULTIPLY", rr, g.math("COSINE", a)), g.math("MULTIPLY", rr, g.math("SINE", a)),
                       g.math("DIVIDE", along, stretch))
    with g.frame("Fissures: Voronoi cell edges (plates) on noise-warped bark space; depth scales with radius"):
        warp = g.vmath("SUBTRACT", g.node("ShaderNodeTexNoise", props={"noise_dimensions": "3D"}, Vector=bv,
                                          Scale=g.math("MULTIPLY", fscale, 1.5), Detail=2.0)["Color"],
                       (0.5, 0.5, 0.5))["Vector"]
        wv = g.vmath("ADD", bv, g.vmath("SCALE", warp, scale=g.math("DIVIDE", 0.35, fscale))["Vector"])["Vector"]
        vor = g.node("ShaderNodeTexVoronoi", props={"feature": "DISTANCE_TO_EDGE", "voronoi_dimensions": "3D"},
                     Vector=wv, Scale=fscale, Randomness=1.0)["Distance"]
        fis = g.math("SUBTRACT", 1.0, g.map_range(vor, 0.0, width, 0.0, 1.0), label="sharp-edged fissures")
        vor2 = g.node("ShaderNodeTexVoronoi", props={"feature": "DISTANCE_TO_EDGE", "voronoi_dimensions": "3D"},
                      Vector=g.vmath("MULTIPLY", wv, (1.0, 1.0, 3.0))["Vector"],
                      Scale=g.math("MULTIPLY", fscale, 0.6), Randomness=1.0, label="short cells: plate breaks")
        brk = g.math("SUBTRACT", 1.0, g.map_range(vor2["Distance"], 0.0, g.math("MULTIPLY", width, 0.7), 0.0, 1.0))
        bmask = g.map_range(g.node("ShaderNodeTexNoise", Vector=bv, Scale=6.0, Detail=2.0)["Fac"], 0.56, 0.62,
                            0.0, 1.0, label="breaks only in patches")
        fis = g.math("MAXIMUM", fis, g.math("MULTIPLY", brk, bmask), label="fissures + irregular plate breaks")
        nz = g.node("ShaderNodeTexNoise", Vector=bv, Scale=g.math("MULTIPLY", fscale, 4.0), Detail=4.0)["Fac"]
        k = g.math("MINIMUM", g.math("DIVIDE", rr, 0.15), 1.0, label="thin stems: shallower")
        ridge = g.node("ShaderNodeTexNoise", Vector=g.vmath("MULTIPLY", bv, (1.0, 1.0, 0.1))["Vector"],
                       Scale=g.math("MULTIPLY", fscale, 0.8), Detail=3.0, Roughness=0.5,
                       label="long vertical ridges (~5 cm apart, measured on close_trunk)")["Fac"]
        crest = g.math("POWER", g.math("SUBTRACT", 1.0, g.math("ABSOLUTE", g.math("MULTIPLY_ADD", ridge, 2.0, -1.0))),
                       4.0, label="narrow sharp crests")
        scar = _scars(g, rr)
        relief = g.math("ADD", g.math("ADD", g.math("MULTIPLY", fis, -1.0), g.math("MULTIPLY", g.math(
            "SUBTRACT", nz, 0.5), 0.3)), g.math("MULTIPLY", g.math("SUBTRACT", crest, 0.25), 2.4))
        relief = g.math("SUBTRACT", relief, g.math("MULTIPLY", scar, 2.5), label="minus scar hollow")
        disp = g.math("MULTIPLY", g.math("MULTIPLY", depth, k), relief)
        mesh = g.node("GeometryNodeSetPosition", Geometry=mesh,
                      Offset=g.vmath("SCALE", g.node("GeometryNodeInputNormal")["Normal"], scale=disp))["Geometry"]
    with g.frame("Attributes for the shader, smooth shading, material"):
        pw = g.node("GeometryNodeInputPosition")["Position"]
        patches = g.map_range(g.node("ShaderNodeTexNoise", Vector=pw, Scale=4.0, Detail=3.0)["Fac"], 0.5, 0.62,
                              0.0, 1.0, interp="SMOOTHSTEP", label="lichen colonies on the trunk")
        upper = g.map_range(g.separate(g.node("GeometryNodeInputNormal"))["Z"], -0.4, 0.5, 0.25, 1.0,
                            label="more on upward-facing bark")
        lich = g.math("MULTIPLY", g.math("MULTIPLY", patches, upper), lichen)
        for name, dt, val in (("nk_fissure", "FLOAT", fis), ("nk_bark", "FLOAT_VECTOR", bv),
                              ("nk_lichen", "FLOAT", lich), ("nk_scar", "FLOAT", scar)):
            mesh = g.node("GeometryNodeStoreNamedAttribute", props={"data_type": dt, "domain": "POINT"},
                          Geometry=mesh, Name=name, Value=val)["Geometry"]
        mesh = g.node("GeometryNodeSetShadeSmooth", Geometry=mesh)["Geometry"]
        mesh = g.node("GeometryNodeSetMaterial", Geometry=mesh, Material=mat)["Geometry"]
    g.output("Mesh", "GEOMETRY", mesh, desc="Bark tube mesh")
    return g.finish()


def materials():
    tree_materials.materials()


def build():
    bark = bpy.data.materials["Garden Tree Bark"]
    leafm = bpy.data.materials["Garden Tree Leaf"]
    g = Graph("Garden Tree", description="The leaning garden tree behind the table: measured trunk and three "
              "stems as fissured bark tubes, buttress roots, and a branch/twig/leaf crown above the scan ceiling",
              modifier=True)
    seed = g.input("Seed", "INT", 7, min=0, max=10000, desc="Random seed (roots, branches, leaves)")
    rscale = g.input("Radius Scale", "FLOAT", 1.0, min=0.5, max=2.0, desc="Multiplier on the fitted stem radii")
    depth = g.input("Fissure Depth", "FLOAT", 0.016, min=0.0, max=0.05, subtype="DISTANCE",
                    desc="Bark fissure depth on the trunk")
    fscale = g.input("Fissure Scale", "FLOAT", 30.0, min=2.0, max=40.0, desc="Bark plates per metre around")
    stretch = g.input("Fissure Stretch", "FLOAT", 7.0, min=1.0, max=8.0, desc="Plate elongation along the stem")
    weather = g.input("Weathering", "FLOAT", 0.45, min=0.0, max=1.0, subtype="FACTOR",
                      desc="Lichen and silvery weathering on the bark")
    fdens = g.input("Flake Density", "FLOAT", 1400.0, min=0.0, max=2000.0,
                    desc="Broken bark flakes per square metre of plate (0 = none)")
    nroots = g.input("Root Count", "INT", 6, min=0, max=12, desc="Buttress roots at the trunk base")
    show = g.input("Show Crown", "BOOL", True, desc="Generate the branch/leaf crown above the measured stems")
    bdens = g.input("Branch Density", "FLOAT", 0.75, min=0.0, max=1.0, subtype="FACTOR",
                    desc="Share of stem points above the crown base that sprout a branch")
    ldens = g.input("Leaf Density", "FLOAT", 1.0, min=0.0, max=3.0, desc="Leaves per twig length (1 = fitted)")
    lsize = g.input("Leaf Size", "FLOAT", 0.075, min=0.02, max=0.2, subtype="DISTANCE", desc="Leaf length")
    with g.frame("Measured stems and roots as curves"):
        sk = g.group(skeleton(), Seed=seed, **{"Root Count": nroots})["Curves"]
    with g.frame("Stems and roots as fissured bark tubes"):
        stems = g.group(bark_mesh(), Curves=sk, Material=bark, **{
            "Radius Scale": rscale, "Fissure Depth": depth, "Fissure Scale": fscale, "Fissure Stretch": stretch,
            "Weathering": weather})["Mesh"]
    with g.frame("Broken bark flakes on the stems"):
        fl = g.group(tree_bark.flakes(), **{"Bark Mesh": stems, "Seed": seed, "Density": fdens,
                                            "Material": bark})["Flakes"]
    with g.frame("Crown: branches, twigs and leaves (optional)"):
        cg = g.group(tree_canopy.crown(), Stems=sk, Seed=seed, Leaf=leafm, **{
            "Branch Density": bdens, "Leaf Density": ldens, "Leaf Size": lsize})
        wood = g.group(bark_mesh(), Curves=cg["Wood"], Material=bark, Resolution=8, **{
            "Fissure Depth": 0.0, "Fissure Scale": fscale, "Fissure Stretch": stretch, "Weathering": weather})
        both = g.node("GeometryNodeJoinGeometry", Geometry=wood["Mesh"])
        g.connect(cg["Leaves"], both.i("Geometry"))
        crown = g.node("GeometryNodeSwitch", props={"input_type": "GEOMETRY"}, Switch=show)
        g.connect(both["Geometry"], crown.i("True"))
        out = g.node("GeometryNodeJoinGeometry", Geometry=stems)
        g.connect(crown["Output"], out.i("Geometry"))
        g.connect(fl, out.i("Geometry"))
    g.output("Geometry", "GEOMETRY", out, desc="Tree geometry")
    return g.finish()

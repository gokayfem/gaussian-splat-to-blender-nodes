"""Arching leafy branches: the woody shrub's visible structure (hero right shrub, close_foliage camera).

The reference shrub is built of arching stems carrying opposite pairs of pointed (lanceolate) leaves that hang in
tiers, with dark gaps between the sprays. So the shrub mass is made mostly of branch instances rooted at several
depths inside the fitted envelope; the envelope only supplies roots, colour and a deep dark core.

'Garden Shrubs Branch'    one branch of length 1 along +X: stem z = Arch x - Droop x^2 with a tapered tube,
                          opposite leaf pairs hanging off each node (splayed, tips down, curled), a terminal leaf;
                          each leaf stores sh_lv (per-leaf value 0.65..1.35) for bright / mid / shaded leaves.
'Garden Shrubs Branch Set' three branch variants (upright, arching, weeping) as pickable instances.
'Garden Shrubs Branches'  branch instances rooted 30..100 % of their length inside the envelope, pointing outwards
                          with random yaw/pitch, coloured per branch from the piece scan colour.
"""
from library.shapes import leaf
from nodekit.graph import Graph, once

from garden.parts.shrubs_nodes import attr, boolean, cmp, cup_twist, join, kind_is, rand, set_mat, store, wavy

VARIANTS = ((0.55, 0.45, 15), (0.4, 0.75, 17), (0.25, 1.05, 13))   # (arch, droop, nodes): upright, arching, weeping


@once
def build_branch():
    lf = leaf()
    g = Graph("Garden Shrubs Branch", description="One leafy branch of length 1 along +X: stem z = Arch x - Droop "
              "x^2 (tapered tube), opposite pairs of pointed leaves at every node of the outer 60 % (leaves concentrated at the spray tip) "
              "(splayed ~70 deg, hanging tips, curled), and a terminal leaf; realized, with sh_u / sh_v / sh_lv "
              "for the leaf shader")
    arch = g.input("Arch", "FLOAT", 0.4, min=-1.0, max=2.0, desc="Initial rise of the stem per unit length")
    droop = g.input("Droop", "FLOAT", 0.75, min=0.0, max=3.0, desc="Downward bend towards the tip")
    leaf_len = g.input("Leaf Length", "FLOAT", 0.2, min=0.02, max=1.0, desc="Leaf length as a share of the branch")
    count = g.input("Segments", "INT", 9, min=3, max=40, desc="Leaf nodes along the stem")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed for per-leaf variation")
    with g.frame("Arching stem curve and a thin tapered tube"):
        line = g.node("GeometryNodeCurvePrimitiveLine", End=(1.0, 0.0, 0.0))["Curve"]
        line = g.node("GeometryNodeResampleCurve", Curve=line, Count=count)["Curve"]
        x = g.separate(g.node("GeometryNodeInputPosition"))["X"]
        z = g.math("SUBTRACT", g.math("MULTIPLY", x, arch), g.math("MULTIPLY", g.math("MULTIPLY", x, x), droop))
        wob = g.math("MULTIPLY", g.math("SINE", g.math("MULTIPLY", x, 7.0)), 0.03)
        line = g.node("GeometryNodeSetPosition", Geometry=line, Position=g.combine(x, wob, z))["Geometry"]
        line = g.node("GeometryNodeSetCurveRadius", Curve=line,
                      Radius=g.math("MULTIPLY_ADD", x, -0.7, 1.0))["Curve"]
        prof = g.node("GeometryNodeCurvePrimitiveCircle", Resolution=4, Radius=0.007)["Curve"]
        stem = g.node("GeometryNodeCurveToMesh", Curve=line, **{"Profile Curve": prof})["Mesh"]
        stem = store(g, stem, "sh_u", 0.95)
        stem = store(g, stem, "sh_v", 1.0)
        stem = store(g, stem, "sh_lv", 0.3)
    with g.frame("One narrow pointed leaf (lanceolate, curled tip, cupped and twisted, wavy margin) on a thin petiole"):
        blade = g.group(lf, Length=1.0, Width=0.26, Fold=0.03, Curl=0.22, Resolution=8,
                        **{"Widest At": 0.3})["Mesh"]
        blade = cup_twist(g, wavy(g, blade))
        p = g.separate(g.node("GeometryNodeInputPosition"))
        blade = store(g, blade, "sh_u", g.math("MINIMUM", g.math("MAXIMUM", p["X"], 0.0), 1.0))
        blade = store(g, blade, "sh_v", g.math("DIVIDE", p["Y"], 0.13))
        blade = g.node("GeometryNodeTransform", Geometry=blade, Translation=(0.12, 0.0, 0.0))["Geometry"]
        pet = g.node("GeometryNodeMeshCylinder", Vertices=3, Radius=0.012, Depth=0.12)["Mesh"]
        pet = g.node("GeometryNodeTransform", Geometry=pet, Translation=(0.06, 0.0, 0.0),
                     Rotation=(0.0, 1.5707963, 0.0))["Geometry"]
        pet = store(g, store(g, store(g, pet, "sh_u", 0.95), "sh_v", 1.0), "sh_lv", 0.35)
        blade = join(g, pet, blade)
    with g.frame("Opposite leaf pairs at every node: splayed, tips hanging, size shrinking to the tip"):
        pts = g.node("GeometryNodeCurveToPoints", props={"mode": "EVALUATED"}, Curve=line)
        idx = g.node("GeometryNodeInputIndex")["Index"]
        xs = g.separate(g.node("GeometryNodeInputPosition"))["X"]
        size = g.math("MULTIPLY", leaf_len, g.math("MULTIPLY_ADD", xs, -0.35, 1.15))
        sel = cmp(g, "GREATER_THAN", xs, 0.4)
        pairs = []
        for side in (1.0, -1.0):
            twist = g.math("MULTIPLY", g.math("MODULO", idx, 2.0), 0.5)
            spin = g.node("FunctionNodeEulerToRotation", Euler=g.combine(
                side * 0.45, g.math("ADD", 0.35, rand(g, -0.25, 0.35, seed, 3 if side > 0 else 4, ident=idx)),
                g.math("ADD", side * 1.2, g.math("MULTIPLY", twist, side))))["Rotation"]
            rot = g.node("FunctionNodeRotateRotation", props={"rotation_space": "LOCAL"}, Rotation=pts["Rotation"],
                         **{"Rotate By": spin})["Rotation"]
            ins = g.node("GeometryNodeInstanceOnPoints", Points=pts["Points"], Instance=blade, Rotation=rot,
                         Selection=sel, Scale=g.math("MULTIPLY", size, rand(g, 0.8, 1.15, seed, 5, ident=idx)))
            lv = g.math("MULTIPLY", rand(g, 0.65, 1.3, seed, 6 if side > 0 else 7, ident=idx),
                        g.math("MULTIPLY_ADD", xs, 0.55, 0.7), label="sunlit, lighter spray tips")
            ins = store(g, ins["Instances"], "sh_lv", lv, domain="INSTANCE")
            pairs.append(ins)
        tip_pt = g.node("GeometryNodePoints", Count=1, Position=g.combine(
            1.0, 0.0, g.math("SUBTRACT", arch, droop)))["Points"]
        tip = g.node("GeometryNodeInstanceOnPoints", Points=tip_pt, Instance=blade, Scale=g.math(
            "MULTIPLY", leaf_len, 0.9), Rotation=g.node("FunctionNodeEulerToRotation", Euler=g.combine(
                0.0, g.math("MULTIPLY", droop, 0.8), 0.0))["Rotation"])["Instances"]
        tip = store(g, tip, "sh_lv", 1.3, domain="INSTANCE")
        leaves = g.node("GeometryNodeRealizeInstances", Geometry=join(g, pairs[0], pairs[1], tip))["Geometry"]
    g.output("Mesh", "GEOMETRY", join(g, stem, leaves), desc="The branch, realized")
    return g.finish()


@once
def build_branch_set():
    br = build_branch()
    g = Graph("Garden Shrubs Branch Set", description="Three branch variants as pickable instances: 0 upright, "
              "1 arching, 2 weeping (Arch / Droop / nodes fitted by eye to the close_foliage reference)")
    ll = g.input("Leaf Length", "FLOAT", 0.2, min=0.02, max=1.0, desc="Leaf length as a share of the branch")
    out = []
    with g.frame("Upright, arching and weeping branch prototypes"):
        for k, (a, d, n) in enumerate(VARIANTS):
            m = g.group(br, Arch=a, Droop=d, Segments=n, Seed=k * 17, **{"Leaf Length": ll})["Mesh"]
            out.append(g.node("GeometryNodeGeometryToInstance", Geometry=m)["Instances"])
    g.output("Branches", "GEOMETRY", join(g, *out), desc="Three branch instances")
    return g.finish()


@once
def build_branches():
    g = Graph("Garden Shrubs Branches", description="Leafy branches rooted 30..100 % of their length inside the "
              "envelope of woody (broadleaf, bright, open) pieces, pointing out along the horizontal surface normal "
              "with random yaw and pitch; variant picked at random, nk_color per branch")
    env = g.input("Envelope", "GEOMETRY", desc="Envelope mesh with sh_* attributes")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    dens = g.input("Branch Density", "FLOAT", 12.0, min=0.0, max=200.0, desc="Branches per m^2 of envelope")
    length = g.input("Branch Length", "FLOAT", 0.7, min=0.05, max=3.0, subtype="DISTANCE", desc="Mean branch length")
    leaf_len = g.input("Leaf Length", "FLOAT", 0.2, min=0.02, max=1.0, desc="Leaf length as a share of the branch")
    gain = g.input("Color Gain", "FLOAT", 1.0, min=0.2, max=4.0, desc="Scan colour to albedo gain")
    mat = g.input("Leaf Material", "MATERIAL", desc="Leaf material")
    with g.frame("Roots on upward / sideways faces of woody pieces, at several depths inside, not reaching over the trunk"):
        nz = g.separate(g.node("GeometryNodeInputNormal")["Normal"])["Z"]
        sel = boolean(g, "AND", kind_is(g, "broadleaf", "bright", "sparse"), cmp(g, "GREATER_THAN", nz, -0.35))
        sel = boolean(g, "AND", sel, cmp(g, "GREATER_THAN", attr(g, "sh_clear"), g.math("ADD", length, 0.35)))
        dp = g.node("GeometryNodeDistributePointsOnFaces", Mesh=env, Seed=g.math("ADD", seed, 51.0),
                    Density=g.mix(sel, 0.0, g.math("MULTIPLY", dens, g.mix(kind_is(g, "broadleaf"), 1.0, g.math(
                        "MULTIPLY_ADD", attr(g, "sh_spray"), 0.85, 0.15)))))
        inset = g.math("MULTIPLY", length, rand(g, -1.0, -0.3, seed, 57), label="several depths; tips end near the measured surface")
        pts = g.node("GeometryNodeSetPosition", Geometry=dp["Points"],
                     Offset=g.vmath("SCALE", dp["Normal"], scale=inset))["Geometry"]
    with g.frame("Point the branch outwards (yaw from the normal), random pitch, length and variant"):
        hn = g.separate(g.vmath("MULTIPLY", dp["Normal"], (1.0, 1.0, 0.0)))
        yaw = g.math("ADD", g.math("ARCTAN2", hn["Y"], hn["X"]), rand(g, -0.6, 0.6, seed, 52))
        rot = g.node("FunctionNodeEulerToRotation", Euler=g.combine(
            rand(g, -0.5, 0.5, seed, 53), g.math("SUBTRACT", rand(g, -0.45, 0.2, seed, 54),
                                                 g.math("MULTIPLY", g.math("MAXIMUM", nz, 0.0), 0.7)), yaw))["Rotation"]
        scale = g.math("MULTIPLY", length, rand(g, 0.6, 1.1, seed, 55))
        variant = rand(g, 0, 2, seed, 58, dtype="INT")
    with g.frame("Per-branch colour: scan colour x gain, saturated, jittered"):
        r = rand(g, 0.0, 1.0, seed, 56)
        col = g.vmath("SCALE", attr(g, "sh_color", "FLOAT_COLOR"),
                      scale=g.math("MULTIPLY", gain, g.math("MULTIPLY_ADD", r, 0.6, 0.8)))
        sat = g.mix(kind_is(g, "bright"), (0.7, 1.0, 0.42, 1.0), (1.05, 1.0, 0.3, 1.0), data_type="RGBA")
        col = g.vmath("MULTIPLY", col, sat)
        col = g.vmath("SCALE", col, scale=g.mix(kind_is(g, "bright"), 1.0, 2.0))
        h2 = rand(g, -0.5, 0.5, seed, 59)
        col = g.vmath("MULTIPLY", col, g.combine(g.math("MULTIPLY_ADD", h2, 0.35, 1.0), 1.0,
                                                 g.math("MULTIPLY_ADD", h2, -0.6, 1.0)),
                      label="per-spray hue: yellower vs bluer green")
        pts = store(g, pts, "nk_color", col, "FLOAT_COLOR")
        pts = store(g, pts, "nk_rand", r)
    with g.frame("Instance a branch variant"):
        br = g.group(build_branch_set(), **{"Leaf Length": leaf_len})["Branches"]
        out = g.node("GeometryNodeInstanceOnPoints", Points=pts, Instance=br, Rotation=rot, Scale=scale,
                     **{"Pick Instance": True, "Instance Index": variant})["Instances"]
        out = set_mat(g, out, mat)
    g.output("Geometry", "GEOMETRY", out, desc="Branch instances")
    return g.finish()

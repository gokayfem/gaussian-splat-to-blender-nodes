"""Sub-groups of 'Garden Shrubs': fitted piece data, the union envelope, leaf clusters and herbaceous plants.

Coordinates are world metres (Z up). A *piece* is one measured shrub envelope from scripts/analyze_shrubs.py:
centre XY, ground Z, two horizontal radii along a yaw, a height, a mean scan colour, a kind and a flower share.
"""
import math

from library.shapes import blossom, grass_tuft, leaf
from nodekit.graph import Graph, once

from garden.parts.shrubs_nodes import (TAU, KINDS, attr, boolean, cmp, index_switch, join, kind_is, rand,
                                       set_mat, smooth, store, wavy, xf)
from garden.util import srgb_to_linear


# ---------------------------------------------------------------------------------------------------------------
def _base(p):
    """Foliage base: open/elevated pieces keep their measured base (foliage on bare stems or overhanging);
    dense mounds are brought most of the way to the ground (their measured base is strap blades and lawn)."""
    b = p.get("base", 0.0)
    return b if (p["kind"] == "sparse" or b > 0.5) else b * 0.85


def build_data(pieces):
    """'Garden Shrubs Data': one point per measured piece carrying its fitted numbers as attributes."""
    n = len(pieces)
    g = Graph("Garden Shrubs Data", description="One point per measured shrub piece (data/params/shrubs.json) at "
              "its envelope centre; attributes sh_size (radius X, radius Y, height), sh_yaw, sh_ground, sh_color "
              "(linear scan colour), sh_kind (0 broadleaf, 1 bright, 2 strap, 3 sparse, 4 low) and sh_flower. "
              "The fitted numbers sit in Index Switch nodes so they can be edited in the UI")
    with g.frame("Points: one per piece, at (x, y, ground)"):
        pts = g.node("GeometryNodePoints", Count=n, Radius=0.05)["Points"]
        idx = g.node("GeometryNodeInputIndex")["Index"]
        pos = index_switch(g, "VECTOR", [(p["centre"][0], p["centre"][1], p["ground_z"]) for p in pieces], idx,
                           label="centre x, y, ground z")
        pts = g.node("GeometryNodeSetPosition", Geometry=pts, Position=pos)["Geometry"]
    with g.frame("Fitted envelope size, orientation, colour, kind, flowers"):
        size = index_switch(g, "VECTOR", [(p["radii"][0], p["radii"][1], p["height"]) for p in pieces], idx,
                            label="radius x, radius y, height")
        yaw = index_switch(g, "FLOAT", [p["yaw"] for p in pieces], idx, label="yaw (rad)")
        col = index_switch(g, "RGBA", [srgb_to_linear(p["color_srgb"]) for p in pieces], idx,
                           label="mean scan colour (linear)")
        kind = index_switch(g, "INT", [KINDS[p["kind"]] for p in pieces], idx, label="kind")
        base = index_switch(g, "FLOAT", [_base(p) for p in pieces], idx, label="foliage base above ground")
        flw = index_switch(g, "FLOAT", [min(1.0, p.get("flower_share", 0.0)) for p in pieces], idx,
                           label="white flower share")
        pts = store(g, pts, "sh_size", size, "FLOAT_VECTOR")
        pts = store(g, pts, "sh_yaw", yaw)
        pts = store(g, pts, "sh_base", base)
        pts = store(g, pts, "sh_ground", g.separate(pos)["Z"])
        pts = store(g, pts, "sh_color", col, "FLOAT_COLOR")
        pts = store(g, pts, "sh_kind", kind, "INT")
        pts = store(g, pts, "sh_flower", flw)
        fill = index_switch(g, "FLOAT", [min(1.0, p.get("fill", 30000) / 12000.0) for p in pieces], idx,
                            label="measured fill (splats per m^3 / 12000, capped at 1)")
        pts = store(g, pts, "sh_fill", fill)
    g.output("Points", "GEOMETRY", pts, desc="Piece points with sh_* attributes")
    return g.finish()


# ---------------------------------------------------------------------------------------------------------------
@once
def build_envelope():
    """'Garden Shrubs Envelope': union of piece ellipsoids as one lumpy closed surface with piece attributes."""
    g = Graph("Garden Shrubs Envelope", description="Each piece becomes an ellipsoid standing on its ground "
              "(radii x Inflate + Pad, height x Height Scale); the ellipsoids are unioned through a fog volume and "
              "meshed, pushed in and out by noise (Lumpiness), cut at the ground, and given the nearest piece's "
              "sh_* attributes")
    pieces = g.input("Pieces", "GEOMETRY", desc="Points from Garden Shrubs Data")
    inflate = g.input("Inflate", "FLOAT", 1.5, min=0.5, max=4.0, desc="Radius multiplier for each piece")
    pad = g.input("Pad", "FLOAT", 0.08, min=0.0, max=1.0, subtype="DISTANCE", desc="Added to each radius")
    sinf = g.input("Sparse Inflate", "FLOAT", 0.9, min=0.3, max=4.0,
                   desc="Radius multiplier for open, see-through pieces (they are not filled masses)")
    bh = g.input("Bright Height", "FLOAT", 1.2, min=0.3, max=3.0,
                 desc="Extra height multiplier for the yellow-green shrubs (their tops are under-sampled in the scan)")
    hs = g.input("Height Scale", "FLOAT", 1.0, min=0.3, max=2.0, desc="Envelope height multiplier")
    vox = g.input("Voxel Size", "FLOAT", 0.05, min=0.02, max=0.3, subtype="DISTANCE",
                  desc="Resolution of the union volume")
    lump = g.input("Lumpiness", "FLOAT", 0.12, min=0.0, max=1.0, subtype="DISTANCE",
                   desc="Amplitude of the noise that breaks up the envelope surface")
    lscale = g.input("Lump Scale", "FLOAT", 2.2, min=0.1, max=20.0, desc="Noise frequency (per metre)")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    field = g.input("Density Field", "GEOMETRY",
                    desc="Measured foliage density voxels (points with sh_density) from data/params/shrubs.json")
    hole = g.input("Hole Distance", "FLOAT", 0.2, min=0.02, max=1.0, subtype="DISTANCE",
                   desc="Envelope points farther than this from any measured foliage voxel get no leaves")
    clear_c = g.input("Clear Centre", "VECTOR", (0.19, -2.68, 0.0), subtype="TRANSLATION",
                      desc="Axis of a vertical cylinder kept free of shrub (the tree trunk)")
    clear_r = g.input("Clear Radius", "FLOAT", 0.62, min=0.0, max=3.0, subtype="DISTANCE",
                      desc="Radius of the cleared cylinder around Clear Centre")
    with g.frame("An ellipsoid per piece between foliage base b and top h: centre (b + h) / 2, radius 0.55 (h - b)"):
        size = g.separate(attr(g, "sh_size", "FLOAT_VECTOR"))
        b = attr(g, "sh_base")
        top = g.math("MULTIPLY", g.math("MULTIPLY", size["Z"], hs), g.mix(kind_is(g, "bright"), 1.0, bh))
        h = g.math("SUBTRACT", top, b)
        infl = g.mix(kind_is(g, "sparse"), inflate, sinf)
        infl = g.math("MULTIPLY", infl, g.mix(kind_is(g, "bright"), 1.0, g.math("SQRT", bh)),
                      label="yellow-green shrubs: under-sampled crowns, wider by sqrt(Bright Height)")
        rx = g.math("MULTIPLY_ADD", size["X"], infl, pad)
        ry = g.math("MULTIPLY_ADD", size["Y"], infl, pad)
        lifted = g.node("GeometryNodeSetPosition", Geometry=pieces,
                        Offset=g.combine(0.0, 0.0, g.math("MULTIPLY_ADD", h, 0.45, b)))["Geometry"]
        ico = g.node("GeometryNodeMeshIcoSphere", Radius=1.0, Subdivisions=3)["Mesh"]
        rot = g.node("FunctionNodeEulerToRotation", Euler=g.combine(0.0, 0.0, attr(g, "sh_yaw")))["Rotation"]
        ell = g.node("GeometryNodeInstanceOnPoints", Points=lifted, Instance=ico, Rotation=rot,
                     Scale=g.combine(rx, ry, g.math("MULTIPLY", h, 0.55)))["Instances"]
        ell = g.node("GeometryNodeRealizeInstances", Geometry=ell)["Geometry"]
    with g.frame("Union through a fog volume, back to a mesh"):
        vol = g.node("GeometryNodeMeshToVolume", Mesh=ell, Density=1.0, **{"Resolution Mode": "Size",
                                                                          "Voxel Size": vox,
                                                                          "Interior Band Width": 0.1})["Volume"]
        env = g.node("GeometryNodeVolumeToMesh", Volume=vol, **{"Resolution Mode": "Grid", "Threshold": 0.5,
                                                               "Adaptivity": 0.0})["Mesh"]
    with g.frame("Nearest piece's attributes onto the envelope"):
        pos = g.node("GeometryNodeInputPosition")["Position"]
        near = g.node("GeometryNodeSampleNearest", Geometry=lifted, **{"Sample Position": pos})["Index"]
        for name, dt in (("sh_size", "FLOAT_VECTOR"), ("sh_ground", "FLOAT"), ("sh_color", "FLOAT_COLOR"),
                         ("sh_kind", "INT"), ("sh_flower", "FLOAT"), ("sh_fill", "FLOAT")):
            v = g.node("GeometryNodeSampleIndex", props={"data_type": dt, "domain": "POINT"}, Geometry=lifted,
                       Value=attr(g, name, dt), Index=near)["Value"]
            env = store(g, env, name, v, dt)
        env = store(g, env, "sh_piece", near, "INT")
        env = store(g, env, "sh_out", g.node("GeometryNodeInputNormal")["Normal"], "FLOAT_VECTOR")
    with g.frame("Lumpy surface: noise along the normal; delete below the ground and inside the trunk clearance"):
        nrm = g.node("GeometryNodeInputNormal")["Normal"]
        noise = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "4D"}, Vector=pos, W=seed,
                       Scale=lscale, Detail=3.0, Roughness=0.6)["Fac"]
        off = g.math("MULTIPLY", g.math("SUBTRACT", noise, 0.68), g.math("MULTIPLY", lump, 2.5),
                     label="mostly inward: the envelope never grows past the measured extent")
        env = g.node("GeometryNodeSetPosition", Geometry=env, Offset=g.vmath("SCALE", nrm, scale=off))["Geometry"]
        below = cmp(g, "LESS_THAN", g.separate(pos)["Z"], g.math("ADD", attr(g, "sh_ground"), 0.01))
        rel = g.vmath("MULTIPLY", g.vmath("SUBTRACT", pos, clear_c), (1.0, 1.0, 0.0))
        dclear = g.vmath("LENGTH", rel)["Value"]
        below = boolean(g, "OR", below, cmp(g, "LESS_THAN", dclear, clear_r))
        env = store(g, env, "sh_clear", dclear)
    with g.frame("Measured spray mask: nearest scan density voxel; far from any voxel = a scan hole (gap)"):
        ni = g.node("GeometryNodeSampleNearest", Geometry=field, **{"Sample Position": pos})["Index"]
        fpos = g.node("GeometryNodeSampleIndex", props={"data_type": "FLOAT_VECTOR", "domain": "POINT"},
                      Geometry=field, Value=g.node("GeometryNodeInputPosition")["Position"], Index=ni)["Value"]
        fden = g.node("GeometryNodeSampleIndex", props={"data_type": "FLOAT", "domain": "POINT"}, Geometry=field,
                      Value=attr(g, "sh_density"), Index=ni)["Value"]
        dist = g.vmath("DISTANCE", pos, fpos)["Value"]
        near_f = g.map_range(dist, hole, g.math("MULTIPLY", hole, 0.5), 0.0, 1.0, interp="SMOOTHSTEP")
        spray = g.math("MULTIPLY", near_f, g.map_range(fden, 0.05, 0.6, 0.25, 1.0))
        env = store(g, env, "sh_spray", spray)
        env = g.node("GeometryNodeDeleteGeometry", props={"domain": "POINT"}, Geometry=env, Selection=below)
        env = smooth(g, env["Geometry"])
    g.output("Envelope", "GEOMETRY", env, desc="Closed-ish envelope mesh with sh_* point attributes")
    return g.finish()


# ---------------------------------------------------------------------------------------------------------------
@once
def build_leaf_shapes():
    """'Garden Shrubs Leaf Shapes': the leaf meshes (length 1) as instances; index 0 broad oval, 1 glossy narrow,
    2 large hosta-like. Each stores sh_u (base 0 .. tip 1) and sh_v (-1 .. 1 across) for the leaf shader."""
    lf = leaf()
    g = Graph("Garden Shrubs Leaf Shapes", description="Three NK Leaf blades of length 1 (base at origin, tip +X, "
              "face +Z) as instances 0 broad oval, 1 narrow glossy, 2 large rounded; each stores sh_u along and "
              "sh_v across for the midrib and root-to-tip shading")
    res = g.input("Resolution", "INT", 7, min=2, max=32, desc="Segments along each leaf")
    shapes = []
    with g.frame("Three leaf outlines with fitted width, fold and curl"):
        for w, at, fold, curl in ((0.36, 0.35, 0.12, 0.2), (0.28, 0.4, 0.1, 0.12), (0.6, 0.4, 0.15, 0.25)):
            m = g.group(lf, Length=1.0, Width=w, Fold=fold, Curl=curl, Resolution=res, **{"Widest At": at})["Mesh"]
            m = wavy(g, m)
            p = g.separate(g.node("GeometryNodeInputPosition"))
            m = store(g, m, "sh_u", g.math("MINIMUM", g.math("MAXIMUM", p["X"], 0.0), 1.0))
            m = store(g, m, "sh_v", g.math("DIVIDE", p["Y"], w * 0.5))
            shapes.append(g.node("GeometryNodeGeometryToInstance", Geometry=m)["Instances"])
    with g.frame("All three as one instance list"):
        out = join(g, *shapes)
    g.output("Leaves", "GEOMETRY", out, desc="Three leaf instances (pick by index)")
    return g.finish()


# ---------------------------------------------------------------------------------------------------------------
@once
def build_clusters():
    """'Garden Shrubs Clusters': leaves on (and just inside) the envelope plus a dark under-layer."""
    g = Graph("Garden Shrubs Clusters", description="Leaves scattered over the envelope (density by kind), pushed "
              "a random depth inside it so the foliage has thickness, aligned to the surface with lifted tips and "
              "random spin; per-leaf nk_color = piece scan colour x Color Gain with per-leaf value/hue jitter. "
              "The envelope itself, shrunk inwards and darkened, is the under-layer that hides gaps")
    env = g.input("Envelope", "GEOMETRY", desc="Envelope mesh with sh_* attributes")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    dens = g.input("Leaf Density", "FLOAT", 420.0, min=0.0, max=5000.0, desc="Leaves per square metre of envelope")
    lsize = g.input("Leaf Scale", "FLOAT", 1.0, min=0.2, max=4.0, desc="Multiplier on the fitted leaf sizes")
    depth = g.input("Depth", "FLOAT", 0.12, min=0.0, max=1.0, subtype="DISTANCE",
                    desc="Leaves sit up to this far inside the envelope")
    lift = g.input("Leaf Lift", "FLOAT", 0.45, min=-1.5, max=1.5, subtype="ANGLE", desc="Tip lift off the surface")
    gain = g.input("Color Gain", "FLOAT", 1.25, min=0.2, max=4.0,
                   desc="Scan colour to albedo gain (scan colour includes self-shadowing)")
    var = g.input("Color Variation", "FLOAT", 0.35, min=0.0, max=1.0, subtype="FACTOR",
                  desc="Per-leaf brightness and hue spread")
    under = g.input("Under Layer", "BOOL", True, desc="Show the dark envelope under-layer")
    core = g.input("Core Density", "FLOAT", 5.0, min=0.0, max=4.0, subtype="FACTOR",
                   desc="Shaded interior leaves as a share of Leaf Density (dark gaps between sprays)")
    size_broad = g.input("Size Broadleaf", "FLOAT", 0.075, min=0.01, max=0.5, subtype="DISTANCE",
                         panel="Leaf sizes", desc="Leaf length of dark broadleaf shrubs")
    size_bright = g.input("Size Bright", "FLOAT", 0.07, min=0.01, max=0.5, subtype="DISTANCE",
                          panel="Leaf sizes", desc="Leaf length of yellow-green shrubs")
    size_sparse = g.input("Size Sparse", "FLOAT", 0.09, min=0.01, max=0.5, subtype="DISTANCE",
                          panel="Leaf sizes", desc="Leaf length of open, see-through plants")
    sparse_d = g.input("Sparse Density", "FLOAT", 0.45, min=0.0, max=2.0, subtype="FACTOR", panel="Leaf sizes",
                       desc="Density factor of open, see-through plants")
    mat = g.input("Leaf Material", "MATERIAL", desc="Leaf material (reads nk_color, nk_rand, sh_u, sh_v)")
    with g.frame("Leaf points: density by kind (no leaves on strap and low pieces)"):
        kind = attr(g, "sh_kind", "INT")
        fac = index_switch(g, "FLOAT", [1.0, 1.0, 0.0, 1.0, 0.0, 0.55], kind, label="density by kind")
        fac = g.math("MULTIPLY", fac, g.mix(kind_is(g, "sparse"), 1.0, g.math("MULTIPLY", sparse_d, g.math(
            "POWER", attr(g, "sh_fill"), 1.5))))
        fac = g.math("MULTIPLY", fac, g.mix(kind_is(g, "broadleaf"), 1.0, attr(g, "sh_spray")),
                     label="broadleaf: leaves only in spray clumps, open gaps between")
        dp = g.node("GeometryNodeDistributePointsOnFaces", Mesh=env, Seed=seed,
                    Density=g.math("MULTIPLY", dens, fac))
        pts = dp["Points"]
        r_depth = rand(g, 0.0, 1.0, seed, 1)
        inset = g.math("SUBTRACT", g.math("MULTIPLY", g.math("POWER", r_depth, 1.6), depth),
                       g.math("MULTIPLY", depth, 0.4), label="from 0.4 Depth outside to 0.6 Depth inside")
        pts = g.node("GeometryNodeSetPosition", Geometry=pts,
                     Offset=g.vmath("SCALE", dp["Normal"], scale=g.math("MULTIPLY", inset, -1.0)))["Geometry"]
    with g.frame("Orientation: surface-aligned, tip lifted, random spin; size by kind"):
        tilt = g.node("FunctionNodeEulerToRotation", Euler=g.combine(
            rand(g, -0.35, 0.35, seed, 2), g.math("SUBTRACT", rand(g, -0.35, 0.35, seed, 3), lift),
            rand(g, 0.0, TAU, seed, 4)))["Rotation"]
        lrot = g.node("FunctionNodeRotateRotation", props={"rotation_space": "LOCAL"}, Rotation=dp["Rotation"],
                      **{"Rotate By": tilt})["Rotation"]
        size = g.mix(kind_is(g, "bright"), size_broad, size_bright)
        size = g.mix(kind_is(g, "sparse"), size, size_sparse)
        size = g.mix(kind_is(g, "herb"), size, g.math("MULTIPLY", size_broad, 1.4))
        size = g.math("MULTIPLY", size, g.math("MULTIPLY", lsize, rand(g, 0.7, 1.3, seed, 5)))
        shape = g.mix(kind_is(g, "bright"), 0.0, 1.0)
        big = boolean(g, "OR", cmp(g, "LESS_THAN", rand(g, 0.0, 1.0, seed, 6), 0.02), kind_is(g, "herb"))
        shape = g.node("FunctionNodeFloatToInt", Float=g.math("MAXIMUM", shape, g.mix(big, 0.0, 2.0)))["Integer"]
    with g.frame("Per-leaf colour: scan colour x gain, value and hue jitter, darker deep inside"):
        r = rand(g, 0.0, 1.0, seed, 7)
        k = g.math("MULTIPLY_ADD", g.math("SUBTRACT", r, 0.5), var, 1.0)
        k = g.math("MULTIPLY", k, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", g.math("POWER", r_depth, 0.6), 0.8)))
        up = g.separate(dp["Normal"])["Z"]
        k = g.math("MULTIPLY", k, g.math("MULTIPLY_ADD", up, 0.5, 1.0), label="lighter, sun-bleached tops")
        hue = g.combine(g.math("MULTIPLY_ADD", rand(g, -0.5, 0.5, seed, 8), var, 1.0), 1.0,
                        g.math("MULTIPLY_ADD", rand(g, -0.5, 0.5, seed, 9), var, 1.0))
        col = g.vmath("MULTIPLY", g.vmath("SCALE", attr(g, "sh_color", "FLOAT_COLOR"),
                                          scale=g.math("MULTIPLY", gain, k)), hue)
        sat = g.mix(kind_is(g, "bright"), (0.7, 1.0, 0.42, 1.0), (1.05, 1.0, 0.28, 1.0), data_type="RGBA")
        col = g.vmath("MULTIPLY", col, sat, label="fit diffuse albedo ratio to the reference (yellower on bright)")
        col = g.vmath("SCALE", col, scale=g.mix(kind_is(g, "bright"), 1.0, 2.0))
        col = g.vmath("SCALE", col, scale=g.mix(kind_is(g, "herb"), 1.0, 1.3), label="herb layer reads lighter")
        pts = store(g, pts, "nk_color", col, "FLOAT_COLOR")
        pts = store(g, pts, "nk_rand", r)
    with g.frame("Instance the picked leaf shape"):
        shapes = g.group(build_leaf_shapes())["Leaves"]
        leaves = g.node("GeometryNodeInstanceOnPoints", Points=pts, Instance=shapes, Rotation=lrot,
                        Scale=size, **{"Pick Instance": True, "Instance Index": shape})["Instances"]
        leaves = set_mat(g, leaves, mat)
    with g.frame("Shaded core: dark leaves 0.7..1.8 Depth inside woody pieces (capped by piece radius), so gaps read deep"):
        core_sel = kind_is(g, "broadleaf", "bright")
        cp = g.node("GeometryNodeDistributePointsOnFaces", Mesh=env, Seed=g.math("ADD", seed, 61.0),
                    Density=g.mix(core_sel, 0.0, g.math("MULTIPLY", dens, core)))
        psz = g.separate(attr(g, "sh_size", "FLOAT_VECTOR"))
        cin = g.math("MINIMUM", g.math("MULTIPLY", depth, rand(g, 0.7, 1.8, seed, 62)),
                     g.math("MULTIPLY", g.math("MINIMUM", psz["X"], psz["Y"]), 0.9),
                     label="never deeper than the piece is thick (no leaves poking out the far side)")
        cpts = g.node("GeometryNodeSetPosition", Geometry=cp["Points"],
                      Offset=g.vmath("SCALE", cp["Normal"], scale=g.math("MULTIPLY", cin, -1.0)))["Geometry"]
        ccol = g.vmath("MULTIPLY", g.vmath("SCALE", attr(g, "sh_color", "FLOAT_COLOR"),
                                           scale=g.math("MULTIPLY", gain, rand(g, 0.2, 0.45, seed, 63))),
                       (0.7, 1.0, 0.42))
        cpts = store(g, cpts, "nk_color", ccol, "FLOAT_COLOR")
        cpts = store(g, cpts, "nk_rand", rand(g, 0.0, 1.0, seed, 64))
        crot = g.node("FunctionNodeEulerToRotation", Euler=g.combine(
            rand(g, -1.2, 1.2, seed, 65), rand(g, -1.2, 1.2, seed, 66), rand(g, 0.0, TAU, seed, 67)))["Rotation"]
        cleaves = g.node("GeometryNodeInstanceOnPoints", Points=cpts, Instance=shapes, Rotation=crot,
                         Scale=g.math("MULTIPLY", g.math("MULTIPLY", size_broad, 1.6), rand(g, 0.7, 1.3, seed, 68)),
                         **{"Pick Instance": True, "Instance Index": 0})["Instances"]
        leaves = join(g, leaves, set_mat(g, cleaves, mat))
    with g.frame("Under-layer: envelope shrunk by 0.35 Depth, dark, only for the dense yellow-green shrubs"):
        nrm = g.node("GeometryNodeInputNormal")["Normal"]
        ul = g.node("GeometryNodeSetPosition", Geometry=env,
                    Offset=g.vmath("SCALE", nrm, scale=g.math("MULTIPLY", depth, -0.35)))["Geometry"]
        ul = g.node("GeometryNodeDeleteGeometry", props={"domain": "POINT"}, Geometry=ul,
                    Selection=kind_is(g, "broadleaf", "sparse", "strap", "low", "herb"))["Geometry"]
        ul = store(g, ul, "nk_color", g.vmath("SCALE", attr(g, "sh_color", "FLOAT_COLOR"),
                                               scale=g.math("MULTIPLY", gain, 0.06)), "FLOAT_COLOR")
        ul = store(g, ul, "nk_rand", 0.5)
        ul = store(g, ul, "sh_u", 0.5)
        ul = store(g, ul, "sh_v", 1.0)
        ul = set_mat(g, ul, mat)
        empty = g.node("GeometryNodeMeshLine", Count=0)["Mesh"]
        ul = g.node("GeometryNodeSwitch", props={"input_type": "GEOMETRY"}, Switch=under, **{"False": empty,
                                                                                         "True": ul})["Output"]
    g.output("Geometry", "GEOMETRY", join(g, ul, leaves), desc="Leaf instances and under-layer")
    return g.finish()


# ---------------------------------------------------------------------------------------------------------------
@once
def build_herbaceous():
    """'Garden Shrubs Herbaceous': strappy iris/grass clumps, fringe blades, low rosettes and white blossoms."""
    tuft, bl = grass_tuft(), blossom()
    g = Graph("Garden Shrubs Herbaceous", description="Upright strap-leaved clumps (NK Grass Tuft, iris-like) on "
              "strap pieces and along the low lawn-facing fringe of the broadleaf shrubs, low leafy rosettes on "
              "the low pieces, and white blossom sprays where the scan shows white flowers")
    env = g.input("Envelope", "GEOMETRY", desc="Envelope mesh with sh_* attributes")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    clump_d = g.input("Clump Density", "FLOAT", 5.0, min=0.0, max=100.0, desc="Strap clumps per m^2 of strap envelope")
    fringe_d = g.input("Fringe Density", "FLOAT", 2.5, min=0.0, max=100.0,
                       desc="Strap clumps per m^2 on the low sides of broadleaf shrubs")
    strap_h = g.input("Strap Height", "FLOAT", 0.7, min=0.05, max=3.0, subtype="DISTANCE",
                      desc="Tallest strap blade (capped by the piece height)")
    fringe_h = g.input("Fringe Height", "FLOAT", 0.4, min=0.05, max=2.0, subtype="DISTANCE",
                       desc="Tallest blade of the fringe clumps under the shrubs")
    low_d = g.input("Rosette Density", "FLOAT", 9.0, min=0.0, max=200.0, desc="Low rosettes per m^2 of low pieces")
    flower_d = g.input("Flower Density", "FLOAT", 120.0, min=0.0, max=2000.0,
                       desc="Blossoms per m^2 of envelope at flower share 1")
    gain = g.input("Color Gain", "FLOAT", 1.25, min=0.2, max=4.0, desc="Scan colour to albedo gain")
    mat = g.input("Leaf Material", "MATERIAL", desc="Material for blades and rosettes")
    fmat = g.input("Blossom Material", "MATERIAL", desc="Material for the white blossoms")
    with g.frame("Strap clump roots: on strap pieces and on low sides of broadleaf shrubs, dropped to the ground"):
        nz = g.separate(g.node("GeometryNodeInputNormal")["Normal"])["Z"]
        pz = g.separate(g.node("GeometryNodeInputPosition")["Position"])["Z"]
        low_side = boolean(g, "AND", cmp(g, "LESS_THAN", g.math("SUBTRACT", pz, attr(g, "sh_ground")), 0.45),
                           cmp(g, "LESS_THAN", g.math("ABSOLUTE", nz), 0.6))
        dens = g.math("ADD", g.mix(kind_is(g, "strap"), 0.0, clump_d),
                      g.mix(boolean(g, "AND", kind_is(g, "broadleaf", "bright", "herb"), low_side), 0.0, fringe_d))
        cp = g.node("GeometryNodeDistributePointsOnFaces", Mesh=env, Density=dens,
                    Seed=g.math("ADD", seed, 21.0))["Points"]
        cp = g.node("GeometryNodeSetPosition", Geometry=cp, Offset=g.vmath(
            "SCALE", g.vmath("MULTIPLY", attr(g, "sh_out", "FLOAT_VECTOR"), (1.0, 1.0, 0.0)), scale=0.04))["Geometry"]
        ppos = g.separate(g.node("GeometryNodeInputPosition")["Position"])
        cp = g.node("GeometryNodeSetPosition", Geometry=cp,
                    Position=g.combine(ppos["X"], ppos["Y"], attr(g, "sh_ground")))["Geometry"]
    with g.frame("Upright iris tuft on strap pieces (piece height capped by Strap Height), spreading tuft on the fringe"):
        iris = g.group(tuft, Blades=11, Height=1.0, Radius=0.05, Spread=0.45, Seed=seed,
                       **{"Height Min": 0.5, "Blade Width": 0.06, "Curl": 0.3, "Fold": 0.5, "Resolution": 6})["Mesh"]
        iris = store(g, iris, "sh_u", attr(g, "nk_tip"))
        iris = store(g, iris, "sh_v", 0.5)
        upright = g.group(tuft, Blades=16, Height=1.0, Radius=0.06, Spread=0.18, Seed=g.math("ADD", seed, 5.0),
                          **{"Height Min": 0.6, "Blade Width": 0.045, "Curl": 0.12, "Fold": 0.5,
                             "Resolution": 6})["Mesh"]
        upright = store(g, store(g, upright, "sh_u", attr(g, "nk_tip")), "sh_v", 0.5)
        tufts = join(g, g.node("GeometryNodeGeometryToInstance", Geometry=iris)["Instances"],
                     g.node("GeometryNodeGeometryToInstance", Geometry=upright)["Instances"])
        ph = g.separate(attr(g, "sh_size", "FLOAT_VECTOR"))["Z"]
        hgt = g.mix(kind_is(g, "strap"), fringe_h, g.math("MINIMUM", ph, strap_h))
        hgt = g.math("MULTIPLY", hgt, g.mix(kind_is(g, "strap"), rand(g, 0.6, 1.1, seed, 22),
                                            rand(g, 0.85, 1.1, seed, 28)))
        col = g.vmath("MULTIPLY", g.vmath("SCALE", attr(g, "sh_color", "FLOAT_COLOR"),
                                          scale=g.math("MULTIPLY", gain, rand(g, 0.8, 1.2, seed, 23))),
                      (1.75, 1.75, 1.2), label="strap blades read paler than the shrub mass")
        cp = store(g, cp, "nk_color", col, "FLOAT_COLOR")
        cp = store(g, cp, "nk_rand", rand(g, 0.0, 1.0, seed, 24))
        pick = g.node("FunctionNodeFloatToInt", Float=g.mix(kind_is(g, "strap"), 0.0, 1.0))["Integer"]
        clumps = g.node("GeometryNodeInstanceOnPoints", Points=cp, Instance=tufts, Scale=hgt,
                        **{"Pick Instance": True, "Instance Index": pick},
                        Rotation=g.node("FunctionNodeEulerToRotation", Euler=g.combine(
                            rand(g, -0.12, 0.12, seed, 25), rand(g, -0.12, 0.12, seed, 26),
                            rand(g, 0.0, TAU, seed, 27)))["Rotation"])["Instances"]
    with g.frame("Low rosettes: wide, short, spreading leaves on low pieces"):
        rp = g.node("GeometryNodeDistributePointsOnFaces", Mesh=env, Seed=g.math("ADD", seed, 31.0),
                    Density=g.math("ADD", g.mix(kind_is(g, "low"), 0.0, low_d), g.mix(boolean(
                        g, "AND", kind_is(g, "broadleaf", "bright"), low_side), 0.0, g.math("MULTIPLY", fringe_d, 0.7))))
        rp = g.node("GeometryNodeSetPosition", Geometry=rp["Points"], Offset=g.vmath(
            "SCALE", g.vmath("MULTIPLY", attr(g, "sh_out", "FLOAT_VECTOR"), (1.0, 1.0, 0.0)), scale=0.08))["Geometry"]
        rp = g.node("GeometryNodeSetPosition", Geometry=rp,
                    Position=g.combine(ppos["X"], ppos["Y"], attr(g, "sh_ground")))["Geometry"]
        ros = g.group(tuft, Blades=9, Height=1.0, Radius=0.01, Spread=1.15, Seed=g.math("ADD", seed, 3.0),
                      **{"Height Min": 0.6, "Blade Width": 0.4, "Curl": 0.15, "Fold": 0.3, "Resolution": 5})["Mesh"]
        ros = store(g, ros, "sh_u", attr(g, "nk_tip"))
        ros = store(g, ros, "sh_v", 0.5)
        rp = store(g, rp, "nk_color", col, "FLOAT_COLOR")
        rp = store(g, rp, "nk_rand", rand(g, 0.0, 1.0, seed, 32))
        rosettes = g.node("GeometryNodeInstanceOnPoints", Points=rp, Instance=ros,
                          Scale=g.math("MULTIPLY", g.math("MINIMUM", ph, 0.32), rand(g, 0.6, 1.0, seed, 33)),
                          Rotation=g.node("FunctionNodeEulerToRotation", Euler=g.combine(
                              0.0, 0.0, rand(g, 0.0, TAU, seed, 34)))["Rotation"])["Instances"]
        herbs = set_mat(g, join(g, clumps, rosettes), mat)
    with g.frame("Fine white flower sprays (florets on thin stalks) where the scan shows flowers (fewer on bright shrubs)"):
        fdens = g.math("MULTIPLY", flower_d, g.math("POWER", attr(g, "sh_flower"), 1.5))
        fdens = g.mix(kind_is(g, "strap", "low"), fdens, 0.0)
        fdens = g.math("MULTIPLY", fdens, g.mix(kind_is(g, "bright"), 1.0, 0.35), label="bright: leaf highlights "
                       "also read as white in the scan, so fewer blossoms")
        fp = g.node("GeometryNodeDistributePointsOnFaces", Mesh=env, Density=fdens,
                    Seed=g.math("ADD", seed, 41.0))
        fpts = g.node("GeometryNodeSetPosition", Geometry=fp["Points"],
                      Offset=g.vmath("SCALE", fp["Normal"], scale=0.1))["Geometry"]
        # a fine spray: ~60 small florets (1.2 cm), ~14 cm across, on thin stalks fanning up and out from one point
        floret = g.group(bl, Petals=5, Size=0.012, Cup=0.4, **{"Petal Width": 0.6, "Centre Size": 0.3})["Mesh"]
        spray = g.node("GeometryNodePoints", Count=60)["Points"]
        sx = g.node("FunctionNodeRandomValue", props={"data_type": "FLOAT_VECTOR"}, Min=(-0.07, -0.07, 0.01),
                    Max=(0.07, 0.07, 0.1), Seed=g.math("ADD", seed, 43.0))["Value"]
        spray = g.node("GeometryNodeSetPosition", Geometry=spray, Position=sx)["Geometry"]
        sp = g.node("GeometryNodeInputPosition")["Position"]
        heads = g.node("GeometryNodeInstanceOnPoints", Points=spray, Instance=floret,
                       Scale=rand(g, 0.7, 1.15, seed, 44))["Instances"]
        stalk = g.node("GeometryNodeMeshCylinder", Vertices=3, Radius=0.0012, Depth=1.0)["Mesh"]
        stalk = g.node("GeometryNodeTransform", Geometry=stalk, Translation=(0.0, 0.0, 0.5))["Geometry"]
        srot = g.node("FunctionNodeAlignRotationToVector", props={"axis": "Z"}, Vector=sp)["Rotation"]
        stalks = g.node("GeometryNodeInstanceOnPoints", Points=spray, Instance=stalk, Rotation=srot,
                        Scale=g.combine(1.0, 1.0, g.vmath("LENGTH", sp)["Value"]))["Instances"]
        stalks = store(g, g.node("GeometryNodeRealizeInstances", Geometry=stalks)["Geometry"], "nk_part", 2.0)
        head = join(g, g.node("GeometryNodeRealizeInstances", Geometry=heads)["Geometry"], stalks)
        flowers = g.node("GeometryNodeInstanceOnPoints", Points=fpts, Instance=head, Rotation=fp["Rotation"],
                         Scale=rand(g, 0.7, 1.3, seed, 42))["Instances"]
        flowers = set_mat(g, flowers, fmat)
    g.output("Geometry", "GEOMETRY", join(g, herbs, flowers), desc="Clumps, rosettes and blossoms")
    return g.finish()

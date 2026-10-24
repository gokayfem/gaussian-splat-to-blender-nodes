"""Reusable Geometry Nodes sub-groups for the garden boundary, plus python helpers that put fitted polyline
points into a graph (sparse control points only: a Mesh Line whose vertices are set from an Index Switch, then
Mesh to Curve, all inside Geometry Nodes).

Curve convention: boundary polylines lie on z = 0 and carry the FLOAT point attribute ``bnd_top`` (top height of
the wall/hedge/fence at that point, metres). Slabs store ``bnd_s`` (arc length) and ``bnd_v`` (0 bottom .. 1 top)
for the shaders and the foliage colouring.
"""
import math

from nodekit.graph import Graph, once

TAU = 2.0 * math.pi


# ---- python idioms (not groups) ---------------------------------------------------------------------------------
def index_switch(g, dtype, values, index):
    """Index Switch node holding constant ``values`` (fitted numbers), selected by ``index``."""
    n = g.node("GeometryNodeIndexSwitch", props={"data_type": dtype}, Index=index)
    while len(n.b.index_switch_items) < len(values):
        n.b.index_switch_items.new()
    for k, v in enumerate(values):
        n.b.inputs[k + 1].default_value = v
    return n["Output"]


def store(g, geo, name, value, dtype="FLOAT", domain="POINT"):
    return g.node("GeometryNodeStoreNamedAttribute", props={"data_type": dtype, "domain": domain},
                  Geometry=geo, Name=name, Value=value)["Geometry"]


def attr(g, name, dtype="FLOAT"):
    return g.node("GeometryNodeInputNamedAttribute", props={"data_type": dtype}, Name=name)["Attribute"]


def rand(g, lo, hi, seed, k, ident=None, dtype="FLOAT"):
    kw = {"Min": lo, "Max": hi, "Seed": g.math("ADD", seed, float(k))}
    if ident is not None:
        kw["ID"] = ident
    return g.node("FunctionNodeRandomValue", props={"data_type": dtype}, **kw)["Value"]


def poly_curve(g, pts, label="Polyline"):
    """Poly curve through fitted points [(x, y, top), ...] at z = 0, with bnd_top per point."""
    idx = g.node("GeometryNodeInputIndex")
    line = g.node("GeometryNodeMeshLine", label=label, Count=len(pts))
    pos = index_switch(g, "VECTOR", [(p[0], p[1], 0.0) for p in pts], idx)
    top = index_switch(g, "FLOAT", [float(p[2]) for p in pts], idx)
    m = g.node("GeometryNodeSetPosition", Geometry=line["Mesh"], Position=pos)["Geometry"]
    m = store(g, m, "bnd_top", top)
    return g.node("GeometryNodeMeshToCurve", Mesh=m)["Curve"]


def point_set(g, pts, label="Points"):
    """A point cloud from fitted positions (used for convex-hull pieces: roof slabs, doors, plaques)."""
    idx = g.node("GeometryNodeInputIndex")
    return g.node("GeometryNodePoints", label=label, Count=len(pts),
                  Position=index_switch(g, "VECTOR", [tuple(p) for p in pts], idx))["Points"]


def hull(g, pts, material, label="Hull"):
    h = g.node("GeometryNodeConvexHull", Geometry=point_set(g, pts, label))["Convex Hull"]
    return g.node("GeometryNodeSetMaterial", Geometry=h, Material=material)["Geometry"]


def box_corners(center, size, yaw_deg, pitch_deg=0.0):
    """8 corners of a box (centre, size, yaw about Z, optional pitch about the box's local X) for hulls."""
    cx, cy, cz = center
    sx, sy, sz = (v / 2 for v in size)
    cy_, sy_ = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    cp, sp = math.cos(math.radians(pitch_deg)), math.sin(math.radians(pitch_deg))
    out = []
    for dx in (-sx, sx):
        for dy in (-sy, sy):
            for dz in (-sz, sz):
                y2, z2 = dy * cp - dz * sp, dy * sp + dz * cp
                out.append((cx + dx * cy_ - y2 * sy_, cy + dx * sy_ + y2 * cy_, cz + z2))
    return out


# ---- groups -----------------------------------------------------------------------------------------------------
@once
def leaf_card():
    """Low-poly leaf (3x3 grid, 8 triangles): base at origin, tip at +X, folded midrib, drooping tip."""
    g = Graph("Garden Boundary Leaf Card", description="A cheap distant leaf: a 3x3 grid shaped to a pointed "
                                                       "ellipse (base at the origin, tip at +X = 1), its halves "
                                                       "folded up along the midrib and the tip drooping")
    w = g.input("Width", "FLOAT", 0.45, min=0.05, max=1.5, subtype="FACTOR", desc="Widest width as share of length")
    fold = g.input("Fold", "FLOAT", 0.35, min=-1.0, max=1.0, desc="Rise of each half per unit of half-width")
    curl = g.input("Curl", "FLOAT", 0.15, min=-1.0, max=1.0, desc="Tip droop as share of length")
    grid = g.node("GeometryNodeMeshGrid", **{"Size X": 1.0, "Size Y": 1.0, "Vertices X": 3, "Vertices Y": 3})
    p = g.separate(g.node("GeometryNodeInputPosition"))
    x = g.math("ADD", p["X"], 0.5)
    prof = g.math("SINE", g.math("MULTIPLY", x, math.pi))
    y = g.math("MULTIPLY", g.math("MULTIPLY", p["Y"], w), prof)
    z = g.math("SUBTRACT", g.math("MULTIPLY", g.math("ABSOLUTE", y), fold),
               g.math("MULTIPLY", g.math("MULTIPLY", x, x), curl))
    out = g.node("GeometryNodeSetPosition", Geometry=grid["Mesh"], Position=g.combine(x, y, z))
    g.output("Mesh", "GEOMETRY", out["Geometry"], desc="Leaf mesh")
    return g.finish(split_inputs=False)


@once
def curve_slab():
    """A solid slab along a boundary polyline: bottom..top from bnd_top, bent through NK Curve Bend."""
    from library.curve import curve_bend
    bend = curve_bend()
    g = Graph("Garden Boundary Curve Slab",
              description="A box modelled in curve space (X = arc length, Y = across, Z = 0..1) and bent onto a "
                          "boundary polyline. Height per vertex comes from the curve's bnd_top attribute sampled at "
                          "its arc length: top = Top From Curve x bnd_top + Top Offset, bottom = Bottom + Bottom "
                          "From Top x bnd_top. Taper narrows the top (hedges). Stores bnd_s and bnd_v")
    curve = g.input("Curve", "GEOMETRY", desc="Poly curve on z = 0 with a bnd_top point attribute")
    thick = g.input("Thickness", "FLOAT", 0.25, min=0.005, max=5.0, subtype="DISTANCE", desc="Slab thickness")
    off = g.input("Offset", "FLOAT", 0.0, min=-5.0, max=5.0, subtype="DISTANCE",
                  desc="Lateral shift of the slab centre (+ left of travel)")
    bottom = g.input("Bottom", "FLOAT", -0.05, min=-2.0, max=10.0, subtype="DISTANCE", desc="Bottom height")
    bft = g.input("Bottom From Top", "FLOAT", 0.0, min=0.0, max=1.0, subtype="FACTOR",
                  desc="Share of bnd_top added to Bottom (1 = bottom measured from the top, for capping rails)")
    tfc = g.input("Top From Curve", "FLOAT", 1.0, min=0.0, max=2.0, subtype="FACTOR",
                  desc="Multiplier of bnd_top for the top height (0 = constant top at Top Offset)")
    toff = g.input("Top Offset", "FLOAT", 0.0, min=-5.0, max=10.0, subtype="DISTANCE", desc="Added to the top")
    taper = g.input("Taper", "FLOAT", 0.0, min=0.0, max=1.0, subtype="FACTOR",
                    desc="Narrowing of the top (thickness x (1 - Taper v^3))")
    step = g.input("Step", "FLOAT", 0.3, min=0.02, max=5.0, subtype="DISTANCE", desc="Vertex spacing along")
    rows = g.input("Rows", "INT", 2, min=2, max=64, desc="Vertex rows from bottom to top")
    with g.frame("Corner-preserving subdivision so sampled tangents stay on each straight run"):
        sub = g.node("GeometryNodeSubdivideCurve", Curve=curve, Cuts=10)["Curve"]
        length = g.node("GeometryNodeCurveLength", Curve=sub)["Length"]
    with g.frame("Unit box in curve space: x 0..L, y -0.5..0.5, z 0..1"):
        nx = g.math("ADD", g.math("CEIL", g.math("DIVIDE", length, step)), 1.0)
        cube = g.node("GeometryNodeMeshCube", Size=g.combine(length, 1.0, 1.0),
                      **{"Vertices X": nx, "Vertices Y": 2, "Vertices Z": rows})
        cube = g.node("GeometryNodeTransform", Geometry=cube["Mesh"],
                      Translation=g.combine(g.math("MULTIPLY", length, 0.5), 0.0, 0.5))["Geometry"]
    with g.frame("Heights from bnd_top sampled at each vertex's arc length"):
        p = g.separate(g.node("GeometryNodeInputPosition"))
        smp = g.node("GeometryNodeSampleCurve", props={"mode": "LENGTH", "data_type": "FLOAT",
                                                       "use_all_curves": True},
                     Curves=sub, Value=attr(g, "bnd_top"), Length=p["X"])
        top = g.math("MULTIPLY_ADD", smp["Value"], tfc, toff)
        bot = g.math("MULTIPLY_ADD", smp["Value"], bft, bottom)
        z = g.math("MULTIPLY_ADD", p["Z"], g.math("SUBTRACT", top, bot), bot)
        shrink = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", taper, g.math("POWER", p["Z"], 3.0)))
        y = g.math("ADD", off, g.math("MULTIPLY", g.math("MULTIPLY", p["Y"], thick), shrink))
        geo = store(g, cube, "bnd_s", p["X"])
        geo = store(g, geo, "bnd_v", p["Z"])
        geo = g.node("GeometryNodeSetPosition", Geometry=geo, Position=g.combine(p["X"], y, z))["Geometry"]
    with g.frame("Bend onto the boundary polyline"):
        out = g.group(bend, Geometry=geo, Curve=sub, Height=0.0, **{"Extend Ends": False})
    g.output("Mesh", "GEOMETRY", out["Geometry"], desc="Slab mesh with bnd_s and bnd_v")
    return g.finish()


@once
def lumpy():
    """Displace a mesh along its normals by 3D noise (foliage masses)."""
    g = Graph("Garden Boundary Lumpy", description="Push vertices along their normals by fractal noise of world "
                                                  "position (centred, so the mass keeps its mean size)")
    mesh = g.input("Mesh", "GEOMETRY", desc="Envelope mesh")
    amount = g.input("Amount", "FLOAT", 0.2, min=0.0, max=3.0, subtype="DISTANCE", desc="Peak displacement")
    scale = g.input("Scale", "FLOAT", 1.5, min=0.05, max=20.0, desc="Noise frequency per metre")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Shifts the noise field")
    pos = g.node("GeometryNodeInputPosition")
    shift = g.combine(g.math("MULTIPLY", seed, 7.31), g.math("MULTIPLY", seed, 3.17), 0.0)
    nz = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "3D"},
                Vector=g.vmath("ADD", pos, shift), Scale=scale, Detail=3.0, Roughness=0.55)
    bulge = g.math("MULTIPLY", g.math("SUBTRACT", nz["Fac"], 0.5), 2.0)
    d = g.math("MULTIPLY", bulge, amount)
    nrm = g.node("GeometryNodeInputNormal")
    geo = store(g, mesh, "bnd_bulge", bulge)
    out = g.node("GeometryNodeSetPosition", Geometry=geo, Offset=g.vmath("SCALE", nrm, scale=d))
    g.output("Mesh", "GEOMETRY", out["Geometry"], desc="Displaced mesh with bnd_bulge (-1 hollow .. 1 bulge)")
    return g.finish(split_inputs=False)


@once
def foliage_skin():
    """Clothe an envelope in leaf cards (normal-aligned, tilted), optional blossoms and a dark under-layer."""
    lc_tree = leaf_card()
    g = Graph("Garden Boundary Foliage Skin",
              description="Leaf cards scattered over an envelope mesh (aligned to it, tips lifted, random spin and "
                          "size), tinted from Shade Color (lower, inward) to Lit Color (upward-facing, upper) by "
                          "normal Z and bnd_v, with per-leaf jitter; optional blossom specks; the envelope stays as "
                          "a dark under-layer so gaps read as depth, not holes")
    mesh = g.input("Mesh", "GEOMETRY", desc="Envelope mesh, normals outwards")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    dens = g.input("Leaf Density", "FLOAT", 180.0, min=0.0, max=5000.0, desc="Leaves per square metre")
    size = g.input("Leaf Size", "FLOAT", 0.09, min=0.005, max=2.0, subtype="DISTANCE", desc="Leaf length")
    lift = g.input("Leaf Lift", "FLOAT", 0.6, min=-1.5, max=1.5, subtype="ANGLE", desc="Tip rise off the surface")
    shade = g.input("Shade Color", "COLOR", (0.05, 0.09, 0.025, 1.0), desc="Leaf colour low/inward (linear)")
    lit = g.input("Lit Color", "COLOR", (0.2, 0.3, 0.08, 1.0), desc="Leaf colour on top/upper faces (linear)")
    var = g.input("Color Variation", "FLOAT", 0.3, min=0.0, max=1.0, subtype="FACTOR", desc="Per-leaf value jitter")
    under = g.input("Under Factor", "FLOAT", 0.45, min=0.0, max=1.0, subtype="FACTOR",
                    desc="Under-layer brightness as a share of Shade Color")
    bdens = g.input("Blossom Density", "FLOAT", 0.0, min=0.0, max=500.0, desc="Blossom specks per square metre")
    bcol = g.input("Blossom Color", "COLOR", (0.8, 0.8, 0.75, 1.0), desc="Blossom colour (linear)")
    bsize = g.input("Blossom Size", "FLOAT", 0.05, min=0.005, max=1.0, subtype="DISTANCE", desc="Blossom radius")
    babove = g.input("Blossom Above", "FLOAT", 0.0, min=0.0, max=1.0, subtype="FACTOR",
                     desc="Blossoms only where bnd_v (height share of the envelope) exceeds this")
    bclus = g.input("Blossom Clustering", "FLOAT", 0.0, min=0.0, max=0.95, subtype="FACTOR",
                    desc="Blossoms only where a position noise exceeds 0.5 + this/4 (groups them in clusters)")
    bshade = g.input("Bulge Shading", "FLOAT", 0.45, min=0.0, max=2.0, subtype="FACTOR",
                     desc="How much bulges (bnd_bulge) brighten and hollows darken the leaves")
    patch = g.input("Patchiness", "FLOAT", 0.5, min=0.0, max=2.0, subtype="FACTOR",
                    desc="Large light/dark patches (noise of position) in the leaf tint")
    pscale = g.input("Patch Scale", "FLOAT", 0.8, min=0.05, max=10.0, desc="Patch noise frequency per metre")
    mat = g.input("Material", "MATERIAL", desc="Foliage material (reads nk_color / nk_rand)")
    with g.frame("Leaf points on the envelope, tilted off the surface, random spin and size"):
        dist = g.node("GeometryNodeDistributePointsOnFaces", Mesh=mesh, Density=dens, Seed=seed)
        tilt = g.node("FunctionNodeEulerToRotation", Euler=g.combine(
            rand(g, -0.4, 0.4, seed, 1), g.math("SUBTRACT", rand(g, -0.3, 0.3, seed, 2), lift),
            rand(g, 0.0, TAU, seed, 3)))["Rotation"]
        rot = g.node("FunctionNodeRotateRotation", props={"rotation_space": "LOCAL"}, Rotation=dist["Rotation"],
                     **{"Rotate By": tilt})["Rotation"]
    with g.frame("Leaf tint: shade to lit by facing-up and height, jittered per leaf"):
        nz = g.separate(dist["Normal"])["Z"]
        up = g.map_range(nz, -0.2, 0.9, 0.0, 1.0)
        fac = g.math("MULTIPLY_ADD", attr(g, "bnd_v"), 0.25, g.math("MULTIPLY", up, 0.45))
        fac = g.math("MULTIPLY_ADD", attr(g, "bnd_bulge"), bshade, fac)
        pn = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "3D"},
                    Vector=g.node("GeometryNodeInputPosition"), Scale=pscale, Detail=2.0, Roughness=0.5)
        fac = g.math("MULTIPLY_ADD", g.math("SUBTRACT", pn["Fac"], 0.5), g.math("MULTIPLY", patch, 2.0), fac)
        r = rand(g, 0.0, 1.0, seed, 5)
        fac = g.math("ADD", fac, g.math("MULTIPLY", g.math("SUBTRACT", r, 0.5), var), clamp=True)
        col = g.mix(fac, shade, lit, data_type="RGBA")["Result"]
        col = g.vmath("SCALE", col, scale=g.math("MULTIPLY_ADD", rand(g, -0.5, 0.5, seed, 6), var, 1.0))
        pts = store(g, dist["Points"], "nk_color", col, "FLOAT_COLOR")
        pts = store(g, pts, "nk_rand", r)
    with g.frame("Instance leaf cards"):
        leaf = g.group(lc_tree)
        leaves = g.node("GeometryNodeInstanceOnPoints", Points=pts, Instance=leaf["Mesh"], Rotation=rot,
                        Scale=g.math("MULTIPLY", size, rand(g, 0.7, 1.3, seed, 4)))["Instances"]
    with g.frame("Blossom specks pushed just above the leaves"):
        db = g.node("GeometryNodeDistributePointsOnFaces", Mesh=mesh, Density=bdens,
                    Seed=g.math("ADD", seed, 17.0),
                    Selection=g.math("MULTIPLY", g.math("GREATER_THAN", attr(g, "bnd_v"), babove),
                                     g.math("GREATER_THAN", g.node("ShaderNodeTexNoise",
                                                                   props={"noise_dimensions": "3D"},
                                                                   Vector=g.node("GeometryNodeInputPosition"),
                                                                   Scale=2.2, Detail=1.0)["Fac"],
                                            g.math("MULTIPLY_ADD", bclus, 0.25, 0.5))))
        bp = g.node("GeometryNodeSetPosition", Geometry=db["Points"],
                    Offset=g.vmath("SCALE", db["Normal"], scale=g.math("MULTIPLY", size, 0.4)))["Geometry"]
        bp = store(g, bp, "nk_color", g.vmath("SCALE", bcol, scale=rand(g, 0.8, 1.1, seed, 18)), "FLOAT_COLOR")
        ico = g.node("GeometryNodeMeshIcoSphere", Radius=1.0, Subdivisions=2)
        ico = g.node("GeometryNodeTransform", Geometry=ico["Mesh"], Scale=(1.0, 1.0, 0.7))
        blos = g.node("GeometryNodeInstanceOnPoints", Points=bp, Instance=ico["Geometry"],
                      Scale=g.math("MULTIPLY", bsize, rand(g, 0.6, 1.3, seed, 19)))["Instances"]
    with g.frame("Dark under-layer: the envelope itself"):
        base = store(g, mesh, "nk_color", g.vmath("SCALE", shade, scale=under), "FLOAT_COLOR")
        base = g.node("GeometryNodeSetShadeSmooth", Geometry=base)["Geometry"]
        join = g.node("GeometryNodeJoinGeometry")
        for geo in (base, leaves, blos):
            g.connect(geo, join.i("Geometry"))
        out = g.node("GeometryNodeSetMaterial", Geometry=join["Geometry"], Material=mat)
    g.output("Geometry", "GEOMETRY", out["Geometry"], desc="Under-layer mesh plus leaf and blossom instances")
    return g.finish()


@once
def slat_row():
    """Upright boards (or posts) at even pitch along a boundary polyline, top from bnd_top."""
    from library.curve import curve_frame
    frame = curve_frame()
    g = Graph("Garden Boundary Slat Row",
              description="Boards of Slat Width at a pitch of Slat Width + Gap, centred along a polyline (level "
                          "frame from NK Curve Frame), each from Bottom up to bnd_top + Top Offset with small "
                          "random height and lean; stores nk_rand per board. Also used for posts")
    curve = g.input("Curve", "GEOMETRY", desc="Poly curve on z = 0 with bnd_top")
    w = g.input("Slat Width", "FLOAT", 0.1, min=0.01, max=2.0, subtype="DISTANCE", desc="Board width")
    gap = g.input("Gap", "FLOAT", 0.01, min=0.0, max=5.0, subtype="DISTANCE", desc="Gap between boards")
    th = g.input("Thickness", "FLOAT", 0.02, min=0.003, max=1.0, subtype="DISTANCE", desc="Board thickness")
    off = g.input("Offset", "FLOAT", 0.0, min=-2.0, max=2.0, subtype="DISTANCE", desc="Lateral shift (+ left)")
    bottom = g.input("Bottom", "FLOAT", 0.0, min=-1.0, max=5.0, subtype="DISTANCE", desc="Board bottom height")
    toff = g.input("Top Offset", "FLOAT", 0.0, min=-3.0, max=3.0, subtype="DISTANCE", desc="Added to bnd_top")
    jit = g.input("Height Jitter", "FLOAT", 0.02, min=0.0, max=0.5, subtype="DISTANCE", desc="Random top jitter")
    lean = g.input("Lean", "FLOAT", 0.01, min=0.0, max=0.3, subtype="ANGLE", desc="Random lean of each board")
    shift = g.input("Shift", "FLOAT", 0.0, min=-2.0, max=2.0, subtype="DISTANCE",
                    desc="Move every board along the curve (edge strips sit at board edges)")
    twist = g.input("Twist", "FLOAT", 0.0, min=0.0, max=0.5, subtype="ANGLE",
                    desc="Constant turn of each board about Z (featheredge boards overlap at an angle)")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    mat = g.input("Material", "MATERIAL", desc="Board material")
    with g.frame("Board count and arc-length centres"):
        sub = g.node("GeometryNodeSubdivideCurve", Curve=curve, Cuts=10)["Curve"]
        length = g.node("GeometryNodeCurveLength", Curve=sub)["Length"]
        pitch = g.math("ADD", w, gap)
        n = g.math("FLOOR", g.math("DIVIDE", length, pitch))
        pts = g.node("GeometryNodePoints", Count=n)["Points"]
        idx = g.node("GeometryNodeInputIndex")
        margin = g.math("MULTIPLY", g.math("SUBTRACT", length, g.math("MULTIPLY", n, pitch)), 0.5)
        s = g.math("ADD", g.math("ADD", g.math("MULTIPLY", g.math("ADD", idx, 0.5), pitch), margin), shift)
    with g.frame("Frame, height and lean per board"):
        f = g.group(frame, Curve=sub, Length=s, Offset=off, Height=bottom)
        smp = g.node("GeometryNodeSampleCurve", props={"mode": "LENGTH", "data_type": "FLOAT",
                                                       "use_all_curves": True},
                     Curves=sub, Value=attr(g, "bnd_top"), Length=s)
        h = g.math("MAXIMUM", g.math("MULTIPLY_ADD", rand(g, -1.0, 1.0, seed, 1, ident=idx), jit,
                                     g.math("SUBTRACT", g.math("ADD", smp["Value"], toff), bottom)), 0.05)
        tilt = g.node("FunctionNodeEulerToRotation", Euler=g.vmath("SCALE", g.combine(
            rand(g, -1.0, 1.0, seed, 2, ident=idx), rand(g, -0.3, 0.3, seed, 3, ident=idx),
            g.math("DIVIDE", twist, g.math("MAXIMUM", lean, 1e-4))), scale=lean))
        rot = g.node("FunctionNodeRotateRotation", props={"rotation_space": "LOCAL"}, Rotation=f["Rotation"],
                     **{"Rotate By": tilt["Rotation"]})["Rotation"]
        pts = g.node("GeometryNodeSetPosition", Geometry=pts, Position=f["Position"])["Geometry"]
        pts = store(g, pts, "nk_rand", rand(g, 0.0, 1.0, seed, 4, ident=idx))
    with g.frame("Unit board standing on its base, scaled per point"):
        cube = g.node("GeometryNodeMeshCube", Size=(1.0, 1.0, 1.0))
        cube = g.node("GeometryNodeTransform", Geometry=cube["Mesh"], Translation=(0.0, 0.0, 0.5))["Geometry"]
        inst = g.node("GeometryNodeInstanceOnPoints", Points=pts, Instance=cube, Rotation=rot,
                      Scale=g.combine(w, th, h))["Instances"]
        out = g.node("GeometryNodeSetMaterial", Geometry=inst, Material=mat)
    g.output("Instances", "GEOMETRY", out["Geometry"], desc="Board instances")
    return g.finish()


@once
def canopy_blobs():
    """Distant tree canopies: one noisy ellipsoid per fitted centre/radius, realized for the foliage skin."""
    g = Graph("Garden Boundary Canopy Blob", description="An ellipsoid canopy envelope (icosphere scaled by "
                                                         "Radii at Center), stored bnd_v = height share, for "
                                                         "Garden Boundary Foliage Skin")
    c = g.input("Center", "VECTOR", (0.0, 0.0, 4.0), subtype="TRANSLATION", desc="Canopy centre (world)")
    r = g.input("Radii", "VECTOR", (2.0, 2.0, 1.5), subtype="XYZ", desc="Ellipsoid radii (m)")
    ico = g.node("GeometryNodeMeshIcoSphere", Radius=1.0, Subdivisions=3)
    z = g.separate(g.node("GeometryNodeInputPosition"))["Z"]
    geo = store(g, ico["Mesh"], "bnd_v", g.math("MULTIPLY_ADD", z, 0.5, 0.5))
    geo = g.node("GeometryNodeTransform", Geometry=geo, Translation=c, Scale=r)
    g.output("Mesh", "GEOMETRY", geo["Geometry"], desc="Canopy envelope")
    return g.finish(split_inputs=False)


@once
def clump_row():
    """Separate plant mounds along a polyline (border planting): one squashed noisy sphere per spaced point."""
    g = Graph("Garden Boundary Clump Row",
              description="Plant mounds every Spacing (jittered) along a boundary polyline: icospheres with random "
                          "radius, height from bnd_top (x Height Jitter), pushed sideways at random, realized and "
                          "stored bnd_v (height share) for Garden Boundary Foliage Skin")
    curve = g.input("Curve", "GEOMETRY", desc="Poly curve on z = 0 with bnd_top")
    spacing = g.input("Spacing", "FLOAT", 0.7, min=0.1, max=5.0, subtype="DISTANCE", desc="Mean mound spacing")
    rmin = g.input("Radius Min", "FLOAT", 0.3, min=0.02, max=3.0, subtype="DISTANCE", desc="Smallest mound radius")
    rmax = g.input("Radius Max", "FLOAT", 0.55, min=0.02, max=3.0, subtype="DISTANCE", desc="Largest mound radius")
    hj = g.input("Height Jitter", "FLOAT", 0.35, min=0.0, max=1.0, subtype="FACTOR",
                 desc="Random reduction of each mound's height below bnd_top")
    side = g.input("Side Jitter", "FLOAT", 0.25, min=0.0, max=3.0, subtype="DISTANCE", desc="Random sideways shift")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    with g.frame("Jittered points along the curve with their tops"):
        rs = g.node("GeometryNodeResampleCurve", Curve=curve, Mode="Length", Length=spacing)["Curve"]
        pts = g.node("GeometryNodeCurveToPoints", props={"mode": "EVALUATED"}, Curve=rs)
        idx = g.node("GeometryNodeInputIndex")
        top = attr(g, "bnd_top")
        jit = g.combine(rand(g, -1.0, 1.0, seed, 1, ident=idx), rand(g, -1.0, 1.0, seed, 2, ident=idx), 0.0)
        p2 = g.node("GeometryNodeSetPosition", Geometry=pts["Points"],
                    Offset=g.vmath("SCALE", jit, scale=side))["Geometry"]
    with g.frame("Mound per point: radius, height = top x (1 - jitter), sitting on the ground"):
        r = rand(g, 0.0, 1.0, seed, 3, ident=idx)
        rad = g.math("ADD", rmin, g.math("MULTIPLY", r, g.math("SUBTRACT", rmax, rmin)))
        h = g.math("MULTIPLY", top, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", hj, rand(g, 0.0, 1.0, seed, 4,
                                                                                        ident=idx))))
        ico = g.node("GeometryNodeMeshIcoSphere", Radius=1.0, Subdivisions=3)
        zz = g.separate(g.node("GeometryNodeInputPosition"))["Z"]
        ico = store(g, ico["Mesh"], "bnd_v", g.math("MULTIPLY_ADD", zz, 0.5, 0.5))
        ico = g.node("GeometryNodeTransform", Geometry=ico, Translation=(0.0, 0.0, 0.5),
                     Scale=(1.0, 1.0, 0.5))["Geometry"]
        inst = g.node("GeometryNodeInstanceOnPoints", Points=p2, Instance=ico,
                      Rotation=g.combine(0.0, 0.0, rand(g, 0.0, TAU, seed, 5, ident=idx)),
                      Scale=g.combine(rad, g.math("MULTIPLY", rad, 0.85), h))["Instances"]
        out = g.node("GeometryNodeRealizeInstances", Geometry=inst)
    g.output("Mesh", "GEOMETRY", out["Geometry"], desc="Realized mound envelopes")
    return g.finish()

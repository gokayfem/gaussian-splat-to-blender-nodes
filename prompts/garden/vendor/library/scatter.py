"""Distributing instances on surfaces and along curves.

Every scatter group returns the instances and the points behind them, so the points can be reused (for a second
layer, for masks, for culling). Points and instances carry:
    nk_rand   FLOAT 0..1 per instance (tints in shaders via an Attribute node after realize)
    nk_scale  FLOAT     the uniform scale applied
    nk_rot    QUATERNION the rotation applied
NK Clumps also writes nk_clump (INT, index of the clump) and nk_dist (FLOAT, 0 at the clump centre, 1 at its rim).
"""
import math
from nodekit.graph import Graph
from nodekit.library import nodegroup
from library.curve import curve_samples

TAU = 2.0 * math.pi


# ---- small node idioms (python helpers, not groups) ----------------------------------------------------------
def _store(g, geo, name, value, dtype="FLOAT", domain="POINT"):
    return g.node("GeometryNodeStoreNamedAttribute", props={"data_type": dtype, "domain": domain},
                  Geometry=geo, Name=name, Value=value)["Geometry"]


def _attr(g, name, dtype="FLOAT"):
    return g.node("GeometryNodeInputNamedAttribute", props={"data_type": dtype}, Name=name)["Attribute"]


def _rand(g, lo, hi, seed, k, ident=None, dtype="FLOAT"):
    n = g.node("FunctionNodeRandomValue", props={"data_type": dtype}, Min=lo, Max=hi,
               Seed=g.math("ADD", seed, float(k)))
    if ident is not None:
        g.connect(ident, n.i("ID"))
    return n["Value"]


def _cmp(g, op, a, b):
    return g.node("FunctionNodeCompare", props={"data_type": "FLOAT", "operation": op}, A=a, B=b)["Result"]


def _switch(g, typ, cond, false=None, true=None):
    n = g.node("GeometryNodeSwitch", props={"input_type": typ}, Switch=cond)
    g.connect(false, n.i("False"))
    g.connect(true, n.i("True"))
    return n["Output"]


def _distribute(g, mesh, sel, density, weight, min_dist, seed):
    """Random points at density x weight; Poisson disk (no two closer than min_dist) when min_dist > 0."""
    rnd = g.node("GeometryNodeDistributePointsOnFaces", props={"distribute_method": "RANDOM"}, Mesh=mesh,
                 Selection=sel, Density=g.math("MULTIPLY", density, weight), Seed=seed)
    poi = g.node("GeometryNodeDistributePointsOnFaces", props={"distribute_method": "POISSON"}, Mesh=mesh,
                 Selection=sel, Seed=seed, **{"Distance Min": min_dist, "Density Max": density,
                                              "Density Factor": weight})
    use_poi = _cmp(g, "GREATER_THAN", min_dist, 0.0)
    pts = _store(g, rnd["Points"], "nk_normal", rnd["Normal"], "FLOAT_VECTOR")
    pts = _store(g, pts, "nk_rot", rnd["Rotation"], "QUATERNION")
    ppts = _store(g, poi["Points"], "nk_normal", poi["Normal"], "FLOAT_VECTOR")
    ppts = _store(g, ppts, "nk_rot", poi["Rotation"], "QUATERNION")
    return _switch(g, "GEOMETRY", use_poi, pts, ppts)


def _if_any(g, pts, *outputs):
    """Pass ``outputs`` through only when ``pts`` has points; otherwise output empty geometry. The Switch is lazy,
    so on an empty distribution (Density 0, everything masked) nothing downstream is evaluated and no node reads
    an attribute that the empty point cloud cannot carry (no "Attribute does not exist" warnings)."""
    n = g.node("GeometryNodeAttributeDomainSize", props={"component": "POINTCLOUD"}, Geometry=pts)["Point Count"]
    any_ = g.node("FunctionNodeCompare", props={"data_type": "INT", "operation": "GREATER_THAN"}, A=n, B=0)["Result"]
    return [_switch(g, "GEOMETRY", any_, None, o) for o in outputs]


def _orient(g, normal, align, spin_max, tilt, seed, k, ident=None):
    """Random spin about Z, Z blended from world up to `normal` by `align`, then a random local tilt."""
    spin = g.node("FunctionNodeEulerToRotation", Euler=g.combine(0.0, 0.0, _rand(g, 0.0, spin_max, seed, k, ident)))
    aligned = g.node("FunctionNodeAlignRotationToVector", props={"axis": "Z", "pivot_axis": "AUTO"},
                     Rotation=spin["Rotation"], Factor=align, Vector=normal)["Rotation"]
    nt = g.math("MULTIPLY", tilt, -1.0)
    tilt_r = g.node("FunctionNodeEulerToRotation", Euler=g.combine(_rand(g, nt, tilt, seed, k + 1, ident),
                                                                   _rand(g, nt, tilt, seed, k + 2, ident), 0.0))
    return g.node("FunctionNodeRotateRotation", props={"rotation_space": "LOCAL"}, Rotation=aligned,
                  **{"Rotate By": tilt_r["Rotation"]})["Rotation"]


def _instance(g, pts, inst, rot, scale, rand, drop=("nk_normal",)):
    """Store rotation, scale and nk_rand on the points, drop working attributes, then instance with them."""
    pts = _store(g, pts, "nk_rand", rand)
    pts = _store(g, pts, "nk_scale", scale)
    pts = _store(g, pts, "nk_rot", rot, "QUATERNION")
    for name in drop:
        pts = g.node("GeometryNodeRemoveAttribute", Geometry=pts, Name=name)["Geometry"]
    ins = g.node("GeometryNodeInstanceOnPoints", Points=pts, Instance=inst, Rotation=_attr(g, "nk_rot", "QUATERNION"),
                 Scale=_attr(g, "nk_scale"))["Instances"]
    return pts, ins


def _variation_inputs(g, rot_default=TAU):
    spin = g.input("Random Rotation", "FLOAT", rot_default, min=0.0, max=TAU, subtype="ANGLE", panel="Variation",
                   desc="Random spin about the instance's Z axis, from 0 up to this angle")
    tilt = g.input("Random Tilt", "FLOAT", 0.0, min=0.0, max=1.5708, subtype="ANGLE", panel="Variation",
                   desc="Random lean of the Z axis, up to this angle each way")
    smin = g.input("Scale Min", "FLOAT", 1.0, min=0.0, max=100.0, panel="Variation", desc="Smallest uniform scale")
    smax = g.input("Scale Max", "FLOAT", 1.0, min=0.0, max=100.0, panel="Variation", desc="Largest uniform scale")
    return spin, tilt, smin, smax


# ---- groups --------------------------------------------------------------------------------------------------
@nodegroup("NK Scatter On Surface", tags=["scatter", "instances", "distribute", "poisson", "surface"],
           use="rocks on terrain, grass tufts, trees on hills, mushrooms, debris, flowers in a lawn, studs on a surface")
def scatter_on_surface():
    """Scatter instances over a mesh at a density, optionally Poisson-spaced, masked by an attribute or slope."""
    g = Graph("NK Scatter On Surface", description="Instances on the faces of a mesh: Density per square metre, or "
                                                   "a Poisson-disk set with no two points closer than Min Distance; "
                                                   "kept only where the Mask Attribute (a 0..1 weight, scaling the "
                                                   "density) allows and where the surface is flatter than Slope Max. "
                                                   "Each instance is spun, aligned between world up and the surface "
                                                   "normal, tilted and scaled at random")
    mesh = g.input("Surface", "GEOMETRY", desc="Mesh to scatter on")
    inst = g.input("Instance", "GEOMETRY", desc="What to place at each point (its origin on the surface, +Z up)")
    dens = g.input("Density", "FLOAT", 10.0, min=0.0, max=100000.0, panel="Distribution",
                   desc="Points per square metre (the maximum, when Poisson)")
    mind = g.input("Min Distance", "FLOAT", 0.0, min=0.0, max=1000.0, subtype="DISTANCE", panel="Distribution",
                   desc="0 for plain random points; above 0 no two points closer than this (Poisson disk)")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, panel="Distribution", desc="Random seed")
    mask = g.input("Mask Attribute", "STRING", "", panel="Mask",
                   desc="Name of a FLOAT point/face attribute on the surface used as a 0..1 density weight (empty: "
                        "everywhere)")
    slope = g.input("Slope Max", "FLOAT", math.pi, min=0.0, max=math.pi, subtype="ANGLE", panel="Mask",
                    desc="Only faces whose normal is within this angle of world up (90 degrees: no overhangs)")
    align = g.input("Align", "FLOAT", 1.0, min=0.0, max=1.0, subtype="FACTOR", panel="Variation",
                    desc="0 instances stand upright (world Z), 1 they follow the surface normal")
    spin, tilt, smin, smax = _variation_inputs(g)
    with g.frame("Where: faces flatter than Slope Max; density weight from the mask attribute"):
        nz = g.separate(g.node("GeometryNodeInputNormal")["Normal"])["Z"]
        flat = _cmp(g, "GREATER_EQUAL", nz, g.math("SUBTRACT", g.math("COSINE", slope), 1e-5))
        na = g.node("GeometryNodeInputNamedAttribute", props={"data_type": "FLOAT"}, Name=mask)
        weight = g.math("MINIMUM", g.math("MAXIMUM", _switch(g, "FLOAT", na["Exists"], 1.0, na["Attribute"]), 0.0),
                        1.0)
    with g.frame("Distribute: random, or Poisson disk when Min Distance > 0"):
        pts = _distribute(g, mesh, flat, dens, weight, mind, seed)
    with g.frame("Orientation, scale and nk_rand per point; instance"):
        rot = _orient(g, _attr(g, "nk_normal", "FLOAT_VECTOR"), align, spin, tilt, seed, 1)
        out_pts, ins = _instance(g, pts, inst, rot, _rand(g, smin, smax, seed, 5), _rand(g, 0.0, 1.0, seed, 6))
    with g.frame("Empty distribution (Density 0, all masked): output nothing, evaluate nothing"):
        ins, pts = _if_any(g, pts, ins, out_pts)
    g.output("Instances", "GEOMETRY", ins, desc="One instance per point (not realized)")
    g.output("Points", "GEOMETRY", pts, desc="The points, with nk_rot, nk_scale and nk_rand")
    return g.finish()


@nodegroup("NK Scatter Along Curve", tags=["scatter", "instances", "curve", "path", "spacing"],
           use="fence posts, street lamps, avenue trees, bollards, rail sleepers, stepping stones, bunting flags")
def scatter_along_curve():
    """Instances every Spacing along a curve (one or both sides), following the curve frame or upright."""
    samples = curve_samples()
    g = Graph("NK Scatter Along Curve", description="Instances at NK Curve Samples points: every Spacing along a "
                                                    "path curve, at Offset or on both sides, jittered along and "
                                                    "across. Each instance follows the level curve frame (+X along "
                                                    "the curve, +Y left) or keeps world orientation, then gets a "
                                                    "random spin and scale")
    curve = g.input("Curve", "GEOMETRY", desc="The path curve")
    inst = g.input("Instance", "GEOMETRY", desc="What to place at each point (+X along the curve when following it)")
    spacing = g.input("Spacing", "FLOAT", 2.0, min=0.01, max=1000.0, subtype="DISTANCE", panel="Placement",
                      desc="Arc length between instances")
    both = g.input("Both Sides", "BOOL", False, panel="Placement", desc="Two rows, at +Offset and -Offset")
    off = g.input("Offset", "FLOAT", 0.0, min=-1000.0, max=1000.0, subtype="DISTANCE", panel="Placement",
                  desc="Lateral offset, positive to the left of travel")
    h = g.input("Height", "FLOAT", 0.0, min=-1000.0, max=1000.0, subtype="DISTANCE", panel="Placement",
                desc="Height above the curve")
    follow = g.input("Follow Curve", "BOOL", True, panel="Placement",
                     desc="Rotate instances with the curve frame (off: world orientation)")
    jit = g.input("Jitter", "FLOAT", 0.0, min=0.0, max=1.0, subtype="FACTOR", panel="Variation",
                  desc="Random shift along the curve, as a fraction of Spacing")
    sjit = g.input("Side Jitter", "FLOAT", 0.0, min=0.0, max=100.0, subtype="DISTANCE", panel="Variation",
                   desc="Random lateral shift, up to this distance either way")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, panel="Variation", desc="Random seed")
    spin, tilt, smin, smax = _variation_inputs(g, rot_default=0.0)
    with g.frame("Sample points along the curve"):
        sp = g.group(samples, Curve=curve, Spacing=spacing, Offset=off, Height=h, Jitter=jit, Seed=seed,
                     **{"Both Sides": both, "Side Jitter": sjit})
    with g.frame("Frame (or world), then random spin and tilt; scale; instance"):
        base = _switch(g, "ROTATION", follow, None, sp["Rotation"])
        idx = g.node("GeometryNodeInputIndex")["Index"]
        nt = g.math("MULTIPLY", tilt, -1.0)
        jitter_rot = g.node("FunctionNodeEulerToRotation", Euler=g.combine(
            _rand(g, nt, tilt, seed, 11, idx), _rand(g, nt, tilt, seed, 12, idx), _rand(g, 0.0, spin, seed, 13, idx)))
        rot = g.node("FunctionNodeRotateRotation", props={"rotation_space": "LOCAL"}, Rotation=base,
                     **{"Rotate By": jitter_rot["Rotation"]})["Rotation"]
        pts, ins = _instance(g, sp["Points"], inst, rot, _rand(g, smin, smax, seed, 14, idx),
                             _attr(g, "nk_rand"), drop=())
    g.output("Instances", "GEOMETRY", ins, desc="One instance per sample (not realized)")
    g.output("Points", "GEOMETRY", pts, desc="The sample points with nk_s, nk_d, nk_side, nk_rot, nk_scale, nk_rand")
    return g.finish()


@nodegroup("NK Clumps", tags=["scatter", "instances", "clusters", "clumps", "surface"],
           use="flower clumps, stone piles, mushroom rings, tufts of grass, crowds in groups, bushes in a meadow")
def clumps():
    """Scatter clump centres on a surface, then a random number of members around each within a radius."""
    g = Graph("NK Clumps", description="Two-level scatter: clump centres on the surface (density, optionally "
                                       "Poisson-spaced), then Members Min..Max members per clump spread over a "
                                       "disc of Clump Radius in the surface's tangent plane (Concentration packs "
                                       "them to the middle) and snapped back onto the surface. Members shrink "
                                       "towards the rim by Falloff. Writes nk_clump, nk_dist, nk_rand, nk_scale, "
                                       "nk_rot")
    mesh = g.input("Surface", "GEOMETRY", desc="Mesh to scatter on")
    inst = g.input("Instance", "GEOMETRY", desc="What to place at each member point")
    dens = g.input("Clump Density", "FLOAT", 0.5, min=0.0, max=10000.0, panel="Clumps",
                   desc="Clump centres per square metre")
    mind = g.input("Clump Spacing", "FLOAT", 0.0, min=0.0, max=1000.0, subtype="DISTANCE", panel="Clumps",
                   desc="0 random centres; above 0 no two centres closer than this (Poisson disk)")
    rad = g.input("Clump Radius", "FLOAT", 0.5, min=0.0, max=1000.0, subtype="DISTANCE", panel="Clumps",
                  desc="Members lie within this distance of their centre")
    nmin = g.input("Members Min", "INT", 3, min=0, max=10000, panel="Clumps", desc="Fewest members per clump")
    nmax = g.input("Members Max", "INT", 9, min=0, max=10000, panel="Clumps", desc="Most members per clump")
    conc = g.input("Concentration", "FLOAT", 0.5, min=0.1, max=4.0, panel="Clumps",
                   desc="Radial exponent: 0.5 even over the disc, higher packs members towards the centre")
    snap = g.input("Snap To Surface", "BOOL", True, panel="Clumps",
                   desc="Move members onto the nearest surface point (needed on curved surfaces)")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, panel="Clumps", desc="Random seed")
    align = g.input("Align", "FLOAT", 0.0, min=0.0, max=1.0, subtype="FACTOR", panel="Variation",
                    desc="0 members stand upright, 1 they follow the surface normal at the clump centre")
    fall = g.input("Falloff", "FLOAT", 0.4, min=0.0, max=1.0, subtype="FACTOR", panel="Variation",
                   desc="How much smaller members are at the rim than at the centre")
    spin, tilt, smin, smax = _variation_inputs(g)
    with g.frame("Clump centres on the surface"):
        centres = _distribute(g, mesh, True, dens, 1.0, mind, seed)
        cidx = g.node("GeometryNodeInputIndex")["Index"]
        centres = _store(g, centres, "nk_clump", cidx, "INT")
        raw_centres = centres
    with g.frame("Members: duplicate each centre a random number of times"):
        count = _rand(g, nmin, g.math("MAXIMUM", nmin, nmax), seed, 1, cidx, "INT")
        dup = g.node("GeometryNodeDuplicateElements", props={"domain": "POINT"}, Geometry=centres, Amount=count)
        ident = g.math("MULTIPLY_ADD", _attr(g, "nk_clump", "INT"), 65536.0, dup["Duplicate Index"], label="member id")
        mem = _store(g, dup["Geometry"], "nk_id", ident, "INT")
    with g.frame("Spread over the clump disc in the tangent plane at the centre, then snap onto the surface"):
        mid_ = _attr(g, "nk_id", "INT")
        u = g.math("POWER", _rand(g, 0.0, 1.0, seed, 2, mid_), conc, label="dist / radius")
        ang = _rand(g, 0.0, TAU, seed, 3, mid_)
        local = g.combine(g.math("MULTIPLY", g.math("COSINE", ang), g.math("MULTIPLY", u, rad)),
                          g.math("MULTIPLY", g.math("SINE", ang), g.math("MULTIPLY", u, rad)), 0.0)
        off = g.node("FunctionNodeRotateVector", Vector=local, Rotation=_attr(g, "nk_rot", "QUATERNION"))["Vector"]
        mem = _store(g, mem, "nk_dist", u)
        mem = g.node("GeometryNodeSetPosition", Geometry=mem, Offset=off)["Geometry"]
        prox = g.node("GeometryNodeProximity", props={"target_element": "FACES"}, Geometry=mesh,
                      **{"Sample Position": g.node("GeometryNodeInputPosition")["Position"]})
        mem = g.node("GeometryNodeSetPosition", Geometry=mem, Selection=snap, Position=prox["Position"])["Geometry"]
    with g.frame("Orientation, scale shrinking towards the rim, nk_rand; instance"):
        rot = _orient(g, _attr(g, "nk_normal", "FLOAT_VECTOR"), align, spin, tilt, seed, 4, mid_)
        sc = g.math("MULTIPLY", _rand(g, smin, smax, seed, 7, mid_),
                    g.math("SUBTRACT", 1.0, g.math("MULTIPLY", fall, _attr(g, "nk_dist"))))
        pts, ins = _instance(g, mem, inst, rot, sc, _rand(g, 0.0, 1.0, seed, 8, mid_), drop=("nk_normal", "nk_id"))
        centres = g.node("GeometryNodeRemoveAttribute", Geometry=centres, Name="nk_normal")["Geometry"]
    with g.frame("No clump centres (density 0, empty surface): output nothing, evaluate nothing"):
        ins, pts, centres = _if_any(g, raw_centres, ins, pts, centres)
    g.output("Instances", "GEOMETRY", ins, desc="One instance per member (not realized)")
    g.output("Points", "GEOMETRY", pts, desc="Member points with nk_clump, nk_dist, nk_rot, nk_scale, nk_rand")
    g.output("Centres", "GEOMETRY", centres, desc="Clump centre points with nk_clump (their index)")
    return g.finish()


@nodegroup("NK Facade Frame", tags=["placement", "building", "facade", "wall", "points", "frame"],
           use="windows, doors, shutters, signs, balconies, wall lamps and drainpipes on any building mass; "
               "posters on kiosks, panels on crates and cabinets")
def facade_frame():
    """One point per wall face of a mesh, at the centre of the face's rectangle, with its size and an outward frame.

    A face is a wall when its normal is within Max Tilt of horizontal. The frame (nk_rot) has +Y out of the wall
    (the horizontal part of the face normal), +Z world up and +X = Y x Z along the wall, so anything modelled
    with its front facing +Y and its base on Z = 0 lands flat on the wall. nk_size = (width along X, 0, height
    along Z) is the extent of the face's corners in that frame and the point sits at the centre of that
    rectangle. nk_face is the face index; the mesh's point and face attributes carry over (face-averaged).
    """
    g = Graph("NK Facade Frame", description=" ".join(facade_frame.__doc__.strip().split("\n\n")[0].split()))
    mesh = g.input("Mesh", "GEOMETRY", desc="Building mass: boxes, extruded footprints, any mesh with walls")
    sel = g.input("Selection", "BOOL", True, hide_value=True, desc="Which faces may become facades (field)")
    tilt = g.input("Max Tilt", "FLOAT", 0.26, min=0.0, max=1.5, subtype="ANGLE",
                   desc="Faces whose normal is within this angle of horizontal count as walls")
    with g.frame("Per face: horizontal outward normal Y, along-wall X = Y x up, and the face centre"):
        nrm = g.node("GeometryNodeInputNormal")["Normal"]
        yh = g.vmath("NORMALIZE", g.vmath("MULTIPLY", nrm, (1.0, 1.0, 0.0)))
        m = _store(g, mesh, "_nk_ff_y", yh, "FLOAT_VECTOR", "FACE")
        m = _store(g, m, "_nk_ff_c", g.node("GeometryNodeInputPosition"), "FLOAT_VECTOR", "FACE")
        nz = g.math("ABSOLUTE", g.separate(nrm)["Z"])
        wall = g.node("FunctionNodeBooleanMath", props={"operation": "AND"}, Boolean=sel, Boolean_001=_cmp(
            g, "LESS_EQUAL", nz, g.math("SINE", tilt)))["Boolean"]
        m = _store(g, m, "_nk_ff_wall", wall, "BOOLEAN", "FACE")
        m = _store(g, m, "nk_face", g.node("GeometryNodeInputIndex"), "INT", "FACE")
    with g.frame("Corner extents along X and Z per face (min and max grouped by face)"):
        y = _attr(g, "_nk_ff_y", "FLOAT_VECTOR")
        x = g.vmath("CROSS_PRODUCT", y, (0.0, 0.0, 1.0))
        rel = g.vmath("SUBTRACT", g.node("GeometryNodeInputPosition"), _attr(g, "_nk_ff_c", "FLOAT_VECTOR"))
        face = g.node("GeometryNodeFaceOfCorner")["Face Index"]
        for name, val in (("x", g.vmath("DOT_PRODUCT", rel, x)["Value"]), ("z", g.separate(rel)["Z"])):
            mm = g.node("GeometryNodeFieldMinAndMax", props={"data_type": "FLOAT", "domain": "CORNER"}, Value=val,
                        **{"Group ID": face})
            m = _store(g, m, f"_nk_ff_{name}0", mm["Min"], "FLOAT", "CORNER")
            m = _store(g, m, f"_nk_ff_{name}1", mm["Max"], "FLOAT", "CORNER")
    with g.frame("A point per wall face at the rectangle's centre; nk_rot and nk_size"):
        pts = g.node("GeometryNodeMeshToPoints", props={"mode": "FACES"}, Mesh=m,
                     Selection=_attr(g, "_nk_ff_wall", "BOOLEAN"))["Points"]
        y = _attr(g, "_nk_ff_y", "FLOAT_VECTOR")
        x = g.vmath("CROSS_PRODUCT", y, (0.0, 0.0, 1.0))
        x0, x1, z0, z1 = (_attr(g, f"_nk_ff_{k}") for k in ("x0", "x1", "z0", "z1"))
        ctr = g.vmath("ADD", g.vmath("ADD", _attr(g, "_nk_ff_c", "FLOAT_VECTOR"), g.vmath(
            "SCALE", x, scale=g.math("MULTIPLY", g.math("ADD", x0, x1), 0.5))), g.combine(
            0.0, 0.0, g.math("MULTIPLY", g.math("ADD", z0, z1), 0.5)))
        pts = g.node("GeometryNodeSetPosition", Geometry=pts, Position=ctr)["Geometry"]
        rot = g.node("FunctionNodeAxesToRotation", props={"primary_axis": "Y", "secondary_axis": "Z"},
                     **{"Primary Axis": y, "Secondary Axis": (0.0, 0.0, 1.0)})["Rotation"]
        pts = _store(g, pts, "nk_rot", rot, "QUATERNION")
        pts = _store(g, pts, "nk_size", g.combine(g.math("SUBTRACT", x1, x0), 0.0, g.math("SUBTRACT", z1, z0)),
                     "FLOAT_VECTOR")
        pts = g.node("GeometryNodeRemoveAttribute", Geometry=pts, Name="_nk_ff_*",
                     **{"Pattern Mode": "Wildcard"})["Geometry"]
        cap = g.node("GeometryNodeCaptureAttribute", props={"domain": "POINT"})
        cap.b.capture_items.new("ROTATION", "Rotation")
        cap.b.capture_items.new("VECTOR", "Size")
        g.connect(pts, cap.i("Geometry"))
        g.connect(_attr(g, "nk_rot", "QUATERNION"), cap.i("Rotation"))
        g.connect(_attr(g, "nk_size", "FLOAT_VECTOR"), cap.i("Size"))
    g.output("Points", "GEOMETRY", cap["Geometry"], desc="One point per wall face, with nk_rot, nk_size, nk_face")
    g.output("Rotation", "ROTATION", cap["Rotation"], desc="Facade frame: +X along the wall, +Y out, +Z up "
                                                           "(field on Points)")
    g.output("Size", "VECTOR", cap["Size"], desc="(width, 0, height) of the wall face (field on Points)")
    return g.finish()

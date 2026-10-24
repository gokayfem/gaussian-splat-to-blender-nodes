"""Small parametric meshes: the building blocks of props and plants.

Conventions: every shape is built at the origin in its own local frame (stated in its description), sized in
metres by its inputs, smooth-shaded where it is meant to be round and flat where it is meant to be sharp. Edge
rounding and chamfers are built at their true size from the inputs, so they never stretch: to vary a box per
point use NK Chamfer Boxes (or instance a shape built at the final size), not instance Scale.

Attributes: NK Blossom marks its centre with nk_part = 1 (petals 0); NK Foliage Mound writes nk_color and
nk_rand per leaf and blossom instance.
"""
import math
from nodekit.graph import Graph
from nodekit.library import nodegroup

TAU = 2.0 * math.pi


# ---- small node idioms (python helpers, not groups) ----------------------------------------------------------
def _join(g, *geos):
    j = g.node("GeometryNodeJoinGeometry")
    for x in reversed(geos):        # the multi-input socket stacks the newest link first
        g.connect(x, j.i("Geometry"))
    return j["Geometry"]


def _xf(g, geo, t=(0, 0, 0), r=(0, 0, 0), s=(1, 1, 1)):
    return g.node("GeometryNodeTransform", Geometry=geo, Translation=t, Rotation=r, Scale=s)["Geometry"]


def _smooth(g, geo, sel=None, on=True):
    n = g.node("GeometryNodeSetShadeSmooth", Mesh=geo, **{"Shade Smooth": on})
    if sel is not None:
        g.connect(sel, n.i("Selection"))
    return n["Mesh"]


def _store(g, geo, name, value, dtype="FLOAT", domain="POINT"):
    return g.node("GeometryNodeStoreNamedAttribute", props={"data_type": dtype, "domain": domain},
                  Geometry=geo, Name=name, Value=value)["Geometry"]


def _attr(g, name, dtype="FLOAT"):
    return g.node("GeometryNodeInputNamedAttribute", props={"data_type": dtype}, Name=name)["Attribute"]


def _rand(g, lo, hi, seed, k, dtype="FLOAT"):
    return g.node("FunctionNodeRandomValue", props={"data_type": dtype}, Min=lo, Max=hi,
                  Seed=g.math("ADD", seed, float(k)))["Value"]


def _cmp(g, op, a, b):
    return g.node("FunctionNodeCompare", props={"data_type": "FLOAT", "operation": op}, A=a, B=b)["Result"]


def _bool(g, op, a, b=None):
    n = g.node("FunctionNodeBooleanMath", props={"operation": op}, Boolean=a)
    if b is not None:
        g.connect(b, n.i("Boolean#1"))
    return n["Boolean"]


def _switch(g, typ, cond, false=None, true=None):
    n = g.node("GeometryNodeSwitch", props={"input_type": typ}, Switch=cond)
    g.connect(false, n.i("False"))
    g.connect(true, n.i("True"))
    return n["Output"]


def _not_cap(g, axis=(0.0, 0.0, 1.0), limit=0.999):
    """Faces whose normal is not (anti)parallel to axis: the sides of a swept tube, not its flat caps."""
    nrm = g.node("GeometryNodeInputNormal")["Normal"]
    return _cmp(g, "LESS_THAN", g.math("ABSOLUTE", g.vmath("DOT_PRODUCT", nrm, axis)["Value"]), limit)


# ---- boxes ---------------------------------------------------------------------------------------------------
@nodegroup("NK Rounded Box", tags=["shape", "box", "bevel", "rounded"],
           use="toy-like crates, cushions, bricks, signboards, furniture, plinths, phone and appliance bodies")
def rounded_box():
    """A box with truly round edges and corners of a fixed radius (a box swept by a sphere), centred at the origin."""
    g = Graph("NK Rounded Box", description="Box of Size with every edge and corner rounded to exactly Radius "
                                            "(the Minkowski sum of a box and a sphere), centred at the origin. "
                                            "Corners are spherified-cube patches; faces are single flat strips. "
                                            "Radius is clamped to just under half the smallest side")
    size = g.input("Size", "VECTOR", (1.0, 1.0, 1.0), min=0.0, max=1000.0, subtype="XYZ",
                   desc="Outer dimensions along X, Y and Z")
    rad = g.input("Radius", "FLOAT", 0.1, min=0.0, max=100.0, subtype="DISTANCE", desc="Edge and corner radius")
    seg = g.input("Segments", "INT", 4, min=1, max=32, desc="Segments around each rounded edge (quarter circle)")
    with g.frame("Cube grid with an even vertex count: each half of each axis becomes one corner patch"):
        nv = g.math("MULTIPLY", g.math("ADD", seg, 1.0), 2.0)
        cube = g.node("GeometryNodeMeshCube", Size=(2.0, 2.0, 2.0),
                      **{"Vertices X": nv, "Vertices Y": nv, "Vertices Z": nv})["Mesh"]
        p = g.node("GeometryNodeInputPosition")["Position"]
        m2 = g.math("MULTIPLY_ADD", seg, 2.0, 1.0, label="2m + 1")
        a = g.vmath("SCALE", g.vmath("SUBTRACT", g.vmath("SCALE", g.vmath("ABSOLUTE", p), scale=m2), (1, 1, 1)),
                    scale=g.math("DIVIDE", 0.5, seg), label="0 at the mid strip, 1 at the face")
        q = g.vmath("MULTIPLY", g.vmath("SIGN", p), a)
    with g.frame("Corner centre +/-(Size/2 - r) plus r times the patch direction"):
        sz = g.separate(size)
        r = g.math("MINIMUM", rad, g.math("MULTIPLY", g.math("MINIMUM", g.math("MINIMUM", sz["X"], sz["Y"]), sz["Z"]),
                                         0.499), label="r (clamped)")
        core = g.vmath("MULTIPLY", g.vmath("SIGN", p), g.vmath("SUBTRACT", g.vmath("SCALE", size, scale=0.5),
                                                                 g.combine(r, r, r)))
        pos = g.vmath("ADD", core, g.vmath("SCALE", g.vmath("NORMALIZE", q), scale=r))
        box = g.node("GeometryNodeSetPosition", Geometry=cube, Position=pos)["Geometry"]
        out = _smooth(g, box)
    g.output("Mesh", "GEOMETRY", out, desc="The rounded box, smooth shaded")
    return g.finish()


@nodegroup("NK Chamfer Box", tags=["shape", "box", "chamfer", "bevel"],
           use="timber beams, wall blocks, stone steps, planks, crates, window frames, low-poly furniture")
def chamfer_box():
    """A box with a flat 45-degree chamfer of fixed width on every edge, centred at the origin."""
    g = Graph("NK Chamfer Box", description="Box of Size with a flat 45-degree chamfer of width Chamfer (measured "
                                            "along each face) on all twelve edges and a triangle at each corner: "
                                            "the convex hull of three boxes, each inset by Chamfer on two axes. "
                                            "The chamfer is built at its true size and never stretches. Flat "
                                            "shaded, centred at the origin")
    size = g.input("Size", "VECTOR", (1.0, 1.0, 1.0), min=0.0, max=1000.0, subtype="XYZ",
                   desc="Outer dimensions along X, Y and Z")
    ch = g.input("Chamfer", "FLOAT", 0.03, min=0.0, max=100.0, subtype="DISTANCE",
                 desc="Chamfer width along each face (clamped to just under half the smallest side)")
    with g.frame("Three boxes, each full size on one axis and inset by 2 x Chamfer on the other two"):
        sz = g.separate(size)
        c2 = g.math("MULTIPLY", g.math("MINIMUM", ch, g.math("MULTIPLY", g.math(
            "MINIMUM", g.math("MINIMUM", sz["X"], sz["Y"]), sz["Z"]), 0.499)), 2.0, label="2c")
        ix, iy, iz = (g.math("SUBTRACT", sz[a], c2) for a in "XYZ")
        boxes = [g.node("GeometryNodeMeshCube", Size=g.combine(*s))["Mesh"]
                 for s in ((sz["X"], iy, iz), (ix, sz["Y"], iz), (ix, iy, sz["Z"]))]
    with g.frame("Their convex hull is the chamfered box"):
        hull = g.node("GeometryNodeConvexHull", Geometry=_join(g, *boxes))["Convex Hull"]
        out = _smooth(g, hull, on=False)
    g.output("Mesh", "GEOMETRY", out, desc="The chamfered box, flat shaded")
    return g.finish()


@nodegroup("NK Chamfer Boxes", tags=["shape", "box", "chamfer", "instances", "points"],
           use="house wall blocks, beams and posts per point, stacked crates, bricks, kerb stones, shelving")
def chamfer_boxes():
    """One chamfered box per point with per-point size and rotation, the chamfer kept at a fixed width."""
    g = Graph("NK Chamfer Boxes", description="One chamfered box per point, centred on it, with Size and Rotation "
                                              "fields evaluated per point. The unit box is instanced with the size "
                                              "as scale, realized, then every corner vertex is rebuilt at Size/2 "
                                              "minus a fixed Chamfer, so thin and fat boxes get the same bevel. "
                                              "Point attributes (nk_color, nk_rand...) carry onto the boxes")
    pts = g.input("Points", "GEOMETRY", desc="One point per box (mesh vertices or a point cloud)")
    sel = g.input("Selection", "BOOL", True, hide_value=True, desc="Which points get a box")
    size = g.input("Size", "VECTOR", (1.0, 1.0, 1.0), min=0.0, max=1000.0, subtype="XYZ",
                   desc="Box dimensions in its local frame (field)")
    rot = g.input("Rotation", "ROTATION", desc="Box rotation (field)")
    ch = g.input("Chamfer", "FLOAT", 0.03, min=0.0, max=100.0, subtype="DISTANCE",
                 desc="Chamfer width (field; clamped to just under half the box's smallest side)")
    with g.frame("Unit chamfered box; each vertex remembers its octant and which axes are inset"):
        cube = g.node("GeometryNodeMeshCube", Size=(1.0, 1.0, 1.0))["Mesh"]
        unit = g.node("GeometryNodeConvexHull", Geometry=_join(
            g, *[_xf(g, cube, s=sc) for sc in ((1.0, 0.8, 0.8), (0.8, 1.0, 0.8), (0.8, 0.8, 1.0))]))["Convex Hull"]
        up = g.node("GeometryNodeInputPosition")["Position"]
        ua = g.separate(g.vmath("ABSOLUTE", up))
        inset = g.combine(*(g.math("LESS_THAN", ua[a], 0.49) for a in "XYZ"))
        unit = _store(g, unit, "_nk_cb_sign", g.vmath("SIGN", up), "FLOAT_VECTOR")
        unit = _store(g, unit, "_nk_cb_in", inset, "FLOAT_VECTOR")
        unit = _smooth(g, unit, on=False)
    with g.frame("Per point: remember centre, size, rotation and clamped chamfer; instance and realize"):
        sp = g.separate(size)
        c = g.math("MINIMUM", ch, g.math("MULTIPLY", g.math("MINIMUM", g.math("MINIMUM", sp["X"], sp["Y"]), sp["Z"]),
                                         0.499))
        p = g.node("GeometryNodeSeparateGeometry", props={"domain": "POINT"}, Geometry=pts, Selection=sel)
        p = _store(g, p["Selection"], "_nk_cb_size", size, "FLOAT_VECTOR")
        p = _store(g, p, "_nk_cb_rot", rot, "QUATERNION")
        p = _store(g, p, "_nk_cb_ch", c)
        p = _store(g, p, "_nk_cb_ctr", g.node("GeometryNodeInputPosition"), "FLOAT_VECTOR")
        inst = g.node("GeometryNodeInstanceOnPoints", Points=p, Instance=unit, Rotation=rot, Scale=size)
        real = g.node("GeometryNodeRealizeInstances", Geometry=inst["Instances"])["Geometry"]
    with g.frame("Rebuild each vertex: centre + rotate(sign * (size/2) - inset * sign * chamfer)"):
        sgn = _attr(g, "_nk_cb_sign", "FLOAT_VECTOR")
        loc = g.vmath("SUBTRACT", g.vmath("MULTIPLY", sgn, g.vmath("SCALE", _attr(g, "_nk_cb_size", "FLOAT_VECTOR"),
                                                                     scale=0.5)),
                      g.vmath("SCALE", g.vmath("MULTIPLY", _attr(g, "_nk_cb_in", "FLOAT_VECTOR"), sgn),
                              scale=_attr(g, "_nk_cb_ch")))
        world = g.vmath("ADD", _attr(g, "_nk_cb_ctr", "FLOAT_VECTOR"), g.node(
            "FunctionNodeRotateVector", Vector=loc, Rotation=_attr(g, "_nk_cb_rot", "QUATERNION"))["Vector"])
        out = g.node("GeometryNodeSetPosition", Geometry=real, Position=world)["Geometry"]
        out = g.node("GeometryNodeRemoveAttribute", Geometry=out, Name="_nk_cb_*",
                     **{"Pattern Mode": "Wildcard"})["Geometry"]
    g.output("Mesh", "GEOMETRY", out, desc="All boxes as one realized mesh")
    return g.finish()


# ---- tubes and turned shapes ---------------------------------------------------------------------------------
@nodegroup("NK Rod", tags=["shape", "rod", "cylinder", "bar", "segment"],
           use="iron bars, railings, posts, poles, branches, pipes, chair legs, sign arms, cables between two points")
def rod():
    """A round bar from Start to End with a given radius."""
    g = Graph("NK Rod", description="Round bar (cylinder) from Start to End with Radius, capped flat. Sides "
                                    "smooth, caps flat. Vertices lie exactly at Radius from the axis")
    a = g.input("Start", "VECTOR", (0.0, 0.0, 0.0), subtype="TRANSLATION", desc="Start point (centre of one cap)")
    b = g.input("End", "VECTOR", (0.0, 0.0, 1.0), subtype="TRANSLATION", desc="End point (centre of the other cap)")
    r = g.input("Radius", "FLOAT", 0.02, min=0.0, max=100.0, subtype="DISTANCE", desc="Bar radius")
    res = g.input("Resolution", "INT", 12, min=3, max=256, desc="Vertices around the bar")
    caps = g.input("Caps", "BOOL", True, desc="Close both ends")
    with g.frame("Sweep a circle along the segment"):
        line = g.node("GeometryNodeCurvePrimitiveLine", Start=a, End=b)["Curve"]
        prof = g.node("GeometryNodeCurvePrimitiveCircle", Resolution=res, Radius=r)["Curve"]
        mesh = g.node("GeometryNodeCurveToMesh", Curve=line, **{"Profile Curve": prof, "Fill Caps": caps})["Mesh"]
    with g.frame("Smooth sides, flat caps"):
        axis = g.vmath("NORMALIZE", g.vmath("SUBTRACT", b, a))
        out = _smooth(g, mesh, _not_cap(g, axis, 0.99))
    g.output("Mesh", "GEOMETRY", out, desc="The rod")
    return g.finish()


@nodegroup("NK Ring", tags=["shape", "torus", "ring", "band", "hoop"],
           use="pot rims, barrel hoops, rings, door knockers, wheels, tyres, halos, life buoys, arches (partial sweep)")
def ring():
    """A torus or flat band lying in the XY plane, with an elliptical-to-square tube and an optional partial sweep."""
    g = Graph("NK Ring", description="Ring in the XY plane around the origin: a tube Tube Width wide (radially) and "
                                     "Tube Height tall swept around Radius. Roundness 1 gives an elliptical tube "
                                     "(a torus when width = height), 0 a square-edged band. Sweep below 360 degrees "
                                     "gives a capped arc starting on +X, running counter-clockwise")
    R = g.input("Radius", "FLOAT", 0.5, min=0.0, max=1000.0, subtype="DISTANCE", desc="Radius of the tube's centre line")
    tw = g.input("Tube Width", "FLOAT", 0.1, min=0.0, max=1000.0, subtype="DISTANCE",
                 desc="Radial thickness of the tube")
    th = g.input("Tube Height", "FLOAT", 0.1, min=0.0, max=1000.0, subtype="DISTANCE",
                 desc="Vertical thickness of the tube (larger than Width for a hoop band)")
    rnd = g.input("Roundness", "FLOAT", 1.0, min=0.0, max=1.0, subtype="FACTOR",
                  desc="1 elliptical tube, 0 rectangular band")
    sweep = g.input("Sweep", "FLOAT", TAU, min=0.0, max=TAU, subtype="ANGLE", desc="How much of the circle to sweep")
    res = g.input("Resolution", "INT", 32, min=3, max=512, panel="Resolution", desc="Segments around the ring")
    tres = g.input("Tube Resolution", "INT", 12, min=3, max=256, panel="Resolution", desc="Segments around the tube")
    with g.frame("Path: full circle, or an open arc when Sweep < 360 degrees"):
        full = _cmp(g, "GREATER_THAN", sweep, TAU - 1e-4)
        circle = g.node("GeometryNodeCurvePrimitiveCircle", Resolution=res, Radius=R)["Curve"]
        arc = g.node("GeometryNodeCurveArc", props={"mode": "RADIUS"}, Resolution=res, Radius=R,
                     **{"Start Angle": 0.0, "Sweep Angle": sweep})["Curve"]
        path = _switch(g, "GEOMETRY", full, arc, circle)
        path = g.node("GeometryNodeSetCurveNormal", Curve=path, Mode="Z Up")["Curve"]
    with g.frame("Profile: superellipse |x|^e + |y|^e, e from Roundness, Width x Height"):
        prof = g.node("GeometryNodeCurvePrimitiveCircle", Resolution=tres, Radius=1.0)["Curve"]
        pp = g.separate(g.node("GeometryNodeInputPosition"))
        e = g.math("MAXIMUM", rnd, 0.04)

        def squash(v, half):
            return g.math("MULTIPLY", g.math("MULTIPLY", g.math("SIGN", v), g.math("POWER", g.math("ABSOLUTE", v), e)),
                          half)
        prof = g.node("GeometryNodeSetPosition", Geometry=prof, Position=g.combine(
            squash(pp["X"], g.math("MULTIPLY", tw, 0.5)), squash(pp["Y"], g.math("MULTIPLY", th, 0.5)), 0.0))
    with g.frame("Sweep, smooth (the two caps of an arc, its last faces, stay flat)"):
        mesh = g.node("GeometryNodeCurveToMesh", Curve=path, **{"Profile Curve": prof["Geometry"],
                                                                "Fill Caps": True})["Mesh"]
        faces = g.node("GeometryNodeAttributeDomainSize", props={"component": "MESH"}, Geometry=mesh)["Face Count"]
        is_cap = _cmp(g, "GREATER_EQUAL", g.node("GeometryNodeInputIndex")["Index"], g.math("SUBTRACT", faces, 2.0))
        out = _smooth(g, mesh, _bool(g, "OR", full, _bool(g, "NOT", is_cap)))
    g.output("Mesh", "GEOMETRY", out, desc="The ring")
    return g.finish()


@nodegroup("NK Profile Revolve", tags=["shape", "lathe", "revolve", "turned", "vessel"],
           use="flower pots, barrels, vases, urns, bottles, columns, lamp posts, bollards, chess pieces, buckets")
def profile_revolve():
    """Lathe a smooth radius profile (five control radii from bottom to top) around Z, optionally hollow."""
    g = Graph("NK Profile Revolve", description="Turned shape around +Z, base at the origin: five control radii "
                                                "at equal steps from 0 to Height, joined by a smooth Catmull-Rom "
                                                "profile (or straight lines), swept by a circle whose size follows "
                                                "the radius. Solid with flat caps, or hollow (a vessel) with a wall "
                                                "of Wall Thickness, an inner floor and a flat rim")
    h = g.input("Height", "FLOAT", 1.0, min=0.0, max=1000.0, subtype="DISTANCE", desc="Total height")
    radii = [g.input(n, "FLOAT", v, min=0.0, max=1000.0, subtype="DISTANCE", panel="Profile", desc=d)
             for n, v, d in (("Radius Bottom", 0.3, "Radius at the base"),
                             ("Radius Lower", 0.4, "Radius at a quarter of the height"),
                             ("Radius Middle", 0.45, "Radius at half the height"),
                             ("Radius Upper", 0.4, "Radius at three quarters of the height"),
                             ("Radius Top", 0.35, "Radius at the top"))]
    smooth = g.input("Smooth Profile", "BOOL", True, panel="Profile",
                     desc="Catmull-Rom through the radii (off: straight segments, e.g. a tapered bucket)")
    wall = g.input("Wall Thickness", "FLOAT", 0.0, min=0.0, max=100.0, subtype="DISTANCE", panel="Vessel",
                   desc="0 for a solid; above 0 a hollow vessel open at the top, with this wall and floor thickness")
    caps = g.input("Cap Top", "BOOL", True, panel="Vessel", desc="Close the top of a solid (ignored when hollow)")
    seg = g.input("Segments", "INT", 32, min=3, max=512, panel="Resolution", desc="Vertices around")
    rings = g.input("Rings", "INT", 6, min=1, max=64, panel="Resolution", desc="Rows per control span (smooth)")
    with g.frame("Vertical spine through the five control points; curve radius = the profile radius"):
        idx = g.node("GeometryNodeInputIndex")["Index"]
        rsw = g.node("GeometryNodeIndexSwitch", props={"data_type": "FLOAT"}, Index=idx)
        for _ in range(3):
            rsw.b.index_switch_items.new()
        for k, r in enumerate(radii):
            g.connect(r, rsw.i(str(k)))
        pts = g.node("GeometryNodePoints", Count=5, Radius=rsw["Output"],
                     Position=g.combine(0.0, 0.0, g.math("MULTIPLY", g.math("DIVIDE", idx, 4.0), h)))["Points"]
        spine = g.node("GeometryNodePointsToCurves", Points=pts)["Curves"]
        cr = g.node("GeometryNodeCurveSplineType", props={"spline_type": "CATMULL_ROM"}, Curve=spine)["Curve"]
        cr = g.node("GeometryNodeSetSplineResolution", Curve=cr, Resolution=rings)["Curve"]
        spine = _switch(g, "GEOMETRY", smooth, spine, cr)
        spine = g.node("GeometryNodeSetCurveNormal", Curve=spine, Mode="Z Up")["Curve"]
        circle = g.node("GeometryNodeCurvePrimitiveCircle", Resolution=seg, Radius=1.0)["Curve"]
        radius = g.node("GeometryNodeInputRadius")["Radius"]
    with g.frame("Outer surface: circle scaled by the radius; caps when solid"):
        hollow = _cmp(g, "GREATER_THAN", wall, 0.0)
        outer = g.node("GeometryNodeCurveToMesh", Curve=spine, Scale=radius,
                       **{"Profile Curve": circle, "Fill Caps": _bool(g, "NOT", hollow)})["Mesh"]
        top_off = _bool(g, "AND", _bool(g, "NOT", hollow), _bool(g, "NOT", caps))
        is_top = _cmp(g, "GREATER_THAN", g.separate(g.node("GeometryNodeInputNormal")["Normal"])["Z"], 0.999)
        outer = g.node("GeometryNodeDeleteGeometry", props={"domain": "FACE"}, Geometry=outer,
                       Selection=_bool(g, "AND", top_off, is_top))["Geometry"]
        outer = _smooth(g, outer, _not_cap(g))
    with g.frame("Vessel: inner wall from Wall Thickness up (flipped), base disc, inner floor, flat rim"):
        t = g.math("MINIMUM", wall, g.math("MULTIPLY", h, 0.9))
        inner_sp = g.node("GeometryNodeTrimCurve", props={"mode": "LENGTH"}, Curve=spine, Start=t,
                          End=g.math("ADD", h, 1.0))["Curve"]
        inner = g.node("GeometryNodeCurveToMesh", Curve=inner_sp, Scale=g.math("SUBTRACT", radius, t),
                       **{"Profile Curve": circle})["Mesh"]
        inner = _smooth(g, g.node("GeometryNodeFlipFaces", Mesh=inner)["Mesh"])
        r_floor = g.node("GeometryNodeSampleCurve", props={"mode": "LENGTH", "use_all_curves": True,
                                                           "data_type": "FLOAT"},
                         Curves=spine, Value=radius, Length=t)["Value"]
        disc = g.node("GeometryNodeCurvePrimitiveCircle", Resolution=seg, Radius=1.0)["Curve"]
        base = g.node("GeometryNodeFillCurve", Curve=disc, Mode="N-gons")["Mesh"]
        bottom = _xf(g, g.node("GeometryNodeFlipFaces", Mesh=base)["Mesh"],
                     s=g.combine(radii[0], radii[0], 1.0))
        floor = _xf(g, base, t=g.combine(0.0, 0.0, t),
                    s=g.combine(g.math("SUBTRACT", r_floor, t), g.math("SUBTRACT", r_floor, t), 1.0))
        rim_in = _xf(g, disc, s=g.combine(g.math("SUBTRACT", radii[4], t), g.math("SUBTRACT", radii[4], t), 1.0))
        rim_out = _xf(g, disc, s=g.combine(radii[4], radii[4], 1.0))
        rim = g.node("GeometryNodeFillCurve", Curve=_join(g, rim_out, rim_in), Mode="N-gons")["Mesh"]
        rim = _xf(g, rim, t=g.combine(0.0, 0.0, h))
        vessel = _switch(g, "GEOMETRY", hollow, None, _smooth(g, _join(g, inner, bottom, floor, rim), _bool(
            g, "NOT", _cmp(g, "GREATER_THAN", g.math("ABSOLUTE", g.separate(
                g.node("GeometryNodeInputNormal")["Normal"])["Z"]), 0.999)), on=True))
    g.output("Mesh", "GEOMETRY", _join(g, outer, vessel), desc="The turned shape")
    return g.finish()


# ---- plants ----------------------------------------------------------------------------------------------------
@nodegroup("NK Leaf", tags=["shape", "leaf", "plant", "foliage"],
           use="leaves for shrubs, ivy, hedges, potted plants, trees, salad, laurel wreaths, feathers")
def leaf():
    """One leaf blade: base at the origin, tip along +X, face up (+Z), with a folded midrib and a curl."""
    g = Graph("NK Leaf", description="A single-sided leaf blade, base at the origin, tip on +X, upper side +Z. "
                                     "Half-width w(u) = Width/2 * sin(pi u^a)^0.8 along u = X/Length, widest at "
                                     "Widest At; the two halves fold up along the midrib and the tip curls down")
    ln = g.input("Length", "FLOAT", 0.1, min=0.0, max=100.0, subtype="DISTANCE", desc="Base to tip")
    wd = g.input("Width", "FLOAT", 0.5, min=0.01, max=2.0, subtype="FACTOR", desc="Widest width as a share of Length")
    at = g.input("Widest At", "FLOAT", 0.4, min=0.05, max=0.95, subtype="FACTOR",
                 desc="Where along the leaf it is widest (0 base, 1 tip)")
    fold = g.input("Fold", "FLOAT", 0.3, min=-2.0, max=2.0, desc="Midrib fold: rise of each half per unit width")
    curl = g.input("Curl", "FLOAT", 0.15, min=-2.0, max=2.0, desc="Droop of the tip as a share of Length")
    res = g.input("Resolution", "INT", 8, min=2, max=64, desc="Segments along the leaf (half as many across)")
    with g.frame("Grid in (u, v): u along 0..1, v across -1..1"):
        grid = g.node("GeometryNodeMeshGrid", **{"Size X": 1.0, "Size Y": 2.0, "Vertices X": g.math("ADD", res, 1.0),
                                                 "Vertices Y": g.math("ADD", g.math("MAXIMUM", g.math(
                                                     "CEIL", g.math("MULTIPLY", res, 0.5)), 2.0), 1.0)})["Mesh"]
        p = g.separate(g.node("GeometryNodeInputPosition"))
        u = g.math("ADD", p["X"], 0.5)
    with g.frame("Blade outline, fold and curl"):
        a = g.math("DIVIDE", -0.6931472, g.math("LOGARITHM", at, math.e), label="exponent: widest at u = Widest At")
        w = g.math("MULTIPLY", g.math("POWER", g.math("MAXIMUM", g.math("SINE", g.math(
            "MULTIPLY", g.math("POWER", u, a), math.pi)), 0.0), 0.8), g.math("MULTIPLY", g.math("MULTIPLY", wd, ln), 0.5),
            label="half width")
        y = g.math("MULTIPLY", p["Y"], w)
        z = g.math("SUBTRACT", g.math("MULTIPLY", g.math("ABSOLUTE", y), fold),
                   g.math("MULTIPLY", g.math("MULTIPLY", u, u), g.math("MULTIPLY", curl, ln)))
        blade = g.node("GeometryNodeSetPosition", Geometry=grid,
                       Position=g.combine(g.math("MULTIPLY", u, ln), y, z))["Geometry"]
        blade = g.node("GeometryNodeMergeByDistance", Geometry=blade, Distance=1e-6)["Geometry"]
    g.output("Mesh", "GEOMETRY", _smooth(g, blade), desc="The leaf blade")
    return g.finish()


@nodegroup("NK Blossom", tags=["shape", "flower", "blossom", "petals", "plant"],
           use="geraniums, daisies, apple blossom, roses (many petals), flower beds, window boxes, garlands")
def blossom():
    """A flower head: rounded petals around a domed centre, opening towards +Z."""
    g = Graph("NK Blossom", description="Flower head at the origin opening towards +Z: Petals rounded petals "
                                        "(flattened ellipsoids) around a domed centre, cupped upwards. The centre "
                                        "carries nk_part = 1 and the petals 0, so one material can colour both")
    n = g.input("Petals", "INT", 5, min=1, max=64, desc="Number of petals")
    size = g.input("Size", "FLOAT", 0.06, min=0.0, max=100.0, subtype="DISTANCE", desc="Flower diameter")
    pw = g.input("Petal Width", "FLOAT", 0.6, min=0.05, max=2.0, subtype="FACTOR",
                 desc="Petal width as a share of its length")
    cup = g.input("Cup", "FLOAT", 0.35, min=-1.5, max=1.5, subtype="ANGLE",
                  desc="Petal tilt up from flat (radians): 0 flat daisy, higher a cup")
    centre = g.input("Centre Size", "FLOAT", 0.3, min=0.0, max=1.0, subtype="FACTOR",
                     desc="Centre diameter as a share of the flower diameter (0 none)")
    with g.frame("One petal: a flattened ellipsoid from the centre outwards along +X, tilted up by Cup"):
        plen = g.math("MULTIPLY", size, 0.5)
        sph = g.node("GeometryNodeMeshUVSphere", Segments=10, Rings=5, Radius=0.5)["Mesh"]
        petal = _xf(g, sph, t=(0.45, 0.0, 0.0), s=(1.0, 1.0, 0.18))
        petal = _xf(g, petal, r=g.combine(0.0, g.math("MULTIPLY", cup, -1.0), 0.0),
                    s=g.combine(plen, g.math("MULTIPLY", plen, pw), plen))
    with g.frame("Petals around Z, slightly overlapping; domed centre"):
        line = g.node("GeometryNodePoints", Count=n)["Points"]
        ang = g.math("MULTIPLY", g.math("DIVIDE", g.node("GeometryNodeInputIndex")["Index"], n), TAU)
        ring_ = g.node("GeometryNodeInstanceOnPoints", Points=line, Instance=petal, Rotation=g.combine(0.0, 0.0, ang))
        petals = g.node("GeometryNodeRealizeInstances", Geometry=ring_["Instances"])["Geometry"]
        cr = g.math("MULTIPLY", g.math("MULTIPLY", size, centre), 0.5)
        dot = g.node("GeometryNodeMeshUVSphere", Segments=12, Rings=6, Radius=1.0)["Mesh"]
        dot = _xf(g, dot, t=g.combine(0.0, 0.0, g.math("MULTIPLY", cr, 0.15)),
                  s=g.combine(cr, cr, g.math("MULTIPLY", cr, 0.6)))
        dot = _store(g, dot, "nk_part", 1.0)
        dot = _switch(g, "GEOMETRY", _cmp(g, "GREATER_THAN", centre, 0.0), None, dot)
        head = _smooth(g, _join(g, petals, dot))
    g.output("Mesh", "GEOMETRY", head, desc="The flower head")
    return g.finish()


@nodegroup("NK Foliage Mound", tags=["plant", "foliage", "leaves", "flowers", "bush", "instances"],
           use="shrubs, hedges, potted plants, flower beds, window boxes, ivy mats, topiary, moss cushions")
def foliage_mound():
    """Clothe a mound mesh in leaves and optional blossoms, tinted per instance (nk_color, nk_rand)."""
    lf, bl = leaf(), blossom()
    g = Graph("NK Foliage Mound", description="Covers a mound mesh in NK Leaf instances lying on it (aligned to the "
                                              "surface, tips lifted, random spin and size) and optional NK Blossom "
                                              "heads on faces that look up or out, pushed just above the leaves. "
                                              "Each instance stores nk_color and nk_rand. The mound itself can stay "
                                              "as a darker under-layer that hides gaps")
    mound = g.input("Mound", "GEOMETRY", desc="Mesh to cover; normals pointing outwards (e.g. a squashed icosphere)")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    show = g.input("Show Mound", "BOOL", True, desc="Keep the mound as a darker under-layer")
    ld = g.input("Leaf Density", "FLOAT", 300.0, min=0.0, max=100000.0, panel="Leaves", desc="Leaves per square metre")
    ls = g.input("Leaf Size", "FLOAT", 0.1, min=0.0, max=10.0, subtype="DISTANCE", panel="Leaves", desc="Leaf length")
    lift = g.input("Leaf Lift", "FLOAT", 0.5, min=-1.5, max=1.5, subtype="ANGLE", panel="Leaves",
                   desc="How far leaf tips rise off the surface (radians)")
    lc = g.input("Leaf Color", "COLOR", (0.08, 0.22, 0.04, 1.0), panel="Leaves", desc="Leaf colour (linear)")
    lvar = g.input("Color Variation", "FLOAT", 0.3, min=0.0, max=1.0, subtype="FACTOR", panel="Leaves",
                   desc="Per-leaf brightness and hue spread")
    under = g.input("Underside", "FLOAT", -0.5, min=-1.0, max=1.0, panel="Leaves",
                    desc="No leaves on faces whose normal Z is below this (-1 everywhere)")
    lmat = g.input("Leaf Material", "MATERIAL", panel="Leaves", desc="Material of leaves and mound")
    bd = g.input("Blossom Density", "FLOAT", 0.0, min=0.0, max=100000.0, panel="Blossoms",
                 desc="Blossoms per square metre on faces looking up or out (0 none)")
    bs = g.input("Blossom Size", "FLOAT", 0.06, min=0.0, max=10.0, subtype="DISTANCE", panel="Blossoms",
                 desc="Blossom diameter")
    bp = g.input("Petals", "INT", 5, min=1, max=64, panel="Blossoms", desc="Petals per blossom")
    ca = g.input("Blossom Color A", "COLOR", (0.7, 0.03, 0.02, 1.0), panel="Blossoms", desc="Main blossom colour")
    cb = g.input("Blossom Color B", "COLOR", (0.85, 0.75, 0.7, 1.0), panel="Blossoms", desc="Second blossom colour")
    mixb = g.input("Color B Share", "FLOAT", 0.25, min=0.0, max=1.0, subtype="FACTOR", panel="Blossoms",
                   desc="Share of blossoms in colour B")
    bmat = g.input("Blossom Material", "MATERIAL", panel="Blossoms", desc="Material of the blossoms")
    with g.frame("Mound under-layer, darker leaf colour"):
        base = _store(g, mound, "nk_color", g.vmath("SCALE", lc, scale=0.5), "FLOAT_COLOR")
        base = g.node("GeometryNodeSetMaterial", Geometry=_smooth(g, base), Material=lmat)["Geometry"]
        base = _switch(g, "GEOMETRY", show, None, base)
    with g.frame("Leaves on the mound: aligned to it, tip lifted, random spin, size and tint"):
        nz = g.separate(g.node("GeometryNodeInputNormal")["Normal"])["Z"]
        dl = g.node("GeometryNodeDistributePointsOnFaces", Mesh=mound, Density=ld, Seed=seed,
                    Selection=_cmp(g, "GREATER_EQUAL", nz, under))
        tilt = g.node("FunctionNodeEulerToRotation", Euler=g.combine(
            _rand(g, -0.3, 0.3, seed, 1), g.math("SUBTRACT", _rand(g, -0.2, 0.2, seed, 2), lift),
            _rand(g, 0.0, TAU, seed, 3)))["Rotation"]
        lrot = g.node("FunctionNodeRotateRotation", props={"rotation_space": "LOCAL"}, Rotation=dl["Rotation"],
                      **{"Rotate By": tilt})["Rotation"]
        blade = g.group(lf, Length=1.0)
        li = g.node("GeometryNodeInstanceOnPoints", Points=dl["Points"], Instance=blade, Rotation=lrot,
                    Scale=g.math("MULTIPLY", ls, _rand(g, 0.7, 1.3, seed, 4)))["Instances"]
        r = _rand(g, 0.0, 1.0, seed, 5)
        k = g.math("MULTIPLY_ADD", g.math("SUBTRACT", r, 0.5), lvar, 1.0)
        hue = g.combine(g.math("MULTIPLY_ADD", _rand(g, -0.5, 0.5, seed, 6), lvar, 1.0), 1.0, 1.0)
        li = _store(g, li, "nk_color", g.vmath("MULTIPLY", g.vmath("SCALE", lc, scale=k), hue), "FLOAT_COLOR",
                    "INSTANCE")
        li = _store(g, li, "nk_rand", r, "FLOAT", "INSTANCE")
        li = g.node("GeometryNodeSetMaterial", Geometry=li, Material=lmat)["Geometry"]
    with g.frame("Blossoms on faces that look up or out, just above the leaves; colour A or B"):
        db = g.node("GeometryNodeDistributePointsOnFaces", Mesh=mound, Density=bd, Seed=g.math("ADD", seed, 11.0),
                    Selection=_cmp(g, "GREATER_EQUAL", nz, g.math("MAXIMUM", under, -0.2)))
        lifted = g.node("GeometryNodeSetPosition", Geometry=db["Points"],
                        Offset=g.vmath("SCALE", db["Normal"], scale=g.math("MULTIPLY", ls, 0.35)))["Geometry"]
        spin = g.node("FunctionNodeEulerToRotation", Euler=g.combine(
            _rand(g, -0.3, 0.3, seed, 12), _rand(g, -0.3, 0.3, seed, 13), _rand(g, 0.0, TAU, seed, 14)))["Rotation"]
        brot = g.node("FunctionNodeRotateRotation", props={"rotation_space": "LOCAL"}, Rotation=db["Rotation"],
                      **{"Rotate By": spin})["Rotation"]
        head = g.group(bl, Petals=bp, Size=1.0)
        bi = g.node("GeometryNodeInstanceOnPoints", Points=lifted, Instance=head, Rotation=brot,
                    Scale=g.math("MULTIPLY", bs, _rand(g, 0.8, 1.2, seed, 15)))["Instances"]
        rb = _rand(g, 0.0, 1.0, seed, 16)
        col = g.mix(_cmp(g, "LESS_THAN", rb, mixb), ca, cb, data_type="RGBA")["Result"]
        bi = _store(g, bi, "nk_color", g.vmath("SCALE", col, scale=_rand(g, 0.85, 1.1, seed, 17)), "FLOAT_COLOR",
                    "INSTANCE")
        bi = _store(g, bi, "nk_rand", rb, "FLOAT", "INSTANCE")
        bi = g.node("GeometryNodeSetMaterial", Geometry=bi, Material=bmat)["Geometry"]
        bi = _switch(g, "GEOMETRY", _cmp(g, "GREATER_THAN", bd, 0.0), None, bi)
    g.output("Geometry", "GEOMETRY", _join(g, base, li, bi), desc="Mound, leaf and blossom instances")
    return g.finish()


@nodegroup("NK Grass Tuft", tags=["plant", "grass", "tuft", "blades", "meadow"],
           use="grass tufts in meadows and lawns, reeds, sedges, rushes, tussocks at fence posts, weeds in cracks, "
               "hair-like fibre bunches")
def grass_tuft():
    """A tuft of curved grass blades rooted on a small disc, leaning outwards, with a 0..1 root-to-tip attribute.

    Blade i (of n) is an NK Leaf stood up on +Z, rooted at radius Radius sqrt((i + 1/2) / n) and the golden angle
    i x 137.5 degrees (plus jitter), leaning outwards by Spread x U(0.3, 1) and curling over outwards. Its length is
    Height x U(Height Min, 1). The realized mesh stores nk_tip (FLOAT, 0 at the root, 1 at the tip: a colour
    gradient for NK Root Tip Gradient) and nk_rand per blade (a realized attribute wins over an instance's
    nk_rand when the tuft is scattered and realized again).
    """
    lf = leaf()
    g = Graph("NK Grass Tuft", description=" ".join(grass_tuft.__doc__.strip().split("\n\n")[0].split()))
    n = g.input("Blades", "INT", 24, min=1, max=1000, desc="Blades in the tuft")
    h = g.input("Height", "FLOAT", 0.35, min=0.0, max=100.0, subtype="DISTANCE", desc="Tallest blade length")
    hmin = g.input("Height Min", "FLOAT", 0.55, min=0.0, max=1.0, subtype="FACTOR",
                   desc="Shortest blade as a share of Height")
    rad = g.input("Radius", "FLOAT", 0.03, min=0.0, max=100.0, subtype="DISTANCE",
                  desc="Roots spread over a disc of this radius (0: a fan from one point)")
    spread = g.input("Spread", "FLOAT", 0.4, min=0.0, max=1.5, subtype="ANGLE", desc="Largest outward lean")
    width = g.input("Blade Width", "FLOAT", 0.06, min=0.005, max=1.0, subtype="FACTOR", panel="Blade",
                    desc="Blade width as a share of its length")
    curl = g.input("Curl", "FLOAT", 0.4, min=-2.0, max=2.0, panel="Blade",
                   desc="How far the tip arches over, as a share of the length (outwards)")
    fold = g.input("Fold", "FLOAT", 0.4, min=-2.0, max=2.0, panel="Blade", desc="V-fold along the midrib")
    res = g.input("Resolution", "INT", 5, min=2, max=64, panel="Blade", desc="Segments along each blade")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    with g.frame("One blade of length 1 along +X with nk_tip = X (0 root, 1 tip)"):
        blade = g.group(lf, Length=1.0, Width=width, Curl=curl, Fold=fold, Resolution=res,
                        **{"Widest At": 0.2})["Mesh"]
        blade = _store(g, blade, "nk_tip", g.math("MINIMUM", g.math("MAXIMUM", g.separate(
            g.node("GeometryNodeInputPosition"))["X"], 0.0), 1.0))
    with g.frame("Roots on a sunflower disc; lean out along the root's azimuth"):
        pts = g.node("GeometryNodePoints", Count=n)["Points"]
        idx = g.node("GeometryNodeInputIndex")["Index"]

        def rnd(lo, hi, k):
            return g.node("FunctionNodeRandomValue", props={"data_type": "FLOAT"}, Min=lo, Max=hi, ID=idx,
                          Seed=g.math("ADD", seed, float(k)))["Value"]
        phi = g.math("MULTIPLY_ADD", idx, 2.3999632, rnd(-0.4, 0.4, 1), label="golden angle + jitter")
        rho = g.math("MULTIPLY", rad, g.math("SQRT", g.math("DIVIDE", g.math("ADD", idx, 0.5),
                                                             g.math("MAXIMUM", n, 1.0))))
        root = g.combine(g.math("MULTIPLY", rho, g.math("COSINE", phi)), g.math("MULTIPLY", rho, g.math("SINE", phi)))
        pts = g.node("GeometryNodeSetPosition", Geometry=pts, Position=root)["Geometry"]
        tilt = g.math("MULTIPLY", rnd(0.3, 1.0, 2), spread)
        rot = g.node("FunctionNodeEulerToRotation", Euler=g.combine(0.0, g.math("SUBTRACT", tilt, math.pi / 2), phi))
        length = g.math("MULTIPLY", h, rnd(hmin, 1.0, 3))
        pts = _store(g, pts, "nk_rand", rnd(0.0, 1.0, 4))
    with g.frame("Instance a blade per root and realize"):
        ins = g.node("GeometryNodeInstanceOnPoints", Points=pts, Instance=blade, Rotation=rot["Rotation"],
                     Scale=length)["Instances"]
        out = g.node("GeometryNodeRealizeInstances", Geometry=ins)["Geometry"]
    g.output("Mesh", "GEOMETRY", out, desc="The tuft, realized, with nk_tip and nk_rand per blade")
    return g.finish()

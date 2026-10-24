"""Placement along a path curve. Model things in curve space (s along, d to the left, h up), then place them
through these groups; the same graph then follows any curve: bends, hills, spirals.

Curve space: X = s, arc length along the curve; Y = d, lateral offset, positive to the left of travel; Z = h,
height above the curve. The frame is level (its +Z is world up), so walls stay vertical on hills.

Point attributes written by the samplers (read them with Named Attribute, or in shaders after realize):
    nk_s      FLOAT  arc length of the point            nk_d      FLOAT  lateral offset
    nk_index  INT    index along its side               nk_side   INT    +1 left of travel, -1 right
    nk_rand   FLOAT  0..1 per point                     nk_rot    QUATERNION  frame (+X along, +Y left, +Z up)
Parcels add nk_s0 (start), nk_width (arc length), nk_chord (straight frontage) and nk_fan (see NK Curve Parcels).
"""
import math
from nodekit.graph import Graph
from nodekit.library import nodegroup


# ---- small node idioms (python helpers, not groups) ----------------------------------------------------------
def _rand(g, lo, hi, ident, seed, k, dtype="FLOAT"):
    """Random value in [lo, hi] for a stable ID; k decorrelates different random properties."""
    return g.node("FunctionNodeRandomValue", props={"data_type": dtype}, Min=lo, Max=hi, ID=ident,
                  Seed=g.math("ADD", seed, float(k)))["Value"]


def _store(g, geo, name, value, dtype="FLOAT", domain="POINT"):
    return g.node("GeometryNodeStoreNamedAttribute", props={"data_type": dtype, "domain": domain},
                  Geometry=geo, Name=name, Value=value)["Geometry"]


def _attr(g, name, dtype="FLOAT"):
    return g.node("GeometryNodeInputNamedAttribute", props={"data_type": dtype}, Name=name)["Attribute"]


def _fswitch(g, cond, if_false, if_true, dtype="FLOAT"):
    n = g.node("GeometryNodeSwitch", props={"input_type": dtype}, Switch=cond)
    g.connect(if_false, n.i("False"))
    g.connect(if_true, n.i("True"))
    return n["Output"]


def _capture_rotation(g, geo, rot):
    cap = g.node("GeometryNodeCaptureAttribute", props={"domain": "POINT"})
    cap.b.capture_items.new("ROTATION", "Rotation")
    g.connect(geo, cap.i("Geometry"))
    g.connect(rot, cap.i("Rotation"))
    return cap["Geometry"], cap["Rotation"]


@nodegroup("NK Curve Frame", tags=["curve", "path", "placement", "orientation"],
           use="streets, fences, rails, rivers, cables, anything placed along a path")
def curve_frame():
    """Curve-space (s, d, h) to world position and a level orientation on a path curve."""
    g = Graph("NK Curve Frame", description="Curve-space (s, d, h) to world position and orientation on a path "
                                            "curve. s = arc length, d = lateral offset (+left), h = height above "
                                            "the curve. Rotation: +X along the curve, +Y left, +Z up")
    curve = g.input("Curve", "GEOMETRY", desc="The path curve")
    s = g.input("Length", "FLOAT", 0.0, subtype="DISTANCE", desc="Arc length along the curve (field)")
    d = g.input("Offset", "FLOAT", 0.0, subtype="DISTANCE", desc="Lateral offset, positive to the left of travel")
    h = g.input("Height", "FLOAT", 0.0, subtype="DISTANCE", desc="Height above the curve")
    with g.frame("Sample the path at arc length s"):
        sample = g.node("GeometryNodeSampleCurve", props={"mode": "LENGTH", "use_all_curves": True},
                        Curves=curve, Length=s)
    with g.frame("Level frame: tangent flattened, left = up x tangent"):
        tangent = g.vmath("NORMALIZE", g.vmath("MULTIPLY", sample["Tangent"], (1.0, 1.0, 0.0)))
        left = g.vmath("CROSS_PRODUCT", (0.0, 0.0, 1.0), tangent)
        rot = g.node("FunctionNodeAxesToRotation", props={"primary_axis": "X", "secondary_axis": "Z"},
                     **{"Primary Axis": tangent, "Secondary Axis": (0.0, 0.0, 1.0)})
    with g.frame("Offset sideways and up"):
        pos = g.vmath("ADD", g.vmath("ADD", sample["Position"], g.vmath("SCALE", left, scale=d)),
                      g.combine(0.0, 0.0, h))
    g.output("Position", "VECTOR", pos)
    g.output("Rotation", "ROTATION", rot["Rotation"])
    g.output("Tangent", "VECTOR", tangent)
    g.output("Left", "VECTOR", left)
    return g.finish()


@nodegroup("NK Curve Bend", tags=["curve", "path", "deform", "bend"],
           use="roads, kerbs, cobbles, rails, walls, fences, river banks, any flat layout bent onto a path")
def curve_bend():
    """Bend geometry modelled in curve space (X along, Y left, Z up) onto a path curve, vertex by vertex."""
    frame = curve_frame()
    g = Graph("NK Curve Bend", description="Bend geometry modelled in flat curve space (X = arc length, Y = lateral "
                                           "offset to the left, Z = height) onto a path curve, vertex by vertex. "
                                           "Points on Y = 0 land exactly on the curve and keep their spacing; at "
                                           "offset Y the local length scales by 1 - Y*curvature, so the inside of "
                                           "a bend is compressed (and folds over if Y exceeds the bend radius) "
                                           "and the outside stretched. Subdivide long faces along X first")
    geo = g.input("Geometry", "GEOMETRY", desc="Geometry modelled in curve space (X along, Y left, Z up)")
    curve = g.input("Curve", "GEOMETRY", desc="The path curve")
    base = g.input("Height", "FLOAT", 0.0, min=-100.0, max=100.0, subtype="DISTANCE",
                   desc="Extra height added to every vertex")
    extend = g.input("Extend Ends", "BOOL", True,
                     desc="Continue straight along the end tangents for X < 0 or X > curve length (off: clamp)")
    with g.frame("Clamp X to the curve; keep the overshoot to extend straight past the ends"):
        length = g.node("GeometryNodeCurveLength", Curve=curve)["Length"]
        p = g.separate(g.node("GeometryNodeInputPosition"))
        s = g.math("MINIMUM", g.math("MAXIMUM", p["X"], 0.0), length, label="s on the curve")
        over = g.math("MULTIPLY", g.math("SUBTRACT", p["X"], s), extend, label="overshoot")
    with g.frame("Each vertex (s, d, h) to world through NK Curve Frame"):
        f = g.group(frame, Curve=curve, Length=s, Offset=p["Y"], Height=g.math("ADD", p["Z"], base))
        pos = g.vmath("ADD", f["Position"], g.vmath("SCALE", f["Tangent"], scale=over))
        out = g.node("GeometryNodeSetPosition", Geometry=geo, Position=pos)
    g.output("Geometry", "GEOMETRY", out["Geometry"])
    return g.finish()


@nodegroup("NK Curve Samples", tags=["curve", "path", "points", "spacing", "placement"],
           use="lamp posts, fence posts, trees along an avenue, bollards, railway sleepers, footprints")
def curve_samples():
    """Points every Spacing along a curve, on one or both sides, with jitter; each stores s, d and its frame.

    On a closed (cyclic) curve the point at s = L would sit on the point at s = 0, so it is left out. Cyclic is
    read from the first spline.
    """
    frame = curve_frame()
    g = Graph("NK Curve Samples", description="Points every Spacing of arc length along a path curve (floor(L / "
                                              "Spacing) + 1 per side, the first at s = 0; on a closed (cyclic) "
                                              "curve ceil(L / Spacing), since s = L is the seam point s = 0 "
                                              "again), at lateral Offset or "
                                              "on both sides at +/-Offset, jittered along and across. Stores "
                                              "nk_s, nk_d, nk_index, nk_side, nk_rand and nk_rot; Rotation is "
                                              "the level curve frame (+X along, +Y left, +Z up)")
    curve = g.input("Curve", "GEOMETRY", desc="The path curve")
    spacing = g.input("Spacing", "FLOAT", 2.0, min=0.01, max=1000.0, subtype="DISTANCE",
                      desc="Arc length between consecutive points")
    both = g.input("Both Sides", "BOOL", False, desc="Two rows, at +Offset (left) and -Offset (right)")
    off = g.input("Offset", "FLOAT", 0.0, min=-1000.0, max=1000.0, subtype="DISTANCE",
                  desc="Lateral offset from the curve, positive to the left of travel")
    h = g.input("Height", "FLOAT", 0.0, min=-1000.0, max=1000.0, subtype="DISTANCE", desc="Height above the curve")
    jit = g.input("Jitter", "FLOAT", 0.0, min=0.0, max=1.0, subtype="FACTOR", panel="Variation",
                  desc="Random shift along the curve, as a fraction of Spacing (1 = up to half a spacing each way)")
    sjit = g.input("Side Jitter", "FLOAT", 0.0, min=0.0, max=100.0, subtype="DISTANCE", panel="Variation",
                   desc="Random lateral shift, up to this distance either way")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, panel="Variation", desc="Random seed")
    with g.frame("Count: floor(L / Spacing) + 1 per side; ceil(L / Spacing) on a closed curve (no seam duplicate)"):
        length = g.node("GeometryNodeCurveLength", Curve=curve)["Length"]
        sp = g.math("MAXIMUM", spacing, 0.01)
        ratio = g.math("DIVIDE", length, sp)
        cyclic = g.node("GeometryNodeSampleIndex", props={"data_type": "BOOLEAN", "domain": "CURVE"},
                        Geometry=curve, Value=g.node("GeometryNodeInputSplineCyclic"), Index=0)["Value"]
        n_open = g.math("ADD", g.math("FLOOR", g.math("ADD", ratio, 1e-4)), 1.0)
        n_closed = g.math("MAXIMUM", g.math("CEIL", g.math("SUBTRACT", ratio, 1e-4)), 1.0)
        n = _fswitch(g, cyclic, n_open, n_closed)
        sides = _fswitch(g, both, 1.0, 2.0)
        pts = g.node("GeometryNodePoints", Count=g.math("MULTIPLY", n, sides))["Points"]
    with g.frame("Curve-space (s, d) of each point: index along, side, jitter"):
        idx = g.node("GeometryNodeInputIndex")["Index"]
        side_k = g.math("FLOOR", g.math("DIVIDE", idx, n), label="0 left, 1 right")
        i = g.math("SUBTRACT", idx, g.math("MULTIPLY", side_k, n), label="index along")
        sign = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", side_k, 2.0))
        shift = g.math("MULTIPLY", _rand(g, -0.5, 0.5, idx, seed, 1), g.math("MULTIPLY", jit, sp))
        s = g.math("MINIMUM", g.math("MAXIMUM", g.math("MULTIPLY_ADD", i, sp, shift), 0.0), length, label="s")
        d = g.math("MULTIPLY_ADD", sign, off, g.math("MULTIPLY", _rand(g, -1.0, 1.0, idx, seed, 2), sjit), label="d")
        pts = _store(g, pts, "nk_s", s)
        pts = _store(g, pts, "nk_d", d)
        pts = _store(g, pts, "nk_index", i, "INT")
        pts = _store(g, pts, "nk_side", sign, "INT")
        pts = _store(g, pts, "nk_rand", _rand(g, 0.0, 1.0, idx, seed, 3))
    with g.frame("Place through NK Curve Frame; store and capture the frame rotation"):
        f = g.group(frame, Curve=curve, Length=_attr(g, "nk_s"), Offset=_attr(g, "nk_d"), Height=h)
        pts = g.node("GeometryNodeSetPosition", Geometry=pts, Position=f["Position"])["Geometry"]
        pts = _store(g, pts, "nk_rot", f["Rotation"], "QUATERNION")
        pts, rot = _capture_rotation(g, pts, _attr(g, "nk_rot", "QUATERNION"))
    g.output("Points", "GEOMETRY", pts, desc="One point per sample (a point cloud)")
    g.output("Rotation", "ROTATION", rot, desc="Level curve frame at each point (field on Points)")
    return g.finish()


@nodegroup("NK Curve Parcels", tags=["curve", "path", "points", "parcels", "subdivision", "placement"],
           use="house rows along a street, market stalls, fence panels, garden plots, shop fronts, quay sheds")
def curve_parcels():
    """Consecutive random-width parcels along a curve, one point per parcel centre, widths summing to its length."""
    frame = curve_frame()
    g = Graph("NK Curve Parcels", description="Split a path curve into consecutive parcels of random width between "
                                              "Width Min and Max, laid end to end so the widths (arc length) sum "
                                              "exactly to the curve length, on one side or both. One point per "
                                              "parcel at the midpoint of its front chord (the straight line between "
                                              "its two front corners at the offset), so neighbours meet exactly on "
                                              "bends. Stores nk_s0, nk_s, nk_width, nk_chord, nk_fan, nk_d, "
                                              "nk_index, nk_side, nk_rand and nk_rot")
    curve = g.input("Curve", "GEOMETRY", desc="The path curve")
    wmin = g.input("Width Min", "FLOAT", 2.0, min=0.01, max=1000.0, subtype="DISTANCE", panel="Parcels",
                   desc="Narrowest parcel (arc length)")
    wmax = g.input("Width Max", "FLOAT", 4.0, min=0.01, max=1000.0, subtype="DISTANCE", panel="Parcels",
                   desc="Widest parcel (arc length). Widths stay in [Min, Max] whenever the length allows it")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, panel="Parcels", desc="Random seed")
    both = g.input("Both Sides", "BOOL", True, panel="Placement",
                   desc="Parcels on both sides at +/-Offset, with independent widths per side")
    off = g.input("Offset", "FLOAT", 3.0, min=-1000.0, max=1000.0, subtype="DISTANCE", panel="Placement",
                  desc="Lateral offset of the parcel fronts, positive to the left of travel")
    h = g.input("Height", "FLOAT", 0.0, min=-1000.0, max=1000.0, subtype="DISTANCE", panel="Placement",
                desc="Height above the curve")
    depth = g.input("Depth", "FLOAT", 4.0, min=0.0, max=1000.0, subtype="DISTANCE", panel="Placement",
                    desc="Parcel depth away from the curve; only used to measure nk_fan")
    face = g.input("Face Centre", "BOOL", True, panel="Placement",
                   desc="Turn each frame so its +Y points back towards the curve (fronts face the street); "
                        "off: +X along travel, +Y left on both sides")
    with g.frame("Parcel count n: as close to L / mean width as Min and Max allow"):
        length = g.node("GeometryNodeCurveLength", Curve=curve)["Length"]
        lo = g.math("CEIL", g.math("SUBTRACT", g.math("DIVIDE", length, g.math("MAXIMUM", wmax, 0.01)), 1e-4))
        hi = g.math("FLOOR", g.math("ADD", g.math("DIVIDE", length, g.math("MAXIMUM", wmin, 0.01)), 1e-4))
        want = g.math("ROUND", g.math("DIVIDE", length, g.math("MULTIPLY", g.math("ADD", wmin, wmax), 0.5)))
        n = g.math("MAXIMUM", g.math("MAXIMUM", lo, g.math("MINIMUM", hi, want)), 1.0, label="n per side")
        sides = _fswitch(g, both, 1.0, 2.0)
        pts = g.node("GeometryNodePoints", Count=g.math("MULTIPLY", n, sides))["Points"]
        idx = g.node("GeometryNodeInputIndex")["Index"]
        side_k = g.math("FLOOR", g.math("DIVIDE", idx, n), label="side group")
        pts = _store(g, pts, "nk_index", g.math("SUBTRACT", idx, g.math("MULTIPLY", side_k, n)), "INT")
        pts = _store(g, pts, "nk_group", side_k, "INT")
    with g.frame("Widths: mean L/n plus zero-mean random deviations, scaled to stay in [Min, Max]"):
        grp = _attr(g, "nk_group", "INT")
        r = g.math("MULTIPLY", _rand(g, -0.5, 0.5, idx, seed, 1), g.math("SUBTRACT", wmax, wmin))
        avg = g.node("GeometryNodeFieldAverage", props={"data_type": "FLOAT", "domain": "POINT"}, Value=r,
                     **{"Group ID": grp})["Mean"]
        dev = g.math("SUBTRACT", r, avg, label="zero-mean deviation")
        amax = g.node("GeometryNodeFieldMinAndMax", props={"data_type": "FLOAT", "domain": "POINT"},
                      Value=g.math("ABSOLUTE", dev), **{"Group ID": grp})["Max"]
        mean = g.math("DIVIDE", length, n, label="mean width")
        room = g.math("MAXIMUM", g.math("MINIMUM", g.math("SUBTRACT", mean, wmin), g.math("SUBTRACT", wmax, mean)),
                      0.0)
        k = g.math("MINIMUM", g.math("DIVIDE", room, g.math("MAXIMUM", amax, 1e-6)), 1.0)
        pts = _store(g, pts, "nk_width", g.math("MULTIPLY_ADD", dev, k, mean))
    with g.frame("Lay the parcels end to end per side (accumulate)"):
        acc = g.node("GeometryNodeAccumulateField", props={"data_type": "FLOAT", "domain": "POINT"},
                     Value=_attr(g, "nk_width"), **{"Group ID": _attr(g, "nk_group", "INT")})
        side = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", _attr(g, "nk_group", "INT"), 2.0))
        pts = _store(g, pts, "nk_s0", acc["Trailing"])
        pts = _store(g, pts, "nk_s", g.math("MULTIPLY", g.math("ADD", acc["Trailing"], acc["Leading"]), 0.5))
        pts = _store(g, pts, "nk_side", side, "INT")
        pts = _store(g, pts, "nk_d", g.math("MULTIPLY", side, off))
        pts = _store(g, pts, "nk_rand", _rand(g, 0.0, 1.0, idx, seed, 2))
    with g.frame("Front corners on the curve at the offset; their chord gives centre, frontage and frame"):
        s0 = _attr(g, "nk_s0")
        s1 = g.math("ADD", s0, _attr(g, "nk_width"))
        d = _attr(g, "nk_d")
        p0 = g.group(frame, Curve=curve, Length=s0, Offset=d)["Position"]
        p1 = g.group(frame, Curve=curve, Length=s1, Offset=d)["Position"]
        chord = g.vmath("MULTIPLY", g.vmath("SUBTRACT", p1, p0), (1.0, 1.0, 0.0))
        cw = g.vmath("LENGTH", chord)["Value"]
        away = _fswitch(g, g.node("FunctionNodeCompare", props={"data_type": "FLOAT", "operation": "LESS_THAN"},
                                  A=d, B=0.0)["Result"], 1.0, -1.0)
        flip = _fswitch(g, face, 1.0, g.math("MULTIPLY", away, -1.0))
        xdir = g.vmath("SCALE", g.vmath("NORMALIZE", chord), scale=flip)
        rot = g.node("FunctionNodeAxesToRotation", props={"primary_axis": "X", "secondary_axis": "Z"},
                     **{"Primary Axis": xdir, "Secondary Axis": (0.0, 0.0, 1.0)})["Rotation"]
        centre = g.vmath("ADD", g.vmath("SCALE", g.vmath("ADD", p0, p1), scale=0.5), g.combine(0.0, 0.0, h))
    with g.frame("Back corners Depth further out: nk_fan = relative width change per unit depth (> 0 outside a bend)"):
        db = g.math("MULTIPLY_ADD", away, depth, d)
        b0 = g.group(frame, Curve=curve, Length=s0, Offset=db)["Position"]
        b1 = g.group(frame, Curve=curve, Length=s1, Offset=db)["Position"]
        wb = g.vmath("LENGTH", g.vmath("MULTIPLY", g.vmath("SUBTRACT", b1, b0), (1.0, 1.0, 0.0)))["Value"]
        fan = g.math("DIVIDE", g.math("SUBTRACT", g.math("DIVIDE", wb, g.math("MAXIMUM", cw, 1e-4)), 1.0),
                     g.math("MAXIMUM", depth, 1e-4))
        fan = g.math("MULTIPLY", fan, g.math("GREATER_THAN", depth, 1e-4))
    with g.frame("Store the frame, move to the chord centre"):
        pts = _store(g, pts, "nk_chord", cw)
        pts = _store(g, pts, "nk_fan", fan)
        pts = _store(g, pts, "nk_rot", rot, "QUATERNION")
        pts = g.node("GeometryNodeSetPosition", Geometry=pts, Position=centre)["Geometry"]
        pts = g.node("GeometryNodeRemoveAttribute", Geometry=pts, Name="nk_group")["Geometry"]
        pts, rot_f = _capture_rotation(g, pts, _attr(g, "nk_rot", "QUATERNION"))
    g.output("Points", "GEOMETRY", pts, desc="One point per parcel at the centre of its front chord")
    g.output("Rotation", "ROTATION", rot_f, desc="Parcel frame: +X along the front chord, +Z up (field on Points)")
    return g.finish()


@nodegroup("NK Curve Ribbon", tags=["curve", "path", "strip", "mesh", "uv"],
           use="roads, footpaths, rivers, kerb strips, rail beds, garden borders, race tracks")
def curve_ribbon():
    """A flat strip of given width and offset along a curve, UV-mapped by arc length."""
    bend = curve_bend()
    g = Graph("NK Curve Ribbon", description="A flat strip along a path curve between Offset - Width/2 and Offset + "
                                             "Width/2, a row of vertices every Step of arc length, bent onto the "
                                             "curve with NK Curve Bend. UVMap: U = arc length, V = distance from "
                                             "the strip's right edge (both in metres; scale in the shader)")
    curve = g.input("Curve", "GEOMETRY", desc="The path curve")
    width = g.input("Width", "FLOAT", 2.0, min=0.0, max=1000.0, subtype="DISTANCE", desc="Strip width")
    off = g.input("Offset", "FLOAT", 0.0, min=-1000.0, max=1000.0, subtype="DISTANCE",
                  desc="Lateral offset of the strip's centre line, positive to the left of travel")
    h = g.input("Height", "FLOAT", 0.0, min=-1000.0, max=1000.0, subtype="DISTANCE", desc="Height above the curve")
    step = g.input("Step", "FLOAT", 0.25, min=0.01, max=100.0, subtype="DISTANCE", panel="Resolution",
                   desc="Largest arc length between vertex rows (smaller follows tight bends better)")
    across = g.input("Segments Across", "INT", 1, min=1, max=256, panel="Resolution",
                     desc="Faces across the strip (more lets a later displacement or bend crown it)")
    mat = g.input("Material", "MATERIAL", desc="Strip material")
    with g.frame("Flat grid in curve space: X = s from 0 to L, Y across the strip"):
        length = g.node("GeometryNodeCurveLength", Curve=curve)["Length"]
        rows = g.math("ADD", g.math("CEIL", g.math("DIVIDE", length, g.math("MAXIMUM", step, 0.01))), 1.0)
        grid = g.node("GeometryNodeMeshGrid", **{"Size X": length, "Size Y": width, "Vertices X": rows,
                                                 "Vertices Y": g.math("ADD", across, 1.0)})
        flat = g.node("GeometryNodeTransform", Geometry=grid["Mesh"],
                      Translation=g.combine(g.math("MULTIPLY", length, 0.5), off, h))["Geometry"]
    with g.frame("UVMap from curve-space position: U = s, V = from the right edge"):
        p = g.separate(g.node("GeometryNodeInputPosition"))
        v = g.math("SUBTRACT", p["Y"], g.math("SUBTRACT", off, g.math("MULTIPLY", width, 0.5)))
        flat = _store(g, flat, "UVMap", g.combine(p["X"], v, 0.0), "FLOAT2", "CORNER")
    with g.frame("Bend onto the curve, material"):
        bent = g.group(bend, Geometry=flat, Curve=curve, **{"Extend Ends": False})
        out = g.node("GeometryNodeSetMaterial", Geometry=bent, Material=mat)
    g.output("Mesh", "GEOMETRY", out["Geometry"], desc="The strip, faces up")
    return g.finish()


@nodegroup("NK Catenary Point", tags=["curve", "rope", "cable", "catenary", "sag", "hanging"],
           use="bunting ropes, washing lines, power and telegraph cables, chains, garlands, rope bridges, "
               "festoon lights, hammocks")
def catenary_point():
    """A point on a rope hanging between two anchors: the chord point lowered by a catenary (or parabola) sag,
    optionally swung about the chord.

    With chord C = End - Start and u in 0..1, Position = Start + u C + R(Swing) (0, 0, -Sag f(u)), where R rotates
    about the chord and f(0) = f(1) = 0, f(1/2) = 1. Parabola: f = 4u(1 - u). Catenary: f = sinh(h u) sinh(h (1 -
    u)) / sinh^2(h / 2), with h solved (6 Newton steps) from Sag / |C| = (cosh h - 1) / (2 h); exact for level
    anchors, it tends to the parabola for shallow ropes and is deeper-bellied for slack ones. Tangent is dP/du
    normalised. All inputs are fields, so one node places every point of many ropes.
    """
    g = Graph("NK Catenary Point", description=" ".join(catenary_point.__doc__.strip().split("\n\n")[0].split()))
    a = g.input("Start", "VECTOR", (0.0, 0.0, 0.0), subtype="TRANSLATION", desc="Anchor at U = 0 (field)")
    b = g.input("End", "VECTOR", (4.0, 0.0, 0.0), subtype="TRANSLATION", desc="Anchor at U = 1 (field)")
    u = g.input("U", "FLOAT", 0.5, min=0.0, max=1.0, subtype="FACTOR", desc="Position along the rope (field)")
    sag = g.input("Sag", "FLOAT", 0.5, min=0.0, max=1000.0, subtype="DISTANCE",
                  desc="Drop below the chord at mid-rope (field)")
    swing = g.input("Swing", "FLOAT", 0.0, min=-3.1416, max=3.1416, subtype="ANGLE",
                    desc="Rotation of the hanging rope about its chord (field), e.g. NK Pendulum Sway.Angle")
    cat = g.input("Catenary", "BOOL", True, desc="True catenary (hanging chain); off: parabola (uniform load "
                                                 "along the span, a suspension-bridge deck)")
    with g.frame("Chord, sag ratio r = Sag / |chord|"):
        chord = g.vmath("SUBTRACT", b, a)
        span = g.math("MAXIMUM", g.vmath("LENGTH", chord)["Value"], 1e-6)
        r = g.math("DIVIDE", g.math("MAXIMUM", sag, 0.0), span, label="r")
    with g.frame("Solve 2 sinh^2(h/2) = 2 r h by Newton from h0 = min(4r, ln(1 + 16r) + 1) (from above)"):
        h = g.math("MAXIMUM", g.math("MINIMUM", g.math("MULTIPLY", r, 4.0), g.math(
            "ADD", g.math("LOGARITHM", g.math("MULTIPLY_ADD", r, 16.0, 1.0), math.e), 1.0)), 1e-4)
        for _ in range(6):
            sh = g.math("SINH", g.math("MULTIPLY", h, 0.5))
            f = g.math("SUBTRACT", g.math("MULTIPLY", g.math("MULTIPLY", sh, sh), 2.0),
                       g.math("MULTIPLY", g.math("MULTIPLY", r, h), 2.0))
            fp = g.math("SUBTRACT", g.math("SINH", h), g.math("MULTIPLY", r, 2.0))
            h = g.math("MAXIMUM", g.math("SUBTRACT", h, g.math("DIVIDE", f, g.math("MAXIMUM", fp, 1e-6))), 1e-4)
    with g.frame("Shape f(u) and slope f'(u): catenary or parabola"):
        den = g.math("POWER", g.math("SINH", g.math("MULTIPLY", h, 0.5)), 2.0)
        f_c = g.math("DIVIDE", g.math("MULTIPLY", g.math("SINH", g.math("MULTIPLY", h, u)), g.math(
            "SINH", g.math("MULTIPLY", h, g.math("SUBTRACT", 1.0, u)))), den)
        d_c = g.math("DIVIDE", g.math("MULTIPLY", h, g.math("SINH", g.math(
            "MULTIPLY", h, g.math("MULTIPLY_ADD", u, -2.0, 1.0)))), den)
        f_p = g.math("MULTIPLY", g.math("MULTIPLY", u, g.math("SUBTRACT", 1.0, u)), 4.0)
        d_p = g.math("MULTIPLY_ADD", u, -8.0, 4.0)
        shape = _fswitch(g, cat, f_p, f_c)
        slope = _fswitch(g, cat, d_p, d_c)
    with g.frame("Drop below the chord, swung about it; tangent = chord + d(drop)/du"):
        neg = g.math("MULTIPLY", sag, -1.0)
        rot = g.node("FunctionNodeAxisAngleToRotation", Axis=g.vmath("NORMALIZE", chord), Angle=swing)["Rotation"]
        drop = g.node("FunctionNodeRotateVector", Vector=g.combine(0.0, 0.0, g.math("MULTIPLY", shape, neg)),
                      Rotation=rot)["Vector"]
        ddu = g.node("FunctionNodeRotateVector", Vector=g.combine(0.0, 0.0, g.math("MULTIPLY", slope, neg)),
                     Rotation=rot)["Vector"]
        pos = g.vmath("ADD", g.vmath("ADD", a, g.vmath("SCALE", chord, scale=u)), drop)
        tan = g.vmath("NORMALIZE", g.vmath("ADD", chord, ddu))
    g.output("Position", "VECTOR", pos, desc="Point on the rope")
    g.output("Tangent", "VECTOR", tan, desc="Unit tangent along the rope (Start to End)")
    g.output("Swing Rotation", "ROTATION", rot, desc="The swing as a rotation about the chord")
    g.output("Drop", "FLOAT", g.math("MULTIPLY", shape, sag), desc="Distance below the chord at U (Sag f(U))")
    return g.finish()

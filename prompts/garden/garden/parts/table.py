"""Garden part 'table': the round weathered garden table at the world origin.

Top group "Garden Table" = "Garden Table Plank Ring" (40 radial wedge planks with modelled gaps, worn bevels, rounded
rim ends, per-plank seam/height jitter and edge dents) + a flush thin slate centre disc + "Garden Table Supports"
(4 chamfered square legs on an X foot of two crossing chamfered beams with sled-cut ends; no bearers are visible
under the top in close_legs/low_side, so none are modelled; the whole frame scales with the table radius). Fitted numbers come from data/params/table.json
(scripts/analyze_table.py). Shaders are in garden/parts/table_materials.py.

Attributes for the shaders: nk_local (grain space, X along the grain), nk_rand (per piece), nk_part (0 plank,
1 frame), nk_end (1 on end-grain faces), nk_edge (0 plank centre line .. 1 long edge), nk_wear (Weathering).
"""
import math

import bpy
from nodekit.graph import Graph, once

from garden.parts import table_materials
from garden.util import load_params

P = load_params("table")
WOOD = "Garden Table Wood"
SLATE = "Garden Table Slate"
RIM_FIT = P.get("rim_radius", 0.783)


def _p(key, default):
    return P.get(key, default)


def materials():
    table_materials.build(P)


def _join(g, *geos):
    j = g.node("GeometryNodeJoinGeometry")
    for x in reversed(geos):
        g.connect(x, j.i("Geometry"))
    return j["Geometry"]


def _store(g, geo, name, value, dtype="FLOAT", domain="POINT"):
    return g.node("GeometryNodeStoreNamedAttribute", props={"data_type": dtype, "domain": domain},
                  Geometry=geo, Name=name, Value=value)["Geometry"]


def _rand(g, seed, offset, lo=0.0, hi=1.0):
    """Per-element random float (index based) with a seed offset so streams stay independent."""
    s = g.math("ADD", seed, offset)
    return g.node("FunctionNodeRandomValue", props={"data_type": "FLOAT"}, Min=lo, Max=hi, Seed=s)["Value"]


def _end_faces(g, geo, axis_dir):
    """nk_end on faces whose normal is parallel to the grain direction (end grain)."""
    nrm = g.node("GeometryNodeInputNormal")
    d = g.math("ABSOLUTE", g.vmath("DOT_PRODUCT", nrm, axis_dir)["Value"])
    return _store(g, geo, "nk_end", g.map_range(d, 0.6, 0.85, 0.0, 1.0), domain="FACE")


@once
def plank_ring():
    g = Graph("Garden Table Plank Ring",
              description="Radial wedge planks between an inner and an outer radius with straight modelled gaps")
    count = g.input("Plank Count", "INT", int(_p("plank_count", 40)), min=8, max=96,
                    desc="Number of wedge planks around the ring")
    r_in = g.input("Inner Radius", "FLOAT", _p("plank_inner_radius", 0.29), min=0.05, max=1.0, subtype="DISTANCE",
                   desc="Radius where the planks meet the centre disc")
    r_out = g.input("Outer Radius", "FLOAT", RIM_FIT, min=0.2, max=2.0, subtype="DISTANCE",
                    desc="Rim radius of the table top")
    top = g.input("Top Height", "FLOAT", _p("top_height", 0.75), min=0.3, max=1.5, subtype="DISTANCE",
                  desc="Height of the plank top surface above the paving")
    thick = g.input("Thickness", "FLOAT", _p("plank_thickness", 0.035), min=0.01, max=0.1, subtype="DISTANCE",
                    desc="Plank thickness")
    gap = g.input("Gap Width", "FLOAT", _p("gap_width", 0.009), min=0.0, max=0.03, subtype="DISTANCE",
                  desc="Mean width of the straight gap between neighbouring planks")
    phase = g.input("Gap Phase", "FLOAT", math.radians(_p("gap_phase_deg", 6.5)), min=-math.pi, max=math.pi,
                    subtype="ANGLE", desc="Angle of the first gap around Z")
    bevel = g.input("Bevel", "FLOAT", 0.001, min=0.0, max=0.012, subtype="DISTANCE",
                    desc="Depth of the worn rounded bevel on the long top edges and the rim end")
    seam_j = g.input("Seam Jitter", "FLOAT", 0.0008, min=0.0, max=0.01, subtype="ANGLE",
                     desc="Random rotation per plank, making neighbouring seams uneven")
    jitter = g.input("Height Jitter", "FLOAT", 0.0004, min=0.0, max=0.01, subtype="DISTANCE",
                     desc="Random up/down offset per plank")
    damage = g.input("Edge Damage", "FLOAT", 0.003, min=0.0, max=0.01, subtype="DISTANCE",
                     desc="Depth of irregular dents and chips along the worn top edges")
    seed = g.input("Seed", "INT", 0, min=0, max=10000, desc="Random seed for per-plank variation")

    with g.frame("Unit box subdivided along the plank (X) and across it (Y) for bevels and dents"):
        box = g.node("GeometryNodeMeshCube", Size=(1.0, 1.0, 1.0),
                     **{"Vertices X": 32, "Vertices Y": 17, "Vertices Z": 2})
        pos = g.separate(g.node("GeometryNodeInputPosition"))
    with g.frame("Polar wedge: x -> radius, y -> angle minus a constant-width gap, z -> thickness, worn bevels"):
        t = g.math("ADD", pos["X"], 0.5)
        r = g.math("MULTIPLY_ADD", t, g.math("SUBTRACT", r_out, r_in), r_in)
        half = g.math("DIVIDE", math.pi, count)
        half_eff = g.math("SUBTRACT", half, g.math("DIVIDE", g.math("MULTIPLY", gap, 0.5), r))
        lat = g.math("ABSOLUTE", g.math("MULTIPLY", pos["Y"], 2.0))
        phi = g.math("MULTIPLY", g.math("MULTIPLY", pos["Y"], 2.0), half_eff)
        is_top = g.math("GREATER_THAN", pos["Z"], 0.0)
        side = g.math("MULTIPLY", g.math("POWER", lat, 16.0), bevel)
        rim = g.math("MULTIPLY", g.math("POWER", g.map_range(t, 0.97, 1.0, 0.0, 1.0), 2.0), bevel)
        inner = g.math("MULTIPLY", g.map_range(t, 0.03, 0.0, 0.0, 1.0), bevel)
        drop = g.math("MULTIPLY", is_top, g.math("ADD", g.math("MAXIMUM", side, rim), inner))
        z = g.math("SUBTRACT", g.math("SUBTRACT", top, g.math("MULTIPLY", g.math("SUBTRACT", 0.5, pos["Z"]), thick)),
                   drop)
        wedge_pos = g.combine(g.math("MULTIPLY", r, g.math("COSINE", phi)), g.math("MULTIPLY", r, g.math("SINE", phi)), z)
        wedge = g.node("GeometryNodeSetPosition", Geometry=box["Mesh"], Position=wedge_pos)["Geometry"]
    with g.frame("Grain space nk_local, edge factor nk_edge, top flag, and end-grain faces"):
        local = g.combine(r, g.math("MULTIPLY", phi, r), g.math("SUBTRACT", z, top))
        wedge = _store(g, wedge, "nk_local", local, dtype="FLOAT_VECTOR")
        wedge = _store(g, wedge, "nk_edge", lat)
        wedge = _store(g, wedge, "nk_top", is_top)
        fpos = g.node("GeometryNodeInputPosition")
        radial = g.vmath("NORMALIZE", g.vmath("MULTIPLY", fpos, (1.0, 1.0, 0.0)))
        wedge = _end_faces(g, wedge, radial)
    with g.frame("One plank per slot with random seam rotation, height, tone"):
        pts = g.node("GeometryNodePoints", Count=count)
        idx = g.node("GeometryNodeInputIndex")
        ang = g.math("ADD", phase, g.math("MULTIPLY", g.math("ADD", idx, 0.5), g.math("MULTIPLY", half, 2.0)))
        ang = g.math("ADD", ang, g.math("MULTIPLY", g.math("SUBTRACT", _rand(g, seed, 37), 0.5),
                                        g.math("MULTIPLY", seam_j, 2.0)))
        rot = g.node("FunctionNodeEulerToRotation", Euler=g.combine(0.0, 0.0, ang))
        inst = g.node("GeometryNodeInstanceOnPoints", Points=pts["Points"], Instance=wedge, Rotation=rot["Rotation"])
        dz = g.math("MULTIPLY", g.math("SUBTRACT", _rand(g, seed, 11), 0.5), g.math("MULTIPLY", jitter, 2.0))
        inst = g.node("GeometryNodeTranslateInstances", Instances=inst["Instances"],
                      Translation=g.combine(0.0, 0.0, dz))["Instances"]
        inst = _store(g, inst, "nk_rand", _rand(g, seed, 23), domain="INSTANCE")
        planks = g.node("GeometryNodeRealizeInstances", Geometry=inst)["Geometry"]
    with g.frame("Edge damage: irregular dents on the worn top edges, different on every plank"):
        e = g.node("GeometryNodeInputNamedAttribute", props={"data_type": "FLOAT"}, Name="nk_edge")["Attribute"]
        tp = g.node("GeometryNodeInputNamedAttribute", props={"data_type": "FLOAT"}, Name="nk_top")["Attribute"]
        nz = g.node("ShaderNodeTexNoise", Vector=g.node("GeometryNodeInputPosition"), Scale=45.0,
                    Detail=3.0)["Fac"]
        dent = g.math("MULTIPLY", g.map_range(nz, 0.55, 0.75, 0.0, 1.0), g.math("MULTIPLY", damage, -1.0))
        mask = g.math("MULTIPLY", g.math("POWER", e, 16.0), tp)
        planks = g.node("GeometryNodeSetPosition", Geometry=planks,
                        Offset=g.combine(0.0, 0.0, g.math("MULTIPLY", dent, mask)))["Geometry"]
    with g.frame("Soft shading across the worn bevels, crisp at the plank sides and ends"):
        planks = g.node("GeometryNodeSetShadeSmooth", props={"domain": "FACE"}, Geometry=planks,
                        **{"Shade Smooth": True})["Geometry"]
        ang = g.node("GeometryNodeInputMeshEdgeAngle")["Unsigned Angle"]
        planks = g.node("GeometryNodeSetShadeSmooth", props={"domain": "EDGE"}, Geometry=planks,
                        **{"Shade Smooth": g.math("LESS_THAN", ang, 0.5)})["Geometry"]
    g.output("Geometry", "GEOMETRY", planks, desc="Realized plank ring with nk_local, nk_rand, nk_edge, nk_end")
    return g.finish()


def _timber(g, length, width, height, chamfer, taper, step=0.012):
    """A chamfered timber along local X (centred), sled-cut: the top drops by `taper`*height over the last 16 cm.

    Stores nk_local (X along the grain) and nk_end (end-grain faces)."""
    line = g.node("GeometryNodeCurvePrimitiveLine", Start=g.combine(g.math("MULTIPLY", length, -0.5), 0.0, 0.0),
                  End=g.combine(g.math("MULTIPLY", length, 0.5), 0.0, 0.0))
    line = g.node("GeometryNodeResampleCurve", Curve=line["Curve"], Mode="Length", Length=step)
    line = g.node("GeometryNodeSetCurveNormal", Curve=line["Curve"], Mode="Free", Normal=(0.0, 0.0, 1.0))
    quad = g.node("GeometryNodeCurvePrimitiveQuadrilateral", Width=height, Height=width)   # Width -> Z, Height -> Y
    prof = g.node("GeometryNodeFilletCurve", Curve=quad["Curve"], Radius=chamfer, Count=2, Mode="Poly")
    mesh = g.node("GeometryNodeCurveToMesh", Curve=line["Curve"], **{"Profile Curve": prof["Curve"], "Fill Caps": True})
    pos = g.separate(g.node("GeometryNodeInputPosition"))
    half = g.math("MULTIPLY", length, 0.5)
    endness = g.map_range(g.math("ABSOLUTE", pos["X"]), g.math("SUBTRACT", half, 0.16), half, 0.0, 1.0,
                          interp="SMOOTHSTEP")
    up = g.map_range(pos["Z"], g.math("MULTIPLY", height, -0.5), g.math("MULTIPLY", height, 0.5), 0.0, 1.0)
    drop = g.math("MULTIPLY", g.math("MULTIPLY", endness, up), g.math("MULTIPLY", height, taper))
    geo = g.node("GeometryNodeSetPosition", Geometry=mesh["Mesh"],
                 Offset=g.combine(0.0, 0.0, g.math("MULTIPLY", drop, -1.0)))["Geometry"]
    geo = _store(g, geo, "nk_local", g.combine(pos["X"], pos["Y"], pos["Z"]), dtype="FLOAT_VECTOR")
    return _end_faces(g, geo, (1.0, 0.0, 0.0))


def _place(g, geo, z0, height, axis, tilt=0.0):
    return g.node("GeometryNodeTransform", Geometry=geo,
                  Translation=g.combine(0.0, 0.0, g.math("ADD", z0, g.math("MULTIPLY", height, 0.5))),
                  Rotation=g.combine(0.0, tilt, axis))["Geometry"]


@once
def supports():
    g = Graph("Garden Table Supports",
              description="Four chamfered legs standing on an X foot of two crossing sled-cut beams")
    top = g.input("Underside Height", "FLOAT", _p("top_height", 0.75) - _p("plank_thickness", 0.035), min=0.2,
                  max=1.5, subtype="DISTANCE", desc="Height of the plank underside, where the legs end")
    scale = g.input("Spread", "FLOAT", 1.0, min=0.2, max=3.0, subtype="FACTOR",
                    desc="Scales leg radius and beam lengths (the top group sets Radius / fitted radius)")
    axis = g.input("Axis", "FLOAT", math.radians(_p("leg_axis_deg", 30.0)), min=-math.pi, max=math.pi,
                   subtype="ANGLE", desc="Direction of the first foot beam; legs sit on the beams")
    leg_r0 = g.input("Leg Radius", "FLOAT", _p("leg_radius", 0.547), min=0.1, max=1.0, subtype="DISTANCE",
                     desc="Distance of each leg centre from the table axis at the fitted radius")
    leg_s = g.input("Leg Size", "FLOAT", _p("leg_size", 0.063), min=0.02, max=0.2, subtype="DISTANCE",
                    desc="Side of the square leg section")
    foot_l0 = g.input("Foot Half Length", "FLOAT", _p("foot_half_length", 0.68), min=0.2, max=1.2,
                      subtype="DISTANCE", desc="Reach of each foot beam from the centre at the fitted radius")
    foot_w = g.input("Foot Width", "FLOAT", _p("foot_width", 0.085), min=0.02, max=0.2, subtype="DISTANCE",
                     desc="Width of the foot beams")
    foot_h = g.input("Foot Height", "FLOAT", _p("foot_height", 0.09), min=0.02, max=0.2, subtype="DISTANCE",
                     desc="Height of the foot beams")
    chamfer = g.input("Chamfer", "FLOAT", 0.006, min=0.0, max=0.02, subtype="DISTANCE",
                      desc="Radius of the worn rounded arrises on legs and beams")

    leg_r = g.math("MULTIPLY", leg_r0, scale)
    foot_l = g.math("MULTIPLY", foot_l0, scale)
    with g.frame("Four chamfered legs on the beam axes, standing on the foot, up to the plank underside"):
        leg_h = g.math("SUBTRACT", top, foot_h)
        leg = _timber(g, leg_h, leg_s, leg_s, chamfer, 0.0, step=0.1)
        leg = g.node("GeometryNodeTransform", Geometry=leg, Rotation=(0.0, -math.pi / 2, 0.0))["Geometry"]
        circ = g.node("GeometryNodeMeshCircle", Vertices=4, Radius=leg_r)
        circ = g.node("GeometryNodeTransform", Geometry=circ["Mesh"],
                      Translation=g.combine(0.0, 0.0, g.math("ADD", foot_h, g.math("MULTIPLY", leg_h, 0.5))),
                      Rotation=g.combine(0.0, 0.0, axis))["Geometry"]
        rot = g.node("FunctionNodeEulerToRotation", Euler=g.combine(0.0, 0.0, axis))
        legs = g.node("GeometryNodeInstanceOnPoints", Points=circ, Instance=leg, Rotation=rot["Rotation"])
        legs = g.node("GeometryNodeRealizeInstances", Geometry=legs["Instances"])["Geometry"]
    with g.frame("X foot: two crossing sled-cut beams (second 2 mm lower so faces never coincide)"):
        flen = g.math("MULTIPLY", foot_l, 2.0)
        b1 = _place(g, _timber(g, flen, foot_w, foot_h, chamfer, 0.5), 0.0, foot_h, axis)
        h2 = g.math("SUBTRACT", foot_h, 0.002)
        b2 = _place(g, _timber(g, flen, foot_w, h2, chamfer, 0.5), 0.0, h2, g.math("ADD", axis, math.pi / 2))
    with g.frame("Per-piece random tone for the frame timber"):
        geo = _join(g, legs, b1, b2)
        geo = _store(g, geo, "nk_part", 1.0)
        isl = g.node("GeometryNodeInputMeshIsland")
        rnd = g.node("FunctionNodeRandomValue", props={"data_type": "FLOAT"}, Min=0.0, Max=1.0,
                     ID=isl["Island Index"], Seed=7)
        geo = _store(g, geo, "nk_rand", rnd["Value"])
    g.output("Geometry", "GEOMETRY", geo, desc="Legs and foot beams with nk_local, nk_end, nk_part, nk_rand")
    return g.finish()


def build():
    ring, sup = plank_ring(), supports()
    g = Graph("Garden Table", kind="GEOMETRY", modifier=True,
              description="Round weathered garden table: radial wedge planks, flush slate centre disc, legs on an X foot")
    seed = g.input("Seed", "INT", 0, min=0, max=10000, desc="Random seed for plank tone, seams and edge dents")
    radius = g.input("Radius", "FLOAT", RIM_FIT, min=0.3, max=2.0, subtype="DISTANCE",
                     desc="Table top rim radius (fitted 0.783 m); legs and foot scale with it")
    height = g.input("Top Height", "FLOAT", _p("top_height", 0.75), min=0.3, max=1.5, subtype="DISTANCE",
                     desc="Height of the top surface above the paving (fitted 0.75 m)")
    count = g.input("Plank Count", "INT", int(_p("plank_count", 40)), min=8, max=96, desc="Number of radial planks")
    gap = g.input("Gap Width", "FLOAT", _p("gap_width", 0.009), min=0.0, max=0.03, subtype="DISTANCE",
                  desc="Gap between planks (modelled, affects the silhouette)")
    disc_r = g.input("Disc Radius", "FLOAT", _p("disc_radius", 0.286), min=0.05, max=1.0, subtype="DISTANCE",
                     desc="Radius of the dark slate centre disc; planks start just outside it")
    weather = g.input("Weathering", "FLOAT", 0.6, min=0.0, max=1.0, subtype="FACTOR",
                      desc="Silver-grey weathering, pale worn edges, cracks and edge dents (0 = fresh oiled teak)")
    thick = _p("plank_thickness", 0.035)

    with g.frame("Plank ring and supports from the fitted parameters; the frame scales with Radius"):
        r_in = g.math("ADD", g.math("MINIMUM", disc_r, g.math("MULTIPLY", radius, 0.8)), 0.004)
        planks = g.group(ring, **{"Plank Count": count, "Inner Radius": r_in, "Outer Radius": radius,
                                  "Top Height": height, "Gap Width": gap, "Seed": seed,
                                  "Edge Damage": g.math("MULTIPLY", weather, 0.0015)})["Geometry"]
        planks = _store(g, planks, "nk_part", 0.0)
        spread = g.math("DIVIDE", radius, RIM_FIT)
        frame = g.group(sup, **{"Underside Height": g.math("SUBTRACT", height, thick), "Spread": spread})["Geometry"]
        wood = g.node("GeometryNodeSetMaterial", Geometry=_join(g, planks, frame),
                      Material=bpy.data.materials[WOOD])["Geometry"]
        wood = _store(g, wood, "nk_wear", weather)
    with g.frame("Thin slate centre disc, flush with the plank tops"):
        dr = g.math("MINIMUM", disc_r, g.math("MULTIPLY", radius, 0.8))
        disc = g.node("GeometryNodeMeshCylinder", props={"fill_type": "NGON"}, Vertices=128, Radius=dr,
                      Depth=0.012, **{"Side Segments": 1})
        disc = g.node("GeometryNodeTransform", Geometry=disc["Mesh"],
                      Translation=g.combine(0.0, 0.0, g.math("SUBTRACT", height, 0.0068)))["Geometry"]
        disc = g.node("GeometryNodeSetShadeSmooth", Geometry=disc, **{"Shade Smooth": False})["Geometry"]
        disc = g.node("GeometryNodeSetMaterial", Geometry=disc, Material=bpy.data.materials[SLATE])["Geometry"]
        disc = _store(g, disc, "nk_wear", weather)
    g.output("Geometry", "GEOMETRY", _join(g, wood, disc), desc="The table mesh")
    return g.finish()

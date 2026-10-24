"""Garden Structures sub-groups: lattice pot, raised bed, step block, handrail, watering can, pallet, pond grates.

Each group models one object in its own frame (base at the origin, +Z up); the top group "Garden Structures"
places them from data/params/structures.json.
"""
import math

from library.shapes import chamfer_box, chamfer_boxes, grass_tuft, profile_revolve, ring, rod
from nodekit.graph import Graph, once

from garden.parts.structures_detail import debris, trailing_stem, weed
from garden.parts.structures_util import (cmp, cube, index, join, position, rand, set_mat, smooth, store, xf)

TAU = 2.0 * math.pi


def _ring_points(g, n, r, phase=0.0, offset=(0.0, 0.0, 0.0)):
    """n points evenly on a circle of radius r (works for n = 1 or 2, unlike Mesh Circle)."""
    i = index(g)
    a = g.math("ADD", g.math("MULTIPLY", g.math("DIVIDE", i, g.math("MAXIMUM", n, 1)), TAU), phase)
    return g.node("GeometryNodePoints", Count=n, Position=g.vmath("ADD", g.combine(
        g.math("MULTIPLY", g.math("COSINE", a), r), g.math("MULTIPLY", g.math("SINE", a), r), 0.0), offset)["Vector"])[
        "Points"]


def _tufts(g, count, radius, height, seed, z):
    """count small grass tufts on a disc of radius at height z (plant material)."""
    tuft = g.group(grass_tuft(), Blades=9, Height=height, Radius=0.02, Spread=0.5, Seed=seed)["Mesh"]
    tuft = set_mat(g, tuft, "Plant")
    pts = g.node("GeometryNodeDistributePointsOnFaces", props={"distribute_method": "RANDOM"},
                 Mesh=g.node("GeometryNodeMeshCircle", props={"fill_type": "NGON"}, Vertices=24,
                             Radius=radius)["Mesh"],
                 Density=g.math("DIVIDE", count, g.math("MULTIPLY", math.pi, g.math("MULTIPLY", radius, radius))),
                 Seed=seed)
    inst = g.node("GeometryNodeInstanceOnPoints", Points=pts["Points"], Instance=tuft,
                  Rotation=g.combine(0.0, 0.0, rand(g, 0.0, TAU, seed, 5)),
                  Scale=rand(g, 0.6, 1.2, seed, 6))["Instances"]
    return xf(g, inst, t=g.combine(0.0, 0.0, z))


@once
def pot():
    g = Graph("Garden Structures Pot", description="Pale cream planter: a hollow turned body (NK Profile Revolve) "
              "with a diagonal lattice: optional soft displacement (st_relief) plus thin crisp ribs drawn per pixel in the "
              "Ceramic shader from st_local / st_latp / st_band, a rolled rim, soil inside, "
              "a wigwam of bamboo canes with a tie, lumpy soil with clods, seedlings and trailing stems. Base at the origin")
    h = g.input("Height", "FLOAT", 0.445, min=0.05, max=3.0, subtype="DISTANCE", desc="Foot to rim top")
    radii = [g.input(n, "FLOAT", v, min=0.01, max=2.0, subtype="DISTANCE", panel="Profile", desc=d)
             for n, v, d in (("Radius Bottom", 0.17, "Radius at the foot"),
                             ("Radius Lower", 0.198, "Radius at a quarter height"),
                             ("Radius Middle", 0.222, "Radius at half height"),
                             ("Radius Upper", 0.25, "Radius at three quarters height"),
                             ("Radius Top", 0.282, "Radius at the rim"))]
    wall = g.input("Wall", "FLOAT", 0.022, min=0.004, max=0.2, subtype="DISTANCE", desc="Wall thickness")
    depth = g.input("Relief Depth", "FLOAT", 0.006, min=0.0, max=0.05, subtype="DISTANCE",
                    desc="Height of the lattice ridges")
    count = g.input("Relief Count", "INT", 14, min=0, max=64, desc="Lattice diamonds around the pot")
    pitch = g.input("Relief Pitch", "FLOAT", 0.11, min=0.02, max=1.0, subtype="DISTANCE",
                    desc="Vertical size of one lattice diamond")
    lw = g.input("Line Width", "FLOAT", 0.11, min=0.01, max=0.5, subtype="FACTOR",
                 desc="Lattice ridge half-width as a share of one diamond")
    fam2 = g.input("Second Family", "FLOAT", 0.55, min=0.0, max=1.0, subtype="FACTOR",
                   desc="Strength of the second (crossing) set of lattice lines")
    rim_h = g.input("Rim Height", "FLOAT", 0.045, min=0.0, max=0.3, subtype="DISTANCE", desc="Rolled rim band height")
    drop = g.input("Soil Drop", "FLOAT", 0.055, min=0.0, max=1.0, subtype="DISTANCE", desc="Soil below the rim")
    canes = g.input("Canes", "INT", 3, min=0, max=12, desc="Bamboo canes standing in the soil")
    cane_h = g.input("Cane Height", "FLOAT", 0.55, min=0.0, max=3.0, subtype="DISTANCE", desc="Cane length above soil")
    tufts = g.input("Seedlings", "INT", 6, min=0, max=60, desc="Small grass/seedling tufts on the soil")
    trail = g.input("Trailing Stems", "INT", 3, min=0, max=24, desc="Stems arching over the rim and hanging down")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed for canes and seedlings")
    with g.frame("Turned hollow body"):
        body = g.group(profile_revolve(), Height=h, **{"Radius Bottom": radii[0], "Radius Lower": radii[1],
                       "Radius Middle": radii[2], "Radius Upper": radii[3], "Radius Top": radii[4],
                       "Wall Thickness": wall, "Segments": 144, "Rings": 14})["Mesh"]
    with g.frame("Lattice: two families of helical lines u +- v = integer (the second fainter), ridge where either is near"):
        p = g.separate(position(g))
        warp = g.node("ShaderNodeTexNoise", Vector=position(g), Scale=7.0, Detail=2.0)["Fac"]
        u = g.math("ADD", g.math("MULTIPLY", g.math("DIVIDE", g.math("ARCTAN2", p["Y"], p["X"]), TAU), count),
                   g.math("MULTIPLY", g.math("SUBTRACT", warp, 0.5), 0.25))
        v = g.math("DIVIDE", p["Z"], pitch)
        lines = []
        for op, wgt in (("ADD", 1.0), ("SUBTRACT", fam2)):
            f = g.math("FRACT", g.math(op, u, v))
            d = g.math("MINIMUM", f, g.math("SUBTRACT", 1.0, f))
            lines.append(g.map_range(d, 0.0, lw, wgt, 0.0, interp="SMOOTHSTEP")["Result"])
        ridge = g.math("MAXIMUM", *lines)
        nrm = g.node("GeometryNodeInputNormal")["Normal"]
        radial = g.vmath("DOT_PRODUCT", nrm, g.vmath("NORMALIZE", g.combine(p["X"], p["Y"], 0.0)))["Value"]
        band = g.math("MULTIPLY", cmp(g, "GREATER_THAN", radial, 0.3),
                      g.math("MULTIPLY", cmp(g, "LESS_THAN", p["Z"], g.math("SUBTRACT", h, rim_h)),
                             cmp(g, "GREATER_THAN", p["Z"], 0.025)))
        brk = g.node("ShaderNodeTexNoise", Vector=position(g), Scale=11.0, Detail=3.0)["Fac"]
        ridge = g.math("MULTIPLY", g.math("MULTIPLY", ridge, band), g.map_range(brk, 0.3, 0.65, 0.25, 1.0)["Result"])
        body = store(g, body, "st_relief", ridge)
        body = store(g, body, "st_local", position(g), dtype="FLOAT_VECTOR")
        body = store(g, body, "st_latp", g.combine(count, pitch, fam2), dtype="FLOAT_VECTOR")
        body = store(g, body, "st_band", g.math("MULTIPLY", band, g.map_range(brk, 0.25, 0.6, 0.35, 1.0)["Result"]))
        body = store(g, body, "st_h", g.math("DIVIDE", p["Z"], h))
        body = g.node("GeometryNodeSetPosition", Geometry=body,
                      Offset=g.vmath("SCALE", nrm, scale=g.math("MULTIPLY", ridge, depth))["Vector"])["Geometry"]
    with g.frame("Rolled rim band (thick, rounded), lumpy soil inside with clods and litter"):
        rim = g.group(ring(), Radius=g.math("SUBTRACT", radii[4], g.math("MULTIPLY", wall, 0.2)),
                      **{"Tube Width": g.math("ADD", wall, 0.026), "Tube Height": rim_h, "Roundness": 0.9,
                         "Resolution": 128, "Tube Resolution": 12})["Mesh"]
        rim = store(g, xf(g, rim, t=g.combine(0.0, 0.0, g.math("SUBTRACT", h, g.math("MULTIPLY", rim_h, 0.5)))),
                    "st_h", 1.0)
        ceramic = set_mat(g, smooth(g, join(g, body, rim)), "Ceramic")
        soil_r = g.math("SUBTRACT", radii[4], g.math("MULTIPLY", wall, 1.1))
        soil_z = g.math("SUBTRACT", h, drop)
        soil = g.node("GeometryNodeMeshCircle", props={"fill_type": "TRIANGLE_FAN"}, Vertices=48,
                      Radius=soil_r)["Mesh"]
        soil = g.node("GeometryNodeSubdivideMesh", Mesh=soil, Level=3)["Mesh"]
        lump = g.node("ShaderNodeTexNoise", Vector=position(g), Scale=14.0, Detail=3.0)["Fac"]
        soil = g.node("GeometryNodeSetPosition", Geometry=soil, Offset=g.combine(
            0.0, 0.0, g.math("MULTIPLY", g.math("SUBTRACT", lump, 0.5), 0.03)))["Geometry"]
        soil = set_mat(g, smooth(g, xf(g, soil, t=g.combine(0.0, 0.0, soil_z))), "Soil")
        dirt = g.group(debris(), Surface=soil, Clods=180.0, Pebbles=25.0, Litter=40.0, Size=0.012,
                       Seed=g.math("ADD", seed, 40))["Geometry"]
    with g.frame("Bamboo canes as a leaning wigwam with a blue tie; seedlings and trailing stems over the rim"):
        zero = g.value(0.0)
        cpts = _ring_points(g, canes, g.math("MULTIPLY", soil_r, 0.45), phase=rand(g, 0.0, TAU, seed, 30, ident=zero),
                            offset=g.combine(rand(g, -0.04, 0.04, seed, 31, ident=zero),
                                             rand(g, -0.04, 0.04, seed, 32, ident=zero), 0.0))
        cyl = g.node("GeometryNodeMeshCylinder", Vertices=6, Radius=0.005, Depth=cane_h)["Mesh"]
        cyl = set_mat(g, xf(g, cyl, t=g.combine(0.0, 0.0, g.math("MULTIPLY", cane_h, 0.5))), "Cane")
        cp = g.separate(position(g))
        rot = g.node("FunctionNodeAlignRotationToVector", props={"axis": "Z"}, Vector=g.combine(
            g.math("MULTIPLY", cp["X"], -0.6), g.math("MULTIPLY", cp["Y"], -0.6), 1.0))["Rotation"]
        cane_i = g.node("GeometryNodeInstanceOnPoints", Points=cpts, Instance=cyl, Rotation=rot)["Instances"]
        cane_i = xf(g, cane_i, t=g.combine(0.0, 0.0, g.math("SUBTRACT", soil_z, 0.03)))
        tie_z = g.math("ADD", g.math("MULTIPLY", cane_h, 0.4), 0.03)
        tie = g.group(ring(), Radius=g.math("ADD", g.math("MULTIPLY", g.math("MULTIPLY", soil_r, 0.45), g.math(
            "SUBTRACT", 1.0, g.math("MULTIPLY", tie_z, 0.6))), 0.006),
                      **{"Tube Width": 0.004, "Tube Height": 0.004, "Resolution": 24})["Mesh"]
        tie = store(g, tie, "nk_color", (0.05, 0.12, 0.55, 1.0), dtype="FLOAT_COLOR")
        tie = set_mat(g, xf(g, tie, t=g.combine(0.0, 0.0, g.math("ADD", soil_z, g.math("MULTIPLY", cane_h, 0.4)))),
                      "Painted")
        tie = g.node("GeometryNodeSwitch", props={"input_type": "GEOMETRY"},
                     Switch=g.node("FunctionNodeCompare", props={"data_type": "INT", "operation": "GREATER_THAN"},
                                   A=canes, B=1)["Result"], **{"True": tie})["Output"]
        sprouts = _tufts(g, tufts, g.math("MULTIPLY", soil_r, 0.85), 0.09, seed, soil_z)
        tpts = _ring_points(g, trail, g.math("MULTIPLY", soil_r, 0.5), phase=rand(g, 0.0, TAU, seed, 36, ident=zero))
        stem = g.group(trailing_stem(), Reach=g.math("MULTIPLY", soil_r, 0.55), Height=drop,
                       Drop=g.math("MULTIPLY", h, 0.3), Seed=seed)["Geometry"]
        heading = g.math("ARCTAN2", g.separate(position(g))["Y"], g.separate(position(g))["X"])
        trails = g.node("GeometryNodeInstanceOnPoints", Points=tpts, Instance=stem,
                        Rotation=g.combine(0.0, 0.0, g.math("ADD", heading, rand(g, -0.3, 0.3, seed, 33))),
                        Scale=rand(g, 0.8, 1.2, seed, 34))["Instances"]
        trails = xf(g, trails, t=g.combine(0.0, 0.0, soil_z))
    g.output("Geometry", "GEOMETRY", join(g, ceramic, soil, dirt, cane_i, tie, sprouts, trails), desc="The planted pot")
    return g.finish()


@once
def raised_bed():
    g = Graph("Garden Structures Raised Bed", description="Raised timber bed: stacked boards on the four sides "
              "of a rectangle as chamfered boards (per-board nk_rand, slight tilt), corner posts inside, a lumpy soil "
              "surface with clods, pebbles and litter, seedlings and leafy weeds. Centred on the origin, base at z 0, X along the long side")
    size = g.input("Size", "VECTOR", (2.37, 1.43, 0.0), subtype="XYZ", desc="Outer length (X) and width (Y)")
    hgt = g.input("Height", "FLOAT", 0.205, min=0.05, max=1.5, subtype="DISTANCE", desc="Top of boards above base")
    rows = g.input("Boards", "INT", 2, min=1, max=8, desc="Board rows per side")
    t = g.input("Board Thickness", "FLOAT", 0.045, min=0.01, max=0.2, subtype="DISTANCE", desc="Board thickness")
    post = g.input("Post Size", "FLOAT", 0.07, min=0.0, max=0.3, subtype="DISTANCE", desc="Corner post section")
    soil_d = g.input("Soil Depth", "FLOAT", 0.035, min=0.0, max=1.0, subtype="DISTANCE",
                     desc="Soil surface below the board tops")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    sdens = g.input("Seedling Density", "FLOAT", 14.0, min=0.0, max=400.0, desc="Seedlings per square metre of soil")
    weather = g.input("Weathering", "FLOAT", 0.5, min=0.0, max=1.0, subtype="FACTOR",
                      desc="Grey weathering of the timber (st_weather)")
    sz = g.separate(size)
    with g.frame("One point per board: side = i mod 4, row = i div 4"):
        i = index(g)
        side = g.math("FLOORED_MODULO", i, 4.0)
        row = g.math("FLOOR", g.math("DIVIDE", i, 4.0))
        bh = g.math("DIVIDE", hgt, rows)
        long_side = cmp(g, "LESS_THAN", side, 1.5)
        sign = g.math("SUBTRACT", g.math("MULTIPLY", g.math("FLOORED_MODULO", side, 2.0), 2.0), 1.0)
        hx = g.math("MULTIPLY", g.math("SUBTRACT", sz["X"], t), 0.5)
        hy = g.math("MULTIPLY", g.math("SUBTRACT", sz["Y"], t), 0.5)
        px = g.mix(long_side, g.math("MULTIPLY", sign, hx), 0.0)
        py = g.mix(long_side, 0.0, g.math("MULTIPLY", sign, hy))
        pz = g.math("MULTIPLY", g.math("ADD", row, 0.5), bh)
        pts = g.node("GeometryNodePoints", Count=g.math("MULTIPLY", rows, 4.0),
                     Position=g.combine(px, py, pz))["Points"]
        lx = g.mix(long_side, t, sz["X"])
        ly = g.mix(long_side, g.math("SUBTRACT", sz["Y"], g.math("MULTIPLY", t, 2.0)), t)
        scale = g.combine(lx, ly, g.math("MULTIPLY", bh, 0.96))
        pts = store(g, pts, "nk_rand", rand(g, 0.0, 1.0, seed, 3))
    with g.frame("Boards and corner posts"):
        jit = g.combine(rand(g, -0.015, 0.015, seed, 4), 0.0, rand(g, -0.006, 0.006, seed, 5))
        boards = g.group(chamfer_boxes(), Points=pts, Size=scale, Rotation=jit, Chamfer=0.007)["Mesh"]
        boards = set_mat(g, boards, "Timber")
        cx = g.math("SUBTRACT", g.math("MULTIPLY", sz["X"], 0.5), g.math("ADD", t, g.math("MULTIPLY", post, 0.5)))
        cy = g.math("SUBTRACT", g.math("MULTIPLY", sz["Y"], 0.5), g.math("ADD", t, g.math("MULTIPLY", post, 0.5)))
        corner = g.node("GeometryNodeMeshGrid", **{"Size X": g.math("MULTIPLY", cx, 2.0),
                                                   "Size Y": g.math("MULTIPLY", cy, 2.0),
                                                   "Vertices X": 2, "Vertices Y": 2})["Mesh"]
        pmesh = set_mat(g, xf(g, cube(g, g.combine(post, post, hgt)),
                              t=g.combine(0.0, 0.0, g.math("MULTIPLY", hgt, 0.5))), "Timber")
        posts = g.node("GeometryNodeInstanceOnPoints", Points=corner, Instance=pmesh)["Instances"]
        timber = g.node("GeometryNodeRealizeInstances", Geometry=join(g, boards, posts))["Geometry"]
        timber = g.node("GeometryNodeMergeByDistance", Geometry=timber, Distance=0.0001)["Geometry"]
        timber = store(g, timber, "st_weather", weather)
    with g.frame("Soil: a lumpy grid inside the boards, seedlings"):
        ix = g.math("SUBTRACT", sz["X"], g.math("MULTIPLY", t, 2.0))
        iy = g.math("SUBTRACT", sz["Y"], g.math("MULTIPLY", t, 2.0))
        grid = g.node("GeometryNodeMeshGrid", **{"Size X": ix, "Size Y": iy, "Vertices X": 120,
                                                 "Vertices Y": 72})["Mesh"]
        lump = g.node("ShaderNodeTexNoise", Vector=position(g), Scale=3.0, Detail=4.0)["Fac"]
        fine = g.node("ShaderNodeTexNoise", Vector=position(g), Scale=28.0, Detail=2.0)["Fac"]
        grid = g.node("GeometryNodeSetPosition", Geometry=grid, Offset=g.combine(0.0, 0.0, g.math(
            "ADD", g.math("MULTIPLY", g.math("SUBTRACT", lump, 0.5), 0.06),
            g.math("MULTIPLY", g.math("SUBTRACT", fine, 0.5), 0.02))))["Geometry"]
        soil_z = g.math("SUBTRACT", hgt, soil_d)
        soil = set_mat(g, smooth(g, xf(g, grid, t=g.combine(0.0, 0.0, soil_z))), "Soil")
        sp = g.node("GeometryNodeDistributePointsOnFaces", props={"distribute_method": "RANDOM"}, Mesh=soil,
                    Density=sdens, Seed=seed)
        tuft = set_mat(g, g.group(grass_tuft(), Blades=12, Height=0.16, Radius=0.035, Seed=seed)["Mesh"], "Plant")
        sprouts = g.node("GeometryNodeInstanceOnPoints", Points=sp["Points"], Instance=tuft,
                         Rotation=g.combine(0.0, 0.0, rand(g, 0.0, TAU, seed, 8)),
                         Scale=rand(g, 0.5, 1.3, seed, 9))["Instances"]
        dirt = g.group(debris(), Surface=soil, Clods=110.0, Pebbles=10.0, Litter=18.0, Size=0.02,
                       Seed=g.math("ADD", seed, 50))["Geometry"]
        wp = g.node("GeometryNodeDistributePointsOnFaces", props={"distribute_method": "RANDOM"}, Mesh=soil,
                    Density=g.math("MULTIPLY", sdens, 0.15), Seed=g.math("ADD", seed, 51))["Points"]
        weeds = g.node("GeometryNodeInstanceOnPoints", Points=wp,
                       Instance=g.group(weed(), Leaves=7, **{"Leaf Length": 0.07}, Seed=seed)["Mesh"],
                       Rotation=g.combine(0.0, 0.0, rand(g, 0.0, TAU, seed, 52)),
                       Scale=rand(g, 0.6, 1.4, seed, 53))["Instances"]
    g.output("Geometry", "GEOMETRY", join(g, timber, soil, sprouts, dirt, weeds), desc="The bed")
    return g.finish()


@once
def step_block():
    g = Graph("Garden Structures Step", description="One solid step of a flight: a chamfered concrete block from "
              "z 0 to its tread height, front edge on y = 0, running back along -Y. Front and side edges are worn "
              "(noise erosion on a subdivided block); the exposed tread carries clumped grass/weeds, a few leaves, "
              "pebbles and soil spilled from the beds along both side edges; optional pink slab top and brick riser")
    w = g.input("Width", "FLOAT", 0.8, min=0.1, max=10.0, subtype="DISTANCE", desc="Width along X")
    d = g.input("Depth", "FLOAT", 0.4, min=0.05, max=5.0, subtype="DISTANCE", desc="Going back along -Y")
    h = g.input("Height", "FLOAT", 0.1, min=0.01, max=2.0, subtype="DISTANCE", desc="Tread height above base")
    going = g.input("Exposed Going", "FLOAT", 0.35, min=0.0, max=5.0, subtype="DISTANCE",
                    desc="Visible tread depth before the next step (weeds only grow there)")
    brick = g.input("Brick Riser", "BOOL", False, desc="Brick material on the front (+Y) riser")
    pink = g.input("Pink Top", "BOOL", False, desc="Salmon paving slabs on the tread (top landing)")
    wear = g.input("Wear", "FLOAT", 0.014, min=0.0, max=0.1, subtype="DISTANCE", desc="Depth of edge erosion")
    weeds_d = g.input("Weeds", "FLOAT", 30.0, min=0.0, max=500.0, desc="Weed tufts per square metre of exposed tread")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    with g.frame("Block, chamfered and subdivided; edges eroded where near the front/side top edges"):
        box = g.group(chamfer_box(), Size=g.combine(w, d, h), Chamfer=0.03)["Mesh"]
        box = xf(g, box, t=g.combine(0.0, g.math("MULTIPLY", d, -0.5), g.math("MULTIPLY", h, 0.5)))
        box = g.node("GeometryNodeSubdivideMesh", Mesh=box, Level=4)["Mesh"]
        p = g.separate(position(g))
        near_top = g.map_range(g.math("SUBTRACT", h, p["Z"]), 0.0, 0.05, 1.0, 0.0)["Result"]
        near_front = g.map_range(g.math("ABSOLUTE", p["Y"]), 0.0, 0.06, 1.0, 0.0)["Result"]
        near_side = g.map_range(g.math("SUBTRACT", g.math("MULTIPLY", w, 0.5), g.math("ABSOLUTE", p["X"])),
                                0.0, 0.06, 1.0, 0.0)["Result"]
        edge = g.math("MULTIPLY", near_top, g.math("MAXIMUM", near_front, near_side))
        n = g.node("ShaderNodeTexNoise", Vector=position(g), Scale=18.0, Detail=4.0, Roughness=0.7)["Fac"]
        ero = g.math("MULTIPLY", g.math("MULTIPLY", edge, g.map_range(n, 0.3, 0.7, 0.2, 1.0)["Result"]), wear)
        nrm = g.node("GeometryNodeInputNormal")["Normal"]
        box = g.node("GeometryNodeSetPosition", Geometry=box,
                     Offset=g.vmath("SCALE", nrm, scale=g.math("MULTIPLY", ero, -1.0))["Vector"])["Geometry"]
        box = store(g, box, "st_local", position(g), dtype="FLOAT_VECTOR")
        box = g.node("GeometryNodeSetShadeSmooth", props={"domain": "FACE"}, Mesh=box,
                     **{"Shade Smooth": cmp(g, "LESS_THAN", g.math("ABSOLUTE", g.separate(
                         g.node("GeometryNodeInputNormal")["Normal"])["Z"]), 0.98)})["Mesh"]
        box = set_mat(g, box, "Concrete")
        nz = g.separate(g.node("GeometryNodeInputNormal")["Normal"])
        sel = g.node("FunctionNodeBooleanMath", props={"operation": "AND"}, Boolean=cmp(g, "GREATER_THAN", nz["Y"], 0.7))
        g.connect(brick, sel.i("Boolean#1"))
        box = set_mat(g, box, "Brick", sel=sel["Boolean"])
        top = g.node("FunctionNodeBooleanMath", props={"operation": "AND"}, Boolean=cmp(
            g, "GREATER_THAN", g.separate(position(g))["Z"], g.math("SUBTRACT", h, 0.04)))
        g.connect(pink, top.i("Boolean#1"))
        box = set_mat(g, box, "Pink Slab", sel=top["Boolean"])
    with g.frame("Exposed tread: clumped weeds/grass (noise-masked), litter, pebbles"):
        tread = g.node("GeometryNodeMeshGrid", **{"Size X": g.math("SUBTRACT", w, 0.02), "Size Y": going,
                                                  "Vertices X": 2, "Vertices Y": 2})["Mesh"]
        tread = xf(g, tread, t=g.combine(0.0, g.math("MULTIPLY", going, -0.5), g.math("SUBTRACT", h, 0.002)))
        clump = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "4D"}, Vector=position(g), W=seed,
                       Scale=4.0, Detail=2.0)["Fac"]
        wp = g.node("GeometryNodeDistributePointsOnFaces", props={"distribute_method": "RANDOM"}, Mesh=tread,
                    Density=weeds_d, Seed=seed)["Points"]
        keep = cmp(g, "GREATER_THAN", g.math("ADD", clump, g.map_range(near_side, 0.0, 1.0, 0.0, 0.3)["Result"]), 0.55)
        wp = g.node("GeometryNodeDeleteGeometry", props={"domain": "POINT"}, Geometry=wp,
                    Selection=g.node("FunctionNodeBooleanMath", props={"operation": "NOT"}, Boolean=keep)["Boolean"])
        tuft = set_mat(g, g.group(grass_tuft(), Blades=10, Height=0.09, Radius=0.02, Spread=0.8, Seed=seed)["Mesh"],
                       "Plant")
        wd = g.group(weed(), Leaves=7, Seed=seed, **{"Leaf Length": 0.045, "Stem Length": 0.05})["Mesh"]
        mat_ = set_mat(g, g.group(grass_tuft(), Blades=22, Height=0.05, Radius=0.06, Spread=1.0, Seed=seed,
                                  **{"Height Min": 0.4, "Resolution": 3})["Mesh"], "Plant")
        kinds = g.node("GeometryNodeGeometryToInstance")
        for x in (mat_, wd, tuft):
            g.connect(x, kinds.i("Geometry"))
        pickv = g.math("FLOOR", rand(g, 0.0, 2.999, seed, 3))
        weeds = g.node("GeometryNodeInstanceOnPoints", Points=wp["Geometry"], Instance=kinds["Instances"],
                       **{"Pick Instance": True, "Instance Index": pickv},
                       Rotation=g.combine(0.0, 0.0, rand(g, 0.0, TAU, seed, 4)),
                       Scale=rand(g, 0.5, 1.3, seed, 5))["Instances"]
        dirt = g.group(debris(), Surface=tread, Clods=25.0, Pebbles=15.0, Litter=12.0, Size=0.012,
                       Seed=g.math("ADD", seed, 7))["Geometry"]
        strip = g.node("GeometryNodeMeshGrid", **{"Size X": g.math("SUBTRACT", w, 0.02), "Size Y": going,
                                                  "Vertices X": 2, "Vertices Y": 2})["Mesh"]
        strip = xf(g, strip, t=g.combine(0.0, g.math("MULTIPLY", going, -0.5), g.math("SUBTRACT", h, 0.004)))
        sx = g.separate(position(g))["X"]
        inner = cmp(g, "LESS_THAN", g.math("ABSOLUTE", sx), g.math("SUBTRACT", g.math("MULTIPLY", w, 0.5), 0.13))
        spill_pts = g.node("GeometryNodeDistributePointsOnFaces", props={"distribute_method": "RANDOM"}, Mesh=strip,
                           Density=g.math("MULTIPLY", weeds_d, 12.0), Seed=g.math("ADD", seed, 8))["Points"]
        spill_pts = g.node("GeometryNodeDeleteGeometry", props={"domain": "POINT"}, Geometry=spill_pts,
                           Selection=inner)["Geometry"]
        crumb = g.node("GeometryNodeMeshIcoSphere", Radius=1.0, Subdivisions=2)["Mesh"]
        cn = g.node("ShaderNodeTexNoise", Vector=position(g), Scale=1.5, Detail=2.0)["Fac"]
        crumb = g.node("GeometryNodeSetPosition", Geometry=crumb, Offset=g.vmath(
            "SCALE", g.node("GeometryNodeInputNormal")["Normal"],
            scale=g.math("MULTIPLY", g.math("SUBTRACT", cn, 0.5), 1.2))["Vector"])["Geometry"]
        crumb = set_mat(g, smooth(g, xf(g, crumb, s=(1.3, 1.0, 0.28))), "Soil")
        spill = g.node("GeometryNodeInstanceOnPoints", Points=spill_pts, Instance=crumb,
                       Rotation=g.combine(0.0, 0.0, rand(g, 0.0, TAU, seed, 9)),
                       Scale=g.math("MULTIPLY", rand(g, 0.006, 0.03, seed, 10), g.math(
                           "ADD", 0.4, g.map_range(g.math("ABSOLUTE", sx), g.math("SUBTRACT", g.math(
                               "MULTIPLY", w, 0.5), 0.13), g.math("MULTIPLY", w, 0.5), 0.0, 1.0)["Result"])))["Instances"]
        front = g.node("GeometryNodeMeshLine", props={"mode": "END_POINTS"}, Count=g.math(
            "CEIL", g.math("MULTIPLY", w, 14.0)), **{"Start Location": g.combine(g.math("MULTIPLY", w, -0.48), 0.0, h),
                                                     "Offset": g.combine(g.math("MULTIPLY", w, 0.48), 0.0, h)})["Mesh"]
        fx = g.separate(position(g))["X"]
        side_w = g.map_range(g.math("ABSOLUTE", fx), g.math("MULTIPLY", w, 0.25), g.math("MULTIPLY", w, 0.48),
                             0.0, 1.0)["Result"]
        front = g.node("GeometryNodeDeleteGeometry", props={"domain": "POINT"}, Geometry=front, Selection=cmp(
            g, "GREATER_THAN", rand(g, 0.0, 1.0, seed, 11), g.math("ADD", side_w, 0.15)))["Geometry"]
        front = g.node("GeometryNodeSetPosition", Geometry=front, Offset=g.combine(
            rand(g, -0.02, 0.02, seed, 12), rand(g, -0.03, 0.012, seed, 13), rand(g, -0.02, 0.0, seed, 14)))["Geometry"]
        over = g.node("GeometryNodeInstanceOnPoints", Points=front, Instance=crumb,
                      Rotation=g.combine(rand(g, -0.5, 0.5, seed, 15), 0.0, rand(g, 0.0, TAU, seed, 16)),
                      Scale=rand(g, 0.01, 0.028, seed, 17))["Instances"]
        corner = g.node("GeometryNodeMeshLine", props={"mode": "END_POINTS"}, Count=g.math(
            "CEIL", g.math("MULTIPLY", w, 45.0)),
            **{"Start Location": g.combine(g.math("MULTIPLY", w, -0.48), g.math("SUBTRACT", 0.015, going), h),
               "Offset": g.combine(g.math("MULTIPLY", w, 0.48), g.math("SUBTRACT", 0.015, going), h)})["Mesh"]
        corner = g.node("GeometryNodeDeleteGeometry", props={"domain": "POINT"}, Geometry=corner, Selection=cmp(
            g, "LESS_THAN", g.node("ShaderNodeTexNoise", props={"noise_dimensions": "4D"}, Vector=position(g),
                                   W=seed, Scale=3.0, Detail=1.0)["Fac"], 0.6))["Geometry"]
        cushion = g.node("GeometryNodeMeshIcoSphere", Radius=1.0, Subdivisions=2)["Mesh"]
        cushion = set_mat(g, smooth(g, xf(g, cushion, s=(1.6, 1.0, 0.3))), "Moss")
        corner = g.node("GeometryNodeSetPosition", Geometry=corner, Offset=g.combine(
            rand(g, -0.01, 0.01, seed, 20), rand(g, -0.012, 0.025, seed, 21), 0.0))["Geometry"]
        moss = g.node("GeometryNodeInstanceOnPoints", Points=corner, Instance=cushion,
                      Rotation=g.combine(0.0, 0.0, rand(g, -0.4, 0.4, seed, 18)),
                      Scale=rand(g, 0.014, 0.034, seed, 19))["Instances"]
        moss = g.node("GeometryNodeSwitch", props={"input_type": "GEOMETRY"},
                      Switch=cmp(g, "GREATER_THAN", weeds_d, 0.0), **{"True": moss})["Output"]
        dirt = join(g, dirt, spill, over, moss)
    g.output("Geometry", "GEOMETRY", join(g, box, weeds, dirt), desc="The step")
    return g.finish()


@once
def handrail():
    g = Graph("Garden Structures Handrail", description="Black steel stair handrail: a bottom post (foot set "
              "into the ground), a knuckle joint, a rail climbing back along -Y with the flight and running on past "
              "the top post by Extension, and a top post down to the landing. Base at the origin")
    post_h = g.input("Post Height", "FLOAT", 0.85, min=0.1, max=3.0, subtype="DISTANCE", desc="Bottom post height")
    run = g.input("Run", "FLOAT", 0.91, min=0.0, max=10.0, subtype="DISTANCE", desc="Horizontal run back along -Y")
    rise = g.input("Rise", "FLOAT", 0.23, min=-2.0, max=5.0, subtype="DISTANCE", desc="Rise of the flight over the run")
    rrise = g.input("Rail Rise", "FLOAT", 0.39, min=-2.0, max=5.0, subtype="DISTANCE",
                    desc="Rise of the rail between the two post tops (steeper than the flight)")
    ext = g.input("Extension", "FLOAT", 0.4, min=0.0, max=5.0, subtype="DISTANCE", desc="Rail beyond the top post")
    r = g.input("Radius", "FLOAT", 0.016, min=0.002, max=0.1, subtype="DISTANCE", desc="Bar radius")
    ties = g.input("Ties", "INT", 0, min=0, max=40, desc="Blue twine wraps along the lower part of the sloping rail")
    with g.frame("Posts, sloping rail with extension, knuckles at the joints"):
        top0 = g.combine(0.0, 0.0, post_h)
        end_floor = g.combine(0.0, g.math("MULTIPLY", run, -1.0), g.math("SUBTRACT", rise, 0.05))
        top1 = g.combine(0.0, g.math("MULTIPLY", run, -1.0), g.math("ADD", rrise, post_h))
        k = g.math("DIVIDE", ext, g.math("MAXIMUM", run, 0.01))
        tip = g.combine(0.0, g.math("MULTIPLY", g.math("ADD", run, ext), -1.0),
                        g.math("ADD", g.math("ADD", rrise, post_h), g.math("MULTIPLY", rrise, k)))
        bars = [g.group(rod(), Start=a, End=b, Radius=r, Resolution=12)["Mesh"]
                for a, b in (((0.0, 0.0, -0.05), top0), (top0, top1), (end_floor, top1), (top1, tip))]
        knobs = [xf(g, g.node("GeometryNodeMeshUVSphere", Segments=12, Rings=6,
                              Radius=g.math("MULTIPLY", r, 1.8))["Mesh"], t=pt) for pt in (top0, top1)]
        out = set_mat(g, smooth(g, join(g, *bars, *knobs)), "Dark Metal")
    with g.frame("Blue twine wraps: thin rings around the sloping rail near its foot"):
        seg = g.vmath("SUBTRACT", top1, top0)["Vector"]
        tl = g.node("GeometryNodeMeshLine", props={"mode": "END_POINTS"}, Count=g.math("MAXIMUM", ties, 1),
                    **{"Start Location": g.vmath("ADD", top0, g.vmath("SCALE", seg, scale=0.08)["Vector"])["Vector"],
                       "Offset": g.vmath("ADD", top0, g.vmath("SCALE", seg, scale=0.45)["Vector"])["Vector"]})["Mesh"]
        ring_m = g.group(ring(), Radius=g.math("ADD", r, 0.002), **{"Tube Width": 0.0045, "Tube Height": 0.0045,
                                                                      "Resolution": 12, "Tube Resolution": 4})["Mesh"]
        ring_m = set_mat(g, store(g, ring_m, "nk_color", (0.02, 0.06, 0.45, 1.0), dtype="FLOAT_COLOR"), "Painted")
        rot = g.node("FunctionNodeAlignRotationToVector", props={"axis": "Z"}, Vector=seg)["Rotation"]
        wraps = g.node("GeometryNodeInstanceOnPoints", Points=tl, Instance=ring_m, Rotation=rot)["Instances"]
        wraps = g.node("GeometryNodeSwitch", props={"input_type": "GEOMETRY"},
                       Switch=g.node("FunctionNodeCompare", props={"data_type": "INT", "operation": "GREATER_THAN"},
                                     A=ties, B=0)["Result"], **{"True": wraps})["Output"]
    g.output("Geometry", "GEOMETRY", join(g, out, wraps), desc="The handrail")
    return g.finish()


@once
def watering_can():
    g = Graph("Garden Structures Watering Can", description="Tall galvanised can: turned body, domed top, a "
              "rolled band, a handle hoop on +X and a spout rising on -X. Base at the origin")
    h = g.input("Height", "FLOAT", 0.58, min=0.05, max=2.0, subtype="DISTANCE", desc="Base to top of dome")
    r = g.input("Radius", "FLOAT", 0.085, min=0.01, max=1.0, subtype="DISTANCE", desc="Body radius")
    with g.frame("Body, dome and band"):
        bh = g.math("MULTIPLY", h, 0.86)
        body = g.group(profile_revolve(), Height=bh, Segments=40, Rings=4, **{
            "Radius Bottom": g.math("MULTIPLY", r, 1.02), "Radius Lower": r, "Radius Middle": r,
            "Radius Upper": g.math("MULTIPLY", r, 0.96), "Radius Top": g.math("MULTIPLY", r, 0.9)})["Mesh"]
        dome = g.node("GeometryNodeMeshUVSphere", Segments=40, Rings=12, Radius=1.0)["Mesh"]
        dome = xf(g, dome, t=g.combine(0.0, 0.0, bh),
                  s=g.combine(g.math("MULTIPLY", r, 0.9), g.math("MULTIPLY", r, 0.9), g.math("MULTIPLY", h, 0.14)))
        band = g.group(ring(), Radius=r, **{"Tube Width": 0.012, "Tube Height": 0.02, "Resolution": 40})["Mesh"]
        band = xf(g, band, t=g.combine(0.0, 0.0, g.math("MULTIPLY", h, 0.42)))
    with g.frame("Handle hoop on the side, spout"):
        hoop = g.group(ring(), Radius=g.math("MULTIPLY", h, 0.2), Sweep=math.pi,
                       **{"Tube Width": 0.014, "Tube Height": 0.014, "Resolution": 24})["Mesh"]
        hoop = xf(g, hoop, t=g.combine(r, 0.0, g.math("MULTIPLY", h, 0.62)), r=(math.pi / 2, math.pi / 2, 0.0))
        spout = g.group(rod(), Start=g.combine(g.math("MULTIPLY", r, -0.8), 0.0, g.math("MULTIPLY", h, 0.2)),
                        End=g.combine(g.math("MULTIPLY", r, -3.2), 0.0, g.math("MULTIPLY", h, 0.8)),
                        Radius=0.012, Resolution=10)["Mesh"]
        out = set_mat(g, smooth(g, join(g, body, dome, band, hoop, spout)), "Galvanised")
    g.output("Geometry", "GEOMETRY", out, desc="The can")
    return g.finish()


@once
def pallet():
    g = Graph("Garden Structures Pallet", description="Worn timber pallet: five chamfered top deck boards along "
              "X with irregular widths, small skew and lift, some broken short (leaving cavities); three stringer "
              "boards, nine blocks and three bottom boards; per-board nk_rand. Base at the origin")
    size = g.input("Size", "VECTOR", (1.2, 0.8, 0.144), subtype="XYZ", desc="Length, width, height")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    sz = g.separate(size)
    with g.frame("Deck boards (5 along X), stringers (3 across), blocks (3 x 3), bottom boards (3)"):
        tb = 0.022
        top = g.node("GeometryNodeMeshLine", props={"mode": "END_POINTS"}, Count=5,
                     **{"Start Location": g.combine(0.0, g.math("MULTIPLY", sz["Y"], -0.43),
                                                    g.math("SUBTRACT", sz["Z"], tb / 2)),
                        "Offset": g.combine(0.0, g.math("MULTIPLY", sz["Y"], 0.43), g.math("SUBTRACT", sz["Z"],
                                                                                           tb / 2))})["Mesh"]
        bi = index(g)
        broken = cmp(g, "GREATER_THAN", rand(g, 0.0, 1.0, seed, 40, ident=bi), 0.75)
        blen = g.math("MULTIPLY", sz["X"], g.mix(broken, rand(g, 0.97, 1.03, seed, 41, ident=bi),
                                                   rand(g, 0.5, 0.75, seed, 42, ident=bi)))
        top = g.node("GeometryNodeSetPosition", Geometry=top, Offset=g.combine(
            g.math("MULTIPLY", g.math("SUBTRACT", sz["X"], blen), g.math("SUBTRACT", rand(g, 0, 1, seed, 43, ident=bi),
                                                                          0.5)),
            rand(g, -0.012, 0.012, seed, 44, ident=bi), rand(g, -0.004, 0.006, seed, 45, ident=bi)))["Geometry"]
        top_b = g.group(chamfer_boxes(), Points=top, Chamfer=0.006,
                        Size=g.combine(blen, rand(g, 0.095, 0.14, seed, 46, ident=bi), tb),
                        Rotation=g.combine(rand(g, -0.03, 0.03, seed, 47, ident=bi), rand(g, -0.015, 0.015, seed, 48,
                                                                                         ident=bi),
                                           rand(g, -0.035, 0.035, seed, 49, ident=bi)))["Mesh"]
        blk_h = g.math("SUBTRACT", sz["Z"], 2 * tb)
        grid = g.node("GeometryNodeMeshGrid", **{"Size X": g.math("SUBTRACT", sz["X"], 0.145),
                                                 "Size Y": g.math("SUBTRACT", sz["Y"], 0.1),
                                                 "Vertices X": 3, "Vertices Y": 3})["Mesh"]
        blocks = g.node("GeometryNodeInstanceOnPoints", Points=xf(g, grid, t=g.combine(0.0, 0.0, g.math(
            "ADD", tb, g.math("MULTIPLY", blk_h, 0.5)))), Instance=cube(g, g.combine(0.145, 0.1, blk_h)))["Instances"]
        line3 = g.node("GeometryNodeMeshLine", props={"mode": "END_POINTS"}, Count=3,
                       **{"Start Location": g.combine(g.math("MULTIPLY", sz["X"], -0.44), 0.0, 0.0),
                          "Offset": g.combine(g.math("MULTIPLY", sz["X"], 0.44), 0.0, 0.0)})["Mesh"]
        strg = g.node("GeometryNodeInstanceOnPoints", Points=xf(g, line3, t=g.combine(
            0.0, 0.0, g.math("SUBTRACT", sz["Z"], 1.5 * tb))), Instance=cube(g, g.combine(0.145, sz["Y"], tb * 0.9)))
        bot = g.node("GeometryNodeInstanceOnPoints", Points=xf(g, xf(g, line3, r=(0.0, 0.0, math.pi / 2)),
                                                               s=g.combine(1.0, g.math("DIVIDE", sz["Y"], sz["X"]),
                                                                           1.0)),
                     Instance=cube(g, g.combine(sz["X"], 0.1, tb)))["Instances"]
        bot = xf(g, bot, t=(0.0, 0.0, tb / 2))
        allb = g.node("GeometryNodeRealizeInstances", Geometry=join(g, top_b, blocks, strg["Instances"], bot))
        isl = g.node("GeometryNodeInputMeshIsland")["Island Index"]
        allb = store(g, allb["Geometry"], "nk_rand", g.node("FunctionNodeRandomValue", props={"data_type": "FLOAT"},
                                                             ID=isl, Seed=seed)["Value"])
        out = set_mat(g, allb, "Pallet Wood")
    g.output("Geometry", "GEOMETRY", out, desc="The pallet")
    return g.finish()


@once
def pond_grates():
    g = Graph("Garden Structures Pond Grates", description="Steel mesh grates over a pond: a row of panels "
              "with frame bars, square wire mesh (a grid's edges swept by a tiny square profile), dark water "
              "below and a stone coping on the long edges. Centred on the origin, X along the row")
    length = g.input("Length", "FLOAT", 4.55, min=0.2, max=20.0, subtype="DISTANCE", desc="Row length (X)")
    depth = g.input("Depth", "FLOAT", 1.35, min=0.2, max=10.0, subtype="DISTANCE", desc="Panel depth (Y)")
    panels = g.input("Panels", "INT", 6, min=1, max=40, desc="Number of panels")
    mesh = g.input("Mesh Size", "FLOAT", 0.05, min=0.02, max=0.5, subtype="DISTANCE", desc="Wire mesh opening")
    show_w = g.input("Water", "BOOL", True, desc="Add a dark water plane (off when the ground part supplies the pond)")
    drop = g.input("Water Drop", "FLOAT", 0.12, min=0.0, max=1.0, subtype="DISTANCE", desc="Water below the grates")
    with g.frame("Frame bars between panels and along both long edges"):
        bars = g.node("GeometryNodeMeshLine", props={"mode": "END_POINTS"}, Count=g.math("ADD", panels, 1),
                      **{"Start Location": g.combine(g.math("MULTIPLY", length, -0.5), 0.0, 0.0),
                         "Offset": g.combine(g.math("MULTIPLY", length, 0.5), 0.0, 0.0)})["Mesh"]
        cross = g.node("GeometryNodeInstanceOnPoints", Points=bars,
                       Instance=cube(g, g.combine(0.04, depth, 0.03)))["Instances"]
        edges = g.node("GeometryNodeMeshGrid", **{"Size X": 0.0, "Size Y": depth, "Vertices X": 1,
                                                  "Vertices Y": 2})["Mesh"]
        longb = g.node("GeometryNodeInstanceOnPoints", Points=edges,
                       Instance=cube(g, g.combine(length, 0.04, 0.03)))["Instances"]
        frame = set_mat(g, g.node("GeometryNodeRealizeInstances", Geometry=join(g, cross, longb))["Geometry"],
                        "Galvanised")
    with g.frame("Wire mesh: grid edges to curves, swept by a small square"):
        nx = g.math("ADD", g.math("CEIL", g.math("DIVIDE", length, mesh)), 1.0)
        ny = g.math("ADD", g.math("CEIL", g.math("DIVIDE", depth, mesh)), 1.0)
        grid = g.node("GeometryNodeMeshGrid", **{"Size X": length, "Size Y": depth, "Vertices X": nx,
                                                 "Vertices Y": ny})["Mesh"]
        crv = g.node("GeometryNodeMeshToCurve", Mesh=grid)["Curve"]
        prof = g.node("GeometryNodeCurvePrimitiveCircle", Resolution=4, Radius=0.0035)["Curve"]
        wire = g.node("GeometryNodeCurveToMesh", Curve=crv, **{"Profile Curve": prof})["Mesh"]
        wire = set_mat(g, xf(g, wire, t=(0.0, 0.0, 0.005)), "Dark Metal")
    with g.frame("Water plane below and stone coping on the long edges"):
        water = g.node("GeometryNodeMeshGrid", **{"Size X": length, "Size Y": depth, "Vertices X": 2,
                                                  "Vertices Y": 2})["Mesh"]
        water = set_mat(g, xf(g, water, t=g.combine(0.0, 0.0, g.math("MULTIPLY", drop, -1.0))), "Water")
        water = g.node("GeometryNodeSwitch", props={"input_type": "GEOMETRY"}, Switch=show_w,
                       **{"True": water})["Output"]
        cop = g.node("GeometryNodeMeshGrid", **{"Size X": 0.0, "Size Y": g.math("ADD", depth, 0.2),
                                                "Vertices X": 1, "Vertices Y": 2})["Mesh"]
        coping = g.node("GeometryNodeInstanceOnPoints", Points=cop,
                        Instance=cube(g, g.combine(g.math("ADD", length, 0.2), 0.12, 0.04)))["Instances"]
        coping = set_mat(g, g.node("GeometryNodeRealizeInstances", Geometry=coping)["Geometry"], "Concrete")
    g.output("Geometry", "GEOMETRY", join(g, frame, wire, water, coping), desc="The pond grates")
    return g.finish()


@once
def seedlings():
    g = Graph("Garden Structures Seedlings", description="Worked soil terrace dressing: a rectangle (X along, Y "
              "across) tilted to rise along -Y; patchy (noise-clumped) grass tufts and leafy weeds, soil clods, "
              "pebbles and litter, and a broken row of edge stones along the front (+Y) edge. Only the dressing; "
              "the soil surface itself belongs to the ground part")
    size = g.input("Size", "VECTOR", (2.8, 1.4, 0.0), subtype="XYZ", desc="Terrace length (X) and depth (Y)")
    slope = g.input("Slope", "FLOAT", 0.117, min=-2.0, max=2.0, desc="Height gained per metre toward -Y")
    dens = g.input("Density", "FLOAT", 22.0, min=0.0, max=400.0, desc="Plants per square metre")
    broad = g.input("Broad", "FLOAT", 0.0, min=0.0, max=1.0, subtype="FACTOR",
                    desc="Share of leafy weeds among the grassy seedlings")
    edge = g.input("Edge Stones", "FLOAT", 6.0, min=0.0, max=40.0, desc="Edge stones per metre along the front")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    with g.frame("Tilted rectangle; patchy plant points (noise clumps)"):
        sz = g.separate(size)
        grid = g.node("GeometryNodeMeshGrid", **{"Size X": sz["X"], "Size Y": sz["Y"], "Vertices X": 2,
                                                 "Vertices Y": 2})["Mesh"]
        y = g.separate(position(g))["Y"]
        grid = g.node("GeometryNodeSetPosition", Geometry=grid,
                      Offset=g.combine(0.0, 0.0, g.math("MULTIPLY", y, g.math("MULTIPLY", slope, -1.0))))["Geometry"]
        pts = g.node("GeometryNodeDistributePointsOnFaces", props={"distribute_method": "POISSON"}, Mesh=grid,
                     **{"Distance Min": 0.03, "Density Max": g.math("MULTIPLY", dens, 1.6)}, Seed=seed)["Points"]
        clump = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "4D"}, Vector=position(g), W=seed,
                       Scale=2.2, Detail=3.0)["Fac"]
        drop = cmp(g, "LESS_THAN", g.math("ADD", clump, rand(g, -0.15, 0.15, seed, 8)), 0.5)
        pts = g.node("GeometryNodeDeleteGeometry", props={"domain": "POINT"}, Geometry=pts, Selection=drop)
    with g.frame("Grass tufts and leafy weeds, varied size"):
        tuft = set_mat(g, g.group(grass_tuft(), Blades=9, Height=0.15, Radius=0.03, Spread=0.7, Seed=seed)["Mesh"],
                       "Plant")
        wd = g.group(weed(), Leaves=9, Seed=seed, **{"Leaf Length": 0.07, "Stem Length": 0.08})["Mesh"]
        mat_ = set_mat(g, g.group(grass_tuft(), Blades=24, Height=0.06, Radius=0.08, Spread=1.0, Seed=seed,
                                  **{"Height Min": 0.4, "Resolution": 3})["Mesh"], "Plant")
        kinds = g.node("GeometryNodeGeometryToInstance")
        for x in (mat_, wd, tuft):
            g.connect(x, kinds.i("Geometry"))
        r7 = rand(g, 0.0, 1.0, seed, 7)
        pick = g.math("ADD", cmp(g, "LESS_THAN", r7, broad),
                      g.math("MULTIPLY", cmp(g, "GREATER_THAN", r7, 0.7), 2.0))
        out = g.node("GeometryNodeInstanceOnPoints", Points=pts["Geometry"], Instance=kinds["Instances"],
                     **{"Pick Instance": True, "Instance Index": pick},
                     Rotation=g.combine(0.0, 0.0, rand(g, 0.0, TAU, seed, 3)),
                     Scale=g.math("POWER", rand(g, 0.45, 1.15, seed, 4), 1.5))["Instances"]
    with g.frame("Soil clods, pebbles, litter; edge stones along the front edge"):
        dirt = g.group(debris(), Surface=grid, Clods=90.0, Pebbles=14.0, Litter=30.0, Size=0.022,
                       Seed=g.math("ADD", seed, 60))["Geometry"]
        n_edge = g.math("MAXIMUM", g.math("CEIL", g.math("MULTIPLY", sz["X"], edge)), 1.0)
        line = g.node("GeometryNodeMeshLine", props={"mode": "END_POINTS"}, Count=n_edge, **{
            "Start Location": g.combine(g.math("MULTIPLY", sz["X"], -0.5), g.math("MULTIPLY", sz["Y"], 0.5),
                                        g.math("MULTIPLY", g.math("MULTIPLY", sz["Y"], 0.5), g.math("MULTIPLY", slope, -1.0))),
            "Offset": g.combine(g.math("MULTIPLY", sz["X"], 0.5), g.math("MULTIPLY", sz["Y"], 0.5),
                                g.math("MULTIPLY", g.math("MULTIPLY", sz["Y"], 0.5), g.math("MULTIPLY", slope, -1.0)))})
        epts = g.node("GeometryNodeSetPosition", Geometry=line["Mesh"], Offset=g.combine(
            rand(g, -0.04, 0.04, seed, 70), rand(g, -0.06, 0.02, seed, 71), 0.0))["Geometry"]
        epts = g.node("GeometryNodeDeleteGeometry", props={"domain": "POINT"}, Geometry=epts,
                      Selection=cmp(g, "LESS_THAN", rand(g, 0, 1, seed, 72), 0.25))["Geometry"]
        stone = g.node("GeometryNodeMeshIcoSphere", Radius=1.0, Subdivisions=1)["Mesh"]
        stone = set_mat(g, xf(g, stone, t=(0.0, 0.0, -0.3), s=(1.0, 0.75, 0.6)), "Stone")
        stones = g.node("GeometryNodeInstanceOnPoints", Points=epts, Instance=stone,
                        Rotation=g.combine(rand(g, -0.3, 0.3, seed, 73), 0.0, rand(g, 0.0, TAU, seed, 74)),
                        Scale=rand(g, 0.035, 0.075, seed, 75))["Instances"]
    g.output("Geometry", "GEOMETRY", join(g, out, dirt, stones), desc="The terrace dressing")
    return g.finish()

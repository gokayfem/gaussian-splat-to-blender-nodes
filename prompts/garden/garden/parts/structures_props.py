"""Garden Structures small props: rock, steel ball, plain pot, statue, bird bath, lantern, football, chair, slide,
toy horse. Each is one group in its own frame (base at the origin, +Z up)."""
import math

from library.shapes import grass_tuft, profile_revolve
from nodekit.graph import Graph, once

from garden.parts.structures_util import cube, join, position, set_mat, smooth, store, xf

TAU = 2.0 * math.pi


def _sphere(g, size, t, seg=24, rings=12):
    m = g.node("GeometryNodeMeshUVSphere", Segments=seg, Rings=rings, Radius=1.0)["Mesh"]
    return xf(g, m, t=t, s=size)


@once
def rock():
    g = Graph("Garden Structures Rock", description="Weathered rounded rock: a smooth icosphere scaled to Size and displaced "
              "along its normal by two octaves of noise (seeded). Base at z 0")
    size = g.input("Size", "VECTOR", (0.4, 0.28, 0.17), subtype="XYZ", desc="Overall length, width, height")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Shape seed")
    lump = g.input("Lumpiness", "FLOAT", 0.35, min=0.0, max=1.0, subtype="FACTOR", desc="Noise displacement share")
    with g.frame("Icosphere, noise lumps, scale, sit on z 0"):
        ico = g.node("GeometryNodeMeshIcoSphere", Radius=0.5, Subdivisions=4)["Mesh"]
        n = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "4D"}, Vector=position(g), W=seed,
                   Scale=1.6, Detail=5.0, Roughness=0.55)["Fac"]
        nrm = g.node("GeometryNodeInputNormal")["Normal"]
        ico = g.node("GeometryNodeSetPosition", Geometry=ico, Offset=g.vmath(
            "SCALE", nrm, scale=g.math("MULTIPLY", g.math("SUBTRACT", n, 0.5), lump))["Vector"])["Geometry"]
        ico = xf(g, ico, s=size)
        flat = g.node("GeometryNodeSetPosition", Geometry=ico, Position=g.vmath("MAXIMUM", position(g), g.combine(
            -100.0, -100.0, g.math("MULTIPLY", g.separate(size)["Z"], -0.35)))["Vector"])["Geometry"]
        out = xf(g, flat, t=g.combine(0.0, 0.0, g.math("MULTIPLY", g.separate(size)["Z"], 0.35)))
        out = set_mat(g, smooth(g, out), "Stone")
    g.output("Geometry", "GEOMETRY", out, desc="The rock")
    return g.finish()


@once
def steel_ball():
    g = Graph("Garden Structures Steel Ball", description="Polished stainless garden sphere resting on z 0")
    r = g.input("Radius", "FLOAT", 0.15, min=0.01, max=2.0, subtype="DISTANCE", desc="Sphere radius")
    with g.frame("UV sphere, smooth, mirror steel"):
        m = g.node("GeometryNodeMeshUVSphere", Segments=48, Rings=24, Radius=r)["Mesh"]
        out = set_mat(g, smooth(g, xf(g, m, t=g.combine(0.0, 0.0, r))), "Steel")
    g.output("Geometry", "GEOMETRY", out, desc="The ball")
    return g.finish()


@once
def plain_pot():
    g = Graph("Garden Structures Plain Pot", description="Plain round pot (glazed or painted, colour from nk_color) "
              "with soil and an upright grassy plant. Base at the origin")
    h = g.input("Height", "FLOAT", 0.34, min=0.05, max=2.0, subtype="DISTANCE", desc="Pot height")
    r = g.input("Radius", "FLOAT", 0.16, min=0.02, max=1.0, subtype="DISTANCE", desc="Rim radius")
    col = g.input("Color", "COLOR", (0.04, 0.04, 0.03, 1.0), desc="Pot colour (linear), stored as nk_color")
    glazed = g.input("Glazed", "BOOL", True, desc="Glossy glaze (off: matt paint/clay)")
    grass = g.input("Plant Height", "FLOAT", 0.35, min=0.0, max=2.0, subtype="DISTANCE", desc="Grassy plant height")
    with g.frame("Turned pot, glazed or matt, coloured"):
        body = g.group(profile_revolve(), Height=h, Segments=48, Rings=4, **{
            "Radius Bottom": g.math("MULTIPLY", r, 0.72), "Radius Lower": g.math("MULTIPLY", r, 0.86),
            "Radius Middle": g.math("MULTIPLY", r, 0.95), "Radius Upper": g.math("MULTIPLY", r, 0.99),
            "Radius Top": r, "Wall Thickness": 0.015})["Mesh"]
        body = store(g, smooth(g, body), "nk_color", col, dtype="FLOAT_COLOR")
        gl = set_mat(g, body, "Glazed")
        mt = set_mat(g, body, "Painted")
        body = g.node("GeometryNodeSwitch", props={"input_type": "GEOMETRY"}, Switch=glazed, **{"False": mt,
                                                                                               "True": gl})["Output"]
    with g.frame("Soil and a grass clump"):
        soil = g.node("GeometryNodeMeshCircle", props={"fill_type": "TRIANGLE_FAN"}, Vertices=32,
                      Radius=g.math("SUBTRACT", r, 0.02))["Mesh"]
        soil = set_mat(g, xf(g, soil, t=g.combine(0.0, 0.0, g.math("SUBTRACT", h, 0.04))), "Soil")
        tuft = g.group(grass_tuft(), Blades=40, Height=grass, Radius=g.math("MULTIPLY", r, 0.6), Spread=0.45,
                       Seed=4)["Mesh"]
        tuft = set_mat(g, xf(g, tuft, t=g.combine(0.0, 0.0, g.math("SUBTRACT", h, 0.04))), "Plant")
    g.output("Geometry", "GEOMETRY", join(g, body, soil, tuft), desc="The potted plant")
    return g.finish()


@once
def buddha():
    g = Graph("Garden Structures Buddha", description="Small seated Buddha statue from ellipsoids: crossed-leg "
              "base, torso, shoulders, head with topknot. Faces +Y. Base at the origin")
    h = g.input("Height", "FLOAT", 0.52, min=0.05, max=3.0, subtype="DISTANCE", desc="Overall seated height")
    with g.frame("Stacked ellipsoids scaled by Height"):
        parts = []
        for s, t in (((0.42, 0.30, 0.13), (0.0, 0.02, 0.07)), ((0.27, 0.19, 0.30), (0.0, 0.0, 0.33)),
                     ((0.34, 0.20, 0.12), (0.0, 0.0, 0.50)), ((0.13, 0.13, 0.15), (0.0, 0.01, 0.72)),
                     ((0.05, 0.05, 0.05), (0.0, 0.0, 0.86)), ((0.18, 0.12, 0.08), (0.0, 0.12, 0.25))):
            parts.append(_sphere(g, g.vmath("SCALE", s, scale=h)["Vector"], g.vmath("SCALE", t, scale=h)["Vector"]))
        out = set_mat(g, smooth(g, join(g, *parts)), "Dark Stone")
    g.output("Geometry", "GEOMETRY", out, desc="The statue")
    return g.finish()


@once
def bird_bath():
    g = Graph("Garden Structures Bird Bath", description="Mushroom-shaped stone ornament: a short post and a "
              "domed cap. Base at the origin")
    top = g.input("Top", "FLOAT", 0.27, min=0.05, max=2.0, subtype="DISTANCE", desc="Height of the cap top")
    cr = g.input("Cap Radius", "FLOAT", 0.15, min=0.02, max=1.0, subtype="DISTANCE", desc="Cap radius")
    with g.frame("Post and cap"):
        post_h = g.math("SUBTRACT", top, g.math("MULTIPLY", cr, 0.45))
        post = g.node("GeometryNodeMeshCylinder", Vertices=16, Radius=g.math("MULTIPLY", cr, 0.25),
                      Depth=post_h)["Mesh"]
        post = xf(g, post, t=g.combine(0.0, 0.0, g.math("MULTIPLY", post_h, 0.5)))
        cap = _sphere(g, g.combine(cr, cr, g.math("MULTIPLY", cr, 0.45)), g.combine(0.0, 0.0, post_h))
        out = set_mat(g, smooth(g, join(g, post, cap)), "Stone")
    g.output("Geometry", "GEOMETRY", out, desc="The ornament")
    return g.finish()


@once
def lantern():
    g = Graph("Garden Structures Lantern", description="Small dark stone lantern: plinth, post, square light "
              "box and pyramid roof. Base at the origin")
    h = g.input("Height", "FLOAT", 0.27, min=0.05, max=2.0, subtype="DISTANCE", desc="Overall height")
    r = g.input("Radius", "FLOAT", 0.085, min=0.01, max=1.0, subtype="DISTANCE", desc="Roof half-width")
    with g.frame("Plinth, post, box, roof"):
        def box(sx, sz, z):
            return xf(g, cube(g, g.combine(g.math("MULTIPLY", r, sx), g.math("MULTIPLY", r, sx),
                                           g.math("MULTIPLY", h, sz))), t=g.combine(0.0, 0.0, g.math("MULTIPLY", h, z)))
        roof = g.node("GeometryNodeMeshCone", Vertices=4, **{"Radius Top": 0.0, "Radius Bottom": g.math(
            "MULTIPLY", r, 1.414), "Depth": g.math("MULTIPLY", h, 0.25)})["Mesh"]
        roof = xf(g, roof, t=g.combine(0.0, 0.0, g.math("MULTIPLY", h, 0.875)), r=(0.0, 0.0, math.pi / 4))
        out = set_mat(g, join(g, box(1.6, 0.15, 0.075), box(0.7, 0.3, 0.3), box(1.3, 0.3, 0.6), roof), "Dark Stone")
    g.output("Geometry", "GEOMETRY", out, desc="The lantern")
    return g.finish()


@once
def football():
    g = Graph("Garden Structures Football", description="Green football with black patches, resting on z 0")
    r = g.input("Radius", "FLOAT", 0.105, min=0.02, max=1.0, subtype="DISTANCE", desc="Ball radius")
    with g.frame("Sphere with patch material"):
        m = g.node("GeometryNodeMeshUVSphere", Segments=32, Rings=16, Radius=r)["Mesh"]
        out = set_mat(g, smooth(g, xf(g, m, t=g.combine(0.0, 0.0, g.math("MULTIPLY", r, 0.97)))), "Ball")
    g.output("Geometry", "GEOMETRY", out, desc="The ball")
    return g.finish()


@once
def chair():
    g = Graph("Garden Structures Chair", description="Folding slatted timber garden chair: five seat slats on two "
              "side rails, four back slats between two uprights, front legs crossing the back legs below the seat; "
              "per-slat nk_color tone. Faces +Y. Base at the origin")
    col = g.input("Color", "COLOR", (0.5, 0.4, 0.33, 1.0), desc="Timber colour (linear), stored as nk_color")
    with g.frame("Seat slats, side rails, back slats and uprights, crossed legs"):
        pieces = []
        for k in range(5):
            pieces.append(xf(g, cube(g, (0.44, 0.065, 0.018)), t=(0.0, 0.17 - k * 0.085, 0.45)))
        for sx in (-0.2, 0.2):
            pieces.append(xf(g, cube(g, (0.03, 0.42, 0.04)), t=(sx, 0.0, 0.42)))
            pieces.append(xf(g, cube(g, (0.035, 0.03, 0.95)), t=(sx, -0.2, 0.47), r=(-0.2, 0.0, 0.0)))
            pieces.append(xf(g, cube(g, (0.035, 0.03, 0.62)), t=(sx * 1.05, 0.05, 0.28), r=(0.55, 0.0, 0.0)))
        for k in range(4):
            pieces.append(xf(g, cube(g, (0.38, 0.016, 0.06)), t=(0.0, -0.245 - k * 0.022, 0.62 + k * 0.1),
                             r=(-0.2, 0.0, 0.0)))
        out = store(g, join(g, *pieces), "nk_color", col, dtype="FLOAT_COLOR")
        out = set_mat(g, out, "Painted")
    g.output("Geometry", "GEOMETRY", out, desc="The chair")
    return g.finish()


@once
def reeds():
    g = Graph("Garden Structures Reeds", description="Clump of tall strap-leaved pond plants (iris/variegated "
              "rush): many long narrow blades from a small root disc, mostly upright with a few arching")
    h = g.input("Height", "FLOAT", 0.8, min=0.05, max=3.0, subtype="DISTANCE", desc="Tallest blade")
    n = g.input("Blades", "INT", 40, min=1, max=400, desc="Blades in the clump")
    r = g.input("Radius", "FLOAT", 0.12, min=0.0, max=2.0, subtype="DISTANCE", desc="Root spread")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    with g.frame("Grass tuft with long narrow blades"):
        out = g.group(grass_tuft(), Blades=n, Height=h, Radius=r, Spread=0.3, Seed=seed,
                      **{"Height Min": 0.5, "Blade Width": 0.035, "Curl": 0.15, "Fold": 0.5, "Resolution": 8})["Mesh"]
        out = set_mat(g, out, "Reed")
    g.output("Geometry", "GEOMETRY", out, desc="The reeds")
    return g.finish()


@once
def crate():
    g = Graph("Garden Structures Crate", description="Open plastic storage crate: four thin walls and a floor, "
              "coloured from nk_color. Base at the origin")
    size = g.input("Size", "VECTOR", (0.55, 0.38, 0.16), subtype="XYZ", desc="Outer size")
    col = g.input("Color", "COLOR", (0.12, 0.16, 0.22, 1.0), desc="Plastic colour (linear)")
    legs = g.input("Legs", "FLOAT", 0.0, min=0.0, max=2.0, subtype="DISTANCE",
                   desc="Height of a simple dark four-legged stand under the crate (0: none)")
    with g.frame("Walls and floor"):
        sz = g.separate(size)
        t = 0.008
        parts = [xf(g, cube(g, g.combine(sz["X"], sz["Y"], t)), t=(0.0, 0.0, t / 2))]
        for sgn in (-0.5, 0.5):
            parts.append(xf(g, cube(g, g.combine(sz["X"], t, sz["Z"])), t=g.combine(
                0.0, g.math("MULTIPLY", sz["Y"], sgn), g.math("MULTIPLY", sz["Z"], 0.5))))
            parts.append(xf(g, cube(g, g.combine(t, sz["Y"], sz["Z"])), t=g.combine(
                g.math("MULTIPLY", sz["X"], sgn), 0.0, g.math("MULTIPLY", sz["Z"], 0.5))))
        out = set_mat(g, store(g, join(g, *parts), "nk_color", col, dtype="FLOAT_COLOR"), "Painted")
    with g.frame("Optional stand: four legs below the floor"):
        grid = g.node("GeometryNodeMeshGrid", **{"Size X": g.math("SUBTRACT", sz["X"], 0.05),
                                                 "Size Y": g.math("SUBTRACT", sz["Y"], 0.05),
                                                 "Vertices X": 2, "Vertices Y": 2})["Mesh"]
        leg = xf(g, cube(g, g.combine(0.025, 0.025, legs)), t=g.combine(0.0, 0.0, g.math("MULTIPLY", legs, -0.5)))
        stand = set_mat(g, g.node("GeometryNodeInstanceOnPoints", Points=grid, Instance=leg)["Instances"],
                        "Dark Metal")
    g.output("Geometry", "GEOMETRY", join(g, out, stand), desc="The crate on its stand")
    return g.finish()


@once
def slide():
    g = Graph("Garden Structures Slide", description="Children's plastic slide: a sloping chute with side lips "
              "and a stepped ladder block, coloured from nk_color. Runs down along +X. Base at the origin")
    ln = g.input("Length", "FLOAT", 0.95, min=0.2, max=5.0, subtype="DISTANCE", desc="Chute horizontal length")
    top = g.input("Top", "FLOAT", 0.56, min=0.1, max=3.0, subtype="DISTANCE", desc="Platform height")
    col = g.input("Color", "COLOR", (0.12, 0.45, 0.15, 1.0), desc="Chute colour (linear)")
    with g.frame("Chute and ladder"):
        ang = g.math("ARCTAN2", top, ln)
        slen = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", ln, ln), g.math("MULTIPLY", top, top)))
        chute = xf(g, cube(g, g.combine(slen, 0.38, 0.04)), t=g.combine(g.math("MULTIPLY", ln, 0.5), 0.0,
                                                                        g.math("MULTIPLY", top, 0.5)),
                   r=g.combine(0.0, ang, 0.0))
        chute = store(g, chute, "nk_color", col, dtype="FLOAT_COLOR")
        ladder = xf(g, cube(g, g.combine(0.3, 0.45, top)), t=g.combine(-0.15, 0.0, g.math("MULTIPLY", top, 0.5)))
        ladder = store(g, ladder, "nk_color", (0.6, 0.12, 0.05, 1.0), dtype="FLOAT_COLOR")
        out = set_mat(g, join(g, chute, ladder), "Painted")
    g.output("Geometry", "GEOMETRY", out, desc="The slide")
    return g.finish()


@once
def toy_horse():
    g = Graph("Garden Structures Toy Horse", description="Ride-on toy: ellipsoid body and head on four legs and a "
              "base; pale grey-blue plastic. Base at the origin")
    h = g.input("Height", "FLOAT", 0.7, min=0.1, max=2.0, subtype="DISTANCE", desc="Height to the top of the head")
    with g.frame("Body, neck/head, legs"):
        parts = [_sphere(g, g.vmath("SCALE", s, scale=h)["Vector"], g.vmath("SCALE", t, scale=h)["Vector"])
                 for s, t in (((0.32, 0.13, 0.13), (0.0, 0.0, 0.62)), ((0.10, 0.08, 0.2), (0.27, 0.0, 0.82)),
                              ((0.06, 0.06, 0.25), (0.2, 0.06, 0.3)), ((0.06, 0.06, 0.25), (-0.2, 0.06, 0.3)),
                              ((0.06, 0.06, 0.25), (0.2, -0.06, 0.3)), ((0.06, 0.06, 0.25), (-0.2, -0.06, 0.3)),
                              ((0.4, 0.18, 0.05), (0.0, 0.0, 0.05)))]
        out = store(g, smooth(g, join(g, *parts)), "nk_color", (0.36, 0.40, 0.42, 1.0), dtype="FLOAT_COLOR")
        out = set_mat(g, out, "Painted")
    g.output("Geometry", "GEOMETRY", out, desc="The toy")
    return g.finish()


@once
def wheelbarrow():
    g = Graph("Garden Structures Wheelbarrow", description="Garden wheelbarrow: a tapered open tub (painted, "
              "nk_color), front wheel with tyre, two handle shafts running back along -X and two rear legs. "
              "Front (wheel) on +X. Base at the origin")
    col = g.input("Color", "COLOR", (0.2, 0.26, 0.24, 1.0), desc="Tub colour (linear)")
    with g.frame("Tub: a lofted, tapered box (cone with 4 sides), open top"):
        tub = g.node("GeometryNodeMeshCone", props={"fill_type": "NONE"}, Vertices=4,
                     **{"Radius Top": 0.42, "Radius Bottom": 0.26, "Depth": 0.26})["Mesh"]
        tub = xf(g, tub, t=(0.05, 0.0, 0.43), r=(0.0, 0.0, math.pi / 4), s=(1.25, 0.85, 1.0))
        tub = store(g, smooth(g, tub, on=False), "nk_color", col, dtype="FLOAT_COLOR")
        tub = set_mat(g, tub, "Painted")
    with g.frame("Wheel, handles, legs"):
        tyre = g.node("GeometryNodeMeshCylinder", Vertices=24, Radius=0.18, Depth=0.08)["Mesh"]
        tyre = set_mat(g, xf(g, tyre, t=(0.48, 0.0, 0.18), r=(math.pi / 2, 0.0, 0.0)), "Dark Metal")
        bars = []
        for sy in (-0.24, 0.24):
            bars.append(xf(g, cube(g, (1.3, 0.03, 0.03)), t=(-0.05, sy, 0.36), r=(0.0, 0.18, 0.0)))
            bars.append(xf(g, cube(g, (0.03, 0.03, 0.32)), t=(-0.25, sy * 0.9, 0.16)))
        frame = set_mat(g, join(g, *bars), "Dark Metal")
    g.output("Geometry", "GEOMETRY", join(g, tub, tyre, frame), desc="The wheelbarrow")
    return g.finish()


@once
def storage_box():
    g = Graph("Garden Structures Storage Box", description="Black plastic garden storage chest: a box with a "
              "slightly overhanging, chamfered lid, coloured from nk_color. Base at the origin")
    size = g.input("Size", "VECTOR", (0.67, 0.45, 0.55), subtype="XYZ", desc="Outer size")
    col = g.input("Color", "COLOR", (0.03, 0.03, 0.028, 1.0), desc="Plastic colour (linear)")
    with g.frame("Body and lid"):
        sz = g.separate(size)
        body = xf(g, cube(g, g.combine(sz["X"], sz["Y"], g.math("MULTIPLY", sz["Z"], 0.9))),
                  t=g.combine(0.0, 0.0, g.math("MULTIPLY", sz["Z"], 0.45)))
        lid = xf(g, cube(g, g.combine(g.math("ADD", sz["X"], 0.03), g.math("ADD", sz["Y"], 0.03),
                                      g.math("MULTIPLY", sz["Z"], 0.1))),
                 t=g.combine(0.0, 0.0, g.math("MULTIPLY", sz["Z"], 0.95)))
        out = set_mat(g, store(g, join(g, body, lid), "nk_color", col, dtype="FLOAT_COLOR"), "Glazed")
    g.output("Geometry", "GEOMETRY", out, desc="The box")
    return g.finish()


@once
def wire_panel():
    g = Graph("Garden Structures Wire Panel", description="Upright wire-mesh / trellis panel in the XZ plane: a "
              "diamond (45-degree) mesh of thin wires inside a thin frame. Base centre at the origin")
    w = g.input("Width", "FLOAT", 1.0, min=0.1, max=10.0, subtype="DISTANCE", desc="Panel width (X)")
    h = g.input("Height", "FLOAT", 0.7, min=0.1, max=5.0, subtype="DISTANCE", desc="Panel height (Z)")
    cell = g.input("Mesh", "FLOAT", 0.1, min=0.01, max=1.0, subtype="DISTANCE", desc="Diamond size")
    with g.frame("Diamond mesh: a grid rotated 45 degrees, clipped to the panel, edges swept by a wire"):
        n = g.math("ADD", g.math("CEIL", g.math("DIVIDE", g.math("MULTIPLY", g.math("MAXIMUM", w, h), 1.5), cell)), 1)
        span = g.math("MULTIPLY", g.math("MAXIMUM", w, h), 1.5)
        grid = g.node("GeometryNodeMeshGrid", **{"Size X": span, "Size Y": span, "Vertices X": n,
                                                 "Vertices Y": n})["Mesh"]
        grid = xf(g, grid, r=(0.0, 0.0, math.pi / 4))
        p = g.separate(position(g))
        out_x = g.node("FunctionNodeCompare", props={"data_type": "FLOAT", "operation": "GREATER_THAN"},
                       A=g.math("ABSOLUTE", p["X"]), B=g.math("MULTIPLY", w, 0.5))["Result"]
        out_y = g.node("FunctionNodeCompare", props={"data_type": "FLOAT", "operation": "GREATER_THAN"},
                       A=g.math("ABSOLUTE", p["Y"]), B=g.math("MULTIPLY", h, 0.5))["Result"]
        outside = g.node("FunctionNodeBooleanMath", props={"operation": "OR"}, Boolean=out_x)
        g.connect(out_y, outside.i("Boolean#1"))
        grid = g.node("GeometryNodeDeleteGeometry", props={"domain": "POINT"}, Geometry=grid,
                      Selection=outside["Boolean"])["Geometry"]
        crv = g.node("GeometryNodeMeshToCurve", Mesh=grid)["Curve"]
        wire = g.node("GeometryNodeCurveToMesh", Curve=crv, **{"Profile Curve": g.node(
            "GeometryNodeCurvePrimitiveCircle", Resolution=4, Radius=0.003)["Curve"]})["Mesh"]
        frame = g.node("GeometryNodeCurvePrimitiveQuadrilateral", Width=w, Height=h)["Curve"]
        frame = g.node("GeometryNodeCurveToMesh", Curve=frame, **{"Profile Curve": g.node(
            "GeometryNodeCurvePrimitiveCircle", Resolution=6, Radius=0.008)["Curve"]})["Mesh"]
        out = xf(g, join(g, wire, frame), t=g.combine(0.0, 0.0, g.math("MULTIPLY", h, 0.5)),
                 r=(math.pi / 2, 0.0, 0.0))
        out = set_mat(g, out, "Dark Metal")
    g.output("Geometry", "GEOMETRY", out, desc="The panel")
    return g.finish()

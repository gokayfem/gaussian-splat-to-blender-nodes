"""Garden Structures detail groups: ground debris (soil clods, pebbles, leaf litter), a leafy weed rosette and a
trailing stem with leaves. Used by the pots, the raised bed, the terrace seedlings and the steps so the rear beds
read as worked soil at several scales (real lumps that cast shadows, not noise)."""
import math

from library.shapes import leaf
from nodekit.graph import Graph, once

from garden.parts.structures_util import index, join, position, rand, set_mat, smooth, store, xf

TAU = 2.0 * math.pi
GOLDEN = 2.39996


def _scatter(g, surface, density, seed, k, dmin):
    return g.node("GeometryNodeDistributePointsOnFaces", props={"distribute_method": "POISSON"}, Mesh=surface,
                  **{"Distance Min": dmin, "Density Max": density}, Seed=g.math("ADD", seed, float(k)))["Points"]


def _lump(g, seed, k, faceted):
    ico = g.node("GeometryNodeMeshIcoSphere", Radius=1.0, Subdivisions=2)["Mesh"]
    n = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "4D"}, Vector=position(g),
               W=g.math("ADD", seed, float(k)), Scale=1.3, Detail=2.0)["Fac"]
    nrm = g.node("GeometryNodeInputNormal")["Normal"]
    ico = g.node("GeometryNodeSetPosition", Geometry=ico, Offset=g.vmath(
        "SCALE", nrm, scale=g.math("MULTIPLY", g.math("SUBTRACT", n, 0.5), 0.9))["Vector"])["Geometry"]
    return smooth(g, ico, on=not faceted)


@once
def debris():
    g = Graph("Garden Structures Debris", description="Ground debris scattered on a surface: soil clods "
              "(noise-displaced lumps, half sunk), small angular pebbles and flat dry leaves/twig bits lying in "
              "random directions, each with its own density. Per-piece nk_rand for the shaders")
    surf = g.input("Surface", "GEOMETRY", desc="Mesh to scatter on (soil, tread, terrace)")
    clod_d = g.input("Clods", "FLOAT", 60.0, min=0.0, max=2000.0, desc="Clods per square metre")
    stone_d = g.input("Pebbles", "FLOAT", 12.0, min=0.0, max=1000.0, desc="Pebbles per square metre")
    lit_d = g.input("Litter", "FLOAT", 20.0, min=0.0, max=2000.0, desc="Dry leaves/twigs per square metre")
    size = g.input("Size", "FLOAT", 0.025, min=0.002, max=0.3, subtype="DISTANCE", desc="Typical clod radius")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    with g.frame("Clods: flattened lumps, sunk a third into the surface"):
        cp = _scatter(g, surf, clod_d, seed, 1, g.math("MULTIPLY", size, 1.5))
        cp = store(g, cp, "nk_rand", rand(g, 0.0, 1.0, seed, 2))
        s = g.math("MULTIPLY", size, g.math("POWER", rand(g, 0.35, 1.0, seed, 3), 1.6))
        clod = set_mat(g, xf(g, _lump(g, seed, 4, False), t=(0.0, 0.0, -0.35), s=(1.0, 1.0, 0.6)), "Soil")
        clods = g.node("GeometryNodeInstanceOnPoints", Points=cp, Instance=clod, Scale=s,
                       Rotation=g.combine(0.0, 0.0, rand(g, 0.0, TAU, seed, 5)))["Instances"]
    with g.frame("Pebbles: faceted stones, half sunk"):
        sp = _scatter(g, surf, stone_d, seed, 11, g.math("MULTIPLY", size, 1.5))
        sp = store(g, sp, "nk_rand", rand(g, 0.0, 1.0, seed, 12))
        ss = g.math("MULTIPLY", size, rand(g, 0.4, 1.2, seed, 13))
        peb = set_mat(g, xf(g, _lump(g, seed, 14, False), t=(0.0, 0.0, -0.3), s=(1.0, 0.8, 0.55)), "Stone")
        pebs = g.node("GeometryNodeInstanceOnPoints", Points=sp, Instance=peb, Scale=ss,
                      Rotation=g.combine(0.0, 0.0, rand(g, 0.0, TAU, seed, 15)))["Instances"]
    with g.frame("Litter: small flat leaves lying on the surface"):
        lp = _scatter(g, surf, lit_d, seed, 21, 0.01)
        lp = store(g, lp, "nk_rand", rand(g, 0.0, 1.0, seed, 22))
        lf = g.group(leaf(), Length=0.045, Width=0.45, Fold=0.25, Curl=-0.1, Resolution=4)["Mesh"]
        lf = set_mat(g, xf(g, lf, t=(0.0, 0.0, 0.002)), "Litter")
        lits = g.node("GeometryNodeInstanceOnPoints", Points=lp, Instance=lf,
                      Rotation=g.combine(rand(g, -0.25, 0.25, seed, 23), rand(g, -0.25, 0.25, seed, 24),
                                         rand(g, 0.0, TAU, seed, 25)),
                      Scale=rand(g, 0.5, 1.4, seed, 26))["Instances"]
    g.output("Geometry", "GEOMETRY", join(g, clods, pebs, lits), desc="Debris instances")
    return g.finish()


@once
def broad_leaf():
    g = Graph("Garden Structures Broad Leaf", description="Organic broadleaf blade, base (petiole joint) at the "
              "origin, tip on +X, face up: a subdivided disc reshaped by a polar outline r(t) = (1 + cos t)^0.8 / 2 "
              "plus two basal lobes (heart shape) near |t| = 2.6, cupped across the midrib and curled at the tip, "
              "with wavy edges")
    ln = g.input("Length", "FLOAT", 0.08, min=0.002, max=1.0, subtype="DISTANCE", desc="Base to tip")
    wd = g.input("Width", "FLOAT", 0.85, min=0.1, max=2.0, subtype="FACTOR", desc="Width / length")
    lobe = g.input("Heart", "FLOAT", 0.25, min=0.0, max=0.6, subtype="FACTOR", desc="Size of the basal lobes")
    cup = g.input("Cup", "FLOAT", 0.25, min=-1.0, max=1.0, desc="Rise of the edges across the midrib")
    curl = g.input("Curl", "FLOAT", 0.2, min=-1.0, max=1.0, desc="Droop of the tip")
    wave = g.input("Wave", "FLOAT", 0.04, min=0.0, max=0.3, subtype="FACTOR", desc="Edge waviness")
    with g.frame("Disc to polar heart outline, then cup, curl and wavy edge"):
        disc = g.node("GeometryNodeMeshCircle", props={"fill_type": "TRIANGLE_FAN"}, Vertices=24, Radius=1.0)["Mesh"]
        disc = g.node("GeometryNodeSubdivideMesh", Mesh=disc, Level=1)["Mesh"]
        p = g.separate(position(g))
        t = g.math("ARCTAN2", p["Y"], p["X"])
        rho = g.vmath("LENGTH", position(g))["Value"]
        base = g.math("MULTIPLY", g.math("POWER", g.math("MULTIPLY", g.math("ADD", g.math("COSINE", t), 1.0), 0.5),
                                         0.8), 1.0)
        lob = g.math("MULTIPLY", lobe, g.math("EXPONENT", g.math("DIVIDE", g.math("POWER", g.math(
            "SUBTRACT", g.math("ABSOLUTE", t), 2.55), 2.0), -0.12)))
        r = g.math("ADD", base, lob)
        wv = g.math("ADD", 1.0, g.math("MULTIPLY", g.math("SINE", g.math("MULTIPLY", t, 9.0)), wave))
        x = g.math("MULTIPLY", g.math("MULTIPLY", g.math("MULTIPLY", rho, r), g.math("COSINE", t)), wv)
        y = g.math("MULTIPLY", g.math("MULTIPLY", g.math("MULTIPLY", rho, r), g.math("SINE", t)),
                   g.math("MULTIPLY", wv, wd))
        z = g.math("ADD", g.math("MULTIPLY", g.math("MULTIPLY", y, y), g.math("MULTIPLY", cup, 2.0)),
                   g.math("MULTIPLY", g.math("MULTIPLY", g.math("MAXIMUM", x, 0.0), g.math("MAXIMUM", x, 0.0)),
                          g.math("MULTIPLY", curl, -1.0)))
        out = g.node("GeometryNodeSetPosition", Geometry=disc, Position=g.vmath(
            "SCALE", g.combine(g.math("ADD", x, g.math("MULTIPLY", lobe, 0.3)), y, z), scale=ln)["Vector"])["Geometry"]
        out = smooth(g, out)
    g.output("Mesh", "GEOMETRY", out, desc="The leaf blade")
    return g.finish()


@once
def weed():
    g = Graph("Garden Structures Weed", description="Loose leafy weed: Leaves broadleaf blades (heart-shaped, "
              "cupped, curled), each on its own thin stem rising from the root at a random elevation on a "
              "golden-angle heading, with varied stem and leaf sizes; base at the origin")
    n = g.input("Leaves", "INT", 9, min=1, max=80, desc="Leaves (each on a stem)")
    ln = g.input("Leaf Length", "FLOAT", 0.07, min=0.005, max=1.0, subtype="DISTANCE", desc="Largest leaf")
    wd = g.input("Leaf Width", "FLOAT", 0.85, min=0.1, max=1.5, subtype="FACTOR", desc="Width / length")
    stem = g.input("Stem Length", "FLOAT", 0.08, min=0.0, max=1.0, subtype="DISTANCE", desc="Longest stem")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    with g.frame("Per leaf: heading, elevation, stem length -> stem tip"):
        idx = index(g)
        phi = g.math("ADD", g.math("MULTIPLY", idx, GOLDEN), rand(g, -0.5, 0.5, seed, 1, ident=idx))
        el = rand(g, 0.2, 1.15, seed, 2, ident=idx)
        sl = g.math("MULTIPLY", stem, rand(g, 0.35, 1.0, seed, 3, ident=idx))
        ce = g.math("COSINE", el)
        dirv = g.combine(g.math("MULTIPLY", ce, g.math("COSINE", phi)), g.math("MULTIPLY", ce, g.math("SINE", phi)),
                         g.math("SINE", el))
        tip = g.vmath("SCALE", dirv, scale=sl)["Vector"]
        base = g.node("GeometryNodePoints", Count=n, Position=(0.0, 0.0, 0.0))["Points"]
        tips = g.node("GeometryNodePoints", Count=n, Position=tip)["Points"]
    with g.frame("Stems along their directions; leaves at the tips, heading outwards, drooping"):
        cyl = g.node("GeometryNodeMeshCylinder", Vertices=4, Radius=0.0016, Depth=1.0)["Mesh"]
        cyl = set_mat(g, xf(g, cyl, t=(0.0, 0.0, 0.5)), "Weed Leaf")
        srot = g.node("FunctionNodeAlignRotationToVector", props={"axis": "Z"}, Vector=dirv)["Rotation"]
        stems = g.node("GeometryNodeInstanceOnPoints", Points=base, Instance=cyl, Rotation=srot,
                       Scale=g.combine(1.0, 1.0, sl))["Instances"]
        lf = g.group(broad_leaf(), Length=1.0, Width=wd, Heart=0.28, Cup=0.45, Curl=0.45, Wave=0.07)["Mesh"]
        lf = set_mat(g, lf, "Weed Leaf")
        tips = store(g, tips, "nk_rand", rand(g, 0.0, 1.0, seed, 4, ident=idx))
        rot = g.combine(rand(g, -0.6, 0.6, seed, 5, ident=idx), rand(g, -0.6, 0.5, seed, 6, ident=idx), phi)
        leaves = g.node("GeometryNodeInstanceOnPoints", Points=tips, Instance=lf, Rotation=rot,
                        Scale=g.math("MULTIPLY", ln, g.math("POWER", rand(g, 0.3, 1.0, seed, 7, ident=idx), 1.4)))["Instances"]
        out = g.node("GeometryNodeRealizeInstances", Geometry=join(g, stems, leaves))["Geometry"]
    g.output("Mesh", "GEOMETRY", out, desc="The weed")
    return g.finish()


@once
def trailing_stem():
    g = Graph("Garden Structures Trailing Stem", description="A stem that rises from soil at the origin, arcs over "
              "a rim at Reach along +X and Height above the soil, then hangs Drop below the rim; small leaves "
              "alternate along it")
    reach = g.input("Reach", "FLOAT", 0.08, min=0.0, max=2.0, subtype="DISTANCE", desc="Horizontal distance to the rim")
    hgt = g.input("Height", "FLOAT", 0.07, min=0.0, max=1.0, subtype="DISTANCE", desc="Rim height above the soil")
    drop = g.input("Drop", "FLOAT", 0.12, min=0.0, max=2.0, subtype="DISTANCE", desc="Hang below the rim")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    with g.frame("Stem path: t in 0..1, rises to the rim at t 0.5, hangs after"):
        line = g.node("GeometryNodeCurvePrimitiveLine", Start=(0.0, 0.0, 0.0), End=(1.0, 0.0, 0.0))["Curve"]
        line = g.node("GeometryNodeResampleCurve", Curve=line, Count=14)["Curve"]
        t = g.separate(position(g))["X"]
        x = g.math("MULTIPLY", reach, g.math("ADD", g.math("MULTIPLY", t, 1.6), 0.0))
        x = g.math("MINIMUM", x, g.math("ADD", reach, g.math("MULTIPLY", g.math("SUBTRACT", t, 0.6), 0.1)))
        arc = g.math("SINE", g.math("MULTIPLY", g.math("MINIMUM", t, 0.6), math.pi / 1.2))
        z = g.math("SUBTRACT", g.math("MULTIPLY", arc, g.math("ADD", hgt, 0.02)),
                   g.math("MULTIPLY", drop, g.math("POWER", g.math("MAXIMUM", g.math("SUBTRACT", t, 0.55), 0.0), 1.2)))
        wob = g.math("MULTIPLY", g.math("SINE", g.math("MULTIPLY", t, g.math("ADD", 6.0, rand(g, 0, 4, seed, 1)))),
                     0.015)
        line = g.node("GeometryNodeSetPosition", Geometry=line, Position=g.combine(x, wob, z))["Geometry"]
        stem = g.node("GeometryNodeCurveToMesh", Curve=line, **{"Profile Curve": g.node(
            "GeometryNodeCurvePrimitiveCircle", Resolution=4, Radius=0.0018)["Curve"]})["Mesh"]
        stem = set_mat(g, stem, "Plant")
    with g.frame("Alternating small leaves along the stem"):
        pts = g.node("GeometryNodeCurveToPoints", props={"mode": "EVALUATED"}, Curve=line)
        lf = set_mat(g, g.group(leaf(), Length=0.035, Width=0.7, Fold=0.3, Curl=0.2, Resolution=4)["Mesh"], "Plant")
        side = g.math("MULTIPLY", g.math("SUBTRACT", g.math("FLOORED_MODULO",
                                                            g.node("GeometryNodeInputIndex")["Index"], 2.0), 0.5),
                      3.0)
        leaves = g.node("GeometryNodeInstanceOnPoints", Points=pts["Points"], Instance=lf,
                        Rotation=g.combine(0.0, rand(g, -0.6, 0.2, seed, 2), side),
                        Scale=rand(g, 0.6, 1.2, seed, 3))["Instances"]
    g.output("Geometry", "GEOMETRY", join(g, stem, leaves), desc="Stem and leaves")
    return g.finish()

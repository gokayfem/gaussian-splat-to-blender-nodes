"""Garden tree bark flakes: broken, peeling bark plates as real geometry on the measured stems.

The close_trunk reference shows pale strips peeling off the grey-brown bark and broken plate edges that catch the
light on the silhouette. Each flake is a thin, cupped slab, base attached to the surface and tip lifted away from
it, aligned with the stem axis (nk_axis, stored by Garden Tree Bark Mesh) so the peeling runs along the fissures.
Flakes cluster along plate edges (beside fissures) of the stems below the crown, are instanced (not realized) and carry
nk_flake / nk_rand for the bark shader.
"""
import math

from nodekit.graph import Graph, once


def _named(g, name, dtype="FLOAT"):
    return g.node("GeometryNodeInputNamedAttribute", props={"data_type": dtype}, Name=name)["Attribute"]


def _store(g, geo, name, value, dtype="FLOAT", domain="POINT"):
    return g.node("GeometryNodeStoreNamedAttribute", props={"data_type": dtype, "domain": domain},
                  Geometry=geo, Name=name, Value=value)["Geometry"]


def _rand(g, lo, hi, seed, dtype="FLOAT"):
    return g.node("FunctionNodeRandomValue", props={"data_type": dtype}, Min=lo, Max=hi, Seed=seed)["Value"]


def _cmp(g, a, b, op):
    return g.node("FunctionNodeCompare", props={"data_type": "FLOAT", "operation": op}, A=a, B=b)["Result"]


def _and(g, a, b):
    n = g.node("FunctionNodeBooleanMath", props={"operation": "AND"})
    g.connect(a, n.b.inputs[0])
    g.connect(b, n.b.inputs[1])
    return n["Boolean"]


@once
def flake_card():
    g = Graph("Garden Tree Bark Flake Card", description="One unit-length bark flake: a thin slab (base at "
              "origin, along +X, face +Z) cupped across and lifted towards its tip, with nk_bark coordinates so the "
              "bark shader textures it")
    width = g.input("Width", "FLOAT", 0.4, min=0.05, max=1.0, subtype="FACTOR", desc="Width / length")
    lift = g.input("Lift", "FLOAT", 0.12, min=0.0, max=1.0, desc="Tip lift away from the trunk, share of length")
    with g.frame("Grid along X, cupped across, tip lifted, given a little thickness"):
        grid = g.node("GeometryNodeMeshGrid", **{"Size X": 1.0, "Size Y": 1.0, "Vertices X": 6, "Vertices Y": 3})
        p = g.separate(g.node("GeometryNodeInputPosition"))
        u = g.math("ADD", p["X"], 0.5)
        y = g.math("MULTIPLY", p["Y"], width)
        z = g.math("SUBTRACT", g.math("MULTIPLY", g.math("MULTIPLY", u, u), lift),
                   g.math("MULTIPLY", g.math("MULTIPLY", y, y), 0.6))
        card = g.node("GeometryNodeSetPosition", Geometry=grid["Mesh"], Position=g.combine(u, y, z))["Geometry"]
        card = g.node("GeometryNodeExtrudeMesh", props={"mode": "FACES"}, Mesh=card, **{"Offset Scale": 0.035,
                                                                                         "Individual": False})
        card = _store(g, card["Mesh"], "nk_bark", g.vmath("SCALE", g.node("GeometryNodeInputPosition"),
                                                        scale=0.05)["Vector"], dtype="FLOAT_VECTOR")
        card = g.node("GeometryNodeSetShadeSmooth", Geometry=card)["Geometry"]
    g.output("Flake", "GEOMETRY", card, desc="Flake mesh")
    return g.finish()


@once
def flakes():
    g = Graph("Garden Tree Bark Flakes", description="Broken bark flakes on the stem plates: points on the bark "
              "mesh (plates only, below the crown base, not on thin twigs), each a cupped slab aligned with the stem "
              "axis, tip lifted off the surface; instanced, tagged nk_flake and nk_rand for the bark shader")
    bark = g.input("Bark Mesh", "GEOMETRY", desc="Stem bark mesh with nk_fissure, nk_axis and nk_r")
    seed = g.input("Seed", "INT", 7, min=0, max=10000, desc="Random seed")
    dens = g.input("Density", "FLOAT", 1400.0, min=0.0, max=2000.0, desc="Flakes per square metre of plate")
    size = g.input("Size", "FLOAT", 0.03, min=0.005, max=0.2, subtype="DISTANCE", desc="Typical flake length")
    lift = g.input("Lift", "FLOAT", 0.1, min=0.0, max=1.0, desc="Tip lift as a share of flake length")
    top = g.input("Top", "FLOAT", 2.4, min=0.0, max=10.0, subtype="DISTANCE", desc="No flakes above this height")
    mat = g.input("Material", "MATERIAL", desc="Bark material")
    with g.frame("Where: plate edges (beside fissures), in clusters, on stems thicker than 4 cm, soil to Top"):
        z = g.separate(g.node("GeometryNodeInputPosition"))["Z"]
        fz = _named(g, "nk_fissure")
        edge = _and(g, _cmp(g, fz, 0.08, "GREATER_THAN"), _cmp(g, fz, 0.7, "LESS_THAN"))
        clus = _cmp(g, g.node("ShaderNodeTexNoise", Vector=g.node("GeometryNodeInputPosition")["Position"],
                               Scale=7.0, Detail=2.0)["Fac"], 0.47, "GREATER_THAN")
        sel = _and(g, _and(g, _and(g, edge, clus), _cmp(g, z, 0.14, "GREATER_THAN")),
                   _and(g, _cmp(g, z, top, "LESS_THAN"), _cmp(g, _named(g, "nk_r"), 0.04, "GREATER_THAN")))
        pts = g.node("GeometryNodeDistributePointsOnFaces", props={"distribute_method": "RANDOM"}, Mesh=bark,
                     Selection=sel, Density=dens, Seed=seed)
        axis = _named(g, "nk_axis", "FLOAT_VECTOR")
    with g.frame("Orientation: face along the surface normal, length along the stem axis, slight random turn"):
        rot = g.node("FunctionNodeAlignRotationToVector", props={"axis": "X", "pivot_axis": "Z"},
                     Rotation=pts["Rotation"], Vector=axis)["Rotation"]
        turn = g.combine(0.0, 0.0, _rand(g, -0.18, 0.18, g.math("ADD", seed, 1)))
        rot = g.node("FunctionNodeRotateRotation", props={"rotation_space": "LOCAL"}, Rotation=rot,
                     **{"Rotate By": g.node("FunctionNodeEulerToRotation", Euler=turn)["Rotation"]})["Rotation"]
        flip = g.math("MULTIPLY", g.math("FLOOR", _rand(g, 0.0, 2.0, g.math("ADD", seed, 2))), math.pi)
        rot = g.node("FunctionNodeRotateRotation", props={"rotation_space": "LOCAL"}, Rotation=rot,
                     **{"Rotate By": g.node("FunctionNodeEulerToRotation",
                                            Euler=g.combine(0.0, 0.0, flip))["Rotation"]})["Rotation"]
    with g.frame("Flakes: random length and width, sunk 1 mm into the bark, tagged for the shader"):
        card = g.group(flake_card(), Width=_rand(g, 0.15, 0.4, g.math("ADD", seed, 3)), Lift=lift)["Flake"]
        card = g.node("GeometryNodeSetMaterial", Geometry=card, Material=mat)["Geometry"]
        r4 = _rand(g, 0.0, 1.0, g.math("ADD", seed, 4))
        s = g.math("MULTIPLY", size, g.math("MULTIPLY_ADD", g.math("MULTIPLY", r4, r4), 2.2, 0.35),
                   label="mostly short, a few long")
        pos = g.vmath("SUBTRACT", g.node("GeometryNodeInputPosition")["Position"],
                      g.vmath("SCALE", pts["Normal"], scale=0.001)["Vector"])["Vector"]
        p2 = g.node("GeometryNodeSetPosition", Geometry=pts["Points"], Position=pos)["Geometry"]
        inst = g.node("GeometryNodeInstanceOnPoints", Points=p2, Instance=card, Rotation=rot,
                      Scale=g.combine(s, s, s))["Instances"]
        inst = _store(g, inst, "nk_flake", 1.0, domain="INSTANCE")
        inst = _store(g, inst, "nk_rand", _rand(g, 0.0, 1.0, g.math("ADD", seed, 5)), domain="INSTANCE")
    g.output("Flakes", "GEOMETRY", inst, desc="Bark flake instances")
    return g.finish()

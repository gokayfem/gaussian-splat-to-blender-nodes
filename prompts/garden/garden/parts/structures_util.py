"""Small node idioms shared by the structures builders (python helpers, not node groups)."""
import math

import bpy

GARDEN_PREFIX = "Garden Structures "


def mat(name):
    """Material data-block by its short name (materials() must have run)."""
    return bpy.data.materials[GARDEN_PREFIX + name]


def join(g, *geos):
    j = g.node("GeometryNodeJoinGeometry")
    for x in reversed([x for x in geos if x is not None]):
        g.connect(x, j.i("Geometry"))
    return j["Geometry"]


def xf(g, geo, t=(0, 0, 0), r=(0, 0, 0), s=(1, 1, 1)):
    return g.node("GeometryNodeTransform", Geometry=geo, Translation=t, Rotation=r, Scale=s)["Geometry"]


def set_mat(g, geo, name, sel=None):
    n = g.node("GeometryNodeSetMaterial", Geometry=geo, Material=mat(name))
    if sel is not None:
        g.connect(sel, n.i("Selection"))
    return n["Geometry"]


def smooth(g, geo, on=True):
    return g.node("GeometryNodeSetShadeSmooth", Mesh=geo, **{"Shade Smooth": on})["Mesh"]


def store(g, geo, name, value, dtype="FLOAT", domain="POINT"):
    return g.node("GeometryNodeStoreNamedAttribute", props={"data_type": dtype, "domain": domain},
                  Geometry=geo, Name=name, Value=value)["Geometry"]


def rand(g, lo, hi, seed, k, dtype="FLOAT", ident=None):
    n = g.node("FunctionNodeRandomValue", props={"data_type": dtype}, Min=lo, Max=hi,
               Seed=g.math("ADD", seed, float(k)))
    if ident is not None:
        g.connect(ident, n.i("ID"))
    return n["Value"]


def cmp(g, op, a, b):
    return g.node("FunctionNodeCompare", props={"data_type": "FLOAT", "operation": op}, A=a, B=b)["Result"]


def index(g):
    return g.node("GeometryNodeInputIndex")["Index"]


def position(g):
    return g.node("GeometryNodeInputPosition")["Position"]


def cube(g, size):
    return g.node("GeometryNodeMeshCube", Size=size)["Mesh"]


def chain(g, x, *ops):
    """M(g, x, ("MULTIPLY", 2), ("ADD", 1)) style math chain."""
    for op, v in ops:
        x = g.math(op, x, v)
    return x


def garden_to_world(a, b, deg):
    """Garden-aligned (a along the beds, b across) -> world XY."""
    t = math.radians(deg)
    return a * math.cos(t) - b * math.sin(t), a * math.sin(t) + b * math.cos(t)

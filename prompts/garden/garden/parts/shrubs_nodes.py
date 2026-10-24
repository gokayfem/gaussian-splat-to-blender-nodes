"""Small node idioms shared by the shrub groups (python helpers, not node groups)."""
import math

TAU = 2.0 * math.pi
KINDS = {"broadleaf": 0, "bright": 1, "strap": 2, "sparse": 3, "low": 4, "herb": 5}


def join(g, *geos):
    j = g.node("GeometryNodeJoinGeometry")
    for x in reversed(geos):        # the multi-input socket stacks the newest link first
        g.connect(x, j.i("Geometry"))
    return j["Geometry"]


def store(g, geo, name, value, dtype="FLOAT", domain="POINT", sel=None):
    n = g.node("GeometryNodeStoreNamedAttribute", props={"data_type": dtype, "domain": domain},
               Geometry=geo, Name=name, Value=value)
    if sel is not None:
        g.connect(sel, n.i("Selection"))
    return n["Geometry"]


def attr(g, name, dtype="FLOAT"):
    return g.node("GeometryNodeInputNamedAttribute", props={"data_type": dtype}, Name=name)["Attribute"]


def rand(g, lo, hi, seed, k, dtype="FLOAT", ident=None):
    n = g.node("FunctionNodeRandomValue", props={"data_type": dtype}, Min=lo, Max=hi,
               Seed=g.math("ADD", seed, float(k)))
    if ident is not None:
        g.connect(ident, n.i("ID"))
    return n["Value"]


def cmp(g, op, a, b, dtype="FLOAT"):
    return g.node("FunctionNodeCompare", props={"data_type": dtype, "operation": op}, A=a, B=b)["Result"]


def boolean(g, op, a, b=None):
    n = g.node("FunctionNodeBooleanMath", props={"operation": op}, Boolean=a)
    if b is not None:
        g.connect(b, n.i("Boolean#1"))
    return n["Boolean"]


def kind_is(g, *names):
    """Selection: the sampled piece kind (sh_kind) is one of ``names``."""
    k = attr(g, "sh_kind", "INT")
    sel = None
    for nm in names:
        s = cmp(g, "EQUAL", k, KINDS[nm], dtype="INT")
        sel = s if sel is None else boolean(g, "OR", sel, s)
    return sel


def index_switch(g, dtype, values, index, label=None):
    """An Index Switch holding one constant per piece (fitted data lives in the node, editable in the UI)."""
    n = g.node("GeometryNodeIndexSwitch", label=label, props={"data_type": dtype})
    items = n.b.index_switch_items
    while len(items) < len(values):
        items.new()
    for i, v in enumerate(values):
        n.b.inputs[i + 1].default_value = v
    g.connect(index, n.i("Index"))
    return n["Output"]


def xf(g, geo, t=(0, 0, 0), r=(0, 0, 0), s=(1, 1, 1)):
    return g.node("GeometryNodeTransform", Geometry=geo, Translation=t, Rotation=r, Scale=s)["Geometry"]


def smooth(g, geo, on=True):
    return g.node("GeometryNodeSetShadeSmooth", Mesh=geo, **{"Shade Smooth": on})["Mesh"]


def set_mat(g, geo, mat):
    return g.node("GeometryNodeSetMaterial", Geometry=geo, Material=mat)["Geometry"]


def wavy(g, mesh, amp=0.06, freq=26.0):
    """Edge waviness on a unit leaf (tip +X): z += amp |y| sin(freq x), strongest at the margins."""
    p = g.separate(g.node("GeometryNodeInputPosition"))
    dz = g.math("MULTIPLY", g.math("MULTIPLY", g.math("ABSOLUTE", p["Y"]), amp),
                g.math("SINE", g.math("MULTIPLY", p["X"], freq)))
    return g.node("GeometryNodeSetPosition", Geometry=mesh, Offset=g.combine(0.0, 0.0, dz))["Geometry"]


def cup_twist(g, mesh, cup=0.9, twist=0.25):
    """Curved cross-section and a slight twist on a unit leaf (tip +X): z += cup y^2 + twist x y."""
    p = g.separate(g.node("GeometryNodeInputPosition"))
    dz = g.math("ADD", g.math("MULTIPLY", g.math("MULTIPLY", p["Y"], p["Y"]), cup),
                g.math("MULTIPLY", g.math("MULTIPLY", p["X"], p["Y"]), twist))
    return g.node("GeometryNodeSetPosition", Geometry=mesh, Offset=g.combine(0.0, 0.0, dz))["Geometry"]

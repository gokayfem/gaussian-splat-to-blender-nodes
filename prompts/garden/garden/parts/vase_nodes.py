"""Small node idioms shared by the vase builders (Python helpers, not node groups)."""
import math

from garden.util import srgb_to_linear

TAU = 2.0 * math.pi


def join(g, *geos):
    j = g.node("GeometryNodeJoinGeometry")
    for x in reversed(geos):  # the multi-input socket stacks the newest link first
        g.connect(x, j.i("Geometry"))
    return j["Geometry"]


def xf(g, geo, t=(0, 0, 0), r=(0, 0, 0), s=(1, 1, 1)):
    return g.node("GeometryNodeTransform", Geometry=geo, Translation=t, Rotation=r, Scale=s)["Geometry"]


def store(g, geo, name, value, dtype="FLOAT", domain="POINT"):
    return g.node("GeometryNodeStoreNamedAttribute", props={"data_type": dtype, "domain": domain},
                  Geometry=geo, Name=name, Value=value)["Geometry"]


def rand(g, lo, hi, seed, k, ident=None):
    """Random float per element; ``k`` offsets the seed so decisions stay independent."""
    n = g.node("FunctionNodeRandomValue", props={"data_type": "FLOAT"}, Min=lo, Max=hi,
               Seed=g.math("ADD", seed, float(k)))
    if ident is not None:
        g.connect(ident, n.i("ID"))
    return n["Value"]


def smooth(g, geo, on=True):
    return g.node("GeometryNodeSetShadeSmooth", Mesh=geo, **{"Shade Smooth": on})["Mesh"]


def colour(rgb):
    """sRGB 0-255 triple -> linear RGBA for a colour socket default."""
    return srgb_to_linear(rgb)


def float_curve(g, factor_value, points, label):
    """Float Curve node mapping ``factor_value`` through the (x, y) control points (fitted profile data)."""
    n = g.node("ShaderNodeFloatCurve", label, Value=factor_value)
    mp = n.b.mapping
    mp.use_clip = False
    curve = mp.curves[0]
    pts = sorted(points)
    curve.points[0].location = pts[0]
    curve.points[1].location = pts[-1]
    for x, y in pts[1:-1]:
        curve.points.new(x, y)
    for p in curve.points:
        p.handle_type = "AUTO_CLAMPED"
    mp.update()
    return n["Value"]


def orient(g, direction, normal):
    """Rotation whose +X points along ``direction`` and whose +Z leans to ``normal`` (pivoting about X)."""
    r = g.node("FunctionNodeAlignRotationToVector", props={"axis": "X", "pivot_axis": "AUTO"}, Vector=direction)
    r = g.node("FunctionNodeAlignRotationToVector", props={"axis": "Z", "pivot_axis": "X"},
               Rotation=r["Rotation"], Vector=normal)
    return r["Rotation"]


def tube(g, curve, radius, resolution=6):
    """Round tube along a curve (stems, petioles)."""
    prof = g.node("GeometryNodeCurvePrimitiveCircle", Resolution=resolution, Radius=radius)["Curve"]
    return g.node("GeometryNodeCurveToMesh", Curve=curve, **{"Profile Curve": prof, "Fill Caps": True})["Mesh"]


def named(g, name, dtype="FLOAT"):
    return g.node("GeometryNodeInputNamedAttribute", props={"data_type": dtype}, Name=name)["Attribute"]

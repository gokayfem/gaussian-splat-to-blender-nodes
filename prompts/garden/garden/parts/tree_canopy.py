"""Garden tree crown: branches from the upper stems, twigs on the branches, instanced leaves on both.

The scan has no splats above ~2.7 m (capture ceiling), so the crown is generated inside an assumed ellipsoid
envelope (data/params/tree.json crown.centre / crown.radii) whose lower part matches the measured foliage
(from ~1.9 m). Branch length shrinks towards the envelope surface so the crown keeps that silhouette.
"""
from nodekit.graph import Graph, once

from garden.util import load_params
from library.shapes import leaf


def _rand(g, lo, hi, seed, dtype="FLOAT"):
    return g.node("FunctionNodeRandomValue", props={"data_type": dtype}, Min=lo, Max=hi, Seed=seed)["Value"]


def _named(g, name, dtype="FLOAT"):
    return g.node("GeometryNodeInputNamedAttribute", props={"data_type": dtype}, Name=name)["Attribute"]


def _store(g, geo, name, value, dtype="FLOAT", domain="POINT"):
    return g.node("GeometryNodeStoreNamedAttribute", props={"data_type": dtype, "domain": domain},
                  Geometry=geo, Name=name, Value=value)["Geometry"]


def _and(g, a, b):
    n = g.node("FunctionNodeBooleanMath", props={"operation": "AND"})
    g.connect(a, n.b.inputs[0])
    g.connect(b, n.b.inputs[1])
    return n["Boolean"]


def _unit(g, v):
    return g.vmath("NORMALIZE", v)["Vector"]


def _shoots(g, points, sel, direction, length, count):
    """A straight curve of `count` points from every selected point along `direction`, `length` long."""
    line = g.node("GeometryNodeCurvePrimitiveLine", Start=(0, 0, 0), End=(1, 0, 0))["Curve"]
    line = g.node("GeometryNodeResampleCurve", Curve=line, Mode="Count", Count=count)["Curve"]
    rot = g.node("FunctionNodeAlignRotationToVector", props={"axis": "X"}, Vector=direction)["Rotation"]
    inst = g.node("GeometryNodeInstanceOnPoints", Points=points, Selection=sel, Instance=line, Rotation=rot,
                  Scale=length)["Instances"]
    inst = _store(g, inst, "nk_len", length, domain="INSTANCE")
    return g.node("GeometryNodeRealizeInstances", Geometry=inst)["Geometry"]


@once
def leaf_card():
    g = Graph("Garden Tree Leaf Card", description="One unit-length leaf (NK Leaf, base at origin, tip +X) "
              "with leaf-space coordinates nk_leafuv (x 0..1 base to tip, y -1..1 across) and the leaf material")
    width = g.input("Width", "FLOAT", 0.45, min=0.1, max=1.0, subtype="FACTOR", desc="Width / length")
    mat = g.input("Material", "MATERIAL", desc="Leaf material")
    with g.frame("Blade and its leaf-space coordinates"):
        blade = g.group(leaf(), Length=1.0, Width=width, **{"Widest At": 0.42, "Fold": 0.25, "Curl": 0.12,
                                                            "Resolution": 6})["Mesh"]
        p = g.separate(g.node("GeometryNodeInputPosition"))
        uv = g.combine(p["X"], g.math("DIVIDE", p["Y"], g.math("MULTIPLY", width, 0.5)), 0.0)
        blade = _store(g, blade, "nk_leafuv", uv, dtype="FLOAT_VECTOR")
        blade = g.node("GeometryNodeSetMaterial", Geometry=blade, Material=mat)["Geometry"]
    g.output("Leaf", "GEOMETRY", blade, desc="Leaf mesh")
    return g.finish()




@once
def crown():
    cr = load_params("tree").get("crown", {})
    cx, cy, cz = cr.get("centre", [-0.15, -2.6, 3.35])
    rx, ry, rz = cr.get("radii", [1.7, 1.5, 1.15])
    base_z = float(cr.get("lower_z_measured", 1.93))
    g = Graph("Garden Tree Crown", description="Branches sprouting from the upper stems towards the outside of "
              "an ellipsoid crown envelope (shorter near its surface), drooping twigs on them, and NK Leaf "
              "instances along twigs and outer branches. Woody curves carry nk_r / nk_along for the bark mesh")
    stems = g.input("Stems", "GEOMETRY", desc="Stem curves with nk_r and nk_root (from Garden Tree Skeleton)")
    seed = g.input("Seed", "INT", 7, min=0, max=10000, desc="Random seed")
    bdens = g.input("Branch Density", "FLOAT", 0.75, min=0.0, max=1.0, subtype="FACTOR",
                    desc="Probability that a stem point above the crown base sprouts a branch")
    ldens = g.input("Leaf Density", "FLOAT", 1.0, min=0.0, max=3.0, desc="Leaves per twig length (1 = fitted)")
    lsize = g.input("Leaf Size", "FLOAT", 0.075, min=0.02, max=0.2, subtype="DISTANCE", desc="Leaf length")
    leafm = g.input("Leaf", "MATERIAL", desc="Leaf material")
    with g.frame(f"Branch origins: stem points above z {base_z:.2f} (crown base), not roots, random share"):
        sp = g.node("GeometryNodeCurveToPoints", props={"mode": "LENGTH"}, Curve=stems, Length=0.05)
        pos = g.node("GeometryNodeInputPosition")["Position"]
        above = g.node("FunctionNodeCompare", props={"data_type": "FLOAT", "operation": "GREATER_THAN"},
                       A=g.separate(pos)["Z"], B=base_z)["Result"]
        keep = g.node("FunctionNodeRandomValue", props={"data_type": "BOOLEAN"}, Probability=bdens,
                      Seed=seed)["Value"]
        notroot = g.node("FunctionNodeBooleanMath", props={"operation": "NOT"},
                         Boolean=_named(g, "nk_root", "BOOLEAN"))["Boolean"]
        bsel = _and(g, _and(g, above, keep), notroot)
    with g.frame(f"Branch direction: out from the crown axis ({cx:.2f}, {cy:.2f}), upward, jittered; "
                 f"length shrinks towards the ellipsoid surface (radii {rx}, {ry}, {rz})"):
        rel = g.vmath("SUBTRACT", pos, (cx, cy, cz))["Vector"]
        rs = g.separate(rel)
        out = _unit(g, g.combine(rs["X"], rs["Y"], 0.0))
        d = g.vmath("ADD", g.vmath("ADD", out, (0.0, 0.0, 0.6))["Vector"],
                    _rand(g, (-0.7, -0.7, -0.3), (0.7, 0.7, 0.5), g.math("ADD", seed, 11), "FLOAT_VECTOR"))
        bdir = _unit(g, g.vmath("ADD", d["Vector"], g.vmath("SCALE", sp["Tangent"], scale=0.3)["Vector"]))
        e = g.vmath("LENGTH", g.vmath("DIVIDE", rel, (rx, ry, rz))["Vector"])["Value"]
        blen = g.math("MULTIPLY", g.math("MULTIPLY", 1.8, _rand(g, 0.5, 1.0, g.math("ADD", seed, 12))),
                      g.math("MAXIMUM", g.math("SUBTRACT", 1.15, e), 0.25))
    with g.frame("Branches: curves that droop towards their tips, radius tapering from the stem's"):
        br = _shoots(g, sp["Points"], bsel, bdir, blen, 10)
        f = g.node("GeometryNodeSplineParameter")["Factor"]
        sag = g.math("MULTIPLY", g.math("MULTIPLY", g.math("MULTIPLY", f, f), _named(g, "nk_len")), -0.22)
        wob = g.vmath("SUBTRACT", g.node("ShaderNodeTexNoise", props={"noise_dimensions": "3D"},
                                         Scale=2.5)["Color"], (0.5, 0.5, 0.5))["Vector"]
        off = g.vmath("ADD", g.combine(0.0, 0.0, sag),
                      g.vmath("SCALE", wob, scale=g.math("MULTIPLY", f, 0.25))["Vector"])["Vector"]
        br = g.node("GeometryNodeSetPosition", Geometry=br, Offset=off)["Geometry"]
        r0 = g.math("MINIMUM", g.math("MULTIPLY", _named(g, "nk_r"), 0.45), 0.035)
        br = _store(g, br, "nk_r", g.math("MAXIMUM", g.math("MULTIPLY", r0, g.math(
            "SUBTRACT", 1.0, g.math("MULTIPLY", f, 0.8))), 0.004))
        br = _store(g, br, "nk_f", f)
    with g.frame("Twigs: short shoots along the outer 85 % of each branch, jittered about its direction"):
        tp = g.node("GeometryNodeCurveToPoints", props={"mode": "LENGTH"}, Curve=br, Length=0.035)
        tsel = _and(g, g.node("FunctionNodeCompare", props={"data_type": "FLOAT", "operation": "GREATER_THAN"},
                               A=_named(g, "nk_f"), B=0.15)["Result"],
                    g.node("FunctionNodeRandomValue", props={"data_type": "BOOLEAN"}, Probability=0.85,
                           Seed=g.math("ADD", seed, 21))["Value"])
        tdir = _unit(g, g.vmath("ADD", g.vmath("ADD", tp["Tangent"], (0.0, 0.0, 0.1))["Vector"],
                                _rand(g, (-1.0, -1.0, -0.6), (1.0, 1.0, 0.8), g.math("ADD", seed, 22),
                                      "FLOAT_VECTOR"))["Vector"])
        tw = _shoots(g, tp["Points"], tsel, tdir, _rand(g, 0.15, 0.35, g.math("ADD", seed, 23)), 4)
        tw = _store(g, tw, "nk_r", g.math("MULTIPLY", 0.006, g.math(
            "SUBTRACT", 1.0, g.math("MULTIPLY", g.node("GeometryNodeSplineParameter")["Factor"], 0.6))))
    with g.frame("Wood: branches + twigs with arc length for the bark mapping"):
        wood = g.node("GeometryNodeJoinGeometry", Geometry=br)
        g.connect(tw, wood.i("Geometry"))
        wood = _store(g, wood, "nk_along", g.node("GeometryNodeSplineParameter")["Length"])
    with g.frame("Leaf points along twigs and outer branches; spacing from Leaf Density"):
        spacing = g.math("DIVIDE", 0.016, g.math("MAXIMUM", ldens, 0.05))
        lp1 = g.node("GeometryNodeCurveToPoints", props={"mode": "LENGTH"}, Curve=tw, Length=spacing)
        outer = g.node("GeometryNodeSeparateGeometry", props={"domain": "POINT"}, Geometry=br, Selection=g.node(
            "FunctionNodeCompare", props={"data_type": "FLOAT", "operation": "GREATER_THAN"},
            A=g.node("GeometryNodeSplineParameter")["Factor"], B=0.55)["Result"])["Selection"]
        lp2 = g.node("GeometryNodeCurveToPoints", props={"mode": "LENGTH"}, Curve=outer,
                     Length=g.math("MULTIPLY", spacing, 1.5))
        tang = _named(g, "nk_tan", "FLOAT_VECTOR")
    with g.frame("Leaves: NK Leaf instances angled off the shoot, face roughly up, random size, nk_rand"):
        lp1p = _store(g, lp1["Points"], "nk_tan", lp1["Tangent"], dtype="FLOAT_VECTOR")
        lp2p = _store(g, lp2["Points"], "nk_tan", lp2["Tangent"], dtype="FLOAT_VECTOR")
        lpts = g.node("GeometryNodeJoinGeometry", Geometry=lp1p)
        g.connect(lp2p, lpts.i("Geometry"))
        ldir = _unit(g, g.vmath("ADD", g.vmath("ADD", tang, (0.0, 0.0, -0.35))["Vector"],
                                _rand(g, (-1.1, -1.1, -0.5), (1.1, 1.1, 0.5), g.math("ADD", seed, 31),
                                      "FLOAT_VECTOR"))["Vector"])
        rot = g.node("FunctionNodeAlignRotationToVector", props={"axis": "X"}, Vector=ldir)["Rotation"]
        up = _unit(g, g.vmath("ADD", (0.0, 0.0, 1.0), _rand(g, (-0.8, -0.8, 0.0), (0.8, 0.8, 0.0),
                                                            g.math("ADD", seed, 32), "FLOAT_VECTOR"))["Vector"])
        rot = g.node("FunctionNodeAlignRotationToVector", props={"axis": "Z", "pivot_axis": "X"}, Rotation=rot,
                     Vector=up)["Rotation"]
        card = g.group(leaf_card(), Material=leafm)["Leaf"]
        lv = g.node("GeometryNodeInstanceOnPoints", Points=lpts, Instance=card, Rotation=rot,
                    Scale=g.math("MULTIPLY", lsize, _rand(g, 0.7, 1.25, g.math("ADD", seed, 33))))["Instances"]
        lv = _store(g, lv, "nk_rand", _rand(g, 0.0, 1.0, g.math("ADD", seed, 34)), domain="INSTANCE")
    g.output("Wood", "GEOMETRY", wood, desc="Branch and twig curves (nk_r, nk_along)")
    g.output("Leaves", "GEOMETRY", lv, desc="Leaf instances")
    return g.finish()

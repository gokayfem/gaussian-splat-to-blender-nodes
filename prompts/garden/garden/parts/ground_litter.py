"""Organic matter on the paving, placed by spatial context rather than evenly:

- joint litter: brown needles, decomposed leaf fragments and the odd twig packed into *some* joint stretches
  (a clump field), mostly at the -y side, round the table foot and toward the lawn;
- moss cushions only in damp pockets (outer slabs, -y side);
- small grass clumps in a few selected cracks;
- surface litter: needle/leaf mats lying on the slabs in patches (round the foot beams, -y half, near the lawn).
"""
import math

import bpy
from nodekit.graph import Graph, once
from library.shapes import grass_tuft

from garden.parts.ground_fields import P, ground_height, paving_boundary, smooth01


def mat(name):
    return bpy.data.materials[name]


def _rand(g, idx, lo, hi, seed, k):
    return g.node("FunctionNodeRandomValue", props={"data_type": "FLOAT"}, Min=lo, Max=hi, ID=idx,
                  Seed=g.math("ADD", seed, float(k)))["Value"]


@once
def leaf_fragment():
    g = Graph("Garden Ground Leaf Fragment", description="A decomposed leaf scrap: an irregular 9-sided disc, "
                                                         "elongated and curled up along its long axis")
    size = g.input("Size", "FLOAT", 0.012, min=0.001, max=0.2, subtype="DISTANCE", desc="Fragment radius")
    curl = g.input("Curl", "FLOAT", 0.6, min=0.0, max=3.0, desc="How strongly the sides curl up")
    with g.frame("Irregular disc: circle with noisy radius, elongated, sides curled up"):
        disc = g.node("GeometryNodeMeshCircle", props={"fill_type": "TRIANGLE_FAN"}, Vertices=9, Radius=1.0)
        pos = g.node("GeometryNodeInputPosition")
        n = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "3D"}, Vector=g.vmath("SCALE", pos, scale=2.3),
                   Scale=1.0, Detail=1.0)
        k = g.map_range(n["Fac"], 0.3, 0.7, 0.5, 1.15)["Result"]
        xyz = g.separate(pos)
        y = g.math("MULTIPLY", g.math("MULTIPLY", xyz["Y"], k), 0.55)
        z = g.math("MULTIPLY", g.math("MULTIPLY", y, y), curl)
        newp = g.vmath("SCALE", g.combine(g.math("MULTIPLY", xyz["X"], k), y, z), scale=size)
        out = g.node("GeometryNodeSetPosition", Geometry=disc["Mesh"], Position=newp)
    g.output("Mesh", "GEOMETRY", out, desc="Leaf fragment mesh")
    return g.finish()


@once
def needle():
    g = Graph("Garden Ground Needle", description="A dead conifer needle: a thin tube along +X, bowed sideways and "
                                                  "slightly up")
    length = g.input("Length", "FLOAT", 0.022, min=0.002, max=0.2, subtype="DISTANCE", desc="Needle length")
    bend = g.input("Bend", "FLOAT", 0.15, min=-1.0, max=1.0, desc="Sideways bow as a share of the length")
    with g.frame("Bowed centre line: 6 points, y and z follow sin(pi t)"):
        line = g.node("GeometryNodeCurvePrimitiveLine", End=g.combine(length, 0.0, 0.0))
        line = g.node("GeometryNodeResampleCurve", Curve=line, Mode="Count", Count=6)
        t = g.node("GeometryNodeSplineParameter")["Factor"]
        arc = g.math("MULTIPLY", g.math("SINE", g.math("MULTIPLY", t, math.pi)), g.math("MULTIPLY", bend, length))
        line = g.node("GeometryNodeSetPosition", Geometry=line, Offset=g.combine(0.0, arc, g.math("MULTIPLY", arc, 0.4)))
    with g.frame("Sweep a 3-sided 0.7 mm profile"):
        prof = g.node("GeometryNodeCurvePrimitiveCircle", Resolution=3, Radius=0.00055)
        mesh = g.node("GeometryNodeCurveToMesh", Curve=line, **{"Profile Curve": prof})
    g.output("Mesh", "GEOMETRY", mesh, desc="Needle mesh")
    return g.finish()


@once
def litter_mat():
    g = Graph("Garden Ground Litter Mat", description="A felted clump of decomposed needles and leaf: a flattened, "
                                                      "lumpy irregular cushion about 4 cm across, base at Z = 0")
    size = g.input("Size", "FLOAT", 0.02, min=0.002, max=0.3, subtype="DISTANCE", desc="Clump radius")
    with g.frame("Flattened icosphere with lumpy noise displacement"):
        ico = g.node("GeometryNodeMeshIcoSphere", Radius=1.0, Subdivisions=2)
        pos = g.node("GeometryNodeInputPosition")
        n = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "3D"}, Vector=pos, Scale=1.8, Detail=3.0)
        k = g.map_range(n["Fac"], 0.3, 0.7, 0.55, 1.2)["Result"]
        xyz = g.separate(pos)
        newp = g.combine(g.math("MULTIPLY", xyz["X"], k), g.math("MULTIPLY", g.math("MULTIPLY", xyz["Y"], k), 0.75),
                         g.math("MULTIPLY", g.math("MAXIMUM", xyz["Z"], -0.1), g.math("MULTIPLY", k, 0.12)))
        out = g.node("GeometryNodeSetPosition", Geometry=ico["Mesh"], Position=g.vmath("SCALE", newp, scale=size))
    g.output("Mesh", "GEOMETRY", out, desc="Litter clump mesh")
    return g.finish()


def litter_library(g):
    """Instance library: 0 needle, 1 moss cushion, 2 grass clump, 3 leaf fragment, 4 twig, 5 bent needle, 6 litter
    mat."""
    with g.frame("Organic pieces: needles, moss, grass clump, leaf fragment, twig, felted litter clump"):
        n_a = g.node("GeometryNodeSetMaterial", Geometry=g.group(needle(), Length=0.016, Bend=0.07)["Mesh"],
                     Material=mat("Garden Ground Litter"))
        n_b = g.node("GeometryNodeSetMaterial", Geometry=g.group(needle(), Length=0.013, Bend=-0.12)["Mesh"],
                     Material=mat("Garden Ground Litter"))
        moss = g.node("GeometryNodeMeshIcoSphere", Radius=0.011, Subdivisions=2)
        moss = g.node("GeometryNodeTransform", Geometry=moss["Mesh"], Scale=(1.4, 1.0, 0.45))
        moss = g.node("GeometryNodeSetMaterial", Geometry=moss, Material=mat("Garden Ground Moss"))
        weed = g.group(grass_tuft(), Blades=9, Height=0.06, **{"Height Min": 0.4}, Radius=0.008, Spread=0.8,
                       **{"Blade Width": 0.07}, Curl=0.4, Resolution=4, Seed=5)["Mesh"]
        weed = g.node("GeometryNodeSetMaterial", Geometry=weed, Material=mat("Garden Ground Grass"))
        leaf = g.group(leaf_fragment(), Size=0.006, Curl=0.7)["Mesh"]
        leaf = g.node("GeometryNodeSetMaterial", Geometry=leaf, Material=mat("Garden Ground Leaf Litter"))
        twig = g.group(needle(), Length=0.06, Bend=0.08)["Mesh"]
        twig = g.node("GeometryNodeTransform", Geometry=twig, Scale=(1.0, 3.5, 3.5))
        twig = g.node("GeometryNodeSetMaterial", Geometry=twig, Material=mat("Garden Ground Twig"))
        clump = g.group(litter_mat(), Size=0.014)["Mesh"]
        clump = g.node("GeometryNodeSetMaterial", Geometry=clump, Material=mat("Garden Ground Litter Mat"))
        lib = g.node("GeometryNodeJoinGeometry")
        # Join lists inputs last-linked first: link in reverse so instance k is the k-th piece above
        for geo in (clump, n_b, twig, leaf, weed, moss, n_a):
            g.connect(g.node("GeometryNodeGeometryToInstance", Geometry=geo), lib.i("Geometry"))
    return lib


def _context(g, pos):
    """Context fields at a position: south (-y half), foot (round the table foot), edge (toward the lawn)."""
    xyz = g.separate(pos)
    south = smooth01(g, xyz["Y"], 0.3, -1.2)
    rho = g.vmath("LENGTH", g.combine(xyz["X"], xyz["Y"], 0.0))["Value"]
    foot = smooth01(g, rho, 0.85, 0.3)
    edge = smooth01(g, g.group(paving_boundary(), Position=pos)["Margin"], 0.55, 0.05)
    return south, foot, edge


def _instance(g, pts, lib, idx_field, seed, k0, scale_lo=0.6, scale_hi=1.4):
    idx = g.node("GeometryNodeInputIndex")
    pts = g.node("GeometryNodeStoreNamedAttribute", props={"data_type": "FLOAT", "domain": "POINT"},
                 Geometry=pts, Name="nk_rand", Value=_rand(g, idx, 0.0, 1.0, seed, k0))["Geometry"]
    rot = g.node("FunctionNodeEulerToRotation", Euler=g.combine(
        _rand(g, idx, -0.25, 0.25, seed, k0 + 1), _rand(g, idx, -0.15, 0.15, seed, k0 + 2),
        _rand(g, idx, 0.0, 6.283, seed, k0 + 3)))
    return g.node("GeometryNodeInstanceOnPoints", Points=pts, Instance=lib, **{"Pick Instance": True},
                  **{"Instance Index": idx_field}, Rotation=rot,
                  Scale=_rand(g, idx, scale_lo, scale_hi, seed, k0 + 4))["Instances"]


def _needle_or_leaf(g, r, p_leaf, p_twig):
    """0/5 needle (two bends), 3 leaf fragment, 4 twig from a 0..1 random r."""
    nd = g.math("MULTIPLY", g.math("GREATER_THAN", g.math("FRACT", g.math("MULTIPLY", r, 13.7)), 0.5), 5.0)
    t = g.mix(g.math("GREATER_THAN", r, 1.0 - p_leaf - p_twig), nd, 3.0)["Result"]
    return g.mix(g.math("GREATER_THAN", r, 1.0 - p_twig), t, 4.0)["Result"]


def _litter_type(g, idx, seed, k0, damp, weed_rate):
    """Per point: grass clump (rare, damp), moss (damp pockets), felted clump (6%) or needles / leaf / twig."""
    r = _rand(g, idx, 0.0, 1.0, seed, k0)
    lit = _needle_or_leaf(g, r, 0.03, 0.004)
    lit = g.mix(g.math("LESS_THAN", _rand(g, idx, 0.0, 1.0, seed, k0 + 3), 0.008), lit, 6.0)["Result"]
    moss = g.math("LESS_THAN", _rand(g, idx, 0.0, 1.0, seed, k0 + 1), g.math("MULTIPLY", damp, 0.3))
    t = g.mix(moss, lit, 1.0)["Result"]
    weed = g.math("LESS_THAN", _rand(g, idx, 0.0, 1.0, seed, k0 + 2), g.math("MULTIPLY", damp, weed_rate))
    return g.mix(weed, t, 2.0)["Result"]


def joint_points(g, slab_pts):
    """Points every 5 mm along every slab outline (the joint lines)."""
    s = P["hex"]["across_flats"]
    rz = math.radians(P["hex"]["rotation_deg"] + 30.0)
    with g.frame("Joint lines: a hex outline on every slab, resampled every 5 mm"):
        hexc = g.node("GeometryNodeCurvePrimitiveCircle", Resolution=6, Radius=s / math.sqrt(3.0))
        outl = g.node("GeometryNodeInstanceOnPoints", Points=slab_pts, Instance=hexc["Curve"],
                      Rotation=g.node("FunctionNodeEulerToRotation", Euler=(0.0, 0.0, rz)))
        curves = g.node("GeometryNodeRealizeInstances", Geometry=outl["Instances"])
        curves = g.node("GeometryNodeResampleCurve", Curve=curves, Mode="Length", Length=0.005)
        jp = g.node("GeometryNodeCurveToPoints", props={"mode": "EVALUATED"}, Curve=curves)["Points"]
    return jp


def joint_litter(g, jp, seed, amount, lib):
    with g.frame("Keep points in litter-laden joint stretches (clump field x context) and damp pockets"):
        idx = g.node("GeometryNodeInputIndex")
        pos = g.node("GeometryNodeInputPosition")
        south, foot, edge = _context(g, pos)
        cl = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "2D"}, Vector=pos, Scale=5.0, Detail=4.0,
                    Roughness=0.65)
        clump = smooth01(g, cl["Fac"], 0.5, 0.64)
        ctx = g.math("MINIMUM", g.math("ADD", 0.35, g.math("MAXIMUM", south, g.math("MAXIMUM", foot, edge))), 1.0)
        dn = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "2D"}, Vector=pos, Scale=2.5, Detail=3.0)
        damp = g.math("MULTIPLY", g.math("MAXIMUM", edge, g.math("MULTIPLY", south, 0.7)),
                      smooth01(g, dn["Fac"], 0.45, 0.62))
        p_keep = g.math("MULTIPLY", g.math("ADD", g.math("MULTIPLY", clump, ctx), g.math("MULTIPLY", damp, 0.3)),
                        amount)
        keep = g.math("LESS_THAN", _rand(g, idx, 0.0, 1.0, seed, 21), g.math("MULTIPLY", p_keep, 0.6))
        jp = g.node("GeometryNodeDeleteGeometry", props={"domain": "POINT"}, Geometry=jp,
                    Selection=g.node("FunctionNodeBooleanMath", props={"operation": "NOT"}, Boolean=keep))["Geometry"]
        jp = g.node("GeometryNodeStoreNamedAttribute", props={"data_type": "FLOAT", "domain": "POINT"},
                    Geometry=jp, Name="gr_damp", Value=damp)["Geometry"]
        jit = g.combine(_rand(g, idx, -0.007, 0.007, seed, 22), _rand(g, idx, -0.007, 0.007, seed, 23), 0.0)
        hz = g.group(ground_height(), Position=pos)["Height"]
        xyz = g.separate(pos)
        jp = g.node("GeometryNodeSetPosition", Geometry=jp, Position=g.vmath("ADD", g.combine(
            xyz["X"], xyz["Y"], g.math("SUBTRACT", hz, 0.003)), jit))["Geometry"]
    with g.frame("Joint piece type by context: grass clumps in selected cracks, moss when damp, else litter"):
        idx2 = g.node("GeometryNodeInputIndex")
        damp2 = g.node("GeometryNodeInputNamedAttribute", props={"data_type": "FLOAT"}, Name="gr_damp")["Attribute"]
        t = _litter_type(g, idx2, seed, 30, damp2, 0.035)
        inst = _instance(g, jp, lib, t, seed, 24)
    return inst


def surface_litter(g, seed, amount, lib, target, jp):
    with g.frame("Surface litter: mats of needles and leaf scraps in patches (foot, -y half, lawn edge)"):
        grid = g.node("GeometryNodeMeshGrid", **{"Size X": 4.6, "Size Y": 4.6, "Vertices X": 93, "Vertices Y": 93})
        pos = g.node("GeometryNodeInputPosition")
        south, foot, edge = _context(g, pos)
        nz = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "2D"}, Vector=pos, Scale=7.0, Detail=6.0,
                    Roughness=0.7)
        patch = smooth01(g, nz["Fac"], 0.55, 0.62)
        near = smooth01(g, g.node("GeometryNodeProximity", props={"target_element": "POINTS"}, Geometry=jp,
                                  **{"Sample Position": pos})["Distance"], 0.075, 0.004)
        where = g.math("MAXIMUM", g.math("MAXIMUM", foot, g.math("MULTIPLY", south, 0.8)),
                       g.math("MAXIMUM", g.math("MULTIPLY", edge, 0.8), 0.3))
        inside = g.math("GREATER_THAN", g.group(paving_boundary(), Position=pos)["Margin"], 0.02)
        w = g.math("MULTIPLY", g.math("MULTIPLY", patch, where), g.math("MULTIPLY_ADD", g.math("MULTIPLY", g.math("MULTIPLY", near, near), near), 0.98, 0.02))
        dens = g.math("MULTIPLY", g.math("MULTIPLY", w, 600000.0), g.math("MULTIPLY", inside, amount))
        sp = g.node("GeometryNodeDistributePointsOnFaces", Mesh=grid["Mesh"], Density=dens, Seed=seed)
    with g.frame("Drop each point onto the slab below (raycast)"):
        p2 = g.node("GeometryNodeInputPosition")
        ray = g.node("GeometryNodeRaycast", **{"Target Geometry": target},
                     **{"Source Position": g.vmath("ADD", p2, (0.0, 0.0, 0.2))}, **{"Ray Direction": (0.0, 0.0, -1.0)},
                     **{"Ray Length": 0.4})
        sp = g.node("GeometryNodeDeleteGeometry", props={"domain": "POINT"}, Geometry=sp["Points"],
                    Selection=g.node("FunctionNodeBooleanMath", props={"operation": "NOT"},
                                     Boolean=ray["Is Hit"]))["Geometry"]
        sp = g.node("GeometryNodeSetPosition", Geometry=sp, Position=g.vmath("ADD", ray["Hit Position"],
                                                                            (0.0, 0.0, 0.0006)))["Geometry"]
    with g.frame("Surface pieces: needles and leaf scraps, no moss or grass"):
        idx = g.node("GeometryNodeInputIndex")
        r = _rand(g, idx, 0.0, 1.0, seed, 41)
        t = _needle_or_leaf(g, r, 0.25, 0.001)
        t = g.mix(g.math("LESS_THAN", _rand(g, idx, 0.0, 1.0, seed, 43), 0.004), t, 6.0)["Result"]
        inst = _instance(g, sp, lib, t, seed, 42)
    return inst

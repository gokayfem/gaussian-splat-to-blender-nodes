"""Hexagonal paver geometry: a prism with a rounded top edge whose rim is chipped and worn per variant.

The outline is a 96-point resampled hexagon (vertex 0 on +X, as Curve Circle and the paver shader assume), so chips
and rounding can bite into the edge as real geometry instead of shader paint.
"""
import math

from nodekit.graph import Graph, once

from garden.parts.ground_fields import smooth01

VARIANTS = 4


@once
def hex_slab():
    g = Graph("Garden Ground Hex Slab", description="One hexagonal concrete paver: a 96-point hex prism with a "
                                                    "two-step rounded top edge, chips and worn dips along the rim "
                                                    "(per Variant); top face at Z = 0")
    flats = g.input("Across Flats", "FLOAT", 0.43, min=0.05, max=2.0, subtype="DISTANCE",
                    desc="Slab width between opposite flat sides")
    thick = g.input("Thickness", "FLOAT", 0.05, min=0.005, max=0.3, subtype="DISTANCE", desc="Slab thickness")
    bevel = g.input("Bevel", "FLOAT", 0.004, min=0.0, max=0.05, subtype="DISTANCE",
                    desc="Size of the rounded top edge")
    chip = g.input("Chipping", "FLOAT", 1.0, min=0.0, max=3.0, desc="Depth and frequency of edge chips (1 = fitted)")
    var = g.input("Variant", "FLOAT", 0.0, min=0.0, max=100.0, desc="Offsets the chip pattern (one per slab variant)")
    with g.frame("Bottom face: hex outline resampled to 96 points, filled"):
        rc = g.math("DIVIDE", flats, math.sqrt(3.0))
        circ = g.node("GeometryNodeCurvePrimitiveCircle", Resolution=6, Radius=rc)
        circ = g.node("GeometryNodeResampleCurve", Curve=circ, Mode="Count", Count=96)
        base = g.node("GeometryNodeFillCurve", Curve=circ, Mode="N-gons")
    with g.frame("Prism: extrude up by the thickness, then two inward steps round the top edge"):
        e0 = g.node("GeometryNodeExtrudeMesh", Mesh=base, Offset=(0.0, 0.0, 1.0), **{"Offset Scale": thick})
        e1 = g.node("GeometryNodeExtrudeMesh", Mesh=e0["Mesh"], Selection=e0["Top"], Offset=(0.0, 0.0, 1.0),
                    **{"Offset Scale": g.math("MULTIPLY", bevel, 0.65)})
        s1 = g.node("GeometryNodeScaleElements", Geometry=e1["Mesh"], Selection=e1["Top"],
                    Scale=g.math("SUBTRACT", 1.0, g.math("DIVIDE", g.math("MULTIPLY", bevel, 0.75), rc)))
        e2 = g.node("GeometryNodeExtrudeMesh", Mesh=s1["Geometry"], Selection=e1["Top"], Offset=(0.0, 0.0, 1.0),
                    **{"Offset Scale": g.math("MULTIPLY", bevel, 0.35)})
        s2 = g.node("GeometryNodeScaleElements", Geometry=e2["Mesh"], Selection=e2["Top"],
                    Scale=g.math("SUBTRACT", 1.0, g.math("DIVIDE", g.math("MULTIPLY", bevel, 1.25), rc)))
        top_z = g.math("ADD", thick, bevel)
    with g.frame("Chips: rim vertices near the top dip down and in where a variant noise peaks"):
        pos = g.node("GeometryNodeInputPosition")
        xyz = g.separate(pos)
        upper = smooth01(g, xyz["Z"], g.math("SUBTRACT", top_z, g.math("MULTIPLY", bevel, 3.0)), top_z)
        nvec = g.vmath("ADD", g.vmath("SCALE", pos, scale=9.0)["Vector"], g.combine(var, g.math("MULTIPLY", var, 1.7),
                                                                                   0.0))
        n1 = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "3D"}, Vector=nvec, Scale=1.0, Detail=3.0,
                    Roughness=0.6)
        bite = g.math("MULTIPLY", smooth01(g, n1["Fac"], 0.56, 0.72), chip)
        n2 = g.node("ShaderNodeTexNoise", props={"noise_dimensions": "3D"}, Vector=nvec, Scale=6.0, Detail=2.0)
        bite = g.math("MULTIPLY", bite, g.map_range(n2["Fac"], 0.3, 0.7, 0.4, 1.2)["Result"])
        rho = g.vmath("LENGTH", g.combine(xyz["X"], xyz["Y"], 0.0))["Value"]
        inward = g.vmath("SCALE", g.vmath("NORMALIZE", g.combine(xyz["X"], xyz["Y"], 0.0))["Vector"],
                         scale=g.math("MULTIPLY", g.math("MULTIPLY", bite, upper), -0.0025))["Vector"]
        down = g.math("MULTIPLY", g.math("MULTIPLY", bite, upper), -0.005)
        off = g.vmath("ADD", inward, g.combine(0.0, 0.0, down))
        # triangulate while the outline is still convex so the chipped (non-planar) top cannot tear open
        tri = g.node("GeometryNodeTriangulate", Mesh=s2["Geometry"])
        geo = g.node("GeometryNodeSetPosition", Geometry=tri,
                     Selection=g.math("GREATER_THAN", rho, g.math("MULTIPLY", rc, 0.8)), Offset=off)
    with g.frame("Drop so the top face sits at Z = 0"):
        out = g.node("GeometryNodeTransform", Geometry=geo,
                     Translation=g.combine(0.0, 0.0, g.math("MULTIPLY", top_z, -1.0)))
    g.output("Mesh", "GEOMETRY", out, desc="The slab mesh (local space, top at Z = 0)")
    return g.finish()


def slab_variants(g, flats, bevel, chip, material):
    """VARIANTS chipped slabs as instances (pick with Instance on Points' Pick Instance)."""
    with g.frame(f"{VARIANTS} chipped slab variants as an instance library"):
        lib = g.node("GeometryNodeJoinGeometry")
        for k in reversed(range(VARIANTS)):
            s = g.group(hex_slab(), **{"Across Flats": flats}, Thickness=0.05, Bevel=bevel, Chipping=chip,
                        Variant=float(7 * k + 3))["Mesh"]
            s = g.node("GeometryNodeSetMaterial", Geometry=s, Material=material)
            g.connect(g.node("GeometryNodeGeometryToInstance", Geometry=s), lib.i("Geometry"))
    return lib

"""Hexagonal concrete paving around the table: chipped slab geometry on the fitted hex lattice (outer slabs settle
into the soil), context-placed organic matter (ground_litter.py) and the two round ground lights.

Lattice (spacing, rotation, origin) and the paved outline come from data/params/ground.json.
"""
import math

import bpy
from nodekit.graph import Graph, once

from garden.parts.ground_fields import P, paving_boundary, smooth01
from garden.parts.ground_litter import joint_litter, joint_points, litter_library, surface_litter
from garden.parts.ground_slab import VARIANTS, slab_variants

K = 9                       # lattice cells -K..K along each axis (covers rho < 3.5 m at 0.445 m spacing)


def mat(name):
    return bpy.data.materials[name]


def _rand(g, idx, lo, hi, seed, k, dtype="FLOAT"):
    return g.node("FunctionNodeRandomValue", props={"data_type": dtype}, Min=lo, Max=hi, ID=idx,
                  Seed=g.math("ADD", seed, float(k)))["Value"]


def _lattice_points(g, seed):
    """One point per lattice cell, at the fitted hex centre; keeps cells inside the paved outline."""
    hx = P["hex"]
    s = hx["across_flats"]
    th = math.radians(hx["rotation_deg"])
    ox, oy = hx["origin"]
    n = 2 * K + 1
    with g.frame("Hex lattice: index -> axial (q, r) -> centre, rotated by the fitted angle"):
        pts = g.node("GeometryNodePoints", Count=n * n)
        idx = g.node("GeometryNodeInputIndex")
        q = g.math("SUBTRACT", g.math("FLOORED_MODULO", idx, float(n)), float(K))
        r = g.math("SUBTRACT", g.math("FLOOR", g.math("DIVIDE", idx, float(n))), float(K))
        u = g.math("MULTIPLY", g.math("MULTIPLY_ADD", r, 0.5, q), s)
        v = g.math("MULTIPLY", r, s * math.sqrt(3.0) / 2.0)
        x = g.math("ADD", g.math("SUBTRACT", g.math("MULTIPLY", u, math.cos(th)), g.math("MULTIPLY", v, math.sin(th))), ox)
        y = g.math("ADD", g.math("ADD", g.math("MULTIPLY", u, math.sin(th)), g.math("MULTIPLY", v, math.cos(th))), oy)
        pts = g.node("GeometryNodeSetPosition", Geometry=pts["Points"], Position=g.combine(x, y, 0.0))
    return pts["Geometry"]


@once
def paving():
    hx = P["hex"]
    g = Graph("Garden Ground Paving", description="Hexagonal concrete pavers on the fitted lattice inside the fitted "
                                                  "outline, with jitter, joint litter, moss and weeds, and two ground "
                                                  "lights")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed for slab jitter and joint litter")
    joint = g.input("Joint Width", "FLOAT", 0.006, min=0.0, max=0.08, subtype="DISTANCE",
                    desc="Gap between neighbouring slabs")
    bevel = g.input("Bevel", "FLOAT", 0.004, min=0.0, max=0.04, subtype="DISTANCE", desc="Rounded top edge size")
    hjit = g.input("Height Jitter", "FLOAT", 0.004, min=0.0, max=0.03, subtype="DISTANCE",
                   desc="Random settling of each slab (up/down)")
    tilt = g.input("Tilt Jitter", "FLOAT", 0.012, min=0.0, max=0.1, subtype="ANGLE", desc="Random slab tilt")
    pjit = g.input("Placement Jitter", "FLOAT", 0.006, min=0.0, max=0.05, subtype="DISTANCE",
                   desc="Random sideways shift of each slab (hand-laid irregularity)")
    grow = g.input("Outline Offset", "FLOAT", 0.0, min=-1.0, max=1.0, subtype="DISTANCE",
                   desc="Grow or shrink the paved outline")
    chip = g.input("Chipping", "FLOAT", 1.2, min=0.0, max=3.0, desc="Edge chips and wear on the slabs (1 = fitted)")
    litter = g.input("Joint Litter", "FLOAT", 1.0, min=0.0, max=3.0, desc="Density of needles, moss and weeds in "
                                                                          "the joints (1 = fitted)")
    pts = _lattice_points(g, seed)
    with g.frame("Keep cells whose centre is inside the fitted paved outline"):
        margin = g.group(paving_boundary(), Position=g.node("GeometryNodeInputPosition"), Offset=grow)["Margin"]
        pts = g.node("GeometryNodeDeleteGeometry", props={"domain": "POINT"}, Geometry=pts,
                     Selection=g.math("LESS_THAN", margin, 0.0))["Geometry"]
    with g.frame("Per-slab random: settle, shift, tilt, nk_rand"):
        idx = g.node("GeometryNodeInputIndex")
        pos = g.node("GeometryNodeInputPosition")
        dz = _rand(g, idx, -1.0, 1.0, seed, 11)
        dx = _rand(g, idx, -1.0, 1.0, seed, 12)
        dy = _rand(g, idx, -1.0, 1.0, seed, 13)
        sink = smooth01(g, g.group(paving_boundary(), Position=pos)["Margin"], 0.25, -0.05)
        top = g.math("ADD", P["paving"]["level_z"], g.math("MULTIPLY_ADD", dz, hjit,
                                                          g.math("MULTIPLY", sink, -0.014)))
        newp = g.vmath("ADD", pos, g.combine(g.math("MULTIPLY", dx, pjit), g.math("MULTIPLY", dy, pjit), top))
        pts = g.node("GeometryNodeSetPosition", Geometry=pts, Position=newp)["Geometry"]
        rz = math.radians(hx["rotation_deg"] + 30.0)
        rot = g.node("FunctionNodeEulerToRotation", Euler=g.combine(
            g.math("MULTIPLY", _rand(g, idx, -1.0, 1.0, seed, 14), tilt),
            g.math("MULTIPLY", _rand(g, idx, -1.0, 1.0, seed, 15), tilt),
            g.math("ADD", rz, g.math("MULTIPLY", _rand(g, idx, -1.0, 1.0, seed, 16), 0.01))))
        pts = g.node("GeometryNodeStoreNamedAttribute", props={"data_type": "FLOAT", "domain": "POINT"},
                     Geometry=pts, Name="nk_rand", Value=_rand(g, idx, 0.0, 1.0, seed, 17))["Geometry"]
        edge_m = g.group(paving_boundary(), Position=g.node("GeometryNodeInputPosition"))["Margin"]
        pts = g.node("GeometryNodeStoreNamedAttribute", props={"data_type": "FLOAT", "domain": "POINT"},
                     Geometry=pts, Name="gr_edge", Value=smooth01(g, edge_m, 0.6, 0.0))["Geometry"]
    with g.frame("Slab width = lattice spacing - joint"):
        flats = g.math("SUBTRACT", hx["across_flats"], joint)
    lib_s = slab_variants(g, flats, bevel, chip, mat("Garden Ground Paver"))
    with g.frame("A chipped slab variant on every kept cell; slab size jitter varies the joint width"):
        idx_s = g.node("GeometryNodeInputIndex")
        sz = _rand(g, idx_s, 0.985, 1.01, seed, 18)
        pick = g.node("FunctionNodeRandomValue", props={"data_type": "INT"}, Min=0, Max=VARIANTS - 1, ID=idx_s,
                      Seed=g.math("ADD", seed, 19.0))["Value"]
        slabs = g.node("GeometryNodeInstanceOnPoints", Points=pts, Instance=lib_s, **{"Pick Instance": True},
                       **{"Instance Index": pick}, Rotation=rot, Scale=g.combine(sz, sz, 1.0))["Instances"]
    lib = litter_library(g)
    jp = joint_points(g, pts)
    litter_geo = joint_litter(g, jp, seed, litter, lib)
    with g.frame("Realized copy of the slabs as a raycast target for surface litter"):
        target = g.node("GeometryNodeRealizeInstances", Geometry=slabs)
    surf_litter = surface_litter(g, seed, litter, lib, target, jp)
    lights = _lights(g)
    with g.frame("Join slabs, joint litter, surface litter and lights"):
        out = g.node("GeometryNodeJoinGeometry")
        for geo in (slabs, litter_geo, surf_litter, lights):
            g.connect(geo, out.i("Geometry"))
    g.output("Geometry", "GEOMETRY", out, desc="Slabs (instances), litter (instances) and ground lights")
    g.output("Slab Points", "GEOMETRY", pts, desc="One point per slab (centre, nk_rand)")
    return g.finish()


def _lights(g):
    """Two round steel ground lights flush with the paving: a shallow disc with a darker lens."""
    r = P["lights_radius"]
    with g.frame("Ground lights: steel ring + lens at the measured positions"):
        ring = g.node("GeometryNodeMeshCylinder", Vertices=32, Radius=r, Depth=0.01)
        ring = g.node("GeometryNodeSetMaterial", Geometry=ring["Mesh"], Material=mat("Garden Ground Steel"))
        lens = g.node("GeometryNodeMeshCylinder", Vertices=32, Radius=r * 0.62, Depth=0.012)
        lens = g.node("GeometryNodeSetMaterial", Geometry=lens["Mesh"], Material=mat("Garden Ground Lens"))
        both = g.node("GeometryNodeJoinGeometry")
        g.connect(ring, both.i("Geometry"))
        g.connect(lens, both.i("Geometry"))
        out = g.node("GeometryNodeJoinGeometry")
        for x, y in P["lights"]:
            t = g.node("GeometryNodeTransform", Geometry=both, Translation=(x, y, P["paving"]["level_z"] + 0.004))
            g.connect(t, out.i("Geometry"))
    return out

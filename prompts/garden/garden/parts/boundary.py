"""Garden part 'boundary': the garden's surrounding walls, shed, fence + gate, hedges/climbers and far vegetation.

Top group "Garden Boundary" joins four sub-groups, each built from the fitted polylines in
data/params/boundary.json (measured by scripts/analyze_boundary.py):

  Garden Boundary Walls           house facade (stock brick), red-brick shed with door and mono-pitch roof,
                                  east boundary wall, neighbour building, south render walls
  Garden Boundary Fences          featheredge fence (boards, posts, rails, capping) and the slatted gate,
                                  round mirror plaque
  Garden Boundary Hedges          north hedge, north border planting, east climber/hedge, ivy column:
                                  noisy slab envelopes along polylines clothed in leaf-card instances
  Garden Boundary Far Vegetation  distant tree canopies beyond the boundary (coarse leaves)

All geometry is generated in Geometry Nodes from sparse fitted points; materials are procedural (see
boundary_materials.py).
"""
import math

import bpy
from nodekit.graph import Graph, once

from garden.parts import boundary_groups as bg
from garden.parts.boundary_materials import PREFIX, materials as _materials
from garden.util import load_params, srgb_to_linear

CONTROLS = ["Seed", "Foliage Density", "Leaf Scale", "Lumpiness", "Wall Height Scale", "Slat Width Scale",
            "Far Vegetation"]


def materials():
    _materials()


def _mat(name):
    return bpy.data.materials[PREFIX + name]


def _P():
    return load_params("boundary")


# ---- walls ------------------------------------------------------------------------------------------------------
def _shed_parts(g, shed, hscale):
    (ax, ay), (bx, by) = shed["front"]
    L = math.hypot(bx - ax, by - ay)
    tx, ty = (bx - ax) / L, (by - ay) / L
    lx, ly = -ty, tx                                   # left of travel = into the shed
    d, th = shed["depth"], shed["wall_thickness"]
    eave, back = shed["eave"], shed["back"]
    A, B = (ax, ay), (bx, by)
    B2, A2 = (bx + lx * d, by + ly * d), (ax + lx * d, ay + ly * d)
    loop = [(*A, eave), (*B, eave), (*B2, back), (*A2, back), (*A, eave)]
    curve = bg.poly_curve(g, loop, "Shed footprint")
    walls = g.group(bg.curve_slab(), Curve=curve, Thickness=th, Offset=th / 2, Bottom=-0.05,
                    **{"Top From Curve": hscale, "Step": 0.4, "Rows": 2})
    walls = g.node("GeometryNodeSetMaterial", Geometry=walls["Mesh"], Material=_mat("Brick Red"))["Geometry"]
    o, rt = shed["roof_overhang"], shed["roof_thickness"]
    corners = []
    for (px, py), z, sa, sl in ((A, eave, -1, -1), (B, eave, 1, -1), (B2, back, 1, 1), (A2, back, -1, 1)):
        cx, cy = px + tx * sa * o + lx * sl * o, py + ty * sa * o + ly * sl * o
        corners += [(cx, cy, z), (cx, cy, z + rt)]
    roof = bg.hull(g, corners, _mat("Roof Felt"), "Roof corners")
    dr = shed["door"]
    t = dr["t"]
    cx, cy = ax + (bx - ax) * t - lx * dr["proud"], ay + (by - ay) * t - ly * dr["proud"]
    yaw = math.degrees(math.atan2(ty, tx))
    door = bg.hull(g, bg.box_corners((cx, cy, dr["height"] / 2), (dr["width"], 0.06, dr["height"]), yaw),
                   _mat("Door Paint"), "Door corners")
    frame = bg.hull(g, bg.box_corners((cx + lx * 0.02, cy + ly * 0.02, dr["height"] / 2 + 0.03),
                                      (dr["width"] + dr.get("frame_extra", 0.12), 0.05,
                                       dr["height"] + 0.06), yaw),
                    _mat("Door Paint"), "Door frame corners")
    parts = [walls, roof, door, frame]
    pw, ph = dr["width"] * 0.36, dr["height"] * 0.3
    for k, (du, dz) in enumerate(((-1, 0.27), (1, 0.27), (-1, 0.66), (1, 0.66))):
        px = cx - lx * 0.035 + tx * du * dr["width"] * 0.22
        py = cy - ly * 0.035 + ty * du * dr["width"] * 0.22
        parts.append(bg.hull(g, bg.box_corners((px, py, dr["height"] * dz), (pw, 0.02, ph), yaw),
                             _mat("Door Paint"), f"Door panel {k}"))
    parts.append(bg.hull(g, bg.box_corners((cx - lx * 0.12, cy - ly * 0.12, 0.04),
                                           (dr["width"] + 0.25, 0.3, 0.1), yaw), _mat("Render"), "Door sill"))
    parts.append(bg.hull(g, bg.box_corners((cx - lx * 0.045 + tx * dr["width"] * 0.3,
                                            cy - ly * 0.045 + ty * dr["width"] * 0.3, dr["height"] * 0.86),
                                           (0.12, 0.01, 0.08), yaw), _mat("Mirror"), "Door plate"))
    return parts


@once
def walls_group():
    p = _P()
    g = Graph("Garden Boundary Walls", description="Boundary masonry from fitted polylines: the stock-brick house "
                                                   "facade, south render walls, the east brick wall behind the "
                                                   "climbers, a neighbour building, and the red-brick shed (closed "
                                                   "footprint slab, mono-pitch roof hull, black door)")
    hs = g.input("Wall Height Scale", "FLOAT", 1.0, min=0.5, max=1.5, subtype="FACTOR",
                 desc="Multiplier on every fitted wall top height")
    pieces = []
    for w in p["walls"]:
        with g.frame(f"Wall '{w['name']}': polyline -> slab -> {w['material']}"):
            curve = bg.poly_curve(g, w["points"], w["name"])
            slab = g.group(bg.curve_slab(), Curve=curve, Thickness=w["thickness"], Offset=w["offset"],
                           Bottom=-0.05, **{"Top From Curve": hs, "Step": 0.5, "Rows": 2})
            pieces.append(g.node("GeometryNodeSetMaterial", Geometry=slab["Mesh"],
                                 Material=_mat(w["material"]))["Geometry"])
    with g.frame("Boxes: facade doorway, rabbit hutch body/roof/legs (convex hulls of fitted boxes)"):
        for b in p.get("boxes", []):
            pieces.append(bg.hull(g, bg.box_corners(tuple(b["center"]), tuple(b["size"]), b["yaw"],
                                                    b.get("pitch", 0.0)), _mat(b["material"]), b["name"]))
    with g.frame("Shed: brick footprint walls, roof slab, door and frame"):
        pieces += _shed_parts(g, p["shed"], hs)
    with g.frame("Join"):
        join = g.node("GeometryNodeJoinGeometry")
        for geo in reversed(pieces):
            g.connect(geo, join.i("Geometry"))
    g.output("Geometry", "GEOMETRY", join["Geometry"], desc="Walls, shed and buildings")
    return g.finish()


# ---- fences -----------------------------------------------------------------------------------------------------
def _fence_parts(g, f, seed, wscale):
    curve = bg.poly_curve(g, f["points"], f["name"])
    mat = _mat(f["material"])
    th = f["thickness"]
    boards = g.group(bg.slat_row(), Curve=curve, Thickness=th, Offset=0.0, Bottom=f.get("bottom", 0.02), Seed=seed,
                     Material=mat,
                     **{"Slat Width": g.math("MULTIPLY", f["slat_width"], wscale), "Gap": f["gap"],
                        "Top Offset": 0.0, "Height Jitter": 0.012, "Lean": 0.012, "Twist": f.get("twist", 0.0)})
    out = [boards["Instances"]]
    if f.get("edge_strip"):
        # pale weathered leading edge of every board (the featheredge lip catching the sky)
        e = f["edge_strip"]
        edges = g.group(bg.slat_row(), Curve=curve, Thickness=th * 0.6, Offset=-th * 0.45, Bottom=0.03, Seed=seed,
                        Material=_mat(e["material"]),
                        **{"Slat Width": e["width"], "Gap": g.math("SUBTRACT", g.math("ADD", g.math(
                            "MULTIPLY", f["slat_width"], wscale), f["gap"]), e["width"]),
                           "Shift": g.math("MULTIPLY", g.math("MULTIPLY", f["slat_width"], wscale), 0.5),
                           "Top Offset": -0.01, "Height Jitter": 0.012, "Lean": 0.012})
        out.append(edges["Instances"])
    ps = f["post_size"]
    if "post_top" not in f:
        posts = g.group(bg.slat_row(), Curve=curve, Thickness=ps, Offset=th / 2 + ps / 2,
                        Bottom=f.get("post_bottom", -0.05), Seed=seed,
                        Material=mat, **{"Slat Width": ps, "Gap": f["post_spacing"] - ps, "Top Offset": 0.04,
                                         "Height Jitter": 0.0, "Lean": 0.0})
        out.append(posts["Instances"])
    else:
        (ax, ay, _), (bx, by, _) = f["points"][0], f["points"][-1]
        L = math.hypot(bx - ax, by - ay)
        tx, ty = (bx - ax) / L, (by - ay) / L
        yaw = math.degrees(math.atan2(ty, tx))
        top = f["post_top"]
        for k, (px, py) in enumerate(((ax - tx * ps / 2, ay - ty * ps / 2), (bx + tx * ps / 2, by + ty * ps / 2))):
            out.append(bg.hull(g, bg.box_corners((px, py, top / 2 - 0.03), (ps, ps, top + 0.06), yaw), mat,
                               f"Gate post {k}"))
        out.append(bg.hull(g, bg.box_corners(((ax + bx) / 2, (ay + by) / 2, top - 0.05), (L + 2 * ps, ps, 0.09),
                                             yaw), mat, "Gate head"))
    for r in f["rails"]:
        rail = g.group(bg.curve_slab(), Curve=curve, Thickness=0.03, Offset=th / 2 + 0.015, Bottom=r,
                       **{"Bottom From Top": 0.0, "Top From Curve": 0.0, "Top Offset": r + 0.09, "Step": 0.5})
        out.append(g.node("GeometryNodeSetMaterial", Geometry=rail["Mesh"], Material=mat)["Geometry"])
    if f.get("cap"):
        cap = g.group(bg.curve_slab(), Curve=curve, Thickness=th + 0.05, Offset=0.012, Bottom=-0.01,
                      **{"Bottom From Top": 1.0, "Top From Curve": 1.0, "Top Offset": 0.035, "Step": 0.5})
        out.append(g.node("GeometryNodeSetMaterial", Geometry=cap["Mesh"], Material=mat)["Geometry"])
    return out


def _plaque(g, pq):
    nx, ny, _ = pq["normal"]
    yaw = math.atan2(ny, nx)
    rot = g.node("FunctionNodeEulerToRotation", Euler=(0.0, math.pi / 2, yaw))["Rotation"]
    circ = g.node("GeometryNodeCurvePrimitiveCircle", Radius=pq["radius"], Resolution=32)
    prof = g.node("GeometryNodeCurvePrimitiveCircle", Radius=pq["tube"], Resolution=8)
    ring = g.node("GeometryNodeCurveToMesh", Curve=circ["Curve"], **{"Profile Curve": prof["Curve"]})
    ring = g.node("GeometryNodeSetMaterial", Geometry=ring["Mesh"], Material=_mat("Terracotta Ring"))["Geometry"]
    disc = g.node("GeometryNodeMeshCircle", props={"fill_type": "NGON"}, Vertices=32, Radius=pq["radius"] * 0.85)
    disc = g.node("GeometryNodeSetMaterial", Geometry=disc["Mesh"], Material=_mat("Mirror"))["Geometry"]
    join = g.node("GeometryNodeJoinGeometry")
    g.connect(disc, join.i("Geometry"))
    g.connect(ring, join.i("Geometry"))
    return g.node("GeometryNodeTransform", Geometry=join["Geometry"], Translation=tuple(pq["center"]),
                  Rotation=rot)["Geometry"]


def _trellis(g, t):
    """Diagonal wire/timber trellis panel: a 45-degree grid clipped to the panel, edges swept with a thin round
    profile, stood upright at the fitted centre and yaw."""
    w, h = t["width"], t["height"]
    n = max(4, int(round(1.5 * max(w, h) / t["cell"])))
    grid = g.node("GeometryNodeMeshGrid", **{"Size X": 1.5 * max(w, h), "Size Y": 1.5 * max(w, h),
                                             "Vertices X": n, "Vertices Y": n})
    rot = g.node("GeometryNodeTransform", Geometry=grid["Mesh"],
                 Rotation=g.node("FunctionNodeEulerToRotation", Euler=(0.0, 0.0, math.pi / 4))["Rotation"])
    p = g.separate(g.node("GeometryNodeInputPosition"))
    outside = g.math("MAXIMUM", g.math("GREATER_THAN", g.math("ABSOLUTE", p["X"]), w / 2),
                     g.math("GREATER_THAN", g.math("ABSOLUTE", p["Y"]), h / 2))
    clip = g.node("GeometryNodeDeleteGeometry", props={"domain": "POINT"}, Geometry=rot["Geometry"],
                  Selection=outside)
    curves = g.node("GeometryNodeMeshToCurve", Mesh=clip["Geometry"])
    prof = g.node("GeometryNodeCurvePrimitiveCircle", Radius=t["wire"], Resolution=4)
    mesh = g.node("GeometryNodeCurveToMesh", Curve=curves["Curve"], **{"Profile Curve": prof["Curve"]})
    up = g.node("FunctionNodeEulerToRotation", Euler=(math.pi / 2, 0.0, math.radians(t["yaw"])))["Rotation"]
    cx, cy, cz = t["center"]
    placed = g.node("GeometryNodeTransform", Geometry=mesh["Mesh"], Translation=(cx, cy, cz), Rotation=up)
    return g.node("GeometryNodeSetMaterial", Geometry=placed["Geometry"], Material=_mat(t["material"]))["Geometry"]


@once
def fences_group():
    p = _P()
    g = Graph("Garden Boundary Fences", description="Timber boundary: featheredge fence boards, posts, rails and "
                                                    "capping along a fitted polyline; slatted gate with posts and "
                                                    "head; the round mirror plaque on the fence")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed for board jitter and tone")
    ws = g.input("Slat Width Scale", "FLOAT", 1.0, min=0.5, max=2.0, subtype="FACTOR",
                 desc="Multiplier on the fitted board widths")
    pieces = []
    for f in p["fences"]:
        with g.frame(f"Fence '{f['name']}': boards, posts, rails"):
            pieces += _fence_parts(g, f, seed, ws)
    with g.frame("Mirror plaque on the fence"):
        pieces.append(_plaque(g, p["plaque"]))
    for t in p.get("trellises", []):
        with g.frame(f"Trellis '{t['name']}': clipped diagonal grid swept as thin wire"):
            pieces.append(_trellis(g, t))
    with g.frame("Join"):
        join = g.node("GeometryNodeJoinGeometry")
        for geo in reversed(pieces):
            g.connect(geo, join.i("Geometry"))
    g.output("Geometry", "GEOMETRY", join["Geometry"], desc="Fence and gate")
    return g.finish()


# ---- foliage ----------------------------------------------------------------------------------------------------
def _skin(g, mesh, item, seed, dens, size, k):
    """Foliage skin with the item's fitted leaf density/size scaled by the group-level multipliers."""
    return g.group(bg.foliage_skin(), Mesh=mesh, Seed=g.math("ADD", seed, float(k * 101)), Material=_mat("Foliage"),
                   **{"Leaf Density": g.math("MULTIPLY", item["leaf_density"], dens),
                      "Leaf Size": g.math("MULTIPLY", item["leaf_size"], size),
                      "Under Factor": item.get("under", 0.2),
                      "Blossom Size": item.get("blossom_size", 0.04),
                      "Blossom Above": item.get("blossom_above", 0.0),
                      "Blossom Clustering": item.get("blossom_clustering", 0.0),
                      "Leaf Lift": item.get("leaf_lift", 0.9),
                      "Patchiness": item.get("patchiness", 0.5),
                      "Color Variation": item.get("color_variation", 0.3),
                      "Bulge Shading": item.get("bulge_shading", 0.65),
                      "Shade Color": srgb_to_linear(item["shade"]), "Lit Color": srgb_to_linear(item["lit"]),
                      "Blossom Density": item.get("blossom_density", 0.0),
                      "Blossom Color": srgb_to_linear(item.get("blossom", [220, 220, 210]))})["Geometry"]


@once
def hedges_group():
    p = _P()
    g = Graph("Garden Boundary Hedges", description="Hedges and climbers along fitted polylines: a tapered slab "
                                                    "envelope (Garden Boundary Curve Slab), displaced by noise "
                                                    "(Garden Boundary Lumpy) and clothed in leaf cards (Garden "
                                                    "Boundary Foliage Skin)")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    dens = g.input("Density Scale", "FLOAT", 1.0, min=0.0, max=4.0, subtype="FACTOR",
                   desc="Multiplier on each hedge's fitted leaves per square metre")
    size = g.input("Leaf Scale", "FLOAT", 1.0, min=0.2, max=3.0, subtype="FACTOR",
                   desc="Multiplier on each hedge's fitted leaf length")
    lump = g.input("Lumpiness", "FLOAT", 1.0, min=0.0, max=3.0, subtype="FACTOR",
                   desc="Multiplier on the fitted envelope noise displacement")
    pieces = []
    for k, h in enumerate(p["hedges"]):
        with g.frame(f"Hedge '{h['name']}': envelope, noise, leaves"):
            curve = bg.poly_curve(g, h["points"], h["name"])
            top = max(pt[2] for pt in h["points"])
            if h.get("clumps"):
                cl = h["clumps"]
                slab = g.group(bg.clump_row(), Curve=curve, Seed=g.math("ADD", seed, float(k)),
                               Spacing=cl["spacing"], **{"Radius Min": cl["radius"][0],
                                                         "Radius Max": cl["radius"][1],
                                                         "Height Jitter": cl["height_jitter"],
                                                         "Side Jitter": cl["side_jitter"]})
            else:
                slab = g.group(bg.curve_slab(), Curve=curve, Thickness=h["thickness"], Offset=h["offset"],
                               Bottom=h["bottom"], Taper=h["taper"],
                               **{"Top From Curve": 1.0, "Step": 0.18, "Rows": max(4, int(round(top / 0.18)))})
            env = g.group(bg.lumpy(), Mesh=slab["Mesh"], Amount=g.math("MULTIPLY", h["lump"], lump),
                          Scale=h["lump_scale"], Seed=g.math("ADD", seed, float(k)))
            pieces.append(_skin(g, env["Mesh"], h, seed, dens, size, k))
    with g.frame("Join"):
        join = g.node("GeometryNodeJoinGeometry")
        for geo in reversed(pieces):
            g.connect(geo, join.i("Geometry"))
    g.output("Geometry", "GEOMETRY", join["Geometry"], desc="Hedge envelopes and leaf instances")
    return g.finish()


@once
def far_group():
    p = _P()
    g = Graph("Garden Boundary Far Vegetation", description="Distant tree canopies beyond the boundary: noisy "
                                                            "ellipsoids at fitted centres, clothed in coarse leaves")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    dens = g.input("Density Scale", "FLOAT", 1.0, min=0.0, max=4.0, subtype="FACTOR",
                   desc="Multiplier on each canopy's fitted leaves per square metre")
    size = g.input("Leaf Scale", "FLOAT", 1.0, min=0.2, max=3.0, subtype="FACTOR",
                   desc="Multiplier on each canopy's fitted leaf length")
    pieces = []
    for k, c in enumerate(p["canopies"]):
        with g.frame(f"Canopy '{c['name']}'"):
            blob = g.group(bg.canopy_blobs(), Center=tuple(c["center"]), Radii=tuple(c["radii"]))
            env = g.group(bg.lumpy(), Mesh=blob["Mesh"], Amount=c.get("lump", 0.35) * min(c["radii"]),
                          Scale=c.get("lump_scale", 0.9),
                          Seed=g.math("ADD", seed, float(k)))
            pieces.append(_skin(g, env["Mesh"], c, seed, dens, size, k + 50))
    for k, t in enumerate(p.get("trunks", [])):
        with g.frame(f"Boundary tree trunk '{t['name']}': tapered tube along a fitted line"):
            line = g.node("GeometryNodeCurvePrimitiveLine", Start=tuple(t["base"]), End=tuple(t["top"]))
            line = g.node("GeometryNodeResampleCurve", Curve=line["Curve"], Count=8)["Curve"]
            fac = g.node("GeometryNodeSplineParameter")["Factor"]
            prof = g.node("GeometryNodeCurvePrimitiveCircle", Radius=t["radius"], Resolution=10)
            tube = g.node("GeometryNodeCurveToMesh", Curve=line, Scale=g.map_range(fac, 0.0, 1.0, 1.0, 0.6),
                          **{"Profile Curve": prof["Curve"]})
            pieces.append(g.node("GeometryNodeSetMaterial", Geometry=tube["Mesh"], Material=_mat("Bark"))["Geometry"])
    with g.frame("Join"):
        join = g.node("GeometryNodeJoinGeometry")
        for geo in reversed(pieces):
            g.connect(geo, join.i("Geometry"))
    g.output("Geometry", "GEOMETRY", join["Geometry"], desc="Far canopies and boundary tree trunks")
    return g.finish()


# ---- top --------------------------------------------------------------------------------------------------------
def build():
    walls, fences, hedges, far = walls_group(), fences_group(), hedges_group(), far_group()
    g = Graph("Garden Boundary", kind="GEOMETRY", modifier=True,
              description="The garden's boundaries and background: house facade, red-brick shed, walls, fence and "
                          "gate, hedges and climbers, far tree canopies, all from fitted polylines")
    seed = g.input("Seed", "INT", 3, min=0, max=100000, desc="Random seed for boards and foliage")
    dens = g.input("Foliage Density", "FLOAT", 1.0, min=0.0, max=4.0, subtype="FACTOR",
                   desc="Multiplier on hedge/canopy leaf density")
    lscale = g.input("Leaf Scale", "FLOAT", 1.0, min=0.3, max=3.0, subtype="FACTOR", desc="Multiplier on leaf size")
    lump = g.input("Lumpiness", "FLOAT", 1.0, min=0.0, max=3.0, subtype="FACTOR",
                   desc="Multiplier on the hedge envelope noise")
    hscale = g.input("Wall Height Scale", "FLOAT", 1.0, min=0.5, max=1.5, subtype="FACTOR",
                     desc="Multiplier on fitted wall heights")
    wscale = g.input("Slat Width Scale", "FLOAT", 1.0, min=0.5, max=2.0, subtype="FACTOR",
                     desc="Multiplier on fence board widths")
    show_far = g.input("Far Vegetation", "BOOL", True, desc="Include the distant tree canopies")
    wn = g.group(walls, **{"Wall Height Scale": hscale})
    fn = g.group(fences, Seed=seed, **{"Slat Width Scale": wscale})
    hn = g.group(hedges, Seed=seed, Lumpiness=lump, **{"Density Scale": dens, "Leaf Scale": lscale})
    fv = g.group(far, Seed=seed, **{"Density Scale": dens, "Leaf Scale": lscale})
    sw = g.node("GeometryNodeSwitch", props={"input_type": "GEOMETRY"}, Switch=show_far)
    g.connect(fv["Geometry"], sw.i("True"))
    join = g.node("GeometryNodeJoinGeometry")
    for geo in (sw["Output"], hn["Geometry"], fn["Geometry"], wn["Geometry"]):
        g.connect(geo, join.i("Geometry"))
    g.output("Geometry", "GEOMETRY", join["Geometry"], desc="Boundary geometry")
    return g.finish(split_inputs=False)

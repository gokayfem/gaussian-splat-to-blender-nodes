"""Garden part 'structures': the man-made mid-ground (pots, raised bed, steps, handrails, edging, pallet, watering
can, rocks, pond grates, steel balls, statue, ornaments, football, far toys/chairs/pots).

Placements and sizes come from data/params/structures.json (measured by scripts/analyze_structures.py); each object
is a "Garden Structures <Thing>" sub-group placed by a Transform. Rectilinear features are laid out in the garden
frame rotated garden_deg about +Z. Top-level artist controls: Seed, Relief Depth, Relief Count, Weathering,
Grate Mesh, Bed Boards, Far Props, Pond.
"""
import math

from nodekit.graph import Graph

from garden.parts import structures_detail as detail, structures_materials, structures_props as props
from garden.parts import structures_shapes as shapes
from garden.parts.structures_util import garden_to_world, join, set_mat, xf
from garden.util import load_params, srgb_to_linear

CONTROLS = ["Seed", "Relief Depth", "Relief Count", "Weathering", "Grate Mesh", "Bed Boards", "Far Props", "Pond"]


def materials():
    structures_materials.build_all()


def _place(g, geo, xy, z, yaw=0.0, scale=1.0):
    return xf(g, geo, t=(xy[0], xy[1], z), r=(0.0, 0.0, yaw), s=(scale, scale, scale))


def _seed(g, seed, k):
    return g.math("ADD", seed, float(k))


def _pots(g, P, ctl):
    out = []
    st = P["pot_style"]
    for p in P["pots"]:
        r = p["radii"]
        geo = g.group(shapes.pot(), label=f"Pot {p['name']}", Height=p["height"], Wall=st["wall"],
                      **{"Radius Bottom": r[0], "Radius Lower": r[1], "Radius Middle": r[2], "Radius Upper": r[3],
                         "Radius Top": r[4], "Relief Depth": ctl["relief"], "Relief Count": ctl["count"],
                         "Relief Pitch": st["relief_pitch"], "Second Family": st.get("second_family", 0.55), "Line Width": st.get("line_width", 0.11), "Rim Height": st["rim_height"],
                         "Soil Drop": st["soil_drop"], "Canes": p["canes"], "Trailing Stems": p.get("trailing", 3), "Seedlings": p.get("seedlings", 6),
                         "Seed": _seed(g, ctl["seed"], p["seed"])})["Geometry"]
        out.append(_place(g, geo, p["xy"], p["base_z"], yaw=p["seed"] * 0.7))
    return out


def _steps(g, P, deg, ctl):
    s = P["steps"]
    out = []
    edges, hs = s["edges_b"], s["heights"]
    for i, h in enumerate(hs):
        top = i == len(hs) - 1
        geo = g.group(shapes.step_block(), label=f"Step {i + 1}", Width=s["width"],
                      Depth=edges[i] - edges[-1] + 0.02, Height=h, Seed=_seed(g, ctl["seed"], 80 + i),
                      Weeds=s.get("weeds", 30.0) * (0.4 if top else 1.0),
                      **{"Exposed Going": edges[i] - edges[i + 1], "Brick Riser": top and s.get("brick_top", False),
                         "Pink Top": top and s.get("pink_top", True)})["Geometry"]
        out.append(_place(g, geo, garden_to_world(s["centre_a"], edges[i], deg), 0.0, math.radians(deg)))
    for k, r in enumerate(P["handrails"]):
        geo = g.group(shapes.handrail(), label=f"Handrail {k + 1}", Run=r["run_b"], Rise=r["rise"],
                      Extension=r.get("extension", 0.4), Ties=r.get("ties", 0), **{"Post Height": r["post_h"], "Rail Rise": r.get("rail_rise", 0.39)})["Geometry"]
        out.append(_place(g, geo, r["post_xy"], r["base_z"], math.radians(deg)))
    for k, e in enumerate(P["edging"]):
        ln = e["a"][1] - e["a"][0]
        kerb = g.group(shapes.step_block(), label="Edging kerb", Width=ln, Depth=e["width"],
                       Height=e["top_z"] - e["base_z"], Weeds=0.0, Wear=0.012, Seed=_seed(g, ctl["seed"], 90 + k),
                       **{"Exposed Going": e["width"]})["Geometry"]
        c = garden_to_world((e["a"][0] + e["a"][1]) / 2, e["b"] + e["width"] / 2, deg)
        out.append(_place(g, kerb, c, e["base_z"], math.radians(deg)))
    return out


def _beds(g, P, deg, ctl):
    b = P["raised_bed"]
    la, lb = b["a"][1] - b["a"][0], b["b"][1] - b["b"][0]
    c = garden_to_world(sum(b["a"]) / 2, sum(b["b"]) / 2, deg)
    geo = g.group(shapes.raised_bed(), label="Raised bed", Size=(lb, la, 0.0), Height=b["top_z"] - b["base_z"],
                  Boards=ctl["boards"], **{"Board Thickness": b["board_t"], "Post Size": b["post"],
                                           "Soil Depth": b["top_z"] - b["soil_z"], "Seedling Density": b.get("seedling_density", 14.0), "Seed": _seed(g, ctl["seed"], 21),
                                           "Weathering": ctl["weather"]})["Geometry"]
    out = [_place(g, geo, c, b["base_z"], math.radians(deg + 90.0))]
    for k, t in enumerate(P.get("terrace_seedlings", [])):
        la2, lb2 = t["a"][1] - t["a"][0], t["b"][1] - t["b"][0]
        c2 = garden_to_world(sum(t["a"]) / 2, sum(t["b"]) / 2, deg)
        z = t["z_front"] + t["slope"] * (t.get("b_ref", -3.8) - sum(t["b"]) / 2)
        sd = g.group(shapes.seedlings(), label="Terrace seedlings", Size=(la2, lb2, 0.0), Slope=t["slope"],
                     Density=t["density"], Broad=t.get("broad", 0.0), Seed=_seed(g, ctl["seed"], 30 + k))["Geometry"]
        out.append(_place(g, sd, c2, z, math.radians(deg)))
    for k, wc in enumerate(P.get("weed_clumps", [])):
        geo = g.group(detail.weed(), label="Weed clump", Leaves=wc["leaves"], Seed=_seed(g, ctl["seed"], 120 + k),
                      **{"Leaf Length": wc["leaf"], "Leaf Width": wc.get("width", 0.85),
                         "Stem Length": wc.get("stem", wc["leaf"] * 1.3)})["Mesh"]
        out.append(_place(g, geo, wc["xy"], wc["z"], k * 1.7))
    pl = P["pallet"]
    pg = g.group(shapes.pallet(), label="Pallet", Size=tuple(pl["size"]), Seed=_seed(g, ctl["seed"], 5))["Geometry"]
    out.append(_place(g, pg, pl["xy"], pl["top_z"] - pl["size"][2], math.radians(pl.get("yaw_deg", deg))))
    return out


def _ground_props(g, P, ctl):
    out = []
    w = P["watering_can"]
    can = g.group(shapes.watering_can(), label="Watering can", Height=w["height"], Radius=w["radius"])["Geometry"]
    out.append(_place(g, can, w["xy"], w["base_z"], w.get("yaw", 0.0)))
    for r in P["rocks"]:
        rk = g.group(props.rock(), label="Rock", Size=tuple(r["size"]), Seed=_seed(g, ctl["seed"], r["seed"]))
        sink = r.get("sink", 0.25) * r["size"][2]
        out.append(_place(g, rk["Geometry"], r["xy"], r["z"] - sink, r["seed"] * 1.3))
    f = P["football"]
    out.append(_place(g, g.group(props.football(), Radius=f["r"])["Geometry"], f["xy"], f.get("z", 0.0)))
    ln = P["lantern"]
    out.append(_place(g, g.group(props.lantern(), Height=ln["height"], Radius=ln["r"])["Geometry"], ln["xy"],
                      ln["base_z"], 0.3))
    for bp in P["black_pots"]:
        pot = g.group(props.plain_pot(), label="Black pot", Height=bp["height"], Radius=bp["r"],
                      Color=(0.035, 0.035, 0.028, 1.0), Glazed=True,
                      **{"Plant Height": bp.get("plant", bp["height"] * 1.1)})["Geometry"]
        out.append(_place(g, pot, bp["xy"], bp["base_z"]))
    return out


def _pond(g, P, deg, ctl):
    pd = P["pond"]
    a0, a1 = pd["bars_a"]
    c = garden_to_world((a0 + a1) / 2, sum(pd["b"]) / 2, deg)
    geo = g.group(shapes.pond_grates(), label="Pond grates", Length=a1 - a0, Depth=pd["b"][1] - pd["b"][0],
                  Panels=pd["panels"], Water=pd.get("water", True), **{"Mesh Size": ctl["mesh"], "Water Drop": pd.get("water_drop", 0.12)})["Geometry"]
    out = [_place(g, geo, c, pd["z"], math.radians(deg))]
    for s in P["spheres"]:
        out.append(_place(g, g.group(props.steel_ball(), Radius=s["r"])["Geometry"], s["xy"], s["z"]))
    bb = P["bird_bath"]
    out.append(_place(g, g.group(props.bird_bath(), Top=bb["top_z"] - pd["z"], **{"Cap Radius": bb["cap_r"]})[
        "Geometry"], bb["xy"], pd["z"]))
    for k, rd in enumerate(P.get("reeds", [])):
        geo = g.group(props.reeds(), label="Pond reeds", Height=rd["height"], Radius=rd["r"],
                      Blades=rd.get("blades", 40), Seed=_seed(g, ctl["seed"], 100 + k))["Geometry"]
        out.append(_place(g, geo, rd["xy"], rd["z"]))
    bu = P["buddha"]
    yaw = math.atan2(-bu["xy"][1], -bu["xy"][0]) - math.pi / 2
    out.append(_place(g, g.group(props.buddha(), Height=bu["height"])["Geometry"], bu["xy"], bu["base_z"], yaw))
    return out


def _far(g, P):
    out = []
    for fp in P["far_pots"]:
        pot = g.group(props.plain_pot(), label="Far pot", Height=fp["height"], Radius=fp["r"],
                      Color=srgb_to_linear(fp["color"]), Glazed=False, **{"Plant Height": 0.25})["Geometry"]
        out.append(_place(g, pot, fp["xy"], fp["base_z"]))
    for ch in P["chairs"]:
        geo = g.group(props.chair(), Color=srgb_to_linear(ch["color"]))["Geometry"]
        out.append(_place(g, geo, ch["xy"], P.get("chairs_z", 0.03), math.radians(ch["yaw_deg"])))
    for k, c in enumerate(P.get("rear_chairs", [])):
        geo = g.group(props.chair(), label="Rear chair", Color=srgb_to_linear(c["color"]))["Geometry"]
        out.append(_place(g, geo, c["xy"], c["z"], math.radians(c["yaw_deg"]), c.get("scale", 1.0)))
    for c in P.get("crates", []):
        geo = g.group(props.crate(), Size=tuple(c["size"]), Color=srgb_to_linear(c["color"]),
                      Legs=c.get("legs", 0.0))["Geometry"]
        out.append(_place(g, geo, c["xy"], c["z"], math.radians(c["yaw_deg"])))
    for bk in P.get("buckets", []):
        pot = g.group(props.plain_pot(), label="Bucket", Height=bk["height"], Radius=bk["r"],
                      Color=srgb_to_linear(bk["color"]), Glazed=True, **{"Plant Height": 0.0})["Geometry"]
        out.append(_place(g, pot, bk["xy"], bk["z"]))
    rc = P.get("rear_clutter", {})
    for k, wb in enumerate(rc.get("wheelbarrows", [])):
        geo = g.group(props.wheelbarrow(), label="Wheelbarrow", Color=srgb_to_linear(wb["color"]))["Geometry"]
        out.append(_place(g, geo, wb["xy"], wb["z"], math.radians(wb["yaw_deg"]), wb.get("scale", 1.0)))
    for bx in rc.get("boxes", []):
        geo = g.group(props.storage_box(), label="Storage box", Size=tuple(bx["size"]))["Geometry"]
        out.append(_place(g, geo, bx["xy"], bx["z"], math.radians(bx["yaw_deg"])))
    for wp in rc.get("wire_panels", []):
        geo = g.group(props.wire_panel(), label="Wire panel", Width=wp["w"], Height=wp["h"], Mesh=wp["mesh"])
        out.append(_place(g, geo["Geometry"], wp["xy"], wp["z"], math.radians(wp["yaw_deg"])))
    for pd in rc.get("pads", []):
        pad = g.group(shapes.step_block(), label="Yard pad", Width=pd["size"][0], Depth=pd["size"][1],
                      Height=pd["h"], Weeds=0.0, **{"Exposed Going": pd["size"][1]})["Geometry"]
        out.append(_place(g, pad, pd["xy"], pd["z"], math.radians(pd.get("yaw_deg", 18.0))))
    for bp in rc.get("pots", []):
        pot = g.group(props.plain_pot(), label="Rear black pot", Height=bp["height"], Radius=bp["r"],
                      Color=(0.03, 0.03, 0.026, 1.0), Glazed=True, **{"Plant Height": bp.get("plant", 0.25)})
        out.append(_place(g, pot["Geometry"], bp["xy"], bp["z"]))
    sl = P["slide"]
    out.append(_place(g, g.group(props.slide(), Length=sl["length"], Top=sl["top_z"])["Geometry"], sl["xy"], P.get("slide_z", 0.02),
                      math.radians(sl["yaw_deg"])))
    th = P["toy_horse"]
    out.append(_place(g, g.group(props.toy_horse(), Height=th["height"])["Geometry"], th["xy"], th["base_z"], 1.2))
    return out


def build():
    P = load_params("structures")
    deg = P["garden_deg"]
    g = Graph("Garden Structures", kind="GEOMETRY", modifier=True,
              description="Man-made garden structures placed from data/params/structures.json: cream lattice pots, "
                          "raised timber bed, concrete steps with brick riser and handrails, kerbs, pallet, "
                          "galvanised can, rocks, pond grates, steel balls, statue, ornaments and far props")
    ctl = dict(
        seed=g.input("Seed", "INT", 0, min=0, max=100000, desc="Offsets every random choice (canes, boards, rocks)"),
        relief=g.input("Relief Depth", "FLOAT", P["pot_style"]["relief_depth"], min=0.0, max=0.03,
                       subtype="DISTANCE", desc="Height of the pots' lattice ridges"),
        count=g.input("Relief Count", "INT", P["pot_style"]["relief_count"], min=0, max=48,
                      desc="Lattice diamonds around each pot"),
        weather=g.input("Weathering", "FLOAT", 0.5, min=0.0, max=1.0, subtype="FACTOR",
                        desc="Grey weathering of the raised-bed timber"),
        mesh=g.input("Grate Mesh", "FLOAT", P["pond"]["mesh"], min=0.02, max=0.3, subtype="DISTANCE",
                     desc="Wire mesh opening of the pond grates"),
        boards=g.input("Bed Boards", "INT", P["raised_bed"]["boards"], min=1, max=6,
                       desc="Board rows per side of the raised bed"),
        far=g.input("Far Props", "BOOL", True, desc="Include the distant toys, chairs and pots (right view)"),
        pond=g.input("Pond", "BOOL", True, desc="Include the pond grates, steel balls, statue and bird bath"),
    )
    with g.frame("Pots flanking the steps"):
        pots = join(g, *_pots(g, P, ctl))
    with g.frame("Steps, handrails and kerbs"):
        steps = join(g, *_steps(g, P, deg, ctl))
    with g.frame("Raised bed and pallet"):
        beds = join(g, *_beds(g, P, deg, ctl))
    with g.frame("Watering can, rocks, football, lantern, black pots"):
        misc = join(g, *_ground_props(g, P, ctl))
    with g.frame("Pond grates, steel balls, bird bath, statue (switchable)"):
        pond = join(g, *_pond(g, P, deg, ctl))
        pond = g.node("GeometryNodeSwitch", props={"input_type": "GEOMETRY"}, Switch=ctl["pond"],
                      **{"True": pond})["Output"]
    with g.frame("Distant toys, chairs and pots (switchable)"):
        far = join(g, *_far(g, P))
        far = g.node("GeometryNodeSwitch", props={"input_type": "GEOMETRY"}, Switch=ctl["far"],
                     **{"True": far})["Output"]
    with g.frame("Realize so per-piece attributes reach the shaders"):
        out = g.node("GeometryNodeRealizeInstances", Geometry=join(g, pots, steps, beds, misc, pond, far))["Geometry"]
    g.output("Geometry", "GEOMETRY", out, desc="All structures")
    return g.finish()

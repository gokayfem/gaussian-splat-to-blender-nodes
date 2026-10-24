"""Scan <-> world conversion (data/frame.json) and the canonical review cameras.

World frame: metres, Z up (paving normal), origin on the paving under the table centre. A camera is stored as
position / look_at / up in world space plus a vertical FOV and pixel size; ``to_scan`` gives the
GaussianSplats3D viewer equivalent so reference and procedural renders share one definition.
"""
import json
import math
import pathlib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_frame():
    f = json.load(open(ROOT / "data/frame.json"))
    return np.array(f["R_scan_to_world"]), np.array(f["origin_scan"]), f["scale_m_per_unit"]


def scan_to_world_point(p):
    R, o, s = load_frame()
    return (np.asarray(p, float) - o) @ R.T * s


def world_to_scan_point(w):
    R, o, s = load_frame()
    return np.asarray(w, float) / s @ R + o


def scan_to_world_dir(v):
    R, _, _ = load_frame()
    return np.asarray(v, float) @ R.T


def world_to_scan_dir(v):
    R, _, _ = load_frame()
    return np.asarray(v, float) @ R


def orbit(azimuth_deg, elevation_deg, distance, target=(0, 0, 0.7)):
    t = np.asarray(target, float)
    a, e = math.radians(azimuth_deg), math.radians(elevation_deg)
    return (t + distance * np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])).tolist()


def build_cameras():
    """Canonical review cameras. 'hero' is the approved screenshot camera converted from the viewer."""
    viewer = dict(position=[-3.15634, -0.16946, -0.51552], look_at=[1.52976, 2.27776, 1.65898],
                  up=[0, -1, -0.54])
    hero_pos = scan_to_world_point(viewer["position"])
    hero_look = scan_to_world_point(viewer["look_at"])
    hero_up = scan_to_world_dir(viewer["up"])
    hero_up = hero_up / np.linalg.norm(hero_up)
    d = hero_pos - np.array([0, 0, 0.7])
    hero_az = math.degrees(math.atan2(d[1], d[0]))
    hero_el = math.degrees(math.atan2(d[2], math.hypot(d[0], d[1])))
    dist = float(np.linalg.norm(d))
    cams = {"hero": dict(position=hero_pos.tolist(), look_at=hero_look.tolist(), up=hero_up.tolist(),
                         fov_y_deg=50.0, width=904, height=928,
                         note="approved screenshot camera (viewer initial camera, 904x928, 50 deg vertical)")}
    zup = [0, 0, 1]
    spec = {
        "opposite": (hero_az + 180, 32, dist, (0, 0, 0.6)),
        "left": (hero_az + 90, 30, dist, (0, 0, 0.6)),
        "right": (hero_az - 90, 30, dist, (0, 0, 0.6)),
        "overview": (hero_az + 20, 55, dist * 1.6, (0, 0, 0.3)),
        "low_side": (hero_az + 135, 14, dist * 0.9, (0, 0, 0.75)),
    }
    for name, (az, el, dd, tgt) in spec.items():
        cams[name] = dict(position=orbit(az, el, dd, tgt), look_at=list(tgt), up=zup, fov_y_deg=50.0,
                          width=960, height=640, note=f"orbit az={az:.0f} el={el} d={dd:.2f}")
    cams["detail_vase"] = dict(position=orbit(hero_az + 10, 35, 1.6, (0, 0, 0.95)), look_at=[0, 0, 0.95],
                               up=zup, fov_y_deg=40.0, width=800, height=800, note="table/vase detail")
    # Matched close-ups: same line of sight as the hero camera (so the scan's coverage is the hero's), pulled in
    # toward world targets back-projected from hero pixels (scripts: see docs/COORDINATES.md).
    close = {"close_table": ((0.45, -0.30, 0.74), 1.15, 30), "close_vase": ((-0.04, 0.015, 0.97), 0.95, 30),
             "close_paving": ((-0.27, 0.45, 0.05), 1.1, 40), "close_trunk": ((0.10, -2.55, 0.85), 1.7, 32),
             "close_foliage": ((-1.0, -2.40, 0.75), 2.0, 36), "close_pots": ((1.2, -3.9, 0.35), 2.6, 32)}
    for name, (tgt, dd, fov) in close.items():
        t = np.asarray(tgt, float)
        v = hero_pos - t
        v /= np.linalg.norm(v)
        cams[name] = dict(position=(t + v * dd).tolist(), look_at=list(tgt), up=zup, fov_y_deg=float(fov),
                          width=1024, height=1024, note=f"matched close-up along hero line of sight, {dd} m")
    cams["close_legs"] = dict(position=orbit(hero_az + 135, 10, 1.9, (0, 0, 0.35)), look_at=[0, 0, 0.35], up=zup,
                              fov_y_deg=40.0, width=1024, height=1024, note="supports/foot close-up from low_side side")
    meta = dict(hero_azimuth_deg=hero_az, hero_elevation_deg=hero_el, hero_distance_m=dist)
    return cams, meta


def to_scan(cam):
    return dict(position=world_to_scan_point(cam["position"]).tolist(),
                look_at=world_to_scan_point(cam["look_at"]).tolist(),
                up=world_to_scan_dir(cam["up"]).tolist(), fov_y_deg=cam["fov_y_deg"],
                width=cam["width"], height=cam["height"])


if __name__ == "__main__":
    cams, meta = build_cameras()
    json.dump(dict(meta=meta, world=cams), open(ROOT / "data/cameras_world.json", "w"), indent=1)
    scan = {n: to_scan(c) for n, c in cams.items()}
    scan["viewer_initial"] = dict(position=[-3.15634, -0.16946, -0.51552], look_at=[1.52976, 2.27776, 1.65898],
                                  up=[0, -1, -0.54], fov_y_deg=50, width=904, height=928)
    json.dump(scan, open(ROOT / "data/reference_cameras.json", "w"), indent=1)
    print(json.dumps(meta), list(cams))

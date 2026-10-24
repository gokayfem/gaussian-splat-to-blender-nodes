#!/usr/bin/env python3
"""Create one orbit manifest for a Z-up Blender scene and its scan-space reference.

World points = scale * R * (scan points - origin). No third-party dependencies.
"""
import argparse
import json
import math
from pathlib import Path


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def unit(v):
    n = math.sqrt(dot(v, v))
    if not math.isfinite(n) or n < 1e-12:
        raise ValueError("Degenerate camera direction")
    return [x/n for x in v]


def vector(v):
    if len(v) != 3 or not all(math.isfinite(float(x)) for x in v):
        raise ValueError("Expected three finite coordinates")
    return [float(x) for x in v]


def validate_frame(f):
    r = f["R_scan_to_world"]
    vector(f["origin_scan"])
    s = f["scale_m_per_unit"]
    if not math.isfinite(s) or s <= 0 or len(r) != 3:
        raise ValueError("Frame requires positive scale and a 3x3 proper rotation")
    for row in r:
        vector(row)
    for i in range(3):
        for j in range(3):
            if abs(dot(r[i], r[j]) - (i == j)) > 1e-5:
                raise ValueError("Rotation is not orthonormal")
    if abs(dot(r[0], cross(r[1], r[2])) - 1) > 1e-5:
        raise ValueError("Rotation reflects handedness; determinant must be +1")
    return f


def transform(v, frame, to_scan=False, direction=False):
    validate_frame(frame)
    v = vector(v)
    r, o, s = (frame[k] for k in ("R_scan_to_world", "origin_scan", "scale_m_per_unit"))
    if to_scan:
        v = v if direction else [x/s for x in v]
        out = [sum(r[j][i]*v[j] for j in range(3)) for i in range(3)]
        return out if direction else [out[i]+o[i] for i in range(3)]
    v = v if direction else [v[i]-o[i] for i in range(3)]
    out = [dot(row, v) for row in r]
    return out if direction else [s*x for x in out]


def validate_camera(c):
    p, t, u = (vector(c[k]) for k in ("position", "look_at", "up"))
    z = unit([p[i]-t[i] for i in range(3)])
    unit(cross(u, z))
    if not 0 < c["fov_y_deg"] < 179:
        raise ValueError("Vertical FOV must be in (0, 179) degrees")
    if any(type(c[k]) is not int or c[k] <= 0 for k in ("width", "height")):
        raise ValueError("Image dimensions must be positive integers")
    return c


def camera_to_scan(c, frame):
    validate_camera(c)
    return dict(c, position=transform(c["position"], frame, True),
                look_at=transform(c["look_at"], frame, True),
                up=unit(transform(c["up"], frame, True, True)))


def orbit(target, radius, elevation, frames, width, height, fov, start=0):
    target = vector(target)
    if not math.isfinite(radius) or radius <= 0 or frames < 2 or not -89 < elevation < 89:
        raise ValueError("Use radius > 0, at least 2 frames and elevation between -89 and 89")
    if not math.isfinite(start):
        raise ValueError("Start azimuth must be finite")
    e = math.radians(elevation)
    cameras = {}
    for i in range(frames):
        a = math.radians(start + 360*i/frames)
        d = [math.cos(e)*math.cos(a), math.cos(e)*math.sin(a), math.sin(e)]
        cameras[f"{i:06d}"] = validate_camera(dict(
            position=[target[j]+radius*d[j] for j in range(3)], look_at=target,
            up=[0, 0, 1], fov_y_deg=fov, width=width, height=height))
    return cameras


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--frame", type=Path, help="Optional scan-to-world similarity transform JSON")
    p.add_argument("--target", type=float, nargs=3, default=[0, 0, 0.7])
    p.add_argument("--radius", type=float, default=3)
    p.add_argument("--elevation", type=float, default=30)
    p.add_argument("--start", type=float, default=0)
    p.add_argument("--frames", type=int, default=240)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=640)
    p.add_argument("--fov", type=float, default=50)
    a = p.parse_args()
    if a.fps <= 0:
        p.error("fps must be positive")
    world = orbit(a.target, a.radius, a.elevation, a.frames, a.width, a.height, a.fov, a.start)
    result = dict(schema_version=1, fps=a.fps, loop=True, world=world)
    if a.frame:
        f = validate_frame(json.loads(a.frame.read_text()))
        result.update(frame=f, scan={k: camera_to_scan(c, f) for k, c in world.items()})
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Wrote {len(world)} poses to {a.out}; closing pose is not duplicated")


if __name__ == "__main__":
    main()

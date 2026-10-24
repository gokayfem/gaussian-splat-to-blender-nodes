"""Viewer-camera math shared by analysis scripts (three.js conventions, scan coordinates)."""
import numpy as np

VIEWER = dict(position=[-3.15634, -0.16946, -0.51552], look_at=[1.52976, 2.27776, 1.65898],
              up=[0.0, -1.0, -0.54], fov_y_deg=50.0)


def look_at_basis(pos, target, up):
    """Rows: camera right, camera up, camera back (three.js: camera looks down -Z)."""
    pos, target, up = (np.asarray(v, float) for v in (pos, target, up))
    z = pos - target
    z /= np.linalg.norm(z)
    x = np.cross(up, z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z])


def project(points, pos, target, up, fov_y_deg, width, height):
    R = look_at_basis(pos, target, up)
    pc = (points - np.asarray(pos, float)) @ R.T
    depth = -pc[:, 2]
    f = 0.5 * height / np.tan(np.radians(fov_y_deg) / 2)
    with np.errstate(divide="ignore", invalid="ignore"):
        u = width / 2 + f * pc[:, 0] / depth
        v = height / 2 - f * pc[:, 1] / depth
    return u, v, depth, f


def point_render(pos, rgba, scale, cam, width, height, min_alpha=40):
    """Painter's-order disc render of splat centres: a fast, approximate view for alignment checks."""
    u, v, d, f = project(pos, cam["position"], cam["look_at"], cam["up"], cam["fov_y_deg"], width, height)
    ok = (d > 0.05) & (u >= 0) & (u < width) & (v >= 0) & (v < height) & (rgba[:, 3] >= min_alpha)
    idx = np.nonzero(ok)[0]
    idx = idx[np.argsort(-d[idx])]
    img = np.zeros((height, width, 3), np.float32)
    zb = np.full((height, width), np.inf, np.float32)
    rad = np.clip(f * scale[idx].max(1) / d[idx] * 0.9, 0.5, 6).astype(np.int32)
    for r in range(0, 7):
        sel = idx[rad == r] if r else idx[rad <= 0]
        if len(sel) == 0:
            continue
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy > r * r + 0.5:
                    continue
                uu = (u[sel] + dx).astype(int); vv = (v[sel] + dy).astype(int)
                m = (uu >= 0) & (uu < width) & (vv >= 0) & (vv < height)
                s, uu, vv = sel[m], uu[m], vv[m]
                dd = d[s]
                # emulate back-to-front painting by writing nearer last
                order = np.argsort(-dd)
                s, uu, vv, dd = s[order], uu[order], vv[order], dd[order]
                closer = dd < zb[vv, uu]
                img[vv[closer], uu[closer]] = rgba[s[closer], :3] / 255.0
                zb[vv[closer], uu[closer]] = dd[closer]
    return img, zb

"""Project-independent capture projection, derived from the Garden c11b/c22s/c26b study.

No Blender dependency. Coordinates and tolerances are in the configured world frame.
Captured radiance is not clean albedo; source masks complement reconstructed depth.
"""
import math

import numpy as np
from scipy.ndimage import distance_transform_edt, gaussian_filter, maximum_filter, minimum_filter

from projection_config import options


def srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def project(camera, points):
    pos, look, up = (np.asarray(camera[k], float) for k in ("position", "look_at", "up"))
    z = pos - look; z /= np.linalg.norm(z)
    x = np.cross(up, z); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    d = points - pos
    distance = np.linalg.norm(d, axis=1)
    forward = -(d @ z)
    f = 0.5 * camera["height"] / math.tan(math.radians(camera["fov_y_deg"]) / 2)
    safe = np.where(np.abs(forward) > 1e-12, forward, 1e-12)
    u = camera["width"] / 2 + f * (d @ x) / safe
    v = camera["height"] / 2 - f * (d @ y) / safe
    return d, distance, forward, f, u, v


def bilinear(image, u, v):
    h, w = image.shape[:2]
    u = np.clip(u - 0.5, 0, w - 1.001); v = np.clip(v - 0.5, 0, h - 1.001)
    x, y = u.astype(int), v.astype(int)
    a, b = (u - x)[:, None], (v - y)[:, None]
    return (image[y, x] * (1-a) * (1-b) + image[y, x+1] * a * (1-b)
            + image[y+1, x] * (1-a) * b + image[y+1, x+1] * a * b)


def reject_samples(points, srgb, rules):
    """Explicit, optional world-region/color rules; never infer semantic labels from hue."""
    rejected = np.zeros(len(points), bool)
    channels = {"r": 0, "g": 1, "b": 2}
    for rule in rules:
        # A bounded region is mandatory: a scene-specific fix must not filter an entire world.
        low, high = np.asarray(rule["bounds_min"], float), np.asarray(rule["bounds_max"], float)
        if low.shape != (3,) or high.shape != (3,) or not np.isfinite([low, high]).all() or (low > high).any():
            raise ValueError("Rejection rules need finite, ordered 3D bounds")
        hit = ((points >= low) & (points <= high)).all(1)
        for left, right, ratio in rule.get("channel_ratios", []):
            if not math.isfinite(ratio) or ratio <= 0:
                raise ValueError("Channel ratios must be finite and positive")
            hit &= srgb[:, channels[left]] > ratio * srgb[:, channels[right]]
        if "rgb_min" in rule:
            hit &= (srgb >= np.asarray(rule["rgb_min"])).all(1)
        if "rgb_max" in rule:
            hit &= (srgb <= np.asarray(rule["rgb_max"])).all(1)
        if "min_sum" in rule:
            hit &= srgb[:, [channels[c] for c in rule["min_sum"]["channels"]]].sum(1) > rule["min_sum"]["value"]
        rejected |= hit
    return rejected


def prepare_view(view, target, p):
    depth, ids = view["depth"], view["ids"]
    depth = minimum_filter(depth, size=max(p["depth_erode"], 1))
    foreign = maximum_filter(ids != target["object_id"], size=max(p["border"], 1))
    allowed = view.get("allowed")
    if allowed is not None:
        # Bilinear samples may touch four pixels; don't interpolate across a rejected pixel.
        allowed = minimum_filter(allowed, size=3)
    return dict(view, depth=depth, foreign=foreign, allowed=allowed,
                linear_rgb=srgb_to_linear(view["rgb"].astype(np.float32)/255))


def sample_view(points, normals, view, target, p):
    c = view["camera"]
    d, distance, forward, f, u, v = project(c, points)
    cosine = -(normals*d).sum(1) / np.maximum(distance, 1e-12)
    x, y = np.clip(u.astype(int), 0, c["width"]-1), np.clip(v.astype(int), 0, c["height"]-1)
    threshold = np.where(np.abs(normals[:, 2]) < 0.4, p["vertical_min_cos"], p["min_cos"])
    valid = (forward > 0) & (u >= 1) & (u < c["width"]-1) & (v >= 1) & (v < c["height"]-1)
    valid &= cosine > threshold
    valid &= distance <= view["depth"][y, x] + p["depth_absolute"] + p["depth_relative"]*distance
    valid &= ~view["foreign"][y, x]
    observed_candidate = valid.copy()
    if view.get("allowed") is not None:
        valid &= view["allowed"][y, x]
    color = bilinear(view["linear_rgb"], u, v)
    valid &= ~reject_samples(points, linear_to_srgb(color), target.get("reject_rules", []))
    resolution = f / np.maximum(distance, 1e-12)
    if p["resolution_cap"]:
        resolution = np.minimum(resolution, p["resolution_cap"])
    weight = ((np.clip(cosine, 0, 1)**4)*resolution**2)**(p["power"]/2)
    if p["edge_feather"]:
        edge = np.minimum(np.minimum(u, c["width"]-u)/(c["width"]/2),
                          np.minimum(v, c["height"]-v)/(c["height"]/2))
        t = np.clip(edge/p["edge_feather"], 0, 1)
        weight *= t*t*(3-2*t)
    return np.where(valid, weight, 0), color, observed_candidate


def blend_samples(weights, colors, mode, quantile):
    """c11b robust diffuse consensus: suppress bright outliers without selecting dark ghosts."""
    if mode == "robust":
        lum = colors @ np.array([0.2126, 0.7152, 0.0722])
        total = weights.sum(0)
        mu = (weights*lum).sum(0)/np.maximum(total, 1e-300)
        sd = np.sqrt(np.maximum((weights*lum*lum).sum(0)/np.maximum(total, 1e-300)-mu*mu, 0)) + 0.02
        dark = lum < mu - np.where(quantile > 1, 3.0, 2.2)*sd
        weights = np.where(dark, 0, weights*np.exp(-3*np.maximum(lum-(mu-quantile*sd), 0)/sd))
    total = weights.sum(0)
    color = (weights[..., None]*colors).sum(0)/np.maximum(total, 1e-300)[:, None]
    return color, total > 0


def project_surface(position, normal, valid, material_ids, views, target, chunk_size=65536):
    p = options(target)
    index = np.flatnonzero(valid)
    output = np.zeros((*valid.shape, 3), np.float32)
    state = np.zeros(valid.shape, np.uint8)
    prepared = [prepare_view(v, target, p) for v in views]
    for start in range(0, len(index), chunk_size):
        ix = index[start:start+chunk_size]
        points, normals = position.reshape(-1, 3)[ix], normal.reshape(-1, 3)[ix].astype(float)
        normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
        sampled = [sample_view(points, normals, v, target, p) for v in prepared]
        weights = np.array([s[0] for s in sampled])
        colors = np.array([s[1] for s in sampled])
        q = np.full(len(ix), p["robust_q"])
        for slot, override in target.get("material_overrides", {}).items():
            q[material_ids.ravel()[ix] == int(slot)] = override.get("robust_q", p["robust_q"])
        color, covered = blend_samples(weights, colors, p["mode"], q)
        candidate = np.array([s[2] for s in sampled]).any(0)
        output.reshape(-1, 3)[ix] = color
        # 2 = observed candidate rejected to procedural fallback; 3 = unseen fallback.
        state.ravel()[ix] = np.where(covered, 1, np.where(candidate, 2, 3))
    return output, state


def finish_texture(color, state, material_ids, target, irradiance=None):
    """Feather only toward procedural fallback; never fill unseen faces with another object's color."""
    p = options(target)
    direct = state == 1
    if target.get("appearance", "captured_radiance") == "estimated_albedo":
        if irradiance is None or irradiance.shape != color.shape or not np.isfinite(irradiance).all():
            raise ValueError("estimated_albedo needs a finite, same-size linear irradiance bake")
        e = irradiance.mean(2)
        lit = direct & (e > 0.05)
        if not lit.any():
            raise ValueError("No lit direct texels for an irradiance estimate")
        floor = p["irradiance_floor"]*float(np.median(e[lit]))
        color = np.clip(color/np.maximum(e, floor)[..., None], 0, 0.9)
    mix = np.zeros(state.shape, np.float32)
    # Material-aware filtering preserves slate/wood and other real face-slot boundaries.
    for slot in np.unique(material_ids[state > 0]):
        surface = (material_ids == slot) & (state > 0)
        d = direct & surface
        if p["mix_feather"]:
            f = gaussian_filter(d.astype(float), p["mix_feather"])/np.maximum(
                gaussian_filter(surface.astype(float), p["mix_feather"]), 1e-6)
            mix[d] = np.clip(2*f[d]-0.5, 0, 1)
        else:
            mix[d] = 1
    rgb = linear_to_srgb(color)
    if direct.any() and p["padding"]:
        distance, nearest = distance_transform_edt(~direct, return_indices=True)
        padding = (state == 0) & (distance <= p["padding"])
        rgb[padding] = rgb[tuple(nearest[:, padding])]
        mix[padding] = mix[tuple(nearest[:, padding])]
        state = state.copy(); state[padding] = 4
    return rgb, mix, state

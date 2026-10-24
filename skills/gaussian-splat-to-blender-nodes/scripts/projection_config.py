"""Shared projection configuration and file fingerprints (standard library only)."""
import hashlib
import json
import math
from pathlib import Path
import re
from cameras import validate_camera


def sha256(path):
    with Path(path).open("rb") as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path):
    path = Path(path).resolve()
    cfg = json.loads(path.read_text())
    if cfg.get("schema_version") != 1 or not cfg.get("targets") or not cfg.get("views"):
        raise ValueError("schema_version=1, nonempty targets and views are required")
    names, objects, ids = set(), set(), set()
    for target in cfg["targets"]:
        name, obj, ident = target["name"], target["object"], target["object_id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name) or name in names or obj in objects:
            raise ValueError("Targets need unique safe names and unique source objects")
        if type(ident) is not int or not 1 <= ident <= 32766 or ident in ids:
            raise ValueError("Target object IDs must be unique integers in 1..32766")
        names.add(name); objects.add(obj); ids.add(ident)
        size = target.get("texture_size", 1024)
        if type(size) is not int or not 8 <= size <= 8192:
            raise ValueError("texture_size must be an integer in 8..8192")
        mode = target.get("appearance", "captured_radiance")
        if mode not in ("captured_radiance", "estimated_albedo"):
            raise ValueError("appearance must be captured_radiance or estimated_albedo")
        options(target)
        for rule in target.get("reject_rules", []):
            validate_rule(rule)
        if target.get("uv_mode", "unwrap") not in ("unwrap", "existing"):
            raise ValueError("uv_mode must be unwrap or existing")
        slots = target.get("material_slots")
        if slots is not None and (not slots or any(type(s) is not int or s < 0 for s in slots) or len(set(slots)) != len(slots)):
            raise ValueError("material_slots must be unique nonnegative integer indices")
        for slot, values in target.get("material_overrides", {}).items():
            if not slot.isdigit() or (slots is not None and int(slot) not in slots):
                raise ValueError("Material overrides must name selected, zero-based material slots")
            for key, value in values.items():
                if key not in ("robust_q", "color_scale", "roughness", "specular"):
                    raise ValueError(f"Unknown material setting: {key}")
                if not math.isfinite(value) or value < 0 or (key in ("roughness", "specular") and value > 1):
                    raise ValueError(f"Invalid material setting: {key}")
    for name, view in cfg["views"].items():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("View names must be safe file stems")
        validate_camera(view["camera"])
        if min(view["camera"][k] for k in ("width", "height")) < 3:
            raise ValueError("Projection captures must be at least 3x3 pixels")
        if not view.get("image"):
            raise ValueError("Every view needs a capture image path")
        if set(view.get("source_valid_masks", {})) - names:
            raise ValueError("source_valid_masks must name configured targets")
    return cfg, path.parent


def options(target):
    p = dict(mode="weighted", power=12.0, min_cos=0.3, vertical_min_cos=0.3,
             depth_absolute=0.006, depth_relative=0.004, depth_erode=1,
             border=9, resolution_cap=0.0, edge_feather=0.0, robust_q=0.3,
             mix_feather=3.0, padding=8, irradiance_floor=0.35)
    unknown = set(target.get("projection", {})) - p.keys()
    if unknown:
        raise ValueError(f"Unknown projection options: {sorted(unknown)}")
    p.update(target.get("projection", {}))
    if p["mode"] not in ("weighted", "robust"):
        raise ValueError("Projection mode must be weighted or robust")
    for key in ("min_cos", "vertical_min_cos", "edge_feather"):
        if not math.isfinite(p[key]) or not 0 <= p[key] <= 1:
            raise ValueError(f"{key} must be in [0,1]")
    for key in ("depth_absolute", "depth_relative", "resolution_cap", "robust_q", "mix_feather"):
        if not math.isfinite(p[key]) or p[key] < 0:
            raise ValueError(f"{key} must be finite and nonnegative")
    if not 0 < p["power"] <= 32 or not 0 < p["irradiance_floor"] <= 1:
        raise ValueError("power must be in (0,32], irradiance_floor in (0,1]")
    for key in ("depth_erode", "border", "padding"):
        if type(p[key]) is not int or not 0 <= p[key] <= 255:
            raise ValueError(f"{key} must be an integer in 0..255")
    return p


def validate_rule(rule):
    """Reject malformed local heuristics before starting any Blender bakes."""
    allowed = {"bounds_min", "bounds_max", "rgb_min", "rgb_max", "channel_ratios", "min_sum"}
    if set(rule) - allowed:
        raise ValueError("Unknown rejection rule field")
    for key in ("bounds_min", "bounds_max", "rgb_min", "rgb_max"):
        if key not in rule and key.startswith("rgb"):
            continue
        value = rule.get(key, [])
        if len(value) != 3 or not all(math.isfinite(v) for v in value):
            raise ValueError(f"{key} must contain three finite numbers")
        if key.startswith("rgb") and not all(0 <= v <= 1 for v in value):
            raise ValueError(f"{key} must be in [0,1]")
    if any(lo > hi for lo, hi in zip(rule["bounds_min"], rule["bounds_max"])):
        raise ValueError("Rejection bounds must be ordered")
    for ratio in rule.get("channel_ratios", []):
        if len(ratio) != 3 or any(c not in ("r", "g", "b") for c in ratio[:2]):
            raise ValueError("Channel ratios require two channel names and a ratio")
        if not math.isfinite(ratio[2]) or ratio[2] <= 0:
            raise ValueError("Channel ratios must be finite and positive")
    if "min_sum" in rule:
        value = rule["min_sum"]
        channels = value.get("channels", [])
        if not channels or len(set(channels)) != len(channels) or any(c not in ("r", "g", "b") for c in channels):
            raise ValueError("min_sum requires unique RGB channels")
        if not math.isfinite(value["value"]) or not 0 <= value["value"] <= len(channels):
            raise ValueError("min_sum threshold is outside the channel sum range")

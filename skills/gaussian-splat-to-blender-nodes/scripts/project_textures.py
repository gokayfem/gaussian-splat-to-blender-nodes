"""Project calibrated captures onto prepared UV surfaces. Run with ordinary Python.

python project_textures.py --config mapping.json --prepared outputs/prepared --out outputs/mapped
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from projection_core import finish_texture, project_surface
from projection_config import load_config, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--prepared", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--chunk-size", type=int, default=65536)
    args = parser.parse_args()
    if args.chunk_size <= 0:
        parser.error("chunk-size must be positive")
    cfg, root = load_config(args.config)
    prep = json.loads((args.prepared/"prepared.json").read_text())
    if prep["config_sha256"] != sha256(args.config):
        raise ValueError("Config changed since preparation; create a new prepared checkpoint")
    for relative, digest in prep["files"].items():
        if sha256(args.prepared/relative) != digest:
            raise ValueError(f"Prepared artifact changed: {relative}")
    captures, fingerprints = {}, {}
    for name, view in cfg["views"].items():
        camera = view["camera"]
        shape = (camera["height"], camera["width"])
        path = root/view["image"]
        with Image.open(path) as image:
            rgb = np.asarray(image.convert("RGB"))
        if rgb.shape[:2] != shape:
            raise ValueError(f"Capture dimensions do not match camera: {name}")
        fingerprints[name] = dict(image_sha256=sha256(path), source_valid_masks={})
        captures[name] = dict(camera=camera, rgb=rgb,
                              depth=np.load(args.prepared/f"depth/{name}.npy", mmap_mode="r"),
                              ids=np.load(args.prepared/f"depth/{name}_id.npy", mmap_mode="r"))
        if any(captures[name][key].shape != shape for key in ("depth", "ids")):
            raise ValueError(f"Visibility-map shape mismatch: {name}")
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(schema_version=1, config_sha256=sha256(args.config),
                  prepared_sha256=sha256(args.prepared/"prepared.json"),
                  source_blend_sha256=prep["source_blend_sha256"], captures=fingerprints, targets={})
    for target in cfg["targets"]:
        name = target["name"]
        fields = {k: np.load(args.prepared/f"{name}_{k}.npy", mmap_mode="r")
                  for k in ("position", "normal", "valid", "material")}
        valid = fields["valid"]
        if valid.dtype != bool or fields["material"].shape != valid.shape or not valid.any() or fields["position"].shape != (*valid.shape, 3) or fields["normal"].shape != (*valid.shape, 3):
            raise ValueError(f"Invalid prepared surface arrays: {name}")
        if not np.isfinite(fields["position"][valid]).all() or not np.isfinite(fields["normal"][valid]).all():
            raise ValueError(f"Non-finite prepared geometry: {name}")
        views = []
        for key, view in cfg["views"].items():
            item = dict(captures[key])
            mask = view.get("source_valid_masks", {}).get(name)
            if mask:
                path = root/mask
                with Image.open(path) as image:
                    allowed = np.asarray(image.convert("L")) >= 128
                if allowed.shape != item["depth"].shape:
                    raise ValueError(f"Source-mask dimensions do not match camera: {key}/{name}")
                item["allowed"] = allowed
                fingerprints[key]["source_valid_masks"][name] = sha256(path)
            views.append(item)
        color, state = project_surface(fields["position"], fields["normal"], valid,
                                       fields["material"], views, target, args.chunk_size)
        irr = np.load(args.prepared/f"{name}_irradiance.npy") if target.get("appearance") == "estimated_albedo" else None
        rgb, mix, padded = finish_texture(color, state, fields["material"], target, irr)
        Image.fromarray(np.rint(rgb*255).astype(np.uint8)).save(args.out/f"{name}_appearance.png")
        Image.fromarray(np.rint(mix*255).astype(np.uint8)).save(args.out/f"{name}_mix.png")
        Image.fromarray(padded).save(args.out/f"{name}_coverage.png")
        np.save(args.out/f"{name}_coverage.npy", padded)
        denominator = int(valid.sum())
        report["targets"][name] = dict(appearance=target.get("appearance", "captured_radiance"),
            surface_texels=denominator, direct=float(np.count_nonzero(state == 1)/denominator),
            rejected_fallback=float(np.count_nonzero(state == 2)/denominator),
            unseen_fallback=float(np.count_nonzero(state == 3)/denominator),
            padding_texels=int(np.count_nonzero(padded == 4)))
        print(name, json.dumps(report["targets"][name]), flush=True)
    report["files"] = {p.name: sha256(p) for p in sorted(args.out.iterdir()) if p.is_file()}
    report["coverage_legend"] = {"0": "outside selected UV surface", "1": "direct capture",
        "2": "rejected source; procedural fallback", "3": "unseen; procedural fallback", "4": "UV padding"}
    (args.out/"projection.json").write_text(json.dumps(report, indent=2)+"\n")


if __name__ == "__main__":
    main()

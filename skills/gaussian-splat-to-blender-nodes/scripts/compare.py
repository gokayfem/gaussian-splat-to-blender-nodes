#!/usr/bin/env python3
"""Compare equal-sized, identically named PNG pairs without changing their framing.

Use directories for a numbered sequence and --video to encode with FFmpeg.
No independent crops, auto-alignment, frame interpolation or fabricated missing views.
"""
import argparse
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw
from inspect_asset import sha256


def pairs(left, right):
    left, right = Path(left), Path(right)
    if left.is_file() and right.is_file():
        return [(left, right)]
    if not left.is_dir() or not right.is_dir():
        raise ValueError("Provide two image files or two frame directories")
    a = {p.name: p for p in left.glob("*.png")}
    b = {p.name: p for p in right.glob("*.png")}
    if not a or a.keys() != b.keys():
        raise ValueError(f"Frame sets differ or are empty: left-only={sorted(a.keys()-b.keys())[:5]}, right-only={sorted(b.keys()-a.keys())[:5]}")
    return [(a[k], b[k]) for k in sorted(a)]


def compose(left, right, labels=("Gaussian splat reference", "Native Blender nodes")):
    with Image.open(left) as a, Image.open(right) as b:
        if a.size != b.size:
            raise ValueError(f"Mismatched image sizes: {a.size} vs {b.size}")
        w, h = a.size
        out = Image.new("RGB", (w*2, h+32), (19, 23, 27))
        out.paste(a.convert("RGB"), (0, 32))
        out.paste(b.convert("RGB"), (w, 32))
    d = ImageDraw.Draw(out)
    d.text((10, 9), labels[0], fill="white")
    d.text((w+10, 9), labels[1], fill="white")
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("left", type=Path)
    p.add_argument("right", type=Path)
    p.add_argument("--out", required=True, type=Path, help="New directory for comparisons and evidence.json")
    p.add_argument("--video", action="store_true", help="Write comparison.mp4 using FFmpeg/libx264")
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--labels", nargs=2, default=["Gaussian splat reference", "Native Blender nodes"])
    a = p.parse_args()
    if a.fps <= 0:
        p.error("fps must be positive")
    pp = pairs(a.left, a.right)
    # Validate every pair before writing, so a mixed-size sequence cannot encode silently.
    sizes = set()
    for l, r in pp:
        with Image.open(l) as il, Image.open(r) as ir:
            if il.size != ir.size:
                p.error(f"Pair size mismatch: {l.name}")
            sizes.add(il.size)
    if len(sizes) != 1:
        p.error("Image dimensions vary across the sequence")
    a.out.mkdir(parents=True, exist_ok=False)
    evidence = []
    for i, (l, r) in enumerate(pp):
        dest = a.out / f"{i:06d}.png"
        compose(l, r, a.labels).save(dest)
        evidence.append(dict(frame=i, source_name=l.name,
                             left_sha256=sha256(l), right_sha256=sha256(r), comparison_sha256=sha256(dest)))
    record = dict(fps=a.fps, frames=len(pp), labels=a.labels, source_dimensions=list(next(iter(sizes))),
                  camera_match="Must be verified against the shared camera manifest; equal image size is not proof", images=evidence)
    if a.video:
        dest = a.out / "comparison.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-framerate", str(a.fps),
                        "-i", str(a.out/"%06d.png"), "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dest)], check=True)
        record["video"] = dict(filename=dest.name, sha256=sha256(dest))
    (a.out/"evidence.json").write_text(json.dumps(record, indent=2)+"\n")
    print(f"Wrote {len(pp)} paired frames to {a.out}")


if __name__ == "__main__":
    main()

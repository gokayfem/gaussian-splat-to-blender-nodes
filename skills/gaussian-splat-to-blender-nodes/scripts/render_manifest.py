"""Render a shared camera manifest in Blender. Removes GS_REFERENCE in memory.

One process renders sequentially. No scan renderer is bundled: export the manifest's
scan cameras in the chosen reference viewer using identical dimensions and FOV.
Does not save or overwrite the source .blend or change its lighting/color management.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cameras import validate_camera


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--reference", default="GS_REFERENCE")
    p.add_argument("--views", help="Comma-separated names; default is every world camera")
    p.add_argument("--samples", type=int, default=32)
    p.add_argument("--engine", choices=["CYCLES", "BLENDER_EEVEE"], default="BLENDER_EEVEE")
    a = p.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    data = json.loads(a.manifest.read_text())
    cameras = data["world"]
    chosen = a.views.split(",") if a.views else list(cameras)
    if a.samples <= 0 or not chosen:
        p.error("Positive samples and at least one camera required")
    for name in chosen:
        if not name or Path(name).name != name or name in (".", "..") or "\\" in name:
            p.error("Camera names must be safe file stems")
        validate_camera(cameras[name])
    a.out.mkdir(parents=True, exist_ok=False)
    ref = bpy.data.collections.get(a.reference)
    if ref:
        for ob in list(ref.all_objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.collections.remove(ref, do_unlink=True)
    sc = bpy.context.scene
    sc.render.engine = a.engine
    if a.engine == "CYCLES":
        sc.cycles.device, sc.cycles.samples, sc.cycles.use_denoising = "CPU", a.samples, True
    else:
        sc.eevee.taa_render_samples = a.samples
    cam = bpy.data.objects.new("QA_manifest_camera", bpy.data.cameras.new("QA_manifest_camera"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.sensor_fit = "VERTICAL"
    cam.data.clip_start, cam.data.clip_end = 0.01, 1000
    sc.render.resolution_percentage = 100
    sc.render.pixel_aspect_x = sc.render.pixel_aspect_y = 1
    sc.render.use_border = False
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    record = dict(manifest_sha256=hashlib.sha256(a.manifest.read_bytes()).hexdigest(),
                  engine=a.engine, samples=a.samples, view_transform=sc.view_settings.view_transform, views=[])
    import math
    for name in chosen:
        c = cameras[name]
        pos, target, up = (Vector(c[k]) for k in ("position", "look_at", "up"))
        z = (pos-target).normalized()
        x = up.cross(z).normalized()
        y = z.cross(x)
        cam.matrix_world = Matrix(((x.x, y.x, z.x, pos.x), (x.y, y.y, z.y, pos.y),
                                   (x.z, y.z, z.z, pos.z), (0, 0, 0, 1)))
        cam.data.angle_y = math.radians(c["fov_y_deg"])
        sc.render.resolution_x, sc.render.resolution_y = c["width"], c["height"]
        path = a.out / f"{name}.png"
        sc.render.filepath = str(path.resolve())
        bpy.ops.render.render(write_still=True)
        record["views"].append(dict(name=name, camera=c, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        (a.out/"render.json").write_text(json.dumps(record, indent=2)+"\n")
        print(f"RENDERED {name}", flush=True)


if __name__ == "__main__":
    main()

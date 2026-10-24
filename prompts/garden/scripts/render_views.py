"""Render canonical cameras from a saved garden .blend.

blender -b <file.blend> --python scripts/render_views.py -- --cams hero,opposite --out outputs/renders/r001
        [--scale 1.0] [--engine BLENDER_EEVEE|CYCLES] [--samples 64] [--clay] [--hide part1,part2]
"""
import argparse
import pathlib
import sys

import bpy

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--cams", default="hero")
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--engine", default="BLENDER_EEVEE")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--clay", action="store_true")
    ap.add_argument("--hide", default="")
    a = ap.parse_args(argv)
    sc = bpy.context.scene
    from garden.scene_setup import render_settings
    render_settings(sc, a.engine, a.samples)
    if a.clay:
        clay = bpy.data.materials.new("QA Clay")
        bsdf = clay.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (0.5, 0.5, 0.5, 1)
        bsdf.inputs["Roughness"].default_value = 0.8
        bpy.context.view_layer.material_override = clay
    for name in [h for h in a.hide.split(",") if h]:
        ob = bpy.data.objects.get("GARDEN_" + name)
        if ob:
            ob.hide_render = True
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for cam in a.cams.split(","):
        ob = bpy.data.objects["CAM_" + cam]
        sc.camera = ob
        sc.render.resolution_x = int(ob["width"] * a.scale)
        sc.render.resolution_y = int(ob["height"] * a.scale)
        sc.render.resolution_percentage = 100
        sc.render.filepath = str(out / f"{cam}.png")
        bpy.ops.render.render(write_still=True, scene=sc.name)
        print("RENDERED", sc.render.filepath)


main()

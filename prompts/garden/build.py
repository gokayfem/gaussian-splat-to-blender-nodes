"""Deterministic builder for the Garden reconstruction.

blender -b --factory-startup --python build.py -- [--parts table,vase] [--out outputs/garden.blend]
          [--with-reference] [--dump outputs/graph.json]

Builds every part in garden/parts (or the listed subset) as a Geometry Nodes modifier object in
GARDEN_PROCEDURAL, plus cameras and lighting. The hidden GS_REFERENCE cloud is opt-in.
"""
import argparse
import importlib
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from garden import compat  # noqa: E402

ADAPTER = compat.install()

import bpy  # noqa: E402
from nodekit import inspect, scene  # noqa: E402

from garden import lighting, scene_setup  # noqa: E402
from garden.parts import PARTS  # noqa: E402


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default=",".join(PARTS))
    ap.add_argument("--out", default=str(ROOT / "outputs/garden.blend"))
    ap.add_argument("--no-reference", action="store_true", help="Compatibility flag; scan is excluded by default")
    ap.add_argument("--with-reference", action="store_true", help="Requires locally acquired/decoded data; do not publish a scan-embedding blend")
    ap.add_argument("--dump", default="")
    return ap.parse_args(argv)


def build_part(name, coll):
    mod = importlib.import_module(f"garden.parts.{name}")
    if hasattr(mod, "materials"):
        mod.materials()
    tree = mod.build()
    me = bpy.data.meshes.new("GARDEN_" + name)
    ob = bpy.data.objects.new("GARDEN_" + name, me)
    coll.objects.link(ob)
    m = ob.modifiers.new(tree.name, "NODES")
    m.node_group = tree
    return ob, m


def main():
    a = parse()
    scene.reset()
    sc = bpy.context.scene
    cols = scene_setup.collections(sc)
    scene_setup.render_settings(sc)
    scene_setup.cameras(cols["CAMERAS"])
    lighting.setup(sc, cols["LIGHTING"])
    if a.with_reference and not a.no_reference:
        scene_setup.reference_cloud(cols["GS_REFERENCE"])
    report = {}
    for name in [p for p in a.parts.split(",") if p]:
        t0 = time.time()
        try:
            ob, m = build_part(name, cols["GARDEN_PROCEDURAL"])
            bpy.context.view_layer.update()
        except Exception as e:  # Report failures and refuse to save an incomplete scene.
            import traceback
            report[name] = dict(failed=f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-600:])
            continue
        stats = inspect.evaluated_stats(ob)
        report[name] = dict(seconds=round(time.time() - t0, 2), verts=stats["verts"], faces=stats["faces"],
                            warnings=[w.message for w in m.node_warnings])
    failures = {k: v for k, v in report.items() if "failed" in v}
    if failures:
        raise RuntimeError(f"Incomplete Garden build: {failures}")
    sc.camera = bpy.data.objects["CAM_hero"]
    lint = inspect.check_groups("Garden ")
    if lint or any(p["warnings"] for p in report.values()):
        raise RuntimeError(f"Node validation failed: {lint}; parts: {report}")
    if a.dump:
        inspect.dump_groups(a.dump, prefix="Garden ")
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=a.out, compress=True)
    import json
    print("BUILD_REPORT " + json.dumps(dict(adapter=ADAPTER, parts=report, lint=lint, out=a.out)))


main()

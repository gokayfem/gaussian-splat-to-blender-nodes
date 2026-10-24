"""Audit native Geometry Nodes objects and remove GS_REFERENCE in memory.

Run in a disposable background Blender process with --python-exit-code 1.
Never saves the loaded .blend. Signatures cover evaluated mesh vertices/topology,
material assignments and instance transforms. This is structural evidence, not a
render-equivalence test or a guarantee that a scene resembles its reference.
"""
import argparse
from array import array
import hashlib
import json
from pathlib import Path
import struct
import sys

import bpy


def mesh_signature(obj):
    me = obj.to_mesh()
    if me is None:
        return None
    try:
        h = hashlib.sha256()
        for items, prop, code, stride in ((me.vertices, "co", "f", 3), (me.loops, "vertex_index", "i", 1),
                                          (me.polygons, "loop_total", "i", 1), (me.polygons, "material_index", "i", 1)):
            a = array(code, [0]) * (len(items)*stride)
            items.foreach_get(prop, a)
            h.update(a.tobytes())
        h.update(json.dumps([m.name if m else None for m in me.materials]).encode())
        return dict(vertices=len(me.vertices), faces=len(me.polygons), sha256=h.hexdigest())
    finally:
        obj.to_mesh_clear()


def snapshot(names):
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    objects, instances, cache = {}, [], {}
    for name in sorted(names):
        ob = bpy.data.objects.get(name)
        if ob is None:
            objects[name] = None
            continue
        evaluated = ob.evaluated_get(dg)
        objects[name] = dict(mesh=mesh_signature(evaluated), matrix=[list(row) for row in ob.matrix_world])
    for inst in dg.object_instances:
        if not inst.is_instance or not inst.parent or inst.parent.original.name not in names:
            continue
        ob = inst.object
        key = ob.as_pointer()
        if key not in cache:
            cache[key] = mesh_signature(ob)
        h = hashlib.sha256(json.dumps(cache[key], sort_keys=True).encode())
        h.update(struct.pack("<16d", *(x for row in inst.matrix_world for x in row)))
        instances.append(h.hexdigest())
    return dict(objects=objects, instance_count=len(instances),
                instances_sha256=hashlib.sha256("".join(sorted(instances)).encode()).hexdigest())


def audit(collection, reference):
    coll = bpy.data.collections.get(collection)
    if coll is None or not coll.all_objects:
        raise ValueError(f"Missing/empty procedural collection: {collection}")
    objects = list(coll.all_objects)
    names = {o.name for o in objects}
    failures, warnings, inventory = [], [], []
    for ob in objects:
        mods = [m for m in ob.modifiers if m.type == "NODES" and m.node_group and m.show_render and m.show_viewport]
        if ob.type != "MESH" or not mods:
            failures.append(f"{ob.name}: expected mesh object with enabled Geometry Nodes")
        if ob.type == "MESH" and len(ob.data.vertices):
            failures.append(f"{ob.name}: base mesh is nonempty; inspect whether geometry was baked/imported")
        inventory.append(dict(name=ob.name, base_vertices=len(ob.data.vertices) if ob.type == "MESH" else None,
                              node_groups=[m.node_group.name for m in mods]))
        for m in mods:
            for w in getattr(m, "node_warnings", []):
                failures.append(f"{ob.name}: {w.message}")
    refs = bpy.data.collections.get(reference)
    if refs and not refs.hide_render:
        failures.append(f"{reference} collection is not hidden from rendering")
    reference_names = {ob.name for ob in refs.all_objects} if refs else set()
    if names & reference_names:
        raise ValueError("Reference and procedural collections share objects; refusing destructive test")
    groups = [g for g in bpy.data.node_groups if g.bl_idname == "GeometryNodeTree"]
    for g in groups:
        for link in g.links:
            if not link.is_valid:
                failures.append(f"{g.name}: invalid node link")
        for n in g.nodes:
            if n.bl_idname in ("GeometryNodeObjectInfo", "GeometryNodeCollectionInfo"):
                for socket in n.inputs:
                    value = getattr(socket, "default_value", None)
                    if isinstance(value, bpy.types.Object) and value.name in reference_names:
                        warnings.append(f"{g.name}/{n.name}: references scan object {value.name}")
                    if isinstance(value, bpy.types.Collection) and value.name == reference:
                        warnings.append(f"{g.name}/{n.name}: references scan collection")
    materials = [m for m in bpy.data.materials if m.users]
    for m in materials:
        if not m.node_tree:
            failures.append(f"{m.name}: no Shader Nodes")
    image_nodes = sorted({f"{g.name}/{n.name}" for g in [*bpy.data.node_groups, *(m.node_tree for m in materials if m.node_tree)]
                          for n in g.nodes if n.bl_idname in ("ShaderNodeTexImage", "ShaderNodeTexEnvironment")})
    if image_nodes:
        warnings.append("Image textures need provenance/manual review; they are not inherently scan-free")
    before = snapshot(names)
    if refs:
        for ob in list(refs.all_objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.collections.remove(refs, do_unlink=True)
        # Blender can retain the previous evaluated GN result after an ID is deleted.
        # Invalidate graph/object caches explicitly before the independence comparison.
        for group in bpy.data.node_groups:
            group.update_tag()
        for ob in bpy.data.objects:
            ob.update_tag(refresh={"DATA"})
    after = snapshot(names)
    if before != after:
        failures.append("Evaluated geometry/instances changed after removing the reference")
    mesh_vertices = sum((v.get("mesh") or {}).get("vertices", 0) for v in after["objects"].values() if v)
    if mesh_vertices == 0 and after["instance_count"] == 0:
        failures.append("Procedural collection evaluates to no meshes or instances")
    return dict(blender_version=bpy.app.version_string, collection=collection, reference=reference,
                reference_objects_removed=len(reference_names), inventory=inventory,
                geometry_node_groups=len(groups), shader_materials=len(materials), image_nodes=image_nodes,
                before=before, after=after, failures=failures, warnings=warnings,
                passed=not failures, limits="Does not compare rendered pixels, materials before/after, animation, or prove visual fidelity")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--collection", default="GARDEN_PROCEDURAL")
    p.add_argument("--reference", default="GS_REFERENCE")
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    r = audit(a.collection, a.reference)
    source = Path(bpy.data.filepath)
    if source.is_file():
        h = hashlib.sha256()
        with source.open("rb") as f:
            for chunk in iter(lambda: f.read(1024*1024), b""):
                h.update(chunk)
        r["blend"] = dict(filename=source.name, sha256=h.hexdigest(), mtime_ns=source.stat().st_mtime_ns)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(r, indent=2)+"\n")
    print(json.dumps({k: r[k] for k in ("passed", "failures", "warnings", "geometry_node_groups", "shader_materials")}))
    if not r["passed"]:
        raise RuntimeError("Native scene audit failed; see JSON report")


if __name__ == "__main__":
    main()
